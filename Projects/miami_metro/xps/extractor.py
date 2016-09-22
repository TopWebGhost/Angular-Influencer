from collections import defaultdict
import logging
import pprint
import threading
import urlparse
import time

from django.db.models import F

from xpathscraper import scrapingresults
from xpathscraper import xbrowser
from xpathscraper import scraper as scrapermod
from xpathscraper import utils
from xpathscraper import resultsenrichment
from platformdatafetcher import platformutils

from xps import models

import debra.models


log = logging.getLogger(__name__)


TAG_LIST_ALL = ['name', 'img', 'price', 'size', 'color', 'sizetype', 'inseam', 'colordata',
        'checkoutbutton']


def normalize_product_url(url):
    parsed = urlparse.urlsplit(url)

    if parsed.netloc.endswith('affiliatetechnology.com'):
        for k in ('URL', 'url'):
            to_find = '&{k}='.format(k=k)
            idx = parsed.query.find(to_find)
            if idx != -1:
                return parsed.query[idx + len(to_find):]


    return url

def get_or_create_product(url):
    url = normalize_product_url(url)
    try:
        return debra.models.ProductModel.objects.get(prod_url=url)
    except debra.models.ProductModel.DoesNotExist:
        return debra.models.ProductModel.objects.create(prod_url=url)
    except debra.models.ProductModel.MultipleObjectsReturned:
        return debra.models.ProductModel.objects.filter(prod_url=url)[0]

def xpath_exprs_for_domain(domain, tag):
    """Computes all xpath expressions (as strings) related to a given domain name
    (which shouldn't begin with 'www.') and a tag (price/name/img).
    """
    from_product = models.XPathExpr.objects.filter(scraping_result__tag=tag).\
            filter(scraping_result__product_model__brand__domain_name=domain).\
            order_by('id')
    return utils.unique_sameorder(xpe.expr for xpe in from_product)


class ExtractionResultsDict(dict):
    """A dictionary subclass that adds some fields describing
    extraction process and clicking results. Main results are stored as dictionary
    items with keys being tags and values - parsed and enriched
    results.
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.valid_product_page = None
        self.not_found_page = None
        self.clicking_results = []

    def __repr__(self):
        orig = dict.__repr__(self)
        return 'ExtractionResultsDict(valid_product_page=%r, not_found_page=%r, ' \
                   'clicking_results=%r, %s)' %  (self.valid_product_page, self.not_found_page,
                           self.clicking_results, orig)

    def _all_results(self, tag):
        res = []
        for reslist in self.get(tag, []):
            if isinstance(reslist, (list, tuple)):
                res.extend(reslist)
        return utils.unique_sameorder(res)

    def _cm_for_colordata(self, d):
        c_m, created = debra.models.Color.objects.get_or_create(name=d.get('name'),
                product_img=d.get('product_img'),
                swatch_img=d.get('swatch_img'))
        return c_m

    def _get_or_create_csms_for_static_page(self, product_model):
        """get_or_creates a list of ColorSizeModels
        that represent size, sizetype, color and colordata results.
        """
        res = []

        color_models = [self._cm_for_colordata(d) for d in self.get('colordata', [])]

        color_names = self._all_results('color')
        size_names = self._all_results('size') or ['Nil']

        for size_n in size_names:
            args = {'product': product_model, 'size': size_n, 'size_standard': size_n}
            if color_models:
                for c_m in color_models:
                    args['color'] = c_m.name
                    args['color_data'] = c_m
                    csm, created = debra.models.ColorSizeModel.objects.get_or_create(**args)
                    res.append(csm)
            elif color_names:
                for color_n in color_names:
                    args['color'] = color_n
                    args['color_data'] = None
                    csm, created = debra.models.ColorSizeModel.objects.get_or_create(**args)
                    res.append(csm)
            else:
                args['color'] = 'Nil'
                args['color_data'] = None
                csm, created = debra.models.ColorSizeModel.objects.get_or_create(**args)
                res.append(csm)
        return res

    def _create_product_price(self, csm, first_price):
        # Pick proper price values to put in 'price', 'orig_price' fields of ProductPrice
        if not first_price.get_orig_price() and not first_price.get_sale_price():
            log.warn('Prices are empty, doing nothing')
            return
        if first_price.get_orig_price() and first_price.get_sale_price():
            price = first_price.get_sale_price().value
            orig_price = first_price.get_orig_price().value
        elif first_price.get_orig_price() and not first_price.get_sale_price():
            price = first_price.get_orig_price().value
            orig_price = None
        else:
            assert not first_price.get_orig_price() and first_price.get_sale_price()
            price = first_price.get_sale_price().value
            orig_price = None
        product_price = debra.models.ProductPrice(product=csm, price=price, orig_price=orig_price)
        product_price.save()
        log.info('Saved ProductPrice id=%s', product_price.id)
        return product_price


    def create_product_prices_for_clicking_results(self, product_model):
        """Creates :class:`debra.models.ProductPrice` instances base on clicking results.
        """
        if not self.clicking_results:
            log.warn('No clicking results, cannot create product prices')
            return []
        res = []
        for page_results in self.clicking_results:
            if not page_results.get('checkoutprice'):
                log.warn('No checkoutprice, cannot create product price')
                continue
            csm_args = {'product': product_model}
            if 'colordata' in page_results:
                csm_args['color_data'] = self._cm_for_colordata(page_results['colordata'][0])
            if 'sizevalue' in page_results:
                csm_args['size'] = page_results['sizevalue'][0]
                csm_args['size_standard'] = page_results['sizevalue'][0]
            if 'sizetypevalue' in page_results:
                csm_args['size_sizetype'] = page_results['sizetypevalue'][0]
            if 'inseamvalue' in page_results:
                csm_args['size_inseam'] = page_results['inseamvalue'][0]
            csm, created = debra.models.ColorSizeModel.objects.get_or_create(**csm_args)
            pp = self._create_product_price(csm, page_results['checkoutprice'][0])
            res.append(pp)
        return res

    def create_product_prices_for_static_page(self, product_model):
        """Creates :class:`debra.models.ProductPrice` instances base on results for a static page.
        """
        if not self.get('price'):
            log.warn('No price, cannot create ProductPrice model')
            return None
        csms = self._get_or_create_csms_for_static_page(product_model)
        res = []
        for csm in csms:
            pp = self._create_product_price(csm, self['price'][0])
            res.append(pp)
        return res

    __str__ = __repr__


class ScraperOpRecorder(object):

    def __init__(self, product):
        self.opr = platformutils.OpRecorder(operation='scraping', product_model=product)
        self.operations = []

    def __call__(self, domain, op, op_status, op_msg):
        self.operations.append(dict(domain=domain, op=op, op_status=op_status, op_msg=op_msg))

    def exception(self):
        self.opr.data = dict(self.opr.data or {}, operations=self.operations)
        self.opr.register_exception()

    def finish(self):
        self.opr.data = dict(self.opr.data or {}, operations=self.operations)
        if not self.opr.is_exception_registered():
            self.opr.register_success()


class XBrowserStorage(object): pass

xbrowser_storage = XBrowserStorage()


class Extractor(object):
    """A main high-level class for extracting results from product pages.
    """

    def __init__(self, driver=None, headless_display=False, reuse_xbrowser=False, sleep_after_load=0):
        self.driver = driver
        self.scraper = None
        self.headless_display = headless_display
        self.reuse_xbrowser = reuse_xbrowser
        self.xbrowser = None
        self.sleep_after_load = sleep_after_load

    def _create_scraper(self, product):
        op_recorder = ScraperOpRecorder(product)
        if self.reuse_xbrowser and getattr(xbrowser_storage, 'xbrowser', None):
            log.info('Reusing xbrowser')
            self.xbrowser = xbrowser_storage.xbrowser
        else:
            log.debug('Creating new xbrowser')
            try:
                self.xbrowser = xbrowser.XBrowser(driver=self.driver,
                        headless_display=self.headless_display,
                        auto_refresh=True if self.reuse_xbrowser else False)
            except:
                op_recorder.exception()
                raise
        if self.reuse_xbrowser:
            xbrowser_storage.xbrowser = self.xbrowser
        self.xbrowser.load_url(product.prod_url)
        if self.sleep_after_load:
            log.debug('Sleeping %d seconds before scraping', self.sleep_after_load)
            time.sleep(self.sleep_after_load)
            log.debug('Finished sleeping')

        if self.reuse_xbrowser:
            log.debug('Reusing xbrowser -- forcing a refresh.')
            self.xbrowser.xrefresh()
            if self.sleep_after_load:
                log.debug('Sleeping %d seconds before scraping', self.sleep_after_load)
                time.sleep(self.sleep_after_load)
                log.debug('Finished sleeping')
        self.scraper = scrapermod.Scraper(self.xbrowser, op_recorder)

    def _compute_enriched(self, sr_by_tag):
        log.debug('_compute_enriched:\n%s', pprint.pformat(sr_by_tag))
        # Compute raw text values first
        result_evaluator = scrapingresults.ResultEvaluator(self.scraper)
        raw_values = defaultdict(list)
        for tag in sr_by_tag:
            for sr_w in sr_by_tag[tag]:
                values = result_evaluator.compute_values(sr_w, tag)
                if values is not None:
                    raw_values[tag].append(values)

        # Now enrich them and return enriched as result
        enriched = resultsenrichment.enrich(dict(raw_values), sr_by_tag, self.scraper)
        return enriched


    def _do_extract(self, product, tag_list, quit_driver, scraping_result_m_list,
            perform_clicking=True):
        log.debug('All scraping result models: %s', pprint.pformat(
            sorted(scraping_result_m_list, key=lambda m: m.tag)))
        if self.scraper is None:
            self._create_scraper(product)
        try:
            sr_by_tag = defaultdict(list)
            for scraping_result_m in scraping_result_m_list:
                sr_by_tag[scraping_result_m.tag].append(models.create_wrapped_scraping_result(
                    scraping_result_m))

            enriched = self._compute_enriched(sr_by_tag)

            res = ExtractionResultsDict(enriched)
            res.valid_product_page = self.scraper.current_page_is_valid_product_page()
            res.not_found_page = self.scraper.current_page_is_not_found_page()
            if perform_clicking:
                clicking_results = self.scraper.perform_clicking()
                if clicking_results:
                    res.clicking_results = [self._compute_enriched(d) for d in clicking_results]
                    log.debug('enriched clicking_results: \n%s', pprint.pformat(res.clicking_results))
            self.scraper._op_recorder.finish()
            return res
        except:
            self.scraper._op_recorder.exception()
            raise
        finally:
            if quit_driver:
                self.cleanup_xresources()

    def cleanup_xresources(self):
        log.debug('Quitting driver')
        if hasattr(self, 'xbrowser') and self.xbrowser and not self.reuse_xbrowser:
            self.xbrowser.quit_driver()
            self.xbrowser.quit_display()
        if not self.reuse_xbrowser:
            self.driver = None
            self.scraper = None

    def _compute_scraping_results_models(self, product, tag_list):
        self._create_scraper(product)
        product.scrapingresult_set.all().delete()
        model_list = []
        assert self.scraper is not None
        for tag in tag_list:
            try:
                method = getattr(self.scraper, 'get_%s_xpaths' % tag)
            except AttributeError:
                raise scrapingresults.ResultsComputationException('Invalid tag: %s' % tag)
            scraping_results = method()
            log.debug('scraping_results for tag=%s: %s', tag, scraping_results)
            model_list.extend(models.create_scraping_result_models(product, tag, scraping_results))
        return model_list

    def extract_using_computed_xpaths(self, product, tag_list=['name', 'img', 'price'], quit_driver=True):
        model_list = self._compute_scraping_results_models(product, tag_list)
        res = self._do_extract(product, tag_list, quit_driver, model_list, perform_clicking=False)
        return res

    def _scraping_results_models_from_set(self, brand, tag_list, set_description):
        q = brand.scrapingresultset_set.all()
        if set_description is not None:
            q = q.filter(description=set_description)
        our_set = q[0]
        log.debug('Will use ScrapingResultSet id %s', our_set.id)
        return [scraping_result for scraping_result in our_set.fetch_entries() if \
                scraping_result.tag in tag_list]

    def extract_using_store_xpaths(self, product, tag_list=['name', 'img', 'price'],
            quit_driver=True, set_description='__included__'):
        assert product.store, 'No Store set for product'
        results = self._scraping_results_models_from_set(product.brand, tag_list, set_description)
        return self._do_extract(product, tag_list, quit_driver, results, perform_clicking=False)

    def _extraction_result_good_enough(self, res, tag_list):
        return all(tag in res for tag in tag_list)

    def extract_from_url(self, url, tag_list=['name', 'img', 'price'], quit_driver=True):
        product = get_or_create_product(url)
        store_sets = product.brand.scrapingresultset_set.all() if product.brand else []
        for srs in store_sets:
            sresults = srs.fetch_entries()
            res = self._do_extract(product, tag_list, quit_driver, sresults, perform_clicking=False)
            log.debug('Extraction from %s using %s gave %s', url, srs, res)
            if self._extraction_result_good_enough(res, tag_list):
                log.debug('Result is good enough, returning it')
                return res
            else:
                log.debug('Result is not good enough')
        log.debug('No available set of results for a store where suitable, computing new')
        fresh_res = self.extract_using_computed_xpaths(product, tag_list, quit_driver,
                set_description=None)
        log.debug('Fresh result: %s', fresh_res)
        if self._extraction_result_good_enough(fresh_res, tag_list):
            log.debug('Promoting xpaths computed for this product to Store xpaths')
            save_xpaths_for_store(product, description=product.prod_url)
        else:
            log.debug('Results are not good enough for promotion to Store xpaths')
        return fresh_res


def save_xpaths_for_store(product, description):
    assert product.scrapingresult_set.exists(), 'No results computed for product %s' % product
    product.brand = models.get_or_create_brand(product.prod_url)
    product.save()
    result_set = models.ScrapingResultSet(brand=product.brand, description=description)
    result_set.save()
    for scraping_result in product.scrapingresult_set.all().order_by('id'):
        set_entry = models.ScrapingResultSetEntry(scraping_result_set=result_set,
                scraping_result=scraping_result)
        set_entry.save()
    return result_set

def include_xpaths_for_store(product, description='__included__'):
    if not product.scrapingresult_set.exists():
        log.warn('No results computed for product %s' % product)
        return
    product.brand = models.get_or_create_brand(product.prod_url)
    product.save()
    result_set, created = models.ScrapingResultSet.objects.get_or_create(
            brand=product.brand,
            description=description)
    present_entries = result_set.scrapingresultsetentry_set.all().select_related()
    present_values = {entry.scraping_result.get_values_as_tuple(): entry for entry in present_entries}
    #log.debug('present_values: %s', present_values)
    for scraping_result in product.scrapingresult_set.all().order_by('id'):
        entry = present_values.get(scraping_result.get_values_as_tuple())
        if entry is not None:
            if entry.product_model is None:
                log.warn('Old set entry without ProductModel, setting')
                entry.product_model = product
            entry.entry_count = F('entry_count') + 1
            entry.save()
            continue

        # Deep copy scraping result, dropping relationship to the specific Product
        scraping_result_copy = models.ScrapingResult(product_model=None,
                flag=scraping_result.flag, tag=scraping_result.tag, created=scraping_result.created)
        scraping_result_copy.save()
        for xpe in scraping_result.fetch_xpath_exprs():
            xpe_copy = models.XPathExpr(scraping_result=scraping_result_copy,
                    list_index=xpe.list_index, expr=xpe.expr)
            xpe_copy.save()

        set_entry = models.ScrapingResultSetEntry(scraping_result_set=result_set,
                                                  scraping_result=scraping_result_copy,
                                                  product_model=product)
        set_entry.save()

