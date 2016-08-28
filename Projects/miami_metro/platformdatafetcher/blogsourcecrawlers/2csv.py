#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import cStringIO
import codecs
from db_conn import *


OUTPUT_FILE = 'lookbook.csv'


class UTF8Recoder:

    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")


class UnicodeWriter:

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow(map(lambda s: s.encode("utf-8") if not isinstance(s, int) else s, row))
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)


def create_csv(f):
    writer = UnicodeWriter(f)
    fline1 = [u'Name', u'Info', u'Followers', u'Lookbook URL', u'Website URL', u'Blog URL']
    writer.writerow(fline1)
    for user in User.select():
        fans = user.fans.replace(',','').replace('.','').replace(' ','').strip()
        if fans.isdigit():
            followers = int(fans)
        else:
            continue
        writer.writerow([user.name, user.info, followers, user.lookbook_url, user.website_url, user.blog_url])


if __name__ == '__main__':
    with open(OUTPUT_FILE, 'wb') as f:
        create_csv(f)
    print 'Done!'

