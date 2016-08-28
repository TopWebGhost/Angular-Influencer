"""Assigning tags to posts and influencers, based on keywords manually
specified in "Filter Adjectives" spreadsheets. The tags are represented
as :class:`debra.models.ContentTag` instances.
"""

import logging
import csv
import os.path
from collections import defaultdict
import pprint
import glob
import sys

import baker
from django.conf import settings
import requests
import lxml.html
from celery.decorators import task
from django.db.models import F
from django.conf import settings
import nltk

from xpathscraper import utils
from xpathscraper import xutils
from xpathscraper  import textutils
from debra import models
from platformdatafetcher import platformutils
from platformdatafetcher import contentclassification


log = logging.getLogger('platformdatafetcher.contenttagging')


ADJECTIVES_BY_PARENT = {}
KEYWORDS_BY_TAG = {}
BRANDS_BY_TAG = {}

FA_MIN_KEYWORDS = 10
FA_MIN_BRANDS = 5

POSTS_FOR_INFLUENCER_TAGGING = 40

BLACKLISTED_TAGS = [
    'kidsbabies.clothing',
]


class Tagger(object):

    def discover_tags(self, url, content):
        return []

    def discover_tags_from_fragments(self, urls_contents):
        res = []
        for url, content in urls_contents:
            res += self.discover_tags(url, content)
        return utils.unique_sameorder(res)


class NonemptyTagger(object):
    """Tag non empty content with 'nonempty' tag to know
    that the tagger was run for this content
    """

    def discover_tags(self, url, content):
        if content:
            return ['nonempty']
        return []



class FashionTagger(object):

    def discover_tags(self, url, content):
        if contentclassification.is_relevant_to_fashion(url, content):
            return ['fashion']
        return []


class FilterAdjectivesTagger(object):

    def __init__(self):
        # Initialize data from csvs
        if not ADJECTIVES_BY_PARENT:
            parse_all_filter_adjectives_csvs()
        if not BRANDS_BY_TAG or not KEYWORDS_BY_TAG:
            flatten_adjectives_by_parent()

    def discover_tags(self, url, content):
        content = xutils.strip_html_tags(content)
        self.ws = textutils.WordSearcher(content)
        res = []

        for tag in BRANDS_BY_TAG:
            contained = self._contained_keywords(BRANDS_BY_TAG[tag])
            #log.info('Contained brands for tag %r: %s', tag, contained)
            if len(contained) >= FA_MIN_BRANDS:
                log.info('Contained keywords for tag %r: %s', tag, contained)
                log.info('Enough keywords to add tag')
                res.append(tag)

        for tag in KEYWORDS_BY_TAG:
            contained = self._contained_keywords(KEYWORDS_BY_TAG[tag])
            if len(contained) >= FA_MIN_KEYWORDS:
                log.info('Contained keywords for tag %r: %s', tag, contained)
                log.info('Enough keywords to add tag')
                res.append(tag)

        return res

    def discover_tags_from_fragments(self, urls_contents):
        self.debug_info = {'brands': defaultdict(list), 'keywords': defaultdict(list)}

        for url, content in urls_contents:
            content = xutils.strip_html_tags(content)
            self.ws = textutils.WordSearcher(content)

            for tag in BRANDS_BY_TAG:
                contained = self._contained_keywords(BRANDS_BY_TAG[tag])
                self.debug_info['brands'][tag].extend([(url, c) for c in contained])

            for tag in KEYWORDS_BY_TAG:
                contained = self._contained_keywords(KEYWORDS_BY_TAG[tag])
                self.debug_info['keywords'][tag].extend([(url, c) for c in contained])

        res = []
        for tag in self.debug_info['brands']:
            if len(self.debug_info['brands'].get(tag, [])) >= FA_MIN_BRANDS:
                log.info('Contained brands for tag %r: %s', tag, self.debug_info['brands'][tag])
                res.append(tag)
        for tag in self.debug_info['keywords']:
            if len(self.debug_info['keywords'].get(tag, [])) >= FA_MIN_KEYWORDS:
                log.info('Contained keywords for tag %r: %s', tag, self.debug_info['keywords'][tag])
                res.append(tag)
        res = utils.unique_sameorder(res)
        return res


    def _contained_keywords(self, keywords):
        res = []
        for kw in keywords:
            if self.ws.contains_sentence(nltk.wordpunct_tokenize(kw)):
                res.append(kw)
        return res

DEFAULT_TAGGERS = [
    NonemptyTagger,
    FashionTagger,
    #FilterAdjectivesTagger,
]

