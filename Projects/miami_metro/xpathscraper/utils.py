from __future__ import division

import time
import urlparse
import math
import datetime
import json
from collections import namedtuple
import re
import itertools
import os
import sys
import logging
import urllib
import copy
import pickle
import socket

import requests
import requests.exceptions
import lxml.html
import baker

from requests.packages.urllib3.exceptions import LocationParseError

from django.conf import settings
from django.core.validators import validate_email


log = logging.getLogger(__name__)

kickbox = None


def set_kickbox():
    import kickbox as kickbox_lib

    try:
        kickbox = kickbox_lib.Client(settings.KICKBOX_APIKEY).kickbox()
    except Exception:
        log.exception('Kickbox client connection problem.')

def post_to_blog_url(url):
    """
    fetch blog url from a given post url
    e.g., if we find 'http://chanellearetha.blogspot.sg/2015/09/the-positive-part-of-breaking-up.html' in
    an instagram profile, then we should use this function to find the blog url 'http://chanellearetha.blogspot.sg/'
    """
    import urlparse
    uu = url_without_path(url)
    parsed = urlparse.urlsplit(uu)
    return parsed.scheme + "://" + parsed.netloc

def urls_equal(url1, url2):
    '''Compare urls ignoring protocol
    '''
    if url1 is None and url2 is None:
        return True
    if url1 is None or url2 is None:
        return False
    p1 = urlparse.urlsplit(url1)
    p2 = urlparse.urlsplit(url2)
    return (p1.netloc, p1.path, p1.query) == (p2.netloc, p2.path, p2.query)

def url_path_endswith(url, exts):
    path = urlparse.urlparse(url).path
    return path.lower().endswith(exts)

def url_without_path(url):
    if not url.startswith('http'):
        url = 'http://' + url
    parsed = urlparse.urlsplit(url)
    cleaned = parsed._replace(path='', query='', fragment='')
    return urlparse.urlunsplit(cleaned)

def urlpath_join(url, path):
    return url.rstrip('/') + '/' + path.lstrip('/')

def url_contains_path(url):
    if not url.startswith('http'):
        url = 'http://' + url
    parsed = urlparse.urlsplit(url)
    return bool(parsed.path.rstrip('/'))

def url_is_valid(url):
    """Performs basic validity checks for an http/https url.
    """
    if not url:
        return False
    if not url.lower().startswith('http'):
        return False
    if not '.' in url:
        return False
    return True

def email_is_valid(email):
    """Performs basic vailidity checks for an email.
    """
    if not email or not email.strip():
        return False
    if '@' not in email or '.' not in email:
        return False
    if email.endswith('.'):
        return False
    try:
        validate_email(email)
        return True
    except Exception:
        return False


class KickboxCache(object):

    def __init__(self, filename, data=None, capacity=5000):
        self._data = data
        self._capacity = capacity
        self._filename = filename
        self._load()
        self._count = 0

    def has_email(self, email):
        return bool(email in self._data.keys())

    def save_email(self, email, response):
        self._data[email] = response
        self._count += 1
        if self._count >= self._capacity:
            self._save()

    def _load(self):
        if not self._filename:
            return
        with open(self._filename, 'rb') as fp:
            self._data = json.load(fp)

    def _save(self):
        self._count = 0
        with open(self._filename, 'wb') as fp:
            json.dump(self._data, fp)

    def save(self):
        self._save()


kickbox_cache = KickboxCache(settings.KICKBOX_CACHE_FILENAME, capacity=500)

def email_kickbox_check(email):
    set_kickbox()
    if kickbox_cache.has_email(email):
        return
    response = kickbox.verify(email)
    kickbox_cache.save_email(email, response.body)

def email_is_accepted(email):
    set_kickbox()
    """
    Performs check using Kickbox API
    """
    try:
        try:
            return kickbox_cache[email]
        except Exception:
            pass
        response = kickbox.verify(email)
        if response.body['result'] == 'deliverable':
            kickbox_cache[email] = True
            return True
        kickbox_cache[email] = False
        return False
    except Exception:
        log.exception('Exception during Kickbox check')
    return False

