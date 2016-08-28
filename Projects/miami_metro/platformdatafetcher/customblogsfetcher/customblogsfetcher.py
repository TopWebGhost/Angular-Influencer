#!/usr/bin/env python
# -*- coding: utf-8 -*-
# customblogsfetcher
#
####################################################################################################

import logging
from time import sleep
from webxtractor import BlogXtractor, PostXtractor, WebXtractorError, BlogContainer
from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from pyvirtualdisplay import Display
from platformdatafetcher.fetcherbase import Fetcher
from platformdatafetcher.activity_levels import recalculate_activity_level
from debra import models
from django.conf import settings
####################################################################################################

# dir_ = os.path.dirname(os.path.abspath(__file__))

#logfile = os.path.join(dir_, 'customblogsfetcher.log')
format = '[%(asctime)s]:[%(levelname)s/%(module)s] %(message)s'
datefmt = '%I:%M:%S'
LOGGER = logging.getLogger('customblogsfetcher')
LOGGER.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(format, datefmt)
handler.setFormatter(formatter)
LOGGER.addHandler(handler)
LOGGER.propagate = False

####################################################################################################

FIREFOX_PATH = None
FIREFOX_PAGE_LOAD_TIMEOUT = 60
FIREFOX_PROFILE_PREFERENCES = (
    ('permissions.default.stylesheet', 2),
    ('permissions.default.image', 2),
    ('dom.ipc.plugins.enabled.libflashplayer.so', False),
    ('browser.safebrowsing.enabled', False),
    ('browser.shell.checkDefaultBrowser', False),
    ('browser.startup.page', 0),
    ('extensions.checkCompatibility', False),
    ('extensions.checkUpdateSecurity', False),
    ('extensions.update.autoUpdateEnabled', False),
    ('extensions.update.enabled', False),
    ('network.prefetch-next', False),
)

####################################################################################################


class Firefox(object):

    def __init__(self):
        if FIREFOX_PATH:
            firefox_binary = FirefoxBinary(firefox_path=FIREFOX_PATH)
        else:
            firefox_binary = None
        firefoxProfile = FirefoxProfile()
        for _ in FIREFOX_PROFILE_PREFERENCES:
            firefoxProfile.set_preference(*_)
        self.firefox = webdriver.Firefox(
            firefox_profile=firefoxProfile,
            firefox_binary=firefox_binary
        )
        self.firefox.set_page_load_timeout(FIREFOX_PAGE_LOAD_TIMEOUT)

    def get(self, url):
        try:
            self.firefox.get(url)
            return self.firefox.page_source
        except Exception as e:
            LOGGER.error('FIREFOX_ERROR: %s, URL: %s' % (str(e), url))
            return None

    def url(self):
        return self.firefox.current_url

    def quit(self):
        self.firefox.quit()

####################################################################################################


class CustomBlogsFetcher(Fetcher):

    name = 'Custom'

    def __init__(self, platform, policy):
        self.platform = platform
        self.blogxtractor = BlogXtractor()
        self.postxtractor = PostXtractor()
        # please do not remove this, in debug settings, we want to see the display
        if not settings.DEBUG:
            self.display = Display(visible=False)
        self.posts = {}
        Fetcher.__init__(self, platform, policy)

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):
        self.stop_page = max_pages if max_pages else -1
        if not settings.DEBUG:
            self.display.start()
        self.firefox = Firefox()
        try:
            self.run()
        except Exception as e:
            LOGGER.error('CUSTOMBLOGSFETCHER_RUN_ERROR: %s' % str(e))
        finally:
            self.firefox.quit()
            if not settings.DEBUG:
                self.display.stop()
        return self.posts.keys()

    def fetch_post_interactions(self, posts):
        comments = []
        for post in posts:
            if post in self.posts:
                comments.extend(self.posts[post])
        return comments

    def run(self):
        LOGGER.info("Processing: %s" % self.platform.url)
        next_page_url = self.platform.url
        processed_posts = []
        blog_container = BlogContainer()
        while self.stop_page and next_page_url:
            sleep(3)
            html = self.firefox.get(next_page_url)
            next_page_url = self.firefox.url()
            if html is None:
                break
            try:
                blog_container = self.blogxtractor.extract(
                    url=next_page_url,
                    html=html,
                    prev_page_url=blog_container.current_page_url,
                    prev_page_number=blog_container.current_page_number,
                    processed_posts=processed_posts,
                )
            except WebXtractorError as e:
                LOGGER.error('BLOGXTRACTOR_ERROR: %s, URL: %s' % (str(e), next_page_url))
                break
            next_page_url = blog_container.next_page_url
            processed_posts.extend(blog_container.posts)
            self.stop_page -= 1
            for post in blog_container.posts:
                if models.Posts.objects.filter(url=post.url, platform=self.platform).exists():
                    continue
                sleep(3)
                html = self.firefox.get(post.url)
                if html is None:
                    continue
                try:
                    post_container = self.postxtractor.extract(
                        url=post.url,
                        html=html,
                        title=post.title,
                    )
                except WebXtractorError as e:
                    LOGGER.error('POSTXTRACTOR_ERROR: %s, URL: %s' % (str(e), post.url))
                    continue
                if post_container.html is None:
                    continue
                self.create_post(post_container)

    def create_post(self, post_container):
        post = models.Posts()
        post.influencer = self.platform.influencer
        post.show_on_search = self.platform.influencer.show_on_search
        post.platform = self.platform
        post.title = post_container.title
        post.url = post_container.url
        post.content = post_container.html
        post.create_date = post_container.publish_date

        self.save_post(post)

        self.posts[post] = []
        for comment_container in post_container.comments:
            comment = self.save_comment(comment_container, post)
            if comment is not None:
                self.posts[post].append(comment)

    def save_comment(self, comment_container, post):
        if models.PostInteractions.objects.filter(
            post=post,
            content=comment_container.html
        ).exists():
            return
        comment = models.PostInteractions()
        if comment_container.author_name or comment_container.author_url:
            follower, created = models.Follower.objects.get_or_create(
                firstname=comment_container.author_name,
                url=comment_container.author_url
            )
            comment.follower = follower
        comment.platform_id = post.platform_id
        comment.post = post
        comment.content = comment_container.html
        comment.create_date = comment_container.publish_date
        comment.if_liked = False
        comment.if_shared = False
        comment.if_commented = True
        comment.save()
        return comment

####################################################################################################
