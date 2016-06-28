import inspect

from django.core.cache import get_cache

from debra.tasks import *
from debra.models import *
from debra.decorators import *
from debra.serializers import InfluencerSerializer

mc_cache = get_cache('memcached')

class CustomTest(object):

    def __init__(self, use_celery=False):
        self.use_celery = use_celery

    @cached_property
    def inf_ids(self):
        j = BrandJobPost.objects.get(id=486)
        return list(j.candidates.values_list('mailbox__influencer', flat=True))

    @cached_property
    def infs(self):
        return Influencer.objects.filter(id__in=self.inf_ids)

    def put_to_cache(self):
        if self.use_celery:
            update_bloggers_cache_data.apply_async(kwargs=dict(
                influencer_ids=self.inf_ids, mute_notifications=True),
            queue='update_bloggers_cache_data')
        else:
            update_bloggers_cache_data(influencer_ids=self.inf_ids,
                mute_notifications=True)

    def test_platforms_exists(self):
        for inf in self.infs:
            cache_data = mc_cache.get('pls_{}'.format(inf.id))
            assert cache_data is not None

    def test_platforms_valid(self):
        infs = self.infs.prefetch_related('platform_set')
        for inf in infs:
            valid_data = InfluencerSerializer.platforms_to_cache(inf)
            cache_data = mc_cache.get('pls_{}'.format(inf.id))
            assert valid_data == cache_data

    def test_time_series_exists(self):
        for inf in self.infs:
            cache_data = mc_cache.get('ts_{}'.format(inf.id))
            assert cache_data is not None

    def test_time_series_valid(self):
        infs = self.infs.prefetch_related('popularitytimeseries_set')
        for inf in infs:
            valid_data = InfluencerSerializer.time_series_to_cache(inf)
            cache_data = mc_cache.get('ts_{}'.format(inf.id))
            assert valid_data == cache_data

    def test(self):
        for name, met in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith('test_'):
                met()

    def run(self):
        self.put_to_cache()
        self.test()