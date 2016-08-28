"""
Fetcher implementations that use RSS feeds for fetching posts and post interactions.
Looks for link to RSS feed on the page, fetches all entries with feedparser and saves as posts
Apparently it is useful as a low-overhead replacement for fetching posts from the blog itself
"""

import logging
import urlparse
import itertools
import json
from collections import defaultdict
import socket
import datetime

from . import feedparsing
from lxml.etree import XMLSyntaxError
from celery.decorators import task
import baker
import requests
import requests.exceptions
import lxml.html

from xpathscraper import utils, xbrowser
from debra import models
from debra import helpers
from platformdatafetcher import platformutils
from platformdatafetcher import fetcherbase
from platformdatafetcher.activity_levels import recalculate_activity_level


log = logging.getLogger('platformdatafetcher.feeds')


class FeedResolver(object):
    """
    Resolve the best feed URL for a blog platform by using several strategies:

    1. Checking the <link> tags on the main page.
    2. Check "common" feed URL's like /feed
    3. Check for links to .rss resources and ones pointing to FeedBurner.

    The implementation follows HTTP redirects and even loads the page with a full browser to support
    JavaScript-based redirects. It also runs the steps above on all frames pointing to the same domain.

    Each discovered blog URL is assigned a priority, so that we can pick main "pure" blog page feeds
    over ones discovered in frames or pointing to FeedBurner. We also validate feeds and reject the ones
    with no entries (As returned by feedparser: that could mean no content, invalid XML, etc).

    To avoid requesting the same URL's over and over again (frame traversal and hardcoded URL resolution)
    we cache the loaded pages with their parsed lxml HTML trees.

    The main entrypoint is the get_feed_url method.
    """
    DISCOVERY_FRAME_LIMIT = 10
    HARDCODED_FEED_PATHS = [
        '/feed',
    ]

    class FeedPage(object):
        def __init__(self, url):
            self.url = url
            self.content = None
            self.redirected_url = None

            self._get()

        def _get(self):
            try:
                # setting verify=True to bypass SSL certificate validation for some blogs
                # http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification
                r = requests.get(self.url,
                                 timeout=feedparsing.FEED_FETCH_TIMEOUT,
                                 headers=utils.browser_headers(),
                                 verify=False)
                r.raise_for_status()
                self.content = r.content
                self.redirected_url = r.url
            except requests.exceptions.RequestException:
                log.exception('Error in feed resolution fetching %r', self.url)

        @property
        def tree(self):
            if not hasattr(self, '_tree'):
                try:
                    if self.content:
                        self._tree = lxml.html.fromstring(self.content)
                    else:
                        self._tree = None
                except XMLSyntaxError:
                    self._tree = None
            return self._tree

        @property
        def error(self):
            return not self.content

    def __init__(self, root_url):
        check = root_url.lower()
        if not check.startswith('http://') and not check.startswith('https://'):
            root_url = 'http://' + root_url

        self.root_url = root_url
        self._loaded_pages = {}
        self._discovered_feeds = {}

    def _get_page(self, url):
        if url in self._loaded_pages:
            return self._loaded_pages[url]

        page = self.FeedPage(url)
        self._loaded_pages[page.url] = page
        self._loaded_pages[page.redirected_url] = page

        return page

    def _feed_found(self, priority, feed_url):
        if feed_url not in self._discovered_feeds:
            self._discovered_feeds[feed_url] = priority

    def _discover_feeds(self):
        page = self._get_page(self.root_url)
        if not page.error:
            self._discover_any_feed_url((0,), page.redirected_url, page.tree)

        #### Let's now try to discover the correctly re-directed url
        try:
            redirected_using_xbrowser = xbrowser.redirect_using_xbrowser(self.root_url)
            page = self._get_page(redirected_using_xbrowser)
            if not page.error:
                self._discover_any_feed_url((1,), redirected_using_xbrowser, page.tree)
        except socket.timeout:
            log.exception('Error in feed redirect resolution fetching %r', self.root_url)

        log.warn('Trying to load frame, because feed url was not found for the url %r', self.root_url)
        frame_srcs = self._get_own_frames(self.root_url, page.tree)
        for index, src in enumerate(frame_srcs):
            frame_page = self._get_page(src)
            if frame_page.error:
                continue
            self._discover_any_feed_url((2,), src, frame_page.tree)

    def get_feed_url(self):
        self._discover_feeds()
        prioritized_feeds = sorted(self._discovered_feeds.keys(),
                                   key=lambda url: self._discovered_feeds[url])
        for feed_url in prioritized_feeds:
            if self.feed_valid(feed_url):
                return feed_url

        log.info('No valid feed found for {}. Discovered: {}'.format(self.root_url, prioritized_feeds))
        return None

    def _do_discover_feed(self, priority, blog_url, tree):
        rss_links = tree.xpath('//link') + tree.xpath('//a') + tree.xpath('//area')
        for position, rss_link in enumerate(rss_links):
            href = rss_link.attrib.get('href')
            if not href:
                continue
            else:
                href = href.replace('\n', '').replace('\t', '').replace('\r', '')

            type = rss_link.attrib.get('type', '').strip().lower()
            if 'rss' in type or \
                    'atom+xml' in type or \
                    href.lower().endswith(('rss', 'rss.xml')):
                feed_url = urlparse.urljoin(blog_url, href)
                self._feed_found(priority + (0, position), feed_url)

            if is_feedburner_url(href):
                feed_url = urlparse.urljoin(blog_url, href)
                self._feed_found(priority + (1, position), feed_url)

    def _detect_hardcoded_feed_url(self, priority, blog_url):
        for feed_path in self.HARDCODED_FEED_PATHS:
            full_url = urlparse.urlunparse(urlparse.urlparse(blog_url)._replace(path=feed_path))
            page = self._get_page(full_url)
            if not page.error and ('<?xml' in page.content.lower() or '<rss' in page.content.lower()):
                log.info('Hardcoded feed url %r is good', feed_path)
                self._feed_found(priority + (0,), full_url)

    def _discover_any_feed_url(self, priority, blog_url, tree):
        from_page_priority = priority + (0,)
        self._do_discover_feed(from_page_priority, blog_url, tree)

        from_hardcoded_url_priority = priority + (1,)
        self._detect_hardcoded_feed_url(from_hardcoded_url_priority, blog_url)

    def _get_own_frames(self, url, tree):
        if not url or tree is None:
            return []

        frame_like = tree.xpath('//iframe') + tree.xpath('//frame')
        srcs_to_check = []
        valid_fragments = ['blogspot', platformutils.meaningful_domain_fragment(url)]
        valid_fragments = [vf for vf in valid_fragments if vf]
        for fl in frame_like:
            src = fl.attrib.get('src')
            if not src:
                continue
            domain = utils.domain_from_url(src)
            if any(vf in domain for vf in valid_fragments):
                srcs_to_check.append(src)
        log.info('srcs_to_check: %r', srcs_to_check)
        srcs_to_check = srcs_to_check[:self.DISCOVERY_FRAME_LIMIT]
        return srcs_to_check

    def parse_feed(self, url):
        log.info('Parsing feed %r' % url)
        return feedparsing.parse(url)

    def feed_valid(self, url):
        parsed_feed = self.parse_feed(url)
        if len(parsed_feed.entries) == 0:
            return False

        return len(parsed_feed.entries) > 0


