// .controller('KeywordFilterCtrl', ['$scope', '$timeout', 'keywordQuery', '$rootScope', function ($scope, $timeout, keywordQuery, $rootScope) {
//   $scope.filterTimeout = null;
//   $scope.keyword = null;
//   $scope.type = 'all';

//   $scope.types = [
//       {value: "all", text:"All"},
//       //{value: "keyword", text:"Keywords"},
//       {value: "brand", text:"Brand URL"},
//       {value: "hashtag", text: "#"},
//       {value: "mention", text: "@"},
//       //{value: "location", text:"Location"}
//       //{value: "blogname", text:"Blog Name"},
//       //{value: "blogurl", text:"Blog URL"},
//       //{value: "name", text:"Name"}
//   ];
//   $scope.type_selected = {value: "all", text:"All"};

//   $scope.updateType = function(selected){
//     if (selected !== undefined)
//         $scope.type_selected = selected;
//     $scope.type_selected = selected;
//     $scope.type = $scope.type_selected.value;
//     $scope.startFilteringTimeout();
//   }

//   $scope.doFilter = function(){
//     keywordQuery.setQuery($scope.keyword, $scope.type);
//     $rootScope.$broadcast("setKeywordFilters", $scope.keyword, $scope.type);
//   };

//   $scope.startFilteringTimeout = function(){
//     $scope.$emit("hasKeywordSet", !!$scope.keyword);
//     if($scope.keyword == null){
//       return;
//     }
//     if($scope.filterTimeout){
//       $timeout.cancel($scope.filterTimeout);
//     }
//     $scope.filterTimeout = $timeout($scope.doFilter, 2000);
//   }


//   $scope.$watch('keyword', $scope.startFilteringTimeout);
//   $scope.$watch('type', $scope.startFilteringTimeout);
// }])


// .directive('autocompleteInput', ['$timeout', '$http', 'keywordQuery', '$rootScope', '$q',
//     function($timeout, $http, keywordQuery, $rootScope, $q) {
//         return {
//             templateUrl: tsConfig.STATIC_PREFIX + 'js/angular/templates/search_autocomplete_input.html',
//             replace: true,
//             restrict: 'A',
//             scope: true,
//             controller: function($scope, $element, $attrs, $transclude) {
//                 if ($attrs.autocompleteUrl)
//                     $scope.autocompleteUrl = $attrs.autocompleteUrl;
//                 $scope.autocompleteTimeout = null;
//                 $scope.cancelPromise = null;
//                 $scope.open = false;
//                 var lockAutocompleteTimeout = false;
//                 $scope.search = function(keyword, type) {
//                     $scope.open = false;
//                     keywordQuery.setQuery(keyword, type);
//                     $rootScope.$broadcast("setKeywordFilters", keyword, type);
//                     lockAutocompleteTimeout = true;
//                     $scope.keyword = keyword;
//                     $scope.type = type;
//                     $timeout(function(){
//                       lockAutocompleteTimeout = false;
//                     }, 250);
//                 };
//                 $scope.doAutocomplete = function() {
//                     if($scope.cancelPromise !== null){
//                       $scope.cancelPromise.resolve();
//                     }
//                     $scope.cancelPromise = $q.defer();
//                     $scope.options = [];
//                     $scope.open = true;
//                     $scope.loading = true;
//                     $scope.type = null;
//                     $http({
//                         method: 'get',
//                         params: {
//                             query: $scope.keyword
//                         },
//                         url: $scope.autocompleteUrl,
//                         timeout: $scope.cancelPromise.promise
//                     }).success(function(options) {
//                         $scope.options = options;
//                         $scope.loading = false;
//                     }).error(function() {
//                     });
//                 };
//                 $scope.startAutocompleteTimeout = function() {
//                     if (lockAutocompleteTimeout === true) {
//                         return;
//                     }
//                     if ($scope.keyword === null || $scope.keyword === undefined) {
//                         return;
//                     }
//                     if ($scope.autocompleteTimeout) {
//                         $timeout.cancel($scope.autocompleteTimeout);
//                     }
//                     $scope.autocompleteTimeout = $timeout($scope.doAutocomplete, 500);
//                 }
//                 $scope.$watch('keywords', $scope.startAutocompleteTimeout);
//             },
//             link: function postLink(scope, iElement, iAttrs) {
//                 $(document).on('click', function(evt) {
//                     scope.$apply(function() {
//                         if ($(evt.target).closest('.autocomplete_input').length === 0) {
//                             scope.open = false;
//                         } else {
//                             if (scope.keyword) {
//                                 scope.open = true;
//                             }
//                         }
//                     });
//                 });
//             }
//         };
//     }
// ])