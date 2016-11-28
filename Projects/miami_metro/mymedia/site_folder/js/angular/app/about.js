'use strict';

angular.module('theshelf')

.controller('AboutBloggerCtrl', ['$scope', 'relfashion_stats', 'category_stats', 'popularity_sums', 'popularity_stats', 'posts',
    function($scope, relfashion_stats, category_stats, popularity_sums, popularity_stats, posts) {
        //if(!(relfashion_stats&&category_stats&&popularity_sums&&popularity_stats)){
        //    return;
        //}
        var donut_formatter = function(y, data) {
            return data.value + " / " + data.percentage + "%";  
        };
        var setup_morris = function(){
            try {
                Morris.Donut({
                    element: 'blog_stat_relfashion',
                    data: relfashion_stats,
                    formatter: donut_formatter,
                });
            } catch (e) {};
            try {
                Morris.Donut({
                    element: 'blog_stat_categories',
                    data: category_stats,
                    formatter: donut_formatter,
                });
            } catch (e) {};
            try {
                var followers_ykeys = [];
                var followers_labels = [];
                var comments_ykeys = [];
                var comments_labels = [];
                for(var idx = 0; idx < popularity_stats.series.length; idx++){
                    var serie = popularity_stats.series[idx];
                    if (popularity_sums[serie.key]["followers"] > 0) {
                        followers_ykeys.push(serie.key+"_num_followers");
                        followers_labels.push(serie.label+" followers");
                    }
                    if (popularity_sums[serie.key]["comments"] > 0) {
                        comments_ykeys.push(serie.key+"_num_comments");
                        comments_labels.push(serie.label+" comments");
                    }
                }
                if(popularity_stats.followers_data.length){
                    Morris.Area({
                        element: 'blog_stat_popularity_followers',
                        data: popularity_stats.followers_data,
                        xkey: 'date',
                        ykeys: followers_ykeys,
                        labels: followers_labels,
                        pointSize: 0,
                        lineWidth: 1,
                        hideHover: true,
                        fillOpacity: 0.1,
                        smooth: false,
                        behaveLikeLine: true,
                    });
                }
                if(popularity_stats.comments_data.length){
                    Morris.Area({
                        element: 'blog_stat_popularity_comments',
                        data: popularity_stats.comments_data,
                        xkey: 'date',
                        ykeys: comments_ykeys,
                        labels: comments_labels,
                        pointSize: 0,
                        lineWidth: 1,
                        hideHover: true,
                        fillOpacity: 0.1,
                        smooth: false,
                        behaveLikeLine: true,
                    });
                }
            } catch (e) {};
        };
        var setup_about_page = function(){
            // salvattore.init();
            setTimeout(setup_morris, 10);
        };
        setTimeout(setup_about_page, 100);
        $scope.posts = posts;
    }
])

.directive('endorsedBrands', ['$timeout',
    function($timeout) {
        return {
            restrict: 'A',
            scope: true,
            link: function(scope, iElement, iAttrs) {
                var all_brands, c_brands;

                var update = function(elems) {
                    iElement.find('.brands').children().remove();
                    iElement.find('.brands').append(elems);
                };

                scope.has_more_brands = function() {
                    if (!all_brands || !c_brands) return
                    return all_brands.length > c_brands.length;
                }
                scope.show_more_brands = function() {
                    c_brands = all_brands;
                    update(c_brands);
                };

                $timeout(function() {
                    all_brands = iElement.find('.brands').children();
                    c_brands = all_brands.slice(0, 20);
                    update(c_brands);
                }, 10);

            }
        };
    }
])


.directive('aboutBloggerPost', ['$sce', 'tagStripper',
    function($sce, tagStripper) {
        return {
            restrict: 'A',
            scope: true,
            link: function(scope, iElement, iAttrs) {

                var check_image = function(imgs) {
                    var img = imgs.shift();
                    var tmp_img = new Image();
                    if (img === undefined) {
                        iElement.remove();
                        return;
                    }
                    tmp_img.onerror = function() {
                        check_image(imgs);
                    };
                    tmp_img.onload = function() {
                        if (tmp_img.width < 200 || tmp_img.height < 200 || tmp_img.width > tmp_img.height * 3) {
                            check_image(imgs);
                        } else {
                            iElement.find(".post_pic img").attr('src', img);    
                            // scope.$apply(function() {
                            //     scope.item.post_img = img;
                            // });
                        }
                    };
                    tmp_img.src = img;
                }

                
                if (scope.post.post_image === null) {
                    if (scope.post.content_images !== undefined && scope.post.content_images !== null && scope.post.content_images.length > 0) {
                        check_image(scope.post.content_images);
                    } else {
                        iElement.find(".post_pic img").hide();
                    }
                } else {
                    // scope.post.post_img = scope.post.post_image;
                    iElement.find(".post_pic img").attr('src', scope.post.post_image);
                }
                iElement.find('.body_text').text(scope.post.content);
                iElement.find('.title').html(scope.post.title);
            }
        };
    }
])

