from __future__ import absolute_import, division, print_function, unicode_literals
from celery.decorators import task
from collections import namedtuple
import nltk
from debra.models import Category, PostCategory, Posts, ProductModelShelfMap, Platform, Influencer, PostInteractions
import inflect
from django.utils import encoding
import re
from bs4 import BeautifulSoup
import logging

log = logging.getLogger('platformdatafetcher.categorization')


priority_keywords = {'fashion': ['rstyle.me', 'shopstyle.com', 'shopstyle.co.uk', 'popsu.gr', 'currentlyobsessed.me',
                                 'ootd', ],
                     'beauty': ['rstyle.me', 'shopstyle.com', 'shopstyle.co.uk', 'popsu.gr', 'currentlyobsessed.me']}

class PostInfo(object):
    def __init__(self, post, post_url, content):
        self.post_url = post_url
        self.content = content

        if content:
            self.content_lower = content.lower()
        else:
            self.content_lower = ''

        # this means that we have done the product imports
        if post.products_import_completed:
            prods = post.get_product_json()
            all_txt = ''
            for p in prods:
                keys = ['prod_name', 'designer_name', 'brand_name', 'domain_name']
                for k in keys:
                    try:
                        if k in p.keys():
                            all_txt += ' ' + p[k]
                    except:
                        pass

            all_txt = all_txt.lower()
            if len(all_txt) > 0:
                #print("Product related text: %s" % all_txt)
                self.content_lower += all_txt
        else:
            log.info("WARNING: this post has not been imported yet %s" % post)

        # add title
        if post.title:
            self.content_lower += ' ' + post.title.lower()

        # now add content from all post interactions for this post
        comments = PostInteractions.objects.filter(post=post, content__isnull=False)
        for c in comments:
            self.content_lower += ' ' + c.content.lower()

        post_url_elems = re.split('_|-|\.', post_url)
        new_url_str = ' '.join(post_url_elems)
        self.content_lower += " " + new_url_str.lower()

        self.init_words()

    def init_words(self):
        soup = BeautifulSoup(self.content_lower)
        t = soup.text
        self.words = nltk.wordpunct_tokenize(t.lower())


CategoryMatch = namedtuple('CategoryMatch',
                           ['success', 'matched_words', 'category_id', 'category_name'])


def find_alterations(words):
    inflecter = inflect.engine()
    result = set()
    result.add(words)
    result.add(words.strip())
    for w in words.split():
        try:
            o = inflecter.singular_noun(w)
        except:
            pass
            continue
        if o:
            result.add(words.replace(w, o))
        else:
            o = inflecter.plural(w)
            result.add(words.replace(w, o))
    return result


class CategoryMatcher(object):
    @classmethod
    def from_category(cls, category):
        return cls(category_id=category.pk,
                   category_name=category.name,
                   keywords=category.keywords,
                   match_threshold=category.match_threshold)

    def _create_match(self, success, matched_words):
        return CategoryMatch(success, matched_words, self.category_id, self.category_name)

    def __init__(self, category_id, category_name, keywords, match_threshold):
        self.category_id = category_id
        self.category_name = category_name
        self.keywords = set(keywords)
        self.match_threshold = match_threshold

    def successfully_matched(self, common_words, count_words=0, found_high_priority_keywords=None):

        threshold = 8
        # if we have less than 250 words, use half the threshold
        if count_words <= 250 or found_high_priority_keywords:
            log.info("count_words %s found_high_priority_keywords %s " % (count_words, found_high_priority_keywords))
            threshold /= 2
        success = len(common_words) >= threshold
        return self._create_match(success, common_words)

    def matches(self, post_info):
        if not self.match_threshold:
            return self._create_match(False, 0)

        common_words = []
        for word in post_info.words:
            if word in self.keywords:
                common_words.append(word)

        return self.successfully_matched(common_words, len(post_info.words))


