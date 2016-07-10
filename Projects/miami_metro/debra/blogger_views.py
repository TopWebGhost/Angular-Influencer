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
from debra.feeds_helpers import BLOG_FEED_PAGE_SIZE, normalize_posts_section_name
from debra.models import Influencer, Platform, BrandMentions, SponsorshipInfo, Brands, ProductModel, InfluencerCategoryMentions, Posts, InfluencersGroup, InfluencerGroupMapping, ProductModelShelfMap, InfluencerCollaborations
from debra.constants import ELASTICSEARCH_URL, ADMIN_TABLE_INFLUENCER_SELF_MODIFIED
from debra.constants import STRIPE_PLAN_STARTUP, STRIPE_PLAN_CHEAP, STRIPE_PLAN_BASIC, STRIPE_COLLECTION_PLANS, STRIPE_EMAIL_PLANS
from debra.widgets import UserFeed
from debra.decorators import user_is_brand_user
from debra.templatetags.custom_filters import fb_pic, post_pic, remove_dot_com
from django.db import IntegrityError
from django.conf import settings
from debra import serializers, elastic_search_helpers
from masuka.image_manipulator import upload_post_image
from debra import logical_categories
from debra import feeds_helpers
from debra import search_helpers
from debra import mongo_utils
from math import ceil
from xpathscraper.utils import domain_from_url
from debra.serializers import AdminInfluencerSerializer
import json
import pdb
import requests
import datetime
from debra import account_helpers
from platformdatafetcher import geocoding
import logging
log = logging.getLogger('debra.search_views')


def get_sections(**kwargs):
    sections = ['blog_posts', 'products', 'instagrams', 'tweets', 'pins',
        'facebook', 'youtube',]
    if kwargs.get('include_all_section'):
        sections = ['all'] + sections
    return sections


@login_required
def blogger_generic_posts(request, section, influencer_id, **kwargs):
    mongo_utils.track_visit(request)
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]

    # parameters
    show_filters = False and brand.stripe_plan

    # get influencer from db
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()

    # track events
    if brand:
        mongo_utils.track_query("brand-clicked-blogger-posts", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-posts", {
            'blog_url': influencer.blog_url
        })
    elif account_helpers.get_associated_influencer(request.user):
        account_helpers.intercom_track_event(request, "blogger-view-posts", {
            'blog_url': influencer.blog_url
        })

    influencer = serializers.annotate_influencer(influencer,
        request=request)

    context = {
        'influencer': influencer,
        'page': normalize_posts_section_name(section),
        'selected_tab': 'search_bloggers',
        'search_page': True,

        'show_filters': show_filters,
        'for_influencer': influencer.id,
        # 'posts_section': section,
        'initial_search_mode': normalize_posts_section_name(section),
        'init_brand': kwargs.get('brand_domain'),

        'type': 'all',
        'selected_tab': 'search',
        'sub_page': 'main_search',
        'shelf_user': request.visitor["user"],
        'debug': settings.DEBUG,
        'tag_id': request.GET.get('tag_id'),
        'saved_search': request.GET.get('saved_search'),

        'sections': get_sections(
            include_all_section=kwargs.get('brand_domain') is not None),
        'blogger_page': True,
    }

    if show_filters:
        context.update(
            search_helpers.prepare_filter_params(context,
                plan_name=brand.stripe_plan)
        )

    return render(request, 'pages/bloggers/blogger_generic_posts.html', context)


@login_required
def blogger_about(request, influencer_id):
    mongo_utils.track_visit(request)

    mongo_utils.influencer_profile_viewed(influencer_id)

    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()
    profile = influencer.shelf_user and influencer.shelf_user.userprofile or None

    if influencer.blacklisted:
        from debra.account_views import access_locked_page

        return access_locked_page(request, "Access is locked by administration.")

    assoc_inf = account_helpers.get_associated_influencer(request.user)
    if assoc_inf == influencer:
        profile_owner = True
        add_email = True
    else:
        profile_owner = False

    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    
    influencer_data = search_helpers.get_influencer_json(influencer, include_photos=True, long_post_content=True, request=request)
    try:
        influencer_data['profile']['items_list'] = influencer_data['profile']['items']
    except KeyError:
        pass
    influender_profile_id = influencer_data.get("profile", {}).get("id", None)
    add_email = False
    if base_brand and base_brand.is_subscribed:
        if base_brand.stripe_plan in STRIPE_EMAIL_PLANS:
            add_email = True
        if base_brand.stripe_plan in STRIPE_COLLECTION_PLANS:
            influencer = Influencer.objects.get(id=influencer_id)
            influencer_data["can_favorite"] = True
            influencer_data["is_favoriting"] = brand.influencer_groups.filter(influencers_mapping__influencer__id=influencer_id).exists()
    else:
        influencer_data["can_favorite"] = False

    if add_email:
        influencer_data["email"] = False
        emails = influencer.email
        if emails:
            splited = emails.split()
            if splited:
                influencer_data["email"] = splited[0]

    if brand:
        mongo_utils.track_query("brand-clicked-blogger-about", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-about", {
            'blog_url': influencer.blog_url
        })
    elif assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-view-about", {
            'blog_url': influencer.blog_url
        })

    influencer = serializers.annotate_influencer(influencer, request=request)

    return render(request, 'pages/bloggers/blogger_about.html', {
        'influencer': influencer,
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
        'selected_tab': 'search_bloggers',
        'search_page': True,

        'sections': get_sections(),
        'blogger_page': True,
    })


@login_required
def blogger_edit(request, influencer_id):
    mongo_utils.track_visit(request)
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()
    if not request.user.userprofile:
        print "User doesnt have userprofile"
        raise Http404()
    profile = request.user.userprofile

    assoc_inf = account_helpers.get_associated_influencer(request.user)
    if assoc_inf != influencer and not request.user.is_superuser:
        print "privilages mismatched"
        return HttpResponseForbidden()

    if assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-edit-description", {
            'blog_url': influencer.blog_url
        })

    if request.is_ajax():
        edits = []

        try:
            data = json.loads(request.body)
        except ValueError:
            print "bad json"
            return HttpResponseBadRequest()

        if data.get("collaborations_modified"):
            edits.append({
                "field": "collaborations",
            })
        if data.get("ifb_modified"):
            edits.append({
                "field": "info for brand",
            })

        old_style_tags = profile.style_tags
        profile.style_tags = ",".join([x.strip() for x in data.get("tags") if x])
        if old_style_tags != profile.style_tags:
            edits.append({
                "field": "style_tags",
                "from": old_style_tags,
                "to": profile.style_tags
            })

        if influencer.name != data.get("name"):
            edits.append({
                "field": "name",
                "from": influencer.name,
                "to": data.get("name")
            })
        influencer.name = data.get("name")
        if influencer.blogname != data.get("blogname"):
            edits.append({
                "field": "blogname",
                "from": influencer.blogname,
                "to": data.get("blogname")
            })
        influencer.blogname = data.get("blogname")
        if influencer.email != data.get("email"):
            edits.append({
                "field": "email",
                "from": influencer.email,
                "to": data.get("email")
            })
        influencer.email = data.get("email")
        location_edited = False
        if influencer.demographics_location_normalized != data.get("location"):
            location_edited = True
            edits.append({
                "field": "demographics_location_normalized",
                "from": influencer.demographics_location_normalized,
                "to": data.get("location")
            })
        influencer.demographics_location_normalized = data.get("location")
        if influencer.demographics_location != data.get("location"):
            edits.append({
                "field": "demographics_location",
                "from": influencer.demographics_location,
                "to": data.get("location")
            })
        influencer.demographics_location = data.get("location")
        if influencer.description != data.get("bio"):
            edits.append({
                "field": "description",
                "from": influencer.description,
                "to": data.get("bio")
            })
        influencer.description = data.get("bio")
        if influencer.collaboration_types != data.get("collaboration_types"):
            edits.append({
                "field": "collaboration_types",
                "from": influencer.collaboration_types,
                "to": data.get("collaboration_types")
            })
        influencer.collaboration_types = data.get("collaboration_types")
        if influencer.how_you_work != data.get("how_you_work"):
            edits.append({
                "field": "how_you_work",
                "from": influencer.how_you_work,
                "to": data.get("how_you_work")
            })
        influencer.how_you_work = data.get("how_you_work")

        influencer.collaborations.all().delete()
        rev_dict_ictype = dict([(x[1], x[0]) for x in InfluencerCollaborations.COLLABORATION_TYPES])
        for collab in data.get("collaborations", []):
            post_url = collab.get("post_url", '')
            if not post_url.startswith("http://") and not post_url.startswith("https://"):
                post_url = "http://" + post_url
            brand_url = collab.get("brand_url", '')
            if not brand_url.startswith("http://") and not brand_url.startswith("https://"):
                brand_url = "http://" + brand_url
            timestamp = collab.get('timestamp')
            try:
                timestamp = datetime.strptime(
                    timestamp.split('T')[0], "%Y-%m-%d")
                timestamp = timestamp.strftime('%x')
            except (AttributeError, ValueError):
                pass
            try:
                influencer.collaborations.create(
                    brand_name=collab.get("brand_name"),
                    brand_url=brand_url,
                    post_url=post_url,
                    details=collab.get("details"),
                    timestamp=timestamp,
                    collaboration_type=rev_dict_ictype.get(collab.get('collab_type'))
                )
            except IntegrityError:
                continue

        influencer.infos_for_brands.all().delete()

        ifb_enabled = data.get("info_for_brands", {}).get("enabled", {})
        ifb_range_max = data.get("info_for_brands", {}).get("range_max", {})
        ifb_range_min = data.get("info_for_brands", {}).get("range_min", {})
        ifb_info = data.get("info_for_brands", {}).get("info", {})

        for info_type, is_enabled in ifb_enabled.iteritems():
            if is_enabled:
                range_min = ifb_range_min.get(info_type)
                range_max = ifb_range_max.get(info_type)
                try:
                    range_min = float(range_min)
                except:
                    range_min = None
                try:
                    range_max = float(range_max)
                except:
                    range_max = None
                info = ifb_info.get(info_type)
                influencer.infos_for_brands.create(
                    range_min=range_min,
                    range_max=range_max,
                    details=info,
                    info_type=info_type
                )

        try:
            validated_on = json.loads(influencer.validated_on)
        except (ValueError, TypeError):
            validated_on = []
        validated_on.append(ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
        validated_on = list(set(validated_on))
        influencer.validated_on = json.dumps(validated_on)

        influencer.save()
        profile.save()

        if location_edited:
            geocoding.normalize_location.apply_async((influencer.id,))

        if edits:
            mongo_utils.influencer_log_edits(influencer.id, edits)

        request.visitor.flush()
        return HttpResponse()
    else:

        info_for_brands = {
            "info": {},
            "range_max": {},
            "enabled": {},
            "range_min": {}
        }

        collaborations = []

        for info in influencer.infos_for_brands.all():
            info_for_brands["enabled"][info.info_type] = True
            info_for_brands["range_min"][info.info_type] = info.range_min
            info_for_brands["range_max"][info.info_type] = info.range_max
            info_for_brands["info"][info.info_type] = info.details

        for collab in influencer.collaborations.all():
            collab_data = {
                "brand_name": collab.brand_name,
                "brand_url": collab.brand_url,
                "post_url": collab.post_url,
                "details": collab.details,
                "timestamp": collab.timestamp,
                "collab_type": dict(InfluencerCollaborations.COLLABORATION_TYPES).get(collab.collaboration_type),
            }
            collaborations.append(collab_data)

        profile_data = {
            "collaborations": collaborations,
            "info_for_brands": info_for_brands,
            "tags": profile.style_tags.split(","),
            "name": influencer.name,
            "blogname": influencer.blogname,
            "email": influencer.email,
            "location": influencer.demographics_location_normalized,
            "bio": influencer.description,
            "collaboration_types": influencer.collaboration_types,
            "how_you_work": influencer.how_you_work
        }

        return render(request, 'pages/bloggers/blogger_edit.html', {
            'influencer': influencer,
            'page': 'edit',
            'selected_tab': 'search_bloggers',
            'profile_data': json.dumps(profile_data, cls=DjangoJSONEncoder),
            'social': search_helpers.get_social_data(influencer, profile),
            'collab_types': InfluencerCollaborations.COLLABORATION_TYPES,

            'sections': get_sections(),
            'blogger_page': True,
        })


@login_required
def blogger_about_edit(request, influencer_id):
    mongo_utils.track_visit(request)
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()

    assoc_inf = account_helpers.get_associated_influencer(request.user)
    if assoc_inf != influencer:
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    profile = influencer.shelf_user and influencer.shelf_user.userprofile or None
    influencer.name = data.get("name")
    influencer.blogname = data.get("blogname")
    influencer.description = data.get("bio")
    if profile:
        profile.style_tags = ",".join(data.get("tags", []))
        profile.save()
    influencer.save()

    return HttpResponse()


@login_required
def blogger_posts(request, influencer_id):
    mongo_utils.track_visit(request)
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    assoc_inf = account_helpers.get_associated_influencer(request.user)
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()
    if brand:
        mongo_utils.track_query("brand-clicked-blogger-posts", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-posts", {
            'blog_url': influencer.blog_url
        })
    elif assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-view-posts", {
            'blog_url': influencer.blog_url
        })
    if request.is_ajax():
        data = feeds_helpers.blog_feed_json_dashboard(request, for_influencer=influencer, default_posts="about")
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        influencer = serializers.annotate_influencer(influencer, request=request)
        return render(request, 'pages/bloggers/blogger_posts.html', {
            'influencer': influencer,
            'page': 'posts',
            'selected_tab': 'search_bloggers',
            'search_page': True,
        })


@login_required
def blogger_posts_sponsored(request, influencer_id):
    mongo_utils.track_visit(request)
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    assoc_inf = account_helpers.get_associated_influencer(request.user)
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()
    if not brand and assoc_inf != influencer:
        return HttpResponseForbidden()
    if brand:
        mongo_utils.track_query("brand-clicked-blogger-sponsored-posts", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-sponsored-posts", {
            'blog_url': influencer.blog_url
        })
    elif assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-view-sponsored-posts", {
            'blog_url': influencer.blog_url
        })
    if request.is_ajax():
        data = feeds_helpers.collab_feed_json(request, for_influencer=influencer, default_posts="about")
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        influencer = serializers.annotate_influencer(influencer, request=request)
        return render(request, 'pages/bloggers/blogger_posts_sponsored.html', {
            'influencer': influencer,
            'page': 'posts_sponsored',
            'selected_tab': 'search_bloggers',
            'search_page': True,
        })


@login_required
def blogger_photos(request, influencer_id):
    mongo_utils.track_visit(request)
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    assoc_inf = account_helpers.get_associated_influencer(request.user)
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()
    if brand:
        mongo_utils.track_query("brand-clicked-blogger-pictures", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-pictures", {
            'blog_url': influencer.blog_url
        })
    elif assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-view-pictures", {
            'blog_url': influencer.blog_url
        })

    if request.is_ajax():
        data = feeds_helpers.instagram_feed_json(request, for_influencer=influencer, default_posts="about_insta")
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        influencer = serializers.annotate_influencer(influencer, request=request)
        return render(request, 'pages/bloggers/blogger_photos.html', {
            'influencer': influencer,
            'page': 'photos',
            'selected_tab': 'search_bloggers',
            'search_page': True,
        })

@login_required
def blogger_youtube(request, influencer_id):
    mongo_utils.track_visit(request)
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    assoc_inf = account_helpers.get_associated_influencer(request.user)
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()
    if brand:
        mongo_utils.track_query("brand-clicked-blogger-videos", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-videos", {
            'blog_url': influencer.blog_url
        })
    elif assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-view-videos", {
            'blog_url': influencer.blog_url
        })

    if request.is_ajax():
        data = feeds_helpers.youtube_feed_json(request, for_influencer=influencer)
            # default_posts="about_youtube")
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        influencer = serializers.annotate_influencer(influencer, request=request)
        return render(request, 'pages/bloggers/blogger_videos.html', {
            'influencer': influencer,
            'page': 'videos',
            'selected_tab': 'search_bloggers',
            'search_page': True,
        })

