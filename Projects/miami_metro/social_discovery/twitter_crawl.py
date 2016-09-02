from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import twitter
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
import re

import time
import requests
from bs4 import BeautifulSoup
import nltk
from django.conf import settings
from django.core.cache import get_cache
from celery.decorators import task

from social_discovery import models
from debra import models as dmodels
from debra import helpers
from platformdatafetcher.platformutils import OpRecorder
from xpathscraper import utils
from . import twitter_utils
from . import blog_discovery
from . import google_search


log = logging.getLogger('social_discovery.twitter_crawl')


def create_client():
    return twitter.Twitter(
        auth=twitter.OAuth(
            settings.TWITTER_OAUTH_TOKEN,
            settings.TWITTER_OAUTH_SECRET,
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET
        )
    )


@task(
    name="social_discovery.twitter_crawl.fetch_friends",
    max_retries=None,
    rate_limit='1/m',
)
def fetch_friends(screen_name, platform_id=None, cursor=-1, batch_size=200):
    with OpRecorder('twitter_crawl_fetch_friends'):
        cache = get_cache('default')
        rate_limit = cache.get('twitter_rate_limited_until')
        if rate_limit and rate_limit > datetime.utcnow():
            log.info('Still rate limited. Retrying later...')
            fetch_friends.retry(
                kwargs=dict(screen_name=screen_name, cursor=cursor, batch_size=batch_size),
                countdown=15 * 60
            )
            return

        try:
            client = create_client()
            profile = get_profile(screen_name, platform_id)

            log.info("Fetching twitter friends. screen_name: %s, platform_id: %s, cursor: %s",
                    screen_name, platform_id, cursor)
            response = client.friends.list(screen_name=profile.screen_name, count=batch_size, cursor=cursor)
            next_cursor = response['next_cursor']
            friends_batch = response['users']

            save_friends(profile, friends_batch)

            if next_cursor == 0:
                log.info('Last friend batch for Twitter profile: %s', profile.screen_name)
                profile.friends_updated = datetime.utcnow()
                profile.save()
            else:
                log.info('Queuing next friend batch for Twitter profile: %s, cursor: %s',
                        profile.screen_name, next_cursor)
                queue_fetch_task(
                    fetch_friends,
                    screen_name=screen_name,
                    platform_id=platform_id,
                    cursor=next_cursor,
                    batch_size=batch_size
                )
        except twitter.TwitterError:
            log.info('Got a Twitter fetch error. Setting rate limit flag and retrying...')
            cache.set('twitter_rate_limited_until', datetime.utcnow() + timedelta(minutes=15))
            fetch_friends.retry(
                kwargs=dict(screen_name=screen_name, cursor=cursor, batch_size=batch_size),
                countdown=15 * 60
            )


def start_fetch_for_platform(platform):
    screen_name = twitter_utils.screen_name_for_url(platform.url)
    if screen_name:
        queue_fetch_task(fetch_friends, screen_name=screen_name, platform_id=platform.pk)
    else:
        log.warning('Could not extract screen name from platform url: %r', platform.url)


def queue_fetch_task(task, **kwargs):
    return task.apply_async(
        kwargs=kwargs,
        queue='twitter_fetch_friends',
        countdown=10,
    )


def save_friends(profile, friends):
    for friend in friends:
        save_friend(profile, friend)


def save_friend(profile, friend_data):
    screen_name = friend_data['screen_name']

    description = get_full_description(friend_data)
    if has_blog_candidate(description):
        log.info("Saving profile '%s' - found blog keywords in description.", screen_name)

        friend_profile = get_profile(screen_name, platform_id=None)
        friend_profile.profile_description = description
        friend_profile.post_count = friend_data.get('statuses_count', 0)
        friend_profile.friends_count = friend_data.get('friends_count', 0)
        friend_profile.followers_count = friend_data.get('followers_count', 0)
        friend_profile.last_post_time = parse_timestamp(friend_data.get('status', {}).get('created_at'))
        friend_profile.api_data = friend_data
        friend_profile.save()

        models.TwitterFollow.objects.get_or_create(follower=profile, followed=friend_profile)
    else:
        log.info("Skipping profile save for '%s' - no blog keywords in description.", screen_name)


def parse_timestamp(text):
    if not text:
        return None

    return dateutil_parser.parse(text)


def get_full_description(friend_data):
    urls = [
        url_data.get('expanded_url', url_data.get('url'))
        for entity in friend_data.get('entities', {}).values()
        for url_data in entity.get('urls', [])
    ]
    valid_urls = [url for url in urls if url is not None]

    description = friend_data.get('description', '')
    return '\n'.join(valid_urls) + '\n' + description


def get_profile(screen_name, platform_id=None):
    profile, created = models.TwitterProfile.objects.get_or_create(
        screen_name=screen_name,
        defaults=dict(platform_id=platform_id),
    )
    if created:
        log.info('Created new Twitter profile: %s', screen_name)

    if platform_id is not None and profile.platform_id != platform_id:
        log.info('Linking Twitter profile: %s with platform %s', screen_name, platform_id)
        profile.platform_id = platform_id
        profile.save()

    return profile


blog_keywords = {'blog', 'blogger', 'influencer'}


def has_blog_candidate(description):
    words = set(nltk.wordpunct_tokenize(description))
    return len(blog_keywords & words) > 0


def _no_blogs(profile):
    """
    Fail parsing and extraction and exclude from further attempts.
    """
    log.info('No blogs discovered for profile %s', profile)
    profile.update_pending = False
    profile.valid_influencer = False
    profile.save()


@task(name="social_discovery.twitter_crawl.discover_blogs")
def discover_blogs(profile_id):
    with OpRecorder('twitter_crawl_discover_blogs'):
        profile = models.TwitterProfile.objects.get(pk=profile_id)
        blogs = find_blogs(profile)

        if not blogs:
            log.info('No blogs discovered for profile %s', profile)
            _no_blogs(profile)
            return

        if not profile_is_valid_influencer(profile):
            log.info('Profile %s not valid. Flagging and skipping...')
            _no_blogs(profile)
            return

        influencer = helpers.create_influencer_and_blog_platform_bunch(
            blogs,
            'discovered_via_twitter',
            category=None
        )
        if len(influencer) >= 1:
            influencer = list(influencer)[0]

        if influencer and not influencer.tw_url or profile.screen_name not in influencer.tw_url:
            influencer.tw_url = 'https://twitter.com/%s' % profile.screen_name
            influencer.save()
            log.info("Updated influencer %d tw_url to '%s'", influencer.pk, influencer.tw_url)

        if influencer:
            profile.discovered_influencer = influencer
            profile.valid_influencer = True
            profile.save()


def find_blogs(profile):
    description = blog_discovery.get_description_decoded(profile.profile_description)
    if blog_discovery.has_influencer_keywords(description):
        return blog_discovery.find_blogs(description)
    return set()


def profile_is_valid_influencer(profile):
    description = blog_discovery.get_description_decoded(profile.profile_description)
    return blog_discovery.has_influencer_keywords(description)
        #profile.post_count > 100 and
        #profile.followers_count >= 200
        #profile.friends_count > 500
        #not important, not everyone uses twitter regularly
        #profile.last_post_time > last_month
        #)


def _get_twitter_page(screen_name):
    twitter_url = 'https://twitter.com/%s' % screen_name
    r = requests.get(twitter_url, headers=utils.browser_headers())

    # Poor man's throttling. Just wait 2 seconds.
    time.sleep(2)
    return r.content


def _get_summary_link_title(soup, data_nav):
    link_tag = soup.find(name='a', attrs={'data-nav': data_nav})
    if link_tag:
        return link_tag.attrs['title']
    else:
        return None


def _extract_number(title_text):
    if title_text:
        numbers_only = re.sub(r'\D', '', title_text)
        return int(numbers_only)
    else:
        return 0


def _extract_description(soup):
    return unicode(soup.find('div', attrs={'class': 'ProfileHeaderCard'}))


def _extract_last_post_time(soup):
    timestamps = [
        # data-time contains the Unix timestamp value
        datetime.fromtimestamp(int(timestamp_el.attrs['data-time']))
        for timestamp_el in soup.find_all('span', attrs={'class': 'js-short-timestamp'})
        if timestamp_el and timestamp_el.attrs.get('data-time')
    ]
    if timestamps:
        return max(timestamps)
    else:
        return None


def _extract_profile_details(screen_name, content):
    soup = BeautifulSoup(content)
    return {
        'screen_name': screen_name,
        'followers': _extract_number(_get_summary_link_title(soup, 'followers')),
        'following': _extract_number(_get_summary_link_title(soup, 'following')),
        'tweets': _extract_number(_get_summary_link_title(soup, 'tweets')),
        'favorites': _extract_number(_get_summary_link_title(soup, 'favorites')),
        'description_html': _extract_description(soup),
        'last_post_time': _extract_last_post_time(soup),
    }


def scrape_profile_details(screen_name):
    return _extract_profile_details(
        screen_name,
        _get_twitter_page(screen_name)
    )


@task(name="social_discovery.twitter_crawl.discover_from_google")
def discover_from_google(bio_search, page=0, max_pages=1000):
    with OpRecorder('twitter_crawl_discover_from_google'):
        log.info('Discovering for bio search %r, page: %d, max_pages: %d', bio_search, page, max_pages)
        discovered_screen_names = google_search.get_twitter_profiles_with_bio(bio_search, page=page)

        for screen_name in discovered_screen_names:
            create_pending_profile(screen_name)

        if page < max_pages - 1:
            discover_from_google.apply_async(
                kwargs=dict(bio_search=bio_search, page=page + 1, max_pages=max_pages),
                queue='twitter_discover_from_google',
                routing_key='twitter_discover_from_google',
            )


def create_pending_profile(screen_name):
    profile, created = models.TwitterProfile.objects.get_or_create(
        screen_name=screen_name,
        defaults=dict(update_pending=True),
    )
    if created:
        log.info('Created new pending profile: %s', screen_name)
        return profile
    else:
        log.info('Already exists: %s', screen_name)
        return None


@task(name="social_discovery.twitter_crawl.update_profile_details")
def update_profile_details(profile_id):
    with OpRecorder('twitter_crawl_update_profile_details'):
        profile = models.TwitterProfile.objects.get(pk=profile_id)
        log.info('Updating details for: %s, pending: %r', profile.screen_name, profile.update_pending)
        details = scrape_profile_details(profile.screen_name)

        profile.friends_count = details['following']
        profile.followers_count = details['followers']
        profile.post_count = details['tweets']
        profile.profile_description = details['description_html']
        profile.last_post_time = details['last_post_time']
        profile.api_data = details

        profile.update_pending = False
        profile.save()


@task(name="social_discovery.twitter_crawl.import_from_mention")
def import_from_mention(mention_id):
    with OpRecorder('twitter_crawl_import_from_mention'):
        m = dmodels.MentionInPost.objects.get(pk=mention_id)
        if m.influencer_imported:
            log.info("Already imported mention %d for %s", m.pk, m.mention)
            return

        screen_name = m.mention.strip().lower()
        create_pending_profile(screen_name)

        dmodels.MentionInPost.objects.filter(platform_name='Twitter',
                                             mention=m.mention,
                                             influencer_imported=False).update(
            influencer_imported=True
        )


def submit_import_from_mention_tasks(submission_tracker, limit=100 * 1000):
    mention_ids = dmodels.MentionInPost.objects.filter(
        platform_name='Twitter', influencer_imported=False
    ).values_list('id', flat=True)[:limit]

    for mention_id in mention_ids:
        import_from_mention.apply_async(
            args=[mention_id],
            queue='twitter_import_from_mention',
            routing_key='twitter_import_from_mention',
        )
        submission_tracker.count_task('twitter_crawl.import_from_mention')


def submit_update_profile_tasks(submission_tracker):
    update_pending = models.TwitterProfile.objects.filter(update_pending=True)
    profile_ids = update_pending.values_list('id', flat=True)

    for profile_id in profile_ids:
        update_profile_details.apply_async(
            args=[profile_id],
            queue='twitter_update_profile_details',
            routing_key='twitter_update_profile_details',
        )
        submission_tracker.count_task('twitter_crawl.update_profile_details')


def submit_twitter_influencer_tasks(submission_tracker):
    extraction_pending = models.TwitterProfile.objects.filter(
        valid_influencer__isnull=True,
        update_pending=False
    )
    profile_ids = extraction_pending.values_list('id', flat=True)

    for profile_id in profile_ids:
        discover_blogs.apply_async(
            args=[profile_id],
            queue='twitter_discover_influencer',
            routing_key='twitter_discover_influencer',
        )
        submission_tracker.count_task('twitter_crawl.discover_blogs')
