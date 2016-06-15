Scraping process
================

XBrowser
--------
:class:`~xpathscraper.xbrowser.XBrowser` is a base building block for scraping
algorithms. It wraps a Selenium driver (web browser instance controlled by Python) and a headless
display, loads default Javascript and JSON files, and exposes utility methods.

Loading urls is done either by passing ``url`` argument to the ``__init__`` method, or by the
:meth:`~xpathscraper.xbrowser.XBrowser.load_url` method.

All Javascript files from a directory ``xpathscraper/js/`` are executed in a browser after a
supplied url is loaded (additional files can be specified using ``extra_js_files`` ``__init__``
argument).

All JSON files from a directory ``xpathscraper/json/`` are loaded into a ``_XPS.jsonData``
Javascript object (``_XPS`` is a default namespace object used by most Javascript code). For a file
named ``xpathscraper/json/abc.json`` it's contents (available as parsed Javascript objects) will be
available as ``_XPS.jsonData['abc']``. JSON data can be also accessed from Python, as parsed Python
objects, with similar syntax: ``xpathscraper.xbrowser.jsonData['abc']``.

Javascript files are executed using Selenium's ``execute_script`` method for default.
Alternatively, if :envvar:`XPS_JS_FROM_SERVER` environment variable is specified as ``1``, JS files
will be loaded from a HTTP server using a base url specified in
:data:`xpathscraper.xbrowser.JS_FILE_SERVER` (the files are loaded by appending ``<script>`` tags to
loaded document's ``<head>``). This method makes debugging easier, because Javascript stack traces
will contain file names and line numbers.

The preferred method to exchange data with a Selenium process (web browser) is
to write a Javascript function in one of the files inside ``xpathscraper/js/``
directory (which is included in :data:`xpathscraper.xbrowser.JS_FILENAMES`
list) and execute it using
:meth:`~xpathscraper.xbrowser.XBrowser.execute_jsfun` or
:meth:`~xpathscraper.xbrowser.XBrowser.execute_jsfun_safe`.

``XBrowser`` possibly allocates a new Selenium instance and a headless display, and it's required to
properly close these resources after a computation is finished. A method
:meth:`~xpathscraper.xbrowser.XBrowser.cleanup` does this and in a common case it should be placed inside a
``finally`` block or a ``with`` statement should be used to automatically call this method::

 with XBrowser() as xb:
    xb.load_url(url)
    # ...

Common Javascript code
----------------------
Common Javascript files put inside ``xpathscraper/js`` are:

* ``utils.js`` - utility functions - processing arrays, strings, functional utils like ``map`` and ``filter``
* ``elutils.js`` - common code operating on HTML elements - finding elements, operating on XPaths, clustering and many other
* ``scraper.js`` - code for extracting specific types of items, like prices and colors - works together with :class:`~xpathscraper.scraper.Scraper`.

The most important functions (defined in ``elutils.js``) are:


.. js:function:: _XPS.computeXPath(el)

    Computes an XPath expression uniquely identifying ``el``, using a short and "human readable"
    selectors.
    

.. js:function:: _XPS.evaluateXPath(expr)

    Evaluates the given ``expr`` XPath expression to an array of elements.


.. js:function:: _XPS.boundingRectForMultipleEls(els, margin)

   Computes a rectangle - an object with ``left``, ``right``, ``top`` and ``bottom`` attributes -
   that is the smallest rectangle that includes all elements from ``els`` array plus a ``margin``
   (in pixels).


.. js:function:: _XPS.minDistance(e1, e2)

    Computes middle-points for each of four borders for HTML element ``e1`` and ``e2`` and returns a
    minimum of distances between a point belonging to ``e1`` and a point belonging to ``e2``.


.. js:function:: _XPS.clusterCloseElements(els, closeEnoughFun[, selectElFun])

    :param els: An array of individual elements from which clusters should be built
    :param closeEnoughFun: A function accepting two arguments which are HTML elements, and returning
        a boolean value determining if the two given elements are close enough to be included in the
        same cluster.
    :param selectElFun: A function accepting an object from ``els`` array and returning HTML
        element to be included in clusters. If ``els`` array does not directly contain HTML elements
        (for example it's an array of pairs of elements and text contents), then this function should be
        used to select a valid HTML element for processing.
    :returns: A two-element array. The first element is an array of formed clusters (lists of `els`
        array members). The second element is a list of `els` members that are not included in any
        cluster.

    The main loop of this function processes pairs of elements from the `els` array. If elements
    belonging to a pair are close enough each other, they are included in the same cluster. If
    elements already did belong to clusters, the clusters are merged. The main loop is repeated as
    long as new clusters are formed or new elements are added to existing clusters.


.. js:function:: _XPS.attrsObject(el, attrArr, cssArr)

    Returns an object with the following attributes:

    * ``boundingRectangle`` - a rectangle object bounding ``el``
    * ``attrs.text`` - direct text content of ``el``
    * for each HTML element attribute ``a`` from ``attrArr``, ``attrs.a`` - with value of the attribute
    * for each CSS attribute ``a`` from ``cssArr``, ``attrs.a`` - with computed CSS value of the attribute

    This function is useful for exchanging data between Python and Javascript without using
    Selenium functions that cause much latency.


Scraper
-------
:class:`~xpathscraper.scraper.Scraper` is a class responsible for extracting data from product
pages, like: name, price, image. Different types of results have different *tags*: ``name``,
``price`` and ``img`` are result's tags. Results returned by the scraper are represented by lists of
:class:`~xpathscraper.scraper.ScrapingResult` objects. Each of them stores a specific result in one
of three attributes:

* ``xpath_expr_list`` - a list of XPath expressions pointing to results. Optionally, a
  ``flag`` can be used to tell more about a meaning of the list.
* ``value`` - a JSON-serializable object containing the result. Eg. for a price it can be a single
  ``'$10.99'`` string, for a size it can be list of strings with size values, like ``['2', '4',
  '6']``.
* ``rich_value`` - a Python *rich* object that represents a parsed value in a more
  semantically-rich way, eg. a price can be represented as ``PriceSingle(currency='$',
  amount=10.99)``.

Originally, all results were represented by lists of XPath expressions and they were passed in this
form to other modules, but a requirement to extract data from dynamic pages (requiring eg. a click)
made XPaths not a suitable representation for all possible results.

To extract results for a given tag, a method ``scraper.get_{tag}_xpaths`` should be executed, or a
tag name can be given as an argument using ``scraper.get_xpaths(tag)``.

.. _clicking-results:

Results of a clicking algorithm
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Results collected by clicking in colors and sizes combinations are treated in a different way. They
are computed by executing a method :meth:`xpathscraper.scraper.Scraper.perform_clicking`, which
returns a list of dictionaries. Each dictionary represents a result of going to a checkout page for
a single color/size combination. It possibly contains the following keys:

* ``sizetypevalue`` - list of size types as strings,
* ``inseamvalue`` - list of inseam values as strings,
* ``sizevalue`` - list of sizes as strings,
* ``colordata`` - list of dictionaries representing data for each parsed color:

  * ``name`` - color name
  * ``product_image`` - product image for this color
  * ``swatch_image`` - swatch image for this color

* ``checkoutprice`` - a list of :class:`xpathscraper.scraper.ScrapingResult` objects representing
  parsed prices (stored as ``rich_value`` attributes).


Exchanging data between Python and Javascript
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The algorithms are divided between Python and Javascript. Exchanging data between Python and
a Selenium process is slow when Selenium's functions are called many times (each call takes at least
20 ms). It means that code that processes DOM elements (eg. a search for elements containing some
text) must be implemented in Javascript and only a final list of elements should be returned to Python. 
A commonly used pattern is to return an DOM element together with it's text content (on Javascript's
side it is represented as a two-element array, in Python as :class:`xpathscraper.xbrowser.ElText`
two-element namedtuple), or an element together with an object/dictionary mapping attribute names to
values.

API
---
.. automodule:: xpathscraper.xbrowser
    :members:


.. autoclass:: xpathscraper.scraper.ScrapingResult
    :members:
.. autoclass:: xpathscraper.scraper.Scraper
    :members:
