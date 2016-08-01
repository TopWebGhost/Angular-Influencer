import logging
import json
from django.http import (HttpResponseBadRequest, HttpResponse,
    HttpResponseRedirect)
from django.shortcuts import redirect, render
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.core.mail import mail_admins
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404
from django.template import RequestContext

import stripe
from rauth import OAuth2Service
from mixpanel import Mixpanel

from debra.constants import (STRIPE_SECRET_KEY, STRIPE_OAUTH_CLIENT_ID,
    STRIPE_CONNECT_AUTHORIZE_URL, STRIPE_CONNECT_ACCESS_TOKEN_URL,
    STRIPE_API_BASE_URL, map_plan_names,)
from debra.models import (Brands, UserProfileBrandPrivilages, UserProfile,
    Influencer)
from debra import account_helpers, brand_helpers

mp = Mixpanel(settings.MIXPANEL_TOKEN)
log = logging.getLogger('debra.payment_views')

stripe.api_key = STRIPE_SECRET_KEY

stripe_connect_service = OAuth2Service(
    name = 'stripe',
    client_id = STRIPE_OAUTH_CLIENT_ID,
    client_secret = STRIPE_SECRET_KEY,
    authorize_url = STRIPE_CONNECT_AUTHORIZE_URL,
    access_token_url = STRIPE_CONNECT_ACCESS_TOKEN_URL,
    base_url = STRIPE_API_BASE_URL,
)

