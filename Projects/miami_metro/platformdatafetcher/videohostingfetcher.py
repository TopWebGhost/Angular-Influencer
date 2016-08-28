import re
import logging
from django.conf import settings
import requests
import lxml.html
from requests.exceptions import SSLError
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from debra.models import Posts
from platformdatafetcher import fetcherbase
from platformdatafetcher import platformutils
from platformdatafetcher.activity_levels import recalculate_activity_level
from xpathscraper import xbrowser, utils
import dateutil.parser
from masuka import image_manipulator
import datetime

log = logging.getLogger('platformdatafetcher.videohostingfetcher')


strip_not_numbers = re.compile(r'\D')


def numbers_only(formatted):
    return strip_not_numbers.sub('', formatted)


def deformat_int(raw_int):
    return int(numbers_only(raw_int))


class YoutubeFetcher(fetcherbase.Fetcher):
    name = 'Youtube'

    def __init__(self, platform, policy):
        fetcherbase.Fetcher.__init__(self, platform, policy)

        try:
            r = requests.get(platform.url, verify=False)
            r.raise_for_status()
        except requests.RequestException as e:
            platformutils.set_url_not_found('youtube_profile_doesnt_exist', platform)
            raise fetcherbase.FetcherException('Youtube url fetch failed: {}.'.format(e))

        self.tree = lxml.html.fromstring(r.content)

        if not self._ensure_has_validated_handle():
            raise fetcherbase.FetcherException('Cannot get validated_handle')

        fetcherbase.retry_when_call_limit(self._update_platform_details)
        fetcherbase.retry_when_call_limit(self._update_num_following)

    def get_validated_handle(self):
        href = self.tree.xpath('//a[contains(@class, "branded-page-header-title-link")]/@href')[0]
        return href

    def _update_platform_details(self):
        subscriber_texts = self.tree.xpath('//span[contains(@class, "yt-subscription-button-subscriber-count-branded-horizontal")]/text()')
        if subscriber_texts:
            self.platform.num_followers = deformat_int(subscriber_texts[0])
            self._update_popularity_timeseries()
        else:
            # The user could have hiddden the subscriber count
            self.platform.num_followers = 0

        self.platform.blogname = self.tree.xpath('//a[contains(@class, "branded-page-header-title-link")]/text()')[0]
        self.platform.profile_img_url = self.tree.xpath('//img[@class="channel-header-profile-image"]/@src')[0]
        if self.platform.profile_img_url:
            image_manipulator.save_social_images_to_s3(self.platform)
        # ok that's a problem, i can't fetch that unless i switch to xbrowser
        # print self.tree.xpath('//div[@id="c4-header-bg-container"]/div/div[@class="hd-banner-image"]')[0].value_of_css_property('background-image')
        # self.platform.cover_img_url = self.tree.xpath('')
        self.platform.save()

    def _update_num_following(self):
        try:
            with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, load_no_images=True) as xb:
                xb.load_url('https://www.youtube.com/{0}/channels?flow=grid&view=56'.format(self.platform.validated_handle))

                while True:         # potentially infinite loop?
                    no_break = False
                    try:
                        button = WebDriverWait(xb.driver, 10).until(expected_conditions.presence_of_element_located((By.CLASS_NAME, 'load-more-button')))
                        button.click()
                        no_break = True
                        continue
                    finally:
                        if not no_break:
                            break
                self.platform.num_following = len(xb.execute_jsfun('_XPS.evaluateXPath', '//li[contains(@class, "channels-content-item")]'))
                self.platform.save()
        except Exception as e:
            log.exception(e)

    def _do_fetch_posts(self, max_pages=None):
        res = []

        try:
            with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, load_no_images=True) as xb:
                videos_list_url = 'https://www.youtube.com/{0}/videos'.format(self.platform.validated_handle)
                xb.load_url(videos_list_url)

                while True:         # potentially infinite loop?
                    no_break = False
                    try:
                        button = WebDriverWait(xb.driver, 4).until(expected_conditions.presence_of_element_located((By.CLASS_NAME, 'load-more-button')))
                        button.click()
                        no_break = True
                        continue
                    finally:
                        if not no_break:
                            break
                urls = [el.get_attribute('href') for el in xb.execute_jsfun('_XPS.evaluateXPath', '//a[contains(@href, "watch?v=")]')] #'//h3[@class="yt-lockup-title"]/a')]

                def count_comments(post, iframe_src):
                    r = requests.get(iframe_src, verify=False)
                    tree = lxml.html.fromstring(r.content)
                    raw_comments_count = tree.xpath('//div[@class="DJa"]/strong')[0].tail.strip()
                    post.ext_num_comments = int(raw_comments_count[1:-1])        # chopping off the parenthesis
                    post.has_comments = True

                for url in set(urls):
                    if not self.policy.should_continue_fetching(self):
                        break

                    xb.load_url(url)
                    description_button = xb.execute_jsfun('_XPS.evaluateXPath', '//button[contains(@class, "yt-uix-expander-collapsed-body")]')
                    try:
                        if description_button and len(description_button) > 0:
                            description_button[0].click()      # expanding the description
                    except:
                        pass
                    video_id = xb.execute_jsfun('_XPS.evaluateXPath', '//meta[@itemprop="videoId"]')[0].get_attribute('content')
                    url = 'https://youtube.com/watch?v=' + video_id

                    previously_saved = list(Posts.objects.filter(url=url, platform=self.platform))
                    if previously_saved:
                        if self.should_update_old_posts():
                            log.debug('Updating existing post for url {}'.format(url))
                            post = previously_saved[0]
                        else:
                            self._inc('posts_skipped')
                            log.debug('Skipping already saved post with url {}'.format(url))
                            if not self.test_run:
                                continue
                    else:
                        log.debug('Creating new post for url {}'.format(url))

                        post = Posts(
                            url=url,
                            platform=self.platform,
                            influencer=self.platform.influencer,
                            show_on_search=self.platform.influencer.show_on_search,
                        )
                        post.title = xb.execute_jsfun('_XPS.evaluateXPath', '//*[@id="watch-headline-title"]//span')[0].text
                        # post.content = xb.execute_jsfun('_XPS.evaluateXPath', '//meta[@itemprop="description"]')[0].get_attribute('content')
                        post.impressions = deformat_int(xb.execute_jsfun('_XPS.evaluateXPath', '//div[@class="watch-view-count"]')[0].text.split()[0])
                        post.post_image = xb.execute_jsfun('_XPS.evaluateXPath', '//link[@itemprop="thumbnailUrl"]')[0].get_attribute('href')
                        post.post_image_width = int(xb.execute_jsfun('_XPS.evaluateXPath', '//meta[@itemprop="width"]')[0].get_attribute('content'))
                        post.post_image_height = int(xb.execute_jsfun('_XPS.evaluateXPath', '//meta[@itemprop="height"]')[0].get_attribute('content'))
                        post.content = xb.execute_jsfun('_XPS.evaluateXPath', '//p[@id="eow-description"]')[0].text
                        create_date_str = xb.execute_jsfun('_XPS.evaluateXPath', '//div[@id="watch-uploader-info"]')[0].text
                        x = create_date_str.find('Published on')
                        if x >= 0:
                            x = x + len('Published on ')
                            create_date_str = create_date_str[x:]
                            create_date = dateutil.parser.parse(create_date_str)
                            post.create_date = create_date
                    try:
                        iframe = WebDriverWait(xb.driver, 10).until(expected_conditions.presence_of_element_located((By.TAG_NAME, 'iframe')))
                        iframe_src = iframe.get_attribute('src')
                        for i in range(3):
                            try:
                                count_comments(post, iframe_src)
                            except:
                                pass
                            else:
                                break
                    finally:
                        pass

                    self.save_post(post)
                    res.append(post)
        except Exception as e:
            log.exception(e)

        self.fetch_post_interactions(res)
        return res

    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):

        # Setting platform's last_fetched date
        if self.platform is not None:
            self.platform.last_fetched = datetime.datetime.now()
            self.platform.save()

        return fetcherbase.retry_when_call_limit(lambda: self._do_fetch_posts(max_pages))

    def fetch_post_interactions(self, posts, max_pages=None):
        for p in posts:
            print("Fetching interactions for %r" % p)
            try:
                r = requests.get(p.url, verify=False)
                tree = lxml.html.fromstring(r.content)
                create_date = tree.xpath('//div[@id="watch-uploader-info"]')
                if not p.create_date:
                    p.create_date = create_date
                    p.save()
                e = tree.xpath('//button[contains(@class, "like-button-renderer-like-button")]/span')
                print("Got %r elements" % e)
                if e and len(e) >= 1:
                    e = e[0]
                    txt = e.text
                    num_likes = deformat_int(txt)
                    p.engagement_media_numlikes = num_likes
                    print("NUM_LIKES: %r %d" % (p.url, num_likes))
                    p.save()
                e = tree.xpath('//div[@class="watch-view-count"]')
                print("Got %r elements" % e)
                if e and len(e) == 1:
                    e = e[0]
                    txt = e.text
                    num_impressions = deformat_int(txt)
                    p.impressions = num_impressions
                    print("NUM_VIEWS: %r %d" % (p.url, p.impressions))
                    p.save()
                # TODO: for comments, we may have to use xbroswer, skipping for now
                p.save()
            except:
                print("Problem fetching likes count for %r" % p.url)
                pass
        return []

    @classmethod
    def get_description(cls, url, xb=None):
        """
        Getting description field from Youtube. For now, we're just collecting links to other platforms so that
        we can validate if this url belongs to the blog.
        """
        # remove query params
        # e.g.: http://www.youtube.com/user/zoella280390?feature=mhee => http://www.youtube.com/user/zoella280390
        url = utils.remove_query_params(url)
        if url.endswith('/'):
            about_page = url + "about"
        else:
            about_page = url + "/about"

        res = set()
        try:
            r = requests.get(about_page, verify=False)
            tree = lxml.html.fromstring(r.content)
            social_links = tree.xpath('//a[contains(@class,"about-channel-link")]/@href')
            for s in social_links:
                res.add(s)
        except SSLError:
            # encountered SSLError - retrying with verify=False
            r = requests.get(about_page, headers=utils.browser_headers(), verify=False)
            tree = lxml.html.fromstring(r.content)
            social_links = tree.xpath('//a[contains(@class,"about-channel-link")]/@href')
            for s in social_links:
                res.add(s)

        return '\n'.join(res)