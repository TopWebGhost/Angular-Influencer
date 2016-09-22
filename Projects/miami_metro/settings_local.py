from settings import *  #flake8:noqa

BROKER_HOST = "127.0.0.1"

# Disable Sentry errors from developer machines
RAVEN_CONFIG = {}


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(asctime)s %(filename)s:%(funcName)s:%(message)s'
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
            'handlers': [ 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    }
}