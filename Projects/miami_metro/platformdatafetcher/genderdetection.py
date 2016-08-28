"""Detect a gender (men/women) for which a product is made. Currently the algorithm only
counts numbers of "men", "women" words encountered.
"""

import logging
from collections import namedtuple

import baker
from celery.decorators import task

from xpathscraper import utils
from xpathscraper import xbrowser as xbrowsermod
from xpathscraper import scraper as scrapermod
from xpathscraper import resultsenrichment
from xpathscraper import scrapingresults


log = logging.getLogger('platformdatafetcher.genderdetection')


KeywordCounts = namedtuple('KeywordCounts', ['men', 'women'])


def count(text):
    text = text.lower()
    women_count = text.count('women')
    text = text.replace('women', '')
    men_count = text.count('men')
    return KeywordCounts(men=men_count, women=women_count)

def sum_keyword_counts(kcs):
    return KeywordCounts(men=sum(kc.men for kc in kcs), women=sum(kc.women for kc in kcs))


@baker.command
def detect_gender(product_url):
    """Returns 'men', 'women' or 'unknown'
    """

    log.info('Detecting gender for %r', product_url)
    texts = []

    with xbrowsermod.XBrowser(url=product_url, headless_display=False, disable_cleanup=True) as xbrowser:
        url = xbrowser.driver.current_url
        log.info('Current url: %r', url)
        texts.append(url)

        scraper = scrapermod.Scraper(xbrowser)
        name_srs = scraper.get_name_xpaths()
        evaluator = scrapingresults.ResultEvaluator(scraper)
        name = evaluator.compute_values(name_srs[0], 'name')
        log.info('Found name: %r', name)
        texts.append(name)

        title = xbrowser.driver.title
        log.info('Found title: %r', title)
        texts.append(title)

        description_els = xbrowser.driver.find_elements_by_xpath('//meta[@name="description"]')
        if description_els:
            description = description_els[0].get_attribute('content')
            log.info('Found description: %r', description)
            texts.append(description)

        keywords_els = xbrowser.driver.find_elements_by_xpath('//meta[@name="keywords"]')
        if keywords_els:
            keywords = keywords_els[0].get_attribute('content')
            log.info('Found keywords: %r', keywords)
            texts.append(keywords)

    kcs = []
    for text in texts:
        kc = count(text)
        log.info('%r %r', kc, text)
        kcs.append(kc)

    res = sum_keyword_counts(kcs)
    log.info('Result: %s', res)
    if res.men > res.women:
        return 'men'
    if res.men == res.women:
        return 'unknown'
    return 'women'

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

