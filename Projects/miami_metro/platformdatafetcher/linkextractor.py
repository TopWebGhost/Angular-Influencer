"""Extracts links coming from a given blog platform.

The links are saved as :class:`debra.models.LinkFromPlatform` with a
:attr:`debra.models.LinkFromPlatform.kind` attribute that can be:

- ``common`` - a link appears on multiple posts. It means it's usually
  a navigation link, an ad, a social link etc.
- ``navigation`` - a link is a part of a horizontal or vertical cluster of links
  (this is detected using a Javascript algorithm that checks visual positions)
- ``hireme`` - links which have texts containing :data:``HIRE_ME_KEYWORDS``.

"""

import logging
from collections import defaultdict
from pprint import pformat

import baker
from celery.decorators import task
from django.conf import settings

from debra import models
from . import contentfiltering
from . import platformutils
from xpathscraper import utils
from xpathscraper import xutils
from xpathscraper import xbrowser as xbrowsermod


log = logging.getLogger('platformdatafetcher.linkextractor')


COMMON_LINKS_POSTS = 5
UNWANTED_EXTS = contentfiltering._IMG_EXTS + ('.css', '.js', '.less', '.ico',)
HIRE_ME_KEYWORDS = ['hire me', 'sponsor me']

BLACKLISTED_DOMAINS = [
    'schema.org',
    'gmpg.org',
    'w3.org',
    'secure',
    'www',
    'www.',
    'fonts.googleapis.com',
]

BLACKLISTED_URL_SUBSTRINGS = [
    '/search/label/',
    '_archive.html',
    '/search?updated-min',
]


_DOMAIN_TO_PLATFORM_ID = None
def domain_to_platform(domain):
    global _DOMAIN_TO_PLATFORM_ID
    if _DOMAIN_TO_PLATFORM_ID is None:
        log.info('Start fetching platform data')
        _DOMAIN_TO_PLATFORM_ID = {}
        for d in models.Platform.objects.all().values('id', 'url'):
            _DOMAIN_TO_PLATFORM_ID[utils.domain_from_url(d['url'])] = d['id']
        log.info('Finished')
    if domain not in _DOMAIN_TO_PLATFORM_ID:
        return None
    return models.Platform.objects.get(id=_DOMAIN_TO_PLATFORM_ID[domain])


def save_links(platform, kind, links_texts, to_save=False):
    res = []
    for link, text in links_texts:
        vlink = platformutils.url_to_handle(link)
        if models.LinkFromPlatform.objects.filter(source_platform=platform,
                                                  normalized_dest_url=vlink,
                                                  kind=kind).exists():
            log.info('Skipping saved link %r', link)
            continue
        lfp = models.LinkFromPlatform(source_platform=platform,
                                      dest_url=link,
                                      normalized_dest_url=vlink,
                                      link_text=text,
                                      kind=kind)
        if to_save:
            lfp.save()
        log.info('Created %r', lfp)
        res.append(lfp)
    return res


def filter_links_texts(links_texts):
    res = []
    for url, text in links_texts:
        domain = utils.domain_from_url(url)
        if domain in BLACKLISTED_DOMAINS:
            continue
        res.append((url, text))
    return res


class LinksFromPlatformUrlExtractor(object):

    def __init__(self, xbrowser, platform):
        self.xbrowser = xbrowser
        self.platform = platform

    def extract_links(self, to_save=False):
        html = self.xbrowser.driver.execute_script('return document.body.innerHTML')
        domain = utils.domain_from_url(self.xbrowser.driver.current_url)
        urls = contentfiltering.find_important_urls(html, [domain, 'www.' + domain])
        log.info('important urls (%s): %s', len(urls), urls)
        res = []
        for u in urls:
            pl = domain_to_platform(utils.domain_from_url(u))
            if pl is not None and pl.id != self.platform.id:
                log.info('detected link from <<%s>> to <<%s>> url <<%s>>', self.platform,
                         pl, u)
                lfp = models.LinkFromPlatform(source_platform=self.platform,
                                                    dest_platform=pl,
                                                    dest_url=u)
                if to_save:
                    lfp.save()
                res.append(lfp)
        return res


