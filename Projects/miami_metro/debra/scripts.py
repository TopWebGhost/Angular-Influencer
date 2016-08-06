'''
this file is for one-off and miscellaneous scripts
'''
from celery.decorators import task
from debra.es_requests import make_es_head_request

from debra.models import *
from debra.constants import *
from debra import helpers as h
from debra import brand_helpers
from masuka.image_manipulator import get_distribution, thumbnail, create_images_for_wishlist_item
from debra.constants import SHELF_BRAND_USER, SHELF_BRAND_PASSWORD, ADMIN_TABLE_INFLUENCER_INFORMATIONS
from django.utils.http import urlquote
from django.contrib.auth.models import User
from debra import db_util
from django.db.models import Count
from boto.s3.connection import S3Connection
from django.conf import settings
import requests
import lxml.html
import lxml.etree
import pdb
import re
import datetime
from xpathscraper import utils
from django.db.models import Q
import baker
from collections import defaultdict
import pprint
from platformdatafetcher.pbfetcher import DefaultPolicy
from platformdatafetcher.geocoding import normalize_location
from platformdatafetcher.fetchertasks import _do_fetch_platform_data
from bulk_update.helper import bulk_update

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan

#####-----< Helpers >-----#####
def _image_manipulator_emulator(image_view_type):
    '''
    wishlist items are now going to have a thumbnail img view, so we need to generate these images
    '''
    NUM_BUCKETS = 20
    # each different type of image view has some specific parameters for saving, buckets, etc.
    IMAGE_TYPE_MAPPING = {
        'panel_view': {
            'tmp_name': '/tmp/for_panel.jpg',
            'key_name_prefix': 'v2-img-for-panel-',
            'size': (450, 450),
        },
        'thumbnail_view': {
            'tmp_name': '/tmp/for_thumbnail.jpg',
            'key_name_prefix': 'v2-img-for-thumbnail-',
            'size': (150, 150)
        },
        'compressed_feed_view': {
            'tmp_name': '/tmp/for_compressed.jpg',
            'key_name_prefix' : 'v2-img-for-feed-compressed-',
            'size': None, #we use special function for feed view
        },
    }

    expires = datetime.date.today() + datetime.timedelta(days=(365))
    conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)

    image_params = IMAGE_TYPE_MAPPING[image_view_type]
    for i,item in enumerate(WishlistItem.objects.all().order_by('-id')):
        print "%d'th item url %s" % (i, item.img_url)
        if not item.img_url:
            continue
        if not (item.img_url.startswith('http')):
            item.img_url = 'http:' + item.img_url
            print "added http: to img_url, result %s " % item.img_url
        if len(item.img_url) > 256:
            print "URL too long: %s %d " % (item.img_url, len(item.img_url))
            continue
        out_panel = image_params['tmp_name']
        try:
            img = thumbnail(item.img_url, image_params['size'])
            img.save(out_panel, 'jpeg')
        except IOError:
            print "Error with %s " % item.id
            item.img_url = None
            item.save()
            continue

        index = item.id % NUM_BUCKETS
        bucket = conn.create_bucket(str(index)+'-theshelf-item-images-bucket')

        key_name = image_params['key_name_prefix'] + item.img_url.replace('/', '_')
        new_key = bucket.new_key(key_name)
        new_key.set_contents_from_filename(out_panel)
        new_key.set_acl('public-read', headers={'Cache-Control': 'max-age=31536000', 'Expires': expires})

        image_view_url = get_distribution(bucket) + '/' + urlquote(key_name)
        if image_view_type == 'panel_view':
            item.img_url_panel_view = image_view_url
        elif image_view_type == 'thumbnail_view':
            item.img_url_thumbnail_view = image_view_url
        elif image_view_type == 'compressed_feed_view':
            item.img_url_feed_compressed

        item.save()
#####-----</ Helpers >-----#####

def migrate_old_to_new():
    '''
    a one off function to copy user_operations table data from a snapshot of an old database
    into the wishlist_items table which now holds a foreign key relation to the product_model table

    PROBABLY NEVER NEEDS TO BE RUN AGAIN BUT IS A GOOD EXAMPLE OF USING MULTIPLE DB's
    '''
    #1 : iterate over the items in the old DB's WishlistItem table
    #1a : for each item, get the items wishlist_item_id, img_url from user_ops, and product_model
    #1b : store this data in an array
    #2 : loop over the array built in 1
    #2a : for each item, get the wishlist item in the new database
    #2b : set that items img url and product_model
    import psycopg2

    conn_string = "host='ec2-54-225-123-71.compute-1.amazonaws.com' dbname='d3dov7mo717n4v' \
                   user='hhizcoynzfygzy' password='i8QVGqwnqfZ2zDnYQOltBMlFkp'"
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = psycopg2.connect(conn_string)

    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor()

    # execute our Query
    cursor.execute("SELECT debra_wishlistitem.id,debra_useroperations.color,debra_useroperations.size, debra_useroperations.datetime \
    FROM debra_wishlistitem INNER JOIN debra_useroperations ON debra_wishlistitem.user_selection_id=debra_useroperations.id")

    print "executed query against old db"
    # for each wishlist item id,  get the corresonding wl_item in our new database and modify that item
    for (wl_id, color, size, datetime) in cursor.fetchall():
        wl_item = WishlistItem.objects.get(id=wl_id)

        wl_item.color = color
        wl_item.size = size
        wl_item.added_datetime = datetime
        wl_item.save()


def copy_property_to_field():
    '''
    a function to copy the data from the property of a model into a field
    '''
    from debra.models import Shelf

    shelves = Shelf.objects.all()
    for shelf in shelves:
        shelf.num_items = len(shelf.items_in_shelf)
        shelf.save()


def resize_feed_images():
    '''
    we want to use the new 230 x [variable height] images for the feed, so run them through the image manipulation
    function we just created
    '''
    from masuka.image_manipulator import feed_transform, get_distribution
    from django.conf import settings
    from debra.models import WishlistItem
    from django.utils.http import urlquote
    from boto.s3.connection import S3Connection
    import datetime

    NUM_BUCKETS = 20
    expires = datetime.date.today() + datetime.timedelta(days=(365))
    conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)

    for item in WishlistItem.objects.all():
        #junk from masuka.image_manipulator
        out_feed = "/tmp/for_feed.jpg"
        img = feed_transform(item.img_url)
        img.save(out_feed, 'jpeg')

        index = item.id % NUM_BUCKETS
        bucket = conn.create_bucket(str(index)+'-theshelf-item-images-bucket')

        key_name = 'v2-img-for-feed-' + item.img_url.replace('/', '_')
        new_key = bucket.new_key(key_name)
        new_key.set_contents_from_filename(out_feed)
        new_key.set_acl('public-read', headers={'Cache-Control': 'max-age=31536000', 'Expires': expires})
        #end junk

        item.img_url_feed_view = get_distribution(bucket) + '/' + urlquote(key_name)
        item.save()


def copy_shelf_img_to_field():
    '''
    a function to copy the calculated first img of all shelves to the new shelf_img field
    '''
    for i,shelf in enumerate(Shelf.objects.filter(is_deleted=False).all().order_by('id')):
        print "%d'th shelf" % i
        shelf.shelf_img = shelf.first_img
        shelf.save()


def change_user_names_to_none():
    '''
    a function to go back and change all user names in our database that are "Your Name?" to None
    '''
    bad_names = UserProfile.objects.filter(name__iexact="Your Name?").all().order_by("id")
    for i,bad_name in enumerate(bad_names):
        print "%d'th bad name" % i
        bad_name.name = None
        bad_name.save()


def shift_collage_images():
    '''
    a function to shift all the collage images from 5 - 9 over to the right one, because we are adding a new collage
    image to the middle of the collage
    '''
    for i,u in enumerate(UserProfile.objects.all().order_by('-id')):
        print "%d'th user" % i
        u.image10 = u.image9
        u.image9 = u.image8
        u.image8 = u.image7
        u.image7 = u.image6
        u.image6 = u.image9
        u.save()


def remove_nil():
    '''
    a function to remove nil values from an objects field
    '''
    values_to_remove = ['Nil', '', 'None']
    for i,it in enumerate(Brands.objects.filter(icon_id__in=values_to_remove).all().order_by('-id')):
        print "%d'th item" % i
        it.icon_id= None
        it.save()

def remove_dangling_wishlistitems():
    '''
    a function to remove all wishlist items that do not appear in any shelf. These shouldn't even exist in the first
    place, so this is sort of a cleanup function.
    '''
    invalid_wi = set()
    for i, w in enumerate(WishlistItem.objects.all().order_by('-id')):
        print "%d'th item " % i
        maps = WishlistItemShelfMap.objects.filter(wishlist_item = w)
        if len(maps) == 0:
            invalid_wi.add(w)
    print "GOT %d dangling wishlist_items" % len(invalid_wi)
    for w in invalid_wi:
        w.is_deleted = True
        w.save()

    return len(invalid_wi)


def import_external_profile_images():
    '''
    History: earlier, we allowed users to upload urls of their profile images, but we have stopped doing that now.
            So, we now have mixed types of urls: some poitning to our s3 buckets and some pointing to outside.
            This method makes them consistent by importing all external images

    This also updates the profile_img url of the UserProfiles who still have old profile img of form: https://s3.amazonaws.com/profile-images-theshelf/<id>.jpg
    to https://s3.amazonaws.com/profile-images-theshelf/<id>_profile_img.jpg
    '''
    from debra import settings
    import sys
    import urllib
    from boto.s3.connection import S3Connection
    import cStringIO
    from PIL import Image, ImageOps

    profs = UserProfile.objects.filter(profile_img_url__isnull=False).exclude(profile_img_url__contains = \
                                        'profile_img.jpg').exclude(profile_img_url__contains = \
                                        '/mymedia/site_folder/images/global/avatar.png').order_by('id')
    conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
    bucket = conn.get_bucket('profile-images-theshelf')
    BUCKET_PATH_PREFIX = "https://s3.amazonaws.com/"

    for i, prof in enumerate(profs):
        try:
            f1 = urllib.urlopen(prof.profile_img_url)
            im1 = cStringIO.StringIO(f1.read())
            img = Image.open(im1)
            image_name = str(prof.user.id) + '_profile_img.jpg'
            new_key = bucket.new_key(image_name)
            file_path = "/tmp/%s_profile_image" % prof.user.id
            img.save(file_path, 'jpeg')
            new_key.set_contents_from_filename(file_path)
            new_key.set_acl('public-read')
            prof.profile_img_url = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + image_name
            prof.save()
        except:
            print "oops, had problem with %s for profile %s, exception %s" % (prof.profile_igm_url, prof, str(sys.exc_info()))
            pass
        print "[%d] Done with %s %s" % (i, prof.profile_igm_url, prof)

def create_thumbnail_images():
    '''
    wishlist items are now going to have a thumbnail img view, so we need to generate these images
    '''
    _image_manipulator_emulator('thumbnail_view')


def recreate_panel_images():
    '''
    some of our panel images got wonked, recreate them
    '''
    _image_manipulator_emulator('panel_view')


def make_shelves_public():
    '''
    our shelves are private by default. They should be public.
    '''
    for i,shelf in enumerate(Shelf.objects.all().order_by('-id')):
        print "%d'th shelf" % i
        shelf.is_public = True
        shelf.save()


def populate_shelf_brand_pointer():
    '''
    we just added a Brands foreign key to shelf. Populate that foreign key by doing this algorithm:
    1. Loop over Shelf objects
    2. For each shelf, check if that shelf's name matches a Brands' name
    3. If so, make that shelf point to that brand
    '''
    for i,shelf in enumerate(Shelf.objects.all().order_by('-id')):
        print "%d'th shelf" % i
        shelf_name = shelf.name
        for j,brand in enumerate(Brands.objects.all().order_by('-id')):
            print "%d'th brand" % j
            if brand.name == shelf_name:
                shelf.brand = brand
                shelf.save()
                break

def recalculate_num_items_shelved():
    '''
    our num of items shelved denormalized field got all wacked up. This script recalculates that number for each user
    '''
    users = UserProfile.objects.all().order_by('-id')
    for i,user in enumerate(users):
        print "%dth user" % i
        num_items = WishlistItem.objects.filter(user_id=user.user, is_deleted=False).count()
        user.num_items_in_shelves = num_items
        user.save()

def call_denormalization(model_type):
    '''
    call the denormalization method on objects
    '''
    objects = []
    if model_type == 'brands':
        objects = Brands.objects.all().order_by('-id')
    elif model_type == 'users':
        objects = UserProfile.objects.all().order_by('-id')
    elif model_type == 'shelf':
        objects = Shelf.objects.all().order_by('-id')
    for i,o in enumerate(objects):
        print '%dth obj' % i
        o.denormalize()


def create_brand_shelf_profiles():
    '''
    we need to create TheShelf management accounts for brands, which can later be claimed by brands
    '''
    brands = Brands.objects.exclude(id__in=[up.brand.id for up in UserProfile.objects.filter(brand__isnull=False).select_related('brand')]).order_by('-id')
    for i,brand in enumerate(brands):
        print '%dth brand name %s domain %s' % (i, brand.name, brand.domain_name)
        if User.objects.filter(username=SHELF_BRAND_USER(brand.name)).exists():
            print "Have %d users " % User.objects.filter(username=SHELF_BRAND_USER(brand.name)).count()
            user = User.objects.filter(username=SHELF_BRAND_USER(brand.name))[0]
        else:
            user = User.objects.create_user(username=SHELF_BRAND_USER(brand.name), email=SHELF_BRAND_USER(brand.name),
                                            password=SHELF_BRAND_PASSWORD)
        user_prof, created = UserProfile.objects.get_or_create(user=user)
        user_prof.brand = brand
        user.is_active = True
        user.save()

        user_prof.create_brand_img()

def remove_trailing_com():
    '''
    a script to remove the trailing /.com from the Brand users
    '''
    users = UserProfile.objects.filter(brand__isnull=False)
    for i,user_p in enumerate(users):
        print '%dth user' % i
        user = user_p.user
        user.username = re.sub(r'/\.com$', ".toggle", user.username)
        user.email = user.username
        user.save()

def create_brand_collage():
    '''
    a script to create the collage for a brand
    '''
    user_brands = UserProfile.objects.filter(brand__isnull=False)
    for i,user_p in enumerate(user_brands):
        print '%dth user' % i
        brand = user_p.brand
        brand_products = ProductModel.objects.filter(brand=brand)
        wl_items = []
        for prod in brand_products:
            items = WishlistItem.objects.filter(product_model=prod, img_url_panel_view__isnull=False)
            if len(items) > 0:
                wl_items.append(items[0])

            if len(wl_items) > 10:
                break

        user_p.image1 = wl_items[0].img_url_panel_view if len(wl_items) > 0 else None
        user_p.image2 = wl_items[1].img_url_panel_view if len(wl_items) > 1 else None
        user_p.image3 = wl_items[2].img_url_panel_view if len(wl_items) > 2 else None
        user_p.image4 = wl_items[3].img_url_panel_view if len(wl_items) > 3 else None
        user_p.image5 = wl_items[4].img_url_panel_view if len(wl_items) > 4 else None
        user_p.image6 = wl_items[5].img_url_panel_view if len(wl_items) > 5 else None
        user_p.image7 = wl_items[6].img_url_panel_view if len(wl_items) > 6 else None
        user_p.image8 = wl_items[7].img_url_panel_view if len(wl_items) > 7 else None
        user_p.image9 = wl_items[8].img_url_panel_view if len(wl_items) > 8 else None
        user_p.image10 = wl_items[9].img_url_panel_view if len(wl_items) > 9 else None

        user_p.save()

def move_followers_to_user():
    '''
    we need to move the calculated number of shelfers/followers for brands onto their associated userprofiles
    '''
    user_brands = UserProfile.objects.filter(brand__isnull=False).order_by('-id')[230:]
    for i, user_p in enumerate(user_brands):
        print '%dth user' % i
        brand = user_p.brand
        shelfers = [shelf.user_id.userprofile for shelf in brand.users_brand_shelves()]
        for shelfer in shelfers:
            user_p.add_follower(shelfer)


def make_brand_domains_correct():
    '''
    For supported stores, domain is just the name or sometimes the entire url
    For unsupported stores, domain is the start url.
    This scripts corrects these errors.

    And for new brands created now, domain will be correct (updated both modify_shelf.py and account_view.py when a brand signs up.)
    '''
    import urlparse
    all_brands = Brands.objects.all()
    for a in all_brands:
        print "Current domain_name: %s " % a.domain_name
        if a.start_url != "Nil":
            new_domain_name = utils.domain_from_url(a.start_url)
        else:
            if a.domain_name is not None:
                new_domain_name = urlparse.urlsplit(a.domain_name).netloc
        print "New domain_name: %s " % new_domain_name
        a.domain_name = new_domain_name
        a.save()


def remove_duplicate_brands():
    """
    Also move the FK from ProductModel to the unique Brand obj
    """
    all_domain_names = set()
    all_brands = Brands.objects.all()
    for b in all_brands:
        all_domain_names.add(b.domain_name)

    for domain_name in all_domain_names:
        brands = Brands.objects.filter(domain_name=domain_name).order_by('id')
        if len(brands) > 1 and len(domain_name) > 1:
            print "%d duplicates for %s" % (len(brands), domain_name)
            to_keep = brands[0]
            prods = ProductModel.objects.filter(brand=to_keep)
            print "Before: We have %d number of products for brand.id %s " % (len(prods), to_keep.id)
            for b in brands[1:]:
                prods = ProductModel.objects.filter(brand=b)
                for p in prods:
                    p.brand = to_keep
                    p.save()
                b.delete()
            prods = ProductModel.objects.filter(brand=to_keep)
            print "After: We have %d number of products for brand.id %s " % (len(prods), to_keep.id)

    return None

def remove_duplicate_brands2():
    """
    First find all brands that have a duplicate

    Idea is to pick one as the main one and then delete others after correctly migrating their backpointers to the main one.

    The only challenging one is UserProfileBrandPrivilages because it is referenced by a UserProfile. And ultimately, we want
    a single UserProfileBrandPrivilages per Brand.
        => So, we may have to do more here if we have such duplicate brands with each having their own UserProfileBrandPrivilages
        => If these are 0, then we can safely run the code below.
    """
    import collections
    print "Fetching brand names, it can take some time..."
    names = [x[0] for x in Brands.objects.all().only('domain_name').values_list('domain_name')]
    print "OK."
    dups = [x for x, y in collections.Counter(names).items() if y > 1]
    print "I found", len(dups), "duplicated brand domains"

    for domain_name in dups:
        print "Processing", domain_name
        brands = Brands.objects.filter(domain_name=domain_name)
        if brands.filter(blacklisted=False).exists():
            realbrand = brands.filter(blacklisted=False)[0]
        else:
            realbrand = brands[0]
        print "Real brand is", realbrand
        for brand in brands:
            if brand == realbrand:
                continue
            print "Processing", brand
            brand.promorawtext_set.update(store=realbrand)
            brand.promoinfo_set.update(store=realbrand)
            brand.saved_queries.update(brand=realbrand)
            brand.productmodel_set.update(brand=realbrand)
            brand.shelf_set.update(brand=realbrand)
            # TODO: what if this brand also has a UserProfileBrandPrivilages too?
            brand.related_user_profiles.update(brand=realbrand)
            brand.brandmentions_set.update(brand=realbrand)
            brand.influencer_groups.update(owner_brand=realbrand)
            brand.scrapingresultset_set.update(brand=realbrand)
            brand.delete()



def remove_duplicate_shelves(shelf_name):
    '''
    Find all shelves that has duplicates : same named shelf for the same user

    Once we find them, we then pick the first as the canonical shelf,
    and for all others,
        we find all WishlistItemShelfMap that point to these other shelves
        and make them point to the canonical_shelf
    '''
    users = User.objects.all().order_by('id')
    total = users.count()
    for i,user in enumerate(users):
        shelves = Shelf.objects.filter(user_id=user, name=shelf_name)
        print "[User %s] Got %d shelves" % (user, shelves.count())
        if shelves.count() > 1:
            shelves = shelves.order_by('id')
            canonical_shelf = shelves[0]
            for sh in shelves[1:]:
                psmaps = ProductModelShelfMap.objects.filter(shelf=sh)
                psmaps.update(shelf=canonical_shelf)
                sh.delete()
            shelves = Shelf.objects.filter(user_id=user, name=shelf_name)
            print "After cleanup, shelf %s has %d duplicates" % (shelf_name, shelves.count())
        else:
            print "No duplicates found, continuing"
            continue
        print "[%d, %.2f] Done with %s" % (i, i*100.0/total, user)


def update_delete_flags():
    '''
    Find all WishlistItemShelfMaps that that have shelf__is_deleted=True or is_deleted=True
        For these, set is_deleted=True
        And save (or re-save) them so as to trigger their signal handler
    '''
    wmaps = WishlistItemShelfMap.objects.filter(Q(shelf__is_deleted=True) | Q(is_deleted=True))
    for wm in wmaps:
        wm.is_deleted = True
        wm.save()



def cleanup_xps_database():
    """
    Should be done after a new xpath calculation algorithm is implemented.
    ScrapingResult, XPathExpr, ScrapingResultSet, ScrapingResultSetEntry, CorrectValue, and FoundValue
    """
    from xps import models as xps_models

    scraping_results = xps_models.ScrapingResult.objects.all()
    xpathxpr_results = xps_models.XPathExpr.objects.all()
    scraping_results_set = xps_models.ScrapingResultSet.objects.all()
    scraping_results_set_entry = xps_models.ScrapingResultSetEntry.objects.all()
    correct_value = xps_models.CorrectValue.objects.all()
    found_value = xps_models.FoundValue.objects.all()

    print "Found %d entries for ScrapingResult, deleting them now." % xps_models.ScrapingResult.objects.count()
    scraping_results.delete()

    print "Found %d entries for XpathExpr, deleting them now." % xps_models.XPathExpr.objects.count()
    xpathxpr_results.delete()

    print "Found %d entries for ScrapingResultSet, deleting them now." % xps_models.ScrapingResultSet.objects.count()
    scraping_results_set.delete()

    print "Found %d entries for ScrapingResultSetEntry, deleting them now." % xps_models.ScrapingResultSetEntry.objects.count()
    scraping_results_set_entry.delete()

    print "Found %d entries for CorrectValue, deleting them now." % xps_models.CorrectValue.objects.count()
    correct_value.delete()

    print "Found %d entries for FoundValue, deleting them now." % xps_models.FoundValue.objects.count()
    found_value.delete()


def rename_uncategorized():
    '''
    we want to rename our uncategorized shelf to "My Likes"
    '''
    uncategorized = Shelf.objects.filter(user_created_cat=True, name=UNCATEGORIZED_SHELF)
    for i, shelf in enumerate(uncategorized):
        print "{shelf}'th shelf".format(shelf=i)
        shelf.name = LIKED_SHELF
        shelf.save()


def move_category_to_model():
    '''
    we want to move cat1 field data from wishlist item to product model
    '''
    items = WishlistItem.objects.exclude(cat1="Nil").order_by('-id').select_related('product_model')
    for i, item in enumerate(items):
        print "{item}'th item".format(item=i)
        item.product_model.cat1 = item.cat1
        item.product_model.save()


def set_shelf_for_wishlistitem():
    '''
    for wishlist items that are not on user created shelves, have them reside on the LIKE shelf
    '''
    w_all = WishlistItem.objects.filter(user_id__userprofile__brand__isnull=True)
    for w in w_all:
        if not WishlistItemShelfMap.objects.filter(wishlist_item=w, shelf__user_created_cat=True).exists():
            like_shelf, _ = Shelf.objects.get_or_create(name=LIKED_SHELF, user_id=w.user_id)
            WishlistItemShelfMap.objects.get_or_create(wishlist_item=w, shelf=like_shelf)
    return

def populate_product_model_shelf():
    '''
    we want to populate ProductModelShelfMap with a combination of data from WishlistItemShelfMap and WishlistItem
    '''
    wl_item_shelf_maps = WishlistItemShelfMap.objects.all().select_related('wishlist_item', 'wishlist_item__product_model', 'shelf').order_by('id')
    for i, it in enumerate(wl_item_shelf_maps):
        print "{item}'th item".format(item=i)
        wl_item = it.wishlist_item
        shelf = it.shelf

        pmsm_dupls = ProductModelShelfMap.objects.filter(product_model=wl_item.product_model, shelf=shelf)
        if pmsm_dupls.exists():
            pmsm_dupls.delete()

        pmsm = ProductModelShelfMap.objects.create(user_prof=wl_item.user_id.userprofile, shelf=shelf, product_model=wl_item.product_model)
        pmsm.color = wl_item.color
        pmsm.size = wl_item.size
        pmsm.img_url = wl_item.img_url
        pmsm.calculated_price = str(wl_item.calculated_price)
        pmsm.item_out_of_stock = wl_item.item_out_of_stock
        pmsm.savings = str(wl_item.savings)
        pmsm.promo_applied = wl_item.promo_applied
        pmsm.shipping_cost = str(wl_item.shipping_cost)
        pmsm.added_datetime = wl_item.added_datetime
        pmsm.imported_from_blog = wl_item.imported_from_blog
        pmsm.time_price_calculated_last = wl_item.time_price_calculated_last
        pmsm.time_notified_last = wl_item.time_notified_last
        pmsm.notify_lower_bound = str(wl_item.notify_lower_bound)
        pmsm.snooze = wl_item.snooze
        pmsm.bought = wl_item.bought
        pmsm.is_deleted = wl_item.is_deleted
        pmsm.show_on_feed = wl_item.show_on_feed
        pmsm.avail_sizes = wl_item.avail_sizes
        pmsm.img_url_shelf_view = wl_item.img_url_shelf_view
        pmsm.img_url_panel_view = wl_item.img_url_panel_view
        pmsm.img_url_feed_view = wl_item.img_url_feed_view
        pmsm.img_url_thumbnail_view = wl_item.img_url_thumbnail_view
        pmsm.img_url_original = wl_item.img_url_original
        pmsm.affiliate_prod_link = wl_item.affiliate_prod_link
        pmsm.affiliate_source_wishlist_id = wl_item.affiliate_source_wishlist_id
        pmsm.current_product_prize = wl_item.current_product_price

        pmsm.save()


def test_populate_product_model_shelf_script():
    '''
    Checks if the above populate_product_model_shelf script worked.
    For each WishlistItemShelfMap, verify that there exists exactly 1 PMSM corresponding to WishlistItemShelfMap.Shelf
    and WishlistItemShelfMap.WishlistItem.ProductModel
    '''
    wl_item_shelf_maps = WishlistItemShelfMap.objects.all().select_related('wishlist_item', 'wishlist_item__product_model', 'shelf').order_by('id')
    for i, it in enumerate(wl_item_shelf_maps):
        print "{item}'th item".format(item=i)
        wl_item = it.wishlist_item
        shelf = it.shelf
        pmsms = ProductModelShelfMap.objects.filter(product_model=wl_item.product_model, shelf=shelf)
        assert pmsms.exists() and pmsms.count() == 1


def remove_is_deleted_flag():
    '''
    Handling ProductModelShelfMaps that have is_deleted = True

    For each such psm:
        - check if there are other psm corresponding to the same product and user_prof and where shelf.user_created_shelves = True
          and are not on DELETED_SHELF
        - if such duplicates exist, then we should not create an entry in DELETED_SHELF
          (cleanup of legacy data: delete if entries exist in DELETED_SHELF)
        - if no such duplicates exist, create an entry in the DELETED SHELF

    '''
    psms = ProductModelShelfMap.objects.select_related('product_model', 'shelf', 'user_prof').filter(is_deleted=True, shelf__user_created_cat=True).order_by('id')
    for i, it in enumerate(psms):
        print "{item}'th item".format(item=i)
        dups = ProductModelShelfMap.objects.filter(product_model=it.product_model,
                                                   user_prof=it.user_prof,
                                                   shelf__user_created_cat=True,
                                                   is_deleted=False).exclude(shelf__name=DELETED_SHELF)
        if dups.exists():
            # we have other user-created shelves that have this product, so skip creating an entry in DELETED_SHELF
            # if an entry exists in DELETED_SHELF, we should delete it
            del_pms = ProductModelShelfMap.objects.filter(product_model=it.product_model,
                                                          user_prof=it.user_prof,
                                                          shelf__user_created_cat=True,
                                                          is_deleted=False,
                                                          shelf__name=DELETED_SHELF)
            del_pms.delete()
        else:
            del_shelf = Shelf.objects.get_or_create(user_id=it.user_prof.user, name=DELETED_SHELF, is_public=False)[0]
            it.clone(it.user_prof, del_shelf)

        it.delete()


def test_remove_is_deleted_flag():
    psms_all = ProductModelShelfMap.objects.select_related('product_model', 'shelf', 'user_prof').filter(is_deleted=True, shelf__user_created_cat=True).order_by('id')
    user_profs = set([p.user_prof for p in psms_all])
    for u in user_profs:
        psms = psms_all.filter(user_prof=u)

        # check 1: if psms.count() == 0, then make sure that DELETED_SHELF for this user has no items
        if psms.count() == 0:
            assert ProductModelShelfMap.objects.filter(user_prof=u, shelf__name=DELETED_SHELF).count() == 0
            continue

        # check 2: all psms that have is_deleted=True, these should all be on DELETED_SHELF only
        assert not psms.exclude(shelf__name=DELETED_SHELF).exists()
        print 'User %s is ok' % u


def create_compressed_feed_img():
    missing_compressed = ProductModelShelfMap.objects.filter(img_url_feed_view__isnull=False, img_url_feed_compressed__isnull=True).order_by('-id')
    print "total missing is ", missing_compressed.count()
    for i,p in enumerate(missing_compressed):
        print "%dth item \n\n\n\n\n\n\n" % i
        create_images_for_wishlist_item(p)


def copy_from_backup_db():
    '''
    this function is simply copying all of the LotteryEntry and LotteryEntryCompletedTask objects from the backup database
    to the prod database
    '''
    backup_entries = LotteryEntry.objects.using("dec19backup").all()
    backup_tasks = LotteryEntryCompletedTask.objects.using("dec19backup").all()
    for i,entry in enumerate(backup_entries):
        print "%dth entry" % i
        entry.save(using='default')

    for i,task in enumerate(backup_tasks):
        print "%dth task" % i
        task.save(using='default')


def create_profiles_for_influencers():
    influencers = Influencer.raw_influencers_for_search()
    influencers_without_user = influencers.filter(shelf_user__isnull=True).order_by('-id')

    for i,inf in enumerate(influencers_without_user):
        print i

        #check if a user exists in our db containing this influencers email or if a userprofile exists containing this
        #influencers blog_url
        try:
            inf_user = User.objects.get(email__iexact=inf.email)
        except ObjectDoesNotExist:
            try:
                blog_url_main_token = utils.strip_url_of_default_info(inf.blog_url, strip_domain=False)
                inf_user = UserProfile.objects.get(blog_page__icontains=blog_url_main_token).user
            except ObjectDoesNotExist:
                blog_domain = utils.domain_from_url(inf.blog_url)
                inf_user = User.objects.create_user(username=SHELF_INFLUENCER_USER(blog_domain),
                                                    email=SHELF_INFLUENCER_USER(blog_domain),
                                                    password=SHELF_INFLUENCER_PASSWORD)
                UserProfile.objects.create(user=inf_user)

        inf.shelf_user = inf_user
        inf.save()


def social_handle_discovery_engine_stats():
    """
    1. Find all new influencers with source__in=['blogurlsraw', 'followers']
    2. That have blog_url field set
    3. That have been attempted to find the social handle
    4. That have relevant_to_fashion=True

    Now, for these, print first those guys that don't have any handle, then those that 2, then those that have 3
    """
    infs = Influencer.objects.filter(source__in=['followers', 'blogurlsraw'], relevant_to_fashion=True,
                                     platform__platformdataop__operation='extract_platforms_from_platform',
                                     blog_url__isnull=False, )

    print "we have %d influencers that may show up in search" % infs.count()
    no_plats = set()
    one_plat = set()
    two_plat = set()
    three_plat = set()
    platforms = {}
    for i in infs[:1000]:
        plats = Platform.objects.filter(influencer=i, platform_name__in=Platform.SOCIAL_PLATFORMS)
        count = plats.count()
        if count == 0:
            no_plats.add(i)
        elif count == 1:
            one_plat.add(i)
        elif count == 2:
            two_plat.add(i)
        elif count == 3:
            three_plat.add(i)
        platforms[i.id] = {}
        for p in plats:
            platforms[i.id][p.platform_name] = p.url

    print "[Total:] %d [no_plat] %d [one_plat] %d [two_plat] %d [three_plat] %d" % (infs.count(), len(no_plats), len(one_plat),
                                                                        len(two_plat), len(three_plat))
    for i in no_plats:
        print "%d, %s, , , , " % (i.id, i.blog_url)
    print "\n\n******\n"
    for i in one_plat:
        print "%d, %s," % (i.id, i.blog_url),
        plat_objs = platforms[i.id]
        for pname in Platform.SOCIAL_PLATFORMS:
            if pname in plat_objs.keys():
                print "%s," %plat_objs[pname],
            else:
                print ",",
        print "\n"






