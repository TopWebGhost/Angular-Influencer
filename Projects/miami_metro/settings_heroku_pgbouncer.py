from settings_rackspace import *  #flake8:noqa

DATABASES['default'].update({
    'HOST': 'ec2-54-81-249-181.compute-1.amazonaws.com',
    'PORT': 6432,
})
