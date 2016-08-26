'''
internal view to check how much info we're collecting for each blogger
'''


from debra.models import Influencer, Platform, Posts, PostInteractions, UserProfile
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.template import RequestContext
from django.shortcuts import render_to_response


@login_required
def blogger_info(request, bloggerid=None):
	'''
	Fetches basic info from our database about the bloggerid
	'''
	result_list = {}
	if bloggerid:
		inf = Influencer.objects.get(id = bloggerid)
		plats = Platform.objects.filter(influencer=inf)
		result_list[inf] = plats
	else:
		trendsetters = UserProfile.objects.filter(is_trendsetter = True).order_by('id')        
		for ts in trendsetters:
			inf = Influencer.objects.get(bloglovin_url = ts.blogloinv_page)
			plats = Platform.objects.filter(influencer = inf)
			result_list[inf] = plats

	return render_to_response('pages/blogger_info.html', 
								{
								'result_list': result_list,
								},
								context_instance=RequestContext(request))
