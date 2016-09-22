"""
Extraction of data from product pages done using `scrapingresults` module gives
raw strings only. This module "enriches" these strings by converting them to appriopriate
higher-level representation using Python classes.

Prices
======

Enriching lists of prices gives lists of PriceBase instances, sorted by distance to the name element. These instances represent one of three forms of price information: a single price, a pair of two prices, and a range of prices. All instances have these method:
    - :method:`PriceBase.get_orig_price()` - return :class:`PriceValue` representing original price
    - :method:`PriceBase.get_sale_price()` - return :class:`PriceValue` representing sale price
where the :class:`PriceValue` class is a named tuple of `currency` and `value` (as `Decimal` number).
If a price value couldn't be extracted, None is returned.

Example session:
    >>> res = e.extract_from_url(url)
    >>> first_price = res['price'][0]
    >>> orig_price = first_price.get_orig_price()
    >>> orig_price_currency = orig_price.currency
    >>> orig_price_value = orig_price.value


Names
=====

Names are parsed into a list of :class:`Name` tuples with `product_name` and `brand_name`
attributes. If a brand name can't be found, it is set to None.

"""


import re
from collections import namedtuple
from decimal import Decimal
import logging

from . import xbrowser
from . import scraper as scrapermod
from . import scrapingresults
from . import textutils


log = logging.getLogger(__name__)


class EnrichmentException(Exception): pass


# A simple representation of a price as a tuple of currency and a value
PriceValue = namedtuple('PriceValue', ['currency', 'value'])


class PriceBase(object):
    """Representation of parsed price that gives original and sale prices.
    """

    def get_orig_price(self):
        """Returns original price as PriceValue or None if
        price couldn't be parsed.
        """
        raise NotImplementedError()

    def get_sale_price(self):
        """Returns sale price as PriceValue or None if
        price couldn't be parsed.
        """
        raise NotImplementedError()

    def __cmp__(self, other):
        return cmp((self.get_orig_price(), self.get_sale_price()),
                (other.get_orig_price(), other.get_sale_price()))

    def __hash__(self):
        return hash((self.get_orig_price(), self.get_sale_price()))


class PriceSingle(PriceBase):

    def __init__(self, price_value):
        assert isinstance(price_value, PriceValue)
        self.price_value = price_value

    def get_orig_price(self):
        return self.price_value

    def get_sale_price(self):
        return None

    def __repr__(self):
        return 'PriceSingle(price_value={self.price_value})'.format(self=self)


class PricePair(PriceBase):

    def __init__(self, orig_price, sale_price):
        assert isinstance(orig_price, PriceValue)
        assert isinstance(sale_price, PriceValue)
        self.orig_price = orig_price
        self.sale_price = sale_price

    def get_orig_price(self):
        return self.orig_price

    def get_sale_price(self):
        return self.sale_price

    def __repr__(self):
        return 'PricePair(orig_price={self.orig_price}, sale_price={self.sale_price})'.format(self=self)


class PriceRange(PriceBase):

    def __init__(self, orig_price_range, sale_price_range):
        self.orig_price_range = orig_price_range
        self.sale_price_range = sale_price_range

    def __repr__(self):
        return 'PriceRange(orig_price_range={self.orig_price_range}, sale_price_range={self.sale_price_range})'.format(self=self)

    def get_orig_price(self):
        if self.orig_price_range:
            # Return the first (lowest) price from the range
            return self.orig_price_range[0]

    def get_sale_price(self):
        if self.sale_price_range:
            return self.sale_price_range[0]


Name = namedtuple('Name', ['product_name', 'brand_name'])


Image = namedtuple('Image', ['src', 'size'])


def enrich(raw_results_by_tag, scraper_results_by_tag, scraper):
    """This function is called by functions from `extractor` module.

    :param:`raw_results_by_tag` a dictionary mapping tags (price/name/img)
    to lists of strings containing extracted raw values.

    :param:`scraper_results_by_tag` a dictionary mapping tags to
    lists of :class:`xpathscraper.scraper.ScrapingResult`

    :param:`scraper` a :class:`xpathscraper.scraper.Scraper` instance with
    loaded product page.
    """
    res = {}

    for tag in raw_results_by_tag:

        # Just rewrite ready values if they were supplied by Scraper
        if all(sr.rich_value is not None for sr in scraper_results_by_tag[tag]):
            res[tag] = [sr.rich_value for sr in scraper_results_by_tag[tag]]
            continue
        if all(sr.value is not None for sr in scraper_results_by_tag[tag]):
            res[tag] = [sr.value for sr in scraper_results_by_tag[tag]]
            continue

        # Find a function for each tag, matching a pattern _enrich_<tag>
        try:
            fun = globals()['_enrich_%s' % tag]
        except KeyError:
            res[tag] = raw_results_by_tag[tag]
        else:
            log.debug('Enriching raw_results: %s', raw_results_by_tag[tag])
            log.debug('Enriching scraper_results: %s', scraper_results_by_tag[tag])

            # Compute enriched results giving raw results and scraping results
            res[tag] = fun(raw_results_by_tag[tag], scraper_results_by_tag[tag], scraper)
    return res