def remove_prefix(astr, prefix, case_sensitive=True):
    if case_sensitive:
        checked_str = astr
    else:
        checked_str = astr.lower()
    if checked_str.startswith(prefix):
        return astr[len(prefix):]
    return astr

def remove_postfix(astr, prefix, case_sensitive=True):
    if case_sensitive:
        checked_str = astr
    else:
        checked_str = astr.lower()
    if checked_str.endswith(prefix):
        return astr[:-len(prefix)]
    return astr

def parse_range(astr):
    result = set()
    for part in astr.split(','):
        x = part.split('-')
        result.update(range(int(x[0]), int(x[-1]) + 1))
    return sorted(result)

def euclidean_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def write_to_file(filename, contents, format='raw'):
    with open(filename, 'w') as f:
        if format == 'raw':
            if isinstance(contents, unicode):
                contents = contents.encode('utf-8')
        elif format == 'pickle':
            contents = pickle.dumps(contents)
        else:
            assert False, 'Unknown format %r' % format
        f.write(contents)


def domain_from_url(url, preserve_www=False):
    if not url.startswith('http'):
        if url.startswith('//'):
            # support broken URL's like //plus.google.com/+blah
            url = 'http:' + url
        else:
            url = 'http://' + url

    netloc = urlparse.urlparse(url).netloc
    if not preserve_www:
        netloc = remove_prefix(netloc, 'www.')
    return netloc.lower()


def strip_last_domain_component(domain):
    if not domain:
        return None
    if '.' not in domain:
        return domain
    if domain.lower().endswith('.co.uk'):
        return domain.lower()[:-len('.co.uk')]
    if re.match('.*\.com\...$', domain.lower()):
        return domain.lower()[:-len('.com.ar')]
    return domain[:domain.rfind('.')]

def resolve_http_redirect(url, timeout=20):
    r = requests.get(url, timeout=timeout, verify=False)
    return r.url

def do_with_query_params(url, qs_fun):
    """qs_fun is a function that receives a dictionary of
    parsed query params and modified them
    """
    parsed = urlparse.urlsplit(url)
    qs = urlparse.parse_qs(parsed.query)
    qs_fun(qs)
    new_query = urllib.urlencode(qs, True)
    parsed = parsed._replace(query=new_query)
    res = urlparse.urlunsplit(parsed)
    return res

def set_query_param(url, param, value):
    def change(qs):
        qs[param] = value
    return do_with_query_params(url, change)

def del_query_param(url, param):
    def change(qs):
        del qs[param]
    return do_with_query_params(url, change)

def remove_query_params(url):
    def change(qs):
        qs.clear()
    return do_with_query_params(url, change)

def remove_fragment(url):
    parsed = urlparse.urlsplit(url)
    parsed = parsed._replace(fragment='')
    return urlparse.urlunsplit(parsed)


class URLResolver(object):
    """Uses requests.Session to use keep-alive
    """

    def __init__(self):
        self.s = requests.Session()

    def resolve(self, url):
        try:
            r = self.s.get(url, timeout=5)
            return r.url
        except:
            log.exception('While resolve')
            return url


def can_get_url(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout, headers=browser_headers(), verify=False)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        return False
    return True


MAX_FETCH_IFRAMES_CALLS = 10
def fetch_iframes(url, _visited=None, _calls=0):
    if _calls > MAX_FETCH_IFRAMES_CALLS:
        return
    if _visited is None:
        _visited = set()
    _visited.add(url)
    try:
        r = requests.get(url, timeout=10, verify=False)
    except requests.exceptions.RequestException:
        return
    except LocationParseError:
        return
    if r.status_code != 200:
        return
    yield r.content.lower()
    try:
        tree = lxml.html.fromstring(r.content)
    except:
        log.exception('While lxml.html.fromstring')
        return
    frames = tree.xpath('//iframe') + tree.xpath('//frame')
    for el in frames:
        src = el.attrib.get('src')
        if not src or src in _visited:
            continue
        for res in fetch_iframes(src, _visited, _calls + 1):
            yield res

def strip_url_of_default_info(url, strip_domain=True):
    '''
    Useful to search for other objects that have almost similar urls
    '''
    if not url:
        return url
    domain = domain_from_url(url) if strip_domain else ''
    #print "got domain %s " % domain
    result = url.lstrip('https').lstrip('http').lstrip(':').lstrip('/').lstrip('www.').lstrip(domain).rstrip('#').rstrip('/').lstrip('/')
    return result.strip()

def flatten(lst):
    return [e for l in lst for e in l]

def unique_sameorder(seq, key=lambda x: x):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if key(x) not in seen and not seen_add(key(x))]

def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def chunk_ranges(l, n):
    for i in xrange(0, len(l), n):
        yield (i, i+n+1)

def pairs(lst):
    for i in xrange(len(lst)-1):
        yield (lst[i], lst[i+1])

def triplets(lst):
    for i in xrange(len(lst)-2):
        yield (lst[i], lst[i+1], lst[i+2])

# http://stackoverflow.com/a/6822773
def window(seq, n):
    "Returns a sliding window (of width n) over data from the iterable"
    "   s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ...                   "
    it = iter(seq)
    result = tuple(itertools.islice(it, n))
    if len(result) == n:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result

def concat_list_dicts(ds):
    """ds is a list of dictionaries with lists as values.
    Result is a dictionary with all keys from ds and results
    being concatenated lists from all dictionaries for each key.
    """
    keys = {k for d in ds for k in d}
    res = {}
    for k in keys:
        res[k] = flatten(d.get(k, []) for d in ds)
    return res

def nestedget(d, *keys):
    for k in keys:
        if d is None or not isinstance(d, (dict, list, tuple)):
            return None
        try:
            d = d[k]
        except:
            d = None
    return d

def firstnested(d, paths):
    """Each path is a list of keys to nested dictionaries ``d``.
    The result is a first nonempty string result successfully computed
    using :func:`nestedget`.
    """
    for path in paths:
        c = nestedget(d, *path)
        if c and isinstance(c, basestring):
            return c
    return None

# http://stackoverflow.com/a/8714242
def make_hashable(o):
    if isinstance(o, (set, tuple, list)):
        return tuple(make_hashable(e) for e in o)
    if not isinstance(o, dict):
        return o
    new_o = copy.deepcopy(o)
    for k, v in new_o.items():
        new_o[k] = make_hashable(v)
    return frozenset(new_o.items())

def limit_lens(o, limit=10):
    if isinstance(o, (set, tuple, list)):
        return o[:limit]
    if isinstance(o, dict):
        for k, v in o.items():
            o[k] = limit_lens(v, limit)
        return o
    return o

def env_flag(var, default='0'):
    val = os.environ.get(var, default)
    return bool(int(val))

def parse_rfc3339_datetime(s):
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%f')

def to_iso3339_string(d, utcchar=True):
    assert isinstance(d, datetime.datetime)
    res = d.isoformat('T')
    if utcchar:
        res += 'Z'
    return res

def from_struct_to_dt(s):
    return datetime.datetime.fromtimestamp(time.mktime(s))

def avg(*args):
    if not args:
        return None
    return sum(args) / float(len(args))

def absolute_values_to_relative_ordering(objects_vals, max_val=100.0):
    """Converts (object, numeric_val) list to (object, ordering_num) list where
    ordering_num is an ordered position of an object in the list, rescaled to
    respect max_val
    """
    objects_vals = sorted(objects_vals, key=lambda (o, val): val)
    step = max_val / float(len(objects_vals) - 1)
    res = []
    for i, (o, val) in enumerate(objects_vals):
        res.append((o, step * i))
    return res

