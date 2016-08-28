"""Integrating fetchers and policies and running them as Celery tasks.
"""

import logging
import time
import os
import os.path
import datetime

from celery.decorators import task
import baker
from django.conf import settings
from django import template

from debra import models
from . import fetcher
from . import fetcherbase
from . import pbfetcher
from . import platformutils
from . import pdimport
from xpathscraper import utils


log = logging.getLogger('platformdatafetcher.fetchertasks')

MAX_PLATFORMS = 100000

PLATFORM_NAMES = fetcher.PLATFORM_NAME_TO_FETCHER_CLASS.keys()
SLEEP_OK = 1
SLEEP_ERROR = 5

MIN_POSTS_NEEDED_FOR_ENABLING_INDEPTH_PROCESSED_FOR_SOCIAL_PLATFORM = 500
MIN_POSTS_NEEDED_FOR_ENABLING_INDEPTH_PROCESSED_FOR_BLOG_PLATFORM = 200
MIN_POSTS_NEEDED_FOR_CHECKING_RELEVANCY = 60


@baker.command
def fetch_all_platforms_data(platform_name):
    pls = models.Platform.objects.filter(platform_name=platform_name).\
            filter(influencer__isnull=False).\
            order_by('-create_date')[:MAX_PLATFORMS]
    pls_count = pls.count()
    log.warn('Processing %s platforms', pls_count)
    for i, pl in enumerate(pls):
        f = None
        try:
            log.info('Processing %s/%s %s', i + 1, pls_count, pl)
            f = fetcher.fetcher_for_platform(pl)
            log.info('Using fetcher %s', f)
            f.fetch_posts(max_pages=1)

            time.sleep(SLEEP_OK)
        except KeyboardInterrupt:
            return
        except fetcherbase.FetcherCallLimitException as exc:
            to_sleep = exc.seconds_to_wait()
            log.exception('FetcherCallLimitException, sleeping for %s', to_sleep)
            time.sleep(to_sleep)
        except:
            log.exception('Exception while fetching data for %s', pl)
            time.sleep(SLEEP_ERROR)
        finally:
            if f is not None:
                try:
                    f.cleanup()
                except:
                    pass


def no_post_images_in_latest_posts(platform, num_posts=15):
    post_data = platform.posts_set.all().order_by('-create_date')[:num_posts].values('post_image', 'products_import_completed')
    post_data = list(post_data)
    if len(post_data) < num_posts:
        log.warn('Not enough posts to decide if posts lack an image')
        return False

    # Posts with products_import_completed == False count as ones that will eventually have images
    posts_with_eventual_images = [d for d in post_data
                         if d['post_image'] is not None or not d['products_import_completed']]
    if not posts_with_eventual_images:
        log.info('No post images in latest %d posts', num_posts)
        return True
    else:
        log.info('There are post images in latest %d posts', num_posts)
        return False


def _fetch_platform(platform_id):
    platform_q = models.Platform.objects.filter(id=int(platform_id))
    if not platform_q.exists():
        log.error('No platform with id %s', platform_id)
        return None
    platform = platform_q[0]
    if platform.influencer is None:
        log.error('Influencer for platform id %s not set, cannot do fetching', platform_id)
        return None
    return platform


def _do_fetch_platform_data(platform, policy=None, force_refetch=False):
    fetcher_impl = None
    opr = platformutils.OpRecorder(operation='fetch_data', platform=platform)

    try:
        if policy is None:
            policy = pbfetcher.policy_for_platform(platform)
        assert policy is not None, 'Policy is None -- policy_for_platform did not return anything'
        opr.data = dict(policy=policy.name,
                        activity_level=platform.activity_level,
                        last_fetched=platform.last_fetched.isoformat() if platform.last_fetched else None)
        log.debug('Will initialize fetcher for platform <<%s>> using policy %s',
                 platform, policy)
        fetcher_impl = fetcher.fetcher_for_platform(platform, policy)

        if platform.platform_name_is_blog and force_refetch:
            fetcher_impl.force_fetch_all_posts = True

        log.debug('Using fetcher_impl %s and policy %s to fetch data for %s', fetcher_impl,
                 policy, platform)
        policy.perform_fetching(fetcher_impl)
    except KeyboardInterrupt:
        opr.register_exception()
    except fetcherbase.FetcherCallLimitException as exc:
        opr.register_exception()
        to_sleep = exc.seconds_to_wait()
        log.exception('FetcherCallLimitException, sleeping for %s', to_sleep)
        time.sleep(to_sleep)
    except:
        opr.register_exception()
        log.exception('Exception while fetching data for %r', platform)
        time.sleep(SLEEP_ERROR)
    finally:
        if fetcher_impl is not None:
            try:
                fetcher_impl.cleanup()
            except:
                log.exception('While cleaning fetcher_impl, ignoring')
                pass

    if not opr.is_exception_registered():
        opr.register_success()

    if fetcher_impl is not None:
        opr.data = dict(opr.data or {},
                        counts=fetcher_impl.counts,
                        fetcher_class=fetcher_impl.__class__.__name__)

    if settings.DISCOVER_NEW_INFLUENCER_USING_COMMENTS:
        # Submit import_from_comment_content tasks for crated post interactions
        if fetcher_impl is not None and platform.platform_name_is_blog:
            log.info('Created %d pis', len(fetcher_impl.created_pis))
            for pi in fetcher_impl.created_pis:
                pdimport.import_from_comment_content.apply_async(args=[pi.id, True], queue='pdimport')

    

    ### # TODO: temporarily disabling checks and switches to alternate fetcher classes
    ### # If the platform has posts but no posts in last 30 days,
    ### # try using an alternative fetcher class for further fetch tasks
    ### if platform.numposts and platform.numposts >= 10:
    ###     recent_posts = platform.posts_set.filter(
    ###         inserted_datetime__gte=datetime.datetime.now() - datetime.timedelta(days=30)).count()
    ###     log.debug('Recently fetched posts: %d', recent_posts)
    ###     if recent_posts == 0:
    ###         cls_name = fetcher.get_alternative_fetcher_class_name(platform)
    ###         log.info('No recent posts, using an alternative fetcher class %s', cls_name)
    ###         platform.fetcher_class = cls_name
    ###         platform.save()

    ### # If a platform is blog and there are no images for the latest 15 posts,
    ### # also try using an alternative fetcher class
    ### if platform.platform_name_is_blog and no_post_images_in_latest_posts(platform, num_posts=15):
    ###     cls_name = fetcher.get_alternative_fetcher_class_name(platform)
    ###     log.info('No post images in recent posts, using an alternative fetcher class %s', cls_name)
    ###     platform.fetcher_class = cls_name
    ###     platform.save()


    # THIS NEEDS TO BE IN CELERY (ATUL)
    log.info('Writing fetching log to mongo:')
    from debra.mongo_utils import mongo_mark_performed_platform
    mongo_mark_performed_platform.apply_async([platform.id,
                                               platform.influencer.id,
                                               platform.influencer.show_on_search,
                                               platform.influencer.old_show_on_search,
                                               platform.url_not_found,
                                               platform.platform_name],
                                              queue='mongo_mark_performed_platform')

    log.info('Finished fetching data for platform %s', platform)
    return opr


@task(name='platformdatafetcher.fetchertasks.fetch_platform_data', ignore_result=True)
@baker.command
def fetch_platform_data(platform_id, policy_name=None, policy_instance=None):
    log.debug('policy_name from task: %r', policy_name)
    log.debug('policy_instance from task: %r', policy_instance)
    if policy_instance is not None:
        policy = policy_instance
    elif policy_name is not None:
        policy = pbfetcher.POLICY_NAME_TO_POLICY.get(policy_name)
        assert policy is not None, 'Invalid policy name: %r' % policy_name
    else:
        policy = None
    platform = _fetch_platform(platform_id)
    if platform:
        _do_fetch_platform_data(platform, policy)


@task(name='platformdatafetcher.fetchertasks.force_refetch_platform_data', ignore_result=True)
@baker.command
def force_refetch_platform_data(platform_id, policy_name=None, policy_instance=None):
    log.info('policy_name from task: %r', policy_name)
    log.info('policy_instance from task: %r', policy_instance)
    if policy_instance is not None:
        policy = policy_instance
    elif policy_name is not None:
        policy = pbfetcher.POLICY_NAME_TO_POLICY.get(policy_name)
        assert policy is not None, 'Invalid policy name: %r' % policy_name
    else:
        policy = None
    platform = _fetch_platform(platform_id)
    if platform:
        _do_fetch_platform_data(platform, policy, force_refetch=True)


def has_gplus_comments(url):
    from platformdatafetcher import postinteractionsfetcher
    try:
        return postinteractionsfetcher.GPlusPostInteractionsFetcher.url_contains_iframe(url)
    except:
        log.exception("Couldn't check if '{}' contains G+ widget.".format(url))
        return False


def has_facebook_comments(url):
    from platformdatafetcher import postinteractionsfetcher
    try:
        return postinteractionsfetcher.FacebookPostInteractionsFetcher.url_contains_iframe(url)
    except:
        log.exception("Couldn't check if '{}' contains Facebook widget.".format(url))
        return False


