import logging

from django.db.models.query import QuerySet

from social_discovery import classifiers
from social_discovery import processors
from social_discovery.blog_discovery import queryset_iterator
from social_discovery.crawler_task import crawler_task
from social_discovery.models import InstagramProfile
from social_discovery.pipeline_constants import (
    get_queue_name_by_pipeline_step,
)
from social_discovery.upgraders import LightUpgrader, LightExtraDataUpgrader

"""
This file contains all Pipelines and derived modules for InstagramProfile
pipeline.
"""

log = logging.getLogger('social_discovery.pipelines')


class Pipeline(object):
    """
    Pipeline description and goals here.

    Pipeline is a set of operations, that should be performed over some set of
    InstagramProfile objects (or a single profile). For example:
      Initial queryset of InstagramProfiles --> KeywordClassifier
        --> SEAClassifier(process_location, process_hashtags, process_language)
         --> SportsClassifier(process_by_sport_keywords)
          --> Upgrader(yet to be created)

    Each step could be done as a separate task, but to ensure this chainlink
    we could pass also a list of steps to pass, for example:
      perform_sequence = ['KeywordClassifier',
      'ProcessorSEA.process_by_location', 'ProcessorSEA.process_by_hashtags',
      'ProcessorSEA.process_by_language',
      'ProcessorSports.process_by_sport_keywords', 'CommonUpgrader']

    After a successful pass of each step (for example, a profile successfully
    has passed 'KeywordClassifier' and got 'blogger' result (with corresponding
    tag added), it issues a crawler_task() for SEAClassifier, task with above
    sequence but without first element.
    If it got 'brand' result, then it should stop (with corresponding tag
    added) and not proceed on the pipeline.
    """

    PIPELINE_ROUTE = None
    # If no input data is specified collect all profiles with this minimum
    # number of followers:
    DEFAULT_MINIMUM_FRIENDS_COUNT = 20000000

    # TODO: make crawler_task use classes instead if class names
    def run_pipeline(self, data=None):
        """
        This function runs pipeline for execution.
        """
        if not self.PIPELINE_ROUTE or not isinstance(
            self.PIPELINE_ROUTE, (list, tuple,)
        ):
            log.error((
                'Pipeline route is empty or incorrectly given: {}, exiting.'
            ).format(self.PIPELINE_ROUTE))
            return

        if type(data) in [int, str]:
            queryset = InstagramProfile.objects.filter(id=data)
        elif isinstance(data, list):
            queryset = InstagramProfile.objects.filter(id__in=data)
        elif isinstance(data, QuerySet):
            queryset = data
        else:
            # TODO: Maybe fetch all profiles for the last day?
            queryset = InstagramProfile.objects.filter(
                friends_count__gte=self.DEFAULT_MINIMUM_FRIENDS_COUNT
            )

        profiles = queryset_iterator(queryset)

        log.info('Performing %s profiles...' % queryset.count())

        for profile in profiles:
            crawler_task.apply_async(
                kwargs={
                    'klass_name': self.PIPELINE_ROUTE[0],
                    'task_type': 'pipeline',
                    'profile_id': profile.id,
                    'route': self.PIPELINE_ROUTE,
                },
                queue=get_queue_name_by_pipeline_step(
                    self.PIPELINE_ROUTE[0]
                )
            )


class SEAPipeline(Pipeline):
    """
    Pipeline to perform profiles for South East Asia
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorSEA.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class AustraliaPipeline(Pipeline):
    """
    Pipeline to perform profiles from Australia and New Zealand
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorAustralia.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class CanadaPipeline(Pipeline):
    """
    Pipeline to perform profiles from Canada
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorCanada.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class GermanyPipeline(Pipeline):
    """
    Pipeline to perform profiles for Mommy hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorGermany.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class TravelPipeline(Pipeline):
    """
    Pipeline to perform profiles for Travel hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorTravel.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class FashionPipeline(Pipeline):
    """
    Pipeline to perform profiles for Fashion hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorFashion.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class DecorPipeline(Pipeline):
    """
    Pipeline to perform profiles for Decor hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorDecor.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class MenFashionPipeline(Pipeline):
    """
    Pipeline to perform profiles for MenFashion hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorMenFashion.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class FoodPipeline(Pipeline):
    """
    Pipeline to perform profiles for Food hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorFood.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class MommyPipeline(Pipeline):
    """
    Pipeline to perform profiles for Mommy hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorMommy.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class HaveYoutubePipeline(Pipeline):
    """
    Pipeline for bloggers having youtube urls in their description

    CURRENTLY: we just classify them with pipelines

    """
    PIPELINE_ROUTE = [
        # HaveYoutubeKeywordClassifier.__name__,
        # HaveYoutubeDescriptionLengthClassifier.__name__,
        # HaveYoutubeOnlyBloggersProcessor.__name__,
        classifiers.HaveYoutubeUrlClassifier.__name__,
        processors.HaveYoutubeUrlProcessor.__name__,
        # HaveYoutubeUpgrader.__name__,
        # HaveYoutubeExtraDataUpgrader.__name__,
    ]


class HaveYoutubeDiscoverUrlsPipeline(Pipeline):
    """
    Pipeline to detect social/non-social urls

    """
    PIPELINE_ROUTE = [
        processors.HaveYoutubeDetectSocialUrlsProcessor.__name__,
    ]


class HaveYoutubeDiscoverPlatformsPipeline(Pipeline):
    """
    Pipeline to discover existing platforms
    """
    PIPELINE_ROUTE = [
        processors.HaveYoutubeDetectExistingPlatformsProcessor.__name__,
    ]


class ConnectInstagramProfilesToInfluencersPipeline(Pipeline):
    """
    This pipeline analyzes the provided instagram profiles and processes them
    through the steps outlined here.
    """
    PIPELINE_ROUTE = [
        processors.DetectSocialUrlsProcessor.__name__,
        processors.DetectExistingPlatformsProcessor.__name__,
        # make sure to set to_save=True when calling this
        LightUpgrader.__name__,
        LightExtraDataUpgrader.__name__,
    ]


class BasicClassifierPipeline(Pipeline):
    """
    Pipeline to discover new influences by brand mentions
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class LifestylePipeline(Pipeline):
    """
    Pipeline to perform profiles for Lifestyle hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorLifestyle.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]


class HealthFitnessPipeline(Pipeline):
    """
    Pipeline to perform profiles for Health Fitness hashtags
    """
    PIPELINE_ROUTE = [
        classifiers.KeywordClassifier.__name__,
        classifiers.DescriptionLengthClassifier.__name__,
        processors.ProcessorHealthFitness.__name__,
        processors.OnlyBloggersProcessor.__name__,
    ]
