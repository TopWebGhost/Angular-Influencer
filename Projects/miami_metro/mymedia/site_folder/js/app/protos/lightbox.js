/**
 * Author: Bobby
 * Purpose: This file is loaded with core so exists on all our pages. Along with feed.js, this is our most important
 * JS file. It provides implementation of all the lightboxes which exist on our site. The Base LightBox which all
 * specific implementations make a call up the prototype chain to has significant hooks exposed which allow for customization
 * to pretty much any degree.
 */


/*
 LIGHTBOXES
 */
/**Lightbox Constructor & Prototype Definitions**/
/*
 Lightbox required params are:
 -selector: the css selector for this lightbox
 */
function LightBox(selector, options) {
    this.selector = selector;
    this.is_fixed = options.is_fixed || false;
    this.dark_background = options.dark_background || false;
    this.black_overlay = options.black_overlay || false;
    this.white_overlay = options.white_overlay || false;

    this.is_nested = false;
    this.is_nested_in = null;
    this.cascade_close = options.cascade_close || false; /* if set to true, when this popup is closed, every popup that nests it will also close */
    this.is_open = false;
    this.is_item_details_lb = false;

    this.keep_overlay_on_close = false; /* if set, the black overlay wont go away when this lightbox is closed */

    this.on_open_cb = options.on_open_cb;
    this.on_close_cb = options.on_close_cb;

    this.nested_popups = [];

    /* if this instance of a lightbox has click bindings or validation, set it up now */
    this.click_bindings && this.click_bindings();
    this.load_bindings && this.load_bindings();
    this.setup_validation && this.setup_validation();

    this.init();
}

function PhotoLightBox(selector, options) {
    this.use_cropper = options['cropper'];
    LightBox.call(this, selector, options);
}


function SignupLightBox(selector, options) {
    LightBox.call(this, selector, options);
    this.signup_type = null;
    this.next_steps_url = undefined;
    this.block_submit = false;
}


function ImageUploadLightBox(selector, options) {
    LightBox.call(this, selector, options);
    this.dz = null /* the dropzone for this lightbox */
}

function EditProfileLightBox(selector, options) {
    LightBox.call(this, selector, options);

    this.image_uploader = LightBox.get_by_type("image_upload");
    this.form_snapshot = $(this.selector).find('#edit_profile_form').clone(true);
    this.about_url = $(this.selector).data('aboutUrl');

    this.nested_popups = [];
    this.anything_changed = false;
    this.save_clicked = false;
}

function AddItemToShelvesLightBox(selector, options) {
    LightBox.call(this, selector, options);

    this.selected_shelves = {};
    this.close_on_done = true;
}

function ChooseLotteryWinnerLightBox(selector, options) {
    LightBox.call(this, selector, options);

    this.winner_template = $('#lottery_winner_tpl').html();
    this.loader = new Loader($(this.selector).find('.co_loader_non_ajax'), null);

    this.giveaway_updated = false;
    this.winner_chosen = false;
}

function AffiliateLinkShelfLightBox(selector, options) {
    this.item_tpl = $("#affiliate_link_item_tpl").html();
    this.added_item_tpl = $('#added_affiliate_link_tpl').html();

    this.sidebar = null;
    this.created_shelf = null;

    this.num_added = 0;
    this.num_starting_links = 6;

    LightBox.call(this, selector, options);
}

function GenericConfirmationLightBox(selector, options) {
    this.positive_cb = null;
    this.negative_cb = function() {
        this.close();
    };
    LightBox.call(this, selector, options);
}

function GenericMessageLightBox(selector, options) {
    LightBox.call(this, selector, options);
}

function GenericFormLightBox(selector, options) {
    this.form_selector = options['form_selector'];
    this.form_submit_selector = options['form_submit_selector'];

    this.silent_submit = options['silent_submit'];
    this.clicked_text = options['clicked_text'] || "Saving...";
    this.finished_text = options['finished_text'] || "Saved";
    this.success_cb = options['success_cb'] || null;
    this.additional_listeners = options['additional_listeners'] || function() {};

    this.validator = null;
    this.block_submit = false;

    this.additional_listeners();
    LightBox.call(this, selector, options);
}





/*****-----*****----*****-----*****----- All LightBoxes -----*****-----*****-----*****-----*****/





/**--Helpers--**/
/*
 close the lightbox on click outside of the lightbox content area
 */
LightBox.prototype.close_on_outside_click = function() {
    var _this = this;
    $(this.selector).on('click', function(evt) {
        if ($(evt.target).closest('.content_area').length < 1) {
            _this.cascade_close ? LightBox.close_all_open() : _this.close();
        }
    });
};

/*
make a lightbox a nested lightbox
@param nested_in - the lightbox this lightbox is nested in
@return this lightbox
 */
LightBox.prototype.make_nested = function(nested_in) {
    this.is_nested = true;
    this.is_nested_in = nested_in;
    $(this.selector).addClass('nested_lightbox');

    return this;
}

/*
remove nested features from a lightbox
 */
LightBox.prototype.unmake_nested = function() {
    this.is_nested = false;
    $(this.selector).removeClass('nested_lightbox');
    return this;
}

/*
get all open lightboxes in this lightboxes list of nested lightboxes
 */
LightBox.prototype.get_open_nested = function() {
    var open_nested = [];

    for (var i = 0, len = this.nested_popups.length ; i < len ; i++) {
        if (this.nested_popups[i].is_open) {
            open_nested.push(this.nested_popups[i]);
        }
    }

    return open_nested;
}
/**--End Helpers--**/

