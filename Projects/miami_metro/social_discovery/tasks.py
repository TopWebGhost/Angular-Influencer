import logging
from datetime import datetime, time, timedelta, date
from pydoc import locate

import baker
from celery import task

from settings import MAX_INSTAGRAM_REFETCH_RETRY_COUNT
from social_discovery import pipelines
from social_discovery.blog_discovery import hashtags as bd_hashtags
from social_discovery.crawler_task import crawler_task
from social_discovery.creators import CreatorByInstagramHashtags
from social_discovery.pipeline_constants import REPROCESS_PROFILES_QUEUE_NAME
from xpathscraper import utils

"""
This file contains Celery tasks for InstagramProfile pipeline.
"""

log = logging.getLogger('social_discovery.tasks')


def _create_profiles_from_instagram_hashtags(
    hashtags_keys=None, pipeline_class_name=None, submission_tracker=None,
    num_pages_to_load=20
):
    """
    Helper method for create profiles tasks
    :param hashtags_keys:  an iterable of bd_hashtags keys to get tags from
    :type hashtags_keys:  tuple of strings
    :param pipeline_class_name:
    :type pipeline_class_name: string
    :param submission_tracker:  custom submission tracker
    :type submission_tracker:  object
    :param num_pages_to_load:
    :return:
    """
    if not all([hashtags_keys, pipeline_class_name, ]):
        return

    hashtags = dict()
    for key in hashtags_keys:
        try:
            hashtags[key] = bd_hashtags[key]
        except KeyError:
            log.error(
                (
                    'Tried to get non existent key "{}" from db_hashtags. '
                    'pipeline: {}'
                ).format(key, pipeline_class_name)
            )
            pass
    if not hashtags:
        log.error(
            (
                'No hashtags filtered from db_hashtags. '
                'hashtags_keys: {}; pipeline: {}'
            ).format(hashtags_keys, pipeline_class_name)
        )
        return

    # Creating new profiles from by hashtags
    cbih = CreatorByInstagramHashtags()
    cbih.create_new_profiles(
        hashtags=hashtags,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load,
        pipeline_class=pipeline_class_name
    )


@task(
    name="social_discovery.tasks.crawler_create_new_sea_profiles",
    ignore_result=True
)
def crawler_create_new_sea_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    # we need only 'singapore' tags now
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('singapore', ),
        pipeline_class_name=pipelines.SEAPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_fashion_profiles",
    ignore_result=True
)
def crawler_create_new_fashion_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('fashion_hashtags', 'fashion_brands', ),
        pipeline_class_name=pipelines.FashionPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_australia_profiles",
    ignore_result=True
)
def crawler_create_new_australia_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('australian', ),
        pipeline_class_name=pipelines.AustraliaPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_canada_profiles",
    ignore_result=True
)
def crawler_create_new_canada_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('canada', ),
        pipeline_class_name=pipelines.CanadaPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_travel_profiles",
    ignore_result=True
)
def crawler_create_new_travel_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('travel_hashtags', ),
        pipeline_class_name=pipelines.TravelPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_decor_profiles",
    ignore_result=True
)
def crawler_create_new_decor_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('decor_hashtags', ),
        pipeline_class_name=pipelines.DecorPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_menfashion_profiles",
    ignore_result=True
)
def crawler_create_new_menfashion_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('menfashion_hashtags', ),
        pipeline_class_name=pipelines.MenFashionPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_food_profiles",
    ignore_result=True
)
def crawler_create_new_food_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('food_hashtags', ),
        pipeline_class_name=pipelines.FoodPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_mommy_profiles",
    ignore_result=True
)
def crawler_create_new_mommy_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('mom_hashtags', ),
        pipeline_class_name=pipelines.MommyPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_german_profiles",
    ignore_result=True
)
def crawler_create_new_german_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('germany', ),
        pipeline_class_name=pipelines.GermanyPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_lifestyle_profiles",
    ignore_result=True
)
def crawler_create_new_lifestyle_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('lifestyle_hashtags', ),
        pipeline_class_name=pipelines.LifestylePipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


