"""Tries to find a description of a blog from "about" or "contact" pages.
It uses ``lxml-readability`` package to extract human readable page from HTML.
"""

import logging

import baker
import lxml.html
import requests
from readability import readability

from xpathscraper import textutils


log = logging.getLogger('platformdatafetcher.descriptionfetcher')


class FromMetaTagsDescriptionFetcher(object):

    def __init__(self, url):
        self.url = url

    def fetch_description(self):
        r = requests.get(self.url)
        tree = lxml.html.fromstring(r.text)
        fragments = []
        metas = tree.xpath('//meta')
        for meta in metas:
            name = meta.attrib.get('name', '').lower()
            if name in ('description', 'keywords'):
                fragments.append(meta.attrib.get('content', ''))
        return ' '.join(fragments) if fragments else None


DESC_LINKS_KEYWORDS = ['about', 'contact']

class FromAboutPageDescriptionFetcher(object):

    def __init__(self, url):
        self.url = url

    def fetch_description(self):
        r = requests.get(self.url)
        tree = lxml.html.fromstring(r.text)
        els = tree.xpath('//a') + tree.xpath('//area')
        pages = []
        seen_links = set()
        for el in els:
            if not el.attrib.get('href'):
                continue
            val = (el.text or '') + ' ' + el.attrib['href']
            if any(kw in val for kw in DESC_LINKS_KEYWORDS) and el.attrib['href'] not in seen_links:
                seen_links.add(el.attrib['href'])
                log.info('fetching description from link %s', el.attrib['href'])
                page = self._page_from_link(el.attrib['href'])
                pages.append(page)
        if not pages:
            log.warn('no description pages')
            return None
        best_page = select_description_page(pages)
        log.info('best page: %s', best_page)
        return best_page['title'] + ' '  + best_page['content']

    def _page_from_link(self, link):
        r = requests.get(link)
        doc = readability.Document(r.text)
        res = {'title': doc.short_title(), 'content': doc.summary()}
        #log.info('page from link %s: %s', link, res)
        return res


DESC_KEYWORDS = ['about', 'description', 'contact', 'me', 'i', 'interests', 'blog']
def select_description_page(pages):
    """``Pages`` is a list of dictionaries with 'title' and 'content'
    keys. A return value is a dictionary from the list which has
    the heighest probability to be a description/about page.
    """
    keywords_s = ' '.join(DESC_KEYWORDS)
    def score(p):
        title_score = textutils.word_matching_score(p['title'], keywords_s)
        content_score = textutils.word_matching_score(p['content'], keywords_s)
        # length score is 1.0 for 2000 chars, goes to 0 for 10000 or longer contents
        length_score = (10000 - min(10000, float(abs(len(p['content'])-2000))))/10000.0
        final_score = (title_score * 3 + content_score) * length_score
        log.debug('page: %s', dict(p, content=p['content'][:300]))
        log.info('title, content, length, final scores: %s, %s, %s, %s',
                 title_score, content_score, length_score, final_score)
        return final_score
    return max(pages, key=score)


@baker.command
def description_meta(url):
    print FromMetaTagsDescriptionFetcher(url).fetch_description()

@baker.command
def description_about(url):
    print FromAboutPageDescriptionFetcher(url).fetch_description()


if __name__ == '__main__':
    #utils.log_to_stderr()
    baker.run()

