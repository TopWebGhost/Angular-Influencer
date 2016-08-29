import logging
import time

from django.conf import settings
import requests
import baker
from xpathscraper import utils
from xpathscraper import xbrowser


log = logging.getLogger('servermonitoring.cachewarming')

URLS_TO_FETCH_AND_SCROLL = [
    'http://app.theshelf.com/explore/inspiration/',
]

URLS_TO_FETCH_SIMPLE_PAGE_NOS = [
    'http://app.theshelf.com/cacherefresh/instagram-feed-json/?pageInst={page_no}',
    'http://app.theshelf.com/cacherefresh/product-feed-json/?pageProd={page_no}',
    'http://app.theshelf.com/cacherefresh/blog-feed-json/?pageBlog={page_no}',
]

MAX_PAGE_NUM = 5

URLS_TO_FETCH_SIMPLE = [u.format(page_no=page_no) for page_no in range(1, MAX_PAGE_NUM+1) \
                                                  for u in URLS_TO_FETCH_SIMPLE_PAGE_NOS]

@baker.command
def fetch_urls_and_scroll(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY):
    for url in URLS_TO_FETCH_AND_SCROLL:
        try:
            with xbrowser.XBrowser(headless_display=False, extra_js_files=['cachewarming.js']) as xb:
                xb.load_url(url)
                xb.execute_jsfun('_CW.scroll')
                time.sleep(120)
        except:
            log.exception('While getting %r', url)
            continue
        log.info('Fetched %r successfully', url)

@baker.command
def fetch_urls_simple():
    log.info('Urls to simple fetch: %s', URLS_TO_FETCH_SIMPLE)
    for url in URLS_TO_FETCH_SIMPLE:
        try:
            r = requests.get(url, timeout=600)
            log.info('Fetched from %r:\n%s', r.url, r.text)
        except:
            log.exception('While getting %r', url)
            continue


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
