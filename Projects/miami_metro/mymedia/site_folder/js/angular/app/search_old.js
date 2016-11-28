'use strict';

angular.module('theshelf')

.controller('BloggersSearchCtrl', ['$scope', '$http', '$timeout', '$location', '$q', 'debug', 'context', function ($scope, $http, $timeout, $location, $q, debug, context) {

    $scope.modes = [
        // {text: 'stats', mode:'stats'},
        {text: 'influencers', mode:'bloggers', url: 'influencers', metaModes: ['main_search', 'instagram_search']},
        {text: 'blog posts', mode:'posts', cf: 'blog', url: 'blog_posts', metaModes: ['main_search'], feedPage: 'pageBlog'},
        {text: 'tweets', mode:'posts', cf: 'tweets', url: 'tweets', metaModes: ['main_search'], feedPage: 'pageTwitter'},
        {text: 'instagrams', mode:'posts', cf: 'photos', url: 'instagrams', metaModes: ['main_search', 'instagram_search'], feedPage: 'pageInst'},
        {text: 'pins', mode:'posts', cf: 'pins', url: 'pins', metaModes: ['main_search'], feedPage: 'pagePin'},
        {text: 'youtube', mode:'posts', cf: 'youtube', url: 'youtube', metaModes: ['main_search'], feedPage: 'pageVideo'},
        {text: 'products', mode: 'posts', cf: 'products', url: 'products', metaModes: ['main_search'], feedPage: 'pageProd'},
        // {text: 'facebook', mode:'posts', cf: 'facebook'},
    ];

    $scope.navigation = {};

    $scope.shouldDisplayMode = function(mode) {
        if (!$scope.navigation.config)
            return false;
        if (mode.metaModes === undefined)
            return $scope.navigation.config.sub_tab === 'main_search';
        return mode.metaModes.indexOf($scope.navigation.config.sub_tab) > -1;
    };

    $scope.resetFiltersDefer = $q.defer();

    $scope.type_selected = {value: "all", text:"All", toggled: true};

    $scope.debug = debug;
    $scope.mode_selected = $scope.modes[0];
    $scope.mode = "bloggers";
    $scope.posts_warning = false;
    $scope.context = context;

    $scope.sort_by_selected = {text: 'Overall popularity'};
    // 'cf' property should be identical to ES field used for search
    $scope.sort_by_properties = [
        {text: 'Overall popularity', cf: 'popularity'},
        {text: 'Average number of comments', cf: 'engagement'},
        {text: "Blog followers", cf: 'social_platforms.Blog'},
        {text: "Facebook followers", cf: 'social_platforms.Facebook'},
        {text: "Twitter followers", cf: 'social_platforms.Twitter'},
        {text: "Instagram followers", cf: 'social_platforms.Instagram'},
        {text: "Pinterest followers", cf: 'social_platforms.Pinterest'},
    ];

    $scope.dateRangeModel = {
        startDate: null,
        endDate: null,
    };

    $scope.urlChangedManually = true;

    $scope.setUrl = function(pageNumber) {
        var url = '';
        if (pageNumber !== undefined)
            $scope.page = pageNumber;
        if ($scope.insideSavedSearch) {
            url += 'saved_search/' + $scope.savedQueries.selected.value + '/';
        }
        url += $scope.mode_selected.url + '/' + (isNaN($scope.page) ? 1 : $scope.page);
        // if (url !== $location.path()) {
        $scope.urlChangedManually = false;
        $location.path(url);
        // }
    };

    $scope.toggleMode = function(mode) {
        if ($scope.andOrFilterOn && !$scope.kwExpr.isDone)
            return;
        $scope.mode_selected = mode;
        $scope.page = 1;
        $scope.updateMode();
    };

    $scope.updateMode = function(doNotLoad, doNotChangeUrl){
        $scope.mode = $scope.mode_selected.mode;
        if ($scope.mode == 'posts') {
            $scope.active = false;
            $scope.content_filter = $scope.mode_selected.cf;
        } else {
            $scope.active = true;
        }
        if($scope.sort_by_selected.cf !== undefined){
          $scope.sort_by = $scope.sort_by_selected.cf;
        }
        if (doNotChangeUrl)
            return;
        $scope.setUrl();
        if (doNotLoad)
            return;
        $timeout(function() {
          $scope.$broadcast("reloadFeeds");
        }, 10);
    };

    $scope.doOpenFavoritePopup = function(options){
        var unselectAll = function(arr) {
            if (arr === undefined || arr === null)
                return;
            arr.forEach(function(el) {
                el.selected = false;
            });
        };
        options.afterSuccessCb = function() {
            [$scope.bloggers, $scope.productFeedBloggers, $scope.productFeedPosts].forEach(unselectAll);
        };
        $scope.$broadcast('openFavoritePopup', options);
    };

    $scope.openBulkFavoritePopup = function(options) {
        options = options || {};
        if (!$scope.context.predictionReportEnabled || $scope.mode_selected.url !== 'blog_posts') {
            $scope.doOpenFavoritePopup({influencers: ($scope.mode === 'posts' ? $scope.productFeedBloggers : $scope.bloggers)});
            return;
        }
        var yes = function() {
            var influencers = $scope.productFeedPosts
                .filter(function(item) { return item.user && item.selected; })
                .map(function(item) { return item.user; })
            influencers.forEach(function(inf) {
                inf.selected = true;
            });
            $scope.doOpenFavoritePopup({influencers: influencers});
        };
        var no = function() {
            $scope.doOpenFavoritePopup({posts: $scope.productFeedPosts});
        };
        $scope.$broadcast('openConfirmationPopup',
            'Do you want to Tag these influencers? Or do you want to Bookmark the posts to a post collection?',
            yes, no, {yesText: 'Influencers', noText: 'Posts', titleText: 'Please Choose'});
    };

    $scope.openUpgradePopup = function(influencer_id){
        $scope.$broadcast('openUpgradePopup');
    };

    $scope.openSaveSearchPopup = function(editing) {
        $scope.$broadcast("openSaveSearchPopup", editing === true ? $scope.savedQueries.selected : null);
    };

    $scope.populatePageInfo = function(data){
        $scope.page_info = data;
    };

    $scope.displayMessage = function(msg) {
        $scope.$broadcast("displayMessage", {message: msg});
    };

    $scope.reloadFeeds = function() {
        $scope.$broadcast('reloadFeeds');
    };

    $scope.applyDateRange = function() {
        if ($scope.filters === undefined || $scope.dateRangeModel.startDate === null || $scope.dateRangeModel.endDate === null)
            return;
        $scope.filters.time_range = {
            from: $scope.dateRangeModel.startDate,
            to: $scope.dateRangeModel.endDate
        };
        $scope.$broadcast('setFilters', $scope.filters);
    };

    $scope.$on("hasFilterSet", function(their_scope, isset){
        $scope.posts_warning = isset;
    });

    $scope.$watch('mode', function(newMode, oldMode){
        console.log($scope.mode, newMode, oldMode);
        return;
        if($scope.mode == 'bloggers' || $scope.mode === undefined){
            $scope.active = true;
        }else{
            $scope.active = false;
        }
    });

    // $scope.$watch('dateRangeModel.startDate', function() {
    //     $scope.applyDateRange();
    // });
    // $scope.$watch('dateRangeModel.endDate', function() {
    //     $scope.applyDateRange();
    // });

}])

.controller('PostAnalyticsCtrl', ['$scope', '$http', '$timeout', '$q', function($scope, $http, $timeout, $q) {

    var genericYes = function(url) {

        var deferred = $q.defer();

        $http({
            method: 'POST',
            url: url
        }).success(function(data) {
            if (data.error !== undefined) {
                deferred.reject({data: data.error});
            } else {
                deferred.resolve();
                $scope.displayMessage({loading: true});
                window.location.reload();
            }
        }).error(function(data) {
            deferred.reject({data: data || 'Error!'});
        });

        return deferred.promise;
    };

    $scope.newPostUrl = null;

    $scope.displayMessage = function(args) {
        $scope.$broadcast('displayMessage', args);
    };

    $scope.removePostAnalytics = function(url) {

        var yes = function() {
            return genericYes(url);
        };

        $scope.$broadcast('openConfirmationPopup',
            'Are you sure you want to remove?',
            yes, null);
    };

    $scope.confirmAndGo = function(url) {

        var yes = function() {
            return genericYes(url);
        };

        $scope.$broadcast('openConfirmationPopup',
            'Are you sure you want to re-calculate? This will take much longer to run.',
            yes, null);
    };

    $scope.addPostUrl = function(endpoint, collectionId, newPostUrl) {
        var postUrl = newPostUrl === undefined ? $scope.newPostUrl : newPostUrl;

        $scope.displayMessage(
            {message: "Adding..."});

        $http({
          method: 'POST',
          url: endpoint,
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          transformRequest: function(obj) {
            var str = [];
            for (var p in obj)
              str.push(encodeURIComponent(p) + "=" + encodeURIComponent(obj[p]));
            return str.join("&");
          },
          data: {url: postUrl, collection_id: collectionId}
        }).success(function() {
            $scope.displayMessage({loading: true});
            window.location = window.location.pathname;
        }).error(function(data) {
            data = data || {};
            $scope.displayMessage({message: data.message || 'Error!'});
        });

        $scope.newPostUrl = null;
    };

    $scope.openAddPostAnalyticsUrlsPopup = function(endpoint, collectionId) {
        $scope.$broadcast('openAddPostAnalyticsUrlsPopup', {
            endpoint: endpoint, collectionId: collectionId});
    };

    $scope.doOpenFavoritePopup = function(options) {
        $scope.$broadcast('openFavoritePopup', options)
    };

    $scope.inputKeyPress = function(keyEvent, endpoint, collectionId) {
        keyEvent.preventDefault();
        if (keyEvent.which === 13) {
          $scope.addPostUrl(endpoint, collectionId);
        }
    };

}])


.directive('postAnalyticsPanel', ['$http', function($http) {
  return {
    restrict: 'A',
    scope: {
      'post': '=',
    },
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/post_analytics_panel.html'),
    link: function(scope, iElement, iAttrs) {
      var endpoint = iAttrs.endpoint;
      // random number between 1 and 7, for random post image
      scope.random = Math.floor(Math.random() * 7 + 1);
      scope.remove = function() {
        $http({
          method: 'DELETE',
          url: endpoint,
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          transformRequest: function(obj) {
            var str = [];
            for (var p in obj)
              str.push(encodeURIComponent(p) + "=" + encodeURIComponent(obj[p]));
            return str.join("&");
          },
          data: {pk: scope.post.id}
        }).success(function() {
          console.log('remove');
          window.location.reload();
        }).error(function() {
          console.log('error');
        });
      };
    }
  };
}])


.directive('appliedFiltersPanel', [function() {
    return {
        restrict: 'A',
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/search_bloggers/applied_filters.html'),
        link: function(scope, iElement, iAttrs) {
            scope.autocompleteUrl = iAttrs.autocompleteUrl;
        }
    };
}])


.directive('bloggerSearchFilters',
           ['popularity', 'brands', 'priceranges', 'locations',
            '$timeout', 'genders', 'socials', 'activity', 'categories', 'tags',
            'enabled_filters', 'filtersQuery', '$http', '$q', 'context',
            function (popularity, brands, priceranges, locations, $timeout, genders,
              socials, activity, cats, tags, enabled_filters, filtersQuery,
              $http, $q, context) {
    return {
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/search_bloggers/filter_panel.html'),
        restrict: 'A',
        controller: function($scope, $element, $attrs, $transclude) {
            $scope.doFilter = function(filters, fromSavedSearch){
                if ($scope.savedSearchLoaded)
                    $scope.savedQueries.selected.changed = true;
                if (filters !== undefined)
                    $scope.resetFilters(filters);
                filtersQuery.setQuery($scope.filters);
                $scope.$broadcast("setFilters", $scope.filters);
            };
        },
        link: function postLink(scope, iElement, iAttrs) {
            scope.debug = iAttrs.debug !== undefined;
            scope.acTimeout = null;
            scope.autocompleteBrandsQuery = null;
            scope.autocompleteBrandsTimeout = null;
            
            var minZero = ['engagement', 'social'];

            scope.categories = (function() {
                var available = [];
                var selected = [];
                var update = function() {};
                var remove = function() {};
                var value2Cat = {};

                function placeholder() {
                    return {
                        text: 'Select Categories',
                        value: null
                    }
                }

                function check() {
                    if (available.length !== cats.length) {
                        available = [];
                        for (var cat in cats) {
                            // available.push({text: cats[cat].title, value: cats[cat].category});
                            value2Cat[cats[cat].category] = {text: cats[cat].title, value: cats[cat].category};
                            available.push(value2Cat[cats[cat].category]);
                        }
                    }
                }

                function getAvailable() {
                    var a = [];

                    check();
                    
                    for (var cat in available) {
                        var found = false;
                        
                        for (var c in selected) {
                            if (available[cat].text === selected[c].text) {
                                found = true;
                                break;
                            }
                        }

                        if (!found) {
                            a.push(available[cat]);
                        }
                    }

                    return a;
                }

                function getApplied() {
                    var a = [];

                    for (var cat in selected) {
                        a.push(selected[cat].text);
                    }

                    return a;
                }

                function getCategoryByValue(value) {
                    return value2Cat[value];
                }
                
                return {
                    show: function() { return !!cats.length },
                    disabled: function() { return !this.show },
                    fetching: function() { return false },
                    available: getAvailable(),
                    selected: placeholder(),
                    selection: null,
                    update: function() {
                        if (this.selected.text !== placeholder().text) {
                            for (var cat in this.available) {
                                if (this.selected.text === this.available[cat].text) {
                                    if (typeof this.selected.value !== 'undefined' &&
                                        this.selected.value === this.available[cat].value) {
                                        this.selection = {
                                            text: this.selected.text,
                                            value: this.selected.value
                                        };
                                        selected.push(this.selection);
                                        this.applied = getApplied();
                                        this.selected = placeholder();
                                        this.available = getAvailable();
                                        update();
                                        break;
                                    }
                                }
                            }
                        }
                    },
                    remove: function(name) {
                        for (var cat in selected) {
                            if (name === selected[cat].text) {
                                selected.splice(cat, 1);
                                this.available = getAvailable();
                                this.applied = getApplied();
                                update();
                                break;
                            }
                        }
                    },
                    applied: getApplied(),
                    filters: function() {
                        var a = [];

                        for (var cat in selected) {
                            a.push(selected[cat].value);
                        }

                        return a;
                    },
                    reset: function(newSelected) {
                        selected = [];
                        if (newSelected !== undefined) {
                            for (var cat in newSelected) {
                                selected.push(getCategoryByValue(newSelected[cat]));
                            }
                        }
                        this.available = getAvailable();
                        this.applied = getApplied();
                    },
                    active: function() {
                        return (!!this.applied.length)
                    },
                    onUpdate: function(handler) {
                        update = handler;
                    }
                }
            }());
            
            angular.forEach(minZero, function(value) {
                angular.forEach(['min', 'max'], function(key) {
                    scope.$watch(value + '_' + key, function(newVal) {
                        if (newVal != 0 && (!newVal || newVal < 0)) {
                            scope[value + '_' + key] = null;
                        }
                    });
                });
                scope.$watch('filters.' + value, function(newValue) {
                    if (!newValue) {
                        scope[value + '_min'] = scope[value + '_max'] = null;
                    }
                });
            });
            
            scope.autocompleteBrands = function(){
                scope.brandsFetching = true;
                if(scope.autocompleteBrandsTimeout !== null){
                    scope.autocompleteBrandsTimeout.resolve();
                }
                scope.autocompleteBrandsTimeout = $q.defer();
                
                var do_animate = true;
                var animate = function(){
                    iElement.find(".brand_search_icon").animate({right: "10px"}, 250);
                    iElement.find(".brand_search_icon").animate({right: "5px"}, 250);
                    if(do_animate){
                        setTimeout(animate, 500);
                    }
                };
                animate();
                
                $http({
                    method: 'get',
                    url: iAttrs.brandAutocomplete,
                    params: {query: scope.autocompleteBrandsQuery},
                    timeout: scope.autocompleteBrandsTimeout.promise
                }).success(function(data){
                    scope.brands = data;
                    scope.updateNano();
                    scope.brandsFetching = false;
                    do_animate=false;
                }).error(function(){
                    scope.brandsFetching = false;
                    do_animate=false;
                });
            };
            
            scope.startAcTimeout = function(query){
                scope.autocompleteBrandsQuery = query;
                if(scope.acTimeout){
                    $timeout.cancel(scope.acTimeout);
                }
                if(scope.autocompleteBrandsQuery === null || scope.autocompleteBrandsQuery === undefined || scope.autocompleteBrandsQuery.length<1) {
                    scope.brands = brands;
                    return;
                }
                // if(scope.acTimeout){
                //   $timeout.cancel(scope.acTimeout);
                // }
                scope.acTimeout = $timeout(scope.autocompleteBrands, 500);
            };
            
            setTimeout(function() {
                $('.bs_tooltip').tooltip();
                var $sidebar = iElement,
                $window = $(window),
                sidebartop = iElement.position().top;
                
                $window.scroll(function() {
                    
                    if ($window.height() > $sidebar.height()) {
                        $sidebar.removeClass('fixedBtm');
                        if($sidebar.offset().top <= $window.scrollTop() && sidebartop <= $window.scrollTop()) {
                            $sidebar.addClass('fixedTop');
                        } else {
                            $sidebar.removeClass('fixedTop');
                        }
                    } else {
                        $sidebar.removeClass('fixedTop');
                        if ($window.height() + $window.scrollTop() > $sidebar.offset().top + $sidebar.height()+20) {
                            $sidebar.addClass('fixedBtm');
                        }
                        
                        if ($sidebar.offset().top < 0) {
                            $sidebar.removeClass('fixedBtm');
                        }
                    }
                    
                });
            }, 10);

            scope.tagsMapping = {};
            scope.pricerangesMapping = {};

            tags.forEach(function(tag) {
                scope.tagsMapping[tag.value] = tag.title;
            });

            priceranges.forEach(function(item) {
                scope.pricerangesMapping[item.title] = item.text;
            })

            scope.filterValue2Text = function(type, value) {
                var byValue = _.findWhere(scope[type], {value: value});
                if (byValue === undefined) // by title
                    return _.findWhere(scope[type], {title: value});
                return byValue;
            };

            scope.activityLevels = [
                {
                    text: 'last week',
                    value: 'ACTIVE_LAST_WEEK',
                }, {
                    text: 'last month',
                    value: 'ACTIVE_LAST_MONTH'
                }, {
                    text: 'last 3 months',
                    value: 'ACTIVE_LAST_3_MONTHS',
                }, {
                    text: 'last 6 months',
                    value: 'ACTIVE_LAST_6_MONTHS',
                }, {
                    text: 'last 1 year',
                    value: 'ACTIVE_LAST_12_MONTHS',
                }
            ];
            
            scope.activityLevelsDisplay = angular.copy(scope.activityLevels);
            
            scope.defaultRangeModels = {
                social: null,
                engagement: "",
            };
            
            scope.defaultTmpFilters = {
                social: null,
                engagement: {
                    value: ""
                },
            };
            
            scope.defaultChoiceModels = {
                activity: null
            };

            scope.resetFilters = function(filters){
                console.log('reset filters');
                scope.selectedActivityLevel = scope.activityLevels[2];
                if (filters !== undefined && filters.categories !== undefined && filters.categories.length > 0) {
                    scope.categories.reset(filters.categories);    
                } else {
                    scope.categories.reset();
                }
                scope.filters = {
                    //popularity: [],
                    engagement: null,
                    brand: [],
                    priceranges: [],
                    location: [],
                    gender: [],
                    social: null,
                    activity: null,
                    tags: [],
                    categories: scope.categories.applied
                };
                
                if (context.isSuperuser) {
                    scope.filters['popularity'] = [];
                    scope.popularity = popularity;
                }

                scope.rangeModels = angular.copy(scope.defaultRangeModels);
                scope.tmpFilters = angular.copy(scope.defaultTmpFilters);
                scope.choiceModels = angular.copy(scope.defaultChoiceModels);
                
                if (filters !== undefined) {
                    // deep copy
                    for (var filter in filters)
                        scope.filters[filter] = angular.copy(filters[filter]);
                    if (filters['social']) {
                        scope.rangeModels['social'] = angular.copy(filters['social']);
                        scope.tmpFilters['social'] = angular.copy(filters['social']);
                        scope.social_min = scope.rangeModels['social'].range_min;
                        scope.social_max = scope.rangeModels['social'].range_max;
                    }
                    if (filters['engagement']) {
                        scope.rangeModels['engagement'] = angular.copy(filters['engagement']);
                        scope.tmpFilters['engagement'] = angular.copy(filters['engagement']);
                        scope.engagement_min = scope.rangeModels['engagement'].range_min;
                        scope.engagement_max = scope.rangeModels['engagement'].range_max;
                    }
                    if (filters['activity']) {
                        scope.choiceModels['activity'] = angular.copy(filters['activity']);
                        scope.selectedActivityLevel = _.findWhere(
                            scope.activityLevels,
                            {value: scope.choiceModels['activity'].activity_level});
                    }
                }
            };

            if (scope.filters === undefined) {
                scope.resetFilters();
            }

            scope.resetFiltersDefer.resolve();

            scope.toggledFilters = {};
            _.keys(scope.filters).forEach(function(filter) {
                scope.toggledFilters[filter] = false;
            });

            scope.toggledByDefault = [
                'engagement', 'socials', 'categories', 'locations', 'tags'];
            scope.toggledByDefault.forEach(function(filter) {
                scope.toggledFilters[filter] = false;
            });

            scope.metaModeFiltersDisabled = {
                'main_search': [], // all,
                'instagram_search': ['locations', 'priceranges', 'categories', 'genders']
            };

            scope.shouldShowFilter = function(filter) {
                // if (scope.andOrFilterOn && !scope.kwExpr.canFetch())
                //     return false;
                if (!scope.navigation.config)
                    return true;
                var disabled = scope.metaModeFiltersDisabled[scope.navigation.config.sub_tab];
                if (disabled)
                    return disabled.indexOf(filter) < 0;
                return true;
            };

            scope.toggleFilter = function(filter) {
                scope.toggledFilters[filter] = !scope.toggledFilters[filter];
                scope.updateNano();
            };
            
            // scope.popularity = popularity;
            scope.priceranges = priceranges;
            scope.brands = brands;
            scope.locations = locations;
            scope.genders = genders;
            scope.socials = socials;
            scope.activity = activity;
            scope.tags = tags;
            scope.filterTimeout = null;
            
            scope.startFilteringTimeout = function(){
                if(scope.filterTimeout){
                    $timeout.cancel(scope.filterTimeout);
                }
                scope.filterTimeout = $timeout(scope.doFilter, 2000);
            };
            
            scope.hasFilters = function(){
                var resp = false;
                if(scope.filters.popularity && scope.filters.popularity.length>0) resp = true;
                else if(scope.filters.engagement) resp = true;
                else if(scope.filters.brand.length>0) resp = true;
                else if(scope.filters.priceranges.length>0) resp = true;
                else if(scope.filters.location.length>0) resp = true;
                else if(scope.filters.tags.length>0) resp = true;
                else if(scope.filters.gender.length>0) resp = true;
                else if(scope.filters.social) resp = true;
                else if(scope.filters.activity) resp = true;
                //else if(scope.keyword) resp = true;
                else if(scope.categories.active()) resp = true;
                scope.$emit("hasFilterSet", resp);
                return resp;
            };
            
            scope.clearAllFilters = function(){
                scope.resetFilters();
                if(scope.filterTimeout){
                    $timeout.cancel(scope.filterTimeout);
                }
                scope.filterTimeout = $timeout(scope.doFilter, 2000);
            };
            
            scope.toggleTypeFilter = function(type, value){
                var index = scope.filters[type].indexOf(value);
                if(index>=0){
                    scope.filters[type].splice(index, 1);
                }else{
                    scope.filters[type].push(value);
                }
                scope.startFilteringTimeout();
            };

            scope.categories.onUpdate(function() {
                scope.filters['categories'] = scope.categories.filters();
                scope.startFilteringTimeout();
            });
            
            scope.clearRangeFilter = function(type){
                scope.filters[type] = null;
                scope.startFilteringTimeout();
            };
            
            scope.toggleRangeFilter = function(type, value, range_min, range_max){
                if(value){
                    if(scope.tmpFilters[type] !== null && scope.tmpFilters[type].value == value){
                        scope.tmpFilters[type] = null;
                        scope.rangeModels[type] = null;
                    }else{
                        scope.tmpFilters[type] = {
                            value: value,
                            range_min: range_min,
                            range_max: range_max,
                        }
                        scope.rangeModels[type] = value;
                    }
                }else{
                    scope.tmpFilters = angular.copy(scope.defaultTmpFilters);
                    scope.rangeModels[type] = null;
                }
                if(range_min !== null && range_min !== undefined && range_max !== null && range_max !== undefined){
                    scope.applyRangeFilter(type);
                }
            };
            
            scope.toggleChoiceFilter = function(type, value, choice) {
                if (type == 'activity') {
                    scope.filters[type] = {
                        platform: value,
                        activity_level_text: choice.text,
                        activity_level: choice.value,
                    };
                    scope.startFilteringTimeout();
                }
            };

            scope.toggleActivityFilter = function(selected) {
                if (selected)
                    scope.selectedActivityLevel = selected;
                scope.toggleChoiceFilter('activity', scope.choiceModels['activity'], scope.selectedActivityLevel);
            };
            
            scope.updateChoiceFilter = function(type) {
                
            };
            
            scope.updateRangeFilter = function(type, range_min, range_max){
                if(Number(range_min) > Number(range_max)){
                    range_min = range_max;
                }
                if(scope.tmpFilters[type]){
                    scope.tmpFilters[type] = {
                        value: scope.tmpFilters[type].value,
                        range_min: range_min,
                        range_max: range_max,
                    }
                    if(range_min !== null && range_min !== undefined &&
                       range_max !== null && range_max !== undefined){
                        scope.applyRangeFilter(type);
                    }
                }
            };
            
            scope.applyRangeFilter = function(type){
                scope.filters[type] = scope.tmpFilters[type];
                scope.startFilteringTimeout();
            };
            
            scope.hasTypeFilter = function(type, value){
                var index = scope.filters[type].indexOf(value);
                if(index>=0){
                    return true;
                }else{
                    return false;
                }
            };
            
            scope.updateNano = function(){
                setTimeout(function() {
                    $(".nano").nanoScroller({alwaysVisible: true});
                    $(".nano").nanoScroller({ scroll: 'top' });
                }, 100);
            };
            
            scope.canFilter = function(name){
                return enabled_filters.indexOf(name)>=0;
            };

            scope.showAllLocations = true;
            scope.showAllTags = true;
            
            scope.$watch('locationsSearch', scope.updateNano);
            scope.$watch('tagsSearch', scope.updateNano);
            scope.updateNano();
        }
    };
}])

.directive('bloggerContainer', ['$http', '$compile', '$sce', '$q',
                                    '$location', '$timeout',
                                    'keywordQuery', 'tsQueryCache', 'tsQuerySort',
                                    'tsQueryResult', 'context', 'filtersQuery',
                                    function ($http, $compile, $sce, $q, $location,
                                      $timeout, keywordQuery,
                                      tsQueryCache, tsQuerySort, tsQueryResult,
                                      context, filtersQuery) {
    return {
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/search_bloggers/container.html'),
        restrict: 'A',
        replace: true,
        controller: function($scope, $element, $attrs, $transclude) {
            $scope.page = 1;
            $scope.grid_scope = null;
            $scope.pages1 = [];
            $scope.pages2 = [];
            $scope.pages3 = [];
            $scope.current_filters = {
                popularity: [],
                engagement: [],
                brand: [],
                priceranges: [],
                gender: [],
                tags: [],
            };
            
            $scope.current_name_filters = null;
            $scope.current_keyword_filters = null;
            $scope.current_keyword_filter_type = null;
            $scope.active = true;
            
            // $scope.$watch('mode', function(){
            //     if($scope.mode == 'bloggers' || $scope.mode === undefined){
            //         $scope.active = true;
            //     }else{
            //         $scope.active = false;
            //     }
            // });

            $scope.context = context;
            
            $scope.cancelDefer = null;

            $scope.doFetchBloggers = function() {

                if($scope.cancelDefer !== null)
                    $scope.cancelDefer.resolve();
                $scope.cancelDefer = null;

                if ($scope.andOrFilterOn && !$scope.kwExpr.canFetch())
                    return;

                if (!$scope.active) {
                    $scope.doFetchPosts();
                    return;
                }

                if ($scope.remaining === 0 && $scope.has_pages === false)
                    return;

                $scope.cancelDefer = $q.defer();

                console.log("do search bloggers");

                $scope.loading = true;
                $scope.populatePageInfo(null);
                $scope.page = Number($scope.page);
                if(isNaN($scope.page) || $scope.page < 1) {
                    $scope.page = 1;
                }
                $scope.clearSalvattore();
                $scope.state = "ok";

                var query_data = {
                    filters: $scope.current_filters,
                    keyword: $scope.current_keyword_filters,
                    type: $scope.current_keyword_filter_type,
                    keyword_types: $scope.keyword_types,
                    groups: $scope.groups,
                    group_concatenator: $scope.concatenationTypeSelected.value,
                    page: $scope.page,
                    order_by: tsQuerySort.get('keyword'),
                    and_or_filter_on: $scope.andOrFilterOn,
                    sub_tab: $scope.navigation.config.sub_tab,
                };

                var retry_timeout = $timeout(function(){
                    if($scope.cancelDefer !== null){
                        $scope.cancelDefer.resolve();
                        $scope.cancelDefer = null;
                        $scope.doFetchBloggers();
                        console.log("timeouted!");
                    }
                }, 20000);

                $http({
                    url: '/search/bloggers/json',
                    method: 'POST',
                    data: query_data,
                    timeout: $scope.cancelDefer.promise
                }).success(function (data) {
                    console.log("search finished");

                    $scope.cancelDefer = null;
                    $timeout.cancel(retry_timeout);

                    tsQueryCache.set(query_data);
                    tsQueryResult.set({
                      total: data.total_influencers,
                      results: data.results
                    });

                    if(data.results == undefined || data.results.length == 0){
                        $scope.state = "no results";
                    }

                    $scope.bloggers = data.results;

                    $scope.id_to_blogger = {};

                    for (var i = 0; i < $scope.bloggers.length; i++) {
                        $scope.bloggers[i].selected = false;
                        $scope.id_to_blogger[$scope.bloggers[i].id] = $scope.bloggers[i];
                    }

                    $scope.pages1 = [];
                    $scope.pages2 = [];
                    $scope.pages3 = [];

                    if($scope.page >= data.pages){
                        $scope.page = data.pages;
                    }
                    var i = 0;
                    for(i; i<data.pages && i<3; i++)
                        $scope.pages1.push(i+1);
                    for(i = Math.max($scope.page-3, i); i<data.pages && i<$scope.page+2; i++)
                        $scope.pages2.push(i+1);
                    for(i = Math.max(data.pages-3, i); i<data.pages; i++)
                        $scope.pages3.push(i+1);
                    angular.forEach($scope.bloggers, function (item, index) {
                        item.blogname = $sce.trustAsHtml(item.blogname);
                        item.index = index;
                    });
                    
                    $scope.remaining = data.remaining;
                    $scope.remaining_debug = data.remaining_debug;
                    $scope.query_limited = data.query_limited;
                    $scope.total_influencers = data.total_influencers;
                    $scope.updateSalvattore(data);
                    $timeout(function(){
                        $scope.loading = false;
                    },100);
                    $scope.has_pages = data.pages !== undefined;
                    var page_info = {
                        total: $scope.total_influencers,
                    };
                    if($scope.total_influencers){
                        page_info["sliceStart"] = Math.max(1, data.slice_size*($scope.page-1)+1)
                        page_info["sliceEnd"] = Math.min($scope.total_influencers, data.slice_size*$scope.page)
                    }else{
                        page_info["sliceStart"] = 0;
                        page_info["sliceEnd"] = 0;
                    }
                    $scope.populatePageInfo(page_info);
                })
                .error(function(a, b, c, d){
                    if(a == "limit"){
                        $scope.state = "limit";
                    }
                });
            };

            $scope.setPage = function(page_no){
                if($scope.pages1.indexOf(page_no)<0 &&
                   $scope.pages2.indexOf(page_no)<0 &&
                   $scope.pages3.indexOf(page_no)<0 ){
                    return;
                }
                // if($scope.active){
                $scope.page = isNaN(page_no) ? 1 : page_no;
                $scope.setUrl();
                $timeout($scope.handlePath, 500);
                //}
            };
            // $scope.$on('$locationChangeSuccess', function(){
            //     return;
            //     var hash = Number($location.path().substr(1)), mode = null;
            //     if (isNaN(hash)) {
            //         mode = $location.path().substr(1).split('/')[0];
            //         hash = $location.path().substr(1).split('/')[1];
            //         if (mode && $scope.active) {
            //             $scope.mode_selected = _.findWhere($scope.modes, {url: mode});
            //             $scope.updateMode(true);
            //         }
            //     }
            //     if($scope.page != hash){
            //         $scope.page = hash;
            //         if(isNaN($scope.page)){
            //             $scope.page = 1;
            //             if($scope.active){
            //                 $location.path($scope.mode_selected.url + '/' + $scope.page);
            //             }
            //         }
            //         $scope.doFetchBloggers();
            //     }
            // });
            $scope.$on("setFilters", function(their_scope, filters){
                $scope.current_filters = angular.copy(filters);
                $scope.page = 1;
                $scope.doFetchBloggers();
            });
            $scope.$on("setKeywordFilters", function(their_scope, filters, type, doNotFetch, keyword_types){
                if(filters.value !== undefined){
                    $scope.current_keyword_filters = angular.copy(filters.value);
                }else{
                    $scope.current_keyword_filters = angular.copy(filters);
                }
                $scope.current_keyword_filter_type = type;
                $scope.page = 1;
                if (doNotFetch !== true) {
                    $scope.doFetchBloggers();
                }
            });
            $scope.$on("reloadFeeds", function(){
                console.log('reload feeds');
                $scope.doFetchBloggers();
            });
        },
        link: function postLink(scope, iElement, iAttrs) {
            scope.initialDefer = $q.defer();
            scope.salvattore_registered = $q.defer();
            scope.pricing_url = iAttrs.pricingUrl;
            scope.clearSalvattore = function () {
                var grid = iElement.find('.salvattore_grid');
                grid.children().remove();
                $("html, body").animate({ scrollTop: 0 }, 200);
            };
            scope.updateSalvattore = function () {
                var grid = iElement.find('.salvattore_grid');
                var element;
                var options = "";
                if(iAttrs.bookmarks !== undefined){
                    options += "bookmarks ";
                }
                grid.css({opacity: 0});
                angular.forEach(scope.bloggers, function (item) {
                    element = '<div blogger-info user="bloggers[' + item.index + ']" '+options+'></div>';
                    grid.append(element);
                });
                if(scope.grid_scope){
                    scope.grid_scope.$destroy();
                }
                scope.grid_scope = scope.$new();
                $compile(grid)(scope.grid_scope);
                var add_salvattore_inner = function (){
                    try{
                        salvattore.register_grid(iElement.find('.salvattore_grid')[0]);
                        scope.salvattore_registered.resolve();
                    }catch(e){
                        $timeout(add_salvattore_inner, 150);
                        return;
                    }
                    grid.css({opacity: 1});
                };
                $timeout(add_salvattore_inner, 150);
            };
            // $timeout(function(){
            //     scope.resetFiltersDefer.promise.then(function() {
            //         // scope.resetFilters();
            //         if (iAttrs.tag !== undefined) {
            //             scope.filters.tags.push(iAttrs.tag);
            //             scope.current_filters.tags.push(iAttrs.tag);
            //             filtersQuery.setQuery(scope.filters);
            //         }
            //         if (iAttrs.svdSearch !== undefined) {
            //             scope.toggleSavedQuery(
            //                 _.findWhere(scope.savedQueries.options, {value: parseInt(iAttrs.svdSearch)})
            //             );
            //         }
            //         var query = keywordQuery.getQuery();
            //         if(query){
            //             scope.current_keyword_filters = query.query;
            //             scope.current_keyword_filter_type = query.type;
            //         };
            //         scope.initialDefer.promise.then(scope.handlePath);
            //     });
            // }, 500);
            scope.initialDefer.promise.then(scope.handlePath);
        }
    };
}])


.directive('bloggerInfo', ['$http', '$rootScope', '$interpolate', 'context', 'debug', 'tsInvitationMessage', function ($http, $rootScope, $interpolate, context, debug, tsInvitationMessage) {
    return {
        restrict: 'A',
        scope: {
          'user': '=',
        },
        replace: true,
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/search_bloggers/blogger_info.html'),
        link: function (scope, iElement, iAttrs) {
            scope.has_collections_in = !_.isEmpty(scope.user.collections_in);
            scope.debug = debug;
            scope.context = context;
            scope.bookmarks = iAttrs.bookmarks !== undefined;     
            setTimeout(function() {
                $('.bs_tooltip').tooltip();
            }, 10);

            scope.$on('user-collections-in-changed', function(their_scope, data) {
                if (scope.user.id == data.id) {
                    scope.has_collections_in = data.has_collections_in;
                    scope.user = angular.extend(scope.user, {
                        collections_in: data.collections_in
                    });
                }
            });

            scope.toggle_follow = function(){
                scope.user.can_follow = false;
                $http.get(scope.user.follow_url).success(function(){
                    scope.user.can_follow = true;
                    if(scope.user.is_following){
                        scope.user.is_following = false;
                    }else{
                        scope.user.is_following = true;
                    }
                });
            };

            scope.openFavoritePopup = function(options){
                //calling parent because of scope isolation
                scope.$parent.doOpenFavoritePopup(options);
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
                $rootScope.$broadcast("openInvitationPopup", options);
            };
        }
    };
}])


.directive('mixedAutocompleteInput', ['$timeout', '$http', '$location', 'keywordQuery',
                                        '$rootScope', '$q', '$document',
                                        'tsQueryCache', 'tsQuerySort', 'filtersQuery',
                                        function($timeout, $http, $location, keywordQuery, $rootScope,
                                          $q, $document, tsQueryCache, tsQuerySort, filtersQuery) {
        var should_autocomplete = function(type) {
            return false;
            // return ["name", "blogname", "blogurl", "location"].indexOf(type) >= 0;
        };
        return {
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/mixed_search_autocomplete_input.html'),
            replace: true,
            restrict: 'A',
            // scope: true,
            controller: function($scope, $element, $attrs, $transclude) {
                if ($attrs.autocompleteUrl)
                    $scope.autocompleteUrl = $attrs.autocompleteUrl;
                $scope.autocompleteTimeout = null;
                $scope.searchTimeout = null;
                $scope.cancelDefer = null;
                $scope.open = false;
                var lockAutocompleteTimeout = false;
                $scope.keyword = null;
                $scope.options = [];
                $scope.type = 'all';
                $scope.keywords = [];
                $scope.keyword_types = [];
                $scope.kw_index = 0;
                $scope.andOrFilterOn = $scope.context.andOrFilterOn;

                $scope.$watch('andOrFilterOn', function(newValue, oldValue) {
                    if (newValue) {
                        $scope.types = [
                            {value: "all", text:"All", toggled: true, extra: false},
                            //{value: "keyword", text:"Keywords"},
                            // {value: "brand", text:"Brand URL", extra: false},
                            {value: "post_hashtag", text: "#", extra: false},
                            {value: "post_mention", text: "@", extra: false},
                            {value: "post_content", text: "Post Content", extra: true},
                            {value: "post_title", text: "Post Title", extra: true},
                            // {value: "location", text:"Location", extra: true},
                            // {value: "blogname", text:"Blog Name", extra: true},
                            // {value: "blogurl", text:"Blog URL", extra: true},
                            // {value: "name", text:"Name", extra: true}
                        ];
                    } else {
                        $scope.types = [
                            {value: "all", text:"All", toggled: true, extra: false, isPostType: false},
                            //{value: "keyword", text:"Keywords"},
                            {value: "brand", text:"Brand URL", extra: false, isPostType: false},
                            {value: "hashtag", text: "#", extra: false, isPostType: true},
                            {value: "mention", text: "@", extra: false, isPostType: true},
                            // {value: "location", text:"Location", extra: true},
                            {value: "blogname", text:"Blog Name", extra: true, isPostType: false},
                            {value: "blogurl", text:"Blog URL", extra: true, isPostType: false},
                            {value: "name", text:"Name", extra: true, isPostType: false}
                        ];
                    }

                    $scope.value2Type = {};
                    angular.forEach($scope.types, function(item) {
                        $scope.value2Type[item.value] = item;
                    });
                });

                $scope.concatenationTypes = [
                    // {value: 'or', text: 'OR'},
                    {value: 'and_same', text: 'SAME POST'},
                    {value: 'and_across', text: 'ANY POST'},
                ];

                $scope.operatorIndices = [1, 3, 6];

                $scope.groups = [];
                $scope.groupsNumber = 0;

                $scope.newKeywords = [];

                $scope.isInfluencerTypeSelected = false;

                $scope.concatenationTypeSelected = $scope.concatenationTypes[0];

                $scope.showExtraTypes = false;

                $scope.value2Type = {};
                angular.forEach($scope.types, function(item) {
                    $scope.value2Type[item.value] = item;
                });

                $scope.updateConcatenationType = function(typeSelected) {
                    if ($scope.loading)
                        return;
                    $scope.concatenationTypeSelected = typeSelected;
                    if ($scope.kwExpr.showOnFiltersPanel())
                        $scope.kwExpr.isDone = false;
                };
                
                $scope.updateType = function(type_selected, doNotFetch){
                    if (type_selected) {
                        $scope.type_selected = type_selected;
                        angular.forEach($scope.types, function(type) {
                            type.toggled = false;
                        });
                        $scope.type_selected.toggled = true;
                    }
                    $scope.type = $scope.type_selected.value;

                    // NOT USED FOR NOW (AUTOCOMPLETE IS OFF)
                    // if (should_autocomplete($scope.type)) {
                    //     $scope.startAutocompleteTimeout();
                    // }

                };

                $scope.sorting = tsQuerySort.selector('keyword');

                $scope.setKeyword = function(keyword, type) {
                    var keywords = Array.isArray(keyword) ? angular.copy(keyword) : [keyword];

                    keywords = keywords.filter(function(kw) {
                        return kw && kw.length > 0;
                    });

                    keywordQuery.setQuery(keywords, type);

                    $scope.keyword = keywords;
                    $scope.kw_index = keywords.length;
                    $scope.type = type || $scope.types[0].value;
                };
                
                $scope.search = function(keyword, type, doNotFetch) {
                    $scope.setKeyword(keyword, type);

                    $scope.savedQueries.selected.changed = $scope.savedSearchLoaded;

                    $scope.open = false;

                    $rootScope.$broadcast("setKeywordFilters", $scope.keyword, $scope.type, doNotFetch, $scope.keyword_types);
                    lockAutocompleteTimeout = true;
                    $timeout(function(){
                        lockAutocompleteTimeout = false;
                    }, 250);
                };
                
                $scope.doAutocomplete = function() {
                    $scope.options = [];
                    $scope.open = false;
                    if($scope.cancelDefer !== null)
                        $scope.cancelDefer.resolve();
                    if ($scope.searchKeyword === null || $scope.searchKeyword === undefined || $scope.searchKeyword.length === 0) {
                        return;
                    }
                    $scope.cancelDefer = $q.defer();
                    $scope.loading = true;

                    $http({
                        method: 'get',
                        params: {
                            query: [$scope.searchKeyword],
                            type: $scope.type,
                        },
                        url: $scope.autocompleteUrl,
                        timeout: $scope.cancelDefer.promise
                    }).success(function(options) {
                        $scope.options = options;
                        $scope.loading = false;
                        if(options.length > 0){
                            $scope.open = true;
                        }
                    }).error(function() {});
                };
                function sort_changed () {
                    var sort = false;
                    var cached = tsQueryCache.get();
                    var current = tsQuerySort.get('keyword');

                    if (cached !== null) {
                        for (var opt in current) {
                            if (typeof cached[opt] !== 'undefined') {
                                if (cached[opt] != current[opt]) {
                                    sort = true;
                                    break;
                                }
                            } else {
                                sort = true;
                            }
                        }
                    } else {
                        if (current.field !== null) {
                            sort = true;
                        }
                    }

                    return sort;
                }
                $scope.startSearchTimeout = function(options){
                    $scope.keyword = [];
                    
                    for (var kw in $scope.keywords) {
                        if ($scope.keywords[kw].length > 0) {
                            $scope.keyword.push($scope.keywords[kw]);
                        }
                    }
                    
                    if ($scope.searchTimeout) {
                        $timeout.cancel($scope.searchTimeout);
                    }
                    $scope.searchTimeout = $timeout(function() {
                        $scope.search($scope.keyword, $scope.type);
                    }, options && options.isInstant ? 0 : 2000);
                };

                $scope.startAutocompleteTimeout = function() {
                    if (!should_autocomplete($scope.type))
                        return;
                    if (lockAutocompleteTimeout === true)
                      return;
                    if ($scope.autocompleteTimeout) {
                        $timeout.cancel($scope.autocompleteTimeout);
                    }
                    $scope.autocompleteTimeout = $timeout($scope.doAutocomplete, 500);
                }

                $scope.switchKeywordMode = function(advancedOn) {
                    if ($scope.isInsideSavedQuery() || $scope.loading)
                        return;
                    if (advancedOn && !$scope.andOrFilterOn) {
                        // regular => advanced
                        $scope.regularKeywordData.keywords = angular.copy($scope.keyword);
                        $scope.regularKeywordData.keywordTypes = angular.copy($scope.keyword_types);
                        $scope.regularKeywordData.kwIndex = $scope.kwIndex;
                        $scope.kwExpr.runSearch();
                    } else if (!advancedOn && $scope.andOrFilterOn) {
                        // advanced => regular
                        $scope.keywords = angular.copy($scope.regularKeywordData.keywords);
                        $scope.keyword = angular.copy($scope.regularKeywordData.keywords);
                        $scope.keyword_types = $scope.regularKeywordData.keywordTypes;
                        $scope.kwIndex = $scope.regularKeywordData.kwIndex;
                        $scope.startSearchTimeout({isInstant: true});
                    }
                    $scope.andOrFilterOn = advancedOn;
                };

                $scope.regularKeywordData = {
                    keywords: [],
                    keywordTypes: [],
                    kwIndex: 0,
                };

                $scope.kwExpr = {
                    groups: [],
                    finished: false,
                    isDone: true,
                    setDone: function() {
                        $scope.kwExpr.isDone = true;
                    },
                    getNextTabIndex: function(group) {
                        var sum = 0;
                        for (var i = 0; $scope.kwExpr.groups[i] != group; i++)
                            sum += $scope.kwExpr.groups[i].keywords.length;
                        return  sum + group.keywords.length + 1;
                    },
                    canFetch: function() {
                        if ($scope.loading)
                            return true;
                        return $scope.kwExpr.isDone;
                    },
                    showOnFiltersPanel: function() {
                        if (!$scope.andOrFilterOn)
                            return false;
                        if ($scope.kwExpr.groups.length === 0)
                            return false;
                        if ($scope.kwExpr.groups[0].keywords.length === 0)
                            return false;
                        if ($scope.kwExpr.groups[0].keywords[0].value.length === 0)
                            return false;
                        return true;
                    },
                    addGroup: function() {
                        var group = {
                            keywords: [],
                        };
                        $scope.kwExpr.groups.push(group);
                        $scope.kwExpr.addKeyword(group);
                        return group;
                    },
                    removeGroup: function(index) {
                        $scope.kwExpr.groups.splice(index, 1);
                    },
                    addKeyword: function(group, kw) {
                        kw = kw ||  {
                            value: "",
                            type: "all",
                        };
                        group.keywords.push(kw);
                    },
                    removeKeyword: function(group, index) {
                        group.keywords.splice(index, 1);
                        if (group.keywords.length == 1 && $scope.kwExpr.groups.length > 1) {
                            $scope.kwExpr.removeGroup($scope.kwExpr.groups.indexOf(group));
                        }
                        $scope.kwExpr.isDone = !$scope.kwExpr.showOnFiltersPanel();
                        if ($scope.kwExpr.isDone && $scope.hasFilters())
                            $scope.kwExpr.runSearch();
                    },
                    onChange: function(options) {
                        if (options.last && options.kw.value.length > 0)
                            $scope.kwExpr.addKeyword(options.group);
                        else if (!options.last && options.kw.value.length == 0)
                            $scope.kwExpr.removeKeyword(options.group, options.index);
                        $scope.kwExpr.isDone = !$scope.kwExpr.showOnFiltersPanel();
                    },
                    onBlur: function(options) {
                        if (options.kw.value.length == 0) {
                            if (!options.last)
                                $scope.kwExpr.removeKeyword(options.group, options.index);
                        }
                    },
                    onTypeChange: function(selected) {
                        if ($scope.kwExpr.showOnFiltersPanel())
                            $scope.kwExpr.isDone = false;
                    },
                    runSearch: function() {
                        var keywords = [];
                        var groups = [];
                        var keywordTypes = [];
                        var kwIndex = 0;
                        var i = 0;
                        while ($scope.kwExpr.groups.length > 1 && i < $scope.kwExpr.groups.length) {
                            if ($scope.kwExpr.groups[i].keywords.length < 2)
                                $scope.kwExpr.removeGroup(i);
                            else
                                i++;
                        }
                        $scope.kwExpr.groups.forEach(function(group, index) {
                            group.keywords.forEach(function(kw) {
                                if (kw.value.length > 0) {
                                    kwIndex++;
                                    keywords.push(kw.value);
                                    groups.push(index);
                                    keywordTypes.push(kw.type.value || kw.type);
                                }
                            });
                        })
                        $scope.keywords = keywords;
                        $scope.groups = groups;
                        $scope.kwIndex = kwIndex;
                        $scope.keyword_types = keywordTypes;
                        $scope.kwExpr.setDone();
                        $scope.startSearchTimeout({isInstant: true});
                    },
                    loadSavedExpression: function() {
                        var values = _.zip($scope.keywords, $scope.keyword_types, $scope.groups);
                        var groups = {}, group, prevGroup;
                        $scope.kwExpr.groups.splice(0, $scope.kwExpr.groups.length)

                        values.forEach(function(item, index) {
                            group = groups[item[2]];
                            if (group === undefined) {
                                groups[item[2]] = group = $scope.kwExpr.addGroup();
                                group.keywords = [];
                                if (prevGroup)
                                    $scope.kwExpr.addKeyword(prevGroup);
                            }
                            $scope.kwExpr.addKeyword(group, {
                                value: item[0],
                                type: item[1]
                            });
                            prevGroup = group;
                        });
                        if (prevGroup)
                            $scope.kwExpr.addKeyword(prevGroup);

                        $scope.kwExpr.setDone();
                    },
                    clear: function() {
                        $scope.kwExpr.groups.splice(0, $scope.kwExpr.groups.length);
                        $scope.kwExpr.addGroup();
                    }
                };

                $scope.kwExpr.addGroup();

                $scope.showAppliedKeywords = function() {
                    if ($scope.andOrFilterOn)
                        return $scope.kwExpr.showOnFiltersPanel();
                    else
                        return $scope.keyword && $scope.keyword.length > 0;
                };

                $scope.showAppliedFilters = function() {
                    return $scope.hasFilters() || $scope.showAppliedKeywords();
                };

                $scope.add_or_element = function(value) {
                    if (!$scope.type_selected)
                        return;
                    if (value !== undefined)
                        $scope.searchKeyword = angular.copy(value);
                    if ($scope.searchKeyword && $scope.searchKeyword.length > 0) {
                        $scope.keywords[$scope.kw_index] = angular.copy($scope.searchKeyword);
                        $scope.kw_index++;
                        $scope.searchKeyword = "";
                        $scope.keyword_types.push(angular.copy($scope.type_selected.value));
                        $scope.groups.push($scope.groupsNumber);
                        $scope.startSearchTimeout({isInstant: true});
                    }
                };

                $scope.$on('resetSearch', function(their_scope, options) {
                    if (options && options.resetMode) {
                        $scope.mode_selected = $scope.modes[0];
                        $scope.updateMode(true);
                    }
                    $scope.getBackToBasicSearch();
                });

                // NOT USED FOR NOW (AUTOCOMPLETE IS OFF)
                // $scope.$watch('searchKeyword', function(nv, ov) {
                //     if (nv !== ov) {
                //         $scope.startAutocompleteTimeout();
                //     }
                // });
                // $scope.$watch('keywords', function(nv, ov) {
                //     if (nv.length >= ov.length) {
                //         for (var v in nv) {
                //             if (typeof ov[v] === 'undefined') {
                //                 if (nv[v].length !== 0) {
                //                     $scope.startAutocompleteTimeout();
                //                     break;
                //                 }
                //             } else {
                //                 if (ov[v] !== nv[v]) {
                //                     $scope.startAutocompleteTimeout();
                //                     break;
                //                 }
                //             }
                //         }
                //     } else {
                //         for (var v in ov) {
                //             if (nv.length <= v) {
                //                 if (ov[v].length !== 0) {
                //                     $scope.startAutocompleteTimeout();
                //                     break;
                //                 }
                //             } else {
                //                 if (nv[v] !== ov[v] && ov[v].length === 0) {
                //                     var diff = false;
                //                     var v = Number(v);
                                    
                //                     for (var i = 0; i + v + 1 < ov.length; i++) {
                //                         if (nv[v + i] !== ov[v + i + 1]) {
                //                             diff = true;
                //                             break;
                //                         }
                //                     }
                                    
                //                     if (diff) {
                //                         $scope.startAutocompleteTimeout();
                //                     }
                                    
                //                     break;
                //                 }
                //             }
                //         }
                //     }
                // }, true);
                
                $scope.sorting.onSelect($scope.startSearchTimeout);
                
                $scope.remove_or_element = function(index) {
                    $scope.keywords.splice(index, 1);
                    $scope.groups.splice(index, 1);
                    $scope.kw_index = $scope.keywords.length;
                    if ($scope.kw_index === 0) {
                        $scope.updateType($scope.types[0], true);
                        $scope.setUrl(1);
                    }
                    if ($scope.keyword_types.length > 0)
                        $scope.keyword_types.splice(index, 1);

                    $scope.startSearchTimeout();
                };

                $scope.show_remove = function() {
                    return $scope.keywords.length > 1 ? true : false;
                };

                $scope.handlePath = function() {
                    console.log('handle path');
                    // main/search/#/<section>/<page>
                    // main/search/#/tag/<tag_id>/<section>/<page>
                    // main/search/#/saved_search/<ss_id>/<section>/<page>
                    if (!$scope.urlChangedManually) {
                        $scope.urlChangedManually = true;
                        return;
                    }

                    var parts = function() {

                        var isCorrect = true;
                        var splittedUrl = $location.path().substr(1).split('/');
                        var isSavedSearch = splittedUrl[0] === 'saved_search';
                        var savedSearchID = isSavedSearch ? Number(splittedUrl[1]) : null;
                        var savedSearch = null;
                        var isTag = splittedUrl[0] === 'tag';
                        var tagID = isTag ? Number(splittedUrl[1]) : null;
                        var modeName = splittedUrl[isSavedSearch || isTag ? 2 : 0];
                        var page = Number(splittedUrl[isSavedSearch || isTag ? 3 : 1]);
                        var mode = null;

                        if (isSavedSearch) {
                            if (isNaN(savedSearchID))
                                isCorrect = false;
                            else {
                                savedSearch = _.findWhere($scope.savedQueries.options, {value: savedSearchID});
                                if (savedSearch === null)
                                    isCorrect = false;
                            }
                        }

                        if (isTag && isNaN(tagID)) {
                            isCorrect = false;
                        }

                        mode = _.findWhere($scope.modes, {url: modeName});
                        if (mode === null)
                            isCorrect = false;

                        if (isNaN(page))
                            isCorrect = false;

                        return {
                            isSavedSearch: isSavedSearch,
                            savedSearch: savedSearch,
                            isTag: isTag,
                            tagID: tagID,
                            mode: mode,
                            page: page,
                            isCorrect: isCorrect
                        };

                    }();

                    if (!parts.isCorrect) {
                        // handle incorrect url
                        $location.path($scope.modes[0].url + '/1');
                        return;
                    }

                    $scope.page = parts.page;
                    $scope.mode_selected = parts.mode;
                    $scope.updateMode(true, true);

                    if (parts.isSavedSearch && !$scope.insideSavedSearch) {
                        $scope.toggleSavedQuery(parts.savedSearch);
                    } else if (parts.isTag) {
                        $scope.filters.tags.push(parts.tagID);
                        $scope.current_filters.tags.push(parts.tagID);
                        filtersQuery.setQuery($scope.filters);
                    } else {
                        $scope.reloadFeeds();
                    }
                };

                $scope.initialDefer.resolve();

                $scope.$on('$locationChangeSuccess', $scope.handlePath);
            },
            link: function postLink(scope, iElement, iAttrs) {
                // NOT USED FOR NOW (AUTOCOMPLETE IS OFF)
                // $document.on('click', function(evt) {
                //     $timeout(function() {
                //         if ($(evt.target).closest('.autocomplete_input').length === 0) {
                //             scope.open = false;
                //         } else {
                //             if (scope.options.length > 0 && should_autocomplete(scope.type)) {
                //                 scope.open = true;
                //             }
                //         }
                //     }, 0);
                // });
            }
        };
    }
])


