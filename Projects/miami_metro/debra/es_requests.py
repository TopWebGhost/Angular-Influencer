# from debra.constants import ELASTICSEARCH_SHIELD_PASSWORD, ELASTICSEARCH_SHIELD_USERNAME
from django.conf import settings
import requests
from requests.auth import HTTPBasicAuth


def make_es_get_request(es_url=None, es_query_string=None):
    """
    This method uses authorized or non-authorized form of GET request to ES depending on settings variable
    :return:
    """
    if es_url is None or es_query_string is None:
        return None
    if settings.USE_ES_AUTHORIZATION is True:
        return requests.get(
            es_url,
            data=es_query_string,
            auth=(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
        )
    else:
        return requests.get(
            es_url,
            data=es_query_string
        )


def make_es_post_request(es_url=None, es_query_string=None):
    """
    This method uses authorized or non-authorized form of GET request to ES depending on settings variable
    :return:
    """
    if es_url is None or es_query_string is None:
        return None
    if settings.USE_ES_AUTHORIZATION is True:
        return requests.post(
            es_url,
            data=es_query_string,
            auth=HTTPBasicAuth(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
        )
    else:
        return requests.post(
            es_url,
            data=es_query_string
        )


def make_es_delete_request(es_url=None, es_query_string=None):
    """
    This method uses authorized or non-authorized form of DELETE request to ES depending on settings variable
    :return:
    """
    if es_url is None:
        return None
    if settings.USE_ES_AUTHORIZATION is True:
        if es_query_string is None:
            return requests.delete(
                es_url,
                auth=HTTPBasicAuth(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
            )
        else:
            return requests.delete(
                es_url,
                data=es_query_string,
                auth=HTTPBasicAuth(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
            )
    else:
        if es_query_string is None:
            return requests.delete(
                es_url,
            )
        else:
            return requests.delete(
                es_url,
                data=es_query_string
            )


def make_es_head_request(es_url=None):
    """
    This method uses authorized or non-authorized form of GET request to ES depending on settings variable
    :return:
    """
    if es_url is None:
        return None
    if settings.USE_ES_AUTHORIZATION is True:
        return requests.head(
            es_url,
            auth=HTTPBasicAuth(settings.ELASTICSEARCH_SHIELD_USERNAME, settings.ELASTICSEARCH_SHIELD_PASSWORD)
        )
    else:
        return requests.head(es_url)
