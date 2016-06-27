from django.core.management.base import BaseCommand
from debra.constants import ELASTICSEARCH_URL, ELASTICSEARCH_INDEX
from debra.es_requests import make_es_post_request
from debra.models import Influencer
import requests
import json
from requests.auth import HTTPBasicAuth
from django.db.models import Q
import gc



class Command(BaseCommand):
    """
    Updates suggesters for influencers in index.
    """
    help = 'Updates suggesters for influencers in index'

    @classmethod
    def handle(cls, *args, **options):

        index_name = ELASTICSEARCH_INDEX

        url = ELASTICSEARCH_URL

        # query = es_influencer_query_builder_v2(parameters, page_size, page)

        # TODO: This part is disabled untill we will find out how to deal with deleted data showing in ES suggesters.
        # influencers = Influencer.objects.filter(Q(blacklisted=True) | ~Q(show_on_search=True))
        influencers = Influencer.objects.filter(id__in=[1688648,])
        inf_queryset = queryset_iterator(influencers)

        ctr = 0
        for inf in inf_queryset:
            ctr += 1
            if ctr % 1000 == 0:
                print('%s influencers performed' % ctr)

            query = {
                "doc": {
                    "_suggest_name": "",
                    "_suggest_blogname": "",
                    "_suggest_blogurl": "",
                    "_suggest_location": ""
                }
            }
            endpoint = "/%s/influencer/%s/_update" % (index_name, inf.id)
            rq = make_es_post_request(
                es_url=url + endpoint,
                es_query_string=json.dumps(query)
            )

        print('%s Influencers performed' % ctr)


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