from celery.decorators import task
from debra.models import Promoinfo, Brands, ProductModel, ColorSizeModel, Posts, Platform, HealthReport, PlatformDataOp
from debra.models import ProductModelShelfMap,ProductPrice,ProductAvailability,ProductPromotion,UserProfile, Influencer, BrandJobPost
from debra.models import InfluencersGroup, InfluencerGroupMapping, MailProxyMessage, PostAnalytics, PostAnalyticsCollection, ROIPredictionReport
from debra.models import InfluencerEditHistory, BrandMentions, PopularityTimeSeries, InfluencerValidationQueue, InfluencerCheck, OpDict, UserProfileBrandPrivilages
from debra.models import MailProxy
from debra.constants import *
from debra.forms import ModifyBrandForm, ModifyUserForm, ModifyProductForm, ModifyInfluencerForm, InfluencerImportForm, PlatformUrlsForm
from debra.widgets import WishlistItemsFeed
from debra import helpers as h
from settings import INTERCOM_APPID, INTERCOM_APIKEY, PROJECT_PATH
from django.contrib import admin
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render, redirect, render_to_response, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.template.loader import render_to_string
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin import AdminSite, ModelAdmin
from django.contrib.admin.models import User as UserModel
from django.contrib.auth.models import Group
from django.conf.urls.defaults import patterns, include, url
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.db.models import Q
from debra import db_util
from debra import admin_helpers
from debra.admin_helpers import handle_blog_url_change, handle_social_handle_updates, update_or_create_new_platform
from debra import serializers
from intercom import Intercom, User, ResourceNotFound
from datetime import timedelta
from debra import brand_helpers, account_helpers
import json
import pdb
import time
import re
import math
import datetime
import operator
import logging
import pprint
import os.path
from collections import defaultdict
from platformdatafetcher import fetchertasks, estimation, platformextractor, platformutils, fetcher, postprocessing, platformcleanup
from xpathscraper import utils


# helpers

def table_page(options):
    skil_influencer_validate = options.get("skip_influencers_validate") == True
    if options["request"].method == 'UPDATE':
        row_id = options["request"].GET.get('id')
        obj = get_object_or_404(options["model"], id=row_id)
        obj.date_validated = datetime.datetime.now()
        try:
            validated_on = json.loads(obj.validated_on)
        except (ValueError, TypeError):
            validated_on = []
        validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
        validated_on = list(set(validated_on))
        obj.validated_on = json.dumps(validated_on)
        if obj.qa:
            obj.qa = " ".join((obj.qa, options["request"].visitor["auth_user"].username))
        else:
            obj.qa = options["request"].visitor["auth_user"].username
        obj.save()
        if obj.fb_url:
            handle_social_handle_updates(obj, 'fb_url', obj.fb_url)
        if obj.pin_url:
            handle_social_handle_updates(obj, 'pin_url', obj.pin_url)
        if obj.tw_url:
            handle_social_handle_updates(obj, 'tw_url', obj.tw_url)
        if obj.insta_url:
            handle_social_handle_updates(obj, 'insta_url', obj.insta_url)
        return HttpResponse()
    elif options["request"].method == 'POST':
        row_id = options["request"].POST.get('pk')
        name = options["request"].POST.get('name')
        value = options["request"].POST.get('value')
        obj = get_object_or_404(options["model"], id=row_id)
        if not skil_influencer_validate:
            obj.date_edited = datetime.datetime.now()
            obj.save()
        data = {
            name: value
        }
        if name == "qa":
            return HttpResponse()
        if not skil_influencer_validate:
            InfluencerEditHistory.commit_change(obj, name, value)
        serializer = options["store_serializer"](obj, data=data, partial=True)
        if serializer.is_valid():
            if name == 'send_report_to_customer':
                return HttpResponse()
            if name == "blog_url":
                handle_blog_url_change(obj, value)
            serializer.save()
            if not skil_influencer_validate:
                handle_social_handle_updates(obj, name, value)
        else:
            return HttpResponseBadRequest(serializer.errors)
        return HttpResponse()
    else:
        if options.get("debug"):
            query = options["query"]
            data = admin_helpers.get_objects(
                options["request"], query, options["load_serializer"], options)
            return HttpResponse("<body></body>")
        if options["request"].is_ajax():
            query = options["query"]
            data = admin_helpers.get_objects(
                options["request"],
                query,
                options["load_serializer"],
                context=options.get("context"),
                options=options)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(options["request"], options["template"],
                options["context"],
                context_instance=RequestContext(options["request"]))


# TABLE CONSTANTS


def create_csv_report(modeladmin, request, queryset):
    '''
    a script similar to the one off script for generating a user report, but for the admin interface and more generic
    '''
    import csv

    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename="report.csv"'
    writer = csv.writer(response)

    for val in queryset:
        try:
            writer.writerow(val.__dict__.items())
        except UnicodeEncodeError:
            writer.writerow(['bad data'])

    return response


create_csv_report.short_description = "Create a report for selected model instances"


def celery_issue_task_fetch_posts(infs=None):
    """
    here we issue a task to issue posts
    """
    if not infs:
        today = datetime.date.today()
        infs = Influencer.objects.filter(date_validated__contains=today, blacklisted=False).exclude(show_on_search=True)
        print "Ok, we have %d number of influencers to check " % infs.count()
    for inf in infs:
        selected_platforms = inf.platforms().filter(platform_name__in=Platform.BLOG_PLATFORMS).exclude(url_not_found=True)
        for platform in selected_platforms:
            print "issuing fetchertasks for %s " % platform
            fetchertasks.fetch_platform_data.apply_async(args=[platform.id],
                                                         link=estimation.estimate_if_fashion_blogger.subtask([inf.id], immutable=True),
                                                         queue='every_day.fetching.%s' % platform.platform_name,
                                                         routing_key='every_day.fetching.%s' % platform.platform_name)

def celery_issue_task_extract_social_handles(infs=None):
    """
    here we issue a task to extract platforms
    """
    if not infs:
        today = datetime.date.today()
        infs = Influencer.objects.filter(date_validated__contains=today, blacklisted=False).exclude(show_on_search=True)
        infs = infs.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
        infs = infs.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION)
        infs = infs.exclude(edit_history__field='recheck')
        print "Ok, we have %d number of influencers to check " % infs.count()

    for inf in infs:
        selected_platforms = Platform.objects.filter(platform_name__in=Platform.BLOG_PLATFORMS, influencer=inf).exclude(url_not_found=True)

        for i, pl in enumerate(selected_platforms):
            print '%d. Submitting extract_platforms_from_platform task for pl=%s' % (i, pl)
            platformextractor.extract_platforms_from_posts.apply_async([pl.id],
                                                                       queue="platform_extraction")

