# -*- coding: utf-8 -*-
"""Computes content classification for an influencer or a brand.
The result of a classification is one of:

- ``brand``
- ``blog``
- ``social``
- ``squatter``
- ``unknown``
"""

import logging
import urlparse
import uuid

import baker
from django.conf import settings
import requests
from celery.decorators import task
import nltk
import lxml
import lxml.html
from requests.exceptions import SSLError

from xpathscraper import utils
from xpathscraper import xutils
from xpathscraper import xbrowser
from xpathscraper import scraper as scrapermod
from debra import models
from platformdatafetcher import (
    platformutils,
    blognamefetcher,
)


log = logging.getLogger('platformdatafetcher.contentclassification')


SITETYPE_BRAND = 'brand'
SITETYPE_BLOG = 'blog'
SITETYPE_SOCIAL = 'social'
SITETYPE_SQUATTER = 'squatter'
SITETYPE_UNKNOWN = 'unknown'

SQUATTER_DOMAIN_KEYWORDS = [
    'premium domain name',
    'this domain is registered',
    'site is under construction',
    'aftermarket.com',
    'sedo.com',
    'domain may be for sale',
    'domain is listed',
    'buydomains.com',
    'alt="godaddy.com"',
]

NOT_FOUND_PAGE_KEYWORDS = [
    'moved or deleted',
    'error in the url',
    'not found',
    'please check the url',
]

BLOG_KEYWORDS = [
    'bloglovin.com',
    'blogger.com/profile',
    'brandbacker.com',
    'influenster.com',
    'bloggersrequired.com',
    'mombuzzmedia.com',
    'sverve.com/profile/',
    'thenicheparent.com',
    'doubledutydivas.com',
    'clevergirlscollective.com',
    'rstyle.com',
    'shopstyle.com',
    'bzzagent.com',
    'yummymummyclub.ca',
    'sheblogsmedia.com',
    'lookbook.nu',
    'more posts',
]


class ClassificationTarget(object):
    def __init__(self, url):
        self.url = url
        self.content = None

        self.fetch()

    def fetch(self):
        attempts = 0
        while attempts < 3:
            try:
                try:
                    r = requests.get(self.url, timeout=10, headers=utils.browser_headers())
                except SSLError:
                    r = requests.get(self.url, timeout=10, headers=utils.browser_headers(), verify=False)

                self.content = r.content
                self.http_status_code = r.status_code
                self.http_headers = r.headers
                attempts = 9999
            except:
                log.exception('While fetching content for classification from: {}'.format(self.url))
                attempts += 1

    def site_gone(self):
        return self.http_status_code in (404, 410)

    @property
    def tree(self):
        if not hasattr(self, '_tree'):
            if not self.content:
                return None

            self._tree = lxml.html.fromstring(self.content)
        return self._tree