LightBox.prototype.init = function() {
    /*set up css classes of a lightbox*/
    this.is_fixed && $(this.selector).addClass('fixed');
    this.dark_background && $(this.selector).addClass('bl_bg_lb');

    /*bind the lightbox close event*/
    var _this = this;
    $(this.selector).find('.lightbox_close').click(function(evt) {
        _this.cascade_close ? LightBox.close_all_open() : _this.close();
        evt.stopPropagation();
    });

    /* bind for close of lightbox on click outside container */
    this.close_on_outside_click();

    /* call the created callback for this lightbox if it exists*/
    this.created_callback && this.created_callback();
};

/*
a method to open this lightbox
 */
LightBox.prototype.open = function() {

    var $overlay = this.black_overlay ? $('body>.black_overlay, body span>.black_overlay') : $('body>.white_overlay, body span>.white_overlay');

    /* if this isnt a nested popup, then when another popup is opened, start by closing any open lightboxes */
    !this.is_nested && LightBox.close_all_open();
    /*show the lightbox, it has to be shown in different ways based on whether or not its fixed*/
    this.is_fixed ? $(this.selector).show() : $(this.selector).addClass("dynamic");
    this.is_open = true;

    /* freeze the body, show the black overlay if appropriate */
    $('body').addClass('height_stop')
    if (this.black_overlay || this.white_overlay) {
        $overlay.show();
    }

    /* trigger an event that will let listeners know that the popup is visible */
    $(this.selector).trigger(this.selector+"_visible");

    /*if this is a nested popup, add class nested overlay to the black overlay */
    this.is_nested && $overlay.addClass('nested_overlay');

    /* item details lightboxes need to jump through some hoops, they have the same styles as nested lightboxes but without the extra caveats */
    this.is_item_details_lb && $(this.selector).addClass('item_details_lightbox');
    this.is_item_details_lb && $overlay.addClass('item_details_overlay');

    this.on_open_cb && this.on_open_cb();

    $(this.selector).trigger('popupOpen');

    $overlay.css({"z-index": 50});
    $(this.selector).css({"z-index": 51});

    return this;
};

/*
 a method to close this lightbox
 */
LightBox.prototype.close = function() {
    var $overlay = this.black_overlay ? $('body>.black_overlay, body span>.black_overlay') : $('body>.white_overlay, body span>.white_overlay');
    this.is_fixed ? $(this.selector).hide() : $(this.selector).removeClass("dynamic");
    this.is_open = false;


    if(this.on_close_cb){
        var ret = this.on_close_cb();
        if(ret === true) return;
    }

    /*
     only hide the dark overlay and remove height stop if this is not a nested popup
     */
    if (!this.is_nested && !this.keep_overlay_on_close && !this.is_item_details_lb) {
        $overlay.hide();
    } else {
        $overlay.removeClass('nested_overlay');
    }
    $('body').removeClass('height_stop');

    /* item details lightboxes need to jump through some hoops, they have the same styles as nested lightboxes but without the extra caveats */
    this.is_item_details_lb && $(this.selector).removeClass('item_details_lightbox');
    this.is_item_details_lb && $overlay.removeClass('item_details_overlay');

    /* if this lightbox instance has extra close bindings, perform them now */
}

/*
 a method to close all open lightboxes
 */
LightBox.close_all_open = function() {
    for (var lb in created_lightboxes) {
        created_lightboxes[lb].is_open && created_lightboxes[lb].close();
    }
};


/* Factory Methods */
/** Generally, the get_by_type and manual_open should be the only things you use to create a lightbox programatically **/
/*
factory method to create a lightbox by its type, without opening it
@param popup_type - the type of the popup to create
 */
LightBox.get_by_type = function(popup_type) {
    return singleton_lightbox(popup_type, false);
}

/*
 factory method to create and open a lightbox
 @return the opened lightbox
 */
LightBox.manual_open = function(popup_type) {
    return singleton_lightbox(popup_type, true);
}





/*****-----*****----*****-----*****----- SignupLightBox Specific -----*****-----*****-----*****-----*****/


SignupLightBox.prototype = Object.create(LightBox.prototype);
SignupLightBox.prototype.constructor = SignupLightBox;

/**-- SignupLightBox Properties --**/
SignupLightBox.prototype.steps = {
    TYPE: 1,
    INFO: 2,
    PIC: 3
};

/**-- SignupLightBox Helpers --**/
/*
go to the given step
@param step - the step to go to
 */
SignupLightBox.prototype.goto_step = function(step) {
    var $all_steps = $(this.selector).find('.content_area_container'),
        $step_container = $(this.selector).find('.content_area_container[data-step='+step+']');

    /* hide the current step, show the next step */
    $all_steps.addClass('hidden');
    $step_container.removeClass('hidden');
};

/*
go to the next step in the login / signup process
@param button - the Next/continue button that was clicked
 */
SignupLightBox.prototype.goto_next_step = function(button) {
    var $container = button.closest('.content_area_container'),
        next_step = parseInt($container.data('step')) + 1;


    if (next_step >= this.steps.PIC) {
        this.close()
    }

    /* close the lightbox after finishing pic upload (or, if the user isnt a blogger, then after the info step) */
    // if (next_step > this.steps.PIC || (this.signup_type != 'blogger' && next_step == this.steps.PIC)) {
    //     this.close()
    // }

    /* hide the current step, show the next step */
    $container.addClass('hidden');
    var $to_show = $container.nextAll('.content_area_container[data-step='+next_step+']');
    $to_show.removeClass('hidden');
};