### Prices

def _find_currency(price_text):
    if not price_text:
        return None
    for cs in xbrowser.jsonData['currency_symbols']:
        if cs in price_text:
            return cs
    return None

def _strip_currency(price_text, currency_symbol):
    if not currency_symbol:
        return price_text
    return re.sub(re.escape(currency_symbol), '', price_text)

def _price_as_decimal(price_text):
    # Remove all comas, non-numbers and non-dots
    price_text = price_text.replace(',', '')
    digits = re.sub(r'[^0-9.]', '', price_text)

    # What's left still can look like '.49.00'. Remove all dots but the last
    dots_left = sum(1 for c in digits if c == '.')
    if dots_left > 1:
        digits = re.sub(r'\.', '', digits, count=dots_left - 1)

    return Decimal(digits)

def _pricevalue_from_text(text):
    if not text:
        return None
    currency = _find_currency(text)
    value = _price_as_decimal(text)
    return PriceValue(currency, value)

def _price_from_el(scraper, el):
    text = scrapingresults._extract_price_text(scraper, el)
    if not text:
        return None
    return _pricevalue_from_text(text)

def _price_pair(scraper, el1, el2):
    p1 = _price_from_el(scraper, el1)
    p2 = _price_from_el(scraper, el2)
    if p1.value > p2.value:
        return PricePair(p1, p2)
    return PricePair(p2, p1)

def _price_range(scraper, el):
    text = scrapingresults._extract_price_text(scraper, el)
    words = textutils.split_longwords(text)
    num_words = [w for w in words if textutils.contains_digit(w)]
    assert len(num_words) == 2
    p1 = _pricevalue_from_text(num_words[0])
    p2 = _pricevalue_from_text(num_words[1])
    # TODO: sale price range
    return PriceRange(orig_price_range=(p1, p2), sale_price_range=None)

def _enrich_price(raw_values, scraper_results, scraper):
    els_sresults = scraper.eval_sr_first_xpaths(scraper_results)
    if not els_sresults:
        return []
    price_ranges = [el_sresult.el for el_sresult in els_sresults if \
            el_sresult.scraping_result.flag == scrapermod.RESULTDESC_PRICE_RANGE]
    els_for_clustering = [el_sresult.el for el_sresult in els_sresults if \
            el_sresult.el not in price_ranges]

    if len(els_for_clustering) == 1:
        clusters, not_paired = [], [els_for_clustering[0]]
    else:
        jsresult = scraper.xbrowser.execute_jsfun('_XPS.clusterPriceElements', els_for_clustering)
        log.debug('_XPS.clusterPriceElements: %s', jsresult)
        clusters, not_paired = jsresult

    res = []
    for cluster in clusters:
        if not cluster:
            continue
        prices = [_price_from_el(scraper, c_el) for c_el in cluster]
        prices = filter(None, prices)
        if len(prices) < 2:
            continue
        els_prices = zip(cluster, prices)
        if len(prices) > 3:
            log.warn('Dropping too large price elements cluster: %s', prices)
            continue
        if len(prices) == 3:
            log.info('Discarding smallest price from cluster: %s', prices)
            els_prices.sort(key=lambda (el, p): p.value, reverse=True)
        assert len(prices) in (2, 3)
        res.append(_price_pair(scraper, els_prices[0][0], els_prices[1][0]))
    for el in price_ranges:
        price_res = _price_range(scraper, el)
        if price_res:
            res.append(price_res)
    for el in not_paired:
        price_val = _price_from_el(scraper, el)
        if price_val:
            res.append(PriceSingle(price_val))
    return res


# Names

def _enrich_name(raw_values, scraper_results, scraper):
    if len(scraper_results) == 1:
        log.warn('More than one name element')
    els_sresults = scraper.eval_sr_xpaths(scraper_results[:1])
    assert len(els_sresults) in (1, 2)
    if len(els_sresults) == 1 or not scraper_results[0].flag:
        return [Name(product_name=raw_values[0], brand_name=None)]
    
    assert scraper_results[0].flag == scrapermod.RESULTDESC_NAME_COMBINED
    has_link = [scraper.xbrowser.execute_jsfun_safe(False, '_XPS.containsTag', el_sr.el, 'a') \
            for el_sr in els_sresults]
    texts = [scraper.xbrowser.el_text(el_sr.el) for el_sr in els_sresults]
    if has_link[0] and not has_link[1]:
        return [Name(product_name=texts[1], brand_name=texts[0])]
    if has_link[1] and not has_link[0]:
        return [Name(product_name=texts[0], brand_name=texts[1])]
    return [Name(product_name='%s %s' % (texts[0], texts[1]), brand_name=None)]

