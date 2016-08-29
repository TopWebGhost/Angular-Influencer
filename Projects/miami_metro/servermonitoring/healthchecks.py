import os
from collections import namedtuple
import time
import logging
import datetime

import requests
from raven import Client
import baker
from django.conf import settings
import django.db
import lxml.html

import debra.models
from xpathscraper import utils
import requests


BASE_WEBAPP_URL = 'http://localhost:8000' if settings.DEBUG else 'http://app.theshelf.com'

DISK_LOOP_SLEEP = datetime.timedelta(minutes=5)
DISK_PATHS = ['/', '/home/', '/tmp/']
DISK_MAX_USAGE = 90

BTEST_USER_EMAIL = 'abcd@gmail.com'
BTEST_USER_PASSWORD = '1234'
BTEST_USER_PROFILE_ID = 71
BTEST_TEST_EVERY = datetime.timedelta(minutes=10)
BTEST_CHECK_EVERY = datetime.timedelta(minutes=2)
BTEST_RESULT_SHOULD_BE_AFTER = datetime.timedelta(minutes=5)
BTEST_UPDATE_URL_EVERY = datetime.timedelta(days=1)
#BTEST_TEST_EVERY = datetime.timedelta(minutes=2)
#BTEST_CHECK_EVERY = datetime.timedelta(minutes=0.2)
#BTEST_RESULT_SHOULD_BE_AFTER = datetime.timedelta(minutes=1)

RABBITMQ_SLEEP = datetime.timedelta(minutes=5)

client = Client(settings.SENTRY_DSN, timeout=10)

log = logging.getLogger('severmonitoring.healthchecks')

# http://stackoverflow.com/a/7285509
_ntuple_diskusage = namedtuple('usage', 'total used free')
def disk_usage(path):
    """Return disk usage statistics about the given path.

    Returned valus is a named tuple with attributes 'total', 'used' and
    'free', which are the amount of total, used and free space, in bytes.
    """
    st = os.statvfs(path)
    free = st.f_bavail * st.f_frsize
    total = st.f_blocks * st.f_frsize
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    return _ntuple_diskusage(total, used, free)


@baker.command
def test_failure():
    print 'Sending test failure'
    client.captureMessage('It\'s a test failure only')


@baker.command
def check_disk_space():
    while True:
        log.info('Performing free disk space tests')
        for path in DISK_PATHS:
            info = disk_usage(path)
            used_pct = round((float(info.used) / float(info.total)) * 100.0, 2)
            if used_pct > DISK_MAX_USAGE:
                log.error('High disk usage %s %s' % (path, used_pct))
                client.captureMessage('Disk usage high for path %s' % path,
                        extra=dict(used_pct=str(used_pct)))
        log.info('Sleeping for %s', DISK_LOOP_SLEEP)
        time.sleep(DISK_LOOP_SLEEP.total_seconds())

def login_to_webapp():
    """Log in into theshelf site and return requests session
    for using proper cookies.
    """
    s = requests.Session()

    resp = s.get(BASE_WEBAPP_URL + '/brands/')
    tree = lxml.html.fromstring(resp.content)
    csrftoken_inputs = tree.xpath('//input[@name="csrfmiddlewaretoken"]')
    token = [input.attrib['value'] for input in csrftoken_inputs if input.attrib.get('value')][0]

    resp = s.post(BASE_WEBAPP_URL + '/login/', params=dict(next='/explore/inspiration'),
            data=dict(email=BTEST_USER_EMAIL, password=BTEST_USER_PASSWORD,
            csrfmiddlewaretoken=token))

    return s


### bookmarklet test

def _latest_wishlistitems_product_url():
    latest_wi = debra.models.ProductModelShelfMap.objects.\
            filter(product_model__price__isnull=False).\
            exclude(product_model__price=-11.0).\
            order_by('-added_datetime')\
            [0]
    return latest_wi.product_model.prod_url

_LATEST_BTEST_PRODUCT_URL = None
_LATEST_BTEST_UPDATE_TIME = None
def update_bookmarklet_product_url():
    global _LATEST_BTEST_PRODUCT_URL
    global _LATEST_BTEST_UPDATE_TIME
    if _LATEST_BTEST_PRODUCT_URL is None or \
            (datetime.datetime.now() - _LATEST_BTEST_UPDATE_TIME) >= BTEST_UPDATE_URL_EVERY:
        log.info('Updating bookmarklet test url')
        _LATEST_BTEST_PRODUCT_URL = _latest_wishlistitems_product_url()
        _LATEST_BTEST_UPDATE_TIME = datetime.datetime.now()
        return True
    return False

