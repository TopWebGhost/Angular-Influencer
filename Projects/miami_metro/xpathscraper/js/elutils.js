_XPS.collectFromFrames = function(winFun, skipGlobal, invalidFrameUrlArray, invalidFrameIdArray) {
    if (typeof invalidFrameUrlArray === 'undefined') {
        invalidFrameUrlArray = [];
    }
    if (typeof invalidFrameIdArray === 'undefined') {
        invalidFrameIdArray = [];
    }
    var res = [];
    var handleWindow = function(currentWindow) {
        if (!(skipGlobal && currentWindow === window)) {
            var funRes = winFun(currentWindow);
            if (funRes instanceof Array) {
                res = res.concat(funRes);
            } else if (funRes instanceof HTMLCollection) {
                res = res.concat(_XPS.collectionToArray(funRes));
            } else {
                res.push(funRes);
            }
        }
        for (var i = 0; i < currentWindow.frames.length; ++i) {
            var frame = currentWindow.frames[i];
            if (frame && frame.window && 'document' in frame.window && frame.frameElement) {
                var frameInfo = frame.window.document.URL + ' ' +
                            frame.frameElement.id + ' ' +
                            JSON.stringify(invalidFrameUrlArray) + ' ' +
                            JSON.stringify(invalidFrameIdArray);
                if (!_XPS.substringInArray(frame.window.document.URL, invalidFrameUrlArray) &&
                    !_XPS.substringInArray(frame.frameElement.id, invalidFrameIdArray)) {
                        console.log('Passed test: ' + frameInfo);
                        handleWindow(frame.window);
                } else {
                        console.log('Not passed, skipping: ' + frameInfo);
                }
            }
        }
    };
    handleWindow(window);
    return res;
};

_XPS.collectionToArray = function(htmlCollection) {
    return Array.prototype.slice.call(htmlCollection);
};

_XPS.getDynamicSource = function() {
    return document.body.outerHTML;
};

_XPS.getElSource = function(el) {
    return el.outerHTML;
};

_XPS.isElementInArray = function(el, arr) {
    if (!(el instanceof Node)) {
        return false;
    }
    for (var i = 0; i < arr.length; ++i) {
        if ((arr[i] instanceof Node) && el.isEqualNode(arr[i])) {
            return true;
        }
    }
    return false;
};


_XPS.idOrClassInArray = function(el, arr) {
    for (var i = 0; i < arr.length; ++i) {
        var s = arr[i];
        if (el.id && el.id.indexOf(s) !== -1) {
            return true;
        }
        if (el.className && el.className.indexOf(s) !== -1) {
            return true;
        }
    }
    return false;
};

_XPS.findCommonAncestor = function(els) {
    if (!els || !els.length) {
        return null;
    }
    var candidate = els[0];
    while (true) {
        var allChildren = candidate.getElementsByTagName('*');

        var foundAll = true;
        for (var i = 0; i < els.length; ++i) {
            var el = els[i];
            if (!_XPS.inArray(el, allChildren)) {
                foundAll = false;
                break;
            }
        }
        if (foundAll) {
            return candidate;
        }

        candidate = candidate.parentNode;
        if (!candidate) {
            return null;
        }
    }
};

_XPS.findAncestorWithClassName = function(el, cls) {
    var ancestor = el.parentNode;
    while (true) {
        if (!ancestor || ancestor.tagName === 'BODY') {
            return null;
        }
        if (ancestor.className && ancestor.className.indexOf(cls) !== -1) {
            return ancestor;
        }
        ancestor = ancestor.parentNode;
    }
};

_XPS.textsFromElContentAndAttrs = function(el, recursive, attrBlacklist) {
    if (typeof attrBlacklist === "undefined") {
        attrBlacklist = [];
    }
    var res = [];
    var text = _XPS.directTextContent(el);
    if (text) {
        res.push(text);
    }
    if (el.attributes) {
        for (var i = 0; i < el.attributes.length; ++i) {
            var attr = el.attributes[i];
            if (attr && attr.value && attrBlacklist.indexOf(attr.name.toLowerCase()) === -1) {
                res.push(attr.value);
            }
        }
    }
    if (!recursive) {
        return res;
    }
    for (var i = 0; i < el.childNodes.length; ++i) {
        var child = el.childNodes[i];
        res = res.concat(_XPS.textsFromElContentAndAttrs(child, true, attrBlacklist));
    }
    return res;
};

_XPS.evaluateXPath = function(expr) {
    var it = document.evaluate(expr, document, null, XPathResult.ANY_TYPE, null);
    var res = [];
    var node = it.iterateNext();
    while (node) {
        res.push(node);
        node = it.iterateNext();
    }
    return res;
};

_XPS.evaluateXPathFirst = function(expr) {
    return _XPS.evaluateXPath(expr)[0];
};

_XPS.evaluateXPathToXPaths = function(expr) {
    return _XPS.map(_XPS.computeXPath, _XPS.evaluateXPath(expr));
};

_XPS.numberOfElementsMatchingXPath = function(expr) {
    return _XPS.evaluateXPath(expr).length;
};

_XPS.childIndex = function(el) {
    var sameTagCount = 0;
    for (var i = 0; i < el.parentNode.children.length; ++i) {
        var child = el.parentNode.children[i];
        if (child === el) {
            return sameTagCount;
        }
        if (child.tagName === el.tagName) {
            ++sameTagCount;
        }
    }
    return -1;
};

_XPS._idSuitable = function(id) {
    if (!id) {
        return false;
    }
    
    if (_XPS.evaluateXPath('*[@id="' + id + '"]').length > 1) {
        return false;
    }

    return true;
};

