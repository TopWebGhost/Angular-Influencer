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
from . import platformextractor


log = logging.getLogger('platformdatafetcher.petester')


def blogger_outreach_data():
    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../debra/csvs/',
                            'blogger_outreach.csv')
    reader = scripts.spreadsheet_reader(filename)
    rows = list(reader)
    return rows

class PETester(object):

    def __init__(self, rows, extraction_fun=platformextractor.extract_platforms_from_platform,
                 with_posts_only=True):
        self.rows = rows
        self.extraction_fun = extraction_fun
        self.with_posts_only = with_posts_only

        # dictionaries mapping platform name to number of test cases
        self.found = defaultdict(int)
        self.notfound = defaultdict(int)
        self.unknown = defaultdict(int)
        self.incorrect = defaultdict(int)
        self.validated = defaultdict(int)
        self.not_validated = defaultdict(int)

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
            pl.platform_name = 'Outreach'
            pl.url = row['url']
        else:
            pl = pl_candidates[0]

        if pl.posts_set.count() < 5:
            log.warn('No posts for %r', pl)
            if self.with_posts_only:
                return

        platformextractor.tlocal._latest_validated, platformextractor.tlocal._latest_not_validated = None, None
        try:
            extracted = self.extraction_fun(platform_object=pl,
                                            to_save=False,
                                            disable_cleanup=self.procs == 1)
        except:
            log.exception('%s During platform extraction, skipping this row', url)
            self.error_urls.append(row['url'])
            return

        if platformextractor.tlocal._latest_validated is not None:
            for pl, reason in platformextractor.tlocal._latest_validated:
                self.validated[(pl.platform_name, reason)] += 1
        if platformextractor.tlocal._latest_not_validated is not None:
            for pl in platformextractor.tlocal._latest_not_validated:
                self.not_validated[pl.platform_name] += 1
                self.not_validated_pls.append((url, pl))

        log.info('%s Extracted platforms: %r', url, extracted)

        extracted_by_platform_name = defaultdict(list)
        for e in extracted:
            extracted_by_platform_name[e.platform_name].append(e)
        log.info('extracted_by_platform_name:\n%s', pformat(dict(extracted_by_platform_name)))
        for pname, pls in extracted_by_platform_name.items():
            if len(pls) != 1:
                log.warn('999 %r Multiple platforms for a single platform_name %s: %s', url, pname, pls)

        for platform_name in ['Facebook', 'Twitter', 'Pinterest', 'Bloglovin', 'Instagram']:

            from_spreadsheet = row[platform_name].strip()
            if from_spreadsheet:
                username_from_spreadsheet = platformextractor.username_from_platform_url(from_spreadsheet)
            else:
                username_from_spreadsheet = ''

            from_extracted = extracted_by_platform_name[platform_name][0] \
                if extracted_by_platform_name[platform_name] \
                else ''
            if from_extracted:
                username_extracted = platformextractor.username_from_platform_url(from_extracted.url)
            else:
                username_extracted = ''

            if username_from_spreadsheet:
                username_from_spreadsheet = username_from_spreadsheet.lower()
            if username_extracted:
                username_extracted = username_extracted.lower()

            if (not username_from_spreadsheet) and (not username_extracted):
                log.info('%s *** No usernames from both sources for %s', url, platform_name)
            elif username_from_spreadsheet == username_extracted:
                log.warn('%s +++ Test passed: %s: spreadsheet: %r, extracted: %r', url, platform_name,
                         username_from_spreadsheet, username_extracted)
                self.found[platform_name] += 1
            elif (not username_from_spreadsheet):
                log.warn('%s ??? Test unknown: %s: spreadsheet: %r, extracted: %r', url, platform_name,
                         username_from_spreadsheet, username_extracted)
                self.unknown[platform_name] += 1
            elif username_from_spreadsheet and (not username_extracted):
                log.warn('%s --- Test fail: %s: spreadsheet: %r, extracted: %r', url, platform_name,
                         username_from_spreadsheet, username_extracted)
                self.notfound[platform_name] += 1
            elif username_from_spreadsheet != username_extracted:
                log.warn('%s !!! Test incorrect: %s: spreadsheet: %r, extracted: %r', url, platform_name,
                         username_from_spreadsheet, username_extracted)
                self.incorrect[platform_name] += 1

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

        total_found = sum(self.found.values())
        total_notfound = sum(self.notfound.values())
        total_incorrect = sum(self.incorrect.values())
        total = total_found + total_notfound + total_incorrect

        if total == 0:
            print 'NO RESULTS'
            return

        print 'FOUND (%.2f%%)' % ((total_found * 100.0) / total)
        pprint(self.found)
        
        print '\nNOTFOUND (%.2f%%)' % ((total_notfound * 100.0) / total)
        pprint(self.notfound)

        print '\nINCORRECT (%.2f%%)' % ((total_incorrect * 100.0) / total)
        pprint(self.incorrect)

        total_unknown = sum(self.unknown.values())
        print '\nUNKNOWN (%.2f%%)' % ((total_unknown * 100.0) / total)
        pprint(self.unknown)

        total_validated = sum(self.validated.values())
        total_not_validated = sum(self.not_validated.values())
        print '\nVALIDATED (%.2f%%)' % ((total_validated * 100.0) / (total_validated + total_not_validated))
        pprint(self.validated)
        print '\nNOT VALIDATED (%.2f%%)' % ((total_not_validated * 100.0) / (total_validated + total_not_validated))
        pprint(self.not_validated)

        print '\nNOT VALIDATED PLATFORMS'
        pprint(self.not_validated_pls)

        print '\nERROR_URLS'
        pprint(self.error_urls)


