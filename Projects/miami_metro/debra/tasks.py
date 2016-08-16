from functools import wraps
import logging
import sys
import time
import datetime
import traceback

from celery.exceptions import SoftTimeLimitExceeded
from celery.decorators import task
from celery.signals import task_postrun

from xpathscraper import utils
from django.core.cache import get_cache
from django.db.models import Q
import json
from django.conf import settings


log = logging.getLogger('debra.tasks')
mc_cache = get_cache('memcached')

REPORT_TO_EMAILS = [
    {'email': 'atul@theshelf.com', 'type': 'to'},
]

from mailsnake import MailSnake
mailsnake_client = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')


@task(name="debra.tasks.update_influencer_show_on_search")
def update_influencer_show_on_search(influencer_id):
    # late import models to avoid circular imports on boot
    from debra import models

    influencer = models.Influencer.objects.get(pk=influencer_id)
    influencer.update_posts_show_on_search()


def retry_when_time_limit_exceeded(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except SoftTimeLimitExceeded as exc:
            args[0].retry(exc=exc)
    return wrapper


### If MIAMI_DEBUG_MEMORY environment flag is set to 1,
### after each celry task execution a summary table will
### be printed listing types and number of objects
### allocated/deallocated during task execution

if utils.env_flag('MIAMI_DEBUG_MEMORY'):
    sys.stderr.write('Registering task memory checker\n')

    from pympler import tracker

    tracker = tracker.SummaryTracker()
    tracker.diff()

    @task_postrun.connect
    def task_postrun_handler(sender=None, body=None, **kwargs):
        sys.stderr.write('Printing memory usage diff\n')
        tracker.print_diff()


def refetch_moz_data_for_platforms(start_id=None, end_id=None, moz_access_id=None, moz_secret_key=None):
    """
    Refetches all MOZ data for Blog non-artificial platforms.
    :param queryset:
    :return:
    """
    # TODO: envelop it in task and schedule it to once per month
    from debra.models import Platform
    from social_discovery.blog_discovery import queryset_iterator
    import time

    ctr = 0

    platforms = Platform.objects.filter(
        platform_name__in=Platform.BLOG_PLATFORMS,
        influencer__show_on_search=True,
        id__gte=start_id,
        id__lte=end_id,
    ).exclude(
        url_not_found=True
    ).exclude(
        url__startswith='http://www.theshelf.com/artificial_blog/'
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        moz_domain_authority__gte=0
    ).order_by('id')

    # for pl in queryset_iterator(platforms):
    #
    #     # if pl.influencer.score_popularity_overall is None:
    #     #     continue
    #
    #     pl.refetch_moz_data()
    #     ctr += 1
    #     print('%s  updated platform %s (%s / %s / %s)' % (
    #         ctr,
    #         pl.id,
    #         pl.moz_domain_authority,
    #         pl.moz_page_authority,
    #         pl.moz_external_links,
    #     ))
    #
    #     if ctr % 1000 == 0:
    #         log.info('Updated moz data for %s platforms' % ctr)
    #
    #     time.sleep(11)

    for pl in queryset_iterator(platforms):
        # if pl.influencer.score_popularity_overall is not None:
        #     continue

        pl.refetch_moz_data(moz_access_id, moz_secret_key)
        ctr += 1
        print('%s  updated platform %s (%s / %s / %s)' % (
            ctr,
            pl.id,
            pl.moz_domain_authority,
            pl.moz_page_authority,
            pl.moz_external_links,
        ))

        if ctr % 1000 == 0:
            log.info('Updated moz data for %s platforms' % ctr)

        time.sleep(11)

    log.info('Finished updating moz data for %s platforms' % ctr)


@task(name="debra.tasks.update_bloggers_cache_data")
def update_bloggers_cache_data(item_ids=None, mute_notifications=False,
        enabled_tasks=None, chunksize=100, to_run=True, to_check=False,
        to_fix=False):
    from debra.cache_utils import *

    if not enabled_tasks:
        enabled_tasks = [
            'tagNames', 'profilePics', 'threadSubjects', 'platformDicts',
            'platformEngagementToFollowersRatio', 'uniquePostAnalayticsIds',]

    params = dict(item_ids=item_ids, enabled_tasks=enabled_tasks,
        mute_notifications=mute_notifications, chunksize=chunksize)

    updaters = [
        CampaignCacheUpdater(),

        LocationsCacheUpdater(),
        LongLocationsCacheUpdater(),
        TopLocationsCacheUpdater(),
        InfluencerTagsCacheUpdater(),
        BrandTagsCacheUpdater(),
        SystemCollectionsCacheUpdater(),
        TagInfluencersCacheUpdater(),
        
        BloggersCacheUpdater(**params),
        # @todo: decide if we're going to use this
        # PostAnalyticsCollectionUpdater(**params),
        TagNamesCacheUpdater(**params),
        MailProxyCacheUpdater(**params),
        MailProxyCountsCacheUpdater(**params),
        PlatformStatsCacheUpdater(**params),
    ]

    if to_run:
        for updater in updaters:
            updater.run()

    if to_check or to_fix:
        for updater in updaters:
            for task in updater._tasks:
                updater.check(task, fix=to_fix)


@task(name="debra.tasks.run_db_denormalization")
def run_db_denormalization(model_names=None):
    from debra import models
    if model_names:
        model_classes = [getattr(models, model_name)
            for model_name in model_names]
    else:
        model_classes = filter(None, [m.get_model()
            for _, m in models.DenormalizationManagerMixin.get_subclasses()
        ])
    print '* detected the following models:'
    print model_classes
    
    for model_class in model_classes:
        model_class.objects.run_denormalization()
    

def fix_pinterest_post_date_generic(inf_id=None, access_token=None):
    """
    Task which fixes pinterest post date (the future ones).
    :return:
    """
    from debra.models import Posts, Influencer
    from platformdatafetcher.pinterest_api import BasicPinterestFetcher
    from dateutil import parser
    from debra.constants import ELASTICSEARCH_URL, ELASTICSEARCH_INDEX
    from es_requests import make_es_get_request

    if inf_id is None:
        log.error('Post id is None, skipping')

    if access_token is None:
        log.error('Access_token id is None, skipping')

    # fetching post ids for this influencer
    post_url = "%s/%s/post/_search?scroll=1m" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    scroll_url = "%s/_search/scroll?scroll=1m" % ELASTICSEARCH_URL

    es_rq = {
        "filter": {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "influencer",
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "terms": {
                                                "influencer.influencer_id": [inf_id, ]
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    {
                        "range": {
                            "create_date": {
                                "gte": "now"
                            }
                        }
                    },
                    {
                        "terms": {
                            "platform_name": [
                                "Pinterest"
                            ]
                        }
                    }
                ]
            }

        },
        "size": 500,
        "from": 0,
        "_source": {
            "exclude": [],
            "include": [
                "_id"
            ]
        }
    }

    # Populating lists
    should_request = True
    scroll_token = None
    post_ids = []

    while should_request:
        if scroll_token is None:
            rq = make_es_get_request(
                es_url=post_url,
                es_query_string=json.dumps(es_rq)
            )
        else:
            rq = make_es_get_request(
                es_url=scroll_url,
                es_query_string=scroll_token
            )

        resp = rq.json()

        scroll_token = resp.get("_scroll_id", None)
        hits = resp.get('hits', {}).get('hits', [])

        if len(hits) == 0:
            should_request = False
        else:

            for hit in hits:
                try:
                    post_id = int(hit.get('_id', None))
                    post_ids.append(post_id)
                except:
                    pass

    # performing all post ids
    bpf = BasicPinterestFetcher(access_token)

    posts_fixed = 0
    for post_id in post_ids:
        try:
            p = Posts.objects.get(id=post_id)
            if p.platform_name == 'Pinterest':

                if p.create_date < datetime.datetime.now():
                    # if dates are not in sync, we just set it for reindexing
                    p.last_modified = datetime.datetime.now()
                    p.save()
                    posts_fixed += 1
                    log.info('Post %s was not in sync in index, scheduled it for reindexing' % post_id)
                    continue

                data = bpf.get_pin_data(p.api_id)
                if data is not None:
                    error = data.get('error', None)
                    pin_date = data.get('data', None)
                    if pin_date:
                        pin_date = pin_date.get('created_at', None)
                        if pin_date:
                            pin_date = parser.parse(pin_date)
                            p.create_date = pin_date
                            p.last_modified = datetime.datetime.now()
                            p.save()
                            posts_fixed += 1
                        else:
                            log.error('API did not return date for post %s' % post_id)
                    elif error == 'Pin was not found':
                        log.error('API returned pin abscence for post %s, setting date to 2000-01-01' % post_id)
                        p.create_date = datetime.datetime(2000, 1, 1)
                        p.last_modified = datetime.datetime.now()
                        p.save()
                        posts_fixed += 1
                    else:
                        log.error('API returned no data element for post %s' % post_id)
                else:
                    log.error('API returned nothing for post %s' % post_id)
                    posts_fixed += 1
            else:
                log.error('Post %s is not for Pinterest platform, skipped.' % post_id)

        except Posts.DoesNotExist:
            log.error('Post %s does not exist in DB' % post_id)

    if posts_fixed > 0:
        try:
            inf = Influencer.objects.get(id=inf_id)
            inf.last_modified = datetime.datetime.now()
            inf.save()
            log.info('Influencer\'s %s last_modified set to today (%s pins dates fixed).' % (inf_id, posts_fixed))
        except Influencer.DoesNotExist:
            log.error('Influencer %s does not exist in DB' % inf_id)


@task(name="debra.tasks.fix_pinterest_post_date_1")
def fix_pinterest_post_date_1(inf_id):
    fix_pinterest_post_date_generic(inf_id, access_token="AdwiM2ClD7HzMmcRvkjvU4ZnSsidFFI1k120cPlDH2XLi-Au2wAAAAA")

@task(name="debra.tasks.fix_pinterest_post_date_2")
def fix_pinterest_post_date_2(inf_id):
    fix_pinterest_post_date_generic(inf_id, access_token="AXWwYKS94fri6ogWA4FRrPglpvARFFI2IOmk9DNDH2b03aBBjQAAAAA")

@task(name="debra.tasks.fix_pinterest_post_date_3")
def fix_pinterest_post_date_3(inf_id):
    fix_pinterest_post_date_generic(inf_id, access_token="AbQDDsd_zbUYr9ip99j-h_NHGxAgFFI2NbtP06dDH2XLi-Au2wAAAAA")



@task(name="debra.tasks.send_fetched_platforms_report", ignore_result=True)
def send_fetched_platforms_report():
    """
    Sends a daily report about performed platforms.
    :return:
    """
    from debra.mongo_utils import report_maker, report_maker2
    # sending an email

    report = report_maker2()

    html_report = """
    <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
    <html lang="en"><head></head><body>%s</body></html>
    """ % report

    if html_report:
        mailsnake_client.messages.send(message={
            'html': html_report,
            'subject': 'Daily fetched platforms report',
            'from_email': 'atul@theshelf.com',
            'from_name': 'Daily fetched platforms report',
            'to': REPORT_TO_EMAILS}
        )


def normalize_influencer_locations():
    from debra import models
    from platformdatafetcher import geocoding
    from social_discovery.blog_discovery import queryset_iterator

    # 96761 bloggers
    infs = models.Influencer.objects.filter(old_show_on_search=True).exclude(
        source__contains='brand').exclude(blacklisted=True)
    total = infs.count()
    changed_count = 0
    for n, inf in enumerate(queryset_iterator(infs), start=1):
        print '******* {}/{} *******'.format(n, total)
        changed_count += int(bool(geocoding.handle_influencer_demographics(inf, diff_only=True)))
        print '(changed count: {})'.format(changed_count)


# def normalize_demographics_localities(infs):
#     from debra import models
#     from aggregate_if import Count

#     locs = infs.values('demographics_locality').annotate(
#         count=Count('demographics_locality'))
#     empty_locs = locs.filter(count=0)

#     return locs
