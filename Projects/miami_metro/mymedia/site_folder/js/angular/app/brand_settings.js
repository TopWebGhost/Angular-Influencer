'use strict';

angular.module('theshelf')

.controller('SettingsCtrl', ['$scope', '$location', '$http', 'landingData', 'context', function ($scope, $location, $http, landingData, context) {
    $scope.context = context;
    $scope.tab = 1;
    $scope.tabsNumber = 7;
    $scope.setTab = function(n){
        $location.path("/"+n);
    };
    $scope.restrictedTabs = [];
    $scope.$on('$locationChangeSuccess', function(){
      var path = Number($location.path().substr(1));
      if (isNaN(path) || path < 1 || path > $scope.tabsNumber || $scope.restrictedTabs.indexOf(path) > -1) {
        $scope.setTab(1);
      } else {
        $scope.tab = path;
      }
    });
    $scope.openAddNewUserPopup = function() {
      $scope.$broadcast('openAddNewUserPopup');
    };

    var self = this;

    self.landingData = landingData;

    function LoadInfluencers() {
      var self = this;

      self.clearText = function() {
        self.urlsText = '';
      };

      self.tagSelected = {"text": "Select a tag...", value: null};

      self.selectTag = function(selected) {
        self.tagSelected = selected;
      };
    }

    self.loadInfluencers = new LoadInfluencers();
}])

.directive('preferences', ['$http', '$rootScope', function($http, $rootScope) {
  return {
    restrict: 'A',
    template: [
      '<fieldset ng-repeat="(name, item) in settings" style="float:left; margin-right:50px;" ng-if="item.editable">',
        '<div class="cb_or_rb_wrap" ng-click="toggleCheckbox()">',
            '<input id="{{ name }}" name="{{ name }}" type="checkbox" ng-model="item.enabled" />',
            '<label for="{{ name }}"><span class="graphic plus_btn"></span> {{ item.text }}</label>',
        '</div>',
      '</fieldset>',
      '<div class="x_space x_40"></div>',
      '<button class="square_bt md"',
      'ng-click="save()"',
      'ng-class="{gray_bt: !preferencesChanged, teal_bt: preferencesChanged}"',
      'ng-disabled="loading || !preferencesChanged">Save</button>',
      '<div main-loader ng-show="loading"></div>'
    ].join('\n'),
    scope: true,
    link: function(scope, iElement, iAttrs) {
      scope.preferencesChanged = false;
      scope.url = iAttrs.url;
      scope.settings = {
        campaigns_enabled: {text: 'Campaigns Enabled', enabled: false, initial: false, editable: false},
        profile_enabled: {text: 'Profile Enabled', enabled: false, initial: false, editable: false},
        non_campaign_messaging_enabled: {text: 'Messaging Outside of the Campaigns Enabled', enabled: false, initial: false, editable: true},
        skipping_stages_enabled: {text: 'Skipping stages for the campaign pipelines enabled', enabled: false, initial: false, editable: true},
      };

      scope.$watch('tab', function(nv, ov) {
        if (nv === 4) {
          scope.load();
        }
      });

      scope.load = function() {
        console.log('loading preferences');
        scope.loading = true;
        $http({
          method: 'GET',
          url: scope.url
        }).success(function(response) {
          for (var i in response)
            scope.settings[i].initial = scope.settings[i].enabled = response[i];
          scope.loading = false;
          scope.preferencesChanged = false;
        });
      };

      scope.toggleCheckbox = function() {
        for (var i in scope.settings)
          if (scope.settings[i].enabled !== scope.settings[i].initial) {
            scope.preferencesChanged = true;
            return;
          }
        scope.preferencesChanged = false;
      };

      scope.save = function() {
        scope.loading = true;
        var params = {};
        for (var i in scope.settings)
          params[i] = scope.settings[i].enabled;
        $http({
          method: 'POST',
          url: scope.url,
          data: params
        }).success(function() {
          scope.loading = false;
          scope.preferencesChanged = false;
          for (var i in scope.settings)
            scope.settings[i].initial = scope.settings[i].enabled;
          $rootScope.$broadcast('preferences-changed', params);
        });
      };
    }
  };
}])

