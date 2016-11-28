'use strict';

angular.module('theshelf')

.directive('brandNav', ['$rootScope', 'nav_config', '$timeout', '$http', '$window', 'context', 'tsBrandNavigation',
    function($rootScope, nav_config, $timeout, $http, $window, context, tsBrandNavigation) {
        return {
            restrict: 'A',
            scope: true,
            link: function(scope, iElement, iAttrs) {
                scope.nav_config = nav_config;

                if (scope.navigation)
                    scope.navigation.config = scope.nav_config;

                scope.context = context;
                scope.campaigns_enabled = context.campaignsEnabled;
                scope.profile_enabled = context.profileEnabled;
                scope.non_campaign_messaging_enabled = context.nonCampaignMessagingEnabled;

                scope.$on('preferences-changed', function(their_scope, data) {
                    console.log('preferences-changed', data);
                    for (var i in data)
                        scope[i] = data[i];
                });

                scope.reloadPage = function() {
                    $window.location.reload();
                };

                var update_dom = function(){
                  if(scope.nav_config.visible){
                    $("body").removeClass("min_sidebar");
                  }else{
                    $("body").addClass("min_sidebar");
                  }
                };
                update_dom();

                scope.toggleSidebarMini = function(){
                  scope.nav_config.visible = !scope.nav_config.visible;
                  update_dom();
                };

                scope.openStripePopup = function(plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time) {
                    scope.$broadcast("openStripePopup", plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time);
                };

                scope.isTabActive = function(tabName) {
                    return scope.nav_config.tab == tabName;
                };

                scope.toggleTabActive = function(tabName) {
                    if(!scope.nav_config.visible){
                        scope.nav_config.visible = true;
                        scope.nav_config.tab = tabName;
                        update_dom();
                        return;
                        //window.location.assign(angular.element(".primary_tab_"+tabName+" .nav_default").attr('href'));
                    }
                    if (scope.nav_config.tab == tabName) {
                        scope.nav_config.tab = null;
                    } else {
                        scope.nav_config.tab = tabName;
                    }
                };

                scope.isSubTabActive = function(tabName) {
                    return scope.nav_config.sub_tab == tabName;
                };

                scope.toggleSubTabActive = function(tabName) {
                    if (scope.nav_config.sub_tab) {
                        scope.nav_config.sub_tab = null;
                    } else {
                        scope.nav_config.sub_tab = tabName;
                    }
                };

                scope.$on('toggleSubTabActive', function(their_scope, tabName) {
                    scope.toggleSubTabActive(tabName);
                });

                scope.getTabClasses = function(tabName) {
                    var classes = [];
                    if (scope.isTabActive(tabName)) {
                        classes.push("selected");
                    }
                    return classes.join(" ");
                };

                scope.getSubTabClasses = function(tabName) {
                    var classes = [];
                    if (scope.isSubTabActive(tabName)) {
                        classes.push("selected");
                    }
                    return classes.join(" ");
                };

                scope.notifyCollectionPopup = function(){
                    console.log("tu!");
                    $(".fade_away_tip").fadeIn("fast");
                    setTimeout(function() {
                        $(".fade_away_tip").fadeOut();
                    }, 3000);
                };

                scope.closeCollectionPopup = function(){
                    $(".fade_away_tip").hide();
                };

                scope.clearNotifications = function(type){
                    $(".badge_"+type).remove();
                    $("."+type+"_notification").remove();
                    $http.post(iAttrs.notifications, {'command': 'clear', 'type': type});
                };

                tsBrandNavigation.setConfig(nav_config);

                scope.$on("notifyCollectionPopup", scope.notifyCollectionPopup);

                var recalc_sidebar_height = function(){
                    var top_pos = iElement.find('.bottom_bar').position().top;
                    var btm_pos = iElement.find('.nano').position().top;
                    iElement.find(".side_bar_content").css({height: top_pos-btm_pos});
                    iElement.find(".nano").nanoScroller({alwaysVisible: false});
                };
                $(window).resize(recalc_sidebar_height);
                setTimeout(function(){
                    recalc_sidebar_height();
                    $(".primary_nav_icons.toggle_open").click(function(){
                        if($(this).hasClass("open")){
                            $('.glob_side_bar').addClass('toggle_btn_clicked');
                            if(!scope.nav_config.visible){
                                scope.$apply(function(){
                                    scope.nav_config.visible = true;
                                    update_dom();
                                });
                            }
                        }else{
                            $('.glob_side_bar').removeClass('toggle_btn_clicked');
                        }
                    });
                    $(document).on('click', function(evt) {
                        if($(evt.target).closest('.toggle_open').length == 0){
                            $('.glob_side_bar').removeClass('toggle_btn_clicked');
                        }
                    });
                }, 100);
            }
        };
    }
])

// .directive('dashboardNavSimple', ['saved_competitions',
//     function(saved_competitions) {
.directive('dashboardNavSimple', [function() {
        return {
            restrict: 'A',
            scope: true,
            link: function(scope, iElement, iAttrs) {
                saved_competitions = [];
                scope.competitors = saved_competitions;
                scope.current_brand = _.findWhere(scope.competitors, {current: true});
                scope.setCompetitor = function(selected) {
                    if (selected !== undefined)
                        scope.competitor = selected;
                    localStorage.setItem("last_competitor", JSON.stringify(scope.competitor));
                };
                var dashboard_brand;
                try{
                    dashboard_brand = JSON.parse(localStorage.getItem("last_competitor"));
                    console.log('aaa');
                    console.log(dashboard_brand);
                }catch(e){
                    dashboard_brand = null;
                }
                if(dashboard_brand === null){
                    dashboard_brand = scope.current_brand;
                    // if(scope.competitors.length>0){
                    //     dashboard_brand = scope.competitors[0];
                    // }
                }
                scope.competitor = null;
                if(dashboard_brand){
                    scope.competitor = {
                        text: dashboard_brand.text,
                        value: dashboard_brand.value
                    };
                }
            }
        };
    }
])


;
