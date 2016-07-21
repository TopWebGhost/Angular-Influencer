from django.shortcuts import render_to_response
from django.template import RequestContext


def error403(request):
    '''
    Default view for error 403: Inadequate permissions.
    '''
    return render_to_response('403.html', context_instance=RequestContext(request))
