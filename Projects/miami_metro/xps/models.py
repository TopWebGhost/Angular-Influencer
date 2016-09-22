import json

from django.db import models

import debra.models
from debra.constants import SHELF_BRAND_USER, SHELF_BRAND_PASSWORD, LIKED_SHELF
from debra import brand_helpers

from xpathscraper import scraper as scrapermod
from xpathscraper import utils
from raven.contrib.django.raven_compat.models import client
from django.core.exceptions import MultipleObjectsReturned

def get_or_create_brand(url):
    domain = utils.domain_from_url(url)
    brand, created = debra.models.Brands.objects.get_or_create(domain_name=domain)
    if created:
        brand.name = domain
        brand.save()
        brand_helpers.create_profile_for_brand(brand)
    return brand

class ScrapingResult(models.Model):
    '''Representation of a scraping result for a single tag (price, name, etc.).
    It logically consists of a list of xpath expressions and an option flag.

    This model class is a wrapper for a scraper.ScrapingResult class.
    The original wrapped object may be accessible as '_wrapped' instance.
    '''
    product_model = models.ForeignKey(debra.models.ProductModel, null=True, blank=True, default=None)
    flag = models.CharField(max_length=128, null=True)
    tag = models.CharField(max_length=128)
    value_json = models.CharField(max_length=4096, null=True, default=None)
    created = models.DateTimeField(auto_now=True)

    def fetch_xpath_exprs(self):
        return list(self.xpathexpr_set.all().order_by('list_index'))

    def get_values_as_tuple(self):
        return (self.tag, self.flag, tuple(xpe.expr for xpe in self.fetch_xpath_exprs()))

    def __unicode__(self):
        if hasattr(self, '_wrapped'):
            evaled = self._wrapped._evals_joined()
        else:
            evaled = '?'
        return u'tag={self.tag}, flag={self.flag}, exprs={exprs}, evaled=<{evaled}>, ' \
                'product_model_id={product_model_id}, value_json={self.value_json}'.\
                format(self=self, exprs=self.fetch_xpath_exprs(),
                        product_model_id=self.product_model.id if self.product_model else 'NULL',
                        evaled=evaled)


class XPathExpr(models.Model):
    '''XPath expression belonging to a :class:`ScrapingResult`.
    The expression are ordered using a `list_index` value.
    '''

    scraping_result = models.ForeignKey(ScrapingResult)

    # ordering number on a list of expressions
    # belonging to a single ScrapingResult
    list_index = models.IntegerField()

    expr = models.CharField(max_length=4096)

    def __unicode__(self):
        return 'scraping_result_id={self.scraping_result.id}, list_index={self.list_index}, ' \
                'expr={self.expr}'.format(self=self)


class ScrapingResultSet(models.Model):
    '''A set of ScrapingResult objects that are computed for a store.
    There can be multiple sets for a store, each with a description.
    '''
    brand = models.ForeignKey(debra.models.Brands)
    description = models.CharField(max_length=1024)

    def fetch_entries(self):
        res = []
        for srs_entry in self.scrapingresultsetentry_set.all().\
                order_by('scraping_result__id').select_related():
            res.append(srs_entry.scraping_result)
        return res

    def __unicode__(self):
        return 'brand={self.brand}, description={self.description}'.format(self=self)

    class Meta:
        unique_together = (('brand', 'description'),)


class ScrapingResultSetEntry(models.Model):
    '''Represents a single element of :class:`ScrapingResultSet` class.
    The ``product_model`` is an optional field telling which :class:`debra.models.ProductModel`
    this entry originated from.
    '''
    scraping_result_set = models.ForeignKey(ScrapingResultSet)
    scraping_result = models.ForeignKey(ScrapingResult)
    product_model = models.ForeignKey(debra.models.ProductModel, null=True, blank=True, default=None,
                                      on_delete=models.SET_NULL)
    entry_count = models.IntegerField(default=1, db_index=True)


class ScrapingResultSize(models.Model):
    """Records size of a given :class:`ScrapingResult`. Used for recording
    sizes of scraped images, can be used for other tags.
    """
    scraping_result = models.ForeignKey(ScrapingResult)
    width = models.IntegerField(null=True)
    height = models.IntegerField(null=True)
    size = models.IntegerField(null=True)


class CorrectValue(models.Model):
    '''This model stores values that should be extracted by the scraper
    for the given product. For example the following objects define
    two valid prices and one name (assuming `p` is a `Product` instance):

    >>> name = CorrectValue(product=p, tag='name', value='Nice T-Shirt')
    >>> price1 = CorrectValue(product=p, tag='price', value='$25')
    >>> price2 = CorrectValue(product=p, tag='price', value='$50')
    (probably wanted: calling save() to put them in DB)
    '''
    product_model = models.ForeignKey(debra.models.ProductModel)
    tag = models.CharField(max_length=128)
    value = models.CharField(max_length=1024)

    def __unicode__(self):
        return 'CorrectValue: product={self.product}, tag={self.tag}, value={self.value}'.format(self=self)


class FoundValue(models.Model):
    '''This is similar to `CorrectValue`, but it is for storing actual
    values returned by the scraper. `created` is an only additional field.
    '''
    product_model = models.ForeignKey(debra.models.ProductModel)
    tag = models.CharField(max_length=128)
    value = models.CharField(max_length=1024)
    created = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return 'FoundValue: product={self.product}, tag={self.tag}, value={self.value}'.format(self=self)



def create_scraping_result_models(product, tag, scraping_results):
    '''Converts a list of :class:`xpathscraper.scraper.ScrapingResult` objects
    to instances of a model class :class:`pdextractor.xps.models.ScrapingResult`.
    '''
    res = []
    for scraping_result in scraping_results:

        value_json = json.dumps(scraping_result.value) if scraping_result.value is not None else None
        if value_json and len(value_json) > 4096:
            value_json = json.dumps({'error': 'toolong'})
        m_scraping_result = ScrapingResult(product_model=product, tag=tag, flag=scraping_result.flag,
                value_json=value_json)
        m_scraping_result._wrapped = scraping_result
        m_scraping_result.save()

        for i, expr in enumerate(scraping_result.xpath_expr_list or []):
            xpathexpr_m = m_scraping_result.xpathexpr_set.create(list_index=i, expr=expr)
            xpathexpr_m.save()

        size_data = scraping_result.extra_data.get('size')
        if size_data:
            size_m = ScrapingResultSize()
            size_m.scraping_result = m_scraping_result
            size_m.width = size_data.get('width')
            size_m.height = size_data.get('height')
            size_m.size = size_data.get('size')
            size_m.save()

        res.append(m_scraping_result)
    return res


def create_wrapped_scraping_result(m_scraping_result):
    '''Opposite of :func:`create_scraping_result_models`: creates an instance of
    :class:`xpathscraper.scraper.ScrapingResult` that is equivalent to a model instance.
    '''
    if getattr(m_scraping_result, '_wrapped', None):
        return m_scraping_result._wrapped
    value = json.loads(m_scraping_result.value_json) if m_scraping_result.value_json is not None else None
    size_models = m_scraping_result.scrapingresultsize_set.all()[:1]
    if size_models:
        size_model = size_models[0]
        extra_data = {'size': {'size': size_model.size, 'width': size_model.width,
                               'height': size_model.height}}
    else:
        extra_data = {}
    return scrapermod.ScrapingResult(
            xpath_expr_list=[xpath_expr.expr for xpath_expr in m_scraping_result.xpathexpr_set.all().\
                    order_by('list_index')],
            flag=m_scraping_result.flag,
            value=value,
            extra_data=extra_data)


