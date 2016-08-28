"""A testing tool for :mod:`platformdatafetcher.email_extractor` module.
It uses QA'd influencers as the source of truth and runs email extraction
algorithm live using multiple processes.
"""

import os.path
import logging
from pprint import pprint, pformat
import multiprocessing.pool
import re

import baker
from collections import defaultdict
from django.conf import settings

from hanna import scripts
from debra import models
from debra import constants
from xpathscraper import utils
from . import emailextractor


log = logging.getLogger('platformdatafetcher.eetester')


class EETester(object):

    def __init__(self, rows, extraction_fun=emailextractor.extract_emails_from_platform,
                 with_posts_only=True):
        self.rows = rows
        self.extraction_fun = extraction_fun
        self.with_posts_only = with_posts_only

        self.found = 0
        self.notfound = 0
        self.unknown = 0
        self.incorrect = 0
        self.validated = 0
        self.not_validated = 0

        self.error_urls = []
        self.not_validated_pls = []

    def test_row(self, row):
        url = row['url']
        log.info('%s Processing', url)
        pl_candidates = models.Platform.objects.filter(url=url, platform_name='Blogspot')
        if not pl_candidates.exists():
            log.warn('%s No Platform', url)
            if self.with_posts_only:
                return
            pl = models.Platform()
            pl.platform_name = 'TestData'
            pl.url = row['url']
        else:
            pl = pl_candidates[0]

        if not pl.posts_set.exists():
            log.warn('No posts for %r', pl)
            if self.with_posts_only:
                return

        emailextractor.tlocal._latest_validated, emailextractor.tlocal._latest_not_validated = None, None
        try:
            extracted = self.extraction_fun(platform_object=pl,
                                            to_save=False,
                                            disable_cleanup=self.procs == 1)
        except:
            log.exception('%s During platform extraction, skipping this row', url)
            self.error_urls.append(row['url'])
            return

        log.info('%s Extracted emails: %r', url, extracted)

        if emailextractor.tlocal._latest_validated is not None:
            for email in emailextractor.tlocal._latest_validated:
                self.validated[(pl.platform_name, reason)] += 1
        if emailextractor.tlocal._latest_not_validated is not None:
            for pl in emailextractor.tlocal._latest_not_validated:
                self.not_validated[pl.platform_name] += 1
                self.not_validated_pls.append((url, pl))

        valid = row.get('valid_emails', '').split()
        log.info('%s Valid emails: %r', url, valid)
        
        extracted = [e.lower() for e in extracted]
        valid = [e.lower() for e in valid]

        if (not valid) and (not extracted):
            log.info('%s *** No usernames from both sources for %s', url, platform_name)
        elif set(valid) == set(extracted):
            log.warn('%s +++ Test passed', url)
            self.found += 1
        elif (not valid):
            log.warn('%s ??? Test unknown', url)
            self.unknown += 1
        elif valid and (not extracted):
            log.warn('%s --- Test fail', url)
            self.notfound += 1
        elif set(valid) != set(extracted):
            log.warn('%s !!! Test incorrect', url)
            self.incorrect += 1

    def _setup_child(self):
        pass

    def _child_job(self, row):
        try:
            self.test_row(row)
        except:
            log.exception('In child job')
            raise

    def test(self, procs=1):
        self.procs = procs
        self.pool = multiprocessing.pool.ThreadPool(processes=procs, initializer=self._setup_child)
        self.pool.map(self._child_job, self.rows, chunksize=1)

        total = self.found + self.notfound + self.incorrect + self.unknown

        if total == 0:
            print 'NO RESULTS'
            return

        print 'FOUND (%.2f%%)' % ((self.found * 100.0) / total)
        pprint(self.found)
        
        print '\nNOTFOUND (%.2f%%)' % ((self.notfound * 100.0) / total)
        pprint(self.notfound)

        print '\nINCORRECT (%.2f%%)' % ((self.incorrect * 100.0) / total)
        pprint(self.incorrect)

        print '\nUNKNOWN (%.2f%%)' % ((self.unknown * 100.0) / total)
        pprint(self.unknown)

        #total_validated = sum(self.validated.values())
        #total_not_validated = sum(self.not_validated.values())
        #print '\nVALIDATED (%.2f%%)' % ((total_validated * 100.0) / (total_validated + total_not_validated))
        #pprint(self.validated)
        #print '\nNOT VALIDATED (%.2f%%)' % ((total_not_validated * 100.0) / (total_validated + total_not_validated))
        #pprint(self.not_validated)

        #print '\nNOT VALIDATED PLATFORMS'
        #pprint(self.not_validated_pls)

        print '\nERROR_URLS'
        pprint(self.error_urls)


def row_from_influencer(inf):
    return {'url': inf.blog_url, 'valid_emails': inf.email}

def rows_from_validated_influencers(inf_count=100):
    infs = models.Influencer.objects.filter(validated_on__contains=\
                                                constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS,
                                            email__isnull=False).\
                                     order_by('-date_validated')\
                                     [:inf_count]
    res = [row_from_influencer(inf) for inf in infs]
    log.info('Rows from recently validated influencers:\n%s', pformat(res))
    return res


@baker.command
def eetester_qa(inf_count, procs):
    rows = rows_from_validated_influencers(int(inf_count))
    eet = EETester(rows, emailextractor.extract_emails_from_platform, True)
    log.info('Processing %d rows with %d processes', len(rows), int(procs))
    eet.test(int(procs))

@baker.command
def eetester_inf(blog_url):
    infs = models.Influencer.objects.filter(blog_url__startswith=blog_url)
    log.info('Found infs: %s', list(infs))
    eet = EETester([row_from_influencer(infs[0])], emailextractor.extract_emails_from_platform, True)
    eet.test(1)

@baker.command
def divide_log_by_thread_ident(filename='eetester.log', prefix='THR:'):
    from . import petester

    petester.divide_log_by_thread_ident(filename, prefix)

if __name__ == '__main__':
    utils.log_to_stderr(thread_id=True)
    baker.run()
