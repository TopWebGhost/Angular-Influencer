from __future__ import (
    absolute_import, division, print_function, unicode_literals,
)

import json
import logging
import re
import time
from datetime import datetime
from urlparse import urlparse

import requests
from bs4 import BeautifulSoup
from celery import task
from django.core.cache import cache

from debra import helpers
from debra import models as dmodels
from debra.models import PlatformDataOp, InfluencersGroup
from masuka import image_manipulator
from platformdatafetcher import fetcher, platformextractor
from platformdatafetcher.emailextractor import extract_emails_from_text
from platformdatafetcher.platformutils import OpRecorder
from social_discovery import models
from xpathscraper import utils
from . import blog_discovery

log = logging.getLogger('social_discovery.instagram_crawl')


def _get_instagram_page(url):
    response = requests.get(url, headers=utils.browser_headers())
    # Poor man's throttling. Just wait 2 seconds.
    time.sleep(2)
    if response.status_code == 200:
        return response.content


def _extract_last_post_time(posts_data):
    if not posts_data:
        return
    timestamps = [
        # created_time contains the Unix timestamp value
        datetime.fromtimestamp(
            int(post.get('date', post.get('created_time', 0)))
        ) for post in posts_data
    ]
    if timestamps:
        return max(timestamps)


def _extract_instagram_data(soup):
    scripts = soup.find_all('script')
    data_script = [s for s in scripts if '_sharedData' in s.text][0]
    data_js = data_script.text
    json_data = data_js[data_js.find('{'): data_js.rfind('}') + 1]
    parsed_data = json.loads(json_data)
    return parsed_data.get('entry_data', {})


def scrape_profile_details(profile):
    content = _get_instagram_page(profile.get_url())
    if not content:
        return
    soup = BeautifulSoup(content)
    page_data = _extract_instagram_data(soup).get('ProfilePage', [None])[0]
    if not page_data:
        return
    user_data = page_data['user']

    description = user_data.get('biography', '')
    external_url = user_data.get('external_url')

    following = user_data.get('followed_by', dict()).get('count', 0)
    followers = user_data.get('follows', dict()).get('count', 0)
    posts_data = user_data['media'].get('nodes')

    return {
        'username': profile.username,
        'followers': followers,
        'following': following,
        'posts': user_data['media']['count'],
        'description': description,
        'external_url': external_url,
        'last_post_time': _extract_last_post_time(posts_data),
        'api_data': user_data,
    }


@task(name="social_discovery.instagram_crawl.update_profile_details")
def update_profile_details(profile_id, category):
    with OpRecorder('instagram_crawl_profile_details'):
        profile = models.InstagramProfile.objects.get(pk=profile_id)
        log.info(
            'Updating details for: %s, pending: %r',
            profile.username, profile.update_pending
        )
        details = scrape_profile_details(profile)
        profile.update_from_web_data(details)


def find_blogs(profile, category):
    """
    Find blog urls from the api_data description and external url.
    """
    description = profile.combine_description_and_external_url()
    return blog_discovery.find_blogs(description, category)


def connect_profiles_to_influencer(qset):
    """
    High level logic: we want to check if there already exists some influencers for each profile and spit out the
                      results in a dictionary (for debugging purposes before we make this function live):
                        'good': have one exact influencer
                        'problem': have more than one influencer match
                        'none': no influencer exists

                'good' and 'none' cases are the easiest to handle. We can go ahead and for (a) connect the profile with
                that influencer and for (b) create a new influencer and connect the profile.

                'problem' profiles require more work and investigation.

    Handling 'problem' profiles (initial thoughts):
        a) if all influencers are duplicates of each other
            => this is an easier case. We need to pick the best (influencer._select_influencer_to_stay(list_of_influencer))
            will pick the best. This however assumes that they are duplicates. So, we need to make sure this is correct.
        b) if one influencer is an artificial url, and others are duplicates, then pick the one from the duplicates.
            => need to figure out why an artificial url based influencer was created? Was there a bug?
        c) if at least one non-duplicate and non-artificial url based influencer was detected, then we need to investigate
            this. Out of the non-duplicates (say one is http://blah1.com and other is http://blah2.com), then we need
            to pick one of them. This usually happens if the influencer is part of another social network and by mistake
            we created an influencer for the social network but automatically connected the user to the social network's
            profile (e.g., http://etsy.com/user1 is the url and we created an Instagram profile for this that points to
            the user)
            These can be potentially fixed by only picking the influencer that has a platform that is auto-validated.
    """
    from . import create_influencers
    result = {'good': [], 'problem': [], 'none': []}

    for i, profile in enumerate(qset):
        print("\n\nWORKING WITH %d %r" % (i, profile))
        #profile = models.InstagramProfile.objects.get(id=profile_id)
        profile_url = profile.get_url()

        # this methods gets a mapping {'platform url': [list of influencers that matched]}
        found_infs_social, _ = create_influencers.find_matching_influencers_for_profile(profile, only_social=True)
        print("[ONLY SOCIAL] %r: found matching influencers: %r" % (profile, found_infs_social))

        found_infs_non_social, _ = create_influencers.find_matching_influencers_for_profile(profile, only_social=False)
        print("[ONLY NON-SOCIAL] %r: found matching influencers: %r" % (profile, found_infs_non_social))

        # here we get the unique list of influencers from these dictionaries
        all_social_infs = [item for sublist in found_infs_social.values() for item in sublist]
        all_non_social_infs = [item for sublist in found_infs_non_social.values() for item in sublist]

        all_social_infs.extend(all_non_social_infs)

        found_infs = set(all_social_infs)
        print("FINAL SET IS %d influencers: %r" % (len(found_infs), found_infs))

        if len(found_infs) == 1:
            # awesome
            print("Got only 1 matching influencer, we should connect <%r> with <%r>" % (profile, found_infs))
            result['good'].append({profile: found_infs})
        elif len(found_infs) > 1:
            # hmmm, so first we need to check if these are all duplicates of each other.
            # Also, what if one is an artificial url and others are not?
            # Finally,
            print("Found %d profiles that have this %s url " % (len(found_infs), profile_url))
            result['problem'].append({profile: found_infs})
        else:
            # we didn't find anything
            print("Didn't find anything: %r for %r" % (found_infs, profile))
            print("We should create an artificial url")
            result['none'].append({profile: found_infs})

    return result

