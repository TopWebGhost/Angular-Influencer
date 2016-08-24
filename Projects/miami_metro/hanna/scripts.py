__author__ = 'atulsingh'

import csv
import baker
import pprint
from collections import defaultdict, OrderedDict
from debra.models import Platform, Influencer, Posts, PostInteractions
from debra.models import Follower, PopularityTimeSeries, ProductsInPosts, InfluencerCheck
from debra import models
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from pyvirtualdisplay import Display
from django.conf import settings
from django.db.models import Q
from xpathscraper import utils
from platformdatafetcher.platformextractor import extract_platforms_from_platform
from platformdatafetcher import fetcher
from platformdatafetcher import platformutils
from debra import db_util
from debra import constants
from debra import helpers
import os.path
import logging
import glob
import requests
import datetime
import urlparse
import json


log = logging.getLogger('hanna.scripts')


########################################################################################################################
#   Methods to check consistency of our influencer database                                                            #
########################################################################################################################
def count_influencers_with_empty_blogurl():
    empty = Influencer.objects.filter(blog_url__isnull=True)
    print "Found %d entries having no blog url in influencer table" % empty.count()
    return empty.count()


def count_and_find_duplicate_influencers():
    # counts and returns influencers that have multiple entries
    all_infs = Influencer.objects.filter(blog_url__isnull=False)
    count = 0
    dups = set()
    for inf in all_infs:
        if Influencer.objects.filter(blog_url=inf.blog_url).count() > 1:
            count += 1
            dups.add(inf.id)
    print "Found %d duplicates in %d influencers." % (count, Influencer.objects.count())
    return count, dups


def count_and_find_duplicate_platforms():
    all_plats = Platform.objects.all()
    count = 0
    dups = set()
    for plat in all_plats:
        if Platform.objects.filter(url=plat.url).count() > 1:
            dups.add(plat.id)
            count += 1
    return count, dups


def check_platform_influencer_are_unique_pairs():
    all_infs = Influencer.objects.all()
    problematic_infs = set()
    for inf in all_infs:
        plat = Platform.objects.get(inf.blog_url)
        if plat.influencer.id != inf.id:
            problematic_infs.add(inf.id)


def check_dangling_platforms():
    # find platforms that do not have any influencer FK
    return Platform.objects.filter(influencer__isnull=True).count()


def check_health_of_influencer_db():
    count_influencers_with_empty_blogurl()
    count_and_find_duplicate_influencers() # only one influencer per domain
    count_and_find_duplicate_platforms()  # only one platform per domain (for blogs) or per username (for social platform)
    check_platform_influencer_are_unique_pairs() # 1:1 mapping between influencers and platforms
    check_dangling_platforms() # no influencer points to them


def delete_all_platforms():
    plats = Platform.objects.all()
    posts = Posts.objects.all()
    interactions = PostInteractions.objects.all()
    followers = Follower.objects.all()
    popularity = PopularityTimeSeries.objects.all()
    prods = ProductsInPosts.objects.all()

    interactions.delete()
    print "Deleted all interactions"
    posts.delete()
    print "Deleted all posts"
    plats.delete()
    print "Deleted all platforms"
    followers.delete()
    print "Deleted all followers"
    popularity.delete()
    print "Deleted all popularity data"
    prods.delete()
    print "Deleted all prod imports data"


########################################################################################################################
#   Methods to find blog url from a given bloglovin url                                                                #
########################################################################################################################
def _get_driver():
    display = None
    if not settings.DEBUG:
        display = Display(visible=0, size=(800, 600))
        display.start()
    driver = webdriver.Firefox()
    return (driver, display)


def _close_driver(driver, display):
    driver.quit()
    if display:
        display.stop()


def _wait_for_element(driver, path, timetowait=None):
    '''
    blocks for the element for 10 seconds, returns True if found (will return as soon as element found)
    '''
    if not timetowait:
        timetowait = 120
    try:
        WebDriverWait(driver, timetowait, poll_frequency=0.05).until(lambda d: driver.find_element_by_xpath(path))
        return True
    except:
        print "Not loaded yet %s in url " % (path)
        pass
        return False


def get_blog_url_from_bloglovin_url(bloglovin_url):
    print "get_blog_url_from_blogloginv_url(%s)" % bloglovin_url
    driver, display = _get_driver()
    driver.get(bloglovin_url)
    driver.refresh()
    _wait_for_element(driver, '//div[contains(@class,"gl-profile-link")]/a')
    elems = driver.find_elements_by_xpath('//div[contains(@class,"gl-profile-link")]/a')
    found_url = None
    if len(elems) > 0:
        found_url = elems[0].text.encode("utf-8", "ignore")
        print "[Using first location] Found blog url: %s " % found_url
    else:
        _wait_for_element(driver, '//div[contains(@class, "user-profile-blogs")]//h2[@class="gl-blog-title"]/span[@class="url"]')
        elems = driver.find_elements_by_xpath('//div[contains(@class, "user-profile-blogs")]//h2[@class="gl-blog-title"]/span[@class="url"]')
        if len(elems) == 0:
            found_url = elems[0].text.encode("utf-8", "ignore")
            print "[Using second location] Found blog url: %s " % found_url

    _close_driver(driver, display)
    return found_url


