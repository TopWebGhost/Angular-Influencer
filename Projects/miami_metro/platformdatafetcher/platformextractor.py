#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PlatformClusteringExtractor
Runs through index page and all pages that it suspects to be "About" pages and looks
for links (+ their immediate surroundings on the page) that look like they lead to
a platform. The principle is that links to all of user's social profile should be
close to one another on the page. Then everything that it finds is passed to
_platforms_from_links that returns Platform objects. It also looks if these platforms
are already in the database, if they aren't it adds them given that to_save flag is set.

PlatformFromPostsExtractor
Searches for links to platforms (including links to social network widgets)
that user posts repeatedly. They are understood to be his own profiles on other
platforms.

PlatformLinksCollector
Searches all social network links found on the index page, possible "About" pages,
and posts. It can be used to

extract_clustered_platforms
Celery task that runs PlatformClusteringExtractor

extract_platforms_from_platform
Celery task that finds all links on platform with PlatformLinksCollector, then
filters checks if they mention domain of the original platform.

extract_platforms_from_posts
Celery task that runs PlatformFromPostsExtractor

extract_combined
Celery taks that uses all the three methods to find profiles

autovalidate_platform
Celery task that tries to check platform by comparing meaningful part of
its social handle with blog title/social handle
"""
import logging
import re
import subprocess
import threading
import time
import urllib2
import urlparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta

import baker
import requests
from celery import task
from django.conf import settings
from django.core.cache import cache
from requests import ConnectionError
from selenium.common.exceptions import (
    WebDriverException, NoSuchElementException,
)

from debra import constants, models
from platformdatafetcher.extract_social_usernames import (
    get_profile_urls_from_usernames, SOCIAL_PLATFORMS, get_url_for_username,
    find_all_usernames,
)
from platformdatafetcher.platformutils import (
    username_from_platform_url, PLATFORM_PROFILE_REGEXPS,
    get_youtube_user_from_channel,
)
from social_discovery.blog_discovery import domains_to_skip
from xpathscraper import utils, xutils
from xpathscraper import xbrowser as xbrowsermod
from xpathscraper.xbrowser import redirect_using_xbrowser
from . import platformutils, socialwidgets, test_data

log = logging.getLogger('platformdatafetcher.platformextractor')

MIN_BLOG_LINK_COUNT_TO_VALIDATE = 5

INVALID_FRAME_URL = [isrc
                     for cls in socialwidgets.WIDGET_CLASSES
                     for isrc in cls.iframe_srcs]
INVALID_FRAME_ID = [iid
                    for cls in socialwidgets.WIDGET_CLASSES
                    for iid in cls.iframe_ids]
INVALID_ROOT_XPATH = [xpath
                      for cls in socialwidgets.WIDGET_CLASSES
                      for xpath in cls.root_xpaths]

BLACKLISTED_USERNAMES = ['profile.php', 'pages', 'blog', 'en', 'sharer.php']
STRIPPED_POSTFIXES = ['/boards', '/pins']

COMMON_ROOT_DOMAINS = ('.com', '.co.uk')
COMMON_BLOG_DOMAINS = ('.blogspot.com', '.wordpress.com')

tlocal = threading.local()

# matches for domain ends and path starting patterns which will be skipped (None means domain/path will not be checked)
BAD_URL_DOMAIN_PATH_PARTS = [
    (None, '/login.php'),
    (None, '/sharer.php'),
    (None, '/ServiceLogin'),
    (None, '/register'),
    (None, '/reblog'),
    (None, '/user/BloggerHelp'),
    (None, '/login.srf'),
    ('facebook.com', '/story.php'),
    ('liketoknow.it', '/login'),
]

SOCIAL_URLS_PER_BLOG_LIMIT = 14  # for 7 social platforms

XBROWSER_OPEN_URL_TRIES_LIMIT = 3

REQUESTS_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.2 (KHTML, like Gecko) '
        'Chrome/22.0.1216.0 Safari/537.2'
    ),
}


def _domain_fragments_for_link_search(source_platform_name=None):
    fragments = [t[0].lower() for t in platformutils.PLATFORM_PROFILE_REGEXPS]
    if source_platform_name:
        fragments = [f for f in fragments if f != source_platform_name.lower()]
    fragments.append('statigr')
    fragments.append('followgram')
    fragments.append('stagram.com')

    # Exclude broken gplus fragment and replace with plus.google.com
    fragments = [f for f in fragments if f != 'gplus']
    fragments.append('plus.google.com')

    return fragments


def cluster_is_good(cluster):
    usernames = [platformutils.username_from_platform_url(pl.url) for pl in cluster]
    usernames = [u.lower() for u in usernames if u is not None]
    usernames = [u.replace('_', '').replace('-', '').replace('.', '') for u in usernames]
    unique_usernames = len(set(usernames))
    if len(usernames) >= 3 and unique_usernames >= 2:
        log.warn('Too many different usernames in cluster: %s', usernames)
        return False
    return True


def cleanup_social_handle(social_handle):
    social_handle = social_handle.replace('#!/', '')

    parsed = urlparse.urlparse(social_handle)

    if not parsed.scheme:
        parsed = parsed._replace(scheme='https')

    if parsed.scheme == 'http' and 'facebook.com' in parsed.netloc:
        parsed = parsed._replace(scheme='https')

    social_handle = urlparse.urlunparse(parsed)

    return social_handle


def real_blog_urls_to_check(blog_url):
    blog_url = blog_url.lower()
    res = [blog_url]

    # Resolve possible redirect
    try:
        r = requests.get(blog_url, timeout=10, verify=False)
    except:
        log.exception('While real_blog_urls_to_check')
        return res

    if utils.domain_from_url(r.url) != utils.domain_from_url(blog_url):
        res.append(r.url)
        blog_url = r.url.lower()

    res.append(utils.domain_from_url(blog_url))

    root_stripped = utils.strip_last_domain_component(utils.domain_from_url(blog_url))

    if '.blogspot' in root_stripped:
        # Strip international root domain like blogspot.co.uk -> blogspot, blogspot.com -> blogspot
        res.append(root_stripped)

        # Strip .blogspot and add .com etc. to handle redirects like
        # abc.blogspot.com -> abc.com
        blogspot_stripped = root_stripped.replace('.blogspot', '')
        if len(blogspot_stripped) >= 5:
            for common_root in COMMON_ROOT_DOMAINS:
                res.append(blogspot_stripped + common_root)

    # Check for top-level domain like abc.com without a subdomain
    if '.' not in root_stripped and len(root_stripped) >= 5:
        # Try adding '.blogspot.com' etc. endings to handle redirects like
        # abc.com -> abc.blogspot.com
        for common_blog_domain in COMMON_BLOG_DOMAINS:
            res.append(root_stripped + common_blog_domain)

    return res

_last_r = None


def social_page_contains_blog_domain_text(social_handle, blog_url, real_blog_urls=None):
    """Checks if a social_handle URL contains a domain of blog_url.
    The return value is a tuple of:
    - an URL of a social_handle itself or a corrected URL if a redirect was
      encountered.
    - count of blog links found on the social platform
    """

    log.info('social_handle=%s blog_url=%s real_blog_urls=%s' % (social_handle, blog_url, real_blog_urls))

    def social_urls_to_check():
        res = [cleanup_social_handle(social_handle)]
        if platformutils.social_platform_name_from_url(blog_url, social_handle) == 'Facebook':
            parsed = urlparse.urlparse(social_handle)
            if '/pages' in social_handle:
                res.append(cleanup_social_handle(urlparse.urlunparse(parsed._replace(query='sk=info'))))
            else:
                res.append(cleanup_social_handle(urlparse.urlunparse(
                    parsed._replace(path=parsed.path.rstrip('/') + '/info'))))
        return res

    max_count = 0
    corrected_url = None
    try:
        if real_blog_urls is None:
            real_blog_urls = real_blog_urls_to_check(blog_url)
            if not real_blog_urls:
                log.warn('real_blog_urls is empty')
                return (None, 0)
        log.debug('real_blog_urls: %r', real_blog_urls)
        for url in social_urls_to_check():
            log.debug('Fetching url %s', url)
            r = platformutils.fetch_social_url(url)

            # for debugging
            global _last_r
            _last_r = r
            for real_blog_url in real_blog_urls:
                log.info('real_blog_url=%r' % real_blog_url)
                blog_domain = utils.domain_from_url(real_blog_url)
                log.info('blog_domain=%r' % real_blog_url)
                content = platformutils.resolve_shortened_urls(r.text)
                matches = content.lower().count(blog_domain.lower())
                max_count = max(max_count, matches)
                if matches > 0:
                    corrected_url = r.url

        log.info('max_count=%s' % max_count)
        return corrected_url, max_count
    except:
        log.exception('While social_page_contains_blog_domain_text, ignoring')
        return corrected_url, max_count


def _platforms_from_links(source_url, influencer, links, to_save=False):
    """

    :param source_url:
    :param influencer:
    :param links:
    :param to_save:
    :return:
    """
    res = []
    for link in links:
        platform_name = platformutils.social_platform_name_from_url(source_url, link, allow_insta_posts=True)
        if platform_name == platformutils.PLATFORM_NAME_DEFAULT:
            # Skip not detected platform names, they can be anything
            log.debug('Invalid platform link %s', link)
            continue

        # checking for username using more stable method of detecting existing platform
        username = username_from_platform_url(link)
        if username is not None:
            domain = urlparse.urlparse(link).netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            platform = models.Platform.objects.filter(influencer=influencer,
                                                      username=username,
                                                      url__contains='//%s/' % domain,
                                                      platform_name=platform_name)
        else:
            platform = models.Platform.objects.filter(influencer=influencer, url=link)

        if not platform.exists():
            log.debug('Creating new platform from link %r', link)
            platform = models.Platform()
            platform.influencer = influencer
            platform.url = link
            platform.platform_name = platform_name
            if to_save:
                platform.save()
        else:
            log.debug('Found existing platform for link %r', link)
            platform = platform[0]
        log.debug('Discovered platform %s from link %s', platform_name, link)
        res.append(platform)
    return res


class PlatformClusteringExtractor(object):

    """Extracts models.Platform objects given a xbrowser.XBrowser instance
    with a loaded blog page. It tries to extract links from the current
    page and from "about me" page (if it can be found).
    """

    def __init__(self, xbrowser, url, influencer=None):
        assert isinstance(url, basestring)
        self.xbrowser = xbrowser
        self.url = url
        self.influencer = influencer
        self.allowed_domains = list()
        self.append_domain_from_url(self.url)

    def extract_platform_clusters(self, to_save=False):
        # if self.xbrowser.driver.current_url != self.url:
        self.xbrowser.load_url(self.url)
        time.sleep(2)
        about_page_links = xutils.get_about_page_links(self.xbrowser)
        log.info('about_page_links: %s', about_page_links)
        res = []

        for page_url in [self.url] + about_page_links:
            log.debug('Will process links from %s', page_url)
            try:
                self.xbrowser.load_url(page_url)
                time.sleep(2)

                current_url = self.xbrowser.driver.current_url
                if page_url == self.url:
                    self.append_domain_from_url(current_url)

                pl_clusters = self._extract_from_current_page(to_save)
                log.debug('Platform clusters extracted from the current page %s : %s', page_url, pl_clusters)
                if self.is_domain_allowed(current_url):
                    res += pl_clusters
                else:
                    log.info('Domain of url %r is not among %s, so its clusters are not considered.' % (
                        current_url,
                        self.allowed_domains
                    ))
            except:
                log.exception('While processing %r, skipping', page_url)
        log.debug('Returning platform clusters: %s', res)
        return res

    def _extract_from_current_page(self, to_save=False):
        """
        Extracts urls from current page, need to investigate why it skips insagram in our example
        :param to_save:
        :return:
        """
        domains_fragments = _domain_fragments_for_link_search()
        log.debug('Domains fragments: %s' % domains_fragments)
        els_links = self.xbrowser.execute_jsfun_safe([], '_XPS.visibleLinksToDomains',
                                                     domains_fragments, False, True, False,
                                                     INVALID_FRAME_URL, INVALID_FRAME_ID,
                                                     INVALID_ROOT_XPATH)
        log.debug('els_links before validation: %r', els_links)
        els_links = [el_link for el_link in els_links if platformutils.social_platform_name_from_url(
            self.xbrowser.url, el_link[1], allow_insta_posts=True) != platformutils.PLATFORM_NAME_DEFAULT]
        log.debug('els_links: %s', els_links)
        clusters = self.xbrowser.execute_jsfun('_XPS.clusterElsTexts', els_links, 80)
        if not clusters:
            return []
        return [_platforms_from_links(self.xbrowser.url,
                                      self.influencer,
                                      [link for el, link in cluster],
                                      to_save)
                for cluster in clusters]

    def append_domain_from_url(self, url):
        domain = urlparse.urlparse(url).netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        self.allowed_domains.append(domain)

    def is_domain_allowed(self, url):
        """
        validates that this url belongs to blog for which we are finding clusters
        :param url:
        :return:
        """
        domain = urlparse.urlparse(url).netloc.lower()
        for ad in self.allowed_domains:
            if domain.endswith(ad):
                return True
        return False


def has_unique_domains(link_cluster):
    domains = set()
    for link in link_cluster:
        domain = utils.domain_from_url(link)
        if domain in domains:
            return False
        domains.add(domain)
    return True


class PlatformFromPostsExtractor(object):

    """Fetches links common to a few posts.
    """

    def __init__(self, xbrowser, source_platform):
        assert isinstance(source_platform, models.Platform)
        self.xbrowser = xbrowser
        self.source_platform = source_platform

    def extract_platforms_from_posts(self, to_save=False):
        if self.source_platform.id:
            posts = list(self.source_platform.posts_set.order_by('-create_date')[:5])
            log.debug('Fetched posts to search for socilal handles %s', [p.url for p in posts])
        else:
            posts = []
        if not posts:
            log.error('No posts to load')
            return []

        links_from_posts = []
        for p in posts:
            try:
                self.xbrowser.load_url(p.url)
                domains_fragments = _domain_fragments_for_link_search(self.source_platform.platform_name)

                direct_links = self.xbrowser.execute_jsfun_safe([], '_XPS.visibleLinksToDomains',
                                                                domains_fragments, True, True, False, INVALID_FRAME_URL, INVALID_FRAME_ID,
                                                                INVALID_ROOT_XPATH)
                log.debug('Direct links before validation: %r', direct_links)

                widget_links = socialwidgets.find_owner_urls_from_widgets(self.xbrowser)
                log.debug('Links from widgets: %r', widget_links)

                links = [platformutils.normalize_social_url(l) for l in direct_links + widget_links]
                links_pnames = {(l, platformutils.social_platform_name_from_url(self.xbrowser.url, l)) for l in links}
                links_pnames = {(l, pname) for (l, pname) in links_pnames if pname != platformutils.PLATFORM_NAME_DEFAULT}
                links_pnames = {(l, pname) for (l, pname) in links_pnames if platformutils.username_from_platform_url(l)}
                log.debug('links for post %s: %s', p.url, links_pnames)
                links_from_posts.append(links_pnames)
            except:
                log.exception('While processing %r, skipping', p.url)

        # Discard up to 2 posts with no links (error, deleted post)
        links_from_posts = [lp for lp in links_from_posts if lp]
        if len(links_from_posts) < 3:
            log.error('Not enough posts with links')
            return []

        common = set.intersection(*links_from_posts)
        log.debug('Common links: %s', common)

        return _platforms_from_links(self.xbrowser.url, self.source_platform.influencer,
                                     [lp[0] for lp in common], to_save)


class PlatformLinksCollector(object):

    """This class traverser the main blog page, "about" and "contact" pages,
    and Posts stored in the DB (if available) and returns all platform links
    as Platform objects without filtering or clustering.
    """

    def __init__(self, xbrowser, source_platform):
        assert isinstance(source_platform, models.Platform)
        self.xbrowser = xbrowser
        self.source_platform = source_platform

    def extract_platforms(self):
        urls = []

        urls.append(self.source_platform.url)

        if self.source_platform.id:
            posts = list(self.source_platform.posts_set.order_by('-create_date')[:5])
            log.debug('Fetched posts to search for social handles %s', [p.url for p in posts])
        else:
            posts = []

        for post in posts:
            urls.append(post.url)

        self.xbrowser.load_url(self.source_platform.url)
        about_page_links = self.xbrowser.execute_jsfun_safe([], '_XPS.visibleLinksWithTexts',
                                                            ['contact', 'about', 'social', 'media', 'follow'], 40)
        about_page_links = [l for l in about_page_links if utils.domain_from_url(l) ==
                            utils.domain_from_url(self.xbrowser.driver.current_url)]
        urls += about_page_links

        urls = utils.unique_sameorder(urls)

        res = []
        domains_fragments = _domain_fragments_for_link_search(self.source_platform.platform_name)
        log.info('Collecting platform links from urls: %s', urls)
        for url in urls:
            try:
                self.xbrowser.load_url(url)
            except:
                log.exception('While loading url, skipping %s', url)
                continue
            links = self.xbrowser.execute_jsfun_safe([], '_XPS.visibleLinksToDomains',
                                                     domains_fragments, True, True, False, INVALID_FRAME_URL, INVALID_FRAME_ID,
                                                     INVALID_ROOT_XPATH)
            links = utils.unique_sameorder(links)
            links = [l for l in links if utils.domain_from_url(l) != utils.domain_from_url(
                self.source_platform.url)]
            links = [platformutils.normalize_social_url(l) for l in links]
            links = [l for l in links if platformutils.social_platform_name_from_url(self.source_platform.url,
                     l) != platformutils.PLATFORM_NAME_DEFAULT and platformutils.username_from_platform_url(l)]
            log.warn('Links collected from url %s: %s', url, links)
            res += links
        platforms = _platforms_from_links(self.xbrowser.url, self.source_platform.influencer, res)
        return platforms


def choose_platform_to_save(platform_name, validated_platforms):
    from platformdatafetcher import socialfetcher

    assert len(validated_platforms) > 0

    if len(validated_platforms) == 1:
        return validated_platforms[0]

    if platform_name == 'Facebook':
        for plat in validated_platforms:
            is_private = socialfetcher.FacebookFetcher.is_private(plat.url)
            if not is_private:
                log.info('Choosing non-private facebook url %r', plat.url)
                return plat
        log.info('All Facebook platforms are private, selecting the first one')
        return validated_platforms[0]

    return validated_platforms[0]


def is_profile_fb_url(platform=None):
    from platformdatafetcher import socialfetcher

    is_profile = False
    if isinstance(platform, models.Platform) and platform.platform_name == 'Facebook':
        is_profile = socialfetcher.FacebookFetcher.is_profile(platform.url)

    return is_profile


# chunks in urls to consider this url not worthy of autovalidating but to skip it
BAD_SOCIAL_URLS = {
    'Facebook': ['facebook.com/pinterest', 'facebook.com/twitter', 'facebook.com/instagram', 'facebook.com/facebook',
                 'facebook.com/lookbook', 'facebook.com/youtube', 'facebook.com/bloglovin', 'facebook.com/polyvore',
                 'facebook.com/askfmpage'],
    'Twitter': ['twitter.com/pinterest', 'twitter.com/twitter', 'twitter.com/instagram', 'twitter.com/facebook',
                'twitter.com/lookbook', 'twitter.com/youtube', 'twitter.com/bloglovin', 'twitter.com/polyvore',
                'twitter.com/askfm'],
    'Instagram': ['instagram.com/pinterest', 'instagram.com/twitter', 'instagram.com/instagram',
                  'instagram.com/facebook', 'instagram.com/lookbook', 'instagram.com/youtube',
                  'instagram.com/bloglovin', 'instagram.com/polyvore', 'instagram.com/askfm'],
    'Pinterest': ['pinterest.com/pinterest', 'pinterest.com/twitter', 'pinterest.com/instagram',
                  'pinterest.com/facebook', 'pinterest.com/lookbook', 'pinterest.com/youtube',
                  'pinterest.com/bloglovin', 'pinterest.com/polyvore', 'pinterest.com/askfm'],
    'Youtube': ['youtube.com/user/pinterest', 'youtube.com/user/twitter', 'youtube.com/user/instagram',
                'youtube.com/user/facebook', 'youtube.com/user/lookbook', 'youtube.com/user/youtube',
                'youtube.com/user/bloglovin', 'youtube.com/user/polyvore', 'youtube.com/user/askfm'],
    'Tumblr': ['pinterest.tumblr.com', 'twitter.tumblr.com', 'instagram.tumblr.com', 'facebook.tumblr.com',
               'lookbook.tumblr.com', 'youtube.tumblr.com', 'bloglovin.tumblr.com', 'polyvore.tumblr.com',
               'askfm.tumblr.com'],
}

def is_url_social_for_social(pl_url, pl_name=None):
    """
    Checks if url is a social url for another social platform, for example:
        https://www.pinterest.com/twitter/
    :param pl_url: url to check
    :param pl_name: social url to check for
    :return:
    """
    if pl_url is None:
        log.warn('platform url is None')
        return None

    # checking if this url is social for social
    if pl_name is None:
        for p_chunks in BAD_SOCIAL_URLS.values():
            if any(chunk in pl_url for chunk in p_chunks):
                log.warn('Url %r appears to be a social url of social platform' % pl_url)
                return True
    else:
        if any(chunk in pl_url for chunk in BAD_SOCIAL_URLS.get(pl_name, [])):
            log.warn('Url %r appears to be a social url of social platform' % pl_url)
            return True
    return False


class SocialLink(object):
    """
    Freshly discovered social page url to harvest further social urls
    """

    url = None  # url link (redirected)
    url_original = None  # url link (original)
    platform = None  # Social platform
    is_source_platform = False  # blog platform is the source one
    is_performed = False  # flag if this platform was performed by discovering and getting new social urls from it
    inaccessible = False  # TODO: in future - flag shows if platform url returned 404 or something like that
    level = None  # level of platform starting with initial blog platform = 0

    def __init__(self, platform=None, is_source_platform=False, level=None):
        assert isinstance(platform, models.Platform)
        self.platform = platform
        self.url = platform.url
        self.is_source_platform = is_source_platform
        if level is not None:
            self.level = level

    def is_autovalidated(self):
        return self.platform.autovalidated if self.platform else None

    def __str__(self):
        return '<%r, depth=%s %s>' % (self.url, self.level, self.platform.autovalidated)

    def __repr__(self):
        return '<%r, depth=%s %s>' % (self.url, self.level, self.platform.autovalidated)

    def update_url(self, url):
        self.url = url
        self.platform.url = url

# The only missing case in validation right now is the following:
# a) we found a facebook platform that is validated
# b.1) we have a social platform that is not validated, but it has a link to other validated platforms in its descr.
# b.2) we have a social platform that is not validated, but it's id and other validated
#      platforms url match significantly
def validate_platform(source_pl, pl, redirected_url=None, xb=None):
    """Validates platform ``platform_url`` found on ``source_pl``, returning
    a reason for validation (a string) or ``None`` if it's not validated.
    """
    log.info("Validating url %r:" % pl.url)
    if not pl.influencer:
        log.warn('No influencer set for %r, not validated' % pl)
        return None

    if is_url_social_for_social(pl.url, pl.platform_name):
        log.info("%s is a social url of social platform, not validated" % pl.url)
        return None

    from . import fetcher

    # make sure to not let invalid social urls pass by (e.g., facebook.com/sharer.php?..)
    n = platformutils.social_platform_name_from_url(source_pl.url, pl.url)
    if n and n == 'blog':
        log.info("%s is not a valid social url, not validated" % pl.url)
        return None

    source_domain = utils.domain_from_url(source_pl.url)
    meaningful_fragment = platformutils.meaningful_domain_fragment(source_pl.url)
    blog_urls_to_check = real_blog_urls_to_check(source_pl.url)
    # if blog url redirects, we should check that url also for verification
    if redirected_url:
        blog_urls_to_check += real_blog_urls_to_check(redirected_url)

    log.debug('Source domain, meaningful fragement for %r: %r, %r', source_pl,
              source_domain, meaningful_fragment)

    # Fetch social page content to reuse it in other functions
    pl_r = None
    try:
        pl_r = platformutils.fetch_social_url(pl.url)
    except:
        log.exception('While fetch_social_url(%r)', pl.url)

    if pl_r:
        # trying fetching title as sometimes it may crash
        try:
            title = xutils.fetch_title(content=pl_r.text)
            if meaningful_fragment and meaningful_fragment.lower() in (title or '').lower():
                log.info('Meaningful fragment present in title %r', title)
                return 'meaningful_title'
        except:
            pass
    else:
        log.warn('Not checking for meaningful fragment in title beacuse of fetch error')

    # Make sure that meaningful fragment exists in the url AND the url is not giving an error (i.e., it's not a 404)
    if meaningful_fragment and meaningful_fragment.lower() in pl.url.lower() and pl_r:
        log.info('Meaningful fragment present in url %r', pl.url)
        return 'meaningful_platform'

    desc = fetcher.try_get_social_description(pl.url, xb=xb)
    # log.info('Fetched description for %r: %r', pl.url, desc)
    if desc:
        pl.description = desc
        found_blog_urls = [burl for burl in blog_urls_to_check if burl.lower() in desc.lower()]
        if found_blog_urls:
            log.info('%r are present in description of %r', found_blog_urls, pl.url)
            return 'blog_url_in_description'
        # this is only invoked if above fails
        # now, there might be a shortened url in the description pointing to the blog
        # example: http://instagram.com/PPFgirl => has http://bit.ly/16b4zOW that points to the blog
        from . import contentfiltering
        urls = set(contentfiltering.find_important_urls(desc))
        urls.update(contentfiltering.re_find_urls(desc))
        log.debug('%r are all urls in the description, now checking for blog url in shortened form', urls)
        for u in urls:
            try:
                resolved_u = utils.resolve_http_redirect(u)
                found_blog_urls = [burl for burl in blog_urls_to_check if burl.lower() in resolved_u.lower()]
                if found_blog_urls:
                    log.info('%r are present in shortened url %r of %r', found_blog_urls, u, pl)
                    return 'blog_url_shortened_in_description'
            except:
                pass

    corrected_social_handle, match_count = social_page_contains_blog_domain_text(pl.url,
                                                                                 source_pl.url,
                                                                                 blog_urls_to_check)
    log.debug('Blog link count: %d', match_count)
    if match_count >= MIN_BLOG_LINK_COUNT_TO_VALIDATE:
        log.info('Blog link count is high enough to validate')
        return 'high_blog_link_count'

    log.info('%r is not validated', pl.url)
    return None


def save_validation_result(reason, platform, to_save=True):
    if reason:
        platform.autovalidated = True
        platform.autovalidated_reason = reason
    else:
        platform.autovalidated = False
        platform.autovalidated_reason = None
    if to_save:
        platform.save()


import pprint
class DiscoveredSocialLinkPool(object):
    """
    All discovered social links with their connections (USING Platforms now)

    Graph object with Links as nodes and their connections as arcs is represented like:
    graph = {
        'Custom <http://www.justsemir.nl>': ['Twitter <https://twitter.com/justsemir>',
                                             'Facebook <https://www.facebook.com/JustSemir/>',
                                             'Youtube <http://www.youtube.com/user/VraagSemir>'],

        'Twitter <https://twitter.com/justsemir>' : ['Custom <http://www.justsemir.nl>'],

        'Facebook <https://www.facebook.com/JustSemir/>': ['Twitter <https://twitter.com/justsemir>'],

        'Youtube <http://www.youtube.com/user/VraagSemir>': ['Instagram <https://www.instagram.com/JustSemir/>'],

        'Instagram <https://www.instagram.com/JustSemir/>': ['Twitter <https://twitter.com/justsemir>']
    }

    We should make our best to have nodes to be unique bu their urls and their urls should be 100% actual urls
    to social platforms. Filter out all unadequate urls from here. Final redirect urls should be applied for platforms.
    Each platform should be loaded in Selenium only once to acquire its links.

    When we autovalidate platforms by any other means (meaningful title or platform url match count) we may
    set platform as autovalidated before searching for rings.
    """
    graph = None
    blog_platform = None
    redirect_urls = True

    maximum_graph_depth = 12  # how many iterations we perform at maximum to detect new platforms
    current_graph_depth = 0

    def __init__(self, blog_platform=None, redirect_urls=True):
        self.graph = {}
        if isinstance(blog_platform, models.Platform):
            blog_platform.url = redirect_using_xbrowser(blog_platform.url, None, normalize_socials=True)
            self.blog_platform = blog_platform
            blog_platform_link = SocialLink(platform=self.blog_platform, is_source_platform=True, level=0)
            blog_platform_link.is_performed = True
            self.graph[blog_platform_link] = []
        else:
            log.error('Initial autovalidated blog platform must be set')
        self.redirect_urls = redirect_urls

    def describe(self):
        pp = pprint.PrettyPrinter(indent=4)
        print('*' * 60)
        pp.pprint(self.graph)
        print('*' * 60)

    # def discover_social_links(self):
    #     # Discovers social links for existing links
    #     pass

    def autovalidated_nodes(self):
        return [node for node in self.graph if node.is_autovalidated()]

    def not_autovalidated_nodes(self):
        return [node for node in self.graph if not node.is_autovalidated()]

    def discover_autovalidated_ring_for_link(self, ttv_link, path=[]):
        # Discovers social links for particular link
        print('        discover_autovalidated_ring_for_link(%r, %r)' % (ttv_link, path))

        # should have autovalidated start link
        if ttv_link is None:
            print('        ttv_link is None')
            return None

        # adding try-to-validate_link to path
        path = path + [ttv_link]

        # ttv_link is autovalidated, return the path
        if ttv_link.is_autovalidated() and len(path) > 1:
            print('        ttv_link is autovalidated and path is > 1')
            return path

        # if node has no links, return None
        if len(self.graph[ttv_link]) == 0:
            print('        ttv_link %r has no links' % ttv_link)
            return None

        # iterating over all not-yet-autovalidated links of this node
        for node in self.graph[ttv_link]:
            print('        checking %r connected links' % node)
            if node.is_autovalidated() or node not in path:
                print('            discovering for %r ' % node)
                new_path = self.discover_autovalidated_ring_for_link(node, path)
                if new_path:
                    print('        * New path: %s' % new_path)
                    return new_path

        print('        * Finish: None')
        return None

    def autovalidate_connected_platforms(self):
        """
        Iteratively autovalidates all found circles of links
        Algorithm:
        1) getting autovalidated link (l1) in graph's vertices
        2) for this platform find non-autovalidated link (l2) by its arcs, forming a path [l1, l2]
        3) for last link of the path iterating through links it is connected by arcs, adding it to path. If the most
            recent link is autovalidated then returning the whole path for autovalidation non-autovalidated among them.
            If it is not autovalidated then repeating (3)
            If there are no more links to add to path - skipping them.
        4) if some change in autovalidating occured, repeat algorithm from (1) for all autovalidated links
        """

        log.info('Autovalidating circular platforms')
        iter_ctr = 0
        changed = True
        while changed and iter_ctr < 100:
            changed = False
            iter_ctr += 1
            log.info('Iteration %s' % iter_ctr)

            for k in self.graph.keys():
                if k.is_autovalidated():
                    print('Parent node: %s' % k)
                    for v in self.graph[k]:
                        if not v.is_autovalidated():
                            print('    child node: %s' % v)
                            ring = self.discover_autovalidated_ring_for_link(v, path=[k,])
                            if ring is not None and len(ring) > 1:
                                for l in ring:
                                    if not l.is_autovalidated():
                                        l.platform.autovalidated = True
                                        l.platform.autovalidated_reason = 'graph_simple_cycle_validation'
                                        print('        Autovalidating : %s' % l)
                                changed = True
                            else:
                                print('        no autovalidated ring found')
        log.info('Autovalidating finished in %s iterations' % iter_ctr)

    def append_link_to_graph(self, parent_link, link):
        """
        appends social url to graph
        """
        if link is None or link.platform is None or link.url is None \
                or parent_link is None or parent_link.platform is None or parent_link.url is None:
            log.error('link and its parent link should not be None and have platforms with urls')
            return None

        # validating url
        url = xbrowsermod.validate_url(link.url)
        if url is None:
            # FUBARed url, forgetting it
            return

        if self.redirect_urls:
            # Here we update all respected links (insta posts to their authors profiles,
            # FB to their direct profiles, etc). Also here we strip out unwanted links
            # (facebook.com/sharer.php and something like that)
            platform_name = link.platform.platform_name or \
                            platformutils.social_platform_name_from_url(None, url, allow_insta_posts=True)
            if platform_name == platformutils.PLATFORM_NAME_DEFAULT:
                return

            elif platform_name == 'Instagram':

                # Checking for Instagram posts' urls
                if 'instagram.com/p/' in url.lower():
                    # seems we have an insta post url here
                    author_link = fetch_insta_profile_by_post_url(url)
                    if author_link is None:
                        return
                    url = author_link
                else:
                    url = url

            elif platform_name == 'Facebook':
                # Making facebook urls straight-forward
                valid_url = redirect_using_xbrowser(url, normalize_socials=True)

                # getting FB username
                fb_username = platformutils.username_from_platform_url(valid_url)
                if fb_username is not None:
                    url = "https://www.facebook.com/%s" % fb_username
                    try:
                        url = redirect_using_xbrowser(url, timeout=10, normalize_socials=True)
                    except:
                        pass

            else:
                # print('Adding %s link with url: %s' % (platform_name, url))
                url = redirect_using_xbrowser(url, normalize_socials=True)
                print('Redirected %s link with url: %s' % (platform_name, url))

        if not is_acceptable_social_url(url) and url != self.blog_platform.url:
            return

        link.url = url
        link.platform.url = url

        # searching parent node
        parent_node = None
        child_node = None
        for node in self.graph.keys():
            if node.url == parent_link.url and parent_node is None:
                parent_node = node
            if node.url == link.url and child_node is None:
                child_node = node
            if child_node and parent_node:
                break

        # exiting if parent node was not found
        if parent_node is None:
            log.error('parent link with url %r not found' % parent_link.url)
            return None

        # if child node not found - creating it
        if child_node is None:
            child_node = link
            child_node.level = parent_node.level + 1
            self.graph[child_node] = []

        if child_node not in self.graph[parent_node]:
            self.graph[parent_node].append(child_node)

        return child_node.level

    def get_sorted_platforms(self):
        """
        returns platforms splitted by autovalidated/not autovalidated
        """
        autovalidated = []
        not_autovalidated = []
        for node in self.graph.keys():
            node.platform.url = node.url
            if node.is_autovalidated():
                autovalidated.append((node.platform, node.platform.autovalidated_reason))
            else:
                not_autovalidated.append(node.platform)

        return autovalidated, not_autovalidated


def _create_platforms_from_description_dslp(parent_node, xb=None, dslp=None):
    """
    Here, we look at the description field of a platform object
    Search for social urls, and then return the list of validated platform objects
    """
    from . import fetcher, platformutils

    print('Called _create_platforms_from_description_dslp() for node\'s paltform %s' % parent_node.platform)

    new_platforms_detected = False

    autovalidated_urls = [avn.platform.url for avn in dslp.autovalidated_nodes()
                          if avn.platform is not None and avn.platform.url is not None]
    autovalidated_urls += [platformutils.url_to_handle(platformutils.normalize_social_url(avn.platform.url))
                           for avn in dslp.autovalidated_nodes()
                           if avn.platform is not None and avn.platform.url is not None]

    non_autovalidated_urls = [navn.platform.url for navn in dslp.not_autovalidated_nodes()
                              if navn.platform is not None and navn.platform.url is not None]
    non_autovalidated_urls += [platformutils.url_to_handle(platformutils.normalize_social_url(navn.platform.url))
                               for navn in dslp.not_autovalidated_nodes()
                               if navn.platform is not None and navn.platform.url is not None]

    desc = parent_node.platform.description
    new_plats = set()
    if desc:
        plats = fetcher.create_platforms_from_text(desc)
        log.info("We found these platforms %s from description of %s %s" % (plats,
                                                                            parent_node.platform.platform_name,
                                                                            parent_node.platform.url))
        for p in plats:
            if p.platform_name in models.Platform.SOCIAL_PLATFORMS:
                # great, we have a new social platform
                log.info("Checking %s" % p)

                # checking for HTML status
                # # TODO: check if it is really needed, because Selenium has no means of retreiving HTML status code
                # r = requests.get(p.url, headers=requests_headers, timeout=15)
                # if r.status_code >= 400:
                #     # inappropriate status code
                #     continue

                dslp.append_link_to_graph(parent_node, SocialLink(p))

                new_platforms_detected = True

                if p.url in autovalidated_urls or p.url in non_autovalidated_urls:
                    log.info("%s exists, so continuing" % p.url)
                    continue

                # save it
                if parent_node.is_autovalidated():
                    save_validation_result("created_from_validated_platforms_description", p, to_save=False)
                else:
                    save_validation_result(None, p, to_save=False)

                p.description = fetcher.try_get_social_description(p.url, xb=xb, extra_fields=True)
                p.influencer = parent_node.platform.influencer
                new_plats.add(p)

            else:
                if redirect_using_xbrowser(p.url, normalize_socials=True) == dslp.blog_platform.url:
                    dslp.append_link_to_graph(parent_node, SocialLink(p))

    log.info("Created %d new platforms" % len(new_plats))
    return new_platforms_detected


def _create_platforms_from_description(validated_platform, all_validated_platforms, xb=None):
    """
    Here, we look at the description field of a platform object
    Search for social urls, and then return the list of validated platform objects
    """
    from . import fetcher, platformutils
    all_validated_urls = [u[0].url for u in all_validated_platforms]
    all_validated_urls += [platformutils.url_to_handle(platformutils.normalize_social_url(u[0].url)) for u in all_validated_platforms]
    desc = validated_platform.description
    new_plats_validated = set()
    if desc:
        plats = fetcher.create_platforms_from_text(desc)
        log.info("We found these platforms %s " % plats)
        for p in plats:
            if p.platform_name in models.Platform.SOCIAL_PLATFORMS:
                # great, we have a new social platform
                log.info("Checking %s" % p)
                if p.url in all_validated_urls:
                    log.info("%s exists, so continuing" % p.url)
                    continue
                # save it
                all_validated_platforms.append((p, "created_from_validated_platforms_description"))
                save_validation_result("created_from_validated_platforms_description", p)
                p.description = fetcher.try_get_social_description(p.url, xb=xb)
                p.influencer = validated_platform.influencer
                new_plats_validated.add(p)

    log.info("Created %d new platforms that were automatically validated" % len(new_plats_validated))


# def do_further_validation_using_validated_platforms(validated, non_validated, xb=None, dslp=None):
def do_further_validation_using_validated_platforms_dslp(xb=None, dslp=None):
    """
    Look at each validated platform's description:
        : If we have a url that matches the non_validated platform's url
            => then add that platform in validated
        : If that url doesn't exist yet in non_validated or validated
            => Create a new platform object and add that to validated
    """

    new_platforms_discovered = True

    while new_platforms_discovered and dslp.current_graph_depth <= dslp.maximum_graph_depth:

        # reseting detection flag and increasing current graph's depth
        new_platforms_discovered = False
        dslp.current_graph_depth += 1  # current level of platforms we detect

        log.info('Called do_further_validation_using_validated_platforms(), DEPTH: %s' % dslp.current_graph_depth)
        log.info('Starting Graph:')
        dslp.describe()

        # for node in dslp.graph.keys():
        for node in dslp.autovalidated_nodes():

            # # we perform unperformed nodes only
            # if not node.is_performed:
            pl = node.platform

            if not pl.description:
                # if no description, fetch it now
                from . import fetcher
                pl.description = fetcher.try_get_social_description(pl.url,
                                                                    xb=xb,
                                                                    extra_fields=True)

            if pl.description:
                for nvn in dslp.not_autovalidated_nodes():
                    # this normalizes the social urls (at least for twitter and instagram)
                    normalized_url = platformutils.normalize_social_url(nvn.platform.url)
                    # next, remove http(s)* and www as well if they exist
                    # (so https://www.twitter.com/blah => twitter.com/blah
                    normalized_url = platformutils.url_to_handle(normalized_url)
                    if normalized_url.lower() in pl.description.lower():
                        # newly_discovered.add(nvn)
                        save_validation_result("social_url_cross_validation", nvn.platform, to_save=False)

        # now, the final case: if a non_validated platform's description contains a link to any one of the validated
        # platforms, then it should also be verified
        for nvn in dslp.not_autovalidated_nodes():
            if not nvn.platform.description:
                # if no description, fetch it now
                from . import fetcher
                nvn.platform.description = fetcher.try_get_social_description(nvn.platform.url,
                                                                              xb=xb,
                                                                              extra_fields=True)
            if nvn.platform.description:
                for vn in dslp.autovalidated_nodes():
                    if vn.platform.url.lower() in nvn.platform.description.lower():
                        # newly_discovered.add(nvn)
                        save_validation_result("social_url_cross_validation", nvn.platform, to_save=False)

        # now, let's see if any of the validated platform's description has social urls that might be of our interest
        # these should be automatically validated.
        for node in dslp.graph.keys():
            if not node.is_performed:
                new_platforms_discovered = _create_platforms_from_description_dslp(node, xb=xb, dslp=dslp)
                node.is_performed = True
        # log.info('Ending Graph:')
        # dslp.describe()

    return


def do_further_validation_using_validated_platforms(validated, non_validated, xb=None):
    """
    Look at each validated platform's description:
        : If we have a url that matches the non_validated platform's url
            => then add that platform in validated
        : If that url doesn't exist yet in non_validated or validated
            => Create a new platform object and add that to validated

    Note: legacy function
    """
    newly_validated = set()
    for pl, _ in validated:
        if not pl.description:
            # if no description, fetch it now
            from . import fetcher
            pl.description = fetcher.try_get_social_description(pl.url, xb=xb)
        if pl.description:
            for v in non_validated:
                # this normalizes the social urls (at least for twitter and instagram)
                normalized_url = platformutils.normalize_social_url(v.url)
                # next, remove http(s)* and www as well if they exist
                # (so https://www.twitter.com/blah => twitter.com/blah
                normalized_url = platformutils.url_to_handle(normalized_url)
                if normalized_url in pl.description:
                    newly_validated.add(v)
                    validated.append((v, "social_url_cross_validation"))
                    non_validated.remove(v)
                    save_validation_result("social_url_cross_validation", v)
    log.info("Awesome, we validated %d more urls %s " % (len(newly_validated), newly_validated))
    log.info("We still have these not yet validated: %s" % non_validated)

    # now, let's see if any of the validated platform's description has social urls that might be of our interest
    # these should be automatically validated.
    for pl, _ in validated:
        _create_platforms_from_description(pl, validated, xb=xb)

    # now, the final case: if a non_validated platform's description contains a link to any one of the validated
    # platforms, then it should also be verified
    for pl in non_validated:
        if not pl.description:
            # if no description, fetch it now
            from . import fetcher
            pl.description = fetcher.try_get_social_description(pl.url, xb=xb)
        if pl.description:
            for p, _ in validated:
                if p.url.lower() in pl.description.lower():
                    validated.append((pl, "social_url_cross_validation"))
                    newly_validated.add(pl)
                    non_validated.remove(pl)
                    save_validation_result("social_url_cross_validation", pl)
                    break
    log.info("Awesome, we validated %d more urls %s " % (len(newly_validated), newly_validated))
    log.info("We still have these not yet validated: %s" % non_validated)

    # now, we may have new platforms that were validated, if yes, we need to call this function again
    if len(newly_validated) > 0:
        do_further_validation_using_validated_platforms(validated, non_validated, xb=xb)

    return


def is_acceptable_social_url(url=None):
    """
    Checks if this social url is acceptable:
    * it is not a social url of another social network
    * it is not an empty social platform url (like http://instagram.com/
    * it is not some sharer/login page's url for social network
    :param url:
    :return:
    """

    # checking that this is not an empty social platform url
    parsed = urlparse.urlparse(url)
    # Tumblr check
    if parsed.netloc.endswith('tumblr.com'):
        if len(parsed.netloc[:-10].replace('www.', '')) > 0:
            pass
        else:
            return False
    else:
        # other socials should have non-empty path
        if len(parsed.path.strip('').strip('/')) == 0:
            return False

    # Checking that this url is not just a root url for social network
    if is_url_social_for_social(url, None):
        return False

    # Checking that it is not a service page of social network
    # Validating url's path

    # https://m.facebook.com/story.php?story_fbid=1058166030877659&id=199633956730875
    if any(
            [
                (
                    bdmn is None or parsed.netloc.lower().endswith(bdmn)
                ) and (
                    bpath is None or parsed.path.startswith(bpath)
                ) for bdmn, bpath in BAD_URL_DOMAIN_PATH_PARTS if bdmn is not None or bpath is not None
            ]
    ):
        return False

    return True


def convert_or_save_platforms(source_pl, pls, to_save=True, xb=None, dslp=None):
    """Appends urls to influencer's *_url fields or directly saves them as
    Platform objects, if they can be validated.
    Returns a list of validated platforms.
    """

    log.info('Converting or saving platforms...')
    log.info('Parent platform: %s' % source_pl)
    log.info('Child platforms: %s' % pls)

    # if the original blog redirects, we should check that too for validation
    resolved_u = None
    try:
        resolved_u = xbrowsermod.redirect_using_xbrowser(source_pl.url, xb=xb)
    except:
        pass

    for pl in pls:
        validation_reason = validate_platform(source_pl, pl, resolved_u, xb=xb)

        # will be saved in save_validation_result according to 'to_save' setting
        save_validation_result(validation_reason, pl, to_save=False)

        print('+= += += Appending 1-st tier platform to dslp: %s' % pl)
        if dslp is not None:
            dslp.append_link_to_graph(SocialLink(source_pl), SocialLink(pl))

    if len(pls) > 0:
        dslp.current_graph_depth += 1

    log.info('NOW THERE SHOULD BE INITIAL_PLATFORMS (blog platform and 1-st level platforms): ')
    dslp.describe()

    # Now, using validated platforms, see if we can further auto-validate more platforms
    # do_further_validation_using_validated_platforms(validated, not_validated, xb=xb, dslp=dslp)
    do_further_validation_using_validated_platforms_dslp(xb=xb, dslp=dslp)

    # HERE we autovalidate circular platform dependencies
    dslp.autovalidate_connected_platforms()
    log.info('Graph after autovalidating interconnected platforms:')
    dslp.describe()

    validated, not_validated = dslp.get_sorted_platforms()

    # To this place we will have 2 lists populated with validated and not-validated platforms

    # there could be two cases:
    # a) we discovered a platform for a type
    # b) we didn't discover a platform for a type
    #
    # now (a) has two cases:
    # i) we found at least one that is autovalidated (we create a platform or should
    # we use an existing platform and make it auto-validated and visible)
    # b) we found some but none is autovalidated (if only one, we mark it visible
    # but if more then than one, we don't do anything)

    platforms_to_show = []  # plats for which we set url_not_found=False (make visible)
    platform_name_autovalidated = []  # platform names for which at least one autovalidated platform was found
    log.info("Performing AUTOVALIDATED platforms")
    for plat, reason in validated:
        log.info("--> platform: id=%s name=%s url=%s" % (plat.id, plat.platform_name, plat.url))
        # log.info("--> Inf: %s" % plat.influencer)

        if not is_acceptable_social_url(plat.url):
            log.info('Url %r is not acceptable social url' % plat.url)
            continue

        plat.url = deparameterize_url(plat.url)

        # finding best duplicate
        dups = models.Platform.find_duplicates(plat.influencer,
                                               plat.url,
                                               plat.platform_name,
                                               exclude_url_not_found_true=False)
        if dups is not None and len(dups) > 0:
            # Found some duplicates
            log.info("We have found %s duplicates for %s platform with url %s" % (
                len(dups),
                plat.platform_name,
                plat.url,
            ))

            # deciding which duplicate will we use
            # Priority: 1) url_not_found != True AND autovalidated=True
            #           2) autovalidated=True
            #           3) the rest
            # if several: ordering by ids

            dups_sorted = sorted(dups, key=lambda x: (
                (
                    0 if x.autovalidated is True and x.url_not_found is not True
                        else 1 if x.autovalidated is True else 2
                ),
                x.id
            ))

            dup_plat = dups_sorted[0]
            log.info("Using duplicate platform: id=%s name=%s url=%s" % (dup_plat.id,
                                                                         dup_plat.platform_name,
                                                                         dup_plat.url))

            # making all remaining duplicates hidden
            for bad_dup in dups_sorted[1:]:
                platformutils.set_url_not_found('duplicate_platform', bad_dup, to_save=to_save)

            # marking platform for which autovalidated platform is found
            if dup_plat.platform_name not in platform_name_autovalidated:
                platform_name_autovalidated.append(dup_plat.platform_name)

            save_validation_result(reason, dup_plat, to_save=False)

            # adding platform to list of platforms which we reveal and save
            platforms_to_show.append((dup_plat, reason))

        else:
            # no duplicates found
            log.info("No duplicates found")
            # marking platform for which autovalidated platform is found
            if plat.platform_name not in platform_name_autovalidated:
                platform_name_autovalidated.append(plat.platform_name)

            save_validation_result(reason, plat, to_save=False)

            # adding platform to list of platforms which we reveal and save
            platforms_to_show.append((plat, reason))

    # Performing non-autovalidated now
    log.info("Performing NON-AUTOVALIDATED platforms")
    for plat in not_validated:
        log.info("--> platform: id=%s name=%s url=%s" % (plat.id, plat.platform_name, plat.url))

        # checking that this is an acceptable social platform url
        if not is_acceptable_social_url(plat.url):
            log.info('Url %r is not acceptable social url' % plat.url)
            continue

        # checking if we have already autovalidated platform for this platform name in list of newly discovered
        if plat.platform_name in platform_name_autovalidated:
            log.info("%s is already in a list of autovalidated, skipping..." % plat.platform_name)
            # exists, skipping that
            continue
        # checking if we have already autovalidated platform for this platform name in DB
        if plat.platform_name in list(plat.influencer.platform_set.filter(platform_name=plat.platform_name,
                                                                          autovalidated=True)):
            # we already have at least one autovalidated platform of this type
            log.info("we already have at least one autovalidated platform for %s, skipping..." % plat.platform_name)
            continue

        # check if we have only one platform for this platform_type
        ctr = 0
        for p in not_validated:
            # print('%s vs %s' % (p, plat))
            if p.url != plat.url and p.platform_name == plat.platform_name:
                ctr += 1
                # print('ctr increased')
        if ctr > 0:
            # seems there are several platforms for this platform type, moving to the next platform
            log.info("Seems there are %s more non-autovalidated platforms for %s, skipping..." % (ctr, plat.platform_name))
            continue

        plat.url = deparameterize_url(plat.url)

        # checking existing disabled duplicates of this platform
        dups = models.Platform.find_duplicates(plat.influencer,
                                               plat.url,
                                               plat.platform_name,
                                               exclude_url_not_found_true=False)
        if dups is not None and len(dups) > 0:
            # Found some duplicates
            log.info("We have found %s duplicates for non-autovalidated %s platform with url %s" % (
                len(dups),
                plat.platform_name,
                plat.url,
            ))

            # deciding which duplicate will we use
            # Priority: 1) url_not_found != True AND autovalidated=True
            #           2) autovalidated=True
            #           3) the rest
            # if several: ordering by ids

            dups_sorted = sorted(dups, key=lambda x: (
                (
                    0 if x.autovalidated is True and x.url_not_found is not True
                        else 1 if x.autovalidated is True else 2
                ),
                x.id
            ))

            dup_plat = dups_sorted[0]

            log.info("Using duplicate platform: id=%s name=%s url=%s" % (dup_plat.id, dup_plat.platform_name, dup_plat.url))

            # making all remaining duplicates concealed
            for bad_dup in dups_sorted[1:]:
                platformutils.set_url_not_found('duplicate_platform', bad_dup, to_save=to_save)

            # adding platform to list of platforms which we reveal and save
            platforms_to_show.append((dup_plat, 'single_nonautovalidated_platform_of_a_type'))
            log.info("We will show it!")

        else:
            # no duplicates found
            log.info("No duplicates found")
            # adding platform to list of platforms which we reveal and save
            platforms_to_show.append((plat, 'single_nonautovalidated_platform_of_a_type'))
            log.info("We will show it!")

    # Save the validated, selected platforms to DB
    if to_save:
        for pl, reason in platforms_to_show:

            if pl.platform_name == 'Facebook' and not is_profile_fb_url(pl):
                platformutils.set_url_not_found('facebook_page_without_likes', pl, to_save=to_save)

            else:
                pl.url_not_found = False
                log.debug('Saving platform %r', pl)
                pl.save()
                pl.influencer.platform_validations[pl.url] = (pl.platform_name, datetime.utcnow().isoformat())

    # Save links into *_url fields:
    # first, select a single platform from the chosen to be saved
    urlfields_by_pname = {pl.platform_name: pl for pl, _ in platforms_to_show}

    # # if there's only one non-validated for a new platform name, use it
    # for pname, pls in non_validated_by_pname.items():
    #     if pname not in urlfields_by_pname and len(pls) == 1:
    #         urlfields_by_pname[pname] = pls[0]
    #
    # log.info('urlfields_by_pname:\n%s', pformat(urlfields_by_pname))

    if to_save:
        source_pl.influencer.clear_url_fields()
        source_pl.influencer.remove_from_validated_on(constants.ADMIN_TABLE_INFLUENCER_FASHION)
        for pl in urlfields_by_pname.values():
            pl.append_to_url_field(source_pl.influencer)
        source_pl.influencer.save()

    # for debugging and testing
    tlocal._latest_validated, tlocal._latest_not_validated = validated, not_validated

    # If we have more than 1 and none of them are validated => inspect them
    # first to see if there are widgets we are not aware of.
    # for pname, pls in non_validated_by_pname.items():
    #     if pname not in validated_by_pname and len(pls) > 1:
    #         log.info('Multiple non-validated platforms: {}'.format({
    #             'source_pl_id': str(source_pl.id),
    #             'source_pl_url': repr(source_pl.url),
    #             'invalid_urls': repr([pl.url for pl in pls]),
    #         }))

    return [pl for pl, _ in platforms_to_show]


@task(name="platformdatafetcher.platformextractor.extract_clustered_platforms", ignore_result=True)
@baker.command
def extract_clustered_platforms(url, influencer=None):
    """Uses clustering algorithm only
    """
    try:
        with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, disable_cleanup=settings.DEBUG) as xb:
            pe = PlatformClusteringExtractor(xb, url, influencer)
            clusters = pe.extract_platform_clusters()
            log.info('returned clusters: %r', clusters)
            if clusters:
                return clusters[0]
            return None
    except Exception as e:
        log.exception(e, extra={'influencer_id': influencer.id if influencer else None})
        return None

def _select_best_for_platform_name(platforms):
    by_platform_name = defaultdict(list)
    for platform in platforms:
        by_platform_name[platform.platform_name].append(platform)
    res = []
    for platform_name, pls in by_platform_name.items():
        if len(pls) == 1:
            res.append(pls[0])
            continue
        for pl in pls:
            if platformutils.username_from_platform_url(pl.url):
                res.append(pl)
                break
    return res


@task(name="platformdatafetcher.platformextractor.extract_platforms_from_platform", ignore_result=True)
@baker.command
def extract_platforms_from_platform(platform_id=None, platform_object=None, to_save=True,
                                    disable_cleanup=None):
    """Collects platforms linked from the platform pointed by either `platform_id` (`int`) or
    `platform_object` (:class:`debra.models.Platform` instance).
    """
    assert platform_id is not None or platform_object is not None
    pl = models.Platform.objects.get(id=int(platform_id)) \
        if platform_id is not None \
        else platform_object
    with platformutils.OpRecorder('extract_platforms_from_platform', platform=pl):
        return _do_extract_platforms_from_platform(pl, to_save, disable_cleanup)


def _do_extract_platforms_from_platform(pl, to_save, disable_cleanup):
    if disable_cleanup is None:
        disable_cleanup = settings.DEBUG
    try:
        with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, disable_cleanup=disable_cleanup) as xb:
            collector = PlatformLinksCollector(xb, pl)
            platforms = collector.extract_platforms()

            res = []
            seen_urls = set()
            for platform in platforms:
                if platform.url in seen_urls:
                    continue
                seen_urls.add(platform.url)
                corrected_social_handle, match_count = social_page_contains_blog_domain_text(platform.url, pl.url)
                log.info('Match count: %d', match_count)
                if corrected_social_handle:
                    platform.url = corrected_social_handle
                    log.warn('+++ Social page %s contains blog domain %s', platform.url, pl.url)
                    res.append(platform)
                else:
                    log.warn('--- Social page %s does not contain blog domain %s', platform.url, pl.url)

            res = _select_best_for_platform_name(res)

            if to_save:
                convert_or_save_platforms(pl, res, xb=xb)
            return res
    except Exception as e:
        log.exception(e, extra={'pl': pl,
                                'to_save': to_save,
                                'disable_cleanup': disable_cleanup})
        return None

@baker.command
def submit_extract_platforms_from_platform_tasks(qs=None):
    if qs is None:
        qs_trendsetters = models.Platform.objects.all().\
            filter(platform_name__in=models.Platform.BLOG_PLATFORMS).\
            filter(influencer__shelf_user__userprofile__is_trendsetter=True)
        qs_ss = models.Platform.objects.all().\
            filter(platform_name__in=models.Platform.BLOG_PLATFORMS).\
            filter(influencer__source='spreadsheet_import')
        print 'c1', qs_trendsetters.count()
        print 'c2', qs_ss.count()
        qs = qs_trendsetters | qs_ss
    qs = qs.values('id')
    cnt = qs.count()
    log.info('Submitting %s extract_platforms_from_platform tasks', cnt)
    for d in qs:
        extract_platforms_from_platform.apply_async(args=[d['id']], queue='platform_extraction')


@baker.command
def extract_platforms_from_profile_blog_page(userprofile_id, to_save=False):
    up = models.UserProfile.objects.get(id=int(userprofile_id))
    pls = models.Platform.objects.filter(url=up.blog_page)
    if not pls.exists():
        log.error('No platforms for userprofile %s', up)
        return []
    pl = pls[0]
    log.info('Found platform based on up.blog_page: %s', pl)
    found_platforms = extract_platforms_from_platform(pl.id, to_save)

    for found_pl in found_platforms:
        page_field = '%s_page' % found_pl.platform_name.lower()
        page_val = getattr(up, page_field)
        log.info('=== platform_name=%s platform_url=%s %s=%s', found_pl.platform_name,
                 found_pl.url, page_field, page_val)
        if not page_val or not found_pl.url:
            log.warn('!!! one of urls empty')
        elif utils.strip_url_of_default_info(page_val, False) == \
                utils.strip_url_of_default_info(found_pl.url, False):
            log.warn('+++ values are the same')
        else:
            log.warn('--- values are different')


@baker.command
def run_blog_page_extraction(max_procs='1'):
    procs = []
    for up_id in test_data.USER_PROFILE_IDS_WITH_BLOG_PAGE_MATCHING_PLATFORM[:int(max_procs)]:
        log.info('processing up_id=%s', up_id)
        p = subprocess.Popen(' '.join(['python', '-m', 'platformdatafetcher.platformextractor',
                                       'extract_platforms_from_profile_blog_page', str(up_id),
                                       '>', 'blog_page_extract_%s.log' % up_id, '2>&1']),
                             shell=True)
        procs.append(p)
    for p in procs:
        p.wait()
    log.warn('finished run_blog_page_extraction')


@task(name="platformdatafetcher.platformextractor.extract_platforms_from_posts", ignore_result=True)
@baker.command
def extract_platforms_from_posts(platform_id=None, platform_object=None, to_save=True, disable_cleanup=False):
    """Uses algorithm collecting links from posts only.
    """
    assert platform_id is not None or platform_object is not None
    pl = models.Platform.objects.get(id=int(platform_id)) \
        if platform_id is not None \
        else platform_object
    log.info('Using platform %r', pl)
    # we use a common name for operation: extract_platforms_from_platform
    try:
        with platformutils.OpRecorder('extract_platforms_from_platform', platform=pl) as opr:
            with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, disable_cleanup=disable_cleanup) as xb:
                fe = PlatformFromPostsExtractor(xb, pl)
                res = fe.extract_platforms_from_posts(to_save=False)
                log.debug('extract_platforms_from_posts res: %s', res)
                if to_save:
                    convert_or_save_platforms(pl, res, xb=xb)
                opr.data = {'platform_urls': [p.url for p in res]}
                return res
    except Exception as e:
        log.exception(e, extra={'platform_id': platform_id,
                                'platform_object': platform_object,
                                'to_save': to_save,
                                'disable_cleanup': disable_cleanup})
        return None


def fetch_insta_profile_by_post_url(insta_post_url=None, xb=None):
    """
    This method returns link to author's instagram by posts's link
    :param insta_post_url: link to instagram post
    :return: link to post's author
    """

    def post_to_profile(insta_post_url, xb):
        xb.driver.get(insta_post_url)
        time.sleep(2)
        try:
            author_node = xb.driver.find_element_by_xpath("//main//article/header/div/a")
            author_node.click()
            time.sleep(2)
            author_url = xb.driver.current_url
        except NoSuchElementException:
            log.info('No author\'s url is found, seems post is missing')
            return None

        log.info('Found author url: %s' % author_url)
        return author_url

    if insta_post_url is None:
        return None

    log.info('Trying to get platform url for Instagram post %s:' % insta_post_url)

    if xb is None:
        with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                                  load_no_images=True, timeout=30) as xb:
            xb.driver.set_script_timeout(30)
            xb.driver.implicitly_wait(30)
            return post_to_profile(insta_post_url, xb)
    else:
        return post_to_profile(insta_post_url, xb)


def collect_social_urls_from_blog_url(xb=None, by_pname=defaultdict(), platform=None, non_social_url=None):
    """
    extracted reusable part from extract_combined where we extracted social urls from blog url
    :return:
    """

    def update(links):
        for url_link in links:
            url_link = redirect_using_xbrowser(url_link, timeout=10, normalize_socials=True)
            pname = platformutils.social_platform_name_from_url(platform.url if platform is not None else non_social_url,
                                                                url_link,
                                                                allow_insta_posts=True)
            if pname == platformutils.PLATFORM_NAME_DEFAULT:
                continue

            # Check for user name uniqueness
            username = platformutils.username_from_platform_url(url_link)
            existing_usernames = [platformutils.username_from_platform_url(u) for u in by_pname[pname]]
            existing_usernames = [n.lower() for n in existing_usernames if n]
            log.debug('existing_usernames: %r', existing_usernames)
            if username and username.lower() in existing_usernames:
                log.debug('Skipping duplicated link %r', url_link)
                continue

            by_pname[pname].append(url_link)

    try:
        xb.driver.implicitly_wait(2)
        xb.load_url(platform.url if platform is not None else non_social_url)
        time.sleep(2)
    except:
        return

    # print('***********************')
    # a_el = xb.driver.find_elements_by_xpath('//body')
    # if len(a_el) > 0:
    #     print(a_el[0].get_attribute('innerHTML'))
    # print('***********************')

    widget_links = socialwidgets.find_owner_urls_from_widgets(xb)
    update(widget_links)
    log.debug('Links after getting widget links: %s', by_pname)

    clustering_extractor = PlatformClusteringExtractor(xb,
                                                       platform.url if platform is not None else non_social_url,
                                                       influencer=platform.influencer if platform else None)
    pl_clusters = clustering_extractor.extract_platform_clusters(to_save=False)
    log.debug('pl_clusters: %r', pl_clusters)
    clusters = [[p.url for p in c] for c in pl_clusters]
    # this below function is quite weird, commenting it out (I coudln't understand it)
    #clusters = [c for c in clusters if has_unique_domains(c)]
    log.debug('Clusters with unique domain names: %s', clusters)
    for c in clusters:
        update(c)
    log.debug('Links after getting clusters: %s', by_pname)

    if platform is not None:
        fp_extractor = PlatformFromPostsExtractor(xb, platform)
        common_pls = fp_extractor.extract_platforms_from_posts(to_save=False)
        log.debug('extract_platforms_from_posts res: %s', common_pls)
        update([p.url for p in common_pls])
        log.debug('Links after getting from common posts: %s', by_pname)


def open_url(url):
    try:
        return urllib2.urlopen(
            urllib2.Request(url, None, REQUESTS_HEADERS),
            timeout=10
        )
    except:
        logging.exception("Couldn't open url %s", url)
        return


def collect_any_social_urls(xb=None, non_social_url=None, use_urllib=False):
    """
    Returns any social urls found on the given page.

    :param xb -- XBrowser instance
    :param non_social_url -- url to analyze
    :param use_urllib: use urllib2 instead of xbrowser (for now it doesn't
                       process iframes but works much faster)
    :return: list of social urls detected
    """

    result = set()
    if non_social_url is None:
        log.error('Url is None, returning empty list')
        return []

    from lxml.html import fromstring

    # regexp patterns for social profiles
    social_regexps = [
        # Twitter patterns
        r"^(?:https?:\/\/)?(?:www\.)?twitter\.com\/(#!\/)?[a-zA-Z0-9_]+$",

        # Facebook patterns
        r"(?:https?:\/\/)?(?:www\.)?facebook\.com\/.(?:(?:\w)*#!\/)?(?:pages\/)?(?:[\w\-]*\/)*([\w\-\.]*)",

        # Instagram patterns
        r"(?:(?:http|https):\/\/)?(?:www.)?(?:instagram.com|instagr.am)\/([A-Za-z0-9-_]+)",

        # Pinterest patterns
        r"http(s)?:\/\/?(?:www\.)?pinterest.com\/[^\/\?]*",

        # Youtube patterns
        r"((http|https):\/\/|)(www\.)?youtube\.com\/(channel\/|user\/|c\/)?[a-zA-Z0-9]{1,}",

        # Tumblr patterns
        r".*\.tumblr\.com\/?",

        # Google plus pattern
        r"(https?://)?(plus\.)?google\.com/(.*/)?(\+[^/]+|\d{21})",
    ]

    def get_matched_url(u):
        u = urllib2.unquote(u)
        for sr in social_regexps:
            match = re.match(sr, u)
            if match:
                return match.group(0)

    try:
        if use_urllib:
            response = open_url(non_social_url)
            if not response:
                return []
            ps = response.read()
        else:
            # loading the url
            xb.driver.implicitly_wait(2)
            xb.load_url(non_social_url)
            time.sleep(2)
            ps = xb.driver.page_source
        initial_page = fromstring(ps)

        # Fetching urls and collecting only social ones
        urls = initial_page.xpath('//a/@href')

        for url in urls:
            matched_url = get_matched_url(url)
            if matched_url:
                log.info('Url %r considered to be social', matched_url)
                result.add(matched_url)

        if use_urllib:
            return list(result)

        iframes = xb.driver.find_elements_by_tag_name('iframe')
        if not len(iframes):
            return list(result)

        for iframe in iframes:
            xb.driver.switch_to_frame(iframe)

            ps = xb.driver.page_source
            iframe_page = fromstring(ps)
            urls = iframe_page.xpath('//a/@href')

            for url in urls:
                matched_url = get_matched_url(url)
                if matched_url:
                    log.info(
                        'Iframe: Url %r considered to be social', matched_url
                    )
                    result.add(matched_url)

            xb.driver.switch_to_default_content()

    except Exception as e:
        log.exception(e)
        return list(result)

    return list(result)


def substitute_instagram_post_urls(url_dict=defaultdict()):
    """
    Substituting Instagram posts' urls with their authors' profiles urls
    :param url_dict -- dict of detected urls
    :return:
    """
    #
    instagram_links_discovered = []
    for link in url_dict.get('Instagram', []):

        link = xbrowsermod.validate_url(link)
        if link is None:
            continue

        # Checking for Instagram posts' urls
        if 'instagram.com/p/' in link.lower():
            # seems we have an insta post url here
            author_link = fetch_insta_profile_by_post_url(link)
            if author_link is not None and author_link not in instagram_links_discovered:
                instagram_links_discovered.append(author_link)
        else:
            if link not in instagram_links_discovered:
                instagram_links_discovered.append(link)
    if len(instagram_links_discovered) > 0:
        url_dict['Instagram'] = instagram_links_discovered


@task(name="platformdatafetcher.platformextractor.extract_combined", ignore_result=True)
@baker.command
def extract_combined(platform_id=None, platform_object=None, to_save=True, disable_cleanup=False):
    """
    1. Check for widgets: facebook, twitter, snapwidget, instgram. If found the expected one, we're done with that particular social platform.
    2. If not, check for clusters (each url with a different domain)
    3. If not, check for common links across posts.
    """
    assert platform_id is not None or platform_object is not None
    platform = models.Platform.objects.get(id=int(platform_id)) \
        if platform_id is not None \
        else platform_object
    log.info('Using platform %r', platform)

    max_retries = 3

    with platformutils.OpRecorder('extract_platforms_from_platform', platform=platform) as opr:

        # Retrying if getting some WebBrowserException
        tries = 0
        last_exception = None
        while tries < max_retries:

            try:
                with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                                          load_no_images=True, disable_cleanup=disable_cleanup, timeout=60) as xb:

                    by_pname = defaultdict(list)

                    # collecting social urls from
                    collect_social_urls_from_blog_url(xb=xb, by_pname=by_pname, platform=platform)

                    # Substituting Instagram posts' urls with their authors' profiles urls
                    substitute_instagram_post_urls(by_pname)

                    log.info('Instagram post links conversion finished')

                    # Making facebook urls straight-forward
                    facebook_links_discovered = []
                    for link in by_pname.get('Facebook', []):
                        log.info('Link: %s' % link)
                        link = redirect_using_xbrowser(link, normalize_socials=True)
                        log.info('Link redirect: %s' % link)
                        link = xbrowsermod.validate_url(link)
                        if link is None:
                            continue
                        log.info('Link after validation: %s' % link)

                        # getting username
                        fb_username = platformutils.username_from_platform_url(link)
                        if fb_username is not None:
                            profile_link = "https://www.facebook.com/%s" % fb_username
                            facebook_links_discovered.append(profile_link)
                            # print('FB profile link %r appended')

                    if len(facebook_links_discovered) > 0:
                        by_pname['Facebook'] = facebook_links_discovered

                    log.info('Facebook links conversion finished')

                    # Convert back all links to Platforms
                    log.info('*** BY_NAME')
                    log.info(by_pname)
                    all_pls = [models.Platform(url=link.strip(),
                                               platform_name=pname,
                                               influencer=platform.influencer)
                               for pname in by_pname for link in by_pname[pname] if link is not None]

                    # Removing platforms which have similar final urls (after all redirects)
                    cleaned_pls = []
                    for plat in all_pls:
                        log.info(plat.url)

                        plat_url = xbrowsermod.validate_url(plat.url)
                        if plat_url is None:
                            continue

                        redirected_url = deparameterize_url(redirect_using_xbrowser(plat_url, normalize_socials=True))
                        # log.info(' * plat=%s redirected=%s' % (plat.url, redirected_url))
                        # log.info(' * TYPES plat=%s redirected=%s' % (type(plat.url), type(redirected_url)))
                        if plat.url != redirected_url:
                            plat.url = redirected_url

                        # checking for HTML status
                        # # TODO: check if it is really needed, because Selenium has no means of retreiving HTML status code
                        # r = requests.get(plat.url, headers=requests_headers, timeout=15)
                        # if r.status_code >= 400:
                        #     # inappropriate status code
                        #     continue

                        # checking for unique entry of each platform url here
                        if any([c.url == redirected_url for c in cleaned_pls]):
                            pass

                        # checking for correctness of platform's url
                        if not is_acceptable_social_url(plat.url):
                            pass

                        cleaned_pls.append(plat)
                    all_pls = cleaned_pls

                    log.info('=================================')
                    log.info('Platforms found by links:')
                    for pl in all_pls:
                        log.info('%s, %s' % (pl.platform_name, pl.url))
                    log.info('=================================')

                    # graph initializing, adding 1-st tier discovered urls
                    dslp = DiscoveredSocialLinkPool(blog_platform=platform)
                    # for p in all_pls:
                    #     print('+= += += Appending 1-st tier platform to dslp: %s' % p)
                    #     dslp.append_platform_to_graph(parent_platform=platform, platform=p)

                    log.info('DSLP initialized, now there should be initial 0-level platform (blog platform): ')
                    dslp.describe()

                    final_pls = convert_or_save_platforms(platform, all_pls, to_save, xb=xb, dslp=dslp)
                    opr.data = {'platform_urls': [p.url for p in final_pls]}

                    # log.info('=================================')
                    # log.info('Final plaforms:')
                    # for pl in final_pls:
                    #     log.info('%s, %s, autovalidated=%s, url_not_found=%s' % (pl.platform_name,
                    #                                                              pl.url,
                    #                                                              pl.autovalidated,
                    #                                                              pl.url_not_found))
                    # log.info('=================================')

                    return final_pls
            except WebDriverException as e:
                last_exception = e
                log.exception(e)
                tries += 1
                time.sleep(10)
                log.warn('Retrying performing platform %s due to WebDriverException' % platform.id)

            except Exception as e:
                last_exception = e
                log.exception(e, extra={'platform_id': platform_id,
                                        'platform_object': platform_object,
                                        'to_save': to_save,
                                        'disable_cleanup': disable_cleanup})
                # log.info('%s Exception %s' % ('*'*30, '*'*30,))
                # opr.pdo.error_msg = e
                # exc_type, exc_value, exc_traceback = sys.exc_info()
                # opr.pdo.error_tb = traceback.print_exception(exc_type, exc_value, exc_traceback, limit=5)
                #
                tries += 1
                time.sleep(10)

        log.warning('Failed to perform platform %s for %s attempts' % (platform.id, max_retries))
        if last_exception is not None:
            raise last_exception

        return None


def check_web_page_for_content(page_url=None, content=None):
    """
    :param page_url: url of web page to check
    :param content: text chunk to search for in page's html content
    :return: True if content is located in page's html content
    """

    log.info('page_url: %s  content: %s' % (page_url, content))

    if page_url is None:
        log.info('page_url should be a string with url')
        return None

    if content is None:
        log.info('content should be a string')
        return None

    with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                              load_no_images=True, timeout=30) as xb:

        # setting timeouts to xb instance
        xb.driver.set_script_timeout(30)
        xb.driver.implicitly_wait(15)

        xb.driver.get(page_url)
        time.sleep(2)
        ps = xb.driver.page_source

        found = True if content in ps else False

        # if we did not find it on main page, check all iframes also
        if not found:

            iframes = xb.driver.find_elements_by_tag_name('iframe')
            if len(iframes) > 0:
                for iframe in iframes:
                    xb.driver.switch_to_frame(iframe)
                    ps = xb.driver.page_source
                    if content in ps:
                        found = True
                    xb.driver.switch_to_default_content()
                    if found:
                        break

        log.info('content was found: %s' % found)
        return found


@task(name="platformdatafetcher.platformextractor.autovalidate_platform", ignore_result=True)
def autovalidate_platform(source_platform_id, platform_id):
    platform = models.Platform.objects.get(id=platform_id)
    with platformutils.OpRecorder('autovalidate_platform', platform=platform):
        if source_platform_id is not None:
            source_platform = models.Platform.objects.get(id=source_platform_id)
        else:
            source_platform = platform.influencer.blog_platform
        if source_platform is None:
            raise ValueError('No blog platform for %r', platform.influencer)
        log.info('Old autovalidated, autovalidated_reason: %r, %r', platform.autovalidated,
                 platform.autovalidated_reason)
        from xpathscraper.xbrowser import redirect_using_xbrowser
        redirected_url = redirect_using_xbrowser(source_platform.url, timeout=20)
        reason = validate_platform(source_platform, platform, redirected_url)
        save_validation_result(reason, platform)
        # if validated correctly, we should see if other platforms can be autovalidated as well
        if reason:
            influencer = platform.influencer
            validated_plats = influencer.platforms().filter(autovalidated=True)
            non_validated = list(influencer.platforms().exclude(autovalidated=True))
            validated = list()
            for v in validated_plats:
                validated.append((v, v.autovalidated_reason))
            do_further_validation_using_validated_platforms(validated, non_validated)
        else:
            # Here we load blog url and look if platform's url exists on page. If it exists and if this platform
            # was created more than ??? ago, we consider this platform validated.

            # check that this platform is 1+ month old by date_edited field
            date_edited = platform.influencer.date_edited
            if date_edited is not None and date_edited < datetime.now() - timedelta(days=30):
                log.info('influencer\'s date_edited is older than 30 days')
                page_has_content = check_web_page_for_content(page_url=source_platform.url, content=platform.url)
                if page_has_content:
                    save_validation_result('platform_age', platform)
            else:
                log.info('influencer\'s date_edited is null or newer than 30 days')

        log.info('New autovalidated, autovalidated_reason: %r, %r', platform.autovalidated,
                 platform.autovalidated_reason)

def deparameterize_url(url=''):
    """
    Strips url of query params
    :param url:
    :return:
    """
    if url.find('?') > 0:
        url = url[:url.find('?')]
    return url


@baker.command
def extract_compare():
    blogging_platforms = ['Blogspot', 'Wordpress']
    plats = models.Platform.objects.filter(influencer__shelf_user__isnull=False, platform_name__in=blogging_platforms)
    print "Working on %d platforms " % plats.count()
    for p in plats:
        print "Searching %s" % p.url
        social_plats_found = extract_platforms_from_platform(p.id)
        print "Result: found %d platform" % len(social_plats_found)
        for s in social_plats_found:
            print "Found new platforms: ", s.url, s.platform_name
        existing = models.Platform.objects.filter(influencer=p.influencer).exclude(platform_name__in=blogging_platforms)
        for s in existing:
            print "We already have: %s, %s" % (s.url, s.platform_name)

        print "\n-----done-----\n"


class LightSocialUrlsExtractor(object):
    """
    Extractor for social urls from given text, optional urls and their found
    urls.
    """
    max_safety_iteration = 100

    # Urls with domains ending on any of these will be skipped
    dts = deepcopy(domains_to_skip)
    dts.remove('liketoknow.it')
    unappropriate_domains = dts + ['vsco.com', 'l.co', ]

    def __init__(self):
        self._reset()

    def _reset(self):
        self.social_urls = set()
        self.non_social_urls = set()
        self._platform_to_url = defaultdict(dict)

    @property
    def all_urls(self):
        return self.social_urls | self.non_social_urls

    def _is_acceptable_url(self, url=None, only_socials=True):
        """
        Checks if this url is acceptable
        * it is not a social url of another social network
        * it is not an empty social platform url (like http://instagram.com/)
          -- for socials only
        * it is not some sharer/login page's url for social network
        :param url:
        :return:
        """
        # checking that this is not an empty social platform url
        parsed = urlparse.urlparse(url)
        # Tumblr check
        if only_socials:
            if parsed.netloc.endswith('tumblr.com'):
                if len(parsed.netloc[:-10].replace('www.', '')) > 0:
                    pass
                else:
                    return False
            else:
                # other socials should have non-empty path
                if len(parsed.path.strip('').strip('/')) == 0:
                    return False

        # Checking that this url is not just a root url for social network
        if is_url_social_for_social(url, None):
            return False

        # unappropriate domains for urls: excludes stuff like etsy.com, vk.com,
        # vsco.com, etc...
        dmn = parsed.netloc.lower()
        if dmn is not None and dmn.startswith('www.'):
            dmn = dmn[4:]
        if dmn in self.unappropriate_domains:
            return False

        # Checking that it is not a service page of social network
        # Validating url's path
        if any(
            [
                (
                    bdmn is None or parsed.netloc.lower().endswith(bdmn)
                ) and (
                    bpath is None or parsed.path.startswith(bpath)
                ) for bdmn, bpath in BAD_URL_DOMAIN_PATH_PARTS if (
                    bdmn is not None or bpath is not None
                )
            ]
        ):
            return False

        return True

    def _add_social_url(self, platform_name, url):
        username = username_from_platform_url(url)
        if username and username not in self._platform_to_url[platform_name]:
            self._platform_to_url[platform_name][username] = url
            self.social_urls.add(url)
            return url

    def _add_non_social_url(self, url):
        added_urls = set()

        def try_add_url(u):
            if u not in self.non_social_urls:
                self.non_social_urls.add(u)
                added_urls.add(u)

        url = url.rstrip('/')
        parsed = urlparse.urlsplit(url)
        urls_to_add = set([
            url,
            # Hostname url: http://example.com/page1 -> http://example.com
            urlparse.urlunsplit((parsed.scheme, parsed.netloc, '', '', '',)),
            # Contact page: http://example.com -> http://example.com/contact
            urlparse.urlunsplit(
                (parsed.scheme, parsed.netloc, 'contact', '', '',)
            ),
        ])
        for url_to_add in urls_to_add:
            try_add_url(url_to_add)
        return tuple(urls_to_add), tuple(added_urls),

    @staticmethod
    def get_url_endpoint(url, xb=None, youtube_user_channels=None):
        """
        Try to get the target url after all redirects if any.
        :param url:
        :param xb: optional XBrowser instance to use if we fail to find
                   redirects with curl
        :param youtube_user_channels: optional defaultdict(set) to save found
               youtube channels per user
        :return:
        """
        url = xbrowsermod.validate_url(url)
        if not url:
            return

        cached_url = cache.get('redirect_url:%s' % url)
        if cached_url is not None:
            return cached_url

        try:
            redirected_url = subprocess.check_output(
                (
                    'curl -ILs -H "User-agent: %s" -o /dev/null '
                    '-w "%%{url_effective}" %s'
                ) % (
                    REQUESTS_HEADERS.get('User-Agent', ''), url
                ),
                shell=True
            )
        except (subprocess.CalledProcessError, TypeError, ):
            logging.exception(
                'Failed to get redirect url with curl for %s', url
            )
            return

        def get_domain(u):
            return re.sub('^www\.', '', urlparse.urlsplit(u).netloc)
        # We can't do straight url comparison due to http/https/slashes/etc.
        if get_domain(url) == get_domain(redirected_url):
            # curl failed to redirect -> try XBrowser
            def get_xb_url(u, _xb):
                _xb.driver.implicitly_wait(2)
                tries_count = 0
                limit = XBROWSER_OPEN_URL_TRIES_LIMIT
                while tries_count < limit:
                    try:
                        _xb.load_url(u)
                        return _xb.driver.current_url
                    except:
                        tries_count += 1
                else:
                    logging.exception('Failed to open %s with xbrowser', u)
                    return u
            if xb:
                redirected_url = get_xb_url(redirected_url, xb)
            else:
                with LightSocialUrlsExtractor.create_xbrowser() as xb:
                    redirected_url = get_xb_url(redirected_url, xb)

        try:
            channel = platformutils.get_youtube_channel_for_url(redirected_url)
        except ConnectionError:
            logging.exception(
                'Failed to get youtube channel for %s', redirected_url
            )
            return
        if channel:
            if 'youtube.com/channel/' not in channel.lower():
                channel = channel.lower()
            youtube_user_page = get_youtube_user_from_channel(channel)
            if youtube_user_page and youtube_user_channels is not None:
                youtube_user_channels[youtube_user_page].add(channel)
            channel = youtube_user_page or channel
        redirected_url = channel or redirected_url.lower() or ''
        if not redirected_url:
            return
        cache.set(
            'redirect_url:%s' % url, redirected_url, 60 * 60 * 24
        )
        return redirected_url

    def _canonize_url(self, url, is_social_guaranteed=False):
        def get_repr(_url):
            username = username_from_platform_url(_url)
            return '{}_{}'.format(
                platformutils.social_platform_name_from_url(None, _url),
                username
            ) if username else None
        if is_social_guaranteed:
            return get_repr(url)
        url = LightSocialUrlsExtractor.get_url_endpoint(url) or ''
        if self._is_social_acceptable(url):
            return get_repr(url)
        return url.rstrip('/')

    @staticmethod
    def _get_platform_from_canonized_url(canonized_url):
        for platform in set(
            [regex[0] for regex in PLATFORM_PROFILE_REGEXPS]
        ):
            if canonized_url.startswith(platform):
                return platform
        return

    def _format_url(self, url):
        if not url:
            return
        if self._social_platform(url):
            return url
        url = url.rstrip('/')
        parsed = urlparse.urlsplit(url)
        netloc = re.sub('^www\.', '', parsed.netloc)
        return urlparse.urlunsplit((
            parsed.scheme, netloc, parsed.path, parsed.query,
            parsed.fragment,
        ))

    def _social_platform(self, url):
        if not url:
            return
        social_pl_name = platformutils.social_platform_name_from_url(
            None, url
        )
        if social_pl_name in models.Platform.SOCIAL_PLATFORMS:
            return social_pl_name

    def _is_social_acceptable(self, url):
        return self._social_platform(url) and self._is_acceptable_url(
            url, only_socials=True
        )

    def add_url(self, url):
        """
        :param url:
        :return:  tuple of added urls
        """
        url = LightSocialUrlsExtractor.get_url_endpoint(url)
        if not url or url in self.all_urls:
            return

        social_pl_name = self._social_platform(url)
        if social_pl_name:
            if self._is_acceptable_url(url, only_socials=True):
                added_url = self._add_social_url(social_pl_name, url)
                if added_url:
                    return (added_url,), (added_url,),
        else:
            if self._is_acceptable_url(url, only_socials=False):
                return self._add_non_social_url(url)

    def add_urls_from_text(self, description):
        """
        Extracts urls by regexp from given description.
        :param description: text description given
        :return: tuple(all_found_urls, added_urls_that_pass_checks)

        Multiple if
        """
        from platformdatafetcher.contentfiltering import find_all_urls

        if not description:
            return set(), set()

        # this can be buggy
        # Example: for this instagram profile <jessicapettway: id=4895078>
        # it gave pr.com as a url which is not correct.
        # TODO: fix this method later on
        # description = simplify(description, preserve_urls=True)

        added_urls = set()
        cleaned_urls = set()
        for new_url in find_all_urls(description) + list(
            get_profile_urls_from_usernames(description)
        ):
            # TODO: fix find_all_urls() regex
            new_url = self._format_url(
                self.get_url_endpoint(new_url.rstrip(','))
            )
            if not new_url:
                continue
            add_url_result = self.add_url(new_url)
            if not add_url_result:
                cleaned_urls.add(new_url)
                continue

            urls_collected, urls_to_add = add_url_result
            if urls_to_add:
                added_urls |= set(urls_to_add)
            if urls_collected:
                cleaned_urls |= set(urls_collected)
            else:
                cleaned_urls.add(new_url)
        return cleaned_urls, added_urls

    @staticmethod
    def create_xbrowser():
        return xbrowsermod.XBrowser(
            headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
            load_no_images=True, disable_cleanup=False,
            timeout=10
        )

    @staticmethod
    def get_instagram_post_author(instagram_post_url):
        import json
        import lxml.html
        try:
            response = open_url(instagram_post_url)
            tree = lxml.html.fromstring(response.content)
            data = json.loads(
                tree.xpath(
                    '//script[contains(text(), "window._sharedData")]/text()'
                )[0].lstrip('window._sharedData =').rstrip(';')
            )
            return data['entry_data']['PostPage'][0]['media']['owner'][
                'username'
            ]
        except:
            return

    @staticmethod
    def get_twitter_timeline(twitter_username):
        try:
            from platformdatafetcher.socialfetcher import TwitterFetcher
            twitter = TwitterFetcher._create_twitter()
            return list(
                twitter.statuses.user_timeline(screen_name=twitter_username)
            )
        except:
            return []

    @staticmethod
    def _is_instagram_post(url):
        parsed = urlparse.urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        if domain == 'instagram.com' and parsed.path.startswith('/p/'):
            return True
        return False

    def extract_urls(
        self, description, extra_urls=None, profile_username=None,
    ):
        """
        Input: text + (optional) urls
        1. Extract all urls
        2. Iterate through all urls:
           => If url is social:
              => Extract urls from description
           => If url is blog:
              => Extract social urls from page contents
           recursively do the same for all new urls found
        :return:
        """
        from . import fetcher

        self._reset()

        extra_urls = extra_urls or []

        log.info("Entering")

        # (0.5) if we have username, then we have instagram social url!
        insta_url_canonized = None
        insta_url = None
        if profile_username is not None:
            insta_url = (
                'https://www.instagram.com/%s/' % profile_username
            ).lower()
            self._add_social_url('Instagram', insta_url)
            insta_url_canonized = self._canonize_url(
                insta_url, is_social_guaranteed=True
            )

        desired_tumblr = self._canonize_url(
            'http://{}.tumblr.com'.format(profile_username),
            is_social_guaranteed=True
        )
        def verify_tumblr(urls):
            """
            Tumblr pages have no links so they are impossible to validate using
            backlinks, so we autovalidate tumblr if it's found during web
            crawling and it has the same username as original instagram
            :param urls:  a list of urls to check for Tumblr
            :return:  tumblr url if validated or None otherwise
            """
            for url in urls:
                if self._canonize_url(url) == desired_tumblr:
                    return desired_tumblr

        # (1) extracting all urls from description
        extracted_urls, _ = self.add_urls_from_text(description)
        tumblr_verified = verify_tumblr(extracted_urls)

        # (2) Create other platform URLs by combining instagram username and
        # usernames found in description with platforms:
        # e.g. https://instagam.com/qwerty/ has twitter username @q1w2e3 in the
        # description, then we create extra URLs to check: 'youtube/qwerty',
        # 'facebook/qwerty', 'youtube/q1w2e3', 'facebook/q1w2e3, etc
        platform_usernames = find_all_usernames(description)
        platform_usernames.add(profile_username)
        for username in platform_usernames:
            for platform_name in SOCIAL_PLATFORMS.ALL:
                url = get_url_for_username(username, platform_name)
                if url:
                    extra_urls.append(url)
        extra_urls = list(set(extra_urls))

        # (3) adding extra urls if any to discovered urls
        for extra_url in extra_urls:
            extra_url = self._format_url(self.get_url_endpoint(extra_url))
            self.add_url(extra_url)

        log.info(
            'Initial social urls: %s; non-social urls: %s',
            self.social_urls, self.non_social_urls
        )

        # (4) chain-checking urls
        parent_urls = defaultdict(set)
        iteration = 0  # safety iteration
        all_urls_verified = dict((url, False) for url in self.all_urls)
        while any(
            [v is False for v in all_urls_verified.values()]
        ) and iteration < self.max_safety_iteration:

            url_to_check = all_urls_verified.keys()[
                all_urls_verified.values().index(False)
            ]
            parent_canonize = self._canonize_url(url_to_check)

            log.info('Checking url: %s', url_to_check)

            if self._social_platform(url_to_check):
                log.info('SOCIAL URL: %s', url_to_check)
                url_description = fetcher.try_get_social_description(
                    url_to_check, xb=None, extra_fields=True
                )
                log.info('Got description: %s', url_description)

                if url_description:
                    collected_urls, added_urls = self.add_urls_from_text(
                        url_description
                    )
                    log.info('Added urls from description: %s', added_urls)
                    if parent_canonize:
                        for url in collected_urls:
                            url_canonize = self._canonize_url(url)
                            if url_canonize:
                                parent_urls[url_canonize].add(parent_canonize)

                    for url in added_urls:
                        all_urls_verified[url] = False
                    if not tumblr_verified:
                        tumblr_verified = verify_tumblr(collected_urls)
            else:
                log.info('NOT SOCIAL URL: %s', url_to_check)
                with self.create_xbrowser() as xb:
                    social_urls_from_blog_page = collect_any_social_urls(
                        xb=xb, non_social_url=url_to_check
                    )
                if len(
                    social_urls_from_blog_page
                ) > SOCIAL_URLS_PER_BLOG_LIMIT:
                    log.info(
                        'Too many social urls for %s, skipping', url_to_check
                    )
                    all_urls_verified[url_to_check] = True
                    iteration += 1
                    continue

                social_urls = filter(
                    lambda url: self._is_social_acceptable(url),
                    map(
                        lambda url: self.get_url_endpoint(url),
                        social_urls_from_blog_page
                    )
                )
                log.info('Collected social urls: %s', social_urls)
                for social_url in social_urls:
                    if self.add_url(social_url):
                        log.info('Add social urls: %s', social_url)
                        all_urls_verified[social_url] = False

                    if parent_canonize:
                        url_canonize = self._canonize_url(social_url)
                        if url_canonize:
                            parent_urls[url_canonize].add(parent_canonize)
                if not tumblr_verified:
                    tumblr_verified = verify_tumblr(social_urls)

            all_urls_verified[url_to_check] = True
            iteration += 1

        # (5) Do autovalidation using backlinks here and remove non-validated
        # from urls and non_social_urls
        def get_all_parents(url, parents_set=None):
            if not parents_set:
                parents_set = set()
            for parent in parent_urls[url]:
                if parent not in parents_set:
                    parents_set.add(parent)
                    parents_set = get_all_parents(parent, parents_set)
            return parents_set

        def get_children(parent_url):
            children = set()
            for url, parents in parent_urls.iteritems():
                if parent_url in parents:
                    children.add(url)
            return children

        validated_urls = set() if not tumblr_verified else {tumblr_verified, }
        if insta_url_canonized:
            for parent in get_all_parents(insta_url_canonized):
                validated_urls.add(parent)
        log.info('Backlink validated urls: %s', validated_urls)

        # Find all social platforms that were validated: we'll skip them
        all_social_platforms = set(
            [regex[0] for regex in PLATFORM_PROFILE_REGEXPS]
        )

        def get_validated_platforms():
            validated_platforms = set()
            for canonized_url in validated_urls:
                for platform in all_social_platforms:
                    if canonized_url.startswith('{}_'.format(platform)):
                        validated_platforms.add(platform)
            return validated_platforms

        allowed_platforms = all_social_platforms - get_validated_platforms()
        allowed_platforms.discard('Instagram')  # we started from Instagram

        # Get all youtube validated urls and autovalidate their children,
        # since youtube 'about' page always has valid links
        #
        # search all validated Youtube children links and validate all social
        # platfroms links except for those platfroms that already validated
        new_validated_urls_per_platform = defaultdict(set)
        for canonized_url in validated_urls:
            if not canonized_url.startswith('Youtube_'):
                continue
            for child in get_children(canonized_url):
                for platform in allowed_platforms:
                    if child.startswith('{}_'.format(platform)):
                        new_validated_urls_per_platform[platform].add(child)
        new_validated_urls = set()
        for platform, urls in new_validated_urls_per_platform.iteritems():
            expected_valid_link = '{}_{}'.format(platform, profile_username)
            if expected_valid_link in urls:
                new_validated_urls.add(expected_valid_link)
            else:
                new_validated_urls |= set(urls)

        log.info('Youtube validated urls: %s', new_validated_urls)
        validated_urls |= new_validated_urls
        if insta_url:
            validated_urls.discard(insta_url)

        # If a social platform having the same username as original Instagram
        # has a same link the Instagram does - we validate this platform
        allowed_platforms -= set(new_validated_urls_per_platform.keys())
        instagram_child_links = get_children(insta_url_canonized)
        new_validated_urls = set()
        if instagram_child_links:
            for platform_name in allowed_platforms:
                url = get_url_for_username(
                    profile_username, platform_name.lower()
                )
                if not url:
                    continue
                social_candidate = self._canonize_url(url)
                if instagram_child_links & get_children(social_candidate):
                    new_validated_urls.add(social_candidate)
            log.info(
                'Same Instagram link validated urls: %s', new_validated_urls
            )
            validated_urls |= new_validated_urls
            allowed_platforms -= get_validated_platforms()
            new_validated_urls_parents = set()
            for url in new_validated_urls:
                for parent in get_all_parents(url):
                    platform = self._get_platform_from_canonized_url(parent)
                    if platform is None or platform in allowed_platforms:
                        new_validated_urls_parents.add(parent)
                        if platform:
                            allowed_platforms.discard(platform)
            log.info(
                'Same Instagram link validated urls parents: %s',
                new_validated_urls_parents
            )
            validated_urls |= new_validated_urls_parents

        # Handle special Twitter case: Twitter has same username as Instagram
        # and no shared links, but has Instagram posts links in the timeline
        allowed_platforms -= get_validated_platforms()
        if 'Twitter' in allowed_platforms:
            from platformdatafetcher.contentfiltering import find_all_urls
            validated_twitter = None
            for post in self.get_twitter_timeline(profile_username):
                for url in find_all_urls(post.get('text', '')):
                    url = self.get_url_endpoint(url)
                    if not url or not self._is_instagram_post(url):
                        continue
                    if self.get_instagram_post_author(
                        url
                    ) == profile_username:
                        validated_twitter = self._canonize_url(
                            get_url_for_username(
                                profile_username, SOCIAL_PLATFORMS.TWITTER
                            ),
                            is_social_guaranteed=True
                        )
                        break
                if validated_twitter:
                    log.info(
                        'Twitter timeline has instagram posts: %s',
                        validated_twitter
                    )
                    validated_urls.add(validated_twitter)
                    for parent in get_all_parents(validated_twitter):
                        platform = self._get_platform_from_canonized_url(
                            parent
                        )
                        if platform is None or platform in allowed_platforms:
                            validated_urls.add(parent)
                    break

        log.info(
            'Result social urls: %s; non-social urls: %s',
            self.social_urls, self.non_social_urls
        )
        log.info('Verified url: %s', insta_url_canonized)
        log.info('Parent urls: %s', parent_urls)
        log.info('Validated urls: %s', validated_urls)

        # return a list of found urls
        social_urls_validated = set()
        for social_url in self.social_urls:
            if self._canonize_url(
                social_url, is_social_guaranteed=True
            ) in validated_urls:
                social_urls_validated.add(social_url)
        # We need to remove duplicates and more specific urls from non-social
        # urls and also transform "contact" pages to main:
        # [http://example.com/contact, http://example.com/mypage1, ] ->
        # -> [http://example.com, ]
        urls_per_domain = dict()
        for non_social_url in self.non_social_urls & validated_urls:
            parsed = urlparse.urlsplit(non_social_url)
            path = '' if parsed.path == '/contact' else parsed.path
            url = urlparse.urlunsplit((
                parsed.scheme, parsed.netloc, path, parsed.query,
                parsed.fragment,
            ))
            current_url = urls_per_domain.get(parsed.netloc)
            if not current_url or len(url) < len(current_url):
                urls_per_domain[parsed.netloc] = url

        return (
            list(social_urls_validated),
            urls_per_domain.values(),
        )


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
