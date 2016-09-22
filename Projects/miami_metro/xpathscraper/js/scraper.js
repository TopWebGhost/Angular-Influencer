/**
 * Names
 */

_XPS.combineNameEls = function(elsTexts, dist) {
    if (typeof dist === 'undefined') {
        dist = 50;
    }
    var res = [];
    for (var i = 0; i < elsTexts.length; ++i) {
        for (var j = i + 1; j < elsTexts.length; ++j) {
            var et1 = elsTexts[i];
            var et2 = elsTexts[j];
            if (_XPS.minDistance(et1[0], et2[0]) <= dist) {
                res.push([et1, et2]);
            }
        }
    }
    return res;
};

/**
 * Cluster prices using elementsCloserThanMaxWidth function.
 */
_XPS.clusterPriceElements = function(els) {
    return _XPS.clusterCloseElements(els, _XPS.elementsCloserThanMaxWidth);
};

_XPS.clusterPriceFragments = function(els) {
    var cRes = _XPS.clusterCloseElements(els, function(e1, e2) {
        return _XPS.minDistance(e1, e2) <= 8;
    });
    var res = [];
    for (var i = 0; i < cRes[0].length; ++i) {
        var cluster = cRes[0][i];
        var ancestor = _XPS.findCommonAncestor(cluster);
        if (ancestor) {
            var t = _XPS.textContentAll(ancestor);
            res.push([ancestor, t]);
        }
    }
    return res;
};

_XPS.clusterElsTexts = function(elsTexts, minDistancePx) {
    var cRes = _XPS.clusterCloseElements(elsTexts,
        function(e1, e2) {
            if (!e1 || !e2) {
                return false;
            }
            //console.log('distance', _XPS.computeXPath(e1), _XPS.computeXPath(e2), _XPS.minDistance(e1, e2));
            return _XPS.minDistance(e1, e2) <= minDistancePx;
        },
        function(elText) {
            return elText[0];
        });
    return cRes[0];
};

// A score for element importance - <h>, <strong>, etc. tags give points
_XPS.tagImportance = {
    'H1': 2.0,
    'H2': 1.5,
    'H3': 1.4,
    'H4': 1.4,
    'H5': 1.3,
    'H6': 1.3,
    'STRONG': 1.2,
    'EM': 1.1
};
_XPS.elementImportance = function(el) {
    var elScore = 1.0;

    if (el.tagName in _XPS.tagImportance) {
        elScore += _XPS.tagImportance[el.tagName];
    }

    if (el.parentNode && el.parentNode.tagName in _XPS.tagImportance) {
        elScore += _XPS.tagImportance[el.parentNode.tagName];
    }

    elScore = Math.min(elScore, 2.0);

    return elScore;
};

