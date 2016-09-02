from __future__ import absolute_import, division, print_function, unicode_literals
import re
import logging
import time
import random
from datetime import datetime
from django.conf import settings
from xpathscraper import xbrowser
from . import twitter_utils


log = logging.getLogger('social_discovery.google_search')


class GoogleSearcher(object):
    _GOOGLE_PAGE_SIZE = 10

    def __init__(self, xb=None):
        self.xb = xb

        self.xb.load_url('https://www.google.com/')

    def search(self, query):
        input_el = self.xb.driver.find_element_by_xpath('//input[@type="text"]')
        input_el.send_keys(query)
        time.sleep(2)
        self._find_search_button().click()
        time.sleep(10)

    def goto_page(self, page):
        self._sleep_before_navigation()
        try:
            page_link = self.xb.driver.find_element_by_xpath('//table[@id="nav"]//a[contains(@href, "start=")]')
        except:
            timestamp = '%d-%02d-%02d-%02d-%02d-%02d' % datetime.utcnow().timetuple()[:6]
            self.xb.driver.save_screenshot('/tmp/google-search-%s.png' % timestamp)
            raise

        start_offset = page * self._GOOGLE_PAGE_SIZE
        current_url = page_link.get_attribute('href')
        new_url = re.sub(r'start=\d+', 'start=%d' % start_offset, current_url)

        # A JS hack to set the 'href' attribute (the Selenium API can't do it)
        self.xb.driver.execute_script(
            'return arguments[0].setAttribute("href", arguments[1])',
            page_link,
            new_url,
        )
        page_link.click()

        # A lame way of waiting for results to load
        time.sleep(10)

    def get_current_results(self):
        els = self.xb.driver.find_elements_by_xpath('//cite')
        res = [el.text for el in els]
        return res

    def _sleep_before_navigation(self):
        to_sleep = random.randrange(10, 20)
        time.sleep(to_sleep)

    def _find_search_button(self):
        buttons = self.xb.driver.find_elements_by_tag_name('button')

        matching = [b for b in buttons if b.get_attribute('aria-label') == 'Google Search']
        if not matching:
            matching = [b for b in buttons if b.get_attribute('aria-label').startswith('Google')]

        if not matching:
            raise Exception('No "Google Search" button')

        return matching[0]


def get_twitter_profiles_with_bio(bio_search_query, page=0):
    full_query = (
        "site:twitter.com bio:*%s* "
        "-inurl:status "
        "-inurl:hashtag "
        "-inurl:lists "
        "-inurl:blog.twitter.com "
        "-intitle:google"
    ) % bio_search_query

    with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, load_no_images=True) as xb:
        searcher = GoogleSearcher(xb)
        searcher.search(full_query)
        if page > 0:
            searcher.goto_page(page)

        results = searcher.get_current_results()
        twitter_profiles = [twitter_utils.screen_name_for_url(result) for result in results]
        return [profile for profile in twitter_profiles if profile is not None]
