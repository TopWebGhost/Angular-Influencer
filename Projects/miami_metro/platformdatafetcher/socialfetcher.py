"""

Fetchers for Twitter (Twitter API), Instagram (instagram api client and requests),
Facebook (facebook api with requests) and Pinterest (XBrowser)
InstagramScrapingFetcher apparently overlaps with the one in scrapingfetcher.py

Save posts and different kinds of stats like number of followers and so on

"""
# import urlparse
import datetime
import json
import logging
import re
import time
from urlparse import urlparse

import iso8601
import lxml.html
import parsedatetime
import requests
import twitter
from dateutil import parser
from django.conf import settings
from instagram import InstagramAPIError
from instagram.client import InstagramAPI

from debra import models
from masuka import image_manipulator
from platformdatafetcher import fetcherbase, platformutils
from platformdatafetcher.activity_levels import recalculate_activity_level
from platformdatafetcher.pinterest_api import BasicPinterestFetcher
from platformdatafetcher.platformextractor import open_url
from xpathscraper import textutils, utils, xbrowser
from . import google_plus

log = logging.getLogger('platformdatafetcher.socialfetcher')


class SocialPlatformFetcher(fetcherbase.Fetcher):
    @property
    def influencer(self):
        return self.platform.influencer

    def _update_detected_name(self, name):
        if not name:
            return

        self.platform.detected_name = name
        self.platform.influencer_attributes['name'] = name

    def _update_detected_description(self, description):
        if not description:
            return

        self.platform.description = description
        self.platform.influencer_attributes['description'] = description

    def _update_detected_about(self, about_text):
        if not about_text:
            return

        self.platform.about = about_text
        self.platform.influencer_attributes['about'] = about_text

    def _update_detected_location(self, location):
        if not location:
            return

        self.platform.detected_demographics_location = location
        self.platform.influencer_attributes['location'] = location

    def _update_detected_blogname(self, blogname):
        if not blogname:
            return

        self.platform.blogname = blogname
        self.platform.influencer_attributes['blogname'] = blogname


class TwitterFetcher(SocialPlatformFetcher):
    name = 'Twitter'
    influencer_update_operation = 'fill_from_tw_data'

    def __init__(self, platform, policy):
        super(TwitterFetcher, self).__init__(platform, policy)

        self.t = self._create_twitter()

        if not self._ensure_has_validated_handle():
            raise fetcherbase.FetcherException('Cannot get validated_handle')

        try:
            fetcherbase.retry_when_call_limit(self._update_platform)
        except twitter.TwitterHTTPError as exc:
            log.exception('Twitter exception during initialization')
            if json.loads(exc.response_data)['errors'][0]['code'] == 34 and self.platform.get_failed_recent_fetches() > 3:
                log.error('Invalid platform url')
                platformutils.set_url_not_found('invalid_twitter_url', self.platform)
                #platformutils.record_field_change('invalid_twitter_url', 'url_not_found',
                #                                  self.platform.url_not_found, True, platform=self.platform)
                #self.platform.url_not_found = True
                #self.platform.save()

            raise fetcherbase.FetcherException('Twitter initialization')
        else:
            platformutils.unset_url_not_found('existing_twitter_handle', self.platform)
            #platformutils.record_field_change(
            #    'existing_twitter_handle', 'url_not_found', self.platform.url_not_found, False, platform=self.platform)
            #self.platform.url_not_found = False
            #self.platform.save()

    def get_validated_handle(self):
        screen_name = platformutils.username_from_platform_url(self.platform.url)
        if not screen_name:
            return None
        if screen_name in settings.TWITTER_INVALID_SCREEN_NAMES:
            return None
        try:
            userdata = self.t.users.show(screen_name=screen_name)
        except twitter.TwitterHTTPError as exc:
            self._raise_for_call_limit(exc)
            self.platform.inc_api_calls(None, 'error')
            raise
        validated_handle = userdata.get('screen_name')
        if not validated_handle:
            return None
        return validated_handle.lower()

    @staticmethod
    def _create_twitter():
        return twitter.Twitter(auth=twitter.OAuth(
            settings.TWITTER_OAUTH_TOKEN,
            settings.TWITTER_OAUTH_SECRET,
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET))

    def _raise_for_call_limit(self, exc):
        if isinstance(exc, twitter.TwitterHTTPError) and exc.e.code == 429:
            self.platform.inc_api_calls(None, 'rate limit')
            limit_ts = float(exc.e.headers.get('x-rate-limit-reset', '0'))
            to_wait = max(1, int(limit_ts - time.time()))
            raise fetcherbase.FetcherCallLimitException('Twitter call limit', exc, to_wait)

    def _update_platform(self):
        try:
            userdata = self.t.users.show(screen_name=self.platform.validated_handle)
            self.platform.inc_api_calls()
        except twitter.TwitterHTTPError as exc:
            self._raise_for_call_limit(exc)
            self.platform.inc_api_calls(None, 'error')
            raise
        self.platform.num_followers = userdata['followers_count']
        self.platform.num_following = userdata['friends_count']
        self.platform.numposts = userdata['statuses_count']
        self._update_popularity_timeseries()

        img_url = userdata.get('profile_image_url')
        # Select default, biggest image
        if img_url and '_normal' in img_url:
            img_url = img_url.replace('_normal', '')
        self.platform.profile_img_url = img_url

        self.platform.cover_img_url = userdata.get('profile_background_image_url')
        if userdata.get('profile_background_image_url') or userdata.get('profile_image_url'):
            image_manipulator.save_social_images_to_s3(self.platform)

        self._update_detected_name(userdata.get('name'))

        detected_description = userdata.get('description', '')
        try:
            description_url = userdata['entities']['url']['urls'][0]['expanded_url']
            log.info('URL from description: %r', description_url)
        except (KeyError, IndexError):
            log.warn('No URL in description')
            description_url = None
        if description_url:
            detected_description += ' ' + description_url

        self._update_detected_description(detected_description)
        self._update_detected_location(userdata.get('location'))

        self.platform.save()

    def _fetch_user_timeline(self, **params):
        data = None
        try:
            data = self.t.statuses.user_timeline(**params)
            self.platform.inc_api_calls()
        except twitter.TwitterHTTPError as exc:
            self.platform.inc_api_calls(None, 'error')
            self._raise_for_call_limit(exc)
            raise
        return data

    @recalculate_activity_level
    def fetch_posts(self, max_pages=5):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        page_no = 1
        res = []
        base_params = dict(screen_name=self.platform.validated_handle)
        max_id = None

        while self.policy.should_continue_fetching(self):
            if page_no > max_pages:
                break
            params = base_params.copy()
            if max_id is not None:
                params['max_id'] = max_id
            data = fetcherbase.retry_when_call_limit(lambda: self._fetch_user_timeline(**params))
            if not data:
                break
            for d in data:
                url = settings.TWITTER_TWEET_URL_TEMPLATE.format(screen_name=self.platform.validated_handle,
                                                        id=d['id'])
                existing_posts = list(models.Posts.objects.filter(url=url, platform=self.platform))
                if existing_posts:
                    post = existing_posts[0]
                    post.post_image = utils.nestedget(d, 'entities', 'media', 0, 'media_url')
                    post.save()
                    self._inc('posts_skipped')
                    log.debug('Skipping already saved tweet with url %s', url)
                elif d.get('retweeted_status'):
                    self._inc('posts_skipped')
                    log.debug('Skipping retweet %s', url)
                else:
                    post = models.Posts()
                    post.platform = self.platform
                    post.platform_name = 'Twitter'
                    post.influencer = self.influencer
                    post.show_on_search = self.influencer.show_on_search
                    post.url = url
                    post.location = d.get('location')
                    post.content = d['text']
                    post.create_date = datetime.datetime.strptime(d['created_at'],
                                                                '%a %b %d %H:%M:%S +0000 %Y')
                    post.engagement_media_numlikes = d['favorite_count']
                    post.engagement_media_numshares = d['retweet_count']
                    post.engagement_media_numretweets = d['retweet_count']
                    post.post_image = utils.nestedget(d, 'entities', 'media', 0, 'media_url')

                    self.save_post(post)
                    res.append(post)

            max_id = min(d['id'] for d in data)
            page_no += 1
        return res

    def fetch_post_interactions(self, posts_list):

        return []

    FOL_DESC_KEYWORDS = ['blog', 'fashion', 'style', 'styling', 'shoes', 'women', 'beauty', 'youtube', 'vlogger']

    def _is_follower_worth_inserting(self, udata):
        if not udata.get('url'):
            return False
        print 'url: %s' % udata.get('url')
        print 'description: %s' % udata.get('description')
        if not any(kw in udata.get('description', '').lower() for kw in self.FOL_DESC_KEYWORDS):
            return False
        return True

    def fetch_platform_followers(self, max_pages=200, follower=True):
        cursor = -1
        page_no = 0
        follower_ids = []
        while True:
            if follower:
                data = fetcherbase.retry_when_call_limit(
                    lambda: self.t.followers.ids(screen_name=self.platform.validated_handle,
                                                 count=5000, cursor=cursor)
                )
            else:
                data = fetcherbase.retry_when_call_limit(
                    lambda: self.t.friends.ids(screen_name=self.platform.validated_handle,
                                               count=5000, cursor=cursor)
                )
            self.platform.inc_api_calls()
            follower_ids += data['ids']
            page_no += 1
            if page_no >= max_pages:
                log.warn('max_pages reached for fetch_platform_followers, did not fetch user data')
                return []
            if cursor in (0, -1):
                log.info('Exhausted followers/ids cursor')
                break
        log.info('Got %s follower ids', len(follower_ids))

        res = []
        for ids_group in utils.chunks(follower_ids, 100):
            ids_param = ','.join(str(id) for id in ids_group)
            data = fetcherbase.retry_when_call_limit(
                lambda: self.t.users.lookup(user_id=ids_param))
            self.platform.inc_api_calls()
            for udata in data:
                if not self._is_follower_worth_inserting(udata):
                    log.warn('Not worth inserting: %s', udata['screen_name'])
                    continue
                log.info('Worth inserting: %s', udata['screen_name'])

                platform_url = settings.TWITTER_USER_URL_TEMPLATE.format(screen_name=udata['screen_name'])
                follower_kwargs = {
                    'firstname': udata['name'],
                    'url': udata.get('url'),
                }
                influencer_search_kwargs = {
                    'tw_url': udata['url'],
                }
                influencer_create_kwargs = {
                    'name': udata['name'],
                    'demographics_location': udata.get('location'),
                    'tw_url': platform_url,
                }
                desc = udata.get('url') + ' ' + udata.get('description', '')
                pl_fol = fetcherbase.create_platform_follower(follower_kwargs, follower_kwargs,
                                                              influencer_search_kwargs, influencer_create_kwargs,
                                                              platform_url, 'Twitter', desc)
                res.append(pl_fol)

            page_no += 1
            if page_no >= max_pages:
                log.warn('max_pages reached')
                break
        return res

    # @classmethod
    # def get_description(cls, url, xb=None):
    #     try:
    #         screen_name = platformutils.username_from_platform_url(url)
    #         t = cls._create_twitter()
    #         userdata = t.users.show(screen_name=screen_name)
    #
    #         description = userdata.get('description')
    #
    #         description_url = None
    #         try:
    #             description_url = userdata['entities']['url']['urls'][0]['expanded_url']
    #         except (KeyError, IndexError):
    #             pass
    #
    #         return (description or '') + ' ' + (description_url or '')
    #
    #     except twitter.TwitterHTTPError:
    #         return None

    @classmethod
    def get_description(cls, url, xb=None):
        from lxml.html import fromstring

        response = open_url(url)
        if not response:
            return
        ps = response.read()
        page = fromstring(ps)

        description_blocks = []

        description = ''.join(page.xpath(
            "//p[@class='ProfileHeaderCard-bio u-dir']"
            "/descendant-or-self::*/text()"
        ))
        if description:
            description_blocks.append(description)

        # Twitter profile description can also have urls: they won't be found
        # using text() above
        desc_urls = page.xpath(
            "//p[@class='ProfileHeaderCard-bio u-dir']/a/@href"
        )
        desc_urls = map(
            lambda u: 'https://twitter.com{}'.format(
                u
            ) if u.startswith('/') else u,
            desc_urls
        )
        description_blocks.extend(desc_urls)

        desc_url_nodes = page.xpath(
            "//div[@class='ProfileHeaderCard']"
            "//span[@class='ProfileHeaderCard-urlText u-dir']"
            "/a[@class='u-textUserColor']"
            "/@title"
        )
        if desc_url_nodes:
            description_blocks.append(desc_url_nodes[0])

        return ' '.join(description_blocks)

    @classmethod
    def static_fetch_post_interactions(cls, posts_list):
        print("Fetching interactions for %d posts " % len(posts_list))
        import requests
        for p in posts_list:
            r = requests.get(p.url, headers=utils.browser_headers())
            import lxml.html
            try:
                tree = lxml.html.fromstring(r.content)
                retweet_btn = tree.xpath('//div[contains(@class, "js-tweet-stats-container")]//a[@class="request-retweeted-popup"]/strong')
                if retweet_btn and len(retweet_btn) > 0:
                    retweet_btn = retweet_btn[0]
                    retweet_cnt_txt = retweet_btn.text
                    print("Got retweet count text: %s" % retweet_cnt_txt)
                    retweet_cnt = int(retweet_cnt_txt)
                    print("Got retwee integer value: %d" % retweet_cnt)
                    p.engagement_media_numretweets = retweet_cnt
                    p.save()
                likes_btn = tree.xpath('//div[contains(@class, "js-tweet-stats-container")]//a[@class="request-favorited-popup"]/strong')
                if likes_btn and len(likes_btn) > 0:
                    likes_btn = likes_btn[0]
                    likes_cnt_txt = likes_btn.text
                    print("Got likes count text: %s" % likes_cnt_txt)
                    likes_cnt = int(likes_cnt_txt)
                    print("Got likes integer value: %d" % likes_cnt)
                    p.engagement_media_numlikes = likes_cnt
                    p.save()
            except:
                print("problem with %r" % p.url)
                pass

class InstagramFetcher(SocialPlatformFetcher):
    """
    XXXXXXXXXXXXXXXXXX ===== WE DON'T USE THIS ANYMORE ====== XXXXXXXXXXXXXXXXXX
    """
    name = 'Instagram'
    influencer_update_operation = 'fill_from_instagram_data'

    def __init__(self, platform, policy):
        super(InstagramFetcher, self).__init__(platform, policy)

        self.instagram = self._create_instagram()

        if not self._ensure_has_validated_handle():
            raise fetcherbase.FetcherException('Cannot get validated_handle')

        fetcherbase.retry_when_call_limit(self._update_platform)

    @staticmethod
    def _create_instagram():
        return InstagramAPI(client_id=settings.INSTAGRAM_CLIENT_ID,
                            client_secret=settings.INSTAGRAM_CLIENT_SECRET)

    def _raise_for_call_limit(self, exc):
        if isinstance(exc, InstagramAPIError) and exc.error_type == 'Rate limited':
            self.platform.inc_api_calls(None, 'rate limit')
            raise fetcherbase.FetcherCallLimitException('Instgram call limit', exc,
                                                        settings.INSTAGRAM_WAIT_AFTER_LIMIT_EXCEEDED)

    def get_validated_handle(self):
        user_name = platformutils.username_from_platform_url(self.platform.url)
        log.info('Instagram user name parsed from url: %s', user_name)
        try:
            users = self.instagram.user_search(q=user_name)
            self.platform.inc_api_calls()
        except InstagramAPIError as exc:
            self.platform.inc_api_calls(None, 'error')
            self._raise_for_call_limit(exc)
            raise
        log.info('Users from instagram search: %s', users)
        for user in users:
            if user.username.lower() == user_name.lower():
                log.info('Found user_id %s', user.id)
                return user.id
        log.error('No user_id found for instagram user %s', user_name)
        return None

    def _update_platform(self):
        try:
            userdata = self.instagram.user(user_id=self.platform.validated_handle)
            self.platform.inc_api_calls()
        except InstagramAPIError as exc:
            self.platform.inc_api_calls(None, 'error')
            self._raise_for_call_limit(exc)
            raise
        if hasattr(userdata, 'counts'):
            self.platform.num_followers = userdata.counts['followed_by']
            self.platform.num_following = userdata.counts['follows']
            self.platform.numposts = userdata.counts['media']
        if hasattr(userdata, 'profile_picture'):
            self.platform.profile_img_url = userdata.profile_picture

        self._update_detected_description(getattr(userdata, 'bio', None))

        self.platform.save()
        if self.platform.profile_img_url:
            image_manipulator.save_social_images_to_s3(self.platform)

    @recalculate_activity_level
    def fetch_posts(self, max_pages=20):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        return fetcherbase.retry_when_call_limit(lambda: self._do_fetch_posts(max_pages))

    @staticmethod
    def _content_from_media(instagram, m):
        content_parts = []
        if hasattr(m, 'caption') and hasattr(m.caption, 'text'):
            content_parts.append(m.caption.text)
        content_parts.append(m.images['standard_resolution'].url)
        content_parts = [p for p in content_parts if p and p.strip()]
        return ' '.join(content_parts)

    def _do_fetch_posts(self, max_pages=None):
        res = []
        page_no = 0
        max_id = None
        while self.policy.should_continue_fetching(self):
            log.info('Page=%s', page_no)
            kwargs = {'user_id': self.platform.validated_handle}
            if max_id is not None:
                kwargs['max_id'] = max_id
            try:
                media, next = self.instagram.user_recent_media(**kwargs)
                self.platform.inc_api_calls()
            except InstagramAPIError as exc:
                self.platform.inc_api_calls(None, 'error')
                self._raise_for_call_limit(exc)
                raise
            self._last_media = media
            if not media:
                log.warn('Empty page')
                break
            max_id = min(m.id for m in media)
            for m in media:
                if models.Posts.objects.filter(url=m.link, platform=self.platform).exists():
                    self._inc('posts_skipped')
                    log.debug('Skipping already saved instagram media with url %s', m.link)
                    continue
                post = models.Posts()
                post.api_id = m.id
                post.platform = self.platform
                post.platform_name = 'Instagram'
                post.influencer = self.influencer
                post.show_on_search = self.influencer.show_on_search
                post.url = m.link
                post.content = self._content_from_media(self.instagram, m)
                post.create_date = m.created_time
                if getattr(m, 'location', False):
                    post.location = m.location.name
                post.engagement_media_numlikes = m.like_count

                self.save_post(post)
                res.append(post)

                self.fetch_post_interactions([post])
            page_no += 1
            if max_pages is not None and page_no >= max_pages:
                log.warn('max_pages=%s reached', max_pages)
                break
        return res

    def _fetch_media(self, media_id):
        try:
            return self.instagram.media(media_id=media_id)
            self.platform.inc_api_calls()
        except InstagramAPIError as exc:
            self.platform.inc_api_calls(None, 'error')
            self._raise_for_call_limit(exc)
            raise

    def fetch_post_interactions(self, posts_list):
        res = []
        for p in posts_list:
            try:
                media = fetcherbase.retry_when_call_limit(lambda: self._fetch_media(p.api_id))
            except InstagramAPIError:
                log.exception('While fetching instagram media, skipping')
                continue
            comments = media.comments or []
            for c in comments:
                pi = models.PostInteractions()
                pi.follower = self._get_follower(c.user.full_name, None)
                pi.platform_id = p.platform_id
                pi.post = p
                pi.create_date = c.created_at
                pi.content = c.text or ''
                pi.if_commented = True
                self._save_pi(pi, res)
        return res

    @classmethod
    def get_description(cls, url, xb=None):
        user_name = platformutils.username_from_platform_url(url)
        try:
            user_id = None
            instagram = cls._create_instagram()
            users = instagram.user_search(q=user_name)
            for user in users:
                if user.username.lower() == user_name.lower():
                    log.info('Found user_id %s', user.id)
                    user_id = user.id
            if user_id is None:
                log.info('No user_id')
                return None
            userdata = instagram.user(user_id=user_id)
            desc = getattr(userdata, 'bio', '')
            desc += ' '
            desc += getattr(userdata, 'website', '')
            return desc
        except InstagramAPIError:
            log.exception('While get_description')
            return None


class InstagramScrapingFetcher(SocialPlatformFetcher):
    name = 'Instagram'
    influencer_update_operation = 'fill_from_instagram_data'

    def __init__(self, platform, policy):
        super(InstagramScrapingFetcher, self).__init__(platform, policy)

        self._data, status_code = self._fetch_data(platform.url, platform=platform)

        if status_code is None or status_code == 500:
            raise fetcherbase.FetcherException('Invalid response/timeout from Instagram server')

        if not self._ensure_has_validated_handle():
            raise fetcherbase.FetcherException('Cannot get validated_handle')

        if not self._data or not self._data.get('entry_data'):
            raise fetcherbase.FetcherException('Cannot get json data from Instagram web page')

        self._update_platform()

    @staticmethod
    def _fetch_data(url, platform=None):
        # HACK: Passing platform if available, so we can flag it as url_not_found, if request fails
        try:
            r = requests.get(url, timeout=20, headers=utils.browser_headers())
            log.info('http status code: %s', r.status_code)
            r.raise_for_status()
            g = re.search('_sharedData = (.*);</script>', r.text)
            if not g:
                return None, r.status_code
            return json.loads(g.group(1)), r.status_code
        # Atul: March 2 2016
        # This doesn't make sense that we are setting url_not_found if we have 3 such errors.
        # What if we called this for posts that are not available anymore? Influencers take down posts
        #except requests.RequestException as e:
        #    if platform and platform.get_failed_recent_fetches() > 3:
        #        platformutils.set_url_not_found('instagram_profile_doesnt_exist', platform)
        #    raise fetcherbase.FetcherException('Instagram url fetch failed for {}: {}.'.format(url, e))
        except:
            log.exception('While _fetch_data')
            return None, None

    def get_validated_handle(self):
        return utils.nestedget(self._data, 'entry_data', 'ProfilePage', 0, 'user', 'id')

    def _update_platform(self):
        #print(self._data)
        userdata = utils.nestedget(self._data, 'entry_data', 'ProfilePage', 0, 'user')

        if 'followed_by' in userdata:
            self.platform.num_followers = userdata['followed_by']['count']
            self.platform.num_following = userdata['follows']['count']
            self.platform.numposts = userdata['media']['count']
            self._update_popularity_timeseries()
        if 'profile_pic_url' in userdata:
            self.platform.profile_img_url = userdata['profile_pic_url']

        if 'biography' in userdata:
            self._update_detected_description(userdata['biography'])

        if 'full_name' in userdata:
            self._update_detected_name(userdata['full_name'])

        self.platform.save()
        if self.platform.profile_img_url:
            image_manipulator.save_social_images_to_s3(self.platform)

    @recalculate_activity_level
    def fetch_posts(self, max_pages=20, force_fetch=False):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        return fetcherbase.retry_when_call_limit(lambda: self._do_fetch_posts(max_pages, force_fetch))

    @staticmethod
    def _content_from_media(m):
        #print("------\n%s\n-----\n" % m)
        content_parts = []
        if m.get('caption'):
            if type(m['caption']) in [str, unicode]:
                content_parts.append(m['caption'])
            else:
                print("Caption is not a string, let's check it %r" % m['caption'])
        if m.get('display_src'):
            content_parts.append(m['display_src'])
        # if this is an instagram video, use the url for the video to display
        if m.get('type') == 'video' and m.get('videos') and m.get('videos').get('standard_resolution') and m.get('videos').get('standard_resolution').get('url'):
            content_parts.append(m['videos']['standard_resolution']['url'])
        elif m.get('images') and m.get('images').get('standard_resolution') and m.get('images').get('standard_resolution').get('url'):
            content_parts.append(m['images']['standard_resolution']['url'])
        content_parts = [p for p in content_parts if p and p.strip()]
        return ' '.join(content_parts)

    def _do_fetch_posts(self, max_pages=None, force_fetch=False):
        res = []
        page_no = 0
        max_id = None
        paging_url_tpl = 'http://instagram.com/{user_name}/media?max_id={max_id}'
        user_name = platformutils.username_from_platform_url(self.platform.url)

        while self.policy.should_continue_fetching(self) or force_fetch:
            log.info('Page=%s', page_no)
            if max_id is None:
                media = self._data['entry_data']['ProfilePage'][0]['user']['media']['nodes']
            else:
                r = requests.get(paging_url_tpl.format(user_name=user_name, max_id=max_id))
                r.raise_for_status()
                media = r.json()['items']
            if not media:
                log.warn('Empty page')
                break
            max_id = min(m['id'] for m in media)
            for m in media:
                #print("checking %s" % m)
                purl = 'http://instagram.com/p/' + m['code']
                posts = models.Posts.objects.filter(url=purl, platform=self.platform)
                post = None
                # 3 cases exist:
                # 1. post exists and has the same content => skip
                # 2. post exists but content has changed => update
                # 3. post doesnt' exist => create a new post
                if posts.exists():
                    post = posts[0]
                if post and post.content and post.content == self._content_from_media(m):
                    self._inc('posts_skipped')
                    log.debug('Skipping already saved instagram media with url %s', purl)
                    continue
                if not post:
                    post = models.Posts()
                    post.api_id = m['id']
                    post.platform = self.platform
                    post.platform_name = 'Instagram'
                    post.influencer = self.influencer
                    post.show_on_search = self.influencer.show_on_search
                    post.url = 'http://instagram.com/p/' + m['code']
                    log.debug('NEW POST created for instagram media with url %s', purl)
                else:
                    log.debug('Post already exists but content is modified instagram media with url %s', purl)
                post.content = self._content_from_media(m)
                ctime = m['date'] if m.get('date') else m['created_time']
                post.create_date = datetime.datetime.fromtimestamp(int(ctime))
                if m.get('location') and m['location'].get('name'):
                    post.location = m['location']['name']
                if m.get('likes'):
                    post.engagement_media_numlikes = m['likes']['count']
                if m.get('comments'):
                    post.engagement_media_numcomments = m['comments']['count']
                if m.get('type') == 'video' and m.get('video_views'):
                    post.impressions = int(m.get('video_views'))
                    print("*****GOT video views %d" % post.impressions)
                self.save_post(post)
                res.append(post)
                print("fetching interactions\n")
                self.fetch_post_interactions(_single_media=m, _single_post=post)
            page_no += 1
            if max_pages is not None and page_no >= max_pages:
                log.warn('max_pages=%s reached', max_pages)
                break
        return res

    def _fetch_media_for_post(self, post):
        data, status_code = self._fetch_data(post.url)
        if status_code and status_code == 200:
            return utils.nestedget(data, 'entry_data', 'PostPage', 0, 'media')
        else:
            return None

    def fetch_post_interactions(self, posts_list=None, _single_media=None, _single_post=None):
        if _single_media is not None and _single_post is not None:
            medias_posts = [(_single_media, _single_post)]
        else:
            assert posts_list is not None
            medias_posts = [(self._fetch_media_for_post(p), p) for p in posts_list]
            medias_posts = [(m, p) for (m, p) in medias_posts if m]
        res = []
        # log.info('medias_posts = %s' % medias_posts)
        for m, p in medias_posts:
            # log.info('m: %s' % m)
            comments = utils.nestedget(m, 'comments', 'nodes') or []
            post_author_id = utils.nestedget(m, 'owner', 'id') or None
            log.info('Author\'s id: %s' % post_author_id)
            log.info('Likes %r' % utils.nestedget(m, 'likes'))
            log.info('Likes count %r' % utils.nestedget(m, 'likes', 'count'))
            if utils.nestedget(m, 'likes'):
                p.engagement_media_numlikes = utils.nestedget(m, 'likes', 'count') or 0
            if utils.nestedget(m, 'comments'):
                p.engagement_media_numcomments = utils.nestedget(m, 'comments', 'count') or 0
            if utils.nestedget(m, 'video_views'):
                p.impressions = utils.nestedget(m, 'video_views')
                print "Got video views %r" % p.impressions
            p.save()
            # log.info('Comments: %s' % comments)

            for c in comments:
                log.info('Performing a comment: %s' % c)
                p_create_date = datetime.datetime.fromtimestamp(int(c['created_at']))
                p_content = c.get('text')
                comment_author_id = utils.nestedget(c, 'user', 'id') or None
                p_follower = self._get_follower("instagram_%s" % comment_author_id, None)

                pi_to_save = False  # flag whether to save the pi
                # checking for existing PostInteractions object with the same post, content and create_date
                existing_pis = p.postinteractions_set.filter(create_date=p_create_date,
                                                             content=p_content)
                if existing_pis.count() > 0:
                    # using existing
                    pi = existing_pis[0]
                    log.info('PostInteraction object for this post already exists, id=%s' % pi.id)
                    if pi.follower != p_follower:
                        pi.follower = p_follower
                        pi_to_save = True

                    if pi.platform_id != p.platform_id:
                        pi.platform_id = p.platform_id
                        pi_to_save = True

                else:
                    log.info('PostInteraction object for this post does not exist')
                    # creating new and saving it
                    pi_to_save = True
                    pi = models.PostInteractions()
                    pi.follower = p_follower
                    pi.platform_id = p.platform_id
                    pi.post = p
                    pi.create_date = p_create_date
                    pi.content = p_content
                    pi.if_commented = True

                if post_author_id is not None and post_author_id == comment_author_id:
                    # comment of the same author as the post
                    # log.info('SAME AUTHOR AS OF THE POST!')
                    # log.info('Post\'s influencer: %s' % p.influencer)
                    # log.info('Follower\'s influencer: %s' % pi.follower.influencer)
                    if pi.follower.influencer is None:
                        log.info('Updating follower\'s influencer...')
                        pi.follower.influencer = p.influencer
                        pi.follower.save()

                # saving the pi if changed
                if not self.test_run and pi_to_save is True:
                    pi.save()
                    self._inc('pis_saved')
                    log.info('Saved post interaction id=%s', pi.id)
                    res.append(pi)
                    self.created_pis.append(pi)
                else:
                    self._inc('pis_skipped')
                    log.info('Skipping existing PostInteraction id=%s', pi.id)

        return res

    @classmethod
    def get_description(cls, url, xb=None):
        """
        This description method uses the _fetch_data() method to get the bio and the website to create the description.
        """
        try:
            temp_d, _ = cls._fetch_data(url)
            bio = utils.nestedget(temp_d, 'entry_data', 'ProfilePage', 0, 'user', 'biography')
            website = utils.nestedget(temp_d, 'entry_data', 'ProfilePage', 0, 'user', 'external_url')
            desc = ''
            desc += bio or ''
            desc += ' '
            desc += website or ''
            return desc
        except:
            log.exception('While get_description')
            return None


class FacebookFetcher(SocialPlatformFetcher):
    name = 'Facebook'
    influencer_update_operation = 'fill_from_fb_data'
    auth_params = {'access_token': '%s|%s' % (settings.FACEBOOK_APP_ID, settings.FACEBOOK_APP_SECRET)}

    def __init__(self, platform, policy):
        super(FacebookFetcher, self).__init__(platform, policy)

        if not self._ensure_has_validated_handle():
            raise fetcherbase.FetcherException('Cannot get validated_handle')

        self._init_success = self._update_platform()
        if not self._init_success:
            raise fetcherbase.FetcherException('Facebook API init not successful '
                                               'for platform %r' % self.platform)

    @classmethod
    def _raise_for_call_limit(cls, resp_json, platform=None):
        if 'error' in resp_json and resp_json['error'].get('code') == 4:
            if platform:
                platform.inc_api_calls(None, 'rate limit')
            raise fetcherbase.FetcherCallLimitException('Facebook application request limit', None,
                                                        settings.FACEBOOK_WAIT_AFTER_LIMIT_EXCEEDED)

    @classmethod
    def _parse_user_id_from_url(cls, url):
        return platformutils.username_from_platform_url(url)

    def get_validated_handle(self):
        user_id = self._parse_user_id_from_url(self.platform.url)
        if user_id is None:
            return None
        resp = self._get('/{user_id}'.format(user_id=user_id))
        userdata = resp.json()
        if 'error' in userdata and userdata['error'].get('code') == 803:
            self.platform.inc_api_calls(resp.status_code, '803 non-existent user')
            log.error('Detected non-existent user id %s', user_id)
            # return None
            log.error('Trying the whole link...')
            resp = self._get('/{the_url}'.format(the_url=self.platform.url))
            userdata = resp.json()
            if 'error' in userdata and userdata['error'].get('code') == 803:
                self.platform.inc_api_calls(resp.status_code, '803 non-existent user')
                log.error('Detected non-existent user for url %s', self.platform.url)
                return None
            elif 'og_object' in userdata:
                # We've got a page unsubscribable
                log.error('Detected unsubscribable page og_object for url %s', self.platform.url)
                return None

        self.platform.inc_api_calls(resp.status_code)
        return userdata.get('id')

    def _update_platform(self):
        resp = self._get('/{user_id}'.format(user_id=self.platform.validated_handle))
        userdata = resp.json()
        self.platform.inc_api_calls(resp.status_code)

        self.platform.total_numlikes = userdata.get('likes')
        # for compatibility with other platforms
        self.platform.num_followers = self.platform.total_numlikes

        self._update_popularity_timeseries()

        if 'cover' in userdata and 'source' in userdata['cover']:
            self.platform.cover_img_url = userdata['cover']['source']

        resp = self._get('/{user_id}/picture?redirect=false&type=large'.format(user_id=self.platform.validated_handle))
        self.platform.inc_api_calls(resp.status_code)
        picdata = resp.json()
        if picdata and 'data' in picdata and 'url' in picdata['data']:
            self.platform.profile_img_url = picdata['data']['url']

        if 'locale' in userdata:
            self.platform.locale = userdata['locale']
            print "Set locale to %s " % userdata['locale']

        self._update_detected_name(self._resolve_name(userdata))
        self._update_detected_description(userdata.get('description'))
        self._update_detected_about(userdata.get('about'))

        city = userdata.get('location', {}).get('city')
        country = userdata.get('location', {}).get('country')
        location = city
        if country:
            location += ', ' + country

        self._update_detected_location(location)

        self.platform.save()
        if self.platform.profile_img_url or self.platform.cover_img_url:
            image_manipulator.save_social_images_to_s3(self.platform)
        return True

    def _resolve_name(self, userdata):
        full_name = None
        if 'first_name' in userdata and userdata['first_name']:
            full_name = userdata['first_name']
            if 'last_name' in userdata and userdata['last_name']:
                full_name += " " + userdata['last_name']
        elif 'name' in userdata and userdata['name']:
            full_name = userdata['name']
        elif 'username' in userdata and userdata['username']:
            full_name = userdata['username']
        return full_name

    def _fetch_json_data(self, url):
        resp = requests.get(url)
        self.platform.inc_api_calls(resp.status_code)
        data = resp.json()
        self._raise_for_call_limit(data, self.platform)
        return data

    def _link_from_id(self, id):
        assert '_' in id
        q_id, q_fbid = id.split('_')
        return 'https://www.facebook.com/permalink.php?story_fbid={q_fbid}&id={q_id}'.\
            format(q_id=q_id, q_fbid=q_fbid)

    def _fill_mentions(self, post, p):
        data = utils.nestedget(p, 'to', 'data')
        if data and isinstance(data, list):
            names = [d['name'] for d in data if 'name' in d]
            log.info('Found mentions: %r', names)
            post.mentions = utils.add_to_comma_separated(post.mentions, names)

    @recalculate_activity_level
    def fetch_posts(self, max_pages=5):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        if not self._init_success:
            log.error('API init not successful, not performing API call')
            return []
        resp = self._get('/{user_id}/posts'.format(user_id=self.platform.validated_handle))
        self.platform.inc_api_calls(resp.status_code)
        data = resp.json()
        print('POSTS JSON:')
        print(data)
        self._last_post_data = data
        page_no = 1
        res = []

        while self.policy.should_continue_fetching(self):
            if not data or not data.get('data'):
                break
            for p in data['data']:
                if 'id' not in p:
                    continue
                api_id = str(p['id'])
                # Sometimes we get facebook posts with urls directed to outer resources.
                # May be we should use urls from 'link' node only when they are not outer links.
                # this way we prevent Facebook Posts having urls pointing to outer resources.
                try:
                    if 'link' in p:
                        api_link = p['link']
                        is_fb_link = urlparse(api_link).netloc.endswith('facebook.com')

                        # using the api-provided link if it is of our API
                        if is_fb_link is True:
                            link = api_link
                        else:
                            link = self._link_from_id(api_id)

                            # otherwise checking if there is an existing post with outer non-FB link
                            existing_posts = models.Posts.objects.filter(url=api_link, platform=self.platform)
                            if existing_posts.count() == 0:
                                # no posts with original url, creating new post as usual - going down by the code.
                                log.info('No existing posts were found with api link %s , '
                                         'creating a new one with permalink %s ' % (api_link, link))
                                pass
                            elif existing_posts.count() == 1:
                                # one existing post is found, just updating its url and setting its last_modified date
                                log.info('FOUND 1 existing post with api link %s:' % api_link)
                                post = existing_posts[0]
                                log.info('Found post: %s' % post)
                                log.info('Substituting its url with: %s' % link)

                                # TODO: NO SAVING FOR NOW comments should be removed later
                                post.url = link
                                post.last_modified = datetime.datetime.now()
                                post.save()

                            else:
                                # if we found duplicates, skipping for now, logging this
                                log.info('FOUND MORE THAN 1 POSTS: %s' % existing_posts)
                                continue
                    else:
                        link = self._link_from_id(api_id)
                except AttributeError:
                    log.error('Generating generic post\'s url, link node supplied incorrect url: %s' % p.get('link'))
                    link = self._link_from_id(api_id)
                if models.Posts.objects.filter(url=link, platform=self.platform).exists():
                    self._inc('posts_skipped')
                    log.info('Skipping already saved facebook entry with url %s', link)
                    continue
                post = models.Posts()
                post.api_id = api_id
                post.platform = self.platform
                post.platform_name = 'Facebook'
                post.influencer = self.influencer
                post.show_on_search = self.influencer.show_on_search
                post.url = link
                post.content = p.get('message', '')
                if p['type'] == 'photo':
                    post.post_image = settings.FACEBOOK_BASE_URL + '/' + p['object_id'] + '/picture'
                post.create_date = iso8601.parse_date(p['created_time'])
                if 'shares' in p and 'count' in p['shares']:
                    post.engagement_media_numfbshares = p['shares']['count']
                    post.engagement_media_numshares = p['shares']['count']
                self._fill_mentions(post, p)

                self.save_post(post)
                res.append(post)

                self.fetch_post_interactions([post])
            if page_no == max_pages:
                break
            page_no += 1
            if 'paging' in data and 'next' in data['paging']:
                data = fetcherbase.retry_when_call_limit(
                    lambda: self._fetch_json_data(data['paging']['next']))
            else:
                break
        return res

    def fetch_post_images(self, posts_list=None, max_pages=None):
        from collections import defaultdict
        if not self._init_success:
            log.error('API init not successful, not performing API call')
            return []
        resp = self._get('/{user_id}/posts'.format(user_id=self.platform.validated_handle))
        self.platform.inc_api_calls(resp.status_code)
        data = resp.json()
        self._last_post_data = data

        res = []

        posts = defaultdict(list)
        for post in models.Posts.objects.filter(platform=self.platform):
            try:
                url = post.url.split('?')[0]
            except IndexError:
                url = post.url
            posts[url].append(post)

        log.info('* There are {} posts in the platform.'.format(len(posts)))

        while data is not None and data.get('data') is not None:
            photos = (
                (p.get('link', self._link_from_id(p['id'])), p['object_id'])
                for p in data['data'] if 'id' in p and p['type'] == 'photo'
            )

            for link, object_id in photos:
                try:
                    try:
                        link = link.split('?')[0]
                    except IndexError:
                        pass
                    dup_posts = posts[link]
                except KeyError:
                    continue
                else:
                    log.debug('* link={}, object_id={}:'.format(link, object_id))
                    for post in dup_posts:
                        post.post_image = "{}/{}/picture".format(
                            settings.FACEBOOK_BASE_URL, object_id)
                        post.save()
                        res.append(post)
                        log.debug('*** id={}, url={}, post_image={}'.format(
                            post.id, post.url, post.post_image))

            try:
                next_page = data['paging']['next']
            except KeyError:
                break
            else:
                data = fetcherbase.retry_when_call_limit(
                    lambda: self._fetch_json_data(next_page))

        return res

    def fetch_post_interactions(self, posts_list, max_pages=20):
        # TODO: Refactor all three (likes, comments and shares) into one request:
        # /v2.6/{post_id}/?fields=likes.summary(true),comments.summary(true),shares

        if not self._init_success:
            log.error('API init not successful, not performing API call')
            return []
        res = []
        page_no = 1
        for p in posts_list:
            # Likes
            resp = self._get('/{id}/likes?summary=true'.format(id=p.api_id))
            self.platform.inc_api_calls(resp.status_code)
            likedata = resp.json()
            if likedata.get('summary') and likedata.get('summary').get('total_count'):
                p.engagement_media_numlikes = likedata['summary']['total_count']
                p.save()
            while True:
                if not likedata.get('data'):
                    break
                for l in likedata['data']:
                    pi = models.PostInteractions()
                    pi.follower = self._get_follower(l['name'], None)
                    pi.platform_id = p.platform_id
                    pi.post = p
                    # No create date for facebook likes
                    pi.create_date = p.create_date
                    pi.if_liked = True
                    self._save_pi(pi, res)
                if page_no >= max_pages:
                    break
                page_no += 1
                if 'paging' in likedata and 'next' in likedata['paging']:
                    likedata = fetcherbase.retry_when_call_limit(
                        lambda: self._fetch_json_data(likedata['paging']['next']))
                else:
                    break

            # Comments
            resp = self._get('/{id}/comments?summary=true'.format(id=p.api_id))
            self.platform.inc_api_calls(resp.status_code)
            commentdata = resp.json()
            if 'summary' in commentdata and 'total_count' in commentdata['summary']:
                p.engagement_media_numcomments = commentdata['summary']['total_count']
            p.save()
            while True:
                if not commentdata.get('data'):
                    break
                for c in commentdata['data']:
                    pi = models.PostInteractions()
                    pi.follower = self._get_follower(c['from']['name'], None)
                    pi.platform_id = p.platform_id
                    pi.post = p
                    pi.content = c['message']
                    pi.numlikes = c['like_count']
                    pi.create_date = iso8601.parse_date(c['created_time'])
                    pi.if_commented = True
                    self._save_pi(pi, res)
                if page_no >= max_pages:
                    break
                page_no += 1
                if 'paging' in commentdata and 'next' in commentdata['paging']:
                    commentdata = fetcherbase.retry_when_call_limit(
                        lambda: self._fetch_json_data(commentdata['paging']['next']))
                else:
                    break

            # get share counts
            # resp = self._get('/{id}/shares?summary=true'.format(id=p.api_id))  # Old form
            resp = self._get('/v2.6/{id}?fields=shares'.format(id=p.api_id))
            self.platform.inc_api_calls(resp.status_code)
            shareddata = resp.json()
            if 'summary' in shareddata and 'total_count' in shareddata['summary']:
                p.engagement_media_numfbshares = shareddata['summary']['total_count']
                p.engagement_media_numshares = shareddata['summary']['total_count']
            p.save()
        return res

    @classmethod
    def get_description(cls, url, xb=None, extra_fields=False):
        user_id = cls._parse_user_id_from_url(url)
        if user_id is None:
            return None
        resp = cls._get('/{user_id}'.format(user_id=user_id))
        userdata = resp.json()

        # adding extra fields like 'about' and 'website' content if
        # extra_fields == True, used in platform extractor
        if extra_fields is True:
            description = ' '.join([
                userdata.get(field_name, '') for field_name in (
                    'description', 'about', 'website', 'personal_info',
                )
            ])
        else:
            description = userdata.get('description')

        return description

    @classmethod
    def is_private(cls, url):
        user_id = cls._parse_user_id_from_url(url)
        if user_id is None:
            return None
        resp = cls._get('/{user_id}'.format(user_id=user_id))
        userdata = resp.json()
        return 'website' not in userdata

    @classmethod
    def get_validated_handle_check(cls, url):
        user_id = cls._parse_user_id_from_url(url)
        if user_id is None:
            return None
        resp = cls._get('/{user_id}'.format(user_id=user_id))
        userdata = resp.json()
        return userdata.get('id')

    @classmethod
    def _get(cls, url_postfix, params=None):
        assert url_postfix.startswith('/')
        url = settings.FACEBOOK_BASE_URL + url_postfix
        if params is None:
            params = {}
        params.update(cls.auth_params)
        log.debug('Fetching from url %s %s', url, params)
        resp = requests.get(url, params=params)
        log.debug('Resp content[:1000]: %s', resp.content[:1000])
        cls._raise_for_call_limit(resp.json())
        return resp

    @classmethod
    def is_profile(cls, url):
        # TODO: This method is about checking if this Facebook url is for page or for profile to show it or hide
        user_id = cls._parse_user_id_from_url(url)
        if user_id is None:
            return None
        resp = cls._get('/{user_id}'.format(user_id=user_id))
        userdata = resp.json()

        is_profile = True
        if 'error' in userdata and userdata['error'].get('code', 0) == 803:
            is_profile = False

        return is_profile


class PinterestFetcher(SocialPlatformFetcher):
    name = 'Pinterest'
    influencer_update_operation = 'fill_from_pin_page'

    def __init__(self, platform, policy):
        super(PinterestFetcher, self).__init__(platform, policy)

        try:
            self.xb = xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                                        load_no_images=True, extra_js_files=['pinterest.js'])
        except Exception as e:
            log.exception(e)

        if not self._ensure_has_validated_handle():
            raise fetcherbase.FetcherException('Cannot get validated_handle')

        self._fetch_profile_data()

        try:
            self.xb.load_url('http://%s/' % self.platform.validated_handle)
        except Exception as e:
            log.exception(e)

        self.goto_pins()
        self.clean_up_pins_page()

    def __del__(self):
        try:
            if self.xb:
                self.xb.cleanup()
                log.info('xBrowser object cleaned before PinterestFetcher object deletion')
        except Exception as e:
            log.exception(e)

    def goto_pins(self):
        '''
        For some obscure reason going directly to /user/pins/ redirects us back to /user/
        while clicking the Pins tab goes to the pins page and displays the modal login box.

        '''
        link_locator = '//*[contains(@class, "tabs")]//li/a[contains(@href, "/pins/")]'
        pins_tab_link = self.xb.driver.find_elements_by_xpath(link_locator)[0]
        pins_tab_link.click()

        for i in range(5):
            try:
                pin_holders = self.xb.driver.find_elements_by_class_name('pinHolder')
                if pin_holders:
                    break
                else:
                    time.sleep(settings.PINTEREST_RESULTS_POLL_SLEEP)
            except Exception as e:
                log.exception(e)

    def clean_up_pins_page(self):
        '''
        Delete the modal login box and reenable body scrolling.
        '''
        try:
            self.xb.execute_jsfun('_P.cleanUpPinsPage')
        except Exception as e:
            log.exception(e)

    def get_validated_handle(self):
        try:
            self.xb.load_url(self.platform.url)
            error = self.xb.driver.find_elements_by_xpath(
                '//div[contains(text(), "' + settings.PINTEREST_INVALID_USER_TEXT + '")]')
            if error:
                log.warn("Found error message on the page, invalid URL")
                return None
            url = self.xb.driver.current_url
            cleaned_url = platformutils.url_to_handle(url)
            for postfix in settings.PINTEREST_UNWANTED_POSTFIXES:
                cleaned_url = utils.remove_postfix(cleaned_url, postfix, case_sensitive=False)
            return cleaned_url
        except Exception as e:
            log.exception(e)
            return None

    _parsedatetime = parsedatetime.Calendar().parse

    def _parse_date(self, s):
        if not s:
            return None

        s = textutils.remove_nonstandard_chars(s)
        s_time = self._parsedatetime(s)[0]
        return datetime.datetime.fromtimestamp(time.mktime(s_time))

    def _fetch_profile_data(self):
        try:
            profile_url = 'http://' + self.platform.validated_handle
            log.info('Pinterest profile url: %s', profile_url)
            self.xb.load_url(profile_url)
            if self.influencer.is_enabled_for_automated_edits():
                self._fetch_location_data()
                self._fetch_username()
                self._fetch_profile_img()
                ## this is a static method because our platform-extractor needs to be able to check
                ## the description with only the url.
                description = self._fetch_description(self.xb.driver)
                if description:
                    self._update_detected_description(description)
            self._fetch_followers_counts()
            self._update_popularity_timeseries()
        except Exception as e:
            log.exception(e)

    def _fetch_location_data(self):
        try:
            el = self.xb.driver.find_elements_by_class_name('userProfileHeaderLocationWrapper')
            if not el or len(el) == 0:
                el = self.xb.driver.find_elements_by_xpath('//li[@class="locationWrapper"]')
            print "Location: got %d elements" % (len(el) if el else 0)
            if el and len(el) > 0:
                el = el[0]
                location = (el.text or '').strip()
                print "LOCATION %s" % location
                self._update_detected_location(location)
                return
            log.warn('Cannot find location element')
        except Exception as e:
            log.exception(e)
            return

    def _fetch_username(self):
        try:
            if not self.influencer.name or self.influencer.name == "Blogger name":
                el = self.xb.driver.find_elements_by_class_name('userProfileHeaderName')
                if not el or len(el) == 0:
                    el = self.xb.driver.find_elements_by_xpath('//div[@class="profileInfo"]//div[@class="name"]')
                if el and len(el) > 0:
                    el = el[0]
                    name = (el.text or '').strip()
                    log.info('Found name: %s', name)
                    self._update_detected_name(name)
        except Exception as e:
            log.exception(e)

    def _fetch_profile_img(self):
        try:
            els = self.xb.driver.find_elements_by_xpath('//div[@class="profileImage"]/img')
            if not els or len(els) == 0:
                log.info("No profile image element found")
            else:
                el = els[0]
                img_src = el.get_attribute('src')
                log.info("got image %s" % img_src)
                if not self.platform.profile_img_url:
                    self.platform.profile_img_url = img_src
                    self.platform.save()
                    image_manipulator.save_social_images_to_s3(self.platform)
        except Exception as e:
            log.exception(e)

    @staticmethod
    def _other_social_handles(driver):
        """
        Check if we have any other social profile url in the description
        """
        res = []
        try:
            els = driver.find_elements_by_xpath('//div[@class="profileInfo"]//a')
            if els and len(els) > 0:
                for e in els:
                    res.append(e.get_attribute('href'))
        except Exception as e:
            log.exception(e)

        return '\n'.join(res)

    @classmethod
    def _fetch_description(cls, driver):
        """
        This is now a class method so that it can be used during testing phase by platformextractor
        when we only have a url to check.

        Check the method get_description() below which is invoked by fetcher.try_get_social_description()
        """
        try:
            description = None
            els = driver.find_elements_by_class_name('userProfileHeaderBio')
            log.info("Found %d elements for userProfileHeaderBio" % (len(els) if els else 0))
            if not els or len(els) == 0:
                els = driver.find_elements_by_xpath('//p[@class="aboutText"]')
                log.info("Found %d elements for '//p[@class=aboutText'" % (len(els) if els else 0))
            if els:
                el = els[0]
                description = (el.text or '').strip()
                log.info("DESCRIPTION %s" % description)
            other_urls = cls._other_social_handles(driver)
            log.info("OTHER SOCIAL %s" % other_urls)
            if other_urls:
                log.info("OTHER SOCIAL %s" % other_urls)
                if description:
                    description = description + " " + other_urls
                else:
                    description = other_urls
                return description
        except Exception as e:
            log.exception(e)

        log.warn('No description element')
        return None

    def _first_num(self, els):
        if not els:
            log.warn('No els to extract num from: %s', els)
            return None
        el = els[0]
        txt = el.text or ''
        if txt == '':
            return 0
        log.info('Got txt: %r' % txt)
        txt = txt.split()[0]
        txt = txt.upper().strip()
        log.info('After preprocessing: %r' % txt)
        if txt.endswith('K'):
            n = txt[:len(txt)-1]
            log.info('return %r' % int(float(n)*1000))
            return int(float(n)*1000)
        if txt.endswith('M'):
            n = txt[:len(txt)-1]
            log.info('return %r' % int(float(n)*1000000))
            return int(float(n)*1000000)
        num = textutils.first_int_word(txt)
        log.info('return %r' % num)
        if num is None:
            log.warn('No number from els %s', els)
            return None
        return num


    def _fetch_followers_counts(self):
        followers = self._first_num(self.xb.driver.find_elements_by_class_name('FollowerCount'))

        if followers is not None:
            log.info('Saving num_followers=%s', followers)
            self.platform.num_followers = int(followers)
            self.platform.save()
        following = self._first_num(
            self.xb.driver.find_elements_by_xpath('//div[@class="FollowingCount Module"]/span[@class="value"]'))
        if following is not None:
            log.info('Saving num_following=%s', following)
            self.platform.num_following = int(following)
            self.platform.save()

    _pin_id_matcher = re.compile(r'.*/pin/(\d+).*', re.IGNORECASE)

    @classmethod
    def pin_id_for_post(cls, post):
        return cls._pin_id_matcher.sub(r'\1', post.url)

    @classmethod
    def get_last_pin_ids(cls, platform):
        posts = platform.posts_set.order_by('-inserted_datetime')[:30]
        return [cls.pin_id_for_post(p) for p in posts]

    @classmethod
    def fetch_pins(cls, xb, platform=None, fetch_all=False):
        pins = []
        try:
            last_pin_ids = cls.get_last_pin_ids(platform) if platform and fetch_all is not True else []
            xb.execute_jsfun('_P.startSearch', last_pin_ids)
            iter = 0

            while True:
                iter += 1
                if platform is not None:
                    platform.inc_api_calls()
                if iter >= settings.PINTEREST_RESULTS_POLL_MAX_ITERATIONS:
                    log.warn('Pinterest results not returned by xbrowser')
                    # get whatever pins we have received so far
                    pins_raw = xb.execute_jsfun('_P.searchResultsAsJSON')
                    pins = json.loads(pins_raw)
                    break
                time.sleep(settings.PINTEREST_RESULTS_POLL_SLEEP)
                log.debug('Checking for pinterest results')
                finished = xb.execute_jsfun('_P.searchFinished')
                if finished:
                    pins_raw = xb.execute_jsfun('_P.searchResultsAsJSON')
                    pins = json.loads(pins_raw)
                    log.info('Pins: %s', pins)
                    break
                else:
                    log.debug('Results not yet available')
        except Exception as e:
            log.exception(e)

        return pins

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None, force_fetch=False):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        self.pins = self.fetch_pins(self.xb, self.platform, fetch_all=False)
        if not self.pins:
            log.error('No pins scraped')
            return []

        res = []
        bpf = None
        for p in self.pins:
            if not self.policy.should_continue_fetching(self):
                break

            post_exists = models.Posts.objects.filter(url=p['url'], platform=self.platform).exists()
            if force_fetch is not True and post_exists:
                log.debug('Skipping already saved pin with url %s', p['url'])
                self._inc('posts_skipped')
                continue
            elif force_fetch is True and post_exists:
                post = models.Posts.objects.filter(url=p['url'], platform=self.platform)[0]
            else:
                post = models.Posts()

            post.platform = self.platform
            post.platform_name = 'Pinterest'
            post.influencer = self.influencer
            post.show_on_search = self.influencer.show_on_search
            post.api_id = p['id']
            post.url = p['url']
            post.content = p.get('description')
            post.title = p.get('title')
            if p.get('img'):
                if not post.content:
                    post.content = p.get('img')
                else:
                    post.content += ' ' + p.get('img')
            # create_date set in fetch_post_interactions method
            #     Re: currently it is set with API and not for all posts.
            post.engagement_media_numlikes = int(p['likeCount']) if p.get('likeCount') else None
            post.engagement_media_numrepins = int(p['repinCount']) if p.get('repinCount') else None
            post.engagement_media_numcomments = int(p['commentCount']) if p.get('commentCount') else None
            post.pinned_by = self.convert_pinned_by(p.get('pinnedBy'))
            if p.get('sourceA'):
                self._set_pin_source(post, p['sourceA'])

            # fetching pin's date using api if this is a post of an influencer in active campaign at appropriate stage
            # and has no create_date set
            if post.create_date is None and \
                    models.InfluencerJobMapping.objects.filter(campaign_stage__gte=3,
                                                               job__archived=False,
                                                               mailbox__influencer_id=post.influencer_id).exists():

                # Initializing bpf here only if it is needed
                if bpf is None:
                    bpf = BasicPinterestFetcher()

                data = bpf.get_pin_data(post.api_id)
                if data is not None:
                    pin_date = data.get('data', None)
                    if pin_date:
                        pin_date = pin_date.get('created_at', None)
                        if pin_date:
                            pin_date = parser.parse(pin_date)
                            post.create_date = pin_date
                            post.last_modified = datetime.datetime.now()
                        else:
                            log.error('Pin API data was not fetched for post %s' % post.id)

            self.save_post(post)
            res.append(post)

            print('Created post %s' % post.id)
            print('Url: %r' % post.url)
            print('Title: %r' % post.title)
            print('Content: %r' % post.content)

        #for post in res:
        #    self.fetch_post_interactions([post])

        # Fetch pins from /source/ page
        from . import externalposts
        source_fetcher = externalposts.PinsBySourceFetcher(self.xb, self.influencer)
        source_fetcher.fetch()

        return res

    def _set_pin_source(self, post, blog_post_url):
        post.pin_source = utils.remove_fragment(blog_post_url)
        post.save()

    def fetch_post_interactions(self, posts_list):
        res = []
        bpf = None
        for post in posts_list:
            single_pin_url = 'http://www.pinterest.com/pin/{id}/'.format(id=post.api_id)
            try:
                self.xb.load_url(single_pin_url, refresh=False)
                data = self.xb.execute_jsfun('_P.singlePageData')
                self.platform.inc_api_calls()
            except:
                log.exception('While _P.singlePageData, skipping post %s', single_pin_url)
                continue
            self._last_data = data
            log.info('Received single pin data: %s', data)

            # print('DATA (post.id):')
            # print(data)

            post.engagement_media_numlikes = int(data['likeCount']) if data.get('likeCount') else None
            post.engagement_media_numrepins = int(data['repinCount']) if data.get('repinCount') else None
            post.engagement_media_numcomments = int(data['commentCount']) if data.get('commentCount') else None
            post.save()
            log.info('New engagement information for post %s : %s/%s/%s' % (
                post.id,
                post.engagement_media_numlikes,
                post.engagement_media_numrepins,
                post.engagement_media_numcomments,
            ))

            if data['pinUrl'] != post.url:
                # Oops! This pin has another url. What to do with it?
                log.info('Oops! This pin has another url. What should we do with it?')
                try:
                    # (1) Search if we have this post
                    new_post = models.Posts.objects.get(url=data['pinUrl'])
                    # getting its post_interactions too:
                    self.fetch_post_interactions([new_post, ])
                    log.info('Ok, post with this url already exist, skipping it.')
                except models.Posts.MultipleObjectsReturned:
                    log.info('Wow-wow-wow! We have even more than 1 of these, that\'s more than enough!')
                    pass
                except models.Posts.DoesNotExist:
                    # (2) We do not have this post - if it is a post of our platform - creating it.

                    with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                                           load_no_images=True, extra_js_files=['pinterest.js']) as local_xb:
                        local_xb.load_url(data.get('pinUrl'), refresh=False)

                        data = local_xb.execute_jsfun('_P.singlePageData')
                        self.platform.inc_api_calls()

                        pin_id = urlparse(data.get('pinUrl')).path.strip('/').split('/')[-1]

                        plat_username = urlparse(post.platform.url).path.strip('/').split('/')[0]
                        new_pin_username = urlparse(data.get('pinnedBy')).path.strip('/').split('/')[0]

                        # if platfoirmname is the same as pin's username, then creating it
                        if plat_username == new_pin_username:

                            post = models.Posts()
                            post.platform = self.platform
                            post.platform_name = 'Pinterest'
                            post.influencer = self.influencer
                            post.show_on_search = self.influencer.show_on_search
                            post.api_id = pin_id
                            post.url = data.get('pinUrl')
                            post.content = data.get('description')
                            post.title = data.get('title')
                            img_url = data.get('img')
                            if img_url:
                                if not post.content:
                                    post.content = img_url
                                else:
                                    post.content += ' ' + img_url
                            try:
                                post.engagement_media_numlikes = int(data.get('likeCount', 0))
                            except ValueError:
                                pass
                            try:
                                post.engagement_media_numrepins = int(data.get('repinCount', 0))
                            except ValueError:
                                pass
                            try:
                                post.engagement_media_numcomments = int(data.get('commentCount', 0))
                            except ValueError:
                                pass

                            post.last_modified = datetime.datetime.now()

                            # fetching pin's date using api if this is a post of an influencer in active campaign
                            # at appropriate stage and has no create_date set
                            if post.create_date is None and \
                                    models.InfluencerJobMapping.objects.filter(
                                        campaign_stage__gte=3,
                                        job__archived=False,
                                        mailbox__influencer_id=post.influencer_id
                                    ).exists():

                                # Initializing bpf here only if it is needed
                                if bpf is None:
                                    bpf = BasicPinterestFetcher()

                                data = bpf.get_pin_data(post.api_id)
                                if data is not None:
                                    pin_date = data.get('data', None)
                                    if pin_date:
                                        pin_date = pin_date.get('created_at', None)
                                        if pin_date:
                                            pin_date = parser.parse(pin_date)
                                            post.create_date = pin_date
                                            post.last_modified = datetime.datetime.now()
                                        else:
                                            log.error('Pin API data was not fetched for post %s' % post.id)

                            self.save_post(post)

                            log.info('Yay! Based on repinned post, we created a new post: %s' % post.id)

                        else:
                            log.info('Potential post is not of the same creator, usernames are different: %s vs %s' % (
                                plat_username,
                                new_pin_username
                            ))

        return res

    def _get_pin_data_by_url(self, pin_url):
        """
        Getting pin's data:
         image
         id
         url
         note (content)
         created_at
         original link
        """

        data = {}
        with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                               load_no_images=True, extra_js_files=['pinterest.js']) as xb:
            xb.load_url(pin_url, refresh=False)

            try:

                # pins = self.xb.driver.find_elements_by_xpath('//div[@class="item activeItem"]/span[@class="value"]')
                # if len(pins) > 0:
                #     the_pin = pins[0]
                #
                #     img_tag = the_pin.find_element_by_tag_name('img')
                #     if img_tag:
                #         data['image'] = img_tag.get_attribute('src')
                #
                #     try:
                #         data['note'] = the_pin.find_elements_by_class_name('pinDescription')[0].text.strip()
                #     except IndexError:
                #         pass
                #
                #     data['original_link'] = None

                data = xb.execute_jsfun('_P.singlePageData')
                self.platform.inc_api_calls()

                print('DATA:')
                print(data)
            except Exception as e:
                log.exception(e)

        return data

    @staticmethod
    def convert_pinned_by(pinned_by):
        if not pinned_by:
            return None
        assert pinned_by.startswith(('http://', 'https://'))
        path = urlparse(pinned_by).path
        parts = [p for p in path.split('/') if p]
        if parts:
            return 'http://www.pinterest.com/%s' % parts[0]
        return None

    @classmethod
    def get_description(cls, url, xb=None):
        """
        Re-using the implementation in _fetch_description method above.
        """
        # we'll use requests here
        from lxml.html import fromstring
        r = requests.get(url, verify=False)
        if r.status_code == 200:
            s = fromstring(r.content)
            url_found = None
            about = None
            urlsInProfile = s.xpath('//div[@class="profileInfo"]//a')
            if urlsInProfile and len(urlsInProfile) > 0:
                urlsInProfile = urlsInProfile[0]
                url_found = urlsInProfile.attrib.get('href')
            aboutText = s.xpath('//p[@class="aboutText"]')
            if aboutText and len(aboutText) > 0:
                aboutText = aboutText[0]
                about = aboutText.text
            else:
                aboutText = s.xpath('//*[@class="userProfileHeaderBio"]')
                if aboutText and len(aboutText) > 0:
                    aboutText = aboutText[0]
                    about = aboutText.text
            if about and url_found:
                return about + ' ' + url_found
            elif about:
                return about
            else:
                return url_found
        log.warning('%r returned non 200 status message' % url)
        return None
        # def load_description(local_xb):
        #     local_xb.load_url(url)
        #     return cls._fetch_description(local_xb.driver)

        # if xb is not None:
        #     return load_description(xb)
        # else:
        #     try:
        #         with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
        #                                load_no_images=True, extra_js_files=['pinterest.js']) as xb:
        #             return load_description(xb)
        #     except Exception as e:
        #         log.exception(e)
        #         return None

    def cleanup(self):
        if hasattr(self, 'xb') and self.xb:
            try:
                self.xb.cleanup()
            except Exception as e:
                log.exception(e)


class BloglovinFetcher(SocialPlatformFetcher):
    name = 'Bloglovin'
    influencer_update_operation = 'fill_from_bloglovin_page'

    def __init__(self, platform, policy):
        super(BloglovinFetcher, self).__init__(platform, policy)

        # let's get the blogname, description, and name of the blogger from here

    def _update_info(self, to_save=True):
        r = requests.get(self.platform.url)
        tree = lxml.html.fromstring(r.content)
        # blogname = tree.xpath('//div[@class="blog-info"]/h1[@class="name"]')
        blogname = tree.xpath('//div[@class="header-card"]'
                              '/h1[contains(concat(" ",@class," "), "header-card-h1" )]')
        blogname_txt = None
        descr_txt = None
        if blogname and len(blogname) > 0:
            blogname_txt = blogname[0].text.strip()
        else:
            # blogname = tree.xpath('//div[@class="user-info"]/h1[@class="name"]')
            blogname = tree.xpath('//div[@class="header-card"]'
                                  '/h1[contains(concat(" ",@class," "), "header-card-h1" )]')
            if blogname and len(blogname) > 0:
                blogname_txt = blogname[0].text.strip()
        if blogname_txt:
            if to_save:
                self._update_detected_blogname(blogname_txt)
        # descr = tree.xpath('//div[@class="blog-info"]/h2[@class="about"]')
        descr = tree.xpath('//div[@class="header-card"]'
                           '/div[contains(concat(" ",@class," "), "header-card-about" )]')
        if descr and len(descr) > 0:
            descr_txt = descr[0].text.strip()
        else:
            # descr = tree.xpath('//div[@class="user-info"]/h2[@class="about"]')
            descr = tree.xpath('//div[@class="header-card"]'
                               '/div[contains(concat(" ",@class," "), "header-card-about" )]')
            if descr and len(descr) > 0:
                descr_txt = descr[0].text.strip()
        if descr_txt:
            if to_save:
                self._update_detected_description(descr_txt)
        # name = tree.xpath('//li/div[@class="blog-by"]//span[@class="author"]')
        name = tree.xpath('//li/div[contains(concat(" ",@class," "), "header-card-claim-msg-text" )]'
                          '//a[contains(concat(" ",@class," "), "header-card-claim-msg-link" )]')
        if name and len(name) > 0:
            name = name[0].text.strip()
            if to_save:
                self._update_detected_name(name)
        log.info("Got Name:[%s] Blogname: [%s] Descr: [%s]" % (name, blogname_txt, descr_txt))

    @classmethod
    def get_description(cls, url, xb=None):
        """
        Getting description field from Bloglovin. For now, we're just collecting links to other platforms so that
        we can validate if this url belongs to the blog.
        """
        r = requests.get(url)
        tree = lxml.html.fromstring(r.content)

        social_links = tree.xpath('//div[contains(@class, "header-card")]//a/@href')
        res = set()
        for s in social_links:
            res.add(s)
        return '\n'.join(res)

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        self._update_info()
        self.platform.save()


