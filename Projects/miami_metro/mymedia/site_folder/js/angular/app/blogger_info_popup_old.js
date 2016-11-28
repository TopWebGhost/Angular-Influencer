'use strict';


var BloggerMoreInfoCtrl = function($scope, $compile, keywordQuery, filtersQuery, tsQueryCache) {
  this.scope = $scope;
  this.compile = $compile;
  this.keywordQuery = keywordQuery;
  this.filtersQuery = filtersQuery;
  this.tsQueryCache = tsQueryCache;

  this.panelScope = null;
  this.wrapper = null;
  this.elem = null;
  this.finalUrl = null;

  this.bloggersRoot = null;
};

BloggerMoreInfoCtrl.$inject = ['$scope', '$compile', 'keywordQuery', 'filtersQuery', 'tsQueryCache'];

BloggerMoreInfoCtrl.prototype.buildPanel = function(sourceUrl, options) {
  if (!sourceUrl) return;

  this.finalUrl = this.getFinalUrl(sourceUrl, options);

  this.bloggersRoot = document.getElementById('bloggers_root');
  if (this.bloggersRoot === null) return;

  console.log('building panel');

  this.wrapper = document.createElement('span');
  this.wrapper.setAttribute('id', 'blogger_panel_wrapper');

  this.elem = document.createElement('span');
  this.elem.setAttribute('blogger-more-info-popup', '');
  this.elem.setAttribute('url', this.finalUrl);

  this.wrapper.appendChild(this.elem);
  this.bloggersRoot.appendChild(this.wrapper);

  this.panelScope = this.scope.$new();
  this.compile(this.wrapper.innerHtml)(this.panelScope);
};

BloggerMoreInfoCtrl.prototype.destroyPanel = function() {
  if (this.panelScope) {
    this.panelScope.$destroy();
    this.panelScope = null;
  }

  if (this.wrapper) {
    this.bloggersRoot.removeChild(this.wrapper);
    this.wrapper = null;
    this.elem = null;
  }
  
  this.bloggersRoot = null;
};

BloggerMoreInfoCtrl.prototype.getFinalUrl = function(sourceUrl, options) {
  var joiner = '?';
  var final_url = sourceUrl;

  if (this.tsQueryCache.empty()) {
    var query = this.keywordQuery.getQuery();
    var filtersquery = this.filtersQuery.getQuery();
    var keyword = null;
    var brandsQuery = [];
    if(query.type == "all" || query.type == "keyword"){
      keyword = query.query;
      brandsQuery.push(query.query);
    }

    if(query.type == "brand"){
      if(query.query !== undefined && query.query.value !== undefined){
        query.query = query.query.value;
      }
      brandsQuery.push(query.query);
    }
    if(filtersquery && filtersquery.brand.length >0 ){
      var i = filtersquery.brand.length;
      var brand;
      while(--i >= 0){
        if(filtersquery.brand[i] !== undefined && filtersquery.brand[i].value !== undefined){
          brand = filtersquery.brand[i].value;
        }else{
          brand = filtersquery.brand[i];
        }
        brandsQuery.push(brand);
      }
    }
    
    if(keyword){
      final_url += joiner+"q="+rfc3986EncodeURIComponent(keyword);
      joiner = "&";
    }
    if(brandsQuery.length > 0){
      final_url += joiner+"brands="+rfc3986EncodeURIComponent(brandsQuery);
    }
  } else {
    final_url += '?' + 'q=' + rfc3986EncodeURIComponent(angular.toJson(this.tsQueryCache.get()))
      + "&json=" + true;
  }

  if (options && options.isBloggerApproval && options.campaignId) {
    final_url += '?campaign_posts_query=' + options.campaignId;
  }

  return final_url;
}


angular.module('theshelf')

  .directive('bloggerMoreInfo', ['$compile', 'keywordQuery', 'filtersQuery',
                                 '$injector', 'tsQueryCache',
                                 function ($compile, keywordQuery, filtersQuery, $injector, tsQueryCache) {
  return {
    restrict: 'A',
    scope: true,
    controller: BloggerMoreInfoCtrl,
    controllerAs: 'bloggerMoreInfoCtrl',
    link: function (scope, iElement, iAttrs, ctrl) {
      scope.reload = iAttrs.reload !== undefined;

      scope.show = function(sourceUrl, options) {
        ctrl.buildPanel(sourceUrl, options);
      };

      scope.$on('killMe', function(theirScope) {
        ctrl.destroyPanel();
      });
    }
  };
}])


.directive('bpdPostsList', ['$compile', '$timeout', 'NotifyingService', function($compile, $timeout, NotifyingService) {
  return {
    restrict: 'A',
    scope: true,
    template: '<div class="feed_wrapper new_feed_wrapper salvattore_grid clearfix" data-columns></div>',
    controller: function() {},
    controllerAs: 'postsListCtrl',
    require: ['^bloggerMoreInfoPopup', 'bpdPostsList'],
    link: function(scope, iElement, iAttrs, ctrls) {
      var popupCtrl = ctrls[0], ctrl = ctrls[1];

      // yeah, you're right, it's a SHIT
      var shit = (function() {
        var PLATFORMS = {
          'Pinterest': 'pins',
          'Twitter': 'tweets',
          'Instagram': 'photos',
          'Youtube': 'youtube',
        };

        return {
          getItemPlatform: function(item) {
            return PLATFORMS[item.platform] || 'blog';
          },
        };
      })();

      var grid;

      NotifyingService.subscribe(scope, 'sectionRenderEvent_' + popupCtrl.popup.sections.postsList.id, function(theirScope, response) {
        var posts = response.data.posts,
            postElements = [];

        ctrl.posts = posts;

        angular.forEach(posts, function(item, index) {
          postElements.push(angular.element('<div feed-item feed-item-' + shit.getItemPlatform(item) + ' item="postsListCtrl.posts[' + index + ']" noheader></div>')[0]);
        });

        $timeout(function() {
          grid = iElement.find('.feed_wrapper');
          salvattore.register_grid(grid[0]);
          salvattore.append_elements(grid[0], postElements);
        }, 100);

        $timeout(function() {
          $compile(grid)(scope);
        }, 200);
      });
    }
  };
}])


