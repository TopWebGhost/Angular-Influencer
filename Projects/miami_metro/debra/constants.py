import sys
import os
import re
import json
from StringIO import StringIO
from collections import defaultdict, OrderedDict

import pydocusign

from django.conf import settings
from django.core.urlresolvers import reverse_lazy, reverse

from servers import workers
from debra.decorators import cached_property

#####-----< Product Import Setting >------#
MIN_FOLLOWERS_TO_QUALIFY_FOR_PRODUCT_IMPORT = 500


#####-----< Intercom >-----#####
INTERCOM_API_SECRET = 'lcr3HTNH846HwygXebrUDwjV1Dz18GZZviikYwM3'


def INTERCOM_CUSTOM_DATA(up):
    from debra import account_helpers
    brand = account_helpers.get_associated_brand(up)
    has_brand = brand is not None
    influencer = account_helpers.get_associated_influencer(up)
    has_influencer = influencer is not None
    regprof = None
    try:
        regprof = up.user.registrationprofile_set.all()[0]
    except:
        pass

    company_data = None
    if has_brand:
        company_data = brand.get_intercom_company_data()

    data = {
        "is_blogger": bool(up.blog_page),
        "is_brand": has_brand or bool(up.temp_brand_domain),
        "blogger_is_active": up.user.is_active if up.blog_page else None,
        "brand_stripe_customer_created_at": brand.flag_stripe_customer_created if brand else None,
        "has_blog_verified": up.blog_verified,
        "has_brand_verified": has_brand,
        "has_influencer": has_influencer,
        "blog_url": up.blog_page,
        "blog_name": up.blog_name,
        "ready_to_invite": influencer is not None and influencer.ready_to_invite or False,
        "activation_key": regprof.activation_key if regprof else None,
        "expiration_days": settings.ACCOUNT_ACTIVATION_DAYS,
        "brand_url": brand.domain_name if brand else up.temp_brand_domain,
        "brand_name": company_data.get('name') if company_data else None,
        "plan": company_data.get('plan') if company_data else None,
        "monthly_spend": company_data.get('monthly_spend') if company_data else None,
    }
    return data

# INTERCOM_CUSTOM_DATA = lambda up: {
#     'connector_tag': up.connector_tag,
#     'popularity_rank': up.popularity_rank,
#     'quality_tag': up.quality_tag,
#     'friendly_tag': up.friendly_tag,
#     'widgets_allowed': up.widgets_privileges,
#     'blog_url': up.blog_page,
#     'collage_img': up.collage_img_url,
#     'blog_name': up.blog_name if up.blog_name else up.blog_page,
#     'normal_name': up.name if up.name else up.stripped_email,
#     'profile_url': 'http://theshelf.com{about}'.format(about=up.about_url if not up.brand else ''),
#     'admin_action': up.admin_action
# }
#####-----</ Intercom >-----#####

#####-----< Stripe >-----#####
STRIPE_TEST_PUBLISHABLE_KEY = "pk_test_6ptDKzUf60Amwh2LOjdO3TFX"
STRIPE_LIVE_PUBLISHABLE_KEY = "pk_live_LOUbXWV96HXXibXH4PPqr5d0"
STRIPE_PUBLISHABLE_KEY = STRIPE_TEST_PUBLISHABLE_KEY if settings.DEBUG else STRIPE_LIVE_PUBLISHABLE_KEY

STRIPE_TEST_SECRET_KEY = "sk_test_kEKHlC5yCZ5t9yBnkOhrOZHY"
STRIPE_LIVE_SECRET_KEY = "sk_live_rCB58iS2OX0emmoeUOz4qPlF"
STRIPE_SECRET_KEY = STRIPE_TEST_SECRET_KEY if settings.DEBUG else STRIPE_LIVE_SECRET_KEY

STRIPE_OAUTH_TEST_CLIENT_ID = "ca_7PZ3zKYLq4BC0hN3c7nHKnsq6mEuhkwO"
STRIPE_OAUTH_LIVE_CLIENT_ID = "ca_7PZ3zKYLq4BC0hN3c7nHKnsq6mEuhkwO"
STRIPE_OAUTH_CLIENT_ID = STRIPE_OAUTH_TEST_CLIENT_ID if settings.DEBUG else STRIPE_OAUTH_LIVE_CLIENT_ID

STRIPE_CONNECT_AUTHORIZE_URL = 'https://connect.stripe.com/oauth/authorize'
STRIPE_CONNECT_ACCESS_TOKEN_URL = 'https://connect.stripe.com/oauth/token'
STRIPE_API_BASE_URL = 'https://api.stripe.com/'
#####-----</ Stripe >-----#####

#####-----< ClickMeter >-----#####
CLICKMETER_BASE_URL = 'http://apiv2.clickmeter.com'
CLICKMETER_API_KEY = '225DA15B-7C92-4DD7-B28A-E13B123FCB7A'
CLICKMETER_DEFAULT_DOMAIN = 3733
CLICKMETER_DEFAULT_GROUP = 325104

CLICKMETER_DEFAULT_UTM_SOURCE = "the-shelf"
CLICKMETER_DEFAULT_UTM_MEDIUM = "the-shelf-hanes"
CLICKMETER_DEFAULT_UTM_CAMPAIGN = "the-shelf-hanes-mullen"

CLICKMETER_CHUNK_SIZE = 50

CLICKMETER_EVENTS_VERIFICATION_NUMBER = 50
CLICKMETER_STATS_LIMIT = 100 # !!! NO MORE THAN 100
# CLICKMETER_API_KEY = '4104C1D8-332C-45EF-B2B6-FBD0DF8351B4'
# CLICKMETER_DEFAULT_DOMAIN = 1794
# CLICKMETER_DEFAULT_GROUP = 263973
#####-----</ ClickMeter >-----#####


#####-----< Google API >----- #####
GOOGLE_API_SERVER_KEY = 'AIzaSyDruGgyY7SeDDds7d9ZNqnBXJfbBPBt5Js'
# GOOGLE_OAUTH_CLIENT_ID = '36452609884-o7d02ab6qrsdv19mne0j5e9tretgd99d.apps.googleusercontent.com'
# GOOGLE_OAUTH_CLIENT_SECRET = 'fBrYh8Vck9luG_HAbMp68Cyz'

#####-----</ Google API >----- #####


#####-----< DocuSign >-----#####
# DOCUSIGN_TEST_USERNAME = "suhanovpavel@gmail.com"
# DOCUSIGN_TEST_PASSWORD = "cracker1994"
# DOCUSIGN_TEST_INTEGRATOR_KEY = "EXAM-7d51229d-14e4-4a66-93ea-98c3ae3622d5"
# DOCUSIGN_TEST_TEMPLATE_ID = '8a66afbd-5da5-4126-bfb7-26f85c893c13'

DOCUSIGN_TEST_CALLBACK_URL = "http://alpha-getshelf.herokuapp.com"
DOCUSIGN_TEST_SIGNER_RETURN_URL = "http://alpha-getshelf.herokuapp.com"
DOCUSIGN_TEST_DOCUMENT_PATH = os.path.join(
    settings.PROJECT_PATH,
    # 'mymedia/site_folder/files/CopyofTheShelfBloggerCollaborationProposal.pdf'
    'mymedia/site_folder/files/new_contract_for_sab.pdf'
)
DOCUSIGN_ALLOWED_TABS = ['nameTabs', 'signHereTabs', 'initialHereTabs', 'dateSignedTabs']

DOCUSIGN_PRODUCTION_ROOT_URL = "https://na2.docusign.net/restapi/v2"
DOCUSIGN_PRODUCTION_USERNAME = "atul@theshelf.com"
DOCUSIGN_PRODUCTION_PASSWORD = "theshelf_contract_15"
DOCUSIGN_PRODUCTION_INTEGRATOR_KEY = "THES-c7e8be24-70fb-4f45-95ef-0e2fc3cf780c"
DOCUSIGN_PRODUCTION_TEMPLATE_ID = '64e1348c-8e90-459c-946c-54c69833e9da'

DOCUSIGN_TEST_ROOT_URL = "https://demo.docusign.net/restapi/v2"
DOCUSIGN_TEST_USERNAME = "atul@theshelf.com"
DOCUSIGN_TEST_PASSWORD = "duncan3064"
DOCUSIGN_TEST_INTEGRATOR_KEY = "THES-c7e8be24-70fb-4f45-95ef-0e2fc3cf780c"
DOCUSIGN_TEST_TEMPLATE_ID = '64e1348c-8e90-459c-946c-54c69833e9da'

# DOCUSIGN_DOCUMENTS = {
#     # campaign ID
#     355: {
#         # 'template_id': '3d5dffe3-5c3b-4e88-8b9b-7e4ec764315e',
#         'template_id': '64e1348c-8e90-459c-946c-54c69833e9da',
#         'documents': {
#             '43341341': {
#                 'fields': {
#                     'printed_name': lambda c: c.blogger.name,
#                     'blog_name': lambda c: c.blogger.blogname,
#                     'address1': lambda c: c.address_lines.get(1),
#                     'address2': lambda c: c.address_lines.get(2),
#                 },
#                 'name': 'Hanes Document',
#                 'page_offsets': [(3, 13), (3, 15)]
#             },
#         }
#     },
#     468: {
#         'template_id': 'bb9b937c-228c-4c58-9752-b72d5fde5fff',
#         'documents': {
#             '65341871': {
#                 'fields': {
#                     'publisher_name': lambda c: c.publisher_name,
#                 },
#                 'name': "Contractor Agreement",
#                 "page_offsets": [(3, 13), (3, 15)]
#             },
#             '32785735': {
#                 'name': 'Evite Trademark Guidelines',
#             }
#         },
#     },
#     472: {
#         'template_id': 'bb9b937c-228c-4c58-9752-b72d5fde5fff',
#         'documents': {
#             '65341871': {
#                 'fields': {
#                     'publisher_name': lambda c: c.publisher_name,
#                 },
#                 'name': "Contractor Agreement",
#                 "page_offsets": [(3, 13), (3, 15)]
#             },
#             '32785735': {
#                 'name': 'Evite Trademark Guidelines',
#             }
#         },
#     },
#     473: {
#         'template_id': 'bb9b937c-228c-4c58-9752-b72d5fde5fff',
#         'documents': {
#             '65341871': {
#                 'fields': {
#                     'publisher_name': lambda c: c.publisher_name,
#                 },
#                 'name': "Contractor Agreement",
#                 "page_offsets": [(3, 13), (3, 15)]
#             },
#             '32785735': {
#                 'name': 'Evite Trademark Guidelines',
#             }
#         },
#     },
#     475: {
#         'template_id': 'bb9b937c-228c-4c58-9752-b72d5fde5fff',
#         'documents': {
#             '46653534': {
#                 'fields': {
#                     'publisher_name': lambda c: c.publisher_name,
#                 },
#                 'name': "Contractor Agreement",
#                 # "page_offsets": [(3, 13), (3, 15)]
#             },
#             '32785735': {
#                 'name': 'Evite Trademark Guidelines',
#             }
#         },
#     },
#     479: {
#         'template_id': 'bb9b937c-228c-4c58-9752-b72d5fde5fff',
#         'documents': {
#             '46653534': {
#                 'fields': {
#                     'publisher_name': lambda c: c.publisher_name,
#                 },
#                 'name': "Contractor Agreement",
#                 # "page_offsets": [(3, 13), (3, 15)]
#             },
#             '32785735': {
#                 'name': 'Evite Trademark Guidelines',
#             }
#         },
#     },
#     'default': {
#         'documents': {
#             'default': {
#                 'fields': {
#                     'client_name': lambda c: c.campaign.client_name,
#                     'project_name': lambda c: c.campaign.title,
#                     'campaign_start_date': lambda c: c.date_start.strftime('%x'),
#                     'campaign_end_date': lambda c: c.date_end.strftime('%x'),
#                     'payment_method': lambda c: c.payment_method,
#                     'mentions_required': lambda c: c.campaign.mentions_required,
#                     'hashtags_required': lambda c: c.campaign.hashtags_required,
#                     'publisher_name': lambda c: c.publisher_name,
#                 },
#                 'name': 'The Shelf Default Document',
#                 'page_offsets': [(3, 13), (3, 15)],
#             },
#         },
#     },
# }

DOCUSIGN_SHELF_VARIABLE = 'SHELF_VAR:'

DOCUSIGN_ROOT_URL = DOCUSIGN_TEST_ROOT_URL if settings.DEBUG else DOCUSIGN_PRODUCTION_ROOT_URL
DOCUSIGN_USERNAME = DOCUSIGN_TEST_USERNAME if settings.DEBUG else DOCUSIGN_PRODUCTION_USERNAME
DOCUSIGN_PASSWORD = DOCUSIGN_TEST_PASSWORD if settings.DEBUG else DOCUSIGN_PRODUCTION_PASSWORD
DOCUSIGN_INTEGRATOR_KEY = DOCUSIGN_TEST_INTEGRATOR_KEY if settings.DEBUG else DOCUSIGN_PRODUCTION_INTEGRATOR_KEY
DOCUSIGN_TEMPLATE_ID = DOCUSIGN_TEST_TEMPLATE_ID if settings.DEBUG else DOCUSIGN_PRODUCTION_TEMPLATE_ID

