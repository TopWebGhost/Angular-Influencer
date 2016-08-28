import logging
import time

import baker
from celery.decorators import task
import requests
import lxml.html
from django.conf import settings
from selenium.webdriver.support.ui import WebDriverWait

from xpathscraper import utils
from xpathscraper import xbrowser


log = logging.getLogger('platformdatafetcher.producturlsextractor')


class ProductUrlsExtractor(object):

    supported_domains = []

    def extract_product_urls(self, url):
        raise NotImplementedError()


class LiketkExtractor(ProductUrlsExtractor):

    supported_domains = ['liketoknow.it', 'liketk.it']

    def extract_product_urls(self, url):
        try:
            with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
                xb.load_url(url)
                anchors = WebDriverWait(xb.driver, 10).until(
                    lambda _: xb.els_by_xpath('//div[@class="hoverflow"]//a')
                )
                anchors = [a for a in anchors if a.get_attribute('href') and \
                           utils.domain_from_url(a.get_attribute('href')) == 'rstyle.me']
                urls = utils.unique_sameorder(a.get_attribute('href') for a in anchors)
                return urls
        except Exception as e:
            log.exception(e, extra={'url': url})
            return None

CLASSES = [
    LiketkExtractor,
]

ALL_SUPPORTED_DOMAINS = {dom for cls in CLASSES for dom in cls.supported_domains}

@baker.command
def do_extract_product_urls(url):
    domain = utils.domain_from_url(url)
    matching_classes = [cls for cls in CLASSES if domain in cls.supported_domains]
    res = []
    for cls in matching_classes:
        e = cls()
        e_res = e.extract_product_urls(url)
        log.info('%r extracted product urls: %r', e, e_res)
        res += e_res
    res = utils.unique_sameorder(res)
    log.info('All product urls extracted from %r: %r', url, res)
    return res


def get_blog_url_from_liketoknowit(liketoknowit_url=None, xb=None):
    """
    Function to extract user's blog url from her http://liketoknow.it/<username> page.
    :param liketoknowit_url: url to liketoknowit page
    :return: blog url
    """
    def get_the_blog_url(xb, liketoknowit_url):
        xb.load_url(liketoknowit_url)

        anchors = WebDriverWait(xb.driver, 10).until(
            lambda _: xb.els_by_xpath('//publisher-header//h5//a')
        )
        anchors = [a for a in anchors if a.get_attribute('href')]
        urls = utils.unique_sameorder(a.get_attribute('href') for a in anchors)

        return urls[0] if len(urls) > 0 else None

    if liketoknowit_url is None:
        return None

    try:
        if xb is None:
            with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
                return get_the_blog_url(xb, liketoknowit_url)
        else:
            return get_the_blog_url(xb, liketoknowit_url)

    except Exception as e:
        log.exception(e, extra={'url': liketoknowit_url})
        return None


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
