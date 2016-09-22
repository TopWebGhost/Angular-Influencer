__author__ = 'atulsingh'

import datetime
import json
from django.conf import settings
from django.http import Http404
from django.contrib.auth.models import Group
from debra import account_helpers
from debra.constants import INTERCOM_CUSTOM_DATA, STRIPE_AGENCY_PLANS,\
    map_plan_names, ANALYTICS_BLACKLISTED_IPS, STRIPE_PLAN_ENTERPRISE,\
    BRAND_SUSPEND_REASONS, KARSYN_USER_ID, ALLOWED_ADMIN_VIEWERS, SITE_CONFIGURATION_ID
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.db import connection
from debra.models import Brands, User
from debra.mongo_utils import get_notifications_col, notify_user
from debra.account_views import access_locked_page


class QueryCountDebugMiddleware(object):
    """
    This middleware will log the number of queries run
    and the total time taken for each request (with a
    status code of 200). It does not currently support
    multi-db setups.
    """
    def process_response(self, request, response):
        if response.status_code == 200:
            total_time = 0

            for query in connection.queries:
                query_time = query.get('time')
                if query_time is None:
                    # django-debug-toolbar monkeypatches the connection
                    # cursor wrapper and adds extra information in each
                    # item in connection.queries. The query time is stored
                    # under the key "duration" rather than "time" and is
                    # in milliseconds, not seconds.
                    query_time = query.get('duration', 0) / 1000
                total_time += float(query_time)

            print '%s queries run, total %s seconds' % (len(connection.queries), total_time)
        return response


class P3PHeaderMiddleware(object):
    def process_response(self, request, response):
        response['P3P'] = getattr(settings, 'P3P_COMPACT', None)
        return response


