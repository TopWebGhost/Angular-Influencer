# -*- coding: utf-8
import json
import re
import logging
from datetime import datetime
import pytz
from django.conf import settings
import requests
import requests.exceptions
import lxml
import lxml.html
import iso8601
from debra import models
from xpathscraper import xbrowser as xbrowsermod
from platformdatafetcher import platformutils


log = logging.getLogger('platformdatafetcher.postinteratcionsfetcher')


class PostInteractionsFetcher(object):
    def __init__(self, xbrowser, post):
        self.xbrowser = xbrowser
        self.post = post

    def fetch_interactions(self, max_pages=None):
        raise NotImplementedError()

    @classmethod
    def url_contains_iframe(cls, url):
        raise NotImplementedError()

    @classmethod
    def fetch_for_posts(cls, posts):
        try:
            with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, load_no_images=True) as xb:
                for post in posts:
                    with platformutils.OpRecorder(operation='{0}_for_post'.format(cls.__name__.lower()), post=post):
                        fetcher = cls(xb, post)
                        yield fetcher.fetch_interactions()
        except Exception as e:
            log.exception(e, extra={'posts_len': len(posts)})

    def _local_naive_dt_as_utc(self, naive_time):
        """
        We seem to get from the DB naive datetime objects in the local timezone.
        To compare them with parsed comment times, we need to convert the times to UTC.
        """
        localtz = pytz.timezone(settings.TIME_ZONE)
        localized = localtz.localize(naive_time)
        return localized.astimezone(pytz.utc)


class DisqusPostInteractionsFetcher(PostInteractionsFetcher):
    def fetch_interactions(self, max_pages=None):
        self.xbrowser.load_url(self.post.url)
        d_iframe_src = self.xbrowser.execute_jsfun('_XPS.findIframe', 'disqus')
        if not d_iframe_src:
            log.warn('No DisqusPostInteractions iframe')
            return ([], False)

        r = requests.get(d_iframe_src)
        self.tree = lxml.html.fromstring(r.content)
        # data_el = self.tree.xpath('//*[@id="disqus-forumData"]')[
        data_el = self.tree.xpath('//*[@id="disqus-threadData"]')[0]
        data = json.loads(data_el.text)

        post_times = [self._local_naive_dt_as_utc(t) for t in self.post.postinteractions_set.filter(
            if_commented=True).values_list('create_date', flat=True)]
        post_times = set(post_times)

        res = []
        for post in data['response'].get('posts', []):
            post_time = iso8601.parse_date(post['createdAt'], pytz.utc)

            if post_time in post_times:
                # Comment likely fetched before. Skip.
                continue

            pi = models.PostInteractions()

            author = post['author'].get('name') or post['author'].get('username')
            url = post['author'].get('url')
            if author:
                kwargs = {'firstname': author}
                if url:
                    kwargs['url'] = url
                followers = models.Follower.objects.filter(**kwargs)
                if followers.exists():
                    pi.follower = followers[0]
                else:
                    pi.follower = models.Follower.objects.create(**kwargs)

            pi.platform_id = self.post.platform_id
            pi.post = self.post
            pi.content = post['raw_message']
            pi.if_commented = True
            pi.create_date = post_time
            pi.save()
            res.append(pi)

        return (res, True)

    @classmethod
    def url_contains_iframe(cls, url):
        try:
            r = requests.get(url, timeout=10)
        except:
            log.exception('Timeout while retrieving page content')
            return False
        if 'disqus' in r.content:
            log.warn('"disqus" found text on page')
            return True
        return False

    @classmethod
    def _list_posts(cls, forum_name):
        # TODO: Unused. Delete?
        resp_json = cls._get('forums/listPosts.json', {'forum': forum_name}).json()
        return resp_json

    @classmethod
    def _get(cls, url_postfix, params=None):
        # TODO: Unused. Delete?
        if params is None:
            params = {}
        params['api_key'] = settings.DISQUS_API_KEY
        params['api_secret'] = settings.DISQUS_API_SECRET
        url = settings.DISQUS_URL_PREFIX + url_postfix
        log.debug('Fetching %s %s', url, params)
        resp = requests.get(url, params=params)
        log.debug('Resp content[:1000]: %s', resp.content[:1000])
        return resp