def add_www(url):
    parts = urlparse.urlsplit(url)
    if not parts.netloc.startswith('www.'):
        parts = parts._replace(netloc='www.' + parts.netloc)
        return urlparse.urlunsplit(parts)
    return None

def remove_www(url):
    parts = urlparse.urlsplit(url)
    if not parts.netloc.startswith('www.'):
        return None
    parts = parts._replace(netloc=remove_prefix(parts.netloc, 'www.', case_sensitive=False))
    return urlparse.urlunsplit(parts)

def remove_protocol(url):
    for prefix in ('https://', 'http://', 'file://'):
        url = remove_prefix(url, prefix, False)
    return url

def pickle_to_file(filename, obj):
    with open(filename, 'w') as f:
        pickle.dump(obj, f)

IP_ADDRESS = None


def get_ip_address():
    # Cache IP address. No need to query network interfaces every time.
    global IP_ADDRESS

    if not IP_ADDRESS:
        import netifaces

        try:
            IP_ADDRESS = netifaces.ifaddresses('eth0')[netifaces.AF_INET][0]['addr']
        except:
            IP_ADDRESS = socket.gethostbyname(socket.gethostname())

    return IP_ADDRESS

def browser_headers():
    return {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_1) AppleWebKit/534.48.3 (KHTML, like Gecko) Version/5.1 Safari/534.48.3'}

def run_tournament(lst, match_fun):
    """Run a tournament: players are in the `lst` list and `match_fun(p1, p2)` returns
    a winning player.
    """
    while True:
        assert lst
        if len(lst) == 1:
            log.debug('TOURNAMENT WINNER: %s', lst[0])
            return lst[0]
        pairs = chunks(lst, 2)
        winners = []
        for pair in pairs:
            assert pair
            if len(pair) == 1:
                log.debug('Lucky element promoted without playing: %s', pair[0])
                # Insert the lucky element at the beginning, to be sure
                # he will play a match
                winners.insert(0, pair[0])
            else:
                log.debug('Match between\nFirst:  %s\nSecond: %s', pair[0], pair[1])
                winner = match_fun(pair[0], pair[1])
                if winner is pair[0]:
                    winner_name = 'first'
                elif winner is pair[1]:
                    winner_name = 'second'
                else:
                    assert False, 'Winner is neither first nor the second player'
                log.debug('Won by %s', winner_name)
                winners.append(winner)
        lst = winners

def run_league(lst, match_fun):
    """Run a league: players are in the `lst` list and `match_fun(p1, p2)` returns
    a pair of points aquired by the first and the second player.
    Returns a final table: a list of pairs (player, score) sorted by score.
    """
    match_pairs = itertools.combinations(lst, 2)
    # maps player index to points
    score_table = { player: 0 for player in lst }
    for (p1, p2) in match_pairs:
        log.debug('Match between\nFirst:  %s\nSecond: %s', p1, p2)
        points1, points2 = match_fun(p1, p2)
        log.debug('Result: %s', (points1, points2))
        score_table[p1] += points1
        score_table[p2] += points2
    table_sorted = sorted(score_table.items(), key=lambda (player, score): score, reverse=True)

    log.debug('Final table')
    for i, (player, score) in enumerate(table_sorted):
        log.debug('%02d. [%d points] %s', (i + 1), score, player)

    return table_sorted


# Parsing XPaths

XPathPathElement = namedtuple('XPathPathElement', ['orig_string', 'tag_name', 'spec'])

def parse_xpath(xpath):
    res = []
    path_components = re.split(r'/+', xpath)
    path_components = [pc for pc in path_components if pc]
    for pc in path_components:
        spec_res = re.search(r'\[(.*)\]', pc)
        if spec_res:
            tag_name = pc.split('[', 1)[0]
            spec = spec_res.group(1)
            res.append(XPathPathElement(orig_string=pc, tag_name=tag_name, spec=spec))
        else:
            res.append(XPathPathElement(orig_string=pc, tag_name=pc, spec=pc))
    return res