_XPS.cssSelector = function(el) {
    return '//' + el.tagName.toLowerCase() + '[@class="' + el.className + '"]';
};

_XPS._cssClassIsUnique = function(el) {
    return _XPS.evaluateXPath(_XPS.cssSelector(el)).length === 1;
};

_XPS.attrValueSuitable = function(s) {
    if (typeof(s) !== 'string') {
        return false;
    }
    /*
    if (s.match(/\d{4,}/)) {
        return false;
    }
    */
    if (s.indexOf('selected') !== -1 || s.indexOf('current') !== -1) {
        return false;
    }
    return true;
};

_XPS.computeXPath = function(el, skipUnique) {
    if (!skipUnique) {
        skipUnique = 0;
    }

    if (el.tagName === 'BODY' || el.tagName === 'HTML') {
        return '//' + el.tagName.toLowerCase();
    }

    var recRes = function() {
        var parentXPath = _XPS.computeXPath(el.parentNode, skipUnique);
        var tagName = el.tagName ? el.tagName.toLowerCase() : '*';
        return parentXPath + '/' + tagName + '[' + (_XPS.childIndex(el) + 1) + ']';
    };

    if (el.id && _XPS._idSuitable(el.id) && _XPS.attrValueSuitable(el.id)) {
        if (skipUnique === 0) {
            return '//' + el.tagName.toLowerCase() + '[@id="' + el.id + '"]';
        }
        --skipUnique;
        return recRes();
    }

    if (el.className && _XPS.attrValueSuitable(el.className) && _XPS._cssClassIsUnique(el)) {
        if (skipUnique === 0) {
            return _XPS.cssSelector(el);
        }
        --skipUnique;
        return recRes();
    }

    return recRes();

};

_XPS.computeXPathAll = function(els, skipUnique) {
    return _XPS.map(function(el) { return _XPS.computeXPath(el, skipUnique); }, els);
};

// https://code.google.com/p/fbug/source/browse/branches/firebug1.6/content/firebug/lib.js?spec=svn12950&r=8828#1332
_XPS.createXPathFromElement = function(element) { 
    if (element && element.id)
            return '//*[@id="' + element.id + '"]';
        else
            return _XPS.getElementTreeXPath(element);
}; 
_XPS.getElementTreeXPath = function(element) {
    var paths = [];
    // Use nodeName (instead of localName) so namespace prefix is included (if any).
    for (; element && element.nodeType == 1; element = element.parentNode)
    {
        var index = 0;
        for (var sibling = element.previousSibling; sibling; sibling = sibling.previousSibling)
        {
            // Ignore document type declaration.
            if (sibling.nodeType == Node.DOCUMENT_TYPE_NODE)
                continue;

            if (sibling.nodeName == element.nodeName)
                ++index;
        }

        var tagName = element.nodeName.toLowerCase();
        var pathIndex = (index ? "[" + (index+1) + "]" : "");
        paths.splice(0, 0, tagName + pathIndex);
    }

    return paths.length ? "/" + paths.join("/") : null;
};

_XPS.textOfSelectedOption = function(optionXPaths) {
    for (var i = 0; i < optionXPaths.length; ++i) {
        var xpath = optionXPaths[i];
        var els = _XPS.evaluateXPath(xpath);
        for (var j = 0; j < els.length; ++j) {
            var el = els[j];
            if (el.tagName === 'OPTION' && el.selected) {
                return _XPS.directTextContent(el);
            }
        }
    }
    return null;
};

_XPS.imageSrcFromXPath = function(xpath) {
    var elArr = _XPS.evaluateXPath(xpath);
    if (!elArr | !elArr.length) {
        return null;
    }
    var el = elArr[0];
    if (el.tagName === 'IMG' && el.getAttribute('src')) {
        return el.getAttribute('src');
    }
    for (var i = 0; i < el.childNodes.length; ++i) {
        var child = el.childNodes[i];
        var childSrc = _XPS.imageSrcFromXPath(_XPS.computeXPath(child));
        if (childSrc) {
            return childSrc;
        }
    }
    return null;
};

_XPS.canvasDataURL = function(el, mimetype) {
    if (typeof mimetype === 'undefined') {
        mimetype = 'image/jpeg';
    }
    if (el.tagName !== 'CANVAS') {
        return null;
    }
    return el.toDataURL(mimetype);
};

_XPS.getDocumentReadyState = function() {
    return document.readyState;
};

_XPS.isChild = function(parentEl, childEl) {
    if (!childEl || childEl.tagName === 'BODY') {
        return false;
    }
    if (childEl.isEqualNode(parentEl)) {
        return true;
    }
    return _XPS.isChild(parentEl, childEl.parentNode);
};

_XPS.removeChildrenFromArray = function(arr, reverse) {
    if (typeof(reverse) === 'undefined') {
        reverse = false;
    }
    for (var i = 0; i < arr.length; ++i) {
        for (var j = i + 1; j < arr.length; ++j) {
            if (!arr[i] || !arr[j]) {
                continue;
            }
            if (_XPS.isChild(arr[i], arr[j])) {
                arr[reverse ? i : j] = null;
            } else if (_XPS.isChild(arr[j], arr[i])) {
                arr[reverse ? j : i] = null;
            }
        }
    }
    var res = [];
    for (var i = 0; i < arr.length; ++i) {
        if (arr[i]) {
            res.push(arr[i]);
        }
    }
    return res;
};

