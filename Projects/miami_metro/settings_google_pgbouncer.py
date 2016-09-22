from settings_google import *  #flake8:noqa
from copy import deepcopy


# Point default DB to local pgbouncer
DATABASES['default'].update({
    'HOST': 'localhost',
    'PORT': 6432,
})


# Set up replica DB config
DATABASES['read_replica'] = deepcopy(DATABASES['default'])
DATABASES['read_replica']['NAME'] += '_replica'
