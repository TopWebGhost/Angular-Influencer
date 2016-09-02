from __future__ import print_function, unicode_literals

import logging
import sys
import time
from datetime import datetime
from urlparse import urlparse, urlunparse

import baker
import requests
from celery import task
from django.db.models import Q
from django.utils.encoding import smart_str
from lxml.html import fromstring
from requests.exceptions import Timeout, ConnectionError

from debra import helpers, admin_helpers
from debra.models import Influencer, Platform, PlatformDataOp
from models import InstagramProfile
from platformdatafetcher import platformextractor, fetchertasks, platformutils
from platformdatafetcher.influencerattributeselector import (
    AutomaticAttributeSelector,
)
from social_discovery.instagram_crawl import (
    get_instagram_profiles_by_category, create_platform_for_influencer,
    get_instagram_profiles_by_keywords,
)
from . import blog_discovery


__author__ = 'atulsingh'


"""
Here, we create influencers from profiles discovered via either followers of
our competitors on Twitter, Instagram or via crawling Instagram feeds or
mentions found in the content shared by influencers that we monitor.

If we find a social url (twitter or instagram) and it has one or more of the
following in their description:
   a) email + a keyword & no .com or url =>
        create influencr, default influencer blog url
   b) youtube url or instagram url + keyword =>
        create influencer, default influencer blog url
   c) blog url + keyword =>
        create influencer (already done directly in instagram_crawl or in
        twitter_crawl)
"""

log = logging.getLogger('social_discovery.create_influencer')

platforms_to_create = ['youtube']
email_clients = ['@gmail.com', '@yahoo.com', '@hotmail.com']

INSTAGRAM_URL = 'http://instagram.com/'
TWITTER_URL = 'http://twitter.com/'

type_to_domain = {'instagram': INSTAGRAM_URL, 'twitter': TWITTER_URL}

requests_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:40.0) Gecko/20100101 Firefox/40.0'}  # noqa


def find_matching_influencer_for_platform_url(url):
    """
    Helper method to find an influencer that has a link to the url in one of
    it's platform objects
    """
    found_infs = set()
    handle = platformutils.url_to_handle(url)

    # If we have handle as a bare domain name as social url or url shortener,
    # we should skip it
    if handle in [
        'facebook.com',
        'pinterest.com',
        'youtube.com',
        'instagram.com',
        'twitter.com',
        't.co',
    ]:
        log.info((
            'Generic social url domain found: %r, '
            'skipping search for matching influencers.'
        ), handle)
        return found_infs

    # TODO: when we define Platform unique fields, make filtering using them
    # instead of url__contans and chunks below
    possible_matched_platforms = Platform.objects.filter(
        url__contains=handle,
        influencer__source__isnull=False,
        influencer__blog_url__isnull=False
    ).exclude(url_not_found=True)
    log.info(
        'Platforms found for %r: %s', url, len(possible_matched_platforms)
    )
    for platform in possible_matched_platforms:
        platform_url = platform.url
        chunks = platform_url.split(handle)
        log.info('checking: \'%s\' vs \'%s\'', handle, platform_url)
        if len(chunks) > 0 and (
            len(chunks[-1]) == 0 or not chunks[-1][0].isalnum()
        ):
            log.info(
                "Platforms detected for this url [%s] [%s] %r %r", handle,
                platform_url, platform, platform.influencer
            )
            found_infs.add(platform.influencer)

    return found_infs


def find_matching_influencers_for_profile(instagram_profile, only_social=True):
    """
    This helper method finds the influencers for each of the social url present
    in this profile.
    For example, an InstagramProfile with username='atul' might contain a
    facebook url, say 'http://facebook.com/atul
    So, we have two social urls:
        a) http://instagram.com/atul
        b) http://facebook.com/atul
    Now, for each of the urls, we'll check if there already exists an
    Influencer that exists and contains a platform object that has the same url
    as (a) or (b).
    Ideally, there should be only one. But if there is more than one, these
    could be duplicates and we need to look into them.

    :param only_social: if True, we only look for social links. If false, we
                        look for non-social links only
    """
    platform_url = INSTAGRAM_URL + instagram_profile.username
    description = instagram_profile.combine_description_and_external_url()

    log.info("Checking [%s] [%s]", instagram_profile, description)
    try:
        if only_social:
            urls = blog_discovery.extract_all_social_links(description)
            urls += [platform_url]
        else:
            urls = blog_discovery.extract_non_social_links(description)
    except TypeError:
        urls = []

    all_found_infs = dict()
    valid_urls = set()
    for u in urls:
        # getting performed platform url, for example if we get url like
        # http://www.youtube.com/watch?v=gai4rlj7pfo
        # then we are fetching an url of the author of this video
        ppu = perform_platform_url(u)
        if not ppu:
            continue

        found_infs = find_matching_influencer_for_platform_url(ppu)
        if found_infs:
            all_found_infs[u] = found_infs

        valid_urls.add(ppu)

    return all_found_infs, valid_urls


def create_influencer_from_instagram(profile_id, to_save):
    profile = InstagramProfile.objects.get(id=profile_id)

    existing_infs, valid_urls = find_matching_influencers_for_profile(profile)
    # We don't handle the case when there're matching influencers
    if existing_infs:
        return False, existing_infs

    '''
    algorithm:
        1. Create an influencer with a fake blog url
        2. Then create a platform object for each of the platforms that we're
           able to discover
            - It could be a youtube or facebook or pinterest or twitter
                - Mark all these platforms as autovalidated
            - Use these platforms to discover other related platforms
                - These should be automatically validated also
            - Issue fetch tasks for these automatically validated platforms
        3. Extract email if given
    '''
    plats = []
    # creating a unique influencer blog url that is concurrency-safe
    blog_url = 'http://www.theshelf.com/artificial_blog/{}.html'.format(
        int(time.time())
    )
    inf = helpers.create_influencer_and_blog_platform(
        blog_url,
        influencer_source='discovered_via_instagram',
        to_save=to_save,
        platform_name_fallback=True
    )
    log.info('Influencer object %s created/fetched.', inf.id)

    if to_save:
        inf.save()
        _ = PlatformDataOp.objects.create(
            influencer=inf, operation='inf_articial_blog_from_instagram_crawl'
        )

    for valid_url in valid_urls:
        platform = create_platform_for_influencer(
            url=valid_url, inf=inf, profile=profile, to_save=to_save
        )
        if not platform:
            continue
        if to_save:
            field_name = Influencer.platform_name_to_field[
                platform.platform_name
            ]
            admin_helpers.handle_social_handle_updates(
                inf, field_name, platform.url
            )
        plats.append((platform, 'discovered_via_instagram',))

    log.debug('After performing all urls, insta_url is: %s', inf.insta_url)

    # now, using the created platforms, see if we can create new platforms
    platformextractor.do_further_validation_using_validated_platforms(
        plats, []
    )

    log.debug('After do_further_validation, insta_url is: %s', inf.insta_url)

    profile.discovered_influencer = inf
    if to_save:
        profile.valid_influencer = True
        profile.save()
        for platform, _ in plats:
            fetchertasks.fetch_platform_data.apply_async(
                [platform.id, ], queue='new_influencer'
            )

    log.debug('Finally Influencer has insta_url: %s', inf.insta_url)
    log.debug((
        'And finally, profile with id %s should have discovered influencer '
        'with id: %s (to_save is %s)'
    ), profile.id, inf.id, to_save)

    # Here we are fetching email, blogname, name, locations from platforms
    get_influencers_email_name_location_for_profile(
        profile_id, to_save=to_save
    )
    # TODO: links to other platforms using @ sign or just like (snapchat: blah)

    return True, inf


