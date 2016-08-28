"""Similar to :mod:`platformdatafetcher.blognamefetcher`, getting
a name of a brand algorithmically by computing a common substring over
a set of product pages.
"""

import logging
import itertools

import baker
import lxml.html
import requests
from celery.decorators import task

from xpathscraper import utils
from xpathscraper import xutils
from platformdatafetcher import platformutils
from debra import models


log = logging.getLogger('platformdatafetcher.brandnamefetcher')


BRAND_NAME_BLACKLIST = ['by', 'woman', 'women', 'man', 'men', 'at', '403 forbidden', '404 not found']
BRAND_NAME_UNWANTED_PREFIXES = ['by', 'at']
BRAND_NAME_BLACKLISTED_SUBSTRINGS = ['404', '403', 'error', 'not found', 'invalid', 'no such', 'search ',
                                     'results for']


class FromTitleBrandFetcher(object):

    def __init__(self, brand):
        self.brand = brand

    def fetch_brand_name(self, to_save=False):
        if not self.brand.domain_name:
            log.error('No domain set for %r', self.brand)
            return None
        url = 'http://%s' % self.brand.domain_name
        try:
            brand_name = xutils.fetch_title(url)
        except:
            log.exception('While fetching title')
            return None
        if not brand_name:
            log.warn('No brand_name from title for brand %r', self.brand)
            return None
        log.info('Found brand_name from platform %r: %r', self.brand, brand_name)
        self.brand.name = brand_name
        if to_save:
            self.brand.save()
        return brand_name


class CommonTitleFragmentBrandFetcher(object):

    STRIP_CHARS = ' \r\t|-*,.;:!#"\''

    def __init__(self, brand):
        self.brand = brand

    def _common_substr(self, titles):
        substr = utils.longest_substr(titles)
        substr = substr.strip(self.STRIP_CHARS)
        for prefix in BRAND_NAME_UNWANTED_PREFIXES:
            substr = utils.remove_prefix(substr, prefix, False).strip(self.STRIP_CHARS)
        return substr

    def _generate_titles_subsets(self, titles):
        res = []
        res.append(titles)

        if len(titles) == 2:
            return res

        res += list(itertools.combinations(titles, len(titles) - 1))

        if len(titles) == 3:
            return res

        res += list(itertools.combinations(titles, len(titles) - 2))

        return res

    def _result_from_subset(self, subset):
        substr = self._common_substr(subset)
        log.info('Common title fragment from %r: %r', subset, substr)
        if not substr \
                or len(substr) < 4 \
                or substr.lower() in BRAND_NAME_BLACKLIST \
                or any(ss in substr.lower() for ss in BRAND_NAME_BLACKLISTED_SUBSTRINGS):
            log.error('No valid common title fragment computed')
            return None
        return substr

    def fetch_brand_name(self, to_save=False):
        if not self.brand.domain_name:
            log.error('No domain set for %r', self.brand)
            return None

        sample_products = self.brand.productmodel_set.\
            filter(price__isnull=False).\
            exclude(price=-11.0).\
            order_by('-insert_date')\
            [:12]

        log.info('sample_products: %r', sample_products)

        titles = []
        for prod in sample_products:
            try:
                title = xutils.fetch_title(prod.prod_url)
            except:
                log.exception('While fetching title')
                continue
            if title:
                titles.append(title)
        
        titles = [t for t in titles \
                  if not any(ss in t.lower() for ss in BRAND_NAME_BLACKLISTED_SUBSTRINGS)]

        if len(titles) < 2:
            log.error('Not enough titles: %r', titles)
            return None

        subsets = self._generate_titles_subsets(titles)
        substr = None
        for subset in subsets:
            substr = self._result_from_subset(subset)
            if substr is not None:
                break

        if substr is None:
            log.warn('No substr computed, copying domain_name as brand.name')
            self.brand.name = self.brand.domain_name
        else:
            log.info('Setting new brand name to %r', substr)
            self.brand.name = substr
        if to_save:
            log.info('Saving changes to DB')
            self.brand.save()
        return self.brand.name


@task(name='platformdatafetcher.brandnamefetcher.fetch_brand_name', ignore_result=True)
@baker.command
def fetch_brand_name(brand_id, cls=CommonTitleFragmentBrandFetcher, to_save=True):
    brand = models.Brands.objects.get(id=int(brand_id))
    bf = cls(brand)
    res = bf.fetch_brand_name(to_save=to_save)
    log.info('Fetched brand_name from brand %r: %r', brand, res)
    return res

@baker.command
def fetch_brand_names_for_all():
    for brand in models.Brands.objects.filter(name__contains='.com').exclude(supported=True).order_by('id'):
        res = fetch_brand_name(brand.id)
        if res:
            log.critical('Domain: %r, Title: %r', brand.domain_name, res)

@baker.command
def fetch_brand_names_for_invalid():
    for brand in models.Brands.objects.exclude(supported=True).order_by('id'):
        if any(x in brand.name for x in BRAND_NAME_BLACKLISTED_SUBSTRINGS):
            log.info('Running for %r', brand)
            res = fetch_brand_name(brand.id, to_save=True)
            log.critical('Domain: %r, Title: %r', brand.domain_name, res)

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