def fetch_social_handlers():
    platforms = Platform.objects.all()
    for p in platforms:
        print "Extracting from {blogurl}".format(blogurl=p.url)
        platforms = extract_platforms_from_platform(p.id, to_save=True)
        print "Got %s platforms " % len(platforms)
        for p in platforms:
            print p
        print "\n\n\n"


def spreadsheet_reader(filename):
    with open(filename, 'rb') as f:
        lines = f.readlines()
    reader = csv.DictReader(lines, ('note', 'blogger_name', 'url', 'email', 'extra_contact1', 'extra_contact2', 'contact_form_url', 'blog_name', 'source',
                                    'gender', 'Facebook',
                                'Twitter', 'Extra_Twitter', 'Pinterest', 'Bloglovin', 'Instagram', 'Extra_Instagram', 'location', 'description'))
    return reader


@baker.command
def set_source_spreadsheet(filename):
    reader = spreadsheet_reader(filename)
    for row in reader:
        duplicate_infs = Influencer.find_duplicates(blog_url=row['url'])
        if len(duplicate_infs) > 0:
            inf = duplicate_infs[0]
            if inf.source == 'spreadsheet_import':
                print 'Influencer %s has source set to spreadsheet_import' % inf
            else:
                inf.source = 'spreadsheet_import'
                inf.save()
                print 'Updated influencer %s source to spreadsheet_import' % inf
        else:
            print '!!! No influencers for blog_url=%s' % row['url']


@baker.command
def create_influencers_platforms_from_csv(filename, from_row='1', to_row='999999'):
    """Works with https://docs.google.com/spreadsheet/ccc?key=0Ai2GPRwzn6lmdEMzWVR0aldXYXJodGplZlVGRVMyQ1E&usp=sharing . To download CSV, add output=csv to the link: https://docs.google.com/spreadsheet/ccc?key=0Ai2GPRwzn6lmdEMzWVR0aldXYXJodGplZlVGRVMyQ1E&usp=sharing&output=csv
    """
    reader = spreadsheet_reader(filename)
    count = 0
    from_row = int(from_row)
    to_row = int(to_row)
    for row in reader:
        print "\n\nCount: %d" % count
        count += 1
        if count < from_row:
            print 'Skipping row %d' % count
            continue
        if count > to_row:
            print 'Skipping row %d' % count
            continue
        if row['email'] == 'email':
            # First title row
            continue
        if not (row['url'] or '').strip():
            # Empty row
            continue
        print 'Processing row %r' % row
        duplicate_infs = Influencer.find_duplicates(blog_url=row['url'])
        if len(duplicate_infs) > 0:
            inf = duplicate_infs[0]
            inf.handle_duplicates()
            print 'Using already saved influencer: %r' % inf
        else:
            inf = Influencer()
        #update info
        inf.source = 'spreadsheet_import'
        inf.name = row['blogger_name']
        inf.blog_url = row['url']
        inf.email = row['email']
        inf.demographics_location = row['location']
        inf.demographics_gender = row['gender']
        assert False, 'This script requires code update to *_url fields processing'
        if row['Facebook']:
            inf.fb_url = row['Facebook']
        if row['Pinterest']:
            inf.pin_url = row['Pinterest']
        if row['Twitter']:
            inf.tw_url = row['Twitter']
        if row['Instagram']:
            inf.insta_url = row['Instagram']
        if row['Bloglovin']:
            inf.bloglovin_url = row['Bloglovin']
        inf.save()
        print 'Saved new influencer: %r' % inf

        # Try to save blog as platform
        if row['url']:
            blog_pl = Platform.objects.filter(url=row['url'])
            if blog_pl.exists():
                print "Blog already exists for url %s [%s]" % (row['url'], blog_pl)
            else:
                discovered_pl, corrected_url = fetcher.try_detect_platform_name(row['url'])
                if discovered_pl:
                    blog_pl = Platform.find_duplicates(inf, row['url'], discovered_pl)
                    if blog_pl and len(blog_pl) > 0:
                        blog_pl = blog_pl[0]
                        blog_pl = blog_pl.handle_duplicates()
                    else:
                        blog_pl = Platform()
                    blog_pl.influencer = inf
                    blog_pl.platform_name = discovered_pl
                    blog_pl.url = row['url']
                    blog_pl.blogname = row['blog_name']
                    blog_pl.save()
                    print 'Saved platform from blog data: %r' % blog_pl
                else:
                    print 'No platform discovered for blog url %r' % row['url']

        for platform_name in ('Facebook', 'Twitter', 'Pinterest', 'Bloglovin', 'Instagram'):
            if not row[platform_name]:
                print 'No url for platform %r' % platform_name
                continue
            pl = Platform.find_duplicates(inf, row[platform_name], platform_name)
            if pl and len(pl) > 0:
                pl = pl[0]
                pl = pl.handle_duplicates()
            else:
                pl = Platform()
            pl.influencer = inf
            pl.platform_name = platform_name
            pl.url = row[platform_name]
            pl.save()
            print 'Saved new platform %r' % pl