def create_influencers_from_crawled_profiles(
    qset, minimum_followers=1000, to_save=None, force_artificial=False
):
    """
    qset: query set passed
    minimum_followers: self-explanatory :-)
    keyword_list: list of keywords to check in profile.api_data['biography'] to
                  ensure they exist there
    """

    valid = qset.filter(friends_count__gte=minimum_followers)
    valid = valid.distinct('username')

    print("Now we have %d valid profiles to look into" % valid.count())
    count = 0
    results = {}
    for i, q in enumerate(valid):
        description = q.combine_description_and_external_url()

        print("Checking [%d] [%s] [%s]" % (i, q, description))
        try:
            urls = blog_discovery.extract_all_social_links(description)
        except TypeError:
            urls = []

        print("[%s] [%s] [%s]" % (i, description, urls))

        res, inf = create_influencer_from_instagram(q.id, to_save)
        if res:
            count += 1
        results[q.id] = inf
        print("[%d] [%d] " % (i, count))

    return results

def find_brand_instagram_profiles(qset):
    bad = InstagramProfile.objects.none()
    # first exclude instagram profiles with brand keywords
    for kw in blog_discovery.brand_keywords:
        k = qset.filter(profile_description__icontains=kw)
        bad |= k
    all_bad = list(bad.values_list('id', flat=True))
    return qset.filter(id__in=all_bad)


def find_valid_instagram_profiles(qset):
    """
    We're using the profile_description field to find potential candidates to create influencers
    and then during creation, we will check the api_data['biography'] to make sure they are the good ones.
    """
    # TODO: Eventually change search from description to search over json field profile.api_data.get('biography')

    valid = InstagramProfile.objects.none()
    bad = InstagramProfile.objects.none()

    # first exclude instagram profiles with brand keywords
    for kw in blog_discovery.brand_keywords:
        k = qset.filter(profile_description__icontains=kw)
        bad |= k

    all_bad = list(bad.values_list('id', flat=True))

    # now pick out only those instagram profiles that have good keywords
    for kw in blog_discovery.influencer_keywords:
        k = qset.filter(profile_description__icontains=kw)
        valid |= k

    all_valid = list(valid.values_list('id', flat=True))

    #return all those that found a valid influencer keyword or didn't find a valid brand keyword
    #return qset.filter(id__in=all_valid) | qset.exclude(id__in=all_bad)
    #TODO: we need to be conservative here in the beginning and exclude anyone with brand keywords for now
    return qset.filter(id__in=all_valid)#.exclude(id__in=all_bad)


def analyze_instagram_profiles(qset):
    # first is the one with only blogger keywords and no brand keywords
    qset_with_blogger_keywords = find_valid_instagram_profiles(qset)
    print("Total: %d" % qset.count())
    print("With blogger keywords: %d" % qset_with_blogger_keywords.count())
    # this is with only brand keywords
    qset_with_brand_keywords = find_brand_instagram_profiles(qset)
    print("With brand keywords: %d" % qset_with_brand_keywords.count())
    # and the rest, these are the interesting ones
    qset_non_brand_keywords = qset.exclude(pk__in=qset_with_brand_keywords).exclude(pk__in=qset_with_blogger_keywords)
    print("With neither blog or brand keywords: %d" % qset_non_brand_keywords.count())
    qset_non_brand_keywords_non_brand_urls = blog_discovery.find_profiles_with_non_branded_links(qset_non_brand_keywords)

    # now, among these qset_with_neither, find those that have either no
    # urls or only social urls. These are potentially good influencers.

    print("All:%d Blogger:%d Brand:%d NothingBrand: %d" % (qset.count(),
        qset_with_blogger_keywords.count(), qset_with_brand_keywords.count(), qset_non_brand_keywords_non_brand_urls.count()))

    return qset_with_brand_keywords, qset_with_blogger_keywords, qset_non_brand_keywords_non_brand_urls

def find_valid_influencers_with_instagram_profiles(qset):
    valid = Influencer.objects.none()
    bad = Influencer.objects.none()
    # first exclude instagram profiles with brand keywords
    for kw in blog_discovery.brand_keywords:
        k = qset.filter(instagram_profile__profile_description__icontains=kw)
        bad |= k

    all_bad = list(bad.values_list('id', flat=True))

    # now pick out only those instagram profiles that have good keywords
    for kw in blog_discovery.influencer_keywords:
        k = qset.filter(instagram_profile__profile_description__icontains=kw)
        valid |= k

    all_valid = list(valid.values_list('id', flat=True))

    #return all those that found a valid influencer keyword or didn't find a valid brand keyword
    #return qset.filter(id__in=all_valid) | qset.exclude(id__in=all_bad)
    #TODO: we need to be conservative now and just return those that had a valid keyword
    # and none of the brand keywords
    return qset.filter(id__in=all_valid)


def find_valid_influencers_with_social_profiles(qset):
    """
    This extends the function above that just looks in the description of Instagram profiles.
    """
    plats = qset.platforms().filter(platform_name__in=Platform.SOCIAL_PLATFORMS_CRAWLED).exclude(url_not_found=True)
    good = set()
    keywords = blog_discovery.influencer_keywords
    for p in plats:
        if p.description:
            for k in keywords:
                if k in p.description.lower():
                    good.add(p.influencer.id)
                    print(len(good))
                    break

    #return all those that found a valid influencer keyword or didn't find a valid brand keyword
    #return qset.filter(id__in=all_valid) | qset.exclude(id__in=all_bad)
    #TODO: we need to be conservative now and just return those that had a valid keyword
    # and none of the brand keywords
    return qset.filter(id__in=good)

def dump_keyword_and_corresponding_urls(brand=True):
    if brand:
        keywords = blog_discovery.brand_keywords
    else:
        keywords = blog_discovery.influencer_keywords
    filename = 'dump_keyword_and_corresponding_urls.csv'
    csvfile = open(filename, 'a+')
    kw_str = ';'.join(keywords)
    csvfile.write('%s\n' % kw_str)


    insta = InstagramProfile.objects.filter(profile_description__icontains='singapore')
    insta = insta.filter(friends_count__gte=500)
    insta_with_kw = {}
    max_length = 0
    for k in keywords:
        insta_with_kw[k] = list(insta.filter(profile_description__icontains=k).values_list('username', flat=True))
        print("%s %d" % (k, len(insta_with_kw[k])))
        if len(insta_with_kw[k]) > max_length:
            max_length = len(insta_with_kw[k])

    for k in range(0, max_length):
        vals = []
        for kw in keywords:
            if k < len(insta_with_kw[kw]):
                val = insta_with_kw[kw][k]
            else:
                val = ''
            vals.append(val)
        csvfile.write('%s\n' % ';'.join(vals))

    csvfile.close()


def perform_platform_url(url=None):
    """
    Function to substitute urls for particular platforms.
    * For Youtube.com it finds author of video if url has /watch?=.
    * For Facebook it substitutes mobile url for desktop one.
    * Url with 'accounts.google.com' as netloc is skipped and returned None
    :param url:
    :return:
    """
    if url is None:
        return url

    parsed_url = urlparse(url)

    # if we have an account.google.com link, then skip it
    if parsed_url.netloc.lower().endswith('accounts.google.com'):
        return None

    # changing url of mobile Facebook page to url of desktop Facebook page
    if parsed_url.netloc.lower() == "m.youtube.com":
        print('So, we have got a link to a mobile Youtube page: %s' % url)
        parsed_url = parsed_url._replace(netloc="youtube.com")
        url = urlunparse(parsed_url)
        print('Changing it to a desktop url: %s' % url)

    # getting url of the video's author on YouTube video
    if (parsed_url.netloc.lower().endswith('youtube.com') and parsed_url.path == '/watch') or parsed_url.netloc == 'youtu.be':
        print('So, we have got a link to a YouTube video: %s' % url)
        try:
            print('Lets find its author...')
            # getting video page
            resp = requests.get(url, timeout=10, headers=requests_headers)
            youtube_page = fromstring(resp.content)

            # getting author's username
            video_authors = youtube_page.xpath("//span[@itemprop='author']/link[@itemprop='url']/@href")
            if len(video_authors) > 0:
                print("Author's profile url is %s" % video_authors[0])
                return video_authors[0]
            else:
                print("Author can't be found and seems this video does not exist anymore.")
                return None
        except (Timeout, ConnectionError):
            pass

    # changing url of mobile Facebook page to url of desktop Facebook page
    if parsed_url.netloc.lower() == "m.facebook.com":
        print('So, we have got a link to a mobile Facebook page: %s' % url)
        parsed_url = parsed_url._replace(netloc="facebook.com")
        url = urlunparse(parsed_url)
        print('Changing it to a desktop url: %s' % url)
    return url


