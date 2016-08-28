"""
Fetchers for wordpress, tumblr and blogger
all with their own apis
"""
from urlparse import urlsplit
import logging
import datetime
import re
from django.template import Template, Context

import requests
import pytumblr
import iso8601

from . import fetcherbase
from requests.exceptions import SSLError
from xpathscraper import utils
from . import descriptionfetcher
from . import platformutils

from debra import models
from platformdatafetcher.activity_levels import recalculate_activity_level


log = logging.getLogger('platformdatafetcher.blogfetcher')


WORDPRESS_BASE_URL = 'https://public-api.wordpress.com/rest/v1'
WORDPRESS_POSTS_PER_PAGE = 20
WORDPRESS_REPLIES_PER_PAGE = 20


class WordpressFetcher(fetcherbase.Fetcher):
    name = 'Wordpress'

    def __init__(self, platform, policy):
        fetcherbase.Fetcher.__init__(self, platform, policy)

        if not self._ensure_has_validated_handle():
            log.error('Cannot get validated_handle for WordpressFetcher',
                      exc_info=1,
                      extra={'platform_id': platform.id,
                             'policy_name': policy.name
                             })
            raise fetcherbase.FetcherException('Cannot get validated_handle')

        self._fetch_description()

    def get_validated_handle(self):
        urls = [self.platform.url]
        added_www = utils.add_www(self.platform.url)
        if added_www:
            urls.append(added_www)
        removed_www = utils.remove_www(self.platform.url)
        if removed_www:
            urls.append(removed_www)
        log.info('get_validated_handle: urls to check: %r', urls)
        for u in urls:
            site = urlsplit(u).netloc
            if isinstance(site, unicode):
                site = site.encode('utf-8')
            api_url = '/sites/{site}'.format(site=site)
            resp = self._get(api_url)
            self.platform.inc_api_calls(resp.status_code)
            if resp.status_code not in (404, 500):
                if resp.json().get('error', '') != 'unauthorized':
                    validated_url = resp.json().get('URL')
                    if validated_url:
                        return utils.remove_protocol(validated_url)
        return None

    def _update_platform_details(self):
        url = '/sites/{site}'.format(site=self.platform.validated_handle)
        resp = self._get(url)
        self.platform.inc_api_calls(resp.status_code)

        if resp.status_code == 404:
            # Blog doesn't exist
            platformutils.set_url_not_found('wordpress_blog_doesnt_exist', self.platform)
            log.warning('Wordpress blog does not exist.',
                        exc_info=1,
                        extra={'platform_id': self.platform.id,
                               'url': url
                               })
            raise fetcherbase.FetcherException('Wordpress blog does not exist.')

        resp_json = resp.json()
        if 'description' in resp_json and self.platform.influencer.is_enabled_for_automated_edits():
            platformutils.record_field_change(
                'fill_from_wp_data',
                'description', self.platform.description, resp_json['description'],
                platform=self.platform)
            self.platform.description = resp_json['description']
        if 'post_count' in resp_json:
            self.platform.numposts = resp_json['post_count']
        if 'subscribers_count' in resp_json:
            self.platform.num_followers = resp_json['subscribers_count']
        self.platform.save()

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None, start_date=None, end_date=None):
        """Returns Posts list from dates from `start_date` to `end_date`
        (which must be datetime.datetime objects).
        """
        self._update_platform_details()

        url = '/sites/{site}/posts/'.format(site=self.platform.validated_handle)
        page = 1
        res = []
        if not max_pages:
            max_pages = 1000

        base_params = {}
        if start_date:
            base_params['after'] = start_date.isoformat()
        if end_date:
            base_params['before'] = end_date.isoformat()

        while self.policy.should_continue_fetching(self):
            params = base_params.copy()
            params.update({'page': page, 'number': WORDPRESS_POSTS_PER_PAGE})
            resp = self._get(url, params)
            self.platform.inc_api_calls(resp.status_code)
            resp_json = resp.json()
            posts_list = resp_json.get('posts', [])
            log.debug('Got %s posts', len(posts_list))
            for post_data in posts_list:
                post_q = models.Posts.objects.filter(url=post_data['URL'], platform=self.platform)
                post_exists = post_q.exists()
                if post_exists and not self.should_update_old_posts():
                    self._inc('posts_skipped')
                    log.debug('Skipping already saved posts with url %s' % post_data['URL'])
                    continue
                if post_exists and self.should_update_old_posts():
                    log.debug('Updating old post')
                    post = post_q[0]
                else:
                    log.debug('Creating new post')
                    post = models.Posts()
                post.influencer = self.platform.influencer
                post.show_on_search = self.platform.influencer.show_on_search
                post.platform = self.platform
                post.title = post_data['title']
                post.url = post_data['URL']
                post.content = post_data['content']
                post.create_date = iso8601.parse_date(post_data['date'])
                post.api_id = str(post_data['ID'])

                self.save_post(post)
                res.append(post)

                self.fetch_post_interactions_extra([post])
            want_more = len(posts_list) == WORDPRESS_POSTS_PER_PAGE
            if not want_more:
                log.debug('Not fetching more pages - current page not filled')
                break
            if page == max_pages:
                log.debug('max_pages reached')
                break
            page += 1
        return res

    def fetch_post_interactions(self, posts_list, max_pages=None):
        comments = self._fetch_comments(posts_list)
        likes = self._fetch_likes(posts_list)
        return comments + likes

    def _fetch_comments(self, posts_list):
        res = []
        for p in posts_list:
            url = '/sites/{site}/posts/{post_ID}/replies/'.format(site=self.platform.validated_handle,
                    post_ID=p.api_id)
            page = 1
            res = []
            while True:
                params = {'page': page, 'number': WORDPRESS_REPLIES_PER_PAGE}
                resp = self._get(url, params)
                self.platform.inc_api_calls(resp.status_code)
                resp_json = resp.json()

                saved_from_call = 0
                for comment_data in resp_json.get('comments', []):
                    follower = self._get_follower(comment_data['author']['name'],
                            comment_data['author']['URL'])
                    pi = models.PostInteractions()
                    pi.platform_id = p.platform_id
                    pi.post = p
                    pi.follower = follower
                    pi.create_date = iso8601.parse_date(comment_data['date'])
                    pi.content = comment_data['content']
                    pi.if_liked = False
                    pi.if_shared = False
                    pi.if_commented = True
                    self._save_pi(pi, res)
                    saved_from_call += 1
                want_more = saved_from_call == WORDPRESS_REPLIES_PER_PAGE
                if not want_more:
                    log.debug('Not fetching more comment pages - current page not filled')
                    break
                page += 1
        return res

    def _fetch_likes(self, posts_list):
        res = []
        for p in posts_list:
            url = '/sites/{site}/posts/{post_ID}/likes/'.format(site=self.platform.validated_handle,
                    post_ID=p.api_id)
            resp = self._get(url)
            self.platform.inc_api_calls(resp.status_code)
            resp_json = resp.json()
            for like in resp_json.get('likes', []):
                follower = self._get_follower(like['name'], like['URL'])
                pi = models.PostInteractions()
                pi.platform_id = p.platform_id
                pi.post = p
                pi.follower = follower
                # Copy date from post, api doesn't return anything
                # but the field is not nullable.
                pi.create_date = p.create_date
                pi.if_liked = True
                pi.if_shared = False
                pi.if_commented = False
                self._save_pi(pi, res)
        return res

    @classmethod
    def _get(cls, url_postfix, params=None):
        assert url_postfix.startswith('/')
        url = WORDPRESS_BASE_URL + url_postfix
        if params is None:
            params = {}
        log.debug('Fetching from url %s %s', url, params)
        resp = requests.get(url, params=params)
        log.debug('Resp content[:1000]: %s', resp.content[:1000])
        return resp

    @classmethod
    def belongs_to_site(cls, url, _platform=None):
        #if urlsplit(url).netloc.lower().endswith('wordpress.com'):
        #    return url
        log.debug('Trying API call to check if URL belongs to Wordpress.com')
        for u in [url, utils.add_www(url)]:
            if u:
                site = urlsplit(u).netloc
                if isinstance(site, unicode):
                    site = site.encode('utf-8')
                api_url = '/sites/{site}'.format(site=site)
                resp = cls._get(api_url)
                if _platform:
                    _platform.inc_api_calls(resp.status_code)
                if resp.status_code not in (404, 500):
                    if resp.json().get('error', '') != 'unauthorized':
                        return u
        return None


