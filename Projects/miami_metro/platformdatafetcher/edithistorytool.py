"""A testing tool that uses data entered by QA as source of truth. It checks what QA
modified. It works for emails and social platform urls.
"""

import logging
from pprint import pprint, pformat
import datetime
from collections import namedtuple

import baker

from debra import models
from debra import constants
from xpathscraper import utils
from platformdatafetcher import platformutils


log = logging.getLogger('platformdatafetcher.edithistorytool')


class EditHistoryTool(object):

    def __init__(self, min_validation_date):
        self.infs = models.Influencer.objects.filter(date_validated__gte=min_validation_date,
                                                     validated_on__contains=\
                                                     constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
        self.infs_count = self.infs.count()
        log.info('Processing %d influencers', self.infs_count)
        self.ehs_q = models.InfluencerEditHistory.objects.filter(influencer__in=self.infs)
        
        self._init_res = {'infs_count': self.infs_count, 'processed': 0, 'incorrect': 0, 'missing': 0}

    def _val_empty(self, v):
        return not v or v.lower() == 'unknown'

    def _missing(self, eh, res):
        log.info('Missing: %r prev=%r curr=%r', eh.influencer, eh.prev_value, eh.curr_value)
        res['missing'] += 1

    def _incorrect(self, eh, res):
        log.info('Incorrect: %r prev=%r curr=%r', eh.influencer, eh.prev_value, eh.curr_value)
        res['incorrect'] += 1

    def _unknown(self, eh, res):
        log.warn('Not recognized: %r prev=%r curr=%r', eh.influencer, eh.prev_value, eh.curr_value)

    def check_emails(self):
        res = self._init_res.copy()
        for eh in self.ehs_q.filter(field='email'):
            if self._val_empty(eh.prev_value) and not self._val_empty(eh.curr_value):
                self._missing(eh, res)
            elif not self._val_empty(eh.prev_value) and not self._val_empty(eh.curr_value) and \
                    eh.prev_value.strip().lower() != eh.curr_value.strip().lower():
                self._incorrect(eh, res)
            else:
                self._unknown(eh, res)
            res['processed'] += 1
        return res

    def check_platforms(self):
        res = self._init_res.copy()
        for eh in self.ehs_q.filter(field__in=models.Influencer.platform_name_to_field.values()):
            if self._val_empty(eh.prev_value) and not self._val_empty(eh.curr_value):
                self._missing(eh, res)
            elif not self._val_empty(eh.prev_value) and not self._val_empty(eh.curr_value):
                urls_prev = eh.prev_value.split()
                urls_curr = eh.curr_value.split()
                urls_prev = [platformutils.url_to_handle(u) for u in urls_prev]
                urls_curr = [platformutils.url_to_handle(u) for u in urls_curr]
                log.info('Urls prev: %r, Urls curr: %r', urls_prev, urls_curr)
                if set(urls_prev) != set(urls_curr):
                    self._incorrect(eh, res)
                else:
                    log.warn('Urls are the same but have different format')
            else:
                self._unknown(eh, res)
            res['processed'] += 1
        return res


@baker.command
def edit_history_check(hours, what):
    assert what in ('emails', 'platforms')
    d = datetime.datetime.utcnow() - datetime.timedelta(hours=int(hours))
    eht = EditHistoryTool(d)
    res = getattr(eht, 'check_%s' % what)()
    print res

if __name__ == '__main__':
    utils.log_to_stderr(thread_id=True)
    baker.run()