DOCUSIGN_ROOT_URL = DOCUSIGN_PRODUCTION_ROOT_URL
DOCUSIGN_USERNAME = DOCUSIGN_PRODUCTION_USERNAME
DOCUSIGN_PASSWORD = DOCUSIGN_PRODUCTION_PASSWORD
DOCUSIGN_INTEGRATOR_KEY = DOCUSIGN_PRODUCTION_INTEGRATOR_KEY
DOCUSIGN_TEMPLATE_ID = DOCUSIGN_PRODUCTION_TEMPLATE_ID

#####-----</ DocuSign >-----#####

#####-----< Houdini/Mech Turk >-----#####
HOUDINI_API_KEY = 'jrcy6cqVoKYQMkDno2J5'
HOUDINI_URL = 'https://v1.houdiniapi.com'
HOUDINI_PROMO_IMAGE_TASK = "promo_ocr__1"
HOUDINI_PROMO_EMAIL_TASK = "emails_promo_info"
#####-----</ Houdini/Mech Turk >-----#####

#####-----< Host Info >-----#####
LOCALHOST = "http://127.0.0.1:8000"
PRODUCTION = "https://app.theshelf.com"
ALPHA = "http://alpha-getshelf.herokuapp.com"
MAIN_DOMAIN = ALPHA if settings.DEBUG else PRODUCTION
BLOG_DOMAIN = 'http://www.theshelf.com'
#####-----</ Host Info >-----#####

#####-----< Emails >-----#####
SUPPORT_EMAIL = "atul@theshelf.com"

ATUL_EMAILS = {'admin_email': "atul@theshelf.com", 'test_email': "atul_44@yahoo.com"}
ARTUR_EMAILS = {'admin_email': "atul@theshelf.com", 'test_email': ""}
LAUREN_EMAILS = {'admin_email': "lauren@theshelf.com", 'contact_email': "laurenj@theshelf.com", 'test_email': "our.newsletter.list@gmail.com"}
MORGAN_EMAILS = {'admin_email': "morgan@theshelf.com", 'test_email': "morgan.peterson0816@gmail.com"}
LAURA_EMAILS = {'admin_email': "walkinginmemphisinhighheels@gmail.com", 'test_email': ""}

LAUREN_FIZZANDFROSTING = {'admin_email': "lauren@fizzandfrosting.com", 'test_email': ""}
RKORKUNIAN = {'admin_email': "rkorkounian@yahoo.co", 'test_email': ""}
SIMPLYLULUDESIGN = {'admin_email': "simplyluludesign@gmail.com", 'test_email': ""}
CHICLYDDIE = {'admin_email': "chiclyddie@gmail.com", 'test_email': ""}
SOUTHERCURLSANDPEARLS = {'admin_email': "southerncurlsandpearls@gmail.com", 'test_email': ""}
LIFEWITHEMILYBLOG = {'admin_email': "emily@lifewithemilyblog.com", 'test_email': ""}
SOPHISTIFUNKBLOG = {'admin_email': "sophistifunkblog@gmail.com", 'test_email': ""}
GLITZANDGOLD = {'admin_email': "glitzandgold1@gmail.com", 'test_email': ""}
CATHIEBRADSHAWLLED = {'admin_email': "kathleen@carriebradshawlied.com", 'test_email': ""}
COFFEEBEANSANDBOBBYPINS = {'admin_email': "Coffeebeansandbobbypins@gmail.com", 'test_email': ""}
KIMBERLY = {'admin_email': 'pennypincherfashion@gmail.com', 'test_email': ""}
SABRINA_COPYWRITER = {'admin_email': 'sabrina.fenster@gmail.com', 'test_email': ""}

ADMIN_EMAILS = [ATUL_EMAILS, LAUREN_EMAILS, MORGAN_EMAILS, LAURA_EMAILS, KIMBERLY, SABRINA_COPYWRITER,
                LAUREN_FIZZANDFROSTING, RKORKUNIAN, SIMPLYLULUDESIGN, CHICLYDDIE, SOUTHERCURLSANDPEARLS,
                LIFEWITHEMILYBLOG, SOPHISTIFUNKBLOG, GLITZANDGOLD, CATHIEBRADSHAWLLED, COFFEEBEANSANDBOBBYPINS]

ALLOWED_ADMIN_VIEWERS = ['atul@theshelf.com', 'lauren@theshelf.com', 'desirae@theshelf.com', 'atul_44@yahoo.com', 'pavel@theshelf.com']
#####-----</ Emails >-----#####

MAX_CAMPAIGN_ATTACHMENT_SIZE = 40 * 1024 * 1024

#####-----< Gmail >-----#####
GMAIL_PROMOS_USERNAME = "rootofsavvypurse"
GMAIL_PROMOS_PASSWORD = 'messier78_%starbuck'
GMAIL_PROMOS_POPSERVER = "pop.gmail.com"
GMAIL_PROMOS_IMAPSERVER = 'imap.gmail.com'
#####-----</ Gmail >-----#####

#####-----< Global Names >-----#####
LIKED_SHELF = "My Likes"
DELETED_SHELF = "Deleted"
GRID_COLLAGE = "grid_collage"
SCROLLABLE_COLLAGE = "scrollable_collage"
#####-----</ Global Names >-----#####

#####-----< Brand User Placeholder >-----#####
SHELF_BRAND_USER = lambda brand_name: "theshelf@{name}.toggle".format(name=brand_name.lower())
SHELF_BRAND_PASSWORD = "johngalt1"
#####-----</ Brand User Placeholder >-----#####

#####-----< Influencer User Placeholder >-----#####
SHELF_INFLUENCER_USER = lambda blog_domain: "toggle@{name}".format(name=blog_domain.lower())
SHELF_INFLUENCER_PASSWORD = "johngalt1"
#####-----</ Influencer User Placeholder >-----#####

KARSYN_USER_ID = 358043

#####-----< Timezones >-----#####
EST = ('-5', 'America/New_York')
TIMEZONES = (
    ('-12', 'Pacific/Kwajalein'),
    ('-11', 'Pacific/Samoa'),
    ('-10', 'Pacific/Honolulu'),
    ('-9', 'America/Juneau'),
    ('-8', 'America/Los_Angeles'),
    ('-7', 'America/Denver'),
    ('-6', 'America/Mexico_City'),
    EST,
    ('-4', 'America/Caracas'),
    ('-3.5', 'America/St_Johns'),
    ('-3', 'America/Argentina/Buenos_Aires'),
    ('-2', 'Atlantic/Azores'),
    ('-1', 'Atlantic/Greenland'),
    ('0', 'Europe/London'),
    ('1', 'Europe/Paris'),
    ('2', 'Europe/Helsinki'),
    ('3', 'Europe/Moscow'),
    ('3.5', 'Asia/Tehran'),
    ('4', 'Asia/Baku'),
    ('4.5', 'Asia/Kabul'),
    ('5', 'Asia/Karachi'),
    ('5.5', 'Asia/Calcutta'),
    ('6', 'Asia/Colombo'),
    ('7', 'Asia/Bangkok'),
    ('8', 'Asia/Singapore'),
    ('9', 'Asia/Tokyo'),
    ('9.5', 'Australia/Darwin'),
    ('10', 'Pacific/Guam'),
    ('11', 'Asia/Magadan'),
    ('12', 'Asia/Kamchatka'),
)
#####-----</ Timezones >-----#####

