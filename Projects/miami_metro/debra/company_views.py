'''
this file holds views for the company pages
'''

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from debra.helpers import get_server_info, get_js_shelfit_code
from debra.forms import ContactUsForm


def contact(request):
    context = {
        'contact_form': ContactUsForm(),
        'page': 'contact'
    }
    return render_to_response('company/contact.html', context, context_instance=RequestContext(request))

def hiring(request):
    return render_to_response('company/hiring.html', {'page': 'hiring'}, context_instance=RequestContext(request))

def press_kit(request):
    return render_to_response('company/press_kit.html', {'page': 'press_kit'}, context_instance=RequestContext(request))

def about_us(request):
    return render_to_response('company/about_us.html', {'page': 'about_us'}, context_instance=RequestContext(request))

def bloggers(request):
    return render_to_response('company/blogger_features.html', {'page': 'bloggers'}, context_instance=RequestContext(request))

def privacy(request):
    return render_to_response('privacy.html', context_instance=RequestContext(request))

def support(request):
    user_agent = request.META['HTTP_USER_AGENT']
    sname = get_server_info(request)
    js_str = get_js_shelfit_code(sname)
    browser = 'firefox'
    if user_agent is not None:
        if 'firefox' in user_agent.lower():
            browser = 'firefox'
        if 'safari' in user_agent.lower():
            browser = 'safari'
        if 'opera' in user_agent.lower():
            browser = 'opera'
        if 'msie' in user_agent.lower():
            browser = 'msie'
        if 'chrome' in user_agent.lower():
            browser = 'chrome'
    return render_to_response('company/support.html',
            {'js_code': js_str,
            'browser': browser,
            'page': 'support'},
            context_instance=RequestContext(request))

def get_shelfit_button(request):
    user_agent = request.META['HTTP_USER_AGENT']
    sname = get_server_info(request)
    js_str = get_js_shelfit_code(sname)
    browser = 'firefox'
    if user_agent is not None:
        if 'firefox' in user_agent.lower():
            browser = 'firefox'
        if 'safari' in user_agent.lower():
            browser = 'safari'
        if 'opera' in user_agent.lower():
            browser = 'opera'
        if 'msie' in user_agent.lower():
            browser = 'msie'
        if 'chrome' in user_agent.lower():
            browser = 'chrome'

    return render_to_response('company/shelfit_btn.html',
        {'js_code': js_str,
         'browser': browser,
         'page': 'shelfit_btn'}, context_instance=RequestContext(request))
