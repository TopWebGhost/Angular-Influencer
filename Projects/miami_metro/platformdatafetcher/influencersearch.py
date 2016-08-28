"""Inserting new influencers by finding blog urls using Google Search. The access
to the Google Search is implemented using Selenium and simulating user's behaviour.
"""

import logging
import time
import random

import baker
from selenium.webdriver.common.keys import Keys
from debra import models
from django.conf import settings
from . import contentclassification
from hanna import import_from_blog_post
from debra import helpers

from xpathscraper import utils
from xpathscraper import xutils
from xpathscraper import xbrowser
from platformdatafetcher import platformextractor



log = logging.getLogger('platformdatafetcher.influencersearch')


class GoogleScraper(object):

    def __init__(self, xb):
        self.xb = xb

        self.xb.load_url('https://www.google.com/')

    def _ensure_more_results(self):
        cur_goog_url = self.xb.driver.current_url
        self.xb.load_url(cur_goog_url+'&num=100')
        time.sleep(5)

    def block_if_captcha(self):
        while True:
            cur_goog_url = self.xb.driver.current_url
            if 'IndexRedirect' in cur_goog_url:
                print "Sleep for 5s until captcha is fixed"
                time.sleep(5)
            else:
                return

    def search(self, query, pages):
        input_el = self.xb.driver.find_element_by_xpath('//input[@type="text"]')
        input_el.send_keys(query)
        time.sleep(1)
        self._find_search_button().click()
        time.sleep(5)
        #self._ensure_more_results()
        self.block_if_captcha()

        for page_no in xrange(pages):
            current_domains = [utils.domain_from_url(u) for u in self._current_results()]
            current_domains = [cd.split(' ', 1)[0] for cd in current_domains]
            current_urls = ['http://%s' % u for u in current_domains]
            log.info('Current google results: %s', current_urls)
            yield current_urls

            self._sleep_before_clicking_next()
            next_el = self.xb.driver.find_element_by_id('pnnext')
            next_el.click()
            time.sleep(5)
            #self._ensure_more_results()
            self.block_if_captcha()

    def _current_results(self):
        els = self.xb.driver.find_elements_by_xpath('//cite')
        res = [el.text for el in els]
        return res

    def _sleep_before_clicking_next(self):
        to_sleep = random.randrange(2, 10)
        log.info('Sleeping %d', to_sleep)
        time.sleep(to_sleep)
        log.info('Continuing')

    def _find_search_button(self):
        buttons = self.xb.driver.find_elements_by_tag_name('button')
        matching = [b for b in buttons if b.get_attribute('aria-label') == 'Google Search']
        if not matching:
            raise Exception('No "Google Search" button')
        return matching[0]

GOOGLE_QUERIES =  [
    "{brand.name} fashion blogger",
    "{brand.name} giveaway",
    "{brand.name} sponsored post",
    "{brand.name} beauty blogger",
]

def get_sponsored_brands_queries():
    res = []
    brands = models.Brands.objects.filter(supported=True).order_by('id')
    for brand in brands:
        for q in GOOGLE_QUERIES:
            res.append(q.format(brand=brand))
    return res

FREEFORM_BRANDS = """
birchbox

true and co

lulus

j crew

nordstrom

stitchfix

ruche

inpink

shoe dazzle

dollar shave

shoe mint

Old Navy

Net a porter

chloe and isabel

Stella and dot

bonobos

ann taylor

loft

blush box

honest company

le tote

jewel mint

wantable

sephora

just fab

toms

trunk club

jack threads

combat gent

dragon inside

madewell

modcloth

shabby apple
"""
FREEFORM_BRANDS = [line for line in FREEFORM_BRANDS.split('\n') if line.strip()]


FREEFORM_QUERIES = [
    '{name} fashion blog',
    '{name} fashion blogger',
    '{name} giveaway',
    '{name} review',
    '{name} sponsored',
]

