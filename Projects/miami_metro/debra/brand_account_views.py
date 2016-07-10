# -*- coding: utf-8 -*-
import time
import json
import stripe
import datetime
import requests
import math
from lxml import etree
from django.conf import settings
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, HttpResponse, HttpResponseBadRequest, Http404
from debra.constants import STRIPE_PLAN_STARTUP, STRIPE_PLAN_CHEAP, STRIPE_PLAN_BASIC, STRIPE_COLLECTION_PLANS, STRIPE_ANALYTICS_PLANS, STRIPE_AGENCY_PLANS, STRIPE_PLAN_AGENCY_SEAT
from debra.constants import STRIPE_LIVE_PUBLISHABLE_KEY, STRIPE_TEST_PUBLISHABLE_KEY
from debra.constants import STRIPE_TEST_SECRET_KEY, STRIPE_LIVE_SECRET_KEY, map_plan_names, STRIPE_PLANS_ALL, NUM_OF_IMAGES_PER_BOX
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.urlresolvers import reverse
from django.contrib.auth import logout
from debra import models
from debra import helpers
from debra import serializers
from debra import brand_helpers
from debra import search_helpers
from debra import feeds_helpers
from debra import account_helpers
from debra import mongo_utils
from debra import constants
from debra.decorators import cached_property, timeit
from bson import json_util
from xpathscraper import utils

from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.validators import URLValidator
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.cache import get_cache

redis_cache = get_cache('redis')

stripe.api_key = STRIPE_TEST_SECRET_KEY if settings.DEBUG else STRIPE_LIVE_SECRET_KEY

# utils


def decorate_charge(charge):
    charge["created"] = datetime.datetime.fromtimestamp(
        charge["created"]).strftime("%b. %e, %Y")
    charge["amount"] = charge["amount"] / 100.0


def decorate_invoice(invoice):
    if invoice["lines"]["has_more"]:
        invoice["lines"] = invoice.lines.all(limit=1000)
    invoice["date"] = datetime.datetime.fromtimestamp(
        invoice["date"]).strftime("%b. %e, %Y")
    invoice["due_usd"] = invoice["amount_due"] / 100.0
    try:
        if invoice["discount"]["coupon"].get("amount_off") is not None:
            invoice["discount_info"] = "${:.2f}".format(
                invoice["discount"]['coupon'].get('amount_off') / 100.0)
        else:
            invoice["discount_info"] = "%i%%" % invoice[
                "discount"]["coupon"]["percent_off"]
    except:
        invoice["discount_info"] = "-"

    invoice_subtotal = 0
    changes = 0
    quantity = 0
    agency_invoice = False
    prorate = 0
    invoice_plan = None
    interval = None
    interval_count = None
    for line in invoice["lines"]["data"]:
        if line["proration"]:
            if "Remaining" in line["description"]:
                changes += 1
            prorate += line["amount"] / 100.0
            line["skip"] = True
            continue
        line["due_usd"] = line["amount"] / 100.0
        invoice_subtotal += line["due_usd"]
        if line["plan"]:
            invoice_plan = constants.PLAN_INFO[line["plan"]["id"]]['type']
            quantity = line["quantity"]
            if STRIPE_PLAN_AGENCY_SEAT in line["plan"]["id"]:
                agency_invoice = True
            line["name"] = "%i x '%s' plan" % (
                line["quantity"], invoice_plan)
            interval = line["plan"]["interval"]
            interval_count = line["plan"]["interval_count"]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  
        elif line["description"]:
            line["name"] = line["description"]
            if STRIPE_PLAN_AGENCY_SEAT in line["name"]:
                agency_invoice = True
        for plan in STRIPE_PLANS_ALL:
            if plan in line["name"]:
                line["name"] = line["name"].replace(plan, invoice_plan)
    invoice["prorate"] = prorate
    invoice["invoice_subtotal"] = invoice_subtotal
    invoice["changes"] = changes
    invoice["invoice_plan"] = invoice_plan
    invoice["quantity"] = quantity
    invoice["agency_invoice"] = agency_invoice
    invoice["interval"] = interval
    invoice["interval_count"] = interval_count


