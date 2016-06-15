Problematic places and potential problems with the platform datamodel
=====================================================================


\*_url fields in Influencer and Platform's urls
-----------------------------------------------
QA enters space separated urls into \*_url fields of a :class:`debra.models.Influencer` model
(``fb_url``, ``insta_url`` etc.). From these values :class:`debra.models.Platform` models are
created and :attr:`debra.models.Platform.url` fields are filled. From this moment platforms start to
live their own lives - the url can be potentially changed, the platform can be invalidated. The
question is if/how the updated platform fields should be synchronized back to \*_url fields.

The field ``blog_url`` also has this problem, and some algorithms use it as a definition of a blog
url, and other use :func:`debra.models.Platform.blog_platform` function that searches for a platform
model with a proper ``platform_name``.

The script for checking differences between \*_url field values and platform urls is implemented as
:func:`debra.scripts.url_fields_platforms_inconsistency_checker`.


Overwriting data entered by QA by algorithms
--------------------------------------------
Algorithms fetching data from APIs/scraping data should generally not overwrite data that was
validated by QA (a helper method for checking this is
:meth:`debra.models.Influencer.is_enabled_for_automated_edits`). It means that it should be checked
explicitly by each algorithm and Influencer's field values should be logged using PlatformDataOp
mechanism (see :func:`platformdatafetcher.platformutils.record_field_change` usages).


URL redirection and other algorithms needing QA validation
----------------------------------------------------------
Assuming QA needs to validate correctness of data, algorithms can't just update data but they should
notify QA. An example is :func:`platformdatafetcher.platformcleanup.update_url_if_redirected`
function which inserts an :class:`debra.models.InfluencerCheck` when a url change is detected.


Dynamicity of platform and influencer data
------------------------------------------
Blog and social urls, as well as data like descriptions, locations is dynamic and can change any time.
This should generally be handled by the postprocessing task submission mechanism, where the ``min_days``
parameter specifies after how many days a task should be repeated. The current values are probably too
high (tasks should be repeated more frequently, without waiting months for all the data to update) and
should be somehow organized.

The problem of a blogger migrating from one URL to another should be handled by the
:func:`platformdatafetcher.platformcleanup.update_url_if_redirected` task. This task assumes that
HTTP-level redirects are correctly set up, for the main page as well as for each post. It looks like it's
quite often not the case, and this leads to two influencers which are practically duplicates. The
situation should be detected by a suspicion insertion module -- the ``suspect_social_dup`` table -- which
contains influencer duplicates found by looking at social handles equality.

Probably the problem of migrating from one blog to another should be handled by new code focusing on this
problem alone. Some issues are currently not addressed at all, like post urls changing after a blog
platform change.


Comparing URLs
--------------
Urls stored in the database are not normalized, and it's not safe to compare them - things like slashes
at the end, query params, HTTP vs HTTPS make the equality check false when in fact urls are equal.

Fetchers use a ``validated_handle`` field to overcome this problem for the
:attr:`debra.models.Platform.url`. This field contains a validated ID for an account for which an initial
url is used, which doesn't have to be normalized.

For normalizing URLs, a function :func:`platformdatafetcher.platformutils.url_to_handle` can be used. It
is used in duplicate handling algorithm.


PlatformDataOp overhead
-----------------------
The table is big and contains many indexes because of multiple foreign keys, which consume a lot of
disk space. :class:`debra.models.PdoLatest`

.. _need-of-storing-invalid-data:

Need of storing invalid data
----------------------------
Even though blacklisted influencers are practically "dead", they shouldn't be deleted from the database.
Information about them is used by functions in :mod:`debra.helpers` to skip inserting the same invalid
influencers over and over again.

No database transactions
------------------------
No database transactions are used and the Django setup uses autocommit setting (it's not worse than
Django's default setting in terms of robustness, but it prevents excessive locking). It increases risks
of leaving the database in incorrect state, especially by code making both database write operations and
network calls (for example API calls when creating a platform). For this reason exceptions should be
handled with care.

Too many tasks in queues
------------------------
The current setup uses the following queues:

- ``daily_fetching.<platform_name>`` - for daily ``fetch_data`` tasks. Each ``platform_name`` has it's
  own queue, for controlling API limits (when a limit is performed and ``sleep()`` is called, we must be
  sure no other process makes requests) and network calls.
- ``indepth_fetching.<platform_name>`` - the same structure as for ``daily_fetching.*`` queues, but for
  ``fetch_data`` tasks using :class:`platformdatafetcher.pbfetcher.IndepthPolicy`.
- ``denormalization``, ``estimation``, ``import_products_from_post``, ``platform_extraction`` and other -
  used for specific, individual tasks that are too heavy/important to share a common queue.
- ``platform_data_postprocessing`` - used for smaller tasks that shouldn't take much time or block
- ``platform_data_postprocessing_blocking`` - used for bigger tasks, usually the ones using Selenium

Most of the tasks have ``time-to-live`` set to one day, to enable resubmitting tasks each day and put the
most important one at the beginning. The problem is with ``platform_data_postprocessing`` and
``platform_data_postprocessing_blocking queues``, because there are many tasks put there, much more that
can be processed in a day. It can cause some tasks to not be processed at all, because the queues look
like (``A``, ``B`` and ``C`` are task types)::

    AAAAAAAAAAAAAABBBBBBBBBBBBBBBCCCCCCCCCCCCCCC

so if there's enough processing power for half of the tasks only, ``C`` will never be processed.

The solution is probably to either merge tasks before submitting then so they could be interleaved::

    ABCABCABCABCABCABC

or use a different queue structure.
