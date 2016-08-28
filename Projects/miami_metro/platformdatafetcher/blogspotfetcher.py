"""
Fetcher for Blogspot
uses grab for some reason
Supports proxies
"""

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A version of Blogspot fetcher that analyzes xpaths.
"""

from random import choice
from datetime import datetime
from dateutil.parser import parse as parse_iso_date
from urlparse import urlparse
from grab.spider import Spider, Task
from grab import Grab
from grab.tools.logs import default_logging

from fetcherbase import Fetcher
from debra import models
from platformdatafetcher.activity_levels import recalculate_activity_level

#????????????????
default_logging(grab_log='/tmp/grab.log', level=10, mode='w',
                propagate_network_logger=False, network_log='/tmp/grab_network.log')


class BlogspotFetcher(Spider, Fetcher):

    name = 'Blogspot'

    # The names of months (for parsing of the date)
    months_names = {
        'JANUARY': 1, 'JAN': 1,
        'FEBRUARY': 2, 'FEB': 2,
        'MARCH': 3, 'MAR': 3,
        'APRIL': 4, 'APR': 4,
        'MAY': 5,
        'JUNE': 6, 'JUN': 6,
        'JULY': 7, 'JUL': 7,
        'AUGUST': 8, 'AUG': 8,
        'SEPTEMBER': 9, 'SEP': 9,
        'OCTOBER': 10, 'OCT': 10,
        'NOVEMBER': 11, 'NOV': 11,
        'DECEMBER': 12, 'DEC': 12,
    }

    def __init__(self,
                 platform,
                 policy,
                 thread_number=10,
                 proxy_support=False,
                 proxy_servers=None,
                 proxy_type='http'):
        """
        :param thread_number: The number of threads
        :param proxy_support: Enable/disable proxy proxy_support
        :param proxy_servers: List of proxies ['host:port', 'host:port', etc.]
        :param proxy_type: The type of the proxy (http, socks4, socks5)
        """
        self.platform = platform
        self.proxy_servers = proxy_servers
        self.proxy_type = proxy_type
        if proxy_support:
            self.get_proxy = lambda: choice(self.proxy_servers)
        else:
            self.get_proxy = lambda: None
            self.proxy_type = None
        self.posts = {}
        Fetcher.__init__(self, platform, policy)
        Spider.__init__(self, thread_number=thread_number, network_try_limit=5)

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):
        self.max_pages_to_scrape = max_pages
        self.run()
        return self.posts.keys()

    def fetch_post_interactions(self, posts):
        comments_list = []
        for post, comments in self.posts.iteritems():
            if post not in posts:
                continue
            for comment in comments:
                c = models.PostInteractions()
                if comment['author_name'] or comment['author_url']:
                    follower, created = models.Follower.objects.get_or_create(
                        firstname=comment['author_name'],
                        url=comment['author_url'])
                    c.follower = follower
                if models.PostInteractions.objects.filter(post=post, content=comment['content']).exists():
                    print "%s already exists" % comment
                    self._inc('pis_skipped')
                    continue

                c.platform_id = post.platform_id
                c.post = post
                c.content = comment['content']
                c.create_date = comment['date']
                c.if_liked = False
                c.if_shared = False
                c.if_commented = True
                c.save()
                self._inc('pis_saved')
                comments_list.append(c)
        print 'Saved post interactions:', len(comments_list)
        return comments_list

    def task_generator(self):
        grab = Grab()
        grab.setup(url=self.platform.url, user_agent=None, timeout=60, connect_timeout=20,
                   reuse_cookies=False, reuse_referer=False, follow_location=True,
                   proxy=self.get_proxy(), proxy_type=self.proxy_type)
        yield Task('blog', grab=grab, priority=10, page_number=1)

    def task_blog(self, grab, task):
        self.platform.inc_api_calls()
        print 'task_blog', grab.response.url

        if '404' in grab.response.status:
            return

        if grab.doc.select(
                '//div[contains(@id,"Blog")]//div[contains(translate(@class,"P","p"),"post")]').count():

            posts = grab.doc.select(
                '//div[contains(@id,"Blog")]//*[contains(@class,"post-title") or contains(@class,"postTitle")]/a')
            if not posts.count():
                posts = grab.doc.select(
                    '//div[contains(@id,"Blog")]//div[contains(@class,"Post")]//*[contains(@class,"PostHeader")]/a')
                if not posts.count():
                    posts = grab.doc.select(
                        '//div[contains(@id,"Blog")]//div[contains(@class,"blog-posts")]//a[@class="timestamp-link"]')
                    if not posts.count():
                        posts = grab.doc.select(
                            '//div[contains(@id,"Blog")]/div[@class="post"]/a[1]')

            if posts.count():
                for post in posts:
                    post_url = post.attr('href')
                    if urlparse(grab.response.url).netloc != urlparse(post_url).netloc:
                        continue
                    if not models.Posts.objects.filter(url=post_url, platform=self.platform).exists():
                        grab.setup(url=post_url, user_agent=None, proxy=self.get_proxy(), follow_location=False)
                        yield Task('post', grab=grab, priority=1)
                    else:
                        self._inc('posts_skipped')
                        print "Post %s, %s already exists " % (post_url, self.platform.url)

                if self.policy.should_continue_fetching(self) and \
                        (self.max_pages_to_scrape is None or task.page_number < self.max_pages_to_scrape):
                    older_posts = grab.doc.select('//div[@*="blog-pager"]//span[contains(@id,"older")]//a')
                    if older_posts.count():
                        older_posts_url = older_posts.attr('href')
                        grab.setup(url=older_posts_url, user_agent=None, proxy=self.get_proxy())
                        yield Task('blog', grab=grab, priority=5, page_number=task.page_number + 1)

    def task_post(self, grab, task):
        print 'task_post', grab.response.url

        self.platform.inc_api_calls()

        title = content = date = None

        # The Post's URL
        url = grab.response.url
        print "Checking url %s" % url
        # The Post's Title
        post_title = grab.doc.select(
            '//div[contains(@id,"Blog")]//*[contains(@class,"post-title") or contains(@class,"postTitle")]')
        if not post_title.count():
            post_title = grab.doc.select(
                '//div[contains(@id,"Blog")]//div[contains(@class,"Post")]//*[contains(@class,"PostHeader")]')
            if not post_title.count():
                post_title = grab.doc.select('//div[contains(@id,"Blog")]/div[@class="post"]/text()[1]')
        if post_title.count():
            title = post_title.text().strip()

        # The Post's Content
        post_content = grab.doc.select(
            '//div[contains(@id,"Blog")]//div[(contains(@class,"post-body") or contains(@class,"postBody"))]')
        if not post_content.count():
            post_content = grab.doc.select(
                '//div[contains(@id,"Blog")]//div[contains(@class,"Post")]//div[contains(@class,"PostContent")]')
        if post_content.count():
            content = post_content.html()
        else:
            return

        # The post date can be present in different variations
        # That's why we try to extract it from <abbr> (ISO format), after that from the date-header and finally from the URL
        # In the header the date can be present in different formats: "Tuesday, 6 December 2011", "February 18, 2014", etc.
        # Sometimes (http://www.tieandi.com/2014/02/valentines-day-wishlist.html) it's written not in English
        # In this case we can only get year and month from the url ("/2014/02/"") and we set day=1
        # We work with "date" over and over again, until this value is changed from None
        # But if the date is None after all tries... well, I have no idea about
        # when this post is published, may be a few thousands years ago?
        post_date = grab.doc.select('//div[contains(@class,"post-footer")]//abbr[contains(@class,"published")]/@title')
        # <abbr>
        if post_date.count():
            iso_date = post_date.text().strip()
            try:
                date = parse_iso_date(iso_date)
            except ValueError:
                # bad ISO-format? let's try another way
                pass
        # "date-header"
        if not date:
            post_date = grab.doc.select('//*[contains(@class,"date-header")]//span')
            if not post_date.count():
                post_date = grab.doc.select('//*[contains(@class,"date-header")]')
                if not post_date.count():
                    post_date = grab.doc.select('//div[contains(@class,"post")]/*[contains(@class,"postAuthor")]/a')
            if post_date.count():
                YMDhm = self.parse_date(post_date.text())
                if YMDhm:
                    date = datetime(*YMDhm)
            # URL
            if not date:
                url_path = urlparse(grab.response.url).path
                if url_path.startswith('/'):
                    url_path_parts = url_path.split('/')
                    month = year = None
                    year_from_url = url_path_parts[1]
                    month_from_url = url_path_parts[2]
                    if month_from_url.isdigit() and int(month_from_url) in range(1, 13):
                        month = int(month_from_url)
                    if year_from_url.isdigit() and int(year_from_url) in range(2000, 2020):
                        year = int(year_from_url)
                    if month and year:
                        date = datetime(year, month, 1, 0, 0)

        post = models.Posts()
        post.influencer = self.platform.influencer
        post.show_on_search = self.platform.influencer.show_on_search
        post.platform = self.platform
        post.title = title
        post.url = url
        post.content = content
        post.create_date = date
        post.save()
        self._inc('posts_saved')
        print "Created post: %s " % post
        self.posts[post] = []

        # Comments
        # This section also can be present in different variations
        comments = []
        # The first type
        comments_blocks = grab.doc.select(
            '//div[contains(@id,"comments")]//dl[contains(@id,"comments-block")]')
        if comments_blocks.count():
            comments_authors = comments_blocks.select('.//dt[contains(@class,"author")]')
            for author in comments_authors:
                author_name = author_url = url = None
                author_a = author.select('./a[@rel="nofollow"]')
                if not author_a.count():
                    author_a = author.select('.//a[@rel="nofollow"]')
                if author_a.count():
                    author_name = author_a.text().strip()
                    try:
                        author_url = author_a.attr('href')
                    except Exception:
                        pass
                comment_body = author.select('./following-sibling::dd[contains(@class,"comment-body")][1]')
                if comment_body.count():
                    content = comment_body.html()
                    # content = ' '.join([_.text().strip() for _ in comment_body.select('.//text()')])
                else:
                    continue
                comment_footer = author.select('./following-sibling::dd[contains(@class,"comment-footer")][1]')
                if comment_footer.count():
                    comment_timestamp = comment_footer.select('.//span[contains(@class,"comment-timestamp")]/a')
                else:
                    comment_timestamp = author.select('.//span[contains(@class,"comment-timestamp")]/a')
                if comment_timestamp.count():
                    try:
                        url = comment_timestamp.attr('href')
                    except Exception:
                        pass
                    timestamp = comment_timestamp.text()
                    if date and not str(date.year)[:-1] in timestamp and ':' in timestamp:
                        timestamp = '.'.join([str(_) for _ in (date.month, date.day, date.year)]) + ' ' + timestamp
                    YMDhm = self.parse_date(timestamp)
                    if YMDhm:
                        date = datetime(*YMDhm)
                comments.append(
                    dict(
                        author_name=author_name,
                        author_url=author_url,
                        content=content,
                        date=date,
                        url=url,
                    )
                )
        # The second type
        else:
            comments_blocks = grab.doc.select('//div[@*="comments"]//div[@*="comment-header"]')
            for comment_header in comments_blocks:
                author_name = author_url = url = None
                author = comment_header.select('.//cite[contains(@class,"user")]')
                if author.count():
                    author_a = author.select('./a')
                    if author_a.count():
                        author_name = author_a.text().strip()
                        try:
                            author_url = author_a.attr('href')
                        except Exception:
                            pass
                    else:
                        author_name = author.text().strip()
                else:
                    author = comment_header.select('.//a[contains(@class, "autor-name")]')
                    if author.count():
                        author_name = author.text().strip()
                        try:
                            author_url = author.attr('href')
                        except Exception:
                            pass
                comment_timestamp = comment_header.select(
                    './/span[contains(@class,"datetime") or contains(@class,"timestamp") or contains(@id,"timestamp")]/a')
                if comment_timestamp.count():
                    try:
                        url = comment_timestamp.attr('href')
                    except Exception:
                        pass
                    timestamp = comment_timestamp.text()
                    if date and not str(date.year)[:-1] in timestamp and ':' in timestamp:
                        timestamp = '.'.join([str(_) for _ in (date.month, date.day, date.year)]) + ' ' + timestamp
                    YMDhm = self.parse_date(timestamp)
                    if YMDhm:
                        date = datetime(*YMDhm)
                comment_body = comment_header.select(
                    './/p[contains(@class,"comment-content") or contains(@class,"comment-body")]')
                if not comment_body.count():
                    comment_body = comment_header.select(
                        './following-sibling::p[contains(@class,"comment-content") or contains(@class,"comment-body")][1]')
                if comment_body.count():
                    content = comment_body.html()
                    # content = ' '.join([_.text().strip() for _ in comment_body.select('.//text()')])
                else:
                    continue
                comments.append(
                    dict(
                        author_name=author_name,
                        author_url=author_url,
                        content=content,
                        date=date,
                        url=url,
                    )
                )
        print "got %d comments " % len(comments)
        for comment in comments:
            self.posts[post].append(comment)
        # this will call self.fetch_post_interactions() first to see if we got any comments
        # if not, disqus will be crawled
        self.fetch_post_interactions_extra([post])

    def parse_date(self, timestamp):
        day = month = year = None
        hours = minutes = 0
        timestamp = timestamp.strip().upper()
        PM = True if 'PM' in timestamp else False
        timestamp = (timestamp
                     .replace('PM', '')
                     .replace('AM', '')
                     .replace(',', '')
                     .replace('-', ''))
        if ':' in timestamp:
            delimiter_index = timestamp.index(':')
            h = timestamp[delimiter_index - 2:delimiter_index].strip()
            if h.isdigit() and int(h) in range(24):
                hours = int(h)
                if PM and hours < 12:
                    hours += 12
            m = timestamp[delimiter_index + 1:delimiter_index + 3].strip()
            if m.isdigit() and int(m) in range(60):
                minutes = int(m)
        timestamp_parts = timestamp.split(' ')[0].split('.')
        if not len(timestamp_parts) == 3:
            timestamp_parts = timestamp.split(' ')[0].split('/')
        if len(timestamp_parts) == 3 and all([_.isdigit() for _ in timestamp_parts]):
            month, day, year = [int(_) for _ in timestamp_parts]
            if year not in range(2000, 2020):
                return None
            if month in range(13, 32) and day in range(1, 13):
                month, day = day, month
            elif not (month in range(1, 13) and day in range(1, 32)):
                return None
        else:
            timestamp_parts = timestamp.split(' ')
            for part in timestamp_parts:
                if part.isdigit() and int(part) in range(1, 32):
                    day = int(part)
                elif part.isdigit() and int(part) in range(2000, 2020):
                    year = int(part)
                elif part in self.months_names:
                    month = self.months_names[part]
            if not all([day, month, year]):
                return None
        return year, month, day, hours, minutes


if __name__ == "__main__":
    infs = models.Influencer.objects.filter(platform__platform_name__in=["Facebook", "Twitter"], source__isnull=False,
                                            blog_url__isnull=False, platform__profile_img_url__isnull=False, relevant_to_fashion__isnull=True)
    plats = models.Platform.objects.filter(influencer__in=infs, platform_name="Blogspot")
    for i, plat in enumerate(plats):
        posts = models.Posts.objects.filter(platform=plat)
        if posts.count() > 5:
            continue
        try:
            bf = BlogspotFetcher(plat, None)
            posts = bf.fetch_posts(2)
            print "got posts %s " % posts
            print "now fetching post interactions"
            bf.fetch_post_interactions(posts)
            print "[%d] Done with %s " % (i, plat.url)
        except:
            pass