class LazyVisitor(object):
    def __init__(self, request):
        self.cache = {}
        self.request = request

    def __getitem__(self, key):
        if not hasattr(self, "get_%s" % key):
            return None
        if not key in self.cache:
            self.cache[key] = getattr(self, "get_%s" % key)()
        #        print key, "=", self.cache[key]
        return self.cache[key]

    @classmethod
    def flush(cls):
        #dummy, to be merged from performance_experiments
        return

    def get_is_admin(self):
        user = self["auth_user"]
        if user and user.is_superuser:
            return True
        else:
            return False

    def get_user(self):
        user = self["auth_user"]
        if user:
            try:
                profile = user.userprofile
            except:
                profile = None
        else:
            profile = None
        return profile

    def get_auth_user(self):
        if self.request.user and self.request.user.is_authenticated():
            user = User.objects.prefetch_related('userprofile__brand_privilages__brand', 'userprofile__brand_privilages', 'userprofile')
            user = user.get(id=self.request.user.id)
        else:
            user = None
        return user

    def get_dev_user(self):
        try:
            user = User.objects.get(email='pavel@theshelf.com')
        except Exception:
            user = None
        return user

    def get_brand_subscribed(self):
        admin = self["is_admin"]
        if admin:
            return True
        else:
            brand = self["base_brand"]
            if brand and brand.is_subscribed:
                return True
            else:
                return False

    def get_has_brand(self):
        if self["brand"]:
            return True
        else:
            return False

    def get_registered_as_brand(self):
        profile = self["user"]
        if profile:
            if profile.temp_brand_domain or self["brand"]:
                return True
        return False

    def get_brand(self):
        # if self.request.session.get("agency_brand"):
        #     brand = Brands.objects.get(id=self.request.session["agency_brand"])
        # else:
        #     brand = self["base_brand"]
        return self["base_brand"]

    def get_base_brand(self):
        user = self["user"]
        if user:
            return account_helpers.get_associated_brand(user)
        else:
            return None

    def get_managed_brands(self):
        # plan = self["plan_name"]
        # if plan in STRIPE_AGENCY_PLANS:
        #     managed_brands = account_helpers.get_managed_brand(self["user"])
        # else:
        #     managed_brands = []
        return []

    def get_has_influencer(self):
        influencer = self["influencer"]
        if influencer:
            return True
        else:
            return False

    def get_influencer(self):
        influencer = account_helpers.get_associated_influencer(self["user"])
        if influencer:
            return influencer
        else:
            return None

    def get_plan_name(self):
        brand = self["base_brand"]
        if brand:
            return brand.stripe_plan
        else:
            return None

    def get_plan_name_mapped(self):
        plan = self["plan_name"]
        if plan:
            return map_plan_names(plan)
        else:
            return None

    def get_intercom_data(self):
        raw = self["intercom_data_raw"]
        if raw:
            data = json.dumps(raw)
        else:
            data = "null"
        return data

    def get_intercom_data_raw(self):
        profile = self["user"]
        if profile:
            intercom_data_raw = INTERCOM_CUSTOM_DATA(profile)
        else:
            intercom_data_raw = None
        return intercom_data_raw

    def get_intercom_company_data(self):
        raw = self["intercom_company_data_raw"]
        if raw:
            data = json.dumps(raw)
        else:
            data = "null"
        return data

    def get_intercom_company_data_raw(self):
        brand = self["base_brand"]
        if brand:
            intercom_company_data_raw = brand.get_intercom_company_data()
        else:
            intercom_company_data_raw = None
        return intercom_company_data_raw

    def get_saved_competitions(self):
        brand = self["brand"]
        competitors = brand.competitors.all()
        return competitors.values_list('competitor__name', 'competitor__domain_name')

    def get_in_qa_team(self):
        user = self["auth_user"]
        return user.groups.filter(name="QA").exists()

    def get_kissmetrics_key(self):
        return settings.KISSMETRICS_APIKEY

    def get_analytics_blacklisted_ip(self):
        import re
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        for bip in ANALYTICS_BLACKLISTED_IPS:
            if re.match(bip, ip):
                return True
        return False

    def get_notifications(self):
        col = get_notifications_col()
        user = self["auth_user"]
        if user:
            ret = list(col.find({"user_id": user.id}))
            if ret:
                return ret[0]
        return {}

    def get_site_configuration_id(self):
        return SITE_CONFIGURATION_ID

    def get_campaigns(self):
        brand = self["brand"]
        base_brand = self["base_brand"]
        if brand and base_brand:
            return brand.job_posts.exclude(archived=True).filter(
                oryg_creator=base_brand
            ).order_by(
                'title'
            ).only(
                'id', 'archived', 'title'
            )

    def get_outreach_templates(self):
        ### NOT USED!!! ###
        from debra.helpers import escape_angular_interpolation_reverse
        base_brand = self["base_brand"]
        if base_brand:
            outreach = dict(base_brand.job_posts.values_list(
                'id', 'outreach_template'))
            data = {}
            for k, v in outreach.items():
                try:
                    v = escape_angular_interpolation_reverse(v)
                    data[k] = json.loads(v)
                except:
                    data[k] = {'template': v}
            return data


