import json
from uuid import uuid4
import itertools
from collections import defaultdict

import requests
from bulk_update.helper import bulk_update

from debra import constants
from debra.decorators import cached_property


class ClickMeterApi(object):

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Clickmeter-Authkey': constants.CLICKMETER_API_KEY,
    }

    def get(self, endpoint, params):
        return requests.get(
            constants.CLICKMETER_BASE_URL + endpoint,
            headers=self.headers,
            params=params,
        )

    def post(self, endpoint, data):
        return requests.post(
            constants.CLICKMETER_BASE_URL + endpoint,
            headers=self.headers,
            data=json.dumps(data),
        )

    def put(self, endpoint, data):
        return requests.put(
            constants.CLICKMETER_BASE_URL + endpoint,
            headers=self.headers,
            data=json.dumps(data),
        )

    def delete(self, endpoint, data=None):
        return requests.delete(
            constants.CLICKMETER_BASE_URL + endpoint,
            headers=self.headers,
            data=json.dumps(data) if data else None,
        )


class ClickMeterException(Exception):
    
    def __init__(self, error_json):
        self.error_json = error_json
        self.error_text = json.dumps(self.error_json, indent=4)
        self.error_html = self.error_text.replace('\n', '<br />').strip('{}')
        super(ClickMeterException, self).__init__(self.error_text)


class ClickMeterListResult(object):

    def __init__(self, api, endpoint, params=None, offset=None, limit=None):
        self._api = api
        self._data = None
        self._limit = limit or constants.CLICKMETER_STATS_LIMIT
        self._offset = offset or 0
        self._count = self._limit + 1
        self._params = params or {}
        self.endpoint = endpoint

    def __iter__(self):
        return self

    def next(self):
        if self._offset >= self._count:
            raise StopIteration
        else:
            self._params.update({
                'offset': self._offset,
                'limit': self._limit,
            })
            response = self._api.get(self.endpoint, params=self._params)
            if response.status_code == 200:
                self._data = response.json()
            else:
                raise ClickMeterException(response.json())
            self._count = self._data.get('count', 0)
            self._offset += self._limit
            return self._data

    def find_entity_on_current_page(self, entity_id):
        try:
            return filter(
                lambda x: x.get('entityId') == entity_id,
                self._data['result']
            )[0]
        except IndexError:
            pass

    def find_entity(self, entity_id):
        for page in self:
            entity = self.find_entity_on_current_page(entity_id)
            if entity:
                return entity


