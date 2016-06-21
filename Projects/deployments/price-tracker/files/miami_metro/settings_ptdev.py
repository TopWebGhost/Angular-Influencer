from .settings import *

# Do we need settings customization now?

#DEBUG = True
#
#DATABASES = {
#
#    'default':{
#
#            # These are for krappa db on heroku for beta:
#            'ENGINE': 'django.db.backends.postgresql_psycopg2',                                 
#            'NAME': 'miami_metro_local',
#
#            # These are for alpha-getshelf 
#            'USER': 'ubuntu',
#            #'PASSWORD': 'KF1_idk9UZBwa4rFOWNrxT5rgq',
#            #'HOST': 'ec2-54-243-223-227.compute-1.amazonaws.com',
#            #'PORT': '5432',
#            #'NAME': 'dd0qdrqesoo9c8',
#
#
#            # This was our original DB deployment on EC2
#            #'NAME': 'devel_db',                      # Or path to database file if using sqlite3.
#            #'USER': 'django_user',                      # Not used with sqlite3.
#            #'PASSWORD': 'messier78_%starbuck',                  # Not used with sqlite3.
#            ###'USER': 'pricetracker',
#            ###'PASSWORD': 'morgan_45$',
#            #'HOST': '184.73.153.141', #23.23.187.196', #'ec2-23-22-92-68.compute-1.amazonaws.com', #'69.120.105.217',                      # Set to empty string for localhost. Not used with sqlite3.
#            #We changed the port to 6432 so as to use pgbouncer, a connection pooler to increase the number of simultaneous db connections
#            #'PORT': '6432',                      # Set to empty string for default. Not used with sqlite3.
#    },
#    'pdextractor':{
#        'ENGINE': 'django.db.backends.postgresql_psycopg2',
#        'NAME': 'pdextractor',
#	'USER': 'ubuntu',
#    }
#}
#
#BROKER_HOST = "127.0.0.1"
#BROKER_PORT = None
#BROKER_USER = None
#BROKER_PASSWORD = None
#BROKER_VHOST = None

