/**
 * Author: Bobby
 * Purpose: This file is loaded with core so exists on all our pages. Its purpose is simple: It provides an abstraction layer
 * for hiding and showing a loader image. We use this fairly extensively in pages where a feed is loaded.
 */


/* a loader is exactly what you think it is, an image that is a placeholder for actual content while that content loads */
function Loader($container, $content_container) {
    this.$container = $container;
    this.$content_container = $content_container; //optional
}

Loader.prototype.toggle_visibility = function() {
    this.$container.toggleClass('hidden') && this.$content_container && this.$content_container.toggleClass('hidden');
    return this;
}

/*
if the loader is an <img>, this function allows for the changing of that images source (useful for replacing
the loader with an image that isn't available until after processing)
@param new_src - the new source to set for the image tag holding the loader
@return this
 */
Loader.prototype.change_src = function(new_src) {
    this.$container.attr('src', new_src);
    return this;
};

/*
add/change attributes on the loader container
@param new_attrs - javascript object which contains new attributes to set on the container for this loader
@return this
 */
Loader.prototype.modify_container_attrs = function(new_attrs) {
    for (var attribute in new_attrs) {
        this.$container.attr(attribute, new_attrs[attribute]);
    }
    return this;
};