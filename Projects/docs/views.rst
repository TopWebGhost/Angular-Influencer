Views
================


A major initiative in recent months has been to rename view file's more appropriately as well as to refactor existing
view logic to make so-called *fat models* rather then having heavy views. Below are the view's of our application:


Account Views
----------------------
The methods of this module handle tasks like account creation, login, and other account related tasks. Below
is the documentation for the functions of the :mod:`debra.account_views` module.

.. automodule:: debra.account_views
    :members:


Admin Views
----------------------
The methods of this module provide the basis for the pages rooted at */admin/upgrade/*. Below is the documentation for
the methods of the :class:`debra.admin.ModifyItemsAdminSite`.

.. autoclass:: debra.admin.ModifyItemsAdminSite
    :members:
