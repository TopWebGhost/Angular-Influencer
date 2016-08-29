import xmlrpclib
import time
import os
import pprint
import glob
import baker

import supervisor.xmlrpc


KILL_POLL_TIME = 5
KILL_9_TIME = 120


def find_local_supervisors():
    sockets = glob.glob('/tmp/supervisor*.sock')
    return [Supervisord(s) for s in sockets]

class Supervisord(object):

    def __init__(self, socketpath):
        self.socketpath = socketpath
        self.proxy = xmlrpclib.ServerProxy('http://127.0.0.1',
                                      transport=supervisor.xmlrpc.SupervisorTransport(
                                          None, None, serverurl='unix://'+socketpath))

    def print_status(self):
        data = dict(socket=self.socketpath, info=self.proxy.supervisor.getAllProcessInfo())
        pprint.pprint(data)

    def get_celery_process_names(self):
        res = []
        for process_info in self.proxy.supervisor.getAllProcessInfo():
            if process_info['name'].startswith('celery'):
                res.append(process_info['name'])
        return res

    def assure_no_celeries(self):
        for process_info in self.proxy.supervisor.getAllProcessInfo():
            if process_info['name'].startswith('celery'):
                return False
        return True

    def kill_gracefully(self, process_name):
        process_info = self.proxy.supervisor.getProcessInfo(process_name)
        started = time.time()
        while True:
            if time.time() - started >= KILL_9_TIME:
                print 'Could not kill gracefully, killing forcibly'
                os.kill(process_info['pid'], 9)
            print 'Killing', process_name
            self.proxy.supervisor.stopProcess(process_name, False)
            print 'Sleeping...'
            time.sleep(KILL_POLL_TIME)
            print 'Awaken'

@baker.command
def print_local_status():
    ss = find_local_supervisors()
    for s in ss:
        s.print_status()

if __name__ == '__main__':
    baker.run()