def discover_feed(url):
    resolver = FeedResolver(url)
    return resolver.get_feed_url()


def clean_url(url):
    """
    Removes utm_* query params frequently present in urls in a feed
    """
    def change(qs):
        invalid_keys = [k for k in qs if k.startswith('utm')]
        for k in invalid_keys:
            del qs[k]
    return utils.do_with_query_params(url, change)


def resolve_feedburner_url(url):
    return utils.resolve_http_redirect(url)


def is_feedburner_url(url):
    domain = utils.domain_from_url(url)
    if 'feedproxy' in domain or 'feedburner' in domain:
        return True
    return False


def _entries_id_set(feed):
    return set((e.get('link'), e.get('id')) for e in feed.entries)


def _paging_works(original_feed, feed_url, paging_fun):
    page_2_url = paging_fun(feed_url, 2)
    log.debug('page_2_url: %r', page_2_url)
    page_2_feed = feedparsing.parse(page_2_url)
    original_entry_ids = _entries_id_set(original_feed)
    page_2_entry_ids = _entries_id_set(page_2_feed)
    #log.info('original_entry_ids: %r', original_entry_ids)
    #log.info('page_2_entry_ids: %r', page_2_entry_ids)
    if not page_2_feed.entries or original_entry_ids == page_2_entry_ids:
        log.debug('Paging does not work for method %r feed %r', paging_fun.__name__, feed_url)
        return False
    log.debug('Paging works for method %r feed %r', paging_fun.__name__, feed_url)
    return True


def _paging_fun_wordpress(feed_url, page_number):
    return utils.set_query_param(feed_url, 'paged', str(page_number))


def _paging_fun_blogspot(feed_url, page_number):
    return utils.set_query_param(feed_url, 'start-index', str(page_number))

PAGING_FUNS = [_paging_fun_wordpress, _paging_fun_blogspot]


def _fetch_all_entries(furl):

    log.debug('Parsing feed url: %r' % furl)
    f = feedparsing.parse(furl)

    paging_fun = next((pf for pf in PAGING_FUNS if _paging_works(f, furl, pf)), None)

    yield f.entries

    if paging_fun is None:
        log.debug('Paging does not work for feed %r', furl)
        return

    page_no = 2
    entries = []
    while True:
        log.debug('Fetching page %s', page_no)
        f_curr = feedparsing.parse(utils.set_query_param(furl, 'paged', str(page_no)))
        new_entries = f_curr.entries[:]
        existing_urls = {e['link'] for e in entries if 'link' in e}
        new_urls = [u['link'] for u in new_entries if 'link' in u and u['link'] not in existing_urls]
        log.debug('new_urls: %r', new_urls)
        if len(new_urls) == 0:
            log.warn('No new urls, stopping on page %s', page_no)
            break
        yield new_entries
        entries += new_entries
        page_no += 1


def _fetch_and_clean(feed_url):
    for entries_raw in _fetch_all_entries(feed_url):
        entries = []
        for e in entries_raw:
            if 'link' in e:
                if is_feedburner_url(e['link']):
                    try:
                        e['link'] = resolve_feedburner_url(e['link'])
                    except:
                        log.exception('While resolve_feedburner_url')
                e['link'] = clean_url(e['link'])
            entries.append(e)
        log.debug('Urls from entries: %r', [e.get('link') for e in entries])
        yield entries


def fetch_entries(platform):
    """
    For a given blog url, returns an iterator yielding pages of entries
    """
    if not platform.feed_url_up_to_date():
        feed_url = discover_feed(platform.url)
        platform.set_feed_url(feed_url)
        if feed_url:
            log.debug('Discovered feed url: %r from %r', feed_url, platform.url)
        else:
            log.warn('Cannot discover feed url from %r', platform.url)
            return

    feed_url = platform.feed_url
    if not feed_url:
        log.warn('Skipping entry loads for a platform with no feed_url %r', platform.url)
        return

    log.debug('Feed url found: %r' % feed_url)

    for entries in _fetch_and_clean(feed_url):
        yield entries


def fetch_entries_from_all_pages(platform, max_pages):
    return utils.flatten(itertools.islice(fetch_entries(platform), 0, max_pages))


class PostsDateFixer(object):

    def __init__(self, platform, max_pages=50):
        self.platform = platform
        self.entries = fetch_entries_from_all_pages(self.platform, max_pages)
        self.entries_by_url = {e['link']: e for e in self.entries}

    def update_posts_dates(self, to_save=False):
        for post in self.platform.posts_set.order_by('-id'):
            if post.url not in self.entries_by_url:
                log.warn('No feed entry for post %r', post)
                continue
            entry = self.entries_by_url[post.url]
            time_struct = entry.published_parsed if hasattr(entry, 'published_parsed') else entry.updated_parsed
            feed_dt = utils.from_struct_to_dt(time_struct)
            log.info('Date from post: %s, from feed: %s', post.create_date, feed_dt)
            if post.create_date.date() != feed_dt.date() and to_save:
                post.create_date = feed_dt
                post.save()
                log.info('Updated')


