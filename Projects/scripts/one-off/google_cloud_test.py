from __future__ import absolute_import, division, print_function, unicode_literals
from django.conf import settings
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

ComputeEngine = get_driver(Provider.GCE)
driver = ComputeEngine(settings.GOOGLE_SERVICE_EMAIL, settings.GOOGLE_SERVICE_KEY,
                       project=settings.GOOGLE_PROJECT_ID)

print(driver.list_images())
