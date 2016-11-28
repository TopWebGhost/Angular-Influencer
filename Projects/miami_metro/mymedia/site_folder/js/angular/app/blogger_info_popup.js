'use strict';


var BloggerMoreInfoCtrl = (function() {
  var BloggerMoreInfoCtrl = function($scope, $compile, keywordQuery, filtersQuery, tsQueryCache, NotifyingService) {
    this.scope = $scope;
    this.compile = $compile;
    this.keywordQuery = keywordQuery;
    this.filtersQuery = filtersQuery;
    this.tsQueryCache = tsQueryCache;
    this.NotifyingService = NotifyingService;

    this.panelScope = null;
    this.wrapper = null;
    this.elem = null;
    this.finalUrl = null;

    this.root = null;
    this.compiledElement = null;
  };


  BloggerMoreInfoCtrl.$inject = ['$scope', '$compile', 'keywordQuery', 'filtersQuery', 'tsQueryCache', 'NotifyingService'];

  BloggerMoreInfoCtrl.prototype.buildPanel = function(sourceUrl, options) {
    var self = this;

    // destroy old panel, just in case
    this.destroyPanel();

    if (!sourceUrl) return;

    this.finalUrl = this.getFinalUrl(sourceUrl, options);

    this.root = document.getElementById(options && options.root ? options.root : 'bloggers_root');
    if (this.root === null) return;

    console.log('building panel');

    this.wrapper = document.createElement('span');
    this.wrapper.setAttribute('id', 'blogger_panel_wrapper');

    this.elem = document.createElement('span');
    this.elem.setAttribute('blogger-more-info-popup', '');
    this.elem.setAttribute('url', this.finalUrl);

    this.wrapper.appendChild(this.elem);
    this.root.appendChild(this.wrapper);

    this.panelScope = this.scope.$new();
    // this.panelScope.$on('$destroy', function() {
    //   console.log('panelScope.$destroy event');
    //   if (self.compiledElement) {
    //     self.compiledElement.off();
    //   }
    // })
    this.compiledElement = this.compile(this.wrapper)(this.panelScope);

    this.NotifyingService.subscribe(this.scope, 'bpKill', function(theirScope) {
      self.destroyPanel();
    });
  };

  BloggerMoreInfoCtrl.prototype.destroyPanel = function() {
    console.log('destroyPanel call');
    if (this.panelScope) {
      this.panelScope.$destroy();
      this.panelScope = null;
    }

    if (this.wrapper) {
      this.root.removeChild(this.wrapper);
      this.wrapper = null;
    }

    if (this.compiledElement) {
      this.compiledElement.off();
      this.compiledElement.remove();
      this.compiledElement = null;
    }

    this.elem = null;
    this.root = null;
  };

  BloggerMoreInfoCtrl.prototype.getFinalUrl = function(sourceUrl, options) {
    var joiner = '?';
    var final_url = sourceUrl;

    if (options && options.isBloggerApproval && options.campaignId) {
      final_url += joiner + 'campaign_posts_query=' + options.campaignId;
    } else if (this.tsQueryCache.empty()) {
      var query = this.keywordQuery.getQuery();
      var filtersquery = this.filtersQuery.getQuery();
      var keyword = null;
      var brandsQuery = [];
      if (query.type == "all" || query.type == "keyword") {
        keyword = query.query;
        brandsQuery.push(query.query);
      }

      if (query.type == "brand") {
        if (query.query !== undefined && query.query.value !== undefined) {
          query.query = query.query.value;
        }
        brandsQuery.push(query.query);
      }
      if (filtersquery && filtersquery.brand.length > 0 ) {
        var i = filtersquery.brand.length;
        var brand;
        while (--i >= 0) {
          if (filtersquery.brand[i] !== undefined && filtersquery.brand[i].value !== undefined) {
            brand = filtersquery.brand[i].value;
          } else {
            brand = filtersquery.brand[i];
          }
          brandsQuery.push(brand);
        }
      }
      
      if (keyword) {
        final_url += joiner+"q="+rfc3986EncodeURIComponent(keyword);
        joiner = "&";
      }
      if (brandsQuery.length > 0) {
        final_url += joiner+"brands="+rfc3986EncodeURIComponent(brandsQuery);
      }
    } else {
      final_url += '?' + 'q=' + rfc3986EncodeURIComponent(angular.toJson(this.tsQueryCache.get()))
        + "&json=" + true;
    }

    return final_url;
  };

  return BloggerMoreInfoCtrl;
})();


angular.module('theshelf')


.service('msSearchMethod', ['_', '$rootScope', 'Restangular', 'NotifyingService',
      'context', function(_, $rootScope, Restangular, NotifyingService, context) {
  var self = this;

  var DEFAULT_MODE = context.brandSettings ? context.brandSettings.searchMethod : 'default';

  function find(value) {
      return _.findWhere(self.options, {value: value});
  }

  function select(value) {
      var nm = find(value);
      self.selected = nm ? nm : find(DEFAULT_MODE);
  }

  self.options = [
      {icon: 'icon-social_0_shelf_icon3', value: 'default', text: ''},
      {icon: '', value: 'r29', text: 'R29'},
  ];
  
  self.change = function(value) {
      var prev = self.selected.value;
      select(value);
      if (prev !== value) {
          NotifyingService.notify('search:change:searchMethod', value);
      }
      Restangular
          .one('brands', context.visitorBrandId)
          .post('flags', {
              search_method: value,
          });
  };

  select();
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
  'NotifyingService',
  'bpPopup',
  'tsPlatformIconClasses',

  'msSearchMethod',
  function ($filter, $compile, $q, $http, $timeout, $sce, $rootScope, $window, debug, context, LazyData, tsStats,
    tsInvitationMessage, tsConfig, singletonRegister, disableScrollService, NotifyingService, bpPopup,
    tsPlatformIconClasses, msSearchMethod) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/blogger_details_new.html'),
    controller: function($scope) {
      var vm = this;

      vm.context = context;
      vm.searchMethod = msSearchMethod;

      vm.platformIcons = tsPlatformIconClasses.get;
      vm.platformWrappers = tsPlatformIconClasses.getBase;

      vm.isOutreachVisible = function() {
        return context.isAuthenticated;
      };

      vm.openFavoritePopup = function(options) {
        NotifyingService.notify('openFavoritePopup', options, true);
      };

      vm.sendMessage = function(options) {
        if (options === undefined)
          return;
        angular.extend(options, {
          groupId: null,
          template: vm.messageData.body,
          subject: vm.messageData.subject,
          user: vm.user,
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
    controllerAs: 'bpCtrl',
    link: function (scope, iElement, iAttrs, ctrl) {

      // angular.element($window).disablescroll({excludedElements: iElement.find('[prevent-disablescrolling]')});
      // disableScrollService.incr();

      var sourceUrl = encodeURI(iAttrs.url);

      iElement.find(".blogger_details_panel_overlay").css({opacity: "0"});
      iElement.find(".blogger_details_panel").css({left: "-100%"});
      iElement.find(".blogger_details_panel_btns").css({opacity: "1", left: "-100%"});
      iElement.find(".blogger_details_panel_overlay").animate({opacity: "0.5"}, 1000);
      iElement.find(".blogger_details_panel").animate({left: "0"}, 1000);
      iElement.find(".blogger_details_panel_btns").animate({opacity: "1", left: "800px"}, 1000);

      ctrl.openEditingPopup = function() {
        ctrl.close();
        $timeout(function() {
          $rootScope.$broadcast('openInfluencerDataPopup', {influencer: ctrl.user});
        }, 700);
      };

      ctrl.initNanoScroller = function() {
        $timeout(function() {
          iElement.find('.nano').nanoScroller({alwaysVisible: true});
          iElement.find('.nano').nanoScroller({ scroll: 'top' });
          iElement.find('.bs_tooltip').tooltip();
        }, 500);
      };

      ctrl.refreshNanoScroller = function() {
        console.log('refreshNanoScroller');
        $timeout(function() {
          iElement.find('.nano').nanoScroller();
        }, 500);
      };

      ctrl.popup = new bpPopup({
        sourceUrl: sourceUrl,
      });

      ctrl.user = {};

      ctrl.popup.mainLoader.load().then(function(response) {
        angular.extend(ctrl.user, response);

        if (ctrl.user.blog_name) {
          ctrl.user.blog_name = $sce.trustAsHtml(ctrl.user.blog_name);
        }

        ctrl.initNanoScroller();

        ctrl.messageData = tsInvitationMessage.get({
          user: ctrl.user,
          context: ctrl.context
        });

        ctrl.popup.createSections({
          userData: ctrl.user,
          finalUrl: scope.bloggerMoreInfoCtrl ? scope.bloggerMoreInfoCtrl.finalUrl : null,
        });
        ctrl.popup.renderSections().forEach(function(sectionPromise) {
          sectionPromise.then(function() {
            ctrl.refreshNanoScroller();
          });
        });

      }, function(response) {
        ctrl.close();
        console.log(response);
        if (response && response.status == 403) {
          $timeout(function() {
            $rootScope.$broadcast("displayMessage", {
                message: "Oh no... looks like you're not logged in.",
            });
          }, 1000);
        }
        console.log('oops, mainLoader failed to load in controller');
      });

      ctrl.close = function() {
        // if (disableScrollService.decr()) {
        //   angular.element($window).disablescroll('undo');
        // }

        ctrl.popup.close();

        iElement.find(".blogger_details_panel_overlay").animate({opacity: "0"}, 500, 'swing', function() {
          NotifyingService.notify('bpKill');
        });
        iElement.find(".blogger_details_panel").animate({left: "-100%"}, 500);
        iElement.find(".blogger_details_panel_btns").animate({opacity: "0",left: "-100%"}, 250);
      };
    }
  };
}])


.directive('bloggerMoreInfo', ['$compile', 'keywordQuery', 'filtersQuery',
                               '$injector', 'tsQueryCache', 'NotifyingService',
                               function ($compile, keywordQuery, filtersQuery, $injector, tsQueryCache,
                                NotifyingService) {
  return {
    restrict: 'A',
    scope: true,
    controller: BloggerMoreInfoCtrl,
    controllerAs: 'bloggerMoreInfoCtrl',
    link: function (scope, iElement, iAttrs, ctrl) {
      scope.reload = iAttrs.reload !== undefined;

      ctrl.show = function(sourceUrl, options) {
        ctrl.buildPanel(sourceUrl, options);
      };

      // @todo: refactor all templates that use the directive in order
      // to remove the following statement
      scope.show = ctrl.show;
    }
  };
}])


.directive('bpdPostsList', ['_', '$compile', '$timeout', '$rootScope', 'NotifyingService', 'tsConfig', 'context',
    function(_, $compile, $timeout, $rootScope, NotifyingService, tsConfig, context) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/bpd_posts_list.html'),
    controller: function() {
      var vm = this;

      vm.masonryReload = function() {
          console.log('masonry.reload !!!');
          $rootScope.$broadcast('masonry.reload');
      };

      vm.masonryDebouncedReload = _.debounce(vm.masonryReload, 300);
    },
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

      ctrl.itemOptions = {
        noheader: true,
        skipSocial: true,
        bookmarks: false,
        debug: false,
        ugcView: false,
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
          return !this.showSocials();
        },
      };

      // var grid, compiledGrid, postElements = [];

      NotifyingService.subscribe(scope, 'sectionRenderEvent_' + popupCtrl.popup.sections.postsList.id, function(theirScope, response) {
        angular.forEach(response.posts, function(post) {
          post.platform = shit.getItemPlatform(post);
        });
        ctrl.posts = response.posts;
      });

      NotifyingService.subscribe(scope, 'itemBlock:resize', function() {
        ctrl.masonryReload();
        popupCtrl.refreshNanoScroller();
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


;
