# -*- coding: utf-8 -*-
import json
import time
import datetime
import csv
import xlwt
import StringIO
from celery.decorators import task
from django.conf import settings
from django.db.models import Q
from django.core.mail import EmailMessage
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, HttpResponse, HttpResponseBadRequest, Http404
from debra.constants import STRIPE_PLAN_STARTUP, STRIPE_PLAN_CHEAP, STRIPE_PLAN_BASIC, ATUL_EMAILS, LAUREN_EMAILS
from django.core.serializers.json import DjangoJSONEncoder
from django.core.urlresolvers import reverse
from rest_framework import serializers
from debra import models
from debra import search_helpers
from collections import OrderedDict

all_european_countries = [
    u"Albania", u"Shqiperia", u"Andorra", u"Armenia", u"Hayastan", u"Austria",
    u"Oesterreich", u"Azerbaijan", u"Azarbaycan", u"Belarus", u"Byelarus",
    u"Беларусь", u"Belgium", u"Belgique", u"Belgie", u"Bosnia ", u"Herzegovina",
    u"Bosna ", u"Hercegovina", u"Bulgaria", u"Bulgariya", u"Croatia",
    u"Hrvatska", u"Cyprus", u"Kypros", u"Kibris", u"Czech", u"Ceska",
    u"Denmark", u"Estonia", u"Eesti", u"Finland", u"Suomi", u"France",
    u"Francaise", u"Georgia", u"Sakartvelo", u"საქართველო", u"Germany",
    u"Deutschland", u"Greece", u"Ellas", u"Ελλάδα", u"Hungary", u"Magyarorszag",
    u"Iceland",
    u"Island", u"Ireland", u"Eire", u"Italy", u"Italia", u"Latvia", u"Lietuva",
    u"Latvija", u"Liechtenstein", u"Lithuania", u"Lietuva", u"Luxembourg",
    u"Macedonia", u"Makedonija", u"Malta", u"Moldova", u"Monaco", u"Montenegro",
    u"Crna Gora", u"Netherlands", u"Nederland", u"Norway", u"Norge", u"Poland",
    u"Polska", u"Portugal", u"Romania", u"Russia", u"Rossiya", u"Россия",
    u"San Marino", u"Serbia", u"Srbija", u"Slovakia", u"Slovensko", u"Slovenia",
    u"Slovenija", u"Spain", u"Espana", u"Sweden", u"Sverige", u"Switzerland",
    u"Schweiz", u"Suisse", u"Svizzera", u"Turkey", u"Turkiye", u"Ukraine",
    u"United Kingdom"]


def string_cleanup(input):
    return " ".join((input or "").encode("utf-8").replace(",", " ").replace(";", " ").replace("\t", " ").split())


def integer_cleanup(input):
    try:
        return int(input or 0)
    except ValueError:
        return 0


def render_to_xls_string(result, headers=None, footers=[], title=None, file_type=None):

    file_type = 'xls'

    output = StringIO.StringIO()

    workbook = xlwt.Workbook()
    f = xlwt.Font()
    f.bold = True
    h_style = xlwt.XFStyle()
    h_style.font = f

    sheet = workbook.add_sheet(title)

    for col_no, value in enumerate(headers):
        sheet.write(0, col_no, value, h_style)

    for row_no, row in enumerate(result):
        for col_no, value in enumerate(row.values()):
            sheet.write(row_no + 1, col_no, value)

    for row_no, row in enumerate(footers):
        for col_no, value in enumerate(row):
            sheet.write(row_no + 1 + len(result), col_no, value)

    workbook.save(output)
    output.seek(0)

    return output.read()

def result_to_string(result, file_type=None):
    if not file_type in ("csv", "xls"):
        file_type = "csv"
    output = StringIO.StringIO()
    row_data = [
        "Blogger name",
        "Blog name",
        "Blog url",
        "Emails",
        #"Alexa Rank",
        #"Avg number of posts",
        #"Avg comments per post",
        "Facebook page",
        "Facebook followers",
        #"Facebook posts per month",
        #"Facebook total posts",
        #"Facebook avg number of comments",
        #"Facebook avg number of shares",
        #"Facebook avg number of likes",

        "Instagram page",
        "Instagram followers",
        #"Instagram posts per month",
        #"Instagram total posts",
        #"Instagram avg number of comments",
        #"Instagram avg number of shares",
        #"Instagram avg number of likes",

        "Pinterest page",
        "Pinterest followers",
        #"Pinterest posts per month",
        #"Pinterest total posts",
        #"Pinterest avg number of comments",
        #"Pinterest avg number of shares",
        #"Pinterest avg number of likes",

        "Twitter page",
        "Twitter followers",
        #"Twitter posts per month",
        #"Twitter total posts",
        #"Twitter avg number of comments",
        #"Twitter avg number of shares",
        #"Twitter avg number of likes"
        "Similar Web UVM"
    ]
    if file_type == "csv":
        csvwriter = csv.writer(output, delimiter=',',quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerow(row_data)
    elif file_type == "xls":
        workbook = xlwt.Workbook()
        f = xlwt.Font()
        f.bold = True
        h_style = xlwt.XFStyle()
        h_style.font = f
        sheet = workbook.add_sheet('Exported influencers data')
        for col_no, value in enumerate(row_data):
            sheet.write(0, col_no, value, h_style)
    for row_no, row in enumerate(result):
        platforms = {}
        for platform in row["platforms"]:
            platforms[platform["platform_name"]] = platform
        row_data = [
            string_cleanup(row["name"]),
            string_cleanup(row["blogname"]),
            string_cleanup(row["blog_url"]),
            string_cleanup(row["email_for_advertising_or_collaborations"] if row["email_for_advertising_or_collaborations"] else row["email_all_other"] if row["email_all_other"] else row["contact_form_if_no_email"]),
            #integer_cleanup(row["alexa_rank"]),
            #integer_cleanup(row["average_num_posts"]),
            #integer_cleanup(row["average_num_comments_per_post"]),
            string_cleanup(platforms.get("Facebook", {}).get("url")),
            integer_cleanup(platforms.get("Facebook", {}).get("num_followers")),
            #integer_cleanup(platforms.get("Facebook", {}).get("posting_rate")),
            #integer_cleanup(platforms.get("Facebook", {}).get("num_posts")),
            #integer_cleanup(platforms.get("Facebook", {}).get("avg_numcomments_overall")),
            #integer_cleanup(platforms.get("Facebook", {}).get("avg_numshares_overall")),
            #integer_cleanup(platforms.get("Facebook", {}).get("avg_numlikes_overall")),

            string_cleanup(platforms.get("Instagram", {}).get("url")),
            integer_cleanup(platforms.get("Instagram", {}).get("num_followers")),
            #integer_cleanup(platforms.get("Instagram", {}).get("posting_rate")),
            #integer_cleanup(platforms.get("Instagram", {}).get("num_posts")),
            #integer_cleanup(platforms.get("Instagram", {}).get("avg_numcomments_overall")),
            #integer_cleanup(platforms.get("Instagram", {}).get("avg_numshares_overall")),
            #integer_cleanup(platforms.get("Instagram", {}).get("avg_numlikes_overall")),

            string_cleanup(platforms.get("Pinterest", {}).get("url")),
            integer_cleanup(platforms.get("Pinterest", {}).get("num_followers")),
            #integer_cleanup(platforms.get("Pinterest", {}).get("posting_rate")),
            #integer_cleanup(platforms.get("Pinterest", {}).get("num_posts")),
            #integer_cleanup(platforms.get("Pinterest", {}).get("avg_numcomments_overall")),
            #integer_cleanup(platforms.get("Pinterest", {}).get("avg_numshares_overall")),
            #integer_cleanup(platforms.get("Pinterest", {}).get("avg_numlikes_overall")),

            string_cleanup(platforms.get("Twitter", {}).get("url")),
            integer_cleanup(platforms.get("Twitter", {}).get("num_followers")),
            #integer_cleanup(platforms.get("Twitter", {}).get("posting_rate")),
            #integer_cleanup(platforms.get("Twitter", {}).get("num_posts")),
            #integer_cleanup(platforms.get("Twitter", {}).get("avg_numcomments_overall")),
            #integer_cleanup(platforms.get("Twitter", {}).get("avg_numshares_overall")),
            #integer_cleanup(platforms.get("Twitter", {}).get("avg_numlikes_overall"))
            integer_cleanup(row["similar_web_uvm"])
        ]
        if file_type == "csv":
            csvwriter.writerow(row_data)
        elif file_type == "xls":
            for col_no, value in enumerate(row_data):
                if type(value) == int:
                    sheet.write(row_no+1, col_no, value)
                else:
                    if value.startswith("http"):
                        value = value.replace('"', '')
                        try:
                            sheet.write(row_no+1, col_no, xlwt.Formula("HYPERLINK(\"%s\")"%str(value).decode('utf-8')))
                        except:
                            sheet.write(row_no+1, col_no, str(value).decode('utf-8'))
                    else:
                        sheet.write(row_no+1, col_no, str(value).decode('utf-8'))
    if file_type == "xls":
        workbook.save(output)
    output.seek(0)
    return output.read()


class PlatformExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Platform
        fields = ('id', 'num_followers', 'posting_rate', 'numposts',
                  'avg_numcomments_overall', 'avg_numshares_overall',
                  'avg_numlikes_overall', 'url', 'platform_name')


class InfluencerExportSerializer(serializers.ModelSerializer):

    platforms = PlatformExportSerializer(source='get_platform_for_search')
    alexa_rank = serializers.SerializerMethodField('get_alexa_rank')
    similar_web_uvm = serializers.SerializerMethodField('get_similar_web_uvm')

    class Meta:
        model = models.Influencer
        fields = ('id', 'name', 'platforms', 'blogname', 'alexa_rank', 'blog_url', 'contact_form_if_no_email',
                  'email_for_advertising_or_collaborations', 'email_all_other', 'average_num_posts', 'average_num_comments_per_post', 'similar_web_uvm')

    def get_alexa_rank(self, obj):
        plat = obj.blog_platform
        alexa = models.AlexaRankingInfo.objects.filter(platform=plat)
        if len(alexa) > 0:
            a = alexa.order_by('-id')[0]
            return a.rank
        return None

    def get_similar_web_uvm(self, obj):
        if len(models.SimilarWebVisits.objects.monthly(obj)) > 0:
            # return models.SimilarWebVisits.objects.monthly(obj).order_by('-begins')[0].count
            return models.SimilarWebVisits.objects.monthly(obj)[0].count
        return 0

@task(name="debra.dataexport_views.export_worker", bind=True)
def export_worker(self, query_set, serializer_class):
    result = []
    for n, influencer in enumerate(query_set):
        data = serializer_class(influencer).data
        result.append(data)
        self.update_state(state='PROGRESS', meta={'percentage': round(100.0*n/count)})
    return result


@task(name="debra.dataexport_views.export_email_worker")
def export_email_worker(query_set, serializer_class, email, append_list_name=None):
    result = []
    for n, influencer in enumerate(query_set):
        data = serializer_class(influencer).data
        result.append(data)
    output_file = result_to_string(result, 'xls')
    email = EmailMessage('Data export results for '+email,
                         'please forward it to '+email,
                         'lauren@theshelf.com',
                         ["lauren@theshelf.com", "atul@theshelf.com"])
    tod = datetime.date.today()
    name = '%s_%s_bloggers_data.xls' % (append_list_name if append_list_name else '', tod.strftime('%b.%e.%Y'))
    email.attach(name, output_file, 'application/vnd.ms-excel')
    email.send()


@task(name="debra.dataexport_views.export_collection")
def export_collection(collection_id, brand_name, send_email=True):
    """
    Downloads the collection and send it as an email attachment excel file
    """
    email = 'atul@theshelf.com'
    collection = models.InfluencersGroup.objects.get(id=collection_id)
    result = []
    influencers = collection.influencers
    for n, influencer in enumerate(influencers):
        data = InfluencerExportSerializer(influencer).data
        result.append(data)
    output_file = result_to_string(result, 'xls')
    tod = datetime.date.today()
    name = '%s_%s_bloggers_data.xls' % (
        brand_name if brand_name else '', tod.strftime('%b.%e.%Y'))

    if send_email:
        email = EmailMessage(
            'Data export results for %s for collection %s' % (
                email, collection.name),
            'please forward it to '+email,
            'lauren@theshelf.com',
            ["atul@theshelf.com"]
        )
        email.attach(name, output_file, 'application/vnd.ms-excel')
        email.send()

    return output_file, name


def export_collection_view(request, collection_id):
    base_brand = request.visitor["base_brand"]

    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()

    export_collection.apply_async(
        [collection_id, base_brand.name], queue="export_collection_email")

    return HttpResponse()


def export_post_analytics_collection(collection_id, brand_name, send_email=True):
    from debra.serializers import (PostAnalyticsDataExportSerializer,
        serialize_post_analytics_data, count_totals, CampaignReportDataExportSerializer)

    serializer_class = PostAnalyticsDataExportSerializer

    collection = models.PostAnalyticsCollection.objects.prefetch_related(
        'postanalytics_set'
    ).get(id=collection_id)

    qs = collection.get_unique_post_analytics().with_counters().order_by('id')

    serialized_data = serialize_post_analytics_data(
        qs, serializer_class)
    totals_data = count_totals(qs, serializer_class)

    output_file = render_to_xls_string(
        serialized_data['data_list'],
        headers=OrderedDict(
            serializer_class.FIELDS_DATA).values(),
        footers=[totals_data['total_values'], totals_data['percentage']],
        title='Post Analytics Collection Data',
        file_type='xls')

    tod = datetime.date.today()
    name = '%s_%s_%s_post_analytics_data.xls' % (
        brand_name or '', collection.id, tod.strftime('%b.%e.%Y'))

    if send_email:
        email = EmailMessage(
            'Data export results for %s for Post Analytics Collection %s' % (
                ATUL_EMAILS.get('admin_email'), collection.name),
            'please forward it to ' + ATUL_EMAILS.get('admin_email'), 
            LAUREN_EMAILS.get('admin_email'), [ATUL_EMAILS.get('admin_email')])

        email.attach(name, output_file, 'application/vnd.ms-excel')
        email.send()

    return output_file, name


def export_campaign_report(campaign_id, brand_name, send_email=True):
    from debra.serializers import (
        serialize_post_analytics_data, count_totals, CampaignReportDataExportSerializer)

    serializer_class = CampaignReportDataExportSerializer

    campaign = models.BrandJobPost.objects.get(id=campaign_id)
    collection = campaign.post_collection

    qs = collection.get_unique_post_analytics().prefetch_related(
        'post__influencer__platform_set',
        'post__influencer__shelf_user__userprofile',
        'post__platform',
    ).with_campaign_counters().order_by('id')

    serialized_data = serialize_post_analytics_data(
        qs, serializer_class)
    totals_data = count_totals(qs, serializer_class)

    output_file = render_to_xls_string(
        serialized_data['data_list'],
        headers=OrderedDict(
            serializer_class.FIELDS_DATA).values(),
        footers=[totals_data['total_values'], totals_data['percentage']],
        title='Post Analytics Collection Data',
        file_type='xls')

    tod = datetime.date.today()
    name = '%s_%s_%s_post_analytics_data.xls' % (
        brand_name or '', collection.id, tod.strftime('%b.%e.%Y'))

    if send_email:
        email = EmailMessage(
            'Data export results for %s for Post Analytics Collection %s' % (
                ATUL_EMAILS.get('admin_email'), collection.name),
            'please forward it to ' + ATUL_EMAILS.get('admin_email'), 
            LAUREN_EMAILS.get('admin_email'), [ATUL_EMAILS.get('admin_email')])

        email.attach(name, output_file, 'application/vnd.ms-excel')
        email.send()

    return output_file, name


def export_post_analytics_collection_view(request, collection_id):
    base_brand = request.visitor["base_brand"]

    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()

    output_file, file_name = export_post_analytics_collection(
        collection_id, base_brand.name)

    mimes = {
        "csv": "application/csv",
        "xls": "application/vnd.ms-excel",
    }

    file_type = 'xls'

    resp = HttpResponse(content_type=mimes[file_type])
    resp['Content-Disposition'] = 'attachment; filename="%s"' % (file_name,)
    resp.write(output_file)
    return resp


def export_campaign_report_view(request, campaign_id):
    base_brand = request.visitor["base_brand"]

    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()

    output_file, file_name = export_campaign_report(
        campaign_id, base_brand.name)

    mimes = {
        "csv": "application/csv",
        "xls": "application/vnd.ms-excel",
    }

    file_type = 'xls'

    resp = HttpResponse(content_type=mimes[file_type])
    resp['Content-Disposition'] = 'attachment; filename="%s"' % (file_name,)
    resp.write(output_file)
    return resp


def dataexport_list(request):
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()
    context = {
        'selected_tab': 'export',
    }
    return render(request, 'pages/dataexport/list.html', context)


def dataexport_save_template(request):
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()
    query = request.POST.get("query")
    if query is None:
        return render(request, 'pages/dataexport/save_template_done.html', {"message": "No filters applied!"})
    camp_type = request.POST.get("type")
    if camp_type is None:
        return render(request, 'pages/dataexport/save_template_done.html', {"message": "Please specify campaign type"})
    description = request.POST.get("description")
    camp = models.BrandCampaign()
    camp.brand = base_brand
    camp.type_of_campaign = camp_type
    camp.start_date = None
    camp.end_date = None
    camp.description = description
    camp.filters_json = query
    camp.save()
    return render(request, 'pages/dataexport/save_template_done.html', {"message": "Saved"})


def dataexport_template(request):
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()
    plan_name = base_brand.stripe_plan
    context = {
        'selected_tab': 'save_template',
    }
    context.update(search_helpers.prepare_filter_params(context, plan_name=plan_name))
    return render(request, 'pages/dataexport/save_template.html', context)

export_types = ["top_500",
                "top_500_us",
                "top_300_uk",
                "top_250_uc_spain",
                "top_250_ny_state",
                "top_250_nyc",
                "top_250_los_angeles",
                "top_250_ca",
                "top_250_london",
                "top_250_canada",
                "top_250_australia",
                "top_250_germany",
                "top_250_brazil",
                "top_250_france",
                "top_250_italy",
                "top_250_male",
                "top_250_expensive",
                "top_250_cheap",
                "top_250_expensive",
                "top_250_classic_upscale",
                "top_250_wild_streetwear",
                "top_250_boho",
                "top_250_handmade",
                "top_250_menswear",
                ]
def get_query_for_export_type(request=None, ignore_plan=False, export_type=None):
    if ignore_plan:
        plan_name = STRIPE_PLAN_STARTUP
    else:
        try:
            export_query = json.loads(request.body) if request else {}
        except ValueError:
            export_query = {}

        export_type = export_query.get('export_type') if export_query else export_type

        #base_brand = request.visitor["base_brand"]
        #plan_name = base_brand.stripe_plan
        influencers = models.Influencer.objects.filter(show_on_search=True, profile_pic_url__isnull=False)
        influencers = influencers.exclude(source__icontains='brands')
        influencers = influencers.filter(name__isnull=False, blogname__isnull=False)
        influencers = influencers.filter(Q(email_for_advertising_or_collaborations__isnull=False) |
                                         Q(email_all_other__isnull=False) |
                                         Q(contact_form_if_no_email__isnull=False))
        influencers = influencers.exclude(blacklisted=True)
        influencers = influencers.exclude(name__iexact='problem id')
        influencers = influencers.filter(platform__activity_level__in=[models.ActivityLevel.ACTIVE_LAST_3_MONTHS,
                                                                       models.ActivityLevel.ACTIVE_LAST_MONTH,
                                                                       models.ActivityLevel.ACTIVE_LAST_WEEK,
                                                                       models.ActivityLevel.ACTIVE_LAST_DAY],
                                         platform__platform_name__in=models.Platform.BLOG_PLATFORMS)
        influencers = influencers.distinct()

    if export_type == "top_500":
        count = 500 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_500_us":
        count = 500 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='United States')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_300_uk":
        count = 300 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='United Kingdom')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_uc_spain":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='Spain')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_ny_state":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__state='New York')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_nyc":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__state='New York', demographics_locality__city='New York')
        influencers = influencers.order_by('-score_popularity_overall')
        influencers = influencers.distinct()
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_los_angeles":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__state='California', demographics_locality__city='Los Angeles')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_ca":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__state='California')
        influencers = influencers.filter(Q(demographics_location_normalized__contains='CA'))
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_london":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__city='London', demographics_locality__country='United Kingdom')
        influencers = influencers.filter(Q(demographics_location_normalized__contains='CA'))
        influencers = influencers.distinct()
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_canada":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='Canada')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_australia":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='Australia')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_germany":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='Germany')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_brazil":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='Brazil')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_france":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='France')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_italy":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(demographics_locality__country='Italy')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_eu":
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        q_list = []
        for c in all_european_countries:
            q_list.append(Q(demographics_location_normalized__icontains=c))
        influencers = influencers.filter(reduce(lambda a, b: a | b, q_list))
        influencers = influencers.order_by('-score_popularity_overall')
        influencers = influencers.distinct()
        query_set = influencers[:250]
        return query_set
    elif export_type == "top_250_south":
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:250]
        return query_set
    elif export_type == "top_250_male":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        male_query = Q(demographics_gender__in=('m', 'M', 'MF', 'FM', 'Male', 'male', ',M', 'N', 'F and M', 'M and F'))
        influencers = influencers.filter(male_query)
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_expensive":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(price_range_tag_normalized='expensive')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:280]
        return query_set
    elif export_type == "top_250_cheap":
        count = 250 + 30
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(price_range_tag_normalized='cheap')
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_classic_upscale":
        count = 250 + 30
        brand_names = ['J.Crew', 'Tory Burch', 'Kate Spade', 'Barneys', 'Vince', 'Saks Fifth Avenue']
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(brandmentions__brand__name__in=brand_names)
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_wild_streetwear":
        count = 250 + 30
        brand_names = ['Nasty Gal', 'ASOS', 'Urban Outfitters']
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(brandmentions__brand__name__in=brand_names)
        influencers = influencers.order_by('-score_popularity_overall')
        influencers = influencers.distinct()
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_boho":
        count = 250 + 30
        brand_names = ['Anthropologie']
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(brandmentions__brand__name__in=brand_names)
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_handmade":
        count = 250 + 30
        brand_names = ['Etsy']
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(brandmentions__brand__name__in=brand_names)
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "top_250_menswear":
        count = 250 + 30
        brand_names = ['Bonobos', 'Trunk Club', 'Jack Spade', 'Cool Material']
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        influencers = influencers.filter(brandmentions__brand__name__in=brand_names)
        influencers = influencers.order_by('-score_popularity_overall')
        query_set = influencers[:count]
        return query_set
    elif export_type == "custom":
        influencers = influencers.filter(score_popularity_overall__isnull=False)
        search_query = search_helpers.query_from_request(request)
        influencers = search_helpers.filter_blogger_results(search_query, influencers)[0][:1000]
        return influencers
    return models.Influencer.objects.all()[:0]


