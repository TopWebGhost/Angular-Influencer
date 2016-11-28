'use strict';

angular.module('theshelf')

.directive('applyPopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/apply_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.template = iAttrs.template;
        scope.brand_name = iAttrs.brandName;
        scope.$on('openApplyPopup', function () {
          scope.open();
          setTimeout(function() {
            iElement.find('#editor').wysiwyg();
          }, 100);
        });
        scope.send = function(template){
          scope.setState("sending");
          $http({
            url: iAttrs.url,
            method: "POST",
            data: {
              template: iElement.find('#editor').cleanHtml(),
            }
          }).success(function(){
            scope.setState("done");
            window.location.reload();
          }).error(function(){
            scope.setState("error");
          });
        };
      }
    };
  }
])

.directive('applyMockPopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/apply_mock_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.$on('openApplyMockPopup', function () {
          scope.open();
        });
      }
    };
  }
])

.directive('seeMore', [function () {
  return {
    restrict: 'A',
    link: function (scope, iElement, iAttrs) {
      var full_content;
      var cut_content;
      setTimeout(function() {
        full_content = iElement.find('.see_more_content').text();
        cut_content = full_content.split(' ').slice(0, 50).join(" ");
        iElement.find('.see_more_content').text(cut_content+'...');
        if(full_content.length != cut_content.length){
          iElement.find('.see_more_link').click(function(){
            iElement.find('.see_more_content').text(full_content);
            iElement.find('.see_more_link').hide();
          });
        }else{
          iElement.find('.see_more_link').hide();
        }
      }, 10);
    }
  };
}])

;
