_XC = {};

_XC.MAX_Y = 400;

_XC.findCheckoutXPathCandidates = function() {
    return _XPS.xpathsAttrsWithWords(Object.keys(_XPS.jsonData['checkout_words']));
};

_XC.findRemoveFromCartXPathCandidates = function() {
    return _XPS.xpathsAttrsWithWords(_XPS.jsonData['remove_from_cart_words']);
};

_XC.findAddToCartXPathCandidates = function() {
    var xpathsAttrs = _XPS.xpathsAttrsWithWords(_XPS.jsonData['add_to_cart_words'],
            undefined, ['background-image']);
    var xpaths = _XPS.map(_XPS.fst, xpathsAttrs);
    var els = _XPS.map(_XPS.evaluateXPathFirst, xpaths);
    els = _XPS.removeChildrenFromArray(els, true);
    var newXPaths = _XPS.computeXPathAll(els);
    return _XPS.filter(function(xpathAttr) { return newXPaths.indexOf(xpathAttr[0]) !== -1; },
            xpathsAttrs);
};

_XC.findSubtotalWordXPathCandidates = function() {
    var els = _XPS.getAllElements(); 

    els = _XPS.filter(_XPS.isVisiblePlus, els);

    els = _XPS.filter(_XPS.boundingRectIsValid, els);

    els = _XPS.filter(function(el) {
        return _XPS.substringInArray(_XPS.directTextContent(el, 100), _XPS.jsonData['subtotal_words']);
    }, els);

    return _XPS.map(_XPS.computeXPath, els);
};

_XC.isNearAndVerticallyAligned = function(baseElXPath, otherElXPath) {
    var baseEl = _XPS.evaluateXPath(baseElXPath)[0];
    var otherEl = _XPS.evaluateXPath(otherElXPath)[0];
    if (_XPS.minDistance(baseEl, otherEl) > 300) {
        return false;
    }
    var r1 = _XPS.boundingRectForEl(baseEl);
    var r2 = _XPS.boundingRectForEl(otherEl);
    if (Math.abs(r1.top - r2.top) > 10) {
        return false;
    }
    if (Math.abs(r1.bottom - r2.bottom) > 10) {
        return false;
    }
    return true;
};

