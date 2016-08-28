# -*- coding: utf-8 -*-
"""
Fabio's test project
Please ignore it
"""
import datetime

from platformdatafetcher.pbfetcher import DefaultPolicy
from platformdatafetcher.blogspotfetcher import BlogspotFetcher
from platformdatafetcher import estimation
from debra.models import BlogUrlsRaw, Platform, Influencer, Posts


def prepare_rawblogurl(raw_blog):
    """
    :param raw_blog: a `debra.models.BlogUrlsRaw` instance

    Check wether an influencer exist with that blog_url. If there's no influencer it creates one.
    Then get or creates a blog platform and mark the platform as INVESTIGATING.
    """
    duplicate_infs = Influencer.find_duplicates(blog_url=raw_blog.blog_url)

    if duplicate_infs:
        inf = duplicate_infs[0]
        inf.handle_duplicates()
    else:
        inf = Influencer.objects.create(source='lookbook', blog_url=raw_blog.blog_url)
    print raw_blog.site_url
    # lookbook_plat = Platform.objects.get_or_create(url=raw_blog.blog_url, platform_name="lookbook", influencer=inf) # why?

    if 'wordpress' in raw_blog.blog_url.lower():
        platform_name = 'Wordpress'
    elif 'blogspot' in raw_blog.blog_url.lower():
        platform_name = 'Blogspot'
    else:
        platform_name = 'Custom'

    blog_platform, created = Platform.objects.get_or_create(url=raw_blog.blog_url, platform_name=platform_name, influencer=inf)
    blog_platform.platform_state = "INVESTIGATING"
    blog_platform.save()

    determine_platform_state(blog_platform)


def determine_platform_state(blog_platform):
    """
    :param blog_platform: a `debra.models.Platform` instance that represents a blog

    Fetch and analyze the latest posts, then set the platform_state flag accordingly.
    """
    bs_fetcher = BlogspotFetcher(blog_platform, None)
    bs_fetcher.fetch_posts(1)

    if estimation.get_relevant_to_fashion_estimator().estimate(blog_platform.influencer.id):
        three_months_ago = datetime.date.today() - datetime.timedelta(3*30)  # banker months (30 days each)
        recent_posts = Posts.objects.filter(platform=blog_platform, create_date__gt=three_months_ago)
        if recent_posts:
            blog_platform.platform_state = Platform.PLATFORM_STATE_ACTIVELY_BLOGGING
        else:
            blog_platform.platform_state = Platform.PLATFORM_STATE_NOT_ACTIVELY_BLOGGING
    else:
        blog_platform.platform_state = Platform.PLATFORM_STATE_NOT_FASHION
    blog_platform.save()


def blog_discoverer(queryset_parameters):
    """
    Add new blogs to the database
    """
    raw_blogs = BlogUrlsRaw.objects.filter(**queryset_parameters)
    for raw_blog in raw_blogs:
        prepare_rawblogurl(raw_blog)


if __name__ == "__main__":
    blog_discoverer({'source__icontains':'lookbook.nu', 'blog_url__icontains':'blogspot'})
