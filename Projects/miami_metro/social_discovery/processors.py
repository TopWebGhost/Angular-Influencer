import logging

from platformdatafetcher.platformextractor import LightSocialUrlsExtractor
from social_discovery.blog_discovery import (
    locations_keywords as bd_locations_keywords,
    locations_phrases as bd_locations_phrases,
    domain_extensions as bd_domain_extensions,
    hashtags as bd_hashtags,
    influencer_keywords as inf_kw,
)
from social_discovery.crawler_task import crawler_task
from social_discovery.instagram_crawl import (
    get_instagram_profiles_by_checking_language,
    get_instagram_profiles_by_searching_profile_description,
    get_instagram_profiles_by_searching_api_biography
)
from social_discovery.models import InstagramProfile, SocialProfileOp
from social_discovery.pipeline_constants import (
    MINIMUM_FRIENDS_COUNT, get_queue_name_by_pipeline_step,
)

"""
This file contains all Processor and derived modules for InstagramProfile pipeline.
"""

log = logging.getLogger('social_discovery.processors')


def generate_influencer_hashtags(location_keywords=None):
    """
    A function to create more hashtags for a given processor:
    a) find all hashtags from blog_discovery.hashtags['influencer_keywords']
    b) use the locations for the processor (e.g., for SEA, use the SEA_location keywords)
    c) append and pre-pend the location keywords to the influencer_keywords to create a new set of hahstags
       (e.g., suppose influencer_keywords = ['influencer', 'blogger', 'Wechat',] and
       australia_location = ['australia'], then new set of hashtags are
       ['austrliainfluencer', 'austrliablogger', australiawechat', 'influeneraustralia', 'bloggeraustralia',
       'wechataustralia'])
       This will help us find more hashtags that are relevant from a given region.
    :return:
    """

    result = []

    # influencers keywords
    if isinstance(location_keywords, list) and len(location_keywords) > 0:
        for location in location_keywords:
            for influencer in inf_kw:
                result.append('%s%s' % (location, influencer))
                result.append('%s%s' % (influencer, location))
    return result


class Processor(object):
    """
    For Instagram:
    1. Searching for InstagramProfiles by location (domains) (instagram_crawl.py line 1441)
    2. Searching for InstagramProfiles by hashtags (instagram_crawl.py line 1452)
    3. Searching for InstagramProfiles by language (some regexps) (Detection of language?)(instagram_crawl.py line 1458)

    Actually, can have a vast amount of classify_by_**** functions that allow classification by corresponding values.
    """

    PROCESSOR_TAG = None

    LOCATIONS_KEYWORDS = None
    LOCATIONS_PHRASES = None

    DOMAINS = None
    HASHTAGS = None

    REGION = None

    def process_by_locations(self, queryset, to_tag=True):
        """
        Returns appropriate InstagramProfiles by criteria:
            * locations
            * url domains

        :param queryset -- incoming queryset of InstagramProfiles
        :param to_tag -- if set True, then category tag will be set to these profiles
        :returns outcoming queryset with appropriate ids filtered or excluded
        """

        if queryset is None:
            return None
        else:
            profiles, key_distribution = get_instagram_profiles_by_searching_api_biography(
                exact_keywords=self.LOCATIONS_KEYWORDS,
                phrases=self.LOCATIONS_PHRASES,
                # phrases=self.LOCATIONS,
                minimum_friends=MINIMUM_FRIENDS_COUNT,
                profiles=queryset,
                special_characters=[],
                domain_extensions=self.DOMAINS
            )

            if to_tag:
                tag = '%s_%s' % (self.PROCESSOR_TAG, 'LOCATION')

                # Performing all profiles from queryset, appending tags and creating SocialProfileOps
                for q in queryset:
                    if q in profiles:
                        # setting a tag
                        if tag not in q.tags:
                            q.append_tag(tag)

                    # creating a SocialProfileOp object for this event
                    SocialProfileOp.objects.create(
                        profile_id=q.id,
                        description=tag if q in profiles else 'UNSUITABLE_'+tag,
                        module_classname=type(self).__name__,
                        data={}
                    )

            return profiles

    def process_by_hashtags(self, queryset, to_tag=True):
        """
        Returns appropriate InstagramProfiles by criteria:
            * hashtags for SEA region

        :param queryset -- incoming queryset of InstagramProfiles
        :returns outcoming queryset with appropriate ids filtered or excluded
        """

        if queryset is None:
            return None
        else:
            profiles, key_distribution = get_instagram_profiles_by_searching_profile_description(
                profiles=queryset,
                minimum_friends=MINIMUM_FRIENDS_COUNT,
                hashtags=self.HASHTAGS,
                mentions=[]
            )

            if to_tag:
                tag = '%s_%s' % (self.PROCESSOR_TAG, 'HASHTAG')

                # Performing all profiles from queryset, appending tags and creating SocialProfileOps
                for q in queryset:
                    if q in profiles:
                        # setting a tag
                        if tag not in q.tags:
                            q.append_tag(tag)

                    # creating a SocialProfileOp object for this event
                    SocialProfileOp.objects.create(
                        profile_id=q.id,
                        description=tag if q in profiles else 'UNSUITABLE_'+tag,
                        module_classname=type(self).__name__,
                        data={}
                    )

        return profiles

    def process_by_language(self, queryset, to_tag=True):
        """
        Returns appropriate InstagramProfiles by criteria:
            * languages for SEA region

        :param queryset -- incoming queryset of InstagramProfiles
        :returns outcoming queryset with appropriate ids filtered or excluded
        """

        if queryset is None:
            return None
        else:
            profiles, key_distribution = get_instagram_profiles_by_checking_language(
                profiles=queryset,
                region=self.REGION,
                check_biography=True,
                check_captions=True,
                caption_match_threshold=3
            )
            if to_tag:
                tag = '%s_%s' % (self.PROCESSOR_TAG, 'LANGUAGE')

                # Performing all profiles from queryset, appending tags and creating SocialProfileOps
                for q in queryset:
                    if q in profiles:
                        # setting a tag
                        if tag not in q.tags:
                            q.append_tag(tag)

                    # creating a SocialProfileOp object for this event
                    SocialProfileOp.objects.create(
                        profile_id=q.id,
                        description=tag if q in profiles else 'UNSUITABLE_'+tag,
                        module_classname=type(self).__name__,
                        data={}
                    )

        return profiles

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next Processor, Classifier or Upgrader in chain.
        """
        return False

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        This function is called when performing Processor as a part of pipeline
        """

        log.info('Started %s.pipeline(profile_id=%s, route=%s)' % (type(self).__name__, profile_id, route))

        profile_qs = InstagramProfile.objects.filter(id=profile_id)
        if profile_qs.count() > 0:

            self.process_by_locations(profile_qs, to_tag=True)
            self.process_by_hashtags(profile_qs, to_tag=True)
            self.process_by_language(profile_qs, to_tag=True)

            # proceeding with pipeline route if result is suitable
            if type(route) is list and len(route) > 1 and self.proceed(result=profile_id):
                log.info('Proceeding to the next step: %s' % route[1])
                crawler_task.apply_async(
                    kwargs={
                        'klass_name': route[1],
                        'task_type': 'pipeline',
                        'profile_id': profile_id,
                        'route': route[1:],
                    },
                    queue=get_queue_name_by_pipeline_step(route[1])
                )
            else:
                log.info('Route finished or terminating route because of result.')
        else:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)


class ProcessorSEA(Processor):
    """
    This is a processor for South East Asian InstagramProfiles
    """

    PROCESSOR_TAG = 'SEA'  # South Eastern Asia

    LOCATIONS_KEYWORDS = \
        bd_locations_keywords['singapore'] + \
        bd_locations_keywords['korea'] + \
        bd_locations_keywords['india'] + \
        bd_locations_keywords['japan'] + \
        bd_locations_keywords['china'] + \
        bd_locations_keywords['indonesia'] + \
        bd_locations_keywords['cambodia'] + \
        bd_locations_keywords['philippines'] + \
        bd_locations_keywords['thailand'] + \
        bd_locations_keywords['taiwan'] + \
        bd_locations_keywords['hong kong'] + \
        bd_locations_keywords['malaysia'] + \
        bd_locations_keywords['vietnam']

    LOCATIONS_PHRASES = \
        bd_locations_phrases['singapore'] + \
        bd_locations_phrases['korea'] + \
        bd_locations_phrases['india'] + \
        bd_locations_phrases['japan'] + \
        bd_locations_phrases['china'] + \
        bd_locations_phrases['indonesia'] + \
        bd_locations_phrases['cambodia'] + \
        bd_locations_phrases['philippines'] + \
        bd_locations_phrases['thailand'] + \
        bd_locations_phrases['taiwan'] + \
        bd_locations_phrases['hong kong'] + \
        bd_locations_phrases['malaysia'] + \
        bd_locations_phrases['vietnam']

    DOMAINS = \
        bd_domain_extensions['singapore'] + \
        bd_domain_extensions['hong kong'] + \
        bd_domain_extensions['philippines'] + \
        bd_domain_extensions['india'] + \
        bd_domain_extensions['japan'] + \
        bd_domain_extensions['blogger_domains']

    # LOCATIONS = LOCATIONS_KEYWORDS + LOCATIONS_PHRASES

    HASHTAGS = [h.lower() for h in bd_hashtags['singapore'] + bd_hashtags['only_sea']]

    REGION = PROCESSOR_TAG

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', 'LOCATION', 'LANGUAGE'])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorAustralia(Processor):
    """
    This is a processor for InstagramProfiles from Australia and New Zealand
    """

    PROCESSOR_TAG = 'AUSTRALIA'

    LOCATIONS_KEYWORDS = \
        bd_locations_keywords['australia'] + \
        bd_locations_phrases['new zealand']

    LOCATIONS_PHRASES = \
        bd_locations_phrases['australia'] + \
        bd_locations_phrases['new zealand']

    DOMAINS = \
        bd_domain_extensions['australia']

    # LOCATIONS = LOCATIONS_KEYWORDS + LOCATIONS_PHRASES

    HASHTAGS = [h.lower() for h in bd_hashtags['australian'] + generate_influencer_hashtags(LOCATIONS_KEYWORDS)]

    REGION = PROCESSOR_TAG

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', 'LOCATION', 'LANGUAGE'])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorCanada(Processor):
    """
    This is a processor for InstagramProfiles from Canada
    """

    PROCESSOR_TAG = 'CANADA'

    LOCATIONS_KEYWORDS = \
        bd_locations_keywords['canada']

    LOCATIONS_PHRASES = \
        bd_locations_phrases['canada']

    DOMAINS = \
        bd_domain_extensions['canada']

    # LOCATIONS = LOCATIONS_KEYWORDS + LOCATIONS_PHRASES

    HASHTAGS = [h.lower() for h in bd_hashtags['canada'] + generate_influencer_hashtags(LOCATIONS_KEYWORDS)]

    REGION = PROCESSOR_TAG

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', 'LOCATION', 'LANGUAGE'])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorTravel(Processor):
    """
    This is a processor for InstagramProfiles from Travel hashtags only
    """
    PROCESSOR_TAG = 'TRAVEL'

    HASHTAGS = [h.lower() for h in bd_hashtags['travel_hashtags']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', ])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorFashion(Processor):
    """
    This is a processor for InstagramProfiles from Fashion hashtags only
    """
    PROCESSOR_TAG = 'FASHION'

    HASHTAGS = [h.lower() for h in bd_hashtags['fashion_hashtags']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', ])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorDecor(Processor):
    """
    This is a processor for InstagramProfiles from Decor hashtags only
    """
    PROCESSOR_TAG = 'DECOR'

    HASHTAGS = [h.lower() for h in bd_hashtags['decor_hashtags']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', ])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorMenFashion(Processor):
    """
    This is a processor for InstagramProfiles from menfashion hashtags only
    """
    # Hashtag is set this way to avoid conflicts when filtering by 'FASHION_HASHTAG'
    PROCESSOR_TAG = 'FASHIONMEN'

    HASHTAGS = [h.lower() for h in bd_hashtags['menfashion_hashtags']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', ])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorFood(Processor):
    """
    This is a processor for InstagramProfiles from Food hashtags only
    """
    PROCESSOR_TAG = 'FOOD'

    HASHTAGS = [h.lower() for h in bd_hashtags['food_hashtags']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', ])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorMommy(Processor):
    """
    This is a processor for InstagramProfiles from Mommy hashtags only
    """
    PROCESSOR_TAG = 'MOMMY'

    HASHTAGS = [h.lower() for h in bd_hashtags['mom_hashtags']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking result (InstagramProfile) if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return any('%s_%s' % (self.PROCESSOR_TAG, tag) in tags for tag in ['HASHTAG', ])
        except InstagramProfile.DoesNotExist:
            pass
        return False


class OnlyBloggersProcessor(Processor):
    """
    This processor is used as a filter to proceed only if 2 conditions are satisfied:
        * have either 'blogger' or both 'SHORT_LEN_50' and 'undecided' tags
        AND
        * there is one or more of OR_TAGS tags

    """
    OR_TAGS = []

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next Processor, Classifier or Upgrader in chain.
        gets Profile as result
        """

        # checking for required tags
        tags = result.tags.split()

        # TODO: Consider also checking for "FOUND_BLOGGER_KEYWORDS" keyword?
        # Sometimes appears in some InstagramProfiles.

        if ('blogger' in tags or ('undecided' in tags and 'SHORT_BIO_50' in tags)) \
                and (
                any([t in tags for t in self.OR_TAGS]) if self.OR_TAGS else True):
            return True
        return False

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        This function is called when performing Processor as a part of pipeline
        """

        log.info('Started %s.pipeline(profile_id=%s, route=%s)' % (type(self).__name__, profile_id, route))

        try:
            profile = InstagramProfile.objects.get(id=profile_id)

            result = self.proceed(result=profile)

            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile.id,
                description='VALID' if result else 'INVALID',  # VALID - satisfies conditions, INVALID - does not.
                module_classname=type(self).__name__,
                data={}
            )

            # proceeding with pipeline route if result is suitable
            if type(route) is list and len(route) > 1 and result:
                log.info('Proceeding to the next step: %s' % route[1])
                crawler_task.apply_async(
                    kwargs={
                        'klass_name': route[1],
                        'task_type': 'pipeline',
                        'profile_id': profile_id,
                        'route': route[1:],
                    },
                    queue=get_queue_name_by_pipeline_step(route[1])
                )
            else:
                log.info('Route finished or terminating route because of result.')
        except InstagramProfile.DoesNotExist:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)


class OnlyBloggersProcessorSEA(OnlyBloggersProcessor):
    """
    Seems these are not required, because ProcessorSEA will not pass it down by pipeline without any of these OR_TAGS
    """
    OR_TAGS = ['SEA_LOCATION', 'SEA_LANGUAGE', 'SEA_HASHTAG']


class OnlyBloggersProcessorAustralia(OnlyBloggersProcessor):
    """
    Seems these are not required, because ProcessorAustralis will not pass it down by pipeline without
    any of these OR_TAGS
    """
    OR_TAGS = ['AUSTRALIA_LOCATION', 'AUSTRALIA_LANGUAGE', 'AUSTRALIA_HASHTAG']


class HaveYoutubeUrlProcessor(Processor):
    """
    This processor is used as a filter to proceed only if this inftagramProfile.description has a youtube url

    """
    OR_TAGS = []

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next Processor, Classifier or Upgrader in chain.
        gets Profile as result
        """

        # checking for required urls in description
        tags = result.tags.split()

        if 'have_youtube' in tags:
            return True
        return False

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        This function is called when performing Processor as a part of pipeline
        """

        log.info('Started %s.pipeline(profile_id=%s, route=%s)' % (type(self).__name__, profile_id, route))

        try:
            profile = InstagramProfile.objects.get(id=profile_id)

            result = self.proceed(result=profile)

            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile.id,
                description='VALID' if result else 'INVALID',  # VALID - satisfies conditions, INVALID - does not.
                module_classname=type(self).__name__,
                data={}
            )

            # proceeding with pipeline route if result is suitable
            if type(route) is list and len(route) > 1 and result:
                log.info('Proceeding to the next step: %s' % route[1])
                crawler_task.apply_async(
                    kwargs={
                        'klass_name': route[1],
                        'task_type': 'pipeline',
                        'profile_id': profile_id,
                        'route': route[1:],
                    },
                    queue=get_queue_name_by_pipeline_step(route[1])
                )
            else:
                log.info('Route finished or terminating route because of result.')
        except InstagramProfile.DoesNotExist:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)


class HaveYoutubeOnlyBloggersProcessor(OnlyBloggersProcessor):
    pass


class DetectSocialUrlsProcessor(Processor):
    """
    This processor gets urls from description of the given InstagramProfile and
    finds all its corresponding social and non-social urls and stores the
    result in the InstagramProfile.

    """
    OR_TAGS = []

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next
        Processor, Classifier or Upgrader in chain.
        Gets Profile as result
        """

        extractor = LightSocialUrlsExtractor()

        description = result.get_description_from_api_history()
        extra_urls = list(result.get_urls_from_api_history())
        urls_detected, non_social_urls_detected = extractor.extract_urls(
            description=description,
            extra_urls=extra_urls,
            profile_username=result.username,
        )

        result.set_social_urls_detected(urls_detected)
        result.set_non_social_urls_detected(non_social_urls_detected)
        result.append_mutual_exclusive_tag(
            'social_urls_extracted', ['social_urls_extracted', ]
        )
        return True

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        This function is called when performing Processor as a part of pipeline
        """

        log.info(
            'Started %s.pipeline(profile_id=%s, route=%s)',
            type(self).__name__, profile_id, route
        )

        try:
            profile = InstagramProfile.objects.get(id=profile_id)
        except InstagramProfile.DoesNotExist:
            log.error(
                'InstagramProfile with id: %s does not exist, exiting.',
                profile_id
            )
            return

        result = self.proceed(result=profile)

        # creating a SocialProfileOp object for this event
        SocialProfileOp.objects.create(
            profile_id=profile.id,
            description='VALID' if result else 'INVALID',
            module_classname=type(self).__name__,
            data={}
        )

        # proceeding with pipeline route if result is suitable
        if type(route) is list and len(route) > 1 and result:
            log.info('Proceeding to the next step: %s' % route[1])
            crawler_task.apply_async(
                kwargs={
                    'klass_name': route[1],
                    'task_type': 'pipeline',
                    'profile_id': profile_id,
                    'route': route[1:],
                },
                queue=get_queue_name_by_pipeline_step(route[1])
            )
        else:
            log.info('Route finished or terminating route because of result.')


class HaveYoutubeDetectSocialUrlsProcessor(DetectSocialUrlsProcessor):
    pass


class DetectExistingPlatformsProcessor(Processor):
    """
    This processor detects existing platforms for the given InstagramProfile
    and saves its ids to InstagramProfile.
    """
    OR_TAGS = []

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next
        Processor, Classifier or Upgrader in chain.
        gets Profile as result
        """
        try:
            result.find_existing_platform_ids()
            return True
        except:
            return False

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        This function is called when performing Processor as a part of pipeline
        """

        log.info(
            'Started %s.pipeline(profile_id=%s, route=%s)',
            type(self).__name__, profile_id, route
        )

        try:
            profile = InstagramProfile.objects.get(id=profile_id)
        except InstagramProfile.DoesNotExist:
            log.error(
                'InstagramProfile with id: %s does not exist, exiting.',
                profile_id
            )
            return

        result = self.proceed(result=profile)

        # creating a SocialProfileOp object for this event
        SocialProfileOp.objects.create(
            profile_id=profile.id,
            description='VALID' if result else 'INVALID',
            module_classname=type(self).__name__,
            data={}
        )

        # proceeding with pipeline route if result is suitable
        if type(route) is list and len(route) > 1 and result:
            log.info('Proceeding to the next step: %s' % route[1])
            crawler_task.apply_async(
                kwargs={
                    'klass_name': route[1],
                    'task_type': 'pipeline',
                    'profile_id': profile_id,
                    'route': route[1:],
                },
                queue=get_queue_name_by_pipeline_step(route[1])
            )
        else:
            log.info('Route finished or terminating route because of result.')


class HaveYoutubeDetectExistingPlatformsProcessor(DetectExistingPlatformsProcessor):
    pass


class ProcessorGermany(Processor):
    """
    This is a processor for InstagramProfiles from hashtags only
    """
    PROCESSOR_TAG = 'GERMANY'

    HASHTAGS = [h.lower() for h in bd_hashtags['germany']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking InstagramProfile if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return '{}_HASHTAG'.format(self.PROCESSOR_TAG) in tags
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorLifestyle(Processor):
    """
    This is a processor for InstagramProfiles from hashtags only
    """
    PROCESSOR_TAG = 'LIFESTYLE'

    HASHTAGS = [h.lower() for h in bd_hashtags['lifestyle_hashtags']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking InstagramProfile if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return '{}_HASHTAG'.format(self.PROCESSOR_TAG) in tags
        except InstagramProfile.DoesNotExist:
            pass
        return False


class ProcessorHealthFitness(Processor):
    """
    This is a processor for InstagramProfiles from hashtags only
    """
    PROCESSOR_TAG = 'HEALTHFITNESS'

    HASHTAGS = [h.lower() for h in bd_hashtags['healthfitness_hashtags']]

    def process_by_locations(self, queryset, to_tag=True):
        return

    def process_by_language(self, queryset, to_tag=True):
        return

    def proceed(self, result):
        """
        Checking InstagramProfile if it has corresponding tags in .tags field
        """
        try:
            profile = InstagramProfile.objects.get(id=result)
            tags = profile.tags.split()
            return '{}_HASHTAG'.format(self.PROCESSOR_TAG) in tags
        except InstagramProfile.DoesNotExist:
            pass
        return False
