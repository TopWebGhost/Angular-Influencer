import time
import logging
import traceback
import datetime
import json
import urllib
import itertools
import urlparse

import requests
import bleach
import intercom
from collections import defaultdict
from lxml import etree
from mixpanel import Mixpanel

from celery.decorators import task

from django.template.loader import render_to_string
from django.db.models import Q
from django.contrib.sites.models import Site
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.conf import settings
from django.core.mail import send_mail, mail_admins

from settings import DEBUG_INTERCOM_APPID, DEBUG_INTERCOM_APIKEY, DEBUG
from settings import PRODUCTION_INTERCOM_APPID, PRODUCTION_INTERCOM_APIKEY

from debra import constants
from debra import brand_helpers
from debra.clickmeter import *
from xpathscraper import utils

mp = Mixpanel(settings.MIXPANEL_TOKEN)
log = logging.getLogger('debra.account_helpers')
clickmeter_api = ClickMeterApi()


def internal_user(user):
    """
    A helper method to see if the user is internal to our company.
    """
    if user.is_staff or user.is_superuser or '@theshelf.com' in user.email.lower():
        return True
    return False


@task(name="debra.account_helpers.send_msg_to_slack")
def send_msg_to_slack(channel, msg):
    """
    Internal method to send a custom message to a given Slack channel.
    """
    slackbot_url = constants.SLACK_POST_URL + '&channel=%23' + channel
    resp = requests.post(slackbot_url, data=msg)
    print("SLACK: GOT RESPONSE: status = [%r] content = [%r]" % (resp, resp.content))
    return resp

def check_user_prof_influencer_connectivity(user_profile_id):
    from debra.helpers import send_admin_email_via_mailsnake
    from debra.models import UserProfile
    prof = UserProfile.objects.get(id=user_profile_id)
    if not prof.influencer:
        send_admin_email_via_mailsnake("No influencer found for %s" % prof, "Blog %s User %s Email %s " % (prof.blog_page, prof.user, prof.user.email))
    else:
        inf = prof.influencer
        if not inf.shelf_user:
            send_admin_email_via_mailsnake("No shelf_user found for %s" % inf.id, "Influencer %s; User_profile_id %s" % (inf, user_profile_id))


def find_and_connect_user_to_influencer(user_prof, to_save=True, **kwargs):
    """
    This method connects a userprofile with an influencer object and updates this data in intercom.
    Sending an email to admins in case of errors.
    *param: user_profile
    *return: None
    """
    from debra.models import Influencer
    from debra.helpers import create_influencer_and_blog_platform, send_admin_email_via_mailsnake
    from platformdatafetcher import platformutils, postprocessing

    blog_url = user_prof.blog_page
    influencer = create_influencer_and_blog_platform(blog_url, 'blogger_signup', to_save, False)
    log.info("Found %r possible influencer for profile [%s %s]" % (influencer, user_prof.user, user_prof.blog_page))

    if not influencer:
        log.info("No influencer found for User_prof_id: %s" % (user_prof.id,))
        send_admin_email_via_mailsnake("No influencer found for user", "User_prof_id: %s" % (user_prof.id,))
        user_prof.error_when_connecting_to_influencer = "NO INFLUENCERS"
    else:
        log.info("Found %s influencer for signed up user %s" % (influencer, user_prof))
        influencer.name = user_prof.name
        influencer.email_for_advertising_or_collaborations = user_prof.user.email
        influencer.email = user_prof.user.email
        user_prof.influencer = influencer
        influencer.shelf_user = user_prof.user
        influencer.append_source('blogger_signup')
        log.info("Done connecting User: [%s, %s] with Influencer: [%s, %s]" % (user_prof.blog_page,
                                                                               user_prof.user.email,
                                                                               influencer.email_for_advertising_or_collaborations,
                                                                               influencer.blog_url))

    if to_save:
        user_prof.save()
        if influencer:
            influencer.save()
            user_prof.update_intercom()
            # if influencer is showing on search, their profile must be ok, so invite them
            if influencer.show_on_search and not influencer.ready_to_invite:
                influencer.ready_to_invite = True
                influencer.save()
                user_prof.update_intercom()
            # if they have been already qa-ed, invite them
            elif influencer.validated_on and 'info' in influencer.validated_on and not influencer.ready_to_invite:
                influencer.ready_to_invite = True
                influencer.save()
                user_prof.update_intercom()
            # now, if this influencer is not validated or not showing on search
            else:
                # issue the complete processing
                postprocessing.process_new_influencer_sequentially(influencer.id, assume_blog=True)

        check_user_prof_influencer_connectivity(user_prof.id)