# views

def account_notifications(request):
    user = request.visitor["auth_user"]
    if not user:
        return redirect('/')
    if not request.method == "POST":
        return HttpResponseBadRequest()

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    if data.get("command") == "clear":
        mongo_utils.remove_notification(user.id, data.get("type"))

    return HttpResponse()


def update_agency_stripe(brand):
    subbrands_count = len(brand.get_managed_brands())
    if brand.is_agency:
        subbrands_count = max(0, subbrands_count - 1)

    customer = stripe.Customer.retrieve(brand.stripe_id)

    seats_subscription = None
    for subs in customer.subscriptions.data:
        if subs.plan.name == STRIPE_PLAN_AGENCY_SEAT:
            seats_subscription = subs
            break

    if seats_subscription:
        seats_subscription.quantity = subbrands_count
        seats_subscription.save()
    else:
        customer.subscriptions.create(
            plan=STRIPE_PLAN_AGENCY_SEAT, quantity=subbrands_count)

    brand.refresh_stripe_data()


def account_landing(request):
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return redirect('/')

    if request.method == 'POST':
        data = json.loads(request.body)
        if request.GET.get('load_influencers'):
            urls = set([
                group[0]
                for group in constants.GRUBER_URLINTEXT_PAT.findall(
                    data.get('urlsText')
                )
            ])

            print 'URLs found:', len(urls)
            print '\n'.join(list(urls))
            print 'tag=', data.get('tagId')

            params = dict(
                urls=urls,
                tag_id=data.get('tagId'),
                brand_id=request.visitor["base_brand"].id,
                user_id=request.visitor["auth_user"].id,
            )

            brand_helpers.handle_new_influencers.apply_async(
                kwargs=params,
                queue="post_campaign_analytics"
            )
            # brand_helpers.handle_new_influencers(**params)
        return HttpResponse()


    class StripeData(object):

        @cached_property
        @timeit
        def customer(self):
            try:
                return stripe.Customer.retrieve(base_brand.stripe_id)
            except:
                pass

        @cached_property
        @timeit
        def upcoming_invoice(self):
            try:
                upcoming = stripe.Invoice.upcoming(customer=self.customer)
                decorate_invoice(upcoming)
            except:
                upcoming = None
            return upcoming

        @cached_property
        @timeit
        def prev_invoices(self):
            try:
                prev_invoices = self.customer.invoices()
                prev_invoices["data"].sort(key=lambda x: x["date"])
                for invoices in prev_invoices["data"]:
                    decorate_invoice(invoices)
            except:
                prev_invoices = []
            return prev_invoices

        @cached_property
        @timeit
        def charges(self):
            try:
                charges = self.customer.charges()
                for charge in charges.data:
                    decorate_charge(charge)
            except:
                charges = []
            return charges


    @timeit
    def get_managed_brands():
        return []
        # for mbrand in request.visitor["base_brand"].get_managed_brands():
        #     try:
        #         pseudoinfluencer = models.Influencer.objects.get(
        #             name=mbrand.domain_name,
        #             source='brands'
        #         )
        #         mbrand.platform_blog = pseudoinfluencer.blog_url
        #         mbrand.platform_facebook = pseudoinfluencer.fb_url
        #         mbrand.platform_twitter = pseudoinfluencer.tw_url
        #         mbrand.platform_pinterest = pseudoinfluencer.pin_url
        #         mbrand.platform_instagram = pseudoinfluencer.insta_url
        #     except:
        #         pass
        #     managed_brands.append(mbrand)

    @timeit
    def get_groups():
        groups = request.visitor['brand'].influencer_groups.exclude(
            archived=True
        ).filter(
            creator_brand=base_brand,
            system_collection=False,
        ).order_by('name')

        for group in groups:
            group.imgs = group.top_influencers_profile_pics
        return groups

    @timeit
    def get_saved_queries():
        saved_queries = base_brand.saved_queries.exclude(
            name__isnull=True
        ).exclude(
            archived=True
        ).order_by('name')
        for query in saved_queries:
            if not query.result:
                query.num_results = 0
                query.imgs = []
                continue
            try:
                result = json.loads(query.result)
                xs = set()
                query.imgs = []
                for x in result['results']:
                    if not x['id'] in xs:
                        xs.add(x['id'])
                        query.imgs.append(x['pic'])
                query.imgs = query.imgs[:NUM_OF_IMAGES_PER_BOX]
            except (ValueError, KeyError):
                pass
            query.num_results = result['total']
        return saved_queries

    @timeit
    def get_post_collections():
        post_collections = base_brand.created_post_analytics_collections.filter(
            system_collection=False
        ).exclude(
            archived=True
        ).order_by('name', '-created_date')
        return post_collections

    @timeit
    def get_brand_user_profile_privilages():
        privs = base_brand.related_user_profiles.select_related(
            'user_profile__user')
        privs
        return privs

    # def get_brand_privilages():
    #     return request.visitor["user"].brand_privilages.filter(
    #         permissions=models.UserProfileBrandPrivilages.PRIVILAGE_AGENCY)

    # brand_privilages = get_brand_privilages()
    brand_user_profile_privilages = get_brand_user_profile_privilages()
    groups = get_groups()
    saved_queries = get_saved_queries()
    post_collections = get_post_collections()
    managed_brands = get_managed_brands()
    stripe_data = StripeData()

    context = {
        'stripe_key': STRIPE_TEST_PUBLISHABLE_KEY if settings.DEBUG else STRIPE_LIVE_PUBLISHABLE_KEY,
        'selected_tab': 'getting_started',
        'sub_page': 'brand_account_settings',
        'current_plan': base_brand.stripe_plan,
        # Stripe
        'customer': stripe_data.customer,
        'upcoming': stripe_data.upcoming_invoice,
        'charges': stripe_data.charges,
        'prev_invoices': stripe_data.prev_invoices,
        # DB
        'managed_brands': managed_brands,
        'brand_user_profile_privilages': brand_user_profile_privilages, 
        # 'privilages': brand_privilages,
        'groups': groups,
        'tags': [{'value': g.id, 'text': g.name} for g in groups],
        'saved_queries': saved_queries,
        'post_collections': post_collections,
    }
    return render(request, 'pages/account/landing.html', context)


def account_invoice_printable(request, invoice_id):
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return redirect('/')
    try:
        customer = stripe.Customer.retrieve(base_brand.stripe_id)
        if invoice_id == "upcoming":
            invoice = stripe.Invoice.upcoming(customer=customer)
            proforma = True
        else:
            invoice = stripe.Invoice.retrieve(invoice_id)
            proforma = False
    except:
        raise Http404()
    if invoice["customer"] != base_brand.stripe_id:
        return HttpResponseForbidden()
    decorate_invoice(invoice)
    context = {
        'invoice': invoice,
        'customer': customer,
        'proforma': proforma
    }
    return render(request, 'pages/account/invoice_printable.html', context)


def account_settings(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return redirect('/')
    context = {
        'selected_tab': 'account',
        'sub_page': 'settings',
    }
    return render(request, 'pages/account/settings.html', context)


def save_account_settings(request):
    brand = request.visitor["brand"]
    user = request.visitor["user"]
    auth_user = request.visitor["auth_user"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden('insufficient privileges')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('no data uploaded')

    form_data = data.get('data', {})
    if data.get("type") == 'personal_info':
        user.location = form_data.get('location')
        user.name = form_data.get('name')
        auth_user.email = form_data.get('email')
        user.set_setting("timezone", form_data.get('timezone'))
        user.save()
        auth_user.save()
    elif data.get("type") == 'change_password':
        if not auth_user.check_password(form_data.get('old_pw')):
            return HttpResponseForbidden('wrong current password')
        if form_data.get('new_pw2') != form_data.get('new_pw'):
            return HttpResponseForbidden('passwords are not same')
        auth_user.set_password(form_data.get('new_pw'))
        auth_user.save()
    elif data.get("type") == 'company_info':
        base_brand.name = form_data.get('company_name')
        base_brand.domain_name = utils.domain_from_url(
            form_data.get('company_url'))
        base_brand.save()
    elif data.get("type") == 'delete_account':
        auth_user.is_active = False
        prof = auth_user.userprofile
        brand = models.UserProfileBrandPrivilages.objects.filter(user_profile=prof)
        brand_names = ''
        for b in brand:
            brand_names += b.brand.domain_name
        auth_user.save()
        logout(request)
        send_mail(
            'Account delete requested from settings page',
            "User id=%i email=%s brands=%s requested account deletion" % (auth_user.id, auth_user.email, brand_names),
            'lauren@theshelf.com',
            ['lauren@theshelf.com', 'atul@theshelf.com'],
            fail_silently=True
        )
    elif data.get("type") == 'brand_options':
        from debra.admin_helpers import handle_blog_url_change, handle_social_handle_updates, update_or_create_new_platform
        brand = get_object_or_404(models.Brands, id=form_data.get('id'))
        if not brand in base_brand.get_managed_brands():
            return HttpResponseForbidden()
        brand.name = form_data.get('name')
        brand.domain_name = utils.domain_from_url(form_data.get('url'))
        brand.save()

        pseudoinfluencer, _ = models.Influencer.objects.get_or_create(
            name=brand.domain_name, source='brands')
        pseudoinfluencer.blog_url = form_data.get('blogurl')
        pseudoinfluencer.fb_url = form_data.get('facebookurl')
        pseudoinfluencer.tw_url = form_data.get('twitterurl')
        pseudoinfluencer.pin_url = form_data.get('pinteresturl')
        pseudoinfluencer.insta_url = form_data.get('instagramurl')
        pseudoinfluencer.save()
        if pseudoinfluencer.blog_url:
            handle_blog_url_change(pseudoinfluencer, pseudoinfluencer.blog_url)
        if pseudoinfluencer.fb_url:
            handle_social_handle_updates(
                pseudoinfluencer, 'fb_url', pseudoinfluencer.fb_url)
        if pseudoinfluencer.tw_url:
            handle_social_handle_updates(
                pseudoinfluencer, 'tw_url', pseudoinfluencer.tw_url)
        if pseudoinfluencer.pin_url:
            handle_social_handle_updates(
                pseudoinfluencer, 'pin_url', pseudoinfluencer.pin_url)
        if pseudoinfluencer.insta_url:
            handle_social_handle_updates(
                pseudoinfluencer, 'insta_url', pseudoinfluencer.insta_url)
        pseudoinfluencer.save()

    elif data.get("type") == "email_settings":
        user.set_setting('email_features', form_data.get('feature', False))
        user.set_setting('email_content', form_data.get('content', False))
        user.set_setting('email_changes', form_data.get('changes', False))
        user.save()
    elif data.get("type") == "outreach":
        user.set_setting('outreach_all', form_data.get('all', False))
        for key, value in form_data.iteritems():
            if key.startswith('brand_'):
                try:
                    brand_id = int(key.split('brand_')[1])
                except:
                    return HttpResponseBadRequest()
                user.set_setting('outreach_brand_%i' % brand_id, value)
        user.save()
    else:
        print data

    return HttpResponse()


def lookup_timezone(request):
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return HttpResponseForbidden('insufficient privileges')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('no data uploaded')

    rq = requests.get("http://www.earthtools.org/timezone/%f/%f" %
                      (data.get('k'), data.get('B')))
    root = etree.fromstring(str(rq.text), etree.XMLParser())
    return HttpResponse(root.xpath('//offset')[0].text)


def add_brand_to_agency(request):

    def set_privilages(to_brand):
        if request.visitor["user"].brand_privilages.filter(brand=to_brand).exists():
            # dont add twice and dont add self
            return True

        expand_privilages = (models.UserProfileBrandPrivilages.PRIVILAGE_OWNER,
                             models.UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR,
                             models.UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR_UNCONFIRMED,
                             )

        for related in brand.related_user_profiles.filter(permissions__in=expand_privilages):
            bp = models.UserProfileBrandPrivilages()
            bp.brand = to_brand
            bp.user_profile = related.user_profile
            bp.permissions = models.UserProfileBrandPrivilages.PRIVILAGE_AGENCY
            bp.save()
        return False

    brand = request.visitor["base_brand"]
    if not brand or not brand.is_subscribed or not brand.stripe_plan in STRIPE_AGENCY_PLANS:
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body)
    except ValueError:
        data = {}

    brand_name = data.get('name')
    brand_url = data.get('url')

    brand_url = utils.domain_from_url(brand_url)
    if not helpers.is_valid_hostname(brand_url):
        return HttpResponseBadRequest("Enter URL with valid hostname.")
    print "Adding ", brand_name, brand_url

    to_brand = models.Brands.objects.filter(domain_name=brand_url)
    print to_brand
    if len(to_brand) > 0:
        print "Found single brand"
        to_brand = to_brand[0]
        if set_privilages(to_brand):
            return HttpResponseBadRequest("You can't add same brand twice and use your brand as agency sub-brand..")
        account_helpers.intercom_track_event(request, "brand-add-subbrand", {
            'brand': brand.domain_name,
            'subbrand': to_brand.domain_name,
        })
        request.session["agency_brand"] = to_brand.id
    elif not to_brand:
        print "Requested new brand"
        to_brand = models.Brands.objects.create(
            domain_name=brand_url, name=brand_name)
        to_brand.save()
        brand_helpers.create_profile_for_brand(to_brand)
        set_privilages(to_brand)
        account_helpers.intercom_track_event(request, "brand-add-subbrand", {
            'brand': brand.domain_name,
            'subbrand': to_brand.domain_name,
        })
        request.session["agency_brand"] = to_brand.id
    else:
        #@todo handle multiple brands
        pass

    try:
        update_agency_stripe(brand)
    except:
        return HttpResponseBadRequest("Something went wrong. Probably, you're trying to use Stripe production mode through test mode user.")

    return HttpResponse()


def del_brand_from_agency(request):
    brand = request.visitor["base_brand"]
    if not brand or not brand.is_subscribed or not brand.stripe_plan in STRIPE_AGENCY_PLANS:
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body)
    except ValueError:
        data = {}

    brand_name = data.get('name')
    print "removing ", brand_name

    to_brands = models.Brands.objects.filter(name=brand_name)
    for to_brand in to_brands:
        remove_privilages = (models.UserProfileBrandPrivilages.PRIVILAGE_OWNER,
                             models.UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR,
                             models.UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR_UNCONFIRMED,
                             )
        profiles = [x.user_profile.id for x in brand.related_user_profiles.filter(
            permissions__in=remove_privilages).only('user_profile__id')]
        print profiles
        print to_brand.related_user_profiles.filter(user_profile__id__in=profiles, permissions=models.UserProfileBrandPrivilages.PRIVILAGE_AGENCY)
        to_brand.related_user_profiles.filter(
            user_profile__in=profiles, permissions=models.UserProfileBrandPrivilages.PRIVILAGE_AGENCY).delete()
        if "agency_brand" in request.session and request.session["agency_brand"] == to_brand.id:
            all_managed = request.visitor["managed_brands"]
            for managed in all_managed:
                if managed.id != to_brand.id:
                    request.session["agency_brand"] = managed.brand.id
                    break
        account_helpers.intercom_track_event(request, "brand-remove-subbrand", {
            'brand': brand.domain_name,
            'subbrand': to_brand.domain_name,
        })

    try:
        update_agency_stripe(brand)
    except:
        return HttpResponseBadRequest("Something went wrong. Probably, you're trying to use Stripe production mode through test mode user.")

    return HttpResponse()


def set_agency_main_brand(request, id):
    to_brand = request.visitor["user"].brand_privilages.filter(brand__id=id)
    if to_brand and to_brand != request.visitor["base_brand"] and request.visitor["base_brand"].is_agency:
        to_brand = to_brand[0]
        request.session["agency_brand"] = to_brand.brand.id
    return redirect('/')


def change_cc(request):
    brand = request.visitor["base_brand"]
    if not brand or not brand.is_subscribed:
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    token = data.get('stripeToken')

    try:
        customer = stripe.Customer.retrieve(brand.stripe_id)
    except:
        return HttpResponseBadRequest(content=json.dumps({'error': str(e)}))

    try:
        new_card = customer.cards.create(card=token)
    except Exception as e:
        return HttpResponseBadRequest(content=json.dumps({'error': str(e)}))

    for card in customer.cards.data:
        if card.id == customer.default_card:
            card.delete()
            break

    customer.default_card = new_card.id
    customer.save()

    return HttpResponse()


def set_as_agency(request):
    brand = request.visitor["base_brand"]
    if not brand or not brand.is_subscribed:
        return HttpResponseForbidden()

    if brand.is_agency is None:
        brand.is_agency = request.POST.get('is_agency', False)
        brand.save()
        update_agency_stripe(brand)

    return redirect('debra.brand_account_views.account_landing')