@task(
    name="social_discovery.tasks.crawler_create_new_fitness_profiles",
    ignore_result=True
)
def crawler_create_new_fitness_profiles(
    submission_tracker=None, num_pages_to_load=20
):
    """
    Celery task to call CreatorByInstagramHashtags.create_new_profiles()
    :param submission_tracker: custom submission tracker object
    :param num_pages_to_load: number of Instagram pages to perform for each
           hashtag
    :return:
    """
    _create_profiles_from_instagram_hashtags(
        hashtags_keys=('healthfitness_hashtags', ),
        pipeline_class_name=pipelines.HealthFitnessPipeline.__name__,
        submission_tracker=submission_tracker,
        num_pages_to_load=num_pages_to_load
    )


def find_youtube_instagram_profiles():
    """
    This task will find youtube-containing Instagram profiles of bloggers with more than 5000 followers.
    also this task will use its own queue to perform so it will perform asap.

    Note: check its pipeline for details.

    :return:
    """

    from social_discovery.models import InstagramProfile

    initial_profiles = InstagramProfile.objects.filter(
        tags__contains="undecided",
        friends_count__gte=5000
    ).values_list(
        "id",
        flat=True
    )

    log.info('Initial profiles found: %s' % initial_profiles.count())

    # log.info('First 50 ids: %s' % [ip.id for ip in initial_profiles[0:50]])

    # issuing tasks
    pipeline = pipelines.HaveYoutubePipeline()

    total = initial_profiles.count()
    ctr = 0

    for ip_id in list(initial_profiles):
        pipeline.run_pipeline(ip_id)
        ctr += 1
        log.info('Performed: %s/%s' % (ctr, total))


@baker.command
def perform_1000_insta_youtube_profiles(num_profiles=5000):
    """
    fetches social urls related to given instagramprofiles
    :return:
    """
    from social_discovery.models import InstagramProfile
    from platformdatafetcher.platformextractor import LightSocialUrlsExtractor

    initial_profiles = InstagramProfile.objects.filter(
        tags__contains="have_youtube",
        friends_count__gte=5000
    ).order_by('id')[:num_profiles]

    extractor = LightSocialUrlsExtractor()

    performed = []

    ctr = 0
    for i in initial_profiles:
        try:
            description = i.get_description_from_api()
            extra_urls = [i.get_url_from_api(), ]
            urls_detected, non_social_urls_detected = extractor.extract_urls(description, extra_urls)

            if urls_detected is not None and len(urls_detected) > 0:
                i.set_social_urls_detected(urls_detected)

            if non_social_urls_detected is not None and len(non_social_urls_detected) > 0:
                i.set_non_social_urls_detected(non_social_urls_detected)

            ctr += 1

            log.info('%s InstagramProfile %s got these urls: %s' % (ctr, i.id, urls_detected))

            performed.append(i.id)
        except:
            log.warn('%s InstagramProfile %s had problems' % (ctr, i.id))
    return performed


@baker.command
def perform_insta_mom_profiles(num_profiles=1000, overwrite=False):
    """
    fetches social urls related to given instagramprofiles
    :return:
    """
    from social_discovery.models import InstagramProfile
    from platformdatafetcher.platformextractor import LightSocialUrlsExtractor

    # excluded 'have_youtube' so that we don't do these again
    if overwrite is True:
        initial_profiles = InstagramProfile.objects.filter(
            tags__contains="new_mommy_hashtags",
            friends_count__gte=10000,
            # social_urls_detected__isnull=True
        ).order_by('id')[:num_profiles]
    else:
        initial_profiles = InstagramProfile.objects.filter(
            tags__contains="new_mommy_hashtags",
            friends_count__gte=10000,
            social_urls_detected__isnull=True
        ).exclude(tags__contains='have_youtube').order_by('id')[:num_profiles]

    extractor = LightSocialUrlsExtractor()

    performed = []

    ctr = 0
    for i in initial_profiles:
        try:
            description = i.get_description_from_api()
            extra_urls = [i.get_url_from_api(), ]
            urls_detected, non_social_urls_detected = extractor.extract_urls(description, extra_urls)

            if urls_detected is not None and len(urls_detected) > 0:
                i.set_social_urls_detected(urls_detected)

            if non_social_urls_detected is not None and len(non_social_urls_detected) > 0:
                i.set_non_social_urls_detected(non_social_urls_detected)

            ctr += 1

            log.info('%s InstagramProfile %s got these urls: %s' % (ctr, i.id, urls_detected))

            performed.append(i.id)
        except:
            log.warn('%s InstagramProfile %s had problems' % (ctr, i.id))
    return performed