@task(name="social_discovery.instagram_crawl.discover_blogs")
def discover_blogs(profile_id, category, to_save=True):
    from . import create_influencers
    with OpRecorder('instagram_crawl_discover_blogs'):
        profile = models.InstagramProfile.objects.get(pk=profile_id)
        blogs = find_blogs(profile, category)

        if not blogs:
            #No blog url is found, so we should create an artificial url or find an existing influencer
            log.info("No blogs found for %s, so we create an influencer with artificial url." % blogs)
            qset = models.InstagramProfile.objects.filter(id=profile_id)
            create_influencers.create_influencers_from_crawled_profiles(qset, minimum_followers=500, to_save=to_save)
            return 'ARTIFICIAL_BLOG'

        if len(blogs) > 1:
            log.warn("WARNING: Got more than 1 blog %s, RETURNING" % blogs)
            profile.append_tag('INFLUENCER_CREATION_ERROR_MULTIPLE_BLOGS')
            return 'INFLUENCER_CREATION_ERROR_MULTIPLE_BLOGS'

        influencer = helpers.create_influencer_and_blog_platform_bunch(
            blogs,
            'discovered_via_instagram',
            category=category,
            to_save=to_save
        )

        if len(influencer) == 0:
            log.info("WARNING:: No influencer found for %s, means that all are blacklisted." % blogs)
            profile.append_tag('INFLUENCER_CREATION_ERROR_ALL_BLACKLISTED')

        assert len(influencer) == 1
        influencer = list(influencer)[0]
        if influencer.instagram_profile.all().count() > 0:
            #This means that we already have another instagram profile that is connected to this influencer.
            #This happens with urls that are platforms (like ask.fm/<user> or dayre.com/<user>).
            log.info("Not associating %r with %s because it's already connected" % (profile.username, influencer))
            profile.append_tag("INFLUENCER_CREATION_ERROR_MULTIPLE_INSTA_PROFILES")
            return "INFLUENCER_CREATION_ERROR_MULTIPLE_INSTA_PROFILES"

        if influencer and not influencer.insta_url or profile.username not in influencer.insta_url:

            if not (influencer.validated_on and 'info' in influencer.validated_on):

                # updating email, name, location, image_url, description
                pl = create_platform_for_influencer(
                    url=profile.get_url(), inf=influencer, profile=profile,
                    to_save=to_save,
                    operation="created_from_instagram_crawl_directly"
                )

            create_influencers.get_influencers_email_name_location_for_profile(profile_id, to_save)
            log.info("Updated influencer %d insta_url to '%s'", influencer.pk, influencer.insta_url)

        if influencer and to_save:
            profile.discovered_influencer = influencer
            profile.valid_influencer = True
            influencer.classification = 'blog'
            influencer.save()
            profile.save()

        return 'EXISTING_BLOG'


def create_platform_for_influencer(
    url, inf, profile, platform=None, to_save=False,
    operation='created_from_instagram_crawl'
):
    """
    This function creates or uses provided platform and sets fields' values for
    email, description, location and name
    for influencer and Instagram platform.

    :param url:
    :param inf:
    :param profile:
    :param to_save:
    :return:
    """
    if not url or not inf or not profile:
        return None

    parsed_u = urlparse(url)
    domain = parsed_u.netloc.lower()

    if not dmodels.Platform.is_social_platform(domain):
        print("URL [%r] is not a social platform, returning")
        return

    if platform is None:
        pl = fetcher.create_single_platform_from_url(url, use_api=False, platform_name_fallback=True)
    else:
        pl = platform

    if not pl.platform_name or (
        pl.platform_name not in dmodels.Influencer.platform_name_to_field
    ):
        print("Platform %r is not a socail url that we care about" % pl)
        return

    field_name = dmodels.Influencer.platform_name_to_field[pl.platform_name]
    print("Setting %r to %r" % (field_name, pl.url))
    setattr(inf, field_name, pl.url)

    if parsed_u.netloc.lower() == 'instagram.com' and profile is not None:
        log.info('netloc is instagram')
        if profile.api_data is not None:
            if profile.api_data.get('full_name') is not None:
                pl.influencer_attributes['name'] = profile.api_data.get('full_name')
                log.info('profile full_name: %s   pl.influencer_attributes[name]: %s' % (
                    profile.api_data.get('full_name'), pl.influencer_attributes.get('name')))

            # setting the profile image of the platform and saving pic if saving is set to True
            if profile.api_data.get('profile_pic_url') is not None:
                pl.profile_img_url = profile.api_data.get('profile_pic_url')
                if to_save:
                    pl.save()
                    image_manipulator.save_social_images_to_s3(pl)

            # setting the country_block for
            if profile.api_data.get('country_block') is not None:
                inf.demographics_location = profile.api_data.get('country_block')

            # setting description
            if profile.api_data.get('biography') is not None:
                inf.description = pl.description = profile.api_data.get('biography')

        # extracting emails
        if inf.description is not None:
            emails = extract_emails_from_text(inf.description)
            if len(emails) > 0:
                # getting maximum 2 emails
                emails = ' '.join(emails[:2])
                inf.email_for_advertising_or_collaborations = emails

    else:
        # setting description if non-instagram platform
        pl.description = fetcher.try_get_social_description(pl.url)

    pl.influencer = inf

    if to_save:
        inf.save()
        platformextractor.save_validation_result('discovered_via_social_profile_description', pl)
        pl.save()
        _ = PlatformDataOp.objects.create(platform=pl, operation=operation)

    return pl


def create_pending_profile(username, append_tag=None, category=None):
    def update_description(profile, tag):
        if not profile.profile_description and tag:
            profile.profile_description = tag
            profile.save()
        if profile.profile_description and len(profile.profile_description) > 2000:
            log.info('profile description already too long, returning')
            return
        if profile.profile_description and tag and not tag in profile.profile_description.lower():
            profile.profile_description += " " + tag
            profile.save()

    profile, created = models.InstagramProfile.objects.get_or_create(username=username)
    update_description(profile, append_tag)

    if created:
        log.info('Created new pending profile: %r', username)
        update_profile_details(profile.id, category)
        # refetch it so that we don't overwrite it
        profile = models.InstagramProfile.objects.get(id=profile.id)
    else:
        log.info('Already exists: %r', username)

    return profile


@task(name="social_discovery.instagram_crawl.import_from_mention")
def import_from_mention(mention_id):
    with OpRecorder('instagram_crawl_import_from_mention'):
        m = dmodels.MentionInPost.objects.get(pk=mention_id)
        if m.influencer_imported:
            log.info("Already imported mention %d for %s", m.pk, m.mention)
            return

        screen_name = m.mention.strip().lower()
        create_pending_profile(screen_name)

        dmodels.MentionInPost.objects.filter(platform_name='Instagram',
                                             mention=m.mention,
                                             influencer_imported=False).update(
            influencer_imported=True
        )


def submit_import_from_mention_tasks(submission_tracker, limit=100 * 1000):
    mention_ids = dmodels.MentionInPost.objects.filter(
        platform_name='Instagram', influencer_imported=False
    ).values_list('id', flat=True)[:limit]

    for mention_id in mention_ids:
        import_from_mention.apply_async(
            args=[mention_id],
            queue='instagram_import_from_mention',
            routing_key='instagram_import_from_mention',
        )
        submission_tracker.count_task('instagram_crawl.import_from_mention')


def submit_instagram_influencer_tasks(submission_tracker):
    extraction_pending = models.InstagramProfile.objects.filter(
        valid_influencer__isnull=True,
        update_pending=False
    )
    profile_ids = extraction_pending.values_list('id', flat=True)

    for profile_id in profile_ids:
        discover_blogs.apply_async(
            args=[profile_id],
            queue='instagram_discover_influencer',
            routing_key='instagram_discover_influencer',
        )
        submission_tracker.count_task('instagram_crawl.discover_blogs')


