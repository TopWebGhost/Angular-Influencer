__author__ = 'atulsingh'

import gspread
from debra.models import Influencer, Platform

GOOGLE_DRIVER_USERNAME = 'lauren@theshelf.com'
GOOGLE_DRIVER_PASSWORD = 'namaste_india'


class GDocsWrapper:

    def __init__(self, doc_name):
        gc = gspread.login(GOOGLE_DRIVER_USERNAME, GOOGLE_DRIVER_PASSWORD)
        self.file = gc.open(doc_name).sheet1

    def read_as_list(self):
        list_of_lists = self.file.get_all_values()
        keywords = list_of_lists[0]
        print "%s" % keywords
        print "How many lists?: %d " % len(list_of_lists)
        urls = set()
        for l in list_of_lists[1:]:
            url = l[0]
            urls.add(url)
        return urls



if __name__ == "__main__":
    gc = GDocsWrapper('The Shelf : Blogger Outreach')
    urls = gc.read_as_list()
    print "Ok, we found %d urls" % len(urls)
    exists = set()

    ## now create an influencer and their corresponding platforms
    ## you can use influencer.create_platform() method