@task(name='debra.account_helpers.bloggers_signup_postprocess', ignore_result=True)
def bloggers_signup_postprocess(user_profile, distinct_id=None, **kwargs):
    from debra.models import InfluencersGroup, UserProfile

    if user_profile.get_setting('influenity_signup'):
        print "[bloggers_signup_postprocess] handling influenity_signup for {}".format(
            user_profile.id)
        user_profile.blog_verified = True
        user_profile.save()
        # only issue this if influencer not already attached to the profile
        if not user_profile.influencer:
            print "[bloggers_signup_postprocess] 'create_and_connect_user_to_influencer' call"
            create_and_connect_user_to_influencer(user_profile.id)
        else:
            print "[bloggers_signup_postprocess] 'create_and_connect_user_to_influencer' call SKIPPED as influencer already exists"
        # refresh
        print "[bloggers_signup_postprocess] refreshing user profile"
        user_profile = UserProfile.objects.get(id=user_profile.id)
        if user_profile.get_setting('influenity_signup') and user_profile.influencer:
            print "[bloggers_signup_postprocess] getting tag {}".format(
                user_profile.get_setting('influenity_tag_id'))
            tag = InfluencersGroup.objects.get(
                id=user_profile.get_setting('influenity_tag_id'))
            print "[bloggers_signup_postprocess] adding to tag {}".format(tag)
            tag.add_influencer(user_profile.influencer)
    
    user_profile.update_intercom()
    #site = Site.objects.get(id=settings.SITE_ID)
    print "[bloggers_signup_postprocess] %s signed up distinct_id %s" % (user_profile, distinct_id)

    # there will be only one registration profile, but lets process "all"
    # for regprof in user_profile.user.registrationprofile_set.all():
    #     # regprof.send_activation_email(site)
    #     ctx_dict = {'activation_key': regprof.activation_key,
    #                 'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
    #                 'site': site}
    #     message = render_to_string('registration/activation_email.txt',
    #                                ctx_dict)
    #     intercom.MessageThread.create(email=user_profile.user.email, body=message)

    intercom_track_event(None, 'blogger-signed-up', {'blog_url': user_profile.blog_page}, user_profile.user)


@task(name='debra.account_helpers.brands_signup_postprocess', ignore_result=True)
def brands_signup_postprocess(user_profile, form, distinct_id=None):
    #site = Site.objects.get(id=settings.SITE_ID)

    from debra.models import Brands

    domain_name = utils.domain_from_url(form.cleaned_data['brand_url'])
    print "DOMAIN_NAME: %s" % domain_name

    brands = Brands.objects.filter(domain_name=domain_name)
    if brands.exists():
        brand = brands[0]
        created = False
    else:
        brand = Brands.objects.create(domain_name=domain_name)
        created = True
    print "created: %s " % created
    print "brand: %s" % brand

    user_profile.temp_brand_domain = domain_name
    user_profile.save()
    user_profile.create_in_intercom()

    if form.data.get('from_admin') == 'true':
        user_profile.intercom_tag_add('dont-send-intro-email')
        user_profile.intercom_tag_add('customer_ignore')

    if form.referer_tag:
        user_profile.intercom_tag_add(form.referer_tag)
    # referer_page = urlparse.urlparse(form.referer).path.strip('/').split('/')[0]
    # print '* REFERER:', referer_page
    # try:
    #     tag = {
    #         '': 'home',
    #         'blogger-outreach': 'newbie',
    #         'influencer-marketing': 'expert',
    #         'agencies': 'agency',
    #         'blogger-campaign-services': 'services',
    #         'coverage': 'coverage',
    #         'the-blog': 'blog',
    #         'blogger-roundups': 'roundups',
    #     }[referer_page]
    # except KeyError:
    #     pass
    # else:
    #     user_profile.intercom_tag_add(tag)

    # if this is a new brand we know the user signing up is the brand manager. Otherwise, users have to claim the brand from us
    if created:
        brand.name = form.cleaned_data['brand_name']
        brand.save()
        brand_helpers.create_profile_for_brand(brand)

    intercom_track_event(None,
                       'brand-signed-up',
                       {'user_email': user_profile.user.email, 'brand_url': domain_name},
                       user_profile.user)



def set_alias_mixpanel(distinct_id, user_profile, brand=None):
    mp.alias(user_profile.user.email, distinct_id)
    mp.people_set_once(user_profile.user.email, {
        "$name": user_profile.name,
        "$email": user_profile.user.email,
        "$created": json.dumps(user_profile.user.date_joined.isoformat()),
        "is_brand": True if brand else False,
        "is_blogger": True if user_profile.blog_page else False,
        "brand": brand.domain_name if brand else None,
        "blog_url": user_profile.blog_page,
        "contacted_by": "none",
    })


def get_distinct_id_mixpanel(request):
    """
    fetches the distinct_id from the cookie set by mixpanel library
    """
    mp_cookie_name = 'mp_%s_mixpanel' % settings.MIXPANEL_TOKEN
    mp_cookie = request.COOKIES.get(mp_cookie_name, None)
    distinct_id = None
    if mp_cookie:
        import ast
        mp_cookie = urllib.unquote(mp_cookie)
        final_cookie = ast.literal_eval(mp_cookie)
        distinct_id = final_cookie.get('distinct_id', None)
    return distinct_id


def resend_activation_email(user):
    """
    Currently if someone wants re-activation email, they will be sent by our platform AND-NOT-INTERCOM.
    TODO: we should integrate them. Second, Intercom takes a long time to send those emails.
    """
    site = Site.objects.get(id=settings.SITE_ID)

    for profile in user.registrationprofile_set.all():
        profile.send_activation_email(site)