.directive('searchTopControls', ['$timeout', '$http', function($timeout, $http) {
    return {
        restrict: 'A',
        link: function(scope, iElement, iAttrs) {
            // not sure where it is used
            scope.savedQuery = null;

            // indicates that we have toggled some saved query
            scope.insideSavedSearch = false;

            // indicates that toggled saved search is loaded
            scope.savedSearchLoaded = false;

            // list of saved searches from the back end
            scope.savedQueriesList = angular.fromJson(iAttrs.savedQueriesList)
                .map(function(val) {
                    return {text: val.name, value: val.id, changed: false};
                });

            // url to get saved search details by id
            scope.getSavedSearchUrl = iAttrs.getSavedSearchUrl;

            scope.getPlaceholderText = function(options) {
                if (options.length > 0)
                    return 'Select a saved search...';
                else
                    return 'No saved searches yet...';
            };

            // dropdown options + current state of saved searches
            scope.savedQueries = {
                options: scope.savedQueriesList,
                placeholder: {text: scope.getPlaceholderText(scope.savedQueriesList), isPlaceholder: true},
                basicSearch: {text: 'Get back to basic search', isBasicSearch: true},
                selected: null,
            };

            // calculates whether we're inside some saved search or not
            scope.isInsideSavedQuery = function() {
                return scope.savedQueries.selected && !scope.savedQueries.selected.isPlaceholder && !scope.savedQueries.selected.isBasicSearch;
            };

            // chooses placeholder for the dropdown as currently selected item
            scope.displayPlaceholder = function() {
                scope.savedQueries.selected = angular.copy(scope.savedQueries.placeholder);
            };

            scope.resetSearch = function() {
                if (!scope.kwExpr.isDone)
                    return;
                scope.resetFilters();
                scope.keywords = [];
                scope.keyword_types = [];
                scope.kw_index = 0;
                scope.groups = [];
                scope.groupsNumber = 0;
                scope.concatenationTypeSelected = scope.concatenationTypes[0];
                scope.kwExpr.clear();
                scope.sorting.selected = scope.sorting.options[0];
                scope.sorting.update(true);
                // choose 'All' by default
                scope.updateType(scope.types[0], true);
                scope.setUrl(1);
                scope.search([], null, true);
                // scope.doFilter();
                if(scope.filterTimeout){
                    $timeout.cancel(scope.filterTimeout);
                }
                scope.filterTimeout = $timeout(scope.doFilter, 2000);
            };

            scope.getBackToBasicSearch = function() {
                scope.savedQueries.options.shift();
                scope.savedQuery = null;
                scope.andOrFilterOn = scope.context.andOrFilterOn;
                scope.resetSearch(); 
                scope.displayPlaceholder();
            };

            scope.doSavedSearchQuery = function() {
                scope.keyword = [];
                scope.keywords = [];
                scope.kw_index = 0;
                scope.keyword_types = [];
                scope.groups = [];
                scope.groupsNumber = 0;
                scope.concatenationTypeSelected = scope.concatenationTypes[0];
                if (scope.savedSearchQuery.keyword && scope.savedSearchQuery.keyword.length > 0) {
                    // to toggle keyword type button
                    scope.updateType(_.findWhere(scope.types, {value: scope.savedSearchQuery.type}), true);

                    scope.keywords = angular.copy(scope.savedSearchQuery.keyword);
                    if (scope.savedSearchQuery.keyword_types !== undefined && scope.savedSearchQuery.keyword_types !== null && scope.savedSearchQuery.keyword_types.length > 0)
                        scope.keyword_types = angular.copy(scope.savedSearchQuery.keyword_types);
                    else {
                        for (var i in scope.savedSearchQuery.keyword)
                            scope.keyword_types.push(scope.savedSearchQuery.type);
                    }

                    if (scope.savedSearchQuery.groups !== undefined && scope.savedSearchQuery.groups !== null && scope.savedSearchQuery.groups.length > 0) {
                        scope.groups = angular.copy(scope.savedSearchQuery.groups);
                    } else {
                        for (var i in scope.savedSearchQuery.keyword)
                            scope.groups.push(0);
                    }
                    scope.groupsNumber = scope.groups.length;
                    if (scope.savedSearchQuery.group_concatenator) {
                        scope.concatenationTypeSelected = _.findWhere(scope.concatenationTypes, {value: scope.savedSearchQuery.group_concatenator});
                    }

                    scope.kwExpr.loadSavedExpression();

                } else {
                    scope.updateType(scope.types[0], true);
                }

                scope.search(scope.keywords, scope.type, true);

                if (scope.savedSearchQuery.order_by !== undefined && scope.savedSearchQuery.order_by.field !== undefined) {
                    scope.sorting.selected = scope.sorting.findOption(scope.savedSearchQuery.order_by.field);
                    scope.sorting.update(true);
                }

                scope.doFilter(scope.savedSearchQuery.filters);

                scope.savedSearchLoaded = true;           
                scope.blockSearchTimeout = true;
            };

            scope.addSavedSearch = function(item) {
                if (scope.savedQueries.options.length > 0 && scope.savedQueries.options[0].isBasicSearch === true)
                    scope.savedQueries.options.splice(1, 0, item);
                else
                    scope.savedQueries.options.unshift(item);
                scope.savedQueries.placeholder.text = scope.getPlaceholderText(scope.savedQueries.options);
                if (!scope.isInsideSavedQuery())
                    scope.displayPlaceholder();
            };

            // on saved searches dropdown toggle
            scope.toggleSavedQuery = function(selected) {

                scope.updateType(scope.types[0], true);
                scope.resetDateRangePicker();

                // special case when we pass 'selected' element through the params
                if (selected !== undefined)
                    scope.savedQueries.selected = selected;

                // selected saved search should be unchanged initially
                scope.savedQueries.selected.changed = false;

                scope.savedSearchLoaded = false;

                // recalculate
                scope.insideSavedSearch = scope.isInsideSavedQuery();


                if (scope.savedQueries.selected.isBasicSearch === true) {
                    scope.getBackToBasicSearch();
                } else if (scope.savedQueries.options.length > 0 && scope.savedQueries.options[0].isBasicSearch !== true) {
                    scope.savedQueries.options.unshift(scope.savedQueries.basicSearch);
                }

                // no need to do a request if we're not inside any of the saved searches
                if (!scope.isInsideSavedQuery())
                    return;

                // request to get chosen saved search's details
                $http({
                    method: 'GET',
                    url: scope.getSavedSearchUrl + scope.savedQueries.selected.value
                }).success(function(response) {
                    // not sure if it's still used
                    scope.$broadcast('toggle-saved-search-dropdown', response);

                    scope.savedSearch = response;
                    scope.savedSearchQuery = response.query;
                    scope.andOrFilterOn = response.and_or_filter_on ? true : false;

                    scope.setUrl(1);

                    scope.doSavedSearchQuery();
                });
            };

            // display a placeholder initially
            scope.displayPlaceholder();            

            scope.$on('saved-search-added', function(their_scope, data) {
                scope.addSavedSearch(data);
            });

            scope.$on('saved-search-edited', function(their_scope, data) {
                _.findWhere(scope.savedQueries.options, {value: data.value}).text = data.text;
                scope.savedQueries.selected.changed = false;
                scope.savedQueries.selected.text = data.text;
            });
        }
    };
}])