#######################################################################
@task(name="social_discovery.instagram_crawl.scrape_instagram_posts", ignore_result=True)
def scrape_instagram_posts(insta_post_url, tag, category):
    """
    This gets a post_url from the scrape_instagram_feed and finds out the instagram handle.
    And checks if the mention already exists in the database. If so, return.

    If not, create the profile.
    category is either "fashion_hashtag" or "singapore"
    tag is a keyword for that category (from blog_discovery.hashtags)
    """
    from xpathscraper import xutils, utils
    import re
    _RE_HASHTAG = re.compile(r'[\s,.!:;]#(\w+)')
    _RE_MENTION = re.compile(r'[\s,.!:;]@(\w+)')

    def find_hashtags(content):
        if not content:
            return None
        # let space be the first character so that regex can match
        content = ' ' + content
        hashtags = _RE_HASHTAG.findall(content)
        hashtags = [x.lower() for x in hashtags]
        hashtags = utils.unique_sameorder(hashtags)
        print('Found hashtags: %r' % hashtags)
        return hashtags

    def find_mentions(content):
        if not content:
            return None
        # let space be the first character so that regex can match
        content = ' ' + content
        mentions = _RE_MENTION.findall(content)
        mentions = [x.lower() for x in mentions]
        mentions = utils.unique_sameorder(mentions)
        print("Found mentions: %r" % mentions)
        return mentions

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

    def append_hashtags_mentions_commentors_to_description(profile, hashtags, mentions, commentors):
        """
        save these hashtags, mentions, and commentors in the InstagramProfile.profile_description
        This profile_description is a field that is used to store meta-data (it's name should be changed at some point).
        """
        if not hashtags:
            hashtags = []
        if not mentions:
            mentions = []
        if not commentors:
            commentors = []

        for h in hashtags:
            curr_hashtags = profile.get_hashtags()
            log.info("Checking hashtag: %r" % h)
            if not h in curr_hashtags:
                print("Adding hashtag: %r" % h)
                if not profile.profile_description:
                    profile.profile_description = h
                else:
                    profile.profile_description += ' ' + h

        for m in mentions:
            curr_mentions = profile.get_mentions()
            mm = '@'+m
            log.info("Checking mention: %r" % mm)
            if not m in curr_mentions:
                print("Adding mentions: %r" % mm)

                if not profile.profile_description:
                    profile.profile_description = mm
                else:
                    profile.profile_description += ' ' + mm

        # save commentors as well with !*_<username> type
        for c in commentors:
            curr_commentors = profile.get_commentors()
            cc = '!*_'+c
            log.info("Checking commentor: %r" % cc)
            if not c in curr_commentors:
                print("Adding commentor: %r" % cc)
                if not profile.profile_description:
                    profile.profile_description = cc
                else:
                    profile.profile_description += ' ' + cc

        profile.save()

    log.info("Scraping %s" % insta_post_url)
    if not tag:
        # try to get tag from the url
        if 'tagged' in insta_post_url:
            loc = insta_post_url.find('tagged=') + len('tagged=')
            tag = insta_post_url[loc:]
            log.info("No tag given, but found tag = %s from url %s" % (tag, insta_post_url))
    r = requests.get(insta_post_url, headers=utils.browser_headers())

    # Poor man's throttling. Just wait 2 seconds.
    time.sleep(2)

    soup = BeautifulSoup(r.content)
    mention = _extract_instagram_data(soup).get('PostPage')[0].get('media').get('owner').get('username')
    post_creator_id = _extract_instagram_data(soup).get('PostPage')[0].get('media').get('owner').get('id')

    log.info("In %r found mention: %s and tag: %r and category: %s" % (insta_post_url, mention, tag, category))

    res = create_pending_profile(mention, tag, category)

    if res.friends_count and res.friends_count < 1000:
        log.info("Small number of followers %d for %s, so returning" % (res.friends_count, res.username))
        return res, None

    # get hashtags & mentions from captions
    caption = _extract_instagram_data(soup).get('PostPage')[0].get('media').get('caption', None)
    hashtags_in_caption = find_hashtags(caption)
    mentions_in_caption = find_mentions(caption)
    append_hashtags_mentions_commentors_to_description(res, hashtags_in_caption, mentions_in_caption, None)

    # get hashtags & mentions from comments made by the author herself (very common)
    comments = _extract_instagram_data(soup).get('PostPage')[0].get('media').get('comments').get('nodes')
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

    dmodels.MentionInPost.objects.filter(platform_name='Instagram', mention=mention).update(
        influencer_imported=True
    )
    return res, commentors


@task(name="social_discovery.instagram_crawl.scrape_instagram_feed_for_tag", ignore_result=True)
def scrape_instagram_feed_for_tag(tag, num_pages, category):
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

                # from social_discovery.crawler_draft import CreatorByInstagramHashtags
                for i in new_image_urls:
                    try:
                        scrape_instagram_posts.apply_async([i, tag, category], queue='scrape_instagram_posts_new')

                        # TODO: here we can call crawler_draft.CreatorByInstagramHashtags.create_profile() function
                        # also uncomment corresponding import line above
                        # cbih = CreatorByInstagramHashtags()
                        # cbih.create_profile(i, tag, category)
                    except:
                        print("some error for %s" % i)
                        pass
                # find the next page button
                el = xb.driver.find_elements_by_xpath('//div[contains(@class, "moreLoadingIndicator")]//a')

                if len(el) > 0:
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

        # now scrape these images to find the screen names
        #for i in image_urls:
        #    try:
        #        scrape_instagram_posts.apply_async([i], queue='scrape_instagram_posts')
        #    except:
        #        pass


@task(name="social_discovery.instagram_crawl.scrape_instagram_feeds", ignore_result=True)
def scrape_instagram_feeds(submission_tracker=None, only_these_tags=None, num_pages_to_load=20):
    """
    This will be a daily task that scrapes instagram public feed to find interesting
    influencers daily.

    Idea is to go to this page daily

    Iterate over the hashtags:
        1. https://instagram.com/explore/tags/<hashtag>/
        repeat until max_num_pages loaded:
            2. wait for the page to load
            3. get all posts url, issue a task to handle their content
            4. scroll to the bottom
            5. find the button to load more images
            6. wait for 1 min
            7. click on the next page
    """
    hashtags = blog_discovery.hashtags
    print('only_these_tags = %r' % only_these_tags)

    asia_analysis = False

    if len(only_these_tags) == 1 and only_these_tags[0] == 'singapore':
        asia_analysis = True

    if not asia_analysis:
        print("Returning because it's not focused on asia for now")
        return

    with OpRecorder('instagram_crawl_scrape_instagram_feeds'):
        categories = only_these_tags if only_these_tags else hashtags.keys()
        for cat in categories:
            tags = hashtags[cat]
            for tag in tags:
                scrape_instagram_feed_for_tag.apply_async([tag, num_pages_to_load, cat], queue='instagram_feed_scraper')
                if submission_tracker:
                    submission_tracker.count_task('instagram_crawl.scrape_instagram_feed_for_tag')


def read_urls_from_file(filename):
    """
    The filename is a file manually created with post urls for a given tag.
    """
    import re

    p = '/p/[\w\d]*/'
    c = re.compile(p)
    f = open(filename, 'r')
    content = f.read()
    result = c.findall(content)
    result = set(['https://instagram.com' + r for r in result])
    print("From %r found %d results" % (filename, len(result)))
    return result


def create_profiles_manually(filename, tag, category):
    """
    This issues a fetch for urls found from file 'filename' with a given hashtag.
    This file was downloaded manually from instagram by searching the hashtag.
    """
    result = read_urls_from_file(filename)
    already_had = 0
    new_ids = set()
    for i, purl in enumerate(result):
        print("Issuing fetch for %r" % purl)
        scrape_instagram_posts.apply_async([purl, tag, category], queue='scrape_instagram_posts_new')
        print("%d already=%d total_now=%d" % (i, already_had, len(new_ids)))


def handle_previous_influencers():
    from platformdatafetcher import contentclassification

    insta = models.InstagramProfile.objects.filter(discovered_influencer__isnull=False)
    insta = insta.exclude(discovered_influencer__blog_url__icontains='blogspot')
    insta = insta.exclude(discovered_influencer__blacklisted=True)
    print("Dealing with %d profiles now " % insta.count())
    not_blacklised = 0
    blacklisted = 0
    for i, inst in enumerate(insta):
        print("[%d] blacklised=[%d] not-blacklisted=[%d]" % (i, blacklisted, not_blacklised))
        try:
            res = contentclassification.classify(inst.discovered_influencer.blog_url)
        except:
            res = 'none'
        description = blog_discovery.get_description_decoded(inst.profile_description)
        if res == 'blog' or blog_discovery.has_influencer_power_keywords(description):
            print("%s is a blog or [%r] has the power keyword" % (inst.discovered_influencer.blog_url, description))
            not_blacklised += 1
        else:
            print("%s is NOT a blog or [%r] does not have the power keyword" % (inst.discovered_influencer.blog_url, description))
            inst.discovered_influencer.blacklisted = True
            inst.discovered_influencer.save()
            blacklisted += 1


def find_instagram_profile_obj_from_url(insta_post_url):
    """
    Fetch the InstagramProfile object given the post url
    """
    r = requests.get(insta_post_url, headers=utils.browser_headers())

    # Poor man's throttling. Just wait 2 seconds.
    time.sleep(2)
    try:
        soup = BeautifulSoup(r.content)
        mention = _extract_instagram_data(soup).get('PostPage')[0].get('media').get('owner').get('username')
        d = models.InstagramProfile.objects.filter(username=mention)
        if d.count() > 0:
            return d[0]
        else:
            return None
    except:
        return None

def check_instagram_pipeline(category=None):
    """
    This method checks the status of profiles discovered via Instagram and how they are being processed.
    `category`: if specified, we use the blog_discovery.keyword to find relevant profiles
    """
    from . import create_influencers
    insta = models.InstagramProfile.objects.all()
    if category:
        print("OK, we are given category: %r" % category)
        keywords = blog_discovery.hashtags[category]
        final = models.InstagramProfile.objects.none()
        for k in keywords:
            a = insta.filter(profile_description__icontains=k)
            print("\t%r: %d" % (k, a.count()))
            final |= a
        insta = final
        print("For %r we have %r profiles" % (category, insta.count()))


    discovered_influencer = insta.filter(discovered_influencer__isnull=False)
    not_discovered_influencer = insta.exclude(discovered_influencer__isnull=False)

    discovered_influencer_ids = list(discovered_influencer.values_list('discovered_influencer__id', flat=True))
    discovered_influencers = dmodels.Influencer.objects.filter(id__in=discovered_influencer_ids)

    discovered_influencers_valid = discovered_influencers.valid()
    discovered_influencers_show_on_search = discovered_influencers_valid.filter(show_on_search=True)
    discovered_influencers_validated = discovered_influencers.filter(validated_on__contains='info')
    discovered_influencers_blacklisted = discovered_influencers.filter(blacklisted=True)

    discovered_influencers_remaining = discovered_influencers.exclude(show_on_search=True).exclude(blacklisted=True).exclude(validated_on__contains='info')

    discovered_influencers_accuracy_validated = discovered_influencers_remaining.filter(accuracy_validated=True)

    discovered_influencers_not_yet_processed = discovered_influencers_remaining.exclude(accuracy_validated=True)

    discovered_influencers_remaining_good = discovered_influencers_not_yet_processed.get_quality_influencers_from_social_sources(1000, 500)
    good_quality_from_social_ids = list(discovered_influencers_remaining_good.values_list('id', flat=True))
    good_quality_from_social = dmodels.Influencer.objects.filter(id__in=good_quality_from_social_ids)
    discovered_influencers_with_good_keywords = create_influencers.find_valid_influencers_with_instagram_profiles(good_quality_from_social)

    msg = 'Checking pipeline of processing for urls discovered via Instagram\n'
    msg += 'Total Profiles: %d\n' % insta.count()
    print(msg)
    msg += '\tWith Influencer Discovered: %d\n' % discovered_influencer.count()
    print(msg)
    msg += '\tNo Influencer Discovered: %d\n' % not_discovered_influencer.count()
    print(msg)
    msg += '\tdiscovered_influencers_valid: %d\n\n' % discovered_influencers_valid.count()
    print(msg)
    msg += '\tdiscovered_influencers_show_on_search: %d\n\n' % discovered_influencers_show_on_search.count()
    print(msg)
    msg += '\tdiscovered_influencers_validated: %d' % discovered_influencers_validated.count()
    print(msg)
    msg += '\tdiscovered_influencers_blacklisted: %d' % discovered_influencers_blacklisted.count()
    print(msg)
    msg += '\tdiscovered_influencers_remaining: %d' % discovered_influencers_remaining.count()
    print(msg)
    msg += '\tdiscovered_influencers_accuracy_validated: %d' % discovered_influencers_accuracy_validated.count()
    print(msg)
    msg += '\tdiscovered_influencers_not_yet_processed: %d' % discovered_influencers_not_yet_processed.count()
    print(msg)
    msg += '\tdiscovered_influencers_remaining_good: %d' % discovered_influencers_remaining_good.count()
    print(msg)
    msg += '\tdiscovered_influencers_with_good_keywords: %d' % discovered_influencers_with_good_keywords.count()


    print(msg)


def dump():
    from . import create_influencers
    keywords = ['welovecleo', 'outfitsg', 'sgdaily', 'tsrwiwt', 'wearsg', 'theinfluencernetwork', 'afstreetstyle',
                'igersingapore', 'vscocamsg', 'femalegp2015', 'sgstreetstyleawards', 'shopmegagamie', 'stylexstyle',
                'innershinesg', 'sgfashionweekly', 'malaysiablogger', 'charleskeithofficial', 'shopsassydream',
                'projecttrendit', 'clozetteambassador', 'corde', 'mom fashion', 'Mamakode', 'BeautySalons', 'hair makeup']

    insta = models.InstagramProfile.objects.all()
    for k in keywords:
        k_insta = insta.filter(profile_description__icontains=k)
        k_insta_1K = k_insta.filter(friends_count__gte=1000)
        k_insta_blogger = create_influencers.find_valid_instagram_profiles(k_insta)
        k_insta_brand = create_influencers.find_brand_instagram_profiles(k_insta)
        k_insta_neither = k_insta.exclude(pk__in=k_insta_brand).exclude(pk__in=k_insta_blogger)
        print("%s;%d;%d;%d;%d;%d"% (k, k_insta.count(), k_insta_1K.count(), k_insta_blogger.count(), k_insta_brand.count(), k_insta_neither.count()))


from django.db.models import Q
def get_instagram_profiles_by_category(category=None, minimum_friends=1000):

    # all profiles
    profiles = models.InstagramProfile.objects.all()

    # only those who has followers >= 1K
    profiles = profiles.filter(friends_count__gte=minimum_friends)

    # only those who belongs to category
    if category is not None:
        # keywords for category & profiles filtering
        keywords = blog_discovery.hashtags[category]
        profiles = get_instagram_profiles_by_keywords(keywords, minimum_friends=minimum_friends, profiles=profiles)
        #profiles = profiles.filter(reduce(lambda x, y: x | y, [Q(profile_description__icontains=keyword) for keyword in keywords]))

    return profiles

def get_instagram_profiles_by_keywords(keywords=None, minimum_friends=1000, profiles=None):

    # all profiles
    if not profiles:
        profiles = models.InstagramProfile.objects.all()

    # only those who has followers >= 1K
    profiles = profiles.filter(friends_count__gte=minimum_friends)

    # only those who belongs to category
    if keywords is not None:
        profiles = profiles.filter(reduce(lambda x, y: x | y, [Q(profile_description__icontains=keyword) for keyword in keywords]))

    return profiles


def get_instagram_profiles_by_searching_blog_urls(profiles=None, minimum_friends=1000):
    """
    This function searches the profiles provided to find those with a valid blog url.
    So, we find urls that are provided in the description and then we run classification over these urls to check
    if they are a blog.
    """
    from platformdatafetcher.contentfiltering import find_all_urls
    from platformdatafetcher.contentclassification import classify
    from social_discovery.blog_discovery import queryset_iterator
    # all profiles
    if not profiles:
        profiles = models.InstagramProfile.objects.all()

    # helper method to keep stats
    def update_stats(username, reason, distribution):
        if username in distribution.keys():
            j = distribution[username]
            j.append(reason)
        else:
            distribution[username] = [reason]

    profiles = profiles.filter(friends_count__gte=minimum_friends)
    profiles_smart = queryset_iterator(profiles)
    ids = set()
    key_distribution = {}
    for p in profiles_smart:
        # first checking if the domain extensions provided exist in the external url
        if p.api_data and 'external_url' in p.api_data.keys() and p.api_data['external_url']:
            external_url = p.api_data['external_url'].lower()
            result = classify(external_url)
            if result == 'blog':
                ids.add(p.id)
            update_stats(p.username, result+":"+external_url, key_distribution)
            update_stats(p.username, 'external_url', key_distribution)

        # second, check if the keywords appear in the description
        if p.api_data and 'biography' in p.api_data.keys() and p.api_data['biography']:
            biography = p.api_data['biography']
            urls = find_all_urls(biography)
            for u in urls:
                result = classify(u)
                if result == 'blog':
                    ids.add(p.id)
                update_stats(p.username, result+":"+u, key_distribution)
                update_stats(p.username, 'biography', key_distribution)

    return profiles.filter(id__in=ids), key_distribution


def update_stats(username, reason, distribution):
    # helper method to keep stats

    if username in distribution.keys():
        j = distribution[username]
        j.append(reason)
    else:
        distribution[username] = [reason]


def simplify(input_str, preserve_urls=False):
    # helper method to clean up text so that we can do matches
    # replace .,|&/+-?: by space
    # then replace any non-ascii by space
    input_str_simple = input_str.replace(',', ' ')
    input_str_simple = input_str_simple.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    input_str_simple = input_str_simple.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')
    input_str_simple = input_str_simple.replace('[', ' ').replace(']', ' ').replace('(', ' ').replace(')', ' ')
    input_str_simple = input_str_simple.replace('{', ' ').replace('}', ' ').replace('<', ' ').replace('>', ' ')
    input_str_simple = input_str_simple.replace('-', ' ').replace('+', ' ').replace('#', ' ').replace('@', ' ')
    input_str_simple = input_str_simple.replace('*', ' ').replace('|', ' ')
    if preserve_urls is not True:
        input_str_simple = input_str_simple.replace(':', ' ').replace('/', ' ').replace('.', ' ').replace('?', ' ')
        input_str_simple = input_str_simple.replace('&', ' ')

    input_str_simple = re.sub(r'[^\x00-\x7F]+', ' ', input_str_simple)
    return input_str_simple


def get_instagram_profiles_by_searching_profile_description(profiles=None,
                                                            minimum_friends=1000,
                                                            hashtags=[],
                                                            mentions=[],
                                                            match_threshold=1):
    """
    Here we check hashtags or mentions in the profile description
    """
    from social_discovery.blog_discovery import queryset_iterator
    profiles = profiles.filter(friends_count__gte=minimum_friends).exclude(profile_description__isnull=True)
    profiles_smart = queryset_iterator(profiles)
    ids = set()
    key_distribution = {}
    for p in profiles_smart:
        profile_hashtags = p.get_hashtags()
        found_hashtags = list(set(hashtags).intersection(set(profile_hashtags)))
        if len(found_hashtags) >= match_threshold:
            ids.add(p.id)
            # keep some stats
            update_stats(p.username, found_hashtags, key_distribution)

    return profiles.filter(id__in=ids), key_distribution


def get_instagram_profiles_by_searching_api_biography(exact_keywords=None,
                                                      phrases=None,
                                                      minimum_friends=1000,
                                                      profiles=None,
                                                      special_characters=None,
                                                      domain_extensions=None,
                                                      check_captions=False,
                                                      caption_match_threshold=3):
    """
    This function checks the api_data['biography']
    """
    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.contentfiltering import find_all_urls
    # all profiles
    if not profiles:
        profiles = models.InstagramProfile.objects.all()

    if not special_characters:
        special_characters = []
    if not exact_keywords:
        exact_keywords = []
    if not phrases:
        phrases = []
    if not domain_extensions:
        domain_extensions = []



    profiles = profiles.filter(friends_count__gte=minimum_friends)
    profiles_smart = queryset_iterator(profiles)
    ids = set()
    key_distribution = {}
    for p in profiles_smart:
        external_url = None
        # first checking if the domain extensions provided exist in the external url
        if p.api_data and 'external_url' in p.api_data.keys() and p.api_data['external_url']:
            external_url = p.api_data['external_url'].lower().strip()
            for d in domain_extensions:
                # d could be '.in' So, we check if the url ends with '.in' or has '.in/' in the url
                if external_url.endswith(d) or (d+'/' in external_url):
                    ids.add(p.id)
                    # keep some stats
                    update_stats(p.username, d, key_distribution)

        # second, check if the keywords appear in the description or the external url field
        if p.api_data and 'biography' in p.api_data.keys() and p.api_data['biography']:
            biography = p.api_data['biography'] + (' ' + external_url if external_url else '')
            biography_simple = simplify(biography)
            biography_words = biography_simple.lower().split()
            # first check for exact matches
            for k in exact_keywords:
                if k.lower() in biography_words:
                    ids.add(p.id)
                    update_stats(p.username, k, key_distribution)

            # now check for phrases
            for k in phrases:
                if k.lower() in biography_simple.lower():
                    ids.add(p.id)
                    update_stats(p.username, k, key_distribution)

            # there might be urls inside the biography, so we should check the extensions here as well
            urls = find_all_urls(biography_simple)
            for d in domain_extensions:
                for u in urls:
                    if u.endswith(d) or (d+'/' in u):
                        ids.add(p.id)
                        update_stats(p.username, d, key_distribution)

            biography_encoded = biography.encode('utf-8')
            for c in special_characters:
                try:
                    if c in biography_encoded:
                        ids.add(p.id)
                        update_stats(p.username, c, key_distribution)
                except:
                    print("problem with profile %s" % p)
                    pass

        if check_captions:
            if p.api_data and 'media' in p.api_data.keys() and 'nodes' in p.api_data['media'].keys():
                nodes = p.api_data['media']['nodes']
                found_chars = []
                found_exact_keywords = []
                for n in nodes:
                    caption = n.get('caption', '')
                    caption_simple = simplify(caption)
                    caption_words = caption_simple.lower().split()
                    caption_encoded = caption.encode('utf-8')
                    # check if keywords are found in the captions
                    for k in exact_keywords:
                        if k.lower() in caption_words:
                            found_exact_keywords.append(k)

                    # check if special characters are found in the captions
                    for c in special_characters:
                        if c in caption_encoded:
                            found_chars.append(c)

                if len(found_chars) >= caption_match_threshold:
                    update_stats(p.username, found_chars, key_distribution)
                    ids.add(p.id)

                if len(found_exact_keywords) >= caption_match_threshold:
                    update_stats(p.username, 'caption_matched_%s' % ','.join(found_exact_keywords), key_distribution)

    return profiles.filter(id__in=ids), key_distribution


