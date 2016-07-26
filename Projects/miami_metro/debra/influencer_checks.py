from __future__ import absolute_import, division, print_function, unicode_literals
from celery.decorators import task
import logging
from debra import models, admin_helpers, constants
from django.core.mail import mail_admins
from django.db.models import Q
import datetime
from masuka.image_manipulator import save_social_images_to_s3
from platformdatafetcher import feeds, platformutils, fetcher, socialfetcher, pbfetcher, fetchertasks, suspicions
from xpathscraper import utils, xutils
import time
import requests
from masuka import image_manipulator
from django.core.cache import get_cache
from logging.handlers import RotatingFileHandler

log = logging.getLogger('debra.influencer_checks')


@task(name='debra.influencer_checks.verify_show_on_search', ignore_result=True)
def verify_show_on_search():
    log.info('Verifying all validated influencers show on search...')
    # first find all UserProfiles that have blog_verified and that have signed up
    # at least 3 days ago (to give enough time to QA to work on them)
    tod = datetime.date.today()
    delay = datetime.timedelta(days=3)
    verified_profiles = models.UserProfile.objects.filter(blog_verified=True, user__date_joined__lte=tod-delay)
    has_influencer = verified_profiles.filter(influencer__isnull=False)
    not_blacklisted = has_influencer.exclude(influencer__blacklisted=True)
    validated_influencer = not_blacklisted.filter(
        influencer__validated_on__icontains='info')
    not_on_search = validated_influencer.exclude(influencer__show_on_search=True)

    influencers = [profile.influencer for profile in not_on_search.select_related('influencer')]
    message_lines = ['{} ({}) - {}'.format(influencer.name, influencer.pk, influencer.blog_url)
                     for influencer in influencers]
    if message_lines:
        message = '''
Detected influencers that have been validated, but do not show on search.

Full list:

{}
'''.format('\n'.join(message_lines))

        log.info(message)
        mail_admins('Validated influencers not showing on search', message)


@task(name='debra.influencer_checks.save_profile_pics_to_s3', ignore_result=True)
def save_profile_pics_to_s3():
    log.info('''Checking that all influencers have their profile pics
        saved to S3...''')
    s3_url_prefix = 'https://s3.amazonaws.com'
    influencers = models.Influencer.objects.exclude(
        Q(profile_pic_url__isnull=True) | \
        Q(profile_pic_url__startswith=s3_url_prefix)
    ).prefetch_related('platform_set')

    for inf in influencers:
        log.info(inf.id)
        for platform in inf.platform_set.all():
            if platform.url_not_found:
                continue
            if platform.profile_img_url and \
            not platform.profile_img_url.startswith(s3_url_prefix):
                save_social_images_to_s3(platform)
        inf.set_profile_pic()
        log.info('...OK')

    inf_ids = map(lambda x: x.id, influencers)
    message = '''Detected influencers having their profile pics not
     being saved to S3.

     Full list:

     {}'''.format(inf_ids)
    log.info(message)
    mail_admins('Influencers with profile/cover pics saved to S3.', message)


def check_flow_of_influencers(created_since=None):
    """
    We want to check how influencers are flowing through our system.
    a) Discovered
    b) posts crawled
    c) categorized
    d) platforms extracted
    e) QA worked
    f) ready for upgrade
    """
    infs = models.Influencer.objects.filter(blog_url__isnull=False).exclude(show_on_search=True)
    msg = ''
    if created_since:
        msg += 'Looking at Influencers that are created since %s\n\n' % created_since
        infs = infs.filter(date_created__gte=created_since)
    infs_blacklisted = infs.filter(blacklisted=True)
    infs_non_blacklisted = infs.exclude(blacklisted=True)
    infs_social_manual = infs.manual_or_from_social_contains()
    just_discovered = infs_non_blacklisted.stage_just_discovered()
    post_crawled = infs_non_blacklisted.stage_posts_crawled()
    categorized = infs_non_blacklisted.stage_influencer_categorized()
    platform_extracted = infs_non_blacklisted.stage_platforms_extracted()
    ready_for_qa = infs_non_blacklisted.stage_ready_for_qa()
    qaed = infs_non_blacklisted.stage_qaed()

    msg += 'Total Influencers: [%d]\n' % infs.count()
    print(msg)
    msg += 'Blacklisted: [%d]\n' % infs_blacklisted.count()
    print(msg)
    msg += 'Non-blacklisted: [%d]\n' % infs_non_blacklisted.count()
    print(msg)
    msg += '\tSocial/Manual Source: [%d]\n' % infs_social_manual.count()
    print(msg)
    msg += '\tJust Discovered: [%d]\n' % just_discovered.count()
    print(msg)
    msg += '\tPosts Crawled: [%d]\n' % post_crawled.count()
    print(msg)
    msg += '\tCategorized: [%d]\n' % categorized.count()
    print(msg)
    msg += '\tPlatforms Extracted: [%d]\n' % platform_extracted.count()
    print(msg)
    msg += '\tReady for QA: [%d]\n' % ready_for_qa.count()
    print(msg)
    msg += '\tQA-ED: [%d]' % qaed.count()

    print(msg)
    tod = datetime.date.today()
    mail_admins('Processing of influencers %s' % tod, msg)


@task(name='debra.influencer_checks.check_import_categorization_tasks', ignore_result=True)
def check_import_categorization_tasks():
    """
    Counts the # of import tasks & categorization finished in the last week.
    """
    tod = datetime.date.today()
    last_week = tod - datetime.timedelta(days=7)
    one = datetime.timedelta(days=1)

    posts = models.Posts.objects.filter(create_date__gte=last_week)

    msg = ''
    start = last_week
    while start < tod:
        next = start + one
        pp = posts.filter(create_date__gte=start).filter(create_date__lte=next)
        posts_in_search = pp.filter(show_on_search=True)
        posts_new = pp.exclude(show_on_search=True)
        posts_in_search_imported = posts_in_search.filter(products_import_completed=True)
        posts_in_search_categorized = posts_in_search.filter(categorization_complete=True)
        posts_new_categorized = posts_new.filter(categorization_complete=True)
        posts_new_imported = posts_new.filter(products_import_completed=True)

        start = next

        msg += '[%s] Total: %d\n' % (start, pp.count())
        msg += '\t Search: %d\t Categorized: %d\t Imported: %d\n' % (posts_in_search.count(),
                                                                     posts_in_search_categorized.count(),
                                                                     posts_in_search_imported.count())
        msg += '\t New: %d\t Categorized: %d\t Imported: %d\n' % (posts_new.count(),
                                                                  posts_new_categorized.count(),
                                                                  posts_new_imported.count())


    mail_admins('Import/Categorization stats from week of (%s-%s)' % (last_week, tod), msg)