def detect_social_urls_for_have_youtube(qty=1000):
    """
    Will perform all have_youtube for getting urls as pipeline (with celery queue)

    :return:
    """

    from social_discovery.models import InstagramProfile
    from social_discovery.pipeline_constants import get_queue_name_by_pipeline_step

    initial_profiles = InstagramProfile.objects.filter(
        tags__contains="have_youtube",
        # friends_count__gte=5000
    ).exclude(tags__contains='mom').filter(tags__contains='blogger').order_by(
        'id'
    ).values_list(
        "id",
        flat=True
    )

    if qty is not None:
        initial_profiles = initial_profiles[:qty]

    log.info('Initial profiles found: %s' % initial_profiles.count())

    # issuing tasks
    pipeline = pipelines.HaveYoutubeDiscoverUrlsPipeline()

    for ip_id in list(initial_profiles):
        crawler_task.apply_async(
            kwargs={
                'klass_name': pipeline.PIPELINE_ROUTE[0],
                'task_type': 'pipeline',
                'profile_id': ip_id,
                'route': pipeline.PIPELINE_ROUTE,
            },
            queue=get_queue_name_by_pipeline_step(pipeline.PIPELINE_ROUTE[0])  # PIPELINE_QUEUE_NAME
        )

def detect_social_urls_for_profiles(must_have_tags='have_youtube', exclude_tags=None, friends_threshold=1000, qty=1000):
    """
    Will perform all new_mommy_hashtags for getting urls as pipeline  (with celery queue)

    :return:
    """

    from social_discovery.models import InstagramProfile
    from social_discovery.pipeline_constants import get_queue_name_by_pipeline_step

    initial_profiles = InstagramProfile.objects.filter(
        tags__contains=must_have_tags,
        friends_count__gte=friends_threshold,
    ).order_by(
        'id'
    )

    if exclude_tags:
        initial_profiles = initial_profiles.exclude(tags__contains=exclude_tags)


    blogs = initial_profiles.filter(tags__contains='blogger')
    undecided = initial_profiles.filter(tags__contains='undecided')

    final_profiles = blogs #| undecided

    final_profiles = final_profiles.values_list(
        "id",
        flat=True
    )

    if qty is not None:
        final_profiles = final_profiles[:qty]

    log.info('Initial profiles found: %s' % final_profiles.count())

    # issuing tasks
    pipeline = pipelines.HaveYoutubeDiscoverUrlsPipeline()

    for ip_id in list(final_profiles):
        crawler_task.apply_async(
            kwargs={
                'klass_name': pipeline.PIPELINE_ROUTE[0],
                'task_type': 'pipeline',
                'profile_id': ip_id,
                'route': pipeline.PIPELINE_ROUTE,
            },
            queue=get_queue_name_by_pipeline_step(pipeline.PIPELINE_ROUTE[0])  # PIPELINE_QUEUE_NAME
        )


def task_discover_existing_platforms(must_have_tags='have_youtube', exclude_tags=None, friends_threshold=1000, qs=None):

    if qs is None:
        from social_discovery.models import InstagramProfile
        initial_profiles = InstagramProfile.objects.filter(tags__contains=must_have_tags,
                                                           friends_count__gte=friends_threshold,).order_by('id')
        if exclude_tags:
            initial_profiles = initial_profiles.exclude(tags__contains=exclude_tags)

        blogs = initial_profiles.filter(tags__contains='blogger')
        undecided = initial_profiles.filter(tags__contains='undecided')

        #final_profiles = blogs | undecided
        final_profiles = blogs

        qs = final_profiles.values_list(
            "id",
            flat=True
        )

    # issuing tasks
    pipeline = pipelines.HaveYoutubeDiscoverPlatformsPipeline()

    for ip_id in list(qs):
        crawler_task.apply_async(
            kwargs={
                'klass_name': pipeline.PIPELINE_ROUTE[0],
                'task_type': 'pipeline',
                'profile_id': ip_id,
                'route': pipeline.PIPELINE_ROUTE,
            },
            # TODO: overriden for comfort
            queue='profiles_pipeline_upgraders_youtube'  # PIPELINE_QUEUE_NAME
        )


@task(
    name="social_discovery.tasks.task_refetch_instagramprofile",
    ignore_result=True
)
def task_refetch_instagramprofile(profile_id=None):
    """
    This task refetches InstagramProfile data.
    If they get different description or different url - then passing it to the
    same pipeline as it was originally a part of.
    :return:
    """
    from social_discovery.models import InstagramProfile
    from social_discovery.instagram_crawl import scrape_profile_details

    if profile_id is None:
        log.error('profile_id is None, exiting')
        return

    try:
        profile = InstagramProfile.objects.get(id=profile_id)
    except InstagramProfile.DoesNotExist:
        log.error(
            'InstagramProfile with id %s does not exist, exiting' % profile_id
        )
        return

    details = scrape_profile_details(profile)
    log.info('Received details: %s' % details)

    # Comparing existing external url and description with old one
    re_performing = False
    if profile.get_description_from_api() != details.get('description'):
        log.info('Descriptions did not match:')
        log.info('%r VS %r' % (
            profile.get_description_from_api(),
            details.get('description', None)
        ))
        re_performing = True
    elif profile.get_external_url() != details.get('external_url'):
        log.info('External urls did not match:')
        log.info('%r VS %r' % (
            profile.get_description_from_api(),
            details.get('description', None)
        ))
        re_performing = True
    if not re_performing:
        # Doing nothing - placing a tag and forfeit it?
        log.info(
            "Description or external url did not change, "
            "setting 'refetched_no_changes' tag."
        )
        profile.append_mutual_exclusive_tag(
            'refetched_no_changes',
            ['refetched_no_changes', 'refetched_changed', ]
        )
        return

    # Update this profile's data and re-issuing this profile to its
    # pipeline again
    profile.update_from_web_data(details)
    profile.append_mutual_exclusive_tag(
        'refetched_changed',
        ['refetched_no_changes', 'refetched_changed', ]
    )

    # detecting pipeline we used for this profile
    tags = profile.tags.split()
    pipeline_class = None
    for t in tags:
        if t.startswith('PIPELINE_'):
            pipeline_class = t[9:]
            break

    if pipeline_class is not None:
        try:
            # getting a 'pipeline' by its name
            log.info('Loading pipeline %s for profile %s' % (
                pipeline_class, profile.id
            ))
            pipeline_cls = locate(
                'social_discovery.pipelines.%s' % pipeline_class
            )

            # creating an 'objekt' of the class
            pipeline = pipeline_cls()

            log.info('Running pipeline %s for profile %s' % (
                pipeline_class, profile.id
            ))
            # calling the required function with appropriate params
            pipeline.run_pipeline(profile.id)
        except KeyError:
            log.error('Pipeline %s not found' % pipeline_class)


@task(name="social_discovery.tasks.task_refetch_profiles_scheduled_in_10_days_later", ignore_result=True)
def task_refetch_profiles_scheduled_in_10_days_later():
    """
    This task refetches profiles that were scheduled to be refetched acording to date_to_fetch_later field.
    Their data is refetched.

    If they get different description or different url - then passing it to the same pipeline as it was
    originally a part of.
    :return:
    """

    # TODO: start this in settings on a daily basis

    from social_discovery.pipeline_constants import QUEUE_TO_REFETCH_PROFILES
    from social_discovery.models import InstagramProfile

    today_min = datetime.combine(date.today(), time.min)
    today_max = datetime.combine(date.today(), time.max)
    profile_ids_to_re_perform = InstagramProfile.objects.filter(
        date_to_fetch_later__range=(today_min, today_max)
    ).values_list('id', flat=True)

    log.info('Issuing Celery tasks to refetch profiles: %s' % len(profile_ids_to_re_perform))

    ctr = 0
    for profile_id in profile_ids_to_re_perform:

        crawler_task.apply_async(
            kwargs={
                'profile_id': profile_id,
            },
            # TODO: overriden for comfort
            queue=QUEUE_TO_REFETCH_PROFILES
        )
        ctr += 1
    log.info('Issued Celery tasks to refetch profiles: %s' % ctr)


@task(
    name="social_discovery.tasks.task_connect_instagramprofile_to_influencers",
    ignore_result=True
)
def task_connect_instagramprofile_to_influencers(
    must_have_tags=None, exclude_tags=None, friends_threshold=1000, limit=1000,
    qs=None
):

    """
    This task should run periodically by default.
    - It finds instagram profiles that are not already connected to
      influencers.
    - Then it filters by friends_count and 'blogger' tag
    - If less than a certain threshold are available, we also check with
      undecided
    """

    from social_discovery.models import InstagramProfile
    from social_discovery.pipeline_constants import CONNECT_PROFILES_QUEUE_NAME

    if not qs:
        initial_profiles = InstagramProfile.objects.filter(
            friends_count__gte=friends_threshold
        )

        if must_have_tags:
            initial_profiles = initial_profiles.filter(
                tags__contains=must_have_tags
            )

        if exclude_tags:
            initial_profiles = initial_profiles.exclude(
                tags__contains=exclude_tags
            )

        # we don't want to process profiles that already have a connected
        # influencer
        initial_profiles = initial_profiles.filter(
            discovered_influencer__isnull=True
        )

        blogs = initial_profiles.filter(tags__contains='blogger')

        # use undecided only if the blog profiles are not enough
        if blogs.count() < limit:
            undecided = initial_profiles.filter(
                tags__contains='undecided'
            ).filter(tags__contains='SHORT_BIO_50')
            final_profiles = blogs | undecided
        else:
            final_profiles = blogs

        qs = final_profiles.values_list(
            'id',
            flat=True
        ).order_by('-friends_count')[:limit]
    else:
        qs = qs.values_list('id', flat=True).order_by('id')

    # issuing tasks
    pipeline = pipelines.ConnectInstagramProfilesToInfluencersPipeline()

    for ip_id in list(qs):
        crawler_task.apply_async(
            kwargs={
                'klass_name': pipeline.PIPELINE_ROUTE[0],
                'task_type': 'pipeline',
                'profile_id': ip_id,
                'route': pipeline.PIPELINE_ROUTE,
            },
            # TODO: overriden for comfort
            queue=CONNECT_PROFILES_QUEUE_NAME
        )


@task(
    name="social_discovery.tasks.reprocess_instagram_profiles",
    ignore_result=True
)
def reprocess_instagram_profiles(friends_lower_bound=50000, period_weeks=2):
    """
    This task should run periodically by default.
    - It finds instagram profiles that are marked as "undecided" and have
      more than 'friends_lower_bound' followers.
    - Refetch web data for these profiles and try to classify them again
    """
    from social_discovery.models import InstagramProfile

    pipeline = pipelines.BasicClassifierPipeline()

    for profile in InstagramProfile.objects.filter(
        date_created__lt=datetime.now() - timedelta(weeks=period_weeks),
        friends_count__gte=friends_lower_bound,
        tags__regex='(^| )undecided( |$)',
        reprocess_tries_count__lt=MAX_INSTAGRAM_REFETCH_RETRY_COUNT,
    ).order_by('-reprocess_tries_count'):
        log.info('Reprocessing profile id: {}; name: {}'.format(
            profile.id, profile.username
        ))
        crawler_task.apply_async(
            kwargs={
                'klass_name': pipeline.PIPELINE_ROUTE[0],
                'task_type': 'pipeline',
                'profile_id': profile.id,
                'route': pipeline.PIPELINE_ROUTE,
            },
            queue=REPROCESS_PROFILES_QUEUE_NAME
        )
        profile.reprocess_tries_count += 1
        profile.save()


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