class FeedFetcher(fetcherbase.Fetcher):
    CONTENT_PATHS = [
        ['content', 0, 'value'],
        ['content', 'value'],
        ['content'],
        ['summary_detail', 0, 'value'],
        ['summary_detail', 'value'],
        ['summary'],
    ]

    FOLLOWER_NAME_PATHS = [
        ['author_detail', 'name'],
        ['author'],
    ]

    def __init__(self, platform, policy, test_run=False):
        super(FeedFetcher, self).__init__(platform, policy)

        self.test_run = test_run

    def _assure_valid_platform_url(self):
        if self.platform.feed_url_up_to_date():
            if not self.platform.feed_url:
                # Feed URL resolution has recently failed => platform not valid. Abort fetch.
                raise fetcherbase.FetcherException('Platform has no feed URL: {}'.format(self.platform.url))
            else:
                # Platform ok - skip validation.
                return

        feed_url = discover_feed(self.platform.url)
        self.platform.set_feed_url(feed_url)
        self.platform.inc_api_calls()

        if not feed_url:
            if self.platform.get_failed_recent_fetches() > 3:
                # Give up, mark platform with url_not_found and avoid fetching it anymore.
                platformutils.set_url_not_found('discover_feed_failed', self.platform)
            raise fetcherbase.FetcherException('Cannot discover feed url')

        if urlparse.urlsplit(self.platform.url).path.rstrip('/'):
            domain_url = utils.url_without_path(self.platform.url)
            domain_feed_url = discover_feed(domain_url)
            if domain_feed_url == feed_url:
                log.warn('Platform url %r and domain url %r have the same feed url %r, updating platform url to domain url', self.platform.url, domain_url, domain_feed_url)
                helpers.update_platform_url(self.platform, domain_url)
                if self.platform.influencer.blacklisted or self.platform.url_not_found:
                    raise fetcherbase.FetcherException('Platform/influencer is invalid after changing url to a domain url')
            else:
                log.info('Platform url contains a path, but feed urls are different: %r %r',
                         domain_feed_url, feed_url)

    def _content_from_entry(self, e):
        return utils.firstnested(e, self.CONTENT_PATHS)

    @recalculate_activity_level
    def fetch_posts(self, max_pages=5, pis_max_pages=5, include_only_post_urls=None, force_fetch_more=False):
        """
        @param force_fetch_more if set to True, the caller is responsible for the termination and setting appropriate
               limit on max_pages
        """
        self._assure_valid_platform_url()

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        res = []
        if include_only_post_urls is not None:
            # Normalize urls
            include_only_post_urls = {platformutils.url_to_handle(u) for u in include_only_post_urls}
        self.platform.inc_api_calls()

        stop_processing = False

        for page_no, entries in enumerate(fetch_entries(self.platform)):
            entries_skipped = 0
            if self.test_run:
                entries = entries[:2]

            # Flag raised from inner loop - stop fetching new entries
            if stop_processing:
                break

            for e in entries:
                if not self.policy.should_continue_fetching(self) and not force_fetch_more:
                    stop_processing = True
                    break

                # date can be present in multiple places
                if not hasattr(e, 'published_parsed') and not hasattr(e, 'updated_parsed'):
                    log.error('No date in feed entry %r', e)
                    continue
                if include_only_post_urls is not None and \
                        platformutils.url_to_handle(e['link']) not in include_only_post_urls:
                    log.info('Post url %r not in included urls', e['link'])
                    continue

                post_url = e['link']
                previously_saved = list(models.Posts.objects.filter(url=post_url, platform=self.platform))
                if previously_saved:
                    if self.should_update_old_posts():
                        log.debug('Updating existing post for url {}'.format(post_url))
                        post = previously_saved[0]
                    else:
                        self._inc('posts_skipped')
                        entries_skipped += 1
                        log.debug('Skipping already saved post with url {}'.format(post_url))
                        if not self.test_run:
                            continue
                else:
                    log.debug('Creating new post for url {}'.format(post_url))
                    post = models.Posts()

                post.influencer = self.platform.influencer
                post.show_on_search = self.platform.influencer.show_on_search
                post.platform = self.platform
                post.platform_name = self.platform.platform_name
                post.title = e['title']
                post.url = e['link']
                post.content = self._content_from_entry(e)
                time_struct = e.published_parsed if hasattr(e, 'published_parsed') else e.updated_parsed
                post.create_date = utils.from_struct_to_dt(time_struct)
                ## look for comment number in the body so that we can get this information even if the feed
                ## limits the comments shown in the feed
                ## TODO: we may need to expand the filter to include more types. Might need to check more blogs.
                if 'slash_comments' in e or 'slash:comments' in e:
                    log.debug('Found number of comments: %s', e['slash_comments'])
                    post.ext_num_comments = int(e['slash_comments'])

                api_data = {}
                for k in ('id', 'wfw_commentrss', 'commentrss', 'commentsrss'):
                    if e.get(k):
                        api_data[k] = e[k]
                post.api_id = json.dumps(api_data)

                self.save_post(post)
                res.append(post)

                pis = self.fetch_post_interactions_extra([post], max_pages=pis_max_pages)
                if self.test_run:
                    res += pis

            if not self.test_run and entries_skipped == len(entries):
                log.debug('All entries skipped, not fetching more (total entries: %s)' % len(entries))
                break
            if max_pages is not None and page_no >= max_pages:
                log.debug('Max pages reached')
                break

        return res

    def _pi_from_entry(self, post, e):
        pi = models.PostInteractions()
        pi.platform_id = post.platform_id
        pi.post = post

        author = utils.firstnested(e, self.FOLLOWER_NAME_PATHS)
        if author:
            pi.follower = self._get_follower(author, None)

        pi.create_date = utils.from_struct_to_dt(e.published_parsed)
        pi.content = utils.firstnested(e, self.CONTENT_PATHS)
        pi.if_liked = False
        pi.if_shared = False
        pi.if_commented = True
        #log.info('comment entry: %r', e)
        #log.info('comment date: %s', pi.create_date)
        return pi

    def _fetch_comments_from_feed(self, feed_url, post, max_pages):
        res = []
        self.platform.inc_api_calls()
        for page_no, entries in enumerate(_fetch_and_clean(feed_url)):
            for entry in entries:
                #log.info('Comment entry:\n%s', pprint.pformat(entry))
                pi = self._pi_from_entry(post, entry)
                if pi:
                    self._save_pi(pi, res)
            if max_pages is not None and page_no >= max_pages:
                log.info('Max pages reached for commments')
                break
        return res

    def _fetch_blogspot_comments(self, posts, max_pages):
        res = []
        for post in posts:
            try:
                api_data = json.loads(post.api_id)
            except:
                log.info('Exception while decoding api_id')
                continue
            if not isinstance(api_data, dict):
                log.warn('Invalid api_id')
                continue
            if 'id' not in api_data or 'post-' not in api_data['id']:
                log.warn('Invalid api_id')
                continue
            post_id = api_data['id'].split('-')[-1]
            feed_url = utils.urlpath_join(post.platform.url,
                '/feeds/{post_id}/comments/default/?alt=rss'.format(post_id=post_id))
            res += self._fetch_comments_from_feed(feed_url, post, max_pages)
        return res

    def _feed_url_from_api_data(self, api_data):
        for k in ('wfw_commentrss', 'commentrss', 'commentsrss'):
            if api_data.get(k):
                return api_data[k]
        return None

    def _fetch_wordpress_comments(self, posts, max_pages):
        res = []
        for post in posts:
            try:
                api_data = json.loads(post.api_id)
            except:
                log.info('Exception while decoding api_id')
                continue
            if not isinstance(api_data, dict):
                log.warn('Invalid api_data object')
                continue
            feed_url = self._feed_url_from_api_data(api_data)
            if not feed_url:
                log.warn('No comments feed url for post %r', post)
                continue
            res += self._fetch_comments_from_feed(feed_url, post, max_pages)
        return res

    def fetch_post_interactions(self, posts, max_pages=None):
        if self.platform.platform_name == 'Blogspot':
            return self._fetch_blogspot_comments(posts, max_pages)
        return self._fetch_wordpress_comments(posts, max_pages)

    def get_validated_handle(self):
        pass


class WordpressFF(FeedFetcher):
    name = 'Wordpress'


class BlogspotFF(FeedFetcher):
    name = 'Blogspot'


class CustomFF(FeedFetcher):
    name = 'Custom'


@baker.command
def test_feed_discovery():
    infs = models.Influencer.objects.filter(show_on_search=True)
    for inf in infs.iterator():
        feed_url = discover_feed(inf.blog_url)
        if feed_url:
            print 'DISCOVERY_YES feed url for %r %r: %r' % (inf, inf.blog_url, feed_url)
        else:
            print 'DISCOVERY_NO feed url for %r %r' % (inf, inf.blog_url)


@baker.command
def test_num_comments_from_feed():
    infs = models.Influencer.objects.filter(show_on_search=True, platform__platform_name='Custom')
    print '%d infs' % infs.count()
    for inf in infs.iterator():
        try:
            if not inf.blog_platform.platform_name == 'Custom':
                continue
            feed_url = discover_feed(inf.blog_url)
            if not feed_url:
                continue
            f = feedparsing.parse(feed_url)
            if not f.entries:
                continue
                if 'slash_comments' in f.entries[0]:
                    print 'NUMCOMMENTS_YES feed_url %r' % feed_url
            else:
                print 'NUMCOMMENTS_NO feed_url %r' % feed_url
        except:
            log.exception('While processing %r', inf)


@task(name='platformdatafetcher.feeds.update_posts_dates', ignore_result=True)
@baker.command
def update_posts_dates(platform_id):
    platform = models.Platform.objects.get(id=int(platform_id))
    with platformutils.OpRecorder(operation='update_posts_dates', platform=platform):
        ff = PostsDateFixer(platform)
        ff.update_posts_dates(to_save=True)


@task(name='platformdatafetcher.feeds.fetch_from_feed', ignore_result=True)
@baker.command
def fetch_from_feed(platform_id):
    platform = models.Platform.objects.get(id=int(platform_id))
    with platformutils.OpRecorder(operation='fetch_from_feed', platform=platform):
        ff = FeedFetcher(platform, None)
        ff.fetch_posts()


@baker.command
def feed_fetcher_test_run(platform_id, max_pages=3, pis_max_pages=3):
    platform = models.Platform.objects.get(id=int(platform_id))
    ff = FeedFetcher(platform, None, True)
    data = ff.fetch_posts(max_pages=int(max_pages), pis_max_pages=int(pis_max_pages))
    return data

REPORT_PER_PNAME = 40
REPORT_INT = 30
REPORT_PAGES = 1
REPORT_PIS_PAGES = 1


@baker.command
def generate_feed_fetcher_report():
    infs = models.Influencer.objects.filter(show_on_search=True)
    plats = []
    for platform_name in ('Blogspot', 'Wordpress', 'Custom'):
        plats += list(models.Platform.objects.filter(platform_name=platform_name,
                                                     influencer__in=infs)[:REPORT_PER_PNAME])
    plats += list(models.Platform.objects.filter(platform_name__in=('Blogspot', 'Wordpress', 'Custom'),
                                                 influencer__in=infs).
                                          exclude(content_lang='en')[:REPORT_INT])
    log.info('Processing %d platforms: %r', len(plats), plats)
    data = {}
    for plat in plats:
        if plat in data:
            log.info('Platform %r is already processed', plat)
            continue
        data[plat] = {'posts': [], 'pis_by_post_url': defaultdict(list)}
        try:
            all = feed_fetcher_test_run(plat.id, REPORT_PAGES, REPORT_PIS_PAGES)
        except:
            log.exception('While feed_fetcher_test_run, ignoring')
            continue
        for m in all:
            if isinstance(m, models.Posts):
                if m.url not in [x.url for x in data[plat]['posts']]:
                    data[plat]['posts'].append(m)
            elif isinstance(m, models.PostInteractions):
                if m.content not in [x.content for x in data[plat]['pis_by_post_url'][m.post.url]]:
                    data[plat]['pis_by_post_url'][m.post.url].append(m)
            else:
                assert False, 'Unknown model %r' % m
        utils.write_to_file('/tmp/feed_fetcher_data.pickle', data, 'pickle')
        html = html_from_feed_fetcher_data(data)
        utils.write_to_file('ff_report.html', html)

    return data


def _idiv(content):
    content = content.encode('utf-8') if content else ''
    return '<div>%s</div>' % content


