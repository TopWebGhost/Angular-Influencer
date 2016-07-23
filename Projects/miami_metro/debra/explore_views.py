'''
this file represents views that are resolved by urls the user visits not specific to any
one person, item, etc.
NOTE: must provide a tpl_var explore_page so that the header knows which tab to select
'''
from django.contrib.auth.decorators import login_required
from debra.decorators import disable_view
from django.conf import settings
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.forms.models import model_to_dict
from django.shortcuts import render_to_response
from django.template import RequestContext
from debra.models import Posts, ProductModelShelfMap, Platform
from django.http import HttpResponseForbidden, HttpResponse, Http404
from debra.widgets import UserFeed, WishlistItemsFeed
from django.core.urlresolvers import reverse
from django.template.defaultfilters import cut
from django.utils.html import strip_tags
from debra.forms import CreateShelfForm
from debra.constants import SEO_VALUES
from random import shuffle
from django.core.cache import cache
from debra.feeds_helpers import product_feed_json, blog_feed_json, instagram_feed_json

import pdb
import json
import re


def inspiration_json(request):
    if not settings.DEBUG:
        raise Http404()
    data = []
    product_data = []
    blog_data = []
    instagram_data = []
    feed_filter = request.GET.get('filter', 'blog')
    if settings.DEBUG:
        feed_filter = "all"
    if feed_filter == 'all' or feed_filter == 'products':
        product_data = product_feed_json(request)
    if feed_filter == 'all' or feed_filter == 'photos':
        instagram_data = instagram_feed_json(request)
    if feed_filter == 'all' or feed_filter == 'blog':
        blog_data = blog_feed_json(request)

    while blog_data or instagram_data or product_data:
        if blog_data:
            data.append(blog_data.pop())
        if instagram_data:
            data.append(instagram_data.pop())
        if product_data:
            data.append(product_data.pop())
    data.reverse()
    #shuffle(data)
    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder, default=lambda obj: None)
        return HttpResponse(data, content_type="application/json")
    else:
        #data = json.dumps(data, cls=DjangoJSONEncoder, default=lambda obj: None, indent=4)
        return HttpResponse("<body>DEBUG</body>")

@disable_view
def inspiration(request, admin_view, filter=None):
    if not filter:
        filter = 'blog'
    result = render_to_response('pages/middle_content_only.html', {
        'explore_page': True,
        'page_name': 'inspiration',
        'feed_type': 'items',
        'feed_filter': filter,
        'create_shelf_form': CreateShelfForm(),
        'page_title': SEO_VALUES['inspiration']['title'],
        'meta_description': SEO_VALUES['inspiration']['meta_desc']
    }, context_instance=RequestContext(request))
    return result


def trendsetters(request, admin_view):
    user_feed = UserFeed(request).generate_trendsetters()

    if request.is_ajax():
        user_feed.ajax_request = True
        return user_feed.render()
    else:
        return render_to_response('pages/middle_content_only.html', {
            'middle': user_feed.render(),
            'explore_page': True,
            'page_name': 'trendsetters',
            'feed_type': 'users',
            'one_column': True,
            'user_feed': True,
            'page_title': SEO_VALUES['trendsetters']['title'],
            'meta_description': SEO_VALUES['trendsetters']['meta_desc']
        }, context_instance=RequestContext(request))

@login_required
def non_trendsetters(request, admin_view):
    '''
    not currently used by anything but the admin panel, but can easily see this being used in the future
    '''
    user_feed = UserFeed(request).generate_plebians()
    if request.is_ajax():
        user_feed.ajax_request = True
        return user_feed.render()
    else:
        return render_to_response('pages/middle_content_only.html', {
            'middle': user_feed.render(),
            'explore_page': True,
            'feed_type': 'users',
            'one_column': True,
            'user_feed': True
        }, context_instance=RequestContext(request))


def trending_brands(request, admin_view):
    brands_feed = UserFeed(request, view_file="trending_brands.html").generate_trending_brands()

    if request.is_ajax():
        brands_feed.ajax_request = True
        return brands_feed.render()
    else:
        return render_to_response('pages/middle_content_only.html', {
            'middle': brands_feed.render(),
            'explore_page': True,
            'page_name': 'trending_brands',
            'feed_type': 'users',
            'one_column': True,
            'user_feed': True,
            'page_title': SEO_VALUES['trending_brands']['title'],
            'meta_description': SEO_VALUES['trending_brands']['meta_desc']
        }, context_instance=RequestContext(request))


def giveaways(request):
    user_feed = UserFeed(request).generate_giveaway_partners()

    if request.is_ajax():
        user_feed.ajax_request = True
        return user_feed.render()
    else:
        return render_to_response('pages/middle_content_only.html', {
            'middle': user_feed.render(),
            'explore_page': True,
            'page_name': 'giveaways',
            'one_column': True,
            'user_feed': True
        }, context_instance=RequestContext(request))
