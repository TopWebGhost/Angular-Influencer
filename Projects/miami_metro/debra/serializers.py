import datetime
import json
import HTMLParser
import copy
import time
import re
import hashlib
import random
import base64
import operator

from collections import defaultdict, OrderedDict
from numbers import Number
from BeautifulSoup import BeautifulSoup
from PIL import Image
from io import BytesIO

from rest_framework import serializers, pagination

from django.core.urlresolvers import reverse
from django.core.cache import get_cache
from django.conf import settings

from debra import models, constants
from debra.decorators import include_template, editable_field

html_parser = HTMLParser.HTMLParser()
mc_cache = get_cache('memcached')
redis_cache = get_cache('redis')


def unescape(x):
    return None if x is None else html_parser.unescape(x)


def transform_customer_comments(obj=None, value=None):
    value = value or obj.influencer.customer_comments
    f = lambda x: x['text'] + " (by <strong>{}</strong>, at <i style='font-style: italic;'>{}</i>)".format(
        x['author_email'], x['timestamp'].strftime('%Y/%m/%d %H:%M'))
    return "<br /><br />".join(map(f, value))


def transform_edit_history(obj, value, field, postprocess=None):
    edits = obj.edit_history.filter(field=field)
    if edits:
        latest = edits.latest('id')
        prev = latest.prev_value
        curr = latest.curr_value
        if not prev:
            prev = "unknown"
        if not curr:
            curr = "unknown"
        if postprocess:
            try:
                curr = postprocess(curr)
            except:
                pass
            try:
                prev = postprocess(prev)
            except:
                pass
        print curr, prev
        return "<span class='debug_incorrect'>%s</span><br/><span class='debug_correct'>%s</span>" % (prev, curr)
    else:
        return value


def transform_msg(value):
    orig_msg = ConversationSerializer.get_original_message(value)
    parts = ConversationSerializer.get_message_parts(orig_msg)

    payload = parts['decoded_payload']

    return {
        'body': payload.replace('\n', ''),
        'subject': orig_msg["subject"],
    }


class CachableSerializerMixin(object):

    @classmethod
    def cache_serializer(cls):
        try:
            cls._cache_serializer
        except AttributeError:
            cls._cache_serializer = CacheSerializer(cls)
        return cls._cache_serializer


class SerializerContextMixin(object):

    def is_fake_data_account(self, obj):
        try:
            return self.context.get('brand').flag_show_dummy_data
        except AttributeError:
            return False

    def get_brand(self, obj):
        try:
            return self.context.get('brand')
        except AttributeError:
            return None

    def get_request(self, obj):
        try:
            return self.context.get('request')
        except AttributeError:
            return None

    def get_user(self, obj):
        try:
            return self.get_request(obj).user
        except AttributeError:
            return None

    def is_public(self, obj):
        try:
            return self.get_user(obj).is_authenticated
        except AttributeError:
            return True


class ConversationSerializer(serializers.ModelSerializer):
    img = serializers.SerializerMethodField('get_img')
    author = serializers.SerializerMethodField('get_author')
    events = serializers.SerializerMethodField('get_events')
    collection = serializers.SerializerMethodField('get_is_collection')
    campaign = serializers.SerializerMethodField('get_is_campaign')
    attachments = serializers.SerializerMethodField('get_attachments')
    events_url = serializers.SerializerMethodField('get_events_url')

    class Meta:
        model = models.MailProxyMessage
        fields = (
            'id', 'msg', 'ts', 'direction', 'type', 'img', 'author', # 'events',
            'collection', 'campaign', 'attachments', 'events_url',
        )

    @staticmethod
    def get_original_message(value):
        from email import message_from_string
        encoding = re.findall("charset=(.*?);", value)
        if encoding:
            encoding = encoding[0]
        else:
            encoding = 'utf-8'
        try:
            encoded_msg = value.encode(encoding)
        except LookupError:
            encoded_msg = value.encode('utf-8', errors='ignore')
        return message_from_string(encoded_msg)

    @staticmethod
    def get_message_parts(msg):
        from debra.helpers import guess_encoding

        inline_image_parts = []
        payloads = []
        html = []
        plain = []
        inline_images = {}
        for part in msg.walk():
            if part.is_multipart():
                continue
            if part.get_content_type().startswith('text'):
                payload = part.get_payload(decode=True)
                payloads.append(payload)
                if part.get_content_type() == 'text/html':
                    html.append(payload)
                elif part.get_content_type() == 'text/plain':
                    plain.append(payload)
            elif part.get_content_type().startswith('image'):
                inline_image_parts.append(part)

        if html:
            res = html[0]
        elif plain:
            res = plain[0]
        else:
            res = payloads[0]

        encoding, decoded_payload = guess_encoding(res)

        if html:
            for part in inline_image_parts:
                cid = part.get('Content-ID')
                if not cid:
                    continue
                cid = cid.strip('<>')
                content_type, content = part.get_content_type(), part.get_payload()
                print content_type
                if content_type == 'image/tiff':
                    content_type = 'image/jpeg'
                    im = Image.open(BytesIO(base64.b64decode(content)))
                    output = BytesIO()
                    im.save(output, 'JPEG')
                    content = base64.b64encode(output.getvalue())
                inline_images[cid] = (content_type, content)

            soup = BeautifulSoup(decoded_payload)
            for img in soup.findAll('img', src=re.compile(r'^cid:')):
                try:
                    print img['src']
                    t = time.time()
                    cid = img['src'].replace('cid:', '')
                    img['src'] = ''
                    img.attrs.append(('cid', cid))
                    img.attrs.append(('lazy-inline-image', ''))
                    print 'time', time.time() - t
                except KeyError:
                    pass
            decoded_payload = soup.renderContents(None)

        return {
            'payload': res,
            'decoded_payload': decoded_payload,
            'encoding': encoding,
            'html': html,
            'inline_images': inline_images,
        }

    def transform_ts(self, obj, value):
        ts = obj.ts
        try:
            tz = obj.thread.brand.get_owner_user_profile().get_setting(
                'timezone')
            ts += datetime.timedelta(hours=int(tz))
        except:
            pass
        return ts

    def transform_msg(self, obj, value):
        return transform_msg(value)

    def get_events_url(self, obj):
        return reverse(
            'debra.job_posts_views.get_message_events',
            args=(obj.id,)
        )

    def get_img(self, obj):
        if obj.direction == models.MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER:
            return None
        if obj.direction == models.MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND:
            return obj.thread.influencer.profile_pic

    def get_author(self, obj):
        if obj.direction == models.MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER:
            return obj.thread.brand.name
        if obj.direction == models.MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND:
            return obj.thread.influencer.name

    def get_events(self, obj):
        t = time.time()
        if obj.type != models.MailProxyMessage.TYPE_EMAIL:
            return []
        events = models.MailProxyMessage.objects.filter(
            mandrill_id=obj.mandrill_id
        ).exclude(
            type=models.MailProxyMessage.TYPE_EMAIL
        ).order_by(
            'ts'
        ).values('type', 'ts')
        events = list(events)
        print '* getting events:', time.time() - t
        return events
        # events = models.MailProxyMessage.objects.filter(
        #     mandrill_id=obj.mandrill_id)
        # events = events.exclude(type=models.MailProxyMessage.TYPE_EMAIL)
        # events = events.order_by('ts')
        # return ConversationSerializer(events, many=True).data

    def get_is_campaign(self, obj):
        try:
            return obj.thread.candidate_mapping.all()[0].job.title
        except:
            return None

    def get_is_collection(self, obj):
        try:
            return obj.thread.mapping.all()[0].group.name
        except:
            return None

    def get_attachments(self, obj):
        try:
            return obj.attachments
        except:
            return None


class ConversationNoEventsSerializer(ConversationSerializer):
    class Meta:
        model = models.MailProxyMessage
        fields = (
            'id', 'msg', 'ts', 'direction', 'type', 'img', 'author',
            'collection', 'campaign'
        )


class ConversationContentSerializer(ConversationSerializer):
    class Meta:
        model = models.MailProxyMessage
        fields = ('id', 'msg',)    


class BrandsSerializer(serializers.ModelSerializer):

    date_edited = serializers.DateTimeField(source="date_edited", format="%x")
    categories = serializers.SlugRelatedField(many=True, slug_field='name')
    similar_brands = serializers.SlugRelatedField(many=True, slug_field='name')

    class Meta:
        model = models.Brands
        fields = (
            'id', 'date_edited', 'name', 'domain_name', 'blacklisted',
            'products_count', 'icon_id', 'is_active', 'blacklist_reason',
            'description', 'date_edited', 'brand_type', 'categories',
            'similar_brands'
        )

    def transform_date_edited(self, obj, value):
        return value or "Not edited"

    def transform_description(self, obj, value):
        try:
            return obj.userprofile.aboutme
        except models.UserProfile.DoesNotExist:
            return obj.description

    def transform_blacklist_reason(self, obj, value):
        if value:
            reasons = dict(models.Brands.BLACKLIST_REASONS)
            return reasons.get(value, 'unknown')
        else:
            return value

    def transform_brand_type(self, obj, value):
        if value:
            reasons = dict(models.Brands.BRAND_TYPES)
            return reasons.get(value, 'unknown')
        else:
            return value


class PlatformSerializer(CachableSerializerMixin, serializers.ModelSerializer):

    show_on_feed = serializers.SerializerMethodField('is_visible_on_feed')

    class Meta:
        model = models.Platform
        fields = (
            'id', 'num_followers', 'posting_rate', 'numposts',
            'avg_numcomments_overall', 'avg_numshares_overall',
            'avg_numlikes_overall', 'url', 'platform_name', 'show_on_feed',
            'total_numlikes',
        )

    def is_visible_on_feed(self, obj):
        return obj.platform_name in (
            "Twitter", "Facebook", "Instagram", "Pinterest", "Youtube")


class PopularityTimeSeriesSerializer(CachableSerializerMixin,
        serializers.ModelSerializer):

    class Meta:
        model = models.PopularityTimeSeries
        fields = (
            'id', 'snapshot_date', 'platform', 'num_followers', 'num_comments',
        )


class MailProxySubjectSerializer(CachableSerializerMixin,
        serializers.ModelSerializer):
    subject = serializers.Field(source='subject')
    
    class Meta:
        model = models.MailProxy
        fields = ('subject',)


class MailProxyCountsSerializer(CachableSerializerMixin,
        serializers.Serializer):

    opened_count = serializers.Field(source='agr_opened_count')
    emails_count = serializers.Field(source='agr_emails_count')
    last_message = serializers.Field(source='agr_last_message')
    last_sent = serializers.Field(source='agr_last_sent')
    last_reply = serializers.Field(source='agr_last_reply')

    class Meta:
        fields = ('opened_count', 'emails_count', 'last_message', 'last_sent',
            'last_reply',)


class PlatformElasticSearchSerializer(serializers.Serializer):
    avg_numcomments_overall = serializers.Field(source='comments')
    avg_numshares_overall = serializers.Field(source='shares')
    avg_numlikes_overall = serializers.Field(source='likes')
    num_followers = serializers.Field(source='num_followers')
    platform_name = serializers.Field(source='platform_name')
    show_on_feed = serializers.SerializerMethodField('get_show_on_feed')

    class Meta:
        fields = (
            # 'id',
            'num_followers',
            # 'posting_rate',
            # 'numposts',
            'avg_numcomments_overall',
            'avg_numshares_overall',
            'avg_numlikes_overall',
            # 'url',
            'platform_name',
            'show_on_feed'
        )

    def get_show_on_feed(self, obj):
        return True


class InfluencerElasticSearchSerializer(serializers.Serializer, SerializerContextMixin):

    id = serializers.SerializerMethodField('get_id')
    name = serializers.SerializerMethodField('get_name')
    first_name = serializers.SerializerMethodField('get_first_name')
    blogname = serializers.SerializerMethodField('get_blogname')
    profile_pic_url = serializers.SerializerMethodField('get_profile_pic_url')
    profile_id = serializers.SerializerMethodField('get_profile_id')
    average_num_comments_per_post = serializers.Field(
        source='avg_numcomments_overall')
    demographics_location = serializers.Field(source='location')
    score_popularity_overall = serializers.Field(source='popularity')
    has_artificial_blog_url = serializers.SerializerMethodField(
        'get_has_artificial_blog_url')
    can_favorite = serializers.SerializerMethodField('get_can_favorite')
    details_url = serializers.SerializerMethodField('get_details_url')
    platforms = serializers.SerializerMethodField('get_platforms')
    collections_in = serializers.SerializerMethodField('get_collections_in')

    class Meta:
        fields = (
            'id',
            'name',
            'platforms',
            'blogname',
            'profile_pic_url',
            'profile_id',

            # 'average_num_posts',
            'first_name',
            'average_num_comments_per_post',
            'demographics_location',
            'score_popularity_overall',
            # 'category_info',
            'has_artificial_blog_url',

            # 'about_page',
            # 'current_platform_page',
            # 'description',
            # 'current_platform',

            'details_url',
            'can_favorite',
            'collections_in',
            # 'posts_json_url',
            # 'items_json_url',
            # 'stats_json_url',
            # 'brand_mentions_json_url',
            # 'monthly_visits_json_url',
            # 'traffic_shares_json_url',
        )

    def get_id(self, obj):
        return obj['_id']

    def get_can_favorite(self, obj):
        return True

    def get_details_url(self, obj):
        return reverse(
            'debra.search_views.blogger_info_json', args=(
                self.get_id(obj),)
        )

    def is_social_account(self, obj, sub_tab):
        return (self.context and self.get_has_artificial_blog_url(obj) and
            self.context.get('sub_tab') == sub_tab)

    def get_name(self, obj):
        if self.is_fake_data_account(obj):
            return constants.FAKE_BLOGGER_DATA['name']
        return unescape(obj['name'])

    def get_first_name(self, obj):
        name = self.get_name(obj)
        return unescape(name.split(' ')[0] if name else '')

    def get_blogname(self, obj):
        if self.is_fake_data_account(obj):
            return constants.FAKE_BLOGGER_DATA['blogname']
        if self.is_social_account(obj, 'instagram_search'):
            try:
                return '@' + self.get_insta_url(obj).split('/')[-1]
            except AttributeError:
                return None
        return unescape(obj['blog_name'])

    def get_profile_pic_url(self, obj):
        # return 'https://s3.amazonaws.com/influencer-images/3170253profile_image.jpg.small.jpg'
        try:
            return [pl for pl in obj.get('social_platforms', [])
                if pl.get('name') == 'profile_pic'][0]['activity_level']
        except (IndexError, KeyError):
            pass

    def get_profile_id(self, obj):
        pass

    def get_has_artificial_blog_url(self, obj):
        return obj.get('blog_url') and "theshelf.com/artificial" in obj.get(
            'blog_url')

    def get_platforms(self, obj):
        from debra.models import Platform
        platforms = defaultdict(dict)
        for pl in obj.get('social_platforms', []):
            try:
                name, field = pl['name'].split('_')
            except ValueError:
                name, field = pl['name'], 'num_followers'
            if name.capitalize() not in Platform.ALL_PLATFORMS:
                continue
            platforms[name][field] = pl.get('num_followers')
            platforms[name]['platform_name'] = name
        # ordered
        platforms_list = sorted(platforms.values(), key=lambda x: x['platform_name'])
        return PlatformElasticSearchSerializer(
            [pl for pl in platforms_list if pl.get('num_followers')],
            many=True
        ).data

    def get_collections_in(self, obj):
        return {}
        # get from ES, not working currently
        tags = obj.get('tags', [])
        data = redis_cache.get_many([
            'ig_{}'.format(tag_id) for tag_id in tags])
        return {
            tag_id: data.get('ig_{}'.format(tag_id), 'Empty')
            for tag_id in tags
        }


class InfluencerElasticSearchSerializerV2(InfluencerElasticSearchSerializer):

    """
    Source Data Example:
    {
        u'blog_url': u'http://clotheshorse-diaryofaclotheshorse.blogspot.com/',
        u'tags': [],
        u'avg_numcomments_overall': 0.439644218551461,
        u'name': u'Fei Cheng',
        u'popularity': 1.499,
        u'social_platforms': [
            {u'instagram': {u'num_followers': 81}},
            {u'bloglovin': {u'num_followers': 0}},
            {u'tumblr': {u'num_followers': 0}},
            {
                u'profile_pic': u'https://s3.amazonaws.com/influencer-images/4139710profile_image.jpg.small.jpg',
                u'cover_pic': u'/static/images/page_graphics/home/new/header_1.jpg'
            }
        ],
        u'location': u'Marilao, Central Luzon, Philippines',
        u'score_engagement_overall': 0.0,
        u'id': u'1532852',
        u'blog_name': u'Chameleon'
    }
    """

    class Meta:
        fields = (
            'id',
            'name',
            'platforms',
            'blogname',
            'profile_pic_url',
            'profile_id',

            'first_name',
            'average_num_comments_per_post',
            'demographics_location',
            'score_popularity_overall',
            'has_artificial_blog_url',

            'details_url',
            'can_favorite',
            'collections_in',
        )

    def get_id(self, obj):
        return obj['id']

    def get_profile_pic_url(self, obj):
        try:
            return [d for d in obj.get('social_platforms', [])
                if 'profile_pic' in d][0]['profile_pic']
        except (IndexError, KeyError):
            pass

    def get_platforms(self, obj):
        from debra.models import Platform
        platforms = []
        for pl in obj.get('social_platforms', []):
            if len(pl) != 1:
                continue
            pl_name = pl.keys()[0].capitalize()
            if pl_name in Platform.ALL_PLATFORMS:
                _data = {
                    'platform_name': pl_name,
                }
                _data.update(pl.values()[0])
                platforms.append(_data)
        platforms.sort(key=lambda x: x['platform_name'])
        return PlatformElasticSearchSerializer(
            [pl for pl in platforms if pl.get('num_followers')],
            many=True
        ).data


class InfluencerSerializer(serializers.ModelSerializer, SerializerContextMixin):
    name = serializers.SerializerMethodField('get_name')
    first_name = serializers.SerializerMethodField('get_first_name')
    blogname = serializers.SerializerMethodField('get_blogname')
    # platforms = PlatformSerializer(source='get_platform_for_search')
    platforms = serializers.SerializerMethodField('get_platforms')
    description = serializers.SerializerMethodField('get_description')
    cover_pic = serializers.SerializerMethodField('get_cover_pic')
    # profile_pic = serializers.SerializerMethodField('get_profile_pic')
    profile_id = serializers.SerializerMethodField('get_profile_id')
    profile_pic_url = serializers.SerializerMethodField('get_profile_pic')
    demographics_location = serializers.SerializerMethodField(
        'get_demographics_location')
    current_platform_page = serializers.SerializerMethodField(
        'get_current_platform_page')
    current_platform = serializers.SerializerMethodField('get_current_platform')
    # invited_to = serializers.SerializerMethodField('get_invited_to')
    # collections_in = serializers.SerializerMethodField('get_collections_in')
    # is_sent_email = serializers.SerializerMethodField('get_is_sent_email')
    score_popularity_overall = serializers.Field(
        source='score_popularity_overall')
    category_info = serializers.Field(source='category_info')
    has_artificial_blog_url = serializers.Field(source='has_artificial_blog_url')
    about_page = serializers.Field(source='about_page')

    details_url = serializers.SerializerMethodField('get_details_url')
    post_counts_json_url = serializers.SerializerMethodField(
        'get_post_counts_json_url')
    posts_json_url = serializers.SerializerMethodField('get_posts_json_url')
    items_json_url = serializers.SerializerMethodField('get_items_json_url')
    stats_json_url = serializers.SerializerMethodField('get_stats_json_url')
    brand_mentions_json_url = serializers.SerializerMethodField(
        'get_brand_mentions_json_url')
    monthly_visits_json_url = serializers.SerializerMethodField(
        'get_monthly_visits_json_url')
    traffic_shares_json_url = serializers.SerializerMethodField(
        'get_traffic_shares_json_url')
    top_country_shares_json_url = serializers.SerializerMethodField(
        'get_top_country_shares_json_url')

    class Meta:
        model = models.Influencer
        fields = (
            'id',
            'name',
            'platforms',
            'blogname',
            'profile_pic_url',
            'cover_pic',
            'profile_id',

            'average_num_posts',
            'first_name',
            'average_num_comments_per_post',
            'demographics_location',
            'score_popularity_overall',
            'category_info',
            'has_artificial_blog_url',
            'about_page',
            'current_platform_page',
            'description',
            'current_platform',

            'details_url',
            'post_counts_json_url',
            'posts_json_url',
            'items_json_url',
            'stats_json_url',
            'brand_mentions_json_url',
            'monthly_visits_json_url',
            'traffic_shares_json_url',
            'top_country_shares_json_url',
        )

    @classmethod
    def platforms_to_cache(cls, obj):
        return PlatformSerializer.cache_serializer().pack(obj.valid_platforms)
        
    @classmethod
    def platforms_from_cache(cls, value):
        return PlatformSerializer.cache_serializer().unpack(value)

    @classmethod
    def time_series_to_cache(cls, obj):
        return PopularityTimeSeriesSerializer.cache_serializer().pack(
            obj.popularitytimeseries_set.all())

    @classmethod
    def time_series_from_cache(cls, value):
        return PopularityTimeSeriesSerializer.cache_serializer().unpack(value)

    def is_social_account(self, obj, sub_tab):
        return (self.context and obj.has_artificial_blog_url and
            self.context.get('sub_tab') == sub_tab)

    def get_name(self, obj):
        if self.is_fake_data_account(obj):
            return constants.FAKE_BLOGGER_DATA['name']
        return unescape(obj.name)

    def get_first_name(self, obj):
        if self.is_fake_data_account(obj):
            return constants.FAKE_BLOGGER_DATA['name']
        return obj.first_name

    def get_platforms(self, obj):
        platforms = obj.all_platforms.filter(lambda pl: pl['num_followers']).get()
        return sorted(platforms, key=lambda x: x['platform_name'])

    def get_blogname(self, obj):
        if self.is_fake_data_account(obj):
            return constants.FAKE_BLOGGER_DATA['blogname']
        if self.is_social_account(obj, 'instagram_search'):
            try:
                return '@' + obj.insta_url.split('/')[-1]
            except AttributeError:
                return None
        return unescape(obj.blogname)

    def get_current_platform_page(self, obj):
        if self.is_social_account(obj, 'instagram_search'):
            return obj.insta_url

    def get_current_platform(self, obj):
        if self.is_social_account(obj, 'instagram_search'):
            pl = obj.get_platform_by_name('Instagram')
            return pl
            # return PlatformSerializer(pl).data

    def get_description(self, obj):
        from debra.search_helpers import tagStripper

        if self.is_fake_data_account(obj):
            return constants.FAKE_BLOGGER_DATA['description']

        desc = obj.description
        if self.is_social_account(obj, 'instagram_search'):
            pl = obj.get_platform_by_name('Instagram')
            if pl is not None:
                # TODO: as we don't store description in cache - I don't really
                # know what to do here
                # desc = pl.description
                pass

        try:
            length_limit = self.context.get('description_length_limit', 140)
        except AttributeError:
            length_limit = 140

        stripped_description, _ = tagStripper(
            desc or '', length_limit=length_limit)

        return stripped_description

    def get_demographics_location(self, obj):
        if obj.demographics_locality:
            return unicode(obj.demographics_locality)
        else:
            return obj.demographics_location_normalized or\
                obj.demographics_location

    def get_profile_id(self, obj):
        return obj.shelf_user and obj.shelf_user.userprofile.id or None

    def get_cover_pic(self, obj):
        # use influencer.cover_pic property
        return obj.cover_pic

    def get_profile_pic(self, obj):
        return obj.profile_pic

    def search_score(self, obj):
        return obj.score_popularity_overall

    def get_invited_to(self, obj):
        # obj.job_ids method will hit database each time, so it's better to
        # prefetch 'mails__candidate_mapping__job' and 'group_mapping__jobs__job'
        # and process this data with Python (will add Raw Sql later, probably)
        if hasattr(obj, 'for_search') and obj.for_search:
            s = set()
            for mail in obj.mails.all():
                for mapping in mail.candidate_mapping.all():
                    s.add(mapping.job_id)
            for mapping in obj.group_mapping.all():
                for job_mapping in mapping.jobs.all():
                    s.add(job_mapping.job_id)
            return filter(None, s)
        else:
            return []

    def get_blogger_url(self, obj, view_name):
        if self.is_public(obj):
            return reverse(
                'debra.search_views.{}_public'.format(view_name),
                args=(obj.id, obj.date_created_hash,)
            )
        return reverse(
            'debra.search_views.{}'.format(view_name), args=(obj.id,))

    def get_details_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_info_json')

    def get_post_counts_json_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_post_counts_json')

    def get_posts_json_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_posts_json')

    def get_items_json_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_items_json')

    def get_stats_json_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_stats_json')

    def get_brand_mentions_json_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_brand_mentions_json')

    def get_monthly_visits_json_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_monthly_visits')

    def get_traffic_shares_json_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_traffic_shares')

    def get_top_country_shares_json_url(self, obj):
        return self.get_blogger_url(obj, 'blogger_top_country_shares')


class InfluencerSearchSerializer(InfluencerSerializer):
    
    class Meta:
        model = models.Influencer
        fields = (
            'id',
            'name',
            'platforms',
            'blogname',
            'profile_pic_url',
            # 'cover_pic',
            'profile_id',

            # 'average_num_posts',
            # 'first_name',
            'average_num_comments_per_post',
            'demographics_location',
            # 'score_popularity_overall',
            # 'category_info',
            'has_artificial_blog_url',
            # 'about_page',
            # 'current_platform_page',
            # 'description',
            # 'current_platform',

            'details_url',
            # 'posts_json_url',
            # 'items_json_url',
            # 'stats_json_url',
            # 'brand_mentions_json_url',
            # 'monthly_visits_json_url',
            # 'traffic_shares_json_url',
            # 'top_country_shares_json_url',
        )


class InfluencerProfileSerializer(InfluencerSerializer):
    pass


class PaginatedInfluencerSerializer(pagination.PaginationSerializer):
    pages = serializers.SerializerMethodField('get_pages')

    class Meta:
        object_serializer_class = InfluencerSerializer

    def get_pages(self, obj):
        return obj.paginator.num_pages


class BaseAdminInfluencerSerializer(serializers.ModelSerializer):
    platform = serializers.Field('blog_platform.platform_name')

    date_edited = serializers.DateTimeField(source="date_edited", format="%x")
    date_validated = serializers.DateTimeField(
        source="date_validated", format="%x")

    is_correctly_qaed = serializers.Field(source='is_correctly_qaed')

    profile_pic = serializers.SerializerMethodField('get_profile_pic')
    fb_likes = serializers.SerializerMethodField('get_fb_likes')
    twitter_followers = serializers.SerializerMethodField(
        'get_twitter_followers')
    pinterest_followers = serializers.SerializerMethodField(
        'get_pinterest_followers')
    instagram_followers = serializers.SerializerMethodField(
        'get_instagram_followers')
    youtube_followers = serializers.SerializerMethodField(
        'get_youtube_followers')
    num_shelved_products = serializers.SerializerMethodField(
        'get_num_products')
    num_posts = serializers.SerializerMethodField('get_num_blog_posts')
    initial_crawl_date = serializers.SerializerMethodField(
        'get_initial_crawl_date')
    last_crawl_date = serializers.SerializerMethodField('get_last_crawl_date')
    last_crawl_prods = serializers.SerializerMethodField(
        'get_last_crawl_prods')
    avg_prods_per_post = serializers.SerializerMethodField(
        'get_avg_prods_per_post')
    posts_with_prods_percentage = serializers.SerializerMethodField(
        'get_posts_with_prods_percentage')
    fashion_links = serializers.SerializerMethodField('get_fashion_links')
    fashion_store_mentions = serializers.SerializerMethodField(
        'get_fashion_store_mentions')
    fashion_widgets = serializers.SerializerMethodField(
        'get_fashion_widgets')
    images = serializers.SerializerMethodField('return_null_value')
    comments = serializers.SerializerMethodField('return_null_value')
    confidence_level = serializers.Field('relevant_to_fashion')
    num_brand_mentions = serializers.SerializerMethodField(
        'get_num_brand_mentions')
    last_denormalize_time = serializers.SerializerMethodField(
        'get_last_denormalize_time')
    last_import_time = serializers.SerializerMethodField(
        'get_last_import_time')
    can_edit = serializers.SerializerMethodField('get_can_edit')
    active = serializers.SerializerMethodField('influencer_active')

    # overwrite default serializer/validator to plain text
    fb_url = serializers.WritableField(source="fb_url")
    tw_url = serializers.WritableField(source="tw_url")
    pin_url = serializers.WritableField(source="pin_url")
    insta_url = serializers.WritableField(source="insta_url")
    bloglovin_url = serializers.WritableField(source="bloglovin_url")
    lb_url = serializers.WritableField(source="lb_url")
    pose_url = serializers.WritableField(source="pose_url")
    youtube_url = serializers.WritableField(source="youtube_url")

    suspicious_url = serializers.WritableField('suspicious_url')

    def transform_problem(self, obj, value):
        if value is not None:
            problems = dict(models.Influencer.PROBLEMS)
            return problems.get(value, '')
        else:
            return value

    def transform_date_edited(self, obj, value):
        return value or "Not edited"

    def get_lb_url(self, inf):
        platforms_qs = inf.platform_set.all()
        for platform in platforms_qs:
            if platform.platform_name == "Lookbook":
                return platform.url

    def get_youtube(self, inf):
        platforms_qs = inf.platform_set.all()
        for platform in platforms_qs:
            if platform.platform_name == "YouTube":
                return platform.url

    def get_metadesc(self, inf):
        platforms_qs = inf.platform_set.all()
        for platform in platforms_qs:
            if not platform.description:
                continue
            if platform.platform_name == "Twitter":
                return platform.description
            if platform.platform_name == "Facebook":
                return platform.description

    def _get_all_posts(self, inf):
        return inf.posts_set.all()

    def _get_all_blog_posts(self, inf):
        posts = set()
        for post in inf.posts_set.all():
            if post.platform.platform_name in models.Platform.BLOG_PLATFORMS:
                posts.add(post)
        return posts
        # return inf.posts_set.all().filter(
        #    platform__platform_name__in=models.Platform.BLOG_PLATFORMS)

    def get_num_blog_posts(self, inf):
        try:
            return inf.agr_blog_posts_count
        except AttributeError:
            return len(self._get_all_blog_posts(inf))

    def get_num_products(self, inf):
        try:
            return inf.agr_products_count
        except AttributeError:
            count = 0
            prod_models = set()
            for post in inf.posts_set.all():
                for prod in post.productmodelshelfmap_set.all():
                    if prod.product_model_id in prod_models:
                        continue
                    prod_models.add(prod.product_model_id)
                    count += 1
            return count
        # return models.ProductModelShelfMap.objects.filter(
        #    post__in=self._get_all_blog_posts(inf)
        # ).distinct('product_model').count()

    def get_num_posts(self, inf):
        try:
            return inf.agr_posts_count
        except AttributeError:
            return self._get_all_posts(inf).count()

    def _get_fetch_data_ops(self, inf):
        return models.PlatformDataOp.objects.filter(
            operation='fetch_data', platform__in=inf.platform_set.all())

    def get_initial_crawl_date(self, inf):
        return self._get_fetch_data_ops(inf).order_by(
            'started')[0].started.strftime("%x")\
            if self._get_fetch_data_ops(inf).exists() else None

    def get_last_crawl_date(self, inf):
        return -1
        try:
            return inf.agr_last_crawl_date
        except AttributeError:
            platforms = frozenset(inf.platform_set.all())
            started_op = None
            for op in inf.platformdataop_set.all():
                if op.platform not in platforms:
                    continue
                if not started_op or (
                    op.started and started_op.started and
                        op.started > started_op.started):
                    started_op = op
            return started_op.finished if started_op else None
            #return self._get_fetch_data_ops(inf).order_by('-started')[0].started.strftime("%x") if self._get_fetch_data_ops(inf).exists() else None

    def get_last_crawl_prods(self, inf):
        posts = self._get_all_posts(inf).filter(products_import_completed=True).order_by('-create_date')
        if posts.exists():
            post = posts[0]
            return models.ProductModelShelfMap.objects.filter(post=post).count()
        return 0

    def get_last_denormalize_time(self, inf):
        return -1
        latest_op = None
        for op in inf.platformdataop_set.all():
            if op.operation == 'denormalize_influencer':
                if not latest_op or (op.finished and latest_op.finished and op.finished > latest_op.finished):
                    latest_op = op
        return latest_op.finished if latest_op else None
        #ops = models.PlatformDataOp.objects.filter(influencer=inf, operation='denormalize_influencer').order_by('-finished')
        #return ops[0].finished if ops.exists() else None

    def get_last_import_time(self, inf):
        # this speeds up notify table quite a lot
        return -1
        latest_op = None
        for post in inf.posts_set.all():
            for op in post.platformdataop_set.all():
                if not latest_op or (op.finished and latest_op.finished and op.finished > latest_op.finished):
                    latest_op = op
        return latest_op.finished if latest_op else None
        #ops = models.PlatformDataOp.objects.filter(post__in=inf.posts_set.all(), operation='fetch_products_from_post')#.order_by('-finished')
        #ops = list(ops.only('finished').values('finished'))
        #print len(ops)
        #ops.sort(key=lambda x: x["finished"])
        #ops.reverse()
        #return ops[0]["finished"] if ops else None

    def get_avg_prods_per_post(self, inf):
        return round(float(self.get_num_products(inf)) / float(len(self._get_all_blog_posts(inf))))

    def get_posts_with_prods_percentage(self, inf):
        posts_with_prods = models.ProductModelShelfMap.objects.filter(post__in=self._get_all_blog_posts(inf)).distinct('post').count()
        all_posts = len(self._get_all_blog_posts(inf))
        return round((100.0 * float(posts_with_prods)) / float(all_posts))

    def get_profile_pic(self, inf):
        return inf.cover_pic

    def _get_pl_attr(self, inf, platform_name, pl_attr, pls=None):
        # t0 = time.time()
        # pls = inf.all_platforms.filter(
        #     lambda pl: pl['platform_name'] == platform_name).get()
        if not pls:
            pls = inf.get_platforms_by_name(platform_name)
        if not pls:
            return None
        # Selected maximum value for the platforms, because there's no selected one now
        vals = filter(None, [pl[pl_attr] for pl in pls])
        # print '_get_pl_attr took {}'.format(time.time() - t0)
        return max(vals) if vals else None

    def get_fb_likes(self, inf):
        return self._get_pl_attr(inf, 'Facebook', 'total_numlikes')

    def get_twitter_followers(self, inf):
        return self._get_pl_attr(inf, 'Twitter', 'num_followers')

    def get_pinterest_followers(self, inf):
        return self._get_pl_attr(inf, 'Pinterest', 'num_followers')

    def get_instagram_followers(self, inf):
        return self._get_pl_attr(inf, 'Instagram', 'num_followers')

    def get_youtube_followers(self, inf):
        return self._get_pl_attr(inf, 'Youtube', 'num_followers')

    def _get_latest_platform_data_op(self, inf):
        ops = models.PlatformDataOp.objects.filter(operation='estimate_if_fashion_blogger', influencer=inf).order_by('-started')
        if not ops:
            return {}
        data = ops[0].data_json
        if data:
            return json.loads(data)
        else:
            return {}

    def get_fashion_links(self, inf):
        op = self._get_latest_platform_data_op(inf)
        return True if (op.get("explanation", {}).get("found_urls_no_resolving") or op.get("urls_requiring_resolving")) else False

    def get_fashion_store_mentions(self, inf):
        op = self._get_latest_platform_data_op(inf)
        return op.get("explanation", {}).get("found_tag_references") if op.get("explanation", {}).get("found_tag_references") else 0

    def get_fashion_widgets(self, inf):
        op = self._get_latest_platform_data_op(inf)
        return op.get("explanation", {}).get("found_iframe_fragments") if op.get("explanation", {}).get("found_iframe_fragments") else ''

    def get_num_brand_mentions(self, inf):
        try:
            return inf.agr_brandmentions_count
        except AttributeError:
            return inf.brandmentions_set.count()

    def return_null_value(self, obj):
        return None

    def get_can_edit(self, obj):
        if obj.validated_on is None:
            return True
        return constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED not in obj.validated_on

    def influencer_active(self, influencer):
        # JS code still relies on a NULL value meaning active status is unknown
        if influencer.active_unknown():
            return None
        else:
            return influencer.active()