def tag_content(taggers, url, content, **content_tag_kwargs):
    if not content:
        log.warn('Empty content for url %r', url)
        return []
    res = []
    log.info('Tagging %r %r...', url, content[:100])
    for T in taggers:
        t = T()
        discovered = t.discover_tags(url, content)
        log.info('Tagging results returned by %r: %r', t, discovered)
        if discovered:
            res += discovered
    res = utils.unique_sameorder(res)
    return save_content_tags(res, **content_tag_kwargs)

def save_content_tags(tags, **content_tag_kwargs):
    cts = []
    for tag in tags:
        ct_q = models.ContentTag.objects.filter(tag=tag, **content_tag_kwargs)
        if ct_q.exists():
            ct = ct_q[0]
            log.debug('Skipping existing %r', tag)
        else:
            ct = models.ContentTag.objects.create(tag=tag, **content_tag_kwargs)
            log.debug('Created %r', ct)
        cts.append(ct)
    return cts


@task(name='platformdatafetcher.contenttagging.tag_post', ignore_result=True)
@baker.command
def tag_post(post_id):
    post = models.Posts.objects.get(id=int(post_id))
    with platformutils.OpRecorder(operation='tag_post', post=post) as opr:
        #assert not post.contenttag_set.exists(), 'Tags for this post were already computed'
        cts = tag_content(DEFAULT_TAGGERS, post.url, post.content, post=post)
        for ct in cts:
            if not models.ContentTagCount.objects.filter(platform=post.platform,
                                                         tag=ct.tag).exists():
                models.ContentTagCount.objects.create(platform=post.platform,
                                                      tag=ct.tag,
                                                      count=1)
            else:
                ctc = models.ContentTagCount.objects.filter(platform=post.platform,
                                                            tag=ct.tag).update(count=F('count')+1)
        return cts

def _include_parent_tag(tags):
    res = []
    for tag in tags:
        res.append(tag)
        parts = tag.split('.')
        if len(parts) > 1:
            res.append(parts[0])
    return utils.unique_sameorder(res)

@task(name='platformdatafetcher.contenttagging.tag_influencer', ignore_result=True)
@baker.command
def tag_influencer(influencer_id, to_save=False):
    influencer = models.Influencer.objects.get(id=int(influencer_id))
    with platformutils.OpRecorder(operation='tag_influencer', influencer=influencer) as opr:
        fat = FilterAdjectivesTagger()
        if not influencer.blog_platform:
            log.error('No blog platform for %r', influencer)
            return None
        posts = influencer.blog_platform.\
            posts_set.order_by('-create_date')[:POSTS_FOR_INFLUENCER_TAGGING]
        urls_contents = [(p.url, p.content) for p in posts if p.content]
        tags = fat.discover_tags_from_fragments(urls_contents)
        tags = _include_parent_tag(tags)
        log.info('All tags: %s', tags)
        if to_save:
            save_content_tags(tags, influencer=influencer)
        return fat.debug_info

def submit_tag_influencer_tasks():
    infs = models.Influencer.objects.filter(show_on_search=True)


### Test functions

def generate_csv_from_debug_infos(influencers_debug_infos, out='fa_tagging.csv'):
    all_tags = utils.unique_sameorder(sorted(KEYWORDS_BY_TAG.keys() + BRANDS_BY_TAG.keys()))

    initial_header = ['influencer_id', 'blog_url']

    tags_titles = []
    tag_type_to_idx = {}
    for i, tag in enumerate(all_tags):
        tags_titles.append('%s brands' % tag)
        tags_titles.append('%s keywords' % tag)
        tag_type_to_idx[(tag, 'brands')] = len(initial_header) + i*2
        tag_type_to_idx[(tag, 'keywords')] = len(initial_header) + i*2 + 1

    header_row = initial_header + tags_titles

    rows_data = []
    for influencer, debug_info in influencers_debug_infos:
        #print 'debug_info'
        #pprint.pprint(debug_info)
        d = {0: influencer.id, 1: influencer.blog_url}

        for type in ('brands', 'keywords'):
            for tag, urls_vals in debug_info[type].items():
                d[tag_type_to_idx[(tag, type)]] = urls_vals
        rows_data.append(d)

    max_idx = max(tag_type_to_idx.values())

    with open(out, 'w') as f:
        w = csv.writer(f)
        w.writerow(header_row)
        for d in rows_data:
            row = [d.get(i, '') or '' for i in xrange(max_idx + 1)]
            w.writerow(row)

def generate_csv_from_debug_infos_per_post(influencers_debug_infos, out='fa_tagging_per_post.csv'):
    header_row = ['influencer_id', 'blog_url', 'post_url', 'tag', 'matched_keywords']

    with open(out, 'w') as f:
        w = csv.writer(f)
        w.writerow(header_row)
        for influencer, debug_info in influencers_debug_infos:
            tags_kws_by_post_url = defaultdict(lambda: defaultdict(list))
            for type in ('brands', 'keywords'):
                for tag, urls_vals in debug_info[type].items():
                    for post_url, kw in urls_vals:
                        tags_kws_by_post_url[post_url][tag + ' ' + type].append(kw)
            for post_url, by_tag in sorted(tags_kws_by_post_url.items()):
                for tag, kws in sorted(by_tag.items()):
                    w.writerow([influencer.id, influencer.blog_url, post_url, tag, ', '.join(kws)])

def generate_csv_for_influencers(infs):
    idi = []
    for inf in infs:
        try:
            di = tag_influencer(inf.id)
            if di:
                idi.append((inf, di))
        except:
            log.exception('')
    generate_csv_from_debug_infos_per_post(idi)

@baker.command
def generate_csv_for_show_on_search(limit=100):
    infs = models.Influencer.objects.filter(show_on_search=True).\
        order_by('-score_popularity_overall')\
        [:int(limit)]
    generate_csv_for_influencers(infs)

@baker.command
def test_tagging():
    posts = models.Posts.objects.filter(influencer__in=models.Influencer.objects.filter(
        show_on_search=True)).order_by('-create_date')[:100]
    for p in posts:
        res = tag_post(p.id)
        if res and len(res) > 1:
            log.critical('FOUND TAGS FOR %r: %s', p, res)

@baker.command
def test_fa_tagging():
    global TAGGERS
    TAGGERS = [FilterAdjectivesTagger]
    infs = models.Influencer.objects.filter(show_on_search=True)
    for inf in infs:
        try:
            posts = inf.blog_platform.posts_set.order_by('-create_date')[:5]
            for post in posts:
                res = tag_post(post.id)
                res = [t.tag for t in res if t.tag != 'nonempty']
                print post.url
                print res
                print
        except:
            log.exception('')


### Parsing "Filter Adjectives" spreadsheet

def normalize_tag_name(tag_name):
    return tag_name.lower().strip().strip('.,:').replace(' ', '_').replace('/', '_').replace('-', '.')

def parse_filter_adjectives_csv(filename):
    global ADJECTIVES_BY_PARENT
    base_tag = os.path.basename(filename).split('.')[0].split(' - ')[1]
    base_tag = normalize_tag_name(base_tag)
    #log.info('base_tag: %r', base_tag)

    with open(filename) as f:
        r = csv.reader(f)

        # header row
        r.next()

        index_to_subcat = {0: 'brands'}
        subcats = r.next()
        for i, val in enumerate(subcats):
            if i == 0:
                # brands column
                continue
            index_to_subcat[i] = normalize_tag_name(val)
        #log.info('index_to_subcat: %s', index_to_subcat)

        ADJECTIVES_BY_PARENT[base_tag] = {}
        for subcat in index_to_subcat.values():
            ADJECTIVES_BY_PARENT[base_tag][subcat] = []

        for row in r:
            for i, val in enumerate(row):
                if not val or not val.strip():
                    continue
                if i in index_to_subcat:
                    ADJECTIVES_BY_PARENT[base_tag][index_to_subcat[i]].append(val)

        #pprint.pprint(ADJECTIVES_BY_PARENT)


def flatten_adjectives_by_parent():
    global KEYWORDS_BY_TAG
    global BRANDS_BY_TAG
    for parent_tag, d in ADJECTIVES_BY_PARENT.items():
        for k, lst in d.items():
            if k == 'brands':
                BRANDS_BY_TAG[parent_tag] = d['brands']
            elif k == 'self':
                KEYWORDS_BY_TAG[parent_tag] = d[k]
            else:
                tag = '%s.%s' % (parent_tag, k)
                KEYWORDS_BY_TAG[tag] = d[k]

    for tag in BLACKLISTED_TAGS:
        KEYWORDS_BY_TAG.pop(tag, None)
        BRANDS_BY_TAG.pop(tag, None)

    #print 'brands'
    #pprint.pprint(BRANDS_BY_TAG)
    #print 'keywords'
    #pprint.pprint(KEYWORDS_BY_TAG)


@baker.command
def parse_all_filter_adjectives_csvs():
    files = glob.glob(os.path.join(settings.PROJECT_PATH, 'debra/csvs/filter_adjectives/*.csv'))
    for file in files:
        parse_filter_adjectives_csv(file)
    flatten_adjectives_by_parent()

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
