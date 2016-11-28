angular.module('theshelf')

.directive('postFeed', [
  '$http',
  '$compile',
  '$timeout',
  '$q',
  '$rootScope',
  '$stateParams',
  'keywordQuery',
  '$location',
  'context',
  'tsKeywordExpression',
  'tsMainSearch',
  'tsQuerySort',
  'tsLoader',
  'tsQueryCache',
  'tsQueryResult',
  'tsConfig',
  'msSearchMethod',
  'NotifyingService',
  'tsBrandNavigation',
  function (
    $http,
    $compile,
    $timeout,
    $q,
    $rootScope,
    $stateParams,
    keywordQuery,
    $location,
    context,
    tsKeywordExpression,
    tsMainSearch,
    tsQuerySort,
    tsLoader, 
    tsQueryCache,
    tsQueryResult,
    tsConfig,
    msSearchMethod,
    NotifyingService,
    tsBrandNavigation) {
    return {
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/post_feeds.html'),
      restrict: 'A',
      controller: function ($scope, $element, $attrs, $transclude) {
        var vm = this;

        $scope.savedSearchSource = $attrs.savedSearchSource;
        $scope.feedDefer = null;

        $scope.timeoutedCount = 0;

        $scope.doFetchPosts = function() {

          if (tsMainSearch.isBloggersMode())
            return;

          console.log("do search posts");

          $scope.populatePageInfo(null);

          var params = {
              filters: tsMainSearch.getFilters(),
              keyword: tsMainSearch.params.keywords,
              keyword_types: tsMainSearch.params.keywordTypes,
              group_concatenator: tsMainSearch.params.groupConcatenator,
              groups: tsMainSearch.params.groupNumbers,
              sort_by: tsQuerySort.get('keyword'),
              and_or_filter_on: tsMainSearch.isAndOrFilterOn(),
              filter: $scope.filter, // ???
              sub_tab: tsBrandNavigation.config.sub_tab,
              search_method: msSearchMethod.selected.value,
              influencer: vm.feedOptions.influencer,
          };

          params[$scope.mode_selected.feedPage] = $scope.page;

          if ($scope.feedDefer !== null)
            $scope.feedDefer.resolve();

          $scope.feedDefer = $q.defer();

          // $scope.clearPostsSalvattore();
          $scope.state = 'ok';

          tsLoader.startLoading();

          var retryTimeout = $timeout(function() {
            if ($scope.feedDefer !== null) {
              $scope.feedDefer.resolve();
              $scope.doFetchPosts();
              tsLoader.setTimeouted();
              // $scope.displayMessage("The site is a bit slow right now, so please re-try in a bit.");
              $scope.timeoutedCount++;
              if ($scope.timeoutedCount == 3) {
                  $scope.timeoutedCount = 0;
                  $scope.closeMessage();
                  $scope.feedDefer = null;
                  $timeout.cancel(retryTimeout);
                  $timeout(function(){
                      tsLoader.stopLoading();
                  },100);
                  $scope.state = "timeouted";
              }
              console.log("timeouted!");
            }
          }, 20000);

          $http({
            url: $scope.savedSearchSource + $scope.mode_selected.url + '/',
            method: 'POST',
            data: params,
            timeout: $scope.feedDefer.promise
          }).success(function(response) {

            console.log("search finished");

            $scope.timeoutedCount = 0;

            $scope.closeMessage();

            $scope.feedDefer = null;
            $timeout.cancel(retryTimeout);

            $scope.productFeedBloggers = response.results
              .filter(function(res) { return res.user; })
              .map(function(res) { return res.user; });
            $scope.productFeedPosts = response.results;

            tsQueryCache.set(params);
            tsQueryResult.set({
              total: $scope.productFeedBloggers.length,
              results: $scope.productFeedBloggers
            });

            if (response.results === undefined || response.results.length === 0) {
              $scope.state = 'no result';
              console.log('No results');
            }

            // save only one reference for each user
            $scope.users = {};
            angular.forEach(response.results, function(res) {
              if (res.user !== undefined) {
                if ($scope.users[res.user.id] === undefined)
                  $scope.users[res.user.id] = res.user;
                else
                  res.user = $scope.users[res.user.id];
              }
            });

            var data = response.results;

            var pageInfo = {
              sliceStart: Math.max(1, response.slice_size * ($scope.page - 1) + 1),
              sliceEnd: Math.min(response.total, response.slice_size * $scope.page),
              total: response.total
            };

            $scope.populatePageInfo(pageInfo);

            $scope.feeds = data;
            $scope.feeds.forEach(function(item, index) {
              item.index = index;
            });

            // $scope.rebuildPostsSalvattore(data);

            vm.handlePins();

            $scope.pages1 = [];
            $scope.pages2 = [];
            $scope.pages3 = [];
            $scope.page = $scope.page;
            $scope.num_pages = response.num_pages;
            var i = 0;
            for (i; i < response.num_pages && i < 3; i++)
                $scope.pages1.push(i + 1);
            for (i = Math.max($scope.page - 3, i); i < response.num_pages && i < $scope.page + 2; i++)
                $scope.pages2.push(i + 1);
            if (response.num_pages<100) {
              for (i = Math.max(response.num_pages - 3, i); i < response.num_pages; i++) {
                $scope.pages3.push(i + 1);
              }
            } else if(response.num_pages < 100) {
              $scope.plus100 = true;
            }

            angular.element("html, body").animate({
              scrollTop: 0
            }, 200);

            tsLoader.stopLoading();

            $timeout(function() {
                NotifyingService.notify('itemBlock:resize');
            }, 900);
          }).error(function(response, status) {
            $scope.feedDefer = null;
            $timeout.cancel(retryTimeout);
            $timeout(function(){
              tsLoader.stopLoading();
            },100);
            if (response === "limit") {
              $scope.state = "limit";
            } else if (status == 403) {
              $scope.state = "unauthorized";
            } else {
              // $scope.state = "error";
            }
          });
        };
      },
      controllerAs: 'postFeedCtrl',
      link: function feedLinkFunction(scope, iElement, iAttrs, ctrl) {

        ctrl.feedOptions = {
          mode: iAttrs.searchMode !== undefined ? 'search' : 'profile',
          influencer: iAttrs.forInfluencer,
        };

        ctrl.itemOptions = {
          nolabel: iAttrs.nolabel !== undefined,
          noheader: iAttrs.noheader !== undefined,
          skipSocial: iAttrs.skipSocial !== undefined,
          bookmarks: iAttrs.bookmarks !== undefined,
          debug: iAttrs.debug !== undefined,
          ugcView: iAttrs.ugcView !== undefined,
          showButtons: function() {
            if (context.visitorHasBrand && !this.ugcView) {
              return !this.noheader || iAttrs.showButtons !== undefined;
            }
            return false;
          },
          showSocials: function() {
            return !(this.noheader || this.ugcView);
          },
          showSocialLabel: function() {
            return tsMainSearch.getMode().url === 'all' || (!this.nolabel && !this.showSocials());
          },
        };

        ctrl.handlePins = function() {
          $timeout(function() {
            angular.element('#pinit').remove();

            var e = document.createElement('script');
            e.setAttribute('type', 'text/javascript');
            e.setAttribute('charset', 'UTF-8');
            e.setAttribute('id', 'pinit');
            e.setAttribute('src', '//assets.pinterest.com/js/pinit_main.js?r='+Math.random()*99999);
            e.setAttribute('data-pin-hover', 'true');
            document.body.appendChild(e);

            scope.$broadcast('pinterest_reloaded');
          }, 500);
        };

        $rootScope.postFeedsDefer.resolve();
      }

    };
  }
])