def export_request(request):
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden()

    try:
        export_query = json.loads(request.body)
    except ValueError:
        export_query = {}

    export_type = export_query.get('export_type')
    if not export_type:
        return HttpResponseBadRequest()

    task_id = export_query.get('task_id')
    if not task_id:
        task_id = request.session.get("%s_task_id" % export_type)
        task_age = request.session.get("%s_task_age" % export_type)
        if not task_age or task_age+60*60*24 < time.time():
            task_id = None
        if export_type == "custom":
            #always reset results if export is customized
            task_id = None
    if task_id:
        task = export_worker.AsyncResult(task_id)
        state = task.state
        info = task.info
        if state == "SUCCESS":
            data = {
                "state": "ready",
                "csv_link": reverse('debra.dataexport_views.export_download', args=("csv", task_id,)),
                "xls_link": reverse('debra.dataexport_views.export_download', args=("xls", task_id,)),
            }
        elif state == "FAILURE":
            print task, task.state, task.info
            data = {
                "state": "error"
            }
        elif state == "PROGRESS":
            if type(info) == dict:
                percentage = info.get("percentage", 0)
            else:
                percentage = 0
            data = {
                "state": "pending",
                "progress": percentage,
                "task_id": task_id
            }
        elif state == "PENDING":
            query_set = get_query_for_export_type(request)
            task = export_worker.apply_async([query_set, InfluencerExportSerializer], queue="celery")
            request.session["%s_task_id" % export_type] = task.id
            request.session["%s_task_age" % export_type] = time.time()
            data = {
                "state": "pending",
                "progress": 0,
                "task_id": task.id
            }
        else:
            data = {
                "state": "pending",
                "progress": 0,
                "task_id": task_id
            }
    else:
        query_set = get_query_for_export_type(request)
        task = export_worker.apply_async([query_set, InfluencerExportSerializer], queue="celery")
        request.session["%s_task_id" % export_type] = task.id
        request.session["%s_task_age" % export_type] = time.time()
        data = {
            "state": "pending",
            "progress": 0,
            "task_id": task.id
        }
    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


def export_download(request, file_type=None, task_id=None):
    mimes = {
        "csv": "application/csv",
        "xls": "application/vnd.ms-excel",
    }
    if not file_type in ("csv", "xls"):
        file_type = "csv"
    if not task_id:
        raise Http404()
    else:
        task = export_worker.AsyncResult(task_id)
        if task.ready() and task.successful():
            resp = HttpResponse(content_type=mimes[file_type])
            resp['Content-Disposition'] = 'attachment; filename="export_%s_output.%s"' % (task_id, file_type)
            resp.write(result_to_string(task.result, file_type))
            return resp
        else:
            raise Http404()


def export_paid_onetime(request):
    from debra.constants import STRIPE_TEST_SECRET_KEY, STRIPE_LIVE_SECRET_KEY, EXPORT_COSTS
    import stripe
    stripe.api_key = STRIPE_TEST_SECRET_KEY if settings.DEBUG else STRIPE_LIVE_SECRET_KEY

    try:
        data = json.loads(request.body)
    except ValueError:
        data = {}

    token = data.get('stripeToken')
    email = data.get('email')
    export_type = data.get('export_type')

    try:
        customer_id = stripe.Customer.create(
            card=token,
            description='{email} request for data export {type}'.format(
                email=email, type=export_type)
        ).id
    except Exception as e:
        print "Payment error", e
        return HttpResponseBadRequest(content=json.dumps({'error': 'Payment processing error'}))

    try:
        stripe.Charge.create(
            amount=EXPORT_COSTS.get(export_type),
            currency="usd",
            customer=customer_id,
            description='{email} request for data export {type}'.format(
                email=email, type=export_type)
        )
    except Exception as e:
        print "Payment error", e
        return HttpResponseBadRequest(content=json.dumps({'error': 'Payment processing error'}))

    if export_type != "custom":
        query = get_query_for_export_type(ignore_plan=True, export_type=export_type)
        export_email_worker.apply_async([query, InfluencerExportSerializer, email], queue="celery")
        #export_email_worker(query, InfluencerExportSerializer, email)

    return HttpResponse(content=json.dumps({'next': reverse("debra.account_views.export_ongoing")}))


