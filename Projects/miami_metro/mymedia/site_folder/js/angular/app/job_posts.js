'use strict';

angular.module('theshelf')


.controller('MessagesCtrl', ['$scope', '$http', '$rootScope', 'messagesData', function($scope, $http, $rootScope, messagesData) {
  var ctrl = this;
  ctrl.sections = messagesData.sections;
  ctrl.sectionSelected = _.findWhere(ctrl.sections, {selected: true});

  $rootScope.$on('mailboxRowRemoved', function(their_scope, options) {
    ctrl.sectionSelected.count--;
    if (options && options.unread) {
      ctrl.sectionSelected.extra.unread_count--;
    }
  });

  $rootScope.$on('mailboxMoved', function(their_scope, options) {
    var section = _.findWhere(ctrl.sections, {key: options.stage});
    section.count++;
    if (options.unread) {
      section.extra.unread_count = section.extra.unread_count || 0;
      section.extra.unread_count++;
    }
  });

  $rootScope.$on('unreadMessageOpened', function(their_scope) {
    ctrl.sectionSelected.extra.unread_count--;
  });
}])


.controller('PipelineCtrl', ['$scope', '$http', '$rootScope',
    'Restangular', 'pipelineData', 'NotifyingService',
    function($scope, $http, $rootScope, Restangular, pipelineData, NotifyingService) {
  var pipeline = this;

  pipeline.data = pipelineData;

  pipeline.showPagination = true;

  pipeline.sections = pipelineData.sections;
  pipeline.sectionSelected = _.findWhere(pipeline.sections, {selected: true});

  pipeline.approvalSections = pipelineData.approvalSections;
  pipeline.approvalSectionSelected = _.findWhere(pipeline.approvalSections, {selected: true});

  pipeline.getViews = function() {
    return [_.first(pipeline.sections), _.last(pipeline.sections)];
  };

  pipeline.getViewSelected = function() {
    if ([pipelineData.ALL_STAGE, pipelineData.ARCHIVED_STAGE].indexOf(pipeline.sectionSelected.key) < 0) {
      return null;
    }
    return pipeline.sectionSelected;
  };

  pipeline.getFilters = function() {
    return pipeline.sections.slice(1, pipeline.sections.length - 1);
  };

  pipeline.filters = pipeline.getFilters();
  pipeline.views = pipeline.getViews();

  pipeline.moveToStage = function(options) {
    $http({
      method: 'POST',
      url: '',
      data: {
        modelName: 'InfluencerJobMapping',
        id: options.ijmId,
        values: {
          campaign_stage: options.stage,
          moved_manually: options.movedManually
        }
      }
    }).success(function(response) {
      // $rootScope.$broadcast('mailboxRowRemoved');
      // $rootScope.$broadcast('mailboxMoved', {stage: options.stage});
      if (options.successCb) {
        options.successCb(options.successCbParams);
      }
    }).error(function() {
    });
  };

  pipeline.moveBloggersButtonLoading = false;
  pipeline.moveBloggersButtonLoaded = false;
  pipeline.moveAllBloggers = function(options) {
    var nextStage = options.stage == 'next' ? pipeline.sectionSelected.key + 1 : options.stage;
    var nextSection = _.findWhere(pipeline.sections, {key: nextStage});

    function yes() {
      pipeline.moveBloggersButtonLoading = true;

      NotifyingService.notify('table:removeAll');

      pipeline.showPagination = false;

      Restangular
        .one('campaigns', pipelineData.campaignId)
        .post('move_all_bloggers_to_another_stage', {
          from_stage: pipeline.sectionSelected.key,
          to_stage: nextSection.key
        }).then(function(response) {
          pipeline.moveBloggersButtonLoading = false;
          pipeline.moveBloggersButtonLoaded = true;

          nextSection.count += pipeline.sectionSelected.count;
          nextSection.extra.unread_count += pipeline.sectionSelected.extra.unread_count;
          pipeline.sectionSelected.count = 0;
          pipeline.sectionSelected.extra.unread_count = 0;

          window.location.href = response.redirectUrl;
        }, function() {
          pipeline.moveBloggersButtonLoading = false;
        });
    }

    $rootScope.$broadcast('openConfirmationPopup', [
      "Do you really want to move all bloggers from ",
      pipeline.sectionSelected.text + " to " + nextSection.text + " stage?"].join(''),
      yes, null, {titleText: "Are you sure?", yesText: "Yes", noText: 'No'});
  };

  $rootScope.$on('invitationSent', function(their_scope, options) {
    var opts = {};
    var extraParams = {};
    var successCbParams = {};

    if (options) {

      angular.extend(opts, options);

      if (opts.extraParams) {
        angular.extend(extraParams, opts.extraParams);
      }

      angular.extend(successCbParams, options);
      if (extraParams.successCbParams) {
        angular.extend(successCbParams, extraParams.successCbParams);
      }

    }

    if (Number(extraParams.moveToStage)) {
      pipeline.moveToStage({
        stage: Number(extraParams.moveToStage),
        movedManually: false,
        successCb: extraParams.successCb,
        successCbParams: successCbParams,
      });
    } else {
      if (typeof extraParams.successCb == "string") {
        $rootScope.$broadcast(extraParams.successCb, successCbParams);
      } else if (typeof extraParams.successCb == "function") {
        extraParams.successCb(successCbParams);
      }
    }

  });

  $rootScope.$on('mailboxRowRemoved', function(their_scope, options) {
    pipeline.sectionSelected.count--;
    pipeline.sections[0].count--;
    if (options && options.unread) {
      pipeline.sectionSelected.extra.unread_count--;
    }
  });

  $rootScope.$on('tableRowRemoved', function(their_scope, options) {
    pipeline.sectionSelected.count--;
    pipeline.approvalSectionSelected.count--;
  });

  $rootScope.$on('mailboxMoved', function(their_scope, options) {
    var section = _.findWhere(pipeline.sections, {key: options.stage});
    section.count++;
    if (options.unread) {
      section.extra.unread_count = section.extra.unread_count || 0;
      section.extra.unread_count++;
    }
    pipeline.sections[0].count++;
  });

  $rootScope.$on('unreadMessageOpened', function(their_scope) {
    pipeline.sections[0].extra.unread_count--;
    pipeline.sectionSelected.extra.unread_count--;
  });

  $rootScope.$broadcast('setHeaders', {headers: pipelineData.headers});

}])


.controller('BrandTaxonomyTableCtrl', [
  '$scope', '$rootScope', 'brandTaxonomyData', 'Restangular', 'tsUtils',
  function ($scope, $rootScope, brandTaxonomyData, Restangular, tsUtils) {
  var ctrl = this;

  ctrl.styleTag = tsUtils.getQueryVariable('style_tag');
  ctrl.productTag = tsUtils.getQueryVariable('product_tag');
  ctrl.priceTag = tsUtils.getQueryVariable('price_tag');

  ctrl.updateEs = function (params) {
    params.tableRow.updatingEs = true;
    var object = Restangular.one('brand_taxonomies', params.id);
    object.post('update_es_counts').then(function (response) {
        params.tableRow.influencers_count_column.values.fieldValue = response.influencersCount;
        params.tableRow.posts_count_column.values.fieldValue = response.postsCount;
        params.tableRow.instagrams_count_column.values.fieldValue = response.instagramsCount;
        params.tableRow.blog_posts_count_column.values.fieldValue = response.blogPostsCount;
        params.tableRow.actions_column.values.modified = response.modified;
        params.tableRow.updatingEs = false;
    });
  };

  ctrl.filter = function () {
    var query = [];
    if (ctrl.styleTag) {
      query.push('style_tag=' + ctrl.styleTag);
    }
    if (ctrl.productTag) {
      query.push('product_tag=' + ctrl.productTag);
    }
    if (ctrl.priceTag) {
      query.push('price_tag=' + ctrl.priceTag);
    }
    window.location.search = query.join('&');
  };

  $rootScope.$broadcast('setHeaders', {headers: brandTaxonomyData.headers});
}])


.controller('TableCtrl', ['$scope', '$rootScope', 'tsUtils', 'Restangular', function($scope, $rootScope, tsUtils, Restangular) {
  var table = this;

  table.headers = {};

  console.log(table);

  table.originalSearchQuery = tsUtils.getQueryVariable('q');
  table.searchQuery = table.originalSearchQuery;

  table.setHeaders = function(headers) {
    table.headers = headers;
  };

  table.emptyHeaders = function() {
    return _.isEmpty(table.headers);
  };

  table.visibleColumns = function(headers) {
    var visible = [];
    headers = headers ? headers : table.headers;
    angular.forEach(headers, function(value, key) {
      if (value.visible) {
        visible.push(key);
      }
    });
    return visible;
  };

  table.visibleColumnsNumber = function(headers) {
    headers = headers ? headers : table.headers;
    return _.filter(table.headers, function(header) { return header.visible; }).length;
  };

  table.search = function() {
    if (table.searchQuery !== table.originalSearchQuery) {
      window.location.search = 'q=' + table.searchQuery;
    }
  };

  $rootScope.$on('setHeaders', function(their_scope, options) {
    table.setHeaders(options.headers);
  });

  $rootScope.doOpenFavoritePopup = function(options) {
    $rootScope.$broadcast('openFavoritePopup', options);
  };

  $scope.$on('doOpenFavoritePopup', function(theirScope, options) {
    $rootScope.doOpenFavoritePopup(options);
  });

  // Add and remove active_soc_btn class
  // Add and remove active_soc_btn class
  // Add and remove active_soc_btn class

  $scope.impBtnClass = "block_header_tab";
  $scope.cliBtnClass = "block_header_tab";

  $scope.changeClass1 = function(){
    if ($scope.impBtnClass === "block_header_tab")
      $scope.impBtnClass = "block_header_tab active_soc_btn";
    else
      $scope.impBtnClass = "block_header_tab";
  };
  $scope.changeClass2 = function(){
    if ($scope.cliBtnClass === "block_header_tab")
      $scope.cliBtnClass = "block_header_tab active_soc_btn";
    else
      $scope.cliBtnClass = "block_header_tab";
  };

}])


.controller('LoadInfluencersCtrl', ['$scope', '$rootScope', '$location', 'loadInfluencersData', function($scope, $rootScope, $location, loadInfluencersData) {
  var ctrl = this;

  ctrl.tags = loadInfluencersData.tagsList;
  ctrl.postCollections = loadInfluencersData.postCollectionsList;
}])


.controller('CampaignCreateCtrl', [
  '$scope',
  '$rootScope',
  '$timeout',
  '$location',
  '$http',
  '$q',
  'context',
  'campaignCreateData',
  'tsInvitationMessage',
  'FileUploader',
  'tsPlatformIconClasses',
  'tsDeliverables',
  function($scope, $rootScope, $timeout, $location, $http, $q, context,
    campaignCreateData, tsInvitationMessage, FileUploader, tsPlatformIconClasses,
    tsDeliverables) {

  var ctrl = this;

  // ctrl.bindWarning = function(){
  //   console.log('bind warning');
  //   $(window).bind("beforeunload", function() {
  //       return "You have unsaved changes!";
  //   });
  // };

  // ctrl.unbindWarning = function(){
  //   console.log('unbind warning');
  //   $(window).unbind("beforeunload");
  // };

  // ctrl.set_cover_img = function(url) {
  //   $scope.campaignSpecificsSection.coverImage = url;
  //   $timeout(function() {
  //     $(".cover_img").removeClass("default");
  //     $(".cover_img").children().remove();
  //     $(".cover_img").append($("<img style='width: 500px' src='" + url + "?r=" + Math.random() + "'/>"));
  //   }, 10);
  // };

  // ctrl.set_profile_img = function(url) {
  //   $scope.campaignSpecificsSection.profileImage = url;
  //   $timeout(function() {
  //     $(".profile_pic").removeClass("default");
  //     $(".profile_pic").children().remove();
  //     $(".profile_pic").append($("<img class='picture_logo' src='" + url + "?r=" + Math.random() + "'/>"));
  //   }, 10);
  // };

  // $scope.$on("coverImageSet", function(their_scope, url) {
  //   $scope.campaignSpecificsSection.coverImageChanged++;
  //   ctrl.set_cover_img(url);
  //   ctrl.bindWarning();
  // });

  // $scope.$on("profileImageSet", function(their_scope, url) {
  //   $scope.campaignSpecificsSection.profileImageChanged++;
  //   ctrl.set_profile_img(url);
  //   ctrl.bindWarning();
  // });

  // ctrl.approvalSection = _.findWhere(
  //   campaignCreateData.campaignSections, {key: 'influencer_approval'});

  // $scope.campaignCreateData = campaignCreateData;
  // $scope.campaignId = campaignCreateData.campaignId;
  // $scope.context = context;

  // $scope.platformIcons = tsPlatformIconClasses.get;

  // $scope.uploader = new FileUploader({
  //   url: context.messageUrls.attachmentUploadUrl,
  //   autoUpload: true,
  //   headers: {
  //       'X-CSRFToken': context.csrf_token
  //   }
  // });

  // $scope.uploader.onSuccessItem = function(fileItem, response, status, headers) {
  //     fileItem.response = response;
  // };

  // $scope.formNames = ['nameSectionForm', 'outreachConfigurationSectionForm'];

  // $scope.formDefers = {};
  // $scope.formPromises = {};

  // angular.forEach($scope.formNames, function(name) {
  //   var deferred = $q.defer();
  //   $scope.formDefers[name] = deferred;
  //   $scope.formPromises[name] = deferred.promise;
  // });

  // $scope.registerFormScope = function(form, name, id) {
  //   $scope.formDefers[name].resolve(form);
  // };

  // $scope.oneAtATime = true;
  // $scope.current_step = 0;

  // $scope.isEdit = function() {
  //   return campaignCreateData.campaignId ? true : false;
  // };

  // $scope.submitToClient = function(options) {
  //   $rootScope.$broadcast('openBloggerApprovalPopup', options);
  // };

  // $scope.saving = false;

  // $scope.save = function() {
  //   $scope.saving = true;
  //   return $http({
  //     method: 'POST',
  //     url: '',
  //     data: {
  //       campaign: {
  //         id: $scope.campaignId,
  //         modelName: 'BrandJobPost',
  //         values: {
  //           title: $scope.nameSection.campaignName,
  //           client_name: $scope.nameSection.clientName,
  //           client_url: $scope.nameSection.clientURL,
  //           description: $scope.campaignSpecificsSection.description,
  //           who_should_apply: $scope.campaignSpecificsSection.whoShouldApply,
  //           hashtags_required: $scope.campaignSpecificsSection.hashtagsRequired,
  //           mentions_required: $scope.campaignSpecificsSection.mentionsRequired,
  //           details: $scope.campaignSpecificsSection.details,
  //           date_start: moment($scope.dateRangeModel.startDate).format('YYYY-MM-DD'),
  //           date_end: moment($scope.dateRangeModel.endDate).format('YYYY-MM-DD'),
  //           creator_id: context.visitorBrandId,
  //           oryg_creator_id: context.visitorBrandId,
  //         },
  //         json_fields: {
  //           info: {
  //             approval_report_enabled: $scope.nameSection.enabled,
  //             deliverables: $scope.campaignSpecificsSection.deliverables,
  //             sending_product_on: $scope.productSendingSection.options.sending_product_on.value,
  //             signing_contract_on: $scope.contractsSection.signing_contract_on,
  //             tracking_codes_on: $scope.trackingCodesSection.tracking_codes_on,
  //             product_links_on: $scope.productSendingSection.productLinksOn,
  //             same_product_url: $scope.productSendingSection.sameProductUrl,
  //             product_url: $scope.productSendingSection.productUrl,
  //             do_select_url: $scope.productSendingSection.doSelectUrl,
  //             restrictions: $scope.productSendingSection.restrictions,
  //             blogger_additional_info_on: $scope.productSendingSection.bloggerAdditionalInfoOn,
  //             blogger_additional_info: $scope.productSendingSection.bloggerAdditionalInfo,
  //             post_requirements: $scope.campaignSpecificsSection.postRequirements,
  //             date_requirements_on: $scope.campaignSpecificsSection.dateRequirementsOn,
  //           },
  //           outreach_template: {
  //             subject: $scope.outreachConfigurationSection.subject,
  //             template: $scope.outreachConfigurationSection.template,
  //             attachments: $scope.outreachConfigurationSection.getAttachments(),
  //           }
  //         }
  //       },
  //       report: {
  //         modelName: 'ROIPredictionReport',
  //         values: {
  //         },
  //         json_fields: {
  //           info: {
  //             blogger_approval_report_columns_hidden: $scope.approvalReportSection.columns
  //               .filter(function(column) { return !column.visible; })
  //               .map(function(column) {
  //                 return column.name;
  //               }),
  //             recipients: $scope.approvalReportSection.recipients,
  //           }
  //         }
  //       }
  //     }
  //   }).success(function() {
  //     campaignCreateData.defaults.campaignName = $scope.nameSection.campaignName;
  //     campaignCreateData.defaults.clientName = $scope.nameSection.clientName;
  //     campaignCreateData.defaults.clientURL = $scope.nameSection.clientURL;
  //     $scope.saving = false;
  //     angular.forEach($scope.sections, function(section, index) {
  //       section.changed = false;
  //       $scope.status[index]['is_completed'] = true;
  //     });
  //     ctrl.unbindWarning();
  //   }).error(function() {
  //     $scope.saving = false;
  //   });
  // };

  // $scope.canSave = function(step) {
  //   if (step === undefined) {
  //     return !$scope.saving && _.any($scope.status, function(s) { return !s.is_completed; }) && _.all($scope.sections, function(s) { return s.valid(); });
  //   } else {
  //     return !$scope.saving && !$scope.status[step].is_completed && $scope.sections[step].valid();
  //   }
  // };

  // $scope.setState = function(state) {
  //   $scope.state = state;
  // };

  // $scope.status = [
  //   {can_edit: true, is_completed: true, is_open: false, live: true},
  //   {can_edit: true, is_completed: true, is_open: false, live: true},
  //   {can_edit: true, is_completed: true, is_open: false, live: true},
  //   {can_edit: true, is_completed: true, is_open: false, live: true},
  //   {can_edit: true, is_completed: true, is_open: false, live: true},
  //   {can_edit: true, is_completed: true, is_open: false, live: true},
  //   {can_edit: true, is_completed: true, is_open: false, live: false},
  //   {can_edit: false, is_completed: true, is_open: false, live: false},
  // ];

  // $scope.setCurrentStep = function(step) {    
  //   $scope.current_step = step;
  //   for (var i in $scope.status) {
  //     $scope.status[i].is_open = false;
  //   }
  //   $scope.status[step]['is_open'] = true;
  //   $scope.status[step]['can_edit'] = true;
  // };

  // $scope.doMoveStep = function(step) {
  //   var defer;

  //   if ($scope.status[$scope.current_step]['is_completed']) {
  //     $scope.setCurrentStep(step);
  //     defer = $q.defer();
  //     defer.resolve(true);
  //     return defer.promise;
  //   }



  //    else {
  //     if (!$scope.canSave($scope.current_step)) {
  //       return;
  //     }
  //     $scope.save().then(function() {
  //       $scope.status[$scope.current_step]['is_completed'] = true;
  //       $scope.doMoveStep(step);
  //     });
  //   }
  // };

  // $scope.moveStep = function(step) {
  //   $location.path("/" + (step + 1));
  // };

  // $scope.moveNextStep = function() {
  //   $scope.moveStep($scope.current_step + 1);
  // };

  // // $scope.setCurrentStep(campaignCreateData.afterCreate ? 0 : 0);
  // // $scope.moveStep(campaignCreateData.afterCreate ? 0 : 0);

  // $scope.submitStep = function (step) {
  //   $scope.moveNextStep(step);
  // };

  // function NameSection(options) {
  //   var self = this;
  //   self.changed = false;

  //   self.formPromise = options.formPromise;
  //   self.formPromise.then(function(form) {
  //     self.form = form;
  //   })

  //   self.campaignName = campaignCreateData.defaults.campaignName;
  //   self.clientName = campaignCreateData.defaults.clientName;
  //   self.clientURL = campaignCreateData.defaults.clientURL;

  //   self.enabled = campaignCreateData.defaults.approvalEnabled || false;

  //   self.toggle = function() {
  //     self.enabled = !self.enabled;
  //   };

  //   self.watch = ['campaignName', 'clientName', 'clientURL', 'enabled'];

  //   self.valid = function() {
  //     return !self.form || self.form.$valid;
  //   };
  // }

  // function ApprovalReportSection() {
  //   var self = this;
  //   self.changed = false;

  //   self.columns = campaignCreateData.approvalReportColumns;
  //   if (campaignCreateData.defaults.columnsHidden) {
  //     self.columns.forEach(function(column) {
  //       column.visible = campaignCreateData.defaults.columnsHidden.indexOf(column.name) < 0;
  //     });
  //   }

  //   self.enabled = campaignCreateData.defaults.approvalEnabled || false;

  //   self.toggle = function() {
  //     self.enabled = !self.enabled;
  //   };

  //   self.recipients = campaignCreateData.defaults.recipients || [];
  //   self.addRecipient = function() {
  //     if (self.newRecipient && self.newRecipient.length > 0) {
  //       self.recipients.push(self.newRecipient);
  //       self.newRecipient = '';
  //     }
  //   };
  //   self.removeRecipient = function(index) {
  //     self.recipients.splice(index, 1);
  //   };

  //   self.settings = [{
  //     name: 'enable_profile_panels',
  //     text: 'Enable profile panels',
  //     value: true,
  //   }, {
  //     name: 'allow_comments',
  //     text: 'Allow Comments',
  //     value: false,
  //   }, {
  //     name: 'require_all_fields',
  //     text: 'Require all fields to be filled',
  //     value: true,
  //   }];

  //   self.watch = ['columns', 'enabled'];
  // }

  // function OutreachConfigurationSection(options) {
  //   var self = this;
  //   self.changed = false;

  //   if (campaignCreateData.defaults.outreachTemplate) {
  //     self.template = campaignCreateData.defaults.outreachTemplate.template;
  //     self.subject = campaignCreateData.defaults.outreachTemplate.subject;
  //   }

  //   if (!self.template || !self.template.length) {
  //     self.template = tsInvitationMessage.getBodyTemplate(null, {user: {name: 'Test User Name'}, context: context});
  //   }
  //   if (!self.subject || !self.subject.length) {
  //     self.subject = tsInvitationMessage.getSubjectTemplate(null, {user: {name: 'Test User Name'}, context: context});
  //   }

  //   self.uploader = options.uploader;

  //   self.getAttachments = function() {
  //     return self.uploader.queue.map(function(item) { return item.response; });
  //   };

  //   self.sendingTestEmail = false;
  //   self.sendTestEmail = function() {
  //     self.sendingTestEmail = true;
  //     $http({
  //       method: 'POST',
  //       url: campaignCreateData.sendTestEmailUrl,
  //       data: {
  //         template: tsInvitationMessage.getBody(self.template, {user: {name: 'Test User Name'}, context: context}),
  //         subject: tsInvitationMessage.getSubject(self.subject, {user: {name: 'Test User Name'}, context: context}),
  //         attachments: self.getAttachments(),
  //         send_mode: 'test',
  //         no_job: true,
  //       }
  //     }).success(function() {
  //       self.sendingTestEmail = false;
  //     }).error(function() {
  //       self.sendingTestEmail = false;
  //     });
  //   };

  //   self.watch = ['template', 'subject'];

  //   self.valid = function() {
  //     return true;
  //   };
  // }

  // function CampaignSpecificsSection() {
  //   var self = this;
  //   self.changed = false;

  //   self.coverImageChanged = 0;
  //   self.profileImageChanged = 0;

  //   self.deliverables = tsDeliverables.get(campaignCreateData.defaults.deliverables);
  //   self.description = campaignCreateData.defaults.description;
  //   self.whoShouldApply = campaignCreateData.defaults.whoShouldApply;
  //   self.mentionsRequired = campaignCreateData.defaults.mentionsRequired;
  //   self.hashtagsRequired = campaignCreateData.defaults.hashtagsRequired;
  //   self.details = campaignCreateData.defaults.details;
  //   self.dateStart = campaignCreateData.defaults.dateStart;
  //   self.dateEnd = campaignCreateData.defaults.dateEnd;
  //   self.postRequirements = campaignCreateData.defaults.postRequirements;
  //   self.dateRequirementsOn = campaignCreateData.defaults.info.date_requirements_on;
  //   self.coverImage = campaignCreateData.defaults.coverImage;
  //   self.profileImage = campaignCreateData.defaults.profileImage;

  //   self.watch = [
  //     'deliverables', 'description', 'whoShouldApply', 'mentionsRequired',
  //     'hashtagsRequired', 'details', 'dateStart', 'dateEnd', 'postRequirements',
  //     'dateRequirementsOn', 'coverImageChanged', 'profileImageChanged',
  //   ];

  //   self.valid = function() {
  //     return true;
  //   };
  // }

  // function ContractsSection() {
  //   var self = this;

  //   self.signing_contract_on = campaignCreateData.defaults.info.signing_contract_on;

  //   self.watch = ['signing_contract_on'];

  //   self.valid = function() {
  //     return true;
  //   };
  // }

  // function ProductSendingSection() {
  //   var self = this;

  //   self.options = {
  //     'sending_product_on': {
  //       value: campaignCreateData.defaults.info.sending_product_on,
  //       text: 'Will you be sending a physical product to the influencer?',
  //     },
  //   };

  //   // product settings
  //   // @TODO: put them in the same section
  //   self.productLinksOn = campaignCreateData.defaults.info.product_links_on;
  //   self.sameProductUrl = campaignCreateData.defaults.info.same_product_url;
  //   self.productUrl = campaignCreateData.defaults.info.product_url;
  //   self.doSelectUrl = campaignCreateData.defaults.info.do_select_url;
  //   self.restrictions = campaignCreateData.defaults.info.restrictions;
  //   self.bloggerAdditionalInfoOn = campaignCreateData.defaults.info.blogger_additional_info_on;
  //   self.bloggerAdditionalInfo = campaignCreateData.defaults.info.blogger_additional_info;

  //   self.watch = ['options', 'productLinksOn', 'sameProductUrl', 'productUrl',
  //     'doSelectUrl', 'restrictions', 'bloggerAdditionalInfoOn', 'bloggerAdditionalInfo',
  //   ];

  //   self.valid = function() {
  //     return true;
  //   };
  // }

  // function TrackingCodesSection() {
  //   var self = this;

  //   self.tracking_codes_on = campaignCreateData.defaults.info.tracking_codes_on;

  //   self.watch = ['tracking_codes_on'];

  //   self.valid = function() {
  //     return true;
  //   };
  // }

  // $scope.dateRangeModel = {
  //   startDate: null,
  //   endDate: null,
  // };

  // $scope.applyDateRange = function() {
  //   $scope.$apply(function() {
  //     $scope.campaignSpecificsSection.dateStart = $scope.dateRangeModel.startDate;
  //     $scope.campaignSpecificsSection.dateEnd = $scope.dateRangeModel.endDate;
  //   });
  // };

  // $scope.approvalReportSection = new ApprovalReportSection();

  // $scope.nameSection = new NameSection({formPromise: $scope.formPromises['nameSectionForm']});
  // $scope.outreachConfigurationSection = new OutreachConfigurationSection({uploader: $scope.uploader});
  // $scope.campaignSpecificsSection = new CampaignSpecificsSection();
  // $scope.contractsSection = new ContractsSection();
  // $scope.productSendingSection = new ProductSendingSection();
  // $scope.trackingCodesSection = new TrackingCodesSection();

  // $scope.sections = [
  //   $scope.nameSection, 
  //   $scope.outreachConfigurationSection,
  //   $scope.campaignSpecificsSection,
  //   $scope.contractsSection,
  //   $scope.productSendingSection,
  //   $scope.trackingCodesSection,
  // ];

  // angular.forEach($scope.sections, function(section, index) {
  //   angular.forEach(section.watch, function(watch) {
  //     $scope.$watch(function() {
  //       return section[watch];
  //     }, function(nv, ov) {
  //       if (!_.isEqual(nv, ov)) {
  //         section.changed = true;
  //         $scope.status[index]['is_completed'] = false;
  //         ctrl.bindWarning();
  //       }
  //     }, true);
  //   });
  // });

  // $timeout(function() {
  //   angular.forEach($scope.status, function (status, index) {
  //     if (status.live) {
  //       $scope.$watch(function () {
  //         return angular.element('#accordion_group_' + index).find('.panel-collapse').hasClass('collapse in');
  //         // return status.is_open;
  //       }, function (isOpen) {
  //         console.log(isOpen);
  //         if (isOpen) {
  //           angular.element('html, body').animate({
  //             scrollTop: angular.element('#accordion_group_' + index).offset().top - 20
  //           }, 500);
  //         }
  //       });
  //     }
  //   });
  // });

  // $scope.$on('$locationChangeStart', function(event, next, current) {
  //   var page = Number(_.last(next.split('/')));
  //   if (isNaN(page) || page < 0 || page > $scope.sections.length) {
  //     event.preventDefault();
  //     $scope.moveStep(0);
  //     return;
  //   }


  //   if ()



  //   if ($scope.status[$scope.current_step]['is_completed']) {
  //     // no need to save anything, just skip
  //     $scope.setCurrentStep(page);
  //   } else {
  //     if ($scope.canSave($scope.current_step)) {

  //     }
  //   }

  //   if ($scope.status[$scope.current_step]['is_completed'])

  // });

  // $scope.$on('$locationChangeSuccess', function() {
  //   var path = Number($location.path().substr(1));
  //   $timeout(function() {
  //     $scope.doMoveStep(path - 1);
  //   });
  // });

  // $scope.state = 'opened';
  // if (campaignCreateData.afterCreate) {
  //   $timeout(function() {
  //     $scope.save();
  //   });
  // }

  // if ($scope.campaignSpecificsSection.coverImage) {
  //   ctrl.set_cover_img($scope.campaignSpecificsSection.coverImage);
  // }

  // if ($scope.campaignSpecificsSection.profileImage) {
  //   ctrl.set_profile_img($scope.campaignSpecificsSection.profileImage);
  // }
}])