@task(name='debra.account_helpers.send_intercom_info', ignore_result=True)
def send_intercom_info(email, user_id, event_name, event_datetime, metadata, from_production):
    payload = {
        'event_name': event_name,
        'created': event_datetime,
        'email': email,
        'user_id': user_id,
        'metadata': {
            "search_query": json.dumps(metadata)
        }
    }
    headers = {'Content-Type': 'application/json'}
    if from_production:
        INTERCOM_APPID = PRODUCTION_INTERCOM_APPID
        INTERCOM_APIKEY = PRODUCTION_INTERCOM_APIKEY
    else:
        INTERCOM_APPID = DEBUG_INTERCOM_APPID
        INTERCOM_APIKEY = DEBUG_INTERCOM_APIKEY
    try:
        resp = requests.post("https://api.intercom.io/events", auth=(INTERCOM_APPID, INTERCOM_APIKEY), headers=headers, data=json.dumps(payload))
        if resp.status_code != 202:
            log.error("Intercom responded with non 202 response %s for  %s %s %s" % (resp.text, user_id, event_name, metadata))
    except Exception as e:
        log.exception("Exception happened while sending intercom event with %s %s %s" % (user_id, event_name, metadata))

def intercom_track_event(request, event_name, metadata, user=None):
    if not user:
        if not request or not request.user.is_authenticated():
            return
        else:
            user = request.user

    dt = int(datetime.datetime.now().strftime("%s"))
    from_production = not DEBUG
    print("event_name: [%s] dt: [%s] metadat: [%s]" % (event_name, dt, metadata))
    if DEBUG:
        send_intercom_info(user.email, user.id, event_name, dt, metadata, from_production)
    else:
        send_intercom_info.apply_async([user.email, user.id, event_name, dt, metadata, from_production], queue="celery")
    #send_intercom_info(user.email, user.id, event_name, dt, metadata, from_production)


@task(name='debra.account_helpers.create_and_connect_user_to_influencer', ignore_result=True)
def create_and_connect_user_to_influencer(userprofile_id, **kwargs):
    from debra.models import UserProfile
    from platformdatafetcher import postprocessing
    userprofile = UserProfile.objects.get(id=userprofile_id)
    find_and_connect_user_to_influencer(userprofile)

    # make sure the user's signed up email is present in Influencer's all emails
    updated_up = UserProfile.objects.get(id=userprofile.id)
    print 'Influencer connected to the userprofile: %r' % updated_up.influencer

    # process tasks for this influencer without using the normal flow
    if updated_up.influencer and not (updated_up.influencer.is_qad() or updated_up.influencer.show_on_search):
        postprocessing.process_new_influencer_sequentially.apply_async(
            [updated_up.influencer.id], queue='new_influencer')


def verify_blog_ownership_inner(url):
    """
    Takes blog url, returns True when badge found on page under given url or under its i/frames
    """

    badges_xpath = "//img[contains(@src,'https://s3.amazonaws.com/theshelfnetwork/badges/')]"
    try:
        page = requests.get(url).text
        root = etree.fromstring(page, etree.HTMLParser())
    except:
        return False
    if root.xpath(badges_xpath):
        return True
    # try with frames and iframes
    frames = root.xpath("//frame[@src]")
    frames.extend(root.xpath("//iframe[@src]"))
    for frame in frames:
        try:
            page = requests.get(frame.attrib["src"]).text
            root = etree.fromstring(page, etree.HTMLParser())
        except:
            continue
        if root.xpath(badges_xpath):
            return True

    ## TODO
    ## if these other checks fail, we can use these highly restrictive but 100% accurate tests
    ## a) if email is from the domain of the blog (e.g.: blog is http://pennypincherfashion.com and email is penny@pennypincherfashion.com)
    ## b) if we find the email of user in the source of the blog or blog/contact/ or blog/about-us/ pages
    return False


@task(name='debra.account_helpers.verify_blog_ownership', ignore_result=True)
def verify_blog_ownership(userprofile_id):
    from debra.models import UserProfile

    userprofile = UserProfile.objects.get(id=userprofile_id)
    user = userprofile.user
    blog_url = userprofile.blog_page

    print "user %s requested badge verification" % user

    verified = verify_blog_ownership_inner(userprofile.blog_page)

    if verified:
        print "verified!"
        userprofile.blog_verified = True
        userprofile.save()
        create_and_connect_user_to_influencer(userprofile.id)
    else:
        pass

    intercom_track_event(None, "blogger-blog-verification", {
        'email': user.email,
        'blog_url': blog_url,
        'success': verified
    }, user)



