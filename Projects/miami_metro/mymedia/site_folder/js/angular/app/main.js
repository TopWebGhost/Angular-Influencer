'use strict';

angular.module('tsGlobal', []);

angular.module('theshelf', [
    'ngRaven',
    'nsPopover',
    'ngResource',
    'ui.mask',
    'ui.bootstrap',
    'ngDropdowns',
    'angularFileUpload',
    'textAngular',
    'datePicker',
    'ng.daterange',
    'internationalPhoneNumber',
    'angular-bind-html-compile',
    'toggle-switch',
    'ngTablescroll',
    'fsm',
    'modelOptions',
    'restangular',
    'pdf',
    'tsGlobal',
    'isteven-multi-select',
    'wu.masonry',
    'gridshore.c3js.chart',
    // 'masonry',

    'pasvaz.bindonce',

    'fixed.table.header',
    'scrollable-table',

    'theshelf.components',
    'theshelf.bloggerPopup',
    'theshelf.filters',
    'mwl.calendar',
    'ngAnimate',
    'colorpicker.module'
])

.config(['$httpProvider', '$sceDelegateProvider', 'RestangularProvider', 'tsConfigProvider',
    function($httpProvider, $sceDelegateProvider, RestangularProvider, tsConfigProvider) {
        $httpProvider.defaults.headers.common["X-Requested-With"] = "XMLHttpRequest";
        $httpProvider.defaults.xsrfCookieName = "csrftoken";
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $sceDelegateProvider.resourceUrlWhitelist([
            'self',
            'https://syndication.twitter.com/**',
            'http://theshelf-static-files.s3.amazonaws.com/**',
            'https://theshelf-static-files.s3.amazonaws.com/**',
        ]);
        RestangularProvider.setBaseUrl('/api/v1');
    }
])

.run(['$rootScope', '$location', '$sce', '$anchorScroll', '$filter', 'tsPlatformIconClasses', 'tsViewHelper', 'tsConfig', function($rootScope, $location, $sce, $anchorScroll, $filter, tsPlatformIconClasses, tsViewHelper, tsConfig) {
    $rootScope.tsConfig = tsConfig;
    $anchorScroll.yOffset = 50;
    $rootScope.pageReload = function() {
        window.location.reload();
    };
    $rootScope.pageRedirect = function(options) {
        window.location.href = options.redirectUrl;
    };
    $rootScope.anchorScroll = function(anchorId) {
        $location.hash(anchorId);
        $anchorScroll();
    };
    $rootScope.stripFormat = function ($html) {
      return $filter('htmlToPlaintext')($html);
    };
    $rootScope.platformIcons = tsPlatformIconClasses.get;
    $rootScope.platformWrappers = tsPlatformIconClasses.getBase;
    $rootScope.angular = angular;
    $rootScope._ = _;
    $rootScope.window = window;
    $rootScope.range10 = _.range(0, 11);
    $rootScope.viewHelper = tsViewHelper;
    $rootScope.sce = $sce;
}])

.value('GoogleApp', {
    apiKey: 'AIzaSyBmbMCvRKdvN0JKjh1lq_R4dhkd3tUirlA',
    clientId: '36452609884-0nlsuotqqd1a0n4qh0epji8r2u6daii2.apps.googleusercontent.com',
    scopes: [
        'https://www.googleapis.com/auth/drive',
    ],
})

.controller('MiddleContentCtrl', ['$scope',
    function($scope) {
        $scope.selected = 'all';
    }
])

.controller('SuperCtrl', function () {
    console.log('super');
})

.controller('LandingNavBarCtrl', ['$scope',
    function($scope) {
        $scope.broadcastContactForm = function() {
            $scope.$broadcast("openContactForm");
            $scope.$emit("openContactForm");
        }
    }
])

.controller('PricingCtrl', ['$scope',
    function($scope) {
        $scope.openStripePopup = function(plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time) {
            if (!$scope.agree) {
                $scope.displayMessage();
            } else {
                $scope.$broadcast("openStripePopup", plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time);
            }
        }
        $scope.agree = true;
        $scope.displayMessage = function() {
            $scope.$broadcast("displayMessage");
        };
    }
])

.controller('AccessLockedCtrl', ['$scope',
    function($scope) {
        $scope.openCCEditPopup = function() {
            $scope.$broadcast("openCCEditPopup");
        };
        $scope.openStripePopup = function(plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time) {
            $scope.$broadcast("openStripePopup", plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time);
        }
    }
])

.controller('BloggersNavCtrl', ['$scope', function($scope) {
    var vm = this;

    $scope.openStripePopup = function(plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time) {
        $scope.$broadcast("openStripePopup", plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time);
    };
}])


.directive('navCounterTab', ['Restangular', function(Restangular) {
    return {
        restrict: 'A',
        scope: {},
        replace: true,
        template: [
            '<a ng-href="{{navCounterTabCtrl.url}}" ng-if="navCounterTabCtrl.count > 0">',
                '<span class="section_label">',
                    '{{navCounterTabCtrl.count}} {{navCounterTabCtrl.title}}',
                '</span>',
            '</a>',
        ].join(''),
        controllerAs: 'navCounterTabCtrl',
        controller: function() {
            var vm = this;

            vm.getCount = function() {
                Restangular
                    .one('influencers', vm.influencerId)
                    .customGET('posts_section_count', {
                        'section': vm.section,
                        'brand_domain_name': vm.brandDomain,
                    }).then(function(response) {
                        vm.count = response.count;
                        vm.url = response.url;
                        vm.title = response.title;
                    }, function() {
                        vm.count = 0;
                        vm.url = null;
                        vn.title = '';
                    });
            };
        },
        link: function(scope, iElement, iAttrs, ctrl) {
            ctrl.influencerId = iAttrs.influencerId;
            ctrl.section = iAttrs.section;
            ctrl.brandDomain = iAttrs.brandDomain;

            ctrl.getCount();
        } 
    };
}])


.controller('BrandHomeCtrl', ['$scope', '$rootScope', 'popup_auto_open',
    function($scope, $rootScope, popup_auto_open) {
        $scope.openLoginPopup = function() {
            $scope.$broadcast("openLoginPopup");
        }
    }
])


.controller('SavedSearchesCtrl', ['$scope', 'keywordQuery',
    function($scope, keywordQuery) {
    }
])

.directive('tooltip', function() {
    return {
        restrict: 'A',
        link: function(scope, element, attrs) {
            $(element).hover(function(){
                // on mouseenter
                $(element).tooltip('show');
            }, function(){
                // on mouseleave
                $(element).tooltip('hide');
            });
        }
    };
})


