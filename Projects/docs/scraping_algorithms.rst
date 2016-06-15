Scraping algorithms
===================
This chapter describes scraping algorithms implemented mostly in the
:class:`xpathscraper.scraper.Scraper` class.

Clustering algorithm
--------------------
*Cluster* is a list of HTML elements that are close each other. Computation of clusters is needed
for data that is spread across multiple HTML elements, for example sizes are often present in HTML
as multiple non-related elements.

The main clustering algorithm is implemented as :js:func:`_XPS.clusterCloseElements` Javascript
function. It needs a function to determine a distance between two elements and usually a function
:js:func:`_XPS.minDistance` is used. These two functions are defined in ``xpathscraper/js/elutils.js``.


Tournament algorithm
--------------------
When we have a list of objects and a comparison function that gets two objects and returns a
"better" object, a question arises about how to determine the "best" object.
This situation is present for cases when we have clusters of elements formed and we want to compute
the best cluster, assuming we have a function that compares two clusters. Computing just a numeric
score would be sufficient to rank clusters, but ability to directly compare two clusters is useful
(for example to check if one cluster is a sub-cluster of the other cluster).

The tournament algorithm is a simulation of a sports cup. Objects are paired and a "match" is played
(the comparison function is run), and the winning object is passed to the next round and the loosing
one is deleted from a pool of players. Pairing and playing matches is repeated until one object is
left.

Implementation of this algorithm is :func:`xpathscraper.utils.run_tournament`.


League algorithm
----------------
An alternative to the tournament algorithm. Every object plays with every other object, and a
winning one gets 1 point and a losing one gets 0 points. An object with a highest score is a winner.

Computing *img* results
-----------------------

All ``<img>`` and ``<canvas>`` elements that are closer than 500 pixels from a *name* element are
selected as initial candidates. For ``<img>`` elements, ``src`` attribute must point to a valid file
extensions (this check excludes PNG, GIF and SVG files). An aspect ratio of an image file, or a
whole element for ``<canvas>``, is checked if it isn't too wide or too high to be a valid product
image. Then a visual position of ``<img>`` or ``<canvas>`` element is checked in relation to a
*name* element:

* if a top border of an image doesn't start below a top border of a *name* element (+/- a small
  margin), the image is marked as invalid
* an image must be either next to a *name* element (horizontally), or directly below a *name*
  element

The biggest image passing all tests is selected as a product's image.

If an image is a ``<canvas>`` element, it's content is uploaded to S3 and URL of an uploaded image
is saved as a product's image.

Computing *name* results
------------------------

A first pass of the algorithm evaluates individual HTML elements using a scoring function, which
looks at three things:

* text score. First it's checked if ``<title>`` of a product page is meaningful, ie. if it
  isn't composed of mostly generic words like "welcome", "product details" and site's name. If it is
  meaningful, then a text score is computed as a percentage of words that are common to an element
  content and a title content. If it is not meaningful, then generic words are excluded and number of
  words inside an element is taken into consideration (the highest score is for elements that have
  2--5 words).
* font size. Bigger fonts get higher score.
* HTML tag importance (eg. ``<h1>`` gets the highest score and ``<h5>`` gets a low score).

Scores for these three features are combined by multiplying them and scaling a text score so that it
is given the highest weight.

A second pass of the algorithm looks into elements that got a non-zero score and forms two-element
combinations of them and uses a similar scoring function to evaluate pairs of elements (text content
is a concatenated text of two elements, font size and tag importance score is an average of scores for the individual elements).

The returned *name* result is an individual element or a combination of two elements which got the
highest score.

Computing *price* results
-------------------------
At first, HTML elements that contain valid price strings (a currency symbol and a number, and not
too many other words) are searched for. Then a list of HTML elements that possibly contain price
fragments is computed (a price fragment is a currency symbol, a number or a dot that isn't a valid
price itself, but can form a valid price when it's joined with near elements). The price fragments
are clustered and a check is performed to see if a cluster forms a valid price text.

For all prices coming from individual elements or clustered fragments a distance to a *name* element
is computed. As a final result, the nearest price is returned as well as all price elements that are
closer than 100 pixels to the nearest price.

The :class:`~xpathscraper.scraper.Scraper` class returns a flat list of prices (represented as a list
of :class:`~xpathscraper.scraper.ScrapingResult` instances). The prices returned by the
:class:`~xps.extractor.Extractor` class are grouped into :class:`xps.extractor.PricePair` objects
that contain a base price and a sale price. This grouping is implemented in the
:func:`xpathscraper.resultsenrichment._enrich_price` function, which runs clustering once again to
determine pairs of prices that are close each other.

Computing *size* results
------------------------

A Javascript function :js:func:`_XPS.findSizeElementsCandidates`, which returns HTML elements that
possibly contain an individual size value, is executed. Then, clusters are built from the returned
elements using an increasing sequence of pixel distances necessary to treat two elements as being
"close enough" to build a cluster. The result is a list of :class:`~xpathscraper.scraper.DistCluster`
tuples that are pairs of a cluster and a distance used to compute a cluster. The list is then
filtered using :meth:`~xpathscraper.scraper.Scraper._is_size_cluster_good_enough` method (this
methods checks if size values parsed from a cluster are a possibly valid sizes, or if a size numbers
range isn't a quantity range).

The filtered list is an input to a league algorithm. The match function is
:meth:`~xpathscraper.scraper.Scraper._better_size_cluster`. The function checks if a cluster isn't a
sub-cluster of the other cluster (:meth:`~xpathscraper.scraper.Scraper._adds_foreign_elements`) --
if it is, to loses. Then a numeric score is computed that takes into consideration number of valid
size values coming from cluster's elements as well as a distance used for computing the cluster
(lower distance gives a higher score).

Computing *color*, *sizetype*, *inseam* results
-----------------------------------------------

Computing these kinds of results is similar to computing *size* values, except they use a
tournament algorithm instead of a league algorithm. An implementation of a high level algorithm is
common, there are different functions for finding candidates to form clusters and to play a match
(see docstring for :meth:`xpathscraper.scraper.Scraper._play_tournament_and_get_xpaths` for details).

Search and evaluation is based on keyword search, with keywords defined in JSON files in
``xpathscraper/json`` directory. The most sophisticated keyword matching algorithm is implemented
for colors (:meth:`xpathscraper.scraper.Scraper._color_range_from_cluster`), which handles
multi-word colors and multiple colors contained in a single text value. 

