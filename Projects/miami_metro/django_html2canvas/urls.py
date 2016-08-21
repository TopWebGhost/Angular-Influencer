from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template
from django.contrib.auth.decorators import login_required

from views import *

urlpatterns = patterns('',
    url(regex = r'^$', view=login_required(imgProxy), name="html2canvas_proxy"),
)
