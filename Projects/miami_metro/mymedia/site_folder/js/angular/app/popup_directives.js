angular.module('theshelf')


.directive('bookmarkPopup', ['_', '$window', '$q', '$timeout', 'Restangular', 'singletonRegister', 'tsConfig',
  'disableScrollService', 'NotifyingService', 'context',
  function(_, $window, $q, $timeout, Restangular, singletonRegister, tsConfig, disableScrollService,
      NotifyingService, context) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/bookmark_popup.html'),
      controller: function($scope) {
        var vm = this;

        vm.opened = false;

        vm.note = null;
        vm.imgUrl = null;

        vm.types = ['tag', 'post',];
        vm.type = 'tag';

//       scope.$watch(iAttrs.model, _.debounce(saveModel, 2000), true);
//     }
//   };
// }])

        vm.toggleSelect = function(group) {
          group.selected = !group.selected;
          vm.updateGroups({
            influencer: vm.influencer,
            groups: [group],
          });
        };

        vm.getGroups = function(params) {
          Restangular
            .one('tags')
            .get(_.isArray(params.influencer) ? {
              brand: context.visitorBrandId
            } : {brand: context.visitorBrandId, influencer_id: params.influencer})
            .then(function(data) {
              vm.imgUrl = data.imgUrl;
              vm.note = data.note;
              vm.groups = angular.copy(data.groups);
              vm.recentGroup = _.findWhere(vm.groups, {id: data.recentTag});
              $scope.setState('loaded');
              vm.initNanoScroller();
            }, function(response) {
              vm.setErrorMessage(response.data.content || 'Error!');
              $scope.setState('add_group_error');
            });
        };

        vm.updateGroups = function(params) {
          $scope.setState('adding_group');
          Restangular
            .one('tags', 1)
            .post('bookmark_influencer', {
              brand: context.visitorBrandId,
              influencer: params.influencer,
              groups: params.groups
                // .filter(function(g) { return g.selected; })
                .map(function(g) { return {id: g.id, selected: g.selected}; }),
            }).then(function(data) {
              vm.groupsListUpdate();
              if (vm.afterSuccessCb) vm.afterSuccessCb();
              $scope.close();
          }, function(response) {
            vm.setErrorMessage(response.data.content || 'Error!');
              $scope.setState('add_group_error');
          });
        };

        vm.addGroup = function(groupName) {
          $scope.setState('adding_group');

          return Restangular
            .all('tags')
            .post({
              name: groupName,
            }).then(function(response) {
              vm.groups.push(response);
              // $scope.setState('loaded');
              NotifyingService.notify('multiSelectFilter:tags:refresh');
              return response;
            }, function(response) {
              vm.setErrorMessage(response.data.content || 'Problem with collection creating');
              $scope.setState('add_group_error');
              return $q.reject();
            });
        };

        vm.addGroupAndBookmark = function(groupName, url) {
          vm.addGroup(groupName).then(function(group) {
            vm.updateGroups({
              influencer: vm.influencer,
              groups: [group],
            });
          }, function() {});
        };

        vm.groupsListUpdate = function() {
          var
            newCollections = {},
            influencers = _.isArray(vm.influencer) ? vm.influencer : [vm.influencer];

          vm.groups
            .filter(function(g) { return g.selected; })
            .forEach(function(g) {
              newCollections[g.id] = g.name;
            });

          angular.forEach(influencers, function(influencer) {
            NotifyingService.notify('user-collections-in-changed', {
              id: influencer,
              collections_in: angular.copy(newCollections),
              // has_collections_in: !_.isEmpty(newCollections),
              partial: vm.many,
            }, true);
          });
        };

        vm.openHandler = function(params) {
          if (vm.opened) return;

          vm.opened = true;
          $scope.open();
          vm.placeholderText = {
            tag: 'Add New Tag',
            post: 'Add New Post Collection',
          }[vm.type];

          vm.influencer = params.influencer;
          vm.many = _.isArray(params.influencer);
          vm.afterSuccessCb = params.afterSuccessCb;

          vm.getGroups({influencer: vm.influencer});
        };

        vm.saveNotes = function() {
          if (vm.note !== undefined && vm.note !== null) {
            console.log('saving notes...');
            Restangular
              .one('tags', 1)
              .post('save_notes', {
                brand: context.visitorBrandId,
                influencer: vm.influencer,
                note: vm.note,
              });
          }
        };

        vm.saveNotesDebounced = _.debounce(vm.saveNotes, 2000);

        vm.showLeftSide = function() {
          return !_.isNull(vm.imgUrl) || !_.isNull(vm.note);
        };
      },
      controllerAs: 'bookmarkPopupCtrl',
      link: function(scope, iElement, iAttrs, ctrl) {
        if (singletonRegister.getOrRegister('bookmarkPopup')) {
          iElement.remove();
          return;
        }

        ctrl.initNanoScroller = function() {
          $timeout(function() {
            iElement.find('.nano').nanoScroller({alwaysVisible: true});
          }, 100);
        };

        ctrl.setErrorMessage = function(text) {
          scope.errorMessage = text;
        };

        scope.close_cb = function() {
          ctrl.saveNotes();
          ctrl.opened = false;
          ctrl.note = null;
          // disableScrollService.do();
        };

        NotifyingService.subscribe(scope, 'openFavoritePopup', function(theirScope, params) {
          ctrl.openHandler(params);
        }, true);
      }
    };
  }])


.directive('favoritePopup', ['$http', '$q', '$rootScope', '$timeout', 'singletonRegister', 'tsConfig',
    'disableScrollService', 'NotifyingService', 'Restangular',
  function ($http, $q, $rootScope, $timeout, singletonRegister, tsConfig, disableScrollService,
      NotifyingService, Restangular) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/favorite_popup.html'),
      controller: function() {
        return;
        var vm = this;

        vm.note = null;

        vm.toggleSelect = function(group) {
          group.selected = !group.selected;
          vm.upload();


          // @todo: why?
          // if (group.col_id) {
          //   id_to_group[group.col_id].selected = group.selected;
          // } else {
          //   for(var i=0;i<scope.groups.length;i++){
          //     if(scope.groups[i].col_id == group.id){
          //         scope.groups[i].selected = group.selected;
          //     }
          //   }
          // }
        };

      },
      controllerAs: 'favoritePopupCtrl',
      link: function (scope, iElement, iAttrs, ctrl) {
        return;
        if (singletonRegister.getOrRegister('favoritePopup')) {
          iElement.remove();
          return;
        }

        scope.close_cb = function () {
          ctrl.opened = false;
          // if (disableScrollService.decr()) {
          //   $(window).disablescroll('undo');
          // }
        };

        ctrl.opened = false;

        scope.groups = [];
        scope.original_groups = [];

        scope.source = iAttrs.source;
        scope.target = iAttrs.target;

        scope.postPopup = false;
        scope.taggingPopup = true;

        scope.addNewGroupPlaceholderText = 'Add New Tag';

        scope.postSource = iAttrs.postSource;
        scope.postTarget = iAttrs.postTarget;

        scope.add_group_url = iAttrs.addGroup;
        scope.post_add_group_url = iAttrs.postAddGroup;

        scope.has_changes = false;

        var id_to_group = {};

        scope.$watch('groups', function(){
          scope.has_changes = !angular.equals(scope.groups, scope.original_groups);
        }, true);

        scope.groupsHandler = function(groups) {

          scope.groups = angular.copy(groups);

          angular.forEach(scope.groups, function(group) {
            group.selected = group.selected || false;
            group.toggled = group.toggled || false;
            group.type = group.type || 'collection';
          });

          for(var i = 0; i < scope.groups.length; i++) {
            id_to_group[scope.groups[i].id] = scope.groups[i];
          }

          scope.original_groups = angular.copy(groups);

          scope.setState("loaded");

          $timeout(function() {
            $(".nano").nanoScroller({alwaysVisible: true});
          }, 100);
        };

        scope.openHandler = function (their_scope, options) {
          if (ctrl.opened) return;
          
          ctrl.opened = true;
          ctrl.note = null;
          if (options === undefined)
            return;

          scope.open();

          scope.afterSuccessCb = options.afterSuccessCb;

          if (options.influencer !== undefined) {
            scope.influencer = options.influencer;
            scope.postPopup = false;
            scope.taggingPopup = true;
            scope.addNewGroupPlaceholderText = 'Add New Tag';
            scope.influencers = undefined;
            scope.post = undefined;
            scope.posts = undefined;
            scope.user = options.user;
          } else if (options.influencers !== undefined) {
            scope.influencers = options.influencers;
            scope.postPopup = false;
            scope.taggingPopup = true;
            scope.addNewGroupPlaceholderText = 'Add New Tag';
            scope.influencer = undefined;
            scope.post = undefined;
            scope.posts = undefined;
          } else if (options.post !== undefined) {
            scope.post = options.post;
            scope.postItem = options.item;
            scope.postPopup = true;
            scope.taggingPopup = false;
            scope.addNewGroupPlaceholderText = 'Add New Post Collection';
            scope.influencer = undefined;
            scope.influencers = undefined;
            scope.posts = undefined;
          } else if (options.posts !== undefined) {
            scope.posts = options.posts;
            scope.postPopup = true;
            scope.taggingPopup = false;
            scope.addNewGroupPlaceholderText = 'Add New Post Collection';
            scope.influencer = undefined;
            scope.influencers = undefined;
            scope.post = undefined;
          }

          if (options.groups !== undefined) {
            scope.groupsHandler(options.groups);
          } else {
            if (scope.postPopup) {
              var postHandler = function(data) {
                scope.img_url = scope.postItem.post_img || data.img_url;
                scope.groupsHandler(data.groups);
              };
              if (scope.post === undefined)
                scope.loadGroups(scope.postSource);
              else
                scope.loadGroups(scope.postSource, {post: scope.post}, postHandler);
            }
            else {
              scope.loadGroups(scope.source,
                (scope.influencer === undefined ? null : {influencer: scope.influencer}));
            }
          }
        };

        scope.loadGroups = function (source, params, handler) {
          params = params || {};
          handler = handler || function(data) {
            scope.img_url = data.imgUrl;
            ctrl.note = data.note;
            scope.groupsHandler(data.groups);
          };

          // Restangular
          //   .one('tags')
          //   .get({influencer_id: params.influencer})
          //   .then(function(data) {
          //     handler(data);
          //     $timeout(function () {
          //       $(window).disablescroll({excludedElements: iElement.find('[prevent-disablescrolling]')});
          //       disableScrollService.incr();
          //     });
          //   }, function() {
          //     scope.setState("load_error"); 
          //   });


          $http({
            method: 'GET',
            url: source,
            params: params
          }).success(function(data) {
            handler(data);
            $timeout(function () {
              $(window).disablescroll({excludedElements: iElement.find('[prevent-disablescrolling]')});
              disableScrollService.incr();
            });
          }).error(function (a, b, c, d) {
            scope.setState("load_error"); 
          });
        };

        NotifyingService.subscribe(scope, 'openFavoritePopup', scope.openHandler, true);

        // scope.toggleSelect = function(group){
        //   group.selected = !group.selected;
        //   if(group.col_id){
        //     id_to_group[group.col_id].selected = group.selected;
        //   }else{
        //     for(var i=0;i<scope.groups.length;i++){
        //       if(scope.groups[i].col_id == group.id){
        //           scope.groups[i].selected = group.selected;
        //       }
        //     }
        //   }
        //   scope.upload();
        // };

        var collectionsListUpdate = function(groups) {
          var new_collections = {};
          angular.forEach(groups, function(group, index) {
            if (group.selected) {
              new_collections[group.id] = group.name;
            }
          });
          var influencers = null;
          if (scope.influencers !== undefined) {
            influencers = scope.influencers
              .filter(function(inf) { return inf.selected; })
              .map(function(inf) { return inf.id; });
          } else if (scope.influencer !== undefined) {
            influencers = [scope.influencer];
          }

          if (influencers !== null) {
            influencers.forEach(function(influencer) {
              $rootScope.$broadcast('user-collections-in-changed', {
                id: influencer,
                collections_in: angular.copy(new_collections),
                has_collections_in: !_.isEmpty(new_collections)
              });
            });
          }
        };

        scope.upload = function (target) {

          if (target === undefined) {
            if (scope.taggingPopup) {
              target = scope.target;
            } else if (scope.postPopup) {
              target = scope.postTarget;
            } else {
              return;
            }
          }

          // not sure
          $rootScope.$broadcast("notifyCollectionPopup", {id: scope.influencer});

          scope.setState('uploading');

          var data = {
            groups: scope.groups,
          };

          if (scope.influencer !== undefined) {
            data.influencer = scope.influencer;
            data.note = ctrl.note;
          } else if (scope.influencers !== undefined)
            data.influencers = scope.influencers
              .filter(function(inf) { return inf.selected; })
              .map(function(inf) { return inf.id; });
          else if (scope.post !== undefined)
            data.post = scope.post;
          else if (scope.posts !== undefined)
            data.posts = scope.posts
              .filter(function(post) { return post.selected; })
              .map(function(post) { return post.id; });

          $http.post(target, data)
            .success(function(data) {
              if (scope.taggingPopup)
                collectionsListUpdate(scope.groups);
              if (data !== undefined && data.is_bookmarked !== undefined) {
                if (scope.post !== undefined)
                  scope.postItem.is_bookmarked = data.is_bookmarked;
                else if (scope.posts !== undefined)
                  scope.posts.forEach(function(post) {
                    if (post.selected)
                      post.is_bookmarked = data.is_bookmarked;
                  });
              }

              if (scope.afterSuccessCb !== undefined)
                scope.afterSuccessCb();
              
              scope.close();
              ctrl.note = null;
            })
            .error(function(a, b, c, d) {
              scope.setState("upload_error");
            });
        };

        ctrl.upload = scope.upload;

        scope.addGroup = function (new_group_name, url) {
          scope.setState('adding_group');
          if (scope.postPopup)
            url = scope.post_add_group_url;
          else
            url = scope.add_group_url;
          return $http.post(url, {
            name: new_group_name
          }).then(function (response) {
            scope.has_changes = true;
            scope.groups.push(response.data);
            scope.setState('loaded');
            setTimeout(function() {
              $(".nano").nanoScroller({alwaysVisible: true});
            }, 100);
          }, function (a, b, c, d) {
            scope.errorMessage = a || 'Problem with adding collection';
            scope.setState("add_group_error");
            return $q.reject();
          });
        };

        scope.addGroupAndBookmark = function(newGroupName, url) {
          scope.addGroup(newGroupName, url).then(function() {
            scope.upload();
          });
        };

      }
    };
  }
])


