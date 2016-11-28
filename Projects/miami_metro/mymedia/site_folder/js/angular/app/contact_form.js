'use strict';

angular.module('theshelf')

.directive('contactForm', ['$http', '$sce', function ($http, $sce) {
  return {
    restrict: 'A',
    scope: true,
    replace: true,
    controller: function($scope, $element, $attrs, $transclude) {
      $scope.loaded = false;
      $scope.$on('openContactForm', function(){
        console.log('open');
        $scope.load();
      });

      $scope.load = function(){
        $scope.loaded = false;
        $http.get("/forms/contact_us")
          .success(function (data) {
            $('#comment_form')[0].reset();
            $('#comment_submit').val('Submit!');
            $scope.name = $sce.trustAsHtml(data.name);
            $scope.message = $sce.trustAsHtml(data.message);
            $scope.subject = $sce.trustAsHtml(data.subject);
            $scope.email = $sce.trustAsHtml(data.email);
            $scope.captcha = $sce.trustAsHtml(data.captcha);
            $scope.token = data.token;
            $scope.loaded = true;
          });
      };
    },
    link: function postLink(scope, iElement, iAttrs) {
    }
  };
}])

.directive('broadcaster', ['$rootScope', function ($rootScope) {
  return {
    restrict: 'A',
    link: function (scope, iElement, iAttrs) {
      iElement.click(function(){
        $rootScope.$apply(function(){
          $rootScope.$broadcast(iAttrs.broadcaster);
        });
      });
    }
  };
}])
;
