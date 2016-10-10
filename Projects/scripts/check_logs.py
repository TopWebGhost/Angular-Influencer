#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals
import os
import sys
from ConfigParser import RawConfigParser
import argparse
from datetime import datetime, timedelta


def worker_sections(parser):
    for section in parser.sections():
        if (section.startswith('program:') and
                'hcheck' not in section and
                'watchdog' not in section):
            yield section


def program_logs(parser, section):
    items = dict(parser.items(section))
    num_processes = int(items.get('numprocs', 1))

    for i in range(num_processes):
        log_path_template = items['stdout_logfile']
        log_path = log_path_template % dict(process_num=i)
        yield log_path


def check_logfile(section, log_file_path, older_than):
    now = datetime.now()
    last_modified = datetime.fromtimestamp(os.path.getmtime(log_file_path))
    age = now - last_modified
    if age > older_than:
        print("[Failed] Process '{}' with logfile: {}".format( section, log_file_path))
        return False
    else:
        print("[  OK  ]: Process '{}' with logfile {}".format(section, log_file_path))
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', type=argparse.FileType('r'), action='store', dest='config',
                        required=True, help='Supervisor config')
    parser.add_argument('-o', action='store', dest='older_than', required=False, help='Older than <n> minutes',
                        default=15)
    args = parser.parse_args()

    parser = RawConfigParser()
    parser.readfp(args.config)

    check_ok = True
    max_age = timedelta(minutes=args.older_than)
    for worker_section in worker_sections(parser):
        for log_file in program_logs(parser, worker_section):
            ok = check_logfile(worker_section, log_file, max_age)
            if not ok:
                check_ok = False

    if not check_ok:
        print("Found stale log files and possibly hung worker processes.")
        sys.exit(1)

    print("All log files ok.")