class AdminInfluencerSerializer(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer


class AdminInfluencerMandrillError(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer
        fields = (
            'id', 'blog_url', 'email_for_advertising_or_collaborations',
            'email_all_other', 'name', 'blogname', 'email',)

    def get_mandrill_error(self, obj):
        try:
            return obj.email_errors
        except AttributeError:
            pass


class AdminInfluencerMissingEmailSerializer(serializers.Serializer):

        id = serializers.IntegerField()
        blog_url = serializers.CharField()
        email_for_advertising_or_collaborations = serializers.CharField()
        # email_all_other = serializers.CharField()
        name = serializers.CharField()
        blogname = serializers.CharField()
        email = serializers.CharField()
        emails_sent_count = serializers.IntegerField()
        last_send_ts = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
        shelf_user__email = serializers.CharField()


class JobPostInfluencerSerializer(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer
        fields = ('id', 'date_edited', 'date_validated',
                  'blog_url', 'blacklisted', 'problem',
                  'platform', 'initial_crawl_date', 'email', 'blogname', 'show_on_search',
                  )


class AdminInfluencerListSerializer(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer
        fields = ('id', 'date_edited', 'date_validated',
                  'blog_url', 'blacklisted', 'problem',
                  'platform', 'initial_crawl_date', 'email', 'blogname', 'show_on_search',
                  )


class AdminInfluencerListDebugSerializer(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer
        fields = ('id', 'date_edited', 'date_validated', 'initial_crawl_date', 'blog_url', 'platform', 'blacklisted', 'problem')
        readonly_fields = ('id', 'date_edited', 'date_validated', 'initial_crawl_date', 'blog_url', 'platform', 'blacklisted', 'problem')

    def transform_blog_url(self, obj, value):
        return transform_edit_history(obj, value, "blog_url")

    def transform_platform(self, obj, value):
        return transform_edit_history(obj, value, "platform")

    def transform_blacklisted(self, obj, value):
        return transform_edit_history(obj, value, "blacklisted")

    def transform_problem(self, obj, value):
        problems = dict(models.Influencer.PROBLEMS)
        return transform_edit_history(obj, value, "problem", lambda x: problems.get(int(x), "unknown"))


class AdminInfluencerFashionSerializer(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer
        fields = ('id', 'date_edited', 'date_validated',
                  'blog_url', 'platform', 'initial_crawl_date',
                  'active', 'fashion_links', 'fashion_store_mentions',
                  'fashion_widgets',
                  'confidence_level',
                  )


class AdminInfluencerFashionDebugSerializer(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer
        fields = ('id', 'date_edited', 'date_validated',
                  'blog_url', 'platform', 'initial_crawl_date',
                  'active',
                  'fashion_links', 'fashion_store_mentions',
                  'fashion_widgets', 'images', 'comments',
                  'confidence_level', 'show_on_search'
                  )
        readonly_fields = ('id', 'date_edited', 'date_validated',
                  'blog_url', 'platform', 'initial_crawl_date',
                  'active',
                  'fashion_links', 'fashion_store_mentions',
                  'fashion_widgets', 'images', 'comments',
                  'confidence_level', 'show_on_search'
                  )

    def transform_blog_url(self, obj, value):
        return transform_edit_history(obj, value, "blog_url")

    def transform_platform(self, obj, value):
        return transform_edit_history(obj, value, "platform")

    def transform_initial_crawl_date(self, obj, value):
        return transform_edit_history(obj, value, "initial_crawl_date")

    def transform_fashion_links(self, obj, value):
        return transform_edit_history(obj, value, "fashion_links")

    def transform_fashion_store_mentions(self, obj, value):
        return transform_edit_history(obj, value, "fashion_store_mentions")

    def transform_fashion_widgets(self, obj, value):
        return transform_edit_history(obj, value, "fashion_widgets")

    def transform_images(self, obj, value):
        return transform_edit_history(obj, value, "images")

    def transform_comments(self, obj, value):
        return transform_edit_history(obj, value, "comments")

    def transform_confidence_level(self, obj, value):
        return transform_edit_history(obj, value, "confidence_level")

    def transform_show_on_search(self, obj, value):
        return transform_edit_history(obj, value, "show_on_search")


class AdminInfluencerInformationsSerializer(BaseAdminInfluencerSerializer):
    agr_last_sent = serializers.SerializerMethodField('get_agr_last_sent')

    class Meta:
        model = models.Influencer
        fields = ('id', 'date_edited', 'date_validated', 'email', 'blog_url',
                  'profile_pic_url', 'blogname', 'name', 'description',
                  'about_url', 'demographics_location', 'fb_url',
                  'tw_url', 'pin_url', 'gplus_url', 'snapchat_username',
                  'insta_url', 'bloglovin_url', 'lb_url', 'demographics_gender',
                  'pose_url', 'youtube_url', 'average_num_comments_per_post', 'qa',
                  'ready_to_invite', 'email_for_advertising_or_collaborations',
                  'email_all_other', 'contact_form_if_no_email', 'can_edit', 'show_on_search', 'relevant_to_fashion',
                  'active', 'blacklisted', 'suspicious_url', 'is_correctly_qaed', 'agr_last_sent',
                  )

    def get_agr_last_sent(self, obj):
        try:
            return obj.agr_last_sent.strftime('%c')
        except AttributeError:
            pass


class AdminInfluencerInformationsDebugSerializer(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer
        fields = ('id', 'date_edited', 'date_validated', 'email', 'blog_url',
                  'profile_pic_url', 'blogname', 'name', 'description',
                  'about_url', 'demographics_location', 'fb_url',
                  'tw_url', 'pin_url',
                  'insta_url', 'bloglovin_url', 'lb_url', 'demographics_gender',
                  'pose_url', 'youtube_url', 'qa'
                  )
        readonly_fields = ('id', 'date_edited', 'date_validated', 'email', 'blog_url',
                  'profile_pic_url', 'blogname', 'name', 'description',
                  'about_url', 'demographics_location', 'fb_url',
                  'tw_url', 'pin_url',
                  'insta_url', 'bloglovin_url', 'lb_url',
                  'pose_url', 'youtube_url', 'qa'
                  )

    def transform_email(self, obj, value):
        return transform_edit_history(obj, value, 'email')

    def transform_blog_url(self, obj, value):
        return transform_edit_history(obj, value, 'blog_url')

    def transform_profile_pic_url(self, obj, value):
        return transform_edit_history(obj, value, 'profile_pic_url')

    def transform_blogname(self, obj, value):
        return transform_edit_history(obj, value, 'blogname')

    def transform_name(self, obj, value):
        return transform_edit_history(obj, value, 'name')

    def transform_description(self, obj, value):
        return transform_edit_history(obj, value, 'description')

    def transform_about_url(self, obj, value):
        return transform_edit_history(obj, value, 'about_url')

    def transform_demographics_location(self, obj, value):
        return transform_edit_history(obj, value, 'demographics_location')

    def transform_fb_url(self, obj, value):
        return transform_edit_history(obj, value, 'fb_url')

    def transform_tw_url(self, obj, value):
        return transform_edit_history(obj, value, 'tw_url')

    def transform_pin_url(self, obj, value):
        return transform_edit_history(obj, value, 'pin_url')

    def transform_insta_url(self, obj, value):
        return transform_edit_history(obj, value, 'insta_url')

    def transform_bloglovin_url(self, obj, value):
        return transform_edit_history(obj, value, 'bloglovin_url')

    def transform_lb_url(self, obj, value):
        return transform_edit_history(obj, value, 'lb_url')

    def transform_pose_url(self, obj, value):
        return transform_edit_history(obj, value, 'pose_url')

    def transform_youtube_url(self, obj, value):
        return transform_edit_history(obj, value, 'youtube_url')


class AdminInfluencerAdminSerializer(BaseAdminInfluencerSerializer):

    class Meta:
        model = models.Influencer
        fields = ('id', 'date_edited', 'date_validated',
                  'profile_pic_url', 'blogname', 'blog_url', 'name', 'demographics_location',
                  'source', 'fb_url', 'fb_likes', 'tw_url',
                  'twitter_followers', 'pin_url', 'pinterest_followers', 'demographics_gender',
                  'insta_url', 'instagram_followers', 'about',
                  )


class AdminInfluencerCurrentSearchResultsSerializer(BaseAdminInfluencerSerializer):

    about_page = serializers.SerializerMethodField('get_about_page')
    suspicious_url = serializers.WritableField('suspicious_url')

    class Meta:
        model = models.Influencer
        # fields = (
        #     'id', 'name', 'blog_url', 'blacklisted', 'last_crawl_date',
        #     'email', 'blogname', 'profile_pic_url', 'num_brand_mentions',
        #     'num_posts', 'num_shelved_products',
        #     'average_num_comments_per_post','last_denormalize_time',
        #     'last_import_time', 'description', 'ready_to_invite', 'about_page',
        #     'show_on_search', 'suspicious_url',
        # )
        fields = (
            'id', 'name', 'blog_url', 'blacklisted', 'last_crawl_date',
            'email', 'blogname', 'profile_pic_url', 'num_brand_mentions',
            'num_posts', 'num_shelved_products',
            'average_num_comments_per_post', 'last_denormalize_time',
            'last_import_time', 'description', 'ready_to_invite', 'about_page',
            'show_on_search', 'suspicious_url',
        )

    def get_about_page(self, obj):
        return obj.about_page


class AdminInfluencerSocialMedia(serializers.ModelSerializer):

    fb_activity = serializers.SerializerMethodField('get_fb_activity')

    class Meta:
        model = models.Influencer
        fields = ('id', 'name', 'blog_url', 'fb_activity')

    def _get_report(self, obj, platform):
        reports = obj.popularitytimeseries_set.filter(platform__platform_name=platform)
        if reports.count() == 0:
            return None, None
        latest = reports.latest('snapshot_date')
        previous = None
        previous_reports = obj.popularitytimeseries_set.filter(platform__platform_name=platform, snapshot_date__lt=latest.snapshot_date)
        if previous_reports.count() > 0:
            previous = previous_reports.latest('snapshot_date')
        return latest, previous

    def _get_delta_fcall(self, latest, previous, field):
        if previous:
            delta = getattr(latest, field, 0)() - getattr(previous, field, 0)()
            if delta != 0:
                delta = "%+i" % delta
            else:
                delta = "="
        elif getattr(latest, field)():
            delta = "+%i" % getattr(latest, field)()
        else:
            delta = ""
        return delta

    def _get_delta(self, latest, previous, field):
        if previous:
            delta = getattr(latest, field, 0) - getattr(previous, field, 0)
            if delta != 0:
                delta = "%+i" % delta
            else:
                delta = "="
        elif getattr(latest, field):
            delta = "+%i" % getattr(latest, field)
        else:
            delta = ""
        return delta

    def _get_posts_2_months(self, platform):
        last_month = datetime.datetime.now() - datetime.timedelta(days=30)
        two_months_ago = datetime.datetime.now() - datetime.timedelta(days=60)
        posts = models.Posts.objects.filter(platform=platform, create_date__lte=last_month, create_date__gte=two_months_ago)
        return posts

    def _get_posts_last_month(self, platform):
        last_month = datetime.datetime.now() - datetime.timedelta(days=30)
        posts = models.Posts.objects.filter(platform=platform, create_date__gte=last_month)
        return posts

    def get_fb_activity(self, obj):
        output = []

        latest, previous = self._get_report(obj, "Facebook")
        if not latest:
            return "No activity recorded"
        followers_delta = self._get_delta(latest, previous, 'num_followers')
        output.append("%i followers %s" % (latest.num_followers, followers_delta))

        latest_posts = self._get_posts_last_month(latest.platform)
        previous_posts = self._get_posts_2_months(latest.platform)

        posts_count = latest_posts.count()
        posts_delta = self._get_delta_fcall(latest_posts, previous_posts, 'count')
        output.append("%i posts/month %s" % (posts_count, posts_delta))

        # interactions = models.PostInteractions.objects.filter(post)
        # likes_current =
        # likes_current = previous_posts.postinteractions_set.filter(is_liked=True)

        return "<br>".join(output)


class PostAnalyticsCollectionCopySerializer(serializers.ModelSerializer):
    new_brand = serializers.WritableField(source='new_brand')

    class Meta:
        model = models.PostAnalyticsCollection
        fields = ('id', 'name', 'new_brand',)


class BrandFlagsTableSerializer(serializers.ModelSerializer):

    date_joined = serializers.SerializerMethodField('get_date_joined')
    user_name = serializers.SerializerMethodField('get_user_name')
    email = serializers.SerializerMethodField('get_email')
    locked = serializers.WritableField(source='flag_locked')
    availiable_plan = serializers.WritableField(source='flag_availiable_plan')
    suspended = serializers.WritableField(source='flag_suspended')
    report_roi_prediction = serializers.WritableField(
        source='flag_report_roi_prediction')
    show_other_plans = serializers.WritableField(source='flag_show_other_plans')
    compete_api_key_available = serializers.WritableField(
        source='flag_compete_api_key_available')
    compete_api_key = serializers.WritableField(source='flag_compete_api_key')
    and_or_filter_on = serializers.WritableField(source='flag_and_or_filter_on')
    export_collection_on = serializers.WritableField(
        source='flag_export_collection_on')
    instagram_search = serializers.WritableField(
        source='flag_instagram_search')
    one_time_fee = serializers.WritableField(source='flag_one_time_fee')
    services_plan = serializers.WritableField(source='flag_services_plan')

    class Meta:
        model = models.Brands
        fields = (
            'id', 'date_joined', 'name', 'domain_name', 'user_name',
            'email', 'suspended', 'show_other_plans', 'locked',
            'availiable_plan', 'analytics_tab_visible', 'is_agency',
            'compete_api_key', 'compete_api_key_available',
            'report_roi_prediction', 'and_or_filter_on', 'export_collection_on',
            'instagram_search', 'one_time_fee', 'services_plan',
        )

    def get_date_joined(self, obj):
        up = obj.get_owner_user_profile()
        if up:
            return up.user.date_joined.strftime("%b. %e, %Y")
        else:
            return "No users"

    def get_user_name(self, obj):
        up = obj.get_owner_user_profile()
        if up:
            return up.name
        else:
            return "No users"

    def get_email(self, obj):
        up = obj.get_owner_user_profile()
        if up:
            return up.user.email
        else:
            return "No users"


class InfluencerCheckSerializer(serializers.ModelSerializer):
    blog_url = serializers.WritableField(source="influencer.blog_url")
    email_for_advertising_or_collaborations = serializers.WritableField(source="influencer.email_for_advertising_or_collaborations")
    email_all_other = serializers.WritableField(source="influencer.email_all_other")
    contact_form_if_no_email = serializers.WritableField(source="influencer.contact_form_if_no_email")
    name = serializers.WritableField(source="influencer.name")
    blogname = serializers.WritableField(source="influencer.blogname")
    description = serializers.WritableField(source="influencer.description")
    demographics_location = serializers.WritableField(source="influencer.demographics_location")
    socials = serializers.SerializerMethodField('get_socials')
    platform_details = serializers.SerializerMethodField('get_platform_details')
    related = serializers.SerializerMethodField('get_related')
    all_platforms = serializers.SerializerMethodField('get_all_platforms')
    autovalidated_platforms = serializers.SerializerMethodField('get_autovalidated_platforms')
    customer_comments = serializers.SerializerMethodField('get_customer_comments')
    atul_collections = serializers.SerializerMethodField('get_atul_collections')

    class Meta:
        model = models.InfluencerCheck
        fields = (
            "id",
            "influencer",
            "platform",
            "cause",
            "status",
            "fields",
            "custom_message",
            "blog_url",
            "email_for_advertising_or_collaborations",
            "email_all_other",
            "contact_form_if_no_email",
            "name",
            "blogname",
            "description",
            "demographics_location",
            "socials",
            "platform_details",
            "related",
            "all_platforms",
            "autovalidated_platforms",
            "customer_comments",
            "atul_collections",
        )
        readonly_fields = (
            "id",
            "influencer",
            "platform",
            "cause",
            "fields",
            "all_platforms",
            "autovalidated_platforms",
        )

    def transform_custom_message(self, obj, value):
        from django.utils.html import escape
        return escape(value)

    def transform_influencer(self, obj, value):
        return obj.influencer and obj.influencer.id

    def transform_platform(self, obj, value):
        return obj.platform and obj.platform.id

    def get_customer_comments(self, obj):
        return transform_customer_comments(obj=obj)

    def get_atul_collections(self, obj):
        ids = constants.ATUL_COLLECTIONS_IDS

        group_ids = map(lambda x: x.group_id, filter(
            lambda x: x.group_id in ids and x.status != models.InfluencerGroupMapping.STATUS_REMOVED,
            obj.influencer.group_mapping.all()
        ))

        try:
            collections = copy.copy(self.context['atul_collections'])
        except (TypeError, KeyError):
            collections = constants.get_atul_collections()

        for collection in collections:
            collection['selected'] = collection['id'] in group_ids

        return collections

    def get_platform_details(self, obj):
        if not obj.platform:
            return
        data = []
        field_name = models.Influencer.platform_name_to_field.get(obj.platform.platform_name)
        if field_name:
            value = getattr(obj.influencer, field_name)
            field_name = "i:%s:%i" % (field_name, obj.influencer.id)
        else:
            field_name = "p:url:%i" % obj.platform.id
            value = getattr(obj.platform, 'url')
        data.append({
            'name': "%s - %r followers, %r comments, %r posts" % (obj.platform.platform_name, obj.platform.num_followers, obj.platform.total_numcomments, obj.platform.numposts),
            'raw': field_name,
            'value': value,
        })
        return data

    def get_all_platforms(self, obj):
        fields = json.loads(obj.fields)

        trans = models.Influencer.field_to_platform_name
        trans['blog_url'] = 'Blog Url'

        mapping = defaultdict(list)

        # urls = models.Platform.objects.filter(
        #     influencer=obj.influencer,
        #     # platform_name__in=map(trans.get, fields)
        #     platform_name__in=trans.values()
        # ).exclude(
        #     url_not_found=True
        # ).values_list('platform_name', 'url')

        urls = [
            (p.platform_name, p.url) for p in obj.influencer.platform_set.all()
            if p.url_not_found == False and p.platform_name in trans.values()
        ]

        for platform_name, url in urls:
            mapping[platform_name].append(url)

        res = "<br /><br />".join(
            ["{}:<br /><br />{}".format("<span style='color: blue;'>" + k + "</span>", "<br /><br />".join(v)) for k, v in mapping.items()]
        )

        return res

    def get_autovalidated_platforms(self, obj):
        fields = json.loads(obj.fields)

        trans = models.Influencer.field_to_platform_name
        trans['blog_url'] = 'Blog Url'

        mapping = defaultdict(list)

        # urls = models.Platform.objects.filter(
        #     influencer=obj.influencer,
        #     # platform_name__in=map(trans.get, fields),
        #     platform_name__in=trans.values(),
        #     autovalidated=True
        # ).exclude(
        #     url_not_found=True
        # ).values_list('platform_name', 'url')

        urls = [
            (p.platform_name, p.url) for p in obj.influencer.platform_set.all()
            if p.url_not_found == False and p.platform_name in trans.values() and p.autovalidated
        ]

        for platform_name, url in urls:
            mapping[platform_name].append(url)

        res = "<br /><br />".join(
            ["{}:<br /><br />{}".format("<span style='color: blue;'>" + k + "</span>", "<br /><br />".join(v)) for k, v in mapping.items()]
        )

        return res

    def transform_cause(self, obj, value):
        causes = dict(models.InfluencerCheck.CAUSES)
        return causes.get(value, 'unknown')

    def transform_status(self, obj, value):
        causes = dict(models.InfluencerCheck.STATUSES)
        return causes.get(value, 'unknown')

    def transform_fields(self, obj, value):
        fields = json.loads(obj.fields)
        data = []
        trans = models.Influencer.field_to_platform_name
        trans["blog_url"] = "Blog Url"
        for field in trans:
            data.append({
                'name': trans.get(field),
                'raw': "i:%s:%i" % (field, obj.influencer.id),
                'value': getattr(obj.influencer, field),
                'is_broken': field in fields
            })
        return data

    def _get_socials_of_influencer(self, obj):
        data = []
        for platform in obj.get_platform_for_search:
            field_name = models.Influencer.platform_name_to_field.get(platform.platform_name)
            if field_name:
                value = getattr(obj, field_name)
                field_name = "i:%s:%i" % (field_name, obj.id)
            else:
                field_name = "p:url:%i" % platform.id
                value = getattr(platform, 'url')
            data.append({
                'name': "%s - %r followers, %r comments, %r posts" % (platform.platform_name, platform.num_followers, platform.total_numcomments, platform.numposts),
                'raw': field_name,
                'value': value,
            })
        data.append({
            'name': "Blog URL",
            'raw': "i:%s:%i" % ('blog_url', obj.id),
            'value': obj.blog_url,
        })
        return data

    def get_socials(self, obj):
        if obj.influencer is None:
            return []
        return self._get_socials_of_influencer(obj.influencer)

    def get_related(self, obj):
        try:
            data_json = json.loads(obj.data_json)
        except:
            return []
        related = []
        for model, pk in data_json["related"]:
            rel_obj = getattr(models, model).objects.get(id=pk)
            if model == "Influencer":
                related.append({
                    'blog_url': rel_obj.blog_url,
                    'socials': self._get_socials_of_influencer(rel_obj)
                })
        return related


class AdminUserSerializer(serializers.ModelSerializer):
    influencer = AdminInfluencerSerializer(source='userprofile.influencer')
    blog_page = serializers.Field(source='userprofile.blog_page')
    has_userprofile = serializers.SerializerMethodField('get_has_userprofile')
    has_influencer = serializers.SerializerMethodField('get_has_influencer')
    inf_blog_url = serializers.Field(source='userprofile.influencer.blog_url')
    inf_blogname = serializers.Field(source='userprofile.influencer.blogname')
    inf_name = serializers.Field(source='userprofile.influencer.name')
    inf_about_page = serializers.Field(
        source='userprofile.influencer.about_page')
    inf_blacklisted = serializers.Field(
        source='userprofile.influencer.blacklisted')
    inf_problem = serializers.Field(source='userprofile.influencer.problem')
    inf_show_on_search = serializers.Field(
        source='userprofile.influencer.show_on_search')
    inf_is_qaed = serializers.SerializerMethodField('get_inf_is_qaed')
    date_signedup = serializers.SerializerMethodField('get_date_signedup')

    class Meta:
        model = models.User
        fields = (
            'id', 'email', 'date_signedup', 'blog_page', 'has_userprofile',
            'has_influencer', 'inf_blog_url', 'inf_blogname', 'inf_name',
            'inf_about_page', 'inf_blacklisted', 'inf_show_on_search',
            'inf_is_qaed',)

    def get_has_userprofile(self, obj):
        if obj.userprofile:
            return True
        return False

    def get_has_influencer(self, obj):
        if obj.userprofile and obj.userprofile.influencer:
            return True
        return False

    def get_inf_is_qaed(self, obj):
        if obj.userprofile and obj.userprofile.influencer:
            return obj.userprofile.influencer.is_qad()

    def get_date_signedup(self, obj):
        return obj.date_joined.strftime('%c')


class AdminUserProfileSerializer(serializers.ModelSerializer):
    # blog_page = serializers.URLField('blog_page')

    class Meta:
        model = models.UserProfile
        fields = ('blog_page',)


class PostSerializer(serializers.ModelSerializer):
    create_date = serializers.SerializerMethodField('get_create_date')

    class Meta:
        model = models.Posts
        fields = ('id', 'influencer', 'url', 'create_date', 'post_image')

    def get_create_date(self, obj):
        if obj.create_date is not None:
            return str(obj.create_date)
        return None


class AdminPostAnalyticsCollectionSerializer(serializers.ModelSerializer):
    brand_id = serializers.Field(source='creator_brand_id')
    brand_name = serializers.Field(source='creator_brand.name')
    username = serializers.Field(source='user.email')
    page_url = serializers.SerializerMethodField('get_page_url')
    is_new_report_ready = serializers.Field(source='is_new_report_ready')
    send_report_to_customer = serializers.WritableField(
        source='flag_send_report_to_customer')
    flag_last_report_sent = serializers.SerializerMethodField(
        'get_last_report_sent')
    new_brand = serializers.WritableField(source='new_brand')

    class Meta:
        model = models.PostAnalyticsCollection
        fields = (
            'id', 'brand_id', 'brand_name', 'username', 'name', 'page_url',
            'flag_last_report_sent', 'is_new_report_ready',
            'send_report_to_customer', 'new_brand',)

    def get_page_url(self, obj):
        return 'app.theshelf.com' + obj.page_url

    def get_last_report_sent(self, obj):
        if obj.last_report_sent is not None:
            return datetime.datetime.strftime(obj.last_report_sent, '%c')


class AdminReportSerializer(serializers.ModelSerializer):
    brand_id = serializers.Field(source='creator_brand_id')
    brand_name = serializers.Field(source='creator_brand.name')
    username = serializers.Field(source='user.email')
    page_url = serializers.SerializerMethodField('get_page_url')
    copy_to_tag = serializers.WritableField(source='copy_to_tag')
    copy_to_report = serializers.WritableField(source='copy_to_report')
    post_collection = serializers.Field(source='post_collection_id')

    class Meta:
        model = models.ROIPredictionReport
        fields = (
            'id', 'brand_id', 'brand_name', 'username', 'name', 'page_url',
            'copy_to_tag', 'copy_to_report', 'post_collection',)

    def get_page_url(self, obj):
        return 'app.theshelf.com' + obj.page_url

    def get_last_report_sent(self, obj):
        if obj.last_report_sent is not None:
            return datetime.datetime.strftime(obj.last_report_sent, '%c')


class AdminTagSerializer(serializers.ModelSerializer):
    brand_id = serializers.Field(source='creator_brand_id')
    brand_name = serializers.Field(source='creator_brand.name')
    username = serializers.Field(source='creator_userprofile.user.email')
    page_url = serializers.SerializerMethodField('get_page_url')
    new_brand = serializers.WritableField(source='new_brand')

    class Meta:
        model = models.PostAnalyticsCollection
        fields = (
            'id', 'brand_id', 'brand_name', 'username', 'name', 'page_url',
             'new_brand',)

    def get_page_url(self, obj):
        return 'app.theshelf.com' + obj.page_url

    def get_last_report_sent(self, obj):
        if obj.last_report_sent is not None:
            return datetime.datetime.strftime(obj.last_report_sent, '%c')


class PostAnalyticsSerializer(serializers.ModelSerializer):
    post = PostSerializer()

    class Meta:
        model = models.PostAnalytics
        exclude = ('modified',)


########## < Analytics/Reporting Serializers > ##########

def annotate_influencer(influencer, request=None, brand=None):
    brand = request.visitor["base_brand"] if request else brand
    if brand and brand.flag_show_dummy_data:
        influencer.blogname = constants.FAKE_BLOGGER_DATA["blogname"]
        influencer.name = constants.FAKE_BLOGGER_DATA["name"]
        influencer.blog_url = constants.FAKE_BLOGGER_DATA["blog_url"]
        influencer.fb_url = constants.FAKE_BLOGGER_DATA["social_url"]
        influencer.pin_url = constants.FAKE_BLOGGER_DATA["social_url"]
        influencer.tw_url = constants.FAKE_BLOGGER_DATA["social_url"]
        influencer.insta_url = constants.FAKE_BLOGGER_DATA["social_url"]
        influencer.youtube_url = constants.FAKE_BLOGGER_DATA["social_url"]
    return influencer


def influencer_info(influencer, include_instance=True,  **kwargs):
    request = kwargs.get('request')
    admin_serializer = AdminInfluencerSerializer()
    serializer = InfluencerSerializer(context={'request': request})
    influencer = annotate_influencer(
        influencer, request=request, brand=kwargs.get('brand'))
    influencer_obj = {
        'fb_likes': admin_serializer.get_fb_likes(influencer) or '',
        'tw_fol': admin_serializer.get_twitter_followers(influencer) or '',
        'ig_fol': admin_serializer.get_instagram_followers(influencer) or '',
        'pin_fol': admin_serializer.get_pinterest_followers(influencer) or '',
        'youtube_fol': admin_serializer.get_youtube_followers(influencer) or '',
        'post_per_month': influencer.average_num_posts or '',
        'num_comments': influencer.average_num_comments_per_post or '',
        'num_giveaways': influencer.average_num_giveaways or '',
        'details_url': serializer.get_details_url(influencer),
        'profile_pic': influencer.profile_pic,
        'name': unescape(influencer.name).strip() if influencer.name else "",
        'blog_url': influencer.blog_url.strip() if influencer.blog_url else "",
        'blogname': unescape(influencer.blogname).strip() if influencer.blogname else "",
        'fb_url': influencer.fb_url or "",
        'pin_url': influencer.pin_url or "",
        'tw_url': influencer.tw_url or "",
        'insta_url': influencer.insta_url or "",
        'youtube_url': influencer.youtube_url or "",
        'id': influencer.id,
    }
    if include_instance:
        influencer_obj['influencer'] = influencer
    influencer_obj.update(kwargs)
    return influencer_obj


class PostUrlInfoSerializer(serializers.ModelSerializer):

    TEMPLATE_PATH = 'snippets/post_analytics_post_url.html'

    url = serializers.Field(source='post_url')
    title = serializers.Field(source='post.title')
    create_date = serializers.Field(source='post.create_date')
    include_template = serializers.SerializerMethodField(
        'get_include_template')
    pa_id = serializers.Field(source='id')

    class Meta:
        model = models.PostAnalytics
        depth = 2
        fields = ('url', 'title', 'create_date', 'include_template', 'pa_id',)

    def get_include_template(self, obj):
        return PostUrlInfoSerializer.TEMPLATE_PATH


class BaseInfoFieldSerializer(object):
    TEMPLATE_PATH = None

    include_template = serializers.SerializerMethodField(
        'get_include_template')

    def get_include_template(self, obj):
        return self.TEMPLATE_PATH


class BaseTableSerializer(SerializerContextMixin):

    FIELDS_DATA = []
    FIELD_TEMPLATES = []
    POST_RELATED_FIELDS = []
    SORT_BY_FIELDS = []
    SUM_FIELDS = []
    UNSORTABLE_FIELDS = []
    HIDDEN_FIELDS = []
    NON_TOTAL_FIELDS = []
    TOTAL_FIELDS = []
    CALCULATED_FIELD_NAMES = {}

    @classmethod
    def value_for_sum(cls, k, item):
        return item.get(dict(cls.SUM_FIELDS).get(k), item.get(k))

    @classmethod
    def should_compute_total(cls, k, v, item=None):
        if item is not None:
            v = cls.value_for_sum(k, item)
        conditions = [
            isinstance(v, Number),
            v >= 0,
            k not in cls.HIDDEN_FIELDS,
            k not in cls.NON_TOTAL_FIELDS,
        ]
        return all(conditions)

    def influencer_check(self, obj):
        try:
            # conditions = (
            #     obj.post is not None,
            #     obj.post.influencer is not None,
            #     # obj.post.influencer.is_qad()
            # )
            # return all(conditions)
            return obj.influencer is not None
        except AttributeError:
            return False

    def get_influencer_info(self, obj):
        if self.influencer_check(obj):
            data = influencer_info(
                obj.influencer,
                include_instance=False,
                brand=self.get_brand(obj),
                request=self.get_request(obj)
            )
            data['include_template'] = dict(self.FIELD_TEMPLATES).get(
                'influencer_info')
            data['pa_id'] = obj.id
            data['is_qad'] = obj.influencer.is_qad()
            data['td_class'] = 'profile_td'
            return data

    def get_visible_items(self, hidden_fields=None):
        _items = self.get_fields().items()
        _hidden_fields = list(set((hidden_fields or []) + self.HIDDEN_FIELDS))
        return [(k, v) for k, v in _items if k not in _hidden_fields]

    @classmethod
    def get_visible_fields(cls, hidden_fields=None, context=None):
        hidden_fields = list(set((hidden_fields or []) + cls.HIDDEN_FIELDS))
        visible_fields = []
        for f, h in cls.FIELDS_DATA:
            if f in hidden_fields:
                continue
            try:
                func = getattr(cls, 'get_{}_header_name'.format(f))
            except AttributeError:
                pass
            else:
                h = func(context=context)
            visible_fields.append((f, h))
        return visible_fields

    @classmethod
    def get_headers(cls, hidden_fields=None, visible_columns=None, context=None):
        return {
            f: {
                'text': h,
                'visible': not(visible_columns and f not in visible_columns),
                'order': n
            } for n, (f, h) in enumerate(cls.get_visible_fields(hidden_fields,
                context=context))
        }


class BaseInfluencerReportTableSerializer(BaseTableSerializer, serializers.ModelSerializer):
    influencer_info = serializers.SerializerMethodField('get_influencer_info')
    personal_engagement_score = serializers.SerializerMethodField(
        'get_personal_engagement_score')
    blog_info = serializers.SerializerMethodField('get_blog_info')
    twitter_info = serializers.SerializerMethodField('get_twitter_info')
    pinterest_info = serializers.SerializerMethodField('get_pinterest_info')
    facebook_info = serializers.SerializerMethodField('get_facebook_info')
    instagram_info = serializers.SerializerMethodField('get_instagram_info')
    youtube_info = serializers.SerializerMethodField('get_youtube_info')
    posts_info = serializers.SerializerMethodField('get_posts_info')

    # platforms = PlatformSerializer(source='get_platform_for_search')
    platforms = serializers.SerializerMethodField('get_platforms')

    POST_RELATED_FIELDS = dict(sum((
        []
    ), [])).keys()

    FIELD_TEMPLATES = [
        ('influencer_info', 'snippets/post_analytics_blogger_info.html'),
        ('blog_info', 'snippets/blog_info.html'),
        ('twitter_info', 'snippets/twitter_info.html'),
        ('pinterest_info', 'snippets/pinterest_info.html'),
        ('facebook_info', 'snippets/facebook_info.html'),
        ('instagram_info', 'snippets/instagram_info.html'),
        ('youtube_info', 'snippets/youtube_info.html'),
        ('approve_info', 'snippets/approve_info.html'),
        ('influencer_note_info', 'snippets/influencer_note_info.html'),
    ]

    UNSORTABLE_FIELDS = [
        'twitter_info', 'pinterest_info', 'facebook_info', 'instagram_info',
        'blog_info', 'youtube_info', 'posts_info',
    ]

    HIDDEN_FIELDS = ['id',]

    VISIBLE_COLUMNS = []

    def get_platforms(self, obj):
        cache_data = obj.influencer.cache_data
        return cache_data if cache_data else PlatformSerializer(
            obj.influencer.get_platform_for_search, many=True).data

    def get_posts_info(self, obj):
        if not self.influencer_check(obj):
            return None
        group_by_influencers = self.context.get('group_by_influencers')
        if group_by_influencers:
            qs = group_by_influencers.get(obj.influencer_id)
        else:
            qs = obj.collection.get_unique_post_analytics(
                post__influencer_id=obj.influencer_id
            ).with_counters()

        serialized_data = serialize_post_analytics_data(
            qs, PostReportTableSerializer, serializer_context=self.context)
        totals_data = count_totals(qs, PostReportTableSerializer, with_fields=True)

        data = {
            'paginated_data_list': serialized_data['data_list'],
            'fields': PostReportTableSerializer.FIELDS_DATA,
            'fields_loading': PostReportTableSerializer.POST_RELATED_FIELDS,
            'fields_unsortable': PostReportTableSerializer.UNSORTABLE_FIELDS,
            'fields_hidden': PostReportTableSerializer.HIDDEN_FIELDS,
        }

        data['include_template'] = dict(
            self.FIELD_TEMPLATES).get('posts_info')

        data.update(serialized_data)
        data.update(totals_data)
        return data

    def get_personal_engagement_score(self, obj):
        try:
            t = time.time()
            avg_score, max_score = obj.calculate_personal_engagement_score(
                self.context.get('virality_scores'))
            print '#{} personal eng. score -- {}'.format(
                obj.id, time.time() - t)
        except TypeError:
            return None
        return "Avg={}\nMax={}".format(avg_score, max_score)

    def get_platform_info(self, obj, platform_name):
        data = {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                platform_name.lower() + '_info'),
            'found': False
        }
        if self.influencer_check(obj):
            pls = obj.influencer.get_platforms_by_name(platform_name)
            if pls:
                data['found'] = True
                pl = pls[0]
                if pl.get('num_followers') and pl.get('avg_numlikes_overall'):
                    pl['eng_fol_ratio'] = 100 * pl['avg_numlikes_overall'] / pl['num_followers']
                data.update(pl)
        return data

    def get_twitter_info(self, obj):
        return self.get_platform_info(obj, 'Twitter')

    def get_pinterest_info(self, obj):
        return self.get_platform_info(obj, 'Pinterest')

    def get_facebook_info(self, obj):
        return self.get_platform_info(obj, 'Facebook')

    def get_instagram_info(self, obj):
        return self.get_platform_info(obj, 'Instagram')

    def get_youtube_info(self, obj):
        return self.get_platform_info(obj, 'Youtube')

    def get_blog_info(self, obj):
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get('blog_info'),
            'found': True,
            'average_num_comments_per_post': obj.influencer.average_num_comments_per_post,
            'average_num_posts': obj.influencer.average_num_posts,
        }


POST_ANALYTICS_BLOGGER_FIELDS = [
    ('blog_name', 'Blog Name'),
    ('blog_url', 'Blog Url'),
    ('influencer_name', 'Author'),
]

POST_ANALYTICS_GROUP_FIELDS = [
    ('influencer_info', 'Influencer'),
    ('post_url_info', 'Url'),
]

POST_ANALYTICS_POST_FIELDS = [
    ('post_title', 'Post'),
    ('post_url', 'Url'),
    ('post_num_comments', 'Post Comments'),
]

POST_ANALYTICS_SIMILAR_WEB_FIELDS = [
    # ('count_tweets', 'Twitter Mentions'),
    # ('count_fb', 'Facebook Shares'),
    # ('count_gplus_plusone', 'Google+'),
    # ('count_pins', 'Pinterest'),

    ('count_tweets_info', 'Twitter Mentions'),
    ('count_fb_info', 'Facebook Shares'),
    ('count_gplus_plusone_info', 'Google+'),
    ('count_pins_info', 'Pinterest'),
]

POST_ANALYTICS_SUMMARY_FIELDS = [
    ('count_total', 'Total'),
    # ('count_total_info', 'Total'),
]

CAMPAIGN_REPORT_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('influencer_info', 'Influencer'),
    ('post_date', 'Date'),
    ('post_info', 'Post'),
    ('post_type_info', 'Type'),
    ('count_impressions', 'Impressions'),
    ('count_clickthroughs', 'Clickthroughs'),
    ('post_total', 'Total Engagement'),
    # ('post_views', 'Views'),
    ('post_likes', 'Likes'),
    ('post_comments', 'Comments'),
    ('post_shares', 'Shares'),
    ('count_fb_shares', 'FB Shares'),
    # ('count_tweets', 'Retweets'),
    ('count_gplus_plusone', 'G+ Shares'),
    ('count_pins', 'Repins'),
    ('impressions', 'Views (valid for videos)')
    # ('post_actions_info', 'Actions'),
    # ('count_unique_impressions', 'Unique Impressions'),
    # ('count_unique_clickthroughs', 'Unique Clickthroughs'),
]


class CampaignReportTableSerializer(BaseTableSerializer, serializers.ModelSerializer):
    influencer_info = serializers.SerializerMethodField('get_influencer_info')
    post_date = serializers.SerializerMethodField('get_post_date')
    post_info = serializers.SerializerMethodField('get_post_info')
    post_type_info = serializers.SerializerMethodField('get_post_type_info')
    post_views = serializers.Field(source='count_impressions')
    post_likes = serializers.Field(source='post_likes')
    post_shares = serializers.SerializerMethodField('get_post_shares')
    post_comments = serializers.Field(source='post_num_comments')
    post_total = serializers.SerializerMethodField('get_post_total')
    post_actions_info = serializers.SerializerMethodField(
        'get_post_actions_info')
    count_fb_shares = serializers.Field(source='agr_fb_count')
    impressions = serializers.SerializerMethodField('get_impressions')

    FIELDS_DATA = CAMPAIGN_REPORT_TABLE_SERIALIZER_FIELDS_DATA

    FIELD_TEMPLATES = [
        ('influencer_info', 'snippets/post_analytics_blogger_info.html'),
        ('post_info', 'snippets/post_analytics_post_info.html'),
        ('post_type_info', 'snippets/post_analytics_post_type_info.html'),
        ('post_actions_info', 'snippets/post_analytics_post_actions_info.html')
    ]

    SORT_BY_FIELDS = [
        ('influencer_info', ('post.influencer.name')),
        ('post_info', ('post.title', 'post_url', '-post.create_date')),
        ('post_type_info', ('post_type')),
        ('post_date', ('post.create_date')),
        ('post_likes', ('post.engagement_media_numlikes')),
        ('post_shares', ('agr_post_shares_count')),
        ('post_comments', ('agr_post_comments_count')),
        ('post_total', ('agr_post_total_count')),
        ('count_fb_shares', ('agr_fb_count')),
        ('impressions', ('post.impressions')),
    ]

    UNSORTABLE_FIELDS = ['post_actions_info',]

    HIDDEN_FIELDS = ['id',]

    class Meta:
        model = models.PostAnalytics
        fields = OrderedDict(
            CAMPAIGN_REPORT_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2

    def transform_count_impressions(self, obj, value):
        try:
            if obj.post.platform.platform_name in models.Platform.SOCIAL_PLATFORMS:
                return 'N/A'
        except AttributeError:
            pass
        return value

    def transform_count_clickthroughs(self, obj, value):
        try:
            if obj.post.platform.platform_name in models.Platform.SOCIAL_PLATFORMS:
                return 'N/A'
        except AttributeError:
            pass
        return value

    def get_post_date(self, obj):
        try:
            return obj.post.create_date.strftime('%x')
        except AttributeError:
            pass

    def get_impressions(self, obj):
        if obj.ext_post_type in models.Platform.SOCIAL_PLATFORMS and obj.post:
            return obj.post.impressions

    def get_post_shares(self, obj):
        if obj.ext_post_type == 'Instagram':
            return 'N/A'
        return obj.post_shares

    def get_post_info(self, obj):
        data = {
            'pa_id': obj.id,
            'include_template': dict(self.FIELD_TEMPLATES).get('post_info'),
            'td_class': 'post_td',
        }

        if obj.post:
            data['post'] = {
                'title': obj.post.title,
                'url': obj.post.url,
                'img': obj.post.post_image,
            }
        return data

    def get_post_type_info(self, obj):
        data = {
            'pa_id': obj.id,
            'include_template': dict(self.FIELD_TEMPLATES).get('post_type_info'),
            'post_type': obj.ext_post_type,
        }
        return data

    def get_post_total(self, obj):
        try:
            return obj.agr_post_total_count
        except AttributeError:
            return sum(filter(None, [
                obj.post_likes,
                obj.post_shares,
                obj.post_num_comments,
            ]))

    def get_post_actions_info(self, obj):
        data = {
            'pa_id': obj.id,
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'post_actions_info'),
            'td_class': 'actions_td',
        }
        return data

    def get_influencer_info(self, obj):
        data = super(
            CampaignReportTableSerializer, self
        ).get_influencer_info(obj)
        data['is_blogger_approval'] = True
        return data


CAMPAIGN_REPORT_DATA_EXPORT_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('influencer_name', 'Blogger Name'),
    ('blog_url', 'Blog URL'),
    ('post_date', 'Date'),
    ('post_title', 'Post Title'),
    ('post_url', 'Url'),
    ('post_type', 'Type'),
    ('post_likes', 'Likes'),
    ('post_shares', 'Shares'),
    ('post_comments', 'Comments'),
    ('count_total', 'Total'),
    ('count_impressions', 'Impressions'),
    ('count_clickthroughs', 'Clickthroughs'),
    ('count_unique_impressions', 'Unique Impressions'),
    ('count_unique_clickthroughs', 'Unique Clickthroughs'),
]

class CampaignReportDataExportSerializer(CampaignReportTableSerializer):

    influencer_name = serializers.Field(source='post.influencer.name')
    blog_url = serializers.Field(source='post.influencer.blog_url')
    post_title = serializers.Field(source='post.title')
    post_url = serializers.Field(source='post.url')
    post_type = serializers.Field(source='ext_post_type')
    count_total = serializers.Field(source='agr_post_total_count')

    FIELDS_DATA = CAMPAIGN_REPORT_DATA_EXPORT_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = ['id',]

    SUM_FIELDS = [
        ('post_likes', 'post__engagement_media_numlikes'),
        ('post_shares', 'agr_post_shares_count'),
        ('post_comments', 'agr_post_comments_count'),
        ('count_total', 'agr_post_total_count'),
        ('count_impressions', 'count_impressions'),
        ('count_clickthroughs', 'count_clickthroughs'),
        ('count_unique_impressions', 'count_unique_impressions'),
        ('count_unique_clickthroughs', 'count_unique_clickthroughs'),
    ]

    class Meta:
        model = models.PostAnalytics
        fields = OrderedDict(
            CAMPAIGN_REPORT_DATA_EXPORT_SERIALIZER_FIELDS_DATA).keys()
        depth = 2


class BrandTaxonomySerializer(serializers.ModelSerializer):

    class Meta:
        model = models.BrandTaxonomy


BRAND_TAXONOMY_TABLE_SERIALIZER_FIELDS_DATA = [
    ('actions', 'Actions'),
    ('id', 'ID'),
    ('row_attributes', 'Attrs'),
    ('brand_name', 'Name'),
    ('source', 'Source'),
    ('repr_url', 'Representative URL'),
    ('style_tag', 'Style Tag'),
    ('product_tag', 'Product Tag'),
    ('price_tag', 'Price Tag'),
    ('keywords', 'Keywords'),
    ('hashtags', "#'s"),
    ('mentions', "@'s"),
    ('mention_urls', "@'s"),
    ('influencers_count', '# Influencers'),
    ('posts_count', '# Posts'),
    ('instagrams_count', '# Instys'),
    ('blog_posts_count', '# Blog Posts'),
]


class BrandTaxonomyTableSerializer(BaseTableSerializer,
        serializers.ModelSerializer):
    row_attributes = serializers.SerializerMethodField(
        'get_row_attributes')

    actions = serializers.SerializerMethodField('get_actions')
    influencers_count = serializers.Field(source='influencers_count')
    posts_count = serializers.Field(source='posts_count')
    instagrams_count = serializers.Field(source='instagrams_count')
    blog_posts_count = serializers.Field(source='blog_posts_count')

    brand_name = serializers.SerializerMethodField('get_brand_name')
    source = serializers.SerializerMethodField('get_source')
    repr_url = serializers.SerializerMethodField('get_repr_url')
    style_tag = serializers.SerializerMethodField('get_style_tag')
    product_tag = serializers.SerializerMethodField('get_product_tag')
    price_tag = serializers.SerializerMethodField('get_price_tag')
    keywords = serializers.SerializerMethodField('get_keywords')
    hashtags = serializers.SerializerMethodField('get_hashtags')
    mentions = serializers.SerializerMethodField('get_mentions')
    mention_urls = serializers.SerializerMethodField('get_mention_urls')

    influencers_count = serializers.SerializerMethodField('get_influencers_count')
    posts_count = serializers.SerializerMethodField('get_posts_count')
    instagrams_count = serializers.SerializerMethodField('get_instagrams_count')
    blog_posts_count = serializers.SerializerMethodField('get_blog_posts_count')

    FIELDS_DATA = BRAND_TAXONOMY_TABLE_SERIALIZER_FIELDS_DATA

    HIDDEN_FIELDS = ['row_attributes',]

    SORT_BY_FIELDS = [
        ('actions', ('modified',)),
    ]

    FIELD_TEMPLATES = [
        ('actions', 'snippets/brand_taxonomy/actions.html'),
        # ('brand_name', 'snippets/brand_taxonomy/brand_name.html'),
        # ('source', 'snippets/brand_taxonomy/source.html'),
        # ('repr_url', 'snippets/brand_taxonomy/repr_url.html'),
        # ('style_tag', 'snippets/brand_taxonomy/name.style_tag'),
        # ('product_tag', 'snippets/brand_taxonomy/product_tag.html'),
        # ('price_tag', 'snippets/brand_taxonomy/price_tag.html'),
        # ('keywords', 'snippets/brand_taxonomy/keywords.html'),
        # ('hashtags', 'snippets/brand_taxonomy/hashtags.html'),
        # ('mentions', 'snippets/brand_taxonomy/mentions.html'),
        # ('mention_urls', 'snippets/brand_taxonomy/mention_urls.html'),
    ]

    class Meta:
        model = models.BrandTaxonomy
        fields = [x[0] for x in BRAND_TAXONOMY_TABLE_SERIALIZER_FIELDS_DATA]
        depth = 2

    def get_row_attributes(self, obj):
        attrs = {
            'mailbox-table-row': 1,
            'mailbox-id': obj.id,
        }
        res = ' '.join(['{}="{}"'.format(k, v) for k, v in attrs.items()])
        return res

    @include_template
    def get_actions(self, obj):
        return {
            'modified': obj.modified.isoformat(),
            'disable_editing': True,
        }

    @editable_field()
    def get_brand_name(self, obj):
        pass

    @editable_field()
    def get_source(self, obj):
        pass

    @editable_field()
    def get_repr_url(self, obj):
        pass

    @editable_field()
    def get_style_tag(self, obj):
        pass

    @editable_field()
    def get_product_tag(self, obj):
        pass

    @editable_field()
    def get_price_tag(self, obj):
        pass

    @editable_field(field_type='textarea')
    def get_keywords(self, obj):
        pass

    @editable_field(field_type='textarea')
    def get_hashtags(self, obj):
        pass

    @editable_field(field_type='textarea')
    def get_mentions(self, obj):
        pass

    @editable_field(field_type='textarea')
    def get_mention_urls(self, obj):
        pass

    @editable_field(field_type='number', editable=False)
    def get_influencers_count(self, obj):
        pass

    @editable_field(field_type='number', editable=False)
    def get_posts_count(self, obj):
        pass

    @editable_field(field_type='number', editable=False)
    def get_instagrams_count(self, obj):
        pass

    @editable_field(field_type='number', editable=False)
    def get_blog_posts_count(self, obj):
        pass


CAMPAIGN_SETUP_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('campaign_id', 'Campaign ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('message_is_sent', 'Sent?'),
    ('row_attributes', 'Row Attributes'),
    # ('posts_info', 'Posts Info'),
    ('moved_manually', 'Moved Manually'),
    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    # ('open_count', 'Opens'),
    # ('messages_count', 'Messages'),
    # ('last_reply', 'Last Reply'),
    ('deliverables', 'Deliverables'),
    ('influencer_rate', 'Influencer Rate'),
    ('suggested_rate', 'Suggested Rate'),
    ('final_rate', 'Final Rate'),
    ('date_range', 'Date Range'),
    ('contract_actions', 'Actions'),
    ('contract_status', 'Contract Status'),
    ('rating', 'Rating'),
    ('reviews', 'Reviews'),
    ('post_links', 'Post Links'),
    ('blog_info', 'Blog'),
    ('twitter_info', 'Twitter'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('instagram_info', 'Instagram'),
    ('youtube_info', 'Youtube'),
    ('send_message_info', 'Send Message'),
    # ('next_stage_info', 'Move'),
    ('post_requirements', 'Post Requirements'),
    ('collect_details', 'Collect Details'),
    ('product_url', 'Product URL'),
    ('restrictions', 'Restrictions'),
    ('product_details', 'Product Details'),
    ('paypal', 'PayPal'),
    ('address', 'Address'),
    ('shipment_tracking_code', 'Shipment Tracking Code'),
    ('ship_date', 'Ship Date'),
    ('shipment_actions', 'Shipment Actions'),
    ('shipment_received_date', 'Package Received'),
    ('tracking_code_link', 'Tracking Codes'),
    ('payment_complete', 'Payment Complete'),
    ('discussion_requirements', 'Requirements'),
    ('global_details', 'Global Details'),
    ('product_info', 'Product Details'),
    ('contract_details', 'Contract Details'),
    ('review_details', 'Review Details'),
    ('shipping_details', 'Shipping Details'),
    ('tracking_code_details', 'Tracking Code Details'),
    ('post_approval_details', 'Post Approval Details'),
    ('influencer_notes', 'Notes'),
    ('template_context', 'Template Context'),
    ('done_logistics', 'Campaign Status'),
    ('restore', 'Restore'),
    ('displayed_rate', 'Displayed Rate'),
    ('send_followup', 'Send Reminder'),
    ('posts_adding_details', 'Posts Adding Details'),
    ('remove_info', 'Actions'),
]


class BaseCampaignSetupTableSerializer(BaseInfluencerReportTableSerializer):
    mailbox_id = serializers.Field(source='mailbox.id')
    contract_id = serializers.Field(source='contract_id')
    campaign_id = serializers.Field(source='job_id')
    has_been_read_by_brand = serializers.Field(
        source='mailbox.has_been_read_by_brand')
    signing_contract_on = serializers.SerializerMethodField(
        'get_signing_contract_on')
    message_is_sent = serializers.SerializerMethodField('get_message_is_sent')
    moved_manually = serializers.SerializerMethodField('get_moved_manually')
    influencer_notes = serializers.SerializerMethodField(
        'get_influencer_notes')
    template_context = serializers.SerializerMethodField(
        'get_template_context')
    subject = serializers.SerializerMethodField('get_subject')
    open_count = serializers.SerializerMethodField('get_open_count')
    messages_count = serializers.SerializerMethodField('get_messages_count')
    last_reply = serializers.SerializerMethodField('get_last_reply')
    deliverables = serializers.SerializerMethodField('get_deliverables_info')
    influencer_rate = serializers.SerializerMethodField('get_influencer_rate')
    suggested_rate = serializers.SerializerMethodField('get_suggested_rate')
    final_rate = serializers.SerializerMethodField('get_final_rate')
    date_range = serializers.SerializerMethodField('get_date_range')
    contract_actions = serializers.SerializerMethodField('get_contract_actions')
    details_form = serializers.SerializerMethodField('get_details_form')
    post_links = serializers.SerializerMethodField('get_post_links')
    rating = serializers.SerializerMethodField('get_rating')
    reviews = serializers.SerializerMethodField('get_reviews')
    send_message_info = serializers.SerializerMethodField(
        'get_send_message_info')
    contract_status = serializers.SerializerMethodField(
        'get_contract_status')
    row_attributes = serializers.SerializerMethodField(
        'get_row_attributes')
    next_stage_info = serializers.SerializerMethodField('get_next_stage_info')
    remove_info = serializers.SerializerMethodField('get_remove_info')
    collect_details = serializers.SerializerMethodField('get_collect_details')
    product_url = serializers.SerializerMethodField('get_product_url')
    restrictions = serializers.SerializerMethodField('get_restrictions')
    product_details = serializers.SerializerMethodField('get_product_details')
    paypal = serializers.SerializerMethodField('get_paypal')
    job_complete = serializers.SerializerMethodField('get_job_complete')
    date_requirements = serializers.SerializerMethodField('get_date_requirements')
    done_negotiating = serializers.SerializerMethodField('get_done_negotiating')
    post_requirements = serializers.SerializerMethodField('get_post_requirements')
    address = serializers.SerializerMethodField('get_address')
    shipment_tracking_code = serializers.SerializerMethodField(
        'get_shipment_tracking_code')
    ship_date = serializers.SerializerMethodField('get_ship_date')
    shipment_actions = serializers.SerializerMethodField('get_shipment_actions')
    shipment_received_date = serializers.Field(
        source='contract.shipment_received_date')
    tracking_code_link = serializers.SerializerMethodField(
        'get_tracking_code_link')
    payment_complete = serializers.SerializerMethodField(
        'get_payment_complete')
    discussion_requirements = serializers.SerializerMethodField(
        'get_discussion_requirements')
    global_details = serializers.SerializerMethodField(
        'get_global_details')
    product_info = serializers.SerializerMethodField(
        'get_product_info')
    contract_details = serializers.SerializerMethodField(
        'get_contract_details')
    review_details = serializers.SerializerMethodField(
        'get_review_details')
    restore = serializers.SerializerMethodField(
        'get_restore')
    shipping_details = serializers.SerializerMethodField(
        'get_shipping_details')
    tracking_code_details = serializers.SerializerMethodField(
        'get_tracking_code_details')
    post_approval_details = serializers.SerializerMethodField(
        'get_post_approval_details')
    done_logistics = serializers.SerializerMethodField(
        'get_done_logistics')
    displayed_rate = serializers.SerializerMethodField(
        'get_displayed_rate')
    send_followup = serializers.SerializerMethodField('get_send_followup')
    posts_adding_details = serializers.SerializerMethodField(
        'get_posts_adding_details')

    FIELD_TEMPLATES = BaseInfluencerReportTableSerializer.FIELD_TEMPLATES + [
        ('send_message_info', 'snippets/campaign_setup/send_message_info.html'),
        ('deliverables', 'snippets/campaign_setup/deliverables_info.html'),
        ('influencer_rate', 'snippets/campaign_setup/influencer_rate.html'),
        ('suggested_rate', 'snippets/campaign_setup/suggested_rate.html'),
        ('final_rate', 'snippets/campaign_setup/final_rate.html'),
        ('influencer_notes', 'snippets/campaign_setup/influencer_notes.html'),
        ('date_range', 'snippets/campaign_setup/date_range.html'),
        ('contract_actions', 'snippets/campaign_setup/contract_actions.html'),
        ('contract_status', 'snippets/campaign_setup/contract_status.html'),
        ('next_stage_info', 'snippets/campaign_setup/next_stage_info.html'),
        ('post_links', 'snippets/campaign_setup/post_links.html'),
        ('reviews', 'snippets/campaign_setup/reviews.html'),
        ('last_reply', 'snippets/campaign_setup/last_reply.html'),
        ('subject', 'snippets/campaign_setup/subject.html'),
        ('moved_manually', 'snippets/campaign_setup/moved_manually.html'),
        ('remove_info', 'snippets/campaign_setup/remove_info.html'),
        ('collect_details', 'snippets/campaign_setup/collect_details.html'),
        ('product_url', 'snippets/campaign_setup/product_url.html'),
        ('restrictions', 'snippets/campaign_setup/restrictions.html'),
        ('product_details', 'snippets/campaign_setup/product_details.html'),
        ('job_complete', 'snippets/campaign_setup/job_complete.html'),
        ('rating', 'snippets/campaign_setup/rating.html'),
        ('paypal', 'snippets/campaign_setup/paypal.html'),
        ('date_requirements', 'snippets/campaign_setup/date_requirements.html'),
        ('done_negotiating', 'snippets/campaign_setup/done_negotiating.html'),
        ('post_requirements', 'snippets/campaign_setup/post_requirements.html'),
        ('address', 'snippets/campaign_setup/address.html'),
        ('shipment_tracking_code', 'snippets/campaign_setup/shipment_tracking_code.html'),
        ('ship_date', 'snippets/campaign_setup/ship_date.html'),
        ('shipment_actions', 'snippets/campaign_setup/shipment_actions.html'),
        ('tracking_code_link', 'snippets/campaign_setup/tracking_code_link.html'),
        ('payment_complete', 'snippets/campaign_setup/payment_complete.html'),
        ('discussion_requirements', 'snippets/campaign_setup/discussion_requirements.html'),
        ('global_details', 'snippets/campaign_setup/global_details.html'),
        ('product_info', 'snippets/campaign_setup/product_info.html'),
        ('post_approval_details', 'snippets/campaign_setup/post_approval_details.html'),
        ('contract_details', 'snippets/campaign_setup/contract_details.html'),
        ('review_details', 'snippets/campaign_setup/review_details.html'),
        ('messages_count', 'snippets/campaign_setup/messages_count.html'),
        ('open_count', 'snippets/campaign_setup/open_count.html'),
        ('restore', 'snippets/campaign_setup/restore.html'),
        ('shipping_details', 'snippets/campaign_setup/shipping_details.html'),
        ('tracking_code_details', 'snippets/campaign_setup/tracking_code_details.html'),
        ('done_logistics', 'snippets/campaign_setup/done_logistics.html'),
        ('displayed_rate', 'snippets/campaign_setup/displayed_rate.html'),
        ('send_followup', 'snippets/campaign_setup/send_followup.html'),
        ('posts_adding_details', 'snippets/campaign_setup/posts_adding_details.html'),
    ]

    FIELDS_DATA = CAMPAIGN_SETUP_TABLE_SERIALIZER_FIELDS_DATA

    HIDDEN_FIELDS = [
        'id', 'mailbox_id', 'row_attributes', 'has_been_read_by_brand',
        'moved_manually', 'message_is_sent', 'contract_id', 'campaign_id',
        'signing_contract_on', 'template_context',
    ]

    SORT_BY_FIELDS = [
        ('moved_manually', ('moved_manually')),
        # ('influencer_notes', ('contract__influencer_notes')),
        ('open_count', ('agr_opened_count')),
        ('messages_count', ('agr_emails_count')),
        # ('last_reply', ('agr_last_message')),
        ('subject', ('agr_last_message')),
        ('influencer_rate', ('contract__starting_price')),
        ('suggested_rate', ('contract__suggested_price')),
        ('final_rate', ('contract__negotiated_price')),
        # ('reviews', ('contract__review')),
        ('contract_status', ('contract__status')),
        ('influencer_info', ('mailbox__influencer__name', 'influencer_analytics__influencer__name')),
        ('rating', ('contract__rating')),
        ('shipment_received_date', ('contract__shipment_received_date')),
        ('payment_complete', ('contract__payment_complete')),
        ('date_requirements', ('contract__date_requirements')),
    ]

    UNSORTABLE_FIELDS = BaseInfluencerReportTableSerializer.UNSORTABLE_FIELDS + [
        'subject', 'date_range', 'contract_actions', 'details_form',
        'post_links', 'send_message_info', 'deliverables',
        'remove_info', 'job_complete', 'paypal', 'reviews',
        'done_negotiating', 'post_requirements', 'address', 'shipment_tracking_code',
        'ship_date', 'shipment_actions', 'tracking_code_link', 'influencer_notes',
        'discussion_requirements', 'global_details', 'product_info',
        'contract_details', 'review_details', 'restore', 'product_url',
        'shipping_details', 'tracking_code_details', 'done_logistics',
        'displayed_rate', 'send_followup', 'posts_adding_details',
        'post_approval_details',
    ]

    def get_send_followup(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'send_followup'),
            'disable_editing': True,
            'followup_status': {
                'value': obj.contract.followup_status or 0,
                'name': obj.contract.followup_status_name,
                'color': obj.contract.followup_status_color,
            },
        }

    def get_displayed_rate(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'displayed_rate'),
            'displayed_rate': obj.contract.info_json.get('displayed_rate'),
        }

    def get_template_context(self, obj):
        # !!! NOT USED !!!
        return {}

    def get_signing_contract_on(self, obj):
        return obj.campaign.info_json.get('signing_contract_on', False)

    def get_restore(self, obj):
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'restore'),
            'campaign_stage_prev': obj.campaign_stage_prev if obj.campaign_stage_prev is not None else 0,
        }

    def get_review_details(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'review_details'),
            'disable_editing': True,
            'sending_product_on': obj.campaign.info_json.get('sending_product_on'),
            'blogger_page': '{}{}'.format(
                obj.contract.blogger_tracking_url, '#/4'),
        }

    def get_post_approval_details(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'post_approval_details'),
            'disable_editing': True,

        }

    def get_contract_details(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'contract_details'),
            'disable_editing': True,

        }

    def get_shipping_details(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'shipping_details'),
            'disable_editing': True,
        }

    def get_posts_adding_details(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'posts_adding_details'),
            'disable_editing': True,
        }

    def get_tracking_code_details(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'tracking_code_details'),
            'disable_editing': True,

        }

    def get_product_info(self, obj):
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'product_info'),
            'disable_editing': True,
            'restrictions_on': not obj.campaign.info_json.get('same_product_url') and obj.campaign.info_json.get('do_select_url'),
            'product_url_on': obj.campaign.info_json.get('product_links_on'),
        }

    def get_global_details(self, obj):
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'global_details'),
            'disable_editing': True,
            'description': obj.campaign.description,
            'who_should_apply': obj.campaign.who_should_apply,
            'mentions_required': obj.campaign.mentions_required,
            'hashtags_required': obj.campaign.hashtags_required,
            'campaign_name': obj.campaign.title,
            'client_url': obj.campaign.client_url,
            'client_name': obj.campaign.client_name,
        }

    def get_discussion_requirements(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'discussion_requirements'),
            'disable_editing': True,
        }

    def get_payment_complete(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'payment_complete'),
            'status': {
                'value': bool(obj.contract.payment_complete),
            },
        }

    def get_tracking_code_link(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'tracking_code_link'),
            'blogger_page_link': '{}{}'.format(
                obj.contract.blogger_tracking_url, ''),
            'blogger_contract_link': '{}{}'.format(
                obj.contract.blogger_tracking_url, '#/15'),
            'blogger_posts_link': '{}{}'.format(
                obj.contract.blogger_tracking_url, '#/16'),
            'tracking_code_link': '{}{}'.format(
                obj.contract.blogger_tracking_url, '#/14'),
            'blogger_shipment_link': '{}{}'.format(
                obj.contract.blogger_tracking_url, '#/13'),
            'post_approval_link': '{}{}'.format(
                obj.contract.blogger_tracking_url, '#/17'),
            'blogger_form_preview_link': '{}{}'.format(
                obj.contract.blogger_tracking_url, '?initial_form_preview=1'),
        }

    def get_shipment_tracking_code(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'shipment_tracking_code'),
            'shipment_tracking_code': obj.contract.shipment_tracking_code,
        }

    def get_ship_date(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'ship_date'),
            'ship_date': obj.contract.ship_date or datetime.datetime.now().date(),
            'disable_editing': True,
        }

    def get_shipment_actions(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'shipment_actions'),
            'status': {
                'value': obj.contract.shipment_status,
            },
        }

    def get_address(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'address'),
            'address': obj.contract.blogger_address,
        }

    def get_post_requirements(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'post_requirements'),
            'post_requirements': obj.post_requirements,
        }

    def get_done_negotiating(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'done_negotiating'),
            'stage': models.InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS,
        }

    def get_date_requirements(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'date_requirements'),
            'date': obj.date_requirements,
            'disable_editing': True,
        }

    def get_paypal(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'paypal'),
            'contract_id': obj.contract_id,
            'username': unescape(obj.paypal_username),
            'agent_name': unescape(obj.contract.info_json.get('agent_name')),
            'payment_terms': unescape(obj.contract.payment_terms),
            'payment_details_on': bool(obj.campaign.info_json.get(
                'payment_details_on')),
            'phone_number': obj.phone_number,
            'entity_name': unescape(obj.contract.publisher_name),
        }

    def get_job_complete(self, obj):
        if not obj.contract_id:
            return
        is_complete = (obj.campaign_stage == models.InfluencerJobMapping.
            CAMPAIGN_STAGE_COMPLETE)
        next_stage = (
            models.InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS
            if is_complete
            else models.InfluencerJobMapping.CAMPAIGN_STAGE_COMPLETE)
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'job_complete'),
            'is_complete': is_complete,
            'stage': next_stage,
        }

    def get_done_logistics(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'done_logistics'),
            'stage': models.InfluencerJobMapping.CAMPAIGN_STAGE_COMPLETE,
        }

    def get_collect_details(self, obj):
        if not obj.contract_id:
            return
        from debra.models import InfluencerJobMapping
        stage_settings = obj.contract.campaign.info_json.get(
            'stage_settings', {}).get(
                str(InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS), {})
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'collect_details'),
            'status': {
                'value': obj.contract.details_collected_status,
                'name': obj.contract.details_collected_status_name,
                'color': obj.contract.details_collected_status_color,
            },
            'send_contract': stage_settings.get('send_contract'),
            'preview_document_url': obj.contract.preview_document_url,
        }

    def get_product_url(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'product_url'),
            'product_url': obj.product_url,
            'product_urls': obj.product_urls,
            'product_sending_status': obj.campaign.product_sending_status,
        }

    def get_restrictions(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'restrictions'),
            'restrictions': obj.product_restrictions,
        }

    def get_product_details(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'product_details'),
            'details': obj.product_preferences,
            'brand_details': obj.product_details,
            'details_on': obj.campaign.info_json.get('blogger_additional_info_on'),
            # 'disable_editing': True,
            'status': obj.contract.details_collected_status,
        }

    def get_message_is_sent(self, obj):
        pass

    def get_remove_info(self, obj):
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'remove_info'),
            'CAMPAIGN_STAGE_ARCHIVED': models.InfluencerJobMapping.CAMPAIGN_STAGE_ARCHIVED,
            'next_stage': obj.campaign_stage + 1,
            'can_move_to_next_stage': self.context.get('brand') and\
                self.context.get('brand').flag_skipping_stages_enabled and \
                obj.campaign_stage in [
                    models.IJM.CAMPAIGN_STAGE_PRE_OUTREACH,
                    models.IJM.CAMPAIGN_STAGE_WAITING_ON_RESPONSE],
        }

    def get_influencer_info(self, obj):
        data = super(BaseCampaignSetupTableSerializer, self).get_influencer_info(
            obj)
        if data:
            data['disable_editing'] = True
            data['location'] = unicode(
                obj.influencer.demographics_locality) if obj.influencer.demographics_locality else None
        return data

    def get_moved_manually(self, obj):
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'moved_manually'),
            'moved_manually': obj.moved_manually,
        }

    def get_next_stage_info(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'next_stage_info'),
            'moved_manually': obj.moved_manually,
            'disable_editing': True,
            # 'contract_id': obj.contract.id,
            'mapping_id': obj.id,
            'stages': {
                'options': [{
                    'value': value,
                    'text': text
                } for value, text in models.InfluencerJobMapping.CAMPAIGN_STAGE],
                'selected': obj.campaign_stage,
                'field': 'campaign_stage',
            }
        }

    def get_row_attributes(self, obj):
        attrs = {
            'mailbox-table-row': 1,
            'mailbox-id': obj.mailbox_id,
            'update-url': reverse('debra.job_posts_views.update_model'),
            'contract-id': obj.contract_id,
            'class': ' '.join(c for c in [
                'mailbox',
                None if not obj.mailbox or obj.mailbox.has_been_read_by_brand else 'unread-message',
                'details_finalized' if obj.campaign_stage == obj.CAMPAIGN_STAGE_FINALIZING_DETAILS and obj.contract and obj.contract.details_collected_status == 2 else None,
                'disapproved_influencer' if obj.influencer_analytics_id and obj.influencer_analytics.approve_status == 2 else None,
            ] if c),
            'ng-class': "{removed_row: mailboxTableRow.removed, done_negotiation: angular.isNumber(mailboxTableRow.finalRateColumn.storedValues.finalRate), pending_influencer_action: mailboxTableRow.collectDetailsStatus.value == 1 || (mailboxTableRow.contractStatus.value > 0 && mailboxTableRow.contractStatus.value < 3) || (mailboxTableRow.shipmentStatus.value == 1)}",
            # 'initial-stage': obj.mailbox.campaign_stage,
        }
        res = ' '.join(['{}="{}"'.format(k, v) for k, v in attrs.items()])
        return res

    def get_contract_status(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'contract_status'),
            # 'contract_id': obj.contract.id,
            # 'contract_status': {
            #     'value': obj.contract.status,
            #     'name': obj.contract.status_name,
            #     'color': obj.contract.status_color,
            # },
        }

    def get_influencer_notes(self, obj):
        if not obj.influencer:
            return
        data = {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'influencer_notes'),
            'td_class': 'actions_td',
            'notes': obj.agr_notes,
            'influencer_id': obj.influencer.id,
            # 'brand_user_mapping_id': obj.agr_brand_user_mapping.id,
        }
        # if obj.influencer_analytics_id:
        #     data['influencer_analytics_id'] = obj.influencer_analytics_id
        #     data['notes'] = obj.influencer_analytics.notes
        # elif obj.contract_id:
        #     data['contract_id'] = obj.contract.id
        #     data['notes'] = obj.contract.influencer_notes
        # else:
        #     return
        return data

    def get_send_message_info(self, obj):
        if not obj.influencer:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'send_message_info'),
            'influencer': {
                'id': obj.influencer.id,
                'name': unescape(obj.influencer.name),
                'first_name': obj.influencer.first_name,
            },
            'campaign_overview_link': CampaignSerializer().get_overview_page_link(obj.campaign),
            'force_invite': obj.campaign.id,
        }

    def get_subject(self, obj):
        if not obj.mailbox or not obj.influencer:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'subject'),
            'influencer_name': obj.influencer.name,
            'subject': obj.agr_mailbox_subject,
            'opens_count': obj.agr_opened_count,
            'messages_count': obj.agr_emails_count,
            'last_sent': obj.agr_last_sent,
            'last_reply': obj.agr_last_reply,
            'last_message': obj.agr_last_message,
            'recent_date': 'last_sent' if obj.agr_last_sent == obj.agr_last_message else 'last_reply',
            'influencer': {
                'id': obj.influencer.id,
                'name': unescape(obj.influencer.name),
                'first_name': obj.influencer.first_name,
            },
            'force_invite': obj.campaign.id if obj.agr_emails_count == 0 else None,
            'disable_editing': True,
        }

    def get_open_count(self, obj):
        if not obj.mailbox or not obj.influencer:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'open_count'),
        }
        # try:
        #     return obj.agr_opened_count
        # except AttributeError:
        #     pass

    def get_messages_count(self, obj):
        if not obj.mailbox or not obj.influencer:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'messages_count'),
        }
        # try:
        #     return obj.agr_emails_count
        # except AttributeError:
        #     pass

    def get_last_reply(self, obj):
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'last_reply'),
            'last_sent': obj.agr_last_sent,
            'last_reply': obj.agr_last_reply,
            'last_message': obj.agr_last_message,
        }

    def get_deliverables_info(self, obj):
        if not obj.contract_id:
            return
        data = {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'deliverables'),
            'contract_id': obj.contract.id,
            'disable_editing': True,
        }
        data['deliverables'] = obj.contract.deliverables_json
        # try:
        #     data['deliverables'] = eval(obj.deliverables)
        # except:
        #     data['deliverables'] = obj.campaign.info_json.get(
        #         'deliverables', {})
        return data

    def get_influencer_rate(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'influencer_rate'),
            'contract_id': obj.contract.id,
            'influencer_rate': obj.contract.starting_price or 0,
        }

    def get_suggested_rate(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'suggested_rate'),
            'contract_id': obj.contract.id,
            'suggested_rate': obj.contract.suggested_price or 0,
        }

    def get_final_rate(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'final_rate'),
            'contract_id': obj.contract.id,
            'final_rate': obj.contract.negotiated_price or 0,
        }

    def get_date_range(self, obj):
        if not obj.contract_id:
            return
        data = {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'date_range'),
            'contract_id': obj.contract.id,
            'start_date': obj.contract.date_start,
            'latest_date': obj.contract.date_end,
            'disable_editing': True,
        }
        return data

    def get_contract_actions(self, obj):
        from debra.models import InfluencerJobMapping
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'contract_actions'),
            'contract_id': obj.contract.id,
            'mailbox_id': obj.mailbox.id,
            'preview_document_url': obj.contract.preview_document_url,
            'signed_document_url': obj.contract.signed_document_url,
            'next_stage': InfluencerJobMapping.CAMPAIGN_STAGE_LOGISTICS,
            'contract_status': {
                'value': obj.contract.status or 1,
                'name': obj.contract.status_name,
                'color': obj.contract.status_color,
                'non_sent_status': obj.contract.STATUS_NON_SENT,
                'signed_status': obj.contract.STATUS_SIGNED,
            },
            'tracking_status': {
                'value': obj.contract.tracking_status,
                'name': obj.contract.tracking_status_name,
                'color': obj.contract.tracking_status_color,
            },
            'shipment_status': {
                'value': obj.contract.shipment_status,
                'name': obj.contract.shipment_status_name,
                'color': obj.contract.shipment_status_color,
            },
            'followup_status': {
                'value': obj.contract.followup_status,
                'name': obj.contract.followup_status_name,
                'color': obj.contract.followup_status_color,
            },
            'posts_adding_status': {
                'value': obj.contract.posts_adding_status,
                'name': obj.contract.posts_adding_status_name,
                'color': obj.contract.posts_adding_status_color,
            },
            'post_approval_status': {
                'value': obj.contract.google_doc_status,
                'name': obj.contract.google_doc_status_name,
                'color': obj.contract.google_doc_status_color,
            },
        }

    def get_details_form(self, obj):
        return 'Details Form'

    def get_post_links(self, obj):
        if not obj.contract_id or not obj.influencer:
            return
        posts = self.context.get('posts', [])
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'post_links'),
            'links': [{
                'url': url,
                'title': unescape(title),
                'platform': 'Blog' if pl in models.Platform.BLOG_PLATFORMS else pl,
            } for url, title, pl, inf in posts if inf == obj.influencer.id]
        }

    def get_rating(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'rating'),
            'contract_id': obj.contract.id,
            'rating': obj.contract.rating,
            'disable_editing': True,
        }

    def get_reviews(self, obj):
        if not obj.contract_id:
            return
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'reviews'),
            'contract_id': obj.contract.id,
            'reviews': obj.contract.review,
        }


