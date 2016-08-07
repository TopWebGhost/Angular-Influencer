import json
import datetime
import time
import urllib
import logging
import sys
import itertools

from collections import defaultdict, Counter
import itertools

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.core.mail import mail_admins
from django.template.loader import render_to_string
from django.http import (HttpResponseForbidden, HttpResponse,\
    HttpResponseBadRequest)
from django.db.models import Q, Count, F
from django.core.serializers.json import DjangoJSONEncoder
from django.core.cache import cache, get_cache
from django.http import Http404
from debra.es_requests import make_es_get_request

from debra.models import (
    Influencer, BrandMentions, Brands, User,
    InfluencerJobMapping, SearchQueryArchive, PostAnalyticsCollection,
    PostAnalytics, ROIPredictionReport, InfluencerAnalytics,
    InfluencerAnalyticsCollection, InfluencerBrandUserMapping,
    InfluencersGroup, Platform,)
from debra.constants import (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX, NUM_OF_IMAGES_PER_BOX)
from debra.constants import STRIPE_COLLECTION_PLANS, STRIPE_EMAIL_PLANS
from debra.decorators import (
    user_is_brand_user, public_influencer_view, user_is_brand_user_json,
    login_required_json)
from debra.serializers import unescape
from debra import constants
from debra import feeds_helpers
from debra import search_helpers
from debra import mongo_utils
from debra import account_helpers
from debra.helpers import get_or_set_cache
from xpathscraper import utils


log = logging.getLogger('debra.search_views')
mc_cache = get_cache('memcached')
redis_cache = get_cache('redis')


@login_required_json
@user_is_brand_user_json
def blogger_search_json_v3(request):

    def postprocessing(search_result, brand, search_query):
        _t0 = time.time()

        # brand_tag_ids = list(base_brand.influencer_groups.exclude(
        #     archived=True
        # ).filter(creator_brand=brand, system_collection=False).values_list(
        #     'id', flat=True))

        pipe = settings.REDIS_CLIENT.pipeline()
        pipe.sdiff('btags_{}'.format(brand.id), 'systags')
        for res in search_result["results"]:
            pipe.sdiff('itags_{}'.format(res['id']), 'systags')
        pipe_data = pipe.execute()

        brand_tag_ids, inf_tag_ids = map(int, pipe_data[0]), {
            int(res['id']): map(int, [t for t in tag_ids if t and t != 'None'])
            for res, tag_ids in zip(search_result['results'], pipe_data[1:])
            if res['id']
        }

        all_tag_ids = set([
            tag_id for tag_id in itertools.chain(*inf_tag_ids.values())
            if tag_id in brand_tag_ids
        ])

        tag_names = {
            int(key[3:]): val
            for key, val in  redis_cache.get_many([
                'ig_{}'.format(tag_id) for tag_id in all_tag_ids
            ]).items()
        }

        for res in search_result['results']:
            res['collections_in'] = {
                tag_id: tag_names.get(tag_id)
                for tag_id in inf_tag_ids.get(int(res['id']), [])
                if tag_names.get(tag_id)
            }

        print '* Filtering tag ids took {}'.format(
            datetime.timedelta(seconds=time.time() - _t0))

        if brand and brand.flag_bloggers_custom_data_enabled and search_query.get('search_method') == 'r29':
            from debra.models import (InfluencerBrandMapping,
                SiteConfiguration)
            from debra.constants import SITE_CONFIGURATION_ID
            from debra.serializers import InfluencerBrandMappingSerializer

            brand_mappings = {
                m.influencer_id: m
                for m in InfluencerBrandMapping.objects.filter(
                    influencer_id__in=[x['id'] for x in search_result['results']],
                    brand_id=brand.id
                ).prefetch_related('influencer__demographics_locality')
            }

            metadata = SiteConfiguration.objects.get(
                id=SITE_CONFIGURATION_ID).blogger_custom_data_json

            for res in search_result['results']:
                mp = brand_mappings.get(int(res['id']))
                from djangorestframework_camel_case.util import camelize
                res['brand_custom_data'] = camelize(InfluencerBrandMappingSerializer(
                    mp, context={'metadata': metadata}).data) if mp else None

        search_result["query_limited"] = query_limiter

        if query_limiter:
            if brand.num_querys_remaining:
                brand.num_querys_remaining -= 1
                brand.save()
                request.session.modified = True
            search_result["remaining"] = brand.num_querys_remaining
            search_result["remaining_debug"] = settings.DEBUG

    only_setup_params = {}
    t0 = time.time()
    t1 = time.time()
    print
    print "BSJ start",
    mongo_utils.track_visit(request)

    try:
        search_query = json.loads(request.body)
    except ValueError:
        search_query = {}

    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]

    q_from_request = search_helpers.query_from_request(request)

    # flag for caching separately ES page of initial data for trial and complete pages
    trial_str = 'full' if bool(brand.flag_show_dummy_data if brand else False) else 'trial'

    # first prettify the query for mandrill, intercom, and slack
    try:
        only_setup_params = search_helpers.find_non_default_query(search_query)
        if only_setup_params is None or only_setup_params == [{}]:
            only_setup_params = {}
        query_formatted = search_helpers.format_query_for_displaying(only_setup_params)
        print "only_setup_params = [%r]  query_formatted = [%r]" % (only_setup_params, query_formatted)
        if len(only_setup_params) == 0:
            cached_empty_query = cache.get('only_setup_params_influencer_%s' % trial_str)
            if cached_empty_query:
                print('Returning cached data about initial page of influencers. No ES query was made.')
                postprocessing(cached_empty_query, brand, q_from_request)
                if request.is_ajax():
                    data_json = json.dumps(cached_empty_query, cls=DjangoJSONEncoder)
                    return HttpResponse(data_json, content_type="application/json")
                else:
                    data_json = json.dumps(cached_empty_query, cls=DjangoJSONEncoder, indent=4)
                    return HttpResponse("<body><pre>{}</pre></body>".format(data_json))
    except:
        a = json.dumps(search_query, sort_keys=True, indent=4, separators=(',', ': '))
        query_formatted = 'Problem in formatting %r' % a
        pass

    account_helpers.intercom_track_event(request, "brand-search-query", {
        'query': query_formatted,
    })

    mongo_utils.track_query(
        "brand-search-query",
        query_formatted, {"user_id": request.visitor["auth_user"].id})

    print time.time() - t1
    print "Verification",
    t1 = time.time()


    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()

    # disable_query_limit = request.user.is_superuser or request.user.is_staff
    disable_query_limit = True
    if not disable_query_limit:
        query_limiter = True
    else:
        query_limiter = False

    print time.time() - t1
    print "Favs",
    t1 = time.time()

    if base_brand:
        user = User.objects.get(id=request.user.id)
        if base_brand.flag_trial_on and not account_helpers.internal_user(user):
            slack_msg = "\n**************\nBrand = " + base_brand.domain_name + " User: " + request.user.email + "\n" + query_formatted
            account_helpers.send_msg_to_slack.apply_async(['brands-trial-activity', slack_msg],
                                                          queue='celery')

        if base_brand.is_subscribed:
            query_limiter = False

        base_brand.saved_queries.create(query=json.dumps(search_query),
            user=request.user)

        # Primitive Rate-Limiting
        if not settings.DEBUG and not account_helpers.internal_user(user) and (
            # TODO: contains on dates? possibly a bug
            base_brand.saved_queries.filter(timestamp__contains=datetime.date.today()).count() > 2000 or
            base_brand.blacklisted is True
        ):
            return HttpResponseForbidden("limit", content_type="application/json")

    print time.time() - t1
    print "Query limiter",
    t1 = time.time()

    if query_limiter and brand.num_querys_remaining == 0:
        data = {}
        data["remaining"] = brand.num_querys_remaining
        data["remaining_debug"] = settings.DEBUG
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")

    if query_limiter:
        items_per_page = 20
    else:
        items_per_page = 30

    search_query = q_from_request

    if search_query.get('sub_tab') == 'instagram_search':
        search_query['filters']['post_platform'] = ['Instagram']
    elif search_query.get('sub_tab') == 'main_search':
        search_query['no_artificial_blogs'] = True

    if search_query.get('search_method') == 'r29':
        search_query['filters']['tags'].append(constants.R29_CUSTOM_DATA_TAG_ID)
    else:
        search_query['filters']['exclude_tags'] = [constants.R29_CUSTOM_DATA_TAG_ID]

    if True:
        # this uses the newer version of our code to use Elastic Search in a more structured way
        # this is the only front-end facing view that uses the new code
        # all other methods use the old search logic
        # our goal is to use the old search logic everywhere first to make sure we're consistent first
        # and then we want to re-factor everything.

        search_result = search_helpers.search_influencers_v3(
            search_query, items_per_page, request=request)

        post_time = time.time()

        if only_setup_params == {}:
            search_result['total_influencers'] = search_result['total_influencers'] + 40000
            cache.set('only_setup_params_influencer_%s' % trial_str, search_result)

        # we can use ES for this

        # search_helpers.set_influencer_collections(
        #     search_result["results"], brand_id=brand.id)

        # search_helpers.set_mailed_to_influencer(
        #     search_result["results"], brand_id=brand.id)

        # search_helpers.set_influencer_invited_to(
        #     search_result["results"], brand_id=brand.id)


        # _t0 = time.time()

        # # brand_tag_ids = list(base_brand.influencer_groups.exclude(
        # #     archived=True
        # # ).filter(creator_brand=brand, system_collection=False).values_list(
        # #     'id', flat=True))

        # pipe = settings.REDIS_CLIENT.pipeline()
        # pipe.sdiff('btags_{}'.format(brand.id), 'systags')
        # for res in search_result["results"]:
        #     pipe.sdiff('itags_{}'.format(res['id']), 'systags')
        # pipe_data = pipe.execute()

        # brand_tag_ids, inf_tag_ids = map(int, pipe_data[0]), {
        #     int(res['id']): map(int, tag_ids)
        #     for res, tag_ids in zip(search_result['results'], pipe_data[1:])
        # }

        # all_tag_ids = set([
        #     tag_id for tag_id in itertools.chain(*inf_tag_ids.values())
        #     if tag_id in brand_tag_ids
        # ])

        # tag_names = {
        #     int(key[3:]): val
        #     for key, val in  redis_cache.get_many([
        #         'ig_{}'.format(tag_id) for tag_id in all_tag_ids
        #     ]).items()
        # }

        # for res in search_result['results']:
        #     res['collections_in'] = {
        #         tag_id: tag_names.get(tag_id)
        #         for tag_id in inf_tag_ids.get(int(res['id']), [])
        #         if tag_names.get(tag_id)
        #     }

        # for res in search_result["results"]:
        #     res['collections_in'] = {
        #         tag_id: name
        #         for tag_id, name in res.get('collections_in', {}).items()
        #         if tag_id in brand_tag_ids
        #     }

        # print '* Filtering tag ids took {}'.format(
        #     datetime.timedelta(seconds=time.time() - _t0))

        # search_helpers.set_influencer_analytics_collections(
        #     search_result["results"], brand_id=brand.id)

        # search_helpers.set_brand_notes(
        #     search_result["results"], user_id=request.user.id)

        print 'Post-processing time', time.time() - post_time

        mongo_utils.influencers_appeared_on_search(
            [x["id"] for x in search_result["results"]])

        # search_result["query_limited"] = query_limiter

        # if brand and brand.flag_bloggers_custom_data_enabled and search_query.get('search_method') == 'r29':
        #     from debra.models import (InfluencerBrandMapping,
        #         SiteConfiguration)
        #     from debra.constants import SITE_CONFIGURATION_ID
        #     from debra.serializers import InfluencerBrandMappingSerializer

        #     brand_mappings = {
        #         m.influencer_id: m
        #         for m in InfluencerBrandMapping.objects.filter(
        #             influencer_id__in=[x['id'] for x in search_result['results']],
        #             brand_id=brand.id
        #         ).prefetch_related('influencer__demographics_locality')
        #     }

        #     metadata = SiteConfiguration.objects.get(
        #         id=SITE_CONFIGURATION_ID).blogger_custom_data_json

        #     for res in search_result['results']:
        #         mp = brand_mappings.get(int(res['id']))
        #         from djangorestframework_camel_case.util import camelize
        #         res['brand_custom_data'] = camelize(InfluencerBrandMappingSerializer(
        #             mp, context={'metadata': metadata}).data) if mp else None
    else:
        # remove this later on
        search_result = search_helpers.search_influencers_old(search_query, 60)
        print "SEARCH_RESULT: %s" % search_result

    print [x["id"] for x in search_result["results"]]

    # if query_limiter:
    #     if brand.num_querys_remaining:
    #         brand.num_querys_remaining -= 1
    #         brand.save()
    #         request.session.modified = True
    #     search_result["remaining"] = brand.num_querys_remaining
    #     search_result["remaining_debug"] = settings.DEBUG
    postprocessing(search_result, brand, search_query)

    print time.time() - t1
    print "BSJ end, total in: ", time.time() - t0
    print

    # @todo: it's from some other branch, so not used for now
    # search_result['engagement_to_followers_ratio_overall'] = Platform.engagement_to_followers_ratio_overall(
    #     'All')

    # if only_setup_params == {}:
    #     search_result['total_influencers'] = search_result['total_influencers'] + 40000
    #     cache.set('only_setup_params_influencer_%s' % trial_str, search_result)
    print 'TOTAL', search_result['total_influencers']

    if request.is_ajax():
        data_json = json.dumps(search_result, cls=DjangoJSONEncoder)
        #print "DATA_JSON: %s" % data_json
        return HttpResponse(data_json, content_type="application/json")
    else:
        data_json = json.dumps(search_result, cls=DjangoJSONEncoder, indent=4)
        return HttpResponse("<body><pre>{}</pre></body>".format(data_json))


