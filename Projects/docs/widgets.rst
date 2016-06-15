Widgets
================


Some call these portlets, some call them partials, we call them widgets. A widget is a component that is found on the
page and is pre-rendered before having its rendered HTML inserted into a parent page. In our application, we have two major
types of widgets:

* Feeds
    * *ShelvesFeed*
    * *WishlistItemsFeed*
    * *UsersFeed*
* ItemInfo


Widget
----------------------
The base class for all of our widgets. This class exposes a base functionality method for ``rendering`` of a widget subclass

.. autoclass:: debra.widgets.Widget
    :members:


Feed
^^^^^^
A subclass of **Widget**, this class encapsulates a list of items

.. autoclass:: debra.widgets.Feed
    :members:


ShelvesFeed
^^^^^^^^^^^^^
A subclass of **Feed**, this class encapsulates a list of :class:`debra.models.Shelf`.

.. autoclass:: debra.widgets.ShelvesFeed
    :members:


WishlistItemsFeed
^^^^^^^^^^^^^^^^^^^
A subclass of **Feed**, this class encapsulates a list of :class:`debra.models.ProductModelShelfMap`.

.. autoclass:: debra.widgets.WishlistItemsFeed
    :members:

    .. automethod:: __init__


UserFeed
^^^^^^^^^^^^^^^^^^^
A subclass of **Feed**, this class encapsulates a list of :class:`debra.models.UserProfile` or :class:`debra.models.Influencer`.

.. autoclass:: debra.widgets.UserFeed
    :members:


ItemInfo
^^^^^^^^^^^^^^^^^^^
A subclass of **Widget**, this class encapsulates the detailed display panel for a :class:`debra.models.ProductModelShelfMap`.

.. autoclass:: debra.widgets.ItemInfo
    :members:
