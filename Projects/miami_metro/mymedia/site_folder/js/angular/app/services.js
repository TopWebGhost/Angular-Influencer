(function() {
    angular.module('theshelf')


        .service('disableScrollService', ['$window', function($window) {
            var self = this;

            var layersCount = 0;

            self.incr = function() {
                layersCount++;
                return self.isDisabled();
            };

            self.decr = function() {
                if (layersCount > 0) layersCount--;
                return self.isDisabled();
            };

            self.isDisabled = function() {
                return layersCount === 0;
            };

            self.do = function() {
                if (self.decr()) {
                    angular.element($window).disablescroll('undo');
                }
            };
        }])
      

        .service('tsAddPostsWidgetService', ['$rootScope', '$q', '$http', 'Restangular', function ($rootScope, $q, $http, Restangular) {
            var self = this;

            function PostsList() {
                var list = this;

                function Type(text, value) {
                    var type = this;

                    this.text = text;
                    this.value = value;
                }

                Type.placeholder = function() {
                    return new Type('Select post type...', null);
                };

                function Post(type, url, title, date, info) {
                    var post = this;
                    var saved = false;

                    this.url = url;
                    this.title = title;
                    this.date = date;
                    this.info = info;
                    this.selected = false;
                    // this.index = index;

                    if (type instanceof Type) {
                        this.type = type;
                    } else if (type !== undefined && type !== null) {
                        this.type = _.find(list.types, function(item) { return item.value === type; });
                    } else {
                        this.type = Type.placeholder();
                    }

                    this.index = function() {
                        return _.indexOf(list.posts, post);
                    };

                    this.isEditable = function() {
                        return !post.saved;
                    };

                    this.updateType = function(selected) {
                        post.type = selected;
                        post.onChange();
                    };

                    this.canSave = function() {
                        return !post.saved && !post.saving && post.dirty && (post.url && post.date && post.type.value);
                    };

                    this.isEmpty = function() {
                        return !(post.url || post.date || post.type.value);
                    };

                    this.onChange = function() {
                        post.dirty = true;
                    };

                    this.select = function($event) {
                        if (post.saved) {
                            post.selected = !post.selected;
                        } else {
                            $event.preventDefault();
                        }
                    };

                    this.dirty = false;
                    this.saved = !this.isEmpty();
                    this.saving = false;
                    this.savingError = false;

                    this.sendingVerify = false;
                    this.sendingVerifyError = false;

                    this.verifyReset = function() {
                        this.sentVerify = (this.info ? this.info.verificationStatus.sent : false);
                        this.verificationStatus = (this.info ? this.info.verificationStatus.text : null);
                        this.verificationStatusColor = (this.info ? this.info.verificationStatus.color : null);
                    };

                    this.verifyReset();

                    this.canVerify = function() {
                        return post.saved && !post.sentVerify;
                    };

                    this.verify = function() {
                        if (!post.canVerify) {
                            return;
                        }
                        post.sendingVerify = true;
                        list.contract.post('verify_blogger_post', {
                            id: post.info.id,
                        }).then(function(response) {
                            post.sentVerify = true;
                            post.sendingVerify = false;
                            post.sendingVerifyError = false;
                            post.info = response.data.info;
                            post.verifyReset();
                        }, function() {
                            post.sentVerify = false;
                            post.sendingVerify = false;
                            post.sendingVerifyError = true;
                        });
                    };

                    this.save = function(response) {
                        if (!post.canSave()) {
                            return;
                        }
                        post.saving = true;
                        post.saved = false;
                        post.savingError = false;

                        list.contract.post('add_blogger_post', {
                            type: post.type.value,
                            url: post.url,
                            title: post.title,
                            date: post.date
                        }).then(function(response) {
                            post.dirty = false;
                            post.saved = true;
                            post.saving = false;
                            post.savingError = false;
                            post.info = response.data.info;
                            post.verifyReset();
                        }, function() {
                            post.saved = false;
                            post.saving = false;
                            post.savingError = true;
                        });
                    };
                }

                this.types = [
                    new Type('Blog', 'Blog'),
                    new Type('Facebook', 'Facebook'),
                    new Type('Pinterest', 'Pinterest'),
                    new Type('Twitter', 'Twitter'),
                    new Type('Instagram', 'Instagram'),
                ];

                this.lastPost = function() {
                    return _.last(list.posts);
                };

                this.canAddPost = function() {
                    if (list.posts.length === 0) {
                        return false;
                    }
                    return !list.lastPost().dirty && !list.lastPost().isEmpty();
                };

                this.addPost = function() {
                    if (list.canAddPost()) {
                        list.posts.push(new Post());
                    }
                };

                this.selected = function() {
                    return list.posts.filter(function(post) { return post.selected && post.saved; });
                };

                this.removing = false;
                this.removingError = false;

                this.doRemoveSelected = function () {
                    list.removing = true;
                    list.removingError = false;
                    list.contract.post('remove_blogger_posts', {
                        ids: list.selected().map(function(post) { return post.info.id; })
                    }).then(function (response) {
                        list.selected().forEach(function(post) {
                            list.posts.splice(post.index(), 1);
                        });
                        list.removing = false;
                        list.removingError = false;
                    }, function() {
                        list.removing = false;
                        list.removingError = true;
                    });
                };

                this.removeSelected = function() {
                    if (list.selected().length < 1) {
                        return;
                    }
                    $rootScope.$broadcast('openConfirmationPopup', 'Are you sure?', list.doRemoveSelected, null);
                };

                this.posts = [new Post()];

                this.loading = false;
                this.loadingError = false;
                this.cancelDefer = null;

                this.cancelLoad = function() {
                    list.loading = false;
                    list.loadingError = false;
                    if (list.cancelDefer !== null) {
                        list.cancelDefer.resolve();
                    }
                }

                this.load = function(options) {
                    if (list.loading) {
                        return;
                    }
                    list.loading = true;
                    list.loadingError = false;
                    if (list.cancelDefer !== null) {
                        list.cancelDefer.resolve();
                        list.cancelDefer = null;
                    }
                    list.cancelDefer = $q.defer();

                    list.contract = Restangular.one('contracts', options.contractId);
                    list.contract.withHttpConfig({
                        timeout: list.cancelDefer.promise
                    }).get().then(function (response) {
                        list.contractData = response;

                        list.posts = [];
                        response['bloggerPosts'].forEach(function(post) {
                            list.posts.push(new Post(post.type, post.url, post.title, post.date, post.info));
                        });
                        list.posts.push(new Post());
                        list.loading = false;
                        list.loadingError = false;

                    }, function() {
                        list.cancelLoad();
                        list.loadingError = true;
                    });
                };

                list.doneSent = false;
                list.doneLoading = false;
                list.doneError = false;

                this.done = function() {
                    list.doneLoading = true;
                    list.doneError = false;
                    list.doneSent = false;
                    list.contract.post('mark_blogger_posts_done').then(function(response) {
                        list.doneSent = true;
                        list.doneLoading = false;
                        list.doneError = false;
                    }, function() {
                        list.doneSent = false;
                        list.doneLoading = false;
                        list.doneError = true;
                    });
                };
            }

            return PostsList;
        }])



        .service('tsUtils', [function() {
            var self = this;

            this.getQueryVariable = function(variable) {
                var query = window.location.search.substring(1);
                var vars = query.split("&");
                for (var i=0; i < vars.length;i++) {
                    var pair = vars[i].split("=");
                    if (pair[0] == variable) {
                        return decodeURIComponent(pair[1].replace(/\+/g,' '));
                    }
                }
                return null;
            };

            this.objectMultiIndex = function(obj, is) {  // obj,['1','2','3'] -> ((obj['1'])['2'])['3']
                return is.length ? self.objectMultiIndex(obj[is[0]], is.slice(1)) : obj;
            };
            this.objectPathIndex = function(obj, is) {   // obj,'1.2.3' -> multiIndex(obj,['1','2','3'])
                return self.objectMultiIndex(obj, is.split('.'));
            };
            this.objectSetIndex = function(obj, is, value) {
                var list = is.split('.');
                if (list.length < 2)
                    return;
                self.objectMultiIndex(obj, list.slice(0, list.length - 1))[list[list.length - 1]] = value;
            };
            // pathIndex('a.b.etc');


            this.makeFormFieldsDirty = function (form) {
                angular.forEach(form, function(val, key) {
                    if (!key.match(/\$/)) {
                        val.$dirty = true;
                    }
                });
                form.$setDirty();
            };

            this.scrollToFirstInvalidElement = function (form) {
                angular.element('html, body').animate({
                    scrollTop: angular.element('form[name=' + form.$name + ']').find('.ng-invalid').first().offset().top - angular.element(window).height() / 2 + 100
                  }, 500);
            };

            this.formatAttachments = function(attachments) {
                if (attachments === undefined || attachments === null)
                    return [];
                return attachments.map(function(item) { return item.response; });
            };

        }])


        .service('tsSendEmail', ['$http', 'tsOutreachTemplate', function ($http, tsOutreachTemplate) {
            var self = this;

            self.setStateCb = null;

            self.data = {
                template: null,
                subject: null,
            };

            self.setState = function (state) {
                if (self.setStateCb) {
                    self.setStateCb(state);
                }
            };

            self.send = function (options) {
                return $http({
                    method: 'POST',
                    url: options.url,
                    data: {
                        template: options.template,
                        subject: options.subject,
                        sendMode: options.sendMode,
                    }
                });
            };

            
        }])



        .factory('tsInvitationTemplate', ['tsOutreachTemplate', function (tsOutreachTemplate) {
            var defaultBody = [
                "<p>Hi {{ getEscaped('user.first_name') }}!</p>",
                "<p>I stumbled across your blog a few month ago and bookmarked your site! I LOVE your style and photography so much!!</p>",
                "<p>I was wondering if you'd be interested in working together? Here is a link to my site for you to check out <a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a></p>",
                "<p>I have a few ideas for how we could collaborate but I just wanted to check with you to see if this sounds interesting!</p>",
                "<p>Thanks!</p>",
                "<p>{{ context.visitorUserName }}<br/>",
                    "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                "</p>",
                "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
            ].join('\n');
            var defaultSubject = "Interested in Collaborating?";

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])



        .factory('tsFollowupTemplate', ['tsOutreachTemplate', function (tsOutreachTemplate) {
            var defaultBody = [
                "<p>Hi {{ getEscaped('user.first_name') }},</p>",
                "<p>Just wanted to follow back up with you to see if you got my previous email about a potential collaboration.",
                "<p>I'd love to work with you and I have some great ideas around how we can set this up.",
                "<p>Please let me know what you think, </p>",
                "<p>{{ context.visitorUserName }}<br/>",
                    "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                "</p>",
                "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
            ].join('\n');
            var defaultSubject = "Interested in Collaborating?";

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])



        .factory('tsCollectDetailsTemplate', ['tsOutreachTemplate', function (tsOutreachTemplate) {
            var defaultBody = [
                "<p>Hey {{ getEscaped('user.first_name') }},</p></br>",
                "<p>Now that we've decided on the logistics, I just wanted to shoot you over a quick form for you to fill up with a few details for the campaign.</p></br>",
                "<p>To get to the form, just click on this link {{ getEscaped('user.collect_info_link') }}, and you'll land on the form page.</p></br>",
                "<p>If you could just review the details that are already filled in to make sure that they are correct. As well as fill in the remaining fields, I can get everything over to you very soon.</p></br>",
                "<p>I'm super excited to get started!</p></br>",
                "<p>{{ context.visitorUserName }}<br/>",
                    "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                "</p>",
                "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
            ].join('\n');
            var defaultSubject = "Collect Details";

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])



        .factory('tsReminderTemplate', ['tsOutreachTemplate', function (tsOutreachTemplate) {
            var defaultBody = [
                "<p>Hey {{ getEscaped('user.first_name') }},</p>",
                "<p>I just wanted to shoot you a quick reminder about your upcoming post! Whoohoo! I'm so excited for it to go live!</p>",
                "<p>Just for your quick reference, here is a <a href=''>link</a> to your campaign overview page with all of the details pertaining to the campaign.",
                "<p>And here is a <a href='{{ getEscaped('user.blogger_page_tracking_section') }}'>link</a> to your tracking codes. There are instructions on that page that will explain how to install them. It's super quick, I promise!</p>",
                "<p>Let me know if you need anything else form my end!</p>",
                "<p>Thanks again!</p>",
                "<p>{{ context.visitorUserName }}<br/>",
                    "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                "</p>",
                "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
            ].join('\n');
            var defaultSubject = "Reminder";

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])



        .factory('tsPaymentCompleteTemplate', ['tsOutreachTemplate', function (tsOutreachTemplate) {
            var defaultBody = [
                "<p>Hey {{ getEscaped('user.first_name') }},</p>",
                "<p>Just wanted to let you know that we've completed the payment!</p>",
                "<p>It's been a pleasure working with you, and we hope to collaborate again with you soon!</p>",
                "Thanks!",
                "<p>{{ context.visitorUserName }}<br/>",
                    "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                "</p>",
                "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
            ].join('\n');
            var defaultSubject = "Payment Complete";

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])



        .factory('tsPostsAddingTemplate', ['tsOutreachTemplate', function (tsOutreachTemplate) {
            var defaultBody = '';
            var defaultSubject = '';

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])


        .factory('tsPostApprovalTemplate', ['tsOutreachTemplate', function (tsOutreachTemplate) {
            var defaultBody = '';
            var defaultSubject = '';

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])



        .factory('tsShippingTemplate', ['tsOutreachTemplate', function (tsOutreachTemplate) {
            var defaultBody = [
                "<p>Hey {{ getEscaped('user.first_name') }},</p>",
                "<p>Just wanted to let you know your package is in the mail! In case you need it, here's the tracking code: {{ getEscaped('user.shipment_tracking_code') }}</p>",
                "<p>Would you mind doing me a quick favor? Whenever you get the package, would you mind coming back to this email and clicking the link below so that I know you have everything that you need?</p>",
                "<p><a href='{{ getEscaped('user.shipment_received_url') }}'>{{ getEscaped('user.shipment_received_url') }}</a></p>",
                "<p>Thank you so much! That's going to really help me! And looking forward to getting started!!!</p>",
                "<p>{{ context.visitorUserName }}<br/>",
                    "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                "</p>",
                "<p><a href='{{ campaign_overview_link }}'>P.S. Check out the campaign overview page for more details</a></p>",
            ].join('\n');
            var defaultSubject = "Shipping Reminder";

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])



        .factory('tsCampaignReportInvitation', ['tsOutreachTemplate', function (tsOutreachTemplate) {
             var defaultBody = [
                "<p>Hi {{ getEscaped('name') }},</p></br>",
                "<p>I wanted to send you a quick link to the live reporting page on our site. No login is necessary.</p></br>",
                "<p>Just click on this <a href='{{ messageData.publicLink }}'>link</a> to view the reporting data. Make sure to click on the Posts and UGC tabs as well.</p></br>",
                "<p>Let me know if you have any questions!</p>",
                "<p>Best,</p>",
                "<p>{{ context.visitorUserName }}</p>",
            ].join('');

            var defaultSubject = "Live reporting page for your {{ messageData.campaignName }}";

            return new tsOutreachTemplate(defaultBody, defaultSubject);
        }])



        .service('tsInvitationMessage', ['$interpolate', '$templateCache', function($interpolate, $templateCache) {
            var defaultBody = [
                "<p>Hi {{ getEscaped('user.first_name') }}!</p>",
                "<p>I stumbled across your blog a few month ago and bookmarked your site! I LOVE your style and photography so much!!</p>",
                "<p>I was wondering if you'd be interested in working together? Here is a link to my site for you to check out <a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a></p>",
                "<p>I have a few ideas for how we could collaborate but I just wanted to check with you to see if this sounds interesting!</p>",
                "<p>Thanks!</p>",
                "<p>{{ context.visitorUserName }}<br/>",
                    "<a href='http://{{ context.visitorBrandDomainName }}'>{{ context.visitorBrandName }}</a>",
                "</p>",
            ].join('\n');
            var defaultSubject = "Interested in Collaborating?";

            var getEscaped = function(name) {
                return "{{" + name + "}}";
            };

            var getTemplate = function(value, options) {
                var opts = {
                    getEscaped: getEscaped
                };
                angular.extend(opts, options || {})
                return $interpolate(value)(opts);
            };

            var getText = function(value, options) {
                return $interpolate(value)(options);
            };

            this.get = function(options) {
                return {
                    body: getText(options.body && options.body.length ? options.body : getTemplate(defaultBody, options), options),
                    subject: getText(options.subject && options.subject.length ? options.subject : getTemplate(defaultSubject, options), options),
                };
            };

            this.getBodyTemplate = function(body, options) {
                return getTemplate(body && body.length ? body : defaultBody, options);
            };

            this.getSubjectTemplate = function(subject, options) {
                return getTemplate(subject && subject.length ? subject : defaultSubject, options);
            };

            this.getBody = function(body, options) {
                return getText(body && body.length ? body : getTemplate(defaultBody, options), options);
            };

            this.getSubject = function(subject, options) {
                return getText(subject && subject.length ? subject : getTemplate(defaultSubject, options), options);
            };        
        }])



        .service('tsSendApprovalMessage', ['$interpolate', function($interpolate) {
            var defaultBody = [
                "<p>Hi {{ getEscaped('name') }},</p></br>",
                "<p>I've put together a list of influencers for you to review for your {{ messageData.campaignName }} Campaign.</p></br>",
                "<p>To review this list :</p>",
                "<p>1. Click on this <a href='{{ messageData.publicLink }}'>link</a>.</p>",
                "<p>2. From that page, click YES, NO, or MAYBE for all influencers in the list. (There might be more than one page, so please make sure to use the pagination at the bottom if applicable.)</p>",
                "<p>3. All of your selections will save automatically, so you can leave the page and return later to complete your review.</p>",
                "<p>4. You can also send this link to another team member to review, just make sure you do not click SUBMIT until you are finished with the list.</p>",
                "<p>5. As soon as you've finalized the list, just click the SUBMIT button and this form will get sent back to me.</p></br>",
                "<p>Let me know if you have any questions! As soon as I receive your selections, I'll begin outreach.</p>",
                "<p>Best,</p>",
                "<p>{{ context.visitorUserName }}</p>",
            ].join('');

            var defaultSubject = "{{ messageData.campaignName }} Campaign : Influencer Approval";

            var getEscaped = function(name) {
                return "{{" + name + "}}";
            };

            var moreOptions = function(options) {
                return {
                    name: options.messageData.name,
                    email: options.messageData.emai,
                };
            };

            var getTemplate = function(value, options) {
                var opts = {
                    getEscaped: getEscaped
                };
                angular.extend(opts, options || {})
                return $interpolate(value)(opts);
            };

            var getText = function(value, options) {
                var opts = {};
                angular.extend(opts, options);
                angular.extend(opts, moreOptions(options));
                return $interpolate(value)(opts);
            };

            this.getBodyTemplate = function(body, options) {
                return getTemplate(body ? body : defaultBody, options);
            };

            this.getSubjectTemplate = function(subject, options) {
                return getTemplate(subject ? subject : defaultSubject, options);
            };

            this.getBody = function(body, options) {
                return getText(body ? body : getTemplate(defaultBody, options), options);
            };

            this.getSubject = function(subject, options) {
                return getText(subject ? subject : getTemplate(defaultSubject, options), options);
            };      
        }])



        .service('tsDeliverables', function() {
            var self = this;

            self.range = function() {
                return _.range(1, 11);
            };

            self.getData = function() {
                return {
                    'Instagram': {value: null, single: 'instagram', plural: 'instagrams'},
                    'Twitter': {value: null, single: 'tweet', plural: 'tweets'},
                    'Pinterest': {value: null, single: 'pin', plural: 'pins'},
                    'Facebook': {value: null, single: 'facebook post', plural: 'facebook posts'},
                    'Youtube': {value: null, single: 'video', plural: 'videos'},
                    'Blog': {value: null, single: 'blog post', plural: 'blog posts'},
                };
            };

            self.get = function(existing) {
                var data = self.getData();
                if (existing) {
                    for (var i in existing) {
                        data[i].value = existing[i].value;
                    }
                }
                return data;
            };
        })



        .service('tsPlatformIconClasses', function() {
            var self = this;

            self.get = function(platform) {
                return {
                    'icon-social_globe3': ['blog', 'blog_posts'].indexOf(platform.toLowerCase()) > -1,
                    'icon-social_facebook': ['facebook'].indexOf(platform.toLowerCase()) > -1,
                    'icon-social_twitter': ['twitter', 'tweets'].indexOf(platform.toLowerCase()) > -1,
                    'icon-social_pinterest': ['pinterest', 'pins'].indexOf(platform.toLowerCase()) > -1,
                    'icon-social_instagram2': ['instagram', 'photos'].indexOf(platform.toLowerCase()) > -1,
                    'icon-social_youtube': ['youtube', 'videos'].indexOf(platform.toLowerCase()) > -1,
                    'icon-social_tumblr': ['tumblr'].indexOf(platform.toLowerCase()) > -1,
                };
            };
            self.getBase = function (platform) {
                return {
                    'social_globe3': ['blog', 'blog_posts'].indexOf(platform.toLowerCase()) > -1,
                    'social_facebook': ['facebook'].indexOf(platform.toLowerCase()) > -1,
                    'social_twitter': ['twitter', 'tweets'].indexOf(platform.toLowerCase()) > -1,
                    'social_pinterest': ['pinterest', 'pins'].indexOf(platform.toLowerCase()) > -1,
                    'social_instagram2': ['instagram', 'photos'].indexOf(platform.toLowerCase()) > -1,
                    'social_youtube': ['youtube', 'videos'].indexOf(platform.toLowerCase()) > -1,
                    'social_tumblr': ['tumblr'].indexOf(platform.toLowerCase()) > -1,
                };
            };
        })



        .service('tsBrandNavigation', ['$rootScope', '$q', function($rootScope, $q) {

            var navigation = this;

            this.configDefer = null;
            this.config = null;

            this.setSubTabActive = function(tabName) {
                navigation.config.sub_tab = tabName;            
            };

            this.setConfig = function(config) {
                navigation.config = config;
                navigation.configDefer.resolve();
            };

            function init() {
                navigation.configDefer = $q.defer();
            }

            init();

        }])



        .service('tsQueryCache', function() {
            var query;
            
            this.set = function(sent_query) {
                query = sent_query;
            };
            
            this.get = function() {
                return query;
            };
            
            this.reset = function() {
                query = null;
            };
            
            this.empty = function() {
                return query === null || query.length === 0 ? true : false;
            };

            this.reset();
        })



        .service('tsQueryResult', function() {
            var result;

            this.set = function(data) {
                result = {
                    results: [],
                    total: data.total
                };
                var items = data.results;
                if (!items) return;
                for (var i = 0; i < items.length; i++) {
                    result.results.push({
                        id: items[i].id,
                        pic: items[i].profile_pic_url ? items[i].profile_pic_url : items[i].pic
                    });
                }
            };

            this.get = function() {
                return result;
            };

            this.reset = function() {
                result = null;
            };

            this.reset();
        })



        .service('tsBloggerDetails', ['$q', '$http', '$timeout', function($q, $http, $timeout) {
            var LOAD_TIMEOUT = 20000;
            var DEFAULT_CHART_COLORS = ["#ff7d99", "#f5695a", "#ffd633", "#8df2ce", "#5fdaf4", "#2f83f5",
                "#0052c1", "#be85ff"];

            function Loader(endpoint) {
                var self = this;
                var deferred = $q.defer();

                self.load = function(url, params, handler) {
                    var timeout = $timeout(function() {
                        if (deferred !== null) {
                            deferred.resolve();
                            self.load(url);
                        }
                    }, LOAD_TIMEOUT);

                    return $http({
                        url: url,
                        method: 'GET',
                        params: params,
                        timeout: deferred.promise,
                    }).success(handler);
                };

                self.destroy = function() {
                    if (deferred) {
                        deferred.resolve();
                        deferred = null;
                    }
                };
            }

            function Section() {
                var self = this;

                self.isEmpty = function() {
                    return false;
                };

                self.destroy = function() {

                };
            }

            self.sections = {
                categoryCoverage: new Section(),
            }; 
        }])



        .service('tsStats', ['$http', '$q', function ($http, $q) {
        
            function Cache(endpoint) {
                var cached = [];
            
                return function(id, url) {
                    var deferred = $q.defer();
                    var created = new Date().getTime();
                    var i = cached.length;
                    var found = false;
                    var ttl = 0;

                    while (i--) {
                        if (cached[i].id() == id) {
                            if (cached[i].valid()) {
                                deferred.resolve(cached[i].data())
                                found = true;
                            } else {
                                cached.splice(i, 1);
                            }
                            break;
                        }
                    }
                    if (!found) {
                        $http.get(url)
                            .then(function(result) {
                                cached.push({
                                    id: function() {
                                        return id;
                                    },
                                    created: function() {
                                        return created;
                                    },
                                    valid: function() {
                                        return new Date().getTime() - created >= ttl ? false : true;
                                    },
                                    data: function() {
                                        return result.data;
                                    }
                                })
                                
                                deferred.resolve(cached[cached.length-1].data());
                            }, function(reason) {
                                deferred.reject(reason);
                            });
                    }
                    
                    return deferred.promise;
                }
            }
        
            function Visits() {
                return {
                    monthly: Cache('monthly_visits')
                }
            }

            function Traffic() {
                return {
                    shares: Cache('traffic_shares'),
                    topCountryShares: Cache('top_country_shares'),
                }
            }
            
            return {
                visits: Visits(),
                traffic: Traffic()
            }
        }]);

})();