@task(name='debra.account_helpers.verify_brand_membership', ignore_result=True)
def verify_brand_membership(userprofile_id):
    import hashlib
    from debra.models import UserProfile, Brands


    userprofile = UserProfile.objects.get(id=userprofile_id)
    user = userprofile.user

    brand = get_object_or_404(Brands, domain_name__iexact=userprofile.temp_brand_domain)

    hex_string = hashlib.md5(str(userprofile.id)).hexdigest()

    fail = False

    print "user", user, "requested brand membership verification"
    try:
        page = requests.get("http://"+userprofile.temp_brand_domain).text
        root = etree.fromstring(page, etree.HTMLParser())
    except Exception as e:
        root = None
    if root:
        meta_shelfid = root.xpath("//meta[@theshelfid='%s']" % hex_string)
        if meta_shelfid:
            print "verified!"
            brand_helpers.sanity_checks(brand)
            userprofile.temp_brand_domain = None
            userprofile.save()

            brand_helpers.connect_user_to_brand(brand, userprofile)

            send_mail('Congrats, your brand membership was verified', "Hi %s,\n We have successfully verified you as the member of your brand %s.\n\n--Thanks,\nShelf Team" % (userprofile.name, brand.name), 'lauren@theshelf.com',[user.email, 'lauren@theshelf.com', 'atul@theshelf.com'], fail_silently=True)
        else:
            print "not verified"
            fail = True
    else:
        fail = True

    intercom_track_event(None, "brand-ownership-verified", {
        'email': user.email,
        'brand_url': brand.domain_name,
        'manual': False,
        'success': not fail
    }, user)

    if fail:
        send_mail("Ooops! We didn't find verifiable tag on your brand page", "Hi %s,\n Since we didn't find the meta tag with value %s, we couldn't automatically verify you as the owner/member of your brand %s. If you think this was a mistake, please respond to this email and we'll look into it.\n\nThanks,\nShelf Team" % (userprofile.name, hex_string, brand.name), 'lauren@theshelf.com',[user.email, 'laurenj@theshelf.com', 'atul@theshelf.com'], fail_silently=True)


def suspend_brands_with_canceled_plan(customer_id, suspend):
    """
    Suspends all brands with given customer_id with 'stripe_plan_deleted' reason
    """
    from debra.models import Brands
    for brand in Brands.objects.filter(stripe_id=customer_id):
        brand.flag_suspended = suspend
        brand.flag_suspend_reason = "stripe_plan_deleted" if suspend else None
        brand.save()


def get_associated_brand(user):
    from debra.models import UserProfile, UserProfileBrandPrivilages
    if isinstance(user, User):
        if not user.is_authenticated():
            return None
        user = user.userprofile
    if isinstance(user, UserProfile):
        brand = None
        if user.brand:
            brand = user.brand
        else:
            associated_privilages = (UserProfileBrandPrivilages.PRIVILAGE_OWNER,
                                     UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR,
                                     UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR_UNCONFIRMED,
                                    )
            privs = user.brand_privilages.filter(
                permissions__in=associated_privilages
            ).prefetch_related('brand__userprofile__user')
            if privs:
                brand = privs[0].brand
        if brand:
            return brand
    return None


def get_managed_brand(user):
    from debra.models import UserProfile, UserProfileBrandPrivilages
    if isinstance(user, User):
        if not user.is_authenticated():
            return []
        user = user.userprofile
    if isinstance(user, UserProfile):
        privs = []
        for brand in user.brand_privilages.all():
            if brand.permissions == UserProfileBrandPrivilages.PRIVILAGE_AGENCY:
                privs.append(brand)
        if privs:
            return privs
        if user.brand:
            return [user.brand]
    return []


def get_associated_influencer(user):
    from debra.models import UserProfile, Influencer
    if isinstance(user, User):
        if not user.is_authenticated():
            return None
        user = user.userprofile
    if isinstance(user, UserProfile):
        inf = Influencer.objects.filter(shelf_user=user.user)
        if inf:
            return inf[0]
        if user.influencer:
            return user.influencer
    return None


@task(name='debra.account_helpers.notify_admins_about_brand_email_mismatch', ignore_result=True)
def notify_admins_about_brand_email_mismatch(user_prof, verified_email=True):
    try:
        send_mail("Error: Brand signed up but email-domain mismatch (%r:%r) found!" % (user_prof.temp_brand_domain, user_prof.user.email),
                  "We couldn't automatically verify %s as the owner/member of brand %s.\nSo, first verify and then go to admin panel and validate them. Email Verified? = %s" %
                  (user_prof.user.email,
                   user_prof.temp_brand_domain, verified_email),
                  'lauren@theshelf.com',
                  ['lauren@theshelf.com', 'atul@theshelf.com', 'anjali@theshelf.com'],
                  fail_silently=False)
    except:
        # retry in 10 minutes
        notify_admins_about_brand_email_mismatch.apply_async([user_prof], queue='celery', countdown=10*60)


@task(name='debra.account_helpers.notify_admins_about_brand_email_match', ignore_result=True)
def notify_admins_about_brand_email_match(user_prof, brand, verified_email=True):
    try:
        send_mail("Success: Brand signed up and email-domain (%r:%r)matched!" % (user_prof.temp_brand_domain, user_prof.user.email),
                  "New brand member registered with email %s for brand %s. Email Verified? = %s" %
                  (user_prof.user.email,
                   brand.name, verified_email),
                  'lauren@theshelf.com',
                  ['lauren@theshelf.com', 'atul@theshelf.com', 'anjali@theshelf.com',],
                  fail_silently=False)
    except:
        # retry in 10 minutes
        notify_admins_about_brand_email_match.apply_async([user_prof, brand], queue='celery', countdown=10*60)


@task(name='debra.account_helpers.automatic_blog_verify', ignore_result=True)
def automatic_blog_verify():
    """
    Here, we automatically set blog_verified = True for users who signed up 2 days ago and haven't yet verified their blog.
    After this step, we set up the influencer mapping.
    Then, QA will manually go over these influencers and fill up their info.
    """
    from debra.models import User, UserProfile
    tod = datetime.date.today()
    date_joined = tod - datetime.timedelta(days=2)
    users = User.objects.filter(date_joined__contains=date_joined, is_active=True, userprofile__blog_page__isnull=False)
    users = users.exclude(userprofile__blog_verified=True).exclude(email__contains='toggle')
    log.info("%d users do not have blog verified set yet, so we're going to set it automatically" % users.count())
    profs = UserProfile.objects.filter(user__in=users)
    for prof in profs:
        prof.blog_verified = True
        prof.save()
        create_and_connect_user_to_influencer(prof.id)
        # send intercom event
        intercom_track_event(None, "blogger-blog-verification", {
            'email': prof.user.email,
            'blog_url': prof.blog_page,
            'success': True
        }, prof.user)

    # now send a report to the admins about how many valid users don't have an influencer
    start = datetime.date(2014, 7, 31)
    profs = UserProfile.objects.filter(blog_verified=True, influencer__isnull=True).exclude(user__email__contains='toggle')
    profs = profs.filter(user__date_joined__gte=start)
    log.info("%d profiles don't have an influencer attached" % profs.count())
    message_lines = ['{} ({}) - {}'.format(prof.pk, prof.user.email, prof.blog_page)
                     for prof in profs]
    mail_admins("No influencer attached for these users", message_lines if message_lines else "Nothing found---good!")


def get_bleached_template(template):
    tags = [
        'a',
        'abbr',
        'acronym',
        'b',
        'blockquote',
        'code',
        'em',
        'i',
        'u',
        'li',
        'ol',
        'strong',
        'font',
        'ul',
        'div',
        'span',
        'strike',
        'p',
        'br',
    ]

    tags_without_styling = set(['p', 'span', 'div'])
    tags_with_styling = set(tags) - tags_without_styling

    attrs = {tag: ['size', 'href'] for tag in tags_without_styling}
    attrs.update({
        tag: ['style', 'size', 'href'] for tag in tags_with_styling})

    styles = ['text-align', 'font-weight', 'font-size', 'color', 'margin', \
        'padding', 'border']

    template = bleach.clean(template, tags, attrs, styles)

    return template


@task(name='debra.account_helpers.influencer_tracking_verification', ignore_result=True)
def influencer_tracking_verification(pa_id, attempts=3, delay=30):
    from urllib2 import unquote
    from debra.models import Contract, PostAnalytics
    from debra.helpers import send_admin_email_via_mailsnake
    from xpathscraper import xbrowser

    # contract = get_object_or_404(Contract, id=contract_id)
    pa = get_object_or_404(PostAnalytics, id=pa_id)
    contract = pa.contract

    pa.tracking_status = pa.TRACKING_STATUS_VERIFYING
    pa.save()

    def visit_page(page_url):
        log.info('* Opening {} with Selenium...'.format(page_url))
        with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
            xb.driver.set_page_load_timeout(60)
            xb.driver.set_script_timeout(60)
            xb.driver.implicitly_wait(10)
            try:
                xb.load_url(page_url)
            except:  
                send_admin_email_via_mailsnake(
                    "'influencer_tracking_verification' Selenium exception for PostAnalytics={} (url={})".format(pa.id, page_url),
                    '<br />'.join(traceback.format_exc().splitlines())
                )

    def check_visit(datapoint, url):
        log.info('* Attempt id={}, #{}'.format(pa.id, n + 1))
        log.info('* Sleeping for {} secs... id={}, #{}'.format(
            delay, pa.id, n + 1))

        time.sleep(delay)
        try:
            log.info('* Getting /clickstream... id={}, #{}'.format(
                pa.id, n + 1))

            resp = requests.get(
                constants.CLICKMETER_BASE_URL + '/clickstream',
                headers=headers,
                params={'datapoint': datapoint})
            try:
                urls = [
                    unquote(x.get('realDestinationUrl', '')).strip().strip('/')
                    for x in resp.json()['rows']][:constants.CLICKMETER_EVENTS_VERIFICATION_NUMBER]
            except KeyError:
                urls = []

            log.info('* Urls found={} for id={}, #{}'.format(
                len(urls), pa.id, n + 1))

            if url.strip().strip('/') in urls:
                log.info('* Post URL is found... id={}, #{}'.format(
                    pa.id, n + 1))

                return True
        except:
            log.info('* Exception, sending email to admins... id={}, #{}'.format(
                pa.id, n + 1))

            send_admin_email_via_mailsnake(
                "'influencer_tracking_verification' exception for PostAnalytics={}".format(pa.id),
                '<br />'.join(traceback.format_exc().splitlines())
            )

    if pa.post_type not in ['Blog']:
        response = requests.get(pa.post_url)
        if response.status_code == 200:
            pa.tracking_status = pa.TRACKING_STATUS_VERIFIED
        else:
            pa.tracking_status = pa.TRACKING_STATUS_VERIFICATION_PROBLEM
        pa.save()
        return

    log.info('* Exctracting tracking data...')

    check_data = [
        (pa.post_url, contract.tracking_pixel, True),
        (contract.product_url, contract.tracking_link, contract.campaign.product_sending_status not in ['no_product_sending', 'no_product_page']),
        (contract.campaign.client_url, contract.tracking_brand_link, True),
    ]

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Clickmeter-Authkey': constants.CLICKMETER_API_KEY,
    }

    for url, datapoint, to_check in check_data:
        if not to_check:
            continue
        success = False
        visit_page(url)
        for n in xrange(attempts):
            success = success or check_visit(datapoint, url)
        if not success:
            log.info('* Nothing is found. id={}, #{}, url={}'.format(pa.id, n + 1, url))

            pa.tracking_status = pa.TRACKING_STATUS_VERIFICATION_PROBLEM
            pa.save()

            log.info("* PostAnalytics updated with 'Verification Problem' status. id={}, #{}".format(
                pa.id, n + 1))
            log.info('* Sending email to admins about failure. id={}, #{}'.format(
                pa.id, n + 1))

            send_admin_email_via_mailsnake(
                'Verification problem on PostAnalytics={}'.format(pa.id),
                '''
                # of attempts = {}, delay = {} secs<br />
                searched for url={}
                '''.format(attempts, delay, url)
            )
            return

    pa.tracking_status = pa.TRACKING_STATUS_VERIFIED
    pa.save()

    log.info("* PostAnalytics updated with 'Verified' status. id={}, #{}".format(
        pa.id, n + 1))