def get_freeform_queries():
    res = []
    for brand_name in FREEFORM_BRANDS:
        for q in FREEFORM_QUERIES:
            res.append(q.format(name=brand_name))
    res.append("fashion blogger giveaway")
    res.append("style blog giveaway")
    res.append("style tag giveaway")
    return res

def collect_urls_from_google(query, pages):
    log.info('Collecting results for query %r', query)
    urls = []
    try:
        with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
            g = GoogleScraper(xb)
            for page_no, results in enumerate(g.search(query, pages)):
                log.info('%d results from page %d', len(results), page_no)
                urls.extend(results)
                time.sleep(random.randrange(1, 5))
    except Exception as e:
        log.exception('While collecting urls, returning what is collected so far: %s' % e, extra={'query': query})
    log.info('Total results for query %r: %d', query, len(urls))
    return urls

@baker.command
def search_freeform():
    search_infs_using_preloaded_urls(get_freeform_queries(), pages=20)

def search_infs_using_preloaded_urls(queries, pages=20):
    for q in queries:
        try:
            urls = collect_urls_from_google(q, pages)
        except:
            log.exception('While collect_urls_from_google(%r), going to the next query', q)
            continue
        print "Got urls: %s" % urls
        return
        for url in urls:
            try:
                if utils.domain_from_url(url) in import_from_blog_post.exclude_domains_set:
                    log.warn('%r is blacklisted', url)
                    continue
                dups = models.Influencer.find_duplicates(url)
                log.info('%r dups: %s', url, dups)
                if not dups:
                    log.info('YES_CREATE %r', url)
                    new_inf = helpers.create_influencer_and_blog_platform(url, 'google', platform_name_fallback=True)
                    log.info('Created influencer: %r', new_inf)
                else:
                    log.info('NO_CREATE %r', url)
            except:
                log.exception('While processing url %r, skipping', url)

@baker.command
def search_infs_by_giveaways(pages=20):
    brands = models.Brands.objects.filter(supported=True).order_by('id')[12:13]
    for brand in brands:
        for q in GOOGLE_QUERIES:
            q = q.format(brand=brand)
            log.info('Searching: %r', q)
            try:
                with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
                    g = GoogleScraper(xb)
                    it = g.search(q, pages)
                    for results in it:
                        for url in results:
                            try:
                                if utils.domain_from_url(url) in import_from_blog_post.exclude_domains_set:
                                    log.warn('%r is blacklisted', url)
                                    continue
                                dups = models.Influencer.find_duplicates(url)
                                log.info('%r dups: %s', url, dups)
                                if not dups:
                                    log.info('YES_CREATE %r', url)
                                    new_inf = helpers.create_influencer_and_blog_platform(url, 'google', platform_name_fallback=True)
                                    log.info('Created influencer: %r', new_inf)
                                else:
                                    log.info('NO_CREATE %r', url)
                            except:
                                log.exception('While processing url %r, skipping', url)
            except Exception as e:
                log.exception('For brand %r got exception: %s' % (brand, e), extra={'pages': pages})


"""
https://docs.google.com/document/d/1ZpwAV1_5m8IDK1_MfDA5cfKmjZO5cCqAavXDTT764TM/edit contains the high level idea

Basically, we want to use Google to search for specific terms and find more bloggers
"""
BLOGGER_TERMS = ['travel', 'decor', 'men fashion', 'men style', 'plus fashion', 'lifestyle', 'fashion',
                 'style', 'lifestyle']

BLOGGER_SEARCH_TERMS = [x + ' blog ' for x in BLOGGER_TERMS]

COUNTRY_CODES = ['.co.uk', '.uk', '.ca', '.au', '.sg', '.ph', '.jp', '.in', '.de', '.ch', '.es', '.be']

GOOGLE_OPERATORS = ['inurl:blogspot inurl:'+x for x in COUNTRY_CODES] + \
                  ['inurl:'+x for x in COUNTRY_CODES]

NUM_PAGES = 20


