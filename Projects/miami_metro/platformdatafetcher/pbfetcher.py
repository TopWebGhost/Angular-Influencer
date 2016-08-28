import datetime
import datetime
import logging
from collections import defaultdict
import sys
import pprint
from collections import namedtuple

import baker
from celery.decorators import task
from django.conf import settings
from platformdatafetcher.platformutils import TaskSubmissionTracker

import debra.models
from xpathscraper import utils
from platformdatafetcher import platformutils


log = logging.getLogger('platformdatafetcher.pbfetcher')


PAGES_FOR_NEW_FETCHER_CLASS = 20


class Policy(object):

    """A base class for implementations of policies used by fetchers (blog and social).

    The policy tells the following things:

    * what data fetchers should use for API calls (like api keys, client ids)
    * which Platforms it applies to -- method :meth:`Policy.applies_to_platform`
    * how important it is to fetch data for a given platform in the next 24 hours
      -- method :meth:`Policy.importance_score`.
    * how to call a fetcher to get needed data (mainly, how much data to fetch) --
      method :meth:`Policy.perform_fetching`.
    * if fetching should be continued -- method :meth:`Policy.should_continue_fetching`.
      Fetchers should call this function and check for a result after each API call
      they make.

    :attr:`Policy.name` is a name of a policy, saved into a database (must be unique and not ``None``).

    :attr:`Policy.API_DATA` is a dictionary with api data. Keys are platform names, values are
    dictionaries with API data keys as keys and API data values as values.
    """

    name = None

    API_DATA = {
        'Wordpress': {},
        'Blogspot': {
            'api_key': [
                'AIzaSyAVu_qvw9SuvUxo9CdrxKWLEVk24RWIKos',
                'AIzaSyA9wVIwr4M5B5nnaXnoY_mZNIl2ZmW1jXg',
                'AIzaSyCrLfHtw1ehhpOoZk_V6rJOL_ENJBRCzuI',
            ],
        },
        # Same as Blogspot
        'Youtube': {
            'api_key': [
                'AIzaSyAVu_qvw9SuvUxo9CdrxKWLEVk24RWIKos',
                'AIzaSyA9wVIwr4M5B5nnaXnoY_mZNIl2ZmW1jXg',
                'AIzaSyCrLfHtw1ehhpOoZk_V6rJOL_ENJBRCzuI',
            ],
        },
        'Instagram': {
            'client_id': [
                'b6d5ce879d9d4c46af4d7f02f2100d2c'
            ],
        },
    }

    def fetcher_queue_name(self, queue_type, platform_name):
        return '{}.fetching.{}'.format(queue_type, platform_name)

    def create_api_data(self, to_save=False):
        """Converts :attr:`Policy.API_DATA` dict into a list of ``debra.models.FetcherApiData*``
        models.

        :param to_save: tells if a ``save()`` call should be executed on the created models.
        """

        assert self.name is not None
        res = []
        for platform_name in self.API_DATA:
            res += self._create_api_data_for_platform(platform_name, to_save)
        return res

    def _create_api_data_for_platform(self, platform_name, to_save):
        res = []
        for key, values in self.API_DATA[platform_name].items():
            spec = debra.models.FetcherApiDataSpec(policy_name=self.name,
                                                   platform_name=platform_name,
                                                   key=key)
            if to_save:
                spec.save()
            res_vals = []
            for i, val in enumerate(values):
                val_m = debra.models.FetcherApiDataValue(spec=spec,
                                                         value_index=i,
                                                         value=val)
                if to_save:
                    val_m.save()
                res_vals.append(val_m)
            res.append((spec, res_vals))
        return res

    def get_api_data_value(self, platform_name, key):
        spec_q = debra.models.FetcherApiDataSpec.objects.filter(policy_name=self.name,
                                                                platform_name=platform_name,
                                                                key=key)
        if not spec_q.exists():
            log.warn('Api data spec does not exist for platform_name=%s, key=%s', platform_name, key)
            return None
        spec = spec_q[0]

        ip = utils.get_ip_address()
        log.info('Getting assignment for ip=%s', ip)
        assignment_q = debra.models.FetcherApiDataAssignment.objects.filter(spec=spec,
                                                                            server_ip=ip)
        if assignment_q.exists():
            val = assignment_q[0].value_m.value
            log.info('Returning already assigned value for key %s: %s', key, val)
            return val

        all_values = list(debra.models.FetcherApiDataValue.objects.filter(spec=spec).
                          order_by('value_index'))
        last_used = max(all_values, key=lambda v_m: v_m.last_usage or
                        datetime.datetime.now() - datetime.timedelta(days=365))
        log.info('Last used value with value_index=%s: %s', last_used.value_index, last_used.value)
        next_index = (last_used.value_index + 1) % len(all_values)
        values_with_next_index = [v_m for v_m in all_values if v_m.value_index == next_index]
        assert values_with_next_index, 'value_index values not contigous'
        assert len(values_with_next_index) == 1, 'More than one record with value_index=%s' % \
            next_index
        next_value = values_with_next_index[0]
        next_value.last_usage = datetime.datetime.now()
        next_value.save()
        new_assignment = debra.models.FetcherApiDataAssignment(spec=spec,
                                                               value_m=next_value,
                                                               server_ip=ip)
        new_assignment.save()
        return next_value.value

    def applies_to_platform(self, platform):
        raise NotImplementedError()

    def importance_score(self, platform):
        raise NotImplementedError()

    def perform_fetching(self, fetcher_impl):
        raise NotImplementedError()

    def should_continue_fetching(self, fetcher_impl):
        from . import fetchertasks
        saved_posts = fetcher_impl.counts['posts_saved']
        skipped_posts = fetcher_impl.counts['posts_skipped']
        total_posts = saved_posts + skipped_posts
        log.info('Total posts fetched: %d, checking if it is enough', total_posts)

        if fetcher_impl.platform.platform_name in debra.models.Platform.SOCIAL_PLATFORMS and \
                total_posts >= fetchertasks.MIN_POSTS_NEEDED_FOR_ENABLING_INDEPTH_PROCESSED_FOR_SOCIAL_PLATFORM and \
                self.name == 'indepth':
            log.debug('It is enough')
            return False
        if fetcher_impl.platform.platform_name in debra.models.Platform.BLOG_PLATFORMS and \
                total_posts >= fetchertasks.MIN_POSTS_NEEDED_FOR_ENABLING_INDEPTH_PROCESSED_FOR_BLOG_PLATFORM and \
                self.name == 'indepth':
            log.debug('It is enough')
            return False
        if self.name == "newinfluencer" and total_posts >= fetchertasks.MIN_POSTS_NEEDED_FOR_CHECKING_RELEVANCY:
            log.info('It is enough: this is a newinfluencer policy and we have already crawled %d posts', total_posts)
            return False

        threshold = fetcher_impl.get_skipped_posts_threshold()
        if skipped_posts > threshold:
            log.info('Stopping fetching after getting {} posts and hitting the threshold.'.format(
                skipped_posts
            ))
            return False

        log.debug('Not enough')
        return True

    # A helper method, can be called by subclasses
    def _refetch_interactions(self, fetcher_impl, max_age_days):
        # find posts that were added to our DB exactly max_age_days ago
        # Earlier, we were re-fetching ALL posts in the last max_age_days, but that was in-efficient
        # we just need to do it only once
        if fetcher_impl.platform.platform_name == 'Pinterest':
            # we don't have reliable ways to get the create_date for Pinterest, so we use inserted_datetime
            posts = fetcher_impl.platform.posts_set.all().\
                filter(inserted_datetime__contains=datetime.datetime.now() - datetime.timedelta(days=max_age_days))
        else:
            posts = fetcher_impl.platform.posts_set.all().\
                filter(create_date__contains=datetime.datetime.now() - datetime.timedelta(days=max_age_days))
        log.info('Refetching post interactions for platform <%s> posts %s', fetcher_impl.platform,
                 len(posts))

        if fetcher_impl.platform.platform_name_is_blog:
            fetcher_impl.fetch_post_interactions_extra(posts)
        else:
            fetcher_impl.fetch_post_interactions(posts)
        log.debug('Finished refetching')

    def get_max_pages(self, platform, default_max_pages):
        """Return number of pages of posts to fetch, based on a default value.
        """
        from platformdatafetcher import fetcher

        if fetcher.fetcher_class_changed_recently(platform):
            return max(PAGES_FOR_NEW_FETCHER_CLASS, default_max_pages)
        return default_max_pages

    def __repr__(self):
        return '{cls}(name={name})'.format(cls=self.__class__.__name__, name=self.name)


