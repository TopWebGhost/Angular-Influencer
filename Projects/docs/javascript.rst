Javascript - **deprecated, old code**
=====================================


Now to the juicy bit, our Javascript. Within our Javascript code, we make heavy use of Object oriented techniques so
as to attempt to keep our files modular and readable. As for libraries, we make heavy use of the **jQuery** library, as well as the **Underscore.js** library,
primarily for its templating system.

From a high level, our Javascript can be grouped into 2 categories:

* Prototypal Javascript libraries - these are modular JS components which can be used in multiple places.
* Javascript that exists at the page level - this JS is primarily responsible for creating ``Objects`` defined in our prototype files.

Below is a more in-depth description of all of our JS files, functions, and methods:


Embeddable
----------------------

Collage
^^^^^^^^^^^
This file doesn't do too much. If the type of *widget* being rendered is a *collage*, It's sole purpose is to set
attributes of DOM elements based on ``data`` attributes set during during the creation process (i.e. Shelf name, Shelf URL).
*Carousel* widgets get the extra honor of having the method :js:func:`ImageManipulator.create_scrollable_images` called on
their images in order to create the scrollable effect.

Lottery
^^^^^^^^^^^
The *lottery* embeddable does a bit more. The *object* in charge on this page is constructed by the constructor:

.. js:class:: LotteryEmbeddable($container)

    :param $container: ``jQuery`` object containing the element which holds the *lottery*


On this object's prototype, we have the following functions defined:
.. js:function:: is_last_step(current_tab)

    :param current_tab: the tab (from the top of the *lottery*) that is currently selected
    :return: true if the user is on the last (reachable) step of the *lottery*

.. js:function:: _fb_login()

    :return: false

    This function is a hack to circumvent the Facebook cross origin policy's from within an iframe. What we do is,
    rather then use the code of *django-facebook* directly as we do in all other login / signup cases, we use the
    standard Facebook Javascript SDK methods to log the user in, then once we get an authorized response from FB,
    we manually submit the *django-facebook* form (the user is at this point logged into Facebook, so no problems will
    be hit).

.. js:function:: _reload()

    :return:

    This function reloads the iframe window. We use this in the case that the user has finished a tier of tasks. That is,
    they've either finished all mandatory tasks or finished all tasks.

.. js:function:: _increment_completed_points(current_tab)

    :param current_tab: the tab (from the top of the *lottery*) that is currently selected
    :return:

    A function to set the value of the points counter to the number of points already completed + the point value
    of the task contained in the ``current_tab``

.. js:function:: _next_incomplete_task(current_tab)

    :param current_tab: the tab (from the top of the *lottery*) that is currently selected
    :return:

    This function attempts to go to the next incomplete task in the *lottery*. If no tasks left are reachable at the user's
    tier, then we call :js:func:`_reload`.

.. js:function:: _mark_tab_as_complete(tab)

    :param tab: a ``jQuery`` object representing the tab in the *lottery* to mark as complete
    :return:

    This function marks the given ``tab`` as completed

.. js:function:: _all_tasks_except(task)

    :param task: the 'except' in ``_all_tasks_except``, this is the task which shouldn't be included in the result
    :return: array containing all of ``this.completed_tasks`` with the exception of ``task``

    A simple filter function to remove a ``task`` from the list of ``completed_tasks``.

.. js:function:: _get_task_with_id(task_id)

    :param task_id: the id of the task to fetch from ``this.completed_tasks``
    :return: the ``task`` object having the given id

.. js:function:: _replace_with_newer(task)

    :param task: if ``task`` already exists in ``this.completed_tasks``, then replace the old task in ``this.completed_tasks`` with ``task``
    :return:

.. js:function:: _show_tab_content(tab)

    :param tab: the ``jQuery`` object representing the tab whose content we want to show
    :return:

.. js:function:: _calculate_num_tasks()

    :return: the number of tasks remaining that are completable in the user's current tier.

.. js:function:: _toggle_terms()

    :return:

    Toggle display of the terms.

.. js:function:: _serialize_task(task)

    :param task: ``jQuery`` object containing an element which represents the task we want to serialize
    :return: the ``task`` serialized as a ``json`` object

.. js:function:: _submit_task(form, task, is_last_step)

    :param form: ``jQuery`` encapsulated ``form`` element which holds the information entered by the user to post to the server.
    :param task: the ``json`` encoded task to send to the server
    :param is_last_step: true if the form is submitting on the last reachable step in the current tier.
    :return:

.. js:function:: load_bindings()

    :return:

    Perform all bindings which should occur on load of the *lottery*

.. js:function:: click_bindings()

    :return:

    Perform all click bindings for the *lottery*.


Pages
----------------------

About Me
^^^^^^^^^^^^^^^^^^^^^^
The ``about_me.js`` file has one primary purpose, and that is dispatching the :js:class:: EditProfilePopup($container)
appropriately. By appropriately, I mean that the popup should be launched with a different start tab / content based
on which section of the *about me* page was clicked. To do this, ``about_me.js`` relies heavily on the :js:function:: EditProfilePopup.set_start_tab(start_tab)
function.

This file also has the single additional job of centering the images of the style collage within their containers for
collages that were system created (not created by users). This is accomplished via the following code block:

.. code-block:: javascript

    var image_manipulator = new ImageManipulator($(this), $(this).closest('.collage-image'));
    image_manipulator.assign_dimension_class();
    image_manipulator.center_image();


Admin
^^^^^^^^^^^^^^^^^^^^^^
``admin.js`` is one of those files that's getting close to the point of being in dire need of refactoring as its starting to
grow fat. The main object of the file, ``Admin``, exposes the following functions, which are dispatched from within the
``$(document).ready`` closure:

.. js:attribute:: Admin.categorized_items

    This attribute is used to store selections by the user on the *posts* and *products* admin pages. We later serialize
    the data stored in this attribute for transport to the server.

.. js:function:: generate_collage_screenshot(debug)

    :param debug: a debug flag. If true, we will open the image that was captured in a window.
    :return:

    This function uses ``html2canvas`` to generate a screenshot of a user's style collage. The primary use for this function
    is by an overnight script which calls this method to generate screenshots to be later sent out in emails.

.. js:function:: new_classification_tag(tag_val, container)

    :param tag_val: the name of the new tag being created
    :param container: the container for all added tags
    :return:

    This function is used by the *users* admin page to add classification tags to users.

.. js:function:: show_intercom_messages(url)

    :param url: the url to use for the ``GET`` request to fetch intercom messages sent to the user implicitly specified in ``url``
    :return:

    This function is used to show messages sent to a given user over intercom. It displays these messages in an instance of
    :js:class:`GenericMessageLightBox`

.. js:function:: save_blogger()

    :return:

    Used in the *influencer import* admin panel. This function saves the last blogger row added into ``Admin.added_bloggers`` array.

.. js:function:: delete_blogger($container)

    :param $container: ``jQuery`` wrapped element that points to a row in the import form
    :return:

    Remove the blogger that is displayed in ``$container`` from the ``Admin.added_bloggers`` array.

.. js:function:: add_blogger_row($page)

    :param $page: ``jQuery`` wrapped element that points to the element which we will append the new row to
    :return:

.. js:function:: set_layout_type(type)

    :param type: string representing which layout type to switch to (one of *div* or *table*)
    :return:


Lottery Analytics
^^^^^^^^^^^^^^^^^^^^^^
``lottery_analytics.js`` is a very simple Javascript file thats purpose is to act as a proxy between elements on the *lottery analytics* page
 and the lightbox which allows the user to choose a winner, :js:class:`ChooseLotteryWinnerLightBox`. ``lottery_analytics.js`` sole object, :js:class:`LotteryAnalyticsPage`, has
two methods:

.. js:function:: add_lottery_winner(winner)

    :param winner: a javascript object containing data about the winner of a *lottery*
    :return:

    This simple method updates the lottery winners on the page with chosen ``winner``

.. js:function:: remove_lottery_winner(winner_id)

    :param winner_id: the id of the winner to remove from the page
    :return:

    The inverse of the :js:func:`add_lottery_winner` function.


Middle Content Only
^^^^^^^^^^^^^^^^^^^^^^
``middle_content_only.js`` is a simple file responsible for creation of the ``feed`` one sees on various pages. This file
is loaded whenever the ``middle_content_only.html`` template file is loaded (which includes all the *Explore* pages, as
well as all the *Me* pages with the exception of the *About Me* page). The file creates an instance of the proper feed
type depending on the value of the ``data-feed-type`` attribute of the feed container.


Middle Content Sidebar
^^^^^^^^^^^^^^^^^^^^^^
Not currently used, but similar in purpose to ``middle_content_only.js``.


Pricing
^^^^^^^^^^^^^^^^^^^^^^
``pricing.js`` is loaded on any page that includes the ``pricing_options.html`` snippet. It includes bindings for
opening the ``stripe`` payment modal with the correct payment amount and values.


Search
^^^^^^^^^^^^^^^^^^^^^^
Much like ``middle_content_only.js``, ``search.js`` is responsible for creation of feeds. However, it
also has the additional responsibility of creating an appropriate :js:class:`FilterBar` instance. After creating
instances of these prototypes, ``search.js`` provides bindings for opening the contact us :js:class:`GenericFormLightBox`,
retrieving additional info about a blogger with an ajax call, and setting up ``autocomplete`` for blogger search.


Shelfit Panel
^^^^^^^^^^^^^^^^^^^^^^
``shelfit_panel.js`` is another straightforward Javascript file, with one exception. It provides the method :js:func:`not_logged_in`
which, like the :js:func:`_fb_login` method of ``embeddable/lottery.js``, is responsible for opening up the Facebook login
popup from within an iframe.


Protos
----------------------
The files inside the ``protos`` folder are really where all the magic happens. The objects defined in these files are built
to be both portable and extensible. Below are a description of the 'classes' and methods defined in these files.


Blogger Widget
^^^^^^^^^^^^^^^^^^^^^^
``blogger_widget.js`` provides implementation of methods for interaction on the *lottery*, *collage*, and *carousel* widgets.
While the individual widgets might have additional ``prototype`` files included to support widget specific functionality,
the main classes of this file, :js:class:`CollageWidget` and :js:class:`Lottery` - both of which specify :js:class:`BloggerWidget`
as their ``prototype``, are responsible for most of the process of widget creation. The definitions of these classes are
as follows:

.. js:class:: BloggerWidget($container, create_embeddable_url)

    :param $container: the ``jQuery`` object containing the element which holds the widget
    :param create_embeddable_url: the url for creation of the :py:class:`debra.models.Embeddable` instance responsible for rendering this widget

.. js:class:: CollageWidget($container, type, create_embeddable_url, download_url)

    :param $container: see :js:class:`BloggerWidget`
    :param type: the type of collage to create (one of 'carousel' or 'collage')
    :param create_embeddable_url: see :js:class:`BloggerWidget`
    :param download_url: the url which points to the :py:meth:`masuka.image_manipulator.download_image` view method.


.. js:class:: Lottery($container, create_embeddable_url, edit_mode, edit_urls)

    :param $container: see js:class:`BloggerWidget`
    :param create_embeddable_url: see js:class:`BloggerWidget`
    :param edit_mode: if true, we're in edit mode and should be allowed to skip between steps at will.
    :param edit_urls: an object of urls that will only be given in edit mode. These urls include:

    * render_embeddable_url - the url for rendering the ``lottery``
    * create_prize_url - the url for creating and editing prizes associated with this ``lottery``
    * create_task_url - the url for creating and editing tasks associated with this ``lottery``
    * preview_url - the url for this ``lottery``'s *preview* page.


