"""
Global conditions for any influencer:
every influencer should have this:
    Influencer.source != Null
    Influencer.blog_url != Null


Step 1. When we add a new influencer in our database, it should be taken up by the crawlers with New influencer policy (pbfetcher.py)

    New influencer policy
    ======================
    relevant_to_fashion == Null
    show_on_search == Null
    platform__name__in = Platform.BLOG_PLATFORMS


Step 2. Once we have posts for these influencers, they should be run estimation task to check if they are relevant to fashion.

    For evaluating relevant_to_fashion:
    ===================================

    relevant_to_fashion == Null
    show_on_search == Null
    platform__name__in = Platform.BLOG_PLATFORMS
    platform__posts != Null [DIFFERENT FROM ABOVE]


Step 3. Once the influencer is interesting from relevant_to_fashion perspective, we should evaluate if it's active.

    For evaluating is_active:
    ===================
    relevant_to_fashion =  True  [DIFFERENT FROM ABOVE]
    show_on_search == Null
    platform__name__in = BLOGS
    platform__posts != Null


Step 4.
"""



import logging
import datetime
import pprint
import time
import operator
import gc

import baker
from celery.decorators import task
from raven.contrib.django.raven_compat.models import client
from django.db.models import Sum, Q
from django.db import transaction
from debra import db_util
from django.core.mail import mail_admins

from debra import models
from debra import constants
from xpathscraper import utils
from xpathscraper import xutils
from . import fetcher
from . import fetchertasks
from . import platformextractor
from . import platformcleanup
from . import geocoding
from . import blognamefetcher
from . import estimation
from . import pdimport
from . import linkextractor
from . import contenttagging
from . import emailextractor
from . import pbfetcher
from . import blogvisitor
from . import categorization
from .platformutils import (OpRecorder, exclude_influencers_disabled_for_automated_edits,
                            exclude_platforms_disabled_for_automated_edits,
                            save_platforms_from_url_fields, TaskSubmissionTracker)
from hanna import alexa_ranking_fetch
from . import contentclassification, postinteractionsfetcher, brandnamefetcher, fetcherbase, postanalysis
from hanna import import_from_blog_post
from masuka import image_manipulator
from platformdatafetcher import scrapingfetcher
from platformdatafetcher import langdetection
from social_discovery import twitter_crawl, instagram_crawl


log = logging.getLogger('platformdatafetcher.postprocessing')


ERROR_EXECUTIONS_TO_SKIP = 5


# Define a global because submit_postprocessing_task requires it
estimate_if_fashion_blogger = estimation.estimate_if_fashion_blogger


@task(name='platformdatafetcher.postprocessing.create_platforms_from_description', ignore_result=True)
@baker.command
def create_platforms_from_description(platform_id):
    platform = models.Platform.objects.get(id=int(platform_id))
    with OpRecorder('create_platforms_from_description', platform=platform):
        from_desc_pls = fetcher.create_platforms_from_text(platform.description, True)
        for dpl in from_desc_pls:
            if dpl.platform_name in models.Platform.BLOG_PLATFORMS:
                # If it's a duplicate, save() will not save data in the DB
                dpl.influencer = models.Influencer(blog_url=dpl.url)
                dpl.influencer.save()
                dpl.save()
            else:
                appended = dpl.append_to_url_field(platform.influencer)
                if appended:
                    platform.influencer.save()
                    platform.influencer.remove_from_validated_on(constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)


@task(name='platformdatafetcher.postprocessing.create_emails_from_description', ignore_result=True)
@baker.command
def create_emails_from_description(platform_id):
    platform = models.Platform.objects.get(id=int(platform_id))
    with OpRecorder('create_emails_from_description', platform=platform):
        log.info('Emails before extraction: %r', platform.influencer.email)
        emails = emailextractor.extract_emails_from_text(platform.description)
        log.info('Found emails for platform %r: %r', platform, emails)
        for e in emails:
            platform.influencer.append_email_if_not_present(e)
            platform.influencer.save()
        log.info('Emails after extraction: %r', platform.influencer.email)


@task(name='platformdatafetcher.postprocessing.do_denormalize', ignore_result=True)
def do_denormalize(model_class_name, model_id, total_popularity=None, total_engagement=None, denormalization_type='full'):
    cls = getattr(models, model_class_name)
    m = cls.objects.using('default').get(id=model_id)

    opr_kwargs = {'operation': 'denormalize_%s' % model_class_name.lower()}
    if cls == models.Influencer:
        opr_kwargs['influencer'] = m
    elif cls == models.Platform:
        opr_kwargs['platform'] = m
    elif cls == models.Posts:
        opr_kwargs['post'] = m
    else:
        opr_kwargs['spec_custom'] = '%s:%s' % (model_class_name, m.id)

    with OpRecorder(**opr_kwargs):
        log.info('Running denormalization for {!r}, type: {}'.format(m, denormalization_type))
        if cls == models.Influencer:
            if denormalization_type == 'fast':
                m.denormalize_fast(total_popularity_score=total_popularity, total_engagement_score=total_engagement)
            elif denormalization_type == 'slow':
                m.denormalize_slow()
            else: # Defaulting to full denormalization
                m.denormalize(total_popularity_score=total_popularity, total_engagement_score=total_engagement)
        else:
            m.denormalize()
        log.info('Denormalized %r', m)


@task(name='platformdatafetcher.postprocessing.do_redetect_platform_name', ignore_result=True,
      bind=True, max_retries=5, default_retry_delay=6 * 3600)
def do_redetect_platform_name(self, pl_id, do_retry=False):
    pl = models.Platform.objects.get(id=pl_id)
    with OpRecorder('redetect_platform_name', platform=pl):
        platformcleanup.redetect_platform_name(pl, update=True)
        if pl.platform_name is None and do_retry:
            log.warn('platform_name is still None, retrying using celery mechanism')
            self.retry()

TIME_START = datetime.datetime.fromtimestamp(0)


def _order_data_fast(m_query, op, min_days, limit=None):
    if limit is None:
        limit = 999999999
    id_query = m_query.values('id')
    id_sql, id_params = id_query.query.sql_with_params()
    table = m_query.model._meta.db_table
    table_postfix = table.split('_')[1]
    # Plural model names are converted to singular foreign keys by Django...
    table_postfix = table_postfix.rstrip('s')
    q = """
    with m_data as (
        select m.id, (select started from debra_platformdataop pdo
                      where pdo.{table_postfix}_id = m.id
                            and pdo.operation = %s
                      order by started desc limit 1) as latest_started
        from {table} m
        where m.id in ({id_sql})
    )
    select * from m_data
    where (latest_started is null) or (current_timestamp - latest_started >= '{min_days} days'::interval)
    order by latest_started nulls first
    limit %s
    """.format(table=table, id_sql=id_sql, table_postfix=table_postfix, min_days=min_days)
    params = [op] + list(id_params) + [limit]
    log.info('Executing %s with params %r', q, params)
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute(q, params)
    log.info('Done')
    res = [row[0] for row in cur]
    cur.close()
    return res


def _order_data_using_pdo_latest(m_query, op, min_days, limit=None):
    if limit is None:
        limit = 999999999

    op_q = models.OpDict.objects.filter(operation=op)
    if not op_q.exists():
        log.error('No OpDict entry for %r', op)
        return []
    op_id = op_q[0].id

    id_query = m_query.values('id')
    id_sql, id_params = id_query.query.sql_with_params()
    table = m_query.model._meta.db_table
    table_postfix = table.split('_')[1]
    # Plural model names are converted to singular foreign keys by Django...
    table_postfix = table_postfix.rstrip('s')
    q = """
    with m_data as (
        select m.id, pdol.latest_started
        from {table} m
        left join debra_pdolatest pdol on pdol.{table_postfix}_id = m.id
                                          and pdol.operation_id = %s
        where m.id in ({id_sql})
    )
    select * from m_data
    where (latest_started is null) or (current_timestamp - latest_started >= '{min_days} days'::interval)
    order by latest_started nulls first
    limit %s
    """.format(table=table, id_sql=id_sql, table_postfix=table_postfix, min_days=min_days)
    params = [op_id] + list(id_params) + [limit]
    log.info('Executing %s with params %r', q, params)
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute(q, params)
    log.info('Done')
    res = [row[0] for row in cur]
    cur.close()
    return res

_MODEL_FK_TO_INT = {
    'platform_id': 1,
    'influencer_id': 2,
    'product_model_id': 3,
    'post_id': 4,
    'follower_id': 5,
    'post_interaction_id': 6,
    'brand_id': 7,
}
_INT_TO_MODEL_FK = {v: k for k, v in _MODEL_FK_TO_INT.items()}
_MODEL_CLS_TO_FK = {
    models.Platform: 'platform_id',
    models.Influencer: 'influencer_id',
    models.ProductModel: 'product_model_id',
    models.Posts: 'post_id',
    models.Follower: 'follower_id',
    models.PostInteractions: 'post_interaction_id',
    models.Brands: 'brand_id',
}
_OP_DICT = None
_PDOL_DICT = None


def _get_latest_started(op, m_cls, m_id):
    global _OP_DICT
    global _PDOL_DICT
    if _OP_DICT is None:
        _OP_DICT = {x.operation: x.id for x in models.OpDict.objects.all()}
    key = u'%s.%s.%s' % (_OP_DICT[op], _MODEL_FK_TO_INT[_MODEL_CLS_TO_FK[m_cls]], m_id)
    res = _PDOL_DICT.get(key)
    if res is None:
        return None
    d_res = datetime.datetime.fromtimestamp(res[0][0])
    #log.debug('Res for %s %s %s = %s', op, m_cls, m_id, d_res)
    return d_res
    # return res[0][0]


def _order_data_using_in_memory_pdo_latest(m_query, op, min_days, limit=None):
    #import marisa_trie
    import dawg

    @transaction.commit_on_success
    def items_iter():
        connection = db_util.connection_for_reading()
        cur = connection.cursor()
        cur.execute("""DECLARE pcursor CURSOR FOR
                       SELECT platform_id, influencer_id, product_model_id, post_id, follower_id,
                              post_interaction_id, brand_id, operation_id, latest_started
                       FROM debra_pdolatest""")
        # WHERE platform_id=125095 OR influencer_id=33572
        i = 0
        while True:
            i += 1
            log.debug('Fetching %d', i)
            cur.execute("""FETCH 10000 FROM pcursor""")
            rows = cur.fetchall()
            if not rows:
                break
            for row in rows:
                d = {}
                d['platform_id'], d['influencer_id'], d['product_model_id'], d['post_id'], d['follower_id'], \
                    d['post_interaction_id'], d['brand_id'], d['operation_id'], d['latest_started'] = row
                model_int_list = [_MODEL_FK_TO_INT[k] for k in _MODEL_FK_TO_INT if d.get(k)]
                if not model_int_list:
                    continue
                model_int = model_int_list[0]
                model_id = [d[k] for k in _MODEL_FK_TO_INT if d.get(k)][0]
                latest_started_ts = int(time.mktime(d['latest_started'].timetuple()))
                item = (u'%s.%s.%s' % (d['operation_id'], model_int, model_id), (latest_started_ts,))
                #log.debug('item: %s', item)
                yield item

    #trie = marisa_trie.RecordTrie('=i', items_iter())
    global _PDOL_DICT
    if _PDOL_DICT is None:
        _PDOL_DICT = dawg.RecordDAWG('=i', items_iter())

    log.info('Executing query...')
    id_query = m_query.values('id')
    m_ids = [row['id'] for row in id_query]
    log.info('Done')

    log.info('Computing latest_started...')
    m_ids_with_latest_started = [(m_id, _get_latest_started(op, m_query.model, m_id) or TIME_START)
                                 for m_id in m_ids]
    log.info('Done')

    log.info('Filtering for min_days')
    now = datetime.datetime.now()
    min_days_td = datetime.timedelta(days=min_days)
    m_ids_with_latest_started = [(m_id, latest_started) for (m_id, latest_started) in m_ids_with_latest_started
                                 if now - latest_started >= min_days_td]
    log.info('Done')

    log.info('Sorting m_ids...')
    m_ids_with_latest_started.sort(key=operator.itemgetter(1))
    log.info('Done')

    if limit is not None:
        log.info('Limiting %d m_ids to %d', len(m_ids_with_latest_started), limit)
        m_ids_with_latest_started = m_ids_with_latest_started[:limit]

    log.info('All to submit:\n%s', pprint.pformat(m_ids_with_latest_started))

    return [x[0] for x in m_ids_with_latest_started]


def _order_data_without_pdo(m_query, op, min_days, limit=None):
    id_query = m_query.values('id')
    if limit is not None:
        id_query = id_query[:limit]
    return [row['id'] for row in id_query]


###def _order_data_to_process(query, op, min_days):
###    """query should be over Influencer or Platform"""
###    processed_with_date = []
###    for m in query:
###
###        # not ever processed
###        if not m.platformdataop_set.filter(operation=op).exists():
###            processed_with_date.append((m, TIME_START))
###            continue
###
###        # not ever successfully processed, set last_processed to an old date
###        if not m.platformdataop_set.filter(operation=op, error_msg__isnull=True).exists():
###            last_processed = TIME_START
###        # successfully processed, search for last_processed
###        else:
###            last_processed = m.platformdataop_set.filter(operation=op, error_msg__isnull=True).\
###                order_by('-started')[0].started
###
###        recent_errors_q = m.platformdataop_set.filter(operation=op, error_msg__isnull=False,
###                                                      started__gt=last_processed).\
###            exclude(error_msg='old_version')
###        if recent_errors_q.exists():
###            last_error = recent_errors_q.order_by('-started')[0].started
###        else:
###            last_error = TIME_START
###
###        recent_errors_count = recent_errors_q.count()
###
###        if recent_errors_count > 0:
###            # not enough erros to skip this, use last_processed to re-execute it once again
###            if recent_errors_count < ERROR_EXECUTIONS_TO_SKIP:
###                processed_with_date.append((m, last_processed))
###                continue
###            # many recent errors, use last_error to not give a higher priority than for executed tasks
###            log.warn('Multiple errors in a serie for platform operation %r model %r', op, m)
###            try:
###                client.captureMessage('Mutliple errors in a serie for a platorm operation %r' % op,
###                                      extra=dict(model_repr=repr(m)))
###            except:
###                pass
###            processed_with_date.append((m, last_error))
###            continue
###
###        # No recent errors, just use last_processed
###        assert recent_errors_count == 0
###        processed_with_date.append((m, last_processed))
###
###    processed_with_date = [(m, d) for (m, d) in processed_with_date
###                           if datetime.datetime.now() - d >= datetime.timedelta(days=min_days)]
###    processed_with_date.sort(key=lambda (m, d): d)
###    log.info('Tasks with dates:\n%s', pprint.pformat(processed_with_date))
###    processed = [m for (m, d) in processed_with_date]
###    return processed


def order_data(m_query, op, min_days, limit=None):
    # return _order_data_fast(m_query, op, min_days, limit)
    # return _order_data_using_pdo_latest(m_query, op, min_days, limit)
    return _order_data_using_in_memory_pdo_latest(m_query, op, min_days, limit)


def submit_postprocessing_task(task_name, query, min_days,
                               queue='platform_data_postprocessing', limit=None):
    """Submits task ``task_name``, implemented as a function with that name,
    accepting an ``id`` argument that is a primary key of models selected by
    ``query``.

    This function inserts first tasks which weren't yet processed for a
    given platform / influencer. Then, it inserts tasks which weren't processed
    in the last ``min_days``, starting from the one which were processed longest ago.
    """
    task_fun = globals()[task_name]
    data = order_data(query, task_name, min_days, limit)
    for i, m_id in enumerate(data):
        log.debug('Submitting %s for %s %r', task_name, i, m_id)
        task_fun.apply_async(args=[m_id], queue=queue)


@task(name='platformdatafetcher.postprocessing.submit_denormalize_tasks', ignore_result=True)
def submit_denormalize_tasks(submission_tracker, min_days=1, limit_factor=1.0, also_artificial=True, denormalization_type='full'):
    """
    this should be called on all influencers that can potentially turn into show_on_search
    """
    base_q = models.Influencer.objects.filter(blog_url__isnull=False,
                                              source__isnull=False,
                                              blacklisted=False).exclude(source__contains='brands')

    #base_active_q = base_q.manual_or_from_social_contains()
    #if only_show_on_search:
    #    active_q = base_active_q.active_unknown()
    #else:
    #    active_q = base_active_q.active()

    if also_artificial:
        artificial = base_q.filter(blog_url__contains="theshelf.com/artificial")

    qad_q = base_q.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).filter(old_show_on_search=True)

    signedup = base_q.filter(source__icontains='blogger_signup')

    tod = datetime.date.today()
    week = datetime.timedelta(days=7)
    last_week = tod - week

    to_process_q = (signedup | qad_q).filter(last_modified__gte=last_week).distinct()

    #data = order_data(to_process_q, 'denormalize_influencer', min_days)
    data = [i.id for i in to_process_q]
    limit = int(len(data) * float(limit_factor))
    log.info('Limiting %d tasks to %d', len(data), limit)
    total_popularity = models.Platform.objects.filter(influencer__show_on_search=True).exclude(url_not_found=True).aggregate(
        num_followers_total=Sum('num_followers'))['num_followers_total']
    total_engagement = models.Platform.objects.filter(influencer__show_on_search=True).exclude(url_not_found=True).aggregate(
        engagement_overall=Sum('score_engagement_overall'))['engagement_overall']

    for i, inf_id in enumerate(data):
        log.debug('Submitting %d/%d %r', i + 1, len(data), inf_id)
        log.info('total_popularity, total_engagement: %s, %s', total_popularity, total_engagement)

        queue = 'denormalization'
        if denormalization_type == 'slow':
            queue = 'denormalization_slow'

        submission_tracker.count_task('do_denormalize.{}.Influencer'.format(denormalization_type))
        do_denormalize.apply_async(args=['Influencer', inf_id, total_popularity,
                                         total_engagement, denormalization_type],
                                   queue=queue, routing_key=queue)
        if limit is not None and i >= limit:
            log.warn('Limit')
            return


def submit_denormalize_posts_tasks(submission_tracker, limit):
    infs = models.Influencer.objects.filter(show_on_search=True)
    to_process_q = models.Posts.objects.\
        filter(influencer__in=infs).\
        filter(platform_name__in=models.Platform.BLOG_PLATFORMS).\
        filter(Q(denorm_num_comments__isnull=True) | Q(denorm_num_comments=0)).\
        order_by('-create_date')\
        [:limit].\
        values('id')
    #to_process_count = to_process_q.count()
    for i, post in enumerate(to_process_q.iterator()):
        log.debug('Submitting %d %r', i + 1, post)
        submission_tracker.count_task('denormalize_posts')
        do_denormalize.apply_async(args=['Posts', post['id']],
                                   queue='denormalization')
        if limit is not None and i >= limit:
            log.warn('Limit')
            return


@task(name='platformdatafetcher.postprocessing.submit_categorization_for_show_on_search_influencers', ignore_result=True)
@baker.command
def submit_categorization_for_show_on_search_influencers():
    """
    Weekly task to run summary categorization for influencers that show on search
    """
    infs = models.Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True)
    infs = infs.exclude(source__icontains='brands')
    infs = infs.order_by('-score_popularity_overall')

    for i, inf in enumerate(infs):
        log.info('%d. Caclulating category info for inf.id=%s', i, inf.id)
        inf.calculate_category_info()
        inf.save()


def submit_categorization_for_new_infs(submission_tracker):
    """
    Here, we issue categorization for new influencers
    => Avoid influencers that are either showing on search or have been already categorized

    Only let new influencers that have
    a) some posts for them
    b) are not already edited by QA
    c) are not showing on search

    We don't care at this point if they are active or not
    because they might be active on their other social platforms. And we can't evaluate that unless we discover their
    social handles.
    """

    infs = models.Influencer.objects.filter(source__isnull=False, blog_url__isnull=False)
    infs = infs.exclude(blacklisted=True).exclude(show_on_search=True)
    infs = infs.filter(classification='blog')

    # now remove infs that have already been qa-ed
    infs = exclude_influencers_disabled_for_automated_edits(infs)

    # and then remove infs that already got some category already (this means they have been categorized)
    with_cat = infs.has_any_categories()
    with_cat_id = with_cat.values_list('id', flat=True)
    infs = infs.exclude(id__in=with_cat_id)[:50000]

    # now, let's calculate category values
    for i, inf in enumerate(infs):
        log.info('%d. Calculating category info for inf.id=%s', i, inf.id)
        categorization.categorize_influencer.apply_async([inf.id], queue='categorize_influencer')
        submission_tracker.count_task('categorization.new_inf_categorization')


@task(name='platformdatafetcher.postprocessing.submit_fetch_social_handles_task', ignore_result=True)
@baker.command
def submit_fetch_social_handles_task(submission_tracker):
    """
    Now, the second step: we should fetch the social handles of all blogs that are:
    a) not showing up on search,
    b) have not been edited by the admin already
    c) have at least a few posts categorized
    d) and don't have a social handle discovered already
    e) and are not our artificial blogs with blog_url starting with 'http://www.theshelf.com/artificial_blog/'
    """
    infs = models.Influencer.objects.all().valid()

    infs = infs.exclude(show_on_search=True)
    infs = infs.exclude(accuracy_validated=True)
    infs = infs.exclude(blog_url__startswith="http://www.theshelf.com/artificial_blog/")

    infs = infs.remove_problematic()
    infs = infs.remove_self_or_qa_modified()

    # only influencers that have some category
    # TODO :: or if they have sufficient number of followers on a given platform and had good keywords in their posts
    infs_with_category = infs.has_any_categories()
    print("infs_with_category=%d" % infs_with_category.count())
    ids1 = infs_with_category.values_list('id', flat=True)
    infs_from_social = infs.get_quality_influencers_from_social_sources(min_followers_count=500)
    print("infs_from_social=%d" % infs_from_social.count())
    ids2 = infs_from_social.values_list('id', flat=True)

    inf_ids = list(ids1) + list(ids2)

    infs = models.Influencer.objects.filter(id__in=inf_ids)
    print("Total influencers: %d" % infs.count())
    infs_not_discovered, infs_discovered = infs.social_platforms_discovered_status()
    print("Total infs:%d Social Plats not discovered:%d Social Plats discovered:%d" % (infs.count(), infs_not_discovered.count(), infs_discovered.count()))
    for i, inf in enumerate(infs_not_discovered):
        if inf.blog_platform:
            inf.blog_platform.platform_state = models.Platform.PLATFORM_STATE_FETCHING_SOCIAL_HANDLES
            inf.blog_platform.save()
            plat_id = inf.blog_platform.id
            log.info('%d. Submitting extract_platforms_from_platform task for pl.id=%s', i, plat_id)
            submission_tracker.count_task('platformextractor.extract_combined')
            platformextractor.extract_combined.apply_async([plat_id], queue="platform_extraction")


@task(name='platformdatafetcher.postprocessing.submit_cleanup_tasks', ignore_result=True)
@baker.command
def submit_cleanup_tasks(min_days):
    infs = models.Influencer.objects.filter(show_on_search=True)

    infs_ids = order_data(infs, 'cleanup', min_days)
    for i, inf_id in enumerate(infs_ids):
        print "%d %s" % (i, inf_id)
        platformcleanup.cleanup.apply_async(args=[inf_id], queue='platform_data_postprocessing')
        print "\n\n----\n\n"


def submit_fetch_alexa_data_tasks(min_days):
    pls = models.Platform.objects.all().searchable_influencer()
    pls = pls.exclude(influencer__blog_url__contains='theshelf.com/artificial')
    pls_ids = order_data(pls, 'fetch_alexa_data', min_days)
    for i, pl_id in enumerate(pls_ids):
        log.info('%s/%s Submitting task fetch_alexa_data', i, len(pls))
        alexa_ranking_fetch.fetch_alexa_data.apply_async(args=[pl_id], queue='platform_data_postprocessing')


def submit_normalize_location_tasks(submission_tracker, min_days):
    infs = models.Influencer.objects.filter(
        old_show_on_search=True, demographics_location__isnull=False, demographics_locality__isnull=True)
    # infs_ids = order_data(infs, 'normalize_location', min_days, 2500)
    # infs_ids = _order_data_to_process(infs, 'normalize_location', min_days)
    infs_ids = [i.id for i in infs]
    print "We have %d influencers today to find out their normalized location, we should limit this to 2500 per day" % len(infs_ids)
    for i, inf_id in enumerate(infs_ids):
        log.info('%s/%s Submitting task normalize_location', i, len(infs_ids))
        submission_tracker.count_task('geocoding.normalize_location')
        geocoding.normalize_location.apply_async(args=[inf_id], queue='platform_data_postprocessing')


def submit_redetect_platform_name_tasks(submission_tracker, limit, min_days):
    null_pls = models.Platform.objects.filter(
        platform_name__isnull=True, influencer__source__isnull=False, influencer__blacklisted=False)
    null_pls = null_pls.exclude(influencer__blog_url__contains='theshelf.com/artificial')
    #custom_pls = models.Platform.objects.filter(platform_name='Custom')
    blog_pls = exclude_platforms_disabled_for_automated_edits(null_pls)
    pls_ids = [b.id for b in blog_pls]
    for i, pl_id in enumerate(pls_ids):
        log.info('%s/%s Submitting task do_redetect_platform_name', i, len(pls_ids))
        do_redetect_platform_name.apply_async(args=[pl_id], queue='platform_data_postprocessing')
        submission_tracker.count_task('do_redetect_platform_name')


def submit_fetch_blogname_tasks(submission_tracker, limit, min_days):
    blog_pls = models.Platform.objects.all().manual_or_from_social_contains().filter(
        Q(blogname__isnull=True) | Q(blogname__in=['unknown', 'blog', 'Blog', '']),
        platform_name__in=models.Platform.BLOG_PLATFORMS).exclude(influencer__show_on_search=True)
    blog_pls = blog_pls.exclude(influencer__blacklisted=True)
    blog_pls = exclude_platforms_disabled_for_automated_edits(blog_pls)
    blog_pls = blog_pls.exclude(influencer__blog_url__contains='theshelf.com/artificial')
    #blog_pls_ids = order_data(blog_pls, 'fetch_blogname', min_days, limit)
    blog_pls_ids = [b.id for b in blog_pls]
    for i, pl_id in enumerate(blog_pls_ids):
        log.info('%s/%s Submitting task fetch_blogname', i, len(blog_pls_ids))
        submission_tracker.count_task('blognamefetcher.fetch_blogname')
        blognamefetcher.fetch_blogname.apply_async(args=[pl_id], queue='platform_data_postprocessing_blocking')


def submit_extract_emails_from_platform_tasks(submission_tracker, limit, min_days):
    infs = models.Influencer.objects.all().manual_or_from_social_contains().filter(blog_url__isnull=False,
                                            blacklisted=False).exclude(show_on_search=True)
    infs = exclude_influencers_disabled_for_automated_edits(infs)
    infs = infs.exclude(blog_url__contains='theshelf.com/artificial')
    infs = infs.exclude(Q(email__isnull=False) | Q(email_for_advertising_or_collaborations__isnull=False) | Q(email_all_other__isnull=False))
    blog_pls = models.Platform.objects.filter(platform_name__in=models.Platform.BLOG_PLATFORMS,
                                              influencer__in=infs)
    # (ATUL): avoiding order_data everywhere, it's too time consuming
    #blog_pls_ids = order_data(blog_pls, 'extract_emails_from_platform', min_days, limit)
    blog_pls_ids = [b.id for b in blog_pls]
    count = 0
    for i, pl_id in enumerate(blog_pls_ids):
        log.info('%s/%s Submitting task extract_emails_from_platform', i, len(blog_pls_ids))
        submission_tracker.count_task('emailextractor.extract_emails_from_platform')
        emailextractor.extract_emails_from_platform.apply_async(
            args=[pl_id], queue='platform_data_postprocessing_blocking')
        count += 1
        if count > limit:
            break


def submit_indepth_crawling_task():
    # we want to run indepth crawling for only those influencers that
    # have relevant_to_fashion=True
    # TODO: right now we're excluding social platforms from being fetched indepth
    # TODO: do this after we have their non-API based crawlers
    plats = models.Platform.objects.influencer_active().filter(
        influencer__relevant_to_fashion__isnull=False,
        indepth_processed=False).exclude(platform_name__in=models.Platform.SOCIAL_PLATFORMS)
    for plat in plats:
        fetchertasks.submit_indepth_platform_task(fetchertasks.indepth_fetch_platform_data, plat)


def submit_brand_classification_tasks(submission_tracker):
    for brand in models.Brands.objects.filter(classification__isnull=True, date_edited__isnull=True):
        submission_tracker.count_task('contentclassification.classify_model')
        contentclassification.classify_model.apply_async(kwargs={'brand_id': brand.id},
                                                         queue='platform_data_postprocessing_blocking')


def submit_brand_discover_name_tasks(submission_tracker):
    for brand in models.Brands.objects.filter(name__contains='.com', date_edited__isnull=True).exclude(supported=True).order_by('id'):
        submission_tracker.count_task('blognamefetcher.fetch_brand_name')
        brandnamefetcher.fetch_brand_name.apply_async(kwargs={'brand_id': brand.id},
                                                      queue='platform_data_postprocessing')


def submit_update_url_if_redirected_tasks(submission_tracker, limit, min_days):
    pls = models.Platform.objects.all().for_task_processing().filter(platform_name__in=models.Platform.BLOG_PLATFORMS)
    pls = pls.exclude(influencer__blog_url__contains='theshelf.com/artificial')
    pls_ids = order_data(pls, 'update_url_if_redirected', min_days, limit)
    for i, pl_id in enumerate(pls_ids):
        submission_tracker.count_task('platformcleanup.update_url_if_redirected')
        platformcleanup.update_url_if_redirected.apply_async(args=[pl_id, False], queue='platform_data_postprocessing')


def submit_import_from_blogger_profile_tasks(limit, min_days):
    start = datetime.date(2014, 5, 1)
    # to_process_q = models.Follower.objects.filter(url__contains='blogger.com',
    #        postinteractions__post__influencer__shelf_user__userprofile__is_trendsetter=True).distinct()
    infs = models.Influencer.objects.filter(show_on_search=True).order_by('-score_popularity_overall')
    to_process_q = models.Follower.objects.filter(url__contains='blogger.com',
                                                  postinteractions__post__influencer__in=infs,
                                                  postinteractions__create_date__gte=start).distinct()
    count = to_process_q.count()
    if count < 100:
        log.warn(
            "submit_import_from_blogger_profile_tasks:: VERY SMALL # OF TASKS (%d) ISSUED, NEED TO UPDATE " % count)
    log.info('Processing %s rows', count)
    to_process = order_data(to_process_q, 'import_from_pi', min_days, limit)
    for i, m_id in enumerate(to_process):
        log.debug('Submitting %d/%d %r', i + 1, count, m_id)
        pdimport.import_from_blogger_profile.apply_async(args=[m_id, True], queue='pdimport')


def submit_import_from_blog_url_tasks(limit, min_days):
    start = datetime.date(2014, 5, 1)
    # Check all influencers that have wordpress or blogspot in their urls
    # (later on: make it more generic so that we can pick any)
    # Excluding platformdataop__... is an optimization:
    # there are too many to process in memory directly
    infs = models.Influencer.objects.filter(show_on_search=True).order_by('-score_popularity_overall')
    to_process_q = models.Follower.objects.filter(Q(url__contains='.wordpress.com') | Q(url__contains='blogspot.com'),
                                                  postinteractions__post__influencer__in=infs,
                                                  postinteractions__create_date__gte=start).\
        exclude(platformdataop__operation='import_from_pi').\
        distinct()
    count = to_process_q.count()
    log.info('Processing %s rows', count)
    if count < 100:
        log.warn(
            "submit_import_from_blogger_profile_tasks:: VERY SMALL # OF TASKS (%d) ISSUED, NEED TO UPDATE " % count)
    to_process = order_data(to_process_q, 'import_from_pi', min_days, limit)
    for i, m_id in enumerate(to_process):
        log.debug('Submitting %d/%d %r', i + 1, count, m_id)
        pdimport.import_from_blog_url.apply_async(args=[m_id, True], queue='pdimport')


def submit_import_from_comment_content_tasks(limit, min_days):
    start = datetime.date(2014, 5, 1)

    trendsetters = models.Influencer.objects.filter(show_on_search=True)
    to_process_q = models.PostInteractions.objects.\
        filter(post__influencer__in=trendsetters, post__platform__platform_name__in=models.Platform.BLOG_PLATFORMS,
               create_date__gte=start).\
        exclude(platformdataop__operation='import_from_comment_content').distinct()
    count = to_process_q.count()
    log.info('Processing %s rows', count)
    to_process = order_data(to_process_q, 'import_from_comment_content', min_days, limit)
    for i, m_id in enumerate(to_process):
        log.debug('Submitting %d/%d %r', i + 1, count, m_id)
        pdimport.import_from_comment_content.apply_async(args=[m_id, True], queue='pdimport')


def submit_import_from_post_content_tasks(limit, min_days):
    start = datetime.date(2014, 5, 1)

    infs = models.Influencer.objects.filter(show_on_search=True)
    to_process_q = models.Posts.objects.\
        filter(influencer__in=infs, platform__platform_name__in=models.Platform.BLOG_PLATFORMS,
               create_date__gte=start).\
        order_by('-post__create_date')
    count = to_process_q.count()
    log.info('Processing %s rows', count)
    to_process = order_data(to_process_q, 'import_from_post_content', min_days, limit)
    for i, m_id in enumerate(to_process):
        log.debug('Submitting %d/%d %r', i + 1, count, m_id)
        pdimport.import_from_post_content.apply_async(args=[m_id, True], queue='pdimport')


def submit_import_from_pi_tasks(limit, min_days):
    return
    submit_import_from_blogger_profile_tasks(limit=limit // 3, min_days=min_days)
    submit_import_from_blog_url_tasks(limit=limit // 3, min_days=min_days)
    submit_import_from_comment_content_tasks(limit=limit // 3, min_days=min_days)
    #submit_import_from_post_content_tasks(limit=limit // 4, min_days=min_days)


def submit_extract_common_links_from_platform_tasks(submission_tracker, limit, min_days):
    pls = models.Platform.objects.all().searchable_influencer().filter(
        platform_name__in=models.Platform.BLOG_PLATFORMS)
    pls = pls.exclude(influencer__blog_url__contains='theshelf.com/artificial')
    #to_process = order_data(pls, 'extract_common_links_from_platform', min_days, limit)
    to_process = [p.id for p in pls]
    for pl_id in to_process:
        submission_tracker.count_task('linkextractor.extract_common_links_from_platform')
        linkextractor.extract_common_links_from_platform.apply_async(args=[pl_id],
                                                                     queue='platform_data_postprocessing')


def submit_extract_hire_me_links_tasks(submission_tracker, limit, min_days):
    pls = models.Platform.objects.all().searchable_influencer().filter(platform_name__in=models.Platform.BLOG_PLATFORMS)
    #to_process = order_data(pls, 'extract_hire_me_links', min_days, limit)
    pls = pls.exclude(influencer__blog_url__contains='theshelf.com/artificial')
    to_process = [p.id for p in pls]
    for pl_id in to_process:
        submission_tracker.count_task('linkextractor.extract_hire_me_links')
        linkextractor.extract_hire_me_links.apply_async(args=[pl_id],
                                                        queue='platform_data_postprocessing')


def submit_product_import_tasks(submission_tracker, limit=10000, only_search_influencers=False):
    """
    issue tasks to fetch products from posts
    --- we give high priority for posts from existing users that show up on search
    --- then the new influencers that have potential to show up on search
    """
    start = datetime.date(2014, 1, 1)

    # let's first issue tasks for influencers that joined us via signup
    plats = models.Platform.objects.filter(
        influencer__source__contains='blogger_signup', platform_name__in=models.Platform.BLOG_PLATFORMS + ['Tumblr'])
    for p in plats:
        submission_tracker.count_task('import_from_blog_post.fetch_prods_from_all_recent_posts')
        import_from_blog_post.fetch_prods_from_all_recent_posts.apply_async(
            [p.id, start], queue="import_products_from_post_latest")

    posts_with_shelf_user = models.Posts.objects.select_related('influencer__shelf_user')
    if only_search_influencers:
        posts = posts_with_shelf_user.filter(influencer__show_on_search=True)
    else:
        posts = posts_with_shelf_user.influencer_active().filter(
            influencer__relevant_to_fashion__isnull=False,
        ).exclude(influencer__show_on_search=True)
    posts = posts.filter(create_date__gte=start)
    posts = posts.filter(products_import_completed__isnull=True)
    # No filtering for blog platforms only

    posts = posts.order_by('-create_date')
    #print "fetch_products_from_posts:::: We have %d posts, issuing %d " % (posts.count(), limit)
    for p in posts[:limit]:
        print p.id
        submission_tracker.count_task('import_from_blog_post.fetch_products_from_post')
        import_from_blog_post.fetch_products_from_post.apply_async(
            [p.id, p.influencer.shelf_user.id if p.influencer.shelf_user else None], queue="import_products_from_post_latest")


def submit_scrape_platform_data_tasks(submission_tracker, limit, min_days):
    """
    This method is designed specifically for users who we're unable to get their data through APIs (they might have
    blocked it). So, we wrote a scraper to get this info.
    """
    plats = models.Platform.objects.all().manual_or_from_social_contains().filter(platform_name='Instagram',
                                           validated_handle__isnull=False,
                                           url_not_found=False,
                                           num_followers__isnull=True)
    count = plats.count()
    log.info('Processing %s rows', count)
    #to_process = order_data(plats, 'scrape_data', min_days, limit)
    to_process = [p.id for p in plats]
    for i, m_id in enumerate(to_process):
        log.debug('Submitting %d/%d %r', i + 1, count, m_id)
        submission_tracker.count_task('scrapingfetcher.scrape_platform_data')
        scrapingfetcher.scrape_platform_data.apply_async([m_id], queue='platform_data_postprocessing')


def submit_detect_platform_lang_tasks(submission_tracker, limit, min_days):
    plats = models.Platform.objects.filter(platform_name__in=models.Platform.BLOG_PLATFORMS,
                                           influencer__show_on_search=True,
                                           content_lang__isnull=True)
    plats = plats.exclude(influencer__blog_url__contains='theshelf.com/artificial')
    #count = plats.count()
    #log.info('Processing %s rows', count)
    #to_process = order_data(plats, 'detect_platform_lang', min_days, limit)
    to_process = [p.id for p in plats]
    for i, m_id in enumerate(to_process):
        log.debug('Submitting %d %r', i + 1, m_id)
        submission_tracker.count_task('langdetection.detect_platform_lang')
        langdetection.detect_platform_lang.apply_async([m_id], queue='platform_data_postprocessing')


def submit_post_image_upload_tasks(submission_tracker, limit):
    """
    Submit a task to find appropriate image for the post (used during display in the front-end)
    """
    start = datetime.date(2015, 1, 1)
    q = models.Posts.objects.filter(post_image__isnull=True,
                                    influencer__show_on_search=True, create_date__gte=start)[:limit]
    for i, post in enumerate(q):
        log.debug('Submitting %d/%d %r', i + 1, limit, post)
        submission_tracker.count_task('image_manipulator.upload_post_image_task')
        image_manipulator.upload_post_image_task.apply_async([post.id], queue='post_image_upload_worker')


def submit_detect_dead_blog_tasks(submission_tracker, min_days, limit):
    infs = models.Influencer.objects.all().manual_or_from_social().filter(blacklisted=False)
    infs = infs.exclude(blog_url__contains='theshelf.com/artificial')
    to_process = order_data(infs, 'detect_dead_blog', min_days, limit)
    for i, m_id in enumerate(to_process):
        submission_tracker.count_task('platformcleanup.detect_dead_blog')
        platformcleanup.detect_dead_blog.apply_async([m_id], queue='platform_data_postprocessing')


def submit_autovalidate_platform_tasks(submission_tracker, min_days, limit):
    infs = models.Influencer.objects.all().manual_or_from_social().filter(blacklisted=False)
    plats = models.Platform.objects.filter(influencer__in=infs,
                                           autovalidated__isnull=True,
                                           platform_name__in=models.Platform.SOCIAL_PLATFORMS).\
        exclude(url_not_found=True)[:limit]
    for i, m_id in enumerate(plats.iterator()):
        submission_tracker.count_task('platformextractor.autovalidate_platform')
        platformextractor.autovalidate_platform.apply_async([None, m_id], queue='platform_data_postprocessing')


def submit_bad_brand_urls():
    blogspot = models.Brands.objects.filter(domain_name__icontains='blogspot.')
    tumblr = models.Brands.objects.filter(domain_name__icontains='tumblr.')

    # First, blackslist these instances because they are not brands
    blogspot.filter(blacklisted=False).update(blacklisted=True)
    tumblr.filter(blacklisted=False).update(blacklisted=True)

    # Now, blogspot instance need to be converted into influencers if they make sense
    # only pass those instances that have not been through this before
    bb = blogspot.exclude(platformdataop__brand__isnull=False, platformdataop__operation='import_from_bad_brand')
    for b in bb:
        pdimport.create_influencer_from_bad_brands.appy_async([b.id], queue="platform_data_postprocessing")


def show_influencers_on_qa_tables(submission_tracker):
    """
    Here we upgrade influencers once they have enough data to be shown on the QA tables for validation
    """
    query = models.Influencer.objects.all().valid()

    query = query.exclude(show_on_search=True)
    query = query.exclude(accuracy_validated=True)

    query = query.remove_problematic()
    query = query.remove_self_or_qa_modified()    

    # tighter controls so that bad urls don't go through
    # 1. the url is live => this is guaranteed by checking for classification = 'blog' because it requires posts
    # 2. prioritize these
    #    2.2 at least 10 posts are categorized
    from social_discovery import create_influencers
    good_quality_from_social = query.get_quality_influencers_from_social_sources(1000)
    good_quality_from_social_ids = list(good_quality_from_social.values_list('id', flat=True))
    good_quality_from_social = models.Influencer.objects.filter(id__in=good_quality_from_social_ids)
    # find ones that are already classified as a blog
    good_quality_from_social_blog = good_quality_from_social.filter(classification='blog')
    good_quality_from_social_others = good_quality_from_social.exclude(classification='blog')
    # for the ones that are not classified as a blog, check if their instagram profiles have more clues
    valid_profiles = create_influencers.find_valid_influencers_with_instagram_profiles(good_quality_from_social_others)
    ids1 = list(set(valid_profiles.values_list('id', flat=True)))
    ids0 = list(set(good_quality_from_social_blog.values_list('id', flat=True)))

    query = query.filter(classification='blog')
    at_least_some_categorized = query.categorized_posts_more_than(20)
    ids2 = list(set(at_least_some_categorized.values_list('id', flat=True)))

    ids = ids0 + ids1 + ids2
    at_least_some_categorized = models.Influencer.objects.filter(id__in=ids)

    # at least social platforms discovery operation was called
    infs_not_extracted, infs_extracted = at_least_some_categorized.social_platforms_discovered_status()

    query = infs_extracted

    # now run influencerattributeselector
    from . import influencerattributeselector
    for q in query:
        influencerattributeselector.AutomaticAttributeSelector(q, to_save=True)
        submission_tracker.count_task('influencerattributeselector.AutomaticAttributeSelector')
    query.update(accuracy_validated=True)
    print "got %d ids " % query.count()


def check_blacklist_sync():
    """
    Here, we make sure that everytime a blogger is added to a collection with name "Blacklist --", it's marked
    blacklisted=True.
    """
    from django.core.mail import mail_admins
    coll = models.InfluencersGroup.objects.filter(name__contains='Blacklist --')
    all_infs = []
    for c in coll:
        i = c.influencers
        all_infs.extend(i)
    all_infs_ids = [i.id for i in all_infs]
    all_infs = models.Influencer.objects.filter(id__in=all_infs_ids)
    not_yet_blacklisted = all_infs.exclude(blacklisted=True)
    print("Not yet blacklisted: %d" % not_yet_blacklisted.count())
    for n in not_yet_blacklisted:
        c = n.groups.filter(name__contains='Blacklist --')
        if c.count() == 1:
            c = c[0]
            n.set_blacklist_with_reason(c.name)
        else:
            print("Problem: %s belongs to %s collections" % (n, c))

    if not_yet_blacklisted.count() == 0:
        mail_admins('SUCCESS: All Blacklisted Influencers Are In Sync', "These %d influencers had problems with blacklisted flag." % not_yet_blacklisted.count())
    else:
        mail_admins('PROBLEM: Some Blacklisted Influencers Are Not In Sync', "These %d influencers had problems with blacklisted flag." % not_yet_blacklisted.count())

@task(name='platformdatafetcher.postprocessing.submit_daily_postprocessing_tasks', ignore_result=True)
@baker.command
def submit_daily_postprocessing_tasks():
    """
    We first submit the daily crawler tasks, and then issue the daily post processing tasks.
    """
    try:
        # first fix the blacklist synch
        check_blacklist_sync()
    except:
        log.info("Exception happened in check_blacklist_sync")
        pass

    try:
        submission_tracker = TaskSubmissionTracker()
        with submission_tracker.total():
            with submission_tracker.operation('submit_daily_fetch_tasks_activity_levels'):
                pbfetcher.submit_daily_fetch_tasks_activity_levels(submission_tracker)
            gc.collect()
            print("Done with GC")
            with submission_tracker.operation('submit_daily_social_platform_update_tasks'):
                pbfetcher.submit_daily_social_platform_update_tasks(submission_tracker)
            gc.collect()
            print("Done with GC")
            with OpRecorder('submit_daily_postprocessing_tasks'):
                with submission_tracker.operation('_do_submit_daily_postprocessing_tasks'):
                    _do_submit_daily_postprocessing_tasks(submission_tracker)
            gc.collect()
            print("Done with GC")
        report_body = submission_tracker.generate_report()
        mail_admins('Daily task submission report', report_body)
    except Exception:
        log.exception('Error submitting daily tasks')


def _do_submit_daily_postprocessing_tasks(submission_tracker):
    log.info('submit_daily_postprocessing_tasks() starts running')

    # Clear caching dicts
    global _OP_DICT
    global _PDOL_DICT
    _OP_DICT = None
    _PDOL_DICT = None

    with OpRecorder(operation='submit_redetect_platform_name_tasks', propagate=False):
        with submission_tracker.operation('submit_redetect_platform_name_tasks'):
            submit_redetect_platform_name_tasks(submission_tracker, limit=10000, min_days=15)

    log.info('submit_fetch_social_handles_task() started')
    with OpRecorder(operation='submit_fetch_social_handles_task', propagate=False):
        with submission_tracker.operation('submit_fetch_social_handles_task'):
            submit_fetch_social_handles_task(submission_tracker)

    log.info('submit_visit_influencer_tasks() started')
    with OpRecorder(operation='submit_visit_influencer_tasks', propagate=False):
        with submission_tracker.operation('submit_visit_influencer_tasks'):
            blogvisitor.submit_visit_influencer_tasks(submission_tracker)

    log.info('submit_normalize_location_tasks() started')
    with OpRecorder(operation='submit_normalize_location_tasks', propagate=False):
        with submission_tracker.operation('submit_normalize_location_tasks'):
            submit_normalize_location_tasks(submission_tracker, 60)

    log.info('submit_scrape_platform_data_tasks() started')
    with OpRecorder(operation='submit_scrape_platform_data_tasks', propagate=False):
        with submission_tracker.operation('submit_scrape_platform_data_tasks'):
            submit_scrape_platform_data_tasks(submission_tracker, limit=5000, min_days=3)

    today = datetime.date.today()
    if today.weekday() == 5:
        log.info('submit_detect_platform_lang_tasks() started')
        with OpRecorder(operation='submit_detect_platform_lang_tasks', propagate=False):
            with submission_tracker.operation('submit_detect_platform_lang_tasks'):
                submit_detect_platform_lang_tasks(submission_tracker, limit=10000, min_days=180)

    log.info('submit_compute_pts_num_comments_tasks() started')
    with OpRecorder(operation='submit_compute_pts_num_comments_tasks', propagate=False):
        with submission_tracker.operation('submit_compute_pts_num_comments_tasks'):
            submit_compute_pts_num_comments_tasks(submission_tracker, limit=10000, min_days=7)


    log.info('submit_try_refetch_comments_tasks() started')
    with OpRecorder(operation='submit_try_refetch_comments_tasks', propagate=False):
        with submission_tracker.operation('submit_try_refetch_comments_tasks'):
            fetchertasks.submit_try_refetch_comments_tasks(submission_tracker, limit=5000)

    today = datetime.date.today()
    if today.weekday() == 5:
        # both these two tasks will use the blocking queued
        log.info('submit_fetch_blogname_tasks() started')
        with OpRecorder(operation='submit_fetch_blogname_tasks', propagate=False):
            # Retry every 5 days if blogname is still null
            with submission_tracker.operation('submit_fetch_blogname_tasks'):
                submit_fetch_blogname_tasks(submission_tracker, limit=10000, min_days=5)

        log.info('submit_extract_emails_from_platform_tasks() started')
        with OpRecorder(operation='submit_extract_emails_from_platform_tasks', propagate=False):
            with submission_tracker.operation('submit_extract_emails_from_platform_tasks'):
                submit_extract_emails_from_platform_tasks(submission_tracker, limit=50000, min_days=90)

        with OpRecorder(operation='show_influencers_on_qa_tables', propagate=False):
            with submission_tracker.operation('show_influencers_on_qa_tables'):
                show_influencers_on_qa_tables(submission_tracker)

    #log.info('submit_autovalidate_platform_tasks() started')
    #with OpRecorder(operation='submit_autovalidate_platform_tasks', propagate=False):
    #    with submission_tracker.operation('submit_autovalidate_platform_tasks'):
    #        submit_autovalidate_platform_tasks(submission_tracker, limit=1000, min_days=90)




    log.info('submit_denormalize_tasks() started')
    # Now, we should run denormalize tasks: those who are already active, we should run it once every week
    # and those are not yet active, we should run today
    with OpRecorder(operation='submit_denormalize_tasks', propagate=False):
        # temporarity disable this doign during the week
        #with submission_tracker.operation('submit_denormalize_fast_tasks'):
        #    submit_denormalize_tasks(submission_tracker, 1, 1.0, without_is_active=True, denormalization_type='fast')
        #    submit_denormalize_tasks(submission_tracker, 1, 1.0 / 7.0, without_is_active=False, denormalization_type='fast')

        # Temporarily disable denormalize_slow tasks -- causing DB performance problems
        today = datetime.date.today()
        if today.weekday() in (5,):
            # Queue slow denormalization tasks to run only over the weekend: Sat/Sun
            log.info('Submiting denormalize_slow tasks...')
            with submission_tracker.operation('submit_denormalize_slow_tasks'):
                submit_denormalize_tasks(submission_tracker, 1, 1.0, also_artificial=False, denormalization_type='slow')
                #submit_denormalize_tasks(submission_tracker, 1, 1.0 / 2.0, without_is_active=False, denormalization_type='slow')


    today = datetime.date.today()
    if today.weekday() == 5:
        # issue classification for urls so that we can mark them blacklisted
        with OpRecorder(operation='submit_content_classification', propagate=False):
            with submission_tracker.operation('submit_content_classification'):
                contentclassification.submit_classify_model_and_fetch_blogname_tasks(submission_tracker)

        log.info('submit_categorization_for_new_infs() started')
        with OpRecorder(operation='submit_categorization_for_new_infs', propagate=False):
            with submission_tracker.operation('submit_categorization_for_new_infs'):
                submit_categorization_for_new_infs(submission_tracker)

    today = datetime.date.today()
    if today.weekday() == 5:
        from debra import influencer_checks
        influencer_checks.check_crawling_tasks()
        influencer_checks.check_import_categorization_tasks()
        influencer_checks.check_flow_of_influencers()

    log.info('issue_task_to_update_popularity_charts() started')
    issue_task_to_update_popularity_charts()

    log.info('submit_reanalyze_social_posts_tasks() started')
    with OpRecorder(operation='submit_reanalyze_social_posts_tasks', propagate=False):
        with submission_tracker.operation('submit_reanalyze_social_posts_tasks'):
            submit_reanalyze_social_posts_tasks(submission_tracker)

    return



@task(name='platformdatafetcher.postprocessing.generate_health_report', ignore_result=True)
def generate_health_report():
    log.info('Submitting Generate Health Report task')
    models.HealthReport.daily_update()


@task(name='platformdatafetcher.postprocessing.denormalize_brands', ignore_result=True)
def denormalize_brands():
    log.info('Submitting Denormalize Brands task')
    for brand in models.Brands.objects.all():
        brand.denormalize()


def fetch_disqus_interactions_for_missing_posts():
    infs = models.Influencer.objects.filter(show_on_search=True)
    blog_plats = models.Platform.objects.filter(influencer__in=infs,
                                                platform_name__in=models.Platform.BLOG_PLATFORMS).exclude(url_not_found=True)
    posts = models.Posts.objects.filter(platform__in=blog_plats, postinteractions__isnull=True)
    total = posts.count()
    print "We have %d posts to review " % total
    have_disqus_comments = set()
    for i, p in enumerate(posts):
        if postinteractionsfetcher.url_contains_disqus_iframe(p.url):
            with OpRecorder(post=p, operation='fetch_disqus_comments'):
                arg = [p]
                postinteractionsfetcher.disqus_for_post_list.apply_async(
                    args=[arg, True], queue="fetch_disqus_comments")
            have_disqus_comments.add(p)
            print "This url %s has disqus comments " % p.url
        else:
            print "no, this url %s has no disqus " % p.url
        print "[%d/%d/%.2f] [%d]\n\n" % (i, total, i * 100.0 / total, len(have_disqus_comments))
    print "Got %d posts that have disqus iframe in it" % len(have_disqus_comments)


def process_more_frequently_new_blogs():
    # find influencers that have no posts
    infs = models.Influencer.objects.filter(source__isnull=False, blog_url__isnull=False)

    # now, fetch their posts
    infs_no_posts = infs.filter(posts__isnull=True).exclude(relevant_to_fashion__isnull=False)
    plats = models.Platform.objects.filter(
        influencer__in=infs_no_posts, platform_name__in=models.Platform.BLOG_PLATFORMS)
    print "Submitted %d tasks for fetching posts " % plats.count()
    for pl in plats:
        fetchertasks.submit_platform_task(fetchertasks.fetch_platform_data, pl)

    # now, check if they have posts, then evaluate if they are ready to be checked for relevant_to_fashion
    infs_w_posts = infs.filter(posts__isnull=False).exclude(relevant_to_fashion__isnull=False).distinct()
    print "Submitted %d for fashion estimatino" % infs_w_posts.count()
    for m in infs_w_posts:
        estimate_if_fashion_blogger.apply_async(args=[m.id], queue='platform_data_content_estimation')

    # now, these who are relevant_to_fashion=True but is_alive == None, denormalize() them
    infs_not_active = infs.active_unknown().filter(relevant_to_fashion=True).distinct()
    print "Submitted %d tasks for evaluating is_active " % infs_not_active.count()
    for i in infs_no_posts:
        i.posts_count = i.calc_posts_count()
        i.is_active = i.calc_is_active()
        i.save()

    # for those that are active and relevant to fashion but have not been touched for platform for extraction, start
    infs = models.Influencer.objects.active().filter(source__isnull=False,
                                            blog_url__isnull=False,
                                            relevant_to_fashion=True).exclude(show_on_search=True)
    infs = exclude_influencers_disabled_for_automated_edits(infs)
    plats = models.Platform.objects.filter(influencer__in=infs, platform_name__in=models.Platform.BLOG_PLATFORMS).exclude(
        platformdataop__operation='extract_platforms_from_platform')

    plats = plats.distinct()
    print "Found %d platform extraction tasks, we'll only submit at most 2000 tasks" % plats.count()

    for pl in plats[:2000]:
        platformextractor.extract_combined.apply_async([pl.id], queue="platform_extraction")

    # now run denormalization for those influencers that have everything
    infs = models.Influencer.objects.active().filter(source__isnull=False,
                                            relevant_to_fashion=True,
                                            platform__profile_img_url__isnull=False, profile_pic_url__isnull=False).exclude(show_on_search=True)
    infs = exclude_influencers_disabled_for_automated_edits(infs)
    infs = infs.distinct()
    total_popularity = models.Platform.objects.filter(influencer__show_on_search=True).aggregate(
        num_followers_total=Sum('num_followers'))['num_followers_total']
    total_engagement = models.Platform.objects.filter(influencer__show_on_search=True).aggregate(
        engagement_overall=Sum('score_engagement_overall'))['engagement_overall']
    print "Submitting %d denorm tasks " % infs.count()
    for inf in infs:
        do_denormalize.apply_async(args=['Influencer', inf.id, total_popularity, total_engagement],
                                   queue='denormalization')


def check_consistency_of_social_handles():
    """
    This checks that we have 1:1 mapping between Influencer.fb_url and Platform with the url and influencer
    TODO: need review by Artur
    """
    infs = models.Influencer.objects.filter(
        show_on_search=True, validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    problem_infs = set()
    field_names = ['fb_url', 'pin_url', 'tw_url', 'insta_url']
    for i in infs[:1]:
        for field in field_names:
            if getattr(i, field, None):
                urls = getattr(i, field, None).split()
                for url in urls:
                    plat = models.Platform.objects.filter(
                        influencer=i, url=url, validated_handle__isnull=False).exclude(url_not_found=True)
                    if not plat.exists():
                        problem_infs.add(str(i.id) + " " + i.blog_url + " " + url)
    return problem_infs


def create_missing_plats():
    """
    TODO ::: need re-view by Artur

    """
    from debra import admin
    infs = models.Influencer.objects.filter(
        show_on_search=True, validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    field_names = ['fb_url', 'pin_url', 'tw_url', 'insta_url']
    for i, inf in enumerate(infs):
        print i
        for field in field_names:
            if getattr(inf, field, None):
                urls = getattr(inf, field, None)
                admin.handle_social_handle_updates(inf, field, urls)


def denormalize_influencers(query):
    total_popularity = models.Platform.objects.filter(influencer__show_on_search=True).\
        aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']
    total_engagement = models.Platform.objects.filter(influencer__show_on_search=True).\
        aggregate(engagement_overall=Sum('score_engagement_overall'))['engagement_overall']
    for q in query:
        try:
            do_denormalize('Influencer', q.id,
                           total_popularity=total_popularity, total_engagement=total_engagement)

        except Exception as e:
            log.exception('While denormalize_influencers: %s' % e, extra={'q': q})


def upgrade_qa_influencers():
    """
    automatically upgrade influencers to show on search if they have been QA-ed

    what steps do bloggers go through once they are QA-ed:
    a) we might get a new facebook or pinterest url => this will be then created into a platform object and then crawled
        to find the picture and # of followers
        --> only this is asynchronous operation and we need to wait for this to complete before we can upgrade a blogger

    TODO: review the enable_show_on_search function as well as create_userprof() method on the Influencer model
    """
    total_popularity = models.Platform.objects.filter(influencer__show_on_search=True).\
        aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']
    total_engagement = models.Platform.objects.filter(influencer__show_on_search=True).\
        aggregate(engagement_overall=Sum('score_engagement_overall'))['engagement_overall']

    query = models.Influencer.objects.all().valid()
    query = query.exclude(show_on_search=True)
    query = query.remove_problematic()
    query = query.stage_qaed()

    # first using the influencers that we discovered from Instagram
    from social_discovery import create_influencers
    #good_quality_from_social = query.get_quality_influencers_from_social_sources(1000)
    valid_profiles = create_influencers.find_valid_influencers_with_instagram_profiles(query)
    valid_profiles_ids = list(valid_profiles.values_list('id', flat=True))
    query = models.Influencer.objects.filter(id__in=valid_profiles_ids)
    # for the remaining ones, find which ones have an autovalidated platform that contains some signal about it being a 
    # a blogger in our verticals
    #remaining_query = query.exclude(id__in=valid_profiles_ids)


    # make sure they have some categorized posts
    query = query.filter(classification='blog')

    # make sure their social handles are consistent & then set the profile pic
    from debra import admin_helpers
    to_upgrade = set()
    for q in query:
        # if there is a duplicate exist for this influencer, mark it's source to none and go to the next influencer
        if models.Influencer.find_duplicates(q.blog_url, q.id):
            q.source = None
            q.save()
            continue
        admin_helpers.handle_social_handle_updates(q, 'fb_url', q.fb_url)
        admin_helpers.handle_social_handle_updates(q, 'pin_url', q.pin_url)
        admin_helpers.handle_social_handle_updates(q, 'tw_url', q.tw_url)
        admin_helpers.handle_social_handle_updates(q, 'insta_url', q.insta_url)
        admin_helpers.handle_social_handle_updates(q, 'youtube_url', q.youtube_url)
        q.set_profile_pic()
        # set activity level
        q.calculate_activity_level()
        q.save()
        to_upgrade.add(q.id)
        print("Going to upgrade %d influencers" % len(to_upgrade))

    print "%d are candidates " % len(to_upgrade)

    query = models.Influencer.objects.filter(id__in=to_upgrade, profile_pic_url__isnull=False)
    print "%d have pictures" % query.count()

    # now we should call the enable_show_on_search()
    for q in query:
        with OpRecorder(operation='enable_show_on_search', influencer=q, propagate=False) as opr:
            res = q.enable_show_on_search()
            opr.data = {'res': res}
            do_denormalize('Influencer',
                           q.id,
                           total_popularity=total_popularity,
                           total_engagement=total_engagement,
                           denormalization_type='fast')


def upgrade_from_alpha_to_production():
    infs = models.Influencer.objects.filter(show_on_search=True).exclude(old_show_on_search=True)
    infs = infs.exclude(blacklisted=True).exclude(blog_url__icontains='theshelf.com')
    infs = infs.filter(profile_pic_url__isnull=False)

    plats = models.Platform.objects.filter(influencer__in=infs).exclude(url_not_found=True)
    plats_autovalidated = plats.filter(autovalidated=True)

    # first find influencers that have influencer keywords in their description
    # this means that they are at least influencers
    from social_discovery import blog_discovery
    influencer_keywords = blog_discovery.influencer_keywords
    plats_with_keywords = plats_autovalidated.filter(reduce(lambda x, y: x | y, [Q(description__icontains=keyword) for keyword in influencer_keywords]))
    infs_blogger = set(plats_with_keywords.values_list('influencer', flat=True))
    infs_blogger = models.Influencer.objects.filter(id__in=infs_blogger)

    # second, find influencers that have rstyle or other affiliate networking widgets
    # I used search on the front end to use ES to find more relevant people from the set above
    # 3.5K satisfied these out of 25K.




def cleanup_non_relevant_influencers():
    """
    We should run this periodically to cleanup
    Influencer.objects.filter(relevant_to_fashion=False)

    For these influencers, we want to delete: (we want to keep the influencer object so that we don't create the duplicate
    and don't waste resources)
        All platforms (has FK to influencer)
        All posts (has FK to platform and influencer)
        All post interactions (has FK to post)
        All followers (has FK to post interactions)
        All ProductModelShelfMaps (has FK to influencer, posts, product_model)
        All PlatformDataOp (has FK to influencer, platform, posts, product_model, follower)

    We should also delete all xpath related tables for price-tracking
    We should also remove indexes that are not used
    """
    infs = models.Influencer.objects.filter(relevant_to_fashion=False)
    print "We have %d influencers that can be removed" % infs.count()


def start_custom_blogs():
    """
    for all english speaking custom blogs, we can start to crawl them and see what the results look like
    """
    #TODO: not called
    plat = models.Platform.objects.filter(influencer__source='spreadsheet_import',
                                          platform_name='Custom',
                                          content_lang='en')  # flake8: noqa


@baker.command
def mark_as_old_version(operation):
    """Force re-execution of a given operation recorded in PlatformDataOp
    by setting error_msg to 'old_version'. After it submit_daily_postprocessing_tasks()
    will treat all the data as not processed yet.
    """
    q = models.PlatformDataOp.objects.filter(operation=operation,
                                             error_msg__isnull=True)
    print 'Updating %d PlatformDataOp records with operation %r' % (q.count(), operation)
    q.update(error_msg='old_version')


@task(name="platformdatafetcher.postprocessing.send_pdo_stats_email", ignore_result=True)
def send_pdo_stats_email():
    from debra import admin
    admin.send_pdo_stats_email()


@task(name="platformdatafetcher.postprocessing.send_daily_posts_stats_email", ignore_result=True)
def send_daily_posts_stats_email():
    from debra import admin
    admin.send_daily_posts_stats_email()


@task(name="platformdatafetcher.postprocessing.compute_pts_num_comments", ignore_result=True)
def compute_pts_num_comments(platform_id):
    platform = models.Platform.objects.get(id=int(platform_id))
    with OpRecorder(operation='compute_pts_num_comments', platform=platform) as opr:
        _do_compute_pts_num_comments(platform)


def _do_compute_pts_num_comments(platform):
    if not platform.posts_set.all().exists():
        log.warn('No posts for platform %r', platform)
        return

    last_pts_q = models.PopularityTimeSeries.objects.filter(platform=platform,
                                                            num_comments__isnull=False).\
        order_by('-snapshot_date')
    if last_pts_q.exists():
        last_pts = last_pts_q[0]
        if datetime.datetime.now() - last_pts.snapshot_date < datetime.timedelta(days=7):
            log.warn('PopularityTimeSeries with num_comments which is younger than 7 days '
                     'already exists for platform %r', platform)
            # return
    else:
        last_pts = None

    if last_pts is not None:
        from_date = last_pts.snapshot_date
    else:
        oldest_post = platform.posts_set.order_by('create_date')[0]
        from_date = oldest_post.create_date

    while True:
        to_date = from_date + datetime.timedelta(days=7)
        log.debug('from_date, to_date: %r %r', from_date, to_date)
        if to_date >= datetime.datetime.now():
            break
        posts = platform.posts_set.filter(create_date__gte=to_date - datetime.timedelta(days=30))
        num_posts = posts.count()
        log.debug('num_posts: %s', num_posts)
        if num_posts == 0:
            log.info('No posts for that period (30 days lookback)')
        else:
            total_comments = models.PostInteractions.objects.filter(post__in=posts).count()
            log.debug('total_comments: %s', total_comments)
            pts = models.PopularityTimeSeries.objects.create(influencer=platform.influencer,
                                                             platform=platform,
                                                             snapshot_date=to_date,
                                                             num_comments=float(total_comments) / num_posts)
            log.info('Created: %r', pts)
        from_date = from_date + datetime.timedelta(days=7)


def submit_compute_pts_num_comments_tasks(submission_tracker, limit, min_days):
    plats = models.Platform.objects.filter(platform_name__in=models.Platform.BLOG_PLATFORMS,
                                           influencer__show_on_search=True)
    #count = plats.count()
    #log.info('Processing %s rows', count)
    #to_process = order_data(plats, 'compute_pts_num_comments', min_days, limit)
    for i, m in enumerate(plats):
        #log.info('Submitting %d/%d %r', i + 1, count, m_id)
        submission_tracker.count_task('compute_pts_num_comments')
        compute_pts_num_comments.apply_async([m.id], queue='platform_data_postprocessing')


def submit_analyze_post_content_tasks(limit, min_days):
    plats = models.Platform.objects.all().searchable_influencer().\
        exclude(platform_name__in=models.Platform.BLOG_PLATFORMS)
    posts = models.Posts.objects.filter(platform__in=plats)
    max_age = datetime.datetime.now() - datetime.timedelta(days=5)
    posts = posts.filter(create_date__lte=max_age)
    to_process = order_data(posts, 'analyze_post_content', min_days, limit)
    for i, m_id in enumerate(to_process):
        log.debug('Submitting %d/%d %r', i + 1, len(to_process), m_id)
        postanalysis.analyze_post_content.apply_async([m_id], queue='platform_data_postprocessing')


def submit_reanalyze_social_posts_tasks(submission_tracker, min_days=3, min_age_days=0, max_age_days=7):
    """
    We submit this task to identify brands, hashtags, mentions for social posts.
    This is dependent on one thing: if a social post, such as a pin, contains a link to a blog
    post and that post being processed for products and brands.

    Currently we don't have a simple way to identify relationships between posts, so we do something
    hacky. We issue re-analysis of posts after 2 days it's created and until 14 days it's created.
    This makes it likely that the blog post that it points to is in the database and is processed.

    TODO: a better mapping between social posts and blog posts.
    """
    plats = models.Platform.objects.all().searchable_influencer().\
        exclude(platform_name__in=models.Platform.BLOG_PLATFORMS).exclude(url_not_found=True)
    posts = models.Posts.objects.filter(platform__in=plats)
    max_dt = datetime.datetime.now() - datetime.timedelta(days=min_age_days)
    min_dt = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
    posts = posts.filter(create_date__gte=min_dt, create_date__lte=max_dt)[:100000]
    #posts_ids = order_data(posts, 'analyze_post_content', min_days)
    for i, m in enumerate(posts):
        log.debug('Submitting %d %r', i + 1, m.id)
        submission_tracker.count_task('postanalysis.analyze_post_content')
        postanalysis.analyze_post_content.apply_async([m.id], queue='platform_data_postprocessing')

    del posts


def submit_tag_influencer_tasks(limit, min_days):
    infs = models.Influencer.objects.all().searchable()
    infs_ids = order_data(infs, 'tag_influencer', min_days, limit)
    for i, m_id in enumerate(infs):
        log.debug('Submitting %d/%d %r', i + 1, len(infs), m_id)
        contenttagging.tag_influencer.apply_async([m_id, True], queue='platform_data_postprocessing')


def submit_check_if_copyrightable_content_tasks(submission_tracker, limit, min_days):
    infs = models.Influencer.objects.all().searchable()
    infs_ids = order_data(infs, 'check_if_copyrightable_content', min_days, limit)
    for i, m_id in enumerate(infs):
        log.debug('Submitting %d/%d %r', i + 1, len(infs), m_id)
        submission_tracker.count_task('contentclassification.check_if_copyrightable_content')
        contentclassification.check_if_copyrightable_content.apply_async([m_id], queue='platform_data_postprocessing')


class FetchAllPolicy(pbfetcher.Policy):
    # Reuse api keys for the other policy
    name = 'relevanttofashion'

    def applies_to_platform(self, platform):
        return True

    def perform_fetching(self, fetcher_impl):
        posts = fetcher_impl.fetch_posts(max_pages=2)


@task(name='platformdatafetcher.postprocessing.update_popularity_charts', ignore_result=True)
def update_popularity_charts(platform_id):
    """
    Here we instantiate the fetcher and call the method to populate the popularity time series.
    """
    plat = models.Platform.objects.get(id=platform_id)
    f = fetcher.fetcher_for_platform(plat, policy=FetchAllPolicy())
    f._update_popularity_timeseries()
    log.info("Platform %r time series data is updated" % plat)


def issue_task_to_update_popularity_charts():
    """
    Here, we run a simple task that makes sure that we are fetching our platform's follower counts data at least
    once per week for everyone.
    """
    infs = models.Influencer.objects.filter(old_show_on_search=True).exclude(blacklisted=True).exclude(source__contains='brands')

    plats = models.Platform.objects.filter(influencer__in=infs, platform_name__in=models.Platform.SOCIAL_PLATFORMS_CRAWLED).exclude(url_not_found=True)

    # let's do twitter the last because it can block
    tod = datetime.date.today()
    delta = datetime.timedelta(days=15)
    threshold = tod - delta
    plats_updated_within_threshold = models.PopularityTimeSeries.objects.filter(platform__in=plats, snapshot_date__gte=threshold).distinct('platform')
    plat_ids_updated_within_threshold = plats_updated_within_threshold.values_list('platform__id', flat=True)

    not_processed_within_threshold = plats.exclude(id__in=plat_ids_updated_within_threshold)
    not_processed_within_threshold_count = not_processed_within_threshold.count()
    # we are splitting twitter and facebook because they can block and we want them to be the last

    twitter = not_processed_within_threshold.filter(platform_name='Twitter')
    facebook = not_processed_within_threshold.filter(platform_name='Facebook')
    twitter_ids = twitter.values_list('id', flat=True)
    facebook_ids = facebook.values_list('id', flat=True)


    all_others = not_processed_within_threshold.exclude(pk__in=twitter).exclude(pk__in=facebook)
    all_others_ids = all_others.values_list('id', flat=True)

    for i,p in enumerate(all_others_ids):
        update_popularity_charts.apply_async([p], queue='social_update_popularity_charts')

    for i,p in enumerate(facebook_ids):
        update_popularity_charts.apply_async([p], queue='social_update_popularity_charts')

    for i,p in enumerate(twitter_ids):
        update_popularity_charts.apply_async([p], queue='social_update_popularity_charts')

    log.info("Total of %d platforms didn't have a time series chart in the last 15 days" % not_processed_within_threshold_count)


@task(name='platformdatafetcher.postprocessing.process_new_influencer_sequentially', ignore_result=True,
      bind=True, soft_time_limit=3 * 3600, time_limit=3 * 3600 + 120, max_retries=3, default_retry_delay=3600)
@baker.command
def process_new_influencer_sequentially(self, influencer_id, assume_blog=True):
    influencer = models.Influencer.objects.get(id=int(influencer_id))
    log.info('process_new_influencer_sequentially called for %r', influencer)
    with OpRecorder(operation='process_new_influencer_sequentially', influencer=influencer) as opr:
        res = _do_process_new_influencer_sequentially(self, influencer, assume_blog)
        opr.data = {'res': res}


def _do_process_new_influencer_sequentially(self, influencer, assume_blog=True):
    if influencer.source is None:
        log.error('source is None for %r', influencer)
        return False
    if not influencer.blog_url:
        log.error('blog_url is empty for %r', influencer)
        return False
    blog_platform = influencer.blog_platform
    if not blog_platform:
        log.error('no blog platform for %r', influencer)
        return False

    def refresh():
        return models.Influencer.objects.get(id=influencer.id)

    if assume_blog:
        influencer.classification = 'blog'
        influencer.blacklisted = False
        influencer.append_validated_on(constants.ADMIN_TABLE_INFLUENCER_LIST)
        influencer.save()
    else:
        contentclassification.classify_model(influencer_id=influencer.id)
        influencer = refresh()
        if influencer.classification != 'blog':
            log.error('Invalid content classification %r for %r', influencer.classification, influencer)
            return False

    influencer = refresh()

    # # fetch blog posts
    #  try:
    #    fetchertasks.fetch_platform_data(influencer.blog_platform.id, policy_instance=FetchAllPolicy())
    # except:
    #     log.exception('While fetching data for %r blog platform', influencer)

    influencer = refresh()
    # if not blog_platform.posts_set.exists():
    #     log.error('No posts after fetching data for blog platform %r, stopping', blog_platform)
    #     #self.retry()
    #     #return False

    # do not fetch anything for our fake blogs
    if not 'theshelf.com' in influencer.blog_url:
        try:
            platformextractor.extract_combined(blog_platform.id)
        except:
            log.exception('While platform extraction for %r', blog_platform)
            return False

        influencer = refresh()
        try:
            blognamefetcher.fetch_blogname(blog_platform.id)
        except:
            log.exception('While fetch_blogname')
        for plat in influencer.platform_set.exclude(url_not_found=True).exclude(id=influencer.blog_platform.id):
            try:
                if 'twitter.com' in plat.url.lower() or plat.platform_name not in models.Platform.SOCIAL_PLATFORMS_CRAWLED:
                    continue
                if plat.validated_handle:
                    # that means we already have processed this, so no need to fetch
                    continue
                _ = fetcher.fetcher_for_platform(plat, FetchAllPolicy())
                # this will just instantiate the platform and get the stats and profile image
            except:
                log.exception('While fetching data for %r', plat)

        influencer = refresh()
        # now issue fetching for these platforms
        plats = models.Platform.objects.filter(influencer=influencer).exclude(url_not_found=True)
        counter = pbfetcher.TaskCounter()
        tracker = TaskSubmissionTracker()
        pbfetcher._do_submit_daily_fetch_tasks(counter, tracker, plats, queue_type='customer_uploaded')

        from . import influencerattributeselector
        influencerattributeselector.AutomaticAttributeSelector(influencer, to_save=True)

        try:
            influencer.denormalize()
        except:
            log.exception('While denormalize')

        log.info('Finalized all tasks, final attrs: %s', influencer.__dict__)
    else:
        log.info('Not extracting platform or fetching blog name for %s' % influencer.blog_url)


    return True


############################################################################################################
##### Below are one-time functions to set source url for pinterest #########################################
############################################################################################################
def set_pin_source_all():
    plats = models.Platform.objects.filter(influencer__relevant_to_fashion__isnull=False, platform_name='Pinterest')
    for p in plats:
        set_pin_source.apply_async([p.id], queue="every_day.fetching.Pinterest")


class FetchPostInteractionsForPostsPolicy(pbfetcher.DefaultPolicy):

    def __init__(self, posts):
        self.posts = posts

    def perform_fetching(self, fetcher_impl):
        fetcher_impl.fetch_post_interactions(self.posts)


@task(name="platformdatafetcher.postprocessing.set_pin_source", ignore_result=True)
@baker.command
def set_pin_source(platform_id):
    platform = models.Platform.objects.get(id=platform_id)
    posts = models.Posts.objects.filter(platform=platform, pin_source__isnull=True)
    log.info("For %s, we have %d pins" % (platform, posts.count()))
    fetchertasks.fetch_platform_data(platform_id,
                                     policy_instance=FetchPostInteractionsForPostsPolicy(posts))


def set_post_pic_in_twitter():
    plats = models.Platform.objects.filter(
        influencer__relevant_to_fashion__isnull=False, platform_name='Twitter').exclude(url_not_found=True)
    for p in plats:
        set_post_pic.apply_async([p.id], queue="every_day.fetching.Twitter")


class FetchPostsPolicy(pbfetcher.DefaultPolicy):

    def perform_fetching(self, fetcher_impl):
        fetcher_impl.fetch_posts(max_pages=10)


@task(name="platformdatafetcher.postprocessing.set_post_pic", ignore_result=True)
@baker.command
def set_post_pic(platform_id):
    fetchertasks.fetch_platform_data(platform_id, policy_instance=FetchPostsPolicy())


@task(name="platformdatafetcher.postprocessing.set_instagram_caption", ignore_result=True)
@baker.command
def set_instagram_caption(platform_id):
    from platformdatafetcher.socialfetcher import InstagramFetcher
    platform = models.Platform.objects.get(id=int(platform_id))
    instagram = InstagramFetcher._create_instagram()
    insta_posts = models.Posts.objects.filter(api_id__isnull=False,
                                              platform=platform,
                                              post_image__isnull=True)
    log.info('%d posts', insta_posts.count())
    for post in insta_posts.iterator():
        try:
            media = instagram.media(post.api_id)
            post.content = InstagramFetcher._content_from_media(instagram, media)
            log.info('Set content %r for post %r' % (post.content, post))
            post.post_image = "done"  # abusing this for storing info that this was processed, will remove it later
            post.save()
        except fetcherbase.FetcherCallLimitException as exc:
            to_sleep = exc.seconds_to_wait()
            log.exception('FetcherCallLimitException, sleeping for %s', to_sleep)
            time.sleep(to_sleep)
        except:
            log.exception('While processing post %r', post)
            time.sleep(5)


@task(name="platformdatafetcher.postprocessing.redirect_shopstyle_product_model", ignore_result=True)
@baker.command
def redirect_shopstyle_product_model(product_model_id):
    pmsm = models.ProductModelShelfMap.objects.get(id=int(product_model_id))
    product_model = pmsm.product_model
    pmsm.affiliate_prod_link = product_model.prod_url

    with OpRecorder('redirect_shopstyle_product_model', product_model=product_model):
        log.info('Processing %r %d', product_model, product_model.id)
        redirected = xutils.resolve_redirect_using_xbrowser(product_model.prod_url, to_sleep=8)
        log.info('Redirected to %r from %r', redirected, product_model.prod_url)
        product_model.prod_url = redirected
        product_model.save()
        pmsm.save()


@task(name="platformdatafetcher.postprocessing.tmp_submit_is_active_denormalize", ignore_result=True)
@baker.command
def tmp_submit_is_active_denormalize(influencer_ids):
    for inf_id in influencer_ids:
        log.info('Submitting {} influencers for is_active denormalization.'.format(len(influencer_ids)))
        # HACK: use the Youtube queue since it's likely empty
        do_denormalize.apply_async(args=['Influencer', inf_id],
                                   queue='every_day.fetching.Youtube',
                                   routing_key='every_day.fetching.Youtube')


@baker.command
def submit_redirect_shopstyle_product_model_tasks():
    prods = models.ProductModelShelfMap.objects.filter(product_model__prod_url__startswith='http://www.shopstyle.com')
    log.info('Products: %d', prods.count())
    for prod in prods:
        redirect_shopstyle_product_model.apply_async(args=[prod.id], queue='platform_data_postprocessing')

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