def test_exports():
    email = 'atul@theshelf.com'
    for e_type in export_types:
        qs = get_query_for_export_type(request=None, ignore_plan=False, export_type=e_type)
        export_email_worker(qs, InfluencerExportSerializer, email, e_type)


def generate_campaign_xls_report(campaign_id):
    """
    All campaign reports (Overall + Posts) to single xls spreadsheet with multiple tabs.
    :param campaign_id: id of campaign, for which report is generated
    :return: StringIO object of resulting xls, could be saved to file or performed a different way
    """
    from debra.serializers import serialize_post_analytics_data, CampaignReportDataExportSerializer
    from debra.models import Platform, Influencer
    from django.db.models.aggregates import Count
    from collections import OrderedDict, defaultdict
    from debra.helpers import OrderedDefaultdict

    campaign = models.BrandJobPost.objects.get(id=campaign_id)
    collection = campaign.post_collection

    # 1. OVERALL DATA
    qs = campaign.participating_post_analytics.exclude(
        post__platform__platform_name='Instagram',
        post__post_image__isnull=True
    )

    post_type_counts = dict(
        (d['post__platform__platform_name'], d['post__platform__platform_name__count'])
        for d in qs.values('post__platform__platform_name').annotate(Count('post__platform__platform_name'))
    )

    for pl in Platform.BLOG_PLATFORMS:
        post_type_counts['Blog'] = post_type_counts.get('Blog', 0) + post_type_counts.get(pl, 0)
        try:
            del post_type_counts[pl]
        except KeyError:
            pass

    influencers_count = qs.values(
        'post__influencer'
    ).filter(
        post__influencer__isnull=False).distinct('post__influencer').count()

    # TOP INFLUENCERS DATA
    qs = qs.with_campaign_counters().order_by(
        '-agr_post_total_count',
    ).values_list(
        'post__influencer', 'agr_post_total_count',
    )
    inf_ids = []
    for inf_id, count in qs:
        if len(inf_ids) == 4:
            break
        if inf_id not in inf_ids:
            inf_ids.append(inf_id)
    infs = {
        inf.id: inf
        for inf in Influencer.objects.filter(
            id__in=inf_ids
        ).prefetch_related('platform_set')
    }
    top_infs_data = {
        'top': [infs[inf_id].feed_stamp for inf_id in inf_ids],
        'total_count': influencers_count
    }

    # POST ENGAGEMENT STATS OVERALL
    qs = campaign.participating_post_analytics.exclude(
        post__platform__platform_name='Instagram',
        post__post_image__isnull=True
    )

    qs = qs.with_campaign_counters().values(
        'post__platform__platform_name',
        'agr_post_total_count',
        'agr_post_shares_count',
        'agr_post_comments_count',
        'post__engagement_media_numlikes',
        'count_tweets',
        'count_fb_likes',
        'count_fb_shares',
        'count_fb_comments',
        'count_gplus_plusone',
        'count_pins',
        'count_clickthroughs',
        'count_impressions',
    )
    counts = OrderedDefaultdict(
        lambda: OrderedDefaultdict(lambda: OrderedDefaultdict(int)))
    post_counts = defaultdict(int)

    try:
        latest_collection_stats = campaign.post_collection.time_series.order_by('-snapshot_date')[0]
    except IndexError:
        pass
    else:
        counts['Blog']['clicks'] = {
            'count': latest_collection_stats.count_clicks,
            'title': 'Clicks'
        }
        counts['Blog']['views'] = {
            'count': latest_collection_stats.count_views,
            'title': 'Views',
        }

    for val in qs:
        pl = val['post__platform__platform_name']
        if pl in Platform.BLOG_PLATFORMS:
            pl = 'Blog'
        counts[pl]['comments']['count'] += val['agr_post_comments_count'] or 0
        counts[pl]['comments']['title'] = pl + ' Comments' if pl in ['Blog'] else 'Comments'
        if pl in ['Blog']:
            counts[pl]['tweets']['count'] += val['count_tweets'] or 0
            counts[pl]['tweets']['title'] = 'Twitter Virality'
            counts[pl]['facebook']['count'] += (val['count_fb_likes'] or 0) + (val['count_fb_shares'] or 0) + (val['count_fb_comments'] or 0)
            counts[pl]['facebook']['title'] = 'Facebook Virality'
            counts[pl]['gplus']['count'] += val['count_gplus_plusone'] or 0
            counts[pl]['gplus']['title'] = 'Google+ Virality'
            counts[pl]['pins']['count'] += val['count_pins'] or 0
            counts[pl]['pins']['title'] = 'Pinterest Virality'
        if pl not in ['Instagram', 'Blog']:
            counts[pl]['shares']['count'] += val['agr_post_shares_count'] or 0
            counts[pl]['shares']['title'] = 'Shares'
        if pl not in ['Blog']:
            counts[pl]['likes']['count'] += val['post__engagement_media_numlikes'] or 0
            counts[pl]['likes']['title'] = 'Likes'
        counts[pl]['total']['count'] += val['agr_post_total_count'] or 0
        counts[pl]['total']['title'] = 'Total'
        for n, item in enumerate(counts[pl].values(), start=1):
            item['order'] = n
        post_counts[pl] += 1

    posts_engagement_data = OrderedDict([
        ('post_counts', post_counts),
        ('counts', counts),
    ])

    # 2. POSTS DATA
    serializer_class = CampaignReportDataExportSerializer

    qs = collection.get_unique_post_analytics().prefetch_related(
        'post__influencer__platform_set',
        'post__influencer__shelf_user__userprofile',
        'post__platform',
    ).with_campaign_counters().order_by('id')

    posts_data = serialize_post_analytics_data(
        qs, serializer_class)

    # 3 BUILDING XLS

    def write_xls_row(xls_sheet, row_num, fields, style=None):
        for column, field in enumerate(fields, start=0):
            if style is None:
                xls_sheet.write(row_num, column, field)
            else:
                xls_sheet.write(row_num, column, field, style)

    output = StringIO.StringIO()

    workbook = xlwt.Workbook()
    f = xlwt.Font()
    f.bold = True
    h_style = xlwt.XFStyle()
    h_style.font = f

    cur_row = 0

    # Overall Sheet
    sheet = workbook.add_sheet('Overall')

    # Top Influencers section
    write_xls_row(sheet, cur_row, [u'Top Influencers'], h_style)
    cur_row += 1

    write_xls_row(sheet, cur_row, [
        u'Name', u'Blog Name', u'Twitter Followers Count', u'Instagram Followers Count',
        u'Facebook Followers Count', u'Pinterest Followers Count', u'Youtube Followers Count'
    ], h_style)
    cur_row += 1

    for infs in top_infs_data.get('top', []):
        write_xls_row(sheet, cur_row, [
            infs.get('user_name', u''),
            infs.get('blog_name', u''),
            infs.get('Twitter_fol', 0),
            infs.get('Instagram_fol', 0),
            infs.get('Facebook_fol', 0),
            infs.get('Pinterest_fol', 0),
            infs.get('Youtube_fol', 0),
        ])
        cur_row += 1

    # Post Engagement Stats: Overall section
    cur_row += 2

    write_xls_row(sheet, cur_row, [u'Post Engagement Stats: Overall'], h_style)
    cur_row += 1

    write_xls_row(sheet, cur_row, [
        u'Post Type', u'Count', u'# of clicks', u'# of impressions', u'# of comments', u'# of likes', u'# of shares'
    ], h_style)
    cur_row += 1

    total_clicks = 0
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_virality = posts_engagement_data.get('counts', {}).get('Blog', {}).get('total', {}).get('count', 0)

    for plat_name in posts_engagement_data.get('post_counts', {}).keys():

        blog_type = u'Blog posts' if plat_name == 'Blog' else plat_name
        posts_count = posts_engagement_data.get('post_counts', {}).get(plat_name, 0)
        clicks = posts_engagement_data.get('counts', {}).get(plat_name, {}).get('clicks', {}).get('count', 0)
        total_clicks += clicks
        views = posts_engagement_data.get('counts', {}).get(plat_name, {}).get('views', {}).get('count', 0)
        total_views += views
        comments = posts_engagement_data.get('counts', {}).get(plat_name, {}).get('comments', {}).get('count', 0)
        total_comments += comments
        likes = posts_engagement_data.get('counts', {}).get(plat_name, {}).get('likes', {}).get('count', 0)
        total_likes += likes
        shares = posts_engagement_data.get('counts', {}).get(plat_name, {}).get('shares', {}).get('count', 0)
        total_shares += shares

        write_xls_row(sheet, cur_row, [
            blog_type,
            posts_count,
            clicks,
            views,
            comments,
            likes,
            shares,
        ], h_style)
        cur_row += 1

    # Totals section
    cur_row += 2

    write_xls_row(sheet, cur_row, [u'Total Clicks:', total_clicks])
    cur_row += 1

    write_xls_row(sheet, cur_row, [u'Total Impressions:', total_views])
    cur_row += 1

    write_xls_row(sheet, cur_row, [u'Total Likes:', total_likes])
    cur_row += 1

    write_xls_row(sheet, cur_row, [u'Total Comments:', total_comments])
    cur_row += 1

    write_xls_row(sheet, cur_row, [u'Total Virality:', total_virality])
    cur_row += 1

    # Posts stats sheets
    def get_str_field(inf_dict, fieldname):
        res = inf_dict.get(fieldname, None)
        if res is None or res.lower() == u'None':
            res = u''
        return res

    def get_int_field(inf_dict, fieldname):
        try:
            res = max(0, int(inf_dict.get(fieldname, 0)))
        except (ValueError, TypeError):
            res = 0
        return res

    for plat_name in ['Blog', 'Instagram', 'Twitter', 'Facebook', 'Pinterest', 'Youtube']:

        cur_row = 0
        sheet = workbook.add_sheet(plat_name)

        if plat_name == 'Blog':
            write_xls_row(sheet,
                          cur_row,
                          [
                              u'Influencer name', u'Influencer blog url', u'Post url', u'Post title', u'Date',
                              u'Comments', u'Impressions', u'Clicks', u'Shares', u'Total'
                          ],
                          h_style)
            cur_row += 1

            for inf in posts_data.get('data_list', []):
                if inf.get('post_type', '') not in ['Instagram', 'Twitter', 'Facebook', 'Pinterest', 'Youtube']:
                    write_xls_row(sheet,
                                  cur_row,
                                  [
                                      get_str_field(inf, 'influencer_name'),
                                      get_str_field(inf, 'blog_url'),
                                      get_str_field(inf, 'post_url'),
                                      get_str_field(inf, 'post_title'),
                                      get_str_field(inf, 'post_date'),
                                      get_int_field(inf, 'post_comments'),
                                      get_int_field(inf, 'count_impressions'),
                                      get_int_field(inf, 'count_clickthroughs'),
                                      get_int_field(inf, 'post_shares'),
                                      get_int_field(inf, 'count_total'),
                                  ])
                    cur_row += 1
        else:
            write_xls_row(sheet,
                          cur_row,
                          [
                              u'Influencer name', u'Social url', u'Post url', u'Post title', u'Date',
                              u'Comments', u'Impressions', u'Clicks', u'Likes', u'Shares', u'Total'
                          ],
                          h_style)
            cur_row += 1

            for inf in posts_data.get('data_list', []):
                if inf.get('post_type', '') == plat_name and len(get_str_field(inf, 'influencer_name')) > 0:
                    write_xls_row(sheet,
                                  cur_row,
                                  [
                                      get_str_field(inf, 'influencer_name'),
                                      get_str_field(inf, 'blog_url'),
                                      get_str_field(inf, 'post_url'),
                                      get_str_field(inf, 'post_title'),
                                      get_str_field(inf, 'post_date'),
                                      get_int_field(inf, 'post_comments'),
                                      get_int_field(inf, 'count_impressions'),
                                      get_int_field(inf, 'count_clickthroughs'),
                                      get_int_field(inf, 'post_likes'),
                                      get_int_field(inf, 'post_shares'),
                                      get_int_field(inf, 'count_total'),
                                  ])
                    cur_row += 1

    workbook.save(output)

    output.seek(0)

    return output


def campaign_xls_report_file(campaign_id):
    """
    Saves generated report to .xls spreadsheet file
    :param campaign_id:
    :return:
    """
    import shutil

    xls_stream = generate_campaign_xls_report(campaign_id)

    name = 'campaign_report__%s__%s.xls' % (campaign_id, datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'))

    # saving to file
    with open(name, 'w') as fd:
        shutil.copyfileobj(xls_stream, fd)
