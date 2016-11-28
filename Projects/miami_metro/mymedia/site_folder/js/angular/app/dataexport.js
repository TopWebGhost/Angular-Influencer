'use strict';

angular.module('theshelf')

.controller('DataexportCtrl', ['$scope', function ($scope) {

}])

.directive('exportPopup', ['$http', '$timeout', '$sce', 'singletonRegister', 'filtersQuery', 'tsConfig',
  function ($http, $timeout, $sce, singletonRegister, filtersQuery, tsConfig) {
    return {
      restrict: 'A',
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/export_popup.html'),
      link: function (scope, iElement, iAttrs) {
        if(singletonRegister.getOrRegister("exportPopup")){
          iElement.remove();
          return;
        }
        scope.task_ids = {};
        scope.shortPolling = function(){
          console.log("shortPolling tick!");
          var task_id = scope.task_ids[scope.export_type];
          if(task_id === undefined){
            task_id = null;
          }
          $http({
            method: 'POST',
            url: iAttrs.requestUrl,
            data: {
              export_type: scope.export_type,
              filters: filtersQuery.getQuery(),
              task_id: task_id
            }
          }).success(function(data){
            if(data.state == "pending"){
              scope.task_ids[scope.export_type] = data.task_id;
              scope.progress = data.progress;
              scope.setState("waiting");
              if(scope.visible){
                $timeout(scope.shortPolling, 5000);
              }
            } else if(data.state == "ready"){
              scope.csv_link = data.csv_link;
              scope.xls_link = data.xls_link;
              scope.setState("ready");
            } else if(data.state == "error"){
              scope.setState("error");
            }
          });
        };

        scope.$on('openExportPopup', function (their_scope, args) {
          scope.export_type = args.type;
          scope.open();
          scope.shortPolling();
        });
      }
    };
  }
])


.controller('SaveTemplateForm', ['$scope', 'filtersQuery', function ($scope, filtersQuery) {
  $scope.$watch(filtersQuery.getQuery, function(){
    $scope.query = JSON.stringify(filtersQuery.getQuery());
  }, true);

}])


;