.directive('productFeed', ['$http', '$compile', '$timeout', '$q', '$rootScope', 'keywordQuery', '$location', 'context', 'tsConfig',
  function ($http, $compile, $timeout, $q, $rootScope, keywordQuery, $location, context, tsConfig) {
    return {
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/product_feeds.html'),
      restrict: 'A',
      scope: {
        filter: '@',
        sortBy: '@',
      },
      controller: function ($scope, $element, $attrs, $transclude) {
        var vm = this;

        $scope.feeds = [];

        $scope.feedTypes = {
          "all": {page: "pageAll", url: "all"},
          "facebook": {page: "pageFacebook", url: "facebook"},
          "blog": {page: "pageBlog", url: "blog_posts"},
          "photos": {page: "pageInst", url: "instagrams"},
          "products": {page: "pageProd", url: "products"},
          "collab": {page: "pageCollab", url: "collabs"},
          "tweets": {page: "pageTwitter", url: "tweets"},
          "pins": {page: "pagePin", url: "pins"},
          "youtube": {page: "pageVideo", url: "youtube"},
        };

        $scope.clearPages = function() {
          $scope.currentPage = {};
          $scope.lastPageEmpty = {};
          for (var i in $scope.feedTypes) {
            $scope.currentPage[i] = 1;
            $scope.lastPageEmpty[i] = false;
          }
        };

        $scope.resetPages = function() {
          $scope.clearPages();
          $scope.in_reset = true;
          $scope.loadPage();
        };

        $scope.setPage = function(number){
          if (number<1 || number > $scope.num_pages) return;
          $scope.currentPage[$scope.filter] = number;
          $scope.lastPageEmpty[$scope.filter] = false;
          $scope.in_reset = true;
          $scope.loadPage();
        };

        $scope.context = context;
        $scope.loading = false;
        $scope.in_reset = false;
        $scope.sourceUrl = $attrs.source;
        $scope.feedDefer = null;
        $scope.paginated = $attrs.paginated !== undefined;
        $scope.no_decorations = $attrs.noDecorations !== undefined;
        $scope.debug = $attrs.debug !== undefined;
        $scope.showButtons = $attrs.showButtons !== undefined;
        $scope.ugcView = $attrs.ugcView !== undefined;
        $scope.savedSearchSource = $attrs.savedSearchSource;

        $scope.clearPages();

        $scope.loadPage = function () {

            console.log('do search posts');

            $scope.loading = true;

            var params = {
                filter: $scope.filter,
                sort_by: $scope.sortBy,
            };

            var hash = [];
            hash.push($scope.feedTypes[$scope.filter].url);
            hash.push($scope.currentPage[$scope.filter])

            params[$scope.feedTypes[$scope.filter].page] = $scope.currentPage[$scope.filter];

            if ($scope.paginated && !$scope.no_decorations) {
              $location.path(hash.join("/"));
            }

            if ($scope.feedDefer !== null) {
              $scope.feedDefer.resolve();
            }
            $scope.feedDefer = $q.defer();

            $scope.clearSalvattore();
            $scope.state = "ok";

            var retryTimeout = $timeout(function() {
              if ($scope.feedDefer !== null) {
                $scope.feedDefer.resolve();
                $scope.loadPage();
                console.log('timeouted!');
              }
            }, 20000);

            $http({
              url: ($scope.savedSearchSource ? $scope.savedSearchSource + $scope.filter2url($scope.filter) + '/' : $scope.sourceUrl),
              method: 'POST',
              data: params,
              timeout: $scope.feedDefer.promise
            }).success(function (response) {

                console.log("search finished");

                $scope.feedDefer = null;
                $timeout.cancel(retryTimeout);

                if(response.results == undefined || response.results.length == 0){
                  $scope.state = "no result";
                  console.log("No results");
                }

                // save only one reference for each user
                $scope.users = {};
                angular.forEach(response.results, function(res) {
                  if (res.user !== undefined) {
                    if ($scope.users[res.user.id] === undefined)
                      $scope.users[res.user.id] = res.user;
                    else
                      res.user = $scope.users[res.user.id];
                  }
                });

                var data = response.results;

                // pass total results number to the parent scope
                // (as this directive's scope is isolated)
                if ($attrs.propagateTotal !== undefined) {
                  $scope.$parent.totalLoading = false;
                  $scope.$parent.total = response.total;
                  $scope.$parent.page_info = {
                    sliceStart: Math.max(1, response.slice_size * ($scope.currentPage[$scope.filter] - 1) +1 ),
                    sliceEnd: Math.min(response.total, response.slice_size * $scope.currentPage[$scope.filter]),
                    total: response.total
                  };
                  $scope.$parent.productFeedBloggers = response.results
                    .filter(function(res) { return res.user; })
                    .map(function(res) { return res.user; });
                  $scope.$parent.productFeedPosts = response.results;
                }

                var platformCounts = {};
                for (var i in $scope.feedTypes) {
                  platformCounts[i] = 0;
                }

                if (true && $scope.in_reset) {
                  $scope.feeds = data;
                  angular.forEach($scope.feeds, function (item, index) {
                    item.index = index;
                    platformCounts[item.platform]++;
                  });
                  platformCounts['all'] = _.reduce(_.values(platformCounts), function(x, y) { return x + y; });
                  $scope.rebuildSalvattore(data);
                  //salvattore gets crazy when non-focused
                  // $(window).bind('focus', function(){
                  //   $scope.rebuildSalvattore(data);
                  //   $scope.in_reset = false;
                  //   $(window).unbind('focus');
                  // });
                } else {
                  angular.forEach(data, function (item) {
                    platformCounts[item.platform]++;
                  });
                  $scope.feeds = $scope.feeds.concat(data);
                  angular.forEach($scope.feeds, function (item, index) {
                    item.index = index;
                  });
                  $(window).bind('focus', function(){
                    $scope.updateSalvattore(data);
                    $(window).unbind('focus');
                  });
                }
                if(document.hasFocus()){
                  $(window).focus();
                }

                for (var i in $scope.feedTypes) {
                  if (platformCounts[i] == 0) {
                    $scope.lastPageEmpty[i] = true;
                  }
                }

                if ($scope.paginated) {
                    $scope.pages1 = [];
                    $scope.pages2 = [];
                    $scope.pages3 = [];
                    $scope.page = $scope.currentPage[$scope.filter];
                    $scope.num_pages = response.num_pages;
                    var i = 0;
                    for (i; i < response.num_pages && i < 3; i++)
                        $scope.pages1.push(i + 1);
                    for (i = Math.max($scope.page - 3, i); i < response.num_pages && i < $scope.page + 2; i++)
                        $scope.pages2.push(i + 1);
                    if (response.num_pages<100) {
                      for (i = Math.max(response.num_pages - 3, i); i < response.num_pages; i++){
                        $scope.pages3.push(i + 1);
                      }
                    } else if(response.num_pages<100) {
                      $scope.plus100 = true;
                    }

                    if (!$scope.no_decorations) {
                      $("html, body").animate({
                          scrollTop: 0
                      }, 200);
                    }
                }

                $scope.loading = false;
              }).error(function(a,b,c,d){
                $timeout.cancel(retryTimeout);
                if(a == "limit"){
                  $scope.state = "limit";
                }
              });
        };

        var handle_path = function(needLoad) {
          if (!$scope.paginated) {
            return;
          }
          var path = $location.path();
          var page = path.substr(1).split('/')[1];

          needLoad = (needLoad === undefined ? false : needLoad);

          if (page) {
            if (!$scope.lastPageEmpty[$scope.filter]) {
              var cpage = $scope.currentPage[$scope.filter];
              var tpage = Number(page);

              if (tpage > 0 && cpage != tpage) {
                $scope.currentPage[$scope.filter] = tpage;
                needLoad = true;
              }
            }
          }

          if (needLoad) {
            $scope.in_reset = true;
            $scope.loadPage();
          }
        };

        $scope.$on('$locationChangeSuccess', handle_path);

        $scope.$on('reloadFeeds', function(){
          $scope.resetPages();
        });

        $scope.$on('scrolledBottom', function() {
          if ($scope.paginated) return;
          if ($attrs.trial !== undefined) return;
          if ($scope.loading) return;
          if (!$scope.lastPageEmpty[$scope.filter]) {
            $scope.currentPage[$scope.filter]++;
            $scope.loadPage();
          }
        });

        $timeout(function() {
          if ($scope.paginated) {
            handle_path(true);
          } else {
            $scope.loadPage();
          }
        }, 250);
      },
      controllerAs: 'productFeedCtrl',
      link: function (scope, iElement, iAttrs, ctrl) {

        ctrl.itemOptions = {
          nolabel: iAttrs.nolabel !== undefined,
          noheader: iAttrs.noheader !== undefined,
          skipSocial: iAttrs.skipSocial !== undefined,
          bookmarks: iAttrs.bookmarks !== undefined,
          debug: iAttrs.debug !== undefined,
          ugcView: iAttrs.ugcView !== undefined,
          showButtons: function() {
            if (context.visitorHasBrand && !this.ugcView) {
              return !this.noheader || iAttrs.showButtons !== undefined;
            }
            return false;
          },
          showSocials: function() {
            return !(this.noheader || this.ugcView);
          },
          showSocialLabel: function() {
            return !this.nolabel && !this.showSocials();
          },
        };

        // $(window).bind('resize', function(){
        //   scope.$apply(function(){
        //     scope.$broadcast('windowResize');
        //   });
        // });
        scope.grid_scope = null;
        scope.salvattore_registered = $q.defer();
        scope.salvattore_refresh_timeout = null;
        scope.create_scrollable_collages = function($containers) {
            $containers.each(function() {
                ImageManipulator.create_scrollable_images($(this));
            });
        };
        scope.clearSalvattore = function() {
          // var grid = iElement.find('.salvattore_grid');
          // $timeout(function() {
          //   grid.children().remove();
          // }, 0);
          $("html, body").animate({ scrollTop: 0 }, 200);
        };
        scope.rebuildSalvattore = function () {$("#pinit").remove();
          var e = document.createElement('script');
          e.setAttribute('type', 'text/javascript');
          e.setAttribute('charset', 'UTF-8');
          e.setAttribute('id', 'pinit');
          e.setAttribute('src', '//assets.pinterest.com/js/pinit_main.js?r='+Math.random()*99999);
          e.setAttribute('data-pin-hover', 'true');
          document.body.appendChild(e);
          scope.$broadcast("pinterest_reloaded");
          scope.$broadcast('windowResize');
          return;

          var grid = iElement.find('.salvattore_grid');
          var items = [];
          grid.children().remove();
          var options = [];
          if(iAttrs.skipSocial !== undefined) {
            options.push("skip-social");
          }
          if(iAttrs.bookmarks !== undefined) {
            options.push("bookmarks");
          }
          if(scope.debug) {
            options.push("debug");
          }
          if (scope.showButtons) {
            // show ONLY buttons, without user profile
            options.push("show-buttons");
          }
          if (scope.ugcView) {
            options.push("ugc-view");
          }
          var element;
          grid.css({opacity: 0});
          angular.forEach(scope.feeds, function (item) {
            if(scope.filter !== 'all'){
              if(scope.filter !== item.platform){
                return;
              }
            }
            element = '<div feed-item feed-item-' + (item.platform) + ' item="feeds[' + item.index + ']" filter="filter" ' + options.join(" ") + '></div>';
            grid.append(element);
          });
          if(scope.grid_scope){
              scope.grid_scope.$destroy();
          }
          scope.grid_scope = scope.$new();
          $compile(grid)(scope.grid_scope);
          var add_items_rebuild = function (){
            try{
              salvattore['register_grid'](grid[0]);
              scope.salvattore_registered.resolve();
            }catch(e){
              $timeout(rebuildSalvattore, 150);
              return;
            }
            grid.css({opacity: 1});
            $timeout(function() {
              scope.create_scrollable_collages($('.blog_product_collage'))
              // $(".dotdot").dotdotdot();
              try{
                twttr.widgets.load();
              }catch(e){};
            $("#pinit").remove();
            var e = document.createElement('script');
            e.setAttribute('type', 'text/javascript');
            e.setAttribute('charset', 'UTF-8');
            e.setAttribute('id', 'pinit');
            e.setAttribute('src', '//assets.pinterest.com/js/pinit_main.js?r='+Math.random()*99999);
            e.setAttribute('data-pin-hover', 'true');
            document.body.appendChild(e);
            scope.$broadcast("pinterest_reloaded");
            scope.$broadcast('windowResize');
            }, 500);
          };
          $timeout(add_items_rebuild, 150);
        };
        scope.updateSalvattore = function (new_feeds) {
          $("#pinit").remove();
          var e = document.createElement('script');
          e.setAttribute('type', 'text/javascript');
          e.setAttribute('charset', 'UTF-8');
          e.setAttribute('id', 'pinit');
          e.setAttribute('src', '//assets.pinterest.com/js/pinit_main.js?r='+Math.random()*99999);
          e.setAttribute('data-pin-hover', 'true');
          document.body.appendChild(e);
          return;
          var grid = iElement.find('.salvattore_grid');
          var items = [];
          var options = [];
          if(iAttrs.skipSocial !== undefined){
            options.push("skip-social");
          }
          if(iAttrs.bookmarks !== undefined){
            options.push("bookmarks");
          }
          angular.forEach(new_feeds, function (item) {
            var element = '<div feed-item feed-item-' + (item.platform) + ' item="feeds[' + item.index + ']" filter="filter" ' + options.join(" ") + '></div>';
            items.push($(element)[0]);
            scope.feeds.push(item);
          });
          scope.salvattore_registered.promise.then(function add_items_update(){
            try{
              salvattore['append_elements'](grid[0], items);
            }catch(e){
              $timeout(rebuildSalvattore, 150);
            }
            if(scope.grid_scope){
              scope.grid_scope.$destroy();
            }
            scope.grid_scope = scope.$new();
            $compile(grid.contents())(scope.grid_scope);
            $timeout(function() {
              scope.create_scrollable_collages($('.blog_product_collage'))
              // $(".dotdot").dotdotdot();
              try{
                twttr.widgets.load();
              }catch(e){};
              $("#pinit").remove();
              var e = document.createElement('script');
              e.setAttribute('type', 'text/javascript');
              e.setAttribute('charset', 'UTF-8');
              e.setAttribute('id', 'pinit');
              e.setAttribute('src', '//assets.pinterest.com/js/pinit_main.js?r='+Math.random()*99999);
              e.setAttribute('data-pin-hover', 'true');
              document.body.appendChild(e);
              scope.$broadcast("pinterest_reloaded");
              scope.$broadcast('windowResize');
            }, 500);
          });
        };
        scope.refreshSalvattore = function(){
          return;
          var grid = iElement.find('.salvattore_grid');
          var tmp = grid.find("[feed-item]:visible").clone().toArray();
          grid.find("[feed-item]:visible").remove();
          salvattore.append_elements(grid[0], tmp);
          if(scope.grid_scope === null){
            scope.grid_scope = scope.$new();
          }
          $compile(grid.contents())(scope.grid_scope);
        };

        // scope.$on("refreshFeedSalvattore", function(){
        //   if(scope.salvattore_refresh_timeout){
        //     $timeout.cancel(scope.salvattore_refresh_timeout);
        //   }
        //   scope.salvattore_refresh_timeout = $timeout(scope.refreshSalvattore, 500);
        // });

      }
    };
  }
])


.directive('feedItem', ['_', '$sce', '$rootScope', '$window', '$timeout', 'context', 'tsConfig',
    'tsInvitationMessage', 'NotifyingService',
    function(_, $sce, $rootScope, $window, $timeout, context, tsConfig, tsInvitationMessage, NotifyingService) {
  return {
    restrict: 'A',
    scope: {
      item: '=',
      options: '=',
    },
    replace: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/item.html'),
    // template: '<div></div>',
    controller: function() {
      var vm = this;

      vm.hover = function(value) {
        vm.hovered = value;
      };

      vm.isLongList = function() {
        return Object.keys(vm.item.user.collections_in).length > 3;
      };

      vm.postRedirect = function() {
        if (vm.options.noheader || vm.options.ugcView) {
          if (context.showDummyData) {
            $rootScope.$broadcast('featureLocked');
            return false;
          } else {
            $window.open(vm.item.url, '_blank');
          }
        } else {
          return true;
        }
      };

      vm.checkImages = function(imgs, element, scope) {
        var img = imgs.shift();
        var tmpImg = new Image();
        if (img === undefined) {
          // element.hide();
          // element.parent().remove();
          // vm.item.post_img = null;
          scope.itemImage = undefined;
          return;
        }

        tmpImg.onerror = function() {
          vm.checkImages(imgs, element, scope);
          tmpImg = null;
          // $timeout(function() {
          //   tmpImg.src = '';
          //   tmpImg = null;
          // }, 2000);
        };

        tmpImg.onload = function() {
          if (tmpImg.width < 230 || tmpImg.height < 200 || tmpImg.width > tmpImg.height * 3) {
            vm.checkImages(imgs, element, scope);
          } else {
            $rootScope.$apply(function() {
              // vm.item.post_img = img;
              scope.itemImage = img;
            });
          }
          tmpImg = null;
          // $timeout(function() {
          //   tmpImg.src = '';
          //   tmpImg = null;
          // }, 2000);
        };

        tmpImg.src = img;
      };

      vm.processImages = function(imgEl, scope) {
        if (vm.item.post_img) {
          scope.itemImage = vm.item.post_img || undefined;
          return;
        }
        if (vm.item.post_pic) {
          // vm.item.post_img = vm.item.post_pic;
          scope.itemImage = vm.item.post_pic || undefined;
        } else if (!vm.item.post_image){
          var imgs = vm.item.content_images;
          if (imgs && imgs.length) {
            vm.checkImages(imgs, imgEl, scope);
          } else {
            // imgEl.hide();
            // imgEl.parent().hide();
            // vm.item.post_img = null;
            scope.itemImage = undefined;
          }
        } else {
          // vm.item.post_img = vm.item.post_image;
          scope.itemImage = vm.item.post_image || undefined;
        }
      };

      vm.cleanedContent = function() {
        var content = vm.item.content;

        if (vm.item.platform === 'photos') {
          content = content.replace(/(\bhttps?:[\&\.\w\=\?\/]+\b)/igm, '<a target="_blank" href="$1"><span class="link">$1</span></a> ');
          content = content.replace(/#(\w+)/g, '<a target="_blank" href="http://instagram.com/$1"><span class="hashtag">#$1</span></a> ');
          content = content.replace(/@(\w+)/g, '<a target="_blank" href="http://instagram.com/$1"><span class="at_sign">@$1</span></a> ');
        } else if (vm.item.platform === 'tweets') {
          if (context.showDummyData) {
            content = content.replace(/(\bhttps?:[\&\.\w\=\?\/]+\b)/igm, '<a ng-click="$event.stopPropagation()" click-emitter="featureLocked"><span class="link">http://google.com</span></a> ');
          } else {
            content = content.replace(/(\bhttps?:[\&\.\w\=\?\/]+\b)/igm, '<a ng-click="$event.stopPropagation()" target="_blank" href="$1"><span class="link">$1</span></a> ');
          }
          content = content.replace(/#(\w+)/g, '<a target="_blank" href="https://twitter.com/hashtag/$1"><span class="hashtag">#$1</span></a> ');
          content = content.replace(/@(\w+)/g, '<a target="_blank" href="https://twitter.com/$1"><span class="at_sign">@$1</span></a> ');
        }

        return content;
        // return $sce.trustAsHtml(content);
      };

      vm.hasUser = function() {
        return vm.item && vm.item.user;
      };

      vm.canBookmarkInfluencer = function() {
        return true;
        return vm.hasUser() && vm.item.user.can_favorite && vm.options.bookmarks;
      };

      vm.bookmarkingLocked = function() {
        return vm.hasUser() && !vm.item.user.can_favorite && vm.options.bookmarks;
      };

      vm.canMessage = function() {
        return vm.hasUser() && vm.item.user.can_favorite && context.nonCampaignMessagingEnabled;
      };

      vm.openBookmarkPopup = function(options) {
        $rootScope.$broadcast('doOpenFavoritePopup', options);
      };

      vm.sendMessage = function(options) {
        if (options === undefined)
          return;
        angular.extend(options, {
          groupId: null,
          template: vm.messageData.body,
          subject: vm.messageData.subject,
          user: vm.item.user,
          // item: vm.item,
        });
        if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
          return;
        } else if (options.event) {
          options.event.preventDefault();
        }
        NotifyingService.notify('openInvitationPopup', options, true);
      };
    },
    controllerAs: 'feedItemCtrl',
    // require: ['^^pos'feedItem'],
    link: function(scope, iElement, iAttrs, ctrl) {
      // var feedCtrl = ctrls[0], ctrl = ctrls[1];

      scope.bookmarks = true;

      ctrl.item = scope.item;
      ctrl.options = scope.options;

      // ctrl.item.safe_url = $sce.trustAsResourceUrl(ctrl.item.url);
      // ctrl.item.title_safe = $sce.trustAsHtml(ctrl.item.title);
      // ctrl.item.content_safe = ctrl.cleanedContent();
      ctrl.item.safe_url = ctrl.item.url;
      ctrl.item.title_safe = ctrl.item.title;
      ctrl.item.content_safe = ctrl.cleanedContent();

      ctrl.messageData = tsInvitationMessage.get({
        user: ctrl.item.user,
        context: context
      });

      ctrl.hasCollectionsIn = !_.isEmpty(ctrl.item.user.collections_in);

      scope.$on('user-collections-in-changed', function(their_scope, data) {
        if (ctrl.item.user.id == data.id) {
          // ctrl.hasCollectionsIn = data.has_collections_in;
          // ctrl.item.user = angular.extend(ctrl.item.user, {
          //   collections_in: data.collections_in
          // });

          ctrl.item.user.collections_in = ctrl.item.user.collections_in || {};
          if (data.partial) {
            angular.extend(ctrl.item.user.collections_in, data.collections_in);
          } else {
            ctrl.item.user.collections_in = angular.copy(data.collections_in);
          }
          ctrl.hasCollectionsIn = !_.isEmpty(ctrl.item.user.collections_in);
        }
      });

      scope.context = context;
      ctrl.context = context;

      scope.itemImage = undefined;
      var imgEl;
      if (ctrl.item.platform == 'photos') {
        imgEl = iElement.find('.instagram_img');
      } else if (ctrl.item.platform == 'pins') {
        imgEl = iElement.find('.pinterest_img');
      } else if (ctrl.item.platform == 'products') {
        imgEl = iElement.find('.img.product_img');
      } else {
        imgEl = iElement.find('.post_pic');
      }
      ctrl.processImages(imgEl, scope);

      // ctrl.item.post_img = ctrl.item.user ? ctrl.item.user.pic : null;
      // ctrl.item.post_image = ctrl.item.user ? ctrl.item.user.pic : null;

      // scope.itemImage = ctrl.item.user ? ctrl.item.user.pic : null;

      imgEl = null;

      if (ctrl.item.platform == 'pins') {
        ctrl.item.pinit = $sce.trustAsUrl(encodeURIComponent("?url=" + ctrl.item.url + "&media=" + ctrl.item.post_pic + "&description=Repinned for theshelf.com"));

        ctrl.repin = function() {
          window.open( "http://www.pinterest.com/pin/" + ctrl.item.pin_id + "/repin/x/", "_blank", "resizable=yes, width=722, height=286");
        };

        ctrl.follow = function() {
          iElement.find(".PIN_" + ctrl.pin_ident + "_follow_me_button").click();
        };

        ctrl.harvestInfo = function() {
          var pinEl = iElement.find(".pinit span")[0];
          if (pinEl === undefined) {
            $timeout(ctrl.harvestInfo, 250);
            return;
          }
          ctrl.pin_ident = pinEl.className.split(" ")[0].split("_")[1];
          ctrl.board = iElement.find(".PIN_" + ctrl.pin_ident + "_embed_pin_text_container_board").text();
        };

        scope.$on('pinterest_reloaded', function() {
          ctrl.harvestInfo();
        });
      }

      scope.itemCtrl = ctrl;
    },
  };
}])


// .directive('feedItemPhotos', ['$sce', '$rootScope', '$timeout', 'context', 'tsInvitationMessage', 'tsConfig',
//     'NotifyingService',
//   function ($sce, $rootScope, $timeout, context, tsInvitationMessage, tsConfig, NotifyingService) {
//     return {
//       restrict: 'A',
//       // scope: {
//       //   'item': '=',
//       // },
//       require: 'feedItem',
//       templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/instagram.html'),
//       link: function (scope, iElement, iAttrs, ctrl) {
//         scope.debug = iAttrs.debug !== undefined;
//         scope.header = iAttrs.noheader === undefined;
//         scope.ugcView = iAttrs.ugcView !== undefined;

//         scope.showButtons = (scope.header || iAttrs.showButtons !== undefined) && context.visitorHasBrand && !scope.ugcView;
//         scope.showSocials = scope.header && !scope.ugcView;
//         scope.showSocialLabel = !scope.header || scope.ugcView;
        
//         scope.extra_class = {brand_relevant_highlight: scope.item.highlight};
//         scope.context = context;

//         scope.user = scope.item.user;
//         scope.user.name = scope.user.user_name;

//         scope.postRedirect = function() {
//           if (!scope.header || scope.ugcView) {
//             if (scope.context.showDummyData) {
//               $rootScope.$broadcast('featureLocked');
//               return false;
//             } else {
//               window.open(scope.item.url, "_blank");
//             }
//           } else {
//             return true;
//           }
//         };

//         var messageData = tsInvitationMessage.get(scope);

//         scope.message = function(options){
//           if (options === undefined)
//             return;
//           angular.extend(options, {
//             groupId: null,
//             template: messageData.body,
//             subject: messageData.subject,
//             user: scope.user, 
//             item: scope.item,
//           });
//           if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
//             return;
//           } else if (options.event) {
//             options.event.preventDefault();
//           }
//           $rootScope.$broadcast("openInvitationPopup", options);
//         };

//         scope.has_collections_in = !_.isEmpty(scope.item.user.collections_in);

//         scope.$on('user-collections-in-changed', function(their_scope, data) {
//           // scope.updating_collections_in = false;
//           if (scope.item.user.id == data.id) {
//             scope.has_collections_in = data.has_collections_in;
//             scope.item.user = angular.extend(scope.item.user, {
//               collections_in: data.collections_in
//             });
//           }
//         });

//         scope.item.safe_url = $sce.trustAsResourceUrl(scope.item.url);
//         scope.openFavoritePopup = function(options){
//           // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
//           // scope isolation bloggerMoreInfoPopup -> favoritedTable
//           var cscope = scope;
//           while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
//             cscope = cscope.$parent;
//           }
//           if(cscope){
//             cscope.doOpenFavoritePopup(options);
//           }else{
//             console.error("Open favorite popup under controller without doOpenFavoritePopup function");
//           }
//         };

//         var check_image = function(imgs){
//           var img = imgs.shift();
//           var tmp_img = new Image();
//           if(img === undefined){
//             iElement.find(".post_pic").hide();
//             return;
//           }
//           tmp_img.onerror = function(a,b,c,d){
//             check_image(imgs);
//           };
//           tmp_img.onload = function(){
//             if(tmp_img.width < 230 || tmp_img.height < 200 || tmp_img.width > tmp_img.height*3){
//               check_image(imgs);
//             }else{
//               scope.$apply(function(){
//                 scope.item.post_img = img;
//               });
//             }
//           };
//           tmp_img.src = img;
//         };

//         if(scope.item.post_image === null){
//           var imgs = scope.item.content_images;
//           if(imgs.length > 0) {
//             check_image(imgs);
//           }else{
//             iElement.find(".instagram_img").hide();
//           }
//         }else{
//           scope.item.post_img = scope.item.post_image;
//         }

//         var content = scope.item.content;
//         content = content.replace(/(\bhttps?:[\&\.\w\=\?\/]+\b)/igm, '<a target="_blank" href="$1"><span class="link">$1</span></a> ');
//         content = content.replace(/#(\w+)/g, '<a target="_blank" href="http://instagram.com/$1"><span class="hashtag">#$1</span></a> ');
//         content = content.replace(/@(\w+)/g, '<a target="_blank" href="http://instagram.com/$1"><span class="at_sign">@$1</span></a> ');
//         scope.item.content_safe = $sce.trustAsHtml(content);
//         scope.bookmarks = iAttrs.bookmarks !== undefined;
//         $timeout(function(){
//           iElement.find('.bs_tooltip').tooltip();
//           iElement.find('.sm_product_images img').error(function(){
//             $(this).parent().remove();
//           });
//         }, 10);
//       }
//     };
//   }
// ])


.directive('feedItemProducts', ['$sce', '$compile', '$timeout', '$rootScope', '$http', 'context',
    'tsInvitationMessage', 'tsConfig', 'NotifyingService',
  function ($sce, $compile, $timeout, $rootScope, $http, context, tsInvitationMessage, tsConfig, NotifyingService) {
    return {
      restrict: 'A',
      scope: {
        'item': '=',
      },
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/product.html'),
      link: function (scope, iElement, iAttrs) {
        scope.bookmarks = iAttrs.bookmarks !== undefined;
        scope.debug = iAttrs.debug !== undefined;
        scope.header = iAttrs.noheader === undefined;
        scope.showButtons = scope.header || iAttrs.showButtons !== undefined;
        scope.context = context;

        scope.user = scope.item.user;
        scope.user.name = scope.user.user_name;

        scope.postRedirect = function() {
          if (!scope.header || scope.ugcView) {
            if (scope.context.showDummyData) {
              $rootScope.$broadcast('featureLocked');
              return false;
            } else {
              window.open(scope.item.url, "_blank");
            }
          } else {
            return true;
          }
        };

        var messageData = tsInvitationMessage.get(scope);

        scope.message = function(options){
          if (options === undefined)
            return;
          angular.extend(options, {
            groupId: null,
            template: messageData.body,
            subject: messageData.subject,
            user: scope.user, 
            item: scope.item,
          });
          if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
            return;
          } else if (options.event) {
            options.event.preventDefault();
          }
          $rootScope.$broadcast("openInvitationPopup", options);
        };

        scope.has_collections_in = !_.isEmpty(scope.item.user.collections_in);

        scope.$on('user-collections-in-changed', function(their_scope, data) {
          // scope.updating_collections_in = false;
          if (scope.item.user.id == data.id) {
            scope.has_collections_in = data.has_collections_in;
            scope.item.user = angular.extend(scope.item.user, {
              collections_in: data.collections_in
            });
          }
        });

        $timeout(function(){
          iElement.find('img.product_img').load(function(){
            if($(this)[0].naturalWidth < 230 || $(this)[0].naturalHeight < 200){
              iElement.remove();
              NotifyingService.notify('refreshSalvattore');
            }
          });
        }, 10);
        scope.openFavoritePopup = function(options){
          // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
          // scope isolation bloggerMoreInfoPopup -> favoritedTable
          var cscope = scope;
          while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
            cscope = cscope.$parent;
          }
          if(cscope){
            cscope.doOpenFavoritePopup(options);
          }else{
            console.error("Open favorite popup under controller without doOpenFavoritePopup function");
          }
        };
        //scope.add_to_shelves_lb = LightBox.get_by_type("add_to_shelves");
        //scope.item_details_panel = new ItemInfo($('#item_details'));
        scope.add_to_shelves = function(){
          // var deferred = scope.add_to_shelves_lb.get_item_shelves(scope.item.shelf_add_url);
          // scope.add_to_shelves_lb.open();
          // $.when(deferred).then(function(data) {
          //   scope.add_to_shelves_lb.set_shelves_html.apply(scope.add_to_shelves_lb, [data]);
          //   $compile($('.add-to-shelves-popup'))($rootScope.$new());
          // });
        };
        scope.details = function(){
                //scope.item_details_panel.add_img_from_feed(scope.item.img_url_panel_view);
                // scope.item_details_panel.like_function = (function($quickshelf_btn) {
                //     return function() {
                //         //scope.quickshelf($quickshelf_btn);
                //     }
                // })($(this).find(scope.selectors.quickshelf_sel));
                //scope.item_details_panel._unbind_events();
                //scope.item_details_panel._show_loaders();
                //scope.item_details_panel.show_panel(iElement.find(".feed_product"));
        };
        scope.delete = function(){
          $http.get(scope.item.remove_from_user_feed).success(function(){
            iElement.remove();
          });
        };
        scope.hide = function(){
          $http.get(scope.item.hide_from_user_feed).success(function(){
            iElement.remove();
          });
        };
      }
    };
  }
])


// .directive('feedItemYoutube', ['$sce', '$q', 'tagStripper', '$timeout', '$rootScope', 'context',
//     'tsInvitationMessage', 'tsConfig', 'NotifyingService',
//   function ($sce, $q, tagStripper, $timeout, $rootScope, context, tsInvitationMessage, tsConfig,
//       NotifyingService) {
//     return {
//       restrict: 'A',
//       // scope: {
//       //   'item': '=',
//       // },
//       templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/youtube.html'),
//       link: function(scope, iElement, iAttrs) {
//         scope.bookmarks = iAttrs.bookmarks !== undefined;
//         scope.debug = iAttrs.debug !== undefined;
//         scope.header = iAttrs.noheader === undefined;
//         scope.ugcView = iAttrs.ugcView !== undefined;
//         scope.showButtons = (scope.header || iAttrs.showButtons !== undefined) && context.visitorHasBrand && !scope.ugcView;
//         scope.showSocials = scope.header && !scope.ugcView;
//         scope.showSocialLabel = !scope.header || scope.ugcView;
//         scope.facebook = scope.item.platform !== undefined && scope.item.platform === "Facebook";
//         scope.extra_class = {brand_relevant_highlight: scope.item.highlight};
//         scope.context = context;

//         scope.user = scope.item.user;
//         scope.user.name = scope.user.user_name;