.directive('tableRow', ['$rootScope', function($rootScope) {
  return {
    restrict: 'A',
    scope: true,
    controller: function() {
    },
    controllerAs: 'tableRowCtrl',
    link: function(scope, iElement, iAttrs, ctrl) {
      // iElement.click(function() {
      //   if (ctrl.removed) {
      //     return false;
      //   }
      // });
      ctrl.removed = iAttrs.removed ? true : false;
      ctrl.removeRow = function() {
        // iElement.remove();
        ctrl.removed = true;
        $rootScope.$broadcast('tableRowRemoved');
      };

      ctrl.archiveRow = function() {
        ctrl.removed = true;
      };
    }
  };
}])


.directive('adminInfluencerRow', ['$http', function($http) {
  return {
    restrict: 'A',
    scope: true,
    link: function(scope, iElement, iAttrs) {
      scope.saveUrl = iAttrs.saveUrl;
      scope.influencerId = iAttrs.influencerId;

      scope.reset = function() {
        scope.status = {saving: false, error: false, dirty: false};   
        scope.toggledNumber = 0;
      }

      scope.done = function() {
        // save to back end
        scope.status.saving = true;
        $http.post(scope.saveUrl, {
          influencer: scope.influencerId,
          groups: scope.localGroups
        }).success(function() {
          scope.reset();
          angular.forEach(scope.localGroups, function(group) {
            group.toggled = false;
          });
          scope.originalGroups = angular.copy(scope.localGroups);
        }).error(function() {
          scope.reset();
          scope.status.error = true;
        });
      };

      scope.clear = function() {
        scope.reset();
        scope.localGroups = angular.copy(scope.originalGroups);
      };

      scope.reset();
    }
  };
}])


.directive('adminInfluencerGroups', [function() {
  return {
    restrict: 'A',
    template: ['<div class="admin-collection-list">',
                  '<span class="admin-collection"',
                    'ng-class="{selected: group.selected}"',
                    'ng-repeat="group in localGroups"',
                    'ng-click="toggleSelect(group)">',
                      '{{ group.name }}',
                  '</span>',
                '</div>'].join(''),
    link: function(scope, iElement, iAttrs) {
      var groups = angular.fromJson(iAttrs.groups);
      scope.originalGroups = angular.copy(groups);
      scope.localGroups = angular.copy(scope.originalGroups);
      scope.toggleSelect = function(group) {
        group.selected = !group.selected;
        if (!group.toggled) {
          scope.toggledNumber++;
        } else {
          scope.toggledNumber--;
        }
        group.toggled = !group.toggled;

        scope.status.dirty = (scope.toggledNumber > 0);
      };
    }
  };
}])


.directive('respondPopup', ['$http', '$rootScope', '$q', 'FileUploader', 'context', 'tsConfig',
  function ($http, $rootScope, $q, FileUploader, context, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/respond_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.subject = iAttrs.subject;
        scope.context = context;
        scope.$on('openRespondPopup', function (their_scope, id, brand_name, subject, thread, withLink) {
          scope.setBackgroundType(null);
          scope.map_id = id;
          scope.brand_name = brand_name;
          scope.subject = subject;
          scope.thread = thread;
          scope.hideCloseButton = false;
          scope.withLink = withLink;

          scope.sendOptions = {
            attachments: [],
          };

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

          scope.sendOptions.attachments = scope.uploader.queue;

          scope.open();
        });
        scope.$on("closeAllConversations", function(){
          if(scope.close)scope.close();
        });
        
        scope.send = function(options){
          if (options !== undefined && options !== null)
            angular.extend(scope.sendOptions, options);
          scope.hideCloseButton = false;
          scope.setState("sending");
          scope.setBackgroundType('black');
          $http({
            url: iAttrs.url,
            method: "POST",
            data: {
              template: scope.sendOptions.template,
              map_id: scope.map_id,
              subject: scope.subject,
              thread: scope.thread,
              send_mode: scope.sendOptions.sendMode,
              attachments: scope.formatAttachments(scope.sendOptions.attachments),
              with_link: scope.withLink ? '1' : null,
            }
          }).success(function(data){
            // if(data.status == "sent" || data.status == "queued"){
            scope.status = "Success";
            // }else if (data.status == "rejected"){
            //   if(data.reject_reason == "soft-bounce"){
            //     scope.status = "Email was sent but it couldn't be delivered. We will retry in few minutes!";
            //   }else{
            //     scope.status = "We couldn't send this message.";
            //   }
            // }
            // scope.setState("done");
            scope.close();
            $rootScope.$broadcast('refreshConversation', {id: scope.map_id});
          }).error(function(){
            scope.setState("error");
          });
        };
      }
    };
  }
])


.directive('conversationToggler', ['$rootScope', function($rootScope) {
  return {
    restrict: 'A',
    link: function(scope, iElement, iAttrs) {
      $rootScope.$on('conversationRefreshed', function(their_scope, options) {
        if (options.id == scope.mailboxId) {
          // scope.values.messagesCount = options.messagesCount;
          // scope.values.opensCount = options.opensCount;
          angular.extend(scope.values, options);
        }
      });
    }
  };
}])


.directive('bloggerConversation', [
  '$http',
  '$sce',
  '$rootScope',
  '$timeout',
  'context',
  'FileUploader',
  'tsUtils',
  'tsConfig',
  function ($http, $sce, $rootScope, $timeout, context, FileUploader, tsUtils, tsConfig) {
  return {
    restrict: 'A',
    replace: true,
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/conversation_element.html'),
    link: function (scope, iElement, iAttrs) {
      scope.context = context;
      scope.visible = false;
      scope.data = [];
      scope.refresh_timeout = null;
      scope.refresh_text = "Refresh";
      scope.unread = false;
      scope.offset = 0;

      scope.reset = function () {
        scope.visible = false;
        scope.offset = 0;
        scope.data.splice(scope.data.length);
      }

      if (scope.tableCtrl) {
        scope.visibleColumnsNumber = scope.tableCtrl.emptyHeaders() ? function() { return iAttrs.colsNumber; } : scope.tableCtrl.visibleColumnsNumber;
      }

      $rootScope.$on('refreshConversation', function(their_scope, options) {
        // if (options.id == iAttrs.map || options.mailboxId == iAttrs.map && scope.visible) {
        if (options.id == iAttrs.map || options.mailboxId == iAttrs.map) {
          scope.refresh();
        }
      });

      scope.$on('closeAllConversations', function(){
        scope.reset();
      });

      scope.$on('toggleConversation', function(their_scope, options) {
        var who = options.who;
        var id = options.id;
        var target = options.target;

        if (id == iAttrs.map) {
          if (!scope.visible) {
            $rootScope.$broadcast('closeAllConversations');
            scope.visible = true;
            scope.state = "loading";
            scope.who = who;
            scope.conversationRow = angular.element(target).closest('tr.mailbox');
            $timeout(function () {
              if (scope.conversationRow) {
                var height = _.reduce(_.map(scope.conversationRow.prevAll(), function (elem) { return angular.element(elem).outerHeight(); }), function (a, b) { return a + b; }, 0);
                angular.element('.table-body').animate({scrollTop: height}, 500);
              }
            }, 100);
            scope.refresh();
          } else {
            scope.reset();
          }
        }
      });

      scope.refresh = false;

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

      scope.sendOptions = {};
      scope.sendOptions.attachments = scope.uploader.queue;

      scope.resetSendOptions = function () {
        scope.sendOptions.template = null;
        scope.sendOptions.sendMode = null;
        scope.uploader.clearQueue();
      };

      scope.refresh = function(refreshOptions) {
        scope.setReplyFormVisible(false);
        scope.refresh_timeout = null;
        scope.refresh_text = "Refreshing...";
        scope.refreshing = true;

        if (refreshOptions && refreshOptions.appendData) {
        } else {
          scope.offset = 0;
          scope.data.splice(0, scope.data.length);
          scope.state = "loading";
        }

        $http({
          method: 'get',
          url: iAttrs.source,
          params: {
            offset: scope.offset,
          },
        }).success(function(response) {

          scope.refreshing = false;

          var data = response.data || [];

          scope.brandLogo = response.brandLogo;

          if (scope.visible) {
            if (scope.conversationRow.hasClass('unread-message')) {
              scope.conversationRow.removeClass('unread-message');
              $rootScope.$broadcast('unreadMessageOpened');
            }
            scope.state = "loaded";
            scope.refresh_text = "Refresh";
            for(var i=0; i<data.length; i++){
              var body = data[i].msg.body;
              body = body.replace(/=[0-9A-F][0-9A-F]/, function(a){return String.fromCharCode(parseInt(a.substr(1), 16))});
              body = body.split("\n");
              var quoted = false;
              var quoted_const = false;
              var quoted_random;
              var body_out = [];
              for(var j=0;j<body.length;j++){
                body[j] = body[j].replace(/^\s+/, "").replace(/<\s?br\s?\/?\s?>/, "");
                if(body[j][0] == ">"){
                  if(quoted === false){
                    quoted = body[j];
                    quoted_random = Math.ceil(Math.random()*100000)
                  }else{
                    quoted += "<br/>"+body[j];
                  }
                }else if(body[j][0] == "_"){
                  quoted_const = body.slice(j).join("<br/>");
                  quoted_random = Math.ceil(Math.random()*100000)
                  break;
                }else{
                  if(quoted === false){
                    if(body[j].length>0){
                      body[j] = body[j];
                      body_out.push(body[j]);
                    }
                  }else{
                    body_out.push("<div class='lt_gray_bg quoted quoted_"+quoted_random+"'>"+quoted+"</div>");
                    body_out.push("<div class='darkest_teal toggle_quoted' data-quoted='"+quoted_random+"'> -- Toggle quoted text -- </div>");
                    quoted = false;
                  }
                }
              }
              if(quoted_const !== false){
                body_out.push("<div class='lt_gray_bg quoted quoted_"+quoted_random+"'>"+quoted_const+"</div>");
                body_out.push("<div class='darkest_teal toggle_quoted' data-quoted='"+quoted_random+"'> -- Toggle quoted text -- </div>");
              }
              if(quoted !== false){
                body_out.push("<div class='lt_gray_bg quoted quoted_"+quoted_random+"'>"+quoted+"</div>");
                body_out.push("<div class='darkest_teal toggle_quoted' data-quoted='"+quoted_random+"'> -- Toggle quoted text -- </div>");
              }
              body = body_out.join("<br>");
              data[i].msg.body = $sce.trustAsHtml(body);
            }
            setTimeout(function() {
              $('.quoted').hide();
              $('.toggle_quoted').click(function(){
                var selector=".quoted_"+$(this).data("quoted");
                $(selector).toggle();
              });
            }, 10);
            // scope.data = data;
            // scope.data.concat(data);
            Array.prototype.push.apply(scope.data, data);
          }
          $rootScope.$broadcast('conversationRefreshed', response.mailboxData);
          scope.offset += response.limit;
          scope.canLoadMore = scope.offset < response.mailboxData.messagesCount;
        }).error(function () {
          scope.refreshing = false;
        });
      };

      scope.setReplyFormVisible = function (isVisible) {
        scope.showReplyForm = isVisible;

        if (isVisible) {
          scope.resetSendOptions();
        }
      };

      scope.respond = function(options) {
        scope.respondStatus = 'sending';
        options = options || {};
        var subject;
        if (scope.data && scope.data.length > 0 && scope.data[scope.data.length-1].msg.subject) {
          subject = "Re: "+scope.data[scope.data.length-1].msg.subject;
        } else {
          subject = "";
        }

        if (options !== undefined && options !== null)
            angular.extend(scope.sendOptions, options);

        $http({
          url: context.messageUrls.sendResponseUrl,
          method: "POST",
          data: {
            template: scope.sendOptions.template,
            map_id: iAttrs.mapId,
            subject: subject,
            thread: iAttrs.thread,
            send_mode: scope.sendOptions.sendMode,
            attachments: tsUtils.formatAttachments(scope.sendOptions.attachments),
            with_link: options.withLink ? '1' : null,
          }
        }).success(function(data){
          scope.respondStatus = "success";
          scope.setReplyFormVisible(false);
          $rootScope.$broadcast('refreshConversation', {id: iAttrs.mapId});
        }).error(function(){
          scope.respondStatus = "error";
        });

        // $rootScope.$broadcast('openRespondPopup', iAttrs.mapId, scope.who, subject, iAttrs.thread, options.with_link);
      };
      scope.do_refresh = function(){
          if(scope.refresh_timeout === null){
            scope.refresh_timeout = $timeout(scope.refresh, 500);
          }
      };

      scope.loadEvents = function (msg) {
        msg.loadingEvents = 'loading';
        $http({
          method: 'GET',
          url: msg.events_url,
        }).success(function(events) {
          msg.loadingEvents = 'loaded';
          msg.events = events;
        }).error(function() {
          msg.loadingEvents = 'error';
          console.log('error!');
        });
      };

      scope.close = function(){
        scope.visible = false;
        scope.$emit("closedConversation", iAttrs.map);
      };
    }
  };
}])


.controller('JobPostListCtrl', ['$scope', '$rootScope', function ($scope, $rootScope) {
  $scope.removePost = function(id){
    $("#post_"+id).fadeOut({complete: function(){
      $("#post_"+id).remove();
    }});
  };
  $scope.openCampaignCreatePopup = function() {
    $rootScope.$broadcast('openCampaignCreatePopup');
  };
}])


.directive('messages', ['$http', '$timeout', '$location', '$compile', function ($http, $timeout, $location, $compile) {
  return {
    restrict: 'A',
    link: function (scope, iElement, iAttrs) {

      scope.oldCampaignLinksEnabled = iAttrs.oldCampaignLinksEnabled !== undefined;

      scope.partialLoading = false;

      scope.displayMessage = function(msg) {
          scope.$broadcast("displayMessage", {message: msg});
      };

      scope.search = function() {
        if (scope.messagesData.searchQuery !== scope.messagesData.originalSearchQuery) {
          window.location.search = 'q=' + scope.messagesData.searchQuery;
        }
      };

      scope.nextSortDirection = function(header) {
        return scope.sortBy != header.value || scope.sortDirection == 1 ? 0 : 1;
      };

      scope.stagesList = iAttrs.stagesList !== undefined ? angular.fromJson(iAttrs.stagesList) : [];
      scope.headers = iAttrs.headers !== undefined ? angular.fromJson(iAttrs.headers) : [];
      scope.messagesData = {
        originalSearchQuery: iAttrs.searchQuery,
        searchQuery: iAttrs.searchQuery,
      };
      scope.sortDirection = parseInt(iAttrs.sortDirection);
      scope.sortBy = iAttrs.sortBy;

      scope.visibleColumns = function() {
        var visible = [];
        angular.forEach(scope.headers, function(value, key) {
          if (value.visible) {
            visible.push(key);
          }
        });
        return visible;
      };

      scope.visibleColumnsNumber = function() {
        return _.filter(scope.headers, function(header) { return header.visible; }).length;
      };

      scope.reloadPage = function() {
        var url = window.location.pathname + window.location.search;
        scope.partialLoading = true;  
        $http({
          method: 'GET',
          url: url,
          params: {
            only_partial: '1',
          }
        }).success(function(partial) {
          var content = $compile(partial)(scope);
          iElement.find('.messages_partial').remove();
          iElement.append(content);
          scope.partialLoading = false;
        });
      };

      scope.conv_visible = {};
      scope.toggleConversation = function(id, who, $event){
        scope.conv_visible[id] = !scope.conv_visible[id];
        scope.$broadcast('toggleConversation', id, who, $event.currentTarget || $event.srcElement);
      };
      scope.$on("closedConversation", function(their_scope, id){
        scope.conv_visible[id] = false;
      });

      scope.changeLocation = function(location) {
        window.location.replace(location);
      }

      var onLocationChange = function() {
        if ($location.path().length < 1)
          scope.showSection('all');
        var parts = $location.path().split('/').slice(-2);
        if (!isNaN(parts[1]))
          scope.showSection(parts[0], Number(parts[1]));
        else
          scope.showSection(parts[1]);
      };

      // scope.$on('$locationChangeSuccess', onLocationChange);

      scope.doOpenFavoritePopup = function(options){
        scope.$broadcast('openFavoritePopup', options);
      };

      scope.$on('doOpenFavoritePopup', function(theirScope, options) {
        scope.doOpenFavoritePopup(options);
      });

      scope.showSection = function(section, id) {
        scope.show_campaigns = false;
        scope.show_collections = false;
        $location.path('/' + section + (id ? '/' + id : ''));
        scope.$broadcast('closeAllConversations');
        if (section != 'all' && section != 'generic') {
          scope['show_' + section + 's'] = true;
        }
        iElement.find('.show_button').removeClass('selected');
        if (section == 'all') {
          iElement.find('.mailbox').show();
        } else {
          iElement.find('.mailbox').hide();
          iElement.find('.from_' + section + (id ? '_' + id : '')).show();
        }
        iElement.find('.show_' + section).addClass('selected');
        if (id) {
          $timeout(function() {
            iElement.find('.show_' + section + '_id_' + id).addClass('selected');
          });
        }
      };
    }
  };
}])


.directive('mailboxTableRow', ['$http', '$timeout', '$rootScope',
    'tsPlatformIconClasses', 'NotifyingService',
    function($http, $timeout, $rootScope, tsPlatformIconClasses, NotifyingService) {
  return {
    restrict: 'A',
    scope: true,
    controllerAs: 'mailboxTableRow',
    controller: function($scope) {
      var vm = this;

      vm.platformIcons = tsPlatformIconClasses.get;

      $scope.stages = {
        options: [],
        updating: false,
        update: function(selected) {
          $timeout(function() {
            $scope.stages.updating = true;
          }, 0);
          $http({
            url: $scope.updateUrl,
            method: 'POST',
            data: {
              modelName: 'MailProxy',
              id: $scope.mailboxId,
              values: {
                stage: selected.value
              }
            }
          }).success(function() {
            $scope.stages.selected = selected;
            $scope.stages.updating = false;
          }).error(function() {
            $scope.stages.updating = false;
            $scope.displayMessage("Failed to change the stage.");
          })
        },
        selected: null,
      };

      $scope.allValues = {};
    },
    link: function(scope, iElement, iAttrs, ctrl) {

      // iElement.click(function() {
      //   if (ctrl.removed) {
      //     return false;
      //   }
      // });

      ctrl.remove = function() {
        ctrl.removed = true;
        $rootScope.$broadcast('mailboxRowRemoved', {unread: iElement.hasClass('unread-message')});
      };

      ctrl.move = function(selected) {
        ctrl.remove();
        $rootScope.$broadcast('mailboxMoved', {stage: selected.value, unread: iElement.hasClass('unread-message')});
      };

      ctrl.setUnread = function (value) {
        if (value && !iElement.hasClass('unread-message')) {
          iElement.addClass('unread-message');
        } else if (!value && iElement.hasClass('unread-message')) {
          iElement.removeClass('unread-message');
        }
      };

      NotifyingService.subscribe(scope, 'table:removeAll', function(theirScope, options) {
        ctrl.removed = true;
      });

      scope.initialStage = iAttrs.initialStage !== undefined ? parseInt(iAttrs.initialStage) : null;
      scope.mailboxId = iAttrs.mailboxId !== undefined ? parseInt(iAttrs.mailboxId) : null;
      scope.contractId = iAttrs.contractId !== undefined ? parseInt(iAttrs.contractId) : null;
      scope.updateUrl = iAttrs.updateUrl;

      scope.$watch('stagesList', function(nv) {
        scope.stages.options = nv;
        scope.stages.selected = _.findWhere(nv, {value: scope.initialStage});
      });

      scope.openEditPopup = function(options) {
        $rootScope.$broadcast('openMailboxMoreInfoPopup', options);
      };
    }
  };
}])


.directive('propagateCellClass', ['$timeout', function ($timeout) {
  return {
    restrict: 'A',
    link: function (scope, iElement, iAttrs) {
      var classes = iAttrs.propagateCellClass.split(' ');
      var closest;
      $timeout(function () {
        closest = iElement.closest('td');
        scope.$watch(function () {
          return iElement.attr('class');
        }, function (nv) {
          for (var i in classes) {
            closest.removeClass(classes[i]);
          }
          closest.addClass(nv);
        });
      });
    }
  };
}])


.directive('mailboxTableCell', ['$http', '$rootScope', function($http, $rootScope) {
  return {
    restrict: 'A',
    scope: true,
    require: '^mailboxTableRow',
    link: function(scope, iElement, iAttrs, ctrl) {
      scope.sendUrl = iAttrs.sendUrl;

      scope.loading = false;
      scope.error = false;
      scope.sent = iAttrs.sent !== undefined;
      scope.status = {
        value: iAttrs.status,
        name: iAttrs.statusName,
        color: iAttrs.statusColor,
      };

      if (iAttrs.propagateStatus) {
        ctrl[iAttrs.propagateStatus] = scope.status;
      }

      iAttrs.$observe('propagateName', function() {
        if (iAttrs.propagateName) {
          ctrl[iAttrs.propagateName] = scope;
        }
      });

      scope.isDirty = function() {
        return scope.loading || scope.error;
      };

      scope.send = function() {
        scope.loading = true;
        scope.error = false;
        scope.sent = false;

        $http({
          method: 'POST',
          url: scope.sendUrl
        }).success(function(response) {
          if (response && response.data && response.data.status) {
            angular.extend(scope.status, response.data.status);
          }
          scope.loading = false;
          scope.error = false;
          scope.sent = true;
          $rootScope.$broadcast('refreshConversation', {id: scope.mailboxId});
        }).error(function() {
          scope.loading = false;
          scope.error = true;
        })
      };

      scope.$on('updateMailboxTableCell', function(their_scope, options) {
        if (options.mId === scope.mailboxId) {
          for (var i in scope.values) {
            scope.values[i] = options.values[i];
          }
        }
      });

      scope.$watch('values', function(nv) {
        angular.extend(scope.allValues, scope.values);
      }, true);

    }
  };
}])


.directive('messagesPageColumnsSelectPopover', ['$http', 'tsConfig', function($http, tsConfig) {
  return {
    restrict: 'A',
    replace: true,
    scope: true,
    templateUrl: tsConfig.wrapTemplate('js/angular/templates/job_posts/messagesPageColumnsSelectPopover.html'),
    link: function(scope, iElement, iAttrs) {
      scope.setUrl = iAttrs.setUrl;
      scope.loading = false;
      scope.withApply = iAttrs.withApply !== undefined;

      if (scope.withApply) {
        scope.headers = angular.copy(scope.tableCtrl.headers);
      } else {
        scope.headers = scope.tableCtrl.headers;
      }

      scope.toggleVisibility = function(header) {
        if (header) {
          header.visible = !header.visible;
          if (scope.withApply) {
            return;
          }
        }
        scope.loading = true;
        $http({
          method: 'POST',
          url: scope.setUrl,
          data: {
            columns: scope.tableCtrl.visibleColumns(scope.headers)
          }
        }).success(function() {
          if (scope.withApply) {
            scope.pageReload();
          } else {
            scope.loading = false;
          }
        }).error(function() {
          scope.loading = false;
        });
      };

      scope.updateNano = function() {
        console.log('update nano');
        setTimeout(function() {
          $(".nano").nanoScroller({alwaysVisible: true});
          $(".nano").nanoScroller({ scroll: 'top' });
        }, 100);
      };
    }
  };
}])


.directive('deliverablesForm', ['tsPlatformIconClasses', function(tsPlatformIconClasses) {
  return {
    restrict: 'A',
    replace: true,
    scope: {
      deliverables: '=',
      // range: '=',
    },
    template: [
      '<div>',
        '<div class="triangle"></div>',
        '<div class="ns-popover-tooltip">',
          '<div class="deliverables">',
            '<div class="deliverable popover_form" ng-class="platformWrappers(name)" ng-repeat="(name, data) in deliverables">',
              '<span class="popover_icon" ng-class="platformIcons(name)"></span>',
              '<span class="popover_label">{{ name | capitalize }}</span>',
              '<select ng-options="number for number in range" ng-model="data.value"></select>',
              // '<div class="order_select" dropdown-select="range" dropdown-model="data.value"></div>',
              // '<input type="number" max="10" />',
            '</div>',
          '</div>',
        '</div>',
      '</div>'].join(''),
    controller: function($scope) {
      $scope.platformIcons = tsPlatformIconClasses.get;
      $scope.platformWrappers = tsPlatformIconClasses.getBase;
      if (!$scope.range) {
        $scope.range = _.range(0, 11);
        // $scope.range = _.range(0, 11).map(function(number) { return {value: number, text: number}; });
      }
    }
  };
}])


