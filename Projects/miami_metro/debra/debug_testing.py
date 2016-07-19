from django.http import HttpResponse

from angel import price_tracker
from django.conf import settings
from django.shortcuts import render
from debra.forms import ShelfAccountForm
from django.template import RequestContext


def price_tracker_queries(request):
    if not settings.DEBUG:
        return
    price_tracker.update_product_price(419952)
    response = render(request, 'pages/landing/home.html', {
        'account_form': ShelfAccountForm()
    }, context_instance=RequestContext(request))

    return response