/**-- SignupLightBox Bindings --**/
SignupLightBox.prototype.setup_validation = function() {
    $('.sign_log_form').each(function() {
        setup_validation($(this).get(0));
    });
};

SignupLightBox.prototype.click_bindings = function() {
    var _this = this;

    $(this.selector).on('click', '.user_type_itm', function(evt) {
        var blogger_signup_form = $(_this.selector).find('.blogger_signup_form'),
            brand_signup_form = $(_this.selector).find('.brand_signup_form'),
            shopper_signup_form = $(_this.selector).find('.shopper_signup_form');

        /* if the popup was re-opened, we mightve had a different type of form shown before, so start by hiding all forms */
        $(_this.selector).find('.form_container').addClass('hidden');

        _this.signup_type = $(this).data('signupType');
        if (_this.signup_type == 'blogger') {
            blogger_signup_form.removeClass('hidden');
        } else if (_this.signup_type == 'brand') {
            brand_signup_form.removeClass('hidden');
        } else {
            shopper_signup_form.removeClass('hidden');
        }
    });

    $(this.selector).on('click', '.next_btn, .skip_link', function(evt) {
        evt.preventDefault();
        _this.goto_next_step($(this));
    });

    $(this.selector).on('click', '.profile_pic_custom', function() {
        var image_upload_lb = LightBox.get_by_type('image_upload');

        image_upload_lb.make_nested(_this);
        image_upload_lb.set_action('/image_upload/?profile_img=1', _this.next_steps_url);
        image_upload_lb.set_aspect_ratio(1);
        image_upload_lb.open();
    });

    $(this.selector).on('click', '.social_facebook', function() {
        F.connect(this.parentNode);
        return false;
    });
};

SignupLightBox.prototype.load_bindings = function() {
    var _this = this;

    $(this.selector).find('.sign_log_form').submit(function(evt) {
        evt.preventDefault();
        _this.next_steps_url = $(this).data('nextSteps');

        if ($(this).valid() && $(this).find('.terms input').is(':checked')) {
            var deferred = ajax_form_submit.apply($(this), []),
                $submit_button = $(this).find('.submit_button');

            deferred.success(function(data) {
                var parsed = $.parseJSON(data);
                _this.next_steps_url = parsed.url;
                _this.goto_next_step($submit_button);

                // if (_this.signup_type === "brand") {
                //     var parsed = $.parseJSON(data);
                //     _this.next_steps_url = parsed.url;
                // }
                // _this.goto_next_step($submit_button);
            });
        }
    });

    $(this.selector).find('.facebook_form_signup').submit(function(evt) {
        _this.block_submit && evt.preventDefault();
    });

    this.on_open_cb = function() {
        this.signup_type = null;
        this.goto_step(1);
    };

    this.on_close_cb = function() {
        if (this.next_steps_url) {
            window.location = this.next_steps_url;
            return true;
        }
    };
};

SignupLightBox.prototype.submit_fb_form = function() {
    $(this.selector).find('.facebook_form_signup').submit();
};

SignupLightBox.prototype.select_blogger = function() {
    setTimeout(function() {
        $(".next_btn[data-signup-type=blogger]").click()
    }, 10);
};

SignupLightBox.prototype.select_brand = function() {
    setTimeout(function() {
        $(".next_btn[data-signup-type=brand]").click()
    }, 10);
};



/*****-----*****----*****-----*****----- ImageUploadLightBox Specific -----*****-----*****-----*****-----*****/





ImageUploadLightBox.prototype = Object.create(LightBox.prototype);
ImageUploadLightBox.prototype.constructor = ImageUploadLightBox;

/**-- ImageUploadLightBox Functions --**/
/*
a function to do onload bindings for this image upload lightbox
 */
ImageUploadLightBox.prototype._validate_cropped = function() {
    var is_valid = true;
    $('#upload_form').find('input.req').each(function() {
        is_valid = is_valid && $(this).val() != '';
    });
    return is_valid;
}

/**-- ImageUploadLightBox Functions --**/
/*
non-click bindings
 */
ImageUploadLightBox.prototype.load_bindings = function() {
    var _this = this;
    $(this.selector).find('#upload_form').submit(function(evt) {
        var $error = $(_this.selector).find('.error');
        if (!_this._validate_cropped()) {
            $error.removeClass('hidden');
            return false;
        } else {
            $error.addClass('hidden');
        }
    });
}

/*
this function clears all of the inputs which hold values relating to cropping, also clears any errors that might have shown
 */
ImageUploadLightBox.prototype.clear_cropping_vals = function() {
    $(this.selector).find('.req').val('');
    $(this.selector).find('.error').addClass('hidden');
}

/*
a function to set the action for this image upload
@param new_action - the action to set for this image uploader
@param next (optional) - if set, this will be the next location to go to after upload...defaults to the current document url
 */
ImageUploadLightBox.prototype.set_action = function(new_action, next) {
    $('#upload_form').attr('action', new_action+"&next="+(next ? next : document.URL));
}

/*
a function to set the aspect ratio for this image upload
@param ratio - the aspect ratio to set
 */
ImageUploadLightBox.prototype.set_aspect_ratio = function(ratio) {
    $('.image-aspect-ratio').text(ratio);
}

/*
a function to set the Dropzone instance for this image upload lightbox
@param dropzone - the dropzone instance for this lightbox
 */