class ClickMeterLinksHandler(object):

    def __init__(self, api, instance, include_pixels=False):
        self._api = api
        self._instance = instance
        self._include_pixels = include_pixels

    def handle(self, *args, **kwargs):
        raise NotImplementedError

    def response_processor(response):
        raise NotImplementedError

    def create_datapoints(self, datapoints):
        from debra.helpers import chunks
        print '* creating new datapoints for urls: {}'.format(datapoints)
        data = [self.get_datapoint_data_for_create(*datapoint)
            for datapoint in datapoints]
        if data:
            response = {'results': []}
            for data_chunk in chunks(data, constants.CLICKMETER_CHUNK_SIZE):
                response_chunk = self._api.put(
                        '/datapoints/batch', data={'list': data_chunk}).json()
                if response_chunk.get('results'):
                    response['results'].extend(response_chunk['results'])
        else:
            response = {}
        return self.response_processor(response)

    def update_datapoints(self, datapoints):
        from debra.helpers import chunks
        print '* updating datapoints: {}'.format(datapoints)
        data = [
            self.get_datapoint_data_for_update(*datapoint)
            for datapoint in datapoints]
        if data:
            response = {'results': []}
            for data_chunk in chunks(data, constants.CLICKMETER_CHUNK_SIZE):
                response_chunk = self._api.post(
                        '/datapoints/batch', data={'list': data_chunk}).json()
                if response_chunk.get('results'):
                    response['results'].extend(response_chunk['results'])
        else:
            response = {}
        return self.response_processor(response)

    def delete_datapoints(self, datapoints):
        from debra.helpers import chunks
        print '* deleting datapoints: {}'.format(datapoints)
        data = [
            self.get_datapoint_data_for_delete(*datapoint)
            for datapoint in datapoints]
        if data:
            # response = self._api.delete(
            #     '/datapoints/batch', data={'entities': data}).json()
            response = {'results': []}
            for data_chunk in chunks(data, constants.CLICKMETER_CHUNK_SIZE):
                response_chunk = self._api.delete(
                        '/datapoints/batch', data={'entities': data_chunk}).json()
                if response_chunk.get('results'):
                    response['results'].extend(response_chunk['results'])
        else:
            response = {}
        return self.response_processor(response)

    @cached_property
    def datapoints(self):
        return self.tracking_links + (
            self.pixels if self._include_pixels else [])

    @cached_property
    def tracking_links(self):
        results = ClickMeterListResult(
            self._api,
            '/aggregated/summary/datapoints', {
                'timeframe': 'beginning',
                'type': 'tl',
                'groupId': self._tracking_group,
            }
        )
        res = []
        for page in results:
            for entity in page['result']:
                res.append(entity.get('entityData', {}))
        return res

    @cached_property
    def pixels(self):
        results = ClickMeterListResult(
            self._api,
            '/aggregated/summary/datapoints', {
                'timeframe': 'beginning',
                'type': 'tp',
                'groupId': self._tracking_group,
            }
        )
        res = []
        for page in results:
            for entity in page['result']:
                res.append(entity.get('entityData', {}))
        return res

    def get_datapoint_values(self, func):
        return {
            entity.get('datapointId'):func(entity) for entity in self.datapoints
        }

    @cached_property
    def datapoint_tracking_codes(self):
        return self.get_datapoint_values(
            lambda entity: entity.get('trackingCode'))

    @cached_property
    def datapoint_entries(self):
        return self.get_datapoint_values(lambda entity: entity)

    @cached_property
    def datapoint_names(self):
        return self.get_datapoint_values(
            lambda entity: entity.get('datapointName'))

    @cached_property
    def datapoint_urls(self):
        return self.get_datapoint_values(
            lambda entity: entity.get('destinationUrl'))


class ClickMeterContractLinksHandler(ClickMeterLinksHandler):
    
    def __init__(self, *args, **kwargs):
        super(ClickMeterContractLinksHandler, self).__init__(*args, **kwargs)
        self._instance.campaign.generate_tracking_group()
        self._tracking_group = self._instance.campaign.tracking_group

    def handle(self, old_urls, new_urls, to_save=True):
        old_urls = filter(None, old_urls)
        new_urls = filter(None, new_urls)
        old_datapoints = zip(self._instance.product_tracking_links or [],
            old_urls)

        to_delete_datapoints = [
            x for x in old_datapoints if x[1] not in new_urls]
        self.delete_datapoints([(x[0],) for x in to_delete_datapoints])

        created_datapoints = self.create_datapoints(
            map(lambda x: (x,), list(set(new_urls) - set(old_urls))))

        new_datapoints = [
            x for x in itertools.chain(old_datapoints, created_datapoints)
            if x not in to_delete_datapoints
        ]

        print '* to delete datapoints: {}'.format(to_delete_datapoints)
        print '* new datapoints: {}'.format(new_datapoints)
        url_2_id_mapping = dict([(x[1], x[0]) for x in new_datapoints])
        ids_to_save = [url_2_id_mapping.get(url) for url in new_urls]
        self.save(ids_to_save, to_save=to_save)

    def save(self, datapoint_ids, to_save=True):
        self._instance.product_tracking_links = datapoint_ids
        if to_save:
            self._instance.save()

    def response_processor(self, response):
        return [
            (e.get('id'), e.get('typeTL', {}).get('url'))
            for e in map(
                lambda r: r.get('entityData', {}), response.get('results', [])
            )
        ]

    def get_datapoint_data_for_create(self, product_url):
        return {
            'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
            'groupId': self._tracking_group,
            'name': '{}'.format(uuid4()),
            'title': u"'{}' campaign for {}".format(
                self._instance.campaign.title, self._instance.id
            ),
            'type': 0,
            'typeTL': {
                'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                'url': product_url,
                'redirectType': 301,
            }
        }

    def get_datapoint_data_for_update(self, datapoint_id, url):
        data = self.get_datapoint_data_for_create(url)
        data.update({
            'id': int(datapoint_id),
            'preferred': True,
            'name': self.datapoint_names.get(int(datapoint_id)),
        })
        return data

    def get_datapoint_data_for_delete(self, datapoint_id):
        return {
            'id': int(datapoint_id),
            'uri': '/datapoints/{}'.format(str(datapoint_id)),
        }


