from django.utils.functional import wraps

from rest_framework.response import Response

from campaigns.helpers import CampaignReportDataWrapper


def campaign_report_endpoint(func):

	@wraps(func)
	def _wrapped(self, request, id):
		endpoint, pl_name = (func.__name__,
			request.GET.get('platform_name'))
		w = CampaignReportDataWrapper(id)
		data = w.get_endpoint_data(endpoint, pl_name)
		return Response(data)

	return _wrapped
