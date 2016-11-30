/**
 * Author: Bobby
 * Purpose: This file is loaded with core so exists on every page. Its purpose is to provide handy functions
 * for manipulating images. These include setting up a carousel of scrolling images, centering an image in its container,
 * and some auxilliary functions.
 */


function ImageManipulator($image, $container) {
    this.$image = $image;
    this.$container = $container;
    this.is_wider = false;
}

/**-- Helper Functions --**/
/*
a function to get this images ratio
@return this images image ratio
 */
ImageManipulator.prototype.image_ratio = function() {
    var native_dims = this.get_native_dimensions();
    return native_dims.width / native_dims.height;
};

/*
a function to get this containers ratio
@return this containers ratio
 */
ImageManipulator.prototype.container_ratio = function() {
    return this.$container.width() / this.$container.height();
};

/*
a function to get the native (not modified by styles) dimensions of this manipulator's image.
Credit: "borrowed" from http://css-tricks.com/snippets/jquery/get-an-images-native-width/
@return true if its a wide image, false if its a tall image
 */
ImageManipulator.prototype.get_native_dimensions = function() {
    var native = new Image();
    native.src = this.$image.attr("src");

    return {
        width: native.width,
        height: native.height
    };
};


/**-- Public API --**/

/*
a function to assign the correct class to this manipulators image based on its proportions and its relation to
its container
Rulez:
-Image vs Container-    -Class-    Class Legend: wider = height:auto; width:100%; || taller = height:100%; width:auto;
 Wider                  taller
 Taller                 wider
 */
ImageManipulator.prototype.assign_dimension_class = function() {
    this.is_wider = this.image_ratio() > this.container_ratio();
    this.$image.addClass(this.is_wider ? 'wider' : 'taller');
};

/*
a function to center this manipulator's image horizontally and vertically in its container
 */
ImageManipulator.prototype.center_image = function() {
    var extra_space_ratio = 0;
    if (this.is_wider) {
        extra_space_ratio = 1 - (this.$container.width() / this.$image.width());
    } else {
        extra_space_ratio = 1 - (this.$container.height() / this.$image.height());
    }
    var margin_ratio = extra_space_ratio / 2,
        margin_percent = margin_ratio * 100;
    this.$image.css(this.is_wider ? 'margin-left' : 'margin-top', "-"+margin_percent+"%");
};

/*
a function to replace the image for this imagemanipulator
 */
ImageManipulator.prototype.replace_image = function(image) {
    this.$image = image;
};

/*
a classmethod to make a scrollable row of images inside a container
 @param $container - in case the scrollable row doesnt exist at page load, we can use the $container for delegation
 @return this ImageManipulator
 */
ImageManipulator.create_scrollable_images = function($container) {
      var SCROLL_RATIO = .4; //80% of row width
    var left_btn = '.left_btn',
        right_btn = '.right_btn';
    var $scrollable_row = $container.find('.scrollable_row'),
        row_width = $scrollable_row.width(),
        step_amount = row_width * SCROLL_RATIO;

    /* scroll right */
    $container.on('mousedown', right_btn, function() {
        var combined_images_width = (function() {
                var combined_width = 0,
                    $images = $scrollable_row.find('img');
                $images.each(function() {
                    combined_width += $(this).outerWidth(true);
                });

                return combined_width;
            })(),
            stop_after = combined_images_width - (row_width * 2); /*represents how far right we should go before hiding the right button */

        $container.find(left_btn).show();

        $scrollable_row.animate({
            left: "-="+step_amount+"px",
            easing: 'linear'
        });

        Math.abs(parseInt($scrollable_row.css('left'))) >= stop_after ? $container.find(right_btn).hide() : $container.find(right_btn).show();
    });


    /* scroll left */
    $container.on('mousedown', left_btn, function() {
        var stop_after = 0 - row_width;

        $container.find(right_btn).show();

        $scrollable_row.animate({
            left: "+="+step_amount+"px",
            easing: 'linear'
        });

        /* if we're at the first place in the scrolling, hide the left button */
        parseInt($scrollable_row.css('left')) >= stop_after ? $container.find(left_btn).hide() : $container.find(left_btn).show();
    });

    return this;
};