@login_required
def brand_payment(request):
    """
    process a payment for a brand
    takes requests body as json with following fields
    - stripeToken
    - promotionCode
    - plan  - plan name, all plans are listed under :mod:`debra.constants`

    - amount - obsolete
    """
    import datetime
    import time
    request.invalidate_visitor = True
    user = request.user
    user_prof = user.userprofile
    brand = account_helpers.get_associated_brand(user_prof)

    do_association = False
    #if the user doesnt have a brand, nothing to do but return
    if not brand:
        print "No brand privilages"
        try:
            brand = Brands.objects.get(domain_name__iexact=user_prof.temp_brand_domain)
        except Brands.DoesNotExist:
            mail_admins("No brand for user: %i during autoassociation in payment view" % (user_prof.id,))
            return HttpResponseBadRequest(content=json.dumps({'error': 'We had some trouble with associating brand to your account, no charge was made.'}))
        except MultipleObjectsReturned:
            mail_admins("Multiple brands for user: %i during autoassociation in payment view" % (user_prof.id,))
            return HttpResponseBadRequest(content=json.dumps({'error': 'We had some trouble with associating brand to your account, no charge was made.'}))

        if brand.stripe_id:
            owner = brand.related_user_profiles.get(permissions=UserProfileBrandPrivilages.PRIVILAGE_OWNER).user_profile
            msg = "Brand you claimed you are member is already registered and your email doesnt seems to be from its domain. Please contact %s to get access to account."
            return HttpResponseBadRequest(content=json.dumps({'error': msg % owner.name}))

        do_association = True

    try:
        data = json.loads(request.body)
        
    except ValueError:
        #old code fallback
        data = {}

    token = data.get('stripeToken')
    promo = data.get('promotionCode')
    plan = data.get('plan')
    one_time = bool(int(data.get('one_time')))
    print "signup to", plan
    log.error('Signup to {}'.format(plan))
    payment_amount = int(data.get('amount', Brands.SUBSCRIPTION_COST))

    if not token:
        #old code fallback
        token = request.POST['stripeToken']
        payment_amount = int(request.POST.get('amount', Brands.SUBSCRIPTION_COST))
        plan = "Startup"
    try:
        customer_id = brand.stripe_id

        # if the brand doesn't have a stripe id, create one now (this should happen when their subscription starts)
        if not customer_id:
            print "Creating new stripe customer"
            log.error('Creating new stripe customer')
            try:
                customer_id = stripe.Customer.create(
                    card=token,
                    description='{brand} customer created'.format(brand=brand.name)
                ).id
            except Exception:
                log.exception('Payment error')
                return HttpResponseBadRequest(content=json.dumps({'error': 'Payment processing error'}))
            # print "Success"
            log.error('Success')
            brand.stripe_id = customer_id
            brand.save()

        customer = stripe.Customer.retrieve(customer_id)

        is_new_subscription = any([
            one_time,
            not customer.subscriptions.data,
            customer.subscriptions.data and customer.subscriptions.data[0].plan != plan,
        ])

        if one_time:
            try:
                stripe.Charge.create(
                    amount=payment_amount * 100,
                    currency="usd",
                    customer=customer_id,
                    description="{brand} with email {email}".format(brand=brand.name, email=user.email)
                )
            except stripe.error.CardError:
                return HttpResponseBadRequest(content=json.dumps({'error': 'Payment processing error'}))
        elif customer.subscriptions.data:
            #remove existing subscriptions if any (plan change)
            # print "Replace subscriptions"
            log.error('Replace subscriptions, len={}, data:{}'.format(len(customer.subscriptions.data), customer.subscriptions.data))
            sub = customer.subscriptions.data[0]
            log.error('Last sub: {}'.format(sub))
            sub.plan = plan
            if promo:
                sub.coupon = promo
            sub.save()
            if not promo:
                try:
                    sub.delete_discount()
                    customer.save()
                except Exception:
                    pass
            log.error('Sub updated: {}'.format(sub))
        else:
            # print "New subscription"
            log.error('New subsciption, promo: '.format(promo))
            try:
                if promo:
                    customer.subscriptions.create(plan=plan, coupon=promo)
                else:
                    customer.subscriptions.create(plan=plan)
            except Exception:
                brand.stripe_id = None
                brand.is_subscribed = False
                brand.save()
                log.exception('Payment error')
                return HttpResponseBadRequest(content=json.dumps({'error': 'Payment processing error'}))
                
        # save payment amount
        brand.flag_last_payment_amount = payment_amount
        brand.flag_stripe_customer_created = time.mktime(datetime.datetime.now().timetuple())
        
        # make sure brand is not blacklisted
        brand.blacklisted = False

        # make sure brand is not suspended due to payment
        if is_new_subscription and brand.flag_suspended and brand.flag_suspend_reason == 'stripe_plan_deleted':
            brand.flag_suspended = False
            brand.flag_suspend_reason = None

        brand.save()

        user_prof.update_intercom()

        log.error('Success')
        mp.track(user_prof.user.email, 'Subscribed',
            {
                'brand_url': brand.domain_name,
                'amount': payment_amount, # payment_amount is in cents
                'promocode': promo,
            })
        # stripe.Charge.create(
        #   amount=payment_amount, # amount in cents
        #   currency="usd",
        #   customer=customer_id,
        #   description="{brand} with email {email}".format(brand=brand.name, email=user.email)
        # )

        if do_association:
            print "Late association with brand"
            brand_helpers.sanity_checks(brand)
            user_prof.temp_brand_domain = None
            user_prof.save()
            brand_helpers.connect_user_to_brand(brand, user_prof)

        print "Refreshing stripe data"
        log.error('Refreshing stripe data')
        brand.refresh_stripe_data()

        brand = Brands.objects.get(id=brand.id)
        if brand.is_subscribed:
            print "All good"
        else:
            print "Brand is still not subscribed?"
        if one_time:
            if request.is_ajax():
                return HttpResponse(status=200, content=json.dumps({'next': reverse("debra.search_views.main_search")}))
            else:
                return redirect(reverse("debra.search_views.main_search"))
        else:
            if request.is_ajax():
                return HttpResponse(status=200, content=json.dumps({'next': reverse("debra.account_views.plan_changed_brand", args=(map_plan_names(plan.lower()),))}))
            else:
                return redirect(reverse("debra.account_views.plan_changed_brand", args=(map_plan_names(plan.lower()),)))
    except stripe.CardError:
        brand.stripe_id = None
        brand.is_subscribed = False
        brand.save()
        # The card has been declined
        return HttpResponseBadRequest(content=json.dumps({'error': 'credit card has been declined'}))
    except stripe.InvalidRequestError:
        return HttpResponseBadRequest(content=json.dumps({'error': 'promotion code is invalid'}))

@login_required
def check_coupon(request):
    """
    returns data about coupon
    """
    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest("Bad request")

    promo = data.get('promotionCode')

    try:
        code = stripe.Coupon.retrieve(promo)
    except:
        return HttpResponseBadRequest("Invalid promotion code!")

    resp = {
        "percent_off": code["percent_off"],
        "amount_off": code["amount_off"]
    }

    return HttpResponse(json.dumps(resp))


@csrf_exempt
def stripe_webhook(request):
    """
    Webhook for Stripe. Handles all sorts of Stripe events.
    """
    event_json = json.loads(request.body)
    event_type = event_json.get('type')

    data = event_json.get('data').get('object')
    customer_id = data.get('customer')

    if event_type in ["customer.subscription.updated", "customer.subscription.deleted", "customer.subscription.created"]:
        # occurs whenever a subscription changes (like switching from one plan 
        # to another, or switching status from trial to active) (1) or a 
        # customer ends their subscription (2) or a customer with no 
        # subscription is signed up for a plan (3).
        suspend = data.get('status') in ["canceled", "past_due", "unpaid"]
        # set suspending flag for all brands with given customer_id
        account_helpers.suspend_brands_with_canceled_plan(customer_id, suspend)

    return HttpResponse(status=200)


@csrf_exempt
def stripe_auth(request):
    params = {'response_type': 'code', 'scope': 'read_write'}
    url = stripe_connect_service.get_authorize_url(**params)
    return HttpResponseRedirect(url)


@csrf_exempt
def stripe_callback(request):
    if not request.user.is_authenticated or not request.visitor["influencer"]:
        return HttpResponseRedirect(reverse('debra.account_views.brand_home'))
    userprofile = UserProfile.objects.get(user=request.user)
    # the temporary code returned from stripe
    code = request.GET['code']
    # identify what we are going to ask for from stripe
    data = {
        'grant_type': 'authorization_code',
        'code': code
    }

    # Get the access_token using the code provided
    resp = stripe_connect_service.get_raw_access_token(method='POST', data=data)

    # process the returned json object from stripe
    stripe_payload = json.loads(resp.text)

    userprofile.stripe_access_token = stripe_payload['access_token']
    userprofile.stripe_refresh_token = stripe_payload['refresh_token']
    userprofile.stripe_publishable_key = stripe_payload['stripe_publishable_key']
    userprofile.stripe_user_id = stripe_payload['stripe_user_id']
    userprofile.save()

    # Sample return of the access_token, please don't do this! this is
    # just an example that it does in fact return the access_token
    return HttpResponse(resp.text)


@login_required
def blogger_payment_page(request, influencer_id):

    base_brand = request.visitor["base_brand"]

    if not base_brand:
        return HttpResponseRedirect(reverse('debra.account_views.brand_home'))

    influencer = Influencer.objects.get(id=influencer_id)

    profile = influencer.shelf_user.userprofile if influencer.shelf_user else None

    if profile is None:
        raise Http404

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except ValueError:
            data = {}
        token = data.get('stripeToken')
        amount = int(data.get('amount', 0))
        application_fee = 0

        connect_customer_id = profile.stripe_connect_customer_id

        if not connect_customer_id:
            connect_customer_id = stripe.Customer.create(
                card=token,
                api_key=profile.stripe_access_token).id
            profile.stripe_connect_customer_id = connect_customer_id
            profile.save()

        connect_customer = stripe.Customer.retrieve(
            connect_customer_id, api_key=profile.stripe_access_token)

        try:
            stripe.Charge.create(
                amount=amount,
                application_fee=application_fee,
                currency='usd',
                customer=connect_customer.id,
                description="",
                api_key=profile.stripe_access_token,
            )
        except stripe.CardError:
            pass
        return HttpResponse()
    else:
        return render(request, 'pages/account/blogger_payment_page.html', {
            'landing_page': True,
            'stripe_key': profile.stripe_publishable_key,
            'amount': 400,
            'influencer': influencer,
            'profile': profile,
        }, context_instance=RequestContext(request))