Postprocessing tasks
====================

Postprocessing tasks are tasks that are executed offline for platforms, influencers and related data.
They fill missing data using APIs and scraping, compute statistics, parse existing content
to extract new data etc. They are executed using Celery workers.

.. _ref-pdo:

PlatformDataOp
--------------

The base assumption is that a set of tasks needs to be executed daily for the given set of
input data (platforms, influencers, brands etc.). Resources (API calls, CPU time etc.) are
limited so there is a need to sort and limit the input data so tasks should be executed
for the data that needs it the most. This is done by recording execution time for a given
platform, influencer etc. and a task name.

This information is stored inside :class:`debra.models.PlatformDataOp` model class, which
records each task execution individually, and inside :class:`debra.models.PdoLatest` which
only records latest time a given task was executed for a given model (that model class was
needed because using :class:`debra.models.PlatformDataOp` for collecting latest execution
times was too costly). Code that executes tasks usually uses a helper class,
:class:`platformdatafetcher.platformutils.OpRecorder`, which automatically fills some
fields and detects uncaught exceptions (information about errors is also stored inside
:class:`debra.models.PlatformDataOp`). The normal usage pattern is::
    with platormutils.OpRecorder(operation='some_task', influencer=my_inf) as opr:
        # doing some work with my_inf
        # ...
        opr.data = {'status': 'ok'}
The last line stores arbitrary JSON document, converted to
:attr:`debra.models.PlatformDataOp.data_json` (this is usually used for debugging, but can
also be used for storing custom data and querying for it later).

Ordering data
-------------
Assuming we have latest execution times, we can order input data, so the models which have
been waiting for the longest time are picked first (this can be viewed as a simplified
version of fetcher policies, which in addition to "age" use custom scores).

The task of ordering can take a lot of time itself, because of large amounts of data to
process. There are several implementations for it:

* :func:`platformdatafetcher.postprocessing._order_data_to_process` - the most correct
  version, uses only :class:`debra.models.PlatformDataOp` and not
  :class:`debra.models.PdoLatest`. It checks for consecutive errors - if there were less
  than 5 errors in a row, the task will be re-executed as if it wasn't executed the
  previous time (this prevents tasks failing for some random reason waiting a long
  time until the next execution slot appears).
* :func:`platformdatafetchr.postprocessing._order_data_fast` - does not differentiate
  between an erroneous and a successful execution, uses an SQL join between an initial
  query and :class:`debra.models.PlatformDataOp`.
* :func:`platformdatafetcher.postprocessing._order_data_using_pdo_latest` - does not
  differentiate between an erroneous and a successful execution. It reads whole content of
  :class:`debra.models.PdoLatest` table into memory (using an optimized dictionary
  implementation), and does joining and sorting using Python code. This is the fastest
  implementation.


Daily execution
---------------
The function :func:`platformdatafetcher.submit_daily_postprocessing_tasks` is the entry
point for task submission executed daily. The function calls small functions that submit
specific tasks, usually by specifying a database query first for selecting an initial set
of input data (eg. for ``fetch_blogname`` tasks platforms with non-existing ``blogname``
are selected), and then calling :func:`platformdatafetcher.postprocessing.order_data`
(which calls one of the functions described in the previous paragraph)
which orders and limits data according to latest execution date.

The queries used for submitting tasks are summarized in a spreadsheet: https://docs.google.com/spreadsheets/d/168BBkEwCJzDxkvwsWM0i4PUUb7LlKok5SFbwJHzefII

Postprocessing module documentation
-----------------------------------
.. automodule:: platformdatafetcher.postprocessing
    :members:


Supporting classes
---------------------
.. automodule:: platformdatafetcher.platformutils
    :members:

