'''
views for a brand user. Currently this (almost entirely) resembles shelf_views.py, however we don't want to abstract
 because this leaves more room for the two to separate in the future
Important to note: Each of these must include page_user_prof as a tpl_var so the page knows the id of the visiting user
'''

from django.shortcuts import render_to_response, redirect
from debra.widgets import WishlistItemsFeed, ShelvesFeed, UserFeed
from debra.forms import ShelfAccountForm, ModifyShelfForm, CreateShelfForm
from debra.models import StyleTag, UserProfile, Brands
from debra.constants import LIKED_SHELF, SEO_VALUES
from debra import helpers as h
from django.template import RequestContext
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from debra.feeds_helpers import product_feed_json
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import authenticate, login, logout
from . import account_views
from debra import search_helpers

import pdb
import json

#####-----< Under 'You' Tab >-----#####
def brand_home(request, user=0):
    return account_views.my_custom_404_view(request)
    page_user_prof = UserProfile.objects.get(id=user)
    filter_id = request.GET.get('q', None)

    if request.is_ajax():
        data = product_feed_json(request, for_user=page_user_prof, shelf=filter_id, user_is_brand=True)
        data = json.dumps(data, cls=DjangoJSONEncoder, default=lambda obj: None)
        return HttpResponse(data, content_type="application/json")
    else:
        tpl = 'pages/middle_content_only.html'
        tpl_vars = {
            'selected_tab': 'myshelf',
            'filtered_shelf': Shelf.objects.get(id=filter_id) if filter_id else None,
            'feed_type': 'items',
            'page_name': 'myshelf',
            'feed_filter': 'products',
            'page_user_prof': page_user_prof,
            'page_title': SEO_VALUES['shelf_home']['title'],
            'meta_description': SEO_VALUES['shelf_home']['meta_desc']
        }
        return render_to_response(tpl, tpl_vars, context_instance=RequestContext(request))

    # page_user_prof = UserProfile.objects.get(id=user)
    # filter = request.GET.get('q', None)
    # feed = WishlistItemsFeed(request, {"shelf": filter}, user=page_user_prof).generate_items()

    # if request.is_ajax():
    #     feed.ajax_request = True
    #     return feed.render()
    # else:
    #     return render_to_response("pages/middle_content_only.html", {
    #         'middle': feed.render(),
    #         'selected_tab': 'myshelf',
    #         'feed_type': 'items',
    #         'page_user_prof': page_user_prof,
    #         'create_shelf_form': CreateShelfForm(),
    #         'page_title': SEO_VALUES['brand_home']['title'],
    #         'meta_description': SEO_VALUES['brand_home']['meta_desc'],
    #     }, context_instance=RequestContext(request))

###not currently used
def followers(request, user=0):
    return account_views.my_custom_404_view(request)
    page_user_prof = UserProfile.objects.get(id=user)
    user_feed = UserFeed(request, view_file='follows.html', user=page_user_prof).generate_followers()

    #endless pagination reached
    if request.is_ajax():
        user_feed.ajax_request = True
        return user_feed.render()
    else:
        return render_to_response('pages/middle_content_only.html', {
            'middle': user_feed.render(),
            'selected_tab': 'followers',
            'page_user_prof': page_user_prof,
            'user_feed': True,
            'page_title': SEO_VALUES['brand_followers']['title'],
            'meta_description': SEO_VALUES['brand_followers']['meta_desc'],
        }, context_instance=RequestContext(request))


@login_required
@require_http_methods(["GET"])
def about_me(request, user=0):
    NUM_FOLLOW_IMAGES = 20
    page_user_prof = UserProfile.objects.get(id=user)
    account_form = ShelfAccountForm(instance=page_user_prof, initial={'twitter_page': page_user_prof.twitter_handle})

    #limit the number of follower/following images to 20
    return render_to_response('pages/about_me.html', {
        'follower_images': page_user_prof.get_followers.select_related('user')[:NUM_FOLLOW_IMAGES],
        'following_images': [],
        'shelves': page_user_prof.user_created_shelves.exclude(name=LIKED_SHELF),
        'recently_shelved': page_user_prof.recently_shelved_items,
        'style_tags': page_user_prof.style_tags.split(',') if page_user_prof.style_tags else StyleTag.default_style_tags(),
        'selected_tab': 'about',
        'page_user_prof': page_user_prof,
        'brand_about': True,
        'account_form': account_form,
        'page_title': SEO_VALUES['brand_about']['title'],
        'meta_description': SEO_VALUES['brand_about']['meta_desc'],
    }, context_instance=RequestContext(request))



@login_required
@require_http_methods(["POST"])
def edit_profile(request, user=0):
    '''
    this view method is for when a user edits their profile
    @param user - the user who is editing their profile
    '''
    page_user_prof = UserProfile.objects.get(id=user)
    bound_form = ShelfAccountForm(request.POST, instance=page_user_prof)

    if bound_form.is_valid():
        bound_form.save()
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=500)




@login_required
def login_as_brand(request, brand_id):
    page_user = request.user
    brand = Brands.objects.filter(id=brand_id, related_user_profiles__user_profile__user=page_user)
    if brand:
        logout(request)
        user = brand[0].userprofile.user
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        return HttpResponseRedirect(user.userprofile.after_login_url)
    return HttpResponseForbidden()
