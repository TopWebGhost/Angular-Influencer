import logging
import re
from collections import namedtuple
import time
import os.path
import tempfile

import baker
import psutil

from xpathscraper import utils


log = logging.getLogger('servermonitoring.watchdog')


VALIDATED_PROCESSES_DIR = os.path.join(tempfile.tempdir or '/tmp', 'watchdog-validated')

ProcessSpec = namedtuple('ProcessSpec', (
                            'pattern',
                            'max_memory_mb',
                            'validated_after_s',
                            'validated_every_s',
                        ))


def process_id(pid):
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return None
    return '%s.%s' % (pid, int(p.create_time()))


def validate_process(pid):
    if not os.path.exists(VALIDATED_PROCESSES_DIR):
        try:
            os.mkdir(VALIDATED_PROCESSES_DIR)
        except OSError as e:
            if e.errno == 17:
                pass
            else:
                raise
    id = process_id(pid)
    if id is None:
        return
    with open(os.path.join(VALIDATED_PROCESSES_DIR, id), 'w') as f:
        f.write(str(time.time()))


def process_validation_timestamp(pid):
    id = process_id(pid)
    if id is None:
        return False
    filename = os.path.join(VALIDATED_PROCESSES_DIR, id)
    try:
        with open(filename, 'r') as f:
            try:
                return float(f.read())
            except ValueError:
                return None
    except IOError:
        return None


def is_process_validated(pid):
    return process_validation_timestamp(pid) is not None


class Watchdog(object):

    def __init__(self, process_spec_list, poll_interval=30):
        self.process_spec_list = process_spec_list
        self.poll_interval = poll_interval

    def watch(self):
        while True:
            log.info('Checking processes')
            loop_start = time.time()
            count = 0
            for proc in psutil.process_iter():
                count += 1
                # check for new processes to avoid situtations when a pid is reused
                if proc.create_time() > loop_start:
                    continue
                for process_spec in self.process_spec_list:
                    if re.match(process_spec.pattern, proc.name().lower()):
                        log.info('Handling process %r matching %r', proc, process_spec)
                        self._handle_process(process_spec, proc)
            log.info('%d processes looked at, now sleeping...', count)
            time.sleep(self.poll_interval)

    def _should_kill(self, process_spec, proc):
        if process_spec.max_memory_mb:
            used_mb = proc.memory_info().rss // (1024 * 1024)
            log.info('Process %r uses %dMB memory', proc, used_mb)
            if used_mb > process_spec.max_memory_mb:
                log.info('Process is using too much memory: %r' % proc.name())
                return True

        if process_spec.validated_after_s is not None:
            uptime = time.time() - proc.create_time()
            if uptime >= process_spec.validated_after_s:
                if not is_process_validated(proc.pid):
                    log.info('Process %s not validated after %ss', proc, uptime)
                    return True

        if process_spec.validated_every_s is not None:
            last_validated = process_validation_timestamp(proc.pid)
            if last_validated is not None:
                since_validation = time.time() - last_validated
                if since_validation >= process_spec.validated_every_s:
                    log.info('Process %s not revalidated after %ss', proc, since_validation)
                    return True

    def _handle_process(self, process_spec, proc):
        if self._should_kill(process_spec, proc):
            self._kill_gracefully(proc)

    def _kill_gracefully(self, proc):
        log.info('Killing %r', proc)
        proc.terminate()
        time.sleep(2)
        if proc.is_running():
            log.info('Still running, sending SIGKILL')
            proc.kill()


PROCESS_SPECS = [
    ProcessSpec(pattern='.*firefox.*',
                max_memory_mb=1200,
                validated_after_s=180,
                validated_every_s=180),
]


@baker.command
def watch(poll_interval=30):
    w = Watchdog(PROCESS_SPECS, int(poll_interval))
    w.watch()


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