.directive('savedSearch', [function() {
    return {
        restrict: 'A',
        link: function(scope, iElement, iAttrs) {
            scope.savedSearchQuery = angular.fromJson(iAttrs.savedSearchQuery);
            scope.populatePageInfo = function(info) {
                scope.page_info = info;
            };
        }
    };
}]);


// .controller('LoadInfluencersCtrl', ['$scope', '$rootScope', '$http', '$sce', 'loadInfluencersData', 'tags', 'tsSavedSearch', function($scope, $rootScope, $http, $sce, loadInfluencersData, tags, tsSavedSearch) {
//   var loadInfluencersCtrl = this;

//   loadInfluencersCtrl.searchMetaData = {};
//   angular.extend(loadInfluencersCtrl.searchMetaData, loadInfluencersData);

//   function tagsList() {
//     var self = this;

//     self.placeholder = function() {
//         return {'title': 'Selecte a tag group'};
//     };

//     tsSavedSearch.defaultTitle = $sce.trustAsHtml([
//         '<span class="brand_name">',
//             '<strong ng-show="loadInfluencersCtrl.searchMetaData.clientName">',
//             '{{ loadInfluencersCtrl.searchMetaData.clientName }} : </strong>',
//             '<span>{{ loadInfluencersCtrl.searchMetaData.campaignName }} : ',
//             '{{ loadInfluencersCtrl.searchMetaData.campaignSectionSelected.text }}</span>',
//         '</span>'].join(''));

//     self.options = tags;
//     self.selected = self.placeholder();
//     self.loaded = false;
//     self.loading = false;

//     self.update = function(selected) {
//         self.selected = selected;
//     };

//     self.add = function() {
//         self.loading = true;
//         $http({
//             method: 'POST',
//             url: '?add_tag_to_approval_report=1',
//             data: {
//                 tag_id: self.selected.value
//             }
//         }).success(function(response) {
//             self.loading = false;
//             self.loaded = true;
//             // self.selected = self.placeholder();
//             window.location.href = loadInfluencersData.approvalReportUrl;
//         }).error(function() {
//             self.loaded = true;
//             self.loading = false;
//             self.selected = self.placeholder();
//         });
//     };

//   }

//   loadInfluencersCtrl.tagsList = new tagsList();

//   $rootScope.$broadcast('setSearchMetaData', loadInfluencersCtrl.searchMetaData);
// }])