def pdo_stats_report(days):
    # Common tasks
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
    select
        pdo.operation,
        case when pdo.error_msg is not null then true else false end as error,
        extract(month from pdo.started) as month,
        extract(day from pdo.started) as day,
        count(*) as cnt
    from debra_platformdataop pdo
    where pdo.started >= current_timestamp - '{days} days'::interval
    and pdo.operation not in ('fetch_data', 'fetch_products_from_post')
    group by
        pdo.operation,
        case when pdo.error_msg is not null then true else false end,
        extract(month from pdo.started),
        extract(day from pdo.started)
    order by operation, error, month, day
    """.format(days=days))
    data = cur.fetchall()
    cur.close()

    # fetch_data tasks divided by platform_name and policy
    cur = connection.cursor()
    cur.execute("""
    with pdo_data as (
        select
            pl.platform_name,
            (pdo.data_json::json->'policy')::text as policy,
            case when pdo.error_msg is not null then true else false end as error,
            extract(month from pdo.started) as month,
            extract(day from pdo.started) as day
        from debra_platformdataop pdo
        join debra_platform pl on pl.id=pdo.platform_id
        where pdo.started >= current_timestamp - '{days} days'::interval
        and pdo.operation = 'fetch_data')
    select
        platform_name, policy, error, month, day,
        count(*) as cnt
    from pdo_data
    group by platform_name, policy, error, month, day
    order by platform_name, policy, error, month, day
    """.format(days=days))
    for platform_name, policy, error, month, day, cnt in cur.fetchall():
        data.append(('fetch_data.%s.%s' % (platform_name, policy[1:-1] if policy else '?'),
                     error, month, day, cnt))
    cur.close()

    # fetch_products_from_post tasks divided by platform_name
    cur = connection.cursor()
    cur.execute("""
    with pdo_data as (
        select
            pl.platform_name,
            case when pdo.error_msg is not null then true else false end as error,
            extract(month from pdo.started) as month,
            extract(day from pdo.started) as day
        from debra_platformdataop pdo
        join debra_posts po on pdo.post_id=po.id
        join debra_platform pl on pl.id=po.platform_id
        where pdo.started >= current_timestamp - '{days} days'::interval
        and pdo.operation = 'fetch_products_from_post')
    select
        platform_name, error, month, day,
        count(*) as cnt
    from pdo_data
    group by platform_name, error, month, day
    order by platform_name, error, month, day
    """.format(days=days))
    for platform_name, error, month, day, cnt in cur.fetchall():
        data.append(('fetch_products_from_post.%s' % platform_name, error, month, day, cnt))
    cur.close()

    data.sort()

    operations_from_queries = [r[0] for r in data]
    operations_from_op_dict = [x.operation for x in OpDict.objects.all()]
    operations = utils.unique_sameorder(sorted(operations_from_queries + operations_from_op_dict))

    # 2-level dict: day_spec -> operation -> data_dict
    by_day = defaultdict(lambda: defaultdict(dict))
    for operation, error, month, day, cnt in data:
        if error:
            k = 'with_error'
        else:
            k = 'without_error'
        by_day[(int(month), int(day))][operation][k] = cnt

    # set default values if no row was present in sql results
    for day_spec in by_day:
        for operation in by_day[day_spec]:
            for k in ('with_error', 'without_error'):
                if not k in by_day[day_spec][operation]:
                    by_day[day_spec][operation][k] = 0

    # set success rates
    for day_spec in by_day:
        for operation in by_day[day_spec]:
            d = by_day[day_spec][operation]
            total = d['without_error'] + d['with_error']
            if total == 0:
                d['success_pct'] = 0
            else:
                d['success_pct'] = (d['without_error'] * 100.0) / total

    day_specs = sorted(by_day.keys(), reverse=True)

    return dict(operations=operations, day_specs=day_specs, by_day=by_day)

def send_pdo_stats_email():
    from django.core.mail import mail_admins

    rep = pdo_stats_report(2)
    operations, day_specs, by_day = rep['operations'], rep['day_specs'], rep['by_day']
    # get the values for yesterday, so the data is complete
    ds = day_specs[1]
    data = by_day[ds]
    items = sorted(data.items(), key=lambda (operation, d): operation)
    #print('All items:\n%s', pprint.pformat(items))
    #items = [(operation, d) for (operation, d) in items if d['success_pct'] < 95]

    lines = []
    lines.append('{:<50} {:<10} {:<5} {:<5}'.format('task', 'success_pct', 'without_error', 'with_error'))
    for (operation, d) in items:
        lines.append('{:<50} {:.2f} {:<5} {:<5}'.format(operation, d['success_pct'], d['without_error'],
                                                 d['with_error']))
    body = '\n'.join(lines)
    mail_admins('PDO Stats Report', body)


def send_daily_posts_stats_email():
    from django.core.mail import mail_admins

    table = get_daily_posts_stats()
    mail_admins(
        'Daily Posts Stats',
        message=table.get_string(),
        html_message=table.get_html_string()
    )


def get_daily_posts_stats():
    from debra import db_util
    from prettytable import from_db_cursor
    sql = '''
        WITH last_week_posts AS (
            SELECT platform_id, inserted_datetime::date AS day, count(*) AS post_count,
                (CASE show_on_search WHEN true THEN true ELSE false END) AS searchable
            FROM debra_posts
            WHERE inserted_datetime > now() - '7 days'::interval
            GROUP BY platform_id, show_on_search, day
        )
        SELECT (CASE ps.searchable WHEN true then 'SEARCH' ELSE 'NOSEARCH' END) AS search,
            ps.day,
            p.platform_name,
            sum(ps.post_count) AS posts
        FROM last_week_posts ps INNER JOIN debra_platform p ON ps.platform_id = p.id
        GROUP BY ps.searchable, ps.day, p.platform_name
        ORDER BY ps.searchable DESC, ps.day DESC, p.platform_name
'''

    connection = db_util.connection_for_reading()
    cursor = connection.cursor()
    cursor.execute(sql)
    table = from_db_cursor(cursor)
    return table

def platform_ids_with_fetch_errors():
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute(platformcleanup.SQL_PLATFORM_IDS_WITH_FETCH_ERRORS)
    return [row[0] for row in cur]

def render_sql_results(request, sql, params, columns):
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    return render(request, 'pages/admin/results_table.html',
                  {'columns': columns, 'rows': rows},
                  context_instance=RequestContext(request))

class BrandsAdmin(ModelAdmin):
    list_display = ('supported','name','domain_name')
    list_display_links = ('name',)
    search_fields = ['supported','name']

class ProductModelAdmin(ModelAdmin):
    date_hierarchy = 'insert_date'
    list_display = ('c_idx','brand','name')
    search_fields = ['c_idx','brand__name','name']

class ProductPromotionAdmin(ModelAdmin):
#    date_hierarchy = 'insert_date'
    list_display = ('savings','promo','product')
#    list_display = ('savings','promo')
    readonly_fields=('promo','product')
    search_fields = ['promo__store__name',
                     'promo__code',
                     'product__product__product__brand__name',
                     'product__product__product__name',
                     'product__product__color',
                     'product__product__size',
                     'product__product__product__c_idx']

class CSMAdmin(ModelAdmin):
    search_fields = ['product__brand__name',
                     'product__name',
                     'color',
                     'size',
                     'product__c_idx']

class ProductAvailabilityAdmin(ModelAdmin):
    date_hierarchy = 'finish_time'
    list_display = ('avail','finish_time','product')
    list_display_links = ('avail','finish_time')
    readonly_fields=('product','finish_time')
    search_fields = ['product__product__brand__name','product__product__name','product__color','product__size','product__product__c_idx']

class PPAdmin(ModelAdmin):
    date_hierarchy = 'finish_time'
    list_display = ('price','shipping_cost','finish_time','product')
    list_display_links = ('price',)
    readonly_fields=('product','finish_time')
    search_fields = ['product__product__brand__name','product__product__name','product__color','product__size','product__product__c_idx']

class UserProfileAdmin(ModelAdmin):
    actions = [create_csv_report]





#####-----#####----- CUSTOM ADMIN SITE -----#####-----#####





class ModifyItemsAdminSite(AdminSite):
    """
    This **AdminSite** instance encapsulates everything rooted at */admin/upgrade/*
    """
    index_template = 'pages/admin/upgrade_view.html'

    def get_urls(self):
        urls = super(ModifyItemsAdminSite, self).get_urls()
        my_urls = patterns('',
            url(r'^inspiration/$', 'debra.explore_views.inspiration', {'admin_view': True}, name="admin_inspiration"),
            # user admin
            url(r'^user/modify/$', self.admin_view(self.modify_users), name="modify_all_users"),
            url(r'^user/(?P<user>\d+)/modify/$', self.admin_view(self.modify_users), name="modify_user"),
            url(r'^user/(?P<user>\d+)/details/$', self.admin_view(self.user_details), name="admin_user_details"),
            url(r'^user/(?P<user>\d+)/delete/$', self.admin_view(self.delete_user), name="admin_delete_user"),
            url(r'^user/(?P<user>\d+)/intercom-messages/$', self.admin_view(self.intercom_messages), name="intercom_messages"),
            url(r'^user/(?P<user>\d+)/emulate-signin/$', self.admin_view(self.signin_as_user), name="admin_signin"),
            # influencer admin
            url(r'^influencer/$', self.admin_view(self.influencers), name="influencers"),
            url(r'^influencer/import/$', self.admin_view(self.import_influencers), name="import_influencers"),
            url(r'^influencer/modify/$', self.admin_view(self.modify_influencers), name="modify_all_influencers"),
            url(r'^influencer/list/nonvalidated/$', self.admin_view(self.influencers_list_nonvalidated), name="influencers_list_nonvalidated"),
            url(r'^influencer/list/validated/$', self.admin_view(self.influencers_list_validated), name="influencers_list_validated"),
            url(r'^influencer/list/debug/$', self.admin_view(self.influencers_list_debug), name="influencers_list_debug"),
            url(r'^influencer/list/summary/$', self.admin_view(self.influencers_list_summary), name="influencers_list_summary"),
            url(r'^influencer/fashion/nonvalidated/$', self.admin_view(self.influencers_fashion_nonvalidated), name="influencers_fashion_nonvalidated"),
            url(r'^influencer/fashion/validated/$', self.admin_view(self.influencers_fashion_validated), name="influencers_fashion_validated"),
            url(r'^influencer/fashion/debug/$', self.admin_view(self.influencers_fashion_debug), name="influencers_fashion_debug"),
            url(r'^influencer/fashion/summary/$', self.admin_view(self.influencers_fashion_summary), name="influencers_fashion_summary"),
            url(r'^influencer/social/nonvalidated/$', self.admin_view(self.influencers_social_handles_nonvalidated), name="influencers_social_handles_nonvalidated"),
            url(r'^influencer/social/validated/$', self.admin_view(self.influencers_social_handles_validated), name="influencers_social_handles_validated"),
            url(r'^influencer/social/debug/$', self.admin_view(self.influencers_social_handles_debug), name="influencers_social_handles_debug"),
            url(r'^influencer/social/summary/$', self.admin_view(self.influencers_social_handles_summary), name="influencers_social_handles_summary"),
            url(r'^influencer/informations/nonvalidated/294255/(?P<section>[a-z_]+)/$', self.admin_view(self.influencers_informations_nonvalidated), name="influencers_informations_nonvalidated"),
            url(r'^influencer/informations/nonvalidated/294255/$', self.admin_view(self.influencers_informations_nonvalidated), name="influencers_informations_nonvalidated"),
            url(r'^influencer/informations/nonvalidated/automated$', self.admin_view(self.influencers_informations_nonvalidated_automated), name="influencers_informations_nonvalidated_automated"),
            url(r'^influencer/informations/validated/910240/$', self.admin_view(self.influencers_informations_validated), name="influencers_informations_validated"),
            url(r'^influencer/informations/all_categories_validated/$', self.admin_view(self.influencers_all_categories_validated), name="influencers_all_categories_validated"),
            url(r'^influencer/informations/validated/automated$', self.admin_view(self.influencers_informations_validated_automated), name="influencers_informations_validated_automated"),
            url(r'^influencer/informations/debug/$', self.admin_view(self.influencers_informations_debug), name="influencers_informations_debug"),
            url(r'^influencer/informations/summary/$', self.admin_view(self.influencers_informations_summary), name="influencers_informations_summary"),
            url(r'^influencer/informations/recently_upgraded/', self.admin_view(self.influencers_informations_newly_upgraded), name="influencers_informations_newly_upgraded"),
            url(r'^influencer/informations/blogspot_duplicates/', self.admin_view(self.influencers_informations_blogspot_duplicates), name="influencers_informations_blogspot_duplicates"),
            url(r'^influencer/informations/male_bloggers/', self.admin_view(self.influencers_informations_male_bloggers), name="influencers_informations_male_bloggers"),
            url(r'^influencer/informations/in_collections/', self.admin_view(self.influencers_informations_in_collections), name="influencers_informations_in_collections"),
            url(r'^influencer/informations/bad_email/', self.admin_view(self.influencers_informations_bad_email), name="influencers_informations_bad_email"),
            url(r'^influencer/informations/missing_email/', self.admin_view(self.influencers_informations_missing_email), name="influencers_informations_missing_email"),
            url(r'^influencer/informations/mandrill_error/', self.admin_view(self.influencers_informations_mandrill_error), name="influencers_informations_mandrill_error"),

            url(r'^influencer/informations/duplicate_social/(?P<platform_name>[\w\W]*)/', self.admin_view(self.influencers_informations_duplicate_social), name="influencers_informations_duplicate_social"),
            # url(r'^influencer/informations/duplicate_pinterest/', self.admin_view(self.influencers_informations_bad_email), name="influencers_informations_bad_email"),
            # url(r'^influencer/informations/duplicate_twitter/', self.admin_view(self.influencers_informations_bad_email), name="influencers_informations_bad_email"),
            # url(r'^influencer/informations/duplicate_instagram/', self.admin_view(self.influencers_informations_bad_email), name="influencers_informations_bad_email"),
            # url(r'^influencer/informations/duplicate_youtube/', self.admin_view(self.influencers_informations_bad_email), name="influencers_informations_bad_email"),


            #### ALL influencers
            url(r'^influencer/informations/all/$', self.admin_view(self.influencers_informations_all), name="influencers_informations_all"),

            url(r'^influencer/create_influencer_and_blog_platform/bunch', self.admin_view(self.create_influencer_and_blog_platform_bunch), name="create_influencer_and_blog_platform_bunch"),

            #### all suspects in one table, but only for daily updated influencers
            url(r'^influencer/informations/suspect_daily_combined/$', self.admin_view(self.influencers_suspect_daily_combined), name="influencers_suspect_daily_combined"),



            #### all suspects in one table each
            url(r'^influencer/informations/suspect_url_content/$', self.admin_view(self.influencers_suspect_url_content), name="influencers_suspect_url_content"),
            url(r'^influencer/informations/suspect_url/$', self.admin_view(self.influencers_suspect_url), name="influencers_suspect_url"),
            url(r'^influencer/informations/suspect_email/$', self.admin_view(self.influencers_suspect_email), name="influencers_suspect_email"),
            url(r'^influencer/informations/suspect_name_similarities/$', self.admin_view(self.influencers_suspect_name_similarities), name="influencers_suspect_name_similarities"),
            url(r'^influencer/informations/suspect_blogname/$', self.admin_view(self.influencers_suspect_blogname), name="influencers_suspect_blogname"),
            url(r'^influencer/informations/suspect_descriptions/$', self.admin_view(self.influencers_suspect_descriptions), name="influencers_suspect_descriptions"),
            url(r'^influencer/informations/suspect_locations/$', self.admin_view(self.influencers_suspect_locations), name="influencers_suspect_locations"),
            url(r'^influencer/informations/suspect_duplicate_social/$', self.admin_view(self.influencers_suspect_duplicate_social), name="influencers_suspect_duplicate_social"),
            url(r'^influencer/informations/suspect_broken_social/$', self.admin_view(self.influencers_suspect_broken_social), name="influencers_suspect_broken_social"),
            url(r'^influencer/informations/suspect_social_follower_outliers/$', self.admin_view(self.influencers_suspect_social_follower_outliers), name="influencers_suspect_social_follower_outliers"),
            url(r'^influencer/informations/suspect_highcomments_low_social_platforms/$', self.admin_view(self.influencers_suspect_highcomments_low_social_platforms), name="influencers_suspect_highcomments_low_social_platforms"),
            url(r'^influencer/informations/suspect_highfollowers_low_social_platforms/$', self.admin_view(self.influencers_suspect_highfollowers_low_social_platforms), name="influencers_suspect_highfollowers_low_social_platforms"),
            url(r'^influencer/informations/suspect_social_handles/$', self.admin_view(self.influencers_suspect_social_handles), name="influencers_suspect_social_handles"),
            url(r'^influencer/informations/suspect_no_comments/$', self.admin_view(self.influencers_suspect_no_comments), name="influencers_suspect_no_comments"),
            url(r'^influencer/informations/suspect_highpostscount_low_social_platforms/$', self.admin_view(self.influencers_suspect_highpostscount_low_social_platforms), name="influencers_suspect_highpostscount_low_social_platforms"),


            url(r'^influencer/current_search/summary/292241/$', self.admin_view(self.influencers_current_search_summary), name="influencers_current_search_summary"),
            url(r'^influencer/signed_up_bloggers/initialize/124199/$', self.admin_view(self.influencers_blogger_signedup_initialize), name="influencers_blogger_signedup_initialize"),
            url(r'^influencer/signed_up_bloggers/qaed_but_not_on_search/124199/$', self.admin_view(self.influencers_blogger_signedup_check), name="influencers_blogger_signedup_check"),
            url(r'^influencer/signed_up_bloggers/qaed_on_search/$', self.admin_view(self.influencers_qaed_on_search), name="influencers_qaed_on_search"),
            url(r'^influencer/signed_up_bloggers/ready_for_upgrade/$', self.admin_view(self.influencers_ready_for_upgrade), name="influencers_ready_for_upgrade"),
            url(r'^influencer/signed_up_bloggers/with_suspicious_url/$', self.admin_view(self.influencers_with_suspicious_url), name="influencers_with_suspicious_url"),
            url(r'^influencer/signed_up_bloggers/all_qaed/124199/$', self.admin_view(self.influencers_blogger_signedup_notify), name="influencers_blogger_signedup_notify"),

            url(r'^influencer/submitted_by_users/(?P<post_collection_id>\d+)/$', self.admin_view(self.influencers_submitted_by_users), name="influencers_submitted_by_users"),
            url(r'^influencer/submitted_by_users/$', self.admin_view(self.influencers_submitted_by_users), name="influencers_submitted_by_users"),
            url(r'^influencer/uploaded_by_customers/$', self.admin_view(self.influencers_uploaded_by_customers), name="influencers_uploaded_by_customers"),
            url(r'^post_analytics_collections_with_loading_entries/$', self.admin_view(self.post_analytics_collections_with_loading_entries), name="post_analytics_collections_with_loading_entries"),

            url(r'^influencer/current_search_potential/summary/$', self.admin_view(self.influencers_current_search_potential_summary), name="influencers_current_search_potential_summary"),
            url(r'^influencer/admin/$', self.admin_view(self.influencers_admin), name="influencers_admin"),
            url(r'^influencer/(?P<influencer>\d+)/modify/$', self.admin_view(self.modify_influencers), name="modify_influencer"),
            url(r'^influencer/(?P<influencer>\d+)/platform/(?P<platform>\d+)/delete/$', self.admin_view(self.delete_influencer_platform), name="delete_influencer_platform"),
            #influencers with slices
            # url(r'^influencer/list/nonvalidated/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_list_nonvalidated), name="influencers_list_nonvalidated"),
            # url(r'^influencer/list/validated/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_list_validated), name="influencers_list_validated"),
            # url(r'^influencer/fashion/nonvalidated/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_fashion_nonvalidated), name="influencers_fashion_nonvalidated"),
            # url(r'^influencer/fashion/validated/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_fashion_validated), name="influencers_fashion_validated"),
            # url(r'^influencer/social/nonvalidated/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_social_handles_nonvalidated), name="influencers_social_handles_nonvalidated"),
            # url(r'^influencer/social/validated/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_social_handles_validated), name="influencers_social_handles_validated"),
            # url(r'^influencer/informations/nonvalidated/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_informations_nonvalidated), name="influencers_informations_nonvalidated"),
            # url(r'^influencer/informations/nonvalidated/qa/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_informations_nonvalidated_qa), name="influencers_informations_nonvalidated_qa"),
            # url(r'^influencer/informations/validated/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_informations_validated), name="influencers_informations_validated"),
            # url(r'^influencer/informations/validated/qa/(?P<no_slices>\d+)/(?P<current_slice>\d+)/$', self.admin_view(self.influencers_informations_validated_qa), name="influencers_informations_validated_qa"),
            #influencers with queues
            url(r'^influencer/informations/nonvalidated/automated/(?P<uuid>.*?)/$', self.admin_view(self.influencers_informations_nonvalidated_automated), name="influencers_informations_nonvalidated_automated"),
            url(r'^influencer/informations/validated/automated/(?P<uuid>.*?)/$', self.admin_view(self.influencers_informations_validated_automated), name="influencers_informations_validated_automated"),
            url(r'^influencer/informations/validated/error/(?P<urltype>.*?)$', self.admin_view(self.influencers_informations_validated_error), name="influencers_informations_validated_error"),
            url(r'^influencer/informations/validated/error_duplicate/$', self.admin_view(self.influencers_informations_validated_duplicate_error), name="influencers_informations_validated_duplicate_error"),
            url(r'^influencer/informations/high_priority/$', self.admin_view(self.influencers_informations_high_priority), name="influencers_informations_high_priority"),
            url(r'^influencer/social/nonvalidated/(?P<uuid>.*?)$', self.admin_view(self.influencers_social_handles_nonvalidated), name="influencers_social_handles_nonvalidated"),
            url(r'^influencer/social/validated/(?P<uuid>.*?)$', self.admin_view(self.influencers_social_handles_validated), name="influencers_social_handles_validated"),
            url(r'^influencer/informations/nonvalidated/(?P<uuid>.*?)$', self.admin_view(self.influencers_informations_nonvalidated), name="influencers_informations_nonvalidated"),
            url(r'^influencer/informations/validated/(?P<uuid>.*?)$', self.admin_view(self.influencers_informations_validated), name="influencers_informations_validated"),
            url(r'^influencer/informations/fake/$', self.admin_view(self.influencers_informations_fake), name="influencers_informations_fake"),
            url(r'^influencer/informations/influencers_profiles_check/$', self.admin_view(self.influencers_profiles_check), name="influencers_profiles_check"),


            # posts admin
            url(r'^post/modify/$', self.admin_view(self.modify_posts), name="modify_all_posts"),
            # brand admin
            url(r'^brand/modify/$', self.admin_view(self.modify_brands), name="modify_all_brands"),
            url(r'^brand/(?P<brand>\d+)/modify/$', self.admin_view(self.modify_brands), name="modify_brand"),
            url(r'^brand/(?P<brand>\d+)/details/$', self.admin_view(self.brand_details), name="admin_brand_details"),
            url(r'^brand/list_auto_non_blacklisted/$', self.admin_view(self.brands_list_auto_non_blacklisted), name="brands_list_auto_non_blacklisted"),
            url(r'^brand/list_auto_blacklisted/$', self.admin_view(self.brands_list_auto_blacklisted), name="brands_list_auto_blacklisted"),
            url(r'^brand/list_edited_non_blacklisted/$', self.admin_view(self.brands_list_edited_non_blacklisted), name="brands_list_edited_non_blacklisted"),
            url(r'^brand/list_edited_blacklisted/$', self.admin_view(self.brands_list_edited_blacklisted), name="brands_list_edited_blacklisted"),
            url(r'^brand/flags/$', self.admin_view(self.brand_flags), name="brand_flags"),
            url(r'^post_analytics_collection_monitoring/$', self.admin_view(self.post_analytics_collection_monitoring), name='post_analytics_collection_monitoring'),
            url(r'^report_monitoring/$', self.admin_view(self.report_monitoring), name='report_monitoring'),
            url(r'^tag_monitoring/$', self.admin_view(self.tag_monitoring), name='tag_monitoring'),
            # (r'^post_analytics_collection_copying/$', self.admin_view(self.post_analytics_collection_copying), name='post_analytics_collection_copying'),
            url(r'^brand/signup/$', self.admin_view(self.brand_signup), name="brand_signup"),

            # item admin
            url(r'^product/modify/$', self.admin_view(self.modify_products), name="modify_all_products"),
            url(r'^product/(?P<product>\d+)/details/$', self.admin_view(self.product_details), name="admin_product_details"),
            # affects admin user
            url(r'^delete-test-email/(?P<user>\d+)/$', self.admin_view(self.delete_test_email), name="delete_test_email"),
            # reports
            url(r'^report/health/$', self.admin_view(self.report_health), name="report_health"),
            url(r'^report/main_summary/$', self.admin_view(self.report_main_summary), name="report_main_summary"),
            url(r'^report/social/$', self.admin_view(self.report_social), name="report_social"),
            url(r'^report/social/summary/$', self.admin_view(self.report_social), name="report_social_summary"),
            url(r'^report/pipeline_summary/$', self.admin_view(self.pipeline_summary), name="report_pipeline_summary"),
            url(r'^report/daily_stats/$', self.admin_view(self.daily_stats), name="report_daily_stats"),
            url(r'^report/pdo_stats/$', self.admin_view(self.pdo_stats), name="report_pdo_stats"),
            url(r'^report/pdo_error_stats/$', self.admin_view(self.pdo_error_stats), name="report_pdo_error_stats"),
            url(r'^report/pdo_all_errors/$', self.admin_view(self.pdo_all_errors), name="report_pdo_all_errors"),
            url(r'^report/hit_influencers_that_joined/$', self.admin_view(self.hit_influencers_that_joined), name="report_pdo_all_errors"),
            url(r'^queue/$', self.admin_view(self.queue_list), name="queue-list"),
            url(r'^queue/(?P<uuid>.*?)/(?P<command>.*?)$', self.admin_view(self.queue), name="queue"),
            url(r'^queue/(?P<uuid>.*?)$', self.admin_view(self.queue), name="queue"),

            url(r'^remove_user_account/(?P<user>.*?)$', self.admin_view(self.remove_user_account), name="remove_user_account"),

            url(r'^popups_demo$', self.admin_view(self.popups_demo), name="popups_demo"),
            url(r'^user_manual_verify/$', self.admin_view(self.user_manual_verify), name="user_manual_verify"),
            url(r'^copy_saved_searches/$', self.admin_view(self.copy_saved_searches), name="copy_saved_searches"),
            url(r'^influencer_manual_verify/$', self.admin_view(self.influencer_manual_verify), name="influencer_manual_verify"),
            url(r'^user_manual_verify/confirm$', self.admin_view(self.user_manual_verify_confirm), name="user_manual_verify_confirm"),
            url(r'^brand_usage_details/(?P<brand_id>.*?)$', self.admin_view(self.brand_usage_details), name="brand_usage_details"),
            url(r'^brand_trial_on$', self.admin_view(self.brand_trial_on), name="brand_trial_on"),
            url(r'^brand_fake_mode_on$', self.admin_view(self.brand_fake_mode_on), name="brand_fake_mode_on"),
            url(r'^set_trial_password$', self.admin_view(self.set_trial_password), name="set_trial_password"),
            url(r'^influencer_tests/$', self.admin_view(self.influencers_tests), name="influencers_tests"),
            url(r'^influencer_tests/create/1$', self.admin_view(self.create_influencer_1), name="influencers_tests_c1"),
            url(r'^influencer_tests/create/2$', self.admin_view(self.create_influencer_2), name="influencers_tests_c2"),
            url(r'^influencer_tests/delete/1$', self.admin_view(self.delete_influencer_1), name="influencers_tests_d1"),
            url(r'^influencer_tests/delete/2$', self.admin_view(self.delete_influencer_2), name="influencers_tests_d2"),
            url(r'^influencer_tests/deleteu/1$', self.admin_view(self.delete_user_1), name="influencers_tests_du1"),
            url(r'^influencer_tests/deleteu/2$', self.admin_view(self.delete_user_2), name="influencers_tests_du2"),
            url(r'^influencer_tests/deleteu/3$', self.admin_view(self.delete_user_3), name="influencers_tests_du3"),

            url(r'^hide_influencer_from_search/$', self.admin_view(self.hide_influencer_from_search), name="hide_influencer_from_search"),

            url(r'^login_as/influencer/(?P<influencer_id>.*?)$', self.admin_view(self.login_as_influencer), name="login_as_influencer"),
            url(r'^login_as/user/(?P<user_id>.*?)$', self.admin_view(self.login_as_user), name="login_as_user"),
        )
        return my_urls + urls

    #### debug! ####

    def login_as_influencer(self, request, influencer_id):
        influencer = Influencer.objects.get(id=influencer_id)
        user = influencer.shelf_user
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        return redirect(user.userprofile.after_login_url)

    def login_as_user(self, request, user_id):
        user = UserModel.objects.get(id=user_id)
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        if user.username.startswith('theshelf') and user.username.endswith('.toggle'):
            return redirect('/account/settings')
        else:
            return redirect(user.userprofile.after_login_url)

    def hide_influencer_from_search(self, request):
        if request.method == 'POST':
            influencer_id = request.POST.get("influencer_id")
            influencer = Influencer.objects.get(id=influencer_id)
            influencer.set_blacklist_with_reason('from_admin_panel')
            for up in influencer.userprofile_set.all():
                up.user.is_active = False
                up.user.save()
            if influencer.shelf_user:
                influencer.shelf_user.is_active = False
                influencer.shelf_user.save()
            influencer.set_show_on_search(False, save=True)
        return redirect(reverse("upgrade_admin:user_manual_verify"))

    def brand_trial_on(self, request):
        if request.method == 'POST':
            brand_id = request.POST.get("brand_id")
            brand = Brands.objects.get(id=brand_id)
            print("Got brand: %s  Trial_flag: %s" % (brand, brand.flag_trial_on))
            # find all users that are connected to this brand
            brand_profs_mapping = UserProfileBrandPrivilages.objects.filter(brand=brand)
            for bp in brand_profs_mapping:
                p = bp.user_profile
                print("Got profile: %s" % p)
                if brand.flag_trial_on:
                    # if brand's trial is already on, now we're going to disable it
                    p.intercom_tag_del('trial')
                    p.intercom_tag_add('trial_finished')
                else:
                    p.intercom_tag_add('trial')
            brand.flag_trial_on = not brand.flag_trial_on
            brand.blacklisted = False
            brand.save()
        return redirect(reverse("upgrade_admin:user_manual_verify"))

    def brand_fake_mode_on(self, request):
        if request.method == 'POST':
            brand_id = request.POST.get("brand_id")
            brand = Brands.objects.get(id=brand_id)
            brand.flag_show_dummy_data = not brand.flag_show_dummy_data
            brand.save()
            cache.clear()
        return redirect(reverse("upgrade_admin:user_manual_verify"))

    def set_trial_password(self, request):
        if request.method == 'POST':
            user_id = request.POST.get("user_id")
            user = UserModel.objects.get(id=user_id)
            user.set_password(TRIAL_PASSWORD)
            user.save()
        return redirect(reverse("upgrade_admin:user_manual_verify"))

    def brand_usage_details(self, request, brand_id):
        from debra.models import MailProxyMessage
        from debra.serializers import ConversationNoEventsSerializer
        b = Brands.objects
        b = b.prefetch_related('saved_queries')
        b = b.prefetch_related('job_posts__creator')
        b = b.prefetch_related('job_posts__oryg_creator')
        b = b.prefetch_related('job_posts__collection__creator_brand')
        b = b.prefetch_related('job_posts__collection__owner_brand')
        b = b.prefetch_related('job_posts')
        b = b.prefetch_related('influencer_groups__creator_brand')
        b = b.prefetch_related('influencer_groups__owner_brand')
        b = b.prefetch_related('influencer_groups')
        b = b.get(id=brand_id)
        m = MailProxyMessage.objects
        m = m.prefetch_related('thread__mapping__group')
        m = m.prefetch_related('thread__mapping')
        m = m.prefetch_related('thread__candidate_mapping__job')
        m = m.prefetch_related('thread__candidate_mapping')
        m = m.prefetch_related('thread__brand')
        m = m.prefetch_related('thread__influencer__shelf_user__userprofile')
        m = m.prefetch_related('thread__influencer__shelf_user')
        m = m.prefetch_related('thread__influencer')
        m = m.prefetch_related('thread')
        m = m.filter(thread__brand=b, type=MailProxyMessage.TYPE_EMAIL).order_by('-ts')
        m_data = []
        for d in ConversationNoEventsSerializer(m, many=True).data:
            m_data.append(dict(d))
        return render(request, 'pages/admin/brand_usage_details.html', {
            'brand': b,
            'mails': m_data,
            'm_count': len(m_data)
        }, context_instance=RequestContext(request))

    def user_manual_verify_confirm(self, request):
        if request.method == "POST":
            email = request.POST.get("email")
            type = request.POST.get("type")
            user = UserModel.objects.get(email=email)
            user_prof = user.userprofile
            if type == "brand":
                brand = Brands.objects.filter(domain_name__iexact=user_prof.temp_brand_domain)
                if not brand:
                    print("Connecting user %s to non existing brand %s !" % (user, user_prof.temp_brand_domain))
                else:
                    brand = brand[0]
                brand_helpers.sanity_checks(brand)
                user_prof.temp_brand_domain = None
                user_prof.save()
                brand_helpers.connect_user_to_brand(brand, user_prof)
                account_helpers.intercom_track_event(None, "brand-ownership-verified", {
                    'email': user.email,
                    'brand_url': brand.domain_name,
                    'manual': True,
                    'success': True,
                }, user)
            elif type == "blogger":
                user_prof.blog_verified = True
                account_helpers.create_and_connect_user_to_influencer.apply_async(
                    [user_prof.id], queue='celery')
                user_prof.save()
            elif type == "email":
                from debra.custom_backend import post_activation
                user.is_active = True
                user.save()
                post_activation(None, user)
        return redirect(reverse("upgrade_admin:user_manual_verify"))

    def user_manual_verify(self, request):
        if request.method == "POST":
            data = {
                "query": request.POST.get("email")
            }
            users_qs = UserModel.objects.all()
            if request.POST.get("email"):
                users_qs = users_qs.filter(
                    email__icontains=request.POST.get("email"))
            elif request.POST.get('campaign_id'):
                _campaign = BrandJobPost.objects.get(
                    id=request.POST.get('campaign_id'))
                users_qs = users_qs.filter(
                    userprofile__brand_privilages__brand_id=_campaign.creator_id)
            elif request.POST.get("brand"):
                users_qs = users_qs.filter(
                    userprofile__brand_privilages__brand__id=request.POST.get(
                        "brand"))
            elif request.POST.get("brand_domain_name"):
                users_qs = users_qs.filter(
                    userprofile__brand_privilages__brand__domain_name__icontains=request.POST.get("brand_domain_name"))
            elif request.POST.get("user"):
                users_qs = users_qs.filter(id=request.POST.get("user"))
            elif request.POST.get("influencer"):
                users_qs = users_qs.filter(
                    userprofile__influencer__id=request.POST.get("influencer"))
            else:
                raise ValueError('Unexpected POST state for user_manual_verify: {}'.format(request.POST))


            users_qs = users_qs.select_related(
                'brand',
            ).prefetch_related(
                'userprofile__brand_privilages__brand',
            )
            users = list(users_qs)

            is_subscribed = dict(Brands.objects.filter(
                domain_name__in=[
                    u.userprofile.temp_brand_domain for u in users]
            ).values_list('domain_name', 'is_subscribed'))



            for user in users:
                profile = user.userprofile
                if not profile:
                    continue
                if profile.blog_page:
                    user.type = "blogger"
                    user.blog = profile.blog_page
                    user.verified = profile.blog_verified
                    user.subscribed = False
                elif profile.temp_brand_domain:
                    user.type = "brand"
                    user.brand = profile.temp_brand_domain
                    user.verified = False
                    # user.subscribed = Brands.objects.get(domain_name=profile.temp_brand_domain).is_subscribed
                    user.subscribed = is_subscribed.get(
                        profile.temp_brand_domain, False)
                elif profile.brand_privilages.all():
                    user.type = "brand"
                    user.brand = profile.associated_brand.domain_name
                    user.brand_id = profile.associated_brand.id
                    user.verified = True
                    user.trial_on = profile.associated_brand.flag_trial_on
                    user.flag_show_dummy_data = profile.associated_brand.flag_show_dummy_data
                    user.subscribed = profile.associated_brand.is_subscribed
                elif profile.brand:
                    user.type = "brand"
                    user.brand = profile.brand.domain_name
                    user.verified = True
                    user.subscribed = profile.brand.is_subscribed
                else:
                    user.type = "shopper"
            data["users"] = users
            return render(request, 'pages/admin/user_manual_verify.html', data, context_instance=RequestContext(request))
        else:
            return render(request, 'pages/admin/user_manual_verify.html', {}, context_instance=RequestContext(request))


    def copy_saved_searches(self, request):
        from debra.models import SearchQueryArchive

        brand = Brands.objects.get(id=int(request.GET.get('brand_id')))
        source_brand = Brands.objects.get(id=313191)
        user = UserModel.objects.get(id=int(request.GET.get('user_id')))

        if request.method == "POST":
            selected_ids = map(
                int, request.POST.getlist('selected_saved_searches'))
            saved_queries = SearchQueryArchive.objects.filter(
                id__in=selected_ids)

            for query in saved_queries:
                query.pk = None
                query.brand = brand
                query.user = user
                query.save()
            
            return HttpResponseRedirect(reverse('upgrade_admin:user_manual_verify'))
        else:
            saved_queries = source_brand.saved_queries.exclude(
                name__isnull=True
            ).exclude(
                archived=True
            ).order_by('name')

            context = {
                'brand': brand,
                'saved_queries': saved_queries,
            }
            return render(request, 'pages/admin/copy_saved_searches.html', context, context_instance=RequestContext(request))


    def influencer_manual_verify(self, request):
        if request.method == "POST":
            data = {
                "query": request.POST.get("email")
            }

            q_list = []

            if request.POST.get('influencer'):
                q_list.append(Q(id=request.POST.get('influencer')))
            else:
                if request.POST.get('blog_url'):
                    q_list.append(Q(blog_url__icontains=request.POST.get('blog_url')))
                if request.POST.get('influencer_name'):
                    q_list.append(Q(name__icontains=request.POST.get('influencer_name')))
                if request.POST.get('email'):
                    q_list.append(
                        Q(email_for_advertising_or_collaborations__icontains=request.POST.get('email')) |
                        Q(email_all_other__icontains=request.POST.get('email')) |
                        Q(shelf_user__email__icontains=request.POST.get('email'))
                    )

            if q_list:
                infs = Influencer.objects.filter(*q_list).prefetch_related(
                    'shelf_user__userprofile')
            else:
                infs = []

            # for inf in infs:
                # user.blog =user.shelf_user.userprofile.blog_page
                # user.verified = user.shelf_user.userprofile.blog_verified
                # user.subscribed = False

            data["infs"] = infs
            return render(request, 'pages/admin/influencer_manual_verify.html', data, context_instance=RequestContext(request))
        else:
            return render(request, 'pages/admin/influencer_manual_verify.html', {}, context_instance=RequestContext(request))

    def influencers_tests(self, request):
        return render(request, 'pages/admin/influencers_tests.html', {}, context_instance=RequestContext(request))

    def create_influencer_1(self, request):
        Influencer.objects.create(email="lauren02468@yahoo.com", blog_url="laurenandjessiblog.com")
        return HttpResponseRedirect(reverse('upgrade_admin:influencers_tests'))
    def create_influencer_2(self, request):
        Influencer.objects.create(blog_url="laurenstestingblog.blogspot.com")
        return HttpResponseRedirect(reverse('upgrade_admin:influencers_tests'))
    def delete_influencer_1(self, request):
        Influencer.objects.filter(email="lauren02468@yahoo.com").delete()
        Influencer.objects.filter(blog_url__icontains="laurenandjessiblog.com").delete()
        return HttpResponseRedirect(reverse('upgrade_admin:influencers_tests'))
    def delete_influencer_2(self, request):
        Influencer.objects.filter(blog_url__icontains="laurenstestingblog.blogspot.com").delete()
        return HttpResponseRedirect(reverse('upgrade_admin:influencers_tests'))
    def delete_user_1(self, request):
        UserModel.objects.filter(email="lauren02468@yahoo.com").delete()
        return HttpResponseRedirect(reverse('upgrade_admin:influencers_tests'))
    def delete_user_2(self, request):
        UserModel.objects.filter(email="laurensingh.stores@gmail.com").delete()
        return HttpResponseRedirect(reverse('upgrade_admin:influencers_tests'))
    def delete_user_3(self, request):
        UserModel.objects.filter(email="lauren_jung@aol.com").delete()
        Brands.objects.filter(domain_name="aol.com").delete()
        UserModel.objects.filter(email="theshelf@aol.com.toggle").delete()
        return HttpResponseRedirect(reverse('upgrade_admin:influencers_tests'))

    def queue_list(self, request, command=None):
        queues = InfluencerValidationQueue.objects.all().distinct('uuid')
        data = {
            'queues': queues
        }
        return render(request, 'pages/admin/queue_list.html', data, context_instance=RequestContext(request))

    def queue(self, request, uuid, command=None):
        if command:
            if command.startswith("add_"):
                if command == 'add_influencers':
                    excludes = {
                        "validated_on": '["%s"]' % ADMIN_TABLE_INFLUENCER_INFORMATIONS
                    }
                    filters = {
                        "show_on_search":True,
                        "validation_queue__isnull":True
                    }
                if command == 'add_influencers_nonqa':
                    excludes = {
                        "validated_on": '["%s"]' % ADMIN_TABLE_INFLUENCER_INFORMATIONS
                    }
                    filters = {
                        "source":'comments_import',
                        "blog_url__isnull":False,
                        "blacklisted":False,
                        "relevant_to_fashion":True,
                        "posts_count__gt":1,
                        "profile_pic_url__isnull":False,
                        "validation_queue__isnull":True
                    }
                entries = []
                for influencer in Influencer.objects.active().exclude(**excludes).filter(**filters)[:100]:
                    entries.append(InfluencerValidationQueue(uuid=uuid, influencer=influencer, state=1))
                InfluencerValidationQueue.objects.bulk_create(entries)
            return HttpResponseRedirect(reverse('upgrade_admin:queue', args=(uuid,)))

        user_queue = InfluencerValidationQueue.objects.filter(uuid=uuid)
        data = {
            'uuid': uuid,
            'total': user_queue.count(),
            'unknown': user_queue.filter(state=0).count(),
            'queued': user_queue.filter(state=1).count(),
            'validated': user_queue.filter(state=2).count(),
        }
        return render(request, 'pages/admin/queue.html', data, context_instance=RequestContext(request))

    def popups_demo(self, request):
        return render(request, 'pages/admin/popups_demo.html', {}, context_instance=RequestContext(request))

    def remove_user_account(self, request, user=None):
        if user == "atul":
            user = UserModel.objects.filter(email="atul_44@yahoo.com")
            brand = Brands.objects.filter(domain_name__contains="yahoo.com")
        elif user == "lauren":
            user = UserModel.objects.filter(email="lauren_jung@aol.com")
            brand = Brands.objects.filter(domain_name__contains="aol.com")
        else:
            return HttpResponse("please append 'atul' or 'lauren' at end of this url")
        brand.delete()
        user.delete()
        return HttpResponse("ok! removed<a href='/admin/upgrade'>go back</a>")

    #####-----< User Admin Actions >-----#####
    def modify_users(self, request, user=0):
        """
        :param request: an ``HttpRequest`` instance
        :param user: if proved, this is the id of a particular :class:`debra.models.UserProfile` we are modifying
        :return: ``HttpResponse`` instance

        If the request is a ``GET`` request and it's ajax, we know we've either hit infinite scroll or the user has
        selected an autocomplete result. In either case, just re-render the portion of the page that needs to be updated
        (so the template file */admin/users.html*) with the filtered :class:`debra.models.UserProfile` ``QuerySet``. If
        it was not an ajax request, then get all non-brand :class:`debra.models.UserProfile`'s, filter them according
        the url arguments, and render the *feed_container.html* template file with these users.

        If the request is a ``POST`` request, then populate a :class:`debra.forms.ModifyUserForm` instance with the
        ``POST`` data as well as the :class:`debra.models.UserProfile` instance given by the id from the url.
        """
        if request.method == 'POST':
            user_prof = UserProfile.objects.get(id=user)

            form = ModifyUserForm(data=request.POST, instance=user_prof)
            if form.is_valid():
                form.save()
                user_prof.admin_categorized = True
                user_prof.save()
            return HttpResponse(status=200)
        else:
            if request.is_ajax():
                # autocomplete
                autocomplete = request.GET.get('q', None)
                users = UserProfile.objects.filter(id=autocomplete)

                return render(request, 'pages/admin/users.html', {
                    'users': users
                }, context_instance=RequestContext(request))
            else:
                users = UserProfile.objects.filter(brand__isnull=True).select_related('user').order_by('-num_followers')

                filter_str = request.GET.get('filters', '')
                filter_list = filter_str.split(',') if filter_str != '' else []
                for f in filter_list:
                    f_name, f_op, f_val = f.split('|')
                    # for the has_collage field we have to do special stuff, since its not a field on user
                    if f_name == 'has_collage':
                        filter_cond = lambda u: u.has_collage if bool(int(f_val)) else not u.has_collage
                        users = UserProfile.objects.filter(id__in=[u.id for u in UserProfile.objects.filter(is_trendsetter=False) if filter_cond(u)])
                    else:
                        users = h.dynamic_filter(users, f_name, f_op, f_val)

                # because for whatever reason django-endless isnt working right on this page, manually page items
                page = int(request.GET.get('page', 1))
                upper = page * 50
                paged = [u for u in users[(upper - 50):upper]]

                return render(request, 'pages/admin/feed_container.html', {
                    'filter': 'pages/admin/filters/users.html',
                    'container': 'users_container',
                    'admin_page': 'users',
                    'user_search': True,
                    'one_column': True,
                    'bottom_button': True,
                    'next_page': '{base}?page={page}&filters={filters}'.format(base=reverse('upgrade_admin:modify_all_users'),
                                                                               page=page + 1,
                                                                               filters=filter_str),
                    'total_num_bloggers': users.filter(can_set_affiliate_links=True).count(),
                    'userprofile_class': UserProfile,
                    'feed_items': render_to_string('pages/admin/users.html', {
                        'users': paged
                    }, context_instance=RequestContext(request))
                })

    def user_details(self, request, user=0):
        """
        :param request: an ``HttpRequest`` instance
        :param user: the :class:`debra.models.UserProfile` to get detailed data for
        :return: ``HttpResponse`` instance
        """
        user_prof = UserProfile.objects.get(id=user)
        user_posts = user_prof.get_all_posts.order_by('-create_date')
        num_facebook_posts = user_posts.filter(platform__platform_name="Facebook").count()
        num_blog_posts = user_posts.filter(platform__platform_name='Blogspot').count()
        num_wordpress_posts = user_posts.filter(platform__platform_name='Wordpress').count()
        num_twitter_posts = user_posts.filter(platform__platform_name="Twitter").count()
        num_pinterest_posts = user_posts.filter(platform__platform_name="Pinterest").count()
        num_instagram_posts = user_posts.filter(platform__platform_name="Instagram").count()

        if request.is_ajax():
            return render(request, 'pages/admin/user_details.html', {
                'num_facebook_posts': num_facebook_posts,
                'num_blog_posts': num_blog_posts,
                'num_wordpress_posts': num_wordpress_posts,
                'num_twitter_posts': num_twitter_posts,
                'num_pinterest_posts': num_pinterest_posts,
                'num_instagram_posts': num_instagram_posts,
                'feed_items': [i for i in user_posts]
            })
        else:
            return render(request, 'pages/admin/feed_container.html', {
                'filter': 'pages/admin/filters/user_details.html',
                'container': 'user_details_container',
                'user': user_prof,
                'feed_items': render_to_string('pages/admin/user_details.html', {
                    'num_facebook_posts': num_facebook_posts,
                    'num_blog_posts': num_blog_posts,
                    'num_wordpress_posts': num_wordpress_posts,
                    'num_twitter_posts': num_twitter_posts,
                    'num_pinterest_posts': num_pinterest_posts,
                    'num_instagram_posts': num_instagram_posts,
                    'feed_items': [i for i in user_posts]
                }, context_instance=RequestContext(request))
            })

    def delete_user(self, request, user=0):
        """
        :param request: an ``HttpRequest`` instance.
        :param user: the id of a :class:`debra.models.UserProfile` instance
        :return: ``HttpResponse`` instance

        this admin method deletes a :class:`django.auth.contrib.models.User` and their associated :class:`debra.models.UserProfile`
        """
        user_prof = UserProfile.objects.get(id=user)
        user = user_prof

        user_prof.delete()
        user.delete()

        return HttpResponse(status=200)

    def intercom_messages(self, request, user=0):
        """
        :param request: an ``HttpRequest`` instance
        :param user: the id of a :class:`debra.models.UserProfile` instance
        :return: ``HttpResponse`` containing ``json`` dumps of the messages sent to the given ``user``

        get all messages sent over *Intercom* to the given :class:`debra.models.UserProfile`.
        """
        user_prof = UserProfile.objects.get(id=user)
        return HttpResponse(status=200, content=json.dumps([]))

    def signin_as_user(self, request, user=0):
        '''
        :param request: an ``HttpRequest`` instance
        :param user: the id of a :class:`debra.models.UserProfile` instance
        :return: ``redirect`` to the *inspiration* page

        This admin method allows you to login as any :class:`django.auth.contrib.models.User` you want to.
        '''
        user_prof = UserProfile.objects.get(id=user)
        user = user_prof.user
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)

        return redirect(reverse('debra.explore_views.inspiration'))
    #####-----</ User Admin Actions >-----#####

    #####-----< Influencer Admin Actions >-----#####
    ##--< Influencer Admin Helpers >--##
    def create_social_platforms(self, influencer, platforms):
        """
        :param influencer: the :class:`debra.models.Influencer` instance whose platform(s) are being added / modified
        :param platforms: a list of ``dict``'s containing platform names as keys and urls as values
        :return: the :class:`debra.models.Influencer` instance whose platform(s) were modified / added
        """
        for plat in platforms:
            for name, url in plat.items():
                if url:
                    platform_name_titled = name.title()
                    # this next method will remove duplicates for the platform_url (or those that match this url somewhat)
                    # and return one of them. We then ensure that the url saved is what is provided.
                    # if no duplicates exist, it will create a new one
                    platform = influencer.create_platform(url, platform_name_titled)
                    platform.handle_duplicates()
                    platform.url = url
                    platform.save()

        return influencer
    ##--</ Influencer Admin Helpers >--##


    def modify_influencers(self, request, influencer=0):
        """
        :param request: ``HttpRequest`` instance
        :param influencer: the id of a :class:`debra.models.Influencer` instance to modify
        :return: ``HttpResponse`` instance

        This admin method behaves very much like :meth:`debra.admin.ModifyItemsAdminSite.modify_users` for ``GET`` requests.
        For ``POST`` requests, the method populates a :class:`debra.forms.ModifyInfluencerForm` form with ``POST`` data
        and the :class:`debra.models.Influencer` with the id given in the url. We then get all platform's modified on
        the front-end and, for each, we create (or update) that platform for the ``influencer``.
        """
        if request.method == 'POST':
            influencer = Influencer.objects.get(id=influencer)
            form = ModifyInfluencerForm(instance=influencer, data=request.POST)
            if form.is_valid():
                influencer = form.save()
                for platform_name in [key for key in form.cleaned_data.keys() if key.title() in Platform.SOCIAL_PLATFORMS]:
                    platform_url = form.cleaned_data.get(platform_name, None)
                    if platform_url:
                        platform_name_titled = platform_name.title()
                        # this next method will remove duplicates for the platform_url (or those that match this url somewhat)
                        # and return one of them. We then ensure that the url saved is what is provided.
                        # if no duplicates exist, it will create a new one
                        platform = influencer.create_platform(platform_url, platform_name_titled)
                        platform.handle_duplicates()
                        platform.url = platform_url
                        platform.save()

                # handle the blog name / blog url form fields
                blog_platform = influencer.blog_platform
                blog_name, blog_url = form.cleaned_data.get('blog_name'), form.cleaned_data.get('blog_url')
                if blog_name:
                    blog_platform.blogname = blog_name
                if blog_url:
                    blog_platform.url = blog_url
                blog_platform.save()

                #handle the widgets access and trendsetter form fields
                if influencer.shelf_user:
                    user_prof = influencer.shelf_user.userprofile
                    widget_access, trendsetter = form.cleaned_data.get('widget_access'), form.cleaned_data.get('trendsetter')

                    user_prof.privilege_level = user_prof.WIDGETS_PRIVILEGES if widget_access else user_prof.DEFAULT_PRIVILEGES
                    user_prof.is_trendsetter = True if trendsetter else False
                    user_prof.save()

                return HttpResponse(status=200)
        else:
            influencers = Influencer.objects.filter(source='spreadsheet_import').select_related('shelf_user__userprofile').filter(remove_tag=False, accuracy_validated=False)
            influencer_tuples = Influencer.influencers_for_search(qs=influencers)

            expanded_tuples = [tup + (ModifyInfluencerForm(instance=tup[0]),)
                               for tup in influencer_tuples]

            if request.is_ajax():
                return render(request, 'pages/admin/influencers.html', {
                    'influencers': expanded_tuples
                })
            else:
                return render(request, 'pages/admin/feed_container.html', {
                    'admin_page': 'influencers',
                    'container': 'influencers_container',
                    'one_column': True,
                    'feed_items': render_to_string('pages/admin/influencers.html', {
                        'influencers': expanded_tuples
                    }, context_instance=RequestContext(request))
                })

    def import_influencers(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance

        This admin method is used to perform a batch import of :class:`debra.models.Influencer`'s. This method depends
        on the ``POST`` data of the request containing a ``json`` object having keys that correspond to the fields of
        :class:`debra.forms.InfluencerImportForm`.
        """
        if request.method == "POST":
            json_dict = json.loads(request.POST.get('blogger'))
            form = InfluencerImportForm(data=json_dict)
            if form.is_valid():
                email = form.cleaned_data.get('email', None)
                name = form.cleaned_data.get('name', None)

                #if email was provided, first check if there is already an influencer in our system with that email, if so use them
                if email:
                    inf, created = Influencer.objects.get_or_create(email=email)
                    if created:
                        inf.date_created = datetime.datetime.now()
                    form.instance = inf
                inf = form.save(commit=False)
                inf.name = name
                inf.save()

                #get the influencers blog platform name and blog url
                blog_platform, blog_url = form.cleaned_data.get('blog_platform'), form.cleaned_data.get('blog_url')

                ##now create the platforms for the influencer (or just modify them if they exist)
                inf_platforms = [{key:form.cleaned_data.get(key)}
                                 for key in form.cleaned_data.keys() if key.title() in Platform.SOCIAL_PLATFORMS]
                # handle the 'extra' fields
                inf_platforms.append({'instagram': form.cleaned_data.get('extra_instagram', None)})
                inf_platforms.append({'twitter': form.cleaned_data.get('twitter', None)})
                inf_platforms.append({'bloglovin': form.cleaned_data.get('bloglovin', None)})
                inf_platforms.append({blog_platform: blog_url})
                inf = self.create_social_platforms(inf, inf_platforms)

                # save the extra information provided about the influencers blog
                inf_blog = inf.blog_platform
                inf_blog.blogname = form.cleaned_data.get('blog_name')
                inf_blog.about = form.cleaned_data.get('blog_aboutme', None)
                inf_blog.save()

                return HttpResponse(status=200)
        else:
            return render(request, 'pages/admin/import_influencers.html', {
                'form': InfluencerImportForm()
            })

    def delete_influencer_platform(self, request, influencer=0, platform=0):
        """
        :param request: ``HttpRequest`` instance
        :param influencer: ``int`` representing the id of a :class:`debra.models.Influencer` instance
        :param platform: ``int`` representing the id of a :class:`debra.models.Platform` instance
        :return: ``HttpResponse`` instance
        """
        plat = Platform.objects.get(id=platform)
        plat.delete()
        return HttpResponse(status=200)
    #####-----</ Influencer Admin Actions >-----#####

    #####-----< Posts Admin Actions >-----#####
    def modify_posts(self, request):
        """
        :param request: ``HttpRequest`` instance.
        :return: ``HttpResponse`` instance.

        This admin method is for viewing and modifying :class:`debra.models.Posts` instances.
        """
        yesterday = h.yesterday()
        yester_yesterday = datetime.datetime(yesterday.year, yesterday.month, yesterday.day - 1)
        posts = Posts.to_show_on_feed(admin=True).filter(inserted_datetime__gte=yester_yesterday).order_by('-create_date')

        if request.method == 'POST':
            # if mark_rest is given, it means that we want to mark the rest of the posts in the queue as categorized,
            # but not show them on the feed
            if request.POST.get('mark_rest'):
                for post in posts:
                    post.admin_categorized = True
                    post.save()

                return HttpResponse(status=200)
            else:
                json_posts = request.POST.get('items')
                posts_dict = json.loads(json_posts)
                categorized_post_instances = posts.filter(id__in=posts_dict.keys())
                for post in categorized_post_instances:
                    show = posts_dict[str(post.id)].get('show', None)
                    post.admin_categorized = True
                    post.show_on_feed = True if show else False
                    post.save()

                return HttpResponse(status=200)
        else:
            if request.is_ajax():
                filter_type = request.GET.get('filter', None)
                if filter_type:
                    if filter_type == 'blog_posts_only':
                        posts = posts.filter(platform__platform_name__in=Platform.BLOG_PLATFORMS)
                    else:
                        posts = posts.filter(platform__platform_name='Instagram')
                return render(request, 'pages/admin/posts.html', {
                    'posts': posts[:50]
                })

            return render(request, 'pages/admin/feed_container.html', {
                'filter': 'pages/admin/filters/posts.html',
                'container': 'posts_container',
                'admin_page': 'posts',
                'bottom_button': True,
                'total_num_items': posts.count(),
                'feed_items': render_to_string('pages/admin/posts.html', {
                    'posts': posts[:50]
                }, context_instance=RequestContext(request))
            })
    #####-----</ Posts Admin Actions >-----#####

    #####-----< Product Admin Actions >-----#####
    def modify_products(self, request):
        """
        :param request: ``HttpRequest`` instance.
        :return: ``HttpResponse`` instance.

        This admin method is for viewing and modifying :class:`debra.models.ProductModelShelfMap` instances.
        """
        yesterday = h.yesterday()
        products = ProductModelShelfMap.objects.filter(shelf__brand__isnull=True,
                                                       user_prof__is_trendsetter=True,
                                                       admin_categorized=False,
                                                       imported_from_blog=True,
                                                       added_datetime__gte=yesterday).select_related('product_model').order_by('-added_datetime')

        if request.method == 'POST':
            # the json object 'products' has the structure:
            # {
            #  'items': {
            #    ':id': {
            #      'error': string or not included
            #      'ugly': 1 or not included
            #    }
            #    ...
            #  }
            #}
            json_products = request.POST.get('items')
            products_dict = json.loads(json_products)
            categorized_product_instances = products.filter(id__in=products_dict.keys())
            for product in categorized_product_instances:
                error = products_dict[str(product.id)].get('error', None)
                ugly = products_dict[str(product.id)].get('ugly', None)

                product.admin_categorized = True
                if error:
                    # if there is a problem with the item, mark the error on the product model and delete the pmsm instance
                    product_model = product.product_model
                    product_model.problems = error
                    product_model.save()
                else:
                    product.show_on_feed = not ugly

                product.delete() if error else product.save()

            return HttpResponse(status=200)
        else:
            return render(request, 'pages/admin/feed_container.html', {
                'filter': 'pages/admin/filters/products.html',
                'container': 'products_container',
                'admin_page': 'products',
                'bottom_button': True,
                'total_num_items': products.count(),
                'feed_items': render_to_string('pages/admin/products.html', {
                    'products': products[:50]
                }, context_instance=RequestContext(request))
            })

    def product_details(self, request, product=0):
        """
        :param request: ``HttpRequest`` instance
        :param product: ``int`` representing the :class:`debra.models.ProductModelShelfMap` instance to get detailed data for
        :return: ``HttpResponse`` instance.
        """
        if request.is_ajax():
            return render(request, 'pages/admin/product_details.html', {
                'feed_items': [i for i in range(0,100)]
            })
        else:
            return render(request, 'pages/admin/feed_container.html', {
                'container': 'product_details_container',
                'feed_items': render_to_string('pages/admin/product_details.html', {
                    'feed_items': [i for i in range(0,100)]
                }, context_instance=RequestContext(request))
            })
    #####-----</ Item Admin Actions >-----#####

    #####-----< Brand Admin Actions >-----#####
    def modify_brands(self, request, brand=0):
        """
        :param request: ``HttpRequest`` instance
        :param brand: ``int`` representing the :class:`debra.models.Brand` instance to modify
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            brand = Brands.objects.get(id=brand)
            form = ModifyBrandForm(instance=brand, data=request.POST)
            if form.is_valid():
                form.save()
                return HttpResponse(status=200)
        else:
            brands = Brands.objects.filter(userprofile__isnull=False).select_related('userprofile').order_by('-userprofile__num_followers')
            if request.is_ajax():
                return render(request, 'pages/admin/brands.html', {
                    'brands': brands
                })
            else:
                return render(request, 'pages/admin/feed_container.html', {
                    'container': 'brands_container',
                    'feed_type': 'brand',
                    'admin_page': 'brands',
                    'one_column': True,
                    'feed_items': render_to_string('pages/admin/brands.html', {
                        'brands': brands
                    }, context_instance=RequestContext(request))
                })

    def brand_details(self, request, brand=0):
        """
        :param request: ``HttpRequest`` instance
        :param brand: ``int`` representing the :class:`debra.models.Brand` instance to get detailed info for

        Not currently used.
        """
        return render(request, 'pages/admin/brand_details.html', {}, context_instance=RequestContext(request))


    def brands_list_auto_non_blacklisted(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            brand = get_object_or_404(Brands, id=row_id)
            brand.date_edited = datetime.datetime.now()
            brand.save()
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value =request.POST.get('value')
            brand = get_object_or_404(Brands, id=row_id)
            brand.date_edited = datetime.datetime.now()
            brand.save()
            if name == 'similar_brands' or name == 'categories':
                if not value:
                    value = []
                else:
                    value = value.split(',')
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            serializer = serializers.BrandsSerializer(brand, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                if 'description' in data:
                    try:
                        brand.userprofile.aboutme = data["description"]
                        brand.userprofile.save()
                    except UserProfile.DoesNotExist:
                        pass
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Brands.objects.prefetch_related('similar_brands', 'categories', 'userprofile',
                                                        'productmodel_set').filter(supported=False,
                                                                                   date_edited__isnull=True).exclude(domain_name__contains='blogspot.').exclude(domain_name__contains='photobucket.com')
                query1 = query.filter(blacklisted__isnull=True)
                query2 = query.filter(blacklisted=False)
                query = query1 | query2

                data = admin_helpers.get_objects(request, query, serializers.BrandsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                #@todo guess columns definition from serializer
                return render(request, 'pages/admin/brands_list.html', {
                    'reasons': Brands.BLACKLIST_REASONS,
                    'types': Brands.BRAND_TYPES
                }, context_instance=RequestContext(request))

    def brands_list_auto_blacklisted(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            brand = get_object_or_404(Brands, id=row_id)
            brand.date_edited = datetime.datetime.now()
            brand.save()
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value =request.POST.get('value')
            brand = get_object_or_404(Brands, id=row_id)
            brand.date_edited = datetime.datetime.now()
            brand.save()
            if name == 'similar_brands' or name == 'categories':
                if not value:
                    value = []
                else:
                    value = value.split(',')
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            serializer = serializers.BrandsSerializer(brand, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                if 'description' in data:
                    try:
                        brand.userprofile.aboutme = data["description"]
                        brand.userprofile.save()
                    except UserProfile.DoesNotExist:
                        pass
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Brands.objects.prefetch_related('similar_brands', 'categories', 'userprofile',
                                                        'productmodel_set').filter(supported=False,
                                                                                   date_edited__isnull=True).exclude(domain_name__contains='blogspot.').exclude(domain_name__contains='photobucket.com')
                query = query.filter(blacklisted=True)
                data = admin_helpers.get_objects(request, query, serializers.BrandsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                #@todo guess columns definition from serializer
                return render(request, 'pages/admin/brands_list.html', {
                    'reasons': Brands.BLACKLIST_REASONS,
                    'types': Brands.BRAND_TYPES
                }, context_instance=RequestContext(request))

    def brand_flags(self, request):
        query = Brands.objects.prefetch_related('related_user_profiles', 'related_user_profiles__user_profile', 'related_user_profiles__user_profile__user')
        query = query.filter(related_user_profiles__isnull=False)
        query = query.distinct()
        options = {
            "request": request,
            "load_serializer": serializers.BrandFlagsTableSerializer,
            "store_serializer": serializers.BrandFlagsTableSerializer,
            "context": {
                # pass list of names of the stripe plans
                'stripe_plans': sorted([(plan, plan) for plan in PLAN_INFO.keys()]),
            },
            "template": 'pages/admin/brand_flags_table.html',
            "query": query,
            "model": Brands,
            "skip_influencers_validate": True,
            #"debug": True
        }
        return table_page(options)

    def post_analytics_collection_monitoring(self, request):
        query = PostAnalyticsCollection.objects.prefetch_related(
            'creator_brand',
            'user'
        )
        options = {
            "request": request,
            "load_serializer": serializers.AdminPostAnalyticsCollectionSerializer,
            "store_serializer": serializers.AdminPostAnalyticsCollectionSerializer,
            "context": {
            },
            "template": 'pages/admin/post_analytics_collection_monitoring_table.html',
            "query": query,
            "model": PostAnalyticsCollection,
            "skip_influencers_validate": True,
        }
        return table_page(options)

    def report_monitoring(self, request):
        query = ROIPredictionReport.objects.prefetch_related(
            'creator_brand',
            'user'
        )
        options = {
            "request": request,
            "load_serializer": serializers.AdminReportSerializer,
            "store_serializer": serializers.AdminReportSerializer,
            "context": {
            },
            "template": 'pages/admin/report_monitoring_table.html',
            "query": query,
            "model": ROIPredictionReport,
            "skip_influencers_validate": True,
        }
        return table_page(options)

    def tag_monitoring(self, request):
        query = InfluencersGroup.objects.prefetch_related(
            'creator_brand',
            'creator_userprofile__user',
        )
        options = {
            "request": request,
            "load_serializer": serializers.AdminTagSerializer,
            "store_serializer": serializers.AdminTagSerializer,
            "context": {
            },
            "template": 'pages/admin/tag_monitoring_table.html',
            "query": query,
            "model": InfluencersGroup,
            "skip_influencers_validate": True,
        }
        return table_page(options)

    def brand_signup(self, request):
        return render(request, 'pages/admin/brand_signup.html', {
            'brand_signup_popup_auto_open': True,
            'from_admin': True
        }, context_instance=RequestContext(request))

    def brands_list_edited_non_blacklisted(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            brand = get_object_or_404(Brands, id=row_id)
            brand.date_edited = datetime.datetime.now()
            brand.save()
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value =request.POST.get('value')
            brand = get_object_or_404(Brands, id=row_id)
            brand.date_edited = datetime.datetime.now()
            brand.save()
            if name == 'similar_brands' or name == 'categories':
                if not value:
                    value = []
                else:
                    value = value.split(',')
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            serializer = serializers.BrandsSerializer(brand, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                if 'description' in data:
                    try:
                        brand.userprofile.aboutme = data["description"]
                        brand.userprofile.save()
                    except UserProfile.DoesNotExist:
                        pass
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Brands.objects.prefetch_related('similar_brands', 'categories', 'userprofile',
                                                        'productmodel_set').filter(supported=False,
                                                                                   date_edited__isnull=False).exclude(domain_name__contains='blogspot.').exclude(domain_name__contains='photobucket.com')
                query = query.filter(blacklisted=False)
                data = admin_helpers.get_objects(request, query, serializers.BrandsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                #@todo guess columns definition from serializer
                return render(request, 'pages/admin/brands_list.html', {
                    'reasons': Brands.BLACKLIST_REASONS,
                    'types': Brands.BRAND_TYPES
                }, context_instance=RequestContext(request))

    def brands_list_edited_blacklisted(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            brand = get_object_or_404(Brands, id=row_id)
            brand.date_edited = datetime.datetime.now()
            brand.save()
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value =request.POST.get('value')
            brand = get_object_or_404(Brands, id=row_id)
            brand.date_edited = datetime.datetime.now()
            brand.save()
            if name == 'similar_brands' or name == 'categories':
                if not value:
                    value = []
                else:
                    value = value.split(',')
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            serializer = serializers.BrandsSerializer(brand, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                if 'description' in data:
                    try:
                        brand.userprofile.aboutme = data["description"]
                        brand.userprofile.save()
                    except UserProfile.DoesNotExist:
                        pass
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Brands.objects.prefetch_related('similar_brands', 'categories', 'userprofile',
                                                        'productmodel_set').filter(supported=False,
                                                                                   date_edited__isnull=False).exclude(domain_name__contains='blogspot.').exclude(domain_name__contains='photobucket.com')
                query = query.filter(blacklisted=True)
                data = admin_helpers.get_objects(request, query, serializers.BrandsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                #@todo guess columns definition from serializer
                return render(request, 'pages/admin/brands_list.html', {
                    'reasons': Brands.BLACKLIST_REASONS,
                    'types': Brands.BRAND_TYPES
                }, context_instance=RequestContext(request))





    def influencers(self, request):
        return render(request, 'pages/admin/influencers_select.html', {
            'InfluencerCheck': InfluencerCheck
        }, context_instance=RequestContext(request))

    def influencers_list_nonvalidated(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()

            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_LIST)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if not influencer.blacklisted:
                print "issuing celery task now to fetch posts and start evaluating the influencer %s " % influencer
                celery_issue_task_fetch_posts([influencer])
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()

            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerListSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                #query = Influencer.objects.filter(source__isnull=False, blog_url__isnull=False, date_validated__isnull=True, classification__isnull=False).exclude(show_on_search=True)
                query = Influencer.objects.filter(source='comments_import', classification__isnull=False, blacklisted=False)
                query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
                query = query.filter(platformdataop__operation='content_classification')
                query = query.filter(platform__platformdataop__operation='fetch_blogname')
                query = query.filter(platform__platformdataop__operation='extract_emails_from_platform').distinct()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerListSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_list.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_list_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))

    def influencers_list_validated(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerListSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                query = Influencer.objects.filter(source__isnull=False, blog_url__isnull=False, classification__isnull=False).exclude(show_on_search=True)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerListSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_list.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_list_validated'),
                    'validated': True,
                }, context_instance=RequestContext(request))

    def influencers_admin(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerAdminSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:

            if request.is_ajax():
                query = Influencer.raw_influencers_for_search()
                query = query.prefetch_related('platform_set', 'edit_history')
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerAdminSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_list_admin.html', {}, context_instance=RequestContext(request))

    def influencers_list_debug(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerListDebugSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:

            if request.is_ajax():
                query = Influencer.objects.all()
                query = query.filter(edit_history__field__in=serializers.AdminInfluencerListDebugSerializer.Meta.fields)
                query = query.prefetch_related('platform_set', 'edit_history')
                query = query.distinct()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerListDebugSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_list_debug.html', {}, context_instance=RequestContext(request))

    def influencers_list_summary(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        date = datetime.date.today()
        reports = []
        for x in xrange(11):
            yesterday = date - timedelta(days=1)
            total_infs = Influencer.objects.filter(date_validated__contains=date).exclude(show_on_search=True)
            edited = Influencer.objects.filter(edit_history__timestamp__contains=date, edit_history__field__in=serializers.AdminInfluencerListDebugSerializer.Meta.fields).exclude(show_on_search=True).distinct('id')
            report = {
                'date': date,
                #'total_urls': PlatformDataOp.objects.filter(started__gte=yesterday, started__lte=date, operation='create_platforms_from_description').count(),
                'total_urls': total_infs.count(),
                'edited': edited.count(),
                'blacklisted': edited.filter(blacklisted=True).count(),
                'reason_dead': edited.filter(blacklisted=True, is_live=False).count(),
                'reason_noturl': edited.filter(blacklisted=True, problem=1).count(),
                'reason_squat': edited.filter(blacklisted=True, problem=2).count(),
                'reason_store': edited.filter(blacklisted=True, problem=3).count(),
                'reason_notblog': edited.filter(problem=4).count(),
            }
            reports.append(report)
            date = yesterday
        return render(request, 'pages/admin/influencers_list_summary.html', {'reports': reports}, context_instance=RequestContext(request))

    def influencers_fashion_nonvalidated(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            if request.GET.get('recheck') == '1':
                influencer.date_edited = datetime.datetime.now()
                InfluencerEditHistory.commit_change(influencer, 'recheck', True)
                influencer.save()
            else:
                influencer.date_validated = datetime.datetime.now()
                try:
                    validated_on = json.loads(influencer.validated_on)
                except (ValueError, TypeError):
                    validated_on = []
                validated_on.append(ADMIN_TABLE_INFLUENCER_FASHION)
                validated_on = list(set(validated_on))
                influencer.validated_on = json.dumps(validated_on)
                if influencer.qa:
                    influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
                else:
                    influencer.qa = request.visitor["auth_user"].username
                influencer.save()
                if InfluencerEditHistory.objects.exclude(influencer=influencer, field='recheck').exists():
                    celery_issue_task_extract_social_handles([influencer])
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerFashionSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                # interesting influencers: have a blog, source is non-null, date_validated is null, and don't show up on search

                query = Influencer.objects.filter(source='comments_import', blog_url__isnull=False, date_validated__isnull=False, blacklisted=False, classification__isnull=False).exclude(show_on_search=True)
                query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
                query = query.filter(platformdataop__operation='estimate_if_fashion_blogger',
                                     platformdataop__error_msg__isnull=True,
                                     platformdataop__finished__isnull=False).distinct()
                # need to run influencer.calc_is_active() to check if the influencer is active
                for q in query.filter(posts_count=0):
                    q.is_active = q.calc_is_active()
                    q.posts_count = q.calc_posts_count()
                    q.save()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerFashionSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_fashion.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_fashion_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))

    def influencers_fashion_validated(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """

        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerFashionSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                query = Influencer.objects.filter(source='comments_import', blog_url__isnull=False, date_validated__isnull=False,
                                                  blacklisted=False, classification__isnull=False, relevant_to_fashion__isnull=False).exclude(show_on_search=True)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION)
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerFashionSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_fashion.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_fashion_validated'),
                    'validated': True,
                }, context_instance=RequestContext(request))

    def influencers_fashion_debug(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerFashionDebugSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:

            if request.is_ajax():
                query = Influencer.objects.filter(source__isnull='comments_import', blog_url__isnull=False, date_validated__isnull=False, blacklisted=False, classification__isnull=False).exclude(show_on_search=True)
                #query = query.filter(date_validated__isnull=True, date_edited__isnull=False)
                query = query.filter(edit_history__field__in=serializers.AdminInfluencerFashionDebugSerializer.Meta.fields)
                query = query.prefetch_related('platform_set', 'edit_history')
                query = query.distinct()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerFashionDebugSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_fashion_debug.html', {}, context_instance=RequestContext(request))


    def influencers_fashion_summary(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        date = datetime.datetime.now()
        reports = []
        for x in xrange(11):
            yesterday = date - timedelta(days=1)
            edits = Influencer.objects.filter(edit_history__timestamp__contains=date.today(), edit_history__field__in=serializers.AdminInfluencerFashionSerializer.Meta.fields)
            edits = edits.distinct('id')
            not_active = 0
            wo_fashion_links = 0
            wo_fashion_store_mentions = 0
            wo_fashion_widgets = 0
            wo_images = 0
            wo_comments = 0
            urls_not_active = []
            urls_wo_fashion_links = []
            urls_wo_fashion_store_mentions = []
            urls_wo_fashion_widgets = []
            urls_wo_images = []
            urls_wo_comments = []

            serialized = serializers.AdminInfluencerFashionSerializer(edits, many=True).data
            for item in serialized:
                if not item["is_active"]:
                    urls_not_active.append(item["blog_url"])
                    not_active+=1
                if not item["fashion_links"]:
                    urls_wo_fashion_links.append(item["blog_url"])
                    wo_fashion_links+=1
                if not item["fashion_store_mentions"]:
                    urls_wo_fashion_store_mentions.append(item["blog_url"])
                    wo_fashion_store_mentions+=1
                if not item["fashion_widgets"]:
                    urls_wo_fashion_widgets.append(item["blog_url"])
                    wo_fashion_widgets+=1
                if not item["images"]:
                    urls_wo_images.append(item["blog_url"])
                    wo_images+=1
                if not item["comments"]:
                    urls_wo_comments.append(item["blog_url"])
                    wo_comments+=1
            report = {
                'date': date,
                'total_urls': Influencer.objects.filter(date_validated__gte=yesterday, date_validated__lte=date).count(),
                'edited': edits.count(),
                'not_active': not_active,
                'wo_fashion_links': wo_fashion_links,
                'wo_fashion_store_mentions': wo_fashion_store_mentions,
                'wo_fashion_widgets': wo_fashion_widgets,
                'wo_images': wo_images,
                'wo_comments': wo_comments,
                'approved': '?',
                'urls_not_active': urls_not_active,
                'urls_wo_fashion_links': urls_wo_fashion_links,
                'urls_wo_fashion_store_mentions': urls_wo_fashion_store_mentions,
                'urls_wo_fashion_widgets': urls_wo_fashion_widgets,
                'urls_wo_images': urls_wo_images,
                'urls_wo_comments': urls_wo_comments,
            }
            reports.append(report)
            date = yesterday
        return render(request, 'pages/admin/influencers_fashion_summary.html', {'reports': reports}, context_instance=RequestContext(request))

    def influencers_social_handles_nonvalidated(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_SOCIAL_HANDLE)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            # when the influencer row is clicked 'save', we need to make sure to call the
            # handle social update for all existing values
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = Influencer.objects.active().filter(source__isnull=False, blog_url__isnull=False, classification='blog',
                                                      relevant_to_fashion=True).exclude(show_on_search=True)
                    query = query.filter(platform__platformdataop__operation='extract_platforms_from_platform',
                                         platform__platformdataop__error_msg__isnull=True,
                                         platform__platformdataop__finished__isnull=False).distinct()
                query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SOCIAL_HANDLE)
                #query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION)
                #query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
                # make sure to only show those users that have their social handles analyzed
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_social_handle.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_social_handles_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))

    def influencers_social_handles_validated(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = Influencer.objects.active().filter(source__isnull=False, blog_url__isnull=False, date_validated__isnull=False,
                                                      relevant_to_fashion=True).exclude(show_on_search=True)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_SOCIAL_HANDLE)

                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_social_handle.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_social_handles_validated'),
                    'validated': True,
                }, context_instance=RequestContext(request))

    def influencers_social_handles_debug(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsDebugSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:

            if request.is_ajax():
                query = Influencer.objects.active().filter(source__isnull=False, blog_url__isnull=False, date_validated__isnull=False,
                                                  relevant_to_fashion=True).exclude(show_on_search=True)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_SOCIAL_HANDLE)
                query = query.filter(edit_history__field__in=serializers.AdminInfluencerInformationsDebugSerializer.Meta.fields)
                query = query.prefetch_related('platform_set', 'edit_history')
                query = query.distinct()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsDebugSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_social_handle.html', {}, context_instance=RequestContext(request))

    def influencers_social_handles_summary(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        date = datetime.datetime.now()
        reports = []
        for x in xrange(11):
            yesterday = date - timedelta(days=1)
            edits = Influencer.objects.filter(edit_history__timestamp__gte=yesterday, edit_history__timestamp__lte=date, edit_history__field__in=serializers.AdminInfluencerInformationsDebugSerializer.Meta.fields)
            edits = edits.distinct('id')
            edit_ops = InfluencerEditHistory.objects.filter(timestamp__gte=yesterday, timestamp__lte=date, field__in=serializers.AdminInfluencerInformationsDebugSerializer.Meta.fields)
            edit_ops = edit_ops.distinct('influencer')
            validated_total = Influencer.objects.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
            validated_total = validated_total.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION)
            validated_total = validated_total.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            report = {
                'date': date,
                'total_urls': Influencer.objects.filter(date_validated__gte=yesterday, date_validated__lte=date).count(),
                'edited': edits.count(),
                'edits_email': edit_ops.filter(field='email').count(),
                'edits_profile_pic': edit_ops.filter(field='profile_pic_url').count(),
                'edits_blogname': edit_ops.filter(field='blogname').count(),
                'edits_name': edit_ops.filter(field='name').count(),
                'edits_meta_desc': edit_ops.filter(field='description').count(),
                'edits_about_url': edit_ops.filter(field='about_url').count(),
                'edits_demographics_location': edit_ops.filter(field='demographics_location').count(),
                'edits_fb_url': edit_ops.filter(field='fb_url').count(),
                'edits_tw_url': edit_ops.filter(field='tw_url').count(),
                'edits_pin_url': edit_ops.filter(field='pin_url').count(),
                'edits_insta_url': edit_ops.filter(field='insta_url').count(),
                'edits_bloglovin_url': edit_ops.filter(field='bloglovin_url').count(),
                'edits_lb_url': edit_ops.filter(field='lb_url').count(),
                'edits_pose': edit_ops.filter(field='pose_url').count(),
                'edits_youtube': edit_ops.filter(field='youtube_url').count(),
            }
            validated = {
                'count_total': validated_total.count(),
                'count_email': validated_total.filter(email__isnull=False).exclude(email="").count(),
                'count_blogname': validated_total.filter(blogname__isnull=False).exclude(blogname="").count(),
                'count_pic': validated_total.filter(profile_pic_url__isnull=False).exclude(profile_pic_url="").count(),
                'count_name': validated_total.filter(name__isnull=False).exclude(name="").count(),
                'count_desc': validated_total.filter(description__isnull=False).exclude(description="").count(),
                'count_loc': validated_total.filter(demographics_location__isnull=False).exclude(demographics_location="").count(),
                'count_fb': validated_total.filter(fb_url__isnull=False).exclude(fb_url="").count(),
                'count_tw': validated_total.filter(tw_url__isnull=False).exclude(tw_url="").count(),
                'count_pin': validated_total.filter(pin_url__isnull=False).exclude(pin_url="").count(),
                'count_insta': validated_total.filter(insta_url__isnull=False).exclude(insta_url="").count(),
                'count_bl': validated_total.filter(bloglovin_url__isnull=False).exclude(bloglovin_url="").count(),
                'count_lb': validated_total.filter(lb_url__isnull=False).exclude(lb_url="").count(),
                'count_pose': validated_total.filter(pose_url__isnull=False).exclude(pose_url="").count(),
                'count_yt': validated_total.filter(youtube_url__isnull=False).exclude(youtube_url="").count(),
                'count_email': validated_total.filter(email__isnull=False).exclude(email="").count(),

                'urls_wo_blogname': validated_total.filter(Q(blogname__isnull=True) | Q(blogname="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_pic': validated_total.filter(Q(profile_pic_url__isnull=True) | Q(profile_pic_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_name': validated_total.filter(Q(name__isnull=True) | Q(name="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_desc': validated_total.filter(Q(description__isnull=True) | Q(description="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_loc': validated_total.filter(Q(demographics_location__isnull=True) | Q(demographics_location="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_fb': validated_total.filter(Q(fb_url__isnull=True) | Q(fb_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_tw': validated_total.filter(Q(tw_url__isnull=True) | Q(tw_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_pin': validated_total.filter(Q(pin_url__isnull=True) | Q(pin_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_insta': validated_total.filter(Q(insta_url__isnull=True) | Q(insta_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_bl': validated_total.filter(Q(bloglovin_url__isnull=True) | Q(bloglovin_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_lb': validated_total.filter(Q(lb_url__isnull=True) | Q(lb_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_pose': validated_total.filter(Q(pose_url__isnull=True) | Q(pose_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_yt': validated_total.filter(Q(youtube_url__isnull=True) | Q(youtube_url="")).only('blog_url').values('blog_url', 'id'),

            }
            reports.append(report)
            date = yesterday
        return render(request, 'pages/admin/influencers_informations_summary.html', {'reports': reports, 'validated': validated}, context_instance=RequestContext(request))


    def influencers_informations_nonvalidated(self, request, uuid=None, section=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)

            if section == 'missing_emails':
                if influencer.email_for_advertising_or_collaborations:
                    from debra.brand_helpers import send_missing_emails
                    celery = True
                    if celery:
                        send_missing_emails.apply_async([influencer.id], queue='celery')
                    else:
                        messages_to_send = send_missing_emails(influencer.id, to_send=True)
                return HttpResponse()

            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            if influencer.gplus_url:
                handle_social_handle_updates(influencer, 'gplus_url', influencer.gplus_url)
            if influencer.youtube_url:
                handle_social_handle_updates(influencer, 'youtube_url', influencer.youtube_url)
            # add the influencer to a collection
            ig = InfluencersGroup.objects.get(id=1967)
            ig.add_influencer(influencer)
            # ensure that it's upgraded to show_on_search=True
            influencer.set_show_on_search(value=True, on_production=False)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                elif name == "blacklisted":
                    if int(value) == 1:
                        influencer.set_blacklist_with_reason("by_qa")
                    else:
                        influencer.blacklist_reasons = None
                        influencer.save()
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            validated = section in ['all_blacklisted', 'all_suspicious', 'qaed_by_mommy']
            if request.is_ajax():
                #@todo guess columns definition from serializer

                # def get_query_1():
                #     dd = datetime.date(2016, 6, 12)
                #     coll = InfluencersGroup.objects.get(id=1964)
                #     ids = coll.influencer_ids
                #     coll2 = InfluencersGroup.objects.get(id=1995)
                #     ids2 = coll2.influencer_ids
                #     ids.extend(ids2)
                #     query = Influencer.objects.filter(
                #         id__in=ids
                #     ).exclude(date_validated__gte=dd)#.exclude(blog_url__contains='http://www.theshelf.com/artificial_blog')
                #     query = query.filter(profile_pic_url__isnull=False)
                #     return query

                # def get_query_2():
                #     from debra.admin_helpers import (
                #         influencers_informations_nonvalidated_query,)
                #     return influencers_informations_nonvalidated_query(uuid)

                print 'SECTION:', section
                print 'UUID:', uuid

                builder_options = {}

                if section == 'all_blacklisted':
                    query = Influencer.objects.filter(blacklisted=True,
                        validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
                elif section == 'all_suspicious':
                    query = Influencer.objects.filter(
                        Q(validated_on__contains=ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED) &
                        Q(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS))
                elif section == 'qaed_by_mommy':
                    _mommy_group = Group.objects.get(name='mommy')
                    # _qa_usernames = _mommy_group.user_set.values_list(
                    #     'username', flat=True)
                    _qa_userprofiles = UserProfile.objects.filter(
                        user__in=_mommy_group.user_set.all()).values_list('id',
                        flat=True)
                    query = Influencer.objects.filter(
                        Q(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS) &
                        # Q(qa__in=_qa_usernames) &
                        ~Q(blacklisted=True) &
                        Q(qa_user_profile_id__in=_qa_userprofiles)
                    ).order_by('id')
                elif section == 'missing_emails':
                    mp_data = Influencer.objects.missing_emails_data()
                    _t0 = time.time()
                    query = list(Influencer.objects.filter(id__in=mp_data.keys()))
                    for inf in query:
                        inf.agr_last_sent = mp_data.get(inf.id)
                    print '* query took {}'.format(time.time() - _t0)

                    builder_options.update({
                        'orderby': ['-agr_last_sent'],
                    })
                elif section == 'bad_emails':
                    _t0 = time.time()
                    inf_ids = list(MailProxyMessage.objects.filter(
                        mandrill_id='.',
                        type=MailProxyMessage.TYPE_EMAIL,
                    ).values_list(
                        'thread__influencer', flat=True))
                    print '* getting ids took {}'.format(time.time() - _t0)
                    query = Influencer.objects.filter(id__in=inf_ids)
                else:
                    query = admin_helpers.NonvalidatedBloggersQueryBuilder(
                        user_profile=request.user.userprofile,
                        exclude_validated=False,
                    ).build_query()
                    # base_query = get_query_1()
                    # query = request.user.userprofile.extend_influencers_for_qa(
                    #     base_query)

                data = admin_helpers.get_objects(request, query,
                    serializers.AdminInfluencerInformationsSerializer,
                    options=builder_options
                )
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                    'validated': validated,
                    'section': section,
                }, context_instance=RequestContext(request))

    def influencers_informations_fake(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                elif name == "blacklisted":
                    if int(value) == 1:
                        influencer.set_blacklist_with_reason("by_qa")
                    else:
                        influencer.blacklist_reasons = None
                        influencer.save()
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                qa_group = Group.objects.get(name='QA')
                if request.user in qa_group.user_set.all():
                    query = request.user.userprofile.get_qa_influencers_to_check(uuid)
                    for inf in query:
                        inf.qa_user_profile=request.user.userprofile
                        inf.save()
                else:
                    query = Influencer.objects.filter(blog_url__contains='http://www.theshelf.com/artificial_blog')
                    
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_fake'),
                    'validated': False,
                }, context_instance=RequestContext(request))


    def influencers_informations_newly_upgraded(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                elif name == "blacklisted":
                    if int(value) == 1:
                        influencer.set_blacklist_with_reason("by_qa")
                    else:
                        influencer.blacklist_reasons = None
                        influencer.save()
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = Influencer.objects.filter(show_on_search=True).exclude(old_show_on_search=True)

                query = query.exclude(blacklisted=True)
                query = query.exclude(source__contains='brand')
                dd = datetime.date(2015, 6, 12)
                query = query.filter(date_upgraded_to_show_on_search__gte=dd)
                query = query.filter(date_validated__lte=dd)
                
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))

    def influencers_informations_blogspot_duplicates(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.collaboration_types = None
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = Influencer.objects.filter(show_on_search=True, collaboration_types='duplicate')
                #query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_validated'),
                    'validated': True,
                }, context_instance=RequestContext(request))

    def influencers_informations_male_bloggers(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = Influencer.objects.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(old_show_on_search=True)
                query = query.filter(demographics_gender='m')
                query = query.filter(profile_pic_url__isnull=False)
                query = query.exclude(blacklisted=True)
                query = query.filter(blog_url__contains='blog')
                query = query.has_any_categories()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_validated'),
                    'validated': True,
                }, context_instance=RequestContext(request))


    def influencers_informations_in_collections(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    # find all influencers that are either in a collection for an agency
                    brands = Brands.objects.filter(stripe_plan__isnull=False)
                    coll = InfluencersGroup.objects.filter(owner_brand__in=brands)
                    coll = coll.exclude(name__contains='Blacklisted --')
                    mappings = InfluencerGroupMapping.objects.select_related('influencer').filter(group__in=coll)
                    #mappings_inf_ids = mappings.values_list('influencer__id', flat=True)
                    # now, we want to make sure only those influencers show up that haven't been edited by
                    # the QA since they were added
                    ids = set()
                    for m in mappings:
                        i = m.influencer
                        print("i.date_edited = [%s] m.last_update = [%s]" % (i.date_edited, m.last_update))
                        if not i.date_edited or i.date_edited < m.last_update:
                            ids.add(i.id)

                    mapping_infs = Influencer.objects.filter(id__in=ids)

                    query = mapping_infs.distinct()

                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_in_collections'),
                    'validated': True,
                }, context_instance=RequestContext(request))


    def influencers_informations_bad_email(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():

                # if they were sent an email and
                #       a) no email exists
                #       b) email gave an error (it bounced) or it was a spam
                # mark all of these with problem=5 (represents 'bad_email')
                # once qa finishes these, I can go over, check, and resend the corresponding emails
                mps_spam = MailProxyMessage.objects.filter(type=MailProxyMessage.TYPE_SPAM)
                mps_bounced = MailProxyMessage.objects.filter(type=MailProxyMessage.TYPE_BOUNCE)
                mps = mps_spam | mps_bounced
                mps_infs_ids = mps.values_list('thread__influencer__id', flat=True)

                no_email1 = MailProxyMessage.objects.filter(thread__influencer__email_for_advertising_or_collaborations__isnull=True)
                no_email2 = no_email1.filter(thread__influencer__email_all_other__isnull=True)

                no_email_inf_ids = no_email2.values_list('thread__influencer__id', flat=True)
                all_ids = list(mps_infs_ids) + list(no_email_inf_ids)
                no_email_infs = Influencer.objects.filter(id__in=all_ids)
                query = no_email_infs.distinct()
                # PROBLEMS = (
                #     (1, "unknown"),
                #     (2, "squatter"),
                #     (3, "brand"),
                #     (4, "social"),
                #     (5, "bad_email"),
                #)
                query.update(problem=5)
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_bad_email'),
                    'validated': True,
                }, context_instance=RequestContext(request))

    def influencers_informations_missing_email(self, request):
        from aggregate_if import Count, Max

        q1 = Q(email_all_other__isnull=True) | Q(email_all_other="")
        q2 = (Q(email_for_advertising_or_collaborations__isnull=True) |
            Q(email_for_advertising_or_collaborations=""))
        q3 = Q(mails__isnull=False)

        query = Influencer.objects.filter(q1 & q2 & q3)

        def sliced_queryset_handler(qs):
            fields = (
                'id', 'blog_url', 'email_for_advertising_or_collaborations',
                'email_all_other', 'name', 'blogname', 'email',
                'shelf_user__email',)
            return qs.values(*fields).annotate(
                emails_sent_count=Count(
                    'mails__threads',
                    only=(
                        Q(mails__threads__mandrill_id__regex=r'.(.)+') &
                        Q(mails__threads__type=MailProxyMessage.TYPE_EMAIL) &
                        Q(mails__threads__direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER)
                    )
                ),
                last_send_ts=Max(
                    'mails__threads__ts',
                    only=(
                        Q(mails__threads__mandrill_id__regex=r'.(.)+') &
                        Q(mails__threads__type=MailProxyMessage.TYPE_EMAIL) &
                        Q(mails__threads__direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER)
                    )
                )
            ).filter(
                emails_sent_count__gt=0
            ).order_by(
                '-last_send_ts'
            )

        query = sliced_queryset_handler(query)

        options = {
            "request": request,
            "load_serializer": serializers.AdminInfluencerMissingEmailSerializer,
            "store_serializer": serializers.AdminInfluencerSerializer,
            "context": {
                "sliced_queryset_handler": None
            },
            "template": 'pages/admin/influencers_informations_missing_email.html',
            "query": query,
            "model": Influencer,
            "skip_influencers_validate": True,
            "getter": operator.itemgetter
        }
        return table_page(options)


    def influencers_informations_mandrill_error(self, request):
        from aggregate_if import Count

        query = Influencer.objects.filter(mails__threads__mandrill_id=".")

        options = {
            "request": request,
            "load_serializer": serializers.AdminInfluencerMandrillError,
            "store_serializer": serializers.AdminInfluencerSerializer,
            "context": {
                "sliced_queryset_handler": None
            },
            "template": 'pages/admin/influencers_informations_mandrill_error.html',
            "query": query,
            "model": Influencer,
            "skip_influencers_validate": True,
            "getter": operator.itemgetter
        }
        return table_page(options)


    def influencers_informations_duplicate_social(self, request, platform_name=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        # Here, we first find out all InfluencerCheck entries with cause
        print "Got platform: %s" % platform_name
        cause_str = "CAUSE_SUSPECT_DUPLICATE_SOCIAL_%s" % platform_name
        field_param = Influencer.platform_name_to_field[platform_name]
        print("cause: %s  field=%s" % (cause_str, field_param))
        cause = getattr(InfluencerCheck, cause_str)

        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            ic = InfluencerCheck.objects.filter(influencer=influencer, status=InfluencerCheck.STATUS_NEW, cause=cause)
            ic.update(status=InfluencerCheck.STATUS_FIXED)
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                entries = InfluencerCheck.objects.select_related('influencer').filter(cause=cause, status=InfluencerCheck.STATUS_NEW)
                inf_ids = entries.values_list('influencer__id', flat=True)

                infs = Influencer.objects.filter(id__in=inf_ids)
                data = admin_helpers.get_objects(request, infs, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_duplicate_social', args=[platform_name]),
                    'validated': True,
                }, context_instance=RequestContext(request))


    def influencers_informations_validated(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = Influencer.objects.filter(source__isnull=False, blog_url__isnull=False, blacklisted=False,
                                                      relevant_to_fashion__isnull=False).exclude(show_on_search=True)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
                #query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_validated'),
                    'validated': True,
                }, context_instance=RequestContext(request))


    def influencers_all_categories_validated(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = Influencer.objects.filter(source__isnull=False,
                        blog_url__isnull=False, blacklisted=False).exclude(
                        show_on_search=True)
                query = query.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
                query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_validated'),
                    'validated': True,
                }, context_instance=RequestContext(request))


    def create_influencer_and_blog_platform_bunch(self, request):
        """
        This method is used to create new influencers from manually entering urls in the admin panel.

        We set the source as well as blogger_type here.
        """
        if request.method == 'POST':
            form = PlatformUrlsForm(request.POST)
            if form.is_valid():
                links = form.cleaned_data["links"]
                source = form.cleaned_data["source"]
                category = form.cleaned_data["category"]
                h.create_influencer_and_blog_platform_bunch.apply_async([links, source, category], queue="celery")

        form = PlatformUrlsForm()

        return render(request, 'pages/admin/create_influencer_and_blog_platform_bunch.html', {'form': form}, context_instance=RequestContext(request))

    ############################ special case tables

    def influencers_informations_nonvalidated_automated(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                print "WE ARE HERE ----------------------\n\n\n"
                #@todo guess columns definition from serializer
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = Influencer.objects.filter(show_on_search=True)
                query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))

    def influencers_informations_validated_automated(self, request, uuid=None):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        # @specialcase only for qa, validated ONLY in informations table
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                #query = Influencer.raw_influencers_for_search()
                if uuid:
                    query = Influencer.objects.filter(validation_queue__uuid=uuid, validation_queue__state=1).distinct()
                else:
                    query = query = Influencer.raw_influencers_for_search()
                query = query.filter(validated_on='["%s"]' % ADMIN_TABLE_INFLUENCER_INFORMATIONS)
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_validated'),
                    'validated': True,
                }, context_instance=RequestContext(request))

    def influencers_informations_validated_error(self, request, urltype=None):
        print "urltype %s " % urltype
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                # these are the problematic ones
                # for each social handle we check if there is a platform (url_not_found is False) but *url field is null
                query = Influencer.objects.filter(show_on_search=True, validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
                fb_null = query.filter(fb_url__isnull=True)
                pin_null = query.filter(pin_url__isnull=True)
                tw_null = query.filter(tw_url__isnull=True)
                insta_null = query.filter(insta_url__isnull=True)
                if urltype:

                    if "facebook" in urltype.lower():
                        plats = Platform.objects.filter(influencer__in=fb_null, platform_name='Facebook').exclude(url_not_found=True)
                        query = Influencer.objects.filter(platform__in=plats).distinct()
                    if "pinterest" in urltype.lower():
                        plats = Platform.objects.filter(influencer__in=pin_null, platform_name='Pinterest').exclude(url_not_found=True)
                        query = Influencer.objects.filter(platform__in=plats).distinct()
                    if "twitter" in urltype.lower():
                        plats = Platform.objects.filter(influencer__in=tw_null, platform_name='Twitter').exclude(url_not_found=True)
                        query = Influencer.objects.filter(platform__in=plats).distinct()
                    if "instagram" in urltype.lower():
                        plats = Platform.objects.filter(influencer__in=insta_null, platform_name='Instagram').exclude(url_not_found=True)
                        query = Influencer.objects.filter(platform__in=plats).distinct()
                else:
                    plats = Platform.objects.filter(influencer__in=fb_null, platform_name='Facebook').exclude(url_not_found=True)
                    problematic_fb_infs = Influencer.objects.filter(platform__in=plats).distinct()

                    plats = Platform.objects.filter(influencer__in=pin_null, platform_name='Pinterest').exclude(url_not_found=True)
                    problematic_pin_infs = Influencer.objects.filter(platform__in=plats).distinct()

                    plats = Platform.objects.filter(influencer__in=tw_null, platform_name='Twitter').exclude(url_not_found=True)
                    problematic_tw_infs = Influencer.objects.filter(platform__in=plats).distinct()

                    plats = Platform.objects.filter(influencer__in=insta_null, platform_name='Instagram').exclude(url_not_found=True)
                    problematic_insta_infs = Influencer.objects.filter(platform__in=plats).distinct()

                    query = problematic_fb_infs | problematic_pin_infs | problematic_tw_infs | problematic_insta_infs

                query = query.distinct().exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)

                print "We have %d problematic influencers " % (query.count())

                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))


    def influencers_informations_validated_duplicate_error(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                # these are the problematic ones
                # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
                query = Influencer.objects.filter(show_on_search=True).prefetch_related('platform_set').exclude(blacklisted=True)
                invalid = query.filter(blogname__icontains='404') | query.filter(blogname__icontains='403')

                query1 = query.filter(email__icontains="<")
                query2 = query.filter(email__icontains="href")
                dup_fb = query.filter(fb_url__contains='DUPLICATE')
                dup_tw = query.filter(tw_url__contains='DUPLICATE')
                dup_insta = query.filter(insta_url__contains='DUPLICATE')
                dup_pin = query.filter(pin_url__contains='DUPLICATE')
                query = dup_fb | dup_tw | dup_pin | dup_insta | invalid | query1 | query2

                query = query.distinct()

                print "We have %d problematic influencers " % (query.count())

                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))

    def influencers_informations_high_priority(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.problem = 0
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                # all influencers that have subscribed (and are not validated yet)
                # influencers that show up on search but are not yet validated
                query1 = Influencer.objects.filter(show_on_search=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(blacklisted=True)
                #print "We have %d query1" % query1.count()
                query2 = Influencer.objects.filter(shelf_user__userprofile__blog_verified=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(blacklisted=True)
                query = query1 | query2
                query = query.distinct()
                #query = Influencer.objects.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS, problem=1)
                #query = query.filter(show_on_search=True)
                #query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
                print "We have %d problematic influencers " % (query.count())

                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))

    def influencers_informations_all(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                # these are the problematic ones
                # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
                query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))



    def influencers_suspect_url_content(self, request):
        """
        All the suspect_* functions will have this structure:
            somewhere else in the code (either during crawling or during spot-checks or invariants), we'll set up a
                new Entry for table InfluencerCheck with following fields
            --Influencer FK
            --Platform PK
            --Cause should be a constant picked from pre-selected list of errors
                (NON_EXISTING_URL, URL_CHANGED, SUSPECT_NO_CONTENT, SUSPECT_EMAIL, SUSPECT_NAME_BLOGNAME,
                SUSPECT_BLOGNAME, SUSPECT_DESCRIPTION, SUSPECT_LOCATION, SUSPECT_DUPLICATE_SOCIAL,
                SUSPECT_BROKEN_SOCIAL, SUSPECT_SOCIAL_PLATFORM_OUTLIER_FOLLOWERS, SUSPECT_HIGH_COMMENTS_LOW_SOCIAL_URLS,
                SUSPECT_HIGH_FOLLOWERS_LOW_SOCIAL_URLS, SUSPECT_SOCIAL_HANDLES, SUSPECT_NO_COMMENTS)
            --Fields (could be multiple, so json?)
            --Comment (text field that the QA can submit)
            --Status (should be a dropdown from FIXED, INVALID, REPORT BUG. set by QA)
            --File_Function (this should contain the filename, and function name so that we know where the error is coming from)
        """

        ###### THIS FUNCTION SHOULD FIND ALL INFLUENCER'S WITH FK FROM InfluencerCheck(cause=SUSPECT_NO_CONTENT)
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))


    def influencers_suspect_url(self, request):
        ###### THIS FUNCTION SHOULD FIND ALL INFLUENCER'S WITH FK FROM InfluencerCheck(cause=NON_EXISTING_URL) | InfluencerCheck(cause=URL_CHANGED)
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_email(self, request):
        ###### THIS FUNCTION SHOULD FIND ALL INFLUENCER'S WITH FK FROM InfluencerCheck(cause=SUSPECT_EMAIL)
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_name_similarities(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_blogname(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_descriptions(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_locations(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_duplicate_social(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_broken_social(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_social_follower_outliers(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_highcomments_low_social_platforms(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_highfollowers_low_social_platforms(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_social_handles(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_no_comments(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_highpostscount_low_social_platforms(self, request):
        ### dummy --- TODO: update this
        if request.is_ajax():
            #@todo guess columns definition from serializer
            # these are the problematic ones
            # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
            query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                'problems': Influencer.PROBLEMS,
                'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                'validated': False,
            }, context_instance=RequestContext(request))

    def influencers_suspect_daily_combined(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                #@todo guess columns definition from serializer
                # these are the problematic ones
                # for each social handle we need to find influencers that hare more than one platform with url_not_found=False
                query = Influencer.objects.filter(source__isnull=False).prefetch_related('platform_set').exclude(blacklisted=True)

                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_suspect_all_platforms.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_informations_nonvalidated'),
                    'validated': False,
                }, context_instance=RequestContext(request))


    ############################ end of special case tables

    def influencers_informations_debug(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsDebugSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:

            if request.is_ajax():
                query = Influencer.raw_influencers_for_search()
#                query = Influencer.objects.filter(source__isnull=False, blog_url__isnull=False, date_validated__isnull=False).exclude(show_on_search=True)
                #query = query.filter(date_validated__isnull=True, date_edited__isnull=False)
                query = query.filter(edit_history__field__in=serializers.AdminInfluencerInformationsDebugSerializer.Meta.fields)
                query = query.prefetch_related('platform_set', 'edit_history')
                query = query.distinct()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsDebugSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations_debug.html', {}, context_instance=RequestContext(request))

    def influencers_informations_summary(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        date = datetime.datetime.now()
        reports = []
        for x in xrange(11):
            yesterday = date - timedelta(days=1)
            edits = Influencer.objects.filter(edit_history__timestamp__gte=yesterday, edit_history__timestamp__lte=date, edit_history__field__in=serializers.AdminInfluencerInformationsDebugSerializer.Meta.fields)
            edits = edits.distinct('id')
            edit_ops = InfluencerEditHistory.objects.filter(timestamp__gte=yesterday, timestamp__lte=date, field__in=serializers.AdminInfluencerInformationsDebugSerializer.Meta.fields)
            edit_ops = edit_ops.distinct('influencer')
            validated_total = Influencer.objects.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST)
            validated_total = validated_total.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION)
            validated_total = validated_total.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            report = {
                'date': date,
                'total_urls': Influencer.objects.filter(date_validated__gte=yesterday, date_validated__lte=date).count(),
                'edited': edits.count(),
                'edits_email': edit_ops.filter(field='email').count(),
                'edits_profile_pic': edit_ops.filter(field='profile_pic_url').count(),
                'edits_blogname': edit_ops.filter(field='blogname').count(),
                'edits_name': edit_ops.filter(field='name').count(),
                'edits_meta_desc': edit_ops.filter(field='description').count(),
                'edits_about_url': edit_ops.filter(field='about_url').count(),
                'edits_demographics_location': edit_ops.filter(field='demographics_location').count(),
                'edits_fb_url': edit_ops.filter(field='fb_url').count(),
                'edits_tw_url': edit_ops.filter(field='tw_url').count(),
                'edits_pin_url': edit_ops.filter(field='pin_url').count(),
                'edits_insta_url': edit_ops.filter(field='insta_url').count(),
                'edits_bloglovin_url': edit_ops.filter(field='bloglovin_url').count(),
                'edits_lb_url': edit_ops.filter(field='lb_url').count(),
                'edits_pose': edit_ops.filter(field='pose_url').count(),
                'edits_youtube': edit_ops.filter(field='youtube_url').count(),
            }
            validated = {
                'count_total': validated_total.count(),
                'count_email': validated_total.filter(email__isnull=False).exclude(email="").count(),
                'count_blogname': validated_total.filter(blogname__isnull=False).exclude(blogname="").count(),
                'count_pic': validated_total.filter(profile_pic_url__isnull=False).exclude(profile_pic_url="").count(),
                'count_name': validated_total.filter(name__isnull=False).exclude(name="").count(),
                'count_desc': validated_total.filter(description__isnull=False).exclude(description="").count(),
                'count_loc': validated_total.filter(demographics_location__isnull=False).exclude(demographics_location="").count(),
                'count_fb': validated_total.filter(fb_url__isnull=False).exclude(fb_url="").count(),
                'count_tw': validated_total.filter(tw_url__isnull=False).exclude(tw_url="").count(),
                'count_pin': validated_total.filter(pin_url__isnull=False).exclude(pin_url="").count(),
                'count_insta': validated_total.filter(insta_url__isnull=False).exclude(insta_url="").count(),
                'count_bl': validated_total.filter(bloglovin_url__isnull=False).exclude(bloglovin_url="").count(),
                'count_lb': validated_total.filter(lb_url__isnull=False).exclude(lb_url="").count(),
                'count_pose': validated_total.filter(pose_url__isnull=False).exclude(pose_url="").count(),
                'count_yt': validated_total.filter(youtube_url__isnull=False).exclude(youtube_url="").count(),
                'count_email': validated_total.filter(email__isnull=False).exclude(email="").count(),

                'urls_wo_blogname': validated_total.filter(Q(blogname__isnull=True) | Q(blogname="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_pic': validated_total.filter(Q(profile_pic_url__isnull=True) | Q(profile_pic_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_name': validated_total.filter(Q(name__isnull=True) | Q(name="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_desc': validated_total.filter(Q(description__isnull=True) | Q(description="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_loc': validated_total.filter(Q(demographics_location__isnull=True) | Q(demographics_location="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_fb': validated_total.filter(Q(fb_url__isnull=True) | Q(fb_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_tw': validated_total.filter(Q(tw_url__isnull=True) | Q(tw_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_pin': validated_total.filter(Q(pin_url__isnull=True) | Q(pin_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_insta': validated_total.filter(Q(insta_url__isnull=True) | Q(insta_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_bl': validated_total.filter(Q(bloglovin_url__isnull=True) | Q(bloglovin_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_lb': validated_total.filter(Q(lb_url__isnull=True) | Q(lb_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_pose': validated_total.filter(Q(pose_url__isnull=True) | Q(pose_url="")).only('blog_url').values('blog_url', 'id'),
                'urls_wo_yt': validated_total.filter(Q(youtube_url__isnull=True) | Q(youtube_url="")).only('blog_url').values('blog_url', 'id'),

            }
            reports.append(report)
            date = yesterday
        return render(request, 'pages/admin/influencers_informations_summary.html', {'reports': reports, 'validated': validated}, context_instance=RequestContext(request))


    #####-----</ Brand Admin Actions >-----#####

    #####-----< Admin Affecting Admin Actions >-----#####
    def delete_test_email(self, request, user=0):
        """
        :param request: ``HttpRequest`` instance
        :param user: not used
        :return: ``redirect`` to *admin* home page

        This admin method allows the logged in user to delete their associated test account (probably so
        that they can recreate another account with the same credentials in a future test)
        """
        for email_dict in ADMIN_EMAILS:
            if email_dict['admin_email'] == request.user.email:
                test_email = email_dict['test_email']
                try:
                    user = User.objects.get(email=test_email)
                    user.userprofile.delete()
                    user.delete()
                except ObjectDoesNotExist:
                    pass

        return redirect(reverse('upgrade_admin:index'))
    #####-----</ Admin Affecting Admin Actions >-----#####

    #####-----< reports >-----#####
    def report_health(self, request):
        reports = list(HealthReport.objects.all().order_by('-date', '-id').distinct('date')[:6])
        for report in reports:
            today = report.date
            yesterday = today - timedelta(days=1)
            today_scraps = Influencer.objects.filter(posts__create_date__gte=yesterday, show_on_search=True).distinct('id')
            today_posts = Posts.objects.only('url').filter(create_date__gte=yesterday)
            report.wo_posts = today_scraps.filter(posts_count__lte=0)
            report.wo_items = today_posts.filter(has_products=False)
            report.wo_images = today_posts.filter(eligible_images_count__lte=0)
        return render(request, 'pages/admin/report_health.html', {'reports': reports}, context_instance=RequestContext(request))

    def report_main_summary(self, request):
        date = datetime.date.today()
        reports = []
        for x in xrange(11):
            yesterday = date - timedelta(days=1)
            last_month = date - timedelta(days=30)
            report = {
                'date': date,
                't1_qaed': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST).count(),
                't1_preprocessed': Influencer.objects.filter(platform__platformdataop__operation='fetch_blogname',
                                                             platform__platformdataop__error_msg__isnull=True,
                                                             platform__platformdataop__finished__contains=date).distinct('id').count(),
                't1_blacklisted': Influencer.objects.filter(edit_history__field="blacklisted", edit_history__timestamp__contains=date).distinct('id').count(),
                't1_validated': Influencer.objects.filter(validated_on__contains=ADMIN_TABLE_INFLUENCER_LIST, edit_history__timestamp__contains=date).exclude(edit_history__field="blacklisted").distinct('id').count(),


                't2_qaed': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION).count(),
                't2_preprocessed': Influencer.objects.filter(platformdataop__operation='estimate_if_fashion_blogger',
                                                             platformdataop__error_msg__isnull=True,
                                                             platformdataop__finished__contains=date).count(),
                't2_validated': Influencer.objects.active().filter(date_validated__contains=date,
                                                                   validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION,
                                                                   relevant_to_fashion=True).exclude(edit_history__field="recheck").count(),
                't2_nonfashion': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION, relevant_to_fashion=False).count(),
                't2_notactive': Influencer.objects.inactive().filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION).count(),
                't2_rechecks': Influencer.objects.filter(edit_history__field="recheck", edit_history__timestamp__contains=date).distinct('id').count(),



                't3_preprocessed': Influencer.objects.filter(platform__platformdataop__operation='extract_platforms_from_platform',
                                                             platform__platformdataop__error_msg__isnull=True,
                                                             platform__platformdataop__finished__contains=date).count(),
                't3_validated': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_SOCIAL_HANDLE).count(),


                't4_preprocessed': Influencer.objects.filter(platform__platformdataop__operation='fetch_data',
                                                             platform__platformdataop__error_msg__isnull=True,
                                                             platform__platformdataop__finished__contains=date).distinct().count(),
                't4_fb_processed': Influencer.objects.filter(platform__platformdataop__operation='fetch_data',
                                                             platform__platformdataop__error_msg__isnull=True,
                                                             platform__platformdataop__finished__contains=date,
                                                             platform__platform_name='Facebook').distinct().count(),
                't4_pin_processed': Influencer.objects.filter(platform__platformdataop__operation='fetch_data',
                                                             platform__platformdataop__error_msg__isnull=True,
                                                             platform__platformdataop__finished__contains=date,
                                                             platform__platform_name='Pinterest').distinct().count(),
                't4_insta_processed': Influencer.objects.filter(platform__platformdataop__operation='fetch_data',
                                                             platform__platformdataop__error_msg__isnull=True,
                                                             platform__platformdataop__finished__contains=date,
                                                             platform__platform_name='Instagram').distinct().count(),
                't4_tw_processed': Influencer.objects.filter(platform__platformdataop__operation='fetch_data',
                                                             platform__platformdataop__error_msg__isnull=True,
                                                             platform__platformdataop__finished__contains=date,
                                                             platform__platform_name='Twitter').distinct().count(),
                't4_validated': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).count(),


                't5_error': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS,
                                                      platformdataop__error_msg__isnull=False,
                                                      platformdataop__finished__contains=date).count(),
                't5_100_posts': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION, relevant_to_fashion=False).count(),
                't5_products_imported': Influencer.objects.filter(posts__platformdataop__operation='fetch_products_from_post',
                                                                  posts__platformdataop__error_msg__isnull=True,
                                                                  posts__platformdataop__finished__contains=date).distinct().count(),
                't5_denormalized': Influencer.objects.filter(platformdataop__operation='denormalize_influencer',
                                                             platformdataop__error_msg__isnull=True,
                                                             platformdataop__finished__contains=date).count(),

                't6_added_to_search': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS, show_on_search=True).count(),


                't7_existing_in_search': Influencer.objects.filter(show_on_search=True).count(),
                't7_existing_blogs_scraped': Influencer.objects.filter(platform__platformdataop__operation='fetch_data',
                                                                       platform__platformdataop__error_msg__isnull=True,
                                                                       platform__platformdataop__finished__contains=date,
                                                                       platform__platform_name__in=Platform.BLOG_PLATFORMS,
                                                                       show_on_search=True).distinct().count(),
                't7_had_new_posts': Influencer.objects.filter(show_on_search=True, posts__create_date__contains=date).distinct().count(),
                't7_had_new_products': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION, relevant_to_fashion=False).count(),
                't7_how_many_have_instagram': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION, relevant_to_fashion=False).count(),
                't7_had_new_instagram_posts': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_FASHION, relevant_to_fashion=False).count(),

                #'t4_with_posts': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS, posts_count__gt=0).count(),
                #'t4_with_items': ProductModelShelfMap.objects.filter(added_datetime__contains=date, post__influencer__validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).distinct('post__influencer').count(),
                #'t4_with_mentions': BrandMentions.objects.filter(snapshot_date__contains=date, influencer__validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).distinct('influencer').count(),
                #'t4_with_social': PopularityTimeSeries.objects.filter(snapshot_date__contains=date, influencer__validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS).distinct('influencer').count(),
                #'t4_show_on_search': Influencer.objects.filter(date_validated__contains=date, validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS, show_on_search=True).count(),
                #'t3_with_posts': Influencer.objects.filter(date_validated__contains=date, posts_count__gt=0).count(),
                #'t3_with_items': ProductModelShelfMap.objects.filter(added_datetime__contains=date, post__isnull=False).distinct('post__influencer').count(),
                #'t3_with_mentions': BrandMentions.objects.filter(snapshot_date__contains=date, influencer__show_on_search=True).distinct('influencer').count(),
                #'t3_with_social': PopularityTimeSeries.objects.filter(snapshot_date__contains=date, influencer__show_on_search=True).distinct('influencer').count(),
                #'t3_show_on_search': Influencer.objects.filter(date_validated__contains=date, show_on_search=True).count(),
            }
            report['t1_proceed'] = report['t1_qaed'] - report['t1_blacklisted']
            report['t2_proceed'] = report['t2_qaed'] - (report['t2_nonfashion'] + report['t2_rechecks'])

            reports.append(report)
            date = yesterday
        return render(request, 'pages/admin/report_main_summary.html', {'reports': reports}, context_instance=RequestContext(request))

    def daily_stats(self, request):
        reports = []
        infs1 = Influencer.objects.filter(show_on_search=True)
        show_on_search = infs1.distinct().count()
        report = {}
        tod = datetime.date(2014,5,14)#.today()
        report['show_on_search'] = show_on_search
        print "show_on_search: %d" % show_on_search


        infs_blog_posts_crawled_today = infs1.filter(posts__platform__platform_name__in=Platform.BLOG_PLATFORMS,
                                                     posts__create_date__contains=tod)
        report['blog_posts_crawled_today'] = infs_blog_posts_crawled_today.distinct().count()




        infs_have_fb = infs1.filter(platform__platform_name='Facebook')
        report['infs_have_fb'] = infs_have_fb.distinct().count()
        infs_fb_posts_crawled_today = infs1.filter(posts__platform__platform_name='Facebook',
                                                     posts__create_date__contains=tod)
        report['fb_posts_crawled_today'] = infs_fb_posts_crawled_today.distinct().count()


        infs_have_pin = infs1.filter(platform__platform_name='Pinterest')
        report['infs_have_pin'] = infs_have_pin.distinct().count()
        infs_pin_posts_crawled_today = infs1.filter(posts__platform__platform_name='Pinterest',
                                                     posts__create_date__contains=tod)
        report['pin_posts_crawled_today'] = infs_pin_posts_crawled_today.distinct().count()


        infs_have_tw = infs1.filter(platform__platform_name='Twitter')
        report['infs_have_tw'] = infs_have_tw.distinct().count()
        infs_tw_posts_crawled_today = infs1.filter(posts__platform__platform_name='Twitter',
                                                     posts__create_date__contains=tod)
        report['tw_posts_crawled_today'] = infs_tw_posts_crawled_today.distinct().count()


        infs_have_insta = infs1.filter(platform__platform_name='Instagram')
        report['infs_have_insta'] = infs_have_insta.distinct().count()
        infs_insta_posts_crawled_today = infs1.filter(posts__platform__platform_name='Instagram',
                                                     posts__create_date__contains=tod)
        report['insta_posts_crawled_today'] = infs_insta_posts_crawled_today.distinct().count()


        infs_prods_imported_today = infs1.filter(posts__products_import_completed=True,
                                                 posts__create_date__contains=tod)
        report['prods_imported_today'] = infs_prods_imported_today.distinct().count()


        infs_denormalized_today = infs1.filter(platformdataop__operation='denormalize_influencer')
        report['denormalized'] = infs_denormalized_today.distinct().count()




        reports.append(report)
        return render(request, 'pages/admin/report_daily_stats.html', {'reports': reports}, context_instance=RequestContext(request))


    def pipeline_summary(self, request):

        report = {}
        report_today = {}
        report_yes = {}
        reports = []
        tod = datetime.date.today()
        yes = tod - datetime.timedelta(days=1)

        ## All interesting influencers
        infs1 = Influencer.objects.filter(source__isnull=False).filter(source__isnull=False).exclude(show_on_search=True)
        stage1 = infs1.distinct().count()
        report['stage1'] = stage1
        report_today['stage1'] = infs1.filter(date_created__contains=tod).distinct().count()
        report_yes['stage1'] = infs1.filter(date_created__contains=yes).distinct().count()
        print "Stage1: %d" % stage1

        # Now, count the ones that have been tried to be content-classified
        infs_classification = Influencer.objects.filter(source__isnull=False,
                                                        classification__isnull=False,).filter(source__isnull=False).exclude(show_on_search=True)
        stage_classification = infs_classification.distinct().count()
        report['stage_classification'] = stage_classification
        report_today['stage_classification'] = infs_classification.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_classification'] = infs_classification.filter(date_created__contains=yes).distinct().count()

        print "Stage_classification: %d" % stage_classification


        # All influencers that are classified to be blog
        # (these should be automatically crawled in our daily_fetchers and then evaluated for relevant_to_fashion)
        infs_blog = Influencer.objects.filter(classification='blog').filter(source__isnull=False).exclude(show_on_search=True)
        stage_blog = infs_blog.distinct().count()
        report['stage_blog'] = stage_blog
        report_today['stage_blog'] = infs_blog.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_blog'] = infs_blog.filter(date_created__contains=yes).distinct().count()
        print "Stage_blog: %d" % stage_blog

        # All influencers that are classified to be blog
        # (these should be automatically crawled in our daily_fetchers and then evaluated for relevant_to_fashion)
        infs_w_posts = Influencer.objects.filter(source__isnull=False, posts__isnull=False).exclude(show_on_search=True)
        stage_w_posts = infs_w_posts.distinct().count()
        report['stage_posts'] = stage_w_posts
        report_today['stage_posts'] = infs_w_posts.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_posts'] = infs_w_posts.filter(date_created__contains=yes).distinct().count()
        print "Stage_posts: %d" % stage_w_posts


        # All that were classified to be relevant_to_fashion
        infs_relevant_to_fashion = Influencer.objects.filter(relevant_to_fashion=True).filter(source__isnull=False).exclude(show_on_search=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
        stage_relevant_to_fashion = infs_relevant_to_fashion.distinct().count()
        report['stage_relevant_to_fashion'] = stage_relevant_to_fashion
        report_today['stage_relevant_to_fashion'] = infs_relevant_to_fashion.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_relevant_to_fashion'] = infs_relevant_to_fashion.filter(date_created__contains=yes).distinct().count()
        print "Stage_relevant_to_fashion: %d" % stage_relevant_to_fashion

        # All that were classified to be relevant_to_fashion
        infs_not_relevant_to_fashion = Influencer.objects.filter(relevant_to_fashion=False).filter(source__isnull=False).exclude(show_on_search=True).exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
        stage_not_relevant_to_fashion = infs_not_relevant_to_fashion.distinct().count()
        report['stage_not_relevant_to_fashion'] = stage_not_relevant_to_fashion
        report_today['stage_not_relevant_to_fashion'] = infs_not_relevant_to_fashion.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_not_relevant_to_fashion'] = infs_not_relevant_to_fashion.filter(date_created__contains=yes).distinct().count()
        print "Stage_not_relevant_to_fashion: %d" % stage_not_relevant_to_fashion

        # We only pick those that are active in the last 6 months
        infs_active = infs_relevant_to_fashion.active().exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
        stage_blog_active = infs_active.distinct().count()
        report['stage_blog_active'] = stage_blog_active
        report_today['stage_blog_active'] = infs_active.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_blog_active'] = infs_active.filter(date_created__contains=yes).distinct().count()
        print "Stage_blogs_active: %d" % stage_blog_active

        # We only pick those that are active in the last 6 months
        infs_inactive = infs_relevant_to_fashion.inactive().exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
        stage_blog_inactive = infs_inactive.distinct().count()
        report['stage_blog_inactive'] = stage_blog_inactive
        report_today['stage_blog_inactive'] = infs_inactive.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_blog_inactive'] = infs_inactive.filter(date_created__contains=yes).distinct().count()
        print "Stage_blogs_active: %d" % stage_blog_inactive


        # how many of these active ones have a facebook url
        infs_discover_fb = infs_active.filter(fb_url__isnull=False)
        stage_infs_discover_fb = infs_discover_fb.distinct().count()
        report['stage_infs_discover_fb'] = stage_infs_discover_fb
        report_today['stage_infs_discover_fb'] = infs_discover_fb.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_infs_discover_fb'] = infs_discover_fb.filter(date_created__contains=yes).distinct().count()
        print "Stage_found_facebook: %d" % stage_infs_discover_fb

        # how many of these have twitter url
        infs_discover_tw = infs_active.filter(tw_url__isnull=False)
        stage_infs_discover_tw = infs_discover_tw.distinct().count()
        report['stage_infs_discover_tw'] = stage_infs_discover_tw
        report_today['stage_infs_discover_tw'] = infs_discover_tw.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_infs_discover_tw'] = infs_discover_tw.filter(date_created__contains=yes).distinct().count()
        print "Stage_found_twitter: %d" % stage_infs_discover_tw

        infs_discover_pin = infs_active.filter(pin_url__isnull=False)
        stage_infs_discover_pin = infs_discover_pin.distinct().count()
        report['stage_infs_discover_pin'] = stage_infs_discover_pin
        report_today['stage_infs_discover_pin'] = infs_discover_pin.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_infs_discover_pin'] = infs_discover_pin.filter(date_created__contains=yes).distinct().count()
        print "Stage_found_pinterest: %d" % stage_infs_discover_pin

        infs_discover_insta = infs_active.filter(insta_url__isnull=False)
        stage_infs_discover_insta = infs_discover_insta.distinct().count()
        report['stage_infs_discover_insta'] = stage_infs_discover_insta
        report_today['stage_infs_discover_insta'] = infs_discover_insta.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_infs_discover_insta'] = infs_discover_insta.filter(date_created__contains=yes).distinct().count()
        print "Stage_found_instagram: %d" % stage_infs_discover_insta

        # how many of these active blogs have been crawled completely?
        indepth_crawled = infs_active.filter(platform__indepth_processed=True)
        stage_indepth_crawled = indepth_crawled.distinct().count()
        report['stage_indepth_crawled'] = stage_indepth_crawled
        report_today['stage_indepth_crawled'] = indepth_crawled.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_indepth_crawled'] = indepth_crawled.filter(date_created__contains=yes).distinct().count()
        print "Stage_indepth_crawled: %d" % stage_indepth_crawled

        # how many have a blogname
        infs_have_blogname = infs_active.filter(blogname__isnull=False)
        stage_have_blogname = infs_have_blogname.distinct().count()
        report['stage_have_blogname'] = stage_have_blogname
        report_today['stage_have_blogname'] = infs_have_blogname.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_have_blogname'] = infs_have_blogname.filter(date_created__contains=yes).distinct().count()
        print "Stage_have_blogname: %d" % stage_have_blogname

        # how many have a description
        infs_have_description = infs_active.filter(description__isnull=False)
        stage_have_description = infs_have_description.distinct().count()
        report['stage_have_description'] = stage_have_description
        report_today['stage_have_description'] = infs_have_description.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_have_description'] = infs_have_description.filter(date_created__contains=yes).distinct().count()
        print "Stage_have_description: %d" % stage_have_description

        # how many have a name?
        infs_have_name = infs_active.filter(name__isnull=False)
        stage_have_name = infs_have_name.distinct().count()
        report['stage_have_name'] = stage_have_name
        report_today['stage_have_name'] = infs_have_name.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_have_name'] = infs_have_name.filter(date_created__contains=yes).distinct().count()
        print "Stage_have_name: %d" % stage_have_name

        # how many have an email?
        infs_have_email = infs_active.filter(email__isnull=False)
        stage_have_email = infs_have_email.distinct().count()
        report['stage_have_email'] = stage_have_email
        report_today['stage_have_email'] = infs_have_email.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_have_email'] = infs_have_email.filter(date_created__contains=yes).distinct().count()
        print "Stage_have_email: %d" % stage_have_email

        # how many have a profile pic?
        infs_have_pic = infs_active.filter(profile_pic_url__isnull=False)
        stage_have_pic = infs_have_pic.distinct().count()
        report['stage_have_pic'] = stage_have_pic
        report_today['stage_have_pic'] = infs_have_pic.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_have_pic'] = infs_have_pic.filter(date_created__contains=yes).distinct().count()
        print "Stage_have_pic: %d" % stage_have_pic


        # how many have everything to be considered ready to show up in search results?
        infs_have_all = infs_active.filter(Q(blogname__isnull=False) | Q(name__isnull=False),
                                           #email__isnull=False,
                                           profile_pic_url__isnull=False,
                                           posts_count__gt=10)
        stage_have_all = infs_have_all.distinct().count()
        report['stage_have_all'] = stage_have_all
        report_today['stage_have_all'] = infs_have_all.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_have_all'] = infs_have_all.filter(date_created__contains=yes).distinct().count()

        # how many have everything to be considered ready to show up in search results?
        infs_have_all_at_least_two_comments = infs_active.filter(Q(blogname__isnull=False) | Q(name__isnull=False),
                                           #email__isnull=False,
                                           profile_pic_url__isnull=False,
                                           posts_count__gt=10,
                                           average_num_comments_per_post__gte=2)
        stage_have_at_least_two_comments = infs_have_all_at_least_two_comments.distinct().count()
        report['stage_have_at_least_two_comments'] = stage_have_at_least_two_comments
        report_today['stage_have_at_least_two_comments'] = infs_have_all_at_least_two_comments.filter(date_created__contains=tod).distinct().count()
        report_yes['stage_have_at_least_two_comments'] = infs_have_all_at_least_two_comments.filter(date_created__contains=yes).distinct().count()

        reports.append(report)
        reports.append(report_today)
        reports.append(report_yes)
        print "Stage_have_all: %d" % stage_have_all
        print reports
        return render(request, 'pages/admin/report_pipeline.html', {'reports': reports}, context_instance=RequestContext(request))

    def influencers_current_search_summary(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            if influencer.suspicious_url:
                influencer.set_blacklist_with_reason('suscipicous_url')
                influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.date_validated = datetime.datetime.now()
            influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Influencer.objects.filter(
                    show_on_search=True
                ).exclude(
                    validated_on__contains=ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED
                )
                query = query.exclude(source=u'r29_customer_import')
                #.exclude(source__contains='brand')
                #query = query.order_by('-score_popularity_overall')
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_current_search_summary'),
                    'validated': True,
                }, context_instance=RequestContext(request))

    def influencers_blogger_signedup_initialize(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            try:
                validated_on = json.loads(influencer.validated_on)
            except (ValueError, TypeError):
                validated_on = []
            validated_on.append(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            validated_on = list(set(validated_on))
            influencer.validated_on = json.dumps(validated_on)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            ### make sure they show on search so that these bloggers can login and edit their profiles
            influencer.date_upgraded_to_show_on_search = datetime.date.today()
            influencer.old_show_on_search = True
            influencer.show_on_search = True
            # will use this flag on Intercom side to send notifications to bloggers once their profile is ready
            # only if this blogger signed-up and we didn't invite them yet
            if 'blogger_signup' in influencer.source and not influencer.ready_to_invite:
                influencer.ready_to_invite = True
            
            # make sure that blacklisted flag is false (we can later check if we classified this url as a non-blog
            # and fine-tune our algorithms)
            influencer.blacklisted = False
            influencer.save()
            influencer.set_profile_pic()
            # now update the intercom as well
            if influencer.shelf_user:
                user_prof = influencer.shelf_user.userprofile
                user_prof.update_intercom()

            print("Influencer [%r] has source=[%r] is now upgraded to show_on_search and ready_to_invite is also set (%r)" % (influencer, influencer.source, influencer.ready_to_invite))
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():

                # pc_influencer_ids = PostAnalytics.objects.exclude(
                #     post__influencer__show_on_search=True
                # ).exclude(
                #     post__influencer__isnull=True
                # ).values_list('post__influencer_id', flat=True)
                if True:
                    inf_ids = Influencer.objects.filter(
                        source__contains='blogger_signup',
                        shelf_user__userprofile__blog_verified=True
                    ).exclude(
                        show_on_search=True
                    ).exclude(
                        email_all_other__icontains='problem'
                    ).exclude(
                        blogname__icontains='problem'
                    ).exclude(
                        email_for_advertising_or_collaborations__icontains='problem'
                    ).values_list(
                        'id', flat=True)

                    inf_ids = list(inf_ids)
                else:
                    coll = InfluencersGroup.objects.get(id=1611)
                    influencers = coll.influencers
                    inf_ids = [i.id for i in influencers]

                query = Influencer.objects.filter(id__in=inf_ids)

                #query.update(is_active=True)
                data = admin_helpers.get_objects(
                    request,
                    query,
                    serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_current_search_summary'),
                    'validated': False,
                }, context_instance=RequestContext(request))


    def influencers_blogger_signedup_check(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            if influencer.suspicious_url:
                # If the flag is set and then the id is saved... it needs to go
                # to a different table "Suspicious URL's"
                # (Save this as blacklisted=True and blacklist_reason=['suscipicous_url'])
                influencer.set_blacklist_with_reason('suscipicous_url')
                influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED)
            else:
                # if the save button is clicked, the id needs to go to another table "ready for upgrade".
                influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_READY_FOR_UPGRADE)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Influencer.objects.filter(
                    source__contains='blogger_signup',
                    shelf_user__userprofile__blog_verified=True,
                    #profile_pic_url__isnull=False,
                    validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS,
                ).exclude(
                    Q(show_on_search=True) | Q(validated_on__contains=ADMIN_TABLE_INFLUENCER_READY_FOR_UPGRADE) | Q(validated_on__contains=ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED)
                ).prefetch_related(
                    # 'posts_set__platformdataop_set',
                    # 'posts_set__productmodelshelfmap_set',
                    # 'platformdataop_set',
                    # 'platform_set',
                )
                query = query.filter(
                    source__contains='blogger_signup',
                    shelf_user__userprofile__blog_verified=True,
                    #profile_pic_url__isnull=False,
                    validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS,
                ).exclude(
                    Q(show_on_search=True) | Q(validated_on__contains=ADMIN_TABLE_INFLUENCER_READY_FOR_UPGRADE) | Q(validated_on__contains=ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED)
                )
                # query = query.distinct()
                query = query.with_counters()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerCurrentSearchResultsSerializer)
                #return HttpResponse("<body></body>")
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/report_current_search.html', {
                    'included_is_ready_to_notify': True,
                }, context_instance=RequestContext(request))


    def influencers_profiles_check(self, request):
        if request.method == 'UPDATE':
            pass
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            user = get_object_or_404(UserModel, id=row_id)
            user_profile = user.userprofile
            if user_profile:
                user_profile.last_modified = datetime.datetime.now()
                user_profile.save()
                data = {
                    name: value
                }
                if name == 'blog_page':
                    profile_serializer = serializers.AdminUserProfileSerializer(
                        user_profile, data=data, partial=True)
                    if profile_serializer.is_valid():
                        profile_serializer.save()
                        account_helpers.create_and_connect_user_to_influencer.apply_async(
                            [user_profile.id], queue='celery')
                    else:
                        return HttpResponseBadRequest(profile_serializer.errors)
                return HttpResponse()
            else:
                return HttpResponseBadRequest()
        else:
            if request.is_ajax():
                query = UserModel.objects.exclude(
                    email__contains='toggle'
                ).prefetch_related(
                    'userprofile__influencer'
                )

                data = admin_helpers.get_objects(request, query, serializers.AdminUserSerializer)
                return HttpResponse(data, content_type='application/json')
            else:
                return render(
                    request, 'pages/admin/influencers_profiles_check.html', {},
                    context_instance=RequestContext(request))


    def influencers_ready_for_upgrade(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            if influencer.suspicious_url:
                influencer.set_blacklist_with_reason('suscipicous_url')
                influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Influencer.objects.filter(
                    validated_on__contains=ADMIN_TABLE_INFLUENCER_READY_FOR_UPGRADE
                ).exclude(
                    validated_on__contains=ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED
                ).with_counters()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerCurrentSearchResultsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(
                    request,
                    'pages/admin/influencers_ready_for_upgrade.html',
                    {},
                    context_instance=RequestContext(request)
                )

    def influencers_with_suspicious_url(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            if influencer.suspicious_url:
                influencer.set_blacklist_with_reason('suscipicous_url')
                influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED)
            else:
                influencer.remove_from_validated_on(ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL)
                influencer.remove_from_validated_on(ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Influencer.objects.filter(
                    validated_on__contains=ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED
                )
                query = query.with_counters()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerCurrentSearchResultsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(
                    request,
                    'pages/admin/influencers_with_suspicious_url.html',
                    {},
                    context_instance=RequestContext(request)
                )


    def influencers_qaed_on_search(self, request):
        # prefetch_related("posts_set", "posts_set__platform", 'brandmentions_set', 'posts_set__productmodelshelfmap_set')
        # query = query.prefetch_related("platformdataop_set", "posts_set__platformdataop_set", 'platform_set')
        query = Influencer.objects.filter(
            source__contains='blogger_signup',
            shelf_user__userprofile__blog_verified=True,
            validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS,
            show_on_search=True
        )
        query = query.with_counters()
        # query = query.distinct()
        options = {
            "request": request,
            "load_serializer": serializers.AdminInfluencerCurrentSearchResultsSerializer,
            "store_serializer": serializers.AdminInfluencerInformationsSerializer,
            "context": {},
            "template": 'pages/admin/report_current_search.html',
            "query": query,
            "model": Influencer
        }
        return table_page(options)

    def influencers_submitted_by_users(self, request, post_collection_id=None):
        admin_brands = [148634, 493699]

        if post_collection_id is not None:
            pa_qs = PostAnalytics.objects.filter(
                collection_id=post_collection_id)
        else:
            pa_qs = PostAnalytics.objects.exclude(
                collection__creator_brand_id__in=admin_brands
            )
        inf_ids = pa_qs.values_list('post__influencer', flat=True)

        query = Influencer.objects.filter(
            id__in=list(inf_ids)
        ).exclude(
            validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS
        ).order_by(
            '-date_created'
        )

        options = {
            "request": request,
            "load_serializer": serializers.AdminInfluencerInformationsSerializer,
            "store_serializer": serializers.AdminInfluencerInformationsSerializer,
            "context": {},
            "template": 'pages/admin/influencers_submitted_by_users.html',
            "query": query,
            "model": Influencer
        }
        return table_page(options)

    def influencers_uploaded_by_customers(self, request):
        if request.method == 'UPDATE':
            row_id = request.GET.get('id')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_validated = datetime.datetime.now()
            influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_INFORMATIONS)
            if influencer.suspicious_url:
                influencer.set_blacklist_with_reason('suscipicous_url')
                influencer.append_validated_on(ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED)
            if influencer.qa:
                influencer.qa = " ".join((influencer.qa, request.visitor["auth_user"].username))
            else:
                influencer.qa = request.visitor["auth_user"].username
            influencer.save()
            if influencer.fb_url:
                handle_social_handle_updates(influencer, 'fb_url', influencer.fb_url)
            if influencer.pin_url:
                handle_social_handle_updates(influencer, 'pin_url', influencer.pin_url)
            if influencer.tw_url:
                handle_social_handle_updates(influencer, 'tw_url', influencer.tw_url)
            if influencer.insta_url:
                handle_social_handle_updates(influencer, 'insta_url', influencer.insta_url)
            influencer.set_show_on_search(True)
            return HttpResponse()
        elif request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():

                if name == "blog_url":
                    handle_blog_url_change(influencer, value)
                serializer.save()
                handle_social_handle_updates(influencer, name, value)
            else:
                return HttpResponseBadRequest(serializer.errors)
            return HttpResponse()
        else:
            if request.is_ajax():

                query = Influencer.objects.all().has_tags(
                    'customer_uploaded'
                ).exclude(
                    old_show_on_search=True
                ).order_by(
                    '-date_created'
                )
                #query = query.order_by('-score_popularity_overall')
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_uploaded_by_customers'),
                    'validated': False,
                }, context_instance=RequestContext(request))

    def post_analytics_collections_with_loading_entries(self, request):
        admin_brands = [148634, 493699]

        query = PostAnalyticsCollection.objects.exclude(
            Q(creator_brand_id__in=admin_brands) | Q(postanalytics__post__isnull=True)
        ).distinct().order_by('creator_brand')

        options = {
            "request": request,
            "load_serializer": serializers.AdminPostAnalyticsCollectionSerializer,
            "store_serializer": serializers.AdminPostAnalyticsCollectionSerializer,
            "context": {
            },
            "template": 'pages/admin/post_analytics_collections_with_loading_entries.html',
            "query": query,
            "model": PostAnalyticsCollection,
            "skip_influencers_validate": True,
        }
        return table_page(options)

    def influencers_blogger_signedup_notify(self, request):
        if request.method == 'POST':
            row_id = request.POST.get('pk')
            name = request.POST.get('name')
            value = request.POST.get('value')
            influencer = get_object_or_404(Influencer, id=row_id)
            influencer.date_edited = datetime.datetime.now()
            influencer.save()
            data = {
                name: value
            }
            if name == "qa":
                return HttpResponse()
            InfluencerEditHistory.commit_change(influencer, name, value)
            serializer = serializers.AdminInfluencerInformationsSerializer(influencer, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                # now we should send a notification to intercom
            else:
                return HttpResponseBadRequest(serializer.errors)
            if name == "ready_to_invite":
                try:
                    user_prof = influencer.shelf_user.userprofile
                    user_prof.create_in_intercom()
                except:
                    # no user, intercom error
                    pass
            return HttpResponse()
        else:
            if request.is_ajax():
                query = Influencer.objects.filter(source__contains='blogger_signup',
                                                  shelf_user__userprofile__blog_verified=True,
                                                  #profile_pic_url__isnull=False,
                                                  validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS,
                                                  ).exclude(show_on_search=True)
                query = query.distinct()
                print "got %d influenceres " % query.count()
                data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerInformationsSerializer)
                #return HttpResponse("<body></body>")
                return HttpResponse(data, content_type="application/json")
            else:
                return render(request, 'pages/admin/influencers_informations.html', {
                    'problems': Influencer.PROBLEMS,
                    'source': reverse('upgrade_admin:influencers_current_search_summary'),
                    'validated': False,
                }, context_instance=RequestContext(request))


    def influencers_current_search_potential_summary(self, request):
        if request.is_ajax():
            query = Influencer.objects.filter(
                source__contains='blogger_signup',
                shelf_user__isnull=False
            ).exclude(
                show_on_search=True
            ).exclude(
                validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS
            ).order_by(
                '-score_popularity_overall'
            )
            query = query.with_counters()
            query = query.distinct()
            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerCurrentSearchResultsSerializer)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/report_current_search.html', {}, context_instance=RequestContext(request))

    def report_social(self, request):
        """
        :param request: ``HttpRequest`` instance
        :return: ``HttpResponse`` instance
        """
        if request.is_ajax():
            query = Influencer.raw_influencers_for_search()
            data = admin_helpers.get_objects(request, query, serializers.AdminInfluencerSocialMedia)
            return HttpResponse(data, content_type="application/json")
        else:
            return render(request, 'pages/admin/social_media_table.html', {
                'source': reverse('upgrade_admin:report_social'),
            }, context_instance=RequestContext(request))



    def report_social_summary(self, request):
        reports = []
        return render(request, 'pages/admin/social_media_activity.html', {'reports': reports}, context_instance=RequestContext(request))

    def pdo_stats(self, request):
        days = float(request.GET.get('days', '3'))
        rep = pdo_stats_report(days)
        operations, day_specs, by_day = rep['operations'], rep['day_specs'], rep['by_day']

        table_rows = []
        for operation in operations:
            trow = [operation]
            for day_spec in day_specs:
                trow.append(by_day[day_spec][operation])
            table_rows.append(trow)

        return render(request, 'pages/admin/pdo_stats.html',
                      {
                          'days': days,
                          'day_specs': day_specs,
                          'table_rows': table_rows,
                      },
                      context_instance=RequestContext(request))

    def pdo_error_stats(self, request):
        days = float(request.GET.get('days', '3'))
        connection = db_util.connection_for_reading()
        cur = connection.cursor()

        cur.execute("""
        (
            with pdo_data as (
                select
                    pdo.operation,
                    pdo.error_msg,
                    extract(month from pdo.started) as month,
                    extract(day from pdo.started) as day
                from debra_platformdataop pdo
                where pdo.started >= current_timestamp - '{days} days'::interval
                and pdo.operation <> 'fetch_data'
                and error_msg is not null
            )
            select operation, error_msg, month, day, count(*) as cnt
            from pdo_data
            group by operation, error_msg, month, day
            having count(*) > 1
        )

        union

        (
            with pdo_data as (
                select
                    pl.platform_name,
                    (pdo.data_json::json->'policy')::text as policy,
                    pdo.error_msg,
                    extract(month from pdo.started) as month,
                    extract(day from pdo.started) as day
                from debra_platformdataop pdo
                join debra_platform pl on pl.id = pdo.platform_id
                where pdo.started >= current_timestamp - '{days} days'::interval
                and pdo.operation = 'fetch_data'
                and error_msg is not null
            )
            select 'fetch_data.' || platform_name || '.' || coalesce(trim(both '"' from policy), '?') as operation,
                error_msg, month, day, count(*) as cnt
            from pdo_data
            group by operation, error_msg, month, day
            having count(*) > 1
        )

        order by operation, cnt desc, error_msg, month, day
        """.format(days=days))
        data = cur.fetchall()
        cur.close()

        operations = utils.unique_sameorder(r[0] for r in data)

        error_msgs_by_operation = defaultdict(list)
        by_day = defaultdict(lambda: defaultdict(dict))
        for (operation, error_msg, month, day, cnt) in data:
            by_day[(int(month), int(day))][operation][error_msg] = cnt
            error_msgs_by_operation[operation].append(error_msg)

        day_specs = sorted(by_day.keys(), reverse=True)

        table_rows = []
        for operation in operations:
            for error_msg in error_msgs_by_operation[operation]:
                trow = [operation, error_msg]
                for day_spec in day_specs:
                    trow.append(by_day[day_spec][operation].get(error_msg, 0))
                table_rows.append(trow)

        return render(request, 'pages/admin/pdo_error_stats.html',
                      {
                          'days': days,
                          'day_specs': day_specs,
                          'table_rows': table_rows,
                      },
                      context_instance=RequestContext(request))


    def pdo_all_errors(self, request):
        days = float(request.GET.get('days', '0.3'))
        connection = db_util.connection_for_reading()
        cur = connection.cursor()
        cur.execute("""
        select
        pdo.id as pdo_id,
        pdo.operation,
        pdo.error_msg,
        pdo.started,
        (pdo.finished - pdo.started) as execution_time,
        inf.id as inf_id,
        inf.blog_url as inf_blog_url,
        pl.id as pl_id,
        pl.url as pl_url,
        po.id as po_id,
        po.url as po_url,
        pm.id as pm_id,
        pm.prod_url as pm_url,
        fol.id as fol_id,
        fol.url as fol_url
        from debra_platformdataop pdo
        left join debra_influencer inf on inf.id=pdo.influencer_id
        left join debra_platform pl on pl.id=pdo.platform_id
        left join debra_posts po on po.id=pdo.post_id
        left join debra_productmodel pm on pm.id=pdo.product_model_id
        left join debra_follower fol on fol.id=pdo.follower_id
        where pdo.started >= current_timestamp - '{days} days'::interval
        and pdo.error_msg is not null
        order by pdo.started desc
        """.format(days=days))
        data = cur.fetchall()
        cur.close()

        return render(request, 'pages/admin/pdo_all_errors.html',
                      {
                          'days': days,
                          'data': data,
                      },
                      context_instance=RequestContext(request))

    def hit_influencers_that_joined(self, request):
        with open(os.path.join(PROJECT_PATH, 'debra/sqlqueries/hit_users_that_joined.sql')) as f:
            sql = f.read()
        return render_sql_results(request,
                                  sql,
                                  [],
                                  ['date joined', 'inf_id', 'inf_name', 'blog_url', 'hits'])

    def ec2_report(self, request):
        from django.conf import settings
        import boto

        ec2_conn = boto.connect_ec2(settings.AWS_KEY, settings.AWS_PRIV_KEY)
        cw_conn = boto.connect_cloudwatch(settings.AWS_KEY, settings.AWS_PRIV_KEY)

        reservations = boto.get_all_instances()
        instances = []
        for r in reservations:
            instances += r.instances

        instance_ids = [inst.id for inst in instaces]

        # Switch on cloudwatch on all instances
        #for inst in instances:
        #    ec2_conn.monitor_instance(inst.id)

        # Example of getting CPUUtilization stats
        #cw.get_metric_statistics(300,
        #                         datetime.datetime.utcnow() - datetime.timedelta(seconds=600),
        #                         datetime.datetime.utcnow(),
        #                         'CPUUtilization',
        #                         'AWS/EC2',
        #                         'Average',
        #                         dimensions={'InstanceId': instance_ids})

    #####-----</ reports >-----#####


modify_admin_site = ModifyItemsAdminSite(name="upgrade_admin", app_name="upgrade_admin")






#####-----< Registers >-----#####
admin.site.register(Promoinfo)
admin.site.register(Brands, BrandsAdmin)

admin.site.register(ProductModel,ProductModelAdmin)
admin.site.register(ColorSizeModel, CSMAdmin)

admin.site.register(ProductPrice, PPAdmin)
admin.site.register(ProductAvailability, ProductAvailabilityAdmin)
admin.site.register(ProductPromotion, ProductPromotionAdmin)

admin.site.register(UserProfile, UserProfileAdmin)
