import logging
import json
from pprint import pformat
import sys
from collections import OrderedDict
import datetime

import baker
import requests
import psycopg2
import psycopg2.extras
import lxml
import lxml.html

from xpathscraper import utils

from . import models
# import miami_metro/settings to access database credentials
from django.conf import settings

log = logging.getLogger('statustasks.tasks')

STATUS_OK = 'ok'
STATUS_FAIL = 'fail'


def _create_prod_db_connection():
    db = settings.DATABASES['default']
    return psycopg2.connect('dbname={NAME} user={USER} password={PASSWORD} port={PORT} host={HOST}'.\
                            format(**db))

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

class Task(object):
    name = 'undefined'

    def run(self):
        """Executes a task and returns (status, desc_json) tuple.
        If an exception happens, status is set to 'fail' and
        desc_json will contain exception name.
        `None` return value indicates no status information is available.
        """
        raise NotImplementedError()

    def __repr__(self):
        return 'Task(name={self.name}'.format(self=self)


class WebsiteAccess(Task):
    name = 'website access'

    def run(self):
        r = requests.get('http://app.theshelf.com/')
        r.raise_for_status()
        return (STATUS_OK, None)


class DatabaseAccess(Task):
    name = 'database access'

    def run(self):
        conn = _create_prod_db_connection()
        cur = conn.cursor()
        cur.execute("""SELECT 1""")
        assert cur.fetchone()[0] == 1
        return (STATUS_OK, None)


class WebsiteLogin(Task):
    name = 'website login'

    def run(self):
        s = requests.Session()

        resp = s.get('http://app.theshelf.com')
        tree = lxml.html.fromstring(resp.content)
        token = tree.xpath('//*[@class="login_form"]//input[@name="csrfmiddlewaretoken"]')[0].attrib['value']

        resp = s.post('http://app.theshelf.com/login/', params=dict(next='/explore/inspiration'),
                data=dict(email='abcd@gmail.com', password='1234', csrfmiddlewaretoken=token))
        resp = s.get('http://app.theshelf.com/explore/inspiration/')
	with open('/tmp/last_website_login.html', 'w') as f:
            f.write(resp.content)
        assert 'daily feed of inspiration' in resp.text.lower()
        return (STATUS_OK, None)


class BookmarkletStatus(Task):
    name = 'bookmarklet status'
    MSG_OK = 'Price updated successfully'
    MSG_FAIL = 'Bookmarklet test fail'

    def run(self):
        try:
            latest_ok = None
            latest_fail = None
            for d, msg in reversed(utils.parse_logfile('/home/ubuntu/hcheck-bookmarklet.out')):
                #log.info('d=%s, msg=%s', d, msg)
                if latest_ok is None and self.MSG_OK in msg:
                    latest_ok = d
                if latest_fail is None and self.MSG_FAIL in msg:
                    latest_fail = d
                if latest_ok is not None and latest_fail is not None:
                    break

            log.info('latest_ok=%s, latest_fail=%s', latest_ok, latest_fail)
            latest_inserted_q = models.TaskResult.objects.filter(task=self.name).\
                order_by('-executed')
            if latest_inserted_q.exists() and latest_inserted_q[0].desc_json:
                log.info('latest_inserted_q[0].desc_json=%r', latest_inserted_q[0].desc_json)
                latest_inserted = eval(json.loads(latest_inserted_q[0].desc_json))
                assert isinstance(latest_inserted, datetime.datetime), type(latest_inserted)
            else:
                latest_inserted = datetime.datetime(1970, 1, 1)
            log.info('bookmarklet: latest_inserted: %s', latest_inserted)
            if latest_ok and latest_ok > latest_inserted:
                log.info('bookmarklet: new ok result')
                return (STATUS_OK, repr(latest_ok))
            if latest_fail and latest_fail > latest_inserted:
                log.info('bookmarklet: new fail result')
                return (STATUS_FAIL, repr(latest_fail))
            log.info('bookmarklet: no new result')
            return None
        except:
            log.exception('during bookmarklet test')
        return None


RABBITMQ_URL = 'http://localhost:25672/'

def rabbitmq_get(url_postfix):
    r = requests.get(RABBITMQ_URL + url_postfix, auth=('shelf_rabbit_q', 'superfastqueue'))
    return r

class RabbitmqAccess(Task):
    name = 'rabbitmq access'

    def run(self):
        r = rabbitmq_get('api/overview')
        log.info('Received rabbitmq response: %r', r.content)
        r_json = r.json()
        assert 'object_totals' in r_json
        return (STATUS_OK, r.content)



TASKS = [
    WebsiteAccess(),
    DatabaseAccess(),
    WebsiteLogin(),
    RabbitmqAccess(),
    BookmarkletStatus(),
]

TASK_BY_NAME = OrderedDict([(t.name, t) for t in TASKS])

def run_tasks():
    res = []
    for task in TASKS:
        tr = run_single_task(task=task)
        if tr:
            res.append(tr)
    log.info('Processed tasks:\n%s', pformat(res))

@baker.command
def run_single_task(task_name=None, task=None):
    if task is None:
        assert task_name is not None
        task = TASK_BY_NAME[task_name]
    try:
        task_res = task.run()
    except Exception as e:
        log.exception('While executing %s', task)
        status = STATUS_FAIL
        desc_json = {'exception_class': e.__class__.__name__, 'repr': repr(e)}
    else:
        if task_res is None:
            log.warn('No task status from task %s', task)
            return None
        status, desc_json = task_res

    if status == STATUS_FAIL:
        logging.getLogger('taskerror').error('Task FAIL: <%s>, %r', task.name, json.dumps(desc_json)[:100])

    tr = models.TaskResult()
    tr.task = task.name
    tr.result = status
    tr.desc_json = json.dumps(desc_json)
    tr.save()
    return tr

@baker.command
def list_tasks():
    print TASKS

if __name__ == '__main__':
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    stderr_hdlr = logging.StreamHandler(sys.stderr)
    stderr_hdlr.setLevel(logging.DEBUG)
    stderr_hdlr.setFormatter(formatter)
    log.setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(stderr_hdlr)

    baker.run()