@login_required
def blogger_items(request, influencer_id):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    assoc_inf = account_helpers.get_associated_influencer(request.user)
    try:
        influencer = Influencer.objects
        influencer = influencer.prefetch_related('platform_set')
        influencer = influencer.get(id=influencer_id)
    except:
        raise Http404()
    if brand:
        mongo_utils.track_query("brand-clicked-blogger-products", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-products", {
            'blog_url': influencer.blog_url
        })
    elif assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-view-products", {
            'blog_url': influencer.blog_url
        })
    if request.is_ajax() or request.GET.get('debug'):
        data = feeds_helpers.product_feed_json(request, for_influencer=influencer)
        data = json.dumps(data, cls=DjangoJSONEncoder)
        if request.GET.get('debug'):
            return HttpResponse("<body></body>")
        return HttpResponse(data, content_type="application/json")
    else:
        influencer = serializers.annotate_influencer(influencer, request=request)
        return render(request, 'pages/bloggers/blogger_items.html', {
            'influencer': influencer,
            'page': 'items',
            'selected_tab': 'search_bloggers',
            'search_page': True,
        })


@login_required
def blogger_tweets(request, influencer_id):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    assoc_inf = account_helpers.get_associated_influencer(request.user)
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()
    if brand:
        mongo_utils.track_query("brand-clicked-blogger-tweets", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-tweets", {
            'blog_url': influencer.blog_url
        })
    elif assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-view-tweets", {
            'blog_url': influencer.blog_url
        })
    if request.is_ajax():
        data = feeds_helpers.twitter_feed_json(request, for_influencer=influencer, default_posts="about_tweets")
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        influencer = serializers.annotate_influencer(influencer, request=request)
        return render(request, 'pages/bloggers/blogger_tweets.html', {
            'influencer': influencer,
            'page': 'tweets',
            'selected_tab': 'search_bloggers',
            'search_page': True,
        })


@login_required
def blogger_pins(request, influencer_id):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    assoc_inf = account_helpers.get_associated_influencer(request.user)
    plan_name = brand.stripe_plan
    try:
        influencers_qs = Influencer.objects.prefetch_related('platform_set')
        influencer = influencers_qs.get(id=influencer_id)
    except:
        raise Http404()
    if brand:
        mongo_utils.track_query("brand-clicked-blogger-pins", {
            'blog_url': influencer.blog_url
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-clicked-blogger-pins", {
            'blog_url': influencer.blog_url
        })
    elif assoc_inf:
        account_helpers.intercom_track_event(request, "blogger-view-pins", {
            'blog_url': influencer.blog_url
        })
    if request.is_ajax():
        data = feeds_helpers.pinterest_feed_json(request, for_influencer=influencer, default_posts="about_pins")
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        influencer = serializers.annotate_influencer(influencer, request=request)

        context = {
            'influencer': influencer,
            'page': 'pins',
            'selected_tab': 'search_bloggers',
            'search_page': True,

            'type': 'all',
            'selected_tab': 'search',
            'sub_page': 'main_search',
            'shelf_user': request.visitor["user"],
            'debug': settings.DEBUG,
            'tag_id': request.GET.get('tag_id'),
            'saved_search': request.GET.get('saved_search'),
        }

        context.update(
            search_helpers.prepare_filter_params(context, plan_name=plan_name))

        return render(request, 'pages/bloggers/blogger_pins.html', context)


@login_required
def blogger_redirection(request, section, blog_url, influencer_id, sub_section=None):
    view_name = None
    if section == 'youtube':
        view_name = 'blogger_youtube'
    view_name = 'blogger_{}'.format(section)
    if sub_section:
        view_name = '{}_{}'.format(view_name, sub_section)
    return redirect('debra.blogger_views.' + view_name, influencer_id=influencer_id)