//         scope.postRedirect = function() {
//           if (!scope.header || scope.ugcView) {
//             if (scope.context.showDummyData) {
//               $rootScope.$broadcast('featureLocked');
//               return false;
//             } else {
//               window.open(scope.item.url, "_blank");
//             }
//           } else {
//             return true;
//           }
//         };

//         var messageData = tsInvitationMessage.get(scope);

//         scope.message = function(options){
//           if (options === undefined)
//             return;
//           angular.extend(options, {
//             groupId: null,
//             template: messageData.body,
//             subject: messageData.subject,
//             user: scope.user, 
//             item: scope.item,
//           });
//           if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
//             return;
//           } else if (options.event) {
//             options.event.preventDefault();
//           }
//           $rootScope.$broadcast("openInvitationPopup", options);
//         };

//         var check_image = function(imgs){
//           var img = imgs.shift();
//           var tmp_img = new Image();
//           if(img === undefined){
//             iElement.find(".post_pic").hide();
//             return;
//           }
//           tmp_img.onerror = function(a,b,c,d){
//             check_image(imgs);
//           };
//           tmp_img.onload = function(){
//             if(tmp_img.width < 230 || tmp_img.height < 200 || tmp_img.width > tmp_img.height*3){
//               check_image(imgs);
//             }else{
//               scope.$apply(function(){
//                 scope.item.post_img = img;
//               });
//             }
//           };
//           tmp_img.src = img;
//         };

//         var subs = scope.item.content;
//         if(scope.item.post_img === undefined){
//           if(scope.item.post_image === null){
//             var imgs = scope.item.content_images;
//             if(imgs.length > 0) {
//               check_image(imgs);
//             }else{
//               iElement.find(".post_pic").hide();
//             }
//           }else{
//             scope.item.post_img = scope.item.post_image;
//             if(scope.item.post_image_dims !== undefined){
//               var img = iElement.find('.post_pic img');
//             }
//           }
//         }

//         scope.has_collections_in = !_.isEmpty(scope.item.user.collections_in);

//         scope.$on('user-collections-in-changed', function(their_scope, data) {
//           // scope.updating_collections_in = false;
//           if (scope.item.user.id == data.id) {
//             scope.has_collections_in = data.has_collections_in;
//             scope.item.user = angular.extend(scope.item.user, {
//               collections_in: data.collections_in
//             });
//           }
//         });

//         scope.item.content_safe = $sce.trustAsHtml(subs);
//         scope.item.title_safe = $sce.trustAsHtml(scope.item.title);
//         scope.details = function(product){
//           scope.item_details_panel = new ItemInfo($('#item_details'));
//           scope.item_details_panel.add_img_from_feed(product.pic);
//           scope.item_details_panel._unbind_events();
//           scope.item_details_panel._show_loaders();
//           scope.item_details_panel.show_panel(iElement.find(".product_"+scope.item.id+"_"+product.id));

//         };

//         scope.openFavoritePopup = function(options){
//           // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
//           // scope isolation bloggerMoreInfoPopup -> favoritedTable
//           var cscope = scope;
//           while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
//             cscope = cscope.$parent;
//           }
//           if(cscope){
//             cscope.doOpenFavoritePopup(options);
//           }else{
//             console.error("Open favorite popup under controller without doOpenFavoritePopup function");
//           }
//         };
//         $timeout(function(){
//           iElement.find('.bs_tooltip').tooltip();
//           iElement.find('.sm_post_images img').error(function(){
//             $(this).parent().remove();
//           });
//         }, 10);
//       }
//     };
//   }
// ])


// .directive('feedItemFacebook', ['$sce', '$q', 'tagStripper', '$timeout', '$rootScope', 'context',
//     'tsInvitationMessage', 'tsConfig', 'NotifyingService',
//   function ($sce, $q, tagStripper, $timeout, $rootScope, context, tsInvitationMessage, tsConfig, NotifyingService) {
//     return {
//       restrict: 'A',
//       // scope: {
//       //   'item': '=',
//       // },
//       templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/blog.html'),
//       link: function (scope, iElement, iAttrs) {
//         scope.bookmarks = iAttrs.bookmarks !== undefined;
//         scope.debug = iAttrs.debug !== undefined;
//         scope.header = iAttrs.noheader === undefined;
//         scope.ugcView = iAttrs.ugcView !== undefined;
//         scope.showButtons = (scope.header || iAttrs.showButtons !== undefined) && context.visitorHasBrand && !scope.ugcView;
//         scope.showSocials = scope.header && !scope.ugcView;
//         scope.showSocialLabel = !scope.header || scope.ugcView;
//         scope.facebook = scope.item.platform === "Facebook" || scope.item.platform === 'facebook';
//         scope.extra_class = {brand_relevant_highlight: scope.item.highlight};
//         scope.context = context;

//         scope.user = scope.item.user;
//         scope.user.name = scope.user.user_name;

//         var messageData = tsInvitationMessage.get(scope);

//         scope.postRedirect = function() {
//           if (!scope.header || scope.ugcView) {
//             if (scope.context.showDummyData) {
//               $rootScope.$broadcast('featureLocked');
//               return false;
//             } else {
//               window.open(scope.item.url, "_blank");
//             }
//           } else {
//             return true;
//           }
//         };

//         scope.message = function(options){
//           if (options === undefined)
//             return;
//           angular.extend(options, {
//             groupId: null,
//             template: messageData.body,
//             subject: messageData.subject,
//             user: scope.user, 
//             item: scope.item,
//           });
//           if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
//             return;
//           } else if (options.event) {
//             options.event.preventDefault();
//           }
//           $rootScope.$broadcast("openInvitationPopup", options);
//         };

//         var check_image = function(imgs){
//           var img = imgs.shift();
//           var tmp_img = new Image();
//           if(img === undefined){
//             iElement.find(".post_pic").hide();
//             return;
//           }
//           tmp_img.onerror = function(a,b,c,d){
//             check_image(imgs);
//           };
//           tmp_img.onload = function(){
//             if(tmp_img.width < 230 || tmp_img.height < 200 || tmp_img.width > tmp_img.height*3){
//               check_image(imgs);
//             }else{
//               scope.$apply(function(){
//                 scope.item.post_img = img;
//               });
//             }
//           };
//           tmp_img.src = img;
//         };

//         var subs = scope.item.content;
//         if(scope.item.post_img === undefined){
//           if(scope.item.post_image === null){
//             var imgs = scope.item.content_images;
//             if(imgs.length > 0) {
//               check_image(imgs);
//             }else{
//               iElement.find(".post_pic").hide();
//             }
//           }else{
//             scope.item.post_img = scope.item.post_image;
//             if(scope.item.post_image_dims !== undefined){
//               var img = iElement.find('.post_pic img');
//             }
//           }
//         }

//         scope.has_collections_in = !_.isEmpty(scope.item.user.collections_in);

//         scope.$on('user-collections-in-changed', function(their_scope, data) {
//           // scope.updating_collections_in = false;
//           if (scope.item.user.id == data.id) {
//             scope.has_collections_in = data.has_collections_in;
//             scope.item.user = angular.extend(scope.item.user, {
//               collections_in: data.collections_in
//             });
//           }
//         });

//         scope.item.content_safe = $sce.trustAsHtml(subs);
//         scope.item.title_safe = $sce.trustAsHtml(scope.item.title);
//         scope.details = function(product){
//           scope.item_details_panel = new ItemInfo($('#item_details'));
//           scope.item_details_panel.add_img_from_feed(product.pic);
//           scope.item_details_panel._unbind_events();
//           scope.item_details_panel._show_loaders();
//           scope.item_details_panel.show_panel(iElement.find(".product_"+scope.item.id+"_"+product.id));

//         };

//         scope.openFavoritePopup = function(options){
//           // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
//           // scope isolation bloggerMoreInfoPopup -> favoritedTable
//           var cscope = scope;
//           while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
//             cscope = cscope.$parent;
//           }
//           if(cscope){
//             cscope.doOpenFavoritePopup(options);
//           }else{
//             console.error("Open favorite popup under controller without doOpenFavoritePopup function");
//           }
//         };
//         $timeout(function(){
//           iElement.find('.bs_tooltip').tooltip();
//           iElement.find('.sm_post_images img').error(function(){
//             $(this).parent().remove();
//           });
//         }, 10);
//       }
//     };
//   }
// ])


