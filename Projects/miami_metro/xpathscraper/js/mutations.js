_XPS.OBSERVER_CONFIG =  {
    attributes: true,
    childList: true,
    characterData: true,
    subtree: true,
    attributeOldValue: true
};

_XPS.BLACKLISTED_OBSERVER_ATTRIBUTES = ['script', 'style', 'src', 'class', 'type'];
_XPS.BLACKLISTED_NEW_EL_TAGS = ['script', 'meta'];
_XPS.observeChanges = function(newTextHandler) {
    var handleMutations = function(mutations) {
        for (var i = 0; i < mutations.length; ++i) {
            var m = mutations[i];
            if (m.type === 'attributes') {
                if (_XPS.BLACKLISTED_OBSERVER_ATTRIBUTES.indexOf(m.attributeName.toLowerCase()) === -1) {
                    newTextHandler(m, m.target.getAttribute(m.attributeName));
                }
            } else if (m.type === 'characterData') {
                newTextHandler(m, m.target.data);
            } else if (m.type === 'childList') {
                if (m.addedNodes) {
                    for (var j = 0; j < m.addedNodes.length; ++j) {
                        var node = m.addedNodes[j];
                        if (node.tagName && _XPS.BLACKLISTED_NEW_EL_TAGS.indexOf(
                                    node.tagName.toLowerCase()) !== -1) {
                            continue;
                        }
                        if (node instanceof Text) {
                            newTextHandler(m, node.data);
                        } else {
                            var textsFromEl = _XPS.textsFromElContentAndAttrs(node, true,
                                    _XPS.BLACKLISTED_OBSERVER_ATTRIBUTES);
                            for (var k = 0; k < textsFromEl.length; ++k) {
                                var t = textsFromEl[k];
                                newTextHandler(m, t);
                            }
                        }
                    }
                }
            } else {
                console.log('Unknown mutation type ' + m.type);
            }
        }
    };
    var observer = new MutationObserver(handleMutations);
    var target = document.body;
    observer.observe(target, _XPS.OBSERVER_CONFIG);
};

_XPS.noticedColors = [];
_XPS.clearNoticedColors = function() { _XPS.noticedColors.length = 0; };
_XPS.noticedColorTextCandidate = function(m, text) {
    if (!text) {
        return;
    }

    var words = _XPS.splitWords(text.toLowerCase());

    var foundColor = false;
    for (var wi = 0; wi < words.length; ++wi) {
        var word = words[wi];
        if (word in _XPS.COLOR_WORDS_OBJECT) {
            foundColor = true;
            break;
        }
    }
    if (foundColor) {
        console.log('COLOR TEXT: ' + text);
    }
    _XPS.noticedColors.push([m, text]);
};


_XPS.isSmallRectangle = function(el) {
    var r = el.getBoundingClientRect();
    return r.height > 5 && r.height < 60
        && r.width > 5 && r.width < 60
        && (r.width/r.height) < 2 && (r.width/r.height) > 0.5;
};

_XPS.isSizeChartEl = function(el) {
    var toCheck = [_XPS.directTextContent(el),
        el.href,
        el.src,
        el.alt,
        el.className
    ];
    for (var i = 0; i < toCheck.length; ++i) {
        var t = toCheck[i];
        if (!t) {
            continue;
        }
        t = t.toLowerCase();
        t = t.replace(/[\s-_]+/g, '');
        if (t.indexOf('sizechart') !== -1) {
            return true;
        }
    }
    return false;
};

_XPS.getColorElementsXPathsToClick = function(resultElsXPaths) {
    console.log('resultElsXPaths', resultElsXPaths);

    var resultEls = _XPS.map(function(xpath) { return _XPS.evaluateXPath(xpath)[0]; },
            resultElsXPaths);

    var els = _XPS.getAllElements();

    els = _XPS.filter(_XPS.isSmallRectangle, els);

    els = _XPS.filter(_XPS.isVisible, els);

    els = _XPS.filter(function(el) {
        var ao = _XPS.attrsObject(el);
        return !_XPS.any(function(val) {
            if (!val) {
                return false;
            }
            return _XPS.substringInArray(val, _XPS.jsonData['clicking_texts_blacklist']);
        }, _XPS.values(ao['attrs']));
    }, els);

    els = _XPS.filter(function(el) { return !_XPS.isSizeChartEl(el); }, els);

    var containingRect = _XPS.boundingRectForMultipleEls(resultEls, 100);
    console.log('containingRect:', containingRect);
    els = _XPS.filter(function(el) { return _XPS.elInsideRect(el, containingRect); }, els);

    els = _XPS.removeChildrenFromArray(els, true);

    return _XPS.map(_XPS.computeXPath, els);
};

_XPS.observeColorChanges = function() {
    _XPS.clearNoticedColors();
    _XPS.observeChanges(_XPS.noticedColorTextCandidate);
};

