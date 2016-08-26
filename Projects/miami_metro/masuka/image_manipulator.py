from celery.decorators import task
from PIL import Image, ImageOps
from django.conf import settings
from boto.cloudfront import CloudFrontConnection
from debra.models import UserProfile, CloudFrontDistribution, BrandJobPost
from django.utils.http import urlquote
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.servers.basehttp import FileWrapper
from django.utils.encoding import smart_str
from debra.forms import UploadImageForm
from debra import helpers as h
from django.shortcuts import render_to_response, redirect, get_object_or_404
from boto.s3.connection import S3Connection
from raven.contrib.django.raven_compat.models import client
import pdb
import mimetypes
import urlparse
import os, errno
import re
import datetime, time
import sys
import urllib
import urllib2
import cStringIO
import logging
import random
import os
from io import BytesIO
from xpathscraper import xbrowser
from django.core.urlresolvers import reverse
from django.core.cache import get_cache

log = logging.getLogger('masuka.image_manipulator')


#####-----< Constants >-----#####
BUCKET_PATH_PREFIX = "https://s3.amazonaws.com/"
NUM_BUCKETS = 20

##Buckets
INFLUENCER_BUCKET = 'influencer-images'
PROFILE_BUCKET = 'profile-images-theshelf'

UPLOAD = True
expires_ = datetime.date.today() + datetime.timedelta(days=(365))
expires = expires_.strftime("%a, %d %b %Y %H:%M:%S GMT")

#bucket_to_cloudfront_map = cache.get('bucket_to_cloudfront_map', {})
cache = get_cache('memcached')

PROFILE_IMAGE_SIZE = 300,300
COVER_IMAGE_SIZE = 600,150
FB_COVER_IMAGE_SIZE = 550,250

IMAGE_SIZES = {
    "size1": (342, 74),
    "size2": (342, 278),
    "size3": (177, 352),
    "size4": (276, 352),
    "size5": (322, 176),
    "size6": (322, 176),
    "size7": (195, 352),
    "size8": (402, 352),
    "size9": (187, 176),
    "size10": (187, 176),
    "profile": PROFILE_IMAGE_SIZE,
    "cover": COVER_IMAGE_SIZE,
}

#####-----</ Constants >-----#####


#####-----< Image Helpers >-----#####
def delete_file(filename):
    try:
        os.remove(filename)
    except OSError:
        print "oops, couldn't delete file %s " % filename
        pass

def thumbnail(img_url, desired_size):
    f1 = urllib.urlopen(img_url)
    im1 = cStringIO.StringIO(f1.read())
    img1 = Image.open(im1)
    img1.thumbnail(desired_size, Image.ANTIALIAS)
    return img1

def transform(img_url, desired_size):
    f1 = urllib.urlopen(img_url)
    im1 = cStringIO.StringIO(f1.read())
    img1 = Image.open(im1)
    img1 = ImageOps.fit(img1, desired_size, Image.ANTIALIAS)
    return img1

def middle_crop(img_url, size):
    '''
    this method crops an image from its center to the supplied size
    @param img_url - url of image to crop
    @param size - the size to crop to
    '''
    f1 = urllib.urlopen(img_url)
    im1 = cStringIO.StringIO(f1.read())
    img = Image.open(im1)

    img = ImageOps.fit(img, size, Image.ANTIALIAS, 0, (0.5, 0.5))
    return img

def feed_transform(img_url):
    '''
    this is different from transform in that we don't have a desired size. We want the feed items to have
    width = 230px but the height is variable, we just want to shrink the image to width 230px while
    maintaining aspect ratio
    '''
    DESIRED_WIDTH = 230
    f1 = urllib.urlopen(img_url)
    im1 = cStringIO.StringIO(f1.read())
    img = Image.open(im1)

    width, height= img.size
    img_ratio = float(width) / float(height)
    desired_height = int(DESIRED_WIDTH / img_ratio)
    img = ImageOps.fit(img, (DESIRED_WIDTH, desired_height), Image.ANTIALIAS)

    return img