class CategoryMatcherWithKeywordPhrases(CategoryMatcher):
    """
    Extends the CategoryMatcher class with a phrase checker
    => we check that each phrase in keywords match exactly
    => we also check plural of each phrase match exactly

    So for example: a phrase like "travel tip" will create one more additional phrases:
        a) "travel tips"
    """
    def matches(self, post_info):
        common_phrases = set()
        content_lower = post_info.content_lower
        found_high_priority_keywords = []
        # helper method to save locations where a keyword was found (to avoid double counting)
        def add_val(k, v):
            # here we store the keyword and the location where it was found as a single value
            common_phrases.add(k+":"+str(v))

        # check for domain specific keywords
        if self.category_name in priority_keywords.keys():
            pk = priority_keywords[self.category_name]
            for p in pk:
                if p in content_lower:
                    found_high_priority_keywords.append(p)
                    break

        for phrase_u in self.keywords:
            phrase = encoding.smart_str(phrase_u, encoding='ascii', errors='ignore')
            if not phrase.strip():
                # empty string at this point
                continue

            # if this is a single word, we need to have exact match: so we search only in tokens of content
            # and each unique match is counted (so we need to store the location in the text where it matched)
            if len(phrase.split()) == 1 and post_info:
                alterations = find_alterations(phrase)
                found = False
                for al in alterations:
                    if post_info and post_info.words:
                        indices = [i for i, x in enumerate(post_info.words) if x == al]
                        #print("For %s, we found %s alterations" % (phrase, alterations))
                        for i in indices:
                            add_val(al, i)
                            log.info("Found %s matches for %s in words" % (indices, al))
                            found = True
                if not found:
                    # make sure we're matching the exact word (so for "tent" we can match " tent", " tent.", " tent)"
                    p = re.compile('\s%s[\s\.);]+' % phrase)
                    indices = [m.start() for m in p.finditer(content_lower)]
                    for i in indices:
                        add_val(phrase, i)
                        log.info("Found %s at these locations %s" %(phrase, indices))
                continue
            # find all alterations for the phrase
            alterations = find_alterations(phrase)
            for al in alterations:
                p = re.compile(al)
                indices = [m.start() for m in p.finditer(content_lower)]
                for i in indices:
                    add_val(phrase, i)
                    log.info("Found %s at these locations %s in content" % (al, indices))
        log.info("common_phrases found: %d total_words: %d" % (len(common_phrases), len(post_info.words)))
        return self.successfully_matched(list(common_phrases), len(post_info.words), found_high_priority_keywords)



_CATEGORY_MATCHERS = None

# Categories that we're going to test right now
_CATEGORY_NAMES_TO_MATCH = ['food', 'fashion', 'beauty', 'travel', 'kids']

# Find all relevent category matches
def get_category_matchers(use_phrases=True):
    global _CATEGORY_MATCHERS
    if _CATEGORY_MATCHERS is None:
        categories = Category.objects.filter(name__in=_CATEGORY_NAMES_TO_MATCH)
        if use_phrases:
                _CATEGORY_MATCHERS = [CategoryMatcherWithKeywordPhrases.from_category(c) for c in categories]
        else:
                _CATEGORY_MATCHERS = [CategoryMatcher.from_category(c) for c in categories]
    return _CATEGORY_MATCHERS


class Categorizer(object):
    def __init__(self, matchers=None, use_phrases=True):
        self.matchers = matchers or get_category_matchers(use_phrases=use_phrases)

    def match_categories(self, post_info):
        matches = [matcher.matches(post_info) for matcher in self.matchers]
        return [match for match in matches if match.success]


@task(name='platformdatafetcher.categorization.categorize_post', ignore_result=True)
def categorize_post(post_id, use_phrases=True):
    post = Posts.objects.get(id=post_id)
    if post.categorization_complete:
        print("Post %r has already completed categorization, returning" % post)
        return

    # TODO: Put it to try/except to observe errors in sentry
    categorizer = Categorizer(use_phrases=use_phrases)
    category_matches = categorizer.match_categories(PostInfo(post, post.url, post.content))

    for category_match in category_matches:
        # same post can have multiple categories
        #print("category_match.id %r" % category_match.category_id)
        #print("category_match.category_name %r" % category_match.category_name)
        #print("category_match.matched %r" % category_match.matched_words)
        # <post, category_id> is a unique pair
        pc, _ = PostCategory.objects.get_or_create(post_id=post_id, category_id=category_match.category_id)
        pc.match_data = dict(matched_words=category_match.matched_words)
        pc.save()
    post.categorization_complete = True
    post.save()

@task(name='platformdatafetcher.categorization.categorize_influencer_posts', ignore_result=True)
def categorize_influencer_posts(inf_id, only_products_import_completed=False):
    inf = Influencer.objects.get(id=inf_id)
    posts = Posts.objects.filter(influencer=inf, platform_name__in=Platform.BLOG_PLATFORMS)
    if only_products_import_completed:
        posts = posts.filter(products_import_completed=True)
    pids = posts.values('id')
    ids = [x['id'] for x in pids]
    for id in ids:
        categorize_post.apply_async([id], queue='post_categorization')


@task(name='platformdatafetcher.categorization.categorize_all_influencers', ignore_result=True)
def categorize_all_influencers():
    infs = Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True).exclude(source__contains='brand')
    for i in infs:
        categorize_influencer.apply_async([i.id], queue='denormalization_slow')

### Setting categorization here for influencers
@task(name='platformdatafetcher.categorization.categorize_influencer', ignore_result=True)
def categorize_influencer(inf_id, threshold_cnt_req=3, update_category_info=True):
    """
    This function should be called once-in-awhile with pretty less frequency.

    It's also a first version, there are multiple improvements we can make later on.

    But let's first describe what it does.

    It goes through the category_info map (e.g., {'fashion': 10, 'beauty': 15, 'travel': 30})
       - calculates the total (for this example, it will be 55)
       - iterates over each category:
            - finds out count for that category
            - if count > threshold_cnt_req
                => add this category as the one that this influencer talks about regularly (some authority)
        (for this example, we'll have found=['beauty', 'travel', 'beauty'] as her main categories.


    There are three main limitations:
    a) if the blogger starts to change topics more frequently, then the % for each category might change and the
       found values might fluctuate quite a bit. If a client creates a collection for influencers based on their focus,
       then it may later found that the influencer is no longer about that particular focus.

    b) this doesn't pay attention to time-decay factor. For example, if someone talked about maternity 2 years ago,
       they will still show up as an expert.

    c) threshold_cnt_req is not a good idea. Once a blogger passes the threshold for each, she will be forever be an
        expert on these categories. But perhaps time-decay factor solution might remedy this situation.

    """
    # first, we will call the method to set the counters for each category
    inf = Influencer.objects.get(id=inf_id)

    inf.posts_count = inf.calc_posts_count()
    inf.save()

    if inf.category_info == {} or update_category_info:
        inf.calculate_category_info()
        inf.save()

    if inf.category_info == {}:
        print("No posts with categories found, returning %r" % inf)
        return

    # now, we're going to assign categories to this influencer
    categories_num_post_mapping = inf.category_info['count']
    found_cats = []
    for cat in categories_num_post_mapping.keys():
        cnt = categories_num_post_mapping[cat]
        # either % of posts > threshold_pct_req
        # or sheer number of posts for this category > threshold_cnt_req
        if cnt >= threshold_cnt_req:
            found_cats.append(cat)
    print("Found %s categories for %s. threshold: %d" % (found_cats, inf, threshold_cnt_req))
    # TODO: set these found_cats in Influencer in some field once we decide
    inf.categories['found'] = found_cats
    inf.save()


def move_categories():
    # temporary function to copy counts for categories to a count sub-object
    infs = Influencer.objects.filter(show_on_search=True).with_categories()
    for i in infs:
        categories = i.category_info
        categories['count'] = {}
        total = 0
        for c in categories.keys():
            if c in ['found', 'count']:
                continue
            categories['count'][c] = categories[c]
            total += (int(categories[c]))
        categories['count']['total'] = total
        i.save()


### helper methods for testing

# read from file, returns an array of unique phrases
def read_from_csv(file_path):
    import pandas

    pan = pandas.read_csv(file_path)
    vals = pan.columns.values
    res = set()
    for v in vals:
        vv = pan[v]
        for a in vv:
            res.add(a)

    res_str = [str(r) for r in res]
    final_res = []
    for r in res_str:
        if r == 'nan':
            continue
        final_res.append(r.lower())

    return final_res

MATCH_THRESHOLDS = [1, 2, 5, 10]

category_file_mapping = {'beauty': '/home/ubuntu/Categ- Keywords V2 - Beauty.csv',
                             'cpg': '/home/ubuntu/Categ- Keywords V2 - CPG.csv',
                             'diy': '/home/ubuntu/Categ- Keywords V2 - DIY.csv',
                             'decor': '/home/ubuntu/Categ- Keywords V2 - Decor.csv',
                             'food': '/home/ubuntu/Categ- Keywords V2 - Food and Drinks.csv',
                             'fitness': '/home/ubuntu/Categ- Keywords V2 - Health %2F Fitness %2F Outdoor Activities.csv',
                             'kids': '/home/ubuntu/Categ- Keywords V2 - Kids%2FBabys.csv',
                             'travel': '/home/ubuntu/Categ- Keywords V2 - Travel.csv',
                             'fashion': '/home/ubuntu/Categ- Keywords V2 - Fashion.csv'
                             }


def get_all_keywords():
    result = {}
    for i, category_name in enumerate(category_file_mapping):
        filepath = category_file_mapping[category_name]
        keywords = read_from_csv(filepath)
        result[category_name] = keywords
    return result


def test_influencer(inf, category_keyword_mapping_getter=get_all_keywords):
    match_threshold = MATCH_THRESHOLDS[0]
    if not inf.blog_platform:
        print("No blog platform for %s" % inf)
        return

    category_keyword_mapping = category_keyword_mapping_getter()

    for i, category_name in enumerate(category_keyword_mapping.keys()):
        print("Checking %s" % category_name)
        keywords = category_keyword_mapping[category_name]
        matcher = CategoryMatcherWithKeywordPhrases(i, category_name, keywords, match_threshold)
        categorizer = Categorizer([matcher])
        print("blah")
        posts = Posts.objects.filter(platform=inf.blog_platform)
        for post in posts[:5]:
            print("Checking post %s %s" % (post.id, post.url))
            category_matches = categorizer.match_categories(PostInfo(post, post.url, post.content))
            for category_match in category_matches:
                print(post.url, category_match.category_name, category_match.matched_words, len(category_match.matched_words))