.directive('customPopup', ['$rootScope', '$timeout', 'NotifyingService', function($rootScope, $timeout, NotifyingService) {
    return {
        restrict: 'A',
        scope: true,
        controller: function($scope) {
            var ctrl = this;

            ctrl.reset = function() {
                ctrl.changed = false;
                ctrl.openOptions = null;
            };

            ctrl.updatedCb = function() {
                ctrl.changed = true;
            };

            ctrl.runTabHandler = function(newTab, oldTab) {
                if (!ctrl.tabHandlers) {
                    return;
                }

                if (ctrl.tabHandlers[oldTab] && ctrl.tabHandlers[oldTab].onExit) {
                    ctrl.tabHandlers[oldTab].onExit();
                }
                if (ctrl.tabHandlers[newTab] && ctrl.tabHandlers[newTab].onEnter) {
                    ctrl.tabHandlers[newTab].onEnter();   
                }
            };

            ctrl.setTabHandlers = function(handlers) {
                ctrl.tabHandlers = handlers;
            };

            ctrl.setTab = function(tab) {
                var newTab = (tab === null || tab === undefined ? 1 : tab);
                var oldTab = ctrl.tab;

                ctrl.tab = newTab;
                ctrl.runTabHandler(newTab, oldTab);

                $scope.$broadcast('customPopupTabChanged', {tab: newTab});
            };

        },
        controllerAs: 'customPopupCtrl',
        link: function(scope, iElement, iAttrs, ctrl) {

            scope.close_cb = function() {
                if (scope.customCloseCb) {
                    scope.customCloseCb();
                }
                if (ctrl.openOptions && ctrl.openOptions.values && ctrl.openOptions.storedValues) {
                    if (ctrl.changed) {
                        angular.copy(ctrl.openOptions.values, ctrl.openOptions.storedValues);
                    } else {
                        angular.copy(ctrl.openOptions.storedValues, ctrl.openOptions.values);
                    }
                }
                ctrl.reset();
            };

            ctrl.reset();

            if (iAttrs.openEventName !== undefined) {
                scope.$on(iAttrs.openEventName, function(their_scope, options) {
                    ctrl.openOptions = options;
                    ctrl.setTab(options.tab);
                    if (iAttrs.preventOpen === undefined) {
                        scope.open();
                    }
                    $timeout(function() {
                        NotifyingService.notify('customPopup:enter', ctrl.openOptions);
                    }, 10);
                });
            }
        }
    };
}])


.directive('editingPopup', ['$rootScope', function($rootScope) {
    return {
        restrict: 'A',
        controller: function() {
        },
        controllerAs: 'editingPopup',
        link: function(scope, iElement, iAttrs) {
        }
    };
}])


.directive('dateRangeWrapper', ['tsUtils', function(tsUtils) {
    return {
        restrict: 'A',
        scope: true,
        link: function(scope, iElement, iAttrs) {
            scope.dateRangeModel = {
                startDate: null,
                endDate: null,
            };

            scope.applyDateRange = function() {
                tsUtils.objectSetIndex(scope, iAttrs.startDateBind, moment(scope.dateRangeModel.startDate).format('YYYY-MM-DD'));
                tsUtils.objectSetIndex(scope, iAttrs.endDateBind, moment(scope.dateRangeModel.endDate).format('YYYY-MM-DD'));
            };
        }
    };
}])


.directive('nano', ['$timeout', function($timeout) {
    return {
        restrict: 'A',
        transclude: true,
        scope: true,
        template: [
            '<div class="nano" ng-cloak>',
                '<div class="content nano-content">',
                    '<div ng-transclude></div>',
                '</div>',
            '</div>',
        ].join(''),
        link: function(scope, iElement, iAttrs) {
            scope.updateNano = function(){
                $timeout(function() {
                    iElement.find('.nano').nanoScroller({alwaysVisible: true});
                    iElement.find('.nano').nanoScroller({ scroll: 'top' });
                }, 100);
            };
            scope.updateNano();

            // transclude(scope, function(clone, scope) {
            //     iElement.find('[ng-transclude]').parent().append(clone);
            //     iElement.find('[ng-transclude]').remove();
            // });
        }
    };
}])


.directive('starRating', ['$timeout', function($timeout) {
    return {
      restrict: 'EA',
      template:
        '<ul class="star-rating" ng-class="{readonly: readonly}">' +
        '  <li ng-repeat="star in stars" class="star" ng-class="{filled: star.filled}" ng-click="toggle($index)">' +
        '    <i class="fa fa-star"></i>' + // or &#9733
        '  </li>' +
        '</ul>',
      scope: {
        ratingValue: '=ngModel',
        max: '=?', // optional (default is 5)
        onRatingSelect: '&?',
        readonly: '=?'
      },
      link: function(scope, element, attributes) {
        if (scope.max == undefined) {
          scope.max = 5;
        }
        function updateStars() {
          scope.stars = [];
          for (var i = 0; i < scope.max; i++) {
            scope.stars.push({
              filled: i < scope.ratingValue
            });
          }
        };
        scope.toggle = function(index) {
          if (scope.readonly == undefined || scope.readonly === false){
            scope.ratingValue = index + 1;
            $timeout(function() {
                scope.onRatingSelect({
                  rating: index + 1
                });
            });
          }
        };
        scope.$watch('ratingValue', function(newValue, oldValue) {
          if (newValue !== null && newValue !== undefined) {
            updateStars();
          }
        });
      }
    };
}])

.directive('mainLoader', ['tsConfig', function(tsConfig) {
    return {
        restrict: 'A',
        replace: true,
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/main_loader.html'),
        link: function(scope, iElement,  iAttrs) {
        }
    };
}])

.directive('influencerStatsTable', ['$http', '$compile', function($http, $compile) {
    return {
        restrict: 'A',

        link: function(scope, iElement, iAttrs) {
            scope.sourceUrl = iAttrs.sourceUrl;
            scope.disablePostsExpand = iAttrs.disablePostsExpand !== undefined;
            scope.disableEditing = iAttrs.disableEditing !== undefined;
            scope.expandPosts = function(paId) {
                if (scope.disablePostsExpand) {
                    return;
                }
                scope.$broadcast('influencer-stats-row-click', {id: paId});
            };
        }
    };
}])

.directive('influencerStatsRow', ['$http', '$compile', function($http, $compile) {
    return {
        restrict: 'A',
        scope: true,
        link: function(scope, iElement, iAttrs) {
            scope.showPosts = false;
            scope.postsLoading = false;
            scope.paId = iAttrs.paId;

            scope.$on('influencer-stats-row-click', function(their_scope, options) {
                if (options.id != scope.paId)
                    return;
                if (!scope.showPosts) {
                    scope.showPosts = true;
                    scope.postsLoading = true;
                    $http({
                        url: scope.sourceUrl,
                        method: 'GET',
                        params: {
                            pa_id: options.id
                        }
                    }).success(function(partial) {
                        var content = $compile(partial)(scope);
                        iElement.find('td > .influencer-posts').remove();
                        iElement.find('td').append(content);
                        scope.postsLoading = false;
                    }).error(function() {
                        scope.displayMessage({message: "Error!"});
                    });
                } else {
                    scope.showPosts = false;
                    iElement.find('td > .influencer-posts').remove();
                }
            });
        }
    };
}])