@task(name='debra.influencer_checks.check_crawling_tasks', ignore_result=True)
def check_crawling_tasks():
    """
    Here, we check what fraction of influencers.show_on_search are getting crawled every week.
    """

    ### NEED TO OPTIMIZE THIS FUNCTION --- it runs for entire day
    return
    crawled_platform_names = models.Platform.SOCIAL_PLATFORMS_CRAWLED + models.Platform.BLOG_PLATFORMS
    tod = datetime.date.today()
    last_week = tod - datetime.timedelta(days=7)

    ops = models.PlatformDataOp.objects.filter(started__gte=last_week)

    infs = models.Influencer.objects.all().searchable()

    plats = models.Platform.objects.filter(influencer__in=infs).exclude(url_not_found=True)

    infs_count = infs.count()
    plats_count = plats.count()
    log.info("We have %d influencers and %d platforms" % (infs_count, plats_count))
    msg = ''


    for pname in crawled_platform_names:
        log.info("Checking %s" % pname)
        plats_pname = plats.filter(platform_name=pname)
        plats_crawl_started = ops.filter(platform__in=plats_pname, operation='fetch_data').distinct('platform')
        plats_crawl_failed = plats_crawl_started.filter(error_msg__isnull=False)
        plats_crawl_succeeded = plats_crawl_started.filter(error_msg__isnull=True)
        plats_crawl_started_ids = plats_crawl_started.values_list('platform__id', flat=True)
        plats_crawl_failed_ids = plats_crawl_failed.values_list('platform__id', flat=True)
        plats_crawl_succeeded_ids = plats_crawl_succeeded.values_list('platform__id', flat=True)

        infs_pname = plats_pname.values_list('influencer', flat=True)
        infs_crawl_started = models.Platform.objects.filter(id__in=plats_crawl_started_ids).values_list('influencer', flat=True)
        infs_crawl_failed = models.Platform.objects.filter(id__in=plats_crawl_failed_ids).values_list('influencer', flat=True)
        infs_crawl_succeeded = models.Platform.objects.filter(id__in=plats_crawl_succeeded_ids).values_list('influencer', flat=True)

        plats_pname_count = plats_pname.count()
        plats_crawl_started_count = plats_crawl_started.count()
        plats_crawl_failed_count = plats_crawl_failed.count()
        plats_crawl_succeeded_count = plats_crawl_succeeded.count()

        success_ratio_plat = plats_crawl_succeeded_count * 100.0 / plats_pname_count

        infs_pname_count = infs_pname.count()
        infs_crawl_started_count = infs_crawl_started.count()
        infs_crawl_failed_count = infs_crawl_failed.count()
        infs_crawl_succeeded_count = infs_crawl_succeeded.count()

        success_ratio_inf = infs_crawl_succeeded_count * 100.0 / infs_pname_count

        msg += "[%s] Total Platforms: %d # crawled: %d  # failed: %d # succeeded: %d success : %.2f" % (pname,
                                                                                                           plats_pname_count,
                                                                                                           plats_crawl_started_count,
                                                                                                           plats_crawl_failed_count,
                                                                                                           plats_crawl_succeeded_count,
                                                                                                           success_ratio_plat)
        msg += "\n"

        msg += "[%s] Total Influencer: %d # crawled: %d  # crawl failed: %d # succeeded: %d success : %.2f" % (pname,
                                                                                                                  infs_pname_count,
                                                                                                                  infs_crawl_started_count,
                                                                                                                  infs_crawl_failed_count,
                                                                                                                  infs_crawl_succeeded_count,
                                                                                                                  success_ratio_inf)
        msg += "\n"

    denorm_tasks_started = ops.filter(influencer__in=infs, operation='denormalize_influencer').distinct('influencer')
    denorm_tasks_failed = denorm_tasks_started.filter(error_msg__isnull=False)
    denorm_tasks_succeded = denorm_tasks_started.filter(error_msg__isnull=True)
    denorm_tasks_success_ratio = denorm_tasks_succeded.count() * 100.0 / infs_count

    msg += "[Denormalize] Total influencers: %d Total started: %d  Total failed: %d Total succeeded: %d success: %.2f" % (infs_count,
                                                                                                             denorm_tasks_started.count(),
                                                                                                             denorm_tasks_failed.count(),
                                                                                                             denorm_tasks_succeded.count(),
                                                                                                             denorm_tasks_success_ratio)

    mail_admins('Crawling success stats from week of (%s-%s)' % (last_week, tod), msg)


def check_social_handle_validity():
    """
    Here, we check each not_url_found social handle and see if has at least a single post that contains a reference
    back to the blog_url of the influencer
    """
    import datetime
    from xpathscraper import utils
    from platformdatafetcher import platformextractor

    infs = models.Influencer.objects.all().searchable()
    plats = models.Platform.objects.filter(influencer__in=infs, platform_name__in=models.Platform.SOCIAL_PLATFORMS_CRAWLED)
    plats = plats.exclude(url_not_found=True)

    since = datetime.date(2015, 1, 1)
    posts = models.Posts.objects.filter(platform__in=plats, create_date__gte=since)

    valid = set()
    suspicious = set()

    for i in infs:
        log.info("checking %s" % i)
        # avoid platforms that are already autovalidated
        pl = plats.filter(influencer=i).exclude(autovalidated=True)
        blog_domain = utils.domain_from_url(i.blog_url)
        for p in pl:
            log.info("checking %s" % p)
            if p.description and blog_domain.lower() in p.description.lower():
                log.info("validated in description")
                valid.add(p)
                continue
            reason = platformextractor.validate_platform(i.blog_platform, p)
            if i.blog_platform and reason:
                log.info("validated by platformextractor.validate_platform method")
                valid.add(p)
                # save this in the platform
                p.autovalidated = True
                p.autovalidated_reason = reason
                p.save()
                continue

            po = posts.filter(platform=p)
            if po.filter(content__icontains=blog_domain).exists():
                valid.add(p)
            else:
                suspicious.add(p)
        log.info("So far: valid: %d  suspicious: %d" % (len(valid), len(suspicious)))


def check_posts_count(detect_feeds=False, set_alternate_fetcher=False):
    """
    Here, we check for influencers that have 0 in their posts_count. This makes our front-end show nothing
    for their blog stats.

    There could be multiple reasons behind this.
    a) Blog platform is null
    b) Non-null Blog platform has posts but we didn't run denormalization yet.
    """
    infs = models.Influencer.objects.all().searchable()
    no_posts = infs.filter(posts_count=0)
    msg = ''
    msg += "We have %d influencers with 0 posts_count" % no_posts.count()
    plats = models.Platform.objects.filter(influencer__in=no_posts, platform_name__in=models.Platform.BLOG_PLATFORMS)
    plats = plats.distinct('influencer')
    infs_id_with_some_platform = plats.values_list('influencer__id', flat=True)
    infs_with_no_plats = no_posts.exclude(id__in=infs_id_with_some_platform)
    msg += "\tWe have %d blog platform objects for these influencers" % plats.distinct('influencer').count()
    msg += "\tWe have %d influencers with no blog platform objects" % infs_with_no_plats.count()

    # find all platforms that have at least one url_not_found=False blog platform
    plats_not_null = plats.exclude(url_not_found=True).distinct('influencer')

    # exclude the above to make sure we only find influencers that only have a platform with url_not_found=True
    plats_not_null_infs = plats_not_null.values_list('influencer', flat=True)
    plats_null = plats.exclude(influencer__in=plats_not_null_infs).distinct('influencer')

    # plats that are null => check if they were marked by feed_discovery part
    plats_null_no_feed = plats_null.filter(feed_url__isnull=True)
    plats_null_feed_never_set = plats_null_no_feed.filter(feed_url_last_updated__isnull=True)

    # plats that are null but have feed url
    plats_null_have_feed = plats_null.filter(feed_url__isnull=False)

    plats_null_have_feed_with_alternate_fetcher = plats_null_have_feed.filter(fetcher_class__isnull=False)
    plats_null_have_feed_without_alternate_fetcher = plats_null_have_feed.filter(fetcher_class__isnull=True)

    plats_null_no_feed_with_alternate_fetcher = plats_null_no_feed.filter(fetcher_class__isnull=False)
    plats_null_no_feed_without_alternate_fetcher = plats_null_no_feed.filter(fetcher_class__isnull=True)

    msg += "\n\nWe have %d influencers with non-null blog platform" % plats_not_null.count()
    msg += "We have %d influencers with null blog platform" % plats_null.count()

    msg += "\n\nWe have %d influencers with feed_url=None" % plats_null_no_feed.count()
    msg += "\tOut of these, have an alternate fetcher %d" % plats_null_no_feed_with_alternate_fetcher.count()
    msg += "\tOut of these, have NO alternate fetcher %d" % plats_null_no_feed_without_alternate_fetcher.count()
    msg += "\tOut of these, feed was never set for %d" % plats_null_feed_never_set.count()

    msg += "\n\nWe have %d influencers with NON-null feed" % plats_null_have_feed.count()
    msg += "\tOut of these, have an alternate fetcher %d" % plats_null_have_feed_with_alternate_fetcher.count()
    msg += "\tOut of these, have NO alternate fetcher %d" % plats_null_have_feed_without_alternate_fetcher.count()

    # with no feed set & not alternate fetcher (plats_null_no_feed_without_alternate_fetcher), find the feed urls
    #   if feed found, set that feed and issue a fetch task reset url_not_found flag

    if detect_feeds:
        ss = list(set(plats_null_no_feed_without_alternate_fetcher | plats_null_no_feed_with_alternate_fetcher))
        feed_found, feed_not_found = redetect_feed_urls(ss, to_save=False)

        log.info("After re-detecting feeds, we have %d with feed " % len(feed_found))
        log.info("And we still don't have feed for %d " % len(feed_not_found))

    #   if feed still not found, we should use the alternate fetcher for these and issue a fetch task for them
    if set_alternate_fetcher:
        ss = list(set(plats_null_no_feed_without_alternate_fetcher | plats_null_no_feed_with_alternate_fetcher))
        alternate_fetcher_set = reset_alternate_fetcher(ss, to_save=False)
        log.info("Alternate fetcher set for %d platforms" % len(alternate_fetcher_set))

    print(msg)
    # platforms that have alternate fetcher class and still marked url_not_found=True => that needs to be checked
    # there are 1289 such platforms right now
    # TODO: even if BloggerRestAPI gets an error like "no data found", we should try to redo this because sometimes
    # it may fail without a real problem.

    # platforms that have feed set but url_not_found=True => why would this happen? Need to check this (very small)


def reset_alternate_fetcher(platform_list, to_save=True):
    """
    Given the platforms, if no feed url is found, we set the alternate fetcher class
    """
    alternate_fetcher_set = set()

    for pl in platform_list:
        log.info("Checking %s" % pl)
        if not pl.feed_url:
            cls_name = fetcher.get_alternative_fetcher_class_name(pl)
            pl.fetcher_class = cls_name
            if to_save:
                pl.save()
                platformutils.record_field_change('influencer_checks_set_alternate_fetcher',
                                                  'fetcher_class',
                                                  None,
                                                  pl.fetcher_class,
                                                  platform=pl)
            alternate_fetcher_set.add(pl)

    return alternate_fetcher_set


def redetect_feed_urls(platform_list, to_save=True):
    """
    Given the platforms, it tries to detect the feed url and sets appropriate fields.
    Also saves it in PlatformDataOp.
    """
    feed_not_found = set()
    feed_found = set()

    for pl in platform_list:
        log.info("Checking %s" % pl)
        try:
            feed_url = feeds.discover_feed(pl.url)
        except:
            feed_url = None
            pass
        if feed_url:
            log.info("Success, we found feed [%s] for %s" % (feed_url, pl))
            if to_save:
                pl.set_feed_url(feed_url)
                pl.url_not_found = None
                pl.fetcher_class = None
                pl.save()
                platformutils.record_field_change('influencer_checks_feed_found', 'url_not_found', True, False, platform=pl)
            feed_found.add(pl)
        else:
            log.info("Failure, we didn't find feed for %s" % pl)
            feed_not_found.add(pl)

    return feed_found, feed_not_found

def check_blog_platforms():
    """
    Find influencers that have None as their blog platform.
    """
    pass


def influencers_validated_last_week():
    tod = datetime.date.today()
    last_week = tod - datetime.timedelta(days=7)
    start = last_week
    one = datetime.timedelta(days=1)
    msg = ''

    while start <= tod:
        validated = models.Influencer.objects.filter(date_validated__contains=start)
        edited = models.Influencer.objects.filter(date_edited__contains=start)
        msg += '%s Edited %d\n' % (start, edited.count())
        msg += '%s Validated %d\n' % (start, validated.count())
        start += one

    print(msg)
    mail_admins('Work done by QA in the week of (%s-%s)' % (last_week, tod), msg)


def _url_not_found_helper(infs, platform_name, cause):
    insta = models.Platform.objects.filter(influencer__in=infs, platform_name=platform_name, url_not_found=True)
    profile_not_found = set()
    msg = '\n***[%s :: %s]***\n' % (platform_name, cause)
    for i in insta:
        ops = models.PlatformDataOp.objects.filter(platform=i,
                                                   operation='fieldchange_url_not_found',
                                                   data_json__contains=cause)
        if ops.count() >= 1:
            profile_not_found.add(i)

    msg += "[%s] We have %d profiles that were marked url_not_found=True because we encountered an error.\n" % (platform_name, len(profile_not_found))

    # now, we should double check to make sure that wasn't a random network error.
    working_again = set()
    not_working = set()
    for i in profile_not_found:
        try:
            r = requests.get(i.url, timeout=20)
            if r.status_code == 200:
                # this url is ok, we should unset the url_not_found
                working_again.add(i)
                continue
        except:
            pass
        not_working.add(i)

    msg += '\tWorking profiles: %d\n' % len(working_again)
    msg += '\tNot working     : %d\n' % len(not_working)

    # ok, for those that are working, let's reset the url_not_found
    for w in working_again:
        w.url_not_found = False
        w.save()

    # for others, we should put them in a suspicious table so that someone can go through them
    print (msg)
    return working_again, not_working

def url_not_found_field_check():
    """
    Find all  platforms that have url_not_found=True and for a given cause.
    We need to make sure that is really the right reason and it wasn't because of a freak network error.
    """
    infs = models.Influencer.objects.all().searchable()
    _url_not_found_helper(infs, 'Instagram', 'instagram_profile_doesnt_exist')
    _url_not_found_helper(infs, 'Twitter', 'invalid_twitter_url')
    _url_not_found_helper(infs, 'Twitter', 'existing_twitter_handle')
    _url_not_found_helper(infs, 'Blogspot', 'no_info_about_blog')
    _url_not_found_helper(infs, 'Wordpress', 'wordpress_blog_doesnt_exist')
    _url_not_found_helper(infs, 'Tumblr', 'tumblr_blog_no_longer_exists')
    _url_not_found_helper(infs, 'Custom', 'discover_feed_failed')
    _url_not_found_helper(infs, 'Blogspot', 'discover_feed_failed')
    _url_not_found_helper(infs, 'Wordpress', 'discover_feed_failed')


def check_non_blacklisted_influencers():
    """
    First, influencers that are not show_on_search but have been QA'ed should be checked.

    Second, influencers that have show_on_search but not old_show_on_search should be checked also.
    """
    infs = models.Influencer.objects.filter(validated_on__contains='info').exclude(show_on_search=True)
    infs_blogs = infs.filter(classification='blog')
    infs_brand = infs.filter(classification='brand')
    infs_squatter = infs.filter(classification='squatter')
    infs_unknown = infs.filter(classification='unknown')
    infs_null = infs.filter(classification__isnull=True)
    infs_blacklisted = infs.filter(blacklisted=True)
    print("[QAed but show_on_search=False] = %d. Classified as blog: %d brand: %d squatter: %d unknown: %d null: %d Blacklisted: %d" % \
          (infs.count(), infs_blogs.count(), infs_brand.count(), infs_squatter.count(), infs_unknown.count(),
           infs_null.count(), infs_blacklisted.count()))

    infs = models.Influencer.objects.filter(show_on_search=True).exclude(old_show_on_search=True)
    infs_blogs = infs.filter(classification='blog')
    infs_brand = infs.filter(classification='brand')
    infs_squatter = infs.filter(classification='squatter')
    infs_unknown = infs.filter(classification='unknown')
    infs_null = infs.filter(classification__isnull=True)
    infs_blacklisted = infs.filter(blacklisted=True)
    print("[show_on_search but not old_show_on_search] = %d. Classified as blog: %d brand: %d squatter: %d unknown: %d null: %d Blacklisted: %d" % \
          (infs.count(), infs_blogs.count(), infs_brand.count(), infs_squatter.count(), infs_unknown.count(),
           infs_null.count(), infs_blacklisted.count()))


def check_blacklisted_influencers():
    """
    Here, we want to detect all influencers that were marked blacklisted=True and were never QA'ed. This could be
    problematic because our algorithm at that time was not good.
    """
    infs = models.Influencer.objects.filter(blacklisted=True).exclude(validated_on__contains='info')
    infs = infs.exclude(classification__in=['squatter', 'brand', 'social'])
    print("Influencers that were marked unknown last time: %d" % infs.count())