_XPS._emailRegexArray = [
    /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}\b/gi,
    /\b[A-Z0-9._%+-]+[\s\{\(]*at[\s\}\)]*[A-Z0-9.-]+[\{\(\s]*dot[\}\(\s]*[A-Z]{2,4}\b/gi
];
_XPS._invalidEmailTags = ['script', 'meta'];
_XPS.findEmails = function() {
    var els = _XPS.getAllElementsFromFrames();
    var elsEmails = [];
    for (var i = 0; i < els.length; ++i) {
        var el = els[i];
        if (_XPS._invalidEmailTags.indexOf(el.tagName.toLowerCase()) !== -1) {
            continue;
        }
        var text = _XPS.directTextContent(el, 10000);
        var href = el.getAttribute('href');
        if (!href || href.toLowerCase().indexOf('mailto:') != 0) {
            href = '';
        }
        for (var j = 0; j < _XPS._emailRegexArray.length; ++j) {
            var regex = _XPS._emailRegexArray[j];
            var s = text + ' ' + href;
            var matches = (s).match(regex);
            if (matches && matches.length) {
                for (var k = 0; k < matches.length; ++k) {
                    elsEmails.push([el, matches[k]]);
                }
            }
        }
    }
    elsEmails.sort(function(elEmail1, elEmail2) {
        var y1 = elEmail1[0].getBoundingClientRect().top;
        var y2 = elEmail2[0].getBoundingClientRect().top;
        return y2 - y1;
    });
    return _XPS.map(_XPS.snd, elsEmails);
};

/**
 * Sizes
 */

_XPS.SIZE_BLACKLIST = ['color', 'colour', 'rate', 'review', 'rating', 'star', 'weight', 'out of', 'heart'];

_XPS.SIZE_ID_CLASS_WHITELIST = ['size'];

_XPS.findQuantitySelectsAndOptions = function() {
    var res = [];
    var selects = document.getElementsByTagName('SELECT');
    for (var i = 0; i < selects.length; ++i) {
        var select = selects[i];
        if (_XPS.idOrClassInArray(select, _XPS.SIZE_ID_CLASS_WHITELIST)) {
            continue;
        }

        var foundWhitelistedOption = false;
        for (var j = 0; j < select.options.length; ++j) {
            var option = select.options[j];
            if (_XPS.idOrClassInArray(option, _XPS.SIZE_ID_CLASS_WHITELIST)) {
                foundWhitelistedOption = true;
                break;
            }
        }
        if (foundWhitelistedOption) {
            continue;
        }

        var nums = [];
        for (var j = 0; j < select.options.length; ++j) {
            var option = select.options[j];
            var n = parseFloat(option.innerHTML);
            if (!isNaN(n)) {
                nums.push(n);
            }
        }

        // check if nums is a range of consecutive integers
        if (nums.length <= 2) {
            continue;
        }
        var areConsecutive = true;
        for (var k = 1; k <= nums.length; ++k) {
            if (k !== nums[k - 1]) {
                areConsecutive = false;
                break;
            }
        }
        if (!areConsecutive) {
            continue;
        }

        res.push(select);
        for (var j = 0; j < select.options.length; ++j) {
            var option = select.options[j];
            res.push(option);
        }
    }
    return res;
};

_XPS.findSizeElementsCandidates = function(resultElsXPaths, excludeFromXPaths) {
    //console.log('size resultElsXPaths: ' + resultElsXPaths);
    var resultEls = _XPS.map(function(xpath) { return _XPS.evaluateXPath(xpath)[0]; }, resultElsXPaths);
    resultEls = _XPS.filter(function(el) { return el; }, resultEls);
    var containingRect = _XPS.boundingRectForMultipleEls(resultEls, 300);
    //console.log('size containingRect: ', containingRect);

    var quantityEls = _XPS.findQuantitySelectsAndOptions();
    var isQuantityEl = function(el) { return _XPS.isElementInArray(el, quantityEls); };

    var excludedEls = _XPS.flatten(_XPS.map(_XPS.evaluateXPath, excludeFromXPaths));
    var isExcludedEl = function(el) {
        return _XPS.any(function(exEl) { return _XPS.isChild(exEl, el); }, excludedEls);
    };
    console.log('excludeFromXPaths', excludeFromXPaths);
    console.log('excludedEls: ', excludedEls);

    var containsBlacklistedWord = function(el) {
        var attrsObject = _XPS.attrsObject(el, _XPS.jsonData['attrs_with_text']);
        console.log('attrsObject', attrsObject);
        return _XPS.any(function(val) {
                return _XPS.substringInArray(val, _XPS.SIZE_BLACKLIST);
            }, _XPS.values(attrsObject['attrs']));
    };

    var elIsValid = function(el) {
        if (isQuantityEl(el)) {
            return false;
        }
        if (isExcludedEl(el)) {
            return false;
        }
        if (containsBlacklistedWord(el)) {
            return false;
        }
        return true;
    };

    var elsWithText = _XPS.getValidElementsWithText([], [], 30, 800, [],
            _XPS.jsonData['attrs_with_text'], [], elIsValid);
    var res = [];
    for (var i = 0; i < elsWithText.length; ++i) {
        var el = elsWithText[i][0];
        var text = elsWithText[i][1];

        if (!_XPS.elInsideRect(el, containingRect)) {
            continue;
        }

        var foundBlacklisted = false;
        for (var sbi = 0; sbi < _XPS.SIZE_BLACKLIST.length; ++sbi) {
            if (text && text.toLowerCase().indexOf(_XPS.SIZE_BLACKLIST[sbi].toLowerCase()) !== -1) {
                foundBlacklisted = true;
                break;
            }
        }
        if (foundBlacklisted) {
            continue;
        }

        var words = _XPS.splitWords(text);
        if (!words) {
            continue;
        }

        var foundNum = false;
        for (var wi = 0; wi < words.length; ++wi) {
            var word = words[wi];
            if (_XPS.representsNumber(word)) {
                foundNum = true;
                break;
            }
        }

        var foundAlphaSize = false;
        for (var as = 0; as < _XPS.jsonData['sizes'].length; ++as) {
            for (var wi = 0; wi < words.length; ++wi) {
                if (words[wi] && words[wi].toLowerCase() === _XPS.jsonData['sizes'][as]) {
                    foundAlphaSize = true;
                    break;
                }
            }
        }

        if (!foundNum && !foundAlphaSize) {
            continue;
        }

        res.push([el, text]);
    }
    return res;
};

_XPS.generateClusters = function(elsTexts, dists) {
    var res = [];
    _XPS.log(elsTexts.length, 'elements for clustering');
    for (var i = 0; i < dists.length; ++i) {
        var dist = dists[i];
        _XPS.log('Clustering for dist', dist);
        var cRes = _XPS.clusterCloseElements(elsTexts, _XPS.distanceLessThan(dist),
                function(elText) { return elText[0]; });
        _XPS.log('Got', cRes[0].length, 'clusters,', cRes[1].length, 'not clustered');
        for (var ci = 0; ci < cRes[0].length; ++ci) {
            var cluster = cRes[0][ci];
            res.push([dist, cluster]);
        }
        // Include one-element clusters only for the smallest distance
        // (doesn't make much sense to repeat them for every distance)
        if (i == 0) {
            for (var ci = 0; ci < cRes[1].length; ++ci) {
                var cluster = [cRes[1][ci]];
                res.push([dist, cluster]);
            }
        }
    }
    return res;
};

_XPS.clusterIncremental = function(els, distLimitStart, distLimitEnd, distStep) {
    var totalEls = els.length;
    var bestCluster = [];
    for (var distLimit = distLimitStart; distLimit <= distLimitEnd; distLimit += distStep) {
        var cRes = _XPS.clusterCloseElements(els, function(e1, e2) {
            var dist = _XPS.minDistance(e1, e2);
            return dist <= distLimit;
        });

        if (!cRes[0]) {
            continue;
        }

        // Find best cluster
        for (var ci = 0; ci < cRes[0].length; ++ci) {
            var cluster = cRes[0][ci];
            if (cluster.length > bestCluster.length) {
                bestCluster = cluster;
            }
        }
    }
    return bestCluster;
};

_XPS.findSizeElements = function() {
    var elsWithText = _XPS.findSizeElementsCandidates();
    var els = [];
    for (var i = 0; i < elsWithText.length; ++i) {
        els.push(elsWithText[i][0]);
    }
    var res = _XPS.clusterIncremental(els, 2, 40, 2);
    return res;
};

/**
 * Colors
 */

_XPS.COLOR_BLACKLIST = [];
_XPS.COLOR_WORDS_OBJECT = null;

_XPS._initColorData = function() {
    if (_XPS.COLOR_WORDS_OBJECT) {
        return;
    }
    _XPS.COLOR_WORDS_OBJECT = {};
    for (var i = 0; i < _XPS.jsonData['colors'].length; ++i) {
        var color = _XPS.jsonData['colors'][i];
        var words = _XPS.splitWords(color);
        for (var wi = 0; wi < words.length; ++wi) {
            var word = words[wi];
            _XPS.COLOR_WORDS_OBJECT[word] = null;
        }
    }
};

_XPS._initColorData();

_XPS.findColorElementsCandidates = function(resultElsXPaths, excludeFromXPaths) {
    var resultEls = _XPS.map(function(xpath) { return _XPS.evaluateXPath(xpath)[0]; }, resultElsXPaths);
    resultEls = _XPS.filter(function(el) { return el; }, resultEls);
    var containingRect = _XPS.boundingRectForMultipleEls(resultEls);

    var elsWithText = _XPS.getValidElementsWithText([], [], 100, 800, [],
            [], []);
    var res = [];
    for (var i = 0; i < elsWithText.length; ++i) {
        var el = elsWithText[i][0];
        var text = elsWithText[i][1];
        
        if (!_XPS.elInsideRect(el, containingRect)) {
            continue;
        }

        var foundBlacklisted = false;
        for (var sbi = 0; sbi < _XPS.COLOR_BLACKLIST.length; ++sbi) {
            if (text && text.toLowerCase().indexOf(_XPS.COLOR_BLACKLIST[sbi].toLowerCase()) !== -1) {
                foundBlacklisted = true;
                break;
            }
        }
        if (foundBlacklisted) {
            continue;
        }

        var words = _XPS.splitWords(text.toLowerCase());
        if (!words) {
            continue;
        }

        var foundColor = false;
        for (var wi = 0; wi < words.length; ++wi) {
            var word = words[wi];
            if (word in _XPS.COLOR_WORDS_OBJECT) {
                console.log('word <' + word + '> in COLOR_WORDS_OBJECT, adding <' + text);
                foundColor = true;
                break;
            }
        }
        if (!foundColor) {
            continue;
        }

        res.push([el, text]);
    }
    return res;
};

_XPS.findSizetypeElementsCandidates = function() {
    var elsWithText = _XPS.getValidElementsWithText([], [], 30, 800, [],
            _XPS.jsonData['attrs_with_text'], []);

    var res = _XPS.filter(function(elText) {
        var text = elText[1];
        return _XPS.substringInArray(text, _XPS.jsonData['sizetypes']);
    }, elsWithText);

    return res;
};

_XPS.findInseamElementsCandidates = function() {
    var elsWithText = _XPS.getValidElementsWithText([], [], 30, 800, [],
            _XPS.jsonData['attrs_with_text'], []);

    var res = _XPS.filter(function(elText) {
        var text = elText[1];
        return _XPS.wordInArray(text, _XPS.jsonData['inseams']);
    }, elsWithText);

    return res;
};

_XPS.findReviewXPathCandidates = function() {
    return _XPS.xpathsAttrsWithWords(Object.keys(_XPS.jsonData['review_words']));
};