@login_required
@user_is_brand_user
def blogger_search(request):
    """
    returns rendered bloggers search page
    """
    return redirect(reverse('debra.search_views.main_search'))


@login_required
@user_is_brand_user
def main_search(request):
    mongo_utils.track_visit(request)
    brand = request.visitor["base_brand"]
    if brand and brand.is_subscribed:
        plan_name = brand.stripe_plan
    else:
        return redirect('/')

    # saved_queries_list = search_helpers.get_brand_saved_queries_list(brand)

    # groups_list = search_helpers.get_brand_groups_list(
    #     request.visitor["brand"], request.visitor["base_brand"])

    # tags_list = search_helpers.get_brand_tags_list(
    #     request.visitor["brand"], request.visitor["base_brand"])

    context = {
        'search_page': True,
        'type': 'all',
        'selected_tab': 'search',
        'sub_page': 'main_search',
        'shelf_user': request.visitor["user"],
        'debug': settings.DEBUG,
        # 'show_select': show_select,
        # 'groups_list': json.dumps(groups_list),
        # 'saved_queries_list': json.dumps(saved_queries_list),
        'tag_id': request.GET.get('tag_id'),
        'saved_search': request.GET.get('saved_search'),
    }

    context.update(
        search_helpers.prepare_filter_params(context, plan_name=plan_name))

    return render(request, 'pages/search/main.html', context)


@login_required
@user_is_brand_user
def posts_search_json(request):
    mongo_utils.track_visit(request)
    base_brand = request.visitor["base_brand"]
    if base_brand:
        user = User.objects.get(id=request.user.id)
        if not settings.DEBUG and not account_helpers.internal_user(user) and (
            # TODO: contains on dates? possibly a bug
            base_brand.saved_queries.filter(timestamp__contains=datetime.date.today()).count() > 2000 or
            base_brand.blacklisted is True
        ):
            return HttpResponseForbidden("limit", content_type="application/json")

    try:
        search_query = json.loads(urllib.unquote(request.body))
    except:
        search_query = {}

    content_filter = search_query.get('filter')
    if content_filter == 'tweets':
        data = feeds_helpers.twitter_feed_json(request)
    elif content_filter == 'pins':
        data = feeds_helpers.pinterest_feed_json(request)
    elif content_filter == 'photos':
        data = feeds_helpers.instagram_feed_json(request)
    else:
        data = feeds_helpers.blog_feed_json_dashboard(request)

    if request.is_ajax():
        #data["results"].sort(key=lambda x: x.get("create_date", x["id"]))
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        return HttpResponse("<body></body>" % data)


@login_required
@user_is_brand_user
def posts_search(request):
    """
    obsolete
    """
    mongo_utils.track_visit(request)
    context = {
        'search_page': True,
        'selected_tab': 'search_posts',
        'shelf_user': request.user.userprofile,
        'debug': settings.DEBUG,
    }
    return render(request, 'pages/search/posts.html', context)


# NON RENDERING METHODS


def blogger_posts_json(request, influencer_id):
    """
    This view renders ajax request with the influencer's posts for influencer's PROFILE.
    params: influencer_id -- id of the desired influencer.
    """
    from debra.models import BrandJobPost
    from debra.search_helpers import find_non_default_query

    use_query = False

    if request.GET.get('campaign_posts_query'):
        campaign = BrandJobPost.objects.get(
            id=request.GET.get('campaign_posts_query'))
        if campaign.posts_saved_search:
            use_query = True
            es_query = campaign.posts_saved_search.query
        else:
            es_query = '{}'
    else:
        try:
            es_query = json.loads(urllib.unquote(request.GET.get('q', '{}')))
        except:
            es_query = {}
        else:
            es_query = find_non_default_query(es_query)
            if es_query is None or es_query == [{}]:
                es_query = {}
            if es_query:
                use_query = True

    # posts_per_page = 60
    posts_per_page = 12

    data = {}  # resulting dict

    # if no cached data, then obtaining it from ES and DB
    if not data:
        # jsonifying request
        if not isinstance(es_query, dict):
            try:
                es_query = json.loads(es_query)
            except ValueError:
                mail_admins(
                    "Request jsonify problem",
                    "es_query: {}\n, request: {}".format(es_query, request)
                )
                es_query = {}

        data = {}
        es_query['page'] = 1
        if not use_query:
            es_query['default_posts'] = "profile"

        # getting posts, posts_sponsored, photos for influencer and adding it to result
        posts, posts_sponsored, photos, total_posts = search_helpers.get_influencer_posts_v2(
            influencer_ids=influencer_id,
            parameters=es_query,
            page_size=posts_per_page,
            include_photos=True,
            request=request
        )

        if posts:
            data['posts'] = posts
        if posts_sponsored:
            data['posts_sponsored'] = posts_sponsored
        if photos:
            data['photos'] = photos
        data['total_posts'] = total_posts

        # caching this data result
        # cache.set(cache_key, data)

    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


blogger_posts_json_public = public_influencer_view(blogger_posts_json)
blogger_posts_json = login_required(blogger_posts_json)


def blogger_items_json(request, influencer_id):
    """
    This view renders ajax request with the influencer's items for influencer's PROFILE.
    params: influencer_id -- id of the desired influencer.
    """

    # retrieving the influencer's object
    es_query = urllib.unquote(request.GET.get('q', '{}'))  # passed query parameters

    items_per_page = 25

    data = {}  # resulting dict

    # if no cached data, then obtaining it from ES and DB
    if not data:
        # jsonifying request
        try:
            es_query = json.loads(es_query)
        except ValueError:
            mail_admins(
                "Request jsonify problem",
                "es_query: {}\n, request: {}".format(es_query, request)
            )
            es_query = {}

        data = {}

        es_query['page'] = 1

        # getting items for influencer and adding it to result
        items, total_items = search_helpers.get_influencer_products_v2(
            influencer_ids=influencer_id,
            parameters=es_query,
            page_size=items_per_page
        )
        items = items if len(items) > 2 else []
        if items:
            data['items'] = items
        data['total_items'] = total_items if len(items) > 2 else 0

        # caching this data result
        # cache.set(cache_key, data)

    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


blogger_items_json_public = public_influencer_view(blogger_items_json)
blogger_items_json = login_required(blogger_items_json)


def blogger_stats_json(request, influencer_id):
    from debra.models import Influencer

    cache_key = "bij_%s_stats" % (influencer_id,)

    def get_data():
        influencer = Influencer.objects.get(id=influencer_id)
        return search_helpers.get_popularity_stats(influencer)

    # data = get_or_set_cache(cache_key, get_data)
    data = get_data()

    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
        return HttpResponse("<body>%s</body>" % data)


blogger_stats_json_public = public_influencer_view(blogger_stats_json)
blogger_stats_json = login_required(blogger_stats_json)


def blogger_brand_mentions_json(request, influencer_id):
    from debra.models import Influencer

    esquery = urllib.unquote(request.GET.get('q', '{}'))
    as_json = urllib.unquote(request.GET.get('json', '')) or False

    if as_json:
        esquery = json.loads(esquery)
        bf_raw = []
        eskw = []

        if 'keyword' in esquery and esquery['keyword'] is not None:
            eskw = esquery['keyword']
                
        if 'filters' in esquery and 'brand' in esquery['filters']:
            bf_raw = [b['value'] for b in esquery['filters']['brand']]
            
    else:
        eskw = [esquery]    
        #brand filters normalization
        bf_raw = urllib.unquote(request.GET.get('brands', '')).split(',')
        
    brands_filter = sorted(filter(None, [bf.strip() for bf in set(bf_raw)]))
    brands_filter = ",".join(brands_filter)

    cache_key = "bij_%s_%s_%s_brand_mentions" % (influencer_id, esquery, brands_filter,)
    cache_key = "".join([ord(ch) > 32 and ord(ch) < 129 and ch or str(ord(ch)) for ch in cache_key])
    data = cache.get(cache_key)

    if not data:

        # First variant
        # brands = map(search_helpers.extract_brand_name, brands_filter.split(',') + eskw)
        # brands = filter(None, brands)

        # Variant with multiple urls at once
        brands = search_helpers.extract_brand_names(brands_filter.split(',') + eskw)

        brand_names = {brand.name.title().strip() for brand in brands}

        influencer = Influencer.objects.get(id=influencer_id)

        data = search_helpers.get_brand_mentions(influencer, exclude_itself=True)

        mentions_notsponsored = search_helpers\
            .additional_brand_mentions_filtering(
                data["mentions_notsponsored"], brand_names)
        if len(mentions_notsponsored) < 3:
            mentions_notsponsored = []
        data['mentions_notsponsored'] = {
            'name': 'main',
            'children': [{
                'name': item['name'].lower(),
                'children':[{
                    'name': item['name'],
                    'size': item['count'],
                    'data': {
                        # 'domain': if item.get('domain_name'),
                        'url': reverse('debra.blogger_views.blogger_generic_posts',
                            kwargs=dict(
                                section='all',
                                influencer_id=influencer_id,
                                brand_domain=item.get('domain_name'),
                            )
                        ) if item.get('domain_name') else None
                    },
                }]
            } for item in mentions_notsponsored]
        }
        data['mentions_min'] = min(x['count']
            for x in mentions_notsponsored) if mentions_notsponsored else 0
        data['mentions_max'] = max(x['count']
            for x in mentions_notsponsored) if mentions_notsponsored else 0
        data['brand_names'] = list(set(x['name']
            for x in mentions_notsponsored))
        # data["mentions_notsponsored"] = search_helpers.additional_brand_mentions_filtering(data["mentions_notsponsored"], brand_names)

        cache.set(cache_key, data)

    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
        return HttpResponse("<body>%s</body>" % data)


blogger_brand_mentions_json_public = public_influencer_view(
    blogger_brand_mentions_json)
blogger_brand_mentions_json = login_required(blogger_brand_mentions_json)


def blogger_post_counts_json(request, influencer_id):
    from debra.models import Influencer

    post_type = request.GET.get('post_type')
    influencer = Influencer.objects.get(id=influencer_id)

    POST_TYPES = ['photos', 'pins', 'tweets', 'videos', 'blog_posts']

    if post_type not in POST_TYPES:
        return HttpResponseBadRequest()

    def get_page_url(influencer, post_type):
        field = {
            'blog_posts': 'posts_page',
            'photos': 'photos_page',
            'tweets': 'tweets_page',
            'pins': 'pins_page',
            'videos': 'youtube_page',
        }[post_type]
        return getattr(influencer, field)

    def get_count(influencer, post_type):
        # return getattr(influencer, '{}_count'.format(post_type))
        return influencer.get_posts_section_count(post_type)

    def get_post_type_verbose(post_type):
        return ' '.join([w.capitalize() for w in post_type.split('_')])

    data = {
        'count': get_count(influencer, post_type),
        'post_type': post_type,
        'post_type_verbose': get_post_type_verbose(post_type),
        'page_url': get_page_url(influencer, post_type),
    }

    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
        return HttpResponse("<body>%s</body>" % data)


blogger_post_counts_json_public = public_influencer_view(
    blogger_post_counts_json)
blogger_post_counts_json = login_required(blogger_post_counts_json)


#####-----</ Similar Web Views />-----#####
def blogger_monthly_visits(request, influencer_id):
    ''' blogger_monthly_views returns an array of all monthly view data for an influencer.
    
    @request: django request object
    @influnecer_id: the id of the influencer to get data for
    
    @results: list of dictionaries containing :month, :count
    '''
    from debra.models import Influencer

    brand = request.visitor["brand"]

    def get_compete_data():
        influencer = Influencer.objects.get(id=influencer_id)
        return influencer.get_monthly_visits_compete(
            brand.flag_compete_api_key)

    def get_data():
        influencer = Influencer.objects.get(id=influencer_id)
        return influencer.get_monthly_visits()

    use_compete = brand and brand.flag_compete_api_key_available

    getter, cache_key = (get_compete_data, "bmv_{}_compete".format(
        influencer_id)) if use_compete else (get_data, "bmv_{}".format(
            influencer_id))

    data = get_or_set_cache(cache_key, getter)

    data = {
        'columns': [
            ['x'] + [item['date'] for item in data],
            ['visits'] + [item['count'] for item in data],
        ]
    }

    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type='application/json')
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
        return HttpResponse('<body>%s</body>' % data)


blogger_monthly_visits_public = public_influencer_view(blogger_monthly_visits)
blogger_monthly_visits = login_required(blogger_monthly_visits)


def blogger_traffic_shares(request, influencer_id): 
    cache_key = "bts_{}".format(influencer_id)

    def get_data():
        influencer = Influencer.objects.get(id=influencer_id)
        return influencer.get_traffic_shares()

    data = get_or_set_cache(cache_key, get_data)

    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type='application/json')
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
        return HttpResponse('<body>%s</body>' % data)


blogger_traffic_shares_public = public_influencer_view(blogger_traffic_shares)
blogger_traffic_shares = login_required(blogger_traffic_shares)


def blogger_top_country_shares(request, influencer_id):
    cache_key = "bcs_{}".format(influencer_id)

    def get_data():
        influencer = Influencer.objects.get(id=influencer_id)
        return influencer.get_top_country_shares()

    data = get_or_set_cache(cache_key, get_data)

    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type='application/json')
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
        return HttpResponse('<body>%s</body>' % data)


blogger_top_country_shares_public = public_influencer_view(blogger_top_country_shares)
blogger_top_country_shares = login_required(blogger_top_country_shares)

#####-----</ End Similar Web Views />-----#####        

def blogger_info_json(request, influencer_id):
    """
    this views returns details json for influencer given in parameter
    request can contain GET query with:
    - q - elastic search query that matches posts content, brands, etc and highlights results
    - brands - elastic search query that matches brands and highlights its related items/posts
    """
    t0 = time.time()
    mongo_utils.track_visit(request)
    esquery = urllib.unquote(request.GET.get('q', '{}'))

    influencer_id = int(influencer_id)

    t_bf = time.time()
    #brand filters normalization
    bf_raw = urllib.unquote(request.GET.get('brands', '')).split(',')
    brands_filter = sorted(filter(None, [bf.strip() for bf in set(bf_raw)]))
    brands_filter = ",".join(brands_filter)
    print 'Brand filters normalization', t_bf - time.time()

    auth_user = request.visitor["auth_user"]

    t_mongo = time.time()
    mongo_utils.track_query("brand-clicked-blogger-detail-panel", {
        "influencer_id": influencer_id,
        "post_filter": esquery,
        "brand_filter": brands_filter
    }, {"user_id": auth_user.id if auth_user else None })
    print 'Mongo track', time.time() - t_mongo

    t_b = time.time()
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    print 'Brand/BaseBrand retrieve', t_b - time.time()

    try:
        parameters = json.loads(esquery)
    except ValueError:
        mail_admins(
            "Request jsonify problem",
            "es_query: {}\n, request: {}".format(esquery, request)
        )
        parameters = {}

    t_cache = time.time()

    def get_cache_key(influencer_id):
        return 'bij_%s_%i_%i_%i' % (
            parameters.get('sub_tab', 'main_search'),
            influencer_id,
            int(bool(base_brand.flag_show_dummy_data if base_brand else False)),
            int(request.user.is_authenticated())
        )

    # get base influencer json from cache or create one
    # cache_key = get_cache_key(influencer_id)

    # data = cache.get(cache_key)
    # print 'Retrieve data from cache', time.time() - t_cache

    print 'Pre-influencer stage', time.time() - t0

    if True:
        _t0 = time.time()
        influencer = Influencer.objects.prefetch_related(
            'platform_set',
            'shelf_user__userprofile',
            'demographics_locality',
            # 'mails__candidate_mapping__job',
            # 'group_mapping__jobs__job'
        ).get(id=influencer_id)

        influencer.for_search = True

        print 'Influencer prefetch', time.time() - _t0
        t0 = time.time()

        data = search_helpers.get_influencer_json(
            influencer,
            with_posts=False,
            with_items=False,
            with_stats=False,
            with_brand_mentions=False,
            parameters=parameters,
            request=request
        )
        
        print 'Get influencer json', time.time() - t0

        # cache.set(cache_key, data)

    t0 = time.time()

    # some brand related variables
    if base_brand and base_brand.is_subscribed and base_brand.stripe_plan in STRIPE_EMAIL_PLANS:
        if base_brand.stripe_plan in STRIPE_COLLECTION_PLANS:
            data["can_favorite"] = True
            # data["is_favoriting"] = brand.influencer_groups.filter(
            #     influencers_mapping__influencer__id=influencer_id).exists()
        data["email"] = False
        if 'influencer' not in locals():
            influencer = Influencer.objects.get(id=influencer_id)
        emails = influencer.email
        if emails:
            splited = emails.split()
            if splited:
                data["email"] = splited[0]
    else:
        data["can_favorite"] = False

    # invited_to list (moved from serializer to prevent being cached)
    if False and brand:
        job_ids = InfluencerJobMapping.objects.with_influencer(
            influencer
        ).filter(
            Q(mailbox__brand_id=brand.id) | \
            Q(mapping__group__owner_brand_id=brand.id)
        ).distinct('job').values_list('job', flat=True)
    else:
        job_ids = []

    if brand:
        from debra.models import InfluencerBrandMapping
        from debra.serializers import InfluencerBrandMappingSerializer
        brand_mapping, _ = InfluencerBrandMapping.objects.get_or_create(
            influencer_id=influencer.id, brand_id=brand.id)
        data['brand_custom_data'] = InfluencerBrandMappingSerializer(
            brand_mapping).data

    data["invited_to"] = list(job_ids)

    # if request.user.is_authenticated():
    #     mapping, _ = InfluencerBrandUserMapping.objects.get_or_create(
    #         user=request.user, influencer=influencer)
    #     data['note'] = mapping.notes

    # tracking
    account_helpers.intercom_track_event(request, "brand-clicked-blogger-detail-panel", {
        'blog_url': data["profile"]["blog_page"]
    })

    print 'Post influencer stage', time.time() - t0

    # finaly serialize and send back
    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
        return HttpResponse("<body>%s</body>" % data)


blogger_info_json_public = public_influencer_view(blogger_info_json)
blogger_info_json = login_required_json(blogger_info_json)


@login_required
def search_brand_json(request):
    """
    this view returns brand names and urls matching GET query *term*
    """
    mongo_utils.track_visit(request)

    if request.is_ajax():
        brand_term = urllib.unquote(request.GET.get('term'))
        brand_term = utils.domain_from_url(brand_term)
        if not brand_term:
            return HttpResponse()
        brands = BrandMentions.objects.filter(brand__blacklisted=False, brand__domain_name__icontains=brand_term)
        brands = brands.distinct('brand__name').only(
            'brand__name', "brand__domain_name").values('brand__name', "brand__domain_name")
        data = [{"name": x["brand__name"], "url": x["brand__domain_name"]} for x in brands[:100]]
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    return HttpResponse()