@baker.command
def redetect_blog_platforms_for_spreadsheet_import():
    infs = Influencer.objects.filter(source='spreadsheet_import',
                                     blog_url__isnull=False)
    infs_count = infs.count()
    print 'Looking at %s influencers' % infs_count
    discovered = []
    not_discovered = []
    for i, inf in enumerate(infs):
        print 'Processing %s/%s' % (i + 1, infs_count)
        if not inf.platform_set.filter(platform_name__in=['Custom', 'Blogspot', 'Wordpress']).exists():
            print '!!! No blog platform for influencer blog_url %r influencer %r' % (inf.blog_url, inf)
            try:
                discovered_pl, corrected_url = fetcher.try_detect_platform_name(inf.blog_url)
            except Exception as e:
                print 'Exception %r while try_detect_platform_name' % e
                continue
            if discovered_pl:
                blog_pl = Platform.find_duplicates(inf, inf.blog_url, discovered_pl)
                if blog_pl and len(blog_pl) > 0:
                    blog_pl = blog_pl[0]
                else:
                    blog_pl = Platform()
                blog_pl.influencer = inf
                blog_pl.platform_name = discovered_pl
                blog_pl.url = inf.blog_url
                blog_pl.save()
                print '+++ Saved platform from blog data: %r' % blog_pl
                discovered.append(blog_pl)
                print '\n', len(discovered), discovered, '\n'
            else:
                print '--- No platform discovered'
                not_discovered.append(inf.blog_url)
                print '\n', len(not_discovered), not_discovered, '\n'


def _master_domain(domain):
    if not domain or '.' not in domain:
        return domain
    parts = domain.split('.')
    if domain.endswith('co.uk'):
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


@baker.command
def influencers_without_blog_platform_by_domain():
    infs = Influencer.objects.filter(source='spreadsheet_import',
                                     blog_url__isnull=False)
    invalid_urls = []
    for i, inf in enumerate(infs):
        print i
        if not inf.platform_set.filter(platform_name__in=['Custom', 'Blogspot', 'Wordpress']).exists():
            invalid_urls.append(inf.blog_url)

    print 'Got %s invalid urls: %r' % (len(invalid_urls), invalid_urls)
    by_domain = defaultdict(list)
    for url in invalid_urls:
        by_domain[_master_domain(utils.domain_from_url(url))].append(url)
    by_domain_items = sorted(by_domain.items(), key=lambda (domain, urls): len(urls), reverse=True)
    pprint.pprint(by_domain_items)


def find_duplicate_blog_posts():
    infs1 = Influencer.objects.filter(source='spreadsheet_import', blog_url__isnull=False)
    infs2 = Influencer.objects.filter(shelf_user__userprofile__is_trendsetter=True)
    infs = infs1 | infs2

    BLOG_PLATFORMS = ['Blogspot', 'Wordpress', 'Custom']
    posts = Posts.objects.filter(influencer__in=infs, platform__platform_name__in=BLOG_PLATFORMS).order_by('id')
    print "We have %d posts " % posts.count()
    post_urls = set()
    for i, p in enumerate(posts):
        post_urls.add(p.url)
        print i

    duplicates = set()
    for url in post_urls:
        if posts.filter(url=url).count() > 1:
            duplicates.add(url)

    print "Found %d number of duplicate posts " % len(duplicates)


@baker.command
def find_influencers_with_multiple_blogs():
    res = []
    infs = Influencer.objects.filter(show_on_search=True).prefetch_related('platform_set')
    for inf in infs:
        blog_plats = list(inf.platform_set.filter(platform_name__in=Platform.BLOG_PLATFORMS).
                                            exclude(url_not_found=True))
        if len(blog_plats) >= 2:
            log.info('Influencer %r has %d blog platforms: %r' % (inf, len(blog_plats), blog_plats))
            res.append(inf)
    return res


