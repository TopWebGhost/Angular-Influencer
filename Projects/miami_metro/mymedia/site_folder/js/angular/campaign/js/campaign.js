(function () {
  angular.module('theshelf.campaign', ['theshelf', 'theshelf.components', 'ui.router', 'restangular', 'pdf', 'tsGlobal'])



  .config([
    '$stateProvider',
    '$urlRouterProvider',
    '$httpProvider',
    'RestangularProvider',
    'tsConfigProvider',
    '$sceDelegateProvider',
    function ($stateProvider, $urlRouterProvider, $httpProvider, RestangularProvider, tsConfigProvider, $sceDelegateProvider) {

    // tsConfig = {
    //   STATIC_PREFIX: '/static/',
    // };

    // $sceDelegateProvider.resourceUrlWhitelist([
    //     'self',
    //     'https://theshelf-static-files.s3.amazonaws.com/**',
    // ]);

    // $sceDelegateProvider.resourceUrlWhitelist(['.*']);

    $sceDelegateProvider.resourceUrlWhitelist([
        'self',
        'https://syndication.twitter.com/**',
        'http://theshelf-static-files.s3.amazonaws.com/**',
        'https://theshelf-static-files.s3.amazonaws.com/**',
    ]);

    RestangularProvider.setBaseUrl('/api/v1');

    $urlRouterProvider.when('/:campaignId', '/:campaignId/1');
    $urlRouterProvider.otherwise('/');

    $httpProvider.defaults.xsrfCookieName = 'csrftoken';
    $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';

    $stateProvider
      .state('empty', {
        url: '^/',
        template: 'Empty',
      })
      .state('wizard', {
        abstract: true,
        url: '^/:campaignId',
        templateUrl: tsConfigProvider.$get().STATIC_PREFIX + 'js/angular/campaign/templates/wizard.html',
        controller: 'WizardCtrl',
        controllerAs: 'wizardCtrl',
        resolve: {
          campaignData: ['$stateParams', 'CampaignService', function ($stateParams, CampaignService) {
            return CampaignService.getOne({id: $stateParams.campaignId});
          }],
        },
      })
      .state('wizard.section', {
        url: '^/:campaignId/:section',
        resolve: {
          saveData: ['CampaignService', '$rootScope', function (CampaignService, $rootScope) {
            $rootScope.random = Math.random();
            if ($rootScope.forms.accordionForm && $rootScope.forms.accordionForm.$pristine) {
              return null;
            } else {
              if ($rootScope.forms.accordionForm) {
                $rootScope.forms.accordionForm.$setPristine();
              }
              return CampaignService.save();
            }
          }],
        },
      });
  }])



  .run(['$rootScope', '$state', '$stateParams', 'WizardService', 'context', 'UploaderService', 'CampaignService', 'tsUtils', function ($rootScope, $state, $stateParams, WizardService, context, UploaderService, CampaignService, tsUtils) {

    $rootScope.$state = $state;
    $rootScope.$stateParams = $stateParams;

    $rootScope.isSwitchingState = false;

    $rootScope.uploader = UploaderService.uploader;

    function isFormValid(toSection, fromSection) {
      return !fromSection || !$rootScope.forms[fromSection.key] || $rootScope.forms[fromSection.key].$valid;
    }
    function isFormPristine(toSection, fromSection) {
      return !fromSection || !$rootScope.forms[fromSection.key] || fromSection.key == toSection.key || $rootScope.forms[fromSection.key].$pristine;
    }

    WizardService.$predicates.push(isFormValid);
    // WizardService.$predicates.push(isFormPristine);

    $rootScope.$on('$stateChangeStart', function (event, to, toParams, from, fromParams) {
      if (fromParams.campaignId !== toParams.campaignId) {
        if ($rootScope.forms.accordionForm && $rootScope.forms.accordionForm.$dirty && !confirm("The form is not saved, do you want to stay on the page?")) {
          event.preventDefault();
        } else {
          $rootScope.isSwitchingState = true;
        }
      }

      var result = WizardService.canSwitchTo(toParams.section, fromParams.section);
      if (result !== true) {
        event.preventDefault();
        $rootScope.isSwitchingState = false;
        if (result.predicate === isFormValid) {
          // $rootScope.forms[result.fromSection.key].$setDirty();
          tsUtils.makeFormFieldsDirty($rootScope.forms[result.fromSection.key]);
          angular.element('html, body').animate({
            scrollTop: angular.element('#accordion_group_' + (fromParams.section -1)).offset().top - 20
          }, 500);
        } else if (result.predicate == isFormPristine) {
          angular.element('html, body').animate({
            scrollTop: angular.element('#accordion_group_' + (fromParams.section -1)).find('.next-step-button').offset().top - angular.element(window).height() + 100
          }, 500);
        } else {
          $state.go('wizard.section', {campaignId: toParams.campaignId, section: 0});  
        }
      }
    });

    $rootScope.$on('$stateChangeSuccess', function (event, toState, toParams) {
      $rootScope.isSwitchingState = false;
      WizardService.setCurrentSection(toParams.section);
    });

    $rootScope.$on('$stateChangeError', function (event, toState, toParams) {
      $rootScope.isSwitchingState = false;
    });

    $rootScope.forms = {};
    $rootScope.registerFormScope = function(form, name, id) {
      $rootScope.forms[name] = form;
    };

  }])



  .factory('wizardConfig', ['tsConfig', 'context', function (tsConfig, context) {
    return {
      templatesRoot: tsConfig.wrapTemplate('js/angular/campaign/templates/wizard_sections'),
      sections: {
        none: {
          canEdit: false,
          isCompleted: true,
          isOpen: false,
          live: false,
          order: -1,
          name: 'Done',
        },
        globalCampaignDetails: {
          canEdit: true,
          isCompleted: true,
          isOpen: false,
          live: true,
          order: 0,
          name: 'Global Campaign Details',
          description: 'Campaign objectives, brand description, hashtags, social handles, campaign imagery, logo',
          templateUrl: tsConfig.wrapTemplate('js/angular/campaign/templates/wizard_sections/globalCampaignDetails.html'),
          controllerName: 'GlobalCampaignDetailsCtrl',
        },
        influencerRequirements: {
          canEdit: true,
          isCompleted: true,
          isOpen: false,
          live: true,
          order: 1,
          name: 'Influencer Requirements',
          description: 'Deliverables, post requirements, dates',
          templateUrl: tsConfig.wrapTemplate('js/angular/campaign/templates/wizard_sections/influencerRequirements.html'),
          controllerName: 'InfluencerRequirementsCtrl',
        },
        outreach: {
          canEdit: true,
          isCompleted: true,
          isOpen: false,
          live: true,
          order: 2,
          name: 'Messaging Templates',
          description: 'Outreach, followups, logistics',
          templateUrl: tsConfig.wrapTemplate('js/angular/campaign/templates/wizard_sections/outreach.html'),
        },
        contracts: {
          canEdit: true,
          isCompleted: true,
          isOpen: false,
          live: true,
          order: 3,
          name: 'Contracts',
          description: 'Contracts, payment instructions',
          templateUrl: tsConfig.wrapTemplate('js/angular/campaign/templates/wizard_sections/contracts.html'),
        },
        product: {
          canEdit: true,
          isCompleted: true,
          isOpen: false,
          live: true,
          order: 4,
          name: 'Product Sending',
          description: 'Shipping details, product selection, brand/product URLs, selection instructions',
          templateUrl: tsConfig.wrapTemplate('js/angular/campaign/templates/wizard_sections/product.html'),
        },
        trackingCodes: {
          canEdit: true,
          isCompleted: true,
          isOpen: false,
          live: true,
          order: 5,
          name: 'Tracking Codes',
          description: 'Impression, engagement, and click-through tracking',
          templateUrl: tsConfig.wrapTemplate('js/angular/campaign/templates/wizard_sections/trackingCodes.html'),
        },
        savedSearchAssociation: {
          canEdit: true,
          isCompleted: true,
          isOpen: false,
          // live: context.isSuperuser,
          live: true,
          order: 6,
          name: 'Client Approval',
          description: 'Enabling approval reports for clients (and/or bosses)',
          templateUrl: tsConfig.wrapTemplate('js/angular/campaign/templates/wizard_sections/savedSearchAssociation.html'),
        },
      }
    };
  }])



  .service('CampaignService', ['Restangular', function (Restangular) {
    var self = this;

    self.data = null;
    self.savingData = false;

    self.getOne = function (params) {
      return Restangular.one('campaigns', params.id).get().then(function (response) {
        self.data = response;
        return response;
      }, function (response) {
        return null;
      });
    };

    self.save = function () {
      if (self.data) {
        self.savingData = true;
        return self.data.patch().then(function () {
          self.savingData = false;
        }, function () { 
          self.savingData = false;
        });
      } else {
        return null;
      }
    };
  }])



  .service('WizardService', ['wizardConfig', function (wizardConfig) {
    var self = this;

    self.previousSection = null;

    self.nthSection = function (n) {
      return _.findWhere(_.values(wizardConfig.sections), {order: n - 1});
    };

    self.closeAllSections = function () {
      angular.forEach(self.sections, function (section, index) {
        section.isOpen = false;
      });
    };

    self.openSection = function (section) {
      self.closeAllSections();
      if (section) {
        section.isOpen = true;
      }
    };

    self.setCurrentSection = function (n) {
      self.previousSection = self.currentSection;
      self.currentSection = self.nthSection(n);
      self.openSection(self.currentSection);
    };

    self.$predicates = [];

    self.canSwitchTo = function (toN, fromN) {
      if (toN > self.sections.length || toN < 0) {
        return false;
      }
      var toSection = self.nthSection(toN);
      var fromSection = self.nthSection(fromN);

      for (var i in self.$predicates) {
        if (!self.$predicates[i](toSection, fromSection)) {
          return {
            predicate: self.$predicates[i],
            toSection: toSection,
            fromSection: fromSection,
          };
        }
      }
      return true;
    };

    angular.forEach(wizardConfig.sections, function (section, key) {
      section.key = key;
    });
    self.sections = _.filter(_.sortBy(_.values(wizardConfig.sections), 'order'), function (section) { return section.live; });
    self.setCurrentSection(1);

  }])



  .controller('WizardCtrl', ['$scope', '$timeout', '$state', '$stateParams', 'WizardService', 'CampaignService', 'campaignData', function ($scope, $timeout, $state, $stateParams, WizardService, CampaignService, campaignData) {
    var vm = this;

    vm.service = WizardService;
    vm.campaignService = CampaignService;
    vm.campaignData = campaignData;

    if (!vm.campaignData) {
      vm.error = {
        text: 'No such campaign.',
      };
    } else {
      vm.error = null;
    }

    $timeout(function () {
      angular.forEach(WizardService.sections, function (section, index) {
        if (section.live) {
          $scope.$watch(function () {
            return section.isOpen;
          }, function (isOpened) {
            if (isOpened) {
              $state.go('wizard.section', {campaignId: $stateParams.campaignId, section: section.order + 1});
            }
          });
          $scope.$watch(function () {
            return angular.element('#accordion_group_' + index).find('.panel-collapse').hasClass('collapse in');
          }, function (isCollapsed) {
            if (isCollapsed) {
              angular.element('html, body').animate({
                scrollTop: angular.element('#accordion_group_' + index).offset().top - 20
              }, 500);
            }
          });
        }
      });
    });

    $timeout(function() {
      CampaignService.save().then(function () {
        $scope.accordionForm.$setPristine();
      });
    }, 100);

    window.onbeforeunload = function () {
      if ($scope.accordionForm.$dirty) {
          return "The form is not saved, do you want to stay on the page?";
      }
    };

    vm.preventToggle = function ($event, section) {
      if ($scope.accordionForm.$dirty) {
        $event.preventDefault();
        $event.stopPropagation();
        angular.element('html, body').animate({
          scrollTop: angular.element('#accordion_group_' + (WizardService.currentSection.order)).find('.next-step-button').offset().top - angular.element(window).height() + 100
        }, 500);
      }
    };

    vm.sectionState = function (section, $last) {
      if (CampaignService.savingData) {
        return 'saving';
      }
      if ($scope.forms[section.key] && $scope.forms[section.key].$invalid) {
        return 'invalid';
      }
      if ($scope.accordionForm.$dirty) {
        return 'dirty';
      }
      if (!$last) {
        return 'next_step';
      }
      return 'done';
    };


  }])



  .controller('GlobalCampaignDetailsCtrl', ['CampaignService', function (CampaignService) {
    var vm = this;
  }])



  .controller('InfluencerRequirementsCtrl', ['CampaignService', function (CampaignService) {
    var vm = this;
  }])



  .controller('OutreachCtrl', [
    'CampaignService',
    'tsInvitationTemplate',
    'tsFollowupTemplate',
    'tsCollectDetailsTemplate',
    'tsReminderTemplate',
    'tsPaymentCompleteTemplate',
    'tsShippingTemplate',
    'tsPostsAddingTemplate',
    'tsPostApprovalTemplate',
    'UploaderService',
    'context',
    function (CampaignService, tsInvitationTemplate, tsFollowupTemplate, tsCollectDetailsTemplate, tsReminderTemplate, tsPaymentCompleteTemplate, tsShippingTemplate, tsPostsAddingTemplate, tsPostApprovalTemplate, UploaderService, context) {
    var vm = this;

    vm.templateContext = {
      user: {
        first_name: 'Test User First Name',
        shipment_tracking_code: 'Shipment Tracking Code',
        shipment_received_url: 'Shipment Received Url',
      },
      campaign_overview_link: CampaignService.data.overviewPageLink,
      context: context
    };
    vm.sendEmailUrl = CampaignService.data.sendInvitationUrl;


    CampaignService.data.outreachTemplate.template = tsInvitationTemplate.getBodyTemplate(CampaignService.data.outreachTemplate.template, vm.templateContext);

    CampaignService.data.outreachTemplate.subject = tsInvitationTemplate.getSubjectTemplate(CampaignService.data.outreachTemplate.subject, vm.templateContext);


    CampaignService.data.info.followupTemplate.template = tsFollowupTemplate.getBodyTemplate(CampaignService.data.info.followupTemplate.template, vm.templateContext);

    CampaignService.data.info.followupTemplate.subject = tsFollowupTemplate.getSubjectTemplate(CampaignService.data.info.followupTemplate.subject, vm.templateContext);


    CampaignService.data.info.collectDetailsTemplate.template = tsCollectDetailsTemplate.getBodyTemplate(CampaignService.data.info.collectDetailsTemplate.template, vm.templateContext);

    CampaignService.data.info.collectDetailsTemplate.subject = tsCollectDetailsTemplate.getSubjectTemplate(CampaignService.data.info.collectDetailsTemplate.subject, vm.templateContext);


    CampaignService.data.info.reminderTemplate.template = tsReminderTemplate.getBodyTemplate(CampaignService.data.info.reminderTemplate.template, vm.templateContext);

    CampaignService.data.info.reminderTemplate.subject = tsReminderTemplate.getSubjectTemplate(CampaignService.data.info.reminderTemplate.subject, vm.templateContext);


    CampaignService.data.info.paymentCompleteTemplate.template = tsPaymentCompleteTemplate.getBodyTemplate(CampaignService.data.info.paymentCompleteTemplate.template, vm.templateContext);

    CampaignService.data.info.paymentCompleteTemplate.subject = tsPaymentCompleteTemplate.getSubjectTemplate(CampaignService.data.info.paymentCompleteTemplate.subject, vm.templateContext);


    CampaignService.data.info.postsAddingTemplate.template = tsPostsAddingTemplate.getBodyTemplate(CampaignService.data.info.postsAddingTemplate.template, vm.templateContext);

    CampaignService.data.info.postsAddingTemplate.subject = tsPostsAddingTemplate.getSubjectTemplate(CampaignService.data.info.postsAddingTemplate.subject, vm.templateContext);


    CampaignService.data.info.shippingTemplate.template = tsShippingTemplate.getBodyTemplate(CampaignService.data.info.shippingTemplate.template, vm.templateContext);

    CampaignService.data.info.shippingTemplate.subject = tsShippingTemplate.getSubjectTemplate(CampaignService.data.info.shippingTemplate.subject, vm.templateContext);


    CampaignService.data.info.postApprovalTemplate.template = tsShippingTemplate.getBodyTemplate(CampaignService.data.info.postApprovalTemplate.template, vm.templateContext);

    CampaignService.data.info.postApprovalTemplate.subject = tsShippingTemplate.getSubjectTemplate(CampaignService.data.info.postApprovalTemplate.subject, vm.templateContext);


    vm.uploader = UploaderService.uploader;
    vm.invitationTemplate = tsInvitationTemplate;
    vm.followupTemplate = tsFollowupTemplate;
    vm.collectDetailsTemplate = tsCollectDetailsTemplate;
    vm.reminderTemplate = tsReminderTemplate;
    vm.paymentCompleteTemplate = tsPaymentCompleteTemplate;
    vm.postsAddingTemplate = tsPostsAddingTemplate;
    vm.shippingTemplate = tsShippingTemplate;
    vm.postApprovalTemplate = tsPostApprovalTemplate;
  }])



  .controller('ContractsCtrl', ['CampaignService', function (CampaignService) {
    var self = this;
  }])



  .controller('ProductCtrl', ['$scope', 'CampaignService', '$timeout', function ($scope, CampaignService, $timeout) {
    var self = this;

    function shouldDisableProductSending () {
      return !CampaignService.data.info.shippingAddressOn && !CampaignService.data.info.productLinksOn && !CampaignService.data.info.bloggerAdditionalInfoOn;
    };

    $scope.$watch(shouldDisableProductSending, function (nv) {
      if (nv) {
        CampaignService.data.info.sendingProductOn = false;
      } else {
        CampaignService.data.info.sendingProductOn = true;
      }
    });

    // self.addAnotherUrl = function (url) {
    //   $scope.wizardCtrl.campaignData.productUrls.push(url);
    // };

    // self.urlChanged = function ($index, $last, form) {
    //   if ($last) {
    //     if (form.$dirty && form.$valid) {
    //       self.addAnotherUrl('');
    //     }
    //   } else {
    //     if (form.$dirty && form.$error.required) {
    //       $scope.wizardCtrl.campaignData.productUrls.splice($index, 1);
    //     }
    //   }
    // };

    // if (!$scope.wizardCtrl.campaignData.productUrls || !$scope.wizardCtrl.campaignData.productUrls.length) {
    //   self.addAnotherUrl('');
    //   $timeout(function () {
    //     if ($scope.forms['product']) {
    //       console.log('going..');
    //       $scope.forms['product'].$setPristine();
    //     }
    //   }, 500);
    // }

  }])



  .controller('TrackingCodesCtrl', ['CampaignService', function (CampaignService) {
    var self = this;
  }])


  .controller('SavedSearchAssociationCtrl', ['Restangular', 'CampaignService', function (Restangular, CampaignService) {
    var self = this;
    var brand = Restangular.one('brands', CampaignService.data.creator);

    function resetSelected() {
      self.options.forEach(function (option) {
        if (option.value == CampaignService.data.postsSavedSearch) {
          self.selected = option;
        }
      });
    }

    self.loading = true;
    brand.customGET('saved_searches').then(function (response) {
      self.options = response.map(function (item) {
        return {text: item.name, value: item.id};
      });
      resetSelected();
      self.loading = false;
      return response;
    });

    self.update = function (selected) {
      console.log(selected);
      self.selected = selected;
      CampaignService.data.postsSavedSearch = selected.value;
    };

  }]);

})();
