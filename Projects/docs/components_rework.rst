Components needing rework
=========================

``platformdatafetcher.estimation``
----------------------------------
Manually defined keyword lists and match counts don't seem to work very well.


``platformdatafetcher.contentclassification``
---------------------------------------------
The same problem as with ``estimation``.

The problem of classification is hard, because it is performed before all the other algorithms are
run, so there is no access to lists of posts, validated social handles etc. The only input is blog
url.
