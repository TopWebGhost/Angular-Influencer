"""
Here, we are implementing our spider algorithm (starting with Instagram)
"""

from celery.decorators import task

from debra.models import Platform, InfluencersGroup
from social_discovery.instagram_crawl import (
    scrape_instagram_posts, create_pending_profile,
)
from social_discovery.models import InstagramProfile

__author__ = 'atulsingh'


def find_platforms(platform_name='Instagram', influencers=None, how_many=None, min_followers=10000, max_followers=20000):
    """
    This function finds platforms for the given influencers.
    """

    plats = Platform.objects.filter(influencer__in=influencers, platform_name=platform_name).order_by('id')
    plats = plats.filter(num_followers__gte=min_followers)
    plats = plats.filter(num_followers__lte=max_followers)

    if how_many and plats.count() > how_many:
        plats = plats[:how_many]

    return plats


def issue_scraping_of_posts(platforms, minimum_comments_required=10, how_many=None):
    """
    This function goes through the posts of the given platforms and looks at minimum_comments_required
    condition to find posts and then issues a fetch task.

    When these posts are fetched, we'll get the hashtags, mentions, and commentors for these posts.
    This will then help us then iterate over these later on to find more interesting profiles to look at.
    """
    count = 0
    for i in platforms:
        if how_many and count >= how_many:
            print("Already issued %d posts, returning now" % count)
            return
        posts = i.posts_set.all()
        for p in posts:
            if p.postinteractions_set.count() >= minimum_comments_required:
                print("Ok, found a post that meets the requirements, issuing a fetch")
                count += 1
                scrape_instagram_posts.apply_async([p.url, None, None], queue='scrape_instagram_posts_new')
        print("So far we have %d urls" % count)


def start(how_many_platforms=None, minimum_comments_required=10, how_many_posts=None):
    """
    This is a driver function. It finds influencers and then issues the handling of scraping.
    """

    coll = InfluencersGroup.objects.get(name='Singapore Keywords')
    influencers = coll.influencers
    platforms = find_platforms(influencers=influencers, how_many=how_many_platforms)
    print("Platforms we're looking at: [Count=%d] %r" % (len(platforms), platforms))
    issue_scraping_of_posts(platforms, minimum_comments_required, how_many=how_many_posts)


@task(name="social_discovery.spider.check_and_create_profile", ignore_result=True)
def check_and_create_profile(username):
    profile = create_pending_profile(username, None, None)
    profile.append_tag('SPIDER')


def fetch_profiles_for_mentions_and_commentors():
    from django.db.models import Q

    coll = InfluencersGroup.objects.get(name='Singapore Keywords')
    influencers = coll.influencers
    insta = InstagramProfile.objects.filter(discovered_influencer__in=influencers)
    print("Found %d insta " % insta.count())
    # find profiles that have a commentor
    insta = insta.filter(Q(profile_description__contains='!*_') | Q(profile_description__contains='@'))
    mentions = []
    commentors = []
    for i in insta:
        m = i.get_mentions()
        c = i.get_commentors()
        mentions.extend(m)
        commentors.extend(c)
        print("So far we have mentions=%d, commentors=%d" % (len(set(mentions)), len(set(commentors))))

    mentions = set(mentions)
    commentors = set(commentors)

    # now we should check if these guys are already in our system
    already_exist_mentions_qset = InstagramProfile.objects.filter(username__in=mentions)
    already_exist_commentors_qset = InstagramProfile.objects.filter(username__in=commentors)

    print("Out of %d mentions, we alreayd have %d" % (len(mentions), already_exist_mentions_qset.count()))
    print("Out of %d commentors, we already have %d" % (len(commentors), already_exist_commentors_qset.count()))

    already_exist_commentors = list(already_exist_commentors_qset.values_list('username', flat=True))
    already_exist_mentions = list(already_exist_mentions_qset.values_list('username', flat=True))
    print("")
    already_exist_commentors.extend(already_exist_mentions)
    already_exists = set(already_exist_commentors)

    all_new_tags = mentions.union(commentors)
    remaining = all_new_tags.difference(already_exists)

    # now for the remaining tags, we'll issue create_pending_profile task that will fetch the description
    # and evaluate if it's a good profile. And if so, it adds a tag 'SPIDER' to the profile.
    for r in remaining:
        check_and_create_profile.apply_async([r], queue='scrape_instagram_posts_new')


def fetch_posts_for_profiles_from_captions(profile_qset=None, max_posts_fetched_per_profile=5):
    """
    This method looks at the api_data containing posts information to fetch data
    """
    print("Found %d eligible profiles that contain 'SPIDER' in tag and have empty profile_description" % profile_qset.count())
    for a in profile_qset:
        nodes = a.get_nodes_from_api()
        if not nodes:
            continue
        count = 0
        for n in nodes:
            code = n.get('code', None)
            if code and count < max_posts_fetched_per_profile:
                url = 'https://instagram.com/p/'+code
                scrape_instagram_posts.apply_async([url, None, None], queue='scrape_instagram_posts_new')
                count += 1


def fill_profiles_found_from_spidering():
    """
    These profiles do not potentially have hashtags or mentions because they were not found through some hashtag
    search. So, we should issue extraction for these profiles.
    """
    all_insta = InstagramProfile.objects.filter(tags='SPIDER')
    all_insta = all_insta.exclude(profile_description__isnull=False)
    all_insta = all_insta.filter(friends_count__gte=1000)

    fetch_posts_for_profiles_from_captions(all_insta)

