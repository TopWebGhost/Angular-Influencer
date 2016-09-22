import csv
import logging
import os
from pprint import pformat
from collections import defaultdict

import requests

import debra.models
from xpathscraper import utils


log = logging.getLogger('xps.testdata.valid_from_spreadsheet')

SPREADSHEET_URL = 'https://docs.google.com/spreadsheet/ccc?key=0Ai2GPRwzn6lmdGx6MldFczFFeGU0TWNzNDRWeGpNLVE&usp=drive_web&output=txt'


class ProductSpreadsheetData(object):

    def __init__(self, only_sample_per_domain=False):
        self.only_sample_per_domain = only_sample_per_domain
        self._parse_rows()
        self._insert_product_models()
        self._create_valid_by_product_id()
        self.CLICKING_RESULTS = {}
        self.INVALID_PRODUCT_PAGES = []

    def _parse_rows(self):
        self.r = requests.get(SPREADSHEET_URL)
        self.reader = csv.DictReader(self.r.iter_lines(),
            ['brand_url', 'num_items', 'brand_name', 'store_extra_info', 'empty1',
             'prod_url', 'img_url', 'prod_name', 'price', 'sale_price', 'product_extra_info'],
            delimiter='\t')
        self.rows = list(self.reader)[1:]
        self.rows = [row for row in self.rows if row.get('prod_url') and row.get('prod_name') and \
                     row.get('img_url') and row.get('price')]
        self.urls_to_process = set(r.get('prod_url') for r in self.rows)

        if self.only_sample_per_domain:
            by_domain = defaultdict(list)
            for row in self.rows:
                by_domain[utils.domain_from_url(row['prod_url'])].append(row)
            sample_rows = []
            for domain, domain_rows in by_domain.iteritems():
                with_sale_price = [r for r in domain_rows if r.get('sale_price').strip()]
                without_sale_price = [r for r in domain_rows if not r.get('sale_price').strip()]
                sample_rows += (with_sale_price + without_sale_price)[:2]
            log.warn('Rows after taking samples per domain: %s', pformat(sample_rows))
            self.urls_to_process = set(r.get('prod_url') for r in sample_rows)

    def _insert_product_models(self):
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
        assert settings_module and settings_module != 'settings', \
            'Production settings module used'
        existing = debra.models.ProductModel.objects.filter(id__lte=-1)
        log.info('Deleting %s ProductModels with negative ids', existing.count())
        existing.delete()
        self.row_by_id = {}
        for i, row in enumerate(self.rows, 1):
            if row['prod_url'] not in self.urls_to_process:
                continue
            prod = debra.models.ProductModel()
            prod.id = -i
            prod.prod_url = row['prod_url']
            prod.save()
            self.row_by_id[prod.id] = row

    def _create_valid_by_product_id(self):
        self.VALID_BY_PRODUCT_ID = {}
        for id, row in self.row_by_id.items():
            if row['prod_url'] not in self.urls_to_process:
                continue
            d = {}
            d['name'] = [row['prod_name']]
            d['img'] = [row['img_url']]
            d['price'] = [row['price']]
            if row.get('sale_price').strip():
                d['price'].append(row['sale_price'])
            self.VALID_BY_PRODUCT_ID[id] = d