class AgeBasedPolicy(Policy):
    INITIAL_SCORE = None
    SCORE_PER_DAY = None
    MAX_SCORE = None
    SCORE_FOR_NOT_FETCHED = None

    def importance_score(self, platform):
        assert self.INITIAL_SCORE is not None and self.SCORE_PER_DAY is not None and \
            self.MAX_SCORE is not None and self.SCORE_FOR_NOT_FETCHED is not None

        if platform.last_api_call is None:
            return self.SCORE_FOR_NOT_FETCHED

        age = datetime.datetime.now() - platform.last_api_call
        age_days = age.total_seconds() / 86400.0
        score = self.INITIAL_SCORE + self.SCORE_PER_DAY * age_days
        score = min(self.MAX_SCORE, score)
        return score


class PostingFrequencyBasedPolicy(Policy):
    _DAYS_LOOKBACK = 90

    def importance_score(self, platform):
        if not platform.posts_set.filter(create_date__isnull=False).exists():
            return 0.0
        first_post_to_look_q = platform.posts_set.\
            filter(create_date__isnull=False,
                   create_date__gte=datetime.datetime.now() -
                   datetime.timedelta(days=self._DAYS_LOOKBACK)).\
            order_by('create_date')
        if not first_post_to_look_q.exists():
            return 0.0
        first_post_to_look = first_post_to_look_q[0]
        lookback_days = utils.timedelta_to_days(datetime.datetime.now() - first_post_to_look.create_date)
        log.debug('lookback_days: %s', lookback_days)
        if lookback_days < 0:
            return 0.0
        posts_count = platform.posts_set.filter(create_date__gte=first_post_to_look.create_date).count()
        avg_days_between_posts = float(lookback_days) / float(posts_count)
        log.debug('posts_count=%s, avg_days_between_posts=%s', posts_count, avg_days_between_posts)
        latest_post_date = platform.posts_set.filter(create_date__isnull=False).\
            order_by('-create_date')[0].create_date
        expected_new_post = latest_post_date + datetime.timedelta(days=avg_days_between_posts)
        log.debug('expected_new_post=%s', expected_new_post)

        # score will be negative if a new post is expected after today, positive if it
        # should be already present
        score_td = expected_new_post - datetime.datetime.now()
        return utils.timedelta_to_days(score_td)


class SignedupInfluencerPolicy(AgeBasedPolicy):

    """A policy for influencers that signed up on the site
    """

    name = 'signedup'

    INITIAL_SCORE = 500
    MAX_SCORE = 600
    SCORE_PER_DAY = 10
    # This shouldn't be used
    SCORE_FOR_NOT_FETCHED = 200

    def applies_to_platform(self, platform):
        return platform.influencer.source and 'blogger_signup' in platform.influencer.source

    def perform_fetching(self, fetcher_impl):
        # fetch post interactions for posts fetched 7 days and 35 days ago
        # this is the start and end of the range of dates for which we want
        # to monitor
        self._refetch_interactions(fetcher_impl, 7)
        self._refetch_interactions(fetcher_impl, 35)
        fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 3)) # FIXME Not fetching followers for now
        #fetcher_impl.fetch_posts(max_pages=1)

        # fetcher_impl.fetch_platform_followers(3, False)


class ForSearchPolicy(AgeBasedPolicy):

    """A policy for influencers with show_on_search == True
    """

    name = 'forsearch'

    INITIAL_SCORE = 200
    MAX_SCORE = 300
    SCORE_PER_DAY = 10
    # This shouldn't be used
    SCORE_FOR_NOT_FETCHED = 200

    def applies_to_platform(self, platform):
        return platform.influencer.show_on_search is True

    def perform_fetching(self, fetcher_impl):
        # fetch post interactions for posts fetched 7 days and 35 days ago
        # this is the start and end of the range of dates for which we want
        # to monitor
        self._refetch_interactions(fetcher_impl, 7)
        self._refetch_interactions(fetcher_impl, 35)
        fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 1))
        #fetcher_impl.fetch_posts(max_pages=1)


class RelevantToFashionPolicy(AgeBasedPolicy):

    """A policy for influencers with show_on_search == None (not computed yet)
    but with relevant_to_fashion == True
    """
    name = 'relevanttofashion'

    INITIAL_SCORE = 400
    MAX_SCORE = 500
    SCORE_PER_DAY = 10
    SCORE_FOR_NOT_FETCHED = 400

    def applies_to_platform(self, platform):
        return platform.influencer.show_on_search is None and \
            platform.influencer.relevant_to_fashion is not None and \
            platform.influencer.active() and \
            platform.validated_handle is None and \
            platform.platform_name in debra.models.Platform.SOCIAL_PLATFORMS

    def perform_fetching(self, fetcher_impl):
        #self._refetch_interactions(fetcher_impl, 3)
        #fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 1))
        fetcher_impl.fetch_posts(max_pages=1)


class NewInfluencerPolicy(AgeBasedPolicy):

    """A policy for Influencers with
        show_on_search == None and
        relevant_to_fashion == None (not computed yet)
        but classification == 'blog'
        and url is a blogspot (for now)
    """

    name = 'newinfluencer'

    INITIAL_SCORE = 0
    MAX_SCORE = 100
    SCORE_PER_DAY = 10
    SCORE_FOR_NOT_FETCHED = 100

    def applies_to_platform(self, platform):
        return platform.influencer.show_on_search is None and platform.activity_level is None \
            and platform.influencer.blog_url is not None and platform.influencer.source is not None \
            and platform.platform_name in ['Blogspot', 'Wordpress', 'Tumblr', 'Custom']

    def perform_fetching(self, fetcher_impl):
        # Refetching interactions for new influencers doesn't make sense
        #fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 5))
        fetcher_impl.fetch_posts(max_pages=100)


class NotForSearchPolicy(AgeBasedPolicy):
    """A policy for influencers with show_on_search == False
    They were marked as not relevant to fashion, but maybe they
    will be marked as relevant after fetching new posts.
    """

    name = 'notforsearch'

    INITIAL_SCORE = 0
    MAX_SCORE = 100
    SCORE_PER_DAY = 10
    # This shouldn't be used
    SCORE_FOR_NOT_FETCHED = 100

    def applies_to_platform(self, platform):
        return platform.influencer.show_on_search is True

    def perform_fetching(self, fetcher_impl):
        self._refetch_interactions(fetcher_impl, 3)
        fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 10))
        # FIXME Not fetching followers for now
        fetcher_impl.fetch_platform_followers(3, False)


class DefaultPolicy(AgeBasedPolicy):
    '''
    A catch-all policy that we use as a last resort.

    It just fetches a single page of posts and no interactions.
    '''
    name = 'default'

    INITIAL_SCORE = 0
    MAX_SCORE = 10
    SCORE_PER_DAY = 1
    SCORE_FOR_NOT_FETCHED = 100

    def applies_to_platform(self, platform):
        return True

    def perform_fetching(self, fetcher_impl):
        fetcher_impl.fetch_posts(max_pages=1)


class ShelfUserPolicy(AgeBasedPolicy):
    name = 'shelfuser'

    INITIAL_SCORE = 30
    MAX_SCORE = 100
    SCORE_PER_DAY = 10
    SCORE_FOR_NOT_FETCHED = 200

    def applies_to_platform(self, platform):
        return platform.influencer.shelf_user is not None

    def perform_fetching(self, fetcher_impl):
        self._refetch_interactions(fetcher_impl, 14)
        fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 10))
        fetcher_impl.fetch_platform_followers(10, False)


class TrendsetterPolicy(AgeBasedPolicy):
    name = 'trendsetter'

    INITIAL_SCORE = 100
    MAX_SCORE = 200
    SCORE_PER_DAY = 10
    SCORE_FOR_NOT_FETCHED = 300

    def applies_to_platform(self, platform):
        if platform.influencer.shelf_user is None:
            return False
        return debra.models.UserProfile.objects.get(user=platform.influencer.shelf_user).is_trendsetter

    def perform_fetching(self, fetcher_impl):
        self._refetch_interactions(fetcher_impl, 14)
        fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 1))
        fetcher_impl.fetch_platform_followers(10, False)


