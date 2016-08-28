"""For the given URL, computes if it is relevant to fashion.
"""
import logging
import baker
from django import db
from django.core.cache import get_cache
from celery.decorators import task
from bs4 import BeautifulSoup
import nltk
import pprint
from debra import models
from xpathscraper import utils
from debra import constants
from platformdatafetcher import platformutils


log = logging.getLogger('platformdatafetcher.estimation')


INVALID_BRAND_TAGS = {
    'express', 'gap', 'amazon', 'target', 'loft', '6pm', 'heels', 'drugstore',
    'coach', 'beauty', 'google', 'walmart', 'retailmenot', 'max', 'women',
    'amazon.com', 'walmart.com', 'old navy', 'banana republic', '403 forbidden',
    '404 not found', 'saturday', 'shift', 'and',
}

POPULAR_BRANDS_TO_LOAD = 100
MAX_POSTS_TO_FETCH = 20
TAGS_TO_FIND = 10
URL_FRAGMENTS_NO_RESOLVING = ['rstyle.me', 'shopstyle.com', 'shopstyle.co.uk', 'popsu.gr', 'currentlyobsessed.me']
URL_FRAGMENTS_REQUIRING_RESOLVING = ['linksynergy.com', 'bit.ly']
URL_FRAGMENTS_IN_IFRAMES = URL_FRAGMENTS_NO_RESOLVING + ['fashiolista.com', 'lookbook.nu', 'luckymag.com', 'glam.com']
URLS_NO_RESOLVING_TO_FIND = 2
URLS_REQUIRING_RESOLVING_TO_FIND = 5
FRAGMENTS_IN_IFRAMES_TO_FIND = 1

FASHION_KEYWORDS = [
    'lipstick', 'nailpolish', 'serum', 'body lotion', 'body wash', 'bangles',
    'necklace', 'bracelets', 'earrings', 'skinny jeans', 'stiletto', 'ballerina flats',
    'gladiator sandals', 'eyeliner', 'eyebrow pencil', 'dress' 'maxi',
    'gown', 'sheath dress', 'shift', 'shirt-dress', 'shirt dress', 'sweater',
    'hoodie', 'sweatshirt', 'knitted', 'cardigan', 'pullover', 'pants',
    'shorts', 'bottoms', 'slacks', 'chinos', 'corduroys', 'capris', 'trousers',
    'khakis', 'tights', 'leggings', 'tank top', 'cami', 'blouse', 'tee',
    'polo', 'turtleneck', 'v-neck', 'crewneck', 'cowl neck', 'button-down',
    'long sleeve', 'boyfriend tee', 'skirts', 'skirt', 'skort', 'pencil skirt',
    'maxiskirt', 'denim', 'jeans', 'outerwear', 'jacket', 'coat', 'blazer',
    'vest', 'sportcoat', 'trench', 'peacoat', 'topcoat', 'poncho', 'shawl',
    'anorak', 'footwear', 'flip flops', 'flip-flops', 'loafer', 'sandal',
    'wedge', 'sneaker', 'wingtip', 'stiletto', 'shoes', 'heels', 'knee-high',
    'riding boots', 'sleepwear', 'robe', 'nightgown', 'pajamas', 'nightie',
    'loungewear', 'belt', 'mittens', 'gloves', 'headband', 'scarves', 'scarf',
    'hat', 'beanie', 'fedora', 'beret', 'wide brim', 'baseball hat', 'baseball cap',
    'cowboy hat', 'visor', 'sunglasses', 'eyewear', 'aviator',
    'aviators', 'handbag', 'tote', 'wristlet', 'satchel', 'duffel', 'clutch',
    'hobo', 'cross-body', 'crossbody', 'purse', 'messenger', 'courier',
    'jewelry', 'bangle', 'cuff bracelet', 'brooch', 'hoops', 'earrings',
    'necklace', 'bracelet', 'pendant', 'jewelry', 'swimwear', 'bikini',
    'one-piece', 'one piece', 'swimsuit', 'swim suit', 'tankini', 'bandeau',
    'two-piece', 'two piece', 'cover up', 'coverup', 'sarong', 'beauty',
    'fragrance', 'lipstick', 'nailpolish', 'perfume', 'repair lotion',
    'perfecting cream', 'repairing lotion', 'facial cream', 'beauty products',
    'beauty product', 'makeup', 'maternity', 'plus-size', 'plus-size', 'plus size',
    'plus-sized', 'plus sized', 'sports bra', 'yoga tank', 'yoga shirt',
    'yoga pants', 'stretch pants', 'running pants', 'running shorts', 'running shoes',
    'tennis shoes', 'crosstrainers', 'rose gold', 'cashmere', 'leopard print',
    'animal print', 'houndstooth', 'woolen', 'plaid', 'flannel',
    'spandex', 'jacquard', 'cotton', 'silk', 'pastels', 'spring colors',
    'floral print', 'florals',
]