#####-----< Test Db Scripts >-----#####
def populate_test_db():
    '''
    a function to populate our test db with some prod data
    this can pull more data as needed in the future
    '''
    save_in_test_db = lambda el: el.save(using='test_db')
    delete_in_test_db = lambda el: el.delete(using='test_db')

    NUM_USERS = 10
    #clear out old data
    print "clearing old users..."
    for up in UserProfile.objects.using('test_db').all().order_by('-id')[:NUM_USERS]:
        delete_in_test_db(up)
        delete_in_test_db(up.user)
    #populate some users
    print "populating users now..."
    some_users = [up.user for up in UserProfile.objects.filter(num_shelves__gt=0, num_items_in_shelves__gt=0).all().order_by('-id')[:NUM_USERS]]
    for user in some_users:
        old_user_profile = user.userprofile
        save_in_test_db(user)
        save_in_test_db(old_user_profile)

    #clear old brands
    NUM_BRANDS = 5
    test_brands = []
    print "clearing out old brands..."
    for brand in Brands.objects.using('test_db').all().order_by('-id')[:NUM_BRANDS]:
        delete_in_test_db(brand)
    #populate new brands
    print "adding new brands..."
    for brand in Brands.objects.all().order_by('-id')[:NUM_BRANDS]:
        test_brands.append(brand)
        save_in_test_db(brand)

    #clear out old product models
    NUM_PRODUCTS = 50
    test_product_models = []
    print "deleting old product models..."
    for brand in test_brands:
        for pm in ProductModel.objects.using('test_db').filter(brand=brand).all().order_by('-id'):
            delete_in_test_db(pm)
    #populate product models
    print "adding new product models..."
    for brand in test_brands:
        for pm in ProductModel.objects.filter(brand=brand).all().order_by('-id')[:NUM_PRODUCTS]:
            test_product_models.append(pm)
            save_in_test_db(pm)

    #clear out old wishlist items
    print "deleting old wishlist items..."
    for pm in test_product_models:
        for wl_item in WishlistItem.objects.using('test_db').filter(product_model=pm).all().order_by('-id'):
            delete_in_test_db(wl_item)
    #populate wishlist items
    print "adding new wishlist items..."
    for pm in test_product_models:
        for wl_item in WishlistItem.objects.filter(product_model=pm).all().order_by('-id'):
            save_in_test_db(wl_item)



###ADMIN SCRIPTS
def generate_user_report():
    '''
    a script to generate a csv report for all users/brands in the database. These fields will be contained:
    1. Name
    2. Email
    3. Account URL (not critical)
    4. Blog link
    5. Last login/site interactions
    6. Shelf info (how many items, etc)
    7. Brand/Blog divisions
    '''
    import csv

    #get all relevant fields for all users
    user_data = [(up.name, up.user.email, up.profile_url, up.blog_url, up.user.last_login, up.num_items_in_shelves, up.num_shelves)
                 for up in UserProfile.objects.all()]
    user_data_count = len(user_data)
    print "found %d users" % user_data_count

    #get all relevant fields for brands
    brand_data = [(b.name, b.domain_name, b.supported) for b in Brands.objects.all()]
    brand_data_count = len(brand_data)
    print "found %d brands" % brand_data_count

    with open('report.csv', 'wb') as csvfile:
        writer = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)

        #write the data (with a progress indicator)
        print "Starting on the user data now.."
        for i,row in enumerate(user_data):
            try:
                writer.writerow(row)
            except UnicodeEncodeError:
                writer.writerow(['bad data' for u in row])

            print "%d / %d" % (i, user_data_count)

        print "Starting on the brand data now.."
        for i,row in enumerate(brand_data):
            try:
                writer.writerow(row)
            except UnicodeEncodeError:
                writer.writerow(['bad data' for b in row])

            print "%d / %d" % (i, brand_data_count)


######Random HTTP Scripts
def magic_brand_details_scraper(brand_details_link):
    """
    a helper for the magic_scraper method, this method scrapes details about a brand and returns those details as a dict
    @param brand_details_link - the link to the details for a given brand
    @return dict containing scraped details (address, website address, phone, categories)
    """
    resp = requests.get(brand_details_link)
    tree = lxml.html.fromstring(resp.text)

    info = tree.xpath("//*[@id='mys-exhibitorInfo']")[0]
    info_list = info.xpath('./ul/li')

    category_list = info.xpath('//ol/li')

    try:
        address = "{add} | {city_state} | {country}".format(add=info_list[0].text.encode('ascii', 'ignore'),
                                                            city_state=info_list[1].text.encode('ascii', 'ignore'),
                                                            country=info_list[2].text.encode('ascii', 'ignore'))
    except IndexError:
        address = 'N/A | N/A | N/A'
    except AttributeError:
        address = 'N/A | N/A | N/A'

    try:
        lxml.etree.strip_tags(info_list[3], 'strong')
        phone = info_list[3].text
    except IndexError:
        phone = 'N/A'

    try:
        website = info_list[4].xpath('./a')[0].text
    except IndexError:
        website = 'N/A'


    return {
        'address': address,
        'phone': phone,
        'website': website,
        'categories': "|".join([cat.text for cat in category_list]) if len(category_list) > 0 else 'N/A'
    }


def magic_scraper():
    """
    scraping brand information for the upcoming Magic convention
    """
    TYPES = {
        'ENK': 4,
        'P': 2,
        'MBB': 7,
        'MBA': 5,
        'S': 11,
        'C': 9,
        'N': 5,
        'T': 1
    }

    base_url = 'http://magicfeb14.mapyourshow.com'
    magic_url = lambda type, page: '{base}/5_0/exhibitor_results.cfm?type=booth&hallid={type}&booth=&page={page}'.format(base=base_url, type=type, page=page)

    for type in TYPES.keys():
        overall_result = []
        for i in range(1, TYPES[type]):
            resp = requests.get(magic_url(type, i))
            tree = lxml.html.fromstring(resp.text)
            table = tree.xpath('//table')[0]
            page_result = []
            for row_i,row in enumerate(table.xpath('./tr')):
                tds = row.xpath('./td[2]|./td[3]')
                page_result.append([])

                try:
                    brand_name, booth = tds[0].xpath('./a')[0], tds[1].xpath('./a')[0]
                    brand_details_link = '{base}{href}'.format(base=base_url, href=brand_name.attrib['href'])

                    page_result[row_i].append(brand_name.text)
                    page_result[row_i].append(booth.text)
                    page_result[row_i].append(brand_details_link)

                    res = magic_brand_details_scraper(brand_details_link)

                    print "{i}th result: {res}".format(i=i, res=res)
                    [page_result[row_i].append(v) for v in res.values() if v is not None]
                except IndexError:
                    pass
            overall_result.append(page_result)

        h.write_csv_file('magic_brands_{type}.csv'.format(type=type), overall_result, is_3d=True, delimiter='^')
        print "~~~~~~~Just finished a type~~~~~~~~\n\n\n"



########TESTING EXISTING METHODS / FUNCTIONS HELPERS
def test_update_blogs_from_xpaths():
    """
    testing of the update_blogs_from_xpaths method of the Platform Model class
    """
    test_data = [{
        'blog_name': 'GBO Fashion',
        'blog_url': 'http://gbofashion.com',
        'post_urls': '//div[contains(@class,"post")]/h2/a',
        'post_title': '//div[contains(@class,"post")]/h1',
        'post_content': '//div[@class="entry"]',
        'post_date': '//div[contains(@class,"post")]//div[@class="date"]',
        'post_comments': '//li[contains(@class, "comment")]',
        'next_page': '//a[@class="next page-numbers"]'
    }]

    return Platform.update_blogs_from_xpaths(test_data, 0)


def fix_spreadsheet_import():
    for inf in Influencer.objects.filter(source='spreadsheet_import'):
        for pl in inf.platform_set.all():
            if not pl.url.startswith(('http', 'www', 'pinterest', 'twitter', 'facebook', 'instagram')):
                print 'Will delete pl %r:\n\nURL: %r\n' % (pl, pl.url)
                #pl.delete()

def fix_invalid_platform_urls():
    invalid_pls = []
    spreadsheet_infs = Influencer.objects.filter(source="spreadsheet_import")

    for pl in Platform.objects.filter(platform_name='Instagram', influencer__in=spreadsheet_infs):
        if 'instagram.com' in pl.url.lower():
            continue
        if 'statigr.am' in pl.url.lower():
            continue
        if 'stagram.com' in pl.url.lower():
            continue
        if 'iphoneogram.com' in pl.url.lower():
            continue
        invalid_pls.append(pl)

    for pl in Platform.objects.filter(platform_name='Facebook', influencer__in=spreadsheet_infs):
        if 'facebook.com' in pl.url.lower():
            continue
        invalid_pls.append(pl)

    for pl in Platform.objects.filter(platform_name='Twitter', influencer__in=spreadsheet_infs):
        if 'twitter.com' in pl.url.lower():
            continue
        invalid_pls.append(pl)

    for pl in Platform.objects.filter(platform_name='Pinterest', influencer__in=spreadsheet_infs):
        if 'pinterest.com' in pl.url.lower():
            continue
        invalid_pls.append(pl)

    for pl in invalid_pls:
        print 'Deleting invalid platform with %s posts: %r' % (pl.posts_set.count(), pl)
        # !!!
        pl.delete()


def update_description_in_influencer_from_platforms():
    """
    Update the description for an influecner from the longest description available on any social platform.
    """
    infs = Influencer.objects.filter(source__isnull=False, blog_url__isnull=False, description__isnull=True)
    total = infs.count()
    for i, inf in enumerate(infs):
        print i*1.00/total, i, inf.id
        plats = inf.platforms().filter(platform_name__in=Platform.SOCIAL_PLATFORMS)
        if plats.exists():
            # let's pick the longest description
            descr = inf.description
            for p in plats:
                print "current: %s, p.name %s p.description: %s" % (descr, p.platform_name, p.description)
                if p.description and (not descr or len(p.description) >= len(descr)):
                    descr = p.description
                    print "ok, picking %s" % p.description
            print 'descr %s' % descr
            if descr:
                inf.description = descr
                print "saving %s as description for %s " % (descr, inf.blog_url)
                inf.save()



def influencer_status():
    infs = Influencer.objects.filter(source='comments_import')
    infs_with_blog_url = infs.filter(blog_url__isnull=False)
    infs_classified = infs_with_blog_url.filter(classification__isnull=False)
    infs_blog = infs.filter(classification='blog')
    infs_blogspot = infs.filter(classification='blog', blog_url__contains='blogspot')
    infs_w_posts = infs.filter(posts_count__gt=0)
    infs_fashion = infs.filter(relevant_to_fashion=True)
    infs_is_active = infs.active()
    infs_active_and_fashion = infs.active().filter(relevant_to_fashion=True)

    print "Infs.source='comments_import': %d" % infs.count()
    print "Infs.classificed: %d" % infs_classified.count()
    print "Infs.blog: %d" % infs_blog.count()
    print "Infs.blogspot: %d" % infs_blogspot.count()
    print "Infs_with_posts: %d" % infs_w_posts.count()
    print "Infs_with_fashion: %d" % infs_fashion.count()
    print "Infs_is_active: %d" % infs_is_active.count()
    print "Infs_active_fashion: %d" % infs_active_and_fashion.count()

#@workinprogress work in progress here


from django.db import transaction
@transaction.commit_manually
def create_virtual_profiles_for_brands(recover_name=True):
    sid = transaction.savepoint()
    try:
        user_as_brands = User.objects.filter(userprofile__brand__isnull=False, userprofile__brand__blacklisted=False).exclude(email__startswith="theshelf@", email__endswith=".toggle")
        for user in user_as_brands:
            print "#"*20
            profile = user.userprofile
            brand = profile.brand
            if recover_name:
                if not brand.domain_name or len(brand.domain_name)<3:
                    guess_name = user.email.split("@")[-1]
                    print "recovering domain name to ", guess_name
                    brand.domain_name = guess_name
                    brand.save()
            else:
                continue
            virtual_brand_user = user
            virtual_brand_user.pk = None
            virtual_brand_user.username = SHELF_BRAND_USER(brand.name)
            virtual_brand_user.password = SHELF_BRAND_PASSWORD
            virtual_brand_user.save()
            virtual_brand_profile = profile
            virtual_brand_profile.pk = None
            virtual_brand_profile.save()
            virtual_brand_user.userprofile = virtual_brand_user
            virtual_brand_user.save()
            profile.brand = None
            profile.save()
            virtual_brand_profile.brand = brand
            virtual_brand_profile.save()

            privilages = UserProfileBrandPrivilages()
            privilages.user_profile = profile
            privilages.brand = brand
            if UserProfileBrandPrivilages.objects.filter(brand=brand, permissions=UserProfileBrandPrivilages.PRIVILAGE_OWNER).exists():
                privilages.permissions = UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR_UNCONFIRMED
            else:
                privilages.permissions = UserProfileBrandPrivilages.PRIVILAGE_OWNER
            privilages.save()
            break
    except Exception as e:
        print e
    transaction.savepoint_rollback(sid)
    transaction.commit()


def update_influencer_fields():
    infs = Influencer.objects.active().filter(source='comments_import', relevant_to_fashion=True).exclude(show_on_search=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    for i,inf in enumerate(infs):
        plats = inf.platforms().exclude(url_not_found=True)
        for p in plats:
            p.append_to_url_field(inf)
        inf.save()
        print "done with %s " % i


def clean_social_handles_for_influencers():
    """
    Use this to cleanup social handles for influencers that have not been QAed yet.
    """
    infs = Influencer.objects.active().filter(source__isnull=False, relevant_to_fashion=True).exclude(show_on_search=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)


    from platformdatafetcher import platformextractor

    plats = Platform.objects.filter(influencer__in=infs, platform_name__in=Platform.BLOG_PLATFORMS)
    for i, pl in enumerate(plats):
        print '%d. Submitting extract_platforms_from_platform task for pl.id=%s' % (i, pl.id)
        platformextractor.extract_combined.apply_async([pl.id], queue="platform_extraction")

@baker.command
def fix_invalid_img_url():
    from masuka import image_manipulator
    from xpathscraper.resultsenrichment import Image

    to_fix = ProductModel.objects.filter(img_url__startswith='Image(')
    to_fix_cnt = to_fix.count()
    log.info('To fix: %d', to_fix_cnt)
    for (i, pm) in enumerate(to_fix.iterator()):
        try:
            corrected_src = eval(pm.img_url).src
            log.info('%d/%d. Correcting id=%d %r to %r', i, to_fix_cnt, pm.id, pm.img_url, corrected_src)
            pm.img_url = corrected_src
            pm.save()
            for pmsm in pm.productmodelshelfmap_set.all():
                pmsm.img_url = corrected_src
                log.info('Running create_images_for_wishlist_item for pmsm.id=%d', pmsm.id)
                image_manipulator.create_images_for_wishlist_item(pmsm)
        except:
            log.exception('While fixing %d %r', i, pm)
    log.info('Fixing ended')


def tag_small_images():
    no_img_url = ProductModel.objects.filter(img_url='Nil')
    no_img_url.update(small_image=True)
    all_prods = ProductModel.objects.filter(small_image=False).order_by('-insert_date')[:1000000]
    for product in all_prods:
        dims = get_dims_for_url(product.img_url)
        if dims[0] > 200 and dims[1] > 200 and dims[0] < dims[1]*3:
            product.small_image = False
        else:
            product.small_image = True
        product.save()


def remove_virtual_users_for_influencers():
    infs = Influencer.objects.filter(source__isnull=False, blog_url__isnull=False, shelf_user__isnull=False)
    print "Have %d influencers to fix" % infs
    have_virtual_users = set()
    infs = infs.filter(shelf_user__username = Q(blog_url))
    for i in infs:
        us = User.objects.filter(username = SHELF_BRAND_USER(i.blog_url))
        if us.exists():
            have_virtual_users.add(i)


def denormalize_posts_and_pmsm():
    for platform in Platform.BLOG_PLATFORMS:
        print "Processing platform", platform
        posts_qs = Posts.objects.filter(platform__platform_name=platform)
        posts_qs.update(platform_name=platform)
    for influencer in Influencer.objects.all():
        print "Processing influencer", influencer.id
        products = ProductModelShelfMap.objects.filter(post__influencer=influencer)
        products.update(influencer=influencer)


def brand_invariants():
    """
    No duplicates
    Every user that has a FK to a brand is a virtual user.
    Any brand that has a UserProfileBrandPrivilages object pointing to it, should have a non virtual user associated with it
    A brand should have at most one UserProfileBrandPrivilages backpointer
    """

    import collections
    print "Fetching brand names, it can take some time..."
    names = [x[0] for x in Brands.objects.all().only('domain_name').values_list('domain_name')]
    print "OK."
    dups = [x for x, y in collections.Counter(names).items() if y > 1]
    print "I found", len(dups), "duplicated brand domains"

    assert len(dups) == 0


    user_profs = UserProfile.objects.filter(brand__isnull=False)
    assert user_profs.exclude(user__username__startswith='theshelf@').exists() == False


    all_brands = Brands.objects.filter(domain_name__isnull=False)
    for brand in all_brands:
        previliges = UserProfileBrandPrivilages.objects.filter(brand=brand)
        assert previliges.filter(user_prof__user__username__contains='theshelf@').exists() == False



def create_vuser_for_brands():
    """
    Dealing with legacy data
    users  = User.objects.filter(userprofile__brand__isnull=False)
    1. Find all userprofiles that have a brand FK.
        a) if the username or email starts with 'theshelf' => then it's a virtual profile we created earlier
            existing_vusers = users.filter(Q(email__startswith='theshelf') | Q(username__startswith='theshelf')).exclude(Q(email__endswith='.toggle') | Q(username__endswith='.toggle'))
            => migrate this username/email to the new system, use the domain name of the brand
                brand = user.userprofile.brand
                user.username = SHELF_BRAND_USER(brand.name)
                user.email = SHELF_BRAND_USER(brand.name)
                user.save()
        b) if the username or email doesn't start with 'theshelf' => these are real users
            existing_signedup_users = users.exclude(Q(email__startswith='theshelf') | Q(username__startswith='theshelf'))
            => remove the FK, create virtual profile for brand, and connect user to the brand



    """
    users = User.objects.filter(userprofile__brand__isnull=False)
    existing_vusers = users.filter(Q(email__startswith='theshelf') | Q(username__startswith='theshelf')).exclude(Q(email__endswith='.toggle') | Q(username__endswith='.toggle'))
    count = existing_vusers.count()

    for n, user in enumerate(existing_vusers):
        print 1+n, '/', count
        brand = user.userprofile.brand
        user.username = SHELF_BRAND_USER(brand.name)
        user.email = SHELF_BRAND_USER(brand.name)
        user.save()

    existing_signedup_users = users.exclude(Q(email__startswith='theshelf') | Q(username__startswith='theshelf'))
    count = existing_signedup_users.count()
    for n, user in enumerate(existing_signedup_users):
        print 1+n, '/', count
        print "User: %s " % user
        profile = user.userprofile
        brand = profile.brand
        print "brand %s " % brand
        profile.brand = None
        profile.save()
        brand_helpers.create_profile_for_brand(brand)
        brand_helpers.connect_user_to_brand(brand, profile)


def fix_brand_domain():
    brands = Brands.objects.filter(domain_name__isnull=False)
    for brand in brands:
        brand.domain_name = brand.domain_name.lower()
        brand.save()


def invariants_test():
    import collections
    import sys

    def print_flush(*args):
        print "{:<100}".format(" ".join(map(str,args))),
        sys.stdout.flush()

    user_head_format = "{:>15}{:>15}{:>40}{:>30}"
    user_row_format = "{0.id:>15}{0.user.id:>15}{0.user.username:>40}{0.brand.domain_name:>30}"
    relation_head_format = "{:>15}{:>15}"
    relation_row_format = "{0.user_profile.id:>15}{0.brand.id:>15}"


    print_flush("Brand domain name duplicates test...")
    names = [x[0] for x in Brands.objects.all().only('domain_name').values_list('domain_name')]
    dups = [x for x, y in collections.Counter(names).items() if y > 1]
    if len(dups) == 0:
        print "PASS"
    else:
        print "FAIL!"
        print "We have", len(dups), "duplicates:"
        print ", ".join(dups)

    print_flush("Every user that has a FK to a brand is a virtual user...")
    users_with_brands = UserProfile.objects.filter(brand__isnull=False)
    incorrect_users = users_with_brands.exclude(user__username__startswith="theshelf@", user__username__endswith=".toggle")
    if incorrect_users.count() == 0:
        print "PASS"
    else:
        print "FAIL!"
        print "We have", incorrect_users.count(), "incorrect users:"
        print user_head_format.format("UserProfile ID", "User ID", "Username", "Brand domain")
        for user in incorrect_users:
            print user_row_format.format(user)

    print_flush("Brand related users should be non-virtual...")
    invalid_relation = UserProfileBrandPrivilages.objects.filter(
        user_profile__user__username__startswith="theshelf@",
        user_profile__user__username__endswith=".toggle"
    )
    if invalid_relation.count() == 0:
        print "PASS"
    else:
        print "FAIL!"
        print "We have", invalid_relation.count(), "incorrect relations:"
        print relation_head_format.format("UserProfile ID", "Brand ID")
        for relation in invalid_relation:
            print relation_row_format.format(relation)



@baker.command
def fix_wordpress_remove_protocol_bug():
    from platformdatafetcher import platformutils

    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
    select id from debra_platform
    where platform_name='Wordpress'
    and validated_handle is not null
    and ((url like '%%http://h%%' and validated_handle not like 'h%%') or
         (url like '%%http://t%%' and validated_handle not like 't%%') or
         (url like '%%http://p%%' and validated_handle not like 'p%%') or
         (url like '%%http://s%%' and validated_handle not like 's%%'))
    """)
    print 'Found %d platforms', cur.rowcount
    for i, (platform_id,) in enumerate(cur):
        platform = Platform.objects.get(id=platform_id)
        with platformutils.OpRecorder(operation='fix_wordpress_remove_protocol_bug',
                                      platform=platform):
            print '%d. Platform %d old validated_handle: %r' % (i, platform_id, platform.validated_handle)
            platform.validated_handle = utils.domain_from_url(platform.url)
            print '%d. Platform %d new validated_handle: %r' % (i, platform_id, platform.validated_handle)
            platform.save()


def find_influencers_that_have_multiple_social_handles():
    """
    Find influencers that have more than 1 platforms created. These are all potentially bad.
    So, we should first of make sure these platform.urls are saved in Influencer.url and
    then let's add MULTIPLE in front of the Influencer.url so that it's easier for the QA to spot these
    and fix.
    """
    query = Influencer.objects.filter(show_on_search=True, validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).prefetch_related('platform_set')
    valid = set()
    for q in query:
        print q.id
        fb_plats = q.platform_set.filter(platform_name='Facebook').exclude(url_not_found=True)
        tw_plats = q.platform_set.filter(platform_name='Twitter').exclude(url_not_found=True)
        pin_plats = q.platform_set.filter(platform_name='Pinterest').exclude(url_not_found=True)
        insta_plats = q.platform_set.filter(platform_name='Instagram').exclude(url_not_found=True)
        if fb_plats.count() >= 2:
            valid.add(q.id)
            for f in fb_plats:
                if not q.contains_url('fb_url', f.url):
                    q.append_url('fb_url', f.url)
            if not q.contains_url('fb_url', 'DUPLICATE'):
                q.append_url('fb_url', 'DUPLICATE')
            q.save()
        if tw_plats.count() >= 2:
            valid.add(q.id)
            for t in tw_plats:
                if not q.contains_url('tw_url', t.url):
                    q.append_url('tw_url', t.url)
            if not q.contains_url('tw_url', 'DUPLICATE'):
                q.append_url('tw_url', 'DUPLICATE')
            q.save()
        if pin_plats.count() >= 2:
            valid.add(q.id)
            for p in pin_plats:
                if not q.contains_url('pin_url', p.url):
                    q.append_url('pin_url', p.url)
            if not q.contains_url('pin_url', 'DUPLICATE'):
                q.append_url('pin_url', 'DUPLICATE')
            q.save()
        if insta_plats.count() >= 2:
            valid.add(q.id)
            for i in insta_plats:
                if not q.contains_url('insta_url', i.url):
                    q.append_url('insta_url', i.url)
            if not q.contains_url('insta_url', 'DUPLICATE'):
                q.append_url('insta_url', 'DUPLICATE')
            q.save()



    query = Influencer.objects.filter(id__in=valid)
    print valid
    print "We have %d influencers with problems " % query.count()

def get_related_models(object, related=None):
    if not related:
        related = set(["%s:%s" % (object._meta.app_label, object._meta.verbose_name)])
    for rel in object._meta.get_all_related_objects():
        if not rel.name in related:
            related.add(rel.name)
            get_related_models(rel.model(), related)
    return related


def cleanup_nonrelevant_platforms():
    n = 0
    while True:
        n += 1
        pid = Platform.objects.filter(influencer__relevant_to_fashion=False).order_by('id')[:100]
        pcount = pid.count()
        if pcount == 0:
            break
        pid = pid[pcount-1].id
        print "Deleting", n, "chunk of platforms"
        Platform.objects.filter(influencer__relevant_to_fashion=False, id__lte=pid).delete()


def weekly_popularity_time_series():
    now = datetime.datetime.now()
    last_month = now - datetime.timedelta(days=30)
    for influencer in Influencer.objects.filter(relevant_to_fashion=True):
        values = influencer.platform_set.filter(posts__create_date__gte=last_month).annotate(num_comments=Sum('posts__denorm_num_comments')).values('id', 'num_comments', 'num_followers', 'num_following')
        for value in values:
            pts = PopularityTimeSeries()
            pts.influencer = influencer
            pts.platform_id = value["id"]
            pts.snapshot_date = now
            pts.num_followers = value["num_followers"]
            pts.num_following = value["num_following"]
            pts.num_comments = value["num_comments"]
            pts.save()


def create_intercom_profiles_for_latest_users():
    from . import account_helpers
    # first find all bloggers that have joined in the last month and verified their email
    last_month = datetime.date(2014, 5, 1)
    user_profiles = UserProfile.objects.filter(user__date_joined__gte=last_month, user__is_active=True, blog_page__isnull=False)
    user_profiles = user_profiles.exclude(user__username__startswith="theshelf", user__username__endswith=".toggle")
    print "We have %d users " % user_profiles.count()

    # we have to make sure these profiles don't already exist
    for user_profile in user_profiles:
        print user_profile
        #user.create_in_intercom()
        if user_profile.get_from_intercom():
            print "User %s already exists in Intercom, continuing" % user_profile.user
            continue
        user_profile.create_in_intercom()
        account_helpers.intercom_track_event(None,
                                             'blogger-signed-up',
                                             {'user_email': user_profile.user.email,
                                              'blog_url': user_profile.blog_page},
                                             user=user_profile.user)
        account_helpers.intercom_track_event(None,
                                             "blogger-email-verified",
                                             {'email': user_profile.user.email,
                                              'blog_url': user_profile.blog_page,
                                              'date_joined': user_profile.user.date_joined.strftime("%c")},
                                             user=user_profile.user)
        if user_profile.blog_verified:
            print "Set this property on the user"
            account_helpers.intercom_track_event(None, "blogger-blog-verification", {
                                                'email': user_profile.user.email,
                                                'blog_url': user_profile.blog_page,
                                                'success': True
                                            }, user_profile.user)


    # now looking for brands
    brand_users = UserProfileBrandPrivilages.objects.filter(brand__blacklisted=False)
    print "We have %d brand users" % brand_users.count()
    for bu in brand_users:
        if bu.user_profile.get_from_intercom():
            print "User %s already exists in Intercom, continuing" % bu.user_profile.user
            continue
        bu.user_profile.create_in_intercom()
        account_helpers.intercom_track_event(None,
                                             'brand-signed-up',
                                             {'user_email': bu.user_profile.user.email,
                                              'brand_url': bu.brand.domain_name},
                                             user=bu.user_profile.user)
        account_helpers.intercom_track_event(None,
                                             "brand-email-verified",
                                             {'email': bu.user_profile.user.email,
                                              'brand_url': bu.brand.domain_name,
                                              'date_joined': bu.user_profile.user.date_joined.strftime("%c")},
                                             user=bu.user_profile.user)

        account_helpers.intercom_track_event(None, "brand-ownership-verified", {
                                            'email': bu.user_profile.user.email,
                                            'brand_url': bu.brand.domain_name,
                                            'manual': False,
                                            'success': True
                                        }, bu.user_profile.user)

def find_duplicate_influencer_for_latest_users(set_flag=False):
    last_month = datetime.date(2014, 5, 1)
    user_profiles = UserProfile.objects.filter(user__date_joined__gte=last_month, user__is_active=True, blog_page__isnull=False)
    user_profiles = user_profiles.exclude(user__username__startswith="theshelf", user__username__endswith=".toggle")
    for user_profile in user_profiles:
        blog_domain = utils.domain_from_url(user_profile.blog_page)
        possible_influencers = Influencer.objects.filter(blog_url__icontains=blog_domain)
        cnt = possible_influencers.count()
        if cnt!=1:
            print "User id {0.id} has {1:<10} possible influencers {2:>40}".format(user_profile, cnt, blog_domain or "No BLOG DOMAIN!")
            if set_flag:
                if cnt == 0:
                    user_profile.error_when_connecting_to_influencer = "NO INFLUENCERS"
                else:
                    user_profile.error_when_connecting_to_influencer = "MULTIPLE INFLUENCERS"
                user_profile.save()


def remove_virtual_influencer_profiles():
    user_ids = [x[0] for x in Influencer.objects.filter(shelf_user__email__startswith="toggle@").values_list("shelf_user__id")]
    Influencer.objects.filter(shelf_user__email__startswith="toggle@").update(shelf_user=None)
    User.objects.filter(id__in=user_ids).delete()


def test_blogger_details_performance():
    import time
    s = requests.session()
    # token & login
    #base_url = "http://localhost:8000"
    #base_domain = "alpha-getshelf.herokuapp.com"
    base_domain = "app.theshelf.com"
    base_url = "http://"+base_domain
    print s.get(base_url)
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': s.cookies["csrftoken"],
        'User-Agent': 'Mozilla/5.0',
        'Host': base_domain,
        'Origin': base_url+"/",
    }
    print s.post(base_url+"/login/", data={"email": "contact@taigh.eu", "password":"test"}, headers=headers)

    #getting some influencers data
    influencers = Influencer.objects.filter(show_on_search=True, profile_pic_url__isnull=False).exclude(blacklisted=True)
    influencers = influencers.filter(score_popularity_overall__isnull=False)
    influencers = influencers.order_by('-score_popularity_overall')
    influencers = influencers.distinct()[:300].only('id').values('id')
    timing_data = []
    timing_details = []
    try:
        for n, x in enumerate(influencers):
            url = reverse('debra.search_views.blogger_info_json', args=(x["id"],))
            st = time.time()
            headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': s.cookies["csrftoken"],
                'User-Agent': 'Mozilla/5.0',
                'Host': base_domain,
                'Origin': base_url+"/",
            }
            resp = s.get(base_url+url, headers=headers)
            if resp.status_code != 200:
                print "STATUS CODE", resp.status_code
            et = time.time()
            timing_data.append(et-st)
            details = {
                'id': x["id"],
                'time': round(1000.0*(et-st)),
            }
            timing_details.append(details)
            print "{:<5} / 300 {:>10}ms id: {:>10} {:>10} bytes".format(n+1, round(1000.0*(et-st)), x["id"], len(resp.text))
            #print resp.text
    except KeyboardInterrupt:
        print
    print "Mean rq time:", 1000*float(sum(timing_data))/len(timing_data), "ms"
    print "Longest 10:"
    timing_details.sort(key=lambda x: -x["time"])
    for e in timing_details[:10]:
        print "{:>10}ms id: {:>10}".format(e["time"], e["id"])


def fix_pmsm_added_datetime():
    td = datetime.datetime.now()
    prods = ProductModelShelfMap.objects.filter(added_datetime__gt=td)
    for p in prods:
        if p.post.added_datetime > td:
            continue
        p.added_datetime = p.post.added_datetime
        p.save()






def fix_products_json():
    bad_posts = Posts.objects.filter(productmodelshelfmap__user_prof__isnull=True, products_json__isnull=False)
    for post in bad_posts:
        post.products_json = None
        post.get_product_json()



def try_pdimport_comment_url():
    start = datetime.date(2014, 6, 1)
    infs = Influencer.objects.filter(show_on_search=True).order_by('-score_popularity_overall')
    to_process_q = Follower.objects.filter(url__contains='blogger.com',
                                           postinteractions__post__influencer__in=infs,
                                           postinteractions__create_date__gte=start).distinct()


def safe_remove_brand(brand, delete=False):
    does_pass = True
    check_1 = brand.is_agency
    print "Is agency?", check_1
    if check_1:
        does_pass = False
    check_2 = brand.as_competitor.exists()
    print "Is it competitor?", check_2
    if check_2:
        does_pass = False
    check_3 = brand.competitors.exists()
    print "It has any competitors?", check_3
    if check_3:
        does_pass = False
    check_4 = brand.brandinpost_set.exists()
    print "Brand in posts?", check_4
    if check_4:
        does_pass = False
    check_5 = brand.brandmentions_set.exists()
    print "Brand mentions?", check_5
    if check_5:
        does_pass = False
    check_6 = brand.influencer_groups.exists()
    print "Any collections?", check_6
    if check_6:
        does_pass = False
    check_7 = brand.job_posts.exists()
    print "Any job posts?", check_7
    if check_7:
        does_pass = False
    check_8 = brand.mails.exists()
    print "Any mails?", check_8
    if check_8:
        does_pass = False
    check_9 = brand.products.exists()
    print "Any products?", check_9
    if check_9:
        does_pass = False
    check_10 = not brand.stripe_id is None
    print "Has stripe id?", check_10
    if check_10:
        does_pass = False
    check_11 = brand.related_user_profiles.all().exclude(permissions=UserProfileBrandPrivilages.PRIVILAGE_AGENCY).exists()
    print "Any non-agency privilages?", check_11
    if check_11:
        does_pass = False

    if not does_pass:
        print "Not passed !!!"
        return

    print "Passed all checks"

    if delete:
        brand.delete()

@baker.command
def insert_brand_social_platform(brands_url, platform_url, platform_name):
    assert platform_name in Platform.SOCIAL_PLATFORMS
    domain = utils.domain_from_url(brands_url)
    blog_url = 'http://theshelf.com/brandblog/%s/' % domain
    inf, _ = Influencer.objects.get_or_create(blog_url=blog_url, name=domain, source='brands')
    if inf.show_on_search != True:
        inf.set_show_on_search(True, save=True)
    print inf
    plat, _ = Platform.objects.get_or_create(influencer=inf, url=platform_url, platform_name=platform_name)
    print plat


def get_missing_profiles():
    import intercom
    intercom.Intercom.api_key = settings.PRODUCTION_INTERCOM_APIKEY
    intercom.Intercom.app_id = settings.PRODUCTION_INTERCOM_APPID
    emails = set([x["email"] for x in intercom.user.User.all()])

    validated_email_up = UserProfile.objects.filter(

        user__is_active=True,
        user__date_joined__gte=datetime.datetime.now() - datetime.timedelta(days=100)
    ).exclude(
        user__email__startswith="theshelf@",
        user__email__endswith=".toggle",
    ).exclude(
        user__email__startswith="toggle@"
    )
    validated_influencers_up = (validated_email_up.filter(influencer__isnull=False))
    validated_brands_up = (validated_email_up.filter(brand_privilages__isnull=False))
    unvalidated_influencers_up = (validated_email_up.filter(influencer__isnull=True, blog_page__isnull=False))
    unvalidated_brands_up = (validated_email_up.filter(brand_privilages__isnull=True, temp_brand_domain__isnull=False))

    print "Missing profiles"
    for x in validated_email_up:
        if not x.user.email in emails:
            print "{:<75}".format(x.user.email),
            if x in validated_influencers_up:
                print "Validated influencer\t",
            if x in validated_brands_up:
                print "Validated brand\t",
            if x in unvalidated_influencers_up:
                print "Not validated influencer\t",
            if x in unvalidated_brands_up:
                print "Not validated brand\t",
            print


def social_handle_inconsistency_checker():
    infs = Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
    print "Got %d influencers" % infs.count()

    fb_bad = set()
    insta_bad = set()
    tw_bad = set()
    pin_bad = set()

    for i in infs:
        plats = i.platforms().exclude(url_not_found=True)
        if i.fb_url:
            # if there are more than one, we should check each one
            urls = i.fb_url.split(' ')
            if len(urls) == 1:
                for u in urls:
                    if not plats.filter(platform_name='Facebook', url=u).exists():
                        fb_bad.add(i)

    #if not i.fb_url and plats.filter(platform_name='Facebook').exists():
    #        fb_bad.add(i)


@baker.command
def url_fields_platforms_inconsistency_checker(do_fixing='0'):
    from platformdatafetcher import platformutils
    from debra import admin

    do_fixing = int(do_fixing)
    infs = Influencer.objects.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(blacklisted=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
    infs = infs.filter(show_on_search=True)
    print infs.count(), 'infs'
    stats = defaultdict(lambda: defaultdict(int))
    infs_with_problems = set()
    for inf in infs:
        platform_urls = defaultdict(list)
        for pl in inf.platform_set.exclude(url_not_found=True):
            platform_urls[pl.platform_name].append(pl.url)
        for platform_name, field in Influencer.platform_name_to_field.items():

            if platform_name in ('Bloglovin', 'Lookbook', 'Pose'):
                continue

            def normalize_url(url):
                url = url.lower()
                url = utils.remove_query_params(url)
                url = url.replace('http://', 'https://')
                return url

            field_urls = (getattr(inf, field) or '').split()

            furls_norm = [normalize_url(u) for u in field_urls]
            purls_norm = [normalize_url(u) for u in platform_urls[platform_name]]

            only_in_field = set(furls_norm) - set(purls_norm)
            only_in_platform = set(purls_norm) - set(furls_norm)

            if not furls_norm and not purls_norm:
                stats[platform_name]['empty'] += 1
                print platform_name, inf, 'empty'
            elif not only_in_field and not only_in_platform:
                stats[platform_name]['ok'] += 1
                print platform_name, inf, 'ok'

            if only_in_field:
                stats[platform_name]['only_in_field'] += 1
                infs_with_problems.add(inf)
                print platform_name, inf, 'only_in_field', only_in_field
                if do_fixing:
                    print 'fixing', field, inf
                    admin.handle_social_handle_updates(inf, field, getattr(inf, field))
            if only_in_platform:
                stats[platform_name]['only_in_platform'] += 1
                infs_with_problems.add(inf)
                print platform_name, inf, 'only_in_platform', only_in_platform
                if do_fixing:
                    print 'fixing', field, inf
                    admin.handle_social_handle_updates(inf, field, getattr(inf, field))
    pprint.pprint(stats)
    print 'infs with problems:', len(infs_with_problems)

    #for inf in infs_with_problems:
    #    with platformutils.OpRecorder(operation='urls_inconsistencies', influencer=inf):
    #        pass

@baker.command
def fix_urls_inconsistencies():
    infs = Influencer.objects.filter(platformdataop__operation='urls_inconsistencies')
    print infs.count(), 'infs'
    for inf in infs:
        # todo
        pass

@baker.command
def try_validate_inconsistent_platforms():
    from platformdatafetcher import platformextractor

    infs = Influencer.objects.filter(platformdataop__operation='urls_inconsistencies')
    print infs.count(), 'infs'
    for inf in infs:
        if not inf.blog_platform:
            print 'Skipping', inf
            continue
        for pl in inf.platform_set.filter(platform_name__in=('Facebook', 'Twitter', 'Instagram', 'Pinterest')).exclude(url_not_found=True):
            validation = platformextractor.validate_platform(inf.blog_platform, pl)
            if not validation:
                print 'NOT_VALIDATED None', inf
            else:
                print 'YES_VALIDATED %s' % validation, inf


def median(lst):
    print len(lst)
    even = (0 if len(lst) % 2 else 1) + 1
    print "even %d " % even
    half = (len(lst) - 1) / 2
    print "half: %d" % half
    return sum(sorted(lst)[half:half + even]) / float(even)

def calculate_potential_reach(only_signed_up=False):
    """
    For each platform:
        find total # of followers
        for blogs, it should be # of commentors? (reach is higher than that)
        find avg and median # of followers for each platform
    """
    plats = Platform.objects.filter(influencer__show_on_search=True).exclude(url_not_found=True)
    if only_signed_up:
        plats = Platform.objects.filter(influencer__shelf_user__userprofile__blog_verified=True).exclude(url_not_found=True)

    pinterest_plats = plats.filter(platform_name='Pinterest')
    twitter_plats = plats.filter(platform_name='Twitter')
    insta_plats = plats.filter(platform_name='Instagram')
    fb_plats = plats.filter(platform_name='Facebook')
    blog_plats = plats.filter(platform_name__in=Platform.BLOG_PLATFORMS)


    pin_followers_count = pinterest_plats.aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']
    tw_followers_count = twitter_plats.aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']
    insta_followers_count = insta_plats.aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']
    fb_followers_count = fb_plats.aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']
    blog_followers_count = blog_plats.aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']

    pin_followers_array = [p.num_followers for p in pinterest_plats]
    tw_followers_array = [p.num_followers for p in twitter_plats]
    insta_followers_array = [p.num_followers for p in insta_plats]
    fb_followers_array = [p.num_followers for p in fb_plats]
    blog_followers_array = [p.num_followers for p in blog_plats]

    pin_followers_median = median(pin_followers_array)
    tw_followers_median = median(tw_followers_array)
    insta_followers_median = median(insta_followers_array)
    fb_followers_median = median(fb_followers_array)
    blog_followers_median = 0 #median(blog_followers_array)

    pin_followers_avg = pin_followers_count/len(pin_followers_array)
    tw_followers_avg = tw_followers_count/len(tw_followers_array)
    insta_followers_avg = insta_followers_count/len(insta_followers_array)
    fb_followers_avg = fb_followers_count/len(fb_followers_array)
    blog_followers_avg = blog_followers_count/len(blog_followers_array)



    print "Pin followers: [total count: %d] [median: %d] [avg: %d]" % (pin_followers_count, pin_followers_median, pin_followers_avg)
    print "Twitter followers: [total count: %d] [median: %d] [avg: %d]" % (tw_followers_count, tw_followers_median, tw_followers_avg)
    print "Instagram followers: [total count: %d] [median: %d] [avg: %d]" % (insta_followers_count, insta_followers_median, insta_followers_avg)
    print "Facebook followers: [total count: %d] [median: %d] [avg: %d]" % (fb_followers_count, fb_followers_median, fb_followers_avg)
    print "Blog followers: [total count: %d] [median: %d] [avg: %d]" % (blog_followers_count, blog_followers_median, blog_followers_avg)


@baker.command
def restore_blogname():
    infs = Influencer.objects.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(blacklisted=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
    print infs.count(), 'infs'
    for inf in infs:
        latest_qad = InfluencerEditHistory.objects.filter(field='blogname', influencer=inf).order_by('-timestamp')
        if not latest_qad.exists():
            print 'NO_EDITS', inf
        else:
            val_qad = latest_qad[0].curr_value
            if val_qad != inf.blogname:
                print 'DIFFERENCE %r %r' % (val_qad, inf.blogname), inf
                inf.blogname = val_qad
                inf.save()
                print 'new blogname: %r' % (inf.blogname)
            else:
                print 'EQUAL %r %r' % (val_qad, inf.blogname), inf


def recalculate_post_images():
    from masuka import image_manipulator
    from_date = datetime.date(2014, 7, 15)
    posts = Posts.objects.filter(create_date__gte=from_date, post_image_width__isnull=True)
    count = posts.count()
    for n, post in enumerate(posts):
        try:
            print n+1, '/', count
            image_manipulator.upload_post_image_task.apply_async([post.id], queue="recalculate_post_images")
        except:
            print "problem with "
            pass


@baker.command
def fix_invalid_blognames():
    from platformdatafetcher import blognamefetcher
    from platformdatafetcher import platformutils

    infs = Influencer.objects.filter(blogname__istartswith='403 forbidden')
    log.info('%d infs', infs.count())
    for inf in infs:
        log.info('Processing %r', inf)
        plat = inf.blog_platform
        if not plat or not plat.url or not inf.blog_url:
            log.warn('No blog platform')
            continue
        if platformutils.url_to_handle(plat.url) != platformutils.url_to_handle(inf.blog_url):
            log.warn('Blog platform url does not match blog_url')
            continue
        try:
            blognamefetcher.fetch_blogname(plat.id, True)
        except:
            log.exception('')

@baker.command
def insert_ichecks_for_blogname_fixing():
    infs = Influencer.objects.filter(blacklisted=False, source__isnull=False)
    plats = Platform.objects.filter(influencer__in=infs)
    pdos = PlatformDataOp.objects.filter(operation='fetch_blogname',
                                         platform__in=plats,
                                         finished__gt=datetime.datetime.now() - datetime.timedelta(hours=4),
                                         server_ip='127.0.1.1')
    log.debug(pdos.query)
    log.info('%d pdos', pdos.count())
    for pdo in pdos:
        log.info('Reporting %r', pdo.platform.influencer)
        InfluencerCheck.report_new(pdo.platform.influencer, None, InfluencerCheck.CAUSE_SUSPECT_NAME_BLOGNAME,
                                   ['blogname'])

def normalize_gender():
    influencers = Influencer.objects.filter(validated_on__contains='info').exclude(show_on_search=True).only('demographics_gender')
    #influencers = Influencer.objects.filter(show_on_search=True).only('demographics_gender')
    c_start = 0
    tcnt = influencers.count()
    while True:
        chunk = influencers[c_start:c_start+100]
        cnt = chunk.count()
        if cnt == 0:
            break
        for n, influencer in enumerate(chunk):
            print c_start+n+1, "/", tcnt
            guess = None
            if influencer.demographics_gender:
                if 'm' in influencer.demographics_gender.lower():
                    guess = 'm'
                if 'f' in influencer.demographics_gender.lower():
                    if guess:
                        guess = 'mf'
                    else:
                        guess = 'f'
            Influencer.objects.filter(id=influencer.id).update(demographics_gender=guess)
        c_start+=100

def denormalize_price_range_tags():
    c_start = 0
    tcnt = Influencer.objects.filter(show_on_search=True).count()
    while True:
        influencers = Influencer.objects.prefetch_related('scores').filter(show_on_search=True)[c_start:c_start+100]
        cnt = influencers.count()
        if cnt == 0:
            break
        for n, influencer in enumerate(influencers):
            print c_start+n+1, "/", tcnt
            Influencer.objects.filter(id=influencer.id).update(price_range_tag_normalized=influencer.price_range_tag)
        c_start+=100

class RefetchNewPostInteractionsPolicy(DefaultPolicy):

    def perform_fetching(self, fetcher_impl):
        self._refetch_interactions(fetcher_impl, 364)


@baker.command
def refetch_comments_for_old_posts():
    for platform in Platform.objects.filter(platform_name__in=Platform.BLOG_PLATFORMS, influencer__show_on_search=True).annotate(count=Count('posts__postinteractions')).filter(count=0):
        _do_fetch_platform_data(platform, RefetchNewPostInteractionsPolicy())


@baker.command
def geocode_changed_locations():
    for ieh in InfluencerEditHistory.objects.filter(field='demographics_location').exclude(prev_value=''):
        influencer.demographics_location_normalized = None
        influencer.save()
        normalize_location.apply_async((ieh.influencer_id,))


def update_instagram_post_urls():
    """
    July 4 2015
    Recently, instagram changed their page structure as well as their url structure from
    http://instagram.com/<username>/post_id to http://instagram.com/p/post_id
    So, we need to update this in our database as well so that exisintg posts stay live.
    """
    plats = Platform.objects.filter(platform_name='Instagram').exclude(url_not_found=True)
    for i, plat in enumerate(plats):
        posts = Posts.objects.filter(platform=plat).exclude(url__icontains='instagram.com/p/')
        print(i, plat, posts.count())
        for p in posts:
            x = p.url.rfind('/')
            y = p.url[x:]
            z = 'http://instagram.com/p%s' % y
            print("old url: %s new url: %s" % (p.url, z))
            p.url = z
            p.save()
        print("Done")


def delete_duplicate_posts(platform_name):
    """
    Here, we will remove such duplicate posts.
    """
    plats = Platform.objects.filter(platform_name=platform_name)

    for i, y in enumerate(plats):
        posts = Posts.objects.filter(platform=y)
        uniq_posts = posts.distinct('url')
        if posts.count() != uniq_posts.count():
            uniq_posts_id = uniq_posts.values_list('id', flat=True)
            dup_posts = posts.exclude(id__in=uniq_posts_id)
            print(i, y, posts.count(), uniq_posts.count())
            dup_posts.delete()
            posts = Posts.objects.filter(platform=y)
            print("After deduplication: %d" % posts.count())
        print("Done")


@task(name="debra.scripts.set_create_for_post", ignore_result=True)
def set_create_for_post(post_id):
    import dateutil.parser
    post = Posts.objects.get(id=post_id)
    print("Trying %r" % post)
    r = requests.get(post.url)
    tree = lxml.html.fromstring(r.content)
    create_date = tree.xpath('//div[@id="watch-uploader-info"]')
    if len(create_date) == 0:
        print("No element found for date, continuing")
        return
    create_date_str = create_date[0].text_content()
    to_check = 'Published on'
    x = create_date_str.find(to_check)
    if x < 0:
        to_check = 'Uploaded on'
        x = create_date_str.find(to_check)
    if x >= 0:
        x = x + len(to_check) + 1
        create_date_str = create_date_str[x:]
        create_date = dateutil.parser.parse(create_date_str)
        post.create_date = create_date
        print("Saved %r as create_date for %r" % (create_date, post))
        post.save()


def set_create_date_for_youtube_posts():
    """
    Our current version is not fetching create_dates for youtube posts. Updated the fetcher and running this script now
    to fetch create dates.
    """
    youtube = Platform.objects.filter(platform_name='Youtube')
    count = youtube.count()
    for i, y in enumerate(youtube):
        posts = Posts.objects.filter(platform=y).exclude(create_date__isnull=False)
        print(i, count, y, posts.count())
        for post in posts:
            set_create_for_post.apply_async([post.id], queue='denormalization')


def unescape_influencers_name_and_blogname(logging_enabled=False, update_db=True):
    """
    Unescape 'name' and 'blogname' fields on 'Influencer' model to eliminate
    the '&amp' problem.
    """
    from debra.serializers import unescape

    infs = Influencer.objects.filter(show_on_search=True).only(
        'name', 'blogname', 'id')

    changes = {}

    for inf in infs:
        new_name = unescape(inf.name)
        new_blogname = unescape(inf.blogname)

        if new_name == inf.name and new_blogname == inf.blogname:
            continue

        data = {}

        if new_name != inf.name:
            data['name'] = new_name

        if new_blogname != inf.blogname:
            data['blogname'] = new_blogname

        changes[inf.id] = data


    infs = Influencer.objects.filter(
        id__in=changes.keys()
    ).only(
        'id', 'name', 'blogname'
    )

    for inf in infs:

        new_name = changes[inf.id].get('name')
        new_blogname = changes[inf.id].get('blogname')

        if logging_enabled:
            print 'Influencer: ', inf.id
            if new_name is not None:
                print inf.name, '==>', new_name
            if new_blogname is not None:
                print inf.blogname, '==>', new_blogname

        if new_name is not None:
            inf.name = new_name

        if new_blogname is not None:
            inf.blogname = new_blogname

    if logging_enabled:
        print 'Number of influencers to change: ', len(changes)

    if update_db:
        bulk_update(infs, update_fields=['name', 'blogname'])


def fix_profile_images():
    """
    Here, we look at influencers that don't have a profile image on Amazon S3 and try to fix them.

    So, we first find all platforms that have url_not_found=True and have a valid reachable image.
    And then call the set_profile_pic() method of the Influencer.
    """
    from platformdatafetcher import fetcher
    infs = Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True)
    no_s3_image = infs.exclude(profile_pic_url__contains='s3.amazonaws')

    # just fetch their latest pictures from the platforms and then call the set_profile_pic
    # function
    success = 0
    for i, n in enumerate(no_s3_image):
        print i, n
        plats = n.platforms().exclude(url_not_found=True).filter(platform_name__in=Platform.SOCIAL_PLATFORMS_CRAWLED)
        for p in plats:
            print "Before", p, p.profile_img_url
            try:
                f = fetcher.fetcher_for_platform(p)
                print "After", p, p.profile_img_url
                if p.profile_img_url and 's3.amazonaws' in p.profile_img_url:
                    n.set_profile_pic()
                f.cleanup()
                if n.profile_pic_url and 's3.amazonaws' in n.profile_pic_url:
                    success += 1
                    print("%d Success %d" % (i, success))
                    break
            except:
                print "Problem with %s" % p
                pass


def cleanup_instagram_profiles():
    """
    If we find an instagram profile that has a url like 'ask.com/<username>' we'll associate it with INfluencer with blog_url='ask.fm'
    And if there is another instagram user with a profile on ask.com, it'll be associated with the same influencer.

    We want to remove these mappings from InstagramProfile -> Influencer if there are more than 1 such mappings for the same influencer.
    """
    from social_discovery import models as smodels

    insta = smodels.InstagramProfile.objects.filter(discovered_influencer__isnull=False)

    inf_ids = list(insta.values_list('discovered_influencer__id', flat=True))
    inf_ids = list(set(inf_ids))

    for i,inf_id in enumerate(inf_ids):
        print(i, inf_id)
        inf = Influencer.objects.get(id=inf_id)
        profs = inf.instagram_profile.all()
        count = profs.count()
        if count > 1:
            print("Influencer %s have %d instagram profiles pointing to it, removing them now" % (inf, count))
            profs.update(discovered_influencer=None)
            print("After removing, we have %d profiles pointing to influencer" % inf.instagram_profile.all().count())


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()


def influencer_set_1():
    """
    https://app.asana.com/0/42664940909123/74028817581832

    :return: set_4 queryset
    """
    set_1 = Influencer.objects.filter(show_on_search=True).exclude(old_show_on_search=True)
    set_2 = set_1.exclude(profile_pic_url__isnull=True)
    set_3 = set_2.exclude(name__isnull=True)

    cnt = 0
    set_4_ids = []
    for inf in set_3:
        plats_count = inf.platforms().filter(url_not_found__isnull=False).count()
        if plats_count >= 2:
            set_4_ids.append(inf.id)
        cnt += 1
        if cnt % 1000 == 0:
            print('performed %s profiles for step 4' % cnt)

    print('Set 1 has %s influencers' % set_1.count())
    print('Set 2 (with non-null profile_pic_url) has %s influencers' % set_2.count())
    print('Set 3 (with non-null name) has %s influencers' % set_3.count())
    print('Set 4 (with at least 2 non-null url_not_found platforms) has %s influencers' % len(set_4_ids))

    set_4 = Influencer.objects.filter(id__in=set_4_ids)
    return set_4


def influencer_set_2():
    """
    https://app.asana.com/0/42664940909123/74028817581832

    :return: set_4 queryset
    """
    set_1 = Influencer.objects.filter(validated_on__contains='info').exclude(show_on_search=True).exclude(blacklisted=True)
    set_2 = set_1.exclude(profile_pic_url__isnull=True)
    set_3 = set_2.exclude(name__isnull=True)

    cnt = 0
    set_4_ids = []
    for inf in set_3:
        plats_count = inf.platforms().filter(url_not_found__isnull=False).count()
        if plats_count >= 2:
            set_4_ids.append(inf.id)
        cnt += 1
        if cnt % 1000 == 0:
            print('performed %s profiles for step 4' % cnt)

    print('Set 1 has %s influencers' % set_1.count())
    print('Set 2 (with non-null profile_pic_url) has %s influencers' % set_2.count())
    print('Set 3 (with non-null name) has %s influencers' % set_3.count())
    print('Set 4 (with at least 2 non-null url_not_found platforms) has %s influencers' % len(set_4_ids))

    set_4 = Influencer.objects.filter(id__in=set_4_ids)
    return set_4


def add_influencers_to_group(influencers_qs=None, group_name=None):
    """
    This helper puts all influencers from influencers_qs to InfluencerGroup with name group_name

    :param influencers_qs: queryset of influencers
    :param group_name: name of the influencer group
    :return:
    """
    from django.db.models.query import QuerySet
    from social_discovery.blog_discovery import queryset_iterator

    if not isinstance(group_name, str):
        print('group_name must be a name of existing InfluencerGroup')
        return

    if not isinstance(influencers_qs, QuerySet):
        print('influencers_qs must be a queryset of Influencer')
        return

    coll = InfluencersGroup.objects.get(name=group_name)

    influencers = queryset_iterator(influencers_qs)

    for inf in influencers:
        coll.add_influencer(inf)

def hundred():
    from debra.models import Influencer, Platform
    from platformdatafetcher.platformextractor import validate_platform
    alpha_inf = Influencer.objects.filter(show_on_search=True
                                          ).exclude(old_show_on_search=True
                                                    ).filter(validated_on__contains='info')
    alpha_inf_ids = alpha_inf.values_list('id', flat=True)
    platforms_autoverified_false = Platform.objects.filter(
        platform_name__in=Platform.SOCIAL_PLATFORMS,
        influencer_id__in=alpha_inf_ids).exclude(autovalidated=True).exclude(url_not_found=True)
    first_hundred = platforms_autoverified_false.exclude(num_followers__isnull=True).order_by('-num_followers')[:100]

    f = open('first_hundred.csv', 'a+')
    for p in first_hundred:
        source_platform = p.influencer.blog_platform
        if source_platform is None:
            f.write("%s;%s;%s;\n" % (p.url, p.num_followers, 'No blog platform for influencer %s' % p.influencer_id))
        else:
            reason = validate_platform(source_platform, p)
            f.write("%s;%s;%s;\n" % (p.url, p.num_followers, reason))
        print(p.url)
    f.close()


def get_unindexed_fashion_influencers():
    """
    Script to get a list of unindexed influencer from collection "Fashion InstagramProfiles"
    :return:
    """
    coll = InfluencersGroup.objects.get(name='Fashion InstagramProfiles')
    inf_ids = coll.influencer_ids
    not_indexed_ids = []
    indexed_ids = []
    # 1638424

    print("Total influencers in collection: %s" % len(inf_ids))

    for inf_id in inf_ids:
        endpoint = "/%s/influencer/%s" % (ELASTICSEARCH_INDEX, inf_id)
        url = ELASTICSEARCH_URL

        rq = make_es_head_request(url + endpoint)

        if rq.status_code == 400:
            not_indexed_ids.append(inf_id)
        elif rq.status_code == 200:
            indexed_ids.append(inf_id)

    print('Indexed: %s' % len(indexed_ids))
    print('Not indexed: %s' % len(not_indexed_ids))

    return not_indexed_ids, indexed_ids


def get_influencers_with_several_platforms_by_type(describe_infs=20):
    """
    Script to find a count of influencers with more than one platform of a type and show some of them.
    Had to use SQL because of unavailability of .annotate() due to JsonField package.
    :param describe_infs -- number of influencers to describe (print them and their platforms)
    :return:
    """

    # getting influencers with more than one platform for each type
    infs = Influencer.objects.extra(
        where=['''
            (SELECT MAX(N2.CNT) FROM (
                SELECT COUNT(id) AS CNT
                FROM debra_platform
                LEFT JOIN (
                    SELECT DISTINCT platform_name
                    FROM debra_platform
                    WHERE debra_platform.influencer_id = debra_influencer.id
                ) distinct_platform_names
                ON (debra_platform.platform_name = distinct_platform_names.platform_name)
                WHERE
                    (debra_platform.url_not_found IS NULL OR debra_platform.url_not_found = FALSE)
                AND
                    debra_platform.influencer_id = debra_influencer.id
                GROUP BY distinct_platform_names.platform_name
            ) N2 ) > 1
        ''']
    )

    # limiting them to those who have show_on_search and not blacklisted
    infs = infs.filter(show_on_search=True).exclude(blacklisted=True)

    # Showing count
    print('Influencers with more than 2 platforms of a type: %s' % infs.count())

    # Printing first describe_infs influencers
    for inf in infs[:describe_infs]:
        print('=============================================')
        print('Influencer id: %s  Name: %s' % (inf.id, inf.name))
        plats = inf.platform_set.exclude(url_not_found=True)
        for p in plats:
            print('Platform: id: %s  Name: %s  Url: %s  Create_date: %s' % (
                p.id, p.platform_name, p.url, p.create_date)
            )

def visible_vs_autovalidated_platforms():

    """
    https://app.asana.com/0/42664940909123/76971013536330
    :return:
    """

    import io
    from platformdatafetcher.platformextractor import autovalidate_platform

    platform_names = [p for p in Platform.SOCIAL_PLATFORMS if p not in ['Fashiolista', 'Lookbook']]
    # platform_names.append('Custom')

    platforms = Platform.objects.filter(
        influencer__show_on_search=True,
        platform_name__in=platform_names
    ).exclude(
        influencer__blacklisted=True
    )

    # limiting platforms by followers number greater than 50
    platforms = platforms.filter(num_followers__gt=50)

    # Limiting subset by influencer's names starting with 'a' to 'c'
    platforms = platforms.filter(Q(influencer__name__istartswith='a') | Q(influencer__name__istartswith='b') | Q(influencer__name__istartswith='c'))

    # visible : autovalidated ratio
    print('Current visible/autovalidated ratio: %s/%s' % (platforms.exclude(url_not_found=True).count(),
                                                          platforms.filter(autovalidated=True).count()
                                                          ))
    print('=================================================')

    # 'Good platforms': visible and validated
    good = platforms.filter(autovalidated=True).exclude(url_not_found=True)
    print('Platforms visible and autovalidated: %s' % good.count())
    print('By platforms:')
    for platform_name in platform_names:
        print('    %s: %s' % (platform_name, good.filter(platform_name=platform_name).count()))
        if platform_name == 'Twitter':
            csvfile = io.open('twitter_good__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
            csvfile.write(
                u'Platform_id\tName\tUrl\tautovalidated\tautovalidated_reason\turl_not_found\tvalidated_handle\tinfluencer_id\tinfluencer.blog_url\tinfluencer.name\n'
            )
            for p in good.filter(platform_name=platform_name).select_related('influencer'):
                csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                    p.id,
                    p.platform_name,
                    p.url,
                    p.autovalidated,
                    p.autovalidated_reason,
                    p.url_not_found,
                    p.validated_handle,
                    p.influencer_id,
                    p.influencer.blog_url,
                    p.influencer.name,
                )
                )
            csvfile.close()

    print('=================================================')

    # not visible but validated
    bad_type_1 = platforms.filter(url_not_found=True).filter(autovalidated=True)
    print('Platforms not visible but autovalidated: %s' % bad_type_1.count())
    print('By platforms:')
    for platform_name in platform_names:
        print('    %s: %s' % (platform_name, bad_type_1.filter(platform_name=platform_name).count()))
        if platform_name == 'Twitter':
            csvfile = io.open('twitter_bad_type_1__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
            csvfile.write(
                u'Platform_id\tName\tUrl\tautovalidated\tautovalidated_reason\turl_not_found\tvalidated_handle\tinfluencer_id\tinfluencer.blog_url\tinfluencer.name\n'
            )
            for p in bad_type_1.filter(platform_name=platform_name).select_related('influencer'):
                csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                    p.id,
                    p.platform_name,
                    p.url,
                    p.autovalidated,
                    p.autovalidated_reason,
                    p.url_not_found,
                    p.validated_handle,
                    p.influencer_id,
                    p.influencer.blog_url,
                    p.influencer.name,
                )
                )
            csvfile.close()

    print('=================================================')
    # visible but not autovalidated
    bad_type_2 = platforms.exclude(url_not_found=True).exclude(autovalidated=True)
    print('Platforms visible but not autovalidated: %s' % bad_type_2.count())
    print('By platforms:')

    for platform_name in platform_names:
        print('    %s: %s' % (platform_name, bad_type_2.filter(platform_name=platform_name).count()))
        if platform_name == 'Twitter':
            csvfile = io.open('twitter_bad_type_2__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
            csvfile.write(
                u'Platform_id\tName\tUrl\tautovalidated\tautovalidated_reason\turl_not_found\tvalidated_handle\tinfluencer_id\tinfluencer.blog_url\tinfluencer.name\n'
            )
            empty_blog_platform = []
            for p in bad_type_2.filter(platform_name=platform_name).select_related('influencer'):

                csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                    p.id,
                    p.platform_name,
                    p.url,
                    p.autovalidated,
                    p.autovalidated_reason,
                    p.url_not_found,
                    p.validated_handle,
                    p.influencer_id,
                    p.influencer.blog_url,
                    p.influencer.name,
                )
                )

                # # sending a task to autovalidate the platform
                # source_platform = p.influencer.blog_platform
                # if source_platform:
                #     autovalidate_platform.apply_async(
                #         kwargs={
                #             'source_platform_id': source_platform.id,
                #             'platform_id': p.id,
                #         },
                #         queue='platform_extraction'
                #     )
                # else:
                #     print('Task was not issued for influencer %s' % p.influencer.id)
                #     empty_blog_platform.append(p.influencer.id)
            # print(empty_blog_platform)
            csvfile.close()

    print('=================================================')

    # fetching not visible and not validated
    need_investigation = platforms.filter(url_not_found=True).exclude(autovalidated=True)
    print('Platforms not visible and not autovalidated (needs investigation): %s' % need_investigation.count())
    print('By platforms:')
    for platform_name in platform_names:
        print('    %s: %s' % (platform_name, need_investigation.filter(platform_name=platform_name).count()))
        if platform_name == 'Twitter':
            csvfile = io.open('twitter_need_investigation__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
            csvfile.write(
                u'Platform_id\tName\tUrl\tautovalidated\tautovalidated_reason\turl_not_found\tvalidated_handle\tinfluencer_id\tinfluencer.blog_url\tinfluencer.name\n'
            )
            for p in need_investigation.filter(platform_name=platform_name).select_related('influencer'):
                csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                    p.id,
                    p.platform_name,
                    p.url,
                    p.autovalidated,
                    p.autovalidated_reason,
                    p.url_not_found,
                    p.validated_handle,
                    p.influencer_id,
                    p.influencer.blog_url,
                    p.influencer.name,
                )
                )
            csvfile.close()

    print('=================================================')


def influencers_without_blog_platform():
    """
    Script creates two csv files: one with influencers without blog_platform, and another with influencers that have
    more than one inf.platforms().filter(platform_name__in=['Blogspot', 'Wordpress', 'Custom']).exclude(url_not_found=True)
    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator
    import io

    print('Getting infs without blog_platform...')

    infs = Influencer.objects.filter(show_on_search=True,
                                     # old_show_on_search=True
                                     ).exclude(blacklisted=True).select_related('platform')

    # infs without blog_platform
    csvfile = io.open('influencers_without_blog_platform__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tinfluencer.name\tblog_url\n'
    )

    infs_qs = queryset_iterator(infs)
    for inf in infs_qs:
        if inf.blog_platform is None:
            csvfile.write(u'%s\t%s\t%s\n' % (
                inf.id,
                inf.name,
                inf.blog_url,
            ))
    csvfile.close()

    print('Getting influencers with more than one platform for each type...')

    # getting influencers with more than one platform for each type
    csvfile = io.open('influencers_with_several_blogs__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tinfluencer.name\tQty of platforms\n'
    )

    infs = infs.extra(
        where=['''
            (SELECT MAX(N2.CNT) FROM (
                SELECT COUNT(id) AS CNT
                FROM debra_platform
                WHERE
                    (debra_platform.url_not_found IS NULL OR debra_platform.url_not_found = FALSE)
                AND
                    debra_platform.influencer_id = debra_influencer.id
                AND
                    platform_name IN ('Blogspot', 'Wordpress', 'Custom')
            ) N2 ) > 1
        ''']
    )

    infs_qs = queryset_iterator(infs)
    for inf in infs_qs:
        csvfile.write(u'%s\t%s\t%s\n' % (
            inf.id,
            inf.name,
            inf.platforms().filter(
                platform_name__in=['Blogspot', 'Wordpress', 'Custom']
            ).exclude(url_not_found=True).count(),
        ))
    csvfile.close()


def get_csv_influencers_without_blog_url():

    from social_discovery.blog_discovery import queryset_iterator
    import io

    infs = Influencer.objects.filter(show_on_search=True,
                                     # old_show_on_search=True
                                     ).exclude(blacklisted=True).values('id', 'name', 'blog_url')

    csvfile = io.open('influencers_without_blog_url__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'a+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tinfluencer.name\n'
    )

    for inf in infs:
        if inf['blog_url'] is None or len(inf['blog_url'].strip()) == 0:
            csvfile.write(u'%s\t%s\n' % (
                inf['id'],
                inf['name'],
            ))
    csvfile.close()


def bad_type_1_resolving():
    """
    https://app.asana.com/0/42664940909123/78791251728185

    Currently only for twitter

    Investigating bad platforms...
    :return:
    """

    platform_name_to_perform = 'Instagram'  # 'Twitter'

    import io
    from platformdatafetcher.platformutils import username_from_platform_url, record_field_change

    platforms = Platform.objects.filter(
        influencer__show_on_search=True,
        platform_name=platform_name_to_perform
    ).exclude(
        influencer__blacklisted=True
    )

    # limiting platforms by followers number greater than 50
    platforms = platforms.filter(num_followers__gt=50)

    # Limiting subset by influencer's names starting with 'a' to 'c'
    platforms = platforms.filter(
        Q(influencer__name__istartswith='a') |
        Q(influencer__name__istartswith='b') |
        Q(influencer__name__istartswith='c'))

    # not visible but validated
    bad_type_1 = platforms.filter(url_not_found=True).filter(autovalidated=True)
    print('%s platforms not visible but autovalidated: %s' % (platform_name_to_perform, bad_type_1.count()))

    csvfile1 = io.open('%s_non_duplicate_visible_autovalidated__%s.csv' % (platform_name_to_perform, datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S')), 'w+', encoding='utf-8')
    csvfile1.write(
        u'Platform_id\tName\tUrl\tvalidated_handle\tinfluencer_id\tinfluencer.blog_url\tinfluencer.name\n'
    )
    csvfile2 = io.open('%s_non_duplicate_visible_not_autovalidated__%s.csv' % (platform_name_to_perform, datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S')), 'w+', encoding='utf-8')
    csvfile2.write(
        u'Platform_id\tName\tUrl\tvalidated_handle\tinfluencer_id\tinfluencer.blog_url\tinfluencer.name\n'
    )

    ctr = 0
    for plat in bad_type_1.select_related('influencer'):

        plat_username = username_from_platform_url(plat.url.lower())  # username for detecting duplicates

        inf = plat.influencer
        # check if there is a duplicate platform (p2) which is autovalidated and is visible

        other_plats = inf.platform_set.filter(platform_name=platform_name_to_perform).exclude(id=plat.id).exclude(url_not_found=True)

        done = False  # flag of no further steps needed
        case = None
        # CASE A
        for op in other_plats:
            op_username = username_from_platform_url(op.url.lower())  # username for detecting duplicates

            if plat_username == op_username and op.autovalidated is True:
                # found a duplicate that autovalidated and visible
                print('Found duplicate platforms: id=%s username=%s  AND  id=%s username=%s' % (plat.id,
                                                                                                plat_username,
                                                                                                op.id,
                                                                                                op_username))

                # setting plat's autovalidated to False, finishing performance
                autovalidated_prev = plat.autovalidated
                record_field_change('autovalidated_unset', 'autovalidated', autovalidated_prev, False, platform=plat)
                plat.autovalidated = False
                plat.save()

                done = True
                case = 'Case A'
                break

        # CASE B
        if not done:
            for op in other_plats:
                op_username = username_from_platform_url(op.url.lower())  # username for detecting duplicates
                if plat_username != op_username:
                    if op.autovalidated is True:
                        csvfile1.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                            plat.id,
                            plat.platform_name,
                            plat.url,
                            plat.validated_handle,
                            plat.influencer.id,
                            plat.influencer.blog_url,
                            plat.influencer.name,
                        ))
                        done = True
                        case = 'Case B.1'
                        break
                    else:
                        csvfile2.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                            plat.id,
                            plat.platform_name,
                            plat.url,
                            plat.validated_handle,
                            plat.influencer.id,
                            plat.influencer.blog_url,
                            plat.influencer.name,
                        ))
                        done = True
                        case = 'Case B.2'
                        break

        # CASE C
        if not done:
            if other_plats.count() == 0:

                # setting plat's url_not_found to False, finishing performance
                url_not_found_prev = plat.url_not_found
                record_field_change('url_not_found_to_false', 'url_not_found', url_not_found_prev, False, platform=plat)
                plat.url_not_found = False
                plat.save()

                # resetting validated_handle for all platforms
                inf.platform_set.filter(platform_name=platform_name_to_perform).update(validated_handle=None)

                case = 'Case C'

        ctr += 1
        print('Done platform id %s, %s, %s' % (plat.id, case, ctr))

    csvfile1.close()
    csvfile2.close()




def bad_type_2_resolving():
    """
    https://app.asana.com/0/42664940909123/78791251728185

    re-autovalidating social platforms for influencers with show_on_search=True, excluding blacklisted=True

    Investigating bad platforms...
    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator
    import io
    from platformdatafetcher.platformextractor import autovalidate_platform

    platform_names = [p for p in Platform.SOCIAL_PLATFORMS if p not in ['Fashiolista', 'Lookbook']]
    # platform_names.append('Custom')

    platforms = Platform.objects.filter(
        influencer__show_on_search=True,
        platform_name__in=platform_names
    ).exclude(
        influencer__blacklisted=True
    )

    # limiting platforms by followers number greater than 50
    platforms = platforms.filter(num_followers__gt=50)

    # visible but not autovalidated
    bad_type_2 = platforms.exclude(url_not_found=True).exclude(autovalidated=True)
    print('Platforms to revalidate: %s' % bad_type_2.count())
    bad_type_2 = platforms.exclude(url_not_found=True).exclude(autovalidated=True)

    empty_blog_platform_ctr = 0
    sent_to_autovalidate_ctr = 0
    bad_type_2_qs = queryset_iterator(bad_type_2)
    for p in bad_type_2_qs:
        # sending a task to autovalidate the platform
        source_platform = p.influencer.blog_platform
        if source_platform:
            autovalidate_platform.apply_async(
                kwargs={
                    'source_platform_id': source_platform.id,
                    'platform_id': p.id,
                },
                queue='platform_extraction'
            )
            sent_to_autovalidate_ctr += 1
        else:
            print('Task was not issued for platform %s' % p.id)
            empty_blog_platform_ctr += 1

        if sent_to_autovalidate_ctr % 1000 == 0:
            print('Sent to autovalidate: %s' % sent_to_autovalidate_ctr)

    print('Finally, sent to autovalidate: %s' % sent_to_autovalidate_ctr)


def visible_vs_autovalidated_influencers():
    """
    https://app.asana.com/0/42664940909123/76971013536330
    :return:
    """
    import io
    platform_names = [p for p in Platform.SOCIAL_PLATFORMS if p not in ['Fashiolista', 'Lookbook']]
    # platform_names.append('Custom')

    platform_names = ['Twitter',]

    influencers = Influencer.objects.filter(
        show_on_search=True,
        # platform_name__in=platform_names
    ).exclude(
        blacklisted=True
    )

    # Limiting subset by influencer's names starting with 'a' to 'c'
    influencers = influencers.filter(Q(name__istartswith='a') | Q(name__istartswith='b') | Q(name__istartswith='c'))

    influencers = Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)

    print('=================================================')
    print('Total Influencers to check in: %s' % influencers.count())
    print('=================================================')

    # 'Good platforms': visible and validated
    for platform_name in platform_names:

        infs = influencers.filter(platform__platform_name=platform_name).distinct()
        print('%s (with at least 1 %s platform): %s' % (platform_name, platform_name, infs.count()))

        # visible and auto-validated
        good_ones = infs.extra(
            where=[
                "platform_name = '%s' AND autovalidated = TRUE AND (url_not_found IS NULL OR url_not_found = FALSE) " % platform_name,
            ]
        ).distinct()
        good_ids = list(good_ones.values_list('id', flat=True))
        print('    good group: %s' % len(good_ids))

        good_infs = influencers.filter(id__in=good_ids, platform__platform_name=platform_name)
        has_visible = good_infs.extra(where=["platform_name = '%s' AND (url_not_found IS NULL OR url_not_found = FALSE)" % platform_name,]).distinct().values_list('id', flat=True)
        has_visible = list(has_visible)
        has_no_visible = []
        for i in list(good_infs.values_list('id', flat=True)):
            if i not in list(has_visible) and i not in has_no_visible:
                has_no_visible.append(i)

        print('        a) do not have any visible platforms: %s' % len(has_no_visible))

        visible_and_autovalidated = good_infs.extra(where=["platform_name = '%s' AND autovalidated = TRUE AND (url_not_found IS NULL OR url_not_found = FALSE) " % platform_name,]).distinct()
        print('        b) visible and autovalidated among them: %s' % visible_and_autovalidated.count())

        visible_and_non_autovalidated = good_infs.extra(where=["platform_name = '%s' AND (autovalidated IS NULL OR autovalidated = FALSE) AND (url_not_found IS NULL OR url_not_found = FALSE) " % platform_name,]).distinct()
        print('        c) visible and non-autovalidated among them: %s' % visible_and_non_autovalidated.count())

        # not visible but validated
        bad_type_1 = infs.exclude(id__in=good_ids).extra(
            where=[
                "platform_name = '%s' AND autovalidated = TRUE AND url_not_found = True " % platform_name,
            ]
        ).distinct()
        bad_type_1_ids = list(bad_type_1.values_list('id', flat=True))
        print('    bad type 1: %s' % len(bad_type_1_ids))

        bad_type_1_infs = influencers.filter(id__in=bad_type_1_ids, platform__platform_name=platform_name)
        has_visible = bad_type_1_infs.extra(where=["platform_name = '%s' AND (url_not_found IS NULL OR url_not_found = FALSE)" % platform_name,]).distinct().values_list('id', flat=True)
        has_visible = list(has_visible)
        has_no_visible = []
        for i in list(bad_type_1_infs.values_list('id', flat=True)):
            if i not in list(has_visible) and i not in has_no_visible:
                has_no_visible.append(i)
        print('        a) do not have any visible platforms: %s' % len(has_no_visible))

        visible_and_autovalidated = bad_type_1_infs.extra(where=["platform_name = '%s' AND autovalidated = TRUE AND (url_not_found IS NULL OR url_not_found = FALSE) " % platform_name,]).distinct()
        print('        b) visible and autovalidated among them: %s' % visible_and_autovalidated.count())

        visible_and_non_autovalidated = bad_type_1_infs.extra(where=["platform_name = '%s' AND (autovalidated IS NULL OR autovalidated = FALSE) AND (url_not_found IS NULL OR url_not_found = FALSE) " % platform_name,]).distinct()
        print('        c) visible and non-autovalidated among them: %s' % visible_and_non_autovalidated.count())

        # visible but not autovalidated
        bad_type_2 = infs.exclude(id__in=good_ids).exclude(id__in=bad_type_1_ids).extra(
            where=[
                "platform_name = '%s' AND (autovalidated IS NULL OR autovalidated = FALSE) AND (url_not_found IS NULL OR url_not_found = FALSE) " % platform_name,
            ]
        )
        bad_type_2_ids = list(bad_type_2.values_list('id', flat=True))
        print('    bad type 2: %s' % len(bad_type_2_ids))

        bad_type_2_infs = influencers.filter(id__in=bad_type_2_ids, platform__platform_name=platform_name)
        has_visible = bad_type_2_infs.extra(where=["platform_name = '%s' AND (url_not_found IS NULL OR url_not_found = FALSE)" % platform_name,]).distinct().values_list('id', flat=True)
        has_visible = list(has_visible)
        has_no_visible = []
        for i in list(bad_type_2_infs.values_list('id', flat=True)):
            if i not in list(has_visible) and i not in has_no_visible:
                has_no_visible.append(i)

        print('        a) do not have any visible platforms: %s' % len(has_no_visible))

        visible_and_autovalidated = bad_type_2_infs.extra(where=["platform_name = '%s' AND autovalidated = TRUE AND (url_not_found IS NULL OR url_not_found = FALSE) " % platform_name,]).distinct()
        print('        b) visible and autovalidated among them: %s' % visible_and_autovalidated.count())

        visible_and_non_autovalidated = bad_type_2_infs.extra(where=["platform_name = '%s' AND (autovalidated IS NULL OR autovalidated = FALSE) AND (url_not_found IS NULL OR url_not_found = FALSE) " % platform_name,]).distinct()
        print('        c) visible and non-autovalidated among them: %s' % visible_and_non_autovalidated.count())

        # fetching not visible and not validated
        investigate = infs.exclude(id__in=good_ids).exclude(id__in=bad_type_1_ids).exclude(id__in=bad_type_2_ids).extra(
            where=[
                "platform_name = '%s' AND (autovalidated IS NULL OR autovalidated = FALSE) AND url_not_found = TRUE " % platform_name,
            ])
        investigate_ids = list(investigate.values_list('id', flat=True))
        print('    investigate: %s' % len(investigate_ids))
        print('Summary total: %s' % (len(good_ids) + len(bad_type_1_ids) + len(bad_type_2_ids) + len(investigate_ids)))
        print('=================================================')

    print(' good group -- visible and autovalidated')
    print(' bad type 1 -- not visible but autovalidated')
    print(' bad type 2 -- visible but not autovalidated')
    print(' investigate -- not visible and not autovalidated')
    print('=================================================')


def revalidating_top_300_1_2():
    """

    Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)
    1. Let's pick the top 300 influencers.
        Sort these influencers by follower counts total (from their visible platforms).
        Pick first 100 influencers who in total have at least 10,000 followers.
        Pick the next 100 influencers who in total have at least 50,000 followers
        Pick the next 100 influencers who in total have at least 100,000 followers
    2. Then, let's run the new autovalidation logic for the platforms that are not autovalidated.
        No need to check the delay between when was the last time we ran extraction.
        For influencers that have validated_on__contains='info', check their date_edited field.
        If it's more than 1 month older, run the new code.


    3. Next, for the same influencers, run extract_combined(influencer.blog_platform.id).
        This should help us find any platforms that were missed.

    4. Now, for these 300 influencers, put the visible but not autovalidated influencers in a spreadsheet so
        that we can check them.

    :return:
    """

    import io
    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.platformextractor import autovalidate_platform

    # infs = Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)
    #
    # # Pick first 100 influencers who in total have at least 10,000 followers.
    # first_100 = infs.filter(platform__num_followers__gt=10000, platform__num_followers__lt=50000).order_by('platform__num_followers').distinct().values_list('id', flat=True)[:100]
    # first_ids = list(first_100)
    #
    # # Pick the next 100 influencers who in total have at least 50,000 followers
    # second_100 = infs.exclude(id__in=first_ids).filter(platform__num_followers__gt=50000, platform__num_followers__lt=100000).order_by('platform__num_followers').distinct().values_list('id', flat=True)[:100]
    # second_ids = list(second_100)
    #
    # # Pick the next 100 influencers who in total have at least 100,000 followers
    # third_100 = infs.exclude(id__in=first_ids).exclude(id__in=second_ids).filter(platform__num_followers__gt=100000).order_by('platform__num_followers').distinct().values_list('id', flat=True)[:100]
    # third_ids = list(third_100)

    first_ids = [1460182, 2202976, 2383451, 1252034, 2503701, 2540867, 1134709, 2388780, 1008668, 2394387, 2657060,
                 2371031, 2456535, 2397618, 2403292, 2558931, 2613770, 1121233, 1782302, 2372346, 1038482, 1500491,
                 2474915, 2489342, 2450685, 2550521, 924715, 1639442, 2480119, 1582344, 1275458, 1462288, 2591768,
                 2547239, 2566608, 2575485, 2366328, 2426971, 2649750, 2592192, 2429959, 2758474, 2378972, 2386701,
                 1148655, 2383304, 2714750, 887180, 2396399, 2643801, 2652762, 2002773, 2410945, 2507007,
                 1117915, 908454, 1438606, 2419547, 2471403, 2387034, 1093009, 2382443, 2589779, 2486271, 1529253,
                 1540854, 2442191, 2501510, 876158, 2387630, 2428930, 1509755, 1295956, 2589115, 938954, 2418472,
                 2507201, 2383807, 2716301, 2425840, 2604195, 1833591, 2520127, 2676044, 1006664, 2418245, 2386852,
                 2516891, 2452866, 1789486, 2660195, 2718801, 2395158, 2621470, 2621196, 2367960, 2415863, 1415176,
                 1030029]

    second_ids = [1266993, 2499015, 2210957, 2367663, 2422560, 1980290, 2038491, 2164202, 2326797, 2440257, 2530540,
                  2507468, 2374443, 1027966, 2511689, 2370778, 2381913, 2651692, 1813393, 2367878, 1116571, 1532861,
                  2648639, 2417214, 2452304, 2656035, 2372136, 2477321, 883506, 2538591, 2556956, 1772727, 2409248,
                  2370246, 2446294, 1858606, 2640084, 1078933, 2759197, 2368775, 2458346, 953972, 1910515, 2366086,
                  2388732, 2446789, 2377914, 2381366, 2574992, 2709957, 2374627, 2465053, 2575040, 759161, 950890,
                  2407338, 2401238, 2055840, 2433606, 1521798, 1585669, 2718231, 2524732, 2644755, 2746036, 2394321,
                  985571, 2542119, 2518030, 1588907, 2648117, 2013985, 2530540, 2502931, 973458, 1037173, 2365960,
                  1030663, 2402840, 2569738, 911511, 2383606, 2647909, 2582251, 2373969, 990223, 2367982, 2367684,
                  2644388, 2659310, 1327568, 2517207, 2526341, 2376433, 2416146, 2366377, 2731985, 1831382, 1661028,
                  2742492]

    third_ids = [2505851, 2523871, 2765142, 1788952, 2589386, 1454202, 1282325, 1778192, 1778777, 2728969, 962993,
                 2489163, 2542831, 2421215, 2370100, 2511466, 2495407, 2006221, 2382507, 2428375, 902923, 1070864,
                 1271855, 2471975, 2435554, 1149995, 2381858, 1853680, 2577336, 2492964, 2430903, 1892801, 1043856,
                 2761975, 879519, 1474087, 2373761, 2521099, 1467418, 1448250, 2372725, 2758748, 2481252, 2388415,
                 2498038, 2758255, 1513345, 1525040, 2529665, 2393619, 2472150, 2383826, 2379745, 1259737, 2616412,
                 1171651, 1452403, 2048075, 2432261, 2625800, 2649879, 2391295, 2657660, 2387789, 903821, 2613173,
                 1632738, 1815740, 1669806, 2486543, 2751937, 1902781, 1455773, 1466232, 2016496, 2007819, 2494465,
                 2645478, 2269386, 1749459, 2392996, 1344054, 1024619, 2438863, 2420932, 2414357, 2510729, 2382399,
                 876823, 2394237, 2570362, 2409579, 2391656, 2374632, 2468554, 2380441, 941098, 2711453, 2396450,
                 1140482]

    ids = first_ids + second_ids + third_ids
    print('Total influencers ids count: %s' % len(ids))

    infs_qs = Influencer.objects.filter(id__in=ids).select_related('platform')

    print('Total infuencers to revalidate: %s' % infs_qs.count())

    # run the new autovalidation logic for the platforms that are not autovalidated
    csvfile = io.open('300_autovalidated__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tName\tBlog_platform.id\tBlog_platform.url\tPlatform id\tPlatform Name\tPlatform url\told autovalidated\n'
    )
    for inf in queryset_iterator(infs_qs):

        blog_plat = inf.blog_platform

        plats = inf.platform_set.exclude(autovalidated=True)

        for plat in plats:

            if isinstance(blog_plat, Platform):
                # autovalidate_platform(blog_plat.id, plat.id)
                autovalidate_platform.apply_async(
                    kwargs={
                        'source_platform_id': blog_plat.id,
                        'platform_id': plat.id,
                    },
                    queue='platform_extraction'
                )

            csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                inf.id,
                inf.name,
                blog_plat.id if isinstance(blog_plat, Platform) else None,
                blog_plat.url if isinstance(blog_plat, Platform) else None,
                plat.id,
                plat.platform_name,
                plat.url,
                plat.autovalidated,
            ))

    csvfile.close()


def revalidating_top_300_3():
    """

    Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)
    1. Let's pick the top 300 influencers.
        Sort these influencers by follower counts total (from their visible platforms).
        Pick first 100 influencers who in total have at least 10,000 followers.
        Pick the next 100 influencers who in total have at least 50,000 followers
        Pick the next 100 influencers who in total have at least 100,000 followers

    3. Next, for the same influencers, run extract_combined(influencer.blog_platform.id).
        This should help us find any platforms that were missed.

    4. Now, for these 300 influencers, put the visible but not autovalidated influencers in a spreadsheet so
        that we can check them.

    :return:
    """

    import io
    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.platformextractor import extract_combined

    first_ids = [1460182, 2202976, 2383451, 1252034, 2503701, 2540867, 1134709, 2388780, 1008668, 2394387, 2657060,
                 2371031, 2456535, 2397618, 2403292, 2558931, 2613770, 1121233, 1782302, 2372346, 1038482, 1500491,
                 2474915, 2489342, 2450685, 2550521, 924715, 1639442, 2480119, 1582344, 1275458, 1462288, 2591768,
                 2547239, 2566608, 2575485, 2366328, 2426971, 2649750, 2592192, 2429959, 2758474, 2378972, 2386701,
                 1148655, 2383304, 2714750, 887180, 2396399, 2643801, 2652762, 2002773, 2410945, 2507007,
                 1117915, 908454, 1438606, 2419547, 2471403, 2387034, 1093009, 2382443, 2589779, 2486271, 1529253,
                 1540854, 2442191, 2501510, 876158, 2387630, 2428930, 1509755, 1295956, 2589115, 938954, 2418472,
                 2507201, 2383807, 2716301, 2425840, 2604195, 1833591, 2520127, 2676044, 1006664, 2418245, 2386852,
                 2516891, 2452866, 1789486, 2660195, 2718801, 2395158, 2621470, 2621196, 2367960, 2415863, 1415176,
                 1030029]

    second_ids = [1266993, 2499015, 2210957, 2367663, 2422560, 1980290, 2038491, 2164202, 2326797, 2440257, 2530540,
                  2507468, 2374443, 1027966, 2511689, 2370778, 2381913, 2651692, 1813393, 2367878, 1116571, 1532861,
                  2648639, 2417214, 2452304, 2656035, 2372136, 2477321, 883506, 2538591, 2556956, 1772727, 2409248,
                  2370246, 2446294, 1858606, 2640084, 1078933, 2759197, 2368775, 2458346, 953972, 1910515, 2366086,
                  2388732, 2446789, 2377914, 2381366, 2574992, 2709957, 2374627, 2465053, 2575040, 759161, 950890,
                  2407338, 2401238, 2055840, 2433606, 1521798, 1585669, 2718231, 2524732, 2644755, 2746036, 2394321,
                  985571, 2542119, 2518030, 1588907, 2648117, 2013985, 2530540, 2502931, 973458, 1037173, 2365960,
                  1030663, 2402840, 2569738, 911511, 2383606, 2647909, 2582251, 2373969, 990223, 2367982, 2367684,
                  2644388, 2659310, 1327568, 2517207, 2526341, 2376433, 2416146, 2366377, 2731985, 1831382, 1661028,
                  2742492]

    third_ids = [2505851, 2523871, 2765142, 1788952, 2589386, 1454202, 1282325, 1778192, 1778777, 2728969, 962993,
                 2489163, 2542831, 2421215, 2370100, 2511466, 2495407, 2006221, 2382507, 2428375, 902923, 1070864,
                 1271855, 2471975, 2435554, 1149995, 2381858, 1853680, 2577336, 2492964, 2430903, 1892801, 1043856,
                 2761975, 879519, 1474087, 2373761, 2521099, 1467418, 1448250, 2372725, 2758748, 2481252, 2388415,
                 2498038, 2758255, 1513345, 1525040, 2529665, 2393619, 2472150, 2383826, 2379745, 1259737, 2616412,
                 1171651, 1452403, 2048075, 2432261, 2625800, 2649879, 2391295, 2657660, 2387789, 903821, 2613173,
                 1632738, 1815740, 1669806, 2486543, 2751937, 1902781, 1455773, 1466232, 2016496, 2007819, 2494465,
                 2645478, 2269386, 1749459, 2392996, 1344054, 1024619, 2438863, 2420932, 2414357, 2510729, 2382399,
                 876823, 2394237, 2570362, 2409579, 2391656, 2374632, 2468554, 2380441, 941098, 2711453, 2396450,
                 1140482]

    ids = first_ids + second_ids + third_ids

    # TODO: OVERRIDE: only GOOD influencers for now
    ids = [759161, 876823, 883506, 887180, 902923, 903821, 908454, 924715, 938954, 941098, 973458, 985571, 990223,
           1006664, 1008668, 1024619, 1027966, 1030663, 1037173, 1038482, 1043856, 1070864, 1078933, 1093009, 1117915,
           1121233, 1134709, 1148655, 1149995, 1171651, 1266993, 1282325, 1295956, 1344054, 1415176, 1438606,
           1448250, 1452403, 1454202, 1455773, 1466232, 1509755, 1525040, 1529253, 1532861, 1540854, 1582344, 1585669,
           1588907, 1632738, 1661028, 1669806, 1749459, 1778192, 1778777, 1782302, 1788952, 1789486, 1815740, 1853680,
           1858606, 1910515, 2002773, 2006221, 2007819, 2013985, 2269386, 2326797, 2365960, 2366086, 2366377, 2367663,
           2367684, 2367878, 2368775, 2370100, 2370246, 2370778, 2371031, 2372346, 2372725, 2373761, 2373969, 2374443,
           2374627, 2376433, 2377914, 2378972, 2381366, 2381858, 2381913, 2382399, 2382443, 2382507, 2383304, 2383451,
           2383606, 2386701, 2386852, 2387034, 2387630, 2387789, 2388415, 2388732, 2388780, 2392996, 2393619, 2394237,
           2394321, 2394387, 2396399, 2397618, 2401238, 2402840, 2403292, 2407338, 2409248, 2409579, 2410945, 2414357,
           2418245, 2419547, 2420932, 2421215, 2422560, 2425840, 2426971, 2428375, 2428930, 2430903, 2432261, 2433606,
           2438863, 2440257, 2446294, 2446789, 2450685, 2456535, 2468554, 2471403, 2471975, 2472150, 2477321, 2480119,
           2481252, 2486271, 2486543, 2492964, 2495407, 2498038, 2502931, 2503701, 2507007, 2507201, 2510729, 2511466,
           2518030, 2520127, 2521099, 2523871, 2524732, 2526341, 2529665, 2538591, 2540867, 2542119, 2547239, 2550521,
           2556956, 2558931, 2566608, 2569738, 2574992, 2575040, 2575485, 2577336, 2582251, 2589115, 2589779, 2592192,
           2604195, 2613173, 2613770, 2616412, 2625800, 2643801, 2644388, 2644755, 2645478, 2647909, 2648117, 2649750,
           2649879, 2651692, 2652762, 2656035, 2657060, 2657660, 2659310, 2660195, 2709957, 2711453, 2714750, 2716301,
           2728969, 2731985, 2742492, 2746036, 2758255, 2758474, 2758748, 2759197, 2761975, 2765142]

    # SECOND 300 guys
    first_ids = [2375228, 2385748, 2228136, 2414770, 2366428, 2391897, 1051857, 1674582, 2518791, 2414727, 2562363,
                 1586093, 2504499, 1464099, 2401008, 2516867, 2416584, 2368158, 1593841, 1135493, 1112713, 1381689,
                 2313549, 2434703, 2696342, 2412674, 1079867, 1813639, 1830570, 2688269, 2157125, 2372017, 2579060,
                 1406933, 2652123, 2436151, 2411931, 2397500, 2517942, 2486595, 2766696, 2418846, 2370873, 2651596,
                 2683248, 2753685, 2566731, 2618815, 1125775, 1714945, 2352085, 2399116, 2641224, 888841, 2372379,
                 2542421, 2574452, 1097598, 2507088, 2739558, 2753790, 2237504, 2391653, 2394834, 1060386, 2511627,
                 1811565, 962206, 1201286, 2396258, 2460874, 2499259, 2470390, 1359521, 2365811, 2430684, 2548580,
                 2414006, 2453353, 2658432, 2660531, 2480754, 2661220, 1381084, 1812472, 2374470, 2447407, 2752492,
                 1387224, 1204237, 2445155, 2645532, 1392033, 1257673, 1296464, 2435887, 2372609, 2479851, 2496038,
                 2649706]
    second_ids = [1463193, 2426630, 1361215, 922821, 2366332, 1407480, 2397256, 2388367, 1773259, 2368425, 1416251,
                  2452784, 2440214, 2452575, 760595, 956008, 2723525, 2485269, 2732480, 1780914, 1761138, 2672389,
                  2109996, 1138126, 1807249, 2275097, 2371360, 2560150, 2622552, 2753765, 2425671, 2417535, 2661458,
                  2469510, 2425827, 2393042, 2051835, 2652912, 2366273, 2383337, 2381868, 2419764, 1572804, 2377219,
                  2397820, 2383003, 2457122, 2551073, 1862577, 1998771, 2426728, 2430631, 2448345, 2759483, 2605755,
                  2387915, 1508073, 2515562, 2752889, 1210595, 2404956, 2509527, 908383, 2595585, 2383556, 2488126,
                  1093715, 2529790, 1052870, 1078042, 2418613, 2378016, 2380824, 2387605, 2610264, 2294460, 2474571,
                  1368847, 2605293, 1449368, 2476524, 1767612, 2398496, 2453648, 2738761, 2433034, 1604979, 1608328,
                  2464514, 2761073, 2368660, 2454408, 1783335, 1238051, 2384689, 1150856, 2379155, 2520115, 2659066,
                  2627125]
    third_ids = [875640, 1069124, 1391254, 1296388, 1895956, 1719138, 1271627, 2500710, 1498437, 1301542, 1425966,
                 2505591, 2372919, 2522386, 2369802, 2458818, 2499106, 2441798, 2377819, 2601224, 1752127, 751617,
                 951924, 2639949, 2485107, 2391367, 2385705, 1049864, 2565468, 2575026, 748391, 2573589, 1280316,
                 1587959, 1459957, 1760031, 950146, 935990, 1492311, 2024158, 2730566, 2760634, 2603184, 953112,
                 2392115, 1337762, 1125377, 1237634, 2760072, 2510435, 2560986, 2532402, 2654844, 2390088, 2482749,
                 1163461, 1121447, 2465921, 2517401, 2399423, 1443552, 2206605, 931585, 2411159, 1448549, 2497278,
                 2623860, 2453710, 2380504, 2383828, 2421686, 2437708, 2449976, 2740455, 2531980, 2563893, 2379781,
                 1644443, 1446006, 1462950, 2475843, 2388518, 2658553, 1075330, 2500491, 2149807, 2559428, 1549306,
                 2518915, 2472811, 2583972, 2723649, 1034115, 2398858, 2759645, 2526767, 1147247, 2499369, 2367937,
                 1526328]

    ids = first_ids + second_ids + third_ids

    print('Total influencers ids count: %s' % len(ids))

    infs_qs = Influencer.objects.filter(id__in=ids).select_related('platform')

    print('Total infuencers to revalidate: %s' % infs_qs.count())

    # for the same influencers, run extract_combined(influencer.blog_platform.id).
    # This should help us find any platforms that were missed.

    csvfile = io.open('300_extract_combined__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tName\tBlog_platform.id\tBlog_platform.url\n'
    )
    for inf in queryset_iterator(infs_qs):
        blog_plat = inf.blog_platform
        if isinstance(blog_plat, Platform):
            # extract_combined(blog_plat.id)
            extract_combined.apply_async(
                kwargs={
                    'platform_id': blog_plat.id,
                },
                queue='platform_extraction'
            )

        csvfile.write(u'%s\t%s\t%s\t%s\n' % (
            inf.id,
            inf.name,
            blog_plat.id if isinstance(blog_plat, Platform) else None,
            blog_plat.url if isinstance(blog_plat, Platform) else None,
        ))
    csvfile.close()


def revalidating_top_300_4():
    """

    Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)
    1. Let's pick the top 300 influencers.
        Sort these influencers by follower counts total (from their visible platforms).
        Pick first 100 influencers who in total have at least 10,000 followers.
        Pick the next 100 influencers who in total have at least 50,000 followers
        Pick the next 100 influencers who in total have at least 100,000 followers

    4. Now, for these 300 influencers, put the visible but not autovalidated influencers in a spreadsheet so
        that we can check them.

    :return:
    """

    import io
    from social_discovery.blog_discovery import queryset_iterator
    first_ids = [1460182, 2202976, 2383451, 1252034, 2503701, 2540867, 1134709, 2388780, 1008668, 2394387, 2657060,
                 2371031, 2456535, 2397618, 2403292, 2558931, 2613770, 1121233, 1782302, 2372346, 1038482, 1500491,
                 2474915, 2489342, 2450685, 2550521, 924715, 1639442, 2480119, 1582344, 1275458, 1462288, 2591768,
                 2547239, 2566608, 2575485, 2366328, 2426971, 2649750, 2592192, 2429959, 2758474, 2378972, 2386701,
                 1148655, 2383304, 2714750, 887180, 2396399, 2643801, 2652762, 2002773, 2410945, 2507007,
                 1117915, 908454, 1438606, 2419547, 2471403, 2387034, 1093009, 2382443, 2589779, 2486271, 1529253,
                 1540854, 2442191, 2501510, 876158, 2387630, 2428930, 1509755, 1295956, 2589115, 938954, 2418472,
                 2507201, 2383807, 2716301, 2425840, 2604195, 1833591, 2520127, 2676044, 1006664, 2418245, 2386852,
                 2516891, 2452866, 1789486, 2660195, 2718801, 2395158, 2621470, 2621196, 2367960, 2415863, 1415176,
                 1030029]

    second_ids = [1266993, 2499015, 2210957, 2367663, 2422560, 1980290, 2038491, 2164202, 2326797, 2440257, 2530540,
                  2507468, 2374443, 1027966, 2511689, 2370778, 2381913, 2651692, 1813393, 2367878, 1116571, 1532861,
                  2648639, 2417214, 2452304, 2656035, 2372136, 2477321, 883506, 2538591, 2556956, 1772727, 2409248,
                  2370246, 2446294, 1858606, 2640084, 1078933, 2759197, 2368775, 2458346, 953972, 1910515, 2366086,
                  2388732, 2446789, 2377914, 2381366, 2574992, 2709957, 2374627, 2465053, 2575040, 759161, 950890,
                  2407338, 2401238, 2055840, 2433606, 1521798, 1585669, 2718231, 2524732, 2644755, 2746036, 2394321,
                  985571, 2542119, 2518030, 1588907, 2648117, 2013985, 2530540, 2502931, 973458, 1037173, 2365960,
                  1030663, 2402840, 2569738, 911511, 2383606, 2647909, 2582251, 2373969, 990223, 2367982, 2367684,
                  2644388, 2659310, 1327568, 2517207, 2526341, 2376433, 2416146, 2366377, 2731985, 1831382, 1661028,
                  2742492]

    third_ids = [2505851, 2523871, 2765142, 1788952, 2589386, 1454202, 1282325, 1778192, 1778777, 2728969, 962993,
                 2489163, 2542831, 2421215, 2370100, 2511466, 2495407, 2006221, 2382507, 2428375, 902923, 1070864,
                 1271855, 2471975, 2435554, 1149995, 2381858, 1853680, 2577336, 2492964, 2430903, 1892801, 1043856,
                 2761975, 879519, 1474087, 2373761, 2521099, 1467418, 1448250, 2372725, 2758748, 2481252, 2388415,
                 2498038, 2758255, 1513345, 1525040, 2529665, 2393619, 2472150, 2383826, 2379745, 1259737, 2616412,
                 1171651, 1452403, 2048075, 2432261, 2625800, 2649879, 2391295, 2657660, 2387789, 903821, 2613173,
                 1632738, 1815740, 1669806, 2486543, 2751937, 1902781, 1455773, 1466232, 2016496, 2007819, 2494465,
                 2645478, 2269386, 1749459, 2392996, 1344054, 1024619, 2438863, 2420932, 2414357, 2510729, 2382399,
                 876823, 2394237, 2570362, 2409579, 2391656, 2374632, 2468554, 2380441, 941098, 2711453, 2396450,
                 1140482]

    ids = first_ids + second_ids + third_ids
    print('Total influencers ids count: %s' % len(ids))

    infs_qs = Influencer.objects.filter(id__in=ids).select_related('platform')

    print('Total infuencers to revalidate: %s' % infs_qs.count())

    #  put the visible but not autovalidated influencers in a spreadsheet so that we can check them.
    csvfile = io.open('300_visible_not_autovalidated__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tName\tplatform.id\tplatform_name\tplatform.url\turl_not_found\tautovalidated\n'
    )
    for inf in queryset_iterator(infs_qs):

        plats = inf.platform_set.all()  # .exclude(url_not_found=True).exclude(autovalidated=True)

        for plat in plats:
            csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                inf.id,
                inf.name,
                plat.id,
                plat.platform_name,
                plat.url,
                plat.url_not_found,
                plat.autovalidated,
            ))
    csvfile.close()


def revalidating_top_300_5():
    """

    Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)
    1. Let's pick the top 300 influencers.
        Sort these influencers by follower counts total (from their visible platforms).
        Pick first 100 influencers who in total have at least 10,000 followers.
        Pick the next 100 influencers who in total have at least 50,000 followers
        Pick the next 100 influencers who in total have at least 100,000 followers

    5. For platforms that are new and have no posts, run
        f = fetcher.fetcher_for_platform(platform)
        f.fetch_posts(max_pages=10)
       to fetch new posts.

    :return:
    """

    import io
    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.fetcher import fetcher_for_platform

    first_ids = [1460182, 2202976, 2383451, 1252034, 2503701, 2540867, 1134709, 2388780, 1008668, 2394387, 2657060,
                 2371031, 2456535, 2397618, 2403292, 2558931, 2613770, 1121233, 1782302, 2372346, 1038482, 1500491,
                 2474915, 2489342, 2450685, 2550521, 924715, 1639442, 2480119, 1582344, 1275458, 1462288, 2591768,
                 2547239, 2566608, 2575485, 2366328, 2426971, 2649750, 2592192, 2429959, 2758474, 2378972, 2386701,
                 1148655, 2383304, 2714750, 887180, 2396399, 2643801, 2652762, 2002773, 2410945, 2507007,
                 1117915, 908454, 1438606, 2419547, 2471403, 2387034, 1093009, 2382443, 2589779, 2486271, 1529253,
                 1540854, 2442191, 2501510, 876158, 2387630, 2428930, 1509755, 1295956, 2589115, 938954, 2418472,
                 2507201, 2383807, 2716301, 2425840, 2604195, 1833591, 2520127, 2676044, 1006664, 2418245, 2386852,
                 2516891, 2452866, 1789486, 2660195, 2718801, 2395158, 2621470, 2621196, 2367960, 2415863, 1415176,
                 1030029]

    second_ids = [1266993, 2499015, 2210957, 2367663, 2422560, 1980290, 2038491, 2164202, 2326797, 2440257, 2530540,
                  2507468, 2374443, 1027966, 2511689, 2370778, 2381913, 2651692, 1813393, 2367878, 1116571, 1532861,
                  2648639, 2417214, 2452304, 2656035, 2372136, 2477321, 883506, 2538591, 2556956, 1772727, 2409248,
                  2370246, 2446294, 1858606, 2640084, 1078933, 2759197, 2368775, 2458346, 953972, 1910515, 2366086,
                  2388732, 2446789, 2377914, 2381366, 2574992, 2709957, 2374627, 2465053, 2575040, 759161, 950890,
                  2407338, 2401238, 2055840, 2433606, 1521798, 1585669, 2718231, 2524732, 2644755, 2746036, 2394321,
                  985571, 2542119, 2518030, 1588907, 2648117, 2013985, 2530540, 2502931, 973458, 1037173, 2365960,
                  1030663, 2402840, 2569738, 911511, 2383606, 2647909, 2582251, 2373969, 990223, 2367982, 2367684,
                  2644388, 2659310, 1327568, 2517207, 2526341, 2376433, 2416146, 2366377, 2731985, 1831382, 1661028,
                  2742492]

    third_ids = [2505851, 2523871, 2765142, 1788952, 2589386, 1454202, 1282325, 1778192, 1778777, 2728969, 962993,
                 2489163, 2542831, 2421215, 2370100, 2511466, 2495407, 2006221, 2382507, 2428375, 902923, 1070864,
                 1271855, 2471975, 2435554, 1149995, 2381858, 1853680, 2577336, 2492964, 2430903, 1892801, 1043856,
                 2761975, 879519, 1474087, 2373761, 2521099, 1467418, 1448250, 2372725, 2758748, 2481252, 2388415,
                 2498038, 2758255, 1513345, 1525040, 2529665, 2393619, 2472150, 2383826, 2379745, 1259737, 2616412,
                 1171651, 1452403, 2048075, 2432261, 2625800, 2649879, 2391295, 2657660, 2387789, 903821, 2613173,
                 1632738, 1815740, 1669806, 2486543, 2751937, 1902781, 1455773, 1466232, 2016496, 2007819, 2494465,
                 2645478, 2269386, 1749459, 2392996, 1344054, 1024619, 2438863, 2420932, 2414357, 2510729, 2382399,
                 876823, 2394237, 2570362, 2409579, 2391656, 2374632, 2468554, 2380441, 941098, 2711453, 2396450,
                 1140482]

    ids = first_ids + second_ids + third_ids
    print('Total influencers ids count: %s' % len(ids))

    infs_qs = Influencer.objects.filter(id__in=ids).select_related('platform')

    print('Total infuencers to fetch new posts for new platforms: %s' % infs_qs.count())

    # fetching posts for plaforms without posts
    for inf in queryset_iterator(infs_qs):

        plats = inf.platform_set.exclude(url_not_found=True).exclude(autovalidated=True)
        for plat in plats:
            if plat.posts_set.all().count() == 0:
                f = fetcher_for_platform(plat)
                f.fetch_posts(max_pages=10)

    print ('fetch_posts issued for all new platforms of given influencers')


def revalidating_top_300_6():
    """

    Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)
    1. Let's pick the top 300 influencers.
        Sort these influencers by follower counts total (from their visible platforms).
        Pick first 100 influencers who in total have at least 10,000 followers.
        Pick the next 100 influencers who in total have at least 50,000 followers
        Pick the next 100 influencers who in total have at least 100,000 followers

    6. Then run denormalization on these 250 influencers.

    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator

    first_ids = [1460182, 2202976, 2383451, 1252034, 2503701, 2540867, 1134709, 2388780, 1008668, 2394387, 2657060,
                 2371031, 2456535, 2397618, 2403292, 2558931, 2613770, 1121233, 1782302, 2372346, 1038482, 1500491,
                 2474915, 2489342, 2450685, 2550521, 924715, 1639442, 2480119, 1582344, 1275458, 1462288, 2591768,
                 2547239, 2566608, 2575485, 2366328, 2426971, 2649750, 2592192, 2429959, 2758474, 2378972, 2386701,
                 1148655, 2383304, 2714750, 887180, 2396399, 2643801, 2652762, 2002773, 2410945, 2507007,
                 1117915, 908454, 1438606, 2419547, 2471403, 2387034, 1093009, 2382443, 2589779, 2486271, 1529253,
                 1540854, 2442191, 2501510, 876158, 2387630, 2428930, 1509755, 1295956, 2589115, 938954, 2418472,
                 2507201, 2383807, 2716301, 2425840, 2604195, 1833591, 2520127, 2676044, 1006664, 2418245, 2386852,
                 2516891, 2452866, 1789486, 2660195, 2718801, 2395158, 2621470, 2621196, 2367960, 2415863, 1415176,
                 1030029]

    second_ids = [1266993, 2499015, 2210957, 2367663, 2422560, 1980290, 2038491, 2164202, 2326797, 2440257, 2530540,
                  2507468, 2374443, 1027966, 2511689, 2370778, 2381913, 2651692, 1813393, 2367878, 1116571, 1532861,
                  2648639, 2417214, 2452304, 2656035, 2372136, 2477321, 883506, 2538591, 2556956, 1772727, 2409248,
                  2370246, 2446294, 1858606, 2640084, 1078933, 2759197, 2368775, 2458346, 953972, 1910515, 2366086,
                  2388732, 2446789, 2377914, 2381366, 2574992, 2709957, 2374627, 2465053, 2575040, 759161, 950890,
                  2407338, 2401238, 2055840, 2433606, 1521798, 1585669, 2718231, 2524732, 2644755, 2746036, 2394321,
                  985571, 2542119, 2518030, 1588907, 2648117, 2013985, 2530540, 2502931, 973458, 1037173, 2365960,
                  1030663, 2402840, 2569738, 911511, 2383606, 2647909, 2582251, 2373969, 990223, 2367982, 2367684,
                  2644388, 2659310, 1327568, 2517207, 2526341, 2376433, 2416146, 2366377, 2731985, 1831382, 1661028,
                  2742492]

    third_ids = [2505851, 2523871, 2765142, 1788952, 2589386, 1454202, 1282325, 1778192, 1778777, 2728969, 962993,
                 2489163, 2542831, 2421215, 2370100, 2511466, 2495407, 2006221, 2382507, 2428375, 902923, 1070864,
                 1271855, 2471975, 2435554, 1149995, 2381858, 1853680, 2577336, 2492964, 2430903, 1892801, 1043856,
                 2761975, 879519, 1474087, 2373761, 2521099, 1467418, 1448250, 2372725, 2758748, 2481252, 2388415,
                 2498038, 2758255, 1513345, 1525040, 2529665, 2393619, 2472150, 2383826, 2379745, 1259737, 2616412,
                 1171651, 1452403, 2048075, 2432261, 2625800, 2649879, 2391295, 2657660, 2387789, 903821, 2613173,
                 1632738, 1815740, 1669806, 2486543, 2751937, 1902781, 1455773, 1466232, 2016496, 2007819, 2494465,
                 2645478, 2269386, 1749459, 2392996, 1344054, 1024619, 2438863, 2420932, 2414357, 2510729, 2382399,
                 876823, 2394237, 2570362, 2409579, 2391656, 2374632, 2468554, 2380441, 941098, 2711453, 2396450,
                 1140482]

    ids = first_ids + second_ids + third_ids
    print('Total influencers ids count: %s' % len(ids))

    infs_qs = Influencer.objects.filter(id__in=ids).select_related('platform')

    print('Total infuencers to fetch new posts for new platforms: %s' % infs_qs.count())

    #  running denormalization on each influencer
    for inf in queryset_iterator(infs_qs):

        inf.denormalize_fast()

    print ('fetch_posts issued for all new platforms of given influencers')


def revalidating_top_300_7():
    """

    Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)
    1. Let's pick the top 300 influencers.
        Sort these influencers by follower counts total (from their visible platforms).
        Pick first 100 influencers who in total have at least 10,000 followers.
        Pick the next 100 influencers who in total have at least 50,000 followers
        Pick the next 100 influencers who in total have at least 100,000 followers

    7. Add these influencers to a collection 'testing_300' (you will need to create one) from my account. So that we can check them.

    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator

    first_ids = [1460182, 2202976, 2383451, 1252034, 2503701, 2540867, 1134709, 2388780, 1008668, 2394387, 2657060,
                 2371031, 2456535, 2397618, 2403292, 2558931, 2613770, 1121233, 1782302, 2372346, 1038482, 1500491,
                 2474915, 2489342, 2450685, 2550521, 924715, 1639442, 2480119, 1582344, 1275458, 1462288, 2591768,
                 2547239, 2566608, 2575485, 2366328, 2426971, 2649750, 2592192, 2429959, 2758474, 2378972, 2386701,
                 1148655, 2383304, 2714750, 887180, 2396399, 2643801, 2652762, 2002773, 2410945, 2507007,
                 1117915, 908454, 1438606, 2419547, 2471403, 2387034, 1093009, 2382443, 2589779, 2486271, 1529253,
                 1540854, 2442191, 2501510, 876158, 2387630, 2428930, 1509755, 1295956, 2589115, 938954, 2418472,
                 2507201, 2383807, 2716301, 2425840, 2604195, 1833591, 2520127, 2676044, 1006664, 2418245, 2386852,
                 2516891, 2452866, 1789486, 2660195, 2718801, 2395158, 2621470, 2621196, 2367960, 2415863, 1415176,
                 1030029]

    second_ids = [1266993, 2499015, 2210957, 2367663, 2422560, 1980290, 2038491, 2164202, 2326797, 2440257, 2530540,
                  2507468, 2374443, 1027966, 2511689, 2370778, 2381913, 2651692, 1813393, 2367878, 1116571, 1532861,
                  2648639, 2417214, 2452304, 2656035, 2372136, 2477321, 883506, 2538591, 2556956, 1772727, 2409248,
                  2370246, 2446294, 1858606, 2640084, 1078933, 2759197, 2368775, 2458346, 953972, 1910515, 2366086,
                  2388732, 2446789, 2377914, 2381366, 2574992, 2709957, 2374627, 2465053, 2575040, 759161, 950890,
                  2407338, 2401238, 2055840, 2433606, 1521798, 1585669, 2718231, 2524732, 2644755, 2746036, 2394321,
                  985571, 2542119, 2518030, 1588907, 2648117, 2013985, 2530540, 2502931, 973458, 1037173, 2365960,
                  1030663, 2402840, 2569738, 911511, 2383606, 2647909, 2582251, 2373969, 990223, 2367982, 2367684,
                  2644388, 2659310, 1327568, 2517207, 2526341, 2376433, 2416146, 2366377, 2731985, 1831382, 1661028,
                  2742492]

    third_ids = [2505851, 2523871, 2765142, 1788952, 2589386, 1454202, 1282325, 1778192, 1778777, 2728969, 962993,
                 2489163, 2542831, 2421215, 2370100, 2511466, 2495407, 2006221, 2382507, 2428375, 902923, 1070864,
                 1271855, 2471975, 2435554, 1149995, 2381858, 1853680, 2577336, 2492964, 2430903, 1892801, 1043856,
                 2761975, 879519, 1474087, 2373761, 2521099, 1467418, 1448250, 2372725, 2758748, 2481252, 2388415,
                 2498038, 2758255, 1513345, 1525040, 2529665, 2393619, 2472150, 2383826, 2379745, 1259737, 2616412,
                 1171651, 1452403, 2048075, 2432261, 2625800, 2649879, 2391295, 2657660, 2387789, 903821, 2613173,
                 1632738, 1815740, 1669806, 2486543, 2751937, 1902781, 1455773, 1466232, 2016496, 2007819, 2494465,
                 2645478, 2269386, 1749459, 2392996, 1344054, 1024619, 2438863, 2420932, 2414357, 2510729, 2382399,
                 876823, 2394237, 2570362, 2409579, 2391656, 2374632, 2468554, 2380441, 941098, 2711453, 2396450,
                 1140482]

    ids = first_ids + second_ids + third_ids
    print('Total influencers ids count: %s' % len(ids))

    infs_qs = Influencer.objects.filter(id__in=ids).select_related('platform')

    print('Total infuencers to fetch new posts for new platforms: %s' % infs_qs.count())

    # adding influencers to collection
    coll_qs = InfluencersGroup.objects.filter(name='testing_300')
    if coll_qs.count() > 0:
        coll = coll_qs[0]
        for inf in queryset_iterator(infs_qs):
            coll.add_influencer(inf)
    else:
        print('Collection was not created')

    print ('Influencer adding finished')


def revalidating_top_300_the_rest():
    """

    Influencer.objects.filter(validated_on__contains='info').exclude(old_show_on_search=True).exclude(blacklisted=True)
    1. Let's pick the top 300 influencers.
        Sort these influencers by follower counts total (from their visible platforms).
        Pick first 100 influencers who in total have at least 10,000 followers.
        Pick the next 100 influencers who in total have at least 50,000 followers
        Pick the next 100 influencers who in total have at least 100,000 followers

    3. Next, for the same influencers, run extract_combined(influencer.blog_platform.id).
        This should help us find any platforms that were missed.

    4. Now, for these 300 influencers, put the visible but not autovalidated influencers in a spreadsheet so
        that we can check them.

    :return:
    """

    import io
    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.platformextractor import extract_combined

    rest_ids = [1460182, 2202976, 1252034, 1500491, 2474915, 2489342, 1639442, 1275458, 1462288, 2591768, 2366328,
                2429959, 2442191, 2501510, 876158, 2418472, 2383807, 1833591, 2676044, 2516891, 2452866, 2718801,
                2395158, 2621470, 2621196, 2367960, 2415863, 1030029, 2499015, 2210957, 1980290, 2038491, 2164202,
                2530540, 2507468, 2511689, 1813393, 1116571, 2648639, 2417214, 2452304, 2372136, 1772727, 2640084,
                2458346, 953972, 2465053, 950890, 2055840, 1521798, 2718231, 2530540, 911511, 2367982, 1327568, 2517207,
                2416146, 1831382, 2505851, 2589386, 962993, 2489163, 2542831, 1271855, 2435554, 1892801, 879519,
                1474087, 1467418, 1513345, 2383826, 2379745, 1259737, 2048075, 2391295, 2751937, 1902781, 2016496,
                2494465, 2570362, 2391656, 2374632, 2380441, 2396450, 1140482]

    print('Total influencers ids count: %s' % len(rest_ids))

    infs_qs = Influencer.objects.filter(id__in=rest_ids).select_related('platform')

    print('Total infuencers to revalidate: %s' % infs_qs.count())

    # for the same influencers, run extract_combined(influencer.blog_platform.id).
    # This should help us find any platforms that were missed.

    csvfile = io.open('300_extract_combined_rest__%s.csv' % datetime.datetime.strftime(
                datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tName\tBlog_platform.id\tBlog_platform.url\n'
    )
    for inf in queryset_iterator(infs_qs):
        if inf.blog_url is None:
            csvfile.write(u'%s\t%s\t%s\t%s\n' % (
                inf.id,
                inf.name,
                'blog_url=None',
                'blog_url=None',
            ))
        else:
            blog_plats = inf.platform_set.filter(url__icontains=inf.blog_url.lower())
            if blog_plats.count() > 0:
                # extract_combined(blog_plat.id)
                extract_combined.apply_async(
                    kwargs={
                        'platform_id': blog_plats[0].id,
                    },
                    queue='platform_extraction'
                )

            csvfile.write(u'%s\t%s\t%s\t%s\n' % (
                inf.id,
                inf.name,
                blog_plats[0].id if blog_plats.count() > 0 else None,
                blog_plats[0].url if blog_plats.count() > 0 else None,
            ))
    csvfile.close()


def reset_300_socials():
    """
    This script resets all platforms of influencers except their blog_platforms
    to url_not_found=True, autovalidated=False
    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator

    ids = [759161, 876823, 883506, 887180, 902923, 903821, 908454, 924715, 938954, 941098, 973458, 985571, 990223,
           1006664, 1008668, 1024619, 1027966, 1030663, 1037173, 1038482, 1043856, 1070864, 1078933, 1093009, 1117915,
           1121233, 1134709, 1148655, 1149995, 1171651, 1266993, 1282325, 1295956, 1344054, 1415176, 1438606,
           1448250, 1452403, 1454202, 1455773, 1466232, 1509755, 1525040, 1529253, 1532861, 1540854, 1582344, 1585669,
           1588907, 1632738, 1661028, 1669806, 1749459, 1778192, 1778777, 1782302, 1788952, 1789486, 1815740, 1853680,
           1858606, 1910515, 2002773, 2006221, 2007819, 2013985, 2269386, 2326797, 2365960, 2366086, 2366377, 2367663,
           2367684, 2367878, 2368775, 2370100, 2370246, 2370778, 2371031, 2372346, 2372725, 2373761, 2373969, 2374443,
           2374627, 2376433, 2377914, 2378972, 2381366, 2381858, 2381913, 2382399, 2382443, 2382507, 2383304, 2383451,
           2383606, 2386701, 2386852, 2387034, 2387630, 2387789, 2388415, 2388732, 2388780, 2392996, 2393619, 2394237,
           2394321, 2394387, 2396399, 2397618, 2401238, 2402840, 2403292, 2407338, 2409248, 2409579, 2410945, 2414357,
           2418245, 2419547, 2420932, 2421215, 2422560, 2425840, 2426971, 2428375, 2428930, 2430903, 2432261, 2433606,
           2438863, 2440257, 2446294, 2446789, 2450685, 2456535, 2468554, 2471403, 2471975, 2472150, 2477321, 2480119,
           2481252, 2486271, 2486543, 2492964, 2495407, 2498038, 2502931, 2503701, 2507007, 2507201, 2510729, 2511466,
           2518030, 2520127, 2521099, 2523871, 2524732, 2526341, 2529665, 2538591, 2540867, 2542119, 2547239, 2550521,
           2556956, 2558931, 2566608, 2569738, 2574992, 2575040, 2575485, 2577336, 2582251, 2589115, 2589779, 2592192,
           2604195, 2613173, 2613770, 2616412, 2625800, 2643801, 2644388, 2644755, 2645478, 2647909, 2648117, 2649750,
           2649879, 2651692, 2652762, 2656035, 2657060, 2657660, 2659310, 2660195, 2709957, 2711453, 2714750, 2716301,
           2728969, 2731985, 2742492, 2746036, 2758255, 2758474, 2758748, 2759197, 2761975, 2765142,
           1460182, 2202976, 1252034, 1500491, 2474915, 2489342, 1639442, 1275458, 1462288, 2591768, 2366328,
           2429959, 2442191, 2501510, 876158, 2418472, 2383807, 1833591, 2676044, 2516891, 2452866, 2718801,
           2395158, 2621470, 2621196, 2367960, 2415863, 1030029, 2499015, 2210957, 1980290, 2038491, 2164202,
           2530540, 2507468, 2511689, 1813393, 1116571, 2648639, 2417214, 2452304, 2372136, 1772727, 2640084,
           2458346, 953972, 2465053, 950890, 2055840, 1521798, 2718231, 2530540, 911511, 2367982, 1327568, 2517207,
           2416146, 1831382, 2505851, 2589386, 962993, 2489163, 2542831, 1271855, 2435554, 1892801, 879519,
           1474087, 1467418, 1513345, 2383826, 2379745, 1259737, 2048075, 2391295, 2751937, 1902781, 2016496,
           2494465, 2570362, 2391656, 2374632, 2380441, 2396450, 1140482]

    # SECOND 300 guys
    first_ids = [2375228, 2385748, 2228136, 2414770, 2366428, 2391897, 1051857, 1674582, 2518791, 2414727, 2562363,
                 1586093, 2504499, 1464099, 2401008, 2516867, 2416584, 2368158, 1593841, 1135493, 1112713, 1381689,
                 2313549, 2434703, 2696342, 2412674, 1079867, 1813639, 1830570, 2688269, 2157125, 2372017, 2579060,
                 1406933, 2652123, 2436151, 2411931, 2397500, 2517942, 2486595, 2766696, 2418846, 2370873, 2651596,
                 2683248, 2753685, 2566731, 2618815, 1125775, 1714945, 2352085, 2399116, 2641224, 888841, 2372379,
                 2542421, 2574452, 1097598, 2507088, 2739558, 2753790, 2237504, 2391653, 2394834, 1060386, 2511627,
                 1811565, 962206, 1201286, 2396258, 2460874, 2499259, 2470390, 1359521, 2365811, 2430684, 2548580,
                 2414006, 2453353, 2658432, 2660531, 2480754, 2661220, 1381084, 1812472, 2374470, 2447407, 2752492,
                 1387224, 1204237, 2445155, 2645532, 1392033, 1257673, 1296464, 2435887, 2372609, 2479851, 2496038,
                 2649706]
    second_ids = [1463193, 2426630, 1361215, 922821, 2366332, 1407480, 2397256, 2388367, 1773259, 2368425, 1416251,
                  2452784, 2440214, 2452575, 760595, 956008, 2723525, 2485269, 2732480, 1780914, 1761138, 2672389,
                  2109996, 1138126, 1807249, 2275097, 2371360, 2560150, 2622552, 2753765, 2425671, 2417535, 2661458,
                  2469510, 2425827, 2393042, 2051835, 2652912, 2366273, 2383337, 2381868, 2419764, 1572804, 2377219,
                  2397820, 2383003, 2457122, 2551073, 1862577, 1998771, 2426728, 2430631, 2448345, 2759483, 2605755,
                  2387915, 1508073, 2515562, 2752889, 1210595, 2404956, 2509527, 908383, 2595585, 2383556, 2488126,
                  1093715, 2529790, 1052870, 1078042, 2418613, 2378016, 2380824, 2387605, 2610264, 2294460, 2474571,
                  1368847, 2605293, 1449368, 2476524, 1767612, 2398496, 2453648, 2738761, 2433034, 1604979, 1608328,
                  2464514, 2761073, 2368660, 2454408, 1783335, 1238051, 2384689, 1150856, 2379155, 2520115, 2659066,
                  2627125]
    third_ids = [875640, 1069124, 1391254, 1296388, 1895956, 1719138, 1271627, 2500710, 1498437, 1301542, 1425966,
                 2505591, 2372919, 2522386, 2369802, 2458818, 2499106, 2441798, 2377819, 2601224, 1752127, 751617,
                 951924, 2639949, 2485107, 2391367, 2385705, 1049864, 2565468, 2575026, 748391, 2573589, 1280316,
                 1587959, 1459957, 1760031, 950146, 935990, 1492311, 2024158, 2730566, 2760634, 2603184, 953112,
                 2392115, 1337762, 1125377, 1237634, 2760072, 2510435, 2560986, 2532402, 2654844, 2390088, 2482749,
                 1163461, 1121447, 2465921, 2517401, 2399423, 1443552, 2206605, 931585, 2411159, 1448549, 2497278,
                 2623860, 2453710, 2380504, 2383828, 2421686, 2437708, 2449976, 2740455, 2531980, 2563893, 2379781,
                 1644443, 1446006, 1462950, 2475843, 2388518, 2658553, 1075330, 2500491, 2149807, 2559428, 1549306,
                 2518915, 2472811, 2583972, 2723649, 1034115, 2398858, 2759645, 2526767, 1147247, 2499369, 2367937,
                 1526328]

    ids = first_ids + second_ids + third_ids

    print('Total influencers ids count: %s' % len(ids))

    infs_qs = Influencer.objects.filter(id__in=ids).select_related('platform')

    print('Total infuencers to reset: %s' % infs_qs.count())

    for inf in queryset_iterator(infs_qs):
        blog_platform = inf.blog_platform
        if blog_platform is not None:

            # TODO: pay attention to this in future
            if blog_platform.url_not_found is not False:
                blog_platform.url_not_found = False
                blog_platform.autovalidated = True
                blog_platform.save()

            inf.platform_set.filter(platform_name__in=Platform.SOCIAL_PLATFORMS).exclude(id=blog_platform.id).update(autovalidated=False, autovalidated_reason=None, url_not_found=True)
        else:
            blog_url = inf.blog_url
            if blog_url is None:
                print('blog_url=None for influencer: %s' % inf.id)
                inf.platform_set.update(autovalidated=False, autovalidated_reason=None, url_not_found=True)
            else:
                blog_platform = inf.platform_set.filter(url__icontains=inf.blog_url.lower())
                if blog_platform.count() > 0:
                    bp = blog_platform[0]

                    # TODO: pay attention to this in future
                    if bp.url_not_found is not False:
                        bp.url_not_found = False
                        bp.autovalidated = True
                        bp.save()

                    inf.platform_set.filter(platform_name__in=Platform.SOCIAL_PLATFORMS).exclude(id=bp.id).update(autovalidated=False, autovalidated_reason=None, url_not_found=True)
                else:
                    inf.platform_set.filter(platform_name__in=Platform.SOCIAL_PLATFORMS).update(autovalidated=False, autovalidated_reason=None, url_not_found=True)
                    print('influencer %s has no blog platform for %s' % (inf.id, inf.blog_url.lower()))


def get_influencers_without_social():
    """
    Getting csv of influencers without any autovalidated social platform (Facebook, or Pinterst, or
    Twitter, or Instagram, or Youtube)
    :return:
    """
    import io
    from social_discovery.blog_discovery import queryset_iterator

    # good ids
    inf_ids = [759161, 876823, 883506, 887180, 902923, 903821, 908454, 924715, 938954, 941098, 973458, 985571, 990223,
               1006664, 1008668, 1024619, 1027966, 1030663, 1037173, 1038482, 1043856, 1070864, 1078933, 1093009,
               1117915, 1121233, 1134709, 1148655, 1149995, 1171651, 1266993, 1282325, 1295956, 1344054,
               1415176, 1438606, 1448250, 1452403, 1454202, 1455773, 1466232, 1509755, 1525040, 1529253, 1532861,
               1540854, 1582344, 1585669, 1588907, 1632738, 1661028, 1669806, 1749459, 1778192, 1778777, 1782302,
               1788952, 1789486, 1815740, 1853680, 1858606, 1910515, 2002773, 2006221, 2007819, 2013985, 2269386,
               2326797, 2365960, 2366086, 2366377, 2367663, 2367684, 2367878, 2368775, 2370100, 2370246, 2370778,
               2371031, 2372346, 2372725, 2373761, 2373969, 2374443, 2374627, 2376433, 2377914, 2378972, 2381366,
               2381858, 2381913, 2382399, 2382443, 2382507, 2383304, 2383451, 2383606, 2386701, 2386852, 2387034,
               2387630, 2387789, 2388415, 2388732, 2388780, 2392996, 2393619, 2394237, 2394321, 2394387, 2396399,
               2397618, 2401238, 2402840, 2403292, 2407338, 2409248, 2409579, 2410945, 2414357, 2418245, 2419547,
               2420932, 2421215, 2422560, 2425840, 2426971, 2428375, 2428930, 2430903, 2432261, 2433606, 2438863,
               2440257, 2446294, 2446789, 2450685, 2456535, 2468554, 2471403, 2471975, 2472150, 2477321, 2480119,
               2481252, 2486271, 2486543, 2492964, 2495407, 2498038, 2502931, 2503701, 2507007, 2507201, 2510729,
               2511466, 2518030, 2520127, 2521099, 2523871, 2524732, 2526341, 2529665, 2538591, 2540867, 2542119,
               2547239, 2550521, 2556956, 2558931, 2566608, 2569738, 2574992, 2575040, 2575485, 2577336, 2582251,
               2589115, 2589779, 2592192, 2604195, 2613173, 2613770, 2616412, 2625800, 2643801, 2644388, 2644755,
               2645478, 2647909, 2648117, 2649750, 2649879, 2651692, 2652762, 2656035, 2657060, 2657660, 2659310,
               2660195, 2709957, 2711453, 2714750, 2716301, 2728969, 2731985, 2742492, 2746036, 2758255, 2758474,
               2758748, 2759197, 2761975, 2765142]

    # SECOND 300 guys
    first_ids = [2375228, 2385748, 2228136, 2414770, 2366428, 2391897, 1051857, 1674582, 2518791, 2414727, 2562363,
                 1586093, 2504499, 1464099, 2401008, 2516867, 2416584, 2368158, 1593841, 1135493, 1112713, 1381689,
                 2313549, 2434703, 2696342, 2412674, 1079867, 1813639, 1830570, 2688269, 2157125, 2372017, 2579060,
                 1406933, 2652123, 2436151, 2411931, 2397500, 2517942, 2486595, 2766696, 2418846, 2370873, 2651596,
                 2683248, 2753685, 2566731, 2618815, 1125775, 1714945, 2352085, 2399116, 2641224, 888841, 2372379,
                 2542421, 2574452, 1097598, 2507088, 2739558, 2753790, 2237504, 2391653, 2394834, 1060386, 2511627,
                 1811565, 962206, 1201286, 2396258, 2460874, 2499259, 2470390, 1359521, 2365811, 2430684, 2548580,
                 2414006, 2453353, 2658432, 2660531, 2480754, 2661220, 1381084, 1812472, 2374470, 2447407, 2752492,
                 1387224, 1204237, 2445155, 2645532, 1392033, 1257673, 1296464, 2435887, 2372609, 2479851, 2496038,
                 2649706]
    second_ids = [1463193, 2426630, 1361215, 922821, 2366332, 1407480, 2397256, 2388367, 1773259, 2368425, 1416251,
                  2452784, 2440214, 2452575, 760595, 956008, 2723525, 2485269, 2732480, 1780914, 1761138, 2672389,
                  2109996, 1138126, 1807249, 2275097, 2371360, 2560150, 2622552, 2753765, 2425671, 2417535, 2661458,
                  2469510, 2425827, 2393042, 2051835, 2652912, 2366273, 2383337, 2381868, 2419764, 1572804, 2377219,
                  2397820, 2383003, 2457122, 2551073, 1862577, 1998771, 2426728, 2430631, 2448345, 2759483, 2605755,
                  2387915, 1508073, 2515562, 2752889, 1210595, 2404956, 2509527, 908383, 2595585, 2383556, 2488126,
                  1093715, 2529790, 1052870, 1078042, 2418613, 2378016, 2380824, 2387605, 2610264, 2294460, 2474571,
                  1368847, 2605293, 1449368, 2476524, 1767612, 2398496, 2453648, 2738761, 2433034, 1604979, 1608328,
                  2464514, 2761073, 2368660, 2454408, 1783335, 1238051, 2384689, 1150856, 2379155, 2520115, 2659066,
                  2627125]
    third_ids = [875640, 1069124, 1391254, 1296388, 1895956, 1719138, 1271627, 2500710, 1498437, 1301542, 1425966,
                 2505591, 2372919, 2522386, 2369802, 2458818, 2499106, 2441798, 2377819, 2601224, 1752127, 751617,
                 951924, 2639949, 2485107, 2391367, 2385705, 1049864, 2565468, 2575026, 748391, 2573589, 1280316,
                 1587959, 1459957, 1760031, 950146, 935990, 1492311, 2024158, 2730566, 2760634, 2603184, 953112,
                 2392115, 1337762, 1125377, 1237634, 2760072, 2510435, 2560986, 2532402, 2654844, 2390088, 2482749,
                 1163461, 1121447, 2465921, 2517401, 2399423, 1443552, 2206605, 931585, 2411159, 1448549, 2497278,
                 2623860, 2453710, 2380504, 2383828, 2421686, 2437708, 2449976, 2740455, 2531980, 2563893, 2379781,
                 1644443, 1446006, 1462950, 2475843, 2388518, 2658553, 1075330, 2500491, 2149807, 2559428, 1549306,
                 2518915, 2472811, 2583972, 2723649, 1034115, 2398858, 2759645, 2526767, 1147247, 2499369, 2367937,
                 1526328]

    inf_ids = first_ids + second_ids + third_ids

    inf_ids = ids = [47603, 47632, 47723, 47753, 47762, 47932, 47988, 324547, 324767, 325135, 749881, 750856, 751237, 751365, 751939, 752491, 752493, 753039, 754694, 755552, 756270, 756419, 756757, 758327,]

    infs = Influencer.objects.filter(id__in=inf_ids).select_related('platform')

    social_platforms = ['Facebook', 'Twitter', 'Instagram', 'Youtube', 'Pinterst',]

    csvfile = io.open('without_autovalidated_socials__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tName\tBlog_platform.id\tBlog_platform.url\tFacebook\tTwitter\tInstagram\tYoutube\tPinterest\n'
    )

    for inf in queryset_iterator(infs):

        if any([inf.platform_set.filter(platform_name=plat, autovalidated=True).count() == 0 for plat in social_platforms]):
            csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                inf.id,
                inf.name,
                'None' if inf.blog_platform is None else inf.blog_platform.id,
                'None' if inf.blog_platform is None else inf.blog_platform.url,
                "%s/%s" %(
                    'yes' if inf.platform_set.filter(platform_name='Facebook').exclude(url_not_found=True).count() > 0 else 'NO',
                    'yes' if inf.platform_set.filter(platform_name='Facebook', autovalidated=True).count() > 0 else 'NO',
                ),
                "%s/%s" %(
                    'yes' if inf.platform_set.filter(platform_name='Twitter').exclude(url_not_found=True).count() > 0 else 'NO',
                    'yes' if inf.platform_set.filter(platform_name='Twitter', autovalidated=True).count() > 0 else 'NO',
                ),
                "%s/%s" %(
                    'yes' if inf.platform_set.filter(platform_name='Instagram').exclude(url_not_found=True).count() > 0 else 'NO',
                    'yes' if inf.platform_set.filter(platform_name='Instagram', autovalidated=True).count() > 0 else 'NO',
                ),
                "%s/%s" %(
                    'yes' if inf.platform_set.filter(platform_name='Youtube').exclude(url_not_found=True).count() > 0 else 'NO',
                    'yes' if inf.platform_set.filter(platform_name='Youtube', autovalidated=True).count() > 0 else 'NO',
                ),
                "%s/%s" %(
                    'yes' if inf.platform_set.filter(platform_name='Pinterest').exclude(url_not_found=True).count() > 0 else 'NO',
                    'yes' if inf.platform_set.filter(platform_name='Pinterest', autovalidated=True).count() > 0 else 'NO',
                ),
            ))

    csvfile.close()


def poll_hanes_campaign(interval=30):
    from debra.account_helpers import send_msg_to_slack
    while True:
        job = BrandJobPost.objects.get(id=355)
        if job.post_collection_id is None:
            send_msg_to_slack('front-end', 'ALARM! Hanes campaign is broken')
            print "{} - ERROR!".format(datetime.datetime.now())
        else:
            print "{} - OK".format(datetime.datetime.now())
        time.sleep(interval)


def platform_duplicates_posts_count(skip_empty_non_validated_platforms=False):
    """
    Creates a csv file with platforms distributions
    :return:
    """
    import io
    from social_discovery.blog_discovery import queryset_iterator

    # good ids
    inf_ids = [759161, 876823, 883506, 887180, 902923, 903821, 908454, 924715, 938954, 941098, 973458, 985571, 990223,
               1006664, 1008668, 1024619, 1027966, 1030663, 1037173, 1038482, 1043856, 1070864, 1078933, 1093009,
               1117915, 1121233, 1134709, 1148655, 1149995, 1171651, 1266993, 1282325, 1295956, 1344054,
               1415176, 1438606, 1448250, 1452403, 1454202, 1455773, 1466232, 1509755, 1525040, 1529253, 1532861,
               1540854, 1582344, 1585669, 1588907, 1632738, 1661028, 1669806, 1749459, 1778192, 1778777, 1782302,
               1788952, 1789486, 1815740, 1853680, 1858606, 1910515, 2002773, 2006221, 2007819, 2013985, 2269386,
               2326797, 2365960, 2366086, 2366377, 2367663, 2367684, 2367878, 2368775, 2370100, 2370246, 2370778,
               2371031, 2372346, 2372725, 2373761, 2373969, 2374443, 2374627, 2376433, 2377914, 2378972, 2381366,
               2381858, 2381913, 2382399, 2382443, 2382507, 2383304, 2383451, 2383606, 2386701, 2386852, 2387034,
               2387630, 2387789, 2388415, 2388732, 2388780, 2392996, 2393619, 2394237, 2394321, 2394387, 2396399,
               2397618, 2401238, 2402840, 2403292, 2407338, 2409248, 2409579, 2410945, 2414357, 2418245, 2419547,
               2420932, 2421215, 2422560, 2425840, 2426971, 2428375, 2428930, 2430903, 2432261, 2433606, 2438863,
               2440257, 2446294, 2446789, 2450685, 2456535, 2468554, 2471403, 2471975, 2472150, 2477321, 2480119,
               2481252, 2486271, 2486543, 2492964, 2495407, 2498038, 2502931, 2503701, 2507007, 2507201, 2510729,
               2511466, 2518030, 2520127, 2521099, 2523871, 2524732, 2526341, 2529665, 2538591, 2540867, 2542119,
               2547239, 2550521, 2556956, 2558931, 2566608, 2569738, 2574992, 2575040, 2575485, 2577336, 2582251,
               2589115, 2589779, 2592192, 2604195, 2613173, 2613770, 2616412, 2625800, 2643801, 2644388, 2644755,
               2645478, 2647909, 2648117, 2649750, 2649879, 2651692, 2652762, 2656035, 2657060, 2657660, 2659310,
               2660195, 2709957, 2711453, 2714750, 2716301, 2728969, 2731985, 2742492, 2746036, 2758255, 2758474,
               2758748, 2759197, 2761975, 2765142]

    infs = Influencer.objects.filter(id__in=inf_ids).select_related('platform')

    csvfile = io.open('platform_duplicates_posts_count__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer_id\tName\tBlog_platform.id\tBlog_platform.url\tPlatform.id'
        u'\tPlatform.name\tPlatform.url\turl_not_found\tAutovalidated\tPosts.count\n'
    )

    for inf in queryset_iterator(infs):

        plats = inf.platform_set.all().order_by('platform_name', 'autovalidated', 'id')

        for plat in plats:
            posts_count = plat.posts_set.all().count()
            if skip_empty_non_validated_platforms and posts_count == 0:
                continue

            csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                inf.id,
                inf.name,
                'None' if inf.blog_platform is None else inf.blog_platform.id,
                'None' if inf.blog_platform is None else inf.blog_platform.url,
                plat.id,
                plat.platform_name,
                plat.url,
                plat.url_not_found,
                plat.autovalidated,
                posts_count
            ))

    csvfile.close()


def capitalize_brand_names():
    """
    capitalizes names of all brands
    :return:
    """
    from social_discovery.blog_discovery import queryset_iterator

    brands = Brands.objects.all()

    ctr_total = 0
    ctr_uppered = 0

    for brand in queryset_iterator(brands):
        if brand.name is not None:
            brand.name = brand.name.upper()
            brand.save()
            ctr_uppered += 1

        ctr_total += 1

    print('Uppercased %s brands of %s total' % (ctr_uppered, ctr_total))


def issue_tasks_men_bloggers():
    """
    Script to reissue tasks for platform discovery of Men bloggers.
    Reissuing only those who has valid blog_platform
    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.platformextractor import extract_combined

    infs = Influencer.objects.filter(
        show_on_search=True
    ).filter(
        demographics_gender__icontains='m'
    ).exclude(
        demographics_gender='Female'
    ).exclude(
        demographics_gender='PROBLEM ID'
    ).exclude(
        blacklisted=True
    ).exclude(
        old_show_on_search=True
    ).order_by('id')

    ctr_total = 0
    ctr_reissued = 0

    for inf in queryset_iterator(infs):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        # check that it is a Platform
        if isinstance(blog_plat, Platform) and \
                blog_plat.platformdataop_set.filter(operation='extract_platforms_from_platform',
                                                    started__gte=datetime.date(2016, 2, 9)).count() == 0:
            # setting it visible and autovalidated
            blog_plat.autovalidated = True
            blog_plat.url_not_found = False
            blog_plat.save()

            # resetting all its socials to invisible-non-autovalidated
            inf.platform_set.filter(
                platform_name__in=Platform.SOCIAL_PLATFORMS
            ).exclude(
                id=blog_plat.id
            ).update(autovalidated=False, autovalidated_reason=None, url_not_found=True)

            # issuing a task to re-perform the platform
            extract_combined.apply_async(
                kwargs={
                    'platform_id': blog_plat.id,
                },
                queue='platform_extraction'
            )

            ctr_reissued += 1

        ctr_total += 1
    print('Reissued %s influencers of %s total' % (ctr_reissued, ctr_total))


def classify_bloggers(ids=None):

    from social_discovery.blog_discovery import queryset_iterator
    from social_discovery.classifiers import KeywordClassifier

    if ids is not None:
        infs = Influencer.objects.filter(id__in=ids)
    else:
        infs = Influencer.objects.filter(
            show_on_search=True
        ).filter(
            demographics_gender__icontains='m'
        ).exclude(
            demographics_gender='Female'
        ).exclude(
            demographics_gender='PROBLEM ID'
        ).exclude(
            blacklisted=True
        ).exclude(
            old_show_on_search=True
        ).order_by('id')[:200]

    classifier = KeywordClassifier()

    summary_results = {}

    for inf in infs:  # queryset_iterator(infs):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        results = []

        social_platforms = inf.platform_set.filter(autovalidated=True).exclude(url_not_found=True).filter(platform_name__in=Platform.SOCIAL_PLATFORMS)

        # if it's a blogspot or if it has an autovalidated bloglovin, then it should be a blog
        if (isinstance(blog_plat, Platform) and '.blogspot.' in blog_plat.url) or social_platforms.filter(platform_name='Bloglovin').count() > 0:
            print('has blogspot blog_platform or has an autovalidated Bloglovin' % results)
            summary_results[inf.id] = 'blogger'

        else:
            for platform in social_platforms:
                result = classifier.classify_unit(platform.description)
                print('    platform: %s url: %s is considered to be: %s' % (platform.id, platform.url, result.upper()))
                results.append(result)

            if 'blogger' in results:
                summary_results[inf.id] = 'blogger'
            elif 'brand' in results:
                summary_results[inf.id] = 'brand'
            else:
                summary_results[inf.id] = 'undecided'

        print('results: %s' % results)
        print('INFLUENCER id: %s url: %s considered as: %s' % (inf.id, blog_plat.url if isinstance(blog_plat, Platform) else blog_plat, summary_results[inf.id].upper()))
        print('* * * * * * * * * *')

    print('Final results:')
    print(summary_results)
    return summary_results

def count_men_bloggers_performed():
    """
    Script to count performed Men bloggers.
    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator

    infs = Influencer.objects.filter(
        show_on_search=True
    ).filter(
        demographics_gender__icontains='m'
    ).exclude(
        demographics_gender='Female'
    ).exclude(
        demographics_gender='PROBLEM ID'
    ).exclude(
        blacklisted=True
    ).exclude(
        old_show_on_search=True
    ).order_by('id')

    ctr_total = 0
    ctr_performed = 0

    for inf in queryset_iterator(infs):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        # check that it is a Platform
        if isinstance(blog_plat, Platform) and \
                blog_plat.platformdataop_set.filter(operation='extract_platforms_from_platform',
                                                    started__gte=datetime.date(2016, 2, 9)).count() > 0:

            ctr_performed += 1

        ctr_total += 1

        if ctr_total % 100 == 0:
            print('Checked so far: %s, performed: %s' % (ctr_total, ctr_performed))

    print('Already performed %s influencers of %s total' % (ctr_performed, ctr_total))


def classify_performed_bloggers(ids=None):

    limit_so_far = 5500

    from social_discovery.blog_discovery import queryset_iterator
    from social_discovery.classifiers import KeywordClassifier

    if ids is not None:
        infs = Influencer.objects.filter(id__in=ids)
    else:
        infs = Influencer.objects.filter(
            show_on_search=True
        ).filter(
            demographics_gender__icontains='m'
        ).exclude(
            demographics_gender='Female'
        ).exclude(
            demographics_gender='PROBLEM ID'
        ).exclude(
            blacklisted=True
        ).exclude(
            old_show_on_search=True
        ).order_by('id')

    classifier = KeywordClassifier()

    summary_results = {}

    classified_ctr = 0

    for inf in queryset_iterator(infs):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        results = []

        if isinstance(blog_plat, Platform):

            social_platforms = inf.platform_set.filter(autovalidated=True).exclude(url_not_found=True).filter(platform_name__in=Platform.SOCIAL_PLATFORMS)

            # if it's a blogspot or if it has an autovalidated bloglovin, then it should be a blog
            if (isinstance(blog_plat, Platform) and '.blogspot.' in blog_plat.url) or social_platforms.filter(platform_name='Bloglovin').count() > 0:
                print('has blogspot blog_platform or has an autovalidated Bloglovin' % results)
                summary_results[inf.id] = 'blogger'

            else:
                for platform in social_platforms:
                    result = classifier.classify_unit(platform.description)
                    # print('    platform: %s url: %s is considered to be: %s' % (platform.id, platform.url, result.upper()))
                    results.append(result)

                if 'blogger' in results:
                    summary_results[inf.id] = 'blogger'
                elif 'brand' in results:
                    summary_results[inf.id] = 'brand'
                else:
                    summary_results[inf.id] = 'undecided'

            if inf.classification is None:
                inf.classification = summary_results[inf.id]
            else:
                inf.classification = ' '.join([inf.classification, summary_results[inf.id]])
            inf.save()

            classified_ctr += 1

            if classified_ctr >= limit_so_far:
                break

            # print('results: %s' % results)
            print('%s INFLUENCER id: %s url: %s considered as: %s' % (classified_ctr,
                                                                      inf.id,
                                                                      blog_plat.url if isinstance(blog_plat, Platform) else blog_plat,
                                                                      summary_results[inf.id].upper()))
            # print('* * * * * * * * * *')

    print('Final results:')
    print(summary_results)
    return summary_results



def men_bloggers_fetch_and_profile(platform_name=None):
    """
     run fetcher.fetcher_for_platform(platform) for each of these influencers and their autovalidated platforms
     then for each one of these influencers run influencer.set_profile_pic() so that their
     profile is obtained from the autovalidated
    :return:
    """
    if platform_name is None:
        return

    from platformdatafetcher import fetcher
    bloggers_col = InfluencersGroup.objects.get(name='alpha-men-bloggers')

    inf_ctr = 0
    plat_ctr = 0

    # for all of 'bloggers' group
    for blogger in bloggers_col.influencers:

        # fetching all platforms of a type
        platforms = blogger.platform_set.filter(autovalidated=True, platform_name=platform_name, validated_handle__isnull=True)

        for platform in platforms:
            # if platform has no validated handle - calling fetcher_for_platform
            try:
                fetcher.fetcher_for_platform(platform)
            except:
                pass

            plat_ctr += 1
        inf_ctr += 1

        print('*** %s influencers, %s platforms PERFORMED' % (inf_ctr, plat_ctr))


    # # for all of the bloggers we fetch profile pic
    # for blogger in bloggers_col.influencers:
    #     blogger.set_profile_pic()
    #     ctr += 1
    #
    #     if ctr % 100 == 0:
    #         print('set_profile_pic called for %s influencers' % ctr)

    print('DONE')


def men_bloggers_fetch_posts():
    """

    :return:
    """

    from platformdatafetcher.fetchertasks import fetch_platform_data
    bloggers_col = InfluencersGroup.objects.get(name='alpha-men-bloggers')

    ctr = 0
    plat_applied = 0

    # for all of 'bloggers' group
    for blogger in bloggers_col.influencers:

        # fetching all platforms of a type
        platforms = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True)

        for platform in platforms:
            if platform.posts_set.all().count() == 0:
                fetch_platform_data.apply_async([platform.id], queue='platform_extraction_2')

                plat_applied += 1

        ctr += 1
        if ctr % 100 == 0:
            print('%s bloggers performed, %s platforms issued' % (ctr, plat_applied))

    print('DONE: %s bloggers performed, %s platforms issued' % (ctr, plat_applied))


def issue_tasks_canada_bloggers():
    """
    Script to reissue tasks for platform discovery of Canadian bloggers.
    Reissuing only those who has valid blog_platform
    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.platformextractor import extract_combined

    infs = Influencer.objects.filter(
        show_on_search=True
    ).filter(
        demographics_locality__country='Canada'
    ).exclude(
        blacklisted=True
    ).exclude(
        old_show_on_search=True
    ).order_by('id')

    ctr_total = 0
    ctr_reissued = 0

    for inf in queryset_iterator(infs):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        # check that it is a Platform
        if isinstance(blog_plat, Platform) and \
                blog_plat.platformdataop_set.filter(operation='extract_platforms_from_platform',
                                                    started__gte=datetime.date(2016, 2, 17)).count() == 0:

            # resetting all its socials to invisible-non-autovalidated
            inf.reset_social_platforms()

            # issuing a task to re-perform the platform
            extract_combined.apply_async(
                kwargs={
                    'platform_id': blog_plat.id,
                },
                queue='platform_extraction_2'
            )

            ctr_reissued += 1

        ctr_total += 1
    print('Reissued %s influencers of %s total' % (ctr_reissued, ctr_total))


def classify_canadian_bloggers(ids=None):

    # limit_so_far = 5500

    from social_discovery.blog_discovery import queryset_iterator
    from social_discovery.classifiers import KeywordClassifier

    if ids is not None:
        infs = Influencer.objects.filter(id__in=ids)
    else:
        infs = Influencer.objects.filter(
            show_on_search=True
        ).filter(
            demographics_locality__country='Canada'
        ).exclude(
            blacklisted=True
        ).exclude(
            old_show_on_search=True
        ).order_by('id')

    classifier = KeywordClassifier()

    summary_results = {}

    classified_ctr = 0

    for inf in queryset_iterator(infs):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        results = []

        if isinstance(blog_plat, Platform):

            social_platforms = inf.platform_set.filter(autovalidated=True).exclude(url_not_found=True).filter(platform_name__in=Platform.SOCIAL_PLATFORMS)

            # if it's a blogspot or if it has an autovalidated bloglovin, then it should be a blog
            if (isinstance(blog_plat, Platform) and '.blogspot.' in blog_plat.url) or social_platforms.filter(platform_name='Bloglovin').count() > 0:
                print('has blogspot blog_platform or has an autovalidated Bloglovin' % results)
                summary_results[inf.id] = 'blogger'

            else:
                for platform in social_platforms:
                    result = classifier.classify_unit(platform.description)
                    # print('    platform: %s url: %s is considered to be: %s' % (platform.id, platform.url, result.upper()))
                    results.append(result)

                if 'blogger' in results:
                    summary_results[inf.id] = 'blogger'
                elif 'brand' in results:
                    summary_results[inf.id] = 'brand'
                else:
                    summary_results[inf.id] = 'undecided'

            if inf.classification is None:
                inf.classification = summary_results[inf.id]
            else:
                inf.classification = ' '.join([inf.classification, summary_results[inf.id]])
            inf.save()

            classified_ctr += 1

            # if classified_ctr >= limit_so_far:
            #     break

            # print('results: %s' % results)
            print('%s INFLUENCER id: %s url: %s considered as: %s' % (classified_ctr,
                                                                      inf.id,
                                                                      blog_plat.url if isinstance(blog_plat, Platform) else blog_plat,
                                                                      summary_results[inf.id].upper()))
            # print('* * * * * * * * * *')

    print('Final results:')
    print(summary_results)
    return summary_results



def canadian_bloggers_fetch_and_profile(platform_name=None):
    """
     run fetcher.fetcher_for_platform(platform) for each of these influencers and their autovalidated platforms
     then for each one of these influencers run influencer.set_profile_pic() so that their
     profile is obtained from the autovalidated
    :return:
    """
    if platform_name is None:
        return

    from platformdatafetcher import fetcher
    bloggers_col = InfluencersGroup.objects.get(name='alpha-canadian-bloggers')

    inf_ctr = 0
    plat_ctr = 0

    # for all of 'bloggers' group
    for blogger in bloggers_col.influencers:

        # fetching all platforms of a type
        platforms = blogger.platform_set.filter(autovalidated=True, platform_name=platform_name, validated_handle__isnull=True)

        for platform in platforms:
            # if platform has no validated handle - calling fetcher_for_platform
            try:
                fetcher.fetcher_for_platform(platform)
            except:
                pass

            plat_ctr += 1
        inf_ctr += 1

        print('*** %s influencers, %s platforms PERFORMED' % (inf_ctr, plat_ctr))


    # # for all of the bloggers we fetch profile pic
    # for blogger in bloggers_col.influencers:
    #     blogger.set_profile_pic()
    #     ctr += 1
    #
    #     if ctr % 100 == 0:
    #         print('set_profile_pic called for %s influencers' % ctr)

    print('DONE')


def canadian_bloggers_set_pic():

    bloggers_col = InfluencersGroup.objects.get(name='alpha-canadian-bloggers')
    for blogger in bloggers_col.influencers:
        blogger.set_profile_pic()


def canadian_bloggers_fetch_posts():
    """

    :return:
    """

    from platformdatafetcher.fetchertasks import fetch_platform_data
    bloggers_col = InfluencersGroup.objects.get(name='alpha-canadian-bloggers')

    ctr = 0
    plat_applied = 0

    # for all of 'bloggers' group
    for blogger in bloggers_col.influencers:

        # fetching all platforms of a type
        platforms = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True)

        for platform in platforms:
            if platform.posts_set.all().count() == 0:
                fetch_platform_data.apply_async([platform.id], queue='platform_extraction_2')

                plat_applied += 1

        ctr += 1
        if ctr % 100 == 0:
            print('%s bloggers performed, %s platforms issued' % (ctr, plat_applied))

    print('DONE: %s bloggers performed, %s platforms issued' % (ctr, plat_applied))



def fetch_names_investigation():
    """

    :return:
    """

    import io

    bloggers_col = InfluencersGroup.objects.get(name='alpha-men-bloggers')

    ctr = 0
    plat_applied = 0

    csvfile = io.open('canadian_blogger_names__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer id\tBlog url\tInstagram url\tInfluencer_attributes[\'name\']\tTwitter url\tInfluencer_attributes[\'name\']\tBloglovin url\tInfluencer_attributes[\'name\']\t\n'
    )

    # for all of 'bloggers' group
    for blogger in bloggers_col.influencers:

        insta = {}
        twitter = {}
        bloglovin = {}

        plats = blogger.platform_set.filter(platform_name__in=['Instagram', 'Twitter', 'Bloglovin']).exclude(url_not_found=True)

        for p in plats:
            if p.platform_name == 'Instagram':
                if p.url:
                    if p.autovalidated is True or plats.filter(platform_name='Instagram').count() == 1:
                        insta[p.url] = p.detected_influencer_attributes.get('name', None) if p.detected_influencer_attributes is not None else None
            elif p.platform_name == 'Twitter':
                if p.url:
                    if p.autovalidated is True or plats.filter(platform_name='Twitter').count() == 1:
                        twitter[p.url] = p.detected_influencer_attributes.get('name', None) if p.detected_influencer_attributes is not None else None
            elif p.platform_name == 'Bloglovin':
                if p.url:
                    if p.autovalidated is True or plats.filter(platform_name='Bloglovin').count() == 1:
                        bloglovin[p.url] = p.detected_influencer_attributes.get('name', None) if p.detected_influencer_attributes is not None else None

        csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
            blogger.id,
            blogger.blog_platform.url,
            u', '.join([u for u in insta.keys() if u is not None]),
            u', '.join([n for n in insta.values() if n is not None]),

            u', '.join([u for u in twitter.keys() if u is not None]),
            u', '.join([n for n in twitter.values() if n is not None]),

            u', '.join([u for u in bloglovin.keys() if u is not None]),
            u', '.join([n for n in bloglovin.values() if n is not None]),
        ))

        ctr += 1
        if ctr % 100 == 0:
            print('%s bloggers performed' % ctr)

    csvfile.close()


def count_platform_extracted_influencers(inf_queryset=None, started=None):
    """
    Counts influencers from queryset had their platform extraction performed/not performed since started date
    :param inf_queryset:
    :param started:
    :return:
    """

    performed_ids = []
    not_performed_ids = []

    for inf in inf_queryset:

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        if isinstance(blog_plat, Platform):
            if blog_plat.platformdataop_set.filter(
                    operation='extract_platforms_from_platform', started__gte=started).count() == 0:
                not_performed_ids.append(inf.id)

            else:
                performed_ids.append(inf.id)

    return performed_ids, not_performed_ids



def describe_performed_canadian_influencers():
    """

    :param inf_queryset:
    :param started:
    :return:
    """

    import io
    from social_discovery.blog_discovery import queryset_iterator

    performed_ids = []
    not_performed_ids = []

    started = date(2016, 2, 17)
    infs = Influencer.objects.filter(
        show_on_search=True
    ).filter(
        demographics_locality__country='Canada'
    ).exclude(
        blacklisted=True
    ).exclude(
        old_show_on_search=True
    ).order_by('id')

    csvfile = io.open('canadian_names_investigation__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer id\tplatform id\tplatform type\tplatform url\tautovalidated\turl_not_found\tname detected\n'
    )

    for inf in queryset_iterator(infs):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        if isinstance(blog_plat, Platform):
            if blog_plat.platformdataop_set.filter(
                    operation='extract_platforms_from_platform', started__gte=started).count() == 0:
                not_performed_ids.append(inf.id)
            else:
                performed_ids.append(inf.id)

                for plat in inf.platform_set.all():
                    if plat.autovalidated is True or plat.url_not_found is not True:

                        csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                            inf.id,
                            plat.id,
                            plat.platform_name,
                            plat.url,

                            plat.autovalidated,
                            plat.url_not_found,

                            plat.detected_influencer_attributes.get('name', None) if plat.detected_influencer_attributes is not None else None,
                        ))

    return performed_ids, not_performed_ids



def fb_platform_investigation():

    import io
    from platformdatafetcher.platformextractor import is_profile_fb_url

    test_platforms = Platform.objects.filter(platform_name='Facebook',
                                             autovalidated=True).exclude(url_not_found=True)[:500]

    csvfile = io.open('fb_platform_investigation__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer id\tFb platform id\tFb platform url\tautovalidated\tis profile?\n'
    )

    # for all of 'bloggers' group
    for platform in test_platforms:

        csvfile.write(u'%s\t%s\t%s\t%s\t%s\n' % (
            platform.influencer_id,
            platform.id,
            platform.url,
            platform.autovalidated,
            is_profile_fb_url(platform),
        ))

    csvfile.close()


def issue_tasks_uk_bloggers():
    """
    Script to reissue tasks for platform discovery of Canadian bloggers.
    Reissuing only those who has valid blog_platform
    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.platformextractor import extract_combined

    infs = Influencer.objects.filter(
        show_on_search=True
    ).filter(
        demographics_locality__country='United Kingdom'
    ).exclude(
        blacklisted=True
    ).exclude(
        old_show_on_search=True
    ).order_by('id')

    ctr_total = 0
    ctr_reissued = 0

    for inf in queryset_iterator(infs):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        # check that it is a Platform
        if isinstance(blog_plat, Platform) and \
                blog_plat.platformdataop_set.filter(operation='extract_platforms_from_platform',
                                                    started__gte=datetime.date(2016, 2, 19)).count() == 0:

            # resetting all its socials to invisible-non-autovalidated
            inf.reset_social_platforms()

            # issuing a task to re-perform the platform
            extract_combined.apply_async(
                kwargs={
                    'platform_id': blog_plat.id,
                },
                queue='platform_extraction_2'
            )

            ctr_reissued += 1

        ctr_total += 1
    print('Reissued %s influencers of %s total' % (ctr_reissued, ctr_total))


"""
Here goes a portion of scripts to perform influencers who are supposed to have show_on_search=True to make them
appear to production. The algorithm is the following:

    (1) Social platforms detection
    (2) Classification of influencers as bloggers/brands/undecided using their discovered platforms
    (3) Platform data fetching for autovalidated/visible platforms
    (4) Influencers denormalization
    (5) Profile picture setting
    (6) Posts fetching
    (7) Setting them old_show_on_search=True and reindexing

"""


# (1) Social platforms detection
def detect_social_platforms(inf_queryset=None, started_datetime=None, default_queue='platform_extraction_2'):
    """
    Script to issue tasks for platform discovery of bloggers by queryset.
    Reissuing only those who has valid blog_platform

    :param inf_queryset -- queryset or list of influencers to perform. Should be as small as possible like:

    Example: infs = Influencer.objects.filter(
        show_on_search=True
    ).filter(
        demographics_locality__country='United Kingdom'
    ).exclude(
        blacklisted=True
    ).exclude(
        old_show_on_search=True
    ).order_by('id')

    :param started_datetime -- datetime used to reissue influencers only of they have no DataSocialOp object with
    operation='' since that date. Used to continue performing queryset if the queue has been flushed.

    Example: datetime.date(2016, 2, 19)

    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.platformextractor import extract_combined

    # infs = Influencer.objects.filter(
    #     show_on_search=True
    # ).filter(
    #     demographics_locality__country='United Kingdom'
    # ).exclude(
    #     blacklisted=True
    # ).exclude(
    #     old_show_on_search=True
    # ).order_by('id')

    ctr_total = 0
    ctr_reissued = 0

    for inf in queryset_iterator(inf_queryset):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        # check that it is a Platform
        if isinstance(blog_plat, Platform) and \
                (started_datetime is None or blog_plat.platformdataop_set.filter(
                    operation='extract_platforms_from_platform',
                    started__gte=started_datetime).count() == 0):

            # resetting all its socials to invisible-non-autovalidated
            inf.reset_social_platforms()

            # issuing a task to re-perform the platform
            extract_combined.apply_async(
                kwargs={
                    'platform_id': blog_plat.id,
                },
                queue=default_queue
            )

            ctr_reissued += 1

        ctr_total += 1
    print('Reissued %s influencers of %s total' % (ctr_reissued, ctr_total))


# (2) Classification of influencers as bloggers/brands/undecided using their discovered platforms
def classify_influencers(inf_queryset=None):
    """
    Classifies influencers by their autovalidated and visible social platforms.
    Appends result to their classification field.

    :param inf_queryset -- queryset of bloggers to classify

    :returns summary_results dict
    """

    # limit_so_far = 5500

    from social_discovery.blog_discovery import queryset_iterator
    from social_discovery.classifiers import KeywordClassifier
    from platformdatafetcher.platformutils import username_from_platform_url
    import io
    # import hashlib
    from urlparse import urlparse

    classifier = KeywordClassifier()

    summary_results = {}

    classified_ctr = 0

    csvfile = io.open('classifying__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')

    social_similarity = {}

    domain_counts = {}

    for inf in queryset_iterator(inf_queryset):

        # getting blog_platform of this influencer
        blog_plat = inf.blog_platform

        results = []

        if isinstance(blog_plat, Platform):
            print('Inf: %s   Blog plat url: %s' % (inf.id, blog_plat.url))

            # TEMP: update domain counts
            netloc = urlparse(blog_plat.url).netloc
            nc = netloc.split('.')

            if len(nc) > 2 and nc[-2] in ['com', 'co']:
                key = u'.'.join(nc[-3:])
                if key in domain_counts:
                    domain_counts[key] = {'count': domain_counts[key]['count'] + 1,
                                          'ids': domain_counts[key]['ids'] + [inf.id, ]}
                else:
                    domain_counts[key] = {'count': 1,
                                          'ids': [inf.id, ]}
                # domain_counts[key] = domain_counts.get(key, 0) + 1
            elif len(nc) > 1:
                key = u'.'.join(nc[-2:])
                if key in domain_counts:
                    domain_counts[key] = {'count': domain_counts[key]['count'] + 1,
                                          'ids': domain_counts[key]['ids'] + [inf.id, ]}
                else:
                    domain_counts[key] = {'count': 1,
                                          'ids': [inf.id, ]}
                # domain_counts[key] = domain_counts.get(key, 0) + 1
            else:
                if netloc in domain_counts:
                    domain_counts[netloc] = {'count': domain_counts[netloc]['count'] + 1,
                                             'ids': domain_counts[netloc]['ids'] + [inf.id, ]}
                else:
                    domain_counts[netloc] = {'count': 1,
                                             'ids': [inf.id, ]}

            social_platforms = inf.platform_set.filter(
                autovalidated=True
            ).exclude(
                url_not_found=True
            ).filter(
                platform_name__in=Platform.SOCIAL_PLATFORMS
            )

            av_plats_dups = {}
            plat_urls = []

            own_plat_urls = []
            for platform in social_platforms:
                # av_plats_counts[platform.platform_name] = av_plats_counts.get(platform.platform_name, 0) + 1
                result = classifier.classify_unit(platform.description)
                # print('    platform: %s url: %s is considered to be: %s' % (platform.id, platform.url, result.upper()))
                results.append(result)

                plat_urls.append(platform.url)

                if platform.platform_name in av_plats_dups:
                    av_plats_dups[platform.platform_name].append({'username': username_from_platform_url(platform.url),
                                                                  'id': platform.id})
                else:
                    av_plats_dups[platform.platform_name] = [
                        {'username': username_from_platform_url(platform.url),
                         'id': platform.id}
                    ]

                # TEMP: Counting influencers for the same usernames
                username = username_from_platform_url(platform.url)
                # current = social_similarity.get(platform.platform_name, {})
                # current_username = current.get(username, 0)
                # current_username = current_username + 1
                # social_similarity[platform.platform_name] = current
                if platform.url in own_plat_urls:
                    pass
                else:
                    if platform.platform_name not in social_similarity:
                        social_similarity[platform.platform_name] = {}
                    social_similarity[platform.platform_name][username] = social_similarity[platform.platform_name].get(username, 0) + 1
                    own_plat_urls.append(platform.url)

            # Handling duplicate influencer here
            # print(sorted(plat_urls))
            # plat_urls_str = "|".join(sorted(plat_urls))
            # social_hash = hashlib.md5(plat_urls_str).hexdigest()
            # print('HASH: %s' % social_hash)
            # if social_hash in social_similarity:
            #     print(u'Influencer %s has same social platforms as influencer %s so it is skipped\n' % (
            #             inf.id,
            #             social_similarity[social_hash]
            #         ))
            #     csvfile.write(
            #         u'Influencer %s has same social platforms as influencer %s so it is skipped\n' % (
            #             inf.id,
            #             social_similarity[social_hash]
            #         )
            #     )
            #     continue
            # else:
            #     social_similarity[social_hash] = inf.id

            # Handling duplicate platforms here
            for k, v in av_plats_dups.items():
                duplicates = dict()
                for pl in v:
                    duplicates[pl['username']] = duplicates.get(pl['username'], []) + [pl['id']]

                for pn, pids in duplicates.items():
                    if len(pids) > 1:
                        csvfile.write(
                            u'Influencer %s has duplicate %s platforms with ids: %s\n' % (inf.id, pn, pids)
                        )

            # we set to bloggers only people with at least 2 autovalidated platforms of a type,
            # otherwise it is considered undecided
            if any([len(v) > 2 for v in av_plats_dups.values()]):
                summary_results[inf.id] = 'undecided'
            elif (isinstance(blog_plat, Platform) and '.blogspot.' in blog_plat.url) or social_platforms.filter(platform_name='Bloglovin').count() > 0:
                # if it's a blogspot or if it has an autovalidated bloglovin, then it should be a blog
                print('has blogspot blog_platform or has an autovalidated Bloglovin' % results)
                summary_results[inf.id] = 'blogger'
            elif 'blogger' in results:
                summary_results[inf.id] = 'blogger'
            elif 'brand' in results:
                summary_results[inf.id] = 'brand'
            else:
                summary_results[inf.id] = 'undecided'

            if inf.classification is None:
                inf.classification = summary_results[inf.id]
            else:
                current = ' '.join([c for c in inf.classification.split() if c.lower() not in ['blogger',
                                                                                               'brand',
                                                                                               'undecided']])
                inf.classification = ' '.join([current, summary_results[inf.id]])
            inf.save()

            classified_ctr += 1

            # if classified_ctr >= limit_so_far:
            #     break

            # print('results: %s' % results)
            print('%s INFLUENCER id: %s url: %s considered as: %s' % (classified_ctr,
                                                                      inf.id,
                                                                      blog_plat.url if isinstance(blog_plat, Platform) else blog_plat,
                                                                      summary_results[inf.id].upper()))
            # print('* * * * * * * * * *')

    csvfile.close()

    csvfile = io.open('domain_counts__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')

    for k, v in domain_counts.items():
        csvfile.write(u'%s\t%s\t%s\n' % (k, v['count'], v['ids']))

    csvfile.close()

    csvfile = io.open('similarity__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')

    for k, v in social_similarity.items():
        for u, qty in v.items():
            csvfile.write(u'%s\t%s\t%s\n' % (k, u, qty))

    csvfile.close()

    # print('Final results:')
    # print(summary_results)
    return summary_results


# (2.5) Removing influencers with duplicate platforms
def bloggers_remove_duplicate_influencers(influencers=None, dups_collection=None):
    """
    Removes all influencers found having similar platforms with usernames.
    If dups_collection is a collection, then these duplicates are moved there.

    :param influencers: -- queryset or collection (InfluencersGroup of influencers)
    :param dups_collection: -- None or collection for duplicates to deal with them later
    :return:
    """

    if influencers is None:
        return

    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.platformutils import username_from_platform_url

    if isinstance(influencers, InfluencersGroup):
        infs = influencers.influencers
    else:
        infs = queryset_iterator(influencers)

    data = {}

    print('Performing influencers -- filling data')

    ctr = 0
    for inf in infs:

        plats = inf.platform_set.filter(autovalidated=True).filter(
            platform_name__in=Platform.SOCIAL_PLATFORMS_CRAWLED).only('id', 'platform_name', 'url', 'autovalidated', 'validated_handle')
        plats_dict = {}
        for plat in plats:
            plats_dict = {'id': plat.id, 'platform_name': plat.platform_name,
                          'url': plat.url, 'validated_handle': plat.validated_handle}

        if len(plats_dict.keys()) > 0:
            data[inf.id] = plats_dict

        ctr += 1
        if ctr % 100 == 0:
            print('Performed %s influencers' % ctr)

    print('Data filled, calculating....')

    suspected_plats = {}
    suspected_plats_lst = []

    usernames = {}

    dup_inf_ids = []

    ctr = 0
    for inf1_id, plats1 in data.items():

        if plats1['id'] not in usernames:
            if plats1['url'].startswith('http://') or plats1['url'].startswith('https://'):
                pass
            else:
                plats1['url'] = 'http://%s' % plats1['url']
            usernames[plats1['id']] = username_from_platform_url(plats1['url'])
        uname1 = usernames.get(plats1['id'], None)

        for inf2_id, plats2 in data.items():
            if inf1_id != inf2_id:

                if plats2['id'] not in usernames:
                    if plats2['url'].startswith('http://') or plats2['url'].startswith('https://'):
                        pass
                    else:
                        plats2['url'] = 'http://%s' % plats2['url']
                    usernames[plats2['id']] = username_from_platform_url(plats2['url'])
                uname2 = usernames.get(plats2['id'], None)

                if plats1['platform_name'] == plats2['platform_name'] and uname1 == uname2:
                    # suspected_plats[plats1['id']] = (inf1_id, inf2_id)
                    suspected_plats_lst.append({
                        'inf1_id': inf1_id,
                        'plats1_id': plats1['id'],
                        'plats1_url': plats1['url'],
                        'uname1': uname1,
                        'handle1': plats1['validated_handle'],
                        'inf2_id': inf2_id,
                        'plats2_id': plats2['id'],
                        'plats2_url': plats2['url'],
                        'uname2': uname2,
                        'handle2': plats2['validated_handle'],
                    })

                    if inf1_id not in dup_inf_ids:
                        dup_inf_ids.append(inf1_id)
                    if inf2_id not in dup_inf_ids:
                        dup_inf_ids.append(inf2_id)

        ctr += 1
        if ctr % 100 == 0:
            print('Performed %s influencers' % ctr)

    print('Performed %s influencers' % ctr)
    if isinstance(dups_collection, InfluencersGroup):
        print('Moving duplicates to collection %r...' % dups_collection.name)

    else:
        print('Removing duplicates away...')

    for dup_id in dup_inf_ids:
        influencers.remove_influencer(Influencer.objects.get(id=dup_id))
        if isinstance(dups_collection, InfluencersGroup):
            dups_collection.add_influencer(Influencer.objects.get(id=dup_id))

    print('Task complete')


# (3) Platform data fetching for autovalidated/visible platforms
def bloggers_fetch_for_platform(influencers=None, platform_name=None):
    """
     run fetcher.fetcher_for_platform(platform) for each of these influencers and their autovalidated platforms
     then for each one of these influencers run influencer.set_profile_pic() so that their
     profile is obtained from the autovalidated

    :param influencers-- queryset or collection (InfluencersGroup of influencers)
    :param platform_name -- name of platform to perform, usually 1 of 5:
            Twitter
            Facebook
            Instagram
            Youtube
            Pinterest

    :return:
    """
    if influencers is None or platform_name is None:
        return

    from platformdatafetcher import fetcher
    from social_discovery.blog_discovery import queryset_iterator

    if isinstance(influencers, InfluencersGroup):
        infs = influencers.influencers
    else:
        infs = queryset_iterator(influencers)

    inf_ctr = 0
    plat_ctr = 0

    # for all of 'bloggers' group
    for blogger in infs:

        # fetching all platforms of a type
        platforms = blogger.platform_set.filter(autovalidated=True,
                                                platform_name=platform_name,
                                                validated_handle__isnull=True
                                                )

        for platform in platforms:
            # if platform has no validated handle - calling fetcher_for_platform
            try:
                fetcher.fetcher_for_platform(platform)
            except:
                pass

            plat_ctr += 1
        inf_ctr += 1

        print('*** %s influencers, %s platforms PERFORMED' % (inf_ctr, plat_ctr))

    print('DONE')


# (4) Influencers denormalization
def denormalize_influencers(influencers=None):
    """
    Runs .denormalize() for influencers
    :param influencers-- queryset or collection (InfluencersGroup of influencers)

    :return:
    """
    if influencers is None:
        return

    from social_discovery.blog_discovery import queryset_iterator

    if isinstance(influencers, InfluencersGroup):
        infs = influencers.influencers
    else:
        infs = queryset_iterator(influencers)

    for inf in infs:
        inf.denormalize()

    print('DONE')


# (5) Profile picture setting
def influencers_set_pic(influencers=None):
    """
    Runs .set_profile_pic() for influencers
    :param influencers-- queryset or collection (InfluencersGroup of influencers)

    :return:
    """
    if influencers is None:
        return

    from social_discovery.blog_discovery import queryset_iterator

    if isinstance(influencers, InfluencersGroup):
        infs = influencers.influencers
    else:
        infs = queryset_iterator(influencers)

    for inf in infs:
        inf.set_profile_pic()

    print('DONE')


# (6) Posts fetching
def influencers_fetch_posts(influencers=None, default_queue='platform_extraction_2'):
    """
    Fetches posts for influencers' autovalidated and visible platforms using celery.

    :param influencers-- queryset or collection (InfluencersGroup of influencers)

    :return:
    """
    if influencers is None:
        return

    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.fetchertasks import fetch_platform_data

    if isinstance(influencers, InfluencersGroup):
        infs = influencers.influencers
    else:
        infs = queryset_iterator(influencers)

    ctr = 0
    plat_applied = 0
    weird_platforms = {}

    # for all of 'bloggers' group
    for blogger in infs:

        weird = blogger.weird_visible_platforms()
        if weird is not None:
            weird_platforms[blogger.id] = weird

        # fetching all platforms of a type
        # Some visible platforms could be non-autovalidated, so removing autovalidated=True filter
        # platforms = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True)
        platforms = blogger.platform_set.exclude(url_not_found=True)

        for platform in platforms:
            # Only platforms without posts will be issued
            if platform.posts_set.all().count() == 0:
                fetch_platform_data.apply_async([platform.id], queue=default_queue)

                plat_applied += 1

        ctr += 1
        if ctr % 100 == 0:
            print('%s bloggers performed, %s platforms issued' % (ctr, plat_applied))

    print('DONE: %s bloggers performed, %s platforms issued' % (ctr, plat_applied))
    return weird_platforms

"""
Influencer performance scripts finished
"""

def influencers_platform_groups(influencers=None):

    if influencers is None:
        return

    from social_discovery.blog_discovery import queryset_iterator
    from platformdatafetcher.fetchertasks import fetch_platform_data

    if isinstance(influencers, InfluencersGroup):
        infs = influencers.influencers
    else:
        infs = queryset_iterator(influencers)

    result = {}

    ctr = 0
    for blogger in infs:
        ctr_fb = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True).filter(platform_name='Facebook').count()
        ctr_tw = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True).filter(platform_name='Twitter').count()
        ctr_in = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True).filter(platform_name='Instagram').count()
        ctr_pi = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True).filter(platform_name='Pinterest').count()
        ctr_yt = blogger.platform_set.filter(autovalidated=True).exclude(url_not_found=True).filter(platform_name='Youtube').count()

        ctr_max = max(ctr_fb, ctr_tw, ctr_in, ctr_pi, ctr_yt)

        if ctr_max not in result:
            result[ctr_max] = [blogger.id,]
        else:
            result[ctr_max].append(blogger.id)

        ctr += 1
        if ctr % 100 == 0:
            print('%s bloggers performed' % ctr)

    print('DONE: %s bloggers performed' % ctr)
    return result

@task(name="debra.scripts.refetch_posts_interactions", ignore_result=True)
def refetch_posts_interactions(platform, num_posts=None):
    """
    Helpher method to refetch post interactions
    """
    from platformdatafetcher import fetcher
    posts = platform.posts_set.all()

    if platform.platform_name == 'Pinterest':
        posts = posts.order_by('-inserted_datetime')
    else:
        posts = posts.order_by('-create_date')

    if num_posts:
        posts = posts[:num_posts]

    f = fetcher.fetcher_for_platform(platform)
    f.fetch_post_interactions(posts)


def populate_empty_advertising_emails(followers=3000, plat=None):
    """
    Finding all influencers with at least number of followers without email_for_advertising_or_collaborations set
    and trying to find some emails in their social autovalidated platforms.
    :return:
    """

    from social_discovery.blog_discovery import queryset_iterator
    from debra.models import Influencer, Platform
    import re
    import io

    infs = Influencer.objects.filter(
        email_for_advertising_or_collaborations__isnull=True,
        old_show_on_search=True
    ).filter(
        platform__autovalidated=True,
        platform__num_followers__gte=followers,
        platform__platform_name__in=Platform.SOCIAL_PLATFORMS
    ).distinct('id')

    print('Started')
    print('Got infs: %s' % infs.count())

    ctr = 0
    ctr_updated = 0

    csvfile = io.open('detected_emails__%s__%s.csv' % (plat.lower(), datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S')), 'w+', encoding='utf-8')
    csvfile.write(
        u'Influencer id\tPlatform url\tdescription\tEmails detected\t\n'
    )

    regex = re.compile(("([a-z0-9!#$%&'*+\/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+\/=?^_`"
                        "{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(\.|"
                        "\sdot\s))+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"))

    for inf in queryset_iterator(infs):
        if plat:
            plats = inf.platform_set.filter(autovalidated=True, platform_name=plat)
        else:
            plats = inf.platform_set.filter(autovalidated=True, platform_name__in=Platform.SOCIAL_PLATFORMS)

        found_emails = []

        for p in plats:
            if p.detected_influencer_attributes is not None and 'description' in p.detected_influencer_attributes:
                match = re.findall(regex, p.detected_influencer_attributes['description'])
                found_emails = found_emails + [email[0].lower() for email in match if email[0].lower() not in found_emails and not email[0].startswith('//')]

                csvfile.write(
                    u'%s\t%s\t%s\t%s\t\n' % (inf.id, p.url, u" ".join(p.detected_influencer_attributes['description'].split()), " ".join(found_emails))
                )

        if len(found_emails) > 0:
            # inf.email_for_advertising_or_collaborations = " ".join(found_emails)
            # inf.save()
            ctr_updated += 1
        # else:
        #     print('For Inf %s found no emails' % inf.id)

        ctr += 1

        if ctr % 1000 == 0:
            print('Performed %s influencers (updated %s)' % (ctr, ctr_updated))

    print('Performed %s influencers (updated %s)' % (ctr, ctr_updated))

    csvfile.close()


def check_duplicated_platforms():
    """
    script collects suspicious duplicated platforms info
    :return:
    """
    from platformdatafetcher.platformutils import username_from_platform_url
    import io

    bloggers_col = InfluencersGroup.objects.get(name='alpha-insta1000-bloggers')

    influencers = bloggers_col.influencers

    data = {}

    print('Performing influencers -- filling data')

    ctr = 0
    for inf in influencers:

        plats = inf.platform_set.filter(autovalidated=True).filter(
            platform_name__in=Platform.SOCIAL_PLATFORMS_CRAWLED).only('id', 'platform_name', 'url', 'autovalidated', 'validated_handle')
        plats_dict = {}
        for plat in plats:
            plats_dict = {'id': plat.id, 'platform_name': plat.platform_name,
                          'url': plat.url, 'validated_handle': plat.validated_handle}

        if len(plats_dict.keys()) > 0:
            data[inf.id] = plats_dict

        ctr += 1
        if ctr % 100 == 0:
            print('Performed %s influencers' % ctr)

    print('Data filled, calculating....')

    suspected_plats = {}
    suspected_plats_lst = []

    usernames = {}

    ctr = 0
    for inf1_id, plats1 in data.items():

        if plats1['id'] not in usernames:
            if plats1['url'].startswith('http://') or plats1['url'].startswith('https://'):
                pass
            else:
                plats1['url'] = 'http://%s' % plats1['url']
            usernames[plats1['id']] = username_from_platform_url(plats1['url'])
        uname1 = usernames.get(plats1['id'], None)

        for inf2_id, plats2 in data.items():
            if inf1_id != inf2_id:

                if plats2['id'] not in usernames:
                    if plats2['url'].startswith('http://') or plats2['url'].startswith('https://'):
                        pass
                    else:
                        plats2['url'] = 'http://%s' % plats2['url']
                    usernames[plats2['id']] = username_from_platform_url(plats2['url'])
                uname2 = usernames.get(plats2['id'], None)

                if plats1['platform_name'] == plats2['platform_name'] and uname1 == uname2:
                    # suspected_plats[plats1['id']] = (inf1_id, inf2_id)
                    suspected_plats_lst.append({
                        'inf1_id': inf1_id,
                        'plats1_id': plats1['id'],
                        'plats1_url': plats1['url'],
                        'uname1': uname1,
                        'handle1': plats1['validated_handle'],
                        'inf2_id': inf2_id,
                        'plats2_id': plats2['id'],
                        'plats2_url': plats2['url'],
                        'uname2': uname2,
                        'handle2': plats2['validated_handle'],
                    })

        ctr += 1
        if ctr % 100 == 0:
            print('Performed %s influencers' % ctr)

    # for inf1 in influencers:
    #     for plats1 in inf1.platform_set.filter(autovalidated=True).filter(
    #             platform_name__in=Platform.SOCIAL_PLATFORMS_CRAWLED).only('id', 'platform_name', 'url', 'autovalidated'):
    #         for inf2 in influencers:
    #             if inf1.id != inf2.id:
    #                 for plats2 in inf2.platform_set.filter(autovalidated=True).filter(
    #                         platform_name__in=Platform.SOCIAL_PLATFORMS_CRAWLED).only('id', 'platform_name',
    #                                                                                  'url', 'autovalidated'):
    #                     if plats1.id not in usernames:
    #                         if plats1.url.startswith('http://') or plats1.url.startswith('https://'):
    #                             pass
    #                         else:
    #                             plats1.url = 'http://%s' % plats1.url
    #                         usernames[plats1.id] = username_from_platform_url(plats1.url)
    #                     uname1 = usernames.get(plats1.id, None)
    #
    #                     if plats2.id not in usernames:
    #                         if plats2.url.startswith('http://') or plats2.url.startswith('https://'):
    #                             pass
    #                         else:
    #                             plats2.url = 'http://%s' % plats2.url
    #                         usernames[plats2.id] = username_from_platform_url(plats2.url)
    #                     uname2 = usernames.get(plats2.id, None)
    #
    #                     if plats1.platform_name == plats2.platform_name and uname1 == uname2:
    #                         suspected_plats[plats1.id] = (inf1.id, inf2.id)

    csvfile = io.open('suspected_plats__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')

    csvfile.write(u'Inf1 id\tPlatform1 id\tPlatform1 url\tUsername1\tvalidated handle 1\t'
                  u'Inf2 id\tPlatform2 id\tPlatform2 url\tUsername2\tvalidated handle 2\n')

    # for k, v in suspected_plats.items():
    #     csvfile.write(u'%s\t%s\t%s\n' % (k, v[0], v[1]))
    for v in suspected_plats_lst:
        csvfile.write(u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
            v['inf1_id'], v['plats1_id'], v['plats1_url'], v['uname1'], v['handle1'],
            v['inf2_id'], v['plats2_id'], v['plats2_url'], v['uname2'], v['handle2'],
        ))

        # csvfile.write(u'%s\t%s\t%s\n' % (v['id'], v['inf1_id'], v['inf2_id']))


    csvfile.close()

    return suspected_plats


def feedless():
    """
    Let's look at all influencers who have show_on_search=True and exclude (blacklisted=True or
    with url__contains='theshelf.com' or source__contains='brand')

    Then, find all of their platforms with platform_name__in=Platform.BLOG_PLATFORMS

    1. Now, we need to check how many of these platforms don't have a feed_url?
    These might be in thousands, so we need to check if they are good platforms to check first.
    So, let's sort them by number of followers on this influencer's auto-validated social urls
    (so that we only check the high quality influencers first).
    Let's look at the top 200 first and see if they really don't have a
    feed url or whether our current logic didn't find it?

    :return:
    """

    infs = Influencer.objects.filter(
        show_on_search=True
    ).exclude(
        blacklisted=True
    ).exclude(
        blog_url__contains='theshelf.com'
    ).exclude(
        source__contains='brand'
    )

    print('Initially found %s influencers' % infs.count())

    plats = Platform.objects.filter(
        platform_name__in=Platform.BLOG_PLATFORMS
    ).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='theshelf.com'
    ).exclude(
        influencer__source__contains='brand'
    ) # .distinct('id')

    print('Initially found %s blog platforms' % plats.distinct('id').count())

    feedless_plats = plats.filter(feed_url__isnull=True)

    print('Initially found %s feedless blog platforms' % feedless_plats.distinct('id').count())

    top_feedless_plats = feedless_plats.order_by('-influencer__platform__num_followers').distinct('influencer__platform__num_followers')

    for tfp in top_feedless_plats[:200]:
        print(tfp.influencer.id, tfp.id, tfp.url, tfp.feed_url)


def fetch_dates_for_pinterest_platform(platform_id=None,
                                       starting_insert_datetime=datetime.datetime(2016, 1, 1),
                                       custom_access_token=None):
    """

    :param platform_id:
    :param starting_insert_datetime:
    :return:
    """
    if platform_id is None:
        return

    from platformdatafetcher.pinterest_api import BasicPinterestFetcher
    from dateutil import parser

    try:
        plat = Platform.objects.get(id=platform_id)
        print('Performing platform: %s' % plat)
        posts = plat.posts_set.filter(create_date__isnull=True, inserted_datetime__gte=starting_insert_datetime)
        print('Posts to perform: %s' % posts.count())
        bpf = BasicPinterestFetcher(custom_access_token)
        for p in posts:
            data = bpf.get_pin_data(p.api_id)
            if data is not None:
                pin_date = data.get('data', None)
                if pin_date:
                    pin_date = pin_date.get('created_at', None)
                    if pin_date:
                        pin_date = parser.parse(pin_date)
                        p.create_date = pin_date
                        p.last_modified = datetime.datetime.now()
                        p.save()
        print('Posts are done')
        inf = plat.influencer
        inf.last_modified = datetime.datetime.now()
        inf.save()
        print('Influencer\'s %s last_modified updated.' % inf.id)

    except Platform.DoesNotExist:
        print('Platform with id %s does not exist' % platform_id)


def fix_dates_for_pinterest_posts_from_es(
        # post_id_from=None,
        # post_id_to=None,
        page_from=0,
        pages_qty_total=0,
        custom_access_token=None
    ):
    """
    Fetches Pinterest posts from ES and fixes its date in DB, schedules that post and influencer on reindexing.

    Custom API keys to run 3 simultaneous tasks:

    token 2: AdwiM2ClD7HzMmcRvkjvU4ZnSsidFFI1k120cPlDH2XLi-Au2wAAAAA
    token 3: AXWwYKS94fri6ogWA4FRrPglpvARFFI2IOmk9DNDH2b03aBBjQAAAAA
    token 4: AbQDDsd_zbUYr9ip99j-h_NHGxAgFFI2NbtP06dDH2XLi-Au2wAAAAA

    """
    from platformdatafetcher.pinterest_api import BasicPinterestFetcher
    from dateutil import parser
    from es_requests import make_es_get_request

    # fetching ids of Pinterest posts to fix

    post_url = "%s/%s/post/_search?scroll=1m" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    scroll_url = "%s/_search/scroll?scroll=1m" % ELASTICSEARCH_URL

    future_pin_posts_ids = []  # posts with ES found indexed in ES

    es_rq = {
        "filter": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "create_date": {
                                "gte": "now"
                            }
                        }
                    },
                    {
                        "terms": {
                            "platform_name": [
                                "Pinterest"
                            ]
                        }
                    }
                ]
            }

        },
        "size": 500,
        "from": 0,
        "_source": {
            "exclude": [],
            "include": [
                "_id"
            ]
        }
    }

    # Populating lists
    should_request = True
    scroll_token = None
    resp_ctr = 0
    page = 0
    while should_request:
        if scroll_token is None:
            rq = make_es_get_request(
                es_url=post_url,
                es_query_string=json.dumps(es_rq)
            )
        else:
            rq = make_es_get_request(
                es_url=scroll_url,
                es_query_string=scroll_token
            )

        resp = rq.json()
        resp_ctr += 1

        print('Loaded ids page # %s' % resp_ctr)

        scroll_token = resp.get("_scroll_id", None)
        hits = resp.get('hits', {}).get('hits', [])

        if len(hits) == 0:
            should_request = False
        else:
            if page >= page_from:
                for hit in hits:
                    try:
                        post_id = int(hit.get('_id', None))
                        if page <= page_from + pages_qty_total:
                            future_pin_posts_ids.append(post_id)

                        if page > page_from + pages_qty_total:
                            should_request = False
                            print('Found last post page, no need to continue')
                    except:
                        pass

        page += 1

    n = 0

    print('Loaded %s ids total.' % len(future_pin_posts_ids))

    bpf = BasicPinterestFetcher(custom_access_token)
    for pid in future_pin_posts_ids:

        try:
            p = Posts.objects.select_related('influencer').get(id=pid)
            if p.platform_name == 'Pinterest' and p.create_date > datetime.datetime.now():
                data = bpf.get_pin_data(p.api_id)
                if data is not None:
                    pin_date = data.get('data', None)
                    if pin_date:
                        pin_date = pin_date.get('created_at', None)
                        if pin_date:
                            pin_date = parser.parse(pin_date)
                            p.create_date = pin_date
                            p.last_modified = datetime.datetime.now()
                            p.save()
                            n += 1
                            print('%s Fixed date %s for post: %s ' % (n, p.create_date, pid))

                            # saving inf only if it does not already has date == today
                            if p.influencer.last_modified.date() != datetime.datetime.today().date():
                                inf = p.influencer
                                inf.last_modified = datetime.datetime.now()
                                inf.save()
                                print('%s Influencer\'s %s last_modified set to today.' % (n, inf.id))
        except Posts.DoesNotExist:
            print('Post %s does not exist in DB' % pid)

    print(' %s Posts are done' % n)
    return future_pin_posts_ids




def issue_tasks_fix_dates_for_pinterest_posts_from_es():
    """
    Fetches Pinterest posts from ES and fixes its date in DB, schedules that post and influencer on reindexing.
    Issues tasks to queue: fix_pinterest_dates

    UPDATE: unit of tasks is Influencer now.

    Custom API keys to run 3 simultaneous tasks:

    token 2: AdwiM2ClD7HzMmcRvkjvU4ZnSsidFFI1k120cPlDH2XLi-Au2wAAAAA
    token 3: AXWwYKS94fri6ogWA4FRrPglpvARFFI2IOmk9DNDH2b03aBBjQAAAAA
    token 4: AbQDDsd_zbUYr9ip99j-h_NHGxAgFFI2NbtP06dDH2XLi-Au2wAAAAA

    """
    from es_requests import make_es_get_request
    from debra.tasks import fix_pinterest_post_date_1, fix_pinterest_post_date_2, fix_pinterest_post_date_3

    # fetching ids of Pinterest posts to fix

    inf_url = "%s/%s/influencer/_search?scroll=1m" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    scroll_url = "%s/_search/scroll?scroll=1m" % ELASTICSEARCH_URL

    future_pin_infs_ids = []  # infs with fitire dates found indexed in ES

    es_rq = {
        "filter": {
            "bool": {
                "must": [
                    {
                        "has_child": {
                            "child_type": "post",
                            "query": {

                                "bool": {
                                    "must": [
                                        {
                                            "range": {
                                                "create_date": {
                                                    "gte": "now"
                                                }
                                            }
                                        },
                                        {
                                            "terms": {
                                                "platform_name": [
                                                    "Pinterest"
                                                ]
                                            }
                                        }

                                    ]
                                }
                            }
                        }
                    }
                ]
            }

        },
        "size": 500,
        "from": 0,
        "_source": {
            "exclude": [],
            "include": [
                "_id"
            ]
        }
    }

    # Populating lists
    should_request = True
    scroll_token = None

    # task executors:
    # debra.tasks.fix_pinterest_post_date_1
    # debra.tasks.fix_pinterest_post_date_2
    # debra.tasks.fix_pinterest_post_date_3
    current_round_robin = 1
    max_round_robin = 3

    while should_request:
        if scroll_token is None:
            rq = make_es_get_request(
                es_url=inf_url,
                es_query_string=json.dumps(es_rq)
            )
        else:
            rq = make_es_get_request(
                es_url=scroll_url,
                es_query_string=scroll_token
            )

        print('Inf ids fetched: %s' % len(future_pin_infs_ids))

        resp = rq.json()

        scroll_token = resp.get("_scroll_id", None)
        hits = resp.get('hits', {}).get('hits', [])

        if len(hits) == 0:
            should_request = False
        else:

            for hit in hits:
                try:
                    inf_id = int(hit.get('_id', None))
                    future_pin_infs_ids.append(inf_id)

                    if current_round_robin == 1:
                        fix_pinterest_post_date_1.apply_async(
                            kwargs={
                                'inf_id': inf_id
                            },
                            queue='fix_pin_date_01'
                        )
                    elif current_round_robin == 2:
                        fix_pinterest_post_date_2.apply_async(
                            kwargs={
                                'inf_id': inf_id
                            },
                            queue='fix_pin_date_02'
                        )
                    elif current_round_robin == 3:
                        fix_pinterest_post_date_3.apply_async(
                            kwargs={
                                'inf_id': inf_id
                            },
                            queue='fix_pin_date_03'
                        )
                    if current_round_robin >= max_round_robin:
                        current_round_robin = 1
                    else:
                        current_round_robin += 1
                except:
                    pass

    print('Issued %s ids total.' % len(future_pin_infs_ids))
    return future_pin_infs_ids

def set_dates_for_pinterest_campaign(campaign_id=None, starting_insert_datetime=datetime.datetime(2016, 3, 1)):
    """

    :param campaign_id:
    :param starting_insert_datetime:
    :return:
    """

    if campaign_id is None:
        return

    try:
        bjp = BrandJobPost.objects.get(id=campaign_id)

        # Initial data
        inf_ids = list(bjp.candidates.filter(campaign_stage__gte=3).values_list('mailbox__influencer__id', flat=True))
        inf_ids = [iid for iid in inf_ids if iid is not None]  # stripping possible Nones

        for inf_id in inf_ids:
            print('Influencer: %s' % inf_id)
            pin_plats = Influencer.objects.get(id=inf_id).platform_set.filter(platform_name='Pinterest').exclude(url_not_found=True)
            for pp in pin_plats:
                print('PLATFORM found: %s' % pp.id)
                fetch_dates_for_pinterest_platform(pp.id, starting_insert_datetime)
    except BrandJobPost.DoesNotExist:
        print('BJP with id %s does not exist' % campaign_id)


def calculate_age_dist_for_production():
    """
    calculates age_dist values for influencers in production.
    :return:
    """
    from social_discovery.blog_discovery import queryset_iterator

    infs = Influencer.objects.filter(old_show_on_search=True)

    ctr = 0
    for inf in queryset_iterator(infs):
        inf.recalculate_age_distribution()
        ctr += 1

        if ctr % 1000 == 0:
            print('Calculated %s influencers' % ctr)

    print('Done : %s.' % ctr)


# def clean_replica():
#     """
#     Cleanses replica DB from unneeded data.
#     :return:
#     """
#
#     from xps import models as xps_models
#
#     from social_discovery.blog_discovery import queryset_iterator
#
#     print('Cleaning debra.PlatformDataOp')
#     # qty = PlatformDataOp.objects.all().delete()
#     # print('debra.PlatformDataOp data deleted: %s' % qty)
#
#     qty = 1
#     total = 0
#     while 1:
#         ids = list(PlatformDataOp.objects.all().values_list('id', flat=True)[:5000])
#         PlatformDataOp.objects.filter(id__in=ids).delete()
#
#         if len(ids) < 5000:
#             break
#         total += len(ids)
#
#         print('debra.PlatformDataOp data deleted: %s / total: %s' % (len(ids), total))
#     print('debra.PlatformDataOp all data deleted: %s' % total)
#
#     return
#
#     print('Cleaning debra.PdoLatest')
#     qty = PdoLatest.objects.all().delete()
#     print('debra.PdoLatest data deleted: %s' % qty)
#
#     print('Cleaning xps.CorrectValue')
#     qty = xps_models.CorrectValue.objects.all().delete()
#     print('xps.CorrectValue data deleted: %s' % qty)
#
#     print('Cleaning xps.FoundValue')
#     qty = xps_models.FoundValue.objects.all().delete()
#     print('xps.FoundValue data deleted: %s' % qty)
#
#     print('Cleaning xps.ScrapingResult')
#     qty = xps_models.ScrapingResult.objects.all().delete()
#     print('xps.ScrapingResult data deleted: %s' % qty)
#
#     print('Cleaning xps.ScrapingResultSet')
#     qty = xps_models.ScrapingResultSet.objects.all().delete()
#     print('xps.ScrapingResultSet data deleted: %s' % qty)
#
#     print('Cleaning xps.ScrapingResultSetEntry')
#     qty = xps_models.ScrapingResultSetEntry.objects.all().delete()
#     print('xps.ScrapingResultSetEntry data deleted: %s' % qty)
#
#     print('Cleaning xps.ScrapingResultSize')
#     qty = xps_models.ScrapingResultSize.objects.all().delete()
#     print('xps.ScrapingResultSize data deleted: %s' % qty)
#
#     print('Cleaning xps.XpathExpr')
#     qty = xps_models.XPathExpr.objects.all().delete()
#     print('xps.XPathExpr data deleted: %s' % qty)
#
#     print('Cleaning debra.Influencers')
#     ctr = 0
#     all_infs = Influencer.objects.exclude(show_on_search=True)
#     total = all_infs.count()
#     for inf in queryset_iterator(all_infs):
#         qty = inf.delete()
#         print('Influencer %s deleted with %s objects' % (ctr, qty))
#         ctr += 1
#         if ctr % 100 == 0:
#             print('Deleted %s influencers out of %s' % (ctr, total))
#
#     # Influencer.objects.exclude(show_on_search=True).delete()
#     print('debra.Influencers data deleted: %s' % total)
#
#     #print('Cleaning debra.Posts')
#     #qty = Posts.objects.exclude(influencer__show_on_search=True).delete()
#     #print('debra.Posts data deleted: %s' % qty)
#
#     #print('Cleaning debra.Platform')
#     #qty = Platform.objects.exclude(influencer__show_on_search=True).delete()
#     #qty += Platform.objects.filter(url_not_found=True).delete()
#     #print('debra.Platform data deleted: %s' % qty)
#
#     #print('Cleaning debra.PostInteractions')
#     #qty = PostInteractions.objects.exclude(post__influencer__show_on_search=True).delete()
#     #print('debra.PostInteractions data deleted: %s' % qty)
#
#     # Todo: What will be the best way to delete ProductModel / ProductModelShelfMap ?