ImageUploadLightBox.prototype.set_dropzone = function(dz) {
    this.dz = dz;
}





/*****-----*****----*****-----*****----- EditProfileLightBox Specific -----*****-----*****-----*****-----*****/





EditProfileLightBox.prototype = Object.create(LightBox.prototype);
EditProfileLightBox.prototype.constructor = EditProfileLightBox;

/**-- EditProfileLightBox Properties --**/
EditProfileLightBox.prototype.selectors = {
    form: '#edit_profile_form',
    save_btn: '.save_edit',
    cancel_btn: '.cancel_edit'
}

/**-- EditProfileLightBox Helpers --**/
/*
a function to setup the image uploader for a given image in the collage
@param image - the image to set up the upload form for
 */
EditProfileLightBox.prototype._set_image_upload_action = function(image) {
    var collage_number = $(this.selector).find('.collage-image').index(image) + 1,
        aspect_ratio = image.width() / image.height();

    this.image_uploader.set_action('/image_upload/?collage_image='+collage_number);
    this.image_uploader.set_aspect_ratio(aspect_ratio);
};

/*
a function to show the content of a screen in the lightbox
@param show - the selector for the screen to show
 */
EditProfileLightBox.prototype._show_screen = function(show) {
    /* hide all account forms, show this one */
    $('.account_lb').addClass('hidden');
    $(show).removeClass("hidden");
};

/*
setup validation for this lightbox
 */
EditProfileLightBox.prototype.setup_validation = function() {
    setup_validation(this.selectors.form);
    /* also set up validation for the  change email, change password forms */
    setup_validation(".change_password_form");
    setup_validation(".change_email_form");
};

/*
a function to check if the form is currently valid
@return true if so, false otherwise
 */
EditProfileLightBox.prototype._form_valid = function() {
    return $(this.selectors.form).valid();
}

/**-- EditProfileLightBox Functions --**/
/*
non-click bindings
 */
EditProfileLightBox.prototype.load_bindings = function() {
    var _this = this;

    $(this.selector).find(this.selectors.form).submit(function(evt) {
        evt.preventDefault();
        $.post($(this).attr('action'), $(this).serialize(), function(resp) {
            _this.anything_changed = false;
            $(_this.selectors.cancel_btn).addClass("inactive");
            $(_this.selector).find(_this.selectors.save_btn).text("Saved");
        })
    });

    /* simulate click of submit button when enter key pressed from within form field */
    $(this.selector).find(this.selectors.form).find('input,textarea').keydown(function(e) {
        _this.anything_changed = true;
        $(_this.selectors.cancel_btn).removeClass("inactive");
        $(_this.selectors.save_btn).text("Save");
        if (e.which == 13)  { //enter key
            $(_this.selector).find(_this.selectors.save_btn).click();
            return false;
        }
    });

    /* on open, make the image upload and contact us lightboxes nested */
    this.on_open_cb = function() {
        this.image_uploader.make_nested(this);
        LightBox.get_by_type('contact_us').make_nested(_this);
    };

    /* on close, reload the about page if anything has changed so any changes can take effect */
    this.on_close_cb = function() {
        this.image_uploader.unmake_nested();
        LightBox.get_by_type('contact_us').unmake_nested();

        if (_this.save_clicked) {
            window.location = _this.about_url;
        } else {
            $(_this.selector).find('#edit_profile_form').replaceWith(_this.form_snapshot);
            _this.form_snapshot = _this.form_snapshot.clone(true);
        }
    }
};

EditProfileLightBox.prototype.click_bindings = function() {
    var _this = this;

    /* bindings for the collage image upload */
    $(this.selector).find('.collage-image.editable').click(function() {
        _this._set_image_upload_action($(this));
        _this.image_uploader.open();
    });

    /*
     Cases are:
     1) User clicks save -> popup saying "changes have been saved. Keep editing or close popup?"
     2) User clicks cancel -> if user has stuff filled out, popup saying "unsaved changes, are you sure you want to cancel?" ->
     If yes, clear out fields, close popup : If no, leave popup open
     3) User clicks outside popup without saving -> Same actions as second case
     */
    $(this.selector).find(this.selectors.save_btn).click(function(evt) {
        var $_this = $(this);

        if (_this._form_valid.apply(_this, [])) {
            $_this.text('Saving');

            $(_this.selector).find(_this.selectors.form).submit();

            _this.save_clicked = true;
        }
    });

    $(this.selector).find(this.selectors.cancel_btn).click(function(evt) {
        evt.preventDefault();
        var confirmation_lb = LightBox.get_by_type("generic_confirmation").set_message("Are you sure you want to cancel? You have some changes that are unsaved");
        confirmation_lb.set_positive_cb(LightBox.close_all_open, confirmation_lb);
        confirmation_lb.set_negative_cb(confirmation_lb.close, confirmation_lb);
        confirmation_lb.make_nested(_this);

        if (_this.anything_changed) {
            confirmation_lb.open();
        } else {
            _this.close();
        }
    });

    /**-- Change email / password form bindings --**/
    $(this.selector).find('.open_account_form').click(function() {
        /* slide closed any forms that might be open */
        $(_this.selector).find('.account_settings_form').slideUp();
        /* slide open the right account form */
        $(this).parent().find($(this).data('for')).slideDown();
        /* show all buttons to open account forms except for the button that was just clicked */
        $(this).closest('.account_settings').find('.open_account_form').show();
        $(this).hide();
    });
    $(this.selector).find('.save_account_form').click(function(evt) {
        $(this).closest('form').valid() && ajax_form_submit.apply($(this).parent(), []);
    });
    $(this.selector).find('.cancel_account_form').click(function(evt) {
        $(this).parent().slideUp();
        /* show all buttons to open account forms */
        $(this).closest('.account_settings').find('.open_account_form').show();
    });

    /**-- Delete Account Bindings --**/
    $(this.selector).find('.delete_account').click(function(evt) {
        evt.preventDefault();
        var delete_url = $(this).attr('href'),
            confirmation_lb = LightBox.get_by_type("generic_confirmation").set_message("Are you sure you want to delete your account?");

        confirmation_lb.make_nested(_this);
        confirmation_lb.set_positive_cb(function() {
            $(this.selectors.pos_btn).text('Working...');
            $.post(delete_url, {}).done(redirect_cb);
        }, confirmation_lb);
        confirmation_lb.set_negative_cb(confirmation_lb.close, confirmation_lb);

        confirmation_lb.open();
    })
};