def check_language(input_charstr, region=None):
    import regex as rex
    if region == 'SEA':
        pattern = rex.compile(r'([\p{IsHan}\p{IsBopo}\p{IsHira}\p{IsKatakana}]+)', re.UNICODE)
        r = pattern.search(input_charstr)
        if r:
            return True
    return False


def get_instagram_profiles_by_checking_language(profiles=None,
                                                region='SEA',
                                                check_biography=True,
                                                check_captions=False,
                                                caption_match_threshold=3):
    """
    This function checks if the biography or captions contains any forieng langauge characters.
    """
    from social_discovery.blog_discovery import queryset_iterator
    # all profiles
    if not profiles:
        profiles = models.InstagramProfile.objects.all()

    # helper method to keep stats
    def update_stats(username, reason, distribution):
        if username in distribution.keys():
            j = distribution[username]
            j.append(reason)
        else:
            distribution[username] = [reason]

    # avoid looking at influencers that already have been found using location
    profiles = profiles.exclude(tags__contains='%s_LOCATION' % region)

    profiles_smart = queryset_iterator(profiles)
    ids = set()
    key_distribution = {}
    for p in profiles_smart:
        if check_biography:
            if p.api_data and 'biography' in p.api_data.keys() and p.api_data['biography']:
                biography = p.api_data['biography']
                if check_language(biography, region):
                    ids.add(p.id)
                    update_stats(p.username, 'found_in_biography', key_distribution)
        if check_captions:
            if p.api_data and 'media' in p.api_data.keys() and 'nodes' in p.api_data['media'].keys():
                nodes = p.api_data['media']['nodes']
                found_ctr = 0
                for n in nodes:
                    caption = n.get('caption', '')
                    if check_language(caption, region):
                        found_ctr += 1
                if found_ctr >= caption_match_threshold:
                    ids.add(p.id)
                    update_stats(p.username, 'found_in_captions_%d' % found_ctr, key_distribution)

    return profiles.filter(id__in=ids), key_distribution



def mark_profiles(profiles, marker):
    """
    Here, we mark Instagram profiles with some markers so that we don't have to discover them again
    """
    print("Starting marking profiles with marker '%s'" % marker)
    for p in profiles:
        tags = p.tags
        if tags:
            if not marker in tags:
                tags += ' ' + marker
        else:
            tags = marker
        p.tags = tags
        p.save()
    print("Done")


def remove_already_processed_profiles(qset):
    """
    we remove all profiles that have an associated influencer and it was processed with our new system.
    """
    import datetime
    d = datetime.date(2015, 11, 4)
    result = qset.exclude(discovered_influencer__date_created__gte=d)
    result = result.exclude(discovered_influencer__date_upgraded_to_show_on_search__gte=d)

    return result


def perform_asian_instagram_profiles(coll=None, friends_at_least_count=1000, friends_at_most_count=2000, to_upgrade=False):
    """
    We are only focusing on instagram profiles that we have already found an Influencer
    (discard the ones that already have show_on_search=True). then we limit them by number of their friends
    and keywords. After that we call AutomaticAttributeSelector() to fetch attributes and upgrade the Influencer.

    Needs an InfluencerGroup parameter, for example InfluencersGroup.objects.get(id=1473)

    :return:
    """
    from social_discovery.models import InstagramProfile
    from social_discovery.blog_discovery import (
        brand_keywords, influencer_keywords, influencer_phrases,
        locations_phrases, locations_keywords, domain_extensions,
    )

    if type(coll) != InfluencersGroup:
        log.error('Need an InfluencerGroup object')
        return None


    locs_kw = locations_keywords['singapore'] + locations_keywords['korea'] + locations_keywords['india'] +\
           locations_keywords['japan'] + locations_keywords['china'] + locations_keywords['indonesia'] + locations_keywords['cambodia'] + \
           locations_keywords['philippines'] + locations_keywords['thailand'] + locations_keywords['taiwan'] + \
           locations_keywords['hong kong'] + locations_keywords['malaysia'] + locations_keywords['vietnam']

    locs_phrases = locations_phrases['singapore'] + locations_phrases['korea'] + locations_phrases['india'] +\
           locations_phrases['japan'] + locations_phrases['china'] + locations_phrases['indonesia'] + locations_phrases['cambodia'] + \
           locations_phrases['philippines'] + locations_phrases['thailand'] + locations_phrases['taiwan'] + \
           locations_phrases['hong kong'] + locations_phrases['malaysia'] + locations_phrases['vietnam']


    domains = domain_extensions['singapore'] + domain_extensions['hong kong'] + domain_extensions['philippines'] + \
              domain_extensions['australia'] + domain_extensions['india'] + domain_extensions['japan'] + \
              domain_extensions['blogger_domains']

    # find all instagram profiles that have at least given number of followers and avoid those that have been QA-ed
    set_original = InstagramProfile.objects.filter(friends_count__gte=friends_at_least_count).exclude(discovered_influencer__validated_on__contains='info')
    set_original = set_original.filter(friends_count__lte=friends_at_most_count)
    set_original = set_original.exclude(tags__contains='SEA_LOCATION')

    # remove recently created profiles
    set_original = remove_already_processed_profiles(set_original)

    print("Total profiles that have not been qaed %d" % set_original.count())

    # first make sure they have location keywords
    set1, key_distribution = get_instagram_profiles_by_searching_api_biography(locs_kw, locs_phrases, 1000, set_original, [], domains)
    print("Found %d with asian locations" % set1.count())
    print("Key distribution: %s" % key_distribution)

    # now, we want to search for blogger keywords in these to find who are good ones
    have_influencer_keywords, distribution = get_instagram_profiles_by_searching_api_biography(influencer_keywords,
                                                                                               influencer_phrases,
                                                                                               1000,
                                                                                               set1)
    print("Found matching influencer keywords: %d" % have_influencer_keywords.count())
    print("Keyword distribution %s" % distribution)

    remaining_set1 = set1.exclude(pk__in=have_influencer_keywords)
    print("remaining : %d" % remaining_set1.count())

    # removing brands
    have_brand_keywords, brand_keyword_distribution = get_instagram_profiles_by_searching_api_biography([],
        brand_keywords,
        1000,
        remaining_set1)
    print("Found %d with brand keywords" % have_brand_keywords.count())
    print("Brand key distribution: %s" % brand_keyword_distribution)

    non_influencer_brand_keywords = remaining_set1.exclude(pk__in=have_brand_keywords)

    # first, mark the profiles with the marker
    ids = [r.id for r in have_influencer_keywords]

    mark_profiles(set1.filter(id__in=ids), 'SEA_LOCATION')

    return have_influencer_keywords, non_influencer_brand_keywords, have_brand_keywords, distribution, brand_keyword_distribution


    """

    matching_profiles = get_instagram_profiles_by_searching_captions(keywords=keywords,
                                                                     minimum_friends=friends_count,
                                                                     profiles=set1)

    print("Found %d matching profiles out of %d" % (matching_profiles.count(), set1.count()))

    ctr = 0
    for profile in matching_profiles:
        AutomaticAttributeSelector(influencer=profile.discovered_influencer, to_save=True)
        profile.discovered_influencer.set_profile_pic()

        influencer = profile.discovered_influencer
        if influencer.profile_pic_url is not None and to_upgrade:
            influencer.show_on_search = True
            influencer.date_upgraded_to_show_on_search = date.today()
            influencer.save()
            coll.add_influencer(influencer)

        ctr += 1
        if ctr % 1000 == 0:
            print("%s profiles performed..." % ctr)

    print("Performance finished, %s profiles performed total." % ctr)
    """


