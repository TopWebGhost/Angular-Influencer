import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, HttpResponse, HttpResponseBadRequest, Http404
from django.db.models import Max, Q, Sum
from django.forms.models import model_to_dict
from django.utils.html import strip_tags
from django.template.defaultfilters import cut
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from debra.models import Influencer, Platform, BrandMentions, SponsorshipInfo, Brands, ProductModel, InfluencerCategoryMentions, Posts, InfluencersGroup, InfluencerGroupMapping, ProductModelShelfMap, InfluencerCollaborations
from debra.constants import ELASTICSEARCH_URL, ADMIN_TABLE_INFLUENCER_SELF_MODIFIED
from debra.constants import STRIPE_PLAN_STARTUP, STRIPE_PLAN_CHEAP, STRIPE_PLAN_BASIC, STRIPE_COLLECTION_PLANS, STRIPE_EMAIL_PLANS
from debra.widgets import UserFeed
from debra.decorators import user_is_brand_user
from debra.templatetags.custom_filters import fb_pic, post_pic, remove_dot_com
from django.db import IntegrityError
from debra import serializers
from masuka.image_manipulator import upload_post_image
from debra import logical_categories
from debra import feeds_helpers
from debra import search_helpers
from math import ceil
from xpathscraper.utils import domain_from_url
from debra.serializers import AdminInfluencerSerializer
import json
import pdb
import requests
import datetime
from debra import account_helpers, brand_helpers
import logging
log = logging.getLogger('debra.search_views')


@login_required
def brand_about(request, brand_url, brand_id):
    try:
        brands_qs = Brands.objects
        brand = brands_qs.get(id=brand_id, domain_name=brand_url)
    except:
        raise Http404()

    if brand == request.visitor["brand"]:
        profile_owner = True
    else:
        profile_owner = False

    influencer_data = search_helpers.get_influencer_json(brand.pseudoinfluencer, include_photos=True, long_post_content=True, request=request)
    influencer_data["can_favorite"] = False
    try:
        profile = brand.userprofile
    except:
        brand_helpers.create_profile_for_brand(brand)
        profile = brand.userprofile

    return render(request, 'pages/brand_profile/brand_about.html', {
        'influencer': brand.pseudoinfluencer,
        'brand': brand,
        'page': 'about',
        'posts': json.dumps(influencer_data.get("posts"), cls=DjangoJSONEncoder),
        'influencer_data': influencer_data,
        'style_tags': profile and profile.style_tags and profile.style_tags.split(","),
        'relfashion_stats': json.dumps(influencer_data.get("relfashion_stats"), cls=DjangoJSONEncoder),
        'category_stats': json.dumps(influencer_data.get("category_stats"), cls=DjangoJSONEncoder),
        'popularity_stats': json.dumps(influencer_data.get("popularity_stats"), cls=DjangoJSONEncoder),
        'popularity_sums': json.dumps(influencer_data.get("popularity_sums"), cls=DjangoJSONEncoder),
        'STRIPE_PLAN_STARTUP': STRIPE_PLAN_STARTUP,
        'STRIPE_PLAN_BASIC': STRIPE_PLAN_BASIC,
        'STRIPE_EMAIL_PLANS': STRIPE_EMAIL_PLANS,
        'COLLABORATION_TYPES': InfluencerCollaborations.COLLABORATION_TYPES,
        'profile_owner': profile_owner,
        'selected_tab': profile_owner and 'getting_started' or '',
        'sub_page': profile_owner and 'brand_profile_view' or '',
        'search_page': True,
        'hide_nav': True,
        'location': brand.pseudoinfluencer.demographics_location_normalized or brand.pseudoinfluencer.demographics_location
    })

@login_required
def brand_edit(request, brand_url, brand_id):
    from debra.admin_helpers import handle_blog_url_change, handle_social_handle_updates, update_or_create_new_platform

    try:
        brands_qs = Brands.objects
        brand = brands_qs.get(id=brand_id, domain_name=brand_url)
    except:
        raise Http404()
    if brand != request.visitor["brand"] and not request.user.is_superuser:
        print "privilages mismatched"
        return HttpResponseForbidden()

    influencer = brand.pseudoinfluencer
    try:
        profile = brand.userprofile
    except:
        brand_helpers.create_profile_for_brand(brand)
        profile = brand.userprofile

    if request.is_ajax():
        try:
            data = json.loads(request.body)
        except ValueError:
            print "bad json"
            return HttpResponseBadRequest()

        old_style_tags = profile.style_tags
        profile.style_tags = ",".join([x.strip() for x in data.get("tags") if x])

        influencer.blogname = data.get("blogname")
        influencer.email = data.get("email")
        influencer.demographics_location_normalized = data.get("location")
        influencer.demographics_location = data.get("location")
        influencer.description = data.get("bio")
        try:
            validated_on = json.loads(influencer.validated_on)
        except (ValueError, TypeError):
            validated_on = []
        validated_on.append(ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
        validated_on = list(set(validated_on))
        influencer.validated_on = json.dumps(validated_on)

        old_fb_url = influencer.fb_url
        influencer.fb_url = data.get('social', {}).get("facebook_page")
        if influencer.fb_url == "":
            influencer.fb_url = None
        old_tw_url = influencer.tw_url
        influencer.tw_url = data.get('social', {}).get("twitter_page")
        if influencer.tw_url == "":
            influencer.tw_url = None
        old_pin_url = influencer.pin_url
        influencer.pin_url = data.get('social', {}).get("pinterest_page")
        if influencer.pin_url == "":
            influencer.pin_url = None
        old_insta_url = influencer.insta_url
        influencer.insta_url = data.get('social', {}).get("instagram_page")
        if influencer.insta_url == "":
            influencer.insta_url = None
        old_blog_url = influencer.blog_url
        influencer.blog_url = data.get('social', {}).get("blog_page")
        if influencer.blog_url == "":
            influencer.blog_url = None

        brand.name = data.get("brandname")
        brand.save()
        influencer.save()
        profile.save()

        if influencer.blog_url != old_blog_url:
            handle_blog_url_change(influencer, influencer.blog_url)
        if influencer.fb_url != old_fb_url:
            handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
        if influencer.tw_url != old_tw_url:
            handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
        if influencer.pin_url != old_pin_url:
            handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
        if influencer.insta_url != old_insta_url:
            handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)

        request.visitor.flush()
        return HttpResponse()
    else:
        profile_data = {
            "collaborations": None,
            "info_for_brands": None,
            'profile_img_url': brand.profile_pic,
            'cover_img_url': brand.cover_pic,
            "tags": profile.style_tags.split(","),
            "name": influencer.name,
            "blogname": influencer.blogname,
            "brandname": brand.name,
            "email": influencer.email,
            "location": influencer.demographics_location_normalized,
            "bio": influencer.description,
            "collaboration_types": influencer.collaboration_types,
            "how_you_work": influencer.how_you_work,
            "social": {
                "facebook_page": influencer.fb_url,
                "twitter_page": influencer.tw_url,
                "pinterest_page": influencer.pin_url,
                "instagram_page": influencer.insta_url,
                "bloglovin_page": influencer.bloglovin_url,
                "lb_page": influencer.lb_url,
                "blog_page": influencer.blog_url,
            }
        }

        return render(request, 'pages/brand_profile/brand_edit.html', {
            'influencer': brand.pseudoinfluencer,
            'brand': brand,
            'page': 'edit',
            'selected_tab': 'brand_profile',
            'hide_nav': False,
            'sub_page': 'brand_profile_edit',
            'profile_data': json.dumps(profile_data, cls=DjangoJSONEncoder),
            'collab_types': InfluencerCollaborations.COLLABORATION_TYPES
        })


@login_required
def brand_posts(request, brand_url, brand_id):
    try:
        brands_qs = Brands.objects
        brand = brands_qs.get(id=brand_id, domain_name=brand_url)
    except:
        raise Http404()
    if request.is_ajax():
        data = feeds_helpers.blog_feed_json_dashboard(request, for_influencer=brand.pseudoinfluencer)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_profile/brand_posts.html', {
            'influencer': brand.pseudoinfluencer,
            'brand': brand,
            'page': 'posts',
            'selected_tab': 'brand_profile',
            'hide_nav': True,
            'search_page': True,
        })


@login_required
def brand_photos(request, brand_url, brand_id):
    try:
        brands_qs = Brands.objects
        brand = brands_qs.get(id=brand_id, domain_name=brand_url)
    except:
        raise Http404()
    if request.is_ajax():
        data = feeds_helpers.instagram_feed_json(request, for_influencer=brand.pseudoinfluencer)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_profile/brand_photos.html', {
            'influencer': brand.pseudoinfluencer,
            'brand': brand,
            'page': 'photos',
            'selected_tab': 'brand_profile',
            'hide_nav': True,
            'search_page': True,
        })


@login_required
def brand_items(request, brand_url, brand_id):
    try:
        brands_qs = Brands.objects
        brand = brands_qs.get(id=brand_id, domain_name=brand_url)
    except:
        raise Http404()
    if request.is_ajax():
        data = feeds_helpers.product_feed_json(request, for_influencer=brand.pseudoinfluencer)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_profile/brand_items.html', {
            'influencer': brand.pseudoinfluencer,
            'brand': brand,
            'page': 'items',
            'selected_tab': 'brand_profile',
            'hide_nav': True,
            'search_page': True,
        })


@login_required
def brand_tweets(request, brand_url, brand_id):
    try:
        brands_qs = Brands.objects
        brand = brands_qs.get(id=brand_id, domain_name=brand_url)
    except:
        raise Http404()
    if request.is_ajax():
        data = feeds_helpers.twitter_feed_json(request, for_influencer=brand.pseudoinfluencer)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_profile/brand_tweets.html', {
            'influencer': brand.pseudoinfluencer,
            'brand': brand,
            'page': 'tweets',
            'selected_tab': 'brand_profile',
            'hide_nav': True,
            'search_page': True,
        })


@login_required
def brand_pins(request, brand_url, brand_id):
    try:
        brands_qs = Brands.objects
        brand = brands_qs.get(id=brand_id, domain_name=brand_url)
    except:
        raise Http404()
    if request.is_ajax():
        data = feeds_helpers.pinterest_feed_json(request, for_influencer=brand.pseudoinfluencer)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        return render(request, 'pages/brand_profile/brand_pins.html', {
            'influencer': brand.pseudoinfluencer,
            'brand': brand,
            'page': 'pins',
            'selected_tab': 'brand_profile',
            'hide_nav': True,
            'search_page': True,
        })