// .directive('feedItemBlog', ['$sce', '$q', 'tagStripper', '$timeout', '$rootScope', 'context',
//     'tsInvitationMessage', 'tsConfig', 'NotifyingService',
//   function ($sce, $q, tagStripper, $timeout, $rootScope, context, tsInvitationMessage, tsConfig, NotifyingService) {
//     return {
//       restrict: 'A',
//       // scope: {
//       //   'item': '=',
//       // },
//       templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/blog.html'),
//       link: function (scope, iElement, iAttrs) {
//         scope.bookmarks = iAttrs.bookmarks !== undefined;
//         scope.debug = iAttrs.debug !== undefined;
//         scope.header = iAttrs.noheader === undefined;
//         scope.ugcView = iAttrs.ugcView !== undefined;
//         scope.showButtons = (scope.header || iAttrs.showButtons !== undefined) && context.visitorHasBrand && !scope.ugcView;
//         scope.showSocials = scope.header && !scope.ugcView;
//         scope.showSocialLabel = !scope.header || scope.ugcView;
//         scope.facebook = scope.item.platform === "Facebook" || scope.item.platform === 'facebook';
//         scope.extra_class = {brand_relevant_highlight: scope.item.highlight};
//         scope.context = context;

//         scope.user = scope.item.user;
//         scope.user.name = scope.user.user_name;

//         var messageData = tsInvitationMessage.get(scope);

//         scope.postRedirect = function() {
//           if (!scope.header || scope.ugcView) {
//             if (scope.context.showDummyData) {
//               $rootScope.$broadcast('featureLocked');
//               return false;
//             } else {
//               window.open(scope.item.url, "_blank");
//             }
//           } else {
//             return true;
//           }
//         };

//         scope.message = function(options){
//           if (options === undefined)
//             return;
//           angular.extend(options, {
//             groupId: null,
//             template: messageData.body,
//             subject: messageData.subject,
//             user: scope.user, 
//             item: scope.item,
//           });
//           if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
//             return;
//           } else if (options.event) {
//             options.event.preventDefault();
//           }
//           $rootScope.$broadcast("openInvitationPopup", options);
//         };

//         var check_image = function(imgs){
//           var img = imgs.shift();
//           var tmp_img = new Image();
//           if(img === undefined){
//             iElement.find(".post_pic").hide();
//             return;
//           }
//           tmp_img.onerror = function(a,b,c,d){
//             check_image(imgs);
//           };
//           tmp_img.onload = function(){
//             if(tmp_img.width < 230 || tmp_img.height < 200 || tmp_img.width > tmp_img.height*3){
//               check_image(imgs);
//             }else{
//               scope.$apply(function(){
//                 scope.item.post_img = img;
//               });
//             }
//           };
//           tmp_img.src = img;
//         };

//         var subs = scope.item.content;
//         if(scope.item.post_img === undefined){
//           if(scope.item.post_image === null){
//             var imgs = scope.item.content_images;
//             if(imgs.length > 0) {
//               check_image(imgs);
//             }else{
//               iElement.find(".post_pic").hide();
//             }
//           }else{
//             scope.item.post_img = scope.item.post_image;
//             if(scope.item.post_image_dims !== undefined){
//               var img = iElement.find('.post_pic img');
//             }
//           }
//         }

//         scope.has_collections_in = !_.isEmpty(scope.item.user.collections_in);

//         scope.$on('user-collections-in-changed', function(their_scope, data) {
//           // scope.updating_collections_in = false;
//           if (scope.item.user.id == data.id) {
//             scope.has_collections_in = data.has_collections_in;
//             scope.item.user = angular.extend(scope.item.user, {
//               collections_in: data.collections_in
//             });
//           }
//         });

//         scope.item.content_safe = $sce.trustAsHtml(subs);
//         scope.item.title_safe = $sce.trustAsHtml(scope.item.title);
//         scope.details = function(product){
//           scope.item_details_panel = new ItemInfo($('#item_details'));
//           scope.item_details_panel.add_img_from_feed(product.pic);
//           scope.item_details_panel._unbind_events();
//           scope.item_details_panel._show_loaders();
//           scope.item_details_panel.show_panel(iElement.find(".product_"+scope.item.id+"_"+product.id));

//         };

//         scope.openFavoritePopup = function(options){
//           // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
//           // scope isolation bloggerMoreInfoPopup -> favoritedTable
//           var cscope = scope;
//           while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
//             cscope = cscope.$parent;
//           }
//           if(cscope){
//             cscope.doOpenFavoritePopup(options);
//           }else{
//             console.error("Open favorite popup under controller without doOpenFavoritePopup function");
//           }
//         };
//         $timeout(function(){
//           iElement.find('.bs_tooltip').tooltip();
//           iElement.find('.sm_post_images img').error(function(){
//             $(this).parent().remove();
//           });
//         }, 10);
//       }
//     };
//   }
// ])


// @todo: not used?
// .directive('feedItemCollab', ['$sce', '$q', '$rootScope', 'tsConfig', 'NotifyingService',
//   function ($sce, $q, $rootScope, tsConfig, NotifyingService) {
//     return {
//       restrict: 'A',
//       // scope: {
//       //   'item': '=',
//       // },
//       templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/collab.html'),
//       link: function (scope, iElement, iAttrs) {
//         scope.bookmarks = iAttrs.bookmarks !== undefined;
//         scope.debug = iAttrs.debug !== undefined;
//         scope.header = iAttrs.noheader === undefined;
//         scope.showButtons = scope.header || iAttrs.showButtons !== undefined;

//         scope.postRedirect = function() {
//           if (!scope.header || scope.ugcView) {
//             if (scope.context.showDummyData) {
//               $rootScope.$broadcast('featureLocked');
//               return false;
//             } else {
//               window.open(scope.item.url, "_blank");
//             }
//           } else {
//             return true;
//           }
//         };

//         scope.message = function(id){
//           $rootScope.$broadcast("openMessageInfluencerPopup", id);
//         };
//         var check_image = function(imgs){
//           var img = imgs.shift();
//           var tmp_img = new Image();
//           if(img === undefined){
//             iElement.find(".post_pic").hide();
//             return;
//           }
//           tmp_img.onerror = function(a,b,c,d){
//             check_image(imgs);
//           };
//           tmp_img.onload = function(){
//             if(tmp_img.width < 230 || tmp_img.height < 200 || tmp_img.width > tmp_img.height*3){
//               check_image(imgs);
//             }else{
//               scope.$apply(function(){
//                 scope.item.post_img = img;
//               });
//             }
//           };
//           tmp_img.src = img;
//         }

//         var subs = scope.item.content;
//         if(scope.item.post_img === undefined){
//           if(scope.item.post_image === null){
//             var imgs = scope.item.content_images;
//             if(imgs.length > 0) {
//               check_image(imgs);
//             }else{
//               iElement.find(".post_pic").hide();
//             }
//           }else{
//             scope.item.post_img = scope.item.post_image;
//           }
//         }

//         scope.item.content_safe = $sce.trustAsHtml(subs);

//         scope.openFavoritePopup = function(options){
//           // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
//           // scope isolation bloggerMoreInfoPopup -> favoritedTable
//           var cscope = scope;
//           while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
//             cscope = cscope.$parent;
//           }
//           if(cscope){
//             cscope.doOpenFavoritePopup(options);
//           }else{
//             console.error("Open favorite popup under controller without doOpenFavoritePopup function");
//           }
//         };
//       }
//     };
//   }
// ])


// .directive('feedItemTweets', ['$sce', '$http', '$rootScope', '$timeout', 'context', 'tsInvitationMessage',
//     'tsConfig', 'NotifyingService',
//   function ($sce, $http, $rootScope, $timeout, context, tsInvitationMessage, tsConfig, NotifyingService) {
//     return {
//       restrict: 'A',
//       // scope: {
//       //   'item': '=',
//       // },
//       templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/tweets.html'),
//       link: function (scope, iElement, iAttrs) {
//         scope.bookmarks = iAttrs.bookmarks !== undefined;
//         scope.debug = iAttrs.debug !== undefined;
//         scope.header = iAttrs.noheader === undefined;
//         scope.ugcView = iAttrs.ugcView !== undefined;
//         scope.showButtons = (scope.header || iAttrs.showButtons !== undefined) && context.visitorHasBrand && !scope.ugcView;
//         scope.showSocials = scope.header && !scope.ugcView;
//         scope.showSocialLabel = !scope.header || scope.ugcView;
//         scope.extra_class = {brand_relevant_highlight: scope.item.highlight};
//         scope.context = context;

//         scope.user = scope.item.user;
//         scope.user.name = scope.user.user_name;

//         scope.postRedirect = function() {
//           if (!scope.header || scope.ugcView) {
//             if (scope.context.showDummyData) {
//               $rootScope.$broadcast('featureLocked');
//               return false;
//             } else {
//               window.open(scope.item.url, "_blank");
//             }
//           } else {
//             return true;
//           }
//         };

//         var messageData = tsInvitationMessage.get(scope);

