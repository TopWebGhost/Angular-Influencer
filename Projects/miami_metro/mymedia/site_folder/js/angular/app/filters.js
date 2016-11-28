'use strict';

(function() {

  angular.module('theshelf.filters', [])

    .filter('htmlToPlaintext', function() {
        return function(text) {
          return  text ? String(text).replace(/<[^>]+>/gm, '') : '';
        };
      }
    )

    .filter('float', function(){
      return function(input) {
        return input === null && 0 || Math.round(input);
      };
    })

    .filter('fixedFloat', function(){
      return function(input, precision) {
        return parseFloat(input).toFixed(precision);
      };
    })

    .filter('topten', function() {
        return function(input, enabled) {
          if(enabled && input.slice){
            return input.slice(0, 10);
          }
          return input;
        };
      })

    .filter('toptencat', function() {
        return function(input, enabled) {
          if(enabled){
            var cats;
            cats = $.map(input, function(cat){
              if(cat.leaf) return null;
              return cat;
            });
            return cats.slice(0, 10);
          }
          return input;
        };
      })

    .filter('bytes', function() {
        return function(bytes, precision) {
            if (isNaN(parseFloat(bytes)) || !isFinite(bytes)) return '-';
            if (typeof precision === 'undefined') precision = 1;
            var units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'],
                number = Math.floor(Math.log(bytes) / Math.log(1024));
            return (bytes / Math.pow(1024, Math.floor(number))).toFixed(precision) +  ' ' + units[number];
        }
    })

    .filter('orderObjectBy', function() {
      return function(items, field, reverse) {
        var filtered = [];
        angular.forEach(items, function(item) {
          filtered.push(item);
        });
        filtered.sort(function (a, b) {
          return (a[field] > b[field] ? 1 : -1);
        });
        if(reverse) filtered.reverse();
        return filtered;
      };
    })

    .filter('capitalize', function() {
        return function(input, scope) {
            return input.substring(0,1).toUpperCase() + input.substring(1);
        };
    });
})();