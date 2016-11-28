angular.module('theshelf.components', ['restangular'])



.config(['$httpProvider', 'RestangularProvider', '$sceDelegateProvider', function ($httpProvider, RestangularProvider, $sceDelegateProvider) {
    // $sceDelegateProvider.resourceUrlWhitelist([
    //     'self',
    //     'https://theshelf-static-files.s3.amazonaws.com/**',
    // ]);
    // $sceDelegateProvider.resourceUrlWhitelist(['.*']);
    $sceDelegateProvider.resourceUrlWhitelist([
        'self',
        'https://syndication.twitter.com/**',
        'http://theshelf-static-files.s3.amazonaws.com/**',
        'https://theshelf-static-files.s3.amazonaws.com/**',
    ]);
    $httpProvider.defaults.headers.common["X-Requested-With"] = "XMLHttpRequest";
    $httpProvider.defaults.xsrfCookieName = "csrftoken";
    $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
    RestangularProvider.setBaseUrl('/api/v1');
}])


.directive('lazyInlineImage', ['Restangular', function (Restangular) {
    return {
        restrict: 'A',
        link: function (scope, iElement, iAttrs) {
            var msgId = scope.msg.id;
            var cid = iAttrs.cid;

            var message = Restangular.one('messages', msgId);

            iElement.hide();
            message.customGET('content_part', {cid: cid}).then(function(response) {
                if (response.status == 'success') {
                    iElement.attr('src', response.data.content).show();
                }
            });
        }
    };
}])


.directive('watchChange', function() {
    return {
        scope: {
            onchange: '&watchChange'
        },
        link: function(scope, iElement, iAttrs) {
            iElement.on('input', function() {
                scope.$apply(function () {
                    scope.onchange();
                });
            });
        }
    };
})



.directive('uniqueIn', function() {
    return {
        priority: -1,
        require: 'ngModel',
        link: function(scope, elm, attrs, ctrl) {
            var set = scope.$eval(attrs.uniqueIn), previous;
            
            ctrl.$formatters.push(validator);
            ctrl.$parsers.push(validator);
            
            ctrl.$formatters.unshift(storePrevious);
            ctrl.$parsers.push(storePrevious);
            
            scope.$watch(
                function() {
                    return set[ctrl.$viewValue] < 2 || !set[ctrl.$viewValue];
                }, 
                function(value){
                    ctrl.$setValidity('unique', value);
                }
            );
            
            function validator(value) {
                // console.log('validator', previous, value);
                if (value !== previous) {
                    if (previous) set[previous] = (set[previous] || 1) - 1;
                    if (value) set[value] = (set[value] || 0) + 1;
                }
                return value;
            }
            
            function storePrevious(v) {
                previous = v;
                return v;
            }
        }
    };
})



.directive('multipleInputs', [function () {
    return {
        restrict: 'A',
        controller: function () {
            var ctrl = this;

            ctrl.uniqueSet = {};

            ctrl.init = function (options) {
                if (!options.values || !options.values.length) {
                    options.values.push('');
                } else {
                    // for (var i in options.values) {
                    //     ctrl.uniqueSet[options.values[i]] = 1;
                    // }
                }
            };

            ctrl.onChange = function (options) {
                if (options.$last) {
                    if (options.form.$dirty && options.form.$valid && options.values[options.$index] && options.values[options.$index].length) {
                      options.values.push('');
                    }
                } else {
                    if (options.form.$dirty && (!options.values[options.$index] || !options.values[options.$index].length)) {
                      options.values.splice(options.$index, 1);
                    }
                }
            };

            ctrl.setFocus = function (value, form) {
                // form.isFocused = value;
                form.isFocused = false;
            };

        },
        controllerAs: 'multipleInputsCtrl',
        link: function (scope, iElement, iAttrs) {
        }
    };
}])



.service('tsViewHelper', function () {
    var self = this;

    self.extend = function (options) {
        angular.extend(options.destination, options.source);
    };
})



