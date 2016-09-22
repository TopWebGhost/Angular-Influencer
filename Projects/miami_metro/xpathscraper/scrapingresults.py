import logging

import selenium
import selenium.common.exceptions

from . import xbrowser
from . import scraper as scrapermod
from . import utils
from . import textutils


log = logging.getLogger(__name__)


class ResultsComputationException(Exception):
    '''This exception is thrown when an error is encountered
    during computation of results.

    :class:`xpathscraper.scraper.ScraperException` is thrown when
    an error occurs during scraping phase.
    '''
    pass


class NoResultException(Exception): pass


STOP_CHARS = xbrowser.jsonData['currency_symbols'] + ['+']

def _extract_first_price_text(text):
    text = text.strip()
    currency_idxs = utils.find_all_non_overlapping(text, STOP_CHARS)
    if len(currency_idxs) > 1:
        valid_fragment = text[:currency_idxs[1]]
    else:
        valid_fragment = text
    return valid_fragment

    #def valid_price_char(c):
    #    if c.isdigit():
    #        return True
    #    if c in xbrowser.jsonData['currency_symbols']:
    #        return True
    #    if c in ('.', ','):
    #        return True
    #    if c.isspace():
    #        return True
    #    return False
    #invalid_idxs = [i for i, c in enumerate(valid_fragment) if not valid_price_char(c)]
    #if invalid_idxs:
    #    return valid_fragment[:invalid_idxs[0]]
    #return valid_fragment

def _price_text_from_fragments(fragments):

    def combine(f_currency, f_num1, f_num2):
        if textutils.represents_int(f_num2):
            if len(f_num2.strip()) == 2:
                return f_currency + f_num1 + '.' + f_num2
        return f_currency + f_num1 + f_num2

    for triplet in utils.triplets(fragments):
        f_cs = [t for t in triplet if textutils.contains_currency_symbol(t)]
        f_num = [t for t in triplet if textutils.contains_digit(t)]
        if len(f_cs) == 1 and len(f_num) == 2:
            return combine(f_cs[0], f_num[0], f_num[1])

    for (f1, f2) in utils.pairs(fragments):
        if (textutils.contains_currency_symbol(f1) and textutils.contains_digit(f2)) or \
           (textutils.contains_currency_symbol(f2) and textutils.contains_digit(f1)):
               return f1 + f2

    return None


def _extract_price_text(scraper, el):
    single_text = scraper.xbrowser.el_text(el).strip()
    if textutils.contains_digit(single_text) and any(cs in single_text for cs in \
            xbrowser.jsonData['currency_symbols']):
        return _extract_first_price_text(single_text)
    fragments = [f.strip() for f in scraper.xbrowser.el_text_all_list(el)]
    log.debug('fragments: %s', fragments)
    f_price_text = _price_text_from_fragments(fragments)
    log.debug('f_price_text: %s', f_price_text)
    if f_price_text is None:
        return None
    return _extract_first_price_text(f_price_text)

class ResultEvaluator(object):

    def __init__(self, scraper):
        self.scraper = scraper

    def compute_values(self, scraping_result, tag):
        assert isinstance(scraping_result, scrapermod.ScrapingResult), 'scraping_result: %s' % \
                scraping_result
        if scraping_result.rich_value is not None:
            return scraping_result.rich_value
        if scraping_result.value is not None and (not scraping_result.xpath_expr_list \
                or not hasattr(self, '_eval_%s' % tag)):
            return scraping_result.value
        try:
            method = getattr(self, '_eval_%s' % tag)
        except AttributeError:
            raise ResultsComputationException('Invalid tag %s result %s' % (tag, scraping_result))
        try:
            return method(scraping_result)
        except NoResultException:
            return None

    def _xpath_value(self, xpath):
        res = None
        try:
            res = self.scraper.driver.find_element_by_xpath(xpath)
        except (selenium.common.exceptions.NoSuchElementException,
                selenium.common.exceptions.StaleElementReferenceException):
            pass
        if not res:
            raise NoResultException('No element evaled from xpath returned by scraper')
        return res

    def _eval_img(self, scraping_result):
        res = []
        for expr in scraping_result.xpath_expr_list:
            el = self._xpath_value(expr)
            src = el.get_attribute('src')
            if not src:
                log.warn('img result has empty src')
            else:
                res.append(src)
        if not res:
            raise NoResultException('No img value')
        return res[0]
    
    def _eval_name(self, scraping_result):

        if not scraping_result.flag:
            res = []
            for xpath_expr in scraping_result.xpath_expr_list:
                el = self._xpath_value(xpath_expr)
                res.append(self.scraper.xbrowser.el_text(el).strip())
            if not res:
                raise NoResultException('No name value')
            return res[0]

        elif scraping_result.flag == scrapermod.RESULTDESC_NAME_COMBINED:
            name_combined = ' '.join(self.scraper.xbrowser.el_text(self._xpath_value(xpath_expr)) \
                    for xpath_expr in scraping_result.xpath_expr_list)
            log.debug('Name combined: <%s>', name_combined)
            return name_combined.strip()

        else:
            assert False, 'Unknown name flag %s' % scraping_result.flag

    def _eval_price(self, scraping_result):
        res = []
        for xpath_expr in scraping_result.xpath_expr_list:
            el = self._xpath_value(xpath_expr)
            res.append(_extract_price_text(self.scraper, el))
        if not res:
            raise NoResultException('No price value')
        return res[0]

    def _els_texts_from_xpaths(self, scraping_result):
        return [self.scraper.xbrowser.el_text_from_text_or_attr_values(el) \
                for xpath in scraping_result.xpath_expr_list \
                for el in self.scraper.xbrowser.els_by_xpath(xpath)]

    def _eval_size(self, scraping_result):
        els_texts = self._els_texts_from_xpaths(scraping_result)
        size_range = self.scraper._size_range_from_cluster(els_texts)
        if len(set(size_range)) >= 2:
            return size_range
        return self.scraper._num_range_from_cluster(els_texts)

    def _eval_color(self, scraping_result):
        els_texts = self._els_texts_from_xpaths(scraping_result)
        return self.scraper._color_range_from_cluster(els_texts)

    def _firsttext(self, scraping_result):
        els_texts = self._els_texts_from_xpaths(scraping_result)
        if not els_texts:
            return ''
        return els_texts[0].text

    _eval_addtocart = _firsttext

    _eval_checkoutbutton = _firsttext

    _eval_removefromcart = _firsttext

    _eval_checkoutprice = _eval_price