def row_from_influencer(inf):
    row = {'url': inf.blog_url}
    for field, platform_name in models.Influencer.field_to_platform_name.items():
        val = getattr(inf, field)
        if val:
            row[platform_name] = val
        else:
            row[platform_name] = ''
    return row

def rows_from_validated_influencers(inf_count=100):
    """Put recently validated influencers into dictionaries
    compatible with rows parsed from the "Outreach" spreadsheet, such that
    the :class:`PETester` class can be used without modifications.
    """
    infs = models.Influencer.objects.filter(validated_on__contains=\
                                         constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).\
                                     order_by('-date_validated')\
                                     [:inf_count]
    res = [row_from_influencer(inf) for inf in infs]
    log.info('Rows from recently validated influencers:\n%s', pformat(res))
    return res


@baker.command
def petester(row_from, row_to, procs):
    rows = blogger_outreach_data()[int(row_from):int(row_to)]
    rows = [r for r in rows if r.get('url') and r['url'] != 'URL']
    #pet = PETester(rows, platformextractor.extract_platforms_from_posts)
    pet = PETester(rows, platformextractor.extract_combined, True)
    log.info('Processing %d rows with %d processes', len(rows), int(procs))
    pet.test(int(procs))

@baker.command
def petester_qa(inf_count, procs):
    rows = rows_from_validated_influencers(int(inf_count))
    pet = PETester(rows, platformextractor.extract_combined, True)
    log.info('Processing %d rows with %d processes', len(rows), int(procs))
    pet.test(int(procs))

@baker.command
def petester_inf(blog_url):
    infs = models.Influencer.objects.filter(blog_url__startswith=blog_url)
    log.info('Found infs: %s', list(infs))
    pet = PETester([row_from_influencer(infs[0])], platformextractor.extract_combined, True)
    pet.test(1)

@baker.command
def petester_single(url):
    rows = [row for row in blogger_outreach_data() if utils.domain_from_url(row['url']) == \
            utils.domain_from_url(url)]
    print rows
    assert rows
    pet = PETester(rows)
    pet.test()

@baker.command
def divide_log_by_thread_ident(filename='petester.log', prefix='THR:'):
    by_thr = defaultdict(list)
    with open(filename, 'r') as f:
        for line in f:
            res = re.search('%s([^ ]+)' % prefix, line)
            if res:
                by_thr[res.group(1)].append(line)
    for thr, lines in by_thr.iteritems():
        with open('%s.%s' % (filename, thr), 'w') as f:
            for line in lines:
                f.write(line)


if __name__ == '__main__':
    utils.log_to_stderr(thread_id=True)
    baker.run()
