import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


from django.core.wsgi import get_wsgi_application
from dj_static import Cling
application = Cling(get_wsgi_application())


# Fix django closing connection to MemCachier after every request (#11331)
from django.core.cache.backends.memcached import BaseMemcachedCache
BaseMemcachedCache.close = lambda self, **kwargs: None