def handle_matched_profiles(matched_profiles):
    """
    The profiles passed to this method are the ones that passed a certain requirement. E.g., they are from south-east-asia.
    """
    from social_discovery.create_influencers import restore_influencers_urls, create_influencers_from_crawled_profiles
    from social_discovery.models import InstagramProfile

     # we first issue creation of influencers for the ones that don't have an influencer
    without_influencer = matched_profiles.filter(discovered_influencer__isnull=True)
    issue_influencer_creation_task(without_influencer)

    with_influencer = matched_profiles.filter(discovered_influencer__isnull=False)

    # divide the rest into two sets: one with artificial urls and one without
    with_artificial_influencers = with_influencer.filter(discovered_influencer__blog_url__contains='theshelf.com/artificial')
    with_artificial_influencers_ids = list(with_artificial_influencers.values_list('id', flat=True))

    without_artificial_influencers = with_influencer.exclude(pk__in=with_artificial_influencers)
    without_artificial_influencers_ids = list(without_artificial_influencers.values_list('id', flat=True))

    # so the profiles that have already associated an influencer, we want to make sure their *_urls are correctly set

    # simpler case is when we have an artificial url.
    conflicting_profile_ids = restore_influencers_urls(with_artificial_influencers_ids, to_save=True)
    qset = InstagramProfile.objects.filter(id__in=conflicting_profile_ids)
    # now issue a creation for these guys for an artifiical url
    create_influencers_from_crawled_profiles(qset, force_artificial=True)

    # now, profiles without artificial urls, we should be more careful with them
    # because we want us to manually double check the ones that are conflicting
    # so, first, find the conflicting ones (without doing a save)
    conflicting_profile_ids = restore_influencers_urls(without_artificial_influencers_ids, to_save=False)
    profiles = InstagramProfile.objects.filter(id__in=conflicting_profile_ids)
    # and mark these confliciting onces with a tag so that we can check them later on
    mark_profiles(profiles, 'CONFLICTING_INFLUENCER')

    # now, we let's remove these conflicting profile ids
    without_artificial_profile_ids = list(without_artificial_influencers.exclude(id__in=conflicting_profile_ids).values_list('id', flat=True))
    without_artificial_influencers_ids = list(without_artificial_influencers.exclude(id__in=conflicting_profile_ids).values_list('discovered_influencer__id', flat=True))
    infs = dmodels.Influencer.objects.filter(id__in=without_artificial_influencers_ids)
    # now disassociate
    for i in infs:
        i.blog_url = None
        i.show_on_search = None
        i.save()
        insta_profs = i.instagram_profile.all()
        insta_profs.update(discovered_influencer=None)

    # now re-issue influencer creation for these guys
    profiles = InstagramProfile.objects.filter(id__in=without_artificial_profile_ids)
    issue_influencer_creation_task(profiles)

    print("Done")



def issue_influencer_creation_task(profiles=None):
    """
    Issue blog_discovery tasks for these profiles.
    :return:
    """

    print("Handling %d matching profiles" % (profiles.count()))
    ctr = 0
    for profile in profiles:
        discover_blogs.apply_async([profile.id, None], queue='create_influencers_from_instagram')
        ctr += 1
        if ctr % 1000 == 0:
            print("%s profiles performed..." % ctr)

    print("Performance finished, %s profiles performed total." % ctr)


def fix_url_shorteners():
    """
    Asana: https://app.asana.com/0/42664940909123/61629948795037
    :return:
    """
    from social_discovery.models import InstagramProfile
    from debra.models import Influencer, Platform
    from social_discovery.create_influencers import create_influencers_from_crawled_profiles

    url_chunks = [
        'bitly.com/', 'bit.ly/', 'chictopia.com/',
        '//line.me/', '//dayre.me/', '500px.com', 'flickr.com'
    ]

    results = {}

    for url_chunk in url_chunks:

        print('Performing influencers for %s in their blog url' % url_chunk)

        influencers = Influencer.objects.filter(blog_url__contains=url_chunk).filter(instagram_profile__isnull=False)
        results[url_chunk] = {'found': influencers.count()}
        print('Found %s influencers having %s in their blog url' % (results[url_chunk].get('found'), url_chunk))

        insta_profiles_ids = []
        for inf in influencers:
            t = time.time()
            print('==========================')
            print('Performing influencer: %s' % inf.id)
            try:
                # getting the instagram profile, disconnecting influencer from it
                insta_profile = inf.instagram_profile.all()[0]
                print('Found InstagramProfile: %s' % insta_profile.id)
                insta_profile.discovered_influencer = None
                insta_profile.save()

                # Disabling influencer and all his platforms
                platforms = Platform.objects.filter(influencer=inf)
                print('Found platforms: %s' % platforms.count())
                print('Disabling platforms...')
                for platform in platforms:
                    print('Deleting platform: %s' % platform.id)
                    platform.url=None
                    platform.influencer=None
                    platform.url_not_found=None
                    platform.save()
                # platforms.update(url=None, influencer=None, url_not_found=None)

                print('Disabling influencer...')
                inf.blacklisted = True
                inf.show_on_search = False
                inf.save()

                # reissuing create_influencer (friends__gte=1000 by default)
                # create_influencers_from_crawled_profiles(InstagramProfile.objects.filter(id=insta_profile.id),
                #                                          minimum_followers=1000,
                #                                          to_save=True)

                insta_profiles_ids.append(insta_profile.id)

                print('Reissued create_influencer with id: %s' % insta_profile.id)

                if 'reissued' in results[url_chunk]:
                    results[url_chunk]['reissued'] += 1
                else:
                    results[url_chunk]['reissued'] = 1

            except IndexError:
                # No insta_profile found
                if 'without_profile' in results[url_chunk]:
                    results[url_chunk]['without_profile'] += 1
                else:
                    results[url_chunk]['without_profile'] = 1

            print('Influencer performed for %s seconds' % int(time.time() - t))

        if len(insta_profiles_ids) > 0:
            # reissuing create_influencer (friends__gte=1000 by default)
            print('Reissuing create_influencer for profiles: %s' % insta_profiles_ids)
            create_influencers_from_crawled_profiles(InstagramProfile.objects.filter(id__in=insta_profiles_ids),
                                                     minimum_followers=1000,
                                                     to_save=True)

    print('Done:')
    print(results)


def fetch_posts_for_profile(username):
    """
    Helper method to fetch post urls that are provided in the api_data field. This is useful to find
    captions of these posts, commentors, as well as mentions and hashtags.
    """
    profile = models.InstagramProfile.objects.get(username=username)

    posts = profile.get_posts()
    for p in posts:
        scrape_instagram_posts(p, None, None)
    print("Done")


