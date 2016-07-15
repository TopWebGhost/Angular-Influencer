"""
a custom backend to use for django registration. We subclass the default as all we want to override
is the post activation redirect method
"""
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from registration.backends.default import DefaultBackend
from django.core.urlresolvers import reverse
from debra.models import Brands, Influencer
from django.core.mail import mail_admins
from debra import brand_helpers, account_helpers
from debra import helpers
from xpathscraper import utils
import pdb
import datetime

import logging
log = logging.getLogger(__name__)


def post_activation(request, user):
    print "OK, here: in post_activation_redirect for %r " % user
    user_prof = user.userprofile
    buy_after = False
    if request:
        if "buy_after" in request.session and request.session["buy_after"]:
            buy_after = True


    if user_prof.temp_brand_domain:
        account_helpers.intercom_track_event(request, "brand-email-verified", {
            'email': user.email,
            'brand_url': user_prof.temp_brand_domain,
            'date_joined': datetime.datetime.now().strftime("%c")
        }, user=user)

        print "ok, we are brand related"
        ####This handles user's who claim to be working for a given brand
        brand = Brands.objects.filter(domain_name__iexact=user_prof.temp_brand_domain)
        if not brand:
            log.error("Connecting user %s to non existing brand %s !" % (user, user_prof.temp_brand_domain))
        else:
            brand = brand[0]

        ## if user's email belongs to the domain name of the brand, then only we allow this association
        if brand and helpers.check_if_email_matches_domain(user.email, brand.domain_name):
            brand_helpers.sanity_checks(brand)
            user_prof.temp_brand_domain = None
            user_prof.save()

            brand_helpers.connect_user_to_brand(brand, user_prof)
            account_helpers.intercom_track_event(None, "brand-ownership-verified", {
                'email': user.email,
                'brand_url': brand.domain_name,
                'manual': False,
                'success': True,
            }, user)

            # change it to celery before push to production
            if not settings.DEBUG:
                account_helpers.notify_admins_about_brand_email_match.apply_async([user_prof, brand], queue="celery")
                #account_helpers.notify_admins_about_brand_email_match(user_prof, brand)
            if request:
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                if buy_after:
                    return reverse("debra.account_views.auto_buy"), (), {}
                return reverse("debra.account_views.email_verified_brand"), (), {}
        else:
            reason = "%s doesn't exist" % user_prof.temp_brand_domain if not brand else "domain mismatch between %s and %s" % (user.email, brand.domain_name)

            # now notify admins so that they can reach out to the brand user
            account_helpers.notify_admins_about_brand_email_mismatch.apply_async([user_prof], queue="celery")

            pass
            ## basically login as the user with no brand associated with you

    if user_prof.blog_name and user_prof.blog_page:
        account_helpers.intercom_track_event(request, "blogger-email-verified", {
            'email': user.email,
            'blog_url': user_prof.blog_page,
            'date_joined': datetime.datetime.now().strftime("%c")
        }, user=user)
        # intercom_user = user_prof.get
        user_prof.update_intercom()
        print "[BLOGGER: EMAIL VERIFIED] %r %r" % (user_prof, user_prof.blog_page)


    if request:
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        if buy_after:
            return reverse("debra.account_views.auto_buy"), (), {}
        print "ok, redirecting to %s " % user.userprofile.after_login_url
        return user.userprofile.after_login_url, (), {}


class ShelfBackend(DefaultBackend):
    def post_activation_redirect(self, request, user):
        return post_activation(request, user)
