_CW = {};

_CW.MAX_ITERS = 120;

_CW.scrollingIteration = function(iter) {
    console.log('iteration ' + iter);
    if (iter >= _CW.MAX_ITERS) {
        console.log('scrolling finished');
        return;
    }
    _CW.scrollDown(iter + 1);
};

_CW.scrollDown = function(iter) {
    window.scrollByPages(10);
    window.setTimeout(function() { _CW.scrollingIteration(iter); }, 1000);
};

_CW.scroll = function() {
    _CW.scrollingIteration(1);
};

