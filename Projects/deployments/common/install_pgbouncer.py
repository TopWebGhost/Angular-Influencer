#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals
import os
import sys
from subprocess import check_call
import tempfile
import argparse

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

sys.path.append(os.path.join(PROJECT_DIR, 'miami_metro'))
import settings

DATABASE = settings.DATABASES['default']

parser = argparse.ArgumentParser()
parser.add_argument('-p', action='store', help='Pool size', dest='pool_size', required=True)
args = parser.parse_args()

DATABASE['POOL_SIZE'] = args.pool_size


def write_template(template, context, out_path):
    text = template % context

    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(text)
    f.close()

    check_call('sudo mv "%s" "%s"' % (f.name, out_path), shell=True)


PGBOUNCER_INI_TEMPLATE = '''
[databases]
%(NAME)s = host=%(HOST)s dbname=%(NAME)s port=%(PORT)s
%(NAME)s_replica = host=%(REPLICA_HOST)s dbname=%(NAME)s port=%(PORT)s

[pgbouncer]
logfile = /var/log/postgresql/pgbouncer.log
pidfile = /var/run/postgresql/pgbouncer.pid

; ip address or * which means all ip-s
listen_addr = 127.0.0.1
listen_port = 6432

auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = session

server_reset_query = DISCARD ALL

max_client_conn = 100
default_pool_size = %(POOL_SIZE)s
'''

USERLIST_TEMPLATE = '''
"%(USER)s" "%(PASSWORD)s"
'''

DEFAULT_PGBOUNCER_TEMPLATE = '''
# Automatically generated by install_pgbouncer.py. Do not edit!
START=1
'''

write_template(PGBOUNCER_INI_TEMPLATE, DATABASE, '/etc/pgbouncer/pgbouncer.ini')
write_template(USERLIST_TEMPLATE, DATABASE, '/etc/pgbouncer/userlist.txt')
write_template(DEFAULT_PGBOUNCER_TEMPLATE, DATABASE, '/etc/default/pgbouncer')

check_call("sudo chown -R postgres.postgres /etc/pgbouncer", shell=True)
check_call("sudo chmod 640 /etc/pgbouncer/*", shell=True)
check_call("sudo service pgbouncer restart", shell=True)