.directive('addReportPopup', ['$http', '$sce', 'tsConfig',
  function ($http, $sce, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/add_report_popup.html'),
      controller: function($scope) {
        $scope.oneAtATime = false;

        $scope.current_step = 0;
        $scope.forms = {};

        $scope.status = [
          {can_edit: true, is_completed: false, is_open: true},
          {can_edit: false, is_completed: false, is_open: false},
          {can_edit: false, is_completed: false, is_open: false}
        ];

        $scope.setCurrentStep = function(step) {    
          $scope.status[$scope.current_step]['is_open'] = false;
          $scope.current_step = step;
          $scope.status[step]['is_open'] = true;
          $scope.status[step]['can_edit'] = true;
        };

        $scope.moveStep = function(step) {    
          var current_step = $scope.current_step;
          if ($scope.status[step].can_edit == true) {
            $scope.current_step = step;
          }
        };

        $scope.moveNextStep = function(step) {
          var current_step = step;
          $scope.status[current_step]['is_completed'] = true;
          current_step = current_step + 1;
          $scope.setCurrentStep(current_step);
        }

        $scope.submitStep1 = function () {    
          if ($scope.forms.form_step1.$valid) {      
            $scope.moveNextStep(0);
            return true;
          } 
          return false;
        };

        $scope.submitStep2 = function (options) {    
          if (options && options.selected) {
            $scope.addReport();
            $scope.moveNextStep(1);
            return true;
          } else if ($scope.forms.form_step2.$valid) {
            $scope.createCollection();
            $scope.moveNextStep(1);
            return true;
          }
          return false;
        };

      },
      link: function (scope, iElement, iAttrs) {
        scope.targetUrl = iAttrs.targetUrl;
        scope.tagsUrl = iAttrs.tagsUrl;
        scope.addCollectionUrl = iAttrs.addCollectionUrl;
        scope.getCollectionsUrl = iAttrs.getCollectionsUrl;
        scope.tags = {
          loading: false,
          available: [],
          selected: null,
          update: function() {

          }
        };

        scope.reportData = {
          update: function(selected) {
            scope.reportData.selectedCollection = selected;
          },
          collectionsLoading: false,
        };

        scope.reset = function() {
          scope.status = [
            {can_edit: true, is_completed: false, is_open: true},
            {can_edit: false, is_completed: false, is_open: false},
            {can_edit: false, is_completed: false, is_open: false}
          ];
          angular.extend(scope.reportData, {
            name: null,
            newCollectionName: null,
            selectedCollection: {'text': 'Select a collection...'},
            collections: []
          });
        };

        scope.$on('openAddReportPopup', function (their_scope, options) {
          if (options === undefined)
            options = {};
          scope.reset();
          scope.open();
          scope.setState('loading');
          $http({
            method: 'GET',
            url: scope.getCollectionsUrl || '',
          }).success(function(data) {
            scope.setState('add_report');
            scope.reportData.collections = angular.copy(data);
          }).error(function() {
            scope.errorMessage = 'Problem with loading post collections.';
            scope.setState("add_report_error");
          });
        });

        scope.createCollection = function() {
          scope.addReport({createCollection: true});
        };

        scope.addReport = function(options) {
          if (!scope.reportData.name)
            return;
          scope.message_text = 'Adding a report...';
          scope.setState('display_message');
          $http.post(scope.targetUrl, {
            name: scope.reportData.name,
            selected_collection_id: scope.reportData.selectedCollection.value,
            new_collection_name: scope.reportData.newCollectionName
          }).success(function(data) {

            scope.close = function() {
              scope.setState('loading');
              window.location.reload();
            }

            if (options && options.createCollection) {
              scope.afterReportAddedText = ["The report has been created, now you need to",
              "add posts. For that, you'll need to go back to the Search tab",
              "and bookmark Blog Posts. If you already have a Tagged group of",
              "influencers that you want to work with, simply filter by that",
              "group, then select the Blog Post tab. Then bookmark any Blog post",
              "that represents content similar to what you want to create via them."].join(' ');
              // scope.setState('after_report_added');
              scope.setState('loading');
              window.location.href = "/search/main";
            } else {
              scope.close();
            }

          }).error(function(error) {
            scope.errorMessage = error || 'Problem with adding report';
            scope.setState('add_report_error');
          });
        };
      }
    };
  }
])


.directive('postAnalyticsStatsPopup', ['$http', '$timeout', 'tsConfig', function($http, $timeout, tsConfig) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/post_analytics_stats_popup.html'),
    link: function(scope, iElement, iAttrs) {
      scope.getUrl = iAttrs.getUrl;

      scope.updateNano = function() {
        $timeout(function() {
          $(".nano").nanoScroller({alwaysVisible: true});
          $(".nano").nanoScroller({ scroll: 'top' });
        }, 200);
      };

      scope.buildChart = function (chart) {
        var data = chart.data;
        for (var i = data.length - 2; i >= 0; i--) {
          for (var key in data[i]) {
            var value = data[i];
            if (!isNaN(value[key]) && value[key] == 0) {
              value[key] = data[i + 1][key];
            }
          }
        }

        var morrisData = {
          element: chart.element,
          data: data,
          xkey: 'date',
          ykeys: chart.ykeys,
          labels: chart.labels,
          // lineColors: colors,
          pointSize: 0,
          lineWidth: 1,
          hideHover: true,
          fillOpacity: 0.1,
          smooth: false,
          behaveLikeLine: true,
        };
        $timeout(function() {
          try {
            Morris.Area(morrisData);
            scope.updateNano();
            chart.loaded = true;
          } catch(e) {console.log('1', e);};
        }, 400);
      };

      scope.$on('openPostAnalyticsStatsPopup', function(their_scope, options) {
        scope.open();

        scope.loading = true;
        scope.error = false;

        $http({
          method: 'GET',
          url: scope.getUrl,
        }).success(function(response) {

          scope.error = true;
          scope.loading = false;

          scope.clicksChart = {
            data: response.data.clicks,
            element: 'clicks_stats_chart',
            labels: ['Total Clicks', 'Unique Clicks'],
            ykeys: ['count_clicks', 'count_unique_clicks'],
            title: 'Clicks',
          };

          scope.viewsChart = {
            data: response.data.views,
            element: 'views_stats_chart',
            labels: ['Total Views', 'Unique Views'],
            ykeys: ['count_views', 'count_unique_views'],
            title: 'Views',
          };

          scope.buildChart(scope.clicksChart);
          scope.buildChart(scope.viewsChart);

        }).error(function() {
          scope.error = true;
          scope.loading = false;
        });

      });
    }
  };
}])


.directive('addCollectionPopup', ['$http', '$sce', 'tsConfig',
  function ($http, $sce, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/add_collection_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.add_group_url = iAttrs.addGroup;
        scope.popup_title = iAttrs.popupTitle;
        scope.popup_instruction = iAttrs.popupInstruction;
        scope.adding_text = iAttrs.addingText;
        scope.redirect_url = iAttrs.redirectUrl;
        scope.redirect_btn_text = iAttrs.redirectBtnText;
        scope.collectionType = iAttrs.collectionType || 'tag';

        scope.$on('openAddCollectionPopup', function (their_scope, options) {
          var collectionType;
          if (options === undefined || options.collectionType === undefined)
            collectionType = 'tag';
          else
            collectionType = options.collectionType;
          if (collectionType !== scope.collectionType)
            return;
          scope.open();
          scope.setState("add_group");
        });      

        scope.redirect = function() {
          setTimeout(function() {
            window.location.replace(scope.redirect_url);
          }, 10);
        };

        scope.addGroup = function (new_group_name) {
          scope.setState('adding_group');
          var output_jobs = [];
          $http.post(scope.add_group_url, {
            name: new_group_name,
            jobs: output_jobs
          })
            .success(function (data) {
              setTimeout(function() {
                window.location.reload();
              }, 10);
            })
            .error(function (a, b, c, d) {
              scope.errorMessage = a || 'Problem with adding collection';
              scope.setState("add_group_error");
            })
        };
      }
    };
  }
])

.directive('mailboxMoreInfoPopup', ['$rootScope', '$http', '$timeout', 'tsConfig', function($rootScope, $http, $timeout, tsConfig) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/mailbox_more_info_popup.html'),
    link: function(scope, iElement, iAttrs) {
      scope.updateNano = function() {
        $timeout(function() {
          $(".nano").nanoScroller({alwaysVisible: true});
          $(".nano").nanoScroller({ scroll: 'top' });
        }, 200);
      };
      scope.updateUrl = iAttrs.updateUrl;
      scope.extraDataUrl = iAttrs.extraDataUrl;
      scope.$on('openMailboxMoreInfoPopup', function(their_scope, options) {
        console.log(options);
        scope.mId = options.mId;
        scope.cId = options.cId;
        scope.values = angular.copy(options.values);
        scope.loading = false;
        scope.showContractInfo = options.showContractInfo === undefined ? true : options.showContractInfo;
        scope.open();
        scope.extraLoading = true;
        $http({
          method: 'GET',
          url: scope.extraDataUrl,
          params: {
            contract_id: scope.cId,
          }
        }).success(function(response) {
          scope.extraLoading = false;
          scope.documents = response.data;
          scope.updateNano();
        }).error(function() {
          console.log('error');
        });
      });

      scope.update = function() {
        scope.loading = true;
        $http({
          method: 'POST',
          url: scope.updateUrl,
          data: {
            id: scope.cId,
            modelName: 'Contract',
            values: scope.values,
          }
        }).success(function() {
          scope.loading = false;
          $rootScope.$broadcast('updateMailboxTableCell', {mId: scope.mId, values: scope.values});  
        }).error(function() {
          scope.loading = false;
          scope.setState('error');
        })
      };

      function infoJson(options) {
        var newJson = {};
        newJson[options.doc.id] = {};
        newJson[options.doc.id][options.field.key] = options.field.value;
        return newJson;
      }

      scope.extraUpdate = {
        update: function(options) {
          options.field.loading = true;
          $http({
            method: 'POST',
            url: scope.updateUrl,
            data: {
              id: scope.cId,
              modelName: 'Contract',
              json_fields: {
                'info': infoJson(options),
              },
            }
          }).success(function() {
            options.field.loading = false;
            options.field.changed = false;
          }).error(function() {
            scope.setState('error');
          })
        },
        loading: false,
        error: false,
      };

    }
  };
}])

.directive('campaignCreatePopup', ['$http', 'context', 'tsConfig', function($http, context, tsConfig) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/campaign_create_popup.html'),
    link: function (scope, iElement, iAttrs) {
      scope.updateUrl = iAttrs.updateUrl;
      scope.redirectUrl = iAttrs.redirectUrl;
      scope.context = context;
      scope.redirect = function(response) {
        scope.setState('loading');
        scope.setBackgroundType('black');
        window.location.href = response.redirectUrl;
      };
      scope.$on('openCampaignCreatePopup', function(their_scope, options) {
        scope.setBackgroundType(null);
        scope.campaignName = '';
        scope.clientName = '';
        scope.clientURL = '';
        scope.open();
      });
    }
  };
}])

.directive('editCollectionPopup', ['$http', '$sce', 'tsConfig',
  function ($http, $sce, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/edit_collection_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.edit_group_url = iAttrs.editGroup;
        scope.collectionType = iAttrs.collectionType || 'tag';

        scope.$on('openEditCollectionPopup', function (their_scope, options) {
          var collectionType;
          var id, name, desc, jobs;
          if (options === undefined || options.collectionType === undefined)
            collectionType = 'tag';
          else
            collectionType = options.collectionType;
          if (collectionType !== scope.collectionType)
            return;
          if (options !== undefined) {
            id = options.id;
            name = options.name;
            desc = options.desc;
            jobs = options.jobs;
          }
          scope.id = id;
          scope.new_name = name;
          scope.new_desc = desc;
          scope.jobs = [];
          scope.selectedJobsCount = 0;
          var unregisterCheckboxToggledEvent = scope.$on('checkboxSelectOptionToggled', function(evt, option) {
            if (option.checked)
              scope.selectedJobsCount++;
            else
              scope.selectedJobsCount--;
          });
          scope.close_cb = function() {
            unregisterCheckboxToggledEvent();
          };
          // if(campaigns !== null){
          //   for(var i=0;i<campaigns.length; i++){
          //     scope.jobs.push({
          //       text: $sce.trustAsHtml(campaigns[i].text + ((campaigns[i].bound !== false && campaigns[i].bound.id != id)?(" (bound to "+campaigns[i].bound.name+")"):"")),
          //       value: campaigns[i].value,
          //       disabled: false,
          //       checked: campaigns[i].bound !== false && campaigns[i].bound.id == id
          //     });
          //     if (scope.jobs.slice(-1)[0].checked)
          //       scope.selectedJobsCount++;
          //   }
          // }
          scope.open();
          scope.setState("edit_group");
        });

        scope.editGroup = function (new_name, new_desc) {
          var output_jobs = [];
          for(var i=0;i<scope.jobs.length; i++){
            if(scope.jobs[i].checked){
              output_jobs.push(scope.jobs[i].value);
            }
          }
          scope.setState('uploading');
          $http.post(scope.edit_group_url, {
            id: scope.id,
            name: new_name,
            description: new_desc,
            jobs: output_jobs
          })
            .success(function (data) {
              window.location.reload();
            })
            .error(function (a, b, c, d) {
              scope.errorMessage = a || "Problem with saving changes";
              scope.setState("upload_error");
            })
        };
      }
    };
  }
])

.directive('addPostAnalyticsUrlsPopup', ['$timeout', '$http', '$q', 'tsConfig', function($timeout, $http, $q, tsConfig) {
    return {
      restrict: 'A',
      // scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/add_post_analytics_urls_popup.html'),
      controller: function($scope) {
        $scope.oneAtATime = true;

        $scope.current_step = 0;
        $scope.forms = {};

        $scope.setState = function(state) {
          $scope.state = state;
        };

        $scope.status = [
          {can_edit: true, is_completed: true, is_open: true},
          {can_edit: true, is_completed: false, is_open: false},
          {can_edit: false, is_completed: false, is_open: false}
        ];

        $scope.$watch('status', function(nv, ov) {
          $scope.updateNano();
        }, true);

        $scope.setCurrentStep = function(step) {    
          $scope.current_step = step;
          for (var i in $scope.status) {
            $scope.status[i].is_open = false;
          }
          $scope.status[step]['is_open'] = true;
          $scope.status[step]['can_edit'] = true;
        };

        $scope.moveStep = function(step) {    
          var current_step = $scope.current_step;
          if ($scope.status[step].can_edit == true) {
            $scope.current_step = step;
          }
        };

        $scope.moveNextStep = function(step) {
          var current_step = step;
          $scope.status[current_step]['is_completed'] = true;
          current_step = current_step + 1;
          $scope.setCurrentStep(current_step);
        }

        $scope.submitStep = function (step) {
          if ($scope.isEdit()) {
            $scope.status[step].is_open = false;
          } else {
            $scope.moveNextStep(step);
          }
        };

        var genericYes = function(url) {

          var deferred = $q.defer();

          $http({
            method: 'POST',
            url: url
          }).success(function(data) {
            if (data.error !== undefined) {
                deferred.reject({data: data.error});
            } else {
                deferred.resolve();
            }
          }).error(function(data) {
            deferred.reject({data: data || 'Error!'});
          });

          return deferred.promise;
        };

        $scope.removePostAnalytics = function(url, index) {

          var yes = function() {
              return genericYes(url).then(function() {
                if (index !== undefined) {
                  $scope.reportData.enteredUrls.splice(index, 1);
                }
              });
          };

          $scope.$broadcast('openConfirmationPopup',
              'Are you sure you want to remove?',
              yes, null, {loading: true});
        };

        $scope.toggleRemoved = function(item) {
          item.removed = !item.removed;
        };

      },
      link: function(scope, iElement, iAttrs) {
        function collectionPlaceholder() {
          return {'text': 'Select a collection...'};
        }

        scope.canSave = function() {
          if (!scope.isChanged()) {
            return false;
          }
          if (scope.isReport() && !scope.reportId) {
            return scope.reportData.name && (scope.reportData.newCollectionName || scope.reportData.selectedCollection.value);  
          } else {
            return scope.reportData.name;
          }
        };

        scope.isStepValid = function(step) {
          function firstStep() {
            return scope.reportData.name && scope.reportData.name.length > 0;
          }

          function secondStep() {
            if (scope.isReport() && !scope.isEdit()) {
              return (scope.reportData.newCollectionName && scope.reportData.newCollectionName.length > 0) || (scope.reportData.selectedCollection.value !== undefined);
            }
            return true;
          }

          var stepValidators = [firstStep, secondStep];
          return stepValidators[step]();
        };

        scope.isChanged = function() {
          if (scope.state === 'loading' || scope.state === 'saving')
            return false;
          if (scope.reportData.urls) {
            return true;
          }
          if (_.any(scope.reportData.enteredUrls, function(item) { return item.removed; })) {
            return true;
          }
          if (scope.reportId || scope.collectionId) {
            return (scope.isReport() && scope.reportData.name !== scope.reportName) || (!scope.isReport() && scope.reportData.name !== scope.collectionName);
          } else {
            return scope.reportData.newCollectionName || scope.reportData.name || scope.reportData.selectedCollection.value;
          }
        };

        scope.isEdit = function() {
          return scope.reportId || scope.collectionId;
        };

        scope.reportData = {
          updateCollection: function(selected) {
            scope.reportData.newCollectionName = null;
          },
          clearCollectionSelect: function() {
            scope.reportData.selectedCollection = collectionPlaceholder();
          },
          clearCollectionName: function() {
            scope.reportData.newCollectionName = null;
          },
          extractedUrls: function() {
            return filtering(scope.reportData.urls, true);
          },
          collections: []
        };

        scope.reset = function() {
          scope.current_step = 0;
          angular.extend(scope.reportData, {
            urls: null,
            name: angular.copy(scope.reportName || scope.collectionName),
            newCollectionName: null,
            selectedCollection: collectionPlaceholder(),
            enteredUrls: [],
            showOnlyUnique: false
          });
          scope.status = [
            {can_edit: true, is_completed: true, is_open: true},
            {can_edit: true, is_completed: false, is_open: false},
            {can_edit: false, is_completed: false, is_open: false}
          ];
          scope.setCurrentStep(scope.isEdit() ? 1 : 0);
        };

        scope.updateNano = function(){
          $timeout(function() {
              iElement.find('.nano').nanoScroller({alwaysVisible: true});
              iElement.find('.nano').nanoScroller({ scroll: 'top' });
          }, 100);
        };

        var urlRegex = /(https?:\/\/[^\s]+)/g;

        function filtering(text, unique) {
          if (text === null || text === undefined || text.length === 0)
            return [];
          if (unique) {
            return _.uniq(text.match(urlRegex));
          } else {
            return text.match(urlRegex) || [];
          }
        }

        // scope.$watch('status', function(nv, ov) {
        //   for (var i in nv) {
        //     if (nv[i].is_open !== ov[i].is_open && nv[i].is_open === false) {
        //       scope.current_step = -1;
        //     }
        //   }
        // }, true);

        scope.$watch('reportData.name', function(nv, ov) {
          if (ov !== undefined && ov !== null) {
            scope.status[0].is_completed = (nv === ov);
          }
        });

        // scope.$watch('reportData.showOnlyUnique', function(nv, ov) {
        //   scope.reportData.enteredUrls = filtering(scope.reportData.urls, nv);
        //   scope.updateNano();
        // });

        scope.$watch('reportData.enteredUrls', function(nv, ov) {
          scope.updateNano();
        });

        scope.addPostUrl = function(endpoint, collectionId) {
          if (!scope.reportData.name) {
            scope.setCurrentStep(0);
            return;
          }
          scope.setState('saving');

          $http({
            method: 'POST',
            url: scope.endpoint,
            data: {
              url: scope.reportData.urls,
              urls_to_remove: scope.reportData.enteredUrls.filter(function(item) { return item.removed; }).map(function(item) { return item.post_url; }),
              collection_id: scope.isReport() ? scope.reportData.selectedCollection.value : scope.collectionId,
              collection_name: scope.isReport() ? scope.reportData.newCollectionName : null,
              report_id: scope.reportId,
              is_report: scope.isReport() ? '1': '0',
              name: scope.reportData.name
            }
          }).success(function(response) {
              response = response || {};
              window.location.href = scope.onSuccessRedirectUrl + (response.report_id ? response.report_id : response.collection_id);
          }).error(function(data) {
              scope.setState('opened');
              data = data || {};
              scope.errorMessage = data.message || 'Error!';
              scope.displayMessage({message: scope.errorMessage});
          });
          
        };

        scope.namePlaceholder = function() {
          return scope.isReport() ? 'Name Your ROI-Prediction Report' : 'Name Your Post Analytics Collection';
        };

        scope.isReport = function() {
          return scope.reportName !== undefined;
        };

        scope.cancelChanged = function($event) {
          if (scope.isChanged()) {
            // scope.reset();
          } else {
            $event.stopPropagation();
            $event.preventDefault();
          }
        };

        // scope.$on('openAddPostAnalyticsUrlsPopup', function(their_scope, options) {
        scope.endpoint = iAttrs.endpoint;
        scope.collectionId = parseInt(iAttrs.collectionId);
        scope.reportId = parseInt(iAttrs.reportId);
        scope.collectionName = iAttrs.collectionName;
        scope.reportName = iAttrs.reportName
        scope.editNameUrl = iAttrs.editNameUrl;
        scope.getCollectionsUrl = iAttrs.getCollectionsUrl;
        scope.onSuccessRedirectUrl = iAttrs.onSuccessRedirectUrl;
        scope.reset();
        scope.setState('opened');

        if (scope.isReport() && !scope.reportId) {
          scope.setState('loading');
          $http({
            method: 'GET',
            url: scope.getCollectionsUrl || '',
          }).success(function(data) {
            scope.setState('opened');
            scope.reportData.collections = angular.copy(data);
          }).error(function() {
            scope.setState('opened');
            scope.errorMessage = 'Problem with loading post collections.';
            scope.displayMessage({message: scope.errorMessage});
          });
        }

        if (scope.reportId || scope.collectionId) {
          scope.setState('loading');
          $http({
            method: 'GET',
            url: '',
          }).success(function(data) {
            scope.reportData.enteredUrls = angular.copy(data);
            scope.reportData.enteredUrls.forEach(function(item) {
              item.removed = false;
            });
            scope.updateNano();
            scope.setState('opened');
          }).error(function() {
            scope.setState('opened');
            scope.errorMessage = 'Problem with loading entered urls.';
            scope.displayMessage({message: scope.errorMessage});
          })
        }

        window.onbeforeunload = function() {
          if (scope.isChanged() && scope.state !== 'loading') {
            return "Your changes have not been saved.";
          }
        };
      }

    };
}])

