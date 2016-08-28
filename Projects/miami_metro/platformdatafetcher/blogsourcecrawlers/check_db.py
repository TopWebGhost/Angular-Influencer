#!/usr/bin/env python
# -*- coding: utf-8 -*-

from db_conn import *

print 'USERS: %s' % User.select().count()
