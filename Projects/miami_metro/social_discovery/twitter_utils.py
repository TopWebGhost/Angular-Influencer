from __future__ import absolute_import, division, print_function, unicode_literals
import re


screen_name_extractor = re.compile(r'twitter.com/(#!/)?@?([^/]+)/?', re.IGNORECASE)


def screen_name_for_url(url):
    match = screen_name_extractor.search(url)
    if match:
        screen_name = match.groups()[1]
        return screen_name.strip()
    else:
        return None