class ClickMeterCampaignLinksHandler(ClickMeterLinksHandler):
    
    def __init__(self, *args, **kwargs):
        super(ClickMeterCampaignLinksHandler, self).__init__(*args, **kwargs)
        self._instance.generate_tracking_group()
        self._tracking_group = self._instance.tracking_group

    def save():
        pass

    def response_processor(self, response):
        data = [
            (int(e.get('title')), (e.get('id'), e.get('typeTL', {}).get('url')))
            for e in map(
                lambda r: r.get('entityData', {}), response.get('results', [])
            )
        ]
        result = defaultdict(list)
        for contract_id, pair in data:
            result[contract_id].append(pair)
        return result

    def get_datapoint_data_for_create(self, product_url, contract_id):
        return {
            'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
            'groupId': self._tracking_group,
            'name': '{}'.format(uuid4()),
            'title': u"{}".format(contract_id),
            'type': 0,
            'typeTL': {
                'domainId': constants.CLICKMETER_DEFAULT_DOMAIN,
                'url': product_url,
                'redirectType': 301,
            }
        }

    def get_datapoint_data_for_delete(self, datapoint_id):
        return {
            'id': int(datapoint_id),
            'uri': '/datapoints/{}'.format(str(datapoint_id)),
        }

    def handle(self, old_urls, new_urls, to_save=True, contract_ids=None):
        from debra.models import Contract
        old_urls = filter(None, old_urls)
        new_urls = filter(None, new_urls)

        if contract_ids is None:
            contracts = Contract.objects.filter(
                influencerjobmapping__job=self._instance)
        else:
            contracts = Contract.objects.filter(
                id__in=contract_ids)

        old_datapoints = {}
        for contract in contracts:
            old_datapoints[contract.id] = zip(
                contract.campaign_product_tracking_links or [],
                old_urls
            )

        to_delete = {}
        for contract in contracts:
            to_delete[contract.id] = [
                x for x in old_datapoints[contract.id]
                if x[1] not in new_urls
            ]

        self.delete_datapoints(
            map(lambda x: (x[0],), itertools.chain(*to_delete.values())))

        to_create = []
        for contract in contracts:
            for url in iter(set(new_urls) - set(old_urls)):
                to_create.append((url, contract.id))

        created_datapoints = self.create_datapoints(to_create)

        for contract in contracts:
            new_datapoints = [
                x for x in itertools.chain(
                    old_datapoints[contract.id],
                    created_datapoints[contract.id])
                if x not in to_delete
            ]
            url_2_id_mapping = dict([(x[1], x[0]) for x in new_datapoints])
            ids_to_save = [url_2_id_mapping.get(url) for url in new_urls]
            contract.campaign_product_tracking_links = ids_to_save

        if contracts:
            bulk_update(
                contracts, update_fields=['campaign_product_tracking_links'])

    def get_contract_product_links(self, contract):
        if self._instance.info_json.get('same_product_url'):
            return contract.campaign_product_tracking_links
        else:
            return contract.product_tracking_links