def test_create_new_influencers_by_category(category=None, top_profiles=100, minimum_friends=1000, to_save=False):

    f = open('../test_top_singapore_%s.txt' % datetime.strftime(datetime.utcnow(), '%Y-%m-%d_%H%M%S'), 'w')
    original = sys.stdout
    sys.stdout = Tee(sys.stdout, f)

    if category is None:
        print("No category was provided -- fetching just %s top InstagramProfiles..." % top_profiles)
    else:
        print("Fetching %s top InstagramProfiles for category '%s'..." % (top_profiles, category))

    singapore_profiles = get_instagram_profiles_by_category(category=category, minimum_friends=minimum_friends)
    sp_without_inf = singapore_profiles.filter(discovered_influencer__isnull=True)
    valid_profiles = find_valid_instagram_profiles(sp_without_inf)
    first_top = list(valid_profiles.order_by('-friends_count').values_list('id', flat=True)[:top_profiles])

    print('%s InstagramProfile ids of required %s have been fetched.' % (len(first_top), top_profiles))
    print(first_top)

    ctr = 0
    for pid in first_top:
        insta_profile = InstagramProfile.objects.filter(id=pid)
        ctr += 1
        if insta_profile.count() > 0:
            print("=================================================")
            print("%s. Performing Profile ID: %s   Username: %s" % (ctr,
                                                                    insta_profile[0].id,
                                                                    insta_profile[0].username))
            create_influencers_from_crawled_profiles(insta_profile,
                                                     to_save=to_save,
                                                     keyword_list=blog_discovery.influencer_keywords)

    sys.stdout = original
    f.close()


class Tee(object):
    """
    This will help us to log prints to files.
    """
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(smart_str(obj))
            f.flush()  # If you want the output to be visible immediately

    def flush(self):
        for f in self.files:
            f.flush()


def restore_influencers_urls(profiles_ids, to_save=False):
    """
    Here we take all new Influencers discovered via Instagram for 'singapore',
    check their platforms. And if platform occurs set its platform url to Influencer's corresponding *_url field
    :return:
    """
    from debra import admin_helpers
    print('Got %s profiles to check and correct...' % len(profiles_ids))

    profiles_with_conflicting_influencer = []

    def handle_field(inf, field_name, current_value, new_value):
        if current_value is None:
            print('Field %s is None, so restoring it to %s ... ' % (field_name, new_value))
        else:
            print('Field %s has a not empty value of %s, overwriting it with %s ' % (field_name, current_value, new_value))
        setattr(inf, field_name, new_value)


    for idx, pid in enumerate(profiles_ids):
        profile = InstagramProfile.objects.get(id=pid)
        print("===========================================")
        print("%s. Profile id %s %s" % (idx, profile.id, profile.username))
        inf = profile.discovered_influencer

        print("Influencer id %s and %s" % (inf.id, inf))
        print("Getting platforms... ")
        platforms = Platform.objects.filter(
            influencer=inf,
            autovalidated=True,
            platform_name__in=Platform.SOCIAL_PLATFORMS_CRAWLED
        ).exclude(
            url_not_found=True
        ).order_by("platform_name")

        print('This influencer has %s social crawled platforms: %s' % (platforms.count(), [pl.platform_name for pl in platforms]))

        platform_names = [pl.platform_name for pl in platforms]
        if not 'Instagram' in platform_names:
            current_value = getattr(inf, 'insta_url')
            handle_field(inf, 'insta_url', current_value, 'http://instagram.com/'+profile.username)
        conflict_found = False
        for pl in platforms:
            field_name = Influencer.platform_name_to_field.get(pl.platform_name)
            if field_name is not None:
                current_value = getattr(inf, field_name)
                handle_field(inf, field_name, current_value, pl.url)
                # check if there is a conflict => meaning that the influencer we connected this profile to has
                # another instagram url which is also validated. So, we need to look at these a bit more
                if field_name == 'insta_url' and current_value:
                    u1 = platformutils.url_to_handle(current_value.lower())
                    u2 = platformutils.url_to_handle(pl.url.lower())
                    if u1 != u2:
                        profiles_with_conflicting_influencer.append(pid)
                        conflict_found = True
            else:
                print('Platform %s does not have a separate url field, skipping it.' % pl.platform_name)

        if to_save and not conflict_found:
            print("Saving now")
            inf.save()
            admin_helpers.handle_social_handle_updates(inf, 'fb_url', inf.fb_url)
            admin_helpers.handle_social_handle_updates(inf, 'pin_url', inf.pin_url)
            admin_helpers.handle_social_handle_updates(inf, 'tw_url', inf.tw_url)
            admin_helpers.handle_social_handle_updates(inf, 'insta_url', inf.insta_url)
            admin_helpers.handle_social_handle_updates(inf, 'youtube_url', inf.youtube_url)

        if to_save and conflict_found:
            profile.discovered_influencer = None
            profile.save()

    return profiles_with_conflicting_influencer