@baker.command
def find_influencer_duplicates():
    res = []
    infs = Influencer.objects.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED).exclude(blacklisted=True)
    for inf in infs:
        dups = Influencer.find_duplicates(inf.blog_url, inf.id)
        if dups:
            log.info('YES_DUP %s %r %r', inf.id, inf, dups)
            res.append(inf)
        else:
            log.info('NO_DUP %s %r', inf.id, inf)
    log.info('Total duplicates: %s', len(res))
    pprint.pprint(res)
    return res


@baker.command
def handle_influencer_duplicates(typ):
    assert typ in ('validated', 'non_validated')
    if typ == 'validated':
        infs = Influencer.objects.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED).exclude(blacklisted=True)
    elif typ == 'non_validated':
        infs = Influencer.objects.exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED).exclude(blacklisted=True).exclude(source__isnull=True).exclude(blog_url__isnull=True).exclude(blog_url='')
    else:
        assert False

    infs_count = infs.count()
    log.info('Handling duplicates for %r infs', infs_count)

    for i, inf in enumerate(infs.iterator()):
        log.info('Processing %d/%d %r', i + 1, infs_count, inf)
        try:
            if Influencer.find_duplicates(inf.blog_url, inf.id):
                    inf.handle_duplicates()
        except:
            log.exception('While handling duplicates for %r, skipping', inf)


@baker.command
def submit_run_handle_duplicates_for_influencer_tasks(typ):
    from platformdatafetcher import platformcleanup

    assert typ in ('validated', 'non_validated')
    if typ == 'validated':
        infs = Influencer.objects.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED).exclude(blacklisted=True)
    elif typ == 'non_validated':
        infs = Influencer.objects.exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED).exclude(blacklisted=True).exclude(source__isnull=True).exclude(blog_url__isnull=True).exclude(blog_url='')
    else:
        assert False

    infs_count = infs.count()
    log.info('Handling duplicates for %r infs', infs_count)

    for i, inf in enumerate(infs.iterator()):
        log.info('Submitting %d/%d %r', i + 1, infs_count, inf)
        platformcleanup.run_handle_duplicates_for_influencer.apply_async([inf.id], queue='duplicate_handling')


@baker.command
def handle_influencer_duplicates_with_checks(max_id=999999):
    influencers = Influencer.objects.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED).exclude(blacklisted=True).filter(id__lte=int(max_id)).order_by('-id')
    for influencer in influencers:
        dups = Influencer.find_duplicates(influencer.blog_url)
        if len(dups) in (0, 1):
            log.info('OK %r', influencer)
            continue
        log.info('%d dups for %r', len(dups), influencer)

        before_with_shelf_user = [inf for inf in dups if inf.shelf_user is not None]
        valid_platform_names_in_dups = {plat.platform_name
                                        for inf in dups
                                        for plat in inf.platform_set.exclude(url_not_found=True)}

        # run de-duplication
        selected = influencer.handle_duplicates()
        log.info('Selected: %r', selected)

        not_selected = [inf for inf in dups if inf.id != selected.id]
        assert len(not_selected) == len(dups) - 1

        # refresh old dups objects and selected
        dups = [Influencer.objects.get(id=inf.id) for inf in dups]
        selected = Influencer.objects.get(id=selected.id)

        after_with_shelf_user = [inf for inf in dups if inf.shelf_user is not None]
        log.info('before/after with_shelf_user: %d %d', len(before_with_shelf_user),
                                                        len(after_with_shelf_user))
        assert len(before_with_shelf_user) <= len(after_with_shelf_user)

        valid_platform_names_in_selected = {plat.platform_name
                                            for plat in selected.platform_set.exclude(url_not_found=True)}
        log.info('platform_names in dups/selected: %s %s', valid_platform_names_in_dups,
                 valid_platform_names_in_selected)
        assert valid_platform_names_in_dups == valid_platform_names_in_selected

        not_selected_validated = [inf for inf in not_selected if not inf.is_enabled_for_automated_edits()]
        log.info('Not selected validated: %s', not_selected_validated)
        # if selected is not validated, check if we are not disabling validated
        if selected.is_enabled_for_automated_edits():
            assert not not_selected_validated


