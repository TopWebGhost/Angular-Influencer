'''
this file is for views relating directly to items
'''
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from debra.models import Shelf, UserProfile, ProductModelShelfMap
from debra.constants import LIKED_SHELF, DELETED_SHELF, SEO_VALUES
from debra.widgets import ItemInfo, ShelvesFeed
from debra.forms import AddItemToShelvesForm, AddAffiliateLinkForm
import pdb
import json


def item_info(request, user=0, item=0, seo_version=False):
    '''
    get the detailed information for an item
    '''
    user_prof = UserProfile.objects.get(id=user) if user > 0 else None
    item = ProductModelShelfMap.objects.get(id=item)
    item_info = ItemInfo(request, item, user=user_prof).generate_self()
    if seo_version:
        page_vars = {
            'page_title': SEO_VALUES['seo_product_info']['title'],
            'meta_description': SEO_VALUES['seo_product_info']['meta_desc'],
        }
        page_vars.update(item_info.tpl_vars)
        return render(request, 'pages/seo_only/product_page.html', page_vars)
    else:
        return item_info.render()


####NON RENDERING METHODS
##these are methods that don't render a page
@login_required
@require_http_methods(["POST"])
def hide_from_feed(request, user=0, item=0):
    '''
    this view method is called primarily for brands and allows them to hide items of theirs that
    they dont want appearing on the feed
    '''
    item = ProductModelShelfMap.objects.get(id=item)
    item.show_on_feed = False
    item.save()
    return HttpResponse(status=200)

@login_required
def remove_item_from_shelf(request, user=0, item=0, all_shelves=False):
    '''
    remove a wishlist item from a users shelf
    @param user - the user to remove item from
    @param item - the item to remove
    '''
    user_prof = UserProfile.objects.get(id=user)
    if not ProductModelShelfMap.objects.filter(id=item).exists():
        return HttpResponse(status=200)
    item_shelf = ProductModelShelfMap.objects.get(id=item)
    product = item_shelf.product_model
    add_to_deleted = all_shelves or product.user_created_shelves_on(for_user=user_prof.user).count() == 1

    #add the item to the users Deleted shelf if either the all_shelves flag was set or the item is only on 1 shelf
    if add_to_deleted:
        deleted_items_shelf = Shelf.objects.get_or_create(name=DELETED_SHELF, user_id=user_prof.user, is_public=False)[0]
        deleted_items_shelf.add_item_to_self(product, user_prof, item_shelf)
        product.remove_from_users_shelves(user_prof)
    else:
        #now delete this item shelf mapping
        item_shelf.delete()

    return HttpResponse(status=200)

@login_required
def add_item_to_shelves(request, user=0, item=0):
    '''
    add an item to a user's shelf, or shelves
    @param user - the user to add the item for
    @param item - the ProductModelShelfMap to add to this users shelves
    '''
    print "Here: user: [%s] item: [%s]" % (user, item)
    user_prof = UserProfile.objects.get(id=user)
    pmsm = ProductModelShelfMap.objects.get(id=item)

    if request.method == "POST":
        form = AddItemToShelvesForm(data=request.POST)
        if form.is_valid():
            selected_shelves = form.cleaned_data['shelves']
            json_result = user_prof.add_item_to_shelves(pmsm, selected_shelves)

            return HttpResponse(status=200, content=json.dumps(json_result))
        else:
            return HttpResponse(status=500)
    else:
        item_shelves = ShelvesFeed(request, None, user=user_prof, view_file="add_to_shelves.html", ajax_request=True).generate_item_shelves(pmsm)
        return item_shelves.render()

@login_required
@require_http_methods(["POST"])
def add_affiliate_link(request, user=0, item=0):
    form = AddAffiliateLinkForm(data=request.POST, instance=ProductModelShelfMap.objects.get(id=item))
    if form.is_valid():
        form.save()
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=500, content=json.dumps({'errors': form.errors}))

@require_http_methods(["GET"])
def ga_tracking(request, user=0, item=0):
    '''
    Update::: redirects to home
    this view method renders the view file which will hold the code for ga tracking. This method is pointed to by an <iframe>'s src
    @param user - the UserProfile whose item was clicked
    @param item - the item that was clicked
    '''
    return redirect(reverse('debra.account_views.brand_home'))


    redirect_url = None

    #if the item is not greater then 0, then this view has been called from an iframe and we dont want to redirect anywhere, just track the visit
    if int(item) > 0:
        try:
            item = ProductModelShelfMap.objects.get(id=item)
            redirect_url = item.affiliate_prod_link if item.affiliate_prod_link and item.affiliate_prod_link != 'Nil' else item.backup_prod_link
        except ObjectDoesNotExist:
            redirect_url = reverse('debra.account_views.home')

    return render(request, 'pages/analytics_redirection.html', {
        'redirect_url': redirect_url,
        'blogger': user
    })
