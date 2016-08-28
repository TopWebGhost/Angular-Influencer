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
# Note: each page is AJAX response which contains about 10 users
# We can get only first 100 pages
# All followers of all bloggers from first 100 pages will be scraped too
# (and their followers too and etc. until the end)
START_PAGE = 1
STOP_PAGE = 100


# Here is a Grab's magic ;)
class FashiolistaScraper(Spider):

    base_url = 'http://www.fashiolista.com'

    def prepare(self):
        # It's a container for monitoring of visited urls (to prevent duplicates)
        # I use "set" object because the time complexity of testing for collection membership ("X in Y")
        # for "set" object is O(1), which is much more faster then for "lists" - O(n)
        self.visited_urls = set()
        self.ok = True
        self.priority = 10
        self.headers = {'X-Requested-With': 'XMLHttpRequest'}

    def task_generator(self):
        for page_number in xrange(START_PAGE, STOP_PAGE):
            if not self.ok:
                break
            self.priority += 1
            url = self.base_url + '/who_to_follow/bloggers/?ajax=1&page=' + str(page_number)
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
        if 'results_returned' not in json_body or json_body['results_returned'] < 1 or 'template' not in json_body:
            self.ok = False
            print 'No results, URL: %s' % grab.response.url
            return
        if 'next_page_data' not in json_body or not json_body['next_page_data']:
            self.ok = False
            print 'Empty next_page, URL: %s' % grab.response.url
        else:
            if 'ajax' in json_body['next_page_data'] and 'page' in json_body['next_page_data']:
                next_page_number = json_body['next_page_data']['page']
                if next_page_number != (task.page_number + 1):
                    print 'Bad next_page value: %s, URL: %s' % (next_page_number, grab.response.url)
                    self.ok = False
            else:
                self.ok = False
                print 'Empty conteiner for next_page, URL: %s' % grab.response.url
        html_body = json_body['template']
        etree = fromstring(html_body)
        users_ = etree.xpath('li/header//h2/a')
        if not users_:
            self.ok = False
            print 'No more users, URL: %s' % grab.response.url
            return
        for user in users_:
            user_url = self.base_url + user.get('href')
            if user_url not in self.visited_urls:
                grab.config['headers'].pop('X-Requested-With', None)
                grab.setup(url=user_url, user_agent=None, proxy=choice(PROXY))
                yield Task('user', grab=grab, priority=3)

    def task_user(self, grab, task):
        fashiolista_url = grab.response.url
        self.visited_urls.add(fashiolista_url)
        name, info, followers, blog_url, followers_url = ('',)*5
        name_section = grab.doc.select('//header[@id="header_profile"]//h2[@id="profile_name"]/a')
        if name_section.count():
            name = name_section[0].text().strip()
        info_section = grab.doc.select(
            '//header[@id="header_profile"]//h2[@id="profile_name"]/following-sibling::div')
        if info_section.count():
            info = info_section[0].text().strip()
        followers_section = grab.doc.select('//a[@class="tab" and contains(@href,"followers")]')
        if followers_section.count():
            followers_url = followers_section[0].attr('href')
            if followers_url:
                followers_url = self.base_url + followers_url.split('#')[0]
            followers = followers_section[0].select('./b').text().strip()
        url = grab.doc.select('//header[@id="header_profile"]//a[contains(@title,"Blog")]')
        if url.count():
            blog_url = url.attr('href')
        blog_obj, created = BlogUrlsRaw.objects.get_or_create(source=self.base_url,
                                                              name=name,
                                                              description=info,
                                                              url=fashiolista_url,
                                                              num_followers=textutils.first_int_word(followers),
                                                              blog_url=blog_url if len(blog_url) > 0 else None,
                                                              site_url=None)
        if created:
            print "Created a new blog_obj"
        else:
            print "Object already existed"
        print "%r %r %s %s %s" % (name, info, followers, fashiolista_url, blog_url)
        if followers_url and followers.isdigit() and int(followers) > 10:
            grab.setup(url=followers_url, user_agent=None, proxy=choice(PROXY))
            yield Task('followers', grab=grab, priority=2)

    def task_followers(self, grab, task):
        followers_urls = grab.doc.select('//div[@class="module-follower"]//h3/a')
        if followers_urls.count():
            for url in followers_urls:
                user_url = self.base_url + url.attr('href')
                if user_url not in self.visited_urls:
                    grab.setup(url=user_url, user_agent=None, proxy=choice(PROXY))
                    yield Task('user', grab=grab, priority=1)


def read_from_file(filename):
    with open(filename) as infile:
        for line in infile:
            if ',' in line:
                tokens = line.split(',')
                if len(tokens) < 5:
                    continue
                else:
                    print tokens


if __name__ == '__main__':
    print 'The scraper is working right now...'
    # change the current dir
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # set up logging for the scraper (empty error.log and empty network.log - is a good sign)
    # set level=10 to log all events
    default_logging(grab_log='/tmp/errors.log', level=20, mode='w',
        propagate_network_logger=False, network_log='/tmp/network.log')
    # prepare for the battle
    bot = FashiolistaScraper(thread_number=THREAD_NUMBER, network_try_limit=3)
    try:
        # good luck and have fun!
        bot.run()
    finally:
        # show stats
        print bot.render_stats()

