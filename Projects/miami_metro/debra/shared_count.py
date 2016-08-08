import requests

from debra.constants import SC_API_KEY, SC_PLAN, SC_API_URL
from debra.generic_api import Resource, ResourceApi


def url_response(response=None):
    data = None

    if response:
        print response
        data = {
            'count_fb_shares': response.get('Facebook').get('share_count', 0) if response.get('Facebook') else 0,
            'count_fb_likes': response.get('Facebook').get('like_count', 0) if response.get('Facebook') else 0,
            'count_fb_comments': response.get('Facebook').get('comment_count', 0) if response.get('Facebook') else 0,
            'count_tweets': response.get('Twitter', 0),
            'count_pins': response.get('Pinterest', 0),
            'count_stumbleupons': response.get('StumbleUpon', 0),
            'count_gplus_plusone': response.get('GooglePlusOne', 0),
            'count_linkedin_shares': response.get('LinkedIn', 0),
        }

    return {'data': data or {}}


class Url(Resource):

    def _clean_value(self, value):
        if not value.startswith('http'):
            value = 'http://' + value
        return value

    def url(self):
        return self._call('url', url_response)


class Api(ResourceApi):

    source_name = 'Shared Count'
    resource_class = Url

    def _request(self, resource, endpoint, resp, **params):
        payload = {
            'apikey': SC_API_KEY,
            'url': resource
        }
        response = requests.get(SC_API_URL + endpoint, params=payload)

        return response
