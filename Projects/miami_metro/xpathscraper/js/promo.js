_XP = {};

_XP.findPromoClusteredCandidates = function() {
    var xpathsAttrs = _XPS.xpathsAttrsHavingTexts();
    var clusteringRes = _XPS.clusterCloseElements(xpathsAttrs, function(el1, el2) {
            var t1 = _XPS.directTextContent(el1);
            var t2 = _XPS.directTextContent(el2);
            if (!_XPS.substringInArray(t1, _XPS.jsonData['promo_words']) &&
                !_XPS.substringInArray(t2, _XPS.jsonData['promo_words'])) {
                    return false;
            }
            return _XPS.arePartsOfSameLogicalText(el1, el2);
        }, function(xa) {
            return _XPS.evaluateXPathFirst(xa[0]);
        }
    );
    return clusteringRes;
};

