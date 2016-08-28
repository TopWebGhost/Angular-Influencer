"""
Extract email adresses from a blog:
Looks for platform user's email
Not unlike platformextractor looks for emails on "About" page and for the same
email in multiple posts
"""

import logging
import re
import threading
import urlparse

import baker
from celery.decorators import task
from django.conf import settings

from xpathscraper import xbrowser as xbrowsermod
from xpathscraper import utils
from debra import models
from platformdatafetcher import platformutils


log = logging.getLogger('platformdatafetcher.emailextractor')

MAX_EMAILS_FROM_ABOUT_PAGE = 3
# See http://www.regular-expressions.info/email.html
EMAIL_PATTERN = re.compile(
    r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.IGNORECASE
)

tlocal = threading.local()


def filter_emails(emails):
    emails = utils.unique_sameorder(emails, key=lambda e: e.lower())

    res = []
    for e in emails:
        if '.png' in e:
            continue
        res.append(e)

    return res


class FromAboutPagesExtractor(object):

    def __init__(self, xbrowser, source_platform):
        self.xbrowser = xbrowser
        self.source_platform = source_platform
        self.found_emails = []

    def update_influencers_email(self, to_save=False, max_visited_links=20):
        log.info('Initial email field value for %r: %r', self.source_platform.influencer,
                 self.source_platform.influencer.email)

        self.xbrowser.load_url(self.source_platform.url)
        urls = self.xbrowser.execute_jsfun_safe([], '_XPS.visibleLinksWithTexts',
                ['contact', 'about', 'social', 'media', 'follow'], 40)
        urls = [u for u in urls if utils.domain_from_url(u) == \
                            utils.domain_from_url(self.xbrowser.driver.current_url)]
        urls = [u for u in urls if urlparse.urlsplit(u).path.rstrip('/')]
        urls = utils.unique_sameorder(urls)
        log.info('Urls to visit in search for emails: %r', urls)

        for page_url in urls[:max_visited_links]:
            try:
                self.xbrowser.load_url(page_url)
                updated = self._update_from_current_page(to_save)
                if updated:
                    log.info('Current page contained email')
            except:
                log.exception('While processing %r, skipping', page_url)
        log.info('Final email field value for %r: %r', self.source_platform.influencer,
                 self.source_platform.influencer.email)

    def _update_from_current_page(self, to_save=False):
        emails = self.xbrowser.execute_jsfun_safe([], '_XPS.findEmails')
        log.info('emails: %s', emails)
        if not emails:
            log.info('No emails found on current page')
            return False
        emails = list(filter_emails(emails))
        if len(emails) > MAX_EMAILS_FROM_ABOUT_PAGE:
            emails = emails[:MAX_EMAILS_FROM_ABOUT_PAGE]
            log.warn('limited emails to %s', emails)
        self.found_emails = filter_emails(self.found_emails + emails)
        if self.source_platform.influencer:
            log.info('Adding influencer\'s emails: %s', emails)
            if self.source_platform.influencer.is_enabled_for_automated_edits():
                for email in emails:
                    self.source_platform.influencer.append_email_if_not_present(email)
            if to_save:
                self.source_platform.influencer.save()
        return True


class FromCommonPostsExtractor(object):

    def __init__(self, xbrowser, source_platform):
        self.xbrowser = xbrowser
        self.source_platform = source_platform
        self.found_emails = []

    def update_influencers_email(self, to_save=False, max_visited_links=20):
        log.info('Initial email field value for %r: %r', self.source_platform.influencer,
                 self.source_platform.influencer.email)

        urls = []

        urls.append(self.source_platform.url)

        if self.source_platform.id:
            posts = list(self.source_platform.posts_set.order_by('-create_date')[:5])
            log.debug('Fetched posts to search for emails %s', [p.url for p in posts])
        else:
            posts = []
        for post in posts:
            urls.append(post.url)

        self.xbrowser.load_url(self.source_platform.url)

        urls = utils.unique_sameorder(urls)
        log.debug('Urls to visit in search for emails: %r', urls)

        emails_from_urls = []
        for page_url in urls[:max_visited_links]:
            try:
                self.xbrowser.load_url(page_url)
                emails = self._find_on_current_page(to_save)
                log.debug('Emails on %r: %r', page_url, emails)
                emails_from_urls.append(emails)
            except:
                log.exception('While processing %r, skipping', page_url)

        emails_from_urls = [efu for efu in emails_from_urls if efu]
        if len(emails_from_urls) < 3:
            log.debug('Not enough urls with emails')
            return

        common = set.intersection(*[set(efu) for efu in emails_from_urls])
        log.debug('Common emails: %r', common)
        self.found_emails = common

        if self.source_platform.influencer.is_enabled_for_automated_edits():
            for email in common:
                self.source_platform.influencer.append_email_if_not_present(email)
        if to_save:
            self.source_platform.influencer.save()

        log.debug('Final email field value for %r: %r', self.source_platform.influencer,
                 self.source_platform.influencer.email)

    def _find_on_current_page(self, to_save=False):
        emails = self.xbrowser.execute_jsfun_safe([], '_XPS.findEmails')
        log.info('emails: %s', emails)
        if not emails:
            log.info('No emails found on current page')
            return []
        return filter_emails(emails)


def extract_emails_from_text(text):
    if not text:
        return []
    emails = EMAIL_PATTERN.findall(text)
    emails = [e.lower() for e in emails]
    emails = utils.unique_sameorder(emails)
    return emails


@task(name="platformdatafetcher.emailextractor.extract_emails_from_platform", ignore_result=True)
@baker.command
def extract_emails_from_platform(platform_id=None, platform_object=None, to_save=True,
                                 disable_cleanup=False):
    assert platform_id is not None or platform_object is not None
    pl = models.Platform.objects.get(id=int(platform_id)) \
        if platform_id is not None \
        else platform_object
    try:
        with platformutils.OpRecorder('extract_emails_from_platform', platform=pl) as opr:
            with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                                      disable_cleanup=disable_cleanup) as xb:
                found_emails = []

                ee1 = FromAboutPagesExtractor(xb, pl)
                ee1.update_influencers_email(to_save=to_save)
                found_emails += ee1.found_emails

                ee2 = FromCommonPostsExtractor(xb, pl)
                ee2.update_influencers_email(to_save=to_save)
                found_emails += ee2.found_emails

                found_emails = filter_emails(found_emails)
                opr.data = {'found_emails': found_emails}
                return found_emails
    except Exception as e:
        log.exception(e, extra={'platform_id': platform_id,
                                'to_save': to_save,
                                'disable_cleanup': disable_cleanup})

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
