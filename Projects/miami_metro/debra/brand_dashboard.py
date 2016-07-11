# -*- coding: utf-8 -*-
import json
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, HttpResponse, HttpResponseBadRequest, Http404, QueryDict
from debra.constants import STRIPE_PLAN_STARTUP, STRIPE_PLAN_CHEAP, STRIPE_PLAN_BASIC, STRIPE_COLLECTION_PLANS, STRIPE_ANALYTICS_PLANS
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.urlresolvers import reverse
from debra import models
from debra import serializers
from debra import search_helpers
from debra import feeds_helpers
from debra import mongo_utils
from debra import brand_helpers
from debra.decorators import brand_view
from bson import json_util


def summary_page(request):
    brand = request.visitor["brand"]

    if request.is_ajax():
        try:
            search_query = json.loads(request.body)
        except ValueError:
            search_query = {}

        if search_query.get('filter') == feeds_helpers.BLOG_FEED_FILTER_KEY:
            data = feeds_helpers.blog_feed_json_dashboard(request, for_brand=brand, limit_size=3)

        if search_query.get('filter') == feeds_helpers.PRODUCT_FEED_FILTER_KEY:
            data = feeds_helpers.product_feed_json(request, for_brand=brand, limit_size=3)

        if search_query.get('filter') == feeds_helpers.INSTAGRAM_FEED_FILTER_KEY:
            data = feeds_helpers.instagram_feed_json(request, for_brand=brand, limit_size=3)

        if search_query.get('filter') == feeds_helpers.PINTEREST_FEED_FILTER_KEY:
            data = feeds_helpers.pinterest_feed_json(request, for_brand=brand, limit_size=3)

        if search_query.get('filter') == feeds_helpers.TWITTER_FEED_FILTER_KEY:
            data = feeds_helpers.twitter_feed_json(request, for_brand=brand, limit_size=3)

        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        context = {
            "brand": brand,
        }
        return render(request, 'pages/brand_dashboard/summary_page.html', context)


def dashboard_charts(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")


    competitors = brand.competitors.all()

    collection = mongo_utils.get_brands_stats_col()

    brand_data = json_util.dumps(collection.find({"brand_id": brand.id}))

    context = {
        'selected_tab': 'dashboard',
        'sub_page': 'charts',
        'brand_data': brand_data,
        'competitors_data': [],
    }
    return render(request, 'pages/brand_dashboard/charts.html', context)


def mentioning_influencers(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")


    context = {
        'selected_tab': 'dashboard',
        'sub_page': 'mentions_influencers',
    }
    return render(request, 'pages/brand_dashboard/bm_influencers.html', context)


def mentioning_posts(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    rq_debug = request.GET.get('debug') != None
    if request.is_ajax() or rq_debug:
        try:
            search_query = json.loads(request.body)
        except ValueError:
            search_query = {}
        brand_domain = search_query.get("keyword", brand.domain_name)
        if rq_debug:
            brand_domain="zappos.com"
        possible_brands = list(models.Brands.objects.filter(domain_name=brand_domain, blacklisted=False).only('id', 'products_count').values('id', 'products_count'))
        if possible_brands:
            possible_brands.sort(key=lambda x: -x["products_count"])
            for_brand = models.Brands.objects.get(id=possible_brands[0]["id"])
        else:
            for_brand = brand
        data = feeds_helpers.blog_feed_json_dashboard(request, for_brand=for_brand, prepare_pagination=False)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        if rq_debug:
            return HttpResponse("<body>%s</body>" % data)
        else:
            return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_dashboard/bm_posts.html', {
            'selected_tab': 'dashboard',
            'sub_page': 'mentions_posts',
        })

def mentioning_posts_sponsored(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    rq_debug = request.GET.get('debug') != None
    if request.is_ajax() or rq_debug:
        try:
            search_query = json.loads(request.body)
        except ValueError:
            search_query = {}
        brand_domain = search_query.get("keyword", brand.domain_name)
        if rq_debug:
            brand_domain="zappos.com"
        possible_brands = list(models.Brands.objects.filter(domain_name=brand_domain, blacklisted=False).only('id', 'products_count').values('id', 'products_count'))
        if possible_brands:
            possible_brands.sort(key=lambda x: -x["products_count"])
            for_brand = models.Brands.objects.get(id=possible_brands[0]["id"])
        else:
            for_brand = brand
        data = feeds_helpers.collab_feed_json(request, for_brand=for_brand, prepare_pagination=False)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        if rq_debug:
            return HttpResponse("<body>%s</body>" % data)
        else:
            return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_dashboard/bm_posts_sponsored.html', {
            'selected_tab': 'dashboard',
            'sub_page': 'mentions_posts_sponsored',
        })

def mentioning_photos(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    rq_debug = request.GET.get('debug') != None
    if request.is_ajax() or rq_debug:
        try:
            search_query = json.loads(request.body)
        except ValueError:
            search_query = {}
        brand_domain = search_query.get("keyword", brand.domain_name)
        if rq_debug:
            brand_domain="zappos.com"
        possible_brands = list(models.Brands.objects.filter(domain_name=brand_domain, blacklisted=False).only('id', 'products_count').values('id', 'products_count'))
        if possible_brands:
            possible_brands.sort(key=lambda x: -x["products_count"])
            for_brand = models.Brands.objects.get(id=possible_brands[0]["id"])
        else:
            for_brand = brand
        data = feeds_helpers.instagram_feed_json(request, for_brand=for_brand, prepare_pagination=False)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        if rq_debug:
            return HttpResponse("<body>%s</body>" % data)
        else:
            return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_dashboard/bm_photos.html', {
            'selected_tab': 'dashboard',
            'sub_page': 'mentions_photos',
        })

def mentioning_products(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    rq_debug = request.GET.get('debug') != None
    if request.is_ajax() or rq_debug:
        try:
            search_query = json.loads(request.body)
        except ValueError:
            search_query = {}
        brand_domain = search_query.get("keyword", brand.domain_name)
        if rq_debug:
            brand_domain="zappos.com"
        possible_brands = list(models.Brands.objects.filter(domain_name=brand_domain, blacklisted=False).only('id', 'products_count').values('id', 'products_count'))
        if possible_brands:
            possible_brands.sort(key=lambda x: -x["products_count"])
            for_brand = models.Brands.objects.get(id=possible_brands[0]["id"])
        else:
            for_brand = brand
        print for_brand
        data = feeds_helpers.product_feed_json(request, for_brand=for_brand, prepare_pagination=False)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        # f = open('/home/walrus/Desktop/feed.json', 'wb')
        # f.write(data)
        # f.close()
        if rq_debug:
            return HttpResponse("<body>%s</body>" % data)
        else:
            return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_dashboard/bm_products.html', {
            'selected_tab': 'dashboard',
            'sub_page': 'mentions_products',
        })


def mentioning_tweets(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    rq_debug = request.GET.get('debug') != None
    if request.is_ajax() or rq_debug:
        try:
            search_query = json.loads(request.body)
        except ValueError:
            search_query = {}
        brand_domain = search_query.get("keyword", brand.domain_name)
        if rq_debug:
            brand_domain="zappos.com"
        possible_brands = list(models.Brands.objects.filter(domain_name=brand_domain, blacklisted=False).only('id', 'products_count').values('id', 'products_count'))
        if possible_brands:
            possible_brands.sort(key=lambda x: -x["products_count"])
            for_brand = models.Brands.objects.get(id=possible_brands[0]["id"])
        else:
            for_brand = brand
        data = feeds_helpers.twitter_feed_json(request, for_brand=for_brand, prepare_pagination=False)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        if rq_debug:
            return HttpResponse("<body>%s</body>" % data)
        else:
            return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_dashboard/bm_tweets.html', {
            'selected_tab': 'dashboard',
            'sub_page': 'mentions_tweets',
        })


def mentioning_pins(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    rq_debug = request.GET.get('debug') != None
    if request.is_ajax() or rq_debug:
        try:
            search_query = json.loads(request.body)
        except ValueError:
            search_query = {}
        brand_domain = search_query.get("keyword", brand.domain_name)
        if rq_debug:
            brand_domain="zappos.com"
        possible_brands = list(models.Brands.objects.filter(domain_name=brand_domain, blacklisted=False).only('id', 'products_count').values('id', 'products_count'))
        if possible_brands:
            possible_brands.sort(key=lambda x: -x["products_count"])
            for_brand = models.Brands.objects.get(id=possible_brands[0]["id"])
        else:
            for_brand = brand
        data = feeds_helpers.pinterest_feed_json(request, for_brand=for_brand, prepare_pagination=False)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        if rq_debug:
            return HttpResponse("<body>%s</body>" % data)
        else:
            return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_dashboard/bm_pins.html', {
            'selected_tab': 'dashboard',
            'sub_page': 'mentions_pins',
        })


def save_competitor(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    try:
        query = json.loads(request.body)
    except ValueError:
        query = {}

    brand_domain = query.get("competitor")
    if not brand_domain:
        return HttpResponseBadRequest()

    possible_brands = list(models.Brands.objects.filter(domain_name=brand_domain, blacklisted=False).only('id', 'products_count').values('id', 'products_count'))
    if possible_brands:
        possible_brands.sort(key=lambda x: -x["products_count"])
        for_brand = models.Brands.objects.get(id=possible_brands[0]["id"])
    else:
        return HttpResponseBadRequest()

    competitor = models.BrandSavedCompetitors()
    competitor.brand = brand
    competitor.competitor = for_brand
    competitor.save()
    return HttpResponse()


def dashboard_competitors_charts(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")


    competitors = brand.competitors.all()
    collection = mongo_utils.get_brands_stats_col()

    tmp_data = {}
    keys = []
    labels = []
    competitors_data = {
        "data": {}
    }

    for competitor in competitors:
        keys.append(competitor.competitor.id)
        labels.append(competitor.competitor.name)
        stats = collection.find({"brand_id": competitor.competitor.id})
        for stat in stats:
            key = "%s_%s" % (stat["metric"], stat["type"])
            if not key in tmp_data:
                tmp_data[key] = {}
            for sample in stat["samples"]:
                if not sample["ts"] in tmp_data[key]:
                    tmp_data[key][sample["ts"]] = {}
                tmp_data[key][sample["ts"]][stat["brand_id"]] = sample["v"]

    for key, values in tmp_data.iteritems():
        competitors_data["data"][key] = []
        for ts, value in values.iteritems():
            sample = {
                "ts": ts * 1000
            }
            for b_id in keys:
                sample[str(b_id)] = value.get(b_id, None)
            competitors_data["data"][key].append(sample)

    competitors_data["keys"] = keys
    competitors_data["labels"] = labels

    context = {
        'selected_tab': 'competitors',
        'sub_page': 'c_charts',
        'types': ['Twitter', 'Facebook', 'Instagram', 'Pinterest', 'Wordpress', 'Blogspot', 'Custom'],
        'brand_data': [],
        'competitors_data': json.dumps(competitors_data),
    }
    return render(request, 'pages/brand_dashboard/charts.html', context)


def mentioning_competitors_influencers(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")


    context = {
        'selected_tab': 'competitors',
        'sub_page': 'c_mentions_influencers',
    }
    return render(request, 'pages/brand_dashboard/bm_influencers.html', context)


def mentioning_competitors_posts(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    return render(request, 'pages/brand_dashboard/bm_posts.html', {
        'selected_tab': 'competitors',
        'sub_page': 'c_mentions_posts',
    })

def mentioning_competitors_posts_sponsored(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    return render(request, 'pages/brand_dashboard/bm_posts_sponsored.html', {
        'selected_tab': 'competitors',
        'sub_page': 'c_mentions_posts_sponsored',
    })

def mentioning_competitors_photos(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    return render(request, 'pages/brand_dashboard/bm_photos.html', {
        'selected_tab': 'competitors',
        'sub_page': 'c_mentions_photos',
    })

def mentioning_competitors_products(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    return render(request, 'pages/brand_dashboard/bm_products.html', {
        'selected_tab': 'competitors',
        'sub_page': 'c_mentions_products',
    })


def mentioning_competitors_tweets(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    return render(request, 'pages/brand_dashboard/bm_tweets.html', {
        'selected_tab': 'competitors',
        'sub_page': 'c_mentions_tweets',
    })


def mentioning_competitors_pins(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in STRIPE_ANALYTICS_PLANS:
        return redirect("/")

    return render(request, 'pages/brand_dashboard/bm_pins.html', {
        'selected_tab': 'competitors',
        'sub_page': 'c_mentions_pins',
    })


@brand_view
def posts_analytics(request, brand, base_brand):
    if request.method == 'GET':
        analytics = models.PostAnalytics.objects.filter(brands__id=brand.id)
        data = serializers.PostAnalyticsSerializer(analytics, many=True).data
        return render(request, 'pages/brand_dashboard/posts_analytics.html', {
            'analytics': map(json.dumps, data)
        })
    elif request.method == 'POST':
        brand = request.visitor["base_brand"]
        data = json.loads(request.body)

        is_report = bool(int(data.get('is_report', 0)))

        if data.get('report_id'):
            report = get_object_or_404(
                models.ROIPredictionReport,
                id=data.get('report_id'),
                creator_brand=brand)
            collection = report.post_collection
        elif data.get('collection_id'):
            collection = get_object_or_404(
                models.PostAnalyticsCollection,
                id=data.get('collection_id'),
                creator_brand=brand
            )
            report = None
        else:
            collection = None
            report = None

        if data.get('name'):
            if is_report and data.get('report_id'):
                existing = brand.created_roi_prediction_reports.exclude(
                    id=data.get('report_id')
                )
            elif not is_report and data.get('collection_id'):
                existing = brand.created_post_analytics_collections.exclude(
                    id=data.get('collection_id'))
            else:
                existing = None

            if existing is not None:
                existing = existing.exclude(
                    archived=True
                ).filter(
                    name=data.get('name')
                )

            if existing is not None and existing.exists():
                if report:
                    message = "Report with such name already exists"
                else:
                    message = "Post Analytics Collection with such name already exists"
                data = json.dumps({'message': message}, cls=DjangoJSONEncoder)
                return HttpResponseBadRequest(
                    data, content_type='application/json')

            if is_report:
                if report is None:
                    report = models.ROIPredictionReport(
                        creator_brand=brand,
                        user=request.user
                    )
                    if data.get('collection_id'):
                        report.post_collection_id = data.get('collection_id')
                    elif data.get('collection_name'):
                        collection = models.PostAnalyticsCollection.objects.create(
                            creator_brand=brand,
                            user=request.user,
                            name=data.get('collection_name'))
                        report.post_collection = collection
                report.name = data.get('name')
                report.save()
            else:
                if collection is None:
                    collection = models.PostAnalyticsCollection.objects.create(
                        creator_brand=brand,
                        user=request.user)
                collection.name = data.get('name')
                collection.save()

        if data.get('urls_to_remove'):
            for url in data.get('urls_to_remove'):
                collection.remove(url)

        if data.get('url'):
            try:
                urls = data.get('url').split('\n')
            except Exception as e:
                print e
                urls = [data.get('url')]

            exists = collection.postanalytics_set.filter(
                post_url__in=urls).exists()
            if exists:
                if len(urls) == 1:
                    message = "This post is already in the collection."
                elif len(urls) > 1:
                    message = "Some of these posts are already in the collection."
                data = json.dumps({'message': message}, cls=DjangoJSONEncoder)
                return HttpResponseBadRequest(data, content_type='application/json')

            brand_helpers.handle_post_analytics_urls(
                urls, brand_id=brand.id, refresh=True, collection=collection)
        
        data = {}
        if collection:
            data['collection_id'] = collection.id
        if report:
            data['report_id'] = report.id
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type='application/json')

    elif request.method == 'DELETE':
        pk = int(QueryDict(request.body).get('pk'))
        analytics = models.PostAnalytics.objects.get(pk=pk)
        analytics.brands.remove(brand)
        return HttpResponse()