@login_required
def autocomplete(request):
    """
    this view returns any items matching GET *query*
    """
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()
    endpoint = "/" + ELASTICSEARCH_INDEX + "/_suggest"
    url = ELASTICSEARCH_URL
    query = {
        "text": urllib.unquote(request.GET.get('query')),
        "blogger_name": {
            "completion": {
                "field": "_suggest_name",
                "fuzzy": True
            }
        },
        "blog_name": {
            "completion": {
                "field": "_suggest_blogname",
                "fuzzy": True
            }
        },
        "blog_url": {
            "completion": {
                "field": "_suggest_blogurl",
                "fuzzy": True
            }
        },
        "brand_name": {
            "completion": {
                "field": "_suggest_brandname",
                "fuzzy": True
            }
        },
        "brand_url": {
            "completion": {
                "field": "_suggest_brandurl",
                "fuzzy": True
            }
        }
    }

    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    options = []
    if rq.status_code == 200:
        resp = rq.json()
        options = {}
        options["name"] = []
        options["blogname"] = []
        options["blogurl"] = []
        options["brand"] = []
        options["brandurl"] = []
        for suggestion in resp.get("blogger_name", []):
            for option in suggestion.get("options", []):
                data = {
                    'value': option["text"],
                    'label': option["text"]
                }
                options["name"].append(data)
        for suggestion in resp.get("blog_name", []):
            for option in suggestion.get("options", []):
                data = {
                    'value': option["text"],
                    'label': option["text"]
                }
                options["blogname"].append(data)
        for suggestion in resp.get("blog_url", []):
            for option in suggestion.get("options", []):
                data = {
                    'value': option["text"],
                    'label': option["text"]
                }
                options["blogurl"].append(data)
        for suggestion in resp.get("brand_name", []):
            for option in suggestion.get("options", []):
                data = {
                    'value': option["text"],
                    'label': option["text"]
                }
                options["brand"].append(data)
        for suggestion in resp.get("brand_url", []):
            for option in suggestion.get("options", []):
                data = {
                    'value': option["text"],
                    'label': option["text"]
                }
                options["brandurl"].append(data)

    influencer_q = []
    for option in options["name"]:
        influencer_q.append(Q(name=option["value"]))
    for option in options["blogname"]:
        influencer_q.append(Q(blogname=option["value"]))
    for option in options["blogurl"]:
        influencer_q.append(Q(blog_url=option["value"]))
    brand_q = []
    for option in options["brand"]:
        brand_q.append(Q(name=option["value"]))
    for option in options["brandurl"]:
        brand_q.append(Q(domain_name=option["value"]))

    old_options = options
    options = {}
    options["name"] = []
    options["blogname"] = []
    options["blogurl"] = []
    options["brand"] = []
    options["brandurl"] = []

    if influencer_q:
        influencers = Influencer.objects
        influencers = influencers.prefetch_related('shelf_user__userprofile', 'shelf_user')
        influencers = influencers.filter(reduce(lambda a, b: a | b, influencer_q))
        influencers = influencers.only('name', 'blogname', 'blog_url', 'profile_pic_url', 'shelf_user')

        unique_influencer_labels = set()
        for option in old_options["name"]:
            option_influencer = None
            for influencer in influencers:
                if influencer.name == option["value"]:
                    option_influencer = influencer
                    break
            if not option_influencer:
                continue
            option["label"] = option_influencer.name
            option["photo"] = option_influencer.profile_pic
            if option["label"] in unique_influencer_labels:
                continue
            unique_influencer_labels.add(option["label"])
            options["name"].append(option)
        for option in old_options["blogname"]:
            option_influencer = None
            for influencer in influencers:
                if influencer.blogname == option["value"]:
                    option_influencer = influencer
                    break
            if not option_influencer:
                continue
            option["label"] = option_influencer.name
            option["photo"] = option_influencer.profile_pic
            if option["label"] in unique_influencer_labels:
                continue
            unique_influencer_labels.add(option["label"])
            options["blogname"].append(option)
        for option in old_options["blogurl"]:
            option_influencer = None
            for influencer in influencers:
                if influencer.blog_url and option["value"] in influencer.blog_url:
                    option_influencer = influencer
                    break
            if not option_influencer:
                continue
            option["label"] = option_influencer.name
            option["photo"] = option_influencer.profile_pic
            if option["label"] in unique_influencer_labels:
                continue
            unique_influencer_labels.add(option["label"])
            options["blogurl"].append(option)
    else:
        options["name"] = old_options["name"]
        options["blogname"] = old_options["blogname"]
        options["blogurl"] = old_options["blogurl"]

    if brand_q:
        brands = Brands.objects
        brands = brands.filter(reduce(lambda a, b: a | b, brand_q))
        brands = brands.only('name', 'domain_name')

        unique_brand_labels = set()
        for option in old_options["brand"]:
            option_brand = None
            for brand in brands:
                if brand.name == option["value"]:
                    option_brand = brand
                    break
            if not option_brand:
                continue
            option["label"] = option_brand.name
            if option["label"] in unique_brand_labels:
                continue
            unique_brand_labels.add(option["label"])
            options["brand"].append(option)
        for option in old_options["brandurl"]:
            option_brand = None
            for brand in brands:
                if brand.domain_name == option["value"]:
                    option_brand = brand
                    break
            if not option_brand:
                continue
            option["label"] = option_brand.name
            if option["label"] in unique_brand_labels:
                continue
            unique_brand_labels.add(option["label"])
            options["brandurl"].append(option)
    else:
        options["brandurl"] = old_options["brandurl"]
        options["brand"] = old_options["brand"]

    if request.is_ajax():
        return HttpResponse(json.dumps(options), content_type="application/json")
    else:
        return HttpResponse("<body></body>")


@login_required
def autocomplete_with_type(request):
    """
    returns items of given *type* for *query*
    """
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()
    endpoint = "/" + ELASTICSEARCH_INDEX + "/_suggest"
    url = ELASTICSEARCH_URL
    type = urllib.unquote(request.GET.get('type'))
    query = {
        "text": urllib.unquote(request.GET.get('query'))
    }
    if type == "name":
        query["suggestions"] = {
            "completion": {
                "field": "_suggest_name",
                #"fuzzy": True,
                "size": 10,
            }
        }
    elif type == "blogname":
        query["suggestions"] = {
            "completion": {
                "field": "_suggest_blogname",
                #"fuzzy": True,
                "size": 10,
            }
        }
    elif type == "blogurl":
        query["suggestions"] = {
            "completion": {
                "field": "_suggest_blogurl",
                #"fuzzy": True,
                "size": 10,
            }
        }
    elif type == "location":
        query["suggestions"] = {
            "completion": {
                "field": "_suggest_location",
                #"fuzzy": True,
                "size": 10,
            }
        }
    if settings.DEBUG:
        print json.dumps(query, indent=4)

    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    options = []
    if rq.status_code == 200:
        resp = rq.json()
        print(' *** %s' % resp)
        options = []
        for suggestion in resp.get("suggestions", []):
            for option in suggestion.get("options", []):
                data = {
                    'value': unescape(option["text"]),
                    'label': unescape(option["text"])
                }
                options.append(data)

    if request.is_ajax():
        return HttpResponse(json.dumps(options), content_type="application/json")
    else:
        return HttpResponse("<body></body>")


@login_required
def autocomplete_brand(request):
    """
    returns brands names matching *query*
    """
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()
    endpoint = "/" + ELASTICSEARCH_INDEX + "/_suggest"
    url = ELASTICSEARCH_URL
    query = {
        "text": urllib.unquote(request.GET.get('query')),
        "suggestions": {
            "completion": {
                "field": "_suggest_brandname",
                "fuzzy": True,
                "size": 50,
            }
        }
    }
    if settings.DEBUG:
        print json.dumps(query, indent=4)

    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    options = []
    if rq.status_code == 200:
        resp = rq.json()
        names = []
        for suggestion in resp.get("suggestions", []):
            for option in suggestion.get("options", []):
                names.append(option["text"])

        if names:
            brands = Brands.objects.filter(name__in=names).only('name', 'domain_name').values('name', 'domain_name')
            for brand in brands:
                options.append({"text": brand["name"], "value": brand["domain_name"]})
    if request.is_ajax():
        return HttpResponse(json.dumps(options), content_type="application/json")
    else:
        return HttpResponse("<body></body>")


def saved_views_tags(request):

    brand = request.visitor["base_brand"]

    groups = request.visitor["brand"].influencer_groups.exclude(
        archived=True
    ).filter(
        creator_brand=brand,
        system_collection=False
    ).prefetch_related(
        'influencers_mapping__influencer__shelf_user__userprofile'
    )

    for group in groups:
        group.imgs = []
        # for influencer in list(group.influencers.all())[:4]:
        for influencer in group.influencers[:NUM_OF_IMAGES_PER_BOX]:
            group.imgs.append(influencer.profile_pic)

    campaigns = request.visitor["brand"].job_posts.filter(oryg_creator=brand)

    context = {
        'search_page': True,
        'type': 'followed',
        'sub_page': 'tags',
        'selected_tab': 'tags_and_searches',
        'shelf_user': request.user.userprofile,
        'groups': groups,
        'campaign_list': campaigns,
    }

    return render(request, 'pages/search/saved_views_tags.html', context)


def post_analytics_collections(request):

    brand = request.visitor["base_brand"]

    existing = brand.created_post_analytics_collections.filter(
        system_collection=False
    ).exclude(
        archived=True
    ).prefetch_related(
        'postanalytics_set__post'
    ).order_by('name', '-created_date')

    if request.is_ajax():
        data = [{'value': x.id, 'text': x.name} for x in existing]
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        context = {
            'search_page': True,
            'type': 'followed',
            'sub_page': 'post_analytics_collections',
            'selected_tab': 'competitors',
            'shelf_user': request.user.userprofile,
            'groups': existing,
        }

        return render(
            request, 'pages/search/post_analytics_collections.html', context)


def edit_post_analytics(request, post_analytics_id):
    from debra.serializers import PostAnalyticsTableSerializer
    from debra.models import (
        InfluencerEditHistory, PlatformDataOp, InfluencerAnalytics)
    from debra import admin_helpers
    from debra import brand_helpers
    if request.method == 'POST':
        body = json.loads(request.body)

        if body.get('is_blogger_approval'):
            del body['is_blogger_approval']
            pa = InfluencerAnalytics.objects.get(id=post_analytics_id)
            collection = None
        else:
            pa = PostAnalytics.objects.get(id=post_analytics_id)
            collection = pa.collection

        for key, value in body.items():
            if key == 'blog_name' and pa.influencer.blogname != value:
                pa.influencer.blogname = value
                pa.influencer.append_validated_on("customer")
                InfluencerEditHistory.commit_change(
                    pa.influencer, 'blogname', value)
                pa.influencer.save()
            elif key == 'influencer_name' and pa.influencer.name != value:
                pa.influencer.name = value
                pa.influencer.append_validated_on("customer")
                InfluencerEditHistory.commit_change(
                    pa.influencer, 'name', value)
                pa.influencer.save()
            elif key == 'post_create_date' and value:
                pa.post.create_date = datetime.datetime.strptime(value, '%Y-%m-%d')
                pa.post.save()
                PlatformDataOp.objects.create(
                    post=pa.post, operation='customer_updated_createdate')
            elif key == 'post_title' and value:
                pa.post.title = value
                pa.post.save()
                PlatformDataOp.objects.create(
                    post=pa.post, operation="customer_updated_post_title")
            elif key == 'post_url' and value and pa.post_url != value:
                # pa.post.url = value
                # pa.post.save()
                # PlatformDataOp.objects.create(
                #     post=pa.post, operation="customer_updated_post_url")
                collection.remove(pa.post_url)
                brand_helpers.handle_post_analytics_urls(
                    [value], refresh=True, collection=collection)
            elif key == 'post_num_comments':
                pa.post_comments = value
                pa.save()
                PlatformDataOp.objects.create(
                    post=pa.post, operation="customer_updated_post_num_comments")
            elif key == 'tw_url':
                pa.influencer.tw_url = value
                pa.influencer.save()
                admin_helpers.handle_social_handle_updates(pa.influencer, 'tw_url', value)
            elif key == 'insta_url':
                pa.influencer.insta_url = value
                pa.influencer.save()
                admin_helpers.handle_social_handle_updates(pa.influencer, 'insta_url', value)
            elif key == 'fb_url':
                pa.influencer.fb_url = value
                pa.influencer.save()
                admin_helpers.handle_social_handle_updates(pa.influencer, 'fb_url', value)
            elif key == 'pin_url':
                pa.influencer.pin_url = value
                pa.influencer.save()
                admin_helpers.handle_social_handle_updates(pa.influencer, 'pin_url', value)
            elif key == 'youtube_url':
                pa.influencer.youtube_url = value
                pa.influencer.save()
                admin_helpers.handle_social_handle_updates(pa.influencer, 'youtube_url', value)
            elif key in ['count_gplus_plusone', 'count_pins', 'count_tweets']:
                pa.__dict__[key] = value
                pa.save()
                PlatformDataOp.objects.create(
                    post=pa.post, operation='customer_updated_' + key)
            elif key in ['count_fb']:
                pa.count_fb_shares = value
                pa.count_fb_likes = 0
                pa.count_fb_comments = 0
                pa.save()
                PlatformDataOp.objects.create(
                    post=pa.post, operation='customer_updated_count_fb')

        return HttpResponse()

    return HttpResponseBadRequest()


def del_post_analytics(request, post_analytics_id):
    if request.method == 'POST':
        # actual post analytics
        pa = PostAnalytics.objects.get(id=post_analytics_id)
        # but we should remove all the instances
        # wih the same url in a collection
        pa.collection.remove(pa.post_url)
        return HttpResponse()

    return HttpResponseBadRequest()


def refresh_post_analytics_collection(request, collection_id):

    collection = PostAnalyticsCollection.objects.get(id=collection_id)

    if request.method == 'POST':
        if not collection.updated:
            data = {
                'error': """We're still calculating, so this operation 
                            is not possible at this time. Please try again later 
                            (we'll send you an email when it's complete."""
            }
        elif collection.is_updated_recently:
            data = {
                'error': """We calculated the results in the last few hours, 
                            so please again tomorrow."""
            }
        else:
            data = {}
            collection.refresh()

        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type='application/json')

    return HttpResponseBadRequest()


# ANALYTICS DETAILS
@login_required
def post_analytics_collection(request, collection_id):
    from debra.serializers import PostAnalyticsTableSerializer, count_totals

    collection = PostAnalyticsCollection.objects.get(id=collection_id)

    qs = collection.get_unique_post_analytics().with_counters()

    context = search_helpers.generic_reporting_table_context(
        request,
        queryset=qs,
        serializer_class=PostAnalyticsTableSerializer,
        total_with_fields=True,
        annotation_fields={
            'post_num_comments': 'agr_num_comments',
            'count_total': 'agr_count_total',
            'count_fb': 'agr_count_fb',
        }
    )

    context.update({
        'sub_page': 'post_analytics_collections',
        'collection': collection,
        'table_id': 'post_analytics_collection_table',
    })

    return render(
        request,
        'pages/search/post_analytics_collection_details.html', context)


@login_required
def post_analytics_collection_edit(request, collection_id):
    from debra.serializers import PostAnalyticsUrlsSerializer
    collection = PostAnalyticsCollection.objects.get(id=collection_id)

    qs = collection.get_unique_post_analytics()

    if request.is_ajax():
        data = PostAnalyticsUrlsSerializer(qs, many=True).data
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type='application/json')

    context = {
        'collection': collection,
        'data_count': qs.count(),
        'search_page': True,
        'type': 'followed',
        'sub_page': 'post_analytics_collections',
        'selected_tab': 'competitors',
        'shelf_user': request.user.userprofile,
    }

    return render(
        request,
        'pages/search/post_analytics_collection_edit.html', context)


@login_required
def post_analytics_collection_create(request):
    context = {
        'search_page': True,
        'type': 'followed',
        'sub_page': 'post_analytics_collections',
        'selected_tab': 'competitors',
        'shelf_user': request.user.userprofile,
    }

    return render(
        request,
        'pages/search/post_analytics_collection_create.html', context)


@login_required
def roi_prediction_report_edit(request, report_id):
    from debra.serializers import PostAnalyticsUrlsSerializer
    report = ROIPredictionReport.objects.get(id=report_id)
    collection = report.post_collection
    qs = collection.get_unique_post_analytics()
    infs = qs.exclude(
        post__influencer__isnull=True
    ).values_list('post__influencer', flat=True).distinct()

    if request.is_ajax():
        data = PostAnalyticsUrlsSerializer(qs, many=True).data
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type='application/json')

    context = {
        'report': report,
        'collection': collection,
        'data_count': infs.count(),
        'search_page': True,
        'type': 'followed',
        # 'sub_page': 'influencer_stats',
        'sub_page': 'roi_prediction_reports',
        'selected_tab': 'competitors',
        'shelf_user': request.user.userprofile,
        'request': request,
    }

    return render(
        request,
        'pages/search/roi_prediction_report_edit.html', context)


@login_required
def roi_prediction_report_create(request):
    context = {
        'search_page': True,
        'type': 'followed',
        # 'sub_page': 'influencer_stats',
        'sub_page': 'roi_prediction_reports',
        'selected_tab': 'competitors',
        'shelf_user': request.user.userprofile,
        'request': request,
    }

    return render(
        request,
        'pages/search/roi_prediction_report_create.html', context)


def saved_views_favorites(request):
    pass


def saved_views_posts(request):
    context = {
        'search_page': True,
        'type': 'followed',
        'sub_page': 'saved_posts',
        'selected_tab': 'tags_and_searches',
        'shelf_user': request.user.userprofile
    }

    return render(request, 'pages/search/saved_views_posts.html', context)


def saved_views_searches(request):
    brand = request.visitor["base_brand"]
    saved_queries = brand.saved_queries.exclude(
        name__isnull=True
    ).exclude(
        archived=True
    )
    for query in saved_queries:
        if not query.result:
            query.num_results = 0
            query.imgs = []
            continue
        result = json.loads(query.result)
        query.imgs = [x['pic'] for x in result['results'][:NUM_OF_IMAGES_PER_BOX]]
        query.num_results = result['total']

        if settings.DEBUG:
            print('*** QUERY RESULT ***')
            print(result)

    context = {
        'search_page': True,
        'type': 'followed',
        'sub_page': 'saved_searches',
        'selected_tab': 'tags_and_searches',
        'shelf_user': request.user.userprofile,
        'saved_queries': saved_queries,
    }
    return render(request, 'pages/search/saved_views_searches.html', context)


