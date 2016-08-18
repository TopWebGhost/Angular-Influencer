from debra.models import Shelf, UserProfile, LotteryPartner, ProductModelShelfMap, Posts, Platform
from debra.forms import ModifyShelfForm, CreateShelfForm, AddItemToShelvesForm, AddAffiliateLinkForm
from debra.constants import LIKED_SHELF, DELETED_SHELF
from debra import helpers as h
from django.shortcuts import render_to_response
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import get_template, render_to_string
from django.template import RequestContext
from itertools import chain, izip_longest
import random
import wr
import pdb

class Widget():
    """
    The base class for all other widgets. This class exposes a method :meth:`debra.widgets.Widget.render` for rendering
    of itself.
    """
    def __init__(self, request, template, tpl_vars={}, ajax_request=False, user=None, admin_view=False):
        """
        :param request: an ``HttpRequest`` instance
        :param template: the path to the template file for this **Widget**.
        :param tpl_vars: a ``dict`` of variables to render the ``template`` with
        :param ajax_request: is this **Widget** being rendered in an ajax request or should we render it to a string
        to be rendered as part of a page
        :param user: a :class:`debra.models.UserProfile` instance
        :param admin_view: is the widget being rendered inside an admin view of a page?
        """
        self.request = request
        self.template = template
        self.tpl_vars = tpl_vars
        self.ajax_request = ajax_request
        self.user = user
        self.admin_view = admin_view

        self.public_view = request.user.is_anonymous()
        self.brand = self.user and self.user.brand

    def render(self):
        """
        :return: either a ``HttpResponse`` instance or a string depending on whether or not this **Widget** is being rendered for an ajax request or as part of a page at load time

        A method for a widget to render itself.
        """
        #if we have a user, the tpl_vars['page_user_prof'] should be popuplated
        if self.user:
            self.tpl_vars['page_user_prof'] = self.user

        self.tpl_vars['admin_view'] = self.admin_view

        if self.ajax_request:
            return render_to_response(self.template, self.tpl_vars, context_instance=RequestContext(self.request))
        else:
            return get_template(self.template).render(RequestContext(self.request, self.tpl_vars))


class Feed(Widget):
    """
    a **Feed** is a type of **Widget** which encapsulates the rendering and behavior of a list of items
    """
    def __init__(self, request, view_file, ajax_request=False, user=None, admin_view=False):
        """
        no additional parameters to constructor
        """
        Widget.__init__(self, request, view_file, ajax_request=ajax_request, user=user, admin_view=admin_view)
        self.items = []

    @property
    def is_empty(self):
        """
        :return: True if this **Feed** is empty, False otherwise
        """
        return len(self.items) == 0

    def render_empty(self):
        """
        :return: the result of rendering this **Feed** in its empty form
        """
        self.tpl_vars['empty'] = True
        return self.render()


class ShelvesFeed(Feed):
    """
    This **Feed** type is for rendering a feed of shelves. The available view files we have for this rendering are:

    * add_to_shelves.html - rendered in the popup for adding an item to a user's shelf(s)
    * bookmarklet_shelves.html - rendered in the bookmarklet as the users' shelves
    * collage_shelves.html - rendered in the *collage* widget as the first step, where the user chooses the shelf to make collage from
    * my_shelves.html - rendered in the *my shelves* page as the only content of the page
    * side_bar.html - <not currently used>
    """
    def __init__(self, request, filter, view_file='side_bar.html', ajax_request=False, user=None, qs=None, extra_context={}):
        """
        :param request: an ``HttpRequest`` instance
        :param filter: the filter to apply to results. This will be a :class:`debra.models.Shelf` id if given.
        :param view_file: the file to render results into.
        :param ajax_request: True if the ``request`` is an ajax request, False otherwise
        :param user: a :class:`debra.models.UserProfile` instance
        :param qs: a ``QuerySet`` of :class:`debra.models.Shelf` to render into the specified ``view_file``
        :param extra_context: a ``dict`` of extra template variables to apply to rendering (in addition to those defined
        internally by this **ShelvesFeed**
        """
        Feed.__init__(self, request, '{base}{file}'.format(base='widgets/shelves_feed_views/', file=view_file),
                      ajax_request=ajax_request, user=user)

        self.tpl_vars = {
            'shelves': qs,
            'likes_shelf': Shelf.objects.get_or_create(user_id=self.user.user, name__iexact=LIKED_SHELF)[0],
            'deleted_shelf': Shelf.objects.get_or_create(user_id=self.user.user, name__iexact=DELETED_SHELF)[0],
            'filter': int(filter) if filter else None
        }
        self.tpl_vars.update(extra_context)

    def generate_item_shelves(self, item, extra_context={}):
        """
        :param item: the :class:`debra.models.ProductModelShelfMap` instance that a user wants to add to their shelves.
        :param extra_context: a ``dict`` of extra template variables to render this **ShelvesFeed** with
        :return: this **ShelvesFeed**

        this method is used primarily to generate the tpl_vars for the add_to_shelves.html view file. This method overrides
        the default template variables with a ``dict`` containing the following keys:

        * item - the ``item`` passed into this method
        * add_to_shelves_form - an instance of :class:`debra.forms.AddItemToShelvesForm`.
        * create_shelf_form - an instance of :class:`debra.forms.CreateShelfForm`.
        * added_shelves - a ``QuerySet`` of :class:`debra.models.Shelf` that belong to this **ShelvesFeed**'s user and the item is on
        * unadded_shelves - inverse of ``added_shelves``
        """
        # if the user already has a wishlist item with the same product model on their shelves, use that item going forward
        added_shelves = item.product_model.shelves_on(for_user=self.user.user).filter(user_created_cat=True).order_by("name")
        self.tpl_vars = {
            'item': item,
            'add_to_shelves_form': AddItemToShelvesForm(),
            'create_shelf_form': CreateShelfForm(),
            'added_shelves': added_shelves,
            'unadded_shelves': self.user.user_created_shelves.exclude(id__in=[shelf.id for shelf in added_shelves]).order_by("name")
        }
        self.tpl_vars.update(extra_context)

        return self

class WishlistItemsFeed(Feed):
    """
    The **WishlistItemsFeed** is used for displaying a **Feed** of :class:`debra.models.ProductModelShelfMap`. The
    available files we have for rendering are:

    * feed_items.html - a grid of :class:`debra.models.ProductModelShelfMap`, this is used in various places
    """
    class FeedItem():
        """
        A feed item is an encapsulation of an item in the feed, which may be displayed in a different way depending on the
        type of item it is (i.e. Twitter tweet, Instagram Page, Blog post, etc). The available files we have for rendering
        are:

        * blog_post.html - renders a :class:`debra.models.Posts` instance having ``platform_name=='Blogspot' or platform_name=='Wordpress' or platform_name=='Custom'``
        * collage_product.html - renders a single product shown in the feed of items when picking items for a *carousel* or *collage*
        * instagram.html - renders an :class:`debra.models.Posts` instance having ``platform_name=='Instagram'``
        * product.html - renders an instance of a :class:`debra.models.ProductModelShelfMap`
        * tweet.html - renders an :class:`debra.models.Posts` instance having ``platform_name=='Twitter'``
        """
        POST = "post"
        PRODUCT = "product"

        def __init__(self, item, request, users_feed=False, tpl=None):
            """
            :param item: either a :class:`debra.models.ProductModelShelfMap` or :class:`debra.models.Posts` instance to render
            :param request: an instance of a ``HttpRequest``
            :param users_feed: if True, the user is viewing their own feed, False means they're looking at someone elses feed
            or the *inspiration feed*
            :param tpl: the name of the template file to use for rendering. If not set, the tpl is dynamically set based on the ``item`` type.
            """
            self.item = item
            self.request = request
            self.users_feed = users_feed
            self.tpl = tpl
            self.tpl_base = "widgets/items_feed_views/feed_item_views/"

        def item_type(self):
            """
            :return: a string representing the type of this **FeedItem**'s item
            """
            try:
                noop = self.item.platform
                return self.POST
            except AttributeError:
                return self.PRODUCT

        def render(self):
            """
            :return: this **FeedItem**'s item rendered to a string
            """
            item_type = self.item_type()
            tpl = ''
            context = {
                'item': self.item,
                'user': self.item.influencer.shelf_user.userprofile if item_type == self.POST else self.item.user_prof,
                'users_feed': self.users_feed
            }

            if item_type == self.POST:
                platform_name = self.item.platform.platform_name

                if platform_name == "Twitter":
                    tpl = 'tweet.html'
                elif platform_name == "Instagram":
                    tpl = 'instagram.html'
                elif self.item.post_type == 'blog':
                    tpl = 'blog_post.html'
                    context['post_tags'] = self.item.brand_tags.split(',') if self.item.brand_tags else []
                    context['products'] = self.item.pmsms_for_self
            else:
                tpl = 'product.html'
                context['item_owner'] = self.item.get_original_instance().user_prof

            tpl = self.tpl or tpl #use the passed template if it was provided

            return render_to_string('{base}{tpl}'.format(base=self.tpl_base, tpl=tpl), context,
                                    context_instance=RequestContext(self.request))


    def __init__(self, request, filter=None, item_tpl=None, ajax_request=False, user=None, admin_view=False, **kwargs):
        """
        :param request: an ``HttpRequest`` instance.
        :param filter: dictionary of filters to apply to the items in this **WishlistItemsFeed**.
        :param item_tpl: if set, items will be rendered into this template file rather then the one dynamically generated on **FeedItem** type.
        :param ajax_request: if True, then this is an ajax request.
        :param user: a :class:`debra.models.UserProfile` instance.
        :param admin_view: if True, this is an admin view of a **WishlistItemsFeed**.

        Summary of supported filters:
        * "shelf" - id of a :class:`debra.models.Shelf` to filter by.
        * "type" - one of "all", "post", "instagram", "product" to filter item type.
        """
        Feed.__init__(self, request, "widgets/items_feed_views/feed_items.html", ajax_request=ajax_request, user=user, admin_view=admin_view)
        self.filter = filter or {}
        self.item_tpl= item_tpl
        self.likes_page = kwargs.get('likes_page', None)

    @property
    def is_empty(self):
        """
        :return: True if the feed is empty and there is no filter and this isn't an ajax request, else False
        """
        return self.user and not self.ajax_request and not self.filter and len(self.items) == 0

    def generate_items(self, qs=None):
        """
        :param qs: a ``QuerySet`` of :class:`debra.models.ProductModelShelfMap`, if this is set then use this for generating ``self.items``, otherwise our logic is encapsulated
        :return: this **WishlistItemsFeed**
        """
        filtered_shelf = None
        type_filter = self.filter.get('type', None)
        shelf_filter = self.filter.get('shelf', None)

        if qs:
            self.items = [self.FeedItem(it, self.request, tpl=self.item_tpl) for it in qs]
        else:
            if self.user:
                logged_in_user = h.user_is_logged_in_user(self.request, self.user)
                if shelf_filter:
                    filtered_shelf = Shelf.objects.get(id=shelf_filter)
                    self.items = [self.FeedItem(it, self.request, users_feed=logged_in_user, tpl=self.item_tpl) for it in
                                  ProductModelShelfMap.objects.filter(shelf=filtered_shelf,
                                                                      is_deleted=False,
                                                                      img_url_feed_view__isnull=False)]
                else:
                    shelfed_items = list(self.user.shelfed_items(has_image=True, unique=True).prefetch_related('original_instance_pointer', 'original_instance_pointer__user_prof'))
                    posts = list(Posts.objects.filter(influencer__shelf_user__userprofile=self.user).\
                                               filter(platform__platform_name__in=Posts.PLATFORMS_ON_FEED).\
                                               select_related('platform', 'influencer__shelf_user__userprofile'))
                    feed_items = [self.FeedItem(it, self.request, users_feed=logged_in_user, tpl=self.item_tpl) for it in shelfed_items + posts]
                    self.items = sorted(feed_items, key=lambda fi: fi.item.added_datetime if fi.item_type() == fi.PRODUCT else fi.item.create_date, reverse=True)

            else:
                MAX_TO_SHOW = 800

                #tuple goes: twitter, instagram, blog
                post_tuples = Posts.to_show_on_feed(to_show=MAX_TO_SHOW)

                feed_products = ProductModelShelfMap.all_to_show_on_feed(to_show=MAX_TO_SHOW)
                distinct_feed_products = ProductModelShelfMap.distinct_product_model(feed_products).prefetch_related('original_instance_pointer', 'original_instance_pointer__user_prof')
                products = list(distinct_feed_products)

                for product, posts_tup in izip_longest(products, post_tuples, fillvalue=None):
                    if posts_tup is None:
                        random_item = product
                    else:
                        random_item = None
                        while random_item is None:
                            random_item = random.choice([product, random.choice(posts_tup)])

                    if type_filter and type_filter != "all":
                        try:
                            ptype = random_item.platform.platform_name
                            if ptype == "Instagram":
                                ptype = "instagram"
                            elif ptype in Platform.BLOG_PLATFORMS:
                                ptype = "post"
                        except AttributeError:
                            ptype = "product"
                        if type_filter != ptype:
                            continue


                    self.items.append(self.FeedItem(random_item, self.request, tpl=self.item_tpl))

        self.tpl_vars = {
            'feed_items': self.items,
            'filtered': shelf_filter,
            'filtered_shelf': filtered_shelf,
            'likes_page': self.likes_page
        }

        return self