/*
a function to set the start screen for this edit profile lightbox
@param start_screen - the screen to open by default
@return this lightbox
 */
EditProfileLightBox.prototype.set_start_screen = function(start_screen) {
    this._show_screen(start_screen);

    return this;
};




/*****-----*****----*****-----*****----- AffiliateLinkShelfLightBox Specific -----*****-----*****-----*****-----*****/





AffiliateLinkShelfLightBox.prototype = Object.create(LightBox.prototype);
AffiliateLinkShelfLightBox.prototype.constructor = AffiliateLinkShelfLightBox;


/**-- AffiliateLinkShelfLightBox Helpers --**/
/*
add a new un-filled affiliate link to be filled in by the user
@return the new number of affiliate links added by the user
 */
AffiliateLinkShelfLightBox.prototype._add_affiliate_link = function() {
    var links_list = $(this.selector).find('.links_list'),
        compiled = _.template(this.item_tpl);

    links_list.append(compiled({link_num: this.num_added}));
    setup_validation("#affiliate_link_form"+this.num_added);
    this.num_added++;

    return this.num_added;
};


/**-- AffiliateLinkShelfLightBox Bindings --**/
AffiliateLinkShelfLightBox.prototype.click_bindings = function() {
    var _this = this;
    /* add a new affiliate link binding */
    $(this.selector).on('click', '.save_affiliate_link', function(evt) {
        var form = $(this).closest('form');
        if (form.valid()) {
            var link = $(this).parent().find('.affiliate_link_input').val(),
                shelf = $(_this.selector).find('.shelf_name').val(),
                post_url = $(this).data('postUrl'),
                $container = $(this).closest('li');
            /* show the loader */
            new Loader($(this).parent().find('.ajax_loader'), null).toggle_visibility();

            /* create and add a new affiliate link input field to the DOM (only if we've run out of our original placeholder links) */
            _this.num_added = (_this.num_added + 1) - _this.num_starting_links >= _this.num_starting_links ? _this._add_affiliate_link() : _this.num_added + 1;
            $(this).hide();

            /* post to the url which will call a celery task for getting the wishlist item for the selected link / shelf */
            $.post(post_url, {link: link, shelf: shelf}).done(function(data) {
                var json_data = $.parseJSON(data),
                    status_url = json_data['status_url'],
                    task_id = json_data['task'];

                /* only executed if this is the first affiliate link that was saved */
                if (!_this.created_shelf) {
                    _this.created_shelf = _this.sidebar.add_new_shelf(json_data);
                    _this.sidebar.sort_elements(".shelf_name");
                }

                /* until we get back a result saying that the task is done processing, make get request for task status recursively */
                (function get_status() {
                    $.get(status_url, {task: task_id}).fail(function() {
                        setTimeout(get_status, 5000);
                    }).success(function(data) {
                        var compiled = _.template(_this.added_item_tpl);
                        $container.replaceWith(compiled($.parseJSON(data)));
                    });
                })();
            });
        }
    });

    $(this.selector).on('click', '.next_btn', function(evt) {
        var form = $(".create_shelf_form");
        if (form.valid()) {
            $(_this.selector).find('.create_shelf').addClass('hidden');
            $(_this.selector).find('.add_affiliate_links').removeClass('hidden');
        }
    });

    /* delete item binding */
    $(this.selector).on('click', '.delete_btn', function(evt) {
        var delete_url = $(this).data('deleteUrl');
        $.post(delete_url);
        $(this).closest('.added_item').remove();
    });

    $(this.selector).on('click', '.finish_btn', function(evt) {
        _this.close();
    });
};

AffiliateLinkShelfLightBox.prototype.load_bindings = function() {
    /* create some placeholder affiliate links in the beginning */
    for (var i = 0 ; i < this.num_starting_links ; i++) {
        this._add_affiliate_link();
    }

    setup_validation(".create_shelf_form");

    $(this.selector).on('submit', 'form', prevent_default_cb());

    this.on_close_cb = function() {
        this.created_shelf && this.sidebar.filter(this.created_shelf);
    }
};


/**-- AffiliateLinkShelfLightBox Public Functions --**/
AffiliateLinkShelfLightBox.prototype.set_sidebar = function(sidebar) {
    this.sidebar = sidebar;
};





/*****-----*****----*****-----*****----- GenericLightBox Specific -----*****-----*****-----*****-----*****/





GenericConfirmationLightBox.prototype = Object.create(LightBox.prototype);
GenericConfirmationLightBox.prototype.constructor = GenericConfirmationLightBox;

/**-- GenericConfirmationLightBox Properties --**/
GenericConfirmationLightBox.prototype.selectors = {
    message: '.message',
    pos_btn: '.confirm_selection',
    neg_btn: '.negate_selection'
};

/**-- GenericConfirmationLightBox Functions --**/
/*
a function to set the message to show for this generic confirmation lightbox
@param message - the message to show
@return this lightbox
 */
GenericConfirmationLightBox.prototype.set_message = function(message) {
    $(this.selectors.message).html(message);
    return this;
};

/*
a function to set the text of the negative button
@param text - the text to set
@return this lightbox
 */
GenericConfirmationLightBox.prototype.set_negative_text = function(text) {
    $(this.selectors.neg_btn).text(text);
    return this;
};

/*
 a function to set the text of the positive button
 @param text - the text to set
 @return this lightbox
 */
GenericConfirmationLightBox.prototype.set_positive_text = function(text) {
    $(this.selectors.pos_btn).text(text);
    return this;
};

/*
a function to set the positive callback for this generic confirmation lightbox
@param cb - the callback to apply on a positive click
@param _this - the object to use as this in the callback
@return this lightbox
 */
GenericConfirmationLightBox.prototype.set_positive_cb = function(cb, _this) {
    this.positive_cb = function() {
        cb.apply(_this, []);
    };

    return this;
};

/*
 a function to set the negative callback for this generic confirmation lightbox
 @param cb - the callback to apply on a negative click
 @param _this - the object to use as this in the callback
 @return this lightbox
 */
GenericConfirmationLightBox.prototype.set_negative_cb = function(cb, _this) {
    this.negative_cb = function() {
        cb.apply(_this, []);
    };

    return this;
};


/*
perform click bindings for this generic confirmation lightbox
 */
GenericConfirmationLightBox.prototype.click_bindings = function() {
    var _this = this;

    $(this.selectors.pos_btn).click(function(evt) {
        evt.stopPropagation();
        _this.positive_cb();
    });

    $(this.selectors.neg_btn).click(function(evt) {
        evt.stopPropagation();
        _this.negative_cb();
    });
};





/*****-----*****----*****-----*****----- GenericMessageLightBox Specific -----*****-----*****-----*****-----*****/





GenericMessageLightBox.prototype = Object.create(LightBox.prototype);
GenericMessageLightBox.prototype.constructor = GenericMessageLightBox;

/**-- GenericConfirmationLightBox Properties --**/
GenericMessageLightBox.prototype.selectors = {
    title: '.lb_title',
    subtitle: '.subti',
    message: '.message'
};

/**-- GenericMessageLightBox Bindings --**/
GenericMessageLightBox.prototype.click_bindings = function() {
    var _this = this;
    $(this.selector).find('.accept_button').click(function() {
        _this.close();
    })
};

/**-- GenericMessageLightBox Functions --**/
/*
 a function to set the title to show for this generic message lightbox
 @param title - the title to set
 @return this lightbox
 */
GenericMessageLightBox.prototype.set_title = function(title) {
    $(this.selector).find(this.selectors.title).html(title);
    return this;
};

/*
 a function to set the subtitle to show for this generic message lightbox
 @param subtitle - the subtitle to set
 @return this lightbox
 */
GenericMessageLightBox.prototype.set_subtitle = function(subtitle) {
    $(this.selector).find(this.selectors.subtitle).html(subtitle);
    return this;
};

/*
 a function to set the message to show for this generic message lightbox
 @param message - the message to show
 @return this lightbox
 */
GenericMessageLightBox.prototype.set_message = function(message) {
    $(this.selector).find(this.selectors.message).html(message);
    return this;
};





/*****-----*****----*****-----*****----- GenericFormLightBox Specific -----*****-----*****-----*****-----*****/






GenericFormLightBox.prototype = Object.create(LightBox.prototype);
GenericFormLightBox.prototype.constructor = GenericFormLightBox;

/**-- GenericFormLightBox Functions --**/
GenericFormLightBox.prototype.setup_validation = function() {
    this.validator = $(this.form_selector).length > 0 && setup_validation(this.form_selector);
};

GenericFormLightBox.prototype.load_bindings = function() {
    var _this = this;

    if(this.silent_submit) {
        /* for a silent submit form lightbox, the default behavior on form submit is to prevent page redirect on submit and update button text */
        $(this.selector).find(this.form_selector).submit(function(evt) {
            evt.preventDefault();
            if ($(this).valid()) {
                var deferred = ajax_form_submit.apply(this, [_this.clicked_text, _this.finished_text, "Try Again"]);
                deferred.success(function(data) {
                    _this.success_cb &&_this.success_cb.call(_this, data);
                });
            }
        });
    }

    $(this.selector).find('.facebook_form_signup').submit(function(evt) {
        _this.block_submit && evt.preventDefault();
    })
};

GenericFormLightBox.prototype.click_bindings = function() {
    $(this.selector).on('click', '.social_facebook', function() {
        F.connect(this.parentNode);
        return false;
    });
}

GenericFormLightBox.prototype.submit_fb_form = function() {
    $(this.selector).find('.facebook_form_signup').submit();
}

/*
a function to set the action for this lightboxes form to a new action
@param new_action - the action to set
@return this lightbox
 */
GenericFormLightBox.prototype.set_action = function(new_action) {
    $(this.selector).find(this.form_selector).attr('action', new_action);
    return this;
}

/*
a function to set a value for a given input in this lightboxes form
@param input_sel - the selector for the input whose value we want to set
@param new_val - the val to set
@param this lightbox
 */
GenericFormLightBox.prototype.set_val = function(input_sel, new_val) {
    $(this.selector).find(input_sel).val(new_val);
};





/*****-----*****----*****-----*****----- AddItemToShelves Specific -----*****-----*****-----*****-----*****/





AddItemToShelvesLightBox.prototype = Object.create(LightBox.prototype);
AddItemToShelvesLightBox.prototype.constructor = AddItemToShelvesLightBox;

/**-- AddItemToShelves Helper Functions --**/
/*
this function adds each of the ids of the selected shelves to the input field for the form to submit the shelves
@return the number of shelves added to the form
 */
AddItemToShelvesLightBox.prototype._add_shelves_to_form = function() {
    var $shelf_ids = $(this.selector).find("input.shelves"),
        new_shelf_ids = '',
        shelf_count = 0;
    for (var id in this.selected_shelves) {
        new_shelf_ids = this.selected_shelves[id] ? new_shelf_ids + id + "," : new_shelf_ids;
        shelf_count++;
    }

    /* make sure we dont end with a trailing comma */
    new_shelf_ids = new_shelf_ids.replace(/,$/, "");
    $shelf_ids.val(new_shelf_ids);

    return shelf_count;
}

/*
this function does the work of adding clicked shelves to the list of selected shelves if hasnt already been added, otherwise
it removes it from the selected shelves
@return the new status of the shelf (true if now its added, false otherwise)
 */
AddItemToShelvesLightBox.prototype._toggle_shelf = function($shelf) {
    var already_added = this.selected_shelves[$shelf.data('shelfId')];
    $($shelf.children()).toggleClass('active');
    this.selected_shelves[$shelf.data('shelfId')] = !already_added;

    return !already_added;
};

/*
this function creates a new shelf and adds that shelf to the list of shelves this item should be placed on
@param data - JSON object containing the data sent back from the server which represents the newly created shelf
 */
AddItemToShelvesLightBox.prototype._create_shelf = function(data) {
    var compiled = _.template($('#new_shelf_tpl').html());
    var new_shelf = $(compiled(data)).appendTo($(this.selector).find('.not_yet_added'));
    this._toggle_shelf(new_shelf);
}

/*
this function should be called after the html has been populated for this lightbox and is responsible for loading
the shelves this item is already on into our javascript.
 */
AddItemToShelvesLightBox.prototype._set_added_shelves = function() {
    var _this = this;
    $(this.selector).find('.already_added_bar .element_wrapper').each(function() {
        _this._toggle_shelf($(this));
    });
}

/**-- AddItemToShelves Bindings --**/
AddItemToShelvesLightBox.prototype.click_bindings = function() {
    var _this = this;

    $(this.selector).on('click', '.element_wrapper', function() {
        var was_added = _this._toggle_shelf($(this)),
            $already_added_bar = $(_this.selector).find('.already_added_bar'),
            $not_yet_added = $(_this.selector).find('.not_yet_added');

        /* add the clicked element to the already added bar if it was added, remove it otherwise */
        was_added ? $already_added_bar.append($(this)) : $not_yet_added.append($(this));

        /* if after this click the already added bar is empty, then show the no shelves selected message */
        $already_added_bar.find('.element_wrapper').length < 1 ? $already_added_bar.find('.no_shelf_message').removeClass('hidden') : $already_added_bar.find('.no_shelf_message').addClass('hidden');
    });

    /** create shelf bindings **/
    /* toggle the add a shelf form and create a new shelf button (they should never be displayed at the same time) */
    var toggle_add_shelf = function() {
        $(_this.selector).find('.create_shelf').toggleClass('hidden');
        $(_this.selector).find('#create_shelf_form').toggleClass('hidden');
    }
    $(this.selector).on('click', '.create_shelf', function() {
        toggle_add_shelf();
    });
    $(this.selector).on('submit', '#create_shelf_form', function(evt) {
        evt.preventDefault();
        var deferred = ajax_form_submit.apply(this, []);
        $.when(deferred).then(function(data) {
            _this._create_shelf.apply(_this, [$.parseJSON(data)]);
            $(_this.selector).find('#create_shelf_form input').val(''); //clear the name of the created shelf to prevent duplicates
            $(_this.selector).find('.already_added_bar .no_shelf_message').addClass('hidden');
        });
        toggle_add_shelf();
    });

    /* override on close callback to save the form on close */
    this.on_close_cb = function() {
        var form = $(this.selector).find('#add_item_to_shelves'),
            added_shelves = this._add_shelves_to_form();

        /* if we arent closing on done click, set the text of the done button to saved */
        !this.close_on_done && $(this.selector).find('.done_btn').text('Saved');

        /* only post if we added any shelves */
        if (added_shelves) {
            var deferred = $.post(form.attr('action'), form.serialize());
            /* if there is a sidebar, update the number of items in the shelves that have items added / removed from them */
            if (window.sidebar) {
                var sidebar = window.sidebar;
                deferred.done(function(data) {
                    var json_data = $.parseJSON(data);
                    json_data.map(function(shelf) {
                        var sidebar_shelf = sidebar.get_shelf_by_id(shelf.id);
                        sidebar._modify_num_items(sidebar_shelf, shelf.num_items);
                    })
                });
            }
        }

        /* reset the selected shelves hash and the shelves container html */
        this.selected_shelves = {};
        this.set_shelves_html("");
    };

    /* save the form when the done button is clicked (by closing the lightbox, which triggers our on_close_cb) */
    $(this.selector).on('click', '.done_btn', function() {
        _this.close_on_done ? _this.close() : _this.on_close_cb();
    });
}



/**-- AddItemToShelves Public Functions --**/
/*
this function is the first thing to be called when an item is clicked and is responsible for fetching the rendered
file which displays shelves this item is on and not yet on for the logged in user
@param get_shelves_url - the url to $.get
@return jQuery deferred which holds the result of the get request
 */
AddItemToShelvesLightBox.prototype.get_item_shelves = function(get_shelves_url) {
    var deferred = $.get(get_shelves_url, {});
    return deferred;
}

/*
this function is responsible for populating this lightbox's shelves container (.item_shelves) with the provided html
@param html - the html to set the container with
 */
AddItemToShelvesLightBox.prototype.set_shelves_html = function(html) {
    $(this.selector).find('.item_shelves').html(html);
    this._set_added_shelves();
}

/*
this function allows for setting the close_on_done field for this popup
@param val - the new val to set
 */
AddItemToShelvesLightBox.prototype.set_close_on_done = function(val) {
    this.close_on_done = val;
}





/*****-----*****----*****-----*****----- ChooseLotteryWinner Specific -----*****-----*****-----*****-----*****/





ChooseLotteryWinnerLightBox.prototype = Object.create(LightBox.prototype);
ChooseLotteryWinnerLightBox.prototype.constructor = ChooseLotteryWinnerLightBox;


/**-- ChooseLotteryWinner Helpers --**/
/*
render the template for a new winner
@param winner - the winner to render the template for
 */
ChooseLotteryWinnerLightBox.prototype.render_template = function(winner) {
    var compiled = _.template(this.winner_template);
    $(this.selector).find('.lottery_winners').append(compiled(winner));
}

/*
set the number for each of the winners
 */
ChooseLotteryWinnerLightBox.prototype.set_winner_numbers = function() {
    $(this.selector).find('.winner_row').each(function() {
        var row_num = $(this).parent().find('.winner_row').index($(this)) + 1;
        $(this).find('.number').text(row_num);
    })
}


/**-- ChooseLotteryWinner Bindings --**/
ChooseLotteryWinnerLightBox.prototype.click_bindings = function() {
    var _this = this;

    $(this.selector).find('.add_winner').click(function() {
        _this.choose_winner($(this).data('postUrl'));
    });

    $(this.selector).find('.update_giveaway').click(function() {
        _this.show_winners($(this).data('postUrl'), $(this));
    });

    $(this.selector).on('click', '.del_button', function() {
        LotteryAnalyticsPage.remove_lottery_winner($(this).data('winnerId'));
        _this.delete_winner($(this).data('postUrl'), $(this).parents('.winner_row'));
    });
}

ChooseLotteryWinnerLightBox.prototype.load_bindings = function() {
    var _this = this;

    this.set_winner_numbers();
    /* if the giveaway updated button hasnt been clicked and a new winner has been chosen, then show a confirmation box */
    this.on_close_cb = function() {
        if (!this.giveaway_updated && this.winner_chosen) {
            var confirmation_lb = LightBox.get_by_type('generic_confirmation').set_message("You haven't updated the giveaway yet with the winner's name.  Do you want to do this now?  Or wait til later?");
            confirmation_lb.set_positive_text("Update Giveaway")
                .set_negative_text("Do It Later")
                .set_positive_cb(function() {
                    $(_this.selector).find('.update_giveaway').click();
                    this.close();
                }, confirmation_lb);
            confirmation_lb.open();
        }
    }
}


/**-- ChooseLotteryWinner Public Functions --**/
/*
this function chooses another winner for the lottery
@param choose_url - the url to choose a winner
 */
ChooseLotteryWinnerLightBox.prototype.choose_winner = function(choose_url) {
    var _this = this;
    this.winner_chosen = true;
    this.giveaway_updated = false;

    this.loader.toggle_visibility();
    $.post(choose_url, {}).done(function(data, resp) {
        var winner = $.parseJSON(data);
        _this.render_template(winner);
        _this.set_winner_numbers();
        _this.loader.toggle_visibility();
        LotteryAnalyticsPage.add_lottery_winner(winner);

        $(_this.selector).find('.update_giveaway').show();
    });
}

/*
this function deletes a winner for the lottery
@param delete_url - the url to delete a winner
@param container - the container of the item that is being deleted
 */
ChooseLotteryWinnerLightBox.prototype.delete_winner = function(delete_url, container) {
    $.post(delete_url, {});
    container.remove();
    this.set_winner_numbers();
}

/*
this function posts to the server and makes the lottery results publicly visible
@param show_url - the url to show winners
@param button - the clicked button
 */
ChooseLotteryWinnerLightBox.prototype.show_winners = function(show_url, button) {
    this.giveaway_updated = true;
    $.post(show_url, {});
    button.hide();
}


/*****-----*****----*****-----*****----- PhotoLightBox Specific -----*****-----*****-----*****-----*****/


PhotoLightBox.prototype = Object.create(LightBox.prototype);
PhotoLightBox.prototype.constructor = PhotoLightBox;


/**-- PhotoLightBox Bindings --**/
PhotoLightBox.prototype.open = function(img_src){
    LightBox.prototype.open.call(this);
    $(this.selector + ' img').attr('src', img_src)
}
