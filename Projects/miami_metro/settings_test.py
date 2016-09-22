#when testing, use the test database as the defaut database
from settings import *

DEBUG = False
DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
    'SHOW_TOOLBAR_CALLBACK': False,
    }

DATABASES['default'] = DATABASES['test_db']
INSTALLED_APPS = filter(lambda el: el != 'south', INSTALLED_APPS)

