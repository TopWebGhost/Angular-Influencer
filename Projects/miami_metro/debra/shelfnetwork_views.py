"""
ShelfNetwork related views
"""
from mixpanel import Mixpanel
from django.conf import settings
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
import urlparse
from debra.forms import ShelfAccountForm
from django.template import RequestContext
from django.http import HttpResponseRedirect

mp = Mixpanel(settings.MIXPANEL_TOKEN)

def shelfnetwork_bloggers(request):
    """
    Pass on the information to mixpanel and load the blogger page
    """
    return HttpResponseRedirect("http://www.theshelf.com")

    return redirect(reverse('debra.account_views.brand_home'))
    ## depicts which badge is used by the blogger
    badge_name = None
    parsed = urlparse.urlparse(request.build_absolute_uri())
    params = urlparse.parse_qs(parsed.query)
    badge_name = params.get('badge_name', [None])[0]
    print "badge name: %s" % badge_name
    ## this represents which blog was this clicked on
    referer = request.META.get('HTTP_REFERER', None)
    print referer

    response = render(request, 'pages/landing/home.html', {
        'page': 'bloggers',
        'account_form': ShelfAccountForm(),
        'referer': referer,
        'badge_name': badge_name,
        'shelfnetwork': 1,
    }, context_instance=RequestContext(request))

    return response