def resize_image(img_id, img_url, new_size, resize_method=thumbnail):
    """
    resize an image to a new size
    @param img_id - the unique id for the image
    @param img_url - the url of the image we're resizing
    @param resize_method - the method to apply for resizing (middle_crop, feed_transform, etc.)
    @return the url of the resized image
    """
    # ff = "/tmp/%s_size_%d" % (img_id, new_size[0])
    ff = BytesIO()
    img1 = resize_method(img_url, new_size)
    if img1.mode != 'RGB':
        img1 = img1.convert('RGB')
    img1.save(ff, 'jpeg')

    return ff
#####-----</ Image Helpers >-----#####

#####-----< File / Bucket Helpers >-----#####
def get_connection():
    """
    get an s3 connection
    @return the connection handle
    """
    conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
    return conn

def get_bucket(bucket_name):
    """
    get an s3 bucket
    @param bucket_name - the name of the S3 bucket
    @return the S3 bucket
    """
    conn = get_connection()
    bucket = conn.get_bucket(bucket_name, validate=False)
    return bucket


def save_file_to_s3(bucket, file_path, img_id, image_name):
    """
    save a given file to S3
    @param bucket - the S3 bucket to save the file to
    @param file_path - the path to the temporary file to save to S3
    @param img_id - the id of the image (usually this will be the user id / product id etc)
    @param image_name - the name of the image to save (i.e. collage_image_1, profile_image, etc.)
    @return the name of the image on s3 (this goes after the BUCKET PATH PREFIX and bucket name)
    """
    new_key_name = str(img_id)+image_name+'.jpg.small.jpg'
    new_key = bucket.new_key(new_key_name)
    if type(file_path) == BytesIO:
        file_path.seek(0)
        new_key.set_contents_from_string(
            file_path.read(),
            headers={'Content-Type': 'image/jpeg'}
        )
    else:
        # SHOULD NOT BE USED !!!
        new_key.set_contents_from_filename(file_path)
        delete_file(file_path)
    new_key.set_acl('public-read')

    return new_key_name

def absolute_url_to_s3_file(bucket, s3_filename):
    """
    :param bucket: string representing the 'folder' the file is stored in in s3
    :param s3_filename: string representing the name of the file in s3
    :return: ``str`` containing the absolute url to the file in s3
    """
    return BUCKET_PATH_PREFIX + bucket + "/" + s3_filename
#####-----</ File / Bucket Helpers >-----#####



