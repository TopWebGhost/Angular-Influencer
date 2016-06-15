Tests and testing tools
***********************

Existing testing tools
======================

Product scraper (price tracker)
-------------------------------

This tool is implemented as a Django command in a module :mod:`xps.management.commands.extractxpaths`. 
The tool runs the scraper (:class:`xpathscraper.scraper.Scraper`) on the products
(:class:`debra.models.ProductModel` instances) loaded into the database from a fixture file
``xps/fixtures/test_urls.json``.

To load the fixture with products, run::

 ./manage.py loaddata xps test_urls

*Note that this will overwrite existing ProductModels having the same ids, so it shouldn't be run on
the production database.*

The fixture file can be edited directly, or a command ``addurltojson`` can be used that takes an url as
an argument, adds it to the fixture file and reloads all the fixture data.

When looking for the command's help (``./manage.py extractxpaths --help``),
multiple options are visible and some of them have "historical" naming or are
specific to some testing scenario. Usage examples::

 # test ProductModels with ids 1, 2, 10
 ./manage.py extractxpaths 1 2 10

 # test all available ProductModels
 ./manage.py extractxpaths all
 
 # test ProductModels with ids defined by Python lambda expression
 ./manage.py extractxpaths 'lambda id: 10 <= id <= 20'

 # test using multiple Firefox processes
 ./manage.py extractxpaths all --concurrency 10

The tool creates logs in ``miami_metro/xps/testlogs``. For each execution a directory with a timestamp
as a name is created. Inside each of these directories, there is a ``main.log`` file which contains
global messages, and for each tested product a file with ``id`` value is created.

Expected results are defined in :mod:`xps.testdata.valid_elements` file and in a spreadsheet (url
defined in :mod:`xps.testdata.valid_from_spreadsheet`) - the source can be selected using ``--ds``
option.


Email extractor
---------------

The module :mod:`platformdatafetcher.eetester` implements a tool for testing email extraction
(:mod:`platformdatafetcher.emailextractor` module). As a source of valid data emails already
validated by QA are used. The extractor is run on blog urls belonging to these influencers,
and the extracted email values are compared.

Usage::

 python -m platformdatafetcher.eetester eetester_qa <number_of_influencers_to_test> <number_of_firefox_processes>

At the end a report summarizing number of successes and failures is printed.


Platform extractor
------------------

The module :mod:`platfomrdatafetcher.petester` is an implementation of a testing tool for platform
extractor (:mod:`platformdatafetcher.platformextractor` module). Source of valid data is defined in
manually prepared spreadsheet "Blogger Outreach" (present in Git repository as a CSV file).

Usage::

 python -m platformdatafetcher.petester petester <row_from> <row_to> <number_of_firefox_processes>

Where ``row_from`` and ``row_to`` specify a range of rows to be tested from the spreadsheet/CSV file.


Checking quality of data by inspecting InfluencerEditHistory
------------------------------------------------------------

The module :mod:`platformdatafetcher.edithistorytool` implements a tool that uses
:class:`debra.models.InfluencerEditHistory` table, which records edits made by QA to each influencer
field. The tool inspects how much data was changed by QA and how much was left intact. This is a method
to test algorithm correctness, as in an ideal situation no data should be changed by QA, only marked as
valid.

For now only emails and social platform urls are checked. Other fields are harder to check, because QA
often have made edits like changing punctuation or letter case, which should be detected as not
important, but they are hard to detect automatically.

Usage::

 python -m platformdatafetcher.edithistorytool edit_history_check <hours> <what>

where ``hours`` is number of hours to look back and ``what`` is either ``emails`` or ``platforms``.

Tests to implement
==================
Integration tests framework should be implemented that will use a test database and datasets specified
for each test case (the database would be recreated after running each test case). Using mocks for things
like API access or fetching website content should be also probably implemented.

Unit tests should be used when possible - if an algorithm can be tested without database access and
APIs.

Some tests are more "monitoring scripts" than tests, because they use the production environment and
check if it behaves correctly.


Fetchers
--------

Modules: :mod:`platformdatafetcher.blogfetcher`,  :mod:`platformdatafetcher.socialfetcher`,
:mod:`platformdatafetcher.fetcherbase`, :mod:`platformdatafetcher.fetcher`,
:mod:`platformdatafetcher.fetchertasks`, :mod:`platformdatafetcher.externalposts`,
:mod:`platformdatafetcher.feeds`, :mod:`platformdatafetcher.postinteractionsfetcher`,
:mod:`platformdatafetcher.scrapingfetcher`.

They strongly rely on APIs and mocking it would be hard and a test would not do much of actual
testing.

A more ambitious approach is to try using a proxy that could automatically reply HTTP server (API)
responses (like http://mitmproxy.org/).

Generally the best solution to test fetchers seems to be a monitoring script that fetches data for
predefined platforms and checks if the results are as expected. But because calling an API and
scraping is error prone, the code must be intelligent enough to not signal errors when these random
things happen. It means that individual results must be stored and only after a series of errors
happens, a notification must be sent.


Algorithms modifying database models
------------------------------------

There are multiple algorithms, usually implemented as Celery tasks, that take a model's instance ID as an
input and modify attributes of an instance. These algorithms' tests should be implemented as integration
tests that use manually prepared snapshots of the database, and retrieve a model instance from the
database to test results.

The list of the algorithms:

- :mod:`platformdatafetcher.blognamefetcher` (the module contains a unit test for the main algorithm
  composing a blog name from page titles)
- :mod:`platformdatafetcher.brandnamefetcher`
- :mod:`platformdatafetcher.contentclassification` (the input of the algorithm is an url only, but
  the algorithm relies on the database for loading some data)
- :mod:`platformdatafetcher.contenttagging` (the main algorithm takes an url and a string as an
  input, so it can be unit tested)
- :mod:`platformdatafetcher.estimation`
- :mod:`platformdatafetcher.langdetection`
- :mod:`platformdatafetcher.pbfetcher`
- :mod:`platformdatafetcher.pdimport`
- :mod:`platformdatafetcher.platformcleanup`
- :mod:`platformdatafetcher.postanalysis`
- :mod:`platformdatafetcher.productutlsextractor`
- :mod:`platformdatafetcher.suspicions`
- functions for creating influencers and platforms in :mod:`debra.helpers`
- duplicate handling in :mod:`debra.models`
- denormalization in :mod:`debra.models`


Unit tests
----------

- :mod:`platformdatafetcher.contentfiltering`
- :mod:`platformdatafetcher.descriptionfetcher` (needs mocking of ``requests`` HTTP fetching)


Hard/impossible to test
-----------------------

- :mod:`platformdatafetcher.blogvisitor` - fake traffic generator (testing would require setting up a custom HTTP server and
  intercepting requests)
- :mod:`platformdatafetcher.geocoding` (monitoring scripts can be implemented like for fetchers,
  calling the real API)
- :mod:`platformdatafetcher.influencersearch` - searching for bloggers through scraping Google
  Search results
- :mod:`platformdatafetcher.influencerverification` - verification of influencer's fields based on
  scraping websites
- :mod:`platformdatafetcher.linkextractor` - extracting links (can be done by mocking HTTP fetching,
  or as a monitoring script)
- :mod:`platformdatafetcher.postprocessing` - submitting tasks (a snapshot with prepared input data
  can be set up and celery functions can be mocked)
- :mod:`platformdatafetcher.socialwidgets` - detecting social widgets (totally relies on
  HTTP/Javascript content - but can be implemented by using mocking/test pages)
- :mod:`platformdatafetcher.sponsorshipfetcher` - like the previous one

