Javascript - **new** - details
==============================

Feeds - blog, products, twitter, instagram, pinterest
+++++++++++++++++++++++++++++++++++++++++++++++++++++

From frontend perpective only thing needed to make feeds work is :js:data:`productFeed` element inside ng-app element and correct script files included (angular core, product feed, deps) and url from which we can query data. So some ultra-minimal feed would look like this:

.. code-block:: html

    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title></title>
        <link rel="stylesheet" href="">
        <script type="text/javascript" src="//ajax.googleapis.com/ajax/libs/jquery/1.8.3/jquery.min.js"></script>

        <!-- it can work without styles but we include them to make sure it works -->
        <script type="application/javascript" src="/static/js/vendor/less-1.4.1.js" charset="utf-8"></script>
        <link href="/mymedia/site_folder/css/global.less" media="screen" rel="stylesheet/less" />
    </head>
    <body ng-app="theshelf">

    <!-- feed itself -->
    <div product-feed filter='pins' source='/search/posts/json' paginated></div>

    <!-- other files are angular itself and some deps needed to boot the app -->
    <script type="application/javascript" src="/static/js/vendor/jquery.dotdotdot.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/angular.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/upload/angular-file-upload.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/ui-utils.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/angular-resource.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/angular-dropdowns.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/vendor/salvattore.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/app/main.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/app/product_feeds.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/app/factories.js" charset="utf-8"></script>

    </body>
    </html>

Of course in real life we include scripts using django-pipeline so final file contains blocks like *{% compressed_js 'core_head' %}* that does job for us. There should be also more classes and containers added to make styles hook up all css rules. Also please note that we use some existing endpoint */search/posts/json* which is actualy same view used by search page. Of course we can override filtering query but this is what filter panels are for. Those will modify keyword and filter queries in factories and broadcast signal that filters are modified which will trigger feed refresh. Also we didnt include blogger info popup which is needed to load bloggers detail panel - it will simply not work without it.

.. code-block:: html

    <script type="application/javascript" src="/static/js/angular/app/blogger_info_popup.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/vendor/jquery.nanoscroller.js" charset="utf-8"></script>


Additional attributes needs to be added to feed container to make bookmarking work (yes, you guessed it: *bookmarks* attribute). What is worth mentioning is that feed helpers functions uses POST with query inside request body (as json). Feed type can be changed by setting *filter* attribute and making endpoint handle it properly (*/search/posts/json* does it).

`Here <http://alpha-getshelf.herokuapp.com/mymedia/feed-example1.html>`_ is live example (you have to login on alpha to see results)

Influencers feed
++++++++++++++++

Influencers feed is little bit more complicated as it needs to be wrapped inside controller and also requires page to define two value providers. Here is minimal example:

.. code-block:: html

    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title></title>
        <link rel="stylesheet" href="">
        <link href="/mymedia/site_folder/css/global.less" media="screen" rel="stylesheet/less" />
        <script type="text/javascript" src="//ajax.googleapis.com/ajax/libs/jquery/1.8.3/jquery.min.js"></script>
        <script type="application/javascript" src="/static/js/vendor/less-1.4.1.js" charset="utf-8"></script>
    </head>
    <body ng-app="theshelf">

    <span ng-controller="BloggersSearchCtrl" id="bloggers_root">
    {{page_info}}
    <div blogger-container></div>
    </span>

    <script type="application/javascript" src="/static/js/vendor/jquery.dotdotdot.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/angular.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/vendor/bootstrap.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/upload/angular-file-upload.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/ui-utils.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/angular-resource.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/angular-dropdowns.min.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/vendor/salvattore.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/app/main.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/app/search.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/app/factories.js" charset="utf-8"></script>
    <script type="application/javascript" src="/static/js/angular/app/filters.js" charset="utf-8"></script>
    <script type="text/javascript">
    (function(){
    angular.module("theshelf").value('trial', false);
    angular.module("theshelf").value('debug', false);
    })();
    </script>
    </body>
    </html>

We had to define *trail* and *debug* values which are used in influencers feed internally. Actualy trial value is not used anymore and can be removed from implementation (it was used when project had implementation of trial period for brands which wants to subscribe). Debug value is used to enable or disable features in staging servers, it can be used to test new features. There is no url for source of influencers (it might be needed to refactor at some point). All filtering is done same way it is done in other feeds - using request body. BloggersSearchCtrl is populated with page info in *page_info*.

`Here <http://alpha-getshelf.herokuapp.com/mymedia/feed-example2.html>`_ is live example (you have to login on alpha to see results)

Feeds Internals
+++++++++++++++

All feeds works in very similar way - there is mechanism for pagination which tells what slice of data we need, filters are joined to create request body and then request to backend is made. After we have data, we do post processing (for example we check if we have enough data, we calculate pagination links since we know how many results there is for given filters etc.). Each item in feed is changed into html element with proper attributes (feed item elements share scope with containers so we can easily use 2-way binding through attributes). Finaly those elements are compiled by angular and inserted into grid. That grid is processed by salvattore which makes it evenly distributed on screen. Of course each item itself does some post processing, for example pinterest feed item will load plugin to get information about pin collection (which is scrapped and made invisible). All feed types reacts to change in url - to be precise change of hashbang which contains current page information. Completly separate thing is applying filters. This is universal mechanism which allows you to customize data visible in feeds. Search page is obvious case because we have separate widget which comunicates with containers using broadcasts and filters factories. But same feed widget is used in *competitors* page and *your analytics*. How is it made? We simply tell feed stream that it needs to filter out content depending on what we expect to see. If we want to see *Zappos* content then we tell feeds that it needs to filter content by brand query with *zappos.com* simply by broadcasting *setKeywordFilters* signal. Only tricky part is handling salvattore which is quite buggy. It needs to have container visible and focused so salvattore processing is fired only after container receives *focus* event. There is also plenty of backward-compatibility code since concept of feeds evolved through time eg. we can still mix different type of feeds (like posts together with tweets) but it's rather deprecated functionality.

Popups
++++++

Generic popups mechanism is inside :ref:`this <main_js>` file. It uses directive inside directive with transclusion mechanism. Consider following code snippet:

.. code-block:: js

    angular.module("popups", [])

    .directive('outer', function(){
        return {
            transclude: true,
            scope: false,
            template: "<div><hr>This is outer!<br><span ng-if='visible' ng-transclude></span><br>This is end of outer! You can toggle inner by clicking <a ng-click='toggle()'>here</a><hr></div>",
            link: function(scope, element){
                scope.visible = false;
                scope.toggle = function(){
                  scope.visible = !scope.visible;
                };
            }
        };
    })

    .directive('inner', function(){
        return {
            scope: true,
            template: "<div outer>This is inner, you can also toggle me <a ng-click='toggle()'>here</a></div>",
            link: function(scope){
            }
        };
    })
    ;

.. code-block:: html

    <div ng-app="popups">
        <div inner></div>
    </div>

(check it `here <http://jsfiddle.net/rvrh5524/>`_)

it demonstrate same mechanism behind popups. We have *outer* directive which controlls behavior of *inner* directive. It has non-isolated scope so *inner* directive can use *outer* function. In our popups case we have *outer* of *genericPopup* directives and *inner* of concrete implementation. There are few versions of popup which differs in template but have same functionality. *Outer* have functions to control visibility and state of popup. We can also do more complicated usages, for example we can use *setNoClose* function to disable closing of popup, or set *close_cb* callback which fires when popup is closed. Most of popups reacts to unique signal by doing some setup and opening itself.
