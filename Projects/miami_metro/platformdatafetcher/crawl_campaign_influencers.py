from debra.models import BrandJobPost, Influencer, Platform
from platformdatafetcher import platformutils
import logging

from celery.decorators import task

from platformdatafetcher.fetchertasks import fetch_platform_data
from platformdatafetcher.platformutils import TaskSubmissionTracker

log = logging.getLogger('platformdatafetcher.crawl_campaign_influencers')


# These ones must match supervisor worker queues
RECRAWL_CAMPAIGNS_QUEUE_PREFIX = "refetch_campaign_posts"

CAMPAIGN_POSTS_TO_COLLECTIONS_QUEUE = "add_campaign_posts_to_collections"


@task(name='platformdatafetcher.crawl_campaign_influencers.submit_recrawl_campaigns_tasks', ignore_result=True)
def submit_recrawl_campaigns_tasks():
    """
    Task to fetch recent posts for campaign-involved influencers.
    :return:
    """
    with platformutils.OpRecorder(operation='submit_recrawl_campaigns_tasks') as opr:
        tasks_submitted = 0
        submission_tracker = TaskSubmissionTracker()

        # getting platforms for those influencers, blog and social.
        bjps = BrandJobPost.objects.exclude(archived=True)

        for bjp in bjps:

            # fetching influencers involved in campaigns and their autovalidated social and blog platforms
            # inf_ids = list(bjp.candidates.filter(campaign_stage=6).values_list('mailbox__influencer__id', flat=True))
            inf_ids = [iid for iid in list(bjp.candidates.filter(campaign_stage__gte=3).values_list('mailbox__influencer__id', flat=True)) if iid is not None]
            for inf_id in inf_ids:
                try:
                    inf = Influencer.objects.get(id=inf_id)

                    try:
                        blog_platform_id = inf.blog_platform.id
                    except (AttributeError, TypeError):
                        blog_platform_id = None

                    platform_ids = list(inf.platform_set.filter(
                        autovalidated=True
                    ).exclude(
                        url_not_found=True
                    ).values_list(
                        'id', flat=True
                    ))

                    if blog_platform_id is not None:
                        platform_ids.insert(0, blog_platform_id)

                    for plat in Platform.objects.filter(id__in=platform_ids):
                        queue_name = '{}.{}'.format(RECRAWL_CAMPAIGNS_QUEUE_PREFIX, plat.platform_name)

                        submission_tracker.count_task(queue_name)
                        fetch_platform_data.apply_async(
                            args=[plat.id, None],
                            queue=queue_name
                        )

                    tasks_submitted += Platform.objects.filter(id__in=platform_ids).count()
                except Influencer.DoesNotExist:
                    pass

        log.info('Tasks submitted: %s' % tasks_submitted)
        opr.data = {'tasks_submitted': tasks_submitted}


@task(name='platformdatafetcher.crawl_campaign_influencers.add_campaign_posts_to_collection_task', ignore_result=True)
def add_campaign_posts_to_collection_task(campaign_id=None):
    if campaign_id is not None:
        log.info('Performing brandjobpost_posts_to_collections() for campaign id: %s' % campaign_id)
        from debra.elastic_search_helpers import brandjobpost_posts_to_collections
        brandjobpost_posts_to_collections([campaign_id, ])

    else:
        log.error('Campaign id is None')


@task(name='platformdatafetcher.crawl_campaign_influencers.campaign_posts_to_collections_batch_performer', ignore_result=True)
def campaign_posts_to_collections_batch_performer():
    """
    Populates the queue to add campaign posts to collections with tasks
    :return:
    """
    with platformutils.OpRecorder(operation='add_campaign_posts_to_collection') as opr:
        tasks_submitted = 0
        submission_tracker = TaskSubmissionTracker()

        bjp_ids = list(BrandJobPost.objects.exclude(archived=True).values_list('id', flat=True))

        for bjp_id in bjp_ids:
            add_campaign_posts_to_collection_task.apply_async(
                args=[bjp_id, ],
                queue=CAMPAIGN_POSTS_TO_COLLECTIONS_QUEUE
            )

            submission_tracker.count_task(CAMPAIGN_POSTS_TO_COLLECTIONS_QUEUE)
            tasks_submitted += 1

        log.info('Tasks submitted: %s' % tasks_submitted)
        opr.data = {'tasks_submitted': tasks_submitted}
