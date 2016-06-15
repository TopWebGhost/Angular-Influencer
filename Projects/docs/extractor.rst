Extracting product data
=======================

A module :mod:`xps.extractor` uses a :class:`~xpathscraper.scraper.Scraper` class to extract results
from product pages and save them into a database.

An :class:`~xps.extractor.Extractor` instance should be created for processing of a single product. It can be supplied with an existing ``driver`` instance or it can create a new one if ``None`` is passed (the default).

Results returned by ``Extractor``'s methods are represented as
:class:`xps.extractor.ExtractionResultsDict` instances, which are dictionaries and have a few additional attributes. Each result for a tag (computed for a static page) is stored as a dictionary entry with a tag name as key and a list of Python objects as a value. Results from a clicking algorithm (a list of dictionaries) are stored under a ``clicking_results`` attribute. These results can be further converted to a list of :class:`debra.models.ProductPrice` database models, together with linked :class:`debra.models.ColorSizeModels`, :class:`debra.models.Color` models, using :meth:`~xps.extractor.ExtractionResultsDict.create_product_prices_for_static_page` or :meth:`~xps.extractor.ExtractionResultsDict.create_product_prices_for_clicking_results`.

The :mod:`xpathscraper.scraper` module produces lists of
:class:`~xpathscraper.scraper.ScrapingResult` objects, and results stored in :class:`xps.extractor.ExtractionResultsDict` instances are Python objects - the convertion process is called *enrichment* and is handled mainly by a :mod:`xpathscraper.resultsenrichment` module. That module contains classes representing prices, names etc. If a :class:`~xpathscraper.scraper.ScrapingResult` supplies an object in a ``value`` or ``rich_value`` attribute, this value is directly used as an enrichment result.

When :mod:`xps.extractor` computes a result, it stores it in a database also. The models used are
defined in :mod:`xps.models`. This is mainly used for storing XPath expressions for bookmarklet
requests. If a :class:`xpathscraper.scraper.ScrapingResult` contains a non-empty  ``value_json`` attribute, it is also saved into a database as :attr:`xps.models.ScrapingResult.value_json` attribute. A ``rich_value`` field is not saved into a database.

The methods computing :class:`xps.extractor.ExtractionResultsDict` results are:

* :meth:`xps.extractor.Extractor.extract_from_url` - it needs a URL of a product page and a tag
  list, and it tries to use available xpath expression already stored in a database for a Product's
  Store (domain name). If there are no stored xpaths or the stored xpaths give invalid results, new
  set of xpaths is computed and saved as a set of xpaths for a Product's Store.
* :meth:`xps.extractor.Extractor.extract_using_computed_xpaths` - it doesn't look at xpaths already
  available for a Product and computes new xpaths and saves them to a database (for a Product only,
  not for a Store)
* :meth:`xps.extractor.Extractor.extract_using_store_xpaths` (takes `description` argument) - it
  looks for a proper :class:`xps.models.ScrapingResultSet` matching given `description`
  and Product's Store, and uses it for extracting values. They are returned even if they are
  invalid/incomplete.

These methods can be called multiple times for a singe `Extractor` instance.

Additionally, a lower-level function :func:`save_xpaths_for_store` can be used to copy xpaths that
are already stored for a given product to a :class:`xps.models.ScrapingResultSet` that is related to
a :class:`debra.models.Brands` product. This enables using this set of xpath expression for
extracting data from other products from the same store, without computing new xpath expressions for
them. Optionally, a `description` can be given to name this set and have multiple sets related to a
single store. The method :meth:`xps.extractor.Extractor.extract_from_url` calls this functions and
sets `description` to a URL given as an argument.


Example session:

>>> from xps import extractor
>>> from xpathscraper import xbrowser
>>> url = 'http://www.amazon.com/Allegra-Womens-Collar-Button-Sleeve/dp/B007WAF02E/ref=zg_bs_1045024_1'
>>> xb = xbrowser.XBrowser(url)
>>> e = extractor.Extractor(xb)
>>> e.extract_using_computed_xpaths(url, ['name', 'price', 'img'])
    ExtractionResultsDict({
     'img': [u'http://ecx.images-amazon.com/images/I/61uLAB7tA%2BL._SX385_.jpg'],
     'name': [u"Clothing & Accessories Allegra K Women's Point Collar Button Upper Long Sleeve Mini Dress"],
     'price': [u'$13.69 - $17.87']
    })


API
---

.. automodule:: xps.extractor
    :members:


.. automodule:: xps.models
    :members:

