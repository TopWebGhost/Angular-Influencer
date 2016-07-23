import json
import re
import math
import logging
import pprint
import time
import requests
import datetime

from random import shuffle

# from endless_pagination.paginators import LazyPaginator

from django.conf import settings
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.forms.models import model_to_dict
from django.core.urlresolvers import reverse
from django.template.defaultfilters import cut
from django.utils.html import strip_tags
from django.http import HttpResponse
from django.core.cache import cache

from debra.constants import ELASTICSEARCH_URL
from debra import constants
from debra import search_helpers, account_helpers
from debra.search_helpers import tagStripper, query_from_request
from debra import db_util
from debra.constants import (STRIPE_PLAN_STARTUP, STRIPE_PLAN_CHEAP,\
    STRIPE_PLAN_BASIC, STRIPE_COLLECTION_PLANS)
from debra import elastic_search_helpers
from xpathscraper.utils import domain_from_url, remove_www, remove_protocol


log = logging.getLogger('debra.feeds_helpers')


INSTAGRAM_FEED_PAGE_SIZE = 60
PRODUCT_FEED_PAGE_SIZE = 60
BLOG_FEED_PAGE_SIZE = 60
COLLABS_FEED_PAGE_SIZE = 60
TWITTER_FEED_PAGE_SIZE = 60
PINTEREST_FEED_PAGE_SIZE = 60
YOUTUBE_FEED_PAGE_SIZE = 60

INSTAGRAM_FEED_CACHE_PREFIX = "instagram_feed"
PRODUCT_FEED_CACHE_PREFIX = "product_feed"
BLOG_FEED_CACHE_PREFIX = "blog_feed"
COLLABS_FEED_CACHE_PREFIX = "collabs_feed"
TWITTER_FEED_CACHE_PREFIX = "twitter_feed"
PINTEREST_FEED_CACHE_PREFIX = "pinterest_feed"
YOUTUBE_FEED_CACHE_PREFIX = "youtube_feed"

INSTAGRAM_FEED_PAGE_NO_KEY = "pageInst"
PRODUCT_FEED_PAGE_NO_KEY = "pageProd"
BLOG_FEED_PAGE_NO_KEY = "pageBlog"
COLLABS_FEED_PAGE_NO_KEY = "pageCollab"
TWITTER_FEED_PAGE_NO_KEY = "pageTwitter"
PINTEREST_FEED_PAGE_NO_KEY = "pagePin"
YOUTUBE_FEED_PAGE_NO_KEY = "pageVideo"
FACEBOOK_FEED_PAGE_NO_KEY = "pageFacebook"
ALL_FEED_PAGE_NO_KEY = "pageAll"

INSTAGRAM_FEED_FILTER_KEY = "photos"
PRODUCT_FEED_FILTER_KEY = "products"
BLOG_FEED_FILTER_KEY = "blog"
COLLABS_FEED_FILTER_KEY = "collab"
TWITTER_FEED_FILTER_KEY = "tweets"
PINTEREST_FEED_FILTER_KEY = "pins"
YOUTUBE_FEED_FILTER_KEY = "youtube"
FACEBOOK_FEED_FILTER_KEY = "facebook"
ALL_FEED_FILTER_KEY = "all"


def brand_from_keyword(keyword):
    brands = []
    
    if type(keyword) != list:
        keyword = [keyword]

    for k in keyword:
        if type(k) == dict:
            k = k.get('value')
            domain = domain_from_url(k)

            try:
                brand = Brands.objects.get(blacklisted=False, domain_name=domain)
            except:
                pass
            else:
                brands.append(brand)

    return brands
                
def build_options(keyword_query, stype):
    from debra.models import Brands
    if stype == "keyword":
        options = {
            "post_content_title": keyword_query
        }
    elif stype == "brand":
        brands = brand_from_keyword(keyword_query)

        if not brands:
            return None
            
        options = {
            "post_brand": brands,
            "exact": True
        }
    elif stype == "name":
        options = {
            "blogger_name": keyword_query
        }
    elif stype == "blogname":
        options = {
            "blog_name": keyword_query
        }
    elif stype == "blogurl":
        options = {
            "blog_url": keyword_query
        }
    elif stype == "location":
        options = {
            "location": keyword_query
        }
    elif stype == "all":
        brands = brand_from_keyword(keyword_query)
        
        options = {
            "blog_url": keyword_query,
            "blog_name": keyword_query,
            "blogger_name": keyword_query,
            "post_content_title": keyword_query,
            "blog_url": keyword_query,
            "location": keyword_query,
        }
        if brands:
            options = {
                "post_brand": brands
            }
    else:
        options = {}
    return options

def post_ids_for_brand(platform_name_or_names, for_brand, max_pages=20):
    if isinstance(platform_name_or_names, (list, tuple)):
        pnames = platform_name_or_names
    else:
        pnames = [platform_name_or_names]

    brand_name = for_brand.name
    brand_domain_name = for_brand.domain_name.replace('www.', '').replace('.com', '')

    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
    with post_ids as (
        select distinct post_id from
        (
            (select post_id from debra_brandinpost where brand_id=%s)
            union
            (select post_id from debra_mentioninpost where mention in (%s, %s))
            union
            (select post_id from debra_hashtaginpost where hashtag in (%s, %s))
        ) as union_select
    )
    select po.id from debra_posts po
    join debra_platform pl on po.platform_id=pl.id
    join post_ids on post_ids.post_id = po.id
    where pl.platform_name = any(%s)
    order by post_id desc
    limit %s
    """, [for_brand.id, brand_name.lower(), brand_domain_name.lower(),
                        brand_name.lower(), brand_domain_name.lower(),
          pnames,
          INSTAGRAM_FEED_PAGE_SIZE * max_pages])
    post_ids = [row[0] for row in cur]
    return post_ids


def get_user_for_post(influencer, parameters, **kw):
    from debra.serializers import InfluencerSerializer
    from debra import constants
    request = kw.get('request')
    brand = request.visitor["base_brand"] if request else None
    res = influencer.feed_stamp
    if brand and brand.flag_show_dummy_data:
        res['user_name'] = constants.FAKE_BLOGGER_DATA['name']
        res['blog_name'] = constants.FAKE_BLOGGER_DATA['blogname']
        res['blog_page'] = constants.FAKE_BLOGGER_DATA['blog_url']
    if parameters is None:
        parameters = {}
    res.update({
        'current_platform_page': InfluencerSerializer(
            context={
                'sub_tab': parameters.get('sub_tab'),
                'brand': request.visitor["base_brand"] if request else None,
                'request': request,
            }
        ).get_current_platform_page(influencer),
        'email': influencer.email,
        'has_artificial_blog_url': influencer.has_artificial_blog_url,
    })
    return res


def generic_post_feed(options, use_es=True):
    from debra.models import Posts
    
    request = options.get("request")

    try:
        brand = request.visitor["base_brand"]
    except Exception:
        brand = None

    search_query = query_from_request(request) if request else {}

    parameters = None

    for_brand = options.get("for_brand")
    for_influencer = options.get("for_influencer")
    with_parameters = options.get("with_parameters")
    preserve_order = options.get("preserve_order")
    platform_preference = options.get('platform_preference')
    with_post_ids = options.get("with_post_ids")
    all_platforms = options.get("all_platforms")
    for_multiple_influencers = options.get('for_multiple_influencers')
    for_user = options.get("for_user")
    refresh_cache = options.get("refresh_cache")
    limit_size = options.get("limit_size")
    prepare_pagination = options.get("prepare_pagination")

    platform = options.get("platform")
    if type(platform) is list:
        platform_q = Q(platform__platform_name__in=platform)
        platform_list = platform
    elif all_platforms:
        platform_q = Q()
        platform_list = []
    else:
        platform_q = Q(platform__platform_name=platform)
        platform_list = [platform]

    keyword_query = search_query.get('keyword')
    stype = search_query.get('stype')

    no_cache = True # options.get("no_cache")
    if stype and keyword_query:
        no_cache = True

    page_no = search_query.get(options.get("page_key"), 1)
    if for_user:
        data = cache.get("%s_%i_%s" % (options.get("cache_prefix"), for_user.id, page_no))
    elif for_influencer:
        data = cache.get("%s_inf_%i_%s" % (options.get("cache_prefix"), for_influencer.id, page_no))
    elif for_brand:
        data = cache.get("%s_brand_%i_%s" % (options.get("cache_prefix"), for_brand.id, page_no))
    else:
        if refresh_cache:
            data = None
        else:
            data = cache.get("%s_%s" % (options.get("cache_prefix"), page_no))

    if options.get('count_only'):
        page_size = 0
    else:
        page_size = options.get("page_size") if limit_size is None else limit_size

    if not data or not "results" in data or no_cache == True:
        today = datetime.datetime.today()
        posts = Posts.objects.select_related('platform', 'influencer__shelf_user__userprofile')
        posts = posts.prefetch_related('influencer__platform_set')
        if with_post_ids is None:
            posts = posts.filter(Q(create_date__isnull=True) | Q(create_date__lte=today))
            posts = posts.exclude(content='').exclude(content__isnull=True)
        posts = posts.filter(platform_q)

        total_hits = None

        if with_post_ids is not None:
            posts = posts.filter(id__in=with_post_ids)
            prepare_pagination = True
            use_es = False
        elif for_user:
            posts = posts.filter(
                influencer__shelf_user__userprofile=for_user,
            )
        elif for_influencer or for_multiple_influencers or with_parameters:
            if use_es:

                if with_parameters:
                    parameters = options.get('parameters')
                else:
                    parameters = {}
                if for_influencer or for_multiple_influencers:
                    parameters.update({
                        "influencer_ids": [for_influencer.id] if for_influencer else [
                            inf.id for inf in for_multiple_influencers],
                    })

                parameters['post_platform'] = platform_list

                if options.get('default_posts'):
                    parameters['default_posts'] = options.get('default_posts')

                if parameters.get('filters'):
                    if parameters.get('search_method') == 'r29':
                        parameters['filters']['tags'].append(constants.R29_CUSTOM_DATA_TAG_ID)
                    else:
                        parameters['filters']['exclude_tags'] = [constants.R29_CUSTOM_DATA_TAG_ID]

                post_ids, _, total_hits = elastic_search_helpers.es_post_query_runner_v2(parameters,
                                                                                         page_no-1,
                                                                                         page_size,
                                                                                         highlighted_first=False,
                                                                                         brand=brand)

                if settings.DEBUG:
                    print('FETCHED POST IDS: %s ' % post_ids)

                if options.get('count_only'):
                    return total_hits

                num_pages = int(math.ceil(float(total_hits) / page_size))
                posts = posts.filter(id__in=post_ids)
            else:
                pass
                # posts = posts.filter(
                #     influencer=for_influencer,
                # )
                # if options.get('count_only'):
                #     return posts.count()
        elif for_brand:
            if use_es:
                es_options = {
                    "post_brand": for_brand,
                    "post_platform": platform_list,
                    "exact": True,
                    "pagination": {
                        "number": page_no-1,
                        "size": page_size,
                    }
                }
                if options.get('count_only'):
                    es_options["pagination"] = {"size": 0}
                q, sc, total_hits = elastic_search_helpers.es_post_query_runner(es_options)
                if options.get('count_only'):
                    return total_hits
                num_pages = int(math.ceil(float(total_hits) / es_options["pagination"]["size"]))
                posts = posts.filter(q)
            else:
                pass
                # post_ids = post_ids_for_brand(platform_list, for_brand)
                # posts = posts.filter(id__in=post_ids).filter(influencer__show_on_search=True)
                # if options.get('count_only'):
                #     return posts.count()

        else:
            if use_es:
                es_options = build_options(keyword_query, stype)
                if es_options == None:
                    return {
                        'results': [],
                        'num_pages': 0
                    }
                es_options["post_platform"] = platform_list
                es_options["pagination"] = {
                    "number": page_no-1,
                    "size": page_size,
                }
                if options.get('count_only'):
                    es_options["pagination"] = {"size": 0}
                q, sc, total_hits = elastic_search_helpers.es_post_query_runner(es_options)
                if options.get('count_only'):
                    return total_hits
                num_pages = int(math.ceil(float(total_hits) / es_options["pagination"]["size"]))
                posts = posts.filter(q)
            else:
                pass
                # posts = posts.filter(
                #     admin_categorized=True,
                #     show_on_feed=True)
             
        posts = posts.exclude(platform__url_not_found=True)   

        if with_post_ids:
            if preserve_order:
                if type(preserve_order) == tuple:
                    posts = posts.order_by(*preserve_order)
                else:
                    post_objects = dict([(post.id, post) for post in posts])
                    posts = filter(
                        None, [post_objects.get(post_id) for post_id in with_post_ids])
                    total_hits = len(posts)
            elif platform_preference and type(platform_preference) in (list, tuple):
                total_hits = posts.count()
                case_statement = ['CASE']
                case_statement.extend([
                    "WHEN pl.platform_name='{}' THEN {}".format(pl, n)
                    for n, pl in enumerate(platform_preference)
                ])
                case_statement.extend([
                    'ELSE {}'.format(len(platform_preference) + 1),
                    'END'
                ])
                case_statement = '\n'.join(case_statement)
                posts = posts.extra(select={
                    'platform_order': '''
                        SELECT {case_statement}
                        FROM debra_platform AS pl
                        WHERE debra_posts.platform_id = pl.id
                    '''.format(case_statement=case_statement)
                }).order_by('platform_order', '-create_date')
            else:
                posts = posts.order_by('-create_date')
        else:
            posts = posts.order_by('-create_date')

        if total_hits is None:
            total_hits = posts.count()

        if use_es:
            page = posts
        else:
            if prepare_pagination:
                paginator = Paginator(posts, page_size)
            else:
                paginator = LazyPaginator(posts, page_size)
            try:
                page = paginator.page(page_no)
            except PageNotAnInteger:
                page = paginator.page(1)
            except EmptyPage:
                page = []
            num_pages = paginator.num_pages

        posts_data = []
        url_dups = set()
        for post in page:
            # Checking for duplicate post urls by removing http or www from the url
            # TODO: we should do this while saving the post also
            url_without_protocol = remove_protocol(post.url)
            url_without_www = remove_www(post.url)
            if post.url in url_dups or url_without_protocol in url_dups:
                continue
            if url_without_www and url_without_www in url_dups:
                continue
            url_dups.add(post.url)
            url_dups.add(url_without_protocol)
            if url_without_www:
                url_dups.add(url_without_www)

            content, imgs = tagStripper(post.content, length_limit=options.get("content_limit", 50))
            post_data = options.get("transform")(post, content, imgs)
            if not post_data:
                continue
            if brand and brand.flag_show_dummy_data:
                post_data['title'] = constants.FAKE_POST_DATA['title']
                post_data['url'] = constants.FAKE_POST_DATA['url']
            if post.create_date:
                post_data["create_date"] = post.create_date.strftime("%b. %e, %Y")
            if for_influencer:
                post_data['user'] = get_user_for_post(for_influencer, parameters, request=request)
            else:
                if post.influencer:
                    post_data['user'] = get_user_for_post(post.influencer, parameters, request=request)

            posts_data.append(post_data)
        print ("got posts_data so far")
        data = {
            'results': posts_data,
            'num_pages': num_pages,
            'total': total_hits,
            'slice_size': page_size
        }

        if page and no_cache != True:
            if for_user:
                cache.set("%s_%i_%s" % (options.get("cache_prefix"), for_user.id, page_no), data)
            elif for_influencer:
                cache.set("%s_inf_%i_%s" % (options.get("cache_prefix"), for_influencer.id, page_no), data)
            elif for_brand:
                cache.set("%s_brand_%i_%s" % (options.get("cache_prefix"), for_brand.id, page_no), data)
            else:
                cache.set("%s_%s" % (options.get("cache_prefix"), page_no), data)
    print ("everything done, now checking for posts data a bit more")
    if brand:
        faved_influencers = set(
            x[0] for x in brand.influencer_groups.values_list(
                'influencers_mapping__influencer__id')
        )

        post_collections = set(brand.created_post_analytics_collections.exclude(
            archived=True
        ).values_list('postanalytics__post_id', 'postanalytics__post_url'))
        post_ids = [x[0] for x in post_collections]
        post_urls = [x[1] for x in post_collections]

        for post_data in data["results"]:
            if post_data['user']["id"]:
                post_data["user"]["details_url"] = reverse('debra.search_views.blogger_info_json', args=(post_data['user']["id"],))
                if brand.stripe_plan in STRIPE_COLLECTION_PLANS:
                    post_data["user"]["can_favorite"] = True
                    post_data["user"]["is_favoriting"] = post_data['user']["id"] in faved_influencers
                else:
                    post_data["user"]["can_favorite"] = False
            # post_data['is_bookmarked'] = post_data['id'] in post_ids or\
            #     post_data['url'] in post_urls
            post_data['is_bookmarked'] = post_data['id'] in post_ids
        print("Done setting different flags for posts")
        search_helpers.set_influencer_collections(
            [x["user"] for x in data["results"] if x.get("user")],
            brand_id=request.visitor["base_brand"].id
        )
        print("Done setting collection flags")
        search_helpers.set_mailed_to_influencer(
            [x["user"] for x in data["results"] if x.get("user")],
            brand_id=request.visitor["base_brand"].id
        )
        print("Done setting mailed flag")
        search_helpers.set_influencer_invited_to(
            [x["user"] for x in data["results"] if x.get("user")],
            brand_id=request.visitor["base_brand"].id
        )
        print("Done setting invited flag")
    return data


def generic_product_feed(options):
    from debra.models import Posts, ProductModelShelfMap, Platform, UserProfile, Influencer, InfluencerCollaborations, ProductModel, Brands
    from debra.templatetags.custom_filters import remove_dot_com
    request = options.get("request")
    assert request

    try:
        brand = request.visitor["base_brand"]
    except Exception:
        brand = None

    search_query = query_from_request(request)

    parameters = None

    for_brand = options.get("for_brand")
    for_influencer = options.get("for_influencer")
    with_parameters = options.get("with_parameters")
    assert for_brand or for_influencer or with_parameters
    refresh_cache = options.get("refresh_cache")
    limit_size = options.get("limit_size")

    page_no = search_query.get(options.get("page_key"), 1)
    if for_influencer:
        data = cache.get("%s_inf_%i_%s" % (options.get("cache_prefix"), for_influencer.id, page_no))
    elif for_brand:
        data = cache.get("%s_brand_%i_%s" % (options.get("cache_prefix"), for_brand.id, page_no))
    else:
        if refresh_cache:
            data = None
        else:
            data = cache.get("%s_%s" % (options.get("cache_prefix"), page_no))

    if options.get('count_only'):
        page_size = 0
    else:
        page_size = options.get("page_size") if limit_size is None else limit_size

    if not data or not "results" in data or options.get("no_cache") == True:
        products = ProductModel.objects
        products = products.prefetch_related(
            'productmodelshelfmap_set__influencer__platform_set',
            'brand'
        )

        total_hits = None

        t = time.time()

        if with_parameters or for_influencer:
            if with_parameters:
                parameters = options.get("parameters")
            else:
                parameters = {}
            if for_influencer:
                parameters.update({
                    "influencer_ids": [for_influencer.id],
                })

            product_ids, _, total_hits = elastic_search_helpers.es_product_query_runner_v2(
                parameters, page_no-1, page_size)

            if settings.DEBUG:
                print('FETCHED PRODUCT IDS: %s ' % product_ids)

            if options.get('count_only'):
                return total_hits

            num_pages = int(math.ceil(float(total_hits) / page_size))
            products = products.filter(id__in=product_ids)
        elif for_brand:
            es_options = {
                "post_brand": for_brand,
                "pagination": {
                    "number": page_no-1,
                    "size": page_size,
                }
            }
            if options.get('count_only'):
                es_options["pagination"] = {"size": 0}
            q, sc, total_hits = elastic_search_helpers.es_product_query_runner(es_options)
            if options.get('count_only'):
                return total_hits
            num_pages = int(math.ceil(float(total_hits) / es_options["pagination"]["size"]))
            products = products.filter(q)

        products = products.order_by('-insert_date')

        print 'ES QUERY', time.time() - t

        t = time.time()

        page = list(products)

        print 'DB QUERY', time.time() - t

        products_data = []
        prod_model_existing = set()

        t = time.time()

        for product in page:
            try:
                pmsm = [p for p in product.productmodelshelfmap_set.all() if p.influencer][0]
            except IndexError:
                pmsm = None

            if product.name in prod_model_existing:
                continue
            prod_model_existing.add(product.name)
            product_data = {
                'id': product.id,
                'img_url_panel_view': product.img_url,
                'platform': PRODUCT_FEED_FILTER_KEY,
                'description': product.description != "Nil" and product.description or '',
                'url': pmsm and pmsm.affiliate_prod_link or product.prod_url,
            }
            if brand and brand.flag_show_dummy_data:
                product_data['url'] = constants.FAKE_BLOGGER_DATA['blog_url']
            product_data['brand_name'] = remove_dot_com(product.brand.name)
            if product.price:
                # bug
                product_data['price'] = product.saleprice
                product_data['orig_price'] = product.price
            if product.insert_date:
                product_data["create_date"] = product.insert_date.strftime("%b. %e, %Y")
            if for_influencer:
                product_data['user'] = get_user_for_post(for_influencer, parameters, request=request)
            else:
                profile = pmsm.influencer
                if profile:
                    product_data['user'] = get_user_for_post(profile, parameters, request=request)
            products_data.append(product_data)
        data = {
            'results': products_data,
            'num_pages': num_pages,
            'total': total_hits,
            'slice_size': page_size
        }
        if page and options.get("no_cache") != True:
            if for_influencer:
                cache.set("%s_inf_%i_%s" % (options.get("cache_prefix"), for_influencer.id, page_no), data)
            elif for_brand:
                cache.set("%s_brand_%i_%s" % (options.get("cache_prefix"), for_brand.id, page_no), data)

        print 'Serializing', time.time() - t

    t = time.time()

    brand = request.visitor["base_brand"]
    if brand:
        faved_influencers = set(x[0] for x in brand.influencer_groups.values_list('influencers_mapping__influencer__id'))
        for post_data in data["results"]:
            if 'user' in post_data and post_data['user']["id"]:
                post_data["user"]["details_url"] = reverse('debra.search_views.blogger_info_json', args=(post_data['user']["id"],))
                if brand.stripe_plan in STRIPE_COLLECTION_PLANS:
                    post_data["user"]["can_favorite"] = True
                    post_data["user"]["is_favoriting"] = post_data['user']["id"] in faved_influencers
                else:
                    post_data["user"]["can_favorite"] = False

        search_helpers.set_influencer_collections(
            [x["user"] for x in data["results"] if x.get("user")],
            brand_id=request.visitor["base_brand"].id
        )

        search_helpers.set_mailed_to_influencer(
            [x["user"] for x in data["results"] if x.get("user")],
            brand_id=request.visitor["base_brand"].id
        )

        search_helpers.set_influencer_invited_to(
            [x["user"] for x in data["results"] if x.get("user")],
            brand_id=request.visitor["base_brand"].id
        )

    print 'Final stage', time.time() - t

    return data


def instagram_feed_json_cacherefresh(request):
    from debra import helpers
    return helpers.render_data(lambda: instagram_feed_json(request, refresh_cache=True))

def instagram_feed_json(request, **kwargs):
    def instagram_transform(post, content, imgs):
        post_data = {
            'id': post.id,
            'post_image': post.post_image,
            'content': content,
            'url': post.url,
            'platform': INSTAGRAM_FEED_FILTER_KEY,
        }
        if not post.post_image:
            post_data["content_images"] = imgs
        elif post.post_image_width and post.post_image_height:
            post_data["post_image_dims"] = (post.post_image_width,\
                post.post_image_height)
        if kwargs.get('include_products', True) and post.products_json:
            post_data["products"] = post.get_product_json()
        else:
            post_data["products"] = []
        return post_data

    post = kwargs.get('for_single_post')
    if post is not None:
        content, imgs = tagStripper(
            post.content, length_limit=kwargs.get('length_limit'))
        return instagram_transform(post, content, imgs)

    options = {
        "request": request,
        # "count_only": count_only,
        # "for_user": for_user,
        # "refresh_cache": refresh_cache,
        # "for_influencer": for_influencer,
        # "for_brand": for_brand,
        # "prepare_pagination": prepare_pagination,
        # "limit_size": limit_size,
        # "no_cache": no_cache,
        "cache_prefix": INSTAGRAM_FEED_CACHE_PREFIX,
        "page_size": INSTAGRAM_FEED_PAGE_SIZE,
        "page_key": INSTAGRAM_FEED_PAGE_NO_KEY,
        "platform": "Instagram",
        "transform": instagram_transform
    }
    options.update(kwargs)
    if kwargs.get('only_options'):
        return options
    else:
        return generic_post_feed(options)


def youtube_feed_json_cacherefresh(request):
    from debra import helpers
    return helpers.render_data(lambda: youtube_feed_json(request, refresh_cache=True))

def youtube_feed_json(request, **kwargs):
    def youtube_transform(post, content, imgs):
        post_data = {
            'id': post.id,
            'post_image': post.post_image,
            'content': content,
            'url': post.url,
            'platform': YOUTUBE_FEED_FILTER_KEY,
        }
        if not post.post_image:
            post_data["content_images"] = imgs
        elif post.post_image_width and post.post_image_height:
            post_data["post_image_dims"] = (post.post_image_width,\
                post.post_image_height)
        if kwargs.get('include_products', True) and post.products_json:
            post_data["products"] = post.get_product_json()
        else:
            post_data["products"] = []
        return post_data

    post = kwargs.get('for_single_post')
    if post is not None:
        content, imgs = tagStripper(
            post.content, length_limit=kwargs.get('length_limit'))
        return youtube_transform(post, content, imgs)

    options = {
        "request": request,
        # "count_only": count_only,
        # "for_user": for_user,
        # "refresh_cache": refresh_cache,
        # "for_influencer": for_influencer,
        # "for_brand": for_brand,
        # "prepare_pagination": prepare_pagination,
        # "limit_size": limit_size,
        # "no_cache": no_cache,
        "cache_prefix": YOUTUBE_FEED_CACHE_PREFIX,
        "page_size": YOUTUBE_FEED_PAGE_SIZE,
        "page_key": YOUTUBE_FEED_PAGE_NO_KEY,
        "platform": "Youtube",
        "transform": youtube_transform
    }
    options.update(kwargs)
    if kwargs.get('only_options'):
        return options
    else:
        return generic_post_feed(options)

def product_feed_json_cacherefresh(request):
    from debra import helpers
    return helpers.render_data(lambda: product_feed_json(request, refresh_cache=True))

# def product_feed_json(request, for_user=None, user_is_brand=False,\
#     refresh_cache=False, shelf=None, for_influencer=None, for_brand=None,\
#     prepare_pagination=False, limit_size=None, no_cache=False, count_only=False):
def product_feed_json(request, **kwargs):
    from debra.models import Posts, ProductModelShelfMap, Platform, UserProfile, Influencer, InfluencerCollaborations, ProductModel, Brands
    options = {
        "request": request,
        "cache_prefix": PRODUCT_FEED_CACHE_PREFIX,
        "page_size": PRODUCT_FEED_PAGE_SIZE,
        "page_key": PRODUCT_FEED_PAGE_NO_KEY,
        # "count_only": kw.get('count_only'),
        # "for_user": for_user,
        # "refresh_cache": refresh_cache,
        # "for_influencer": for_influencer,
        # "for_brand": for_brand,
        # "prepare_pagination": prepare_pagination,
        # "limit_size": limit_size,
        # "no_cache": no_cache,
    }
    options.update(kwargs)
    return generic_product_feed(options)


def blog_feed_json_cacherefresh(request, limit_size=None, no_cache=False, count_only=False):
    from debra import helpers
    return helpers.render_data(lambda: blog_feed_json(request, refresh_cache=True))

def blog_feed_json(request, for_user=None, refresh_cache=False, for_influencer=None, for_brand=None, sponsored_only=False, prepare_pagination=False, limit_size=None, no_cache=False):
    from debra.models import (Posts, ProductModelShelfMap, Platform,\
        UserProfile, Influencer, InfluencerCollaborations, ProductModel, Brands)

    try:
        search_query = json.loads(request.body)
    except:
        search_query = {}

    page_no = search_query.get(BLOG_FEED_PAGE_NO_KEY, 1)

    #keyword query
    keyword_query = search_query.get('keyword')
    #type of keyword query
    stype = search_query.get('stype')
    #check if we filter by influencers
    influencer_filters = search_query.get('filters')
    content_filter = search_query.get('filter', 'blog')

    brand = request.visitor["base_brand"]
    today = datetime.datetime.today()
    select_related = ['influencer']

    #forming basic posts query
    posts = Posts.objects.all()
    posts = posts.filter(Q(create_date__isnull=True) | Q(create_date__lte=today))
    if sponsored_only:
        posts = posts.filter(is_sponsored=True)
    if for_user:
        posts = posts.filter(
            influencer__shelf_user__userprofile=for_user,
            platform_name__in=Platform.BLOG_PLATFORMS,
        )
    elif for_influencer:
        posts = posts.filter(
            influencer=for_influencer,
            platform_name__in=Platform.BLOG_PLATFORMS,
        )
    elif for_brand:
        options = {
            "post_brand": for_brand,
            "exact": True
        }
        q = elastic_search_helpers.es_post_query_runner(options)[0]
        posts = posts.filter(q)
    else:
        posts = posts.filter(
            influencer__show_on_search=True,
            influencer__profile_pic_url__isnull=False,
            #platform_name__in=Platform.BLOG_PLATFORMS,
        )

    # if we filter by influencer we setup post_influencers_ids
    if influencer_filters and request.user.is_authenticated():
        influencers = Influencer.objects.filter(
            show_on_search=True,
            average_num_comments_per_post__gte=5,
        )
        if brand and brand.is_subscribed:
            plan_name = brand.stripe_plan
        else:
            plan_name = None
        search_query = search_helpers.query_from_request(request)
        influencers, _ = search_helpers.filter_blogger_results(search_query, influencers)
        inf_ids = [x['id'] for x in influencers.only('id').values('id')]
        posts = posts.filter(influencer__id__in=inf_ids)

    if stype == "keyword":
        options = {
            "post_content_title": keyword_query
        }
    elif stype == "brand":
        if type(keyword_query) == dict:
            keyword_query = keyword_query.get('value')
        domain = domain_from_url(keyword_query)
        try:
            brand = Brands.objects.get(domain_name=domain)
        except:
            return {
               'results': [],
               'num_pages': 0
            }
        options = {
            "post_brand": brand,
            "exact": True
        }
    elif stype == "name":
        options = {
            "blogger_name": keyword_query
        }
    elif stype == "blogname":
        options = {
            "blog_name": keyword_query
        }
    elif stype == "blogurl":
        options = {
            "blog_url": keyword_query
        }
    elif stype == "location":
        options = {
            "location": keyword_query
        }
    elif stype == "all":
        domain = domain_from_url(keyword_query)
        try:
            brand = Brands.objects.get(blacklisted=False, domain_name=domain)
        except:
            brand = None
        options = {
            "blog_url": keyword_query,
            "blog_name": keyword_query,
            "blogger_name": keyword_query,
            "post_content_title": keyword_query,
            "blog_url": keyword_query,
            "location": keyword_query,
        }
        if brand:
            options["post_brand"] = brand,
    else:
        options = {}
    options["pagination"] = {
        "number": page_no-1,
        "size": BLOG_FEED_PAGE_SIZE if limit_size is None else limit_size,
    }
    q, sc, total_hits = elastic_search_helpers.es_post_query_runner(options)
    num_pages = int(math.ceil(float(total_hits) / options["pagination"]["size"]))
    posts = posts.filter(q)
    posts_ids = [x[0] for x in posts.only('id').values_list('id')]
    score_mapping = sc

    # getting actual data for paginated posts
    posts_data = []
    posts = Posts.objects.select_related(*select_related)
    posts = posts.prefetch_related('influencer__platform_set', 'influencer__shelf_user__userprofile')
    posts = posts.filter(id__in=posts_ids)
    if keyword_query and stype in ('all', 'keyword', 'brand', 'name', 'blogname', 'blogurl', 'location'):
        posts = list(posts)
        posts.sort(key=lambda x: -score_mapping.get(x.id, 0))
    else:
        posts = posts.order_by('-create_date')

    #serializing posts
    posts_url = set()
    for post in posts:
        if post.url in posts_url:
            continue
        posts_url.add(post.url)
        content, images = search_helpers.tagStripper(post.content)
        # stripped = re.sub(
        #     r'<script(?:\s[^>]*)?(>(?:.(?!/script>))*</script>|/>)', '', content, flags=re.S)
        post_data = {}
        post_data["id"] = post.id
        if keyword_query:
            post_data["score"] = score_mapping.get(post.id, 0)
        post_data["url"] = post.url
        post_data["title"] = post.title
        post_data["post_image"] = post.post_image
        post_data["content"] = content
        if not post.post_image:
            post_data["content_images"] = images
        elif post.post_image_width and post.post_image_height:
            post_data["post_image_dims"] = (post.post_image_width, post.post_image_height)

        if post.create_date:
            post_data["create_date"] = post.create_date.strftime("%b. %e, %Y")
        post_data['platform'] = BLOG_FEED_FILTER_KEY
        if post.products_json:
            post_data["products"] = post.get_product_json()
        else:
            post_data["products"] = []

        influencer = post.influencer
        post_data['user'] = influencer.feed_stamp
        posts_data.append(post_data)
    data = {
        'results': posts_data,
        'num_pages': num_pages
    }
    if brand:
        faved_influencers = set(x[0] for x in brand.influencer_groups.values_list('influencers_mapping__influencer__id'))
        for post_data in data['results']:
            post_data["user"]["details_url"] = reverse('debra.search_views.blogger_info_json', args=(post_data['user']["id"],))
            if brand.stripe_plan in STRIPE_COLLECTION_PLANS:
                post_data["user"]["can_favorite"] = True
                post_data["user"]["is_favoriting"] = post_data['user']["id"] in faved_influencers
            else:
                post_data["user"]["can_favorite"] = False
    return data


def blog_feed_json_dashboard(request, **kwargs):
    def transform(post, content, imgs):
        post_data = {
            "id": post.id,
            "url": post.url,
            "title": post.title,
            "post_image": post.post_image,
            "content": content,
            "platform": BLOG_FEED_FILTER_KEY,
        }
        if not post.post_image:
            post_data["content_images"] = imgs
        elif post.post_image_width and post.post_image_height:
            post_data["post_image_dims"] = (post.post_image_width,\
                post.post_image_height)
        if kwargs.get('include_products', True) and post.products_json:
            post_data["products"] = post.get_product_json()
        else:
            post_data["products"] = []
        return post_data

    post = kwargs.get('for_single_post')
    if post is not None:
        content, imgs = tagStripper(
            post.content, length_limit=kwargs.get('length_limit'))
        return transform(post, content, imgs)

    options = {
        "request": request,
        # "count_only": count_only,
        # "for_user": None,
        # "refresh_cache": False,
        # "for_influencer": for_influencer,
        # "for_brand": for_brand,
        # "prepare_pagination": prepare_pagination,
        # "limit_size": limit_size,
        # "no_cache": no_cache,
        "cache_prefix": BLOG_FEED_CACHE_PREFIX,
        "page_size": BLOG_FEED_PAGE_SIZE,
        "page_key": BLOG_FEED_PAGE_NO_KEY,
        "platform": ['Blogspot', 'Wordpress', 'Custom', 'Tumblr', 'Squarespace', ],
        "transform": transform
    }
    options.update(kwargs)
    if kwargs.get('only_options'):
        return options
    else:
        return generic_post_feed(options)


def facebook_feed_json(request, **kwargs):
    def transform(post, content, imgs):
        post_data = {
            "id": post.id,
            "url": post.url,
            "title": post.title,
            "post_image": post.post_image,
            "content": content,
            "platform": 'facebook',
        }
        if not post.post_image:
            post_data["content_images"] = imgs
        elif post.post_image_width and post.post_image_height:
            post_data["post_image_dims"] = (post.post_image_width,\
                post.post_image_height)
        if kwargs.get('include_products', True) and post.products_json:
            post_data["products"] = post.get_product_json()
        else:
            post_data["products"] = []
        return post_data

    post = kwargs.get('for_single_post')
    if post is not None:
        content, imgs = tagStripper(
            post.content, length_limit=kwargs.get('length_limit'))
        return transform(post, content, imgs)

    options = {
        "request": request,
        # "count_only": count_only,
        # "for_user": None,
        # "refresh_cache": False,
        # "for_influencer": for_influencer,
        # "for_brand": for_brand,
        # "prepare_pagination": prepare_pagination,
        # "limit_size": limit_size,
        # "no_cache": no_cache,
        "cache_prefix": BLOG_FEED_CACHE_PREFIX,
        "page_size": BLOG_FEED_PAGE_SIZE,
        "page_key": FACEBOOK_FEED_PAGE_NO_KEY,
        "platform": ['Facebook'],
        "transform": transform
    }
    options.update(kwargs)
    if kwargs.get('only_options'):
        return options
    else:
        return generic_post_feed(options)


def collab_feed_json(request, for_influencer=None, for_brand=None, prepare_pagination=False, limit_size=None, no_cache=False, count_only=False):
    from debra.models import Posts, ProductModelShelfMap, Platform, UserProfile, Influencer, InfluencerCollaborations, ProductModel, Brands

    try:
        search_query = json.loads(request.body)
    except:
        search_query = {}

    page_no = search_query.get(COLLABS_FEED_PAGE_NO_KEY, 1)

    brand = request.visitor["base_brand"]
    if for_influencer:
        data = cache.get("%s_inf_%i_%s" % (COLLABS_FEED_CACHE_PREFIX, for_influencer.id, page_no))
    elif for_brand:
        data = cache.get("%s_brand_%i_%s" % (COLLABS_FEED_CACHE_PREFIX, for_brand.id, page_no))
    else:
        data = cache.get("%s_%s" % (COLLABS_FEED_CACHE_PREFIX, page_no))

    if not data or not "results" in data or no_cache:
        today = datetime.datetime.today()
        select_related = ['influencer']

        collabs = InfluencerCollaborations.objects.all()
        if for_influencer:
            collabs = collabs.filter(
                influencer=for_influencer,
            )
        elif for_brand:
            collabs = collabs.filter(
                brand_name=for_brand.name,
            )
        paginator = Paginator(collabs, COLLABS_FEED_PAGE_SIZE if limit_size is None else limit_size)
        # if prepare_pagination:
        #     paginator = Paginator(collabs, COLLABS_FEED_PAGE_SIZE if limit_size is None else limit_size)
        # else:
        #     paginator = LazyPaginator(collabs, COLLABS_FEED_PAGE_SIZE if limit_size is None else limit_size)
        try:
            page = paginator.page(page_no)
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = []
        num_pages = paginator.num_pages

        collabs_data = []
        for collab in page:
            collab_data = {}
            collab_data["id"] = collab.id
            collab_data["url"] = collab.post_url
            collab_data['platform'] = COLLABS_FEED_FILTER_KEY
            collab_data['details'] = collab.details
            if collab.timestamp:
                collab_data['timestamp'] = collab.timestamp.strftime("%b. %e, %Y")
            collab_data['brand_name'] = collab.brand_name
            collab_data['collab_type'] = dict(InfluencerCollaborations.COLLABORATION_TYPES).get(collab.collaboration_type)
            influencer = collab.influencer
            collab_data['user'] = influencer.feed_stamp
            collabs_data.append(collab_data)
        if page and not no_cache:
            if for_influencer:
                cache.set("%s_inf_%i_%s" % (COLLABS_FEED_CACHE_PREFIX, for_influencer.id, page.number), collabs_data)
            elif for_brand:
                cache.set("%s_brand_%i_%s" % (COLLABS_FEED_CACHE_PREFIX, for_brand.id, page.number), collabs_data)
            else:
                cache.set("%s_%s" % (COLLABS_FEED_CACHE_PREFIX, page.number), collabs_data)
        data = {
            'results': collabs_data,
            'num_pages': num_pages
        }
    if brand:
        faved_influencers = set(x[0] for x in brand.influencer_groups.values_list('influencers_mapping__influencer__id'))
        for collab_data in data["results"]:
            collab_data["user"]["details_url"] = reverse('debra.search_views.blogger_info_json', args=(collab_data['user']["id"],))
            if brand.stripe_plan in STRIPE_COLLECTION_PLANS:
                collab_data["user"]["can_favorite"] = True
                collab_data["user"]["is_favoriting"] = collab_data['user']["id"] in faved_influencers
            else:
                collab_data["user"]["can_favorite"] = False
    return data


def twitter_feed_json(request, **kwargs):
    handle_re = re.compile("twitter.com\/([A-Za-z0-9_]{1,15})")
    tweet_id_re = re.compile("status\/(\d+)")

    def transform(post, content, imgs):
        platform = post.platform
        handles = handle_re.findall(platform.url)
        tweet_ids = tweet_id_re.findall(post.url)
        if not handles or not tweet_ids:
            return None
        post_data = {
            'id': post.id,
            'tweet_id': tweet_ids[0],
            'content': post.content,
            'post_image': post.post_image,
            'handle': handles[0],
            'url': post.url,
            'platform': TWITTER_FEED_FILTER_KEY,
        }
        if not post.post_image:
            post_data["post_image"] = imgs and imgs[0] or None
        elif post.post_image_width and post.post_image_height:
            post_data["post_image_dims"] = (post.post_image_width, post.post_image_height)
        if kwargs.get('include_products', True) and post.products_json:
            post_data["products"] = post.get_product_json()
        else:
            post_data["products"] = []
        return post_data

    post = kwargs.get('for_single_post')
    if post is not None:
        content, imgs = tagStripper(
            post.content, length_limit=kwargs.get('length_limit'))
        return transform(post, content, imgs)

    options = {
        "request": request,
        # "count_only": count_only,
        # "for_user": for_user,
        # "refresh_cache": refresh_cache,
        # "for_influencer": for_influencer,
        # "for_brand": for_brand,
        # "prepare_pagination": prepare_pagination,
        # "limit_size": limit_size,
        # "no_cache": no_cache,
        "cache_prefix": TWITTER_FEED_CACHE_PREFIX,
        "page_size": TWITTER_FEED_PAGE_SIZE,
        "page_key": TWITTER_FEED_PAGE_NO_KEY,
        "platform": "Twitter",
        "transform": transform
    }
    options.update(kwargs)
    if kwargs.get('only_options'):
        return options
    else:
        return generic_post_feed(options)


def all_feed_json(request, **kwargs):

    def transform(post, content, imgs):
        platform = post.platform
        feed_json = get_feed_handler_for_platform(platform.platform_name)
        post_options = feed_json(request, only_options=True, **kwargs)
        return post_options.get('transform')(post, content, imgs)

    options = {
        "request": request,
        # "count_only": count_only,
        # "for_user": for_user,
        # "refresh_cache": refresh_cache,
        # "for_influencer": for_influencer,
        # "for_brand": for_brand,
        # "prepare_pagination": prepare_pagination,
        # "limit_size": limit_size,
        # "no_cache": no_cache,
        "cache_prefix": 'ALL',
        'all_platforms': True,
        # "page_size": TWITTER_FEED_PAGE_SIZE,
        "page_key": 'pageAll',
        # "platform": "Twitter",
        "transform": transform
    }
    options.update(kwargs)
    if kwargs.get('only_options'):
        return options
    else:
        return generic_post_feed(options)


def pinterest_feed_json(request, **kwargs):
    handle_re = re.compile("pinterest.com\/([A-Za-z0-9_]{1,15})")
    pin_id_re = re.compile("pin\/(\d+)")

    def transform(post, content, imgs):
        platform = post.platform
        handles = handle_re.findall(platform.url)
        pin_ids = pin_id_re.findall(post.url)
        if not handles or not pin_ids:
            return
        post_data = {
            'id': post.id,
            'pin_id': pin_ids[0],
            'pins': platform.avg_numshares_overall,
            'likes': platform.avg_numlikes_overall,
            'followers': platform.num_followers,
            'coms': platform.avg_numcomments_overall,
            'content': content,
            'handle': handles[0],
            'post_pic': post.post_image,
            'url': post.url,
            'platform': PINTEREST_FEED_FILTER_KEY,
        }
        if not post.post_image:
            post_data["post_pic"] = imgs and imgs[0] or None
        elif post.post_image_width and post.post_image_height:
            post_data["post_image_dims"] = (post.post_image_width, post.post_image_height)
        if kwargs.get('include_products', True) and post.products_json:
            post_data["products"] = post.get_product_json()
        else:
            post_data["products"] = []

        return post_data

    post = kwargs.get('for_single_post')
    if post is not None:
        content, imgs = tagStripper(
            post.content, length_limit=kwargs.get('length_limit'))
        return transform(post, content, imgs)

    options = {
        "request": request,
        # "count_only": count_only,
        # "for_user": for_user,
        # "refresh_cache": refresh_cache,
        # "for_influencer": for_influencer,
        # "for_brand": for_brand,
        # "prepare_pagination": prepare_pagination,
        # "limit_size": limit_size,
        # "no_cache": no_cache,
        "cache_prefix": PINTEREST_FEED_CACHE_PREFIX,
        "page_size": PINTEREST_FEED_PAGE_SIZE,
        "page_key": PINTEREST_FEED_PAGE_NO_KEY,
        "platform": "Pinterest",
        "transform": transform,
        "content_limit": 200,
    }
    options.update(kwargs)
    if kwargs.get('only_options'):
        return options
    else:
        return generic_post_feed(options)


FEED_HANDLERS = {}

FEED_HANDLERS[INSTAGRAM_FEED_FILTER_KEY] = instagram_feed_json
FEED_HANDLERS[PRODUCT_FEED_FILTER_KEY] = product_feed_json
FEED_HANDLERS[BLOG_FEED_FILTER_KEY] = blog_feed_json_dashboard
FEED_HANDLERS[COLLABS_FEED_FILTER_KEY] = collab_feed_json
FEED_HANDLERS[TWITTER_FEED_FILTER_KEY] = twitter_feed_json
FEED_HANDLERS[PINTEREST_FEED_FILTER_KEY] = pinterest_feed_json
FEED_HANDLERS[YOUTUBE_FEED_FILTER_KEY] = youtube_feed_json
FEED_HANDLERS[FACEBOOK_FEED_FILTER_KEY] = facebook_feed_json
FEED_HANDLERS[ALL_FEED_FILTER_KEY] = all_feed_json

PLATFORM_2_KEY_MAPPING = {
    'Instagram': INSTAGRAM_FEED_FILTER_KEY,
    'Twitter': TWITTER_FEED_FILTER_KEY,
    'Pinterest': PINTEREST_FEED_FILTER_KEY,
    'Youtube': YOUTUBE_FEED_FILTER_KEY,
    'Facebook': FACEBOOK_FEED_FILTER_KEY,
    'Blog': BLOG_FEED_FILTER_KEY,
    'All': ALL_FEED_FILTER_KEY,
}

def platform_name_2_filter_key(platform_name):
    return PLATFORM_2_KEY_MAPPING.get(platform_name or 'All', BLOG_FEED_FILTER_KEY)

def get_feed_handler_for_platform(platform_name):
    return FEED_HANDLERS.get(platform_name_2_filter_key(platform_name))

def normalize_posts_section_name(section_name='all'):
    if section_name.lower() in ['blog_posts', 'posts', 'blog']:
        return 'blog_posts'
    elif section_name.lower() in ['instagrams', 'photos', 'instagram']:
        return 'instagrams'
    elif section_name.lower() in ['tweets', 'twitter', 'tweet']:
        return 'tweets'
    elif section_name.lower() in ['pins', 'pinterest', 'pin']:
        return 'pins'
    elif section_name.lower() in ['facebook']:
        return 'facebook'
    elif section_name.lower() in ['youtube', 'video', 'videos']:
        return 'youtube'
    elif section_name.lower() in ['product', 'products', 'item', 'items']:
        return 'products'
    return 'all'

def normalize_feed_key(feed_key='all'):
    if feed_key.lower() in ['blog_posts', 'posts', 'blog']:
        return BLOG_FEED_FILTER_KEY
    elif feed_key.lower() in ['instagrams', 'photos', 'instagram']:
        return INSTAGRAM_FEED_FILTER_KEY
    elif feed_key.lower() in ['tweets', 'twitter', 'tweet']:
        return TWITTER_FEED_FILTER_KEY
    elif feed_key.lower() in ['pins', 'pinterest', 'pin']:
        return PINTEREST_FEED_FILTER_KEY
    elif feed_key.lower() in ['facebook']:
        return FACEBOOK_FEED_FILTER_KEY
    elif feed_key.lower() in ['youtube', 'video', 'videos']:
        return YOUTUBE_FEED_FILTER_KEY
    elif feed_key.lower() in ['product', 'products', 'item', 'items']:
        return PRODUCT_FEED_FILTER_KEY
    return 'all'

def get_feed_handler(feed_key='all'):
    return FEED_HANDLERS.get(normalize_feed_key(feed_key))