.controller('IsAgencyCtrl', ['$scope', function ($scope) {
  $scope.toggleAgency = function(){
    $scope.agency = !$scope.agency;
  };
}])

.controller('CCEditCtrl', ['$scope', '$timeout', '$http', function ($scope, $timeout, $http) {
    $scope.exp_month = {};
    $scope.exp_year = {};
    $scope.months = [{
        text: '1'
    }, {
        text: '2'
    }, {
        text: '3'
    }, {
        text: '4'
    }, {
        text: '5'
    }, {
        text: '6'
    }, {
        text: '7'
    }, {
        text: '8'
    }, {
        text: '9'
    }, {
        text: '10'
    }, {
        text: '11'
    }, {
        text: '12'
    }, ]
    $scope.years = [{
        text: '2014'
    }, {
        text: '2015'
    }, {
        text: '2016'
    }, {
        text: '2017'
    }, {
        text: '2018'
    }, {
        text: '2019'
    }, {
        text: '2020'
    }, {
        text: '2021'
    }, {
        text: '2022'
    }, {
        text: '2023'
    }, {
        text: '2024'
    }, {
        text: '2025'
    }, ];
    $scope.types = [{
        text: "Visa",
        mask: "9999 9999 9999 9999",
        cvcmask: "999"
    }, {
        text: "MasterCard",
        mask: "9999 9999 9999 9999",
        cvcmask: "999"
    }, {
        text: "AmEx",
        mask: "9999 999999 99999",
        cvcmask: "9999"
    }, {
        text: "JCB",
        mask: "9999 9999 9999 9999",
        cvcmask: "999"
    }, {
        text: "Discover",
        mask: "9999 9999 9999 9999",
        cvcmask: "999"
    }, {
        text: "Diners Club",
        mask: "9999 9999 9999 99",
        cvcmask: "999"
    }];
    var stripe_validator = function () {
      if ($scope.stripedata === undefined) return;
      if ($scope.stripedata.number !== undefined) {
        $scope.card_valid = Stripe.card.validateCardNumber($scope.stripedata.number);
        $scope.card_type = Stripe.card.cardType($scope.stripedata.number);
        if($scope.card_type !== $scope.cctype.text) $scope.card_valid = false;
      }
      if ($scope.stripedata.exp_month !== undefined && $scope.stripedata.exp_year !== undefined) {
        $scope.exp_valid = Stripe.card.validateExpiry($scope.stripedata.exp_month, $scope.stripedata.exp_year);
      }
      if ($scope.stripedata.cvc !== undefined) {
        $scope.cvc_valid = Stripe.card.validateCVC($scope.stripedata.cvc);
      }
    };
    $scope.$watch('stripedata', stripe_validator, true);
    $scope.updateType = function(selected){
      if (selected !== undefined)
        $scope.cctype = selected;
      $scope.ccmask = $scope.cctype.mask;
      $scope.cvcmask = $scope.cctype.cvcmask;
      stripe_validator();
    };

    // $scope.updateExpDate = function () {
    //   $scope.stripedata.exp_month = $scope.exp_month.text;
    //   $scope.stripedata.exp_year = $scope.exp_year.text;
    // };

    $scope.updateExpMonth = function(selected) {
      $scope.stripedata.exp_month = selected.text;
    };

    $scope.updateExpYear = function(selected) {
      $scope.stripedata.exp_year = selected.text;
    };

    var responseHandler = function (status, response) {
      $scope.$apply(function () {
        if (response.error) {
          $scope.state = "Error: " + response.error.message;
        } else {
          var token = response.id;
          $http.post($scope.store_url, {
            stripeToken: token,
          })
            .success(function (data) {
              window.location.reload();
            })
            .error(function (a, b, c, d) {
              $scope.state = "Error: "+a.error;
            });
        }
      });
    };
    $scope.getToken = function (key, url) {
      if(!$scope.changed){
        return;
      }
      $scope.state = "Uploading";
      $scope.store_url = url;
      Stripe.setPublishableKey(key);
      Stripe.card.createToken($scope.stripedata, responseHandler);
    };
    $scope.state = "Save";
    $scope.stripedata = {};
    $scope.paymentdata = {};
    $scope.cctype = angular.copy($scope.types[0]);
    $scope.updateType();
    $scope.exp_month = {};
    $scope.exp_year = {};

    $scope.changed = false;
    var orygData = null;
    $timeout(function(){
      orygData = angular.copy($scope.stripedata);
      $scope.$watch('stripedata', function(){
        $scope.changed = !angular.equals($scope.stripedata, orygData)
      }, true);
    }, 100);
}])

.directive('confirmUploadPopup', [
    'tsConfig',
    function(tsConfig) {
        return {
            restrict: 'A',
            scope: true,
            transclude: true,
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/confirmable_link_popup.html'),
            link: function(scope, iElement, iAttrs) {
                scope.title = "Are You Sure?";
                scope.message = "This action is final. If you decide you want to re-join The Shelf again later, you will need to contact us";
                scope.no = function(){
                    scope.close();
                };
                scope.yes = function(){
                  scope.$emit('confirmed');
                  scope.setState('working');
                  scope.setNoClose(true);
                };
                scope.$on('openConfirmUploadPopup', function(){
                  scope.open();
                });
            }
        };
    }
])

.directive('removeBrand', ['$http', 'tsConfig',
    function($http, tsConfig) {
        return {
            restrict: 'A',
            scope: true,
            transclude: true,
            templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/confirmable_link_popup.html'),
            link: function(scope, iElement, iAttrs) {
                scope.title = "Are You Sure?";
                scope.message = "Do you really want to remove this brand?";
                scope.no = function(){
                    scope.close();
                };
                scope.yes = function(){
                  scope.setNoClose(true);
                  scope.setState('working');
                  $http({
                    method: 'POST',
                    url: iAttrs.url,
                    data: {
                      name: iAttrs.removeBrand,
                    }
                  }).success(function(){
                    window.location.reload();
                  });
                };
                var bind = function(){
                    iElement.find('.transcluded').click(function(){
                        scope.$apply(function(){
                            scope.open();
                        });
                        return false;
                    });
                };
                setTimeout(bind, 10);
            }
        };
    }
])

.directive('addBrand', ['$http', '$timeout',
  function ($http,$timeout) {
    return {
      restrict: 'A',
      scope: true,
      link: function (scope, iElement, iAttrs) {
        scope.matchBrandUrl = iAttrs.matchBrandUrl;
        scope.brand_name = null;
        scope.brand_url = null;
        scope.show_name = false;
        scope.state = 'save';
        scope.$watch("brand_url", function(newVal) {
          if (scope.state === 'error')
            scope.state = 'Save';
        });
        scope.$on("brandSelected", function(their_scope, brand){
          if(brand){
            scope.brand_name = brand.name;
            scope.brand_url = brand.url;
            if(scope.brand_name){
              scope.show_name = false;
            }else{
              scope.show_name = true;
            }
          }else{
            scope.brand_name = null;
            scope.brand_url = null;
            scope.show_name = true;
          }
        });
        scope.brandName = function(){
          return scope.brand_name;
        };
        scope.changeBrandName = function(brand_name){
          scope.brand_name = brand_name;
        };
        scope.save = function(){
          scope.modified = true;
          scope.state = 'saving';
          $http({
            method: 'POST',
            url: iAttrs.saveUrl,
            data: {
              name: scope.brand_name,
              url: scope.brand_url
            }
          }).success(function(){
            window.location.reload();
          }).error(function(msg) {
            scope.errorMessage = msg;
            scope.state = 'error';
          });
        };
      }
    };
  }
])