def country_specific_google_queries(num_pages=NUM_PAGES, to_save=False):
    def run_query(query, country_code):
        urls = []
        try:
            urls = collect_urls_from_google([query], num_pages)
        except:
            log.exception('While collect_urls_from_google(%r), going to the next query', query)
        print "Got urls: %s with code %s" % (urls, country_code)
        return urls

    def is_valid_url(url):
        if utils.domain_from_url(url) in import_from_blog_post.exclude_domains_set:
            log.warn('%r is blacklisted', url)
            return False
        return True

    for term in BLOGGER_TERMS[:2]:
        bterm = term + ' blog '
        for code in COUNTRY_CODES:
            query1 = bterm + ' inurl:blogspot inurl:' + code
            query2 = bterm + ' inurl:' + code
            url1 = run_query(query1, code)
            url2 = run_query(query2, code)
            url = set(url1 + url2)
            # at this point, create an empty influencer that we'll process later on
            for u in url:
                if is_valid_url(u):
                    print "Create influencer for %s with source='google%s_%s'" % (u, code, term.replace(' ', '_'))
                    if to_save:
                        models.Influencer.objects.create(blog_url=u, source='google%s_%s' % (code, term.replace(' ', '_')))


def create_influencers_from_blacklisted_brands():
    blogspot_brands = models.Brands.objects.filter(domain_name__icontains='blogspot')
    print "Got %d brands with blacklisted" % blogspot_brands.count()

    good_urls = []
    for i, b in enumerate(blogspot_brands):
        print "%d %r" % (i, b)
        url = b.domain_name.lower()
        if utils.domain_from_url(url) in import_from_blog_post.exclude_domains_set:
            log.warn('%r is blacklisted', url)
            continue
        dups = models.Influencer.find_duplicates(url)
        log.info('%r dups: %s', url, dups)
        if not dups:
            print "Can create a new influencer for %s" % url
            good_urls.append(url)
        print "Good urls so far: %d" % len(good_urls)