.directive('postAnalyticsCell', [
    '$http',
    '$compile',
    '$rootScope',
    '$timeout',
    'context',
    'tsInvitationMessage',
    function($http, $compile, $rootScope, $timeout, context, tsInvitationMessage) {
    return {
        restrict: 'A',
        scope: true,
        controller: function() {
        },
        // controllerAs: 'Ctrl',
        link: function(scope, iElement, iAttrs) {
            scope.reload = iAttrs.reload !== undefined;
            scope.disableEditing = iAttrs.disableEditing === undefined ? scope.disableEditing : true;
            scope.localPaId = iAttrs.paId;
            $timeout(function() {
                var noteTextArea = iElement.find('.post_analytics_note');
                if (scope.approvesData) {
                    if (!scope.approvesData.values[scope.localPaId] && iAttrs.approveStatus !== undefined) {
                        scope.approvesData.values[scope.localPaId] = iAttrs.approveStatus;    
                    }
                    if (!scope.approvesData.notes[scope.localPaId] && iAttrs.influencerNote !== undefined) {
                        console.log(iAttrs.influencerNote);
                        scope.approvesData.notes[scope.localPaId] = iAttrs.influencerNote;
                    }
                }
            }, 0);
            scope.show = function(sourceUrl, options) {
                if (options && options.isBloggerApproval && options.campaignId) {
                  sourceUrl += '?campaign_posts_query=' + options.campaignId;
                }
                scope.hideOutreach = !context.isAuthenticated;
                var wrapper = angular.element("<span>");
                var elem = angular.element("<span blogger-more-info-popup url='"+sourceUrl+"'></span>");
                angular.element('#post_analytics_root').append(wrapper);
                wrapper.append(elem);
                $compile(wrapper.contents())(scope);
            };
            scope.message = function(options) {
                if (options === undefined)
                    return;
                options.context = context;
                var messageData = tsInvitationMessage.get(options);
                angular.extend(options, {
                    template: messageData.body,
                    subject: messageData.subject,
                });
                $rootScope.$broadcast('openInvitationPopup', options);
                $rootScope.$on('invitationSent', function(their_scope, options) {
                    scope.invitationSent = true;
                });
            };
        }
    };
}])



.directive('postAnalyticsUpdate', ['$http', '$filter', 'context', function($http, $filter, context) {
    return {
        restrict: 'A',
        transclude: true,
        template: [
                    '<div ng-show="showEdit" class="">',
                        '<div ng-transclude></div>',
                    '</div>',
                    '<button' + (context.previewMode ? ' preview-mode-toggler preview-mode-enabled' : '') + ' ng-show="!disableEditing && !showEdit" ng-click="open({$event: $event})" class="edit_btn pencil_btn"><span class="icon-misc_files_pencil3"></span></button>',
                    '<button ng-show="!disableEditing && showEdit" ng-click="$event.stopPropagation();close()" class="edit_btn cancel_btn"><span class="icon-letter_x04"></span></button>'
                ].join('\n'),
        controllerAs: 'editableElementCtrl',
        controller: function($scope, $attrs) {

            // @todo: should be removed ??
            $scope.dateRangeModel = {
                startDate: null,
                endDate: null,
            };
            $scope.applyDateRange = function() {
                $scope.values.startDate = moment($scope.dateRangeModel.startDate).format('YYYY-MM-DD');
                $scope.values.latestDate = moment($scope.dateRangeModel.endDate).format('YYYY-MM-DD');
                if ($attrs.updateParams) {
                    $scope.update($scope.$eval($attrs.updateParams));
                } else {
                    $scope.update({
                        start_date: $scope.values.startDate,
                        latest_date: $scope.values.latestDate
                    });
                }
            };

            $scope.save = function(options) {
                $scope.changed = true;
                $scope.close(options);
            };

            $scope.update = function(data, cb) {
                $scope.error = false;
                $scope.loading = true;
                $http({
                    method: 'POST',
                    url: $scope.targetUrl,
                    data: data
                }).success(function(response) {
                    $scope.loading = false;
                    $scope.changed = true;
                    $scope.close();
                }).error(function() {
                    $scope.changed = false;
                    $scope.loading = false;
                    $scope.error = true;
                });
            };

        },
        link: function(scope, iElement, iAttrs, ctrl, transclude) {

            scope.targetUrl = iAttrs.targetUrl;
            scope.updateOnChange = iAttrs.updateOnChange;

            scope.values = (iAttrs.valuesList === undefined ? {} : angular.fromJson(iAttrs.valuesList));
            // @TODO: migrate to use only 'ctrl' data
            ctrl.values = scope.values;

            scope.alwaysEdit = iAttrs.alwaysEdit !== undefined;

            if (scope.alwaysEdit) {
                scope.showEdit = true;
                scope.disableEditing = true;
            }

            if (scope.updateOnChange) {
                scope.$watch('values', function(nv, ov) {
                    if (nv && ov && !_.isEqual(nv, ov)) {
                        scope.update(scope.$eval(scope.updateOnChange));
                    }
                }, true);
            }

            scope.loading = false;
            scope.changed = false;
            scope.error = false;

            scope.storedValues = angular.copy(scope.values);
            // @TODO: migrate to use only 'ctrl' data
            ctrl.storedValues = scope.storedValues;

            scope.context = context;

            scope.isEditable = function () {
                if (!context.isAuthenticated)
                    return true;
                return !context.onTrial && !context.showDummyData;
            };

            ctrl.preventEditing = iAttrs.preventEditing;

            scope.open = function(options) {
                if (ctrl.preventEditing !== undefined) {
                    if (scope.previewModeCtrl) {
                        scope.previewModeCtrl.showPreviewModePopup();
                    }
                    return;
                }
                options.$event.stopPropagation();
                if (!scope.isEditable())
                    return;
                scope.showEdit = true;
            };

            ctrl.open = scope.open;
            ctrl.isEditable = scope.isEditable;

            scope.close = function(options) {
                if (scope.loading)
                    return;
                if (!scope.alwaysEdit) {
                    scope.showEdit = false;
                }
                if (options && options.values && options.storedValues) {
                    if (scope.changed) {
                        angular.copy(options.values, options.storedValues);
                    } else {
                        angular.copy(options.storedValues, options.values);
                    }
                } else {
                    if (scope.changed)
                        scope.storedValues = angular.copy(scope.values);
                    else
                        scope.values = angular.copy(scope.storedValues);
                }
                scope.changed = false;
            };  

            transclude(scope, function(clone, scope) {
                iElement.find('[ng-transclude]').parent().append(clone);
                iElement.find('[ng-transclude]').remove();
            });

        }
    };
}])


.directive('postButtons', ['tsConfig', 'context', function(tsConfig, context) {
    return {
        restrict: 'A',
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/post_buttons.html'),
        link: function(scope, iElement, iAttrs) {
            if (scope.user === undefined && scope.item !== undefined)
                scope.user = scope.item.user;
        }
    };
}])


.directive('bloggerButtons', ['tsConfig', 'context', function(tsConfig, context) {
    return {
        restrict: 'A',
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/blogger_buttons.html'),
        link: function(scope, iElement, iAttrs) {
            if (scope.user === undefined && scope.item !== undefined)
                scope.user = scope.item.user;
        }
    };
}])


