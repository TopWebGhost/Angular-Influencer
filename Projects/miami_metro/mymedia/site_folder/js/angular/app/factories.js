'use strict';

angular.module('theshelf')


.factory('keywordQuery', [function(){
  var query = null;
  var type = null;
  var keyword_types = null;
  var instance = {
    setQuery: function(new_query, new_type, new_keyword_types){
      if(new_query !== undefined && new_query.value !== undefined){
        query = new_query.value;
      }else{
        query = new_query;
      }
      type = new_type;
      keyword_types = new_keyword_types;
    },
    getQuery: function(){
      return {query: query, type: type, keyword_types: keyword_types};
    }
  };
  return instance;
}])

.factory('filtersQuery', [function(){
  var query = null;
  var instance = {
    setQuery: function(new_query){
      query = new_query;
    },
    getQuery: function(){
      return query;
    }
  };
  return instance;
}])

.factory('tagStripper', [function(){
  var instance = {
    strip: function(input){
      if(input === null) return "";
      var subs = input;
      subs = subs.replace(/\n/ig,"");
      subs = subs.replace(/(<([^>]*?)script([^>]*?)>.*?<\s*?\/\s*?script([^>]*?)>)/ig,"");
      subs = subs.replace(/(<([^>]*?)style([^>]*?)>.*?<\s*?\/\s*?style([^>]*?)>)/ig,"");
      subs = subs.replace(/(<([^>]*?)xml([^>]*?)>.*?<\s*?\/\s*?xml([^>]*?)>)/ig,"");
      subs = subs.replace(/(<([^>]*?)iframe([^>]*?)>.*?<\s*?\/\s*?iframe([^>]*?)>)/ig,"");
      subs = subs.replace(/(<([^>]+)>)/ig,"");
      subs = subs.replace(/ +/g," ");
      return subs;
    },
  };
  return instance;
}])

.factory('singletonRegister', [function () {
  var singletons = {};
  return {
    getOrRegister: function(name){
      if(singletons[name] !== undefined){
        return true;
      }else{
        singletons[name] = true;
        return false;
      }
    }
  };
}])

;