@task(name='debra.account_helpers.update_campaign_tracking_stats', ignore_result=True)
def update_campaign_tracking_stats(campaign_id):
    from debra.models import (
        BrandJobPost, PostAnalyticsCollectionTimeSeries)
    from debra.helpers import send_admin_email_via_mailsnake

    campaign = get_object_or_404(
        BrandJobPost, id=campaign_id)

    if campaign.tracking_group is None:
        return

    result = ClickMeterListResult(
        clickmeter_api,
        '/aggregated/summary/groups', {
            'timeframe': 'beginning',
            'status': 'active',
        }
    )

    try:
        entity = result.find_entity(campaign.tracking_group)
    except ClickMeterException as e:
        send_admin_email_via_mailsnake(
            'ClickMeterException for Campaign={}'.format(campaign_id),
            e.error_html
        )
    else:
        if not entity:
            # TODO: commented it out because of spamming out emails
            # send_admin_email_via_mailsnake(
            #     'Cannot find ClickMeter EntityId={} for Campaign={}'.format(
            #         campaign.tracking_group, campaign_id),
            #     'Cannot find ClickMeter EntityId={} for Campaign={}'.format(
            #         campaign.tracking_group, campaign_id),
            # )
            pass
        else:
            time_series = PostAnalyticsCollectionTimeSeries.objects.create(
                collection=campaign.post_collection,
                count_clicks=entity.get('totalClicks', 0),
                count_unique_clicks=entity.get('uniqueClicks', 0),
                count_views=entity.get('totalViews', 0),
                count_unique_views=entity.get('uniqueViews', 0),
                snapshot_date=datetime.datetime.now()
            )


# NOT USED!!!!!
@task(name='debra.account_helpers.update_contract_tracking_stats', ignore_result=True)
def update_contract_tracking_stats(contract_id):
    from debra.models import Contract, PostAnalytics
    from debra.helpers import send_admin_email_via_mailsnake

    contract = get_object_or_404(Contract, id=contract_id)

    clicks_result = ClickMeterListResult(
        clickmeter_api,
        '/aggregated/summary/datapoints', {
            'timeframe': 'beginning',
            'type': 'tl',
        }
    )

    views_result = ClickMeterListResult(
        clickmeter_api,
        '/aggregated/summary/datapoints', {
            'timeframe': 'beginning',
            'type': 'tp',
        }
    )

    def get_datapoint_entity(result, datapoint_id):
        try:
            entity = result.find_entity(datapoint_id)
        except ClickMeterException as e:
            send_admin_email_via_mailsnake(
                'ClickMeterException for Contract={}'.format(contract_id),
                e.error_html
            )
        else:
            if not entity:
                # send_admin_email_via_mailsnake(
                #     'Cannot find ClickMeter EntityId={} for Contract={}'.format(
                #         datapoint_id, campaign_id),
                #     'Cannot find ClickMeter EntityId={} for Contract={}'.format(
                #         datapoint_id, campaign_id),
                # )
                return
            return entity

    link_entity = get_datapoint_entity(clicks_result, contract.tracking_link)
    brand_link_entity = get_datapoint_entity(
        clicks_result, contract.tracking_brand_link)
    pixel_entity = get_datapoint_entity(views, contract.tracking_pixel)

    post_collection = contract.campaign.post_collection
    post_analytics = post_collection.filter(
        contract=contract).get_unique_post_analytics()
    for pa in post_analytics:
        new_pa = pa
        new_pa.pk = None
        new_pa.count_clickthroughs = link_entity.get('totalClicks', 0) + brand_link_entity.get('totalClicks', 0)
        new_pa.count_unique_clickthroughs = link_entity.get('uniqueClicks', 0) + brand_link_entity.get('uniqueClicks', 0)
        new_pa.count_impressions = pixel_entity.get('totalViews', 0)
        new_pa.count_unique_impressions = pixel_entity.get('uniqueViews', 0)
        new_pa.save()