def save_search(request):
    if request.method == 'POST':
        brand = request.visitor["base_brand"]
        try:
            query_id = int(request.POST.get('query_id'))
        except ValueError:
            query_id = None

        query_string = request.POST.get('query')
        try:
            if query_string in [None, 'null']:
                raise ValueError
            json.loads(query_string)
        except ValueError:
            mail_admins(
                "Saving search with incorrect query",
                "query string: {}".format(query_string, request)
            )

        if query_id is not None:
            q = brand.saved_queries.get(id=query_id)
            q.name = request.POST.get('name')
            q.query = request.POST.get('query')
            q.result = request.POST.get('result')
            q.save()
        else:
            sq = brand.saved_queries.create(
                user=request.user,
                name=request.POST.get('name'),
                query=request.POST.get('query'),
                result=request.POST.get('result')
            )
            query_id = sq.id
        data = json.dumps({'id': query_id}, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    return HttpResponseBadRequest()


@login_required_json
def saved_search_details(request, query_id=None, section=None, **kwargs):

    from debra.models import (SearchQueryArchive, Influencer, Posts,\
        ProductModelShelfMap)

    SECTIONS = ['all', 'influencers', 'blog_posts', 'instagrams', 'tweets',\
        'pins', 'youtube', 'products', 'facebook']
    POST_SECTIONS = ['all', 'blog_posts', 'instagrams', 'tweets', 'pins',\
        'facebook', 'youtube',]
    PRODUCT_SECTIONS = ['products']

    if not section in SECTIONS:
        raise Http404

    if query_id:
        query = SearchQueryArchive.objects.get(id=query_id)
    else:
        query = None

    count_only = request.GET.get('count_only')

    filter_mapping = {
        'all': 'all',
        'blog_posts': 'blog',
        'instagrams': 'photos',
        'tweets': 'tweets',
        'pins': 'pins',
        'facebook': 'blog',
        'youtube': 'youtube',
        'products': 'products',
        'facebook': 'facebook',
    }

    default_posts_mapping = {
        'all': 'about_all',
        'pins': 'about_pins',
        'tweets': 'about_tweets',
        'instagrams': 'about_insta',
        'youtube':  'about_youtube',
        'facebook': 'about_facebook',
    }

    if request.method == 'POST':
        if not section in POST_SECTIONS and not section in PRODUCT_SECTIONS:
            return HttpResponseBadRequest()

        front_end_query = search_helpers.query_from_request(request)
        front_end_filters = front_end_query.get('filters')

        if query:
            result, esquery = query.result_json, search_helpers.query_from_request(request, source=query.query_json)
        else:
            result, esquery = None, None

        if front_end_filters and esquery:
            esquery['filters']['time_range'] = front_end_filters.get('time_range')

        feed_json = feeds_helpers.get_feed_handler(section)

        feed_params = dict(no_cache=True, limit_size=30, count_only=count_only)
        # for_influencer=influencer, default_posts="about_pins"
        if front_end_query.get('influencer'):
            try:
                influencer = Influencer.objects.get(
                    id=int(front_end_query.get('influencer')))
            except:
                raise Http404()
            else:
                feed_params.update({
                    'for_influencer': influencer,
                    'default_posts': default_posts_mapping.get(section, 'about'),
                    'with_parameters': True,
                    'parameters': esquery if query_id else front_end_query,
                })
        else:
            feed_params.update({
                'with_parameters': True,
                'parameters': esquery if query_id else front_end_query,
            })

        data = feed_json(request, **feed_params)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    elif not request.is_ajax():
        context = {
            'search_page': True,
            'type': 'followed',
            'sub_page': section,
            'selected_tab': 'tags_and_searches',
            'shelf_user': request.user.userprofile,
            'sections': SECTIONS,
            'section': section,
            'platform_filter': filter_mapping.get(section),
            'query': query
        }
        return render(request, 'pages/search/saved_search_details_{}.html'.format(
            'influencers' if section == 'influencers' else 'posts'), context)


@login_required
def get_saved_searches(request, query_id):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    saved_search = get_object_or_404(SearchQueryArchive,
        id=query_id, brand=brand)

    data = {
        'id': saved_search.id,
        'name': saved_search.name,
        'query': saved_search.query_json,
        'and_or_filter_on': saved_search.query_json.get(
            'and_or_filter_on', False)
    }

    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


@login_required
def edit_saved_searches(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    saved_search = get_object_or_404(SearchQueryArchive,
        id=data.get('id'), brand=brand)

    if brand.saved_queries.exclude(archived=True).filter(
        name=data.get('name')).exists():
        return HttpResponseBadRequest(
            "Saved Search with such name already exists",
            content_type="application/json")

    saved_search.name = data.get('name')
    saved_search.save()

    return HttpResponse()


@login_required
def delete_saved_search(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    saved_search = get_object_or_404(SearchQueryArchive,
        id=data.get('id'), brand=brand)

    mongo_utils.track_query("brand-delete-saved-search", {
        'saved_search_name': saved_search.name,
    }, {"user_id": request.visitor["auth_user"].id})

    account_helpers.intercom_track_event(request, "brand-delete-saved-search", {
        'saved_search_name': saved_search.name,
    })

    saved_search.archived = True
    saved_search.save()

    return HttpResponse()


def roi_prediction_reports(request):
    from aggregate_if import Count
    brand = request.visitor["base_brand"]

    existing = brand.created_roi_prediction_reports.filter(
        post_collection__system_collection=False
    ).exclude(
        archived=True
    ).prefetch_related(
        'post_collection__postanalytics_set__post'
    ).annotate(
        influencers_number=Count(
            'post_collection__postanalytics__post__influencer', distinct=True)
    ).order_by('name', '-created_date')

    if request.is_ajax():
        data = [{'value': x.id, 'text': x.name} for x in existing]
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        context = {
            'search_page': True,
            'type': 'followed',
            'sub_page': 'roi_prediction_reports',
            'selected_tab': 'competitors',
            'shelf_user': request.user.userprofile,
            'groups': existing,
        }
        return render(
            request, 'pages/search/roi_prediction_reports.html', context)


# ANALYTICS DETAILS
def roi_prediction_report(request, report_id):

    inf_partial, context = roi_prediction_report_influencer_stats_partial(
        request,report_id)

    context['influencer_stats_partial_content'] = inf_partial

    return render(
        request, 'pages/search/roi_prediction_report_details.html', context)


# ANALYTICS DETAILS
def blogger_approval_report(request, report_id):
    from debra.serializers import InfluencerApprovalReportTableSerializer
    from debra.helpers import PageSectionSwitcher, name_to_underscore

    report = ROIPredictionReport.objects.get(id=report_id)

    collection = report.influencer_collection

    campaign = report.campaign

    if campaign is not None:
        return redirect(
            'debra.job_posts_views.campaign_approval', args=(campaign.id,))
        pre_outreach_enabled = campaign.info_json.get(
            'approval_report_enabled', False)
        if not pre_outreach_enabled:
            raise Http404()

    if request.method == 'POST':
        if request.GET.get('delete_pending'):
            collection.influenceranalytics_set.filter(
                approve_status=InfluencerAnalytics.APPROVE_STATUS_PENDING
            ).delete()
        return HttpResponse()

    qs = collection.influenceranalytics_set.prefetch_related(
        'influencer__platform_set',
        'influencer__shelf_user__userprofile',
    )

    status_counts = dict(Counter(qs.values_list('approve_status', flat=True)))

    approve_status = int(request.GET.get(
        'approve_status', -1 if status_counts.get(-1, 0) > 0 else 0
    ))

    statuses = []
    for status, name in InfluencerAnalytics.APPROVE_STATUS[:-1]:
        statuses.append({
            'value': status,
            'count': status_counts.get(status, 0),
            'name': name,
            'visible': False if status_counts.get(status, 0) == 0 and status in [-1, 0] else True,
            'class': '{}_approval'.format(name_to_underscore(name)),
        })

    print '* counts distribution:', status_counts

    if approve_status is not None:
        qs = qs.filter(
            approve_status=approve_status
        )

    def pre_serialize_processor(paginated_qs):
        brand_user_mapping = {
            x.influencer_id:x
            for x in InfluencerBrandUserMapping.objects.filter(
                influencer__in=[p.influencer for p in paginated_qs],
                user=request.user
            )
        }
        for p in paginated_qs:
            p.agr_brand_user_mapping = brand_user_mapping.get(
                p.influencer.id)
            if p.agr_brand_user_mapping:
                p.agr_notes = p.agr_brand_user_mapping.notes
            else:
                p.agr_notes = None

    context = search_helpers.generic_reporting_table_context(
        request,
        queryset=qs,
        serializer_class=InfluencerApprovalReportTableSerializer,
        include_total=False,
        pre_serialize_processor=pre_serialize_processor,
        hidden_fields=report.info_json.get(
            'blogger_approval_report_columns_hidden', []) + ['approve_info'] + ['remove_info'] if collection.approval_status == collection.APPROVAL_STATUS_SUBMITTED else [],
    )

    print context['fields_hidden']

    campaign = report.campaign

    context.update({
        'table_id': 'blogger_approval_report_table',
        'sub_page': 'roi_prediction_reports',
        'collection': collection,
        'approve_status': approve_status,
        'report': report,
        'brand_id': request.visitor["base_brand"].id,
        'user_id': request.user.id,
        'statuses': statuses,
        'total_count': sum(status_counts.values()),
        'public_link': report.get_public_url(request.user),
        'status_counts': status_counts,
        'campaign': campaign,
    })

    if campaign is not None:
        context.update({
            'campaign_switcher': PageSectionSwitcher(
                constants.CAMPAIGN_SECTIONS, 'influencer_approval',
                url_args=(campaign.id,),
                extra_url_args={'influencer_approval': (campaign.report_id,)},
                hidden=[] if pre_outreach_enabled else ['influencer_approval'],
            ),
        })

    return render(
        request, 'pages/search/blogger_approval_report_details.html', context)


from debra.pipeline_views import PublicBloggerApprovalView
blogger_approval_report_public = PublicBloggerApprovalView.as_view()


def approve_report_update(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        brand = Brands.objects.get(id=int(data.get('brand_id')))

        if data.get('approve_status'):
            for ia_id, status in reversed(data.get('approve_status').items()):
                try:
                    ia = InfluencerAnalytics.objects.get(id=ia_id)
                except InfluencerAnalytics.DoesNotExist:
                    continue
                else:
                    if ia.approve_status != int(status):
                        ia.approve_status = int(status)
                        ia.save()
                        print ia_id, 'status changed to', int(status)
                    else:
                        print ia_id, 'status remains', int(status)
        if data.get('notes'):
            for ia_id, note in reversed(data.get('notes').items()):
                try:
                    ia = InfluencerAnalytics.objects.get(id=ia_id)
                except InfluencerAnalytics.DoesNotExist:
                    continue
                else:
                    if note and ia.notes != note:
                        ia.notes = note
                        ia.save()
                        print ia_id, 'note changed'
                    else:
                        print ia_id, 'note remains the same'
        return HttpResponse()
    else:
        return HttpResponseBadRequest()


def public_approval_report_submit(request):
    from debra import helpers, mail_proxy
    from debra.constants import MAIN_DOMAIN, BLOG_DOMAIN
    data = json.loads(request.body)

    brand_id = data.get('brand_id')
    report_id = data.get('report_id')
    user_id = data.get('user_id')

    report = ROIPredictionReport.objects.get(id=report_id)
    user = User.objects.get(id=user_id)

    public_link = report.get_public_url(user)
    inner_link = "{}{}".format(MAIN_DOMAIN, reverse(
        'debra.search_views.blogger_approval_report',
        args=(report_id,))
    )

    # subject = "{}. Client approval report submitted".format(inner_link)
    # body = "".join([
    #     "<p>Public link: {}</p>",
    #     "<p>Inner link: {}</p>",
    # ]).format(public_link, inner_link)

    # helpers.send_admin_email_via_mailsnake(
    #     subject,
    #     body,
    #     ["michael@theshelf.com", "desirae@theshelf.com", "lauren@theshelf.com"]
    # )

    rendered_message = render_to_string(
        'mailchimp_templates/approval_report_submitted_email.txt', {
            'user': user.userprofile,
            'campaign': report.campaign,
            'blog_domain': BLOG_DOMAIN,
            'main_domain': MAIN_DOMAIN,
        }
    ).encode('utf-8')

    mandrill_message = {
        'html': rendered_message,
        'subject': "The Influencer Approval Form for {} has been submitted.".format(report.campaign.title),
        'from_email': 'lauren@theshelf.com',
        'from_name': 'Lauren',
        'to': [{
            'email': user.email,
            'name': user.userprofile.name if user.userprofile else user.email
        }],
    }

    print mandrill_message

    mail_proxy.mailsnake_send(mandrill_message)

    report.influencer_collection.approval_status = InfluencerAnalyticsCollection.APPROVAL_STATUS_SUBMITTED
    report.influencer_collection.save()

    if report.campaign:
        report.campaign.influencer_collection.influenceranalytics_set.filter(
            tmp_approve_status__isnull=True
        ).update(
            tmp_approve_status=InfluencerAnalytics.APPROVE_STATUS_PENDING
        )
        report.campaign.influencer_collection.influenceranalytics_set.update(
            approve_status=F('tmp_approve_status'))
        report.campaign.merge_approved_candidates(celery=True)

    return HttpResponse()


def blogger_approval_status_change(request, brand_id, report_id, user_id):
    from debra import helpers
    from debra import mail_proxy

    data = json.loads(request.body)
    report = ROIPredictionReport.objects.get(id=report_id)
    user = User.objects.get(id=user_id)
    collection = report.influencer_collection
    if collection.approval_status > int(data.get('status')):
        # if False:
        #     to_list = []
        #     permissiions = report.creator_brand.related_user_profiles.prefetch_related(
        #         'user_profile__user').all()
        #     for permissiion in permissiions:
        #         profile = permissiion.user_profile
        #         if profile and profile.user and profile.user.email:
        #             to_list.append({
        #                 'email': profile.user.email,
        #                 'name': profile.name
        #             })
        to_list = [{
            'email': user.email,
            'name': user.userprofile.name if user.userprofile else user.email
        }]
        mandrill_message = {
            'html': "One of your clients wants to make more changes on '{}' blogger approval report".format(report.name),
            'subject': "More edits for '{}' blogger approval report".format(report.name),
            'from_email': 'atul@theshelf.com',
            'from_name': 'Atul',
            'to': to_list,
        }

        print mandrill_message

        mail_proxy.mailsnake_send(mandrill_message)

    collection.approval_status = int(data.get('status'))
    collection.save()

    return HttpResponse()


def client_approval_invite_send(request, report_id):
    from debra import helpers
    from debra import mail_proxy
    from debra.brand_helpers import send_approval_report_to_client

    report = ROIPredictionReport.objects.get(id=report_id)

    data = json.loads(request.body)

    send_approval_report_to_client.apply_async(
        [report.campaign.id], queue="blogger_approval_report")
    # send_approval_report_to_client(report.campaign.id)

    mandrill_message = {
        'html': data.get('body'),
        'subject': data.get('subject'),
        # 'from_email': request.user.email,
        'from_email': '{}_b_{}_id_{}@reply.theshelf.com'.format(
            request.user.email.split('@')[0],
            request.visitor['base_brand'].id,
            request.user.id),
        'from_name': request.visitor["user"].name,
        'to': data.get('toList', [{
            'email': data.get('toEmail'),
            'name': data.get('toName')
        }]),
    }

    print mandrill_message

    mail_proxy.mailsnake_send(mandrill_message)

    report.influencer_collection.approval_status = 1
    report.influencer_collection.save()

    return HttpResponse()


# ANALYTICS DETAILS
def roi_prediction_report_influencer_stats_partial(request, report_id):
    from debra.serializers import InfluencerReportTableSerializer

    report = ROIPredictionReport.objects.get(id=report_id)

    collection = report.post_collection

    qs = collection.get_unique_post_analytics().exclude(
        post__influencer__isnull=True
    ).with_counters()

    group_by_influencers = defaultdict(list)
    for x in qs:
        group_by_influencers[x.post.influencer_id].append(x)

    inf_ids = [x[0].id for x in group_by_influencers.values() if x]
    qs = qs.filter(id__in=inf_ids)
    collection.agr_post_analytics_set = qs

    context = search_helpers.generic_reporting_table_context(
        request,
        queryset=qs,
        serializer_class=InfluencerReportTableSerializer,
        include_total=False,
        serializer_context={
            'virality_scores': collection.virality_score_values_for_influencers,
            'group_by_influencers': group_by_influencers,
        }
    )

    context.update({
        'report': report,
        'collection': collection,
        'sub_page': 'roi_prediction_reports',
        'table_id': 'influencer_roi_prediction_report_table',
    })

    partial = render_to_string(
        'pages/search/roi_prediction_report_influencer_stats_details_partial.html',
        context)
    return partial, context


# ANALYTICS DETAILS
def roi_prediction_report_influencer_stats(request, report_id):
    partial, context = roi_prediction_report_influencer_stats_partial(
        request,report_id)
    context['influencer_stats_partial_content'] = partial
    return render(
        request,
        'pages/search/roi_prediction_report_influencer_stats_details.html',
        context
    )


def influencer_posts_info(request):
    from debra.serializers import InfluencerReportTableSerializer

    pa_id = int(request.GET.get('pa_id'))
    pa = PostAnalytics.objects.get(id=pa_id)

    context = InfluencerReportTableSerializer(context={
        'brand': request.visitor["base_brand"],
    }).get_posts_info(pa)
    partial = render_to_string(
        context.get('include_template'), {'data': context})

    return HttpResponse(partial)