def should_refetch_social_comments(platform_id):
    first_post = models.Posts.objects.filter(platform_id=platform_id).order_by('-create_date')[:1][0]
    return has_gplus_comments(first_post.url) or has_facebook_comments(first_post.url)


@task(name='platformdatafetcher.fetchertasks.check_social_comments', ignore_result=True)
@baker.command
def check_social_comments(platform_ids):
    log.info('check_social_comments for {} platforms.'.format(len(platform_ids)))

    for platform_id in platform_ids:
        if should_refetch_social_comments(platform_id):
            log.info('Scheduling a forced refetch for social comments for platform: {}'.format(platform_id))
            platform = models.Platform.objects.get(pk=platform_id)
            force_refetch_platform_data.apply_async(args=[platform.id],
                         queue='every_day.fetching.%s' % platform.platform_name,
                         routing_key='every_day.fetching.%s' % platform.platform_name)
        else:
            log.info('Skipping social comments refetch for platform {}. Comment widgets not found.'.format(platform_id))


@task(name='platformdatafetcher.fetchertasks.indepth_fetch_platform_data', ignore_result=True)
@baker.command
def indepth_fetch_platform_data(platform_id, force=False):
    platform = _fetch_platform(platform_id)
    if not platform:
        return
    if platform.indepth_processed and not int(force):
        log.warn('Platform %s already indepth processed, skipping', platform)
        return

    opr = _do_fetch_platform_data(platform, pbfetcher.IndepthPolicy())
    if not opr.is_exception_registered():
        log.info('Successfull execution, setting indepth_processed')
        platform.indepth_processed = True
        platform.save()
    else:
        threshold = MIN_POSTS_NEEDED_FOR_ENABLING_INDEPTH_PROCESSED_FOR_BLOG_PLATFORM if platform.platform_name in models.Platform.BLOG_PLATFORMS else MIN_POSTS_NEEDED_FOR_ENABLING_INDEPTH_PROCESSED_FOR_SOCIAL_PLATFORM
        if models.Posts.objects.filter(platform=platform).count() >= threshold:
            platform.indepth_processed = True
            platform.save()
            return
        if opr.data.get('counts') and \
                (opr.data['counts']['posts_saved'] >= threshold):
            log.info('Error encountered, but %d posts fetched - setting indepth_processed', opr.data['counts']['posts_saved'])
            platform.indepth_processed = True
            platform.save()
        else:
            log.warn('Error encountered and less than %d posts fetched - not setting indepth_processed', threshold)


def submit_platform_task(task_fun, platform):
    policy = pbfetcher.policy_for_platform(platform)
    if policy is None:
        log.error('Cannot submit task because policy is None for %s', platform)
        return
    task_fun.apply_async(args=[platform.id, policy.name],
                         queue='every_day.fetching.%s' % platform.platform_name,
                         routing_key='every_day.fetching.%s' % platform.platform_name)


def submit_platform_task_precomputed(task_fun, platform_id, queue_type, platform_name, policy):
    task_fun.apply_async(args=[platform_id, policy.name],
                         queue=policy.fetcher_queue_name(queue_type, platform_name),
                         routing_key=policy.fetcher_queue_name(queue_type, platform_name))


def submit_indepth_platform_task(task_fun, platform):
    task_fun.apply_async(args=[platform.id], queue='indepth_fetching.%s' % platform.platform_name,
                         routing_key='indepth_fetching.%s' % platform.platform_name)


@baker.command
def generate_supervisord_conf(deployment='daily-fetcher'):
    with open(os.path.join(settings.PROJECT_PATH,
                           '../deployments/%s/files/supervisord.conf.tpl' % deployment)) as tpl_f:
        t = template.Template(tpl_f.read())
    with open(os.path.join(settings.PROJECT_PATH,
                           '../deployments/%s/files/supervisord.conf' % deployment), 'w') as out_f:
        output = t.render(template.Context({'platforms': settings.DAILY_FETCHED_PLATFORMS}))
        out_f.write(output)


def _submit_indepth_tasks_for_influencers(influencers):
    for inf in influencers:
        pls = models.Platform.objects.filter(influencer=inf)
        log.warn('Submitting %s indepth fetch tasks for influencer %s', pls.count(), inf)
        for pl in pls:
            submit_indepth_platform_task(indepth_fetch_platform_data, pl)


@baker.command
def submit_tasks_for_influencers_with_nonnull_source():
    _submit_indepth_tasks_for_influencers(models.Influencer.objects.filter(source__isnull=False))


@baker.command
def submit_tasks_for_trendsetters_not_from_spreadsheet():
    _submit_indepth_tasks_for_influencers(
        models.Influencer.objects.filter(source=None,
                                         shelf_user__userprofile__is_trendsetter=True))


@task(name='platformdatafetcher.fetchertasks.submit_indepth_nightly_tasks', ignore_result=True)
def submit_indepth_nightly_tasks():
    submit_tasks_for_influencers_with_nonnull_source()


@task(name='platformdatafetcher.fetchertasks.fetch_info_from_social_handles', ignore_result=True)
def fetch_info_from_social_handles(inf_id):
    """
    Here, for each of the social handles for the influencer, we find the information contained in the social handles
    and at least 250 posts worth of data (that's why we call indepth processing)
    ===> this is currently called from debra/admin.py for every influencer that passes the manual inspection
    """
    inf = models.Influencer.objects.get(id=inf_id)
    print "Inside fetch_info_from_social_handles for %s " % inf
    with platformutils.OpRecorder('fetch_social_profile_info', influencer=inf):
        plats = inf.platforms().filter(platform_name__in=models.Platform.SOCIAL_PLATFORMS_CRAWLED)
        for platform in plats:
            submit_indepth_platform_task(fetch_platform_data, platform)

REFETCH_MIN_AGE = datetime.timedelta(days=7)
REFETCH_MAX_AGE = datetime.timedelta(days=180)


class RefetchingPolicy(pbfetcher.Policy):

    name = 'refetching'

    def __init__(self, posts):
        self.posts = posts

    def applies_to_platform(self, platform):
        return True

    def perform_fetching(self, fetcher_impl):
        if fetcher_impl.platform.platform_name_is_blog:
            fetcher_impl.fetch_post_interactions_extra(self.posts)
        else:
            fetcher_impl.fetch_post_interactions(self.posts)


@task(name='platformdatafetcher.fetchertasks.try_refetch_comments', ignore_result=True)
def try_refetch_comments(post_id):
    post = models.Posts.objects.get(id=int(post_id))
    with platformutils.OpRecorder(operation='try_refetch_comments', post=post):
        _do_fetch_platform_data(post.platform, RefetchingPolicy([post]))


@baker.command
def submit_try_refetch_comments_tasks(submission_tracker, limit=1000):
    plats = models.Platform.objects.all().searchable_influencer().filter(
                                           platform_name__in=models.Platform.BLOG_PLATFORMS,
                                           total_numcomments__gt=0)
    plats = plats.exclude(influencer__blog_url__contains='theshelf.com/artificial')
    log.info('%d platforms with nonzero total_numcomments', plats.count())
    posts = models.Posts.objects.filter(platform__in=plats,
                create_date__lte=datetime.datetime.now() - REFETCH_MIN_AGE,
                create_date__gte=datetime.datetime.now() - REFETCH_MAX_AGE)

    # !!! optimization - should use denorm_num_comments instead
    posts = posts.exclude(platformdataop__operation='try_refetch_comments')
    posts = posts[:limit]

    for post in posts.iterator():
        if not post.postinteractions_set.all().exists():
            if pbfetcher.policy_for_platform(post.platform) is None:
                log.warn('No policy can be computed for %r', post.platform)
            else:
                log.info('Submitting task try_refetch_comments for post %r', post)
                submission_tracker.count_task('try_refetch_comments')
                try_refetch_comments.apply_async([post.id], queue='platform_data_postprocessing')
    #log.info('%d posts with no post interactions', posts.count())


@task(name='platformdatafetcher.fetchertasks.tmp_calculate_platform_activity_levels', ignore_result=True)
@baker.command
def tmp_calculate_platform_activity_levels(platform_ids):
    for platform_id in platform_ids:
        platform = models.Platform.objects.get(pk=platform_id)
        try:
            platform.calculate_activity_level()
            platform.save()
            log.info("Platform {} calculated new activity level: '{}'".format(
                platform_id, platform.activity_level))
        except:
            log.exception('Error calculating activity level for platform: {}'.format(platform_id))


@task(name='platformdatafetcher.fetchertasks.tmp_submit_refetch_for_influencers', ignore_result=True)
@baker.command
def tmp_submit_refetch_for_influencers(influencer_ids):
    influencers = models.Influencer.objects.filter(pk__in=influencer_ids)
    for influencer in influencers:
        blog = influencer.blog_platform
        if blog:
            fetch_platform_data.apply_async(args=[blog.id],
                         queue='every_day.fetching.Youtube',
                         routing_key='every_day.fetching.Youtube')


if __name__ == '__main__':
    utils.log_to_stderr(['__main__', 'platformdatafetcher', 'xps', 'xpathscraper', 'requests'])
    baker.run()