def html_from_feed_fetcher_data(data):
    r = []
    for plat, pdata in data.items():
        r.append('<br><br><b>Blog {plat.url} {plat.platform_name}</b>'.format(plat=plat))
        r.append('<p>')
        for post in pdata['posts']:
            post_summary_line = '<br><b>Post {post.url} title: {post.title!r} date: {post.create_date}</b>'
            r.append(post_summary_line.format(post=post))
            r.append('<br>')
            r.append(_idiv(post.content))
            comments = pdata['pis_by_post_url'].get(post.url, [])
            r.append('<hr><p>%d comments' % len(comments))
            for comment in comments:
                r.append('<hr>Comment date: {comment.create_date}'.format(comment=comment))
                r.append('<br>')
                r.append(_idiv(comment.content))
    return '\n'.join(r)


def _links_to_post(post_url, entry_content):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(entry_content)
    link_urls = {a.attrs.get('href', '').lower() for a in soup.find_all('a')}
    return post_url.lower() in link_urls


@task(name='platformdatafetcher.feeds.check_feed', ignore_result=True)
def check_feed(platform_id):
    feed_url = models.Platform.objects.filter(pk=int(platform_id)).values_list(
        'feed_url', flat=True)[0]

    feed = feedparsing.parse(feed_url)
    check = models.FeedCheck(platform_id=platform_id, feed_url=feed_url)

    if feed.bozo:
        check.invalid_feed = True
        check.error = feed.bozo_exception
    elif len(feed.entries) == 0:
        check.no_entries = True
    else:
        first_entry = feed.entries[0]

        if 'content' in first_entry:
            check.full_posts = True
        if 'summary' in first_entry:
            check.summaries = True
        if 'summary_detail' in first_entry:
            check.summary_details = True

        if not check.full_posts and not check.summaries and not check.summary_details:
            log.info('Cannot determine full posts or summary for platform %r', platform_id)

        post_link = first_entry.get('link')
        content = utils.firstnested(first_entry, FeedFetcher.CONTENT_PATHS)
        if post_link and content:
            check.link_to_post = _links_to_post(post_link, content)

    check.save()


def _plain_text_length(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or '')
    return len(soup.text)


@task(name='platformdatafetcher.feeds.check_blog_post_length', ignore_result=True)
def check_blog_post_length(influencer_id, num_posts=20):
    influencer = models.Influencer.objects.get(pk=influencer_id)
    blog = influencer.blog_platform
    posts = blog.posts_set.order_by('-create_date')[:num_posts]

    lengths = [_plain_text_length(p.content) for p in posts]
    max_length = max(lengths)

    models.PostLengthCheck.objects.create(
        influencer=influencer,
        platform=blog,
        max_post_length=max_length,
    )


def recheck_searchable_influencers_post_length():
    # Get rid of old results first
    models.PostLengthCheck.objects.all().delete()

    influencer_ids = list(models.Influencer.objects.all().searchable().values_list('id', flat=True))
    for influencer_id in influencer_ids:
        check_blog_post_length.apply_async([influencer_id],
                                           queue='every_day.fetching.Custom',
                                           routing_key='every_day.fetching.Custom')


def first_entry(url):
    print(url)
    feed = feedparsing.parse(url)
    entry = feed.entries[0] if feed.entries else None
    return (url, entry)


def test_platforms_entries(platform_ids, use_requests=False):
    """
    Only used to compare the default feedparser HTTP transport with the requests one.
    """
    try:
        saved_use_requests = feedparsing.USE_REQUESTS
        feedparsing.USE_REQUESTS = use_requests

        from datetime import datetime
        import traceback
        import cPickle
        import itertools
        plats = list(models.Platform.objects.filter(id__in=platform_ids))
        print('Loaded %d platform entities.' % len(plats))

        result = {}
        for plat in plats:
            try:
                print('Fetching feed entries for platform: %s' % plat.pk)
                entries = [e for page in itertools.islice(fetch_entries(plat), 2) for e in page]
                result[plat.feed_url] = entries
            except:
                print('Error fetching entries from %s' % plat.feed_url)
                traceback.print_exc()

        timestamp = '%04d-%02d-%02d-%02d-%02d' % datetime.utcnow().timetuple()[:5]
        transport_name = 'requests' if use_requests else 'feedparser'
        with open('test_entries_%s_%s.pickle' % (transport_name, timestamp), 'w') as f:
            cPickle.dump(result, f)
    finally:
        feedparsing.USE_REQUESTS = saved_use_requests


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