class CachableUserInfo(object):
    def process_request(self, request):
        request.visitor = LazyVisitor(request)
        request.brand_is_subscribed_orig = None
        request.brand_oryg_plan = None
        request.brand_override = None
        if request.visitor["auth_user"]:
            is_sub_override = request.visitor["auth_user"].username.startswith("theshelf@")
            is_sub_override &= request.visitor["auth_user"].username.endswith(".toggle")
            is_sub_override &= request.visitor["base_brand"] != None
            is_sub_override |= (request.visitor["base_brand"] is not None and request.visitor["base_brand"].flag_trial_on)
            is_sub_override |= (request.visitor["base_brand"] is not None and request.visitor["is_admin"])
            if is_sub_override:
                request.brand_is_subscribed_orig = request.visitor["base_brand"].is_subscribed
                request.brand_oryg_plan = request.visitor["base_brand"].stripe_plan
                request.brand_override = request.visitor["base_brand"].id
                request.visitor["base_brand"].is_subscribed = True
                request.visitor["base_brand"].stripe_plan = STRIPE_PLAN_ENTERPRISE
                return

        if not request.path.startswith("/mymedia") and not request.path.startswith("/static"):
            brand = request.visitor["base_brand"]
            auth_user = request.visitor["auth_user"]
            if brand and brand.flag_locked:
                allowed_urls = []
                allowed_urls.append(reverse("debra.account_views.agency"))
                allowed_urls.append(reverse("debra.account_views.selfserve"))
                allowed_urls.append(reverse("debra.account_views.home"))
                allowed_urls.append(reverse("debra.account_views.contact_us"))
                allowed_urls.append(reverse("debra.dynamicforms_views.contact_us_form"))
                allowed_urls.append(reverse("debra.account_views.our_logout"))
                allowed_urls.append(reverse('debra.account_views.registration_complete_brand'))
                if not request.path in allowed_urls:
                    return redirect(reverse('debra.account_views.registration_complete_brand'))
            if brand and brand.flag_suspended:
                if auth_user and auth_user.email.startswith("theshelf@") and auth_user.email.endswith(".toggle"):
                    return
                allowed_urls = []
                allowed_urls.append(reverse("debra.account_views.our_logout"))
                allowed_urls.append(reverse("debra.brand_account_views.change_cc"))
                allowed_urls.append(reverse("debra.payment_views.brand_payment"))
                allowed_urls.append(reverse("debra.payment_views.check_coupon"))
                if not request.path in allowed_urls:
                    return access_locked_page(request,
                        BRAND_SUSPEND_REASONS.get(
                            brand.flag_suspend_reason, None
                        ) or "Access is locked by administration.",
                        suspend_reason=brand.flag_suspend_reason
                    )
            # comment out agency-specific checks
            # if brand and brand.is_subscribed:
            #     if (brand.is_agency == True or brand.is_agency is None) and brand.stripe_plan in STRIPE_AGENCY_PLANS:
            #         allowed_urls = []
            #         url = reverse("debra.account_views.plan_changed_brand", args=(request.visitor["plan_name_mapped"],))
            #         allowed_urls.append(url)
            #         allowed_urls.append(reverse("debra.brand_account_views.mark_add_brand_to_agency"))
            #         allowed_urls.append(reverse("debra.brand_account_views.set_as_agency"))
            #         allowed_urls.append(reverse("debra.search_views.search_brand_json"))
            #         allowed_urls.append(reverse("debra.account_views.auto_buy"))
            #         allowed_urls.append(reverse("debra.account_views.our_logout"))
            #         if brand.is_agency == True:
            #             managed = request.visitor["managed_brands"]
            #             if not managed:
            #                 if not request.path in allowed_urls:
            #                     return redirect(url)
            #             elif not "agency_brand" in request.session:
            #                 request.session["agency_brand"] = managed[0].brand.id
            #                 return redirect('/')
            #         if brand.is_agency is None:
            #             url = reverse("debra.account_views.plan_changed_brand", args=(request.visitor["plan_name_mapped"],))
            #             if not request.path in allowed_urls and not request.path.startswith("/mymedia"):
            #                 return redirect(url)

    def process_response(self, request, response):
        if hasattr(request, 'brand_is_subscribed_orig') and request.brand_is_subscribed_orig != None:
            brand = Brands.objects.get(id=request.brand_override)
            brand.is_subscribed = request.brand_is_subscribed_orig
            brand.stripe_plan = request.brand_oryg_plan
            brand.save()
        return response


class AdminRestrictionForQA(object):

    def process_request(self, request):
        if request.path.startswith(reverse('admin:index')):
            qa_group = Group.objects.get(name='QA')
            # from all QA staff, only Karsyn has access to all admin pages
            # if qa_group in request.user.groups.all():
            #     nonvalidated_view_path = reverse(
            #         'upgrade_admin:influencers_blogger_signedup_initialize')
            #     if not(request.path.startswith(nonvalidated_view_path) or\
            #         request.user.id == KARSYN_USER_ID):
            #             raise Http404
            if request.user.is_authenticated():
                allow = any([
                    request.user.is_superuser,
                    request.user.email in ALLOWED_ADMIN_VIEWERS,
                    (request.path.startswith(
                        reverse('upgrade_admin:influencers_blogger_signedup_initialize')
                    ) or request.path.startswith(reverse(
                        'upgrade_admin:influencers_informations_nonvalidated'))
                    ) and qa_group in request.user.groups.all()
                ])
            else:
                # allow = request.path.startswith(
                #     reverse('upgrade_admin:user_manual_verify'))
                allow = True
            if not allow:
                raise Http404