"""Base class for fetchers and helper functions.
"""


import logging
import time
import datetime

from debra import models
from debra import helpers, constants
from . import descriptionfetcher
from . import postinteractionsfetcher
from . import platformutils
from . import categorization
from . import postanalysis
from hanna import import_from_blog_post


log = logging.getLogger('platformdatafetcher.fetcherbase')

DEFAULT_SECONDS_TO_WAIT = 30


class FetcherException(Exception):
    pass


class FetcherCallLimitException(FetcherException):

    def __init__(self, msg, root_exc=None, to_wait=DEFAULT_SECONDS_TO_WAIT):
        Exception.__init__(self, msg)
        self.root_exc = root_exc
        self.to_wait = to_wait

    def seconds_to_wait(self):
        return max(1, self.to_wait)


class Fetcher(object):
    """Base class for Blog and social fetchers.
    Fetching is divided into three methods: ``fetch_posts``, ``fetch_post_interactions`` and
    ``fetch_platform_followers``.

    The first returns :class:`models.Posts` list, the second one takes a :class:`models.Posts` list
    for which to fetch :class:`models.PostInteractions`.

    The third method ``fetch_platform_followers`` creates ``models.PlatformFollower`` objects
    (and saves them in the database) and returns them as a list.

    All methods must accept ``max_pages`` kwarg.

    """

    name = 'unknown'

    def __init__(self, platform, policy):
        assert isinstance(platform, models.Platform)
        if platform.url_not_found:
            raise FetcherException('Platform %s has url_not_found == True' % platform.id)
            
        self.platform = platform
        self.policy = policy
        self.counts = {
            'posts_skipped': 0,
            'posts_saved': 0,
            'pis_skipped': 0,
            'pis_saved': 0,
        }
        self.created_pis = []
        self.test_run = False
        self.new_fetcher_class = None
        self.force_fetch_all_posts = False

    def _inc(self, what):
        """Increment a counter used for debugging/monitoring (see :attr:`Fetcher.counts`)."""
        self.counts[what] += 1

    def fetch_posts(self, max_pages=None):
        """Fetch and return a list of :class:`debra.models.Posts` models.
        Also fetches :class:`debra.models.PostInteractions` for each post."""
        raise NotImplementedError()

    def fetch_post_interactions(self, posts, max_pages=None):
        """Fetch a list of :class:`debra.models.PostInteractions` models. for ``posts``"""
        raise NotImplementedError()

    def get_skipped_posts_threshold(self):
        '''
        The maximum number of existing posts while fetching.

        If we hit that number, we assume we have fetched all the new posts already and stop fetching.

        The default value is 3, but fetchers can override it, if needed.
        '''
        return 3

    def save_post(self, post):
        new_post = post.pk is None

        log.debug('Saving post %r', post)
        if not self.test_run:
            post.platform_name = post.platform.platform_name
            post.save()
        self._inc('posts_saved')

        if new_post and not self.test_run:
            log.info("Great, creating a new post %s" % post)
            if post.influencer.old_show_on_search and \
                    post.influencer.platforms().filter(num_followers__gte=constants.MIN_FOLLOWERS_TO_QUALIFY_FOR_PRODUCT_IMPORT).exclude(url_not_found=True).count() > 0:
                log.info("This post %s has show_on_search true, so issuing import_task directly" % post)
                # queue the import task right away if this influencer is showing on search
                # regardless of what kind of platform it is (social or blog)
                shelf_user_id = post.influencer.shelf_user.id if post.influencer.shelf_user else None
                import_from_blog_post.fetch_products_from_post.apply_async([post.id, shelf_user_id],
                                                                           queue='import_products_from_post_directly')
            else:
                if post.platform.platform_name_is_blog:
                    log.info("This post %s doesn't have show_on_search set, so issuing categorization directly" % post)
                    # categorization is run directly only for new influencers
                    categorization.categorize_post.apply_async([post.id], queue='post_categorization')



    def fetch_post_interactions_extra(self, posts, max_pages=None):
        """Calls ``fetch_post_interactions(posts)``, if
        this call does not return interactions then it tries to use
        other post interactions providers (DisqusFetcher for now).
        """
        if not posts:
            return []
        pis = []
        try:
            pis = self.fetch_post_interactions(posts, max_pages=max_pages)
        except:
            log.exception('While fetch_post_interactions')
            pass
        if pis:
            return pis
        log.info('Fetched did not give post interactions, trying social widgets')
        pis = postinteractionsfetcher.fetch_for_posts(posts)
        log.info('Got %d comments from social widget', len(pis))
        return pis

    def fetch_platform_followers(self, max_pages=2, follower=True):
        """Fetch a list of :class:`debra.models.PlatformFollower` models.

        if `follower`=True => we only pick this users followers
        if `follower`=False => we only pick users that this user follows
        """
        # For default, we return an empty list as this method
        # can not be implemented for all fetchers
        return []

    def cleanup(self):
        """Clean resources consumed by this fetcher."""
        pass

    def should_update_old_posts(self):
        return self.force_fetch_all_posts or self.new_fetcher_class

    def _get_follower(self, display_name, url):
        kwargs = {'firstname': display_name, 'url': url}
        return helpers.get_first_or_create(models.Follower.objects, kwargs)

    def _pi_exists(self, pi):
        assert pi.post
        assert pi.follower
        return pi.post.postinteractions_set.filter(create_date=pi.create_date,
                                                   content=pi.content,
                                                   if_liked=pi.if_liked,
                                                   if_shared=pi.if_shared,
                                                   if_commented=pi.if_commented).exists()

    def _save_pi(self, pi, saved_pis):
        if not self._pi_exists(pi):
            if not self.test_run:
                pi.save()
            self._inc('pis_saved')
            log.debug('Saved new post interaction id=%s', pi.id)
            saved_pis.append(pi)
            self.created_pis.append(pi)
            return True
        self._inc('pis_skipped')
        log.debug('Skipping existing PostInteraction %r', pi)
        return False

    def _fetch_description(self):
        if not self.platform.influencer.is_enabled_for_automated_edits():
            log.warn('Influencer not enabled for edits, not fetching description')
            return
        try:
            df = descriptionfetcher.FromMetaTagsDescriptionFetcher(self.platform.url)
            desc = df.fetch_description()
            if desc:
                log.info('Updating platform description to: %r', desc)
                platformutils.record_field_change('from_description_fetcher',
                    'description', self.platform.description, desc,
                    platform=self.platform)
                self.platform.description = desc
                self.platform.save()
            else:
                log.info('No platform description found')
        except:
            log.exception('While fetching platform description')
            pass

    def _ensure_has_validated_handle(self):
        if self.platform.validated_handle:
            log.info('validated_handle already exists: %r', self.platform.validated_handle)
            return True
        self._set_validated_handle()
        if self.platform.validated_handle:
            log.info('created new validated_handle: %r', self.platform.validated_handle)
            return True
        log.warn('unable to create validated_handle')
        return False

    def _set_validated_handle(self):
        validated_handle = None
        try:
            validated_handle = retry_when_call_limit(lambda: self.get_validated_handle())
        except FetcherCallLimitException:
            log.exception('API limit while getting validated_handle, doing nothing')
            return
        except:
            log.exception('While getting validated_handle, treating as invalid')
            self.platform.validated_handle = None
            platformutils.set_url_not_found('exception_in_get_validated_handle', self.platform)
            return
        if not validated_handle:
            log.warn('Empty validated_handle returned from get_validated_handle, treating as invalid')
            self.platform.validated_handle = None
            platformutils.set_url_not_found('empty_validated_handle', self.platform)
            return
        if models.Platform.objects.filter(platform_name=self.platform.platform_name,
                                          influencer=self.platform.influencer,
                                          validated_handle=validated_handle).exists():
            log.warn('A platform with parsed validated_handle %r already exists for influencer %r',
                     validated_handle, self.platform.influencer)
            self.platform.validated_handle = None
            platformutils.set_url_not_found('existing_validated_handle', self.platform)
            return
        platformutils.record_field_change('correct_validated_handle', 'url_not_found', self.platform.url_not_found, False, platform=self.platform)
        self.platform.url_not_found = False
        self.platform.validated_handle = validated_handle
        self.platform.save()

    @classmethod
    def get_description(cls, url, xb=None):
        """Returns description for the given social_handle / blog_url.
        Returns ``None`` if it can't be found.
        """
        return None

    def get_validated_handle(self):
        """Returns a handle (username/url) validated through API for the platform
        given in __init__
        """
        raise NotImplementedError()

    @classmethod
    def belongs_to_site(cls, url):
        """Returns:
        - None if url does not belong,
        - url of belonging blog in case it belongs (it is either the same url
          as an argument, or corrected to include www. prefix etc.).
        - a tuple (platform_name, url) in a case url belongs but platform_name
          is different than ``self.name``
        """
        return None

    def _update_popularity_timeseries(self):
        # Update PopularityTimeSeries
        if self.platform.influencer and (
                (self.platform.num_followers is not None) or
                (self.platform.num_following is not None) or
                (self.platform.total_numlikes is not None)):
            pts = models.PopularityTimeSeries()
            pts.influencer = self.platform.influencer
            pts.platform = self.platform
            pts.snapshot_date = datetime.datetime.now()
            if self.platform.platform_name == 'Facebook':
                pts.num_followers = self.platform.total_numlikes
            else:
                pts.num_followers = self.platform.num_followers
            pts.num_following = self.platform.num_following
            pts.save()


def retry_when_call_limit(f, retries=1):
    try:
        return f()
    except FetcherCallLimitException as e:
        if retries > 0:
            log.warn('Call limit exception, sleeping %s', e.seconds_to_wait())
            time.sleep(e.seconds_to_wait())
            log.warn('Retrying')
            return retry_when_call_limit(f, retries - 1)
        log.warn('No more retries')
        raise


def create_platform_follower(follower_search_kwargs, follower_create_kwargs,
                                    influencer_search_kwargs, influencer_create_kwargs,
                                    platform_url, platform_name, description):
    def get_platform():
        existing_platforms = models.Platform.objects.filter(url=platform_url, platform_name=platform_name)
        if existing_platforms.exists():
            log.info('Follower\'s platform found in DB: %r', existing_platforms[0])
            return existing_platforms[0]
        log.info('No existing %s platforms found for url %r', platform_name, platform_url)

        inf_q = models.Influencer.objects.filter(**influencer_search_kwargs)
        if inf_q.exists():
            inf = inf_q[0]
            log.info('Found existing influencer: %r', inf)
        else:
            inf, inf_created = models.Influencer.objects.get_or_create(**influencer_create_kwargs)
            if inf_created:
                log.info('Created new influencer: %r', inf)
                inf.source = 'followers'
                inf.date_created = datetime.datetime.now()
                inf.save()
            else:
                log.info('Found existing influencer using influencer_create_kwargs: %r', inf)

        dup_platforms = models.Platform.find_duplicates(inf, platform_url, platform_name)
        if dup_platforms:
            log.info('Detected duplicated platforms: %r', dup_platforms)
            return dup_platforms[0]

        pl = models.Platform()
        pl.influencer = inf
        pl.platform_name = platform_name
        pl.url = platform_url
        pl.description = description
        pl.processing_state = models.Platform.PROCESSING_STATE_NEW_FOLLOWERS_PLATFORM
        pl.save()
        log.info('Created new platform: %r', pl)
        return pl

    def get_follower():
        fol_q = models.Follower.objects.filter(**follower_search_kwargs)
        if fol_q.exists():
            fol = fol_q[0]
            log.info('Found existing follower: %r', fol)
            return fol
        fol, fol_created = models.Follower.objects.get_or_create(**follower_create_kwargs)
        if fol_created:
            log.info('Created new follower: %r', fol)
            return fol
        log.info('Found existing follower using follower_create_kwargs: %r', fol)
        return fol

    pl = get_platform()
    fol = get_follower()
    pl_fol, pl_fol_created = models.PlatformFollower.objects.get_or_create(
        follower=fol,
        platform=pl)
    if pl_fol_created:
        log.info('Created new PlatformFollower instance')
        return pl_fol
    log.info('PlatformFollower instance alread exists')
    return pl_fol