def mark_add_brand_to_agency(request):
    brand = request.visitor["base_brand"]
    if not brand or not brand.is_subscribed:
        return HttpResponseForbidden()
    brand.is_agency = True
    brand.save()
    return add_brand_to_agency(request)


def send_latest_invoice_to_email(request):
    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed:
        return redirect('/')
    customer = stripe.Customer.retrieve(base_brand.stripe_id)
    try:
        upcoming = stripe.Invoice.upcoming(customer=customer)
    except:
        return HttpResponseBadRequest()

    balance = 0
    out = []
    now = datetime.datetime.now()
    for invoice in upcoming.lines.data:
        dt = datetime.datetime.fromtimestamp(invoice["period"]["end"])
        total = invoice["amount"] / 100.0
        if total > 0 and dt > now:
            out.append({"invoice": invoice, "dt": dt, "total": total})
    if not out:
        return HttpResponseBadRequest()
    latest = out[0]

    subject = 'Invoice'
    from_email = 'lauren@theshelf.com'
    to = request.visitor["auth_user"].email

    html_content = render_to_string('pages/account/invoice_email.html', {
        'customer': customer,
        'data': latest
    })
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    return HttpResponse()


def brand_preferences(request):
    brand = request.visitor["base_brand"]
    if not brand or not brand.is_subscribed:
        return HttpResponseForbidden()

    if request.method == "GET":
        data = {
            'campaigns_enabled': brand.flag_campaigns_enabled or False,
            'profile_enabled': brand.flag_profile_enabled or False,
            'non_campaign_messaging_enabled': brand.flag_non_campaign_messaging_enabled or False,
            'skipping_stages_enabled': brand.flag_skipping_stages_enabled or False,
        }
        data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            for key, value in data.items():
                brand._set_flag(key, value)
            brand.save()
        except ValueError:
            return HttpResponseBadRequest()
        return HttpResponse({}, content_type="application/json")
    else:
        return HttpResponseBadRequest()