.directive('bpdAgeDistributionChart', ['bpAgeDistributionChart', function(bpAgeDistributionChart) {

  var directive = bpAgeDistributionChart.createGenericChartDirective({bindTo: '#age_distribution_chart'});

  angular.extend(directive, {
    template: '<div id="age_distribution_chart" style="margin: 0px auto;"></div>',
    controllerAs: 'ageDistributionChartCtrl',
    require: ['^bloggerMoreInfoPopup', 'bpdAgeDistributionChart'],
  });

  return directive
}])


.directive('bpdCategoryChart', ['bpCategoryChart', function(bpCategoryChart) {

  var directive = bpCategoryChart.createGenericChartDirective({bindTo: '#category_chart'});

  angular.extend(directive, {
    template: [
        '<div class="blog_stat_block" ng-style="{\'display\': \'inline-block\', \'width\': (100 / categoryChartCtrl.chart.cleanedData.length) - 2 + \'%\', \'margin\': \'0 auto\'}" ng-repeat="items in categoryChartCtrl.chart.cleanedData">',
            '<div id="category_chart_{{ $index }}" style="margin: 0px auto;"></div>',
            '<div style="text-align: center; color: #656565; font-family: Arial, Helvetica, sans-serif; font-size: 15px;">{{ items[0] | capitalize }}</div>',
        '</div>'
      ].join(''),
    controllerAs: 'categoryChartCtrl',
    require: ['^bloggerMoreInfoPopup', 'bpdCategoryChart'],
  });

  return directive;
}])


.directive('bpdTrafficSharesChart', ['bpTrafficSharesChart', function(bpTrafficSharesChart) {
  var directive = bpTrafficSharesChart.createGenericChartDirective({bindTo: '#traffic_shares_chart'});

  angular.extend(directive, {
    template: '<div id="traffic_shares_chart" style="margin: 0px auto;"></div>',
    controllerAs: 'trafficSharesCtrl',
    require: ['^bloggerMoreInfoPopup', 'bpdTrafficSharesChart'],
  });

  return directive;
}])


.directive('bpdMonthlyVisitsChart', ['bpMonthlyVisitsChart', function(bpMonthlyVisitsChart) {
  var directive = bpMonthlyVisitsChart.createGenericChartDirective({bindTo: '#monthly_visits_chart'});

  angular.extend(directive, {
    template: '<div id="monthly_visits_chart" style="margin: 0px auto;"></div>',
    controllerAs: 'monthlyVisitsCtrl',
    require: ['^bloggerMoreInfoPopup', 'bpdMonthlyVisitsChart'],
  });

  return directive;
}])


.directive('bpdBrandMentionsChart', ['bpBrandMentionsChart', function(bpBrandMentionsChart) {
  var directive = bpBrandMentionsChart.createGenericChartDirective({
    bindTo: '#brand_mentions_chart',
    wrapper: '#brand_mentions_chart_wrapper',
  });

  angular.extend(directive, {
    template: [
      '<div id="brand_mentions_chart_wrapper" class="endorsed_brands">',
        '<div id="brand_mentions_chart"></div>',
      '</div>',
    ].join(''),
    controllerAs: 'brandMentionsCtrl',
    require: ['^bloggerMoreInfoPopup', 'bpdBrandMentionsChart'],
  });

  return directive;
}])


.directive('bpdTopCountrySharesChart', ['$window', '$timeout', 'bpTopCountrySharesChart', function($window, $timeout, bpTopCountrySharesChart) {

  var resizeHandler;

  var directive = bpTopCountrySharesChart.createGenericChartDirective({
    bindTo: function() {
      return document.getElementById('top_country_shares_chart')
    },
    renderCb: function(chartInstance) {
      resizeHandler = function() {
        chartInstance.resize();
      };
      $timeout(function() {
        $window.addEventListener('resize', resizeHandler);
      }, 400);
    },
    destroyCb: function(chartInstance) {
      if (resizeHandler) {
        $window.removeEventListener('resize', resizeHandler);
      }
    },
  });

  angular.extend(directive, {
    template: '<div id="top_country_shares_chart" style="margin: 0px auto;"></div>',
    controllerAs: 'topCountrySharesChartCtrl',
    require: ['^bloggerMoreInfoPopup', 'bpdTopCountrySharesChart'],
  });

  return directive;
}])


.directive('bpdEngagementStatsChart', ['bpEngagementStatsChart', function(bpEngagementStatsChart) {
  var directive = bpEngagementStatsChart.createGenericChartDirective({bindTo: '#engagement_stats_chart'});

  angular.extend(directive, {
    template: '<div id="engagement_stats_chart" style="margin: 0px auto;"></div>',
    controllerAs: 'engagementStatsCtrl',
    require: ['^bloggerMoreInfoPopup', 'bpdEngagementStatsChart'],
  });

  return directive;
}])


