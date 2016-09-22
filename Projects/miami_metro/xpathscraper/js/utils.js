_XPS.LOG_TO_CONSOLE = false;

_XPS.PXDIST_CLOSE_EACH_OTHER = 50;

_XPS.log = function() {
    if (!_XPS.LOG_TO_CONSOLE) {
        return;
    }
    console.log.apply(console, arguments);
};

_XPS.logElTexts = function(els) {
    for (var i = 0; i < els.length; ++i) {
        var el = els[i];
        var textContent = _XPS.directTextContent(el, 80);
        _XPS.log(el, textContent);
    }
};

_XPS.inArray = function(el, arr) {
    for (var i = 0; i < arr.length; ++i) {
        if (el === arr[i]) {
            return true;
        }
    }
    return false;
};

_XPS.values = function(obj) {
    var res = [];
    for (var k in obj) {
        res.push(obj[k]);
    }
    return res;
};

_XPS.objectFromItems = function(items) {
    res = {};
    for (var i = 0; i < items.length; ++i) {
        var item = items[i];
        res[item[0]] = item[1];
    }
    return res;
};

_XPS.euclideanDistance = function(p, q) {
    return Math.sqrt(Math.pow(p[0] - q[0], 2) + Math.pow(p[1] - q[1], 2));
};

_XPS.substringInArray = function(s, arr) {
    if (typeof(s) !== 'string') {
        return false;
    }
    if (s === '') {
        return false;
    }
    for (var k = 0; k < arr.length; ++k) {
        var word = arr[k];
        if (s && s.toLowerCase().indexOf(word) !== -1) {
            return true;
        }
    }
    return false;
};

_XPS.regExpEscape = function(s) {
    return s.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
};

_XPS.phraseInArray = function(s, arr) {
    if (typeof(s) !== 'string') {
        return false;
    }
    if (s === '') {
        return false;
    }

    var matcher = RegExp('\\b' + this.regExpEscape(s) + '\\b', 'i');
    for (var k = 0; k < arr.length; ++k) {
        var text = arr[k];
        if (matcher.test(text)) {
            return true;
        }
    }
    return false;
};

_XPS.wordInArray = function(s, arr) {
    if (typeof(s) !== 'string') {
        return false;
    }
    var sWords = _XPS.splitWords(s.toLowerCase());
    for (var i = 0; i < sWords.length; ++i) {
        var sw = sWords[i];
        for (var k = 0; k < arr.length; ++k) {
            var word = arr[k];
            if (sw === word) {
                return true;
            }
        }
    }
    return false;
};

_XPS.map = function(fun, args) {
    var res = [];
    for (var i = 0; i < args.length; ++i) {
        res.push(fun(args[i]));
    }
    return res;
};

_XPS.mapStr = function(funStr, args) {
    return _XPS.map(eval(funStr), args);
};

_XPS.filter = function(fun, args) {
    var res = [];
    for (var i = 0; i < args.length; ++i) {
        if (fun(args[i])) {
            res.push(args[i]);
        }
    }
    return res;
};

_XPS.filterStr = function(funStr, args) {
    return _XPS.filter(eval(funStr), args);
};

_XPS.any = function(fun, args) {
    for (var i = 0; i < args.length; ++i) {
        if (fun(args[i])) {
            return true;
        }
    }
    return false;
};

_XPS.all = function(fun, args) {
    for (var i = 0; i < args.length; ++i) {
        if (!fun(args[i])) {
            return false;
        }
    }
    return true;
};

_XPS.identity = function(arg) {
    return arg;
};

_XPS.fst = function(arg) {
    return arg[0];
};

_XPS.snd = function(arg) {
    return arg[1];
};

_XPS.max = function(args, key) {
    if (typeof(key) === 'undefined') {
        key = function(x) { return x; };
    }
    if (!args || !args.length) {
        return null;
    }
    var current = args[0];
    for (var i = 1; i < args.length; ++i) {
        var arg = args[i];
        if (key(arg) > key(current)) {
            current = arg;
        }
    }
    return current;
};

_XPS.flatten = function(arrayOfArrays) {
    var res = [];
    for (var i = 0; i < arrayOfArrays.length; ++i) {
        res = res.concat(arrayOfArrays[i]);
    }
    return res;
};

_XPS.sumArray = function(arr) {
    var res = 0;
    for (var i = 0; i < arr.length; ++i) {
        res += arr[i];
    }
    return res;
};

_XPS.avgArray = function(arr) {
    return _XPS.sumArray(arr) / arr.length;
};

_XPS.splitWords = function(s) {
    if (!s) {
        return [];
    }
    var words = s.split(/\W+/);
    var res = [];
    for (var i = 0; i < words.length; ++i) {
        var word = words[i];
        if (!word) {
            continue;
        }
        res.push(word.toLowerCase());
    }
    return res;
};

_XPS.representsNumber = function(s) {
    var sLower = s.toLowerCase();
    if ((sLower.startsWith('w') || sLower.startsWith('l')) && sLower.length > 1) {
        s = sLower.substr(1);
    };
    return !isNaN(s);
};
