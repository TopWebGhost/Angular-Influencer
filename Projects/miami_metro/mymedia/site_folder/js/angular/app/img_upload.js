'use strict';

angular.module('theshelf')

.directive('imageUpload', ['$compile', '$rootElement',
  function ($compile, $rootElement) {
    return {
      restrict: 'A',
      scope: true,
      link: function (scope, iElement, iAttrs) {
        scope.upload = function (url, aspect, uploadData) {
          var wrapper = angular.element("<span>");
          var options = [];
          if(iAttrs.noReload !== undefined){
            options.push("no-reload");
          }
          if(iAttrs.successBc !== undefined){
            options.push('success-bc="'+iAttrs.successBc+'"');
          }

          if ($rootElement.find('[image-upload-popup]').length > 0)
            return;

          scope.uploadData = uploadData;

          var elem = angular.element("<span image-upload-popup url='" + url + "' aspect='" + aspect + "' " + (options.join(' ')) + " upload-data='uploadData'></span>");
          $rootElement.append(wrapper);
          wrapper.append(elem);
          $compile(wrapper.contents())(scope);
        };
      }
    };
  }
])
;