.directive('bloggerMoreInfoPopup', [
  '$filter',
  '$compile',
  '$q',
  '$http',
  '$timeout',
  '$sce',
  '$rootScope',
  '$window',

  'debug',
  'context',
  'LazyData',
  'tsStats',
  'tsInvitationMessage',
  'tsConfig',
  'singletonRegister',
  'disableScrollService',
  'tsBloggerPopup',
  // charts
  function ($filter, $compile, $q, $http, $timeout, $sce, $rootScope, $window, debug, context, LazyData, tsStats,
    tsInvitationMessage, tsConfig, singletonRegister, disableScrollService, tsBloggerPopup) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/blogger_details_new.html'),
    controller: function() {
      var vm = this;

      vm.isOutreachVisible = function() {
        return context.isAuthenticated;
      };

    },
    controllerAs: 'bpCtrl',
    link: function (scope, iElement, iAttrs, ctrl) {

      // angular.element(window).disablescroll({excludedElements: iElement.find('[prevent-disablescrolling]')});
      // disableScrollService.incr();

      var sourceUrl = encodeURI(iAttrs.url);
      var urlParts = iAttrs.url.split('?');
      var influencerId = urlParts[0].split('/')[2];
      var messageData;

      function urlWithParams(url) {
        return url + (urlParts[1] ? '?' + urlParts[1] : '');
      }

      (function () {
        if (scope.user === undefined)
          scope.user = {};
        scope.user.can_follow = false;
        scope.loaded = false;
        scope.postsLoaded = true;
        scope.statsLoaded = false;
        scope.brandMentionsLoaded = false;
        scope.debug = debug;
        scope.hide_more_endorsed = true;

        scope.context = context;

        scope.hideOutreach = !context.isAuthenticated;

        scope.followPromise = null;
        scope.favoritePromise = null;
      })();

      (function () {
        // ctrl.user = scope.user;
        // ctrl.sections = tsBloggerPopup.sections;
      })();

      (function () {
        iElement.find(".blogger_details_panel_overlay").css({opacity: "0"});
        iElement.find(".blogger_details_panel").css({left: "-100%"});
        iElement.find(".blogger_details_panel_btns").css({opacity: "1", left: "-100%"});
        iElement.find(".blogger_details_panel_overlay").animate({opacity: "0.5"}, 1000);
        iElement.find(".blogger_details_panel").animate({left: "0"}, 1000);
        iElement.find(".blogger_details_panel_btns").animate({opacity: "1", left: "800px"}, 1000);
      })();

      (function () {

        scope.postCounts = {};
        scope.postCountsDefer = {};
        scope.loadPostCounts = function (url, postType) {
          scope.postCountsDefer[postType] = $q.defer();
          $timeout(function() {
            if (scope.postCountsDefer[postType] !== null) {
              scope.postCountsDefer[postType].resolve();
              scope.loadPostCounts(url, postType);
            }
          }, 20000);

          $http({
            url: url + '?' + urlParts[1],
            params: {
              post_type: postType,
            },
            method: "GET",
            timeout: scope.postCountsDefer[postType].promise
          }).success(function(data) {
            scope.postCountsDefer[postType].resolve();
            scope.postCountsDefer[postType] = null;
            scope.postCounts[postType] = data.count;
          });
        };

        scope.loadPosts = function(url) {
          // retrying
          scope.postsDefer = $q.defer();
          $timeout(function() {
            if (scope.postsDefer !== null) {
              scope.postsDefer.resolve();
              scope.loadPosts(url);
            }
          }, 20000);

          $http({
            url: url + '?' + urlParts[1],
            method: "GET",
            timeout: scope.postsDefer.promise
          }).success(function(data) {
            scope.postsDefer.resolve();
            scope.postsDefer = null;
            scope.posts = data["posts"];

            var posts = [];

            // create widgets for posts
            if (scope.posts) {
              angular.forEach(scope.posts, function(item, index) {
                var content = null;
                var mapping = {
                  'Pinterest': 'pins',
                  'Twitter': 'tweets',
                  'Instagram': 'photos',
                  'Youtube': 'youtube'
                };
                content = $('<div feed-item feed-item-' + (mapping[item.platform] || 'blog') + ' item="posts[' + index + ']" noheader></div>');
                posts.push(content[0]);
              });
            }

            // add both lists to salvattore
            salvattore.append_elements(scope.grid2[0], posts);

            //recompile template
            //give some time for dom to settle and refresh nano scroller
            $timeout(function() {
              scope.postsLoaded = true;
              if(scope.posts == undefined || scope.posts.length == 0){
                scope.hidePosts = true;
              }
              $compile(scope.grid2)(scope);
            }, 100);

          });
        };

        scope.loadItems = function(url) {
          scope.itemsLoaded = true;
          scope.hideItems = true;
          return;
          // retrying
          scope.itemsDefer = $q.defer();
          $timeout(function() {
            if (scope.itemsDefer !== null) {
              scope.itemsDefer.resolve();
              scope.loadItems(url);
            }
          }, 20000);

          $http({
            url: url + '?' + urlParts[1],
            method: "GET",
            timeout: scope.itemsDefer.promise
          }).success(function(data) {
            scope.itemsDefer.resolve();
            scope.itemsDefer = null;
            scope.items = data["items"];

            var items = [];

            // create widgets for items
            if (scope.items) {
              angular.forEach(scope.items, function(item, index) {
                if (angular.isUndefined(item.img_url_feed_view)) {
                  return;
                }
                var content = $('<div blogger-item item="items['+index+']">');
                items.push(content[0]);
              });
            }

            // add both lists to salvattore
            salvattore.append_elements(scope.grid1[0], items);

            //recompile template
            //give some time for dom to settle and refresh nano scroller
            $timeout(function() {
              scope.itemsLoaded = true;
              if(scope.items == undefined || scope.items.length == 0){
                scope.hideItems = true;
              }
              $compile(scope.grid1)(scope);
            }, 100);

          });
        };

        scope.loadBrandMentions = function(url) {

          function classes(root) {
            var classes = [];

            function recurse(name, node) {
              if (node.children) node.children.forEach(function(child) { recurse(node.name, child); });
              else classes.push({packageName: name, className: node.name, value: node.size});
            }

            recurse(null, root);
            return {children: classes};
          }

          function buildBubbleChart(data, params) {
            var root = data;
            var diameter = 700,
                height = 500,
                format = d3.format(",d"),
                // color = d3.scale.category20c();

                color = d3.scale.ordinal()
                  .domain(params.brand_names)
                  .range(["#a1e9f8", "#ffe88c", "#ffc0ba", "#84b8ff", "#8df2ce", "#c1c1c1"]);
                  // .range([
                  //   "#a454ff", "#e40076", "#ff7753", "#f8b025", "#dbd800",
                  //   "#89eac7", "#008ef1", "#0d3395"]);

            var bubble = d3.layout.pack()
                .sort(null)
                .size([diameter, height])
                .padding(1.5);

              var svg = d3.select("#endorsed_brands").append("svg")
                .attr("width", diameter)
                .attr("height", height)
                .attr("class", "bubble");

              var node = svg.selectAll(".node")
                  .data(bubble.nodes(classes(root))
                  .filter(function(d) { return !d.children; }))
                .enter().append("g")
                  .attr("class", "node")
                  .attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; });

              // var tooltip = d3.select("#endorsed_brands")
              //   .append("div")
              //   .style("position", "absolute")
              //   .style("z-index", "10")
              //   .style("visibility", "hidden")
              //   .style("color", "white")
              //   .style("padding", "8px")
              //   .style("background-color", "rgba(0, 0, 0, 0.75)")
              //   .style("border-radius", "6px")
              //   .style("font", "12px sans-serif")
              //   .text("tooltip");

              // node.append("title")
              //     .text(function(d) { return d.className + ": " + format(d.value); });

              node.append("circle")
                  .attr("r", function(d) { return d.r; })
                  .style("fill", function(d) { return color(d.packageName); });

              node.append("text")
                  .attr("dy", ".3em")
                  .style("text-anchor", "middle")
                  .style("font-size", "11px")
                  .style("font-family", "arial")
                  .style("fill", "black")
                  .text(function(d) { return d.className ? d.className.substring(0, d.r / 3) : ''; });

              angular.element('#endorsed_brands svg g.node').tipsy({ 
                gravity: 'w', 
                html: true, 
                title: function() {
                  var d = this.__data__;
                  return d.className + ": " + format(d.value);
                }
              });

              d3.select('.endorsed_brands').style("height", height + "px");
          }

          scope.brandMentionsDefer = $q.defer();
          $timeout(function(){
            if(scope.brandMentionsDefer !== null) {
              scope.brandMentionsDefer.resolve();
              scope.loadBrandMentions(url);
            }
          }, 20000);
          $http({
            url: url + '?' + urlParts[1],
            method: "GET",
            timeout: scope.brandMentionsDefer.promise
          }).success(function(data) {
            scope.brandMentionsDefer.resolve();
            scope.brandMentionsDefer = null;
            scope.brandMentions = data;
            scope.brandMentionsLoaded = true;
            if (scope.brandMentions.mentions_notsponsored) {
              scope.endorsed_brands = scope.brandMentions.mentions_notsponsored; // .slice(0, 20);
              $timeout(function () {
                buildBubbleChart(scope.endorsed_brands, data);
              }, 400);
            }
          });
        };

        scope.visits = {show: {monthly: false, empty: false}, loading: true, loaded: false};

        scope.loadMonthlyVisits = function(url, influencerId) {
          tsStats.visits.monthly(influencerId, url)
              .then(function(results) {
                  scope.visits.loading = false;
                  scope.visits.loaded = true;
                  if (results.columns.length) {
                    scope.visits.show.monthly = true;
                    scope.visits.show.empty = false;
                    $timeout(function() {
                        if ($('#blog_stat_monthly_visits').length > 0) {
                            try {
                                var chart = c3.generate({
                                    bindto: '#blog_stat_monthly_visits',
                                    data: {
                                        x: 'x',
                                        columns: results.columns,
                                        type: "area-spline",
                                    },
                                    color: {
                                      pattern: ["#63eda4" ],
                                    },
                                    legend: {
                                      show: false,
                                      //position: 'bottom',
                                      // inset: {
                                      //   anchor: 'top-left',
                                      //   x: 20,
                                      //   y: 0,
                                      //   step: 1,
                                      // },
                                    },
                                    axis: {
                                      x: {
                                        type: 'timeseries',
                                        tick: {
                                          format: '%m-%d-%Y',
                                          count: 7,
                                        },
                                        padding: {
                                          left: 0,
                                          right: 0,
                                        }
                                      },
                                      y: {
                                        inner: true,
                                        count: 5,
                                        tick: {
                                          count: 5,
                                          format: d3.format(',.0f'),
                                        },
                                      }
                                    }
                                });
                            } catch(e) {
                                console.log('error rendering monthly visits', e);
                            }
                        }
                    }, 700);
                  } else {
                      scope.visits.show.empty = true;
                  }
            }).catch(function(reason) {
                scope.visits.loading = false;
                console.log('unable to load monthly visits');
            });
        };

        function SharesMap() {
          var campaignMap = this;
          var bubbles = null;

          this.map = null;
          this.loading = false;
          this.data = null;
          this.buildMap = function() {
            console.log('building map');
            var paletteScale = d3.scale.linear()
              .domain([campaignMap.data[0].traffic_share, campaignMap.data[campaignMap.data.length - 1].traffic_share])
              .range(["#fff","#74ebd3", "#908ef8"]);
            var dataset = {};
            for (var i in campaignMap.data) {
              dataset[campaignMap.data[i].code] = {
                fillColor: paletteScale(campaignMap.data[i].traffic_share)
              };
            }
            campaignMap.map = new Datamap({
              element: document.getElementById('sharesMapContainer'),
              geographyConfig: {
                  popupOnHover: true,
                  highlightOnHover: false,
                  borderWidth: 1,
                  borderColor: '#c4c4c4'
              },
              responsive: true,
              scope: 'world',
              // scope: 'usa',
              fills: {
                city: 'red',
                lowest: 'red',
                low: 'blue',
                middle: 'yellow',
                high: 'pink',
                defaultFill: '#fff'
              },
              bubblesConfig: {
                borderWidth: 1,
                borderColor: '#fff',
                popupOnHover: true,
                highlightOnHover: true,
                highlightFillColor: '#FC8D59',
                highlightBorderColor: 'rgba(250, 15, 160, 0.2)',
                highlightBorderWidth: 2,
                highlightBorderOpacity: 1,
                highlightFillOpacity: 0.85,
                exitDelay: 100,
              },
              data: dataset,
            });
            campaignMap.placeBubbles();
            // campaignMap.map.legend();

            window.addEventListener('resize', function() {
              campaignMap.map.resize();
            });
          };

          this.placeBubbles = function() {
            var bubbles = [];
            campaignMap.data.forEach(function(location) {
              if (location.point) {
                bubbles.push({
                  radius: 5 + location.traffic_share * 100,
                  fillKey: 'city',
                  latitude: location.point.latitude,
                  longitude: location.point.longitude,
                  location: location,
                });
              }
            });
            campaignMap.map.bubbles(bubbles, {
              animate: false,
              popupTemplate: function(geo, data) {
                var infs = ['<div class="hoverinfo">'];
                infs.push('<strong>' + data.location.country_name + ' (' + (data.location.traffic_share * 100).toFixed(2) + '%)' + '</strong><br />');
                infs.push('</div>');
                return infs.join('');
              }
            });
          };

          this.setData = function(data) {
            console.log('loading data');
            // campaignMap.loading = true;
            campaignMap.data = data;
            $timeout(campaignMap.buildMap, 400);
          };
        }

        function TopCountryShares() {
          var self = this;

          self.isVisible = function() {
            return !scope.user.has_artificial_blog_url && !self.empty && self.shouldLoad();
          };

          self.shouldLoad = function() {
            // return context.isSuperuser;
            return true;
          };

          self.reset = function () {
            self.empty = false;
            self.loading = false;
            self.loaded = false;
          };

          self.reset();
        }

        scope.topCountryShares = new TopCountryShares();

        scope.loadTopCountryShares = function (url, influencerId) {
          if (!scope.topCountryShares.shouldLoad()) {
            return;
          }
          scope.topCountryShares.loading = true;
          tsStats.traffic.topCountryShares(influencerId, url)
            .then(function(results) {
              scope.topCountryShares.loading = false;
              scope.topCountryShares.loaded = true;

              if (results.length) {
                  scope.topCountryShares.empty = false;
                  var sharesMap = new SharesMap();
                  sharesMap.setData(results);
              } else {
                  scope.topCountryShares.empty = true;
              }
            }, function() {
              scope.topCountryShares.reset();
              scope.topCountryShares.empty = true;
            }).catch(function(reason) {
              scope.topCountryShares.reset();
              scope.topCountryShares.empty = true;
            });
        };

        scope.trafficShares = {empty: false, show: true, loading: true, loaded: false}

        scope.loadTrafficShares = function(url, influencerId) {
          tsStats.traffic.shares(influencerId, url)
            .then(function(results) {
                scope.trafficShares.loading = false;
                scope.trafficShares.loaded = true;

                results = results.filter(function(x) { return x.value > 0; });

                if (results.length) {
                  $timeout(function() {
                      if ($('#blog_stat_traffic_shares').length > 0) {
                          try {
                              var chartData = [];
                              for (var i in results) {
                                chartData.push([results[i].type, results[i].value]);
                              }
                              c3.generate({
                                bindto: '#blog_stat_traffic_shares',
                                color: {
                                  pattern: ["#ff7d99", "#f5695a", "#ffd633",
                                    "#8df2ce", "#5fdaf4", "#2f83f5", "#0052c1",
                                    "#be85ff"
                                  ],
                                },
                                legend: {
                                  position: 'bottom',
                                  // inset: {
                                  //   anchor: 'top-left',
                                  //   x: 20,
                                  //   y: 0,
                                  //   step: 1,
                                  // },
                                },
                                data: {
                                  columns: chartData,
                                  type: 'donut',
                                },
                                donut: {
                                  title: 'Traffic Sources',
                                }
                              });
                              // for (var i in results)
                              //   chartData.push({
                              //     label: results[i].type,
                              //     value: results[i].value
                              //   });
                              // var donut_formatter = function(y, data){
                              //   return (data.value * 100).toFixed(2) + "%";
                              // }
                              // var traffic_shares_chart = {
                              //     element: 'blog_stat_traffic_shares',
                              //     data: chartData,
                              //     resize: true,
                              //     formatter: donut_formatter,
                              //     colors: ["#a454ff", "#e40076", "#ff7753",
                              //       "#f8b025", "#dbd800", "#89eac7", "#008ef1",
                              //       "#0d3395"
                              //     ]
                              // };
                              // Morris.Donut(traffic_shares_chart);
                              scope.trafficShares.empty = false;
                          } catch(e) {
                              console.log('error rendering traffic shares', e);
                          }
                      }
                  }, 600);
                } else {
                    scope.trafficShares.empty = true;
                }
          }).catch(function(reason) {
              scope.trafficShares.loading = false;
              console.log('unable to load traffic shares');
          });
        };
        
        scope.loadStats = function(url) {
          scope.statsDefer = $q.defer();
          $timeout(function(){
            if(scope.statsDefer !== null) {
              scope.statsDefer.resolve();
              scope.loadStats(url);
            }
          }, 20000);
          $http({
            url: url + '?' + urlParts[1],
            method: "GET",
            timeout: scope.statsDefer.promise
          }).success(function(data) {
            scope.statsDefer.resolve(data);
            scope.statsDefer = null;
            scope.stats = data;
              scope.statsLoaded = true;
              // var donut_formatter = function(y, data){
              //   return data.value + " / " + data.percentage + "%";
              // }
              // if(scope.stats.relfashion_stats){
              //   try{
              //     Morris.Donut({
              //       element: 'blog_stat_relfashion',
              //       data: scope.stats.relfashion_stats,
              //       formatter: donut_formatter,
              //     });
              //   }catch(e){console.log('1', e);};
              // }
              // if(scope.stats.category_stats){
              //   try{
              //     Morris.Donut({
              //       element: 'blog_stat_categories',
              //       data: scope.stats.category_stats,
              //       formatter: donut_formatter,
              //       colors: ["#a454ff", "#e40076", "#ff7753",
              //         "#f8b025", "#dbd800", "#89eac7", "#008ef1",
              //         "#0d3395"
              //       ]
              //     });
              //   }catch(e){console.log('2', e);};
              // }
              if (scope.stats.popularity_stats && scope.stats.popularity_sums) {
                try {
                    var followers_ykeys = [];
                    var followers_labels = {};
                    var comments_ykeys = [];
                    var comments_labels = [];
                    var socialLineColors = {};
                    var social_colors = {
                      'twitter': '#39ceee',
                      'facebook': '#0066f1',
                      'instagram': '#f7c600',
                      'pinterest': '#e90084',
                      'youtube': '#f5695a',
                    };
                    for(var idx = 0; idx < scope.stats.popularity_stats.series.length; idx++){
                        var serie = scope.stats.popularity_stats.series[idx];
                        if (!scope.stats.popularity_sums[serie.key])
                          continue;
                        if (scope.stats.popularity_sums[serie.key]["followers"] > 0) {
                            followers_ykeys.push(serie.key+"_num_followers");
                            followers_labels[serie.key + "_num_followers"] = serie.label + " followers";
                            socialLineColors[serie.key + "_num_followers"] = social_colors[serie.key.split('_')[0]];
                        }
                        if (scope.stats.popularity_sums[serie.key]["comments"] > 0) {
                            comments_ykeys.push(serie.key+"_num_comments");
                            comments_labels.push(serie.label+" comments");
                        }
                    }
                    if (scope.stats.popularity_stats.followers_data.length) {
                      var fData = scope.stats.popularity_stats.followers_data;

                      for (var i = fData.length - 2; i >= 0; i--) {
                        for (var key in fData[i]) {
                          var value = fData[i];
                          if (!isNaN(value[key]) && value[key] == 0) {
                            value[key] = fData[i + 1][key];
                          }
                        }
                      }

                      scope.followersYkeys = followers_ykeys;
                      scope.followersLabels = followers_labels;
                      scope.lineColors = socialLineColors;

                      var chartData = {};
                      for (var i in scope.stats.popularity_stats.followers_data) {
                        for (var k in scope.stats.popularity_stats.followers_data[i]) {
                          if (!chartData[k]) {
                            chartData[k] = [];
                          }
                          chartData[k].push(scope.stats.popularity_stats.followers_data[i][k]);
                        }
                      }
                      var columnsData = [];
                      for (var i in chartData) {
                        var nt = [i];
                        for (var j in chartData[i]) {
                          nt.push(chartData[i][j]);
                        }
                        columnsData.push(nt);
                      }

                      // var morrisData = {
                      //   element: 'blog_stat_popularity_followers',
                      //   data: scope.stats.popularity_stats.followers_data,
                      //   xkey: 'date',
                      //   ykeys: followers_ykeys,
                      //   labels: followers_labels,
                      //   lineColors: socialLineColors,
                      //   pointSize: 0,
                      //   lineWidth: 1,
                      //   hideHover: true,
                      //   fillOpacity: 0.1,
                      //   smooth: false,
                      //   behaveLikeLine: true,
                      // };
                      var chartTypes = {};
                      for (var i in columnsData) {
                        chartTypes[columnsData[i][0]] = 'area-spline';
                      }
                      $timeout(function() {
                        try {
                          // Morris.Area(morrisData);
                          c3.generate({
                            bindto: '#blog_stat_popularity_followers',
                            data: {
                              x: 'date',
                              columns: columnsData,
                              types: chartTypes,
                              colors: socialLineColors,
                              names: followers_labels,
                              groups: [followers_ykeys],
                            },
                            size: {
                              height: 430
                            },
                            legend: {
                              show: false,
                              //position: 'bottom',
                              // inset: {
                              //   anchor: 'top-left',
                              //   x: 20,
                              //   y: 0,
                              //   step: 1,
                              // },
                            },
                            axis: {
                              x: {
                                type: 'timeseries',
                                tick: {
                                  format: '%m-%d-%Y',
                                  count: 7,
                                },
                                padding: {
                                  left: 0,
                                  right: 0,
                                }
                              },
                              y: {
                                inner: true,
                                count: 5,
                                tick: {
                                  count: 5,
                                  format: d3.format(',.0f'),
                                },
                              }
                            }
                          });
                        } catch(e) {console.log('3', e);};
                      }, 400);
                    }
                    // if(scope.stats.popularity_stats.comments_data.length){
                    //   try {
                    //     Morris.Area({
                    //         element: 'blog_stat_popularity_comments',
                    //         data: scope.stats.popularity_stats.comments_data,
                    //         xkey: 'date',
                    //         ykeys: comments_ykeys,
                    //         labels: comments_labels,
                    //         pointSize: 0,
                    //         lineWidth: 1,
                    //         hideHover: true,
                    //         fillOpacity: 0.1,
                    //         smooth: false,
                    //         behaveLikeLine: true,
                    //     });
                    //   } catch (e) {console.log('4', e);};
                    // }
                } catch (e) {console.log(e);};
              }
          });
        };

        scope.socialPostTypes = ['photos', 'pins', 'tweets', 'videos'];
      })();

      ctrl.popup = new tsBloggerPopup({
        sourceUrl: sourceUrl,
      });

      ctrl.user = {};

      ctrl.popup.mainLoader.load().then(function(response) {
        angular.extend(ctrl.user, response.data);

        if (ctrl.user.blog_name) {
          ctrl.user.blog_name = $sce.trustAsHtml(ctrl.user.blog_name);
        }

        // @todo: refactor this
        messageData = tsInvitationMessage.get(scope);

        $timeout(function() {
            iElement.find('.nano').nanoScroller({alwaysVisible: true});
            iElement.find('.nano').nanoScroller({ scroll: 'top' });
            iElement.find('.bs_tooltip').tooltip();
        }, 500);

        ctrl.popup.createSections({userData: ctrl.user});
        ctrl.popup.renderSections();

      }, function() {
        console.log('oops, mainLoader failed to load in controller');
      });

      (function() {

        // scope.load = function() {
        //   scope.influencerPromise = $q.defer();
        //   $timeout(function(){
        //     if(scope.influencerPromise !== null) {
        //       scope.influencerPromise.resolve();
        //       scope.load();
        //     }
        //   }, 20000);
        //   $http({
        //     url: sourceUrl,
        //     method: "GET",
        //     timeout: scope.influencerPromise.promise,
        //   }).success(function(data){
        //     scope.influencerPromise.resolve();
        //     scope.influencerPromise = null;
        //     var items1=[];
        //     var items2=[];
        //     scope.loaded = true;
        //     angular.extend(scope.user, data);
        //     scope.user.blog_name = $sce.trustAsHtml(scope.user.blog_name);
        //     messageData = tsInvitationMessage.get(scope);

        //     $timeout(function() {
        //         $(".nano").nanoScroller({alwaysVisible: true});
        //         $(".nano").nanoScroller({ scroll: 'top' });
        //         $('.bs_tooltip').tooltip();
        //     }, 500);

        //     // scope.loadStats(data.stats_json_url);
        //     // scope.loadBrandMentions(data.brand_mentions_json_url);
        //     // scope.loadPosts(data.posts_json_url);
        //     // scope.loadItems(data.items_json_url);
        //     // scope.loadMonthlyVisits(data.monthly_visits_json_url, data.id);
        //     // scope.loadTrafficShares(data.traffic_shares_json_url, data.id);
        //     // scope.loadTopCountryShares(data.top_country_shares_json_url, data.id);
        //     // scope.socialPostTypes.forEach(function (postType) {
        //     //   scope.loadPostCounts(data.post_counts_json_url, postType);
        //     // });

        //     function buildCategoryChart() {
        //       var categoryInfoData = [],
        //         categoryTotal = 0;
        //       if (scope.user.category_info !== undefined && scope.user.category_info.count) {
        //         for (var key in scope.user.category_info.count) {
        //           if (key == 'total')
        //             continue;
        //           categoryInfoData.push([key, scope.user.category_info.count[key]]);
        //           categoryTotal += scope.user.category_info.count[key];
        //         }
        //       }
        //       for (var i in categoryInfoData) {
        //         categoryInfoData[i][1] = (categoryInfoData[i][1] / categoryTotal * 100).toFixed(1);
        //       }

        //       scope.categoryInfo = {show: true, empty: false, data: categoryInfoData};
        //       scope.categoryInfo.empty = categoryInfoData.length < 1;

        //       $timeout(function() {
        //         var colors = ["#ff7d99", "#f5695a", "#ffd633",
        //           "#8df2ce", "#5fdaf4", "#2f83f5", "#0052c1", "#be85ff"];
        //         try {
        //           for (var i in categoryInfoData) {
        //             c3.generate({
        //               bindto: '#blog_category_info_' + i,
        //               color: {
        //                 pattern: ["#ff7d99", "#f5695a", "#ffd633",
        //                   "#8df2ce", "#5fdaf4", "#2f83f5", "#0052c1",
        //                   "#be85ff"
        //                 ],
        //               },
        //               legend: {
        //                 position: 'bottom',
        //                 // inset: {
        //                 //   anchor: 'top-left',
        //                 //   x: 20,
        //                 //   y: 0,
        //                 //   step: 1,
        //                 // },
        //               },
        //               color: {
        //                 pattern: [colors[i]],
        //               },
        //               data: {
        //                 columns: [categoryInfoData[i]],
        //                 // type: 'donut',
        //                 type: 'gauge',
        //               },
        //               size: {
        //                 height: 80,
        //               },
        //               // title: {
        //               //   text: $filter('capitalize')(categoryInfoData[i][0]),
        //               // },
        //               // donut: {
        //               //   title: 'Post Categories',
        //               // },
        //             });
        //           }
        //         } catch(e) {console.log('3', e);};
        //       }, 400);
        //     }

        //     function buildAgeDistributionChart() {
        //       $timeout(function () {
        //         try {
        //           var chartData = [];
        //           for (var i in scope.user.age_distribution) {
        //             chartData.push([scope.user.age_distribution[i].label, scope.user.age_distribution[i].value]);
        //           }
        //           c3.generate({
        //             bindto: '#age_distribution_info',
        //             color: {
        //               pattern: ["#ff7d99", "#f5695a", "#ffd633",
        //                 "#8df2ce", "#5fdaf4", "#2f83f5", "#0052c1",
        //                 "#be85ff"
        //               ],
        //             },
        //             legend: {
        //               position: 'bottom',
        //               // inset: {
        //               //   anchor: 'top-left',
        //               //   x: 20,
        //               //   y: 0,
        //               //   step: 1,
        //               // },
        //             },
        //             data: {
        //               columns: chartData,
        //               type: 'donut',
        //             },
        //             donut: {
        //               title: 'Age Distribution',
        //             }
        //           });
        //           // Morris.Donut({
        //           //   element: 'age_distribution_info',
        //           //   data: scope.user.age_distribution,
        //           //   resize: true,
        //           //   formatter: function(y, data) {
        //           //     return (data.value).toFixed(2) + "%";
        //           //   },
        //           //   colors: ["#a454ff", "#e40076", "#ff7753",
        //           //     "#f8b025", "#dbd800", "#89eac7", "#008ef1",
        //           //     "#0d3395"
        //           //   ]
        //           // });
        //         } catch(e) {console.log('age_distribution_info error', e);}
        //       }, 600);
        //     }

        //     // buildCategoryChart();
        //     // buildAgeDistributionChart();

        //   });
        // };

        // scope.load();
      })();

      ctrl.close = function() {
        // if (disableScrollService.decr()) {
        //   angular.element(window).disablescroll('undo');
        // }

        ctrl.popup.close();

        (function () {
          // scope.socialPostTypes.forEach(function (postType) {
          //   if (scope.postCountsDefer[postType]) {
          //     scope.postCountsDefer[postType].resolve();
          //     scope.postCountsDefer[postType] = null;
          //   }
          // });
          // if(scope.influencerPromise) {
          //   scope.influencerPromise.resolve();
          //   scope.influencerPromise = null;
          // }
          // if(scope.followPromise) {
          //   scope.followPromise.resolve();
          //   scope.followPromise = null;
          // }
          // if(scope.favoritePromise) {
          //   scope.favoritePromise.resolve();
          //   scope.favoritePromise = null;
          // }
          // if(scope.postsDefer) {
          //   scope.postsDefer.resolve();
          //   scope.postsDefer = null;
          // }
          // if(scope.itemsDefer) {
          //   scope.itemsDefer.resolve();
          //   scope.itemsDefer = null;
          // }
          // if(scope.statsDefer) {
          //   scope.statsDefer.resolve();
          //   scope.statsDefer = null;
          // }
          // if(scope.brandMentionsDefer) {
          //   scope.brandMentionsDefer.resolve();
          //   scope.brandMentionsDefer = null;
          // }
        })();

        iElement.find(".blogger_details_panel_overlay").animate({opacity: "0"}, 500, 'swing', function(){
          scope.$emit("killMe");
          // scope.$destroy();
          // iElement.remove();
        });
        iElement.find(".blogger_details_panel").animate({left: "-100%"}, 500);
        iElement.find(".blogger_details_panel_btns").animate({opacity: "0",left: "-100%"}, 250);
      };


      (function () {
        scope.openFavoritePopup = function(options){
          // scope isolation bloggerMoreInfoPopup -> bloggerMoreInfo -> BloggersSearchCtrl
          // scope isolation bloggerMoreInfoPopup -> favoritedTable

          var cscope = scope;
          while(cscope !== null && cscope.doOpenFavoritePopup === undefined){
            cscope = cscope.$parent;
          }
          if(cscope){
            cscope.doOpenFavoritePopup(options);
          }
        };

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
      })();


      // GRID STUFF

      // scope.salvattore_refresh_timeout = null;
      // scope.grid1 = iElement.find('.extra_itms');
      // scope.grid2 = iElement.find('.feed_wrapper');
      // $timeout(function() {
      //   salvattore.register_grid(scope.grid1[0]);
      //   salvattore.register_grid(scope.grid2[0]);
      //   scope.postsLoaded = false;
      // }, 10);

      // scope.$on("refreshSalvattore", function(){
      //   console.log('refresh salvattore');
      //   if(scope.salvattore_refresh_timeout){
      //     $timeout.cancel(scope.salvattore_refresh_timeout);
      //   }
      //   scope.salvattore_refresh_timeout = $timeout(function(){
      //     var tmp = iElement.find("[blogger-item]").clone().toArray();
      //     iElement.find("[blogger-item]").remove();
      //     salvattore.append_elements(scope.grid1[0], tmp);
      //     $compile(scope.grid1)(scope);
      //   }, 100);
      // });


      // NOT USED STUFF

      // scope.has_more_brands = function(){
      //   if (scope.endorsed_brands === undefined) return false;
      //   return scope.brandMentions.mentions_notsponsored.length > scope.endorsed_brands.length;
      // };
      // scope.show_more_brands = function(){
      //   scope.endorsed_brands = scope.brandMentions.mentions_notsponsored;
      // };

      // scope.toggle_follow = function(){
      //   if(scope.followPromise){
      //     return;
      //   }
      //   scope.followPromise = $q.defer();
      //   scope.influencerPromise.promise.then(function(){
      //     $http.get(scope.user.follow_url, {timeout: scope.followPromise.promise}).success(function(){
      //       if(scope.user.is_following){
      //         scope.user.is_following = false;
      //       }else{
      //         scope.user.is_following = true;
      //       }
      //       scope.followPromise = null;
      //     });

      //   });
      // };

    }
  };
}])


