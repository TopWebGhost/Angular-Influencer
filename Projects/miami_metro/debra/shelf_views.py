'''
views for user pages (my shelves, followers/following, about).
Important to note: Each of these must include page_user_prof as a tpl_var so the page knows the id of the visiting user
'''

from debra.widgets import WishlistItemsFeed, ShelvesFeed, UserFeed
from django.core.serializers.json import DjangoJSONEncoder
from debra.forms import ShelfAccountForm, ModifyShelfForm, CreateShelfForm, ChangeEmailForm, ChangePasswordForm
from debra.models import Shelf, UserProfile, StyleTag, ProductModelShelfMap, InfluencerGroupMapping
from debra.constants import SEO_VALUES
from debra import helpers as h
from hanna.import_from_blog_post import create_wishlist_for_url_in_shelf
from django.shortcuts import render_to_response, render, redirect
from django.template import RequestContext
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseNotFound
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from debra.feeds_helpers import product_feed_json, blog_feed_json, instagram_feed_json
from debra.decorators import user_is_brand_user
from debra import search_helpers

import random
import pdb
import json
from . import account_views

#####-----< Under 'You' Tab >-----#####
def shelf_home(request, user=0, filter=None):
    '''
    cases:
    - is_ajax = if its an ajax request, we want to render an httpresponse for the response (endless scroll)
    - feed.is_empty() = the user has no items in their feed, render the empty version of their homepage into middle content only
    - feed not empty = normal flow, render their sidebar alongside the feed of their items
    '''
    return account_views.my_custom_404_view(request)
    page_user_prof = UserProfile.objects.get(id=user)
    filter_id = request.GET.get('q', None)
    #feed = WishlistItemsFeed(request, {"shelf": filter_id}, user=page_user_prof).generate_items()

    if request.is_ajax():
        data = []
        product_data = []
        blog_data = []
        instagram_data = []
        feed_filter = request.GET.get('filter', 'blog')
        if feed_filter == 'all' or feed_filter == 'products':
            product_data = product_feed_json(request, for_user=page_user_prof, shelf=filter_id)
        if feed_filter == 'all' or feed_filter == 'photos':
            instagram_data = instagram_feed_json(request, for_user=page_user_prof)
        if feed_filter == 'all' or feed_filter == 'blog':
            blog_data = blog_feed_json(request, for_user=page_user_prof)

        while blog_data or instagram_data or product_data:
            if blog_data:
                data.append(blog_data.pop())
            if instagram_data:
                data.append(instagram_data.pop())
            if product_data:
                data.append(product_data.pop())
        data.reverse()
        data = json.dumps(data, cls=DjangoJSONEncoder, default=lambda obj: None)
        return HttpResponse(data, content_type="application/json")
    else:
        if not filter:
            filter='blog'
        tpl = 'pages/middle_content_only.html'
        tpl_vars = {
            'selected_tab': 'myshelf',
            'filtered_shelf': Shelf.objects.get(id=filter_id) if filter_id else None,
            'feed_type': 'items',
            'page_name': 'myshelf',
            'feed_filter': filter,
            'page_user_prof': page_user_prof,
            'page_title': SEO_VALUES['shelf_home']['title'],
            'meta_description': SEO_VALUES['shelf_home']['meta_desc']
        }
        return render_to_response(tpl, tpl_vars, context_instance=RequestContext(request))


    # if not UserProfile.objects.filter(id=user).exists():
    #     return account_views.my_custom_404_view(request)
    # page_user_prof = UserProfile.objects.get(id=user)
    # filter_id = request.GET.get('q', None)
    # feed = WishlistItemsFeed(request, {"shelf": filter_id}, user=page_user_prof).generate_items()

    # if request.is_ajax():
    #     feed.ajax_request = True
    #     return feed.render()
    # else:
    #     if feed.is_empty and h.user_is_logged_in_user(request, page_user_prof):
    #         tpl = 'pages/middle_content_only.html'
    #         tpl_vars = {
    #             'empty': True,
    #             'middle': feed.render_empty(),
    #             'selected_tab': 'myshelf',
    #             'page_user_prof': page_user_prof,
    #             'page_title': SEO_VALUES['shelf_home']['title'],
    #             'meta_description': SEO_VALUES['shelf_home']['meta_desc']
    #         }
    #     else:
    #         tpl = 'pages/middle_content_only.html'
    #         tpl_vars = {
    #             'middle' : feed.render(),
    #             'selected_tab': 'myshelf',
    #             'filtered_shelf': Shelf.objects.get(id=filter_id) if filter_id else None,
    #             'feed_type': 'items',
    #             'page_user_prof': page_user_prof,
    #             'page_title': SEO_VALUES['shelf_home']['title'],
    #             'meta_description': SEO_VALUES['shelf_home']['meta_desc']
    #         }

    #     return render_to_response(tpl, tpl_vars, context_instance=RequestContext(request))

def my_shelves(request, user=0):
    return account_views.my_custom_404_view(request)
    '''
    the shelves for a given user
    **this might seem overly convoluted at first, but the reason we do it this way is so that we don't have to run
    a (potentially expensive) query on ProductModelShelfMap per Shelf**
    '''
    page_user_prof = UserProfile.objects.get(id=user)
    users_shelves = page_user_prof.user_created_shelves | page_user_prof.user_category_shelves
    users_shelves = users_shelves.exclude(name='')

    # pre-fetch all pmsm's we care about (for their image)
    images = list(ProductModelShelfMap.objects.filter(shelf__in=users_shelves,
                                                      img_url_feed_view__isnull=False).select_related('shelf'))
    # this lambda gets the pmsm's img url for a given shelf (in memory, so no database fetch)
    shelf_images = lambda shelf: [pmsm.img_url_feed_view for pmsm in filter(lambda pmsm: pmsm.shelf == shelf, images)[:4]]

    shelves = ShelvesFeed(request, None,
                          view_file='my_shelves.html',
                          user=page_user_prof,
                          qs=None, #going to be overriden anyway by extra_context
                          extra_context={
                              'shelves': [{'obj': s, 'images': shelf_images(s)} for s in users_shelves]
                          })

    return render(request, 'pages/middle_content_only.html', {
                'selected_tab': 'shelves',
                'middle': shelves.render(),
                'feed_type': 'shelves',
                'page_user_prof': page_user_prof,
                'create_shelf_form': CreateShelfForm(),
                'modify_shelf_form': ModifyShelfForm(),
                'page_title': SEO_VALUES['my_shelves']['title'],
                'meta_description': SEO_VALUES['my_shelves']['meta_desc']
            })

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
            'empty': user_feed.is_empty,
            'middle': user_feed.render() if not user_feed.is_empty else user_feed.render_empty(),
            'selected_tab': 'followers',
            'page_user_prof': page_user_prof,
            'user_feed': True,
            'page_title': SEO_VALUES['followers']['title'],
            'meta_description': SEO_VALUES['followers']['meta_desc']
        }, context_instance=RequestContext(request))

###not currently used
def following(request, user=0):
    return account_views.my_custom_404_view(request)
    page_user_prof = UserProfile.objects.get(id=user)
    user_feed = UserFeed(request, view_file="follows.html", user=page_user_prof).generate_following()

    #endless pagination reached
    if request.is_ajax():
        user_feed.ajax_request = True
        return user_feed.render()
    else:
        pass
    return render_to_response('pages/middle_content_only.html', {
        'empty': user_feed.is_empty,
        'middle': user_feed.render() if not user_feed.is_empty else user_feed.render_empty(),
        'selected_tab': 'following',
        'page_user_prof': page_user_prof,
        'user_feed': True,
        'page_title': SEO_VALUES['following']['title'],
        'meta_description': SEO_VALUES['following']['meta_desc']
    }, context_instance=RequestContext(request))


@require_http_methods(["GET"])
def about_me(request, user=0):
    NUM_FOLLOW_IMAGES = 20
    NUM_SHELVES = 10
    page_user_prof = UserProfile.objects.get(id=user)
    account_form = ShelfAccountForm(instance=page_user_prof, initial={'twitter_page': page_user_prof.twitter_handle})

    #limit the number of follower/following images to 20
    return render_to_response('pages/about_me.html', {
         'follower_images': page_user_prof.get_followers.filter(user__profile_img_url__isnull=False)[:NUM_FOLLOW_IMAGES],
         'following_images': page_user_prof.get_following.select_related('following__brand')[:NUM_FOLLOW_IMAGES],
         'shelves': page_user_prof.user_created_shelves.filter(num_items__gt=0).order_by('-num_items')[:NUM_SHELVES],
         'recently_shelved': page_user_prof.recently_shelved_items,
         'style_tags': page_user_prof.style_tags.split(',') if page_user_prof.style_tags else StyleTag.default_style_tags(),
         'selected_tab': 'about',
         'page_user_prof': page_user_prof,
         'account_form': account_form,
         'change_email_form': ChangeEmailForm(instance=page_user_prof),
         'change_password_form': ChangePasswordForm(),
         'page_title': SEO_VALUES['about_me']['title'],
         'meta_description': SEO_VALUES['about_me']['meta_desc'],
         'next': page_user_prof.about_url
    }, context_instance=RequestContext(request))