@login_required
def image_upload(request):
    print "Got inside image_upload. method %s " % request.method
    next_redirect = redirect(request.GET.get('next', reverse('debra.shelf_views.about_me', args=(request.user.userprofile.id,))))
    if request.method == 'POST':
        f = UploadImageForm(request.POST, request.FILES)
        print "GOt form content %s " % f
        if f.is_valid():
            parsed = urlparse.urlparse(request.build_absolute_uri())
            params = urlparse.parse_qs(parsed.query)

            img_file = f.cleaned_data['image_file']
            x1 = int(f.cleaned_data['x1'])
            y1 = int(f.cleaned_data['y1'])
            x2 = int(f.cleaned_data['x2'])
            y2 = int(f.cleaned_data['y2'])
            scaling = f.cleaned_data['scaling_factor']

            #map the scaling factor across each of the coordinates
            x1,y1,x2,y2 = [int(scaling * val) for val in [x1,y1,x2,y2]]

            #im = Image.open(StringIO(img_file.read()))
            #im.save('x.jpg')
            im1 = cStringIO.StringIO(img_file.read())
            img1 = Image.open(im1)
            #box = (x1, y1, x2, y2)
            print "x1 %s y1 %s x2 %s y2 %s " % (x1, y1, x2, y2)

            campaign = None
            user = None
            brand = None
            if "brand" in params.keys():
                brand = request.visitor["brand"]
                img_id = brand.id
                user = None
            elif "campaign" in params.keys():
                campaign = BrandJobPost.objects.get(id=int(request.GET.get('campaign')))
                brand = campaign.creator
                img_id = str(campaign.id) + '_campaign'
            else:
                user = request.user
                img_id = user.id
                brand = None

            bucket = get_bucket('profile-images-theshelf')

            if 'profile_img' in params.keys():
                #file_path = settings.MEDIA_ROOT + "/raja.jpg"
                # first save to /tmp (if save=0), and then, save to s3 (if save=1)
                # file_path = "/tmp/%s_profile_image" % img_id
                region_contents = BytesIO()
                region = img1.crop((x1, y1, x2, y2))
                region.convert('RGB').save(region_contents, 'jpeg')

                if 'save' in params.keys():
                    try:
                        save_flag = bool(int(params['save'][0]))
                        if not save_flag:
                            return HttpResponse()
                    except:
                        pass

                image_name = ''
                if 'cover_img' in params.keys():
                    image_name = str(img_id) + '_cover_img.jpg'
                    new_key = bucket.new_key(image_name)
                else:
                    image_name = str(img_id) + '_profile_img.jpg'
                    new_key = bucket.new_key(image_name)
                region_contents.seek(0)
                new_key.set_contents_from_string(
                    region_contents.read(), headers={'Content-Type': 'image/jpeg'})
                new_key.set_acl('public-read')

                if user:
                    prof = user.get_profile()
                path = ""
                if 'cover_img' in params.keys():
                    if brand:
                        brand.cover_img_url = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + image_name
                        path = brand.cover_img_url
                        resize_profile_images_brand(brand, 12)
                    else:
                        prof.cover_img_url = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + image_name
                        path = prof.cover_img_url
                        resize_profile_images(user, 12)
                else:
                    if campaign:
                        campaign.profile_img_url = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + image_name
                        path = campaign.profile_img_url
                        resize_profile_images_brand(campaign, 11)
                    elif brand:
                        brand.profile_img_url = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + image_name
                        path = brand.profile_img_url
                        resize_profile_images_brand(brand, 11)
                    else:
                        prof.profile_img_url = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + image_name
                        path = prof.profile_img_url
                        resize_profile_images(user, 11)
                if user:
                    prof.save()
                elif campaign:
                    campaign.save()
                elif brand:
                    brand.save()

                return HttpResponse(path)

            if 'collage_image' in params.keys():
                collage_image_id = params['collage_image'][0]
                # file_path = "/tmp/%s_collage_image_%s" % (user.id, collage_image_id)
                region_contents = BytesIO()
                region = img1.crop((x1, y1, x2, y2))
                region.save(region_contents, 'jpeg')
                print "collage image_id %s " % collage_image_id
                new_key = bucket.new_key(str(user.id)+'_collage_'+str(collage_image_id) + '.jpg')
                region_contents.seek(0)
                new_key.set_contents_from_string(
                    region_contents.read(),
                    headers={'Content-Type': 'image/jpeg'})
                new_key.set_acl('public-read')

                prof = user.get_profile()
                img_path = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '1':
                    prof.image1 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '2':
                    prof.image2 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '3':
                    prof.image3 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '4':
                    prof.image4 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '5':
                    prof.image5 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '6':
                    prof.image6 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '7':
                    prof.image7 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '8':
                    prof.image8 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '9':
                    prof.image9 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                if collage_image_id == '10':
                    prof.image10 = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user.id)+'_collage_'+str(collage_image_id) +'.jpg'
                prof.save()
                resize_profile_images(user, int(collage_image_id))
                return HttpResponse()

            h.send_mandrill_email(message_name='image_error', tpl_vars={
                'user': request.user,
                'request_params': request.GET,
                'problem': "Invalid request parameters"
            })
            return HttpResponse()
        else:
            h.send_mandrill_email(message_name='image_error', tpl_vars={
                'user': request.user,
                'request_params': '%r' % request.GET,
                'problem': "Image upload form was not valid"
            })
            client.captureMessage('Invalid image upload form %s %r' % request.user, f)
            return HttpResponse()
    else:
        h.send_mandrill_email(message_name='image_error', tpl_vars={
            'user': request.user,
            'request_params': '%r' % request.GET,
            'problem': "User made GET request instead of POST"
        })
        client.captureMessage('GET instead of post %s' % request.user)
        return HttpResponse()


@login_required
def upload_campaign_cover(request):
    from debra.models import BrandJobPost
    f = UploadImageForm(request.POST, request.FILES)
    if f.is_valid():
        img_file = f.cleaned_data['image_file']
        x1 = int(f.cleaned_data['x1'])
        y1 = int(f.cleaned_data['y1'])
        x2 = int(f.cleaned_data['x2'])
        y2 = int(f.cleaned_data['y2'])
        scaling = f.cleaned_data['scaling_factor']

        x1,y1,x2,y2 = [int(scaling * val) for val in [x1,y1,x2,y2]]

        im1 = cStringIO.StringIO(img_file.read())
        img1 = Image.open(im1)

        bucket = get_bucket('campaign-covers')

        base_brand = request.visitor["base_brand"]
        brand = request.visitor["brand"]
        try:
            campaign_id = int(request.POST.get('campaign_id'))
        except:
            campaign_id = 0

        tmp_key = 'tmp_{}_{}_{}_campaign_cover'.format(
            brand.id, base_brand.id, campaign_id)

        region = img1.crop((x1, y1, x2, y2))

        region_contents = BytesIO()
        region.convert('RGB').save(region_contents, 'jpeg')
        region_contents.seek(0)

        new_key = bucket.new_key(tmp_key)
        new_key.set_contents_from_string(
            region_contents.read(), headers={'Content-Type': 'image/jpeg'})
        new_key.set_acl('public-read')

        file_url = os.path.join(BUCKET_PATH_PREFIX, 'campaign-covers', tmp_key)

        return HttpResponse(file_url)
    return HttpResponseBadRequest()


def reassign_campaign_cover(campaign_id):
    from debra.models import BrandJobPost

    if type(campaign_id) == int:
        campaign = BrandJobPost.objects.get(id=campaign_id)
    else:
        campaign = campaign_id
    brand_id, base_brand_id, job_id = campaign.creator_id, campaign.oryg_creator_id, campaign.id
    bucket = get_bucket('campaign-covers')

    old_key = 'tmp_{}_{}_{}_campaign_cover'.format(
        brand_id, base_brand_id, job_id)
    # old_key = '%i_%i_tmp_cover_img.jpg' % (brand_id, base_brand_id)
    new_key = '{}_{}_{}_cover_img.jpg'.format(brand_id, base_brand_id, job_id)

    file_url = os.path.join(
        BUCKET_PATH_PREFIX, 'campaign-covers/', new_key)
    try:
        bucket.copy_key(new_key, 'campaign-covers', old_key)
        bucket.delete_key(old_key)
        new_key_obj = bucket.get_key(new_key)
        new_key_obj.set_acl('public-read')
        campaign.cover_img_url = file_url
        campaign.save()
    except Exception as e:
        print "Bucket key copy error?", e


def resize_profile_images(user, index=None, resize_method=thumbnail):
    '''
    Users may upload large images for their profiles. This function re-saves them into small sizes
    for the trendsetter page.
    '''
    prof = user.get_profile()
    bucket = get_bucket(PROFILE_BUCKET)

    #array's first element is None because image indexes start with 1
    sizes_list = [None, IMAGE_SIZES["size1"], IMAGE_SIZES["size2"],
                  IMAGE_SIZES["size3"], IMAGE_SIZES["size4"],
                  IMAGE_SIZES["size5"], IMAGE_SIZES["size6"],
                  IMAGE_SIZES["size7"], IMAGE_SIZES["size8"],
                  IMAGE_SIZES["size9"], IMAGE_SIZES["size10"],
                  PROFILE_IMAGE_SIZE, COVER_IMAGE_SIZE]
    prof_images = [None, prof.image1, prof.image2, prof.image3, prof.image4,
                   prof.image5, prof.image6, prof.image7, prof.image8,
                   prof.image9, prof.image10, prof.profile_img_url,
                   prof.cover_img_url]
    img_types = [None, '_collage_1', '_collage_2', '_collage_3', '_collage_4',
                 '_collage_5', '_collage_6', '_collage_7', '_collage_8',
                 '_collage_9', '_collage_10', '_profile_img', '_cover_img']
    #if an index is specified, we do this only for that image url
    if index:
        size = sizes_list[index]
        img_url = prof_images[index]
        img_type = img_types[index]
        if img_url:
            ff = resize_image(user.id, img_url, size, resize_method=resize_method)
            save_file_to_s3(bucket, ff, user.id, img_type)
        return

    #if no index is provided, we'll do it for all images
    for i,size in enumerate(sizes_list):
        img_url = prof_images[i]
        img_type = img_types[i]
        if img_url:
            ff = resize_image(user.id, img_url, size)
            save_file_to_s3(bucket, ff, user.id, img_type)

    prof.save()
    return

def resize_profile_images_brand(brand, index=None, resize_method=thumbnail):
    '''
    Users may upload large images for their profiles. This function re-saves them into small sizes
    for the trendsetter page.
    '''
    bucket = get_bucket(PROFILE_BUCKET)

    #array's first element is None because image indexes start with 1
    sizes_list = [None, IMAGE_SIZES["size1"], IMAGE_SIZES["size2"],
                  IMAGE_SIZES["size3"], IMAGE_SIZES["size4"],
                  IMAGE_SIZES["size5"], IMAGE_SIZES["size6"],
                  IMAGE_SIZES["size7"], IMAGE_SIZES["size8"],
                  IMAGE_SIZES["size9"], IMAGE_SIZES["size10"],
                  PROFILE_IMAGE_SIZE, COVER_IMAGE_SIZE]
    prof_images = [None, None, None, None, None,
                   None, None, None, None,
                   None, None, brand.profile_img_url,
                   brand.cover_img_url]
    img_types = [None, '_collage_1', '_collage_2', '_collage_3', '_collage_4',
                 '_collage_5', '_collage_6', '_collage_7', '_collage_8',
                 '_collage_9', '_collage_10', '_profile_img', '_cover_img']
    #if an index is specified, we do this only for that image url
    if index:
        size = sizes_list[index]
        img_url = prof_images[index]
        img_type = img_types[index]
        if img_url:
            ff = resize_image(brand.id, img_url, size, resize_method=resize_method)
            save_file_to_s3(bucket, ff, brand.id, img_type)
        return

    #if no index is provided, we'll do it for all images
    for i,size in enumerate(sizes_list):
        img_url = prof_images[i]
        img_type = img_types[i]
        if img_url:
            ff = resize_image(brand.id, img_url, size)
            save_file_to_s3(bucket, ff, brand.id, img_type)

    brand.save()
    return


def save_external_profile_image_to_s3(user_profile):
    '''
    Saves the image pointed by the img_url to S3 (and .small version as well)
    '''
    try:
        user_profile.profile_img_url = BUCKET_PATH_PREFIX + 'profile-images-theshelf/' + str(user_profile.user.id) + '_profile_img.jpg'
        user_profile.save()
        resize_profile_images(user_profile.user, index=11, resize_method=middle_crop)
    except:
        print "oops, had problem with %s for profile %s, exception %s" % (user_profile.profile_img_url, user_profile, str(sys.exc_info()))


