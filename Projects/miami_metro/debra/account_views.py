from django.http import HttpResponse, HttpResponseForbidden, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.core.exceptions import MultipleObjectsReturned
from django.core.mail import mail_admins
from django.shortcuts import render_to_response, redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.template import RequestContext
from django.contrib.auth.views import password_reset
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.http import urlencode
from debra.search_helpers import prepare_filter_params
from debra.forms import BrandRegistrationForm, BloggerRegistrationForm, ShopperRegistrationForm
from debra.forms import ShelfAccountForm, ShelfLoginForm, ContactUsForm, ChangeEmailForm, ChangePasswordForm, ContactUsDemoForm, AddNewUserForm
from debra.models import Brands, ProductModelShelfMap, UserProfileBrandPrivilages, UserProfile
from debra.constants import SUPPORT_EMAIL, LAUREN_EMAILS, ATUL_EMAILS, STRIPE_LIVE_PUBLISHABLE_KEY, STRIPE_TEST_PUBLISHABLE_KEY
from debra.constants import STRIPE_PLAN_CHEAP, STRIPE_PLAN_BASIC, STRIPE_PLAN_STARTUP, map_plan_names
from debra.constants import EXPORT_COSTS, EXPORT_INFO
from debra import constants
from debra import account_helpers
from debra import brand_helpers
from xpathscraper import utils
from django.conf import settings
import logging
import json
from django.views.decorators.csrf import csrf_exempt
from mailsnake import MailSnake

mailsnake_client = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')

log = logging.getLogger('debra.account_views')


def favicon(request):
    return redirect("/mymedia/site_folder/images/global/favicon.ico")


def robots(request):
    return HttpResponse("""
User-agent: *
Disallow: /
""", content_type="text/plain")


def my_custom_404_view(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering our ``404.html`` page.
    """
    return render_to_response('404.html', context_instance=RequestContext(request))


def home(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponseRedirect`` if the user is already authenticated, else ``HttpResponse``

    If the ``user`` is already authenticated, redirect them to the url that is most appropriate for their account type.
    Otherwise, render the home page with template variables:

    * *account_form* - an instance of :class:`debra.forms.ShelfAccountForm`
    """
    if request.user.is_authenticated():
        brand = request.visitor["brand"]
        if brand:
            account_helpers.intercom_track_event(request, "brand-viewed-blogger-landing", {})
        # if not (brand and not brand.is_subscribed):
        #     return HttpResponseRedirect(request.user.userprofile.after_login_url)

    response = render(request, 'pages/landing/home.html', {
        'page': 'bloggers',
        'landing_page': True,
        'account_form': ShelfAccountForm()
    }, context_instance=RequestContext(request))

    return response


def internal_blog_visitor(request):
    """
    This method is called by our internal tool to send traffic to bloggers.
    Since this page will show up in blogger's GA, we want to make sure they can't visit this page. So, if they are
    logged in, we should redirect to the home page.
    If they are not logged in, then we should show them an almost empty page showing simple text that they can't view this page
    unless they are logged in.
    And we don't load any of our own analytics on this page, so this will not affect our own analytics numbers.
    """
    if request.user.is_authenticated():
        return redirect(reverse('debra.account_views.home'))
    return HttpResponse("<html><body>Welcome to <a href='http://www.theshelf.com'>TheShelf.com</a>. This is an internal page and you need to be logged in.</body></html>")


def brand_home(request, **kwargs):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering the brand home page

    Render the brand home page with template variables:

    * *account_form* - an instance of :class:`debra.forms.ShelfAccountForm`
    """

    if request.user.is_authenticated():
        brand = request.visitor["brand"]
        if brand:
            account_helpers.intercom_track_event(request, "brand-viewed-brand-landing", {})
        return HttpResponseRedirect(request.user.userprofile.after_login_url)

    if not settings.DEBUG and kwargs.get('blog_redirection', True):
        return HttpResponseRedirect("http://theshelf.com")

    return render(request, 'pages/landing/brand_home.html', {
        'landing_page': True,
        'account_form': ShelfAccountForm(),
        'login_popup_auto_open': kwargs.get('login_popup_auto_open', False),
        'brand_signup_popup_auto_open': kwargs.get('brand_signup_popup_auto_open', False),
        'blogger_signup_popup_auto_open': kwargs.get('blogger_signup_popup_auto_open', False),
        'influenity_signup_popup_auto_open': kwargs.get('influenity_signup_popup_auto_open', False),
    }, context_instance=RequestContext(request))


def getting_started(request, **kwargs):
    """
    """
    return render(request, 'pages/account/getting_started.html', {},
        context_instance=RequestContext(request)
    )


def agency(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering the agency landing page on squarespace site
    """
    return HttpResponseRedirect("http://www.theshelf.com/agencies/")


def selfserve(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering the brand home page on the squarespace site
    """
    return HttpResponseRedirect("http://www.theshelf.com/brands/")


@login_required
def pricing(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering the pricing page

    Render the pricing page with template variables:

    * *stripe_key* - the public key for the ``stripe`` payment service. If ``DEBUG`` is True, we use the ``STRIPE_TEST_PUBLISHABLE_KEY`` key, otherwise
    we use the ``STRIPE_LIVE_PUBLISHABLE_KEY`` key
    """

    current_plan = None

    base_brand = request.visitor["base_brand"]
    brand = request.visitor["brand"]
    if brand:
        account_helpers.intercom_track_event(request, "brand-viewed-pricing", {})
        slack_msg = "\n**************\nBrand = " + brand.domain_name + " User: " + request.user.email + "\n" + " Viewed Pricing Page"
        account_helpers.send_msg_to_slack.apply_async(['brand-viewed-pricing', slack_msg], queue='celery')

    if settings.DEBUG:
        if brand and brand.is_subscribed:
            current_plan = brand.stripe_plan
    else:
        if brand and brand.is_subscribed and not brand.flag_trial_on:
            return HttpResponseRedirect(request.user.userprofile.after_login_url)

    admin_plan = base_brand.flag_availiable_plan

    plans = []
    if base_brand.is_agency and base_brand.flag_show_other_plans:
        plans = constants.get_agency_extra_plans()
        if admin_plan not in plans:
            plans = [admin_plan] + plans
    else:
        plans = [admin_plan]

    plans = filter(None, map(constants.PLAN_INFO.get, plans))

    if base_brand.flag_one_time_fee_on:
        for plan in plans:
            plan['hidden_button'] = True
            plan['extra_text'] = "This will be charged starting next month. At this point, you'll only be charged for the One Time fee."
        other_plans = plans
        plans = [{
            'name': 'One Time Services Contract' if base_brand.flag_services_plan else 'One Time Setup / Service Fee',
            'amount': float(base_brand.flag_one_time_fee),
            'interval': None,
            'type': None,
            'interval_count': None,
            'one_time': True,
            'services_plan': base_brand.flag_services_plan,
            'other_plans': other_plans
        }]

    return render(request, 'pages/landing/pricing.html', {
        'landing_page': True,
        'stripe_key': STRIPE_TEST_PUBLISHABLE_KEY if settings.DEBUG else STRIPE_LIVE_PUBLISHABLE_KEY,
        'current_plan': current_plan,
        'plans': plans,
    }, context_instance=RequestContext(request))


def features(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering the features page
    """

    brand = request.visitor["brand"]
    if brand:
        account_helpers.intercom_track_event(request, "brand-viewed-features", {})

    return render(request, 'pages/landing/features.html', {
        'landing_page': True,
        'page': 'features'
    }, context_instance=RequestContext(request))


def terms(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering the terms page
    """

    return redirect('http://www.theshelf.com/terms-and-conditions/')

    brand = request.visitor["brand"]
    if brand:
        account_helpers.intercom_track_event(request, "brand-viewed-terms", {})

    return render(request, 'pages/landing/terms.html', {
        'landing_page': True,
        'nav_bar_extra_class': "plain_page_nav_bar",
    })


def privacy(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering the privacy page
    """

    brand = request.visitor["brand"]
    if brand:
        account_helpers.intercom_track_event(request, "brand-viewed-privacy", {})

    return render(request, 'pages/landing/privacy.html', {
        'landing_page': True,
        'nav_bar_extra_class': "plain_page_nav_bar",
    })


@require_http_methods(["POST"])
@csrf_exempt
def shelf_login(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    If the login attempt was successful, return an ``HttpResponse`` with ``status=200`` and ``content`` equals a ``json`` object containing keys:

    * *url* - the url to go to after a successful login, this defaults to the url provided as a ``next`` parameter
    in the ``GET`` request, but if that isn't provided, it uses the url set in the :class:`debra.models.UserProfile` instance
    given by ``valid_user.userprofile.after_login_url``

    if the login attempt was not successful, return an ``HttpResponse`` with ``status=500`` and ``content`` equals a ``json`` object containing keys:

    * *errors* - an array of errors given by ``form.errors``

    """
    request.invalidate_visitor = True
    form = ShelfLoginForm(data=request.POST)
    if form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        next_url = request.GET.get('next', None)

        valid_user = authenticate(username=email, password=password)
        if valid_user.username.startswith("theshelf") and valid_user.username.endswith(".toggle"):
            return HttpResponseForbidden()
        login(request, valid_user)
        brand = account_helpers.get_associated_brand(valid_user)
        if brand and brand.is_agency:
            managed = account_helpers.get_managed_brand(valid_user)
            if managed:
                request.session["agency_brand"] = managed[0].brand.id
        return HttpResponse(status=200, content=json.dumps({'url': next_url if next_url else valid_user.userprofile.after_login_url}))
    else:
        return HttpResponse(status=403, content=json.dumps({'errors': form.errors}))


@require_http_methods(["POST"])
def shopper_signup(request):
    """
    :param request: an ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    If the user successfully signs up (so the :class:`debra.forms.ShopperRegistration` form validated),
    simply return an ``HttpResponse`` instance with ``status=200``. However, if
    form validation failed, respond with a ``HttpResponse`` instance with ``status=500`` and content equals a ``json`` object containing keys:

    * *errors* - an array of errors given by ``form.errors``
    """
    form = ShopperRegistrationForm(data=request.POST)
    if form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        form.save()

        valid_user = authenticate(username=email, password=password)
        login(request, valid_user)

        return HttpResponse(status=200)
    else:
        return HttpResponse(status=500, content=json.dumps({'errors': form.errors}))


@require_http_methods(["POST"])
def blogger_signup(request):
    """
    :param request: an ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    If the blogger successfully signs up (so the :class:`debra.forms.BloggerRegistration` form validated),
    simply return an ``HttpResponse`` instance with ``status=200``. However, if
    form validation failed, respond with a ``HttpResponse`` instance with ``status=500`` and content equals a ``json`` object containing keys:

    * *errors* - an array of errors given by ``form.errors``
    """
    # body = json.loads(request.POST)
    body = request.POST
    form = BloggerRegistrationForm(data=request.POST)
    distinct_id = account_helpers.get_distinct_id_mixpanel(request)
    if form.is_valid():
        #email = form.cleaned_data['email']
        #password = form.cleaned_data['password']
        name = form.cleaned_data['name']
        blog_name = form.cleaned_data['blog_name']
        blog_url = form.cleaned_data['blog_url']

        user_prof = form.save()
        #profile_info_extraction.initialize_profile_info.apply_async([user_prof], queue="celery")

        # print "[blogger_signup] user_prof: %r name %r blog_page %r" % (user_prof, name, blog_url)
        user_prof.name = name
        user_prof.blog_name = blog_name
        user_prof.blog_page = blog_url
        user_prof.can_set_affiliate_links = True
        user_prof.save()
        print "[blogger_signup_post_save] user_prof.blog_page %s distinct_id %s" % (user_prof.blog_page, distinct_id)

        # this has to be called as celery task
        params = dict(
            user_profile=user_prof,
            distinct_id=distinct_id,
            # influenity_signup=bool(body.get('influenity_signup')),
            # tag_id=1636,
        )
        if settings.DEBUG:
            account_helpers.bloggers_signup_postprocess(**params)
        else:
            account_helpers.bloggers_signup_postprocess.apply_async(
                kwargs=params, queue="celery")

        if bool(body.get('influenity_signup')):
            redirect_url = 'http://www.theshelf.com/influenity-thank-you'
        else:
            redirect_url = reverse(
                'debra.account_views.registration_complete_blogger')

        return HttpResponse(
            status=200, content=json.dumps({'url': redirect_url}))
    else:
        # if we're here, its a failed login (email is correct, password wrong)
        return HttpResponse(status=500, content=json.dumps({'errors': form.errors}))


@require_http_methods(["POST"])
def brand_signup(request):
    """
    :param request: an ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    If the brand successfully signs up (so the :class:`debra.forms.BrandRegistrationForm` form validated)
    return an ``HttpResponse`` instance with ``status=200`` and content equals a ``json`` object containing keys:

    * *url* - if ``DEBUG`` is True, this value is the url which mimics the activation link the user would receive by email, if
        not ``DEBUG``, the url leads to the ``registration complete`` page.

    If form validation failed, respond with a ``HttpResponse`` instance with ``status=500`` and content equals a ``json`` object containing keys:

    * *errors* - an array of errors given by ``form.errors``
    """
    from debra import basecrm_integration
    from debra import streak_integration

    from_admin = request.POST.get('from_admin', False) == 'true'
    form = BrandRegistrationForm(
        data=request.POST,
        request=request,
        referer=request.POST.get('referer', '')
    )
    distinct_id = account_helpers.get_distinct_id_mixpanel(request)
    if form.is_valid():
        brand_user_prof = form.save()
        brand_user_prof.name = form.cleaned_data['first_name']
        # brand_user_prof.name = form.cleaned_data['first_name'] + ' ' + form.cleaned_data['last_name']
        brand_user_prof.save()

        # automatically login user after registration
        user = brand_user_prof.user
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        if not from_admin:
            login(request, user)

        buy_after = False
        if request.POST.get("buy_after") == "true":
            buy_after = True
        request.session["buy_after"] = buy_after

        # this has to be called as celery task
        if True:
            account_helpers.brands_signup_postprocess(brand_user_prof, form, distinct_id)
        else:
            account_helpers.brands_signup_postprocess.apply_async([brand_user_prof, form, distinct_id], queue="celery")

        if not settings.DEBUG and not from_admin:
            brand_signedup_first_name = form.cleaned_data["first_name"]
            brand_signedup_last_name = form.cleaned_data["last_name"]

            brand_signedup_url = form.cleaned_data["brand_url"]
            brand_signedup_brand_name = form.cleaned_data["brand_name"]
            brand_signedup_email = form.cleaned_data["email"]
            # brand_phone_number = brand_user_prof.phone
            brand_phone_number = ""

            # create a lead in BASE CRM (it's fault-tolerant)
            basecrm_integration.create_lead(brand_signedup_first_name,
                                            brand_signedup_last_name,
                                            brand_signedup_brand_name,
                                            brand_signedup_url,
                                            brand_signedup_email,
                                            brand_phone_number)

            referer_tag = 'home' if form.referer_tag == 'blog' else\
                form.referer_tag
            streak_integration.mark_brand_signup(**locals())

            # now send an email to ourselves on sales@theshelf.com just to make sure we can test out the basecrm
            # integration in the beginning 
            subject = '%s <> The Shelf: Demo Request' % brand_signedup_url
            body = "Hi %s,<p>Thanks for your interest!</p><p>Just wanted to confirm that you signed up for a demo for the url: %s</p><p>Let us know a few times today and tomorrow for a quick call. It's a short 5-10 min demo where we'll show you how our product works.</p>Thanks,<br>Dean<br><br>PS: Check out <a href=%s>our blog</a> for some informative articles on Influencer Marketing." % (
                brand_signedup_first_name,
                brand_signedup_url,
                "http://www.theshelf.com/the-blog/?utm_campaign=demo-email-automated&utm_medium=demo-email&utm_source=email&utm_content=demo-email&utm_term=brands-agencies"
            )
            from_email = 'sales@theshelf.com'
            from_name = 'Amy from TheShelf.com'
            to_emails = [{'email': 'atul@theshelf.com', 'type': 'to'},
                         {'email': 'sales@theshelf.com', 'type': 'to'},
                         ]

            mailsnake_client.messages.send(message={'html': body,
                                                    'subject': subject,
                                                    'from_email': from_email,
                                                    'from_name': from_name,
                                                    'to': to_emails})

            # send notification on slack so that our sales folks can instantly bounce on it
            slack_msg = "\n**************\nNEW LEAD " + brand_signedup_url + " Email: [" + brand_signedup_email + "] Name: [" + brand_signedup_first_name + "] Phone: [" + brand_phone_number + "]\n"
            account_helpers.send_msg_to_slack.apply_async(['brand-signup', slack_msg],
                                                          queue='celery')

        if from_admin:
            return HttpResponse(status=200, content=json.dumps({'url': reverse('upgrade_admin:brand_signup')}))
        else:
            return HttpResponse(status=200, content=json.dumps({'url': reverse('debra.account_views.registration_complete_brand')}))
    else:
        return HttpResponse(content=json.dumps({'errors': form.errors}), status=500)


@login_required
def blogger_next_steps(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` rendering the ``blogger_after_signup.html`` page
    """
    # force to use after login url there
    return HttpResponseRedirect(request.user.userprofile.after_login_url)

    return render(request, 'pages/landing/blogger_after_signup.html', {})


@login_required
def brand_next_steps(request):
    """
    replaced to render search page with trial popup
    """

    brand = request.visitor["brand"]
    if brand and brand.is_subscribed:
        return redirect(reverse('debra.search_views.blogger_search'))

    return redirect(reverse('debra.account_views.pricing'))

    # old "trial" code here
    # context = {
    #     'search_page': True,
    #     'type': 'all',
    #     'selected_tab': 'search_bloggers',
    #     'shelf_user': request.user.userprofile,
    #     'debug': settings.DEBUG,
    # }

    # context.update(prepare_filter_params(context, plan_name=None))

    # return render(request, 'pages/landing/brand_after_signup.html', context)


@require_http_methods(["POST"])
def contact_us(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    If the :class:`debra.forms.ContactUsForm` was valid, then send us the contact us email and return a ``redirect`` to the url given by
    the ``next`` key in the ``GET`` parameters. Or, if that doesn't exist, just return a ``HttpResponse`` instance
    with ``status=200``.

    If the :class:`debra.forms.ContactUsForm` was not valid, then issue a ``HttpResponse`` having ``status=500`` and ``content`` as a ``json`` object
    containing keys:

    * *errors* - an array of errors given by ``form.errors``
    """
    contact_form = ContactUsForm(data=request.POST)

    if contact_form.is_valid():
        name = contact_form.cleaned_data['name']
        email = contact_form.cleaned_data['email']
        message = contact_form.cleaned_data['message']

        subject = 'Thank you %s for contacting us at The Shelf!' % (name.title())
        body = 'Hi %s,<p>Thank you for contacting us!</p><p>Your message:<br><br>********************<p>%s<br><br>********************</p></p><p>We have been notified and we will get in touch with you as soon as possible!</p>Thanks,<br>Lauren' % (name.title(),
                                                                                                                                                             message)
        from_email = LAUREN_EMAILS['contact_email']
        from_name = 'Lauren @The Shelf'
        to_emails = [{'email': SUPPORT_EMAIL, 'type': 'bcc'},
                     {'email': LAUREN_EMAILS['contact_email'], 'type': 'cc'},
                     {'email': email, 'type': 'to'}]
        mailsnake_client.messages.send(message={'html': body,
                                                'subject': subject,
                                                'from_email': from_email,
                                                'from_name': from_name,
                                                'to': to_emails})
    else:
        return HttpResponse(status=500, content=json.dumps({'errors': contact_form.errors}))

    next = request.GET.get('next', None)
    return redirect(next) if next else HttpResponse(status=200)


@require_http_methods(["POST"])
def add_new_user(request):
    base_brand = request.visitor["base_brand"]
    form = AddNewUserForm(data=request.POST)

    if form.is_valid():
        name = form.cleaned_data["name"]
        email = form.cleaned_data["email"]

        password = User.objects.make_random_password()

        new_user = User.objects.create_user(email, email, password)
        new_user.is_active = True
        new_user.save()

        up = UserProfile.objects.create(user=new_user)
        up.name = name
        up.save()

        brand_helpers.connect_user_to_brand(base_brand, up)

        subject = 'You have been invited to join %s\'s account on The Shelf!' % base_brand.domain_name
        body = 'Hi %s,<p>Your team member (%s) has invited you to join her on The Shelf.</p><p>To access your account please use username: %s and password: %s</p>Thanks,<br>The Shelf Team.' % (name, request.user.email, email, password)

        from_email = LAUREN_EMAILS['contact_email']
        from_name = 'Lauren @The Shelf'
        to_emails = [
            {'email': email, 'type': 'to'},
            {'email': LAUREN_EMAILS['admin_email'], 'type': 'cc'},
            {'email': request.user.email, 'type': 'cc'},
        ]

        mailsnake_client.messages.send(
            message={
                'html': body,
                'subject': subject,
                'from_email': from_email,
                'from_name': from_name,
                'to': to_emails
            })
    else:
        return HttpResponse(status=500, content=json.dumps({'errors': form.errors}))

    return HttpResponse()


@login_required
def our_logout(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``redirect`` to the home page
    """
    request.invalidate_visitor = True
    logout(request)
    if settings.DEBUG:
        return redirect(reverse('debra.account_views.brand_home'))
    else:
        return HttpResponseRedirect("http://theshelf.com")


@login_required
@require_http_methods(["POST"])
def change_email(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    If the :class:`debra.forms.ChangeEmailForm` was valid, then change the logged in user's email and return a ``HttpResponse``
    instance with ``status=200``

    If the :class:`debra.forms.ChangeEmailForm` was not valid, then issue a ``HttpResponse`` having ``status=500`` and ``content`` as a ``json`` object
    containing keys:

    * *errors* - an array of errors given by ``form.errors``
    """
    user = request.user
    bound_form = ChangeEmailForm(request.POST, instance=user)
    if bound_form.is_valid():
        u = bound_form.save(commit=False)
        u.username = u.email
        u.save()
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=500, content=json.dumps(bound_form.errors))


@login_required
@require_http_methods(["POST"])
def change_password(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    If the :class:`debra.forms.ChangePasswordForm` was valid, then change the logged in user's email and return a ``HttpResponse``
    instance with ``status=200``

    If the :class:`debra.forms.ChangePasswordForm` was not valid, then issue a ``HttpResponse`` having ``status=500`` and ``content`` as a ``json`` object
    containing keys:

    * *errors* - an array of errors given by ``bound_form.errors``
    """
    user = request.user
    bound_form = ChangePasswordForm(request.POST)
    if bound_form.is_valid():
        password = bound_form.cleaned_data.get('password')
        user.set_password(password)
        user.save()
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=500, content=json.dumps(bound_form.errors))

@ensure_csrf_cookie
def reset_password(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    we need this django-registration override method so we can see what the status of the reset_password call
    was, as we use our own forms to implement this method
    Note: this is just a thin wrapper around the django password_reset view method

    If the ``password_reset`` result had a ``status_code==302`` then ``HttpResponse`` will have a ``status=200``,
    otherwise ``HttpResponse`` will have a ``status=500``. The response will have an empty ``json`` object as its ``content``
    """
    reset_result = None
    try:
        reset_result = password_reset(request)
    except Exception:
        log.exception('password_reset error.')

    if reset_result is None:
        return HttpResponse(status=500, content=json.dumps({}))

    if reset_result.status_code != 302:
        # log.error('password_reset failed to redirect.'
        #     'Response: {}\n{}'.format(
        #         type(reset_result), reset_result.__dict__)
        # )
        pass

    return HttpResponse(status=200 if reset_result.status_code in [302] else 500, content=json.dumps({}))


@login_required
def unregister(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    This view method is for "deleting" the user in the request. We say "deleting" because we don't actually delete the
    user, just make them inactive.  The returned ``HttpResponse`` has ``status=200`` and ``content`` equals a ``json`` object
    containing keys:

    * *url* - the value of url provided as the ``next`` parameter in the ``GET`` request
    """
    user = request.user
    user.is_active = False
    user.save()

    our_logout(request)
    return HttpResponse(status=200, content=json.dumps({'url': request.GET.get('next')}))


@login_required
def upgrade_request(request):
    """
    :param request: ``HttpRequest`` instance
    :return: ``HttpResponse`` instance

    *DEPRECATED*
    """
    user = request.user
    num_items = ProductModelShelfMap.objects.filter(user_prof=user.userprofile).count()
    blog_url = request.POST.get('blog_url', None)

    if blog_url is None:
        return HttpResponse(status=500)

    send_mail('User %s wants to upgrade.' % user.email, 'She had %d items and her url is %s!' % (num_items, blog_url),
              'lauren@theshelf.com',
              ['atul@theshelf.com', 'lauren@theshelf.com'], fail_silently=False)

    return redirect(reverse('debra.shelf_views.about_me', args=(user.id,)))


@login_required
def blogger_blog_ok(request):
    """
    blogger landing page when blog is verified
    """
    # logout(request)
    if request.visitor['influencer']:
        if request.visitor['influencer'].ready_to_invite or request.visitor['influencer'].show_on_search:
            return redirect(request.visitor['influencer'].about_page)
        else:
            return render(request, 'pages/landing/tmp_blogger_blog_added.html', {})
    else:
        if request.visitor["user"].blog_verified:
            account_helpers.find_and_connect_user_to_influencer(request.visitor["user"])
        return redirect('/')


def blog_url_strip(url):
    try:
        a = url.split('://')
        if a[0] in ['http', 'https']:
            a = a[1:]
        a = a[0].split('.')
        if a[0].lower() in ['www']:
            a = a[1:]
        return '.'.join(a)
    except:
        return url


@login_required
def blogger_blog_not_ok(request):
    """
    blogger landing page when blog is not verified
    """
    user = request.visitor["user"]
    auth_user = request.visitor["auth_user"]
    influencer = request.visitor["influencer"]
    if influencer and influencer.group_mapping.filter(jobs__isnull=True).exists():
        user.blog_verified = True
        user.save()
    if not user:
        return redirect('/')
    blog_url = user.blog_page
    account_helpers.intercom_track_event(request, "blogger-get-badge", {
        'email': auth_user.email,
        'blog_url': blog_url,
    })
    return render(request, 'pages/landing/tmp_blogger_blog_verify.html', {'blog_url': blog_url, 'blog_url_stripped': blog_url_strip(blog_url) or blog_url})

# def blogger_badges_help(request):
#     """
#     page with badges (the same as in `blogger_blog_not_ok`, but this time just plain page)
#     """
#     user = request.visitor["user"]


@login_required
def brand_email_mismatch(request):
    """
    brand landing page when email domain mismatch brand domain
    """

    import hashlib
    userprofile = request.user.userprofile
    hex_string = hashlib.md5(str(userprofile.id)).hexdigest()
    account_helpers.intercom_track_event(request, "brand-email-mismatch", {
        'email': request.user.email,
        'brand_url': request.user.userprofile.temp_brand_domain
    })
    logout(request)
    return render(request, 'pages/landing/brand_email_domain_mismatch.html', {
        'userprofile': userprofile,
        'hex_string': hex_string
    })


@login_required
def shopper_next_steps(request):
    """
    shopper landing page
    """
    logout(request)
    return render(request, 'pages/landing/tmp_shopper.html', {})


@login_required
def trigger_badge_verify(request):
    """
    view called when user requests blog badge verification
    """
    if not request.user.userprofile or request.user.userprofile.blog_verified:
        return redirect('/')
    blog_url = request.user.userprofile.blog_page
    #blogger_name = request.user.userprofile.name if request.user.userprofile.name else request.user.email
    account_helpers.intercom_track_event(request, 'blogger-badge-verification-requested', {'blog_url': blog_url})
    account_helpers.verify_blog_ownership.apply_async([request.user.userprofile.id], queue="celery", countdown=5 * 60)
    # account_helpers.verify_blog_ownership(request.user.userprofile.id)

    if request.is_ajax():
        return HttpResponse()
    else:
        return render(request, 'registration/badge_verify_request_sent.html', {})


@login_required
def trigger_brand_membership_verify(request):
    """
    view called when user requests blog badge verification
    """
    userprofile = request.user.userprofile
    if not userprofile.temp_brand_domain:
        logout(request)
        return HttpResponse("verified")
    brand = get_object_or_404(Brands, domain_name__iexact=userprofile.temp_brand_domain)
    account_helpers.intercom_track_event(
        request, 'brand-membership-verification-requested', {'brand_url': brand.domain_name})
    account_helpers.verify_brand_membership.apply_async([userprofile.id], queue="celery")
    # account_helpers.verify_brand_membership(userprofile.id)

    return HttpResponse()


def resend_activation_key(request):
    """
    """
    email = request.GET.get('email')
    user = get_object_or_404(User, email=email, is_active=False)
    account_helpers.resend_activation_email(user)
    return render(request, 'registration/email_resent.html', {})


@login_required
def registration_complete_brand(request):
    brand = request.visitor["brand"]
    if brand:
        if brand.is_subscribed:
            return redirect(reverse('debra.search_views.blogger_search'))
        elif not brand.flag_locked:
            return redirect(reverse('debra.account_views.pricing'))
    if request.visitor["has_influencer"]:
        return HttpResponseRedirect(request.user.userprofile.after_login_url)
    return render(request, 'registration/registration_complete_brand.html', {
        'landing_page': True,
    })


def registration_complete_blogger(request):
    return render(request, 'registration/registration_complete_blogger.html', {})


def email_verified_brand(request):
    brand = request.visitor["brand"]
    if not brand or brand.is_subscribed or brand.flag_locked is False:
        return redirect('/')
    return render(request, 'registration/activation_complete_brand.html', {})


def demo_requested(request):
    return render(request, 'registration/demo_requested.html', {})


def auto_buy(request):
    user_prof = request.visitor["user"]
    brand = request.visitor["base_brand"]
    owner = None
    # users email matched existing
    if brand:
        # subscribed brand => go to search
        if brand.is_subscribed:
            return HttpResponseRedirect(request.user.userprofile.after_login_url)
    else:
        # brand mismatch, figure out whom the user claims he is
        try:
            brand = Brands.objects.get(domain_name__iexact=user_prof.temp_brand_domain)
        except Brands.DoesNotExist:
            mail_admins("No brand for user: %i during account_views.auto_buy" % (user_prof.id,))
            raise Http404()
        except MultipleObjectsReturned:
            mail_admins("Multiple brands for user: %i during account_views.auto_buy" % (user_prof.id,))
            raise Http404()

        owner = brand.related_user_profiles.get(permissions=UserProfileBrandPrivilages.PRIVILAGE_OWNER).user_profile

    return render(request, 'registration/auto_buy.html', {
        'brand': brand,
        'owner': owner,
        'stripe_key': STRIPE_TEST_PUBLISHABLE_KEY if settings.DEBUG else STRIPE_LIVE_PUBLISHABLE_KEY,
    })


def plan_changed_brand(request, plan_name):
    oryg_name = None
    brand = request.visitor["base_brand"]
    if brand and brand.is_subscribed:
        oryg_name = brand.stripe_plan
    else:
        return redirect('/')
    current_plan = map_plan_names(oryg_name)
    if plan_name.lower() != current_plan.lower():
        return redirect('/')
    return render(request, 'registration/plan_changed_brand.html', {
        'plan_name': current_plan,
        'oryg_name': oryg_name,
        'purchase_amount': brand.flag_last_payment_amount,
        'STRIPE_PLAN_CHEAP': STRIPE_PLAN_CHEAP,
        'STRIPE_PLAN_BASIC': STRIPE_PLAN_BASIC,
        'STRIPE_PLAN_STARTUP': STRIPE_PLAN_STARTUP,
    })


def export_list(request):
    """
    """
    if request.user.is_authenticated():
        return HttpResponseRedirect(request.user.userprofile.after_login_url)

    return redirect(reverse('debra.account_views.brand_home'))

    listing = []
    groups = [range(0, 2), range(2, 5), range(5, 9), range(9, 11)]
    costs = {}
    for group in groups:
        sublisting = []
        for index in group:
            export = EXPORT_INFO[index]
            export.update({
                'price': int(EXPORT_COSTS[export['export_type']] / 100)
            })
            sublisting.append(export)
            costs[export['export_type']] = {
                'price': export['price'],
                'title': export['title']
            }
        listing.append(sublisting)

    response = render(request, 'pages/landing/lists.html', {
        'page': 'bloggers',
        'exports': listing,
        'export_costs': costs
    }, context_instance=RequestContext(request))
    return response


def export_list_custom(request):
    """
    """
    response = render(request, 'pages/landing/lists_custom_page.html', {
        'page': 'bloggers',
    }, context_instance=RequestContext(request))
    return response


def export_ongoing(request):
    """
    """
    if request.user.is_authenticated():
        return HttpResponseRedirect(request.user.userprofile.after_login_url)
    response = render(request, 'pages/landing/export_ongoing.html', {
    }, context_instance=RequestContext(request))
    return response


def access_locked_page(request, reason, suspend_reason=None):
    brand = request.visitor["brand"]
    data = {
        'reason': reason,
        'suspend_reason': suspend_reason,
        'stripe_key': STRIPE_TEST_PUBLISHABLE_KEY if settings.DEBUG else STRIPE_LIVE_PUBLISHABLE_KEY,
        'plan': constants.PLAN_INFO.get(brand.flag_availiable_plan) if brand else None
    }
    response = render(request, 'pages/landing/access_locked.html',
        data, context_instance=RequestContext(request))
    return response


def blog_redirect(request, post_url):
    blog_url = '/'.join([constants.BLOG_DOMAIN, 'the-blog', post_url])
    if len(request.GET) > 0:
        blog_url += '?' + urlencode(request.GET)
    # return HttpResponsePermanentRedirect(blog_url)
    context = {
        'blog_url': blog_url,
    }
    return render(request, 'pages/account/blog_redirection_page.html', context)


@login_required
def slack_test(request):
    from debra.account_helpers import send_msg_to_slack

    if request.GET.get('msg'):
        send_msg_to_slack('front-end', unicode(request.GET.get('msg')))
    return HttpResponse("Enter some message to be sent using 'msg' GET parameter")
