from django.conf import settings
from debra.helpers import get_js_shelfit_code, get_server_info
from debra.constants import INTERCOM_API_SECRET, STRIPE_LIVE_PUBLISHABLE_KEY, STRIPE_TEST_PUBLISHABLE_KEY, STRIPE_COLLECTION_PLANS
from debra import constants
from masuka.image_manipulator import IMAGE_SIZES
from django.contrib.auth.forms import PasswordResetForm
import hmac, hashlib, random


def template_globals(request):
    sname = get_server_info(request)

    show_collections = False
    if request.visitor["base_brand"] and request.visitor["base_brand"].stripe_plan in STRIPE_COLLECTION_PLANS:
        show_collections = True

    data = {
        'rand': random.randint(0, 10000),
        'js_shelfit_code': get_js_shelfit_code(sname),
        'shelf_user': request.visitor["user"],
        'password_reset_form': PasswordResetForm(),
        'facebook_app_id': settings.FACEBOOK_APP_ID,
        'image_sizes': IMAGE_SIZES,
        'testing_removal': False,
        'DEBUG': settings.DEBUG,
        'STRIPE_KEY': STRIPE_TEST_PUBLISHABLE_KEY if settings.DEBUG else STRIPE_LIVE_PUBLISHABLE_KEY,
        'visitor': request.visitor,
        'constants': constants,
        'show_collections': show_collections,
        'HEROKU_RELEASE_VERSION': settings.HEROKU_RELEASE_VERSION if settings.ON_HEROKU else None,
        'ON_HEROKU': settings.ON_HEROKU,
    }
    return data


def generate_intercom_user_hash(request):
    if request.user.is_authenticated():
        return hmac.new(INTERCOM_API_SECRET, request.user.email, digestmod=hashlib.sha256).hexdigest()
    else:
        return {}