.directive('tsAffixed', [function () {
    return {
        restrict: 'A',
        link: function (scope, iElement, iAttrs) {
            var didScroll;
            var lastScrollTop = 0;
            var delta = 5;
            var navbarOffset = iElement.offset().top;
            var navDownClass = 'affix', navUpClass = 'nav-up';

            function hasScrolled() {
                var st = angular.element(this).scrollTop();
                if (Math.abs(lastScrollTop - st) <= delta)
                    return;
                if (st <= navbarOffset + delta) {
                    iElement.prev().height(0);
                    iElement.removeClass(navDownClass).removeClass(navUpClass);
                } else if (st > lastScrollTop && st > iElement.outerHeight() + navbarOffset) {
                    iElement.removeClass(navDownClass).addClass(navUpClass);
                } else {
                    if (st + angular.element(window).height() < angular.element(document).height()) {
                        iElement.prev().height(iElement.outerHeight());
                        iElement.removeClass(navUpClass).addClass(navDownClass);
                    }
                }
                lastScrollTop = st;
            }

            angular.element(window).scroll(function (event) {
                didScroll = true;
            });

            setInterval(function () {
                if (didScroll) {
                    hasScrolled();
                    didScroll = false;
                }
            }, 250);
        }
    };
}])



.directive('dropdownFormAdapter', ['$timeout', function ($timeout) {
    return {
        scope: {
            options: '=',
            selected: '=',
            onchange: '&',
        },
        require: 'ngModel',
        template: [
            '<div class="order_select"',
                'dropdown-select="options"',
                'dropdown-model="selected"',
                'dropdown-onchange="_onchange(selected)"></div>',
        ].join(''),
        link: function (scope, iElement, iAttrs, ngModelController) {
            scope._onchange = function (selected) {
                ngModelController.$setViewValue(selected.value);
                $timeout(function () {
                    ngModelController.$render();
                }, 10);
                scope.selected = selected;
                scope.onchange({selected: selected});
            };
        }
    };
}])



.directive('coverImageUploader', ['$timeout', function ($timeout) {
    return {
        scope: {
            uploadUrl: '=',
            imageSize: '=',
            'uploadData': '=',
        },
        require: 'ngModel',
        template: [
            '<div class="cover_img default"></div>',
            '<div class="normal_bt sm gray_bt" image-upload ng-click="upload(uploadUrl, imageSize, uploadData)" no-reload success-bc="coverImageSet">Replace Image</div>',
        ].join(''),
        link: function (scope, iElement, iAttrs, ngModelController) {

            ngModelController.$render = function () {
                if (ngModelController.$viewValue) {
                    var img = angular.element('<img />');
                    img.attr('src', ngModelController.$viewValue + '?r=' + Math.random());
                    img.attr('style', 'width: 500px;');
                    iElement.find('.cover_img').removeClass('default');
                    iElement.find('.cover_img').children().remove();
                    iElement.find('.cover_img').append(img);
                }
            };

            scope.$on('coverImageSet', function (theirScope, url) {
                ngModelController.$setViewValue(url);
                $timeout(function () {
                    ngModelController.$render();
                }, 10);
            });
        }
    };
}])



.directive('profileImageUploader', ['$timeout', function ($timeout) {
    return {
        scope: {
            uploadUrl: '=',
            imageSize: '=',
            defaultLogoText: '=',
            uploadData: '=',
        },
        require: 'ngModel',
        template: [
            '<div class="profile_pic default">',
                '<div class="text_logo">{{ defaultLogoText }}</div>',
            '</div>',
            '<div class="normal_bt sm gray_bt" image-upload ng-click="upload(uploadUrl, imageSize, uploadData)" no-reload success-bc="profileImageSet">Replace With Logo</div>',
        ].join(''),
        link: function (scope, iElement, iAttrs, ngModelController) {

            ngModelController.$render = function () {
                if (ngModelController.$viewValue) {
                    var img = angular.element('<img />');
                    img.attr('src', ngModelController.$viewValue + '?r=' + Math.random());
                    img.addClass('picture_logo');
                    iElement.find('.profile_pic').removeClass('default');
                    iElement.find('.profile_pic').children().remove();
                    iElement.find('.profile_pic').append(img);
                }
            };

            scope.$on('profileImageSet', function (theirScope, url) {
                ngModelController.$setViewValue(url);
                $timeout(function () {
                    ngModelController.$render();
                }, 10);
            });
        }
    };
}])



.directive('singleDatePicker', [function () {
    return {
        restrict: 'A',
        scope: {},
        require: 'ngModel',
        // replace: true,
        template: [
            '<div class="btn btn-circle blue">',
                '<i class="fa fa-calendar"></i>&nbsp;<span class="date-text"></span> <b class="fa fa-angle-down"></b>',
            '</div>',
        ].join(''),
        link: function (scope, iElement, iAttrs, ngModelController) {

            var built = false;
            var disabled = false;

            ngModelController.$formatters.push(function (modelValue) {
                return modelValue ? moment(modelValue) : undefined;
            });

            ngModelController.$parsers.push(function (viewValue) {
                return viewValue.format('YYYY-MM-DD');
            });

            ngModelController.$render = function () {
                var dateView = ngModelController.$viewValue ? ngModelController.$viewValue.format('M/D/YY') : '--/--/--';

                if (!built) {
                    iElement.find('div').daterangepicker({
                        opens: iAttrs.opens ? iAttrs.opens : 'left',
                        showDropdowns: true,
                        startDate: ngModelController.$viewValue,
                        endDate: undefined,
                        minDate: undefined,
                        maxDate: undefined,
                        singleDatePicker: true
                    }, callback);
                    built = true;
                } else {
                    // iElement.find('div').data('daterangepicker').setStartDate(ngModelController.$viewValue);
                }

                iElement.find('.date-text').text(dateView);
            };

            function callback(start, end) {
                ngModelController.$setViewValue(start);
                if (start.format('M/D/YY') !== ngModelController.$viewValue.format('M/D/YY')) {
                    ngModelController.$setDirty();
                }
                scope.$apply(function () {
                    ngModelController.$render();
                });
            }

            iAttrs.$observe('disabled', function () {
                disabled = iAttrs.disabled ? true : false;
            });

            iElement.children().click(function (event) {
                if (disabled) {
                    event.preventDefault();
                    event.stopPropagation();
                }
            });

        }
    };
}])



.directive('dateRangePicker', [function () {
    return {
        restrict: 'A',
        scope: {},
        require: 'ngModel',
        // replace: true,
        template: [
            '<div class="btn btn-circle blue">',
                '<i class="fa fa-calendar"></i>&nbsp;<span class="date-text"></span> <b class="fa fa-angle-down"></b>',
            '</div>',
        ].join(''),
        link: function (scope, iElement, iAttrs, ngModelController) {

            var built = false;
            var disabled = false;

            ngModelController.$formatters.push(function (modelValue) {
                return {
                    startDate: modelValue.startDate ? moment(modelValue.startDate) : undefined,
                    endDate: modelValue.endDate ? moment(modelValue.endDate) : undefined,
                };
            });

            ngModelController.$parsers.push(function (viewValue) {
                return {
                    startDate: viewValue.startDate.format('YYYY-MM-DD'),
                    endDate: viewValue.endDate.format('YYYY-MM-DD'),
                };
            });

            ngModelController.$render = function () {
                var viewValue = ngModelController.$viewValue;
                var startDate, endDate;

                startDate = viewValue.startDate ? viewValue.startDate.format('M/D/YY') : '--/--/--';
                endDate = viewValue.endDate ? viewValue.endDate.format('M/D/YY') : '--/--/--';

                if (!built) {
                    iElement.find('div').daterangepicker({
                        opens: iAttrs.opens ? iAttrs.opens : 'left',
                        showDropdowns: true,
                        startDate: viewValue.startDate,
                        endDate: viewValue.endDate,
                        minDate: undefined,
                        maxDate: undefined,
                        singleDatePicker: false,
                    }, callback);
                    built = true;
                }

                iElement.find('.date-text').text(startDate + ' - ' + endDate);
            };

            function callback(start, end) {
                ngModelController.$setViewValue({startDate: start, endDate: end});
                if (start.format('M/D/YY') !== ngModelController.$viewValue.startDate.format('M/D/YY') || end.format('M/D/YY') !== ngModelController.$viewValue.endDate.format('M/D/YY')) {
                    ngModelController.$setDirty();
                }
                scope.$apply(function () {
                    ngModelController.$render();
                });
            }

            iAttrs.$observe('disabled', function () {
                disabled = iAttrs.disabled ? true : false;
            });

            iElement.children().click(function (event) {
                if (disabled) {
                    event.preventDefault();
                    event.stopPropagation();
                }
            });

        }
    };
}])



.directive('requester', ['$http', '$timeout', function($http, $timeout) {
    return {
        restrict: 'A',
        scope: true,
        controllerAs: 'requesterCtrl',
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
        },
        link: function(scope, iElement, iAttrs, ctrl) {
            if (iAttrs.attachedForm && iAttrs.onFormDirty) {
                scope.$watch(iAttrs.attachedForm + '.$dirty', function (nv, ov) {
                    if (nv) {
                        scope.$eval(iAttrs.onFormDirty);
                    }
                });
            }
        }
    };
}])



.directive('emailSender', ['$http', '$timeout', function($http, $timeout) {
    return {
        restrict: 'A',
        scope: true,
        controllerAs: 'emailSenderCtrl',
        controller: function() {
            var ctrl = this;

            ctrl.loading = false;
            ctrl.loaded = false;
            ctrl.reloading = false;
            ctrl.send = function(options) {
                if (ctrl.loading || ctrl.reloading) {
                    return;
                }
                ctrl.loading = true;
                ctrl.loaded = false;
                return $http({
                    url: options.url,
                    method: 'POST',
                    data: options.data,
                }).success(function(response) {
                    ctrl.loading = false;
                    ctrl.loaded = true;
                    if (options.status) {
                        angular.extend(options.status, response.data.status);
                    }
                    if (options.successCb) {
                        options.successCb(options.successCbParams ? options.successCbParams : response);
                    }
                    return response;
                }).error(function() {
                    ctrl.loading = false;
                    ctrl.loaded = true;
                });
            };
        },
        link: function(scope, iElement, iAttrs, ctrl) {
        }
    };
}])



.factory('tsOutreachTemplate', ['$interpolate', '$templateCache', '$http', 'UploaderService', function($interpolate, $templateCache, $http, UploaderService) {
    
    function Template (defaultBody, defaultSubject) {
        this.defaultBody = defaultBody;
        this.defaultSubject = defaultSubject;
        this.sendingTestEmail = false;
    }

    Template.prototype = {
        getBodyTemplate: function (body, options) {
            return getTemplate(body && body.length ? body : this.defaultBody, options);
        },
        getSubjectTemplate: function (subject, options) {
            return getTemplate(subject && subject.length ? subject : this.defaultSubject, options);
        },
        getBody: function (body, options) {
            return getText(body && body.length ? body : getTemplate(this.defaultBody, options), options);
        },
        getSubject: function (subject, options) {
            return getText(subject && subject.length ? subject : getTemplate(this.defaultSubject, options), options);
        },
        sendTestEmail: function (url, options) {
            var self = this;
            self.sendingTestEmail = true;
            $http({
                method: 'POST',
                url: url,
                data: {
                    template: self.getBody(options.body, options.context),
                    subject: self.getSubject(options.subject, options.context),
                    attachments: UploaderService.getAttachments(),
                    send_mode: 'test',
                    no_job: true,
                }
            }).success(function () {
                self.sendingTestEmail = false;
            }).error(function () {
                self.sendingTestEmail = false;
            });
        }
    };

    function getEscaped(name) {
        return "{{" + name + "}}";
    };

    function getTemplate(value, options) {
        var opts = {
            getEscaped: getEscaped
        };
        angular.extend(opts, options || {});
        return $interpolate(value)(opts);
    };

    function getText(value, options) {
        return $interpolate(value)(options);
    };

    return Template;
}])



.directive('addPostsWidget', ['tsAddPostsWidgetService', 'tsConfig', function (tsAddPostsWidgetService, tsConfig) {
    return {
        restrict: 'A',
        scope: true,
        templateUrl: tsConfig.wrapTemplate('js/angular/components/templates/add_posts_widget.html'),
        link: function (scope, iElement, iAttrs) {
            scope.postsList = new tsAddPostsWidgetService();

            scope.$on('loadAddPostsWidget', function (theirScope, options) {
                console.log('loadAddPostsWidget');
                scope.postsList.load(options);
            });

            scope.$on('cancelLoadAddPostsWidget', function (theirScope, options) {
                console.log('cancelLoadAddPostsWidget');
                scope.postsList.cancelLoad();
            });
        }
    };
}])



.directive('iframeRenderer', ['$timeout', function ($timeout) {
    return {
        restrict: 'A',
        replace: true,
        scope: true,
        template: '<div><div ng-if="visible"><iframe ng-src="{{ sce.trustAsResourceUrl(url) }}" frameborder="0" height="{{ height }}" width="{{ width }}"></iframe></div><div ng-if="!visible" main-loader></div></div>',
        link: function (scope, iElement, iAttrs) {
            var iFrame = null;
            scope.visible = false;

            scope.$on('renderIframe', function(theirScope, options) {
                scope.url = options.url;
                scope.visible = true;
                scope.width = iAttrs.width;
                scope.height = iAttrs.height;
                $timeout(function () {
                    iFrame = iElement.find('iframe');   
                });
            });

            scope.$on('$destroy', function () {
                // iFrame.off();
                // iFrame.remove();
                // iElement.off();
            });
        }
    };
}])


