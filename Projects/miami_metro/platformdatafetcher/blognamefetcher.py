# -*- coding: utf-8 -*-

"""
Determines blog name using simple euristic: blog title is part of the page title
(inside <title> tag) that goes before the first punctuation mark before either "|" or "-"
given that it is longer than 3 symbols
"""
"""Fetching a blogname for a given platform. The algorithm fetches multiple
pages for a platform and removes a common substring.

Generally blognames entered by QA will be used, and this algorithm is only run when
QA didn't edit an influencer.
"""

import logging
import unittest
import string
import re

import baker
import lxml.html
import requests
from celery.decorators import task

from xpathscraper import utils
from xpathscraper import xutils
from xpathscraper import textutils
from platformdatafetcher import platformutils
from debra import models
from debra import constants


log = logging.getLogger('platformdatafetcher.blognamefetcher')


INVALID_TITLE_WORDS = ['404', '403', 'error', 'forbidden']
INVALID_TITLE_SUBSTRINGS = ['not found', 'no such', 'results for']


class BlognameFetcher(object):

    def __init__(self, platform):
        assert platform.influencer is not None, 'Influencer is None for %r' % platform
        self.platform = platform

    def fetch_blogname(self):
        raise NotImplementedError()


class FromTitleBlognameFetcher(BlognameFetcher):

    def __init__(self, platform, force_edit=False):
        BlognameFetcher.__init__(self, platform)
        self.force_edit = force_edit

    def fetch_blogname(self):

        # TODO: put it in try/except for sending error to Sentry

        blogname = xutils.fetch_title_simple(self.platform.url)
        if not blogname:
            log.warn('No blogname from title for platform %r', self.platform)
            return None

        log.info('Found blogname from platform %r: %r', self.platform, blogname)
        blogname = cleanup_blogname(blogname)
        log.info('After cleanup: %r', blogname)

        if textutils.contains_any_en_word(blogname, INVALID_TITLE_WORDS):
            log.warn('Blogname contains invalid word')
            return None

        if textutils.contains_substring(blogname, INVALID_TITLE_SUBSTRINGS):
            log.warn('Blogname contains invalid substring')
            return None

        if self.force_edit or self.platform.influencer.is_enabled_for_automated_edits():
            log.info('Saving blogname')
            self.platform.blogname = blogname
            self.platform.save()

            if self.platform.platform_name_is_blog:
                log.info('Saving influencer.blogname')
                self.platform.influencer.blogname = blogname
                self.platform.influencer.save()

        return blogname

_re_unicode_space = re.compile(r'\s+', re.UNICODE)
_div_chars = ('|', '-')
def cleanup_blogname(blogname):
    blogname = blogname.strip(string.punctuation)

    #blogname = _re_unicode_space.sub(u'', blogname)

    for div_char in _div_chars:
        if div_char in blogname:
            first_part = blogname.split(div_char, 1)[0]
            first_part = first_part.strip().strip(string.punctuation)
            if first_part and len(first_part) >= 3:
                blogname = first_part
                break

    return blogname


class Test_cleanup_blogname(unittest.TestCase):

    def testGood1(self):
        self.assertEqual('Life of Verity', cleanup_blogname('Life of Verity'))

    def testGood2(self):
        self.assertEqual('no Stillo', cleanup_blogname('no Stillo'))

    def testGood3(self):
        self.assertEqual('Caritrini', cleanup_blogname('Caritrini'))

    #def testGoodUnicode(self):
    #    self.assertEqual(u'World by Ally ♥', cleanup_blogname(u'World by Ally ♥'))

    def testStripPunct(self):
        self.assertEqual('My Life', cleanup_blogname('My Life...'))

    def testStripAfterPipe(self):
        self.assertEqual('LA SAKEUSE',
                         cleanup_blogname('''LA SAKEUSE | histoire d'une chasseuse de sacs et de trucs'''))

    def testStripAfterDash(self):
        self.assertEqual('ZAGUFASHION',
                         cleanup_blogname('ZAGUFASHION - Fashion Blogger my travels, style tips and beauty'))

    def testPunctAndStrip(self):
        self.assertEqual('Hann', cleanup_blogname('Hann | Beauty & Lifestyle.'))

    def testPunctAndStrip2(self):
        self.assertEqual('Pink Elephant Blog', cleanup_blogname('Pink Elephant Blog. | Irish Beauty Blog with an eye for all things Beauty, Fashion & Life'))



@task(name='platformdatafetcher.blognamefetcher.fetch_blogname', ignore_result=True)
@baker.command
def fetch_blogname(platform_id, force_edit=False):
    pl = models.Platform.objects.get(id=int(platform_id))
    with platformutils.OpRecorder('fetch_blogname', platform=pl) as opr:
        bf = FromTitleBlognameFetcher(pl, force_edit=force_edit)
        res = bf.fetch_blogname()
        log.info('Fetched blogname for platform %r: %r', pl, res)

@baker.command
def cleanup_blogname_for_nonvalidated():
    infs = models.Influencer.objects.active().filter(source__isnull=False, relevant_to_fashion=True).exclude(show_on_search=True).exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    plats = models.Platform.objects.filter(influencer__in=infs, platform_name__in=models.Platform.BLOG_PLATFORMS)
    print '%d plats' % plats.count()
    for plat in plats:
        if plat.blogname:
            print 'old: %r' % plat.blogname
            new = cleanup_blogname(plat.blogname)
            print 'new: %r' % new
            if new and plat.blogname != new:
                print 'Saving'
                plat.blogname = new
                plat.save()
            if new and plat.influencer.blogname != new:
                print 'Saving into influencer', plat.influencer.id
                plat.influencer.blogname = new
                plat.influencer.save()
        else:
            print 'skipping'

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

