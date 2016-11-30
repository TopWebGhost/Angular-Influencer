/**
 * Author: Bobby
 * Purpose: This file is loaded with core so exists on every page. All this file does is provide some handy methods
 * (for both the base Object as well as jQuery)
 */



/*
this helper function gets the innermost values from an object. So, for instance, given:
{a: {
  b: 1,
  c: {
    d: {
      2
    }
  },
  e: 3
}
would return [1, 2, 3]
 */
Object.get_innermost = function(obj) {
    var _get_innermost = function(obj, arr) {
        for (var key in obj) {
            if (obj[key] instanceof Object) {
                _get_innermost(obj[key], arr);
            } else {
                arr.push(obj[key]);
            }
        }
        return arr;
    };

    return _get_innermost(obj, []);
};

/*
this helper examines an object and removes all entries of that object that have
a falsey value. For instance:
{
a: true,
b: false,
c: {
 d: 1
 },
e: 0,
f: '',
g: 'hey'
}
would return:
{
a: true,
c: {
 d: 1
 }
g: 'hey'
}
 */
Object.remove_falsey = function(obj) {
    for (var key in obj) {
        if (obj[key] instanceof Object) {
            Object.remove_falsey(obj[key]);
        } else {
            !key && delete obj[key];
        }
    }

    return obj;
};


/*
this helper returns a new object that has all the keys of the passed object, with the exception of the keys provided
as arguments
@param obj - the original object
@param exclude - the array of keys to exclude in the generated object
 */
Object.new_without_exclude = function(obj, exclude) {
    var new_obj = {};

    Object.keys(obj).map(function(k, i) {
        if (exclude.indexOf(k) < 0) {
            new_obj[k] = obj[k];
        }
    });

    return new_obj;
};

/*
this jQuery function makes sure that a callback for an image load is ONLY fired when that image is loaded
"borrowed" from http://stackoverflow.com/questions/5624733/jquery-load-not-firing-on-images-probably-caching
 */
jQuery.fn.extend({
    ensureLoad: function(handler) {
        return this.each(function() {
            if(this.complete) {
                handler.call(this);
            } else {
                $(this).load(handler);
            }
        });
    }
});

/*
this jQuery function allows you to get the 'outer html' for an element
"borrowed" from http://stackoverflow.com/questions/3614212/jquery-get-html-of-a-whole-element
 */
jQuery.fn.outerHtml = function() {
  return jQuery('<div />').append(this.eq(0).clone()).html();
};