class RelevantToFashionEstimator(object):
    def _get_popular_brands(self):
        cache = get_cache('default')
        if not cache.has_key('popular_brands'):
            popular_brands = models.Brands.objects.\
                filter(blacklisted=False).\
                filter(num_items_shelved__gte=5).\
                exclude(name='www').\
                annotate(num_products=db.models.Count('productmodel')).\
                order_by('-num_products')[:POPULAR_BRANDS_TO_LOAD]
            cache.set('popular_brands', popular_brands, timeout=60 * 60 * 24)
        return cache.get('popular_brands')

    def __init__(self, to_save=True):
        self.to_save = to_save
        log.debug('Starting loading brand tags...')
        self.popular_brands = self._get_popular_brands()
        self.domains = [utils.domain_from_url(b.domain_name) for b in self.popular_brands]
        self.brand_names = [utils.strip_last_domain_component(b.name) for b in self.popular_brands]
        self.tags = utils.unique_sameorder(self.domains + self.brand_names + FASHION_KEYWORDS)
        self.tags = [t for t in self.tags if len(t) >= 3]
        self.tags = [t.lower() for t in self.tags]
        self.tags = [t for t in self.tags if t not in INVALID_BRAND_TAGS]
        self.tags_words = [tuple(nltk.wordpunct_tokenize(t)) for t in self.tags]
        log.debug('tags_words: %r', self.tags_words)

        self.resolver = utils.URLResolver()

        self.explanation = {}

    def _set_relevant(self, influencer, val):
        if self.to_save and influencer.relevant_to_fashion != val:
            log.info('Setting relevant_to_fashion=%r for influencer %r', val, influencer)
            self.explanation['result'] = val
            influencer.relevant_to_fashion = val
            influencer.save()
        return val

    def _find_tag_references(self, posts):
        found_tags = set()
        for post in posts:
            self._find_tags_in_post(post, found_tags)
            print(len(found_tags))
        return found_tags

    def _find_tags_in_post(self, post, found_tags):
        product_urls = [u.lower() for u in post.product_urls()]
        for tag in self.tags:
            if any(tag in url for url in product_urls):
                found_tags.add(tag)

        if post.content and (not self._looks_like_url_for_bs(post.content)) and post.content_words:
            for tags_words in self.tags_words:
                for words_candidate in utils.window(post.content_words, len(tags_words)):
                    #if 'forever' in post.content and tags_words==('forever', '21'):
                    #    log.debug('words_candidate=%r, tags_words=%r', words_candidate, tags_words)
                    if words_candidate == tags_words:
                        found_tags.add(words_candidate)

    def _find_url_references_no_resolving(self, posts):
        found_urls = set()
        for post in posts:
            product_urls = [u.lower() for u in post.product_urls()]
            for url in product_urls:
                if any(fragment in url for fragment in URL_FRAGMENTS_NO_RESOLVING):
                    found_urls.add(url)
        return found_urls

    def _find_url_references_requiring_resolving(self, posts):
        found_urls = set()
        for post in posts:
            product_urls = [u.lower() for u in post.product_urls()]
            for url in product_urls:
                if any(fragment in url for fragment in URL_FRAGMENTS_REQUIRING_RESOLVING):
                    resolved = self.resolver.resolve(url)
                    if resolved != url and any(tag in resolved for tag in utils.unique_sameorder(self.domains + self.brand_names)) or \
                            any(fragment in resolved for fragment in URL_FRAGMENTS_NO_RESOLVING):
                        found_urls.add(resolved)
        return found_urls

    def _find_fragment_references_in_iframes(self, influencer):
        if not influencer.blog_url:
            log.warn('No blog_url set for %r', influencer)
            return set()
        found_fragments = set()
        for content in utils.fetch_iframes(influencer.blog_url):
            for fragment in URL_FRAGMENTS_IN_IFRAMES:
                if fragment in content:
                    found_fragments.add(fragment)
        return found_fragments

    def _looks_like_url_for_bs(self, content):
        return ' ' not in content

    def estimate(self, influencer):
        self.explanation = {}

        blog_platform = influencer.blog_platform
        if not blog_platform:
            log.warn('%r has no blog platform', influencer)
            return self._set_relevant(influencer, False)

        log.info('RelevantToFashionEstimator.estimate for %r', influencer)
        posts = list(blog_platform.posts_set.all()[:MAX_POSTS_TO_FETCH])
        log.info('Got %d posts', len(posts))
        for p in posts:
            if not p.content or self._looks_like_url_for_bs(p.content):
                continue
            b = BeautifulSoup(p.content)
            text = b.get_text().lower()
            p.content_words = nltk.wordpunct_tokenize(text)
            #log.debug('Post %r, content words: %r', p, p.content_words)

        already_set = False

        # first checking if posts have some product urls links
        urls_no_resolving = self._find_url_references_no_resolving(posts)
        log.info('Found urls_no_resolving: %r', urls_no_resolving)
        self.explanation['found_urls_no_resolving'] = list(urls_no_resolving)
        self.explanation['len_found_urls_no_resolving'] = len(urls_no_resolving)
        if len(urls_no_resolving) >= URLS_NO_RESOLVING_TO_FIND:
            self._set_relevant(influencer, True)
            already_set = True

        urls_requiring_resolving = self._find_url_references_requiring_resolving(posts)
        log.info('Found urls_requiring_resolving: %r', urls_requiring_resolving)
        self.explanation['urls_requiring_resolving'] = list(urls_requiring_resolving)
        self.explanation['len_urls_requiring_resolving'] = len(urls_requiring_resolving)
        if not already_set and len(urls_requiring_resolving) >= URLS_REQUIRING_RESOLVING_TO_FIND:
            self._set_relevant(influencer, True)
            already_set = True

        iframe_fragments = self._find_fragment_references_in_iframes(influencer)
        log.info('Found iframe_fragments: %r', iframe_fragments)
        self.explanation['found_iframe_fragments'] = list(iframe_fragments)
        self.explanation['len_found_iframe_fragments'] = len(iframe_fragments)
        if not already_set and len(iframe_fragments) >= FRAGMENTS_IN_IFRAMES_TO_FIND:
            self._set_relevant(influencer, True)
            already_set = True

        tag_references = self._find_tag_references(posts)
        log.info('Found tag_references: %r', tag_references)
        self.explanation['found_tag_references'] = list(tag_references)
        self.explanation['len_found_tag_references'] = len(tag_references)
        if not already_set and len(tag_references) >= TAGS_TO_FIND:
            self._set_relevant(influencer, True)
            already_set = True

        if not already_set:
            log.info('No positive test')
            self._set_relevant(influencer, False)

        log.info('Result: %s', influencer.relevant_to_fashion)
        log.info('Explanation:\n%s', pprint.pformat(self.explanation))

        return influencer.relevant_to_fashion