#####-----< Generic Values >-----#####
NULL_VALUES = ["Nil", ""] # stupid, but we have random Nil's and '' floating around as None values
#####-----</ Generic Values >-----#####

#####-----< SEO Values >-----#####
SEO_VALUES = {
    'inspiration': {
        'title': "Get Your Fashion Inspiration!",
        'meta_desc': """The Inspiration Feed contains the best of the best, those items loved by top bloggers. Use the Inspiration Feed to bookmark clothes, fashion accessories and more."""
    },
    'trendsetters': {
        'title': "Trending Bloggers",
        'meta_desc': "See who's currently trending, follow top fashion bloggers you love, build your own following."
    },
    'trending_brands': {
        'title': "Trending Brands",
        'meta_desc': "Check out the brands everyone is talking about."
    },
    'shelf_home': {
        'title': "All Shelves",
        'meta_desc': "See all shelves and fashion items for a user. Shelf trendy items, build a following."
    },
    'my_shelves': {
        'title': "My Shelves",
        'meta_desc': "These are your fashion shelves. Put those products that truly inspire you into your own custom categories."
    },
    'followers': {
        'title': "Followers",
        'meta_desc': """Everyone who thinks this blogger's fashion rules supreme. Higher numbers of followers could mean more chances for campaign partnerships with brand's."""
    },
    'following': {
        'title': "Bloggers and Brands Followed",
        'meta_desc': "Every brand and person this blogger thinks is a fashionista."
    },
    'about_me': {
        'title': "Style Profile",
        'meta_desc': "Style DNA for a person. Tells their story, style tags they fall under, and links to their external sites"
    },
    'liked_items': {
        'title': "Favorite Fashion",
        'meta_desc': """Find the trending styles by exploring liked items. Everything from handbags to suitpants, from watches to skirts, liked items tells the story of everybody."""
    },
    'brand_home': {
        'title': "Brand Shelves",
        'meta_desc': "See all this brands' items that have been shelved by other bloggers. Add them to your own Shelf or just browse."
    },
    'brand_followers': {
        'title': "Brand Followers",
        'meta_desc': "Bloggers that think this brand has the coolest stuff around."
    },
    'brand_about': {
        'title': "Style Profile",
        'meta_desc': "Style DNA for a brand. Tells their story, style tags they fall under, and links to their external sites"
    },
    'seo_product_info': {
        'title': "Product Details",
        'meta_desc': "View product price, in-stock status, and more. See if your favorite blogger has shelved this fashion!"
    },
    'widgets_home': {
        'title': "Blogger Widgets | Tools",
        'meta_desc': """Build your own style collage, create a lottery to win over new followers, or use the carousel to create a scrolling panorama of your favorite fashion. When your done, embed the widget right on your blog."""
    },
    'new_lottery': {
        'title': "New Lottery",
        'meta_desc': """Create a new giveaway to promote yourself and a brand. Win over new followers, get people excited about you."""
    },
    'edit_lottery': {
        'title': "Edit Existing Lottery",
        'meta_desc': """Edit an existing lottery to add or change prizes and tasks, modify the start and | or end date of the lottery, and more."""
    },
    'preview_lottery': {
        'title': "Preview Lottery",
        'meta_desc': """See what a lottery will look like before copying a single line of code to your blog. Interact with the lottery and make sure everything looks perfect before putting your shiny new lottery onto your blogging platform"""
    },
    'lottery_analytics': {
        'title': "Lottery Analytics | Choose Winners",
        'meta_desc': """Check all lottery entries and choose the lucky winner(s) for your lottery."""
    },
    'view_lotterys': {
        'title': "Edit | Manage | Create Lotterys",
        'meta_desc': """View analytics for running or past lotteries, duplicate a successful lottery, edit the details for a created lottery, or start a new lottery and drive new traffic to your blog."""
    },
    'collage': {
        'title': "Create Your Fashion Collage",
        'meta_desc': """Show the world fashion items that you absolutely love. Share your creation on social media and on your blog"""
    },
    'embeddable': {
        'title': "A Shelf Widget",
        'meta_desc': "A widget created on theshelf.com, visit and create your own."
    }
}
#####-----</ SEO Values >-----#####


#####-----< Admin related: Atul's collections >-----#####

ATUL_COLLECTIONS_IDS = [1187, 1188, 1189, 1190, 1191, 1192, 1193]

def get_atul_collections():
    from debra.models import InfluencersGroup
    groups = InfluencersGroup.objects.filter(
        id__in=ATUL_COLLECTIONS_IDS
    ).order_by(
        'name'
    ).only(
        'id', 'name'
    )

    return map(lambda x: {'id': x.id, 'name': x.name}, groups)


#####-----</ Admin related: Atul's collections >-----#####


#####-----< Admin related: Influencer status Values >-----#####

ADMIN_TABLE_INFLUENCER_LIST = "list"
ADMIN_TABLE_INFLUENCER_FASHION = "fash"
ADMIN_TABLE_INFLUENCER_SOCIAL_HANDLE = "social"
ADMIN_TABLE_INFLUENCER_INFORMATIONS = "info"
ADMIN_TABLE_INFLUENCER_SELF_MODIFIED = "self"
ADMIN_TABLE_INFLUENCER_READY_FOR_UPGRADE = "upgrade"
ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL = "susp"
ADMIN_TABLE_INFLUENCER_SUSPICIOUS_URL_BLACKLISTED = "suspbl"

#####-----</ Admin related: Influencer status Values >-----#####


#####-----< Elastic Search Values >-----#####


# ELASTICSEARCH_URL = "http://198.199.71.215:9200"#"http://23.251.156.9:9200"
# #ELASTICSEARCH_URL = "http://104.130.31.24:9200"
# ELASTICSEARCH_INDEX = "keyword_building"

# New ES url fwith flattened mapping
ELASTICSEARCH_URL = "http://162.243.220.77:80"
#ELASTICSEARCH_INDEX = "keywords"
ELASTICSEARCH_INDEX = "posts_2016-08-02" #<= new test index
ELASTICSEARCH_TAGS_INDEX = "tags"

ELASTICSEARCH_TAGS_TYPE = 'tags_mapping'

ELASTICSEARCH_OFFSET_CACHE_TIMEOUT = 3600
ELASTICSEARCH_POP_CACHE_TIMEOUT = 3600