.directive('settingsFormUploader', ['$http', '$timeout', function ($http, $timeout) {
  return {
    restrict: 'A',
    scope: true,
    link: function (scope, iElement, iAttrs) {
      scope.changed = false;
      var orygData = null;
      if(iAttrs.settingsFormUploader.length>0){
        $timeout(function(){
          orygData = angular.copy(scope[iAttrs.settingsFormUploader]);
          scope.$watch(iAttrs.settingsFormUploader, function(){
            scope.changed = !angular.equals(scope[iAttrs.settingsFormUploader], orygData)
          }, true);
        }, 100);
      }
      scope.state = {
        name: 'ready',
        text: 'Save',
      };
      var do_confirm=function(form, data, type, url){
        scope.state = {
          name: 'uploading',
          text: 'Uploading'
        };
        return $http({
          method: 'post',
          url: url,
          data: {
            type: type,
            data: data
          }
        }).success(function(){
          orygData = angular.copy(scope[iAttrs.settingsFormUploader]);
          scope.state = {
            name: 'success',
            text: 'Success',
          };
          $timeout(function(){
            scope.state = {
              name: 'ready',
              text: 'Save',
            };
          }, 4000);
        }).error(function(data){
          scope.state = {
            name: 'error',
            text: 'Error: '+data,
            data: data
          };
        });
      };
      scope.toggle = function(what, key){
        if(scope[what] === undefined){
          scope[what] = {};
        }
        if(scope[what][key] === undefined){
          scope[what][key] = false;
        }
        scope[what][key] = !scope[what][key];
      };
      scope.submit = function(form, data, type, url){
        if(iAttrs.confirmUpload !== undefined){
          scope.$broadcast('openConfirmUploadPopup');
          scope.$on('confirmed', function(){
            do_confirm(form, data, type, url).then(function(){
              window.location.assign('/');
            });
          });
        }else{
          if(scope.changed){
            do_confirm(form, data, type, url);
          }
        }
      };
    }
  };
}])

.directive('setDefaultTo', ['$timeout', function ($timeout) {
  return {
    restrict: 'A',
    require: 'ngModel',
    link: function (scope, iElement, iAttrs, ngModel) {
      $timeout(function(){
        ngModel.$setViewValue(iAttrs.setDefaultTo);
        iElement.val(iAttrs.setDefaultTo);
      }, 0);
    }
  };
}])

.directive('location', [function () {
  return {
    restrict: 'A',
    require: 'ngModel',
    link: function (scope, iElement, iAttrs, ngModel) {

        function getAddr(place, options) {
          if (!place) return null;
          if (options.useLongNames && place.address_components && place.address_components.length) {
            return place.address_components.map(function(comp) {
              return comp.long_name ? comp.long_name : comp.short_name;
            }).join(', ');
          } else {
            return place.formatted_address;
          }
        }

        var ac;
        var ac_changed = function() {
          scope.$apply(function() {
              var place = ac.getPlace();
              var addr = getAddr(place, {useLongNames: iAttrs.useLongNames !== undefined});
              if (place !== undefined && addr) {
                var longlat = place.geometry.location;
                ngModel.$setViewValue(addr);
                iElement.val(addr);
                scope.$emit("updateTimezone", longlat);
              }
          });
        };
        setTimeout(function() {
            ac = new google.maps.places.Autocomplete($("input#location")[0], {
                types: ["geocode"]
            });
            ac.changed = ac_changed;
        }, 10);
    }
  };
}])


.directive('timezone', ['$http', function ($http) {
  return {
    restrict: 'A',
    require: 'ngModel',
    link: function (scope, iElement, iAttrs, ngModel) {
      scope.$on('updateTimezone', function(event, longlat){
        scope.loading = true;
        $http({
          method: 'post',
          url: iAttrs.url,
          data: longlat
        }).success(function(data){
          ngModel.$setViewValue(data);
          iElement.val(data);
          scope.loading = false;
        });
      });
    }
  };
}])

;