@baker.command
def disable_duplicate_blog_platforms(inf_id):
    from platformdatafetcher import platformutils
    from platformdatafetcher import platformcleanup

    inf = models.Influencer.objects.get(id=int(inf_id))
    with platformutils.OpRecorder(operation='disable_duplicate_blog_platforms', influencer=inf):
        blog_plats = list(inf.platform_set.filter(platform_name__in=Platform.BLOG_PLATFORMS).
                                            exclude(url_not_found=True))
        assert len(blog_plats) >= 2, 'No blog duplicates'
        for plat in blog_plats:
            log.info('Calling handle_duplicates on %r' % plat)
            if plat.url_not_found:
                log.info('Platform has url_not_found set to true')
                continue
            plat.handle_duplicates(True)
            platformcleanup.redetect_platform_name(plat)
        inf.remove_from_validated_on(constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
        inf.save()


@baker.command
def run_disable_duplicate_blog_platforms():
    infs = find_influencers_with_multiple_blogs()
    log.info('%d Influencers with duplicated blogs: %r' % (len(infs), infs))
    for i, inf in enumerate(infs):
        log.info('Processing %d/%d' % (i, len(infs)))
        disable_duplicate_blog_platforms(inf.id)


@baker.command
def resolve_tco_urls():
    """Try to resolve t.co urls. If an error happens (404 usually), delete the platform
    """
    from platformdatafetcher import platformcleanup

    plats = models.Platform.objects.filter(influencer__show_on_search=True,
                                           url__icontains='t.co/')
    plats = list(plats)
    log.info('Processing plats (%d): %r', len(plats), plats)
    for plat in plats:
        try:
            platformcleanup.update_url_if_redirected(plat.id)
        except:
            log.warn('Deleting platform %r', plat)
            plat.delete()
        else:
            log.warn('Leaving platform %r', plat)


@baker.command
def migrate_pts_from_duplicates():
    infs = Influencer.objects.filter(show_on_search=True)
    plats = Platform.objects.filter(influencer__in=infs).exclude(url_not_found=True)
    for plat in plats:
        log.info('plat: %r', plat)
        plat_ptss = list(plat.popularitytimeseries_set.order_by('snapshot_date'))
        log.info('plat_ptss: %s', plat_ptss)
        plat_dates = {pts.snapshot_date for pts in plat_ptss}
        dups = Platform.find_duplicates(plat.influencer, plat.url, plat.platform_name, plat.id,
                                        exclude_url_not_found_true=False)
        if not dups:
            log.info('No dups')
            continue
        for dup in dups:
            log.info('dup: %r', dup)
            dup_ptss = list(dup.popularitytimeseries_set.order_by('snapshot_date'))
            log.info('dup_ptss: %s', dup_ptss)
            for pts in dup_ptss:
                if pts.snapshot_date in plat_dates:
                    log.info('Skipping existing pts %r', pts)
                    continue
                pts.platform = plat
                pts.save()
                log.info('Migrated pts: %r', pts)


@baker.command
def call_posts_denormalize():
    infs = Influencer.objects.filter(show_on_search=True)
    plats = Platform.objects.filter(influencer__in=infs).exclude(url_not_found=True)
    plats_count = plats.count()
    for i, plat in enumerate(plats.iterator()):
        print 'Processing %r %d/%d %d posts' % (plat, i + 1, plats_count, plat.posts_set.all().count())
        for post in plat.posts_set.all():
            try:
                post.denormalize()
            except:
                log.exception('While post.denormalize() for %r', plat)


@baker.command
def delete_influencers_with_source_comments_content_import_and_0_posts():
    infs = Influencer.objects.not_active().filter(source='comments_content_import').\
        exclude(relevant_to_fashion=True).\
        exclude(show_on_search=True)
    log.info('%d infs', infs.count())
    for i, inf in enumerate(infs):
        log.info('%d %r', i, inf)
        posts = Posts.objects.filter(influencer=inf)
        if not posts.exists():
            log.info('Deleting influencer %r', inf)
            inf.delete()


@baker.command
def products_from_posts_test_data():
    infs = Influencer.objects.filter(show_on_search=True).order_by('-score_popularity_overall')[:100]
    data = []
    for inf in infs:
        posts = inf.posts_set.filter(products_import_completed=True).\
            order_by('-create_date')[:2]
        for post in posts:
            row = OrderedDict(post_url=post.url)
            pmsms = post.productmodelshelfmap_set.select_related('product_model').order_by('id')
            pms = [pmsm.product_model for pmsm in pmsms]
            for i, pm in enumerate(pms):
                row['product_url_%d' % i] = pm.prod_url
                row['price_%d' % i] = pm.price
                row['img_url_%d' % i] = pm.img_url
            data.append(row)
    with open('products_from_posts_test_data.csv', 'w') as f:
        writer = csv.writer(f)
        for row in data:
            writer.writerow(row.values())


@baker.command
def import_network_bloggers(filename):

    with open(filename, 'rb') as f:
        lines = f.readlines()[1:]
    reader = csv.DictReader(lines, ('unusual', 'blog_name', 'url', 'persons_name', 'location', 'source',
                                   'description'))
    blogger_type = os.path.basename(filename).split('.')[0].split(' - ')[1]
    log.info('blogger_type: %r', blogger_type)
    for row in reader:
        try:
            log.info('row: %r', row)
            if not row['url'].startswith('http'):
                log.warn('Skipping row with invalid url %r', row['url'])
                continue
            source = utils.domain_from_url(row['source'])
            if not source.strip():
                log.warn('Skipping row with no source')
                continue
            if not row['url'].strip():
                log.warn('Skipping row with no url')
                continue
            inf = helpers.create_influencer_and_blog_platform(row['url'], source, to_save=True, platform_name_fallback=True)
            if not inf:
                log.warn('Skipping blacklisted url')
                continue
            if not inf.is_enabled_for_automated_edits():
                log.warn('Influencer is not enabled for automated edits, skipping')
                continue
            inf.blogname = row['blog_name']
            inf.blogger_type = blogger_type
            inf.name = row['persons_name']
            inf.demographics_location = row['location']
            inf.description = row['description']
            log.info('source, blogname, name, location, description: %r, %r, %r, %r, %r',
                     inf.source, inf.blogname, inf.name, inf.demographics_location, inf.description[:100])
            inf.save()

            # update blogname for blog platform
            blog_pl_q = inf.platform_set.filter(url=row['url'])
            if blog_pl_q.exists():
                blog_pl = blog_pl_q[0]
                log.info('Updating blogname of %r', blog_pl)
                blog_pl.blogname = row['blog_name']
                blog_pl.save()
        except:
            log.exception('While processing %s, skipping', row)


@baker.command
def import_network_bloggers_all():
    hanna = os.path.dirname(os.path.realpath(__file__))
    files = glob.glob(os.path.join(hanna, '../debra/csvs/network_bloggers/*.csv'))
    for f in files:
        import_network_bloggers(f)


@baker.command
def handle_blacklisted_from_blogger_signup():
    infs = models.Influencer.objects.filter(userprofile__isnull=False,
                                            source__icontains='blogger_signup',
                                            blacklisted=True)
    print 'Processing %d infs' % infs.count()
    for inf in infs:
        inf.blacklisted = False
        inf.save()
        inf.handle_duplicates()


@baker.command
def restore_blacklisted_validated():
    infs = Influencer.objects.filter(blacklisted=True, validated_on__icontains='info').exclude(show_on_search=True)
    log.info('%d infs will be restored', infs.count())
    for inf in infs:
        log.info('Processing %r', inf)
        inf.blacklisted = False
        inf.save()
        inf.handle_duplicates()


def _non_existing_blog(blog_url):
    try:
        r = requests.get(blog_url, timeout=10)
    except:
        return True
    return r.status_code != 200


def _redirect_to_the_other_detected(source_url, possible_target_url):
    from platformdatafetcher import platformutils

    try:
        r = requests.get(source_url, timeout=10)
    except:
        return False
    return platformutils.url_to_handle(r.url) == \
           platformutils.url_to_handle(possible_target_url)


def _similar_blog_platform_content(inf1, inf2):
    bp1 = inf1.blog_platform
    bp2 = inf2.blog_platform
    if not bp1 or not bp2:
        log.info('No blog platform')
        return False
    since = datetime.datetime.now() - datetime.timedelta(days=90)
    uq1 = bp1.posts_set.filter(create_date__gte=since).values('url')
    uq2 = bp2.posts_set.filter(create_date__gte=since).values('url')
    urls1 = [d['url'] for d in uq1]
    urls2 = [d['url'] for d in uq2]
    log.debug('urls1: %d urls2: %d', urls1, urls2)
    same_urls = set(urls1) & set(urls2)
    if same_urls:
        log.info('Same post urls: %s', same_urls)
        return True
    return False


def _handle_post_url(inf, to_save):
    path = urlparse.urlsplit(inf.blog_url).path.rstrip('/')
    if not path:
        return False
    try:
        dres = fetcher.try_detect_platform_name(inf.blog_url)
        if dres is None:
            return False
        platform_name, corrected_url = dres
        if platform_name is None:
            return False
        if platform_name not in ('Blogspot', 'Wordpress'):
            return False
        if to_save:
            with platformutils.OpRecorder(operation='dup_pair.handle_post_url', influencer=inf) as opr:
                orig_parsed = urlparse.urlsplit(inf.blog_url)
                new_parsed = orig_parsed._replace(path='')
                new_url = urlparse.urlunsplit(new_parsed)
                opr.data = {'orig_url': inf.blog_url, 'new_url': new_url}
                helpers.update_blog_url(inf, new_url)
                inf.handle_duplicates()
        return True
    except:
        log.exception('While handle_post_url')
    return False


def _handle_dup_pair(inf1_id, inf2_id, to_save=False):
    inf1 = models.Influencer.objects.get(id=inf1_id)
    inf2 = models.Influencer.objects.get(id=inf2_id)

    if inf1.source is None or inf2.source is None:
        log.warn('RES: already handled duplicates')
        return

    log.info('Processing dup pair %r, %r', inf1, inf2)

    #if _non_existing_blog(inf1.blog_url):
    #    log.info('RES: Non existing %r', inf1)
    #    if to_save:
    #        with platformutils.OpRecorder(operation='dup_pair.disable_influencer', influencer=inf1) as opr:
    #            inf1.blacklisted = True
    #            inf1.save()
    #            opr.data = {'reason': 'Invalid blog url %r' % inf1.blog_url}
    #    return
    #if _non_existing_blog(inf2.blog_url):
    #    log.info('RES: Non existing %r', inf2)
    #    if to_save:
    #        with platformutils.OpRecorder(operation='dup_pair.disable_influencer', influencer=inf2) as opr:
    #            inf2.blacklisted = True
    #            inf2.save()
    #            opr.data = {'reason': 'Invalid blog url %r' % inf2.blog_url}
    #    return
    if _redirect_to_the_other_detected(inf1.blog_url, inf2.blog_url):
        log.info('RES: Redirect')
        log.info('Redirect from %r to %r', inf1, inf2)
        if to_save:
            with platformutils.OpRecorder(operation='dup_pair.redirect_between_duplicates', influencer=inf1) as opr:
                opr.data = {'source_url': inf1.blog_url, 'target_url': inf2.blog_url,
                            'target_influencer_id': inf2.id}
                helpers.update_blog_url(inf1, inf2.blog_url)
                inf1.handle_duplicates()
        return
    if _redirect_to_the_other_detected(inf2.blog_url, inf1.blog_url):
        log.info('RES: Redirect')
        log.info('Redirect from %r to %r', inf2, inf1)
        if to_save:
            with platformutils.OpRecorder(operation='dup_pair.redirect_between_duplicates', influencer=inf2) as opr:
                opr.data = {'source_url': inf2.blog_url, 'target_url': inf1.blog_url,
                            'target_influencer_id': inf1.id}
                helpers.update_blog_url(inf2, inf1.blog_url)
                inf2.handle_duplicates()
        return
    if _similar_blog_platform_content(inf1, inf2):
        purl1 = _handle_post_url(inf1, to_save)
        purl2 = _handle_post_url(inf2, to_save)
        if purl1 or purl2:
            log.info('Automatically handled post urls')
            log.info('RES: Post urls handled')
        else:
            log.info('Not post urls but similar content, inserting IC only')
            log.info('RES: Similar blog content')
            if to_save:
                InfluencerCheck.report_new(inf1, None, InfluencerCheck.CAUSE_SUSPECT_SIMILAR_CONTENT, [],
                                       'Other influencer: %r' % inf2,
                                       {'related': [['Influencer', inf2.id]]})
        return
    log.info('RES: Found nothing for this pair')
    if to_save:
        InfluencerCheck.report_new(inf1, None, InfluencerCheck.CAUSE_SUSPECT_SIMILAR_BLOG_URLS, [],
                               'Other influencer: %r' % inf2,
                               {'related': [['Influencer', inf2.id]]})


@baker.command
def fix_duplicates_by_social_platform():
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
select distinct inf1.id, inf2.id
from debra_platform pl1, debra_platform pl2, debra_influencer inf1, debra_influencer inf2
where pl1.url = pl2.url
and pl1.url <> ''
and pl1.id < pl2.id
and pl1.url_not_found=false
and pl2.url_not_found=false
and pl1.platform_name in ('Facebook', 'Twitter', 'Instagram', 'Pinterest')
and pl2.platform_name = pl1.platform_name
and inf1.id=pl1.influencer_id
and inf2.id=pl2.influencer_id
and inf1.blacklisted=false and inf1.source is not null and inf1.validated_on like '%%info%%'
                and inf1.show_on_search=true and  {inf1_active}
and inf2.blacklisted=false and inf2.source is not null and inf2.validated_on like '%%info%%' and inf2.show_on_search=true
                and {inf2_active}
    """.format(inf1_active=models.InfluencerQuerySet.active_sql('inf1'),
                   inf2_active=models.InfluencerQuerySet.active_sql('inf2')))
    log.info('Fetching %d duplicate pairs', cur.rowcount)
    for inf1_id, inf2_id in cur:
        _handle_dup_pair(inf1_id, inf2_id)


@baker.command
def fix_redirect_between_duplicates():
    pdos = models.PlatformDataOp.objects.filter(operation='dup_pair.redirect_between_duplicates')
    for pdo in pdos:
        data = json.loads(pdo.data_json)
        if not pdo.influencer.platform_set.filter(url=data['target_url']).exists():
            log.info('Issuing blog_url update for %r', pdo.influencer)
            pdo.influencer.blog_url = data['source_url']
            pdo.influencer.save()
            matching = helpers.update_blog_url(pdo.influencer, data['target_url'])
            if matching > 0:
                assert pdo.influencer.platform_set.filter(url=data['target_url']).exists()
        else:
            log.info('Target platform already exists for %r', pdo.influencer)


@baker.command
def submit_process_new_influencer_tasks_for_null_relevant_to_fashion():
    from platformdatafetcher import postprocessing
    from platformdatafetcher.platformutils import exclude_influencers_disabled_for_automated_edits

    infs = models.Influencer.objects.filter(source='blogger_signup',
                                            relevant_to_fashion__isnull=True)
    infs = exclude_influencers_disabled_for_automated_edits(infs)
    log.info('%d infs to process in new_influencer', infs.count())
    for inf in infs:
        postprocessing.process_new_influencer_sequentially.apply_async([inf.id], queue='new_influencer')


@baker.command
def blacklist_t_co_influencers():
    from platformdatafetcher.platformutils import exclude_influencers_disabled_for_automated_edits

    infs = models.Influencer.objects.filter(Q(blog_url__startswith='https://t.co/') |
                                                Q(blog_url__startswith='http://t.co/'),
                                            source__isnull=False,
                                            blacklisted=False)
    infs = exclude_influencers_disabled_for_automated_edits(infs)
    log.info('%d infs to blacklist', infs.count())
    for inf in infs:
        log.info('Processing %r', inf)
        inf.set_blacklist_with_reason('bad_url')
        inf.save()


@baker.command
def reset_url_not_found_for_validated_instagram_platforms_with_api_error():
    connection = db_util.connection_for_writing()
    cur = connection.cursor()
    cur.execute("""
    update debra_platform set url_not_found=null where id in
    (
        select pl.id
        from debra_platformdataop pdo
        join debra_platform pl on pdo.platform_id=pl.id
        join debra_influencer inf on pl.influencer_id=inf.id
        where inf.validated_on like '%info%'
        and pdo.operation='fetch_data'
        and pl.platform_name='Instagram'
        and pl.url_not_found=true
        and error_msg like '%Instagram%'
    );
    """)


@baker.command
def process_sequentially_google_and_network_bloggers():
    from platformdatafetcher import postprocessing
    from platformdatafetcher.platformutils import exclude_influencers_disabled_for_automated_edits

    google_infs = models.Influencer.objects.filter(source='google', relevant_to_fashion__isnull=True)
    google_infs = exclude_influencers_disabled_for_automated_edits(google_infs)
    log.info('%d google_infs to process', google_infs.count())
    for inf in google_infs:
        postprocessing.process_new_influencer_sequentially.apply_async([inf.id, False],
                                                                       queue='new_influencer')

    network_infs = models.Influencer.objects.filter(blogger_type__isnull=False,
                                                    relevant_to_fashion__isnull=True)
    network_infs = exclude_influencers_disabled_for_automated_edits(network_infs)
    for inf in network_infs:
        postprocessing.process_new_influencer_sequentially.apply_async([inf.id, True],
                                                                       queue='new_influencer')


@baker.command
def create_blog_platforms_when_missing():
    from debra import helpers

    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
    select inf.id
    from debra_influencer inf
    left join debra_platform pl on pl.influencer_id=inf.id and (pl.platform_name in ('Blogspot', 'Wordpress', 'Custom') or pl.platform_name is null)
    where inf.blacklisted=False
    and inf.source is not null
    and inf.validated_on like '%%info%%'
    and pl.id is null;
    """)
    inf_ids = cur.fetchall()
    log.info('%d infs without a blog platform', len(inf_ids))
    for inf_id, in inf_ids:
        inf = models.Influencer.objects.get(id=inf_id)
        helpers.create_blog_platform_for_blog_url(inf)


@baker.command
def create_blog_platforms_for_source_google_when_missing():
    from debra import helpers

    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
    select inf.id
    from debra_influencer inf
    left join debra_platform pl on pl.influencer_id=inf.id and (pl.platform_name in ('Blogspot', 'Wordpress', 'Custom') or pl.platform_name is null)
    where inf.blacklisted = False
    and inf.source = 'google'
    and pl.id is null;
    """)
    inf_ids = cur.fetchall()
    log.info('%d infs without a blog platform', len(inf_ids))
    for inf_id, in inf_ids:
        inf = models.Influencer.objects.get(id=inf_id)
        helpers.create_blog_platform_for_blog_url(inf)


@baker.command
def reset_url_not_found_for_validated_instagram_platforms_with_ANY_error():
    infs = Influencer.objects.filter(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).exclude(blacklisted=True)
    plats = Platform.objects.filter(influencer__in=infs, platform_name='Instagram', url_not_found=True)
    for plat in plats:
        with platformutils.OpRecorder('reset_url_not_found', platform=plat):
            plat.url_not_found = None
            plat.save()
            print 'processed %r', plat


if __name__ == '__main__':
    #utils.log_to_stderr()
    baker.run()
