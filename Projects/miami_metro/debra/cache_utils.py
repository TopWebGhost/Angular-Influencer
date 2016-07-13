import traceback
import time
from datetime import datetime, timedelta
from collections import defaultdict

from django.core.cache import get_cache
from django.db.models import Q
from django.conf import settings

from aggregate_if import Count, Max
import redis

from debra import helpers
from debra import models
from debra import serializers
from debra import constants
from debra.decorators import cached_property
from social_discovery.blog_discovery import (queryset_iterator,
    better_queryset_iterator)
from campaigns import helpers as campaign_helpers


mc_cache = get_cache('memcached')
redis_cache = get_cache('redis')

DEFAULT_CACHE = redis_cache

redis_client = redis.Redis(host=settings.REDIS_URL.hostname,
    port=settings.REDIS_URL.port, password=settings.REDIS_URL.password)


class BaseCacheUpdaterTask(object):

    def run(self, data):
        raise NotImplementedError


class BaseCacheUpdater(object):

    def __init__(self, *args, **kwargs):
        self._tasks = []

    def run(self):
        raise NotImplementedError


class CacheUpdaterTask(object):

    def __init__(self, name=None, prefetch=None, many=True, cache=None,
            timeout=0, notificator=None, cache_key_generator=None,
            data_generator=None, cache_key_prefix=None, updater=None):
        self.name = name or self.__class__.__name__
        self._prefetch = prefetch
        self._many = many
        self._cache = cache if cache else DEFAULT_CACHE
        self._timeout = timeout
        self._notificator = notificator
        self._data_generator = data_generator
        self._cache_key_generator = cache_key_generator
        self._cache_key_prefix = cache_key_prefix
        self._updater = updater

    def _prepare_data(self, items):
        if self._data_generator:
            return self._data_generator(items)
        else:
            raise NotImplementedError

    def _generate_cache_key(self, item):
        if self._cache_key_generator:
            return self._cache_key_generator(item)
        else:
            raise NotImplementedError

    def run(self, data):
        self._put_to_cache(self._prepare_data(data))

    def _do_put_to_cache(self, method, *args):
        try:
            t0 = time.time()
            method(*args, timeout=self._timeout)
            # print '*** cache.set operation took', timedelta(
            #     seconds=time.time() - t0)
        except:
            self._notificator.notificate(
                "storing to cache failed for '{}'".format(self.name),
                '<br />'.join(traceback.format_exc().splitlines()),
            )

    def _put_to_cache(self, data):
        _t0 = time.time()
        if self._many:
            self._do_put_to_cache(self._cache.set_many, data)
        else:
            for k, v in data.items():
                self._do_put_to_cache(self._cache.set, k, v)
        print '* _put_to_cache took {}'.format(time.time() - _t0)


class CacheUpdater(object):
    
    def __init__(self, item_ids=None, chunksize=1000, mute_notifications=False,
            enabled_tasks=None, _set_iterable=True, cache=None):
        self._cache = cache if cache else DEFAULT_CACHE
        self._set_notificator(mute=mute_notifications)
        self.set_db_chunksize(chunksize)
        self.set_cache_chunksize(chunksize)
        self.set_tasks(enabled_tasks=enabled_tasks)
        if _set_iterable:
            self._set_iterable_data(item_ids=item_ids)

    def _set_notificator(self, notificator=None, mute=False):
        if not notificator:
            notificator = helpers.EmailAdminNotificator(
                'bloggers-cache-updater', mute=mute)
        self._notificator = notificator

    def _set_iterable_data(self, *args, **kwargs):
        self._do_set_iterable_data(*args, **kwargs)
        self._items_total = self._iterable_data.count()
        self._chunks_total = self._items_total / self._chunksize + int(
            self._items_total % self._chunksize != 0)

    def _do_set_iterable_data(self, *args):
        raise NotImplementedError

    def _create_iterator(self, prefetch=None):
        return enumerate(
            better_queryset_iterator(self._iterable_data, prefetch=prefetch,
                many=True, chunksize=self._chunksize), start=1)

    @property
    def _default_tasks(self):
        return []

    def set_tasks(self, tasks=None, enabled_tasks=None):
        self._tasks = tasks or self._default_tasks
        if enabled_tasks:
            self._tasks = [t for t in self._tasks if t.name in enabled_tasks]

    def set_db_chunksize(self, chunksize):
        self._chunksize = chunksize

    def set_cache_chunksize(self, chunksize):
        self._cache_chunksize = chunksize

    def _run_task(self, task):
        self._notificator.notificate(
            "started at {}".format(datetime.now()),
            "got {} items".format(self._items_total)
        )
        iterator = self._create_iterator(prefetch=task._prefetch)

        t0 = time.time()
        try:
            _t0 = time.time()
            for n, data in iterator:
                print '* [{}] {}/{} items processing'.format(
                        task.name, n, self._chunks_total)
                task.run(data)
                print '\t * [{}] iteration took {}'.format(
                        task.name, timedelta(seconds=time.time() - _t0))
                _t0 = time.time()
        except:
            self._notificator.notificate('crashed',
                '<br />'.join(traceback.format_exc().splitlines()))
        t1 = timedelta(seconds=time.time() - t0)
        print '* done, took {}'.format(t1)
        self._notificator.notificate("finished at {}".format(
            datetime.now()), "Took {}".format(t1))

    @cached_property
    def _iterable_data_ids(self):
        return list(self._iterable_data.values_list('id', flat=True))

    def run(self):
        for task in self._tasks:
            self._run_task(task)

    def _create_checker(self, task):
        return CacheChecker(self._iterable_data_ids, task=task)

    def check(self, task, fix=False, celery=False):
        checker = self._create_checker(task)
        checker.run()
        if fix:
            checker.fix(celery=celery)


class ModelCacheUpdater(CacheUpdater):

    model = None
    queryset = None
    tasks = []

    def get_model(self):
        return self.model

    def get_queryset(self):
        return self.queryset or self.model.objects.all()

    @property
    def _default_tasks(self):
        return [
            CacheUpdaterTask(name, notificator=self._notificator,
                updater=self, cache_key_generator=key_func,
                data_generator=lambda items: {
                    key_func(item): val_func(item)
                    for item in items
                })
        for name, (key_func, val_func) in self.tasks]

    def _do_set_iterable_data(self, item_ids=None):
        self._iterable_data = self.get_queryset()
        if item_ids:
            self._iterable_data = self._iterable_data.\
                filter(id__in=item_ids)


class BloggersCacheUpdater(CacheUpdater):

    @cached_property
    def _default_tasks(self):
        return [
            # CacheUpdaterTask('platforms', prefetch=['platform_set'],
            #     notificator=self._notificator, updater=self,
            #     cache_key_generator=lambda x: 'pls_{}'.format(x),
            #     data_generator=lambda items: {
            #         'pls_{}'.format(i.id): serializers.InfluencerSerializer\
            #             .platforms_to_cache(i) for i in items},
            # ),
            CacheUpdaterTask('platformTuples', prefetch=['platform_set'],
                notificator=self._notificator, updater=self,
                cache_key_generator=lambda x: 'plst_{}'.format(x),
                data_generator=lambda items: {
                    'plst_{}'.format(i.id): tuple(
                        tuple(serializers.PlatformSerializer(pl).data.values())
                        for pl in i.valid_platforms
                    ) for i in items
                }),
            CacheUpdaterTask('platformDicts', prefetch=['platform_set'],
                notificator=self._notificator, updater=self,
                cache_key_generator=lambda x: 'plst_{}'.format(x),
                data_generator=lambda items: {
                    'plsd_{}'.format(i.id): tuple(
                        serializers.PlatformSerializer(pl).data
                        for pl in i.valid_platforms
                    ) for i in items
                }),
            CacheUpdaterTask('profilePics',
                prefetch=['shelf_user__userprofile'], many=True,
                notificator=self._notificator, updater=self,
                cache_key_generator=lambda x: 'pp_{}'.format(x),
                data_generator=lambda items: {
                    'pp_{}'.format(i.id): i.profile_pic.encode('utf-8')
                    if i.profile_pic else '' for i in items},
            ),
        ]

    def _do_set_iterable_data(self, item_ids=None):
        if item_ids:
            self._iterable_data = models.Influencer.objects.filter(
                id__in=item_ids)
        else:
            self._iterable_data = models.Influencer.objects.cachable()


class TagNamesCacheUpdater(CacheUpdater):
    # @TODO: rename this updater class

    @property
    def _default_tasks(self):
        return [
            CacheUpdaterTask('tagNames', notificator=self._notificator,
                cache_key_generator=lambda x: 'ig_{}'.format(x),
                updater=self,
                data_generator=lambda items: {
                    'ig_{}'.format(tag.id): tag.name for tag in items}
            ),
            # CacheUpdaterTask('tagInfluencers', notificator=self._notificator,
            #     cache_key_generator=lambda x: 'ig_{}_infs'.format(x),
            #     updater=self,
            #     data_generator=lambda items: {
            #         'ig_{}_infs'.format(tag.id): tag
            #     }
            # ),
        ]

    def _do_set_iterable_data(self, item_ids=None):
        self._iterable_data = models.InfluencersGroup.objects.all()
        if item_ids:
            self._iterable_data = self._iterable_data.filter(
                system_collection=False, id__in=item_ids)
        else:
            self._iterable_data = self._iterable_data.filter(
                system_collection=False)
        self._iterable_data = self._iterable_data.only('id', 'name')


class MailProxyCacheUpdater(CacheUpdater):

    @property
    def _default_tasks(self):

        def _subjects_data_generator(mps):
            _t0 = time.time()
            first_messages = dict(models.MailProxyMessage.objects.filter(
                type=1,
                thread_id__in=[mp.id for mp in mps]
            ).order_by(
                'thread', 'ts'
            ).distinct('thread').values_list('thread', 'msg'))
            for mp in mps:
                mp._subject = None
                mp._first_message = first_messages.get(mp.id)
            print '* data generator took {}'.format(time.time() - _t0)
            data = {
                'sb_{}'.format(mp.id): serializers.MailProxySubjectSerializer\
                    .cache_serializer().pack([mp]) for mp in mps
            }
            return data

        return [
            CacheUpdaterTask('threadSubjects',
                notificator=self._notificator, updater=self,
                cache_key_generator=lambda x: 'sb_{}'.format(x),
                data_generator=_subjects_data_generator)
        ]

    def _do_set_iterable_data(self, item_ids=None):
        self._iterable_data = models.MailProxy.objects.all()
        if item_ids:
            self._iterable_data = self._iterable_data.filter(id__in=item_ids)


class MailProxyCountsCacheUpdater(CacheUpdater):

    @property
    def _default_tasks(self):
        return [
            CacheUpdaterTask('messageCounts',
                notificator=self._notificator, updater=self,
                cache_key_generator=lambda x: 'mpc_{}'.format(x),
                data_generator=lambda mps: {
                    'mpc_{}'.format(mp['id']): serializers\
                        .MailProxyCountsSerializer.cache_serializer()\
                        .pack([mp])
                    for mp in mps
                })
        ]

    def _do_set_iterable_data(self, item_ids=None):
        self._iterable_data = models.MailProxy.objects.all()
        if item_ids:
            self._iterable_data = self._iterable_data.filter(id__in=item_ids)
        self._iterable_data = self._iterable_data.mailbox_counts()


class PlatformStatsCacheUpdater(CacheUpdater):

    @property
    def _default_tasks(self):
        return [
            CacheUpdaterTask('platformEngagementToFollowersRatio', notificator=self._notificator,
                updater=self, cache_key_generator=lambda x: 'pef_{}'.format(x),
                data_generator=lambda pls: {
                    'pef_{}'.format(pl_name): models.Platform.calculate_engagement_to_followers_ratio_overall(pl_name)
                    for pl_name in models.Platform.SOCIAL_PLATFORMS + ['Blog']
                })
        ]

    def _do_set_iterable_data(self, item_ids=None):
        self._iterable_data = models.Platform.objects.filter(
            id=models.Platform.objects.all()[0].id)


class CampaignCacheUpdater(BaseCacheUpdater):

    def run(self):
        # @todo: remove that filter
        campaigns = models.BrandJobPost.objects.all().filter(id__in=[705, 355])
        total = campaigns.count()
        for n, campaign in enumerate(queryset_iterator(campaigns), start=1):
            wrapper = campaign_helpers.CampaignReportDataWrapper(campaign)
            wrapper.save_to_cache()
            print '* {}/{}'.format(n, total)


class PostAnalyticsCollectionUpdater(CacheUpdater):

    @property
    def _default_tasks(self):
        return [
            CacheUpdaterTask('uniquePostAnalayticsIds', notificator=self._notificator,
                updater=self, cache_key_generator=lambda x: 'unq_pas_{}'.format(x),
                data_generator=lambda pcs: {
                    'unq_pas_{}'.format(pc.id): pc._get_unique_post_analytics_ids()
                    for pc in pcs
                })
        ]

    def _do_set_iterable_data(self, item_ids=None):
        pac_ids = list(models.BrandJobPost.objects.exclude(
            post_collection__isnull=True
        ).values_list('post_collection', flat=True))
        self._iterable_data = models.PostAnalyticsCollection.objects.filter(
            id__in=pac_ids)


class InfluencerTagsCacheUpdater(BaseCacheUpdater):

    def run(self):
        pairs = list(models.InfluencerGroupMapping.objects.values_list(
            'influencer', 'group',
        ).exclude(
            influencer__isnull=True
        ).exclude(
            group__isnull=True
        ).distinct(
            'influencer', 'group',
        ))
        inf_2_tags = defaultdict(list)
        for inf_id, tag_id in pairs:
            inf_2_tags[inf_id].append(tag_id)

        total = len(inf_2_tags)
        for n, (inf_id, tag_ids) in enumerate(inf_2_tags.items(), start=1):
            redis_client.sadd('itags_{}'.format(inf_id), *tag_ids)
            print '* {}/{}'.format(n, total)


class BrandTagsCacheUpdater(BaseCacheUpdater):

    def run(self):
        pairs = list(models.InfluencerGroupMapping.objects.values_list(
            'group__creator_brand', 'group',
        ).distinct(
            'group__creator_brand', 'group',
        ))
        brand_2_tags = defaultdict(list)
        for brand_id, tag_id in pairs:
            brand_2_tags[brand_id].append(tag_id)

        total = len(brand_2_tags)
        for n, (brand_id, tag_ids) in enumerate(brand_2_tags.items(), start=1):
            redis_client.sadd('btags_{}'.format(brand_id), *tag_ids)
            print '* {}/{}'.format(n, total)


class SystemCollectionsCacheUpdater(BaseCacheUpdater):

    def run(self):
        tag_ids = models.InfluencersGroup.objects.filter(
            system_collection=True
        ).values_list('id', flat=True)
        total = len(tag_ids)
        print '* adding {} tags'.format(total)
        redis_client.sadd('systags', *tag_ids)


class LocationsCacheUpdater(BaseCacheUpdater):

    def run(self):
        locations_list = models.Influencer.get_locations_list(
            num_results=None, overwrite=True, use_full_names=False)
        redis_cache.set('locs', locations_list, timeout=0)


class LongLocationsCacheUpdater(BaseCacheUpdater):

    def run(self):
        locations_list = models.Influencer.get_locations_list(
            num_results=None, overwrite=True)
        redis_cache.set('longlocs', locations_list, timeout=0)


class TopLocationsCacheUpdater(BaseCacheUpdater):

    def run(self):
        locations_list = models.Influencer.get_locations_list(
            num_results=200, overwrite=True)
        redis_cache.set('toplocs', locations_list, timeout=0)


class TagInfluencersCacheUpdater(BaseCacheUpdater):

    def run(self):
        pairs = list(models.InfluencerGroupMapping.objects.values_list(
            'influencer', 'group',
        ).distinct(
            'influencer', 'group',
        ))

        tag_2_infs = defaultdict(list)

        for inf_id, tag_id in pairs:
            tag_2_infs[tag_id].append(inf_id)

        total = len(tag_2_infs)
        for n, (tag_id, inf_ids) in enumerate(tag_2_infs.items(), start=1):
            redis_client.sadd('tinfs_{}'.format(tag_id), *inf_ids)

            try:
                pic_url = [pp for pp in redis_cache.get_many([
                    'pp_{}'.format(inf_id)
                    for inf_id in inf_ids
                ]).values() if pp and pp != constants.DEFAULT_PROFILE_PIC][0]
            except IndexError:
                redis_client.hdel('tpics', tag_id)
            else:
                redis_client.hset('tpics', tag_id, pic_url)

            print '* {}/{}'.format(n, total)


class CacheChecker(object):

    def __init__(self, item_ids, task=None, cache_key=None, updater=None):
        self._all_ids = item_ids
        self._total = len(self._all_ids)
        self._missing_ids = []
        self._task = task
        self._cache_key = task._cache_key_generator if task else cache_key
        self._updater = task._updater.__class__ if task else updater

    def run(self, chunksize=1000):
        t0 = time.time()
        for n, inf_ids in enumerate(helpers.chunks(self._all_ids, chunksize),
                start=1):
            print '* {}/{} processed'.format(
                (n - 1) * len(inf_ids), self._total)
            _t0 = time.time()
            _missing_cnt = 0
            data = DEFAULT_CACHE.get_many([
                self._cache_key(inf_id) for inf_id in inf_ids])
            for inf_id in inf_ids:
                if self._cache_key(inf_id) not in data or\
                        data[self._cache_key(inf_id)] is None:
                    self._missing_ids.append(inf_id)
                    _missing_cnt += 1
            print '** Took {}, {} new missing ids'.format(
                timedelta(seconds=time.time() - _t0), _missing_cnt)
        print 'Check took {}'.format(timedelta(seconds=time.time() - t0))
        print '{} new missing items found'.format(len(self._missing_ids))

    def fix(self, enabled_tasks=None, celery=True):
        params = dict(item_ids=self._missing_ids, mute_notifications=True,
            enabled_tasks=[self._task.name] if self._task else enabled_tasks)
        if celery:
            from debra.tasks import update_bloggers_cache_data
            update_bloggers_cache_data.apply_async(kwargs=params,
                queue='update_bloggers_cache_data')
        else:
            self._updater(**params).run()
