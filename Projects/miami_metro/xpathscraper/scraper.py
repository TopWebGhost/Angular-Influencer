# -*- coding: utf-8 -*-
from __future__ import division

import re
import sys
from collections import namedtuple, defaultdict, OrderedDict
from urlparse import urlsplit
import logging
import time
import copy
import pprint
import heapq

import baker
from django.conf import settings
from boto.s3.connection import S3Connection
from boto.exception import BotoServerError
import selenium.common.exceptions

from . import xbrowser
from .xbrowser import ElText
from . import seleniumtools
from . import utils
from . import textutils
from .utils import avg


log = logging.getLogger('xpathscraper.scraper')


IMG_MAX_ASPECT_RATIO = 4.0
IMG_MIN_ASPECT_RATIO = 0.1
S3_CANVAS_IMGS_BUCKET = 'product-images-from-canvas'
S3_CANVAS_IMG_URL_EXPIRES = 86400 * 100

MAX_NAME_EL_CANDIDATES = 100
TITLE_WORDS_TO_DISCARD = ['product', 'detail', 'us', 's', 'join', 'welcome', 'to']
INVALID_NAME_TAGS= ['script', 'title', 'meta']
INVALID_NAME_PARENT_TAGS = []
INVALID_NAME_ANCESTOR_NAMES = []
EL_MAX_TEXT_LENGTH = 150

EL_MAX_Y = 700

INVALID_PRICE_TAGS = ['script', 'title', 'meta']
INVALID_PRICE_FRAGMENTS_SUBSTRINGS = ['%']
MAX_PXDIST_PRICE_FROM_BEST = 100

SIZE_CLUSTERING_DISTANCES = [0, 1, 2, 5, 8, 12, 16, 20, 30, 40, 50, 60, 70, 80]
COLOR_CLUSTERING_DISTANCES = SIZE_CLUSTERING_DISTANCES

COMMON_XPATH_COMPUTATION_SKIP_TRIES = [0, 1, 2, 3]

COLOR_NOISE_WORDS_WHITELIST = ['&', 'and', 'or', 'color', 'colour', 'suede', 'motif', 'busted',
    'bright', 'light', 'dark', 'heather', 'hthr', 'gamma', 'hyper', 'sail']

SLEEP_BETWEEN_CLICKS = 2

#SAFE_TO_CLICK = ['jcrew.com', 'gap.com', 'amazon.com', 'express.com', 'anthropologie.com']
SAFE_TO_CLICK = []
#SAFE_TO_CLICK = ['jcrew.com']
#CHECK_SAFE_TO_CLICK_DOMAINS = (not settings.DEBUG)
CHECK_SAFE_TO_CLICK_DOMAINS = True
LIMIT_SIZE_CLICKS = None
LIMIT_PATHS = None

GOTO_CART = True
#GOTO_CART = False
TRY_REDUCE_XPATHS = False


RESULTDESC_PRICE_RANGE = 'PRICE_RANGE'
RESULTDESC_DOLLARS_AND_CENTS = 'DOLLARS_AND_CENTS'
RESULTDESC_NAME_COMBINED = 'NAME_COMBINED'


class ScrapingResult(object):
    """Result of a scraping is a list of XPath expressions,
    together with an optional RESULTDESC_* flag and a dictionary
    mapping XPath expressions to evaluated text content (optional - for debugging).
    Alternatively, a result may be directly represented as a json-serializable
    ``value`` object or ``rich_value`` (which can be any Python object).

    ``extra_data`` is a dictionary with additional description of a scraping result for
    validation and debugging purposes. Results for ``img`` tag can contain an entry under
    ``size`` key, which is a dictionary with optional ``size``, ``width`` and ``height``
    entries.
    """

    def __init__(self, xpath_expr_list=[], flag=None, xpath_evals=dict(), value=None, rich_value=None,
                 extra_data={}):
        assert isinstance(xpath_expr_list, (list, tuple))
        assert xpath_expr_list or value is not None or rich_value is not None, 'empty ScrapingResult'
        self.xpath_expr_list = xpath_expr_list
        self.flag = flag
        self.xpath_evals = xpath_evals
        self.value = value
        self.rich_value = rich_value
        self.extra_data = extra_data

    def _evals_joined(self, sep=' || '):
        return sep.join('%s' % self.xpath_evals[expr] for expr in self.xpath_expr_list \
                if expr in self.xpath_evals)

    def _key(self):
        return utils.make_hashable((self.xpath_expr_list or [], self.flag, self.value))

    def __cmp__(self, other):
        return cmp(self._key(), other._key())

    def __hash__(self):
        return hash(self._key())

    def __str__(self):
        return 'ScrapingResult({self.xpath_expr_list!r}, flag={self.flag}, evals={evals!r}, value={self.value!r}, rich_value={self.rich_value!r}, extra_data={self.extra_data!r})'.\
            format(self=self, evals=self._evals_joined())
    __repr__ = __str__


class ScraperException(Exception): pass


# To help readability, we use named tuples instead
# of raw tuples that support numeric indexing only
EtScore = namedtuple('EtScore', ['el_text', 'score'])
NameScore = namedtuple('NameScore', ['text_score', 'font_score'])
CombinationScore = namedtuple('CombinationScore', ['combination', 'c_score'])
EltDistance = namedtuple('EltDistance', ['el_text', 'distance'])
ElSResult = namedtuple('ElSResult', ['el', 'scraping_result'])

TagXPathValue = namedtuple('TagXPathValue', ['tag', 'xpath', 'value'])

# Add __hash__ to a tuple of distance and elements with text (a cluster)
class DistCluster(namedtuple('DistCluster', ['dist', 'et_cluster'])):
    def __hash__(self):
        return hash((self.dist, tuple(self.et_cluster)))


