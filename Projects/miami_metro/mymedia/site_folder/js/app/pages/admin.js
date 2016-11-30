/**
 * Author: Bobby
 * Purpose: This file is loaded when an admin page is loaded. If the admin pages get much more involved, it would
 * probably be a good idea to pull the logic for each individual page into its own file, but for now this does
 * fine.
 */

var Admin = {
    categorized_items: {}
};

/*****-----< User Admin Specific >-----*****/

/*
generate a screenshot of a users collage, this is used for sending out emails containing users' collages
@param debug - if true / set, then open the image in a window
 */
Admin.generate_collage_screenshot = function(debug) {
    var collage = $('.user_collage');
    html2canvas(collage, {
        proxy: collage.data('html2canvasProxy'),
        logging: true,
        onrendered: function(canvas) {
            var image = canvas.toDataURL();
            debug && window.open(image);
            $.post(collage.data("collageUpload"), {
                image: image
            })
        }
    })
};

/*
add a new admin_classification_tag for the user
@param tag_val - the value of the new tag
@param container - the container to add the tag to
 */
Admin.new_classification_tag = function(tag_val, container) {
    var tag_tpl = _.template("<div class='clearfix'><input type='checkbox' class='admin_classification' value='<%= tag_name %>' checked/><label><%= tag_name %></label></div>");
    var compiled = tag_tpl({tag_name: tag_val});
    container.append(compiled);
};

/*
 show all messages sent to a given user over intercom
 @param url - the url for fetching the users messages sent over intercom
*/
Admin.show_intercom_messages = function(url) {
    var container = $("<div><ul class='intercom_messages_container'></ul><div>"),
        messages_tpl = _.template("<% _.each(messages, function(message) { %><li class='<% if (us_message(message)) { %>us_message<% } else { %>user_message<% } %>'><%= message.from.name %>: <%= message.html %></li><% }) %>");
    $.get(url, {}, function(data) {
        var message_lb = LightBox.get_by_type('generic_message');
        var parsed = $.parseJSON(data);

        if (parsed.length > 0) {
            for (var i = 0, len = parsed.length ; i < len ; i++) {
                var cur_thread = parsed[i];
                cur_thread['us_message'] = function(message) {
                    return message.from && message.from.is_admin;
                };
                container.find('.intercom_messages_container').append(messages_tpl(cur_thread));
            }
        } else {
            container.html("<h1>No Messages</h1>");
        }


        message_lb.set_message(container.html());
        message_lb.open();
    });
};


/*****-----< Product Admin Specific >-----*****/


/** a product is an item in the grid of products. Its parameters are:
 *
 * @param id - the id of the product being added
 * @constructor
 * (this is actually used for Posts as well)
 */
function Product(id) {
    this.id = id;
}


/*****-----< Influencer Import Specific >-----*****/


/*
add the last blogger that was created to the admin's object of added influencers
 */
Admin.save_blogger = function() {
    Admin.added_bloggers = Admin.added_bloggers || [];
    var $last_added = Admin.row_container.children().last();

    Admin.added_bloggers.push({});
    var this_blogger = Admin.added_bloggers[Admin.added_bloggers.length - 1];
    $last_added.find('input, select, textarea').each(function() {
        this_blogger[$(this).attr('name')] = $(this).val();
    });
    this_blogger['$container'] = $last_added;
};

/*
delete the blogger having the given container from the list of added bloggers
@param $container - the container of the blogger to delete
 */
Admin.delete_blogger = function($container) {
    Admin.added_bloggers = Admin.added_bloggers.filter(function(el, i) {
        return el.$container.get(0) != $container.get(0);
    });
};

/*
create a new row for the blogger import section
@param $page - the page to add the row to
 */
Admin.add_blogger_row = function($page) {
    var new_row_tpl = _.template(Admin.row_tpl);
    var new_row = new_row_tpl();
    $page.append(new_row);
};

/*
set the layout type for the admin
@param type - the type of layout to make it (table or div)
 */
Admin.set_layout_type = function(type) {
    Admin.layout_type = type;
    Admin.row_container = type === 'table' ? $('.table_layout') : $('.div_layout');
    Admin.row_tpl = type === 'table' ? $('.new_blogger_table_tpl').html() : $('.new_blogger_div_tpl').html();

    /* show the appropriate layout container and add the first row to that container */
    $('.layout_type').hide();
    Admin.row_container.show();

    /* for the table, the real row container is actually the tbody, so lets set that after showing the table */
    Admin.row_container = type === 'table' ? Admin.row_container.find('.another_container') : Admin.row_container;

    Admin.row_container.html('');
};



$(document).ready(function() {
    var $page = $('.admin_page');
    var search_box = $('.admin_search_box'),
        autocomplete_el = $(".admin_autocomplete"),
        all_results_btn = $('.admin_all_results'),
        results_tpl = '<div class="autocomplete_result" data-item-id="<%= result.id %>"><img src="<%=result.img %>" /><%= result.name %></div>';
    var confirmation_lb = LightBox.get_by_type("generic_confirmation"); //for deleting user

    ($page.hasClass('influencers_container') || $page.hasClass('brands_container')) && new UserFeed($page, '.admin_item', {
        apply_salvatorre: true
    });

    /**-- User Click Bindings Exclusively --**/
    $page.on('click', '.submit_button', function(evt) {
        evt.preventDefault();
        var $form = $(this).closest('form');
        checkboxes_to_string($form.find('.admin_classification'), $form.find('input[name="admin_classification_tags"]'));
        ajax_form_submit.apply($form, ['Saving..', 'Saved', 'User saved, but not in intercom']);
    });
    $page.on('click', '.show_collage_btn', function(evt) {
        evt.preventDefault();
        $(this).closest('.admin_item').find('.user_collage').slideToggle();
    });
    $page.on('click', '.delete_btn', function(evt) {
        evt.preventDefault();
        var delete_url = $(this).data('deleteUrl'),
            container = $(this).closest('.admin_item');
        confirmation_lb.set_positive_cb(function() {
            $.post(delete_url);
            container.remove();
            this.close();
        }, confirmation_lb);
        confirmation_lb.open();
    });
    $page.on('click', '.new_tag_btn', function(evt) {
        evt.preventDefault();
        var tag_fieldset = $(this).parent().find('.new_tag_entry').slideToggle(),
            tag_input = tag_fieldset.find('input');
        tag_fieldset.find('button').one('click', function(evt) {
            evt.preventDefault();
            Admin.new_classification_tag(tag_input.val(), tag_fieldset.parent().find('.tags_container'));
            tag_fieldset.slideUp();
        });
    });
    $page.on('click', '.intercom_messages', function() {
        Admin.show_intercom_messages($(this).data('getUrl'));
    });


    /**-- Influencer Click Binding Exclusively --**/
    if ($page.hasClass('influencers_container')) {
       $page.on('click', '.influencer_link.show_blog', function(evt) {
           evt.preventDefault();
            var iframe = $(this).closest('.admin_item').find('iframe'),
                src = iframe.data('src'),
                is_hidden = $(this).text() == 'Show Blog';

            iframe.toggleClass('open');
            is_hidden ?  iframe.attr('src', src) : iframe.removeAttr('src');
            is_hidden ? $(this).text('Hide Blog') : $(this).text('Show Blog');
        });

        $page.on('click', '.set_remove_tag', function() {
            $(this).next().val();
        });

        $page.on('click', '.trash', function() {
            var post_url = $(this).data('postUrl');
            $.post(post_url, {});
            $(this).closest('.social_block').remove();
        })
    }


    /**-- Influencer Import Click Binding Exclusively --**/
    if ($page.hasClass('import_bloggers')) {
        var $submit_btn = $('.submit');

        Admin.set_layout_type('table');
        Admin.add_blogger_row(Admin.row_container);

        /* binding for deleting a entry */
        $page.on('click', '.delete_row', function() {
            var $container = $(this).closest('.blogger_row');
            Admin.delete_blogger($container);
            $container.remove();
        });

        $page.on('click', '.change_layout', function() {
            Admin.added_bloggers = [];
            Admin.layout_type === 'table' ? Admin.set_layout_type('div') : Admin.set_layout_type('table');
            Admin.add_blogger_row(Admin.row_container);
        });

        /* binding for checking if we've already added a blogger */
        $page.on('click', '.check_added', function() {
            var $search_input = $page.find('.already_added_search input'),
                search_val = $search_input.val();

            /* check all the blog urls entered to see if we have a match */
            $page.find('.blog_url').each(function() {
                if ($(this).val() === search_val) {
                    /* highlight the row and scroll to this position */
                    $(this).closest('.blogger_row').addClass('search_match');
                    $('html, body').animate({
                        scrollTop: $(this).offset().top
                    }, 2000);
                }
            });
        });

        /* binding for adding another row */
        $(document).on('click', '.add_another_btn', function() {
            Admin.save_blogger();
            Admin.add_blogger_row(Admin.row_container);
        });

        /* binding for submitting influencers */
        $(document).on('click', '.submit', function() {
            Admin.save_blogger();
            $submit_btn.text('Submitting..');

            var deferreds = [];
            Admin.added_bloggers.map(function(el, i) {
                deferreds.push($.post('', {blogger: JSON.stringify(Object.new_without_exclude(el, ['$container']))}, function(resp) {
                    el.$container.addClass('success');
                }).fail(function() {
                    el.$container.addClass('fail');
                }));
            });

            $.when.apply($, deferreds).then(function() {
                $('.reset').removeClass('hidden');
                $submit_btn.text('Submit');
            }, function() {
                $('.reset').removeClass('hidden');
                $submit_btn.text('Submit');
            });
        });

        /* binding for resetting page */
        $(document).on('click', '.reset', function() {
            $(this).addClass('hidden');
            $submit_btn.text('Submit');

            $page.find('.blogger_row').remove();
            Admin.added_bloggers = [];
            Admin.add_blogger_row(Admin.row_container);
        })
    }


    /**-- Product + Post Binding Exclusively --**/
    /* when the page is first loaded, add all feed items to the products for the admin so we can process server side when finished */
    if ($page.hasClass('posts_container') || $page.hasClass('products_container')) {
        /* setup the filter for posts */
        if ($page.hasClass('posts_container')) {
            var filters = "";

            $('input').click(function() {
                var type = $(this).data('filterType');
                if ($(this).is(':checked')) {
                   $.get('', {filter: type}, function(resp) {
                        $page.html(resp);
                        salvattore.register_grid($page.get(0));
                    })
                }
            });

            $('.mark_rest').click(function() {
                $(this).text('working..');
                $.post('', {mark_rest: true}).done(function() {
                    window.location = document.URL;
                })
            });
        }

        $page.find('.admin_item').each(function() {
            var instance = new Product($(this).data('itemId'));
            Admin.categorized_items[instance.id] = {};
        });
        /* when a product is clicked, we want to track meta data for that product in our Admin var */
        $page.on('click', '.admin_item', function(evt) {
            var id = $(this).data('itemId'),
                added_product = Admin.categorized_items[id];
            var problem = $(evt.target).closest('.marker');
            var item_ok = $(evt.target).closest('.item_ok');

            if (problem.length > 0 && problem.hasClass('item_error')) {
                added_product.error = problem.data('errorType');
                $(this).remove();
            } else if (problem.length > 0 && problem.hasClass('item_ugly')) {
                added_product.ugly = 1;
                $(this).remove();
            } else if (item_ok.length > 0) {
                added_product.show = 1;
                $(this).remove();
            }
        });
        $('.items_save').click(function() {
            $.post('', {items: JSON.stringify(Admin.categorized_items)}).done(function() {
                window.location = document.URL;
            });
            $(this).text('Working...');
        });
    }


    /**-- User Filter Stuff --**/
    $('.filter_btn').click(function(evt) {
        evt.preventDefault();
        var filter_str = '';

        $('.filter:checked').each(function() {
            var name = $(this).data('filterName'),
                type = $(this).data('filterType'),
                val = $(this).data('filterVal');
            filter_str += name+"|"+type+"|"+val+",";
        });

        filter_str = remove_trailing_comma(filter_str);
        $(this).attr('href', '?filters='+filter_str);
        window.location = $(this).attr('href');
    });

    /**-- Autocomplete Stuff --**/
    autocomplete(results_tpl, autocomplete_el);
    search_box.on('click', '.autocomplete_result', function() {
        var item_id = $(this).data('itemId');
        $.get("", {q: item_id}, function(resp) {
            $page.html(resp);
            all_results_btn.removeClass('hidden');
        });
    });

    all_results_btn.click(function() {
        $.get(document.URL, function(resp) {
            all_results_btn.addClass('hidden');
            $page.html(resp);
        });
    })
});