"""High level definitions for fetchers, including a configuration of fetcher
classes used for fetching.
"""

import inspect
import json
import logging

import requests
from requests.exceptions import HTTPError

from debra import models
from platformdatafetcher import feeds
from platformdatafetcher import fetcherbase
from platformdatafetcher import videohostingfetcher
from platformdatafetcher.platformextractor import REQUESTS_HEADERS
from xpathscraper import utils, xutils
from . import (
    contentfiltering, pbfetcher, blogfetcher, socialfetcher,
    squarespacefetcher, platformutils,
)


log = logging.getLogger('platformdatafetcher.fetcher')

FETCHER_CLASSES = [
    #blogfetcher.WordpressFetcher,
    feeds.WordpressFF,

    #customblogsfetcher.CustomBlogsFetcher,
    feeds.CustomFF,

    #blogfetcher.BloggerFetcherREST,
    #blogspotfetcher.BlogspotFetcher,
    feeds.BlogspotFF,

    blogfetcher.TumblrFetcher,
    socialfetcher.TwitterFetcher,

    # https://app.asana.com/0/38788253712150/102912414897013
    squarespacefetcher.SquarespaceFetcher,

    #socialfetcher.InstagramFetcher,
    socialfetcher.InstagramScrapingFetcher,
    socialfetcher.FacebookFetcher,
    socialfetcher.PinterestFetcher,
    socialfetcher.GPlusFetcher,
    socialfetcher.BloglovinFetcher,
    videohostingfetcher.YoutubeFetcher,
]

PLATFORM_NAME_TO_FETCHER_CLASS = {cls.name: cls for cls in FETCHER_CLASSES}

# A second set of classes that can be inserted into Paltform.fetcher_class
# field when a fetcher from the default list doesn't work.
FETCHER_CLASSES_ALTERNATIVE = [
            blogfetcher.WordpressFetcher,
            blogfetcher.BloggerFetcherREST,
]

FETCHER_CLASSES_ALTERNATIVE_BY_NAME = {cls.__name__: cls for cls in FETCHER_CLASSES_ALTERNATIVE}

PLATFORM_NAME_TO_FETCHER_CLASS_ALTERNATIVE = {cls.name: cls for cls in FETCHER_CLASSES_ALTERNATIVE}


class UnknownPlatformName(Exception):
    pass


def get_alternative_fetcher_class_name(platform):
    if platform.platform_name not in PLATFORM_NAME_TO_FETCHER_CLASS_ALTERNATIVE:
        return None
    return PLATFORM_NAME_TO_FETCHER_CLASS_ALTERNATIVE[platform.platform_name].__name__


def fetcher_class_changed_recently(platform):
    # TODO: temporarily disabling recent fetcher class change.
    return False

    if not platform.fetcher_class:
        return False
    latest_fetch_data = platform.platformdataop_set.filter(operation='fetch_data').\
        filter(data_json__contains='fetcher_class').\
        order_by('-id')
    if not latest_fetch_data.exists():
        return False
    pdo = latest_fetch_data[0]
    data = json.loads(pdo.data_json)
    fc = data.get('fetcher_class')
    if not fc:
        return False
    log.debug('fetcher class from platform: %r, pdo: %r', platform.fetcher_class, fc)
    return platform.fetcher_class != fc


def fetcher_for_platform(platform, policy=None):
    """Create a :class:`~platformdatafetcher.fetcherbase.Fetcher` instance suitable
    for fetching data for a given platform.

    :param platform: a Platform model for which to create a fetcher
    :param policy: a :class:`~platformdatafetcher.pbfetcher.Policy` passed to a fetcher. If
    ``None``, a policy is searched for based on ``platform.influencer`` field.

    """
    if platform.platform_name not in PLATFORM_NAME_TO_FETCHER_CLASS:
        raise UnknownPlatformName(platform.platform_name)
    if policy is None:
        policy = pbfetcher.policy_for_platform(platform)
    if platform.fetcher_class:
        if platform.fetcher_class not in FETCHER_CLASSES_ALTERNATIVE_BY_NAME:
            log.error('Platform %r specified non-listed alternative fetcher class %s, using default',
                      platform, platform.fetcher_class)
            cls = PLATFORM_NAME_TO_FETCHER_CLASS[platform.platform_name]
        else:
            log.info('Using alternative fetcher class %s', platform.fetcher_class)
            cls = FETCHER_CLASSES_ALTERNATIVE_BY_NAME[platform.fetcher_class]
    else:
        cls = PLATFORM_NAME_TO_FETCHER_CLASS[platform.platform_name]
    res = cls(platform, policy)
    res.new_fetcher_class = fetcher_class_changed_recently(platform)
    log.debug('new_fetcher_class: %s', res.new_fetcher_class)
    return res


def detect_platform_name_from_content(url):
    for content in utils.fetch_iframes(url):
        platform_name = xutils.contains_blog_metatags(content)
        if not platform_name:
            return None
        else:
            return (platform_name, url)

    return None