class PopularInfluencerPolicy(AgeBasedPolicy):
    name = 'popularinfluencer'

    INITIAL_SCORE = 10
    MAX_SCORE = 20
    SCORE_PER_DAY = 1
    SCORE_FOR_NOT_FETCHED = 100

    def _platform_popularity_score(self, platform):
        return (platform.total_numlikes or 0) + \
            (platform.num_followers or 0)

    def _influencer_popularity_score(self, influencer):
        return sum(self._platform_popularity_score(platform) for platform in
                   influencer.platform_set.all())

    def applies_to_platform(self, platform):
        return self._influencer_popularity_score(platform.influencer) >= 100

    def importance_score(self, platform):
        age_score = AgeBasedPolicy.importance_score(self, platform)
        pop_score = self._platform_popularity_score(platform)
        return age_score + min(10, (pop_score // 1000))

    def perform_fetching(self, fetcher_impl):
        self._refetch_interactions(fetcher_impl, 7)
        fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 10))
        fetcher_impl.fetch_platform_followers(4, False)


class FollowerPolicy(AgeBasedPolicy):
    name = 'followerpolicy'

    INITIAL_SCORE = 10
    MAX_SCORE = 20
    SCORE_PER_DAY = 1
    SCORE_FOR_NOT_FETCHED = 100

    def applies_to_platform(self, platform):
        return platform.processing_state == debra.models.Platform.PROCESSING_STATE_NEW_FOLLOWERS_PLATFORM

    def perform_fetching(self, fetcher_impl):
        fetcher_impl.fetch_posts(max_pages=self.get_max_pages(fetcher_impl.platform, 10))
        fetcher_impl.fetch_platform_followers(10, False)

        # After processing a new follower's platform, set 'state' to default value
        # so later the platform will be processed as other platforms
        fetcher_impl.platform.state = None
        fetcher_impl.platform.save()


class BrandsPolicy(AgeBasedPolicy):

    """A policy for influencers with tag brands_for_discovering_new_inf
    """

    name = 'brands'

    INITIAL_SCORE = 200
    MAX_SCORE = 300
    SCORE_PER_DAY = 10
    SCORE_FOR_NOT_FETCHED = 200

    def applies_to_platform(self, platform):
        return platform.influencer.tags and \
            'brands_for_discovering_new_inf' in platform.influencer.tags

    def perform_fetching(self, fetcher_impl):
        platform = fetcher_impl.platform
        posts = debra.models.Posts.objects.filter(platform=platform)
        first_time = posts.count() == 0
        fetcher_impl.fetch_posts(max_pages=400 if first_time else 20)


class IndepthPolicy(Policy):

    """A policy that can be applied to any influencer - fetches all available data.
    It's meant to be used with separate queues ``indepth_fetching.*``. It is not included
    in the :data:``POLICIES`` list and it's not automatically selected for Influencers.
    """
    name = 'indepth'

    def applies_to_platform(self, platform):
        return True

    def importance_score(self, platform):
        return 100

    def perform_fetching(self, fetcher_impl):
        fetcher_impl.fetch_posts(max_pages=200)
        #fetcher_impl.fetch_platform_followers(20, False)


# More specific policies must be put first, because the first matching policy will be used
POLICIES = [
    SignedupInfluencerPolicy(),
    BrandsPolicy(),
    ForSearchPolicy(),
    RelevantToFashionPolicy(),
    NewInfluencerPolicy(),
    # FIXME not processing influencers with show_on_search == False for now
    # NotForSearchPolicy(),

    # old list
    # TrendsetterPolicy(),
    # ShelfUserPolicy(),
    # PopularInfluencerPolicy(),
    DefaultPolicy(),
]

POLICY_NAME_TO_POLICY = {p.name: p for p in POLICIES}


def policy_for_platform(platform):
    for p in POLICIES:
        if p.applies_to_platform(platform):
            return p
    #log.warn('No policy applies to platform %r', platform)
    return None


