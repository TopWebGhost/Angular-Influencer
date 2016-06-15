Fetching data from Platforms (blogs and social sites)
=====================================================

A base building block is a *fetcher*, a subclass of :class:`platformdatafetcher.fetcherbase.Fetcher`.
Fetchers are used to fetch data from *platforms* (represented by :class:`debra.models.Platform` model
class). A platform is a social/blog page for a single user, for example a Facebook page like
https://www.facebook.com/pages/Penny-Pincher-Fashion/147607585304838 or a blog page like
http://www.pennypincherfashion.com/. A type of a platform - Facebook / Blogspot / Twitter etc. - is
stored in :attr:`debra.models.Platform.platform_name` field.

Each fetcher class defines which :attr:`platform_name` it handles by specifying a
:attr:`~platformdatafetcher.fetcherbase.Fetcher.name` class attribute. A list of all :class:`Fetcher`
subclasses used for fetching is defined as a :attr:`platformdatafetcher.fetcher.FETCHER_CLASSES` list,
and a dictionary :attr:`platformdatafetcher.fetcher.PLATFORM_NAME_TO_FETCHER_CLASS` maps a
``platform_name`` to a class implementing a fetcher for this type of platform (the assumption is that
there is only a single class for each ``platform_name``).

How the fetchers are used is decided by :class:`platformdatafetcher.pbfetcher.Policy` subclasses.
Policies tell if they should be applied to a :class:`~debra.models.Platform` by executing the
:meth:`~platformdatafetcher.pbfetcher.Policy.applies_to_platform` method (implemented in subclasses).
The method :meth:`~platformdatafetcher.pbfetcher.Policy.perform_fetching` receives a
:class:`~platformdatafetcher.fetcherbase.Fetcher` instance and should call ``fetch_posts``,
``fetch_post_interactions`` and ``fetch_platform_followers`` methods with appropriate ``max_pages``
arguments to get data (posts, posts interactions and platform followers) from platforms. A policy can
also do some work specific for a matched platform, like submit a Celery task for a specific type of an
influencer.

The other important method is :meth:`~platformdatafetcher.pbfetcher.Policy.importance_score`, which
assigns a numeric score to a platform, which is needed to sort platforms bases on their importance to
fetch data for the more important platforms first.  The currently implemented policies set higher
importance score for platform owners which are Shelf users, are popular (number of likes / followers)
or are trendsetters. The other component of the score is *age* - time since the last api was made for a
platform.

There shouldn't be a need to create fetchers and policies manually. The function
:func:`platformdatafetcher.fetcher.fetcher_for_platform` takes a :class:`~debra.models.Platform`
instance (a ``policy`` argument is for forcing usage of a specific policy and normally should be left
as ``None``) and creates a :class:`~platformdatafetcher.fetcherbase.Fetcher` instance which can be used
to fetch data for that platform. This function is used by Celery tasks
:func:`platformdatafetcher.fetchertasks.fetch_platform_data` and
:func:`platformdatafetcher.fetchertasks.indepth_fetch_platform_data` that receive a
:attr:`debra.models.Platform.id` and do fetching for the platform. The function
:func:`platformdatafetcher.fetchertasks.fetch_platform_data` is a high level function that can be used
in most cases for fetching data for a platform. It uses ``fetch_data`` PDO operation name (see
:ref:`ref-pdo`). It can also be run from command line to fetch data for a given Platform id and a policy
name::
    $ python -m platformdatafetcher.fetchertasks fetch_platform_data 1371048 forsearch

A summary of what fields are checked by :meth:`~platformdatafetcher.pbfetcher.Policy.applies_to_platform` is available in a Google spreadsheet: https://docs.google.com/spreadsheets/d/1u7gMTLUibsu8jotpGPXBwdoHN8gCMeoRBaQDMFtpFWw .

Alternative fetcher classes
---------------------------

There exists a mechanism for switching a fetcher implementation for a given
:class:`debra.models.Platform` instance to a different class. This is currently used when a default,
RSS-based fetcher class is not good enough for fetching (current condition: if there were no posts
fetched in the last 30 days), and an API-based fetcher should be used. A switch is made by writing a
class name (:class:`platformdatafetcher.fetcehrbase.Fetcher` subclass) to
:attr:`debra.models.Platform.fetcher_class`. If this field is non-empty, it has a higher priority
than a class found in :attr:`platformdatafetcher.fetcher.FETCHER_CLASSES`.

The alternative fetcher classes (that should be "more correct" than the default defined in 
:attr:`platformdatafetcher.fetcher.FETCHER_CLASSES`) are defined in
:attr:`platformdatafetcher.fetcher.FETCHER_CLASSES_ALTERNATIVE`.

.. _ref-validated-handle:

validated_handle of a platform
------------------------------
To prevent storing duplicated platforms, comparing just platform urls is not enough (for example,
both ``https://instagram.com/auser`` and ``https://instagram.com/#!/auser#q`` point to the same
social account). A mechanism involving :attr:`debra.models.Platform.validated_handle` field is used.
The field stores a validated, sure ID of an social account owner. The field value should come from
an API or some other verified source.

If a fetcher class wants to use this mechanism (it's currently used by API based fetchers and 
not used by :class:`platformdatafetcher.feeds.FeedFetcher`), it should call the base class method
:meth:`platformdatafetcher.fetcherbase.Fetcher._ensure_has_validated_handle` in ``__init__``, and
implement :meth:`platformdatafetcher.fetcherbase.Fetcher.get_validated_handle` that fetches ID for a
platform passed to ``__init__``. The ``_ensure_has_validated_handle`` method will set
:attr:`platformdatafetcher.Fetcher.url_not_found` flag according to validity of the returned value.


Executing fetchers using Celery tasks
-------------------------------------

Each platform name is assigned two queues: ``daily_fetching.<platform_name>`` and
``indepth_fetching.<platform_name>``.

The ``daily_fetching.*`` queues are meant to be filled with fetching tasks once per day (the queues
have ``time-to-live`` set to 24 hours, to prevent processing tasks older than one day). The function
that does this is :func:`platformdatafecher.pbfetcher.submit_daily_fetch_tasks`. It processes all
platforms in the database, computes importance scores using policies applied to them, sorts platforms
based on the score, and inserts tasks (the higher the score, the less time a platform will wait in the
queue, and the lowest scoring platforms can not be processed because of api limits errors and lack of
resources to process them in an 24 hour period).

The ``indepth_fetching.*`` queues are meant for a one-time processing of all data for all platforms in
the database (and ``daily_fetching.*`` queues are then used to only fetch newest posts / posts
interactions). After finishing a job for a platform, a flag
:attr:`debra.models.Platform.indepth_processed` is set and
:func:`platformdatafetcher.pbfetcher.submit_indepth_tasks` will not insert a task for such platforms
any more.


One-time scripts
----------------

There's often a need to write one-time scripts for doing something with the data in the database.  Such
scripts are usually located in :mod:`debra.scripts` or :mod:`hanna.scripts`. There's nothing special
about them, they are standalone functions/baker commands that can be run from Python or Bash shell. But
because they usually take long time to execute (they can process a lot of data), the following
recommendations should be applied:

- use the EC2 server because of much lower network latencies to the DB server
- run the script using ``tmux`` (or ``screen``) so that SSH connection drops will not disrupt the
  computation
- run the script as a background process and redirect output to a log file::

      python -m some.module command &> log.txt &

- handle exceptions with care - if you are processing data in a loop, make sure an exception
  will not break the whole process
- if the operation is important and you should have control over errors, don't use a single loop for processing - use Celery task for a custom queue and run celery workers for it
- even if it's a one-time operation, using PlatformDataOp for storing information about the execution
  and some debugging information will be helpful later, when looking for operations done for the given
  model
  

Fetching API
============


Base definitions for fetchers
-----------------------------
.. automodule:: platformdatafetcher.fetcherbase
    :members:

.. automodule:: platformdatafetcher.fetcher
    :members:

Policy based fetching
---------------------
.. automodule:: platformdatafetcher.pbfetcher
    :members:

Fetcher implementations
-----------------------
.. automodule:: platformdatafetcher.blogfetcher
    :members:

.. automodule:: platformdatafetcher.socialfetcher
    :members:
