"""Creating new influencers.

Tasks in this module use multiple sources to acquire new blog urls that
have a chance to be relevant to fashion.

"""


import logging
import random
import pprint
import time

import baker
from celery.decorators import task
import requests
import lxml.html
from django.db.models import Q, Count

from debra import models
from debra import helpers
from xpathscraper import utils
from xpathscraper import xutils
from platformdatafetcher import fetcher
from platformdatafetcher import platformutils
from platformdatafetcher import contentfiltering
from platformdatafetcher import estimation
from hanna import import_from_blog_post


log = logging.getLogger('platformdatafetcher.pdimport')

PROXY_CONFIGS = [
    {
        'http': 'http://us.proxymesh.com:31280',
        'https': 'http://us.proxymesh.com:31280',
    },
    {
        'http': 'http://uk.proxymesh.com:31280',
        'https': 'http://uk.proxymesh.com:31280',
    },
]

GOOGLE_PLUS_PEOPLE_TEMPLATE = 'https://www.googleapis.com/plus/v1/people/{user_id}?key=AIzaSyA9wVIwr4M5B5nnaXnoY_mZNIl2ZmW1jXg'

SLEEP_AFTER_PROCESSING_BLOGGER = 15
ALSO_CRAWL_OTHER_BLOGS_FOLLOWED = False

BLACKLISTED_DOMAINS = [utils.domain_from_url(u) for u in import_from_blog_post.exclude_domains] + \
    ['etsy.com', 'widget.shopstyle.com']


def get_blog_url_from_googleplus(user_id):
    r = requests.get(GOOGLE_PLUS_PEOPLE_TEMPLATE.format(user_id=user_id))
    d = r.json()
    if not d.get('urls'):
        return None
    return d['urls'][0]


def get_proxy_config():
    return random.choice(PROXY_CONFIGS)


@task(name='platformdatafetcher.pdimport.import_blogurlsraw_single', ignore_result=True)
def import_blogurlsraw_single(blogurlsraw_id, to_save=True):
    m = models.BlogUrlsRaw.objects.get(id=int(blogurlsraw_id))
    if not m.source:
        log.error('No source set for %r', m)
        return
    if not m.blog_url:
        log.error('No blog_url set for %r', m)
        return

    dup_infs = models.Influencer.find_duplicates(m.blog_url, exclude_blacklisted=False)
    if helpers.all_blacklisted(dup_infs):
        log.error('All duplicate influencers blacklisted for url %r, not importing', m.blog_url)
        return
    if dup_infs:
        inf = helpers.select_valid_influencer(dup_infs)
        log.warn('Existing inf found: %r', inf)
    else:
        inf = models.Influencer(blog_url=m.blog_url, name=m.name, source='blogurlsraw')
        if to_save:
            inf.save()

    blog_pls = fetcher.create_platforms_from_urls([m.blog_url], True)
    if blog_pls:
        blog_pl = blog_pls[0]
        blog_pl.influencer = inf
    else:
        log.warn('Could not create blog platform from blog_url %r, using Custom platform_name',
                 m.blog_url)
        blog_pl = models.Platform(platform_name='Custom', url=m.blog_url, influencer=inf)
    log.info('Blog platform from blog_url: %r', blog_pl)
    if to_save:
        # This handles duplicates
        # set appropriate state
        blog_pl.platform_state = models.Platform.PLATFORM_STATE_STARTED
        blog_pl.save()

    pl = models.Platform(url=m.url, num_followers=m.num_followers, description=m.description,
                         influencer=inf)
    if 'lookbook.nu' in m.source:
        pl.platform_name = 'Lookbook'
    elif 'fashiolista.com' in m.source:
        pl.platform_name = 'Fashiolista'
    else:
        assert False, 'unknown source %r' % m.source
    if to_save:
        # This handles duplicates
        pl.save()

    # site_url can contain additional social handle
    if m.site_url:
        site_pls = fetcher.create_platforms_from_urls([m.site_url], True)
        if site_pls:
            site_pl = site_pls[0]
            site_pl.influencer = inf
            if to_save:
                # This handles duplicates
                site_pl.save()

    m.have_been_processed = True
    if to_save:
        m.save()


@task(name='platformdatafetcher.pdimport.import_from_blogger_profile', ignore_result=True)
@baker.command
def import_from_blogger_profile(follower_id, to_save=True):
    follower = models.Follower.objects.get(id=follower_id)
    with platformutils.OpRecorder(operation='import_from_pi', follower=follower) as opr:
        _do_import_from_blogger_profile(follower.url, opr, to_save)


def _do_import_from_blogger_profile(blogger_profile_url, opr, to_save=True):
    log.info('Processing profile %r', blogger_profile_url)

    r = requests.get(blogger_profile_url, headers=utils.browser_headers(), proxies=get_proxy_config())

    blogurls_names = []

    if utils.domain_from_url(r.url) == 'plus.google.com':
        gplus_user_id = r.url.rstrip('/').split('/')[-1]
        gplus_user = requests.get(GOOGLE_PLUS_PEOPLE_TEMPLATE.format(user_id=gplus_user_id)).json()
        log.info('Got gplus data:\n%s', pprint.pformat(gplus_user))
        if not gplus_user.get('urls'):
            log.warn('No gplus urls')
            return
        blog_url = gplus_user['urls'][0]['value']
        name = gplus_user['displayName']
        log.info('Gplus url and name: %r %r', blog_url, name)
        blogurls_names.append((blog_url, name))
    else:
        tree = lxml.html.fromstring(r.content)

        name_els = tree.xpath('//div[@class="vcard"]//h1')
        if not name_els:
            log.warn('No name els')
            name = None
        else:
            name = name_els[0].text.strip()
            if not name:
                log.warn('Empty name')
        log.info('Blogger name: %r', name)

        blog_url_els = tree.xpath('//a[contains(@rel, "contributor-to")]')
        if not blog_url_els:
            log.warn('No blog url')
            utils.write_to_file('/tmp/last_no_blog.html', r.text)
            blog_url = None
            if r.text.strip().lower() == 'proxy authorization required':
                raise Exception('Proxy error')
        else:
            for el in blog_url_els:
                blog_url = el.attrib['href'].strip()
                log.info('Blog url: %r', blog_url)
                blogurls_names.append((blog_url, name))
        if ALSO_CRAWL_OTHER_BLOGS_FOLLOWED:
            observed_els = tree.xpath('//li[@class="sidebar-item"]/a')
            for el in observed_els:
                blogurls_names.append((el.attrib.get('href'), None))

    log.info('Collected blogurls_names: %r', blogurls_names)
    data = {'inf_id_existing': [], 'inf_id_created': []}
    for blog_url, name in blogurls_names:
        if not blog_url:
            continue
        blog_pl_name = fetcher.create_platforms_from_urls([blog_url], True)[0].platform_name

        dup_infs = models.Influencer.find_duplicates(blog_url, exclude_blacklisted=False)
        if helpers.all_blacklisted(dup_infs):
            log.error('All duplicate influencers blacklisted for url %r, not importing', blog_url)
            continue
        if dup_infs:
            inf = helpers.select_valid_influencer(dup_infs)
            log.warn('Existing inf found: %r', inf)
            data['inf_id_existing'].append(inf.id)
        else:
            inf = models.Influencer(blog_url=blog_url, name=name, source='comments_import')
            log.info('Created new influencer %r', inf)
            data['inf_id_created'].append(inf.id)
            if to_save:
                inf.save()

        blog_pl_dups = models.Platform.find_duplicates(inf, blog_url, blog_pl_name)
        if blog_pl_dups:
            log.warn('Blog platform with url %r is already inserted: %r', blog_url, blog_pl_dups)
            continue

        blog_pl = models.Platform(platform_name=blog_pl_name,
                                  url=blog_url,
                                  influencer=inf)
        log.info('Created new platform %r', blog_pl)
        if to_save:
            blog_pl.save()
    opr.data = data
    time.sleep(SLEEP_AFTER_PROCESSING_BLOGGER)


@task(name='platformdatafetcher.pdimport.import_from_blog_url', ignore_result=True)
@baker.command
def import_from_blog_url(follower_id, to_save=True):
    follower = models.Follower.objects.get(id=follower_id)
    with platformutils.OpRecorder(operation='import_from_pi', follower=follower) as opr:
        url = utils.url_without_path(follower.url)
        log.info('Will check url %r', url)
        if any(invalid_s in url for invalid_s in ('@', '(', '..')):
            log.warn('Invalid follower url: %r', url)
            return
        log.info('import_from_blog_url runs for follower %r', follower)
        url = utils.resolve_http_redirect(url)
        domain = utils.domain_from_url(url)
        if domain in BLACKLISTED_DOMAINS:
            log.info('Domain %r is blacklisted', domain)
            return
        inf = helpers.create_influencer_and_blog_platform(url, 'comments_import', to_save)
        if not inf:
            log.error('Blacklisted url: %r', url)
        if inf and inf.id is not None:
            opr.data = {'inf_id_created': [inf.id]}
        else:
            opr.data = {'inf_cnt_skipped': 1}


@task(name='platformdatafetcher.pdimport.import_from_comment_content', ignore_result=True)
@baker.command
def import_from_comment_content(post_interaction_id, to_save=True):
    pi = models.PostInteractions.objects.get(id=int(post_interaction_id))
    with platformutils.OpRecorder(operation='import_from_comment_content', post_interaction=pi) as opr:
        log.info('import_from_comment_content for %r', pi)
        _do_import_from_content(pi.content, opr, to_save)

_DOMAINS_OF_POPULAR_BRANDS = None


@task(name='platformdatafetcher.pdimport.import_from_post_content', ignore_result=True)
@baker.command
def import_from_post_content(post_id, to_save=True):
    global _DOMAINS_OF_POPULAR_BRANDS

    if _DOMAINS_OF_POPULAR_BRANDS is None:
        log.info('Starting loading _DOMAINS_OF_POPULAR_BRANDS')
        popular_brands = models.Brands.objects.\
            filter(blacklisted=False).\
            filter(num_items_shelved__gte=5).\
            exclude(name='www').\
            annotate(num_products=Count('productmodel')).\
            order_by('-num_products')[:100]
        _DOMAINS_OF_POPULAR_BRANDS = [utils.domain_from_url(b.domain_name) for b in popular_brands]
        log.info('Finished loading _DOMAINS_OF_POPULAR_BRANDS')

    post = models.Posts.objects.get(id=int(post_id))
    with platformutils.OpRecorder(operation='import_from_post_content', post=post) as opr:
        log.info('import_from_post_content for %r', post)
        _do_import_from_content(post.content, opr, to_save, blacklisted_domains=BLACKLISTED_DOMAINS +
                                _DOMAINS_OF_POPULAR_BRANDS +
                                estimation.URL_FRAGMENTS_NO_RESOLVING +
                                estimation.URL_FRAGMENTS_REQUIRING_RESOLVING +
                                estimation.URL_FRAGMENTS_IN_IFRAMES)


def _do_import_from_content(content, opr, to_save, blacklisted_domains=BLACKLISTED_DOMAINS):
    """
    This function creates new platforms from content provided by searching for urls
    (except those given in blacklisted_domains).

    Limitation: it works only for building new 'blog' platforms, and doesn't work for creating new social platforms
    """
    if not content:
        log.warn('No content, doing nothing')
        return
    urls = contentfiltering.find_all_urls(content)
    log.info('Found %d urls: %r', len(urls), urls)
    platforms = []
    for url in urls:
        log.info('Oring url: %r', url)
        try:
            url = utils.resolve_http_redirect(url)
        except:
            log.exception('While resolve_http_redirect, skipping')
            continue
        log.info('Redirected url: %r', url)
        vurl = platformutils.url_to_handle(url)
        if not vurl:
            log.info('No handle computed from url %r, skipping', url)
            continue
        domain = utils.domain_from_url(vurl)
        if domain in blacklisted_domains:
            log.info('Domain %r is blacklisted', domain)
            continue
        blog_url = utils.url_without_path(url)
        if domain.endswith('.wordpress.com'):
            platforms.append(models.Platform(platform_name='Wordpress', url=blog_url))
        elif domain.endswith('.blogspot.com'):
            platforms.append(models.Platform(platform_name='Blogspot', url=blog_url))
        else:
            content = xutils.fetch_url(blog_url)
            if content:
                discovered_pname = xutils.contains_blog_metatags(content)
                if discovered_pname:
                    platforms.append(models.Platform(platform_name=discovered_pname, url=blog_url))
                    continue
            platforms.append(models.Platform(platform_name='Custom', url=blog_url))

    influencers = []
    influencers_created = []
    for plat in platforms:
        inf, inf_created = helpers.get_or_create_influencer(plat.url, 'comments_content_import',
                                                            to_save)
        if not inf:
            log.warn('Skipping url %r because influencer with this url is blacklisted', plat.url)
            continue
        plat.influencer = inf
        influencers.append(inf)
        if inf_created:
            influencers_created.append(inf)

    if opr:
        opr.data = {
            'influencer_ids': [influencer.id for influencer in influencers],
            'influencer_created_ids': [influencer.id for influencer in influencers_created],
            'influencer_blog_urls': [influencer.blog_url for influencer in influencers],
        }

    log.info('Platforms from content: %r', platforms)
    if to_save:
        for plat in platforms:
            # influencer of None means we got a blacklisted influencer
            # when we searched by URL.
            if plat.influencer is not None:
                plat.save()

    return platforms


@task(name='platformdatafetcher.pdimport.submit_import_blogurlsraw_tasks', ignore_result=True)
@baker.command
def submit_import_blogurlsraw_tasks(limit=None, to_save=True):
    to_process_q = models.BlogUrlsRaw.objects.filter(have_been_processed=False, blog_url__isnull=False)
    count = to_process_q.count()
    log.info('Processing %s rows', count)
    for i, m in enumerate(to_process_q):
        if limit is not None and i >= limit:
            log.warn('Limit')
            break
        log.info('Submitting %d/%d %r', i + 1, count, m)
        import_blogurlsraw_single.apply_async(args=[m.id, to_save], queue='pdimport')


@baker.command
def test_import_from_comment_content():
    pis = models.PostInteractions.objects.filter(Q(content__contains='http') |
                                                 Q(content__contains='.com'), post__url__contains='pennypincherfashion.com').order_by('-post__create_date')
    pis = pis[:100]
    all_plats = set()
    for pi in pis:
        print "[%s] For comment %s" % (pi.post.url, pi.content)
        platforms = import_from_comment_content(pi.id, False)
        all_plats = all_plats.union(set(platforms))
    print "Found total of %d unique platforms" % len(all_plats)
    for plat in all_plats:
        print plat


@task(name='platformdatafetcher.pdimport.create_influencer_from_bad_brands', ignore_result=True)
def create_influencer_from_bad_brands(brand, to_save=True):
    '''
    This method creates influencers from Brands whose domains contain blogger urls.
    Example:
        blogspot = Brands.objects.filter(domain_name__icontains='blogspot.")
        blogspot.update(blacklisted=True)
        for b in blogspot:
          create_influencer_from_bad_brands(b, True)


        Double checks:
            this function should be called only for those Brands that have not been passed through this function
            we shouldn't run this for brands with domain_name in 'tumblr.com', because these influencer could have
                a separate blog (say on blogspot.com) and then we will have duplicates

    '''
    with platformutils.OpRecorder(operation='import_from_bad_brand', brand=brand) as opr:
        url = brand.domain_name
        domain = utils.domain_from_url(url)
        if domain in BLACKLISTED_DOMAINS:
            log.info('Domain %r is blacklisted', domain)
            return
        inf = helpers.create_influencer_and_blog_platform(
            url, 'discovered_from_brands', to_save, platform_name_fallback=True)
        if not inf:
            log.error('Blacklisted url: %r', url)
        if inf and inf.id is not None:
            opr.data = {'inf_id_created': [inf.id]}
        else:
            opr.data = {'inf_cnt_skipped': 1}


@baker.command
def create_influencers_from_pinterest(str_list_of_pinboards):
    '''
    This method creates influencers given a list of pinboard urls.

    Algorithm:
        1. Create a parent influencer I
        2. Create a platform for each pinboard url for I
        3. Issue a fetcher task for each of these platforms
        4. Once they are done, iterate over the posts for each these platforms
            - find their pin source
            - for each of these pin source, create a new influencer and a blog platform, with source = 'from_pinterest'
        5. Create a new policy that gives higher priority to fetchers for these influencers
    '''

    list_of_pinboards = str_list_of_pinboards.split("\n")

    inf, _ = models.Influencer.objects.get_or_create(blog_url='http://theshelf.com/blog',
                                                     source='pinterest_list_manual')
    from . import fetchertasks
    for url in list_of_pinboards:
        if len(url) < 5:
            continue
        platform, _ = models.Platform.objects.get_or_create(influencer=inf, url=url, platform_name='Pinterest')
        fetchertasks.fetch_platform_data.apply_async([platform.id], queue='new_influencers_from_pinterest')


def check_status_of_manual_creating_platforms():
    plats = models.Platform.objects.filter(
        influencer__source='pinterest_list_manual:blogger_signup', platform_name='Pinterest')
    pins = models.Posts.objects.filter(platform__in=plats)
    print "Got %d pins so far " % pins.count()

    # exclude: rstyle, pinterest.com, facebook.com, brands url, fabsugar, popsugar

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
