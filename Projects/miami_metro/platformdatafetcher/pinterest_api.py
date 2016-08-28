import requests
import logging
from requests.exceptions import HTTPError

import time

log = logging.getLogger('platformdatafetcher.pinterest_api')

"""
Here is a new Pinterest performer helper which deals with tokens and acquires needed data (pins, may be boards)

Pinterest limits: 1000 requests per 1 hour per user

https://developers.pinterest.com/docs/api/overview/
https://developers.pinterest.com/tools/access_token/

"""


class BasicPinterestFetcher(object):
    """
    Very basic implementation of pinterest data fetcher using API.
    Currently access tokens should be refreshed here manually.
    """
    access_token = "AXBLOqySdgvV9ausR51kR3i06R9mFEPSVy7R3GRDATl-QUBCXwAAAAA"
    sleep_time_min = 15
    max_tries = 8

    def __init__(self, custom_access_token=None):
        if custom_access_token is not None:
            self.access_token = custom_access_token

    def get_pin_data(self, pin_id=None, fields='id,created_at,counts'):

        if pin_id is None:
            return {'error': 'pin_id is None'}

        # main cycle
        attempts = 0
        while attempts <= self.max_tries:

            try:
                log.info('Trying to fetch data for pin %s' % pin_id)

                params = {
                    'access_token': self.access_token,
                    # 'fields': 'id,note,url,created_at,counts'
                    'fields': fields
                }

                r = requests.get("https://api.pinterest.com/v1/pins/%s/" % pin_id, params=params, headers=None)

                r.raise_for_status()

                response = r.json()

                log.info('Got the following response: %s' % response)
                log.info('Limits: %s remaining / %s total' % (r.headers.get('X-Ratelimit-Remaining'),
                                                              r.headers.get('X-Ratelimit-Limit')))

                return response

            except HTTPError as e:
                log.error(e)
                log.error('Http message: %s' % e.message)

                if e.response.status_code == 404:
                    log.error('Pin was not found')
                    return {'error': 'Pin was not found'}
                else:
                    log.error(e.message)

            except Exception as e:
                log.error(e)

            log.info('Waiting for %s min...' % self.sleep_time_min)
            time.sleep(self.sleep_time_min * 60)
            log.info('Waiting ended')
            attempts += 1

        log.error('All %s attempts ended.' % self.max_tries)
        return {'error': 'All %s attempts ended.' % self.max_tries}


# TODO: sketching of bigger version of Pinterest proxy with auto-access_tokens obtaining.
# class PinterestProxy(object):
#
#     """
#     Object to interact with Pinterest using its API and transparently managing access tokens for given users.
#     """
#
#     user_pool = []
#
#     def __init__(self, user_pool=None):
#         """
#         Initing mediator - fetching access_tokens
#         :return:
#         """
#
#         # here we populate a pool of active users -- later move it to DB
#         if user_pool is not None:
#             self.user_pool = user_pool
#             # TODO: here we resolve missing tokens, setting statuses?
#
#             # for entry in self.user_pool:
#             #     if entry.get('status') is None:
#             #         entry['status'] = 'active'
#
#
#     def cooldown_access_token(self, token=None):
#         """
#         Sets access token on cooldown
#         :param token:
#         :return:
#         """
#         pass
#
#     def get_available_token(self):
#         """
#         Returns the most likely available token
#
#         Two variants:
#
#         (1) first of all we give an available 'active' token, if such thing would exist.
#         (2) if there are no active tokens, then we give out the most old cooldown-set token.
#         So we will be using the first token until it is expired and went on cooldown,
#         then it will be the second token, then the third, etc.
#         Pros: more control over tokens; visibility of users working one after another.
#         Cons: extra complexity of implementation
#
#         OR
#
#         (1) we give tokens in a revolver manner - one after another untill they all are on cooldown.
#         Pros: all tokens will expire nearly simultaneousely.
#         Cons: weird burst-like activity from the point of view of Pinterest.
#
#         :return:
#         """
#
#         return self.user_pool[0].get('access_token')
#
#     def get_pin_data(self, pin_id=None):
#         """
#         Returns pin's id using available access_token
#
#         (1) Find access_token which is 'active'.
#         (2) call teh request.
#         (3) if its remaining is 0 then set it as 'cooldown'
#         (4) if there are no active tokens, wait 10 minutes, take the most unused access_token, try using it.
#
#
#         :param pin_id:
#         :return:
#         """
#
#         response = None
#
#         try:
#             log.info('Fetching data for pin %s' % pin_id)
#
#             access_token = self.get_available_token()
#
#             params = {
#                 'access_token': access_token,
#                 'fields': 'id,note,url,created_at,counts'
#             }
#
#             r = requests.get("https://api.pinterest.com/v1/pins/%s/" % pin_id, params=params, headers=None)
#
#             r.raise_for_status()
#
#             response = r.json()
#
#             log.info('Got the following response: %s' % response)
#             log.info('Limits: %s remaining / %s total' % (r.headers.get('X-Ratelimit-Remaining'),
#                                                           r.headers.get('X-Ratelimit-Limit')))
#
#             if r.headers.get('X-Ratelimit-Remaining') == 0:
#                 self.cooldown_access_token(access_token)
#
#         except HTTPError as e:
#             log.error(e)
#             log.error('Http code: %s' % e.message)
#
#         except Exception as e:
#             log.error(e)
#
#         return response
#
#     def get_board_data(self, pin_id=None):
#         """
#         Returns board's id using available access_token
#
#         :param pin_id:
#         :return:
#         """
#         pass
