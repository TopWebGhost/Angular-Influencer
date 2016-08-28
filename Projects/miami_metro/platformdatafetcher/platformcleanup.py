__author__ = 'atulsingh'

"""
In this module, we plan to cleanup the platforms that we create for each influencer:
1. remove platforms with blacklisted urls
2. remove platforms with urls that point to other platforms
3. remove unwanted characters from the platform urls (e.g., anything with a query params, subdirectories)
4. make sure to make the url a valid url (e.g., add http:// if it doesn't exist)
5. make sure the urls are consistent after loading the page (i.e., if the page redirects, update platform.url to the final page url)
5. verification checks to make sure the platform actually points to the blog
    a) the posts for the platform should contain a reference to the platform.url
    b) the description of the platform should contain a reference to the platform.url
6. if we have more than one platform in (a) + (b), we should run handle_duplicates()

TODO:: We should handle the case where there may be more than one valid social handle
"""

from celery.decorators import task
from debra.models import Influencer, Platform, Posts, InfluencerCheck
from xpathscraper import utils
import urllib2
import requests
import lxml.html
from platformdatafetcher import fetcherbase, fetcher, contentfiltering, platformutils
import logging
import re
from debra import db_util
from debra import constants
import json

log = logging.getLogger('platformdatafetcher.platformcleanup')

BLACKLISTED_PLATFORM_URLS = {'Pinterest': 'facebook.com/,instagram.com/,twitter.com/,pinterest.com/pins/,blog.pinterest.com/,pinterest.com/about/,pinterest.com/search/,pinterest.com/join/?,pinterst.com/login/?',
                             'Facebook': 'instagram.com/,twitter.com/,pinterest.com/,/login.php,/sharer.php,/photo.php,/p.php,/l.php,/profile.php,/share.php,/plugins/likebox,/event.php,/video/video.php,/group.php',
                             'Twitter': 'facebook.com/,instagram.com/,pinterest.com/,twitter.com/intent/,twitter.com/home?status',
                             'Instagram': 'twitter.com/,pinterest.com/,facebook.com/,followgram.me/'}

UNWANTED_QUERY_PARAMS = {'Pinterest': '?',
                         'Facebook': '?',
                         'Twitter': '?',
                         'Instagram': '?'}


def find_duplicate_platforms(platform_name=None):
    """
    For each platform type, find the duplicates
    Ideally, we should have <influencer, platform_name> uniqueness
    """
    BLOG_PLATFORMS = ['Blogspot', 'Wordpress', 'Custom', 'Tumblr']
    SOCIAL_PLATFORMS = ['Facebook', 'Pinterest', 'Twitter', 'Instagram']
    PLATFORMS = BLOG_PLATFORMS + SOCIAL_PLATFORMS if not platform_name else [platform_name]
    infs1 = Influencer.objects.filter(source='spreadsheet_import', blog_url__isnull=False)
    infs2 = Influencer.objects.filter(shelf_user__userprofile__is_trendsetter=True)
    infs = infs1 | infs2

    for i,inf in enumerate(infs):
        print "Checking %d %s" % (i, inf)
        plats = inf.platforms()
        for pname in PLATFORMS:
            pp = plats.filter(platform_name=pname)
            if pp.count() == 0:
                print "no platform found for %s" % pname
            if pp.count() > 1:
                print "Duplicate found for %s" % pname
                for p in pp:
                    print p, p.url_not_found
        print "\n-----------\n"

@task(name='platformdatafetcher.platformcleanup.cleanup', ignore_result=True)
def cleanup(influencer_id):
    SOCIAL_PLATFORMS = ['Facebook', 'Pinterest', 'Twitter', 'Instagram']
    influencer = Influencer.objects.get(id=influencer_id)
    with platformutils.OpRecorder('cleanup', influencer=influencer) as opr:
        for pname in SOCIAL_PLATFORMS:
            try:
                _do_cleanup(influencer, pname)
            except:
                log.exception('While _do_cleanup(%r, %r)', influencer, pname)
                pass