class CampaignSetupTableSerializer(BaseCampaignSetupTableSerializer):

    VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_TABLE_SERIALIZER_FIELDS_DATA]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2


UNLINKED_MESSAGES_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    # ('contract_id', 'Contract ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('open_count', 'Opens'),
    ('messages_count', 'Messages'),
    ('blog_info', 'Blog'),
    ('instagram_info', 'Instagram'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('twitter_info', 'Twitter'),
    ('youtube_info', 'Youtube'),
    # ('next_stage_info', 'Move'),
    ('influencer_notes', 'Notes'),
    ('mailbox_stage', 'Stage'),
]


class UnlinkedMessagesTableSerializer(BaseCampaignSetupTableSerializer):

    mailbox_stage = serializers.SerializerMethodField('get_mailbox_stage')

    FIELDS_DATA = UNLINKED_MESSAGES_TABLE_SERIALIZER_FIELDS_DATA

    FIELD_TEMPLATES = BaseCampaignSetupTableSerializer.FIELD_TEMPLATES + [
        ('mailbox_stage', 'snippets/campaign_setup/mailbox_stage.html'),
    ]

    SORT_BY_FIELDS = [
        ('moved_manually', ('moved_manually')),
        # ('influencer_notes', ('contract__influencer_notes')),
        ('open_count', ('agr_opened_count')),
        ('messages_count', ('agr_emails_count')),
        # ('last_reply', ('agr_last_message')),
        ('subject', ('agr_last_message')),
        ('influencer_rate', ('contract__starting_price')),
        ('suggested_rate', ('contract__suggested_price')),
        ('final_rate', ('contract__negotiated_price')),
        ('mailbox_stage', ('stage')),
        ('contract_status', ('contract__status')),
        ('influencer_info', ('influencer__name')),
    ]

    class Meta:
        model = models.MailProxy
        fields = OrderedDict(
            UNLINKED_MESSAGES_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2

    def get_mailbox_stage(self, obj):
        return {
            'include_template': dict(self.FIELD_TEMPLATES).get(
                'mailbox_stage'),
            'disable_editing': True,
            'stages': {
                'options': [{
                    'value': value,
                    'text': text
                } for value, text in models.MailProxy.STAGE],
                'selected': obj.stage,
                'field': 'stage',
            },
        }

    def get_row_attributes(self, obj):
        attrs = {
            'mailbox-table-row': 1,
            'mailbox-id': obj.mailbox.id,
            'update-url': reverse('debra.job_posts_views.update_model'),
            # 'contract-id': obj.contract_id,
            'class': ' '.join(c for c in [
                'mailbox',
                None if not obj.mailbox or obj.mailbox.has_been_read_by_brand else 'unread-message',
            ] if c),
            'ng-class': "{done_negotiation: !isNaN(mailboxTableRow.finalRate)}",
            # 'initial-stage': obj.mailbox.campaign_stage,
        }
        res = ' '.join(['{}="{}"'.format(k, v) for k, v in attrs.items()])
        return res


# CAMPAIGN_SETUP_ALL_TABLE_SERIALIZER_FIELDS_DATA = [
#     ('id', 'ID'),
#     ('mailbox_id', 'MailBox ID'),
#     ('contract_id', 'Contract ID'),
#     ('has_been_read_by_brand', 'Read?'),
#     ('row_attributes', 'Row Attributes'),
#     ('moved_manually', 'Moved Manually'),
#     ('influencer_info', 'Influencer'),
#     ('subject', 'Messages'),
#     ('blog_info', 'Blog'),
#     ('instagram_info', 'Instagram'),
#     ('pinterest_info', 'Pinterest'),
#     ('facebook_info', 'Facebook'),
#     ('twitter_info', 'Twitter'),
#     ('youtube_info', 'Youtube'),
#     # ('send_message_info', 'Send Message'),
#     # ('next_stage_info', 'Move'),
#     ('influencer_notes', 'Notes'),
#     # ('restore', 'Archive / Restore'),
#     # ('remove_info', 'Archive'),
# ]


CAMPAIGN_SETUP_ALL_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('campaign_id', 'Campaign ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),
    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('influencer_notes', 'Notes'),

    # hidden
    ('deliverables', 'Deliverables'),

    ('influencer_rate', 'Influencer Rate'),
    ('suggested_rate', 'Suggested Rate'),
    ('final_rate', 'Final Rate'),

    # hidden
    ('date_range', 'Date Range'),
    ('contract_actions', 'Actions'),

    # ('contract_status', 'Contract Status'),
    ('rating', 'Rating'),
    ('reviews', 'Reviews'),
    ('post_links', 'Post Links'),

    ('blog_info', 'Blog'),
    ('twitter_info', 'Twitter'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('instagram_info', 'Instagram'),
    ('youtube_info', 'Youtube'),
    # ('send_message_info', 'Send Message'),
    # ('next_stage_info', 'Move'),

    # hidden
    ('post_requirements', 'Post Requirements'),

    ('collect_details', 'Collect Details'),

    # hidden
    ('product_url', 'Product URL'),
    ('restrictions', 'Restrictions'),
    ('product_details', 'Product Details'),
    ('address', 'Address'),
    ('shipment_tracking_code', 'Shipment Tracking Code'),
    ('ship_date', 'Ship Date'),

    ('shipment_actions', 'Shipment Actions'),
    ('shipment_received_date', 'Package Received'),
    ('tracking_code_link', 'Tracking Codes'),
    ('discussion_requirements', 'Requirements'),
    ('global_details', 'Global Details'),
    ('product_info', 'Product Details'),
    ('contract_details', 'Contract Details'),
    ('review_details', 'Review Details'),
    ('shipping_details', 'Shipping Details'),
    ('tracking_code_details', 'Tracking Code Details'),
    ('post_approval_details', 'Post Approval Details'),
    ('template_context', 'Template Context'),
    ('done_logistics', 'Campaign Status'),
    ('displayed_rate', 'Displayed Rate'),
    ('send_followup', 'Send Reminder'),
    ('posts_adding_details', 'Posts Adding Details'),

    ('paypal', 'Payment'),
    ('payment_complete', 'Payment Complete'),
    ('job_complete', 'Campaign Status'),
    ('remove_info', 'Actions'),
]


class CampaignSetupAllTableSerializer(BaseCampaignSetupTableSerializer):

    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_ARCHIVED_TABLE_SERIALIZER_FIELDS_DATA]

    FIELDS_DATA = CAMPAIGN_SETUP_ALL_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = BaseCampaignSetupTableSerializer.HIDDEN_FIELDS + [
        'deliverables',
        'date_range',
        'contract_actions',
        'post_requirements',
        'product_url',
        'restrictions',
        'product_details',
        'address',
        'ship_date',
    ]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_ALL_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2



CAMPAIGN_SETUP_ARCHIVED_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),
    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('blog_info', 'Blog'),
    ('instagram_info', 'Instagram'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('twitter_info', 'Twitter'),
    ('youtube_info', 'Youtube'),
    # ('send_message_info', 'Send Message'),
    # ('next_stage_info', 'Move'),
    ('influencer_notes', 'Notes'),
    ('restore', 'Restore'),
    # ('remove_info', 'Delete'),
]


class CampaignSetupArchivedTableSerializer(BaseCampaignSetupTableSerializer):

    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_ARCHIVED_TABLE_SERIALIZER_FIELDS_DATA]

    FIELDS_DATA = CAMPAIGN_SETUP_ARCHIVED_TABLE_SERIALIZER_FIELDS_DATA

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_ARCHIVED_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2


CAMPAIGN_SETUP_PRE_OUTREACH_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('contract_id', 'Contract ID'),
    # ('mailbox_id', 'MailBox ID'),
    # ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    # ('posts_info', 'Posts Info'),
    # ('moved_manually', 'Moved Manually'),
    ('influencer_info', 'Influencer'),
    ('blog_info', 'Blog'),
    ('instagram_info', 'Instagram'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('twitter_info', 'Twitter'),
    ('youtube_info', 'Youtube'),
    ('send_message_info', 'Send Message'),
    ('influencer_notes', 'Notes'),
    # ('next_stage_info', 'Move'),
    ('remove_info', 'Actions'),
]


class CampaignSetupPreOutreachTableSerializer(BaseCampaignSetupTableSerializer):

    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_PRE_OUTREACH_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_PRE_OUTREACH_TABLE_SERIALIZER_FIELDS_DATA

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_PRE_OUTREACH_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2


CAMPAIGN_SETUP_WAITING_ON_RESPONSE_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),
    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('open_count', 'Opens'),
    ('messages_count', 'Messages'),
    ('send_followup', 'Send Reminder'),
    # ('last_reply', 'Last Reply'),
    ('influencer_notes', 'Notes'),
    # ('next_stage_info', 'Move'),
    ('remove_info', 'Actions'),
]


