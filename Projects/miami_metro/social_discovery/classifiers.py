import logging
from social_discovery.instagram_crawl import simplify

from social_discovery.models import InstagramProfile, SocialProfileOp
from social_discovery.blog_discovery import queryset_iterator

from social_discovery.blog_discovery import brand_keywords as brand_kw, \
    influencer_keywords as inf_kw, \
    influencer_phrases as inf_phrases

from social_discovery.pipeline_constants import get_queue_name_by_pipeline_step
from social_discovery.crawler_task import crawler_task

"""
This file contains all Classifier and derived modules for InstagramProfile pipeline.
"""

log = logging.getLogger('social_discovery.classifiers')


def contains(small, big):
    """
    Checks if first list is contained in second.
    http://stackoverflow.com/questions/3847386/testing-if-a-list-contains-another-list-with-python
    :param small: what to search
    :param big: where to search
    :return:
    """
    for i in xrange(len(big)-len(small)+1):
        for j in xrange(len(small)):
            if big[i+j] != small[j]:
                break
        else:
            return i, i+len(small)
    return False


class Classifier(object):
    """
    Classifier module: we can have multiple classifier classes. The first type will be a brand/blogger
    classification. It can use variety of methods. For example, currently,
    we use a keyword and phrase based classifier.

    Technically, classifier should return one value of a group list for example, ['blogger', 'brand', 'undecided']
    according to some filtering and comparing mechanism. Can have one method with source data as input and resulting
    value as an output. Also can have helper methods for batch performance to improve speed.

    using
    get_instagram_profiles_by_searching_api_biography()

    """

    # list of all available categories for categorization
    AVAILABLE_CATEGORIES = []

    def classify_unit(self, source=None, **kwargs):
        """
        This method is the core of classification algorithm. It receives source data for classification (object, model,
        string, etc.) and returns a value of classification category for this object.
        For example, we use InstagramProfile as source data, and result could be either 'brand' or 'blogger'
        or 'undecided'.
        """
        # return 'brand'
        raise NotImplemented

    def classify_profile(self, instagram_profile=None):
        """
        Classifies given InstagramProfile and sets corresponding mutual exclusive tag
        :param instagram_profile: InstagramProfile object to classify
        :return:
        """
        instagram_profile.append_mutual_exclusive_tag(self.classify_unit(instagram_profile),
                                                      self.AVAILABLE_CATEGORIES)

    def classify_queryset(self, source_queryset=None, **kwargs):
        """
        Helper method. Same as above but performs the whole queryset.
        ! Could return a dict of pairs ' id: classification_value '
        """

        # return {'id1': 'blogger', 'id2': 'brand',}
        raise NotImplemented

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next Processor, Classifier or Upgrader in chain.
        """
        return False

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        Performing single profile and deciding if it will go further by pipeline's route.
        """

        log.info('Started %s.pipeline(profile_id=%s, route=%s)' % (type(self).__name__, profile_id, route))
        # Fetching data from kwargs
        try:
            profile = InstagramProfile.objects.get(id=profile_id)
            category = self.classify_unit(profile)

            profile.append_mutual_exclusive_tag(category, self.AVAILABLE_CATEGORIES)

            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile.id,
                description=category,
                module_classname=type(self).__name__,
                data={}
            )

            log.info('category=%s' % category)

            # proceeding with pipeline route if result is suitable
            if type(route) is list and len(route) > 1 and self.proceed(result=category):
                log.info('Proceeding to the next step: %s' % route[1])
                crawler_task.apply_async(
                    kwargs={
                        'klass_name': route[1],
                        'task_type': 'pipeline',
                        'profile_id': profile.id,
                        'route': route[1:],
                    },
                    queue=get_queue_name_by_pipeline_step(route[1])
                )
            else:
                log.info('Route finished or terminating route because of result.')

        except InstagramProfile.DoesNotExist:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)


class KeywordClassifier(Classifier):
    """
    Classifier by keywords in description of InstagramProfile.
    Classifies InstagramProfiles as blogger, brand or undecided.

    Example of
    # brand SEA_hashtags SEA_location SEA_language
    # blogger SEA_hashtags US_location SEA_language

    """

    # keywords for brands and bloggers
    BRAND_KEYWORDS = []
    BRAND_PHRASES = brand_kw
    BLOGGER_KEYWORDS = inf_kw
    BLOGGER_PHRASES = inf_phrases

    # Brand phrases list of sets
    BRAND_PHRASES_LOS = [ph.lower().split() for ph in BRAND_PHRASES]
    # Blogger phrases list of sets
    BLOGGER_PHRASES_LOS = [ph.lower().split() for ph in BLOGGER_PHRASES]

    # list of all available categories for categorization
    AVAILABLE_CATEGORIES = [
        'brand',
        'blogger',
        'undecided',
    ]

    def classify_unit(self, source=None, **kwargs):
        """
        Classifying source by if it contains certain keywords.
        1. Check if profile_description contains any BRAND keyword. If so, return result that it is a 'brand'.
        2. Check if profile_description contains one or more BLOGGER keywords. If so, return 'blogger'.
        3. If it contains neither BRAND nor BLOGGER keywords, return 'undecided'

        Also takes in account situations like , for example, if blogger keyword is 'actor', it
        will not match a brand's word 'contractor'.
        """

        if type(source) == InstagramProfile:
            check_string = source.get_description_from_api()
        else:
            check_string = source

        if check_string is None:
            return self.AVAILABLE_CATEGORIES[2]

        check_string = simplify(check_string.lower())

        chunks = check_string.split()

        # if liketoknow hashtag appears in the profile, then it's a blogger for sure
        if (
            '#liketoknow' in chunks or
            'liketoknow.it/' in check_string or
            'liketk.it/' in check_string
        ):
            return self.AVAILABLE_CATEGORIES[1]  # 'blogger'

        # TODO: https://app.asana.com/0/38788253712150/89518390725641
        # checking if it is a brand
        for kw in self.BRAND_KEYWORDS:
            if kw.lower() in chunks:
                return self.AVAILABLE_CATEGORIES[0]  # 'brand'

        for ph in self.BRAND_PHRASES_LOS:
            # if set(ph).issubset(chunks):
            if contains(ph, chunks):
                return self.AVAILABLE_CATEGORIES[0]  # 'brand'

        # checking if it is a blogger
        for kw in self.BLOGGER_KEYWORDS:
            if kw.lower() in chunks:
                return self.AVAILABLE_CATEGORIES[1]  # 'blogger'

        for ph in self.BLOGGER_PHRASES_LOS:
            # if set(ph).issubset(chunks):
            if contains(ph, chunks):
                return self.AVAILABLE_CATEGORIES[1]  # 'blogger'

        return self.AVAILABLE_CATEGORIES[2]  # 'undecided'

    def classify_queryset(self, queryset=None, category=None, to_tag=True, **kwargs):
        """
        Helper method. Source_queryset should be a queryset for InstagramProfiles.
        Same as above but performs the whole queryset.
        Could return a dict of pairs ' id: classification_value '
        or a queryset object with excluding by ids.

        Example:
        We want to filter queryset so only bloggers should remain:
        we call the function as
        cs.classify_queryset(source_queryset=qs, category='blogger')

        Method's drawback: could be extremely time consuming queryset.
         Could be changed by filtering out ids of objects.


        :param to_tag if set True, then category tag will be set to these profiles
        """

        if category not in self.AVAILABLE_CATEGORIES:
            return queryset

        profiles = queryset_iterator(queryset)

        ids = set()

        for profile in profiles:
            biography = profile.api_data.get('biography')
            if biography is not None and self.classify_unit(profile) == category:
                ids.add(profile.id)

                # setting tag for classified profiles
                if to_tag:
                    profile.append_mutual_exclusive_tag(category, self.AVAILABLE_CATEGORIES)

                    # creating a SocialProfileOp object for this event
                    SocialProfileOp.objects.create(
                        profile_id=profile.id,
                        description=category,
                        module_classname=type(self).__name__,
                        data={}
                    )

        return queryset.filter(id__in=ids)

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next Processor, Classifier or Upgrader in chain.
        """
        return True if result in ['blogger', 'undecided'] else False


class DescriptionLengthClassifier(Classifier):
    """
    Classifies InstagramProfiles by their profile description length.
    """

    # list of all available categories for categorization
    AVAILABLE_CATEGORIES = [
        'SHORT_BIO_50',
        'LONG_BIO_50',
    ]

    def classify_unit(self, source=None, **kwargs):
        """
        Classifying source by its description length.
        If description's length is less than 50 characters, then it is considered a blogger, otherwise undecided.
        """

        if type(source) == InstagramProfile:
            check_string = source.get_description_from_api()
        else:
            check_string = source

        if check_string is None:
            return self.AVAILABLE_CATEGORIES[0]

        return self.AVAILABLE_CATEGORIES[0] if len(check_string) <= 50 else self.AVAILABLE_CATEGORIES[1]

    def classify_queryset(self, queryset=None, category=None, to_tag=True, **kwargs):
        """
        Helper method. Source_queryset should be a queryset for InstagramProfiles.
        Same as above but performs the whole queryset.
        Could return a dict of pairs ' id: classification_value '
        or a queryset object with excluding by ids.

        Example:
        We want to filter queryset so only bloggers should remain:
        we call the function as
        cs.classify_queryset(source_queryset=qs, category='blogger')

        :param to_tag if set True, then category tag will be set to these profiles
        """

        if category not in self.AVAILABLE_CATEGORIES:
            return queryset

        profiles = queryset_iterator(queryset)

        ids = set()

        for profile in profiles:
            if self.classify_unit(profile) == category:
                ids.add(profile.id)

                # setting tag for classified profiles
                if to_tag:
                    profile.append_mutual_exclusive_tag(category, self.AVAILABLE_CATEGORIES)

                    # creating a SocialProfileOp object for this event
                    SocialProfileOp.objects.create(
                        profile_id=profile.id,
                        description=category,
                        module_classname=type(self).__name__,
                        data={}
                    )

        return queryset.filter(id__in=ids)

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next Processor, Classifier or Upgrader in chain.
        """
        return True  # if result in self.AVAILABLE_CATEGORIES else False


class NLTKHashtagsClassifier(Classifier):
    """
    Classifies InstagramProfiles as blogger, brand or undecided.

    Currently is a PROTOTYPE.
    """

    # list of all available categories for categorization
    AVAILABLE_CATEGORIES = [
        'brand',
        'blogger',
        'undecided',
    ]

    classifier = None
    undecided_margin = None

    def __init__(self, blogger_hashtags=[], brand_hashtags=[], undecided_margin=None):
        """
        Explicitly inits lists of hashtags and creates NLTK Classifier object.
        Lists are not intended to contain unique hashtags.
        :param blogger_hashtags: list of lists of hashtags suitable for bloggers
        :param brand_hashtags: list of lists of hashtags suitable for brands
        :param undecided_margin: probability margin when to consider classification result as undecided
        :return:
        """
        from textblob.classifiers import NaiveBayesClassifier

        initial_train = []
        for v in blogger_hashtags:
            initial_train.append((v, self.AVAILABLE_CATEGORIES[1]))
        for v in brand_hashtags:
            initial_train.append((v, self.AVAILABLE_CATEGORIES[0]))
        self.classifier = NaiveBayesClassifier(initial_train)
        initial_train = []

    def classify_unit(self, source=None, **kwargs):
        """
        This method is the core of classification algorithm. It receives source data for classification (object, model,
        string, etc.) and returns a value of classification category for this object.
        For example, we use InstagramProfile as source data, and result could be either 'brand' or 'blogger'
        or 'undecided'.
        """
        # return 'brand'

        cat_classified = self.classifier.classify(source)
        probability = self.classifier.prob_classify(source)

        # TODO: add probability_margin logic here

        return cat_classified

    def classify_queryset(self, source_queryset=None, **kwargs):
        """
        Helper method. Same as above but performs the whole queryset.
        Return queryset
        """
        # TODO: Think how to do it for this classifier.

        raise NotImplemented

    def update_classifier(self, extra_data=None):
        """

        """
        if extra_data is not None:
            self.classifier.update(extra_data)



class HaveYoutubeUrlClassifier(Classifier):
    """
    Classifier by keywords in description of InstagramProfile.
    Classifies InstagramProfiles as 'have_youtube' if it contains some youtube link in content.

    """

    AVAILABLE_CATEGORIES = [
        'have_youtube',
    ]

    youtube_url_chunks = [
        "youtube.com/",
        "youtu.be/",
        "y2u.be/",
    ]

    def classify_unit(self, source=None, **kwargs):
        """
        Classifying source by if it contains something like youtube url regexp.

        youtube
        youtu.be
        """

        if type(source) == InstagramProfile:
            check_string = source.get_description_from_api()
        else:
            check_string = source

        if check_string is not None and any([uc in check_string for uc in self.youtube_url_chunks]):
            return self.AVAILABLE_CATEGORIES[0]

        check_url = source.get_url_from_api()
        if check_url is not None:
            if any([uc in check_url for uc in self.youtube_url_chunks]):
                return self.AVAILABLE_CATEGORIES[0]

        return None  # no youtube url found

    def classify_queryset(self, queryset=None, category=None, to_tag=True, **kwargs):
        """
        Helper method. Source_queryset should be a queryset for InstagramProfiles.
        Same as above but performs the whole queryset.
        Could return a dict of pairs ' id: classification_value '
        or a queryset object with excluding by ids.

        Example:
        We want to filter queryset so only bloggers should remain:
        we call the function as
        cs.classify_queryset(source_queryset=qs, category='blogger')

        Method's drawback: could be extremely time consuming queryset.
         Could be changed by filtering out ids of objects.


        :param to_tag if set True, then category tag will be set to these profiles
        """

        if category not in self.AVAILABLE_CATEGORIES:
            return queryset

        profiles = queryset_iterator(queryset)

        ids = set()

        for profile in profiles:
            biography = profile.api_data.get('biography')
            if biography is not None and self.classify_unit(profile) == category:
                ids.add(profile.id)

                # setting tag for classified profiles
                if to_tag:

                    # profile.append_mutual_exclusive_tag(category, self.AVAILABLE_CATEGORIES)
                    if category is not None:
                        profile.append_mutual_exclusive_tag(category, self.AVAILABLE_CATEGORIES)
                    elif profile.tags is not None and any([t in profile.tags for t in self.AVAILABLE_CATEGORIES]):
                        profile.tags = ' '.join([t for t in profile.tags.split() if t not in self.AVAILABLE_CATEGORIES])
                        profile.save()

                    # creating a SocialProfileOp object for this event
                    SocialProfileOp.objects.create(
                        profile_id=profile.id,
                        description=category,
                        module_classname=type(self).__name__,
                        data={}
                    )

        return queryset.filter(id__in=ids)

    def proceed(self, result):
        """
        This function determines condition when it will proceed to the next Processor, Classifier or Upgrader in chain.
        """
        return True


class HaveYoutubeKeywordClassifier(KeywordClassifier):
    """
    uses separate youtube queue
    """
    pass


class HaveYoutubeDescriptionLengthClassifier(DescriptionLengthClassifier):
    """
    uses separate youtube queue
    """
    pass
