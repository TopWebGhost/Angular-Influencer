from __future__ import absolute_import, division, print_function, unicode_literals
import feedparser
import requests
from xpathscraper import utils
# speedparser is a faster feedparser replacement, but using it is still
# experimental. There is no way of knowing if it handles the feeds we parse in
# the same way as feedparser does.
#
#import speedparser
import socket
from urlparse import urlparse


FEED_FETCH_TIMEOUT = 20
USE_REQUESTS = True


class RequestsFileLike(object):
    '''
    A file-like object that feedparser can read() from.

    We use it as a way to replace the built-in HTTP transport with requests. Requests
    handles cookies, redirects, etc.
    '''

    def __init__(self, url):
        self.url = url

    def read(self):
        # TODO: raising a chardet unicode detection error on 404 feed responses
        # ValueError: Expected a bytes object, not a unicode object
        # e.g. http://www.hautemimi.com/feed/asdfasdfas
        try:
            # We encountered this kind of 'smart' feeds: http://feeds.feedblitz.com/freebiefindingmom
            # It will render html page when finds user-agent, otherwise it provides an xml Atom feed.
            # So trying to checking url's domain and then behave correspondingly

            # setting verify=True to bypass SSL certificate validation for some blogs
            # http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification

            is_feedblitz = urlparse(self.url).netloc == 'feeds.feedblitz.com'

            r = requests.get(
                self.url,
                timeout=FEED_FETCH_TIMEOUT,
                headers=None if is_feedblitz else utils.browser_headers(),
                verify=False
            )

            # extra check if it was a redirect to feedblitz
            if not is_feedblitz and urlparse(r.url).netloc == 'feeds.feedblitz.com':
                self.url = r.url
                r = requests.get(
                    self.url,
                    timeout=FEED_FETCH_TIMEOUT,
                    verify=False
                )

            r.raise_for_status()
            self.content = r.content
            self.headers = r.headers
        except requests.RequestException:
            self.content = b''
            self.headers = {}

        return self.content

    def close(self):
        pass


def parse(feed_url):
    """
    A facade sitting between us and feed parser libraries.

    Sets and cleans up the global socket timeout. No other way to configure it for feedparser.
    """

    try:
        current_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(FEED_FETCH_TIMEOUT)

        parsable = feed_url
        if USE_REQUESTS:
            parsable = RequestsFileLike(feed_url)
        return feedparser.parse(parsable)
    finally:
        socket.setdefaulttimeout(current_timeout)

    #return speedparser.parse(feed_url)
