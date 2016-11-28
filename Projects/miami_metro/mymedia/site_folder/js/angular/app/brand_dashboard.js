'use strict';

angular.module('theshelf')

.controller('DashboardCtrl', ['$scope', '$rootScope',
    function($scope, $rootScope) {
        $scope.doOpenFavoritePopup = function(options) {
            $rootScope.$broadcast('openFavoritePopup', options);
        };
        $scope.populatePageInfo = function(info) {
            $scope.page_info = info;
        };
        $scope.$on('dashboard_brand', function(their_scope, dashboard_brand){
            $scope.dashboard_brand = dashboard_brand;
        });
        $scope.dashboard_brand = null;
        $scope.total = 0;
        $scope.totalLoading = true;
        $scope.startDate = null;
        $scope.endDate = null;

        $scope.$on('doOpenFavoritePopup', function(theirScope, options) {
            $scope.doOpenFavoritePopup(options);
        });
    }
])

.directive('dashboardChart', [
    function() {
        return {
            restrict: 'A',
            scope: {
                dashboardChart: "=",
            },
            template: '<div class="dashboard_chart_container"><div class="dashboard_chart"></div><div class="chart_label">{{label}}</div>',
            link: function(scope, iElement, iAttrs) {
                var setup = {
                    element: iElement.find('.dashboard_chart'),
                    data: scope.dashboardChart.samples.map(function(e) {
                        return {v:e.v, ts:e.ts*1000};
                    }),
                    xkey: 'ts',
                    ykeys: ["v"],
                    labels: [scope.dashboardChart.type],
                    pointSize: 0,
                    lineWidth: 1,
                    hideHover: true,
                    fillOpacity: 0.1,
                    smooth: false,
                    behaveLikeLine: true,
                };
                scope.label = scope.dashboardChart.type;
                setTimeout(function() {Morris.Area(setup)}, 0);
            }
        };
    }
])

.directive('dashboardCompetitorsChart', [
    function() {
        return {
            restrict: 'A',
            scope: {
                dashboardCompetitorsChart: "=",
                keys: "=",
                labels: "=",
                title: "@",
            },
            template: '<div class="dashboard_chart_container"><div class="dashboard_chart"></div><div class="chart_label">{{label}}</div>',
            link: function(scope, iElement, iAttrs) {
                var setup = {
                    element: iElement.find('.dashboard_chart'),
                    data: scope.dashboardCompetitorsChart,
                    xkey: 'ts',
                    ykeys: scope.keys,
                    labels: scope.labels,
                    pointSize: 0,
                    lineWidth: 1,
                    hideHover: true,
                    fillOpacity: 0.1,
                    smooth: false,
                    behaveLikeLine: true,
                };
                scope.label = scope.title;
                setTimeout(function() {Morris.Area(setup)}, 0);
            }
        };
    }
])

.directive('dashboardNav', ['$rootScope', 'keywordQuery', 'dashboard_brand', '$timeout',
    function($rootScope, keywordQuery, dashboard_brand, $timeout) {
        return {
            restrict: 'A',
            scope: true,
            link: function(scope, iElement, iAttrs) {
                saved_competitions = [];
                scope.competitors = saved_competitions;
                scope.setCompetitor = function(selected) {
                    if (selected !== undefined)
                        scope.competitor = selected;
                    $rootScope.$broadcast("dashboard_brand", scope.competitor);
                    keywordQuery.setQuery(scope.competitor, "brand");
                    $rootScope.$broadcast("setKeywordFilters", scope.competitor, "brand");
                    localStorage.setItem("last_competitor", JSON.stringify(scope.competitor));
                };
                scope.current_brand = _.findWhere(scope.competitors, {current: true});
                if(dashboard_brand === null){
                    try{
                        dashboard_brand = JSON.parse(localStorage.getItem("last_competitor"));
                    }catch(e){
                        dashboard_brand = null;
                    }
                    if(dashboard_brand === null){
                        dashboard_brand = scope.current_brand;
                    }
                    scope.competitor = {
                        text: dashboard_brand.text,
                        value: dashboard_brand.value
                    };
                    $timeout(function(){
                        $rootScope.$broadcast("dashboard_brand", dashboard_brand);
                    }, 10);
                    keywordQuery.setQuery(dashboard_brand, "brand");
                }
            }
        };
    }
])

.directive('brandMentioningInfluencers', ['$rootScope', 'keywordQuery', '$timeout', 'dashboard_brand',
    function($rootScope, keywordQuery, $timeout, dashboard_brand) {
        return {
            restrict: 'A',
            link: function(scope, iElement, iAttrs) {
                if(dashboard_brand === null){   
                    // dashboard nav will handle it
                    return;
                }
                keywordQuery.setQuery(dashboard_brand, "brand");
            }
        };
    }
])

;