def get_influencers_email_name_location_for_profile(profile_id, to_save=False):
    profile = InstagramProfile.objects.get(id=profile_id)
    print("===========================================")

    inf = profile.discovered_influencer
    # print('Influencer id: %s' % inf.id)

    if inf is not None:
        platforms = Platform.objects.filter(influencer=inf, platform_name='Instagram')
        print('Instagram platforms qty: %s' % platforms.count())

        print("STARTING values:")
        print("Influencer :  *Name: %s  *Demographics_location: %s  *Email_for_advertising_and_collaborations: %s  *validated_on: %s  *Description: %s " % (
            inf.name, inf.demographics_location, inf.email_for_advertising_or_collaborations, inf.validated_on, inf.description
        ))
        print("Profile :  *api_data.get('full_name'): %s" % profile.api_data.get('full_name'))
        if platforms.count() > 0:
            platforms = list(platforms)
            platform = platforms[0]
            print("Platform :  *platform_name: %s  *name: %s  *profile_img_url: %s" % (
                platform.platform_name,
                platform.influencer_attributes.get('name', '<not_exists>'),
                platform.profile_img_url
            ))

            platform = create_platform_for_influencer(
                url=platform.url, inf=inf, profile=profile, platform=platform,
                to_save=to_save
            )

            AutomaticAttributeSelector(influencer=inf, to_save=to_save)

            print("AFTER values:")
            print("Influencer :  *Name: %s  *Demographics_location: %s  *Email_for_advertising_and_collaborations: %s  *validated_on: %s  *Description: %s " % (
                inf.name, inf.demographics_location, inf.email_for_advertising_or_collaborations, inf.validated_on, inf.description
            ))
            print("Profile :  *api_data.get('full_name'): %s" % profile.api_data.get('full_name'))
            print("Platform :  *platform_name: %s  *name: %s  *profile_img_url: %s" % (
                platform.platform_name,
                platform.influencer_attributes.get('name', '<not_exists>'),
                platform.profile_img_url
            ))

        else:
            print ("* NO Instargam platforms detected for this Influencer.")

    else:
        print ("* NO discovered influencer for InstagramProfile with id %s" % profile_id)

def get_influencers_email_name_location(category=None, to_save=False):
    singapore_profiles = get_instagram_profiles_by_category(category)
    sp_with_inf = singapore_profiles.filter(discovered_influencer__isnull=False)
    sp_with_inf = sp_with_inf.filter(discovered_influencer__blog_url__startswith="http://www.theshelf.com/artificial_blog/")
    # remove influencers that QA has already gone through
    sp_with_inf = sp_with_inf.exclude(discovered_influencer__validated_on__contains='info').exclude(discovered_influencer__validated_on__contains='self')
    # remove influencers who we already found a name
    sp_with_inf = sp_with_inf.exclude(discovered_influencer__name__isnull=False)
    profiles_ids = list(sp_with_inf.order_by('-friends_count').values_list('id', flat=True))

    print('Got %s profiles to check and correct...' % len(profiles_ids))

    name_ctr = 0
    email_ctr = 0
    loc_ctr = 0

    for idx, pid in enumerate(profiles_ids, start=1):
        print("%s. Profile id %s" % (idx, pid))
        get_influencers_email_name_location_for_profile(pid, to_save)

    print ('Results: %s / %s / %s' % (name_ctr, email_ctr, loc_ctr))