def have_empty(influencer, to_save=False):
    """
    CHECK this guy i = Influencer.objects.get(id=2151303)
    i = Influencer.objects.get(id=917941)

    Check if an influencer has no platform with url_not_found=False for each social url.
    If the influencer has the url set by QA =>
        => If we have a strongly validated platform but it doesn't match QA
            => then we should create
    """
    platforms = models.Platform.objects.filter(influencer=influencer)
    names = models.Influencer.platform_name_to_field.keys()
    to_exclude = ['Lookbook', 'Pose']
    msg = None
    state = None

    def get_username(url):
        return platformutils.username_from_platform_url(url)

    for name in ['Twitter']:
        field_url = models.Influencer.platform_name_to_field[name]
        if name in to_exclude:
            continue
        url = getattr(influencer, field_url, None)
        plat_name = platforms.filter(platform_name=name).exclude(url_not_found=True)
        plats_autovalidated = platforms.filter(platform_name=name).filter(autovalidated=True)
        if plat_name.count() == 0 and plats_autovalidated.count() > 0:
            msg = "[%s] we have NO valid platform objects set but we have good objects [%s]\n" % (url,
                                                                                                        plats_autovalidated.values_list('url', flat=True))
            plats_validated_strong = plats_autovalidated.filter(autovalidated_reason='blog_url_in_description')
            if url:
                if plats_validated_strong.count() >= 1:
                    if plats_validated_strong.count() == 1:
                        print("QA entered=[%s] and it matches what we have=[%s], so we should enable this." % (url, plats_validated_strong[0].url))
                        if to_save:
                            # now discard all others except what was entered in the URL field (either by QA or ours)
                            admin_helpers.handle_social_handle_updates(influencer, field_url, url)
                        state = 0
                    if plats_validated_strong.count() > 1:
                        print("HMMM, QA etnered=[%s] we have more than 1 strongly validated %s" % (url, plats_validated_strong))
                        state = 1
                    msg += '\t[%s] Found strong urls [%s]  QA entered: %s\n' % (field_url,
                                                                                     plats_validated_strong.values_list('url', flat=True),
                                                                                     url)

                else:
                    msg += '\t[%s] Found other autovalidated urls [%s]  [%s] QA entered: %s\n' % (field_url,
                                                                                     plats_autovalidated.values_list('url', flat=True),
                                                                                     plats_autovalidated.values_list('autovalidated_reason', flat=True),
                                                                                     url)
                    for pa in plats_autovalidated:
                        if get_username(url) == get_username(pa.url):
                            print("HMMM, QA etnered=[%s] we found at least one validated that matched %s" % (url, pa))
                            if to_save:
                                admin_helpers.handle_social_handle_updates(influencer, field_url, url)
                            break
                    state = 2
            else:
                # here if we have a strongly validated platform, we should copy it to the influencer fields
                if plats_validated_strong.count() == 1:
                    url = plats_validated_strong[0].url
                    if to_save:
                        setattr(influencer, field_url, url)
                        influencer.save()
                        # now discard all others except what was entered in the URL field (either by QA or ours)
                        admin_helpers.handle_social_handle_updates(influencer, field_url, url)
                    msg += '\t[%s] [%s] Saving url %s and QA forgot to add this\n' % (influencer, field_url, url)
                    state = 3
                elif plats_validated_strong.count() > 1:
                    msg += '\t[%s] [%s] Got more than 1 autovalidated platforms with reason blog_url_in_description %s\n' % (influencer,
                                                                                                                        field_url,
                                                                                                                        plats_validated_strong.values_list('url', flat=True))
                    state = 4
                else:
                    msg += '\t[%s] [%s] Got no platforms with strong reason blog_url_in_description, but rest are %s\n' % (influencer,
                                                                                                                       field_url,
                                                                                                                       plats_autovalidated.values_list('url', flat=True))
                    state = 5
        if plat_name.count() == 0 and plats_autovalidated.count() == 0:
            plats_all = platforms.filter(platform_name=name)

            if plats_all.count() > 0:
                msg = "[%s] we have no autovalidated platform and QA didn't enter anything either but we have some platform objects %s %s\n" % (influencer,
                                                                                                                                             plats_all,
                                                                                                                                             plats_all.values_list('autovalidated_reason', flat=True))
                state = 6
            else:
                msg = "[%s] we have no autovalidated platform and QA didn't enter anything\n" % influencer
                state = 7

    return msg, state


def have_multiple(influencer, to_save=False):
    """
    Here we check if an influencer has multiple valid platform objects for any social url.

    We also correct these mistakes for the easier cases:
    a) If there is more than one Platform objects but only one that is autovalidated and matches what QA has filled in,
        then we discard all others and keep this platform.
    b) If there is one autovalidated platform but it doesn't match what QA has submitted
        mark these validated platform with a special reason "influencer_check_validated_%s"%autovalidated_reason
        mark all others also url_not_found (that didn't match what QA entered).
    c) If we have more than one validated,
        if any of these match what QA has entered, pick that and discard others.
    d) If more than one platforms exist but none is auto validated => don't know what to do here. Why does this case exist?
    """
    platforms = models.Platform.objects.filter(influencer=influencer).exclude(url_not_found=True)
    names = models.Influencer.platform_name_to_field.keys()
    to_exclude = ['Lookbook', 'Pose', 'Bloglovin']
    msg = None
    state = None

    def get_username(url):
        return platformutils.username_from_platform_url(url)

    for name in names:
        if name in to_exclude:
            continue
        field_url = models.Influencer.platform_name_to_field[name]
        url = getattr(influencer, field_url, None)
        plat_name = platforms.filter(platform_name=name)

        if plat_name.count() > 1:
            msg = "[%s] [%s] we have more than one platform objects: [%s]\n" % (name, url, plat_name.values_list('url', flat=True))

            plat_name_auto_validated = plat_name.filter(autovalidated=True)

            if plat_name_auto_validated.count() == 1 and url and get_username(url) == get_username(plat_name_auto_validated[0].url):
                msg += "\tAWESOME: We have one autovalidated %s among these and it matches the url %s" % (plat_name_auto_validated, url)
                state = 0
            elif plat_name_auto_validated.count() == 0:
                msg += "\tBAD: No autovalidated platforms exist"
                state = 1
            elif plat_name_auto_validated.count() == 1 and (not url or get_username(url) != get_username(plat_name_auto_validated[0].url)):
                msg += "\tWORSE (QA PROBLEM): We have autovalidated platform %s but they don't match url %s" % (plat_name_auto_validated, url)
                state = 2
                # we need to go over the validated one with QA later on
                p = plat_name_auto_validated[0]
                if to_save:
                    platformutils.set_url_not_found('influencer_check_%s_but_qa_didnt_find' % p.autovalidated_reason, p)
            elif plat_name_auto_validated.count() > 1:
                msg += "\tWEIRD: We have more than one autovalidated platforms %s for url %s\n" % (plat_name_auto_validated, url)
                found = None
                for i, p in enumerate(plat_name_auto_validated):
                    if found:
                        break
                    if url and get_username(url) == get_username(p.url):
                        found = p
                    # if QA didn't fine the url and we either pick one with a good reason or the last one
                    if not url and (p.autovalidated_reason == 'blog_url_in_description' or i == len(plat_name_auto_validated) - 1):
                        found = p
                if found:
                    if not url:
                        url = found.url
                        setattr(influencer, field_url, url)
                        if to_save:
                            influencer.save()
                    msg += "\t\tSELECTED %s to stay with autovalidate_reason=%s. QA entered url: %s\n" % (found, found.autovalidated_reason, url)
                else:
                    # this means that QA's URL didn't match any of our discovered urls, which may indicate QA problem
                    if to_save:
                        for p in plat_name_auto_validated:
                            platformutils.set_url_not_found('influencer_check_%s_but_qa_didnt_find' % p.autovalidated_reason, p)
                    msg += "\t\tNo platform was selected. QA entered url: %s\n" % url
                state = 3
            else:
                state = 4

            if to_save:
                # now discard all others except what was entered in the URL field (either by QA or ours)
                admin_helpers.handle_social_handle_updates(influencer, field_url, url)

    return msg, state