Functions of :js:class:`BloggerWidget`
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. js:function:: _show_next_step(show_prev, previous_step)

    :param show_prev: if true, we won't hide the previous step when showing the next step.
    :param previous_step: ``int`` representing the step we're coming from. This is the step that will -unless ``show_prev=true`` - be hidden.

.. js:function:: click_bindings()

    Setup navigational bindings (what happens when a ``.tab`` is clicked.

.. js:function:: non_click_bindings()

    Setup tooltips and other bindings that should occur on page load.

.. js:function:: embeddable_preview(render_embeddable_url)

    :param render_embeddable_url: the url to use as the source of the ``iframe`` which contains the embeddable version of the widget.


Functions of :js:class:`CollageWidget`
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. js:attribute:: steps

    Provides a mapping of human readable steps to step numbers.

.. js:function:: _toggle_picked_images(force_turn_on, image)

    :param force_turn_on: if true, then rather then toggle the selection state of the ``image``, we will **always** make it selected.
    :param image: the ``jQuery`` object containing the image to toggle selection of.

.. js:function:: _toggle_all_images(force_turn_on, $btn)

    :param force_turn_on: see :js:func:`_toggle_picked_images`
    :param $btn: the 'Select All' button. We will change the text of this button as appropriate as part of this function execution.

.. js:function:: _select_picked_images()

    This function is used to manually add the selected class to all the images in our widget's ``picked_images`` object.

.. js:function:: _embeddable_code()

    Called when the user has clicked **Generate Code**, this function calls the :js:func:`Collage.copy` function to generate
    the code for the collage.

.. js:function:: _picked_as_list()

    A simple helper method to return all the values of our ``picked_images`` object as an array (assuming the value is truthy).

.. js:function:: specific_binding()

    This is where all :js:class:`CollageWidget` specific bindings occur. The major bindings that occur here are responsible
    for appropriately delegating to :js:class:`Collage` based on what interactions occur.

.. js:function:: goto_step(step_num, show_previous, next_click)

    :param step_num: ``int`` representing the next step to go to
    :param show_previous: if true, we won't hide the previous step when we go to the next step.
    :param next_click: if true, this function was called as a result of clicking the *next* button, not using the *nav bar*

    Each widget must provide its own implementation of this function (as it is what's called from the base :js:class:`BloggerWidget`'s
    :js:func:`_show_next_step` function, and so must have an implementation). The function provides specific logic that
    deals with moving between steps.


Classes of :js:class:`Lottery`
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. js:class:: LotteryItem($container, delete_url, id, lottery)

    :param $container: the ``jQuery`` object encapsulating the element which contains this ``LotteryItem``
    :param delete_url: the url for deleting this ``LotteryItem``
    :param id: the id of this ``LotteryItem``
    :param lottery: the :js:class:`Lottery` that this this ``LotteryItem`` is a part of.

    ``LotteryItem`` is the base class for both :js:class:`Prize` and :js:class:`Task`, client-side reprentations of
    :py:class:`debra.models.LotteryPrize` and :py:class:`debra.models.LotteryTask`, respectively.

.. js:class:: Prize($container, delete_url, id, lottery, description, brand, quantity)

    :param $container: see :js:class:`LotteryItem`.
    :param delete_url: see :js:class:`LotteryItem`.
    :param id: see :js:class:`LotteryItem`
    :param lottery: see :js:class:`LotteryItem`.
    :param description: the entered description of this ``Prize``
    :param brand: the entered brand of this ``Prize``
    :param quantity: the entered quantity of this ``Prize``

.. js:class:: Task($container, delete_url, id, lottery, task_name, is_mandatory, point_value, is_custom_task)

    :param $container: see :js:class:`LotteryItem`.
    :param delete_url: see :js:class:`LotteryItem`.
    :param id: see :js:class:`LotteryItem`
    :param lottery: see :js:class:`LotteryItem`.
    :param task_name: the entered name of this ``Task``
    :param is_mandatory: true if this ``Task`` is mandatory
    :param point_value: the entered point value of this ``Task``
    :param is_custom_task: only true if the type of task the user has entered is a *custom* task.

Functions of :js:class:`LotteryItem`
""""""""""""""""""""""""""""""""""""""""""""""""

.. js:function:: add_item(dropdown, is_edit)

    :param dropdown: ``jQuery`` encapsulated element representing the dropdown the user entered information about the added :js:class:`LotteryItem` into.
    :param is_edit: true if the user was editing a :js:class:`LotteryItem` that had previously been created

    This function is called immediately post creation of a :js:class:`LotteryItem`.

.. js:function:: click_bindings()

    Sets up the bindings for deleting this :js:class:`LotteryItem`.

Functions of :js:class:`Task`
""""""""""""""""""""""""""""""""""""""""""""""""

.. js:function:: set_step_num()

    This function is responsible for setting the *step_id* form field inside this :js:class:`Task` container appropriately.
    The *step_id* maps directly to the :py:attr:`debra.models.LotteryTask.step_id` field.

.. js:function:: submit_form()

    Submit the form contained inside this :js:class:`Task`'s ``$container``.

Functions of :js:class:`Lottery`
""""""""""""""""""""""""""""""""""""""""""""""""

.. js:attribute:: steps

    see :js:class:`Collage`

.. js:function:: make_wysiwyg(target)

    :param target: ``jQuery`` object representing the target for the ``wysiwyg``

     We use the (mediocre) ``wysihtml5`` library for creation of the ``wysiwyg``.

 .. js:function:: form_validate($form, hard_validate)

    :param $form: ``jQuery`` object containing the form to validate
    :param hard_validate: if true, then we show error messages (if there are any). False means we validate without showing messages.
    :return: true if ``$form`` is valid, false otherwise.

.. js:function:: _submit_base_form()

    :return: a ``deferred`` object.

    Submit the base lottery form (the one that creates a new :py:class:`debra.models.Lottery` instance).

.. js:function:: _add_item(form, container, resp_json)

    :param form: the form that was submitted to the server
    :param container: the ``jQuery`` wrapped container for the new item (item data will be inserted into this container)
    :param resp_json: the ``json`` response from the server after submitting the ``form``.

    This function is called directly after a user saves the form for creating a new item. Its primary role is to delegate
    to the :js:class:`LotteryItem`'s :js:func:`add_item` function.

.. js:function:: _get_items_of_type(type)

    :param type: a reference to one of :js:class:`Prize` or :js:class:`Task` (not an instance!)
    :return: an array of :js:class:`Prize` or :js:class:`Task` instances

    Get all items of a given ``type`` added to this :js:class:`Lottery`.

.. js:function:: _close_dropdown($dropdown)

    :param $dropdown: the ``jQuery`` object containing an element which represents a dropdown

.. js:function:: _create_embeddable()

    :return: ``deferred`` object

    Make a post request to this :js:class:`Lottery`'s ``create_embeddable_url``. The success handler sets the
    url for rendering the embeddable created from the request.

.. js:function:: specific_bindings()

    Dispatch all of the functions defined above as appropriate.

.. js:function:: goto_step(step_num)

    :param step_num: see :js:class:`CollageWidget`

    See :js:class:`CollageWidget`


Collage
^^^^^^^^^^^^^^^^^^^^^^
The :js:class:``



Feed
^^^^^^^^^^^^^^^^^^^^^^


Filter Bar
^^^^^^^^^^^^^^^^^^^^^^


Helpers
^^^^^^^^^^^^^^^^^^^^^^


Image Manipulator
^^^^^^^^^^^^^^^^^^^^^^


Item Info
^^^^^^^^^^^^^^^^^^^^^^


Lightbox
^^^^^^^^^^^^^^^^^^^^^^


Loader
^^^^^^^^^^^^^^^^^^^^^^


Sidebar
^^^^^^^^^^^^^^^^^^^^^^


Stripe
^^^^^^^^^^^^^^^^^^^^^^



Utils
----------------------



Common
----------------------