def save_social_images_to_s3(platform):
    """
    given a Platform, save it's profile_img and cover_img to s3
    @param platform - the Platform object that we want to store image data to s3 for
    @return the platform who's data was saved to s3
    """
    bucket = get_bucket(INFLUENCER_BUCKET)

    try:
        # new update: we shouldn't re-size the profile images if they are smaller than 200px

        f1 = urllib.urlopen(platform.profile_img_url)
        im1 = cStringIO.StringIO(f1.read())
        img = Image.open(im1)
        if img.size[0] < 200:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            profile = "/tmp/%s_size_%d" % (platform.id, img.size[0])
            img.save(profile, 'jpeg')
        else:
            profile = resize_image(platform.id, platform.profile_img_url, PROFILE_IMAGE_SIZE, resize_method=middle_crop)
        s3_profile = save_file_to_s3(bucket, profile, platform.id, 'profile_image')
        platform.profile_img_url = absolute_url_to_s3_file(INFLUENCER_BUCKET, s3_profile)
        platform.save()
    except:
        print "Problem saving profile image for platform: %s, url %s" % (platform, platform.profile_img_url)
        pass

    try:
        cover = resize_image(platform.id, platform.cover_img_url, FB_COVER_IMAGE_SIZE, resize_method=middle_crop)
        s3_cover = save_file_to_s3(bucket, cover, platform.id, 'cover_image')
        platform.cover_img_url = absolute_url_to_s3_file(INFLUENCER_BUCKET, s3_cover)
        platform.save()
    except:
        print "Problem saving cover image for platform: %s, url: %s" % (platform, platform.cover_img_url)
        pass
    return platform


def create_and_store_thumbnails(wishlist_item, img_url, bucket, bucket_index, FORCE_PUSH=False):
    '''
    store 5 copies of the wishlist's image in our S3 bucket
        - feed view
        - shelf view
        - thumbnail view
        - original
        - compressed feed view
    '''
    IMAGE_TYPE_MAPPING = {
        'shelf_view': {
            'tmp_name': '/tmp/%s_for_shelf.jpg' % wishlist_item.id,
            'key_name_prefix' : 'v2-img-for-shelf-',
            'size': (120, 120),
            'wishlist_field': 'img_url_shelf_view',
        },
        'feed_view': {
            'tmp_name': '/tmp/%s_for_feed.jpg' % wishlist_item.id,
            'key_name_prefix' : 'v2-img-for-feed-',
            'size': None, #we use special function for feed view
            'wishlist_field': 'img_url_feed_view',
        },
        'compressed_feed_view': {
            'tmp_name': '/tmp/%s_compressed_for_feed.jpg' % wishlist_item.id,
            'key_name_prefix' : 'v2-img-for-feed-compressed-',
            'size': None, #we use special function for feed view
            'wishlist_field': 'img_url_feed_compressed',
        },
        'panel_view': {
            'tmp_name': '/tmp/%s_for_panel.jpg' % wishlist_item.id,
            'key_name_prefix': 'v2-img-for-panel-',
            'size': (450, 450),
            'wishlist_field': 'img_url_panel_view',
        },
        'thumbnail_view': {
            'tmp_name': '/tmp/%s_for_thumbnail.jpg' % wishlist_item.id,
            'key_name_prefix': 'v2-img-for-thumbnail-',
            'size': (150, 150),
            'wishlist_field': 'img_url_thumbnail_view',
        },
        'original_view': {
            'tmp_name': '/tmp/%s_for_original.jpg' % wishlist_item.id,
            'key_name_prefix' : '',
            'size': None,
            'wishlist_field' : 'img_url_original',
        }
    }

    for key in IMAGE_TYPE_MAPPING.keys():
        mapping = IMAGE_TYPE_MAPPING[key]
        size = mapping['size']
        key_name = mapping['key_name_prefix'] + img_url.replace('/', '_')
        new_key = bucket.new_key(key_name)
        tmp_name = mapping['tmp_name']
        print "[%s] [%s] [%s] " % (size, key_name, tmp_name)

        # special handling for keeping original images in our S3
        if key == "original_view":
            f1 = urllib.urlopen(img_url)
            im1 = cStringIO.StringIO(f1.read())
            img1 = Image.open(im1)
        else:
            if size:
                img1 = thumbnail(img_url, size)
            else:
                img1 = feed_transform(img_url)

        img1.save(tmp_name, 'jpeg', quality=50 if key == 'compressed_feed_view' else 75)

        new_key.set_contents_from_filename(tmp_name)
        new_key.set_acl('public-read', headers={'Cache-Control': 'max-age=31536000', 'Expires': expires})
        log.debug("Uploading image %s to S3...." % (tmp_name))
        #log.debug("updating URL for key %s to %s " % (key_name, get_distribution(bucket) + '/' + urlquote(key_name)))
        setattr(wishlist_item, mapping['wishlist_field'], get_distribution(bucket) + '/' + urlquote(key_name))
        delete_file(tmp_name)
    wishlist_item.save()



def get_distribution(bucket):
    val = CloudFrontDistribution.get(bucket.name)
    print("Value = %s for bucket= %s" % (val, bucket.name))
    return val



@task(name="masuka.image_manipulator.create_images_for_wishlist_item")
def create_images_for_wishlist_item(w, bucket=None):
    if w.img_url_shelf_view and 'cloudfront' in w.img_url_shelf_view:
        if w.img_url_feed_view and 'cloudfront' in w.img_url_feed_view:
            if w.img_url_panel_view and 'cloudfront' in w.img_url_panel_view:
                log.debug("w %s is good " % w)
                #return
                pass
    index = w.id % NUM_BUCKETS
    if not bucket:
        conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
        log.debug("Creating bucket %d " % index)
        bucket = conn.create_bucket(str(index)+'-theshelf-item-images-bucket')
        #log.debug("distribtion %s " % get_distribution(bucket))
        bucket.set_acl('public-read')

    #print "Trying wishlist %s " % w
    img_url = w.img_url
    if img_url == '':
        #print "Updating image_url since it is empty "
        img_url = w.product_model.img_url
    if not '//' in img_url:
        #print "Updating image_url %s since it doesn't have http:// " % img_url
        img_url = 'http://' + '/'+img_url
    elif not 'http' in img_url:
        #print "Updating image_url %s since it is doesn't have http " % img_url
        img_url = 'http:' + img_url
    log.debug("OK, img_url so far: %s, trying to fetch it and see if this causes a problem " % img_url)
    try:
        f1 = urllib.urlopen(img_url)
        im1 = cStringIO.StringIO(f1.read())
        img1 = Image.open(im1)
    except:
        print "ran out of solutions, so skipping this item %s " % w
        return
    #print "Final img_url %s " % img_url
    w.save()

    try:
        #print "Using bucket %d " % index
        create_and_store_thumbnails(w, img_url, bucket, index,FORCE_PUSH=True)
        w.save()
    except:
        log.exception('While create_and_store_thumbnails')
        #raise
        pass


@task(name="masuka.image_manipulator.create_shelf_share_screenshot")
def create_shelf_share_screenshot(request, user=0):
    image_data = re.search(r'base64,(.*)', request.POST.get('image')).group(1)

    conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
    bucket = conn.get_bucket('blogger-collages-theshelf', validate=False)
    epoch = int(time.time())
    key_name = 'shelf-shareable-screenshot-'+str(user) + '-' + str(epoch) + '.png'
    filename = '/tmp/shelf_' + str(user) +'.png'

    temp = cStringIO.StringIO(image_data.decode('base64'))
    img = Image.open(temp)
    img.save(filename, 'png')

    new_key = bucket.new_key(key_name)
    new_key.set_contents_from_filename(filename)
    new_key.set_acl('public-read')

    img_url = 'https://s3.amazonaws.com/blogger-collages-theshelf/' + urlquote(key_name)

    return HttpResponse(content=img_url, status=200)

def download_image(request, user=0):
    '''
    serve a download to the user for the given image (in the GET parameters)
    '''
    file = urllib.urlopen(request.GET.get('img'))
    response = HttpResponse(file.read(), content_type='image/png')
    response['Content-Disposition'] = 'attachment; filename=blogger_collage.png'

    return response


def emulate_login(xb, site_url):
    xb.load_url(site_url)

    login_btn = xb.el_by_xpath('//a[@data-popup-type="login"]')
    login_btn.click()
    time.sleep(1)

    email_field = xb.el_by_xpath('//div[contains(@class,"login-popup")]//input[@id="id_email"]')
    password_field = xb.el_by_xpath('//div[contains(@class,"login-popup")]//input[@id="id_password"]')

    email_field.send_keys('atul@theshelf.com')
    print "Email entered"
    password_field.send_keys('duncan3064')
    print "Password entered"
    submit = xb.el_by_xpath('//input[@id="login_submit"]')
    time.sleep(10)
    password_field.submit()
    time.sleep(5)
    print "Done, now at %s" % xb.driver.current_url