def check_multiple_valid_social_platforms(multiple_or_empty='multiple', to_save=False):
    """
    Calls appropriate function above based on the parameter multiple_or_empty
    """
    infs = models.Influencer.objects.all().searchable().filter(old_show_on_search=True).order_by('-score_popularity_overall')
    have_problems = [[], [], [], [], [], [], [], [], []]
    for j,i in enumerate(infs[:300]):
        if multiple_or_empty == 'multiple':
            msg, state = have_multiple(i, to_save)
        else:
            msg, state = have_empty(i, to_save)

        if msg:
            print("%s\n\t%s" % (i, msg))
            have_problems[state].append(i)
        else:
            print("%s No problem" % i)
        print("%s-------\n" % j)

    print("[%s] Influencers with problems: [0]=%s [1]=%s [2]=%s [3]=%s [4]=%s [5]=%s [6]=%s [7]=%s [8]=%s Total=%s" % (multiple_or_empty,
                                                                                                                        len(have_problems[0]),
                                                                                                                        len(have_problems[1]),
                                                                                                                        len(have_problems[2]),
                                                                                                                        len(have_problems[3]),
                                                                                                                        len(have_problems[4]),
                                                                                                                        len(have_problems[5]),
                                                                                                                        len(have_problems[6]),
                                                                                                                        len(have_problems[7]),
                                                                                                                        len(have_problems[8]),
                                                                                                                        infs.count()))


def check_facebook_id_from_url_extraction():
    infs = models.Influencer.objects.all().searchable().filter(old_show_on_search=True).order_by('-score_popularity_overall')
    fb_plats = models.Platform.objects.filter(platform_name='Facebook', influencer__in=infs).exclude(url_not_found=True)
    fb_plats_with_validated = fb_plats.filter(validated_handle__isnull=False)
    print("We have %d facebook platforms, validated_handle %d" % (fb_plats.count(), fb_plats_with_validated.count()))

    count_success = 0
    count_not_200 = 0
    count_didnt_match = 0

    for i, f in enumerate(fb_plats_with_validated):
        url = f.url.lower()
        if '?' in url:
            loc = url.find('?')
            url = url[:loc]
        r = requests.get('https://graph.facebook.com/%s' % f.validated_handle)
        url_without_protocol = utils.remove_protocol(url)
        url_without_www = utils.remove_www(url)
        url_without_www_protocol = utils.remove_protocol(url_without_www) if url_without_www else None
        print("without_protocol=[%s] without_www=[%s] without_www_protocl=[%s]" % (url_without_protocol, url_without_www, url_without_www_protocol))
        if r.status_code == 200:
            resp = r.json()
            l = resp['link'].lower()
            l_without_protocol = utils.remove_protocol(l)
            l_without_www = utils.remove_www(l)
            l_without_www_protocol = utils.remove_protocol(l_without_www) if l_without_www else None
            print("l_without_protocol=[%s] l_without_www=[%s] l_without_www_protocol=[%s]" % (l_without_protocol, l_without_www, l_without_www_protocol))
            if l == url or l_without_protocol == url_without_protocol or \
                    (l_without_www and l_without_www == url_without_www) or l == url_without_www or \
                    l_without_www == url or url == l_without_www_protocol or l == url_without_www_protocol \
                    or l_without_www_protocol == url_without_protocol or l_without_protocol == url_without_www_protocol:
                #print("Perfect URL matches")
                count_success += 1
            else:
                # now check if L redirects
                rl = xutils.resolve_redirect_using_xbrowser(l)
                if rl is not l:
                    pass
                print("Error: url: %s didn't match what we found in the handle %s" % (f.url, l))
                count_didnt_match += 1
        else:
            print("%s didn't return 200" % f)
            count_not_200 += 1

        print("[%d] matched:%d not-match:%d not-200:%d" % (i, count_success, count_didnt_match, count_not_200))
        time.sleep(5)


def getting_200(url):
    try:
        print("Checking %s" % url)
        r = requests.get(url)
        if r.status_code == 200:
            return True
    except:
        pass
    return False


def influencer_profile_image_fixes(to_fix=False):
    """
    Facebook images:
        url type: fbcdn-profile-a.akamaihd.net

    Twitter images:
        url type: pbs.twimg.com

    Instagram images:
    have the following format    https://igcdn-photos-c-a.akamaihd.net/hphotos-ak-xaf1/t51.2885-19/11287812_487668668053154_1181492298_a.jpg

    For all of the above, check if the url exists by requesting it and checking reply.status_code
        If 404 => need to find something else
        If 200 => create in S3 bucket and save it in influencer.profile_img_url


    Pinterest images: we don't find them or use them

    Harder problem
        => the image stored in the platform is also an S3 image. And that image is busted? How do we detect these?
        => May be check the platform that this S3 image is stored in.
        => Check then the availability of the platform. 
    """




    def get_platform_used_for_profile_img(influencer):
        plats = influencer.platforms()#.exclude(url_not_found=True)
        plats = plats.filter(profile_img_url=influencer.profile_pic_url)
        if plats.count() == 1:
            return plats[0]
        elif plats.count() > 1:
            print("We have more than one platform that has the same profile img url.")
            return None
        else:
            print("No platform found with the same profile url, shouldn't happen")
            return None

    def fix_image(platform, image_url):
        if not platform:
            print("No platform provided, returning")
            return
        print("Ok, platform %s matches the image url %s, so we can proceed with fixing it" % (platform, image_url))
        image_manipulator.save_social_images_to_s3(platform)

    def fix_infs(infs_bad):
        #if not to_fix:
        #    return

        bad = set()

        # Now go through each of these suspect influencers and see if the URL is getting 404 or 200?
        # If 200 => then correctly save it in S3 bucket and save it in Influencer.
        # If 404 => then we should check if this platform is reachable or not. If not, mark this url_not_found
        #           and then run influencer.set_profile_pic()
        for inf in infs_bad:
            print("Trying %s Bad so far: %d" % (inf, len(bad)))
            plat = get_platform_used_for_profile_img(inf)
            if not getting_200(inf.profile_pic_url):
                bad.add(inf)
                if plat:
                    plat.profile_img_url = None
                    plat.save()
                inf.profile_pic_url = None
                inf.save()
                print("Bad image url, plat: %s" % plat)
            else:
                fix_image(plat, inf.profile_pic_url)
            print("Final profile pic: %s for %s " % (inf.profile_pic_url, inf))

        print("Non-S3 Profiles: [%s] Unreachable: %d" % (infs_bad.count(), len(bad)))

    # for testing
    collection = models.InfluencersGroup.objects.get(id=1043)
    inf_ids = [i.id for i in collection.influencers]
    infs = models.Influencer.objects.filter(id__in=inf_ids)

    #infs = models.Influencer.objects.filter(show_on_search=True)

    fb_pics = infs.filter(profile_pic_url__contains='fbcdn-profile-')
    tw_pics = infs.filter(profile_pic_url__contains='pbs.twimg.com')
    in_pics = infs.filter(profile_pic_url__contains='igcdn-photos-')

    infs_bad = fb_pics | tw_pics | in_pics
    infs_bad = infs_bad.distinct()

    print("Total: [%d] Profile-Facebook: [%d] Profile-Twitter: [%d] Profile-Instagram: [%d]" % (infs.count(),
                                                                                                fb_pics.count(),
                                                                                                tw_pics.count(),
                                                                                                in_pics.count()))
    if infs_bad.count() == 0:
        print("AWESOME: no issues for now, returning happily.")
        #return
    else:
        fix_infs(infs_bad)


    # now, let's go through the platforms for each of the remaining ones and make sure they are reachable and then
    # save them in S3
    plats = models.Platform.objects.filter(influencer__in=infs).exclude(url_not_found=True)
    #plats = plats.exclude(profile_img_url__isnull=True)
    print("%s have %s platforms that don't have their image stored in S3")
    for p in plats:
        u = p.profile_img_url
        if 'amazonaws' not in u:
            if getting_200(u):
                # great, we can access the image
                # let's save this in S3
                image_manipulator.save_social_images_to_s3(p)
            else:
                # reset the image url now
                p.profile_img_url = None
                p.save()
        # ok, let's try fetching the profile page
        if not getting_200(p.url):
            # hmmm, this is weird, mark this platform url_not_found
            platformutils.set_url_not_found('influencers_check_cant_access_url', p)
        else:
            policy = pbfetcher.DefaultPolicy()
            try:
                fetcher_impl = fetcher.fetcher_for_platform(p, policy)
            except:
                pass
        print ("%s has %s image url" % (p, p.profile_img_url))

    # now, let's recalculate the images for these influencers
    for i in infs:
        i.set_profile_pic()
        print("%s has %s" % (i, i.profile_pic_url))


def remove_wellknown_social_urls():
    """
    Anyone with a link to a polyvore brand twitter or facebook url

    So, suspicious brands urls
    ['polyvore', 'etsy', 'popsugar', 'twitter', 'facebook', 'pinterest', 'instagram']
    """
    pass


def check_and_ensure_profile_pics_on_s3():
    """
    Make sure that all platform.profile_img_url are on S3 if we have a valid URL
    """
    infs = models.Influencer.objects.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    infs = infs.exclude(blacklisted=True)

    # these two bottom ones can be removed later on
    infs = infs.filter(show_on_search=True)
    infs = infs.exclude(old_show_on_search=True)

    infs_non_s3 = infs.filter(profile_pic_url__isnull=False).exclude(profile_pic_url__icontains='amazonaws')
    print("Total: %d %d influencers have non-s3 image" % (infs.count(), infs_non_s3.count()))

    plats = models.Platform.objects.filter(influencer__in=infs).exclude(url_not_found=True)
    plats = plats.filter(profile_pic_url__isnull=False)
    plats = plats.exclude(profile_pic_url__icontains='amazonaws')
    print("Ok, before starting, we have %d platforms with non-s3 images" % plats.count())
    for p in plats:
        if getting_200(p.profile_img_url):
            image_manipulator.save_social_images_to_s3(p)
        else:
            print("Oh, the profile img %s is not reachable anymore. We shoudl probably refetch it")
            p.profile_img_url = None
            p.save()

    print("OK, after finishing, we have %d platforms with non-s3 images" % plats.count())


def check_if_profile_image_from_bad_platform():
    """
    Here we look at influencer's images and see if they are coming from a platform that is not
    either autovalidated or doesn't match what the QA entered.
    """
    infs = models.Influencer.objects.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    infs = infs.exclude(blacklisted=True)

    # these two bottom ones can be removed later on
    infs = infs.filter(show_on_search=True)
    infs = infs.exclude(old_show_on_search=True)

    infs_with_profile_pic = infs.filter(profile_pic_url__isnull=False)
    infs_with_s3_profile_pic = infs_with_profile_pic.filter(profile_pic_url__contains='amazonaws')

    print("Total: %d Have profile: %d  Have s3 profile: %d" % (infs.count(),
                                                               infs_with_profile_pic.count(),
                                                               infs_with_s3_profile_pic.count()))

    bad_infs = set()
    good_infs_others = set()
    good_infs_autovalidated = set()
    more_than_one = set()
    none_found = set()
    for i, inf in enumerate(infs_with_profile_pic):
        print("%d Checking %s. So far we have %d bad and %d good_autoval %d good other and %d with more than one and %d with none influencers" % (i, inf, len(bad_infs), len(good_infs_autovalidated), len(good_infs_others), len(more_than_one), len(none_found)))
        plat = inf.platforms().filter(profile_img_url=inf.profile_pic_url)
        if plat.count() > 0:
            if plat.count() > 1:
                more_than_one.add(inf)
                continue
            plat = plat[0]
            # ok, now check if these are autovalidated or entered by QA
            autovalidated = plat.autovalidated
            if autovalidated:
                good_infs_autovalidated.add(inf)
                continue
            pname = plat.platform_name
            field_name = models.Influencer.platform_name_to_field[pname]
            field_val = getattr(inf, field_name)
            print("field_name: %s field_val: %s" % (field_name, field_val))
            if field_val and platformutils.username_from_platform_url(field_val.lower()) == platformutils.username_from_platform_url(plat.url.lower()):
                good_infs_others.add(inf)
                continue
            bad_infs.add(inf)
        else:
            none_found.add(inf)


def check_platform_consistency():
    """
    Ok, almost all errors arise because the platforms discovered are not correct.
    -- either they point to someone else (like etsy.com)
    -- or they are just wrong or dead

    We already have a mechanism to automatically detect whether url is good or not.
    So, here we will go through each url value stored in Influencers and
    a) see if we have a url_not_valid=False platform for that value
       => if yes, check if it's autovalidated
            => if not, try once more. If not, add it to a special table or collection that QA can go through
    """
    infs = models.Influencer.objects.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    infs = infs.exclude(blacklisted=True)

    # these two bottom ones can be removed later on
    infs = infs.filter(show_on_search=True)

    plats = models.Platform.objects.filter(influencer__in=infs).exclude(url_not_found=True)
    plats = plats.filter(platform_name__in=models.Platform.SOCIAL_PLATFORMS)

    plats_autovalidated = plats.filter(autovalidated__isnull=False)
    plats_autovalidated_success = plats.filter(autovalidated=True)
    plats_autovalidated_fail = plats.filter(autovalidated=False)
    plats_not_yet_autovalidated = plats.filter(autovalidated__isnull=True)

    print("Total social: %d Evaluated: %d Succeeded: %d Failed: %d Not done: %d" % (plats.count(),
                                                                                    plats_autovalidated.count(),
                                                                                    plats_autovalidated_success.count(),
                                                                                    plats_autovalidated_fail.count(),
                                                                                    plats_not_yet_autovalidated.count()))

    # now, check consistency between