class UserFeed(Feed):
    """
    The **UserFeed** shows a **Feed** of :class:`debra.models.UserProfile` (or some other model object that represents a user).

    The available files we have for rendering are;

    * ajax_blogger_info.html - used on the *search* page, this view file shows additional info about an :class:`debra.models.Influencer` in a toggle-panel
    * follows.html - not currently used, but was used on the *following* and *followers* pages.
    * search_bloggers.html - the primary feed on the *search* page, this view file renders a feed of :class:`debra.models.Influencer`
    * trending_brands.html - the primary feed on the *trending brands* page, this view file renders a feed of :class:`debra.models.UserProfile` that represent :class:`debra.models.Brand`
    * trendsetters.html - the primary feed on the *trendsetters* page, this view file renders a feed of :class:`debra.models.UserProfile` we've deemed 'too cool for skool'
    """
    # different types of UserFeed's
    BRANDS_FEED = "brand_feed"
    TRENDSETTERS_FEED = "trendsetters_feed"

    def __init__(self, request, view_file="trendsetters.html", ajax_request=False, user=None, qs=None, extra_context={}):
        """
        :param request: an ``HttpRequest`` instance
        :param view_file: the name of the file to use for rendering the items in this **UsersFeed**
        :param ajax_request: if True, this is an ajax request
        :param user: an instance of :class:`debra.models.UserProfile`
        :param qs: a ``QuerySet`` of :class:`debra.models.Influencer` or :class:`debra.models.UserProfile`, if set, this is used as the primary variable in template rendering.
        :param extra_context: a ``dict`` of extra variables to supply to the template when rendering
        """
        Feed.__init__(self, request, 'widgets/users_feed_views/{file}'.format(file=view_file), ajax_request=ajax_request, user=user)

        if qs:
            self.tpl_vars = {
                'users': qs
            }
            self.tpl_vars.update(extra_context)

    #####-----#####-----< Public API >-----#####-----#####
    def set_qs(self, qs):
        """
        :param qs: the ``QuerySet`` to render this **UsersFeed** template with
        :return: this **UsersFeed**
        """
        self.tpl_vars['users'] = qs
        return self
    #####-----#####-----</ Public API >-----#####-----#####

    #####-----#####-----< Trendsetters >-----#####-----#####
    def generate_trendsetters(self):
        """
        :return: this **UsersFeed**


        generate the template variables to be used when loading the *trendsetters* page.
        We group the trendsetters into two buckets: followed and unfollowed, for speedup purposes
        """
        trendsetters = UserProfile.get_trendsetters().order_by('-num_followers')
        if self.public_view:
            self.generate_public_items(trendsetters, self.TRENDSETTERS_FEED)
        else:
            followed_trendsetters_map = self.request.user.userprofile.get_following.filter(following__in=trendsetters)
            self.items = [{'is_followed': trendsetter.id in [follow_map.following.id for follow_map in followed_trendsetters_map],
                           'obj': trendsetter} for trendsetter in trendsetters]

        self.tpl_vars = {'trendsetters': self.items}
        return self
    #####-----#####-----</ Trendsetters >-----#####-----#####


    def generate_giveaway_partners(self):
        '''
        TEMPORARY METHOD!
        '''

        partners = LotteryPartner.objects.all().order_by('-partner__num_followers')
        if self.public_view:
            self.generate_public_items([partner.partner for partner in partners], self.TRENDSETTERS_FEED)
        else:
            followed_partners_map = self.request.user.userprofile.get_following.filter(following__in=[partner.partner for partner in partners])
            self.items = [{'is_followed': partner.partner.id in [follow_map.following.id for follow_map in followed_partners_map],
                           'obj': partner.partner} for partner in partners]

        self.tpl_vars = {'trendsetters': self.items}
        return self

    def generate_plebians(self):
        """
        :return: this **UsersFeed**

        Not currently used
        """
        self.items = [{'is_followed': False,
                       'obj': up} for up in UserProfile.get_plebians()]
        self.tpl_vars = {'trendsetters': self.items, 'potential_trendsetters': True}
        return self


    #####-----#####-----< Trending Brands >-----#####-----#####
    def generate_trending_brands(self):
        """
        :return: this **UsersFeed**

        get all brands that are currently trending, perform optimization method similar to the :meth:`debra.widgets.UsersFeed.generate_trendsetters` method.
        """
        #if in admin view, we care about inactive brands, everyone else cares about active brands
        brand_users = UserProfile.objects.filter(brand__isnull=False).select_related('brand').order_by('-brand__num_shelfers')
        brand_users = brand_users if self.admin_view else brand_users.filter(brand__is_active=True)
        if self.public_view:
            self.generate_public_items(brand_users, self.BRANDS_FEED)
        else:
            followed_brands_map = self.request.user.userprofile.get_following.filter(following__in=brand_users)
            self.items = [(up.brand, {'is_followed': up.id in [follow_map.following.id for follow_map in followed_brands_map],
                                      'obj': up}) for up in brand_users]

        self.tpl_vars = {'brands_profs': self.items}
        return self
    #####-----#####-----</ Trending Brands >-----#####-----#####


    #####-----#####-----< Followers/Folowing >-----#####-----#####
    def generate_followers(self):
        """
        :return: this **UsersFeed**

        Not currently used
        """
        if self.public_view:
            self.items = self.user.followed_by_list_builder(self.user)
        else:
            #followed_by_list_builder has some important speed boosters
            self.items = self.user.followed_by_list_builder(self.request.user.userprofile)

        self.tpl_vars = {'follows': self.items,
                         'followers_page': True}
        return self

    def generate_following(self):
        """
        :return: this **UsersFeed**

        Not currently used
        """
        self.items = self.user.following_list_builder(self.user if self.public_view else self.request.user.userprofile)

        self.tpl_vars = {'follows': self.items}
        return self
    #####-----#####-----</ Followers/Folowing >-----#####-----#####

    #####-----#####-----< Public Version of a UserFeed >-----#####-----#####
    def generate_public_items(self, queryset, feed_type):
        """
        :param queryset: a ``QuerySet`` of :class:`debra.models.UserProfile` to render the public feed with
        :param feed_type: the type of feed being generated (one of ``self.TRENDSETTERS_FEED`` or ``self.BRANDS_FEED``)

        this method generates the public items for a UserFeed
        """
        if feed_type == self.TRENDSETTERS_FEED:
            self.items = [{'is_followed': False,
                           'obj': up} for up in queryset]
        else:
            self.items = [(up.brand, {'is_followed': False,
                                      'obj': up}) for up in queryset]
    #####-----#####-----</ Public Version of a UserFeed >-----#####-----#####


