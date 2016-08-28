"""Functions for extracting urls from text/HTML.
"""

import re
import urlparse
from BeautifulSoup import BeautifulSoup
import lxml.html
from xpathscraper import utils


_url_re = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$_@.&+~#!?=\[\-\]\/]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
_url_no_protocol_re = re.compile(r'(?:[a-zA-Z]|[0-9]|[$_@.&+~#!?=\[\-\]\/]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
_IMG_EXTS = ('.png', '.gif', '.svg', '.jpg', '.jpeg')


def re_find_urls(s):
    """Find urls using a regexp expression"""
    urls = _url_re.findall(s)
    urls = [u for u in urls if '.' in u]
    return urls


def _netloc_for_url_candidate(candidate):
    if not candidate.startswith('http'):
        candidate = 'https://%s' % candidate
    try:
        return urlparse.urlsplit(candidate).netloc
    except ValueError:
        return None


def find_all_urls(s, exclude_imgs=True):
    """Looks also for urls without a protocol (http/https).
    """
    from platformdatafetcher import platformutils

    urls = []
    v_urls = set()

    for u in _url_re.findall(s):
        if exclude_imgs and u.endswith(_IMG_EXTS):
            continue
        if platformutils.url_to_handle(u) not in v_urls:
            v_urls.add(platformutils.url_to_handle(u))
            urls.append(u)

    for candidate in _url_no_protocol_re.findall(s):
        netloc = _netloc_for_url_candidate(candidate)
        if netloc is None:
            continue
        if exclude_imgs and candidate.endswith(_IMG_EXTS):
            continue
        # Skip texts like: posted..It or ...ok
        if '..' in candidate or '(' in candidate or '@' in candidate:
            continue
        if '.' not in netloc:
            continue
        if candidate.startswith('//'):
            continue
        root_domain = netloc.split('.')[-1]
        if not 2 <= len(root_domain) <= 4:
            continue
        if any(c.isdigit() for c in root_domain):
            continue
        # Skip texts like posted.Are - look at letter case
        if root_domain[0].isupper() and root_domain[1:].islower():
            continue

        if platformutils.url_to_handle(candidate) in v_urls:
            continue
        v_urls.add(platformutils.url_to_handle(candidate))
        urls.append('http://' + candidate)
    return urls


def find_links_with_texts(content):
    tree = lxml.html.fromstring(content)
    res = []

    def process_els(els, attr):
        for el in els:
            if attr not in el.attrib:
                continue
            if el.attrib[attr].startswith('javascript'):
                continue
            text = (el.text or '').strip()[:100]
            res.append((el.attrib[attr], text))

    process_els(tree.xpath('//a'), 'href')
    process_els(tree.xpath('//area'), 'href')
    process_els(tree.xpath('//iframe'), 'src')

    return res


def find_important_urls(content, exclude_domains_from_urls=[], exclude_root_links=True,
                        exclude_imgs=True, include_only_imgs=False):
    """Finds all urls in `content`
    - excluding any domains present in urls in `exclude_domains_from_urls` list.
    - if `exclude_root_links` is `True`, exclude url's linking to root domain's path.
    - if `exclude_imgs` is `True`, exclude url's linking to images
    - if `include_only_imgs` is `True`, just pick images
    """
    if not content:
        return set()

    exclude_domains = []
    for e_url in exclude_domains_from_urls:
        if not e_url:
            continue
        if "'" in e_url:
            loc = e_url.rindex("'")
            e_url = e_url[:loc]
        if '"' in e_url:
            loc = e_url.rindex('"')
            e_url = e_url[:loc]
        netloc = urlparse.urlsplit(e_url).netloc
        exclude_domains.append(netloc)
        if not netloc.startswith('www.'):
            exclude_domains.append('www.' + netloc)
    soup = BeautifulSoup(content)
    anchor_elems = soup.findAll('a')
    urls = [a.get('href') for a in anchor_elems]
    if include_only_imgs:
        anchor_elems = soup.findAll('img')
        urls = [a.get('src') for a in anchor_elems]
        # if no url is found, use the regular expression (this is important for Instagram urls or twitter where
        # ) where the url is not in an anchor tag
        if len(urls) == 0:
            urls = _url_re.findall(content)
    res = set()
    # print "exclude domains: %s " % exclude_domains
    for u in urls:
        if not u:
            continue
        # print u
        try:
            parsed = urlparse.urlsplit(u)
            if any(ed in parsed.netloc for ed in exclude_domains):
                continue
            if exclude_root_links and ((not parsed.path) or (parsed.path == '/')):
                continue
            if exclude_imgs and (parsed.path or '').lower().endswith(_IMG_EXTS):
                continue
            if include_only_imgs:
                if (parsed.path or '').lower().endswith(_IMG_EXTS):
                    res.add(u)
                continue

            # Filter out mailto: links and other non-web stuff.
            if parsed.scheme in ('', 'http', 'https'):
                res.add(u)
        except:
            pass
    return res


def filter_urls(urls, exclude_domains_from_urls):
    domains = set()
    for eurl in exclude_domains_from_urls:
        if not eurl.startswith('http'):
            eurl = 'http://%s' % eurl
        domains.add(utils.domain_from_url(eurl))
        domains.add('www.%s' % utils.domain_from_url(eurl))
    res = []
    for url in urls:
        if utils.domain_from_url(url) in domains:
            continue
        res.append(url)
    return res