class GPlusFetcher(SocialPlatformFetcher):
    name = 'Gplus'

    @classmethod
    def get_profile(cls, url):
        uid = platformutils.username_from_platform_url(url)

        service = google_plus.GPlusService()
        return service.get_profile(uid)

    @classmethod
    def get_description(cls, gplus_url, xb=None):
        profile = cls.get_profile(gplus_url)
        external_urls_no_duplicates = set(
            [url for name, url in (profile.sites + profile.profiles + profile.links)])
        return '\n'.join(external_urls_no_duplicates)

    def _update_platform_data(self):
        profile = self.get_profile(self.platform.url)

        if profile.full_name:
            name = profile.full_name
        elif profile.first_name and profile.last_name:
            name = profile.first_name + ' ' + profile.last_name
        elif profile.first_name:
            name = profile.first_name
        elif profile.last_name:
            name = profile.last_name
        elif profile.other_names:
            name = profile.other_names[0]
        else:
            name = None

        self._update_detected_name(name)

        self._update_detected_description(profile.introduction)
        self._update_detected_about(profile.tagline)
        self._update_detected_location(profile.location)

        self.platform.influencer_attributes['emails'] = profile.emails
        self.platform.influencer_attributes['gender'] = profile.gender

        self.platform.influencer_attributes['profiles'] = profile.profiles
        self.platform.influencer_attributes['sites'] = profile.sites
        self.platform.influencer_attributes['links'] = profile.links

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        self._update_platform_data()