def evaluate_if_good_for_spider_source(username):
    """
    This method evalues if a profile is a good source for spidering out to find more interesting influencers.
    """
    from social_discovery.blog_discovery import (
        hashtags, brand_keywords, locations_keywords, locations_phrases,
        domain_extensions,
    )

    profile = models.InstagramProfile.objects.get(username=username)

    all_commentors = []
    commentors = {}
    posts = profile.get_posts()

    for p in posts:
        r, c = scrape_instagram_posts(p, None, None)
        commentors[p] = c
        if c:
            all_commentors.extend(c)

    print("Total commentors:\t %d" % len(all_commentors))
    print("Unique commentors:\t %d" % len(set(all_commentors)))

    existing_comments_in_db = models.InstagramProfile.objects.filter(username__in=all_commentors)

    print("Existing commentors:\t %d, >1K:%d, with_tag %d" % (existing_comments_in_db.count(),
                                                              existing_comments_in_db.filter(friends_count__gte=1000).count(),
                                                              existing_comments_in_db.filter(tags__isnull=False).count()))

    # now fetch the remaining ones
    remaining = list(set(all_commentors) - set(list(existing_comments_in_db.values_list('username', flat=True))))
    print("Need to fetch info for %d profiles" % len(remaining))
    for r in remaining:
        create_pending_profile(r)

    existing_comments_in_db = models.InstagramProfile.objects.filter(username__in=all_commentors)
    print("After fetching, we have Existing commentors:\t %d" % existing_comments_in_db.count())

    profiles_with_1K = existing_comments_in_db.filter(friends_count__gte=1000)

    print("Out of %d profiles, %d have more than 1000 friends" % (existing_comments_in_db.count(), profiles_with_1K.count()))

    locs_kw = locations_keywords['singapore'] + locations_keywords['korea'] + locations_keywords['india'] +\
           locations_keywords['japan'] + locations_keywords['china'] + locations_keywords['indonesia'] + locations_keywords['cambodia'] + \
           locations_keywords['philippines'] + locations_keywords['thailand'] + locations_keywords['taiwan'] + \
           locations_keywords['hong kong'] + locations_keywords['malaysia'] + locations_keywords['vietnam']

    locs_phrases = locations_phrases['singapore'] + locations_phrases['korea'] + locations_phrases['india'] +\
           locations_phrases['japan'] + locations_phrases['china'] + locations_phrases['indonesia'] + locations_phrases['cambodia'] + \
           locations_phrases['philippines'] + locations_phrases['thailand'] + locations_phrases['taiwan'] + \
           locations_phrases['hong kong'] + locations_phrases['malaysia'] + locations_phrases['vietnam']

    domains = domain_extensions['singapore'] + domain_extensions['hong kong'] + domain_extensions['philippines'] + \
              domain_extensions['india'] + domain_extensions['japan'] + \
              domain_extensions['blogger_domains']

    brand, brand_distribution = get_instagram_profiles_by_searching_api_biography([], brand_keywords, 1000, profiles_with_1K)

    print("Found %d profiles with brand keywords" % brand.count())

    remaining_profiles = profiles_with_1K.exclude(pk__in=brand)

    sea_location, sea_location_distribution = get_instagram_profiles_by_searching_api_biography(locs_kw, locs_phrases, 1000, remaining_profiles, [], domains)

    print("Found %d profiles with SEA location" % sea_location.count())

    remaining_profiles = remaining_profiles.exclude(pk__in=sea_location)

    # now let's use hashtags to find relevant influencers by searching their profile_description
    htags = hashtags['singapore']
    htags.extend(hashtags['only_sea'])
    htags = [h.lower() for h in htags]

    sea_hashtags, sea_hastags_distribution = get_instagram_profiles_by_searching_profile_description(remaining_profiles, 1000, htags, [])
    print("Found additional %d profiles with SEA hashtags" % sea_hashtags.count())

    remaining_profiles = remaining_profiles.exclude(pk__in=sea_hashtags)

    # now let's use langague to detect more influencers from SEA region
    sea_language, sea_language_distribution = get_instagram_profiles_by_checking_language(remaining_profiles, 'SEA', True, True, 3)
    print("Found %d profiles with SEA language" % sea_language.count())

    all_sea = sea_hashtags | sea_location | sea_language
    print("Total SEA profiles found: %d" % all_sea.count())

    remaining_profiles = remaining_profiles.exclude(pk__in=sea_language)

    print("Remaining un-decided profiles: %d" % remaining_profiles.count())

    if remaining_profiles.count() > 0:

        no_profile_description = remaining_profiles.filter(profile_description__isnull=True)
        print("out of these, %d don't have anything in their profile description" % no_profile_description.count())

        print("So, we'll try to fetch their posts and get some hashtags")
        for r in remaining_profiles:
            urls = r.get_posts()
            for u in urls:
                try:
                    scrape_instagram_posts(u, None, None)
                except:
                    pass

        sea_hashtags, sea_hastags_distribution = get_instagram_profiles_by_searching_profile_description(remaining_profiles, 1000, htags, [])
        print("Found additional %d profiles with SEA hashtags" % sea_hashtags.count())

        remaining_profiles = remaining_profiles.exclude(pk__in=sea_hashtags)

        # now let's use langague to detect more influencers from SEA region
        sea_language, sea_language_distribution = get_instagram_profiles_by_checking_language(remaining_profiles, 'SEA', True, True, 3)
        print("Found additional %d profiles with SEA language" % sea_language.count())
        remaining_profiles = remaining_profiles.exclude(pk__in=sea_language)

    return remaining_profiles, all_sea, no_profile_description


@task(name="social_discovery.instagram_crawl.scrape_posts_from_api_for_profile", ignore_result=True)
def scrape_posts_from_api_for_profile(profile_id):
    """
    This function is safe from concurrency point of view. Meaning that we shouldn't be issuing fetching for all posts
    for a profile at the same time. Because it'll will be unclear which post will be the last one to overwrite
    every other posts's data.
    """
    profile = models.InstagramProfile.objects.get(id=profile_id)
    posts = profile.get_posts()
    for p in posts:
        try:
            print("Fetching post: %r" % p)
            scrape_instagram_posts(p, None, None)
        except:
            print("Problem with post: %r" % p)
            pass

    print("Done fetching all posts for %r" % profile)


def get_post_content_and_author_comments(post_url):
    """
    Extract the caption and all comments made by the post author

    :param post_url:  URL of the Instagram post to analyze
    :type post_url:  str
    :return: space separated caption and author's comments
    :rtype: str or unicode
    """
    r = requests.get(post_url, headers=utils.browser_headers())
    soup = BeautifulSoup(r.content)
    content = _extract_instagram_data(soup).get('PostPage')[0].get('media').get('caption', None)
    post_creator_id = _extract_instagram_data(soup).get('PostPage')[0].get('media').get('owner').get('id')
    comments = _extract_instagram_data(soup).get('PostPage')[0].get('media').get('comments').get('nodes')
    for comment in comments:
        comment_author = comment['user']['id']
        if post_creator_id == comment_author:
            comment_text = comment['text']
            if comment_text:
                content = '{0} {1}'.format(content, comment_text)
    return content


if __name__ == '__main__':
    from social_discovery.blog_discovery import hashtags, brand_keywords, influencer_keywords, influencer_phrases, locations_keywords, locations_phrases, domain_extensions
    sea_location = models.InstagramProfile.objects.filter(tags__contains='SEA_LOCATION')
    print("Got %d with SEA_LOCATION" % sea_location.count())
    have_influencer_keywords, distribution = get_instagram_profiles_by_searching_api_biography(influencer_keywords,
                                                                                               influencer_phrases,
                                                                                               1000,
                                                                                               sea_location)

    without_influencer = have_influencer_keywords.filter(discovered_influencer__isnull=True)
    print("Got %d without influencer " % without_influencer.count())
    for i,w in enumerate(without_influencer):
        discover_blogs(w.id, None, True)