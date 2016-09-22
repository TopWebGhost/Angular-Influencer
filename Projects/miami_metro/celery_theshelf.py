from __future__ import absolute_import, division, print_function, unicode_literals
import os
import importlib
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
from django.conf import settings

# Needed to initialize actions and avoid an import error later on
from django.contrib.admin import actions

app = Celery('theshelf')

app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