class CommonLinksExtractor(object):

    def __init__(self, platform):
        self.platform = platform
        self.source_handle = utils.domain_from_url(platformutils.url_to_handle(self.platform.url))

    def extract_links(self, to_save=False):
        posts_data = list(self.platform.posts_set.all().\
                          order_by('-create_date').\
                          values('url')\
                          [:COMMON_LINKS_POSTS])
        if not posts_data:
            log.warn('No posts for common links search')
            return []
        posts_urls = [d['url'] for d in posts_data]

        log.info('posts_urls: %r', posts_urls)

        # Maps link kind to a dictionary mapping a url to a set of urls
        by_kind = defaultdict(dict)
        for url in posts_urls:
            log.info('Fetching content from %r', url)
            by_kind['common_external'][url] = set()
            by_kind['common_internal'][url] = set()
            html_it = iter(utils.fetch_iframes(url))
            while True:
                try:
                    html = html_it.next()
                except StopIteration:
                    break
                except:
                    log.exception('While fetching html, skipping this url')
                    continue
                links_texts = contentfiltering.find_links_with_texts(html)
                links_texts = [(u, t) for (u, t) in links_texts if not u.endswith(UNWANTED_EXTS)]
                links_texts = [(u, t) for (u, t) in links_texts \
                               if not any(ss in u for ss in BLACKLISTED_URL_SUBSTRINGS)]
                by_kind['common_external'][url].update([(u, t) for (u, t) in links_texts \
                      if utils.domain_from_url(platformutils.url_to_handle(u)) != self.source_handle])
                by_kind['common_internal'][url].update([(u, t) for (u, t) in links_texts \
                      if utils.domain_from_url(platformutils.url_to_handle(u)) == self.source_handle])
        common = defaultdict(dict)
        for kind, links_texts_by_url in by_kind.items():
            nonempty_sets = [s for s in links_texts_by_url.values() if s]
            if len(nonempty_sets) < 2:
                log.warn('Not enough nonempty sets of links from posts for %s', kind)
                common[kind] = set()
                continue
            common[kind] = sorted(set.intersection(*nonempty_sets))
            common[kind] = filter_links_texts(common[kind])
            log.info('Common links of kind %r (%d):\n%s', kind, len(common[kind]), pformat(common[kind]))

        res = []
        for kind, common_links_texts in common.items():
            res += save_links(self.platform, kind, common_links_texts, to_save)
        return res


class HireMeLinksExtractor(object):

    def __init__(self, platform, xbrowser):
        self.platform = platform
        self.xbrowser = xbrowser

        self.xbrowser.load_url(self.platform.url)

    def extract_links(self, to_save=False):
        links = self.xbrowser.execute_jsfun_safe([], '_XPS.visibleLinksWithTexts',
                                                 HIRE_ME_KEYWORDS,
                                                 50)
        return save_links(self.platform, 'hireme', [(l, None) for l in links], to_save)


class NavigationLinksExtractor(object):

    def __init__(self, platform, xbrowser):
        self.platform = platform
        self.xbrowser = xbrowser

    def extract_links(self, to_save=False):
        clusters = xutils.find_navigation_links_clusters(self.xbrowser)
        # flatten all clusters
        els = [el for cluster in clusters for el in cluster]
        links_texts = [(el.get_attribute('href'), el.text) for el in els if el.get_attribute('href')]
        log.debug('links_texts: %r', links_texts)
        links_texts = utils.unique_sameorder(links_texts, key=lambda lt: lt[0])
        links_texts = [(link, text) for (link, text) in links_texts \
                       if utils.domain_from_url(link) == \
                          utils.domain_from_url(self.xbrowser.driver.current_url) and \
                          utils.url_contains_path(link)]
        return save_links(self.platform, 'navigation', links_texts, to_save)


@baker.command
def extract_links_from_platform_url(platform_id):
    try:
        pl = models.Platform.objects.get(id=int(platform_id))
        xb = xbrowsermod.XBrowser(pl.url)
        le = LinksFromPlatformUrlExtractor(xb, pl)
        le.extract_links()
    except Exception as e:
        log.exception(e, extra={'platform_id': platform_id})


@task(name="platformdatafetcher.linkextractor.extract_common_links_from_platform", ignore_result=True)
@baker.command
def extract_common_links_from_platform(platform_id):
    pl = models.Platform.objects.get(id=int(platform_id))
    with platformutils.OpRecorder(operation='extract_common_links_from_platform', platform=pl) as opr:
        old_links_q = pl.sourcelink_set.filter(kind__startswith='common') | \
                      pl.sourcelink_set.filter(kind__startswith='navigation')
        log.info('Deleting %d old links', old_links_q.count())
        old_links_q.delete()

        lfps = []

        ext = CommonLinksExtractor(pl)
        lfps += ext.extract_links(to_save=True)
        try:
            with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xbrowser:
                xbrowser.load_url(pl.url)
                ext = NavigationLinksExtractor(pl, xbrowser)
                lfps += ext.extract_links(to_save=True)
        except Exception as e:
            log.exception(e, extra={'platform_id': platform_id})

        opr.data = {'extracted': len(lfps)}


@task(name="platformdatafetcher.linkextractor.extract_hire_me_links", ignore_result=True)
@baker.command
def extract_hire_me_links(platform_id):
    pl = models.Platform.objects.get(id=int(platform_id))
    try:
        with platformutils.OpRecorder(operation='extract_hire_me_links', platform=pl) as opr:
            with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xbrowser:
                ext = HireMeLinksExtractor(pl, xbrowser)
                lfps = ext.extract_links(to_save=True)
                opr.data = {'extracted': len(lfps)}
    except Exception as e:
        log.exception(e, extra={'platform_id': platform_id})


@baker.command
def run_extract_common_links_from_platform_for_trensetters(limit):
    trendsetters = models.Influencer.objects.filter(shelf_user__userprofile__is_trendsetter=True)[:limit]
    for inf in trendsetters:
        pl = inf.blog_platform
        if not pl:
            log.warn('No platform for %r', inf)
            continue
        if pl.sourcelink_set.filter(kind__startswith='common_internal').exists():
            log.warn('Already processer: %r', pl)
            continue
        log.info('Running for %r', pl)
        extract_common_links_from_platform(pl.id)

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