class CampaignSetupWaitingOnResponseTableSerializer(BaseCampaignSetupTableSerializer):
    
    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_WAITING_ON_RESPONSE_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_WAITING_ON_RESPONSE_TABLE_SERIALIZER_FIELDS_DATA

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_WAITING_ON_RESPONSE_TABLE_SERIALIZER_FIELDS_DATA
        ).keys()
        depth = 2


CAMPAIGN_SETUP_NEGOTIATION_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('campaign_id', 'Campaign ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),
    ('deliverables', 'Deliverables'),
    ('date_range', 'Date Range'),
    ('post_requirements', 'Post Requirements'),

    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    # ('deliverables', 'Deliverables'),
    ('discussion_requirements', 'Requirements'),
    ('influencer_rate', 'Influencer Rate'),
    ('suggested_rate', 'Suggested Rate'),
    ('final_rate', 'Final Rate'),
    ('displayed_rate', 'Displayed Rate'),
    ('done_negotiating', 'Actions'),
    ('instagram_info', 'Instagram'),
    ('blog_info', 'Blog'),
    ('facebook_info', 'Facebook'),
    ('pinterest_info', 'Pinterest'),
    ('twitter_info', 'Twitter'),
    ('youtube_info', 'Youtube'),
    # ('open_count', 'Opens'),
    # ('messages_count', 'Messages'),
    # ('last_reply', 'Last Reply'),
    # ('next_stage_info', 'Move'),
    ('influencer_notes', 'Notes'),
    ('remove_info', 'Actions'),
]


class CampaignSetupNegotiationTableSerializer(BaseCampaignSetupTableSerializer):
    
    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_NEGOTIATION_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_NEGOTIATION_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = BaseCampaignSetupTableSerializer.HIDDEN_FIELDS + [
        'deliverables',
        'date_range',
        'post_requirements',
    ]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_NEGOTIATION_TABLE_SERIALIZER_FIELDS_DATA
        ).keys()
        depth = 2


CAMPAIGN_SETUP_FINALIZING_DETAILS_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('deliverables', 'Deliverables'),
    ('campaign_id', 'Campaign ID'),
    ('moved_manually', 'Moved Manually'),
    ('influencer_info', 'Influencer'),
    # ('influencer_notes', 'Notes on Influencer'),
    ('subject', 'Messages'),

    ('blog_info', 'Blog'),
    ('instagram_info', 'Instagram'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('twitter_info', 'Twitter'),
    ('youtube_info', 'Youtube'),

    ('review_details', 'Review Details'),
    ('global_details', 'Campaign Details'),
    ('discussion_requirements', 'Requirements'),
    ('final_rate', 'Final Rate'),
    # ('open_count', 'Opens'),
    # ('messages_count', 'Messages'),
    # ('last_reply', 'Last Reply'),
    # ('deliverables', 'Deliverables'),

    ('date_range', 'Date Range'),
    ('date_requirements', 'Scheduled Post'),
    ('product_info', 'Product Info'),
    ('product_url', 'Product URL'),
    ('restrictions', 'Restrictions'),
    ('product_details', 'Product Details'),
    ('post_requirements', 'Post Requirements'),

    ('collect_details', 'Collect Details'),
    # ('contract_actions', 'Send Contract'),
    ('influencer_notes', 'Notes'),
    # ('next_stage_info', 'Move'),
    ('remove_info', 'Actions'),
]


class CampaignSetupFinalizingDetailsTableSerializer(BaseCampaignSetupTableSerializer):
    
    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_FINALIZING_DETAILS_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_FINALIZING_DETAILS_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = BaseCampaignSetupTableSerializer.HIDDEN_FIELDS + [
        'deliverables',
        'date_range',
        'post_requirements',
        'product_url',
        'restrictions',
        'product_details',
        'date_requirements',
        'global_details',
        'discussion_requirements',
        'product_info',
    ]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_FINALIZING_DETAILS_TABLE_SERIALIZER_FIELDS_DATA
        ).keys()
        depth = 2


CAMPAIGN_SETUP_CONTRACT_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('campaign_id', 'Campaign ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),
    ('signing_contract_on', 'Contract On'),

    ('date_range', 'Date Range'),
    ('product_url', 'Product URL'),
    ('restrictions', 'Restrictions'),
    ('product_details', 'Product Details'),
    ('deliverables', 'Deliverables'),
    ('paypal', 'PayPal email'),
    ('global_details', 'Campaign Details'),
    ('deliverables', 'Deliverables'),
    ('post_requirements', 'Post Requirements'),
    ('date_range', 'Date Range'),
    ('ship_date', 'Ship Date'),
    ('shipment_tracking_code', 'Shipment Tracking Code'),
    ('post_links', 'Post Links'),
    ('tracking_code_link', 'Tracking Code Page'),
    ('rating', 'Rating'),
    ('reviews', 'Reviews'),
    ('collect_details', 'Collect Details'),
    ('contract_actions', 'Contract Actions'),

    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('contract_details', 'Contract Details'),
    ('date_requirements', 'Scheduled Post'),
    ('final_rate', 'Final Rate'),
    # ('address', 'Address'),
    ('contract_actions', 'Actions'),
    ('remove_info', 'Actions'),
]


class CampaignSetupContractTableSerializer(BaseCampaignSetupTableSerializer):
    
    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_CONTRACT_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_CONTRACT_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = BaseCampaignSetupTableSerializer.HIDDEN_FIELDS + [
        'deliverables',
        'date_range',
        'post_requirements',
        'product_url',
        'restrictions',
        'product_details',
        'paypal',
        'global_details',
        'final_rate',
        'ship_date',
        'shipment_tracking_code',
        'post_links',
        'tracking_code_link',
        'rating',
        'reviews',
        'collect_details',
        'contract_actions',
    ]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_CONTRACT_TABLE_SERIALIZER_FIELDS_DATA
        ).keys()
        depth = 2


CAMPAIGN_SETUP_LOGISTICS_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('campaign_id', 'Campaign ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),

    ('date_range', 'Date Range'),
    ('restrictions', 'Restrictions'),
    ('deliverables', 'Deliverables'),
    ('deliverables', 'Deliverables'),
    ('post_requirements', 'Post Requirements'),
    ('date_range', 'Date Range'),
    ('paypal', 'PayPal email'),

    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('global_details', 'Campaign Details'),
    # ('discussion_requirements', 'Requirements'),
    ('contract_details', 'Contract Details'),
    ('product_url', 'Product URL'),
    ('product_details', 'Product Details'),
    ('contract_actions', 'Actions'),
    ('date_requirements', 'Scheduled Post'),
    ('final_rate', 'Final Rate'),
    ('address', 'Address'),

    ('shipment_tracking_code', 'Shipment Tracking Code'),
    ('ship_date', 'Ship Date'),
    ('shipment_actions', 'Actions'),
    # ('open_count', 'Opens'),
    # ('messages_count', 'Messages'),
    # ('last_reply', 'Last Reply'),
    # ('details_form', 'Details'),
    # ('next_stage_info', 'Move'),
    ('remove_info', 'Actions'),
]


class CampaignSetupLogisticsTableSerializer(BaseCampaignSetupTableSerializer):

    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_LOGISTICS_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_LOGISTICS_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = BaseCampaignSetupTableSerializer.HIDDEN_FIELDS + [
        'deliverables',
        'date_range',
        'post_requirements',
        # 'product_url',
        'restrictions',
        # 'product_details',
        'paypal',
        'global_details',
        'final_rate',
        'contract_actions',
    ]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_LOGISTICS_TABLE_SERIALIZER_FIELDS_DATA
        ).keys()
        depth = 2

    def get_next_stage_info(self, obj):
        data = super(
            CampaignSetupLogisticsTableSerializer, self).get_next_stage_info(obj)
        data['button_text'] = 'Ready'
        return data


CAMPAIGN_SETUP_UNDERWAY_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('campaign_id', 'Campaign ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),
    ('contract_actions', 'Actions'),
    ('deliverables', 'Deliverables'),
    ('global_details', 'Global Details'),
    ('date_range', 'Date Range'),
    ('post_requirements', 'Post Requirements'),
    ('final_rate', 'Final Rate'),
    ('paypal', 'PayPal'),


    ('product_url', 'Product URL'),
    ('restrictions', 'Restrictions'),
    ('product_details', 'Product Details'),
    ('global_details', 'Campaign Details'),
    ('ship_date', 'Ship Date'),
    ('shipment_tracking_code', 'Shipment Tracking Code'),
    ('tracking_code_link', 'Tracking Code Page'),
    ('rating', 'Rating'),
    ('reviews', 'Reviews'),
    ('collect_details', 'Collect Details'),
    ('address', 'Address'),
    ('template_context', 'Template Context'),


    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('shipment_received_date', 'Package Received'),
    ('date_requirements', 'Scheduled Post'),
    # ('open_count', 'Opens'),
    # ('messages_count', 'Messages'),
    # ('last_reply', 'Last Reply'),
    ('contract_details', 'Contract Details'),
    # ('tracking_code_link', 'Tracking Codes'),
    ('post_links', 'Post Links'),
    ('job_complete', 'Actions'),
    # ('next_stage_info', 'Move'),
    # ('influencer_notes', 'Notes'),
    ('remove_info', 'Actions'),
]


class CampaignSetupUnderwayTableSerializer(BaseCampaignSetupTableSerializer):

    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_UNDERWAY_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_UNDERWAY_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = BaseCampaignSetupTableSerializer.HIDDEN_FIELDS + [
        'deliverables',
        'date_range',
        'final_rate',
        'post_requirements',
        'restrictions',
        'paypal',
        'global_details',
        'final_rate',
        'contract_actions',

        'deliverables',
        'date_range',
        'product_url',
        'restrictions',
        'product_details',
        'paypal',
        'global_details',
        'final_rate',
        'ship_date',
        'shipment_tracking_code',
        # 'post_links',
        'tracking_code_link',
        'rating',
        'reviews',
        'collect_details',
        'contract_actions',
        # 'date_requirements',
        'address',
        'template_context',
    ]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_UNDERWAY_TABLE_SERIALIZER_FIELDS_DATA
        ).keys()
        depth = 2

    def get_next_stage_info(self, obj):
        data = super(
            CampaignSetupUnderwayTableSerializer, self).get_next_stage_info(obj)
        data['button_text'] = 'Complete'
        return data