def sort_platforms_for_fetching(query_set, ordering='by_id_and_day'):
    """
    Here platforms for fetching are sorted according to ordering parameters.
    Possible issue is that they are not allowing all platforms to be re-crawled.

    :param query_set:
    :param ordering:
    :return:
    """
    all_platform_infos = []
    platform_infos = []
    blog_signedup_infos = []
    for platform in query_set.iterator():
        policy = policy_for_platform(platform)
        if policy is None:
            continue
        score = policy.importance_score(platform)

        all_platform_infos.append(
            PlatformInfo(platform.id, platform.platform_name, score, policy))

        platform_infos.append(
            PlatformInfo(platform.id, platform.platform_name, score, policy))

        if platform.influencer.source and 'blogger_signup' in platform.influencer.source:
            blog_signedup_infos.append(
                PlatformInfo(platform.id, platform.platform_name, score, policy))
        if len(platform_infos) % 1000 == 0:
            log.info('Processed %d platforms', len(platform_infos))

    log.info('Total platforms: %d, sorting...', len(platform_infos))
    all_platform_infos.sort(key=lambda info: info.score, reverse=True)

    if ordering == 'by_score':
        platform_infos.sort(key=lambda info: info.score, reverse=True)
    if ordering == 'by_id_and_day':
        # Update on June 12 2016: just letting the sorting order as provided by the caller function
        # which is based on last_updated time. Which should work perfectly.
        pass
        
        # tod = datetime.date.today()
        # total = len(platform_infos)
        # perday = total / 7
        # start = perday * tod.weekday()
        # end = start + perday
        # # here, we sort by id first
        # platform_infos.sort(key=lambda info: info.id)
        # # and then pick the subset
        # platform_infos = platform_infos[start: end]
        #
        # # now let's append the signed up users (so that we crawl them everyday if we have resources)
        # platform_infos.extend(blog_signedup_infos)
        #
        # # and then let's append the rest of the influencers sorted by score
        # platform_infos.extend(all_platform_infos)

    log.info('Sorted')

    return platform_infos


@task(name='platformdatafetcher.pbfetcher.submit_daily_fetch_tasks', ignore_result=True)
@baker.command
def submit_daily_fetch_tasks():
    with platformutils.OpRecorder(operation='submit_daily_fetch_tasks') as opr:
        counter = TaskCounter()
        submission_tracker = TaskSubmissionTracker()
        query = debra.models.Platform.objects.all().for_daily_fetching()
        plats = _do_submit_daily_fetch_tasks(counter, submission_tracker, query)
        opr.data = {'tasks_submitted': len(plats)}


