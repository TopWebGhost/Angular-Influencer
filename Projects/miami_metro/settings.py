# Django settings for miami_metro project.
import sys
import os
import os.path
import urlparse
import platform
from datetime import timedelta


def env_var(key, default=None):
    val = os.environ.get(key, default)
    if val in ['True', 'true']:
        val = True
    elif val in ['False', 'false']:
        val = False
    return val

WINDOWS = 'CYGWIN' in platform.system() or 'Windows' in platform.system()

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))

KICKBOX_CACHE_FILENAME = ''

## This controls if we are going to be issuing pdimport tasks
DISCOVER_NEW_INFLUENCER_USING_COMMENTS = False

DEBUG = True
AWS = False
#this is for theshelf production
if 'NEW_RELIC_APP_NAME' in os.environ.keys() and 'beta-getshelf' in os.environ['NEW_RELIC_APP_NAME']:
    DEBUG = False

#this takes care of ec2 instances
if 'HOME' in os.environ.keys() and 'ubuntu' in os.environ['HOME']:
    DEBUG = False

if 'RDS_HOSTNAME' in os.environ.keys():
    DEBUG = False
    AWS = True

LOCAL_ALWAYS_DEBUG = os.getenv('LOCAL_DEBUG')
# LOCAL_ALWAYS_DEBUG = env_var('LOCAL_DEBUG', True)
if LOCAL_ALWAYS_DEBUG:
    DEBUG = True

LOCAL_DEBUG_DB_BACKENDS = env_var('LOCAL_DEBUG_DB_BACKENDS', True)

TEMPLATE_DEBUG = DEBUG

#SENTRY_DSN = 'http://b2cd5cdb839f4547ad379bc9ee16e395:ac981e80cda449e3bbd112abe3f87ba4@0.93.148.146.bc.googleusercontent.com/2'
# SENTRY_DSN = 'https://e3d2619246384da38c79cc5cac7a7160:1adfb8ab223f46c89cd978d28666b007@sentry.io/101686'

if not LOCAL_ALWAYS_DEBUG:
    #sys.stderr.write('Non-debug mode, using sentry DSN %s\n' % SENTRY_DSN)
    # RAVEN_CONFIG = {
    #    'dsn': SENTRY_DSN,
    # }
    pass

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'OPTIONS': {
            'autocommit': True,
        },
        'USER': 'theshelfmaster',
        'PASSWORD': '&R%ny_vegas_51_best',
        'HOST': 'theshelfdbinstance.cydo4oi1ymxb.us-east-1.rds.amazonaws.com',
        'PORT': '5432',
        'NAME': 'shelfdb',
        'TEST': {
            'NAME': 'test_shelfdb',
        },
    }
}

SOUTH_TESTS_MIGRATE = False

READ_DB = 'default'
WRITE_DB = 'default'


if DEBUG:
    #DATABASES['default'] = DATABASES['staging_db']
    pass

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

WSGI_APPLICATION = "wsgi.application"

# 4 --> alpha 5 --> beta 6 --> theshelf
#
SITE_ID = 6

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.join(PROJECT_PATH, 'mymedia')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/mymedia/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(PROJECT_PATH, 'staticfiles')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Additional locations of static files
if not WINDOWS:
    STATICFILES_DIRS = (
        # Put strings here, like "/home/html/static" or "C:/www/django/static".
        # Always use forward slashes, even on Windows.
        # Don't forget to use absolute paths, not relative paths.
        # For facebook static files
        os.path.join(PROJECT_PATH, 'mymedia/site_folder/'),
    )

#print PROJECT_PATH

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'pipeline.finders.FileSystemFinder',
    'pipeline.finders.AppDirectoriesFinder',
    'pipeline.finders.PipelineFinder',
    'pipeline.finders.CachedFileFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'ts_odorxi6^zdyeut2a*g1u-%@%ia$)oyipwn1(6$ed6uip=cz'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django_mobile.loader.Loader',
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'memcached'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

MIDDLEWARE_CLASSES = (
    'sslify.middleware.SSLifyMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'middleware.CachableUserInfo',
    'middleware.AdminRestrictionForQA',
    'django.contrib.messages.middleware.MessageMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django_mobile.middleware.MobileDetectionMiddleware',
    'django_mobile.middleware.SetFlavourMiddleware',
)

SSLIFY_DISABLE_FOR_REQUEST = [
    # Allow HTTP for Mandrill web hook
    lambda request: request.get_full_path().startswith('/reply'),
    lambda request: request.get_full_path().startswith('/payment_stripe_webhook'),
]

ROOT_URLCONF = 'urls'
APPEND_SLASH = True

P3P_COMPACT = 'policyref="http://theshelf.com/privacy", CP="NON DSP COR CURa TIA"'
MIDDLEWARE_CLASSES += ('middleware.P3PHeaderMiddleware',)

if DEBUG:
    MIDDLEWARE_CLASSES = ('middleware.QueryCountDebugMiddleware',) + MIDDLEWARE_CLASSES

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(PROJECT_PATH, 'templates'),
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.i18n',
    'django.core.context_processors.static',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
    'django_facebook.context_processors.facebook',
    'django_mobile.context_processors.flavour',
    "debra.context_processors.template_globals",
    "debra.context_processors.generate_intercom_user_hash",
)

INSTALLED_APPS = (
    'longerusername',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.staticfiles',
    'collectfast', # BEFORE 'django.contrib.staticfiles' !!!
    'django.contrib.humanize',
    'django.contrib.admin',
    'debra',
    'campaigns',
    'social_discovery',
    'hanna',
    'xps',
    'gunicorn',
    'south',
    'debug_toolbar',
    'registration',
    'django_facebook',
    'django.contrib.admindocs',
    'django_mobile',
    'django_html2canvas',
    'mailchimp',
    'django_extensions',
    'django_nose',
    'widget_tweaks',
    #'raven.contrib.django.raven_compat',
    'pipeline',
    'captcha',
    'django-intercom.intercom',
    'platformdatafetcher.customblogsfetcher',
    'fixture_magic',
    'rest_framework',
    'storages',
)

if not WINDOWS: # memcached based stuff doesn't run on windows
    # INSTALLED_APPS += ('endless_pagination',)
    ENDLESS_PAGINATION_LOADING = """<div class="co_loader"><ul class="bokeh"><li></li><li></li><li></li><li></li></ul></div>"""


# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(filename)s:%(funcName)s:%(message)s'
        },
    },
    'handlers': {
        'null': {
            'level': 'INFO',
            'class': 'django.utils.log.NullHandler',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'sentry': {
            'level': 'WARNING',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins', 'sentry'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'open_facebook.api': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'servermonitoring': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'requests': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        '': {
            'handlers': ['sentry', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    }
}

if LOCAL_ALWAYS_DEBUG:
    if LOCAL_DEBUG_DB_BACKENDS:
        LOGGING['loggers']['django.db.backends'] = {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        }
    LOGGING['handlers']['console']['level'] = 'DEBUG'


from kombu import Queue


# http://stackoverflow.com/questions/25320200/sentry-logging-in-django-celery-stopped-working
# This string is for using Sentry logging with celery asynchronous tasks
# CELERYD_HIJACK_ROOT_LOGGER = False


'''
Instructions to set up rabbit

/opt/rabbitmq/sbin/rabbitmqctl add_user shelf_rabbit_q superfastqueue
/opt/rabbitmq/sbin/rabbitmqctl list_queues -p /theshelf
/opt/rabbitmq/sbin/rabbitmqctl add_vhost /theshelf
/opt/rabbitmq/sbin/rabbitmqctl set_permissions -p /theshelf shelf_rabbit_q ".*" ".*" ".*"
/opt/rabbitmq/sbin/rabbitmqctl set_user_tags shelf_rabbit_q management

'''
# Pointing to GCE's rabbitmq
BROKER_HOST = "130.211.172.204"

BROKER_PORT = 5672
BROKER_USER = "shelf_rabbit_q"
BROKER_PASSWORD = "superfastqueue"
BROKER_VHOST = "/theshelf"

BROKER_HEARTBEAT = 10

CELERYD_CONCURRENCY = 2

CELERYD_PREFETCH_MULTIPLIER = 1

CELERY_SEND_TASK_ERROR_EMAILS = False

CELERY_ACCEPT_CONTENT = ['pickle', 'json']

# Expire result messages in 1 hour. Don't keep them in RabbitMQ for a full day.
CELERY_TASK_RESULT_EXPIRES = timedelta(hours=1)

# To prevent memory leaks
CELERYD_MAX_TASKS_PER_CHILD = 1000

CELERY_SEND_EVENTS = False

CELERY_EVENT_QUEUE_TTL = 90 # Delete celeryev messages after 1.5 minutes

# Name and email addresses of recipients
ADMINS = (
    ("Atul Singh", "atul@theshelf.com"),
    ('Pavel', 'pavel@theshelf.com'),
    # ("Vladimir", "mukhin.vladimir@googlemail.com"),
)

SERVER_EMAIL = "atul@theshelf.com"

CELERY_IMPORTS = (
                  "debra.bookmarklet_views",
                  "masuka.image_manipulator",
                  "hanna.scripts",
                  "hanna.import_from_blog_post",
                  "angel.price_tracker",
                  "quinn.manager",
                  "masuka.profile_info_extraction",
                  "platformdatafetcher.fetchertasks",
                  "platformdatafetcher.sponsorshipfetcher",
                  "platformdatafetcher.customblogs",
                  "platformdatafetcher.platformextractor",
                  "platformdatafetcher.emailextractor",
                  "platformdatafetcher.postprocessing",
                  "platformdatafetcher.pdimport",
                  "platformdatafetcher.platformcleanup",
                  "platformdatafetcher.blognamefetcher",
                  "platformdatafetcher.estimation",
                  "platformdatafetcher.contentclassification",
                  "platformdatafetcher.postinteractionsfetcher",
                  "platformdatafetcher.scrapingfetcher",
                  "platformdatafetcher.langdetection",
                  "platformdatafetcher.contenttagging",
                  "platformdatafetcher.suspicions",
                  "platformdatafetcher.feeds",
                  "platformdatafetcher.postanalysis",
                  "platformdatafetcher.producturlsextractor",
                  "platformdatafetcher.blogvisitor",
                  "platformdatafetcher.lifecycletest",
                  "platformdatafetcher.videohostingfetcher",
                  "platformdatafetcher.crawl_campaign_influencers",
                  "xpathscraper.promosearch",
                  "debra.account_helpers",
                  "debra.dataexport_views",
                  "debra.mongo_utils",
                  "debra.analytics_report",
                  "debra.admin_reports",
                  "social_discovery.twitter_crawl",
                  "social_discovery.instagram_crawl",
                  "debra.influencer_checks",
                  "debra.admin_helpers",
                  "debra.scripts",
                  "debra.brand_helpers",
                  "debra.celery_status_checker",
                  "social_discovery.create_influencers",
                  "social_discovery.spider",
                  "social_discovery.tasks",
                  "social_discovery.upgraders",  # personal task(s) for upgraders
                  "social_discovery.profile_statistics",
)

DAILY_FETCHED_PLATFORMS = [
    'Wordpress',
    'Blogspot',
    'Facebook',
    'Instagram',
    'Twitter',
    'Pinterest',
    'Tumblr',
    'Custom',
    'Youtube',
]


def _every_day_daily_queue(pl):
    return Queue('every_day.fetching.%s' % pl,
                 routing_key='every_day.fetching.%s' % pl,
                 queue_arguments={'x-message-ttl': 24 * 3600 * 1000})


def _first_fetch_daily_queue(pl):
    return Queue('first_fetch.fetching.%s' % pl,
                 routing_key='first_fetch.fetching.%s' % pl,
                 queue_arguments={'x-message-ttl': 24 * 3600 * 1000})


def _infrequent_daily_queue(pl):
    return Queue('infrequent.fetching.%s' % pl,
                 routing_key='infrequent.fetching.%s' % pl,
                 queue_arguments={'x-message-ttl': 24 * 3600 * 1000})


def _indepth_queue(pl):
    return Queue('indepth_fetching.%s' % pl,
                 routing_key='indepth_fetching.%s' % pl)


CELERY_QUEUES = tuple([_every_day_daily_queue(pl) for pl in DAILY_FETCHED_PLATFORMS] +
                      [_first_fetch_daily_queue(pl) for pl in DAILY_FETCHED_PLATFORMS] +
                      [_infrequent_daily_queue(pl) for pl in DAILY_FETCHED_PLATFORMS] +
                      [_indepth_queue(pl) for pl in DAILY_FETCHED_PLATFORMS] +
                      [
                          _every_day_daily_queue('Gplus'),
                          _every_day_daily_queue('Bloglovin'),
                          _first_fetch_daily_queue('Gplus'),
                          _first_fetch_daily_queue('Bloglovin'),
                          _infrequent_daily_queue('Gplus'),
                          _infrequent_daily_queue('Bloglovin'),
                      ] +
                      [
                          Queue('platform_data_postprocessing',
                                routing_key='platform_data_postprocessing',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('platform_data_postprocessing_blocking',
                                routing_key='platform_data_postprocessing_blocking',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('platform_data_content_estimation',
                                routing_key='platform_data_content_estimation',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('platform_extraction',
                                routing_key='platform_extraction',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('blog_visit',
                                routing_key='blog_visit',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('pdimport',
                                routing_key='pdimport',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('denormalization',
                                routing_key='denormalization',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('denormalization_slow',
                                routing_key='denormalization_slow',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('import_products_from_post_latest',
                                routing_key='import_products_from_post_latest',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('post_image_upload_worker',
                                routing_key='post_image_upload_worker',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('twitter_discover_influencer',
                                routing_key='twitter_discover_influencer',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('instagram_discover_influencer',
                                routing_key='instagram_discover_influencer',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('twitter_update_profile_details',
                                routing_key='twitter_update_profile_details',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('instagram_update_profile_details',
                                routing_key='instagram_update_profile_details',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('twitter_import_from_mention',
                                routing_key='twitter_import_from_mention',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('instagram_import_from_mention',
                                routing_key='instagram_import_from_mention',
                                queue_arguments={'x-message-ttl': 24 * 3600 * 1000}),

                          Queue('instagram_feed_scraper',
                                routing_key='instagram_feed_scraper'),

                          Queue('create_influencers_from_instagram',
                                routing_key='create_influencers_from_instagram'),
                       ])


CELERY_ROUTES = {
                 "debra.bookmarklet_views.postprocess_new_wishlistitem": {"queue:": "update_product_price"},
                 "angel.price_tracker.update_product_price": {"queue": "update_product_price"},
                 "platformdatafetcher.sponsorshipfetcher.search_for_sponsorship": {"queue": "sponsorship_fetching"},
                 "xpathscraper.promosearch.process_brand": {"queue": "promo_search"},
                 "platformdatafetcher.platformextractor.extract_platforms_from_platform": {"queue": "platform_extraction"},
                 "platformdatafetcher.pdimport.submit_import_blogurlsraw_tasks": {"queue": "pdimport"},
                 "platformdatafetcher.postprocessing.submit_daily_postprocessing_tasks": {"queue": "submit_daily_postprocessing_tasks"},
                 "social_discovery.instagram_crawl.scrape_instagram_feeds": {"queue": "instagram_feed_scraper"},
}

from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {

    "daily-tasks-submission": {
        "task": 'platformdatafetcher.postprocessing.submit_daily_postprocessing_tasks',
        "schedule": crontab(minute="0", hour="7"),
        "args": (),
    },
    "daily-automatic-blog-verify": {
        "task": 'debra.account_helpers.automatic_blog_verify',
        "schedule": crontab(minute="0", hour="5"),
        "args": (),
    },
    #"daily-generate_health_report": {
    #    "task": 'platformdatafetcher.postprocessing.generate_health_report',
    #    "schedule": crontab(minute="0", hour="6", day_of_week='sun'),
    #    "args": (),
    #},

    "weekly-denormalize_brands": {
        "task": 'platformdatafetcher.postprocessing.denormalize_brands',
        "schedule": crontab(minute='0', hour='5', day_of_week='sun'),
        "args": (),
    },
    #"daily_pdo_report": {
    #    "task": "platformdatafetcher.postprocessing.send_pdo_stats_email",
    #    "schedule": crontab(minute='0', hour='8'),
    #    "args": (),
    #},
    #"daily_posts_report": {
    #    "task": "platformdatafetcher.postprocessing.send_daily_posts_stats_email",
    #    "schedule": crontab(minute='30', hour='8'),
    #    "args": (),
    #},
    "duplicates_report": {
        "task": "debra.admin_reports.duplicates_report",
        "schedule": crontab(minute='0', hour='2', day_of_week='sun'),
        "args": (),
    },
    "lifecycletest_seq": {
        "task": "platformdatafetcher.lifecycletest.test_sequential_processing",
        "schedule": crontab(minute='30', hour='1'),
        "args": (),
    },
    "lifecycletest_normal_start": {
        "task": 'platformdatafetcher.lifecycletest.start_normal_test',
        "schedule": crontab(minute='0', hour='3', day_of_week='sun'),
        "args": (),
    },
    "lifecycletest_normal_check": {
        "task": 'platformdatafetcher.lifecycletest.check_normal_test_status',
        "schedule": crontab(minute='5', hour='3'),
        "args": (),
    },
    "verify_influencers_show_on_search": {
        "task": 'debra.influencer_checks.verify_show_on_search',
        "schedule": crontab(minute='15', hour='3', day_of_week='sun'),
        "args": (),
    },
    "daily_check_email_for_advertising_or_collaborations": {
      "task": "debra.influencer_checks.check_email_for_advertising_or_collaborations",
      "schedule": crontab(minute='0', hour='4'),
      "args": (),
    },
    #"crawl_instagram_feed": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
        # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (),
    #},
    "categorize_influencers_weekly": {
        "task": 'platformdatafetcher.categorization.categorize_all_influencers',
        "schedule": crontab(minute='0', hour="2", day_of_week='sat'),
        "args": (),
    },
    "run_social_duplicate_detection_monthly": {
        "task": 'debra.influencer_checks.create_social_platform_duplicates_influencer_checks',
        "schedule": crontab(minute=0, hour="3", day_of_month='1'),
        "args": (),
    },
    #"crawl_instagram_feed_fashion": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
    #    # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['fashion_hashtags'], 20),
    #},

    # "crawl_instagram_feed_singapore": {
    #     "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
    #     # execute this every 4 hours
    #     "schedule": crontab(minute='0', hour="*/1"),
    #     "args": (None, ['singapore'], 20),
    # },
    # Using new Crawler to perform SEA Instagram feeds
    "crawl_instagram_feed_singapore": {
        "task": 'social_discovery.tasks.crawler_create_new_sea_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform Australia Instagram feeds
    "crawl_instagram_feed_australia": {
        "task": 'social_discovery.tasks.crawler_create_new_australia_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform Canada Instagram feeds
    "crawl_instagram_feed_canada": {
        "task": 'social_discovery.tasks.crawler_create_new_canada_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform Travel Instagram feeds
    "crawl_instagram_feed_travel": {
        "task": 'social_discovery.tasks.crawler_create_new_travel_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },

    # Using new Crawler to perform fashion Instagram feeds
    "crawl_instagram_feed_fashion": {
        "task": 'social_discovery.tasks.crawler_create_new_fashion_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform decor Instagram feeds
    "crawl_instagram_feed_decor": {
        "task": 'social_discovery.tasks.crawler_create_new_decor_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform menfashion Instagram feeds
    "crawl_instagram_feed_menfashion": {
        "task": 'social_discovery.tasks.crawler_create_new_menfashion_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform food Instagram feeds
    "crawl_instagram_feed_food": {
        "task": 'social_discovery.tasks.crawler_create_new_food_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform mommy Instagram feeds
    "crawl_instagram_feed_mommy": {
        "task": 'social_discovery.tasks.crawler_create_new_mommy_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform mommy Instagram feeds
    "crawl_instagram_feed_german": {
        "task": 'social_discovery.tasks.crawler_create_new_german_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform mommy Instagram feeds
    "crawl_instagram_feed_lifestyle": {
        "task": 'social_discovery.tasks.crawler_create_new_lifestyle_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Using new Crawler to perform mommy Instagram feeds
    "crawl_instagram_feed_fitness": {
        "task": 'social_discovery.tasks.crawler_create_new_fitness_profiles',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/4"),
        "args": (None, 20),
    },
    # Sending statistics email for performed emails
    "send_statistics_email": {
        "task": 'social_discovery.profile_statistics.send_statistics_email',
        # execute this at 01:00 daily
        "schedule": crontab(minute='0', hour="1"),
        "args": (),
    },

    # Checking statuses of Celery on machines and sending mail if some is shut down.
    "check_celery_statuses": {
        "task": 'debra.celery_status_checker.check_celery_statuses',
        # execute this every 1 hours
        "schedule": crontab(minute='0', hour="*/1"),
        "args": (),
    },

    # Checking statuses of ElasticSearch cluster and sending mail if any node is shut down.
    "check_es_cluster_status": {
        "task": 'debra.es_status_checker.check_es_cluster_status',
        # execute this every 1 hours
        "schedule": crontab(minute="*/30", hour="*"),
        "args": (),
    },

    # Checking if all production Influencers are indexed.
    "check_production_influencers": {
        "task": 'debra.es_status_checker.check_old_show_on_search_influencers',
        # execute this at 08:00 daily
        "schedule": crontab(minute="0", hour="8"),
        "args": (),
    },

    # Re-crawling campaign-involved influencers for new blog and social posts
    "submit_recrawl_campaigns_tasks": {
        "task": 'platformdatafetcher.crawl_campaign_influencers.submit_recrawl_campaigns_tasks',
        # execute this every day at 10 AM and 10 PM
        "schedule": crontab(minute='0', hour="10,22"),
        "args": (),
    },

    # Adding campaign posts to their collections
    "campaign_posts_to_collections_batch_performer": {
        "task": 'platformdatafetcher.crawl_campaign_influencers.campaign_posts_to_collections_batch_performer',
        # execute this every day at 10AM and 6PM
        "schedule": crontab(minute='0', hour="10,18"),
        "args": (),
    },

    # Adding campaign posts to their collections
    "reindex_unindexed_posts": {
        "task": 'debra.influencer_checks.reindex_unindexed_posts',
        # execute this every day at 01AM
        "schedule": crontab(minute='0', hour="1"),
        "args": (),
    },

    #"crawl_instagram_feed_fashion_brands": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
        # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['fashion_brands'], 20),
    #},
    #"crawl_instagram_feed_travel": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
        # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['travel_hashtags'], 20),
    #},
    #"crawl_instagram_feed_video": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
    #    # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['video_hashtags'], 20),
    #},
    #"crawl_instagram_feed_canada": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
        # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['canada'], 20),
    #},
    #"crawl_instagram_feed_hongkong": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
        # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['hongkong'], 20),
    #},
    #"crawl_instagram_feed_india": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
    #    # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['india'], 20),
    #},
    #"crawl_instagram_feed_beauty": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
    #    # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['beauty_hashtags'], 20),
    #},
    #"crawl_instagram_feed_food": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
        # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['food_hashtags'], 20),
    #},
    #"crawl_instagram_feed_decor": {
    #    "task": 'social_discovery.instagram_crawl.scrape_instagram_feeds',
        # execute this every 4 hours
    #    "schedule": crontab(minute='0', hour="*/2"),
    #    "args": (None, ['decor_hashtags'], 20),
    #},
    #"check-invariants": {
    #    "task": 'platformdatafetcher.invariants.check_invariants',
    #    "schedule": crontab(minute='0', hour='3'),
    #    "args": (),
    #},
    "send_missing_emails": {
       "task": 'debra.brand_helpers.send_missing_emails',
       "schedule": timedelta(hours=24),
       "args": (),
    },
    "bulk_update_campaigns_tracking_stats": {
       "task": 'debra.account_helpers.bulk_update_campaigns_tracking_stats',
       "schedule": timedelta(hours=12),
       "args": (),
    },
    "update_bloggers_cache_data": {
       "task": 'debra.tasks.update_bloggers_cache_data',
       "schedule": crontab(minute='0', hour=4),
       "args": (),
    },
    "crawl_contract_influencers": {
       "task": 'debra.account_helpers.crawl_contract_influencers',
       "schedule": crontab(minute='0', hour=3),
       "args": (),
    },

    # Sending daily report about platforms .
    "send_fetched_platforms_report": {
        "task": 'debra.tasks.send_fetched_platforms_report',
        # execute this every day at 0:05
        "schedule": crontab(minute=5, hour=0),
        "args": (),
    },

    # this calls the worker to issue connecting tasks
    "connect_instagram_profiles_to_infs":{
        "task": "social_discovery.tasks.task_connect_instagramprofile_to_influencers",
        "schedule": crontab(minute=2, hour=6),
        "args": (None, None, 1000, 5000, None)
    },

    "reprocess_instagram_profiles": {
        "task": 'social_discovery.tasks.reprocess_instagram_profiles',
        "schedule": crontab(minute=0, hour=1, day_of_month='*/16'),
        "args": (),
    },

}

PERFORMANCE_DEBUGGING = env_var('PERFORMANCE_DEBUGGING', False)

def custom_show_toolbar(request):
    #return True # Always show toolbar, for example purposes only.
    if PERFORMANCE_DEBUGGING and DEBUG:
        return True
    else:
        return False

DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
    'SHOW_TOOLBAR_CALLBACK': custom_show_toolbar,
}


'''
    django-registration-related
'''
ACCOUNT_ACTIVATION_DAYS = 7
'''
    Email settings for django-registration
'''
EMAIL_HOST = 'smtp.1and1.com' # 'smtp.gmail.com'
EMAIL_HOST_USER = 'no-reply@getshelf.com' # 'rootofsavvypurse@gmail.com'
EMAIL_HOST_PASSWORD = 'shubhkamna'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'lauren@theshelf.com' # 'rootofsavvypurse@gmail.com'

LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/'


'''
    FB integration for alpha-shelf.herokuapp.com
'''
FACEBOOK_APP_ID = '368356726554767' if not DEBUG else '373652826104203'
FACEBOOK_APP_SECRET = 'fb0673f9e73bcf8a36f216769d7065f3' if not DEBUG else '83105b6f5b9136c56c69ba2c57c9995f'
FACEBOOK_HIDE_CONNECT_TEST = True


AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'django_facebook.auth_backends.FacebookBackend',
)
AUTH_PROFILE_MODULE = 'debra.UserProfile'


'''
    AWS keys
'''
AWS_KEY = 'AKIAJYJDNH3B4757RTRA'
AWS_PRIV_KEY = 'm01BHnNU/ys4C5JcSIa0F6ozYIRmjqQqRGwHAxJ0'


# HERE WE OVERRIDE STATIC AND MEDIA FOR PRODUCTION

# these are for static bucket 'django-storages'
AWS_STORAGE_BUCKET_NAME = 'theshelf-static-files'
AWS_ACCESS_KEY_ID = AWS_KEY
AWS_SECRET_ACCESS_KEY = AWS_PRIV_KEY
AWS_HEADERS = {  # see http://developer.yahoo.com/performance/rules.html#expires
    'Expires': 'Thu, 31 Dec 2099 20:00:00 GMT',
    'Cache-Control': 'max-age=94608000',
}
AWS_QUERYSTRING_AUTH = False

# Tell django-storages that when coming up with the URL for an item in S3 storage, keep
# it simple - just use this domain plus the path. (If this isn't set, things get complicated).
# This controls how the `static` template tag from `staticfiles` gets expanded, if you're using it.
# We also use it in the next setting.
AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME


MAILCHIMP_API_KEY = 'c83cc81633bb09ca085aab480ca72943-us4'
MANDRILL_API_KEY = '096301cd-b703-4061-b3f6-0b862e2f63a1'
MANDRILL_ADMIN_EMAIL_API_KEY = 'hAirPgfh5N5oCQ4fnPnHBA'

DISQUS_API_KEY = 'gW8w5Hnon4LdMMR9TlhRYEj3UfKmd2hCJXtrKclkHFAT6wZ0my6dtMwqtBsflabj'
DISQUS_API_SECRET = 'aMeiiM1lJoFKNShJU5GeWkmVhIK77ADiY0toILREx31X4k6CVv1OVaLvuumHejKf'
DISQUS_URL_PREFIX = 'https://disqus.com/api/3.0/'


TWITTER_OAUTH_TOKEN = '1411425830-QW09BJs2lcQg3UOlabSjAa2DBdfQdlK6fIEKSqL'
TWITTER_OAUTH_SECRET = '2pypLc8ea80Ue6EqBbgL4O9QTWdYtQeN6JsdcW7mXieoa'
TWITTER_CONSUMER_KEY = 'EUOyYO9RQ4KL6PjS3osZmQ'
TWITTER_CONSUMER_SECRET = 'lx1qtzdGUYKj57JwGFvSUGKu7yQEFR3hXpJIUM7Bs'
TWITTER_USER_URL_TEMPLATE = 'https://twitter.com/{screen_name}'
TWITTER_TWEET_URL_TEMPLATE = 'https://twitter.com/{screen_name}/status/{id}'
TWITTER_INVALID_SCREEN_NAMES = ['share']


INSTAGRAM_CLIENT_ID = 'b6d5ce879d9d4c46af4d7f02f2100d2c'
INSTAGRAM_CLIENT_SECRET = 'c4ae26052a424be4879c67122d16de4d'
INSTAGRAM_WAIT_AFTER_LIMIT_EXCEEDED = 60


FACEBOOK_BASE_URL = 'https://graph.facebook.com'
FACEBOOK_WAIT_AFTER_LIMIT_EXCEEDED = 60


PINTEREST_RESULTS_POLL_SLEEP = 2
PINTEREST_RESULTS_POLL_MAX_ITERATIONS = 3
PINTEREST_INVALID_USER_TEXT = "We couldn't find that page"
PINTEREST_UNWANTED_POSTFIXES = ['/boards', '/pins']


COMPANY_ADDRESS = '200 Hoover Avenue, Las Vegas, NV 89101'

TEST_RUNNER = 'tests.runner.PytestTestRunner'


USE_S3 = env_var('USE_S3', not DEBUG)

###############################
### Django Pipeline Configs
###############################
# PIPELINE_COMPILERS = (
#   'debra.pipeline_compilers.AngularTemplateCompiler',
# )

PIPELINE_ENABLED = USE_S3
PIPELINE_JS = {
    'core_head': {
        'source_filenames': (
            'js/vendor/less-1.4.1.js',
            'js/vendor/spoiler.min.js',
        ),
        'output_filename': 'js/prod/core_head.js',
    },
    'page': {
        'source_filenames': (
            'js/page_scripts.js',
        ),
        'output_filename': 'js/prod/page.js',
    },
    'pdf_view': {
        'source_filenames': (
            'js/vendor/pdf.js',
            'js/vendor/compatibility.js',
            # 'js/vendor/pdf.worker.js',
        ),
        'output_filename': 'js/prod/pdf.js',
    },
    # 'pdf_worker': {
    #     'source_filenames': (
    #         'js/vendor/pdf.worker.js',
    #     ),
    #     'output_filename': 'js/prod/pdf.worker.js',
    # },
    'core': {
        'source_filenames': (
            'js/vendor/google-client.js',
            'js/vendor/underscore-min.js',
            'js/vendor/tinybox.js',
            'js/vendor/jquery.placeholder.js',
            'js/vendor/bootstrap.js',
            'js/vendor/bootstrap-affix.js',
            'js/vendor/bootstrap-popover.js',
            'js/vendor/jquery.tipTip.js',
            'js/vendor/jquery.cookie.js',
            'js/vendor/jquery.validate.js',
            'js/vendor/intro_js/intro.js',
            'js/vendor/imagesloaded.pkgd.js',
            'js/vendor/jquery.nanoscroller.js',
            'js/vendor/jquery.browser.min.js',
            'js/vendor/modernizr.custom.63321.js',
            'js/vendor/modernizr.custom.17475.js',
            'js/vendor/jquery.Jcrop.js',
            'js/vendor/jquery.fittext.js',
            'js/vendor/jquery.disablescroll.js',
            'js/vendor/jquery-ui-1.10.3.custom.min.js',
            'js/vendor/jquery.tipsy.js',
            'js/app/protos/helpers.js',
            'js/app/protos/lightbox.js',
            'js/app/protos/image_manipulator.js',
            'js/app/protos/loader.js',
            'js/app/protos/feed.js',
            'js/app/on_imgload.js',
            'js/app/common.js',
            'js/vendor/jquery.imgareaselect.min.js',
            'js/vendor/jquery.hotkeys.js',
            'js/vendor/google-code-prettify/prettify.js',
            'js/vendor/bootstrap-wysiwyg.js',
            'js/vendor/moment.min.js',
            'js/vendor/daterangepicker.js',
            'js/vendor/intlTelInput.js',
            'js/vendor/utils.js',
            'js/vendor/jquery.ba-throttle-debounce.js',
            'js/vendor/d3.js',
            'js/vendor/topojson.js',
            'js/vendor/datamaps.all.js',
            'js/vendor/c3.js',
            'js/vendor/interact.min.js',
            'js/vendor/rrule.js',
            'js/vendor/masonry.pkgd.js',
            # 'js/vendor/pdf.js',
            # 'js/vendor/pdf.worker.js',
        ),
        'output_filename': 'js/prod/core.js',
    },
    'angular_core': {
        'source_filenames': (
            # 'js/angular/**/*.html',
            'js/angular/angular.min.js',
            'js/angular/angular-animate.min.js',
            'js/angular/angular-file-upload.min.js',
            'js/angular/ui-utils.min.js',
            'js/angular/ui-bootstrap-tpls.js',
            'js/angular/angular-pdf.js',
            'js/angular/angular-resource.min.js',
            'js/angular/bindonce.js',
            'js/angular/angular-dropdowns.min.js',
            'js/angular/angular-datepicker.min.js',
            'js/angular/restangular.js',
            # 'js/angular/angular-ui-router.js',
            # 'js/angular/angular-ui-router_1.0.0-beta.1.js',
            'js/angular/angular-ui-router_0.3.1.js',
            'js/angular/isteven-multi-select.js',
            # 'js/angular/gapi.js',
            'js/angular/international-phone-number.js',
            'js/angular/angular-toggle-switch.js',
            'js/angular/angular-tablescroll.js',
            'js/angular/fsm-sticky-header.js',
            'js/angular/ng-daterange.js',
            'js/angular/nsPopover.js',
            'js/angular/textAngular-rangy.min.js',
            'js/angular/textAngular-sanitize.min.js',
            'js/angular/textAngular.min.js',
            'js/angular/angular-bind-html-compile.js',
            'js/angular/ngModelOptions.js',
            'js/angular/fixed-table-header.js',
            'js/angular/angular-scrollable-table.js',
            'js/angular/angular-masonry.js',
            'js/angular/c3-angular.js',
            'js/angular/angular-bootstrap-calendar-tpls.min.js',
            'js/angular/bootstrap-colorpicker-module.min.js',
            # 'js/angular/angular-masonry-directive.js',

            # APP
            # 'js/angular/third-party-modules.js',
            # 'js/angular/app/main.js',
            # 'js/angular/app/blogger_info_popup_services.js',
            # 'js/angular/components/js/components.js',
            # 'js/angular/app/img_upload.js',
            # 'js/angular/app/product_feeds.js',
            # 'js/angular/app/contact_form.js',
            # 'js/angular/app/services.js',
            # 'js/angular/app/popup_directives.js',
            # 'js/angular/app/factories.js',
            # 'js/angular/app/filters.js',
        ),
        'output_filename': 'js/prod/angular-core.js',
    },
    'angular_app': {
        'source_filenames': (
            'js/angular/third-party-modules.js',
            'js/angular/app/main.js',
            'js/angular/app/blogger_info_popup_services.js',
            'js/angular/components/js/components.js',
            'js/angular/app/img_upload.js',
            'js/angular/app/product_feeds.js',
            'js/angular/app/contact_form.js',
            'js/angular/app/services.js',
            'js/angular/app/popup_directives.js',
            'js/angular/app/factories.js',
            'js/angular/app/filters.js',
        ),
        'output_filename': 'js/prod/angular-app.js',
    },
    'angular_about': {
        'source_filenames': (
            'js/angular/app/about.js',
            'js/vendor/datepicker/js/bootstrap-datepicker.js',
        ),
        'output_filename': 'js/prod/angular-about.js',
    },
    'angular_blogger': {
        'source_filenames': (
            'js/angular/app/blogger.js',
            'js/vendor/salvattore.js',
            'js/angular/app/blogger_info_popup.js',
        ),
        'output_filename': 'js/prod/angular-blogger.js',
    },
    'angular_dataexport': {
        'source_filenames': (
            'js/angular/app/dataexport.js',
        ),
        'output_filename': 'js/prod/angular-dataexport.js',
    },
    'angular_jobposts': {
        'source_filenames': (
            'js/vendor/datepicker/js/bootstrap-datepicker.js',
            'js/angular/app/job_posts.js',
            'js/vendor/salvattore.js',
            'js/angular/app/blogger_info_popup.js',
        ),
        'output_filename': 'js/prod/angular-jobposts.js',
    },
    'angular_saved_searches': {
        'source_filenames': (
            'js/vendor/datepicker/js/bootstrap-datepicker.js',
            'js/angular/app/job_posts.js',
            'js/vendor/salvattore.js',
            'js/angular/app/blogger_info_popup.js',
            'js/angular/app/brand_dashboard.js',
            'js/angular/app/search.js',
            'js/angular/app/brand_nav.js',
        ),
        'output_filename': 'js/prod/angular-saved-searches.js',
    },
    'angular_campaign': {
        'source_filenames': (
            'js/angular/campaign/js/campaign.js',
        ),
        'output_filename': 'js/prod/angular-campaign.js',
    },
    'angular_invite_apply': {
        'source_filenames': (
            'js/angular/app/invite_apply.js',
        ),
        'output_filename': 'js/prod/angular-invite.js',
    },
    'angular_search': {
        'source_filenames': (
            'js/angular/app/blogger.js',
            'js/vendor/salvattore.js',
            'js/angular/app/blogger_info_popup.js',
            'js/angular/app/search.js',
            'js/angular/app/search_posts.js',
            'js/vendor/jquery.dataTables.min.js',
            'js/angular/app/brand_settings.js',
        ),
        'output_filename': 'js/prod/angular-search.js',
    },
    'angular_dashboard': {
        'source_filenames': (
            'js/angular/app/brand_dashboard.js',
            'js/angular/app/search.js',
            'js/vendor/salvattore.js',
            'js/angular/app/blogger_info_popup.js',
        ),
        'output_filename': 'js/prod/brand_dashboard_template.js',
    },
    'angular_brand_navigation': {
        'source_filenames': (
            'js/angular/app/brand_nav.js',
        ),
        'output_filename': 'js/prod/brand_navigation.js',
    },
    'angular_brand_settings': {
        'source_filenames': (
            'js/vendor/salvattore.js',
            'js/angular/app/brand_settings.js',
        ),
        'output_filename': 'js/prod/brand_settings.js',
    },
    'admin': {
        'source_filenames': (
            'js/vendor/endless-pagination.js',
            'js/vendor/salvattore.js',
            'js/vendor/html2canvas.js',
            'js/vendor/jquery.dataTables.min.js',
            'js/app/pages/admin.js',
            'js/app/protos/feed.js',
        ),
        'output_filename': 'js/prod/admin.js',
    },
    'pricing': {
        'source_filenames': (
            'js/app/protos/stripe.js',
            'js/app/pages/pricing.js',
        ),
        'output_filename': 'js/prod/pricing.js',
    },
    'angular_admin': {
        'source_filenames': (
            'js/angular/admin/admin.js',
            'js/angular/ng-table.min.js',
            'js/vendor/jquery.poshytip.min.js',
            'js/vendor/jquery-editable-poshytip.min.js',
        ),
        'output_filename': 'js/prod/angular_admin.js',
    },
    'campaign_overview': {
        'source_filenames': (
        ),
        'output_filename': 'js/prod/campaign_overview.js',
    }
}
#PIPELINE_CSS_COMPRESSOR = 'pipeline.compressors.yuglify.YuglifyCompressor'
# PIPELINE_JS_COMPRESSOR = 'pipeline.compressors.yuglify.YuglifyCompressor'
PIPELINE_JS_COMPRESSOR = None # 'pipeline.compressors.jsmin.JSMinCompressor'
PIPELINE_DISABLE_WRAPPER = True
#django pipeline static files storage
# STATICFILES_STORAGE = 'pipeline.storage.PipelineCachedStorage'

COLLECTFAST_DEBUG = True

# Using S3 Amazon storage to static or serve static locally
if USE_S3:
    COLLECTFAST_ENABLED = True
    AWS_PRELOAD_METADATA = True
    # This is used by the `static` template tag from `static`, if you're using that. Or if anything else
    # refers directly to STATIC_URL. So it's safest to always set it.
    STATICFILES_LOCATION = 'static'

    # Tell the staticfiles app to use S3Boto storage when writing the collected static files (when
    # you run `collectstatic`).
    # STATICFILES_STORAGE = 's3storage.StaticStorage'
    STATICFILES_STORAGE = 's3storage.StaticPipelineStorage'
    STATIC_URL = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, STATICFILES_LOCATION)

    MEDIAFILES_LOCATION = 'mymedia'
    MEDIA_URL = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, MEDIAFILES_LOCATION)
    DEFAULT_FILE_STORAGE = 's3storage.MediaStorage'
else:
    COLLECTFAST_ENABLED = False
    STATICFILES_STORAGE = 'django_pipeline_forgiving.storages.PipelineForgivingStorage'


MEDIAFILES_LOCATION = 'mymedia'
MEDIA_URL = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, MEDIAFILES_LOCATION)
DEFAULT_FILE_STORAGE = 's3storage.MediaStorage'

###############################
### Captcha Configs
###############################
CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.random_char_challenge'

###############################
## Intercom
###############################

DEBUG_INTERCOM_APPID = "lud7gown"
DEBUG_INTERCOM_APIKEY = "cfba7731d03dda9f82067430e00aa4f3b293e305"
PRODUCTION_INTERCOM_APPID = "m1hk2jv2"
PRODUCTION_INTERCOM_APIKEY = "4ae3b0c1f459c25742396b9b79634c0d7721aacd"

if DEBUG:
    INTERCOM_APPID = DEBUG_INTERCOM_APPID
    INTERCOM_APIKEY = DEBUG_INTERCOM_APIKEY
else:
    INTERCOM_APPID = PRODUCTION_INTERCOM_APPID
    INTERCOM_APIKEY = PRODUCTION_INTERCOM_APIKEY

INTERCOM_CUSTOM_DATA_CLASSES = [
    'debra.helpers.IntercomCustomData',
]

###############################
## Kissmetrics
###############################

DEBUG_KISSMETRICS_APIKEY = '92656e819e1dcfd93ae16ec8abe73ca14e5f61bf'
PRODUCTION_KISSMETRICS_APIKEY = '118d8c195207036ac26acb0c37bd2b7cd22dc96e'

if DEBUG:
    KISSMETRICS_APIKEY = DEBUG_KISSMETRICS_APIKEY
else:
    KISSMETRICS_APIKEY = PRODUCTION_KISSMETRICS_APIKEY

KICKBOX_APIKEY = '6dca449a52f77ed6f568ffe0c88b9e0914108b8e6fe1dc58144834a37226f52a'

BASECRM_TOKEN = '2e4449263cd5cf20745571ad5a5dd1409604dcd0bdc393696e31caf1b48554e1'

HEROKU_MEMCACHIER_SERVERS = ','.join([
  '147766.09996f.us-east-3.heroku.prod.memcachier.com:11211',
  #'138013.09996f.us-east-3.heroku.prod.memcachier.com:11211'
])

HEROKU_MEMCACHIER_USERNAME = '09996f'
HEROKU_MEMCACHIER_PASSWORD = 'af245c0d324ad9dd4fcf'

ON_HEROKU = False
if 'ON_HEROKU' in os.environ:
    ON_HEROKU = True
    HEROKU_RELEASE_VERSION = os.environ.get('HEROKU_RELEASE_VERSION')

USE_PRODUCTION_MEMCACHED = eval(
  os.environ.get('USE_PRODUCTION_MEMCACHED', 'False'))

MEMCACHED_PRODUCTION_CREDENTIALS = {
    'MEMCACHE_SERVERS': HEROKU_MEMCACHIER_SERVERS.replace(',', ';'),
    'MEMCACHE_USERNAME': HEROKU_MEMCACHIER_USERNAME,
    'MEMCACHE_PASSWORD': HEROKU_MEMCACHIER_PASSWORD,
}

def get_local_memcache_creds():
    try:
        return {
            'MEMCACHE_SERVERS': os.environ['MEMCACHIER_SERVERS'].replace(',', ';'),
            'MEMCACHE_USERNAME': os.environ['MEMCACHIER_USERNAME'],
            'MEMCACHE_PASSWORD': os.environ['MEMCACHIER_PASSWORD'],
        }
    except:
        pass

LOCAL_MEMCACHED_CREDS = get_local_memcache_creds()

# detect local memcached
if USE_PRODUCTION_MEMCACHED:
    MEMCACHE_TYPE = 'production'
elif ON_HEROKU:
    # MEMCACHE_TYPE = 'local' if LOCAL_MEMCACHED_CREDS else 'production'
    MEMCACHE_TYPE = 'production'
elif not ON_HEROKU and DEBUG:
    try:
        import socket
        socket.socket().connect(('localhost', 11211))
    except:
        MEMCACHE_TYPE = 'local-filebased'
    else:
        MEMCACHE_TYPE = 'local'
elif not ON_HEROKU and not DEBUG:
    MEMCACHE_TYPE = 'production'

if MEMCACHE_TYPE == 'production':
    os.environ.update(MEMCACHED_PRODUCTION_CREDENTIALS)


MEMCACHE_CACHES = {
    'local': {
        'LOCATION': 'localhost:11211',
        'BACKEND': 'django_pylibmc.memcached.PyLibMCCache',
        'TIMEOUT': 24 * 60 * 60,
        'BINARY': True,
        'OPTIONS': {'tcp_nodelay': True}
    },
    'local-filebased': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/django_cache2',
        'TIMEOUT': 24 * 60 * 60
    },
    'production': {
        'BACKEND': 'django_pylibmc.memcached.PyLibMCCache',
        'TIMEOUT': 24 * 60 * 60,
        'BINARY': True,
        'OPTIONS': {'tcp_nodelay': True}
    },
}

PRODUCTION_REDIS_URL = 'redis://h:par5ketf0q9coa1seu0aa8om11e@ec2-54-225-122-219.compute-1.amazonaws.com:6519'

# redis_url = urlparse.urlparse(os.environ.get('REDIS_URL'))
redis_url = urlparse.urlparse(PRODUCTION_REDIS_URL)

REDIS_URL = urlparse.urlparse(PRODUCTION_REDIS_URL)

import redis

REDIS_CLIENT = redis.Redis(host=REDIS_URL.hostname,
    port=REDIS_URL.port, password=REDIS_URL.password)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/django_cache',
        'TIMEOUT': 60 * 60 * 24
    },
    'short': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'TIMEOUT': 60
    },
    'long': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/django_cache_long',
        'TIMEOUT': 60 * 60 * 24 * 30
    },
    'collectfast': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/tmp/collectfast_cache',
        'TIMEOUT': 60 * 60 * 24
    },
    'redis': {
         "BACKEND": "redis_cache.RedisCache",
         "LOCATION": "{0}:{1}".format(redis_url.hostname, redis_url.port),
         "OPTIONS": {
             "PASSWORD": redis_url.password,
             "DB": 0,
         }
    }
}

CACHES['memcached'] = MEMCACHE_CACHES[MEMCACHE_TYPE]

COLLECTFAST_CACHE = 'collectfast'

USE_BAKED_PARTIALS = False
if ON_HEROKU:
    USE_BAKED_PARTIALS = True

MIXPANEL_TOKEN = '73ebaff77d34512063b2f3bef46039a9'
MONGO_CONNECTION_STRING = "mongodb://heroku:pn-8J3nnKAFbmVpmtYLTz6BtvFOL4kJ4h4lgLTyln-jgyTsOO0bnzjpVPPtHN_BEtdjj-7d6wS1jrPwl7NfsuQ@candidate.18.mongolayer.com:10798,candidate.35.mongolayer.com:10735/app5524706"

GRAPH_MODELS = {
    'all_applications': True,
    'group_models': True,
}

XVFB_RUNNING = os.getenv('XVFB')
AUTOCREATE_HEADLESS_DISPLAY = not (XVFB_RUNNING or DEBUG)

# PHONENUMBER_DB_FORMAT = 'INTERNATIONAL'

# MOZ API SETTINGS (https://moz.com/products/api/pricing)
MOZ_ACCESS_ID = 'mozscape-f3613416c1'
MOZ_SECRET_KEY = 'df0f3eb45af5baf9c52410e76ef173c1'

# A flag set to True will use ES Shield plugin for authorization in conjunction with two next values
USE_ES_AUTHORIZATION = True

# ES Shield plugin authorization credentials
ELASTICSEARCH_SHIELD_USERNAME = 'user'
ELASTICSEARCH_SHIELD_PASSWORD = 'Ohgh6eonahkamieg'

# We try to reprocess undecided InstagramProfiles periodically
# We'll stop reprocessing after this number of retries
MAX_INSTAGRAM_REFETCH_RETRY_COUNT = 10
