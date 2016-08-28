#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from random import choice
from debra.models import BlogUrlsRaw
from xpathscraper import textutils

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        raise ImportError("A json lib is required")
try:
    from grab.spider import Spider, Task
    from grab import Grab
    from grab.tools.logs import default_logging
except ImportError:
    raise ImportError("Grab lib is required (pip install Grab)")
try:
    from lxml.html import fromstring
except ImportError:
    raise ImportError("lxml lib is required (pip install lxml)")


# A number of threads for the scraper (don't set it more than 50 to prevent the 3rd world war)
THREAD_NUMBER = 1
# Proxymesh.com servers
PROXY = (
    'us.proxymesh.com:31280',
    'uk.proxymesh.com:31280',
)
# Note: each page is AJAX response which contains about 48 users
# I've stoped on a page number 2150 (first 100,000 entries which I've sent to you)
# If you want to start from the beginning and get all users in one run, just set START_PAGE = 1
START_PAGE = 1
# I don't know a real number of pages, it's a raw estimate.
# Anyway, if the scraper will get an empty response, then the work will be stopped.
# So leave this value = 50,000. It's enough to get all data from the website.
STOP_PAGE = 50000


# Here is a Grab's magic ;)
class LookbookScraper(Spider):

    base_url = 'http://lookbook.nu'

    def prepare(self):
        self.ok = True
        self.priority = 10
        self.headers = { 
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'http://lookbook.nu/search/users',
            }

    def task_generator(self):
        for page_number in xrange(START_PAGE, STOP_PAGE):
            if not self.ok:
                break
            self.priority += 1
            url = self.base_url + '/search/users?page=' + str(page_number)
            grab = Grab()
            grab.setup(url=url, user_agent=None, headers=self.headers,
                reuse_cookies=False, reuse_referer=False,  follow_location=False,
                timeout=60, connect_timeout=20, hammer_mode=False,
                proxy=choice(PROXY), proxy_type='http')
            yield Task('search', grab=grab, page_number=page_number, priority=self.priority)

    def task_search(self, grab, task):
        try:
            json_body = json.loads(grab.response.body)
        except ValueError:
            self.ok = False
            print "JSON object could not be decoded, URL: %s" % grab.response.url
            return
        if 'payload' not in json_body or not json_body['payload'].strip():
            self.ok = False
            print 'Empty payload, URL: %s' % grab.response.url
            return
        html_body = json_body['payload']
        etree = fromstring(html_body)
        users_ = etree.xpath('//li[@class="search_result_user"]//h1/a')
        if not users_:
            self.ok = False
            print 'No more users, URL: %s' % grab.response.url
            return
        else:
            print 'Page number:', str(task.page_number), '; Users:', str(len(users_))
        for user in users_:
            user_url = user.get('href')
            if user_url:
                grab.config['headers'].pop('X-Requested-With', None)
                grab.config['headers'].pop('Referer', None)
                grab.setup(url=user_url, user_agent=None, proxy=choice(PROXY))
                yield Task('user', grab=grab, priority=1)

    def task_user(self, grab, task):
        lookbook_url = grab.response.url
        name, info, fans, website_url, blog_url = ('',)*5
        name_section = grab.doc.select('//div[@id="userheader"]//h1/a')
        if name_section.count():
            name = name_section[0].text().strip()
        info_section = grab.doc.select('//div[@id="userheader"]//p')
        if info_section.count():
            info = info_section[0].text().strip()
        fans_section = grab.doc.select(
            '//ul[@class="profile_stats"]//span[contains(text(),"Fans")]/preceding-sibling::span')
        if fans_section.count():
            fans = fans_section[0].text().strip()
        urls_section = grab.doc.select(
            '//div[@class="linespaced"]//a[@itemprop="url" and @rel="nofollow"]')
        for url in urls_section:
            if not blog_url and url.select('./parent::div[following-sibling::div[contains(text(),"Bl")]]').count():
                blog_url = url.attr('href')
            else:
                website_url = url.attr('href')
        print "%r %r %s %s %s %s" % (name, info, fans, lookbook_url, website_url, blog_url)

        if BlogUrlsRaw.objects.filter(source=self.base_url, url=lookbook_url).exists():
            print "object exists, returning"
            return
        blog_obj, created = BlogUrlsRaw.objects.get_or_create(source=self.base_url,
                                                              name=name,
                                                              description=info,
                                                              url=lookbook_url,
                                                              num_followers=textutils.first_int_word(fans),
                                                              blog_url=blog_url if len(blog_url) > 0 else None,
                                                              site_url=website_url if len(website_url) > 0 else None)
        if created:
            print "Created a new blog_obj"
        else:
            print "Object already existed"




if __name__ == '__main__':
    # change the current dir
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # set up logging for the scraper (empty error.log and empty network.log - is a good sign)
    # set level=10 to log all events
    default_logging(grab_log='/tmp/errors.log', level=20, mode='w',
        propagate_network_logger=False, network_log='/tmp/network.log')
    # prepare for the battle
    bot = LookbookScraper(thread_number=THREAD_NUMBER, network_try_limit=3)
    try:
        # good luck and have fun!
        bot.run()
    finally:
        # show stats
        print bot.render_stats()

