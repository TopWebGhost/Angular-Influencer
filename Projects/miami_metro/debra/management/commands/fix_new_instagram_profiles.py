from django.core.management.base import BaseCommand
import json
from debra.models import Influencer
import requests
from platformdatafetcher.fetcherbase import FetcherException

from platformdatafetcher.socialfetcher import InstagramScrapingFetcher
from platformdatafetcher.pbfetcher import policy_for_platform


import gc


class Command(BaseCommand):

    help = 'Fixes Instagram profile pictures and urls inside'

    @classmethod
    def handle(cls, *args, **options):

        # fetching our new Influencers
        influencers = Influencer.objects.filter(
            blog_url__icontains='theshelf.com/artificial',
            show_on_search=True,
            # blogname='Unusual Traffic Detected'
        )

        inf_queryset = queryset_iterator(influencers)

        ctr = 0
        exc_plat_ids = []
        print('Started performing added Influencers (total: %s)...' % influencers.count())
        for inf in inf_queryset:

            # Checking out if image url is valid and reachable, if not - setting them to None

            platforms = inf.platform_set.filter(platform_name='Instagram').exclude(url_not_found=True)
            for platform in platforms:

                platform.profile_img_url = None
                platform.save()
                try:
                    InstagramScrapingFetcher(platform, policy_for_platform(platform))
                except:
                    exc_plat_ids.append(platform.id)

            inf.set_profile_pic()

            # bad blog name
            if inf.blogname == 'Unusual Traffic Detected':
                inf.blogname = None
                inf.save()

            # Increasing counter
            ctr += 1
            if ctr % 100 == 0:
                print('%s influencers performed' % ctr)

        print('Total: %s' % ctr)
        if len(exc_plat_ids) > 0:
            print('Dumping platform Ids with exceptions:')
            f = open('fix_new_instagram_profiles_exception.txt', 'w')
            json.dump(exc_plat_ids, f)
            f.close()



# https://djangosnippets.org/snippets/1949/
def queryset_iterator(queryset, chunksize=1000):
    """
    Iterate over a Django Queryset ordered by the primary key

    This method loads a maximum of chunksize (default: 1000) rows in it's
    memory at the same time while django normally would load all rows in it's
    memory. Using the iterator() method only causes it to not preload all the
    classes.

    Note that the implementation of the iterator does not support ordered query sets.
    """
    pk = 0
    try:
        last_pk = queryset.order_by('-pk')[0].pk
        queryset = queryset.order_by('pk')
        while pk < last_pk:
            for row in queryset.filter(pk__gt=pk)[:chunksize]:
                pk = row.pk
                yield row
            gc.collect()
    except IndexError:
        gc.collect()