class FacebookPostInteractionsFetcher(PostInteractionsFetcher):
    comments_css_matcher = re.compile(r'class=[\'"][^\'"]*fb-comments[^\'"]*[\'"]', re.IGNORECASE)

    def fetch_interactions(self, max_pages=None):
        self.xbrowser.load_url(self.post.url)
        iframe_src = self.xbrowser.execute_jsfun('_XPS.findIframe', 'facebook.com/plugins/comments')
        if not iframe_src:
            log.warn('No FacebookPostInteractions iframe')
            return ([], False)

        post_times = [self._local_naive_dt_as_utc(t) for t in self.post.postinteractions_set.filter(
            if_commented=True).values_list('create_date', flat=True)]
        post_times = set(post_times)

        r = requests.get(iframe_src)
        self.tree = lxml.html.fromstring(r.content)
        posts = self.tree.xpath('//ul[contains(@class, "fbFeedbackPosts")]//li[contains(@class, "fbFeedbackPost")]')
        res = []
        for post in posts:
            timestamp = int(post.xpath('.//abbr/@data-utime')[0])
            post_time = datetime.fromtimestamp(timestamp, tz=pytz.UTC)

            if post_time in post_times:
                # Comment likely fetched before. Skip.
                continue

            content = post.xpath('.//div[@class="postText"]/text()')[0]
            follower_name = post.xpath('.//a[@class="profileName"]/text()')[0]
            follower_url = post.xpath('.//a[@class="profileName"]/@href')[0]

            pi = models.PostInteractions()
            follower, _ = models.Follower.objects.get_or_create(firstname=follower_name, url=follower_url)

            pi.platform_id = self.post.platform_id
            pi.post = self.post
            pi.content = content
            pi.follower = follower
            pi.if_commented = True
            pi.create_date = post_time
            pi.save()
            res.append(pi)

        return (res, True)

    @classmethod
    def url_contains_iframe(cls, url):
        try:
            r = requests.get(url, timeout=10)
        except:
            log.exception('Timeout while retrieving page content')
            return False

        if ('facebook.com/comments/' in r.content or
                'facebook.com/plugins/comments' in r.content or
                cls.comments_css_matcher.findall(r.content)):
            log.warn('Facebook comments widget found on the page')
            return True
        return False


class GPlusPostInteractionsFetcher(PostInteractionsFetcher):
    comments_css_matcher = re.compile(r'class=[\'"][^\'"]*cmt_iframe_holder[^\'"]*[\'"]', re.IGNORECASE)

    def fetch_interactions(self, max_pages=None):
        self.xbrowser.load_url(self.post.url)

        iframe_src = self.xbrowser.execute_jsfun('_XPS.findIframe', '/_/widget/render/comments')
        if not iframe_src:
            log.warn('No GPlusPostInteractions iframe')
            return ([], False)

        r = requests.get(iframe_src)
        self.tree = lxml.html.fromstring(r.content)

        comments_count_raw = self.tree.xpath('//div[@id="widget_bounds"]//div[@class="DJa"]/text()')[0]
        try:
            comments_count = int(comments_count_raw.split(' ')[0])
        except ValueError:
            # TODO: Having a text value in that field usually means we got the
            # "No comments" string in the respective language. Unfortunately we
            # sometimes get a value such as "One comment" or its equivalent in
            # the respective language e.g. "Um comentário"
            # We need to either get the raw comment count from somewhere else
            # or handle the most common strings.
            comments_count = 0

        self.post.ext_num_comments = comments_count
        self.post.save()

        # posts = self.tree.xpath('//div[@guidedhelpid="streamcontent"]/div/div')
        res = []
        # for post in posts:
        #     pi = debra.models.PostInteractions()

        #     pi.content = ''.join(post.xpath('.//div[@class="Ct"]/text()'))
        #     full_name = post.xpath('.//header/h3/a/span/text()')[0]
        #     gplus_url = 'https://plus.google.com/' + post.xpath('.//header/h3/a/@oid')[0]
        # this url will lead to the right page, but it might not be the one people usually see when they open it
        # eg https://plus.google.com/113322956792512411411 redirects to https://plus.google.com/+CatarinaLavos89/posts
        # may cause problems when normalizing urls for gplus accounts

        #     follower, _ = debra.models.Follower.objects.get_or_create(firstname=full_name, url=gplus_url)

        #     pi.platform_id = self.post.platform_id
        #     pi.post = self.post
        #     pi.follower = follower
        #     pi.if_commented = True
        # pi.create_date = datetime.today()       # pretty serious problem here
        #     pi.save()
        #     res.append(pi)
        return (res, True)

    @classmethod
    def url_contains_iframe(cls, url):
        try:
            r = requests.get(url, timeout=10)
        except:
            log.exception('Timeout while retrieving page content')
            return False
        if ('apis.google.com/u/0/_/widget/render/comments' in r.content or
                cls.comments_css_matcher.findall(r.content)):
            log.warn('GPlus comments widget found on the page')
            return True
        return False


def get_fetcher_by_key(key):
    if key == 'disqus':
        return DisqusPostInteractionsFetcher
    elif key == 'facebook':
        return FacebookPostInteractionsFetcher
    elif key == 'gplus':
        return GPlusPostInteractionsFetcher
    else:
        raise ValueError('Unknown widget type: {}'.format(key))


def fetch_for_platform(platform, post_list, force=False):
    """A more intelligent algoritm that fetches PostInteractions comments, but
    before spawning XBrowser it checks if disqus is available in the first post.
    """
    fetcher_class = get_fetcher_by_key(platform)
    if not post_list:
        return []
    if not force and not fetcher_class.url_contains_iframe(post_list[0].url):
        return []
    res = []
    for interactions, iframe_found in fetcher_class.fetch_for_posts(post_list):
        log.debug('Parsed %s comments: %r', platform, interactions)
        res += interactions
        if not iframe_found and len(interactions) == 0:
            log.warn('Incorrect iframe detection for %s', platform)
            return res
    return res


def fetch_for_posts(post_list):
    platforms = ('disqus', 'facebook', 'gplus')
    for platform in platforms:
        res = fetch_for_platform(platform, post_list)
        if res:
            return res
    return []
