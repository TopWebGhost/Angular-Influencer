from subprocess import Popen, PIPE
import sys
from servers import workers
from django.conf import settings
import errno
from threading import Timer
from celery.decorators import task

import logging

REPORT_TO_EMAILS = [
    {'email': 'atul@theshelf.com', 'type': 'to'},
]

log = logging.getLogger('debra.celery_status_checker')

from mailsnake import MailSnake
mailsnake_client = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')


def timeout(p):
    if p.poll() is None:
        try:
            p.kill()
            print 'Error: process taking too long to complete--terminating'
        except OSError as e:
            if e.errno != errno.ESRCH:
                raise


@task(name="debra.celery_status_checker.check_celery_statuses", ignore_result=True)
def check_celery_statuses():

    machines_list = workers

    downed_machines = []

    # getting downed machines
    for group_name, hosts_list in machines_list.items():

        # skipping some particular groups we're not interested in
        if group_name in ['google-queue', 'rs-queue', 'sentry', 'rs-daily-fetcher']:
            continue

        for remote_host in hosts_list:
            log.info('Connecting to %s...' % remote_host)
            proc = Popen(['fab',
                          '-H', '%s' % remote_host,
                          '-f', '~/Projects_DEFAULT/fabfile/',
                          'common.supervisorctl:command="status"'],
                         stdout=PIPE,
                         stderr=PIPE)

            kill_proc = lambda p: p.kill()
            timer = Timer(10, kill_proc, [proc])
            try:
                timer.start()
                output, err = proc.communicate()
            finally:
                timer.cancel()

            # log.info('OUTPUT FOR %s:%s:' % (group_name, remote_host))
            # log.info(output)

            if any([arg in output for arg in ['STOPPED', 'RUNNING']]):
                log.info('Looks like supervisord is running...')
                pass
            else:
                log.info('Looks like supervisord is downed...')
                downed_machines.append(remote_host)

    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    log.info('Downed machines: %s' % downed_machines)

    # sending an email
    if len(downed_machines) > 0:
        html = "<p>Seems that these machines have Celery currently downed:</p>"
        for host in downed_machines:
            html += "<p>%s</p>" % host

        mailsnake_client.messages.send(message={
            'html': html,
            'subject': 'Some Celery machines might be down',
            'from_email': 'atul@theshelf.com',
            'from_name': 'Celery supervisor checker',
            'to': REPORT_TO_EMAILS}
        )