.directive('bloggerItem', ['tsConfig', function (tsConfig) {
  return {
    restrict: 'A',
    scope: {
      'item': '='
    },
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/blogger_item.html'),
    link: function (scope, iElement, iAttrs) {
      iElement.find('img').error(function(){
        iElement.remove();
        scope.$emit("refreshSalvattore");
      });
      iElement.find('img').load(function(){
        if($(this)[0].naturalWidth < 200 || $(this)[0].naturalHeight < 200){
          iElement.remove();
          scope.$emit("refreshSalvattore");
        }
      });
    }
  };
}])


.directive('bloggerPost', ['$sce', 'tagStripper', 'tsConfig', function ($sce, tagStripper, tsConfig) {
  return {
    restrict: 'A',
    scope: {
      'item': '=',
      'user': '='
    },
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/blogger_post.html'),
    link: function (scope, iElement, iAttrs) {

      var check_image = function(imgs){
        var img = imgs.shift();
        var tmp_img = new Image();
        if(img === undefined){
          iElement.find(".post_pic").hide();
          return;
        }
        tmp_img.onerror = function(){
          check_image(imgs);
        };
        tmp_img.onload = function(){
          if(tmp_img.width < 200 || tmp_img.height < 200 || tmp_img.width > tmp_img.height*3){
            check_image(imgs);
          }else{
            scope.$apply(function(){
              if(scope.item === undefined){
                return;
              }
              scope.item.post_img = img;
            });
          }
        };
        tmp_img.src = img;
      };

      var subs = scope.item.content;
      if(scope.item.post_img === undefined){
        if(scope.item.post_image === null){
          var imgs = scope.item.content_images;
          if(imgs.length > 0) {
            check_image(imgs);
          }else{
            iElement.find(".post_pic").hide();
          }
        }else{
          scope.item.post_img = scope.item.post_image;
        }
      }
      scope.item.content_safe = $sce.trustAsHtml(subs);
      scope.item.title_safe = $sce.trustAsHtml(scope.item.title);
    }
  };
}])

;