# Fill this with: ('<consumer_key>',
#    '<consumer_secret>',
#    '<oauth_token>',
#    '<oauth_secret>')
PYTUMBLR_CLIENT_ARGS = (
    'ENb8pFwBUq6BoG6lMfMnsh5qwAbJRw9OpiVP1hO5S4ilfykGfA',
    'Nqn7b53AUbt8wu4m0P10Yvuvc6t7UXSANS1qdgsnbRILUY96FW',
)


class TumblrFetcher(fetcherbase.Fetcher):

    name = 'Tumblr'

    @classmethod
    def _create_client(cls):
        return pytumblr.TumblrRestClient(*PYTUMBLR_CLIENT_ARGS)

    def __init__(self, platform, policy):
        fetcherbase.Fetcher.__init__(self, platform, policy)
        self.client = self._create_client()

        if not self._ensure_has_validated_handle():
            log.error('Cannot get validated_handle for TumblrFetcher',
                      exc_info=1,
                      extra={'platform_id': platform.id,
                             'policy_name': policy.name
                             })
            raise fetcherbase.FetcherException('Cannot get validated_handle')

        self._update_platform_details()

    def get_validated_handle(self):
        if self.platform.url.startswith('http'):
            site = urlsplit(self.platform.url).netloc
        else:
            site = self.platform.url.rstrip('/').lstrip('/')
        info = self.client.blog_info(site)
        log.info('get_validated_handle info: %s', info)
        self.platform.inc_api_calls()
        if info.get('meta') and info['meta'].get('status') == 404:
            return None
        if not info.get('blog'):
            return None
        return info['blog'].get('name')

    def _update_platform_details(self):
        info = self.client.blog_info(self.platform.validated_handle)
        self.platform.inc_api_calls()
        if info.get('meta') and info['meta'].get('status') == 404:
            log.info('Tumblr blog no longer exists')
            platformutils.set_url_not_found('tumblr_blog_no_longer_exists', self.platform)
            log.warning('Tumblr blog does not exist.',
                        exc_info=1,
                        extra={'platform_id': self.platform.id,
                               })
            raise fetcherbase.FetcherException('Blog no longer exists')
        if self.platform.influencer.is_enabled_for_automated_edits():
            platformutils.record_field_change('fill_from_tumblr_data',
                'description', self.platform.description, info['blog']['description'],
                platform=self.platform)
            self.platform.description = info['blog']['description']
            platformutils.record_field_change('fill_from_tumblr_data',
                'blogname', self.platform.blogname, info['blog']['title'],
                platform=self.platform)
            self.platform.blogname = info['blog']['title']
        self.platform.numposts = info['blog']['posts']
        self.platform.total_numlikes = info['blog'].get('likes', 0)

        # !!! followers method requires oauth authorization
        #followers = self.client.followers(self.platform.validated_handle)
        #log.info('tumblr followers:\n%s', pformat(followers))
        #self.platform.inc_api_calls()
        #self.platform.num_followers = followers['total_users']

        self.platform.save()

    _POSTS_PER_PAGE = 3

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        if max_pages is None:
            max_pages = 1000
        page_no = 0
        res = []
        base_params = {'limit': self._POSTS_PER_PAGE}
        offset = 0

        while self.policy.should_continue_fetching(self):
            params = dict(base_params, offset=offset)
            log.info('Getting tumblr posts with params: %s', params)
            data = self.client.posts(self.platform.validated_handle, **params)
            for post_data in data.get('posts', []):
                url = post_data['post_url']
                existing_posts = list(models.Posts.objects.filter(url=url, platform=self.platform))
                if existing_posts:
                    if not self.should_update_old_posts():
                        self._inc('posts_skipped')
                        log.debug('Skipping already saved post with url %r', url)
                        continue
                    else:
                        post = existing_posts[0]
                        log.debug('Updating existing post with url: %r', url)
                else:
                    post = models.Posts()

                post.influencer = self.platform.influencer
                post.show_on_search = self.platform.influencer.show_on_search
                post.platform = self.platform
                self.read_post_data(post, post_data)

                self.save_post(post)
                res.append(post)

                self.fetch_post_interactions_extra([post])
            offset += self._POSTS_PER_PAGE
            page_no += 1
            if page_no >= max_pages:
                log.warn('max_pages reached')
                break
        return res

    @classmethod
    def read_post_data(cls, post, api_data):
        post.title = api_data.get('title', '')
        post.url = api_data['post_url']
        #post.content = api_data.get('body', api_data.get('caption', ''))
        post.content = cls.get_post_content(api_data)
        post.create_date = datetime.datetime.utcfromtimestamp(api_data['timestamp'])
        post.api_id = str(api_data['id'])

        return post

    content_template = Template('''
{% for item in items %}
<div>
    {% if item.url %}
        <img src="{{item.url|safe}}">
    {% endif %}
    {% if item.text %}
        <p>{{item.text|safe}}</p>
    {% endif %}
</div>
{% endfor %}
''')

    @classmethod
    def get_post_content(cls, api_data):
        if 'body' in api_data:
            return api_data['body']

        items = []

        if 'photos' in api_data:
            for photo in api_data['photos']:
                photo_caption = photo.get('caption', '')
                photo_url = photo.get('original_size', {}).get('url')
                if photo_url:
                    items.append(dict(url=photo_url, text=photo_caption))

        if 'caption' in api_data:
            items.append(dict(url=None, text=api_data['caption']))

        return cls.content_template.render(Context(dict(items=items)))

    def fetch_post_interactions(self, posts, max_pages=None):
        res = []
        for post in posts:
            post_data = self.client.posts(self.platform.validated_handle,
                                          id=post.api_id,
                                          notes_info='true')
            self.platform.inc_api_calls()
            if post_data.get('meta') and post_data.get('meta').get('status') == 404:
                log.warn('Post does not exist: %r', post.api_id)
                continue
            for note_data in post_data['posts'][0].get('notes', []):
                if note_data['type'] != 'like':
                    continue
                follower = self._get_follower(note_data['blog_name'], note_data['blog_url'])
                pi = models.PostInteractions()
                pi.platform_id = post.platform_id
                pi.post = post
                pi.follower = follower
                pi.create_date = datetime.datetime.fromtimestamp(int(note_data['timestamp']))
                pi.if_liked = True
                pi.if_shared = False
                pi.if_commented = False
                self._save_pi(pi, res)
        return res

    def fetch_platform_followers(self, max_pages=5):
        return []

    @classmethod
    def belongs_to_site(cls, url, _platform=None):
        client = cls._create_client()
        log.debug('Trying API call to check if URL belongs to Tumblr')
        site = urlsplit(url).netloc
        if isinstance(site, unicode):
            site = site.encode('utf-8')
        resp = client.blog_info(site)
        if _platform:
            _platform.inc_api_calls()
        if resp.get('meta') and resp['meta'].get('status') == 404:
            return None
        return url


