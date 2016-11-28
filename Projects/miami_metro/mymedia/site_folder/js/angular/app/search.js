(function () {

    angular.module('mainSearch', ['theshelf', 'ui.router'])

    .provider('msConfig', ['contextProvider', function(contextProvider) {
        var context = contextProvider.$get();

        this.$get = function() {
            return {
                CANCEL_TIMEOUT: (context.onHeroku ? 20000 : 50000),
            };
        };
    }])

    .config(['$stateProvider', '$urlRouterProvider', '$sceDelegateProvider', 'RestangularProvider',
            'contextProvider', function($stateProvider, $urlRouterProvider, $sceDelegateProvider, RestangularProvider, contextProvider) {

        var context = contextProvider.$get();
        var initMode = context.initialSearchMode ? context.initialSearchMode : 'influencers';
        var initBrand = context.initBrand ? context.initBrand : null;

        $sceDelegateProvider.resourceUrlWhitelist([
            'self',
            'https://syndication.twitter.com/**',
            'http://theshelf-static-files.s3.amazonaws.com/**',
            'https://theshelf-static-files.s3.amazonaws.com/**',
        ]);
        RestangularProvider.setBaseUrl('/api/v1');

        // suffix should match "../:tab/:section/:page"

        $urlRouterProvider.when('/saved_search/:id/:tab/:section', '/saved_search/:id/:tab/:section/1');
        $urlRouterProvider.when('/saved_search/:id/:tab', '/saved_search/:id/:tab/' + initMode + '/1');
        $urlRouterProvider.when('/saved_search/:id', '/saved_search/:id/main_search/' + initMode + '/1');

        $urlRouterProvider.when('/tag/:id/:tab/:section', '/tag/:id/:tab/:section/1');
        $urlRouterProvider.when('/tag/:id/:tab', '/tag/:id/:tab/' + initMode + '/1');
        $urlRouterProvider.when('/tag/:id', '/tag/:id/main_search/' + initMode + '/1');

        $urlRouterProvider.when('/brand/:domain/:tab/:section', '/brand/:domain/:tab/:section/1');
        $urlRouterProvider.when('/brand/:domain/:tab', '/brand/:domain/:tab/' + initMode + '/1');
        $urlRouterProvider.when('/brand/:domain', '/brand/:domain/main_search/' + initMode + '/1');

        $urlRouterProvider.when('/:tab/:section', '/:tab/:section/1');

        // this should be a special case for 'enter' state
        // $urlRouterProvider.when('/:tab', '/:tab/influencers/1');

        $urlRouterProvider.when('/', '/main_search/' + initMode + '/1');

        if (initBrand) {
            $urlRouterProvider.otherwise('/brand/' + initBrand);
        } else {
            $urlRouterProvider.otherwise('/');
        }

        var tagsListPromise = null;
        var savedSearchesListPromise = null;
        var bloggerCustomDataPromise = null;

        var resolve = {
            bloggersContainer: ['$rootScope', function($rootScope) {
                return $rootScope.bloggersDefer.promise;
            }],
            postFeeds: ['$rootScope', function($rootScope) {
                return $rootScope.postFeedsDefer.promise;
            }],
            resetFilters: ['$rootScope', 'context', function($rootScope, context) {
                return $rootScope.resetFiltersDefer.promise;
            }],
            dateRange: ['$rootScope', function($rootScope) {
                return $rootScope.dateRangeDefer.promise;
            }],
            navigation: ['tsBrandNavigation', 'context', function(tsBrandNavigation, context) {
                return tsBrandNavigation.configDefer.promise;
            }],
            savedSearchesList: ['Restangular', 'context', 'tsSavedSearch', function (Restangular, context, tsSavedSearch) {
                if (savedSearchesListPromise === null && context.visitorBrandId !== null) {
                    savedSearchesListPromise = Restangular
                        .one('brands', context.visitorBrandId)
                        .withHttpConfig({ cache: true })
                        .getList('saved_searches')
                        .then(function (response) {
                            tsSavedSearch.init({savedSearchesList: response});
                            return response;
                        });
                }
                return savedSearchesListPromise;
            }],
            tagsList: ['TagsService', 'context', function(TagsService, context) {
                if (tagsListPromise === null && context.visitorBrandId !== null) {
                    tagsListPromise = TagsService.getData();
                }
                console.log('Y', tagsListPromise);
                return tagsListPromise;
            }],
            bloggerCustomData: ['Restangular', 'context', 'bloggerCustomData',
                    function(Restangular, context, bloggerCustomData) {
                if (bloggerCustomDataPromise === null && context.visitorBrandId !== null) {
                    bloggerCustomDataPromise = Restangular
                        .one('configurations', context.SITE_CONFIGURATION_ID)
                        .withHttpConfig({cache: true})
                        .customGET('blogger_custom_metadata')
                        .then(function(response) {
                            // @todo: one more ugly tmp thing!
                            if (!bloggerCustomData.isResolved) {
                                bloggerCustomData.resolve(Restangular.stripRestangular(response));
                            }
                            return response;
                        });
                }
                return bloggerCustomDataPromise;
            }],
        };

        $stateProvider

            .state('enter', {
                url: '^/:tab',
                resolve: resolve,
            })

            .state('basic', {
                url: '^/:tab/:section/:page',
                resolve: resolve,
            })

            .state('saved_search', {
                url: '^/saved_search/:id/:tab/:section/:page',
                resolve: resolve,
            })

            .state('saved_search.changed', {
                url: '^/saved_search/:id/:tab/:section/:page/changed',
                resolve: resolve,
            })

            .state('tag', {
                url: '^/tag/:id/:tab/:section/:page',
                resolve: resolve,
            })

            .state('brand', {
                url: '^/brand/:domain/:tab/:section/:page',
                resolve: resolve,
            })

            ;
    }])

    .run([
        '$rootScope',
        '$timeout',
        '$q',
        '$state',
        '$stateParams',
        '$window',
        'tsBrandNavigation',
        'tsMainSearch',
        'tsKeywordExpression',
        'tsSavedSearch',
        'tsLoader',
        'tsDateTimeRange',
        'tsQuerySort',
        'context',
        'TagsService',
        function($rootScope, $timeout, $q, $state, $stateParams, $window, tsBrandNavigation,
            tsMainSearch, tsKeywordExpression, tsSavedSearch, tsLoader, tsDateTimeRange,
            tsQuerySort, context, TagsService) {
        $rootScope.$state = $state;
        $rootScope.$stateParams = $stateParams;

        $rootScope.savedSearch = tsSavedSearch;
        $rootScope.isLoading = tsLoader.isLoading;
        $rootScope.loader = tsLoader;
        $rootScope.ms = tsMainSearch;
        $rootScope.kwExpr = tsKeywordExpression;
        $rootScope.tagsService = TagsService;

        tsLoader.setTimeoutedNotificationHandler(function() {
            $rootScope.$broadcast("displayMessage", {
                message: "The site is a bit slow right now, so please re-try in a bit.",
                closeCb: function() {
                    tsLoader.hideTimeoutedNotification();
                }
            });
        });

        tsLoader.setOnStartLoadingHandler(function() {
            // $rootScope.closeMessage();
        });

        tsMainSearch.setOnParamsChangeHandler(function(params) {
            console.log('params changed!');
            tsSavedSearch.setChanged(params);
            if (!tsMainSearch.isAndOrFilterOn() && tsMainSearch.params.kwIndex === 0) {
                tsMainSearch.setType();            
            }
        });

        tsSavedSearch.setHandler(function() {
            //$timeout(function() {
            $state.go('saved_search', {id: tsSavedSearch.selected.value, tab: $stateParams.tab, section: 'influencers', page: 1});
            tsDateTimeRange.reset();
            $rootScope.resetDateRangePicker();
            //}, 500);
        });

        tsSavedSearch.setErrorHandler(function() {
            $rootScope.displayMessage("Error loading this saved search..");
            tsSavedSearch.exit();
        });

        tsSavedSearch.setParamsHandler(function(params) {
            if (tsMainSearch.isAndOrFilterChangedManually()) {
                params.keywords = [];
                params.keywordTypes = [];
                params.groupNumbers = [];
                params.kwIndex = 0;
                tsKeywordExpression.reset();
            } else {
                tsMainSearch.setAndOrFilterOn(params.andOrFilterOn ? true : false);
            }
            tsMainSearch.setParams(params);

            if (tsMainSearch.isAndOrFilterOn()) {
                tsKeywordExpression.load();
                tsKeywordExpression.run(function() {
                    $state.reload();
                });
            }
        });

        tsSavedSearch.setResetHandler(function() {
            $rootScope.resetSearch();
            $state.go('basic', {tab: $stateParams.tab, section: 'influencers', page: 1}, {reload: true});
        });

        $rootScope.closeMessage = function() {
            $rootScope.$broadcast("closeMessage");
        };

        $rootScope.resetDateRangePicker = function() {
            $rootScope.$broadcast('resetDateRangePicker');
        };

        $rootScope.reloadFeeds = function() {
            console.log('broadcast reloadFeeds');
            $rootScope.$broadcast('reloadFeeds');
        };

        $rootScope.doFilter = function(){
            $rootScope.$broadcast("doFilter");
        };

        $rootScope.applyMode = function(params) {
            // TODO: rework controllers and views to use direct values from services
            $rootScope.mode_selected = tsMainSearch.getMode();
            $rootScope.mode = tsMainSearch.getMode().mode;
            $rootScope.page = Number(params.page);
        };

        $rootScope.resetSearch = function(options) {
            tsMainSearch.setAndOrFilterOn();
            tsMainSearch.resetParams(options);
            tsKeywordExpression.load();
        };

        $rootScope.removeAllFilters = function() {
            $rootScope.resetSearch();
            tsMainSearch.goToPage(1);
        };

        $rootScope.closeMessage = function() {
            $rootScope.$broadcast("closeMessage");
        };

        $rootScope.switchKeywordMode = function(advancedOn) {
            if (!canSwitchMode()) {
                return;
            }
            var yes = function() {
                $rootScope.resetSearch({nonFilterOnly: true});
                tsMainSearch.setAndOrFilterOn(advancedOn, {manual: true});
                tsMainSearch.goToPage(1);
            };
            var no = function() {
                $window.open('/search/main', '_blank');
            };
            var toName = function(toAdvanced) {
                return toAdvanced ? 'Advanced' : 'Regular';
            };
            if (tsMainSearch.params.keywords.length > 0) {
                $rootScope.$broadcast('openConfirmationPopup',
                    "If you switch to this " + toName(advancedOn) + " search, you will lose the current keywords that you've applied in the " + toName(!advancedOn) + " search.",
                    yes, no, {yesText: 'OK', noText: 'Open up a new search window', titleText: 'Are you sure?'});
            } else {
                yes();
            }
        };

        $rootScope.switchMetaMode = function(params) {
            tsMainSearch.setMode(params.section);
            $rootScope.applyMode(params);
            if (tsSavedSearch.isActive()) {
                tsSavedSearch.exit();
            } else {
                $rootScope.resetSearch();
                $rootScope.reloadFeeds();
            }
        };

        $rootScope.displayMessage = function(msg) {
            $rootScope.$broadcast("displayMessage", {message: msg});
        };

        $rootScope.showAppliedKeywords = function() {
            if (tsMainSearch.isAndOrFilterOn())
                return !tsKeywordExpression.isEmpty();
            else
                return tsMainSearch.params.keywords.length > 0;
        };

        $rootScope.sorting = tsQuerySort.selector('keyword');

        $rootScope.sorting.onSelect(function() {
            $timeout(function() {
                tsMainSearch.goToPage(1);
            }, 500);
        });

        $rootScope.bloggersDefer = $q.defer();
        $rootScope.resetFiltersDefer = $q.defer();
        $rootScope.savedSearchDefer = $q.defer();
        $rootScope.postFeedsDefer = $q.defer();
        $rootScope.dateRangeDefer = $q.defer();

        var onSuccess = {
            'enter': function(params) {
            },
            'basic': function(params) {
                $rootScope.reloadFeeds();
            },
            'saved_search': function(params) {
                var promise = tsSavedSearch.go(Number(params.id));
                if (promise) {
                    promise.then($rootScope.reloadFeeds);
                }
            },
            'saved_search.changed': function(params) {
                $rootScope.reloadFeeds();
            },
            'tag': function(params) {
                tsMainSearch.addFilter('tags', [Number(params.id)]);
                $rootScope.$broadcast('toggleFilter', 'tags');
                $rootScope.reloadFeeds();
            },
            'brand': function(params) {
                if (!tsMainSearch.isKeywordApplied(params.domain, 'brand')) {
                    tsMainSearch.addRegularKeyword(params.domain, 'brand');
                }
                $rootScope.reloadFeeds();
            },
        };

        function canSwitchMode() {
            if (tsMainSearch.isAndOrFilterOn() && !tsKeywordExpression.isComplete())
                return false;
            if (tsLoader.isLoading() && !tsMainSearch.isParamsChanged())
                return false;
            return true;
        }

        $rootScope.canSwitchMode = canSwitchMode;

        if (context.visitorBrandId === null) {
            console.log('==> setConfig');
            tsBrandNavigation.setConfig({
                tab: 'search',
                sub_tab: 'main_search',
                visible: true,
            });
        }

        $rootScope.$on('$stateChangeStart', function(event, to, toParams, from, fromParams) {
            console.log(from.name, '=>', to.name);

            if (!canSwitchMode()) {
                event.preventDefault();
                return;
            }

            console.log('==> setSubTabActive');
            tsBrandNavigation.setSubTabActive(toParams.tab);

            if ( (toParams.page !== undefined && isNaN(toParams.page)) || (toParams.id !== undefined && isNaN(toParams.id)) ) {
                event.preventDefault();
                var newParams = {
                    tab: toParams.tab,
                    section: toParams.section,
                    page: 1
                };
                $state.go('basic', newParams, {notify: false}).then(function() {
                    $rootScope.switchMetaMode(newParams);
                });
                return;
            }

            if (['main_search', 'instagram_search'].indexOf(toParams.tab) < 0) {
                event.preventDefault();
                var newParams = {
                    tab: 'main_search',
                    section: 'influencers',
                    page: 1
                };
                $state.go('basic', newParams, {notify: false}).then(function() {
                    $rootScope.switchMetaMode(newParams);
                });
                return;
            }

            if (!tsMainSearch.findMode(toParams.section)) {
                event.preventDefault();
                var newParams = {
                    tab: toParams.tab,
                    section: 'influencers',
                    page: 1
                };
                $state.go('basic', newParams, {notify: false}).then(function() {
                    $rootScope.switchMetaMode(newParams);
                });
                return;
            }

            if (to.name === 'enter') {
                event.preventDefault();
                var newParams = {
                    tab: toParams.tab,
                    section: 'influencers',
                    page: 1
                };
                $state.go('basic', newParams, {notify: false}).then(function() {
                    $rootScope.switchMetaMode(newParams);
                });
                return;
            }

            if (!tsMainSearch.shouldDisplayMode(toParams.section, toParams)) {
                event.preventDefault();
                var newParams = angular.copy(toParams);
                newParams.section = 'influencers';
                $state.go(to.name, newParams, {notify: true});
                return;
            }

            if (tsSavedSearch.isChanged()) {
                event.preventDefault();
                $state.go('saved_search.changed', toParams, {notify: false}).then(function() {
                    tsMainSearch.setMode(toParams.section);
                    $rootScope.applyMode(toParams);
                    $rootScope.reloadFeeds();
                });
                return;
            }

            if (to.name === 'saved_search.changed') {
                event.preventDefault();
                $state.go('saved_search', toParams, {notify: true});
                return;
            }

            if (from.name === 'tag') {
                event.preventDefault();
                $state.go('basic', toParams, {notify: false}).then(function() {
                    $rootScope.reloadFeeds();
                });
                return;
            }

            // $rootScope.switchMetaMode(toParams);
            tsMainSearch.setMode(toParams.section);
            $rootScope.applyMode(toParams);
        });

        $rootScope.$on('$stateChangeSuccess', function(event, toState, toParams) {
            onSuccess[toState.name](toParams);
        });

        $rootScope.$on('$stateNotFound', function() {
            console.log('$stateNotFound');
        });

        $rootScope.$on('$stateChangeError', function() {
            console.log('$stateChangeError');
        });
    }])

        
    .service('bloggerCustomData', ['$q', function($q) {
        var self = this;

        self.deferred = $q.defer();
        self.isResolved = false;

        self.resolve = function(data) {
            self.deferred.resolve(data);
            self.isResolved = true;
        };

    }])


    .service('TagsService', ['$q', 'Restangular', 'context', function($q, Restangular, context) {
        var self = this;
        var value2Obj = {};

        self.initDeferred = $q.defer();
        self.initResolved = false;

        self.getData = function() {
            console.log('TagsService.getData');
            return Restangular
                .one('tags')
                .get()
                .then(function(data) {
                    self.data = angular.copy(data.groups);
                    angular.forEach(self.data, function(tag) {
                        value2Obj[tag.id] = tag;
                    });
                    if (self.initResolved === false) {
                        self.initDeferred.resolve(self.data);
                        self.initResolved = true;
                    }
                    console.log('TagsService.getData.resolved');
                    return self.data;
                }, function(response) {});
        };

        self.getTagById = function(value) {
            if (!self.data) return;
            return value2Obj[value];
        };
    }])


    .value('tags', [])



    .controller('BloggersSearchCtrl', [
        '$scope',
        '$rootScope',
        '$state',
        '$stateParams',
        '$http',
        '$timeout',
        '$location',
        '$q',
        'debug',
        'context',
        'tsMainSearch',
        'tsKeywordExpression',
        'tsSavedSearch',
        'tsDateTimeRange',
        'NotifyingService',
        'msViewMode',
        'msSearchMethod',
        // 'savedSearchesList',
        function ($scope, $rootScope, $state, $stateParams, $http, $timeout,
            $location, $q, debug, context, tsMainSearch, tsKeywordExpression,
            tsSavedSearch, tsDateTimeRange, NotifyingService, msViewMode, msSearchMethod) {

        var vm = this;

        vm.viewMode = msViewMode;
        vm.searchMethod = msSearchMethod;

        $scope.modes = tsMainSearch.modes;

        $scope.debug = debug;
        $scope.context = context;

        $scope.dateRangeModel = {
            startDate: null,
            endDate: null,
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
            var selectedInfluencers = ($scope.mode === 'posts' ? $scope.productFeedBloggers : $scope.bloggers)
                .filter(function(inf) { return inf.selected; });
            if (!selectedInfluencers || !selectedInfluencers.length) {
                 $scope.$broadcast('openConfirmationPopup',
                    '', null, null, {
                        removeNo: true, yesText: 'OK', titleText: 'Please select at least one influencer.'
                    });
                 return;
            }
            options = options || {};
            if (!$scope.context.predictionReportEnabled || $scope.mode_selected.url !== 'blog_posts') {
                $scope.doOpenFavoritePopup({
                    influencer: selectedInfluencers
                        .map(function(inf) { return inf.id; }),
                });
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
            // $scope.$broadcast('openConfirmationPopup',
            //     'Do you want to Tag these influencers? Or do you want to Bookmark the posts to a post collection?',
            //     yes, no, {yesText: 'Influencers', noText: 'Posts', titleText: 'Please Choose'});
            yes();
        };

        $scope.openUpgradePopup = function(influencer_id){
            $scope.$broadcast('openUpgradePopup');
        };

        $scope.openSaveSearchPopup = function(editing) {
            $scope.$broadcast("openSaveSearchPopup", editing === true ? tsSavedSearch.selected : null);
        };

        $scope.populatePageInfo = function(data){
            $scope.page_info = data;
        };

        $scope.$on('saved-search-added', function(their_scope, opt) {
            tsSavedSearch.add(opt);
            tsSavedSearch.select(opt);
        });

        $scope.$on('saved-search-edited', function(their_scope, opt) {
            tsSavedSearch.resave(opt);
            $state.go('saved_search', $state.params, {reload: true});
        });

        $scope.$on('doOpenFavoritePopup', function(theirScope, options) {
            $scope.doOpenFavoritePopup(options);
        });


        // @unused
        // $rootScope.$on('setSearchMetaData', function(their_scope, data) {
        //     $scope.searchMetaData = data;
        // });
        // function timestamp(date) {
        //     return (new Date(date).getTime() / 1000).toFixed();
        // };


        // @todo: remove this and use 'dateRangePicker' directive instead
        $scope.applyDateRange = function() {
            if ($scope.filters === undefined || $scope.dateRangeModel.startDate === null || $scope.dateRangeModel.endDate === null)
                return;
            tsDateTimeRange.set($scope.dateRangeModel.startDate, $scope.dateRangeModel.endDate);
            $scope.doFilter();
        };
    }])


    .service('MultiSelectFilterService', ['_', '$q', 'Restangular', 'NotifyingService', 'bloggerCustomData',
        'locations', 'context', 'TagsService',
            function(_, $q, Restangular, NotifyingService, bloggerCustomData, locations, context, TagsService) {
        var self = this;

        function FilterConfig(params) {
            this.name = params.name;
            // this.options = params.options;
            this.getData = params.getData;
            this.remoteSearch = params.remoteSearch;

            this.deferred = null;
        }
        FilterConfig.prototype = {};
        FilterConfig.prototype.refresh = function(data, options) {
            options = options || {};
            this.deferred = $q.defer();

            if (options.notify) {
                NotifyingService.notify('multiSelectFilter:' + this.name + ':refresh');
            }

            this.deferred.resolve(data);
        };


        function createBloggerCustomDataFilters() {
            var filters = {
                customCategories: 'categoryChoices',
                customOccupation: 'occupationChoices',
                customSex: 'sexChoices',
                customEthnicity: 'ethnicityChoices',
                customTags: 'tagsChoices',
                customLanguage: 'languageChoices',
            };

            return _.map(filters, function(choicesName, filterName) {
                var config = new FilterConfig({
                    name: filterName,
                });

                config.deferred = $q.defer();
                
                bloggerCustomData.deferred.promise.then(function(data) {
                    config.deferred.resolve({
                        values: data[choicesName],
                    });
                });

                return config;
            });
        }

        function createOtherFilters() {
            var location = new FilterConfig({
                name: 'location',
                // options: locations,
                getData: function(params) {
                    return Restangular
                        .one('configurations', context.SITE_CONFIGURATION_ID)
                        .customGET('locations', params);
                },
                remoteSearch: true,
            });

            var tags = new FilterConfig({
                name: 'tags',
                // options: TagsService.data.map(function(tag) {
                //     return {};
                // }),
                getData: function(params) {
                    return TagsService.getData().then(function(tags) {
                        return tags.map(function(tag) {
                            return {
                                value: tag.id,
                                title: tag.name,
                            };
                        });
                    });
                },
                remoteSearch: false,
            });

            location.refresh({
                options: locations,
            }, {notify: false});

            tags.deferred = $q.defer();
            TagsService.initDeferred.promise.then(function(data) {
                tags.deferred.resolve({
                    options: data.map(function(tag) {
                        return {
                            value: tag.id,
                            title: tag.name,
                        };
                    }),
                });                
            });

            return [location, tags];
        }

        self.getConfigs = function() {
            var configsArray = Array.prototype.concat(createBloggerCustomDataFilters(),
                createOtherFilters());
            var configs = {};
            angular.forEach(configsArray, function(config) {
                configs[config.name] = config;
            });
            return configs;
        };
    }])


    .directive('multiSelectFilter', ['$timeout', 'tsConfig', 'NotifyingService', function($timeout, tsConfig, NotifyingService) {
        return {
            restrict: 'A',
            scope: true,
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/search_bloggers/multi_select_filter.html'),
            require: ['^bloggerSearchFilters', 'multiSelectFilter'],
            controller: function() {
                var vm = this;

                var getData = _.debounce(function() {
                    vm.loading = true;
                    vm.config.getData({
                        q: vm.searchModel,
                    }).then(function(response) {
                        vm.loading = false;
                        vm.filterOptions = response;
                        vm.updateNano();
                    }, function() {
                        vm.loading = false;
                    });
                }, 1000);

                vm.updateResults = function() {
                    if (vm.config.remoteSearch) {
                        getData();
                    } else {
                        vm.updateNano();
                    }
                };

                vm.refresh = function() {
                    getData();
                };
            },
            controllerAs: 'multiSelectFilterCtrl',
            link: function(scope, iElement, iAttrs, ctrls) {
                var filtersCtrl = ctrls[0], ctrl = ctrls[1];

                ctrl.filterName = iAttrs.filterName;
                ctrl.filterTitle = iAttrs.filterTitle;
                ctrl.filterHint = iAttrs.filterHint;
                ctrl.searchPlaceholder = iAttrs.searchPlaceholder;

                ctrl.config = filtersCtrl.multiSelectFilters[ctrl.filterName];

                ctrl.isVisible = function() {
                    return ctrl.filterOptions && filtersCtrl.shouldShowFilter(ctrl.filterName);
                };

                ctrl.idDisabled = function() {
                    return filtersCtrl.canFilter(ctrl.filterName);
                };

                ctrl.initNano = function() {
                    $timeout(function() {
                        iElement.find('.nano').nanoScroller({alwaysVisible: true});
                        iElement.find('.nano').nanoScroller({scroll: 'top'});
                    }, 100);
                };

                ctrl.updateNano = function() {
                    $timeout(function() {
                        iElement.find('.nano').nanoScroller();
                    }, 100);
                };

                ctrl.init = function() {
                    ctrl.config.deferred.promise.then(function(data) {
                        ctrl.filterValues = data.values;

                        if (!data.options) {
                            ctrl.filterOptions = ctrl.filterValues.map(function(v) {
                                return {
                                    value: v,
                                    title: v,
                                };
                            });
                        } else {
                            ctrl.filterOptions = data.options;
                        }

                        scope.multiSelectCtrl = ctrl;
                    });
                };

                NotifyingService.subscribe(scope, 'multiSelectFilter:' + ctrl.filterName + ':refresh', function() {
                    ctrl.refresh();
                });

                ctrl.init();
            }
        };
    }])


    .directive('appliedFiltersPanel', ['tsConfig', function(tsConfig) {
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
                '$timeout', 'genders', 'socials', 'activity', 'categories', 'tags', 'source', 'ageGroups',
                'enabled_filters', 'filtersQuery', '$http', '$q', 'context', '$rootScope', 'tsMainSearch',
                'tsKeywordExpression', 'tsConfig', 'NotifyingService', 'bloggerCustomData', 'msSearchMethod',
                'tsBrandNavigation', 'Restangular', '$window', 'MultiSelectFilterService', 'TagsService',
                function (popularity, brands, priceranges, locations, $timeout, genders,
                  socials, activity, cats, tags, source, ageGroups, enabled_filters, filtersQuery,
                  $http, $q, context, $rootScope, tsMainSearch, tsKeywordExpression, tsConfig,
                  NotifyingService, bloggerCustomData, msSearchMethod, tsBrandNavigation, Restangular,
                  $window, MultiSelectFilterService, TagsService) {
        return {
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/search_bloggers/filter_panel.html'),
            restrict: 'A',
            controllerAs: 'bloggerSearchFiltersCtrl',
            controller: function() {},
            link: function postLink(scope, iElement, iAttrs, ctrl) {
                scope.debug = iAttrs.debug !== undefined;
                
                var minZero = ['engagement', 'social', 'likes', 'shares', 'comments', 'customAgeRange'];

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
                
                setTimeout(function() {
                    iElement.find('.bs_tooltip').tooltip();

                    var $sidebar = iElement,
                        $$window = angular.element(window),
                        sidebartop = iElement.position().top;
                    
                    $$window.scroll(function() {
                        
                        if ($$window.height() > $sidebar.height()) {
                            $sidebar.removeClass('fixedBtm');
                            if($sidebar.offset().top <= $$window.scrollTop() && sidebartop <= $$window.scrollTop()) {
                                $sidebar.addClass('fixedTop');
                            } else {
                                $sidebar.removeClass('fixedTop');
                            }
                        } else {
                            $sidebar.removeClass('fixedTop');
                            if ($$window.height() + $$window.scrollTop() > $sidebar.offset().top + $sidebar.height()+20) {
                                $sidebar.addClass('fixedBtm');
                            }
                            
                            if ($sidebar.offset().top < 0) {
                                $sidebar.removeClass('fixedBtm');
                            }
                        }
                        
                    });
                }, 10);

                scope.sourceMapping = {};
                scope.pricerangesMapping = {};
                scope.avgAgeMapping = {};

                source.forEach(function(src) {
                    scope.sourceMapping[src.value] = src.title;
                });

                priceranges.forEach(function(item) {
                    scope.pricerangesMapping[item.title] = item.text;
                });

                ageGroups.forEach(function(item) {
                    scope.avgAgeMapping[item.value] = item.icon;
                });

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
                    likes: null,
                    shares: null,
                    comments: null,
                    engagement: "",
                    customAgeRange: "",
                };
                
                scope.defaultTmpFilters = {
                    social: null,
                    likes: null,
                    shares: null,
                    comments: null,
                    engagement: {
                        value: ""
                    },
                    customAgeRange: {
                        value: "",
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
                        popularity: [],
                        engagement: null,
                        customAgeRange: null,
                        brand: [],
                        priceranges: [],
                        location: [],
                        gender: [],
                        social: null,
                        likes: null,
                        avgAge: [],
                        shares: null,
                        comments: null,
                        activity: null,
                        tags: [],
                        customCategories: [],
                        customOccupation: [],
                        customSex: [],
                        customEthnicity: [],
                        customTags: [],
                        customLanguage: [],
                        source: [],
                        categories: scope.categories.applied
                    };
                    
                    scope.rangeModels = angular.copy(scope.defaultRangeModels);
                    scope.tmpFilters = angular.copy(scope.defaultTmpFilters);
                    scope.choiceModels = angular.copy(scope.defaultChoiceModels);

                    function emptyRangeModel() {
                        return {
                            rangeMin: null,
                            rangeMax: null,
                        };
                    }

                    scope.social_min = null;
                    scope.social_max = null;

                    scope.likes_min = null;
                    scope.likes_max = null;

                    scope.shares_min = null;
                    scope.shares_max = null;

                    scope.comments_min = null;
                    scope.comments_max = null;

                    scope.engagement_min = null;
                    scope.engagement_max = null;

                    scope.customAgeRange_min = null;
                    scope.customAgeRange_max = null;

                    scope.avg_age_min = null;
                    scope.avg_age_max = null;
                    
                    // scope.socialModel = emptyRangeModel();
                    // scope.likesModel = emptyRangeModel();
                    // scope.sharesModel = emptyRangeModel();
                    // scope.commentsModel = emptyRangeModel();
                    // scope.engagementModel = emptyRangeModel();
                    
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
                        if (filters['likes']) {
                            scope.rangeModels['likes'] = angular.copy(filters['likes']);
                            scope.tmpFilters['likes'] = angular.copy(filters['likes']);
                            scope.likes_min = scope.rangeModels['likes'].range_min;
                            scope.likes_max = scope.rangeModels['likes'].range_max;
                        }
                        if (filters['shares']) {
                            scope.rangeModels['shares'] = angular.copy(filters['shares']);
                            scope.tmpFilters['shares'] = angular.copy(filters['shares']);
                            scope.shares_min = scope.rangeModels['shares'].range_min;
                            scope.shares_max = scope.rangeModels['shares'].range_max;
                        }
                        if (filters['comments']) {
                            scope.rangeModels['comments'] = angular.copy(filters['comments']);
                            scope.tmpFilters['comments'] = angular.copy(filters['comments']);
                            scope.comments_min = scope.rangeModels['comments'].range_min;
                            scope.comments_max = scope.rangeModels['comments'].range_max;
                        }
                        if (filters['engagement']) {
                            scope.rangeModels['engagement'] = angular.copy(filters['engagement']);
                            scope.tmpFilters['engagement'] = angular.copy(filters['engagement']);
                            scope.engagement_min = scope.rangeModels['engagement'].range_min;
                            scope.engagement_max = scope.rangeModels['engagement'].range_max;
                        }
                        if (filters['customAgeRange']) {
                            scope.rangeModels['customAgeRange'] = angular.copy(filters['customAgeRange']);
                            scope.tmpFilters['customAgeRange'] = angular.copy(filters['customAgeRange']);
                            scope.customAgeRange_min = scope.rangeModels['customAgeRange'].range_min;
                            scope.customAgeRange_max = scope.rangeModels['customAgeRange'].range_max;
                        }
                        if (filters['activity']) {
                            scope.choiceModels['activity'] = angular.copy(filters['activity']);
                            scope.selectedActivityLevel = _.findWhere(
                                scope.activityLevels,
                                {value: scope.choiceModels['activity'].activity_level});
                        }
                    }

                };

                scope.resetFilters();

                scope.toggledFilters = {};
                _.keys(scope.filters).forEach(function(filter) {
                    scope.toggledFilters[filter] = false;
                });

                ctrl.toggledFilters = scope.toggledFilters;

                scope.toggledByDefault = [
                    'engagement', 'socials', 'categories', 'location', 'tags'];
                scope.toggledByDefault.forEach(function(filter) {
                    scope.toggledFilters[filter] = false;
                });

                scope.metaModeFiltersDisabled = {
                    'main_search': [], // all,
                    'instagram_search': ['location', 'priceranges', 'categories', 'genders']
                };

                scope.searchMethodFiltersDisabled = {
                    'default': ['customCategories', 'customOccupation', 'customSex',
                        'customEthnicity', 'customTags', 'customLanguage', 'customAgeRange',],
                    'r29': [],
                };

                scope.shouldShowFilter = function(filter) {
                    var filtersDisabled;

                    if (!tsBrandNavigation.config)
                        return true;
                    filtersDisabled = scope.metaModeFiltersDisabled[tsBrandNavigation.config.sub_tab];
                    if (filtersDisabled && filtersDisabled.indexOf(filter) > -1)
                        return false;
                    filtersDisabled = scope.searchMethodFiltersDisabled[msSearchMethod.selected.value];
                    if (filtersDisabled && filtersDisabled.indexOf(filter) > -1)
                        return false;
                    return true;
                };

                ctrl.shouldShowFilter = scope.shouldShowFilter;

                scope.toggleFilter = function(filter) {
                    scope.toggledFilters[filter] = !scope.toggledFilters[filter];
                    scope.updateNano();
                };

                ctrl.toggleFilter = scope.toggleFilter;

                scope.$on('toggleFilter', function(their_scope, filter) {
                    scope.toggleFilter(filter);
                });
                
                scope.popularity = popularity;
                scope.priceranges = priceranges;
                scope.brands = brands;
                scope.location = locations;
                scope.genders = genders;
                scope.socials = socials;
                scope.ageGroups = ageGroups;
                scope.activity = activity;
                scope.tags = TagsService.data;
                scope.source = source;
                scope.filterTimeout = null;
                
                scope.startFilteringTimeout = function(){
                    if(scope.filterTimeout){
                        $timeout.cancel(scope.filterTimeout);
                    }
                    // save filters
                    tsMainSearch.setParams({filters: scope.filters});
                    // filters are changed during keyword expression editing,
                    // so we need to reload the results once we discard the keyword
                    // expression
                    tsKeywordExpression.setFiltersChanged();
                    scope.filterTimeout = $timeout(scope.doFilter, 2000);
                };
                
                scope.hasFilters = function(){
                    var resp = false;
                    if(scope.filters.popularity && scope.filters.popularity.length > 0) resp = true;
                    else if(scope.filters.engagement) resp = true;
                    else if(scope.filters.customAgeRange) resp = true;
                    else if(scope.filters.brand.length>0) resp = true;
                    else if(scope.filters.priceranges.length>0) resp = true;
                    else if(scope.filters.location.length>0) resp = true;
                    else if(scope.filters.tags.length>0) resp = true;
                    else if(scope.filters.customCategories.length>0) resp = true;
                    else if(scope.filters.customOccupation.length>0) resp = true;
                    else if(scope.filters.customSex.length>0) resp = true;
                    else if(scope.filters.customEthnicity.length>0) resp = true;
                    else if(scope.filters.customTags.length>0) resp = true;
                    else if(scope.filters.customLanguage.length>0) resp = true;
                    else if(scope.filters.gender.length>0) resp = true;
                    else if(scope.filters.social) resp = true;
                    else if(scope.filters.likes) resp = true;
                    else if(scope.filters.avgAge && scope.filters.avgAge.length > 0) resp = true;
                    else if(scope.filters.shares) resp = true;
                    else if(scope.filters.comments) resp = true;
                    else if(scope.filters.activity) resp = true;
                    else if(scope.filters.source.length>0) resp = true;
                    //else if(scope.keyword) resp = true;
                    else if(scope.categories.active()) resp = true;
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
                    if (index >= 0) {
                        scope.filters[type].splice(index, 1);
                    } else {
                        scope.filters[type].push(value);
                    }
                    scope.startFilteringTimeout();
                };

                ctrl.toggleTypeFilter = scope.toggleTypeFilter;

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
                    scope.toggleChoiceFilter('activity', scope.choiceModels['activity'].platform, scope.selectedActivityLevel);
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
                    return scope.filters[type].indexOf(value) >= 0;
                };

                ctrl.hasTypeFilter = scope.hasTypeFilter;
                
                scope.updateNano = function(){
                    setTimeout(function() {
                        iElement.find(".nano").nanoScroller({alwaysVisible: true});
                        iElement.find(".nano").nanoScroller({ scroll: 'top' });
                    }, 100);
                };
                ctrl.updateNano = scope.updateNano;

                scope.canFilter = function(name){
                    return enabled_filters.indexOf(name)>=0;
                };
                ctrl.canFilter = scope.canFilter;

                scope.$watch('sourceSearch', scope.updateNano);
                scope.updateNano();

                ctrl.multiSelectFilters = {};
                angular.extend(ctrl.multiSelectFilters, MultiSelectFilterService.getConfigs());

                $rootScope.resetFiltersDefer.resolve();
            }
        };
    }])

    .directive('bloggerContainer', ['_', '$http', '$compile', '$sce', '$q', '$rootScope',
                                        '$location', '$timeout', '$stateParams',
                                        'keywordQuery', 'tsQueryCache', 'tsQuerySort',
                                        'tsQueryResult', 'context', 'filtersQuery',
                                        'tsKeywordExpression', 'tsMainSearch', 'tsLoader',
                                        'tsSavedSearch', 'tsConfig', 'NotifyingService',
                                        'msViewMode', 'msSearchMethod', 'tsBrandNavigation', 'msConfig',
                                        function (_, $http, $compile, $sce, $q, $rootScope, $location,
                                          $timeout, $stateParams, keywordQuery,
                                          tsQueryCache, tsQuerySort, tsQueryResult,
                                          context, filtersQuery, tsKeywordExpression, tsMainSearch,
                                          tsLoader, tsSavedSearch, tsConfig, NotifyingService,
                                          msViewMode, msSearchMethod, tsBrandNavigation, msConfig) {
        return {
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/search_bloggers/container.html'),
            restrict: 'A',
            replace: true,
            controllerAs: 'bloggerContainerCtrl',
            controller: function($scope, $element, $attrs, $transclude) {
                var vm = this;

                vm.viewMode = msViewMode;
                vm.searchMethod = msSearchMethod;

                vm.masonryReload = function() {
                    console.log('masonry.reload !!!');
                    $rootScope.$broadcast('masonry.reload');
                };

                vm.masonryDebouncedReload = _.debounce(vm.masonryReload, 300);

                $scope.grid_scope = null;
                $scope.pages1 = [];
                $scope.pages2 = [];
                $scope.pages3 = [];
                
                $scope.current_name_filters = null;
                $scope.current_keyword_filters = null;
                $scope.current_keyword_filter_type = null;

                $scope.context = context;
                
                $scope.cancelDefer = null;

                $scope.timeoutedCount = 0;

                $scope.doFetchBloggers = function() {

                    vm.imgsShouldLoadCount = 0;
                    vm.imgsLoadedCount = 0;

                    if($scope.cancelDefer !== null)
                        $scope.cancelDefer.resolve();
                    $scope.cancelDefer = null;

                    $scope.page = tsMainSearch.getPage();

                    // if ($scope.andOrFilterOn && tsLoader.isLoading() && !tsKeywordExpression.isComplete())
                    //     return;

                    if (!tsMainSearch.isBloggersMode()) {
                        $scope.doFetchPosts();
                        return;
                    }

                    if ($scope.waitForAction) {
                        if (!tsMainSearch.isParamsChanged() && !tsSavedSearch.isActive()) {
                            $scope.state = 'wait_for_action';
                            return;
                        }
                    }

                    if ($scope.remaining === 0 && $scope.has_pages === false)
                        return;

                    $scope.cancelDefer = $q.defer();

                    console.log("do search bloggers");

                    tsLoader.startLoading();
                    $scope.populatePageInfo(null);

                    $scope.clearSalvattore();

                    $scope.state = "ok";

                    var query_data = {
                        filters: tsMainSearch.params.filters,
                        keyword: tsMainSearch.params.keywords,
                        type: "all", // deprecated, just default value for now
                        keyword_types: tsMainSearch.params.keywordTypes,
                        groups: tsMainSearch.params.groupNumbers,
                        group_concatenator: tsMainSearch.params.groupConcatenator,
                        page: $scope.page,
                        order_by: tsQuerySort.get('keyword'),
                        and_or_filter_on: tsMainSearch.isAndOrFilterOn(),
                        sub_tab: tsBrandNavigation.config.sub_tab,
                        search_method: msSearchMethod.selected.value,
                    };

                    var retryTimeout = $timeout(function(){
                        if($scope.cancelDefer !== null){
                            $scope.cancelDefer.resolve();
                            $scope.cancelDefer = null;
                            $scope.doFetchBloggers();
                            tsLoader.setTimeouted();
                            // $scope.displayMessage("The site is a bit slow right now, so please re-try in a bit.");
                            $scope.timeoutedCount++;
                            if ($scope.timeoutedCount == 3) {
                                $scope.timeoutedCount = 0;
                                $scope.closeMessage();
                                $scope.cancelDefer = null;
                                $timeout.cancel(retryTimeout);
                                $timeout(function(){
                                    tsLoader.stopLoading();
                                },100);
                                $scope.state = "timeouted";
                            }
                            console.log("timeouted!");
                        }
                    }, msConfig.CANCEL_TIMEOUT);

                    $http({
                        url: '/search/bloggers/json',
                        method: 'POST',
                        data: query_data,
                        timeout: $scope.cancelDefer.promise
                    }).success(function (data) {
                        console.log("search finished"); 


                        $scope.timeoutedCount = 0;

                        $scope.closeMessage();

                        $scope.cancelDefer = null;
                        $timeout.cancel(retryTimeout);

                        tsQueryCache.set(query_data);
                        tsQueryResult.set({
                          total: data.total_influencers,
                          results: data.results
                        });

                        if(data.results == undefined || data.results.length == 0){
                            $scope.state = "no results";
                        }

                        $scope.bloggers = data.results;
                        $scope.engagementToFollowersRatio = data.engagement_to_followers_ratio_overall;

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

                        if (msViewMode.selected.value == 'grid') {
                            $timeout(function() {
                                $scope.updateSalvattore();
                            }, 10);
                        } else {
                            $scope.clearSalvattore();
                        }

                        $timeout(function(){
                            tsLoader.stopLoading();
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
                        
                        $timeout(function() {
                            NotifyingService.notify('itemBlock:resize');
                        }, 900);
                    })
                    .error(function(response, status) {
                        // $scope.timeoutedCount = 0;
                        $scope.cancelDefer = null;
                        $timeout.cancel(retryTimeout);
                        $timeout(function(){
                            tsLoader.stopLoading();
                        },100);
                        if (response == "limit") {
                            $scope.state = "limit";
                        } else if (status == 403) {
                            $scope.state = "unauthorized";
                        } else {
                            // $scope.state = "error";
                        }
                    });
                };

                $scope.setPage = function(page_no){
                    if (!tsKeywordExpression.isComplete())
                        return;
                    console.log('set page');
                    if($scope.pages1.indexOf(page_no)<0 &&
                       $scope.pages2.indexOf(page_no)<0 &&
                       $scope.pages3.indexOf(page_no)<0 ){
                        return;
                    }
                    tsMainSearch.goToPage(isNaN(page_no) ? 1 : page_no);
                };

                $scope.applyFilters = function() {
                    $scope.resetFilters(tsMainSearch.params.filters);
                    filtersQuery.setQuery(tsMainSearch.params.filters);
                    if ($scope.sorting.isSelectedByDefault) {
                        $scope.sorting.select($scope.sorting.findOption($scope.showAppliedKeywords() ? '_score' : null));
                    }
                };

                $scope.$on("doFilter", function(their_scope){
                    // filters should be saved before calling this
                    console.log('doFilter');
                    $scope.applyFilters();
                    tsMainSearch.goToPage(1);
                });

                $scope.$on("reloadFeeds", function(){
                    console.log('reload feeds');
                    $scope.applyFilters();
                    tsLoader.hideTimeoutedNotification();
                    $scope.doFetchBloggers();
                });

                console.log('resolve!!!!!!!!!!!!!!!!!!!');
                $rootScope.bloggersDefer.resolve();
            },
            link: function postLink(scope, iElement, iAttrs, ctrl) {
                scope.campaignId = iAttrs.campaignId;
                scope.waitForAction = iAttrs.waitForAction !== undefined;
                scope.salvattore_registered = $q.defer();
                scope.pricing_url = iAttrs.pricingUrl;

                scope.clearSalvattore = function () {
                    angular.element("html, body").animate({ scrollTop: 0 }, 200);
                    return $timeout(function() {}, 150);
                    var gridWrapper = iElement.find('.bloggers_grid_wrapper');

                    if(scope.grid_scope){
                        scope.grid_scope.$destroy();
                        scope.grid_scope = null;
                    }
                    var promise = $timeout(function() {
                        gridWrapper.children().remove();
                    }, 100);
                    angular.element("html, body").animate({ scrollTop: 0 }, 200);
                    return promise;
                };

                scope.updateSalvattore = function () {
                    return $timeout(function() {}, 150);
                    var gridWrapper = iElement.find('.bloggers_grid_wrapper');
                    var grid = angular.element('<div class="salvattore_grid clearfix bloggers_container" data-columns></div>');
                    gridWrapper.append(grid);

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
                        scope.grid_scope = null;
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
                    return $timeout(add_salvattore_inner, 150);
                };

                NotifyingService.subscribe(scope, 'search:change:viewMode', function(theirScope, viewMode) {
                    if (viewMode === 'grid') {
                        tsLoader.startLoading();
                        $timeout(function() {
                            scope.updateSalvattore().then(function() {
                                tsLoader.stopLoading();
                            });
                        }, 10);
                    } else if (viewMode === 'table') {
                        tsLoader.startLoading();
                        $timeout(function() {
                            scope.clearSalvattore().then(function() {
                                tsLoader.stopLoading();
                            });
                        }, 10);
                    }
                });

                NotifyingService.subscribe(scope, 'search:change:searchMethod', function(theirScope, searchMethod) {
                    tsMainSearch.switchTypesMode();
                    if (searchMethod !== 'r29') {
                        msViewMode.change('grid');
                    }
                    $rootScope.resetSearch();
                    tsMainSearch.goToPage(1);
                });

                NotifyingService.subscribe(scope, 'itemBlock:resize', function() {
                    ctrl.masonryReload();
                });
            }
        };
    }])


    .directive('bloggerInfo', [
        '$timeout',
        '$http',
        '$rootScope',
        '$interpolate',
        'context',
        'debug',
        'tsInvitationMessage',
        'tsConfig',
        function ($timeout, $http, $rootScope, $interpolate, context, debug, tsInvitationMessage, tsConfig) {
        return {
            restrict: 'A',
            scope: {
              'user': '=',
            },
            controller: function() {},
            // controllerAs: 'bloggerInfoCtrl'
            replace: true,
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/search_bloggers/blogger_info.html'),
            // template: '<div></div>',
            link: function (scope, iElement, iAttrs) {
                scope.has_collections_in = !_.isEmpty(scope.user.collections_in);
                scope.debug = debug;
                scope.context = context;
                scope.bookmarks = iAttrs.bookmarks !== undefined;     
                $timeout(function() {
                    iElement.find('.bs_tooltip').tooltip();
                }, 10);

                scope.keys = Object.keys;

                scope.isLongList = function() {
                    return scope.user.collections_in && Object.keys(scope.user.collections_in).length > 9;
                };

                scope.$on('user-collections-in-changed', function(their_scope, data) {
                    if (scope.user.id == data.id) {
                        // scope.has_collections_in = data.has_collections_in;
                        // scope.user = angular.extend(scope.user, {
                        //     collections_in: data.collections_in
                        // });
                        scope.user.collections_in = scope.user.collections_in || {};
                        if (data.partial) {
                            angular.extend(scope.user.collections_in, data.collections_in);
                        } else {
                            scope.user.collections_in = angular.copy(data.collections_in);
                        }
                        scope.has_collections_in = !_.isEmpty(scope.user.collections_in);
                    }
                });

                scope.platform = scope.user.current_platform;

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
                    if (options.user && options.user.has_artificial_blog_url && options.user.current_platform_page && !options.user.email) {
                        return;
                    } else if (options.event) {
                        options.event.preventDefault();
                    }
                    $rootScope.$broadcast("openInvitationPopup", options);
                };
            }
        };
    }])


    .directive('mixedAutocompleteInput', ['$timeout', '$http', '$location', 'keywordQuery',
                                            '$rootScope', '$q', '$document',
                                            'tsQueryCache', 'tsQuerySort', 'filtersQuery', 'tsKeywordExpression', 'tsMainSearch', 'tsLoader',
                                            'tsConfig',
                                            function($timeout, $http, $location, keywordQuery, $rootScope,
                                              $q, $document, tsQueryCache, tsQuerySort, filtersQuery, tsKeywordExpression, tsMainSearch, tsLoader, tsConfig) {
            return {
                templateUrl: tsConfig.wrapTemplate('js/angular/templates/mixed_search_autocomplete_input.html'),
                replace: true,
                restrict: 'A',
                controller: function($scope, $element, $attrs) {
                    $scope.showExtraTypes = false;

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

                    $scope.showAppliedFilters = function() {
                        return $scope.hasFilters() || $scope.showAppliedKeywords();
                    };

                    $scope.add_or_element = function() {
                        if ($scope.searchKeyword && $scope.searchKeyword.length > 0) {
                            tsMainSearch.addRegularKeyword($scope.searchKeyword, angular.copy(tsMainSearch.getType().value))
                            $scope.searchKeyword = "";
                            tsMainSearch.goToPage(1);
                        }
                    };

                    $scope.remove_or_element = function(index) {
                        tsMainSearch.removeRegularKeyword(index);
                        tsMainSearch.goToPage(1);
                    };
                    
                },
                link: function postLink(scope, iElement, iAttrs) {
                }
            };
        }
    ])

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
    }])

    .directive('searchTopSection', function() {
        return {
            restrict: 'A',
            link: function(scope, iElement, iAttrs) {
                iElement.find('.search_extras').affix({
                    offset: {
                        top: 0
                    }
                });
            }
        };
    })

    .directive('bloggerSearchPage', function() {
        return {
            restrict: 'A',
            link: function(scope, iElement, iAttrs) {
                iElement.find('.mass_bookmark_button').affix({
                    offset: {
                        top: 0
                    }
                });
            }
        };
    })

    .directive('keywordExpressionEditor', ['$rootScope', 'tsKeywordExpression', 'tsMainSearch', 'tsConfig', function($rootScope, tsKeywordExpression, tsMainSearch, tsConfig) {
        return {
            restrict: 'A',
            replace: true,
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/keyword_expression_editor.html'),
            link: function(scope, iElement, iAttrs) {
                scope.kwExpr = tsKeywordExpression;

                scope.onChange = function(options) {
                    if (options.last && !options.kw.isEmpty()) {
                        options.group.addKeyword();
                    } else if (!options.last && options.kw.isEmpty()) {
                        options.group.removeKeyword(options.index);
                    }

                    if (tsKeywordExpression.isEmpty()) {
                        tsKeywordExpression.setComplete();
                        if (tsKeywordExpression.isFiltersChanged()) {
                            scope.runSearch(); 
                        }
                    } else {
                        tsKeywordExpression.setEditing();
                    }
                };

                scope.onBlur = function(options) {
                    if (options.kw.isEmpty() && !options.last)
                        options.group.removeKeyword(options.index);
                };

                scope.onTypeChange = function() {
                    tsKeywordExpression.setEditing();
                };

                scope.removeKeyword = function(options) {
                    options.group.removeKeyword(options.index);
                    if (tsKeywordExpression.isEmpty())
                        scope.runSearch();
                };

                scope.discard = function(options) {
                    var changed = tsKeywordExpression.isFiltersChanged();
                    tsKeywordExpression.load();
                    if (changed) {
                        scope.runSearch();
                    }
                };

                scope.runSearch = function() {

                    tsKeywordExpression.setComplete();

                    tsKeywordExpression.run(function() {
                        scope.applyFilters();
                        tsMainSearch.goToPage(1);
                    });

                };
            }
        };
    }])



    .service('tsSearchUtils', [function() {

        function compare(newParams, oldParams, excludeKeys) {
            if (excludeKeys === undefined)
                excludeKeys = [];
            for (var k in newParams) {
                if (excludeKeys.indexOf(k) < 0 && oldParams[k] !== undefined && !_.isEqual(newParams[k], oldParams[k]))
                    return false;
            }
            return true;
        }

        function compareParamsOnly(newParams, oldParams) {
            return compare(newParams, oldParams, ['filters']);
        }

        function compareFiltersOnly(newParams, oldParams) {
            return compare(newParams.filters, oldParams.filters, ['time_range']);
        }

        function compareParams(newParams, oldParams, excludeKeys) {
            return compareFiltersOnly(newParams, oldParams) && compareParamsOnly(newParams, oldParams);
        }

        function paramsOnlyChanged(newParams, oldParams) {
            return compareFiltersOnly(newParams, oldParams) && !compareParamsOnly(newParams, oldParams);
        }

        function filtersOnlyChanged(newParams, oldParams) {
            return !compareFiltersOnly(newParams, oldParams) && compareParamsOnly(newParams, oldParams);
        }

        this.comparator = function(newParams, oldParams) {
            return {
                isEqual: compareParams(newParams, oldParams),
                isParamsOnlyChanged: paramsOnlyChanged(newParams, oldParams),
                isFiltersOnlyChanged: filtersOnlyChanged(newParams, oldParams)
            };
        };

        // this.compareParams = compareParams;
        // this.paramsOnlyChanged = paramsOnlyChanged;
        // this.filtersOnlyChanged = filtersOnlyChanged;

    }])

    .service('tsDateTimeRange', [function() {
        var startDate = null;
        var endDate = null;

        this.set = function(start, end) {
            startDate = start;
            endDate = end;
        };

        this.getStart = function() {
            return startDate;
        };

        this.getEnd = function() {
            return endDate;
        };

        this.reset = function() {
            startDate = null;
            endDate = null;
        };

        this.empty = function() {
            return startDate === null || endDate === null;
        };
    }])

    .service('tsLoader', ['$q', '$timeout', 'tsSavedSearch', 'tsMainSearch', 'msConfig',
            function($q, $timeout, tsSavedSearch, tsMainSearch, msConfig) {
        var loadingDefer = null;
        var loader = this;
        var timeouted = false;
        var onLoadedHandler = function() {};
        var canShowNotification = true;
        var timeoutedNotificationHandler = function() {};
        var notificationTimeout = null;
        var onStartLoadingHandler = function() {};

        this.isFetching = function() {
            return loadingDefer !== null;
        }

        this.isLoading = function() {
            // here we define in what state all actions should be locked
            if (tsSavedSearch.isLoading())
                return true;
            if (loader.isFetching()) {
                return true;
                // if (tsMainSearch.isParamsChanged())
                //     return !tsMainSearch.isFiltersOnlyChanged();
                // return false;
            }
            return false;
        };

        this.startLoading = function() {
            if (loadingDefer !== null) {
                loadingDefer.resolve();
            }
            loadingDefer = $q.defer();
            console.log('start loading');
            onStartLoadingHandler();
        };

        this.setOnStartLoadingHandler = function(handler) {
            onStartLoadingHandler = handler || function() {};
        };

        this.stopLoading = function() {
            if (loadingDefer !== null) {
                loadingDefer.resolve();
            }
            loadingDefer = null;
            timeouted = false;
            console.log('stop loading');
            onLoadedHandler();
        };

        this.setOnLoadedHandler = function(handler) {
            onLoadedHandler = handler || function() {};
        }

        this.setTimeouted = function() {
            timeouted = true;
            loader.showTimeoutedNotification();
        };

        this.isTimeouted = function() {
            return timeouted;
        };

        this.setTimeoutedNotificationHandler = function(handler) {
            timeoutedNotificationHandler = handler || function() {};
        };

        this.showTimeoutedNotification = function() {
            if (canShowNotification) {
                timeoutedNotificationHandler();
            }
        };

        this.restartNotificationTimer = function() {
            canShowNotification = false;
            if (notificationTimeout !== null) {
                $timeout.cancel(notificationTimeout);
            }
            notificationTimeout = $timeout(function() {
                canShowNotification = true;
            }, msConfig.CANCEL_TIMEOUT);
        };

        this.hideTimeoutedNotification = function() {
            loader.restartNotificationTimer();
        };
    }])


    .service('msViewMode', ['_', '$rootScope', 'NotifyingService', 'Restangular', 'context',
            function(_, $rootScope, NotifyingService, Restangular, context) {
        var self = this;

        var DEFAULT_MODE = context.brandSettings ? context.brandSettings.searchViewMode : 'grid';

        function find(value) {
            return _.findWhere(self.options, {value: value});
        }

        function select(value) {
            var nm = find(value);
            self.selected = nm ? nm : find(DEFAULT_MODE);
        }

        self.options = [
            {icon: 'icon-misc_shapes_9grid', value:'grid', text: 'Grid'},
            {icon: 'icon-misc_shapes_stripes', value:'table', text: 'Table'},
        ];
        
        self.change = function(value) {
            var prev = self.selected.value;
            select(value);
            if (prev !== value) {
                NotifyingService.notify('search:change:viewMode', value);
            }
            Restangular
                .one('brands', context.visitorBrandId)
                .post('flags', {
                    search_view_mode: value,
                });
        };

        select();
    }])


    .service('tsMainSearch', ['_', '$q', 'context', 'debug', '$stateParams',
            '$state', 'tsSearchUtils', 'tsDateTimeRange', 'msSearchMethod',
            function(_, $q, context, debug, $stateParams, $state, tsSearchUtils,
                tsDateTimeRange, msSearchMethod) {
        var ms = this;

        this.modes = [
            {text: 'all', mode: 'posts', url: 'all', metaModes: ['main_search'], feedPage: 'pageAll'},
            {text: 'influencers', mode:'bloggers', url: 'influencers', metaModes: ['main_search', 'instagram_search']},
            {text: 'blog posts', mode:'posts', cf: 'blog', url: 'blog_posts', metaModes: ['main_search'], feedPage: 'pageBlog'},
            {text: 'tweets', mode:'posts', cf: 'tweets', url: 'tweets', metaModes: ['main_search'], feedPage: 'pageTwitter'},
            {text: 'instagrams', mode:'posts', cf: 'photos', url: 'instagrams', metaModes: ['main_search', 'instagram_search'], feedPage: 'pageInst'},
            {text: 'pins', mode:'posts', cf: 'pins', url: 'pins', metaModes: ['main_search'], feedPage: 'pagePin'},
            {text: 'youtube', mode:'posts', cf: 'youtube', url: 'youtube', metaModes: ['main_search'], feedPage: 'pageVideo'},
            {text: 'products', mode: 'posts', cf: 'products', url: 'products', metaModes: ['main_search'], feedPage: 'pageProd'},
            {text: 'facebook', mode:'posts', cf: 'facebook', url: 'facebook', metaModes: ['main_search'], feedPage: 'pageFacebook'},
        ];

        // if (debug) {
        //     this.modes.push({
        //         text: 'facebook', mode:'posts', cf: 'facebook', url: 'facebook', metaModes: ['main_search'], feedPage: 'pageFacebook'});
        // }

        function getAdvancedTypes() {
            return [
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
        }

        function getRegularTypes() {
            return [
                {value: "all", text:"All", extra: false},
                //{value: "keyword", text:"Keywords"},
                {value: "brand", text:"Brand URL", extra: false},
                {value: "hashtag", text: "#", extra: false},
                {value: "mention", text: "@", extra: false},
                // {value: "location", text:"Location", extra: true},
                {value: "blogname", text: msSearchMethod.selected.value === 'r29' ? "Instagram Handle" : "Blog Name", extra: true},
                {value: "blogurl", text:"Blog URL", extra: true},
                {value: "name", text:"Name", extra: true}
            ];
        }

        var andOrFilterOn;

        setAndOrFilterOn(false);

        var currentType = this.types[0];

        function findType(value) {
            return _.findWhere(ms.types, {value: value});
        }

        function setType(type) {
            if (type === undefined)
                type = ms.types[0];
            if (type.value === undefined)
                type = findType(type);
            currentType = type;
        }

        function getType() {
            return currentType;
        }

        function switchTypesMode(isAdvanced) {
            if (isAdvanced) {
                ms.types = getAdvancedTypes();
            } else {
                ms.types = getRegularTypes();
                setType();
            }
        }

        var currentMode = ms.modes[0];
        // var currentMode = (context.initialSearchMode ? findMode(context.initialSearchMode) : ms.modes[0]);
        var andOrFilterChangedManually = false;

        function isAndOrFilterOn() {
            return andOrFilterOn;
        }

        function setAndOrFilterOn(value, options) {
            if (value === undefined) {
                // value = context.andOrFilterOn;
                value = andOrFilterOn;
            }
            andOrFilterOn = value;
            if (options && options.manual) {
                andOrFilterChangedManually = true;
            } else {
                andOrFilterChangedManually = false;
            }
            switchTypesMode(value);
        }

        function isAndOrFilterChangedManually() {
            return andOrFilterChangedManually;
        }

        function findMode(url) {
            return _.findWhere(ms.modes, {url: url});
        }

        function setMode(url) {
            // TODO: create Mode constructor
            currentMode = findMode(url);
        }

        function getMode() {
            return currentMode;
        }

        function isBloggersMode() {
            return currentMode.mode === 'bloggers';
        }

        function shouldDisplayMode(mode, params) {
            if (typeof mode === "string") {
                mode = findMode(mode);
            }
            if (typeof params === "undefined") {
                params = $stateParams;
            }
            return mode.metaModes.indexOf(params.tab) > -1;
        }

        ms.params = null;
        var paramsChanged = false;
        var filtersOnlyChanged = false;
        var onParamsChangeHandler = function() {};

        function resetParams(options) {
            var empty = {
                filters: {
                    popularity: [],
                    engagement: null,
                    customAgeRange: null,
                    brand: [],
                    priceranges: [],
                    location: [],
                    gender: [],
                    social: null,
                    likes: null,
                    shares: null,
                    comments: null,
                    activity: null,
                    tags: [],
                    customCategories: [],
                    customOccupation: [],
                    customSex: [],
                    customEthnicity: [],
                    customTags: [],
                    customLanguage: [],
                    source: [],
                    categories: [],
                },
                keywords: [],
                keywordTypes: [],
                groupNumbers: [],
                kwIndex: 0,
                groupConcatenator: 'and_same',
                andOrFilterOn: context.andOrFilterOn,
            };
            if (options !== undefined && options.nonFilterOnly) {
                empty.filters = ms.params.filters;
            }
            setParams(empty);
        }

        function setParams(options) {
            if (options === undefined)
                return;

            var oldParams = angular.copy(ms.params);

            if (ms.params === null)
                ms.params = {};

            for (var k in options)
                ms.params[k] = angular.copy(options[k]);

            if (oldParams === null)
                return;

            var comparator = tsSearchUtils.comparator(ms.params, oldParams);

            paramsChanged = !comparator.isEqual;
            filtersOnlyChanged = comparator.isFiltersOnlyChanged;

            if (paramsChanged)
                onParamsChangeHandler(ms.params);
        }

        function getFilters() {
            if (!ms.params.filters)
                return null;

            var filters = angular.copy(ms.params.filters);

            if (!tsDateTimeRange.empty()) {
                filters.time_range = {
                    from: tsDateTimeRange.getStart(),
                    to: tsDateTimeRange.getEnd()
                };
            }

            return filters;
        }

        this.addFilter = function(name, value) {
            var extended = angular.copy(ms.params.filters);
            extended[name] = value;
            setParams({filters: extended});
        };

        this.addRegularKeyword = function(kw, type) {
            if (andOrFilterOn)
                return;
            setParams({
                keywords: ms.params.keywords.concat([kw]),
                keywordTypes: ms.params.keywordTypes.concat([type]),
                kwIndex: ms.params.kwIndex + 1
            });
        };

        this.removeRegularKeyword = function(removeIndex) {
            if (andOrFilterOn)
                return;
            setParams({
                keywords: ms.params.keywords.filter(function(value, index) { return index !== removeIndex; }),
                keywordTypes: ms.params.keywordTypes.filter(function(value, index) { return index !== removeIndex; }),
                kwIndex: ms.params.kwIndex - 1
            });
        };

        this.isKeywordApplied = function(kw, type) {
            if (!ms.params.keywords) return false;
            var idx = ms.params.keywords.indexOf(kw);
            if (idx === -1) return false;
            return ms.params.keywordTypes && ms.params.keywordTypes[idx] === type;
        };

        function isParamsChanged() {
            return paramsChanged;
        }

        function isFiltersOnlyChanged() {
            return filtersOnlyChanged;
        }

        function setOnParamsChangeHandler(handler) {
            onParamsChangeHandler = handler || function() {};
        }

        function getPage() {
            return Number($stateParams ? $stateParams.page : 1);
        }

        function setPage(page) {
            $stateParams.page = Number(page);
        }

        function goToPage(page) {
            setPage(page);
            $state.reload();
        }

        resetParams();

        // @todo: refactor this temporary shit
        var external = {
            findMode: findMode,
            setMode: setMode,
            getMode: getMode,
            shouldDisplayMode: shouldDisplayMode,
            isAndOrFilterOn: isAndOrFilterOn,
            setAndOrFilterOn: setAndOrFilterOn,
            isAndOrFilterChangedManually: isAndOrFilterChangedManually,
            findType: findType,
            setType: setType,
            getType: getType,
            setParams: setParams,
            resetParams: resetParams,
            getFilters: getFilters,
            isParamsChanged: isParamsChanged,
            isFiltersOnlyChanged: isFiltersOnlyChanged,
            isBloggersMode: isBloggersMode,
            setOnParamsChangeHandler: setOnParamsChangeHandler,
            getPage: getPage,
            setPage: setPage,
            goToPage: goToPage,
            switchTypesMode: switchTypesMode,
        };

        for (var i in external)
            this[i] = external[i];

    }])

    .service('tsKeywordExpression', ['tsMainSearch', '$state', function(tsMainSearch, $state) {
        var expression = this;

        var isComplete = true;
        var onCompleteHandler = null;

        var groups = [new Group()];

        function Group() {
            var group = this;

            function Keyword(value, type) {
                var keyword = this;

                if (value === undefined)
                    value = "";
                if (type === undefined)
                    type = "all";


                this.value = value;

                this.type = type;

                this.index = function() {
                    return group.keywordStartIndex() + group.keywords.indexOf(keyword);
                };

                this.isEmpty = function() {
                    return keyword.value.length === 0;
                };
            }

            this.keywords = [new Keyword()];

            this.addKeyword = function(value, type) {
                group.keywords.push(new Keyword(value, type, group));
            };

            this.removeKeyword = function(index) {
                if (!group.isEmpty()) {
                    group.keywords.splice(index, 1);
                    if (group.isEmpty())
                        expression.removeGroup(group.index());
                    expression.setEditing();
                }

            };

            this.index = function() {
                return groups.indexOf(group);
            };

            this.keywordStartIndex = function() {
                var sum = 1;
                for (var i = 0; groups[i] !== group; i++)
                    sum += groups[i].size();
                return sum;
            };

            this.size = function() {
                return group.keywords.length;
            };

            this.isEmpty = function() {
                return group.keywords.length === 0 || (group.keywords.length === 1 && group.keywords[0].isEmpty());
            };

            this.showParenthesis = function() {
                return group.keywords.length > 2 && groups.length > 1;
            };

            this.clear = function() {
                group.keywords = [];
            };

        }

        function GroupConcatenator(value, text) {

            this.value = function() {
                return value;
            };

            this.text = function() {
                return text;
            };
        }

        var groupConcatenators = [
            new GroupConcatenator('and_same', 'SAME POST'),
            new GroupConcatenator('and_across', 'ANY POST'),
        ];

        var groupConcatenator;

        resetGroupConcatenator();

        this.groups = groups;
        this.groupConcatenators = groupConcatenators;

        this.setGroupConcatenator = function(operation) {
            if (operation !== groupConcatenator && groups.length > 1)
                expression.setEditing();
            groupConcatenator = operation;
        };

        function resetGroupConcatenator() {
            groupConcatenator = groupConcatenators[0];
        };

        this.groupConcatenator = function() {
            return groupConcatenator;
        }

        function findGroupConcatenator(value) {
            return _.find(groupConcatenators, function(item) { return item.value() === value; });
        }

        this.isComplete = function() {
            return expression.isEmpty() || isComplete;
        };

        this.setComplete = function() {
            isComplete = true;
            if (onCompleteHandler !== null)
                onCompleteHandler();
        };

        this.setEditing = function() {
            isComplete = false;
        };

        this.setOnCompleteHanlder = function(handler) {
            onCompleteHandler = handler;
        };

        this.isEmpty = function() {
            return groups.length === 0 || (groups.length === 1 && groups[0].isEmpty());
        };

        var filtersChanged = false;

        this.setFiltersChanged = function() {
            if (!expression.isComplete()) {
                filtersChanged = true;
            }
        };

        this.isFiltersChanged = function() {
            return filtersChanged;
        };

        this.addGroup = function() {
            var group = new Group();
            groups.push(group);
            return group;
        };

        this.removeGroup = function(index) {
            if (!expression.isEmpty()) {
                groups.splice(index, 1);
            }
        };

        this.reset = function() {
            groups.splice(0, groups.length);
            groups.push(new Group());
            resetGroupConcatenator();
        };

        this.load = function() {
            var groupSet = {}, group, prevGroup;

            var keywords = tsMainSearch.params.keywords;
            var keywordTypes = tsMainSearch.params.keywordTypes;
            var groupNumbers = tsMainSearch.params.groupNumbers;

            if (keywords.length === 0) {
                expression.reset();
                return;
            }


            var concatenator = findGroupConcatenator(tsMainSearch.params.groupConcatenator);
            if (concatenator)
                expression.setGroupConcatenator(concatenator);

            groups.splice(0, groups.length);

            for (var i = 0; i < keywords.length; i++) {
                group = groupSet[groupNumbers[i]];
                if (group === undefined) {
                    groupSet[groupNumbers[i]] = group = expression.addGroup();
                    group.clear();
                    if (prevGroup)
                        prevGroup.addKeyword();
                }
                group.addKeyword(keywords[i], keywordTypes[i]);
                prevGroup = group;
            }
            if (prevGroup)
                prevGroup.addKeyword();

            filtersChanged = false;
            expression.setComplete();

        };

        this.undo = function() {
            expression.load();
        };

        function applyParams() {

            var keywords = [];
            var keywordTypes = [];
            var groupNumbers = [];
            var kwIndex = 0;

            var i = 0;

            // remove empty groups
            while (!expression.isEmpty() && i < groups.length) {
                if (groups[i].isEmpty())
                    expression.removeGroup(i);
                else
                    i++;
            }

            groups.forEach(function(group, index) {
                group.keywords.forEach(function(kw) {
                    if (!kw.isEmpty()) {
                        kwIndex++;
                        keywords.push(kw.value);
                        keywordTypes.push(kw.type.value || kw.type);
                        groupNumbers.push(index);
                    }
                });
            });

            var options = {
                keywords: keywords,
                keywordTypes: keywordTypes,
                groupNumbers: groupNumbers,
                kwIndex: kwIndex,
                groupConcatenator: expression.groupConcatenator().value(),
            };

            tsMainSearch.setParams(options);

        }

        var runHandler = function() {
            tsMainSearch.setPage(1);
            $state.reload();
        }

        this.setHandler = function(handler) {
            runHandler = handler || function() {};
        };

        this.run = function(handler) {
            applyParams();
            if (handler !== undefined)
                handler();
            else
                runHandler();
        }

    }])

    .service('tsSavedSearch', [
        '$http',
        '$q',
        '$timeout',
        '$filter',
        '$state',
        'context',
        'tsQuerySort',
        'tsKeywordExpression',
        'tsSearchUtils', function($http, $q, $timeout, $filter, $state, context, tsQuerySort, tsKeywordExpression, tsSearchUtils) {
        var main = this;

        var options = [];

        var detailsUrl = context.savedSearchDetailsUrl;
        var selected = null;
        // var selectHandler = function(selected) {
        //     $state.go('saved_search', {id: selected.value(), section: 'influencers', page: 1});
        // };
        var selectHandler;
        var resetHandler;

        main.defaultTitle = "Basic Search";

        function Option(value, name) {
            var option = this;
            var changed = false;
            var queryPromise = null;
            var advanced = false;
            var loading = false;

            this.name = function() {
                return name;
            };

            this.value = function() {
                return value;
            };

            this.originalParams = null;

            this.isChanged = function() {
                return changed;
            };

            this.setChanged = function(params) {
                if (params === undefined)
                    changed = true;
                else
                    changed = option.originalParams !== null && !tsSearchUtils.comparator(params, option.originalParams).isEqual;
            }; 

            this.resave = function(newName) {
                changed = false;
                queryPromise = null;
                rename(newName);
            };

            this.isAdvanced = function() {
                return advanced;
            };

            function rename(newName) {
                name = newName;
                update();
            };

            this.toDisplay = function() {
                return {
                    value: option.value(),
                    text: option.name(),
                    changed: option.isChanged()
                };
            };

            this.isLoading = function() {
                return loading;
            };

            this.query = function() {
                if (queryPromise === null) {
                    loading = true;
                    queryPromise = $http({
                        method: 'GET',
                        url: detailsUrl + option.value()
                    }).success(function(data) {
                        advanced = data.and_or_filter_on ? true : false;
                        loading = false;
                        return data.query;
                    });
                }
                return queryPromise;
            };
        }

        function placeholder() {
            return {
                text: !main.isEmpty() ? 'Select a saved search...' : 'No saved searches yet...',
                value: null
            };
        }

        function  back() {
            return {
                text: 'Get back to basic search',
                value: null
            };
        }

        function update() {
            main.options = [];

            // TODO: add sorting by creation date
            // $filter('orderBy')(options, function(opt) {
            //     return opt.name();
            // });

            options.forEach(function(opt) {
                if (opt !== selected)
                    main.options.push(opt.toDisplay());
            });

            main.options = _.sortBy(main.options, function (option) {
                return option.text.toLowerCase();
            });

            if (main.isActive())
                main.options.unshift(back());

            main.selected = main.isActive() ? selected.toDisplay() : placeholder();
        }

        function findOption(value) {
            return _.find(options, function(opt) { return opt.value() === value; });
        }

        function init(params) {
            options = params.savedSearchesList.map(function(item) {
                return new Option(item.id, item.name);
            });
            selected = placeholder();
            update();
        }

        main.init = init;

        this.resave = function(opt) {
            var o = findOption(opt.value);
            if (o) {
                o.resave(opt.text);
            }
        };

        this.isActive = function() {
            return selected instanceof Option;
        };

        this.select = function(opt) {
            selected = findOption(opt.value);
            update();
            $timeout(function() {
                run(selected !== undefined ? selectHandler : resetHandler);
            }, 500);
        };

        this.exit = function() {
            if (!main.isActive())
                return;
            selected = null;
            update();
            run(resetHandler);
        }

        this.go = function(value) {
            selected = findOption(value);
            update();
            return run();
        };

        this.isEmpty = function() {
            return options.length < 1;
        };

        this.title = function() {
            return main.isActive() ? selected.name() : main.defaultTitle;
        };

        this.isChanged = function() {
            return main.isActive() && selected.isChanged()
        };

        this.setChanged = function(params) {
            if (!main.isActive())
                return;
            selected.setChanged(params);
        };

        this.add = function(opt) {
            options.push(new Option(opt.value, opt.text));
            update();
        };

        var paramsHandler;
        var errorHandler;

        function applyParams(query) {

            var keyword = [];
            var keywordTypes = [];
            var groupNumbers = [];

            if (query.keyword)
                keyword = query.keyword;
            else
                keyword = [];

            if (query.keyword_types && query.keyword_types.length > 0)
                keywordTypes = query.keyword_types;
            else
                for (var i in query.keyword)
                    keywordTypes.push(query.type);

            if (query.groups && query.groups.length > 0) {
                groupNumbers = query.groups;
                var cnt = 0;
                groupNumbers[0] = 0;
                for (var n = 1; n < query.groups.length; n++) {
                    if (query.groups[n] !== query.groups[n - 1])
                        cnt++;
                    groupNumbers[n] = cnt;
                }
            } else
                for (var i in query.keyword)
                    groupNumbers.push(0);

            if (query.order_by !== undefined && query.order_by.field !== undefined) {
                // tsQuerySort.sorting.
            }

            var params = {
                filters: query.filters,
                keywords: keyword,
                keywordTypes: keywordTypes,
                groupNumbers: groupNumbers,
                kwIndex: keyword.length,
                groupConcatenator: query.group_concatenator,
                andOrFilterOn: query.and_or_filter_on,
            };

            selected.originalParams = angular.copy(params);

            return params;

        }

        function run(handler) {

            if (!main.isActive()) {
                resetHandler();
                return null;
            }

            handler = handler || function() {};

            return selected.query().then(function(data) {
                return applyParams(data.data.query);
            }).then(paramsHandler).then(handler, errorHandler);
        };

        this.run = run;

        this.setHandler = function(handler) {
            selectHandler = handler || function() {};
        };

        this.setErrorHandler = function(handler) {
            errorHandler = handler || function() {};
        };

        this.setParamsHandler = function(handler) {
            paramsHandler = handler || function() {};
        };

        this.setResetHandler = function(handler) {
            resetHandler = handler || function() {};
        };

        this.isLoading = function() {
            return main.isActive() && selected.isLoading();
        };

        // init();

    }])

    .service('tsQuerySort', [function() {
        var options = {
            keyword: [
                new Option('Sort by: Popularity'),
                new Option('Relevance', '_score'),
                // new Option('Twitter Followers', 'twitter_followers'),
                // new Option('Facebook Followers', 'facebook_followers'),
                // new Option('Instagram Followers', 'instagram_followers'),
                // new Option('Pinterest Followers', 'pinterest_followers'),
                // new Option('Youtube Followers', 'youtube_followers'),
            ]
        };
        
        var selected = {
            keyword: options.keyword[0]
        };

        this.get = function(which) {
            return selected[which].field() !== null ?
                {'field': selected[which].field(), 'order': selected[which].order()} : {};
        };
        
        this.selector = function(of, cb) {
            return new Selector(of, cb);  
        };
        
        function Option(display, field, order) {
            if (typeof field === 'undefined') {
                field = null;
                order = null;
            } else {
                if (typeof order == 'undefined') {
                    order = 'desc';
                }
            }
            
            this.field = function() {
              return field;
            };
            
            this.order = function() {
                return order;
            };
            
            this.display = function() {
                return display;
            };

            this.compare = function(option) {
                if (option instanceof Option) {
                    if (field == option.field() && order == option.order()) {
                        return true;
                    }
                }

                return false;
            };
        }

        function Selector(of, updated) {
            var selector = this;
            updated = updated | function() {};
            this.options = [];

            for (var o in options[of]) {
                this.options.push(makeopt(options[of][o]))
            }

            this.selected = makeopt(selected[of]);

            this.isSelectedByDefault = true;

            this.onSelect = function(handler) {
                updated = handler;
            };
            
            this.select = function(opt) {
                var to;

                if (opt && validopt(opt)) {
                    selector.selected = opt;
                }
                
                if (validopt(selector.selected)) {
                    to = reverseopt(selector.selected)

                    for (var o in options[of]) {
                        if (options[of][o].compare(to)) {
                            selected[of] = options[of][o]
                            break;
                        }
                    }
                }
            };

            this.update = function() {
                selector.isSelectedByDefault = false;
                selector.select();
                updated();
            };

            this.findOption = function(value) {
                for (var o in options[of]) {
                    if (options[of][o].field() === value) {
                        return makeopt(options[of][o]);
                    }
                }
                return null;
            };

            function makeopt(from) {
                return {text: from.display(), value: {field: from.field(), order: from.order()}};
            }

            function reverseopt(from) {
                return new Option(from.text, from.value.field, from.value.order);
            }

            function validopt(opt) {
                if (undef(opt, 'text') || undef(opt, 'value')) {
                    return false;
                }

                if (undef(opt.value, 'field') || undef(opt.value, 'order')) {
                    return false;
                }

                return true;
            }

            function undef(what, prop) {
                return (typeof what[prop] === 'undefined') ? true : false;
            }
        }
    }]);




    // ============================================================================
    angular.module('theshelf')

    .controller('PostAnalyticsCtrl', ['$scope', '$window', '$http', '$timeout', '$q', '$rootScope', 'context',
            function($scope, $window, $http, $timeout, $q, $rootScope, context) {

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
                    $window.location.reload();
                }
            }).error(function(data) {
                deferred.reject({data: data || 'Error!'});
            });

            return deferred.promise;
        };

        $scope.newPostUrl = null;

        $scope.toggleConversation = function(id, who, $event) {
            $scope.$broadcast('toggleConversation', id, who, $event.currentTarget || $event.srcElement);
        };

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
                ["You should only recalculate if you're wanting to generate a new ",
                "report with new data. If you just want to refresh your page to ",
                "view the progress of your post imports, just click the refresh ",
                "button on your browser."].join(""),
                yes, null, {titleText: "Are you sure?", yesText: "Recalculate", noText: "Cancel",
                    extraButtons: [
                        {title: 'Refresh', cb: function() { $window.location.href=$window.location.href }},
                    ]
                });
        };

        $scope.approvesData = {
            values: {},
            notes: {},
            updating: {},
        };

        $scope.showPreviewPopup = function() {
            $scope.$broadcast('openConfirmationPopup',
                "You are in preview mode, so you can't edit this " +
                "page. This is the report that will be sent to your " +
                "client for them to approve the influencers who they like.",
                null, null, {titleText: "Preview Mode", yesText: "OK", removeNo: true});
        };

        $scope.selectApprove = function(paId, value) {
            $scope.approvesData.updating[paId] = true;
            $http({
                method: 'POST',
                url: '/update_model/',
                data: {
                    modelName: 'InfluencerAnalytics',
                    id: paId,
                    values: {
                        tmp_approve_status: parseInt(value),
                    }
                }
            }).success(function() {
                $scope.approvesData.updating[paId] = false;
                $scope.approvesData.values[paId] = value;
            }).error(function() {
                $scope.approvesData.updating[paId] = false;
            });
        };

        $scope.changeApprove = function(paId, value, $event, options) {
            if (options && options.preview) {
                $event.preventDefault();
                $scope.showPreviewPopup();
            } else if ($scope.editingLocked) {
                $event.preventDefault();
                $scope.$broadcast('openConfirmationPopup', [
                    "<p>1. Click YES or NO for all influencers in the list. (There might be more than one page.)</p>",
                    "<p>2. At any point, you can click SAVE in the upper right to make sure you don't lose any changes.</p>",
                    "<p>3. If you want another team member to review, make sure you click the SAVE button before sharing the link with them.</p>",
                    "<p>4. When you are finished, click the SUBMIT button in order to send your results back to " +
                    (options.userFirstName && options.userFirstName.length ? options.userFirstName : "our user") + ".</p>"].join('</br>'),
                    function() {
                        $scope.makeSelections();
                        // $scope.approvesData.values[paId] = value;
                        $scope.selectApprove(paId, value);
                    }, null, {titleText: "Approval Form", htmlContent: true});
            } else {
                // $scope.approvesData.values[paId] = value;
                $scope.selectApprove(paId, value);
            }
        };

        $scope.approveLoading = false;

        $scope.approveSave = function(brandId) {
            $scope.approveLoading = true;
            $timeout(function () {
                $scope.approveLoading = false;    
            }, 2000);
            // return $http({
            //     method: 'POST',
            //     url: '/approve_report_update/',
            //     data: {
            //         'approve_status': $scope.approvesData.values,
            //         // 'notes': $scope.approvesData.notes,
            //         'brand_id': brandId,
            //     }
            // }).success(function(response) {
            //     $scope.approveLoading = false;
            //     console.log(response);
            // });
        };

        $scope.approveSaveSubmit = function(options) {
            $scope.$broadcast('openBloggerApprovalPopup', options);
        };

        $scope.submitToClient = function(options) {
            $scope.$broadcast('openBloggerApprovalPopup', options);
        };

        $scope.moreEdits = function(options) {
            angular.extend(options, {moreEdits: true});
            $scope.$broadcast('openBloggerApprovalPopup', options);
        };

        $scope.editingLocked = true;

        $scope.makeSelections = function(options) {
            if (options && options.preview) {
                $scope.showPreviewPopup();
                return;
            }
            $scope.editingLocked = false;
        };

        $scope.openAddPostAnalyticsUrlsPopup = function(options) {
            $scope.$broadcast('openAddPostAnalyticsUrlsPopup', options);
        };

        $scope.doOpenFavoritePopup = function(options) {
            $scope.$broadcast('openFavoritePopup', options)
        };

        $scope.inputKeyPress = function(keyEvent, endpoint, collectionId) {
            if (keyEvent.which === 13) {
              keyEvent.preventDefault();
              $scope.addPostUrl(endpoint, collectionId);
            }
        };

        $scope.$on('doOpenFavoritePopup', function(theirScope, options) {
            $scope.doOpenFavoritePopup(options);
        });

    }])


    .directive('postAnalyticsPanel', ['$http', '$window', 'tsConfig', function($http, $window, tsConfig) {
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
              $window.location.reload();
            }).error(function() {
              console.log('error');
            });
          };
        }
      };
    }]);
})();


(function() {

})();