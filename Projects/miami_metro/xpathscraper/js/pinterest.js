_P = {};

function append_str(str1, str2) {
    var res = str1 + ' ' + str2;
    return res
}

/*
 * Pin
 */

_P.Pin = function(anchorEl) {
    this.anchorEl = anchorEl;
    this.div = _XPS.findAncestorWithClassName(this.anchorEl, 'pinWrapper');
    
    hrefParts = this.anchorEl.href.split('/');
    if (hrefParts[hrefParts.length - 1] === '') {
        this.pinId = hrefParts[hrefParts.length - 2];
    } else {
        this.pinId = hrefParts[hrefParts.length - 1];
    }

    this.imgEl = this.div.getElementsByTagName('IMG')[0];
    this.descriptionEl = this.div.getElementsByClassName('pinDescription')[0];
    this.creditsEl = this.div.getElementsByClassName('pinCredits')[0];
    this.repinCountEl = this.div.getElementsByClassName('repinCountSmall')[0];
    this.likeCountEl = this.div.getElementsByClassName('likeCountSmall')[0];
    this.commentCountEl = this.div.getElementsByClassName('commentCountSmall')[0];
    this.sourceA = this.div.getElementsByClassName('navLinkOverlay')[0];
    this.moreDescriptionEls = this.div.getElementsByClassName('vaseText');
    this.titleEl = this.div.getElementsByClassName('pinImageWrapper')[0];
};

_P.Pin.prototype.getURL = function() {
    return this.anchorEl.href;
};

_P.Pin.prototype.toJSON = function() {

    var descr = this.descriptionEl ? _XPS.directTextContent(this.descriptionEl) : '';
    for (var i = 0; i < this.moreDescriptionEls.length; i++) {
        var text = this.moreDescriptionEls[i].innerText || this.moreDescriptionEls[i].textContent;
        descr = append_str(descr, text ? text : '')
    };

    return {
        'id': this.pinId,
        'url': this.getURL(),
        'img': this.imgEl.src,
        'description': descr,
        'likeCount': this.likeCountEl ? _XPS.directTextContent(this.likeCountEl) : '',
        'repinCount': this.repinCountEl ? _XPS.directTextContent(this.repinCountEl) : '',
        'commentCount': this.commentCountEl ? _XPS.directTextContent(this.commentCountEl) : '',
        'sourceA': this.sourceA ? this.sourceA.href : '',
        'pinnedBy': this.creditsEl ? this.creditsEl.querySelector('a').href : '',
        'title': this.titleEl ? this.titleEl.getAttribute('title') : '',
    };
};

_P.cleanUpPinsPage = function() {
    //Remove the modal popup click blocker
    var modalBlocker = document.getElementsByClassName('Modal');
    if (modalBlocker != null){
        modalBlocker = modalBlocker[0];
        modalBlocker.parentNode.removeChild(modalBlocker);
    }
    // clear the noscroll, etc classes from body
    document.body.className = '';
}


/*
 * PagePins
 */

_P.MAX_PINS = 50;
_P.SCROLL_ITERATIONS = 30;
_P.SCROLL_SLEEP = 1000;
_P.SCROLL_BY_PAGES = 10;

_P.PagePins = function() {
    this.allPins = {};
    this.pinCount = 0;
    this.findGoing = false;
    this.reachedOldPins = false;
};

_P.PagePins.prototype.getPins = function() {
    var res = [];
    for (var pinId in this.allPins) {
        res.push(this.allPins[pinId]);
    }
    return res;
};

_P.PagePins.prototype.addPin = function(pin) {
    if (pin.pinId in this.allPins) {
        // console.log('pin with id', pid.pinId, 'already added');
    } else {
        this.allPins[pin.pinId] = pin;
        ++this.pinCount;
    }
};

_P.PagePins.prototype._findPinsOnCurrentPage = function() {
    var anchors = document.getElementsByTagName('A');
    var res = [];
    for (var i = 0; i < anchors.length; ++i) {
        var a = anchors[i];
        if (!a.href) {
            continue;
        }
        if (a.href.match(/.*\/pin\/\d+\/?$/)) {
            //console.log('Found pin link', a.href);
            var foundPin = new _P.Pin(a);
            console.log('new pin id', foundPin.pinId);
            if (_P.lastPinIds[foundPin.pinId]) {
                // Reached pins we'd already fetched. Bail out.
                _P.reachedOldPins = true;
                break;
            }
            this.addPin(foundPin);
        }
    }
    return res;
};

_P.PagePins.prototype._findAllIteration = function(iter) {
    console.log('Fetch iteration ' + iter);
    var shouldStop = false;
    var beforeCount = this.pinCount;
    this._findPinsOnCurrentPage();
    var _afterCount = this.pinCount;
    console.log('Added ' + (_afterCount - beforeCount) + ' new pins');
    if (_P.reachedOldPins) {
        console.log('Reached old pins.');
        shouldStop = true;
    }
    if (_afterCount >= _P.MAX_PINS) {
        console.log('Reached max pins.');
        shouldStop = true;
    }
    return this._findAll(iter + 1, shouldStop);
};