###not currently used
def liked_items(request, user=0):
    return account_views.my_custom_404_view(request)
    page_user_prof = UserProfile.objects.get(id=user)
    likes_shelf = page_user_prof.likes_shelf
    feed = WishlistItemsFeed(request, {"shelf": likes_shelf.id}, user=page_user_prof, **{
        'likes_page': True
    }).generate_items()

    if request.is_ajax():
        feed.ajax_request = True
        return feed.render()
    else:
        return render(request, 'pages/middle_content_only.html', {
            'empty': feed.is_empty,
            'middle' : feed.render() if not feed.is_empty else feed.render_empty(),
            'selected_tab': 'likes',
            'page_user_prof': page_user_prof,
            'page_title': SEO_VALUES['liked_items']['title'],
            'meta_description': SEO_VALUES['liked_items']['meta_desc']
        }, context_instance=RequestContext(request))
#####-----</ Under 'You' Tab >-----#####

####NON RENDERING METHODS
##these are methods that don't render a page
@login_required
def toggle_follow(request, user=0, target=0):
    '''
    this view method toggles following of another user
    @param user - the logged in user
    @param target - the user to start following/unfollow
    '''
    page_user_prof = UserProfile.objects.get(id=user)
    target_user_prof = UserProfile.objects.get(id=target)

    if page_user_prof.is_following(target_user_prof):
        page_user_prof.stop_following(target_user_prof)
    else:
        page_user_prof.start_following(target_user_prof)

    target_influencer = target_user_prof.influencer
    if target_influencer and page_user_prof.brand:
        group, _ = page_user_prof.brand.influencer_groups.get_or_create()
        try:
            mapping = group.influencers_mapping.get(influencer=target_influencer)
            mapping.delete()
        except InfluencerGroupMapping.DoesNotExist:
            group.influencers_mapping.create(influencer=target_influencer)
    return HttpResponse(status=200)


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
        u = bound_form.save()
        if u.blog_name and u.blog_page:
            u.can_set_affiliate_links = True
            u.save()

        return HttpResponse(status=200)
    else:
        return HttpResponse(status=500)

@login_required
@require_http_methods(["POST", "DELETE"])
def modify_shelf(request, user=0, shelf=0):
    shelf = Shelf.objects.get(id=shelf)
    form = ModifyShelfForm(data=request.POST, instance=shelf)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            return redirect(request.GET.get('next')) if request.GET.get('next', None) else HttpResponse(status=200)
        else:
            return HttpResponse(status=500)
    else:
        shelf.delete()
        return HttpResponse(status=200)

@login_required
@require_http_methods(["POST"])
def create_shelf(request, user=0):
    '''
    performed when a user creates a shelf
    @return json string containing the created shelf name and id or a redirect if a 'next' parameter is supplied
    '''
    form = CreateShelfForm(data=request.POST)

    if form.is_valid():
        shelf_name = form.cleaned_data.get('name')
        existing_shelves = Shelf.objects.filter(user_id__userprofile=user, name__iexact=shelf_name, user_created_cat=True)
        if existing_shelves.exists():
            new_shelf = existing_shelves[0]
        else:
            new_shelf = form.save(commit=False)
            new_shelf.user_id = UserProfile.objects.get(id=user).user
            new_shelf.user_created_cat = True
            new_shelf.save()
        return redirect(request.GET.get('next')) if request.GET.get('next') else HttpResponse(content=json.dumps({
            'id': new_shelf.id,
            'name': new_shelf.name
        }))
    else:
        return HttpResponse(status=500)

@login_required
@require_http_methods(["POST"])
def create_shelf_from_links(request, user=0):
    '''
    this method is for creating a shelf from affiliate links
    @return json string containing the url for checking the status of the created task
    '''
    user_prof = UserProfile.objects.get(id=user)
    shelf = request.POST.get('shelf')
    link = request.POST.get('link')

    existing_shelves = Shelf.objects.filter(user_id=user_prof.user, name__iexact=shelf)
    if existing_shelves.exists():
        new_shelf = existing_shelves[0]
    else:
        new_shelf = Shelf.objects.create(user_id=user_prof.user, name=shelf)

    task = create_wishlist_for_url_in_shelf.apply_async([new_shelf, link], queue="blog_import")
    return HttpResponse(content=json.dumps({
        'status_url': reverse('debra.query_views.check_task_status'),
        'task': task.id,
        'shelf': {
            'id': new_shelf.id,
            'name': new_shelf.name,
            'num_items': new_shelf.num_items,
            'img': new_shelf.shelf_img
        }
    }))