_XPS.anyRelated = function(arr1, arr2) {
    for (var i = 0; i < arr1.length; ++i) {
        for (var j = 0; j < arr2.length; ++j) {
            var e1 = arr1[i];
            var e2 = arr2[j];
            if (e1.isEqualNode(e2)) {
                return true;
            }
            if (_XPS.isChild(e1, e2) || _XPS.isChild(e2, e1)) {
                return true;
            }
        }
    }
    return false;
};

_XPS.removeRelatedEls = function(origArrXPath, badArrXPath) {
    var res = [];
    for (var i = 0; i < origArrXPath.length; ++i) {
        var origEls = _XPS.evaluateXPath(origArrXPath[i]);
        var isRelated = _XPS.any(function(xpath) {
            return _XPS.anyRelated(origEls, _XPS.evaluateXPath(xpath));
        }, badArrXPath);
        if (!isRelated) {
            res.push(origArrXPath[i]);
        }
    }
    return res;
};

_XPS.imageLikeElements = function() {
    var els = _XPS.collectionToArray(document.getElementsByTagName('IMG')).
        concat(_XPS.collectionToArray(document.getElementsByTagName('CANVAS')));
    els = _XPS.filter(_XPS.isVisiblePlus, els);
    return els;
};

_XPS.elementSize = function(el) {
    if (el && el.width && el.height) {
        return el.width * el.height;
    }
    return -1;
};

_XPS.aspectRatio = function(el) {
    if (el && el.width && el.height) {
        return el.width / el.height;
    }
    return 0;
};

_XPS.boundingRectForTextNode = function(node) {
    var range = document.createRange();
    range.selectNodeContents(node);
    return range.getBoundingClientRect();
};

_XPS.boundingRectForEl = function(el) {
    if (el.childNodes && el.childNodes.length && el.childNodes[0].nodeType === 3) {
        return _XPS.boundingRectForTextNode(el.childNodes[0]);
    }
    return el.getBoundingClientRect();
};

_XPS.boundingRectIsValid = function(el) {
    var r = _XPS.boundingRectForEl(el);
    if (r.top < 0 || r.bottom < 0 || r.left < 0 || r.right < 0) {
        return false;
    }
    return true;
};

_XPS.boundingRectForMultipleEls = function(els, margin) {
    if (typeof margin === 'undefined') {
        margin = 100;
    }

    if (!els || !els.length) {
        return null;
    }

    els = _XPS.filter(function(el) { return el; }, els);
    if (!els.length) {
        return null;
    }

    var firstRect = _XPS.boundingRectForEl(els[0]);
    var res = {
        left: firstRect.left - margin,
        right: firstRect.right + margin,
        top: firstRect.top - margin,
        bottom: firstRect.bottom + margin
    };
    for (var i = 1; i < els.length; ++i) {
        var el = els[i];
        var r = _XPS.boundingRectForEl(el);
        res.left = Math.min(res.left, r.left - margin);
        res.right = Math.max(res.right, r.right + margin);
        res.top = Math.min(res.top, r.top - margin);
        res.bottom = Math.max(res.bottom, r.bottom + margin);
    }
    return res;
};

_XPS.getMiddleY = function(el) {
    var r = el.getBoundingClientRect();
    return (r.top + r.bottom) / 2;
};

_XPS._borderPoints = function(r, idxs) {
    var res = [];
    var rWidth = r.right - r.left;
    var rHeight = r.bottom - r.top;
    for (var i = 0; i < idxs.length; ++i) {
        var num = idxs[i];
        switch(num) {
            case 0:
                res.push([r.left + rWidth/2, r.top]);
                break;
            case 1:
                res.push([r.right, r.top + rHeight/2]);
                break;
            case 2:
                res.push([r.left + rWidth/2, r.bottom]);
                break;
            case 3:
                res.push([r.left, r.top + rHeight/2]);
                break;
            default:
                console.log('Invalid borderPoint num ' + num);
        }
    }
    return res;
};

_XPS.elInsideRect = function(el, rect) {
    var points = _XPS._borderPoints(_XPS.boundingRectForEl(el), [0, 1, 2, 3]);
    for (var i = 0; i < points.length; ++i) {
        var x = points[i][0];
        var y = points[i][1];
        if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
            return true;
        }
    }
    return false;
};

_XPS.elBelowTopOfOtherEl = function(el, otherEl, marginPx) {
    if (typeof marginPx === 'undefined') {
        marginPx = 100;
    }
    var otherTop = otherEl.getBoundingClientRect().top;
    var elTop = el.getBoundingClientRect().top;

    // console.log('otherTop', otherTop, _XPS.computeXPath(el), elTop)

    return (otherTop - marginPx) - elTop < 0;
};

_XPS.elNextToOtherEl = function(el, otherEl, marginPx) {
    if (typeof marginPx === 'undefined') {
        marginPx = 0;
    }
    var otherR = _XPS.boundingRectForEl(otherEl);
    var elR = _XPS.boundingRectForEl(el);
    var isOnLeft = elR.right < (otherR.left + marginPx);
    var isOnRight = otherR.right < (elR.left + marginPx);
    return isOnLeft || isOnRight;
};

_XPS.elDirectlyBelowOtherEl = function(el, otherEl, marginPx) {
    if (typeof marginPx === 'undefined') {
        margin = 0;
    }
    var otherR = _XPS.boundingRectForEl(otherEl);
    var elR = _XPS.boundingRectForEl(el);

    var isBelow = elR.top > otherR.top;
    if (!isBelow) {
        return false;
    }

    var isVerticallyAligned = Math.abs(elR.left - otherR.left) < marginPx;
    var isVerticallyContained = (otherR.left + marginPx) > elR.left &&
                                (otherR.right - marginPx) < elR.right; 
    var goodVerticalPosition = isVerticallyAligned || isVerticallyContained;
    if (!goodVerticalPosition) {
        return false;
    }

    var isNear = elR.top - otherR.top < 150;
    if (!isNear) {
        return false;
    }

    return true;
};

_XPS.arePartsOfSameLogicalText = function(el1, el2) {
    if (_XPS.minDistance(el1, el2) > 70) {
        return false;
    }

    var r1 = _XPS.boundingRectForEl(el1);
    var r2 = _XPS.boundingRectForEl(el2);

    var marginV = ((r1.height + r2.height) / 2) * 0.2;
    var marginH = ((r1.width + r2.width) / 2) * 0.2;

    var areVerticallyAligned = Math.abs(r1.left - r2.left) < marginV;
    var areHorizontallyAligned = Math.abs(r1.top - r2.top) < marginH;

    if (!areVerticallyAligned && !areHorizontallyAligned) {
        return false;
    }

    var fs1 = _XPS.getFontSize(el1);
    var fs2 = _XPS.getFontSize(el2);
    var avgFs = (fs1 + fs2) / 2;

    return Math.abs(fs1 - fs2) / avgFs <= avgFs*0.3;
};

_XPS.linksClusters = function(maxElTop, closeEnoughFun) {
    var anchors = _XPS.collectionToArray(document.getElementsByTagName('A'));
    anchors = _XPS.filter(_XPS.isVisiblePlus, anchors);
    anchors = _XPS.filter(function(el) { return el.getBoundingClientRect().top <= maxElTop; }, anchors);
    var cRes = _XPS.clusterCloseElements(anchors, closeEnoughFun);
    return cRes;
};

_XPS.horizontalLinksClusters = function() {
    var marginPx = 10;
    var closeEnoughFun = function(el1, el2) {
        var r1 = el1.getBoundingClientRect();
        var r2 = el2.getBoundingClientRect();
        if (Math.abs(r1.top - r2.top) > marginPx) {
            return false;
        }
        if (Math.abs(r1.bottom - r2.bottom) > marginPx) {
            return false;
        }
        return _XPS.minDistance(el1, el2) < 80;
    };
    var cRes = _XPS.linksClusters(500, closeEnoughFun);
    return cRes[0];
};

_XPS.horizontalLinksClustersRects = function() {
    var clusterArray = _XPS.horizontalLinksClusters();
    return _XPS.map(function(cluster) {
        return _XPS.boundingRectForMultipleEls(cluster, 40);
    }, clusterArray);
};

_XPS.verticalLeftLinksClusters = function() {
    var marginPx = 10;
    var closeEnoughFun = function(el1, el2) {
        var r1 = el1.getBoundingClientRect();
        var r2 = el2.getBoundingClientRect();
        if (Math.abs(r1.left - r2.left) > marginPx) {
            return false;
        }
        return _XPS.minDistance(el1, el2) < 40;
    };
    var cRes = _XPS.linksClusters(1000, closeEnoughFun);
    return cRes[0];
};

_XPS.verticalRightLinksClusters = function() {
    var marginPx = 10;
    var closeEnoughFun = function(el1, el2) {
        var r1 = el1.getBoundingClientRect();
        var r2 = el2.getBoundingClientRect();
        if (Math.abs(r1.right - r2.right) > marginPx) {
            return false;
        }
        return _XPS.minDistance(el1, el2) < 40;
    };
    var cRes = _XPS.linksClusters(1000, closeEnoughFun);
    return cRes[0];
};

_XPS.rectanglesIntersect = function(a, b) {
    if (!a || !b) {
        return false;
    }
    return (a.left <= b.right &&
            b.left <= a.right &&
            a.top <= b.bottom &&
            b.top <= a.bottom);
};

_XPS.elsOutsideRects = function(elsTexts, rects) {
    return _XPS.filter(function(elText) {
        var el = elText[0];
        return !_XPS.any(function(rect) {
            var res = _XPS.rectanglesIntersect(rect, _XPS.boundingRectForEl(el));
            if (res) {
                console.log('Intersect for text <' + elText[1] + '>: ' + rect + ' ' + _XPS.boundingRectForEl(el));
            }
        }, rects);
    }, elsTexts);
};

_XPS.elsWithoutYCoords = function(elsTexts, ys) {
    return _XPS.filter(function(elText) {
        var el = elText[0];
        return !_XPS.any(function(y) {
            var r = el.getBoundingClientRect();
            return r.top <= y && r.bottom >= y;
        }, ys);
    }, elsTexts);
};

/**
 * Minimal distance between el1, el2, computed by
 * returning minimal distance between pairs of points belonging
 * to the first and the second element.
 * 'pointsIdxs', if defined, is an array with point indexes to compute.
 * 0 - middle point of top border
 * 1 - middle point of right border
 * 2 - middle point of bottom border
 * 3 - middle point of left border
 */
_XPS.minDistance = function(el1, el2, pointsIdxs) {
    if (typeof(pointsIdxs) === 'undefined' || !pointsIdxs || !pointsIdxs.length) {
        pointsIdxs = [0, 1, 2, 3];
    }

    var r1 = _XPS.boundingRectForEl(el1);
    var r2 = _XPS.boundingRectForEl(el2);

    var mPoints1 = _XPS._borderPoints(r1, pointsIdxs);
    var mPoints2 = _XPS._borderPoints(r2, pointsIdxs);

    var distances = [];
    for (var i = 0; i < mPoints1.length; ++i) {
        for (var j = 0; j < mPoints2.length; ++j) {
            distances.push(_XPS.euclideanDistance(mPoints1[i], mPoints2[j]));
        }
    }

    var minDistance = Math.min.apply(Math, distances);
    return minDistance;
};