def upgrade_influencers_to_search(qset):
    """
    Here, we simply upgrade influencers.
    Assumes that we have the profile_pic_url set as well as the name
    """
    for i, q in enumerate(qset):
        print("%d" % i)
        inf = q.discovered_influencer
        inf.date_upgraded_to_show_on_search = datetime.today()
        if 'theshelf.com/artificial' in inf.blog_url:
            # reset the blogname from "Unusual Traffic Detected"
            inf.blogname = None
        inf.show_on_search = True
        inf.save()


def upgrade_artificial_blogs(keywords=None):
    profiles = get_instagram_profiles_by_keywords(keywords, minimum_friends=500)
    brand_profiles = profiles.filter(reduce(lambda x, y: x | y, [Q(profile_description__icontains=keyword) for keyword in blog_discovery.brand_keywords]))
    print("Total profiles: %d  Removing brand profiles: %d" % (profiles.count(), brand_profiles.count()))
    sp_with_inf = profiles.exclude(pk__in=brand_profiles)
    sp_with_inf = sp_with_inf.filter(discovered_influencer__blog_url__startswith="http://www.theshelf.com/artificial_blog/")
    print("Profiles with a discovered influencer with fake blog: %d" % sp_with_inf.count())
    # remove influencers that QA has already gone through
    sp_with_inf = sp_with_inf.exclude(discovered_influencer__validated_on__contains='info').exclude(discovered_influencer__validated_on__contains='self')
    sp_with_inf_on_search_already = sp_with_inf.filter(discovered_influencer__show_on_search=True)
    print("Already showing on search %d" % sp_with_inf_on_search_already.count())
    sp_with_inf = sp_with_inf.exclude(pk__in=sp_with_inf_on_search_already)

    sp_with_inf_with_pics = sp_with_inf.filter(discovered_influencer__profile_pic_url__isnull=False)
    print("Out of %d profiles, we only have %d with profile pics" % (sp_with_inf.count(), sp_with_inf_with_pics.count()))
    upgrade_influencers_to_search(sp_with_inf_with_pics)


def upgrade_valid_blogs(keywords=None, minimum_friends=1000):
    profiles = get_instagram_profiles_by_keywords(keywords, minimum_friends=minimum_friends)
    brand_profiles = profiles.filter(reduce(lambda x, y: x | y, [Q(profile_description__icontains=keyword) for keyword in blog_discovery.brand_keywords]))
    print("Total profiles: %d  Removing brand profiles: %d" % (profiles.count(), brand_profiles.count()))
    sp_with_inf = profiles.exclude(pk__in=brand_profiles)
    sp_with_inf = sp_with_inf.exclude(discovered_influencer__blog_url__startswith="http://www.theshelf.com/artificial_blog/")
    print("Profiles with a discovered influencer with fake blog: %d" % sp_with_inf.count())
    # remove influencers that QA has already gone through
    sp_with_inf = sp_with_inf.exclude(discovered_influencer__validated_on__contains='info').exclude(discovered_influencer__validated_on__contains='self')

    sp_with_inf_on_search = sp_with_inf.filter(discovered_influencer__show_on_search=True)
    print("Already on search=%d" % sp_with_inf_on_search.count())

    sp_with_inf = sp_with_inf.exclude(pk__in=sp_with_inf_on_search)

    # ok, these remaining influencers, we need more quality control
    # 1. they must have a valid blog
    # 2. they must be in our verticals
    # 3. (may be we need to fetch their instagram posts and get the hashtags they use?)

    sp_with_inf_with_pics = sp_with_inf.filter(discovered_influencer__profile_pic_url__isnull=False)
    print("Out of %d profiles, we only have %d with profile pics" % (sp_with_inf.count(), sp_with_inf_with_pics.count()))

    # large number of these don't have an instagram url, that means we're probably overwriting it somewhere?
    # and these platforms should be fetched..
    #upgrade_influencers_to_search(sp_with_inf_with_pics)