def discover_blogs_from_brand_urls():
    """
    We create a Brand object from the content of existing influencers. But it's quite likely that the urls
    in these blogs are actually pointing to a lot of other quality blogs.
    """

    all_brands = models.Brands.objects.all()

    blogs = all_brands.filter(classification='blog') | all_brands.filter(domain_name__icontains='blog')

    pass


def platforms_from_signedup_bloggers_fetch_stats(to_fix=False):
    """
    Here, we figure out how many of the signed up influencers have platforms that do not have posts.
    """
    infs = models.Influencer.objects.filter(source__contains='blogger_signup')
    plats = models.Platform.objects.filter(influencer__in=infs).exclude(url_not_found=True)
    have_posts = set()
    for p in plats:
        if models.Posts.objects.filter(platform=p).count() > 0:
            have_posts.add(p)

    have_posts_id = [h.id for h in have_posts]
    plats_no_posts = plats.exclude(id__in=have_posts_id)

    print("Total infs.blogger_signup=%d Total plats=%d Have posts=%d No posts=%d" % (infs.count(),
                                                                                     plats.count(),
                                                                                     len(have_posts),
                                                                                     plats_no_posts.count()))

    if to_fix:
        for p in plats_no_posts:
            pol = pbfetcher.policy_for_platform(p)
            fetchertasks.fetch_platform_data.apply_async([p.id, pol.name], queue='new_influencer')


@task(name='debra.influencer_checks.create_social_platform_duplicates_influencer_checks', ignore_result=True)
def create_social_platform_duplicates_influencer_checks():
    """
    Here we invoke code to run suspicions.py method to detect influencers that have same social urls.
    We run this once for each platform that we crawl.

    We should run this once every month.
    :return:
    """
    s = suspicions.SuspectDuplicateSocial()
    plat_names = models.Platform.SOCIAL_PLATFORMS_CRAWLED

    for name in plat_names:
        s.report_all(name)


@task(name='debra.influencer_checks.check_email_for_advertising_or_collaborations', ignore_result=True)
def check_email_for_advertising_or_collaborations():
    email_pairs = models.Influencer.objects.exclude(
        shelf_user__isnull=True
    ).values_list(
        'id', 'shelf_user__email', 'email_for_advertising_or_collaborations'
    )

    def should_update(pair):
        shelf_user_email, email_for_advertising_or_collaborations = pair

        if shelf_user_email is None or 'toggle' in shelf_user_email:
            return False
        if email_for_advertising_or_collaborations is None:
            return True
        if 'PROBLEM ID' in email_for_advertising_or_collaborations:
            return False
        if shelf_user_email != email_for_advertising_or_collaborations:
            return True

    id_to_email = dict(
        [(p[0], p[1]) for p in email_pairs if should_update(p[1:])])

    infs = models.Influencer.objects.filter(id__in=id_to_email.keys())

    for inf in infs:
        inf.email_for_advertising_or_collaborations = id_to_email[inf.id]
        inf.save()


@task(name='debra.influencer_checks.reindex_unindexed_posts', ignore_result=True)
def reindex_unindexed_posts():
    """
    Here we check if all eligible posts of the influencer are indexed and if some are not, scheduling them for indexing.

    :return:
    """

    # Creating custom logger with file
    custom_logger = logging.getLogger('reindexing')
    hdlr = RotatingFileHandler('/home/ubuntu/log/reindexing_not_indexed_posts.log',
                               maxBytes=10*1024*1024,
                               backupCount=5)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    custom_logger.addHandler(hdlr)
    custom_logger.setLevel(logging.INFO)

    custom_logger.info('reindex_unindexed_posts started')

    performance_step = 1000  # step of slice to perform

    from debra.elastic_search_helpers import inf_indexed_posts_checker

    # getting iteration number from cache if it is there, otherwise start it again
    cache = get_cache('long')
    iter_number = cache.get('reindex_unindexed_posts_iter')
    if iter_number is None:
        iter_number = 0

    # fetching corresponding influencers
    inf_ids = list(models.Influencer.objects.filter(
        old_show_on_search=True,
    ).exclude(
        blacklisted=True
    ).exclude(
        source__contains='brand'
    ).order_by(
        'id'
    ).values_list(
        'id', flat=True
    )[iter_number*performance_step:iter_number*performance_step+performance_step])

    if len(inf_ids) > 0:

        custom_logger.info('Performing %s influencers today: iteration: %s [%s:%s] . First id: %s, last id: %s' % (
            performance_step,
            iter_number,
            iter_number*performance_step,
            iter_number*performance_step+performance_step,
            inf_ids[0],
            inf_ids[-1],
        ))

        # finding all of their not indexed posts
        for inf_id in inf_ids:
            _, not_indexed_ids = inf_indexed_posts_checker(inf_id)

            if not_indexed_ids is not None and isinstance(not_indexed_ids, list) and len(not_indexed_ids) > 0:
                custom_logger.info('Influencer %s has %s posts not indexed' % (inf_id, len(not_indexed_ids)))
                models.Posts.objects.filter(id__in=not_indexed_ids).update(last_modified=datetime.datetime.now())
                print(not_indexed_ids)
                custom_logger.info('%s posts scheduled for indexing' % len(not_indexed_ids))
                try:
                    inf = models.Influencer.objects.get(id=inf_id)
                    inf.last_modified = datetime.datetime.now()
                    inf.save()
                    custom_logger.info('Influencer %s scheduled for indexing' % inf_id)
                except models.Influencer.DoesNotExist:
                    custom_logger.error('Influencer with id %s does not exist')

        # after all is done, updating iter_number
        iter_number += 1
        cache.set('reindex_unindexed_posts_iter', iter_number, 7*24*3600)  # caching it for 7 days

    else:
        # iter_number = 0
        # cache.set('reindex_unindexed_posts_iter', iter_number, 7*24*3600)  # caching it for 7 days

        custom_logger.info('No influencers fetched, no work today... iteration: %s [%s:%s]' % (
            iter_number,
            iter_number*performance_step,
            iter_number*performance_step+performance_step
        ))