BLOGGER_BASE_URL = 'https://www.googleapis.com/blogger/v3'
BLOGGER_KEYS = ['AIzaSyAVu_qvw9SuvUxo9CdrxKWLEVk24RWIKos', 'AIzaSyA9wVIwr4M5B5nnaXnoY_mZNIl2ZmW1jXg']
BLOGGER_WAIT_AFTER_LIMIT_EXCEEDED = 60


class BloggerFetcherREST(fetcherbase.Fetcher):
    """Raises requests.exceptions.HTTPError for API limit errors.
    """

    name = 'Blogspot'

    def __init__(self, platform, policy):
        fetcherbase.Fetcher.__init__(self, platform, policy)
        assert platform.influencer is not None
        platform_url = platform.url

        self.api_key = self.policy.get_api_data_value(self.name, 'api_key')

        r = self._get(self.api_key, '/blogs/byurl', {'url': platform_url})
        resp = r.json()
        self.platform.inc_api_calls(r.status_code)
        if 'id' not in resp:
            if '://www' not in platform_url:
                platform_url = platform_url.replace('://', '://www.')
            r = self._get(self.api_key, '/blogs/byurl', {'url': platform_url})
            self.platform.inc_api_calls(r.status_code)
            resp = r.json()
            # do this only if we have failed 3 times in the last week
            if 'id' not in resp and self.platform.get_failed_recent_fetches() > 3:
                platformutils.set_url_not_found('no_info_about_blog', self.platform)
                #platformutils.record_field_change('no_info_about_blog', 'url_not_found', self.platform.url_not_found, True, platform=self.platform)
                #self.platform.url_not_found = True
                #self.platform.save()

                log.error('Cannot fetch information for BloggerFetcherREST',
                          exc_info=1,
                          extra={'platform_id': platform.id,
                                 'policy_name': policy.name,
                                 'url': platform.url
                                 })

                raise fetcherbase.FetcherException('Cannot fetch information about url %s' % platform.url)
        if 'published' in resp.keys():
            platform.create_date = iso8601.parse_date(resp['published'])
        if 'description' in resp.keys() and self.platform.influencer.is_enabled_for_automated_edits():
            platformutils.record_field_change('fill_from_blogger_data',
                'description', self.platform.description, resp['description'],
                platform=self.platform)
            platform.description = resp['description']
        if 'posts' in resp.keys():
            platform.numposts = resp['posts']['totalItems']
        if 'pages' in resp.keys():
            self.num_pages = resp['pages']['totalItems']
        if 'name' in resp.keys() and self.platform.influencer.is_enabled_for_automated_edits():
            platformutils.record_field_change('fill_from_blogger_data',
                'blogname', self.platform.blogname, resp['name'],
                platform=self.platform)
            platform.blogname = resp['name']
        platform.save()
        self.blog_id = resp['id']

        if self.platform.influencer.is_enabled_for_automated_edits():
            self._fetch_description()
            self._fetch_description_from_pages()

    def _fetch_description_from_pages(self):
        r = self._get(self.api_key, '/blogs/{blogId}/pages'.format(blogId=self.blog_id))
        self.platform.inc_api_calls(r.status_code)
        pages = r.json().get('items', [])
        if not pages:
            log.warn('No pages to look for a description')
            return
        desc_page = descriptionfetcher.select_description_page(pages)
        desc = desc_page['title'] + ' ' + desc_page['content']
        log.info('Setting description: %r', desc)
        platformutils.record_field_change('fill_from_blogger_data',
            'description', self.platform.description, desc,
            platform=self.platform)
        self.platform.description = desc
        self.platform.save()

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None, start_date=None, end_date=None):
        """Returns list of models.Posts, from days from
        `start_date` to `end_data` (inclusive) specified as datetime.datetime
        objects in UTC timezone, fetching no more than `max_pages`.
        """
        url = '/blogs/{blogId}/posts'.format(blogId=self.blog_id)

        base_params = {}
        if start_date:
            base_params['startDate'] = utils.to_iso3339_string(start_date)
        if end_date:
            base_params['endDate'] = utils.to_iso3339_string(end_date)

        page_no = 0
        next_page_token = None
        res = []
        if not max_pages:
            print "Ok, max_pages is %s, so setting it to %s " % (max_pages, 1000)
            max_pages = 1000

        while self.policy.should_continue_fetching(self):
            if page_no == max_pages:
                log.debug('max_pages reached')
                break
            params = base_params.copy()
            if next_page_token:
                params['pageToken'] = next_page_token

            resp = self._get(self.api_key, url, params)
            self.platform.inc_api_calls(resp.status_code)
            resp_json = resp.json()
            for post_data in resp_json.get('items', []):
                post_q = models.Posts.objects.filter(url=post_data['url'], platform=self.platform)
                post_exists = post_q.exists()
                if post_exists and not self.should_update_old_posts():
                    self._inc('posts_skipped')
                    log.debug('Skipping already saved posts with url %s' % post_data['url'])
                    continue
                if post_exists and self.should_update_old_posts():
                    log.debug('Updating old post')
                    post = post_q[0]
                else:
                    log.debug('Creating new post')
                    post = models.Posts()
                post.influencer = self.platform.influencer
                post.show_on_search = self.platform.influencer.show_on_search
                post.platform = self.platform
                post.title = post_data['title']
                post.url = post_data['url']
                post.content = post_data['content']
                post.create_date = iso8601.parse_date(post_data['published'])
                if 'location' in post_data and 'name' in post_data['location']:
                    post.location = post_data['location']['name']
                post.api_id = str(post_data['id'])

                self.save_post(post)
                res.append(post)

                self.fetch_post_interactions_extra([post])
            page_no += 1
            next_page_token = resp_json.get('nextPageToken')
            if not next_page_token:
                break
        return res

    def fetch_post_interactions(self, posts_list, max_pages=None):
        """Returns list of models.PostInteractions, based on a post list
        previously returned by fetch_posts().
        """
        res = []
        for p in posts_list:
            url = '/blogs/{blogId}/posts/{postId}/comments'.format(blogId=self.blog_id,
                    postId=p.api_id)
            next_page_token = None
            res = []
            while True:
                params = {}
                if next_page_token:
                    params['pageToken'] = next_page_token

                resp = self._get(self.api_key, url, params)
                self.platform.inc_api_calls(resp.status_code)
                resp_json = resp.json()
                if next_page_token and resp_json.get('nextPageToken') == next_page_token:
                    break

                for comment_data in resp_json.get('items', []):
                    follower = self._get_follower(comment_data['author']['displayName'],
                            comment_data['author'].get('url'))
                    pi = models.PostInteractions()
                    pi.platform_id = p.platform_id
                    pi.post = p
                    pi.follower = follower
                    pi.create_date = iso8601.parse_date(comment_data['published'])
                    pi.content = comment_data['content']
                    pi.if_liked = False
                    pi.if_shared = False
                    pi.if_commented = True
                    self._save_pi(pi, res)
                next_page_token = resp_json.get('nextPageToken')
                if not next_page_token:
                    break
        return res

    @classmethod
    def _get(cls, api_key, url_postfix, params=None, retries=1):
        return fetcherbase.retry_when_call_limit(lambda: cls._do_get(api_key, url_postfix, params),
                                                 retries)

    @classmethod
    def _do_get(cls, api_key, url_postfix, params):
        assert url_postfix.startswith('/')
        url = BLOGGER_BASE_URL + url_postfix
        if params is None:
            params = {}
        params['key'] = api_key
        log.debug('Fetching from url %s %s', url, params)
        try:
            resp = requests.get(url, params=params)
        except SSLError:
            resp = requests.get(url, params=params, verify=False)
        if resp.status_code == 403:
            # API call limit exceeded
            raise fetcherbase.FetcherCallLimitException('Blogger call limit', None,
                    BLOGGER_WAIT_AFTER_LIMIT_EXCEEDED)
        log.debug('Resp content[:1000]: %s', resp.content[:1000])
        return resp

    @classmethod
    def belongs_to_site(cls, url):
        netloc = urlsplit(url).netloc.lower()
        if re.match(r'.*\.blogspot\.[a-z.]{2,7}$', netloc):
            return url
        log.debug('Trying API call to check if URL belongs to blogspot.com')
        for u in [url, utils.add_www(url)]:
            if u:
                u = u.lower()
                resp = cls._get(BLOGGER_KEYS[1], '/blogs/byurl', {'url': u}, retries=0)
                if resp.status_code not in (404, 500):
                    if urlsplit(u).netloc.lower().endswith('youtube.com'):
                        return ('Youtube', u)
                    return u
        return None
