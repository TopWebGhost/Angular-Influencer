'''
this file is for checking properties of specific model instances. Also, autocomplete
'''
from debra.models import UserProfile, Influencer, Platform
from django.db.models import Q
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from celery.result import AsyncResult
import pdb
import json

from debra.serializers import unescape


#####-----< Autocomplete Queries >-----#####
def user_autocomplete(request):
    '''
    get autocomplete results for a user search
    @return json string containing search results
    '''
    term = request.GET.get('term')
    matched_users = UserProfile.objects.filter(Q(name__icontains=term) | Q(blog_name__icontains=term) | Q(user__email__icontains=term)).order_by('-is_trendsetter', '-can_set_affiliate_links')

    results = [{
        'id': up.id,
        'name': up.best_name_for_search,
        'profile_url': up.profile_url,
        'blog_name': up.blog_name,
        'img': up.profile_img_url
    } for up in matched_users]

    return HttpResponse(status=200, content=json.dumps({'results': results}))

def blogger_autocomplete(request):
    """
    similar to user_autocomplete, but for the fact that it operates on Influencers instead of UserProfile's
    @return json string containing search results
    """
    term = request.GET.get('term')

    influencers = Influencer.raw_influencers_for_search()
    matched_influencers = influencers.filter(name__isnull=False).filter(Q(name__icontains=term) |
                                                                        Q(email__icontains=term) |
                                                                        Q(platform__blogname__icontains=term))

    results = []
    for inf in matched_influencers:
        results.append({
            'id': inf.id,
            'name': unescape(inf.name),
            'img': unescape(inf.name)
        })

    return HttpResponse(status=200, content=json.dumps({'results': results}))
#####-----</ Autocomplete Queries >-----#####

#####-----< Celery Task Queries >-----#####
def check_task_status(request):
    '''
    get the status of a celery task (id given in the GET parameters).
    @return HttpResponse with status=200 if the task has completed, 500 o/w
    '''
    task = request.GET.get('task')
    res = AsyncResult(task)
    if res.ready():
        response_dict = res.get()
        if response_dict:
            # get the params necessary for constructing the url to delete the item
            user = request.user.userprofile.id
            item_id = response_dict['pmsm_id']
            return HttpResponse(status=200, content=json.dumps({
                'img': response_dict['img_url_thumbnail_view'],
                'name': response_dict['name'],
                'delete_url': reverse('remove_from_shelf', args=(user, item_id,))
            }))
        else:
            return HttpResponse(status=200, content=json.dumps({
                'status': 'failed'
            }))
    else:
        return HttpResponse(status=500)
#####-----</ Celery Task Queries >-----#####

