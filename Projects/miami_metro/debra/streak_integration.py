
""" 
    streak_client.py ~ Python wrapper for Streak CRM API requests
    * Consumes Mashape API hosted here: https://www.mashape.com/jenbrannstrom/streak-crm-for-gmail#!documentation
    Usage:
        from streak_client import StreakClient
        streak = StreakClient()
        pipelines = streak.get("pipelines").body
"""

import requests
import json
import datetime
import time

from django.conf import settings

from debra.constants import STREAK_HOST, STREAK_API_KEY
from debra import requests_ssl_patch
from debra.decorators import cached_property
from debra.templatetags.custom_filters import common_date_format
from xpathscraper import utils


class StreakBaseObject(object):

    def __init__(self, *args, **kwargs):
        if kwargs.get('api_data'):
            self.api_data = kwargs.get('api_data')
            self.key = self.api_data['key']
        else:
            self.key = kwargs.get('key')

    def reset(self):
        try:
            del self.api_data
        except AttributeError:
            pass

    @cached_property
    def name(self):
        return self.api_data['name']


class StreakField(StreakBaseObject):
    def __init__(self, pipeline, **kwargs):
        self.pipeline = pipeline
        super(StreakField, self).__init__(self, **kwargs)


class StreakFieldValue(StreakBaseObject):
    def __init__(self, box, key=None, api_data=None):
        self.box = box
        if api_data:
            self.api_data = api_data
            self.key = api_data['key']
        else:
            self.key = key

    @cached_property
    def api_data(self):
        return client.get('boxes/{boxKey}/fields/{fieldKey}'.format(
            boxKey=self.box.key, fieldKey=self.key)).json()

    def update(self, value):
        return client.post(
            'boxes/{boxKey}/fields/{fieldKey}'.format(
                boxKey=self.box.key, fieldKey=self.key),
            params={'value': value}
        )


class StreakBox(StreakBaseObject):
    def __init__(self, stage, key=None, api_data=None):
        self.stage = stage
        if api_data:
            self.api_data = api_data
            self.key = api_data['key']
        else:
            self.key = key

    @cached_property
    def api_data(self):
        return client.get('boxes/{boxKey}'.format(boxKey=self.key)).json()

    def update(self, **kwargs):
        params = {'stageKey': self.stage.key}
        return client.post('boxes/{boxKey}'.format(boxKey=self.key),
            params=params)

    def update_fields(self, fields):
        for field, value in fields.items():
            field_value = StreakFieldValue(box=self,
                key=self.stage.pipeline.fields[field].key)
            field_value.update(value)


class StreakStage(StreakBaseObject):
    def __init__(self, pipeline, key=None, api_data=None):
        self.pipeline = pipeline
        if api_data:
            self.api_data = api_data
            self.key = api_data['key']
        else:
            self.key = key

    @cached_property
    def api_data(self):
        return client.get('boxes/{boxKey}'.format(boxKey=self.key)).json()

    def create_box(self, box_name):
        resp = client.put(
            'pipelines/{pipelineKey}/boxes'.format(
                pipelineKey=self.pipeline.key),
            params={'name': box_name, 'stageKey': self.key}
        )
        if resp.status_code == 200:
            return StreakBox(stage=self, api_data=resp.json())


class StreakPipeline(StreakBaseObject):
    def __init__(self, key=None, api_data=None):
        if api_data:
            self.api_data = api_data
            self.key = api_data['key']
        else:
            self.key = key

    @cached_property
    def fields(self):
        return {
            data['name']: StreakField(pipeline=self, api_data=data)
            for data in self.api_data['fields']
        }

    @cached_property
    def api_data(self):
        return client.get('pipelines/{pipelineKey}'.format(
            pipelineKey=self.key))

    @cached_property
    def stages(self):
        return [
            StreakStage(pipeline=self, api_data=stage)
            for stage in self.api_data['stages'].values()
        ]

    def get_stage_by_name(self, name):
        try:
            return [stage for stage in self.stages if stage.name == name][0]
        except IndexError:
            pass


class Streak(StreakBaseObject):

    @cached_property
    def pipelines(self):
        return [
            StreakPipeline(api_data=pipeline)
            for pipeline in client.get('pipelines').json()
        ]
        
    def get_pipeline_by_name(self, name):
        try:
            return [p for p in self.pipelines if p.name == name][0]
        except IndexError:
            pass

    def reset(self):
        try:
            del self.pipelines
        except AttributeError:
            pass
        

class StreakClient(object):
    host = STREAK_HOST
    auth = (STREAK_API_KEY, 'ignored')
    headers = {}

    @cached_property
    def _session(self):
        return requests
        # session = requests.Session()
        # session.mount('https://', requests_ssl_patch.MyAdapter())
        # return session

    def get(self, endpoint, params={}):
        return self._session.get("%s/%s" % (self.host, endpoint), params=params,
            auth=self.auth, headers=self.headers)

    def post(self, endpoint, params={}):
        return self._session.post("%s/%s" % (self.host, endpoint),
            json=params, auth=self.auth, headers=self.headers)

    def put(self, endpoint, params={}):
        return self._session.put("%s/%s" % (self.host, endpoint),
            data=params, auth=self.auth, headers=self.headers)

    def patch(self, endpoint, params={}):
        return self._session.patch("%s/%s" % (self.host, endpoint),
            data=params, auth=self.auth, headers=self.headers)

    def delete(self, endpoint, params={}):
        return self._session.delete("%s/%s" % (self.host, endpoint),
            data=params, auth=self.auth, headers=self.headers)


client = StreakClient()


def create_box(*args, **kwargs):
    client.create_box(*args, **kwargs)


def mark_brand_signup(**kw):
    try:
        streak = Streak()
        pipeline = streak.get_pipeline_by_name('2016')
        stage = pipeline.get_stage_by_name(
            'TESTING' if settings.DEBUG else 'New Leads')
        box = stage.create_box(utils.domain_from_url(kw.get('brand_signedup_url')))
        box.update_fields({
            'Brand Name': kw.get('brand_signedup_brand_name'),
            'Brand URL': kw.get('brand_signedup_url'),
            'Created': int(time.mktime(datetime.datetime.now().timetuple()) * 1000),
            'Email': kw.get('brand_signedup_email'),
            'Person': '{} {}'.format(kw.get('brand_signedup_first_name'),
                kw.get('brand_signedup_last_name')),
            'Marketing Signup Page': kw.get('referer_tag'),
        })
    except:
        pass