def try_detect_platform_name(url):
    """Based on url return (platform_name, possibly_corrected_url) tuple.
    If it cannot be detected, (None, None) is returned.

    UPDATED: updating FETCHER_CLASSES with blogfetcher.BloggerFetcherREST so that we make sure to use the API-based crawler
    """
    try:
        content_res = detect_platform_name_from_content(url)
    except:
        log.exception('While detect_platform_name_from_content, ignoring')
    else:
        if content_res:
            log.info('Detected platform name from content: %r', content_res)
            return content_res

    classes_to_check = FETCHER_CLASSES[:]
    if blogfetcher.BloggerFetcherREST not in classes_to_check:
        classes_to_check.append(blogfetcher.BloggerFetcherREST)
    for fc in classes_to_check:
        try:
            log.info("Trying %s " % fc.name)
            res = fc.belongs_to_site(url)
            if res:
                if isinstance(res, tuple):
                    return res
                return (fc.name, res)
        except HTTPError:

            log.info("Didn't find %s in %s " % (url, fc.name))

    return (None, None)


def try_get_social_description(url, xb=None, extra_fields=False):
    social_pl_name = platformutils.social_platform_name_from_url(None, url)
    if social_pl_name == platformutils.PLATFORM_NAME_DEFAULT:
        return None
    fc = PLATFORM_NAME_TO_FETCHER_CLASS.get(social_pl_name)
    if fc is None:
        return None
    try:
        # check if dynamically obtained class's get_description method has 'extra_fields' arg
        if 'extra_fields' in inspect.getargspec(fc.get_description).args:
            return fc.get_description(url, xb=xb, extra_fields=extra_fields)
        else:
            return fc.get_description(url, xb=xb)
    except:
        log.exception('While try_get_social_description')
    return None


def create_platforms_from_text(text, use_api=False, additional_fields=False):
    if not text:
        return []
    urls = set(contentfiltering.find_important_urls(text))
    urls.update(contentfiltering.re_find_urls(text))
    return create_platforms_from_urls(urls, use_api)


def create_single_platform_from_url(url, use_api=False, platform_name_fallback=False):
    """
    :return: a :class:`debra.models.Platform` instance (not saved)
    :param url: an url for which to create a platform
    :param use_api: if to use api calls to detect platform_name (can result in an exception)
    :param platform_name_fallback: if platform_name cannot be detected, this tells if a platform with platform_name ``None`` should be created.
    :raises UnknownPlatformName: when ``platform_name_fallback == False`` and platform_name could not be detected
    :raises FetcherException: when ``platform_name_fallback == False`` and ``use_api == True`` and there was a fetcher error during platform name detection
    :raises requests.RequestException: when url resolving fails
    """

    # This can result in an exception, so we'are skipping this
    # url = utils.resolve_http_redirect(url)

    social_pl_name = platformutils.social_platform_name_from_url(None, url)
    if social_pl_name != platformutils.PLATFORM_NAME_DEFAULT:
        return models.Platform(platform_name=social_pl_name, url=url)
    handle = platformutils.url_to_handle(url)
    if handle.endswith('blogspot.com'):
        return models.Platform(platform_name='Blogspot', url=url)
    if handle.endswith('wordpress.com'):
        return models.Platform(platform_name='Wordpress', url=url)
    if handle.endswith('tumblr.com'):
        return models.Platform(platform_name='Tumblr', url=url)

    # checking for Squarespace platform
    # Checking for 'This is Squarespace.' in page's content.
    try:
        r = requests.get(url=url, timeout=20, headers=REQUESTS_HEADERS)
        r.raise_for_status()
        if '<!-- This is Squarespace. -->' in r.content:
            return models.Platform(platform_name='Squarespace', url=url)
    except:
        pass

    if not use_api:
        if platform_name_fallback:
            return models.Platform(platform_name=None, url=url)
        raise UnknownPlatformName()
    assert use_api
    try:
        fc_name, _ = try_detect_platform_name(url)
        if fc_name:
            return models.Platform(platform_name=fc_name, url=url)
        if platform_name_fallback:
            return models.Platform(platform_name=None, url=url)
        raise UnknownPlatformName()
    except fetcherbase.FetcherException:
        if platform_name_fallback:
            return models.Platform(platform_name=None, url=url)
        raise


def create_platforms_from_urls(urls, use_api=False, platform_name_fallback=False):
    """
    Returns a list of platforms created using
    :func:`create_single_platform_from_url` for a list of ``urls``. Processing
    stops when an exception happens (only possible if ``platform_name_fallback == True``).
    Exceptions occuring during url resolving cause skipping errnous urls.
    If ``platform_name_fallback == False`` and ``UnknownPlatformName`` is raised
    by ``create_single_platform_from_url``, a "Custom" platform_name is used.
    """
    res = []
    for url in urls:
        try:
            plat = create_single_platform_from_url(url, use_api, platform_name_fallback)
            res.append(plat)
        except requests.RequestException:
            log.exception('Exception during url resolving, skipping url %r', url)
            continue
        except UnknownPlatformName:
            res.append(models.Platform(platform_name='Custom', url=url))
    return res