def crawled_by_platform(p, last_date):
    """

    :param p:
    :param last_date:
    :return:
    """

    if p is None:

        return PlatformDataOp.objects.filter(
            operation='fetch_data',
            platform__influencer__old_show_on_search=True,
            started__gte=last_date,
        ).count()
    else:
        return PlatformDataOp.objects.filter(
            operation='fetch_data',
            platform__influencer__old_show_on_search=True,
            platform__platform_name=p,
            started__gte=last_date,
        ).count()


def crawled_influencers_total(last_date, unique=True, inverted=False):
    """

    :param last_date:
    :param unique:
    :param inverted:
    :return:
    """

    qs = Influencer.objects.filter(
        old_show_on_search=True,
    )
    if inverted is True:
        qs = qs.exclude(
            platform__platformdataop__operation='fetch_data',
            platform__platformdataop__started__gte=last_date,
        )
    else:
        qs = qs.filter(
            platform__platformdataop__operation='fetch_data',
            platform__platformdataop__started__gte=last_date,
        )

    if unique is True:
        qs = qs.distinct('id')

    return qs.count()


def crawled_platforms_total(last_date, unique=True, plat_name=None):
    """

    :param last_date:
    :param unique:
    :param plat_name:
    :return:
    """

    if plat_name is not None:
        qs = PlatformDataOp.objects.filter(
            platform__influencer__old_show_on_search=True,
            platform__platform_name=plat_name,
            operation='fetch_data',
            started__gte=last_date,
        )
    else:
        qs = PlatformDataOp.objects.filter(
            platform__influencer__old_show_on_search=True,
            operation='fetch_data',
            started__gte=last_date,
        )

    if unique is True:
        qs = qs.distinct('id')

    return qs.count()



def describe_crawled():
    """

    :return:
    """
    import datetime

    print('fetching counts:')

    last_date = datetime.datetime(2016, 5, 9)
    print('Fetched data the last week: %s' % crawled_by_platform(None, last_date))
    print('Among them:')

    for p in Platform.BLOG_PLATFORMS:
        print('    %s: %s' % (p, crawled_by_platform(p, last_date)))
    for p in Platform.SOCIAL_PLATFORMS_CRAWLED:
        print('    %s: %s' % (p, crawled_by_platform(p, last_date)))
    print('*' * 40)

    last_date = datetime.datetime(2016, 5, 2)
    print('Fetched data the last two weeks: %s' % crawled_by_platform(None, last_date))
    print('Among them:')
    for p in Platform.BLOG_PLATFORMS:
        print('    %s: %s' % (p, crawled_by_platform(p, last_date)))
    for p in Platform.SOCIAL_PLATFORMS_CRAWLED:
        print('    %s: %s' % (p, crawled_by_platform(p, last_date)))
    print('*' * 40)

    last_date = datetime.datetime(2016, 4, 25)
    print('Fetched data the last three weeks: %s' % crawled_by_platform(None, last_date))
    print('Among them:')
    for p in Platform.BLOG_PLATFORMS:
        print('    %s: %s' % (p, crawled_by_platform(p, last_date)))
    for p in Platform.SOCIAL_PLATFORMS_CRAWLED:
        print('    %s: %s' % (p, crawled_by_platform(p, last_date)))
    print('*' * 40)

    last_date = datetime.datetime(2016, 4, 18)
    print('Fetched data the last three weeks: %s' % crawled_by_platform(None, last_date))
    print('Among them:')
    for p in Platform.BLOG_PLATFORMS:
        print('    %s: %s' % (p, crawled_by_platform(p, last_date)))
    for p in Platform.SOCIAL_PLATFORMS_CRAWLED:
        print('    %s: %s' % (p, crawled_by_platform(p, last_date)))
    print('*' * 40)




def describe_crawled2():
    """

    :return:
    """
    import datetime

    total_infs = Influencer.objects.filter(old_show_on_search=True).count()

    last_date = datetime.datetime(2016, 5, 9)
    print(' * * * LAST WEEK * * *')
    print('INFLUENCERS (old_show_on_search=True):')
    crawled_total = crawled_influencers_total(last_date, unique=True, inverted=False)
    print('    Crawled, unique: %s' % crawled_total)
    print('    Not crawled, unique: %s' % (total_infs - crawled_total))

    print('PLATFORMS (old_show_on_search=True):')
    print('    TOTAL: %s' % crawled_platforms_total(last_date, unique=True, plat_name=None))
    for p in Platform.BLOG_PLATFORMS:
        print('    %s: %s' % (p, crawled_platforms_total(last_date, unique=True, plat_name=p)))
    for p in Platform.SOCIAL_PLATFORMS_CRAWLED:
        print('    %s: %s' % (p, crawled_platforms_total(last_date, unique=True, plat_name=p)))
    print('*' * 40)

    last_date = datetime.datetime(2016, 5, 2)
    print(' * * * LAST 2 WEEKS * * *')
    print('INFLUENCERS (old_show_on_search=True):')
    crawled_total = crawled_influencers_total(last_date, unique=True, inverted=False)
    print('    Crawled, unique: %s' % crawled_total)
    print('    Not crawled, unique: %s' % (total_infs - crawled_total))

    print('PLATFORMS (old_show_on_search=True):')
    print('    TOTAL: %s' % crawled_platforms_total(last_date, unique=True, plat_name=None))
    for p in Platform.BLOG_PLATFORMS:
        print('    %s: %s' % (p, crawled_platforms_total(last_date, unique=True, plat_name=p)))
    for p in Platform.SOCIAL_PLATFORMS_CRAWLED:
        print('    %s: %s' % (p, crawled_platforms_total(last_date, unique=True, plat_name=p)))
    print('*' * 40)

    last_date = datetime.datetime(2016, 4, 25)
    print(' * * * LAST 3 WEEKS * * *')
    print('INFLUENCERS (old_show_on_search=True):')
    crawled_total = crawled_influencers_total(last_date, unique=True, inverted=False)
    print('    Crawled, unique: %s' % crawled_total)
    print('    Not crawled, unique: %s' % (total_infs - crawled_total))

    print('PLATFORMS (old_show_on_search=True):')
    print('    TOTAL: %s' % crawled_platforms_total(last_date, unique=True, plat_name=None))
    for p in Platform.BLOG_PLATFORMS:
        print('    %s: %s' % (p, crawled_platforms_total(last_date, unique=True, plat_name=p)))
    for p in Platform.SOCIAL_PLATFORMS_CRAWLED:
        print('    %s: %s' % (p, crawled_platforms_total(last_date, unique=True, plat_name=p)))
    print('*' * 40)

    last_date = datetime.datetime(2016, 4, 18)
    print(' * * * LAST 4 WEEKS * * *')
    print('INFLUENCERS (old_show_on_search=True):')
    crawled_total = crawled_influencers_total(last_date, unique=True, inverted=False)
    print('    Crawled, unique: %s' % crawled_total)
    print('    Not crawled, unique: %s' % (total_infs - crawled_total))

    print('PLATFORMS (old_show_on_search=True):')
    print('    TOTAL: %s' % crawled_platforms_total(last_date, unique=True, plat_name=None))
    for p in Platform.BLOG_PLATFORMS:
        print('    %s: %s' % (p, crawled_platforms_total(last_date, unique=True, plat_name=p)))
    for p in Platform.SOCIAL_PLATFORMS_CRAWLED:
        print('    %s: %s' % (p, crawled_platforms_total(last_date, unique=True, plat_name=p)))
    print('*' * 40)


def verify_tags_of_indexed_influencers(since=None):
    """
    This script checks and updates scripts to ES influencers.
    :return:
    """

    from debra.models import influencer_add_tag, influencer_remove_tag

    es = Elasticsearch(['198.199.71.215', ])

    tag_ids = list(InfluencersGroup.objects.all().order_by('id').values_list('id', flat=True))
    log.info('Found %s tag ids' % len(tag_ids))

    for tag_id in tag_ids:
        if since is not None and tag_id < since:
            continue

        log.info('Checking tag_id: %s' % tag_id)

        # Collecting ids of influencers from DB
        gr = InfluencersGroup.objects.get(id=tag_id)
        influencers = gr.influencers
        db_ids = [inf.id for inf in influencers]

        # fetching ids of influencers having this id from ES
        es_ids = []
        es_data = scan(
            es,
            query={
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "tag": tag_id
                                }
                            }
                        ]
                    }
                }
            },
            size=200,
        )

        for hit in es_data:
            # print(hit)
            try:
                es_id = hit.get('_id')
                if es_id is not None and es_id not in es_ids:
                    es_ids.append(int(es_id))
            except Exception as e:
                log.error(e)

        log.info('DB ids count: %s, ES ids count: %s' % (len(db_ids), len(es_ids)))
        ids_to_append_tag = []
        ids_to_remove_tag = []

        for i in db_ids:
            if i not in es_ids:
                ids_to_append_tag.append(i)

        for i in es_ids:
            if i not in db_ids:
                ids_to_remove_tag.append(i)

        if len(ids_to_append_tag) > 0:
            log.info('Appending tag to infs: %s' % ids_to_append_tag)

            for inf_id in ids_to_append_tag:
                influencer_add_tag(inf_id, tag_id)

        if len(ids_to_remove_tag) > 0:
            log.info('Removing tag from infs: %s' % ids_to_remove_tag)

            for inf_id in ids_to_remove_tag:
                influencer_remove_tag(inf_id, tag_id)

    log.info('Done.')



def test_last_fetched_correct():
    """
    Checks if platform.last_fetched is being set correctly
    :return:
    """

    from debra.mongo_utils import get_ids_of_performed

    since = datetime.datetime(2016, 6, 9, 0, 0, 0)

    ids_performed = get_ids_of_performed(since)

    log.info('Ids performed: %s' % len(ids_performed))

    result_ids = []

    chunks = [ids_performed[x:x+200] for x in xrange(0, len(ids_performed), 200)]

    for chunk in chunks:
        ids = list(Platform.objects.filter(id__in=chunk, last_fetched__lt=since).values_list('id', flat=True))

        if len(ids) > 0:
            log.info('Found not updated platforms: %s' % ids)
            result_ids.extend(ids)

    return result_ids



def separate_show_on_searches(saved_search_id=None, target_col_id=None):
    """
    Adds influencers from saved query to collection, skipping those with old_show_on_search=True
    """

    from debra.elastic_search_helpers import es_influencer_query_builder_v2

    saved_search = SearchQueryArchive.objects.get(id=saved_search_id)
    log.info('Saved search: %s' % saved_search)

    target_col = InfluencersGroup.objects.get(id=target_col_id)
    log.info('Target collection: %s' % target_col)

    inf_query = es_influencer_query_builder_v2(saved_search.query_json)

    # removing pagination
    inf_query.pop('from')
    inf_query.pop('size')

    # overriding filter -- adding exclusion of old_show_on_search=True and getting show_on_search=True on production
    inf_query['query']['filtered']['filter'] = {
        "and": [
            {
                'term': {
                    'show_on_search': True
                }
            },
            {
                'term': {
                    'blacklisted': False
                }
            },
            {
                'bool': {
                    'must_not': {
                        'term': {
                            'old_show_on_search': True
                        }
                    }
                }
            }
        ]
    }

    log.info(inf_query)

    es = Elasticsearch(['198.199.71.215', ])

    es_ids = set()

    es_data = scan(
        es,
        query=inf_query,
        size=500,
    )

    for hit in es_data:
        # print(hit)
        try:
            es_id = hit.get('_id')
            if es_id is not None:
                es_ids.add(int(es_id))
        except Exception as e:
            log.error(e)

    log.info('Found %s ids' % len(es_ids))

    ctr = 0
    for iid in es_ids:
        target_col.add_influencer(Influencer.objects.get(id=iid))
        ctr += 1

        if ctr % 1000 == 0:
            log.info('Added %s influencers to collection' % ctr)

    log.info('All needed influencers added to collection')


def add_tags_to_influencers_to_new_index(start=0):
    """
    Since tags are now available in a separate index in the new index, we have to copy them now externally.
    Find all collections and influencers in those collections.
    """
    from . import elastic_search_helpers

    coll = InfluencersGroup.objects.all().order_by('id').exclude(owner_brand__domain_name__in=['yahoo.com', 'rozetka.com.ua']).exclude(id=1923)

    for j, c in enumerate(coll[start:]):
        infs = c.influencers
        print("Starting with %d %r" % (j, c))
        for i in infs:
            elastic_search_helpers.influencer_add_tag(i.id, c.id)
            print ("%d Adding INfluencer.id %d to Tag %r" % (j, i.id, c))


def handling_R29_influencers():
    """
    Aug 29th status:
    Currently, we have R29's influencers separately:
        infs = Influencer.objects.filter(source='r29_customer_import')

    But we want to combine them with the rest of the influencers.

    So, here is our algorithm:

    infs.count() = 2542
    plats = Platform.objects.filter(influencer__in=infs, platform_name='Instagram')
    plats_insta = plats.exclude(url_not_found=True)
    plats_insta.count() = 2542

    Our idea is the following:
        a) For a given instagram platform that is in the refinery's separate database
        b) check if we have any other instagram platform elsewhere which is showing up in production and has the same username
        c) then out of these, check which ones are autovalidated => call them autovalidated
        d) rest are not_autvalidated or not_found
        e) Then for autovalidated, check if we have more than one => they are duplicaes, we need to handle them
            e.1) single ones can be put in a collection for QA to go through
                e.1.1) add to collection single_autovalidated
            e.2) if duplicates, put in duplicate_autovalidated => need to check manually first
        f) For not autovalidated
            f.1) if only one =>
            f.2) if more than one =>
        g) for none found (1300 of them)
            g.1) check if there are some in just show_on_search?



    found_plats = {}

    for plat in plats_insta:
        p_usernames = Platform.objects.filter(username=plat.username, platform_name='Instagram').exclude(influencer__in=infs).exclude(url_not_found=True)
        found_plats = []
        for p in p_usernames:
            b = (plat, p, p.influencer)
            found_plats[username].append(b)

    There are 3 cases per username:
    a) there is only one platform for a given username
        => should we connect?
        plat.influencer = p.influencer
    b) there is more than one
        => if only one is on production => pick that one
        => if none is on production => pick the best
    c) there is none
        => just add the influencer for the username to the collection to_process
        add plat to a collection to be processed (extraction for platform names)

    So at this point, we should have an influencer for each platform.
    If this influencer already has a InfluencerBrandMapping object, we're good.
    Else, connect InfluencerBrandMapping for platform.influencer to the newly found influencer.

    Then, we need to index these influencers with their custom data.
    We should also then copy the names and location to the newly connected influencers.

    """
    infs = Influencer.objects.filter(source='r29_customer_import')
    plats = Platform.objects.filter(influencer__in=infs, platform_name='Instagram')
    plats_insta = plats.exclude(url_not_found=True)
    print("Plats : %d " % plats_insta.count())

    collection_1 = "r29_single_autovalidated"
    collection_2 = "r29_duplicate_autovalidated_old_show_on_search"
    collection_3 = "r29_duplicate_autovalidated_rest"
    collection_4 = "r29_found_none"
    collection_5 = "r29_single_non_autovalidated"
    collection_6 = "r29_duplicate_non_autovalidated"


    # stores a dictionary of results
    # found_plats[plat] = [plat1, plat2]
    found_plats_single_autovalidated = {}
    found_plats_single_non_autovalidated = {}
    found_plats_duplicate_autovalidated_old_show_on_search = {}
    found_plats_duplicate_autovalidated_rest = {}
    found_plats_duplicate_non_autovalidated = {}
    none_found = {}

    for plat in plats_insta:
        pq = Platform.objects.filter(username=plat.username, platform_name='Instagram').exclude(influencer__in=infs).exclude(url_not_found=True)
        pq = pq.filter(influencer__show_on_search=True)
        pq_autovalidated = pq.filter(autovalidated=True)
        if pq_autovalidated.count() == 1:
            found_plats_single_autovalidated[plat] = [pq_autovalidated[0]]
            continue
        if pq_autovalidated.count() == 0 and pq.count() == 0:
            none_found[plat] = []
            continue
        if pq.count() == 1 and pq_autovalidated.count() == 0:
            found_plats_single_non_autovalidated[plat] = [pq[0]]
            continue
        if pq.count() > 1 and pq_autovalidated.count() == 0:
            found_plats_duplicate_non_autovalidated[plat] = []
            for p in pq:
                found_plats_duplicate_non_autovalidated[plat].append(p)
            continue
        if pq_autovalidated.count() > 1:
            pq_autovalidated_old_show_on_search = pq_autovalidated.filter(influencer__old_show_on_search=True)
            if pq_autovalidated_old_show_on_search.count() >= 1:
                found_plats_duplicate_autovalidated_old_show_on_search[plat] = []
                for p in pq_autovalidated_old_show_on_search:
                    found_plats_duplicate_autovalidated_old_show_on_search[plat].append(p)
            else:
                found_plats_duplicate_autovalidated_rest[plat] = []
                for p in pq_autovalidated:
                    found_plats_duplicate_autovalidated_rest[plat].append(p)

    return found_plats_single_autovalidated, \
           found_plats_single_non_autovalidated, \
           found_plats_duplicate_autovalidated_old_show_on_search, \
           found_plats_duplicate_autovalidated_rest, \
           found_plats_duplicate_non_autovalidated, \
           none_found

    # found_plats_single_autovalidated => they should be added to "r29_single_autovalidated"
    # found_plats_single_non_autovalidated => should be added to "r29_single_non_autovalidated"
    # found_plats_duplicate_autovalidated_old_show_on_search => should be added to "r29_duplicate_autovalidated_old_show_on_search"
    # found_plats_duplicate_autovalidated_rest => should be added to "r29_duplicate_autovalidated_rest"
    # found_plats_duplicate_non_autovalidated => should be added to "r29_duplicate_non_autovalidated"
    # none_found => should be added to "r29_found_none"
    pass


def copy_popularity_data(source_platform, destination_platform, to_save=False):
    # now we copy the popularitycharts
    source_charts_data = PopularityTimeSeries.objects.filter(platform=source_platform)
    print("Copying popularity charts from %r to %r" % (source_platform, destination_platform))
    print("Got %d items in the charts data from source: %r" % (source_charts_data.count(), source_platform))
    if not to_save:
        return
    for k in source_charts_data:
        k.platform = destination_platform
        k.influencer = destination_platform.influencer
        k.pk = None
        k.save()


def copy_platform_data(source_platform, destination_platform, to_save=False):

    """
    Here we create a clone of the platform object (sans the posts).

    """
    print("Copying stats from Src [%r] to Dst [%r]" % (source_platform, destination_platform))
    destination_platform.validated_handle = source_platform.validated_handle
    destination_platform.num_followers = source_platform.num_followers
    destination_platform.num_followers = source_platform.num_followers

    destination_platform.total_numlikes = source_platform.total_numlikes
    destination_platform.total_numcomments = source_platform.total_numcomments
    destination_platform.total_numshares = source_platform.total_numshares

    destination_platform.avg_numlikes_overall = source_platform.avg_numlikes_overall
    destination_platform.avg_numcomments_overall = source_platform.avg_numcomments_overall
    destination_platform.avg_numshares_overall = source_platform.avg_numshares_overall

    destination_platform.avg_num_impressions = source_platform.avg_num_impressions
    destination_platform.autovalidated = True
    destination_platform.autovalidated_reason = 'copying_from_existing_autovalidated'
    if to_save:
        destination_platform.save()

    print("After copying: num_followers:%d total_numlikes:%d" % (destination_platform.num_followers, destination_platform.total_numlikes))

    copy_popularity_data(source_platform, destination_platform, to_save)

def create_and_copy_platforms_from_influencer(source_influencer, destination_influencer, to_save=False):
    """
    This is one-time thing for R29 but perhaps we can re-use it for later.

    Assume that instagram_url is the same between them.

    For Instagram:
        a) destination_influencer should have a platform
        b) find the platform from source that is not invalid

    Go through each autovalidated platform from source influencer
        -> create a platform if one doesn't already exist in destination
        -> copy the stats
    """

    def pick_with_longest_history(plats):
        max = 0
        p_with_max = None
        for p in plats:
            p_charts_data = PopularityTimeSeries.objects.filter(platform=p)
            if p_charts_data.count() > max:
                p_with_max = p
        return p_with_max



    dst_plats = destination_influencer.platforms().exclude(url_not_found=True)
    # there must be one
    dst_insta = dst_plats.filter(platform_name='Instagram')[0]
    dst_insta_username = dst_insta.username

    social_validated = source_influencer.platforms().exclude(url_not_found=True)
    # must match the username and platform name
    src_instas = social_validated.filter(platform_name='Instagram', username=dst_insta_username)
    best_src_insta = pick_with_longest_history(src_instas)

    copy_popularity_data(best_src_insta, dst_insta, to_save)


    remaining_platform_names = ['Youtube', 'Facebook', 'Pinterest', 'Twitter', 'Gplus']

    social_validated = social_validated.filter(platform_name__in=remaining_platform_names)
    social_validated = social_validated.filter(autovalidated=True)

    for name in remaining_platform_names:
        src_plats = social_validated.filter(platform_name=name)
        best_src_plat = pick_with_longest_history(src_plats)

        if best_src_plat:
            existing_dst_plats = dst_plats.filter(platform_name=name)
            # there should be only one
            if existing_dst_plats:
                dst = existing_dst_plats[0]
            else:
                dst = Platform(influencer=destination_influencer, url=best_src_plat.url, platform_name=name)
                field_name = Influencer.platform_name_to_field.get(name)
                setattr(destination_influencer, field_name, best_src_plat.url)

            copy_platform_data(best_src_plat, dst, to_save)


    # Now, copy the profile picture and score_popularity_overall
    destination_influencer.score_popularity_overall = source_influencer.score_popularity_overall
    destination_influencer.dist_age_0_19 = source_influencer.dist_age_0_19
    destination_influencer.dist_age_20_24 = source_influencer.dist_age_20_24
    destination_influencer.dist_age_25_29 = source_influencer.dist_age_25_29
    destination_influencer.dist_age_30_34 = source_influencer.dist_age_30_34
    destination_influencer.dist_age_35_39 = source_influencer.dist_age_35_39

    if to_save:
        destination_influencer.save()