def process_influencers_from_instagram_profiles(category=None):
    """
    Creating Influencers using potentially good InstagramProfiles

    https://app.asana.com/0/42664940909123/60096699386181

    :return:
    """
    if category is None:
        return

    t = time.time()
    # getting InstagramProfiles...
    insta_profiles = InstagramProfile.objects.all()

    # ...without discovered_influencer
    insta_profiles = insta_profiles.filter(discovered_influencer__is_null=True)

    # ...which are good for influencer keywords
    insta_profiles = insta_profiles.filter(reduce(lambda x, y: x | y, [Q(profile_description__icontains=keyword) for keyword in blog_discovery.influencer_keywords]))

    # ...and not have any of brands keywords
    insta_profiles = insta_profiles.exclude(reduce(lambda x, y: x | y, [Q(profile_description__icontains=keyword) for keyword in blog_discovery.brand_keywords]))
    print('Good influencers fetched: %s' % (time.time() - t))

    # 478757 InstagramProfiles so far

    groups = [100000, 50000, 25000, 10000, 5000, 2000, 1000]
    for group in groups:
        group_profiles = insta_profiles.filter(minimum_friends=group)

        print('Number of Influencers having %s friends ' % group_profiles.count())

        # TODO: temporarily disabled
        # for profile in group_profiles:
        #
        #     discover_blogs(profile, category=category)


def another_issue(to_save=False):
    """
    Asana: https://app.asana.com/0/42664940909123/60096699386183
    :return:
    """

    # Influencer profiles that don't have an artificial url and are from InstagramProfile but haven't been QA-ed yet (validated_on doesn't contain 'info' or 'self'):
    infs = Influencer.objects.filter(source__contains='discovered_via_instagram').exclude(validated_on__contains='info').exclude(validated_on__contains='self').exclude(blog_url__startswith='http://www.theshelf.com/artificial_blog')
    # 172103

    # check how many satisfy the singapore requirements
    keywords = blog_discovery.hashtags['singapore']
    singapore_infs = infs.filter(reduce(lambda x, y: x | y, [Q(instagram_profile__profile_description__icontains=keyword) for keyword in keywords]))
    print('Satisfy singapore keywords: %s' % singapore_infs.count())

    # check how many of these have an 'insta_url' => they all should have one, right?
    singapore_infs_with_insta_url = singapore_infs.filter(insta_url__isnull=False)
    print('Satisfy singapore keywords with insta_url: %s' % singapore_infs_with_insta_url.count())

    # have we discovered social urls for these?
    with_other_urls = singapore_infs_with_insta_url.filter(Q(fb_url__isnull=False)
                                                           | Q(pin_url__isnull=False)
                                                           | Q(tw_url__isnull=False)
                                                           | Q(youtube_url__isnull=False)
                                                           | Q(bloglovin_url__isnull=False))

    print('Finally, influencers: %s' % with_other_urls.count())

    # # run name, email detection for these
    # for inf in with_other_urls:
    #     profiles_ids = inf.instagram_profile.all().values_list('id', flet=True)
    #     if len(profiles_ids) > 0:
    #         get_influencers_email_name_location_for_profile(profiles_ids[0], to_save=True)


@baker.command
def test(tag, to_save):
    insta_with_tag = InstagramProfile.objects.filter(profile_description__icontains=tag)
    insta_with_tag = insta_with_tag.filter(discovered_influencer__isnull=True)
    print("Found %d influencers with tag %r" % (insta_with_tag.count(), tag))
    brand, bloggers, others = analyze_instagram_profiles(insta_with_tag)
    create_influencers_from_crawled_profiles(others, minimum_followers=1000, to_save=to_save)

if __name__ == '__main__':
    from xpathscraper import utils
    utils.log_to_stderr()
    baker.run()
