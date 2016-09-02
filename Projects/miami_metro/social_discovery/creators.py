import json
import logging
import re
import time
from pydoc import locate

import requests
from bs4 import BeautifulSoup
from django.core.cache import cache

from debra.models import MentionInPost, Posts, Influencer, Platform
from platformdatafetcher.platformutils import (
    OpRecorder, username_from_platform_url,
)
from platformdatafetcher.postanalysis import clean_content_for_keyword_search
from social_discovery.crawler_task import crawler_task
from social_discovery.instagram_crawl import (
    get_post_content_and_author_comments, scrape_profile_details,
)
from social_discovery.models import (
    InstagramProfile, PlatformLatestPostProcessed,
)
from social_discovery.pipeline_constants import MINIMUM_FRIENDS_COUNT
from social_discovery.pipelines import BasicClassifierPipeline
from xpathscraper import utils, xutils

"""
This file contains all Creator and derived modules for InstagramProfile pipeline.
"""

log = logging.getLogger('social_discovery.creators')

# regexps to find hashtags and mentions in text, useful for any Creator descendant
_RE_HASHTAG = re.compile(r'[\s,.!:;]#(\w+)')
_RE_MENTION = re.compile(r'[\s,.!:;]@(\w+)')


def find_hashtags(content):
    """
    Helper method to get hashtags list from provided content
    """
    if not content:
        return None
    # let space be the first character so that regex can match
    content = ' ' + content
    hashtags = _RE_HASHTAG.findall(content)
    hashtags = [x.lower() for x in hashtags]
    hashtags = utils.unique_sameorder(hashtags)
    log.info('Found hashtags: %r' % hashtags)
    return hashtags

def find_mentions(content):
    """
    Helper method to get mentions list from provided content
    """
    if not content:
        return None
    # let space be the first character so that regex can match
    content = ' ' + content
    mentions = _RE_MENTION.findall(content)
    mentions = [x.lower() for x in mentions]
    mentions = utils.unique_sameorder(mentions)
    log.info("Found mentions: %r" % mentions)
    return mentions


class Creator(object):
    """
    Creator module:
     this will be a parent module and we can have multiple sub-classes. Each module will be responsible for
     creating profiles for each type of objects. The logic inside will use different ways we can create profiles.

    Technically, it should be a periodic task, which will perform create_profiles() operation on some queryset of
     source data and create for this data new profiles that do not yet exist.

    """

    # here we could have statistical counters, with some method to refresh or reset it
    profiles_created = 0

    def create_new_profiles(self, **kwargs):
        """
        This method is a starting point of obtaining new profiles. Here we perform some initial criteria
        (getting initial hashtags and issuing tasks for feed performance for Instagram platform for example).
        Will be overridden in each of Creator's children.
        """
        raise NotImplementedError

    def create_profile(self, url=None, content=None):
        """
        Different implementation for various platforms. Acquires url or raw content data.
        """
        raise NotImplementedError

# Example modules for creation of profiles for different types of objects:

class InstagramCreator(Creator):
    """
    Defines a method for creation of profiles by separate Instagram posts' urls.
    Should have child classes.
    """

    def create_new_profiles(self, **kwargs):
        """
        This method is a starting point of obtaining new profiles. Here we perform some initial criteria
        (getting initial hashtags and issuing tasks for feed performance for Instagram platform for example).
        Will be overridden in each of Creator's children.
        """
        raise NotImplementedError

    def create_profile(self, url=None, tag=None, category=None, pipeline_class=None, **kwargs):
        """
        Creating profile by Instagram post url or raw content object (in future, if needed)
        """

        def append_hashtags_mentions_commentors_to_description(profile, hashtags, mentions, commentors):
            if not hashtags:
                hashtags = []
            if not mentions:
                mentions = []
            if not commentors:
                commentors = []
            for h in hashtags:
                log.info("checking hashtags %r" % h)
                if not profile.profile_description:
                    # print("Adding hashtag from own comment: %r" % h)
                    profile.profile_description = h
                if profile.profile_description and not h in profile.profile_description:
                    # print("Adding hashtag from own comment: %r" % h)
                    profile.profile_description += ' ' + h
            for m in mentions:
                log.info("checking mentions %r" % m)
                if not profile.profile_description:
                    # print("Adding mentions from own comment: %r" % m)
                    profile.profile_description = '@'+m
                if profile.profile_description and not '@'+m in profile.profile_description:
                    # print("Adding mentions from own comment: %r" % m)
                    profile.profile_description += ' @' + m
            # save commentors as well with !*_<username> type
            for c in commentors:
                log.info("checking commentor %r" % c)
                if not profile.profile_description:
                    # print("Adding commentor: %r" % c)
                    profile.profile_description = '!*_'+c
                if profile.profile_description and not '!*_'+c in profile.profile_description:
                    # print("Adding commentor: %r" % c)
                    profile.profile_description += ' !*_' + c

            profile.save()

        def find_hashtags_mentions_commentors_in_comments(post_username, post_user_id, comments):
            hashtags = []
            mentions = []
            commentors = set()
            for j in comments:
                m = j['user']['id']
                commentor = j['user']['username']
                commentors.add(commentor)
                content = ''
                if post_user_id == m:
                    content += j['text']
                if len(content) > 0:
                    print("Content = %r" % content)
                    if xutils.is_html(content):
                        cleaned_content = xutils.strip_html_tags(content)
                        print("Needed to clean it up, it's now: %r" % cleaned_content)
                    else:
                        cleaned_content = content
                    set1 = find_hashtags(cleaned_content)
                    set2 = find_mentions(cleaned_content)
                    if set1:
                        hashtags.extend(set1)
                    if set2:
                        mentions.extend(set2)
            return hashtags, mentions, commentors

        log.info("Scraping url: %s" % url)

        # getting category from kwargs, getting tag from kwargs, otherwise detecting it from url
        # category = kwargs.get('category', None)
        # tag = kwargs.get('tag', None)
        if not tag:
            # try to get tag from the url
            if 'tagged' in url:
                loc = url.find('tagged=') + len('tagged=')
                tag = url[loc:]
                log.info("No tag given, but found tag = %s from url %s" % (tag, url))

        # getting page's content
        r = requests.get(url, headers=utils.browser_headers())

        # Poor man's throttling. Just wait 2 seconds.
        time.sleep(2)

        # TODO: need some check of requests result

        # getting instagram data, post's mention(?) and creator's id
        soup = BeautifulSoup(r.content)
        instagram_data = self.__extract_instagram_data(soup)

        owner_data = instagram_data.get('PostPage')[0].get('media').get('owner')
        mention = owner_data.get('username')
        post_creator_id = owner_data.get('id')

        log.info("In %r found mention: %s and tag: %r and category: %s" % (url, mention, tag, category))

        # creating pending profile using mention, tag and category -
        res, created = self.create_pending_profile(mention, tag)

        log.info('PROFILE_CHECK_01 created=%s id=%s date_created=%s' % (created, res.id, res.date_created))

        if res.friends_count and res.friends_count < MINIMUM_FRIENDS_COUNT:
            log.info("Small number of followers %d (lesser than %s) for %s, so returning" % (
                res.friends_count, MINIMUM_FRIENDS_COUNT, res.username
            ))
            return res, None

        # get hashtags & mentions from captions
        caption = instagram_data.get('PostPage')[0].get('media').get('caption', None)
        hashtags_in_caption = find_hashtags(caption)
        mentions_in_caption = find_mentions(caption)
        append_hashtags_mentions_commentors_to_description(res, hashtags_in_caption, mentions_in_caption, None)

        # get hashtags & mentions from comments made by the author herself (very common)
        comments = instagram_data.get('PostPage')[0].get('media').get('comments').get('nodes')
        hashtags_in_comments, mention_in_comments, commentors = find_hashtags_mentions_commentors_in_comments(mention, post_creator_id, comments)
        append_hashtags_mentions_commentors_to_description(res, hashtags_in_comments, mention_in_comments, commentors)

        if category:
            if res.tags and category in res.tags:
                log.info("Category %r already exists in %r, let's not do more analysis" % (category, res))
                return res, commentors
            #save the tag as well as the hashtag
            res.append_tag(category)
            if tag:
                append_hashtags_mentions_commentors_to_description(res, [tag], [], [])

        MentionInPost.objects.filter(platform_name='Instagram', mention=mention).update(
            influencer_imported=True
        )

        # If this profile was freshly-created and has required prerequisites (has desired number of followers, etc),
        # its hashtags and mentions were set, pipeline_class provided,
        # then we initiate Pipeline performance of this profile.
        if created and pipeline_class is not None:
            try:
                # adding pipeline tag for profile to know from which pipeline it came
                res.append_tag('PIPELINE_%s' % pipeline_class)

                # getting a 'pipeline' by its name
                log.info('Loading pipeline %s for profile %s' % (pipeline_class, res.id))
                pipeline_cls = locate('social_discovery.pipelines.%s' % pipeline_class)

                # creating an 'objekt' of the class
                pipeline = pipeline_cls()

                log.info('Running pipeline %s for profile %s' % (pipeline_class, res.id))
                # calling the required function with appropriate params
                pipeline.run_pipeline(res.id)
            except KeyError:
                log.error('Pipeline %s not found' % pipeline_class)

        log.info('PROFILE_CHECK_02 created=%s id=%s date_created=%s' % (created, res.id, res.date_created))
        return res, commentors

    @staticmethod
    def __extract_instagram_data(soup):
        scripts = soup.find_all('script')
        data_script = [s for s in scripts if '_sharedData' in s.text][0]
        data_js = data_script.text
        json_data = data_js[data_js.find('{'): data_js.rfind('}') + 1]
        parsed_data = json.loads(json_data)
        return parsed_data.get('entry_data', {})

    @classmethod
    def create_pending_profile(cls, username, append_tag=None):
        """
        Creates or gets profile by username (actually, by mention)
        :param username:
        :param append_tag:
        :param category:
        :return:
        """
        profile, created = InstagramProfile.objects.get_or_create(
            username=username
        )
        profile.update_description(append_tag)

        if created:
            log.info('Created new pending profile: %r', username)
            cls.update_profile_details(profile.id)
            # refetch it so that we don't overwrite it
            profile = InstagramProfile.objects.get(id=profile.id)
        else:
            log.info('Already exists: %r', username)

        return profile, created

    @classmethod
    def update_profile_details(cls, profile_id):
        with OpRecorder('instagram_crawl_profile_details'):
            profile = InstagramProfile.objects.get(pk=profile_id)
            log.info(
                'Updating details for: %s, pending: %r',
                profile.username, profile.update_pending
            )
            details = scrape_profile_details(profile)
            profile.update_from_web_data(details)


class CreatorByInstagramHashtags(InstagramCreator):
    """
    Uses hashtags to create profiles.
    This creator's initial data is a list of hashtags, which are performed one by one.
    For each tag a feed is obtained and posts from this feed are performed.
    """

    def create_new_profiles(self,
                            hashtags=None,
                            submission_tracker=None,
                            num_pages_to_load=20,
                            pipeline_class=None,
                            **kwargs):
        """
        Iterates over a list of hashtags by mask https://instagram.com/explore/tags/<hashtag>/
        Issues a task to perform

        Note: 'hashtags' should be a dict with categories and tags like:
        {'singapore': ['oo7d', 'anothertag', 'onemoretag', ...], ...}

        """
        if type(hashtags) != dict:
            log.error('hashtags parameter should be a dict of categories and lists '
                      'of their corresponding hashtags, not a %s' % type(hashtags))
            return None

        log.info('Issuing tasks to obtain profiles for hashtags: %s' % hashtags)
        # print('hashtags: %s   num_pages: %s' % (hashtags, num_pages_to_load))

        with OpRecorder('instagram_crawl_scrape_instagram_feeds'):
            categories = hashtags.keys()
            for cat in categories:
                tags = hashtags[cat]
                for tag in tags:
                    crawler_task.apply_async(
                        kwargs={
                            'klass_name': 'CreatorByInstagramHashtags',
                            'task_type': 'perform_feed',
                            'tag': tag,
                            'num_pages': num_pages_to_load,
                            'category': cat,
                            'pipeline_class': pipeline_class
                        },
                        queue='instagram_feed_scraper'  # Queue where tasks to perform separate feeds are put
                    )

                    if submission_tracker is not None:
                        submission_tracker.count_task('crawlers.scrape_instagram_feed_for_tag')

    def perform_feed(self, tag, num_pages, category, pipeline_class=None, **kwargs):
        """
        This scrapes the instagram tags page for a given tag
        blog_discovery.hashtags[category] = {list of tags}.
        """
        with OpRecorder('instagram_crawl_feed_for_tag'):
            from xpathscraper import xbrowser
            from django.conf import settings
            page_count = 0
            image_urls = set()
            old_image_urls_count = 0
            log.info("Starting scraping for tag %r" % tag)
            with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, load_no_images=True) as xb:
                url = 'https://instagram.com/explore/tags/%s/' % tag
                xb.load_url(url)
                time.sleep(2)

                # checking the number of posts if it is already in cache
                posts_qty = None
                posts_qty_nodes = xb.driver.find_elements_by_xpath('//header/span/span[@class]')
                if len(posts_qty_nodes) > 0:
                    try:
                        posts_qty = posts_qty_nodes[0].text
                        posts_qty = int(posts_qty.strip().replace(',', ''))
                        cached_posts_qty = cache.get('instagram_tag__%s' % tag)
                        if cached_posts_qty is not None and (posts_qty - int(cached_posts_qty)) <= 100:
                            log.info(
                                'Cached posts quantity is %s, now it is %s, '
                                'too few new posts - skipping this feed.' % (cached_posts_qty, posts_qty)
                            )
                            return
                        else:
                            log.info(
                                'Cached posts quantity is %s, now it is %s, performing this feed.' % (cached_posts_qty,
                                                                                                      posts_qty)
                            )
                    except ValueError:
                        log.error('Could not parse posts quantity to number: %s, please check format' % posts_qty)
                else:
                    log.info('No posts quantity node detected, possible Instagram page HTML structure changed.')

                # scroll to the bottom before we can find the 'load more pages' button
                xb.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                while page_count < num_pages:
                    # find all images on the page so far and add them to our set
                    try:
                        # images = xb.driver.find_elements_by_xpath('//div[contains(@class, "PostsGrid__root")]//a')
                        # Instagram structure changed
                        images = xb.driver.find_elements_by_xpath('//article//a')
                    except:
                        page_count = num_pages
                        continue
                    all_image_urls = set()
                    for i in images:
                        all_image_urls.add(i.get_attribute('href'))

                    new_image_urls = all_image_urls - image_urls
                    image_urls = all_image_urls
                    if len(image_urls) == old_image_urls_count:
                        page_count = num_pages
                        continue
                    old_image_urls_count = len(image_urls)

                    print("new images: %d so far we have %d image urls for tag %r" % (len(new_image_urls), len(image_urls), tag))
                    for i in new_image_urls:
                        try:
                            crawler_task.apply_async(
                                kwargs={
                                    'klass_name': 'CreatorByInstagramHashtags',
                                    'task_type': 'create_profile',
                                    'url': i,
                                    'tag': tag,
                                    'category': category,
                                    'pipeline_class': pipeline_class
                                },
                                # Queue where tasks to create new profiles for separate posts in feed are put
                                queue='scrape_instagram_posts_new',
                            )
                        except:
                            print("some error for %s" % i)
                            pass
                    # find the next page button
                    # el = xb.driver.find_elements_by_xpath('//div[contains(@class, "moreLoadingIndicator")]//a')
                    el = xb.driver.find_elements_by_xpath('//a[contains(text(), "Load more")]')

                    if page_count == 0 and len(el) > 0:
                        e = el[0]
                        e.click()
                        log.info("Found next page button for page %s successfully, clicking and waiting." % page_count)

                    else:
                        log.info("'Load More Pics' button not found... returning.")
                        #page_count = num_pages
                        # scroll to the bottom before we can find the 'load more pages' button
                        xb.driver.execute_script("window.scrollTo(0, 50);")
                        xb.driver.execute_script("window.scrollTo(0, 1000000);")
                    time.sleep(3)
                    page_count += 1

                # caching post quantity for this tag
                if tag is not None and isinstance(posts_qty, int):
                    cache.set('instagram_tag__%s' % tag, posts_qty)


class CreatorByInstagramCommentors(Creator):
    """
    Uses commentors to create profiles. As initial data we could pass a queryset of valid Commentors,
    whom we sill perform. Also we will tag these people as 'COMMENTOR'
    """
    pass


class CreatorByInstagramMentions(Creator):
    """
    Use user mentions from the brand posts and comments made by the brand
    to find new Influences
    """
    def _start_pipilene(self, instagram_profile, pipeline_class):
        try:
            # add pipeline tag for profile to know which pipeline it came from
            instagram_profile.append_tag(
                'PIPELINE_%s' % pipeline_class.__name__
            )

            # get a 'pipeline' by its name
            log.info('Loading pipeline {0} for profile {1}'.format(
                pipeline_class.__name__, instagram_profile.id
            ))

            pipeline = pipeline_class()

            log.info('Running pipeline {0} for profile {1}'.format(
                pipeline_class.__name__, instagram_profile.id
            ))
            # call the required function with appropriate params
            pipeline.run_pipeline(instagram_profile.id)
        except AttributeError:
            log.exception(
                'Pipeline class {0} is missing required attributes'.format(
                    pipeline_class
                )
            )

    def create_new_profiles(
        self, platforms_q=None, posts_limit=None, **kwargs
    ):
        if platforms_q is None:
            # Get all brands platfroms
            influencers_q = Influencer.objects.filter(
                source='retailers_to_crawl'
            )
            platforms_q = Platform.objects.filter(
                influencer__in=influencers_q, platform_name='Instagram'
            )

        for platform in platforms_q:
            (
                platform_post_relation, _,
            ) = PlatformLatestPostProcessed.objects.get_or_create(
                platform=platform, defaults={'platform': platform, },
            )
            posts = Posts.objects.filter(
                platform=platform,
                id__gt=platform_post_relation.latest_post_id_processed
            ).exclude(
                products_import_completed=True
            )
            if posts_limit:
                posts = posts[:posts_limit]
            latest_processed_post_id = 0
            for post in posts:
                log.info('Processing {}'.format(post.url))
                content_and_comments = get_post_content_and_author_comments(
                    post.url
                )
                if not content_and_comments:
                    latest_processed_post_id = post.id
                    continue
                cleaned_content = clean_content_for_keyword_search(
                    content_and_comments
                )
                mentions = _RE_MENTION.findall(cleaned_content)
                mentions = utils.unique_sameorder(
                    [x.lower() for x in mentions]
                )
                log.info('Found mentions: {}'.format(mentions))
                for mention in mentions:
                    (
                        instagram_profile, created,
                    ) = InstagramProfile.objects.get_or_create(
                       username__iexact=mention,
                       defaults={'username': mention, },
                    )
                    platform_username = username_from_platform_url(
                        platform.url
                    )
                    instagram_profile.append_tag(
                        'link_from_retailer_{0}'.format(platform_username)
                    )
                    if (
                        created or
                        instagram_profile.discovered_influencer is None
                    ):
                        # Mark newly created profiles and those that enter
                        # the pipeline due to this creator
                        instagram_profile.append_tag(
                            'created_link_from_retailer_{0}'.format(
                                platform_username
                            )
                        )
                        self._start_pipilene(
                            instagram_profile, BasicClassifierPipeline
                        )
                latest_processed_post_id = post.id
            platform_post_relation.latest_post_id_processed = (
                latest_processed_post_id
            )
            platform_post_relation.save()
