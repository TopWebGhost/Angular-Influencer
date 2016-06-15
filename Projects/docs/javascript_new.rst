Javascript - **new** - files breakdown
====================


about.js
++++++++

Bloggers/Brand profile about pages.

Controllers
-----------

.. js:data:: AboutBloggerCtrl
responsible for displaying widgets on profile pages and setup of salvattore

.. js:data:: AboutEditCtrl
handles profile edit page, data binding for form fields, logic behind past collaborations, informations for brands and image uploading


Directives
----------

.. js:data:: endorsedBrands
directive to display minified endorsed brands list and button for show more, when show more is clicked list is presented in its full version

.. js:data:: aboutBloggerPost
cut version of feed's post widget, displays profile page version of post

.. js:data:: photosGallery
handles carousel of instagram photos

blogger_info_popup.js
+++++++++++++++++++++

Logic behind influencers details panel popup

Directives
----------

.. js:data:: bloggerMoreInfo
it is directive that fires details popup, it creates new popup instance every time and appends it to dom tree, it also checks currently selected filters to modify details url and allow post/products filtering depending on filters

.. js:data:: bloggerMoreInfoPopup
this is popup implementation, when created it fires left-slide animation and in meantime loads details data. When data is loaded it appends posts and products widgets. It handles *show more* brand mentions logic. Also it allows to spawn bookmark and message popups

.. js:data:: bloggerItem
wraps simplified product widget to display photo, name and brand name of product

.. js:data:: bloggerPost
wraps simplified post widget to display photo and post content

blogger.js
++++++++++

Contains controller to spawn bloggers bookmark popup, **it can be merged into main file**

brand_dashboard.js
++++++++++++++++++

Controllers
-----------

.. js:data:: DashboardCtrl
manages logic of dashboard pages, it contains information about current brand (or competitor), allows to spawn bookmark popup

Directives
----------
.. js:data:: dashboardChart
displays statistics charts **currently only in debug mode**

.. js:data:: dashboardCompetitorsChart
displays statistics charts of competitors **currently only in debug mode**

.. js:data:: dashboardNav
manages current competitor dropdown

.. js:data:: brandMentioningInfluencers
manages brand's influencers on your analytics -> influencers **it should be merged into dashboardNav**

brand_nav.js
++++++++++++

Directives
----------

.. js:data:: brandNav
together with :js:data:`dashboardNav` its used to manage left navigation bar, it contains logic to minify sidebar, open/close tabs, manage menus and notifications. It also contains logic to spawn stripe popup as in the past there were limited brand plans which required payment to access some features

.. js:data:: dashboardNavSimple
simplified version of brand nav, allows only to change competitor

brand_settings.js
+++++++++++++++++

this file contains logic used in brands settings page

Controllers
-----------

.. js:data:: SettingsCtrl
manages tabs

.. js:data:: IsAgencyCtrl
**not used, can be deleted**

.. js:data:: CCEditCtrl
manages dropdowns and validation for credit card edit box


Directives
----------
.. js:data:: confirmUploadPopup
popup with yes/no buttons, currently used only on brand delete button **maybe name should be changed?**

.. js:data:: removeBrand
confirmation popup and logic to remove sub-brand from agency

.. js:data:: addBrand
manages add brand to agency box, uses :js:data:`matchBrand` to autocomplete brand urls

.. js:data:: settingsFormUploader
generic directive to save data from settings page sub-forms, in case of delete brand (whole account not sub-brand) it uses :js:data:`confirmUploadPopup` to confirm deletion

.. js:data:: setDefaultTo
useful generic directive to set default value of input field **its so generic it can be moved to main.js**

.. js:data:: location
wrapper aroung google places location autocomplete, it also notifies :js:data:`timezone` that it needs to re-lookup timezone

.. js:data:: timezone
used to autocomplete timezone utc offset, notified by :js:data:`location` about coordinates


contact_form.js
+++++++++++++++

Directives
----------
.. js:data:: contactForm
it is directive that manages dynamic loading of contact form, it uses very old contact form code so it's different from generic popup implementations

.. js:data:: broadcaster
it is duplicate of :js:data:`clickEmitter`, it can be replaced by it


dataexport.js
+++++++++++++
it contains directive to export raw influencers data to file, currently not used


factories.js
++++++++++++

.. js:data:: keywordQuery
keeps keyword search query (aka top search bar)

.. js:data:: filtersQuery
keeps filters (aka left search panel)

.. js:data:: tagStripper
utility to strip html down to plain text (it's not used anymore)

.. js:data:: singletonRegister
singleton register, used to verify if some popups (like login or signup which contains ids in form) has been created only once

filters.js
++++++++++

.. js:data:: float
changes null values into 0 and rounds floating point values

.. js:data:: topten
takes slice of 10 elements from input, can be enebled or disabled conditionaly by argument

.. js:data:: toptencat
same as :js:data:`topten` but used to take slice of categories in filter panel, returns only root categories

img_upload.js
+++++++++++++
contains directive used to spawn dynamicaly image upload popup (load, compile and add to dom)

invite_apply.js
+++++++++++++++
contains extracted piece of js code used on invited page

job_posts.js
++++++++++++

Controllers
-----------

.. js:data:: JobPostCtrl
manages create and edit job post page

.. js:data:: FavoritesCtrl
manages collections list page

.. js:data:: FavoritesTableCtrl
manages collection details page

.. js:data:: JobPostListCtrl
manages campaign list page

Directives
----------

.. js:data:: targetSearchFilters
modified version of :js:data:`bloggerSearchFilters` used to choice filters for campaign

.. js:data:: favoritedTable
manages table of influencers in campaigns and collections, spawns conversations, invite popup, details panel

.. js:data:: respondPopup
popup where you can reply from conversation thread

.. js:data:: bloggerConversation
contains list of messages between blogger and brand, spawns :js:data:`respondPopup` to reply to message

.. js:data:: messages
manages list of threads in messages page

.. js:data:: changeAssociationsPopup
not used anymore - allowed to change association between campaign and collection

.. _main_js:

main.js
+++++++

app configuration and generic controllers/directives

Directives
----------

.. js:data:: imgfit
directive used to center image inside container, there is better approach using css with background-size and background-position

.. js:data:: aHref
allows to navigate by clicking on any element

.. js:data:: eventReactor
allows to run callback as reaction to angular event

.. js:data:: clickEmitter
broadcasts and emits event from rootscope on click event

.. js:data:: confirmationPopup
displays confirmation popup with callback on yes/no buttons

.. js:data:: confirm
different version of :js:data:`confirmationPopup`

.. js:data:: trackMe
not used, it tracked event to intercom

.. js:data:: checkboxSelect
allows to display checkboxes inside dropdown

.. js:data:: matchBrand
used to autocomplete brand url from input text field

Generic popup mechanism
-----------------------
this file also contains logic of generic popups, every popup has
same set of functions provided by these directives, manages popup visibility,
closing/opening and state machine


popup_directives.js
+++++++++++++++++++

this file contains most of definitions of popups in application

.. js:data:: favoritePopup
currently it should be called bookmark popup, allows to create collection and add influencer to it

.. js:data:: addCollectionPopup
allows to add collection

.. js:data:: editCollectionPopup
allows to rename colection

.. js:data:: stripePopup
this popup handles credit card validation and stripe token generation, used in payment page

.. js:data:: imageUploadPopup
this popup allows to load image from file and crop it

.. js:data:: learnMoreBloggersPopup
simple informative popup

.. js:data:: loginPopup
popup that controlls login

.. js:data:: signupPopup
popup that controlls signup

.. js:data:: blogBadgePopup
popup with blogger badge generator

.. js:data:: brandMembershipPopup
not used

.. js:data:: loginRequiredPopup
not used, it was displayed when you had to login to see content

.. js:data:: editProfilePopup
not used

.. js:data:: featureLockedPopup
not used, it was displayed when plan was too low to dispaly feature

.. js:data:: emailBloggersPopup
not used

.. js:data:: exportPaidPopup
variation of :js:data:`stripePopup` it is used to allow payment for export influencers raw data without prior signup to website

.. js:data:: addCompetitorPopup
popup that allows to add competitor, uses :js:data:`matchBrand` to autocomplete brand url

.. js:data:: enterpriseBrandsEditPopup
not used anymore

.. js:data:: ccEditPopup
not used

.. js:data:: requestDemoPopup
not used

.. js:data:: trialOverPopup
not used

.. js:data:: proPlanSettingsPopup
it's used in registration process to allow users to choice if they are agency or not, it also allows to add first sub-brand if user selected agency

.. js:data:: messageInfluencerPopup
variation of :js:data:`respondPopup` to message bloggers directly from search page

.. js:data:: sendInvoicePopup
not used

.. js:data:: invitePopup
variation of :js:data:`respondPopup` to invite user from collection to campaigns

product_feeds.js
++++++++++++++++

One of most important files in project. Contains feeds (actualy not only product feeds but also blog, twitter, pinterst etc.)

.. js:data:: productFeed
this directive loads feed and creates grid of items for each feed element, there will be separate file to explain it

.. js:data:: feedItemPhotos
instagram feed item

.. js:data:: feedItemProducts
product feed item

.. js:data:: feedItemBlog
blog post feed item

.. js:data:: feedItemCollab
sponsored blog post feed item (not used)

.. js:data:: feedItemTweets
twitter feed item

.. js:data:: feedItemPins
pinterest feed item

.. js:data:: scrollWatch
directive used to watch for scroll bottom event in non-paginated feed mode, currently not used

search.js
+++++++++

One of most important files in project. Contains influencers feed.

.. js:data:: bloggerSearchFilters
left filter panel implementation

.. js:data:: bloggerContainer
container with influencers widgets grid, it will be explained more in separate file

.. js:data:: bloggerInfo
single influencer widget

.. js:data:: autocompleteInput
not used

.. js:data:: mixedAutocompleteInput
it allows to autocomplete different types of search queries like blog name or blogger name

search_posts.js
+++++++++++++++
not used anymore
