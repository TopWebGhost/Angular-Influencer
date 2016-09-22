# -*- coding: utf-8 -*-
from __future__ import division

import sys
import os
import os.path
from collections import namedtuple
import json
from glob import glob
import logging
import threading
import time
import urlparse

import selenium.common.exceptions
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.keys import Keys
import pyvirtualdisplay
from django.conf import settings

from . import seleniumtools
from . import datatools
from . import utils
from .utils import env_flag
from servermonitoring import watchdog

from django.core.cache import cache

log = logging.getLogger(__name__)


JS_DIR = os.path.join(os.path.dirname(__file__), 'js')
JSON_DIR = os.path.join(os.path.dirname(__file__), 'json')
jsonData = datatools.JSONDataLoader(JSON_DIR)

LOAD_JS_FILES_FROM_SERVER = env_flag('XPS_JS_FROM_SERVER')
VERBOSE_LOG = settings.DEBUG

JS_FILENAMES = [
    'visibility.js',
    'utils.js',
    'elutils.js',
    'scraper.js',
    'mutations.js',
    'checkout.js',
]

JS_FILE_SERVER = 'http://localhost/js/'

xcontext = threading.local()


class ElText(namedtuple('ElText', ['el', 'text'])):
    """A tuple of WebElement and textual content. We add some
    methods to the tuple to handle comparing and hashing
    in a way that enables storing WebElements with texts
    in dictionaries and sets.
    """
    def __eq__(self, other):
        return self.el._id == other.el._id

    def __hash__(self):
        return hash(self.el._id)

    def __repr__(self):
        # Original __repr__ for WebElement is too long
        elstr = '<el>'
        if VERBOSE_LOG:
            xbrowser = getattr(xcontext, 'current_xbrowser', None)
            if xbrowser:
                elstr = xbrowser.execute_jsfun_safe('?', '_XPS.computeXPath', self.el)
        return super(ElText, self._replace(el=elstr)).__repr__()


class XBrowser(object):
    """This class prepares an environment for running code in a Firefox browser
    through Selenium. It loads json data, Javascript code and exposes helper
    functions.

    :param url: an url to load initially (can be ``None`` to skip loading)
    :param driver: a Selenium's WebDriver instance (can be ``None`` to create a default instance)
    :param headless_display: tells if a headless display should be created (and closed when doing a cleanup)_build/html
    :param extra_js_files: a list of javascript filenames that should be injected after every page load, in addition to these specified in :data:`JS_FILENAMES`.
    :param disable_cleanup: don't do cleanup when using a ``with`` statement (useful for debugging).
    :param auto_refresh: ignore ``refresh`` argument in load_url and refresh automatically when new domain is visited
    """

    def __init__(self, url=None, driver=None, headless_display=False, extra_js_files=[],
                 disable_cleanup=False, width=1366, height=768, auto_refresh=False,
                 load_no_images=False, custom_proxy=None, timeout=None):
        xcontext.current_xbrowser = self

        self._js_filenames = JS_FILENAMES + extra_js_files
        if not settings.DEBUG:
            self.disable_cleanup = False
        else:
            self.disable_cleanup = disable_cleanup
        self.auto_refresh = auto_refresh
        self.auto_visited_domains = set()

        self.display = None
        if headless_display:
            self.display = pyvirtualdisplay.Display(visible=0, size=(width, height))
            self.display.start()

        self.driver = None
        self.driver_owned = False
        if driver:
            self.driver = driver
            self.driver_owned = False
        else:
            self.driver = seleniumtools.create_default_driver(load_no_images=load_no_images,
                                                              custom_proxy=custom_proxy)
            self.driver_owned = True

        if isinstance(timeout, int):
            self.driver.set_page_load_timeout(timeout)

        self.url = None
        if url:
            self.load_url(url)

    def recreate_driver(self):
        if self.driver is None:
            return
        self.driver.quit()
        self.driver = seleniumtools.create_default_driver()
        self.driver_owned = True

    def add_js_file(self, filename):
        if filename not in self._js_filenames:
            self._js_filenames.append(filename)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()

    def inject_js(self):
        """Explicitly inject JS and JSON to the loaded document.
        """
        if self._is_js_initialized():
            log.debug('JS is already initialized')
            return False

        # Init JS global variables
        #log.debug('Init script loading')
        self._init_script_loading()
        #log.debug('Done')

        # Load JSON data
        #log.debug('Loading json')
        self._load_json()
        #log.debug('Done')

        # Load JS
        #log.debug('Loading js')
        if LOAD_JS_FILES_FROM_SERVER:
            self._load_js_from_server()
        else:
            self._load_js()
        return True

    def load_url(self, url, refresh=False):
        """Load the specified url and inject js/json.
        Optionally, refresh a page after a load.
        """
        log.debug('Loading url %s', url)
        self.url = url

        try:
            self.driver.get(self.url)
        except selenium.common.exceptions.TimeoutException as e:
            log.info("Timeout loading: %s", self.url)
            # Loads can timeout due to some rogue 3-rd party script failing to load in due
            # time. In that case most of our page is loaded and the DOM is responsive, so
            # we can work with it. If a "find" op succeeds and returns more than 0
            # elements, we assume the DOM is usable and continue.
            dom_loaded = False
            try:
                dom_loaded = len(self.driver.find_elements_by_tag_name('*')) > 0
            except:
                pass

            if not dom_loaded:
                raise e

        domain = utils.domain_from_url(url)

        if self.auto_refresh:
            do_refresh = domain not in self.auto_visited_domains
        else:
            do_refresh = refresh
        if do_refresh != refresh:
            log.warn('refresh argument overriden by auto_refresh setting')

        if do_refresh:
            # Refresh the page to close overlays
            log.debug('Refreshing page')
            self.driver.refresh()
            log.debug('Done')

        if self.auto_refresh:
            self.auto_visited_domains.add(domain)

        self.inject_js()

        self.current_tab_no = 0

        try:
            watchdog.validate_process(seleniumtools.driver_pid(self.driver))
        except:
            log.exception('While watchdog revalidating, ignoring')

        log.debug('Done')

    def xrefresh(self):
        """Refresh a page and re-inject JS/JSON.
        """
        log.debug('Refreshing page')
        self.driver.refresh()
        log.debug('Done')
        self.inject_js()

    def _load_js(self):
        #log.debug('Loading js files through selenium')
        filenames = [os.path.join(JS_DIR, f) for f in self._js_filenames]
        seleniumtools.load_js_files(self.driver, filenames)

    def _load_js_from_server(self):
        #log.debug('Loading js files from server %s', JS_FILE_SERVER)
        for filename in self._js_filenames:
            url = JS_FILE_SERVER + filename
            script = '''
            var se = document.createElement('script');
            se.setAttribute('src', '%s');
            document.getElementsByTagName('head').item(0).appendChild(se);
            ''' % url
            self.driver.execute_script(script)

    def _read_json(self, base_filename):
        with open(os.path.join(JSON_DIR, base_filename)) as f:
            return json.load(f)

    def _is_js_initialized(self):
        return self.driver.execute_script('return typeof _XPS !== "undefined";')

    def _init_script_loading(self):
        self.driver.execute_script('_XPS = new Object(); _XPS.jsonData = new Object();')
        self.driver.execute_script('netscape.security.PrivilegeManager.enablePrivilege("UniversalBrowserRead");')

    def _load_json(self):
        for filename in glob(os.path.join(JSON_DIR, '*.json')):
            base_filename = os.path.splitext(os.path.basename(filename))[0]
            self.driver.execute_script("_XPS.jsonData['%s'] = JSON.parse(%s)" % (base_filename,
                jsonData.load_to_js_string(os.path.basename(filename))))

    def quit_driver(self):
        """Quit the Selenium driver, if we created it.
        """
        if self.driver is not None and self.driver_owned:
            self.driver.quit()
            self.driver = None

    def quit_display(self):
        """Quit headless display.
        """
        if self.display is not None:
            self.display.stop()

    def cleanup(self):
        """Cleanup all things - quit driver and headless display.
        """
        try:
            if not self.disable_cleanup:
                self.quit_driver()
                self.quit_display()
            if getattr(xcontext, 'current_xbrowser', None) is self:
                del xcontext.current_xbrowser
        except:
            log.exception('While XBrowser.cleanup(), ignoring')

    def _current_el(self):
        return self.driver.find_element_by_tag_name('*')

    def create_new_tab(self):
        """Create new web browser tab using a keyboard shortcut.
        """
        current_el = self._current_el()
        current_el.send_keys(Keys.CONTROL + 't')
        self.driver.switch_to_default_content()

    def close_current_tab(self):
        """Close current browser's tab using a keyboard shortcut.
        """
        current_el = self._current_el()
        current_el.send_keys(Keys.CONTROL + 'w')
        time.sleep(1)
        self.switch_tab()

    def switch_tab(self):
        """Switch to the "next" tab using a keyboard shortcut.
        """
        current_el = self._current_el()
        current_el.send_keys(Keys.CONTROL + Keys.PAGE_DOWN)
        self.driver.switch_to_default_content()

    def compute_xpath(self, el, skip_unique=0):
        """Compute XPath for a web driver's element.
        """
        return self.execute_jsfun_safe(None, '_XPS.computeXPath', el, skip_unique)

    def execute_jsfun(self, fun, *args):
        """Execute Javascript function with args.
        """
        return seleniumtools.execute_jsfun(self.driver, fun, *args)

    def execute_jsfun_safe(self, safe_res, fun, *args):
        """Execute Javascript function with args, returning ``safe_res`` if an
        :class:`selenium.common.exceptions.NoSuchElementException` or
        :class:`selenium.common.exceptions.StaleElementReferenceException` exception
        happened.
        """
        try:
            return self.execute_jsfun(fun, *args)
        except (selenium.common.exceptions.NoSuchElementException,
                selenium.common.exceptions.StaleElementReferenceException):
            return safe_res

    def el_text(self, el):
        """Extract direct text content from an element.
        """
        try:
            text = self.execute_jsfun('_XPS.directTextContent', el)
            return text
        except selenium.common.exceptions.StaleElementReferenceException:
            return ''

    def el_text_xpath(self, xpath):
        """Extract direct text content from an element pointed by an xpath.
        """
        return self.execute_jsfun_safe(None, '_XPS.directTextContentXPath', xpath)

    def el_text_all(self, el):
        """Extract all text content inside an element (including children).
        """
        return self.execute_jsfun_safe('', '_XPS.textContentAll', el)

    def el_text_all_list(self, el):
        """Extract text content from an element and it's children as a list,
        a single element being text content of a single element.
        """
        return self.execute_jsfun_safe([], '_XPS.textContentAllList', el)

    def el_text_from_text_or_attr_values(self, el, max_text_length=30, include_attr_values=None):
        """Create a :class:`ElText` tuple of an element and text of the element (it non-empty)
        or it's attributes, specified as ``include_attr_values``.
        """
        if include_attr_values is None:
            include_attr_values = jsonData['attrs_with_text']
        text = self.execute_jsfun_safe(None, '_XPS.textOrAttrValues', el, max_text_length,
                include_attr_values)
        return ElText(el, text)

    def el_text_from_el(self, el):
        """Create an :class:`ElText` tuple of an element and it's direct text content.
        """
        return ElText(el=el, text=self.el_text(el))

    def el_size(self, el):
        """Size of an element, in pixels.
        """
        try:
            return self.execute_jsfun('_XPS.elementSize', el)
        except selenium.common.exceptions.StaleElementReferenceException:
            return -1

    def enrich_els_texts(self, pairs):
        return [ElText(p[0], p[1]) for p in pairs]

    def els_with_texts(self, invalid_tags, invalid_parent_tags, max_text_length, max_y=700,
            invalid_ancestor_names=[], include_attr_values=[], include_css_values=[]):
        """Executes a Javascript ``_XPS.getValidElementsWithText`` function that
        returns DOM elements fullfilling specified conditions.
        """
        pairs = self.execute_jsfun_safe([], '_XPS.getValidElementsWithText', invalid_tags,
            invalid_parent_tags, max_text_length, max_y, invalid_ancestor_names,
            include_attr_values, include_css_values)
        return self.enrich_els_texts(pairs)

    def el_font_size(self, el):
        """Font size of an element, computed using relevant CSS rules.
        """
        try:
            res = self.execute_jsfun('_XPS.getFontSize', el)
            return res or 0
        except selenium.common.exceptions.StaleElementReferenceException:
            return 0

    def els_min_distance(self, el1, el2, points_idxs=[0, 1, 2, 3]):
        """Minimal distance between middle-points of borders of two elements.
        """
        try:
            res = self.execute_jsfun('_XPS.minDistance', el1, el2, points_idxs)
            return res
        except (selenium.common.exceptions.NoSuchElementException,
                selenium.common.exceptions.StaleElementReferenceException):
            return sys.maxint

    def el_importance(self, el):
        """An importance score of an element based on it's tag.
        """
        try:
            res = self.execute_jsfun('_XPS.elementImportance', el)
            return res
        except (selenium.common.exceptions.NoSuchElementException,
                selenium.common.exceptions.StaleElementReferenceException):
            return 1.0

    def el_source(self, el):
        return self.execute_jsfun('_XPS.getElSource', el)

    def el_by_xpath(self, xpath):
        """Wraps Selenium's ``find_element_by_xpath`` function and checks
        for ``NoSuchElementException``, ``StaleElementReferenceException`` -
        returns ``None`` if such exception happened.
        """
        try:
            return self.driver.find_element_by_xpath(xpath)
        except (selenium.common.exceptions.NoSuchElementException,
                selenium.common.exceptions.StaleElementReferenceException):
            return None

    def els_by_xpath(self, xpath):
        """Same as :meth:`el_by_xpath`, but for multiple elements evaluated
        from an xpath expression.
        """
        try:
            return self.driver.find_elements_by_xpath(xpath)
        except (selenium.common.exceptions.NoSuchElementException,
                selenium.common.exceptions.StaleElementReferenceException):
            return []