def expand_canada_bloggers(issue_social_discovery=False, issue_influencer_classification=False):
    """
    This is a first attempt at expanding a specific set of influencers. We'll refactor this later on.
    """
    from debra import social_discovery
    from social_discovery import models as smodels

    # Source #1
    qaed = models.Influencer.objects.filter(validated_on__icontains='info').exclude(show_on_search=True)
    qaed = qaed.exclude(blacklisted=True)
    qaed = qaed.filter(demographics_location__icontains='canada')
    # these sould be added to a collection

    country_locations = ['canada', 'canadian', 'vancouver', 'toronto', 'quebec', 'montreal', 'ontario', 'calgary',
                        'alberta', 'british columbia', 'new foundland', 'halifax']

    country_domain_endswith = ['.ca', '.ca/']

    # Source #2
    insta = smodels.InstagramProfile.objects.filter(discovered_influencer__isnull=False)
    new_insta = smodels.InstagramProfile.objects.none()
    for loc in country_locations:
        insta_loc = insta.filter(profile_description__icontains=loc)
        new_insta |= insta_loc

    new_insta = new_insta.distinct('username')
    print "Got new_insta %d influencers" % new_insta.count()

    new_insta_inf_ids = new_insta.values_list('discovered_influencer__id', flat=True)
    new_insta_infs = models.Influencer.objects.filter(id__in=new_insta_inf_ids)
    print "remaining non-qaed infs from instagram %d" % new_insta_infs.count()

    # Source #3 now checking in our database
    remaining = models.Influencer.objects.all().exclude(validated_on__icontains='info').exclude(show_on_search=True)
    remaining = remaining.exclude(blacklisted=True)
    print "Got %d remaining influencers in the database" % remaining.count()
    country_domains_in_remaining = models.Influencer.objects.none()

    for dom in country_domain_endswith:
        # first search for domain ends with country codes
        remaining_dom = remaining.filter(blog_url__endswith=dom)
        country_domains_in_remaining |= remaining_dom

    print "Got %d remaining influencers with country specific domains" % country_domains_in_remaining.count()

    for loc in country_locations:
        # now search for locations in urls
        remaining_dom = remaining.filter(blog_url__icontains=loc)
        country_domains_in_remaining |= remaining_dom

    print "Got %d remaining influencers with country specific domains" % country_domains_in_remaining.count()

    # Source 4: now check google
    from_google = models.Influencer.objects.none()
    for dom in country_domain_endswith:
        rr = remaining.filter(source__icontains='google%s'%dom)
        from_google |= rr

    print "Got %d influencers from Google" % from_google.count()

    # Source 5: Twitter
    twitter = smodels.TwitterProfile.objects.filter(discovered_influencer__isnull=False)
    new_twitter = smodels.TwitterProfile.objects.none()
    for loc in country_locations:
        tw_loc = twitter.filter(profile_description__icontains=loc)
        new_twitter |= tw_loc

    new_twitter = new_twitter.distinct('screen_name')
    new_twitter_inf_ids = new_twitter.values_list('discovered_influencer__id', flat=True)
    new_twitter_infs = models.Influencer.objects.filter(id__in=new_twitter_inf_ids)
    print "remaining non-qaed infs from Twitter %d" % new_twitter_infs.count()

    potential_infs = new_insta_infs | new_twitter_infs | from_google | country_domains_in_remaining
    potential_infs = potential_infs.distinct('blog_url')

    potential_infs = potential_infs.exclude(validated_on__icontains='info')

    potential_infs_blogs = potential_infs.filter(classification='blog')

    # these need to be classified
    potential_infs_not_classified_yet = potential_infs.filter(classification__isnull=True)

    if issue_influencer_classification:
        for inf in potential_infs_not_classified_yet:
            contentclassification.classify_model.apply_async(kwargs={'influencer_id': inf.id}, queue='influencer_classification')


    # for the potential_infs_blogs, check these required characteristics
    # 1. Make sure these are live urls
    potential_infs_blogs_alive = potential_infs_blogs.filter(is_live=True)
    # 2. look at categorization value

    # 3. How many social platforms?
    f = potential_infs_blogs_alive.filter(fb_url__isnull=False)
    p = potential_infs_blogs_alive.filter(pin_url__isnull=False)
    t = potential_infs_blogs_alive.filter(tw_url__isnull=False)
    i = potential_infs_blogs_alive.filter(insta_url__isnull=False)
    y = potential_infs_blogs_alive.filter(youtube_url__isnull=False)
    # at least 3 => C(5, 3) = 5!/3!2! = 5 * 4/2 = 10
    # at least 2 => C(5, 2) = 5!/3!2! = 10
    at_least_2 = (f & p) | (f & t) | (f & i) | (f & y) | (p & t) | (p & i) | (p & y) | (t & i) | (t & y) | (i & y)
    at_least_2 = at_least_2.distinct()

    at_least_3 = (f & p & t) | (f & p & i) | (f & p & y) | (f & t & i) | (f & t & y) | (f & i & y) | \
                 (p & t & i) | (p & t & y) | (p & i & y) | (t & i & y)
    at_least_3 = at_least_3.distinct()

    if issue_social_discovery:
        at_least_3_ids = at_least_3.values_list('id', flat=True)
        others = potential_infs_blogs_alive.exclude(id__in=at_least_3_ids)
        for o in others:
            platformextractor.extract_combined.apply_async([o.id], queue="platform_extraction")


    # 4. Avoid news sites? (No more than 1 post per day)

    # 5. Categorization
    #   5.a need to call inf.calculate_category_info()
    #   5.b need to call categorization.categorize_influencer(inf.id)

    # 6. Run blognamefetcher for the platform

    # 7. Run influencerattributeselector on the influencer

    # 8. Run set_profile_pic() method for each influencer

    # 9. Only upgrade influencers that have a name, blogname, profile_pic, min. amount of categorized posts,


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