#####-----</ Elastic Search Values >-----#####

####-----< Search Settings >-----####
SEARCH_FLYOUT_POST_LENGTH_LIMIT = 30
####-----</ Search Settings >-----####

#####-----< Stripe plans >-----#####

# Basically, this section contains information about stripe plans, that is used
# all over the project. So, brand_flags admin table, all sorts of popups on the
# frontend, django views... they all use (or at least should use) infromation
# from here

# here we place variables which name differs from actual plan's name
# for example, 'STRIPE_PLAN_ENTERPRISE_800' and 'ENTERPRISE_PLAN_800';
# it is done for backward compatibility (those variables probably used
# over the project and we're creating variables dynamically in the code below)
CUSTOM_NAMES = (
    ('STRIPE_PLAN_CHEAP', "Cheap"),
    ('STRIPE_PLAN_BASIC', "Basic"),
    ('STRIPE_PLAN_STARTUP', "Startup"),
    ('STRIPE_PLAN_AGENCY', "Agency"),
    ('STRIPE_PLAN_ENTERPRISE', "Enterprise"),
    ('STRIPE_PLAN_ENTERPRISE_200', "ENTERPRISE_PLAN_200"),
    ('STRIPE_PLAN_ENTERPRISE_300', "ENTERPRISE_PLAN_300"),
    ('STRIPE_PLAN_ENTERPRISE_400', "ENTERPRISE_PLAN_400"),
    ('STRIPE_PLAN_ENTERPRISE_500', "ENTERPRISE_PLAN_500"),
    ('STRIPE_PLAN_ENTERPRISE_800', "ENTERPRISE_PLAN_800"),
    ('STRIPE_PLAN_AGENCY_SEAT', "Per_seat"),
)

# NOT SURE if this mistaken plan is needed
# STRIPE_PLAN_AGENCY_YEARLY_12000 = "STRIPE_PLAN_AGENCY_YEARLY_1000"


# here we will store info about all plans (amount, type etc.);
# represented by dict with plan names as keys
PLAN_INFO = {}


def get_plan_type(plan):
    """
    Return plan type (package name): 'lite', 'pro', 'custom' etc.
    @param plan - plan name (as in Stripe)
    @return - type as a lowercase string
    """
    plan = plan.upper()
    if plan == "STRIPE_PLAN_AGENCY_YEARLY_12000":
        return 'lite'
    elif plan == "STRIPE_PLAN_AGENCY_YEARLY_30000":
        return 'pro'
    elif 'AGENCY' in plan.upper():
        return 'custom'
    else:
        return 'brand'


def get_agency_extra_plans():
    """
    Return list of extra plans that should be displayed on agency pricing page
    additionally to plan choosed by admin. Also checks if all the plans listed
    are also grabbed from Stripe (if not, then such plans do not exist)
    @return - 'extra' list (empty if at least one of plans listed does not exist)
    """
    extra = ["STRIPE_PLAN_AGENCY_YEARLY_12000", "STRIPE_PLAN_AGENCY_YEARLY_30000"]
    if not all([x in STRIPE_PLANS_ALL for x in extra]):
        extra = []
    return extra


STRIPE_PLANS_FILE_PATH = os.path.join(
    settings.PROJECT_PATH,
    'debra',
    'jsons',
    'stripe_plans.json')


def sync_stripe_plans(key=None):
    """
    To update Stripe plans on production do the following:
        1) call sync_stripe_plans()
        2) git add -A .
        3) git commit -am "update stripe plans"
        4) git push origin master
        5) git push beta HEAD:master --force
    """
    import stripe
    key = key or STRIPE_LIVE_SECRET_KEY
    stripe.api_key = key
    data = stripe.Plan.all(limit=100).to_dict()
    with open(STRIPE_PLANS_FILE_PATH, 'w') as f:
        f.write(json.dumps(data['data'], indent=4))


def get_plans_from_stripe(key=None):
    """
    Doing request to Stripe API using 'key'. Dynamically creates variables for
    Stripe plans in current module. Fills PLAN_INFO with information about each
    plan ('amount', 'interval', 'type' and so on). At the same time this function
    is generator that iterates over avaliaible plans and yields each plan's id.
    @param key - specify it only if you want some specific key, otherwise it will
    choose the one depending on settings.DEBUG.
    @return - iterator over plans ids
    """
    import stripe
    key = key or STRIPE_SECRET_KEY
    with open(STRIPE_PLANS_FILE_PATH, 'r') as f:
        stripe_plans = json.loads(f.read())
    plans = [stripe.Plan.construct_from(plan, key) for plan in stripe_plans]
    for plan in CUSTOM_NAMES:
        try:
            setattr(sys.modules[__name__], plan[0], plan[1])
        except Exception:
            pass
    for plan in plans:
        # set constants in constants.py module
        try:
            setattr(sys.modules[__name__], plan.name, plan.id)
        except Exception:
            pass
        # fill PLAN_INFO with needed info from stripe
        PLAN_INFO[plan.id] = {
            'name': plan.name,
            'amount': plan.amount / 100,
            'interval': plan.interval,
            'type': get_plan_type(plan.id),
            'interval_count': plan.interval_count
        }
        yield plan.id


def get_plan_messages_count(plan):
    """
    Get number of messages per period for given plan.
    Currently only for 'brand' plans.
    @param plan - plan name
    @return - number of messages per period or None, if no such number for plan
    """
    plan_type = get_plan_type(plan)
    if plan_type == 'brand':
        # plan_messages_count = plan_amount
        return PLAN_INFO[plan]['amount']
    return None


def get_plan_views_count(plan):
    """
    Get number of extended profile views per period for given plan.
    Currently only for 'brand' and 'custom' plans.
    @param plan - plan name
    @return - number of views
    """
    plan_type = get_plan_type(plan)
    if plan_type == 'brand':
        return PLAN_INFO[plan]['amount'] * 3
    elif plan_type == 'custom':
        return PLAN_INFO[plan]['amount'] / 12


def get_plan_downloads_count(plan):
    """
    Ger number of contact list downloads for given plan.
    Currently only for 'custom' plans.
    @param plan - plan name
    @return - number of downloads
    """
    if get_plan_type(plan) == 'custom':
        # 15000 => 625/month, 20000 => 833/month, 25000 => 1041/month
        return PLAN_INFO[plan]['amount'] / 24
    return None


# fill up all plans (request to Stripe API on module load)
STRIPE_PLANS_ALL = list(get_plans_from_stripe(key=STRIPE_LIVE_SECRET_KEY))


# section of 'details' information about each type of plan
# it is a tuple of tuples, where first item in each tuple is actualy detail
# description, and other items are params for that string (could be plain values
# or callables that generate such values)