class Classifier(object):
    def classify(self, url):
        log.info('Classifying %r', url)

        # run testing functions, starting from least expensive
        if self._url_is_social(url):
            return SITETYPE_SOCIAL

        # This test can give wrong results, because there are influencers
        # with random blog_urls
        # if self._is_blog_in_db(url):
        #    return SITETYPE_BLOG

        target = ClassificationTarget(url)
        if target.content is None:
            return SITETYPE_UNKNOWN

        if target.site_gone():
            return SITETYPE_SQUATTER

        if self._contains_blog_tags(target, url):
            print("contains blog tags")
            return SITETYPE_BLOG

        if self._contains_blog_keyword(target):
            print("contains blog keywords")
            return SITETYPE_BLOG

        if self._contains_blog_keyword_canonical_page(target):
            print("contains blog keywords on canonical page")
            return SITETYPE_BLOG

        # Classify blogspot/wordpress URL's as blog *after* running the squatter check
        # to avoid classifying deleted blogs as such
        domain = utils.domain_from_url(url).lower()
        if 'blogspot' in domain or 'wordpress.com' in domain or 'tumblr.com' in domain:
            return SITETYPE_BLOG

        if 'etsy.com' in domain:
            return SITETYPE_BRAND
        # these both give false positives
        #if self._contains_trackback_links(target):
        #    print("contains traceback")
        #    return SITETYPE_BLOG

        #if self._has_feed(url):
        #    print("contains feed")
        #    return SITETYPE_BLOG

        if self._contains_typical_blog_xpaths(url):
            print("contains xpaths")
            return SITETYPE_BLOG

        if self._contains_squatter_keyword(target):
            return SITETYPE_SQUATTER

        if not self._correctly_handles_random_page(url):
            return SITETYPE_SQUATTER

        # Check for a brand not hosted on blogspot/wordpress.com
        if self._has_mostly_valid_products(url):
            return SITETYPE_BRAND
        try:
            if self._contains_checkout_or_addtocart(url):
                return SITETYPE_BRAND
        except:
            log.exception('While _contains_checkout_or_addtocart')

        return SITETYPE_UNKNOWN

    def _contains_blog_tags(self, target, url):
        try:
            return xutils.contains_blog_metatags(content=None, tree=target.tree) is not None
        except:
            log.exception("Couldn't find blog metatags in url: ".format(url))
            return False

    def _contains_trackback_links(self, target):
        for tag in target.tree.xpath('//link'):
            rel = tag.attrib.get('rel')
            if rel in ['traceback', 'pingback']:
                return True

        return False

    def _has_feed(self, url):
        from platformdatafetcher import feeds
        try:
            # Use the requests-powered feed parser
            return feeds.discover_feed(url) is not None
        except:
            log.exception("Couldn't discover feed url while classifying: ".format(url))
            return False

    def _contains_typical_blog_xpaths(self, url):
        from . import fetch_blog_posts_manually
        return fetch_blog_posts_manually.check_xpaths_exists_in_url(url)

    def _has_mostly_valid_products(self, url):
        domain = utils.domain_from_url(url)
        brand_q = models.Brands.objects.filter(domain_name=domain)
        if not brand_q.exists():
            log.info('No brands for domain %r', domain)
            return False
        brand = brand_q[0]
        if brand.supported:
            log.info('Brand is supported, so it must be valid')
            # return True
        valid_products = brand.productmodel_set.\
            filter(price__isnull=False).\
            exclude(price=-11).\
            count()
        invalid_products = (brand.productmodel_set.filter(price__isnull=True) |
                            brand.productmodel_set.filter(price=-11)).\
            count()
        log.info('Brand %r has %d valid and %d invalid products', brand, valid_products,
                 invalid_products)
        if valid_products + invalid_products < 5:
            log.info('The number of products is too small to make an estimation')
            return False
        # 60% must be valid
        if float(valid_products) / float(valid_products + invalid_products) > 0.60:
            log.info('Large number of products have valid prices, assuming it is a brand')
            return True
        log.info('The number of valid products is too small')
        return False

    def _url_is_social(self, url):
        is_social = platformutils.social_platform_name_from_url(None, url) != \
            platformutils.PLATFORM_NAME_DEFAULT
        if is_social:
            log.info('%r is social platform url', url)
            return True
        log.info('%r is not an social url', url)
        return False

    def _is_blog_in_db(self, url):
        if models.Influencer.find_duplicates(url):
            log.info('Found Influencer having this blog url')
            return True
        if models.Platform.objects.filter(platform_name__in=models.Platform.BLOG_PLATFORMS,
                                          url=url).exists():
            log.info('Found blog platform having this url')
            return True
        log.info('No blog / platform in DB found')
        return False

    def _contains_checkout_or_addtocart(self, url):
        try:
            with xbrowser.XBrowser(url=url,
                                   headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
                scraper = scrapermod.Scraper(xb)
                if scraper.get_checkoutbutton_xpaths():
                    log.info('%r contains checkoutbutton', url)
                    return True
                if scraper.get_addtocart_xpaths():
                    log.info('%r contains addtocart', url)
                    return True
                log.info('%r does not contain addtocart or checkoutbutton', url)
                return False
        except Exception as e:
            log.exception(e, exc_info=1, extra={'url': url})

    def _contains_blog_keyword(self, target):
        for kw in BLOG_KEYWORDS:
            if kw.lower() in target.content.lower():
                log.info('Found blog keyword %r', kw)
                return True
        log.info('No blog keyword found')
        return False

    def _contains_blog_keyword_canonical_page(self, target):
        """
        This variant of _contains_blog_keyword works with scriptless version of page if it is implemented by the site
        :param target:
        :return:
        """
        # we have <meta name="fragment" content="!">, loading and checking blog words in canonical version of the page
        if len(target.tree.xpath("//meta[@name='fragment'][@content='!']")) > 0:
            log.info('Checking canonical page for tags')
            try:
                url_parsed = urlparse.urlparse(target.url)
                new_url = '%s://%s/?_escaped_fragment_' % (url_parsed.scheme, url_parsed.netloc)
                try:
                    r = requests.get(new_url, timeout=10, headers=utils.browser_headers())
                except SSLError:
                    r = requests.get(new_url, timeout=10, headers=utils.browser_headers(), verify=False)

                content = r.content.lower()
                for kw in BLOG_KEYWORDS:
                    log.info('Checking %s' % kw)
                    if kw.lower() in content:
                        log.info('Found blog keyword %r in canonical page', kw)
                        return True
            except Exception as e:
                log.exception(e)

        return False

        #
        #
        # for kw in BLOG_KEYWORDS:
        #     if kw.lower() in target.content.lower():
        #         log.info('Found blog keyword %r', kw)
        #         return True
        # log.info('No blog keyword found')
        # return False

    def _correctly_handles_random_page(self, url):
        parsed = urlparse.urlsplit(url)
        parsed = parsed._replace(path='/' + uuid.uuid4().get_hex())
        try:
            r = requests.get(urlparse.urlunsplit(parsed), timeout=5)
        except:
            log.exception('While getting random page')
            return True
        if r.status_code == 200 and not any(kw in r.content.lower() for kw in NOT_FOUND_PAGE_KEYWORDS):
            log.info('%r incorrectly handles non-existing pages', url)
            return False
        log.info('%r: good handling of non-existing pages', url)
        return True

    def _contains_squatter_keyword(self, target):
        return any(kw in target.content for kw in SQUATTER_DOMAIN_KEYWORDS)


@task(name='platformdatafetcher.contentclassification.check_if_copyrightable_content', ignore_result=True)
@baker.command
def check_if_copyrightable_content(influencer_id):
    influencer = models.Influencer.objects.get(id=int(influencer_id))
    with platformutils.OpRecorder(operation='check_if_copyrightable_content', influencer=influencer):
        res = False
        r = requests.get(influencer.blog_url, timeout=20)
        text = xutils.strip_html_tags(r.text)
        if u'©' in text:
            res = True
        else:
            words = nltk.wordpunct_tokenize(text)
            if 'copyright' in words:
                res = True
        log.info('Copyrightable content for %r: %r', influencer, res)
        influencer.copyrightable_content = res
        influencer.save()
        return res


@task(name='platformdatafetcher.contentclassification.classify_model', ignore_result=True)
def classify_model(brand_id=None, influencer_id=None):
    # we are processing only one id, either an influencer or a brand
    assert brand_id is not None or influencer_id is not None
    assert not (brand_id is not None and influencer_id is not None)
    opr_kwargs = {'operation': 'content_classification'}
    if brand_id is not None:
        m = models.Brands.objects.get(id=brand_id)
        url = 'http://%s' % m.domain_name
        opr_kwargs['brand'] = m
    else:
        m = models.Influencer.objects.get(id=influencer_id)
        url = m.blog_url
        opr_kwargs['influencer'] = m
    with platformutils.OpRecorder(**opr_kwargs) as opr:
        c = Classifier()
        res = c.classify(url)
        log.info('Classified object %r url %r as %r', m, url, res)
        opr.data = {'result': res}
        m.save_classification(res)


@task(name='platformdatafetcher.contentclassification.submit_classify_model_and_fetch_blogname_tasks',
      ignore_result=True)
@baker.command
def submit_classify_model_and_fetch_blogname_tasks(submission_tracker):
    infs = models.Influencer.objects.filter(classification__isnull=True, source__isnull=False, blog_url__isnull=False)
    infs = infs.exclude(blog_url__contains='theshelf.com/artificial')
    infs = infs.exclude(validated_on__contains='info')
    infs = infs.exclude(show_on_search=True)
    for inf in infs:
        submission_tracker.count_task('influencer_classification')
        classify_model.apply_async(kwargs={'influencer_id': inf.id},
                                   queue='influencer_classification')


@baker.command
def run_for_brands():
    c = Classifier()
    for b in models.Brands.objects.all():
        try:
            res = c.classify('http://%s' % b.domain_name)
            log.info('Classification result %r for %r', res, b)
            b.classification = res
            b.save()
        except:
            log.exception('While classify()')


@baker.command
def run_for_influencers():
    c = Classifier()
    for inf in models.Influencer.objects.filter(is_live=True):
        try:
            res = c.classify(inf.blog_url)
            log.info('Classification result %r for %r', res, inf)
            inf.classification = res
            inf.save()
        except:
            log.exception('While classify()')


@baker.command
def test_brands_classification():
    brands = models.Brands.objects.filter(supported=True)
    c = Classifier()
    for b in brands:
        res = c.classify('http://%s' % b.domain_name)
        log.info('Classification result %r for %r', res, b)
        if res == SITETYPE_BRAND:
            log.info('+++ Good result for %r', b)
        else:
            log.info('--- Wrong result for %r', b)


@baker.command
def test_blogs_classification():
    blogs = models.Platform.objects.filter(platform_name__in=models.Platform.BLOG_PLATFORMS)[:200]
    c = Classifier()
    for b in blogs:
        res = c.classify(b.url)
        log.info('Classification result %r for %r', res, b)
        if res == SITETYPE_BLOG:
            log.info('+++ Good result for %r', b)
        else:
            log.info('--- Wrong result for %r', b)


def classify(url):
    return Classifier().classify(url)


@baker.command
def random_page_test(url):
    print Classifier()._correctly_handles_random_page(url)


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