_XPS.addIfNotPresent = function(arr, el) {
    for (var i = 0; i < arr.length; ++i) {
        if (arr[i] === el) {
            return false;
        }
    }
    arr.push(el);
    return true;
};

/**
 * Check if elements are not further from each other than
 * maximum of widths of the elements. Used for clustering prices.
 */
_XPS.elementsCloserThanMaxWidth = function(e1, e2) {
    var r1 = e1.getBoundingClientRect();
    var r2 = e2.getBoundingClientRect();
    var width1 = r1.right - r1.left;
    var width2 = r2.right - r2.left;
    var maxWidth = Math.max(width1, width2);
    var dist = _XPS.minDistance(e1, e2);
    return dist <= maxWidth;
};

_XPS.MAX_CLUSTER_SIZE = 20;
/**
 * This function clusters "close enough" elements into arrays of elements.
 * The function 'closeEnoughFun' takes two DOM elements and tells
 * where they are close each other. Returned value is a two-element array
 * with array of clusters (arrays) as the first element, and an array
 * of not clustered element as the second.
 */
_XPS.clusterCloseElements = function(els, closeEnoughFun, selectElFun) {
    // Check if we have enough elements to process
    if (els.length <= 1) {
        return [[], []];
    }

    if (!selectElFun) {
        selectElFun = function(el) { return el; };
    }

    // Dictionary - a key is a unique XPath of DOM element,
    // a value is a cluster (array) to which this element belongs.
    var xpathToCluster = new Object();
    // array of all found clusters
    var clusters = [];
    
    // Iterate over all two-element combinations of input elements,
    // as long as we build or modify clusters
    
    var elAdded;
    var loop = 0;
    var ops = 0;

    function newOp() {
        ++ops;
        if (ops > 1000) {
            _XPS.log('Force stop ops');
            return true;
        }
        return false;
    }

    do {
        _XPS.log('Clustering loop', loop);
        if (loop > 10) {
            _XPS.log('Force stop');
            break;
        }
        ++loop;
        elAdded = false;
        for (var i = 0; i < els.length - 1; ++i) {
            for (var j = i + 1; j < els.length; ++j) {
                var eData1 = els[i];
                var eData2 = els[j];
                var e1 = selectElFun(eData1);
                var e2 = selectElFun(eData2);
                // Check if e1 and e2 elements are close enough
                var areCloseEnough = closeEnoughFun(e1, e2);
                if (areCloseEnough) {
                    _XPS.log('Elements close enough:', _XPS.computeXPath(e1), _XPS.computeXPath(e2));
                    // compute unique xpaths identifying elements
                    var xpath1 = _XPS.createXPathFromElement(e1);
                    var xpath2 = _XPS.createXPathFromElement(e2);
                    //_XPS.log('xpath1', xpath1);
                    //_XPS.log('xpath2', xpath2);
                    // check if both elements are already assigned to a cluster
                    if ((xpath1 in xpathToCluster) && (xpath2 in xpathToCluster)) {
                        //_XPS.log('xpaths in two clusters, merging');
                        // Merge two clusters - replace the second one with the first
                        var cluster1 = xpathToCluster[xpath1];
                        var cluster2 = xpathToCluster[xpath2];
                        if (cluster1.length + cluster2.length > _XPS.MAX_CLUSTER_SIZE) {
                            _XPS.log('Merged cluster would be too big, not merging');
                        } else if (cluster1 !== cluster2) {
                            for (var z = 0; z < cluster2.length; ++z) {
                                var justAdded = _XPS.addIfNotPresent(cluster1, cluster2[z]);
                                if (justAdded) {
                                    elAdded = true;
                                }
                            }
                            xpathToCluster[xpath2] = cluster1;

                            // update mapping to the new cluster for other elements also
                            for (var z = 0; z < cluster2.length; ++z) {
                                var zXpath = _XPS.createXPathFromElement(cluster2[z]);
                                if (zXpath in xpathToCluster) {
                                    xpathToCluster[zXpath] = cluster1;
                                }
                            }

                            // clear memory, but keep the empty array to save time
                            // by not deleting it from an array which requries
                            // moving all elements
                            cluster2.length = 0;
                        }
                    // if only one element belongs to a cluster,
                    // add the other to already created cluster
                    } else if (xpath1 in xpathToCluster) {
                        //_XPS.log('xpath1 has cluster');
                        if (xpathToCluster[xpath1].length + 1 > _XPS.MAX_CLUSTER_SIZE) {
                            _XPS.log('Cannot add, cluster too large');
                        } else {
                            var justAdded = _XPS.addIfNotPresent(xpathToCluster[xpath1], eData2);
                            if (justAdded) {
                                elAdded = true;
                            }
                            xpathToCluster[xpath2] = xpathToCluster[xpath1];
                        }
                    } else if (xpath2 in xpathToCluster) {
                        //_XPS.log('xpath2 has cluster');
                        if (xpathToCluster[xpath2].length + 1 > _XPS.MAX_CLUSTER_SIZE) {
                            _XPS.log('Cannot add, cluster too large');
                        } else {
                            var justAdded = _XPS.addIfNotPresent(xpathToCluster[xpath2], eData1);
                            if (justAdded) {
                                elAdded = true;
                            }
                            xpathToCluster[xpath1] = xpathToCluster[xpath2];
                        }
                    // No cluster for e1 or e2, creating new
                    } else {
                        //_XPS.log('creating new cluster');
                        elAdded = true;
                        var newCluster = [eData1, eData2];
                        xpathToCluster[xpath1] = newCluster;
                        xpathToCluster[xpath2] = newCluster;
                        clusters.push(newCluster);
                    }
                    //_XPS.log('xpathToCluster' + xpathToCluster);
                }
            }
        }
    } while (elAdded);
    //} while (false);
    _XPS.log('final xpathToCluster: ', xpathToCluster);

    // find non-clustered elements. Iterate over all elements in each cluster.
    var notClustered = [];
    for (var i = 0; i < els.length; ++i) {
        var elData = els[i];
        var found = false;
        for (var key in xpathToCluster) {
            var cluster = xpathToCluster[key];
            for (var j = 0; j < cluster.length; ++j) {
                var clusteredEl = cluster[j];
                if (clusteredEl === elData) {
                    found = true;
                    break;
                }
            }
        }
        if (!found) {
            notClustered.push(elData);
        }
    }

    // return what is already computed
    return [clusters, notClustered];
};