.directive('imageonload', ['$timeout', function($timeout) {
    return {
        restrict: 'A',
        controller: function() {
            var vm = this;
        },
        controllerAs: 'imageonloadCtrl',
        link: function(scope, element, attrs, ctrl) {

            ctrl.errorHandler = function() {
                element.parent().hide();
            };

            ctrl.loadHandler = function() {
                var image = new Image();

                image.onload = function() {
                    var ext = element.attr('src').split('.').pop();
                    if (this.width < 100 || this.height < 100 || ext === 'gif')
                        element.parent().hide();
                    image = null;
                };

                image.onerror = function() {
                    image = null;
                };

                image.src = element.attr('src');
            };

            element.bind('error', ctrl.errorHandler);
            element.bind('load', ctrl.loadHandler);

            scope.$on('$destroy', function() {
                element.off('error', ctrl.errorHandler);
                element.off('load', ctrl.loadHandler);
            });
        }
    };
}])


.directive('notifyOnLoad', ['$timeout', '$parse', 'NotifyingService', 'DebouncedEventService',
        function($timeout, $parse, NotifyingService, DebouncedEventService) {
    return {
        restrict: 'A',
        controller: function() {
            var vm = this;
        },
        controllerAs: 'notifyOnLoadCtrl',
        link: function(scope, iElement, iAttrs, ctrl) {
            if (!iAttrs.notifyOnLoad.length)
                return;

            ctrl.handler = function() {
                $timeout(function() {
                    DebouncedEventService.notify(iAttrs.notifyOnLoad, null, 300);
                    // NotifyingService.notify(iAttrs.notifyOnLoad);
                }, 10);
            };

            iElement.bind('error', ctrl.handler);
            iElement.bind('load', ctrl.handler);

            scope.$on('$destroy', function() {
                iElement.off('error', ctrl.handler);
                iElement.off('load', ctrl.handler);
            });
        }
    };
}])

.directive('bgImage', ['$timeout', function($timeout) {
    return {
        scope: true,
        template: [
            '<div main-loader ng-show="spinner && !loaded"></div>',
            // '<div class="bg-image-content" style="width: 100%; height: " ng-show="loaded"></div>',
        ].join(''),
        controller: function() {
            var vm = this;
        },
        controllerAs: 'bgImageCtrl',
        link: function(scope, iElement, iAttrs) {
            if (iAttrs.defaultImage) {
                scope.defaultImage = iAttrs.defaultImage;
            } else {
                scope.defaultImage = 'https://s3.amazonaws.com/influencer-images/2354181profile_image.jpg.small.jpg';
            }
            scope.hideOnError = iAttrs.hideOnError !== undefined;
            scope.hideParent = iAttrs.hideParent !== undefined;
            scope.spinner = iAttrs.spinner !== undefined;
            scope.loaded = false;

            iAttrs.$observe('bgImage', function() {
                if (!iAttrs.bgImage) {
                    if (!scope.spinner) 
                        iElement.css("background-image", "url(" + scope.defaultImage + ")");
                } else {
                    var image = new Image();
                    image.onload = function() {
                        iElement.css("background-image", "url(" + iAttrs.bgImage + ")");
                        scope.$apply(function() {
                            scope.loaded = true;
                        });
                        image = null;
                        // $timeout(function() {
                        //     image.src = '';
                        //     image = null;
                        // }, 2000);
                    };
                    image.onerror = function() {
                        scope.$apply(function() {
                            scope.loaded = true;
                        });
                        if (scope.hideOnError) {
                            if (scope.hideParent) {
                                iElement.parent().hide();
                            } else {
                                iElement.hide();
                            }
                        } else {
                            iElement.css("background-image", "url(" + scope.defaultImage + ")");
                        }
                        image = null;
                        // $timeout(function() {
                        //     image.src = '';
                        //     image = null;
                        // }, 2000);
                    }
                    image.src = iAttrs.bgImage;
                }
            });
        }
    };
}])

