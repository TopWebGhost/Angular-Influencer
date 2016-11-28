'use strict';

angular.module('theshelf')

.controller('BloggerCommonCtrl', ['$scope', '$rootScope', 'context', function ($scope, $rootScope, context) {
    $scope.doOpenFavoritePopup = function(options){
        var unselectAll = function(arr) {
            if (arr === undefined || arr === null)
                return;
            arr.forEach(function(el) {
                el.selected = false;
            });
        };
        options.afterSuccessCb = function() {
            [$scope.productFeedPosts].forEach(unselectAll);
        };
        $rootScope.$broadcast('openFavoritePopup', options);
    };

    $scope.displayMessage = function(msg) {
        $scope.$broadcast("displayMessage", {message: msg});
    };

    $scope.context = context;

    $scope.$on('doOpenFavoritePopup', function(theirScope, options) {
        $scope.doOpenFavoritePopup(options);
    });
}])


.controller('BloggerContractCtrl', ['$scope', '$location', '$timeout', '$http', '$q', '$rootScope', 'pageServerData', 'tsUtils', 'tsAddPostsWidgetService', function($scope, $location, $timeout, $http, $q, $rootScope, pageServerData, tsUtils, tsAddPostsWidgetService) {
    $scope.tab = 1;

    $scope.setAllowedTabs = function (tabs) {
        $scope.allowedTabs = tabs;
    };

    $scope.setDefaultTab = function (tab) {
        $scope.defaultTab = tab;
    };

    $scope.addAllowedTab = function (tab) {
        if (!$scope.isAllowedTab(tab)) {
            $scope.allowedTabs.push(tab);
        }
    };

    $scope.isAllowedTab = function (tab) {
        return $scope.allowedTabs.indexOf(tab) > -1;
    };

    $scope.setTab = function(n) {
        $location.path("/" + n);
    };

    $scope.detailsSentCallback = function () {
        $scope.pageReload();
    };

    $scope.$on('$locationChangeSuccess', function() {
        var path = Number($location.path().substr(1));
        if (isNaN(path) || $scope.allowedTabs.indexOf(path) < 0) {
            $scope.setTab($scope.defaultTab);
        } else {
            $scope.tab = path;
        }
    });

    $scope.$watch('tab', function(nv, ov) {
        if (nv !== ov) {
            if (nv === 16) {
                $timeout(function () {
                    $scope.$broadcast('loadAddPostsWidget', {
                        contractId: pageServerData.contractId
                    });
                });
            } else {
                $scope.$broadcast('cancelLoadAddPostsWidget');
            }
        }
    });

    $scope.saveForm = function (form, requestButtonCtrl, requestParams) {
        if (form.$invalid) {
            tsUtils.makeFormFieldsDirty(form);
            return;
        }
        if (form.$dirty && form.$valid && !requestButtonCtrl.loading) {
            requestButtonCtrl.doRequest(requestParams);
        }
    };

    $scope.loading = false;
    $scope.error = false;
    $scope.sent = false;
    $scope.send = function(url) {
        $scope.loading = true;
        $scope.error = false;
        $http({
            url: url,
            method: 'POST',
        }).success(function() {
            $scope.loading = false;
            $scope.sent = true;
            $scope.error = false;
        }).error(function() {
            $scope.loading = false;
            $scope.error = true;
        });
    };

    function InfluencerInfo() {
        var self = this;

        angular.extend(self, pageServerData.defaults);

        self.canSave = function(form) {
            return form.$dirty && form.$valid && !self.saving;
        };

        self.saving = false;
        self.save = function(form) {
            if (!self.canSave(form)) {
                if (form.$invalid) {
                    tsUtils.makeFormFieldsDirty(form);
                    tsUtils.scrollToFirstInvalidElement(form);
                }
                return;
            }
            self.saving = true;
            return $http({
                method: 'POST',
                url: pageServerData.updateModelUrl,
                data: {
                    'list': [{
                        id: pageServerData.contractId,
                        modelName: 'Contract',
                        values: {
                            product_url: self.productURL,
                            product_urls: self.productUrls,
                            blogger_address: self.address,
                            // details_collected_status: 2,
                            date_requirements: self.dateRequirements,
                        },
                        json_fields: {
                            info: {
                                agent_name: self.agentName,
                                publisher_name: self.entityName,
                                product_preferences: self.productPreferences,
                                additional_data: {
                                    paypal_username: self.paypalUsername,
                                    phone_number: self.phoneNumber,
                                },
                            },
                        }
                    }, {
                        id: pageServerData.influencerId,
                        modelName: 'Influencer',
                        notifyAboutChanges: true,
                        values: {
                            name: self.fullName,
                            blogname: self.blogName,
                            fb_url: self.facebookURL,
                            tw_url: self.twitterURL,
                            insta_url: self.instagramURL,
                            pin_url: self.pinterestURL,
                            youtube_url: self.youtubeURL,
                        }
                    }]
                }
            }).success(function() {
                self.saving = false;
                form.$setPristine();
                // if (pageServerData.sendContract) {
                //     $rootScope.$broadcast('openConfirmationPopup', "The last step is signing the contract. Click on the button to go there now, and then you're all set!", function() {
                //         $rootScope.pageRedirect({redirectUrl: pageServerData.contractsUrl});
                //     }, null, {titleText: "Great thank you!", yesText: 'Sign the Contract', removeNo: true});
                // } else {
                //     $rootScope.$broadcast('displayMessage', {message: 'Thank You!', instructionText: 'Your info and preferences are submitted. And your campaign manager will be in touch soon.'});
                // }
            }).error(function() {
                self.saving = false;
                form.$setPristine();
            });
        };

        self.canSend = function (form) {
            // return form.$pristine && form.$valid && !self.saving && !self.sending;
            return form.$valid && !self.saving && !self.sending;
        };

        self.sending = false;
        self.send = function(form) {
            if (!self.canSend(form)) {
                if (form.$invalid) {
                    tsUtils.makeFormFieldsDirty(form);
                }
                return;
            }
            self.sending = true;
            return $http({
                method: 'POST',
                url: pageServerData.updateModelUrl,
                data: {
                    'list': [{
                        id: pageServerData.contractId,
                        modelName: 'Contract',
                        values: {
                            details_collected_status: 2,
                        },
                    }]
                }
            }).success(function() {
                self.sending = false;
                self.submitted = true;
                $scope.detailsSentCallback();
                // if (pageServerData.sendContract) {
                //     $rootScope.$broadcast('openConfirmationPopup', "The last step is signing the contract. Click on the button to go there now, and then you're all set!", function() {
                //         $rootScope.pageRedirect({redirectUrl: pageServerData.contractsUrl});
                //     }, null, {titleText: "Great thank you!", yesText: 'Sign the Contract', removeNo: true});
                // } else {
                //     $rootScope.$broadcast('displayMessage', {message: 'Thank You!', instructionText: 'Your info and preferences are submitted. And your campaign manager will be in touch soon.'});
                // }
            }).error(function() {
                self.sending = false;
            });
        };

        self.finishAndSend = function (form) {
            var savePromise = self.save(form);
            if (savePromise) {
                savePromise.then(function () {
                    self.send(form);
                });
            } else {
                self.send(form);
            }
        };
    }

    $scope.postsList = new tsAddPostsWidgetService();
    $scope.influencerInfo = new InfluencerInfo();

    $scope.influencerDateRangeModel = {
      startDate: null,
      endDate: null,
    };

    $scope.applyDateRange = function() {
        if (!$scope.forms['influencerInfoForm'])
            return;
        $scope.$apply(function() {
            $scope.influencerInfo.dateRequirements = moment($scope.influencerDateRangeModel.startDate).format('YYYY-MM-DD');
            $scope.forms['influencerInfoForm'].$setDirty();
        });
    };

    $scope.forms = {};
    $scope.registerFormScope = function(form, name, id) {
        $scope.forms[name] = form;
    };

    $scope.pageServerData = pageServerData;

}])

;
