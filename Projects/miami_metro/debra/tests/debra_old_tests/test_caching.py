from django.core.cache import get_cache

from debra.tasks import *
from debra.models import *
from debra.decorators import *

mc_cache = get_cache('memcached')

class CustomTest(object):

    @cached_property
    def inf_ids(self):
        j = BrandJobPost.objects.get(id=486)
        return list(j.candidates.values_list('mailbox__influencer', flat=True))

    @cached_property
    def infs(self):
        return Influencer.objects.filter(id__in=self.inf_ids)

    def put_to_cache(self):
        update_bloggers_cache_data(influencer_ids=self.inf_ids,
            send_emails=False)

    def test(self):
        for inf in self.infs:
            assert mc_cache.get('pls_{}'.format(inf.id)) is not None

    def run(self):
        self.put_to_cache()
        self.test()