"""A test (running on production environment) that creates a new influencer
instance and runs either a simplified sequentiall processing, or normal multiple-day
processing that should result in running all tasks necessery for an influencer to be
"fully processed". A check for a successfull run looks at an attribute set by
``denormalize_influencer`` task.
"""

import logging
import threading
import socket
import time
import datetime

import baker
from django.core.mail import mail_admins
from celery.decorators import task

from xpathscraper import utils
from platformdatafetcher import postprocessing
from platformdatafetcher import platformutils
from debra import helpers
from debra import models
from debra import constants


log = logging.getLogger('platformdatafetcher.lifecycletest')

TEST_BLOG_HOST = 'platformdatafetchertestblog.com'
TEST_BLOG_URL = 'http://%s' % TEST_BLOG_HOST
REAL_HOST = 'pennypincherfashion.com'

INF_SOURCE = 'lifecycletest'

TEST_SLEEP = 10
TEST_ITERATIONS = 100

NORMAL_TEST_SHOULD_FINISH_AFTER = datetime.timedelta(days=5)


class SequentialProcessingTestUsingMocking(object):

    def __init__(self):
        self._mock()

    def test(self):
        self._cleanup()
        self._start_processing()
        try:
            self._test_results()
        finally:
            self._cleanup()

    def _mock(self):
        host_ip = socket.gethostbyname(REAL_HOST)
        gethostbyname_orig = socket.gethostbyname
        create_connection_orig = socket.create_connection

        def gethostbyname_our(hostname):
            if hostname and hostname.lower() == TEST_BLOG_HOST.lower():
                return host_ip
            return gethostbyname_orig(hostname)

        def create_connection_our(address, *args, **kwargs):
            if address[0].lower() == TEST_BLOG_HOST.lower():
                address = (REAL_HOST, address[1])
            return create_connection_orig(address, *args, **kwargs)

        socket.gethostbyname = gethostbyname_our
        socket.create_connection = create_connection_our

    def _start_processing(self):
        self.inf = helpers.create_influencer_and_blog_platform(TEST_BLOG_URL, INF_SOURCE, to_save=True,
                                                          platform_name_fallback=True)
        self.processing_thread = threading.Thread(target=self._do_processing)
        self.processing_thread.start()

    def _do_processing(self):
        postprocessing.process_new_influencer_sequentially(self.inf.id, assume_blog=False)

    def _test_results(self):
        for step in xrange(100):
            log.info('Starting testing loop iteration')
            self.inf = models.Influencer.objects.get(id=self.inf.id)
            log.info('Refreshed influencer: %r', self.inf)
            if self.inf.active_unknown():
                log.info('Activity status not yet determined. Processing not finished.')
            else:
                log.info('Influencer active: {}, processing finished successfully'.format(self.inf.active()))
                return True
            log.info('Sleeping...')
            time.sleep(5)
        log.info('No successfull result')
        return False

    def _cleanup(self):
        test_infs = models.Influencer.objects.filter(source=INF_SOURCE)
        assert test_infs.count() <= 5
        test_infs.delete()


class ProcessingTest(object):

    def __init__(self):
        self.orig_inf = None
        self.inf = None

    def test_seq(self):
        self._prepare_test_influencer()
        self._start_seq_processing()
        try:
            test_res = self._test_results()
        except:
            test_res = False
        body = 'Original influencer: %r, created influencer: %r' % (self.orig_inf, self.inf)
        if test_res:
            log.info('Test passed!')
            mail_admins('New inf. seq. processing test SUCCESS', body)
        else:
            log.info('Test not passed! Sending email: %r', body)
            mail_admins('New inf. seq. processing test FAIL', body)

    def start_normal_test(self):
        self._prepare_test_influencer(op='created_for_normal_testing')

    def _is_inf_processed_successfully(self, inf):
        return inf.score_popularity_overall is not None

    def check_normal_test_status(self, send_email=False):
        infs = models.Influencer.objects.filter(platformdataop__operation='created_for_normal_testing').order_by('-date_created')
        yes = [inf for inf in infs if self._is_inf_processed_successfully(inf)]
        no = [inf for inf in infs if not self._is_inf_processed_successfully(inf)]
        log.info('Processed successfully: %r', yes)
        log.info('Not processed successfully: %r', no)
        failures = [inf for inf in no if datetime.datetime.now() - inf.date_created >=
                    NORMAL_TEST_SHOULD_FINISH_AFTER]
        log.info('Failures: %r', failures)
        if failures and send_email:
            mail_admins('New inf. normal processing FAIL', 'Failed infs: %r', failures)

    def _disable_inf(self, orig_inf):
        assert orig_inf.blog_url and orig_inf.blog_url.strip()
        blog_plats = list(orig_inf.platform_set.filter(url=orig_inf.blog_url))
        assert len(blog_plats) <= 5
        for plat in blog_plats:
            log.info('Disabling %r', plat)
            plat.url += '.DISABLED'
            plat.save()
        orig_inf.blog_url = orig_inf.blog_url + '.DISABLED'
        orig_inf.blacklisted = True
        orig_inf.save()

    def _prepare_test_influencer(self, op='created_for_testing'):
        infs = models.Influencer.objects.filter(relevant_to_fashion=True, show_on_search=False,
                                                source__isnull=False, classification='blog',
                                                blacklisted=False).\
            exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).\
            exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED).\
            order_by('-id')
        log.info('%d infs', infs.count())
        assert infs.exists()
        inf_to_recreate = infs[0]
        self.orig_inf = inf_to_recreate
        log.info('Recreating influencer %r', inf_to_recreate)
        orig_blog_url = inf_to_recreate.blog_url
        orig_source = inf_to_recreate.source
        self._disable_inf(inf_to_recreate)
        self.inf = helpers.create_influencer_and_blog_platform(orig_blog_url,
                                                               orig_source,
                                                               to_save=True,
                                                               platform_name_fallback=True)
        assert self.inf is not None
        with platformutils.OpRecorder(operation=op, influencer=self.inf) as opr:
            opr.data = {'source_influencer_id': inf_to_recreate.id}
        log.info('New influencer for testing: %r', self.inf)

    def _start_seq_processing(self):
        self.processing_thread = threading.Thread(target=self._do_processing)
        self.processing_thread.start()

    def _do_processing(self):
        postprocessing.process_new_influencer_sequentially(self.inf.id, assume_blog=False)

    def _test_results(self):
        for step in xrange(TEST_ITERATIONS):
            log.info('Starting testing loop iteration')
            self.inf = models.Influencer.objects.get(id=self.inf.id)
            log.info('Refreshed influencer: %r', self.inf)
            if self.inf.score_popularity_overall is None:
                log.info('score_popularity_overall is still None, processing not finished')
            else:
                log.info('score_popularity_overall=%r, processing finished successfully', self.inf.score_popularity_overall)
                return True
            log.info('Sleeping...')
            time.sleep(TEST_SLEEP)
        log.info('No successfull result')
        return False


@task(name="platformdatafetcher.lifecycletest.test_sequential_processing", ignore_result=True)
@baker.command
def test_sequential_processing():
    test = ProcessingTest()
    test.test_seq()


@task(name="platformdatafetcher.lifecycletest.start_normal_test", ignore_result=True)
@baker.command
def start_normal_test():
    test = ProcessingTest()
    test.start_normal_test()


@task(name="platformdatafetcher.lifecycletest.check_normal_test_status", ignore_result=True)
@baker.command
def check_normal_test_status():
    test = ProcessingTest()
    test.check_normal_test_status()


if __name__ == '__main__':
    utils.log_to_stderr(thread_id=True)
    baker.run()
