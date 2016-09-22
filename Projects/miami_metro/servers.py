from __future__ import absolute_import, division, print_function, unicode_literals

"""
Warning! Warning! Warning!

Do not put anything in this module that will make it not run with a vanilla Python installation.
This server configuration is imported both in the project virtualenv and outside it - in the Fabric
script context, so it needs to be kept as simple as possible.
"""

workers = {
    'daily-fetcher': [
    ],
    'daily-fetcher-blogs': [
        # '104.154.43.69',  -- previous
        '192.81.215.178',
    ],
    'daily-fetcher-social': [
        # '104.154.88.22',  -- previous
        '198.211.99.232',
    ],
    'daily-fetcher-infrequent': [

    ],
    'newinfluencer-fetcher': [
    ],
    'platform-data-postprocessing': [
        '198.211.101.104'
    ],
    'product-importer-from-blogs': [
        '198.199.64.156',
	'198.199.66.78',
    ],
    'celery-default': [
        '198.211.112.132',
    ],
    'rs-daily-fetcher': [
    ],
    'rs-platform-data-postprocessing': [
    ],
    'db-second': [
       'ec2-54-224-5-129.compute-1.amazonaws.com'
    ],
    'rs-queue': [
        
    ],
    'google-queue': [
        '130.211.131.175',  # stats node
        '130.211.163.243',
        '146.148.57.97',
        '130.211.118.92',
        '130.211.159.88',
    ],
    'sentry': [
        '146.148.93.0',
    ],
}


# This is a dict of ElasticSearch nodes forming our Cluster. It is used to monitor if any node is downed.
# Format is: 'node_name': 'node_IP'
es_nodes = {
    'elasticsearch-index-02': '162.243.220.77',
    'elasticsearch-index-03': '162.243.248.151',
    'elasticsearch-index-05': '192.241.161.176',
    'elasticsearch-index-06': '162.243.44.91',
}