.directive('changeAssociationsPopup', ['$http', '$rootScope', 'tsConfig',
  function ($http, $rootScope, tsConfig) {
    return {
      restrict: 'A',
      scope: true,
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/lightboxes/content/change_associations_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.$on('openChangeAssociationsPopup', function (their_scope) {
          scope.open();
          scope.load();
        });
        scope.currentUpdate = function(selected) {
          if (selected !== undefined)
            scope.current = selected;
        };
        scope.load = function(){
          $http.get(iAttrs.url)
            .success(function (data) {
              scope.current = data.current;
              scope.all = data.all;
              scope.setState('loaded');
            });
        };
        scope.save = function(){
          scope.setState('saving');
          $http.post(iAttrs.url, scope.current)
            .success(function () {
              window.location.reload();
            });
        };
      }
    };
  }
])

    /*
.directive('donout', function(){
  return {
    restrict: 'E',
    scope: {data:'='},
    link: function(scope, iElement, iAttrs, ctrl) {
      var el = iElement[0];
      var width=50,
        height=50,
        radius=Math.min(width,height)/2;

      var color=d3.scale.ordinal().range(["rgb(166,60,48)", "rgb(207,207,207)"]);

      var arc=d3.svg.arc()
        .outerRadius(radius)
        .innerRadius(radius-15);

      scope.$watch("data", function(data){
        if(!data){ return; }

        var countArr=[];

        countArr.push(data['totalPostsGone']);
        countArr.push(data['totalPostsRequired'] - data['totalPostsGone']);

        var pie=d3.layout.pie()
          .sort(null)
          .value(function(d){return d});

        var svg=d3.select(el).append("svg")
          .attr("width",width)
          .attr("height",height)
          .append("g")
          .attr("transform","translate("+width/2+","+height/2+")");

        var g=svg.selectAll(".arc")
          .data(pie(countArr))
          .enter().append("g")
          .attr("class","arc");

        g.append("path")
          .attr("d",arc)
          .style("fill",function(d,i){return color(i);});

        g.append("text")
          .attr("transform",function(d){return "translate("+arc.centroid(d)+")";})
          .attr("dy",".35em")
          .style("text-anchor","middle")
          .text(function(d,i){return countArr[i]});

      }, true);
    }
  }
})
*/
.directive('campaignOverview', [
  '$q',
  '$http',
  '$timeout',
  '$filter',
  'Restangular',
  'context',
  'tsPlatformIconClasses',
  'd3',
  function($q, $http, $timeout, $filter, Restangular, context, tsPlatformIconClasses, d3) {
  return {
    restrict: 'A',
    controller: function() {},
    controllerAs: 'campaignOverviewCtrl',
    link: function(scope, iElement, iAttrs, ctrl) {

      scope.context = context;

      ctrl.campaignId = parseInt(iAttrs.campaignId);
      
      function buildChart(chart) {
        var data = chart.data;
        // for (var i = data.length - 2; i >= 0; i--) {
        //   for (var key in data[i]) {
        //     var value = data[i];
        //     if (!isNaN(value[key]) && value[key] == 0) {
        //       value[key] = data[i + 1][key];
        //     }
        //   }
        // }

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
            chart.loaded = true;
          } catch(e) {console.log('1', e);};
        }, 400);
      };

      function CampaignMap() {
        var campaignMap = this;
        var bubbles = null;

        this.map = null;
        this.loading = false;
        this.data = null;
        this.buildMap = function() {
          // console.log('building map');
          var paletteScale = d3.scale.linear()
            .domain([campaignMap.data.state_stats.lowest, campaignMap.data.state_stats.highest])
            .range(["#7ff8ed","#7a2be7","#88b2ff","#ef5f30"]);
          var dataset = {};
          for (var state in campaignMap.data.state_stats.stats) {
            dataset[state] = {fillColor: paletteScale(campaignMap.data.state_stats.stats[state])};
          }

          var projectionBuilder = (campaignMap.data.settings.projection ? function(element) {
            var projection = d3.geo.mercator()
              .center([campaignMap.data.settings.center.lat, campaignMap.data.settings.center.long])
              .scale(campaignMap.data.settings.scale);
              // .translate([element.offsetWidth / 2, 2 * element.offsetHeight / 3]);

            var path = d3.geo.path().projection(projection);
            return {path: path, projection: projection};
          } : undefined);

          var datamapConfig = {
            element: document.getElementById('campaignMapContainer'),
            geographyConfig: {
                popupOnHover: true,
                highlightOnHover: false,
                borderWidth: 1,
                borderColor: '#c4c4c4'
            },
            responsive: true,
            scope: 'world',
            // scope: 'usa',
            fills: {
              city: 'red',
              lowest: '#7ff8ed',
              low: '#7a2be7',
              middle: '#88b2ff',
              high: '#ef5f30',
              defaultFill: 'white'
            },
            bubblesConfig: {
              borderWidth: 1,
              borderColor: '#fff',
              popupOnHover: true,
              highlightOnHover: true,
              highlightFillColor: '#FC8D59',
              highlightBorderColor: 'rgba(250, 15, 160, 0.2)',
              highlightBorderWidth: 2,
              highlightBorderOpacity: 1,
              highlightFillOpacity: 0.85,
              exitDelay: 100,
            },
            data: dataset,
          };

          if (projectionBuilder) {
            datamapConfig.setProjection = projectionBuilder;
          }

          campaignMap.map = new Datamap(datamapConfig);

          campaignMap.placeBubbles();
          // campaignMap.map.legend();

          window.addEventListener('resize', function() {
            campaignMap.map.resize();
          });
        };

        this.placeBubbles = function() {
          var bubbles = [];
          campaignMap.data.bubbles.forEach(function(location) {
            bubbles.push({
              radius: 5 + location.influencers.length * 2,
              fillKey: 'city',
              latitude: location.latitude,
              longitude: location.longitude,
              influencers: location.influencers,
              location: location.location,
            });
          });
          campaignMap.map.bubbles(bubbles, {
            animate: false,
            popupTemplate: function(geo, data) {
              var infs = ['<div class="hoverinfo">'];
              if (data.location.city) {
                infs.push('<strong>' + data.location.city + ' (' + data.influencers.length + ')' + '</strong><br />');
              }
              data.influencers.forEach(function(inf) {
                infs.push(inf.name + ', <span style="font-style: italic; font-weight: bold;">' + inf.blogname + '</span><br />');
              });
              infs.push('</div>');
              return infs.join('');
            }
          });
        };

        this.loadData = function() {
          console.log('loading data');
          campaignMap.loading = true;
          $http({
            method: 'GET',
            url: '',
            params: {
              influencer_locations: 1,
            }
          }).success(function(response) {
            campaignMap.loading = false;
            campaignMap.data = response.data;
            console.log("campaignMap::", campaignMap.data);
            $timeout(campaignMap.buildMap, 400);
          });
        };

        this.loadData();
      }

      function numberWithCommas(x) {
        return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      }

      function TopInfluencers() {
        var topInfluencers = this;

        this.loading = false;
        this.campaignId = Number(iAttrs.campaignId);

        this.loadData = function() {
          topInfluencers.loading = true;
          $http({
            method: 'GET',
            url: '',
            params: {
              top_influencers: 1,
            }
          }).success(function(response) {
            topInfluencers.loading = false;
            topInfluencers.list = response.data.top;
            topInfluencers.totalCount = response.data.total_count;
            console.log("topInfluencers::::", topInfluencers.list);
          });
        };

        this.loadData();
      }

      function InstagramPhotos() {
        var self = this;

        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          $http({
            method: 'GET',
            url: '',
            params: {
              instagram_photos: 1,
            }
          }).success(function(response) {
            console.log("instagram:::", response.data);
            self.loading = false;
            self.list1=[];
            self.list2=[];
            var j=0;
            if(response.data.instagram_photos.length < 20){
              for( var i=0; i< response.data.instagram_photos.length; i++){
                if(i<10){
                  self.list1[i]=response.data.instagram_photos[i];
                }else{
                  self.list2[j]=response.data.instagram_photos[i];
                  j++;
                }
              }
            }else{
              for( var i=0; i< 20; i++){
                if(i<10){
                  self.list1[i]=response.data.instagram_photos[i];
                }else{
                  self.list2[j]=response.data.instagram_photos[i];
                  j++;
                }
              }
            }
          });
        };

        this.loadData();
      }

      function TopPosts() {
        var self = this;

        self.itemOptions = {
          nolabel: false,
          noheader: false,
          skipSocial: true,
          bookmarks: false,
          // debug: iAttrs.debug !== undefined,
          ugcView: true,
          showButtons: function() {
            if (context.visitorHasBrand && !this.ugcView) {
              return !this.noheader || iAttrs.showButtons !== undefined;
            }
            return false;
          },
          showSocials: function() {
            return !(this.noheader || this.ugcView);
          },
          showSocialLabel: function() {
            return !this.nolabel && !this.showSocials();
          },
        };

        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          $http({
            method: 'GET',
            url: '',
            params: {
              top_posts: 1,
            }
          }).success(function(response) {
            self.loading = false;
            self.list = response.data.top;
            console.log("topposts::::::", self.list);
          });
        };

        this.loadData();
      }

      function PostStats() {
        var self = this;

        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          $http({
            method: 'GET',
            url: '',
            params: {
              post_stats: 1,
            }
          }).success(function(response) {
            self.loading = false;
            self.counts = response.data.counts;
            self.postCounts = response.data.post_counts;
            // self.genericCounts = response.data.generic_counts;
          });
        };

        this.loadData();
      }

      function PostImpressions() {
        var self = this;

        var URLS = [
          'total_blog_impressions', 'total_potential_social_impressions',
          'total_potential_unique_social_impressions', 'all_impressions',
        ];

        var data = {};
        self.data = {};

        self.loading = false;

        self.loadData = function() {
          var promises = [];

          self.loading = true;
          URLS.forEach(function(url) {
            promises.push(Restangular
              .one('campaigns', ctrl.campaignId)
              .customGET(url)
              .then(function(response) {
                data[url] = response;
              }));
          });

          $q.all(promises)
            .then(function() {
              self.loading = false;
              self.data['PostImpressions'] = data;
            });
          console.log("postimpressions:", self.data['PostImpressions']);
        };

        self.loadData();
      }

      /* PlatformStatus *///////////////////////////////////////////////////////////////////////////////////////
      /* PlatformStatus *///////////////////////////////////////////////////////////////////////////////////////////////////////////////
      /* PlatformStatus *///////////////////////////////////////////////////////////////////////////////////////////////////////////////
      /* PlatformStatus *///////////////////////////////////////////////////////////////////////////////////////////////////////////////

      var blockTitle = ['Blog', 'Instagram', 'Facebook', 'Twitter', 'Pinterest'];
      var iconTitle = ['icon-letter_quotes3', 'icon-social_instagram', 'icon-social_facebook', 'icon-social_twitter', 'icon-social_pinterest'];
      var blockColor = ['#aaaaaa', '#fcc862', '#5b99fc', '#6fe2e5', '#f85f71'];
      var blockColor1 = ['#cecece', '#fddb9a', '#9abffa', '#aef4f6', '#faa1ab'];

      function BlogStatus() {
        var self = this;
        var i = 0;
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('platform_counts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.loading = false;
                self.data =[];
                self.data[0] = response;
                self.data[0].idNum = i;
                self.data[0].iconTitle = iconTitle[i];
                self.data[0].blockColor = blockColor[i];
                self.data[0].blockColor1 = blockColor1[i];
                self.data[0].percent = Math.round( response.totalPostsGone * 100 / response.totalPostsRequired );
                self.data[0].percentAudience = Math.round( response.audience*100 );
                self.data[0].totalPostsGone = numberWithCommas(response.totalPostsGone);
                self.data[0].totalPostsRequired = numberWithCommas(response.totalPostsRequired);
                self.data[0].totalImpressions = numberWithCommas(response.totalImpressions);
                self.data[0].repinsCount = numberWithCommas(response.repinsCount);
                self.data[0].facebookCount = numberWithCommas(response.facebookCount);
                self.data[0].gplusCount = numberWithCommas(response.gplusCount);
                self.data[0].commentsCount = numberWithCommas(response.commentsCount);
                self.data[0].totalClicks = numberWithCommas(response.totalClicks);
                self.data[0].totalEngagements = numberWithCommas(response.totalEngagements);
                console.log("row--one platform_counts::", i, self.data);
              });
        };
        this.loadData();
      }

      function InstagramStatus() {
        var self = this;
        var i = 1;
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('platform_counts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.loading = false;
                self.data=[];
                self.data[0] = response;
                self.data[0].idNum = i;
                self.data[0].iconTitle = iconTitle[i];
                self.data[0].blockColor = blockColor[i];
                self.data[0].blockColor1 = blockColor1[i];
                self.data[0].percent = Math.round( response.totalPostsGone * 100 / response.totalPostsRequired );
                self.data[0].percentAudience = Math.round( response.audience*100 );
                self.data[0].totalPostsGone = numberWithCommas(response.totalPostsGone);
                self.data[0].totalPostsRequired = numberWithCommas(response.totalPostsRequired);
                self.data[0].totalImpressions = numberWithCommas(response.totalImpressions);
                self.data[0].commentsCount = numberWithCommas(response.commentsCount);
                self.data[0].likesCount = numberWithCommas(response.likesCount);
                self.data[0].totalEngagements = numberWithCommas(response.totalEngagements);
                console.log("row--one platform_counts::", i, self.data);
              });
        };
        this.loadData();
      }
      function FacebookStatus() {
        var self = this;
        var i = 2;
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('platform_counts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.loading = false;
                self.data=[];
                self.data[0] = response;
                self.data[0].idNum = i;
                self.data[0].iconTitle = iconTitle[i];
                self.data[0].blockColor = blockColor[i];
                self.data[0].blockColor1 = blockColor1[i];
                self.data[0].percent = Math.round( response.totalPostsGone * 100 / response.totalPostsRequired );
                self.data[0].totalPostsGone = numberWithCommas(response.totalPostsGone);
                self.data[0].totalPostsRequired = numberWithCommas(response.totalPostsRequired);
                self.data[0].totalImpressions = numberWithCommas(response.totalImpressions);
                console.log("row--one platform_counts::", i, self.data);
              });
        };
        this.loadData();
      }
      function TwitterStatus() {
        var self = this;
        var i = 3;
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('platform_counts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.loading = false;
                self.data = [];
                self.data[0] = response;
                self.data[0].idNum = i;
                self.data[0].iconTitle = iconTitle[i];
                self.data[0].blockColor = blockColor[i];
                self.data[0].blockColor1 = blockColor1[i];
                self.data[0].percent = Math.round( response.totalPostsGone * 100 / response.totalPostsRequired );
                self.data[0].totalPostsGone = numberWithCommas(response.totalPostsGone);
                self.data[0].totalPostsRequired = numberWithCommas(response.totalPostsRequired);
                self.data[0].totalImpressions = numberWithCommas(response.totalImpressions);
                console.log("row--one platform_counts::", i, self.data);
              });
        };
        this.loadData();
      }
      function PinterestStatus() {
        var self = this;
        var i = 4;
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('platform_counts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.loading = false;
                self.data = [];
                self.data[0] = response;
                self.data[0].idNum = i;
                self.data[0].iconTitle = iconTitle[i];
                self.data[0].blockColor = blockColor[i];
                self.data[0].blockColor1 = blockColor1[i];
                self.data[0].percent = Math.round( response.totalPostsGone * 100 / response.totalPostsRequired );
                self.data[0].totalPostsGone = numberWithCommas(response.totalPostsGone);
                self.data[0].totalPostsRequired = numberWithCommas(response.totalPostsRequired);
                self.data[0].totalImpressions = numberWithCommas(response.totalImpressions);
                console.log("row--one platform_counts::", i, self.data);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////


      /* randomInfluencers *///////////////////////////////////////////////////////////////////////////////////////
      /* randomInfluencers *///////////////////////////////////////////////////////////////////////////////////////
      /* randomInfluencers *///////////////////////////////////////////////////////////////////////////////////////
      /* randomInfluencers *///////////////////////////////////////////////////////////////////////////////////////

      function BlogRandomInfluencers() {
        var self = this;
        var i = 0;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('random_influencers', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.data = response.influencers;
                console.log("row--one randomInfluencers::", i, self.data);
              });
        };
        this.loadData();
      }
      function InstagramRandomInfluencers() {
        var self = this;
        var i = 1;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('random_influencers', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.data = response.influencers;
                console.log("row--one randomInfluencers::", i, self.data);
              });
        };
        this.loadData();
      }
      function FacebookRandomInfluencers() {
        var self = this;
        var i = 2;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('random_influencers', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.data = response.influencers;
                console.log("row--one randomInfluencers::", i, self.data);
              });
        };
        this.loadData();
      }
      function TwitterRandomInfluencers() {
        var self = this;
        var i = 3;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('random_influencers', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.data = response.influencers;
                console.log("row--one randomInfluencers::", i, self.data);
              });
        };
        this.loadData();
      }
      function PinterestRandomInfluencers() {
        var self = this;
        var i = 4;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('random_influencers', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.data = response.influencers;
                console.log("row--one randomInfluencers::", i, self.data);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////

      /* topPosts, lowerPosts *///////////////////////////////////////////////////////////////////////////////////////
      /* topPosts, lowerPosts *///////////////////////////////////////////////////////////////////////////////////////
      /* topPosts, lowerPosts *///////////////////////////////////////////////////////////////////////////////////////
      /* topPosts, lowerPosts *///////////////////////////////////////////////////////////////////////////////////////

      function BlogTLPosts() {
        var self = this;
        var i = 0;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('top_posts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.lowerPosts = response.lowerPosts;
                self.topPosts = response.topPosts;
                console.log("row--three top_posts::", i, self);
              });
        };
        this.loadData();
      }
      function InstagramTLPosts() {
        var self = this;
        var i = 1;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('top_posts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.lowerPosts = response.lowerPosts;
                self.topPosts = response.topPosts;
                console.log("row--three top_posts::", i, self);
              });
        };
        this.loadData();
      }
      function FacebookTLPosts() {
        var self = this;
        var i = 2;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('top_posts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.lowerPosts = response.lowerPosts;
                self.topPosts = response.topPosts;
                console.log("row--three top_posts::", i, self);
              });
        };
        this.loadData();
      }
      function TwitterTLPosts() {
        var self = this;
        var i = 3;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('top_posts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.lowerPosts = response.lowerPosts;
                self.topPosts = response.topPosts;
                console.log("row--three top_posts::", i, self);
              });
        };
        this.loadData();
      }
      function PinterestTLPosts() {
        var self = this;
        var i = 4;

        this.loadData = function() {
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('top_posts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.lowerPosts = response.lowerPosts;
                self.topPosts = response.topPosts;
                console.log("row--three top_posts::", i, self);
              });
        };
        this.loadData();
      }
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////

      /* PostSamples *///////////////////////////////////////////////////////////////////////////////////////
      /* PostSamples *///////////////////////////////////////////////////////////////////////////////////////
      /* PostSamples *///////////////////////////////////////////////////////////////////////////////////////
      /* PostSamples *///////////////////////////////////////////////////////////////////////////////////////

      function BlogPostSamples() {
        var self = this;
        this.loading = false;
        var i = 0;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('post_samples', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.loading = false;
                self.posts = response.posts;
                console.log("row--fourth BlogPostSamples::", i, self.posts);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////


      /* top influencers by share counts *///////////////////////////////////////////////////////////////////////////////////////
      /* top influencers by share counts *///////////////////////////////////////////////////////////////////////////////////////
      /* top influencers by share counts *///////////////////////////////////////////////////////////////////////////////////////
      /* top influencers by share counts *///////////////////////////////////////////////////////////////////////////////////////

      function BlogTopInfluencers() {
        var self = this;
        this.loading = false;
        var i = 0;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('top_influencers_by_share_counts', { platform_name: blockTitle[i] })
              .then(function(response) {
                self.loading = false;
                self.Gplus = response.influencers.Gplus;
                self.Twitter = response.influencers.Twitter;
                self.Pinterest = response.influencers.Pinterest;
                console.log("row--fourth BlogTopInfluencers::", i, self);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////

      /* Posting time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Posting time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Posting time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Posting time series *///////////////////////////////////////////////////////////////////////////////////////

      function PlatformPostsTimeSeries() {
        var self = this;
        this.loading = false;
        var _data=[];
        for(var i=0; i<5; i++){
          _data[i] = [];
        }

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('posting_time_series')
              .then(function(response) {
                self.loading = false;
                self.minDate = response.timeSeries[0].postDate.substring(0, 10);
                self.maxDate = response.timeSeries[response.timeSeries.length-1].postDate.substring(0, 10);
                self.minMaxDate = [response.timeSeries[0].postDate.substring(0, 10),response.timeSeries[response.timeSeries.length-1].postDate.substring(0, 10)].toString();
                for(var i=0; i< response.timeSeries.length; i++){
                  if(response.timeSeries[i].platformName == 'Blog'){
                    _data[0].push(response.timeSeries[i]);
                  }
                  else if(response.timeSeries[i].platformName == 'Instagram'){
                    _data[1].push(response.timeSeries[i]);
                  }
                  else if(response.timeSeries[i].platformName == 'Facebook'){
                    _data[2].push(response.timeSeries[i]);
                  }
                  else if(response.timeSeries[i].platformName == 'Twitter'){
                    _data[3].push(response.timeSeries[i]);
                  }
                  else if(response.timeSeries[i].platformName == 'Pinterest'){
                    _data[4].push(response.timeSeries[i]);
                  }
                }

                self.data = [];

                for(var i=0; i< 5; i++){
                  var temp = [];
                  var str = {};
                  var xDate = [];
                  var yValue = [];

                  for(var j=0; j < _data[i].length; j++){
                    temp[j] = _data[i][j].postDate;

                    if(!str[temp[j].substring(0, 10)]) {
                      str[temp[j].substring(0, 10)] = 0;
                    }
                    str[temp[j].substring(0, 10)] ++;
                  }
                  xDate = Object.keys(str);
                  for(var k=0; k< xDate.length; k++){
                    yValue[k] = str[xDate[k]];
                  }
                  var _json = {
                    idNum: i,
                    blockColor: blockColor[i],
                    platformName: _data[i][0].platformName,
                    xDate: xDate.toString(),
                    yValue: yValue.toString()
                  };
                  self.data.push(_json);
                }

                console.log("platform_series", self);
              });
        };

        this.loadData();
      }
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////

      /* Impressions time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Impressions time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Impressions time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Impressions time series *///////////////////////////////////////////////////////////////////////////////////////

      function ImpressionsTimeSeries() {
        var self = this;
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('impressions_time_series')
              .then(function(response) {
                self.loading = false;
                self.data = [];
                self.data[0]={};
                var _count = [],_date = [];
                self.totalImpressions = numberWithCommas(response.totalImpressions);
                for(var i= 0; i<response.timeSeries.length; i++){
                  _count.push(response.timeSeries[i].count);
                  _date.push(response.timeSeries[i].date);
                }
                self.data[0].count = _count.toString();
                self.data[0].date = _date.toString();
                console.log("row--fourth ImpressionsTimeSeries::", i, self.data);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////


      /* Total Engagements *///////////////////////////////////////////////////////////////////////////////////////
      /* Total Engagements *///////////////////////////////////////////////////////////////////////////////////////
      /* Total Engagements *///////////////////////////////////////////////////////////////////////////////////////
      /* Total Engagements *///////////////////////////////////////////////////////////////////////////////////////

      function TotalEngagements() {
        var self = this;
        this.loading = true;
        var count1 =[],date1 =[];

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('cumulative_engagement_time_series')
              .then(function(response) {
                var _count = [],_date = [];
                for (var j = 0; j < response.length; j++) {
                  _count.push(response[j].count);
                  _date.push(response[j].date);
                }
                self.data = [];
                self.data[0] = {};
                self.data[0].date = _date.toString();
                self.data[0].count = _count.toString();
                self.data[0].minDate=response[0].date;
                self.data[0].maxDate=response[response.length-1].date;
                self.loading = false;
                console.log("Total Engagements:::", self.data[0]);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////


      /* Engagement time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Engagement time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Engagement time series *///////////////////////////////////////////////////////////////////////////////////////
      /* Engagement time series *///////////////////////////////////////////////////////////////////////////////////////

      // function for getting week from date

      Date.prototype.getweek = function() {
        var onejan = new Date(this.getFullYear(), 0, 1);
        return Math.ceil(((( this-onejan ) / 86400000 ) + onejan.getDay() + 1 ) / 7 );
      };

      // function for building the scatter chart

      var buildScatterChart = function(config){
        var chart = c3.generate({
          bindto: config.elementId,
          data: {
            x: 'x',
            xs: {
              data: 'x'
            },
            json: config.jsonData,
            type: 'scatter',
            colors: {
              data: config.colors
            }
          },
          legend: {
            show: false
          },
          size: {
            height: config.height,
            width: config.width
          },
          point: {
            show: true,
            r: function(d) {
              // console.log('d:::', d);
              return  config.values[d.index];
            },
            focus: {
              expand: {
                enabled: false
              }
            }
          },
          axis: {
            x: {
              show: config.xShow,
              type: 'timeseries',
              tick: {
                format: function(x) {
                  var month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

                  return (month[x.getMonth()]);
                },
                outer: false,
                fit: true,
                values: ['2016-01-01', '2016-02-01', '2016-03-01', '2016-04-01', '2016-05-01', '2016-06-01', '2016-07-01', '2016-08-01', '2016-09-01', '2016-10-01', '2016-11-01', '2016-12-01']
              },
              max: '2016-12-31',
              min: '2016-01-01'
            },
            y: {
              show: false,
              max: 20,
              min: -20
            }
          },
          tooltip: {
            show: false
          }

        });
      };

      var EngagementTimeline = function(response){
        var self ={};
        self.xDate = [], self.yValue = [], self.rValue = [];
        var zValue = [];
        var xWeekNum = 0;
        var xDay = 0;
        var weekData = {};

        for(var j=0; j < response.length; j++) {
          self.xDate[j] = response[j].date;
          zValue[j] = response[j].count;

          var a = new Date(self.xDate[j]);
          xWeekNum = a.getweek();
          xDay = a.getDay();

          if(!weekData[xWeekNum]){
            weekData[xWeekNum] = {};
            weekData[xWeekNum].value = zValue[j];
            weekData[xWeekNum].date = self.xDate[j];
          }else{
            weekData[xWeekNum].value = weekData[xWeekNum].value + zValue[j];
          }
          if(xDay == 3){
            weekData[xWeekNum].date = self.xDate[j];
          }
        }
        zValue =[], self.xDate = [];

        for(var k=0;k<54; k++){
          if(!weekData[k+1]){
            self.xDate[k] = null;
            zValue[k] = 0;
          }else{
            self.xDate[k] = weekData[k+1].date;
            if(weekData[k+1].value == 0){
              zValue[k] = 0;
            }
            else if( 0 < weekData[k+1].value && weekData[k+1].value <= 100 ){
              zValue[k] = 2;
            }
            else if( 100 < weekData[k+1].value && weekData[k+1].value <= 200 ){
              zValue[k] = 4;
            }
            else if( 200 < weekData[k+1].value && weekData[k+1].value <= 300 ){
              zValue[k] = 6;
            }
            else if( 300 < weekData[k+1].value && weekData[k+1].value <= 500 ){
              zValue[k] = 8;
            }
            else if( 500 < weekData[k+1].value ){
              zValue[k] = 10;
            }else{
              zValue[k] = 0;
            }
          }
          if(zValue[k]!=0){
            self.rValue.push(zValue[k]);
          }
          self.yValue[k] = 0;
        }
        return self;
      };

      function BlogEngagementTimeline() {
        var self = this;
        var config = [];
        this.loading = true;
        var i=0;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('engagement_time_series', { platform_name: blockTitle[i] })
              .then(function(response) {

                var _count = [],_date = [];
                for(var j= 0; j<response.length; j++){
                  _count.push(response[j].count);
                  _date.push(response[j].date);
                }
                self.count = _count.toString();
                self.date = _date.toString();

                var eTL = EngagementTimeline(response);

                config[i] = {
                  elementId: '#BbChartBlog',
                  jsonData: {
                    'data': eTL.yValue,
                    'x': eTL.xDate
                  },
                  values: eTL.rValue,
                  colors: blockColor[i],
                  height: 50,
                  width: 1000,
                  xShow: false
                };
                buildScatterChart(config[i]);
                self.loading = false;
                console.log("Blogengagement_time_series", response, config);
              });
        };
        this.loadData();
      }
      function InstagramEngagementTimeline() {
        var self = this;
        var config = [];
        this.loading = true;
        var i=1;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('engagement_time_series', { platform_name: blockTitle[i] })
              .then(function(response) {

                var _count = [],_date = [];
                for(var j= 0; j<response.length; j++){
                  _count.push(response[j].count);
                  _date.push(response[j].date);
                }
                self.count = _count.toString();
                self.date = _date.toString();

                var eTL = EngagementTimeline(response);

                config[i] = {
                  elementId: '#BbChartInstagram',
                  jsonData: {
                    'data': eTL.yValue,
                    'x': eTL.xDate
                  },
                  values: eTL.rValue,
                  colors: blockColor[i],
                  height: 50,
                  width: 1000,
                  xShow: false
                };
                buildScatterChart(config[i]);
                self.loading = false;
                console.log("Insta-engagement_time_series", response, config);
              });
        };
        this.loadData();
      }
      function FacebookEngagementTimeline() {
        var self = this;
        var config = [];
        this.loading = true;
        var i=2;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('engagement_time_series', { platform_name: blockTitle[i] })
              .then(function(response) {

                var _count = [],_date = [];
                for(var j= 0; j<response.length; j++){
                  _count.push(response[j].count);
                  _date.push(response[j].date);
                }
                self.count = _count.toString();
                self.date = _date.toString();

                var eTL = EngagementTimeline(response);

                config[i] = {
                  elementId: '#BbChartFacebook',
                  jsonData: {
                    'data': eTL.yValue,
                    'x': eTL.xDate
                  },
                  values: eTL.rValue,
                  colors: blockColor[i],
                  height: 50,
                  width: 1000,
                  xShow: false
                };
                buildScatterChart(config[i]);
                self.loading = false;
                console.log("Facebook-engagement_time_series", response, config);
              });
        };
        this.loadData();
      }
      function TwitterEngagementTimeline() {
        var self = this;
        var config = [];
        this.loading = true;
        var i=3;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('engagement_time_series', { platform_name: blockTitle[i] })
              .then(function(response) {

                var _count = [],_date = [];
                for(var j= 0; j<response.length; j++){
                  _count.push(response[j].count);
                  _date.push(response[j].date);
                }
                self.count = _count.toString();
                self.date = _date.toString();

                var eTL = EngagementTimeline(response);

                config[i] = {
                  elementId: '#BbChartTwitter',
                  jsonData: {
                    'data': eTL.yValue,
                    'x': eTL.xDate
                  },
                  values: eTL.rValue,
                  colors: blockColor[i],
                  height: 50,
                  width: 1000,
                  xShow: false
                };
                buildScatterChart(config[i]);
                self.loading = false;
                console.log("Twitter-engagement_time_series", response, config);
              });
        };
        this.loadData();
      }
      function PinterestEngagementTimeline() {
        var self = this;
        var config = [];
        this.loading = true;
        var i=4;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('engagement_time_series', { platform_name: blockTitle[i] })
              .then(function(response) {

                var _count = [],_date = [];
                for(var j= 0; j<response.length; j++){
                  _count.push(response[j].count);
                  _date.push(response[j].date);
                }
                self.count = _count.toString();
                self.date = _date.toString();

                var eTL = EngagementTimeline(response);

                config[i] = {
                  elementId: '#BbChartPinterest',
                  jsonData: {
                    'data': eTL.yValue,
                    'x': eTL.xDate
                  },
                  values: eTL.rValue,
                  colors: blockColor[i],
                  height: 70,
                  width: 1000,
                  xShow: true
                };
                buildScatterChart(config[i]);
                self.loading = false;
                console.log("Pinterest-engagement_time_series", response, config);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////

      /* Instagram likes *///////////////////////////////////////////////////////////////////////////////////////
      /* Instagram likes *///////////////////////////////////////////////////////////////////////////////////////
      /* Instagram likes *///////////////////////////////////////////////////////////////////////////////////////
      /* Instagram likes *///////////////////////////////////////////////////////////////////////////////////////

      function InstagramLikes() {
        var self = this;
        var config = [];
        this.loading = false;
        var i=1;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('engagement_time_series', { platform_name: blockTitle[i] ,engagement_type: 'likes'})
              .then(function(response) {

                self.data = [];
                self.data[0]={};
                var _count = [],_date = [], likes=0;
                for(var i= 0; i<response.length; i++){
                  likes=likes + response[i].count;
                  _count.push(response[i].count);
                  _date.push(response[i].date);
                }
                self.data[0].minDate = response[0].date;
                self.data[0].maxDate = response[response.length-1].date;
                self.data[0].totalCount = numberWithCommas(likes);
                self.data[0].count = _count.toString();
                self.data[0].date = _date.toString();
                self.loading = false;
                console.log("Instagram-engagement_likes", self);
              });
        };
        this.loadData();
      }

      function InstagramComments() {
        var self = this;
        var config = [];
        this.loading = false;
        var i=1;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('engagement_time_series', { platform_name: blockTitle[i] ,engagement_type: 'comments'})
              .then(function(response) {

                self.data = [];
                self.data[0]={};
                var _count = [],_date = [], comments=0;
                for(var i= 0; i<response.length; i++){
                  comments=comments + response[i].count;
                  _count.push(response[i].count);
                  _date.push(response[i].date);
                }
                self.data[0].minDate = response[0].date;
                self.data[0].maxDate = response[response.length-1].date;
                self.data[0].totalCount = numberWithCommas(comments);
                self.data[0].count = _count.toString();
                self.data[0].date = _date.toString();
                self.loading = false;
                console.log("Instagram-engagement_comments", self);
              });
        };
        this.loadData();
      }
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////


      /* Influencer performance *///////////////////////////////////////////////////////////////////////////////////////
      /* Influencer performance *///////////////////////////////////////////////////////////////////////////////////////
      /* Influencer performance *///////////////////////////////////////////////////////////////////////////////////////
      /* Influencer performance *///////////////////////////////////////////////////////////////////////////////////////

      function myBubbleChart() {

        var CONFIG = {
          COLORS: ["#a1e9f8", "#ffe88c", "#ffc0ba", "#84b8ff", "#8df2ce", "#c1c1c1"],
          WIDTH: 400,
          HEIGHT: 500
        };
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('influencer_performance')
              .then(function(response) {
                self.jsonData = {
                  "name": "layer1",
                  "children": []
                };
                var jsonData1 = {}, jsonData2 = {}, jsonData3 = {};
                var j1= 0, j2= 0, j3=0;
                jsonData1.name = '';
                jsonData1.children=[];
                jsonData2.name = '';
                jsonData2.children=[];
                for(var i=0; i<response.influencers.length; i++){

                  jsonData3.name=response.influencers[i].name;
                  jsonData3.size=response.influencers[i].score;

                  if(j3==3){
                    jsonData2.name = "layer3"+j1+j2;
                    jsonData1.children[j2]=JSON.parse(JSON.stringify(jsonData2));
                    j3 = 0;
                    j2++;
                  }
                  if(j2==3){
                    jsonData1.name = "layer2"+j1;
                    self.jsonData.children[j1]=JSON.parse(JSON.stringify(jsonData1));
                    j2 = 0;
                    j1++;
                  }
                  jsonData2.children[j3]=JSON.parse(JSON.stringify(jsonData3));
                  j3++;
                }
                console.log("row--fourth Influencer performance::", self.jsonData, response.influencers);
                self.buildChart = function(){

                  var format = d3.format(",d"),
                      color = d3.scale.category20c();

                  var bubble = d3.layout.pack()
                      .sort(null)
                      .size([CONFIG.WIDTH, CONFIG.HEIGHT])
                      .padding(1.5);

                  var svg = d3.select("#bubbleContainer").append("svg")
                      .attr("width", CONFIG.WIDTH)
                      .attr("height", CONFIG.HEIGHT)
                      .attr("class", "bubble");


                  var node = svg.selectAll(".node")
                      .data(bubble.nodes(classes(self.jsonData))
                          .filter(function (d) {
                            return !d.children;
                          }))
                      .enter().append("g")
                      .attr("class", "node")
                      .attr("transform", function (d) {
                        return "translate(" + d.x + "," + d.y + ")";
                      });

                  node.append("title")
                      .text(function (d) {
                        return d.className + ": " + format(d.value);
                      });

                  node.append("circle")
                      .attr("r", function (d) {
                        return d.r;
                      })
                      .style("fill", function (d) {
                        return color(d.packageName);
                      });

                  node.append("text")
                      .attr("dy", ".3em")
                      .style("text-anchor", "middle")
                      .style("font-size", "10px")
                      .text(function (d) {
                        return d.className.substring(0, d.r / 3);
                      });


                  // Returns a flattened hierarchy containing all leaf nodes under the root.
                  function classes(root) {
                    var classes = [];

                    function recurse(name, node) {
                      if (node.children) node.children.forEach(function (child) {
                        recurse(node.name, child);
                      });
                      else classes.push({packageName: name, className: node.name, value: node.size});
                    }

                    recurse(null, root);
                    return {children: classes};
                  }
                };
                self.buildChart();
                self.loading = false;
              });
        };
        this.loadData();
      }
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////

      /* clickthroughs_time_series *///////////////////////////////////////////////////////////////////////////////////////
      /* clickthroughs_time_series *///////////////////////////////////////////////////////////////////////////////////////
      /* clickthroughs_time_series *///////////////////////////////////////////////////////////////////////////////////////
      /* clickthroughs_time_series *///////////////////////////////////////////////////////////////////////////////////////

      function ClickThroughsTimeSeries() {
        var self = this;
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('clickthroughs_time_series')
              .then(function(response) {
                self.loading = false;
                self.data = [];
                self.data[0]={};
                var _count = [],_date = [];
                self.clicks = numberWithCommas(response.totalClicks);
                for(var i= 0; i<response.timeSeries.length; i++){
                  _count.push(response.timeSeries[i].count);
                  _date.push(response.timeSeries[i].date);
                }
                self.data[0].count = _count.toString();
                self.data[0].date = _date.toString();
                console.log("row--fourth ClickThroughsTimeSeries::", self.data);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////

      /* cumulative_impressions_time_series *///////////////////////////////////////////////////////////////////////////////////////
      /* cumulative_impressions_time_series *///////////////////////////////////////////////////////////////////////////////////////
      /* cumulative_impressions_time_series *///////////////////////////////////////////////////////////////////////////////////////
      /* cumulative_impressions_time_series *///////////////////////////////////////////////////////////////////////////////////////

      function CumulativeImpressionsTimeSeries() {
        var self = this;
        this.loading = false;

        this.loadData = function() {
          self.loading = true;
          Restangular
              .one('campaign_reports', ctrl.campaignId)
              .customGET('cumulative_impressions_time_series')
              .then(function(response) {
                self.loading = false;
                self.data = [];
                self.data[0]={};
                var _count = [],_date = [];
                self.totalImpressions = response.totalImpressions;
                for(var i= 0; i<response.timeSeries.length; i++){
                  _count.push(response.timeSeries[i].count);
                  _date.push(response.timeSeries[i].date);
                }
                self.data[0].count = _count.toString();
                self.data[0].date = _date.toString();
                self.data[0].minDate = response.timeSeries[0].date;
                self.data[0].maxDate = response.timeSeries[response.timeSeries.length-1].date;
                console.log("row--fourth cumulative_impressions_time_series::", self.data);
              });
        };
        this.loadData();
      }

      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////
      //////////////////////////////////////////////////////////////////////////////////////////////////////////////

      scope.campaignMap = new CampaignMap();
      // scope.topInfluencers = new TopInfluencers();
      scope.BlogEngagementTimeline = new BlogEngagementTimeline();
      scope.InstagramEngagementTimeline = new InstagramEngagementTimeline();
      scope.TwitterEngagementTimeline = new TwitterEngagementTimeline();
      scope.FacebookEngagementTimeline = new FacebookEngagementTimeline();
      scope.PinterestEngagementTimeline = new PinterestEngagementTimeline();
      scope.instagramPhotos = new InstagramPhotos();
      // scope.topPosts = new TopPosts();
      // scope.postStats = new PostStats();
      // scope.postImpressions = new PostImpressions();
      scope.BlogStatus = new BlogStatus();
      scope.InstagramStatus = new InstagramStatus();
      scope.FacebookStatus = new FacebookStatus();
      scope.TwitterStatus = new TwitterStatus();
      scope.PinterestStatus = new PinterestStatus();
      scope.BlogRandomInfluencers = new BlogRandomInfluencers();
      scope.InstagramRandomInfluencers = new InstagramRandomInfluencers();
      scope.FacebookRandomInfluencers = new FacebookRandomInfluencers();
      scope.TwitterRandomInfluencers = new TwitterRandomInfluencers();
      scope.PinterestRandomInfluencers = new PinterestRandomInfluencers();
      scope.BlogTLPosts = new BlogTLPosts();
      scope.InstagramTLPosts = new InstagramTLPosts();
      scope.FacebookTLPosts = new FacebookTLPosts();
      scope.TwitterTLPosts = new TwitterTLPosts();
      scope.PinterestTLPosts = new PinterestTLPosts();
      scope.BlogPostSamples = new BlogPostSamples();
      scope.BlogTopInfluencers = new BlogTopInfluencers();
      scope.ImpressionsTimeSeries = new ImpressionsTimeSeries();
      scope.ClickThroughsTimeSeries = new ClickThroughsTimeSeries();
      scope.CumulativeImpressionsTimeSeries = new CumulativeImpressionsTimeSeries();
      scope.InstagramLikes = new InstagramLikes();
      scope.InstagramComments = new InstagramComments();
      scope.TotalEngagements = new TotalEngagements();
      ////////////////////////////////////////////
      scope.platformPostsTimeSeries = new PlatformPostsTimeSeries();
      scope.platformIconClasses = tsPlatformIconClasses.get;
      scope.myBubbleChart = new myBubbleChart();
    }
  };
}])


// =================== OLD STUFF =========================


.controller('JobPostCtrl', ['$scope', '$rootScope', '$q', 'defaults', 'filtersQuery', 'collab_types', 'collections', '$timeout', 'FileUploader', 'context', function ($scope, $rootScope, $q, defaults, filtersQuery, collab_types, collections, $timeout, FileUploader, context) {
  $scope.post_data = {
    title: _.unescape(defaults.title).replace('&#39;', '\''),
    details: _.unescape(defaults.details).replace('&#39;', '\''),
    who: _.unescape(defaults.who).replace('&#39;', '\''),
    description: _.unescape(defaults.description).replace('&#39;', '\''),
    published: defaults.published,
    collection_tmp: defaults.collection,
    collab_type_tmp: defaults.collab_type,
    collab_type: defaults.collab_type.value,
    mentions_required: defaults.mentions_required,
    hashtags_required: defaults.hashtags_required,
    client_name: defaults.client_name,
    date_start: defaults.date_start,
    date_end: defaults.date_end,
    utm_source: defaults.utm_source,
    utm_medium: defaults.utm_medium,
    utm_campaign: defaults.utm_campaign,
  }
  $scope.collections = collections;
  $scope.collab_types = collab_types;

  $scope.dateRangeDefer = $q.defer();

  $scope.dateRangeDefer.promise.then(function() {
      $rootScope.$broadcast('resetDateRangePicker');
  });

  $scope.dateRangeModel = {
      startDate: null,
      endDate: null,
  };

  $scope.applyDateRange = function() {
      $scope.post_data.date_start = moment($scope.dateRangeModel.startDate).format('YYYY-MM-DD');
      $scope.post_data.date_end = moment($scope.dateRangeModel.endDate).format('YYYY-MM-DD');
  };

  $scope.$watch('dateRangeModel', function(nv, ov) {
      $scope.applyDateRange();
  }, true);


  var set_cover_img = function(url){
    $scope.cover_img_url = url;
    setTimeout(function() {
      $(".image_prev").children().remove();
      $(".image_prev").append($("<img style='width: 400px' src='"+url+"?r="+Math.random()+"'/>"));
    }, 10);
    $("#cover_img_url").val(url);
  };


  $scope.$on("coverImageSet", function(their_scope, url){
    set_cover_img(url);
    bind_warning();
  });

  if(defaults.cover_img_url){
    set_cover_img(defaults.cover_img_url);
  }

  var bind_warning = function(){
    console.log('bind warning');
    $(window).bind("beforeunload", function() {
        return "You have unsaved changes!";
    });
  };
  var unbind_warning = function(){
    console.log('unbind warning');
    $(window).unbind("beforeunload");
  };

  $scope.updateCollabType = function(selected){
    if (selected !== undefined)
      $scope.post_data.collab_type_tmp = selected;
    $("#collab_type").val($scope.post_data.collab_type_tmp.value);
  };
  $scope.updateCollection = function(){
    $("#collection").val($scope.post_data.collection_tmp.value);
  };
  setTimeout($scope.updateCollabType, 10);
  setTimeout($scope.updateCollection, 10);
  if(defaults.filters){
    filtersQuery.setQuery(defaults.filters);
    $("#filter_json").val(JSON.stringify(defaults.filters));
    $scope.post_data.filters=JSON.stringify(defaults.filters);
  }
  $scope.togglePublish = function(){
    $scope.job_post.published.$modelValue = !$scope.job_post.published.$modelValue;
  }
  $scope.$on("setFilters", function(their_scope, filters){
    $("#filter_json").val(JSON.stringify(filters));
    $scope.post_data.filters = JSON.stringify(filters);
  });

  $scope.select_file = function(){
    $("#attach_upload").click();
  };

  $scope.uploader = new FileUploader({
    url: context.uploadCampaignAttachmentUrl,
    autoUpload: true,
    headers: {
        'X-CSRFToken': context.csrf_token
    }
  });

  $scope.uploader.onErrorItem = function(fileItem, response, status, headers) {
    $scope.attachmentUploadError = response || "Error during uploading."
    $scope.form_errors = true;
    $scope.uploadMessage = null;
  };

  $scope.uploader.onSuccessItem = function(fileItem, response, status, headers) {
      $scope.attachmentUploadError = null;
      $scope.form_errors = false;
      $scope.uploadMessage = "Click 'Update', otherwise changes will not be saved.";
  };

  $timeout(function(){
    $scope.oryg_post_data = angular.copy($scope.post_data);
    $scope.$watch("post_data", function(){
      if(angular.equals($scope.oryg_post_data, $scope.post_data)){
        unbind_warning();
      }else{
        bind_warning();
      }
    }, true);
  }, 100);

  $scope.save = function(){
    unbind_warning();
    $scope.can_submit = true;
    setTimeout(function() {
      var editedValues = ['details', 'who'];
      editedValues.forEach(function(value) {
        $("#" + value).val($("#editor_" + value).html());  
      });
      $("form[name='job_post']").submit();
      $scope.can_submit = false;
    }, 10);
  };

  $scope.saveAndPublish = function(){
    $("form[name='job_post']").attr("action", $("form[name='job_post']").attr("action")+"?publish=true");
    $timeout($scope.save, 10);
  };

  $scope.can_submit = false;
  $("form[name='job_post']").submit(function(){
    if($scope.can_submit !== true){
      return false;
    }
  });

}])


.controller('FavoritesCtrl', ['$scope', '$http', '$q', '$window', 'context', function ($scope, $http, $q, $window, context) {
  $scope.addCollection = function(options){
    $scope.$broadcast('openAddCollectionPopup', options);
  };
  $scope.addReport = function(options) {
    $scope.$broadcast('openAddReportPopup', options);
  };
  $scope.editGroup = function(options){
    $scope.$broadcast('openEditCollectionPopup', options);
  };
  $scope.deleteGroup = function(id, url){
    $scope.$broadcast(
      'openConfirmationPopup',
      'Are you sure?',
      function(){
        $http.post(url, {
            id: id,
        });
        var promise = $q.defer();
        promise.promise.then(function(){
          //Intercom('trackEvent', 'bloggers-favorites-list-delete', {id: id});
          setTimeout(function() {
            $("#group_"+id).fadeOut({complete: function(){
              $("#group_"+id).remove();
            }});
          }, 10);
        });
        promise.resolve();
        return promise.promise;
      },
      null
    );
  };

  $scope.displayMessage = function(msg) {
      $scope.$broadcast("displayMessage", {message: msg});
  };

  $scope.context = context;
  $scope.$window = $window;

}])

.controller('FavoritesTableCtrl', ['$scope', '$timeout', function ($scope, $timeout) {
  $scope.selected_bloggers = [];
  $scope.$on("selectAllBloggers", function(){
    setTimeout(function(){
      $("span.blogger_select").filter(":not(:checked)").click();
    }, 10);
    $("span.blogger_select").click(function(){
      var id = $(this).data('id');
      $scope.$apply(function(){
        $scope.selected_bloggers[id] = true;
      });
    });
  });
}])

.directive('favoritedTable', ['$http', '$compile', '$rootScope', '$timeout', '$location', 'context', function ($http, $compile, $rootScope, $timeout, $location, context) {
  return {
    restrict: 'A',
    controller: function($scope, $element, $attrs, $transclude) {
      $scope.table_mode = 'all';
      $scope.context = context;
      $scope.showFavorites = function(){
        $scope.$broadcast('closeAllConversations');
        $timeout(function(){
          $location.path('/favorites');
          $scope.table_mode = 'favorites';
        }, 10);
      };
      $scope.showApplicants = function(){
        $scope.$broadcast('closeAllConversations');
        $timeout(function(){
          $location.path('/applicants');
          $scope.table_mode = 'applicants';
        }, 10);
      };
      $scope.showAll = function(){
        $scope.$broadcast('closeAllConversations');
        $timeout(function(){
          $location.path('/all');
          $scope.table_mode = 'all';
        }, 10);
      };
      if ($attrs.disableRouting === undefined) {
        if($location.path() == "/applicants"){
          $timeout($scope.showApplicants, 100);
        }
        if($location.path() == "/favorites"){
          $timeout($scope.showFavorites, 100);
        }
        if($location.path() == "/all"){
          $timeout($scope.showAll, 100);
        }
        $timeout($scope.showAll, 50);
      }
      $scope.conv_visible = {};
      $scope.toggleConversation = function(id, who, influencer_id){
        $scope.conv_visible[id] = !$scope.conv_visible[id];
        $scope.$broadcast('toggleConversation', id, who);
      };
      $scope.$on("closedConversation", function(their_scope, id){
        $scope.conv_visible[id] = false;
      });
      $scope.displayMessage = function(msg) {
        $scope.$broadcast("displayMessage", {message: msg});
    };
    },
    link: function (scope, iElement, iAttrs) {
      scope.influencers_ids = angular.fromJson(iAttrs.influencers || '[]');
      scope.influencers = [];
      scope.id_to_influencer = {};
      for (var i = 0; i < scope.influencers_ids.length; i++) {
        var newInfluencer = {
          id: scope.influencers_ids[i],
          selected: false
        };
        scope.influencers.push(newInfluencer);
        scope.id_to_influencer[newInfluencer.id] = newInfluencer;
      }
      scope.selectInfluencer = function(id) {
        scope.id_to_influencer[id].selected = !scope.id_to_influencer[id].selected;
      };
      scope.doOpenFavoritePopup = function(options){
        // options.groups = angular.fromJson(options.groups);
        scope.$broadcast('openFavoritePopup', options);
      };

      scope.$on('doOpenFavoritePopup', function(theirScope, options) {
        scope.doOpenFavoritePopup(options);
      });

      scope.show = function(sourceUrl, options){
        if (options && options.isBloggerApproval && options.campaignId) {
          sourceUrl += '?campaign_posts_query=' + options.campaignId;
        }
        var wrapper = angular.element("<span>");
        var elem = angular.element("<span blogger-more-info-popup reload url='"+sourceUrl+"'></span>");
        $("#favorited_table_root").append(wrapper);
        wrapper.append(elem);
        $compile(wrapper.contents())(scope);
      };
/*      scope.submitEdit = function(id, selector, url){
        var status = $(selector).find('.influencer_status').val();
        $(selector).addClass('blacklisted');
        $http.post(url, {
          id: id,
          status: status
        }).success(function(){
          $(selector).removeClass('blacklisted');
        }).error(function(a, b, c, d){
          //Intercom('trackEvent', 'error', {name: "Edit stage", sent: d, received: a, status: b, headers: c()});
        });
      };*/
      scope.submitDelete = function(id, group_id, url){
        $("#mapping_"+id).fadeOut();
        $("#candidate_"+id).fadeOut();
        $(".conversation_"+id).fadeOut();
        $http.post(url, {
          id: id,
          group_id: group_id
        }).success(function(){
        }).error(function(a, b, c, d){
          //Intercom('trackEvent', 'error', {name: "Delete influencer from group", sent: d, received: a, status: b, headers: c()});
        });
      };


/*      $('.influencer_status').change(function(){
        var mapping_id = $(this).data("mapping-id");
        var mapping_selector = $(this).data("mapping-selector");
        var url = $(this).data("url");
        scope.$apply(function(){
          scope.submitEdit(mapping_id, mapping_selector, url);
        });
      });*/


      scope.invite = function(influencer_id, group_id, template, subject, invited_to, force_invite){
        if (options === undefined)
          return;
        angular.extend(options, {
          user: scope.user, 
          item: scope.item,
        });
        $rootScope.$broadcast("openInvitationPopup", options);
      };

    }
  };
}])



.directive('previewModeToggler', ['$rootScope', function($rootScope) {
  return {
    restrict: 'A',
    controller: 'PublicApprovalReportCtrl',
    controllerAs: 'previewModeCtrl',
    link: function(scope, iElement, iAttrs, ctrl) {
      // if (iAttrs.previewModeEnabled) {
      //   iElement.bind('click', function($event) {
      //     $event.preventDefault();
      //     $event.stopPropagation();
      //     ctrl.showPreviewModePopup();
      //   });
      // }
    }
  };
}])



.controller('PublicApprovalReportCtrl', ['$scope', '$http', '$timeout', '$rootScope', 'approvalData',
  function ($scope, $http, $timeout, $rootScope, approvalData) {
    var self = this;

    self.data = approvalData;
    self.submitted = approvalData.approvalStatus == 2;
    self.submitting = false;
    self.dirty = false;

    self.showContinueEditingPopup = function($event, options) {
      $rootScope.$broadcast('openConfirmationPopup', [
        "Are you sure you want to continue editing?. ",
        "Your selections have already been sent to your campaign manager. ",
        "If it has been a while since you last submitted you might want ",
        "to check in with them before you make edits. If you choose to go ",
        "ahead and make your edits, please remember to click SUBMIT when you ",
        "are finished, and your campaign manager will get an email about your updates"
      ].join(''), function yes() {
        self.submitting = true;
        return $http({
          method: 'POST',
          url: '/update_model/',
          data: {
            modelName: 'InfluencerAnalyticsCollection',
            id: parseInt(approvalData.collectionId),
            values: {
              approval_status: parseInt(approvalData.collectionId),
            }
          }
        }).then(function() {
          self.submitting = false;
          self.submitted = false;
          $timeout(function() {
            // angular.element($event.target).triggerHandler('click');
            angular.element($event.target).trigger('click');
          });
        }, function() {
          self.submitting = false;
          self.submitted = false;
        });
      }, function no() {}, {titleText: 'Wait a sec', yesText: 'Continue Editing', noText: 'Cancel Edit'});
    };

    self.showPreviewModePopup = function() {
      $rootScope.$broadcast('openConfirmationPopup',
          "You are in preview mode, so you can't edit this " +
          "page. This is the report that will be sent to your " +
          "client for them to approve the influencers who they like.",
          null, null, {titleText: "Preview Mode", yesText: "OK", removeNo: true});
    };

    self.canChangeApprove = function($event, options) {
      if (self.data.previewMode) {
        $event.preventDefault();
        self.showPreviewModePopup();
      } else if (self.submitted) {
        $event.preventDefault();
        self.showContinueEditingPopup($event, options);
      } else {
        return true;
      }
    };

    self.changeApprove = function(options) {
      options.requesterCtrl.doRequest({
        method: 'POST',
        url: '/update_model/',
        data: {
          modelName: 'InfluencerAnalytics',
          id: options.id,
          values: {
            tmp_approve_status: parseInt(options.value),
          }
        }
      }).then(function() {
        self.dirty = true;
      });
    };

    self.submit = function() {
      if (self.data.previewMode) {
        self.showPreviewModePopup();
        return;
      }
      $rootScope.$broadcast('openBloggerApprovalPopup', {
        brandId: approvalData.brandId,
        reportId: approvalData.reportId,
        userId: approvalData.userId,
        userFirstName: approvalData.userFirstName,
        clientLink: approvalData.clientLink,
        campaignName: approvalData.campaignName,
        approve: true,
        status: approvalData.approvalStatus,
        campaignId: approvalData.campaignId,
      });
    };

    $scope.$on('approval:sent', function(theirScope) {
      self.submitted = true;
      self.dirty = false;
    });

    // window.onbeforeunload = function () {
    //   if (self.dirty) {
    //       return [
    //         "All of your changes are saved, but in order to send these to _____, you need to click Submit. ",
    //         "Do you want to leave the page without submitting, or do you want to send these final choices to your _____?"
    //       ].join('\n');
    //   }
    // };

    // self.changeApprove = function(paId, value, $event, options) {
    // self.changeApprove = function($event, options) {
    //   if (self.data.previewMode) {
    //       $event.preventDefault();
    //       self.showPreviewPopup();
    //   } else if (self.editingLocked) {
    //       // $event.preventDefault();
    //       // $rootScope.$broadcast('openConfirmationPopup', [
    //       //     "<p>1. Click YES or NO for all influencers in the list. (There might be more than one page.)</p>",
    //       //     "<p>2. At any point, you can click SAVE in the upper right to make sure you don't lose any changes.</p>",
    //       //     "<p>3. If you want another team member to review, make sure you click the SAVE button before sharing the link with them.</p>",
    //       //     "<p>4. When you are finished, click the SUBMIT button in order to send your results back to " +
    //       //     (options.userFirstName && options.userFirstName.length ? options.userFirstName : "our user") + ".</p>"].join('</br>'),
    //       //     function() {
    //       //         $scope.makeSelections();
    //       //         // $scope.approvesData.values[paId] = value;
    //       //         $scope.selectApprove(paId, value);
    //       //     }, null, {titleText: "Approval Form", htmlContent: true});
    //   } else {
    //       // $scope.approvesData.values[paId] = value;
    //       $scope.selectApprove(paId, value);
    //   }
    // };
  }])


.directive('resize', ['$window', function ($window) {
  return function (scope, element, attr) {

    var w = angular.element($window);
    scope.$watch(function () {
      return {
        'h': window.innerHeight,
        'w': window.innerWidth
      };
    }, function (newValue, oldValue) {
      // console.log(newValue, oldValue);
      scope.windowHeight = newValue.h;
      scope.windowWidth = newValue.w;

      scope.responsiveWidth1 = scope.windowWidth * 0.55 - 250;
      scope.responsiveWidth2 = scope.windowWidth - 340;
      scope.responsiveWidth3 = scope.windowWidth * 0.3 - 70;

      console.log("current width:"+scope.responsiveWidth3);
      scope.resizeWithOffset = function (offsetH) {
        scope.$eval(attr.notifier);
        return {
          'height': (newValue.h - offsetH) + 'px'
        };
      };

    }, true);

    w.bind('resize', function () {
      scope.$apply();
    });
  }
}])
.directive('toggle', function(){
        return {
            restrict: 'A',
            link: function postLink(scope, element, attrs){
                if(attrs.toggle ==="tooltip"){
                    $(element).tooltip();
                }
                if(attrs.toggle==="popover"){
                    $(element).popover();
                }
            }
        };
    })
.controller('ViewChangeClickCtrl', ['moment', function(moment) {

  var vm = this;

  vm.events = [];
  vm.calendarView = 'year';
  vm.viewDate = moment().startOf('month').toDate();
  vm.viewChangeEnabled = true;

  vm.viewChangeClicked = function(date, nextView) {
    // console.log(date, nextView);
    return vm.viewChangeEnabled;
  };
  vm.calendarViewYear = function(){
    vm.calendarView = 'year';
  };
  vm.calendarViewMonth = function(){
    vm.calendarView = 'month';
  };

}])
.factory('alert', ['$uibModal', function($uibModal) {

  function show(action, event) {
    return $uibModal.open({
      templateUrl: '<div class="modal-header"> <h3 class="modal-title">Event action occurred!</h3> </div> <div class="modal-body"><p>Action:<pre>{{ vm.action }}</pre> </p> <p>Event: <pre>{{ vm.event | json }}</pre> </p> </div> <div class="modal-footer"> <button class="btn btn-primary" ng-click="$close()">OK</button></div>',
      controller: function() {
        var vm = this;
        vm.action = action;
        vm.event = event;
      },
      controllerAs: 'vm'
    });
  }

  return {
    show: show
  };

}]);