@task(name="masuka.image_manipulator.create_user_collage_images")
def create_user_collage_images():
    '''
    Called periodically to create collage image screenshot for users that have a collage ready
    ---using currently for blogger outreach
    '''
    profs = UserProfile.objects.filter(collage_img_url__isnull=True, blog_page__isnull=False)
    if not profs.exists():
        return
    headless_display = settings.AUTOCREATE_HEADLESS_DISPLAY
    xb = xbrowser.XBrowser(headless_display=headless_display, width=1200, height=800)
    host = 'http://127.0.0.1:8000' if settings.DEBUG else 'http://app.theshelf.com'
    view = reverse('debra.account_views.home', args=())
    print host, view, host+view
    # first we need to login
    emulate_login(xb, host+view)

    for p in profs:
        print "Checking %s" % p
        if not p.has_collage:
            print "%s doesn't have the collage ready " % p
            continue
        admin_url = reverse('upgrade_admin:admin_user_details', args=(p.id,))
        print host+admin_url
        xb.load_url(host+admin_url)
        time.sleep(30)
        ## now invoke javascript function 'generate_screenshot()'
        xb.execute_jsfun('Admin.generate_collage_screenshot')
        time.sleep(120)

    # after everything is done, cleanup
    xb.cleanup()

def create_profile_collage_screenshot(request, user=0):
    image_data = re.search(r'base64,(.*)', request.POST.get('image')).group(1)
    prof = UserProfile.objects.get(id=user)
    conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
    bucket = conn.get_bucket('blogger-collages-theshelf', validate=False)
    ## now save it in S3
    filename = '/tmp/collage-img-'+str(prof.id) + '.png'

    key_name = 'profile_collage_' + str(prof.id) +'.png'
    temp = cStringIO.StringIO(image_data.decode('base64'))
    img = Image.open(temp)
    img.save(filename, 'png')

    new_key = bucket.new_key(key_name)
    new_key.set_contents_from_filename(filename)
    new_key.set_acl('public-read')
    img_url = 'https://s3.amazonaws.com/blogger-collages-theshelf/' + urlquote(key_name)

    prof.collage_img_url = img_url
    prof.save()

    return HttpResponse(content=img_url, status=200)


def upload_post_image(post):
    """Finds and uploads eligible image, returns True if success"""
    img_urls = post.find_eligible_images(stop_after_first=True)
    if len(img_urls) > 0:
        opener = urllib2.build_opener()
        try:
            chunk = opener.open(img_urls[0]).read()
        except Exception:
            opener.addheaders = [('User-agent', 'Mozilla/5.0')]
            chunk = opener.open(img_urls[0]).read()

        stringio = cStringIO.StringIO(chunk)
        img_data = Image.open(stringio)

        # new_size = (500, int(img_data.size[1]/(img_data.size[0]/500.0)))
        # img_data.thumbnail(new_size)

        # tmp_name = "/tmp/%s_blog_image.jpg" % post.id
        # image_name = str(post.id) + '_post_img.jpg'

        # img_data.save(tmp_name)

        # bucket = get_bucket('blog-post-images-theshelf')
        # new_key = bucket.new_key(image_name)
        # new_key.set_contents_from_filename(tmp_name)
        # new_key.set_acl('public-read')
        # uploaded_url = BUCKET_PATH_PREFIX + 'blog-post-images-theshelf/' + image_name
        post.post_image = img_urls[0]
        post.post_image_width = img_data.size[0]
        post.post_image_height = img_data.size[1]
        post.save()
        return True
    return False


@task(name="masuka.image_manipulator.upload_post_image_task")
def upload_post_image_task(post_id):
    from debra.models import Posts
    post = Posts.objects.get(id=post_id)
    upload_post_image(post)
