import logging
import time
import baker

from selenium.common.exceptions import WebDriverException
import lxml
import lxml.html
import requests
import bs4
from BeautifulSoup import BeautifulSoup
from django.conf import settings

from xpathscraper import utils


log = logging.getLogger('xpathscraper.xutils')


def wait_for_condition(condition_fun, timeout=10, poll_every=0.5, name=None):
    if name is None:
        name = condition_fun.__name__
    start = time.time()
    while True:
        time.sleep(poll_every)
        elapsed = (time.time() - start)
        if condition_fun():
            log.info('Condition <%s> met after %.3f', name, elapsed)
            return True
        else:
            log.info('Condition <%s> not met after %.3f, continuing polling', name, elapsed)
        if elapsed - start > timeout:
            log.info('Condition <%s> NOT met after timeout (%.3f elapsed)', name, elapsed)
            return False


def _state_complete(xbrowser):
    return xbrowser.driver.execute_script('return document.readyState') == 'complete'


def wait_for_complete_state(xbrowser, timeout=10, poll_every=0.2):
    return wait_for_condition(lambda: _state_complete(xbrowser),
                              timeout, poll_every, 'complete state')


def wait_for_complete_state_or_url_change(xbrowser, timeout=10, poll_every=0.2):
    orig_url = xbrowser.driver.current_url

    def url_changed():
        return xbrowser.driver.current_url != orig_url
    return wait_for_condition(
        lambda: _state_complete(xbrowser) or url_changed(),
        timeout,
        poll_every,
        'complete state or url change')


def find_common_links(xbrowser, urls):
    domains = [utils.domain_from_url(u) for u in urls]
    assert len(set(domains)) == 1, 'urls are not for the same domain: %s' % domains
    domain = domains[0]
    links_by_url = {}
    for u in urls:
        xbrowser.load_url(u)
        links_by_url[u] = xbrowser.execute_jsfun('_XPS.visibleLinksToDomains', [domain], True)
        links_by_url[u] = [link.strip() for link in links_by_url[u]]
    common_links = set.intersection(*[set(v) for v in links_by_url.values()])
    return common_links


def crawl_indepth(xbrowser, url, do_when_loaded=None, depth=1, max_per_page=100, _visited=None):
    if _visited is None:
        _visited = set()
    log.info('Will try to load url %s, visited: %s', url, len(_visited))
    if url in _visited:
        log.info('url %s already visited', url)
        return
    domain = utils.domain_from_url(url)
    try:
        _visited.add(url)
        xbrowser.load_url(url)
        if do_when_loaded is not None:
            do_when_loaded(url)
        links = xbrowser.execute_jsfun('_XPS.visibleLinksToDomains', [domain], True)
    except WebDriverException:
        log.exception('While computing links for url %r', url)
        return
    links = utils.unique_sameorder(links)
    links = [l for l in links if l not in _visited]
    if max_per_page is not None:
        links = links[:max_per_page]
    log.info('Links from depth %s url %s: (%s) %r', depth, url, len(links), links)
    if depth > 0:
        for i, link in enumerate(links):
            log.info('Loading link %s/%s: %s', i + 1, len(links), link)
            crawl_indepth(xbrowser, link, do_when_loaded, depth - 1, max_per_page, _visited)
    else:
        log.info('Depth is 0, not going deeper')


def find_navigation_links_clusters(xbrowser):
    res = []
    res += xbrowser.execute_jsfun('_XPS.horizontalLinksClusters')
    res += xbrowser.execute_jsfun('_XPS.verticalLeftLinksClusters')
    res += xbrowser.execute_jsfun('_XPS.verticalRightLinksClusters')
    res = [cluster for cluster in res if len(cluster) >= 3]
    return res


def find_iframe_src(html, src_fragment):
    tree = lxml.html.fromstring(html)
    iframes = tree.xpath('//iframe')
    for iframe in iframes:
        print iframe.attrib.get('src'), 'ok'
        if src_fragment in iframe.attrib.get('src', ''):
            return iframe.attrib['src']
    return None


def fetch_title(url=None, content=None):
    """This function must be given either an url, or downloaded content
    """
    if content is None:
        assert url is not None
        r = requests.get(url, timeout=5, headers=utils.browser_headers(), verify=False)
        content = r.text
    tree = lxml.html.fromstring(content)
    title_els = tree.xpath('//title')
    if not title_els:
        return None
    title = (title_els[0].text or '').strip()
    if not title:
        return None
    return title


def fetch_title_simple(url):
    """This function uses a simpler algorithm in BeatifulSoup
    to avoid parsing errors in lxml.
    """
    r = requests.get(url, timeout=20, headers=utils.browser_headers(), verify=False)
    soup = BeautifulSoup(r.text)
    return soup.title.string


def contains_blog_metatags(content, tree=None):
    """
    Returns blog platform if it can be detected from content.

    You can pass a pre-parsed lxml.html tree as an optimization to avoid reparsing.
    """
    if tree is None:
        tree = lxml.html.fromstring(content)

    for tag in tree.xpath('//meta'):
        meta_name = tag.attrib.get('name')
        print("Got name: %r" % meta_name)
        meta_content = tag.attrib.get('content')
        print("Got content: %r" % meta_content)

        if meta_content and 'blog' in meta_content.lower():
            # here we check if blogger is contained somewhere in the meta tags
            # doesn't matter in what tag
            return 'Blog'

        if not meta_name or not meta_content:
            continue
        meta_content = meta_content.lower()

        if meta_name == 'generator':
            if 'blogger' in meta_content:
                return 'Blogspot'
            if 'wordpress' in meta_content:
                return 'Wordpress'
        elif meta_name == 'twitter:site':  # Twitter meta tags
            if 'tumblr' in meta_content:
                return 'Tumblr'
        elif 'twitter:app:name' in meta_name:
            if 'tumblr' in meta_content:
                return 'Tumblr'
        elif 'og:type' in meta_name:  # FB OpenGraph meta tags
            if 'tumblr' in meta_content:
                return 'Tumblr'
        elif meta_name == 'al:ios:app_name':  # App Links meta tags
            if 'tumblr' in meta_content:
                return 'Tumblr'

    return None


def fetch_url(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout, verify=False)
        return r.text
    except:
        log.exception('While fetch_url')
        return None


def is_html(content):
    content = content.lower()
    return '<div' in content or 'href=' in content or '<p>' in content


def strip_html_tags(content):
    b = bs4.BeautifulSoup(content)
    return b.get_text()


def get_about_page_links(xbrowser):
    links = xbrowser.execute_jsfun_safe([], '_XPS.visibleLinksWithTexts',
                                        ['contact', 'about', 'social', 'media', 'follow'], 40)
    links = [l for l in links if utils.domain_from_url(l) ==
             utils.domain_from_url(xbrowser.driver.current_url)]
    return utils.unique_sameorder(links)


@baker.command
def print_navigation_links(url):
    from xpathscraper import xbrowser as xbrowsermod

    with xbrowsermod.XBrowser(headless_display=False, disable_cleanup=True) as xb:
        xb.load_url(url)
        clusters = find_navigation_links_clusters(xb)
        for cluster in clusters:
            print '\n'
            for el in cluster:
                print el.get_attribute('href')


def resolve_redirect_using_xbrowser(url, to_sleep=5):
    from xpathscraper import xbrowser as xbrowsermod
    try:
        with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
            xb.load_url(url)
            time.sleep(to_sleep)
            return xb.driver.current_url
    except:
        log.exception('While resolve_redirect_using_xbrowser for %r', url)
        return url


if __name__ == '__main__':
    utils.log_to_stderr(['__main__', 'xpathscraper', 'requests'])
    baker.run()