@task(name='debra.account_helpers.bulk_update_contract_tracking_stats', ignore_result=True)
def bulk_update_contract_tracking_stats(campaign_id, pa_ids=None, connect_to_url_call=True):
    from copy import copy
    from debra.models import BrandJobPost, PostAnalytics, Platform
    from debra.helpers import send_admin_email_via_mailsnake
    from debra.brand_helpers import connect_url_to_post

    campaign = get_object_or_404(BrandJobPost, id=campaign_id)
    post_collection = campaign.post_collection

    log.info('* Getting Post Analytics from DB...')

    if pa_ids is None:
        # qs = post_collection.get_unique_post_analytics()
        qs = PostAnalytics.objects.filter(
            id__in=list(
                campaign.participating_post_analytics.values_list(
                    'id', flat=True))
        )
    else:
        qs = PostAnalytics.objects.filter(id__in=pa_ids)

    qs = qs.exclude(
        post__platform__isnull=True
    ).prefetch_related('post__platform', 'contract')

    # social_posts = post_analytics.exclude(Q(post_type='Blog') | Q(post_type__isnull=True))
    # post_analytics = post_analytics.filter(Q(post_type='Blog') | Q(post_type__isnull=True))
    social_posts = qs.filter(
        post__platform__platform_name__in=Platform.SOCIAL_PLATFORMS
    )
    post_analytics = qs.filter(
        post__platform__platform_name__in=Platform.BLOG_PLATFORMS
    )

    social_posts = list(social_posts)
    post_analytics = list(post_analytics)

    log.info('* Got {} blog posts, {} social posts.'.format(
        len(post_analytics), len(social_posts)))

    log.info('* Getting data from ClickMeter...')

    if pa_ids:
        date_range = (
            min(p.created for p in post_analytics) - datetime.timedelta(hours=2),
            max(p.created for p in post_analytics) + datetime.timedelta(hours=2),
        )
    else:
        date_range = None

    clicks_result = ClickMeterListResult(
        clickmeter_api,
        '/aggregated/summary/datapoints', {
            'timeframe': 'custom' if date_range else 'beginning',
            'fromDay': date_range[0].strftime('%Y%m%d%H%M') if date_range else None,
            'toDay': date_range[1].strftime('%Y%m%d%H%M') if date_range else None,
            'type': 'tl',
        }
    )

    views_result = ClickMeterListResult(
        clickmeter_api,
        '/aggregated/summary/datapoints', {
            'timeframe': 'custom' if date_range else 'beginning',
            'fromDay': date_range[0].strftime('%Y%m%d%H%M') if date_range else None,
            'toDay': date_range[1].strftime('%Y%m%d%H%M') if date_range else None,
            'type': 'tp',
        }
    )

    log.info('* Creating mappings...')

    def get_new_pas(pas):
        if pa_ids:
            return pas
        new_pas = []
        for pa in pas:
            new_pa = PostAnalytics.objects.from_source(
                post_url=pa.post_url, refresh=True)
            new_pa.post = pa.post
            new_pa.collection = pa.collection
            new_pa.contract = pa.contract
            new_pa.post_found = pa.post_found
            # new_pa = pa
            # new_pa.pk = None
            try:
                if pa.post.platform.platform_name in Platform.BLOG_PLATFORMS:
                    new_pa.count_clickthroughs = 0
                    new_pa.count_unique_clickthroughs = 0
                    new_pa.count_impressions = 0
                    new_pa.count_unique_impressions = 0
            except AttributeError:
                pass
            new_pas.append(new_pa)
        return new_pas

    new_post_analytics = get_new_pas(post_analytics)
    new_social_post_analytics = get_new_pas(social_posts)

    def get_mapping(field):
        d = defaultdict(list)
        for p in new_post_analytics:
            if p.contract is not None:
                field_value = getattr(p.contract, field)
                if isinstance(field_value, list):
                    field_values = field_value
                else:
                    field_values = [field_value]
                for field_value in field_values:
                    d[field_value].append(p)
        return d

    mappings = {
        # 'tracking_link': get_mapping('tracking_link'),
        'product_tracking_links': get_mapping('product_tracking_links'),
        'campaign_product_tracking_links': get_mapping(
            'campaign_product_tracking_links'),
        'tracking_brand_link': get_mapping('tracking_brand_link'),
        'tracking_pixel': get_mapping('tracking_pixel'),
    }

    def find_by_field(field, value):
        return mappings[field][value]

    log.info('* Updating views counts...')

    for page in views_result:
        for entity in page['result']:
            for pa in find_by_field('tracking_pixel', entity.get('entityId')):
                log.info('* Tracking Pixel {} updating...'.format(
                    entity.get('entityId')))
                pa.count_impressions = entity.get('totalViews', 0)
                pa.count_unique_impressions = entity.get('uniqueViews', 0)

    log.info('* Updating counts views...')

    use_campaign_links = campaign.info_json.get('same_product_url')

    for page in clicks_result:
        for entity in page['result']:
            if use_campaign_links:
                for pa in find_by_field('campaign_product_tracking_links', entity.get('entityId')):
                    log.info('* Tracking Link {} updating...'.format(
                        entity.get('entityId')))
                    pa.count_clickthroughs += entity.get('totalClicks', 0)
                    pa.count_unique_clickthroughs += entity.get('uniqueClicks', 0)
            else:
                for pa in find_by_field('product_tracking_links', entity.get('entityId')):
                    log.info('* Tracking Link {} updating...'.format(
                        entity.get('entityId')))
                    pa.count_clickthroughs += entity.get('totalClicks', 0)
                    pa.count_unique_clickthroughs += entity.get('uniqueClicks', 0)
            for pa in find_by_field('tracking_brand_link', entity.get('entityId')):
                log.info('* Tracking Brand Link {} updating...'.format(
                    entity.get('entityId')))
                pa.count_clickthroughs += entity.get('totalClicks', 0)
                pa.count_unique_clickthroughs += entity.get('uniqueClicks', 0)

    log.info('* Saving newly created Post Analytics...')

    for pa in itertools.chain(new_post_analytics, new_social_post_analytics):
        pa.save()
        if connect_to_url_call:
            try:
                connect_url_to_post(pa.post_url, pa.id)
            except:
                send_msg_to_slack(
                    'connect-url-to-post',
                    "{asterisks}\n"
                    "Post Analytics = {pa_id}\n"
                    "{asterisks}\n"
                    "{traceback}\n"
                    "{delimiter}"
                    "\n".format(
                        pa_id=pa.id,
                        asterisks="*" * 120,
                        delimiter="=" * 120,
                        traceback=traceback.format_exc(),
                    )
                )

    log.info('* Done.')