.directive('photosGallery', ['photos',
    function(photos) {
        return {
            restrict: 'A',
            link: function(scope, iElement, iAttrs) {
                var idx = null;
                scope.percentage = 0;
                scope.photos = angular.copy(photos);
                
                var set_photo = function(dir) {
                    setTimeout(function() {
                        var img_c = iElement.find('img.current');
                        var img_n = iElement.find('img.next');
                        img_n.attr('src', scope.photos[idx]);
                        img_n.css({
                            opacity: 0,
                            display: "block",
                            position: "absolute",
                            top: 0,
                            left: 0
                        });
                        img_c.css({
                            opacity: 1
                        });
                        img_c.animate({
                            opacity: 0
                        }, {
                            duration: 100,
                            queue: false
                        });
                        img_n.animate({
                            opacity: 1
                        }, {
                            duration: 100,
                            queue: false,
                            complete: function() {
                                img_c.attr('src', scope.photos[idx]);
                                img_c.css({
                                    opacity: 1
                                });
                                img_n.css({
                                    opacity: 0,
                                    display: "none"
                                });
                            }
                        });
                    }, 10);
                };
                scope.prev = function() {
                    idx--;
                    if (idx < 0) idx = scope.photos.length - 1;
                    set_photo();
                };
                scope.next = function() {
                    idx++;
                    if (idx >= scope.photos.length) idx = 0;
                    set_photo();
                };
                setTimeout(function() {
                    var loaded = 0;
                    scope.loading = true;
                    var update_percentage = function() {
                        scope.percentage = Math.round(100.0 * loaded / scope.photos.length);
                        if (loaded == scope.photos.length) {
                            scope.loading = false;
                        }
                    };
                    iElement.find("img.photo_preload").error(function() {
                        var e_idx = $(this).data('index');
                        scope.$apply(function() {
                            scope.photos.splice(e_idx, 1);
                            if (scope.photos.length == 0) {
                                iElement.remove();
                            }
                            update_percentage();
                            if (e_idx == idx) {
                                idx = 0;
                                set_photo();
                            }
                        });
                    }).load(function() {
                        var l_idx = $(this).data('index');
                        if (idx === null) {
                            idx = 0;
                            set_photo();
                        }
                        loaded++;
                        scope.$apply(function() {
                            update_percentage();
                        });
                    });
                }, 0);

                iElement.hide();
                setTimeout(function() {
                    idx = 0;
                    set_photo();
                    iElement.fadeIn();
                }, 1000);

            }
        };
    }
])

.controller('AboutEditCtrl', ['$scope', 'profile_data', '$http', '$q', '$rootScope', 'brand_matcher', '$timeout', 'collab_types',
    function($scope, profile_data, $http, $q, $rootScope, brand_matcher, $timeout, collab_types) {
        var ac;
        $scope.profile_data = profile_data;
        $scope.oryg_profile_data = angular.copy(profile_data);
        $scope.profile_data.collaborations_modified = false;
        $scope.profile_data.ifb_modified = false;
        $scope.collab_types = collab_types;
        $scope.tmp_select_collab_type = angular.copy(collab_types[0]);

        $scope.tags = {
            style1: [
                "feminine",
                "girly",
                "flirty",
                "luxe",
                "chic",
                "sexy",
                "trendy",
                "rocker",
                "grungy",
                "edgy",
                "modern",
                "minimalist",
                "modest",
            ],
            style2: [
                "relaxed",
                "easy-going",
                "classic",
                "sophisticated",
                "timeless",
                "Southern",
                "preppy",
                "So-cal",
                "surfer",
                "sporty",
                "outdoors",
                "fitness",
                "eco-friendly",
            ],
            style3: [
                "casual",
                "tomboy",
                "free-spirit",
                "hippy",
                "boho",
                "ethnic",
                "global",
                "vintage",
                "retro",
                "whimsical",
                "colorful",
                "loud",
                "floral",
            ],
            blogger1: [
                "Street Fashion",
                "Celebrity Fashion",
                "Men's Fashion",
                "Women's Fashion",
                "Couple's Fashion",
                "Kid's Fashion",
                "Outfit-Of-The-Day",
                "Budget Fashion",
                "High-End Fashion",
                "Couture Fashion",
                "Plus-sized Fashion",
                "Ethnic Fashion",
                "Religious Fashion",
            ],
            blogger2: [
                "Modest Fashion",
                "Fashion by Occassion",
                "Beauty Bloggers",
                "Mommy-Blogger",
                "DIY ",
                "Lifestyle",
                "Teen Blogger",
                "College Blogger",
                "20s Something Blogger",
                "30s Something Blogger",
                "40s Something Blogger",
                "50s Something Blogger",
            ]
        };

        $scope.info_for_brands = [
            "sponsored posts",
            "product reviews",
            "giveaways",
            "banner ads",
            "brand ambassadors",
            "event coverage",
            "personal styling",
            "other",
        ];

        $scope.ifb_modified = function(ifb){
            if(isNaN(Number($scope.profile_data.info_for_brands.range_min[ifb]))){
                $scope.profile_data.info_for_brands.range_min[ifb] = 0;
            }
            if(isNaN(Number($scope.profile_data.info_for_brands.range_max[ifb]))){
                $scope.profile_data.info_for_brands.range_max[ifb] = 0;
            }
            $scope.profile_data.ifb_modified = true;
        }

        $scope.hasTag = function(tag_name) {
            return $scope.profile_data.tags.indexOf(tag_name)>=0;
        };

        $scope.toggleTag = function(tag_name) {
            var idx = $scope.profile_data.tags.indexOf(tag_name);
            if (idx >= 0) {
                $scope.profile_data.tags.splice(idx, 1);
            } else {
                $scope.profile_data.tags.push(tag_name);
            }
        };

        $scope.anyInfoVisible = function(){
            var is_visible = false;
            for(var i in $scope.profile_data.info_for_brands.enabled){
                is_visible = $scope.profile_data.info_for_brands.enabled[i];
                if(is_visible) break;
            }
            return is_visible;
        };

        $scope.anyCollabVisible = function(){
            var is_visible = false;
            for(var i = 0; i<$scope.profile_data.collaborations.length; i++){
                is_visible = $scope.collabVisible($scope.profile_data.collaborations[i]);
                if(is_visible) break;
            }
            return is_visible;
        };

        $scope.collabVisible = function(collab){
            return collab.brand_name && collab.brand_url && collab.post_url && collab.details;
        };

        $scope.addCollaboration = function() {
            $scope.profile_data.collaborations_modified = true;
            if($scope.last_collab_data.post_url.match(/https?:\/\//i) == null){
                $scope.last_collab_data.post_url = "http://"+$scope.last_collab_data.post_url;
            }
            if($scope.last_collab_data.brand_url.match(/https?:\/\//i) == null){
                $scope.last_collab_data.brand_url = "http://"+$scope.last_collab_data.brand_url;
            }
            $scope.profile_data.collaborations.push(angular.copy($scope.last_collab_data));
            // $("#campaign_date").val("");
            $rootScope.$broadcast('resetDateRangePicker');
            $scope.tmp_select_collab_type = angular.copy(collab_types[0]);
            $scope.last_collab_data = {
                brand_name: null,
                brand_url: null,
                post_url: null,
                details: null,
                collab_type: $scope.tmp_select_collab_type.text,
            };
        };

        $scope.removeCollaboration = function(idx) {
            $scope.profile_data.collaborations_modified = true;
            $scope.profile_data.collaborations.splice(idx, 1);
        };

        var ac_changed = function() {
            $scope.$apply(function() {
                var place = ac.getPlace();
                if (place !== undefined && place.formatted_address !== undefined) {
                    $scope.profile_data.location = place.formatted_address;
                }
            });
        };

        $scope.stringify = function(obj) {
            return JSON.stringify(obj);
        };

        $scope.save = function(){
            if($scope.collab_form !== undefined && $scope.collab_form.$valid){
                $scope.addCollaboration();
                $timeout($scope.save, 10);
                return;
            }
            $scope.profile_data
            $(window).unbind("beforeunload");
            $scope.$broadcast("openEditProfilePopup", $scope.profile_data);
        };

        setTimeout(function() {
            ac = new google.maps.places.Autocomplete($("input#location")[0], {
                types: ["(cities)"]
            });
            ac.changed = ac_changed;
            if($scope.profile_data.location){
                $("input#location").val($scope.profile_data.location);
            }
        }, 10);

        $scope.last_collab_data = {
            brand_name: null,
            brand_url: null,
            post_url: null,
            details: null,
            collab_type: $scope.tmp_select_collab_type.text,
            timestamp: null,
        };

        $scope.updateCollabType = function(selected) {
            if (selected !== undefined) {
                $scope.last_collab_data.collab_type = selected.text;
            }
        };

        $scope.$watch('profile_data', function(){
            if(angular.equals($scope.profile_data, $scope.oryg_profile_data)){
                $(window).unbind("beforeunload");
            }else{
                $(window).bind("beforeunload", function() {
                    return "You have unsaved changes!";
                });
            }
        }, true);

        $scope.autocomplete_timeout = null;

        $scope.doAutocomplete = function(){
            $scope.term = $scope.last_collab_data.brand_name;
            $scope.autocomplete_message = "Loading...";
            $scope.autocomplete_results = null;
            $http({
                url: brand_matcher+"?term="+$scope.term,
                method: "GET"
            }).success(function(data){
                $scope.autocomplete_results = data;
                $scope.autocomplete_message = null;
            }).error(function(){
                $scope.autocomplete_message = "Error!";
                $scope.autocomplete_results = null;
            });
        }

        $scope.startAutocompleteTimeout = function(){
            if($scope.autocomplete_timeout !== null){
                $timeout.cancel($scope.autocomplete_timeout);
            }
            $scope.autocomplete_timeout = $timeout($scope.doAutocomplete, 500);
        }

        $scope.selectResult = function(result){
            $scope.last_collab_data.brand_name = result;
            $scope.autocomplete_results = [];
        }

        // $("#campaign_date").datepicker().on('changeDate', function(ev){
        //     $scope.$apply(function(){
        //         $scope.last_collab_data.timestamp = ev.date;
        //     });
        // }).on('show', function(ev){
        //     $('.datepicker').css({'top': $("#campaign_date").position().top+40+'px', 'position': 'absolute', 'left': $("#campaign_date").position().left-65+'px'});
        // });

        $scope.dateRangeDefer = $q.defer();

        $scope.dateRangeDefer.promise.then(function() {
            $rootScope.$broadcast('resetDateRangePicker');
        });

        $scope.dateRangeModel = {
            startDate: null,
            endDate: null,
        };

        $scope.applyDateRange = function() {
            $scope.last_collab_data.timestamp = $scope.dateRangeModel.startDate;
        };

        $scope.$watch('dateRangeModel.startDate', function(nv, ov) {
            $scope.applyDateRange();
        });

        $('#id_brandname').keyup(function(){
            //$scope.startAutocompleteTimeout();
        });

        $('#id_brandname').blur(function(e){
            $(".brand-autocomplete").fadeOut(500);
            $timeout(function(){
                $scope.autocomplete_results = null;
            }, 500);
        });

        var set_cover_img = function(url){
            if(url !== null && url.length>0){
              setTimeout(function() {
                $(".cover_img").children().remove();
                $(".cover_img").append($("<img src='"+url+"?r="+Math.random()+"'/>"));
              }, 10);
            }
        };
        $scope.$on("coverImageSet", function(their_scope, url){
            set_cover_img(url);
        });

        var set_profile_img = function(url){
            if(url !== null && url.length>0){
              setTimeout(function() {
                $(".profile_pic").children().remove();
                $(".profile_pic").append($("<img src='"+url+"?r="+Math.random()+"'/>"));
              }, 10);
            }
        };
        $scope.$on("profileImageSet", function(their_scope, url){
            set_profile_img(url);
        });

        if(profile_data.cover_img_url){
            set_cover_img(profile_data.cover_img_url);
        }
        if(profile_data.profile_img_url){
            set_profile_img(profile_data.profile_img_url);
        }

        //if(defaults.cover_img_url){
        //  set_cover_img(defaults.cover_img_url);
        //}

        // $.widget( "custom.citycomplete", $.ui.autocomplete, {
        //     _renderItem: function( ul, item ) {
        //         var idx = item.label.indexOf(this.term);
        //         var itemhtml = $( "<a>" ).html( item.label.substr(0, idx) + "<b>" + this.term + "</b>" + item.label.substr(idx+this.term.length));
        //         return $( "<li>" )
        //             .append( itemhtml )
        //             .appendTo( ul );
        //     },
        // });

        // angular.element('#id_brandname').citycomplete({
        //     minLength: 2,
        //     source: brand_matcher,
        //     select: function( event, ui ) {
        //         $scope.$apply(function(){
        //             $scope.params.zipcode = ui.item.value;
        //             $scope.params.location = $scope.options.location.filter(function(elem) {
        //                 return elem.name == ui.item.city;
        //             })[0].id;
        //         });
        //     }
        // });
    }
])


;