//         scope.message = function(options){
//           if (options === undefined)
//             return;
//           angular.extend(options, {
//             groupId: null,
//             template: messageData.body,
//             subject: messageData.subject,
//             user: scope.user, 
//             item: scope.item,
//           });
//           if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
//             return;
//           } else if (options.event) {
//             options.event.preventDefault();
//           }
//           $rootScope.$broadcast("openInvitationPopup", options);
//         };

//         scope.has_collections_in = !_.isEmpty(scope.item.user.collections_in);

//         scope.$on('user-collections-in-changed', function(their_scope, data) {
//           // scope.updating_collections_in = false;
//           if (scope.item.user.id == data.id) {
//             scope.has_collections_in = data.has_collections_in;
//             scope.item.user = angular.extend(scope.item.user, {
//               collections_in: data.collections_in
//             });
//           }
//         });


//         scope.item.safe_url = $sce.trustAsResourceUrl(scope.item.url);
//         scope.openFavoritePopup = function(options){
//           // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
//           // scope isolation bloggerMoreInfoPopup -> favoritedTable
//           var cscope = scope;
//           while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
//             cscope = cscope.$parent;
//           }
//           if(cscope){
//             cscope.doOpenFavoritePopup(options);
//           }else{
//             console.error("Open favorite popup under controller without doOpenFavoritePopup function");
//           }
//         };
//         var content = scope.item.content;
//         if (context.showDummyData) {
//           content = content.replace(/(\bhttps?:[\&\.\w\=\?\/]+\b)/igm, '<a ng-click="$event.stopPropagation()" click-emitter="featureLocked"><span class="link">http://google.com</span></a> ');
//         } else {
//           content = content.replace(/(\bhttps?:[\&\.\w\=\?\/]+\b)/igm, '<a ng-click="$event.stopPropagation()" target="_blank" href="$1"><span class="link">$1</span></a> ');
//         }
//         content = content.replace(/#(\w+)/g, '<a target="_blank" href="https://twitter.com/hashtag/$1"><span class="hashtag">#$1</span></a> ');
//         content = content.replace(/@(\w+)/g, '<a target="_blank" href="https://twitter.com/$1"><span class="at_sign">@$1</span></a> ');
//         scope.item.content_safe = $sce.trustAsHtml(content);
//         scope.skip_social = iAttrs.skipSocial !== undefined;

//         $timeout(function(){
//           iElement.find('.bs_tooltip').tooltip();
//           iElement.find('.sm_product_images img').error(function(){
//             $(this).parent().remove();
//           });
//         }, 10);
//       }
//     };
//   }
// ])


// .directive('feedItemPins', ['$sce', '$http', '$timeout', '$rootScope', 'context', 'tsInvitationMessage',
//     'tsConfig', 'NotifyingService',
//   function ($sce, $http, $timeout, $rootScope, context, tsInvitationMessage, tsConfig, NotifyingService) {
//     return {
//       restrict: 'A',
//       // scope: {
//       //   'item': '=',
//       // },
//       templateUrl: tsConfig.wrapTemplate('js/angular/templates/feeds/pin.html'),
//       link: function (scope, iElement, iAttrs) {
//         scope.bookmarks = iAttrs.bookmarks !== undefined;
//         scope.debug = iAttrs.debug !== undefined;
//         scope.header = iAttrs.noheader === undefined;
//         scope.ugcView = iAttrs.ugcView !== undefined;
//         scope.showButtons = (scope.header || iAttrs.showButtons !== undefined) && context.visitorHasBrand && !scope.ugcView;
//         scope.showSocials = scope.header && !scope.ugcView;
//         scope.showSocialLabel = !scope.header || scope.ugcView;
//         scope.extra_class = {brand_relevant_highlight: scope.item.highlight};
//         scope.context = context;

//         scope.user = scope.item.user;
//         scope.user.name = scope.user.user_name;

//         scope.postRedirect = function() {
//           if (!scope.header || scope.ugcView) {
//             if (scope.context.showDummyData) {
//               $rootScope.$broadcast('featureLocked');
//               return false;
//             } else {
//               window.open(scope.item.url, "_blank");
//             }
//           } else {
//             return true;
//           }
//         };

//         var messageData = tsInvitationMessage.get(scope);

//         scope.message = function(options){
//           if (options === undefined)
//             return;
//           angular.extend(options, {
//             groupId: null,
//             template: messageData.body,
//             subject: messageData.subject,
//             user: scope.user, 
//             item: scope.item,
//           });
//           if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
//             return;
//           } else if (options.event) {
//             options.event.preventDefault();
//           }
//           $rootScope.$broadcast("openInvitationPopup", options);
//         };

//         var check_image = function(imgs){
//           var img = imgs.shift();
//           var tmp_img = new Image();
//           if(img === undefined){
//             iElement.find(".pinterest_img").hide();
//             return;
//           }
//           tmp_img.onerror = function(a,b,c,d){
//             check_image(imgs);
//           };
//           tmp_img.onload = function(){
//             if(tmp_img.width < 230 || tmp_img.height < 200 || tmp_img.width > tmp_img.height*3){
//               check_image(imgs);
//             }else{
//               scope.$apply(function(){
//                 scope.item.post_img = img;
//               });
//             }
//           };
//           tmp_img.src = img;
//         };

//         var subs = scope.item.content;
//         if(scope.item.post_img === undefined){
//           if (scope.item.post_pic !== null && scope.item.post_pic !== undefined) {
//             scope.item.post_img = scope.item.post_pic;
//           } else if (scope.item.post_image === null){
//             var imgs = scope.item.content_images;
//             if(imgs.length > 0) {
//               check_image(imgs);
//             }else{
//               iElement.find(".pinterest_img").hide();
//             }
//           }else{
//             scope.item.post_img = scope.item.post_image;
//             if(scope.item.post_image_dims !== undefined){
//               var img = iElement.find('.pinterest_img img');
//             }
//           }
//         }

//         scope.item.safe_url = $sce.trustAsResourceUrl(scope.item.url);
//         scope.openFavoritePopup = function(options){
//           // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
//           // scope isolation bloggerMoreInfoPopup -> favoritedTable
//           var cscope = scope;
//           while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
//             cscope = cscope.$parent;
//           }
//           if(cscope){
//             cscope.doOpenFavoritePopup(options);
//           }else{
//             console.error("Open favorite popup under controller without doOpenFavoritePopup function");
//           }
//         };
//         var content = scope.item.content;
//         scope.item.content_safe = $sce.trustAsHtml(content);
//         scope.item.pinit = $sce.trustAsUrl(encodeURIComponent("?url="+scope.item.url+"&media="+scope.item.post_pic+"&description=Repinned for theshelf.com"));

//         scope.has_collections_in = !_.isEmpty(scope.item.user.collections_in);

//         scope.$on('user-collections-in-changed', function(their_scope, data) {
//           // scope.updating_collections_in = false;
//           if (scope.item.user.id == data.id) {
//             scope.has_collections_in = data.has_collections_in;
//             scope.item.user = angular.extend(scope.item.user, {
//               collections_in: data.collections_in
//             });
//           }
//         });

//         var harvest_info = function(){
//           var pin_element = iElement.find(".pinit span")[0];
//           if(pin_element === undefined){
//             $timeout(harvest_info, 250);
//             return;
//           }
//           scope.pin_ident = pin_element.className.split(" ")[0].split("_")[1];
//           scope.board = iElement.find(".PIN_"+scope.pin_ident+"_embed_pin_text_container_board").text();
//         }
//         scope.$on("pinterest_reloaded", harvest_info);
//         scope.repin = function(){
//           window.open( "http://www.pinterest.com/pin/"+scope.item.pin_id+"/repin/x/", "_blank", "resizable=yes, width=722, height=286");
//         };
//         scope.follow = function(){
//           iElement.find(".PIN_"+scope.pin_ident+"_follow_me_button").click();
//         };
//         scope.skip_social = iAttrs.skipSocial !== undefined;
//         $timeout(function(){
//           iElement.find('.bs_tooltip').tooltip();
//           iElement.find('.sm_product_images img').error(function(){
//             $(this).parent().remove();
//           });
//         }, 10);
//       }
//     };
//   }
// ])


.directive('scrollWatch', function () {
  return {
    restrict: 'A',
    template: "<span></span>",
    link: function (scope, elem, attrs) {
      $(window)
        .scroll(function () {
          if ($(window).scrollTop() > $(document).height() - 3*$(window).height()) {
            scope.$broadcast("scrolledBottom");
          }
          return false;
        });
    }
  };
})

;