_P.PagePins.prototype._findAll = function(iter, shouldStop) {
    if (shouldStop || iter >= _P.SCROLL_ITERATIONS) {
        console.log('Find finished');
        this.findGoing = false;
        return;
    }
    window.scrollByPages(_P.SCROLL_BY_PAGES);
    var that = this;
    window.setTimeout(function() { that._findAllIteration(iter); }, _P.SCROLL_SLEEP);
};

_P.PagePins.prototype.find = function() {
    this.findGoing = true;
    this._findAll(0, false);
};


/*
 * Single pin page view
 */

_P.SinglePinPage = function() {
    this.elem = document.querySelectorAll('.pinWrapper')[0];
    this.repinCountEl = this.elem.getElementsByClassName('repinCountSmall')[0];
    this.likeCountEl = this.elem.getElementsByClassName('likeCountSmall')[0];
    this.commentCountEl = this.elem.getElementsByClassName('commentCountSmall')[0];
    this.sourceA = this.elem.getElementsByClassName('navLinkOverlay')[0];
    this.pinurl = this.elem.getElementsByClassName('pinImageWrapper')[0];

    //this.pincrediturl = this.elem.querySelectorAll('.creditItem, .pinnedBy')[0].getElementsByTagName('a')[0];
    this.pincrediturl = this.elem.querySelectorAll('.creditItem, .pinnedBy')[0];

    this.creditsEl = this.elem.getElementsByClassName('pinCredits')[0];
    this.descriptionEl = this.elem.getElementsByClassName('pinDescription')[0];
    this.imgEl = this.elem.getElementsByTagName('img')[0];
    this.moreDescriptionEls = this.elem.getElementsByClassName('vaseText');
    this.titleEl = this.elem.getElementsByClassName('pinImageWrapper')[0];
    //this.commentEls = document.querySelectorAll('.pinDescription .pinDescriptionComment');
    //this.sourceA = document.querySelector('.sourceFlagWrapper a');
    //this.userBaseA = document.querySelector('.UserBase a');
};

_P.SinglePinPage.prototype._parseComment = function(cDiv) {
    var res = {};
    res.authorName = cDiv.querySelector('.commentDescriptionCreator').textContent.trim();
    timeContainer = cDiv.querySelector('.commentDescriptionTimeAgo');
    if (timeContainer != null) {
        res.timeAgo = timeContainer.textContent.trim();
    }
    textContainer = cDiv.querySelector('.commentDescriptionContent');
    if (textContainer != null){
        res.text = textContainer.textContent.trim();
    }

    return res;
};

_P.SinglePinPage.prototype.toJSON = function() {

    var descr = this.descriptionEl ? _XPS.directTextContent(this.descriptionEl) : '';
    for (var i = 0; i < this.moreDescriptionEls.length; i++) {
        var text = this.moreDescriptionEls[i].innerText || this.moreDescriptionEls[i].textContent;
        descr = append_str(descr, text ? text : '');
    };

    return {
        'likeCount': this.likeCountEl ? _XPS.directTextContent(this.likeCountEl) : '',
        'repinCount': this.repinCountEl ? _XPS.directTextContent(this.repinCountEl) : '',
        'commentCount': this.commentCountEl ? _XPS.directTextContent(this.commentCountEl) : '',
        'sourceA': this.sourceA ? this.sourceA.href : '',
        'pinUrl': this.pinurl ? this.pinurl.href : '',
        'pinCreditUrl': this.pincrediturl ? this.pincrediturl.querySelector('a').href : '',
        'pinnedBy': this.creditsEl ? this.creditsEl.querySelector('a').href : '',
        'img': this.imgEl ? this.imgEl.src : '',
        'description': descr,
        'title': this.titleEl ? this.titleEl.getAttribute('title') : '',

    };
    /*
    ===== OLD VERSION ===
    var res = {};
    res.img = this.imgEl.src;
    var authorComment = this._parseComment(this.commentEls[0]);
    res.timeAgo = authorComment.timeAgo;
    res.authorName = authorComment.authorName;
    res.comments = [];
    for (var i = 1; i < this.commentEls.length; ++i) {
        res.comments.push(this._parseComment(this.commentEls[i]));
    }
    if (this.sourceA) {
        res.sourceUrl = this.sourceA.href;
    }
    if (this.userBaseA) {
        res.pinnedBy = this.userBaseA.href;
    }
    return res;
    */
};


/*
 * Functions
 */

_P.startSearch = function(lastPinIds) {
    console.log('lastPinIds', lastPinIds);
    _P.lastPinIds = {};
    for (var i = 0; i < lastPinIds.length; i++) {
        var pinId = lastPinIds[i];
        _P.lastPinIds[pinId] = true;
    }
    _P.pagePins = new _P.PagePins();
    _P.pagePins.find();
};

_P.searchFinished = function() {
    return !_P.pagePins.findGoing;
};

_P.searchResultsAsJSON = function() {
    return JSON.stringify(_P.pagePins.getPins());
};


_P.singlePageData = function() {
    var single = new _P.SinglePinPage();
    return single.toJSON();
};