def submit_daily_fetch_tasks_activity_levels(submission_tracker):
    """
    Get the platforms that need fetching and submit tasks for each of them.

    We distinguish between three groups of platforms according to their activity level:
    1. Platforms that get updated often and need to be fetched daily.
    2. Platforms that have never been fetched and need to be fetched ASAP.
    3. Platforms that get updated infrequently, but we still to update them every once in a while.

    We use a different `queue_type` parameter to route tasks to the correct queue.
    """
    with platformutils.OpRecorder(operation='submit_daily_fetch_tasks') as opr:

        with submission_tracker.operation('first_fetch'):
            counter = TaskCounter()
            not_fetched = debra.models.Platform.objects.all().never_fetched()
            not_fetched = not_fetched.exclude(influencer__blog_url__contains='theshelf.com/artificial')
            plats_not_fetched = _do_submit_daily_fetch_tasks(counter, submission_tracker, not_fetched, queue_type='first_fetch')
            log.info('not_fetched: {}'.format(len(plats_not_fetched)))

        with submission_tracker.operation('every_day'):
            counter = TaskCounter()
            every_day = debra.models.Platform.objects.all().for_everyday_fetching()
            every_day = every_day.exclude(influencer__blog_url__contains='theshelf.com/artificial')
            every_day_ids = every_day.values_list('id', flat=True)

            # we should crawl influencers who are in collections also (without paying attention to whether they
            # are blacklisted or have artificial urls). But exclude platforms that are artificial because
            # we can't crawl them.
            coll = debra.models.InfluencersGroup.objects.all().order_by('id')
            coll = coll.exclude(owner_brand__domain_name__in=['yahoo.com', 'rozetka.com.ua']).exclude(id=1923)
            inf_ids = []
            for c in coll:
                ids = c.influencer_ids
                inf_ids.extend(ids)
            influencer_in_collections = debra.models.Influencer.objects.filter(id__in=inf_ids)
            platforms_in_collections = debra.models.Platform.objects.filter(influencer__in=influencer_in_collections)
            platforms_in_collections = platforms_in_collections.exclude(url_not_found=True)
            platforms_in_collections = platforms_in_collections.exclude(url__contains='theshelf.com/artificial')
            platforms_in_collections_ids = platforms_in_collections.values_list('id', flat=True)
            every_day_ids = list(every_day_ids)
            every_day_ids.extend(list(platforms_in_collections_ids))
            every_day = debra.models.Platform.objects.filter(id__in=every_day_ids)

            # Poor man's rotation to avoid starving tasks always falling on the back of the
            # queue. Those will get moved to the queue front on the next day.
            # TODO:  control if last_fetched is correctly being updated.
            every_day = every_day.order_by('last_fetched')
            plats_every_day = _do_submit_daily_fetch_tasks(counter, submission_tracker, every_day, queue_type='every_day')
            log.info('every_day: {}'.format(len(plats_every_day)))

        with submission_tracker.operation('infrequent'):
            counter = TaskCounter()
            less_often = debra.models.Platform.objects.all().for_infrequent_fetching()
            less_often = less_often.exclude(influencer__blog_url__contains='theshelf.com/artificial')
            plats_less_often = _do_submit_daily_fetch_tasks(counter, submission_tracker, less_often, queue_type='infrequent')
            log.info('less_often: {}'.format(len(plats_less_often)))

        with submission_tracker.operation('infrequent'):
            counter = TaskCounter()
            query = debra.models.Influencer.objects.all().has_tags('customer_uploaded')
            by_customers = debra.models.Platform.objects.filter(influencer__in=query)
            plats_by_customers = _do_submit_daily_fetch_tasks(counter, submission_tracker, by_customers, queue_type='customer_uploaded')
            log.info('plats_uploaded_by_customers: {}'.format(len(plats_by_customers)))

        # here we crawl platforms so that we can get new posts content
        with submission_tracker.operation('discover_new_infs'):
            counter = TaskCounter()
            query = debra.models.Influencer.objects.all().has_tags('brands_for_discovering_new_inf')
            plats = debra.models.Platform.objects.filter(influencer__in=query).filter(platform_name='Instagram')
            plats_by_brands = _do_submit_daily_fetch_tasks(counter, submission_tracker, plats, queue_type='discover_new_infs')
            log.info('discover_new_infs: {}'.format(len(plats_by_brands)))

        all_plats = plats_not_fetched + plats_every_day + plats_less_often + plats_by_customers
        opr.data = {'tasks_submitted': len(all_plats)}
        del all_plats
        del plats_not_fetched
        del plats_less_often
        del plats_by_customers

def submit_daily_social_platform_update_tasks(submission_tracker):
    """
    Get the Gplus and Bloglovin platforms we need to fetch and submit tasks for them.

    We are not really fetching posts here -- just updating platform info.

    We select platforms that have never had their info fetched and ones for which we have
    not done so for over a month.
    """
    with platformutils.OpRecorder(operation='submit_daily_fetch_tasks') as opr:
        counter = TaskCounter()

        with submission_tracker.operation('gplus_fetch'):
            gplus_plats = debra.models.Platform.objects.all().gplus_update_pending()
            gplus_plats = _do_submit_daily_fetch_tasks(counter, submission_tracker, gplus_plats, queue_type='every_day')
            log.info('Gplus: {}'.format(len(gplus_plats)))

        with submission_tracker.operation('bloglovin_fetch'):
            bloglovin_plats = debra.models.Platform.objects.all().bloglovin_update_pending()
            bloglovin_plats = _do_submit_daily_fetch_tasks(counter, submission_tracker, bloglovin_plats, queue_type='every_day')
            log.info('Bloglovin: {}'.format(len(bloglovin_plats)))

        all_plats = gplus_plats + bloglovin_plats
        opr.data = {'tasks_submitted': len(all_plats)}


PlatformInfo = namedtuple('PlatformInfo', [
    'id', 'platform_name', 'score', 'policy'
])


