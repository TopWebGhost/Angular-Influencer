import logging
import datetime

import baker
from celery.decorators import task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from debra import db_util

import debra.models
from xpathscraper import utils
from xpathscraper import xbrowser as xbrowsermod
from xpathscraper import textutils
from platformdatafetcher import platformutils
from platformdatafetcher import contentfiltering


log = logging.getLogger('platformdatafetcher.widgetfetcher')


class SponsorshipFetcher(object):
    widget_type = None

    def __init__(self, xbrowser, post):
        self.xbrowser = xbrowser
        self.post = post

    def fetch_sponsorship(self, to_save=False):
        """Should return :class:`debra.models.SponsorshipInfo`.
        """
        raise NotImplementedError()


class RafflecopterFetcher(SponsorshipFetcher):
    widget_type = 'rafflecopter'

    def __init__(self, xbrowser, post):
        self.xbrowser = xbrowser
        self.post = post

    def fetch_sponsorship(self, to_save=False):
        self.xbrowser.load_url(self.post.url)
        iframes = self.xbrowser.driver.find_elements_by_tag_name('iframe')
        log.debug('iframes: %s', iframes)
        r_iframes = [iframe for iframe in iframes if 'rafflecopter' in \
                     (iframe.get_attribute('src') or '').lower()]
        if not r_iframes:
            log.warn('No rafflecopter iframes')
            return None
        kwargs = {
            'post': self.post,
            'widget_type': self.widget_type,
        }
        sp_q = debra.models.SponsorshipInfo.objects.filter(**kwargs)
        if sp_q.exists():
            sp = sp_q[0]
            log.debug('using existing SponsorshipInfo: %r', sp)
        else:
            sp = debra.models.SponsorshipInfo(**kwargs)
            log.debug('created new SponsorshipInfo')

        sp.url = r_iframes[0].get_attribute('src')
        self.xbrowser.driver.switch_to_frame(r_iframes[0].get_attribute('name'))

        total_entries_el = self.xbrowser.driver.find_element_by_id('entry-count')
        total_entries_word = total_entries_el.text.split()[0]
        if total_entries_word == '--':
            sp.total_entries = 0
        else:
            try:
                sp.total_entries = int(total_entries_word)
            except ValueError:
                pass

        max_entry_value_el = self.xbrowser.driver.find_element_by_id('points-avail')
        sp.max_entry_value = int(textutils.int_words(max_entry_value_el.text)[-1])

        title_el = self.xbrowser.driver.find_element_by_id('aux-prizes')
        sp.title = title_el.text.strip()

        is_running_el = self.xbrowser.driver.find_element_by_id('time-left')
        sp.is_running = 'over' not in is_running_el.text.lower()

        log.info('parsed sponsorship: %s', sp)

        if to_save:
            sp.save()
        return sp


class _FromIframeFetcher(SponsorshipFetcher):
    iframe_address = None

    def __init__(self, xbrowser, post):
        SponsorshipFetcher.__init__(self, xbrowser, post)

    def fetch_sponsorship(self, to_save=False):
        assert self.iframe_address
        self.xbrowser.load_url(self.post.url)

        iframes = self.xbrowser.driver.find_elements_by_tag_name('iframe')
        log.debug('iframes: %s', iframes)
        r_iframes = [iframe for iframe in iframes if self.iframe_address in \
                     (iframe.get_attribute('src') or '').lower()]
        if not r_iframes:
            log.warn('No %s iframes', self.widget_type)
            return None
        kwargs = {
            'post': self.post,
            'widget_type': self.widget_type,
        }
        sp_q = debra.models.SponsorshipInfo.objects.filter(**kwargs)
        if sp_q.exists():
            sp = sp_q[0]
            log.debug('using existing SponsorshipInfo: %r', sp)
        else:
            sp = debra.models.SponsorshipInfo(**kwargs)
            log.debug('created new SponsorshipInfo')

        sp.url = r_iframes[0].get_attribute('src')[:1000]

        if to_save:
            sp.save()
        return sp


class RstyleFetcher(_FromIframeFetcher):
    widget_type = 'rstyle'
    iframe_address = 'currentlyobsessed.me'


class ShopstyleFetcher(_FromIframeFetcher):
    widget_type = 'shopstyle'
    iframe_address = 'popsugar.com'


class ShopsensestyleFetcher(_FromIframeFetcher):
    widget_type = 'shopstyle2'
    iframe_address = 'shopstyle.com'