CAMPAIGN_SETUP_COMPLETE_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('campaign_id', 'Campaign ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),

    ('date_range', 'Date Range'),
    ('product_url', 'Product URL'),
    ('restrictions', 'Restrictions'),
    ('product_details', 'Product Details'),
    ('deliverables', 'Deliverables'),
    ('global_details', 'Campaign Details'),
    ('post_requirements', 'Post Requirements'),
    ('date_range', 'Date Range'),
    ('ship_date', 'Ship Date'),
    ('shipment_tracking_code', 'Shipment Tracking Code'),
    ('shipment_received_date', 'Shipment Received Date'),
    ('tracking_code_link', 'Tracking Code Page'),
    ('collect_details', 'Collect Details'),
    ('contract_actions', 'Contract Actions'),
    ('displayed_rate', 'Displayed Rate'),
    ('address', 'Address'),
    ('template_context', 'Template Context'),

    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('contract_details', 'Details'),
    ('post_links', 'Post Links'),
    ('rating', 'Rating'),
    ('reviews', 'Reviews'),
    ('final_rate', 'Final Rate'),
    ('paypal', 'PayPal Username'),
    ('payment_complete', 'Payment Complete'),
    ('job_complete', 'Campaign Status'),
    ('remove_info', 'Actions'),
]


class CampaignSetupCompleteTableSerializer(BaseCampaignSetupTableSerializer):

    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_COMPLETE_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_COMPLETE_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = BaseCampaignSetupTableSerializer.HIDDEN_FIELDS + [
        'deliverables',
        'date_range',
        'post_requirements',
        'product_url',
        'restrictions',
        'product_details',
        'global_details',
        'displayed_rate',
        'ship_date',
        'shipment_tracking_code',
        'shipment_received_date',
        'tracking_code_link',
        'collect_details',
        'contract_actions',
        'address',
        'template_context',
    ]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_COMPLETE_TABLE_SERIALIZER_FIELDS_DATA
        ).keys()
        depth = 2


CAMPAIGN_SETUP_SANDBOX_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    ('mailbox_id', 'MailBox ID'),
    ('contract_id', 'Contract ID'),
    ('campaign_id', 'Campaign ID'),
    ('has_been_read_by_brand', 'Read?'),
    ('row_attributes', 'Row Attributes'),
    ('moved_manually', 'Moved Manually'),
    ('signing_contract_on', 'Contract On'),

    ('date_range', 'Date Range'),
    ('product_url', 'Product URL'),
    ('restrictions', 'Restrictions'),
    ('product_details', 'Product Details'),
    ('deliverables', 'Deliverables'),
    ('paypal', 'PayPal email'),
    ('global_details', 'Campaign Details'),
    ('deliverables', 'Deliverables'),
    ('post_requirements', 'Post Requirements'),
    ('date_range', 'Date Range'),
    ('ship_date', 'Ship Date'),
    ('shipment_tracking_code', 'Shipment Tracking Code'),
    ('shipment_received_date', 'Shipment Received Date'),
    ('tracking_code_link', 'Tracking Code Page'),
    ('rating', 'Rating'),
    ('reviews', 'Reviews'),
    ('collect_details', 'Collect Details'),
    ('contract_actions', 'Contract Actions'),
    ('final_rate', 'Final Rate'),
    ('displayed_rate', 'Displayed Rate'),
    ('address', 'Address'),
    ('template_context', 'Template Context'),

    ('influencer_info', 'Influencer'),
    ('subject', 'Messages'),
    ('contract_details', 'Details & Contract'),
    ('shipping_details', 'Shipment Status'),
    ('tracking_code_details', 'Distribute Tracking Codes'),
    ('post_approval_details', 'Post Approval'),
    ('posts_adding_details', 'Posts Adding Details'),
    ('date_requirements', 'Scheduled Post'),
    ('post_links', 'Post Links'),
    ('done_logistics', 'Campaign Status'),
    ('influencer_notes', 'Notes'),

    ('remove_info', 'Actions'),
]


class CampaignSetupSandboxTableSerializer(BaseCampaignSetupTableSerializer):
    
    # VISIBLE_COLUMNS = [x[0] for x in CAMPAIGN_SETUP_SANDBOX_TABLE_SERIALIZER_FIELDS_DATA]
    FIELDS_DATA = CAMPAIGN_SETUP_SANDBOX_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = BaseCampaignSetupTableSerializer.HIDDEN_FIELDS + [
        'deliverables',
        'date_range',
        'post_requirements',
        'product_url',
        'restrictions',
        'product_details',
        'paypal',
        'global_details',
        'final_rate',
        'displayed_rate',
        'ship_date',
        'shipment_tracking_code',
        'shipment_received_date',
        'tracking_code_link',
        'rating',
        'reviews',
        'collect_details',
        'contract_actions',
        'address',
        'template_context',
    ]

    class Meta:
        model = models.InfluencerJobMapping
        fields = OrderedDict(
            CAMPAIGN_SETUP_SANDBOX_TABLE_SERIALIZER_FIELDS_DATA
        ).keys()
        depth = 2


POST_ANALYTICS_TABLE_SERIALIZER_FIELDS_DATA = sum((
    POST_ANALYTICS_GROUP_FIELDS,
    # POST_ANALYTICS_POST_FIELDS,
    [('post_num_comments_info', 'Post Comments')],
    POST_ANALYTICS_SIMILAR_WEB_FIELDS,
    [
        ('count_clickthroughs', 'Clicks'),
        ('count_impressions', 'Impressions'),
    ],
    POST_ANALYTICS_SUMMARY_FIELDS,
    [
        ('id', 'ID'),
        ('post_num_comments', 'Post Comments'),
        ('count_tweets', 'Twitter Mentions'),
        ('count_fb', 'Facebook Shares'),
        ('count_gplus_plusone', 'Google+'),
        ('count_pins', 'Pinterest'),
    ],
), [])


class PostAnalyticsTableSerializer(BaseTableSerializer, serializers.ModelSerializer):

    blog_name = serializers.Field(source='post.influencer.blogname')
    blog_url = serializers.Field(source='post.influencer.blog_url')
    post_title = serializers.Field(source='post.title')
    post_url = serializers.Field(source='post_url')
    influencer_name = serializers.Field(source='post.influencer.name')
    post_num_comments = serializers.Field(source='post_num_comments')

    count_fb = serializers.Field(source='count_fb')
    count_clickthroughs = serializers.Field(source='count_clickthroughs')
    count_impressions = serializers.Field(source='count_impressions')
    count_total = serializers.Field(source='count_total')

    count_fb_info = serializers.SerializerMethodField('get_count_fb_info')
    count_gplus_plusone_info = serializers.SerializerMethodField(
        'get_count_gplus_plusone_info')
    count_pins_info = serializers.SerializerMethodField('get_count_pins_info')
    count_tweets_info = serializers.SerializerMethodField(
        'get_count_tweets_info')
    # count_total_info = serializers.SerializerMethodField('get_count_total_info')

    influencer_info = serializers.SerializerMethodField('get_influencer_info')
    post_url_info = serializers.SerializerMethodField('get_post_url_info')
    post_num_comments_info = serializers.SerializerMethodField(
        'get_post_num_comments_info')

    FIELDS_DATA = POST_ANALYTICS_TABLE_SERIALIZER_FIELDS_DATA

    POST_RELATED_FIELDS = dict(sum((
        POST_ANALYTICS_BLOGGER_FIELDS,
        POST_ANALYTICS_GROUP_FIELDS,
        POST_ANALYTICS_POST_FIELDS,
    ), [])).keys()

    FIELD_TEMPLATES = [
        ('influencer_info', 'snippets/post_analytics_blogger_info.html'),
        ('post_url_info', 'snippets/post_analytics_post_url.html'),
        ('post_num_comments_info',
            'snippets/post_analytics_num_comments.html'),
        ('count_fb_info', 'snippets/post_analytics_count_fb_info.html'),
        ('count_gplus_plusone_info', 'snippets/post_analytics_gplus_plusone_info.html'),
        ('count_pins_info', 'snippets/post_analytics_pin_info.html'),
        ('count_tweets_info', 'snippets/post_analytics_count_tweets_info.html'),
        # ('count_total_info', 'snippets/post_analytics_count_total_info.html'),
    ]

    SORT_BY_FIELDS = [
        ('influencer_info', ('post.influencer.name')),
        ('post_url_info', ('post.title', 'post_url', '-post.create_date')),
        ('post_num_comments_info', ('post_num_comments')),
        ('count_fb_info', ('count_fb')),
        ('count_gplus_plusone_info', ('count_gplus_plusone')),
        ('count_pins_info', ('count_pins')),
        ('count_tweets_info', ('count_tweets')),
        # ('count_total_info', ('count_total')),
    ]

    SUM_FIELDS = [
        ('post_num_comments_info', 'agr_num_comments'),
        ('count_fb_info', 'agr_count_fb'),
        ('count_gplus_plusone_info', 'count_gplus_plusone'),
        ('count_pins_info', 'count_pins'),
        ('count_tweets_info', 'count_tweets'),
        ('count_total', 'agr_count_total'),
        ('count_clickthroughs', 'count_clickthroughs'),
        ('count_impressions', 'count_impressions'),
    ]

    UNSORTABLE_FIELDS = []

    HIDDEN_FIELDS = [
        'id', 'post_num_comments', 'count_tweets', 'count_fb',
        'count_gplus_plusone', 'count_pins']

    class Meta:
        model = models.PostAnalytics
        fields = OrderedDict(
            POST_ANALYTICS_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2

    def get_post_url_info(self, obj):
        data = {
            'url': obj.post_url,
            'td_class': 'post_td',
        }
        if self.influencer_check(obj):
            data.update({
                'title': obj.post.title,
                'create_date': obj.post.create_date,
                'post_found': True,
                'post_image': obj.post.post_image,
            })
        else:
            data['post_found'] = False
        brand = self.get_brand(obj)
        if brand and brand.flag_show_dummy_data:
            data['url'] = constants.FAKE_POST_DATA['url']
            if data.get('title'):
                data['title'] = constants.FAKE_POST_DATA['title']
        data['include_template'] = dict(
            self.FIELD_TEMPLATES).get('post_url_info')
        data['pa_id'] = obj.id
        return data

    def get_post_num_comments_info(self, obj):
        data = {
            'num_comments': obj.post_num_comments,
            'include_template': dict(
                self.FIELD_TEMPLATES
            ).get('post_num_comments_info'),
            'pa_id': obj.id,
            'post_found': self.influencer_check(obj)
        }
        return data

    def get_count_info(self, obj, field_name):
        data = {
            'include_template': dict(self.FIELD_TEMPLATES).get(field_name + '_info'),
            'pa_id': obj.id,
            field_name: getattr(obj, field_name)
        }
        return data

    def get_count_fb_info(self, obj):
        return self.get_count_info(obj, 'count_fb')

    def get_count_gplus_plusone_info(self, obj):
        return self.get_count_info(obj, 'count_gplus_plusone')

    def get_count_pins_info(self, obj):
        return self.get_count_info(obj, 'count_pins')

    def get_count_tweets_info(self, obj):
        return self.get_count_info(obj, 'count_tweets')

    def get_count_total_info(self, obj):
        return self.get_count_info(obj, 'count_total')


POST_ANALYTICS_DATA_EXPORT_SERIALIZER_FIELDS_DATA = sum((
    POST_ANALYTICS_BLOGGER_FIELDS,
    POST_ANALYTICS_POST_FIELDS,
    [('count_tweets', 'Twitter Mentions'),
    ('count_fb', 'Facebook Shares'),
    ('count_gplus_plusone', 'Google+'),
    ('count_pins', 'Pinterest'),],
    [
        ('count_clickthroughs', 'Clicks'),
        ('count_impressions', 'Impressions'),
    ],
    POST_ANALYTICS_SUMMARY_FIELDS,
), [])


class PostAnalyticsDataExportSerializer(PostAnalyticsTableSerializer):

    FIELDS_DATA = POST_ANALYTICS_DATA_EXPORT_SERIALIZER_FIELDS_DATA

    HIDDEN_FIELDS = []

    SUM_FIELDS = [
        ('post_num_comments', 'agr_num_comments'),
        ('count_fb', 'agr_count_fb'),
        ('count_gplus_plusone', 'count_gplus_plusone'),
        ('count_pins', 'count_pins'),
        ('count_tweets', 'count_tweets'),
        ('count_total', 'agr_count_total'),
        ('count_clickthroughs', 'count_clickthroughs'),
        ('count_impressions', 'count_impressions'),
    ]

    class Meta:
        model = models.PostAnalytics
        fields = OrderedDict(
            POST_ANALYTICS_DATA_EXPORT_SERIALIZER_FIELDS_DATA).keys()
        depth = 2


POST_REPORT_TABLE_SERIALIZER_FIELDS_DATA = sum((
    # [('post_img_info', 'The Post')],
    [('post_url_info', 'Url'), ],
    [('post_num_comments_info', 'Post Comments')],
    POST_ANALYTICS_SIMILAR_WEB_FIELDS,
    POST_ANALYTICS_SUMMARY_FIELDS,
    [('virality_score', 'Virality Score')],
    # [('insights', 'Insights')],
    [('id', 'ID'), ('post_num_comments', 'Post Comments')],
), [])


class PostReportTableSerializer(PostAnalyticsTableSerializer):
    virality_score = serializers.Field(source='virality_score')
    insights = serializers.Field(source='insights')
    post_img_info = serializers.SerializerMethodField('get_post_img_info')

    FIELDS_DATA = POST_REPORT_TABLE_SERIALIZER_FIELDS_DATA

    FIELD_TEMPLATES = [
        ('post_img_info', 'snippets/post_analytics_post_img_info.html'),
        ('post_url_info', 'snippets/post_analytics_post_url.html'),
        ('post_num_comments_info',
            'snippets/post_analytics_num_comments.html'),
        ('count_fb_info', 'snippets/post_analytics_count_fb_info.html'),
        ('count_gplus_plusone_info', 'snippets/post_analytics_gplus_plusone_info.html'),
        ('count_pins_info', 'snippets/post_analytics_pin_info.html'),
        ('count_tweets_info', 'snippets/post_analytics_count_tweets_info.html'),
    ]

    SUM_FIELDS = [
        ('post_num_comments_info', 'agr_num_comments'),
        ('count_fb_info', 'agr_count_fb'),
        ('count_gplus_plusone_info', 'count_gplus_plusone'),
        ('count_pins_info', 'count_pins'),
        ('count_tweets_info', 'count_tweets'),
        ('count_total', 'agr_count_total'),
        ('count_clickthroughs', 'count_clickthroughs'),
        ('count_impressions', 'count_impressions'),
    ]

    NON_TOTAL_FIELDS = ['virality_score']

    class Meta:
        model = models.PostAnalytics
        fields = OrderedDict(
            POST_REPORT_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2

    def get_post_img_info(self, obj):
        data = {}
        data['post_found'] = self.influencer_check(obj)
        if data['post_found']:
            data['post_img'] = obj.post.post_img
        data['include_template'] = dict(
            self.FIELD_TEMPLATES).get('post_img_info')
        data['pa_id'] = obj.id
        return data


class PostAnalyticsUrlsSerializer(serializers.ModelSerializer):

    remove_url = serializers.Field(source='remove_url')

    class Meta:
        model = models.PostAnalytics
        fields = (
            'id', 'post_url', 'remove_url',
        )


INFLUENCER_REPORT_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    # ('posts_info', 'Posts Info'),
    ('influencer_info', 'Influencer'),
    ('twitter_info', 'Twitter'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('instagram_info', 'Instagram'),
    ('personal_engagement_score', 'Personal Engagement Score'),
]


class InfluencerReportTableSerializer(BaseInfluencerReportTableSerializer):

    FIELDS_DATA = INFLUENCER_REPORT_TABLE_SERIALIZER_FIELDS_DATA

    FIELD_TEMPLATES = [
        ('influencer_info', 'snippets/post_analytics_blogger_info.html'),
        ('twitter_info', 'snippets/twitter_info.html'),
        ('pinterest_info', 'snippets/pinterest_info.html'),
        ('facebook_info', 'snippets/facebook_info.html'),
        ('instagram_info', 'snippets/instagram_info.html'),
        ('posts_info', 'snippets/posts_info.html'),
    ]

    SORT_BY_FIELDS = [
        ('influencer_info', ('post.influencer.name')),
    ]

    SUM_FIELDS = [
    ]

    UNSORTABLE_FIELDS = [
        'twitter_info', 'pinterest_info', 'facebook_info', 'instagram_info',
        'personal_engagement_score', 'posts_info',]

    HIDDEN_FIELDS = ['id', 'posts_info']

    class Meta:
        model = models.PostAnalytics
        fields = OrderedDict(
            INFLUENCER_REPORT_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2


class BaseInfluencerApprovalReportTableSerializer(BaseInfluencerReportTableSerializer):

    row_attributes = serializers.SerializerMethodField(
        'get_row_attributes')
    open_profile = serializers.SerializerMethodField('get_open_profile')
    approve_info = serializers.SerializerMethodField('get_approve_info')
    influencer_notes = serializers.SerializerMethodField(
        'get_influencer_notes')
    influencer_client_notes = serializers.SerializerMethodField(
        'get_influencer_client_notes')
    remove_info = serializers.SerializerMethodField('get_remove_info')

    FIELD_TEMPLATES = [
        ('open_profile', 'snippets/open_profile.html'),
        ('influencer_info', 'snippets/post_analytics_blogger_info.html'),
        ('twitter_info', 'snippets/twitter_info.html'),
        ('pinterest_info', 'snippets/pinterest_info.html'),
        ('facebook_info', 'snippets/facebook_info.html'),
        ('instagram_info', 'snippets/instagram_info.html'),
        ('approve_info', 'snippets/approve_info.html'),
        # ('influencer_notes', 'snippets/campaign_setup/influencer_notes.html'),
        # ('influencer_client_notes', 'snippets/campaign_setup/influencer_notes.html'),
        ('remove_info', 'snippets/remove_info.html'),
    ]

    SORT_BY_FIELDS = [
        ('influencer_info', ('influencer.name',)),
        ('approve_info', ('tmp_approve_status',)),
    ]

    SUM_FIELDS = []

    UNSORTABLE_FIELDS = [
       'twitter_info', 'pinterest_info', 'facebook_info', 'instagram_info',
       'remove_info', 'influencer_notes', 'influencer_client_notes', 'open_profile',
    ]

    @include_template
    def get_remove_info(self, obj):
        return {
            'disable_editing': True,
            # 'archived': obj.approve_status == models.IA.APPROVE_STATUS_ARCHIVED,
            'archived': obj.archived,
            'stage_type': 'pre_outreach',
        }

    def get_influencer_info(self, obj):
        data = super(
            BaseInfluencerApprovalReportTableSerializer, self
        ).get_influencer_info(obj)
        data['is_blogger_approval'] = True
        data['propagate'] = True
        data['location'] = unicode(
            obj.influencer.demographics_locality) if obj.influencer.demographics_locality else None
        return data

    @include_template
    def get_open_profile(self, obj):
        pass

    def get_row_attributes(self, obj):
        attrs = {
            'table-row': 1,
            'ng-class': "{removed_row: tableRowCtrl.removed}",
            'mailbox-table-row': 1,
        }
        if obj.archived:
            attrs['removed'] = 1
        res = ' '.join(['{}="{}"'.format(k, v) for k, v in attrs.items()])
        return res

    def get_approve_info(self, obj):
        data = {}
        data['include_template'] = dict(self.FIELD_TEMPLATES).get(
            'approve_info')
        data['approve_status'] = models.IA.APPROVE_STATUS_PENDING\
            if obj.approve_status is None else obj.approve_status
        data['tmp_approve_status'] = models.IA.APPROVE_STATUS_PENDING\
            if obj.tmp_approve_status is None else obj.tmp_approve_status
        data['disable_editing'] = True
        # data['approve_status_name'] = obj.approve_status_name
        # data['approve_status_color'] = obj.approve_status_color
        return data

    def do_get_influencer_notes(self, obj):
        return {
            'default_values': {
                'influencer_id': obj.influencer.id,
                'user_id': self.context['request'].user.id,
            }
        }

    def do_get_influencer_client_notes(self, obj):
        pass

    @editable_field(field_type='textarea', placeholder='',
        related_obj_name='agr_brand_user_mapping', field_name='notes',
        model_name='InfluencerBrandUserMapping')
    def get_influencer_notes(self, obj):
        return self.do_get_influencer_notes(obj)

    @editable_field(field_type='textarea', placeholder='',
        field_name='client_notes')
    def get_influencer_client_notes(self, obj):
        return self.do_get_influencer_client_notes(obj)


INFLUENCER_APPROVAL_REPORT_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    # ('posts_info', 'Posts Info'),
    ('row_attributes', 'Row Attributes'),
    ('influencer_info', 'Influencer'),
    ('twitter_info', 'Twitter'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('instagram_info', 'Instagram'),
    ('open_profile',  'Profile'),
    ('approve_info', 'Approve'),
    ('influencer_notes', 'Notes To Your Client'),
    ('influencer_client_notes', 'Notes From Your Client'),
    ('remove_info', 'Actions'),
]


class InfluencerApprovalReportTableSerializer(BaseInfluencerApprovalReportTableSerializer):

    FIELDS_DATA = INFLUENCER_APPROVAL_REPORT_TABLE_SERIALIZER_FIELDS_DATA

    HIDDEN_FIELDS = ['id', 'approve_info', 'row_attributes', 'open_profile']
 
    class Meta:
        model = models.InfluencerAnalytics
        fields = OrderedDict(
            INFLUENCER_APPROVAL_REPORT_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2

    def do_get_influencer_client_notes(self, obj):
        data = super(InfluencerApprovalReportTableSerializer,
            self).do_get_influencer_client_notes(obj) or {}
        data.update({
            'disable_editing': True,
        })
        return data


PUBLIC_INFLUENCER_APPROVAL_REPORT_TABLE_SERIALIZER_FIELDS_DATA = [
    ('id', 'ID'),
    # ('posts_info', 'Posts Info'),
    ('row_attributes', 'Row Attributes'),
    ('influencer_info', 'Influencer'),
    ('twitter_info', 'Twitter'),
    ('pinterest_info', 'Pinterest'),
    ('facebook_info', 'Facebook'),
    ('instagram_info', 'Instagram'),
    ('open_profile',  'Profile'),
    ('approve_info', 'Approve'),
    ('influencer_notes', u'Notes From {}'),
    ('influencer_client_notes', 'Your Notes'),
    ('remove_info', 'Remove'),
]


class PublicInfluencerApprovalReportTableSerializer(BaseInfluencerApprovalReportTableSerializer):

    FIELDS_DATA = PUBLIC_INFLUENCER_APPROVAL_REPORT_TABLE_SERIALIZER_FIELDS_DATA
    HIDDEN_FIELDS = ['id', 'remove_info', 'row_attributes']

    CALCULATED_FIELD_NAMES = {
        'influencer_notes': lambda x: 1
    }

    class Meta:
        model = models.InfluencerAnalytics
        fields = OrderedDict(
            PUBLIC_INFLUENCER_APPROVAL_REPORT_TABLE_SERIALIZER_FIELDS_DATA).keys()
        depth = 2

    @classmethod
    def get_influencer_notes_header_name(cls, context=None):
        context = context or {}
        return dict(cls.FIELDS_DATA).get('influencer_notes').format(
            context['user'].userprofile.first_name)

    def do_get_influencer_notes(self, obj):
        data = super(PublicInfluencerApprovalReportTableSerializer,
            self).do_get_influencer_notes(obj) or {}
        data.update({
            'disable_editing': True,
        })
        return data

    def get_influencer_info(self, obj):
        data = super(PublicInfluencerApprovalReportTableSerializer, self).get_influencer_info(obj)
        data['disable_editing'] = True
        return data


def count_totals(qs, serializer_class, with_fields=False):
    totals = {}
    vals = qs.values(*([x[1] for x in serializer_class.SUM_FIELDS]))
    mapping = dict((y, x) for x, y in serializer_class.SUM_FIELDS)
    for val in vals:
        for field, value in val.items():
            tmp = mapping[field]
            totals[tmp] = totals.get(tmp, 0) + (value or 0)

    fields = serializer_class().get_fields().keys()
    total_values = map(totals.get, fields)

    count_total = totals.get('count_total', 1) or 1
    percentage = [None if total is None else '{}%'.format(
        int(round(total * 100.0 / count_total))) for total in total_values]

    if with_fields:
        total_values = zip(fields, total_values)
        percentage = zip(fields, percentage)

    return {
        'total_values': total_values,
        'percentage': percentage,
    }


def serialize_post_analytics_data(paginated_qs, serializer_class, serializer_context=None):
    t = time.time()

    serializer_instance = serializer_class(
        paginated_qs, many=True, context=serializer_context)
    serialized_qs = serializer_instance.data

    print '* serialization time', time.time() - t

    return {
        'data_list': serialized_qs,
        'data_count': len(serialized_qs),
    }


########## </ Analytics/Reporting Serializers > ##########

class WritableJSONField(serializers.WritableField):

    def to_native(self, value):
        from debra.helpers import escape_angular_interpolation
        try:
            # return json.loads(escape_angular_interpolation(value))
            return json.loads(value)
        except:
            return {}

    def from_native(self, value):
        from debra.helpers import escape_angular_interpolation
        try:
            return escape_angular_interpolation(
                json.dumps(value))
            # return json.dumps(value)
        except:
            pass


class DictField(serializers.WritableField):

    def to_native(self, value):
        return value

    def from_native(self, value):
        return value


class CampaignSerializer(serializers.ModelSerializer):
    campaign_sections = serializers.SerializerMethodField(
        'get_campaign_sections')
    date_range = DictField(source='date_range')
    cover_img_upload_url = serializers.SerializerMethodField(
        'get_cover_img_upload_url')
    profile_img_upload_url = serializers.SerializerMethodField(
        'get_profile_img_upload_url')
    cover_img_size = serializers.SerializerMethodField(
        'get_cover_img_size')
    profile_img_size = serializers.SerializerMethodField(
        'get_profile_img_size')
    send_invitation_url = serializers.SerializerMethodField(
        'get_send_invitation_url')
    load_influencers_url = serializers.SerializerMethodField(
        'get_load_influencers_url')
    overview_page_url = serializers.SerializerMethodField(
        'get_overview_page_url')
    overview_page_link = serializers.SerializerMethodField(
        'get_overview_page_link')
    contract_preview_url = serializers.SerializerMethodField(
        'get_contract_preview_url')
    outreach_template = WritableJSONField()
    info = WritableJSONField()
    template_context = serializers.SerializerMethodField('get_template_context')
    product_urls = serializers.WritableField()
    post_approval_enabled = serializers.Field(
        source='creator.flag_post_approval_enabled')
    has_already_loaded_influencers = serializers.SerializerMethodField(
        'get_has_already_loaded_influencers')

    class Meta:
        model = models.BrandJobPost
        fields = (
            'id', 'report', 'profile_img_url', 'cover_img_url',
            'date_range', 'title', 'client_name', 'template_context',
            'client_url', 'outreach_template', 'info', 'posts_saved_search',
            'description', 'who_should_apply', 'send_invitation_url',
            'hashtags_required', 'mentions_required', 'cover_img_size',
            'details', 'cover_img_upload_url', 'profile_img_upload_url',
            'campaign_sections', 'load_influencers_url', 'profile_img_size',
            'overview_page_url', 'contract_preview_url', 'overview_page_link',
            'product_urls', 'post_approval_enabled',
            'has_already_loaded_influencers', 'creator',
        )

    def transform_product_urls(self, obj, value):
        if not value:
            value = [""]
        return value

    def transform_outreach_template(self, obj, value):
        from debra.helpers import escape_angular_interpolation
        if not value:
            value.update({
                'template': '\n'.join([
                    "<p>Hi {{ getEscaped('user.first_name') }}!</p>",
                    "<p>I stumbled across your blog a few month ago and bookmarked your site! I LOVE your style and photography so much!!</p>",
                    "<p>I was wondering if you'd be interested in working together? Here is a link to my site for you to check out <a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a></p>",
                    "<p>I have a few ideas for how we could collaborate but I just wanted to check with you to see if this sounds interesting!</p>",
                    "<p>Thanks!</p>",
                    "<p>{{ context.visitorUserName }}<br/>",
                        "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                    "</p>",
                    "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
                ]),
                'subject': 'Interested in Collaborating?',
            })
        return value
        # value = json.dumps(value)
        # return json.loads(escape_angular_interpolation(value))

    def transform_info(self, obj, value):
        from debra.helpers import escape_angular_interpolation
        if value.get('payment_terms') is None:
            value['payment_terms'] = 'within 15 days of the last required post going live'
        if value.get('shipping_address_on') is None:
            value['shipping_address_on'] = True
        if value.get('payment_details_on') is None:
            value['payment_details_on'] = True
        if not value.get('post_approval_template'):
            value['post_approval_template'] = {
                'template': '\n'.join([
                    "<p>Hey {{ getEscaped('user.first_name') }},</p></br>",
                    "<p>I know that your post date is coming up so I wanted to send over a quick reminder about submitting your post for approval before making the post live. It's easy, I promise!</p></br>",
                    "<p>Just go to this <a href='{{ getEscaped('user.blogger_page_post_approval_section') }}'>link</a>. Use the text box to paste in your post and photos. Don't worry about formatting, I just need to see the flow and the text to make sure everything is on-brand.</p></br>",
                    "<p>When you're finished click the button on your Campaign Dashboard in order to let me know that you're finished.</p></br>",
                    "<p>Can't wait to see everything!</p></br>",
                     "<p>{{ context.visitorUserName }}<br/>",
                        "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                    "</p>",
                    "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
                ]),
                'subject': obj.outreach_template_json.get('subject') if\
                    obj.outreach_template_json else '',
            }
        if not value.get('collect_details_template'):
            value['collect_details_template'] = {
                'template': '\n'.join([
                    "<p>Hey {{ getEscaped('user.first_name') }},</p></br>",
                    "<p>Now that we have gone through the logistics, I just need you to fill out this quick form that goes through the details of the campaign.</p>",
                    "<p>You can find the form here:{{ getEscaped('user.collect_info_link') }}.</p>",
                    "<p>Please scroll down, review the details that are pre-filled, and make sure they are correct. Also, you will need to fill in the remaining fields at the bottom so that we can get started.</p></br>",
                    "<p>Thanks so much!</p></br>",
                    "<p>{{ context.visitorUserName }}<br/>",
                        "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                    "</p>",
                    "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
                ]),
                'subject': obj.outreach_template_json.get('subject') if\
                    obj.outreach_template_json else '',
            }
        if not value.get('reminder_template'):
            value['reminder_template'] = {
                'template': '\n'.join([
                    "<p>Hey {{ getEscaped('user.first_name') }},</p>",
                    "<p>I just wanted to shoot you a quick reminder about your upcoming post! Whoohoo! I'm so excited for it to go live!</p>",
                    "<p>Just for your quick reference, here is a <a href='{{ getEscaped('user.blogger_page') }}'>link</a> to your campaign overview page with all of the details pertaining to the campaign.",
                    "<p>And here is a <a href='{{ getEscaped('user.blogger_page_tracking_section') }}'>link</a> to your tracking codes. There are instructions on that page that will explain how to install them. It's super quick, I promise!</p>",
                    "<p>Let me know if you need anything else form my end!</p>",
                    "<p>Thanks again!</p>",
                    "<p>{{ context.visitorUserName }}<br/>",
                        "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                    "</p>",
                    "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
                ]),
                'subject': obj.outreach_template_json.get('subject') if\
                    obj.outreach_template_json else '',
            }
        if not value.get('followup_template'):
            value['followup_template'] = {
                'template': '\n'.join([
                    "<p>Hi {{ getEscaped('user.first_name') }},</p>",
                    "<p>Just wanted to follow back up with you to see if you got my previous email about a potential collaboration.",
                    "<p>I'd love to work with you and I have some great ideas around how we can set this up.",
                    "<p>Please let me know what you think, </p>",
                    "<p>{{ context.visitorUserName }}<br/>",
                        "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                    "</p>",
                    "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
                ]),
                'subject': obj.outreach_template_json.get('subject') if\
                    obj.outreach_template_json else '',
            }
        if not value.get('payment_complete_template'):
            value['payment_complete_template'] = {
                'template': '\n'.join([
                    "<p>Hey {{ getEscaped('user.first_name') }},</p>",
                    "<p>Just wanted to let you know that we've completed the payment!</p>",
                    "<p>It's been a pleasure working with you, and we hope to collaborate again with you soon!</p>",
                    "Thanks!",
                    "<p>{{ context.visitorUserName }}<br/>",
                        "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                    "</p>",
                    "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
                ]),
                'subject': obj.outreach_template_json.get('subject') if\
                    obj.outreach_template_json else '',
            }
        if not value.get('posts_adding_template'):
            value['posts_adding_template'] = {
                'template': '\n'.join([
                    "<p>Hey {{ getEscaped('user.first_name') }},</p>",
                    "<p>I'm so excited that your posts are going up!</p>",
                    "<p>I just wanted to shoot you over one final thing... can you go to this <a href='{{ getEscaped('user.blogger_page_posts_section') }}'>page</a> and enter in your post urls whenever you finish them up.</p>",
                    "<p>This will just help me to keep track of everything so that I don't miss any of your lovely content. =)</p>",
                    "<p>Thanks again!</p>",
                    "<p>{{ context.visitorUserName }}<br/>",
                        "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                    "</p>",
                ]),
                'subject': obj.outreach_template_json.get('subject') if\
                    obj.outreach_template_json else '',
            }
        if not value.get('shipping_template'):
            value['shipping_template'] = {
                'template': '\n'.join([
                    "<p>Hey {{ getEscaped('user.first_name') }},</p>",
                    "<p>Just wanted to let you know your package is in the mail! In case you need it, here's the tracking code: {{ getEscaped('user.shipment_tracking_code') }}</p>",
                    "<p>Would you mind doing me a quick favor? Whenever you get the package, would you mind coming back to this email and clicking the link below so that I know you have everything that you need?</p>",
                    "<p><a href='{{ getEscaped('user.shipment_received_url') }}'>{{ getEscaped('user.shipment_received_url') }}</a></p>",
                    "<p>Thank you so much! That's going to really help me! And looking forward to getting started!!!</p>",
                    "<p>{{ context.visitorUserName }}<br/>",
                        "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                    "</p>",
                    "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
                ]),
                'subject': obj.outreach_template_json.get('subject') if\
                    obj.outreach_template_json else '',
            }
        if not value.get('restrictions'):
            value['restrictions'] = ''.join([
                "Please select any product on our website and enter the",
                " url here.",
            ])
        if not value.get('blogger_additional_info'):
            value['blogger_additional_info'] = ''.join([
                "Please let us know any additional information about your ",
                "product that we'll need in order to send you the correct",
                " item, like size and/or color.",
            ])
        if not value.get('payment_instructions'):
            value['payment_instructions'] = ''.join([
                "Please let us know your preferred ",
                "method of payment. We can use Paypal, wire transfers, or checks.",
                " Depending on which option you prefer, please provide additional information",
                " (i.e. your Paypal address,",
                " routing information, or address)."
            ])
        if not value.get('deliverables'):
            value['deliverables'] = {
                'Instagram': {
                    'value': None,
                    'single': 'instagram',
                    'plural': 'instagrams'
                },
                'Twitter': {
                    'value': None,
                    'single': 'tweet',
                    'plural': 'tweets'
                },
                'Pinterest': {
                    'value': None,
                    'single': 'pin',
                    'plural': 'pins'
                },
                'Facebook': {
                    'value': None,
                    'single': 'facebook post',
                    'plural': 'facebook posts'
                },
                'Youtube': {
                    'value': None,
                    'single': 'video',
                    'plural': 'videos'
                },
                'Blog': {
                    'value': None,
                    'single': 'blog post',
                    'plural': 'blog posts'
                },
            }
        return value
        # value = json.dumps(value)
        # return json.loads(escape_angular_interpolation(value))

    def get_template_context(self, obj):
        request = self.context['request']
        return {
            'campaign_overview_link': self.get_overview_page_link(obj),
            'context': {
                'visitor_user_name': request.visitor['user'].name,
                'visitor_user_first_name': request.visitor['user'].first_name,
                'visitor_brand_domain_name': request.visitor['brand'].domain_name,
                'visitor_brand_name': request.visitor['brand'].name,
            }
        }

    def get_has_already_loaded_influencers(self, obj):
        return obj.candidates.count() > 0

    def get_date_range(self, obj):
        return {
            'start_date': obj.date_start,
            'end_date': obj.date_end,
        }

    def get_overview_page_url(self, obj):
        return reverse(
            'debra.job_posts_views.campaign_overview_page',
            args=(obj.id,)
        )

    def get_overview_page_link(self, obj):
        return ''.join([
            constants.MAIN_DOMAIN,
            self.get_overview_page_url(obj),
        ])

    def get_contract_preview_url(self, obj):
        return reverse(
            'debra.job_posts_views.download_campaign_contract_document_preview',
            args=(obj.id,)
        )

    def get_load_influencers_url(self, obj):
        return reverse(
            'debra.job_posts_views.campaign_load_influencers',
            args=(obj.id,)
        )

    def get_cover_img_upload_url(self, obj):
        return reverse('masuka.image_manipulator.upload_campaign_cover')

    def get_profile_img_upload_url(self, obj):
        return ''.join([
            reverse('masuka.image_manipulator.image_upload'),
            '?profile_img=1&campaign={}'.format(obj.id)
        ])

    def get_cover_img_size(self, obj):
        from masuka.image_manipulator import IMAGE_SIZES
        return ':'.join(map(str, IMAGE_SIZES['cover']))

    def get_profile_img_size(self, obj):
        from masuka.image_manipulator import IMAGE_SIZES
        return ':'.join(map(str, IMAGE_SIZES['profile']))

    def get_send_invitation_url(self, obj):
        return reverse('debra.job_posts_views.send_invitation')

    def get_campaign_sections(self, obj):
        from debra.helpers import PageSectionSwitcher
        return PageSectionSwitcher(
            constants.CAMPAIGN_SECTIONS, 'settings',
            url_args=(obj.id,),
            extra_url_args={'influencer_approval': (obj.report_id,)},
            hidden=[] if obj.info_json.get('approval_report_enabled', False) else ['influencer_approval'],
        ).to_dict()

    def save_object(self, obj, *args, **kwargs):
        from masuka.image_manipulator import reassign_campaign_cover
        obj.date_start = self.data.get('date_range', {}).get('start_date')
        obj.date_end = self.data.get('date_range', {}).get('end_date')
        if obj.creator_user is None:
            obj.creator_user = self.context.get('request').user
        value = super(CampaignSerializer, self).save_object(obj, *args, **kwargs)
        if obj.cover_img_url and "tmp_cover_img" in obj.cover_img_url:
            reassign_campaign_cover(obj)
        return value


class SiteConfigurationSerializer(serializers.ModelSerializer):
    stripe_plans = WritableJSONField()
    docusign_documents = WritableJSONField()
    blogger_custom_data = WritableJSONField()

    class Meta:
        model = models.BrandJobPost
        fields = ('id', 'stripe_plans', 'docusign_documents',
            'blogger_custom_data',)



class ContractSerializer(serializers.ModelSerializer):
    endpoints = serializers.SerializerMethodField('get_endpoints')

    blogger_posts = serializers.Field(source='blogger_posts')

    class Meta:
        model = models.Contract
        fields = ('id', 'endpoints', 'blogger_posts',)

    def get_endpoints(self, obj):
        return {}


class CustomDataInfluencerSerializer(serializers.ModelSerializer):

    location = serializers.SerializerMethodField('get_location')
    
    class Meta:
        model = models.Influencer
        fields = ('id', 'email', 'name', 'blogname', 'insta_url',
            'youtube_url', 'snapchat_username', 'tw_url', 'fb_url',
            'pin_url', 'blog_url',)

    def get_location(self, obj):
        return obj.demographics_location_normalized


class CustomDataLocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.DemographicsLocality
        fields = ('country', 'city', 'state',)


class InfluencerBrandMappingSerializer(serializers.ModelSerializer):

    metadata = serializers.SerializerMethodField('get_metadata')
    influencer_data = serializers.SerializerMethodField('get_influencer_data')
    location_data = serializers.SerializerMethodField('get_location_data')

    categories = serializers.WritableField()
    occupation = serializers.WritableField()
    tags = serializers.WritableField()
    sex = serializers.WritableField()
    ethnicity = serializers.WritableField()
    language = serializers.WritableField()

    class Meta:
        model = models.InfluencerBrandMapping
        fields = ('id', 'influencer', 'brand', 'cell_phone', 'representation',
            'rep_email_address', 'rep_phone', 'language', 'zip_code', 'mailing_address',
            'categories', 'occupation', 'sex', 'age', 'ethnicity', 'tags', 'metadata',
            'influencer_data', 'location_data', 'notes', 'date_of_birth',)

    def get_influencer_data(self, obj):
        return CustomDataInfluencerSerializer(obj.influencer).data

    def get_location_data(self, obj):
        data = CustomDataLocationSerializer(obj.influencer.demographics_locality).data
        # data['location'] = obj.influencer.demographics_location_normalized
        data['location'] = InfluencerSerializer().get_demographics_location(obj.influencer)
        return data

    def get_metadata(self, obj):
        # metadata = models.InfluencerBrandMapping().get_metadata()
        if self.context and self.context.get('metadata'):
            metadata = self.context.get('metadata')
        else:
            metadata = models.SiteConfiguration.objects.get(
                id=constants.SITE_CONFIGURATION_ID).blogger_custom_data_json

        metadata['language_choices'] = [{
            'name': choice,
            'selected': choice in (obj.language or [])
        } for choice in metadata['language_choices']]

        metadata['occupation_choices'] = [{
            'name': choice,
            'selected': choice in (obj.occupation or [])
        } for choice in metadata['occupation_choices']]

        metadata['category_choices'] = [{
            'name': choice,
            'selected': choice in (obj.categories or [])
        } for choice in metadata['category_choices']]

        metadata['ethnicity_choices'] = [{
            'name': choice,
            'selected': choice in (obj.ethnicity or [])
        } for choice in metadata['ethnicity_choices']]

        metadata['tags_choices'] = [{
            'name': choice,
            'selected': choice in (obj.tags or [])
        } for choice in metadata['tags_choices']]

        metadata['sex_choices'] = [{
            'name': choice,
            'selected': choice in (obj.sex or [])
        } for choice in metadata['sex_choices']]

        return metadata
            

class BrandSerializer(serializers.ModelSerializer):
    outreach_templates = serializers.SerializerMethodField(
        'get_outreach_templates')
    campaigns = serializers.SerializerMethodField(
        'get_campaigns')

    class Meta:
        model = models.Brands
        fields = ('id', 'domain_name', 'outreach_templates', 'campaigns',)

    def get_outreach_templates(self, obj):
        from debra.helpers import escape_angular_interpolation_reverse
        outreach = dict(obj.job_posts.values_list('id', 'outreach_template'))
        data = {}
        for k, v in outreach.items():
            try:
                v = escape_angular_interpolation_reverse(v)
                item = json.loads(v)
            except:
                item = {'template': v}
            data[str(k)] = item
        return data

    def get_campaigns(self, obj):
        items = obj.job_posts.exclude(archived=True).order_by('title').only(
            'id', 'title')
        data = [{
            'text': unescape(item.title), 'value': item.id} for item in items]
        return data

    def get_saved_searches(self, obj):
        from debra.search_helpers import get_brand_saved_queries_list
        return get_brand_saved_queries_list(obj)

    def get_tags(self, obj):
        from debra.search_helpers import get_brand_tags_list
        items = [{
            'value': item['id'], 'title': item['name']
        } for item in get_brand_tags_list(obj, obj)]
        return items


class CacheSerializer(object):

    def __init__(self, serializer):
        self._serializer = serializer

    def pack(self, items):
        return '||'.join(['|'.join(map(
            lambda v: unicode(v).encode('utf-8'),
            item.values())) for item in self._serializer(items, many=True).data
        ])

    def unpack(self, value):
        from debra.helpers import eval_or_return
        _t0 = time.time()
        if not value:
            return
        value = value.decode('utf-8')
        items = value.split('||') if value else []
        data = [
            self.serialize_iterable(map(eval_or_return, item.split('|')))
            for item in items
        ]
        print '* unpack() took {}'.format(time.time() - _t0)
        return data

    def serialize_iterable(self, iterable, many=False):
        if iterable is None:
            return None
        if many:
            return [
                dict(zip(self._serializer.Meta.fields, item))
                for item in iterable]
        else:
            return dict(zip(self._serializer.Meta.fields, iterable))



class InfluencersGroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.InfluencersGroup
        fields = ('id', 'name', 'owner_brand', 'creator_brand',
            'system_collection', 'archived', 'influencers_count',)