.directive('stripePopup', ['$http', 'context', 'tsConfig',
  function ($http, context, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/stripe_popup.html'),
      link: function (scope, iElement, iAttrs) {
        Stripe.setPublishableKey(iAttrs.key);
        scope.context = context;
        scope.amount = iAttrs.amount;
        scope.amountOriginal = iAttrs.amount;
        scope.payment_url = iAttrs.paymentUrl;
        scope.promo_url = iAttrs.promoUrl;
        scope.exp_month = {};
        scope.exp_year = {};
        scope.months = [];
        scope.years = [];
        for (var i = 1; i <= 12; ++i)
          scope.months.push({text: i.toString()});
        for (var i = 2014; i <= 2025; ++i)
          scope.years.push({text: i.toString()});
        scope.types = [
          {
            text: "Visa",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "MasterCard",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "AmEx",
            mask: "9999 999999 99999",
            cvcmask: "9999"
          },{
            text: "JCB",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "Discover",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "Diners Club",
            mask: "9999 9999 9999 99",
            cvcmask: "999"
          }
        ];

        scope.updateType = function(selected) {
          if (selected !== undefined)
            scope.cctype = selected;
          scope.ccmask = scope.cctype.mask;
          scope.cvcmask = scope.cctype.cvcmask;
        };
        scope.cctype = angular.copy(scope.types[0]);
        scope.updateType();

        // scope.updateExpDate = function (selected) {
        //   scope.stripedata.exp_month = scope.exp_month.text;
        //   scope.stripedata.exp_year = scope.exp_year.text;
        // };

        scope.updateExpMonth = function(selected) {
          if (selected)
            scope.exp_month = selected;
          scope.stripedata.exp_month = selected.text;
        };

        scope.updateExpYear = function(selected) {
          if (selected)
            scope.exp_year = selected;
          scope.stripedata.exp_year = selected.text;
        };  

        var stripe_validator = function () {
          if (scope.stripedata === undefined) return;
          if (scope.stripedata.number !== undefined) {
            scope.card_type = Stripe.card.cardType(scope.stripedata.number);
            scope.card_valid = Stripe.card.validateCardNumber(scope.stripedata.number);
            if(scope.card_type !== scope.cctype.text) scope.card_valid = false;
          }
          if (scope.stripedata.exp_month !== undefined && scope.stripedata.exp_year !== undefined) {
            scope.exp_valid = Stripe.card.validateExpiry(scope.stripedata.exp_month, scope.stripedata.exp_year);
          }
          if (scope.stripedata.cvc !== undefined) {
            scope.cvc_valid = Stripe.card.validateCVC(scope.stripedata.cvc);
          }
        };
        scope.$watch('stripedata', stripe_validator, true);

        var responseHandler = function (status, response) {
          scope.$apply(function () {
            if (response.error) {
              scope.error = response.error.message;
              scope.setState('error');
            } else {
              scope.error = "";
              var token = response.id;
              if (Intercom) {
                Intercom('trackEvent', 'brand-clicked-subscribe', {plan_name: scope.plan});
              }

              $http.post(scope.payment_url, {
                stripeToken: token,
                promotionCode: scope.paymentdata.promotionCode,
                plan: scope.plan,
                amount: scope.amount,
                one_time: scope.one_time ? '1': '0',
              })
                .success(function (data) {
                  if (iAttrs.saveUrl) {
                    $http.post(iAttrs.saveUrl, {
                      stripeToken: token,
                    }).success(function () {
                      scope.setState('success');
                      window.location.assign(data.next);
                    }).error(function (a, b, c, d) {
                      scope.error = a.error;
                      scope.setState('error');
                    });
                  } else {
                    scope.setState('success');
                    window.location.assign(data.next);
                  }
                })
                .error(function (a, b, c, d) {
                  scope.error = a.error;
                  scope.setState('error');
                });
            }
          })
        };

        scope.getToken = function () {
          scope.setState('processing');
          Stripe.card.createToken(scope.stripedata, responseHandler);
        };

        scope.redeem = function(){
          scope.setState('redeeming');
          $http.post(scope.promo_url, {
            promotionCode: scope.paymentdata.tmpPromotionCode
          })
            .success(function (data) {
              var percent_off=0, amount_off=0;
              if(data.percent_off){
                 percent_off = Number(data.percent_off)/100.0;
              }
              if(data.amount_off){
                amount_off = Number(data.amount_off)/100.0;
              }
              scope.amount = Number(scope.amountOriginal)*(1-percent_off) - amount_off;
              scope.setState('opened');
              scope.paymentdata.promotionCode = scope.paymentdata.tmpPromotionCode;
            })
            .error(function (a, b, c, d) {
              scope.error = a;
              scope.paymentdata.promotionCode = null;
              scope.setState('error');
            });

        }

        scope.$on('openStripePopup', function (their_scope, plan, is_subscribed, disable_close, amount, plan_type, plan_period, plan_interval_count, one_time) {
          scope.amount = amount;
          scope.amountOriginal = amount;
          scope.package = plan_type;
          scope.one_time = one_time;
          scope.plan = plan;
          scope.plan_interval_count = plan_interval_count;
          scope.plan_period = plan_period + (plan_interval_count > 1 ? 's': '');
          scope.stripedata = {};
          scope.paymentdata = {};
          scope.exp_month = {};
          scope.exp_year = {};
          scope.open();
          if(disable_close == true){
            scope.no_close = true;
          }

          if(is_subscribed){
            scope.setState('plan_change');
            if (Intercom) {
              Intercom('trackEvent', 'brand-clicked-subscribe', {plan_name: scope.plan});
            }
            $http.post(scope.payment_url, {
              plan: scope.plan,
              stripeToken: true,

            })
              .success(function (data) {
                scope.setState('success');
                window.location.assign(data.next);
              })
              .error(function (a, b, c, d) {
                scope.error = a.error;
                scope.setState('error');
              });
          }
        });
      }
    };
  }
])

.directive('imageUploadPopup', ['$resource', '$compile', '$q', '$http', '$rootScope', 'tsConfig',
  function ($resource, $compile, $q, $http, $rootScope, tsConfig) {

    return {
      restrict: 'A',
      scope: {
        'url': '@',
        'aspect': '@',
        'uploadData': '=',
      },
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/image_upload_popup.html'),
      link: function (scope, iElement, iAttrs) {
        var orig_width = 0,
          orig_height = 0;
        var scale = 1;
        var x, y, w, h;
        var crop_instance = null;
        var file = null;
        var scroll_top;
        scope.upload_blocked = true;
        scope.img_container = null;
        scope.crop_container = null;

        scope.open_cb = function () {
          scroll_top = $("body").scrollTop();
          $('html, body')
            .animate({ scrollTop: 0 })
          scope.img_container = iElement.find(".input_image");
          scope.crop_container = iElement.find(".profile_image");
          scope.img_container.attr("src", "");
          scope.crop_container.attr("src", "");
          scope.img_container.unbind('change');
          scope.img_container.bind('change', function () {
            scope.$apply(function () {
              if (scope.img_container[0].files && scope.img_container[0].files[0] && /image\/*/.test(scope.img_container[0].files[0].type)) {
                file = scope.img_container[0].files[0];
                var FR = new FileReader();
                FR.onload = function (e) {
                  FR.onload = function(){};
                  scope.crop_container.attr("src", e.target.result);
                  scope.$apply(function () {
                    scope.state = "crop";
                  });
                  //dom settlement
                  setTimeout(function () {
                    var img_width = scope.crop_container.width();
                    var img_height = scope.crop_container.height();
                    orig_width = img_width;
                    var mw = Math.min(img_width, img_height);
                    crop_instance = null;
                    update_scale();
                    var x1 = (img_width - mw) / 2;
                    var y1 = (img_height - mw) / 2;
                    var aspect = Number(scope.aspect.split(':')[0]) / Number(scope.aspect.split(':')[1])
                    var r_x1 = scope.crop_container.width()*(0.5 - 0.4);
                    var r_y1 = Math.max(0, scope.crop_container.height()*0.5 - scope.crop_container.width()*0.4/aspect);
                    var r_x2 = scope.crop_container.width()*(0.5 + 0.4);
                    var r_y2 = Math.min(scope.crop_container.height(), scope.crop_container.height()*0.5 + scope.crop_container.width()*0.4/aspect);
                    crop_instance = scope.crop_container.imgAreaSelect({
                      onSelectChange: crop_change,
                      handles: true,
                      minHeight: 32,
                      minWidth: 32,
                      persistent: true,
                      aspectRatio: scope.aspect,
                      x1: r_x1,
                      y1: r_y1,
                      x2: r_x2,
                      y2: r_y2,
                      instance: true
                    });
                    crop_change(null, {
                      x1: r_x1,
                      y1: r_y1,
                      width: r_x2-r_x1,
                      height: r_y2-r_y1,
                    });
                  }, 500);
                };
                FR.readAsDataURL(scope.img_container[0].files[0]);
              } else {
                scope.state = "error";
              }
            });
          });
        };

        scope.close_cb = function(){
          if (crop_instance) {
            crop_instance.remove();
          };
          iElement.remove();
          $("body").scrollTop(scroll_top);
        };

        scope.upload = function () {
          scope.state = "uploading";
          var fd = new FormData();
          fd.append('csrfmiddlewaretoken', window.csrftoken());
          if (scope.uploadData) {
            fd.append('campaign_id', scope.uploadData.campaign_id);
          }
          fd.append('image_file', file);
          fd.append('x1', x);
          fd.append('y1', y);
          fd.append('x2', x + w || 1);
          fd.append('y2', y + h || 1);
          fd.append('scaling_factor', 1);
          if (crop_instance) {
            crop_instance.remove();
          };
          $http.post(scope.url, fd, {
            transformRequest: angular.identity,
            headers: {
              'Content-Type': undefined
            }
          })
            .success(function (url) {
              scope.state = "success";
              if(iAttrs.successBc !== undefined){
                $rootScope.$broadcast(iAttrs.successBc, url);
              }
              if(iAttrs.noReload !== undefined){
                scope.close();
              }else{
                window.location.reload();
              }
            })
            .error(function (a, b, c, d) {
              scope.state = "error";
            });
        };


        var crop_change = function (img, selection) {
          scope.$apply(function () {
            x = Math.round(selection.x1 * scale);
            y = Math.round(selection.y1 * scale);
            w = Math.round(selection.width * scale);
            h = Math.round(selection.height * scale);
            if (isNaN(x) || isNaN(y) || isNaN(w) || isNaN(h) || w < 1 || h < 1) {
              scope.upload_blocked = true;
            } else {
              scope.upload_blocked = false;
            }
          });
        };

        var update_scale = function () {
          if (orig_width == 0) {
            orig_width = scope.crop_container.width();
          }
          if (orig_height == 0) {
            orig_height = scope.crop_container.height();
          }
          var screen_width = $(window).width()*0.8;
          var screen_height = $(window).height()*0.6;
          var hor_scale = 1;
          var ver_scale = 1;
          if (orig_width > screen_width) {
            hor_scale = orig_width / screen_width;
          }
          if (orig_height > screen_height) {
            ver_scale = orig_height / screen_height;
          }
          scale = Math.max(hor_scale, ver_scale);
          var new_width = (orig_width / scale);
          if (new_width === 0) {
            setTimeout(update_scale, 500);
          } else {
            scope.crop_container.attr('width', new_width + "px");
            if (crop_instance) {
              crop_change(true, crop_instance.getSelection());
            }
          }

        };

        scope.select_img = function () {
          scope.img_container.click();
        };

        $(window).resize(update_scale);
      }
    };
  }
])

.directive('learnMoreBloggersPopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/learn_more_bloggers_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.$on('openLearnMoreBloggers', function (their_scope) {
          scope.open();
        });
      }
    };
  }
])


.directive('loginPopup', ['$http', '$sce', '$rootScope', 'singletonRegister', '$timeout', '$interval', 'popup_auto_open', '$location', 'tsConfig',
  function ($http, $sce, $rootScope, singletonRegister, $timeout, $interval, popup_auto_open, $location, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/login_popup.html'),
      link: function (scope, iElement, iAttrs) {
        var getParameterByName = function(name) {
            name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
            var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
                results = regex.exec(location.search);
            return results == null ? null : decodeURIComponent(results[1].replace(/\+/g, " "));
        }

        if(singletonRegister.getOrRegister("loginPopup")){
          iElement.remove();
          return;
        }
        scope.emailPattern = /[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,4}/i;

        scope.$on('openLoginPopup', function (their_scope) {
          scope.no_close_outside = true;
          scope.error = "";
          scope.message="Submit!";
          scope.open();
        });

        if (popup_auto_open.login_popup) {
          $timeout(function() {
            scope.$broadcast('openLoginPopup');
          }, 1000);

          $timeout(function() {
            scope.close = function() {
              window.location.href = "http://www.theshelf.com/";
            };
          }, 500);
        }

        scope.login = function(){
          scope.message="Wait";
          scope.error = "";
          var email = iElement.find("#login_form_id_1").val();
          var password = iElement.find("#login_form_id_2").val();
          var st = $http({
              method: 'POST',
              url: iAttrs.loginUrl,
              data: $.param({email: email, password: password}),
              headers: {'Content-Type': 'application/x-www-form-urlencoded'}
          }).success(function(data){
            scope.message="Success";
            var next = getParameterByName("next");
            if(next !== null){
              window.location.assign(next);
            }else{
              window.location.assign(data.url);
            }
          }).error(function(a, b, c, d){
            if(b == 403){
              scope.error = $sce.trustAsHtml(Object.get_innermost(a).join(", "));
            }else if(b == 400){
              scope.error = "Cross site request forgery validation failed. Please refresh the page and try again.";
            }
            scope.message="Try again";
          });
        };

        // setInterval(function(){
        //   scope.$apply(function(){
        //     scope.lf1 = $("#login_form_id_1").val();
        //     scope.lf2 = $("#login_form_id_2").val();
        //   });
        // }, 100);

      }
    };
  }
])


.directive('signupPopup', ['$http', '$sce', '$rootScope', '$timeout', 'singletonRegister', 'popup_auto_open', 'tsConfig',
  function ($http, $sce, $rootScope, $timeout, singletonRegister, popup_auto_open, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/signup_popup.html'),
      link: function (scope, iElement, iAttrs) {
        if(singletonRegister.getOrRegister("signupPopup")){
          iElement.remove();
          return;
        }

        if (popup_auto_open.brand_signup_popup || popup_auto_open.blogger_signup_popup) {
          $timeout(function() {
            scope.$broadcast('openSignupPopup', {"initial_type": popup_auto_open.brand_signup_popup ? "brand": (popup_auto_open.influenity_signup_popup ? "influenity" : "blogger")});
          }, 1000);

          $timeout(function() {
            scope.close_cb = function() {
              if (history.length > 1) {
                history.go(-1);
              } else {
                window.location.href = "http://www.theshelf.com/";
              }
            };
          }, 500);
        }

        scope.$on('openSignupPopup', function (their_scope, args) {
          scope.no_close_outside = true;
          scope.error = "";
          scope.message="Submit!";
          scope.agree = true;
          scope.sendData = {
            phone: '',
          };
          $timeout(function() {
            scope.open();
            if(args !== undefined){
              if(args.initial_type !== undefined){
                scope.setState(args.initial_type);
              }
              if(args.buy_after !== undefined){
                scope.buy_after = true;
              }
            }
          }, 500);
        });
        scope.$on('openRequestDemo', function (their_scope) {
          scope.error = "";
          scope.message="Submit!";
          scope.agree = true;
          $timeout(function() {
            scope.open();
            scope.setState("brand");
          }, 500);
        });
        scope.requestDemo = function(){
          // scope.close();
          $rootScope.$broadcast("openRequestDemo");
        };
        scope.login = function(){
          // scope.close();
          $rootScope.$broadcast("openLoginPopup");
        };
        scope.signup_blogger = function(){
          scope.message="Wait";
          scope.error = "";
          var name = $("#blogger_signup_id_1").val();
          var email = $("#blogger_signup_id_2").val();
          var password = $("#blogger_signup_id_3").val();
          var blog_name = $("#blogger_signup_id_4").val();
          var blog_url = $("#blogger_signup_id_5").val();
          $http({
              method: 'POST',
              url: iAttrs.signupBloggerUrl,
              data: $.param({
                name: name,
                email: email,
                password: password,
                blog_name: blog_name,
                blog_url: blog_url,
                referer: popup_auto_open.referer,
                influenity_signup: popup_auto_open.influenity_signup_popup ? '1' : null,
              }),
              headers: {'Content-Type': 'application/x-www-form-urlencoded'}
          }).success(function(data){
            scope.message="Success";
            window.location.assign(data.url);
            window._kmq.push(['identify', email]);
            window._kmq.push(['set', {'is_brand': false}]);
            window._kmq.push(['record', 'Blogger Sign Up Form Submitted', {'name': name, 'email': email}]);
          }).error(function(a, b, c, d){
            scope.error = $sce.trustAsHtml(Object.get_innermost(a).join(" "));
            scope.login_state = "error";
            scope.message="Try again";
          });
        };
        scope.signup_brand = function(){
          scope.message="Wait";
          scope.error = "";
          var first_name = $("#brand_signup_id_1").val();
          var last_name = $("#brand_signup_id_2").val();
          var email = $("#brand_signup_id_3").val();
          var password = $("#brand_signup_id_4").val();
          var brand_name = $("#brand_signup_id_5").val();
          var brand_url = $("#brand_signup_id_6").val();
          var fromAdmin = iAttrs.fromAdmin !== undefined;
          $http({
              method: 'POST',
              url: iAttrs.signupBrandUrl,
              data: $.param({
                first_name: first_name,
                last_name: last_name,
                email: email,
                password: password,
                brand_name: brand_name,
                brand_url: brand_url,
                buy_after: scope.buy_after,
                phone_number: '+' + scope.sendData.phone,
                from_admin: fromAdmin,
                referer: popup_auto_open.referer,
              }),
              headers: {'Content-Type': 'application/x-www-form-urlencoded'}
          }).success(function(data){
            scope.message="Success";
            window.location.assign(data.url);
            window._kmq.push(['identify', email]);
            window._kmq.push(['set', {'is_brand': true}]);
            window._kmq.push(['record', 'Brand Sign Up Form Submitted', {'name': first_name + last_name, 'email': email}]);
          }).error(function(a, b, c, d){
            scope.error = $sce.trustAsHtml(Object.get_innermost(a).join(" "));
            scope.login_state = "error";
            scope.message="Try again";
          });
        };
      }
    };
  }
])


.directive('blogBadgePopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/code_for_badge_popup.html'),
      link: function (scope, iElement, iAttrs) {

        scope.regen_badge_code = function(){
          //concating array into one string
          scope.badge_code = [
            '<!-- THE SHELF NETWORK -->',
            '<a style="width:100%; max-width:200px; overflow:hidden;"  href="http://www.theshelf.com/shelfnetwork/bloggers/?badge_name=',
            scope.badge_name,
            '&utm_medium=blogger-badges&utm_source=blogger-badge&utm_content=badge-', scope.badge_name, '&utm_campaign=',scope.blog_url_stripped,'">',
            '<img style="width:100%; max-width:200px;"  src="https://s3.amazonaws.com/theshelfnetwork/badges/',
            scope.badge_name,
            '.jpg" /></a>'
          ].join("");
        };

        scope.trigger_badge_verify = function(){
          var url = iAttrs.badgeVerifyUrl;
          scope.setState('verify');
          $http.get(url).success(function(data){
            scope.setState('success');
          }).error(function(){
            scope.setState('error');
          })
        };

        scope.$on('openBlogBadgePopup', function (their_scope, args) {
          scope.badge_name = args.badge_name;
          scope.blog_url_stripped = args.blog_url_stripped;
          scope.regen_badge_code();
          scope.open();
          setTimeout(function() {
            iElement.find('.badge_code').click(function(){$(this).select()});
          }, 10);
        });
      }
    };
  }
])

.directive('bloggerTrackingLinkPopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/code_for_badge_popup.html'),
      link: function (scope, iElement, iAttrs) {

        scope.trigger_badge_verify = function(){
          var url = iAttrs.badgeVerifyUrl;
          scope.setState('verify');
          $http.get(url).success(function(data){
            scope.setState('success');
          }).error(function(){
            scope.setState('error');
          })
        };

        scope.$on('openBloggerTrackingLinkPopup', function (their_scope, args) {
          scope.trackingLink = args.trackingLink;
          scope.trackingPixelSnippet = args.trackingPixelSnippet;
          scope.open();
        });
      }
    };
  }
])

.directive('brandMembershipPopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/brand_membership_verification.html'),
      link: function (scope, iElement, iAttrs) {
        scope.$on('openBrandMembershipPopup', function (their_scope, args) {
          scope.open();
          var url = iAttrs.verifyUrl;
          scope.setState('verify');
          $http.get(url).success(function(data){
            if(data == 'verified'){
              scope.setState('verified');
              window.location.assign('/');
            }else{
              scope.setState('success');
            }
          }).error(function(){
            scope.setState('error');
          })
        });
      }
    };
  }
])

.directive('loginRequiredPopup', ['$http', '$rootScope', 'tsConfig',
  function ($http, $rootScope, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/login_required_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.$on('openLoginRequiredPopup', function (their_scope, args) {
          scope.open();
        });
        scope.signupPopup = function(type){
          $rootScope.$broadcast("openSignupPopup", {"initial_type": type});
          scope.close();
        };
        scope.loginPopup = function(type){
          $rootScope.$broadcast("openLoginPopup");
          scope.close();
        };
      }
    };
  }
])

.directive('editProfilePopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/edit_profile_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.$on('openEditProfilePopup', function (their_scope, data) {
          scope.open();
          scope.save(data);
          scope.setNoClose(true);
        });
        scope.save = function(data){
          scope.setState("saving");
          $http({
              url: iAttrs.saveUrl,
              method: 'POST',
              data: data
          }).success(function(){
            scope.setState("saved");
            window.location.assign(iAttrs.successUrl);
          }).error(function(){
            scope.setState("error");
            scope.setNoClose(false);
          });
        };
      }
    };
  }
])



.directive('inviteToReportPopup', ['$http', 'context', 'tsCampaignReportInvitation', 'tsConfig', function ($http, context, tsCampaignReportInvitation, tsConfig) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/invite_to_report_popup.html'),
    link: function (scope, iElement, iAttrs) {
      scope.context = context;

      scope.messageData = {};

      scope.reset = function() {
        angular.extend(scope.messageData, {
          name: null,
          email: null,
          campaignName: scope.campaignName,
          publicLink: scope.clientLink,
        });
        angular.extend(scope.messageData, {
          subject: tsCampaignReportInvitation.getSubjectTemplate(null, scope),
          message: tsCampaignReportInvitation.getBodyTemplate(null, scope),
        });
      };

      scope.inviteClient = function () {
        scope.setState('loading');
        scope.name = scope.messageData.name;
        $http({
          method: 'POST',
          url: '?send_invitation_to_public_report=1',
          data: {
            body: tsCampaignReportInvitation.getBody(scope.messageData.message, scope),
            subject: tsCampaignReportInvitation.getSubject(scope.messageData.subject, scope),
            clientLink: scope.clientLink,
            toEmail: scope.messageData.email,
            toName: scope.messageData.name,
          }
        }).success(function() {
          scope.setState('invited');
        }).error(function() {
          scope.setState('error');
        });
      };

      scope.$on('openInviteToReportPopup', function(their_scope, options) {
        scope.clientLink = options.clientLink;
        scope.campaignName = options.campaignName;
        scope.reset();
        scope.open();
      });

    }
  };
}])



.directive('bloggerApprovalPopup', ['$http', '$rootScope', 'context', 'tsSendApprovalMessage',
    'tsCampaignReportInvitation', 'tsConfig', 'Restangular',
    function($http, $rootScope, context, tsSendApprovalMessage, tsCampaignReportInvitation,
      tsConfig, Restangular) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/blogger_approval_popup.html'),
    controller: function() {},
    controllerAs: 'bloggerApprovalPopupCtrl',
    link: function(scope, iElement, iAttrs, ctrl) {

      scope.context = context;
      scope.clientApprovalInviteUrl = iAttrs.clientApprovalInviteUrl;
      scope.approvalStatusChangeUrl = iAttrs.approvalStatusChangeUrl;

      scope.messageData = {};

      scope.reset = function() {
        angular.extend(scope.messageData, {
          name: null,
          email: null,
          campaignName: scope.campaignName,
          publicLink: scope.clientLink,
        });
        angular.extend(scope.messageData, {
          subject: tsSendApprovalMessage.getSubjectTemplate(null, scope),
          message: tsSendApprovalMessage.getBodyTemplate(null, scope),
        });
      };


      scope.changeStatus = function(status) {
        scope.setState('loading');
        $http({
          method: 'POST',
          url: scope.approvalStatusChangeUrl,
          data: {
            status: status
          }
        }).success(function() {
          window.location.reload();
        }).error(function() {
          scope.setState('error');
        });
      };

      scope.saveTmp = function() {
        scope.close();
        return;
        scope.setState('loading');
        $http({
          method: 'POST',
          url: '/approve_report_update/',
          data: {
            'approve_status': scope.approvesData.values,
            'notes': scope.approvesData.notes,
            'brand_id': scope.brandId,
          }
        }).success(function() {
          scope.close();
        }).error(function() {
          scope.setState('error');
        });
      };

      scope.approve = function() {
        scope.setState('loading');
        scope.setBackgroundType('black');

        Restangular
          .one('campaigns', ctrl.openOptions.campaignId)
          .post('submit_public_approval_report', {
            'brand_id': scope.brandId,
            'report_id': scope.reportId,
            'user_id': scope.userId,
          })
          .then(function(response) {
            scope.setState('approved');
            scope.setBackgroundType(null);
            $rootScope.$broadcast('approval:sent');
            scope.close_cb = function() {
              scope.visible = true;
              scope.no_close = true;
              scope.setState('loading');
              scope.setBackgroundType('black');
              window.location.href = response.redirectUrl;
            };
          }, function() {
            scope.setState('error');
          });


        // $http({
        //   method: 'POST',
        //   url: '/approve_report_update/',
        //   data: {
        //     'approve_status': scope.approvesData.values,
        //     'notes': scope.approvesData.notes,
        //     'brand_id': scope.brandId,
        //   }
        // }).success(function() {
        //   $http({
        //     method: 'POST',
        //     url: '/public_approval_report_submit/',
        //     data: {
        //       'brand_id': scope.brandId,
        //       'report_id': scope.reportId,
        //       'user_id': scope.userId,
        //     }
        //   }).success(function(response) {
        //       scope.setState('approved');
        //       window.location.reload();
        //   }).error(function() {
        //     scope.setState('error');
        //   });
        // }).error(function() {
        //   scope.setState('error');
        // });
      };

      scope.inviteToReport = function () {
        scope.setState('loading');
        $http({
          method: 'POST',
          url: '',
          data: {
            body: tsCampaignReportInvitation.getBody(scope.messageData.message, scope),
            subject: tsCampaignReportInvitation.getSubject(scope.messageData.subject, scope),
            clientLink: scope.publicReportLink,
            toEmail: scope.messageData.email,
            toName: scope.messageData.name,
          }
        }).success(function() {
          scope.setState('invited');
        }).error(function() {
          scope.setState('error');
        });
      };

      scope.inviteClient = function() {
        scope.setState('loading');
        scope.setBackgroundType('black');
        $http({
          method: 'POST',
          url: scope.clientApprovalInviteUrl,
          data: {
            body: tsSendApprovalMessage.getBody(scope.messageData.message, scope),
            subject: tsSendApprovalMessage.getSubject(scope.messageData.subject, scope),
            clientLink: scope.clientLink,
            toEmail: scope.messageData.email,
            toName: scope.messageData.name,
          }
        }).success(function() {
          scope.setState('invited');
          scope.setBackgroundType(null);
        }).error(function() {
          scope.setState('error');
          scope.setBackgroundType(null);
        });
      };

      scope.$on('openBloggerApprovalPopup', function(their_scope, options) {
        scope.setBackgroundType(null);
        ctrl.openOptions = options;
        scope.clientLink = options.clientLink;
        scope.campaignName = options.campaignName;
        scope.reset();
        scope.approvalStatus = options.status;
        if (options && options.approve) {
          scope.brandId = options.brandId;
          scope.reportId = options.reportId;
          scope.userId = options.userId;
          scope.userFirstName = options.userFirstName;
          scope.open();

          scope.setState('loading');
          scope.setBackgroundType('black');
          Restangular
            .one('campaigns', options.campaignId)
            .customGET('approval_report_selection_counts')
            .then(function(response) {
              scope.setBackgroundType(null);
              scope.countStats = response;
              scope.setState('approve');
            });
        } else if (options && options.moreEdits) {
          scope.open();
          scope.setState('moreEdits');
        } else {
          scope.open();
        }
      });

    }
  };
}])

.directive('displayMessagePopup', ['tsConfig', function(tsConfig) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/display_message_popup.html'),
    link: function(scope, iElement, iAttrs) {
      scope.message = iAttrs.message;
      scope.loading = false;

      scope.$on('displayMessage', function(their_scope, args) {
        scope.open();
        if (args !== undefined && args !== null) {
          if (args.loading) {
            scope.setState('loading');
          }
          if (args.message !== undefined) {
            scope.message = args.message;
          }
          if (args.instructionText !== undefined) {
            scope.instructionText = args.instructionText;
          }
          if (args.noClose === true) {
            scope.setNoClose();
          }
          if (args.closeCb !== undefined) {
            scope.close_cb = args.closeCb;
          }
        }
      });

      scope.$on('closeMessage', function(their_scope, args) {
        if (scope.close) {
          scope.close();
        }
      });
      
    }
  }
}])

.directive('featureLockedPopup', ['$http', 'singletonRegister', 'tsConfig',
  function ($http, singletonRegister, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/feature_locked_popup.html'),
      link: function (scope, iElement, iAttrs) {
        if (singletonRegister.getOrRegister('featureLockedPopup')) {
          iElement.remove();
          return;
        }
        scope.link = iAttrs.link;
        scope.plan_name = iAttrs.planName;
        scope.link_title = iAttrs.linkTitle;
        scope.$on('featureLocked', function (their_scope, args) {
          if(args){
            scope.message = args.message;
          }
          scope.open();
        });
        scope.signupPopup = function(type){
          $rootScope.$broadcast("openSignupPopup", {"initial_type": type});
          scope.close();
        };
      }
    };
  }
])

.directive('emailBloggersPopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      scope: {
        'selectedBloggers': '='
      },
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/email_bloggers_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.markers = "{{name}} and {{blogname}}";
        scope.email = iAttrs.defaultEmail;
        scope.template = "";
        scope.$on('openEmailBloggersPopup', function (their_scope, args) {
          scope.influencer_ids = [];
          for(var i in scope.selectedBloggers){
            if(scope.selectedBloggers[i]){
              scope.influencer_ids.push(i);
            }
          }
          if(scope.influencer_ids.length>0){
            scope.open();
          }
        });
        scope.send = function(subject, template){
          scope.setState("sending");
          $http({
            url: iAttrs.url,
            method: "POST",
            data: {
              from_email: scope.email,
              template: template,
              subject: subject,
              influencer_ids: scope.influencer_ids,
            }
          }).success(function(){
            scope.setState("done");
          }).error(function(){
            scope.setState("error");
          });
        };
      }
    };
  }
])

.directive('exportPaidPopup', ['$http', 'exportCosts', 'tsConfig',
  function ($http, exportCosts, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/export_paid_popup.html'),
      link: function (scope, iElement, iAttrs) {
        Stripe.setPublishableKey(iAttrs.key);
        scope.amount = iAttrs.amount;
        scope.amountOriginal = iAttrs.amount;
        scope.payment_url = iAttrs.paymentUrl;
        scope.promo_url = iAttrs.promoUrl;
        scope.exp_month = {};
        scope.exp_year = {};
        scope.months = [];
        scope.years = [];
        for (var i = 1; i <= 12; ++i)
          scope.months.push({text: i.toString()});
        for (var i = 2014; i <= 2025; ++i)
          scope.years.push({text: i.toString()});
        scope.types = [
          {
            text: "Visa",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "MasterCard",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "AmEx",
            mask: "9999 999999 99999",
            cvcmask: "9999"
          },{
            text: "JCB",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "Discover",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "Diners Club",
            mask: "9999 9999 9999 99",
            cvcmask: "999"
          }
        ];

        scope.updateType = function(selected){
          if (selected !== undefined)
            scope.cctype = selected;
          scope.ccmask = scope.cctype.mask;
          scope.cvcmask = scope.cctype.cvcmask;
        };

        scope.cctype = angular.copy(scope.types[0]);
        scope.updateType();

        // scope.updateExpDate = function () {
        //   scope.stripedata.exp_month = scope.exp_month.text;
        //   scope.stripedata.exp_year = scope.exp_year.text;
        // };

        scope.updateExpMonth = function(selected) {
          if (selected)
            scope.exp_month = selected;
          scope.stripedata.exp_month = selected.text;
        };

        scope.updateExpYear = function(selected) {
          if (selected)
            scope.exp_year = selected;
          scope.stripedata.exp_year = selected.text;
        };        

        scope.toggleAgree = function(){
          scope.agreed = !scope.agreed;
        };
        var stripe_validator = function () {
          if (scope.stripedata === undefined) return;
          if (scope.stripedata.number !== undefined) {
            scope.card_type = Stripe.card.cardType(scope.stripedata.number);
            scope.card_valid = Stripe.card.validateCardNumber(scope.stripedata.number);
            if(scope.card_type !== scope.cctype.text) scope.card_valid = false;
          }
          if (scope.stripedata.exp_month !== undefined && scope.stripedata.exp_year !== undefined) {
            scope.exp_valid = Stripe.card.validateExpiry(scope.stripedata.exp_month, scope.stripedata.exp_year);
          }
          if (scope.stripedata.cvc !== undefined) {
            scope.cvc_valid = Stripe.card.validateCVC(scope.stripedata.cvc);
          }
        };
        scope.$watch('stripedata', stripe_validator, true);

        var responseHandler = function (status, response) {
          scope.$apply(function () {
            if (response.error) {
              scope.error = response.error.message;
              scope.setState('error');
            } else {
              scope.error = "";
              var token = response.id;
              $http.post(scope.payment_url, {
                stripeToken: token,
                promotionCode: scope.paymentdata.promotionCode,
                export_type: scope.plan,
                email: scope.paymentdata.email,
                amount: scope.amount,
              })
                .success(function (data) {
                  scope.setState('success');
                  window.location.assign(data.next);
                })
                .error(function (a, b, c, d) {
                  scope.error = a.error;
                  scope.setState('error');
                });
            }
          });
        };

        scope.getToken = function () {
          scope.setState('processing');
          Stripe.card.createToken(scope.stripedata, responseHandler);
        };

        scope.redeem = function(){
          scope.setState('redeeming');
          $http.post(scope.promo_url, {
            promotionCode: scope.paymentdata.tmpPromotionCode
          })
            .success(function (data) {
              var percent_off=0, amount_off=0;
              if(data.percent_off){
                 percent_off = Number(data.percent_off)/100.0;
              }
              if(amount_off){
                amount_off = Number(data.amount_off)/100.0;
              }
              scope.amount = Number(scope.amountOriginal)*(1-percent_off) - amount_off;
              scope.setState('opened');
              scope.paymentdata.promotionCode = scope.paymentdata.tmpPromotionCode;
            })
            .error(function (a, b, c, d) {
              scope.error = a;
              scope.paymentdata.promotionCode = null;
              scope.setState('error');
            });
        };

        scope.$on('openExportPaidPopup', function (their_scope, args) {
          var plan = args.export_type;
          scope.plan = plan;
          if (plan == 'custom') {
            scope.amount = angular.copy(args.price);
            scope.amountOriginal = angular.copy(args.price);
            scope.package = "Custom list";
          } else {
            scope.amount = scope.amountOriginal = exportCosts[plan].price;
            scope.package = exportCosts[plan].title;
          }
          scope.stripedata = {};
          scope.paymentdata = {};
          scope.exp_month = {};
          scope.exp_year = {};
          scope.agreed = false;
          scope.open();
        });
      }
    }; 
  }
])


.directive('addNewUserPopup', ['$http', '$sce', 'tsConfig', function($http, $sce, tsConfig) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/add_new_user_popup.html'),
    link: function(scope, iElement, iAttrs) {
      scope.target = iAttrs.target;
      scope.source = iAttrs.source;
      scope.$on('openAddNewUserPopup', function(their_scope) {
        scope.loaded = false;
        scope.open();
        scope.error = null;
        scope.data = {};
        $http.get(scope.source)
          .success(function(data) {
            scope.loaded = true;
          });
      });
      scope.confirm = function(yes) {
        if (yes) {
          scope.setState('opened');
          scope.submit(scope.data);
        } else {
          scope.setState('opened');
        }
      };
      scope.submit = function(data) {
        scope.loaded = false;
        $http({
          method: 'POST',
          url: iAttrs.target,
          data: $.param(data),
          headers: {'Content-Type': 'application/x-www-form-urlencoded'}
        }).success(function() {
          scope.loaded = true;
          scope.setState('success');
          window.location.reload();
        }).error(function(data) {
          var keys = Object.keys(data.errors);
          var errors = [];
          for(var i = 0; i< keys.length; i++){
            for(var j = 0; j<data.errors[keys[i]].length; j++){
              errors.push(keys[i]+": "+data.errors[keys[i]][j]);
            }
          }
          scope.error = $sce.trustAsHtml(errors.join("<br/>"));
          scope.loaded = true;
        })
      };
    }
  };
}])


.directive('addCompetitorPopup', ['$http', 'tsConfig',
  function ($http, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/add_competitor_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.matchBrand = iAttrs.matchBrandUrl;
        scope.$on('openAddCompetitorPopup', function (their_scope, args) {
          scope.open();
        });
        scope.$on("brandSelected", function(their_scope, brand){
          if(brand){
            scope.brand_url = brand.url;
          }
        });
        scope.save = function(){
          scope.setState('saving');
          $http({
            method: 'post',
            data: {competitor: scope.brand_url},
            url: iAttrs.saveUrl,
          }).success(function(){
            scope.setState('saved');
            window.location.reload();
          }).error(function(){
            scope.setState('error');
          });
        }
      }
    };
  }
])


.directive('saveSearchPopup', ['$rootScope', '$http', 'tsQueryCache', 'tsQueryResult', 'tsConfig',
  function($rootScope, $http, tsQueryCache, tsQueryResult, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/save_search_popup.html'),
      link: function(scope, iElement, iAttrs) {
        scope.$on('openSaveSearchPopup', function(their_scope, data) {
          scope.setBackgroundType(null);
          scope.data = {
            viewName: data && data.text ? data.text : '',
            queryId: data && data.value ? data.value : null
          };
          scope.open();
          if (data) {
            scope.save();
          }
        });
        scope.save = function() {
          scope.setState('saving');
          scope.setBackgroundType('black');
          $http({
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            transformRequest: function(obj) {
              var str = [];
              for (var p in obj)
                str.push(encodeURIComponent(p) + "=" + encodeURIComponent(obj[p]));
              return str.join("&");
            },
            data: {
              name: scope.data.viewName,
              query: angular.toJson(tsQueryCache.get()),
              result: angular.toJson(tsQueryResult.get()),
              query_id: scope.data.queryId
            },
            url: iAttrs.saveUrl
          }).success(function(response) {
            $rootScope.$broadcast(
              scope.data.queryId ? 'saved-search-edited' : 'saved-search-added',
              {text: scope.data.viewName, value: response.id});
            scope.close();
          }).error(function() {
            scope.setState('error');
          });
        };
      }
    };
  }
])



.directive('enterpriseBrandsEditPopup', ['$http', '$timeout', 'tsConfig',
  function ($http,$timeout, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/enterprise_brands_edit.html'),
      link: function (scope, iElement, iAttrs) {
        scope.matchBrandUrl = iAttrs.matchBrandUrl;
        scope.brands = JSON.parse(iAttrs.brands);
        scope.brand_name = null;
        scope.brand_url = null;
        scope.show_name = false;
        scope.modified = false;
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
        scope.$on('openEnterpriseBrandsEditPopup', function (their_scope, args) {
          scope.open();
        });
        scope.brandName = function(){
          return scope.brand_name;
        };
        scope.changeBrandName = function(brand_name){
          scope.brand_name = brand_name;
        };
        scope.save = function(){
          scope.modified = true;
          scope.setState('saving');
          $http({
            method: 'POST',
            url: iAttrs.saveUrl,
            data: {
              name: scope.brand_name,
              url: scope.brand_url
            }
          }).success(function(){
            scope.brands.push(scope.brand_name);
            scope.setState('opened');
          }).error(function(){
            scope.setState('opened');
          });
        };
        scope.remove = function(name){
          scope.modified = true;
          scope.setState('saving');
          $http({
            method: 'POST',
            url: iAttrs.delUrl,
            data: {
              name: name,
            }
          }).success(function(){
            var idx = scope.brands.indexOf(name);
            if(idx>=0){
              scope.brands.splice(idx, 1);
            }
            scope.setState('opened');
          });
        };
        scope.close_cb = function(){
          if(scope.modified){
            scope.open();
            scope.setState('refreshing');
            window.location.reload();
          }
        };
      }
    };
  }
])


.directive('ccEditPopup', ['$http', '$timeout', 'tsConfig',
  function ($http, $timeout, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/cc_edit_popup.html'),
      link: function (scope, iElement, iAttrs) {
        Stripe.setPublishableKey(iAttrs.key);
        scope.exp_month = {};
        scope.exp_year = {};
        scope.months = [];
        scope.years = [];
        for (var i = 1; i <= 12; ++i)
          scope.months.push({text: i.toString()});
        for (var i = 2014; i <= 2025; ++i)
          scope.years.push({text: i.toString()});
        scope.types = [
          {
            text: "Visa",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "MasterCard",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "AmEx",
            mask: "9999 999999 99999",
            cvcmask: "9999"
          },{
            text: "JCB",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "Discover",
            mask: "9999 9999 9999 9999",
            cvcmask: "999"
          },{
            text: "Diners Club",
            mask: "9999 9999 9999 99",
            cvcmask: "999"
          }
        ];

        var stripe_validator = function () {
          if (scope.stripedata === undefined) return;
          if (scope.stripedata.number !== undefined) {
            scope.card_valid = Stripe.card.validateCardNumber(scope.stripedata.number);
            scope.card_type = Stripe.card.cardType(scope.stripedata.number);
            if(scope.card_type !== scope.cctype.text) scope.card_valid = false;
          }
          if (scope.stripedata.exp_month !== undefined && scope.stripedata.exp_year !== undefined) {
            scope.exp_valid = Stripe.card.validateExpiry(scope.stripedata.exp_month, scope.stripedata.exp_year);
          }
          if (scope.stripedata.cvc !== undefined) {
            scope.cvc_valid = Stripe.card.validateCVC(scope.stripedata.cvc);
          }
        };

        scope.updateType = function(selected){
          if (selected !== undefined)
            scope.cctype = selected;
          scope.ccmask = scope.cctype.mask;
          scope.cvcmask = scope.cctype.cvcmask;
          stripe_validator();
        };
        scope.cctype = angular.copy(scope.types[0]);
        scope.updateType();

        // scope.updateExpDate = function () {
        //   scope.stripedata.exp_month = scope.exp_month.text;
        //   scope.stripedata.exp_year = scope.exp_year.text;
        // };

        scope.updateExpMonth = function(selected) {
          if (selected)
            scope.exp_month = selected;
          scope.stripedata.exp_month = selected.text;
        };

        scope.updateExpYear = function(selected) {
          if (selected)
            scope.exp_year = selected;
          scope.stripedata.exp_year = selected.text;
        };  

        scope.$watch('stripedata', stripe_validator, true);

        var responseHandler = function (status, response) {
          scope.$apply(function () {
            if (response.error) {
              scope.error = response.error.message;
              scope.setState('error');
            } else {
              scope.error = "";
              var token = response.id;
              $http.post(iAttrs.saveUrl, {
                stripeToken: token,
              })
                .success(function (data) {
                  scope.setState('success');
                  window.location.reload();
                })
                .error(function (a, b, c, d) {
                  scope.error = a.error;
                  scope.setState('error');
                });
            }
          });
        };

        scope.getToken = function () {
          scope.setState('processing');
          Stripe.card.createToken(scope.stripedata, responseHandler);
        };

        scope.editNumber = function(){
          scope.number_edit = true;
        };

        scope.$on('openCCEditPopup', function () {
          if(iAttrs.lastfour){
            scope.card_placeholder = "**** **** **** "+iAttrs.lastfour;
            scope.number_edit = false;
          }
          scope.stripedata = {};
          scope.paymentdata = {};
          scope.exp_month = iAttrs.expMonth!==undefined&&{'text':iAttrs.expMonth}||{};
          scope.exp_year = iAttrs.expYear!==undefined&&{'text':iAttrs.expYear}||{};
          scope.stripedata.exp_month = scope.exp_month.text;
          scope.stripedata.exp_year = scope.exp_year.text;
          scope.open();
        });
      }
    };
  }
])


.directive('requestDemoPopup', ['$http', '$sce', 'tsConfig',
  function ($http, $sce, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/contact_us_demo.html'),
      link: function (scope, iElement, iAttrs) {
        scope.target = iAttrs.target;
        scope.$on('_openRequestDemo', function (their_scope) {
          scope.loaded = false;
          scope.open();
          scope.data = {};
          scope.error = null;
          scope.data.subject = "Demo request";
          scope.data.name = iAttrs.name;
          scope.data.email = iAttrs.email;
          scope.data.brand = iAttrs.brand;
          scope.data.brandurl = iAttrs.brandurl;
          $http.get(iAttrs.source)
            .success(function (data) {
              scope.captcha = $sce.trustAsHtml(data.captcha);
              scope.loaded = true;
            });
        });
        scope.submit = function(data){
          scope.loaded = false;
          data.captcha_0 = iElement.find('#id_captcha_0').val();
          data.captcha_1 = iElement.find('#id_captcha_1').val();
          $http({
              method: 'POST',
              url: iAttrs.target,
              data: $.param(data),
              headers: {'Content-Type': 'application/x-www-form-urlencoded'}
          }).success(function(){
            window.location.assign(iAttrs.after);
          })
          .error(function(data){
            var keys = Object.keys(data.errors);
            var errors = [];
            for(var i = 0; i< keys.length; i++){
              for(var j = 0; j<data.errors[keys[i]].length; j++){
                errors.push(keys[i]+": "+data.errors[keys[i]][j]);
              }
            }
            scope.error = $sce.trustAsHtml(errors.join("<br/>"));
            scope.loaded = true;
          });
        };
      }
    };
  }
])


.directive('trialOverPopup', ['$timeout', '$rootScope', 'tsConfig',
  function ($timeout, $rootScope, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/trial_over_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.pricing_url = iAttrs.pricingUrl;
        $timeout(function(){
          scope.open();
        }, 1000);
        scope.requestDemo = function(){
          scope.forceClose();
          $rootScope.$broadcast("openRequestDemo");
        };
      }
    };
  }
])

.directive('proPlanSettingsPopup', ['$http', '$timeout', 'tsConfig',
  function ($http,$timeout, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/pro_plan_is_agency_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.isAgencyNo = function(){
          scope.setState('saving');
          $http({
              method: 'POST',
              url: scope.markAsAgency,
              headers: {'Content-Type': 'application/x-www-form-urlencoded'}
          }).success(function(){
            window.location.assign('/');
          })
        };
        scope.isAgencyYes = function(){
          scope.setState("firstBrand");
        };
        scope.matchBrandUrl = iAttrs.matchBrandUrl;
        scope.markAsAgency = iAttrs.markAsAgency;
        scope.show_name = false;
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
          scope.setState('saving');
          $http({
            method: 'POST',
            url: iAttrs.saveUrl,
            data: {
              name: scope.brand_name,
              url: scope.brand_url
            }
          }).success(function(){
            window.location.assign('/');
          }).error(function(msg) {
            scope.brand_name = null;
            scope.brand_url = null;
            scope.setState('error');
            scope.errorMessage = msg;
          });
        };
        var autoopen = function(){
          if(scope.open === undefined){
            $timeout(autoopen, 100);
            return;
          }
          scope.open();
          scope.setNoClose(true);
          if(iAttrs.selectBrand !== undefined){
              scope.isAgencyYes();
          }
        }
        autoopen();
      }
    };
  }
])

.directive('messageInfluencerPopup', ['$http', '$rootScope', 'tsConfig',
  function ($http, $rootScope, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/contact_influencer_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.$on('openMessageInfluencerPopup', function (their_scope, id) {
          scope.id = id;
          scope.open();
          setTimeout(function() {
            iElement.find('#editor').wysiwyg();
            iElement.find('#editor').html('');
          }, 100);
        });
        scope.send = function(template, subject){
          scope.setState("sending");
          $http({
            url: iAttrs.url,
            method: "POST",
            data: {
              template: iElement.find('#editor').cleanHtml(),
              id: scope.id,
              subject: subject,
              thread: scope.thread,
              attachments: scope.getAttachments()
            }
          }).success(function(data){
            if(data.status == "sent"){
              scope.status = "Success";
            }else if (data.status == "rejected"){
              if(data.reject_reason == "soft-bounce"){
                scope.status = "Email was sent but it couldn't be delivered. We will retry in few minutes!";
              }else{
                scope.status = "We couldn't send this message.";
              }
            }
            scope.setState("done");
          }).error(function(){
            scope.setState("error");
          });
        };
      }
    };
  }
])

.directive('sendInvoicePopup', ['$http', '$rootScope', 'tsConfig',
  function ($http, $rootScope, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/send_invoice_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.$on('openSendInvoice', function (their_scope, id) {
          scope.open();
          scope.send();
        });
        scope.send = function(template, subject){
          $http({
            url: iAttrs.url,
            method: "POST",
          }).success(function(){
            scope.close();
          }).error(function(){
            scope.close();
          });
        };
      } 
    };
  }
])



.directive('sendEmailPopup', [
  '$http',
  '$rootScope',
  '$timeout',
  'context',
  'tsSendEmail',
  'tsOutreachTemplate',
  'tsConfig',
  function ($http, $rootScope, $timeout, context, tsSendEmail, tsOutreachTemplate, tsConfig) {
  return {
    restrict: 'A',
    scope: {},
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/send_email_popup.html'),
    controller: function ($scope) {
      var vm = this;

      vm.sendOptions = {
        template: null,
        subject: null,
        mailboxId: null,
      };

      vm.send = function (options) {
        vm.beforeSend();
        $http({
          method: 'POST',
          url: vm.sendUrl,
          data: {
            template: {
              body: vm.sendOptions.template,
              subject: vm.sendOptions.subject,
            },
            send_mode: options ? options.send_mode : undefined,
            map_id: vm.sendOptions.mailboxId,
          }
        }).success(function (response) {
          vm.successCb(response);
        }).error(function (response) {
          vm.errorCb(response);
        });
      };

      vm.template = null;

      $scope.send = vm.send;
      $scope.hideSendTest = true;

    },
    controllerAs: 'sendEmailPopupCtrl',
    link: function (scope, iElement, iAttrs, vm) {
      scope.$on('openSendEmailPopup', function (their_scope, options) {
        scope.setBackgroundType(null);
        vm.sendUrl = options.url;
        vm.sendOptions.mailboxId = options.mailboxId;

        vm.beforeSend = function () {
          scope.setBackgroundType('black');
          scope.setState('sending');
        };

        vm.successCb = function (response) {
          scope.setBackgroundType(null);
          if (options.status) {
            angular.extend(options.status, response.data.status);
          }
          if (options.successCb) {
            options.successCb(options.successCbParams);
          }
          if (options.successEvent) {
            $rootScope.$broadcast(options.successEvent, options.successEventParams);
          }
          scope.close();
        };

        vm.errorCb = function (response) {
          scope.setState('error');
        };
        scope.open();

        scope.setBackgroundType('black');
        scope.setState('sending');
        $http({
          method: 'GET',
          url: options.templateContextUrl,
        }).success(function (templateContext) {
          scope.setBackgroundType(null);
          scope.setState('opened');
          var tmpContext = angular.copy(templateContext);
          tmpContext.context = context;
          vm.template = new tsOutreachTemplate(options.template, options.subject);
          vm.sendOptions.template = vm.template.getBody(null, tmpContext);
          if (templateContext.data && templateContext.data.subject) {
            vm.sendOptions.subject = templateContext.data.subject;
          } else {
            vm.sendOptions.subject = vm.template.getSubject(null, tmpContext);
          }
          vm.bloggerPagePreviewUrl = options.bloggerPagePreviewUrl;
          vm.extraUrls = options.extraUrls;
        }).error(function () {
          scope.setState('error');
        });

      });
    }
  };
}])



.directive('pdfDocumentPopup', ['$timeout', 'tsConfig', function ($timeout, tsConfig) {
  return {
    restrict: 'A',
    scope: {},
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/pdf_document_popup.html'),
    link: function (scope, iElement, iAttrs) {
      scope.$on('openPdfDocumentPopup', function (their_scope, options) {
        scope.url = options.url;
        scope.titleText = options.title;
        scope.random = Math.random();
        scope.open();

        scope.pdfUrl = options.url;
        scope.scroll = 0;
        scope.tsConfig = tsConfig;

        scope.docState = 'loading';

        scope.getNavStyle = function(scroll) {
          if (scroll > 100) return 'pdf-controls fixed';
          else return 'pdf-controls';
        };

        scope.onError = function(error) {
          console.log('onError');
          scope.docState = 'error';
        };

        scope.onLoad = function() {
          console.log('onLoad');
          scope.docState = 'loaded';
        };

        scope.onProgress = function(progress) {
          console.log(progress);
        };


        // $timeout(function() {
        //   var container = iElement.find('#object-container');
        //   var defaultContent = angular.element('<p><a href="' + scope.url + '?r=' + scope.random + '" target="_blank">Click</a> to download the document</p>');
        //   var object = angular.element('<object data="' + scope.url + '?r=' + scope.random + '" type="application/pdf" width="100%" height="500px"></object>');
        //   object.append(defaultContent);
        //   container.append(object);
        // }, 200);
      });
    }
  };
}])


.directive('autosave', ['_', function(_) {
  return {
    restrict: 'A',
    link: function(scope, iElement, iAttrs) {

      function saveModel(newModel, oldModel) {
        console.log(newModel, oldModel, scope.infDataPopupCtrl.blogger);
        if (newModel !== oldModel && oldModel !== undefined) {
          scope.infDataPopupCtrl.blogger.save();
        }
      }

      scope.$watch(iAttrs.model, _.debounce(saveModel, 2000), true);
    }
  };
}])


.directive('tagBubbles', [function() {
  return {
    restrict: 'A',
    scope: {
      choices: '=',
      output: '=',
      blogger: '=',
    },
    template: '<div class="tag" ng-repeat="tag in tagBubblesCtrl.choices" ng-click="tagBubblesCtrl.toggle(tag)" ng-class="{\'selected\': tag.selected}">{{ tag.name }}</div>',
    controllerAs: 'tagBubblesCtrl',
    controller: function() {
      var vm = this;

      vm.toggle = function(tag) {
        tag.selected = !tag.selected;
        vm.output.splice(0, vm.output.length);
        Array.prototype.push.apply(vm.output, vm.choices
          .filter(function(c) { return c.selected; })
          .map(function(c) { return c.name; }));
        vm.blogger.save();
      };

    },
    link: function(scope, iElement, iAttrs, ctrl) {
      ctrl.blogger = scope.blogger;
      ctrl.choices = scope.choices;
      ctrl.output = scope.output;
    }
  };
}])


.directive('influencerDataPopup', ['$timeout', 'Restangular', 'tsConfig', 'BloggerCustomData', 'NotifyingService',
    'BloggerCustomDataPopup',
    function ($timeout, Restangular, tsConfig, BloggerCustomData, NotifyingService, BloggerCustomDataPopup) {
  return {
    restrict: 'A',
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/influencer_data_popup.html'),
    controllerAs: 'infDataPopupCtrl',
    require: ['customPopup', 'influencerDataPopup'],
    controller: function ($scope) {
      var vm = this;
    },
    link: function (scope, iElement, iAttrs, ctrls) {
      var customPopupCtrl = ctrls[0];
      var ctrl = ctrls[1];

      ctrl.popup = BloggerCustomDataPopup;

      NotifyingService.subscribe(scope, 'customPopup:enter', function(theirScope, options) {
        // scope.state = 'loading';
        scope.setBackgroundType('black');
        scope.setState('loading');
        scope.visible = true;
        ctrl.baseBlogger = options.influencer;

        BloggerCustomDataPopup.fetchData(ctrl.baseBlogger.id).then(function(blogger) {
          ctrl.blogger = blogger;
          scope.setState('opened');
          scope.setBackgroundType(null);
        });

      });

      scope.customCloseCb = function() {
        console.log('close cb');
        if (ctrl.baseBlogger.brand_custom_data) {
          ctrl.blogger.save({ignoreBackend: true});
          angular.extend(ctrl.baseBlogger.brand_custom_data, ctrl.blogger.data);
        }
      };

    },
  };
}])


.service('BloggerCustomDataPopup', ['Restangular', 'context', 'BloggerCustomData', function(Restangular, context, BloggerCustomData) {
  var self = this;

  self.fetchData = function(influencerId) {
    return Restangular
      .one('brands', context.visitorBrandId)
      .customGET('blogger_custom_data', {influencer_id: influencerId})
      .then(function(response) {
        return new BloggerCustomData({
          bloggerData: Restangular.stripRestangular(response),
        });
      });
  };

}])


.factory('BloggerCustomData', ['Restangular', 'context', function(Restangular, context) {

  function BloggerCustomData(options) {
    var self = this;

    self.data = angular.copy(options.bloggerData);
  }

  BloggerCustomData.prototype = {};

  BloggerCustomData.prototype.update = function(data) {
    var self = this;
    if (!self.data) self.data = {};
    angular.extend(self.data, data);
  };
 
  BloggerCustomData.prototype.save = function(options) {
    var self = this;

    console.log('saving');

    if (self.data['language'].length && self.data['language'][0].name) {
      self.data['language'] = self.data['language'].map(function(c) {
        return c.name;
      });
    }

    if (options && options.ignoreBackend) return;

    Restangular
      .one('brands', context.visitorBrandId)
      .post('blogger_custom_data', {
        influencer_id: self.data.influencer,
        fields: self.data,
      });
  };

  BloggerCustomData.prototype.formatAndSave = function(name) {
    var self = this;

    self.data[name] = self.data[name].map(function(c) {
      return c.name;
    });
    self.save();
  };

  return BloggerCustomData;
}])



.directive('contractPipelinePopup', ['$timeout', 'Restangular', 'tsConfig', function ($timeout, Restangular, tsConfig) {
  return {
    restrict: 'A',
    // scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/contract_pipeline_popup.html'),
    controllerAs: 'contractPipelinePopupCtrl',
    require: ['customPopup', 'contractPipelinePopup'],
    controller: function ($scope) {
      var ctrl = this;

      ctrl.tabHandlers = {
        3: {
          onEnter: function () {
            $timeout(function () {
              $scope.$broadcast('loadAddPostsWidget', {contractId: $scope.customPopupCtrl.openOptions.contractId});
            });
          },
          onExit: function () {
            $scope.$broadcast('cancelLoadAddPostsWidget');  
          }
        },
        6: {
          onEnter: function () {
            $timeout(function () {
              var contract = Restangular.one('contracts', $scope.customPopupCtrl.openOptions.contractId);
              contract.post('generate_google_doc').then(function (response) {
                $scope.$broadcast('renderIframe', {
                  url: response.data.googleDocEmbedUrl
                });
              });
            })
          },
          onExit: function () {
            $timeout(function () {
              $scope.$broadcast('clearIframe');
            });
          }
        }
      };

    },
    link: function (scope, iElement, iAttrs, ctrls) {
      var customPopupCtrl = ctrls[0];
      var contractPipelinePopupCtrl = ctrls[1];

      customPopupCtrl.setTabHandlers(contractPipelinePopupCtrl.tabHandlers);
    },
  };
}])



.directive('invitePopup', [
  'Restangular',
  '$http',
  '$rootScope',
  '$timeout',
  '$sce',
  '$window',
  'context',
  'FileUploader',
  'tsInvitationMessage',
  'tsConfig',
  'NotifyingService',
  function (Restangular, $http, $rootScope, $timeout, $sce, $window, context, FileUploader,
      tsInvitationMessage, tsConfig, NotifyingService) {
    return {
      restrict: 'A',
      // scope: true,
      scope: {},
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/invitation_popup.html'),
      controllerAs: 'invitePopupCtrl',
      controller: function () {
      },
      link: function (scope, iElement, iAttrs, ctrl) {

        var outreachTemplates = null;
        var campaigns = null;

        scope.template = iAttrs.template;
        scope.subject = iAttrs.subject;
        scope.brand_name = iAttrs.brandName;
        scope.context = context;
        scope.settings_url = iAttrs.settingsUrl;
        scope.can_set_subject = iAttrs.canSetSubject !== undefined;

        scope.uploader = new FileUploader({
            url: context.messageUrls.attachmentUploadUrl,
            autoUpload: true,
            headers: {
                'X-CSRFToken': context.csrf_token
            }
        });

        scope.uploader.onSuccessItem = function(fileItem, response, status, headers) {
            fileItem.response = response;
        };

        scope.sendOptions = {
          // attachments: [],
          template: scope.template,
          sendMode: null,
          attachments: scope.uploader.queue,
        };

        scope.resetSendOptions = function () {
          scope.sendOptions.template = scope.template,
          scope.sendOptions.sendMode = null;
          scope.uploader.clearQueue();
        };

        scope.openContactForm = function() {
          console.log('contact us');
          $rootScope.$broadcast("openContactForm");
        };

        scope.job = {};

        function handleCampaignChange(nv) {
          if (nv !== null && outreachTemplates && outreachTemplates[nv]) {
            if (outreachTemplates[nv].template) {
              scope.sendOptions.template = tsInvitationMessage.getBody(outreachTemplates[nv].template, scope);  
            } else {
              scope.sendOptions.template = scope.template;
            }
            if (outreachTemplates[nv].subject) {
              scope.sendOptions.subject = tsInvitationMessage.getSubject(outreachTemplates[nv].subject, scope);
            } else {
              scope.sendOptions.subject = scope.subject;
            }
          } else {
            scope.sendOptions.template = scope.template;
            scope.sendOptions.subject = scope.subject;
          }
        }

        function openHandler(theirScope, options) {
          scope.campaign_overview_link = options.campaign_overview_link;
          scope.setBackgroundType(null);
          
          scope.resetSendOptions();
          scope.sendOptions.template = options.template;
          scope.sendOptions.subject = options.subject;

          scope.forceInvite = options.forceInvite;
          scope.strictForce = options.strictForce;

          scope.hideCloseButton = false;
          scope.confirmEnabled = false;
          scope.reload = options.reload;
          scope.group_id = options.groupId;
          scope.ijm_id = options.ijm_id;
          scope.influencer_id = options.userId;
          scope.template = options.template;
          scope.subject = options.subject;
          scope.confirmed = false;
          scope.user = options.user;
          scope.targetScope = theirScope;
          // scope.successCb = options.successCb;
          // scope.successCbParams = options.successCbParams;
          scope.extraParams = options.extraParams;
          scope.invited_to = options.jobIds !== undefined ? options.jobIds : (scope.user && scope.user.invited_to ? scope.user.invited_to : []);
          // scope.job = {text: "Don't add campaign link", value: null};
          angular.extend(scope.job, {text: "Don't add campaign link", value: null});
          // if (options.forceInvite !== undefined) {
          //   scope.force_invite = true;
          //   scope.job.value = options.forceInvite;
          //   for(var i=0;i<scope.campaigns.length; i++){
          //     if (options.forceInvite == scope.campaigns[i].value) {
          //       scope.job.text = scope.campaigns[i].text;
          //       break;
          //     }
          //   }
          // } else {
          scope.possible_campaigns = [{
            text: "Don't add campaign link", value: null
          }];
          if (campaigns) {
            for (var i=0; i < campaigns.length; i++) {
              if (scope.invited_to.indexOf(campaigns[i].value) < 0) {
                scope.possible_campaigns.push({
                  text: campaigns[i].text.replace("&#39;", "'"),
                  value: campaigns[i].value,
                });
              } else {
                scope.possible_campaigns.push({
                  text: campaigns[i].text.replace("&#39;", "'") + " (already invited)",
                  value: campaigns[i].value,
                });
              }
              if (options.forceInvite !== undefined && options.forceInvite == campaigns[i].value) {
                scope.campaignLinkChanged(campaigns[i]);
              }
            }
          }
          // scope.open();
          scope.setState('opened');
        }

        NotifyingService.subscribe(scope, 'openInvitationPopup', function (theirScope, options) {
          scope.open();
          scope.setState("sending");
          scope.setBackgroundType('black');

          Restangular
            .one('brands', context.visitorBrandId)
            // .one('outreach_templates')
            .withHttpConfig({ cache: true })
            .get()
            .then(function(response) {
              outreachTemplates = response.outreachTemplates;
              campaigns = response.campaigns;
              openHandler(theirScope, options);
            });
        }, true);

        scope.campaignLinkChanged = function(selected) {
          angular.extend(scope.job, selected);
          handleCampaignChange(scope.job.value);
          if (scope.invited_to.indexOf(scope.job.value) < 0) {
            scope.alreadyInvited = false;
          } else {
            scope.alreadyInvited = true;
          }
        };

        scope.setSubject = function(subject){
          scope.subject = subject;
        };
        scope.confirm = function(yes){
          if (yes) {
            scope.confirmed = true;
            scope.send(null);
          } else {
            scope.setState('opened');
          }
        };

        scope.send = function(options){
          if (context.onTrial) {
            $rootScope.$broadcast("displayMessage", {
              message: "During Trial, you are not allowed to send messages. Please upgrade to use this feature."
            });
            return;
          }
          if (options !== null && options !== undefined)
            angular.extend(scope.sendOptions, options);
          if (scope.alreadyInvited) {
            scope.setState("alreadyInvited");
          } else if(scope.confirmEnabled && scope.job.value === null && scope.confirmed !== true){
            scope.setState("confirm");
          } else{
            // scope.hideCloseButton = true;
            scope.setState("sending");
            scope.setBackgroundType('black');
            $http({
              url: iAttrs.url,
              method: "POST",
              data: {
                template: scope.sendOptions.template,
                influencer_id: scope.influencer_id,
                group_id: scope.group_id,
                job_id: scope.job.value,
                ijm_id: scope.ijm_id,
                influencer_analytics_id: options.influencer_analytics_id,
                subject: scope.sendOptions.subject,
                send_mode: scope.sendOptions.sendMode,
                attachments: scope.formatAttachments(scope.sendOptions.attachments)
              }
            }).success(function(response){
              // if(data.status == "sent" || data.status == "queued"){
              scope.status = "Success";
              if (scope.sendOptions.reload) {
                if (scope.reloadPage !== undefined) {
                  scope.close();
                  scope.reloadPage();
                } else {
                  window.location.reload();
                }
              } else if (scope.sendOptions.sendMode !== 'test') {
                if (scope.user !== undefined && scope.user !== null) {
                  scope.user.is_sent_email = true;
                  if (scope.job.value !== null && scope.user.invited_to) {
                    scope.user.invited_to.push(scope.job.value);
                  }
                }
              }
              if (scope.sendOptions.sendMode !== 'test') {
                $rootScope.$broadcast('invitationSent', {
                  user: scope.user,
                  ijmId: scope.ijm_id,
                  mailboxId: response.data.mailboxId,
                  extraParams: scope.extraParams,
                  targetScope: scope.targetScope,
                  // successCb: scope.successCb,
                  // successCbParams: scope.successCbParams
                });
              }
              // }else if (data.status == "rejected"){
                // if(data.reject_reason == "soft-bounce"){
                //   scope.status = "Email was sent but it couldn't be delivered. We will retry in few minutes!";
                // }else{
                //   scope.status = "We couldn't send this message.";
                // }
              // }
              // scope.setState("done");
              scope.close();
            }).error(function(){
              scope.setState("error");
            });
          }
          
        };

      }
    };
  }
])


;