class ItemInfo(Widget):
    """
    The ItemInfo widget shows the user a detailed display of a clicked item.
    """
    def __init__(self, request, item, user=None):
        """
        :param request: an ``HttpRequest`` instance
        :param item: the :class:`debra.models.ProductModelShelfMap` instance we're showing detailed info for
        :param user: the :class:`debra.models.UserProfile` instance currently viewing the item
        """
        Widget.__init__(self, request, 'widgets/item_info_dynamic.html', ajax_request=True, user=user)
        self.item = item
        self.request = request

    def generate_self(self):
        """
        :return: this **ItemInfo** widget

        Generate the template variables for this **ItemInfo** widget.
        TODO: allow for injection of parameters.
        """
        model = self.item.product_model
        user_prof = self.item.user_prof
        original_shelfer = self.item.get_original_instance().user_prof

        SPOOF_AMOUNT = self.item.added_datetime.day #pseudo-random, remove once we have enough data to not have to spoof

        # these are cascading levels of filtering for the shelf in order of desiribality (we'd like if we could stop after the first filter),
        # just to make sure we get some value into the template
        public_shelves_on = model.public_shelves_on()
        shelf = public_shelves_on[0] if public_shelves_on.exists() else model.shelves_on()[0] #dont crash

        self.tpl_vars = {
            'item'          : self.item,
            'is_users_item' : original_shelfer.id == user_prof.id,
            'is_users_feed' : self.user.user == self.request.user if self.user else False,
            'num_reshelves' : public_shelves_on.count() + SPOOF_AMOUNT,
            'shelfer_prof'  : user_prof,
            'original_shelfer': self.item.get_original_instance().user_prof,
            'shelfer_shelf' : shelf, #get the first shelf that the shelfer added this item to
            'similar_items' : self.item.similar_items,
            'model'         : model,
            'brand'         : model.brand,
            'supported_store': self.item.from_supported_store,
            'create_shelf_form': CreateShelfForm(),
            'add_affiliate_link_form': AddAffiliateLinkForm(instance=self.item)
        }

        return self