BRAND_PLAN_DETAILS = (
    ("""Access to the entire directory and all features listed below. \
        Unlimited search and search results.""",),
    ("""This pricing plan caps some of the actions within the platform. \
        Extended profile views capped at {}. Messages capped at \
        {}. Contact us if you would like to customize the \
        pricing and usage caps.""", get_plan_views_count, get_plan_messages_count),
)

_FREE_ACCESS = ("""This plan gives you FREE access to our UGC Live Stream, \
    a beta feature that we're launching soon.  This will surface all brand \
    mentions within content of the brands that you are tracking.  It will \
    surface content from blogs as well as social platforms.""",)

LITE_PLAN_DETAILS = (
    ("""The LITE plan offers all features in the PRO plan (listed below).""",),
    ("""Contact list downloads are limited to 500 contacts each month.""",),
    ("""Views of extended profiles is capped at 1000.""",),
    ("""Searches are currently uncapped.""",),
    _FREE_ACCESS,
)

PRO_PLAN_DETAILS = (
    ("""All features listed below.""",),
    ("""Unlimited contact list downloads.""",),
    ("""Unlimited profile views.""",),
    ("""Unlimited Searches.""",),
    _FREE_ACCESS,
)

CUSTOM_PLAN_DETAILS = (
    ("""This is a CUSTOM plan.  It has the same features as the PRO plan.""",),
    ("""Contact list downloads are limited to {} contacts each month. Views \
        of extended profiles is capped at {}. Searches are currently \
        uncapped.""", get_plan_downloads_count, get_plan_views_count),
    _FREE_ACCESS,
)


# just mapping

PLAN_DETAILS = {
    'brand': BRAND_PLAN_DETAILS,
    'lite': LITE_PLAN_DETAILS,
    'pro': PRO_PLAN_DETAILS,
    'custom': CUSTOM_PLAN_DETAILS,
}


def get_plan_details(plan):
    """
    Generator that generates list of details for given 'plan'
    @param plan - plan name (as in Stripe)
    @return - iterator over details for given plan
    """
    for detail in PLAN_DETAILS[plan['type']]:
        text = detail[0]
        res = text
        if len(detail) > 1:
            params = detail[1:]
            res = text.format(*[param(plan['name']) if callable(param) else param for param in params])
        yield res


# fill up details for each plan

for plan in PLAN_INFO.values():
    plan['details'] = list(get_plan_details(plan))

# virtual plans that don't exist in Stripe
LOCAL_PLANS = (
    "ONE_TIME_FEE",
)

# it is done for backward compatibility (those groups used overall of the
# project for some logic, mostly to allow/restrict smth for user with given plan)

PLAN_GROUPS = (
    "STRIPE_EMAIL_PLANS",
    "STRIPE_ANALYTICS_PLANS",
    "STRIPE_PRO_PLANS",
    "STRIPE_COLLECTION_PLANS",
    "STRIPE_SUBSCRIPTIONS_PLANS",
)

# we just filling up each group with all available plans...

for group in PLAN_GROUPS:
    setattr(sys.modules[__name__], group, STRIPE_PLANS_ALL + list(LOCAL_PLANS))


# ... except for agency plans.. only plans with 'AGENCY' word in their names go
# to this group

STRIPE_AGENCY_PLANS = tuple(filter(lambda x: 'AGENCY' in x.upper(), STRIPE_PLANS_ALL))


# map_plan_names used in many places, so just mapping to new function

map_plan_names = get_plan_type


#####-----</ Stripe plans >-----#####

EXPORT_COSTS = {
    "top_500": 35000,
    "top_1000": 50000,
    "top_500_uc": 35000,
    "top_1000_uc": 50000,
    "top_500_uc_us": 35000,
    "top_250_ny": 20000,
    "top_250_ca": 20000,
    "top_250_eu": 20000,
    "top_250_south": 20000,
    "top_500_male": 35000,
    "top_500_female": 35000,
    "custom": 375000,
}

EXPORT_COSTS = dict((key, int(value * 1.5)) for key, value in EXPORT_COSTS.items())

EXPORT_INFO = [
    {
        "export_type": "top_500",
        "title": "Top 500 Fashion Bloggers",
        "info_txt": "This list contains the top fashion bloggers in \
            our directory of over 17,000 fashion bloggers.  The rankings are \
            based on social followings, comment counts, and quality."
    },
    {
        "export_type": "top_1000",
        "title": "Top 1000 Fashion Bloggers",
        "info_txt": "This list contains the top fashion bloggers in our \
            directory of over 17,000 fashion bloggers.  The rankings are \
            based on social followings, comment counts, and quality."
    },
    {
        "export_type": "top_500_uc",
        "title": "500 Up-and-coming Fashion Bloggers",
        "info_txt": "If the top fashion bloggers are too exclusive, you can \
            download a list of bloggers who are up and coming.  They have \
            comment counts between 10-30 comments per post.  And their social \
            followings are between 1000-15,000."
    },
    {
        "export_type": "top_1000_uc",
        "title": "1000 Up-and-coming Fashion Bloggers",
        "info_txt": "If the top fashion bloggers are too exclusive, you can \
            download a list of bloggers who are up and coming.  They have \
            comment counts between 10-30 comments per post.  And their social \
            followings are between 1000-15,000."
    },
    {
        "export_type": "top_500_uc_us",
        "title": "500 (US) Up-and-coming Fashion Bloggers",
        "info_txt": "Download a list of bloggers who are up and coming, within \
            the United States.  They have comment counts between 10-30 comments \
            per post.  And their social followings are between 1000-15,000."
    },
    {
        "export_type": "top_250_ny",
        "title": "Top 250 New York Bloggers",
        "info_txt": "This location-specific list will showcase top bloggers \
            from New York (primarily NYC).  We use comment counts, social \
            followings, and engagement to calculate the rankings."
    },
    {
        "export_type": "top_250_ca",
        "title": "Top 250 California Bloggers",
        "info_txt": "This location-specific list will showcase top bloggers \
            from California.  We use comment counts, social followings, and \
            engagement to calculate the rankings."
    },
    {
        "export_type": "top_250_eu",
        "title": "Top 250 European Bloggers",
        "info_txt": "This location-specific list will showcase top bloggers \
            from Europe.  We use comment counts, social followings, and engagement \
            to calculate the rankings."
    },
    {
        "export_type": "top_250_south",
        "title": "Top 250 Southern Bloggers",
        "info_txt": "This location-specific list will showcase top bloggers \
            from the South East.  We use comment counts, social followings, \
            and engagement to calculate the rankings."
    },
    {
        "export_type": "top_500_male",
        "title": "Top 500 Male Bloggers",
        "info_txt": "This list contains the top male fashion bloggers in our \
            directory of over 17,000 fashion bloggers.  The rankings are based \
            on social followings, comment counts, and quality."
    },
    {
        "export_type": "top_500_female",
        "title": "Top 500 Women Bloggers",
        "info_txt": "This list contains the top female fashion bloggers in our \
            directory of over 17,000 fashion bloggers.  The rankings are based \
            on social followings, comment counts, and quality."
    }
]

BRAND_SUSPEND_REASONS = {
    "stripe_plan_deleted": "Your account is currently suspended because of payment issue. If you need to re-active it, please contact us.",
}

# ANALYTICS BLACKLISTED IPS

ANALYTICS_BLACKLISTED_IPS = [
    '127.0.0.1',
    '127.0.0.*', # you can use wildcard too
    '104.130.9.146', # post processing machine IP (must change this if we change this machine),
    '146.148.*.*',
    '130.211.*.*',
    '162.222.*.*',
    '107.178.*.*',
    '23.236.*.*',
]

ANALYTICS_BLACKLISTED_IPS += [str(ip) for role in workers
                              for ip in workers[role]
                              if role != 'db-second']


STREAK_TEST_API_KEY = '5cf736f7099749e49a64f137adbc407c'
STREAK_LIVE_API_KEY = '8f5feae372c04090870472f5d43a97cb'
STREAK_API_KEY = STREAK_TEST_API_KEY if settings.DEBUG else STREAK_LIVE_API_KEY
STREAK_HOST = 'https://www.streak.com/api/v1'


#####-----</ SimilarWeb />-----#####
''' SW_LOCAL_REFRESH_TTL determines the staleness tolerance for local caching, and is in seconds. '''
SW_LOCAL_REFRESH_TTL = 14400

''' SW_USER_KEY is the user key needed for API access provided by Similar Web. '''

SW_USER_KEY = '888dc7a9b68020d0f73ee30bec325698'

''' SW_INCLUDE_SUBDOMAINS indicates if subdomains should be included. '''
SW_INCLUDE_SUBDOMAINS = True

''' SW_VERSION sets which API version to use. '''
SW_VERSION = 'v1'

''' SW_API_URL is the base url that the API can be reached at (no trailing /). '''
SW_API_URL = 'https://api.similarweb.com'

''' SW_RESPONSE_FORMAT is the serialization format for responses from the API. '''
SW_RESPONSE_FORMAT = 'JSON'

#####-----</ SharedCount />-----#####
SC_API_KEY = 'f5ee1be4b58febc3d743c957eea6dbff8f062cd5'
SC_PLAN = 'plus'
SC_API_URL = 'https://{}.sharedcount.com/'.format(SC_PLAN)
SC_LOCAL_REFRESH_TTL = 14400

#####-----</ Compete />-----#####
COMPETE_TEST_API_KEY = '2b0a820b45d4e37543ee10a0edd835f7'
COMPETE_API_URL = 'https://apps.compete.com'

#####-----</ PASSWORD MANAGING />-----#####
TRIAL_PASSWORD = "test_theshelf_2234"


#####-----</ SLACK POST URL />-----#####
SLACK_POST_URL = 'https://theshelf.slack.com/services/hooks/slackbot?token=1d62fXd4KZqtFfAKGWlTPjHm'

#####-----</ JOB POSTS />-----#####
NUM_OF_IMAGES_PER_BOX = 7

#####-----</ FAKE DATA RETURNED DURING TRIAL TO AVOID SCRAPING />-----#####
FAKE_BLOGGER_DATA = {
    'name': 'Blogger Name',
    'blogname': 'Blog Title',
    'blog_url': 'http://google.com',
    'social_url': 'http://google.com',
    'description': 'Once your trial is over, this will be replaced with the real description of the influencer.'
}

FAKE_POST_DATA = {
    'title': 'Post Title',
    'url': 'http://google.com'
}


#####-----</ CONTRACT_DOCUMENTS />-----#####
def get_default_tabs(contract):
    from debra.models import Contract, BrandJobPost
    from debra.docusign import TextTab, DateSignedTab, EditTextTab

    assert type(contract) in (Contract, BrandJobPost,)

    campaign = contract.campaign

    text_tabs = []

    deliverables_start_position = (144, 349)
    deliverables_delta = 15
    deliverables_lines = [line for line in contract.deliverables_text.split('\n') if len(line) > 0]

    deliverables_text = []
    for n, line in enumerate(deliverables_lines, start=0):
        deliverables_text.append(
            dict(
                documentId='default',
                pageNumber=1,
                xPosition=deliverables_start_position[0],
                yPosition=deliverables_start_position[1] + deliverables_delta * n,
                locked=True,
                value=line,
                name='Deliverables line '.format(n + 1),
                font='arial',
                fontSize='size9',
                # width=234,
                height=11,
            )
        )

    extra_details_start_position = (144, 514)
    extra_details_delta = 15
    extra_details_lines = [line for line in (contract.post_requirements or '').split('\n') if len(line) > 0]

    extra_details_text = []
    for n, line in enumerate(extra_details_lines, start=0):
        extra_details_text.append(
            dict(
                documentId='default',
                pageNumber=1,
                xPosition=extra_details_start_position[0],
                yPosition=extra_details_start_position[1] + extra_details_delta * n,
                locked=True,
                value=line,
                name='Extra Details line '.format(n + 1),
                font='arial',
                fontSize='size9',
                # width=234,
                height=11,
            )
        )

    text_tabs.extend(deliverables_text)

    text_tabs.extend(extra_details_text)

    text_tabs.extend([
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=118,
            yPosition=106,
            locked=True,
            value='SHELF_VAR:client_name',
            name='Client Name',
            font='arial',
            fontSize='size12',
            # width=234,
            height=22,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=164,
            yPosition=136,
            locked=True,
            value='SHELF_VAR:project_name',
            name='Project Name',
            font='arial',
            fontSize='size12',
            # width=234,
            height=22,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=299,
            yPosition=198,
            locked=True,
            value='SHELF_VAR:campaign_start_date',
            name='Date Start',
            font='arial',
            fontSize='size11',
            # width=234,
            height=22,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=363,
            yPosition=198,
            locked=True,
            value='SHELF_VAR:campaign_end_date',
            name='Date End',
            font='arial',
            fontSize='size11',
            # width=234,
            height=22,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=108,
            yPosition=258,
            locked=True,
            value='SHELF_VAR:payment_method',
            name='Payment Method',
            font='arial',
            fontSize='size9',
            width=108,
            height=10,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=305,
            yPosition=258,
            locked=True,
            value='{:.2f}'.format(float(contract.negotiated_price or 0 if type(contract) == Contract else 0)),
            name='Negotiated Price',
            font='arial',
            fontSize='size9',
            # width=234,
            height=11,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=355,
            yPosition=620,
            locked=True,
            value=contract.date_start.strftime('%x'),
            name='Contract Start Date',
            font='arial',
            fontSize='size9',
            # width=234,
            height=11,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=405,
            yPosition=620,
            locked=True,
            value=contract.date_end.strftime('%x'),
            name='Contract Latest Date',
            font='arial',
            fontSize='size9',
            # width=234,
            height=11,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=212,
            yPosition=590,
            locked=True,
            value='SHELF_VAR:mentions_required',
            name='Mentions Required',
            font='arial',
            fontSize='size9',
            # width=234,
            height=11,
        ),
        dict(
            documentId='default',
            pageNumber=1,
            xPosition=419,
            yPosition=590,
            locked=True,
            value='SHELF_VAR:hashtags_required',
            name='Hashtags Required',
            font='arial',
            fontSize='size9',
            # width=234,
            height=11,
        ),
        dict(
            documentId='default',
            pageNumber=2,
            xPosition=175,
            yPosition=354,
            locked=True,
            value='SHELF_VAR:publisher_name',
            name='Publisher Name',
            font='arial',
            fontSize='size12',
            # width=234,
            height=22,
        ),
    ])

    date_signed_tabs = [
        dict(
            documentId='default',
            pageNumber=2,
            xPosition=178,
            yPosition=371,
            locked=True,
            value='',
            name='Date Signed',
            font='arial',
            fontSize='size12',
            # width=234,
            height=22,
        ),
    ]

    sign_here_tabs = [
        dict(
            documentId='default',
            pageNumber=2,
            xPosition=176,
            yPosition=299,
            name='Signature',
            tabLabel='Signature',
        ),
    ]

    tabs = {
        'textTabs': text_tabs,
        'signHereTabs': sign_here_tabs,
        'dateSignedTabs': date_signed_tabs,
    }

    return tabs


def get_default_document(contract):
    with open(DOCUSIGN_TEST_DOCUMENT_PATH, 'rb') as pdf_file:
        document = {
            'raw_document': pdf_file.read(),
            'tabs': get_default_tabs(contract),
            'documentId': 'default',
        }
    return document



usa_state_names = {
        'AK': 'Alaska',
        'AL': 'Alabama',
        'AR': 'Arkansas',
        'AS': 'American Samoa',
        'AZ': 'Arizona',
        'CA': 'California',
        'CO': 'Colorado',
        'CT': 'Connecticut',
        'DC': 'District of Columbia',
        'DE': 'Delaware',
        'FL': 'Florida',
        'GA': 'Georgia',
        'GU': 'Guam',
        'HI': 'Hawaii',
        'IA': 'Iowa',
        'ID': 'Idaho',
        'IL': 'Illinois',
        'IN': 'Indiana',
        'KS': 'Kansas',
        'KY': 'Kentucky',
        'LA': 'Louisiana',
        'MA': 'Massachusetts',
        'MD': 'Maryland',
        'ME': 'Maine',
        'MI': 'Michigan',
        'MN': 'Minnesota',
        'MO': 'Missouri',
        'MP': 'Northern Mariana Islands',
        'MS': 'Mississippi',
        'MT': 'Montana',
        'NA': 'National',
        'NC': 'North Carolina',
        'ND': 'North Dakota',
        'NE': 'Nebraska',
        'NH': 'New Hampshire',
        'NJ': 'New Jersey',
        'NM': 'New Mexico',
        'NV': 'Nevada',
        'NY': 'New York',
        'OH': 'Ohio',
        'OK': 'Oklahoma',
        'OR': 'Oregon',
        'PA': 'Pennsylvania',
        'PR': 'Puerto Rico',
        'RI': 'Rhode Island',
        'SC': 'South Carolina',
        'SD': 'South Dakota',
        'TN': 'Tennessee',
        'TX': 'Texas',
        'UT': 'Utah',
        'VA': 'Virginia',
        'VI': 'Virgin Islands',
        'VT': 'Vermont',
        'WA': 'Washington',
        'WI': 'Wisconsin',
        'WV': 'West Virginia',
        'WY': 'Wyoming'
}

usa_state_abbreviations = dict(
    (n, a) for a, n in usa_state_names.items())

def get_state_abbreviation(name):
    return dict(usa_state_abbreviations).get(
        name, usa_state_names.get(name, name))


CAMPAIGN_SECTIONS = [
    ('settings', {
        'text': 'Settings',
        'url': lambda args: reverse(
            'debra.job_posts_views.campaign_create', args=args),
    }),
    # ('load_influencers', {
    #     'text': 'Load Influencers',
    #     'url': lambda args: reverse(
    #         'debra.job_posts_views.campaign_load_influencers', args=args)
    # }),
    # ('overview', {'text': 'Overview'}),
    # ('influencer_approval', {
    #     'text': 'Influencer Approval',
    #     'url': lambda args: reverse(
    #         'debra.search_views.blogger_approval_report', args=args),
    # }),
    ('campaign_setup', {
        'text': 'Campaign Pipeline',
        'url': lambda args: reverse(
            'debra.job_posts_views.campaign_setup', args=args)
    }),
    ('reporting', {
        'text': 'Reporting',
        'url': lambda args: reverse(
            'debra.job_posts_views.campaign_report', args=args)
    }),
]


GRUBER_URLINTEXT_PAT = re.compile(ur'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')

SITE_CONFIGURATION_ID = 1


class SiteConfigurator(object):

    def __init__(self, model_id):
        self._model_id = model_id

    @cached_property
    def instance(self):
        from debra.models import SiteConfiguration
        return SiteConfiguration.objects.get(id=self._model_id)


site_configurator = SiteConfigurator(SITE_CONFIGURATION_ID)


class CountryConstants(object):

    def __init__(self):
        file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'jsons',
            'country-codes.json',
        )
        with open(file_path) as f:
            self.data = json.loads(f.read())
            self.numeric_code_2_country = {
                int(c['country-code']):c for c in self.data
            }

    def get_name_by_numeric_code(self, code):
        return self.numeric_code_2_country.get(code, {}).get('name')

    def get_point_by_numeric_code(self, code):
        return self.numeric_code_2_country.get(code, {}).get('point')

    def get_code_by_numeric_code(self, code):
        return self.numeric_code_2_country.get(code, {}).get('alpha-3')

COUNTRY_CODES = CountryConstants()

R29_CUSTOM_DATA_TAG_ID = 2048
# R29_BLOGGERS_TAG_ID = 2033
R29_BLOGGERS_TAG_ID = 1920 # tmp value
R29_BLOGGERS_QA_TAG_ID = 2038


DEFAULT_PROFILE_PIC = '/mymedia/site_folder/images/global/avatar.png'

GOOGLE_API_KEY = 'AIzaSyBnBvPARR68MNMA0Ij6yVP9f5re46aXYBY'