class ShopThePostSponsorshipFetcher(SponsorshipFetcher):
    widget_type = 'shopthepost'
    base_xpath = '//div[contains(@class, "shopthepost-widget")]'

    def __init__(self, xbrowser, post):
        SponsorshipFetcher.__init__(self, xbrowser, post)

    def fetch_sponsorship(self, to_save=False):
        self.xbrowser.load_url(self.post.url)
        divs = self.xbrowser.driver.find_elements_by_xpath(self.base_xpath)
        if not divs:
            return None
        div = divs[0]
        widget_id = div.get_attribute('data-widget-id')
        if not widget_id:
            log.warn('No widget id for shopthepost widget, passing')
            return None
        kwargs = {
            'post': self.post,
            'widget_type': self.widget_type,
            'widget_id': widget_id,
            'url': self.post.url,
            'base_xpath': self.base_xpath,
        }
        sp_q = debra.models.SponsorshipInfo.objects.filter(**kwargs)
        if sp_q.exists():
            sp = sp_q[0]
            log.info('using existing SponsorshipInfo: %r', sp)
        else:
            sp = debra.models.SponsorshipInfo(**kwargs)
            log.info('created new SponsorshipInfo %r', sp)
        if to_save:
            sp.save()
        return sp



SPONSORSHIP_FETCHER_CLASSES = [
    RafflecopterFetcher,
    RstyleFetcher,
    ShopstyleFetcher,
    ShopsensestyleFetcher,
    ShopThePostSponsorshipFetcher,
]

WIDGET_TYPE_TO_SPONSORSHIP_FETCHER_CLASS = {cls.widget_type: cls for cls in SPONSORSHIP_FETCHER_CLASSES}

TASK_KWARGS = {
    'ignore_result': True,
    'bind': True,
    'soft_time_limit': 300,
    'time_limit': 330,
    'max_retries': 3,
    'default_retry_delay': 3600,
}


def detect_sidebar_sponsorships(sponsorship_info):
    if sponsorship_info is None:
        return
    shared = debra.models.SponsorshipInfo.objects.filter(url=sponsorship_info.url,
                                                   widget_id=sponsorship_info.widget_id,
                                                   post__platform=sponsorship_info.post.platform)
    cnt = shared.count()
    assert cnt > 0, 'Arg not saved'
    if cnt == 1:
        log.info('Not a sidebar widget')
        return
    log.info('Detected %d widgets with the same url and widget_id', cnt)
    for si in shared:
        if si.sidebar:
            continue
        with platformutils.OpRecorder(operation='fieldchange_sidebar',
                                      spec_custom='SponsorshipInfo:%d' % si.id) as opr:
            si.sidebar = True
            si.save()


@task(name='platformdatafetcher.sponsorshipfetcher.update_all_sponsorships')
@baker.command
def update_all_sponsorships():
    sps = debra.models.SponsorshipInfo.objects.filter(is_running=True)
    for sp in sps:
        update_single_sponsorship.apply_async([sp.id])

@task(name='platformdatafetcher.sponsorshipfetcher.update_single_sponsorship', **TASK_KWARGS)
def update_single_sponsorship(self, sponsorshipinfo_id):
    try:
        sp = debra.models.SponsorshipInfo.objects.get(id=sponsorshipinfo_id)
        with platformutils.OpRecorder(operation='update_single_sponsorship', post=sp.post) as opr:
            with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
                f = WIDGET_TYPE_TO_SPONSORSHIP_FETCHER_CLASS[sp.widget_type](xb, sp.post)
                si = f.fetch_sponsorship(True)
                detect_sidebar_sponsorships(si)
    except SoftTimeLimitExceeded as exc:
        self.retry(exc=exc)

@task(name='platformdatafetcher.sponsorshipfetcher.search_for_sponsorship', **TASK_KWARGS)
def search_for_sponsorship(self, post_id):
    res = []
    try:
        post = debra.models.Posts.objects.get(id=post_id)
        with platformutils.OpRecorder(operation='search_for_sponsorship', post=post) as opr:
            with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
                for f_cls in SPONSORSHIP_FETCHER_CLASSES:
                    f = f_cls(xb, post)
                    try:
                        fres = f.fetch_sponsorship(True)
                        if fres is not None:
                            res.append(fres)
                            detect_sidebar_sponsorships(fres)

                    except:
                        log.exception('While search_for_sponsorship')
    except SoftTimeLimitExceeded as exc:
        self.retry(exc=exc)
    return res