def reduce_xpaths_to_capturing_xpath(xpaths):
    for xpath in xpaths:
        assert xpath.startswith('//')
    paths = [parse_xpath(xpath) for xpath in xpaths]
    if len(set(len(p) for p in paths)) != 1:
        return None
    values_by_path_index = [[p[i] for p in paths] for i in range(len(paths[0]))]
    res = []
    for values in values_by_path_index:
        if len(set(v.orig_string for v in values)) == 1:
            res.append(values[0].orig_string)
            continue
        if len(set(v.tag_name for v in values)) != 1:
            return None
        if not all(v.spec and v.spec.isdigit() for v in values):
            return None
        if not sorted(int(v.spec) for v in values) == range(1, len(values) + 1):
            return None
        res.append(values[0].tag_name)
    return '//' + '/'.join(res)

def find_all(a_str, sub):
    start = 0
    res = []
    while True:
        start = a_str.find(sub, start)
        if start == -1:
            return res
        res.append(start)
        start += len(sub)

def find_all_non_overlapping(a_str, sub_list):
    start = 0
    res = []
    used_idxs = set()
    for sub in sub_list:
        while True:
            start = a_str.find(sub, start)
            if start == -1:
                break
            idxs = set(range(start, start + len(sub)))
            if used_idxs.isdisjoint(idxs):
                res.append(start)
                used_idxs.update(idxs)
            start += len(sub)
    return res

def parse_logfile(filename):
    with open(filename) as f:
        lines = f.readlines()
    res = []
    for line in lines:
        try:
            if not line.strip():
                continue
            words = line.split()
            if len(words) < 4:
                continue
            d = datetime.datetime.strptime(words[0] + ' ' + words[1].split(',')[0], '%Y-%m-%d %H:%M:%S')
            res.append((d, ' '.join(words[4:])))
        except ValueError:
            pass
    return res

def parse_percents(s):
    s = s.replace('%', '')
    return float(s) / 100.0

class LocalProxy(object):
    """A proxy object taken from werkzeug.local
    """

    __slots__ = ('__local', '__dict__', '__name__')

    def __init__(self, local, name=None):
        object.__setattr__(self, '_LocalProxy__local', local)
        object.__setattr__(self, '__name__', name)

    def _get_current_object(self):
        """Return the current object.  This is useful if you want the real
        object behind the proxy at a time for performance reasons or because
        you want to pass the object into a different context.
        """
        if not hasattr(self.__local, '__release_local__'):
            return self.__local()
        try:
            return getattr(self.__local, self.__name__)
        except AttributeError:
            raise RuntimeError('no object bound to %s' % self.__name__)

    @property
    def __dict__(self):
        try:
            return self._get_current_object().__dict__
        except RuntimeError:
            raise AttributeError('__dict__')

    def __repr__(self):
        try:
            obj = self._get_current_object()
        except RuntimeError:
            return '<%s unbound>' % self.__class__.__name__
        return repr(obj)

    def __bool__(self):
        try:
            return bool(self._get_current_object())
        except RuntimeError:
            return False

    def __unicode__(self):
        try:
            return unicode(self._get_current_object())
        except RuntimeError:
            return repr(self)

    def __dir__(self):
        try:
            return dir(self._get_current_object())
        except RuntimeError:
            return []

    def __getattr__(self, name):
        if name == '__members__':
            return dir(self._get_current_object())
        return getattr(self._get_current_object(), name)

    def __setitem__(self, key, value):
        self._get_current_object()[key] = value

    def __delitem__(self, key):
        del self._get_current_object()[key]

    __getslice__ = lambda x, i, j: x._get_current_object()[i:j]

    def __setslice__(self, i, j, seq):
        self._get_current_object()[i:j] = seq

    def __delslice__(self, i, j):
        del self._get_current_object()[i:j]

    __setattr__ = lambda x, n, v: setattr(x._get_current_object(), n, v)
    __delattr__ = lambda x, n: delattr(x._get_current_object(), n)
    __str__ = lambda x: str(x._get_current_object())
    __lt__ = lambda x, o: x._get_current_object() < o
    __le__ = lambda x, o: x._get_current_object() <= o
    __eq__ = lambda x, o: x._get_current_object() == o
    __ne__ = lambda x, o: x._get_current_object() != o
    __gt__ = lambda x, o: x._get_current_object() > o
    __ge__ = lambda x, o: x._get_current_object() >= o
    __cmp__ = lambda x, o: cmp(x._get_current_object(), o)
    __hash__ = lambda x: hash(x._get_current_object())
    __call__ = lambda x, *a, **kw: x._get_current_object()(*a, **kw)
    __len__ = lambda x: len(x._get_current_object())
    __getitem__ = lambda x, i: x._get_current_object()[i]
    __iter__ = lambda x: iter(x._get_current_object())
    __contains__ = lambda x, i: i in x._get_current_object()
    __add__ = lambda x, o: x._get_current_object() + o
    __sub__ = lambda x, o: x._get_current_object() - o
    __mul__ = lambda x, o: x._get_current_object() * o
    __floordiv__ = lambda x, o: x._get_current_object() // o
    __mod__ = lambda x, o: x._get_current_object() % o
    __divmod__ = lambda x, o: x._get_current_object().__divmod__(o)
    __pow__ = lambda x, o: x._get_current_object() ** o
    __lshift__ = lambda x, o: x._get_current_object() << o
    __rshift__ = lambda x, o: x._get_current_object() >> o
    __and__ = lambda x, o: x._get_current_object() & o
    __xor__ = lambda x, o: x._get_current_object() ^ o
    __or__ = lambda x, o: x._get_current_object() | o
    __div__ = lambda x, o: x._get_current_object().__div__(o)
    __truediv__ = lambda x, o: x._get_current_object().__truediv__(o)
    __neg__ = lambda x: -(x._get_current_object())
    __pos__ = lambda x: +(x._get_current_object())
    __abs__ = lambda x: abs(x._get_current_object())
    __invert__ = lambda x: ~(x._get_current_object())
    __complex__ = lambda x: complex(x._get_current_object())
    __int__ = lambda x: int(x._get_current_object())
    __long__ = lambda x: long(x._get_current_object())
    __float__ = lambda x: float(x._get_current_object())
    __oct__ = lambda x: oct(x._get_current_object())
    __hex__ = lambda x: hex(x._get_current_object())
    __index__ = lambda x: x._get_current_object().__index__()
    __coerce__ = lambda x, o: x._get_current_object().__coerce__(x, o)
    __enter__ = lambda x: x._get_current_object().__enter__()
    __exit__ = lambda x, *a, **kw: x._get_current_object().__exit__(*a, **kw)
    __radd__ = lambda x, o: o + x._get_current_object()
    __rsub__ = lambda x, o: o - x._get_current_object()
    __rmul__ = lambda x, o: o * x._get_current_object()
    __rdiv__ = lambda x, o: o / x._get_current_object()
    __rtruediv__ = lambda x, o: x._get_current_object().__rtruediv__(o)
    __rfloordiv__ = lambda x, o: o // x._get_current_object()
    __rmod__ = lambda x, o: o % x._get_current_object()
    __rdivmod__ = lambda x, o: x._get_current_object().__rdivmod__(o)


# http://code.activestate.com/recipes/578231-probably-the-fastest-memoization-decorator-in-the-/
def memoize(f):
    """ Memoization decorator for a function taking one or more arguments. """
    class memodict(dict):
        def __getitem__(self, *key):
            return dict.__getitem__(self, key)

        def __missing__(self, key):
            ret = self[key] = f(*key)
            return ret
    return memodict().__getitem__


def log_to_stderr(logger_names=[''], level=logging.DEBUG, thread_id=False):
    if thread_id:
        formatter = logging.Formatter('%(asctime)s THR:%(thread)d %(name)s %(levelname)s %(message)s')
    else:
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    stderr_hdlr = logging.StreamHandler(sys.stderr)
    stderr_hdlr.setLevel(logging.DEBUG)
    stderr_hdlr.setFormatter(formatter)
    logging.getLogger('django').setLevel(logging.INFO)
    logging.getLogger('selenium').setLevel(logging.INFO)
    for name in logger_names:
        logging.getLogger(name).addHandler(stderr_hdlr)
        logging.getLogger(name).setLevel(level)

    # blacklisted
    logging.getLogger('iso8601').setLevel(logging.CRITICAL)

def in_ipython():
    try:
        __IPYTHON__
    except NameError:
        return False
    else:
        return True

def error_msg_from_exception():
    typ, obj, tb = sys.exc_info()
    if typ is None:
        return None
    return u'%r %r' % (typ, obj)

# http://stackoverflow.com/a/2894073
def longest_substr(data):
    substr = ''
    if len(data) > 1 and len(data[0]) > 0:
        for i in range(len(data[0])):
            for j in range(len(data[0])-i+1):
                if j > len(substr) and is_substr(data[0][i:i+j], data):
                    substr = data[0][i:i+j]
    return substr
def is_substr(find, data):
    if len(data) < 1 and len(find) < 1:
        return False
    for i in range(len(data)):
        if find not in data[i]:
            return False
    return True

def add_to_comma_separated(orig_str, new_vals):
    if orig_str:
        new_vals = orig_str.split(', ') + new_vals
    new_vals = unique_sameorder(new_vals)
    return ', '.join(new_vals)

def datetime_range_from_date(date):
    return (datetime.datetime.combine(date, datetime.time.min),
             datetime.datetime.combine(date, datetime.time.max))

def timedelta_to_days(td):
    return float(td.total_seconds()) / 86400.0

def import_from_name(import_name):
    import_name = str(import_name)
    if ':' in import_name:
        module, obj = import_name.split(':', 1)
    elif '.' in import_name:
        module, obj = import_name.rsplit('.', 1)
    else:
        return __import__(import_name)
    if isinstance(obj, unicode):
        obj = obj.encode('utf-8')
    try:
        return getattr(__import__(module, None, None, [obj]), obj)
    except (ImportError, AttributeError):
        modname = module + '.' + obj
        __import__(modname)
        return sys.modules[modname]

def force_db_indexes_usage():
    from debra import db_util
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("set enable_seqscan = false")

def get_first_or_instantiate(manager, **kwargs):
    existing = list(manager.filter(**kwargs)[:1])
    if existing:
        return existing[0]
    return manager.model(**kwargs)

def copy_model_attr_values(source, dest):
    for field in source._meta.fields:
        if field.name == source._meta.pk:
            continue
        source_val = getattr(source, field.name)
        dest_val = getattr(desc, field.name, None)
        if source_val != dest_val:
            pass

class TaskInfoWriter(object):
    def __init__(self, filename):
        self.f = open(filename, 'a')
    def add(self, queue, task_name, arg):
        self.f.write('%s %s %s\n' % (queue, task_name, arg))
        self.f.flush()
    def close(self):
        self.f.close()

def distinct_list(seq):
    """
    Fast function to remove duplicates from list preserving order:
    http://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-in-python-whilst-preserving-order
    :param seq:
    :return:
    """
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]

@baker.command
def submit_tasks_from_task_info_file(filename):
    with open(filename) as f:
        for i, line in enumerate(f):
            queue, task_name, arg = line.split()
            arg = int(arg)
            task = import_from_name(task_name)
            task.apply_async(args=[arg], queue=queue)
            if i % 1000 == 0:
                log.info('%d tasks submitted', i)
        log.info('%d total tasks submitted', i)

if __name__ == '__main__':
    baker.run()