@baker.command
def bookmarklet_processing_test():
    # List of all times at which bookmarklet tests were performed
    test_times = []
    while True:
        try:
            if update_bookmarklet_product_url():
                test_times[:] = []
            log.info('Bookmarklet product url: %s', _LATEST_BTEST_PRODUCT_URL)
            now = datetime.datetime.now()
            if not test_times or (now >= test_times[-1] + BTEST_TEST_EVERY):
                log.info('Performing new bookmarklet test')
                test_times.append(now)
                s = login_to_webapp()
                log.info('Base webapp url: %s', BASE_WEBAPP_URL)
                resp = s.get(BASE_WEBAPP_URL + '/pricebookmarklet/get-xpaths-for-url',
                        params=dict(url=_LATEST_BTEST_PRODUCT_URL, healthcheck='1'))
                log.info('Bookmarklet resp: %s', resp.content)
                if resp.status_code == 500:
                    utils.write_to_file('/tmp/bookmarklet500.html', resp.content)
                resp.raise_for_status()

            # Check if previous oldest test updated database
            if test_times:
                product_q = debra.models.ProductModel.objects.filter(prod_url=_LATEST_BTEST_PRODUCT_URL)
                if not product_q.exists():
                    log.warn('Product not yet found in the DB')
                    time.sleep(5)
                    continue
                product = product_q[0]
                item = debra.models.ProductModelShelfMap.objects.filter(product_model=product)[0]
                if not item.current_product_price or item.current_product_price.\
                        finish_time < test_times[0]:
                            # Price not yet updated, but should we send error message?
                            log.info('Price not yet updated')
                            if test_times[0] + BTEST_RESULT_SHOULD_BE_AFTER < now:
                                log.error('Bookmarklet test fail, sending error message to sentry')
                                client.captureMessage('Bookmarklet test fail: price not updated',
                                        extra=dict(
                                                prod_url=_LATEST_BTEST_PRODUCT_URL,
                                                seconds_since_submit=\
                                                    str((now - test_times[0]).total_seconds())))
                else:
                    log.info('Price updated successfully')
                    log.info('Fetching existing ProductModelShelfMap')
                    user_item_q = debra.models.ProductModelShelfMap.objects.filter(
                        user_prof_id=BTEST_USER_PROFILE_ID,
                        product_model=product)
                    if user_item_q.exists():
                        user_item = user_item_q[0]
                        if not user_item.img_url:
                            client.captureMessage('Bookmarklet test fail: image not set',
                                    extra=dict(
                                            prod_url=_LATEST_BTEST_PRODUCT_URL,
                                            seconds_since_submit=\
                                                str((now - test_times[0]).total_seconds())))
                        log.info('Deleting existing ProductModelShelfMap (%s)', user_item_q.count())
                        user_item_q.delete()
                    else:
                        client.captureMessage('Bookmarklet test fail: ProductModelShelfMap not created',
                                extra=dict(
                                        prod_url=_LATEST_BTEST_PRODUCT_URL,
                                        seconds_since_submit=\
                                            str((now - test_times[0]).total_seconds())))
                    del test_times[0]
            else:
                log.info('Not checking test status - no waiting tests')

            # Sleep for some time, after releasing db connection
            django.db.close_connection()
            log.info('Sleeping %s' % BTEST_CHECK_EVERY)
            time.sleep(BTEST_CHECK_EVERY.total_seconds())
            log.info('Finished sleeping')
        except KeyboardInterrupt:
            return
        except:
            client.captureException()
            log.exception('')
            try:
                django.db.close_connection()
            except:
                log.exception('While closing connection')
                pass
            time.sleep(5)


def get_rabbitmq_nodes_memory():
    response = requests.get(settings.RABBITMQ_MANAGEMENT_API_ENDPOINT + '/api/nodes',
                            auth=(settings.BROKER_USER, settings.BROKER_PASSWORD))
    response.raise_for_status()

    nodes = response.json()

    used_memory = [(node['name'], node['mem_used']) for node in nodes]
    return used_memory


def run_rabbitmq_check():
    global memory_logger

    memory_info = get_rabbitmq_nodes_memory()
    for node, memory_bytes in memory_info:
        memory_logger.info("RabbitMQ node '{}' using {:.2f} MB memory.".format(node, memory_bytes / 1024. / 1024.))
        if memory_bytes > settings.RABBITMQ_NODE_MEMORY_ALERT:
            raise Exception("Memory used on RabbitMQ node '{}' too high: {:.2f} MB. Threshold: {:.2f} MB.".format(
                node, memory_bytes / 1024. / 1024., settings.RABBITMQ_NODE_MEMORY_ALERT / 1024. / 1024.))


memory_logger = None


@baker.command
def check_rabbitmq_memory():
    # Configure logging -- using the implicit Sentry handler there
    from django.utils.dictconfig import dictConfig
    dictConfig(settings.LOGGING)

    global memory_logger
    memory_logger = logging.getLogger('servermonitoring.healthchecks.check_rabbitmq_memory')

    while True:
        try:
            run_rabbitmq_check()
        except:
            memory_logger.exception('RabbitMQ memory check failed')

        memory_logger.info('Sleeping for %s', RABBITMQ_SLEEP)
        time.sleep(RABBITMQ_SLEEP.total_seconds())


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
