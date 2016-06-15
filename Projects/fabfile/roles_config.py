from __future__ import absolute_import, division, print_function, unicode_literals
from miami_metro.servers import workers


roledefs = {
    'daily-fetcher': {
        'hosts': workers['daily-fetcher'],
        'project_dir': '/home/ubuntu/Projects_daily-fetcher'
    },
    'daily-fetcher-blogs': {
        'hosts': workers['daily-fetcher-blogs'],
        'project_dir': '/home/ubuntu/Projects_daily-fetcher-blogs'
    },
    'daily-fetcher-social': {
        'hosts': workers['daily-fetcher-social'],
        'project_dir': '/home/ubuntu/Projects_daily-fetcher-social'
    },
    'daily-fetcher-infrequent': {
        'hosts': workers['daily-fetcher-infrequent'],
        'project_dir': '/home/ubuntu/Projects_daily-fetcher-infrequent'
    },
    'newinfluencer-fetcher': {
        'hosts': [
        ],
        'project_dir': '/home/ubuntu/Projects_newinfluencer-fetcher'
    },
    'platform-data-postprocessing': {
        'hosts': workers['platform-data-postprocessing'],
        'project_dir': '/home/ubuntu/Projects_platform-data-postprocessing'
    },
    'product-importer-from-blogs': {
        'hosts': workers['product-importer-from-blogs'],
        'project_dir': '/home/ubuntu/Projects_product-importer-from-blogs'
    },
    'celery-default': {
        'hosts': workers['celery-default'],
        'project_dir': '/home/ubuntu/Projects_celery-default'
    },
    'rs-daily-fetcher': {
        'hosts': workers['rs-daily-fetcher'],
        'project_dir': '/home/ubuntu/Projects_rs-daily-fetcher'
    },
    'rs-platform-data-postprocessing': {
        'hosts': workers['rs-platform-data-postprocessing'],
        'project_dir': '/home/ubuntu/Projects_rs-platform-data-postprocessing'
    },
    'db-second': {
        'hosts': workers['db-second'],
        'project_dir': '/home/ubuntu/Projects_db-second'
    },
    'rs-queue': {
        'hosts': workers['rs-queue'],
    },
    'google-queue': {
        'hosts': ['miami@' + host for host in workers['google-queue']],
    },
    'sentry': {
        'hosts': workers['sentry'],
        'project_dir': '/home/ubuntu/Projects_sentry'
    },
}

roledefs['all-workers'] = {
    'hosts': [
        host for roledef in [roledefs[role_name] for role_name in [
            'daily-fetcher',
            'daily-fetcher-blogs',
            'daily-fetcher-social',
            'daily-fetcher-infrequent',
            'rs-daily-fetcher',
            'newinfluencer-fetcher',
            'platform-data-postprocessing',
            'rs-platform-data-postprocessing',
            'product-importer-from-blogs',
            'celery-default',
        ]]
        for host in roledef['hosts']]
}

roledefs['all'] = {
    'hosts': [host for roledef in roledefs.values() for host in roledef['hosts']]
}