class Scraper(object):
    """Extracts xpaths for relevant attributes from the product page.

    :param xbrowser: a XBrowser object with loaded page
    :param op_recorder: ``None`` or a callable accepting ``domain_name, operation_name,
        operation_status, status_message`` arguments for recording information
        for monitoring/statistic purposes.
    """

    def __init__(self, xbrowser, op_recorder=None):
        self.xbrowser = xbrowser
        self._op_recorder = op_recorder

        self._inital_cookies = self.xbrowser.driver.get_cookies()

        # Process title
        log.debug('Computing title data')
        self._compute_title_words()
        self._check_if_title_meaningful()
        log.debug('Done')

        # Dictionaries for storing size/color elements/clusters
        # Keys are tags (size/color for now), values are ElText/DistCluster lists
        self._candidates = {}
        self._dists_clusters = {}
        self._best_cluster = {}

        self._init_colors_data()

        # A list of dictionaries with results (keys are tags) computed for an individual
        # static page shown after clicking an element.
        self._click_results = None

        # Maps tags to xpaths of first result el.
        self._first_el_xpath = {}

        # Maps tags to a list of all xpaths
        self._all_xpaths = {}

    def _record(self, op, status=None, msg=None):
        if not self._op_recorder:
            return
        domain = utils.domain_from_url(self.xbrowser.driver.current_url)
        log.warn('Recording for domain %s: op=%s status=%s msg=%s', domain, op, status, msg)
        self._op_recorder(domain, op, status, msg)

    def get_xpaths(self, tag, *args, **kwargs):
        """Compute scraping results, as a list of :class:`ScrapingResult` objects, for a
        specified tag, passing optional `args` and `kwargs`.
        """
        method = getattr(self, 'get_{tag}_xpaths'.format(tag=tag))
        return method(*args, **kwargs)

    @property
    def driver(self):
        """Selenium driver instance used by this scraper.
        """
        return self.xbrowser.driver

    @property
    def url(self):
        """Current url.
        """
        return self.xbrowser.url

    def quit_driver(self):
        """Quit and clean used :class:`xbrowser.XBrowser` instance.
        """
        if self.xbrowser:
            self.xbrowser.quit_driver()

    def _compute_title_words(self):
        words = textutils.simple_words(self.driver.title)
        # Don't include words from domain name
        self.domain = urlsplit(self.url).netloc.lower()
        self.domain_words = textutils.simple_words(self.domain)
        self.title_words = [w for w in words if w not in self.domain and \
                w not in TITLE_WORDS_TO_DISCARD]

    def _in_url(self, word):
        return word in textutils.split_words(self.url)


    ### addtocart

    def _total_addtocart_score(self, xpath_attr):
        return self._attrs_matching_score(xpath_attr,
                self._default_word_weights(xbrowser.jsonData['add_to_cart_words']),
                self._CHECKOUT_ATTR_SCORE)

    _regexps_add_to_cart = map(re.compile, [
        r'add.*cart',
        r'add.*bag',
        r'add.*basket',
        r'add.*tote',
        r'add.*wish.*list',
    ])
    def get_addtocart_xpaths(self):
        """Compute results for addtocart.
        """
        xpaths_attrs = self.xbrowser.execute_jsfun('_XC.findAddToCartXPathCandidates')
        #log.info('addtocart xpaths_attrs: %s', xpaths_attrs)
        if not xpaths_attrs:
            log.warn('no xpaths_attrs for addtocart')
            return []

        xpathsattrs_scores = [(xpath_attr, self._total_addtocart_score(xpath_attr)) \
                for xpath_attr in xpaths_attrs]

        xpathsattrs_scores.sort(key=lambda (xpath_attr, score): score, reverse=True)
        log.debug('addtocart xpaths_scores: %s', xpathsattrs_scores)

        first_xpath = xpathsattrs_scores[0][0][0]
        self._first_el_xpath['addtocart'] = first_xpath
        return [ScrapingResult([first_xpath])]

    def _add_to_cart_button_present(self):
        return bool(self.get_addtocart_xpaths())


    ### page validity

    _patterns_not_found = map(re.compile, [
        r'oops',
        r'yikes',
        r'page.*not?.*found',
        r'page.*not?.*available',
        r'(product|item).*(no)?t?.*(un)?available',
        r'sorry.*(product|item|page)',
        #r'(product|item).*sold.*out',
        r'sold.*out',
        r'sorry.*(!)?.*(out|stock)',
        r'out.*of.*stock',
    ])
    def _not_found_text_present(self):
        els_texts = self.xbrowser.els_with_texts(['script'], [], max_text_length=200, max_y=700,
                include_attr_values=['alt', 'src', 'id'])
        for el_text in els_texts:
            for pattern in self._patterns_not_found:
                if pattern.search(el_text.text.lower()):
                    log.debug('Element text <%s> matched pattern <%s>, '
                            'current page contains "not found" text',
                            el_text.text.lower(), pattern.pattern)
                    return True
        log.debug('Current page does not contain "not found" text')
        return False


    def current_page_is_valid_product_page(self):
        """Tells if a loaded page contains product information (name and price
        at least).
        """
        return self._add_to_cart_button_present()

    def current_page_is_not_found_page(self):
        """Tells if a loaded page is a "not found" page (doesn't contain
        any product data - not even a product name).
        """
        return self._not_found_text_present()


    ### img

    def get_img_xpaths(self, _img_kind='default'):
        """Compute results for img.
        """
        all_imgs = self.xbrowser.execute_jsfun('_XPS.imageLikeElements')
        all_imgs_with_sizes = [(el.get_attribute('src'), self.xbrowser.el_size(el)) for el in all_imgs]
        all_imgs_with_sizes.sort(key=lambda x: x[1], reverse=True)
        log.debug('all_imgs_with_sizes: %s', pprint.pformat(all_imgs_with_sizes))
        close_enough_els = self.xbrowser.execute_jsfun(
                '_XPS.elsCloserThan', 500, self.first_el('name'), all_imgs)
        log.debug('%s close enough img els', len(close_enough_els))

        imgs = []
        for img in close_enough_els:
            try:
                src = img.get_attribute('src') or ''
                if utils.url_path_endswith(src, ('.png', '.gif', '.svg')):
                    continue

                aspect_ratio = self.xbrowser.execute_jsfun('_XPS.aspectRatio', img)
                if aspect_ratio != 0 and not \
                    (IMG_MIN_ASPECT_RATIO < aspect_ratio < IMG_MAX_ASPECT_RATIO):
                    log.debug('Skipping image <%s> with aspect ratio %s', src, aspect_ratio)
                    continue

                valid_pos_below = self.xbrowser.execute_jsfun_safe(False,
                        '_XPS.elBelowTopOfOtherEl', img, self.first_el('name'))
                if not valid_pos_below:
                    log.debug('img has invalid position below: %s', src)
                    continue
                log.debug('img has valid position below: %s', src)

                valid_pos_nextto = self.xbrowser.execute_jsfun_safe(False,
                        '_XPS.elNextToOtherEl', img, self.first_el('name'), 40)
                valid_pos_directly_below = self.xbrowser.execute_jsfun_safe(False,
                        '_XPS.elDirectlyBelowOtherEl', img, self.first_el('name'), 150)
                if valid_pos_nextto:
                    log.debug('img has valid_pos_nextto: %s', src)
                elif valid_pos_directly_below:
                    log.debug('img has valid_pos_directly_below: %s', src)
                else:
                    log.debug('invalid img position: %s', src)
                    continue

            except selenium.common.exceptions.StaleElementReferenceException:
                continue

            imgs.append(img)

        if not imgs:
            self._record('get_img_xpaths', 'notfound')
            return []
        imgs_with_sizes = [(el, self.xbrowser.el_size(el)) for el in imgs]
        if log.isEnabledFor(logging.DEBUG):
            log.debug('imgs_with_sizes before sorting: %s',
                      [(e.get_attribute('src'), s) for e, s in imgs_with_sizes])
        imgs_with_sizes.sort(key=lambda (el, size): -size)
        if log.isEnabledFor(logging.DEBUG):
            log.debug('imgs_with_sizes after sorting: %s',
                      [(e.get_attribute('src'), s) for e, s in imgs_with_sizes])
        biggest_img = imgs_with_sizes[0][0]
        biggest_size = imgs_with_sizes[0][1]

        big_imgs = [biggest_img] + [img for img in all_imgs \
                                    if self.xbrowser.el_size(img) == biggest_size \
                                    and img != biggest_img]
        log.debug('big images with max size: %s', [img.get_attribute('src') \
                                                         for img in big_imgs])

        exprs = [self.xbrowser.compute_xpath(img) for img in big_imgs]
        if not exprs or all(e is None for e in exprs):
            log.warn('img expr evaluated to None! Returning nothing')
            self._record('get_img_xpaths', 'evalerror')
            return []
        self._first_el_xpath['img'] = filter(None, exprs)[0]

        srcs = [img.get_attribute('src') for img in big_imgs]
        new_srcs = []
        for src, img in zip(srcs, big_imgs):
            if src is not None and src in new_srcs:
                new_srcs.append(None)
            elif not src and img.tag_name.lower() == 'canvas':
                try:
                    new_srcs.append(self._upload_img_from_canvas(biggest_img, _img_kind))
                except BotoServerError:
                    log.exception('Boto exception while uploading images, skipping')
            else:
                new_srcs.append(src)

        self._record('get_img_xpaths', 'ok')

        from xpathscraper import resultsenrichment
        return [ScrapingResult([expr], None, {expr: src}, value=src,
                               rich_value=resultsenrichment.Image(src=src, size=biggest_size),
                               extra_data={'size': {'size': biggest_size}}) \
                for expr, src in zip(exprs, new_srcs) if expr and src]

    def _upload_img_from_canvas(self, biggest_img, kind):
        data_url = self.xbrowser.execute_jsfun('_XPS.canvasDataURL', biggest_img)
        image_data = data_url.split(',', 1)[1].decode('base64')
        s3conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
        bucket = s3conn.create_bucket(S3_CANVAS_IMGS_BUCKET)
        bucket.set_acl('public-read')
        key_name = self.url + ' ' + kind
        log.debug('S3 key_name: %s, bytes: %s', key_name, len(image_data))
        key = bucket.get_key(key_name)
        if key:
            log.debug('S3 key already exists, not uploading')
        else:
            log.debug('Creating new S3 key')
            key = bucket.new_key(key_name)
            key.set_contents_from_string(image_data)
        url = key.generate_url(S3_CANVAS_IMG_URL_EXPIRES)
        log.debug('Canvas img url: %s', url)
        self._record('canvas_upload', 'ok')
        return url


    ### name

    def _check_if_title_meaningful(self):
        self.title_meaningful = len(self.title_words) >= 2
        log.debug('Title <%s>, title words <%s>, meaningful: %s', self.driver.title,
                self.title_words, self.title_meaningful)

    def _name_text_score_usetitle(self, text):
        if not text:
            return 0.0
        if text.startswith(('http://', 'https://')):
            return 0.0
        words = textutils.simple_words(text)
        common_words = len(set(self.title_words) & set(words))
        nomin = float(common_words)
        denom = float(len(self.title_words) + len(words))
        if denom == 0:
            return 0.0
        res = nomin / denom

        if res > 0:
            log.debug('_name_text_score(%s, %s) = %s', text, self.title_words, res)
        return res

    def _name_text_score_notitle(self, text):
        if not text:
            return 0.0
        if any(w in text for w in ['http', '.com', 'co.uk']):
            return 0.0
        if any(w in text for w in self.domain_words if len(w) > 3):
            return 0.0
        words = textutils.simple_words(text)
        if len(words) == 0:
            return 0.0
        elif len(words) == 1:
            return 0.2
        elif len(words) in (2, 3, 4, 5):
            return 1.0
        elif len(words) < 10:
            return 0.5
        else:
            return 0.2

    def _name_text_score(self, *args, **kwargs):
        if self.title_meaningful:
            return self._name_text_score_usetitle(*args, **kwargs)
        return self._name_text_score_notitle(*args, **kwargs)

    def _scale_text_score(self, score):
        return float(score) / (1.0 - float(score))

    def _name_score_usetitle(self, el_text):
        text_score = self._name_text_score_usetitle(el_text.text)
        if (text_score == 0):
            # Do not fetch location to optimize speed when the score is 0
            return NameScore(text_score=0, font_score=0)
        font_size = self.xbrowser.el_font_size(el_text.el)
        importance = self.xbrowser.el_importance(el_text.el)
        final_score = self._scale_text_score(text_score) * min(font_size, 24.0) * importance
        return NameScore(text_score=final_score, font_score=(text_score, font_size, importance))

    def _name_score_notitle(self, el_text):
        text_score = self._name_text_score_notitle(el_text.text)
        if text_score == 0:
            # Do not fetch location to optimize speed when the score is 0
            return NameScore(text_score=0, font_score=0)
        font_size = self.xbrowser.el_font_size(el_text.el)
        importance = self.xbrowser.el_importance(el_text.el)
        final_score = text_score * min(font_size, 24.0) * importance
        return NameScore(text_score=final_score, font_score=(text_score, font_size, importance))

    def _name_score(self, *args, **kwargs):
        if self.title_meaningful:
            return self._name_score_usetitle(*args, **kwargs)
        return self._name_score_notitle(*args, **kwargs)

    def _name_combined_score_usetitle(self, combined):
        combined_text = ' '.join(el_text.text for el_text in combined)
        return self._name_score(ElText(combined[0].el, combined_text))

    def _name_combined_score_notitle(self, combined):
        combined_text = ' '.join(el_text.text for el_text in combined)
        text_score = self._name_text_score(combined_text)
        if text_score == 0:
            return NameScore(text_score=0, font_score=0)
        font_size = avg(self.xbrowser.el_font_size(combined[0].el),
                self.xbrowser.el_font_size(combined[1].el))
        importance = avg(self.xbrowser.el_importance(combined[0].el),
                self.xbrowser.el_importance(combined[1].el))
        final_score = text_score * min(font_size, 24) * importance
        return NameScore(text_score=final_score, font_score=(text_score, font_size, importance))

    def _name_combined_score(self, *args, **kwargs):
        if self.title_meaningful:
            return self._name_combined_score_usetitle(*args, **kwargs)
        return self._name_combined_score_notitle(*args, **kwargs)

    def get_name_xpaths(self):
        """Compute results for name.
        """
        blacklisted_rects = self.xbrowser.execute_jsfun('_XPS.horizontalLinksClustersRects')
        log.debug('get_name_xpaths: link clusters rects: %s', blacklisted_rects)
        log.debug('get_name_xpaths: Getting els with texts')
        candidate_els = self.xbrowser.els_with_texts(INVALID_NAME_TAGS, INVALID_NAME_PARENT_TAGS,
            EL_MAX_TEXT_LENGTH, invalid_ancestor_names=INVALID_NAME_ANCESTOR_NAMES)
        log.debug('get_name_xpaths: Got them: %s', len(candidate_els))
        candidate_els_raw = self.xbrowser.execute_jsfun('_XPS.elsOutsideRects',
                                                    [list(el_text) for el_text in candidate_els],
                                                    blacklisted_rects)
        candidate_els = self.xbrowser.enrich_els_texts(candidate_els_raw)
        log.debug('get_name_xpaths: After excluding cluster heights: %s', len(candidate_els))

        self.name_el_score = [EtScore(el_text, self._name_score(el_text)) for el_text in candidate_els]
        self.name_el_score = [et_score for et_score in self.name_el_score \
                if et_score.score.text_score > 0]
        if not self.name_el_score:
            self._record('get_name_xpaths', 'notfound', 'no el scored > 0')
            return []
        # get MAX_NAME_EL_CANDIDATES elements with the heighest score, but preserve initial ordering
        # to correctly join name elements
        self.name_el_score_enum = heapq.nlargest(MAX_NAME_EL_CANDIDATES, enumerate(self.name_el_score),
                                                 key=lambda (i, et_score): et_score.score)
        best_name_el_score = self.name_el_score_enum[0][1]
        self.name_el_score_enum.sort(key=lambda (i, et_score): i)
        self.name_el_score = [et_score for (i, et_score) in self.name_el_score_enum]
        log.debug('name_el_score (%d): %s', len(self.name_el_score), self.name_el_score)

        combined_els_texts_raw = self.xbrowser.execute_jsfun('_XPS.combineNameEls',
                                                             [list(et_score.el_text) \
                                                              for et_score in self.name_el_score])
        combined_els_score = []
        for combined_raw in combined_els_texts_raw:
            combined = self.xbrowser.enrich_els_texts(combined_raw)
            combined_els_score.append(CombinationScore(combined, self._name_combined_score(combined)))

        if combined_els_score:
            best_combined_els_score = max(combined_els_score,
                                          key=lambda combination_score: combination_score.c_score)
        else:
            best_combined_els_score = None
        log.debug('combined_els_score: %s', sorted(combined_els_score,
            key=lambda combination_score: combination_score.c_score, reverse=True))

        if best_combined_els_score and best_combined_els_score.c_score > best_name_el_score.score:
            log.debug('Using combined element as name result')
            best_combination = best_combined_els_score.combination
            self._first_el_xpath['name'] = self.xbrowser.compute_xpath(best_combination[0].el)
            exprs = [self.xbrowser.compute_xpath(element_text.el) for element_text in best_combination]
            exprs = [e for e in exprs if e is not None]
            res = ScrapingResult(exprs, RESULTDESC_NAME_COMBINED,
                    dict(zip(exprs, [element_text.text for element_text in best_combination])))
            self._record('get_name_xpaths', 'ok', 'combined')
            return [res]

        log.debug('Using a single element as name result')
        best_name_e_t = best_name_el_score.el_text
        self._first_el_xpath['name'] = self.xbrowser.compute_xpath(best_name_e_t.el)
        expr = self.xbrowser.compute_xpath(best_name_e_t.el)
        if expr is None:
            log.warn('The best element evaluated to None! Returning nothing')
            self._record('get_name_xpaths', 'evalerror')
            return []
        res = ScrapingResult([expr], None, {expr: best_name_e_t.text})
        self._record('get_name_xpaths', 'ok', 'single')
        return [res]

    def first_el_xpath(self, tag):
        """Returns first xpath for a given tag. Computes results for a given tag
        if they are not available.
        """
        if not self._first_el_xpath.get(tag):
            self.get_xpaths(tag)
        xpath = self._first_el_xpath.get(tag)
        if not xpath:
            return None
        return xpath

    def first_el(self, tag, fresh=False):
        """Evaluates xpath got from :meth:`first_el_xpath`.

        :param fresh: if `True`, recomputes results even if they are already available.
        """
        if fresh:
            self.get_xpaths(tag)
        xpath = self.first_el_xpath(tag)
        if xpath is None:
            raise ValueError("Could not find xpath for '{}' tag on: {}".format(
                tag, self.xbrowser.driver.current_url))
        try:
            return self.xbrowser.driver.find_element_by_xpath(xpath)
        except selenium.common.exceptions.InvalidSelectorException:
            log.exception('Find by xpath failed for: {}'.format(xpath))
            raise
        #except selenium.common.exceptions.WebDriverException:
        #   return None

    def all_xpaths(self, tag):
        """Returns all xpaths for a given tag.
        """
        if not self._all_xpaths.get(tag):
            self.get_xpaths(tag)
        return self._all_xpaths.get(tag, [])

    ### price

    def _is_price_range(self, el):
        text = self.xbrowser.execute_jsfun('_XPS.directTextContent', el)
        if not text:
            return False
        words = textutils.split_longwords(text)
        with_digit = len([w for w in words if textutils.contains_digit(w)])
        without_digit = len(words) - with_digit
        return with_digit == 2 and without_digit in (1, 2)

    def _valid_price_format(self, w):
        if not textutils.contains_digit(w):
            return False
        for cs in xbrowser.jsonData['currency_symbols']:
            if not (w.startswith(cs) or w.endswith(cs)):
                continue
            #if ',' not in w and '.' not in w:
            #    continue
            return True
        return False

    def get_price_xpaths(self, _max_y=700, _custom_base_el=None):
        """Compute results for addtocart.
        """
        # If we cannot detect name element, we cannot parse price elements
        if _custom_base_el is None:
            base_el = self.first_el('name')
        else:
            base_el = _custom_base_el
        if not base_el:
            self._record('get_price_xpaths', 'notfound', 'no base el')
            return []

        # Elements containing valid prices
        price_els_texts = []
        # Elements containing fragments of prices that we can possibly join to form
        # whole prices
        price_fragments_els_texts = []
        for el_text in self.xbrowser.els_with_texts(INVALID_PRICE_TAGS, [], EL_MAX_TEXT_LENGTH,
                max_y=_max_y):
            #if '99.90' in el_text.text:
            #    import pdb; pdb.set_trace()
            if not el_text.text:
                continue
            words = textutils.split_longwords(el_text.text)

            if not textutils.contains_digit(el_text.text):
                # Not a full price, but maybe a fragment which contains a currency symbol
                if any(cs in el_text.text for cs in xbrowser.jsonData['currency_symbols']):
                    price_fragments_els_texts.append(el_text)
                continue

            nondigit_words = [w for w in words if not textutils.contains_digit(w)]
            digit_words = [w for w in words if w not in nondigit_words]
            if len(nondigit_words) > 3:
                continue
            if len(digit_words) > 2:
                continue

            all_words_are_prices = all(self._valid_price_format(w) for w in digit_words)
            if len(words) == 2:
                words_are_price_and_currency = \
                   ((words[0] in xbrowser.jsonData['currency_symbols']) and textutils.represents_dollar_amount(words[1])) or \
                   ((words[1] in xbrowser.jsonData['currency_symbols']) and textutils.represents_dollar_amount(words[0]))
            else:
                words_are_price_and_currency = False

            if (not all_words_are_prices) and (not words_are_price_and_currency):
                # Not a full price, but digit words are possibly price fragments
                if not any(ss in el_text.text for ss in INVALID_PRICE_FRAGMENTS_SUBSTRINGS):
                    price_fragments_els_texts.append(el_text)
                continue

            price_els_texts.append(el_text)

        # Cluster fragments
        if price_fragments_els_texts:
            log.debug('price_fragments_els_texts: %s', price_fragments_els_texts)
            fragments_joined_els_texts = [ElText(r[0], r[1]) for r in \
                    self.xbrowser.execute_jsfun_safe([], '_XPS.clusterPriceFragments',
                        [et.el for et in price_fragments_els_texts])]
            log.debug('Fragments joined: %s', fragments_joined_els_texts)
            fragments_joined_els_texts = [et for et in fragments_joined_els_texts if \
                    self._valid_price_format(et.text)]
            log.debug('Fragments joined after filtering: %s', fragments_joined_els_texts)
            price_els_texts.extend(fragments_joined_els_texts)
        else:
            log.debug('No price fragments')

        if not price_els_texts:
            self._record('get_price_xpaths', 'notfound')
            return []

        els_with_visual_distance = [EltDistance(el_text, self.xbrowser.els_min_distance(el_text.el,
            base_el, [0, 2])) for el_text in price_els_texts]
        els_with_visual_distance.sort(key=lambda elt_distance: elt_distance.distance)
        min_visual_distance = els_with_visual_distance[0].distance
        near_enough = [elt_distance.el_text for elt_distance in els_with_visual_distance \
                if elt_distance.distance - min_visual_distance <= MAX_PXDIST_PRICE_FROM_BEST \
                and elt_distance.distance < sys.maxint]
        log.debug('els_with_visual_distance: %s' % \
                [(repr(elt_distance.el_text.text), elt_distance.distance) \
                for elt_distance in els_with_visual_distance])

        if near_enough:
            self._first_el_xpath['price'] = self.xbrowser.compute_xpath(near_enough[0].el)

        self._all_xpaths['price'] = []
        res = []
        for el_text in near_enough:
            if self._is_price_range(el_text.el):
                flag = RESULTDESC_PRICE_RANGE
            else:
                flag = None
            expr = self.xbrowser.compute_xpath(el_text.el)
            if expr is not None:
                self._all_xpaths['price'].append(expr)
                res.append(ScrapingResult([expr], flag, { expr: el_text.text }))
        self._record('get_price_xpaths', 'ok')
        return res

    def _compute_clusters(self, tag, algo_params):
        jsfun_name = '_XPS.find%sElementsCandidates' % tag.capitalize()
        log.debug('Computing candidates for clustering, algo_params=%s', algo_params)
        result_els_xpaths = [self.first_el_xpath('price'), self.first_el_xpath('name'),
                self.first_el_xpath('img'), self.first_el_xpath('addtocart')]
        self._candidates[tag] = [ElText(et[0], et[1]) for et in \
                self.xbrowser.execute_jsfun_safe(None, jsfun_name, result_els_xpaths,
                    algo_params.get('exclude_from_xpaths', []))]
        log.debug('Done: (%s) %s', len(self._candidates[tag]), self._candidates[tag])
        log.debug('Generating clusters')
        cluster_data = self.xbrowser.execute_jsfun_safe([], '_XPS.generateClusters',
                [list(el_text) for el_text in self._candidates[tag]], SIZE_CLUSTERING_DISTANCES)
        dist_clusters = [DistCluster(cd[0], [ElText(et[0], et[1]) for et in cd[1]]) \
                for cd in cluster_data]
        seen_clusters = set()
        self._dists_clusters[tag] = []
        for dist_cluster in dist_clusters:
            cluster_tuple = tuple(dist_cluster.et_cluster)
            if cluster_tuple in seen_clusters:
                continue
            seen_clusters.add(cluster_tuple)
            self._dists_clusters[tag].append(dist_cluster)

    ### size

    def _size_value_valid(self, value):
        return 0 <= value <= 60

    def _represents_size_number(self, s):
        if textutils.represents_number(s):
            return True
        if s.lower().startswith(('w', 'l', 'h')):
            return textutils.represents_number(s[1:])

    def _numeric_size_value(self, s):
        try:
            return float(s)
        except ValueError:
            return float(s[1:])

    def _num_range_from_cluster(self, els_texts):
        res = []
        for el_text in els_texts:
            words = textutils.split_longwords(el_text.text)
            numeric_words = [w for w in words if self._represents_size_number(w)]
            if numeric_words:
                value = self._numeric_size_value(numeric_words[0])
                if self._size_value_valid(value):
                    res.append(numeric_words[0])
        return res

    def _num_range_looks_like_quantity(self, num_range, min_len=3):
        if len(num_range) < min_len:
            return False
        return [round(self._numeric_size_value(x)) for x in num_range] == range(1, len(num_range) + 1)

    def _size_range_from_cluster(self, els_texts):
        res = []
        for el_text in els_texts:
            words = textutils.split_en_words(el_text.text)
            size_words = [w for w in words if w.lower() in xbrowser.jsonData['sizes']]
            if size_words:
                res.append(size_words[0])
        return res

    def _parsed_xpaths(self, els_texts):
        xpaths = [self.xbrowser.compute_xpath(element_text.el) for element_text in els_texts]
        xpaths = [xpath for xpath in xpaths if xpath is not None]
        return [utils.parse_xpath(xpath) for xpath in xpaths]

    def _xpath_lists_similar(self, x1, x2):
        if len(set(len(x) for x in x1)) != 1 or len(set(len(x) for x in x2)) != 1:
            return False
        tag_names1 = { tuple(path_element.tag_name for path_element in x) for x in x1 }
        tag_names2 = { tuple(path_element.tag_name for path_element in x) for x in x2 }
        return tag_names1 == tag_names2

    def _adds_foreign_elements(self, orig_set, new_set):
        if orig_set == new_set:
            return False
        if len(orig_set) in (0, 1):
            return False
        if len(orig_set & new_set) < 2:
            return False
        if not new_set.issuperset(orig_set):
            return False
        orig_xpaths = self._parsed_xpaths(orig_set)
        new_xpaths = self._parsed_xpaths(new_set)
        return not self._xpath_lists_similar(orig_xpaths, new_xpaths)

    def _check_if_adds_foreign_elements(self, dist_cluster1, dist_cluster2):
        elt_set1 = set(dist_cluster1.et_cluster)
        elt_set2 = set(dist_cluster2.et_cluster)
        if self._adds_foreign_elements(elt_set1, elt_set2) and \
                dist_cluster2.dist > dist_cluster1.dist:
            log.debug('Second cluster adds foreign elements to the first, it loses')
            return dist_cluster1
        if self._adds_foreign_elements(elt_set2, elt_set1) and \
                dist_cluster1.dist > dist_cluster2.dist:
            log.debug('First cluster adds foreign elements to the second, it loses')
            return dist_cluster2
        return None

    def _score_from_ranges(self, dist_cluster, num_range, size_range):
        if len(set(size_range)) >= 2:
            base_score = 2.5 * len(set(size_range))
        else:
            base_score = max(len(set(size_range)), len(num_range))
        noise = len(dist_cluster.et_cluster) - base_score
        return base_score - noise

    def _result_based_on_score(self, dist_cluster1, score1, dist_cluster2, score2):
        log.debug('score1=%s, score2=%s', score1, score2)
        if score1 == score2:
            if dist_cluster1.dist <= dist_cluster2.dist:
                log.debug('Same score, but first has lower distance')
                return dist_cluster1
            log.debug('Same score, but second has lower distance')
            return dist_cluster2
        if score1 > score2:
            log.debug('First element has higher range score, it wins')
            return dist_cluster1
        log.debug('Second element has higher range score, it wins')
        return dist_cluster2

    def _dist_factor(self, dist):
        return ((150-dist)/100)

    def _better_size_cluster(self, dist_cluster1, dist_cluster2):
        foreign_check_res = self._check_if_adds_foreign_elements(dist_cluster1, dist_cluster2)
        if foreign_check_res is not None:
            return foreign_check_res

        num_range1 = self._num_range_from_cluster(dist_cluster1.et_cluster)
        size_range1 = self._size_range_from_cluster(dist_cluster1.et_cluster)
        num_range2 = self._num_range_from_cluster(dist_cluster2.et_cluster)
        size_range2 = self._size_range_from_cluster(dist_cluster2.et_cluster)
        log.debug('num_range1: %s', num_range1)
        log.debug('size_range1: %s', size_range1)
        log.debug('num_range2: %s', num_range2)
        log.debug('size_range2: %s', size_range2)

        score1 = self._score_from_ranges(dist_cluster1, num_range1, size_range1)
        score1 *= self._dist_factor(dist_cluster1.dist)
        score2 = self._score_from_ranges(dist_cluster2, num_range2, size_range2)
        score2 *= self._dist_factor(dist_cluster2.dist)
        return self._result_based_on_score(dist_cluster1, score1, dist_cluster2, score2)

    def _num_range_irregular(self, num_range):
        # case for joining price fragments
        if len(num_range) == 2:
            sorted_range = sorted(num_range)
            if sorted_range[0] < 1.0 and sorted_range[1] > 19:
                return True

        return False


    def _is_size_cluster_good_enough(self, dist_cluster):
        size_range = self._size_range_from_cluster(dist_cluster.et_cluster)
        if len(set(size_range)) >= 1:
            return True

        num_range = self._num_range_from_cluster(dist_cluster.et_cluster)

        if len(num_range) <= 1:
            return False

        if self._num_range_irregular(num_range):
            return False

        # excluding quantity select is done by Javascript already, but
        # still a range of consecutive numbers is a wrong size cluster usually
        if self._num_range_looks_like_quantity(num_range):
            return False

        return True

    def _log_clusters(self, tag):
        log.debug('%d clusters', len(self._dists_clusters[tag]))
        for i, dc in enumerate(self._dists_clusters[tag]):
            log.debug('%02d. %s', i, dc)

    def _compute_and_filter_clusters(self, tag, algo_params):
        good_enough_fun = getattr(self, '_is_%s_cluster_good_enough' % tag)
        self._compute_clusters(tag, algo_params)

        log.debug('%s clusters before filtering:', tag)
        self._log_clusters(tag)
        self._dists_clusters[tag] = [dc for dc in self._dists_clusters[tag] if good_enough_fun(dc)]
        #log.debug('%s clusters after filtering:', tag)
        #self._log_clusters(tag)

    def _scraping_result_for_cluster(self, et_cluster, algo_params):
        xpaths = self._compute_best_xpaths_for_els_texts(et_cluster)
        if not xpaths:
            return None
        if not algo_params.get('include_all_options', False):
            option_value = self.xbrowser.execute_jsfun('_XPS.textOfSelectedOption', xpaths)
            if option_value is not None:
                return ScrapingResult(xpaths, None, xpath_evals={}, value=[option_value])
        if len(xpaths) == len(et_cluster):
            value = []
            evals = {}
            for xpath, el_text in zip(xpaths, et_cluster):
                evals[xpath] = el_text.text
                value.append(el_text.text)
            return ScrapingResult(xpaths, None, evals, value=value)
        value = [self.xbrowser.el_text(el) for el in self.xbrowser.els_by_xpath(xpaths[0])]
        return ScrapingResult(xpaths, None, {xpaths[0]: ' :: '.join(value)}, value)

    def _play_tournament_and_get_xpaths(self, tag, algo_params={}):
        """This function requires the following defined:
        - self._better_{tag}_cluster(dist_cluster1, dist_cluster2)
        - self._is_{tag}_cluster_good_enough(dist_cluster)
        - _XPS.find{tag.capitalize}ElementsCandidates
        """
        log.debug('Playing tournament for %s', tag)
        self._compute_and_filter_clusters(tag, algo_params)
        if not self._dists_clusters[tag]:
            log.warn('_play_tournament_and_get_xpaths(%s): no clusters left to play after filtering, '
                     'returning empty result', tag)
            self._record('_play_tournament_and_get_xpaths(%s)' % tag, 'noclusters')
            return []
        match_fun = getattr(self, '_better_%s_cluster' % tag)
        self._best_cluster[tag] = utils.run_tournament(self._dists_clusters[tag], match_fun)
        scraping_result = self._scraping_result_for_cluster(self._best_cluster[tag].et_cluster,
                algo_params)
        if scraping_result is not None:
            res = [scraping_result]
        else:
            log.warn('None result from _scraping_result_for_cluster')
            res = []
        log.debug('Tournament res for %s: %s', tag, res)
        self._record('_play_tournament_and_get_xpaths(%s)' % tag, 'ok')
        return res

    def _play_league_and_get_xpaths(self, tag, algo_params={}):
        log.debug('Playing league for %s', tag)
        self._compute_and_filter_clusters(tag, algo_params)
        if not self._dists_clusters[tag]:
            log.warn('_play_league_and_get_xpaths(%s): no clusters left to play after filtering, '
                     'returning empty result', tag)
            self._record('_play_league_and_get_xpaths(%s)' % tag, 'noclusters')
            return []
        match_fun = getattr(self, '_play_match_%s' % tag)
        table = utils.run_league(self._dists_clusters[tag], match_fun)
        self._best_cluster[tag] = table[0][0]
        scraping_result = self._scraping_result_for_cluster(self._best_cluster[tag].et_cluster,
                algo_params)
        if scraping_result is not None:
            res = [scraping_result]
        else:
            log.warn('None result from _scraping_result_for_cluster')
            res = []
        log.debug('League res for %s: %s', tag, res)
        self._record('_play_league_and_get_xpaths(%s)' % tag, 'ok')
        return res

    def _play_match_size(self, dist_cluster1, dist_cluster2):
        winner = self._better_size_cluster(dist_cluster1, dist_cluster2)
        if winner is dist_cluster1:
            return (1, 0)
        elif winner is dist_cluster2:
            return (0, 1)
        assert False, 'No winner'

    def get_size_xpaths(self):
        """Compute results for size.
        """
        return self._get_click_or_static_xpaths('size')


    ### color

    def _init_colors_data(self):
        self._word_to_color_words = defaultdict(list)
        for c in xbrowser.jsonData['colors']:
            color_words = textutils.split_en_words(c)
            for word in color_words:
                self._word_to_color_words[word].append(color_words)
        # Sort color words lists by length, to match longer color names first
        for cw_list in self._word_to_color_words.values():
            cw_list.sort(key=len, reverse=True)

    def _color_range_from_cluster(self, els_texts):
        res = []
        for el_text in els_texts:
            words = utils.unique_sameorder(textutils.split_en_words(el_text.text.lower()))
            used_words_idxs = set()
            res_for_words = []
            for word in words:
                color_words_list = self._word_to_color_words.get(word, [])
                for color_words in color_words_list:
                    if not all(color_word in words for color_word in color_words):
                        continue
                    found_idxs = [words.index(color_word) for color_word in color_words]
                    if not used_words_idxs.isdisjoint(found_idxs):
                        continue
                    used_words_idxs.update(found_idxs)
                    res_for_words.append(' '.join(color_words))
            not_used_words = [words[i] for i in range(len(words)) if i not in used_words_idxs]
            #log.debug('words=%s, not_used_words=%s', words, not_used_words)
            if not all(w in COLOR_NOISE_WORDS_WHITELIST for w in not_used_words):
                continue
            res.extend(res_for_words)
        return res

    def _better_color_cluster(self, dist_cluster1, dist_cluster2):
        foreign_check_res = self._check_if_adds_foreign_elements(dist_cluster1, dist_cluster2)
        if foreign_check_res is not None:
            return foreign_check_res
        color_range1 = self._color_range_from_cluster(dist_cluster1.et_cluster)
        color_range2 = self._color_range_from_cluster(dist_cluster2.et_cluster)
        log.debug('color_range1: %s', color_range1)
        log.debug('color_range2: %s', color_range2)
        score1 = 2*len(color_range1) - len(dist_cluster1.et_cluster)
        score1 *= self._dist_factor(dist_cluster1.dist)
        score2 = 2*len(color_range2) - len(dist_cluster2.et_cluster)
        score2 *= self._dist_factor(dist_cluster2.dist)
        return self._result_based_on_score(dist_cluster1, score1, dist_cluster2, score2)

    def _is_color_cluster_good_enough(self, dist_cluster):
        colors = self._color_range_from_cluster(dist_cluster.et_cluster)
        return len(colors) >= 1

    def _get_click_or_static_xpaths(self, tag):
        if self._safe_to_click():
            return self._get_click_result(tag)
        return self._get_xpaths_static(tag)

    def get_color_xpaths(self):
        """Compute results for color.
        """
        return self._get_click_or_static_xpaths('color')

    ### sizetype

    def _sizetype_range_from_cluster(self, els_texts):
        res = []
        for el_text in els_texts:
            words = textutils.split_en_words(el_text.text.lower())
            if len(words) <= 2 and any(w in xbrowser.jsonData['sizetypes'] for w in words):
                res.append(el_text.text)
        return res

    def _better_sizetype_cluster(self, dist_cluster1, dist_cluster2):
        sizetype_range1 = self._sizetype_range_from_cluster(dist_cluster1.et_cluster)
        sizetype_range2 = self._sizetype_range_from_cluster(dist_cluster2.et_cluster)
        log.debug('sizetype_range1: %s', sizetype_range1)
        log.debug('sizetype_range2: %s', sizetype_range2)
        return self._result_based_on_score(dist_cluster1, len(sizetype_range1),
                dist_cluster2, len(sizetype_range2))

    def _is_sizetype_cluster_good_enough(self, dist_cluster):
        sizetypes = self._sizetype_range_from_cluster(dist_cluster.et_cluster)
        return len(sizetypes) >= 1

    def get_sizetype_xpaths(self):
        """Compute results for sizetype.
        """
        return self._get_click_or_static_xpaths('sizetype')


    ### inseam

    def _inseam_range_from_cluster(self, els_texts):
        res = []
        for el_text in els_texts:
            words = textutils.split_en_words(el_text.text.lower())
            if len(words) <= 2 and any(w in xbrowser.jsonData['inseams'] for w in words):
                res.append(el_text.text)
        return res

    def _better_inseam_cluster(self, dist_cluster1, dist_cluster2):
        inseam_range1 = self._inseam_range_from_cluster(dist_cluster1.et_cluster)
        inseam_range2 = self._inseam_range_from_cluster(dist_cluster2.et_cluster)
        log.debug('inseam_range1: %s', inseam_range1)
        log.debug('inseam_range2: %s', inseam_range2)
        return self._result_based_on_score(dist_cluster1, len(inseam_range1),
                dist_cluster2, len(inseam_range2))

    def _is_inseam_cluster_good_enough(self, dist_cluster):
        inseams = self._inseam_range_from_cluster(dist_cluster.et_cluster)
        if len(inseams) > 1:
            return True
        if len(inseams) == 0:
            return False
        assert len(inseams) == 1
        return 'regular' not in inseams[0].lower()

    def get_inseam_xpaths(self):
        """Compute results for inseam.
        """
        return self._get_click_or_static_xpaths('inseam')


    ### colordata

    def get_colordata_xpaths(self):
        """Compute results for colordata.
        """
        return self._get_click_result('colordata')

    def _get_colordata_xpaths_static(self, color_name, clicked_xpath):
        res = {'name': color_name}

        img_res = self.get_img_xpaths(_img_kind=color_name)
        if img_res:
            res['product_image'] = img_res[0].rich_value.src

        if clicked_xpath:
            swatch_image = self.xbrowser.execute_jsfun('_XPS.imageSrcFromXPath', clicked_xpath)
        else:
            swatch_image = None
        res['swatch_image'] = swatch_image

        return [ScrapingResult(value=res)]


    ### checkoutbutton

    def _el_to_click_based_on_found(self, xpath):
        anchors = self.xbrowser.execute_jsfun('_XPS.evaluateXPathToXPaths', xpath + '//a')
        if anchors:
            return anchors[0]
        return xpath

    def _word_matching_score(self, text, words_weights):
        indiv_scores = [weight * textutils.word_matching_score(text, s) \
                for s, weight in words_weights.items()]
        if min(indiv_scores) == -1:
            return -1
        return max(indiv_scores)

    def _attrs_matching_score(self, xpath_attr, words_weights, attr_score_d):
        scores = []
        for attr, value in xpath_attr[1]['attrs'].items():
            matching_score = self._word_matching_score(value, words_weights)
            attr_score = attr_score_d.get(attr, 0.0)
            score = matching_score * attr_score
            #log.debug('xpath %s attr %s value %s matching_score %s attr_score %s score %s',
            #        xpath_attr[0], attr, value, matching_score, attr_score, score)
            scores.append(score)
        return max(scores)

    _CHECKOUT_ATTR_SCORE = {
            'text': 1.0,
            'alt': 1.0,
            'value': 0.3,
            'href': 0.25,
            'background-image': 0.25,
            'class': 0.15,
            'src': 0.05,
    }
    def _total_checkoutbutton_score(self, xpath_attr):
        return self._attrs_matching_score(xpath_attr, xbrowser.jsonData['checkout_words'],
                self._CHECKOUT_ATTR_SCORE)

    def _closer_to_right_top_corner(self, rect1, rect2):
        def left(r):
            return min(r['right'], 1000)
        def bottom(r):
            return min(0, r['bottom'])
        def point(r):
            return (left(r), bottom(r))
        p1 = point(rect1)
        p2 = point(rect2)
        best_p = (max(p1[0], p2[0]), min(p1[1], p2[1]))
        dist1 = utils.euclidean_distance(p1, best_p)
        dist2 = utils.euclidean_distance(p2, best_p)
        if dist1 < dist2:
            return rect1
        return rect2

    def get_checkoutbutton_xpaths(self):
        """Compute results for checkoutbutton.
        """
        xpaths_attrs = self.xbrowser.execute_jsfun('_XC.findCheckoutXPathCandidates')
        log.debug('checkoutbutton xpaths_attrs: %s', xpaths_attrs)
        if not xpaths_attrs:
            return []

        xpathsattrs_scores = [(xpath_attr, self._total_checkoutbutton_score(xpath_attr)) \
                for xpath_attr in xpaths_attrs]
        def cmp_xpath_score((xpath_attr1, score1), (xpath_attr2, score2)):
            if score1 != score2:
                return cmp(score1, score2)
            r1 = xpath_attr1[1]['boundingRectangle']
            r2 = xpath_attr2[1]['boundingRectangle']
            closer_res = self._closer_to_right_top_corner(r1, r2)
            if closer_res is r1:
                return 1
            return -1

        xpathsattrs_scores.sort(cmp=cmp_xpath_score, reverse=True)
        log.debug('checkoutbutton xpaths_scores: %s', xpathsattrs_scores)

        xpath = xpathsattrs_scores[0][0][0]
        xpath = self._el_to_click_based_on_found(xpath)
        log.debug('final checkoutbutton xpath to click: %s', xpath)
        self._first_el_xpath['checkoutbutton'] = xpath
        return [ScrapingResult([xpath])]


    ### review

    def _total_review_score(self, xpath_attr):
        return self._attrs_matching_score(xpath_attr, xbrowser.jsonData['review_words'],
                self._CHECKOUT_ATTR_SCORE)

    def get_review_xpaths(self):
        """Compute results for review.
        """
        xpaths_attrs = self.xbrowser.execute_jsfun('_XPS.findReviewXPathCandidates')
        #log.info('review xpaths_attrs: %s', xpaths_attrs)
        if not xpaths_attrs:
            log.debug('No review xpaths')
            return []

        xpathsattrs_scores = [(xpath_attr, self._total_review_score(xpath_attr)) \
                for xpath_attr in xpaths_attrs]
        xpathsattrs_scores = [(xpath_attr, score) for (xpath_attr, score) in xpathsattrs_scores \
                if score > 0]
        log.debug('review xpaths_scores: %s', xpathsattrs_scores)
        if not xpathsattrs_scores:
            return []

        xpath = xpathsattrs_scores[0][0][0]
        self._first_el_xpath['review'] = xpath
        xpaths = [xpath_attr[0] for xpath_attr, score in xpathsattrs_scores]
        log.debug('review xpaths: %s', xpaths)
        return [ScrapingResult(xpaths)]


    ### clicking algorithm

    def _clicksleep(self):
        log.debug('Sleeping %s', SLEEP_BETWEEN_CLICKS)
        time.sleep(SLEEP_BETWEEN_CLICKS)
        log.debug('Continuing...')
        # It breaks search for product images, at least
        #xutils.wait_for_complete_state_or_url_change(self.xbrowser)

    def _result_from_checkout_page(self):
        subtotal_xpaths = self.xbrowser.execute_jsfun('_XC.findSubtotalWordXPathCandidates')
        log.debug('subtotal_xpaths: %s', subtotal_xpaths)
        for subtotal_xpath in subtotal_xpaths:
            subtotal_el = self.xbrowser.driver.find_element_by_xpath(subtotal_xpath)
            log.debug('checkout: computing prices for %s', subtotal_xpath)
            prices = self.get_price_xpaths(_max_y=2000, _custom_base_el=subtotal_el)
            log.debug('checkout: found prices: %s', prices)
            good_prices = [sr for sr in prices if sr.xpath_expr_list and self.xbrowser.execute_jsfun(\
                '_XC.isNearAndVerticallyAligned', subtotal_xpath, sr.xpath_expr_list[0])]
            log.debug('checkout: good prices: %s', good_prices)
            if good_prices:
                the_price = good_prices[0]
                from xpathscraper import resultsenrichment
                price_enriched = resultsenrichment._enrich_price(None, [the_price], self)
                log.debug('Enriched checkout price: %s', price_enriched)
                self._record('_result_from_checkout_page', 'ok')
                return {'checkoutprice': [ScrapingResult(rich_value=price_enriched[0])]}
        self._record('_result_from_checkout_page', 'notfound')
        return {}

    def _default_word_weights(self, word_lst, weight=1.0):
        return {word: weight for word in word_lst}

    def _total_removefromcart_score(self, xpath_attr):
        return self._attrs_matching_score(xpath_attr,
                self._default_word_weights(xbrowser.jsonData['remove_from_cart_words']),
                self._CHECKOUT_ATTR_SCORE)

    def _find_removefromcart_el(self):
        xpaths_attrs = self.xbrowser.execute_jsfun('_XC.findRemoveFromCartXPathCandidates')
        log.debug('removefromcart xpaths_attrs: %s', xpaths_attrs)
        if not xpaths_attrs:
            self._record('_find_removefromcart_el', 'notfound')
            return None
        xpathsattrs_scores = [(xpath_attr, self._total_removefromcart_score(xpath_attr)) \
                for xpath_attr in xpaths_attrs]
        xpathsattrs_scores.sort(key=lambda (xpath_attr, score): score, reverse=True)
        log.debug('removefromcart xpathsattrs_scores: %s', xpathsattrs_scores)
        first_xpath = xpathsattrs_scores[0][0][0]
        self._record('_find_removefromcart_el', 'ok')
        return self.xbrowser.driver.find_element_by_xpath(first_xpath)

    def _is_checkout_page_empty(self):
        self.xbrowser.inject_js()
        return self._result_from_checkout_page() == {}

    def _click_removefromcart_and_check_if_it_worked(self):
        remove_el = self._find_removefromcart_el()
        if remove_el is None:
            log.warn('No remove button found')
            return False
        log.debug('Clicking on remove button')
        remove_el.click()
        self._clicksleep()
        try:
            remove_worked = self._is_checkout_page_empty()
        except:
            log.exception('Exception while _is_checkout_page_empty, continuing')
            remove_worked = True
        if not remove_worked:
            self._record('_click_removefromcart_and_check_if_it_worked', 'fail')
            log.error('Remove button not working')
            return False
        log.debug('Remove button worked')
        return True

    def _restore_cookies(self):
        self.xbrowser.driver.delete_all_cookies()
        for cookie in self._inital_cookies:
            self.xbrowser.driver.add_cookie(cookie)

    def _goto_cart(self, page_results):
        checkout_res = page_results.copy()
        orig_url = self.xbrowser.driver.current_url

        try:
            addtocart_el = self.first_el('addtocart', fresh=True)
        except selenium.common.exceptions.NoSuchElementException:
            log.warn('No addtocart button present for this size/color combination')
            self._record('addtocart_not_present')
            return checkout_res

        try:
            log.debug('Clicking addtocart el')
            addtocart_el.click()
            self._clicksleep()
            self._record('addtocart_clicked')

            # If clicking addtocart reloaded page, inject js (if not,
            # nothing bad happens)
            new_page = self.xbrowser.inject_js()
            if new_page:
                log.warn('Clicking addtocart loaded a different page')
                self._record('addtocart_loaded_different_page')

            # It seems it can break some sites
            log.debug('Reloading page before clicking checkout button')
            self.xbrowser.load_url(orig_url)

            checkoutbutton_el = self.first_el('checkoutbutton', fresh=True)
            if not checkoutbutton_el:
                log.warn('Cannot evaluate checkoutbutton el')
                self._record('cannot_evaluate_checkoutbutton')
                return checkout_res
            log.debug('Clicking checkoutbutton')
            checkoutbutton_el.click()
            self._clicksleep()
            self._record('checkoutbutton_clicked')

            log.debug('Now on checkout page, injecting js')
            new_page = self.xbrowser.inject_js()
            if not new_page:
                log.warn('Checkout page is the same as product page, '
                        'clicking checkoutbutton once again')
                checkoutbutton_el.click()
                self._record('checkoutbutton_clicked_once_again')
                self._clicksleep()

            new_res = self._result_from_checkout_page()
            log.debug('result from checkout page: %s', new_res)
            checkout_res.update(new_res)
        except selenium.common.exceptions.WebDriverException as e:
            self._record('while_going_to_cart', 'exception', e.__class__.__name__)
            log.exception('Exception while going to cart, continuing')
        finally:
            #log.info('Restoring cookies')
            #self._restore_cookies()

            #log.info('Deleting all cookies')
            #self.xbrowser.driver.delete_all_cookies()
            #log.info('Done')

            try:
                self._click_removefromcart_and_check_if_it_worked()
            except selenium.common.exceptions.WebDriverException as e:
                self._record('while_clicking_removefromcart', 'exception', e.__class__.__name__)
                log.exception('Exception while clicking removefromcart, continuing')

        return checkout_res

    def _get_xpaths_static(self, tag, algo_params={}):
        if tag in {'size'}:
            return self._play_league_and_get_xpaths(tag, dict(algo_params,
                exclude_from_xpaths=self.all_xpaths('price') + self.all_xpaths('review')))
        if tag in {'color', 'sizetype', 'inseam'}:
            return self._play_tournament_and_get_xpaths(tag, dict(algo_params, include_all_options=True))
        assert False, 'unknown tag %s' % tag

    def _safe_to_click(self):
        if CHECK_SAFE_TO_CLICK_DOMAINS and \
                (not any(safe_domain in self.domain for safe_domain in SAFE_TO_CLICK)):
            log.warn('Domain not safe for clicking')
            return False
        return True

    def _compute_color_candidates_to_click(self, els_to_click, els_to_not_click, result_els_xpaths):
        if not self._safe_to_click():
            return []
        log.debug('els_to_click: %s', els_to_click)
        log.debug('els_to_not_click: %s', els_to_not_click)
        to_click = self.xbrowser.execute_jsfun('_XPS.getColorElementsXPathsToClick',
                result_els_xpaths)
        log.debug('got to_click: %r', to_click)
        if els_to_click:
            to_click += els_to_click
        log.debug('all els to click (%s): %s', len(to_click), to_click)
        if els_to_not_click:
            to_click = self.xbrowser.execute_jsfun('_XPS.removeRelatedEls', to_click,
                    els_to_not_click)
            log.debug('els to click after removing (%s): %s', len(to_click), to_click)
        return list(reversed(to_click))

    def _click(self, xpath):
        log.debug('Clicking %s', xpath)
        url_before_click = self.xbrowser.driver.current_url
        clicked_el = None
        try:
            clicked_el = self.xbrowser.driver.find_element_by_xpath(xpath)
            clicked_el.click()
        except (selenium.common.exceptions.NoSuchElementException,
                selenium.common.exceptions.StaleElementReferenceException,
                selenium.common.exceptions.ElementNotVisibleException,
                selenium.common.exceptions.UnexpectedAlertPresentException,
               ):
            log.exception('Exception while clicking, skipping')
        else:
            self._clicksleep()
        #log.info('sleeping before checking url')
        #time.sleep(1)
        log.debug('continuing')
        if not self.xbrowser._is_js_initialized():
            log.warn('JS is not initialized after clicking! Reloading original url')
            self.xbrowser.load_url(url_before_click, refresh=True)
            self.reset()
        return clicked_el

    def _inner_results_to_hashable(self, inner_results):
        d = copy.deepcopy(inner_results)
        if d.get('colordata'):
            d['colordata'][0].value.pop('product_image', None)
            d['colordata'][0].value.pop('swatch_image', None)
        return utils.make_hashable(d)

    def _do_color_size_clicks(self):
        seen_combinations = set()
        while True:
            data_tuple = yield
            if data_tuple is None:
                log.debug('_do_color_size_clicks received None, finishing')
                return
            cur_results, color_pathel, size_pathel = data_tuple

            if color_pathel and color_pathel.xpath:
                log.debug('Clicking color el')
                self._click(color_pathel.xpath)
                self._record('clicked_color_pathel')

            color_res = self._get_xpaths_static('color')
            log.debug('color_res: %s', color_res)
            last_colors = color_res[0].value if color_res else None
            if last_colors:
                cur_results['colordata'] = self._get_colordata_xpaths_static(
                        (last_colors[0] or '').lower(), color_pathel.xpath if color_pathel else None)
            inner_results = cur_results.copy()

            if size_pathel and size_pathel.xpath:
                try:
                    size_el = self.xbrowser.driver.find_element_by_xpath(size_pathel.xpath)
                except selenium.common.exceptions.WebDriverException:
                    log.exception('Cannot evaluate size_el, skipping this color, size combination')
                    self._record('cannot_eval_size_el_skipping')
                    continue
                size_value = size_pathel.value
                if not size_value:
                    size_value = self.xbrowser.el_text(size_el)
                inner_results['sizevalue'] = [ScrapingResult(value=size_value)]
                log.debug('Clicking size xpath %s value=%s', size_pathel.xpath, size_value)
                self._click(size_pathel.xpath)
                self._record('clicked_size_pathel')
            else:
                log.debug('Not clicking size - no size xpath')

            ir_hashable = self._inner_results_to_hashable(inner_results)
            log.debug('seen_combinations: %s', seen_combinations)
            if ir_hashable in seen_combinations:
                log.debug('Page results combination previously encountered')
                continue
            log.debug('Noticed new page results combination: %s', inner_results)
            # FIXME
            #seen_combinations.add(ir_hashable)

            if GOTO_CART:
                log.debug('Going to cart')
                inner_results = self._goto_cart(inner_results.copy())
                self._record('got_cart_results')
            else:
                log.warn('Not going to cart, computing price from the current page')
                prices = self.get_price_xpaths()
                log.debug('Prices for current page: %s', prices)
                if not prices:
                    log.warn('No price found')
                else:
                    from xpathscraper import resultsenrichment
                    price_enriched = resultsenrichment._enrich_price(None, [prices[0]], self)
                    log.debug('Enriched price for the current page: %s', price_enriched)
                    if price_enriched:
                        inner_results['checkoutprice'] = [ScrapingResult(rich_value=price_enriched[0])]

            log.debug('Final inner_results: %s', inner_results)
            if inner_results:
                self._click_results.append(inner_results)


    def _click_in_paths(self):
        orig_url = self.xbrowser.driver.current_url
        paths = self._generate_click_paths()
        if not paths:
            log.debug('No paths to click, adding empty path to click')
            paths = [[]]

        self.xbrowser.recreate_driver()
        self.xbrowser.load_url(orig_url, refresh=True)

        color_size_gen = self._do_color_size_clicks()
        color_size_gen.send(None)

        def send_xpaths(path_res, color_pathel, size_pathel):
            log.debug('Sending path_res=%s color_pathel=%s, size_pathel=%s',
                    path_res, color_pathel, size_pathel)
            color_size_gen.send((path_res, color_pathel, size_pathel))

            #log.info('Restoring cookies and refreshing a page after clicking in path els')
            #self._restore_cookies()
            log.debug('Refreshing page after clicking in path els')
            self.xbrowser.load_url(orig_url, refresh=True)

        if LIMIT_PATHS:
            paths = paths[:LIMIT_PATHS]
        for path_no, path in enumerate(paths):
            log.warn('=' * 40)
            log.warn('Clicking in path %d/%d: %s', path_no + 1, len(paths), path)
            work_path = path[:]
            path_res = {}
            while work_path and work_path[0].tag not in {'color', 'size'}:
                log.debug('Simple clicking %s', work_path[0])
                self._click(work_path[0].xpath)
                self._clicksleep()

                text = work_path[0].value
                if not text:
                    text = self.xbrowser.el_text_xpath(work_path[0].xpath)
                if text:
                    path_res['%svalue' % work_path[0].tag] = [ScrapingResult(value=text)]

                del work_path[0]

            if not work_path:
                # Empty path for products without colors and sizes
                send_xpaths(path_res, None, None)
                continue

            log.debug('Path remaining after simple clicking: %s', work_path)
            if work_path[0].tag == 'color':
                color_pathel = work_path[0]
                del work_path[0]
            else:
                color_pathel = None

            if work_path and work_path[0].tag == 'size':
                size_pathel = work_path[0]
            else:
                size_pathel = None

            send_xpaths(path_res, color_pathel, size_pathel)
            self._record('click_path_processed')

        try:
            color_size_gen.send(None)
        except StopIteration:
            pass

    def _xpaths_from_first_sr(self, tag, algo_params={}):
        srs = self._get_xpaths_static(tag, algo_params)
        if not srs:
            return []
        return srs[0].xpath_expr_list or []

    def _xpaths_values_from_first_sr(self, tag, algo_params={}):
        srs = self._get_xpaths_static(tag, algo_params)
        if not srs:
            return []
        sr = srs[0]
        if isinstance(sr.value, list) and len(sr.value) == len(sr.xpath_expr_list):
            return zip(sr.xpath_expr_list, sr.value)
        return zip(sr.xpath_expr_list, [None] * len(sr.xpath_expr_list))

    def _first_color_name_static(self):
        color_res = self._get_xpaths_static('color')
        if not color_res or not color_res[0].value:
            return None
        return color_res[0].value[0]

    def _generate_click_paths(self):

        def generate_paths(tag):
            if tag == 'sizetype':
                next_fun = lambda: generate_paths('inseam')
            elif tag == 'inseam':
                next_fun = lambda: generate_color_paths()
            xpaths_values = self._xpaths_values_from_first_sr(tag)
            log.debug('generate_xpaths(%s): xpaths: %s', tag, xpaths_values)
            if not xpaths_values:
                return next_fun()
            res = []
            for xpath, value in xpaths_values:
                self._click(xpath)
                self._clicksleep()
                paths = next_fun()
                for p in paths:
                    res.append([TagXPathValue(tag, xpath, value)] + p)
            return res

        def generate_color_paths():
            result_els_xpaths = [self.first_el_xpath('price'), self.first_el_xpath('name'),
                    self.first_el_xpath('img')]
            log.debug('result_els_xpaths: %s', result_els_xpaths)
            if any(xpath is None for xpath in result_els_xpaths):
                log.error('Cannot compute price, name or img, cannot click')
                return []

            # color xpaths might be labels only or <option>s, which we need to click
            color_xpaths_values = self._xpaths_values_from_first_sr('color',
                    {'include_all_options': True})
            size_xpaths_values = self._xpaths_values_from_first_sr('size')
            xpaths = self._compute_color_candidates_to_click(
                    els_to_click=[x_v[0] for x_v in color_xpaths_values],
                    els_to_not_click=[x_v[0] for x_v in size_xpaths_values],
                    result_els_xpaths=result_els_xpaths)
            log.debug('generate_color_paths(): xpaths: %s', xpaths)
            if not xpaths:
                return generate_size_paths()
            res = []

            # include size-only xpaths for not clicking any color
            res += generate_size_paths()

            xpath_values_d = dict(color_xpaths_values + size_xpaths_values)
            main_url = self.xbrowser.driver.current_url
            for xpath in xpaths:
                self.xbrowser.load_url(main_url)
                self.reset()
                old_color = self._first_color_name_static()
                self._click(xpath)
                self._clicksleep()
                try:
                    new_color = self._first_color_name_static()
                except selenium.common.exceptions.WebDriverException:
                    log.exception('Exception while computing new color, not using this xpath')
                    continue
                log.debug('old_color=%s, new_color=%s', old_color, new_color)
                if new_color == old_color:
                    log.debug('Colors are the same, not using this xpath')
                    continue
                if new_color is None:
                    log.debug('New color is None, not using this xpath')
                    continue
                log.debug('Colors are different, using this xpath')
                paths = generate_size_paths()
                for p in (paths or [[]]):
                    res.append([TagXPathValue('color', xpath, xpath_values_d.get(xpath))] + p)
            return res

        def generate_size_paths():
            xpaths_values = self._xpaths_values_from_first_sr('size')
            if LIMIT_SIZE_CLICKS is not None:
                log.warn('Limiting size clicks to %s', LIMIT_SIZE_CLICKS)
                xpaths_values = xpaths_values[:LIMIT_SIZE_CLICKS]
            log.debug('generate_size_paths(): xpaths_values: %s', xpaths_values)
            res = [[TagXPathValue('size', x_v[0], x_v[1])] for x_v in xpaths_values]
            return res

        paths = generate_paths('sizetype')
        log.warn('Click paths: \n%s', '\n'.join(repr(p) for p in paths))
        return paths

    def _postprocess_click_results(self):
        best_by_size_color = OrderedDict()

        def get_sizevalue(x):
            if not x.get('sizevalue'):
                return None
            return x['sizevalue'][0].value

        def get_colordata(x):
            if not x.get('colordata'):
                return {}
            if not x['colordata'][0].value:
                return {}
            return x['colordata'][0].value

        rest = []
        for d in self._click_results:
            sizevalue = get_sizevalue(d)
            colordata = get_colordata(d)
            colorname = colordata.get('name')
            log.debug('postprocess: sizevalue=%s, colorname=%s from %s', sizevalue, colorname, d)
            if not colorname and not sizevalue:
                rest.append(d)
            elif (sizevalue, colorname) in best_by_size_color:
                best_d = best_by_size_color[(sizevalue, colorname)]
                def key(x):
                    return (
                        bool(get_sizevalue(x)),
                        bool(get_colordata(x)),
                        bool(get_colordata(x).get('product_image')),
                        bool(get_colordata(x).get('swatch_image')),
                    )
                if key(d) > key(best_d):
                    log.debug('Result %s is better than %s, replacing', d, best_d)
                    best_by_size_color[(sizevalue, colorname)] = d
            else:
                best_by_size_color[(sizevalue, colorname)] = d
        self._click_results = best_by_size_color.values() + rest


    def perform_clicking(self):
        """Execute the clicking algorithm and return a list of dictionaries as a result.
        """
        if self._click_results:
            return self._click_results
        self._click_results = []
        if self._safe_to_click():
            self._click_in_paths()
            self._postprocess_click_results()
            log.debug('CLICKING RESULT: %s', self._click_results)
            self._record('performed_clicking')
        return self._click_results

    def _get_click_result(self, tag):
        if self._click_results is None:
            self.perform_clicking()
        return utils.unique_sameorder(
                list(reversed(utils.concat_list_dicts(self._click_results).get(tag, []))))

    def reset(self):
        """Reset state of a scraper.
        """
        self._first_el_xpath.clear()

    ### WebElement/JS methods

    def _try_reduce_xpaths_to_capturing_xpath(self, xpaths):
        reduced = utils.reduce_xpaths_to_capturing_xpath(xpaths)
        if reduced is None:
            log.debug('Couldn\'t reduce xpath expressions %s', xpaths)
            return None
        log.debug('Reduced %s to xpath: %s', xpaths, reduced)
        els_from_orig_xpaths = [self.xbrowser.el_by_xpath(xpath) for xpath in xpaths]
        els_from_orig_xpaths = [el for el in els_from_orig_xpaths if el is not None]
        els_from_reduced_xpath = self.xbrowser.els_by_xpath(reduced)
        if seleniumtools.element_sets_equivalent(els_from_orig_xpaths, els_from_reduced_xpath):
            log.debug('Reduced xpath gives equivalent results')
            return reduced
        else:
            log.debug('Reduced xpath doesn\'t give equivalent results')
            return None

    def _compute_best_xpaths_for_els_texts(self, els_texts):
        for skip_unique in COMMON_XPATH_COMPUTATION_SKIP_TRIES:
            xpaths = [self.xbrowser.compute_xpath(el_text.el, skip_unique) for el_text in els_texts]
            xpaths = [xpath for xpath in xpaths if xpath is not None]
            if TRY_REDUCE_XPATHS:
                reduced = self._try_reduce_xpaths_to_capturing_xpath(xpaths)
            else:
                reduced = None
            if reduced:
                log.debug('Found reduced expr for skip_unique=%s', skip_unique)
                return [reduced]
            log.debug('Didn\'t find reduced expr for skip_unique=%s', skip_unique)
        log.debug('No reduced exprs found')
        res = [self.xbrowser.compute_xpath(el_text.el, 0) for el_text in els_texts]
        res = [xpath for xpath in res if xpath is not None]
        return res

    def eval_sr_xpaths(self, scraping_results, select_exprs_fun=None):
        els = []
        for sr in scraping_results:
            if not sr.xpath_expr_list:
                continue
            exprs = select_exprs_fun(sr) if select_exprs_fun else sr.xpath_expr_list
            for e in exprs:
                el = None
                try:
                    el = self.driver.find_element_by_xpath(e)
                except (selenium.common.exceptions.NoSuchElementException,
                        selenium.common.exceptions.StaleElementReferenceException):
                    pass
                if el:
                    els.append(ElSResult(el, sr))
        return els

    def eval_sr_first_xpaths(self, scraping_results):
        return self.eval_sr_xpaths(scraping_results, lambda sr: [sr.xpath_expr_list[0]])


### Commands for debugging/testing

@baker.command
def create_scraper_for_url(url, headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY):
    xb = xbrowser.XBrowser(url, headless_display=headless_display, disable_cleanup=(not settings.DEBUG))
    s = Scraper(xb)
    return s

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