def validate_url(url=None):
    """
    validates url to be a correct url, reconstructs urls like:
        //instagram.com/p/BBNxrh9E1cU
        instagram.com/p/BBNxrh9E1cU
    to their canonical form
    """
    if url is None:
        return None

    url = url.strip()

    # Complete unfinished url
    if url.startswith('//'):
        url = 'http:%s' % url
    if not (url.startswith('http://') or url.startswith('https://')):
        url = 'http://%s' % url

    # validate url
    try:
        parsed = urlparse.urlparse(url)

        # checking netloc -- without it that is definitely not an url
        if not parsed.netloc:
            log.info('No netloc found for url %s, returning None' % url)
            return None

        # checking schemes
        if not parsed.scheme:
            parsed = parsed._replace(scheme='http')
        if parsed.scheme not in ['http', 'https']:
            parsed = parsed._replace(scheme='http')

        return urlparse.urlunparse(parsed)

    except AttributeError as e:
        log.exception(e)
        return None


def redirect_using_xbrowser(url, xb=None, timeout=None, normalize_socials=False):
    """
    Check for redirection using selenium. Sometimes requests doesn't capture the redirect properly
    Using caching to prevent multiple selenium invocation for same urls.
    :param normalize_socials -- set this to True to normalize social url, otherwize l
    """
    def check_redirect(xb, normalize_socials_flag=False):
        xb.load_url(url)
        redirected_url = xb.driver.current_url

        if normalize_socials_flag:
            # unifying urls for socials
            parsed = urlparse.urlparse(redirected_url)
            if parsed.netloc.endswith('pinterest.com'):
                if parsed.path.endswith('/'):
                    parsed = parsed._replace(path=parsed.path[:-1])

            elif parsed.netloc.endswith('plus.google.com'):
                if parsed.path.endswith('/about'):
                    parsed = parsed._replace(path=parsed.path[:-6])

            elif parsed.netloc.endswith('youtube.com'):
                if parsed.path.endswith('/feed'):
                    parsed = parsed._replace(path=parsed.path[:-5])

            redirected_url = parsed.geturl()

        if redirected_url is not None:
            cache.set('redirect_url:%s:%s' % (normalize_socials_flag, url), redirected_url, 60*60*24)
        return redirected_url

    url_validated = validate_url(url)
    if url_validated is None:
        log.error('url %r is not valid' % url)
        return None
    else:
        url = url_validated

    # checking cache first
    cached_url = cache.get('redirect_url:%s:%s' % (normalize_socials, url))
    if cached_url is not None:
        return cached_url

    if xb is not None:
        return check_redirect(xb, normalize_socials)
    else:
        # Retrying if getting some exception with browser
        max_retries = 3
        tries = 0
        while tries < max_retries:
            try:
                with XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, load_no_images=True, timeout=timeout) as xb:
                    return check_redirect(xb, normalize_socials)
            except WebDriverException:
                log.info('Retrying getting redirect of url %s ...' % url)
                tries += 1
                time.sleep(10)


if __name__ == '__main__':
    # Just spawn a Firefox window with JS loaded
    # if this module is called from command line
    # (useful for fiddling with Javascript)
    assert len(sys.argv) == 2
    xb = XBrowser(url=sys.argv[1])