def _do_cleanup(influencer, platform_name):
    print "\tCHECKING: %s" % platform_name
    all_platforms = influencer.platforms().filter(platform_name=platform_name).exclude(url_not_found=True).exclude(influencer__blog_url__isnull=True)
    platforms, platform_to_remove = remove_blacklisted_platforms(all_platforms, platform_name)
    if len(platforms) == 0:
        print "\t\tNo platforms exist"
        return
    else:
        print "Platforms: %s" % platforms
        blog_domain = utils.domain_from_url(influencer.blog_url).lower()
        print "\t\tBlog domain: %s" % blog_domain
        post_contains_domain = set()
        description_contains_domain = set()

        for plat in platforms:
            # let's first set the url_not_found to False for these candidates
            plat.url_not_found = False
            plat.save()
            update_url_if_redirected(plat.id, update=True)
            remove_qs_and_params(plat, update=True)
            ensure_url_is_valid(plat, update=True)

        if len(platforms) == 1:
            print "\t\tOnly 1 platform, not checking posts and descriptions"
            return

        for plat in platforms:
            if plat.api_calls == 0 and not Posts.objects.filter(platform=plat).exists():
                # make sure to fetch some information about the platform
                continue

            if check_posts(plat, [blog_domain, blog_domain.strip('blogspot.com'), blog_domain.strip('wordpress.com')]):
                post_contains_domain.add(plat)
            if check_description(plat, blog_domain) or check_description(plat, blog_domain.strip('blogspot.com')) or check_description(plat, blog_domain.strip('wordpress.com')):
                description_contains_domain.add(plat)
        print "\t\tpost_contains_domain: %s" % post_contains_domain
        print "\t\tdescription_contains_domain: %s" % description_contains_domain
        final = set()
        if len(post_contains_domain) > 0 and len(description_contains_domain) > 0:
            # pick the ones that are common between these two sets: high probability to be the correct one
            final = post_contains_domain.intersection(description_contains_domain)
            print "\t\t\tFINAL: %s" % final
        elif len(post_contains_domain) > 0:
            # next in priority: if the posts have a reference to the blog domain
            # this might not always be the case (especially for pinterest? instagram?)
            # perhaps we should look at the username/handle and check if it matches the blog_domain?
            print "\t\t\tFINAL: %s" % post_contains_domain
            final = post_contains_domain
        else:
            print "\t\t\tFINAL: %s" % description_contains_domain
            final = description_contains_domain
        # now we should run handle_duplicates()
        if len(final) > 0:
            set_url_not_found_field(all_platforms, final)
            final = handle_duplicates(list(final))
            print "\t\tRESULT: %s " % final
        else:
            print "\t\tno valid candidates exist"
            set_url_not_found_field(platform_to_remove, [])
            # handle duplicates anyway for each remaining candidate
            for pl in platforms:
                # make sure the object exists (as handle_duplicate for another platform can delete this)
                if Platform.objects.filter(id=pl.id).exists():
                    pl.handle_duplicates()

def set_url_not_found_field(all_platforms, skip_platforms):
    print "\t\t\tskip_platforms: %s " % skip_platforms
    skip_platform_ids = [skip.id for skip in skip_platforms]
    for plat in all_platforms:
        if plat.id in skip_platform_ids:
            continue
        print "\t\t\tsetting url_not_found for %s " % plat
        plat.url_not_found = True
        plat.save()

def remove_blacklisted_platforms(platforms, platform_name):
    """
    we trim the list by finding all platforms in this list that point to the blacklisted urls
    :param platforms: list of platforms
    :param platform_name: all these platforms are of the same platform_name

    we remove blacklisted platforms
    """
    blacklisted = BLACKLISTED_PLATFORM_URLS[platform_name].split(',')
    print "\t\t\tblacklisted url: %s" % blacklisted
    to_remove = set()
    result = set()
    for plat in platforms:
        bl = False
        for b in blacklisted:
            if b in plat.url:
                to_remove.add(plat)
                bl = True
                plat.url_not_found = True
                plat.save()
        if not bl:
            result.add(plat)
    if len(to_remove) > 0:
        print "\t\t\tWe'll remove: %s " % to_remove
    return result, to_remove


def remove_qs_and_params(plat, update=True):
    """
    basically we remove everything that is a query string
    param: plat is the platform
    param: update if True, we update the platform object
    """
    url = plat.url
    qs = UNWANTED_QUERY_PARAMS[plat.platform_name]
    loc = url.rfind(qs)
    new_url = url
    if loc > 1:
        new_url = url[:loc]
        if update:
            plat.url = new_url
            plat.save()
    if new_url != url:
        print "\t\t\tNew url: %s, old_url: %s" % (new_url, url)

def ensure_url_is_valid(plat, update=True):
    """
    Make sure the url is a valid one
    param: plat is the platform
    param: update if True, we update the platform object
    """
    url = plat.url
    new_url = url
    if not url.startswith('http'):
        new_url = 'http://' + url
    if update:
        if new_url != url:
            print "\t\t\tNew url: %s, old_url: %s" % (new_url, url)
            #plat.influencer.update_url_references(plat.url, new_url)
            plat.url = new_url
            plat.save()