@task(name='platformdatafetcher.sponsorshipfetcher.fetch_recent_sponsorships')
@baker.command
def fetch_recent_sponsorships():
    """Searches for all sponsorships in posts crawled in the last day.
    """
    posts = debra.models.Posts.objects.\
        filter(create_date__gte=datetime.date.today() - datetime.timedelta(days=1)).\
        exclude(platform__platform_name__in=['Facebook', 'Pinterest', 'Twitter', 'Instagram'])
    log.info('Submitting search_for_sponsorship tasks for %s posts', posts.count())
    for post in posts:
        search_for_sponsorship.apply_async([post.id])

@baker.command
def sponsorship_from_url(widget_type, url, to_save='0'):
    try:
        xb = xbrowsermod.XBrowser()
        post = debra.models.Posts.objects.filter(url=url)[0]
        rf = WIDGET_TYPE_TO_SPONSORSHIP_FETCHER_CLASS[widget_type](xb, post)
        sp = rf.fetch_sponsorship(int(to_save))
        print sp
    except Exception as e:
        log.exception(e, extra={'widget_type': widget_type,
                                'url': url,
                                'to_save': to_save})
        return None

def get_product_urls(post_id):
    """
    This method fetches the product URLs contained inside the widgets
    """
    post = debra.models.Posts.objects.get(id=post_id)
    if post.platform.is_social:
        log.debug("Post %r is from social platform, so no need to search for iframe based widgets" % post)
        return set()
    search_for_sponsorship(post_id)
    #widgets = debra.models.SponsorshipInfo.objects.filter(post__id=post_id)
    widgets = debra.models.SponsorshipInfo.objects.filter(post__id=post_id, widget_type__in=['rstyle',
                                                                                             'shopstyle',
                                                                                             'shopstyle2'])
    widgets = widgets.exclude(sidebar=True)
    url_set = set()
    if widgets.exists():
        for w in widgets:
            xb = None
            try:
                xb = xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY)
                xb.load_url(w.url)
                url_xpath = '//a'
                if w.base_xpath:
                    url_xpath = w.base_xpath + url_xpath
                log.info('Using url xpath %r for widget %r', url_xpath, w)
                url_elements = xb.els_by_xpath(url_xpath)
                for u in url_elements:
                    if u.get_attribute('href'):
                        url_set.add(u.get_attribute('href'))
                xb.cleanup()
            except Exception as e:
                log.exception("Exception occurred while parsing product url: %s" % e,
                              extra={'post_id': post_id,
                                     'url': w.url})
            if xb:
                try:
                    xb.cleanup()
                except Exception as e:
                    log.exception(e)

    return url_set


@baker.command
def redetect_sidebar_sponsorships():
    sis = debra.models.SponsorshipInfo.objects.exclude(sidebar=True)
    for si in sis:
        try:
            detect_sidebar_sponsorships(si)
        except:
            log.exception('Skipping')



@baker.command
def find_and_reimport_linking_posts(slot=0):
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
    select po.url
    from debra_sponsorshipinfo si
    join debra_posts po on si.post_id=po.id
    where si.sidebar=true;
    """)
    bad_post_urls = {r[0] for r in cur}
    log.info('Got %d bad urls', len(bad_post_urls))
    infs = debra.models.Influencer.objects.filter(show_on_search=True).order_by('id')
    count = infs.count()
    num_workers = 10
    slice_val = count/num_workers
    for inf in infs[slot*slice_val:(slot+1)*slice_val]:
        log.info('Processing influencer %r', inf)
        all_posts = inf.posts_set.all()
        for post in all_posts.iterator():
            try:
                content = platformutils.iterate_resolve_shortened_urls(post.content)
                all_urls = contentfiltering.find_all_urls(content)
                log.info('Urls in post %r: %r', post, all_urls)
                for url in all_urls:
                    url = utils.remove_query_params(url)
                    if url in bad_post_urls:
                        log.warn('Bad url: %r', url)
                        post.brandinpost_set.all().delete()
                        post.products_import_completed = False
                        post.save()
            except:
                log.exception('While processing %r', post)


if __name__ == '__main__':
    utils.log_to_stderr(['__main__', 'platformdatafetcher', 'xps', 'xpathscraper', 'requests'])
    baker.run()