RELEVANT_TO_FASHION_ESTIMATOR = None


def get_relevant_to_fashion_estimator():
    global RELEVANT_TO_FASHION_ESTIMATOR
    if RELEVANT_TO_FASHION_ESTIMATOR is None:
        RELEVANT_TO_FASHION_ESTIMATOR = RelevantToFashionEstimator()
    return RELEVANT_TO_FASHION_ESTIMATOR


@task(name='platformdatafetcher.estimation.estimate_if_fashion_blogger', ignore_result=True)
@baker.command
def estimate_if_fashion_blogger(influencer_id, to_save=True):
    influencer = models.Influencer.objects.get(id=int(influencer_id))
    posts = models.Posts.objects.filter(influencer=influencer, platform__platform_name__in=models.Platform.BLOG_PLATFORMS)
    with platformutils.OpRecorder('estimate_if_fashion_blogger', influencer=influencer) as opr:
        opr.data = {'posts_count': posts.count()}
        if posts.count() == 0:
            log.warn('estimate_if_fashion_blogger didnt start for %r because it has no blog posts yet', influencer)
            opr.data = dict(opr.data, explanation='no_posts')
            return
        estimator = get_relevant_to_fashion_estimator()
        estimator.to_save = to_save
        res = estimator.estimate(influencer)
        opr.data = dict(opr.data, explanation=utils.limit_lens(estimator.explanation, 10))
        log.info('Saved explanation:\n%s', pprint.pformat(opr.data))
        if to_save:
            influencer.append_validated_on(constants.ADMIN_TABLE_INFLUENCER_FASHION)
            influencer.save()
        return res


@baker.command
def test_trendsetters():
    infs = models.Influencer.objects.filter(shelf_user__userprofile__is_trendsetter=True)
    return _do_test(infs, '/tmp/trendsetters.pickle')


@baker.command
def test_nonfashion():
    infs = models.Influencer.objects.filter(relevant_to_fashion=False)
    return _do_test(infs, '/tmp/nonfashion.pickle')


def _do_test(infs, pickle_file):
    estimator = RelevantToFashionEstimator(to_save=False)
    good = 0
    bad = 0
    explanations = []
    for inf in infs:
        orig = inf.relevant_to_fashion
        res = estimator.estimate(inf)
        explanations.append((inf.id, estimator.explanation))
        if res == orig:
            log.warn('+++ The same relevant_to_fashion value for %r', inf)
            good += 1
        else:
            log.warn('--- Different relevant_to_fashion value for %r', inf)
            bad += 1
        utils.write_to_file(pickle_file, explanations, 'pickle')
    log.warn('GOOD: %d BAD: %d', good, bad)


@baker.command
def test_relevant_to_fashion_estimator(infs_count=100):
    infs = models.Influencer.raw_influencers_for_search()[:int(infs_count)]
    estimator = get_relevant_to_fashion_estimator()
    good = 0
    bad = 0
    for inf in infs:
        orig = inf.relevant_to_fashion
        res = estimator.estimate(inf)
        if res == orig:
            log.warn('+++ The same relevant_to_fashion value for %r', inf)
            good += 1
        else:
            log.warn('--- Different relevant_to_fashion value for %r', inf)
            bad += 1
    log.warn('GOOD: %d BAD: %d', good, bad)


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
