alert("hello");
var s = document.createElement('script');
s.src = chrome.extension.getURL('shelfit_getshelf.js');
(document.head||document.documentElement).appendChild(s);
s.onload = function() {
    s.parentNode.removeChild(s);

};