.directive('editableField', ['tsConfig', function(tsConfig) {
    return {
        restrict: 'A',
        scope: true,
        template: tsConfig.wrapTemplate('js/angular/templates/editable_field.html'),
        controller: function() {},
        controllerAs: 'fieldCtrl',
        link: function(scope, iElement, iAttrs, ctrl) {
        }
    };
}])



// @todo: refactor this so that it works not only with campaigns
.directive('rowArchiver', ['$http', '$timeout', 'Restangular', function($http, $timeout, Restangular) {
    return {
        restrict: 'A',
        scope: true,
        controllerAs: 'rowArchiverCtrl',
        controller: function($scope) {
            var vm = this;

            vm.loading = false;

            vm.toggle = function(options) {
                vm.loading = true;
                return Restangular.one('campaigns', vm.campaignId)
                    .post('archive_influencer', {
                        'stage_type': vm.stageType,
                        'mapping_id': vm.mappingId,
                    }).then(function() {
                        options.values.archived = !options.values.archived;
                        options.ctrl.removed = options.values.archived;
                        vm.loading = false;
                    }, function() {
                        vm.loading = false;
                    });
            };
        },
        link: function(scope, iElement, iAttrs, ctrl) {
            ctrl.campaignId = iAttrs.campaignId;
            ctrl.stageType = iAttrs.stageType;
            ctrl.mappingId = iAttrs.mappingId;
        }
    };
}])


.service('UploaderService', ['FileUploader', 'context', function (FileUploader, context) {
    var self = this;

    self.uploader = new FileUploader({
      url: context.messageUrls.attachmentUploadUrl,
      autoUpload: true,
      headers: {
          'X-CSRFToken': context.csrf_token
      }
    });

    self.uploader.onSuccessItem = function(fileItem, response, status, headers) {
        fileItem.response = response;
    };

    self.getAttachments = function() {
      return self.uploader.queue.map(function(item) { return item.response; });
    };
}])


.factory('NotifyingService', ['$rootScope', function($rootScope) {
    return {
        subscribe: function(scope, event, callback, compatibility) {
            if (compatibility) {
                scope.$on(event, callback);
            }
            var handler = $rootScope.$on(event, callback);
            scope.$on('$destroy', handler);
            console.log('subscribe for ' + event);
        },

        notify: function(event, data, compatibility) {
            if (compatibility) {
                $rootScope.$broadcast(event, data);
            }
            $rootScope.$emit(event, data);
            console.log('notify ' + event);
        }
    };
}])


.factory('DebouncedEventService', ['_', 'NotifyingService', function(_, NotifyingService) {
    var events = {};

    return {
        register: function(name, data, timeout) {
            function notify() {
                NotifyingService.notify(name, data);
            }
            events[name] = _.debounce(notify, timeout);
        },
        notify: function(name, data, timeout) {
            if (!events[name]) {
                this.register(name, data, timeout);
            }
            events[name]();
        },
    };
}])


.directive('sgNumberInput', ['$filter', '$browser', function($filter, $browser) {
    return {
        require: 'ngModel',
        link: function($scope, $element, $attrs, ngModelCtrl) {
            var listener = function() {
                var value = $element.val().replace(/,/g, '')
                $element.val($filter('number')(value, false))
            }
            
            // This runs when we update the text field
            ngModelCtrl.$parsers.push(function(viewValue) {
                return viewValue.replace(/,/g, '');
            })
            
            // This runs when the model gets updated on the scope directly and keeps our view in sync
            ngModelCtrl.$render = function() {
                $element.val($filter('number')(ngModelCtrl.$viewValue, false))
            }
            
            $element.bind('change', listener)
            $element.bind('keydown', function(event) {
                var key = event.keyCode
                // If the keys include the CTRL, SHIFT, ALT, or META keys, or the arrow keys, do nothing.
                // This lets us support copy and paste too
                if (key == 91 || (15 < key && key < 19) || (37 <= key && key <= 40)) 
                    return 
                $browser.defer(listener) // Have to do this or changes don't get picked up properly
            })
            
            $element.bind('paste cut', function() {
                $browser.defer(listener)  
            })
        }
        
    }
}])

;