def redetect_platform_name(plat, update=True):
    if not plat.url:
        return
    try:
        new_platform_name, corrected_url = fetcher.try_detect_platform_name(plat.url)
    except fetcherbase.FetcherException:
        log.exception('While redetect_platform_name, not updating platform_name')
        return
    if new_platform_name is None or corrected_url is None:
        log.warn('Unable to detect platform_name for url %r', plat.url)
        return
    log.info('Detected new platform_name and url for url %r: %r %r', plat.url, new_platform_name,
             corrected_url)
    if not update:
        return
    if plat.platform_name == new_platform_name and plat.url == corrected_url:
        log.info('Values are the same, not updating')
        return
    plat.platform_name = new_platform_name
    #plat.influencer.update_url_references(plat.url, corrected_url)
    plat.url = corrected_url
    plat.save()

def detect_user_level_redirect(url):
    """Detects blog redirects made not by HTTP status codes, but by pages
    requring clicking from a user. Returns a new url if a redirect is
    detected or the original url if not.
    """
    try:
        r = requests.get(url, timeout=10)
        #tree = lxml.html.fromstring(r.content)

        if "about to be redirected" in r.content:
            match = re.search(r'is\s+now\s+at\s+([^\s<]+)', r.content)
            if match:
                url = match.group(1)
                url = url.rstrip('.')
                return url

        return url
    except:
        log.exception('While detect_user_level_redirect')
        return url

def is_page_content_valid(content):
    """Detects removed, private blogs/social accounts
    """
    if not content:
        return True
    content = content.lower()
    tree = lxml.html.fromstring(content)
    if 'blogger.com' in content:
        h1_els = tree.xpath('//h1')
        h1_texts = ' '.join(h1.text or '' for h1 in h1_els)
        if 'blog has been removed' in h1_texts:
            return False
        if 'blog not found' in h1_texts:
            return False
    return True

@task(name='platformdatafetcher.platformcleanup.update_url_if_redirected', ignore_result=True)
def update_url_if_redirected(plat_id, update=False):
    """
    If the platform.url gets redirected to a new one, we should update the platform.url

    :param plat_id: is the platform id
    :param update: if True, we update the platform object
    """
    plat = Platform.objects.get(id=plat_id)
    with platformutils.OpRecorder(operation='update_url_if_redirected', platform=plat) as opr:
        try:
            resp = requests.get(plat.url)

            if is_page_content_valid(resp.text):
                log.info('Page content is valid')
            else:
                log.info('Invalid page content for %r, removing ADMIN_TABLE_INFLUENCER_INFORMATIONS',
                         plat)
                plat.influencer.remove_from_validated_on(
                    constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
                plat.influencer.save()
                opr.data = {'res': 'invalid_page_content'}
                return

            if resp.status_code != 200:
                log.warn('HTTP status code is not 200 for platform %r', plat)
                opr.data = {'res': 'invalid_status_code'}
                return
            new_url = resp.url
            if new_url == plat.url:
                new_url = detect_user_level_redirect(plat.url)
            if new_url != plat.url and new_url.rstrip('/') != plat.url.rstrip('/'):

                print "\t\t\tNew url: %s, old_url: %s" % (new_url, plat.url)
                opr.data = {'res': 'detected_redirection', 'new_url': new_url, 'old_url': plat.url}
                InfluencerCheck.report(plat.influencer, plat, InfluencerCheck.CAUSE_URL_CHANGED, [],
                                       'Old url: %r, new url: %r' % (plat.url, new_url))
                if update and new_url:
                    old_url = plat.url
                    #plat.influencer.update_url_references(old_url, new_url)
                    plat.url = new_url
                    plat.validated_handle = None
                    if plat.platform_name_is_blog:
                        redetect_platform_name(plat, update)
                    plat.save(bypass_checks=True)
                    plat.handle_duplicates()

                    # Update blog_urls also
                    infs_to_update = list(Influencer.objects.filter(blog_url=old_url))
                    print "\t\t\tUpdating influencer's blog_url: %r" % infs_to_update
                    for inf in infs_to_update:
                        assert inf.blog_url == old_url and inf.blog_url
                        inf.blog_url = new_url
                        inf.save(bypass_checks=True)
                        inf.handle_duplicates()

        except:
            log.exception('While checking redirect for %r', plat)
            # re-raise exception so it can be registered by OpRecorder
            raise

def handle_duplicates(platforms):
    plat = platforms[0]
    if Platform.objects.filter(id=plat.id).exists():
        return plat.handle_duplicates()
    return None

def check_posts(plat, keywords):
    """
    check if one of ``keywords`` appears in the posts for this platform
    return True if yes, else False
    """
    posts = Posts.objects.filter(platform=plat)
    if not posts.exists():
        return False

    for kw in keywords:
        if posts.filter(url__icontains=kw).exists():
            return True
        if posts.filter(content__icontains=kw).exists():
            return True

    # sometimes the post's content may contain shortened urls, e.g. http://t.co/ZJAoKM1TDZ that will re-direct
    # to a url that points to the blog
    ur = utils.URLResolver()
    for p in posts[:30]:
        urls = contentfiltering.re_find_urls(p.content)
        for u in urls:
            # ok, let's try to see if this re-directs
            try:
                new_url = ur.resolve(u)
                for kw in keywords:
                    if kw in new_url.lower():
                        return True
            except:
                pass
    return False


def check_description(plat, blog_domain):
    """
    check both platform.description and platform.about
    """
    return (plat.description and blog_domain in plat.description.lower()) or (plat.about and blog_domain in plat.about.lower())

DEAD_BLOG_TESTS_TO_BLACKLIST = 7
@task(name='platformdatafetcher.platformcleanup.detect_dead_blog', ignore_result=True)
def detect_dead_blog(influencer_id):
    inf = Influencer.objects.get(id=influencer_id)
    with platformutils.OpRecorder(operation='detect_dead_blog', influencer=inf) as opr:
        success = None
        data = {}
        try:
            r = requests.get(inf.blog_url, timeout=30)
        except:
            success = False
        else:
            success = r.status_code == 200
            data['status_code'] = r.status_code
        log.info('detect_dead_blog result for %r: %s', inf.blog_url, success)
        data['success'] = success

        previous_runs = inf.platformdataop_set.filter(operation='detect_dead_blog',
                                                      finished__isnull=False,
                                                      error_msg__isnull=True).order_by('-finished')\
                                                     [:DEAD_BLOG_TESTS_TO_BLACKLIST - 1]
        if len(previous_runs) < DEAD_BLOG_TESTS_TO_BLACKLIST - 1:
            log.info('Not enough previous ops to check if should be disabled')
        else:
            recent_successes = [success] + [json.loads(pdo.data_json)['success'] for pdo in previous_runs]
            if all(x == False for x in recent_successes):
                log.warn('%d consecetive failures, blacklisting %r', DEAD_BLOG_TESTS_TO_BLACKLIST, inf)
                inf.blacklisted = True
                inf.save()
                data['blacklisted'] = True

        opr.data = data

@task(name='platformdatafetcher.platformcleanup.run_handle_duplicates_for_influencer', ignore_result=True)
def run_handle_duplicates_for_influencer(influencer_id):
    influencer = Influencer.objects.get(id=influencer_id)
    with platformutils.OpRecorder(operation='handle_inf_duplicates', influencer=influencer) as opr:
        dups = Influencer.find_duplicates(influencer.blog_url, influencer.id)
        if dups:
            log.info('Found %d duplicates, running handle_duplicates')
            influencer.handle_duplicates()
        else:
            log.info('No duplicates found')


SQL_PLATFORM_IDS_WITH_FETCH_ERRORS = """
select pl.id
from debra_platform pl
join debra_influencer inf on pl.influencer_id=inf.id
where (select count(*) from debra_platformdataop pdo where pdo.platform_id=pl.id and operation='fetch_data' and error_msg is not null) >= 5
and not exists(select * from debra_platformdataop pdo where pdo.platform_id=pl.id and operation='fetch_data' and error_msg is null)
and (pl.url_not_found is null or pl.url_not_found=false)
and pl.platform_name <> 'Instagram'
"""

def blacklist_platforms_with_fetch_errors():
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute(SQL_PLATFORM_IDS_WITH_FETCH_ERRORS)
    log.info('%d plats to blacklist', cur.rowcount)
    for plat_id, in cur:
        plat = Platform.objects.get(id=plat_id)
        with platformutils.OpRecorder(operation='blacklist_platforms_with_fetch_errors',
                                      platform=plat) as opr:
            log.info('Blacklisting platform %r', plat)
            plat.url_not_found = True
            plat.save()