@task(name='debra.account_helpers.bulk_update_campaigns_tracking_stats', ignore_result=True)
def bulk_update_campaigns_tracking_stats(campaign_ids=None):
    from debra.models import BrandJobPost

    if campaign_ids:
        trackable_campaigns = BrandJobPost.objects.filter(id__in=campaign_ids)
    else:
        trackable_campaigns = BrandJobPost.objects.filter(
            periodic_tracking=True)

    for campaign in trackable_campaigns:
        update_campaign_tracking_stats.apply_async(
            [campaign.id], queue='update_campaign_tracking_stats')
        bulk_update_contract_tracking_stats.apply_async(
            [campaign.id], queue='bulk_update_contract_tracking_stats')


@task(name='debra.account_helpers.crawl_contract_influencers', ignore_result=True)
def crawl_contract_influencers():
    """
    This function finds out influencers who are participating in a campaign and issues a special fetch
    so that we have the posts in our system as soon as they are live.

    This function will issue another task that fetches the posts for each individual platform.
    """
    from debra.models import Contract, Influencer
    from debra.helpers import send_admin_email_via_mailsnake
    from platformdatafetcher import pbfetcher, socialfetcher

    # find influencers that are part of a contract and they have signed the contract
    inf_ids = Contract.objects.filter(
        influencerjobmapping__job__periodic_tracking=True, status=Contract.STATUS_SIGNED
    ).values_list('influencerjobmapping__mailbox__influencer', flat=True)

    infs = Influencer.objects.filter(id__in=inf_ids)

    platforms_to_fetch = ['Twitter', 'Facebook', 'Instagram', 'Pinterest', 'Blogspot', 'Wordpress', 'Custom', 'Tumblr', 'Youtube']

    total = infs.count()

    for n, inf in enumerate(infs, start=1):
        for platform_name in platforms_to_fetch:
            log.info('* {}/{} Influencer={} Platform={}'.format(
                n, total, inf.id, platform_name))
            plats = inf.platforms().filter(platform_name=platform_name).exclude(url_not_found=True)
            log.info('* Found %d platforms for %r' % (plats.count(), platform_name))
            try:
                plat = plats[0]
            except IndexError:
                log.info('** No matching platform.')
                continue
            log.info('* Issuing post fetching for %r.' % plat)
            crawl_contract_influencers_platform.apply_async([plat.id], queue='crawl_contract_influencers_platforms')


@task(name='debra.account_helpers.crawl_contract_influencers_platform', ignore_result=True)
def crawl_contract_influencers_platform(platform_id):
    from platformdatafetcher import pbfetcher, fetcher
    from debra.models import Platform
    from debra.helpers import send_admin_email_via_mailsnake

    plat = Platform.objects.get(id=platform_id)

    try:
        log.info('* Start posts fetching.')
        f = fetcher.fetcher_for_platform(plat)
        f.fetch_posts()
    except Exception:
        log.info(
            "'crawl_contract_influencers' exception for Influencer={%r} Platform={%r:%r}" % (plat.influencer.id, plat.platform_name, plat.url)
        )
