import collections
import decimal
import hashlib
import traceback
import itertools
import inspect
import json
import logging
import math
import operator
import os
import random
import re
import sys
import time
import traceback
import urllib2
from StringIO import StringIO
from datetime import datetime, timedelta, date
from operator import __or__ as OR
from uuid import uuid4

import intercom
import requests
import stripe
import wr
from boto.cloudfront import CloudFrontConnection
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.core.cache import cache, get_cache
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.urlresolvers import reverse
from django.db import models, IntegrityError, transaction
from django.db.models import Sum, F, Max, Q, Count, Avg
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils.encoding import smart_unicode
from django_facebook import signals
from django_facebook.models import FacebookProfileModel
from django_facebook.utils import get_user_model
# NOTE: South's migration support doesn't respect nullability (null=True)
# for django_pgjson.JsonField's, so make sure you run an:
# ALTER TABLE sometable ALTER COLUMN somecolumn DROP NOT NULL
# after creating your JSON column
from django_pgjson.fields import JsonField as PGJsonField
from djorm_pgarray.fields import TextArrayField
from jsonfield import JSONField
from phonenumber_field.modelfields import PhoneNumberField

from debra import (
    account_helpers, clickmeter, constants, db_util, feeds_helpers,
    mail_proxy, search_helpers,
)
from debra.classification_data import influencer_age_groups_dict
from debra.constants import (
    STRIPE_TEST_SECRET_KEY, STRIPE_LIVE_SECRET_KEY, ELASTICSEARCH_URL,
    ELASTICSEARCH_INDEX, site_configurator)
from debra.decorators import (
    cached_model_property, json_field_property, cached_property,
    signal_crashed_notification, timeit, custom_cached,)
from debra.es_requests import make_es_delete_request
from debra.logical_categories import logical_categories_reverse_mapping
from debra.lsapi import lsapi, lsapiException
from platformdatafetcher import contentfiltering
from settings import DEBUG, INTERCOM_APPID, INTERCOM_APIKEY
from xpathscraper import utils

intercom.Intercom.app_api_key = INTERCOM_APIKEY
intercom.Intercom.app_id = INTERCOM_APPID
log = logging.getLogger('debra.models')
stripe.api_key = STRIPE_TEST_SECRET_KEY if DEBUG else STRIPE_LIVE_SECRET_KEY
short_cache = get_cache('short')

clickmeter_api = clickmeter.ClickMeterApi()
mc_cache = get_cache('memcached')
redis_cache = get_cache('redis')

# some helper functions


def get_dims_for_url(url):
    from django.core.files.images import get_image_dimensions
    opener = urllib2.build_opener()
    try:
        img = opener.open(url)
    except Exception:
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        img = opener.open(url)
    stringio = StringIO()
    while True:
        chunk = img.read(1500)
        if not chunk:
            return None
        stringio.write(chunk)
        dims = get_image_dimensions(stringio)
        if dims:
            return dims


class BaseMixin(object):

    @classmethod
    def get_subclasses(cls):

        def is_not_me(x):
            return x != cls

        def is_abstract_model(x):
            try:
                return x._meta.abstract
            except AttributeError:
                return False

        def is_subclass(x):
            return is_not_me(x) and inspect.isclass(x) and\
                issubclass(x, cls) and not is_abstract_model(x)

        return inspect.getmembers(
            sys.modules[__name__], is_subclass)


class BaseManagerMixin(BaseMixin):

    @classmethod
    def get_model(cls):
        classes = inspect.getmembers(sys.modules[__name__],
            inspect.isclass)
        for _, _cls in classes:
            if getattr(_cls, 'objects', None).__class__ == cls:
                return _cls


class PostSaveTrackableMixin(BaseMixin, models.Model):

    class Meta:
        abstract = True

    def _clear_old_field_values(self):
        for field in self._POST_SAVE_TRACKABLE_FIELDS:
            try:
                delattr(self, '_old_{}'.format(field))
            except AttributeError:
                pass

    def is_field_changed(self, field):
        try:
            return getattr(self, field) != getattr(self, '_old_{}'.format(
                field))
        except AttributeError:
            return False


class TimeSeriesMixin(object):

    def time_series(self, field, date_field='created', date_field_full=None, cumulative=False):
        time_series = self.exclude(**{
            '{}__isnull'.format(date_field): True
        }).exclude(**{
            '{}__isnull'.format(field): True
        }).extra(select={
            'year': "EXTRACT(year FROM {})".format(date_field_full or date_field),
            'month': "EXTRACT(month FROM {})".format(date_field_full or date_field),
            'day': "EXTRACT(day FROM {})".format(date_field_full or date_field),
        }).values(
            'year', 'month', 'day'
        ).order_by(
            'year', 'month', 'day'
        ).annotate(Sum(field))

        if cumulative:
            data, curr_sum = [], 0
            for serie in time_series:
                curr_sum += serie['{}__sum'.format(field)]
                data.append({
                    'date': date(
                        year=int(serie['year']),
                        month=int(serie['month']),
                        day=int(serie['day']),
                    ),
                    'count': curr_sum,
                })
        else:
            data = [{
                'date': date(
                    year=int(serie['year']),
                    month=int(serie['month']),
                    day=int(serie['day']),
                ),
                'count': serie['{}__sum'.format(field)],
            } for serie in time_series]

        return data


###################################################
###################################################
class DenormalizationManagerMixin(BaseManagerMixin):

    def run_denormalization(self, item_ids=None):
        print '* running {} denormalization'.format(self)
        items = self.all()
        if item_ids:
            items = items.filter(id__in=item_ids)
        for item in items:
            print '** denormalizing item={}'.format(item.id)
            _t0 = time.time()
            item.denormalize()
            print 'took {}'.format(time.time() - _t0)


class TaggingMixin(models.Model):
    tags = TextArrayField(null=True, default=[])

    class Meta:
        abstract = True

    def add_tags(self, tags, to_save=True):
        cur_tags = self.tags
        if cur_tags:
            cur_tags = set(self.tags)
            cur_tags.update(tags)
        else:
            cur_tags = set(tags)
        self.tags = list(cur_tags)
        if to_save:
            self.save()

    def remove_tags(self, tags, to_save=True):
        cur_tags = self.tags
        if cur_tags:
            cur_tags = set(cur_tags) - set(tags)
            self.tags = list(cur_tags)
            if to_save:
                self.save()

    @property
    def tags_list(self):
        if self.tags is None:
            return []
        return self.tags



###################################################
###################################################


class PromoRawText(models.Model):
    DATA_SOURCE_CHOICES = (
        (0, 'Website'),
        (1, 'Email'),
    )
    store = models.ForeignKey('Brands', default='1')
    insert_date = models.DateField('insert date')
    raw_text = models.TextField(blank=True, null=True, default=None)
    initial_type = models.CharField(max_length=50, null=True, blank=True, default='storewide')
    data_source = models.CharField(max_length=10, choices=DATA_SOURCE_CHOICES)
    processed = models.BooleanField(default=False)

    def __unicode__(self):
        return smart_unicode(self.store) + " " + smart_unicode(self.insert_date) + " " + smart_unicode(self.raw_text) + " " + smart_unicode(self.data_source)


###################################################
###################################################
class Promoinfo(models.Model):

    STORE_CHOICES = (
        ('JCREW', 'JCREW'),
        ('EXPRESS', 'EXPRESS'),
    )

    AVAILABILITY_CHOICES = (
        (0, 'STORES ONLY'),
        (1, 'ONLINE ONLY'),
        (2, 'BOTH'),
    )

    #store = models.CharField(max_length=10, choices = STORE_CHOICES)
    store = models.ForeignKey('Brands', default='1')
    d = models.DateField('date issued', default=datetime.today())
    #d_expire = models.DateField('expiry date')
    validity = models.IntegerField('Valid for how many days?', default=0)
    code = models.CharField('Code if any', max_length=20)  # the promotion code to enter
    where_avail = models.IntegerField('Available in stores/online/both?', choices=AVAILABILITY_CHOICES, default=2)
    free_shipping_lower_bound = models.FloatField(default=10000)

    PROMO_TYPE_CHOICES = (
        (0, 'clearance'),
        (1, 'aggregate'),
        (2, 'storewide'),
        (3, 'b1g1'),
        (4, 'misc'),
        (5, 'shipping'),
    )

    promo_type = models.IntegerField('What kind of promotion is this?', choices=PROMO_TYPE_CHOICES, default=0)

    promo_disc_perc = models.FloatField('Discount %? Example: if 30%, enter 30.', default=0)  # percent reduction
    promo_disc_amount = models.FloatField(
        'Discount of certain dollars. E.g., $15 off of your purchase. Enter 15.', default=0)  # amount reduction
    promo_disc_lower_bound = models.FloatField(
        'How much do you need to spend to use this promotion?', default=0)  # minimum price after the promo

    SEX_CHOICES = (
        (0, 'MALE'),
        (1, 'FEMALE'),
        (2, 'ALL'),
    )
    sex_category = models.IntegerField(
        'Is this applicable to only women items? Or men items? Or both?', choices=SEX_CHOICES, default=2)

    ITEM_CATEGORY_CHOICES = (
        (0, 'SHIRTS'),
        (1, 'PANTS'),
        (2, 'SWEATERS'),
        (3, 'JEANS'),
        (4, 'OUTERWEAR'),
        (5, 'UNDERWEAR'),
        (7, 'EVERYTHING')
    )

    item_category = models.CharField('Categories applicable to:?', max_length=100, default="Nil")

    ''' Whether the category provided should be excluded from the promotion '''
    exclude_category = models.BooleanField(default=False)

    start_date = models.DateTimeField('start date', default=datetime.now)
    end_date = models.DateTimeField('end date', default=datetime.now)

    '''
    item_category = models.IntegerField(choices = ITEM_CATEGORY_CHOICES, default=0)

    class Meta:
        unique_together = ('store', 'd', 'promo_type', 'promo_disc_perc', 'promo_disc_amount',
                           'promo_disc_lower_bound', 'sex_category', 'item_category')
    '''

    def __unicode__(self):
        return '%s "%s" %s' % (self.store, self.code, self.d)


###################################################
###################################################
class MechanicalTurkTask(models.Model):

    '''
    Mechanical Turk is the service we are using to extract text from promotions. This model represents
    a task given to mechanical turk and contains fields relevant to the processing of that task.
    '''
    task_type = models.CharField(max_length=100, choices=[(
        task, task) for task in [constants.HOUDINI_PROMO_EMAIL_TASK, constants.HOUDINI_PROMO_IMAGE_TASK]], default=constants.HOUDINI_PROMO_EMAIL_TASK)
    task_id = models.CharField(max_length=100)
    status = models.CharField(max_length=100)


###################################################
###################################################
class PromoDashboardUnit(models.Model):
    promo_info = models.ForeignKey(Promoinfo, null=True, blank=True, default=None)
    promo_raw = models.ForeignKey(PromoRawText, null=True, blank=True, default=None)
    promo_updated_text = models.TextField()

    user = models.ForeignKey(User, null=True, blank=True, default=None)
    checked = models.BooleanField(default=False)
    create_time = models.DateField('Creation time', default=datetime.today())
    updated_time = models.DateField('Update time', default=datetime.today())

    def __unicode__(self):
        return '%s %s %s %s %d %s %s' % (self.promo_info, self.promo_updated_text, self.promo_raw, self.user,
                                         self.checked, self.create_time, self.updated_time)


###################################################
###################################################

class BrandCategory(models.Model):
    name = models.CharField(max_length=100)


class BrandJobPostMixin(object):

    def brand_campaigns(self, base_brand, brand):
        from aggregate_if import Count, Sum

        qs = self.exclude(
            archived=True
        ).filter(
            creator=brand, oryg_creator=base_brand
        )

        def get_influencer_collection_annotations(qs):
            ids = list(qs.values_list(
                'id', 'report__influencer_analytics_collection'))
            collection_2_campaign = dict([(y, x) for x, y in ids])
            values = dict(
                InfluencerAnalyticsCollection.objects.filter(
                    id__in=[x[1] for x in ids]
                ).annotate(
                    agr_approval=Count(
                        'influenceranalytics__influencer',
                        only=(
                            Q(influenceranalytics__approve_status=0)
                        )
                    )
                ).values_list('id', 'agr_approval')
            )
            return {
                collection_2_campaign[c_id]:value
                for c_id, value in values.items()
            }
        collection_annotations = get_influencer_collection_annotations(qs)

        qs = qs.prefetch_related('creator')

        annotations = {}
        annotations.update(BrandJobPost.stage_annotations())
        annotations.update({
            'agr_spent': Sum(
                'candidates__contract__negotiated_price', only=(
                    Q(candidates__campaign_stage__gt=InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION) &
                    Q(candidates__campaign_stage__lt=InfluencerJobMapping.CAMPAIGN_STAGE_ARCHIVED)
                ),
            ),
            # 'agr_approval': Count(
            #     'report__influencer_analytics_collection__influenceranalytics__influencer',
            #     only=(
            #         Q(report__influencer_analytics_collection__influenceranalytics__approve_status=0)
            #     ),
            #     distinct=True,
            # )
        })

        print 'getting annotations...'
        qs = qs.annotate(**annotations)
        for campaign in qs:
            campaign.agr_approval = collection_annotations.get(campaign.id)
        print 'annotations are done'

        return qs


class BrandJobPostQuerySet(models.query.QuerySet, BrandJobPostMixin):
    pass


class BrandJobPostManager(models.Manager, BrandJobPostMixin):

    def get_query_set(self):
        return BrandJobPostQuerySet(self.model, using=self.db)


class BrandJobPost(TaggingMixin, PostSaveTrackableMixin, models.Model):
    _POST_SAVE_TRACKABLE_FIELDS = ['client_url', 'product_urls']

    COLLABORATION_TYPES = (
        ("sponsored_posts", "Sponsored Posts"),
        ("product_reviews", "Product Reviews"),
        ("giveaways", "Giveaways"),
        ("banner_ads", "Banner Ads"),
        ("event_coverage", "Event Coverage"),
        ("affiliate", "Affiliate Offer"),
        ("other", "Other"),
    )
    # this is job post owner
    creator = models.ForeignKey('Brands', related_name='job_posts')
    oryg_creator = models.ForeignKey('Brands', related_name='job_posts_created', null=True, blank=True)
    creator_user = models.ForeignKey(User, related_name='job_posts_created', null=True)
    description = models.TextField(null=True, blank=True)
    title = models.CharField(max_length=256, null=True, blank=True)
    who_should_apply = models.TextField(null=True, blank=True)
    filter_json = models.TextField(null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    collab_type = models.CharField(max_length=32, choices=COLLABORATION_TYPES)
    date_start = models.DateField(null=True, blank=True)
    date_end = models.DateField(null=True, blank=True)
    published = models.BooleanField(default=False)
    date_publish = models.DateField(null=True, blank=True)
    collection = models.ForeignKey(
        "InfluencersGroup", related_name="job_post", null=True, blank=True, on_delete=models.SET_NULL)
    profile_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    cover_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    attachment_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    archived = models.NullBooleanField(blank=True, null=True, default=False)
    hashtags_required = models.CharField(max_length=1000, null=True)
    mentions_required = models.CharField(max_length=1000, null=True)
    outreach_template = models.TextField(null=True, blank=True)

    info = models.TextField(null=True, default="")
    # tags = TextArrayField(null=True)
    posts_added_info = models.TextField(null=True)

    client_name = models.CharField(max_length=1000, null=True)
    client_url = models.CharField(max_length=1000, null=True)

    product_urls = TextArrayField(null=True, default=[])

    utm_source = models.CharField(max_length=1000, null=True)
    utm_medium = models.CharField(max_length=1000, null=True)
    utm_campaign = models.CharField(max_length=1000, null=True)
    tracking_group = models.CharField(max_length=1000, null=True)
    report = models.ForeignKey('ROIPredictionReport', null=True)
    post_collection = models.ForeignKey('PostAnalyticsCollection', null=True)
    bloggers_post_collection = models.OneToOneField(
        'PostAnalyticsCollection', related_name='bloggers_campaign', null=True)
    periodic_tracking = models.BooleanField(default=True)

    posts_saved_search = models.ForeignKey('SearchQueryArchive', null=True)

    objects = BrandJobPostManager()

    class Meta:
        ordering = ['title']
        get_latest_by = "id"

    def __unicode__(self):
        return "Campaign %s from %s" % (self.title, self.creator.name)

    @timeit
    def upload_influencers(self, inf_ids, stage=None, update_cache=True):
        stage = IJM.CAMPAIGN_STAGE_APPROVAL if stage is None else stage
        approved = stage not in [IJM.CAMPAIGN_STAGE_APPROVAL]
        extra = {
            inf_id: {
                'approve_status': approved
            } for inf_id in inf_ids
        }
        self.influencer_collection.merge_influencers(
            inf_ids,
            celery=False,
            extra=extra,
            campaign=self,
            approved=approved
        )
        self.candidates.filter(
            mailbox__influencer__in=inf_ids
        ).update(campaign_stage=stage)
        if update_cache:
            from debra.tasks import update_bloggers_cache_data
            update_bloggers_cache_data(item_ids=inf_ids,
                enabled_tasks=['profilePics', 'platformDicts'])

    def merge_approved_candidates(self, celery=True, inf_ids=None):
        from debra.brand_helpers import add_approved_influencers_to_pipeline
        if celery:
            add_approved_influencers_to_pipeline.apply_async(
                [self.id, inf_ids], queue="blogger_approval_report")
        else:
            add_approved_influencers_to_pipeline(self.id, inf_ids)

    def generate_tracking_group(self, to_save=True):
        print '* generate tracking group'
        if not self.tracking_group:
            group_response = clickmeter_api.post(
                '/groups', data={'name': self.id}).json()
            self.tracking_group = str(group_response.get('id'))
            if to_save:
                self.save()

    def get_datapoint_names(self, datapoint_type=None):
        datapoint_type = datapoint_type or 'tl'
        self.generate_tracking_group()
        results = clickmeter.ClickMeterListResult(
            clickmeter_api,
            '/aggregated/summary/datapoints', {
                'timeframe': 'beginning',
                'type': datapoint_type,
                'groupId': self.tracking_group or self.id
            }
        )
        res = []
        for page in results:
            for entity in page['result']:
                entity_data = entity.get('entityData', {})
                res.append(
                    (entity_data.get('datapointId'),
                        entity_data.get('datapointName'))
                )
        return dict(res)

    def update_tracking_link_batch(self):
        print '* batch update for tracking links'
        datapoint_ids = self.candidates.filter(
            contract__tracking_link__isnull=False
        ).values_list(
            'contract__tracking_link',
            'contract_id',
            # 'contract__tracking_link_name',
            'contract__product_url',
        )
        names = self.get_datapoint_names()
        data = [{
            'id': int(datapoint_id),
            'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
            'groupId': self.tracking_group or self.id,
            'preferred': True,
            'name': names.get(int(datapoint_id)),
            'title': u"'{}' campaign for {}".format(
                self.title, contract_id),
            'typeTL': {
                'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                'url': self.info_json.get('product_url') if self.info_json.get('same_product_url') else product_url,
                'redirectType': 301,
            }
        } for datapoint_id, contract_id, product_url in datapoint_ids]

        if data:
            response = clickmeter_api.post(
                '/datapoints/batch', data={'list': data}).json()

    def update_tracking_brand_link_batch(self):
        print '* batch update for tracking brand links'
        datapoint_ids = self.candidates.filter(
            contract__tracking_brand_link__isnull=False
        ).values_list(
            'contract__tracking_brand_link',
            'contract_id',
            # 'contract__tracking_brand_link_name',
        )
        names = self.get_datapoint_names()
        data = [{
            'id': int(datapoint_id),
            'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
            'groupId': self.tracking_group or self.id,
            'preferred': True,
            'name': names.get(int(datapoint_id)),
            'title': u"'{}' campaign for {} (brand link)".format(
                self.title, contract_id),
            'typeTL': {
                'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                'url': self.client_url,
                'redirectType': 301,
            }
        } for datapoint_id, contract_id in datapoint_ids]
        if data:
            response = clickmeter_api.post(
                '/datapoints/batch', data={'list': data}).json()

    @transaction.commit_on_success
    def handle_campaign_stage(self, qs=None, hard=False):
        if qs is None:
            qs = self.candidates.all()

        t = time.time()
        print 'handle_campaign_stage()...'

        if not hard:
            qs = qs.exclude(moved_manually=True)
        else:
            qs.filter(
                campaign_stage__lt=InfluencerJobMapping.CAMPAIGN_STAGE_UNDERWAY
            ).update(
                moved_manually=False,
                campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_PRE_OUTREACH
            )

        # if self.first_stage_after_outreach == InfluencerJobMapping.CAMPAIGN_STAGE_CONTRACTS:
        #     pass
        if '{}_stage_disabled'.format(InfluencerJobMapping.CAMPAIGN_STAGE_PRE_OUTREACH) in self.tags_list:
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_PRE_OUTREACH)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE)
        else:
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_PRE_OUTREACH) &
                Q(mailbox__threads__isnull=False)
                # Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
                # Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL) &
                # Q(mailbox__threads__direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER)
            ).update(
                campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE)

        if '{}_stage_disabled'.format(InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE) in self.tags_list:
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION)
        else:
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE) &
                Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
                Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL) &
                Q(mailbox__threads__direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION)

        if '{}_stage_disabled'.format(InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION) in self.tags_list:
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS)

        stage_settings = self.info_json.get('stage_settings', {}).get(
                str(InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS), {})
        if '{}_stage_disabled'.format(InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS) in self.tags_list:
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_CONTRACTS)
        elif stage_settings.get('send_contract'):
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS) &
                # Q(contract__negotiated_price__isnull=False) &
                Q(contract__details_collected_status=2) &
                Q(contract__status=Contract.STATUS_SIGNED)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_CONTRACTS)
        else:
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS) &
                # Q(contract__negotiated_price__isnull=False) &
                Q(contract__details_collected_status=2)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_CONTRACTS)

        if self.info_json.get('signing_contract_on'):
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_CONTRACTS) &
                Q(contract__status=Contract.STATUS_SIGNED)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_LOGISTICS)
        else:
            print 'YO', qs.filter(
                Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_CONTRACTS)
            ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_LOGISTICS)

        # ========  TURN OFF AUTO-MOVING TO THE IN-PROGRESS STAGE =============
        # ========  TURN OFF AUTO-MOVING TO THE IN-PROGRESS STAGE =============

        # if self.info_json.get('sending_product_on'):
        #     qs.filter(
        #         Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_LOGISTICS) &
        #         Q(contract__shipment_status=2)
        #     ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_UNDERWAY)
        # else:
        #     qs.filter(
        #         Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_LOGISTICS)
        #     ).update(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_UNDERWAY)

        print time.time() - t

    def get_or_create_post_collection(self):
        if self.post_collection is None:
            self.post_collection = PostAnalyticsCollection.objects.create(
                name=u'Posts added by bloggers from {} campaign'.format(
                    self.title),
                creator_brand=self.creator,
                system_collection=True,
            )
            self.save()
        return self.post_collection

    @classmethod
    def pipeline_stages(cls):
         return [
            (IJM.CAMPAIGN_STAGE_PRE_OUTREACH, 'Outreach'),
            (IJM.CAMPAIGN_STAGE_WAITING_ON_RESPONSE, 'Follow-up'),
            (IJM.CAMPAIGN_STAGE_NEGOTIATION, 'Discussion'),
            (IJM.CAMPAIGN_STAGE_FINALIZING_DETAILS, 'Logistics'),
            # (IJM.CAMPAIGN_STAGE_CONTRACTS, 'Contracts'),
            # (IJM.CAMPAIGN_STAGE_LOGISTICS, 'Shipping'),
            # (IJM.CAMPAIGN_STAGE_UNDERWAY, 'In Progress'),
            (IJM.CAMPAIGN_STAGE_COMPLETE, 'Complete'),
            (IJM.CAMPAIGN_STAGE_ARCHIVED, 'Archived'),
        ]

    @classmethod
    def stages(cls):
        return [
            (IJM.CAMPAIGN_STAGE_ALL, 'All'),
            (IJM.CAMPAIGN_STAGE_LOAD_INFLUENCERS, 'Load Influencers'),
            (IJM.CAMPAIGN_STAGE_APPROVAL, 'Approval'),
        ] + cls.pipeline_stages()

    @classmethod
    def stage_annotations(cls):
        from aggregate_if import Count
        from debra.helpers import name_to_underscore

        annotations = {}
        for stage, name in cls.pipeline_stages():
            if stage in InfluencerJobMapping.SANDBOX_STAGES:
                stages = InfluencerJobMapping.SANDBOX_STAGES
            else:
                stages = [stage]
            annotations['agr_{}'.format(name_to_underscore(name))] = Count(
                'candidates', only=(
                    Q(candidates__campaign_stage__in=stages)
                ),
                distinct=True
            )
            annotations['agr_{}_unread'.format(name_to_underscore(name))] = Count(
                'candidates', only=(
                    Q(candidates__campaign_stage__in=stages) &
                    Q(candidates__mailbox__has_been_read_by_brand=False)
                ),
                distinct=True
            )
        annotations['agr_all'] = Count('candidates', distinct=True)

        return annotations

    @cached_property
    def stage_counts(self):
        from debra.helpers import name_to_underscore
        print 'getting counts for {}'.format(self.id)
        counts = {}
        unread_counts = {}
        for stage, name in self.stages():
            try:
                counts[stage] = getattr(self, 'agr_{}'.format(
                    name_to_underscore(name)))
            except AttributeError:
                pass
            try:
                unread_counts[stage] = getattr(self, 'agr_{}_unread'.format(
                    name_to_underscore(name)))
            except AttributeError:
                pass
        print 'counts are done'
        return {
            'counts': counts,
            'unread_counts': unread_counts,
        }

    @property
    def payment_method(self):
        return self.info_json.get('payment_method', 'PayPal')

    @property
    def publisher_name(self):
        return 'Publisher Name'

    @property
    def docusign_documents(self):
        from debra.constants import site_configurator
        specific_documents = site_configurator.instance.docusign_documents_json.get(
            str(self.id), {}).get('documents', {})
        # specific_documents = constants.DOCUSIGN_DOCUMENTS.get(
        #     self.id, {}).get('documents', {})
        specific_documents.update(
            site_configurator.instance.docusign_documents_json.get(
                'default').get('documents')
        )
        return specific_documents

    def get_docusign_page_offsets(self, document_id):
        page_offsets = self.docusign_documents[str(document_id)].get(
            'page_offsets')
        try:
            return eval(page_offsets)
        except TypeError:
            return page_offsets

    def get_docusign_field_value(self, document_id, name):
        value = self.info_json.get(str(document_id), {}).get(name)
        if value is None:
            value = self.docusign_documents[str(document_id)]['fields'].get(name)
            try:
                value = eval(value)(self)
            except:
                value = None
        return value

    @property
    def docusign_template(self):
        from debra.constants import site_configurator
        return site_configurator.instance.docusign_documents_json.get(
            str(self.id), {}).get('template_id')

    @cached_property
    def stage_switcher(self):
        from debra.helpers import PageSectionSwitcher, name_to_underscore

        print '* getting switcher for {}'.format(self.id)
        print '** getting urls...'
        urls = {
            n: '{}?campaign_stage={}'.format(reverse(
                'debra.job_posts_views.campaign_setup',
                args=(self.id,)
            ), n) for n, _ in self.stages()
        }

        urls[-2] = reverse(
            'debra.job_posts_views.campaign_approval',
            args=(self.id,)
        )
        urls[-3] = reverse(
            'debra.job_posts_views.campaign_load_influencers',
            args=(self.id,)
        )

        print '** getting hidden'
        hidden = []
        if not self.info_json.get('approval_report_enabled', False):
            hidden.append(-2)
        if not self.info_json.get('signing_contract_on'):
            hidden.append(InfluencerJobMapping.CAMPAIGN_STAGE_CONTRACTS)
        if not self.info_json.get('sending_product_on'):
            hidden.append(InfluencerJobMapping.CAMPAIGN_STAGE_LOGISTICS)

        print '** creating switcher...'
        sw = PageSectionSwitcher(
            self.stages(), None,
            urls=urls,
            extra={
                'unread_count': self.stage_counts['unread_counts'],
                'class': {k:name_to_underscore(v) for k, v in self.stages()},
            },
            hidden=hidden,
            counts=self.stage_counts['counts'],
        )
        print 'switcher is done'
        return sw

    @property
    def deliverables_json(self):
        return self.info_json.get('deliverables', {})

    @property
    def deliverables_text(self):
        return "\n".join(
            "{} {}".format(
                data.get('value', 0),
                data.get('plural') if data.get('value', 0) > 1 else data.get('single')
            ) for name, data in self.deliverables_json.items()
            if data.get('value')
        )

    @property
    def deliverables_lines(self):
        lines = [
            line for line in self.deliverables_text.split('\n') if len(line) > 0
        ]
        return {n:line for n, line in enumerate(lines, start=1)}

    @property
    def payment_terms(self):
        try:
            return self.info_json['payment_terms']
        except KeyError:
            # return 'within 15 days of the last required post going live'
            pass

    @property
    def payment_terms_lines(self):
        if self.payment_terms is None:
            return {}
        lines = [x for x in self.payment_terms.split('\n') if x]
        return {n:x for n, x in enumerate(lines, start=1)}

    @property
    def campaign(self):
        return self

    @property
    def brand(self):
        return self.creator

    @property
    def date_range(self):
        return {
            'start_date': self.date_start,
            'end_date': self.date_end,
        }

    @date_range.setter
    def date_range(self, value):
        if type(value) == dict:
            self.date_start = value.get('start_date')
            self.date_end = value.get('end_date')

    @property
    def send_contract_along_with_details(self):
        stage_settings = self.info_json.get(
            'stage_settings', {}
        ).get(str(InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS), {})
        return stage_settings.get('send_contract', False)

    @property
    def first_stage_after_outreach(self):
        for stage, name in InfluencerJobMapping.CAMPAIGN_STAGE:
            if stage > 0 and '{}_stage_disabled'.format(stage) not in self.tags_list:
                return stage

    @property
    def first_stage(self):
        for stage, name in InfluencerJobMapping.CAMPAIGN_STAGE:
            if '{}_stage_disabled'.format(stage) not in self.tags_list:
                return stage

    @property
    def product_sending_status(self):
        '''
        0. No product sending.
        1. No product page.
        2. One product page for everyone.
        3. Influencers can choose their products.
        '''
        if not self.info_json.get('sending_product_on'):
            return 'no_product_sending'
        elif not self.info_json.get('product_links_on'):
            return 'no_product_page'
        elif self.info_json.get('same_product_url'):
            return 'one_product_page'
        elif self.info_json.get('do_select_url'):
            return 'can_choose_product_page'
        else:
            return 'cannot_choose_product_page'

    @property
    def product_section_on(self):
        return self.info_json.get('sending_product_on')
        # if self.product_sending_status == 'no_product_sending':
        #     return False
        # if self.product_sending_status == 'no_product_page' and not self.info_json.get('blogger_additional_info_on'):
        #     return False
        # return True

    @property
    def date_requirements_on(self):
        return self.info_json.get('date_requirements_on')

    @property
    def post_requirements(self):
        return self.info_json.get('post_requirements')

    @property
    def info_json(self):
        from debra.serializers import CampaignSerializer
        from debra.helpers import escape_angular_interpolation_reverse
        try:
            value = json.loads(self.info)
            value = CampaignSerializer().transform_info(self, value)
            return json.loads(escape_angular_interpolation_reverse(json.dumps(value)))
        except:
            return {}

    @json_field_property
    def posts_added_info_json(self):
        return 'posts_added_info'

    @property
    def payment_details_on(self):
        return self.info_json.get('payment_details_on', True)

    @property
    def outreach_template_json(self):
        from debra.serializers import CampaignSerializer
        from debra.helpers import escape_angular_interpolation_reverse
        try:
            value = json.loads(self.outreach_template)
            value = CampaignSerializer().transform_outreach_template(self, value)
            return json.loads(escape_angular_interpolation_reverse(json.dumps(value)))
        except:
            return {}

    @property
    def roi_report(self):
        if self.report_id is None:
            self.report = ROIPredictionReport.objects.create(
                name=u'Report for {} campaign'.format(self.title),
                creator_brand=self.creator,
            )
            self.save()
        return self.report

    @property
    def influencer_collection(self):
        report = self.roi_report
        if report.influencer_analytics_collection_id is None:
            print '* Creating a new influencer collection...'
            report.influencer_analytics_collection = InfluencerAnalyticsCollection.objects.create()
            report.save()
            print '* Done. ID={}'.format(report.influencer_analytics_collection.id)
        # self.report.influencer_analytics_collection.merge_influencers(
        #     self.participating_influencer_ids, celery=True)
        return report.influencer_analytics_collection

    @property
    def report_hash_key(self):
        if self.post_collection:
            key = '/'.join([
                str(self.id),
                str(self.post_collection.created_date),
            ])
            return hashlib.md5(key).hexdigest()

    @cached_property
    @timeit
    def participating_influencer_ids(self):
        return list(
            self.participating_post_analytics.exclude(
                post__influencer__isnull=True
            ).values_list('post__influencer', flat=True).distinct()
        )

    @cached_property
    @timeit
    def participating_influencers_count(self):
        return self.participating_post_analytics.exclude(
            post__influencer__isnull=True
        ).values_list('post__influencer', flat=True).distinct().count()

    @cached_property
    @timeit
    def participating_influencers(self):
        return Influencer.objects.filter(id__in=self.participating_influencer_ids)

    @property
    def participating_post_analytics(self):
        return self.post_collection.get_unique_post_analytics().exclude(
            post__influencer__isnull=True,
        ).filter(
            Q(contract__influencerjobmapping__campaign_stage__gt=InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION) &
            ~Q(contract__influencerjobmapping__campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_ARCHIVED)
        )

    @property
    def participating_post_ids(self):
        post_ids = self.participating_post_analytics.values_list(
            'post', flat=True).distinct('post')
        return list(post_ids)

    @property
    def participating_platforms(self):
        return Platform.objects.filter(
            id__in=self.participating_post_analytics.values_list(
                'post__platform', flat=True)
        )

    @cached_property
    # @cached_model_property
    def potential_social_impressions(self):
        _t0 = time.time()
        qs = self.participating_post_analytics
        qs = qs.exclude(post__platform_name__in=Platform.BLOG_PLATFORMS)
        qs = qs.values(
            'post__platform', 'post__platform__num_followers', 'post__platform_name',
        ).annotate(posts_count=Count('post__platform__posts'))

        res = collections.defaultdict(int)
        for item in qs:
            num_followers = item['post__platform__num_followers'] or 0
            posts_count = item['posts_count'] or 0
            res[item['post__platform_name']] += num_followers * posts_count

        print '* potential_social_impressions took {}'.format(time.time() - _t0)
        return res

    def get_impressions(self, funcs, platform_name=None, social_only=False, blog_only=False, **kwargs):

        blog_impressions, social_impressions = funcs

        if platform_name == 'Blog' or blog_only:
            return blog_impressions()
        elif platform_name in ['Twitter', 'Facebook', 'Instagram', 'Pinterest'] or social_only:
            return social_impressions()
        elif platform_name is None:
            return blog_impressions() + social_impressions()

    def get_total_impressions(self, platform_name=None, qs=None, **kwargs):

        qs = qs or self.participating_post_analytics

        def blog_impressions():
            return qs.filter(
                post__platform_name__in=Platform.BLOG_PLATFORMS
            ).aggregate(
                Sum('count_impressions')).get('count_impressions__sum', 0) or 0

        def social_impressions():
            # post_ids = self.participating_post_ids
            # platforms = self.participating_platforms
            if platform_name:
                platform_names = [platform_name]
            else:
                platform_names = [
                    'Twitter', 'Facebook', 'Instagram', 'Pinterest']
            # data = self.potential_social_impressions
            # return sum(data.get(pl, 0) for pl in platform_names)
            # platforms = platforms.filter(platform_name__in=platform_names)
            return sum(platforms.extra(select={
                'total_impressions': '''
                    coalesce((SELECT COUNT(p.id) * debra_platform.num_followers
                        FROM debra_posts as p
                        WHERE p.platform_id = debra_platform.id AND p.id IN %s), 0)
                '''
            }, select_params=(tuple(post_ids),)).values_list(
                'total_impressions', flat=True
            ))

        def get_data():
            return self.get_impressions(
                (blog_impressions, social_impressions), platform_name, **kwargs)

        def get_cache_key():
            return 'tip_{}_{}'.format(self.id, platform_name)

        _t0 = time.time()

        cache_key = get_cache_key()
        data = cache.get(cache_key)
        if not data:
            data = get_data()
            cache.set(cache_key, data)

        print '* get_total_impressions for {} took {}'.format(
            platform_name, time.time() - _t0)

        return data

    def get_unique_impressions(self, platform_name=None, qs=None, **kwargs):

        qs = qs or self.participating_post_analytics

        def blog_impressions():
            return qs.filter(
                post__platform_name__in=Platform.BLOG_PLATFORMS
            ).aggregate(
                Sum('count_unique_impressions')
            ).get('count_unique_impressions__sum', 0) or 0

        def social_impressions():
            # platforms = self.participating_platforms
            if platform_name:
                platform_names = [platform_name]
            else:
                platform_names = [
                    'Twitter', 'Facebook', 'Instagram', 'Pinterest']
            return qs.filter(
                post__platform_name__in=platform_names
            ).aggregate(Sum('post__platform__num_followers')).get(
                'post__platform__num_followers__sum', 0)

        return self.get_impressions(
            (blog_impressions, social_impressions), platform_name, **kwargs)

    @cached_property
    def top_posts(self):
        self.participating_post_analytics

    @property
    def mails(self):
        # mails = short_cache.get('%i_jbp_mails_cache'%self.id)
        # if mails != None:
        #     return mails
        mails = MailProxyMessage.objects.filter(
            type=MailProxyMessage.TYPE_EMAIL,
        )
        q = [Q(thread__candidate_mapping__job=self)]
        if self.collection:
            q.append(Q(thread__mapping__group=self.collection))
        mails = mails.filter(reduce(lambda x, y: x | y, q))
        mails = mails.exclude(mandrill_id='.')
        mails = mails.order_by('ts')
        mails = mails.only('id', 'ts', 'type', 'direction', 'thread__influencer')
        mails = list(mails.values('id', 'ts', 'type', 'direction', 'thread__influencer'))
        # short_cache.set('%i_jbp_mails_cache'%self.id, mails)
        return mails

    def rebake(self):
        # partials_baker.bake_list_details_jobpost_partial_async(self.id)
        # partials_baker.bake_list_messages_partial_async(self.creator, self.oryg_creator)
        # if self.collection:
        #    partials_baker.bake_list_details_partial_async(self.collection.id)
        pass

    @property
    def filter_json_obj(self):
        print self.filter_json
        return json.loads(self.filter_json)

    @property
    def collab_type_verbose(self):
        return dict(self.COLLABORATION_TYPES).get(self.collab_type)

    @property
    def invited_count(self):
        invited_statuses = (
            InfluencerJobMapping.STATUS_INVITED,
            InfluencerJobMapping.STATUS_EMAIL_RECEIVED,
            InfluencerJobMapping.STATUS_VISITED,
        )

        influencers_set = set(
            mapping.influencer for mapping in self.candidates.filter(
                status__in=invited_statuses))

        return len(influencers_set)

    @property
    def applied_count(self):
        applied = set()
        for candidate in self.candidates.all():
            if candidate.status == InfluencerJobMapping.STATUS_ACCEPTED:
                applied.add(candidate.influencer.id)
        for th in self.mails:
            if th["direction"] == MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND:
                applied.add(th["thread__influencer"])
        return len(applied)

    def create_system_collection(self):
        if self.collection and self.collection.system_collection:
            return self.collection
        group = InfluencersGroup()
        group.name = self.title
        group.owner_brand = self.creator
        group.creator_brand = self.oryg_creator
        group.system_collection = True
        group.save()
        self.collection = group
        self.save()
        return group

    def save(self, *args, **kwargs):
        if self.collection and self.collection.system_collection:
            self.collection.name = self.title
            self.collection.save()
        return super(BrandJobPost, self).save(*args, **kwargs)


class MandrillBatch(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    data = PGJsonField(null=True, blank=True)


class MandrillEvent(models.Model):
    STATUS_ADDED = 0
    STATUS_SENT = 1
    STATUS_SAVED = 2
    STATUS_PROCESSED = 3

    STATUS = (
        (STATUS_ADDED, 'Added'),
        (STATUS_SENT, 'Sent'),
        (STATUS_SAVED, 'Saved'),
        (STATUS_PROCESSED, 'Processed'),
    )

    TYPE_INBOUND = 0
    TYPE_EVENT = 1

    TYPE = (
        (TYPE_INBOUND, 'Inbound'),
        (TYPE_EVENT, 'Event'),
    )

    data = PGJsonField(null=True, blank=True)
    status = models.IntegerField(null=True, default=STATUS_ADDED, choices=STATUS)
    type = models.IntegerField(null=True, default=TYPE_INBOUND, choices=TYPE)
    batch = models.ForeignKey(MandrillBatch, null=True)


class MailProxyQuerySet(models.query.QuerySet):

    def with_counters(self):
        from aggregate_if import Count, Max
        return self.annotate(
            agr_opened_count=Count(
                'threads',
                only=(
                    Q(threads__mandrill_id__regex=r'.(.)+') &
                    (
                        Q(threads__type=MailProxyMessage.TYPE_OPEN) |
                        Q(threads__type=MailProxyMessage.TYPE_CLICK)
                    )
                )
            ),
            agr_emails_count=Count(
                'threads',
                only=(
                    # Q(threads__mandrill_id__regex=r'.(.)+') &
                    Q(threads__type=MailProxyMessage.TYPE_EMAIL)
                )
            ),
            agr_last_message=Max(
                'threads__ts',
                only=(
                    # Q(threads__mandrill_id__regex=r'.(.)+') &
                    Q(threads__type=MailProxyMessage.TYPE_EMAIL)
                )
            ),
            agr_last_sent=Max(
                'threads__ts',
                only=(
                    # Q(threads__mandrill_id__regex=r'.(.)+') &
                    Q(threads__type=MailProxyMessage.TYPE_EMAIL) &
                    Q(threads__direction=MailProxyMessage\
                        .DIRECTION_BRAND_2_INFLUENCER)
                )
            ),
            agr_last_reply=Max(
                'threads__ts',
                only=(
                    # Q(threads__mandrill_id__regex=r'.(.)+') &
                    Q(threads__type=MailProxyMessage.TYPE_EMAIL) &
                    Q(threads__direction=MailProxyMessage\
                        .DIRECTION_INFLUENCER_2_BRAND)
                )
            ),
        )

    def mailbox_counts(self):
        return self.with_counters().values(
            'id', 'agr_opened_count', 'agr_emails_count',
            'agr_last_message', 'agr_last_sent', 'agr_last_reply',)

    def mailbox_counts_from_cache(self):
        raise NotImplementedError
        # mp_ids = list(self.values_list('id', flat=True))
        # cache_data = mc_cache.get_many(
        #     ['mpc_{}'.format(mp_id) for mp_id in mp_ids])
        # return self.extra(select={'some_stuff': 'debra_mailproxy.id'})

class MailProxyManager(models.Manager):

    def get_query_set(self):
        return MailProxyQuerySet(self.model, using=self.db)


class MailProxy(models.Model):
    STAGE_PRE_OUTREACH = 0
    STAGE_WAITING = 1
    STAGE_SECOND_ATTEMPT = 2
    STAGE_INTERESTED =3
    STAGE_DETAILS_SET = 4
    STAGE_ARCHIVED = 5

    STAGE = [
        (STAGE_PRE_OUTREACH, 'Pre-Outreach'),
        (STAGE_WAITING, 'Waiting to Hear Back'),
        (STAGE_SECOND_ATTEMPT, '2nd Attempt'),
        (STAGE_INTERESTED, 'Interested'),
        (STAGE_DETAILS_SET, 'Details Set'),
        (STAGE_ARCHIVED, 'Archived'),
    ]

    CAMPAIGN_STAGE_PRE_OUTREACH = 0
    CAMPAIGN_STAGE_WAITING_ON_RESPONSE = 1
    CAMPAIGN_STAGE_NEGOTIATION = 2
    CAMPAIGN_STAGE_CONTRACTS = 3
    CAMPAIGN_STAGE_LOGISTICS = 4
    CAMPAIGN_STAGE_UNDERWAY = 5
    CAMPAIGN_STAGE_COMPLETE = 6

    CAMPAIGN_STAGE = [
        (CAMPAIGN_STAGE_PRE_OUTREACH, 'Pre-Outreach'),
        (CAMPAIGN_STAGE_WAITING_ON_RESPONSE, 'Waiting on Response'),
        (CAMPAIGN_STAGE_NEGOTIATION, 'Negotiation'),
        (CAMPAIGN_STAGE_CONTRACTS, 'Contracts'),
        (CAMPAIGN_STAGE_LOGISTICS, 'Logistics'),
        (CAMPAIGN_STAGE_UNDERWAY, 'Underway'),
        (CAMPAIGN_STAGE_COMPLETE, 'Complete'),
    ]

    influencer = models.ForeignKey('Influencer', related_name="mails", null=True, blank=True)
    influencer_mail = models.CharField(max_length=256)
    brand = models.ForeignKey('Brands', related_name="mails", null=True, blank=True)
    brand_mail = models.CharField(max_length=256)
    initiator = models.ForeignKey(User, related_name='mails', null=True, blank=True)
    has_been_read_by_brand = models.NullBooleanField(default=True)
    info = models.TextField(null=True)

    stage = models.IntegerField(
        null=True, default=STAGE_PRE_OUTREACH, choices=STAGE)
    campaign_stage = models.IntegerField(
        null=True, default=CAMPAIGN_STAGE_WAITING_ON_RESPONSE, choices=CAMPAIGN_STAGE)

    objects = MailProxyManager()

    @staticmethod
    def create_box(brand, influencer):
        mp = MailProxy.objects.create(influencer=influencer, brand=brand)

        generate_mail = lambda m, x, t: "%s_%s_id_%s@reply.theshelf.com" % (t, str(x.id), str(m.id))

        mp.influencer_mail = generate_mail(mp, influencer, "i")
        mp.brand_mail = generate_mail(mp, brand, "b")
        mp.set_info('version', '1.1')
        mp.set_info('use_extended_names', True)
        mp.save()

        return mp

    @staticmethod
    def get_or_create(brand, influencer):
        mps = MailProxy.objects.filter(brand=brand, influencer=influencer)
        if mps:
            return mps[0]
        else:
            return MailProxy.create_box(brand=brand, influencer=influencer)

    def update_in_cache(self, timeout=0):
        try:
            del self.first_message
        except AttributeError:
            pass
        try:
            del self.subject
        except AttributeError:
            pass
        redis_cache.set('sb_{}'.format(self.id), self.subject, timeout=timeout)

    # trigger all baking handlers
    def rebake(self):
        pass

    def send_email_as_brand(self, sender, subject, body, attachments=None):
        return mail_proxy.send_email(self, sender, subject, body, MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER, attachments)

    def send_email_as_influencer(self, subject, body, attachments=None):
        return mail_proxy.send_email(self, None, subject, body, MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND, attachments)

    @property
    def info_json(self):
        try:
            return json.loads(self.info)
        except:
            return {}

    def set_info(self, key, value):
        info_json = self.info_json
        info_json[key] = value
        self.info = json.dumps(info_json)

    @property
    def mailbox(self):
        return self

    @property
    def reply_stamp(self):
        if self.mails:
            return self.mails[-1]["ts"]
        return None

    @property
    def opened_count(self):
        count = 0
        for m in self.mails:
            if m["type"] in (MailProxyMessage.TYPE_OPEN, MailProxyMessage.TYPE_CLICK):
                count += 1
        return count

    @property
    def emails_count(self):
        count = 0
        for m in self.mails:
            if m["type"] == MailProxyMessage.TYPE_EMAIL:
                count += 1
        return count

    @property
    def post_stamp(self):
        threads = self.mails
        if not threads:
            return None
        return threads[0]["ts"]

    @property
    def mails(self):
        mails = short_cache.get('%i_mp_mails_cache' % self.id)
        if mails is not None:
            return mails
        mails = list(self.threads.all().exclude(mandrill_id='.').order_by('ts').only(
            'id', 'ts', 'type', 'direction').values('id', 'ts', 'type', 'direction'))
        short_cache.set('%i_mp_mails_cache' % self.id, mails)
        return mails

    @cached_property
    def first_message(self):
        try:
            return self._first_message
        except AttributeError:
            pass
        try:
            self._prefetched_objects_cache['threads']
        except (AttributeError, KeyError):
            messages = self.threads.filter(
                type=MailProxyMessage.TYPE_EMAIL).order_by('ts')
        else:
            messages = sorted([
                t for t in self._prefetched_objects_cache['threads']
                if t.type == MailProxyMessage.TYPE_EMAIL], key=lambda x: x.ts)
        try:
            return messages[0].msg
        except IndexError:
            pass

    @cached_property
    def subject(self):
        from email import message_from_string
        _t0 = time.time()
        try:
            subject = self._subject
        except AttributeError:
            subject = redis_cache.get('sb_'.format(self.id))
        if subject is None:
            try:
                subject = message_from_string(
                        self.first_message.encode('utf-8'))['subject']
            except:
                subject = ''
        # print '** getting subject took {}'.format(time.time() - _t0)
        return subject

    @property
    def collection(self):
        """
        Get collection associated (or None)

        mailbox_group_pairs = InfluencerGroupMapping.objects.values_list('mailbox', 'group')
        d = defaultdict(set)
        for k, v in mailbox_group_pairs:
            d[k].add(v)

        d[i] - set of collections(groups) that mailbox has relation to

        len(filter(lambda x: len(x) > 1, d.values())) = 1 for now

        """

        try:
            return self.candidate_mapping.all()[0].mapping.group
        except (IndexError, AttributeError):
            pass
        try:
            return self.mapping.all()[0].group
        except (IndexError, AttributeError):
            return None

    @property
    def campaign(self):
        """
        Get campaign associated (or None)
        """
        try:
            return self.candidate_mapping.all()[0].job
        except (IndexError, AttributeError):
            return None

    @property
    def influencer_name(self):
        try:
            if self.info_json.get('use_extended_names'):
                if self.influencer.blogname:
                    return '{} from {}'.format(
                        self.influencer.first_name, self.influencer.blogname)
                else:
                    return self.influencer.first_name
            else:
                return self.influencer.name
        except:
            return self.influencer_name

    @property
    def brand_name(self):
        try:
            if self.info_json.get('use_extended_names'):
                if self.initiator and self.initiator.userprofile:
                    return '{} from {}'.format(
                        self.initiator.userprofile.first_name, self.brand.name)
            return self.brand.name
        except:
            return self.brand.name


class MailProxyMessage(models.Model):
    DIRECTION_BRAND_2_INFLUENCER = 1
    DIRECTION_INFLUENCER_2_BRAND = 2
    DIRECTION_NONE = 3
    DIRECTIONS = (
        (DIRECTION_INFLUENCER_2_BRAND, "Influencer to brand"),
        (DIRECTION_BRAND_2_INFLUENCER, "Brand to influencer"),
        (DIRECTION_NONE, "None"),
    )
    TYPE_EMAIL = 1
    TYPE_CLICK = 2
    TYPE_OPEN = 3
    TYPE_SEND = 4
    TYPE_SPAM = 5
    TYPE_BOUNCE = 6
    TYPES = (
        (TYPE_EMAIL, "Email"),
        (TYPE_CLICK, "Click"),
        (TYPE_OPEN, "Open"),
        (TYPE_SEND, "Send"),
        (TYPE_SPAM, "Spam"),
        (TYPE_BOUNCE, "Bounce"),
    )
    thread = models.ForeignKey('MailProxy', related_name="threads")
    msg = models.TextField()
    ts = models.DateTimeField()
    direction = models.IntegerField(choices=DIRECTIONS)
    type = models.IntegerField(choices=TYPES)
    mandrill_id = models.CharField(max_length=45)
    attachments = JSONField(null=True)

    class Meta:
        get_latest_by = "ts"

    def update_in_cache(self, timeout=0):
        if self.thread:
            try:
                del self.thread.first_message
            except AttributeError:
                pass
            try:
                del self.thread.subject
            except AttributeError:
                pass
            redis_cache.set('sb_{}'.format(self.thread_id), self.thread.subject,
                timeout=timeout)
        # from debra.serializers import MailProxyCountsSerializer
        # if not self.thread_id:
        #     return
        # data_list = list(MailProxy.objects.filter(
        #     id=self.thread_id).mailbox_counts())
        # serialized_data = MailProxyCountsSerializer.cache_serializer().pack(
        #     data_list)
        # mc_cache.set('mpc_{}'.format(self.thread_id), serialized_data,
        #     timeout=timeout)

    def send(self):
        from debra import mail_proxy
        from debra.serializers import transform_msg
        d = transform_msg(self.msg)
        body = d['body']
        subject = d['subject']
        if self.direction == MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER:
            mail_proxy.send_email(
                self.thread, None, subject, body, MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER, self.attachments, resend=self)
        else:
            mail_proxy.send_email(
                self.thread, None, subject, body, MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND, self.attachments, resend=self)

    @classmethod
    def get_subject_from_msg(cls, msg):
        from email import message_from_string
        if not msg:
            return
        return message_from_string(msg.encode('utf-8'))['subject']


class BrandSavedCompetitors(models.Model):
    brand = models.ForeignKey('Brands', related_name='competitors')
    competitor = models.ForeignKey('Brands', related_name='as_competitor')
    timestamp = models.DateField(auto_now_add=True)


class Brands(models.Model):

    BLACKLIST_REASONS = (
        (1, "Not a url"),
        (2, "Broken url"),
        (3, "Parked url"),
        (4, "Not a store"),
    )

    BRAND_TYPES = (
        (1, "Brand"),
        (2, "Aggregator"),
    )

    name = models.CharField(max_length=200, default='Nil', db_index=True)
    shopstyle_id = models.CharField(max_length=200, default='Nil')
    domain_name = models.CharField(max_length=200, default='Nil', db_index=True)
    supported = models.BooleanField(default=False, db_index=True)
    promo_discovery_support = models.BooleanField(default=False)
    icon_id = models.CharField(max_length=50, null=True, blank=True)
    crawler_name = models.CharField(max_length=50, default='Nil')
    start_url = models.CharField(max_length=100, default='Nil')

    partially_supported = models.BooleanField(default=False)
    disable_tracking_temporarily = models.BooleanField(default=False)

    ##--< Brand Images >--##
    logo_img_url = models.CharField(max_length=200, default='Nil')
    logo_blueimg_url = models.CharField(max_length=200, default='Nil')

    ##--< Flags >--##
    is_active = models.BooleanField(default=False)
    is_claimed = models.BooleanField(default=True)
    is_agency = models.NullBooleanField(default=False)

    ##--< Subscription Fields >--##
    is_subscribed = models.BooleanField(default=False)
    stripe_id = models.CharField(max_length=200, blank=True, null=True, default=None)
    stripe_plan = models.CharField(max_length=200, blank=True, null=True, default=None)
    stripe_monthly_cost = models.IntegerField(blank=True, null=True)
    num_querys_remaining = models.IntegerField(default=40)

    ##--< Stats Fields >--##
    num_items_shelved = models.IntegerField(default=0)
    num_shelfers = models.IntegerField(default=0)
    num_items_have_price_alerts = models.IntegerField(default=0)

    ##--< XPath Fields >--##
    product_name_xpath = models.CharField(max_length=1000, null=True, blank=True)
    product_price_xpath = models.CharField(max_length=1000, null=True, blank=True)
    product_img_xpath = models.CharField(max_length=1000, null=True, blank=True)

    classification = models.CharField(max_length=100, null=True, blank=True)

    # Tags assigned by us to each brand to characterize their demographics, style, price range, focus etc.
    #brand_self_assigned_styletags = models.TextField(blank=True, null=True, default=None)
    #internally_assigned_styletags = models.TextField(blank=True, null=True, default=None)

    #####-----< Constants >-----#####
    # cost of a brand subcription (in cents)
    SUBSCRIPTION_COST = 100 * 100
    # the number of results to limit to if the brand is not subscribed
    RESULTS_LIM_IF_NOT_SUBSCRIBED = 8
    #####-----</ Constants >-----#####

    # if this is true, we don't allow importing from this brand (e.g., google.com, wikipedia, etc., that a user might
    # have accidentally bookmarked
    blacklisted = models.BooleanField(default=False)
    blacklist_reason = models.IntegerField(null=True, blank=True, choices=BLACKLIST_REASONS)

    analytics_tab_visible = models.BooleanField(default=False)

    similar_brands = models.ManyToManyField('self')
    description = models.TextField(null=True, blank=True)
    categories = models.ManyToManyField('BrandCategory')
    date_edited = models.DateTimeField(null=True, blank=True)
    date_validated = models.DateTimeField(null=True, blank=True)
    brand_type = models.IntegerField(null=True, blank=True, choices=BRAND_TYPES)

    products_count = models.IntegerField(default=0, null=True)

    brand_setup = models.TextField(null=True, blank=True)

    def _set_flag(self, key, value):
        try:
            brand_setup = json.loads(self.brand_setup)
        except:
            brand_setup = {}
        brand_setup[key] = value
        self.brand_setup = json.dumps(brand_setup)

    def _get_flag(self, key, default=None):
        try:
            brand_setup = json.loads(self.brand_setup)
        except:
            brand_setup = {}
        return brand_setup.get(key, default)

    @property
    def flag_search_method(self):
        return self._get_flag('search_method', 'default')

    @flag_search_method.setter
    def flag_search_method(self, value):
        self._set_flag('search_method', value)

    @property
    def flag_search_view_mode(self):
        return self._get_flag('search_view_mode', 'grid')

    @flag_search_view_mode.setter
    def flag_search_view_mode(self, value):
        self._set_flag('search_view_mode', value)

    @property
    def flag_bloggers_custom_data_enabled(self):
        return self._get_flag('bloggers_custom_data_enabled', False)

    @flag_bloggers_custom_data_enabled.setter
    def flag_bloggers_custom_data_enabled(self, value):
        self._set_flag('bloggers_custom_data_enabled', bool(value))

    @property
    def flag_skipping_stages_enabled(self):
        return self._get_flag('skipping_stages_enabled', False)

    @flag_skipping_stages_enabled.setter
    def flag_skipping_stages_enabled(self, value):
        self._set_flag('skipping_stages_enabled', bool(value))

    @property
    def flag_trial_on(self):
        return self._get_flag("trial_on", False)

    @flag_trial_on.setter
    def flag_trial_on(self, value):
        self._set_flag("trial_on", value)

    @property
    def flag_post_approval_enabled(self):
        return self._get_flag("post_approval_enabled", False)

    @flag_post_approval_enabled.setter
    def flag_post_approval_enabled(self, value):
        self._set_flag("post_approval_enabled", bool(value))

    @property
    def flag_age_distribution_on(self):
        return self._get_flag("age_distribution_on", False)

    @flag_age_distribution_on.setter
    def flag_age_distribution_on(self, value):
        self._set_flag("age_distribution_on", bool(value))

    @property
    def flag_services_plan(self):
        return self._get_flag("services_plan", False)

    @flag_services_plan.setter
    def flag_services_plan(self, value):
        if value and value != '0':
            self._set_flag("services_plan", True)
        else:
            self._set_flag("services_plan", False)

    @property
    def flag_one_time_fee(self):
        return self._get_flag("one_time_fee", "0.000")

    @flag_one_time_fee.setter
    def flag_one_time_fee(self, value):
        self._set_flag("one_time_fee", value)

    @property
    def flag_one_time_fee_on(self):
        try:
            return float(self.flag_one_time_fee) > 0
        except ValueError:
            return False

    @property
    def flag_show_dummy_data(self):
        value = self._get_flag("show_dummy_data")
        if value is None:
            return self.flag_trial_on
        else:
            return value

    @flag_show_dummy_data.setter
    def flag_show_dummy_data(self, value):
        value = bool(value and value != '0')
        self._set_flag("show_dummy_data", value)

    @property
    def flag_instagram_search(self):
        return self._get_flag("instagram_search", False)

    @flag_instagram_search.setter
    def flag_instagram_search(self, value):
        self._set_flag("instagram_search", value)

    @property
    def flag_export_collection_on(self):
        return self._get_flag("export_collection_on", False)

    @flag_export_collection_on.setter
    def flag_export_collection_on(self, value):
        self._set_flag("export_collection_on", value)

    @property
    def flag_post_reporting_on(self):
        return self._get_flag("post_reporting_on", False)

    @flag_post_reporting_on.setter
    def flag_post_reporting_on(self, value):
        self._set_flag("post_reporting_on", value)

    @property
    def flag_and_or_filter_on(self):
        return self._get_flag("and_or_filter_on", False)

    @flag_and_or_filter_on.setter
    def flag_and_or_filter_on(self, value):
        self._set_flag("and_or_filter_on", value)

    @property
    def flag_compete_api_key_available(self):
        return self._get_flag("compete_api_key_available", False)

    @flag_compete_api_key_available.setter
    def flag_compete_api_key_available(self, value):
        self._set_flag("compete_api_key_available", value)

    @property
    def flag_compete_api_key(self):
        return self._get_flag("compete_api_key", "")

    @flag_compete_api_key.setter
    def flag_compete_api_key(self, value):
        self._set_flag("compete_api_key", value)

    @property
    def flag_last_payment_amount(self):
        return self._get_flag("last_payment_amount", 0)

    @flag_last_payment_amount.setter
    def flag_last_payment_amount(self, value):
        if value:
            self._set_flag("last_payment_amount", value)

    @property
    def flag_stripe_customer_created(self):
        return self._get_flag("stripe_customer_created", None)

    @flag_stripe_customer_created.setter
    def flag_stripe_customer_created(self, value):
        if value:
            self._set_flag("stripe_customer_created", value)

    @property
    def flag_report_roi_prediction(self):
        return self._get_flag("report_roi_prediction", False)

    @flag_report_roi_prediction.setter
    def flag_report_roi_prediction(self, value):
        self._set_flag("report_roi_prediction", value and value != '0')

    @property
    def flag_show_other_plans(self):
        return self._get_flag("show_other_plans", True)

    @flag_show_other_plans.setter
    def flag_show_other_plans(self, value):
        if value and value != '0':
            self._set_flag("show_other_plans", True)
        else:
            self._set_flag("show_other_plans", False)

    @property
    def flag_plan_period(self):
        return self._get_flag("plan_period", "month")

    @flag_plan_period.setter
    def flag_plan_period(self, value):
        if not value or value not in ["month", "year"]:
            value = "month"
        self._set_flag("plan_period", value)

    @property
    def flag_suspended(self):
        return self._get_flag("suspended", False)

    @flag_suspended.setter
    def flag_suspended(self, value):
        value = bool(value and value != '0')
        self._set_flag("suspended", value)

    @property
    def flag_suspend_reason(self):
        return self._get_flag("suspend_reason", None)

    @flag_suspend_reason.setter
    def flag_suspend_reason(self, value):
        self._set_flag("suspend_reason", value)

    @property
    def flag_locked(self):
        return self._get_flag("locked", True)

    @flag_locked.setter
    def flag_locked(self, value):
        if value and value != '0':
            self._set_flag("locked", True)
        else:
            self._set_flag("locked", False)

    @property
    def flag_previous_campaign_link_version(self):
        return self._get_flag("previous_campaign_link_version", False)

    @flag_previous_campaign_link_version.setter
    def flag_previous_campaign_link_version(self, value):
        if value and value != '0':
            self._set_flag("previous_campaign_link_version", True)
        else:
            self._set_flag("previous_campaign_link_version", False)

    @property
    def flag_availiable_plan(self):
        return self._get_flag("availiable_plan", None)

    @flag_availiable_plan.setter
    def flag_availiable_plan(self, value):
        self._set_flag("availiable_plan", value)

    @property
    def flag_campaigns_enabled(self):
        return self._get_flag("campaigns_enabled", None)

    @flag_campaigns_enabled.setter
    def flag_campaigns_enabled(self, value):
        self._set_flag("campaigns_enabled", value)

    @property
    def flag_profile_enabled(self):
        return self._get_flag("profile_enabled", None)

    @flag_profile_enabled.setter
    def flag_profile_enabled(self, value):
        self._set_flag("profile_enabled", value)

    @property
    def flag_non_campaign_messaging_enabled(self):
        return self._get_flag("non_campaign_messaging_enabled", False)

    @flag_non_campaign_messaging_enabled.setter
    def flag_non_campaign_messaging_enabled(self, value):
        self._set_flag("non_campaign_messaging_enabled", value)

    @property
    def flag_blur_cover(self):
        return self._get_flag("blur_cover", True)

    @flag_blur_cover.setter
    def flag_blur_cover(self, value):
        self._set_flag("blur_cover", value)

    @property
    def flag_blur_camp_cover(self):
        return self._get_flag("blur_camp_cover", True)

    @flag_blur_camp_cover.setter
    def flag_blur_camp_cover(self, value):
        self._set_flag("blur_camp_cover", value)

    @property
    def flag_default_invitation_campaign(self):
        return self._get_flag('default_invitation_campaign')

    @flag_default_invitation_campaign.setter
    def flag_default_invitation_campaign(self, value):
        self._set_flag(
            'default_invitation_campaign',
            int(value) if value is not None else None)

    @property
    def profile_img_url(self):
        return self._get_flag("profile_img_url", [])

    @profile_img_url.setter
    def profile_img_url(self, value):
        self._set_flag("profile_img_url", value)

    @property
    def cover_img_url(self):
        return self._get_flag("cover_img_url", [])

    @cover_img_url.setter
    def cover_img_url(self, value):
        self._set_flag("cover_img_url", value)

    @property
    def brand_weblink(self):
        result = self._get_flag("brand_weblink", None)
        if not result:
            result = self.domain_name
        return result

    @brand_weblink.setter
    def brand_weblink(self, value):
        self._set_flag("brand_weblink", value)

    #####-----< External Model Queries >-----#####
    def save_classification(self, res):
        """
        This method is invoked by the contentclassification module:
        we first save the result
        and then check if the result=='blog', then blacklisted=False, else blacklisted=True
        """
        self.classification = res
        if res == 'brand':
            self.blacklisted = False
        else:
            self.blacklisted = True
        self.save()

    def users_brand_shelves(self):
        '''
        get those shelves that point to this brand
        @return QuerySet of shelves that point to this brand
        '''
        return Shelf.objects.filter(brand=self).select_related('user_id', 'user_id__userprofile')
    #####-----</ External Model Queries >-----#####

    #####-----< Classmethods >------#####
    @classmethod
    def get_guessed_brand_url(cls, product_url):
        '''
        make an intelligent guess at this brands url by taking everything up to the first slash after http:// on the product_url
        @param product_url - the product url we're forming our guess off of
        @return the guessed brand url
        '''
        # the https offset forces the regex to start searching the string after the // following http[s]
        HTTPS_OFFSET = 9
        first_slash_pattern = re.compile(r"\/")
        first_slash = first_slash_pattern.search(product_url, HTTPS_OFFSET)

        return product_url[:first_slash.start()]
    #####-----</ Classmethods >------#####

    #####-----< Calculated Fields >-----#####
    @property
    def profile_url(self):
        return reverse('debra.brand_views.brand_home', args=(self.userprofile.id,))

    @property
    def products(self):
        return ProductModelShelfMap.objects.filter(product_model__brand=self)
    #####-----</ Calculated Fields >-----#####

    #####-----< Django Overrides >-----#####
    def __unicode__(self):
        return '%r %s %r' % (self.name, self.id, self.domain_name)

    def get_absolute_url(self):
        return reverse('debra.brand_views.brand_home', args=(self.userprofile.id,))

    def denormalize(self):
        self.products_count = self.productmodel_set.count()
        self.save()

    class Meta:
        ordering = ['-products_count']
        verbose_name_plural = "brands"

    #####-----</ Django Overrides >-----#####

    #####-----<  Intercom >-----#####
    def get_intercom_company_data(self):
        plan = "Trial"
        spend = 0
        if self.is_subscribed:
            if not self.stripe_plan or self.stripe_monthly_cost is None:
                self.refresh_stripe_data()
            if not self.stripe_plan or self.stripe_monthly_cost is None:
                return {}
            plan = self.stripe_plan
            spend = self.stripe_monthly_cost / 100.0
        return {
            'id': self.id,
            'name': self.name,
            # 'subscribed': self.is_subscribed,
            'plan': plan,
            'monthly_spend': spend,
            'created_at': int(self.userprofile.user.date_joined.strftime("%s"))
        }
    #####-----</ Intercom >-----#####

    #####-----<  Stripe >-----#####
    def refresh_stripe_data(self):
        brand = Brands.objects.get(id=self.id)
        if not brand.stripe_id:
            brand.is_subscribed = False
            brand.stripe_monthly_cost = 0
            brand.stripe_plan = None
            brand.save()
            return
        try:
            customer = stripe.Customer.retrieve(brand.stripe_id)
        except:
            brand.stripe_monthly_cost = 0
            brand.stripe_plan = None
            brand.is_subscribed = False
            brand.save()
            return

        brand.stripe_monthly_cost = 0
        brand.stripe_plan = None

        for sub in customer.subscriptions.data:
            plan = sub.plan
            if plan.id in constants.STRIPE_SUBSCRIPTIONS_PLANS:
                brand.stripe_plan = plan.id
            cost = plan.amount * sub.quantity
            if sub.discount:
                percent_off = sub.discount.coupon.percent_off
                amount_off = sub.discount.coupon.amount_off
                if percent_off:
                    cost = cost * (1 - percent_off / 100.0)
                if amount_off:
                    cost = cost - amount_off
            brand.stripe_monthly_cost += cost
        if brand.flag_one_time_fee_on:
            brand.stripe_plan = 'ONE_TIME_FEE'
        brand.is_subscribed = True
        brand.save()

    #####-----</ Stripe >-----#####

    def save(self, *args, **kwargs):
        if not self.id:
            self.flag_locked = True
        return super(Brands, self).save(*args, **kwargs)

    # helpers

    def get_owner_user_profile(self):
        for priv in self.related_user_profiles.all():
            if priv.permissions == UserProfileBrandPrivilages.PRIVILAGE_OWNER:
                return priv.user_profile
        return None

    def get_managed_brands(self):
        owner = self.get_owner_user_profile()
        if owner is None:
            return []
        brands = [x[0] for x in owner.brand_privilages.filter(
            permissions=UserProfileBrandPrivilages.PRIVILAGE_AGENCY).values_list('brand')]
        return Brands.objects.filter(id__in=brands)

    # profile methods / properties
    def _brand_page_kwargs(self):
        return {'brand_url': self.domain_name, 'brand_id': self.id}

    @property
    @cached_model_property
    def hasPseudoinfluencer(self):
        return Influencer.objects.filter(
            name=self.domain_name,
            source='brands'
        ).exists()

    @property
    def pseudoinfluencer(self):
        params = dict(name=self.domain_name, source='brands')
        try:
            prefetched = Influencer.objects.filter(**params)[0]
        except IndexError:
            prefetched = Influencer.objects.create(**params)
        if prefetched.show_on_search is not True:
            prefetched.show_on_search = True
            prefetched.save()
        if prefetched.last_modified is None:
            prefetched.last_modified = datetime.now()
            prefetched.save()
        return prefetched

    @property
    @cached_model_property
    def about_page(self):
        return reverse('debra.brand_profile_views.brand_about', kwargs=self._brand_page_kwargs())

    @property
    @cached_model_property
    def edit_page(self):
        return reverse('debra.brand_profile_views.brand_edit', kwargs=self._brand_page_kwargs())
        # return reverse('debra.brand_account_views.account_landing')+"#/5"

    @property
    @cached_model_property
    def posts_page(self):
        return reverse('debra.brand_profile_views.brand_posts', kwargs=self._brand_page_kwargs())

    @property
    @cached_model_property
    def items_page(self):
        return reverse('debra.brand_profile_views.brand_items', kwargs=self._brand_page_kwargs())

    @property
    @cached_model_property
    def photos_page(self):
        return reverse('debra.brand_profile_views.brand_photos', kwargs=self._brand_page_kwargs())

    @property
    @cached_model_property
    def tweets_page(self):
        return reverse('debra.brand_profile_views.brand_tweets', kwargs=self._brand_page_kwargs())

    @property
    @cached_model_property
    def pins_page(self):
        return reverse('debra.brand_profile_views.brand_pins', kwargs=self._brand_page_kwargs())

    @property
    @cached_model_property
    def items_count(self):
        return feeds_helpers.product_feed_json(request=True, for_influencer=self.pseudoinfluencer, count_only=True)

    @property
    @cached_model_property
    def photos_count(self):
        return feeds_helpers.instagram_feed_json(request=True, for_influencer=self.pseudoinfluencer, count_only=True, default_posts="about_insta")

    @property
    @cached_model_property
    def pins_count(self):
        return feeds_helpers.pinterest_feed_json(request=True, for_influencer=self.pseudoinfluencer, count_only=True, default_posts="about_pins")

    @property
    @cached_model_property
    def tweets_count(self):
        return feeds_helpers.twitter_feed_json(request=True, for_influencer=self.pseudoinfluencer, count_only=True, default_posts="about_tweets")

    @property
    @cached_model_property
    def blog_posts_count(self):
        return feeds_helpers.blog_feed_json_dashboard(request=True, for_influencer=self.pseudoinfluencer, count_only=True, default_posts="about")

    @property
    def profile_pic(self):
        p_img = self.profile_img_url
        if p_img:
            return p_img
        return self.pseudoinfluencer.profile_pic

    @property
    def cover_pic(self):
        c_img = self.cover_img_url
        if c_img:
            return c_img
        tw = [p for p in self.pseudoinfluencer.platform_set.all() if p.platform_name == "Twitter" and p.profile_img_url]
        if len(tw) > 0:
            return tw[0].cover_img_url
        else:
            fb = [p for p in self.pseudoinfluencer.platform_set.all() if p.platform_name == "Facebook"]
            if len(fb) > 0:
                return fb[0].cover_img_url

        return self.pseudoinfluencer.cover_pic


    def get_visible_tags_list(self):
        from debra.serializers import unescape
        _qs = self.influencer_groups.exclude(
            archived=True
        ).filter(
            creator_brand=self,
            system_collection=False,
        ).order_by('name').only(
            'id', 'name', 'influencers_count'
        )
        return [{
            'id': t.id,
            'name': unescape(t.name),
            'count': t.influencers_count,
        } for t in _qs]

    def get_visible_post_collections_list(self, with_counts=False):
        from debra.serializers import unescape
        _qs = self.created_post_analytics_collections.exclude(
            archived=True
        ).filter(
            system_collection=False
        )
        if with_counts:
            _qs = _qs.annotate(
                infs_count=Count('postanalytics__post__influencer',
                    distinct=True))
        _qs = _qs.order_by('name').values('id', 'name', 'infs_count')
        return [{
            'id': t['id'],
            'name': unescape(t['name']),
            'count': t['infs_count'] if with_counts else None,
        } for t in _qs]


class SearchQueryArchive(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True)
    brand = models.ForeignKey(Brands, related_name="saved_queries")
    user = models.ForeignKey(User, related_name="saved_queries", null=True)
    query = models.TextField()
    result = JSONField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    archived = models.NullBooleanField(blank=True, null=True, default=False)

    @property
    def query_json(self):
        return json.loads(self.query)

    @property
    def result_json(self):
        return json.loads(self.result)

    def __unicode__(self):
        return self.query

    class Meta:
        ordering = ['-timestamp']


class BetaBrandRequests(models.Model):

    '''
    brands that request to sign up with us during beta period
    '''
    signup_user = models.CharField(max_length=200, default='')
    signup_user_email = models.CharField(max_length=200, default='')
    url = models.CharField(max_length=200, )
    name = models.CharField(max_length=100, default='')


class BrandCampaign(models.Model):
    brand = models.ForeignKey(Brands, related_name="campaigns")
    type_of_campaign = models.CharField(max_length=64)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField()
    filters_json = models.TextField()


#####-----#####-----#####-----< ProductModel Tables >-----#####-----#####-----#####


class ProductModel(models.Model):

    '''
    This model holds the items scraped by our spiders
    '''
    brand = models.ForeignKey(Brands, default='1')
    designer_name = models.CharField(max_length=200, blank=True, null=True, default=None)
    name = models.CharField(max_length=200, default='Nil')
    prod_url = models.URLField(max_length=2000, verify_exists=False, default='Nil', db_index=True)
    price = models.FloatField(max_length=10, default='-11.0')
    saleprice = models.FloatField(max_length=10, default='-11.0')
    promo_text = models.CharField(max_length=200, default='Nil')
    img_url = models.URLField(max_length=2000, verify_exists=False, default='Nil')
    description = models.TextField(default='Nil')
    insert_date = models.DateTimeField('Date inserted', default=datetime.now, db_index=True)
    cat1 = models.CharField(max_length=25, blank=True, null=True)
    cat2 = models.CharField(max_length=25, blank=True, null=True)
    cat3 = models.CharField(max_length=25, blank=True, null=True)
    c_idx = models.CharField(max_length=300, blank=True, default='')  # the product id
    small_image = models.BooleanField(default=False)

    num_fb_likes = models.IntegerField(default=0)
    num_twitter_mentions = models.IntegerField(default=0)
    num_pins = models.IntegerField(default=0)

    # does this productmodel have any problems as found by morgan?
    problems = models.CharField(max_length=100, blank=True, null=True)

    #####-----< Methods >-----#####
    def shelves_on(self, for_user=None):
        '''
        get all shelves that this ProductModel is on
        @param for_user - if set, only return shelves that are created by the given user
        @return QuerySet of Shelf that have this WishlistItem on them
        '''
        mappings = ProductModelShelfMap.objects.filter(product_model=self).select_related('shelf')
        shelf_ids = [m.shelf.id for m in mappings]
        shelves = Shelf.objects.filter(id__in=shelf_ids)
        return shelves.filter(user_id=for_user) if for_user else shelves

    def public_shelves_on(self, for_user=None):
        '''
        get the public, non deleted shelves that this product model is on
        @param for_user - if set, only return shelves that are created by the given user
        @return QuerySet of public Shelfs that have this ProductModel on them
        '''
        # in the future we should have is_deleted=False, however first have to
        # decide on what happens when a shelf is deleted
        return self.shelves_on(for_user=for_user).filter(is_public=True)

    def user_created_shelves_on(self, for_user=None):
        '''
        get the user created shelves that this product model is on
        @param for_user - if set, only return shelves that are created by the given user
        @return QuerySet of user created Shelfs that have this ProductModel on them
        '''
        # in the future we should have is_deleted=False, however first have to
        # decide on what happens when a shelf is deleted
        return self.shelves_on(for_user=for_user).filter(user_created_cat=True)

    def remove_from_users_shelves(self, user_prof):
        '''
        a method to remove this product model from all of the given users shelves
        @param user_prof - the UserProfile to remove shelf mappings to this ProductModel for
        '''
        ProductModelShelfMap.objects.filter(user_prof=user_prof, product_model=self).delete()

    def add_to_shelves(self, ids, user_prof, boilerplate):
        '''
        a method to add this ProductModel instance to the given shelves
        @param ids - comma separated string of shelf ids to add the item to (note: this should also include shelves the item is already on)
        @param user_prof - the UserProfile who is adding the product
        @param boilerplate - this was the ProductModelShelfMap instance that was actually selected to be added to the users shelves.
        If the user doesnt already have a mapping of this product model to a given shelf, the boilerplate will be used
        to create the produced ProductModelShelfMap instance
        @return array of dictionaries containing ids and num_items for the shelves that the item was added to
        '''
        user = user_prof.user
        json_result = []
        not_liked = ids and ids != ''

        # get or create the brand shelf for this user/item combo
        brand = self.brand
        brand_shelf = Shelf.objects.get_or_create(
            name=brand.name, user_id=user, brand=brand, is_public=False, user_created_cat=False)[0]
        brand_shelf.add_item_to_self(self, user_prof, boilerplate)

        # make the user who just shelfed the item a "follower" of the brand
        brand.userprofile.add_follower(user_prof)
        # get the shelves the item is already on. We need these so if the item is deleted from a shelf in the
        # add item to shelves lightbox, we can know to delete that mapping (only
        # do this if the 'Like' button wasn't clicked)
        on_shelves = {shelf.id: shelf for shelf in self.public_shelves_on(for_user=user)} if not_liked else {}

        shelf_ids = [int(shelf_id) for shelf_id in ids.split(',')] if not_liked else [-1]
        for s_id in shelf_ids:
            # if the shelf id is negative, we know the user quick shelved the item and it should be added to "My Likes"
            shelf = Shelf.objects.get(id=s_id) if s_id > 0 else Shelf.objects.get_or_create(
                name=constants.LIKED_SHELF, user_id=user)[0]
            # create the mapping for the user created shelf
            mapping = shelf.add_item_to_self(self, user_prof, boilerplate)
            # add the shelf to the json result
            json_result.append({
                'id': s_id,
                'num_items': mapping.shelf.num_items
            })
            # if the shelf id is in the on_shelves mapping, pop that entry
            on_shelves.pop(s_id) if on_shelves.get(s_id) else None

        # if anything is left in on_shelves, then we have to remove the item from those shelves
        for s_id, obj in on_shelves.items():
            shelf = Shelf.objects.get(id=s_id)
            # don't delete the constants.LIKED_SHELF mapping unless explicitly deleted using remove_from_user_shelves()
            if shelf.name == constants.LIKED_SHELF:
                continue
            shelf.remove_product_from_self(self)

        return json_result

    def get_color_sizes(self):
        return ColorSizeModel.objects.select_related('color_data').filter(product=self)

    #####-----</ Methods >-----#####

    def tag_small_images(self):
        dims = models.get_dims_for_url(self.img_url)
        if dims[0] > 200 and dims[1] > 200 and dims[0] < dims[1] * 3:
            self.small_image = False
        else:
            self.small_image = True
        self.save()
        return self.small_image

    def __unicode__(self):
        return u'%s %s %s %s' % (self.id, self.name, self.price, self.saleprice)

@receiver(post_delete, sender=ProductModel)
def delete_product_from_es(sender, instance, **kwargs):
    """
    Deletes data of product from ElasticSearch index after it is deleted from DB.
    :param sender:
    :param instance:
    :param using:
    :return:
    """
    endpoint = "/%s/product/%s" % (ELASTICSEARCH_INDEX, instance.id)
    url = ELASTICSEARCH_URL

    make_es_delete_request(es_url=url+endpoint)
    # requests.delete(url + endpoint,
    #                 auth=HTTPBasicAuth(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
    #                 )

###################################################
###################################################


class Color(models.Model):
    name = models.CharField(max_length=500, null=True, default=None)
    product_img = models.CharField(max_length=500, null=True, default=None)
    swatch_img = models.CharField(max_length=500, null=True, default=None)

    def __unicode__(self):
        return u'name={self.name}, product_img={self.product_img}, swatch_img={self.swatch_img}'.format(self=self)


class ColorSizeModel(models.Model):

    '''
    This model holds the color and size information for the products scraped by our spiders.
    We have one column for each color and size combination for each product.
    '''
    product = models.ForeignKey(ProductModel, default='0')
    color = models.CharField(max_length=500, default='Nil')
    size = models.CharField(max_length=500, default='Nil')

    color_data = models.ForeignKey(Color, null=True, default=None)

    size_standard = models.CharField(max_length=500, null=True, default=None)
    size_sizetype = models.CharField(max_length=500, null=True, default=None)
    size_inseam = models.CharField(max_length=500, null=True, default=None)

    def __unicode__(self):
        return u'%s %s: %s %s %s %s' % (self.id, self.product.brand.name, self.product.c_idx, self.product.name, self.color, self.size)


###################################################
###################################################
class ProductPrice(models.Model):
    product = models.ForeignKey(ColorSizeModel, editable=False)
    finish_time = models.DateTimeField('Finish time', auto_now_add=True)
    price = models.FloatField(max_length=10, default='-11.0')
    orig_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    shipping_cost = models.FloatField(max_length=10, default='-1.0')

    def __unicode__(self):
        return u'%s: %s %s %s' % (self.product, self.price, self.shipping_cost, self.finish_time)

###################################################
###################################################


class ProductAvailability(models.Model):
    product = models.ForeignKey(ColorSizeModel, editable=False)
    finish_time = models.DateTimeField('Finish time', auto_now_add=True)
    avail = models.BooleanField(default='false')

    def __unicode__(self):
        return u'%s: %s %s' % (self.avail, self.product, self.finish_time)

    class Meta:
        verbose_name_plural = "product availability"

###################################################
###################################################


class ProductPromotion(models.Model):
    promo = models.ForeignKey(Promoinfo, blank=True, null=True, editable=False, default='0')
    product = models.ForeignKey(ProductPrice, blank=True, null=True, editable=False, default='0')
    savings = models.FloatField(max_length=10, default='0.0')

    def __unicode__(self):
        return u'"%s" $%s' % (
            self.promo.code,
            self.savings,
        )


###################################################
# Slated for Removal
class WishlistItem(models.Model):

    '''
    This model stores info on User wishlists. One object per item in each User's wishlist.
    '''
    user_id = models.ForeignKey(User, related_name="wishlist_items", null=True, blank=True, default=None)
    product_model = models.ForeignKey(ProductModel, default=None)
    color = models.CharField(max_length=100, blank=True, null=True, default='Nil')
    size = models.CharField(max_length=100, blank=True, null=True, default='Nil')
    img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    calculated_price = models.FloatField(max_length=10, default='-11.0')
    item_out_of_stock = models.BooleanField(default=False)
    savings = models.FloatField(max_length=10, default='0')
    promo_applied = models.ForeignKey(Promoinfo, blank=True, null=True, default=None)
    shipping_cost = models.FloatField(max_length=10, default='-1')
    added_datetime = models.DateTimeField('Added to wishlist datetime', default=datetime.now, db_index=True)

    imported_from_blog = models.BooleanField(default=False)

    '''
        Notification related changes
    '''
    time_price_calculated_last = models.DateTimeField('Calculation time', default=datetime.now)
    time_notified_last = models.DateTimeField('User notification time', default=datetime.now)
    notify_lower_bound = models.FloatField(max_length=10, default='-1')
    # Snooze for this item. If false, we send only one email.User can change it to receive periodic notifications.
    snooze = models.BooleanField(default=False)

    #####-----< Flag Fields >-----#####
    bought = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    show_on_feed = models.BooleanField(default=True)
    #####-----</ Flag Fields >-----#####

    '''
      Comma seperated list of available sizes
    '''
    avail_sizes = models.CharField(max_length=2000, blank=True, null=True, default='')

    #####-----< Image Fields >-----#####
    img_url_shelf_view = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_panel_view = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_feed_view = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_thumbnail_view = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_original = models.URLField(max_length=1000, blank=True, null=True, default=None)
    #####-----</ Image Fields >-----#####

    #####-----< Affiliate Link Fields >-----#####
    affiliate_prod_link = models.URLField(max_length=1000, blank=True, null=True)
    affiliate_source_wishlist_id = models.IntegerField(max_length=100, default='-1')
    #####-----</ Affiliate Link Fields >-----#####

    #####-----< Price Tracker Fields >-----#####
    current_product_price = models.ForeignKey(ProductPrice, null=True, default=None)
    #####-----</ Price Tracker Fields >-----#####

    #####-----< Calculated Fields >-----#####
    @property
    def from_supported_store(self):
        '''
        check if this wishlist item comes from a supported brand
        @return True if from a supported store, else False
        '''
        return self.product_model.brand.supported

    @property
    def backup_prod_link(self):
        '''
        if the affiliate_prod_link for this item doesnt exist, use this instead
        @return backup prod link string
        '''
        return self.product_model.prod_url

    @property
    def similar_items(self):
        '''
        get items similar to this wishlist item, where similar is defined as having the same category
        @return QuerySet of WishlistItem that have the same category as this wishlist item
        '''
        NUM_SIMILAR = 20
        return WishlistItem.objects.filter(product_model__in=ProductModel.objects.filter(cat1=self.product_model.cat1), is_deleted=False, show_on_feed=True).all()[:NUM_SIMILAR]

    #####-----</ Calculated Fields >-----#####

    ######-----< Methods >------#####
    def remove_from_users_shelves(self):
        '''
        a method to remove this wishlist item from all of this items user's shelves, and set this WishlistItem to be deleted
        '''
        for item_map in WishlistItemShelfMap.objects.filter(wishlist_item=self, is_deleted=False):
            item_map.is_deleted = True
            item_map.save()

        self.is_deleted = True
        self.save()

        return True

    def add_to_shelves(self, ids, user):
        '''
        a method to add this wishlist item to the given shelves
        @param ids - comma separated string of shelf ids to add the item to (note: this should also include shelves the item is already on)
        @param user - the User who is adding the item
        @return array of dictionaries containing ids and num_items for the shelves that the item was added to
        '''
        json_result = []
        not_liked = ids and ids != ''

        # get or create the brand shelf for this user/item combo
        it_brand = self.product_model.brand
        brand_shelf = Shelf.objects.get_or_create(
            name=it_brand.name, user_id=user, brand=it_brand, is_public=False, user_created_cat=False)[0]
        brand_shelf.add_item_to_self(self)

        # make the user who just shelfed the item a "follower" of the brand
        it_brand.userprofile.add_follower(user.userprofile)
        # get the shelves the item is already on. We need these so if the item is deleted from a shelf in the
        # add item to shelves lightbox, we can know to delete that mapping (only
        # do this if the 'Like' button wasn't clicked)
        on_shelves = {shelf.id: shelf for shelf in self.public_shelves_on(for_user=user)} if not_liked else {}

        shelf_ids = [int(shelf_id) for shelf_id in ids.split(',')] if not_liked else [-1]
        for s_id in shelf_ids:
            # if the shelf id is negative, we know the user quick shelved the item and it should be added to "My Likes"
            shelf = Shelf.objects.get(id=s_id) if s_id > 0 else Shelf.objects.get_or_create(
                name=constants.LIKED_SHELF, user_id=user)[0]
            # create the mapping for the user created shelf
            shelf.add_item_to_self(self)
            # add the shelf to the json result
            json_result.append({
                'id': s_id,
                'num_items': shelf.num_items
            })
            # if the shelf id is in the on_shelves mapping, pop that entry
            on_shelves.pop(s_id) if on_shelves.get(s_id) else None

        # if anything is left in on_shelves, then we have to remove the item from those shelves
        for s_id, obj in on_shelves.items():
            shelf = Shelf.objects.get(id=s_id)
            shelf.remove_product_from_self(self)

        return json_result

    def clone(self, user):
        '''
        create a clone of this wishlist item
        @param user - the user the cloned wishlist item will belong to
        @return the user of the new item
        '''
        self.pk = None
        self.user_id = user
        self.added_datetime = datetime.now()
        self.is_deleted = False
        self.save()

        return self.user_id

    def shelves_on(self, for_user=None):
        '''
        get the public, non deleted shelves that this wishlist item is on
        @param for_user - if set, only return shelves that are created by the given user
        @return QuerySet of Shelf that have this WishlistItem on them
        '''
        shelves = Shelf.objects.filter(id__in=[mapping['shelf'] for mapping in WishlistItemShelfMap.objects.filter(
            wishlist_item=self, is_deleted=False).values('shelf')])
        shelves = shelves.filter(user_id=for_user) if for_user else shelves
        return shelves

    def public_shelves_on(self, for_user=None):
        '''
        get the public, non deleted shelves that this wishlist item is on
        @param for_user - if set, only return shelves that are created by the given user
        @return QuerySet of public Shelfs that have this WishlistItem on them
        '''
        # in the future we should have is_deleted=False, however first have to
        # decide on what happens when a shelf is deleted
        return self.shelves_on(for_user=for_user).filter(is_public=True)
    ######-----</ Methods >------#####

    def username(self):
        return self.user_id.username
    username.admin_order_field = 'user_id__username'

    def brand_name(self):
        return self.product_model.brand
    brand_name.admin_order_field = 'product_model__brand'

    def product_name(self):
        return self.product_model.name
    product_name.admin_order_field = 'product_model__name'

    def product_id(self):
        return self.product_model.c_idx
    product_id.admin_order_field = 'product_model__c_idx'


###################################################
###################################################
class Shelf(models.Model):
    # Foreign Keys
    brand = models.ForeignKey(Brands, null=True, blank=True)
    user_id = models.ForeignKey(User, related_name="shelves", null=True, blank=True, default=None)

    # Flags
    user_created_cat = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    imported_from_blog = models.BooleanField(default=False)

    # Char Fields
    description = models.TextField()
    name = models.CharField(max_length=100)

    # Count Fields
    num_likes = models.IntegerField(default=0)
    num_items = models.IntegerField(default=0)

    # Image Fields
    shelf_img = models.URLField(max_length=2000, blank=True, default=None, null=True)

    #####-----< Calculated Fields >-----#####
    @property
    def first_img(self):
        '''
        get the image that represents this shelf (first wishlist item on shelf for now)
        @return img url of first image on shelf, or None if no mappings matching criteria exist
        '''
        mappings = ProductModelShelfMap.objects.filter(shelf=self, img_url_thumbnail_view__isnull=False).order_by('id')
        if mappings.exists():
            return mappings[0].img_url_thumbnail_view
        else:
            return None

    @property
    def form_for_self(self):
        from debra.forms import ModifyShelfForm
        return ModifyShelfForm(instance=self)
    #####-----</ Calculated Fields >-----#####
    #####-----< Methods >-----#####

    def add_item_to_self(self, product, user_prof, boilerplate):
        '''
        a method to add a ProductModel to this shelf
        @param product - the product to add to this shelf
        @param user_prof - the user who is adding the item
        @param boilerplate - the ProductModelShelfMap instance to use if the mapping has to be created
        @return ProductModelShelfMap that was created
        '''
        mapping = ProductModelShelfMap.objects.filter(user_prof=user_prof, shelf=self, product_model=product)
        result = mapping[0] if mapping.exists() else boilerplate.clone(user_prof, self)

        return result

    def remove_product_from_self(self, product):
        '''
        a method to remove a ProductModel from this shelf
        @param product - the product to remove
        '''
        ProductModelShelfMap.objects.filter(shelf=self, product_model=product).delete()

    def remove_all_products_from_self(self):
        '''
        a method to delete all products on this shelf
        '''
        ProductModelShelfMap.objects.filter(shelf=self).delete()
    #####-----</ Methods >-----#####

    def denormalize(self):
        self.num_items = ProductModelShelfMap.objects.filter(shelf=self).count()
        self.save()

    def __unicode__(self):
        return u'%s %s %s %s %s %d %s' % (self.name, self.brand, self.user_created_cat, self.is_public,
                                          self.user_id, self.num_likes, self.description)


###################################################
# Slated For Removal
class WishlistItemShelfMap(models.Model):
    wishlist_item = models.ForeignKey(WishlistItem, null=True, blank=True, default=None)
    shelf = models.ForeignKey(Shelf, null=True, blank=True, default=None)
    is_deleted = models.BooleanField(default=False)

    def __unicode__(self):
        return u'%s %s' % (self.wishlist_item, self.shelf)

    @classmethod
    def num_shelf_items(cls, shelf):
        '''
        given a shelf, get the number of items on that shelf.
        TODO: make this a property of the class by de-normalization
        '''
        return cls.objects.filter(shelf=shelf, is_deleted=False).count()


#####-----#####-----< PostShelfMap >-----#####-----#####
#####-----#####-----< PostShelfMap >-----#####-----#####


class PostShelfMap(models.Model):

    """
    this model represents a post that a user has shelved
    """
    ##--< Foreign Keys >--##
    user_prof = models.ForeignKey('UserProfile')
    shelf = models.ForeignKey(Shelf)
    post = models.ForeignKey('Posts')


#####-----#####-----< ProductModelShelfMap >-----#####-----#####
#####-----#####-----< ProductModelShelfMap >-----#####-----#####


class ProductModelShelfMap(models.Model):

    '''
    This model represents a product that a user has shelved
    '''
    ##--< Foreign Keys >--##
    user_prof = models.ForeignKey('UserProfile', null=True, blank=True, default=None, db_index=True)
    shelf = models.ForeignKey(Shelf, null=True, blank=True, default=None, db_index=True)
    post = models.ForeignKey('Posts', null=True, blank=True, default=None, db_index=True)
    product_model = models.ForeignKey(ProductModel, default=None, db_index=True)
    current_product_price = models.ForeignKey(ProductPrice, null=True, default=None)
    promo_applied = models.ForeignKey(Promoinfo, blank=True, null=True, default=None)
    influencer = models.ForeignKey('Influencer', blank=True, null=True)

    ##--< Meta Info >--##
    color = models.CharField(max_length=100, blank=True, null=True, default='Nil')
    size = models.CharField(max_length=100, blank=True, null=True, default='Nil')
    # comma separated list of available sizes
    avail_sizes = models.CharField(max_length=2000, blank=True, null=True, default='')

    ##--< Date Fields >--##
    added_datetime = models.DateTimeField('Added to wishlist datetime', default=datetime.now, db_index=True)
    time_price_calculated_last = models.DateTimeField('Calculation time', default=datetime.now)
    time_notified_last = models.DateTimeField('User notification time', default=datetime.now)

    ##--< Pricing Fields >--##
    calculated_price = models.FloatField(max_length=10, default='-11.0')
    savings = models.FloatField(max_length=10, default='0')
    shipping_cost = models.FloatField(max_length=10, default='-1')
    notify_lower_bound = models.FloatField(max_length=10, default='-1')

    ##--< Flag Fields >--##
    bought = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    show_on_feed = models.BooleanField(default=True)
    item_out_of_stock = models.BooleanField(default=False)
    imported_from_blog = models.BooleanField(default=False)
    # Snooze for this item. If false, we send only one email.User can change it to receive periodic notifications.
    snooze = models.BooleanField(default=False)
    admin_categorized = models.BooleanField(default=False)

    ##--< Image Fields >--##
    img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_shelf_view = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_panel_view = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_feed_view = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_thumbnail_view = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_original = models.URLField(max_length=1000, blank=True, null=True, default=None)
    img_url_feed_compressed = models.URLField(max_length=1000, blank=True, null=True, default=None)

    ##--< Affiliate Link Fields >--##
    affiliate_prod_link = models.URLField(max_length=1000, blank=True, null=True)
    # this pointer lets us follow the trail to the first instance of a PMSM
    original_instance_pointer = models.ForeignKey("ProductModelShelfMap", blank=True, null=True, default=None)

    #####-----< Calculated Fields >-----#####
    @property
    def backup_prod_link(self):
        '''
        if the affiliate_prod_link for this item doesnt exist, use this instead
        @return backup prod link string
        '''
        return self.product_model.prod_url

    @property
    def from_supported_store(self):
        '''
        check if this wishlist item comes from a supported brand
        @return True if from a supported store, else False
        '''
        return self.product_model.brand.supported

    @property
    def similar_items(self):
        '''
        get items similar to this wishlist item, where similar is defined as having the same category
        @return QuerySet of ProductModelShelfMap that have the same category as this ProductModelShelfMap's product model
        '''
        NUM_SIMILAR = 20
        similar = ProductModelShelfMap.objects.filter(
            product_model__cat1=self.product_model.cat1, is_deleted=False, show_on_feed=True).distinct('product_model')
        return similar[:NUM_SIMILAR]

    @property
    def num_shelf_items(self):
        '''
        calculate the number of items on this mappings shelf (used for denormalization).
        @return int representing the number of items on the shelf
        '''
        return ProductModelShelfMap.objects.filter(shelf=self.shelf, is_deleted=False, img_url_feed_view__isnull=False).count()
    #####-----</ Calculated Fields >-----#####

    #####-----< Classmethods >-----#####
    @classmethod
    def distinct_product_model(cls, qs):
        '''
        handles a potential bug in ordering and distinct
        @return QuerySet of ProductModelShelfMap instances
        NOTE ::: DO NOT feed qs that has been ordered by id
        '''
        aggregated = qs.values('product_model').annotate(latest=Max('id'))
        return cls.objects.select_related('product_model', 'product_model__brand', 'current_product_price', 'user_prof').filter(id__in=[res['latest'] for res in aggregated]).order_by('-id')

    @classmethod
    def create_copy_from_instance(cls, instance):
        '''
        create a copy of a given ProductModelShelfMap instance and return the new copy
        @param instance - the ProductModelShelfMap instance to use as a boilerplate for copying
        @return new ProductModelShelfMap which has identical properties to the given instance
        '''
        pmsm = ProductModelShelfMap(
            user_prof=instance.user_prof, shelf=instance.shelf, product_model=instance.product_model)
        pmsm.color = instance.color
        pmsm.size = instance.size
        pmsm.img_url = instance.img_url
        pmsm.calculated_price = str(instance.calculated_price)
        pmsm.item_out_of_stock = instance.item_out_of_stock
        pmsm.savings = str(instance.savings)
        pmsm.promo_applied = instance.promo_applied
        pmsm.shipping_cost = str(instance.shipping_cost)
        pmsm.added_datetime = instance.added_datetime
        pmsm.imported_from_blog = instance.imported_from_blog
        pmsm.time_price_calculated_last = instance.time_price_calculated_last
        pmsm.time_notified_last = instance.time_notified_last
        pmsm.notify_lower_bound = str(instance.notify_lower_bound)
        pmsm.snooze = instance.snooze
        pmsm.bought = instance.bought
        pmsm.is_deleted = instance.is_deleted
        pmsm.show_on_feed = instance.show_on_feed
        pmsm.avail_sizes = instance.avail_sizes
        pmsm.img_url_shelf_view = instance.img_url_shelf_view
        pmsm.img_url_panel_view = instance.img_url_panel_view
        pmsm.img_url_feed_view = instance.img_url_feed_view
        pmsm.img_url_thumbnail_view = instance.img_url_thumbnail_view
        pmsm.img_url_original = instance.img_url_original
        pmsm.affiliate_prod_link = instance.affiliate_prod_link
        pmsm.original_instance_pointer = instance.get_original_instance()
        pmsm.current_product_prize = instance.current_product_price

        return pmsm

    @classmethod
    def all_to_show_on_feed(cls, to_show=None):
        '''
        get all ProductModelShelfMap instances that should be shown on the feed (these must have certain properties)
        Note: Right now we also want to trickle in imported items while the site isnt very active, we can remove this in
        the future
        @param to_show - the number of items to fetch for showing on the feed
        @return QuerySet of ProductModelShelfMap
        '''
        MINUTES_IN_DAY = 60 * 24
        to_show = to_show if to_show else ProductModelShelfMap.objects.count()

        now = datetime.now()
        yesterday = now - timedelta(days=1)
        imported_since_yesterday = cls.objects.filter(imported_from_blog=True, added_datetime__gte=yesterday,
                                                      show_on_feed=True, user_prof__is_trendsetter=True)
        # trickle is calculated by first calculating a rate of trickle flow (by dividing the minutes in a day by the number
        # of items to trickle), next we calculate the time since the start of the day (in minutes) and divide that value by
        # the trickle flow rate to get the number of items to trickle in
        mins_per_trickle = math.ceil(
            MINUTES_IN_DAY / imported_since_yesterday.count()) if imported_since_yesterday.exists() else MINUTES_IN_DAY

        since_day_start = now - datetime(now.year, now.month, now.day, hour=0, minute=0)
        mins_since_day_start = since_day_start.total_seconds() / 60
        trickle_index = int(mins_since_day_start / mins_per_trickle)
        trickle_ids = [t.id for t in imported_since_yesterday[:trickle_index]]

        without_trickle = cls.objects.filter(user_prof__is_trendsetter=True, item_out_of_stock=False,
                                             product_model__brand__supported=True, is_deleted=False,
                                             show_on_feed=True, img_url_feed_view__isnull=False).exclude(id__in=imported_since_yesterday)
        return (without_trickle | imported_since_yesterday.filter(id__in=trickle_ids))[:to_show]

    #####-----</ Classmethods >-----#####

    #####-----< Methods >-----#####
    def clone(self, user_prof, shelf):
        '''
        create a clone of this mapping
        @param user_prof - the UserProfile the cloned mapping will belong to
        @param shelf - the Shelf the cloned mapping will belong to
        @return the new ProductModelShelfMap instance created as a result of the clone
        '''
        duplicate = ProductModelShelfMap.create_copy_from_instance(self)
        duplicate.user_prof = user_prof
        duplicate.shelf = shelf
        duplicate.added_datetime = datetime.now()
        duplicate.save()

        return duplicate

    def clone_to_shelf_for_blog_imported_items(self, create_date):
        '''
        creates a clone for the item in "My Blogs of January" named shelves
        @param create_date - the date when the blog post was created
        '''
        month = create_date.strftime('%B')
        shelf_name = "My {month} Posts".format(month=month)
        shelf = Shelf.objects.get_or_create(user_id=self.user_prof.user if self.user_prof else None,
                                            name=shelf_name,
                                            imported_from_blog=True,
                                            user_created_cat=True)[0]
        return shelf.add_item_to_self(self.product_model, self.user_prof, self)

    def get_original_instance(self):
        """
        :return: :class:`debra.models.ProductModelShelfMap` instance which was the first in the ``original_instance_pointer`` chain
        """
        if self.original_instance_pointer is None:
            return self
        else:
            return self.original_instance_pointer.get_original_instance()
    #####-----</ Methods >-----#####

    #####-----< Django Overrides >-----#####
    def get_absolute_url(self):
        return reverse('debra.item_views.item_info', args=(self.id,))
    #####-----</ Django Overrides >-----#####


#####-----#####-----< UserProfile >-----#####-----#####


class UserProfile(FacebookProfileModel):
    # constants
    DEFAULT_PRIVILEGES = 0
    BLOGGER_PRIVILEGES = 1
    WIDGETS_PRIVILEGES = 2

    ACTION_IGNORE = 'ignore'
    ACTION_WIDGET_REACH_OUT = 'reach_out_about_widget'
    ACTION_COLLAGE_REACH_OUT = 'reach_out_about_collage'
    ACTION_SMALL_BETA = 'small_beta'
    ACTION_BIG_LATER = 'big_later'
    ACTION_VIP = 'vip'

    CONNECTOR_TYPES = (
        ('c', 'connector'),
        ('m', 'maven'),
        ('u', 'unknown'),
        ('d', 'not relevant'),
    )

    POPULARITY_CHOICES = (
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
        (5, 5),
        (6, 6),
        (7, 7),
        (8, 8),
        (9, 9),
        (10, 10),
    )

    ADMIN_ACTIONS = (
        (ACTION_IGNORE, 'ignore'),
        (ACTION_WIDGET_REACH_OUT, 'reach out about widget'),
        (ACTION_COLLAGE_REACH_OUT, 'reach out about collage'),
        (ACTION_SMALL_BETA, 'small - beta testing'),
        (ACTION_BIG_LATER, 'big - later'),
        (ACTION_VIP, 'VIP'),
    )

    QA_INFLUENCERS_TO_CHECK_NUMBER = 50

    ##--< relation fields >--##
    user = models.OneToOneField(User)
    # set if a user is a representative of a brand
    brand = models.OneToOneField(Brands, null=True, blank=True)
    influencer = models.ForeignKey('Influencer', blank=True, null=True, default=None)
    # if a user has indicated that they represent a brand and that brand exists in our system,
    # this field is set until they verify their email at which point we transfer accounts
    temp_brand_domain = models.CharField(max_length=300, blank=True, null=True, default=None)

    ##--< denormalized fields >--##
    num_shelves = models.IntegerField(default=0)
    num_items_in_shelves = models.IntegerField(default=0)
    num_following = models.IntegerField(default=0)
    num_followers = models.IntegerField(default=0)

    ##--< images for the collage >--##
    image1 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image2 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image3 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image4 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image5 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image6 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image7 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image8 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image9 = models.URLField(max_length=1000, blank=True, null=True, default=None)
    image10 = models.URLField(max_length=1000, blank=True, null=True, default=None)

    ##--< status flags >--##
    blog_verified = models.NullBooleanField(default=None)
    default_shelves_created = models.BooleanField(default=False)
    unclaimed = models.BooleanField(default=False)  # remove soon
    # should we show the autocategorized shelves (imported from blog posts)
    show_autocategorized = models.BooleanField(default=False)
    can_set_affiliate_links = models.BooleanField(default=False)

    ##--< style tags user associates with (comma separated string) >--##
    style_tags = models.CharField(max_length=5000, null=True, default="")

    ##--< bio's >--##
    aboutme = models.TextField(max_length=2000, blank=True, null=True, default=None)
    style_bio = models.TextField(max_length=2000, blank=True, null=True, default=None)
    age = models.IntegerField(blank=True, null=True, default=None)

    ##--< user meta info >--##
    is_female = models.BooleanField(default=True)
    location = models.TextField(blank=True, null=True, default=None)
    notification = models.BooleanField(default=True)
    name = models.CharField(max_length=100, blank=True, null=True, default=None)
    blog_name = models.CharField(max_length=100, blank=True, null=True, default=None)
    is_trendsetter = models.BooleanField(default=False, db_index=True)
    phone_number = PhoneNumberField(blank=True, null=True)

    ##--< admin info >--##
    popularity_rank = models.IntegerField(choices=POPULARITY_CHOICES, null=True, blank=True)
    connector_tag = models.CharField(max_length=10, choices=CONNECTOR_TYPES, null=True, blank=True)
    quality_tag = models.BooleanField(default=False)
    friendly_tag = models.BooleanField(default=True)
    privilege_level = models.IntegerField(default=0, null=True, blank=True)
    # has someone gone to the admin panel and categorized this user
    admin_categorized = models.BooleanField(default=False)
    admin_comments = models.TextField(blank=True, null=True, default=None)
    admin_action = models.CharField(max_length=50, choices=ADMIN_ACTIONS, null=True, blank=True)
    admin_classification_tags = models.CharField(max_length=200, null=True, blank=True)

    ##--< profile images >--##
    profile_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    cover_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    gravatar_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    # can be used for backups, or any other misc purpose
    temp_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)
    collage_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None)

    ##--< notification flags >--##
    account_management_notification = models.BooleanField(default=True)
    opportunity_notification = models.BooleanField(default=True)
    price_alerts_notification = models.BooleanField(default=True)
    deal_roundup_notification = models.BooleanField(default=True)
    social_interaction_notification = models.BooleanField(default=True)
    newsletter_enabled = models.BooleanField(default=True)

    ##--< users links >--##
    facebook_page = models.URLField(max_length=1000, blank=True, null=True, default=None)
    pinterest_page = models.URLField(max_length=1000, blank=True, null=True, default=None)
    bloglovin_page = models.URLField(max_length=1000, blank=True, null=True, default=None)
    twitter_page = models.URLField(max_length=1000, blank=True, null=True, default=None)
    instagram_page = models.URLField(max_length=1000, blank=True, null=True, default=None)
    blog_page = models.URLField(max_length=1000, blank=True, null=True, default=None)  # _web_page3
    etsy_page = models.URLField(max_length=1000, blank=True, null=True, default=None)  # _web_page2
    store_page = models.URLField(max_length=1000, blank=True, null=True, default=None)  # _web_page2
    youtube_page = models.URLField(max_length=1000, blank=True, null=True, default=None)  # _web_page2
    web_page = models.URLField(max_length=1000, blank=True, null=True, default=None)  # _web_page

    ##--< datetime fields >--##
    last_modified = models.DateTimeField(auto_now=True, blank=True)
    error_when_connecting_to_influencer = models.CharField(blank=True, null=True, max_length=32)

    ##--< Stripe Connect data >--##
    # stripe_access_token = models.CharField(null=True, max_length=1000)
    # stripe_refresh_token = models.CharField(null=True, max_length=1000)
    # stripe_publishable_key = models.CharField(null=True, max_length=1000)
    # stripe_user_id = models.CharField(null=True, max_length=1000)
    # stripe_connect_customer_id = models.CharField(null=True, max_length=1000)

    settings_json = models.TextField(null=True, blank=True, default=None)

    #####-----< Classmethods >-----#####
    @classmethod
    def get_trendsetters(cls):
        '''
        simple classmethod to get all UserProfiles that are trendsetters
        '''
        return cls.objects.filter(is_trendsetter=True, can_set_affiliate_links=True).select_related('user').all()

    @classmethod
    def get_plebians(cls):
        '''
        simple classmethod to get all UserProfiles that are NOT trendsetters
        '''
        return cls.objects.filter(is_trendsetter=False).select_related('user').all()

    @classmethod
    def user_created_callback(cls, user):
        '''
        this method is called when a new user is created
        @return newly created UserProfile instance
        '''
        new_prof = cls.objects.create(user=user)
        # new_prof.create_global_shelves()
        # new_prof.create_default_followers()
        return new_prof

    @classmethod
    def weighted_random_trendsetters(cls, num_to_get):
        '''
        this method fetches random trendsetters weighted by their popularity
        @param num_to_get - the number of trendsetters to fetch
        '''
        WEIGHTING_FACTOR = 1000
        trendsetters = cls.objects.filter(is_trendsetter=True).order_by('-num_followers')
        # FIXME
        total_num_followers = trendsetters.aggregate(Sum('num_followers'))['num_followers__sum']

        weighted_trendsetters = {}
        for trendsetter in trendsetters:
            weight = int((trendsetter.num_followers * WEIGHTING_FACTOR) /
                         total_num_followers) if trendsetter.num_followers > 0 else 1
            weighted_trendsetters[trendsetter] = weight

        result = []
        for i in range(0, num_to_get):
            choice = wr.choice(weighted_trendsetters)
            result.append(choice)
            weighted_trendsetters.pop(choice, None)

        return result
    #####-----</ Classmethods >-----#####

    @property
    def first_name(self):
        from debra.serializers import unescape
        return unescape(self.name.split(' ')[0] if self.name else '')

    @property
    def flag_default_invitation_campaign(self):
        return self.get_setting('default_invitation_campaign')

    @flag_default_invitation_campaign.setter
    def flag_default_invitation_campaign(self, value):
        self.set_setting(
            'default_invitation_campaign',
            int(value) if value is not None else None
        )

    @property
    def flag_can_edit_contracts(self):
        return self.get_setting('can_edit_contracts')

    @flag_can_edit_contracts.setter
    def flag_can_edit_contracts(self, value):
        return self.set_setting('can_edit_contracts', bool(value))

    @property
    def flag_messages_columns_visible(self):
        return self.get_setting('messages_columns_visible', [])

    @flag_messages_columns_visible.setter
    def flag_messages_columns_visible(self, value):
        return self.set_setting('messages_columns_visible', value)

    @property
    def flag_messages_paginate_by(self):
        return self.get_setting('messages_paginate_by', 20)

    @flag_messages_paginate_by.setter
    def flag_messages_paginate_by(self, value):
        return self.set_setting('messages_paginate_by', value)

    #####-----< Privilege Levels >-----#####
    @property
    def default_privileges(self):
        return self.privilege_level == self.DEFAULT_PRIVILEGES

    @property
    def blogger_privileges(self):
        return self.privilege_level >= self.BLOGGER_PRIVILEGES

    @property
    def widgets_privileges(self):
        return self.privilege_level >= self.WIDGETS_PRIVILEGES
    #####-----</ Privilege Levels >-----#####

    #####-----< User Statuses >-----#####
    @property
    def is_blogger(self):
        '''
        a method to check if this user is a blogger
        TODO: either rename _can_set_affiliate_links or add field is_blogger
        '''
        return self.can_set_affiliate_links

    @property
    def is_atul_test_account(self):
        return self.user.email == constants.ATUL_EMAILS.get('test_email')

    @property
    def has_liked_items(self):
        '''
        this method checks if the user has 'liked' any items
        @return True if user has liked items, False otherwise
        '''
        return self.liked_items.count() > 0

    @property
    def has_social_links(self):
        '''
        a method to check if this user has uploaded any social links
        @return True if any uploaded, false otherwise
        '''
        return self.facebook_page or self.pinterest_page or self.bloglovin_page or self.twitter_page or\
            self.instagram_page or self.blog_page or self.etsy_page or self.web_page

    @property
    def has_story(self):
        '''
        check if this user has uploaded any of their "story" information
        @return True if so, False o/w
        '''
        return self.name or self.blog_name or self.aboutme

    @property
    def has_style(self):
        '''
        check if this user has filled out any of their style information
        @return True if any style info filled out, False o/w
        '''
        return self.style_bio or self.style_tags

    @property
    def has_collage(self):
        '''
        check if this user has filled out all of their style collage
        @return True if style collage has all images, False otherwise
        '''
        return self.image1 and self.image2 and self.image3 and self.image4 and self.image5 and self.image6 and\
            self.image7 and self.image8 and self.image9 and self.image10

    @property
    def social(self):
        return search_helpers.get_social_data(influencer=self.influencer, profile=self)
    #####-----</ User Statuses >-----#####

    #####-----< Urls >-----#####
    @property
    def profile_url(self):
        '''
        a method to get the url of this users profile
        '''
        return reverse('debra.brand_views.brand_home', args=(self.id,)) if self.brand else reverse('debra.shelf_views.shelf_home', args=(self.id,))

    @property
    def about_url(self):
        '''
        a method to get the url for the about page for a user
        '''
        # return reverse('debra.brand_views.brand_about', args=(self.id,)) if
        # self.brand else reverse('debra.shelf_views.about_me', args=(self.id,))
        return reverse('debra.shelf_views.about_me', args=(self.id,))

    @property
    def followers_url(self):
        '''
        a method to get the url for this users' followers page
        '''
        return reverse('debra.shelf_views.followers', args=(self.id,))

    @property
    def after_login_url(self):
        """
        the url to go to after login (assuming 'next' isnt passed in the request)
        """
        brand = account_helpers.get_associated_brand(self)
        if brand:
            if brand.is_subscribed:
                return reverse('debra.search_views.blogger_search')
            else:
                if brand.flag_locked:
                    return reverse('debra.account_views.registration_complete_brand')
                else:
                    return reverse('debra.account_views.brand_next_steps')
        elif self.temp_brand_domain:
            return reverse('debra.account_views.registration_complete_brand')
        elif self.blog_page:
            # return reverse('debra.explore_views.inspiration', kwargs={'filter': 'blog'})
            if self.blog_verified:
                return reverse('debra.account_views.blogger_blog_ok')
            else:
                return reverse('debra.account_views.blogger_blog_not_ok')
        else:
            return reverse('debra.account_views.shopper_next_steps')
    #####-----</ Urls >-----#####

    @property
    def phone(self):
        if self.phone_number:
            return self.phone_number.as_e164

    #####-----< External Model Queries >-----#####
    def add_item_to_shelves(self, shelf_item, selected_shelves):
        '''
        a method to add a given item to the selected shelves
        '''
        product = shelf_item.product_model
        return product.add_to_shelves(selected_shelves, self, shelf_item)

    def shelfed_items(self, unique=False, has_image=False):
        '''
        a method to get all (non-deleted) items shelved by this user
        @param unique - if true, we will contstrain results to be unique on product model
        @param has_image - if true, restrict results to those results that have an img_url_thumbnail_view
        @return QuerySet of ProductModelShelfMap containing items shelved by this user
        '''
        if self.brand:
            result = ProductModelShelfMap.objects.filter(
                shelf__brand=self.brand, is_deleted=False) | ProductModelShelfMap.objects.filter(user_prof=self, is_deleted=False)
        else:
            result = ProductModelShelfMap.objects.filter(user_prof=self, is_deleted=False)

        result = result.exclude(img_url_thumbnail_view__isnull=True) if has_image else result
        result = ProductModelShelfMap.distinct_product_model(
            result) if unique else result.order_by('-id').select_related('product_model')
        return result

    @property
    def recently_shelved_items(self):
        '''
        return some of the more recently shelved wishlist items for this user.
        @return a list of recently shelved items
        '''
        NUM_ITEMS = 40
        return self.shelfed_items(unique=True, has_image=True)[:NUM_ITEMS]

    @property
    def user_created_shelves(self):
        '''
        get all non empty, user created shelves for this user
        '''
        return Shelf.objects.filter(user_created_cat=True, user_id=self.user, is_deleted=False, is_public=True)

    @property
    def user_category_shelves(self):
        '''
        get all category shelves for this user
        '''
        return Shelf.objects.filter(name__in=logical_categories_reverse_mapping.keys(), num_items__gt=0, user_id=self.user, user_created_cat=False, is_deleted=False)

    @property
    def auto_created_shelves(self):
        '''
        get all shelves we wish to display (user_created_cat=True) that are also
        '''
        return self.user_created_shelves.filter(imported_from_blog=True)
    #####-----</ External Model Queries >-----#####

    #####-----< Calculated Fields >-----#####
    @property
    def stripped_email(self):
        '''
        a method to strip everything after the @ sign of an email for this user off. Very similar to
        user_name_or_email method in custom_filters.py
        '''
        return re.sub(r'@\w+\.\w+', "", self.user.email)

    @property
    def best_name_for_search(self):
        '''
        this method gets the best display name for this user when searching for them. Order of preference is:
        1) name
        2) blog name
        3) stripped email
        '''
        result = self.name if self.name else self.blog_name
        return result if result else self.stripped_email

    @property
    def twitter_handle(self):
        '''
        this simple method converts the users twitter url to a handle (http://www.twitter.com/steiny/ become @steiny)
        '''
        url = self.twitter_page
        if url and not url.endswith('/'):
            url += '/'
        url_parts = url.split('/') if self.twitter_page else []
        url_parts.reverse()
        return "@{name}".format(name=url_parts[1]) if len(url_parts) > 1 else ""

    @property
    def likes_shelf(self):
        '''
        this method gets the My Likes Shelf for this user, or creates one if it doesnt exist
        '''
        shelf = Shelf.objects.get_or_create(name=constants.LIKED_SHELF, user_id=self.user)[0]
        return shelf

    @property
    def liked_items(self):
        '''
        this method gets all the items the user has Liked
        @return QuerySet of WishlistItemShelfMap representing the items this user has liked
        '''
        return ProductModelShelfMap.objects.filter(shelf__name=constants.LIKED_SHELF, user_prof=self)

    @property
    def classification_tags_list(self):
        '''
        this method returns this users admin_classification_tags as a list (split on the ,)
        '''
        return self.admin_classification_tags.split(',')
    #####-----/< Calculated Fields >-----#####

    @cached_property
    def associated_brand(self):
        if self.brand:
            return self.brand
        associated_privilages = (
            UserProfileBrandPrivilages.PRIVILAGE_OWNER,
            UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR,
            UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR_UNCONFIRMED,
        )
        privs = [
            p for p in self.brand_privilages.all()
            if p.permissions in associated_privilages]
        try:
            return privs[0].brand
        except IndexError:
            pass

    ######----< Follower / Following >----######
    @property
    def get_followers(self):
        '''
        a method to get all the followers of this user
        @return all users following this user
        '''
        return UserFollowMap.objects.select_related('user').filter(following=self).order_by("-user__num_followers")

    @property
    def get_following(self):
        '''
        a method to get all the users this user is following
        @return QuerySet of UserFollowMap containing all users this user is following
        '''
        return UserFollowMap.objects.select_related('following').filter(user=self).order_by("-following__num_followers")

    @property
    def followed_influencers(self):
        """
        get all influencers that this user is following
        @return QuerySet of Influencer that this user is following
        """
        # Note: this assumes that the only UserProfile's that would be followed by a brand are also Influencer's..could
        # be a faulty assumption in the future
        following = UserProfile.objects.filter(id__in=[mapping.following.id for mapping in self.get_following])
        return Influencer.objects.filter(shelf_user__userprofile__in=following)

    def following_list_builder(self, request_user):
        '''
        this convenience method builds a list of UserProfiles this user is following with follow info attached
        Note: is_followed for a user in this users list of following returns true if request user is following that user
        @param request_user - the User object in the request (logged in user)
        @return a list of dicts containing {is_followed:[bool], obj:[userprofile_instance]
        '''
        request_user_following = request_user.get_following
        return [{'is_followed': follow.following.id in [user.following.id for user in request_user_following],
                 'obj': follow.following} for follow in self.get_following]

    def followed_by_list_builder(self, request_user):
        '''
        this convenience method builds a list of UserProfiles following this user with relevant follow info attached
        Note: is_followed for a user in this users list of followers returns true if request user is followed by that user
        @param request_user - the User object in the request (logged in user)
        @return a list of dicts containing {is_followed:[bool], obj:[userprofile_instance]
        '''
        request_user_following = request_user.get_following
        return [{'is_followed': follower.user.id in [user.following.id for user in request_user_following],
                 'obj': follower.user} for follower in self.get_followers]

    def add_follower(self, follower):
        '''
        a method to add a follower to this user
        @return the new follow object
        '''
        return UserFollowMap.objects.get_or_create(user=follower, following=self)[0]

    def start_following(self, user):
        '''
        a method to have this user start following a user
        @return the new follow object
        '''
        return UserFollowMap.objects.create(user=self, following=user)

    def is_following(self, user):
        '''
        a method to check whether this user is following another user
        @return True if this user is following @user otherwise false
        '''
        return UserFollowMap.objects.filter(user=self, following=user).count() > 0

    def stop_following(self, user):
        '''
        a method to have this user stop following another user
        '''
        UserFollowMap.objects.filter(user=self, following=user).delete()

    def padding_function(self, base_num):
        '''
        the function to user for padding the num_follower and num_following counts
        '''
        MIN_NUM_FOLLOWS = 500
        if base_num > MIN_NUM_FOLLOWS:
            today = datetime.now()
            jan_1 = datetime(2014, 1, 1)
            padding_num = (today - jan_1).days * 2 + random.choice([1, 2, 3, 4, 5])
            return base_num + padding_num
        else:
            return base_num

    def padded_num_followers(self):
        '''
        a method to get the padded num of followers count for this user, we want to use padding to make the
        site seem busier, but only pad if the user has a sufficient amount of followers
        '''

        return self.padding_function(self.num_followers)

    def padded_num_following(self):
        '''
        same as padded_num_followers but for following count
        '''
        return self.padding_function(self.num_following)
    ######----</ Follower / Following >----######

    #####-----< Brand User >-----#####
    def create_brand_img(self):
        '''
        create this UserProfile's Brand's cover image if it doesnt exist from one of that brands products
        '''
        if self.cover_img_url is None:
            items = ProductModelShelfMap.objects.filter(product_model__brand=self.brand, img_url_original__isnull=False)
            it = items[0] if items.exists() else None
            self.cover_img_url = it.img_url_original if it else None

    def claim_brand(self):
        '''
        because initially, we created a shelf user in charge of managing every brands account, when a brand signs
        up for the site, we need to boot our stand-in userprofile and replace it with this userprofile
        '''
        pass

    def get_default_brand(self):
        brand = Brands.objects.filter(related_user_profiles__user_profile=self)
        if brand:
            return brand[0]
        else:
            return None
    #####-----</ Brand User >-----#####

    ######----< Lottery >----######
    @property
    def created_lotterys(self):
        '''
        get all the lotterys that were created by this user
        @return QuerySet of Lottery that this user has created
        '''
        return Lottery.objects.filter(creator=self)

    def completed_lottery_tasks(self, lottery):
        '''
        this method gets the tasks in a given lottery that the user has already completed
        @param lottery - the lottery to get the completed tasks for
        @return queryset containing LotteryTask objects that were completed by this user
        '''
        return LotteryTask.objects.filter(id__in=[mapping.task.id for mapping in LotteryEntryCompletedTask.objects.filter(task__lottery=lottery, entry__user=self).select_related('task')])

    def incomplete_lottery_tasks(self, lottery):
        '''
        inverse of completed lottery tasks..duh
        @param lottery - the lottery to get incomplete tasks for
        @return queryset of LotteryTask objects incomplete for this user
        '''
        return LotteryTask.objects.filter(lottery=lottery).exclude(id__in=[task.id for task in self.completed_lottery_tasks(lottery)])

    def completed_mandatory_tasks(self, lottery):
        '''
        this method checks whether the user has completed all mandatory tasks for the given lottery
        @param lottery - the lottery to check for
        @return true if mandatory tasks completed, false otherwise
        '''
        return self.completed_lottery_tasks(lottery).count() >= LotteryTask.objects.filter(lottery=lottery, mandatory=True).count()
    ######----</ Lottery >----######

    #####-----< Account Methods >-----#####
    def create_global_shelves(self):
        '''
        create shelves that every user should have
        '''
        Shelf.objects.get_or_create(user_id=self.user, name=constants.LIKED_SHELF)
        Shelf.objects.get_or_create(user_id=self.user, is_public=False, name=constants.DELETED_SHELF)

    def create_default_followers(self):
        '''
        when a user signs up we want them to be following some people by default. These
        people are 10 trendsetters chosen randomly, but having weights based on their popularity
        '''
        default_followers = UserProfile.weighted_random_trendsetters(10)
        for u in default_followers:
            u.add_follower(self)

    def unregister(self):
        '''
        remove notifications and newsletters for this user
        '''
        self.newsletter_enabled = False
        self.notification = False
        self.save()
    #####-----</ Account Methods >-----#####

    #####-----< Atuls Methods >-----#####
    @property
    def get_influencer(self):
        '''
        Finds influencer corresponding to this user if they have the same blog
        '''
        if not self.blog_page or self.blog_page == '':
            return None
        dups = Influencer.find_duplicates(self.blog_page)
        if len(dups) > 0:
            d = dups[0]
            inf = d.handle_duplicates()
            inf.shelf_user = self.user
            inf.email = self.user.email
            inf.save()
            self.influencer = inf
            self.save()
            return inf
        # we should create one now
        inf = Influencer.objects.create(email=self.user.email, blog_url=self.blog_page, shelf_user=self.user)
        self.influencer = inf
        self.save()
        return inf

    @property
    def get_all_posts(self):
        inf = self.get_influencer
        return inf.posts() if inf else Posts.objects.none()

    @property
    def get_all_platforms(self):
        inf = self.get_influencer if self.blog_page else None
        return Platform.objects.filter(influencer=inf) if inf is not None else Platform.objects.none()

    def has_posts(self, platform_name):
        '''
        return False if either no platform for this platform_name or no posts
        '''
        plat = self.get_all_platforms.filter(platform_name=platform_name)
        if not plat.exists():
            return False
        return Posts.objects.filter(platform=plat[0]).exists()

    def enable_data_crawling(self):
        '''
        First, set the influencer for this user
        and then create the platforms
        '''
        inf = self.get_influencer
        fb = utils.strip_url_of_default_info(self.facebook_page)
        pin = utils.strip_url_of_default_info(self.pinterest_page)
        tw = utils.strip_url_of_default_info(self.twitter_page)
        insta = utils.strip_url_of_default_info(self.instagram_page)
        if fb:
            fb_plat = inf.create_platform(self.facebook_page, "Facebook")
            print "Facebook", fb, self.facebook_page, fb_plat
            print "****"
        if pin:
            pin_plat = inf.create_platform(self.pinterest_page, "Pinterest")
            print "Pinterest", pin, self.pinterest_page, pin_plat
            print "****"
        if tw:
            tw_plat = inf.create_platform(self.twitter_page, "Twitter")
            print "Twitter", tw, self.twitter_page, tw_plat
            print "****"
        if insta:
            insta_plat = inf.create_platform(self.instagram_page, "Instagram")
            print "Instagram", insta, self.instagram_page, insta_plat
            print "****"
        if self.blog_page:
            try:
                from platformdatafetcher import fetcher
                platform_name, corrected_url = fetcher.try_detect_platform_name(self.blog_page)
                self.blog_page = corrected_url
                self.save()
                inf.create_platform(corrected_url, platform_name)
            except:
                print "exception in finding the blog platform name %s" % self.blog_page
                pass

    @property
    def display_post_stats_of_all_platforms(self):
        posts = self.get_all_posts
        plats = self.get_all_platforms
        for p in plats:
            pp = posts.filter(platform=p).order_by('-create_date')
            print "%s %s" % (p.url, pp.count())

    @property
    def is_fashion_blogger(self):
        if not self.admin_classification_tags:
            return False
        cur_tag = self.admin_classification_tags
        if 'Not' in cur_tag:
            return False
        return True

    #####-----</ Atuls Methods >-----#####

    #####-----< Denormalization >-----#####
    def denormalize(self):
        self.num_shelves = len(self.user_created_shelves)
        self.num_items_in_shelves = len(self.shelfed_items())
        self.save()
    #####-----</ Denormalization >-----#####

    def print_basic_stats(self):
        print "[Facebook: %s] [Pinterest: %s] [Bloglovin: %s] [Instagram: %s] [Blog URL: %s] [Blog Name: %s] [Profile Img: %s] [Cover Img: %s] [About: %s] " % (self.facebook_page,
                                                                                                                                                                self.pinterest_page, self.bloglovin_page, self.instagram_page, self.blog_page,
                                                                                                                                                                self.blog_name, self.profile_img_url, self.cover_img_url, self.aboutme)

    #####-----< Django Overrides >-----#####
    def __unicode__(self):
        return 'Name: %s / Id: %s' % (self.name, self.id)

    def get_absolute_url(self):
        if self.brand:
            return reverse('debra.brand_views.brand_home', args=(self.id,))
        else:
            return reverse('debra.shelf_views.shelf_home', args=(self.id,))
        #####-----</ Django Overrides >-----#####

        #####-----< Intercom >-----#####

    def update_intercom(self):
        intercom_user = self.get_from_intercom()
        if intercom_user:
            self.update_in_intercom(intercom_user)
        else:
            self.create_in_intercom()

    def update_in_intercom(self, intercom_user=None):
        '''
        try to update this shelf user in intercom.
        @param intercom_user - the intercom user representation of this Shelf User. If not provided, we will attempt to fetch it from intercom.
        @return error dict if error occurs, else None
        '''
        custom_data = constants.INTERCOM_CUSTOM_DATA(self)
        try:
            if not intercom_user:
                intercom_user = intercom.User.find(email=self.user.email)

            brand = account_helpers.get_associated_brand(self)
            if brand:
                company_data = brand.get_intercom_company_data()
                intercom_user.company = company_data
            intercom_user.custom_data = custom_data
            intercom_user.user_id = self.user.id
            intercom_user.email = self.user.email
            intercom_user.save()
            return None
        except Exception as e:
            return {'error': e.message, 'obj': intercom_user}

    def create_in_intercom(self):
        '''
        create this ``UserProfile`` in intercom
        '''
        brand = account_helpers.get_associated_brand(self)
        company_data = {}
        if brand:
            company_data = brand.get_intercom_company_data()
        intercom_user = intercom.User.create(
            email=self.user.email,
            user_id=self.user.id,
            name=self.name,
            created_at=self.user.date_joined.strftime("%c"),
            custom_data=constants.INTERCOM_CUSTOM_DATA(self),
            company=company_data
        )
        if self.get_setting('influenity_signup'):
            self.intercom_tag_add('dont-send-intro-email')
        return intercom_user

    def get_from_intercom(self):
        """
        :return: ``IntercomUser`` instance if user exists in intercom, else None

        get this user from intercom if they exist
        """
        try:
            intercom_user = intercom.User.find(user_id=self.user.id)
            return intercom_user
        except:
            return None

    def messages_from_intercom(self):
        '''
        get messages that have been sent to this user using intercom
        @return array of intercom message dicts, see https://api.intercom.io/docs#getting_messages for details of result structure
        '''
        return intercom.MessageThread.find_all(email=self.user.email)

    #####-----< New Intercom utils >-----#####
    def intercom_tag_add(self, tag_name):
        tag = intercom.Tag()
        tag.name = tag_name
        tag.user_ids = [str(self.user.id)]
        tag.tag_or_untag = "tag"
        tag.save()

    def intercom_tag_del(self, tag_name):
        tag = intercom.Tag()
        tag.name = tag_name
        tag.user_ids = [str(self.user.id)]
        tag.tag_or_untag = "untag"
        tag.save()
    #####-----</ Intercom >-----##
    ###

    # settings
    def set_setting(self, key, value):
        try:
            settings_json = json.loads(self.settings_json)
        except:
            settings_json = {}
        settings_json[key] = value
        self.settings_json = json.dumps(settings_json)

    def get_setting(self, key, default=None):
        try:
            settings_json = json.loads(self.settings_json)
        except:
            settings_json = {}
        return settings_json.get(key, default)

    @property
    def influencers_for_qa(self):
        infs = self.influencers_for_check.all()
        infs = infs.exclude(
            validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS
        )
        infs = infs.exclude(
            validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED
        )
        return infs

    def extend_influencers_for_qa(self, query=None):
        qa_group = Group.objects.get(name='QA')
        if self.user in qa_group.user_set.all():
            infs = self.influencers_for_qa
            missing_amount = UserProfile.QA_INFLUENCERS_TO_CHECK_NUMBER\
                - infs.count()
            if missing_amount > 0:
                if query is None:
                    qs = infs
                else:
                    query = query.filter(qa_user_profile__isnull=True)
                    qs = infs | query
                ids = qs.values_list('id',
                    flat=True)[:UserProfile.QA_INFLUENCERS_TO_CHECK_NUMBER]
                res = Influencer.objects.filter(id__in=ids)
            else:
                res = infs
            res.update(qa_user_profile=self)
        else:
            res = query
        return res.order_by('id')

    def get_qa_influencers_to_check(self, uuid=None):
        from debra.admin_helpers import influencers_informations_nonvalidated_query
        return self.extend_influencers_for_qa(
            influencers_informations_nonvalidated_query(uuid))


class UserProfileBrandPrivilages(models.Model):
    PRIVILAGE_UNKNOWN = 0
    PRIVILAGE_OWNER = 1
    PRIVILAGE_CONTRIBUTOR = 2
    PRIVILAGE_CONTRIBUTOR_UNCONFIRMED = 3
    PRIVILAGE_REJECTED = 4
    PRIVILAGE_AGENCY = 5
    PRIVILAGES = (
        (PRIVILAGE_UNKNOWN, 'Unknown'),
        (PRIVILAGE_OWNER, 'Owner'),
        (PRIVILAGE_CONTRIBUTOR, 'Contributor'),
        (PRIVILAGE_CONTRIBUTOR_UNCONFIRMED, 'Contributor (waiting for acceptance)'),
        (PRIVILAGE_REJECTED, 'Rejected'),
        (PRIVILAGE_AGENCY, 'Agency'),
    )

    user_profile = models.ForeignKey(UserProfile, related_name='brand_privilages')
    brand = models.ForeignKey(Brands, related_name="related_user_profiles")
    permissions = models.IntegerField(default=PRIVILAGE_UNKNOWN, choices=PRIVILAGES)

    def __unicode__(self):
        return u"%s privilage on %s" % (dict(UserProfileBrandPrivilages.PRIVILAGES)[self.permissions], self.brand.name)


###################################################
# User Follow Mapping (In App NOT CRAWLER!)
###################################################
class UserFollowMap(models.Model):

    '''
    each object in this model represents a user following another user
    '''
    user = models.ForeignKey(UserProfile, related_name="users")
    following = models.ForeignKey(UserProfile, related_name="follows")

    class Meta:
        unique_together = (("user", "following"),)

###################################################
# Tags for describing a users style
###################################################


class StyleTag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    @classmethod
    def default_style_tags(cls):
        '''
        these are tags that we use as placeholders (if the user hasn't yet added their own tags
        '''
        return ['hipster', 'trendy', 'colorful']


###################################################
###################################################


#####-----#####-----#####-----< Blog Related Tables >-----#####-----#####-----#####

#####-----#####-----#####-----< Blog Source Tables >-----#####-----#####-----#####

class BlogUrlsRaw(models.Model):

    '''
    This is used to store the raw crawled blog urls and meta data associated with them.
    Then later on, we do the sanitization.

    Source URL => domain where the url resides: fashiolista.com or bloglovin.com
    Name => name used at the source
    Description => this contains interested information (like location, age)
    url => url at the source
    blog_url => url of the blog
    site_url => sometimes it could be the tumblr url
    num_followers => number of followers on this source platform
    have_been_processed => if this entry has been de-duped and processed
    '''
    source = models.URLField(null=True, blank=True, default=None)
    name = models.CharField(max_length=100, blank=True, null=True, default=None)
    description = models.CharField(max_length=1000, blank=True, null=True, default=None)
    url = models.URLField(null=True, blank=True, default=None)
    blog_url = models.URLField(null=True, blank=True, default=None)
    site_url = models.URLField(null=True, blank=True, default=None)
    num_followers = models.IntegerField(null=True, blank=True, default=None)
    have_been_processed = models.BooleanField(default=False)

    def __unicode__(self):
        return u'id={self.id}, source={self.source}, name={self.name}, blog_url={self.blog_url}'.format(self=self)

#####-----#####-----#####-----< Influencer Table >-----#####-----#####-----#####


class DemographicsLocality(models.Model):
    country = models.CharField(max_length=128, blank=True, null=True, default=None)
    state = models.CharField(max_length=128, blank=True, null=True, default=None)
    city = models.CharField(max_length=128, blank=True, null=True, default=None)

    def __unicode__(self):
        return ', '.join(filter(None, [self.city, self.state, self.country]))


class InfluencerQuerySet(models.query.QuerySet):

    @classmethod
    def active_filter(cls):
        return dict(is_active=True)

    @classmethod
    def active_sql(cls, table_alias=None):
        if table_alias:
            return '{}.is_active = true'.format(table_alias)
        else:
            return 'is_active = true'

    @classmethod
    def inactive_filter(cls):
        return dict(is_active=False)

    @classmethod
    def active_unknown_filter(cls):
        return dict(is_active__isnull=True)

    def cachable(self):
        return self.filter(
            Q(show_on_search=True) &
            Q(source__isnull=False) &
            # Q(blog_url__isnull=False) &
            ~Q(blacklisted=True)
            # ~Q(blog_url__contains='theshelf.com/artificial')
        ) | self.has_tags('test_blogger')

    def active(self):
        return self.filter(**self.active_filter())

    def inactive(self):
        return self.filter(**self.inactive_filter())

    def not_active(self):
        return self.exclude(**self.active_filter())

    def active_unknown(self):
        return self.filter(**self.active_unknown_filter())

    def manually_approved(self):
        return self.filter(source__icontains='manual_')

    def discovered_via_twitter(self):
        return self.filter(source='discovered_via_twitter')

    def discovered_via_instagram(self):
        return self.filter(source='discovered_via_instagram')

    def discovered_via_twitter_contains(self):
        return self.filter(source__contains='discovered_via_twitter')

    def discovered_via_instagram_contains(self):
        return self.filter(source__contains='discovered_via_instagram')

    def discovered_via_twitter_contains_workaround(self):
        """
        Using UPPER(source) LIKE UPPER('%blah%') sometimes avoids a full scan on the posts table
        """
        return self.filter(source__icontains='discovered_via_twitter')

    def manual_or_from_twitter(self):
        return self.manually_approved() | self.discovered_via_twitter()

    def manual_or_from_social(self):
        return self.manually_approved() | self.discovered_via_twitter() | self.discovered_via_instagram()

    def manual_or_from_social_contains(self):
        return self.manually_approved() | self.discovered_via_twitter_contains() | self.discovered_via_instagram_contains() | self.filter(source__icontains='blogger_signup')

    def searchable(self):
        return self.filter(show_on_search=True).exclude(blacklisted=True).exclude(source__contains='brands')

    def valid(self):
        return self.filter(source__isnull=False, blog_url__isnull=False, blacklisted=False)

    def social_platforms_discovered_status(self):
        '''
        Filter influencers who have been run the operation to find platforms
        '''
        platforms = Platform.objects.filter(platform_name__in=Platform.BLOG_PLATFORMS, influencer__in=self)
        platforms_already_extracted = platforms.filter(platform_state=Platform.PLATFORM_STATE_FETCHING_SOCIAL_HANDLES)
        return self.exclude(platform__in=platforms_already_extracted), self.filter(platform__in=platforms_already_extracted)

        #### TODO: REMOVE BELOW AFTER TESTING
        plat_not_extracted = set()
        for a in self:
            b = a.blog_platform
            if b:
                o = list(PlatformDataOp.objects.filter(platform=b, operation='extract_platforms_from_platform').values_list('id', flat=True))
                if len(o) == 0:
                    plat_not_extracted.add(a.id)

        return self.filter(id__in=plat_not_extracted), self.exclude(id__in=plat_not_extracted)

    def distinct(self, *args, **kwargs):
        '''
        A hack that delists the JSON field from the column list when doing a DISTINCT.

        PG [justifiably] can't compare JSON values and raises an error.

        Note that we do nothing if we got an argument (DISTINCT ON (...) clause) since we
        assume the caller knows what s/he is doing.
        '''
        already_deferred = kwargs.pop('already_deferred', None)
        if not args and not already_deferred:
            return self.defer('autodetected_attributes', 'categories').distinct(*args, already_deferred=True, **kwargs)
        else:
            return super(InfluencerQuerySet, self).distinct(*args, **kwargs)

    def with_counters(self):
        return self.extra(select={
            'agr_brandmentions_count': '''
                SELECT COUNT(*) FROM debra_brandmentions AS bm WHERE bm.influencer_id=debra_influencer.id
            ''',
            'agr_blog_posts_count': '''
                SELECT -1
            ''',
            'agr_products_count': '''
                SELECT -1
            ''',
            # 'agr_blog_posts_count': '''
            #     SELECT COUNT(*)
            #         FROM debra_posts AS p
            #             JOIN debra_platform AS pl
            #                 ON p.platform_id=pl.id
            #         WHERE p.influencer_id=debra_influencer.id AND pl.platform_name IN ('Wordpress', 'Blogspot', 'Custom')
            # ''',
            # 'agr_products_count': '''
            #     SELECT COUNT(DISTINCT product_model_id)
            #         FROM debra_posts AS p
            #             JOIN debra_productmodelshelfmap AS ps
            #                 ON ps.post_id=p.id
            #         WHERE p.influencer_id=debra_influencer.id
            # ''',
            # 'agr_last_crawl_date': '''
            #     SELECT MAX(started)
            #         FROM debra_platformdataop AS pdo
            #             JOIN debra_platform as p
            #                 ON pdo.platform_id=p.id
            #         WHERE pdo.influencer_id=debra_influencer.id AND p.influencer_id=debra_influencer.id
            # ''',
        })

    def without_autodetected_attributes(self):
        return self.extra(where=["autodetected_attributes IS NULL OR autodetected_attributes::TEXT = 'null'"])

    def with_autodetected_attributes(self):
        return self.extra(where=["autodetected_attributes IS NOT NULL AND autodetected_attributes::TEXT <> 'null'"])

    def without_categories(self):
        return self.extra(where=["categories IS NULL OR categories::TEXT = 'null'"])

    def with_categories(self):
        return self.extra(where=["categories IS NOT NULL AND categories::TEXT <> 'null'"])

    def has_any_categories(self, category_list=None):
        '''
        Returns the query set that contains an OR of category_list
        '''
        if not category_list:
            category_list = ['fashion', 'beauty', 'kids', 'travel', 'food', 'fitness']
        qsets = None
        for category in category_list:
            qq = self.has_categories(category)
            if not qsets:
                qsets = qq
            else:
                qsets |= qq
        return qsets

    def has_categories(self, *categories):
        '''
        Constructs an array of category names and uses the PG @> 'contains' operator.

        Relies on the sh_influencer_categories DB function and an index on its values.
        '''
        if not categories:
            return self.none()

        from psycopg2.extensions import adapt
        quoted = [adapt(category).getquoted() for category in categories]
        # manually quote strings and pass to ARRAY constructor
        where_clause = 'sh_influencer_categories(categories) @> ARRAY[{}]'.format(', '.join(quoted))
        return self.extra(where=[where_clause])

    def categorized_posts_more_than(self, post_number_threshold):
        return self.extra(where=['sh_total_categorized_posts(categories) > %s'],
                          params=[post_number_threshold])

    def with_categorized_posts_totals(self):
        return self.extra(select={'total_categorized_posts': 'sh_total_categorized_posts(categories)'})

    def _blacklist_where_clause(self, reasons):
        from psycopg2.extensions import adapt
        quoted = [adapt(reason).getquoted() for reason in reasons]
        # manually quote strings and pass to ARRAY constructor
        return 'blacklist_reasons @> ARRAY[{}]'.format(', '.join(quoted))


    def is_blacklisted(self, *reasons):
        '''
        Constructs an array of reasons and uses the PG @> 'contains' operator.

        Relies on a GIN index on blacklist_reasons.
        '''
        if not reasons:
            return self.none()

        return self.extra(where=[self._blacklist_where_clause(reasons)])

    def exclude_if_blacklisted(self, *reasons):
        '''
        Constructs an array of reasons and uses the PG @> 'contains' operator.

        Relies on a GIN index on blacklist_reasons.
        '''
        if not reasons:
            return self.none()

        inverse = '(NOT ({}))'.format(self._blacklist_where_clause(reasons))
        return self.extra(where=[inverse])

    def _tag_where_clause(self, tags):
        from psycopg2.extensions import adapt
        quoted = [adapt(tag).getquoted() for tag in tags]
        # manually quote strings and pass to ARRAY constructor
        return 'tags @> ARRAY[{}]'.format(', '.join(quoted))

    def has_tags(self, *tags):
        if not tags:
            return self.none()

        return self.extra(where=[self._tag_where_clause(tags)])

    """
    We want to check how influencers are flowing through our system.
    a) Discovered
    b) posts crawled
    c) categorized
    d) platforms extracted
    e) QA worked
    f) ready for upgrade
    """
    def stage_just_discovered(self):
        return self.filter(activity_level__isnull=True)

    def stage_posts_crawled(self):
        q = self.filter(activity_level__isnull=False)
        c = q.categorized_posts_more_than(0)
        c_ids = c.values_list('id', flat=True)
        return q.exclude(id__in=c_ids)

    def stage_influencer_categorized(self):
        return self.has_any_categories()

    def stage_platforms_extracted(self):
        not_extracted, extracted = self.social_platforms_discovered_status()
        return extracted

    def stage_ready_for_qa(self):
        return self.filter(accuracy_validated=True).exclude(validated_on__contains='info')

    def stage_qaed(self):
        return self.filter(validated_on__contains='info')

    def remove_self_or_qa_modified(self):
        return self.exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)

    def get_quality_influencers_from_social_sources(self, min_followers_count=None, required_size=1000):
        """
        Here, we try to find quality influencers using follower count. If we have enough influencers with 50K followers
        we return them. Else, we expand our search by reducing the follower count requirement by `decrement`.

        The threshold required is specified in `required_size` paramater passed to this function.
        """
        start = min_followers_count if min_followers_count else 50000
        decrement = 2500

        infs_from_instagram_crawler = self.filter(instagram_profile__isnull=False)
        infs_from_twitter_crawler = self.filter(twitter_profile__isnull=False)
        infs_from_social = infs_from_instagram_crawler | infs_from_twitter_crawler

        while start > 0:
            instagram_crawler_filtered = infs_from_instagram_crawler.filter(instagram_profile__friends_count__gte=start)
            #twitter_crawler_filtered = infs_from_twitter_crawler.filter(twitter_profile__followers_count__gte=start)
            infs_from_social = instagram_crawler_filtered #twitter_crawler_filtered |
            infs_from_social = infs_from_social.distinct()

            # if we have enough urls to find platforms, just use these
            if infs_from_social.count() > required_size:
                return infs_from_social
            print("Failed, we got only %d influencers with at least %d followers" % (infs_from_social.count(), start))
            start -= decrement
            print("Now checking influencers with at least %d followers" % start)

        return infs_from_social.distinct()

    def get_larger_publications(self):
        """
        Here, we try to identify influencers that are essentially a larger publication. We do so by looking at the # of
        posts they had produced in the last month. If that exceeds > 90 (more than 3 per day), then we suspect that
        they are a larger publication.
        """
        blogs = Platform.objects.filter(influencer__in=self, platform_name__in=Platform.BLOG_PLATFORMS).exclude(url_not_found=True)
        larger_publication_ids = set()
        end = datetime.today()
        start = end - timedelta(days=30)
        for i, b in enumerate(blogs):
            posts = Posts.objects.filter(platform=b, create_date__gte=start).filter(create_date__lte=end)
            if posts.count() > 90:
                larger_publication_ids.add(b.influencer.id)
            print(i, len(larger_publication_ids))
        return self.filter(id__in=larger_publication_ids)

    def remove_problematic(self):
        """
        Just remove all influencers who have `problem` written
        """
        self = self.exclude(email_for_advertising_or_collaborations__icontains='problem')
        self = self.exclude(email_all_other__icontains='problem')
        self = self.exclude(blogname__icontains='PROBLEM') | self.exclude(name__icontains='PROBLEM')
        return self

    def infs_with_all_validated_platforms(self):
        """
        Return only those influencers that have all of the available platforms as autovalidated
        """
        all_valid = set()
        for i in self:
            # using a static list here becuase Tumblr is the problematic one
            plats = i.platforms().exclude(url_not_found=True).filter(platform_name__in=['Facebook', 'Pinterest', 'Twitter', 'Instagram', 'Youtube'])
            plats_auto = plats.filter(autovalidated=True)
            if plats.count() == plats_auto.count():
                all_valid.add(i.id)

        return self.filter(id__in=all_valid)

class InfluencerManager(models.Manager):

    def get_query_set(self):
        return InfluencerQuerySet(self.model, using=self.db)

    get_queryset = get_query_set

    def active(self):
        return self.all().active()

    def inactive(self):
        return self.all().inactive()

    def not_active(self):
        return self.all().not_active()

    def active_unknown(self):
        return self.all().active_unknown()

    def cachable(self):
        return self.all().cachable()

    def get_profile_pics(self, inf_ids):
        pics = redis_cache.get_many(['pp_{}'.format(inf_id)
            for inf_id in inf_ids])
        return {
            int(k.strip('pp_')): v
            for k, v in pics.items() if v and v != 'None'
        }

    def missing_emails_data(self):
        '''
        returns 'influencer_id' => 'last sent message data' mapping for all
        influencers with missing 'email_for_advertising_or_collaborations' value
        '''
        from aggregate_if import Max, Count
        _t0 = time.time()
        excluded_ids = list(MailProxy.objects.filter(
            Q(influencer__email_for_advertising_or_collaborations__isnull=True) |
            Q(influencer__email_for_advertising_or_collaborations='')
        ).annotate(
            agr_resp_count=Count(
                'threads', only=(
                    Q(threads__direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND) &
                    Q(threads__type=MailProxyMessage.TYPE_EMAIL)
                )
            ),
        ).exclude(agr_resp_count=0).values_list('influencer', flat=True))
        print '* excluded_ids took {}'.format(time.time() - _t0)
        print len(excluded_ids)

        _t0 = time.time()
        mp_data = dict(MailProxy.objects.filter(
            Q(influencer__email_for_advertising_or_collaborations__isnull=True) |
            Q(influencer__email_for_advertising_or_collaborations='')
        ).exclude(
            influencer_id__in=excluded_ids
        ).exclude(
            influencer__isnull=True
        ).annotate(
            agr_sent_count=Count(
                'threads', only=(
                    Q(threads__direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER) &
                    Q(threads__type=MailProxyMessage.TYPE_EMAIL)
                )
            ),
            agr_last_sent=Max(
                'threads__ts', only=(
                    Q(threads__type=MailProxyMessage.TYPE_EMAIL) &
                    Q(threads__direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER)
                )
            ),
        ).exclude(agr_sent_count=0).values_list(
            'influencer', 'agr_last_sent',
        ))
        print '* mp_data took {}'.format(time.time() - _t0)
        return mp_data


class InfluencerRelatedQuerySet(models.query.QuerySet):

    def influencer_active(self):
        influencer_filter = InfluencerQuerySet.active_filter()
        platform_filter = {'influencer__' + k: v for k, v in influencer_filter.items()}
        return self.filter(**platform_filter)


class InfluencerRelatedManager(models.Manager):

    def influencer_active(self):
        return self.all().influencer_active()


class ActivityLevel(object):

    '''
    Platform and influencer activity level indication.

    We use this to determine how often we fetch platforms and whether influencers
    have been recently active in our system.

    We fetch blogs active more often than a blog a month every day, the rest get fetched
    less often. In addition we assume a NULL activity level means a new platform that
    needs to be fetched right away, so that we determine its level. Those platforms get scheduled
    every day too.
    '''
    ACTIVE_UNKNOWN = 'ACTIVE_UNKNOWN'
    ACTIVE_NEW = 'ACTIVE_NEW'
    ACTIVE_LAST_DAY = 'ACTIVE_LAST_DAY'
    ACTIVE_LAST_WEEK = 'ACTIVE_LAST_WEEK'
    ACTIVE_LAST_MONTH = 'ACTIVE_LAST_MONTH'
    ACTIVE_LAST_3_MONTHS = 'ACTIVE_LAST_3_MONTHS'
    ACTIVE_LAST_6_MONTHS = 'ACTIVE_LAST_6_MONTHS'
    ACTIVE_LAST_12_MONTHS = 'ACTIVE_LAST_12_MONTHS'
    ACTIVE_LONG_TIME_AGO = 'ACTIVE_LONG_TIME_AGO'

    _ENUM = {
        ACTIVE_NEW: 0,
        ACTIVE_LAST_DAY: 10,
        ACTIVE_LAST_WEEK: 100,
        ACTIVE_LAST_MONTH: 1000,
        ACTIVE_LAST_3_MONTHS: 3000,
        ACTIVE_LAST_6_MONTHS: 6000,
        ACTIVE_LAST_12_MONTHS: 12000,
        ACTIVE_LONG_TIME_AGO: 24000,
        ACTIVE_UNKNOWN: -1
    }

    _ACTIVITY_LEVELS = [
        (ACTIVE_NEW, 'New'),
        (ACTIVE_LAST_DAY, 'Active last day'),
        (ACTIVE_LAST_WEEK, 'Active last week'),
        (ACTIVE_LAST_MONTH, 'Active last month'),
        (ACTIVE_LAST_3_MONTHS, 'Active three months ago'),
        (ACTIVE_LAST_6_MONTHS, 'Active six months ago'),
        (ACTIVE_LAST_12_MONTHS, 'Active a year ago'),
        (ACTIVE_LONG_TIME_AGO, 'Active a long time ago'),
    ]

    _ACTIVITY_LEVEL_PRIORITIES = {
        ACTIVE_NEW: 0,
        ACTIVE_LAST_DAY: 1,
        ACTIVE_LAST_WEEK: 2,
        ACTIVE_LAST_MONTH: 3,
        ACTIVE_LAST_3_MONTHS: 4,
        ACTIVE_LAST_6_MONTHS: 5,
        ACTIVE_LAST_12_MONTHS: 6,
        ACTIVE_LONG_TIME_AGO: 7,
        ACTIVE_UNKNOWN: 100,
    }

    @classmethod
    def most_often(cls, activity_levels):
        if not activity_levels:
            raise ValueError('activity_levels must contain values.')

        sorted_levels = sorted(activity_levels,
                               key=lambda level: cls._ACTIVITY_LEVEL_PRIORITIES.get(level, 1000))
        return sorted_levels[0]


class InfluencerActivityLevelMixin(object):

    def calculate_activity_level(self):
        platform_levels = self.get_platform_activity_levels()
        if not platform_levels:
            self.activity_level = None
        else:
            self.activity_level = ActivityLevel.most_often(platform_levels)


from debra.elastic_search_helpers import influencer_set_blacklisted

class Influencer(TaggingMixin, PostSaveTrackableMixin, models.Model, InfluencerActivityLevelMixin):
    SOURCE_TYPES = (
        ('spreadsheet_import', 'spreadsheet_import'),
    )

    PROBLEMS = (
        (1, "unknown"),
        (2, "squatter"),
        (3, "brand"),
        (4, "social"),
        (5, "bad_email"),
    )

    GENDERS = (
        ('m', 'Male'),
        ('f', 'Female'),
        ('mf', 'Male and Female')
    )

    platform_name_to_field = {'Facebook': 'fb_url', 'Pinterest': 'pin_url', 'Twitter': 'tw_url', 'Instagram': 'insta_url',
                              'Bloglovin': 'bloglovin_url', 'Youtube': 'youtube_url', 'Pose': 'pose_url',
                              'Lookbook': 'lb_url', 'Gplus': 'gplus_url'}

    field_to_platform_name = {'fb_url': 'Facebook', 'pin_url': 'Pinterest', 'tw_url': 'Twitter', 'insta_url': 'Instagram',
                              'bloglovin_url': 'Bloglovin', 'youtube_url': 'Youtube', 'pose_url': 'Pose',
                              'lb_url': 'Lookbook', 'gplus_url': 'Gplus'}

    SOCIAL_PLATFORM_FIELDS = ['fb_url', 'pin_url', 'tw_url', 'insta_url', 'bloglovin_url',
        'youtube_url', 'pose_url', 'lb_url', 'gplus_url',]

    _POST_SAVE_TRACKABLE_FIELDS = [
        'fb_url', 'pin_url', 'tw_url', 'bloglovin_url', 'youtube_url',
        'pose_url', 'lb_url', 'gplus_url', 'insta_url']

    name = models.CharField(max_length=1000, blank=True, null=True, default=None, db_index=True)
    # space separated list of emails
    email = models.CharField('Email', null=True, blank=True, default=None, max_length=1000)
    email_for_advertising_or_collaborations = models.CharField(
        'email_for_advertising_or_collaborations', null=True, blank=True, default=None, max_length=1000)
    email_all_other = models.CharField('email_all_other', null=True, blank=True, default=None, max_length=1000)
    contact_form_if_no_email = models.CharField(
        'contact_form_if_no_email', null=True, blank=True, default=None, max_length=1000)

    shelf_user = models.ForeignKey(User, null=True, blank=True, default=None, db_index=True)
    profile_pic_url = models.URLField(max_length=1000, null=True, blank=True, default=None)

    demographics_locality = models.ForeignKey(DemographicsLocality, related_name='influencers', blank=True, null=True)
    demographics_location = models.CharField(max_length=1000, blank=True, null=True, default=None)
    demographics_location_normalized = models.CharField(max_length=1000, blank=True, null=True, default=None)
    demographics_location_lat = models.FloatField(blank=True, null=True, default=None)
    demographics_location_lon = models.FloatField(blank=True, null=True, default=None)
    demographics_bloggerage = models.IntegerField(null=True, blank=True, default=None)
    demographics_gender = models.CharField(max_length=10, null=True, blank=True, default=None, choices=GENDERS)

    blog_url = models.URLField(max_length=1000, null=True, blank=True, default=None, db_index=True)
    fb_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    pin_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    tw_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    insta_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    bloglovin_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    bloglovin_followers = models.IntegerField(null=True, blank=True, default=None)
    youtube_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    pose_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    lb_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    gplus_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    snapchat_username = models.CharField(max_length=1000, null=True, blank=True, default=None)

    ##--< Denormalized Fields >--##
    score_engagement_overall = models.FloatField(null=True, blank=True, default=None)
    score_popularity_overall = models.FloatField(null=True, blank=True, default=None)
    average_num_giveaways = models.IntegerField(default=0)
    average_num_posts = models.FloatField(null=True, blank=True, default=0.0, db_index=True)
    average_num_comments_per_giveaway = models.FloatField(null=True, blank=True, default=0.0)
    average_num_comments_per_post = models.FloatField(null=True, blank=True, default=0.0)
    average_num_comments_per_sponsored_post = models.FloatField(null=True, blank=True, default=0.0)
    posts_count = models.IntegerField(default=0, null=True, blank=True)

    ##--< Admin Fields >--##
    relevant_to_fashion = models.NullBooleanField(default=None, db_index=True)
    remove_tag = models.BooleanField(default=False)
    accuracy_validated = models.BooleanField(default=False)
    # if this influencer passes all tests to be shown on the search results
    show_on_search = models.NullBooleanField(default=None, db_index=True)
    # TODO: get rid of this one after pushing the activity_level changes to production
    old_show_on_search = models.NullBooleanField(default=None, db_index=True)
    # if the blog url is a valid url and doens't go to 500 or 404
    is_live = models.NullBooleanField(default=None, db_index=True)
    # if the blogger has been actively blogging
    is_active = models.NullBooleanField(default=None, db_index=True)
    activity_level = models.CharField(max_length=1000, blank=True, null=True,
                                      default=None, choices=ActivityLevel._ACTIVITY_LEVELS, db_index=True)

    # where did the influencer come from ('laurens list', 'scraped' etc)
    source = models.CharField(max_length=100, blank=True, null=True, default=None, db_index=True)

    fb_crawler_problem = models.BooleanField(default=False)
    fb_couldnt_find = models.BooleanField(default=False)
    fb_blogger_mistake = models.BooleanField(default=False)
    tw_crawler_problem = models.BooleanField(default=False)
    tw_couldnt_find = models.BooleanField(default=False)
    tw_blogger_mistake = models.BooleanField(default=False)
    in_crawler_problem = models.BooleanField(default=False)
    in_couldnt_find = models.BooleanField(default=False)
    in_blogger_mistake = models.BooleanField(default=False)
    pn_crawler_problem = models.BooleanField(default=False)
    pn_couldnt_find = models.BooleanField(default=False)
    pn_blogger_mistake = models.BooleanField(default=False)

    date_created = models.DateTimeField(null=True, blank=True)
    date_edited = models.DateTimeField(null=True, blank=True)
    date_validated = models.DateTimeField(null=True, blank=True)
    validated_on = models.CharField(null=True, blank=True, max_length=100)

    blacklisted = models.BooleanField(default=False)
    blacklist_reasons = TextArrayField(null=True, blank=True)
    problem = models.IntegerField(default=0, choices=PROBLEMS)

    # tags = TextArrayField(null=True, blank=True)

    blogname = models.CharField(max_length=1000, blank=True, null=True, default=None)
    about_url = models.TextField(null=True, blank=True, default=None)
    description = models.TextField(null=True, blank=True, default=None)
    blogger_type = models.CharField(max_length=1000, blank=True, null=True, default=None)

    classification = models.CharField(max_length=100, null=True, blank=True)

    last_modified = models.DateTimeField(auto_now=True, null=True, blank=True)
    qa = models.CharField(null=True, blank=True, max_length=512)

    qa_user_profile = models.ForeignKey(
        UserProfile, related_name='influencers_for_check',
        blank=True, null=True, default=None, db_index=True)

    date_upgraded_to_show_on_search = models.DateTimeField(null=True, blank=True)

    collaboration_types = models.TextField(blank=True, null=True, default=None)
    how_you_work = models.TextField(blank=True, null=True, default=None)
    ready_to_invite = models.NullBooleanField()

    latest_in_influencer_score = models.DateTimeField(null=True, blank=True)

    copyrightable_content = models.NullBooleanField()

    # json-encoded list of fields that are verified by an algorithm
    autoverified_fields = models.CharField(max_length=1000, null=True, blank=True)

    # details on attributes autodetected from platforms
    autodetected_attributes = PGJsonField(null=True, blank=True)

    # category details: name -> post_count
    categories = PGJsonField(null=True, blank=True)

    price_range_tag_normalized = models.CharField(max_length=10, null=True, blank=True, default=None)

    # estimated stats: age distribution of viewership
    dist_age_0_19 = models.FloatField(null=True, blank=True)
    dist_age_20_24 = models.FloatField(null=True, blank=True)
    dist_age_25_29 = models.FloatField(null=True, blank=True)
    dist_age_30_34 = models.FloatField(null=True, blank=True)
    dist_age_35_39 = models.FloatField(null=True, blank=True)
    dist_age_40 = models.FloatField(null=True, blank=True)

    # estimated stats: gender distribution of viewership
    dist_gender_female = models.FloatField(null=True, blank=True)
    dist_gender_male = models.FloatField(null=True, blank=True)

    objects = InfluencerManager()

    #####-----< Classmethods >-----#####
    ##--< Aggregates >--##
    @classmethod
    def total_num_followers(cls):
        influencers = cls.raw_influencers_for_search()
        # FIXME
        return Platform.objects.filter(influencer__in=influencers).exclude(url_not_found=True).aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']

    @classmethod
    def total_platform_engagement(cls):
        influencers = cls.raw_influencers_for_search()
        return Platform.objects.filter(influencer__in=influencers).exclude(url_not_found=True).aggregate(engagement_overall=Sum('score_engagement_overall'))['engagement_overall']
    ##--</ Aggregates >--##

    @classmethod
    def group_by_location(cls, num_results=20, qs=None):
        """
        get the highest locations / number of influencers for that location
        @param num_results - the number of results to fetch
        @param qs - if given, we will perform the grouping over the given qs, not over all objects of the class
        @return QuerySet containing fields demographics_location and num_in_loc
        """
        target = qs if qs else cls.objects
        return target.values('demographics_location').annotate(num_in_loc=Count('demographics_location')).order_by('-num_in_loc')[:num_results]

    @classmethod
    def get_locations_list(cls, num_results=10, qs=None, overwrite=False, use_full_names=True):
        """
        added for processing demographics_location_normalized for filtering
        get the highest locations / number of influencers for that location
        @param num_results - the number of results to fetch
        @param qs - if given, we will perform the grouping over the given qs, not over all objects of the class
        @param overwrite - forcefully owerwrites cached value
        @return QuerySet containing fields demographics_location and num_in_loc
        """

        cached = None
        if qs is None and num_results is not None:
            cached = cache.get('locations_list_%s' % num_results)

        if overwrite or cached is None:
            target = qs if qs else Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True)

            # locs = target.extra(select={'title': 'demographics_location_normalized'}).values(
            #     'title').annotate(count=Count('demographics_location_normalized')).order_by('-count')
            target = target.select_related('demographics_locality')

            if use_full_names:

                countries = target.values(
                    'demographics_locality__country'
                ).exclude(
                    demographics_locality__country__isnull=True
                ).annotate(
                    count=Count('demographics_locality')
                ).order_by('-count')[:num_results]

                states = target.values(
                    'demographics_locality__country',
                    'demographics_locality__state',
                ).exclude(
                    demographics_locality__country__isnull=True
                ).exclude(
                    demographics_locality__state__isnull=True
                ).annotate(
                    count=Count('demographics_locality')
                ).order_by('-count')[:num_results]

                cities = target.values(
                    'demographics_locality__country',
                    'demographics_locality__state',
                    'demographics_locality__city',
                ).exclude(
                    demographics_locality__city__isnull=True
                ).annotate(
                    count=Count('demographics_locality')
                ).order_by('-count')[:num_results]

                locs = sorted(itertools.chain(countries, states, cities),
                    key=lambda x: -x['count'])

                locations_mixed = []
                ordering = [
                    'demographics_locality__city',
                    'demographics_locality__state',
                    'demographics_locality__country',
                ]
                for loc in locs:
                    keys = [k for k in ordering if loc.get(k)]
                    if not keys:
                        continue
                    locations_mixed.append({
                        'title': ', '.join([loc.get(k) for k in keys]),
                        'count': loc['count'],
                        'type': [k for k in keys][0].split('__')[1],
                    })
            else:
                countries = target.values('demographics_locality__country').annotate(count=Count('demographics_locality__country')).order_by('-count')[:num_results]
                states = target.values('demographics_locality__state').annotate(count=Count('demographics_locality__state')).order_by('-count')[:num_results]
                cities = target.values('demographics_locality__city').annotate(count=Count('demographics_locality__city')).order_by('-count')[:num_results]

                locations_mixed = sorted(list(countries) + list(states) + list(cities), key=lambda x: -x["count"])

                for loc in locations_mixed:
                    for k in [k for k in loc.keys() if k != 'count' ]:
                        loc['title'] = loc[k]
                        loc['type'] = k.split('__')[1]
                        del loc[k]

            results = locations_mixed[:num_results]

            if qs is None:
                cache.set('locations_list_%s' % num_results, results, 60*60*24)

            return results
        else:
            return cached

        # location_aggregated = {}
        # for loc in locs:
        #     if not loc["title"]:
        #         continue
        #     name_split = [x.strip() for x in loc["title"].split(',')]
        #     for sub_loc in name_split:
        #         if sub_loc not in location_aggregated:
        #             location_aggregated[sub_loc] = 0
        #         location_aggregated[sub_loc] += loc["count"]
        # out_locs = []
        # for k, v in location_aggregated.iteritems():
        #     out_locs.append({
        #         "title": k,
        #         "count": v
        #     })
        # out_locs.sort(key=lambda x: -x["count"])
        # return out_locs[:num_results]

    @classmethod
    def filters(cls):
        """
        get all the possible filters for an influencer (as defined in the html file(s) which render Influencer
        objects
        @return dict containing filter mappings
        """
        return {
            'brand_name': lambda tup, brands: [t for t in tup if t[0] in BrandMentions.all_influencers_mentioning_brands(brands)],
            'popularity': lambda tup, pop_range: [t for t in tup if
                                                  float(pop_range[0]) <= t[0].score_popularity_overall <= float(pop_range[1])],
            'engagement': lambda tup, eng_range: [t for t in tup if
                                                  float(eng_range[0]) <= t[0].score_engagement_overall <= float(eng_range[1])],
            'location': lambda tup, locs: [t for t in tup if t[0].demographics_location in locs],
        }

    @classmethod
    def _search_prefetch(cls, qs):
        return qs.distinct().\
            prefetch_related('platform_set').\
            prefetch_related('brandmentions_set').\
            prefetch_related('brandmentions_set__brand')

    @classmethod
    def raw_influencers_for_search(cls):
        """
        this method gets all influencers that have a facebook profile img and a location (and should be shown on search)
        @return QuerySet of Influencer that have facebook pics and a location and should be shown on search
        """
        return cls._search_prefetch(Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True))

    @classmethod
    def trendsetter_influencers(cls):
        """
        get those influencers that are trendsetters
        @return QuerySet of Influencer that are trendsetters
        """
        return cls.objects.filter(userprofile__is_trendsetter=True)

    #####-----</ Classmethods >-----#####

    def get_popularity_stats(self, **kw):
        from debra.search_helpers import get_popularity_stats
        return get_popularity_stats(self, **kw)

    def get_monthly_visits(self):
        try:
            data = [{'date': visit.frontend_date(), 'count': visit.count} for\
                    visit in SimilarWebVisits.objects.monthly(self.id)]
        except:
            print '** exception in get_monthly_visits'
            data = []
        return data

    def get_monthly_visits_compete(self, compete_key):
        from debra import compete
        api = compete.Api()
        try:
            data = api[self.blog_url].visits(api_key=compete_key)['data']
        except:
            data = []
        return data

    def get_traffic_shares(self):
        try:
            data = [{'type': dict(SW_SOURCE_TYPE_CHOICES).get(item.source_type),
                'value': item.value} for item in\
                    SimilarWebTrafficShares.objects.latest(self)]
        except Exception, e:
            data = []
        return data

    def get_top_country_shares(self):
        from debra.similar_web import Api
        api = Api()
        try:
            data = api[self.blog_url].top_country_shares()['data']
        except Exception, e:
            data = []
        return data

    def active(self):
        return self.is_active is True

    def inactive(self):
        return self.is_active is False

    def active_unknown(self):
        return self.is_active is None

    def append_source(self, new_source):
        """This method appends a new source to the existing list of sources
        """
        if not new_source:
            return
        if self.source:
            if not new_source.lower() in self.source.lower():
                self.source = self.source + ':' + new_source.lower()
        else:
            self.source = new_source.lower()
        if len(self.source) >= 100:
            self.source = self.source[:99]

    def append_url(self, field, url):
        """This should be used with fb_url, tw_url etc. fields to append a new url using a call like:
        ``inf.append_url('tw_url', 'https://twitter.com/user')``
        """
        val = getattr(self, field)
        if val is None or not val.strip():
            setattr(self, field, url)
            return
        val = val + ' ' + url
        setattr(self, field, val)

    def append_comment(self, comment_text, user=None, brand=None):
        new_comment = InfluencerCustomerComment(
            comment=comment_text, influencer=self)
        if brand is not None:
            new_comment.brand = brand
        if user is not None:
            new_comment.user = user
        new_comment.save()

    def contains_url(self, field, url, normalize=True):
        val = getattr(self, field) or ''
        urls = val.split()
        if normalize:
            urls = [utils.strip_url_of_default_info(u, False) for u in urls]
            url = utils.strip_url_of_default_info(url, False)
        return url in urls

    def clear_url_fields(self):
        for field in self.platform_name_to_field.values():
            setattr(self, field, None)

    def update_url_references(self, old_url, new_url):
        if not old_url or not new_url:
            return
        if not old_url.startswith('http') or not new_url.startswith('http'):
            return
        for field in self.platform_name_to_field.values():
            url_string = getattr(self, field, None)
            if not url_string:
                continue
            if old_url not in url_string:
                continue
            new_string = url_string.replace(old_url, new_url)
            setattr(self, field, new_string)
            self.save()

    def remove_from_validated_on(self, val):
        if not self.validated_on:
            return
        val_on = json.loads(self.validated_on)
        if val not in val_on:
            return
        val_on.remove(val)
        self.validated_on = json.dumps(val_on)

    def normalize_single_email(self, email):
        return email.replace(' ', '_').lower()

    def get_emails(self):
        if not self.email_all_other:
            return []
        return [self.normalize_single_email(email) for email in self.email_all_other.split()]

    def append_email_if_not_present(self, email):
        if self.normalize_single_email(email) in self.get_emails():
            return False
        if not self.email_all_other:
            self.email_all_other = self.normalize_single_email(email)
        else:
            self.email_all_other = self.email_all_other + ' ' + self.normalize_single_email(email)
        return True

    def is_qad(self):
        try:
            validated_on = json.loads(self.validated_on)
        except (ValueError, TypeError):
            validated_on = []
        return constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS in validated_on

    def is_enabled_for_automated_edits(self):
        try:
            validated_on = json.loads(self.validated_on)
        except (ValueError, TypeError):
            validated_on = []
        if constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS in validated_on:
            return False
        if constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED in validated_on:
            return False
        return True

    def get_platform_by_name(self, name):
        pls = [x for x in self.all_platforms.get()
            if x['platform_name'] == name]
        # pls = [x for x in self.platform_set.all() if x.platform_name == name]
        try:
            return pls[0]
        except IndexError:
            return None

    @property
    def first_name(self):
        from debra.serializers import unescape
        return unescape(self.name.split(' ')[0] if self.name else '')

    @property
    def last_name(self):
        from debra.serializers import unescape
        return unescape(' '.join(self.name.split(' ')[1:]) if self.name else '')

    @property
    def emails(self):
        if self.email_for_advertising_or_collaborations:
            emails = self.email_for_advertising_or_collaborations.split()
        elif self.email_all_other:
            emails = self.email_all_other.split()
        elif self.shelf_user:
            emails = [self.shelf_user.email]
        else:
            emails = ['suhanovpavel@gmail.com']
        return emails

    @property
    def is_correctly_qaed(self):
        return True

    @is_correctly_qaed.setter
    def is_correctly_qaed(self, value):
        value = bool(int(value))
        if not value:
            self.date_validated = None
            self.remove_from_validated_on(
                constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            self.save()

    @property
    def customer_comments(self):
        # comments = self.influencer_customer_comments.order_by('timestamp').all()

        comments = sorted(
            self.influencer_customer_comments.all(),
            key=lambda x: x['timestamp'])


        res = []
        for comment in comments:
            res.append({
                'text': comment.comment,
                'author_email': comment.user.email,
                'timestamp': comment.timestamp
            })

        return res

    @customer_comments.setter
    def customer_comments(self, value):
        # {user_id: <number>, brand_id: <number>, text: <string>}
        if type(value) == str:
            value = json.loads(value)
        user = User.objects.get(id=value.get('user_id'))
        brand = None
        if value.get('brand_id') is not None:
            brand = Brands.objects.get(id=value.get('brand_id'))
        self.append_comment(
            value.get('text'),
            user=user,
            brand=brand
        )

    @property
    def has_artificial_blog_url(self):
        return self.blog_url and "theshelf.com/artificial" in self.blog_url

    @property
    def suspicious_url(self):
        return constants.ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL in self.validated_on_list

    @suspicious_url.setter
    def suspicious_url(self, value):
        try:
            value = bool(int(value))
        except ValueError:
            value = False
        if value:
            self.append_validated_on(constants.ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL)
        else:
            self.remove_from_validated_on(constants.ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL)

    @property
    def autodetected(self):
        if self.autodetected_attributes is None:
            self.autodetected_attributes = {}
        return self.autodetected_attributes

    @property
    def platform_validations(self):
        if 'platform_validations' not in self.autodetected:
            self.autodetected['platform_validations'] = {}
        return self.autodetected['platform_validations']

    def autodetect_attribute(self, name, value):
        """
        Set the actual attribute, and then record details about it in autodetected_attributes.
        """
        setattr(self, name, value)

        self.autodetected[name] = dict(value=value, detect_time=datetime.utcnow().isoformat())

    @property
    def category_info(self):
        if self.categories is None:
            self.categories = {}
        return self.categories

    #####-----< Count Fields >-----#####
    @property
    def num_posts(self):
        return self.posts().count()

    @property
    def emails_sent_count(self):
        try:
            return self.agr_emails_sent_count
        except AttributeError:
            mbs = MailProxyMessage.objects.filter(
                thread__influencer=self,
                mandrill_id__regex=r'.(.)+',
                type=MailProxyMessage.TYPE_EMAIL,
                direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER
            )
            return mbs.count()

    @property
    def num_shelved_products(self):
        u = self.shelf_user
        if u:
            return u.userprofile.shelfed_items(unique=True).count()
        else:
            return 0
    #####-----</ Count Fields >-----#####

    #####-----< Foreign Fields >-----#####

    @property
    def price_range_tag(self):
        count = {}
        total = 0.0
        for score in self.scores.all().only('price_range').values('price_range'):
            tag = score["price_range"]
            value = 1
            if tag == "unknown":
                continue
            elif tag == "highend":
                tag = "expensive"
            elif tag == "midlevel":
                tag = "middle"
            if tag in count:
                count[tag] += value
            else:
                count[tag] = value
            total += 1
        if count:
            #count = count.items()
            #count.sort(key=lambda x: -x[1])
            # return count[0][0]
            if count.get("expensive", 0) / total > 0.5:
                return "expensive"
            if count.get("cheap", 0) / total > 0.5:
                return "cheap"
        return "middle"

    def platforms(self):
        return self.platform_set.all()

    def posts(self):
        posts_for_valid_platforms = self.posts_set.all().exclude(platform__url_not_found=True)
        non_empty_posts = posts_for_valid_platforms.exclude(content='').exclude(content__isnull=True)
        return non_empty_posts.order_by('-create_date')

    def new_posts(self):
        return self.posts().filter(create_date__gte=datetime.now() - timedelta(days=364))

    GiveawaySummary = collections.namedtuple('GiveawaySummary', ['post_id', 'added'])

    @property
    def giveaway_summary(self):
        """
        get all giveaways that this user has created
        @return QuerySet of SponsorshipInfo created by this user
        """
        if not hasattr(self, '_giveaway_summary'):
            query = SponsorshipInfo.objects.filter(post__in=self.posts()).order_by('-added_datetime')
            post_and_date = query.values_list('post_id', 'added_datetime')

            self._giveaway_summary = [self.GiveawaySummary(post_id, added_datetime)
                                      for post_id, added_datetime in post_and_date]
        return self._giveaway_summary

    @property
    def max_followers_among_all_platforms(self):
        """
        finds the max of followers across all platforms
        --should be calculated after denormalization on platforms have been called
        """
        plats = self.platforms()
        max_num_followers = 0
        for p in plats:
            if p.num_followers > max_num_followers:
                max_num_followers = p.num_followers
        return max_num_followers

    @property
    def invitations(self):
        """
        Get list of invitations for this user, ignoring the fact that
        database consist duplicate invitations (the same user has been invited
        more than once to the same campaign)
        """
        return InfluencerJobMapping.objects.with_influencer(self).distinct('job')

    @property
    def job_ids(self):
        return InfluencerJobMapping.objects.with_influencer(self).distinct('job').values_list('job', flat=True)

    @property
    def jobs(self):
        """
        Get list of jobs (campaigns) this influencer has been invited to
        """
        # needs to be improved to reduce number of requests from 2 to 1
        return BrandJobPost.objects.filter(id__in=self.job_ids)

    @property
    def group_ids(self):
        return self.group_mapping.exclude(
            status=InfluencerGroupMapping.STATUS_REMOVED
        ).distinct('group').values_list('group', flat=True)

    @property
    def groups(self):
        """
        Get list of groups (collections) this influencer belongs to
        """
        return InfluencersGroup.objects.filter(id__in=self.group_ids)

    @property
    def validated_on_list(self):
        try:
            validated_on = json.loads(self.validated_on)
        except (ValueError, TypeError):
            validated_on = []
        return validated_on

    @property
    def date_created_hash(self):
        return hashlib.md5(str(self.date_created)).hexdigest()

    #####-----</ Foreign Fields >-----#####
    def append_validated_on(self, val):
        try:
            validated_on = json.loads(self.validated_on)
        except (ValueError, TypeError):
            validated_on = []
        validated_on.append(val)
        validated_on = list(set(validated_on))
        self.validated_on = json.dumps(validated_on)
        self.date_edited = datetime.now()

    def save_classification(self, res):
        """
        This method is invoked by the contentclassification module:
        we first save the result
        and then check if the result=='blog', then blacklisted=False, else blacklisted=True
        """
        self.classification = res
        if res == 'blog':
            self.blacklisted = False
        else:
            if res == 'squatter':
                self.problem = 2
                self.invalidate_blog_platform('contentclassificaton_squatter')
            if res == 'brand':
                self.problem = 3
            if res == 'social':
                self.problem = 4
            if res == 'unknown':
                self.problem = 1
            self.set_blacklist_with_reason(res)
        self.append_validated_on(constants.ADMIN_TABLE_INFLUENCER_LIST)
        self.save()

    def invalidate_blog_platform(self, reason):
        # late import to avoid circular imports (platformutils imports models)
        from platformdatafetcher import platformutils
        try:
            # Don't use the self.blog_platform property as it can return a different
            # platform. We need exactly the one that we just classified using self.blog_url
            blog_platform = self.blog_platform
            if blog_platform:
                platformutils.set_url_not_found(reason, blog_platform)
        except Platform.DoesNotExist:
            log.exception('Blog platform not found for influencer with blog_url={}'.format(self.blog_url))

    def _set_fields(self, user, profile):
        """
        make sure userprofile doesn't already have an influencer
        """

        print "Infuencer", self, "matched: ", user, profile.blog_page

        self.shelf_user = user
        if not profile.influencer:
            profile.influencer = self
        else:
            self.save()
            return

        if not profile.blog_name and self.blogname:
            profile.blog_name = self.blogname
        if not profile.name and self.name:
            profile.name = self.name
        profile.can_set_affiliate_links = True
        profile.save()
        self.save()

    def create_userprof(self, dry_run=False):
        """
        Create a user/userprofile for an influencer
        """
        if not self.show_on_search:
            return
        if self.shelf_user:
            return
        if not self.blog_url:
            return
        if not self.blog_platform:
            return
        if self.blog_platform.url != self.blog_url:
            return

        blog_domain = utils.domain_from_url(self.blog_url)
        blog_main = utils.strip_url_of_default_info(self.blog_url, strip_domain=False)

        if self.email:
            emails = self.email.split()
            all_possible_users = []
            for email in emails:
                possible_users = User.objects.filter(
                    email__iexact=email, registrationprofile__isnull=True, userprofile__isnull=False)
                all_possible_users.extend(possible_users)
            if len(all_possible_users):
                if len(all_possible_users) != 1:
                    print "Found following users matching influencer id=%i email" % self.id
                    for user in all_possible_users:
                        print user
                self._set_fields(all_possible_users[0], all_possible_users[0].userprofile)
                return

        user_profiles = UserProfile.objects.filter(blog_page__icontains=blog_main, blog_verified=True)
        if user_profiles:
            if len(user_profiles) != 1:
                print "Found following user profiles matching influencer id=%i blog url" % self.id
                for up in user_profiles:
                    print up
            profile = user_profiles[0]
            self._set_fields(profile.user, profile)
            return

        if dry_run:
            print "profile will be created"
            return

        user = User.objects.create_user(username=constants.SHELF_INFLUENCER_USER(blog_domain),
                                        email=constants.SHELF_INFLUENCER_USER(blog_domain),
                                        password=constants.SHELF_INFLUENCER_PASSWORD)
        profile = UserProfile.objects.create(user=user)

        self._set_fields(user, profile)

        for post in self.posts_set.all():
            post.productmodelshelfmap_set.all().update(user_prof=profile)
            for product in post.productmodelshelfmap_set.all():
                product.shelf.user_id = user
                product.shelf.save()

    def posts_for_platform(self, platform):
        """
        Returns the posts for this influencer for platform_name in descending order of time
        """
        posts = Posts.objects.filter(influencer=self, platform=platform).order_by('-create_date')
        return posts

    def create_platform(self, platform_url, platform_name):
        dups = Platform.find_duplicates(self, platform_url)
        if dups and len(dups) > 0:
            return dups[0]
        plat = Platform.objects.get_or_create(influencer=self, url=platform_url, platform_name=platform_name)[0]
        return plat

    def _select_influencer_to_stay(self, infs):
        def score(inf):
            if inf.source and 'blogger_signup' in inf.source:
                source_score = 1
            else:
                source_score = 0

            if inf.is_enabled_for_automated_edits():
                validated_score = 0
            else:
                validated_score = 1

            if inf.show_on_search:
                show_on_search_score = 1
            else:
                show_on_search_score = 0

            if inf.profile_pic:
                profile_pic_score = 1
            else:
                profile_pic_score = 0

            if not inf.blacklisted:
                blacklisted_score = 1
            else:
                blacklisted_score = 0

            if inf.old_show_on_search:
                old_show_on_search_score = 1
            else:
                old_show_on_search_score = 0

            posts_score = inf.posts_count or 0

            res = (source_score, validated_score, show_on_search_score, old_show_on_search_score, profile_pic_score, posts_score, blacklisted_score, -inf.id)
            log.info('Influencer %r got stay score: %s', inf, res)
            return res
        return max(infs, key=score)

    def handle_duplicates(self):
        '''
        removes duplicates and returns one influencer (after moving platform->influencer for others)
        '''
        from platformdatafetcher import platformutils

        dups = Influencer.find_duplicates(self.blog_url, self.id)
        if len(dups) == 0:
            log.info('No duplicates found')
            return self

        candidates_to_stay = [self] + dups
        selected_inf = self._select_influencer_to_stay(candidates_to_stay)
        infs_to_disable = [inf for inf in candidates_to_stay if inf != selected_inf]
        log.info('Selected influencer to stay: %r', selected_inf)
        log.info('Influencers to disable: %r', infs_to_disable)

        # migrate shelf_user
        if selected_inf.shelf_user is None:
            infs_with_shelf_user = [inf for inf in infs_to_disable if inf.shelf_user is not None]
            if infs_with_shelf_user:
                log.info('Using shelf_user from the first of %r', infs_with_shelf_user)
                selected_inf.shelf_user = infs_with_shelf_user[0].shelf_user
                selected_inf.save()
            else:
                log.info('No infs with shelf_user among infs being disabled')

        all_plats = Platform.objects.filter(influencer__in=infs_to_disable)
        for plat in all_plats:
            plat.influencer = selected_inf
            try:
                plat.save(force_checks=True)
            except IntegrityError:
                log.exception('Unique checks failed for migrated platform, skipping this platform')

        for inf in infs_to_disable:
            with platformutils.OpRecorder(operation='disable_influencer', influencer=inf) as opr:
                log.debug('Disabling influencer %r', inf)
                opr.data = {'old_source': inf.source, 'old_show_on_search': inf.show_on_search}
                inf.source = None
                inf.validated_on = None
                inf.set_show_on_search(False, save=True)

        selected_inf.remove_from_validated_on(constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)

        # check to make sure there are no more duplicates left
        assert len(self.find_duplicates(self.blog_url, selected_inf.id)) == 0

        print "Done removing duplicates for %s, remaining platform: %s" % (self.blog_url, selected_inf)
        return selected_inf

    @property
    def blog_platform(self):
        # if either we never set this attribute or the attribute value is none, set it now
        if not hasattr(self, '_blog_platform') or not self._blog_platform:
            self._blog_platform = self.get_blog_platform()
        return self._blog_platform

    def get_blog_platform(self):
        plats = self.platform_set.all().exclude(platform_name__in=Platform.SOCIAL_PLATFORMS).exclude(url_not_found=True)
        if not plats.exists():
            # ok, now we're going to look for Tumblr also (only if Wordpress or Blogspot doesn't exist)
            plats = self.platform_set.all().filter(platform_name='Tumblr').exclude(url_not_found=True)
            if not plats.exists():
                return None
        if plats.count() == 1:
            return plats[0]
        else:
            # we have more than one platform? we should pick the one with higher number of posts
            post0 = Posts.objects.filter(platform=plats[0])
            post1 = Posts.objects.filter(platform=plats[1])
            if post0.count() > post1.count():
                return plats[0]
            else:
                return plats[1]

    @property
    def valid_platforms(self):
        return [
            pl for pl in self.platform_set.all()
            if not pl.url_not_found]

    @property
    def get_platform_for_search(self):
        return [pl for pl in self.valid_platforms if pl.num_followers]

    @cached_property
    def all_platforms(self):
        from debra.serializers import PlatformSerializer
        from debra.helpers import CacheQuerySet
        try:
            _serialized_platforms = self._serialized_platforms
        except AttributeError:
            _serialized_platforms = None
        return CacheQuerySet(PlatformSerializer, unpack=False).set_cache_key(
            'plsd_{}'.format(self.id)).raw_self(_serialized_platforms).all(
            self.platform_set.exclude(url_not_found=True))

    @cached_property
    def platforms_by_name(self):
        try:
            if not self._serialized_platforms:
                return {}
        except AttributeError:
            return {}
        else:
            groups = collections.defaultdict(list)
            for pl in self._serialized_platforms:
                groups[pl['platform_name']].append(pl)
            return groups

    def get_platforms_by_name(self, name):
        return self.platforms_by_name.get(name, [])

    @cached_property
    def all_time_series(self):
        from debra.serializers import PopularityTimeSeriesSerializer
        from debra.helpers import CacheQuerySet
        return CacheQuerySet(PopularityTimeSeriesSerializer).set_cache_key(
            'ts_{}'.format(self.id)).all(
                self.popularitytimeseries_set.filter(
                    snapshot_date__gte=datetime(year=2015, month=1, day=1)))

    @property
    @cached_model_property
    def about_page(self):
        return reverse('debra.blogger_views.blogger_about', kwargs={'influencer_id': self.id})

    @property
    @cached_model_property
    def edit_page(self):
        return reverse('debra.blogger_views.blogger_edit', kwargs={'influencer_id': self.id})

    # @property
    # def edit_page(self):
    # return reverse('debra.blogger_views.blogger_about_edit',
    # kwargs={'blog_url': utils.domain_from_url(self.blog_url or ''),
    # 'influencer_id': self.id})

    @property
    @cached_model_property
    def posts_page(self):
        return reverse('debra.blogger_views.blogger_posts', kwargs={'influencer_id': self.id})
        # return reverse('debra.blogger_views.blogger_posts', kwargs={'blog_url': utils.domain_from_url(self.blog_url or ''), 'influencer_id': self.id})

    @property
    @cached_model_property
    def posts_sponsored_page(self):
        # return reverse('debra.blogger_views.blogger_posts_sponsored', kwargs={'blog_url': utils.domain_from_url(self.blog_url or ''), 'influencer_id': self.id})
        return reverse('debra.blogger_views.blogger_posts_sponsored', kwargs={'influencer_id': self.id})

    @property
    @cached_model_property
    def items_page(self):
        return reverse('debra.blogger_views.blogger_items', kwargs={'influencer_id': self.id})

    @property
    @cached_model_property
    def photos_page(self):
        return reverse('debra.blogger_views.blogger_photos', kwargs={'influencer_id': self.id})

    @property
    @cached_model_property
    def tweets_page(self):
        return reverse('debra.blogger_views.blogger_tweets', kwargs={'influencer_id': self.id})

    @property
    @cached_model_property
    def pins_page(self):
        return reverse('debra.blogger_views.blogger_pins', kwargs={'influencer_id': self.id})

    @property
    @cached_model_property
    def youtube_page(self):
        return reverse('debra.blogger_views.blogger_youtube', kwargs={'influencer_id': self.id})

    @property
    @cached_model_property
    def items_count(self):
        return feeds_helpers.product_feed_json(request=True, for_influencer=self, count_only=True, default_posts="about")

    @property
    @cached_model_property
    def photos_count(self):
        return feeds_helpers.instagram_feed_json(request=True, for_influencer=self, count_only=True, default_posts="about_insta")

    @property
    @cached_model_property
    def pins_count(self):
        return feeds_helpers.pinterest_feed_json(request=True, for_influencer=self, count_only=True, default_posts="about_pins")

    @property
    @cached_model_property
    def tweets_count(self):
        return feeds_helpers.twitter_feed_json(request=True, for_influencer=self, count_only=True, default_posts="about_tweets")

    @property
    @cached_model_property
    def videos_count(self):
        #return feeds_helpers.youtube_feed_json(request=True, for_influencer=self, count_only=True)
        return self.get_youtube_count()

    @property
    @cached_model_property
    # def dynamic_posts_count(self):
    def blog_posts_count(self):
        return feeds_helpers.blog_feed_json_dashboard(request=True, for_influencer=self, count_only=True)

    def get_youtube_count(self):
        youtube = list(self.platform_set.all().filter(platform_name='Youtube').exclude(url_not_found=True))
        posts = Posts.objects.filter(platform__in=youtube).distinct('url')
        return posts.count()

    def get_posts_section_count(self, section, **kwargs):
        section = feeds_helpers.normalize_feed_key(section)

        default_posts_mapping = {
            feeds_helpers.PINTEREST_FEED_FILTER_KEY: 'about_pins',
            feeds_helpers.TWITTER_FEED_FILTER_KEY: 'about_tweets',
            feeds_helpers.INSTAGRAM_FEED_FILTER_KEY: 'about_insta',
            feeds_helpers.ALL_FEED_FILTER_KEY: 'about_all',
            feeds_helpers.FACEBOOK_FEED_FILTER_KEY: 'about_facebook',
            feeds_helpers.YOUTUBE_FEED_FILTER_KEY: 'about_youtube',
        }

        def get_cache_key():
            res = 'psc_{}_{}'.format(self.id, section)
            if kwargs.get('brand'):
                res = '{}_{}'.format(res, kwargs.get('brand'))
            return res

        def get_search_params():
            params = {}
            if kwargs.get('brand'):
                params.update({
                    'keyword': [kwargs.get('brand')],
                    'keyword_types': ['brand'],
                })
            return params

        def get_data():
            # if section == 'youtube':
            #     return self.get_youtube_count()
            feed_json = feeds_helpers.get_feed_handler(section)
            feed_params = dict(request=True, for_influencer=self, count_only=True,
                default_posts=default_posts_mapping.get(section, 'about'),
                with_parameters=True,
                parameters=get_search_params(),
            )
            data = feed_json(**feed_params)
            return data

        cache_key = get_cache_key()
        data = cache.get(cache_key)
        if data is None:
            data = get_data()
            cache.set(cache_key, data)

        return data

    @property
    @cached_model_property
    def dynamic_posts_sponsored_count(self):
        collabs = InfluencerCollaborations.objects.filter(
            influencer=self,
        )
        return collabs.count()

    @cached_property
    # @cached_model_property
    def profile_pic(self):
        try:
            return self._profile_pic
        except AttributeError:
            if self.shelf_user and self.shelf_user.userprofile:
                if self.shelf_user.userprofile.profile_img_url and self.shelf_user.userprofile.profile_img_url != "None":
                    return self.shelf_user.userprofile.profile_img_url
            if self.profile_pic_url and self.profile_pic_url != "None":
                return self.profile_pic_url
            return "/mymedia/site_folder/images/global/avatar.png"

    @property
    # @cached_model_property
    def cover_pic(self):
        # giving preference to user uploaded files
        if self.shelf_user and self.shelf_user.userprofile:
            if self.shelf_user.userprofile.cover_img_url and self.shelf_user.userprofile.cover_img_url != "None":
                return self.shelf_user.userprofile.cover_img_url
        # now look at the platforms

        t = time.time()

        candidates = filter(
            lambda x: not x.url_not_found and x.cover_img_url and '/themes/theme1/' not in x.cover_img_url,
            self.platform_set.all()
        )
        candidates.sort(key=lambda x: x.platform_name)
        candidates = map(lambda x: x.cover_img_url, candidates)

        print 'cover pic:', time.time() - t

        # candidates = self.platform_set.all().exclude(url_not_found=True).exclude(cover_img_url__isnull=True).exclude(cover_img_url__icontains='/themes/theme1/')
        # # order them by name, so facebook, instagram, pinterest, twitter, youtube
        # cover_img_candidates = candidates.order_by('platform_name').values_list('cover_img_url', flat=True)
        # if len(cover_img_candidates) > 0:
        #     return cover_img_candidates[0]

        # print 'end', time.time() - t

        if len(candidates) > 0:
            return candidates[0]
        return "/static/images/page_graphics/home/new/header_1.jpg"


    def __unicode__(self):
        return 'id: %s name: %r blog_url: %r ' % (self.id, self.name, self.blog_url)

    @staticmethod
    def find_duplicates(blog_url, id=None, exclude_source_isnull=True, exclude_blacklisted=True):
        """
        Searches for Influencer instances that have similar blog urls.
        -> we search by removing 'http', 'www' and '.com' keywords and then search if the remaining keywords match
        -> if id is given, we don't include that id in the returned set (so in this case, the returned set are other influencers)
        """
        from platformdatafetcher import platformutils

        MAX_PRINTED_DUPS = 20

        blog_url_handle = platformutils.url_to_handle(blog_url)
        blog_url_main_token = utils.strip_last_domain_component(blog_url_handle)
        if not blog_url_main_token:
            return []
        all_infs = Influencer.objects.filter(blog_url__icontains=blog_url_main_token)
        if exclude_source_isnull:
            all_infs = all_infs.exclude(source__isnull=True)
        if exclude_blacklisted:
            all_infs = all_infs.exclude(blacklisted=True)
        # we may have false positives now (fashionista.com will match BosFashionista)
        dups = []
        for idx, inf in enumerate(all_infs):
            if id and inf.id == id:
                continue
            token = platformutils.url_to_handle(inf.blog_url)
            if token == blog_url_handle:
                dups.append(inf)
            else:
                if idx <= MAX_PRINTED_DUPS:
                    print "this: %r, potential match candidate: %r (url:%r)" % (blog_url_main_token, token, inf.blog_url)
                if idx == MAX_PRINTED_DUPS:
                    print "will not print more candidates"

        if (len(dups) > 0 and id) or (len(dups) > 1 and not id):
            print "Yes, %r has %s duplicates " % (blog_url, dups)
        return dups

    @staticmethod
    def influencer_stats():
        all_infs = Influencer.trendsetter_influencers()
        # now picking only those twitter platforms that have an facebook profile image and influencer has a location
        have_name = 0
        have_blogname = 0
        have_fb_profile_pic = 0
        have_location = 0
        have_blog = 0
        have_blog_posts = 0
        have_pin_posts = 0
        have_fb_posts = 0
        have_tw_posts = 0
        have_insta_posts = 0
        have_facebook = 0
        have_twitter = 0
        have_pinterest = 0
        have_instagram = 0
        for inf in all_infs:
            if inf.name and inf.name != "Blogger name":
                have_name += 1
            if inf.demographics_location:
                have_location += 1
            fb = Platform.objects.filter(influencer=inf, platform_name="Facebook")
            if fb.exists():
                have_facebook += 1
                if fb.filter(profile_img_url__isnull=False).exists():
                    have_fb_profile_pic += 1
                if Posts.objects.filter(platform=fb[0]).count() > 0:
                    have_fb_posts += 1
            if inf.blog_platform:
                have_blog += 1
                if inf.blog_platform.blogname:
                    have_blogname += 1
                if Posts.objects.filter(platform=inf.blog_platform).count() > 0:
                    have_blog_posts += 1
            pin = Platform.objects.filter(influencer=inf, platform_name="Pinterest")
            if pin.exists():
                have_pinterest += 1
                if Posts.objects.filter(platform=pin[0]).count() > 0:
                    have_pin_posts += 1
            insta = Platform.objects.filter(influencer=inf, platform_name="Instagram")
            if insta.exists():
                have_instagram += 1
                if Posts.objects.filter(platform=insta[0]).count() > 0:
                    have_insta_posts += 1
            twitter = Platform.objects.filter(influencer=inf, platform_name="Twitter")
            if twitter.exists():
                have_twitter += 1
                if Posts.objects.filter(platform=twitter[0]).count() > 0:
                    have_tw_posts += 1

        print "[All: %d] [Loc: %d] [Name: %d] [Blogname: %d][Blog: %d] [FB: %d] [Insta: %d] [Twitter: %d] [Pinterest: %d]"\
            % (all_infs.count(), have_location, have_name, have_blogname, have_blog, have_facebook, have_instagram, have_twitter, have_pinterest)
        print "Have blog posts: %d " % have_blog_posts
        print "Have facebook posts: %d" % have_fb_posts
        print "Have Pinterest posts: %d" % have_pin_posts
        print "have Instagram posts: %d" % have_insta_posts
        print "Have Twitter posts: %d" % have_tw_posts

    #####-----< Denormalization Methods >-----#####
    def calc_popularity_score(self, all_followers_count=None):
        """
        popularity is calculated as follows:
        1) Get the total of all followers for all influencers
        2) Calculate the num of followers for this influencer
        3) Divide the value in (2) by the value in (1) to get the influencer's relative popularity
        4) Multiply by 100 to normalize the value
        """
        if not all_followers_count:
            all_followers_count = self.total_num_followers()
        self_followers_count = self.platforms().exclude(url_not_found=True).aggregate(
            num_followers_total=Sum('num_followers'))['num_followers_total']
        # to make sure the results are not all 0 (ideally this should be
        # calculated dynamically: sum-of-all/minimal count)
        self_followers_count = self_followers_count * 1000000.0 if self_followers_count else 0.0
        rel_popularity = round(
            ((decimal.Decimal(self_followers_count) / decimal.Decimal(all_followers_count)) * 100), 3) if self_followers_count else 0.0
        return rel_popularity

    def calc_engagement_score(self, all_engagement_scores=None):
        """
        engagement is calculated just like popularity except it uses the engagement scores of its platforms as its base
        metric unit
        """
        if not all_engagement_scores:
            all_engagement_scores = self.total_platform_engagement()
        self_engagement_score = self.platforms().exclude(url_not_found=True).aggregate(
            engagement_overall=Sum('score_engagement_overall'))['engagement_overall']

        rel_engagement = round(
            ((decimal.Decimal(self_engagement_score) / decimal.Decimal(all_engagement_scores)) * 100), 3) if self_engagement_score else 0.0
        return rel_engagement

    def calc_average_num_giveaways(self):
        giveaway_count = len(self.giveaway_summary)
        if giveaway_count > 1:
            first, last = self.giveaway_summary[0], self.giveaway_summary[-1]
            months_delta = int((last.added - first.added).days / 30)
            return giveaway_count / months_delta if months_delta > 0 else giveaway_count
        else:
            return giveaway_count

    def calc_posts_count(self):
        if self.blog_platform is None:
            return 0
        posts = Posts.objects.filter(influencer=self, create_date__isnull=False, platform=self.blog_platform)
        return posts.count()

    def calc_average_num_posts(self):
        '''
        #posts / months
        '''
        if self.blog_platform is None:
            return 0

        connection = db_util.connection_for_reading()
        cursor = connection.cursor()
        cursor.execute('''
            SELECT count(id), min(create_date), max(create_date)
            FROM debra_posts ps
            WHERE ps.influencer_id = %s AND ps.platform_id = %s AND create_date IS NOT NULL
            ''', [self.pk, self.blog_platform.pk])
        rows = cursor.fetchall()

        posts_count, first_create_date, last_create_date = rows[0]
        if posts_count > 1:
            months_delta = int((last_create_date - first_create_date).days / 30)
            return posts_count / months_delta if months_delta > 0 else posts_count
        else:
            return posts_count

    def calc_average_num_comments_per_giveaway(self):
        a_year_ago = datetime.today() - timedelta(days=364)
        this_year_only = [summary for summary in self.giveaway_summary
                          if summary.added > a_year_ago]
        post_ids = [s.post_id for s in this_year_only]
        comments = PostInteractions.objects.filter(post_id__in=post_ids)
        num_giveaways = len(self.giveaway_summary)
        return int(comments.count() / num_giveaways) if num_giveaways else 0

    def calc_average_num_comments_per_post(self):
        if self.blog_platform is None:
            return 0
        return self.blog_platform.avg_numcomments_overall
        #posts = self.new_posts().filter(platform=self.blog_platform)
        #num_comments = PostInteractions.objects.filter(post__in=posts, if_commented=True).count()
        #num_posts = posts.count()
        # return num_comments / num_posts if num_posts > 0 else 0

    def calc_average_num_comments_per_sponsored_post(self):
        if self.blog_platform is None:
            return 0
        posts = self.new_posts().filter(is_sponsored=True, platform=self.blog_platform)
        num_comments = PostInteractions.objects.filter(post__in=posts, if_commented=True).count()
        num_posts = posts.count()
        return num_comments / num_posts if num_posts > 0 else 0

    def calc_is_active(self):
        """
        this could be potentially pretty inaccurate but we'll have another metric to identify how active the blogger is
        """
        if self.blog_platform is None:
            return None
        posts = Posts.objects.filter(platform=self.blog_platform).filter(create_date__isnull=False)
        if not posts.exists():
            return None
        # should have posted at least 1 post in the last 3 months
        start_date = datetime.today() - timedelta(days=30 * 3)
        return posts.filter(create_date__gte=start_date).count() >= 1

    def calc_is_live(self):
        # make sure the url is reachable & platform is available and url_not_found is not set
        url = self.blog_url
        is_reachable = utils.can_get_url(url)
        return self.blog_platform and (self.blog_platform.url_not_found is not True) and is_reachable

    def set_profile_pic(self):
        # first reset it
        self.profile_pic_url = None
        self.save()
        img_candidates = self.platform_set.filter(profile_img_url__isnull=False, num_followers__gt=0).exclude(url_not_found=True).order_by('-num_followers').values_list('profile_img_url', flat=True)
        available_images = []
        for url in img_candidates:
            if not url:
                continue
            try:
                dims = get_dims_for_url(url)
            except:  # catching url open, image read errors and bad urls
                continue
            if not dims:
                continue
            if dims[0] < dims[1] * 3:
                available_images.append((dims[0] + dims[1], url))
                break
        if available_images:
            # get biggest image
            available_images.sort()
            self.profile_pic_url = available_images[-1][1]
            self.save()

    def set_description_from_platforms(self):
        cur_descr = self.description
        platforms_qs = self.platform_set.all().filter(
            platform_name__in=Platform.SOCIAL_PLATFORMS).exclude(url_not_found=True)
        for platform in platforms_qs:
            if platform.description and (not cur_descr or len(platform.description) >= len(cur_descr)):
                cur_descr = platform.description
            if platform.about and (not cur_descr or len(platform.about) >= len(cur_descr)):
                cur_descr = platform.about
        # update only if there is no current description
        if cur_descr and not self.description:
            self.description = cur_descr
            self.save()

    def set_blogname(self):
        if self.blog_platform:
            self.blogname = self.blog_platform.blogname
            self.save()
        if self.shelf_user and self.shelf_user.userprofile and not self.shelf_user.userprofile.blog_name:
            self.shelf_user.userprofile.blog_name = self.blogname
            self.shelf_user.userprofile.can_set_affiliate_links = True
            self.shelf_user.userprofile.save()

    def enable_show_on_search(self):
        # TODO: enable this later, for now we're commenting this out
        if not self.blog_url or not self.source:
            return False
        self.set_profile_pic()
        if self.is_live and self.posts_count > 10 and self.profile_pic_url:
            self.date_upgraded_to_show_on_search = datetime.now()
            self.set_show_on_search(True, save=True)
            return True
        return False

    def set_show_on_search(self, value, save=True, on_production=True):
        if on_production:
            self.old_show_on_search = value
        self.show_on_search = value
        self.date_upgraded_to_show_on_search = datetime.now()
        if save:
            self.save()

        # late import to avoid circular imports on boot
        from debra import tasks
        tasks.update_influencer_show_on_search.delay(self.pk)

    def update_posts_show_on_search(self):
        self.posts_set.all().update(show_on_search=self.show_on_search)

    def calculate_category_info(self):
        query = '''
        WITH category_info AS (
            SELECT postcategories.category_id AS category_id, count(postcategories.category_id) AS posts
            FROM {posts_table} posts INNER JOIN {postcategory_table} postcategories ON
                posts.id = postcategories.post_id
            WHERE posts.influencer_id = %s
            GROUP BY postcategories.category_id
        )
        SELECT category.name, category_info.posts
        FROM category_info INNER JOIN {category_table} category
            ON category_info.category_id = category.id
        '''.format(posts_table=Posts._meta.db_table,
                   postcategory_table=PostCategory._meta.db_table,
                   category_table=Category._meta.db_table)

        connection = db_util.connection_for_reading()
        cursor = connection.cursor()
        cursor.execute(query, [self.pk])
        result = cursor.fetchall()

        if result:
            self.category_info.setdefault('count', {})
            self.category_info['count'].update(result)

    #####-----</ Denormalization Methods >-----#####

    #####-----< Denormalization >-----#####
    def denormalize_platforms(self):
        for pl in self.platform_set.exclude(url_not_found=True).filter(platform_name__in=Platform.SOCIAL_PLATFORMS_CRAWLED):
            log.debug('Denormalizing platform %r', pl)
            pl._do_denormalize()
            log.debug('Done')

    def denormalize_influencer_attributes(self):
        if not self.profile_pic_url:
            log.debug('Setting profile_pic')
            self.set_profile_pic()
            log.debug('Done')

        # set description
        if not self.description:
            log.debug('Setting description')
            self.set_description_from_platforms()
            log.debug('Done')

        # set blogname
        if not self.blogname:
            log.debug('Setting blogname')
            self.set_blogname()
            log.debug('Done')

        if not self.lb_url or not self.youtube_url:
            log.debug('Filling youtube_url, lb_url')
            platforms_qs = self.platform_set.all().filter(
                platform_name__in=['Lookbook', 'YouTube']).exclude(url_not_found=True)
            for platform in platforms_qs:
                if platform.platform_name == "Lookbook" and not self.lb_url:
                    self.lb_url = platform.url
                if platform.platform_name == "YouTube" and not self.youtube_url:
                    self.youtube_url = platform.url
            log.debug('Done')

    def denormalize_scores(self, total_popularity_score=None, total_engagement_score=None):
        log.debug('Computing scores')
        self.score_popularity_overall = self.calc_popularity_score(total_popularity_score)
        self.score_engagement_overall = self.calc_engagement_score(total_engagement_score)
        log.debug('Done')

        log.debug('Computing posts count')
        self.posts_count = self.calc_posts_count()
        log.debug('Done')

        log.debug('Computing average nums')
        self.average_num_giveaways = self.calc_average_num_giveaways()
        self.average_num_posts = self.calc_average_num_posts()
        self.average_num_comments_per_giveaway = self.calc_average_num_comments_per_giveaway()
        self.average_num_comments_per_post = self.calc_average_num_comments_per_post()
        self.average_num_comments_per_sponsored_post = self.calc_average_num_comments_per_sponsored_post()
        log.debug('Done')

    def denormalize_is_active(self):
        log.debug('Computing is_active')
        self.is_active = self.calc_is_active()
        log.debug('Done')

        log.debug('Computing is_live')
        self.is_live = self.calc_is_live()
        log.debug('Done')

    def denormalize_influencer_score(self):
        log.debug('Computing influencer scores')
        InfluencerScore._process_influencer(self)
        log.debug('Done')

    def denormalize(self, total_popularity_score=None, total_engagement_score=None):
        log.info('Running full denormalize for influencer: {!r}'.format(self))

        self.denormalize_fast(total_popularity_score, total_engagement_score)
        self.denormalize_slow()

    def denormalize_fast(self, total_popularity_score=None, total_engagement_score=None):
        self.denormalize_influencer_attributes()
        self.denormalize_scores(total_popularity_score, total_engagement_score)
        self.denormalize_is_active()

        log.debug('Saving after denormalize_fast')
        self.save()
        log.debug('Done')

    def denormalize_slow(self):
        self.denormalize_platforms()

        log.debug('Saving after denormalize_platforms')
        self.save()
        log.debug('Done')

        self.denormalize_influencer_score()

    @classmethod
    def overall_scores_to_relative(cls, qs=None):
        infs = qs if qs else cls.objects.all()

        pop_overall = [(inf, inf.score_popularity_overall) for inf in infs
                       if inf.score_popularity_overall is not None]
        pop_relative = utils.absolute_values_to_relative_ordering(pop_overall)
        for (inf, rel) in pop_relative:
            inf.score_popularity_overall = rel

        eng_overall = [(inf, inf.score_engagement_overall) for inf in infs
                       if inf.score_engagement_overall is not None]
        eng_relative = utils.absolute_values_to_relative_ordering(eng_overall)
        for (inf, rel) in eng_relative:
            inf.score_engagement_overall = rel

        for inf in infs:
            if inf.score_popularity_overall is not None or inf.score_engagement_overall is not None:
                inf.save()
    #####-----</ Denormalization >-----#####

    def get_platform_activity_levels(self):
        return [p.activity_level for p in self.platform_set.all().exclude(url_not_found=True)]

    def save(self, *args, **kwargs):
        bypass_checks = kwargs.pop('bypass_checks', None)
        if bypass_checks:
            log.warn('Bypassing duplicate checks')
            return models.Model.save(self, *args, **kwargs)
        if self.id is not None or not self.blog_url:
            # If the influencer is already in the DB, or we don't have blog_url to check for duplicates,
            # we do normal saving
            return models.Model.save(self, *args, **kwargs)
        dups = Influencer.find_duplicates(self.blog_url, self.id)
        if dups:
            log.warn('Influencer dups detection: not inserting %r because of duplicates: %r', self, dups)
            return
        log.warn('Influencer dups detection: inserting %r, no duplicates', self)
        return models.Model.save(self, *args, **kwargs)

    @property
    def feed_stamp(self):
        from debra.serializers import unescape
        data = {
            'id': self.id,
            'user_name': unescape(self.name),
            'first_name': unescape(self.first_name),
            'blog_name': unescape(self.blogname),
            'blog_page': self.blog_url,
            'pic': self.profile_pic,
            'details_url': reverse(
                'debra.search_views.blogger_info_json', args=(self.id,)),
            'date_created_hash': self.date_created_hash,
        }
        for platform in self.get_platform_for_search:
            data["%s_fol" % platform.platform_name] = platform.num_followers
        data["coms"] = self.average_num_comments_per_post
        return data

    def set_blacklist_with_reason(self, reason):
        """
        Helper method.
        Sets the blacklisted flag to True
        and sets the blacklist_reasons text array field
        """

        cur_reasons = self.blacklist_reasons
        if cur_reasons:
            cur_reasons.append(reason)
        else:
            cur_reasons = [reason]
        self.blacklist_reasons = cur_reasons
        self.blacklisted = True
        self.save()

        # updating index of this influencer
        influencer_set_blacklisted(self.id, self.blacklisted)

    # def add_tags(self, tags, to_save=True):
    #     cur_tags = self.tags
    #     if cur_tags:
    #         cur_tags = set(self.tags)
    #         cur_tags.update(tags)
    #     else:
    #         cur_tags = set(tags)
    #     self.tags = list(cur_tags)
    #     if to_save:
    #         self.save()

    # def remove_tags(self, tags, to_save=True):
    #     cur_tags = self.tags
    #     if cur_tags:
    #         cur_tags = set(cur_tags) - set(tags)
    #         self.tags = cur_tags
    #         if to_save:
    #             self.save()

    def describe(self):
        """
        Helper method, just shows all content of fields of current influencer.
        """
        fields = self._meta.fields
        for field in fields:
            print('%s : %s' % (field.name, getattr(self, field.name)))

    def reset_social_platforms(self):
        """
        This method resets all social platforms and their corresponding urls to non-autovalidated and invisible
         with their handlers set to None.
        """
        from platformdatafetcher.platformutils import set_url_not_found

        # a) cleaning up the social *_url fields
        self.fb_url = None
        self.pin_url = None
        self.tw_url = None
        self.insta_url = None
        self.bloglovin_url = None
        self.youtube_url = None
        self.pose_url = None
        self.lb_url = None
        self.gplus_url = None

        # b) for all social platforms, mark them autovalidated=None and invisible
        self.platform_set.filter(
            platform_name__in=Platform.SOCIAL_PLATFORMS
        ).update(
            autovalidated=False,
            autovalidated_reason=None,
        )

        # c) calling set_url_not_found('reset', platform, True) for them all
        for plat in self.platform_set.filter(platform_name__in=Platform.SOCIAL_PLATFORMS):
            set_url_not_found('reset', plat, True)

    def show_social_platforms(self):
        """
        Shows social platforms with their visible/autovalidated stats
        """
        for p in self.platform_set.order_by('platform_name', 'id'):
            print p, 'url_not_found=', p.url_not_found, \
                'autovalidated=', p.autovalidated, 'reason=', p.autovalidated_reason

    def weird_visible_platforms(self):
        """
        Checking sanity of visible platforms this influencer has.
        Criteria:
            * any number of autovalidated/visible platforms
            * only one non-autovalidated/visible platform of a type if no autovalidated found

        :return list of platform names which do not uphold these criteria.
        """
        visible = {}
        for plat in self.platform_set.exclude(url_not_found=True):
            if plat.platform_name not in visible:
                visible[plat.platform_name] = {'autovalidated': 0, 'not_autovalidated': 0}

            if plat.autovalidated is True:
                visible[plat.platform_name]['autovalidated'] += 1
            else:
                visible[plat.platform_name]['not_autovalidated'] += 1

        result = []
        for k, v in visible.items():
            # should be no visible not_autovalidated if there is at least one autovalidated
            if v['autovalidated'] > 0 and v['not_autovalidated'] > 0:
                if k not in result:
                    result.append(k)
            # should be no more than 1 non-autovalidated platforms
            elif v['not_autovalidated'] > 1:
                if k not in result:
                    result.append(k)

        return result if len(result) > 0 else None

    def recalculate_age_distribution(self):
        """
        recalculates percent distribution estimated ages of influencer's blog visitors using ES search.
        :param group_data -- a dict of keywords. keys should be suffixes of appropriate fiields,
                             values should be dicts of keywords.

        Asana task: https://app.asana.com/0/38788253712150/110713706980898
        """
        if not self.id:
            log.error('Influencer must have id and be indexed to recalculate its estimated values')
            return

        from debra.elastic_search_helpers import get_posts_total_by_keywords

        posts_counts = dict()
        total_count = None

        # getting posts count
        for group_name, keyword_list in influencer_age_groups_dict.items():
            posts_count = get_posts_total_by_keywords(self.id, keyword_list)
            if posts_count is not None:
                posts_counts[group_name] = float(posts_count)
                total_count = total_count + posts_count if total_count is not None else posts_count

        # recalculating percents and updating values
        # Currently we just plainly calculate distributions without any weights or keyword per group counts
        if total_count is None:
            log.error('No counts were found - perhaps influencer %s has no indexed posts or ES could not be reached.')
            return
        elif total_count == 0:
            log.error('Total posts for all ages is 0, can\'t calculate percentages.')
            return
        else:
            total_count = float(total_count)

        if total_count > 0:  # otherwise division by zero is possible
            # for group_name, group_total in posts_counts.items():
            #     if hasattr(self, "dist_age_%s" % group_name):
            #         percent = float(group_total * 100.0 / total_count)
            #         setattr(self, "dist_age_%s" % group_name, percent)

            # counting totals and stats only for 4 top values to make them sure to be in 25%
            top_4_counts = dict(sorted(posts_counts.iteritems(), key=operator.itemgetter(1), reverse=True)[:4])
            total_count = float(0)
            for group_total in top_4_counts.values():
                total_count += group_total

            for group_name, group_total in posts_counts.items():
                if hasattr(self, "dist_age_%s" % group_name):
                    if group_name in top_4_counts:
                        percent = float(group_total * 100.0 / total_count)
                        setattr(self, "dist_age_%s" % group_name, percent)
                    else:
                        setattr(self, "dist_age_%s" % group_name, None)

            self.last_modified = datetime.now()
            self.save()

    def debug_age_dist(self):
        print('Influencer id: %s' % self.id)
        print('Age 0-19: %s' % self.dist_age_0_19)
        print('Age 20-24: %s' % self.dist_age_20_24)
        print('Age 25-29: %s' % self.dist_age_25_29)
        print('Age 30-34: %s' % self.dist_age_30_34)
        print('Age 35-39: %s' % self.dist_age_35_39)
        print('Age 40+: %s' % self.dist_age_40)

    def recalculate_gender_distribution(self):
        """
        recalculates percent distribution estimated ages of influencer's blog visitors using ES search.

        Future method stub.
        """
        log.warn('Method not yet implemented')
        return


@receiver(post_delete, sender=Influencer)
def delete_influencer_from_es(sender, instance, **kwargs):
    """
    Deletes data of influencer from ElasticSearch index after it is deleted from DB.
    :param sender:
    :param instance:
    :param using:
    :return:
    """
    endpoint = "/%s/influencer/%s" % (ELASTICSEARCH_INDEX, instance.id)
    url = ELASTICSEARCH_URL

    make_es_delete_request(es_url=url + endpoint)
    # requests.delete(url + endpoint,
    #                 auth=HTTPBasicAuth(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
    #                 )


class InfluencerEditHistory(models.Model):
    influencer = models.ForeignKey('Influencer', related_name='edit_history')
    timestamp = models.DateTimeField(auto_now_add=True)
    field = models.CharField(max_length=50)
    prev_value = models.TextField(null=True, blank=True)
    curr_value = models.TextField(null=True, blank=True)

    @classmethod
    def commit_change(cls, influencer, field, new_value):
        edit = InfluencerEditHistory()
        edit.influencer = influencer
        edit.field = field
        edit.prev_value = getattr(influencer, field, 'Nil')
        if not edit.prev_value:
            edit.prev_value = "unknown"
        edit.curr_value = new_value
        edit.save()

    def __unicode__(self):
        return u"Influencer: %s Field: %s Prev: '%s' Curr: '%s'" % (self.influencer.id,
                                                                    self.field,
                                                                    self.prev_value,
                                                                    self.curr_value)

class InfluencerScore(models.Model):
    influencer = models.ForeignKey('Influencer', related_name='scores')
    score = models.FloatField()
    category = models.CharField(max_length=128)
    price_range = models.CharField(max_length=32)

    class Meta:
        unique_together = ('category', 'price_range', 'influencer')

    def __unicode__(self):
        return u"influencer id=%i for %s at %s" % (self.influencer.id, self.category, self.price_range)

    @classmethod
    def _tag_price_range(cls, category, price):
        levels = {
            #'category_name': (cheap_max, mid_max, expensive_max)
            # $1 < cheap_max < mid_max < expensive_max < +inf
            #'accessories': (30, 50, 100),
            #'active': (30, 50, 100),
            #'apparel': (30, 50, 100),
            #'aviator': (30, 50, 100),
            #'aviators': (30, 50, 100),
            #'backpack': (30, 50, 100),
            'bags': (30, 120, 400),
            #'bandeau': (30, 50, 100),
            #'bangle': (30, 50, 100),
            #'baseball cap': (30, 50, 100),
            #'baseball hat': (30, 50, 100),
            #'beanie': (30, 50, 100),
            #'beauty': (30, 50, 100),
            #'belt': (30, 50, 100),
            #'beret': (30, 50, 100),
            #'bermuda': (30, 50, 100),
            #'bikini': (30, 50, 100),
            #'blazer': (30, 50, 100),
            #'blouse': (30, 50, 100),
            #'bootie': (30, 50, 100),
            #'boots': (30, 50, 100),
            #'bottom': (30, 50, 100),
            #'boxers': (30, 50, 100),
            #'bra': (30, 50, 100),
            #'bracelet': (30, 50, 100),
            #'briefcase': (30, 50, 100),
            #'briefs': (30, 50, 100),
            #'brooch': (30, 50, 100),
            #'button-down': (30, 50, 100),
            #'cami': (30, 50, 100),
            #'capris': (30, 50, 100),
            #'cardigan': (30, 50, 100),
            #'cargo': (30, 50, 100),
            #'chino': (30, 50, 100),
            #'clutch': (30, 50, 100),
            #'coat': (30, 50, 100),
            #'cords': (30, 50, 100),
            #'courier': (30, 50, 100),
            #'cover up': (30, 50, 100),
            #'coverup': (30, 50, 100),
            #'cowboy hat': (30, 50, 100),
            #'cowl': (30, 50, 100),
            #'crewneck': (30, 50, 100),
            #'cross-body': (30, 50, 100),
            #'crossbody': (30, 50, 100),
            #'cuff bracelet': (30, 50, 100),
            'denim': (40, 120, 250),
            #'dress': (30, 50, 100),
            'dresses': (30, 100, 250),
            #'duffel': (30, 50, 100),
            #'earrings': (30, 50, 100),
            #'eyewear': (30, 50, 100),
            #'fedora': (30, 50, 100),
            #'flip flops': (30, 50, 100),
            #'flip-flops': (30, 50, 100),
            #'footwear': (30, 50, 100),
            #'fragrance': (30, 50, 100),
            #'gladiator': (30, 50, 100),
            #'glasses': (30, 50, 100),
            #'gloves': (30, 50, 100),
            #'gown': (30, 50, 100),
            #'handbag': (30, 50, 100),
            #'hats': (30, 50, 100),
            #'headband': (30, 50, 100),
            #'heel': (30, 50, 100),
            #'henley': (30, 50, 100),
            #'hobo': (30, 50, 100),
            #'hood': (30, 50, 100),
            #'hoops': (30, 50, 100),
            'innerwear': (15, 40, 100),
            #'intimate': (30, 50, 100),
            #'intimates': (30, 50, 100),
            #'jackets': (30, 50, 100),
            #'jeans': (30, 50, 100),
            #'jewelry': (30, 50, 100),
            #'khakis': (30, 50, 100),
            #'knit': (30, 50, 100),
            #'leg': (30, 50, 100),
            #'leggings': (30, 50, 100),
            #'leotard': (30, 50, 100),
            #'lipstick': (30, 50, 100),
            #'loafer': (30, 50, 100),
            #'long sleeve': (30, 50, 100),
            #'loungewear': (30, 50, 100),
            #'maternity': (30, 50, 100),
            #'maxi': (30, 50, 100),
            #'maxiskirt': (30, 50, 100),
            #'messenger': (30, 50, 100),
            #'mini': (30, 50, 100),
            #'mittens': (30, 50, 100),
            #'nailpolish': (30, 50, 100),
            #'necklace': (30, 50, 100),
            #'nightgown': (30, 50, 100),
            #'nightie': (30, 50, 100),
            #'one piece': (30, 50, 100),
            #'one-piece': (30, 50, 100),
            'outerwear': (50, 200, 400),
            #'pajama': (30, 50, 100),
            'pant': (40, 120, 250),
            #'panties': (30, 50, 100),
            'pants': (40, 120, 250),
            #'peacoat': (30, 50, 100),
            #'pencil skirt': (30, 50, 100),
            #'pendant': (30, 50, 100),
            #'perfume': (30, 50, 100),
            #'plus size': (30, 50, 100),
            #'plus sized': (30, 50, 100),
            #'plus-size': (30, 50, 100),
            #'plus-sized': (30, 50, 100),
            #'polo': (30, 50, 100),
            #'poncho': (30, 50, 100),
            #'pregnancy': (30, 50, 100),
            #'pregnant': (30, 50, 100),
            #'pullover': (30, 50, 100),
            #'pump': (30, 50, 100),
            #'purse': (30, 50, 100),
            #'robe': (30, 50, 100),
            #'romper': (30, 50, 100),
            #'runner': (30, 50, 100),
            #'sandal': (30, 50, 100),
            #'sarong': (30, 50, 100),
            #'satchel': (30, 50, 100),
            #'scarf': (30, 50, 100),
            #'scarves': (30, 50, 100),
            #'shawl': (30, 50, 100),
            #'sheath': (30, 50, 100),
            #'shift': (30, 50, 100),
            'shirt': (25, 60, 250),
            'shirts': (25, 60, 250),
            'shoe': (40, 100, 300),
            'shoes': (40, 100, 300),
            #'short': (30, 50, 100),
            'skirt': (40, 80, 200),
            'skirts': (40, 80, 200),
            #'skort': (30, 50, 100),
            #'slack': (30, 50, 100),
            'sleepwear': (20, 50, 140),
            #'sneaker': (30, 50, 100),
            #'sock': (30, 50, 100),
            #'sport': (30, 50, 100),
            #'sportcoat': (30, 50, 100),
            #'sports bra': (30, 50, 100),
            #'stiletto': (30, 50, 100),
            #'sunglasses': (30, 50, 100),
            #'sweater': (30, 50, 100),
            'sweaters': (40, 90, 250),
            #'sweatshirt': (30, 50, 100),
            #'swim suit': (30, 50, 100),
            #'swimsuit': (30, 50, 100),
            #'swimwear': (30, 50, 100),
            #'tank': (30, 50, 100),
            #'tankini': (30, 50, 100),
            #'tee': (30, 50, 100),
            #'thong': (30, 50, 100),
            #'tights': (30, 50, 100),
            #'topcoat': (30, 50, 100),
            #'tote': (30, 50, 100),
            #'trench': (30, 50, 100),
            #'trouser': (30, 50, 100),
            #'trunk': (30, 50, 100),
            #'tunic': (30, 50, 100),
            #'turtleneck': (30, 50, 100),
            #'two piece': (30, 50, 100),
            #'two-piece': (30, 50, 100),
            #'umbrella': (30, 50, 100),
            #'undergarment': (30, 50, 100),
            #'underwear': (30, 50, 100),
            #'underwire': (30, 50, 100),
            #'v-neck': (30, 50, 100),
            #'vest': (30, 50, 100),
            #'visor': (30, 50, 100),
            #'wallet': (30, 50, 100),
            #'watches': (30, 50, 100),
            #'wedge': (30, 50, 100),
            #'wetsuit': (30, 50, 100),
            #'wide brim': (30, 50, 100),
            #'wingtip': (30, 50, 100),
            #'workout': (30, 50, 100),
            #'wristlet': (30, 50, 100),
            #'yoga': (30, 50, 100),
        }
        level = levels.get(category, None)
        if level:
            low, mid, high = level
            if price <= low:
                return 'cheap'
            elif price <= mid:
                return 'midlevel'
            elif price <= high:
                return 'expensive'
            else:
                return 'highend'
        else:
            return 'unknown'

    @classmethod
    def _score_dict_for_influencer(cls, influencer):
        score_dict = {}
        all_prods = ProductModelShelfMap.objects.filter(influencer=influencer)
        if influencer.latest_in_influencer_score is not None:
            all_prods = all_prods.filter(added_datetime__gt=influencer.latest_in_influencer_score)
            filtered = True
        else:
            filtered = False
        if not all_prods.exists():
            return {}, filtered, influencer.latest_in_influencer_score
        latest = all_prods.order_by('-added_datetime')[0].added_datetime

        all_prods = all_prods.select_related('product_model')

        for product in all_prods:
            # print "product", product
            product_model = product.product_model
            cat1 = product_model.cat1
            if cat1:
                price = product_model.price
                tag = cls._tag_price_range(cat1, price)
                label = (cat1, tag)
                if label not in score_dict:
                    score_dict[label] = 0
                score_dict[label] += 1
            cat2 = product_model.cat2
            if cat2:
                price = product_model.price
                tag = cls._tag_price_range(cat2, price)
                label = (cat2, tag)
                if label not in score_dict:
                    score_dict[label] = 0
                score_dict[label] += 1
            cat3 = product_model.cat3
            if cat3:
                price = product_model.price
                tag = cls._tag_price_range(cat3, price)
                label = (cat3, tag)
                if label not in score_dict:
                    score_dict[label] = 0
                score_dict[label] += 1
        return score_dict, filtered, latest

    @classmethod
    def _process_influencer(cls, influencer):
        score_dict, filtered, new_latest = cls._score_dict_for_influencer(influencer)
        if not filtered:
            influencer.scores.using('default').all().delete()
        for label, score in score_dict.iteritems():
            category, tag = label
            inf_score = utils.get_first_or_instantiate(cls.objects.using('default'),
                                                       influencer=influencer,
                                                       category=category, price_range=tag)
            inf_score.score = (inf_score.score or 0) + score
            inf_score.save()
        influencer.latest_in_influencer_score = new_latest
        influencer.price_range_tag_normalized = influencer.price_range_tag
        influencer.save()

    @classmethod
    def denormalize(cls):
        influencers = Influencer.raw_influencers_for_search().prefetch_related(
            'posts_set', 'posts_set__productmodelshelfmap_set')
        cnt = influencers.count()
        for n, influencer in enumerate(influencers):
            print n + 1, "/", cnt
            cls._process_influencer(influencer)

@receiver(post_delete, sender=InfluencerScore)
def delete_product_from_es(sender, instance, **kwargs):
    """
    Deletes data of iscore from ElasticSearch index after it is deleted from DB.
    :param sender:
    :param instance:
    :param using:
    :return:
    """
    endpoint = "/%s/influencer_score/%s" % (ELASTICSEARCH_INDEX, instance.id)
    url = ELASTICSEARCH_URL

    make_es_delete_request(es_url=url + endpoint)
    # requests.delete(url + endpoint,
    #                 auth=HTTPBasicAuth(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
    #                 )


class InfluencerInfoForBrand(models.Model):
    info_type = models.CharField(max_length=64)
    range_min = models.FloatField(null=True, blank=True)
    range_max = models.FloatField(null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    influencer = models.ForeignKey(Influencer, related_name="infos_for_brands")


class InfluencerCollaborations(models.Model):
    COLLABORATION_TYPES = (
        ("sponsored_posts", "Sponsored Post"),
        ("product_reviews", "Product Review"),
        ("giveaways", "Giveaway"),
        ("banner_ads", "Banner Ad"),
        ("event_coverage", "Event Coverage"),
        ("affiliate", "Affiliate Offer"),
        ("other", "Other"),
    )
    brand_name = models.CharField(max_length=64)
    brand_url = models.CharField(max_length=128)
    post_url = models.CharField(max_length=128)
    timestamp = models.DateTimeField(null=True, blank=True)
    collaboration_type = models.CharField(max_length=20, choices=COLLABORATION_TYPES)
    details = models.TextField(null=True, blank=True)
    influencer = models.ForeignKey(Influencer, related_name="collaborations")


class InfluencerValidationQueue(models.Model):
    STATES = (
        (0, 'Unknown'),
        (1, 'Queued'),
        (2, 'Validated on All'),
        (3, 'Validated on Table 1'),
        (4, 'Validated on Table 2'),
        (5, 'Validated on Table 3'),
    )
    uuid = models.CharField(max_length=64, default=lambda: str(uuid4()))
    influencer = models.ForeignKey(Influencer, related_name="validation_queue")
    state = models.IntegerField(default=0, choices=STATES)


class PlatformActivityLevelMixin(object):
    periods = [
        (timedelta(days=1), ActivityLevel.ACTIVE_LAST_DAY),
        (timedelta(days=7), ActivityLevel.ACTIVE_LAST_WEEK),
        (timedelta(days=30), ActivityLevel.ACTIVE_LAST_MONTH),
        (timedelta(days=30 * 3), ActivityLevel.ACTIVE_LAST_3_MONTHS),
        (timedelta(days=30 * 6), ActivityLevel.ACTIVE_LAST_6_MONTHS),
        (timedelta(days=365), ActivityLevel.ACTIVE_LAST_12_MONTHS),
    ]

    def calculate_activity_level(self):
        today = datetime.today()

        if self.insert_date and self.insert_date > today - timedelta(days=30):
            self.activity_level = ActivityLevel.ACTIVE_NEW
            return

        last_post = self.get_last_post_date()
        if not last_post:
            self.activity_level = ActivityLevel.ACTIVE_UNKNOWN
            return

        for period, level in self.periods:
            if last_post > today - period:
                self.activity_level = level
                return

        # Fallback to lowest activity level
        self.activity_level = ActivityLevel.ACTIVE_LONG_TIME_AGO


class PlatformQuerySet(InfluencerRelatedQuerySet):

    def valid(self):
        return self.exclude(url_not_found=True).exclude(url__contains='theshelf.com/artificial')

    def with_fetchable_influencer(self):
        preselect_influencer = self.select_related('influencer')
        return preselect_influencer.filter(influencer__source__isnull=False,
                                           influencer__blog_url__isnull=False).exclude(influencer__blacklisted=True)

    def eligible_for_daily_fetching(self):
        return self.filter(platform_name__in=settings.DAILY_FETCHED_PLATFORMS)

    def for_daily_fetching(self):
        return self.valid().with_fetchable_influencer().eligible_for_daily_fetching()

    def searchable_influencer(self):
        # either these influencers are showing on production or have been recently qa-ed
        import datetime
        dd = datetime.date(2016, 6, 12)
        q1 = self.filter(influencer__old_show_on_search=True)
        q2 = self.filter(influencer__date_validated__gte=dd)
        q = q1 | q2
        return q.exclude(influencer__blacklisted=True).exclude(influencer__validated_on__contains='susp')

    def for_everyday_fetching(self):
        return self.for_daily_fetching().searchable_influencer()
        # commenting the one below for now because seems like we're
        # skipping a bunch of platforms
        # return self.for_daily_fetching().searchable_influencer() & (
        #     self._active_everyday() |
        #     self._top_platforms() |
        #     self._with_signedup_influencers() |
        #     self.filter(num_followers__gte=1000)
        # )

    def active_in_last_3_months(self):
        return self.filter(activity_level__in=[
            ActivityLevel.ACTIVE_NEW,
            ActivityLevel.ACTIVE_LAST_DAY,
            ActivityLevel.ACTIVE_LAST_WEEK,
            ActivityLevel.ACTIVE_LAST_MONTH,
            ActivityLevel.ACTIVE_LAST_3_MONTHS,
        ])

    def active_in_last_6_months(self):
        return self.filter(activity_level__in=[
            ActivityLevel.ACTIVE_NEW,
            ActivityLevel.ACTIVE_LAST_DAY,
            ActivityLevel.ACTIVE_LAST_WEEK,
            ActivityLevel.ACTIVE_LAST_MONTH,
            ActivityLevel.ACTIVE_LAST_3_MONTHS,
        ])

    def active_in_last_12_months(self):
        return self.filter(activity_level__in=[
            ActivityLevel.ACTIVE_NEW,
            ActivityLevel.ACTIVE_LAST_DAY,
            ActivityLevel.ACTIVE_LAST_WEEK,
            ActivityLevel.ACTIVE_LAST_MONTH,
            ActivityLevel.ACTIVE_LAST_3_MONTHS,
            ActivityLevel.ACTIVE_LAST_6_MONTHS,
            ActivityLevel.ACTIVE_LAST_12_MONTHS
        ])

    def _active_everyday(self):
        return self.filter(activity_level__in=[
            ActivityLevel.ACTIVE_NEW,
            ActivityLevel.ACTIVE_LAST_DAY,
            ActivityLevel.ACTIVE_LAST_WEEK,
            ActivityLevel.ACTIVE_LAST_MONTH,
            ActivityLevel.ACTIVE_LAST_6_MONTHS,
            ActivityLevel.ACTIVE_UNKNOWN,
        ])

    def _top_platforms(self):
        popular_influencers = Influencer.objects.all().searchable().order_by('-score_popularity_overall')[:5000]
        return self.filter(influencer__in=popular_influencers)

    def _with_signedup_influencers(self):
        cutoff = datetime.utcnow() - timedelta(days=7)
        return self.filter(
            influencer__source__icontains='blogger_signup',
            last_fetched__lt=cutoff,
        )

    def _with_unknown_activity(self):
        cutoff = datetime.utcnow() - timedelta(days=30)
        return self.filter(
            activity_level=ActivityLevel.ACTIVE_UNKNOWN,
            last_fetched__lt=cutoff,
        )

    def _for_3_month_fetching(self):
        cutoff = datetime.utcnow() - timedelta(days=15)
        return self.filter(
            activity_level=ActivityLevel.ACTIVE_LAST_3_MONTHS,
            last_fetched__lt=cutoff
        )

    def _for_6_month_fetching(self):
        cutoff = datetime.utcnow() - timedelta(days=2 * 30)
        return self.filter(
            activity_level=ActivityLevel.ACTIVE_LAST_6_MONTHS,
            last_fetched__lt=cutoff,
        )

    def _for_12_month_fetching(self):
        cutoff = datetime.utcnow() - timedelta(days=4 * 30)
        return self.filter(
            activity_level=ActivityLevel.ACTIVE_LAST_12_MONTHS,
            last_fetched__lt=cutoff,
        )

    def for_infrequent_fetching(self):
        return self.for_daily_fetching().searchable_influencer() & (
            self._with_signedup_influencers() |
            self._with_unknown_activity() |
            self._for_3_month_fetching() |
            self._for_6_month_fetching() |
            self._for_12_month_fetching()
        )

    def _social_update_pending(self):
        cutoff = datetime.utcnow() - timedelta(days=30)

        valid = self.valid().with_fetchable_influencer()
        return valid.filter(Q(last_fetched__isnull=True) | Q(last_fetched__lt=cutoff))

    def gplus_update_pending(self):
        return self._social_update_pending().filter(platform_name='Gplus')

    def bloglovin_update_pending(self):
        return self._social_update_pending().filter(platform_name='Bloglovin')

    def manually_approved(self):
        return self.filter(influencer__source__icontains='manual_')

    def discovered_via_twitter(self):
        return self.filter(influencer__source='discovered_via_twitter')

    def discovered_via_instagram(self):
        return self.filter(influencer__source='discovered_via_instagram')

    def discovered_via_twitter_contains(self):
        return self.filter(influencer__source__contains='discovered_via_twitter')

    def discovered_via_instagram_contains(self):
        return self.filter(influencer__source__contains='discovered_via_instagram')

    def manual_or_from_twitter(self):
        return self.manually_approved() | self.discovered_via_twitter()

    def manual_or_from_social(self):
        return self.manually_approved() | self.discovered_via_twitter() | self.discovered_via_instagram()


    def manual_or_from_social_contains(self):
        return self.manually_approved() | \
               self.discovered_via_twitter_contains() | \
               self.discovered_via_instagram_contains() | \
               self.filter(influencer__source__contains='blogger_signup')

    def url_looks_like_fashion(self):
        return self.filter(
            Q(url__icontains='fashion') |
            Q(url__icontains='beauty') |
            Q(url__icontains='makeup') |
            Q(url__icontains='cooking') |
            Q(url__icontains='health') |
            Q(url__icontains='fitness')
        )

    def for_task_processing(self):
        return self.manually_approved() | self.searchable_influencer()

    def never_fetched(self):
        return self.for_daily_fetching().filter(Q(activity_level__isnull=True) | Q(activity_level='ACTIVE_NEW'))

    def distinct(self, *args, **kwargs):
        '''
        A hack that delists the JSON field from the column list when doing a DISTINCT.

        PG [justifiably] can't compare JSON values and raises an error.

        Note that we do nothing if we got an argument (DISTINCT ON (...) clause) since we
        assume the caller knows what s/he is doing.
        '''
        already_deferred = kwargs.pop('already_deferred', None)
        if not args and not already_deferred:
            return self.defer('detected_influencer_attributes').distinct(*args, already_deferred=True, **kwargs)
        else:
            return super(PlatformQuerySet, self).distinct(*args, **kwargs)


class PlatformManager(InfluencerRelatedManager):

    def get_query_set(self):
        return PlatformQuerySet(self.model, using=self.db)

    get_queryset = get_query_set


class Platform(models.Model, PlatformActivityLevelMixin):

    """
    Each platform objects contains the URL
    (e.g., http://www.facebook.com/atulsingh), name (e.g., Facebook)
    and information associated with that Platform.
    Influencer => points to the unique "person" that has this platform
    """
    SOCIAL_PLATFORMS = [
        'Twitter', 'Facebook', 'Instagram', 'Pinterest', 'Lookbook',
        'Fashiolista', 'Youtube', 'Bloglovin', 'Tumblr', 'Gplus',
    ]
    SOCIAL_PLATFORMS_CRAWLED = [
        'Twitter', 'Facebook', 'Instagram', 'Pinterest', 'Youtube', 'Tumblr',
    ]
    BLOG_PLATFORMS = ['Wordpress', 'Blogspot', 'Custom', 'Squarespace', ]

    ALL_PLATFORMS = SOCIAL_PLATFORMS + BLOG_PLATFORMS

    PROCESSING_STATE_NEW_FOLLOWERS_PLATFORM = 'NEW_FOLLOWERS_PLATFORM'

    PLATFORM_STATE_STARTED = 'STARTED'
    PLATFORM_STATE_DEAD_URL = 'DEAD_URL'
    PLATFORM_STATE_FETCHING_SOCIAL_HANDLES = 'FETCHING_SOCIAL_HANDLES'
    PLATFORM_STATE_NOT_FASHION = 'NOT_FASHION'
    PLATFORM_STATE_ACTIVELY_BLOGGING = 'ACTIVELY_BLOGGING'
    PLATFORM_STATE_NOT_ACTIVELY_BLOGGING = 'NOT_ACTIVELY_BLOGGING'

    ALL_PLATFORM_STATES = [PLATFORM_STATE_STARTED, PLATFORM_STATE_DEAD_URL,
                           PLATFORM_STATE_FETCHING_SOCIAL_HANDLES, PLATFORM_STATE_NOT_FASHION,
                           PLATFORM_STATE_ACTIVELY_BLOGGING, PLATFORM_STATE_NOT_ACTIVELY_BLOGGING]

    influencer = models.ForeignKey(Influencer, blank=True, null=True, default=None, db_index=True)
    platform_name = models.CharField(max_length=1000, blank=True, null=True, default=None, db_index=True)
    validated_handle = models.CharField(max_length=1000, blank=True, null=True, default=None, db_index=True)
    # this is based off of the url to quickly check identical urls for duplicate detection
    username = models.CharField(max_length=1000, blank=True, null=True, default=None, db_index=True)
    description = models.TextField(null=True, blank=True, default=None)
    about = models.TextField(null=True, blank=True, default=None)
    url = models.URLField(max_length=1000, null=True, blank=True, default=None, db_index=True)
    create_date = models.DateTimeField(default=None, blank=True, null=True)
    blogname = models.CharField(max_length=1000, blank=True, null=True, default=None)  # e.g., blog name

    # Detected influencer attributes
    # TODO: drop these attributes - we'll lump everything together in the
    # detected_influencer_attributes JSON field
    detected_name = models.CharField(max_length=1000, blank=True, null=True, default=None)
    detected_demographics_location = models.CharField(max_length=1000, blank=True, null=True, default=None)
    detected_demographics_gender = models.CharField(
        max_length=10, null=True, blank=True, default=None, choices=Influencer.GENDERS)

    detected_influencer_attributes = PGJsonField(null=True, blank=True)

    # locale is provided by Facebook and is encoded as ll_cc (ll=language, cc=country)
    # refer: https://developers.facebook.com/docs/internationalization/
    locale = models.CharField(max_length=32, blank=True, null=True, default=None)

    profile_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None, db_index=True)
    cover_img_url = models.URLField(max_length=1000, blank=True, null=True, default=None, db_index=True)

    # Calculated Stats
    posting_rate = models.FloatField(null=True, blank=True, default=None)

    numposts = models.IntegerField(null=True, blank=True, default=None)
    numsponsoredposts = models.IntegerField(null=True, blank=True, default=None)

    num_followers = models.IntegerField(null=True, blank=True, default=None)
    num_following = models.IntegerField(null=True, blank=True, default=None)

    total_numlikes = models.IntegerField(null=True, blank=True, default=None)
    total_numcomments = models.IntegerField(null=True, blank=True, default=None)
    total_numshares = models.IntegerField(null=True, blank=True, default=None)

    avg_numlikes_overall = models.FloatField(null=True, blank=True, default=None)
    avg_numcomments_overall = models.FloatField(null=True, blank=True, default=None)
    avg_numshares_overall = models.FloatField(null=True, blank=True, default=None)

    avg_num_impressions = models.FloatField(null=True, blank=True, default=None)

    avg_numlikes_sponsored = models.IntegerField(null=True, blank=True, default=None)
    avg_numcomments_sponsored = models.IntegerField(null=True, blank=True, default=None)
    avg_numshares_sponsored = models.IntegerField(null=True, blank=True, default=None)

    avg_numlikes_non_sponsored = models.IntegerField(null=True, blank=True, default=None)
    avg_numcomments_non_sponsored = models.IntegerField(null=True, blank=True, default=None)
    avg_numshares_non_sponsored = models.IntegerField(null=True, blank=True, default=None)

    # these scores are a number between 0-100 to help us rank
    # engagement is based on comments/shares
    # popularity is based on number of followers & following
    score_engagement_overall = models.FloatField(null=True, blank=True, default=None, db_index=True)

    score_popularity_overall = models.FloatField(null=True, blank=True, default=None, db_index=True)
    # these only should could sponsored posts
    score_engagement_sponsored = models.FloatField(null=True, blank=True, default=None)
    # these only should could non-sponsored posts
    score_engagement_non_sponsored = models.FloatField(null=True, blank=True, default=None)

    platform_state = models.CharField(max_length=1000, blank=True, null=True, default=None,
                                      choices=zip(ALL_PLATFORM_STATES, ALL_PLATFORM_STATES))

    activity_level = models.CharField(max_length=1000, blank=True, null=True,
                                      default=None, choices=ActivityLevel._ACTIVITY_LEVELS, db_index=True)
    last_fetched = models.DateTimeField(default=None, blank=True, null=True)
    insert_date = models.DateTimeField(default=datetime.now, blank=True, null=True)

    # Used by fetchers to store state of processing, see PROCESSING_STATE_* class
    # variables for possible values
    processing_state = models.CharField(max_length=1000, blank=True, null=True, default=None)

    api_calls = models.IntegerField(null=False, blank=False, default=0)
    last_api_call = models.DateTimeField(default=None, blank=True, null=True)
    indepth_processed = models.BooleanField(default=False)
    url_not_found = models.NullBooleanField()
    validated = models.NullBooleanField()

    last_modified = models.DateTimeField(auto_now=True, null=True, blank=True)

    content_lang = models.CharField(max_length=64, null=True, blank=True)

    # overrides default fetcher class specification defined in code
    fetcher_class = models.CharField(max_length=64, null=True, blank=True)

    autovalidated = models.NullBooleanField()
    autovalidated_reason = models.CharField(max_length=128, null=True, blank=True)

    feed_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    feed_url_last_updated = models.DateTimeField(default=None, blank=True, null=True)
    only_summary_from_feed = models.NullBooleanField(null=True, blank=True, default=None)

    # moz.com API data fields for blog platforms
    moz_domain_authority = models.FloatField(null=True, blank=True, default=None)
    moz_page_authority = models.FloatField(null=True, blank=True, default=None)
    moz_external_links = models.IntegerField(null=True, blank=True, default=None)

    objects = PlatformManager()

    class Meta:
        unique_together = (('platform_name', 'validated_handle', 'influencer'),)

    #####-----< Classmethods >-----#####
    @classmethod
    def normalize_platform_name(cls, pl_name):
        if pl_name is None:
            return
        # if pl_name is None:
        #     return cls.ALL_PLATFORMS
        if pl_name.lower() in ['blog', 'blogs', 'posts']:
            return cls.BLOG_PLATFORMS
        if pl_name.lower() in ['social']:
            return cls.SOCIAL_PLATFORMS
        return [pl_name]

    @classmethod
    def blog_platforms_for_select(cls):
        return [(plat, plat) for plat in cls.BLOG_PLATFORMS]

    @classmethod
    def calculate_engagement_to_followers_ratio_overall(cls, platform_name):
        if platform_name == 'Blog':
            platform_names = cls.BLOG_PLATFORMS
        elif platform_name == 'Social':
            platform_names = cls.SOCIAL_PLATFORMS
        else:
            platform_names = [platform_name]
        return cls.objects.filter(
            platform_name__in=platform_names, url_not_found=False,
            num_followers__gt=0, avg_numlikes_overall__isnull=False,
        ).aggregate(
            avg_ratio=Avg('avg_numlikes_overall',
                field='100.0 * avg_numlikes_overall/num_followers')
        )['avg_ratio']

    @classmethod
    def engagement_to_followers_ratio_overall(cls, platform_name):
        if platform_name == 'All':
            data = redis_cache.get_many([
                'pef_{}'.format(pl) for pl in cls.SOCIAL_PLATFORMS + ['Blog']])
            return {k[4:]:v for k, v in data.items()}
        else:
            data = redis_cache.get('pef_{}'.format(platform_name))
            if data is None:
                data = cls.calculate_engagement_to_followers_ratio_overall(platform_name)
            return data
    #####-----</ Classmethods >-----#####

    #####-----< Stats Methods >-----#####
    @property
    def calculate_num_followers(self):
        return self.num_followers

    @property
    def calculate_num_following(self):
        return self.num_following

    @property
    def calculate_num_posts(self):
        if not self.id:
            return 0
        return Posts.objects.filter(platform=self).count()

    @property
    def calculate_num_sponsored_posts(self):
        if not self.id:
            return 0
        return Posts.objects.filter(platform=self, is_sponsored=True).count()

    @property
    def calculate_video_views(self):
        posts = Posts.objects.filter(platform=self)
        if not posts:
            return 0
        nc = posts.count()
        return posts.aggregate(Sum('impressions'))['impressions__sum']/nc

    @property
    def calculate_posting_rate(self):
        '''
        #posts / months
        '''
        posts = Posts.objects.filter(platform=self, create_date__isnull=False).order_by('create_date')
        if posts.count() > 1:
            delta = posts[posts.count() - 1].create_date - posts[0].create_date
            if delta.days == 0:
                return 0.0
            return posts.count() * 30.0 / delta.days
        return 0.0

    def calculate_num_comments(self, posts=None):
        """
        @param posts could be a QuerySet that was constructed already (e.g., only containing sponsored posts)
        """
        if self.platform_name in ["Custom", "Blogspot", "Wordpress"]:
            if posts is None:
                posts = self.posts_set.all()
                #interactions = PostInteractions.objects.filter(platform=self)

            db_count = 0
            ext_count = 0

            if self.platform_name in ['Blogspot', 'Custom', 'Wordpress']:
                #comments = interactions
                # Here, we iterate over each post, count the # of comments and ext_num_comments
                # and we want to pick the highest from each post (rather than summing them first and then picking the max)
                a = 0
                b = 0
                m = 0
                for p in posts:
                    cc = PostInteractions.objects.filter(post=p).count()
                    dc = p.ext_num_comments if p.ext_num_comments else 0
                    mc = max(cc, dc)
                    a += cc
                    b += dc
                    m += mc
                db_count = max(a, b, m)

            #ext_count = posts.aggregate(Sum('ext_num_comments'))['ext_num_comments__sum']
            count_through_api = posts.aggregate(Sum('engagement_media_numcomments'))['engagement_media_numcomments__sum']
            log.debug('db_count: %s, ext_count: %s count_through_api: %s', db_count, ext_count, count_through_api)
            return max(db_count, ext_count, count_through_api)
        else:
            if posts:
                return posts.aggregate(Sum('engagement_media_numcomments'))['engagement_media_numcomments__sum']
            else:
                return self.posts_set.aggregate(Sum('engagement_media_numcomments'))['engagement_media_numcomments__sum']


    def calculate_num_likes(self, posts=None):
        """
        Use PostInteractions.count() for Facebook/Blogspot/Wordpress
        For others, this information is saved directly inside the Posts model.
        @param posts could be a QuerySet that was constructed already (e.g., only containing sponsored posts)
        """

        if self.platform_name in ["Custom", "Blogspot", "Wordpress"]:
            return 0
        else:
            if posts:
                return posts.aggregate(Sum('engagement_media_numlikes'))['engagement_media_numlikes__sum']
            else:
                return self.posts_set.aggregate(Sum('engagement_media_numlikes'))['engagement_media_numlikes__sum']

    def calculate_num_shares(self, posts=None):
        """
        Use a platform's specific field
        @param posts could be a QuerySet that was constructed already (e.g., only containing sponsored posts)
        """
        if posts is None:
            posts = self.posts_set.all()

        if self.platform_name == "Facebook":
            return posts.aggregate(Sum('engagement_media_numfbshares'))['engagement_media_numfbshares__sum']
        if self.platform_name == "Pinterest":
            return posts.aggregate(Sum('engagement_media_numrepins'))['engagement_media_numrepins__sum']
        if self.platform_name == "Twitter":
            return posts.aggregate(Sum('engagement_media_numshares'))['engagement_media_numshares__sum']
        return 0

    def calculate_num_impressions(self, posts=None):
        """
        Use a platform's specific field
        @param posts could be a QuerySet that was constructed already (e.g., only containing sponsored posts)
        """
        if posts is None:
            posts = self.posts_set.all()

        if self.platform_name == "Youtube":
            return posts.aggregate(Sum('impressions'))['impressions__sum']
        return 0

    @property
    def alexa_ranking(self):
        ranking = AlexaRankingInfo.objects.filter(platform=self)
        if len(ranking) == 0:
            return None
        return ranking[0]

    @property
    def calculate_engagement_overall(self):
        '''
        sum of comments + likes + shares
        TODO: perhaps we should give more weight to shares and comments than likes?
        '''
        return (
            (self.avg_numshares_overall or 0) +
            (self.avg_numlikes_overall or 0) +
            (self.avg_numcomments_overall or 0)
        )

    @property
    def calculate_engagement_sponsored(self):
        '''
        sum of comments + likes + shares
        TODO: perhaps we should give more weight to shares and comments than likes?
        '''
        return (
            (self.avg_numshares_sponsored or 0) +
            (self.avg_numlikes_sponsored or 0) +
            (self.avg_numcomments_sponsored or 0)
        )

    @property
    def calculate_engagement_non_sponsored(self):
        '''
        sum of comments + likes + shares
        TODO: perhaps we should give more weight to shares and comments than likes?
        '''
        return (
            (self.avg_numshares_non_sponsored or 0) +
            (self.avg_numlikes_non_sponsored or 0) +
            (self.avg_numcomments_non_sponsored or 0)
        )

    @property
    def calculate_popularity(self):
        '''
        if num_following > 0, then we should give more weight to people who have higher number of followers than they follow
        else, it should just be number of followers
        => 5000 followers and 1000 following => popularity = 50,000
        '''
        if self.num_following > 0 and self.num_followers > 0:
            ratio = self.num_followers / self.num_following
            if ratio > 1:
                return self.num_followers * ratio

        return self.num_followers

    #####-----</ Stats Methods >-----#####

    #####-----< Flag Properties >-----#####
    @property
    def is_social(self):
        return self.platform_name_is_social

    @property
    def platform_name_is_social(self):
        return self.platform_name in self.SOCIAL_PLATFORMS

    @property
    def platform_name_is_blog(self):
        return self.platform_name in self.BLOG_PLATFORMS
    #####-----</ Flag Properties >-----#####

    #####-----< Meta Fields >-----#####
    @property
    def email(self):
        return self.influencer.email

    @property
    def css_name(self):
        mapping = {
            'custom': 'social_blog2',
            'twitter': 'social_twitter',
            'pinterest': 'social_pinterest',
            'facebook': 'social_facebook',
            'blogspot': 'social_globe2',
            'bloglovin': 'social_globe2',
            'wordpress': 'social_blog2',
            'tumblr': 'social_blog2',
            'instagram': 'social_instagram2'
        }

        return mapping[self.platform_name.lower()]
    #####-----</ Meta Fields >-----#####

    @property
    def influencer_attributes(self):
        if self.detected_influencer_attributes is None:
            self.detected_influencer_attributes = {}
        return self.detected_influencer_attributes

    @staticmethod
    def is_social_platform(url):
        # return None in case if invalid/empty URL
        if not url:
            return
        url_domain = utils.domain_from_url(url)
        from platformdatafetcher.platformutils import PLATFORM_DOMAIN_REGEX
        for social_domain_regex in PLATFORM_DOMAIN_REGEX.SOCIAL_DOMAINS:
            if social_domain_regex.match(url_domain):
                return True
        return False

    @staticmethod
    def find_duplicates(influencer, blog_url=None, platform_name=None, id=None, any_platform_name=False,
                        exclude_url_not_found_true=True):
        # search for all platforms (with the same platform_name) that have a similar domain handle
        # Determining domain handle:
        # first, check if this is a social platform.
        # if yes, avoid using the domain name as a search token (use only penny from facebook.com/penny)
        # else, use the domain also (pennypincherfashion.com or penny.blogspot.com)
        if platform_name:
            is_social = platform_name in Platform.SOCIAL_PLATFORMS
        else:
            is_social = Platform.is_social_platform(blog_url)
        strip_domain = is_social and platform_name != 'Tumblr'  # Tumblr has token in its domain, excluding it here
        blog_url_main_token = utils.strip_url_of_default_info(blog_url, strip_domain=strip_domain)
        if blog_url_main_token == '':
            print "blog url main token is empty, returning None"
            return None

        if not influencer:
            # Avoid a slow OUTER JOIN if influencer is None
            all_plats = Platform.objects.extra(where=['influencer_id IS NULL'])
        else:
            all_plats = Platform.objects.filter(influencer=influencer)

        all_plats = all_plats.filter(url__icontains=blog_url_main_token)

        if exclude_url_not_found_true:
            all_plats = all_plats.exclude(url_not_found=True)
        if not any_platform_name:
            all_plats = all_plats.filter(platform_name=platform_name)
        dups = []
        for plat in all_plats:
            if id and plat.id == id:
                continue
            token = utils.strip_url_of_default_info(plat.url, strip_domain=strip_domain)
            if token.lower() == blog_url_main_token.lower():
                print "duplicate found this: %r candidate: %r" % (blog_url_main_token, token)
                dups.append(plat)
            else:
                print "[%r] not a duplicate this: [%r, %r, %r] candidate: [%r, %r, %r]" % (platform_name,
                                                                                           blog_url_main_token, blog_url,
                                                                                           id, token, plat.url, plat.id)

        if len(dups) > 0:
            print "Yes, %r has %d duplicates " % (blog_url, len(dups))
        return dups

    def handle_duplicates(self, any_platform_name=False):
        '''
        removes duplicates and returns the current platform object (after moving the posts->platform pointer)
        '''
        assert self.influencer, 'No influencer set but handle_duplicates() called'
        if any_platform_name:
            assert self.platform_name in self.BLOG_PLATFORMS, 'any_platform_name is unsafe for social platforms'
        dups = Platform.find_duplicates(self.influencer, self.url, self.platform_name, self.id,
                                        any_platform_name=any_platform_name)
        if not dups or len(dups) == 0:
            return self
        return self.delete_and_migrate_dups(dups, any_platform_name=any_platform_name)

    def delete_and_migrate_dups(self, dups, any_platform_name):
        if not dups:
            return self
        dup_ids = [p.id for p in dups]
        assert self.id not in dup_ids

        # now migrate all posts->platform pointer to self
        all_posts = Posts.objects.filter(platform__in=dups).order_by('url').distinct('url')
        skipped_posts = 0
        for post in all_posts:
            if Posts.objects.filter(platform=self, url=post.url).exists():
                skipped_posts += 1
                continue
            post.platform = self
            post.save()
        print "Skipped %d duplicate posts" % skipped_posts

        # migrate PopularityTimeSeries
        all_ptss = PopularityTimeSeries.objects.filter(platform__in=dups).order_by('id')
        for pts in all_ptss:
            pts.platform = self
            pts.save()

        # delete all platforms except self
        plats_to_delete = Platform.objects.filter(id__in=dup_ids)
        infs = set([plat.influencer for plat in plats_to_delete])
        plats_to_delete.update(url_not_found=True, validated_handle=None)
        if len(infs) > 1:
            print "we have %d influencers for the duplicates corresponding to this %s" % (len(infs), self)

        if len(infs) == 1:
            target = infs.pop()
            if not self.influencer:
                self.influencer = target
            elif target.id != self.influencer.id:
                self.influencer = target
            else:
                pass
            self.save()

        # check to make sure there are no more duplicates left
        assert len(self.find_duplicates(
            self.influencer, self.url, self.platform_name, self.id, any_platform_name=any_platform_name)) == 0

        print "Done removing duplicates for %r, remaining platform: %r" % (self.url, self)
        return self

    def set_platform_name(self):
        """Sets self.platform_name to Wordpress/Blogger/Tumblr (if it can be detected).
        Possibly corrects self.url (to include 'www.' prefix).
        It potentially calls API so can be slow/result in exceptions.
        """
        # Circular module deps
        from platformdatafetcher import fetcher
        name, corrected_url = fetcher.try_detect_platform_name(self.url)
        if name:
            self.platform_name = name
            print "Saved name %s " % self.platform_name

        if corrected_url and self.url != corrected_url:
            self.url = corrected_url
            print "Corrected url from %s to %s " % (self.url, corrected_url)
        self.save()

    def feed_url_up_to_date(self):
        return (self.feed_url_last_updated is not None and
                self.feed_url_last_updated > datetime.utcnow() - timedelta(days=7))

    def set_feed_url(self, feed_url):
        if feed_url:
            self.feed_url = feed_url
            self.feed_url_last_updated = datetime.utcnow()
            self.save()

    def inc_api_calls(self, status_code=None, status_msg=None):
        # TODO: temporarily disabled - troubleshooting DB performance issues
        return

        if not self.id:
            return
        self_q = Platform.objects.filter(id=self.id)
        updated = self_q.update(api_calls=F('api_calls') + 1, last_api_call=datetime.now())
        assert updated == 1

        if self.platform_name:
            calls_kwargs = {
                'platform_name': self.platform_name,
                'calls_date': date.today(),
                'calls_hour': datetime.now().hour,
                'status_code': status_code,
                'status_msg': status_msg,
            }
            calls_q = PlatformApiCalls.objects.filter(**calls_kwargs)
            if calls_q.exists():
                calls_row = calls_q[0]
            else:
                # Need to create a new row, but must be aware of a race
                # condition - other processes can execute this code
                # in parallel.
                try:
                    calls_row = PlatformApiCalls.objects.create(**calls_kwargs)
                except IntegrityError:
                    calls_q = PlatformApiCalls.objects.filter(**calls_kwargs)
                    assert calls_q.exists(), 'Unique constraint prevented from inserting a new row but ' \
                        'a row still not found'
                    calls_row = calls_q[0]
            calls_row.inc()

    @staticmethod
    def get_platform(url_segment, platform_name):
        if url_segment == '' or url_segment is None:
            return None
        return Platform.objects.filter(url__contains=url_segment, platform_name=platform_name)

    def calculate_avg_num_interactions(self, type_post='all', type_interaction='comment'):
        '''
        type_post:
                    'all' => calculate average over all types of posts
                    'non_sponsored' => calculate average over non_sponsored posts
                    'sponsored' => calculate average over sponsored posts

        type_interaction:
                    'comment'
                    'like'
                    'share'
        '''
        try:
            # TODO: remove when we fix the sponsored/non_sponsored performance problem
            if type_post is not 'all':
                return 0.0

            posts = self.posts_set.all()

            PEEK_INTO_HISTORY_START = {'Facebook': 35,
                                       'Instagram': 35,
                                       'Twitter': 35,
                                       'Blogspot': 35,
                                       'Wordpress': 35,
                                       'Tumblr': 35,
                                       'Custom': 35,
                                       'Youtube': 35,
                                       'Pinterest': 90,
                                       'Gplus': 35,
                                       }
            PEEK_INTO_HISTORY_END = {'Facebook': 7,
                                    'Instagram': 7,
                                    'Twitter': 7,
                                    'Blogspot': 7,
                                    'Wordpress': 7,
                                    'Tumblr': 7,
                                    'Custom': 7,
                                    'Youtube': 7,
                                    'Pinterest': 30,
                                    'Gplus': 7,
                                    }

            import datetime
            t_now = datetime.datetime.today()
            st = t_now - datetime.timedelta(days=PEEK_INTO_HISTORY_START[self.platform_name])
            et = t_now - datetime.timedelta(days=PEEK_INTO_HISTORY_END[self.platform_name])

            #now, find posts between this range
            if self.platform_name == 'Pinterest':
                posts = posts.filter(inserted_datetime__gte=st, inserted_datetime__lt=et)
            else:
                posts = posts.filter(create_date__gte=st, create_date__lt=et)

            if posts.count() < 20:
                posts = self.posts_set.all()

            if type_post == 'sponsored':
                posts = posts.filter(is_sponsored=True)
            elif type_post == 'non_sponsored':
                posts = posts.filter(is_sponsored=False)

            cached_attribute = '_post_count_{}'.format(type_post)
            if not hasattr(self, cached_attribute):
                setattr(self, cached_attribute, posts.count())

            post_count = getattr(self, cached_attribute)

            if type_interaction == 'comment':
                count = self.calculate_num_comments(posts)
            elif type_interaction == 'like':
                count = self.calculate_num_likes(posts)
            elif type_interaction == 'share':
                count = self.calculate_num_shares(posts)
            elif type_interaction == 'impression':
                count = self.calculate_num_impressions(posts)

            return count * 1.0 / post_count if count else 0.0
        except ZeroDivisionError:
            return 0.0


    def set_username(self):
        """ This method just fetches the username from the url.
        This is useful for detecting duplicate urls.
        """
        from platformdatafetcher import platformutils
        self.username = platformutils.username_from_platform_url(self.url)
        if self.username:
            self.username = self.username.lower()
        self.save()

    #####-----< Denormalization >-----#####
    def _do_denormalize(self):
        """This is a private method called by :class:`Influencer`"""

        self.numposts = self.calculate_num_posts

        self.numsponsoredposts = self.calculate_num_sponsored_posts

        self.total_numcomments = self.calculate_num_comments()
        if self.platform_name == "Facebook":
            # for Facebook, num_followers is saved in total_numlikes
            # so we shouldn't over-write it and save it in num_f911806ollowers
            self.num_followers = self.total_numlikes
        else:
            self.total_numlikes = self.calculate_num_likes()
        self.total_numshares = self.calculate_num_shares()

        self.avg_numcomments_overall = self.calculate_avg_num_interactions(type_interaction='comment')
        self.avg_numlikes_overall = self.calculate_avg_num_interactions(type_interaction='like')
        self.avg_numshares_overall = self.calculate_avg_num_interactions(type_interaction='share')
        self.avg_num_impressions = self.calculate_avg_num_interactions(type_interaction='impression')

        # TODO: disabled due to performance problems. This needs to be rewritten
        ### self.avg_numcomments_sponsored = self.calculate_avg_num_interactions(type_post='sponsored', type_interaction='comment')
        ### self.avg_numlikes_sponsored = self.calculate_avg_num_interactions(type_post='sponsored', type_interaction='like')
        ### self.avg_numshares_sponsored = self.calculate_avg_num_interactions(type_post='sponsored', type_interaction='share')

        ### self.avg_numcomments_non_sponsored = self.calculate_avg_num_interactions(type_post='non_sponsored', type_interaction='comment')
        ### self.avg_numlikes_non_sponsored = self.calculate_avg_num_interactions(type_post='non_sponsored', type_interaction='like')
        ### self.avg_numshares_non_sponsored = self.calculate_avg_num_interactions(type_post='non_sponsored', type_interaction='share')

        self.posting_rate = self.calculate_posting_rate

        self.score_popularity = self.calculate_popularity
        self.score_engagement_overall = self.calculate_engagement_overall
        self.score_engagement_sponsored = self.calculate_engagement_sponsored
        self.score_engagement_non_sponsored = self.calculate_engagement_non_sponsored

        if self.platform_name in Platform.SOCIAL_PLATFORMS_CRAWLED and not self.username:
            self.set_username()

        self.save()

    def save(self, *args, **kwargs):
        bypass_checks = kwargs.pop('bypass_checks', None)
        force_checks = kwargs.pop('force_checks', None)
        if self.id is not None and not force_checks:
            log.debug('The platform is already in the DB, performing normal save()')
            # If the platform is already in the DB, we do normal saving
            return models.Model.save(self, *args, **kwargs)
        if bypass_checks:
            log.warn('Bypassing duplicate checks')
            return models.Model.save(self, *args, **kwargs)
        dups = Platform.find_duplicates(self.influencer, self.url, self.platform_name)
        if dups:
            log.warn('Platform dups detection: not inserting %r because of duplicates: %r', self, dups)
            return
        log.warn('Platform dups detection: inserting %r, no duplicates', self)
        return models.Model.save(self, *args, **kwargs)

    def last_execution(self, operation, max_days=None):
        """Return last execution time of an operation in last max_days (can be ``None`` for no time limit),
        ``None`` if there was no such execution.
        """
        q = self.platformdataop_set.filter(operation=operation)
        if max_days is not None:
            q = q.filter(started__gte=datetime.now() - timedelta(days=max_days))
        q = q.order_by('-started')
        if not q.exists():
            return None
        return q[0].started

    def append_to_url_field(self, influencer=None, clear=False):
        if influencer is None:
            influencer = self.influencer
        if influencer is None:
            return False
        if self.platform_name not in Influencer.platform_name_to_field:
            return False
        field_name = Influencer.platform_name_to_field[self.platform_name]
        if clear:
            setattr(influencer, field_name, '')
        if influencer.contains_url(field_name, self.url):
            return False
        influencer.append_url(field_name, self.url)
        return True

    def get_last_post_date(self):
        """
        Fall back to inserted_datetime if post create_date is NULL
        """
        if self.platform_name == 'Pinterest':
            posts = self.posts_set.all().exclude(inserted_datetime__isnull=True).order_by('-inserted_datetime')
            if posts:
                return posts[0].inserted_datetime
        else:
            posts = self.posts_set.all().exclude(create_date__isnull=True).order_by('-create_date')
            if posts:
                return posts[0].create_date

        return None


        ### This below function is buggy, so using a simpler method above
        ### Example: <Platform: id:125095 inf_id:33572 Blogspot u'http://www.pennypincherfashion.com/'>
        ### This returns None
        posts_meta = Posts._meta
        posts_table = posts_meta.db_table
        create_date_column = posts_meta.get_field_by_name('create_date')[0].column

        query = '''
        SELECT {create_date} AS post_date
        FROM {posts}
        WHERE platform_id = %s
        ORDER BY post_date DESC
        LIMIT 1
        '''.format(
            create_date=create_date_column, posts=posts_table)

        connection = db_util.connection_for_reading()
        cursor = connection.cursor()
        cursor.execute(query, [self.pk])
        result = cursor.fetchall()

        if len(result):
            return result[0][0]
        else:
            return None

    def get_failed_recent_fetches(self):
        platformdataop_meta = PlatformDataOp._meta
        platformdataop_table = platformdataop_meta.db_table

        sql = '''
        SELECT count(DISTINCT started::date) as fail_days
        FROM {platformdataop}
        WHERE error_tb IS NOT NULL AND started > now() - '1 week'::interval AND platform_id = %s
        '''.format(platformdataop=platformdataop_table)

        connection = db_util.connection_for_reading()
        cursor = connection.cursor()
        cursor.execute(sql, [self.pk])
        rows = cursor.fetchall()
        fail_days = rows[0][0]

        return fail_days

    def __unicode__(self):
        return 'id:{self.id} inf_id:{self.influencer_id} {self.platform_name} {self.url!r}'.\
            format(self=self)

    def refetch_moz_data(self, moz_access_id=None, moz_secret_key=None):
        if self.platform_name in self.BLOG_PLATFORMS:
            try:
                # initializing moz API handler
                if moz_access_id is not None and moz_secret_key is not None:
                    l = lsapi(moz_access_id, moz_secret_key)
                else:
                    l = lsapi(settings.MOZ_ACCESS_ID, settings.MOZ_SECRET_KEY)

                # fetching response from moz with required values
                response = l.urlMetrics(
                    [self.url, ],
                    lsapi.UMCols.domainAuthority | lsapi.UMCols.pageAuthority | lsapi.UMCols.externalEquityLinks  #|  lsapi.UMCols.externalLinks
                )

                if len(response) > 0:
                    # updating data for Platform
                    changed = False

                    try:
                        # Domain Authority
                        if response[0].get('pda') is not None:
                            self.moz_domain_authority = response[0].get('pda')
                            changed = True
                    except KeyError as ke:
                        log.error(ke)

                    try:
                        # Page Authority
                        if response[0].get('upa') is not None:
                            self.moz_page_authority = response[0].get('upa')
                            changed = True
                    except KeyError as ke:
                        log.error(ke)

                    try:
                        # Number of external links
                        if response[0].get('ueid') is not None:
                            self.moz_external_links = response[0].get('ueid')
                            changed = True
                    except KeyError as ke:
                        log.error(ke)

                    if changed:
                        self.save()
                        if self.influencer is not None:
                            self.influencer.last_modified = datetime.now()
                            self.influencer.save()

            except lsapiException as e:
                log.error(e)
        else:
            log.warn('Platform %s is not a blog blatform, it is %s' % (self.id, self.platform_name))

class PlatformDataOp(models.Model):
    platform = models.ForeignKey(Platform, null=True, db_index=True)
    influencer = models.ForeignKey(Influencer, null=True, db_index=True)
    product_model = models.ForeignKey(ProductModel, null=True)
    post = models.ForeignKey('Posts', null=True)
    follower = models.ForeignKey('Follower', null=True)
    post_interaction = models.ForeignKey('PostInteractions', null=True)
    brand = models.ForeignKey('Brands', null=True)
    # If an operation is made not for a platform or an influencer,
    # in this field we can store custom text specifying an object
    spec_custom = models.CharField(max_length=1024, db_index=True, null=True)

    operation = models.CharField(max_length=1024, db_index=True)

    # started time is automatically filled to 'now'
    started = models.DateTimeField(auto_now_add=True, db_index=True)
    # finish time should be filled manually
    finished = models.DateTimeField(null=True, db_index=True)

    # exception/error class and message
    error_msg = models.TextField(null=True)
    # exception traceback
    error_tb = models.TextField(null=True)

    # server_ip and process_pid are filled automatically
    server_ip = models.CharField(max_length=128, default=utils.get_ip_address)
    process_pid = models.IntegerField(null=True, default=os.getpid)

    # this field can be used to store custom data in JSON format
    data_json = models.TextField(null=True)

    def duration(self):
        if self.started is None or self.finished is None:
            return None
        return (self.finished - self.started).total_seconds()

    def __unicode__(self):
        spec = repr(self.platform or self.influencer or self.product_model or self.post or
                    self.follower or self.post_interaction or self.brand or self.spec_custom or '?')
        return u'{operation} {spec} started:{started} finished:{finished}'.format(
            operation=self.operation, spec=spec, started=self.started, finished=self.finished)


class OpDict(models.Model):

    """Maps operation name from PlatformDataOp to integer value (``id`` implicit column)."""
    operation = models.CharField(max_length=1024, unique=True)


class PdoLatest(models.Model):
    platform = models.ForeignKey(Platform, null=True)
    influencer = models.ForeignKey(Influencer, null=True)
    product_model = models.ForeignKey(ProductModel, null=True)
    follower = models.ForeignKey('Follower', null=True)
    brand = models.ForeignKey('Brands', null=True)

    operation_id = models.IntegerField(db_index=True)
    latest_started = models.DateTimeField()

    @staticmethod
    def save_latest(operation, started_dt, platform=None, influencer=None, product_model=None, post=None,
                    follower=None, post_interaction=None, brand=None):
        op_dict_entry, _ = OpDict.objects.get_or_create(operation=operation)
        op_id = op_dict_entry.id

        m_kw = {}
        if platform is not None:
            m_kw['platform'] = platform
        if influencer is not None:
            m_kw['influencer'] = influencer
        if product_model is not None:
            m_kw['product_model'] = product_model
        if post is not None:
            m_kw['post'] = post
        if follower is not None:
            m_kw['follower'] = follower
        if post_interaction is not None:
            m_kw['post_interaction'] = post_interaction
        if brand is not None:
            m_kw['brand'] = brand

        pdo_latest = utils.get_first_or_instantiate(PdoLatest.objects, operation_id=op_id, **m_kw)
        pdo_latest.latest_started = started_dt
        pdo_latest.save()


class PlatformApiCalls(models.Model):
    platform_name = models.CharField(max_length=1000, blank=True, null=True, default=None)
    calls_date = models.DateField()
    calls_hour = models.IntegerField()
    status_code = models.IntegerField(null=True, blank=True, default=None)
    status_msg = models.CharField(max_length=1000, blank=True, null=True, default=None)
    num_calls = models.IntegerField(default=0)

    class Meta:
        unique_together = (('platform_name', 'calls_date', 'calls_hour', 'status_code', 'status_msg'),)

    def inc(self):
        if not self.id:
            return
        self_q = PlatformApiCalls.objects.filter(id=self.id)
        self_q.update(num_calls=F('num_calls') + 1)


class CategoryQuerySet(models.query.QuerySet):
    pass


class CategoryManager(models.Manager):

    def get_query_set(self):
        # Don't load keywords by default. Expected to be large.
        return CategoryQuerySet(self.model, using=self.db).defer('keywords')


class Category(models.Model):
    name = models.TextField(null=False, blank=False)
    keywords = TextArrayField(null=True, blank=False)
    match_threshold = models.IntegerField(null=True, blank=True, default=None)

    objects = CategoryManager()

    def __unicode__(self):
        return u'id={}, name={}'.format(self.pk, self.name)


class PostsQuerySet(TimeSeriesMixin, InfluencerRelatedQuerySet):
    pass


class PostsManager(InfluencerRelatedManager):

    def get_query_set(self):
        return PostsQuerySet(self.model, using=self.db)

    get_queryset = get_query_set


class Posts(models.Model):
    PLATFORMS_ON_FEED = Platform.BLOG_PLATFORMS + ['Instagram']

    ##--< Crucial Creation Fields >--##
    influencer = models.ForeignKey(Influencer, db_index=True)
    platform = models.ForeignKey(Platform, null=True, blank=True, default=None, db_index=True)
    content = models.TextField(null=True, blank=True, default=None)
    title = models.CharField(max_length=1000, blank=True, null=True, default=None)
    url = models.URLField(max_length=1000, null=True, blank=True, default=None, db_index=True)

    ##--< Fields Set By Denormalization >--##
    is_sponsored = models.NullBooleanField(null=True, blank=True, default=None)
    product_urls = models.TextField(null=True, blank=True, default=None)
    products_import_completed = models.NullBooleanField(null=True, blank=True, default=None)
    categorization_complete = models.NullBooleanField(null=True, blank=True, default=None)
    platform_name = models.CharField(max_length=32, blank=True, null=True, default=None, db_index=True)
    show_on_search = models.NullBooleanField(default=None, db_index=False)

    # this stores information whether we tried all commentors of this post for finding new influencers
    commentor_import_completed = models.NullBooleanField(null=True, blank=True, default=None)
    # stores comma-separated list of brand names that represent the products contained in this post
    brand_tags = models.CharField(max_length=10000, null=True, blank=True, default=None)

    ##--< Other Fields >--##
    api_id = models.CharField(max_length=1000, null=True, blank=True, default=None)
    location = models.CharField(max_length=1000, blank=True, null=True, default=None)
    fetch_manually_completed = models.NullBooleanField(null=True, blank=True, default=None)

    ##--< Datetime Fields >--##
    create_date = models.DateTimeField(default=None, blank=True, null=True, db_index=True)
    inserted_datetime = models.DateTimeField(default=datetime.now)

    # these are engagement specific to that platform
    # e.g., for a given facebook post, how many likes/comments/shares we got on the same platform
    engagement_media_numlikes = models.IntegerField(null=True, blank=True, default=None)
    engagement_media_numcomments = models.IntegerField(null=True, blank=True, default=None)
    engagement_media_numshares = models.IntegerField(null=True, blank=True, default=None)
    # these capture engagement for a blog post on facebook/twitter/pinterest
    engagement_media_numretweets = models.IntegerField(null=True, blank=True, default=None)
    engagement_media_numfbshares = models.IntegerField(null=True, blank=True, default=None)
    engagement_media_numrepins = models.IntegerField(null=True, blank=True, default=None)

    ##--< Admin Fields >--##
    admin_categorized = models.BooleanField(default=False)
    show_on_feed = models.BooleanField(default=False)
    problems = models.CharField(max_length=100, blank=True, null=True)

    has_comments = models.BooleanField(default=False)
    has_products = models.BooleanField(default=False)
    denorm_num_comments = models.IntegerField(null=True, blank=True, default=None)
    # number of comments got from external place (comments are not in PostInteractions)
    ext_num_comments = models.IntegerField(default=0, null=True, blank=True)
    eligible_images_count = models.IntegerField(default=0, null=True)
    post_image = models.URLField(null=True, blank=True, db_index=True)
    post_image_width = models.IntegerField(default=None, null=True, blank=True)
    post_image_height = models.IntegerField(default=None, null=True, blank=True)

    pin_source = models.CharField(max_length=1000, null=True, blank=True)
    pinned_by = models.CharField(max_length=1000, null=True, blank=True)

    impressions = models.IntegerField(null=True, blank=True, default=None)

    # comma separated lists
    hashtags = models.CharField(max_length=10000, null=True, blank=True, default=None)
    mentions = models.CharField(max_length=10000, null=True, blank=True, default=None)

    last_modified = models.DateTimeField(auto_now=True, null=True, blank=True)

    products_json = models.TextField(null=True, blank=True, default=None)

    categories = models.ManyToManyField(Category, through='PostCategory', related_name='categories+')

    objects = PostsManager()

    #####-----< Classmethods >-----#####
    @classmethod
    def to_show_on_feed(cls, to_show=0, for_user=None, admin=False):
        """
        get the Posts that we should show on the inspiration feed (is_trendsetter=True, platform__platform_name__in="twitter, instagram")
        @param to_show - the maximum number of items to fetch for the feed
        @para for_user - set when only showing posts shelved by a user
        @param admin - if True, we want to see those posts that should be categorized
        @return list of tuples containing the various types of posts to show on the feed if for_user and unzipped not set,
        else return a QuerySet of Posts
        """
        to_show = to_show or cls.objects.count()

        all_posts = cls.objects.filter(influencer__shelf_user__userprofile__is_trendsetter=True,
                                       influencer__relevant_to_fashion=True,
                                       platform__platform_name__in=cls.PLATFORMS_ON_FEED).select_related('platform', 'influencer__shelf_user__userprofile').order_by('-create_date')
        all_posts = all_posts.filter(admin_categorized=False) if admin else all_posts.filter(
            admin_categorized=True, show_on_feed=True)

        if admin:
            return all_posts
        if for_user:
            return all_posts.filter(id__in=[psm.post.id for psm in PostShelfMap.objects.filter(user_prof=for_user).select_related('post')])

        #twitter_posts = all_posts.filter(platform__platform_name='Twitter')[:to_show]
        instagram_posts = all_posts.filter(platform__platform_name='Instagram')[:to_show]
        blog_posts = all_posts.filter(platform__platform_name__in=['Blogspot', 'Wordpress'])[:to_show]
        return itertools.zip_longest(instagram_posts, blog_posts, fillvalue=None)
    #####-----</ Classmethods >-----#####

    @property
    def analytics(self):
        return PostAnalytics.objects.from_source(self)

    #####-----< Basic Metadata >----#####
    @property
    def post_type(self):
        """
        return the type of post this is (one of 'social' or 'blog')
        """
        platform_name = self.platform.platform_name
        return 'blog' if platform_name in Platform.BLOG_PLATFORMS else 'social'

    @property
    def added_datetime(self):
        """
        just so that we have a one to one mapping for the 'create_date' field to the PMSM 'added_datetime' field
        """
        return self.create_date
    #####-----</ Basic Metadata >----#####

    def product_urls(self, exclude_domains_from_urls=None):
        if exclude_domains_from_urls:
            final_exclude_domains_from_urls = exclude_domains_from_urls + [self.url]
        else:
            final_exclude_domains_from_urls = [self.url]
        # print "final_exclude_domains_from_urls %s" % final_exclude_domains_from_urls
        return contentfiltering.find_important_urls(self.content, final_exclude_domains_from_urls)

    def test_and_set_sponsored_flag(self):
        '''
        we check if the post contains keywords to reflect it's a sponsored post
        '''
        TITLE_KEYWORDS = ['giveaway', 'sponsored']
        CONTENT_KEYWORDS = TITLE_KEYWORDS + ['c/o', 'courtesy of']

        for kw in TITLE_KEYWORDS:
            if self.title and kw in self.title.lower():
                self.is_sponsored = True

        for kw in CONTENT_KEYWORDS:
            if self.content and kw in self.content.lower():
                self.is_sponsored = True

        self.is_sponsored = bool(self.is_sponsored)
        self.save()

    def find_eligible_images(self, stop_after_first=False):
        urls = []
        for url in self.img_urls:
            log.debug('eligible image: %r' % url)
            try:
                dims = get_dims_for_url(url)
            except:
                log.error('get_dims_for_url failed for %r' % url)
                continue
            log.debug('with dimensions: {}'.format(dims))
            if dims and dims[0] > 200 and dims[1] > 200 and dims[0] < dims[1] * 3:
                urls.append(url)
            if stop_after_first and len(urls) > 0:
                break
        return urls

    def calc_eligible_images_count(self):
        return len(self.find_eligible_images())

    @property
    def pmsms_for_self(self):
        """
        get all ProductModelShelfMap instances that this Post contains
        @return QuerySet of ProductModelShelfMap
        """
        return ProductModelShelfMap.distinct_product_model(ProductModelShelfMap.objects.filter(post=self))

    @property
    def img_urls(self):
        from debra import search_helpers
        content, images = search_helpers.tagStripper(self.content)
        return images
        # return contentfiltering.find_important_urls(self.content, [], exclude_imgs=False, include_only_imgs=True)

    @property
    def num_comments(self):
        return PostInteractions.objects.filter(post=self).count()

    @property
    def post_img(self):

        if self.post_image is not None:
            return self.post_image
        return '/mymedia/site_folder/images/global/missing_image.jpg'
        # try:
        #    post_image = self.find_eligible_images(stop_after_first=True)[0]
        # except IndexError:
        #    post_image = '/mymedia/site_folder/images/global/missing_image.jpg'
        # return post_image

    def get_product_json(self, skip_save=False, recalculate=False):
        from debra.templatetags.custom_filters import best_pic_for_product, remove_dot_com

        if not self.products_json or recalculate:
            prods_only = ['id', 'post__id', 'img_url', 'img_url_feed_view', 'user_prof__id']
            prods_qs = ProductModelShelfMap.objects.select_related(
                'post', 'user_prof', 'product_model', 'product_model__brand')
            prods_qs = prods_qs.filter(post=self)
            prods_qs = prods_qs.distinct('product_model__img_url')
            prods_qs = prods_qs.only(*prods_only)
            unique_products_pics = set()
            products = []
            for product in prods_qs:
                pic = best_pic_for_product(product)
                if not pic:
                    continue
                if pic in unique_products_pics:
                    continue
                unique_products_pics.add(pic)
                product_data = {
                    'url': product.affiliate_prod_link or product.product_model.prod_url,
                    'prod_name': product.product_model.name,
                    'designer_name': product.product_model.designer_name,
                    'brand_name': remove_dot_com(product.product_model.brand.name),
                    'brand_domain': product.product_model.brand.domain_name,
                    'pic': pic
                }
                products.append(product_data)
            self.products_json = json.dumps(products)
            if not skip_save:
                self.save()
        return json.loads(self.products_json)

    def __unicode__(self):
        return u'id={self.id} platform={platform_url}, title={self.title}, url={self.url}, ' \
            'create_date={self.create_date}'.format(self=self,
                                                    platform_url=self.platform.url if self.platform else None)

    #####-----< Denormalize >-----#####
    def denormalize(self):
        self.test_and_set_sponsored_flag()
        self.has_products = self.productmodelshelfmap_set.count() > 0

        num_comments_from_db = self.postinteractions_set.count()
        num_comments_ext = self.ext_num_comments or 0
        self.denorm_num_comments = max(num_comments_from_db, num_comments_ext)
        self.save()

        self.eligible_images_count = self.calc_eligible_images_count()
        self.platform_name = self.platform.platform_name
        # self.get_product_json(skip_save=False)
        self.save()

@receiver(post_delete, sender=Posts)
def delete_post_from_es(sender, instance, **kwargs):
    """
    Deletes data of post from ElasticSearch index after it is deleted from DB.
    :param sender:
    :param instance:
    :param using:
    :return:
    """
    endpoint = "/%s/post/%s" % (ELASTICSEARCH_INDEX, instance.id)
    url = ELASTICSEARCH_URL

    make_es_delete_request(es_url=url + endpoint)
    # requests.delete(url + endpoint,
    #                 auth=HTTPBasicAuth(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
    #                 )


# this stores the products obtained after importing items from a post
# useful for influencers who have not yet joined our platform
# and when this influencer joins our platform, we can quickly import these items into her
# posts rather than running the entire scraping at that time
class ProductsInPosts(models.Model):
    post = models.ForeignKey(Posts)
    prod = models.ForeignKey(ProductModel, null=True, blank=True, default=None)
    orig_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    is_affiliate_link = models.BooleanField(default=False)
    is_valid_product = models.BooleanField(default=False)


class PostCategory(models.Model):

    '''
    Stores the categories determined for posts after running the categorization algorithms
    '''
    post = models.ForeignKey(Posts, null=False, blank=False, db_index=True)
    category = models.ForeignKey(Category, null=False, blank=False, db_index=True)
    # Store category match details for debug purposes and future reference
    match_data = PGJsonField(null=True, blank=True)


# this captures interactions/engagement per post
class PostInteractions(models.Model):
    ##--< Required Fields >--##
    # TODO: remove nullability and index
    platform = models.ForeignKey(Platform, null=True, blank=True, db_index=True)

    post = models.ForeignKey(Posts, db_index=True)
    follower = models.ForeignKey('Follower', null=True, blank=True, default=None)
    content = models.CharField(max_length=10000, null=True, blank=True, default=None)

    ##--< Interaction Type Flag >--##
    if_liked = models.NullBooleanField(null=True, blank=True, default=None)
    if_shared = models.NullBooleanField(null=True, blank=True, default=None)
    if_commented = models.NullBooleanField(null=True, blank=True, default=None)

    ##--< Other Fields >--##
    api_id = models.CharField(max_length=1000, null=True, blank=True, default=None)
    numlikes = models.IntegerField(null=True, blank=True, default=None)

    ##--< Datetime Fields >--##
    create_date = models.DateTimeField()
    added_datetime = models.DateTimeField(default=datetime.now, db_index=True)

    def __unicode__(self):
        return u'len(content)={lc} post={self.post}, follower={self.follower}'.\
            format(self=self, lc=len(self.content) if self.content is not None else -1)


class LinkFromPlatform(models.Model):
    source_platform = models.ForeignKey(Platform, related_name='sourcelink_set')
    dest_platform = models.ForeignKey(Platform, null=True, related_name='destlink_set')
    dest_url = models.CharField(max_length=1000, null=True)
    normalized_dest_url = models.CharField(max_length=1000, null=True, db_index=True)
    link_text = models.CharField(max_length=1000, null=True)
    kind = models.CharField(max_length=100, null=True)

    class Meta:
        unique_together = (('source_platform', 'dest_url', 'kind'),)

    def __unicode__(self):
        return u'id=%r source_platform.url=%r, dest=%r (%r), kind=%r' % \
            (self.id,
             self.source_platform.url if self.source_platform is not None else None,
             self.normalized_dest_url,
             self.dest_platform.url if self.dest_platform is not None else self.dest_url,
             self.kind)


class LinkFromPost(models.Model):
    source_post = models.ForeignKey(Posts, related_name='sourcelink_set')
    dest_post = models.ForeignKey(Posts, related_name='destlink_set')

    def __unicode__(self):
        return 'link %r => %r' % (self.source_post, self.dest_post)


class SponsorshipInfo(models.Model):
    post = models.ForeignKey(Posts)
    widget_type = models.CharField(max_length=1000, null=True)
    title = models.CharField(max_length=1000, null=True)
    content = models.CharField(max_length=10000, null=True, blank=True, default=None)
    url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    base_xpath = models.CharField(max_length=1000, null=True, blank=True, default=None)
    widget_id = models.CharField(max_length=1000, null=True, blank=True, default=None)
    total_entries = models.IntegerField(null=True)
    max_entry_value = models.IntegerField(null=True)
    is_running = models.NullBooleanField()
    sidebar = models.NullBooleanField()
    added_datetime = models.DateTimeField(default=datetime.now, db_index=True)

    def __unicode__(self):
        return 'id={self.id}, post_id={self.post_id}, title={self.title}, content={self.content}, ' \
            'url={self.url}, total_entries={self.total_entries}, ' \
            'max_entry_value={self.max_entry_value}, is_running={self.is_running}'.format(self=self)


class Follower(models.Model):
    firstname = models.CharField(max_length=1000, null=True, blank=True, default=None, db_index=True)
    lastname = models.CharField(max_length=1000, null=True, blank=True, default=None, db_index=True)
    email = models.EmailField(null=True, blank=True, default=None, db_index=True)
    url = models.URLField(max_length=1000, null=True, blank=True, default=None, db_index=True)
    shelf_user = models.ForeignKey(User, null=True, blank=True, default=None)
    location = models.CharField(max_length=1000, null=True, blank=True, default=None)
    # ADDED:
    demographics_gender = models.CharField(max_length=10, null=True, blank=True, default=None)
    demographics_fbpic = models.CharField(max_length=200, null=True, blank=True, default=None)
    demographics_fbid = models.CharField(max_length=200, null=True, blank=True, default=None)
    demographics_age = models.IntegerField(max_length=200, null=True, blank=True, default=None)
    follower_recurringscore = models.FloatField(null=True, blank=True, default=None)
    is_blogger = models.NullBooleanField(null=True, blank=True, default=None)

    # if a follower is also an influencer, this points to the proper Influencer model
    influencer = models.ForeignKey(Influencer, null=True, blank=True, default=None)

    num_interactions = models.IntegerField(null=True, blank=True, default=None)

    def __unicode__(self):
        return u'{self.id} firstname: {self.firstname}, lastname: {self.lastname}'.format(self=self)


class PlatformFollower(models.Model):
    follower = models.ForeignKey(Follower, null=True, blank=True, default=None)
    platform = models.ForeignKey(Platform, null=True, blank=True, default=None)

    def __unicode__(self):
        return u'follower: <%r>, platform: <%r>' % (self.follower, self.platform)


# this is to build a time series of popularity of an influencer
class PopularityTimeSeries(models.Model):
    influencer = models.ForeignKey(Influencer)
    platform = models.ForeignKey(Platform)
    snapshot_date = models.DateTimeField(null=True, blank=True, default=None)
    num_followers = models.IntegerField(max_length=1000, null=True, blank=True, default=None)
    num_following = models.IntegerField(max_length=1000, null=True, blank=True, default=None)
    num_comments = models.IntegerField(max_length=1000, null=True, blank=True, default=None)

    def __unicode__(self):
        return u'{self.id} inf_id:{self.influencer_id} plat_id:{self.platform_id} {self.snapshot_date} {self.num_followers},{self.num_following},{self.num_comments}'.format(self=self)


class AlexaRankingInfo(models.Model):
    platform = models.ForeignKey(Platform, null=True, blank=True, default=None)
    seo_loadtime = models.FloatField(null=True, blank=True, default=None)  # FloatField correct? what args?

    # we can use this to find out who have important sites linking to them
    links_in_count = models.IntegerField(null=True, blank=True, default=None)
    sites_linking_in = models.TextField(null=True, blank=True, default=None)

    rank = models.FloatField(null=True, blank=True, default=None)

    reach = models.FloatField(null=True, blank=True, default=None)
    page_views_per_1m = models.FloatField(null=True, blank=True, default=None)
    page_views_rank = models.IntegerField(null=True, blank=True, default=None)
    page_views_per_user = models.FloatField(null=True, blank=True, default=None)

    keywords = models.FloatField(null=True, blank=True, default=None)

    snapshot_date = models.DateTimeField(null=True, blank=True, default=None)

    def __unicode__(self):
        return repr(self.__dict__)


class AlexaMetricByCountry(models.Model):
    alexa_ranking_info = models.ForeignKey(AlexaRankingInfo)
    country_code = models.CharField(max_length=64, null=True)
    rank = models.IntegerField(null=True, blank=True, default=None)
    contribution_page_views_pct = models.FloatField(null=True)
    contribution_users_pct = models.FloatField(null=True)

    def __unicode__(self):
        return repr(self.__dict__)


#####-----#####-----#####-----< Denormalization Tables >-----#####-----#####-----#####


class BrandMentions(models.Model):

    """
    for a given influencer, we want to know how many times that influencer mentioned a given brand
    """
    influencer = models.ForeignKey(Influencer, null=True, blank=True, default=None)
    brand = models.ForeignKey(Brands, null=True, blank=True, default=None)
    count_sponsored = models.IntegerField(null=True, blank=True, default=None)
    count_notsponsored = models.IntegerField(null=True, blank=True, default=None)
    snapshot_date = models.DateTimeField(default=datetime.now, db_index=True)

    def __unicode__(self):
        return u'id={self.id} influencer={self.influencer}, brand={self.brand}, count_sponsored={self.count_sponsored}, count_notsponsored={self.count_notsponsored}'.format(self=self)

    #####-----< Classmethods >-----#####
    @classmethod
    def group_by_endorsed(cls, num_results=None):
        """
        used in blogger search to display the top brands - by mention - in the filter bar (endorsed
        means not sponsored...terrible naming)
        @param num_results - limit results to this amount...defaults to all objects if not provided
        @return array of dicts containing brand__name and sum_endorsed as keys
        """
        res = cls.objects.values('brand__domain_name').annotate(
            sum_endorsed=Sum('count_notsponsored')).order_by('-sum_endorsed')
        if num_results is not None:
            res = res[:num_results]
        return res

    @classmethod
    def group_by_endorsed_name(cls, num_results=None):
        """
        used in blogger search to display the top brands - by mention - in the filter bar (endorsed
        means not sponsored...terrible naming)
        @param num_results - limit results to this amount...defaults to all objects if not provided
        @return array of dicts containing brand__name and sum_endorsed as keys
        """
        res = cls.objects.exclude(brand__blacklisted=True).values('brand__name', 'brand__domain_name').annotate(
            sum_endorsed=Sum('count_notsponsored')).order_by('-sum_endorsed')
        if num_results is not None:
            res = res[:num_results]
        return res

    @classmethod
    def all_influencers_mentioning_brands(cls, brands):
        """
        get a list of all influencers that have mentioned the passed brands
        @param brands - the names of the brands which we want to get influencers for
        @return list of Influencer
        """
        brand_mentions = cls.objects.select_related('influencer').filter(brand__name__in=brands)
        return [bm.influencer for bm in brand_mentions]

    @staticmethod
    def analyze_influencer(inf):
        posts = Posts.objects.filter(influencer=inf,
                                     platform__platform_name__in=Platform.BLOG_PLATFORMS,
                                     products_import_completed=True,
                                     brand_tags__isnull=False)
        all_brand_mentions = {}
        sponsored_brand_mentions = {}
        for p in posts:
            brand_names = p.brand_tags.split(', ')
            for b in brand_names:
                if b in all_brand_mentions:
                    all_brand_mentions[b] += 1
                else:
                    all_brand_mentions[b] = 1
                if p.is_sponsored:
                    if b in sponsored_brand_mentions:
                        sponsored_brand_mentions[b] += 1
                    else:
                        sponsored_brand_mentions[b] = 1
        for brand_name in all_brand_mentions:
            print "%s %d %d" % (brand_name, all_brand_mentions[brand_name], sponsored_brand_mentions[brand_name] if brand_name in sponsored_brand_mentions else 0)
            try:
                brand = Brands.objects.get(name=brand_name)
            except:
                continue
            bm, created = BrandMentions.objects.get_or_create(influencer=inf, brand=brand)
            bm.count_notsponsored = all_brand_mentions[brand_name]
            if brand_name in sponsored_brand_mentions:
                bm.count_sponsored = sponsored_brand_mentions[brand_name]
            bm.save()
        print "Done with %s " % inf.blog_url

    @classmethod
    def nightly_run(cls):
        """
        this method should be run each night and is responsible for creating / updating BrandMentions rows as appropriate

        New algorithm: for each brand that a user mentions (via a product link or a brand page link), we count
                    how many posts it is mentioned in
                    TODO: what if a blogger mentioned the same brand multiple times in a given post?
        """

        infs = Influencer.objects.filter(show_on_search=True).order_by('-id')

        for i, inf in enumerate(infs):
            print i
            BrandMentions.analyze_influencer(inf)

        if False:
            all_products = ProductModelShelfMap.objects.filter(
                post__isnull=False, post__influencer__show_on_search=True).order_by('-id')
            #influencer_ids = {i.id:True for i in Influencer.raw_influencers_for_search()}

            for i, pmsm in enumerate(all_products.iterator()):
                print "%dth" % i
                brand_id = pmsm.product_model.brand_id
                influencer_id = pmsm.post.influencer_id
                instance = cls.objects.filter(influencer_id=influencer_id, brand_id=brand_id)

                if instance.exists():
                    instance[0].denormalize()
                else:
                    instance = BrandMentions.objects.create(influencer_id=influencer_id, brand_id=brand_id)
                    instance.denormalize()

    #####-----</ Classmethods >-----#####

    #####-----< Denormalize >-----#####
    def denormalize(self):
        """
        this is actually the primary method of BrandMentionedByBlogger because this Model is - by and large - a
        denormalization table
        """
        influencer_brand_products = ProductModelShelfMap.objects.filter(
            product_model__brand=self.brand, post__influencer=self.influencer)
        distinct_posts = influencer_brand_products.distinct('post')

        self.count_sponsored = distinct_posts.filter(post__is_sponsored=True).count()

        not_sponsored = distinct_posts.filter(post__is_sponsored=False)
        if self.influencer.shelf_user:
            shelved_items = self.influencer.shelf_user.userprofile.shelfed_items(
                unique=True).filter(product_model__brand=self.brand)
            not_sponsored = not_sponsored.exclude(id__in=[s.id for s in shelved_items])
            self.count_notsponsored = not_sponsored.count() + shelved_items.count()
        else:
            self.count_notsponsored = not_sponsored.count()

        self.save()
    #####-----</ Denormalize >-----#####


class InfluencerCategoryMentions(models.Model):

    """
    A row in this table represents how much an influencer has talked about a given category
    """
    influencer = models.ForeignKey(Influencer, related_name="category_mentions")
    category = models.CharField(max_length=200)
    category_count = models.IntegerField(default=0)

    @classmethod
    def group_by_category(cls, num_results=None):
        """
        used in blogger search to display the top category's, this method is used to group all
        products shelved or blogged about by influencers on the search
        @param num_results - limit results to this amount...defaults to all objects if not provided
        @return array of dicts containing brand__name and sum_endorsed as keys
        """
        to_fetch = num_results if num_results else cls.objects.count()
        return cls.objects.values('category').annotate(sum_cat=Sum('category_count')).order_by('-sum_cat')[:to_fetch]

    @classmethod
    def nightly_run(cls):
        """
        the method to run next nightly for maintenance of this denormalization table
        """
        # start by deleting all rows because the number we care about most,
        # category_count, should start at 0 for all instances
        cls.objects.all().delete()

        search_influencers = Influencer.raw_influencers_for_search().select_related('shelf_user')

        for i, inf in enumerate(search_influencers):
            print i
            # get all products shelved by the influencer or talked about in a post
            influencer_post_pmsms = ProductModelShelfMap.objects.filter(post__influencer=inf)
            influencer_shelved_pmsms = ProductModelShelfMap.objects.filter(user_prof__user=inf.shelf_user)
            all_pmsms = influencer_post_pmsms | influencer_shelved_pmsms

            # for each of the distinct product models, check if we already track that models category with the current influencer
            # in our DB
            for prod in ProductModelShelfMap.distinct_product_model(all_pmsms):
                if prod.product_model.cat1:
                    instance = cls.objects.get_or_create(influencer=inf, category=prod.product_model.cat1)[0]
                    instance.category_count += 1
                    instance.save()


#####-----#####-----#####-----</ Denormalization Tables >-----#####-----#####-----#####


#####-----#####-----#####-----< Lottery Tables >-----#####-----#####-----#####


class Lottery(models.Model):
    THEME_CHOICES = (
        ("theme_pink", "theme_pink"),
        ("theme_dark_pink", "theme_dark_pink"),
        ("theme_purple", "theme_purple"),
        ("theme_dark_blue", "theme_dark_blue"),
        ("theme_blue", "theme_blue"),
        ("theme_teal", "theme_teal"),
        ("theme_dark_teal", "theme_dark_teal"),
        ("theme_lime", "theme_lime"),
        ("theme_yellow", "theme_yellow"),
        ("theme_orange", "theme_orange"),
    )

    #####-----< Meta >-----#####
    name = models.CharField(max_length=200)
    image = models.URLField(max_length=1000, blank=True, null=True, default=None)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default=THEME_CHOICES[0][0])
    terms = models.TextField(max_length=5000, null=True, blank=True)
    #####-----</ Meta >-----#####

    #####-----< Foreign Relations >-----#####
    creator = models.ForeignKey(UserProfile)
    #####-----</ Foreign Relations >-----#####

    #####-----< Date Fields >-----#####
    start_datetime = models.DateTimeField(default=datetime.now)
    end_datetime = models.DateTimeField()
    start_date = models.DateField()  # remove
    end_date = models.DateField()  # remove
    timezone = models.CharField(max_length=100, choices=constants.TIMEZONES, default=constants.EST[0])
    #####-----</ Date Fields >-----#####

    #####-----< Flags >-----#####
    in_test_mode = models.BooleanField(default=True)
    show_winners = models.BooleanField(default=False)
    #####-----</ Flags >-----#####

    #####-----< Classmethods >-----#####
    @classmethod
    def past_lotterys(cls):
        pass
    #####-----</ Classmethods >-----#####

    #####-----< Foreign Model Querys >-----#####
    @property
    def self_prizes(self):
        return LotteryPrize.objects.filter(lottery=self)

    @property
    def self_tasks(self):
        return LotteryTask.objects.filter(lottery=self)

    @property
    def self_entries(self):
        return LotteryEntry.objects.filter(lottery=self)

    @property
    def self_completed_tasks(self):
        return LotteryEntryCompletedTask.objects.filter(entry__lottery=self)

    @property
    def self_embeddable(self):
        '''
        this should never return more then one, but wrapping it to be safe
        '''
        try:
            return Embeddable.objects.get(lottery=self)
        except MultipleObjectsReturned:
            return None

    @property
    def self_winners(self):
        '''
        get the winners of this lottery
        '''
        return self.self_completed_tasks.filter(is_winner=True)

    @property
    def total_points_completed(self):
        '''
        get the total number of points completed for all entries to this lottery
        '''
        return LotteryEntryCompletedTask.objects.filter(task__lottery=self).aggregate(Sum('task__point_value'))['task__point_value__sum']
    #####-----</ Foreign Model Querys >-----#####

    #####-----< Calculated Fields >-----#####
    @property
    def embeddable_url(self):
        return reverse('debra.widget_views.render_embeddable', args=(self.creator.id, self.self_embeddable.id,))

    @property
    def num_timezone(self):
        return float(self.timezone)

    @property
    def correction_for_timezone(self):
        EST_OFFSET = 5.0
        return timedelta(hours=(self.num_timezone + EST_OFFSET))

    @property
    def hasnt_started(self):
        '''
        return True if the lottery hasnt started yet
        '''
        seconds_remaining = (self.start_datetime - datetime.now()).total_seconds() - \
            self.correction_for_timezone.total_seconds()
        return seconds_remaining > 0

    @property
    def has_ended(self):
        '''
        return True if the lottery has ended, false otherwise
        '''
        seconds_remaining = (self.end_datetime - datetime.now()).total_seconds() - \
            self.correction_for_timezone.total_seconds()
        return seconds_remaining < 0

    @property
    def is_running(self):
        '''
        return True if this lottery is currently in progress, false otherwise
        '''
        return not self.hasnt_started and not self.has_ended

    @property
    def has_entries(self):
        '''
        return True if this lottery has entries, false otherwise
        '''
        return self.self_entries.count() > 0

    @property
    def average_num_tasks_completed(self):
        '''
        get the average number of tasks completed per user for this lottery
        '''
        return math.ceil(self.self_completed_tasks.count() / self.self_entries.count()) if self.self_entries.count() > 0 else 0
    #####-----</ Calculated Fields >-----#####

    #####-----< Methods >-----#####
    @property
    def time_remaining_dict(self):
        '''
        this method gets the time remaining for the lottery. Now, this will be the time remaining till the lottery
        starts, if it hasn't started yet, else it is the time remaining till the lottery ends
        '''
        MINUTE, HOUR = 60, 60 * 60

        now = datetime.now()
        target_time = self.end_datetime if self.is_running else self.start_datetime
        total_remaining_secs = (target_time - now).total_seconds() - self.correction_for_timezone.total_seconds()
        diff = timedelta(seconds=total_remaining_secs)

        return {
            'days': diff.days,
            'hours': ((diff.seconds / HOUR) % 24),
            'minutes': (diff.seconds / MINUTE) % 60
        }

    def clone(self):
        '''
        clone this lottery
        '''
        self.pk = None
        self.save()

    def duplicate(self, tasks, prizes, embeddable):
        '''
        duplicate items from a previous lottery to this lottery
        @param tasks - the tasks from the old lottery to duplicate
        @param prizes - the prizes from the old lottery to duplicate
        '''
        [task.clone(self) for task in tasks]
        [prize.clone(self) for prize in prizes]
        embeddable.clone(self)

        # we DO want to modify the dates for this new, cloned lottery to be in the future, not the past
        self.start_datetime = datetime.now()
        self.end_datetime = datetime.now() + timedelta(days=1)
        self.save()

    def clear_test_entries(self):
        '''
        this method clears all entries on a lottery that were added before the start of the lottery
        '''
        cleanup = lambda qs: [it.delete() for it in qs if (
            (self.start_datetime - it.touch_datetime).total_seconds() - self.correction_for_timezone.total_seconds()) > 0]
        cleanup(self.self_entries)
        cleanup(self.self_completed_tasks)

    def clear_test_mode(self):
        '''
        this method is called on a lottery when it is ready to go from test mode into "production mode"
        '''
        self.in_test_mode = False
        self.clear_test_entries()
        self.save()

    def pick_winner(self):
        '''
        this method does what you think it does
        @return LotteryEntryCompletedTask that won the lottery
        '''
        completed_tasks = self.self_completed_tasks.filter(is_winner=False)
        random_winner = random.choice(completed_tasks)
        random_winner.is_winner = True
        random_winner.save()
        return random_winner
    #####-----</ Methods >-----#####


class LotteryPartner(models.Model):

    '''
    a lottery partner is a blogger that has been invited to be a partner in the lottery by the lottery creator
    '''
    partner = models.ForeignKey(UserProfile)
    lottery = models.ForeignKey(Lottery)


class LotteryPrize(models.Model):
    lottery = models.ForeignKey(Lottery)
    description = models.CharField(max_length=200)
    quantity = models.IntegerField()
    # not using a foreignkey because the specified brand might not be in our system
    brand = models.CharField(max_length=200, blank=True, null=True)

    #####-----< Methods >-----#####
    def clone(self, lottery):
        '''
        clone this prize and have the clone point to the given lottery, return the clone
        '''
        self.pk = None
        self.lottery = lottery
        self.save()
        return self
    #####-----</ Methods >-----#####


class LotteryTask(models.Model):
    TWITTER_FOLLOW = {
        'name': "twitter_follow",
        'value': lambda name: "Follow {name} on Twitter".format(name=name),
        'meta': {
            'css_class': 'social_twitter',
            'icon': 'icon-social_twitter',
            'type': 'url',
            'prompt': 'Twitter URL',
            'instructions': "enter in your twitter handle below",
            'validation_placeholder': "your twitter handle"
        }
    }
    TWITTER_TWEET = {
        'name': "twitter_tweet",
        'value': lambda name: "Tweet About...",
        'meta': {
            'css_class': 'social_twitter',
            'icon': 'icon-social_twitter',
            'type': 'text',
            'prompt': 'Tweet Text',
            'instructions': "Click the twitter button below and tweet the specified text",
            'validation_placeholder': "your twitter handle"
        }
    }
    PINTEREST_PIN = {
        'name': "pinterest_pin",
        'value': lambda name: "Pin a Photo",
        'meta': {
            'css_class': 'social_pinterest',
            'icon': 'icon-social_pinterest',
            'type': 'url',
            'prompt': 'Photo URL',
            'prompt2': 'Photo Title',
            'social_description': '_________',
            'instructions': "Pin this photo on Pinterest",
            'validation_placeholder': "your pinterest url"
        }
    }
    PINTEREST_FOLLOW = {
        'name': "pinterest_follow",
        'value': lambda name: "Follow {name} on Pinterest".format(name=name),
        'meta': {
            'css_class': 'social_pinterest',
            'icon': 'icon-social_pinterest',
            'type': 'url',
            'prompt': 'Pinterest URL',
            'instructions': "enter your pinterest handle below",
            'validation_placeholder': "your pinterest url"
        }
    }
    FACEBOOK_FOLLOW = {
        'name': "facebook_follow",
        'value': lambda name: "Follow {name} on Facebook".format(name=name),
        'meta': {
            'css_class': 'social_facebook',
            'icon': 'icon-social_facebook',
            'type': 'url',
            'prompt': 'Facebook URL',
            'instructions': "enter your facebook url below",
            'validation_placeholder': "your facebook url"
        }
    }
    FACEBOOK_POST = {
        'name': "facebook_post",
        'value': lambda name: "Post on Facebook",
        'meta': {
            'css_class': 'social_facebook',
            'icon': 'icon-social_facebook',
            'type': 'text',
            'prompt': 'Post Text',
            'instructions': "Share this giveaway post on Facebook.",
            'validation_placeholder': "your facebook url"
        }
    }
    INSTAGRAM_FOLLOW = {
        'name': "instagram_follow",
        'value': lambda name: "Follow {name} on Instagram".format(name=name),
        'meta': {
            'css_class': 'social_instagram2',
            'icon': 'icon-social_instagram2',
            'type': 'url',
            'prompt': 'Instagram URL',
            'instructions': "enter your instagram url below",
            'validation_placeholder': "your instagram url"
        }
    }
    BLOGLOVIN_FOLLOW = {
        'name': "bloglovin_follow",
        'value': lambda name: "Follow {name} on BlogLovin".format(name=name),
        'meta': {
            'css_class': 'social_blog_lovin',
            'icon': 'icon-social_blog_lovin',
            'type': 'url',
            'prompt': 'BlogLovin URL',
            'instructions': "enter your bloglovin url below",
            'validation_placeholder': "your bloglovin url"
        }
    }
    BLOG_COMMENT = {
        'name': "blog_comment",
        'value': lambda name: "Post a Comment about {name}".format(name=name),
        'meta': {
            'css_class': 'social_blog',
            'icon': 'icon-social_blog',
            'type': 'url',
            'prompt': 'Blog URL',
            'instructions': "enter your validation url"
        }
    }
    CUSTOM = {
        'name': "custom",
        'value': lambda name: "Create your own rule",
        'meta': {
            'css_class': 'custom',
            'icon': 'icon-custom',
            'type': 'text',
            'instructions': lambda req: req,
            'prompt': 'What do you want them to do...'
        }
    }
    ALL_TASKS = [TWITTER_FOLLOW, TWITTER_TWEET, PINTEREST_PIN, PINTEREST_FOLLOW, FACEBOOK_FOLLOW, FACEBOOK_POST,
                 INSTAGRAM_FOLLOW, BLOGLOVIN_FOLLOW, BLOG_COMMENT, CUSTOM]
    TASKS = ([(task['name'], task['value']) for task in ALL_TASKS])

    POINT_VALUES = (
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
        (5, 5),
        (10, 10),
        (20, 20),
    )

    CUSTOM_TEXT_FIELD = ("text_field", 'include a text field')
    CUSTOM_BUTTON = ("button", 'include an "I did it" button')
    CUSTOM_RULE_OPTIONS = (
        CUSTOM_TEXT_FIELD,
        CUSTOM_BUTTON
    )

    lottery = models.ForeignKey(Lottery)
    task = models.CharField(max_length=200, choices=TASKS, default=TWITTER_FOLLOW['name'])
    point_value = models.IntegerField(choices=POINT_VALUES, default=POINT_VALUES[0][0])
    # what the contestant must do to fulfill the task
    requirement_text = models.CharField(max_length=300, null=True, blank=True)
    requirement_url = models.URLField(null=True, blank=True)  # the url the users must visit to post the requirement
    # the name of the target that must be followed to fulfill this task (only filled in if there is a requirement url)
    url_target_name = models.CharField(max_length=200, null=True, blank=True)
    validation_required = models.BooleanField(default=False)
    mandatory = models.BooleanField(default=False)
    # step ids determine the sorting order for lottery tasks in render-embeddable view
    step_id = models.IntegerField(default=0)
    # custom rule specific
    custom_option = models.CharField(
        max_length=50, choices=CUSTOM_RULE_OPTIONS, default=CUSTOM_TEXT_FIELD, null=True, blank=True)
    url_to_visit = models.URLField(null=True, blank=True)

    @property
    def task_dict(self):
        '''
        this function returns the task dictionary for this instance i.e. if this task had task field of value 'twitter_tweet'
        return TWITTER_TWEET dict
        @return task dictionary for this LotteryTask
        '''
        for task in self.ALL_TASKS:
            if task['name'] == self.task:
                return task

    #####-----< Methods >-----#####
    def clone(self, lottery):
        '''
        clone this task and have the clone point to the given lottery, return the clone
        '''
        self.pk = None
        self.lottery = lottery
        self.save()
        return self
    #####-----</ Methods >-----#####


class LotteryEntry(models.Model):

    '''
    a lottery entry represents a single entry into a lottery
    '''
    lottery = models.ForeignKey(Lottery)
    user = models.ForeignKey(UserProfile)
    is_winner = models.BooleanField(default=False)
    touch_datetime = models.DateTimeField(auto_now_add=True)


class LotteryEntryCompletedTask(models.Model):

    '''
    Lottery entry completed task instances represent tasks completed by a lottery entry instance
    '''
    entry = models.ForeignKey(LotteryEntry)
    task = models.ForeignKey(LotteryTask)
    entry_validation = models.CharField(max_length=300, null=True, blank=True)
    touch_datetime = models.DateTimeField(auto_now_add=True)
    is_winner = models.BooleanField(default=False)
    # custom task specific
    custom_task_response = models.CharField(max_length=300, null=True, blank=True)

    #####-----< Calculated Fields >-----#####
    @property
    def task_num(self):
        '''
        get the "number" of a lottery completed task entry (calculated by taking the count of all completed tasks completed before
        the given one)
        '''
        return self.entry.lottery.self_completed_tasks.filter(touch_datetime__lt=self.touch_datetime).count() + 1
    #####-----</ Calculated Fields >-----#####


#####-----#####-----#####-----</ Lottery Tables >-----#####-----#####-----#####


#####-----#####-----#####-----< Embeddable Table >-----#####-----#####-----#####


class Embeddable(models.Model):
    COLLAGE_WIDGET = "collage_widget"
    LOTTERY_WIDGET = "lottery_widget"
    TYPES = (
        (COLLAGE_WIDGET, "collage widget"),
        (LOTTERY_WIDGET, "lottery widget"),
    )

    creator = models.ForeignKey(UserProfile)
    # TODO: consider making this a OneToOne field
    lottery = models.ForeignKey(Lottery, null=True, blank=True)
    type = models.CharField(max_length=50, choices=TYPES, default=COLLAGE_WIDGET)
    html = models.TextField(max_length=5000)

    def clone(self, lottery):
        '''
        clone this embeddable to a new lottery
        '''
        self.pk = None
        self.lottery = lottery
        self.save()


#####-----#####-----#####-----</ Embeddable Table >-----#####-----#####-----#####


#####-----#####-----#####-----< Policy Based Fetching >-----#####-----#####-----#####


class FetcherApiDataSpec(models.Model):
    policy_name = models.CharField(max_length=128)
    platform_name = models.CharField(max_length=128)
    key = models.CharField(max_length=128)

    def __unicode__(self):
        return '{self.id} {self.policy_name} {self.platform_name} {self.key}'.format(self=self)


class FetcherApiDataValue(models.Model):
    spec = models.ForeignKey(FetcherApiDataSpec)
    value_index = models.IntegerField()
    value = models.CharField(max_length=10000)
    last_usage = models.DateTimeField(default=None, blank=True, null=True)

    def __unicode__(self):
        return '{self.id} {self.value_index} {self.value}'.format(self=self)


class FetcherApiDataAssignment(models.Model):
    spec = models.ForeignKey(FetcherApiDataSpec)
    value_m = models.ForeignKey(FetcherApiDataValue)
    server_ip = models.CharField(max_length=128, db_index=True)

    def __unicode__(self):
        return '<spec={self.spec}> <value={self.value_m}> {self.server_ip}'.format(self=self)

    class Meta:
        unique_together = (('spec', 'server_ip'),)


#####-----#####-----#####-----</ Policy Based Fetching >-----#####-----#####-----#####


#####-----#####-----#####-----< Counting Scraping Errors >-----#####-----#####-----#####


class OperationStatus(models.Model):

    """Records number of named operations, together with a status and an
    optional message, for a given object_type and object_spec, per hour per
    day. For scraping operations object_type will be 'domain' and object_spec
    will be a name of a domain.
    """
    object_type = models.CharField(max_length=1000)
    object_spec = models.CharField(max_length=10000, db_index=True)
    op = models.CharField(max_length=1000)
    op_status = models.CharField(null=True, max_length=10000)
    op_msg = models.CharField(null=True, max_length=50000)
    op_date = models.DateField()
    op_hour = models.IntegerField()
    op_count = models.IntegerField(default=0)

    @staticmethod
    def find(object_type, object_spec, op, op_status, op_msg):
        kwargs = {
            'object_type': object_type,
            'object_spec': object_spec,
            'op': op,
            'op_status': op_status,
            'op_msg': op_msg,
            'op_date': date.today(),
            'op_hour': datetime.now().hour,
        }
        q = OperationStatus.objects.filter(**kwargs)
        if q.exists():
            return q[0]
        try:
            return OperationStatus.objects.create(**kwargs)
        except IntegrityError:
            q = PlatformApiCalls.objects.filter(**kwargs)
            assert q.exists(), 'Unique constraint prevented from inserting a new row but ' \
                'a row still not found'
            return q[0]

    @staticmethod
    def inc(*args, **kwargs):
        record = OperationStatus.find(*args, **kwargs)
        record.op_count = F('op_count') + 1
        record.save()

    class Meta:
        unique_together = (('object_type', 'object_spec', 'op', 'op_status',
                            'op_msg', 'op_date', 'op_hour'),)


class FetcherTask(models.Model):
    platform = models.ForeignKey(Platform)
    started = models.DateTimeField()
    server_ip = models.CharField(max_length=128)
    process_pid = models.CharField(max_length=128)
    policy_name = models.CharField(null=True, max_length=1000)
    posts_skipped = models.IntegerField(null=True)
    posts_saved = models.IntegerField(null=True)
    pis_skipped = models.IntegerField(null=True)
    pis_saved = models.IntegerField(null=True)
    duration = models.FloatField(null=True)
    error_msg = models.TextField(null=True)

#####-----#####-----#####-----</ Counting Scraping Errors >-----#####-----#####-----#####


#####-----#####-----#####-----< Signal Handlers >-----#####-----#####-----#####


#####-----< Registration Signals >-----#####
def fb_user_registered_handler(sender, user, facebook_data, **kwargs):
    '''
    when a user registers via facebook, we have to specially create the userprofile for that user, as
    we don't want to send out the email verification like we do when creating a user normally
    '''
    UserProfile.objects.get_or_create(user=user)
#####-----</ Registration Signals >-----#####

#####-----< Denormalization Signals >-----#####


def create_shelf_img(sender, instance, created, **kwargs):
    '''
    when a productmodelshelfmap is created, check if it's shelf already has a shelf image.
    If not, make its image this mapping's productmodelshelfmap.img_url_thumbnail_view
    '''
    if not instance.shelf.shelf_img:
        instance.shelf.shelf_img = instance.img_url_thumbnail_view
        instance.shelf.save()


def update_shelf_num_items(sender, instance, *args, **kwargs):
    '''
    increment or decrement the number of items on this mappings shelf when a shelf is modified
    '''
    # if a shelf has been deleted (so this handler is being triggered as a
    # result of a cascading delete), then the instance wont have a shelf
    try:
        shelf = instance.shelf
        if shelf.user_id:
            shelf.num_items = instance.num_shelf_items
            shelf.save()
    except ObjectDoesNotExist:
        pass


def update_user_num_shelves(sender, instance, created, **kwargs):
    '''
    when a shelf is created or deleted, update the users number of shelves
    '''
    if instance.user_id:
        user_prof = instance.user_id.userprofile
        user_prof.num_shelves = user_prof.user_created_shelves.count()
        user_prof.save()


def update_user_num_items(sender, instance, created, **kwargs):
    '''
    when a ProductModelShelfMap is created, update the instances user's number of items in shelves
    '''
    user_prof = instance.user_prof
    if user_prof:
        user_prof.num_items_in_shelves = user_prof.shelfed_items(
            unique=True, has_image=True).exclude(shelf__name=constants.DELETED_SHELF).count()
        user_prof.save()


def update_follow_count(sender, instance, *args, **kwargs):
    try:
        instance.user.num_following = instance.user.get_following.count()
        instance.following.num_followers = instance.following.get_followers.count()
        instance.user.save()
        instance.following.save()
    except ObjectDoesNotExist:
        pass


def create_default_competitor(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        BrandSavedCompetitors.objects.filter(brand=instance, competitor=instance)[0]
    except IndexError:
        BrandSavedCompetitors.objects.create(brand=instance, competitor=instance)


def mark_mailbox_as_unread(sender, instance, created, **kwargs):
    # post-save signal handler for MailProxyMessage;
    # it checks whether we should mark corresponding thread (instance.thread)
    # as read or not;
    # there are 2 cases when we should change mark for given thread:
    # 1) when a new message from influencer comes to our thread (
    # should mark as unread);
    # 2) when brand user opens the latest message from influencer in that
    # thread in his email client (should mark as read);
    if not created:
        return
    try:
        if instance.type == MailProxyMessage.TYPE_EMAIL and \
            instance.direction == MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND:
            instance.thread.has_been_read_by_brand = False
            instance.thread.save()
        elif instance.type == MailProxyMessage.TYPE_OPEN:
            target_msg_id = instance.mandrill_id
            try:
                latest_message = instance.thread.threads.filter(
                    type=MailProxyMessage.TYPE_EMAIL,
                    direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND
                ).order_by('-ts')[0]
            except IndexError:
                log.info("There are no messages in thread: {}".format(
                    instance.thread.id)
                )
            else:
                # if user opened the most recent message, then mark thread as read
                if latest_message.mandrill_id == target_msg_id:
                    instance.thread.has_been_read_by_brand = True
                    instance.thread.save()
    except Exception:
        log.exception("Unexpected exception in mark_mailbox_as_unread.")


class HealthReport(models.Model):
    date = models.DateField(auto_now_add=True)

    # table 1
    blog_urls = models.IntegerField()
    urls_analyzed = models.IntegerField()
    live = models.IntegerField()
    fashion = models.IntegerField()
    active = models.IntegerField()
    with_social = models.IntegerField()
    with_comments = models.IntegerField()
    with_items = models.IntegerField()

    # table 2
    eligible = models.IntegerField()
    added_today = models.IntegerField()
    at_least_7 = models.IntegerField()
    at_least_100 = models.IntegerField()

    # table 3
    # not displayed but used for diff calculation
    perc_scrap_today = models.IntegerField()
    perc_scrap_wo_posts = models.IntegerField()
    perc_scrap_wo_items = models.IntegerField()
    perc_scrap_wo_images = models.IntegerField()

    @classmethod
    def daily_update(cls):
        today = date.today()
        yesterday = today - timedelta(days=1)
        try:
            report = HealthReport.objects.get(date=today)
        except HealthReport.DoesNotExist:
            report = HealthReport()
        try:
            yest_report = HealthReport.objects.get(date=yesterday)
        except HealthReport.DoesNotExist:
            yest_report = None

        considered_bloggers = Influencer.objects.filter(blog_url__isnull=False)
        report.blog_urls = considered_bloggers.count()
        report.urls_analyzed = PlatformDataOp.objects.filter(
            started__gte=yesterday, operation='create_platforms_from_description').count()
        report.live = considered_bloggers.filter(is_live=True).count()
        report.fashion = considered_bloggers.filter(relevant_to_fashion=True).count()
        report.active = considered_bloggers.active().count()
        report.with_social = considered_bloggers.filter(
            platform__platform_name__in=Platform.SOCIAL_PLATFORMS).distinct('id').count()
        report.with_comments = Posts.objects.filter(
            has_comments=True, influencer__in=considered_bloggers).distinct('influencer').count()
        report.with_items = Posts.objects.filter(
            has_products=True, influencer__in=considered_bloggers).distinct('influencer').count()

        report.eligible = considered_bloggers.active().filter(relevant_to_fashion=True, is_live=True).count()
        if yest_report:
            report.added_today = report.eligible - yest_report.eligible
        else:
            report.added_today = report.eligible
        report.at_least_7 = considered_bloggers.filter(posts_count__gte=7).count()
        report.at_least_100 = considered_bloggers.filter(posts_count__gte=100).count()

        today_scraps = Influencer.objects.filter(posts__create_date__gte=yesterday, show_on_search=True).distinct('id')
        all_influencers_count = Influencer.objects.filter(show_on_search=True).count()
        report.perc_scrap_today = round(100.0 * today_scraps.count() / all_influencers_count)
        report.perc_scrap_wo_posts = round(
            100.0 * today_scraps.filter(posts_count__lte=0).count() / today_scraps.count())

        today_posts = Posts.objects.filter(create_date__gte=yesterday)
        report.perc_scrap_wo_items = round(100.0 * today_posts.filter(has_products=False).count() / today_posts.count())
        report.perc_scrap_wo_images = round(
            100.0 * today_posts.filter(eligible_images_count__lte=0).count() / today_posts.count())

        report.save()


from debra.elastic_search_helpers import influencer_add_tag, influencer_remove_tag


class InfluencersGroupManager(DenormalizationManagerMixin,
        models.Manager):

    def add_influencer(self, ):
        ''' add influencer to db and es '''
        pass

    def remove_influencer(self):
        ''' remove influencer from db and es '''
        pass

    def add_influencer_bulk(self, tag_ids, inf_ids):
        ''' add multiple influencers to db and es '''
        pass

    def remove_influencer_bulk(self):
        ''' remove multiple inlfuencers from db and es '''
        pass

    def add_influencer_to_redis(self, tag_ids, inf_ids, **kwargs):
        '''
        add influencer or set of influencers to tag or set of tags using redis
        @param tag_id - either int or list value, representing a single tag or a list of tags to add
            influencer/influencers to
        @param inf_id - either int or list value, representing a single influencer or a list of influencers
            which need to be added to tag/tags
        @return
        '''
        _t0 = time.time()
        # inf_ids = inf_id if type(inf_id) == list else [inf_id]
        # tag_ids = tag_id if type(tag_id) == list else [tag_id]
        pipe = settings.REDIS_CLIENT.pipeline()
        for tag_id in tag_ids:
            for inf_id in inf_ids:
                pipe.sadd(
                    'tinfs_{}'.format(tag_id), inf_id)
                pipe.sadd(
                    'itags_{}'.format(inf_id), tag_id)
        if kwargs.get('mark_as_recent') and kwargs.get('brand_id') and tag_ids:
            pipe.hset('brectags', kwargs.get('brand_id'), tag_ids[-1])
        pipe.execute()
        print 'add_influencer_to_redis took {}'.format(time.time() - _t0)

    def remove_influencer_from_redis(self, tag_ids, inf_ids):
        '''
        remove influencer or set of influencers from tag or set of tags using redis
        @param tag_id - either int or list value, representing a single tag or a list of tags to remove
            influencer/influencers from
        @param inf_id - either int or list value, representing a single influencer or a list of influencers
            which need to be removed from tag/tags
        @return
        '''
        _t0 = time.time()
        # inf_ids = inf_id if type(inf_id) == list else [inf_id]
        # tag_ids = tag_id if type(tag_id) == list else [tag_id]
        pipe = settings.REDIS_CLIENT.pipeline()
        for tag_id in tag_ids:
            for inf_id in inf_ids:
                pipe.srem(
                    'tinfs_{}'.format(tag_id), inf_id)
                pipe.srem(
                    'itags_{}'.format(inf_id), tag_id)
        pipe.execute()
        print 'remove_influencer_from_redis took {}'.format(time.time() - _t0)

    def add_influencer_fast(cls, tag_ids, inf_ids, celery=True, **kwargs):
        from debra.brand_helpers import bookmarking_task

        cls.add_influencer_to_redis(tag_ids, inf_ids, **kwargs)

        task_kwargs = dict(
            tag_ids=tag_ids,
            operation='add_influencer',
            collection_type='tag',
            params=dict(
                influencer=inf_ids,
                save_to_redis=False,
                **kwargs
            ),
        )
        if not celery:
            bookmarking_task(**task_kwargs)
        else:
            bookmarking_task.apply_async(kwargs=task_kwargs,
                queue='bookmarking')

    def remove_influencer_fast(cls, tag_ids, inf_ids, celery=True, **kwargs):
        from debra.brand_helpers import bookmarking_task

        cls.remove_influencer_from_redis(tag_ids, inf_ids)

        task_kwargs = dict(
            tag_ids=tag_ids,
            operation='remove_influencer',
            collection_type='tag',
            params=dict(
                influencer=inf_ids,
                save_to_redis=False,
                **kwargs
            ),
        )
        if not celery:
            bookmarking_task(**task_kwargs)
        else:
            bookmarking_task.apply_async(kwargs=task_kwargs,
                queue='bookmarking')


class InfluencersGroup(models.Model):
    name = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    owner_brand = models.ForeignKey('Brands', related_name="influencer_groups")
    creator_brand = models.ForeignKey('Brands', related_name="created_collections", null=True, blank=True)
    creator_userprofile = models.ForeignKey('UserProfile', related_name="created_collections", null=True, blank=True)
    system_collection = models.NullBooleanField(default=False)
    archived = models.NullBooleanField(blank=True, null=True, default=False)

    # denormalized values
    influencers_count = models.IntegerField(null=True, default=0)
    top_influencers = TextArrayField(null=True, default=[])
    top_influencers_profile_pics = TextArrayField(null=True, default=[])

    objects = InfluencersGroupManager()

    def __unicode__(self):
        return "Collection %s for %s made by %s" % (self.name, str(self.owner_brand), str(self.creator_brand))

    def update_in_cache(self, timeout=0):
        if not self.system_collection:
            redis_cache.set('ig_{}'.format(self.id), self.name, timeout=timeout)
        else:
            settings.REDIS_CLIENT.sadd('systags', self.id)
        # if self.archived:
        #     pipe.hset('brectag', kwargs.get('brand_id'), tag_ids[-1])

    def denormalize(self):
        inf_ids = list(self.influencers_mapping.exclude(
            status=InfluencerGroupMapping.STATUS_REMOVED
        ).values_list('influencer', flat=True).distinct('influencer'))

        def get_profile_pics(expensive=False):
            if expensive:
                profile_pics = [pp for pp in redis_cache.get_many([
                    'pp_{}'.format(inf_id) for inf_id in inf_ids]).values()
                    if '/mymedia/site_folder/images/global/avatar.png' not in pp]
                profile_pics.extend(
                    ['/mymedia/site_folder/images/global/avatar.png'] * (
                        min(len(inf_ids), constants.NUM_OF_IMAGES_PER_BOX) - len(profile_pics)))
            else:
                profile_pics = redis_cache.get_many([
                    'pp_{}'.format(inf_id)
                    for inf_id in inf_ids[:constants.NUM_OF_IMAGES_PER_BOX]
                ]).values()
            return profile_pics

        self.influencers_count = len(inf_ids)
        self.top_influencers = inf_ids[:constants.NUM_OF_IMAGES_PER_BOX]
        self.top_influencers_profile_pics = get_profile_pics()
        self.save()

    def rebake(self):
        # partials_baker.bake_list_messages_partial_async(self.owner_brand, self.creator_brand)
        pass

    def add_influencer(self, influencer, denormalize=True, save_to_redis=True, **kwargs):
        from debra.helpers import get_model_instance

        if isinstance(influencer, list):
            for inf in influencer:
                self.add_influencer(inf, denormalize, save_to_redis, **kwargs)
            return

        created = False
        influencer = get_model_instance(influencer, Influencer)

        q = self.influencers_mapping.filter(influencer=influencer)
        if q.exists():
            for mapping in q:
                if mapping.status == mapping.STATUS_REMOVED:
                    created = True
                mapping.status = mapping.STATUS_ADDED
                mapping.notes = kwargs.get('note')
                mapping.save()
        else:
            self.influencers_mapping.create(
                influencer=influencer, notes=kwargs.get('note')
            )
            created = True

        if created:
            # adding this group_id to influencer's 'tags' list in ES index
            influencer_add_tag(influencer.id, self.id)
            if denormalize:
                self.denormalize()
            if save_to_redis:
                InfluencersGroup.objects.add_influencer_to_redis(
                    [self.id, ], [influencer.id, ]
                )

        self.handle_automatic_blacklisting(influencer)
        return created

    def remove_influencer(self, influencer, denormalize=True, save_to_redis=True, **kwargs):
        from debra.helpers import get_model_instance

        if isinstance(influencer, list):
            for inf in influencer:
                self.remove_influencer(inf, denormalize, save_to_redis, **kwargs)
            return

        removed = False
        influencer = get_model_instance(influencer, Influencer)

        q = self.influencers_mapping.filter(influencer=influencer)
        if q.exists():
            for mapping in q:
                if mapping.status != mapping.STATUS_REMOVED:
                    removed = True
                mapping.status = mapping.STATUS_REMOVED
                mapping.save()
            self.handle_automatic_blacklisting(influencer)

        if removed:
            # removing this group_id from influencer's 'tags' list in ES index
            result = influencer_remove_tag(influencer.id, self.id)
            if denormalize:
                self.denormalize()
            if save_to_redis:
                InfluencersGroup.objects.remove_influencer_from_redis([self.id], [influencer.id])

        return removed

    def handle_automatic_blacklisting(self, influencer):
        """
        collections inside atul_44@yahoo.com user account are created only for data quality checks.
        So if an influencer is added to any collection inside this account, it is automatically blacklisted.
        And if an influencer is removed from any collection inside this account, we check if it can be moved back
        to blacklisted=False world if it doesn't already exist in other collections in this account.
        """
        if 'Blacklist --' in self.name:
            q = self.influencers_mapping.filter(influencer=influencer)
            # either it exists in STATUS_REMOVED or STATUS_ADDED
            assert q.filter(status=InfluencerGroupMapping.STATUS_REMOVED).exists() or q.filter(status=InfluencerGroupMapping.STATUS_ADDED).exists()

            if q.filter(status=InfluencerGroupMapping.STATUS_REMOVED).exists():
                # influencer was removed, now check other collections
                collections = influencer.group_mapping.all().exclude(group__id=self.id).filter(group__name__icontains='Blacklist --')
                exists_in_collections = collections.filter(status=InfluencerGroupMapping.STATUS_ADDED)
                if exists_in_collections.exists():
                    # still exists in other blacklist collections, so pass
                    if not influencer.blacklisted:
                        influencer.set_blacklist_with_reason(exists_in_collections[0].group.name)
                else:
                    # perfect, it's clean now. So, let's remove the blacklist flag
                    influencer.blacklisted = False
                    influencer.blacklist_reasons = None
                    influencer.save()
            if q.filter(status=InfluencerGroupMapping.STATUS_ADDED).exists():
                # influencer was added to this collection, so blacklist it now
                influencer.set_blacklist_with_reason(self.name)

    @classmethod
    def cleanup_system_collections(cls):
        InfluencersGroup.objects.filter(system_collection=True, job_post__isnull=True).delete()

    # def save(self, *args, **kwargs):
    #     if not "skip_sync" in kwargs:
    #         try:
    #             self.job_post.title = self.name
    #             self.job_post.save(skip_sync=True)
    #         except BrandJobPost.DoesNotExist:
    #             pass
    #     if "skip_sync" in kwargs:
    #         del kwargs["skip_sync"]
    #     return super(InfluencersGroup, self).save(*args, **kwargs)

    @property
    def invited_count(self):
        invited_statuses = (
            InfluencerGroupMapping.STATUS_INVITED,
            InfluencerGroupMapping.STATUS_EMAIL_RECEIVED,
            InfluencerGroupMapping.STATUS_VISITED,
        )
        invited = 0
        for m in self.influencers_mapping.all():
            if m.status in invited_statuses:
                invited += 1
        return invited

    @property
    def bloggers_count(self):
        return len(self.influencers)

    @property
    def applied_count(self):
        applied = 0
        for m in self.influencers_mapping.all():
            if m.status == InfluencerGroupMapping.STATUS_ACCEPTED:
                applied += 1
        return applied

    @property
    def influencers(self):
        return list(set(map(lambda x, self=self: x.influencer, filter(
            lambda x: x.status != InfluencerGroupMapping.STATUS_REMOVED,
            self.influencers_mapping.all())
        )))

    @property
    def influencer_ids(self):
        return list(set(self.influencers_mapping.exclude(
            status=InfluencerGroupMapping.STATUS_REMOVED
        ).values_list('influencer', flat=True)))

    @property
    def page_url(self):
        return "{}#/main_search/tag/{}".format(reverse(
            'debra.search_views.main_search'), self.id)

    @property
    def new_brand(self):
        pass

    @new_brand.setter
    def new_brand(self, value):
        from debra.helpers import create_tag_copy_for_brand

        brand_id = int(value)
        create_tag_copy_for_brand(self.id, brand_id)


class InfluencerGroupMapping(models.Model):
    STATUS_ADDED = 0
    STATUS_REMOVED = 1

    # backward compat
    STATUS_UNKNOWN = 2
    STATUS_NON_INVITED = 3
    STATUS_INVITED = 4
    STATUS_EMAIL_RECEIVED = 5
    STATUS_VISITED = 6
    STATUS_ACCEPTED = 7

    STATUS = (
        (STATUS_ADDED, 'Mapping exists'),
        (STATUS_REMOVED, 'Mapping is hidden'),


        (STATUS_UNKNOWN, 'Unknown'),
        (STATUS_NON_INVITED, 'Not invited yet'),
        (STATUS_INVITED, 'Blogger invited'),
        (STATUS_EMAIL_RECEIVED, 'Blogger received email'),
        (STATUS_VISITED, 'Blogger visited invitation page'),
        (STATUS_ACCEPTED, 'Blogger accepted invitation'),
    )

    influencer = models.ForeignKey('Influencer', related_name="group_mapping")
    group = models.ForeignKey('InfluencersGroup', related_name="influencers_mapping", null=True, blank=True)
    last_update = models.DateTimeField(auto_now=True, null=True, blank=True)
    mailbox = models.ForeignKey('MailProxy', null=True, blank=True, related_name='mapping')

    # we can safely remove it when new job-collection-influencer logic is settled
    status = models.IntegerField(null=True, default=STATUS_ADDED, choices=STATUS)
    notes = models.TextField(null=True)

    def __unicode__(self):
        return "Mapping %s to %s" % (str(self.influencer), str(self.group))

    def job_status(self, for_job):
        for job_mapping in self.jobs.all():
            if job_mapping.job == for_job:
                return job_mapping
        return None

    @property
    def mails(self):
        mails = short_cache.get('%i_igm_mails_cache' % self.id)
        if mails is not None:
            return mails
        mails = MailProxyMessage.objects
        q = []
        if self.mailbox:
            q.append(Q(thread=self.mailbox))
        if self.jobs:
            q.append(Q(thread__in=[x.mailbox for x in self.jobs.all() if x.mailbox]))
        if q:
            mails = mails.filter(reduce(lambda x, y: x | y, q))
            mails = mails.exclude(mandrill_id='.')
            mails = list(mails.order_by('ts').only(
                'id', 'ts', 'type', 'direction').values('id', 'ts', 'type', 'direction'))
        else:
            mails = []
        short_cache.set('%i_igm_mails_cache' % self.id, mails)
        return mails

    @property
    def status_verbose(self):
        return dict(InfluencerGroupMapping.STATUS).get(self.status)

    @property
    def can_invite(self):
        return self.status == InfluencerGroupMapping.STATUS_NON_INVITED

    def get_or_create_mailbox(self):
        if not self.mailbox:
            self.mailbox = MailProxy.create_box(brand=self.group.creator_brand, influencer=self.influencer)
            self.save()
        return self.mailbox

    @property
    def reply_stamp(self):
        if self.mails:
            return self.mails[-1]["ts"]
        return None

    @property
    def opened_count(self):
        count = 0
        for th in self.mails:
            if th["type"] in (MailProxyMessage.TYPE_OPEN, MailProxyMessage.TYPE_CLICK):
                count += 1
        return count

    @property
    def post_stamp(self):
        if self.mails:
            return self.mails[0]["ts"]
        return None

    @property
    def emails_count(self):
        count = 0
        for m in self.mails:
            if m["type"] == MailProxyMessage.TYPE_EMAIL:
                count += 1
        return count


class ExtendedInfluencerJobMappingManager(models.Manager):

    def with_influencer(self, influencer):
        q_list = [
            Q(mailbox__influencer=influencer),
            Q(mapping__influencer=influencer)
        ]
        return self.filter(reduce(OR, q_list))


class InfluencerBrandUserMapping(models.Model):
    influencer = models.ForeignKey(
        'Influencer', related_name="brand_mappings", null=True, blank=True)
    brand = models.ForeignKey(
        'Brands', related_name="influencer_mappings", null=True, blank=True)
    user = models.ForeignKey(
        User, related_name="influencer_mappings", null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = (
            ('influencer', 'brand', 'user'),
        )


class InfluencerBrandMapping(models.Model):
    SEX_FEMALE = 1
    SEX_MALE = 2
    SEX_TRANSGENDER = 3

    SEX = (
        (SEX_FEMALE, 'Female'),
        (SEX_MALE, 'Male'),
        (SEX_TRANSGENDER, 'Transgender'),
    )

    influencer = models.ForeignKey(
        'Influencer', null=True, blank=True)
    brand = models.ForeignKey(
        'Brands', null=True, blank=True)

    # SOCIAL / URLs
    name = models.CharField(max_length=1000, null=True) # duplicate of Influencer.name
    blogname = models.CharField(max_length=1000, null=True) # duplicate of Influencer.blogname
    blog_url = models.CharField(max_length=1000, null=True)
    email = models.CharField(max_length=1000, null=True) # duplicate of Influencer.email

    insta_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    youtube_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    snapchat_username = models.CharField(max_length=1000, null=True, blank=True, default=None)
    tw_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    fb_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    pin_url = models.URLField(max_length=1000, null=True, blank=True, default=None)

    # CONTRACT FIELDS
    cell_phone = models.CharField(max_length=1000, null=True)
    representation = models.CharField(max_length=1000, null=True)
    rep_email_address = models.CharField(max_length=1000, null=True)
    rep_phone = models.CharField(max_length=1000, null=True)

    #LOCATION
    language = TextArrayField(null=True, default=[])
    zip_code = models.CharField(max_length=1000, null=True)
    mailing_address = models.CharField(max_length=1000, null=True)

    #CHARACTERISTICS
    categories = TextArrayField(null=True, default=[])
    occupation = TextArrayField(null=True, default=[])
    ethnicity = TextArrayField(null=True, default=[])
    tags = TextArrayField(null=True, default=[])
    # sex = models.IntegerField(null=True, default=SEX_MALE, choices=SEX)
    sex = TextArrayField(null=True, default=[])
    age = models.IntegerField(null=True)
    date_of_birth = models.DateField(null=True)
    notes = models.TextField(null=True, blank=True)

    last_modified = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = (
            ('influencer', 'brand'),
        )

    @classmethod
    def get_metadata(cls):
        return site_configurator.instance.blogger_custom_data_json


class Contract(PostSaveTrackableMixin, models.Model):

    _POST_SAVE_TRACKABLE_FIELDS = ['product_urls']

    STATUS_NON_SENT = 0
    STATUS_SENT = 1
    STATUS_DELIVERED = 2
    STATUS_SIGNED = 3
    STATUS_DECLINED = 4
    STATUS_VOIDED = 5

    STATUS = (
        (STATUS_NON_SENT, 'Not sent'),
        (STATUS_SENT, 'Pending'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_SIGNED, 'Complete'),
        (STATUS_DECLINED, 'Declined'),
        (STATUS_VOIDED, 'Voided'),
    )

    STATUS_COLOR = (
        (STATUS_NON_SENT, 'black'),
        (STATUS_SENT, '#13d1fa'),
        (STATUS_DELIVERED, 'blue'),
        (STATUS_SIGNED, 'green'),
        (STATUS_DECLINED, 'red'),
        (STATUS_VOIDED, 'grey'),
    )

    TRACKING_STATUS_SKIPPED = -1
    TRACKING_STATUS_NON_SENT = 0
    TRACKING_STATUS_SENT = 1
    TRACKING_STATUS_ADDED = 2
    TRACKING_STATUS_VERIFICATION_PROBLEM = 3
    TRACKING_STATUS_VERIFYING = 4

    TRACKING_STATUS = (
        (TRACKING_STATUS_SKIPPED, 'Skipped'),
        (TRACKING_STATUS_NON_SENT, 'Not sent'),
        (TRACKING_STATUS_SENT, 'Pending'),
        (TRACKING_STATUS_ADDED, 'Complete'),
        (TRACKING_STATUS_VERIFICATION_PROBLEM, 'Verification problem'),
        (TRACKING_STATUS_VERIFYING, 'Pending'),
    )

    TRACKING_STATUS_COLOR = (
        (TRACKING_STATUS_SKIPPED, 'black'),
        (TRACKING_STATUS_NON_SENT, 'black'),
        (TRACKING_STATUS_SENT, 'blue'),
        (TRACKING_STATUS_ADDED, 'green'),
        (TRACKING_STATUS_VERIFICATION_PROBLEM, 'red'),
        (TRACKING_STATUS_VERIFYING, 'grey'),
    )

    POSTS_ADDING_STATUS_SKIPPED = -1
    POSTS_ADDING_STATUS_NON_SENT = 0
    POSTS_ADDING_STATUS_SENT = 1
    POSTS_ADDING_STATUS_DONE = 2

    POSTS_ADDING_STATUS = [
        (POSTS_ADDING_STATUS_SKIPPED, 'Skipped'),
        (POSTS_ADDING_STATUS_NON_SENT, 'Not sent'),
        (POSTS_ADDING_STATUS_SENT, 'Pending'),
        (POSTS_ADDING_STATUS_DONE, 'Complete'),
    ]

    POSTS_ADDING_STATUS_COLOR = [
        (POSTS_ADDING_STATUS_SKIPPED, 'black'),
        (POSTS_ADDING_STATUS_NON_SENT, 'black'),
        (POSTS_ADDING_STATUS_SENT, 'blue'),
        (POSTS_ADDING_STATUS_DONE, 'green'),
    ]

    PAYPAL_INFO_STATUS_NON_SENT = 0
    PAYPAL_INFO_STATUS_SENT = 1
    PAYPAL_INFO_STATUS_DONE = 2

    PAYPAL_INFO_STATUS = [
        (PAYPAL_INFO_STATUS_NON_SENT, 'Not sent'),
        (PAYPAL_INFO_STATUS_SENT, 'Pending'),
        (PAYPAL_INFO_STATUS_DONE, 'Complete'),
    ]

    PAYPAL_INFO_STATUS_COLOR = [
        (PAYPAL_INFO_STATUS_NON_SENT, 'black'),
        (PAYPAL_INFO_STATUS_SENT, 'blue'),
        (PAYPAL_INFO_STATUS_DONE, 'green'),
    ]

    CAMPAIGN_STAGE_PRE_OUTREACH = 0
    CAMPAIGN_STAGE_WAITING_ON_RESPONSE = 1
    CAMPAIGN_STAGE_NEGOTIATION = 2
    CAMPAIGN_STAGE_FINALIZING_DETAILS = 3
    CAMPAIGN_STAGE_CONTRACTS = 4
    CAMPAIGN_STAGE_LOGISTICS = 5
    CAMPAIGN_STAGE_UNDERWAY = 6
    CAMPAIGN_STAGE_COMPLETE = 7
    CAMPAIGN_STAGE_ARCHIVED = 8

    CAMPAIGN_STAGE = [
        (CAMPAIGN_STAGE_PRE_OUTREACH, 'Pre-Outreach'),
        (CAMPAIGN_STAGE_WAITING_ON_RESPONSE, 'No Response'),
        (CAMPAIGN_STAGE_NEGOTIATION, 'Negotiation'),
        (CAMPAIGN_STAGE_FINALIZING_DETAILS, 'Logistics'),
        # (CAMPAIGN_STAGE_CONTRACTS, 'Contracts'),
        # (CAMPAIGN_STAGE_LOGISTICS, 'Logistics'),
        (CAMPAIGN_STAGE_UNDERWAY, 'Underway'),
        (CAMPAIGN_STAGE_COMPLETE, 'Complete'),
        (CAMPAIGN_STAGE_ARCHIVED, 'Archived'),
    ]

    DETAILS_COLLECTED_STATUS_SKIPPED = -1
    DETAILS_COLLECTED_STATUS_NON_SENT = 0
    DETAILS_COLLECTED_STATUS_SENT = 1
    DETAILS_COLLECTED_STATUS_DONE = 2

    DETAILS_COLLECTED_STATUS = [
        (DETAILS_COLLECTED_STATUS_SKIPPED, 'Skipped'),
        (DETAILS_COLLECTED_STATUS_NON_SENT, 'Not sent'),
        (DETAILS_COLLECTED_STATUS_SENT, 'Pending'),
        (DETAILS_COLLECTED_STATUS_DONE, 'Complete'),
    ]

    DETAILS_COLLECTED_STATUS_COLOR = [
        (DETAILS_COLLECTED_STATUS_SKIPPED, 'black'),
        (DETAILS_COLLECTED_STATUS_NON_SENT, 'black'),
        (DETAILS_COLLECTED_STATUS_SENT, 'blue'),
        (DETAILS_COLLECTED_STATUS_DONE, 'green'),
    ]

    SHIPMENT_STATUS_SKIPPED = -1
    SHIPMENT_STATUS_NON_SENT = 0
    SHIPMENT_STATUS_SENT = 1
    SHIPMENT_STATUS_DONE = 2

    SHIPMENT_STATUS = [
        (SHIPMENT_STATUS_SKIPPED, 'Skipped'),
        (SHIPMENT_STATUS_NON_SENT, 'Not sent'),
        (SHIPMENT_STATUS_SENT, 'Pending'),
        (SHIPMENT_STATUS_DONE, 'Complete'),
    ]

    SHIPMENT_STATUS_COLOR = [
        (SHIPMENT_STATUS_SKIPPED, 'black'),
        (SHIPMENT_STATUS_NON_SENT, 'black'),
        (SHIPMENT_STATUS_SENT, 'blue'),
        (SHIPMENT_STATUS_DONE, 'green'),
    ]

    FOLLOWUP_STATUS_SKIPPED = -1
    FOLLOWUP_STATUS_NON_SENT = 0
    FOLLOWUP_STATUS_SENT = 1
    FOLLOWUP_STATUS_DONE = 2

    FOLLOWUP_STATUS = [
        (FOLLOWUP_STATUS_SKIPPED, 'Skipped'),
        (FOLLOWUP_STATUS_NON_SENT, 'Not sent'),
        (FOLLOWUP_STATUS_SENT, 'Pending'),
        (FOLLOWUP_STATUS_DONE, 'Complete'),
    ]

    FOLLOWUP_STATUS_COLOR = [
        (FOLLOWUP_STATUS_SKIPPED, 'black'),
        (FOLLOWUP_STATUS_NON_SENT, 'black'),
        (FOLLOWUP_STATUS_SENT, 'blue'),
        (FOLLOWUP_STATUS_DONE, 'green'),
    ]

    GOOGLE_DOC_STATUS_SKIPPED = -1
    GOOGLE_DOC_STATUS_NON_SENT = 0
    GOOGLE_DOC_STATUS_SENT = 1
    GOOGLE_DOC_STATUS_DONE = 2

    GOOGLE_DOC_STATUS = [
        (GOOGLE_DOC_STATUS_SKIPPED, 'Skipped'),
        (GOOGLE_DOC_STATUS_NON_SENT, 'Not sent'),
        (GOOGLE_DOC_STATUS_SENT, 'Pending'),
        (GOOGLE_DOC_STATUS_DONE, 'Complete'),
    ]

    GOOGLE_DOC_STATUS_COLOR = [
        (GOOGLE_DOC_STATUS_SKIPPED, 'black'),
        (GOOGLE_DOC_STATUS_NON_SENT, 'black'),
        (GOOGLE_DOC_STATUS_SENT, 'blue'),
        (GOOGLE_DOC_STATUS_DONE, 'green'),
    ]


    # influencer_analytics = models.OneToOneField(
    #     'InfluencerAnalytics', null=True)

    campaign_stage = models.IntegerField(
        null=True, default=CAMPAIGN_STAGE_PRE_OUTREACH, choices=CAMPAIGN_STAGE)
    moved_manually = models.NullBooleanField(null=True)
    status = models.IntegerField(
        default=STATUS_SENT, choices=STATUS, null=True)
    envelope = models.CharField(max_length=1000, null=True)
    starting_price = models.IntegerField(default=0, null=True)
    suggested_price = models.IntegerField(default=0, null=True)
    negotiated_price = models.IntegerField(null=True)
    influencer_notes = models.TextField(null=True, default="")
    deliverables = models.TextField(null=True, default="")
    extra_details = models.TextField(null=True, default="")
    rating = models.IntegerField(null=True, default=0)
    review = models.TextField(null=True, default="")
    start_date = models.DateField(null=True, blank=True)
    latest_date = models.DateField(null=True, blank=True)
    date_requirements = models.DateField(null=True, blank=True)
    blogger_address = models.CharField(max_length=1000, null=True, default="")
    shipment_tracking_code = models.CharField(max_length=1000, null=True, default="")
    ship_date = models.DateField(null=True, blank=True)
    shipment_status = models.IntegerField(null=True, default=0)
    followup_status = models.IntegerField(null=True, default=0)
    shipment_received_date = models.DateTimeField(null=True, blank=True)
    info = models.TextField(null=True, default="")

    tracking_link = models.CharField(max_length=1000, null=True)
    tracking_brand_link = models.CharField(max_length=1000, null=True)
    tracking_pixel = models.CharField(max_length=1000, null=True)
    product_tracking_links = TextArrayField(null=True, default=[])
    campaign_product_tracking_links = TextArrayField(null=True, default=[])

    product_url = models.CharField(max_length=1000, null=True)
    product_urls = TextArrayField(null=True, default=[])

    google_doc_id = models.CharField(max_length=1000, null=True)

    google_doc_status = models.IntegerField(
        default=GOOGLE_DOC_STATUS_NON_SENT,
        null=True, choices=GOOGLE_DOC_STATUS)
    tracking_status = models.IntegerField(
        default=TRACKING_STATUS_NON_SENT, null=True, choices=TRACKING_STATUS)
    posts_adding_status = models.IntegerField(
        default=POSTS_ADDING_STATUS_NON_SENT, null=True,
        choices=POSTS_ADDING_STATUS)
    paypal_info_status = models.IntegerField(
        default=PAYPAL_INFO_STATUS_NON_SENT, null=True,
        choices=PAYPAL_INFO_STATUS)
    details_collected_status = models.IntegerField(
        null=True, default=DETAILS_COLLECTED_STATUS_NON_SENT,
        choices=DETAILS_COLLECTED_STATUS)
    payment_complete = models.NullBooleanField(null=True)

    def generate_google_doc(self):
        from debra.google_api import build_service
        if self.google_doc_id is None:
            try:
                service = build_service()
                file_data = service.files().insert(body={
                    'mimeType': 'application/vnd.google-apps.document',
                    'title': "{}: {}".format(
                        self.campaign.title, self.publisher_name),
                }).execute()
                permission_data = service.permissions().insert(
                    fileId=file_data['id'],
                    body={
                        'type': 'anyone',
                        'role': 'writer',
                        'withLink': True,
                        'value': '',
                    }
                ).execute()
                self.google_doc_id = file_data['id']
                self.save()
            except:
                account_helpers.send_msg_to_slack(
                    'google-doc-create',
                    "{asterisks}\n"
                    "Contract = {contract_id}\n"
                    "{asterisks}\n"
                    "{traceback}\n"
                    "{delimiter}"
                    "\n".format(
                        contract_id=self.id,
                        asterisks="*" * 120,
                        delimiter="=" * 120,
                        traceback=traceback.format_exc(),
                    )
                )

    def get_docusign_field_value(self, document_id, name):
        value = self.info_json.get(str(document_id), {}).get(name)
        if value is None:
            value = self.docusign_documents[str(document_id)]['fields'].get(
                name)
            try:
                value = eval(value)(self)
            except:
                value = None
        return value

    def get_docusign_page_offsets(self, document_id):
        return self.campaign.get_docusign_page_offsets(document_id)

    def get_datapoint_name(self, datapoint_id):
        result = clickmeter_api.get(
            '/datapoints/{}'.format(datapoint_id), {}).json()
        return result.get('name')

    def update_tracking_link(self):
        datapoint_id = self.tracking_link
        if datapoint_id:
            data = {
                'id': int(datapoint_id),
                'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                'groupId': int(self.campaign.tracking_group or self.campaign.id),
                'preferred': True,
                'name': self.get_datapoint_name(datapoint_id),
                'title': u"'{}' campaign for {}".format(
                    self.campaign.title, self.id),
                'typeTL': {
                    'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                    'url': self.influencerjobmapping.product_url,
                    'redirectType': 301,
                }
            }
            response = clickmeter_api.post(
                '/datapoints/{}'.format(datapoint_id), data=data).json()

    def generate_tracking_link(self, to_save=True):
        print '* generate tracking link'
        self.campaign.generate_tracking_group()
        if not self.tracking_link and self.influencerjobmapping.product_url:
            tracking_link_name = uuid4()
            tracking_link_data = {
                'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                'groupId': self.campaign.tracking_group or self.campaign.id,
                'name': '{}'.format(tracking_link_name),
                'title': u"'{}' campaign for {}".format(
                    self.campaign.title, self.id),
                'type': 0,
                'typeTL': {
                    'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                    'url': self.influencerjobmapping.product_url,
                    'redirectType': 301,
                },
            }
            tracking_link_response = clickmeter_api.post(
                '/datapoints', data=tracking_link_data).json()
            print '*', tracking_link_response
            try:
                self.tracking_link = tracking_link_response['id']
            except KeyError:
                pass
            if to_save:
                self.save()

    def generate_tracking_brand_link(self, to_save=True):
        print '* generate tracking brand link'
        self.campaign.generate_tracking_group()
        if not self.tracking_brand_link and self.campaign.client_url:
            tracking_brand_link_name = uuid4()
            tracking_brand_link_data = {
                'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                'groupId': self.campaign.tracking_group or self.campaign.id,
                'name': '{}'.format(tracking_brand_link_name),
                'title': u"'{}' campaign for {} (brand link)".format(
                    self.campaign.title, self.id),
                'type': 0,
                'typeTL': {
                    'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                    'url': self.campaign.client_url,
                    'redirectType': 301,
                },
            }
            tracking_brand_link_response = clickmeter_api.post(
                '/datapoints', data=tracking_brand_link_data).json()
            print '*', tracking_brand_link_response
            try:
                self.tracking_brand_link = tracking_brand_link_response['id']
            except KeyError:
                pass
            if to_save:
                self.save()

    def generate_tracking_pixel(self, to_save=True):
        print '* generate tracking pixel'
        self.campaign.generate_tracking_group()
        if not self.tracking_pixel:
            tracking_pixel_name = uuid4()
            tracking_pixel_data = {
                'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                'groupId': self.campaign.tracking_group or self.campaign.id,
                'name': '{}'.format(tracking_pixel_name),
                'title': u"'{}' campaign for {}".format(
                    self.campaign.title, self.id),
                'type': 1,
            }
            tracking_pixel_response = clickmeter_api.post(
                '/datapoints', data=tracking_pixel_data).json()
            print '*', tracking_pixel_response
            try:
                self.tracking_pixel = tracking_pixel_response['id']
            except KeyError:
                pass
            if to_save:
                self.save()

    def generate_tracking_info(self):
        print '* generate tracking info'
        self.campaign.generate_tracking_group()
        # self.generate_tracking_link(to_save=False)
        self.generate_tracking_brand_link(to_save=False)
        self.generate_tracking_pixel(to_save=False)
        self.save()

    # def reset_tracking_info(self):
    #     self.tracking_link = None
    #     self.tracking_brand_link = None
    #     self.tracking_pixel = None
    #     self.tracking_status = self.TRACKING_STATUS_NON_SENT
    #     self.save()

    def set_info(self, key, value):
        info_json = self.info_json
        info_json[key] = value
        self.info = json.dumps(info_json)

    def get_info(self, key, default=None):
        return self.info_json.get(key, default)

    def load_info_json(self):
        try:
            self._cached_info_json = json.loads(self.info)
        except:
            self._cached_info_json = {}

    @property
    def google_doc_embed_url(self):
        if self.google_doc_id:
            return 'https://docs.google.com/document/d/{}/edit?embedded=true'.format(
                self.google_doc_id)

    @property
    def rate_type(self):
        f = self.negotiated_price
        d = self.info_json.get('displayed_rate')

        if f is None or f == 0:
            if d:
                return 'displayed_rate'
            else:
                return 'hidden'
        else:
            if d:
                return 'displayed_rate'
            else:
                return 'final_rate'

    @property
    def product_datapoints(self):
        return zip(self.product_tracking_links, self.product_urls)

    @property
    def ship_date_value(self):
        return self.ship_date or datetime.now().date()

    @property
    def payment_method(self):
        return self.info_json.get('payment_method', 'PayPal')

    @property
    def default_subject(self):
        if self.campaign.outreach_template_json.get('subject'):
            return self.campaign.outreach_template_json.get('subject')
        else:
            return ''

    @property
    def post_requirements(self):
        if self.extra_details:
            return self.extra_details
        return self.campaign.post_requirements

    @property
    def deliverables_json(self):
        try:
            return eval(self.deliverables)
        except:
            return self.campaign.info_json.get('deliverables', {})

    @property
    def deliverables_text(self):
        return "\n".join(
            "{} {}".format(
                data.get('value', 0),
                data.get('plural') if data.get('value', 0) > 1 else data.get('single')
            ) for name, data in self.deliverables_json.items()
            if data.get('value')
        )

    @property
    def deliverables_lines(self):
        lines = [
            line for line in self.deliverables_text.split('\n') if len(line) > 0
        ]
        return {n:line for n, line in enumerate(lines, start=1)}

    @property
    def displayed_rate_lines(self):
        if self.rate_type == 'displayed_rate':
            lines = [
                line for line in self.info_json.get('displayed_rate').split('\n') if len(line) > 0
            ]
        elif self.rate_type == 'final_rate':
            lines = ['${}'.format(self.negotiated_price)]
        else:
            lines = []
        return {n:line for n, line in enumerate(lines, start=1)}

    @property
    def payment_terms(self):
        try:
            return self.info_json['payment_terms']
        except KeyError:
            return self.campaign.payment_terms
            # return 'within 15 days of the last required post going live'

    @property
    def payment_terms_lines(self):
        if self.payment_terms is None:
            return {}
        lines = [x for x in self.payment_terms.split('\n') if x]
        return {n:x for n, x in enumerate(lines, start=1)}

    @property
    def info_json(self):
        try:
            self._cached_info_json
        except AttributeError:
            self.load_info_json()
        return self._cached_info_json

    @property
    def docusign_documents(self):
        return self.campaign.docusign_documents

    @property
    def is_tracking_info_generated(self):
        return all([
            # self.tracking_link is not None if self.campaign.info_json.get('sending_product_on') and self.influencerjobmapping.product_url else True,
            self.tracking_pixel is not None,
            self.tracking_brand_link is not None if self.campaign.client_url else True,
        ])

    @property
    def tracking_status_name(self):
        return dict(self.TRACKING_STATUS).get(self.tracking_status)

    @property
    def tracking_status_color(self):
        return dict(self.TRACKING_STATUS_COLOR).get(self.tracking_status)

    @property
    def paypal_info_status_name(self):
        return dict(self.PAYPAL_INFO_STATUS).get(self.paypal_info_status)

    @property
    def paypal_info_status_color(self):
        return dict(self.PAYPAL_INFO_STATUS_COLOR).get(self.paypal_info_status)

    @property
    def posts_adding_status_name(self):
        return dict(self.POSTS_ADDING_STATUS).get(self.posts_adding_status)

    @property
    def posts_adding_status_color(self):
        return dict(self.POSTS_ADDING_STATUS_COLOR).get(
            self.posts_adding_status)

    @property
    def google_doc_status_name(self):
        return dict(self.GOOGLE_DOC_STATUS).get(self.google_doc_status)

    @property
    def google_doc_status_color(self):
        return dict(self.GOOGLE_DOC_STATUS_COLOR).get(
            self.google_doc_status)

    @property
    def tracking_hash_key(self):
        key = '/'.join([
            str(self.id),
            str(self.blogger.id),
            str(self.campaign.id),
            # str(self.tracking_link),
            # str(self.tracking_pixel),
        ])
        return hashlib.md5(key).hexdigest()

    @property
    def blogger_tracking_url(self):
        return ''.join([
            constants.MAIN_DOMAIN,
            reverse(
                'debra.job_posts_views.blogger_tracking_page',
                args=(self.id, self.tracking_hash_key,)
            ),
        ])

    @property
    def blogger_shipment_received_url(self):
        return ''.join([
            constants.MAIN_DOMAIN,
            reverse(
                'debra.job_posts_views.blogger_shipment_received',
                args=(self.id, self.blogger.date_created_hash,)
            ),
        ])

    @property
    def address_lines(self):
        if self.blogger_address is None:
            return {}
        lines = [x for x in self.blogger_address.split('\n') if x]
        return {n:x for n, x in enumerate(lines, start=1)}

    @property
    def docusign_template(self):
        return self.campaign.docusign_template

    @property
    def campaign(self):
        try:
            return self.agr_campaign
        except AttributeError:
            return self.influencerjobmapping.job

    @property
    def mailbox(self):
        return self.influencerjobmapping.mailbox

    @property
    def brand(self):
        return self.influencerjobmapping.job.creator

    @property
    def client_name(self):
        """
        This is the Client name for the campaign. For a brand, the client name is same as the job.creator.
        For an agency, it could be different and we will use job.client_name
        """
        return self.influencerjobmapping.job.client_name

    @property
    def blogger(self):
        return self.influencerjobmapping.influencer

    @property
    def influencer(self):
        return self.blogger

    @property
    def status_name(self):
        return dict(self.STATUS).get(self.status or 1)

    @property
    def status_color(self):
        return dict(self.STATUS_COLOR).get(self.status or 1)

    @property
    def publisher_name(self):
        from debra.serializers import unescape
        if self.info_json.get('publisher_name'):
            publisher_name = self.info_json.get('publisher_name')
        elif self.blogger.name and self.blogger.blogname:
            publisher_name = u'{} of {}'.format(
                self.blogger.name, self.blogger.blogname)
        else:
            if self.blogger.name:
                publisher_name = self.blogger.name
            else:
                publisher_name = self.blogger.blogname
        return unescape(publisher_name if publisher_name else 'No name')

    @property
    def link(self):
        return ''.join([
            constants.MAIN_DOMAIN,
            self.url,
        ])

    @property
    def url(self):
        return reverse(
            'debra.job_posts_views.contract_signing_view',
            args=(
                self.id,
                self.blogger.date_created_hash
            )
        )

    @property
    def signed_document(self):
        from debra.docusign import client
        if self.envelope is None:
            return None
        raw = client.get_envelope_document(
            envelopeId=self.envelope, documentId='1')
        return raw.data

    @property
    def signed_document_url(self):
        return reverse(
            'debra.job_posts_views.download_contract_document',
            args=(self.id,)
        )

    @property
    def preview_document_url(self):
        return reverse(
            'debra.job_posts_views.download_contract_document_preview',
            args=(self.id,)
        )

    @property
    def date_start(self):
        if self.start_date and self.latest_date:
            return self.start_date
        return self.campaign.date_start

    @property
    def date_end(self):
        if self.start_date and self.latest_date:
            return self.latest_date
        return self.campaign.date_end

    @property
    def can_view(self):
        return self.status in [self.STATUS_SENT, self.STATUS_DELIVERED]

    @property
    def can_download(self):
        return self.status in [self.STATUS_SIGNED]

    @property
    def tracking_pixel_snippet(self):
        clickmeter_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Clickmeter-Authkey': constants.CLICKMETER_API_KEY,
        }

        pixel_datapoint = requests.get(
            constants.CLICKMETER_BASE_URL + '/datapoints/' + str(self.tracking_pixel),
            headers=clickmeter_headers
        ).json()

        pixel_snippet = (
            "<script type='text/javascript'>" +
            "var ClickMeter_pixel_url = '{link}';" +
            "</script>" +
            "<script type='text/javascript' id='cmpixelscript' src='//s3.amazonaws.com/scripts-clickmeter-com/js/pixelNew.js'></script>" +
            "<noscript>" +
            "<img height='0' width='0' alt='' src='{link}' />" +
            "</noscript>").format(link=pixel_datapoint['trackingCode'])

        return pixel_snippet

    @property
    def tracking_link_url(self):
        clickmeter_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Clickmeter-Authkey': constants.CLICKMETER_API_KEY,
        }

        link_datapoint = requests.get(
            constants.CLICKMETER_BASE_URL + '/datapoints/' + str(self.tracking_link),
            headers=clickmeter_headers
        ).json()

        return '{}'.format(
            link_datapoint['trackingCode'],
            # urllib.urlencode({
            #     'utm_source': self.campaign.utm_source,
            #     'utm_medium': self.campaign.utm_medium,
            #     'utm_campaign': self.campaign.utm_campaign,
            # })
        )

    @property
    def tracking_brand_link_url(self):
        clickmeter_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Clickmeter-Authkey': constants.CLICKMETER_API_KEY,
        }

        link_datapoint = requests.get(
            constants.CLICKMETER_BASE_URL + '/datapoints/' + str(self.tracking_brand_link),
            headers=clickmeter_headers
        ).json()

        return '{}'.format(
            link_datapoint['trackingCode'],
            # urllib.urlencode({
            #     'utm_source': self.campaign.utm_source,
            #     'utm_medium': self.campaign.utm_medium,
            #     'utm_campaign': self.campaign.utm_campaign,
            # })
        )

    @property
    def tracking_product_urls(self):
        from debra.clickmeter import ClickMeterContractLinksHandler
        handler = ClickMeterContractLinksHandler(clickmeter_api, self)
        if self.campaign.info_json.get('same_product_url'):
            tracking_links = self.campaign_product_tracking_links
        else:
            tracking_links = self.product_tracking_links
        res = []
        for datapoint_id in tracking_links:
            entity = handler.datapoint_entries.get(int(datapoint_id))
            res.append(
                (entity.get('destinationUrl'), entity.get('trackingCode')))
        return filter(None, res)

    @property
    def blogger_posts(self):
        if self.campaign.bloggers_post_collection is None:
            return []
        posts = self.campaign.bloggers_post_collection.get_unique_post_analytics().filter(
            contract=self
        ).order_by('created')
        return [p.blogger_post for p in posts]

    @property
    def details_collected_status_name(self):
        return dict(self.DETAILS_COLLECTED_STATUS).get(
            self.details_collected_status)

    @property
    def details_collected_status_color(self):
        return dict(self.DETAILS_COLLECTED_STATUS_COLOR).get(
            self.details_collected_status)

    @property
    def shipment_status_name(self):
        return dict(self.SHIPMENT_STATUS).get(
            self.shipment_status)

    @property
    def shipment_status_color(self):
        return dict(self.SHIPMENT_STATUS_COLOR).get(
            self.shipment_status)

    @property
    def followup_status_name(self):
        return dict(self.FOLLOWUP_STATUS).get(
            self.followup_status or 0)

    @property
    def followup_status_color(self):
        return dict(self.FOLLOWUP_STATUS_COLOR).get(
            self.followup_status or 0)


class InfluencerJobMapping(PostSaveTrackableMixin, models.Model):
    _POST_SAVE_TRACKABLE_FIELDS = ['campaign_stage']

    # backward compat
    STATUS_UNKNOWN = 0
    STATUS_NON_INVITED = 1

    STATUS_INVITED = 2
    STATUS_EMAIL_RECEIVED = 3
    STATUS_VISITED = 4
    STATUS_ACCEPTED = 5

    STATUS_REMOVED = 6

    STATUS = (
        (STATUS_UNKNOWN, 'Unknown'),
        (STATUS_NON_INVITED, 'Not invited yet'),
        (STATUS_INVITED, 'Blogger invited'),
        (STATUS_EMAIL_RECEIVED, 'Blogger received email'),
        (STATUS_VISITED, 'Blogger visited invitation page'),
        (STATUS_ACCEPTED, 'Blogger accepted invitation'),
        (STATUS_REMOVED, 'Mapping is hidden'),
    )

    CAMPAIGN_STAGE_LOAD_INFLUENCERS = -3
    CAMPAIGN_STAGE_APPROVAL = -2
    CAMPAIGN_STAGE_ALL = -1
    CAMPAIGN_STAGE_PRE_OUTREACH = 0
    CAMPAIGN_STAGE_WAITING_ON_RESPONSE = 1
    CAMPAIGN_STAGE_NEGOTIATION = 2
    CAMPAIGN_STAGE_FINALIZING_DETAILS = 3
    CAMPAIGN_STAGE_CONTRACTS = 4
    CAMPAIGN_STAGE_LOGISTICS = 5
    CAMPAIGN_STAGE_UNDERWAY = 6
    CAMPAIGN_STAGE_COMPLETE = 7
    CAMPAIGN_STAGE_ARCHIVED = 8

    CAMPAIGN_STAGE = [
        (CAMPAIGN_STAGE_PRE_OUTREACH, 'Outreach'),
        (CAMPAIGN_STAGE_WAITING_ON_RESPONSE, 'Follow-up'),
        (CAMPAIGN_STAGE_NEGOTIATION, 'Discussion'),
        (CAMPAIGN_STAGE_FINALIZING_DETAILS, 'Collect Info'),
        (CAMPAIGN_STAGE_CONTRACTS, 'Contracts'),
        (CAMPAIGN_STAGE_LOGISTICS, 'Shipping'),
        (CAMPAIGN_STAGE_UNDERWAY, 'In Progress'),
        (CAMPAIGN_STAGE_COMPLETE, 'Complete'),
        (CAMPAIGN_STAGE_ARCHIVED, 'Archived'),
    ]

    SANDBOX_STAGES = [
        CAMPAIGN_STAGE_FINALIZING_DETAILS,
        CAMPAIGN_STAGE_CONTRACTS,
        CAMPAIGN_STAGE_LOGISTICS,
        CAMPAIGN_STAGE_UNDERWAY,
    ]

    mapping = models.ForeignKey(
        'InfluencerGroupMapping', related_name="jobs", null=True, blank=True)
    job = models.ForeignKey(BrandJobPost, related_name="candidates")
    mailbox = models.ForeignKey(
        'MailProxy', null=True, blank=True, related_name='candidate_mapping')
    contract = models.OneToOneField(
        'Contract', null=True, on_delete=models.SET_NULL)
    influencer_analytics = models.OneToOneField(
        'InfluencerAnalytics', null=True)

    moved_manually = models.NullBooleanField(null=True)
    status = models.IntegerField(default=STATUS_INVITED, choices=STATUS)
    campaign_stage = models.IntegerField(
        null=True, default=CAMPAIGN_STAGE_PRE_OUTREACH, choices=CAMPAIGN_STAGE)
    campaign_stage_prev = models.IntegerField(
        null=True, default=CAMPAIGN_STAGE_PRE_OUTREACH, choices=CAMPAIGN_STAGE)

    archived = models.NullBooleanField(default=False, null=True)

    # client_notes = models.TextField(null=True, blaye nk=True)

    objects = ExtendedInfluencerJobMappingManager()

    # @classmethod
    # def get_campaign_stage_criteria():

    #     _q = {
    #         IJM.CAMPAIGN_STAGE_PRE_OUTREACH: Q(mailbox__threads__isnull=False),
    #         IJM.CAMPAIGN_STAGE_WAITING_ON_RESPONSE: (
    #             Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
    #             Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL) &
    #             Q(mailbox__threads__direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND)
    #         ),
    #         IJM.CAMPAIGN_STAGE_NEGOTIATION: (
    #             Q(contract__negotiated_price__isnull=False) |
    #             Q()
    #         ),
    #     }

    #     return {
    #         IJM.CAMPAIGN_STAGE_PRE_OUTREACH: lambda ijm: Q(mailbox__threads__isnull=True),
    #         IJM.CAMPAIGN_STAGE_WAITING_ON_RESPONSE: None,
    #         CAMPAIGN_STAGE_NEGOTIATION: None,
    #         SANDBOX_STAGES: None,
    #         CAMPAIGN_STAGE_COMPLETE: None,
    #     }

    # def guess_campaign_stage(self):
    #     if self.campaign_stage == IJM.CAMPAIGN_STAGE_ARCHIVED:
    #         if self.campaign_stage_prev in [None, IJM.CAMPAIGN_STAGE_ARCHIVED]:
    #             if self.mailbox.threads.count() == 0:
    #                 return IJM.CAMPAIGN_STAGE_PRE_OUTREACH
    #             elif self.mailbox.threads.filter(
    #                 mandrill_id__regex=r'.(.)+',
    #                 type=MailProxyMessage.TYPE_EMAIL,
    #                 direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND).count() == 0:
    #         else:
    #             return self.campaign_stage_prev
    #     else:
    #         return self.campaign_stage

    def get_or_create_mailbox(self):
        if not self.mailbox:
            self.mailbox = MailProxy.create_box(brand=self.job.oryg_creator, influencer=self.mapping.influencer)
            self.save()
        return self.mailbox

    @property
    def post_requirements(self):
        if self.contract.extra_details:
            return self.contract.extra_details
        return self.campaign.post_requirements

    @property
    def date_requirements(self):
        # return self.contract.info_json.get('date_requirements')
        return self.contract.date_requirements

    @property
    def product_url(self):
        if self.campaign.info_json.get('same_product_url'):
            return self.campaign.info_json.get('product_url')
        return self.contract.product_url

    @property
    def product_urls(self):
        if self.campaign.info_json.get('same_product_url'):
            return self.campaign.product_urls
        return self.contract.product_urls

    @property
    def product_restrictions(self):
        return self.contract.info_json.get(
            'restrictions', self.campaign.info_json.get('restrictions'))

    @property
    def product_details(self):
        if self.contract.info_json.get('blogger_additional_info'):
            return self.contract.info_json.get('blogger_additional_info')
        else:
            return self.campaign.info_json.get('blogger_additional_info')

    @property
    def product_preferences(self):
        if self.contract.info_json.get('product_preferences'):
            return self.contract.info_json.get('product_preferences')
        # else:
        #     return self.campaign.info_json.get('blogger_additional_info')

    @property
    def paypal_username(self):
        return self.contract.info_json.get(
            'additional_data', {}).get('paypal_username')

    @property
    def paypal_entity_name(self):
        return self.contract.info_json.get(
            'additional_data', {}).get('paypal_entity_name')

    @property
    def phone_number(self):
        return self.contract.info_json.get(
            'additional_data', {}).get('phone_number')

    @property
    def address(self):
        return self.contract.blogger_address

    @property
    def campaign(self):
        try:
            return self._campaign
        except AttributeError:
            return self.job

    @property
    def mails(self):
        mails = short_cache.get('%i_ijm_mails_cache' % self.id)
        if mails is not None:
            return mails
        mails = MailProxyMessage.objects
        q = []
        if self.mailbox:
            q.append(Q(thread=self.mailbox))
        # if self.mapping and self.mapping.mailbox:
        #    q.append(Q(thread=self.mapping.mailbox))
        # if self.job:
        #     q.append(Q(thread__candidate_mapping__job=self.job))
        # if self.job.collection:
        #     q.append(Q(thread__mapping__group=self.job.collection))
        if q:
            mails = mails.filter(reduce(lambda x, y: x | y, q))
            mails = mails.exclude(mandrill_id='.')
            mails = mails.order_by('ts')
            mails = mails.only('id', 'ts', 'type', 'direction')
            mails = list(mails.values('id', 'ts', 'type', 'direction'))
        else:
            mails = []
        short_cache.set('%i_ijm_mails_cache' % self.id, mails)
        return mails

    @property
    def applied(self):
        for m in self.mails:
            if m["direction"] == MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND:
                return True
        return self.status == InfluencerJobMapping.STATUS_ACCEPTED

    @property
    def reply_stamp(self):
        if self.mails:
            return self.mails[-1]["ts"]
        return None

    @property
    def opened_count(self):
        count = 0
        for m in self.mails:
            if m["type"] in (MailProxyMessage.TYPE_OPEN, MailProxyMessage.TYPE_CLICK):
                count += 1
        return count

    @property
    def emails_count(self):
        count = 0
        for m in self.mails:
            if m["type"] == MailProxyMessage.TYPE_EMAIL:
                count += 1
        return count

    @property
    def post_stamp(self):
        if self.mails:
            return self.mails[0]["ts"]
        return None

    @property
    def status_stamp(self):
        if self.status == InfluencerJobMapping.STATUS_INVITED:
            return self.post_stamp()
        if self.status == InfluencerJobMapping.STATUS_EMAIL_RECEIVED:
            last = None
            for thread in self.mails:
                if thread["type"] == MailProxyMessage.TYPE_OPEN:
                    last = thread
            return last.ts
        if self.status == InfluencerJobMapping.STATUS_VISITED or self.status == InfluencerJobMapping.STATUS_ACCEPTED:
            last = None
            for thread in self.mails:
                if thread["type"] == MailProxyMessage.TYPE_CLICK:
                    last = thread
            return last.ts

    @property
    def status_verbose(self):
        if self.status is None:
            return "Not invited yet"
        return dict(InfluencerJobMapping.STATUS).get(self.status)

    @property
    def can_invite(self):
        return self.status == InfluencerJobMapping.STATUS_NON_INVITED

    @property
    def group(self):
        return self.mapping.group

    @property
    def influencer(self):
        if self.mailbox_id:
            return self.mailbox.influencer
        elif self.mapping_id:
            return self.mapping.influencer
        elif self.influencer_analytics_id:
            return self.influencer_analytics.influencer
        return None  # this should not happen

    @property
    def email_subject(self):
        if self.mailbox:
            return self.mailbox.subject
        elif self.mapping and self.mapping.mailbox:
            return self.mapping.mailbox.subject
        return None


IJM = InfluencerJobMapping


class ContentTag(models.Model):
    post = models.ForeignKey(Posts, null=True)
    influencer = models.ForeignKey(Influencer, null=True)
    tag = models.CharField(max_length=100)

    class Meta:
        unique_together = (
            ('post', 'tag'),
            ('influencer', 'tag'),
        )

    def __unicode__(self):
        return 'post_id:{self.post_id} {self.tag!r}'.format(self=self)


class ContentTagCount(models.Model):
    platform = models.ForeignKey(Platform)
    tag = models.CharField(max_length=100)
    count = models.IntegerField()

    @staticmethod
    def tag_presence_pct(platform, tag):
        total_q = ContentTagCount.objects.filter(platform=platform, tag='nonempty')
        if not total_q.exists():
            return 0.0
        total = total_q[0].count
        tag_q = ContentTagCount.objects.filter(platform=platform, tag=tag)
        if not tag_q.exists():
            return 0.0
        for_tag = tag_q[0].count
        return (for_tag * 100.0) / total

    class Meta:
        unique_together = (('platform', 'tag'),)

    def __unicode__(self):
        return 'platform_id:{self.platform_id} {self.tag} {self.count}'.format(self=self)


class PlatformDataWarning(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    platform = models.ForeignKey(Platform, null=True)
    influencer = models.ForeignKey(Influencer, null=True)
    invariant = models.CharField(max_length=1000)
    confirmed = models.NullBooleanField()

    def __unicode__(self):
        return 'plat_id:{self.platform_id} inf_id:{self.influencer_id} {self.invariant!r} confirmed:{self.confirmed}'


class BrandInPost(models.Model):
    brand = models.ForeignKey(Brands)
    post = models.ForeignKey(Posts)

    # class Meta:
    #    unique_together = (('brand', 'post'))

    def __unicode__(self):
        return u'brand.id=%s brand.name=%r post.id=%s' % (self.brand_id, self.brand.name, self.post_id)


class MentionInPost(models.Model):
    mention = models.CharField(max_length=100, db_index=True)
    post = models.ForeignKey(Posts)
    platform = models.ForeignKey(Platform, null=True, db_index=True)
    influencer = models.ForeignKey(Influencer, null=True, db_index=False)
    platform_name = models.CharField(max_length=1000, blank=True, null=True, default=None, db_index=False)
    influencer_imported = models.BooleanField(default=False, db_index=True)

    # class Meta:
    #    unique_together = (('mention', 'post'))


class HashtagInPost(models.Model):
    hashtag = models.CharField(max_length=100, db_index=True)
    post = models.ForeignKey(Posts)

    # class Meta:
    #    unique_together = (('hashtag', 'post'))


#####-----< Angel List Profiles>-----#####

class AngelListProfile(models.Model):
    # name
    # investments
    # linked in profile
    # about me
    # site
    # blog url
    # twitter
    # investment thesis
    # seed
    url = models.CharField(max_length=512)
    name = models.CharField(max_length=64, null=True, blank=True, default=None)
    tw_url = models.CharField(max_length=512, null=True, blank=True, default=None)
    linkedin_url = models.CharField(max_length=512, null=True, blank=True, default=None)
    blog_url = models.CharField(max_length=512, null=True, blank=True, default=None)
    facebook_url = models.CharField(max_length=512, null=True, blank=True, default=None)
    aboutme_url = models.CharField(max_length=512, null=True, blank=True, default=None)
    site_url = models.CharField(max_length=512, null=True, blank=True, default=None)
    bio = models.TextField(blank=True, null=True, default=None)
    roles = models.TextField(blank=True, null=True, default=None)
    angel_id = models.IntegerField(blank=True, null=True, default=None)
    locations_interested = models.TextField(blank=True, null=True, default=None)
    markets_interested = models.TextField(blank=True, null=True, default=None)
    is_accredited = models.NullBooleanField(default=None)


class AngelListCompanyUserRelationship(models.Model):
    user = models.ForeignKey(AngelListProfile)
    company_url = models.CharField(max_length=512, null=True, blank=True)
    angellist_url = models.CharField(max_length=512, null=True, blank=True)
    relationship = models.CharField(max_length=32)

#####-----</ Angel List Profiles>-----#####

class InfluencerCustomerComment(models.Model):
    influencer = models.ForeignKey('Influencer', related_name='influencer_customer_comments', null=True)
    brand = models.ForeignKey('Brands', related_name='influencer_customer_comments', null=True)
    user = models.ForeignKey(User, related_name='influencer_customer_comments', null=True, blank=True, default=None)
    comment = models.TextField(blank=True, null=True, default=None)
    timestamp = models.DateTimeField(auto_now_add=True)



class InfluencerCheck(models.Model):
    CAUSE_NON_EXISTING_URL = 1
    CAUSE_URL_CHANGED = 2
    CAUSE_SUSPECT_NO_CONTENT = 3
    CAUSE_SUSPECT_EMAIL = 4
    CAUSE_SUSPECT_NAME_BLOGNAME = 5
    CAUSE_SUSPECT_BLOGNAME = 6
    CAUSE_SUSPECT_DESCRIPTION = 7
    CAUSE_SUSPECT_LOCATION = 8

    CAUSE_SUSPECT_BROKEN_SOCIAL = 10
    CAUSE_SUSPECT_SOCIAL_PLATFORM_OUTLIER_FOLLOWERS = 11
    CAUSE_SUSPECT_HIGH_COMMENTS_LOW_SOCIAL_URLS = 12
    CAUSE_SUSPECT_HIGH_FOLLOWERS_LOW_SOCIAL_URLS = 13
    CAUSE_SUSPECT_SOCIAL_HANDLES = 14
    CAUSE_SUSPECT_NO_COMMENTS = 15
    CAUSE_SUSPECT_HIGH_POSTS_LOW_SOCIAL_URLS = 16
    CAUSE_SUSPECT_SIMILAR_CONTENT = 17
    CAUSE_SUSPECT_SIMILAR_BLOG_URLS = 18
    CAUSE_SUSPECT_NO_SOCIAL_FOLLOWERS = 19
    CAUSE_SUSPECT_EMAIL_KICKBOX = 20
    CAUSE_SUSPECT_BIG_PUBLICATION = 21
    CAUSE_SUSPECT_DUPLICATE_SOCIAL_Facebook = 22
    CAUSE_SUSPECT_DUPLICATE_SOCIAL_Twitter = 23
    CAUSE_SUSPECT_DUPLICATE_SOCIAL_Pinterest = 24
    CAUSE_SUSPECT_DUPLICATE_SOCIAL_Instagram = 25
    CAUSE_SUSPECT_DUPLICATE_SOCIAL_Youtube = 26
    CAUSE_SUSPECT_DUPLICATE_SOCIAL_Tumblr = 27



    CAUSES = (
        (CAUSE_NON_EXISTING_URL, "Suspicious URLs"),
        (CAUSE_URL_CHANGED, "Url Changed"),
        (CAUSE_SUSPECT_NO_CONTENT, "Suspect No Content"),
        (CAUSE_SUSPECT_EMAIL, "Suspicious Email"),
        (CAUSE_SUSPECT_EMAIL_KICKBOX, "Suspicious Email checked using Kickbox"),
        (CAUSE_SUSPECT_NAME_BLOGNAME, "Similarities between blogname and blogger name"),
        (CAUSE_SUSPECT_BLOGNAME, "Suspicious Blogname"),
        (CAUSE_SUSPECT_DESCRIPTION, "Suspicious Description"),
        (CAUSE_SUSPECT_LOCATION, "Suspicious Location"),
        (CAUSE_SUSPECT_BROKEN_SOCIAL, "Broken/Mainstream Social Links"),
        (CAUSE_SUSPECT_SOCIAL_PLATFORM_OUTLIER_FOLLOWERS, "Outliers Social Followers"),
        (CAUSE_SUSPECT_HIGH_COMMENTS_LOW_SOCIAL_URLS, "High # of comments but not enough social urls"),
        (CAUSE_SUSPECT_HIGH_FOLLOWERS_LOW_SOCIAL_URLS, "High # of followers but not enough social urls"),
        (CAUSE_SUSPECT_SOCIAL_HANDLES, "Suspicious social handles"),
        (CAUSE_SUSPECT_NO_COMMENTS, "Suspicious no comments"),
        (CAUSE_SUSPECT_HIGH_POSTS_LOW_SOCIAL_URLS, "High # of posts but not enough social urls"),
        (CAUSE_SUSPECT_SIMILAR_CONTENT, "Similar content for blogs of two different influencers"),
        (CAUSE_SUSPECT_SIMILAR_BLOG_URLS, "Similar blog urls of two different influencers"),
        (CAUSE_SUSPECT_NO_SOCIAL_FOLLOWERS, "Suspicious no social followers"),
        (CAUSE_SUSPECT_BIG_PUBLICATION, "A blog which is for a bigger publication/multiple authors"),
        (CAUSE_SUSPECT_DUPLICATE_SOCIAL_Facebook, "Suspected Duplicate Facebook URLs"),
        (CAUSE_SUSPECT_DUPLICATE_SOCIAL_Twitter, "Suspected Duplicate Twitter URLs"),
        (CAUSE_SUSPECT_DUPLICATE_SOCIAL_Pinterest, "Suspected Duplicate Pinterest URLs"),
        (CAUSE_SUSPECT_DUPLICATE_SOCIAL_Instagram, "Suspected Duplicate Instagram URLs"),
        (CAUSE_SUSPECT_DUPLICATE_SOCIAL_Youtube, "Suspected Duplicate Youtube URLs"),
        (CAUSE_SUSPECT_DUPLICATE_SOCIAL_Tumblr, "Suspected Duplicate Tumblr URLs"),
    )

    STATUS_FIXED = 1
    STATUS_INVALID = 2
    STATUS_REPORT_BUG = 3
    STATUS_NEW = 4
    STATUS_MODIFIED = 5
    STATUS_VALID = 6  # This is used to tell that this field is good.

    STATUSES = (
        (STATUS_FIXED, "Fixed"),
        (STATUS_INVALID, "Invalid"),
        (STATUS_REPORT_BUG, "Report bug"),
        (STATUS_NEW, "New"),
        (STATUS_MODIFIED, "Modified"),
        (STATUS_VALID, "Valid")
    )
    DEFAULT_STATUS = STATUS_NEW

    influencer = models.ForeignKey('Influencer', null=True)
    platform = models.ForeignKey('Platform', null=True)
    cause = models.IntegerField(choices=CAUSES)
    status = models.IntegerField(choices=STATUSES)
    fields = models.TextField()
    filename_function = models.TextField()
    custom_message = models.TextField(null=True, blank=True)
    qa = models.TextField(null=True, blank=True)

    data_json = models.CharField(max_length=10000, null=True)
    """Additional data attached to the ``InfluencerCheck``, as a JSON dictionary.
    Values under specific keys:
    - 'related' - an array of two-element arrays identifying models. The first element is a
    model class name, the second is an ``id`` value. Example:
    {"related": [["Influencer", 111]]}
    """

    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)

    @classmethod
    def report(cls, influencer, platform, cause, fields, custom_message=None, data=None):
        """
        Add InfluencerCheck record for given influencer, platform and cause.
        'fields' should be list or tuple of fields affected by problem.
        """
        import traceback
        import os
        file_name, line_no, function_name, _ = traceback.extract_stack(limit=2)[0]
        file_name = os.path.normpath(file_name)
        if 'miami_metro' in file_name:
            file_name = file_name[file_name.index('miami_metro'):]
        obj = InfluencerCheck()
        obj.influencer = influencer
        obj.platform = platform
        obj.cause = cause
        assert type(fields) is list or type(fields) is tuple
        obj.fields = json.dumps(fields)
        obj.filename_function = "%s:%i %s" % (file_name, line_no, function_name)
        obj.status = InfluencerCheck.DEFAULT_STATUS
        if custom_message:
            obj.custom_message = custom_message
        if data is not None:
            obj.data_json = json.dumps(data)
        obj.save()
        return obj

    @classmethod
    def already_exists(cls, influencer, cause, fields):
        """
        If we already have an InfluencerCheck object for this <influencer, field, cause> and status is either
        NEW or VALID, then we can skip this.
        """
        if InfluencerCheck.objects.filter(influencer=influencer,
                                          cause=cause,
                                          status__in=[InfluencerCheck.STATUS_NEW, InfluencerCheck.STATUS_VALID],
                                          fields=fields).exists():
            log.info('Already exists: report %s for fields %r %r already exists', cause, fields, influencer)
            return True
        return False

    @classmethod
    def report_new(cls, influencer, platform, cause, fields, custom_message=None, data=None):
        """
        Calls ``report`` for the specified args only if a model with STATUS_NEW does not exist.
        """
        if InfluencerCheck.objects.filter(influencer=influencer, platform=platform,
                                          cause=cause, status=InfluencerCheck.STATUS_NEW,
                                          fields=fields).exists():
            log.info('Already exists: report %s for fields %r for %r already exists', cause, fields, influencer)
            return None
        log.info('Reporting %s for %r', cause, influencer)
        return InfluencerCheck.report(influencer, platform, cause, fields, custom_message, data)


class FeedCheck(models.Model):

    """
    Store details about feeds we discover on platforms.
    """
    platform = models.ForeignKey('Platform', null=False)
    feed_url = models.URLField(max_length=1000, null=True, blank=True, default=None)
    full_posts = models.BooleanField(null=False, blank=False)
    summaries = models.BooleanField(null=False, blank=False)
    summary_details = models.BooleanField(null=False, blank=False)
    link_to_post = models.BooleanField(null=False, blank=False)
    invalid_feed = models.BooleanField(null=False, blank=False)
    no_entries = models.BooleanField(null=False, blank=False)
    error = models.TextField(null=True)
    created = models.DateTimeField(auto_now_add=True, null=False)


class PostLengthCheck(models.Model):

    """
    Store details about feeds we discover on platforms.
    """
    influencer = models.ForeignKey('Influencer', null=False)
    platform = models.ForeignKey('Platform', null=False)
    max_post_length = models.IntegerField(null=False, blank=False)
    created = models.DateTimeField(auto_now_add=True, null=False)

    def __unicode__(self):
        return u'PostLengthCheck(influencer={}, max post length={})'.format(
            self.influencer_id, self.max_post_length)


class PostAnalyticsQuerySet(TimeSeriesMixin, models.query.QuerySet):

    @staticmethod
    def _get_campaign_counters(selected_counters=None, aggregate=False):
        data = {
            'agr_fb_count': '''
                coalesce(count_fb_shares, 0) +
                coalesce(count_fb_likes, 0) +
                coalesce(count_fb_comments, 0)
            ''',
            'agr_post_shares_count': '''
                coalesce(
                    (SELECT
                        CASE
                            WHEN post_type='Facebook' THEN p.engagement_media_numfbshares
                            WHEN post_type='Twitter' THEN p.engagement_media_numretweets
                            WHEN post_type='Pinterest' THEN p.engagement_media_numrepins
                            ELSE coalesce(count_tweets, 0) +
                                coalesce(count_fb_shares, 0) +
                                coalesce(count_fb_likes, 0) +
                                coalesce(count_fb_comments, 0) +
                                coalesce(count_gplus_plusone, 0) +
                                coalesce(count_pins, 0)
                        END
                        FROM debra_posts AS p
                        WHERE debra_postanalytics.post_id = p.id),
                    0
                )
            ''',
            'agr_post_comments_count': '''
                coalesce(nullif(coalesce(
                    (SELECT
                        CASE
                            WHEN post_type IS NULL OR post_type='Blog' THEN
                                CASE
                                    WHEN post_comments IS NOT NULL AND post_comments >= 0 THEN post_comments
                                    ELSE p.ext_num_comments
                                END
                            ELSE GREATEST(p.engagement_media_numcomments, COUNT(pi.id))
                        END
                        FROM debra_posts AS p JOIN debra_postinteractions AS pi ON pi.post_id = p.id
                        WHERE debra_postanalytics.post_id = p.id GROUP BY p.id),
                    0
                ), -1), 0)
            ''',
            'agr_post_likes_count': '''
                coalesce(
                    (SELECT p.engagement_media_numlikes
                        FROM debra_posts AS p
                        WHERE debra_postanalytics.post_id = p.id
                    ), 0
                )
            ''',
            'agr_post_total_count': '''
                coalesce(
                    (SELECT
                        CASE
                            WHEN post_type='Facebook' THEN p.engagement_media_numfbshares
                            WHEN post_type='Twitter' THEN p.engagement_media_numretweets
                            WHEN post_type='Pinterest' THEN p.engagement_media_numrepins
                            ELSE coalesce(count_tweets, 0) +
                                coalesce(count_fb_shares, 0) +
                                coalesce(count_fb_likes, 0) +
                                coalesce(count_fb_comments, 0) +
                                coalesce(count_gplus_plusone, 0) +
                                coalesce(count_pins, 0)
                        END
                        FROM debra_posts AS p
                        WHERE debra_postanalytics.post_id = p.id),
                    0
                ) +
                coalesce(nullif(coalesce(
                    (SELECT
                        CASE
                            WHEN post_type IS NULL OR post_type='Blog' THEN
                                CASE
                                    WHEN post_comments IS NOT NULL AND post_comments >= 0 THEN post_comments
                                    ELSE p.ext_num_comments
                                END
                            ELSE GREATEST(p.engagement_media_numcomments, COUNT(pi.id)) + coalesce(p.impressions, 0)
                        END
                        FROM debra_posts AS p JOIN debra_postinteractions AS pi ON pi.post_id = p.id
                        WHERE debra_postanalytics.post_id = p.id GROUP BY p.id),
                    0
                ), -1), 0) +
                coalesce(
                    (SELECT p.engagement_media_numlikes
                        FROM debra_posts AS p
                        WHERE debra_postanalytics.post_id = p.id
                    ), 0
                )
            ''',
        }
        if selected_counters:
            data = {
                k: v for k, v in data.items()
                if k in selected_counters
            }
        if aggregate:
            data = {
                k: 'SUM({})'.format(v) for k, v in data.items()
            }
        return data

    def _get_total_blog_impressions(self):
        blog_posts = self.filter(post__platform_name__in=Platform.BLOG_PLATFORMS)
        return blog_posts.aggregate(
            Sum('count_impressions')
        )['count_impressions__sum'] or 0

    def _get_unique_blog_impressions(self):
        blog_posts = self.filter(post__platform_name__in=Platform.BLOG_PLATFORMS)
        return blog_posts.aggregate(
            Sum('count_unique_impressions')
        )['count_unique_impressions__sum'] or 0

    def _get_total_social_impressions(self):
        social_posts = self.filter(post__platform_name__in=Platform.SOCIAL_PLATFORMS)
        return social_posts.aggregate(
            Sum('post__platform__num_followers')
        )['post__platform__num_followers__sum'] or 0
        # social_posts = social_posts.values(
        #     'post__platform',
        #     'post__platform__num_followers',
        #     'post__platform_name',
        # ).annotate(
        #     posts_count=Count('post__platform__posts')
        # )

        # def _post_impressions(post_data):
        #     pl_name = post_data['post__platform_name']
        #     num_followers = post_data['post__platform__num_followers'] or 0
        #     num_posts = post_data['posts_count'] or 0
        #     # return pl_name, num_followers * num_posts
        #     return num_followers * num_posts

        # impressions = sum([_post_impressions(post_data) for post_data in social_posts])
        # return impressions

    def _get_unique_social_impressions(self):
        social_posts = self.filter(post__platform_name__in=Platform.SOCIAL_PLATFORMS)
        social_platforms = Platform.objects.filter(
            id__in=list(
                social_posts.distinct(
                    'post__platform'
                ).values_list('post__platform', flat=True)
            )
        )
        return social_platforms.aggregate(Sum('num_followers'))['num_followers__sum'] or 0

    def filter_platforms(self, *platform_names):
        platform_names = filter(None, platform_names or [])
        platform_names = itertools.chain(*[Platform.normalize_platform_name(pl_name)
            for pl_name in platform_names])
        platform_names = list(set(platform_names))
        if platform_names:
            return self.filter(post__platform_name__in=platform_names)
        return self

    def total_impressions(self, blog_only=False, social_only=False):
        if blog_only:
            return self._get_total_blog_impressions()
        if social_only:
            return self._get_total_social_impressions()
        return self._get_total_blog_impressions() + self._get_total_social_impressions()

    def unique_impressions(self, blog_only=False, social_only=False):
        if blog_only:
            return self._get_unique_blog_impressions()
        if social_only:
            return self._get_unique_social_impressions()
        return self._get_unique_blog_impressions() + self._get_unique_social_impressions()

    def total_clicks(self):
        return self.aggregate(
            total_clicks=Sum('count_clickthroughs')
        )['total_clicks'] or 0

    def unique_clicks(self):
        return self.aggregate(
            total_unique_clicks=Sum('count_unique_clickthroughs')
        )['total_unique_clicks'] or 0

    def total_facebook_engagement(self):
        return self.aggregate_campaign_counters(
            selected_counters=['agr_fb_count'])['agr_fb_count']

    def audience(self):
        # 1) audience => it's the sum of number of followers on all social platforms
        # where they have a post + unique blog impressions
        # 2) so for example, if they have 1000 followers on Instagram and 1000 blog views
        # and they got 100 likes and 10 clicks
        # then it's (100+10)/(1000+1000) = 110/2000
        # so you have to sum up unique blog impressios (from click meter) and total unique
        # followers from each platform where they have a post
        # because we don't want to count Instagrams from all if not all of them did an Instagram
        return float(self.total_engagement()) / float(self.unique_impressions())

    def with_counters(self):
        return self.prefetch_related(
            'post__influencer__shelf_user__userprofile',
            'post__influencer__platform_set',
            # 'post__postinteractions_set',
        ).extra(
            # (SELECT DISTINCT COUNT(*)
            # FROM
            # (SELECT *
            #     FROM debra_posts AS p
            #         JOIN debra_postinteractions AS pi
            #     ON pi.post_id = p.id
            #     WHERE debra_postanalytics.post_id = p.id
            # ) AS STF) +
            select={
                'agr_count_total': '''
                    coalesce(nullif(coalesce(
                        post_comments,
                        (SELECT p.ext_num_comments
                            FROM debra_posts AS p
                            WHERE debra_postanalytics.post_id = p.id), 0
                    ), -1), 0) +
                    coalesce(count_tweets, 0) +
                    coalesce(count_fb_shares, 0) +
                    coalesce(count_fb_likes, 0) +
                    coalesce(count_fb_comments, 0) +
                    coalesce(count_gplus_plusone, 0) +
                    coalesce(count_pins, 0) +
                    coalesce(count_clickthroughs, 0) +
                    coalesce(count_impressions, 0)
                ''',
                'agr_count_fb': '''
                    coalesce(count_fb_shares, 0) +
                    coalesce(count_fb_likes, 0) +
                    coalesce(count_fb_comments, 0)
                ''',
                'agr_num_comments': '''
                    coalesce(nullif(coalesce(
                        post_comments,
                        (SELECT p.ext_num_comments
                            FROM debra_posts AS p
                            WHERE debra_postanalytics.post_id = p.id), 0
                    ), -1), 0)
                '''
            }
        )

    def total_video_impressions(self):
        post_ids = list(self.values_list('post', flat=True).distinct())
        posts = Posts.objects.filter(id__in=post_ids).aggregate(
            total_video_impressions=Sum('impressions')
        )['total_video_impressions'] or 0

    def total_engagement(self, **kwargs):
        return self.aggregate_campaign_counters(
            selected_counters=['agr_post_total_count'])['agr_post_total_count']

    def total_likes(self):
        return self.aggregate_campaign_counters(
            selected_counters=['agr_post_likes_count'])['agr_post_likes_count']

    def total_comments(self):
        return self.aggregate_campaign_counters(
            selected_counters=['agr_post_comments_count'])['agr_post_comments_count']

    def total_shares(self):
        return self.aggregate_campaign_counters(
            selected_counters=['agr_post_shares_count'])['agr_post_shares_count']

    def aggregate_campaign_counters(self, selected_counters=None, **kwargs):
        select_dict = PostAnalyticsQuerySet._get_campaign_counters(
            selected_counters=selected_counters, aggregate=True)
        qs = self.extra(select=select_dict).values(*select_dict.keys())
        data = qs[0]
        return {
            k: int(v) if v is not None else 0 for k, v in data.items()
        }

    def post_ids(self):
        return list(self.exclude(
            post__isnull=True
        ).values_list(
            'post', flat=True
        ).distinct())

    def posts(self):
        return Posts.objects.filter(id__in=self.post_ids())

    def influencer_ids(self):
        return list(self.exclude(post__influencer__isnull=True).\
            values_list('post__influencer', flat=True).\
            distinct())

    def influencers(self):
        return Influencer.objects.filter(id__in=self.influencer_ids())

    def with_campaign_counters(self, **kwargs):

        def platform_preference_case_statement(platforms):
            case_statement = ['CASE']
            case_statement.extend([
                "WHEN pl.platform_name='{}' THEN {}".format(pl, n)
                for n, pl in enumerate(platforms)
            ])
            case_statement.extend([
                'ELSE {}'.format(len(platforms) + 1),
                'END'
            ])
            return '\n'.join(case_statement)

        select_dict = PostAnalyticsQuerySet._get_campaign_counters(
            selected_counters=kwargs.get('selected_counters'))

        if kwargs.get('platform_preference'):
            select_dict.update({
                'platform_order': '''
                    SELECT {case_statement}
                    FROM debra_platform AS pl
                        JOIN debra_posts as p
                        ON p.platform_id = pl.id
                    WHERE debra_postanalytics.post_id = p.id
                '''.format(
                    case_statement=platform_preference_case_statement(
                        kwargs.get('platform_preference'))
                )
            })

        return self.extra(select=select_dict)


class PostAnalyticsManager(models.Manager):

    DEFAULT_SOURCE = 'sharedcount.com'

    def get_query_set(self):
        return PostAnalyticsQuerySet(self.model, using=self.db)

    def _local(self, post_url, brand=None):
        query_set = super(PostAnalyticsManager, self).get_query_set()
        try:
            # item = query_set.filter(
            #     post_url__iexact=post_url
            # )[0]
            item = query_set.exclude(
                created__isnull=True
            ).filter(
                post_url__iexact=post_url
            ).order_by(
                '-created')[0]
        except IndexError:
            item = None
        return item

    def _api_data(self, post_url):
        from debra.shared_count import Api

        api = Api()

        data = api[post_url].url()['data']

        return data

    def _api(self, post_url, data=None, brand=None):

        if not data:
            data = self._api_data(post_url)
        try:
            item = PostAnalytics(
                post_url=post_url,
                source=PostAnalyticsManager.DEFAULT_SOURCE,
                **data)
        except KeyError as e:
            raise Exception('Invalid response from SharedCount API')
        else:
            return item

    def _item(self, post_url, brand=None, refresh=False):
        if refresh:
            item = None
        else:
            item = self._local(post_url)

        if not item or (datetime.now() - item.modified).seconds\
            > constants.SC_LOCAL_REFRESH_TTL:
            api_data = self._api_data(post_url)
            api_result = self._api(post_url, data=api_data)

            if api_result:
                if item:
                    self._update_current_local_abstraction(item, api_data)
                else:
                    self._save_api_abstractions(api_result)
                    item = api_result
        return item

    def _update_current_local_abstraction(self, last_local, api_data):
        last_local.modified = datetime.now()
        last_local.__dict__.update(api_data)
        last_local.save()

    def _save_api_abstractions(self, api_result):
        api_result.save()

    def handle_redirect(self, pa, redirected_url):
        api_data = self._api_data(redirected_url)
        self._update_current_local_abstraction(pa, api_data)

    def from_source(self, post_url=None, brand=None, refresh=False):
        return self._item(post_url, brand=brand, refresh=refresh)


class PostAnalytics(models.Model):
    '''
    Stores statistics for given post fetched from particular source.
    '''
    VIRALITY_SCORE_2_INSIGHTS_MAPPING = [
        (100, "Text for [0, 100)"),
        (200, "Text for [100, 200)"),
        (300, "Text for [200, 300)"),
    ]

    TRACKING_STATUS_NON_SENT = 0
    TRACKING_STATUS_SENT = 1
    TRACKING_STATUS_VERIFYING = 2
    TRACKING_STATUS_VERIFIED = 3
    TRACKING_STATUS_VERIFICATION_PROBLEM = 4

    TRACKING_STATUS = (
        (TRACKING_STATUS_NON_SENT, 'Not sent'),
        (TRACKING_STATUS_SENT, 'Sent'),
        (TRACKING_STATUS_VERIFYING, 'Verifying'),
        (TRACKING_STATUS_VERIFIED, 'Verified'),
        (TRACKING_STATUS_VERIFICATION_PROBLEM, 'Verification problem'),
    )

    TRACKING_STATUS_COLOR = (
        (TRACKING_STATUS_NON_SENT, 'black'),
        (TRACKING_STATUS_SENT, 'blue'),
        (TRACKING_STATUS_VERIFYING, 'grey'),
        (TRACKING_STATUS_VERIFIED, 'green'),
        (TRACKING_STATUS_VERIFICATION_PROBLEM, 'red'),
    )

    brands = models.ManyToManyField('Brands')
    post = models.ForeignKey(Posts, null=True)
    collection = models.ForeignKey('PostAnalyticsCollection', null=True)
    contract = models.ForeignKey('Contract', null=True)
    post_found = models.BooleanField(default=False)
    post_url = models.URLField(null=True)

    # For storing 'date' and 'title' temporarily. They should not be used
    # after association with Post. And 'post.create_date' / 'post.title' /
    # 'post.platform.platform_name' should be used instead
    post_date = models.DateField(null=True)
    post_title = models.CharField(max_length=1000, null=True)
    post_type = models.CharField(max_length=1000, null=True)
    tracking_status = models.IntegerField(
        null=True, default=TRACKING_STATUS_NON_SENT, choices=TRACKING_STATUS)

    source = models.CharField(max_length=120, null=True, blank=True)

    count_fb_shares = models.IntegerField(null=True)
    count_fb_likes = models.IntegerField(null=True)
    count_fb_comments = models.IntegerField(null=True)
    count_tweets = models.IntegerField(null=True)
    count_pins = models.IntegerField(null=True)
    count_stumbleupons = models.IntegerField(null=True)
    count_gplus_plusone = models.IntegerField(null=True)
    count_linkedin_shares = models.IntegerField(null=True)

    count_impressions = models.IntegerField(null=True)
    count_clickthroughs = models.IntegerField(null=True)
    count_unique_impressions = models.IntegerField(null=True)
    count_unique_clickthroughs = models.IntegerField(null=True)

    count_video_impressions = models.IntegerField(null=True)
    count_likes = models.IntegerField(null=True)
    post_comments = models.IntegerField(null=True, blank=True, default=None)
    count_shares = models.IntegerField(null=True)


    # count_unique_impressions = models.IntegerField(null=True)
    # count_unique_clickthroughs = models.IntegerField(null=True)

    inner_link = models.URLField(null=True)

    modified = models.DateTimeField(null=False, auto_now=True)
    created = models.DateTimeField(null=True, auto_now_add=True)

    # storing different info, for example the reason why this post was added to collection of campaign
    info = models.CharField(max_length=512, null=True, blank=True)

    # not used anymore
    approve_status = models.IntegerField(null=True, default=1)
    notes = models.TextField(null=True)

    objects = PostAnalyticsManager()

    # class Meta:
    #     unique_together = ['post', 'source']

    def handle_redirect(self):
        redirected_url = self.redirected_ur
        if self.post_url != redirected_url:
            PostAnalytics.objects.handle_redirect(self, redirected_url)

    @property
    def redirected_url(self):
        return utils.resolve_http_redirect(self.post_url)

    @property
    def ext_post_type(self):
        try:
            return self.post_type or self.post.platform.platform_name
        except AttributeError:
            pass

    @property
    def post_likes(self):
        try:
            return self.post.engagement_media_numlikes
        except AttributeError:
            pass

    @property
    def post_shares(self):
        try:
            return self.agr_post_shares_count
        except AttributeError:
            try:
                if self.post_type == 'Facebook':
                    return self.post.engagement_media_numfbshares
                elif self.post_type == 'Twitter':
                    return self.post.engagement_media_numretweets
                elif self.post_type == 'Pinterest':
                    # return self.post.engagement_media_numrepins
                    return self.count_total
                else:
                    return self.post.engagement_media_numshares
            except AttributeError:
                pass

    @property
    def blogger_post(self):
        p = self
        return {
            'date': p.post_date,
            'title': p.post_title,
            'url': p.post_url,
            'type': p.post_type,
            'info': {
                'id': p.id,
                'verificationStatus': {
                    'value': p.tracking_status,
                    'text': dict(PostAnalytics.TRACKING_STATUS).get(p.tracking_status),
                    'nonSent': p.tracking_status in [PostAnalytics.TRACKING_STATUS_NON_SENT, PostAnalytics.TRACKING_STATUS_VERIFICATION_PROBLEM],
                    'sent': p.tracking_status in [PostAnalytics.TRACKING_STATUS_SENT, PostAnalytics.TRACKING_STATUS_VERIFYING, PostAnalytics.TRACKING_STATUS_VERIFIED],
                    'color': dict(PostAnalytics.TRACKING_STATUS_COLOR).get(p.tracking_status),
                },
            }
        }

    @property
    def influencer(self):
        try:
            return self.post.influencer
        except AttributeError:
            return None

    @property
    def influencer_id(self):
        try:
            return self.post.influencer_id
        except AttributeError:
            return None

    @property
    def virality_score(self):
        try:
            inf = self.post.influencer
        except AttributeError:
            return None
        else:
            try:
                return self.count_total * 100 / sum(
                    pl.num_followers for pl in inf.get_platform_for_search)
            except ZeroDivisionError:
                return None

    @property
    def personal_engagement_score(self):
        return self.calculate_personal_engagement_score()

    @property
    def insights(self):
        try:
            index = [i for i, (x, _) in enumerate(self.VIRALITY_SCORE_2_INSIGHTS_MAPPING) if x > self.virality_score][0]
        except IndexError:
            index = -1
        return self.VIRALITY_SCORE_2_INSIGHTS_MAPPING[index][1]

    @property
    def post_num_comments(self):
        # if self.post_comments is not None and self.post_comments >= 0:
        #     return self.post_comments
        # elif self.post and self.post.ext_num_comments >= 0:
        #     return self.post.ext_num_comments
        try:
            return self.agr_post_comments_count
        except AttributeError:
            try:
                if self.post_type in [None, 'Blog']:
                    if self.post_comments is not None and self.post_comments >= 0:
                        return self.post_comments
                    return max(self.post.ext_num_comments, 0)
                else:
                    # @TODO: (p.engagement_media_numcomments, COUNT(pi.id))
                    return self.post.engagement_media_numcomments
            except AttributeError:
                pass
        # elif hasattr(self, 'num_comments'):
        #     return self.num_comments
        # elif self.post:
        #     return self.post.num_comments

    @property
    def count_fb(self):
        return sum(
            filter(None, [
                self.count_fb_shares,
                self.count_fb_likes,
                self.count_fb_comments
            ])
        )

    @property
    def count_total(self):
        if hasattr(self, 'agr_count_total'):
            return self.agr_count_total
        return sum(
            filter(lambda x: x is not None and x != -1, [
                self.count_tweets,
                self.count_fb,
                self.count_gplus_plusone,
                self.count_pins,
                self.post_num_comments
            ])
        )

    @property
    def remove_url(self):
        return reverse(
            'debra.search_views.del_post_analytics', args=(self.id,))

    @property
    def zero(self):
        return 0

    def calculate_personal_engagement_score(self, values=None):
        try:
            inf = self.post.influencer
        except AttributeError:
            return None
        else:
            if values is None:
                influencer_posts = self.collection.get_unique_post_analytics(
                    post__influencer=inf)
                virality_scores = filter(
                    None, [x.virality_score for x in influencer_posts])
            else:
                virality_scores = filter(None, values.get(inf.id) or [])
            avg_sc = float(sum(virality_scores)) / max(len(virality_scores), 1)
            max_sc = max(virality_scores or [0])
            return avg_sc, max_sc


class PostAnalyticsCollectionManager(DenormalizationManagerMixin,
        models.Manager):
    pass


class PostAnalyticsCollection(models.Model):
    name = models.CharField(max_length=128, blank=True)
    archived = models.NullBooleanField(blank=True, null=True, default=False)
    is_updating = models.BooleanField(default=False)
    created_date = models.DateTimeField(auto_now_add=True)
    last_report_sent = models.DateTimeField(null=True)
    creator_brand = models.ForeignKey('Brands',
        related_name='created_post_analytics_collections',
        null=True, blank=True
    )
    system_collection = models.NullBooleanField(default=False)
    user = models.ForeignKey(
        User, related_name='post_analytics_collections',
        null=True, blank=True, default=None
    )
    tag = models.ForeignKey('InfluencersGroup',
        related_name='post_analytics_collections', null=True, blank=True)
    items_number = models.IntegerField(null=True, default=0)

    # denormalized fields
    top_post_images = TextArrayField(null=True, default='{}')

    objects = PostAnalyticsCollectionManager()

    def denormalize(self, save=True):
        def get_post_images():
            return list(self.postanalytics_set.exclude(
                post__post_image__isnull=True
            ).values_list(
                'post__post_image', flat=True
            ).distinct('post')[:constants.NUM_OF_IMAGES_PER_BOX])

        self.refresh_count(save=False)
        self.top_post_images = get_post_images()
        if save:
            self.save()

    def add(self, item, save=True):
        assert type(item) in (PostAnalytics, int,)

        if type(item) == int:
            item = PostAnalytics.objects.get(id=item)

        item.collection = self
        if save:
            item.save()
        self.denormalize(save=save)

    def remove(self, url=None, post_ids=None, pa_ids=None):
        assert url is not None or post_ids is not None or pa_ids is not None

        if pa_ids:
            ids = pa_ids
        elif post_ids:
            ids = self.postanalytics_set.filter(
                post_id__in=post_ids
            ).values_list('id', flat=True)
        else:
            urls = url if type(url) == list else [url]
            ids = [
                x.id for x in self.postanalytics_set.all()
                if x.post_url in urls
            ]

        if ids:
            print 'Removing {} from post collection with id={}'.format(
                ids, self.id)
            qs = PostAnalytics.objects.filter(id__in=ids)
            qs.delete()
            self.denormalize()

    def refresh_count(self, save=True):
        self.items_number = self.get_unique_post_analytics().count()
        if save:
            self.save()

    def refresh(self):
        from debra.brand_helpers import handle_post_analytics_urls

        urls = set(self.postanalytics_set.all().values_list(
            'post_url', flat=True))
        handle_post_analytics_urls(urls, self.id, None, True)

    def _get_unique_post_analytics_ids(self):
        qs = self.postanalytics_set.order_by(
            'post_url', 'post__platform', '-created'
        ).distinct(
            'post_url', 'post__platform',
        )
        return list(qs.values_list('id', flat=True))

    @custom_cached(key=lambda self: 'unq_pas_{}'.format(self.id))
    def get_unique_post_analytics_ids(self):
        return self._get_unique_post_analytics_ids()

    @timeit
    def get_unique_post_analytics(self, cached=False, **kwargs):
        ids = self.get_unique_post_analytics_ids() if cached\
            else self._get_unique_post_analytics_ids()
        return PostAnalytics.objects.filter(id__in=ids, **kwargs)

    @property
    def influencer_ids(self):
        qs = self.get_unique_post_analytics().exclude(
            post__influencer__isnull=True
        )
        qs = qs.values('post__influencer')
        qs = qs.annotate(Max('modified')).order_by('modified__max')
        res = [x['post__influencer'] for x in qs]
        return res

    @property
    def imgs(self):
        return self.top_post_images
        # posts = [x.post for x in self.postanalytics_set.all() if x.post]
        # imgs = list(set([x.post_image for x in posts if x.post_image]))
        # return imgs[:constants.NUM_OF_IMAGES_PER_BOX]

    @property
    def virality_score_values_for_influencers(self):
        t = time.time()
        try:
            posts = self.agr_post_analytics_set
        except AttributeError:
            posts = self.unique_post_analytics.prefetch_related(
                'post__influencer__platform_set')
        d = collections.defaultdict(list)
        for p in posts:
            if p.post.influencer is not None:
                d[p.post.influencer_id].append(p.virality_score)
        print 'virality_score_values_for_influencers --', time.time() - t
        return d

    @property
    def unique_post_analytics(self):
        return self.get_unique_post_analytics()

    @property
    def page_url(self):
        return reverse(
            'debra.search_views.post_analytics_collection', args=(self.id,))

    @property
    def updated(self):
        conditions = [
            self.get_unique_post_analytics().filter(
                post__isnull=True).count() == 0,
            not self.is_updating
        ]
        return all(conditions)

    @property
    def last_updated(self):
        try:
            pa = self.postanalytics_set.exclude(created__isnull=True).order_by(
                '-created')[0]
        except IndexError:
            return None
        else:
            return pa.created

    @property
    def is_updated_recently(self):
        last_updated = self.last_updated or datetime.min
        days = (datetime.now() - last_updated).days
        return days < 1

    @property
    def is_new_report_ready(self):
        try:
            return self.updated and (self.last_report_sent is None or\
                self.last_updated > self.last_report_sent)
        except TypeError:
            return False

    @property
    def new_brand(self):
        pass

    @new_brand.setter
    def new_brand(self, brand_id):
        from debra.helpers import create_post_collection_copy_for_brand
        create_post_collection_copy_for_brand(self.id, brand_id)

    @property
    def flag_send_report_to_customer(self):
        pass

    @flag_send_report_to_customer.setter
    def flag_send_report_to_customer(self, value):
        from debra import brand_helpers
        value = bool(value and value != '0')
        if value and self.is_new_report_ready:
            brand_helpers.send_post_analytics_report(self.id)

    @property
    def clicks_stats(self):
        return [{
            'count_clicks': s.count_clicks,
            'count_unique_clicks': s.count_unique_clicks,
            'date': s.snapshot_date.strftime('%Y-%m-%d %H:%M'),
        } for s in self.time_series.all()]

    @property
    def views_stats(self):
        return [{
            'count_views': s.count_views,
            'count_unique_views': s.count_unique_views,
            'date': s.snapshot_date.strftime('%Y-%m-%d %H:%M'),
        } for s in self.time_series.all()]


class PostAnalyticsCollectionTimeSeries(models.Model):
    collection = models.ForeignKey(
        'PostAnalyticsCollection', null=True, related_name='time_series')
    # from_date = models.DateTimeField(null=True)
    # to_date = models.DateTimeField(null=True)
    snapshot_date = models.DateTimeField(null=True)
    count_views = models.IntegerField(default=0)
    count_unique_views = models.IntegerField(default=0)
    count_clicks = models.IntegerField(default=0)
    count_unique_clicks = models.IntegerField(default=0)


class EngagementTimeSeries(models.Model):

    influencer = models.ForeignKey('Influencer', null=True)
    platform = models.ForeignKey('Platform', null=True)
    avg_likes = models.FloatField(null=True)
    avg_comments = models.FloatField(null=True)
    avg_shares = models.FloatField(null=True)
    likes_data = models.TextField(null=True)
    comments_data = models.TextField(null=True)
    shares_data = models.TextField(null=True)
    date_range_start = models.DateTimeField(null=True)
    date_range_end = models.DateTimeField(null=True)

    months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    years = [2015, 2016]

    @json_field_property
    def likes_data_json(self):
        return 'likes_data'

    @json_field_property
    def comments_data_json(self):
        return 'comments_data'

    @json_field_property
    def shares_data_json(self):
        return 'shares_data'

    def set_raw_likes_data(self, raw_data):
        self.likes_data = json.dumps(raw_data)

    def set_raw_comments_data(self, raw_data):
        self.comments_data = json.dumps(raw_data)

    def set_raw_shares_data(self, raw_data):
        self.shares_data = json.dumps(raw_data)


    def fetch_posts(self, start_date, end_date):
        all_posts = Posts.objects.filter(platform=self.platform)
        if self.platform.platform_name == 'Pinterest':
            posts = all_posts.filter(inserted_datetime__gte=start_date, inserted_datetime__lt=end_date)
        else:
            posts = all_posts.filter(create_date__gte=start_date, create_date__lt=end_date)
        return posts

    @staticmethod
    def fetch_engagements_summary(posts):
        if not posts:
            return 0.0, 0.0, 0.0
        plat = posts[0].platform

        num_posts = float(posts.count())
        avg_comments = plat.calculate_num_comments(posts)
        avg_shares = plat.calculate_num_shares(posts)
        avg_likes = plat.calculate_num_likes(posts)

        avg_comments = avg_comments/num_posts if avg_comments else 0.0
        avg_shares = avg_shares/num_posts if avg_shares else 0.0
        avg_likes = avg_likes/num_posts if avg_likes else 0.0

        return avg_comments, avg_shares, avg_likes

    @staticmethod
    def fetch_raw_engagements(posts):
        raw_comments = {}
        raw_shares = {}
        raw_likes = {}
        for p in posts:
            raw_comments[p.id] = max(p.engagement_media_numcomments, p.ext_num_comments, p.num_comments)
            raw_shares[p.id] = p.engagement_media_numshares
            raw_likes[p.id] = p.engagement_media_numlikes

        return raw_comments, raw_shares, raw_likes


    @staticmethod
    def handle_platform(platform):
        import datetime
        print "Handling %r" % platform
        y = EngagementTimeSeries.years[0]
        months = EngagementTimeSeries.months

        for m in months:
            st = datetime.datetime(y, m, 1)
            if m < 12:
                end = datetime.datetime(y, m+1, 1)
            else:
                end = datetime.datetime(y+1, 1, 1)
            print "Handling time range: <%r, %r> " % (st, end)

            elem, created = EngagementTimeSeries.objects.get_or_create(platform=platform, date_range_start=st, date_range_end=end)
            if not created:
                print("Entry already exists for %r, moving to the next one" % platform)
                continue
            print("Creating a new EngagementTimeSeries for %r for <%r, %r>" % (platform, st, end))

            posts = elem.fetch_posts(st, end)
            avg_comments, avg_shares, avg_likes = EngagementTimeSeries.fetch_engagements_summary(posts)
            raw_comments, raw_shares, raw_likes = EngagementTimeSeries.fetch_raw_engagements(posts)

            elem.avg_comments = avg_comments
            elem.avg_shares = avg_shares
            elem.avg_likes = avg_likes

            elem.set_raw_comments_data(raw_comments)
            elem.set_raw_likes_data(raw_likes)
            elem.set_raw_shares_data(raw_shares)

            elem.save()


class InfluencerAnalytics(models.Model):
    APPROVE_STATUS_NOT_SENT = -1
    APPROVE_STATUS_PENDING = 0
    APPROVE_STATUS_YES = 1
    APPROVE_STATUS_NO = 2
    APPROVE_STATUS_MAYBE = 3
    APPROVE_STATUS_ARCHIVED = 4

    APPROVE_STATUS = [
        (APPROVE_STATUS_NOT_SENT, "Not Sent"),
        (APPROVE_STATUS_PENDING, "Pending"),
        (APPROVE_STATUS_YES, "Yes"),
        (APPROVE_STATUS_NO, "No"),
        (APPROVE_STATUS_MAYBE, "Maybe"),
        (APPROVE_STATUS_ARCHIVED, "Archived"),
    ]

    APPROVE_STATUS_COLOR = [
        (APPROVE_STATUS_NOT_SENT, "black"),
        (APPROVE_STATUS_PENDING, "grey"),
        (APPROVE_STATUS_YES, "green"),
        (APPROVE_STATUS_NO, "red"),
        (APPROVE_STATUS_MAYBE, "yellow"),
        (APPROVE_STATUS_ARCHIVED, "grey"),
    ]

    influencer = models.ForeignKey(Influencer, null=True)
    influencer_analytics_collection = models.ForeignKey(
        'InfluencerAnalyticsCollection', null=True)
    # contract = models.OneToOneField('Contract', null=True)

    tmp_approve_status = models.IntegerField(
        null=True, default=APPROVE_STATUS_PENDING, choices=APPROVE_STATUS)
    approve_status = models.IntegerField(
        null=True, default=APPROVE_STATUS_PENDING, choices=APPROVE_STATUS)
    notes = models.TextField(null=True)
    client_notes = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)
    archived = models.NullBooleanField(default=False, null=True)

    @property
    def approve_status_name(self):
        return dict(self.APPROVE_STATUS).get(self.approve_status)

    @property
    def approve_status_color(self):
        return dict(self.APPROVE_STATUS_COLOR).get(self.approve_status)

    @property
    def report(self):
        try:
            return self.influencer_analytics_collection.roipredictionreport_set.all()[0]
        except IndexError:
            pass

    @property
    def campaign(self):
        try:
            return self.report.campaign
        except AttributeError:
            pass


IA = InfluencerAnalytics


class InfluencerAnalyticsCollectionManager(models.Manager):

    def from_tag(self, tag, collection=None, approved=False, campaign=None):
        if collection is None:
            print '* Influencer collection is missing, creating a new one...'
            collection = InfluencerAnalyticsCollection(tag=tag, name=tag.name)
            collection.save()
            print '* Influencer collection created with id={}'.format(
                collection.id)
        print '* Saving influencers from Tag(id={})'.format(tag.id)
        extra = {
            inf_id:{'approve_status': approved}
            for inf_id in tag.influencer_ids
        }
        collection.merge_influencers(
            tag.influencer_ids,
            celery=True,
            extra=extra,
            campaign=campaign,
            approved=approved,
        )
        return collection

    def from_post_collection(self, post_collection=None, collection=None,
            approved=False, campaign=None):
        if collection is None:
            print '* Influencer collection is missing, creating a new one...'
            collection = InfluencerAnalyticsCollection()
            collection.save()
            print '* Influencer collection created with id={}'.format(
                collection.id)
        if post_collection is not None:
            print '* Saving influencers from Post Collection(id={})'.format(
                    post_collection.id)
            extra = {
                inf_id:{'approve_status': approved}
                for inf_id in post_collection.influencer_ids
            }
            collection.merge_influencers(
                post_collection.influencer_ids,
                extra=extra,
                celery=True,
                campaign=campaign,
                approved=approved,
            )
        return collection


class InfluencerAnalyticsCollection(models.Model):
    APPROVAL_STATUS_NOT_SENT = 0
    APPROVAL_STATUS_SENT = 1
    APPROVAL_STATUS_SUBMITTED = 2

    APPROVAL_STATUS = [
        (APPROVAL_STATUS_NOT_SENT, "Not Sent To Client Yet"),
        (APPROVAL_STATUS_SENT, "Sent To Client"),
        (APPROVAL_STATUS_SUBMITTED, "Submitted By Client"),
    ]

    APPROVAL_STATUS_COLOR = [
        (APPROVAL_STATUS_NOT_SENT, "red"),
        (APPROVAL_STATUS_SENT, "yellow"),
        (APPROVAL_STATUS_SUBMITTED, "green"),
    ]

    tag = models.ForeignKey('InfluencersGroup', null=True)
    approval_status = models.IntegerField(
        null=True, default=APPROVAL_STATUS_NOT_SENT, choices=APPROVAL_STATUS)
    is_updating = models.BooleanField(default=False)
    system_collection = models.NullBooleanField(default=False)

    objects = InfluencerAnalyticsCollectionManager()

    def save_influencers(self, inf_ids, extra=None):
        self.is_updating = True
        self.save()
        if extra is None:
            extra = {}
        for inf_id in inf_ids:
            params = dict(
                influencer_id=inf_id, influencer_analytics_collection=self)
            try:
                params.update(extra.pop(inf_id))
            except KeyError:
                pass
            ia = InfluencerAnalytics.objects.create(**params)
        # for k, v in extra.items():
        #     self.influenceranalytics_set.filter(
        #         influencer_id=k).update(**v)
        self.is_updating = False
        self.save()
        print '* Influencers saved'

    def merge_influencers(self, inf_ids, celery=False, extra=None, campaign=None, approved=False):
        from debra.brand_helpers import (
            add_influencers_to_blogger_approval_report,)
        print '* Merging {} influencers...'.format(len(inf_ids))
        new_ids = list(set(inf_ids) - set(self.influencer_ids))
        print '* {} new influencers found'.format(len(new_ids))
        # preserving the order
        new_ids = [x for x in inf_ids if x in new_ids]
        if new_ids:
            self.is_updating = True
            self.save()
            params = dict(
                inf_ids=new_ids,
                inf_collection_id=self.id,
                campaign_id=campaign.id,
                extra=extra,
                approved=approved
            )
            if celery:
                add_influencers_to_blogger_approval_report.apply_async(
                    kwargs=params, queue='blogger_approval_report')
            else:
                add_influencers_to_blogger_approval_report(**params)
        return new_ids

    @property
    def influencer_ids(self):
        return list(self.influenceranalytics_set.values_list(
            'influencer', flat=True))

    @property
    def approval_status_name(self):
        return dict(self.APPROVAL_STATUS).get(self.approval_status)

    @property
    def approval_status_color(self):
        return dict(self.APPROVAL_STATUS_COLOR).get(self.approval_status)


IAC = InfluencerAnalyticsCollection


class ROIPredictionReport(models.Model):
    name = models.CharField(max_length=128, blank=True)
    archived = models.NullBooleanField(blank=True, null=True, default=False)
    created_date = models.DateTimeField(auto_now_add=True)

    post_collection = models.ForeignKey('PostAnalyticsCollection',
        related_name='prediction_reports', null=True, blank=True)
    influencer_analytics_collection = models.ForeignKey(
        'InfluencerAnalyticsCollection', null=True, on_delete=models.SET_NULL)
    creator_brand = models.ForeignKey('Brands',
        related_name='created_roi_prediction_reports',
        null=True, blank=True
    )
    user = models.ForeignKey(
        User, related_name='roi_prediction_reports',
        null=True, blank=True, default=None
    )
    main_campaign = models.ForeignKey(
        BrandJobPost, related_name="roi_reports", null=True)
    info = models.TextField(null=True, default="")

    def get_public_hash(self, user):
        key = '/'.join([
            str(self.created_date),
            str(user.date_joined)
        ])
        return hashlib.md5(key).hexdigest()

    def get_public_url(self, user):
        return ''.join([
            constants.MAIN_DOMAIN,
            reverse(
                'debra.search_views.blogger_approval_report_public',
                args=(
                    self.creator_brand_id,
                    self.id,
                    user.id,
                    self.get_public_hash(user),
                )
            )
        ])

    @property
    def campaign(self):
        try:
            return self.brandjobpost_set.all()[0]
        except IndexError:
            pass

    # @property
    # def info_json(self):
    #     try:
    #         return json.loads(self.info)
    #     except:
    #         return {}

    @json_field_property
    def info_json(self):
        return 'info'

    @cached_property
    def influencer_collection(self):
        return self._get_or_create_influencer_collection()

    def _get_or_create_influencer_collection(self):
        _collection = InfluencerAnalyticsCollection.objects.from_post_collection(
            self.post_collection,
            collection=self.influencer_analytics_collection)
        if self.influencer_analytics_collection is None:
            self.influencer_analytics_collection = _collection
            self.save()
        return self.influencer_analytics_collection

    @cached_property
    def influencer_collection(self):
        return self._get_or_create_influencer_collection()

    @property
    def user_invited(self):
        # user who invited the client (used for generating a public url)
        try:
            return self.tmp_user_invited
        except AttributeError:
            return self.user or 0

    @property
    def public_url(self):
        return self.get_public_url(self.user_invited)

    @property
    def items_number(self):
        try:
            return self.post_collection.items_number or 0
        except AttributeError:
            return 0

    @property
    def imgs(self):
        try:
            return self.post_collection.imgs
        except AttributeError:
            return []

    @property
    def page_url(self):
        return reverse(
            'debra.search_views.roi_prediction_report', args=(self.id,))

    @property
    def copy_to_report(self):
        pass

    @copy_to_report.setter
    def copy_to_report(self, brand_id):
        from debra.helpers import create_report_copy_for_brand
        create_report_copy_for_brand(self.id, brand_id)

    @property
    def copy_to_tag(self):
        pass

    @copy_to_tag.setter
    def copy_to_tag(self, value):
        from debra.helpers import create_tag_from_report_for_brand

        tag_id = None
        brand_id = None

        try:
            brand_id = int(value)
        except ValueError:
            try:
                brand_id, tag_id = [int(x.strip()) for x in value.split(',')]
            except Exception:
                return
        tag = create_tag_from_report_for_brand(
            self.id, brand_id, tag_id)


#####-----</ Similar web integration />-----#####
''' Available durations for SimilarWebVisits. '''
SW_GRANULARITY_DAILY = 0
SW_GRANULARITY_WEEKLY = 1
SW_GRANULARITY_MONTHLY = 2
SW_GRANULARITY_CHOICES = (
    (SW_GRANULARITY_DAILY, 'Daily'),
    (SW_GRANULARITY_WEEKLY, 'Weekly'),
    (SW_GRANULARITY_MONTHLY, 'Monthly')
)

class SimilarWebVisitsManager(models.Manager):
    ''' SimilarWebVisistsManager provides access to SimilarWebVisits data.

    SimilarWebVisits, defined below, is ETL data returned from the Similar Web
    API. This manager transparently manages local caching of the ETL documents
    from the API in the following manner:
        a) SimilarWebVisits.objects.monthly(influencer) is called
        b) Finds locally cached monthly ETL data for the influencer
           - Reads up to last month indiscriminately
           - Reads last month if modified time is less than SW_LOCAL_REFRESH_TTL
        c) Uses the timestamp of the last local result as the basis of an API request
        d) Uses Manager.bulk_create to create the new abstractions in postgres
        e) Appends the new results to the local list and returns the results

    To implement weekly or daily statistics, copy the monthly method, setting
    begin_min to the first day of timespan/week, begin_max to the beginning of
    the current window (i.e. date(today.year, today.month, today.day) for daily),
    and pass a new lambda function into _items with the correct granularity flag,
    which are defined above.

    The lambda function `last_seen` should accept a datetime.date argument, which will
    be the beginning date of the last valid abstraction in the database, returning
    the next 'begins' timestamp where the query for the API should start.
    '''
    def _influencer(self, influencer):
        ''' _influencer is used internally to extract an Influencer from id or object. '''
        if type(influencer) != Influencer:
            try:
                influencer = int(float(influencer))
            except:
                raise Exception('unknown type for influencer in SimilarWebVisitsManager')

            influencer = Influencer.objects.get(pk=influencer)
        return influencer

    def _local(self, influencer, begins, ends, granularity):
        ''' _local queries postgres for local rows, and enforces SW_LOCAL_REFRESH_TTL. '''
        items = super(SimilarWebVisitsManager, self).get_query_set().\
            filter(
                influencer=influencer,
                granularity=granularity,
                begins__lte=ends,
                begins__gte=begins
            ).order_by(
                '-begins'
            )

        return items if items else []

    def _api(self, influencer, begins, ends, granularity):
        ''' _api wraps the similar_web.Api class, and is used for requesting new data. '''
        from debra.similar_web import Api
        from debra.generic_api import ApiContactingError
        api = Api()

        # sometimes, SimilarWeb has delays with most recent stats
        # so, we should request data upto previous month or even earlier;
        # here we're trying 3 times to set appropriate 'end' date for our period;
        # it applies only when original 'end' param is empty,
        # when it is not, we do only one try using month previous to 'end'
        for _ in xrange(4):
            if ends.month == 1:
                ends = date(ends.year - 1, 12, 1)
            else:
                ends = date(ends.year, ends.month - 1, 1)
            try:
                report, _ = SimilarWebVisitsReport.objects.get_or_create(
                    influencer=influencer,
                    granularity=granularity,
                    start=begins,
                    end=ends)
                report.api_calls_count += 1
                report.save()
                granular_data = api[influencer.blog_url].visits(
                    start_month='%s-%s' % (begins.year, begins.month),
                    end_month='%s-%s' % (ends.year, ends.month),
                    granularity=SW_GRANULARITY_CHOICES[granularity][1]
                )
            except ApiContactingError:
                pass
            else:
                if granular_data['data']:
                    break

        items = []

        try:
            for month in granular_data['data']:
                item = SimilarWebVisits()
                item.granularity = granularity
                item.begins = datetime.strptime(month['date'], '%Y-%m-%d').date()
                item.count = int(float(month['count']))
                item.influencer = influencer
                items.append(item)
        except KeyError as e:
            raise Exception('Invalid response from SimilarWeb API')
        print "Got %d items" % len(items)
        return items

    def _items(self, influencer, begins_min, begins_max, granularity):
        ''' _items collects local ETL data, then merges in any missing api data. '''
        from debra.generic_api import Api404Error
        items = list(
            self._local(influencer, begins_min, begins_max, granularity))

        report, _ = SimilarWebVisitsReport.objects.get_or_create(
            influencer=influencer,
            granularity=granularity,
            start=begins_min,
            end=begins_max)

        report.calls_count += 1
        report.save()

        if not items:
            try:
                items = self._api(
                    influencer, begins_min, begins_max, granularity)
            except Api404Error:
                '*** monthly._api 404 error'
                items = []

            if items:
                self._save_api_abstractions(items)

        elif items and items[0].begins != begins_max and (datetime.now() - items[0].modified).days > 30:
            try:
                api = self._api(
                    influencer, items[0].begins, begins_max, granularity)
            except Api404Error:
                self._remove_current_local_abstractions(influencer)

            if api:
                self._update_current_local_abstraction(items[0], api)
                self._save_api_abstractions(api)
                self._merge_api_abstractions(items, api)

        # if type(items) == list:
        #     qs = SimilarWebVisits.objects.filter(
        #         id__in=[item.id for item in items])
        # else:
        #     qs = items
        # qs = qs.order_by('-begins')
        # return qs

        return sorted(items, key=lambda x: x.begins, reverse=True)

    def _update_current_local_abstraction(self, last_local, api_results):
        ''' _update_current_local_abstraction updates the current window's abstraction, if it exists. '''
        if last_local.begins == api_results[0].begins:
            last_local.count = api_results[0].count
            last_local.save()
            api_results.pop(0)

    def _save_api_abstractions(self, api_results):
        ''' _save_api_abstractions saves api ETL data locally. '''
        from django.db import transaction
        try:
            print api_results
            super(SimilarWebVisitsManager, self).bulk_create(api_results)
        except:
            transaction.rollback()

    def _remove_current_local_abstractions(self, influencer):
        ''' _remove_current_local_abstractions removes api ETL data locally. '''
        from django.db import transaction
        try:
            influencer.similarwebvisits_set.all().delete()
        except:
            transaction.rollback()

    def _merge_api_abstractions(self, into, abstractions):
        ''' _merge_api_abstractions merges newly saved abstractions into the result set returned by the manager. '''
        into.extend(sorted(abstractions, key=lambda etl: etl.begins, reverse=True))

    def monthly(self, influencer, start=None, end=None):
        if not start:
            start = date(date.today().year - 1, date.today().month, 1)
        if not end:
            end = date.today()

        influencer = self._influencer(influencer)
        begins_min = date(start.year, start.month, 1)
        begins_max = date(end.year, end.month, 1)

        items = self._items(influencer, begins_min,
                begins_max, SW_GRANULARITY_MONTHLY)

        return items


class SimilarWebVisits(models.Model):
    ''' SimilarWebVisits stores ETL visit data from the Similar Web API.

    @influencer: the influencer the ETL data describes
    @granularity: the granularity of the data, defined in the SW_GRANULARITY_CHOICES enum
    @begins the first date covered by the ETL document
    @modified the time that this document was modified
    @count the number of visits the influencer had in this time window
    '''
    influencer = models.ForeignKey('Influencer', null=False)
    granularity = models.IntegerField(null=False, choices=SW_GRANULARITY_CHOICES)
    begins = models.DateField(null=False, auto_now_add=False, auto_now=False)
    modified = models.DateTimeField(null=False, auto_now=True)
    count = models.IntegerField(null=False)

    objects = SimilarWebVisitsManager()

    class Meta:
        unique_together = ['influencer', 'granularity', 'begins']

    def frontend_date(self):
        ''' frontend_date returns a string formatted for the frontend. '''
        return self.begins


class SimilarWebVisitsReport(models.Model):
    influencer = models.ForeignKey('Influencer', null=False)
    timestamp = models.DateField(auto_now_add=True)
    start = models.DateField(null=False, auto_now_add=False, auto_now=False)
    end = models.DateField(null=False, auto_now_add=False, auto_now=False)
    granularity = models.IntegerField(
        null=False, choices=SW_GRANULARITY_CHOICES)
    calls_count = models.IntegerField(null=False, default=0)
    api_calls_count = models.IntegerField(null=False, default=0)

    class Meta:
        unique_together = ['influencer', 'granularity', 'start', 'end']


SW_SOURCE_TYPE_SEARCH = 1
SW_SOURCE_TYPE_SOCIAL = 2
SW_SOURCE_TYPE_MAIL = 3
SW_SOURCE_TYPE_PAID_REFERRALS = 4
SW_SOURCE_TYPE_DIRECT = 5
SW_SOURCE_TYPE_REFERRALS = 6

SW_SOURCE_TYPE_CHOICES = (
    (SW_SOURCE_TYPE_SEARCH, 'Search'),
    (SW_SOURCE_TYPE_SOCIAL, 'Social'),
    (SW_SOURCE_TYPE_MAIL, 'Mail'),
    (SW_SOURCE_TYPE_PAID_REFERRALS, 'Paid Referrals'),
    (SW_SOURCE_TYPE_DIRECT, 'Direct'),
    (SW_SOURCE_TYPE_REFERRALS, 'Referrals'),
)


class SimilarWebTrafficSharesManager(models.Manager):

    def _local(self, influencer):
        items = super(SimilarWebTrafficSharesManager, self).get_query_set().\
            filter(
                influencer=influencer
            ).order_by(
                'source_type'
            )

        return items if items else []

    def _api(self, influencer):
        from debra.similar_web import Api
        from debra.generic_api import Api404Error

        api = Api()

        try:
            data = api[influencer.blog_url].traffic_shares()
        except Api404Error:
            data = {'data': []}

        items = []

        try:
            for source_data in data['data']:
                item = SimilarWebTrafficShares()
                item.influencer = influencer
                item.source_type = source_data['type']
                item.value = source_data['value']
                items.append(item)
        except KeyError as e:
            raise Exception('Invalid response from SimilarWeb API')

        return items

    def _items(self, influencer):
        items = self._local(influencer)

        if not items or any(map(lambda x: (datetime.now() - x.modified).seconds\
            > constants.SW_LOCAL_REFRESH_TTL, items)):
            api_results = self._api(influencer)

            if api_results:
                if items:
                    items.delete()
                self._save_api_abstractions(api_results)
                items = api_results

        return items

    def _save_api_abstractions(self, api_results):
        super(SimilarWebTrafficSharesManager, self).bulk_create(api_results)

    def latest(self, influencer):
        return self._items(influencer)


class SimilarWebTrafficShares(models.Model):
    ''' SimilarWebTrafficShares stores distribution of trafic over sources '''
    influencer = models.ForeignKey('Influencer', null=False)
    source_type = models.IntegerField(null=False, choices=SW_SOURCE_TYPE_CHOICES)
    value = models.FloatField(null=False)
    modified = models.DateTimeField(null=False, auto_now=True)

    objects = SimilarWebTrafficSharesManager()

    class Meta:
        unique_together = ['influencer', 'source_type']


class CloudFrontDistribution(models.Model):
    """
    A model to store the key-value mappings of CloudFront distribution so that we don't call these again.
    """
    name = models.CharField(max_length=1000, blank=True, null=True)
    value = models.URLField(max_length=1000, blank=True, null=True)

    @classmethod
    def set(cls):
        c = CloudFrontConnection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
        rs = c.get_all_distributions()
        for r in rs:
            dd = r.get_distribution()
            bb = dd._get_bucket()
            inst = cls()
            inst.name = bb.name
            inst.value = 'http://' + dd.domain_name
            inst.save()

    @classmethod
    def get(cls, bucket_name):
        return cls.objects.get(name=bucket_name).value


class BrandTaxonomy(models.Model):
    brand_name = models.CharField(max_length=1000, null=True)
    source = models.CharField(max_length=1000, null=True)
    repr_url = models.CharField(max_length=1000, null=True)
    style_tag = models.CharField(max_length=1000, null=True)
    product_tag = models.CharField(max_length=1000, null=True)
    price_tag = models.CharField(max_length=1000, null=True)
    keywords = models.TextField(null=True)
    hashtags = models.TextField(null=True)
    mentions = models.TextField(null=True)
    mention_urls = models.TextField(null=True)
    # keywords = TextArrayField(null=True, default=[])
    # hashtags = TextArrayField(null=True, default=[])
    # mentions = TextArrayField(null=True, default=[])
    # mention_urls = TextArrayField(null=True, default=[])
    modified = models.DateTimeField(auto_now=True, null=True)

    influencers_count = models.IntegerField(null=True, default=0)
    posts_count = models.IntegerField(null=True, default=0)
    instagrams_count = models.IntegerField(null=True, default=0)
    blog_posts_count = models.IntegerField(null=True, default=0)

    @property
    def keywords_list(self):
        try:
            return self.keywords.split('\n')
        except:
            return []

    @property
    def hashtags_list(self):
        try:
            return self.hashtags.split('\n')
        except:
            return []

    @property
    def mentions_list(self):
        try:
            return self.mentions.split('\n')
        except:
            return []

    @property
    def mention_urls_list(self):
        try:
            return self.mention_urls.split('\n')
        except:
            return []

    def _build_query(self):
        _query = {
            'keyword_types': [],
            'and_or_filter_on': False,
            'filters': {},
            'keyword': [],
            'group_concatenator': 'and_same',
            'sub_tab': 'main_search',
            'no_artifical_blogs': True,
            'groups': [],
            'type': 'all',
        }
        if self.keywords_list:
            _query['keyword_types'].extend(['all'] * len(self.keywords_list))
            _query['keyword'].extend(self.keywords_list)
        if self.hashtags_list:
            _query['keyword_types'].extend(['hashtag'] * len(self.hashtags_list))
            _query['keyword'].extend(self.hashtags_list)
        if self.mentions_list:
            _query['keyword_types'].extend(['mention'] * len(self.mentions_list))
            _query['keyword'].extend(self.mentions_list)
        if self.mention_urls_list:
            _query['keyword_types'].extend(['brand'] * len(self.mention_urls_list))
            _query['keyword'].extend(self.mention_urls_list)
        return _query

    def update_influencers_count(self):
        from debra.elastic_search_helpers import es_influencer_query_runner_v2
        _, _, total = es_influencer_query_runner_v2(
            self._build_query(), page_size=1, page=0, source=True)
        self.influencers_count = total
        self.save()

    def update_posts_count(self):
        feed_json = feeds_helpers.get_feed_handler_for_platform(None)
        total = feed_json(
            request=None,
            no_cache=True,
            with_parameters=True,
            parameters=self._build_query(),
            count_only=True,
        )
        self.posts_count = total
        self.save()

    def update_instagrams_count(self):
        feed_json = feeds_helpers.get_feed_handler_for_platform('Instagram')
        total = feed_json(
            request=None,
            no_cache=True,
            with_parameters=True,
            parameters=self._build_query(),
            count_only=True,
        )
        self.instagrams_count = total
        self.save()

    def update_blog_posts_count(self):
        feed_json = feeds_helpers.get_feed_handler_for_platform('Blog')
        total = feed_json(
            request=None,
            no_cache=True,
            with_parameters=True,
            parameters=self._build_query(),
            count_only=True,
        )
        self.blog_posts_count = total
        self.save()

    @cached_property
    def es_updaters(self):
        return [
            self.update_influencers_count,
            self.update_posts_count,
            self.update_instagrams_count,
            self.update_blog_posts_count,
        ]

    def update_es_counts(self):
        for _u in self.es_updaters:
            _u()


class SiteConfiguration(models.Model):
    stripe_plans = models.TextField(null=True)
    docusign_documents = models.TextField(null=True)
    blogger_custom_data = models.TextField(null=True)


    @json_field_property
    def stripe_plans_json(self):
        return 'stripe_plans'

    @json_field_property
    def docusign_documents_json(self):
        return 'docusign_documents'

    @json_field_property
    def blogger_custom_data_json(self):
        return 'blogger_custom_data'


class TestModel(models.Model):
    name = models.CharField(max_length=1000, null=True)
    tags = TextArrayField(null=True, blank=True)
    # info = PGJsonField(null=True, blank=True)


class TestModel2(models.Model):
    name = models.CharField(max_length=1000, null=True)
    test_model = models.ForeignKey(TestModel, null=True)


#####-----</ Denormalization Signals >-----#####

@signal_crashed_notification
def save_original_state(sender, instance, **kwargs):
    try:
        instance._ignore_old
        del instance._ignore_old
    except AttributeError:
        if issubclass(sender, PostSaveTrackableMixin):
            old_instance = sender.objects.get(
                id=instance.id) if instance.id else None
            if not old_instance:
                instance._newly_created = True
            for field in sender._POST_SAVE_TRACKABLE_FIELDS:
                if old_instance:
                    old_value = getattr(old_instance, field)
                else:
                    old_value = sender._meta.get_field_by_name(
                        field)[0].default
                setattr(instance, '_old_{}'.format(field), old_value)


@signal_crashed_notification
def generate_tracking_info(sender, instance, **kwargs):
    from debra.clickmeter import (
        ClickMeterContractLinksHandler, ClickMeterCampaignLinksHandler)
    if sender == Contract:
        try:
            cond = all([
                instance._old_product_urls != instance.product_urls,
                not instance.campaign.info_json.get('same_product_url'),
                # instance.product_urls,
            ])
            if cond:
                product_urls_handler = ClickMeterContractLinksHandler(
                    clickmeter_api, instance)
                product_urls_handler.handle(
                    instance._old_product_urls,
                    instance.product_urls)
                # del instance._old_product_urls
            # del instance._old_product_urls
        except AttributeError:
            pass

        try:
            instance._newly_created
            del instance._newly_created
        except AttributeError:
            pass
        else:
            if instance.campaign.info_json.get('same_product_url'):
                product_urls_handler = ClickMeterCampaignLinksHandler(
                    clickmeter_api, instance.campaign)
                product_urls_handler.handle(
                    [], instance.campaign.product_urls,
                    contract_ids=[instance.id])
    elif sender == BrandJobPost:
        try:
            if instance._old_client_url != instance.client_url:
                instance.update_tracking_brand_link_batch()
            # del instance._old_client_url
        except AttributeError:
            pass

        try:
            cond = all([
                instance._old_product_urls != instance.product_urls,
                instance.info_json.get('same_product_url'),
                # instance.product_urls,
            ])
            if cond:
                product_urls_handler = ClickMeterCampaignLinksHandler(
                    clickmeter_api, instance)
                product_urls_handler.handle(
                    instance._old_product_urls,
                    instance.product_urls)
            # del instance._old_product_urls
        except AttributeError:
            pass

    if issubclass(sender, PostSaveTrackableMixin):
        instance._clear_old_field_values()


@signal_crashed_notification
def social_handle_update_handler(sender, instance, **kwargs):
    from debra.admin_helpers import task_handle_social_handle_updates

    #TODO: remove return after we import
    #print "* task_handle_social_handle_updates returning immediately now"
    #return

    celery = True

    # influencer_id, url_field, new_val
    for field in sender._POST_SAVE_TRACKABLE_FIELDS:
        try:
            value = getattr(instance, field)
        except AttributeError:
            pass
        else:
            if instance.is_field_changed(field):
                print "* task_handle_social_handle_updates for '{}'".format(
                    field)
                if celery:
                    task_handle_social_handle_updates.apply_async([
                        instance.id, field, value
                    ], queue='social-handle-updates')
                else:
                    task_handle_social_handle_updates(
                        instance.id, field, value)


@signal_crashed_notification
def campaign_stage_handler(sender, instance, **kwargs):
    if instance.is_field_changed('campaign_stage'):
        sender.objects.filter(id=instance.id).update(
            campaign_stage_prev=instance._old_campaign_stage)


@signal_crashed_notification
def cache_update_handler(sender, instance, **kwargs):
    print '** update in cache {}'.format(sender)
    instance.update_in_cache()


post_save.connect(cache_update_handler, sender=MailProxy, dispatch_uid="mail-proxy-cache-update-handler")
post_save.connect(cache_update_handler, sender=MailProxyMessage, dispatch_uid="mail-proxy-message-cache-update-handler")
post_save.connect(cache_update_handler, sender=InfluencersGroup, dispatch_uid="influencers-group-cache-update-handler")


for _, _cls in PostSaveTrackableMixin.get_subclasses():
    pre_save.connect(save_original_state, sender=_cls,
        dispatch_uid="{}-save-original-state".format(_cls.__name__))

# pre_save.connect(save_original_state, sender=BrandJobPost, dispatch_uid="campaign-save-original-state-signal")
post_save.connect(generate_tracking_info, sender=BrandJobPost, dispatch_uid="campaign-generate-tracking-info")

# pre_save.connect(save_original_state, sender=Contract, dispatch_uid="contract-save-original-state")
post_save.connect(generate_tracking_info, sender=Contract, dispatch_uid="contract-generate-tracking-info")


post_save.connect(social_handle_update_handler, sender=Influencer, dispatch_uid="social-handle-update-handler")

post_save.connect(campaign_stage_handler, sender=InfluencerJobMapping, dispatch_uid="campaign-stage-handler")


post_save.connect(create_shelf_img, sender=ProductModelShelfMap, dispatch_uid="create-shelfimg-signal")

post_save.connect(create_default_competitor, sender=Brands, dispatch_uid="create-default-competitor-signal")

post_save.connect(mark_mailbox_as_unread, sender=MailProxyMessage, dispatch_uid="mark-mailbox-as-unread-signal")

post_save.connect(update_shelf_num_items, sender=ProductModelShelfMap, dispatch_uid="add-shelfnums-signal")
post_delete.connect(update_shelf_num_items, sender=ProductModelShelfMap, dispatch_uid="del-shelfnums-signal")

post_save.connect(update_user_num_shelves, sender=Shelf, dispatch_uid="modify-numshelves-signal")
post_save.connect(update_user_num_items, sender=ProductModelShelfMap, dispatch_uid="modify-usernums-signal")

post_save.connect(update_follow_count, sender=UserFollowMap, dispatch_uid="followed-user-signal")
post_delete.connect(update_follow_count, sender=UserFollowMap, dispatch_uid="unfollowed-user-signal")

signals.facebook_user_registered.connect(fb_user_registered_handler, sender=get_user_model())


#####-----#####-----#####-----</ Signal Handlers >-----#####-----#####-----#####