class TaskCounter(object):
    """
    Counts submitted fetch tasks and keeps track of limits.
    """

    UNLIMITED = 100000000
    TASKS_LIMIT = UNLIMITED
    LIMIT_PER_PLATFORM_NAME = {
        'Wordpress': UNLIMITED,
        'Blogspot': UNLIMITED,
        'Twitter': 50000,
        'Instagram': 50000,
        'Facebook': 50000,
        'Pinterest': 50000,
        'Custom': UNLIMITED,
        'blog': 0,
        'Youtube': 50000,
        'Bloglovin': UNLIMITED,
        'Gplus': UNLIMITED,
    }

    def __init__(self):
        self.total = 0
        self.platforms = defaultdict(int)
        self.skipped = defaultdict(int)

    def count(self, platform_name):
        self.total += 1
        self.platforms[platform_name] += 1

    def skip(self, platform_name):
        self.total += 1
        self.skipped[platform_name] += 1

    def should_skip(self, platform_name):
        platform_limit = self.LIMIT_PER_PLATFORM_NAME.get(platform_name, sys.maxint)
        return self.platforms[platform_name] >= platform_limit

    def should_abort(self):
        return self.total >= self.TASKS_LIMIT


class DummyCounter(TaskCounter):
    '''
    Fake task counter with no limits. Helpful in test task submissions from the shell.
    '''
    def count(self, platform_name):
        pass

    def skip(self, platform_name):
        pass

    def should_skip(self, platform_name):
        return False

    def should_abort(self):
        return False


def _do_submit_daily_fetch_tasks(task_counter, submission_tracker, query_set, queue_type='every_day'):
    # from debra.mongo_utils import mongo_mark_issued_platform
    platforms_infos = sort_platforms_for_fetching(query_set)

    # Select platforms to fetch, according to scores and limits
    selected_platforms = []
    for info in platforms_infos:
        if task_counter.should_abort():
            break

        if task_counter.should_skip(info.platform_name):
            task_counter.skip(info.platform_name)
            continue
        else:
            task_counter.count(info.platform_name)
            selected_platforms.append(info)

    log.info('Skipped platforms: %s', pprint.pformat(dict(task_counter.skipped)))

    # Submit tasks
    from . import fetchertasks
    total_selected = len(selected_platforms)
    for c, info in enumerate(selected_platforms):
        log.info('fetching %d %d %s %s' % (c, total_selected, queue_type, info.platform_name))
        submission_tracker.count_task('fetching.{}.{}'.format(queue_type, info.platform_name))
        fetchertasks.submit_platform_task_precomputed(fetchertasks.fetch_platform_data,
                                                      platform_id=info.id,
                                                      queue_type=queue_type,
                                                      platform_name=info.platform_name,
                                                      policy=info.policy)

        # writing data to mongodb about issued platforms
        # ATUL: this is not needed, we just need to keep track of platforms that were not crawled
        # and this causes a lot of delay
        # mongo_mark_issued_platform(info.id)

    log.info('Tasks submitted')
    return selected_platforms


@task(name='platformdatafetcher.pbfetcher.submit_indepth_tasks', ignore_result=True)
@baker.command
def submit_indepth_tasks():
    platforms = debra.models.Platform.objects.\
        filter(indepth_processed=False).\
        filter(platform_name__isnull=False).\
        filter(platform_name__in=settings.DAILY_FETCHED_PLATFORMS).\
        filter(influencer__show_on_search=True).\
        order_by('create_date')

    from . import fetchertasks
    for platform in platforms:
        fetchertasks.submit_indepth_platform_task(fetchertasks.indepth_fetch_platform_data, platform)

    log.info('Submitted %d indepth tasks' % len(platforms))


POLICIES_TO_STORE_IN_DB = POLICIES + [IndepthPolicy()]


@baker.command
def recreate_api_data():
    debra.models.FetcherApiDataAssignment.objects.all().delete()
    debra.models.FetcherApiDataValue.objects.all().delete()
    debra.models.FetcherApiDataSpec.objects.all().delete()
    for p in POLICIES_TO_STORE_IN_DB:
        p.create_api_data(to_save=True)


@baker.command
def insert_new_api_data():
    for p in POLICIES_TO_STORE_IN_DB:
        models = p.create_api_data(to_save=False)
        pprint.pprint(models)
        for spec_m, val_ms in models:
            specs = debra.models.FetcherApiDataSpec.objects.filter(
                policy_name=spec_m.policy_name,
                platform_name=spec_m.platform_name,
                key=spec_m.key)
            if not specs.exists():
                spec_m.save()
            else:
                spec_m = specs[0]
            for val_m in val_ms:
                if not debra.models.FetcherApiDataValue.objects.filter(
                        spec=spec_m,
                        value_index=val_m.value_index,
                        value=val_m.value).exists():
                    val_m.spec = spec_m
                    val_m.save()

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
