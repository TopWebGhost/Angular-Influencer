The meaning of Influencer, Platform fields and where they are changed
=====================================================================

Influencer.show_on_search
-------------------------

Tells if an influencers should be included in the blogger search for an end user. This is not set to
``True`` automatically. This is done by a function run manually:
:func:`platformdatafetcher.postprocessing.upgrade_qa_influencers`. This function sets
:attr:`debra.models.Influencer.date_upgraded_to_show_on_search` as well as it records a PlatformDataOp
operation ``enable_show_on_search``.


Influencer.source
-----------------

Name of a mechanism by which an influencer was created, for example ``blogger_signup``,
``comment_import``. This is passed as an argument to the default function for creating influencers
:func:`debra.helpers.create_influencer_and_blog_platform`.

Multiple values are separated by ``:``. 

This value is set to ``NULL`` by the duplicate handling algorithm. Generally setting ``source IS NULL``
is a way to disable an influencer. Most functions that submit postprocessing tasks exclude these
influencers.


Influencer.blacklisted
----------------------

Tells if an influencer is invalid. This is set when an algorithms wants to remove an influencer from
further processing. Note that generally influencers and platforms shouldn't be deleted (see
:ref:`need-of-storing-invalid-data` ).

Usages:

- classifying an influencer (one of the first tasks performed on a newly created influencer) calls
  :func:`debra.models.Influencer.save_classification`, which sets ``blacklisted = True`` when a
  classification result is not ``blog``
- unregistering an influencer: :func:`debra.helpers.unregister_influencer`
- one-time scripts in :mod:`debra.scripts` and :mod:`hanna.scripts` that disable some specific invalid
  influencers
- :func:`platformdatafetcher.platformcleanup.detect_dead_blog` task

This flag is NOT set by the duplicate handling algorithm.


Influencer.blog_url
-------------------

This should store the url of a blog platform. Note that the function
:attr:`debra.models.Influencer.blog_platform` uses a different mechanism to find a blog platform: it
only looks at Platform models with a specific ``platform_name``. This is the same problem as with
``*_url`` fields as described in the "Problems" chapter.


Influencer.relevant_to_fashion
------------------------------

This is set by an algorithm in :mod:`platformdatafetcher.contentclassification` module. This field is
set in the initial stages of processing an influencer, so a way to check if an influencer finished the
"initialization" stages is to check if ``relevent_to_fashion__isnull=False``.


Influencer.is_active
--------------------

This is set by ``denormalize_influencer`` task, which checks if a post has been published in the last
90 days.


Platform.validated_handle
-------------------------

See :ref:`ref-validated-handle` for description.


Platform.url_not_found
----------------------

This is similar to :attr:`debra.models.Influencer.blacklisted` - if set to ``True`` then platform is
mostly excluded for further processing, is not visible in the blogger search interface etc.

Usages:

- fetcher classes set this if a ``validated_handle`` can't be fetched, which means they are surely
  invalid (usually API told that)
- one-time scripts in :mod:`debra.scripts`, :mod:`hanna.scripts`,
  :mod:`platformdatafetcher.platformcleanup`  that disable some specific platforms
- after QA edits an influencer, platforms not included in \*_url fields are marked as
  ``url_not_found = True``.