/**
 * Older function for clustering - checks individual pairs only.
 */
_XPS.pairCloseElements = function(els) {
    var alreadyPaired = [];
    var res = [];
    for (var i = 0; i < els.length; ++i) {
        for (var j = i + 1; j < els.length; ++j) {
            var e1 = els[i];
            var e2 = els[j];
            var r1 = e1.getBoundingClientRect();
            var r2 = e2.getBoundingClientRect();
            var width1 = r1.right - r1.left;
            var width2 = r2.right - r2.left;
            var maxWidth = Math.max(width1, width2);
            var dist = _XPS.minDistance(e1, e2);
            if (dist <= 1.0 * maxWidth) {
                if (alreadyPaired.indexOf(e1) !== -1 || alreadyPaired.indexOf(e2) !== -1) {
                    _XPS.log('Cannot pair price elements, would pair single element many times');
                    return [[], els];
                }
                alreadyPaired.push(e1);
                alreadyPaired.push(e2);
                res.push([e1, e2]);
            }
        }
    }

    var notPaired = [];
    for (var i = 0; i < els.length; ++i) {
        if (alreadyPaired.indexOf(els[i]) === -1) {
            notPaired.push(els[i]);
        }
    }
    _XPS.log('els', els);
    _XPS.log('res', res);
    _XPS.log('notPaired', notPaired);

    return [res, notPaired];
};

_XPS.areCloseEachOther = function(el1, el2) {
    return _XPS.minDistance(el1, el2) <= _XPS.PXDIST_CLOSE_EACH_OTHER;
};

_XPS.directTextContent = function(el, maxTextLength) {
    var nodes = el.childNodes;
    var text = '';
    for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].nodeType == Node.TEXT_NODE) {
            text += nodes[i].textContent.trim();
            if (maxTextLength !== undefined && text.length > maxTextLength) {
                return '<toolong>';
            }
        }
    }

    for (var replacement in _XPS.jsonData['text_replacements']) {
        text = text.replace(replacement, _XPS.jsonData['text_replacements'][replacement]);
    }

    return text;
};

_XPS.directTextContentXPath = function(xpath) {
    var el = _XPS.evaluateXPath(xpath)[0];
    return _XPS.directTextContent(el);
};

_XPS.textContentAll = function(el) {
    if (!el.textContent) {
        return '';
    }
    var t = el.textContent;
    t = t.trim();
    t = t.replace(/\s+/g, '');
    return t;
};

_XPS.textContentAllList = function(el) {
    var res = [];
    var direct = _XPS.directTextContent(el);
    if (direct) {
        res.push(direct);
    }
    for (var i = 0; i < el.children.length; ++i) {
        var child = el.children[i];
        res = res.concat(_XPS.textContentAllList(child));
    }
    return res;
};

_XPS.getAllElementsFromFrames = function() {
    return _XPS.collectFromFrames(function(win) {
        return win.document.getElementsByTagName('*');
    });
};

_XPS.getAllElements = function() {
    return document.getElementsByTagName('*');
};

_XPS.isVisible = function(el) {
    return el.offsetWidth > 0 && el.offsetHeight > 0;
};

_XPS.isVisiblePlus = function(el) {
    if (el.style.display === 'none') {
        return false;
    }
    if (window.getComputedStyle(el, null).getPropertyValue('visibility') === 'hidden') {
        return false;
    }
    if (!_XPS.isVisible(el)) {
        return false;
    }
    return true;
};

_XPS.getFontSize = function(el) {
    var style = window.getComputedStyle(el, null).getPropertyValue('font-size');
    var fontSize = parseFloat(style); 
    return (fontSize + 1);
};

_XPS._hasOneOfTags = function(el, tags) {
    if (!el || !el.tagName) {
        return false;
    }
    for (var i = 0; i < tags.length; ++i) {
        if (tags[i] == el.tagName.toLowerCase()) {
            return true
        }
    }
    return false;
};

_XPS.collectAncestorNames = function(el) {
    if (!el || el.tagName === 'HTML' || el.tagName === 'BODY') {
        return [];
    }
    var res = [el.id, el.className];
    var upperRes = _XPS.collectAncestorNames(el.parentNode);
    return res.concat(upperRes);
};


_XPS.textOrAttrValues = function(el, maxTextLength, includeAttrValues, includeCssValues) {
    var textContent = _XPS.directTextContent(el, maxTextLength);
    if (textContent === '<toolong>') {
        return '';
    }
    if (textContent) {
        return textContent;
    }
    // use first non-empty attribute value as textContent if it is not present directly
    for (var ai = 0; ai < includeAttrValues.length; ++ai) {
        var attr = includeAttrValues[ai];
        var attrValue = el.getAttribute(attr);
        if (attrValue) {
            return attrValue;
        }
    }
    
    if (includeCssValues) {
        for (ci = 0; ci < includeCssValues.length; ++ci) {
            var cssAttr = includeCssValues[ci];
            var cssAttrValue = window.getComputedStyle(el, null).getPropertyValue(cssAttr);
            if (cssAttrValue) {
                return cssAttrValue;
            }
        }
    }

    return '';
};

_XPS.getValidElementsWithText = function(invalidTagNames, invalidParentTagNames, maxTextLength,
        maxY, invalidAncestorClassIdNames, includeAttrValues, includeCssValues, elIsValidFun) {

    if (typeof(invalidAncestorClassIdNames) === 'undefined') {
        invalidAncestorClassIdNames = [];
    }
    if (typeof(includeAttrValues) === 'undefined') {
        includeAttrValues = [];
    }
    if (typeof(includeCssValues) === 'undefined') {
        includeCssValues = [];
    }
    if (typeof(elIsValidFun) === 'undefined') {
        elIsValidFun = function(el) { return true; };
    }

    var all = _XPS.getAllElements();
    var filtered = [];

    for (var i = 0; i < all.length; ++i) {
        var el = all[i];

        if (_XPS._hasOneOfTags(el, invalidTagNames)) {
            continue;
        }

        if (el.parentNode && _XPS._hasOneOfTags(el.parentNode, invalidParentTagNames)) {
            continue;
        }

        if (el.style.display === 'none') {
            continue;
        }

        if (window.getComputedStyle(el, null).getPropertyValue('visibility') === 'hidden') {
            continue;
        }

        if (!_XPS.isVisible(el)) {
            continue;
        }
        /*
        if (!VISIBILITY.isVisible(el)) {
            continue;
        }
        */

        if (!elIsValidFun(el)) {
            continue;
        };

        var textContent = _XPS.textOrAttrValues(el, maxTextLength, includeAttrValues, includeCssValues);
        if (textContent === '') {
            continue;
        }

        var elY = el.getBoundingClientRect().top;
        if (maxY && elY && elY >= maxY) {
            continue;
        }

        // Check if any of parent nodes or the node itself has class or id
        // containing an invalid substring
        var gotInvalidClassId = false;
        var ancestorNames = _XPS.collectAncestorNames(el);
        //_XPS.log('ancestorNames' + ancestorNames);
        //_XPS.log('invalidAncestorClassIdNames ' + invalidAncestorClassIdNames);
        for (var z = 0; z < invalidAncestorClassIdNames.length; ++z) {
            if (gotInvalidClassId) {
                break;
            }
            for (var zz = 0; zz < ancestorNames.length; ++zz) {
                if (typeof ancestorNames[zz] !== 'string' || !ancestorNames[zz]) {
                    continue;
                }
                if (ancestorNames[zz].toLowerCase().indexOf(invalidAncestorClassIdNames[z]) !== -1) {
                    gotInvalidClassId = true;
                    break;
                }
            }
        }
        if (gotInvalidClassId) {
            continue;
        }

        filtered.push([el, textContent]);
    }

    return filtered;
};

_XPS.containsTag = function(el, tagName) {
    var rec = function(elArg) {
        if (!elArg) {
            return false;
        }
        if (elArg.tagName.toLowerCase() === tagName) {
            return true;
        }
        for (var i = 0; i < elArg.children; ++i) {
            if (rec(elArg.children[i])) {
                return true;
            }
        }
        return false;
    };
    if (el.parentNode && el.parentNode.tagName.toLowerCase() === tagName) {
        return true;
    }
    return rec(el);
};

_XPS.visibleLinksToDomains = function(domains, linksOnly, fromFrames, skipGlobal,
        invalidFrameUrlArray, invalidFrameIdArray, invalidRootXPathArray) {
    if (typeof(invalidRootXPathArray) === 'undefined') {
        invalidRootXPathArray = [];
    }

    var invalidRootEls = _XPS.flatten(_XPS.map(_XPS.evaluateXPath, invalidRootXPathArray));
    console.log('invalidRootXPathArray:' + invalidRootXPathArray);
    console.log('invalidRootEls:', invalidRootEls);

    var elIsValid = function(el) {
        return !_XPS.any(function(rootEl) { return _XPS.isChild(rootEl, el); }, invalidRootEls);
    }

    var aEls, areaEls;
    if (fromFrames) {
        aEls = _XPS.collectFromFrames(function(win) {
            var aEls = win.document.getElementsByTagName('A');
            if (win === window) {
                aEls = _XPS.filter(elIsValid, aEls);
            }
            for (var i = 0; i < aEls.length; ++i) {
                var href = aEls[i].getAttribute('href');
                if (href && href.indexOf('facebook') !== -1) {
                    console.log('Found link ' + href + ' in ' + win.document.URL);
                }
            }
            return aEls;
        }, skipGlobal, invalidFrameUrlArray, invalidFrameIdArray);

        areaEls = _XPS.collectFromFrames(function(win) {
            var arEls = win.document.getElementsByTagName('AREA');
            if (win === window) {
                arEls = _XPS.filter(elIsValid, arEls);
            }
            return arEls;
        }, skipGlobal, invalidFrameUrlArray, invalidFrameIdArray);

    } else {
        aEls = _XPS.filter(elIsValid, document.getElementsByTagName('A'));
        areaEls = _XPS.filter(elIsValid, document.getElementsByTagName('AREA'));
    }
    anchors = _XPS.collectionToArray(aEls).concat(_XPS.collectionToArray(areaEls));
    var res = [];
    for (var i = 0; i < domains.length; ++i) {
        var domain = domains[i];
        for (var j = 0; j < anchors.length; ++j) {
            var anchor = anchors[j];
            var link = anchor.getAttribute('href');
            if (!link) {
                continue;
            }
            if (link.toLowerCase().indexOf(domain) !== -1) {
                if (linksOnly) {
                    res.push(link);
                } else {
                    res.push([anchor, link]);
                }
            }
        }
    }
    return res;
};


_XPS.visibleLinksWithTexts = function(texts, maxTextContentLength) {
    var aEls = document.getElementsByTagName('A');
    var areaEls = document.getElementsByTagName('AREA');
    var anchors = _XPS.collectionToArray(aEls).concat(_XPS.collectionToArray(areaEls));
    var res = [];
    for (var i = 0; i < texts.length; ++i) {
        var text = texts[i];
        for (var j = 0; j < anchors.length; ++j) {
            var anchor = anchors[j];

            var link = anchor.getAttribute('href');
            if (!link) {
                continue;
            }
            if (link.indexOf('mailto') === 0) {
                continue;
            }
            if (link.toLowerCase().indexOf(text) !== -1) {
                res.push(link);
            }

            var textContent = _XPS.directTextContent(anchor, maxTextContentLength);
            if (!textContent || textContent === '<toolong>') {
                continue;
            }
            if (textContent.toLowerCase().indexOf(text) !== -1) {
                res.push(link);
            }
        }
    }
    return res;
};

_XPS.allLinks = function() {
    var anchors = document.getElementsByTagName('A');
    var res = [];
    for (var i = 0; i < anchors.length; ++i) {
        var a = anchors[i];
        if (a.href) {
            res.push(a.href);
        }
    }
    return res;
};

_XPS.distanceLessThan = function(d) {
    return function(e1, e2) {
        if (e1.tagName === 'OPTION') {
            e1 = e1.parentNode;
        }
        if (e2.tagName === 'OPTION') {
            e2 = e2.parentNode;
        }
        var dist = _XPS.minDistance(e1, e2);
        return dist <= d;
    };
};

_XPS.elsCloserThan = function(dist, el, otherEls) {
    var res = [];
    for (var i = 0; i < otherEls.length; ++i) {
        var other = otherEls[i];
        var d = _XPS.minDistance(el, other);
        //console.log('between', _XPS.computeXPath(el), _XPS.computeXPath(other), d);
        if (d <= dist) {
            res.push(other);
        }
    }
    //console.log('ress', res.length);
    return res;
};

_XPS.attrsObject = function(el, attrArr, cssArr) {
    if (typeof attrArr === 'undefined') {
        attrArr = ['alt', 'href', 'class', 'src', 'value'];
    }
    if (typeof cssArr === 'undefined') {
        cssArr = [];
    }

    res = {};
    res['boundingRectangle'] = _XPS.boundingRectForEl(el);

    res['attrs'] = {};
    res['attrs']['text'] = _XPS.directTextContent(el, 100);
    //res['tagName'] = el.tagName;
    for (var i = 0; i < attrArr.length; ++i) {
        var attr = attrArr[i];
        var attrValue = el.getAttribute(attr);
        if (attrValue) {
            res['attrs'][attr.toLowerCase()] = attrValue.toLowerCase();
        }
    }

    for (var i = 0; i < cssArr.length; ++i) {
        var cssAttr = cssArr[i];
        var cssAttrValue = window.getComputedStyle(el, null).getPropertyValue(cssAttr);
        if (cssAttrValue) {
            res['attrs'][cssAttr.toLowerCase()] = cssAttrValue.toLowerCase();
        }
    }

    return res;
};

_XPS.xpathsAttrsWithWords = function(words, attrArr, cssArr) {
    var els = _XPS.getAllElements(); 

    var elsAttrs = _XPS.map(function(el) { return [el, _XPS.attrsObject(el, attrArr, cssArr)]; }, els);

    elsAttrs = _XPS.filter(function(elAttr) { return _XPS.isVisiblePlus(elAttr[0]); }, elsAttrs);

    elsAttrs = _XPS.filter(function(elAttr) { return _XPS.boundingRectIsValid(elAttr[0]); }, elsAttrs);

    elsAttrs = _XPS.filter(function(elAttr) {
        if (!elAttr[1]) {
            return false;
        }
        for (var k in elAttr[1]['attrs']) {
            if (_XPS.phraseInArray(elAttr[1]['attrs'][k], words)) {
                elAttr[1]['foundIn'] = k;
                return true;
            }
        }
        return false;
    }, elsAttrs);

    return _XPS.map(function(elAttr) { return [_XPS.computeXPath(elAttr[0]), elAttr[1]]; },
            elsAttrs);
};

_XPS.xpathsAttrsHavingTexts = function() {
    var els = _XPS.getAllElements(); 

    var elsAttrs = _XPS.map(function(el) { return [el, _XPS.attrsObject(el)]; }, els);

    elsAttrs = _XPS.filter(function(elAttr) { return elAttr[1]['attrs']['text']; }, elsAttrs);

    elsAttrs = _XPS.filter(function(elAttr) { return _XPS.isVisiblePlus(elAttr[0]); }, elsAttrs);

    elsAttrs = _XPS.filter(function(elAttr) { return _XPS.boundingRectIsValid(elAttr[0]); }, elsAttrs);

    return _XPS.map(function(elAttr) { return [_XPS.computeXPath(elAttr[0]), elAttr[1]]; },
            elsAttrs);
};


_XPS.findIframe = function(src) {
    var matching = _XPS.filter(function(el) { return el.src && el.src.indexOf(src) !== -1; },
            document.getElementsByTagName('IFRAME'));
    if (matching.length === 0) {
        return null;
    }
    return matching[0].src;
};

