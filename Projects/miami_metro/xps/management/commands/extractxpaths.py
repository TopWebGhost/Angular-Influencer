from optparse import make_option
from collections import defaultdict
import datetime
import logging
import os.path
import os
import multiprocessing
import multiprocessing.pool
import threading
import sys
import pprint
import copy
import pyvirtualdisplay

from django.core.management.base import BaseCommand
from django.conf import settings

from xpathscraper import seleniumtools 
from xpathscraper import utils
from xpathscraper import textutils
from xpathscraper import scrapingresults

from xps import models
from xps import extractor
from xps.testdata import valid_elements as valid_from_module
from xps.testdata import valid_from_spreadsheet

from debra.models import ProductModel

# Tags for which all values in a valid list must be returned by a scraper, not one of them
REQUIRE_ALL_VALID = ['price', 'size', 'color']

REQUIRE_NO_ADDITIONAL = ['size', 'color']


parent_log = logging.getLogger('extractxpaths.parent')
child_log = logging.getLogger('extractxpaths.child')

LOG_DIR = os.path.join(settings.PROJECT_PATH, 'xps/testlogs')
LATEST_LINK = os.path.join(LOG_DIR, 'latest')


class Command(BaseCommand):
    TAG_LIST = ['name', 'img', 'price', 'size', 'color', 'sizetype', 'inseam']
    #TAG_LIST = ['name', 'img', 'price', 'size', 'color']
    #TAG_LIST = ['name', 'img', 'price']

    args = '<product_id1:root_el_xpath1> <product_id2:root_el_xpath2> ... (root_el_xpath part is optional) OR a single string <all> for all product ids for which test data is defined.'
    help = '''Calculates xpath expressions for the given products. Deletes old xpath expressions.
Tests if the computed xpaths evaluate to correct elements if the --test option is given.'''
    option_list = BaseCommand.option_list + (
            make_option('--ds',
                dest='ds',
                default='m',
                help='Datasource - "s" for spreadsheet and "m" for the Python module'),
            make_option('--test',
                action='store_true',
                dest='do_test',
                default=True,
                help='Test if XPath expressions evaluate to correct elements'),
            make_option('--concurrency',
                dest='concurrency',
                default='1',
                help='Concurrency level - how many parallell browsers to use for testing'),
            make_option('--notdefined',
                action='store_true',
                dest='do_notdefined',
                default=False,
                help='Select also product ids that have no test data'),
            make_option('--invalidpages',
                action='store_true',
                dest='do_invalidpages',
                default=False,
                help='Select INVALID_PRODUCT_PAGES as "all"'),
            make_option('--includedset',
                action='store_true',
                dest='do_includedset',
                default=False,
                help='Use __included__ set of expressions for extracting results, instead of computing new'),
            make_option('--withtagsdefined',
                dest='do_withtagsdefined',
                default=None,
                help='Select only products that have test data defined for the specified tags'),
            make_option('--clicking',
                action='store_true',
                dest='do_clicking',
                default=False,
                help='Perform clicking and test clicking results validity'),
            make_option('--clickingonly',
                action='store_true',
                dest='do_clickingonly',
                default=False,
                help='Test clicking results only, for products that have click test data'),
            make_option('--sample',
                action='store_true',
                dest='do_sample',
                default=False,
                help='Take only a sample of up to 2 products for each brand for the spreadsheet data'),
            make_option('--headless',
                action='store_true',
                dest='do_headless',
                default=False,
                help='Use headless display'),
            )

    def _extract_exprs(self, driver, product, root_el_xpath):
        ext = extractor.Extractor(driver=driver, headless_display=self.do_headless, reuse_xbrowser=False)
        if self.do_includedset:
            assert product.brand, 'includedset option present but no brand set for a product id=%s' % \
                    product.id
            all_models = ext._scraping_results_models_from_set(product.brand, self.TAG_LIST,
                    '__included__')
            # Recreate _wrapped attribute
            for m in all_models:
                m._wrapped = models.create_wrapped_scraping_result(m)
            # We need a browser window to evaluate results
            ext._create_scraper(product)
        else:
            all_models = ext._compute_scraping_results_models(product, self.TAG_LIST)

        # Log enriched results
        enriched = ext._do_extract(product, self.TAG_LIST, False, all_models)
        child_log.info('Enriched: %s', enriched)

        if self.do_test:
            child_log.info('Testing validity')
            if not self.do_clickingonly:
                self._test_page_validity(ext.scraper, product, all_models)
                self._test_xpaths(ext.scraper, product, all_models)
            if self.do_clicking:
                self._test_clicking_results(enriched.clicking_results, product)
        else:
            child_log.info('Not testing validity')

        child_log.debug('Product %s %s', product.id, product.prod_url)
        child_log.debug('Test data: %s', self._out_test_data(ext.scraper, all_models, product))

    def _test_clicking_results(self, clicking_results, product):
        valid_results = self.valid_elements.CLICKING_RESULTS.get(product.id)
        if not valid_results:
            child_log.warn('??? No clicking test data for product.id=%s', product.id)
            if clicking_results:
                self.tests_unknown['_clicking'] += 1
            return
        child_log.info('clicking_results=%s', pprint.pformat(clicking_results))
        child_log.info('valid_results=%s', pprint.pformat(valid_results))

        def is_clicking_dict_good_enough(res_d):
            res_d = copy.deepcopy(res_d)
            if res_d in valid_results:
                return True
            if 'checkoutprice' in res_d:
                del res_d['checkoutprice']
                if res_d in valid_results:
                    return True
            if not res_d.get('colordata'):
                return False
            if res_d['colordata'][0].get('name') and res_d['colordata'][0].get('swatch_image'):
                if any(d.get('colordata') and d['colordata'][0]['name'] == \
                            res_d['colordata'][0]['name'] and
                        d['colordata'][0].get('product_image') == \
                                res_d['colordata'][0].get('product_image') \
                        for d in valid_results):
                    return True
            child_log.warn('Dict is not good enough to be valid: %s', res_d)
            return False

        valid = all(is_clicking_dict_good_enough(res_d) for res_d in clicking_results)
        if valid:
            self.tests_passed['_clicking'] += 1
            child_log.warn('+++ Valid clicking result (%s dicts)' % len(clicking_results))
        else:
            self.tests_failed['_clicking'] += 1
            child_log.warn('--- Invalid clicking result:\n%s\nShould be:\n%s',
                    pprint.pformat(clicking_results), pprint.pformat(valid_results))
            self.products_failed['_clicking'].append(product.id)
        utils.pickle_to_file('/tmp/clicking_results.pickle', clicking_results)

    def _test_page_validity(self, scraper, product, scraping_results):
        valid = scraper.current_page_is_valid_product_page()
        should_be = False if product.id in self.valid_elements.INVALID_PRODUCT_PAGES else True
        child_log.info('Tested page validity: %s, should be: %s', valid, should_be)
        if valid == should_be:
            self.tests_passed['_validpage'] += 1
        else:
            self.tests_failed['_validpage'] += 1
            self.products_failed['_validpage'].append(product.id)

        not_found = scraper.current_page_is_not_found_page()
        child_log.info('Tested if "not found" page: %s', not_found)

    def _test_xpaths(self, scraper, product, scraping_results):
        if product.id not in self.valid_elements.VALID_BY_PRODUCT_ID:
            child_log.warn('!!! No validity data for product.id=%s, cannot test' % product.id)
            return

        def eval_text_result(result):
            result_evaluator = scrapingresults.ResultEvaluator(scraper)
            orig_result = models.create_wrapped_scraping_result(result)
            value = result_evaluator.compute_values(orig_result, result.tag)
            return value

        def is_result_valid(result, valid_value):
            texts = [eval_text_result(result)]

            if result.tag == 'img':
                return any(utils.urls_equal(text.src, valid_value) for text in texts)

            if result.tag == 'name':
                try:
                    valid_value = valid_value.decode('utf-8')
                except UnicodeDecodeError:
                    pass
                def name_text_is_good(t):
                    if textutils.simplify_text(t) == textutils.simplify_text(valid_value):
                        return True
                    return False
                return any(name_text_is_good(text) for text in texts)

            if result.tag == 'price':
                def price_text_is_good(t):
                    def normalize_price(p):
                        return p.replace('$', '').\
                            replace('USD', '').\
                            replace(',', '').\
                            replace('.', '').\
                            strip()
                    vv = normalize_price(valid_value)
                    tv = normalize_price(t)
                    if not vv or not tv:
                        return False
                    if vv in tv or tv in vv:
                        return True
                    return False
                return any(text and price_text_is_good(text) for text in texts)

            def valid_value_in_text_word():
                for t in texts[0]:
                    t_words = textutils.split_en_words(t.lower())
                    v_words = textutils.split_en_words(valid_value.lower())
                    if set(v_words).issubset(set(t_words)):
                        return True
                return False

            if result.tag == 'size':
                return valid_value_in_text_word()

            if result.tag == 'color':
                return valid_value in texts[0]

            assert False, 'Unknown tag %s' % tag

        validated_by_tag = defaultdict(list)

        if self.do_includedset:
            scraping_results = [sr for sr in scraping_results if eval_text_result(sr) is not None]

        for scraping_result in scraping_results:
            tag = scraping_result.tag
            possible_valid_values = self.valid_elements.VALID_BY_PRODUCT_ID[product.id].get(tag, [])
            text_value = eval_text_result(scraping_result)
            if not possible_valid_values:
                child_log.warn('??? No validity data for result %r text_value %r' % \
                        (scraping_result, text_value))
                self.tests_unknown[tag] += 1
                self.products_unknown[tag].append(product.id)
            else:
                validated = [vv for vv in possible_valid_values if is_result_valid(
                    scraping_result, vv)]
                validated_by_tag[tag].extend(validated)
                if validated:
                    child_log.warn('+++ Valid result %r text_value %r values=[%s]' % \
                        (scraping_result, text_value, validated))
                    self.tests_passed[tag] += 1
                else:
                    child_log.warn('--- Invalid result %r text value %r valid values: %s' % \
                            (scraping_result, text_value, possible_valid_values))
                    self.tests_failed[tag] += 1
                    self.products_failed[tag].append(product.id)

        # For the spreadsheet data, we only have one image - patch the
        # current results that looked for multiple images
        if self.ds == 's' and validated_by_tag.get('img') and product.id in \
                self.products_failed['img']:
            len_before = len(self.products_failed['img'])
            self.products_failed['img'] = [x for x in self.products_failed['img'] \
                                           if x != product.id]
            len_after = len(self.products_failed['img'])
            self.tests_failed['img'] -= len_before - len_after

        for tag in REQUIRE_ALL_VALID:
            possible = self.valid_elements.VALID_BY_PRODUCT_ID[product.id].get(tag, [])
            actual = validated_by_tag[tag]
            for value in set(possible) - set(actual):
                child_log.warn('-*- Required value <%s> tag %s not returned by scraper' % \
                        (value, tag))
                self.tests_missing[tag] += 1
                self.products_missing[tag].append(product.id)

        for tag in REQUIRE_NO_ADDITIONAL:
            possible = self.valid_elements.VALID_BY_PRODUCT_ID[product.id].get(tag, [])
            actual = validated_by_tag[tag]
            for value in set(actual) - set(possible):
                child_log.warn('-|- Returned value <%s> tag %s not listed as valid' % \
                        (value, tag))
                self.tests_failed[tag] += 1
                self.products_failed[tag].append(product.id)



    def _out_test_data(self, scraper, sresults, product):
        if not sresults:
            child_log.error('No scraping results to print test data')
            return ''
        sres_by_tag = defaultdict(list)
        for sr in sresults:
            sres_by_tag[sr.tag].append(sr)

        if len(sres_by_tag['name']) > 0:
            name_repr = repr(sres_by_tag['name'][0]._wrapped._evals_joined(' '))
        else:
            name_repr = ''

        if len(sres_by_tag['img']) > 0:
            img_repr = repr(sres_by_tag['img'][0]._wrapped._evals_joined(' '))
        else:
            img_repr = ''

        if len(sres_by_tag['size']) > 0:
            result_evaluator = scrapingresults.ResultEvaluator(scraper)
            res = result_evaluator.compute_values(sres_by_tag['size'][0]._wrapped, 'size')
            size_repr = repr(res)
        else:
            size_repr = '[]'

        if len(sres_by_tag['color']) > 0:
            result_evaluator = scrapingresults.ResultEvaluator(scraper)
            res = result_evaluator.compute_values(sres_by_tag['color'][0]._wrapped, 'color')
            color_repr = repr(res)
        else:
            color_repr = '[]'

        data_entry = '''
    {product_id}: dict(
            name=[{name_repr}],
            img=[{img_repr}],
            price={price_list_repr},
            size={size_repr},
            color={color_repr},
    ),
        '''.format(product_id=product.id,
                name_repr=name_repr,
                img_repr=img_repr,
                price_list_repr=repr([sr._wrapped._evals_joined(' ') for sr in sres_by_tag['price']]),
                size_repr=size_repr,
                color_repr=color_repr,
                )
        return data_entry

    def _setuplog(self, l, hdlr_list, level):
        assert isinstance(hdlr_list, list)
        for hdlr in hdlr_list:
            l.addHandler(hdlr)
        l.setLevel(level)

    def _configure_child_logging(self, product):
        self.tlocal.product_id = product.id
        self.tlocal.child_log_filename = os.path.join(self.run_dir, '%03d.log' % int(product.id))
        parent_log.warn('Processing %s %s %s', product.id, product.prod_url,
                self.tlocal.child_log_filename)
        self.tlocal.child_log_hdlr = logging.FileHandler(self.tlocal.child_log_filename)
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        self.tlocal.child_log_hdlr.setFormatter(formatter)
        
    def _finish_child_logging(self):
        pass

    def _configure_parent_logging(self, child_to_stdout):
        global parent_log
        datestr = datetime.datetime.utcnow().strftime('%y%m%d.%H%M%S')
        self.run_dir = os.path.join(LOG_DIR, datestr)
        os.mkdir(self.run_dir)

        if os.path.exists(LATEST_LINK):
            os.unlink(LATEST_LINK)
        os.symlink(self.run_dir, LATEST_LINK)

        parent_log_filename = os.path.join(self.run_dir, 'main.log')
        self.stdout.write('Parent log: %s\n' % parent_log_filename)
        hdlr = logging.FileHandler(parent_log_filename)
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)

        self._setuplog(parent_log, [hdlr], logging.DEBUG)

        self.stdout_hdlr = logging.StreamHandler(sys.stdout)
        self.stdout_hdlr.setLevel(logging.DEBUG)
        self.stdout_hdlr.setFormatter(formatter)
        parent_log.addHandler(self.stdout_hdlr)

        null_handler = logging.NullHandler()
        def handler_for_current_thread():
            if hasattr(self.tlocal, 'child_log_hdlr'):
                return self.tlocal.child_log_hdlr
            return null_handler

        child_handler_proxy = utils.LocalProxy(handler_for_current_thread)
        child_handlers = [child_handler_proxy]
        if child_to_stdout:
            child_handlers.append(self.stdout_hdlr)
        self._setuplog(child_log, child_handlers, logging.DEBUG)
        #self._setuplog(logging.getLogger(''), child_handlers, logging.INFO)
        self._setuplog(logging.getLogger('xps'), child_handlers, logging.DEBUG)
        self._setuplog(logging.getLogger('xpathscraper'), child_handlers, logging.DEBUG)

    def _setup_child(self):
        pass
        #connection.close()

    def _child_job(self, (product, root_el_xpath, close_driver)):
        try:
            self._configure_child_logging(product)
            child_log.info('Product %s <%s>' % (product.id, product.prod_url))
            driver = seleniumtools.create_default_driver()
            self._extract_exprs(driver, product, root_el_xpath)
            if close_driver:
                driver.quit()
            parent_log.warn('Finished processing %s %s', product.id, product.prod_url)
        except:
            parent_log.exception('Child exception, logfile %s', self.tlocal.child_log_filename)
            child_log.exception('Processing exception')
        finally:
            self._finish_child_logging()

    def handle(self, *args, **kwargs):
        self.ds = kwargs.get('ds', 'm')
        self.do_test = kwargs.get('do_test')
        self.do_notdefined = kwargs['do_notdefined']
        self.do_invalidpages = kwargs['do_invalidpages']
        self.do_includedset = kwargs['do_includedset']
        self.do_withtagsdefined = kwargs['do_withtagsdefined']
        self.do_clickingonly = kwargs['do_clickingonly']
        self.do_clicking = kwargs['do_clicking'] or self.do_clickingonly
        self.do_sample = kwargs['do_sample']
        self.do_headless = kwargs['do_headless']

        self.withtags = self.do_withtagsdefined.split(',') if self.do_withtagsdefined else None
        self.concurrency = int(kwargs['concurrency'])
        self.tlocal = threading.local()

        if self.do_notdefined and self.do_withtagsdefined:
            assert False, 'Options not compatible: notdefined, withtagsdefined'

        if self.ds == 'm':
            self.valid_elements = valid_from_module
        elif self.ds == 's':
            self.valid_elements = valid_from_spreadsheet.ProductSpreadsheetData(self.do_sample)
        else:
            assert False, 'Invalid datasource spec: %r' % self.ds

        # Number of tests passed/failed/unknown by tag
        self.tests_passed = defaultdict(int)
        self.tests_failed = defaultdict(int)
        self.tests_unknown = defaultdict(int)
        self.tests_missing = defaultdict(int)

        self.products_failed = defaultdict(list)
        self.products_unknown = defaultdict(list)
        self.products_missing = defaultdict(list)

        def split_spec(spec):
            if ':' not in spec:
                return int(spec), None
            fst, snd = spec.split(':', 1)
            return (int(fst), snd)

        # Create `data` list of (product_id, root_el) tuples
        if args and not (args[0][0].isdigit() or args[0][0] == '-'):
            if self.do_notdefined:
                # TODO
                #existing_ids = [product.id for product in Product.objects.all().order_by('id')]
                existing_ids = sorted(self.valid_elements.VALID_BY_PRODUCT_ID.keys())
            elif self.do_invalidpages:
                existing_ids = self.valid_elements.INVALID_PRODUCT_PAGES[:]
            else:
                existing_ids = sorted(self.valid_elements.VALID_BY_PRODUCT_ID.keys())
            arg = args[0]
            if arg == 'all':
                pred = lambda id: True
            elif arg.startswith('lambda'):
                pred = eval(arg)
            else:
                assert False, 'Unknown id definition %s' % args[0]
            used_ids = [id for id in existing_ids if pred(id)]
            data = zip(used_ids, [None] * len(used_ids))
        else:
            data = [split_spec(spec) for spec in args]

        # Filter out products that don't have needed test data
        if self.withtags:
            filtered_data = []
            for (product_id, spec2) in data:
                if all(self.valid_elements.VALID_BY_PRODUCT_ID[product_id].get(tag) is not None \
                        for tag in self.withtags):
                    filtered_data.append((product_id, spec2))
            data = filtered_data

        # Filter out products that don't have clicking results data defined
        if self.do_clickingonly:
            data = [(product_id, spec2) for (product_id, spec2) in data if product_id in \
                    self.valid_elements.CLICKING_RESULTS]

        used_ids = [d[0] for d in data]

        self._configure_parent_logging(len(data) == 1)

        parent_log.info('Using %d ids: %s' % (len(used_ids), used_ids))

        self.display = None
        if self.do_headless:
            self.display = pyvirtualdisplay.Display(visible=0, size=(1200, 800))
            self.display.start()

        # Run tests in child threads
        close_driver = len(data) > 1
        child_data = [(ProductModel.objects.get(id=int(product_id)), root_el_xpath, close_driver) \
                for product_id, root_el_xpath in data]
        parent_log.info('Starting tests')

        if len(child_data) == 1:
            self._child_job(child_data[0])
        else:
            pool = multiprocessing.pool.ThreadPool(processes=self.concurrency,
                    initializer=self._setup_child)
            pool.map(self._child_job, child_data, chunksize=1)

        if self.do_test:
            parent_log.info('Tested %d products', len(child_data))
            ds = ['tests_passed', 'tests_failed', 'tests_missing', 'tests_unknown']
            all_summed = sum(sum(getattr(self, s).values()) for s in ds)
            if all_summed > 0:
                def outinfo(attr):
                    d = getattr(self, attr)
                    d_sum = sum(d.values())
                    d_percent = int(round( float(d_sum * 100) / float(all_summed) ))
                    parent_log.info('Results: %s: %d (%d%%) %s' % (attr, d_sum, d_percent, dict(d)))
                for s in ds:
                    outinfo(s)

            # sort products_* dictionaries
            for d in [self.products_failed, self.products_missing, self.products_unknown]:
                for k in d:
                    d[k].sort()

            parent_log.info('products_failed: %s', dict(self.products_failed))
            parent_log.info('products_missing: %s', dict(self.products_missing))
            parent_log.info('products_unknown: %s', dict(self.products_unknown))

        parent_log.info('Finished tests %s', self.run_dir)

        if self.display is not None:
            self.display.stop()

