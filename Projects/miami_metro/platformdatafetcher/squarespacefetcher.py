import datetime
import logging
import urlparse

import dateutil.parser
import requests
from lxml.html import fromstring

from debra.models import Posts
from platformdatafetcher import fetcherbase
from platformdatafetcher.activity_levels import recalculate_activity_level
from platformdatafetcher.fetch_blog_posts_manually import (
    get_all_comments_number,
)
from platformdatafetcher.platformextractor import REQUESTS_HEADERS

log = logging.getLogger('platformdatafetcher.squarespacefetcher')

# timeout used for fetching page's content
PAGE_FETCH_TIMEOUT = 10


class SquarespaceFetcher(fetcherbase.Fetcher):
    """
    Fetcher for Squarespace blog platforms.

    Implements three methods of parent Fetcher class:

     * fetch_posts -- returns a list of models.Posts of fetched posts
     * fetch_post_interactions -- returns models.PostInteractions list for a given models.Posts list
     * fetch_platform_followers -- creates models.PlatformFollower objects
        (and saves them in the database) and returns them as a list.

    All methods must accept max_pages kwarg.
    """

    name = "Squarespace"

    def __init__(self, platform, policy, overwrite_existing=False):
        super(SquarespaceFetcher, self).__init__(platform, policy)

        self.parsed_base_url = urlparse.urlparse(self.platform.url)

        if overwrite_existing is True:
            self.force_fetch_all_posts = True

    def _check_articles_exist(self, page_url):
        """
        checks if blog articles exist on page
        :return:
        """
        # TODO: check if the url or url domain + '/blog/' is the correct one.
        try:
            r = requests.get(
                url=page_url, timeout=PAGE_FETCH_TIMEOUT,
                headers=REQUESTS_HEADERS
            )
            r.raise_for_status()
            page = fromstring(r.content)
            articles = page.xpath("//body//article[(starts-with(@id, 'article-'))]")
            return len(articles) > 0
        except Exception as e:
            log.exception(e)
        return False

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):
        """
        Fetching posts for current platform for current number of pages.
        There is a problem that number of posts per page can be different, even 1 post per page.

        IMPORTANT: Currently platform.url should point to page with entries list.

        Technical info for post fetching:
        blog url:
            platform.url + '/blog'
        xpath to posts list on page:
            article/
        xpath to post's urls in post list::
            /h1/a (first a, with urls like /blog/<something>)

        Pagination:
        xpath to pagination block:
            body//...//nav[@class contains='pagination']/
        xpath to older url:
            /div[class='older']
                /a[href='URL TO PREVIOUS PAGE']
        xpath to newer url:
            /div[class='newer']
                /a[href='URL TO PREVIOUS PAGE']

        :param max_pages: -- how many pages of this blog should be performed
        :return:
        """

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        result = []

        if not isinstance(max_pages, int) or max_pages >= 9999:
            log.debug('max_pages is %s, exiting...' % max_pages)
            return

        log.debug('Fetching posts from url %r, pages: %s' % (self.platform.url, max_pages))

        self._assure_valid_platform_url()

        # Performing blog platform
        current_page = 1

        current_page_url = None

        if self._check_articles_exist(self.platform.url):
            current_page_url = self.platform.url

        if current_page_url is None:
            try:
                blog_url_parsed = urlparse.urlparse(self.platform.url)
                blog_url_parsed = blog_url_parsed._replace(path='/blog/').geturl()
                if self._check_articles_exist(blog_url_parsed):
                    current_page_url = blog_url_parsed
            except Exception as e:
                log.exception(e)

        if current_page_url is not None:
            while current_page <= max_pages:

                log.debug('===== Page %s =====' % current_page)

                # fetching list of articles from pages
                r = requests.get(
                    url=current_page_url, timeout=PAGE_FETCH_TIMEOUT,
                    headers=REQUESTS_HEADERS
                )
                r.raise_for_status()

                page = fromstring(r.content)
                log.debug('Length page: %s' % len(r.content))

                page.make_links_absolute("%s://%s" % (self.parsed_base_url.scheme, self.parsed_base_url.netloc))

                articles = page.xpath("//body//article")
                # performing fetched posts
                if articles:
                    log.debug('Articles detected: %s' % len(articles))

                    for article in articles:

                        article_id = article.attrib.get('id', None)

                        post_url = None  # detected url of current post

                        header_tags = ['h1', 'h2', 'h3']
                        post_urls_found = None
                        for h in header_tags:
                            post_urls_found = article.xpath(".//%s//a/@href" % h)
                            if len(post_urls_found) > 0:
                                break

                        if post_urls_found:
                            post_url = post_urls_found[0]

                        if post_url is not None:

                            # Finding if we already have this post
                            existing_posts = list(Posts.objects.filter(url=post_url, platform=self.platform))
                            if existing_posts:
                                if not self.should_update_old_posts():
                                    self._inc('posts_skipped')
                                    log.debug('Skipping post that already exist: %r, id: %s' % (
                                        post_url, existing_posts[0].id)
                                    )
                                    continue
                                else:
                                    post = existing_posts[0]
                                    log.debug('Updating post that already exist: %r, id: %s' % (
                                        post_url, existing_posts[0].id)
                                    )
                            else:
                                post = Posts()

                            log.debug('Post url: %s' % post_url)
                            data = self._fetch_single_post_data(post_url)

                            # validating data and creating a post?
                            if data:

                                post.influencer = self.platform.influencer
                                post.show_on_search = self.platform.influencer.show_on_search
                                post.platform = self.platform

                                post.title = data.get('title', u'')
                                post.url = post_url

                                post.content = data.get('content', u'')
                                post.create_date = data.get('date_published', None)
                                post.api_id = str(article_id)

                                # TODO: test save posts
                                self.save_post(post)
                                result.append(post)

                        else:
                            log.debug('Post url was not found, skipping article')

                        # # TODO: Temp
                        # return result
                else:
                    log.debug('No articles detected')

                # performing pagination: finding url for previous page and increasing
                prev_pages = page.xpath(
                    "//body//nav//a[(contains(@href, 'offset=') and not(contains(@href, 'reversePaginate=')))]/@href"
                )
                if prev_pages:
                    log.debug('Older blog page url: %s' % prev_pages[0])
                    current_page_url = prev_pages[0]
                else:
                    log.debug('Last page of the blog was reached')
                    current_page = 9999

                if current_page == max_pages:
                    current_page = 9999
                else:
                    current_page += 1

        else:
            log.error('Platform %s does not seems to have url %s to be a blog url for Squarespace' % (
                self.platform.id,
                self.platform.url)
            )

        return result

    def _fetch_single_post_data(self, post_url=None):
        """
        This method fetches data from provided post url:
            * post title
            * post content
            * comments count (?)
            * date/time when the post was posted (?)

        xpaths:
            post title:
                //article//h1//a/text()
            post content:
                //article//p/text()
                - strip that from all non-text tags (scripts, imgs, etc...), leave only text (a href => text)
            post date:
                ????
            post comment counts
                ????
        :param post_url:
        :return:
        """
        result = None

        log.info("Trying to get data for post %r..." % post_url)

        try:
            # fetching list of articles from pages
            r = requests.get(
                url=post_url, timeout=PAGE_FETCH_TIMEOUT,
                headers=REQUESTS_HEADERS
            )
            r.raise_for_status()

            post_page = fromstring(r.content)
            post_page.make_links_absolute("%s://%s" % (self.parsed_base_url.scheme, self.parsed_base_url.netloc))

            result = {}

            # fetching title
            titles = post_page.xpath("//body//article//h1//a/text()")
            # performing fetched posts
            if titles:
                result['title'] = titles[0]
                log.debug("Title: %r" % result['title'])
            else:
                log.warn("No title found for post url %r" % post_url)

            # fetching content
            contents = post_page.xpath("//body//article//p")
            # performing fetched posts
            if contents:
                log.debug('Found %s <p> tags with text there' % len(contents))
                texts = []
                for c in contents:
                    for chunk in c.itertext():
                        if chunk is not None:
                            texts.append(chunk)

                result['content'] = u" ".join([u" ".join(t.split()) for t in texts])
                log.debug("Content: %r" % result['content'][:50])
            else:
                log.warn("No content found for post url %r" % post_url)

            # fetching date of creation
            # searching for <time> tag in /article and its datetime or text attribute
            times = post_page.xpath("//body//article//time[contains(@class, 'publish')]")
            if not times:
                times = post_page.xpath("//body//article//time")
            if times:
                post_time_str = None
                for t in times:
                    post_time_str = t.attrib.get('datetime', None)
                    if post_time_str is None and len(t.text().strip()) > 0:
                        post_time_str = t.text().strip()
                        break

                if post_time_str is not None:
                    result['date_published'] = dateutil.parser.parse(post_time_str)
                    log.debug("Publish date: %s" % result['date_published'])
                else:
                    log.warn("No publish date was found in <times> for post url %s" % post_url)
            else:
                log.warn("No publish date was found for post url %r" % post_url)

        except Exception as e:
            # Catching that raise_for_status() exception
            log.exception(e)

        return result

    def fetch_post_interactions(self, posts, max_pages=None):
        """
        Currently we do not retrieve comments, just comment counts

        :param posts:
        :param max_pages:
        :return:
        """
        # fetching posts counts
        for post in posts:
            try:
                comments_number = get_all_comments_number(post.url)
                post.engagement_media_numcomments = comments_number
                post.ext_num_comments = comments_number
                post.save()
            except:
                pass

        return []

    def fetch_platform_followers(self, max_pages=2, follower=True):
        result = None
        return result

    def _assure_valid_platform_url(self):
        """
        Check if this platform is really a Squarespace platform.
        :return:
        """
        return check_if_squarespace_url(self.platform.url)


def check_if_squarespace_url(url=None):
    """
    Function to check if this url belongs to Squarespace.
    Simple and easy check: we consider it a Squarespace url if it has '<!-- This is Squarespace. -->' token inside.

    If that would be not enough, we can think of more elaborate check.

    :param url:
    :return:
    """
    try:
        r = requests.get(url=url, timeout=10, headers=REQUESTS_HEADERS)
        r.raise_for_status()
        return '<!-- This is Squarespace. -->' in r.content
    except:
        pass

    return None
