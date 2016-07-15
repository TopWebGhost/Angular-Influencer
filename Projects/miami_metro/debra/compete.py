import requests
from datetime import datetime

from debra.constants import COMPETE_TEST_API_KEY, COMPETE_API_URL
from debra.generic_api import Resource, ResourceApi
from xpathscraper.utils import domain_from_url


def visits_response(response=None):
    data = []

    if response:
        response_data = filter(lambda x: x['value'] is not None,\
            response['data']['trends']['vis'])
        for item in response_data:
            data.append({
                'count': item['value'],
                'date': datetime.strptime(item['date'], "%Y%m")
            })

    return {'data': data}


class Domain(Resource):

    def _clean_value(self, value):
        return domain_from_url(value)

    def visits(self, start_month=None, end_month=None, latest_months=None,\
        api_key=None):
        return self._call('vis', visits_response,
            start_date=start_month, end_date=end_month, latest=latest_months,\
            apikey=api_key)

class Api(ResourceApi):

    source_name = 'Compete'
    resource_class = Domain

    def _request(self, resource, endpoint, resp, **params):
        payload = {
            'apikey': COMPETE_TEST_API_KEY
        }
        payload.update(params)
        response = requests.get(
            COMPETE_API_URL + '/sites/' + resource + '/trended/' + endpoint,
            params=payload
        )

        return response