.directive('morrisArea', function(LazyData, $compile) {
    return {
        restrict: 'A',
        replace: true,
        template: '<div style="margin: 0px auto;"></div>',
        // scope: {
        //   data: '=',
        //   xkey: '@',
        //   ykeys: '=',
        //   labels: '=',
        //   lineColors: '='  
        // },
        link: function(scope, element, attrs) {
            var donut_formatter = function(y, data){
              return data.value + " / " + data.percentage + "%";
            }

            LazyData.getPromise().then(function(data) {
                scope.stats = data;

                if (scope.stats.popularity_stats && scope.stats.popularity_sums) {
                  try {
                      var followers_ykeys = [];
                      var followers_labels = [];
                      var comments_ykeys = [];
                      var comments_labels = [];
                      var socialLineColors = [];
                      var social_colors = {
                        'twitter': '#00adf2',
                        'facebook': '#2d58a4',
                        'instagram': '#d0bf01',
                        'pinterest': '#c92320'
                      };
                      for(var idx = 0; idx < scope.stats.popularity_stats.series.length; idx++){
                          var serie = scope.stats.popularity_stats.series[idx];
                          if (!scope.stats.popularity_sums[serie.key])
                            continue;
                          if (scope.stats.popularity_sums[serie.key]["followers"] > 0) {
                              followers_ykeys.push(serie.key+"_num_followers");
                              followers_labels.push(serie.label+" followers");
                              socialLineColors.push(social_colors[serie.key.split('_')[0]]);
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

                        var chartData = {
                          element: element,
                          data: scope.stats.popularity_stats.followers_data,
                          xkey: 'date',
                          ykeys: followers_ykeys,
                          labels: followers_labels,
                          lineColors: socialLineColors,
                          pointSize: 0,
                          lineWidth: 1,
                          hideHover: true,
                          fillOpacity: 0.1,
                          smooth: false,
                          behaveLikeLine: true,
                        };

                        try {
                          Morris.Area(chartData);
                        } catch(e) {console.log('3', e);};
                        $compile(element.parent('.blog_stat_block'))(scope);
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
        }
    };
})

.factory('LazyData', function($q, $timeout, $http) {
    var deferred = $q.defer();
    var handler, url, time;

    var outputDeferred = $q.defer();

    var setHandler = function(func, time, url) {
        handler = func;
        url = url;
        time = time;
    };

    var getPromise = function() {
        return outputDeferred.promise;
    };

    var getData = function(handler, url) {
        $http({
            url: url,
            method: 'GET',
            timeout: deferred.promise
        }).success(function(data) {
            outputDeferred.resolve(data);
            deferred.resolve();
            deferred = null;
            handler(data);
        });
    };

    var startTimer = function(func, time, url) {
        setHandler(func, time, url);
        $timeout(function() {
            if (deferred !== null) {
                deferred.resolve();
                getData(func, url);
            }
        }, 20000);
        getData(func, url);
    };

    return {
        setHandler: setHandler,
        getPromise: getPromise,
        getData: getData,
        startTimer: startTimer
    };
})

// should be removed later on
.directive('imgfit', [
    function() {
        return {
            restrict: 'C',
            link: function(scope, iElement, iAttrs) {
                if (iAttrs.skip !== undefined) return;
                var calc_other_dim = false;
                if (iAttrs.keepAspect !== undefined) {
                    calc_other_dim = true;
                }
                var fitfn = function() {
                    if (iElement.data('fit_appliend') == true) {
                        return;
                    }
                    var imgWidth = iElement[0].naturalWidth;
                    var imgHeight = iElement[0].naturalHeight;
                    if (imgWidth == 0 || imgHeight == 0) {
                        iElement.load(fitfn);
                        return;
                    }
                    iElement.data('fit_appliend', true);
                    var containerWidth, containerHeight;
                    var parent = iElement.parent();
                    var steps = 0;
                    do {
                        containerWidth = parent.width();
                        containerHeight = parent.height();
                        parent = parent.parent();
                        steps++;
                        if (steps > 10) {
                            console.log("imgfit: failed, no parent container with sizes specified");
                            return;
                        }
                    } while (!containerHeight || !containerWidth);
                    if (iElement.css("width")
                        .substr(-2, 2) !== "px") {
                    }
                    if (iElement.css("height")
                        .substr(-2, 2) !== "px") {
                    }
                    if (imgWidth == containerWidth || imgHeight == containerHeight) {
                    }
                    var aspect = imgWidth / imgHeight;
                    var cont_aspect = containerHeight / containerWidth;
                    if (isNaN(aspect) || isNaN(cont_aspect)) {
                        console.log("imgfit: failed, cant calculate aspect", imgWidth, imgHeight, containerWidth, containerHeight);
                        return;
                    }
                    iElement.css("position", "relative");
                    if (aspect < 1) {
                        var scale = containerHeight / imgHeight;
                        var offset = Math.min(0, (containerWidth - imgWidth * scale) / 2);
                        if (imgWidth * scale < containerWidth) {
                            scale = containerWidth / imgWidth;
                            offset = Math.min(0, (containerHeight - imgHeight * scale) / 2);
                            iElement.css("top", offset);
                        } else {
                            iElement.css("left", offset);
                        }
                        iElement.css("height", imgHeight * scale);
                        if (calc_other_dim) {
                            iElement.css("width", imgWidth * scale);
                        }
                    } else {
                        var scale = containerWidth / imgWidth;
                        var offset = Math.min(0, (containerHeight - imgHeight * scale) / 2);
                        if (imgHeight * scale < containerHeight) {
                            scale = containerHeight / imgHeight;
                            offset = Math.min(0, (containerWidth - imgWidth * scale) / 2)
                            iElement.css("left", offset);
                        } else {
                            iElement.css("top", offset);
                        }
                        iElement.css("width", imgWidth * scale);
                        if (calc_other_dim) {
                            iElement.css("height", imgHeight * scale);
                        }
                    }
                    iElement.wrap($("<div style='width: " + containerWidth + "px; height: " + containerHeight + "px; overflow: hidden'></div>"))
                };
                setTimeout(fitfn, 0);
                $(window).resize(function(){
                    if(iElement.data('fit_appliend') == true){
                        iElement.unwrap();
                    }
                    iElement.data('fit_appliend', false);
                    fitfn();
                });
            }
        };
    }
])


.directive('aHref', ['$window', function($window) {
    return {
        restrict: 'A',
        controller: function() {
            var vm = this;
        },
        controllerAs: 'aHrefCtrl',
        link: function(scope, iElement, iAttrs, ctrl) {
            ctrl.clickHandler = function($event) {
                if (iAttrs.prevent) {
                    $event.preventDefault();
                    $event.stopPropagation();
                }
                if (iAttrs.skip !== undefined) {
                    $event.stopPropagation();
                } else if (iAttrs.direct !== undefined) {
                    $window.location.assign(iAttrs.aHref);
                } else {
                    $window.open(iAttrs.aHref, '_blank');
                }
            };

            iElement.bind('click', ctrl.clickHandler);

            scope.$on('$destroy', function() {
                iElement.off('click', ctrl.clickHandler);
            });
        }
    };
}])

.directive('eventReactor', [
    function() {
        return {
            restrict: 'A',
            scope: {
                'callback': '&'
            },
            link: function(scope, iElement, iAttrs) {
                scope.$on(iAttrs.eventReactor, function() {
                    scope.callback();
                });
            }
        };
    }
])

.directive('clickEmitter', ['$rootScope',
    function($rootScope) {
        return {
            restrict: 'A',
            link: function(scope, iElement, iAttrs) {
                iElement.click(function() {
                    $rootScope.$apply(function() {
                        if (iAttrs.args !== undefined) {
                            var args = JSON.parse(iAttrs.args);
                            $rootScope.$broadcast(iAttrs.clickEmitter, args);
                            $rootScope.$emit(iAttrs.clickEmitter, args);
                        } else {
                            $rootScope.$broadcast(iAttrs.clickEmitter);
                            $rootScope.$emit(iAttrs.clickEmitter);
                        }
                    });
                });
            }
        };
    }
])


.directive('broadcaster', ['$rootScope', function($rootScope) {
    return {
        restrict: 'A',
        controller: function() {
            this.broadcast = function(eventName, options) {
                $rootScope.$broadcast(eventName, options || {});
            };
        },
        controllerAs: 'broadcasterCtrl',
    };
}])


.directive('confirmationPopup', ['$http', '$sce', 'tsConfig',
    function($http, $sce, tsConfig) {
        return {
            restrict: 'A',
            scope: {},
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/confirmation_popup.html'),
            link: function(scope, iElement, iAttrs) {
                scope.yesText = 'Yes';
                scope.noText = 'No';
                scope.titleText = 'Please Confirm';

                scope.$on('openConfirmationPopup', function(their_scope, message, yes_cb, no_cb, options) {
                    scope.setBackgroundType(null);
                    if (options !== undefined) {
                        scope.yesText = options.yesText || scope.yesText;
                        scope.noText = options.noText || scope.noText;
                        scope.titleText = options.titleText || scope.titleText;
                        scope.extraButtons = options.extraButtons || [];
                        scope.loading = options.loading || true;
                        scope.workingText = options.loadingText;
                        scope.removeYesButton = options.removeYes;
                        scope.removeNoButton = options.removeNo;
                        scope.htmlContent = options.htmlContent;
                    }
                    scope.message = scope.htmlContent ? $sce.trustAsHtml(message) : message;
                    scope.yes_cb = yes_cb;
                    scope.no_cb = no_cb;
                    scope.open();
                });

                scope.yes = function() {
                    if (scope.yes_cb === null) {
                        scope.close();
                        return;
                    }
                    scope.setState('working');
                    scope.setBackgroundType('black');
                    var result_promise = scope.yes_cb();
                    if (result_promise === undefined) {
                        scope.setBackgroundType(null);
                        scope.close();
                        return;
                    }
                    result_promise.then(scope.close, function(data) {
                        scope.setBackgroundType(null);
                        scope.setState('error');
                        scope.error = $sce.trustAsHtml(data.data);
                    });
                };

                scope.no = function() {
                    if (scope.no_cb === null) {
                        scope.close();
                        return;
                    }
                    scope.setState('working');
                    scope.setBackgroundType('black');
                    var result_promise = scope.no_cb();
                    if (result_promise === undefined) {
                        scope.setBackgroundType(null);
                        scope.close();
                        return;
                    }
                    result_promise.then(scope.close, function(data) {
                        scope.setBackgroundType(null);
                        scope.setState('error');
                        scope.error = $sce.trustAsHtml(data.data);
                    });
                };
            }
        };
    }
])

.directive('confirm', ['$http', '$sce', 'tsConfig',
    function($http, $sce, tsConfig) {
        return {
            restrict: 'A',
            scope: {
                yesCb: "&",
                noCb: "&",
            },
            transclude: true,
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/confirmable_link_popup.html'),
            link: function(scope, iElement, iAttrs) {
                scope.title = iAttrs.confirmTitle;
                scope.message = iAttrs.message;
                scope.waitResult = iAttrs.waitResult !== undefined;
                var bind = function(){
                    iElement.find('.transcluded').click(function(){
                        scope.$apply(function(){
                            scope.open();
                        });
                        return false;
                    });
                };
                scope.no = function(){
                    if(iAttrs.noUrl !== undefined){
                        scope.setState('working');
                        $http({
                            method: 'POST',
                            url: iAttrs.noUrl
                        }).success(function(){
                            if(scope.waitResult){
                                if(iAttrs.thenUrl !== undefined){
                                    scope.setState('done');
                                    window.location.assign(iAttrs.thenUrl);
                                };
                                if(scope.noCb !== undefined){
                                    scope.close();
                                    scope.noCb(false);
                                };
                            }
                        }).error(function(){
                            if(scope.waitResult){
                                scope.setState('error');
                            }
                        });
                        if(!scope.waitResult){
                            if(iAttrs.thenUrl !== undefined){
                                window.location.assign(iAttrs.thenUrl);
                            };
                            if(scope.noCb !== undefined){
                                scope.close();
                                scope.noCb(false);
                            };
                        }
                    }else{
                        scope.close();
                    }
                };
                scope.yes = function(){
                    if(iAttrs.yesUrl !== undefined){
                        scope.setState('working');
                        $http({
                            method: 'POST',
                            url: iAttrs.yesUrl
                        }).success(function(){
                            if(scope.waitResult){
                                if(iAttrs.thenUrl !== undefined){
                                    scope.setState('done');
                                    window.location.assign(iAttrs.thenUrl);
                                };
                                if(scope.yesCb !== undefined){
                                    scope.close();
                                    scope.yesCb(true);
                                };
                            }
                        }).error(function(){
                            if(scope.waitResult){
                                scope.setState('error');
                            }
                        });
                        if(!scope.waitResult){
                            if(iAttrs.thenUrl !== undefined){
                                window.location.assign(iAttrs.thenUrl);
                            };
                            if(scope.yesCb !== undefined){
                                scope.close();
                                scope.yesCb(true);
                            };
                        }
                    }else{
                        scope.close();
                    }
                };
                setTimeout(bind, 10);
            }
        };
    }
])

.directive('formHandler', ['$timeout', function($timeout) {
    return {
        restrict: 'A',
        link: function(scope, iElement, iAttrs) {
            $timeout(function() {
                if (scope.registerFormScope) {
                    scope.registerFormScope(scope[iAttrs.name], iAttrs.formHandler.length ? iAttrs.formHandler : iAttrs.name, scope.$id);
                }
            });
        }
    };
}])

.directive('trackMe', [
    function() {
        return {
            restrict: 'A',
            scope: true,
            link: function(scope, iElement, iAttrs) {
                // iElement.bind(iAttrs.event, function() {
                    //Intercom('trackEvent', iAttrs.name, JSON.parse(iAttrs.meta));
                // });
            }
        };
    }
])

.directive('checkboxSelect', ['tsConfig', function (tsConfig) {
    return {
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/checkbox_select.html'),
        restrict: 'A',
        scope: {
            options: '='
        },
        transclude: true,
        link: function postLink(scope, iElement, iAttrs) {
            scope.active = false;
            setTimeout(function() {
                var ignore_blur = false;
                iElement.click(function(){
                    iElement.find('input').focus();
                });
                iElement.find('.dropdown-item').mouseenter(function(){
                    ignore_blur = true;
                });
                iElement.find('.dropdown-item').mouseleave(function(){
                    ignore_blur = false;
                });
                iElement.find('input').focus(function(){
                    scope.$apply(function(){
                        scope.active = true;
                    });
                });
                iElement.find('input').blur(function(){
                    if(ignore_blur) return;
                    scope.$apply(function(){
                        scope.active = false;
                    });
                });
            }, 10);
            scope.isSelected = function(option){
                return option.checked;
            };
            scope.toggle = function(option){
                if(option.disabled) return;
                option.checked = !option.checked;
                scope.$emit('checkboxSelectOptionToggled', option);
            };
        }
    };
}])

.directive('matchBrand', [ '$timeout', '$http', 'tsConfig',
    function($timeout, $http, tsConfig) {
        return {
            restrict: 'A',
            scope: true,
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/brand_matcher.html'),
            link: function(scope, iElement, iAttrs) {
                scope.placeholder = iAttrs.placeholder;
                scope.autocomplete_timeout = null;
                scope.result = null;
                scope.loading = false;
                var can_blur = true;

                scope.doAutocomplete = function() {
                    if(!scope.brand_url) return;
                    scope.term = scope.brand_url;
                    scope.autocomplete_message = "Loading...";
                    scope.autocomplete_results = null;
                    scope.loading = true;
                    $http({
                        url: iAttrs.matchBrand + "?term=" + scope.term,
                        method: "GET"
                    }).success(function(data) {
                        scope.autocomplete_results = data;
                        scope.autocomplete_message = null;
                        scope.loading = false;
                    }).error(function() {
                        scope.autocomplete_message = "Error!";
                        scope.autocomplete_results = null;
                        scope.loading = false;
                    });
                }

                scope.startAutocompleteTimeout = function() {
                    if (scope.autocomplete_timeout !== null) {
                        $timeout.cancel(scope.autocomplete_timeout);
                    }
                    scope.autocomplete_timeout = $timeout(scope.doAutocomplete, 500);
                }

                scope.selectResult = function(result) {
                    scope.result = result;
                    scope.brand_url = result.url;
                    scope.$emit("brandSelected", angular.copy(result));
                    iElement.find(".brand-autocomplete").fadeOut(500);
                }
                setTimeout(function() {
                    iElement.keyup(function(){
                        scope.result = null;
                        if(scope.brand_url == ""){
                          if(scope.loading) return false;
                          scope.$emit("brandSelected", null);
                          scope.autocomplete_message = null;
                          scope.autocomplete_results = null;
                        }else{
                          scope.startAutocompleteTimeout();
                        }
                    });
                    iElement.find("input").click(function(e){
                      if(scope.autocomplete_results){
                        iElement.find(".brand-autocomplete").fadeIn(100);
                      }
                      if(scope.autocomplete_message){
                        iElement.find(".brand-autocomplete-message").fadeIn(100);
                      }
                    });
                    iElement.find("input").blur(function(e){
                        if(!can_blur) return;
                        if(scope.loading) return false;
                        iElement.find(".brand-autocomplete").fadeOut(500);
                        iElement.find(".brand-autocomplete-message").fadeOut(500);
                        if (scope.autocomplete_timeout !== null) {
                          $timeout.cancel(scope.autocomplete_timeout);
                          scope.autocomplete_timeout = null;
                        }
                        $timeout(function(){
                        if(iAttrs.canSetOwn !== undefined){
                            var result;
                            if(scope.result){
                                result = scope.result;
                            }else{
                                result = {
                                    name: null,
                                    url: scope.brand_url
                                };
                            }
                            scope.$emit("brandSelected", angular.copy(result));
                        }
                        }, 10);
                    });
                    iElement.mouseenter(function(){
                        can_blur=false;
                    });
                    iElement.mouseleave(function(){
                        can_blur=true;
                    });
                }, 100);
            }
        };
    }
])

.directive('dotdotdot', function() {
    return {
        restrict: 'A',
        link: function(scope, iElement, iAttrs) {
            scope.$watch(function() {
                iElement.dotdotdot({
                    watch: true
                });
            });
        }
    };
})


.directive('requestButton', ['$http', '$timeout', function($http, $timeout) {
    return {
        restrict: 'A',
        scope: true,
        controllerAs: 'requestButtonCtrl',
        controller: function() {
            var ctrl = this;

            ctrl.loading = false;
            ctrl.loaded = false;
            ctrl.reloading = false;
            ctrl.doRequest = function(options) {
                if (ctrl.loading || ctrl.reloading) {
                    return;
                }
                ctrl.loading = true;
                ctrl.loaded = false;
                return $http({
                    url: options.url,
                    method: options.method,
                    data: options.data,
                }).success(function(response) {
                    ctrl.loading = false;
                    ctrl.loaded = true;
                    if (options.successCb) {
                        options.successCb(options.successCbParams ? options.successCbParams : response);
                    }
                    return response;
                }).error(function() {
                    ctrl.loading = false;
                    ctrl.loaded = true;
                });
            };

            function Dropdown(list) {
                var self = this;
                self.getParams = null;

                self.options = list.options;
                self.selected = _.findWhere(list.options, {value: list.selected});

                self.options.splice(self.options.indexOf(self.selected), 1)

                self.update = function(selected) {
                    self.selected = selected;
                    if (self.getParams) {
                        var params = self.getParams();
                        ctrl.doRequest(params).then(function() {
                            if (params.dropdownCb) {
                                params.dropdownCb(selected);
                            }
                        })
                    }
                }
            }

            ctrl.Dropdown = Dropdown;
            ctrl.pageReload = function() {
                ctrl.reloading = true;
                window.location.reload();
            };
        },
        link: function(scope, iElement, iAttrs, ctrl) {
            if (iAttrs.sendParams) {
                $timeout(function() {
                    if (iAttrs.dropdown) {
                        scope.dropdown = new ctrl.Dropdown(scope.$eval(iAttrs.dropdown));
                        scope.dropdown.getParams = function() {
                            return scope.$eval(iAttrs.sendParams);
                        };
                        // self.dropdown.placeholder = function() {
                        //     return scope.$eval(iAttrs.dropdownPlaceholder);
                        // };
                    } else {
                        scope.sendParams = scope.$eval(iAttrs.sendParams);
                    }
                }, 0);
            }
        }
    };
}])


.directive('genericTable', [function() {
    return {
        restrict: 'A',
        templateUrl: '',
        replace: true,
        controller: function() {

        },
        link: function(scope, iElement, iAttrs, ctrl) {

        }
    };
}])


.directive('influencerInfo', ['$rootScope', 'tsPlatformIconClasses', 'tsConfig',
        function($rootScope, tsPlatformIconClasses, tsConfig) {
    return {
        restrict: 'A',
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/influencer_info.html'),
        replace: true,
        scope: true,
        controller: function() {
            var vm = this;

            vm.canEdit = function() {
                return true;
            };

            vm.openEditPopup = function(options) {
                $rootScope.$broadcast('openInfluencerDataPopup', options);
            };
        },
        controllerAs: 'influencerInfoCtrl',
        link: function(scope, iElement, iAttrs, ctrl) {
            scope.platformIcon = tsPlatformIconClasses.get;
        }
    };
}])


.directive('platformInfo', ['tsPlatformIconClasses', 'tsConfig', function(tsPlatformIconClasses, tsConfig) {
    return {
        restrict: 'A',
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/platform_info.html'),
        scope: true,
        link: function(scope, iElement, iAttrs) {
            scope.platformIcon = tsPlatformIconClasses.get;
            // scope.platform = scope.blogger.platforms[0] if scope.blogger.platforms else null;
            scope.platformName = iAttrs.platformName;
            scope.platforms = scope.influencer.platforms.filter(function(pl) { return pl.platform_name == scope.platformName && pl.show_on_feed; });
            scope.platform = scope.platforms.length > 0 ? scope.platforms[0] : null;
        }
    };
}])


.directive('sendInviteButton', ['$rootScope', 'context', 'tsInvitationMessage', function($rootScope, context, tsInvitationMessage) {
    return {
        restrict: 'A',
        link: function(scope, iElement, iAttrs) {
            scope.forceInvite = parseInt(iAttrs.forceInvite);
            scope.message = function(options) {
                if (options === undefined)
                    return;
                options.context = context;
                var messageData = tsInvitationMessage.get(options);
                angular.extend(options, {
                    template: messageData.body,
                    subject: messageData.subject,
                });
                $rootScope.$broadcast('openInvitationPopup', options);
            };
        }
    };
}])

// .directive('radioChoice', [function() {
//     return {
//         restrict: 'A',
//         templateUrl: tsConfig.wrapTemplate('js/angular/templates/radio_choice.html'),
//         link: function 
//     }; 
// }])

.directive('wysiwygEditor', ['$timeout', 'tsConfig', function($timeout, tsConfig) {
    return {
        restrict: 'A',
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/wysiwyg_editor.html'),
        replace: true,
        controller: function($scope, $element) {
            var tabindex = $element.attr('tabindex');
            $element.removeAttr('tabindex');
            $scope.textAreaSetup = function($element) {
                $element.attr('tabindex', tabindex);
                $element.css('height', '100%');
            };
        }
    };
}])

.directive('uploadPanel', ['FileUploader', 'context', 'tsConfig', function(FileUploader, context, tsConfig) {
    return {
        restrict: 'A',
        templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/upload_panel.html'),
        replace: true,
        transclude: true,
        link: function(scope, iElement, iAttrs, ctrl, transclude) {
            scope.selectFile = function() {
                iElement.find('input[type=file]').click();
            };

            transclude(scope, function(clone, scope) {
                if (clone.length) {
                    iElement.find('[ng-transclude]').parent().append(clone);
                    iElement.find('[ng-transclude]').remove();
                    scope.defaultUploadPanel = false;
                } else {
                    scope.defaultUploadPanel = true;
                }
            });
        }
    };
}])

;

(function() {

    var genericUploadPopupLogic = function($timeout, $q, FileUploader, context) {
        return function(scope, iElement, iAttrs) {
            scope.formatAttachments = function(attachments) {
                if (attachments === undefined || attachments === null)
                    return [];
                return attachments.map(function(item) { return item.response; });
            };
        };
    };

    var generic_popup_logic = function($timeout) {
        return function(scope, iElement, iAttrs) {
            scope.no_close = iAttrs.noClose !== undefined;
            scope.no_close_outside = $(iElement.parent()).attr("no-close-outside") !== undefined;
            scope.visible = false;
            if (iAttrs.layer !== undefined) {
                scope.layer = 10 * Number(iAttrs.layer);
            } else {
                var layer_elem = iElement.closest('[layer]');
                if (layer_elem.length) {
                    scope.layer = 10 * Number(layer_elem.attr('layer'));
                } else {
                    scope.layer = 10;
                }
            }

            scope.state = "unknown";
            scope.extraClasses = iAttrs.extraClass;

            scope.setBackgroundType = function(type) {
                scope.backgroundType = type;
            };

            scope.setNoClose = function(nc){
                scope.no_close = nc;
            };
            scope.open = function() {
                scope.visible = true;
                scope.state = "opened";
                if(scope.no_close_outside !== true){
                    setTimeout(function() {
                        $(iElement.find('.container'))
                            .click(function(evt) {
                                if (evt.target === evt.currentTarget) {
                                    scope.$apply(scope.close);
                                }
                            });
                    }, 10);
                }
                scope.open_cb && $timeout(scope.open_cb, 100);
            };
            scope.close = function() {
                if(scope.no_close){
                    return;
                }
                scope.visible = false;
                scope.close_cb && $timeout(scope.close_cb, 0);
            };
            scope.forceClose = function() {
                scope.visible = false;
            };
            scope.setState = function(state) {
                scope.state = state;
            };

            if (iAttrs.autoOpenDelay !== undefined) {
                $timeout(function() {
                    scope.open()
                }, Number(iAttrs.autoOpenDelay));
            }
        };
    };

    angular.module('theshelf')
        .directive('blankPopup', ['$timeout', 'tsConfig',
            function($timeout, tsConfig) {
                return {
                    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/templates/blank_popup.html'),
                    transclude: true,
                    replace: true,
                    restrict: 'A',
                    link: generic_popup_logic($timeout)
                };
            }
        ])
        .directive('genericPopup', ['$timeout', 'tsConfig',
            function($timeout, tsConfig) {
                return {
                    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/templates/generic_popup.html'),
                    transclude: true,
                    replace: true,
                    restrict: 'A',
                    link: generic_popup_logic($timeout)
                };
            }
        ])
        .directive('genericUploading', ['$timeout', '$q', 'FileUploader', 'context',
            function($timeout, $q, FileUploader, context) {
                return {
                    replace: true,
                    restrict: 'A',
                    link: genericUploadPopupLogic($timeout, $q, FileUploader, context)
                };
            }])
        .directive('blackBackgroundPopup', ['$timeout', 'tsConfig',
            function($timeout, tsConfig) {
                return {
                    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/templates/black_background.html'),
                    transclude: true,
                    replace: true,
                    restrict: 'A',
                    link: generic_popup_logic($timeout)
                };
            }
        ])
        .directive('borderlessBlackPopup', ['$timeout', 'tsConfig',
            function($timeout, tsConfig) {
                return {
                    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/templates/borderless_black_bg.html'),
                    transclude: true,
                    replace: true,
                    restrict: 'A',
                    link: generic_popup_logic($timeout)
                };
            }
        ])
        .directive('fixedWhiteBackgroundPopup', ['$timeout', 'tsConfig',
            function($timeout, tsConfig) {
                return {
                    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/templates/fixed_white_bg.html'),
                    transclude: true,
                    replace: true,
                    restrict: 'A',
                    link: generic_popup_logic($timeout)
                };
            }
        ])
        .directive('whiteBackgroundPopup', ['$timeout', 'tsConfig',
            function($timeout, tsConfig) {
                return {
                    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/templates/white_background.html'),
                    transclude: true,
                    replace: true,
                    restrict: 'A',
                    link: generic_popup_logic($timeout)
                };
            }
        ])
        .directive('uploadList', ['tsConfig', function(tsConfig) {
            return {
                templateUrl: tsConfig.wrapTemplate('js/angular/templates/upload_list.html'),
                replace: true,
                restrict: 'A'
            };
        }])
        .directive('affixed', function() {
            return {
                restrict: 'A',
                link: function(scope, iElement, iAttrs) {
                    iElement.affix({
                        offset: {
                            top: 0
                        }
                    });
                }
            };
        })
        .directive('sortingRow', [function() {
            return {
                link: function(scope, iElement, iAttrs) {
                    var sortDirection = iAttrs.sortDirection === undefined ? 0 : parseInt(iAttrs.sortDirection);
                    if (iAttrs.sortBy !== undefined) {
                        angular.element(iElement.find('th')[iAttrs.sortBy - 1])
                            .addClass(sortDirection == 0 ? 'sorting_asc' : 'sorting_desc');
                    }

                    iElement.find('th').on('click', function() {
                        var elem = angular.element(this);
                        if (elem.hasClass('sorting_asc')) {
                            iElement.find('th').removeClass('sorting_asc sorting_desc');
                            elem.addClass('sorting_desc');
                        } else if (elem.hasClass('sorting_desc')) {
                            iElement.find('th').removeClass('sorting_asc sorting_desc');
                            elem.addClass('sorting_asc');
                        } else {
                            iElement.find('th').removeClass('sorting_asc sorting_desc');
                            elem.addClass('sorting_asc');
                        }
                    });
                }
            };
        }])
        .directive('sortingColumn', [function() {
            return {
                link: function(scope, iElement, iAttrs) {
                    iElement.on('click', function() {
                        window.location.replace(iAttrs.refreshParams);
                    });
                }
            };
        }])

        .directive('tagsEditing', ['$http', '$q', '$window', 'context', function($http, $q, $window, context) {
          return {
            restrict: 'A',
            link: function($scope, iElement, iAttrs) {
              $scope.addCollection = function(){
                $scope.$broadcast('openAddCollectionPopup');
              };
              $scope.editGroup = function(options){
                $scope.$broadcast('openEditCollectionPopup', options);
              };
              $scope.deleteGroup = function(id, url){
                $scope.$broadcast(
                  'openConfirmationPopup',
                  'Are you sure?',
                  function(){
                    $http.post(url, {
                        id: id,
                    });
                    var promise = $q.defer();
                    promise.promise.then(function(){
                      //Intercom('trackEvent', 'bloggers-favorites-list-delete', {id: id});
                      setTimeout(function() {
                        $("#group_"+id).fadeOut({complete: function(){
                          $("#group_"+id).remove();
                        }});
                      }, 10);
                    });
                    promise.resolve();
                    return promise.promise;
                  },
                  null
                );
              };

                $scope.sendExport = function(url) {
                    $scope.displayMessage("Exporting..");
                    $http({
                        method: 'GET',
                        url: url
                    }).success(function(data) {
                        $scope.displayMessage("You'll get your export data on email soon.");
                    }).error(function() {
                        $scope.displayMessage("Error");
                    })
                };

              $scope.displayMessage = function(msg) {
                  $scope.$broadcast("displayMessage", {message: msg});
              };

              $scope.context = context;
              $scope.$window = $window;
            }
          };
        }]);

})();
