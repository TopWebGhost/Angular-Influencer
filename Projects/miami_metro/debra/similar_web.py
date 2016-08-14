''' Similar Web Integration

This file contains the integration with Similar Web.

The Api object is built around sites, and uses them as a key. Individual
methods available (such as visits for a domain/site) should be implemented
on the Domain object, so it mirrors SW's api.

The keyword arguments passed to Domain._call are in turn passed to 
Api._call, and encoded into the query string for the request.
'''

import requests
import random

from debra.constants import SW_INCLUDE_SUBDOMAINS, SW_USER_KEY, SW_VERSION
from debra.constants import SW_API_URL, SW_RESPONSE_FORMAT
from debra.constants import COUNTRY_CODES
from debra.generic_api import Resource, ResourceApi
from xpathscraper.utils import domain_from_url

DAILY = 'daily'
WEEKLY = 'weekly'
MONTHLY = 'monthly'

def visits_response(response=None):
    data = []

    if response:
        for item in response['visits']:
            data.append({'date': item['date'], 'count': item['visits']})
    
    return {'data': data}

def traffic_response(response=None):
    from debra.models import SW_SOURCE_TYPE_CHOICES

    # source_type_NAME => source_type_ID mapping
    source_types_dict = dict((choice[1], choice[0])\
        for choice in SW_SOURCE_TYPE_CHOICES)

    data = []
    if response:
        for item in response['TrafficShares']:
            data.append({
                'type': source_types_dict.get(item['SourceType']),
                'value': item['SourceValue']})
    return {'data': data}


def top_country_shares_response(response=None):
    data = []
    if response:
        # others_share = 0.0
        for item in response['TopCountryShares'][:20]:
            # if others_share < response['TopCountryShares'][0]['TrafficShare']:
            #     others_share += item['TrafficShare']
            # else:
            data.append({
                'country_name': COUNTRY_CODES.get_name_by_numeric_code(
                    item['CountryCode']),
                'code': COUNTRY_CODES.get_code_by_numeric_code(
                    item['CountryCode']),
                'traffic_share': item['TrafficShare'],
                'point': COUNTRY_CODES.get_point_by_numeric_code(
                    item['CountryCode']),
            })
        # data.append({
        #     'country_name': 'Others',
        #     'traffic_share': others_share,
        # })
    return {'data': data}


class Domain(Resource):
    ''' Domain is used to access any API with /Site/ in the URL. '''

    def _clean_value(self, value):
        return domain_from_url(value)
        
    def visits(self, start_month, end_month, granularity=MONTHLY):
        return self._call('visits', visits_response, start_date=start_month,
                            end_date=end_month,
                            granularity=granularity.lower())

    def traffic_shares(self):
        return self._call('traffic', traffic_response)

    def top_country_shares(self):
        return self._call('traffic', top_country_shares_response)


class Api(ResourceApi):
    ''' Api manages api calls to the Similar Web API, with dict access by Domain.
    '''
    source_name = 'Similar Web'
    resource_class = Domain

    def _request(self, resource, endpoint, resp, **params):
        payload = {
            'md': 'true' if not SW_INCLUDE_SUBDOMAINS else 'false',
            'Format': SW_RESPONSE_FORMAT,

        }
        payload.update(params)
        if endpoint == 'visits':
            dst = SW_API_URL + '/' + SW_VERSION + '/website/' + resource + '/total-traffic-and-engagement/' + endpoint
            payload['api_key'] = SW_USER_KEY
        else:
            dst = SW_API_URL + '/Site/' + resource + '/' + SW_VERSION + '/' + endpoint
            payload['UserKey'] = SW_USER_KEY


        print "resource: [%r]  endpoint: [%r]" % (resource, endpoint)
        print "request: %r" % dst
        print "payload: %r" % payload
        print

        response = requests.get(dst, params=payload)
        print response, response.content

        return response