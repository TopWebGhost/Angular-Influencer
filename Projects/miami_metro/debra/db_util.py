from __future__ import absolute_import, division, print_function, unicode_literals
from django.conf import settings
from django.db import connections


'''
Retrieve read/write DB connection according to our master/replica settings.

Uses the READ_DB/WRITE_DB settings values. The base settings module points both to the default db and
the replica settings overrides that.
'''


def connection_for_reading():
    return connections[settings.READ_DB]


def connection_for_writing():
    return connections[settings.WRITE_DB]
