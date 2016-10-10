from __future__ import absolute_import, division, print_function, unicode_literals
import sys
import time
from collections import namedtuple
from django.db import connection


QueryInfo = namedtuple('QueryInfo', [
    'now', 'running',
    'datid', 'datname', 'pid', 'usesysid', 'usename', 'application_name',
    'client_addr', 'client_hostname', 'client_port',
    'backend_start', 'xact_start', 'query_start', 'state_change',
    'waiting', 'state', 'query',
])


def get_active():
    cursor = connection.cursor()
    try:
        cursor.execute('''
                    SELECT now() as now, now() - query_start as running,
                        datid, datname, pid, usesysid, usename, application_name,
                        client_addr, client_hostname, client_port,
                        backend_start, xact_start, query_start, state_change,
                        waiting, state, query
                    FROM pg_stat_activity
                    WHERE state = 'active' and waiting <> 't'::bool
                    ORDER BY running ASC
                    ''')
        rows = cursor.fetchall()
        for row in rows:
            q = QueryInfo(*row)
            if 'pg_stat_activity' not in q.query:
                yield q
    finally:
        cursor.close()

def print_query(q):
    print('{seconds:.2f}\t{q.client_addr}\t{q.query}'.format(seconds=q.running.total_seconds(), q=q))

def print_active():
    for q in get_active():
        print_query(q)

if __name__ == '__main__':
    while True:
        sys.stderr.write("\x1b[2J\x1b[H")
        print_active()
        time.sleep(5)
