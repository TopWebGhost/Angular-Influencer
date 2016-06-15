Website testing framework
=========================
This chapter describes scraping test suite that covers basic usage scenario for both bloggers and brands.
Tests uses :class:`~xpathscraper.xbrowser.XBrowser` as wrapper around selenium web drivers to simplyfy testing process.
Together with test suite runs django server  :class:`~tests.helpers.ServerRunner` (in separate thread) to add possibility of mocking functions and control
how server works (ex. adding locks for waiting for some functions to be complete). All tests are performed on live data.
Celery runs in *eager* mode - it means that all deferred calls are made instantly.

Bloggers testing
--------------------
:class:`~tests.blogger_tests.RegisterBlogger` is responsible for performing end-to-end testing of bloggers registration and basic profile customizing.

Testing process
+++++++++++++++

- setup of server, setup of :class:`~xpathscraper.xbrowser.XBrowser`
- remove instance of test user and influencer
- navigation to home page
- fillout registration form as blogger
- activate email
- verify blog page
- mark influencer as ready to use profile
- test profile customization

Notes
+++++

Email sending is tested by mocking mailing-related functions from django core.
We assume that there is page located under http://taigh.eu/ which contains correct The Shelf badge.
It can be made more generic by mocking :func:`debra.account_helpers.verify_blog_ownership_inner`.

Expected code coverage
++++++++++++++++++++++

- :func:`debra.account_views.brand_home`
- :func:`debra.account_views.blogger_signup`
- :func:`debra.account_helpers.bloggers_signup_postprocess`
- :func:`debra.account_views.shelf_login`
- :func:`debra.account_views.our_logout`
- :func:`debra.custom_backend.post_activation`
- :func:`debra.account_views.blogger_blog_not_ok`
- :func:`debra.account_views.blogger_blog_ok`
- :func:`debra.blogger_views.blogger_about`
- :func:`debra.blogger_views.blogger_edit`

Brands testing
--------------------
:class:`~tests.brand_tests.RegisterBrand` is responsible for performing end-to-end testing of brands registration, search page, competitors page, collections and campaigns.

Testing process
+++++++++++++++

- setup of server, setup of :class:`~xpathscraper.xbrowser.XBrowser`
- remove instance of test user and brand
- navigation to home page
- fillout registration form as brand
- activate email
- mark brand access as unlocked, assign plan (**Enterprise**)
- perform payment
- mark brand as non-agency
- navigate to search bloggers page
- test all filters in filter panel and keyword filters for both bloggers and posts view
- navigate to competitors page
- test all competitors feeds with **Zappos** as competitor
- navigate to collections tab
- create empty collection with special characters in name
- bookmark 2 influencers and check if they are visible in collection
- navigate to campaign tab
- create campaign and associate it with existing collection, verify if bloggers are visible
- create new campaign with system created collection
- bookmark 3 bloggers
- verify if they are visible in campaign table

Notes
+++++

Email, mixpanel and intercom calls are mocked (although page views makes intercom hit and register users).


Expected code coverage
++++++++++++++++++++++

- :func:`debra.account_views.brand_home`
- :func:`debra.account_views.brand_signup`
- :func:`debra.account_helpers.brands_signup_postprocess`
- :func:`debra.custom_backend.post_activation`
- :func:`debra.payment_views.brand_payment`
- :func:`debra.account_views.blogger_blog_ok`
- :func:`debra.search_views.blogger_search`
- :func:`debra.search_views.blogger_search_json`
- :func:`debra.feed_helpers.generic_post_feed`
- :func:`debra.feed_helpers.generic_product_feed`
- :func:`debra.search_views.autocomplete_with_type`
- :mod:`debra.brand_dashboard`
- :func:`debra.job_post_views.list_jobs`
- :func:`debra.job_post_views.list_details_jobpost`
- :func:`debra.job_post_views.get_influencer_groups`
- :func:`debra.job_post_views.set_influencer_groups`
- :func:`debra.job_post_views.add_influencer_groups`
- :func:`debra.job_post_views.delete_influencer_groups`
- :func:`debra.job_post_views.view`
- :func:`debra.job_post_views.add`
- :func:`debra.job_post_views.list_details`
- :func:`debra.job_post_views.list_details_jobpost`

Things to be done
+++++++++++++++++

- test all plan combinations
- test agency flow
- test blogger profiles
- test account settings
- test emailing

Classes
------------

.. py:class:: tests.blogger_tests.RegisterBlogger

.. py:class:: tests.brand_tests.RegisterBrand

.. py:class:: tests.helpers.ServerRunner

