import logging
import re
import json
import pprint

import baker
from celery.decorators import task
import requests
import lxml.html

from platformdatafetcher import platformutils
from xpathscraper import utils
from xpathscraper import xutils
from debra import models


log = logging.getLogger('platformdatafetcher.scrapingfetcher')


class ScrapingFetcher(object):
    name = None

    def __init__(self, platform):
        self.platform = platform

    def scrape(self):
        raise NotImplementedError()


class InstagramScrapingFetcher(ScrapingFetcher):
    name = 'Instagram'

    def scrape(self):
        r = requests.get(self.platform.url, timeout=10)
        m = re.search('''"counts"\s*:\s*({[^}]*})''', r.text)
        assert m, 'Cannot parse instagram counts'
        counts = json.loads(m.group(1))
        log.info('Filling counts data for %r: %r', self.platform, counts)
        self.platform.num_followers = counts['followed_by']
        self.platform.num_following = counts['follows']
        self.platform.numposts = counts['media']
        self.platform.save()


SCRAPING_FETCHER_CLASSES = [
    InstagramScrapingFetcher,
]

PLATFORM_NAME_TO_SCRAPING_FETCHER = {cls.name: cls for cls in SCRAPING_FETCHER_CLASSES}


@task(name='platformdatafetcher.scrapingfetcher.scrape_platform_data', ignore_result=True)
@baker.command
def scrape_platform_data(platform_id):
    platform = models.Platform.objects.get(id=int(platform_id))
    with platformutils.OpRecorder(operation='scrape_data', platform=platform):
        if platform.platform_name not in PLATFORM_NAME_TO_SCRAPING_FETCHER:
            log.error('No scraping fetcher for platform_name %r', platform.platform_name)
            raise Exception('No scraping fetcher for platform_name %r' % platform.platform_name)
        sf = PLATFORM_NAME_TO_SCRAPING_FETCHER[platform.platform_name](platform)
        sf.scrape()


@task(name='platformdatafetcher.scrapingfetcher.scrape_instagram_post_caption', ignore_result=True)
@baker.command
def scrape_instagram_post_caption(post_id):
    post = models.Posts.objects.get(id=int(post_id))
    r = requests.get(post.url)
    data_match = re.search(r'sharedData[^{]+({.*);', r.content)
    if not data_match:
        log.warn('No data for %r', post)
        return
    data = json.loads(data_match.group(1))
    caption = utils.nestedget(data, 'entry_data', 'DesktopPPage', 0, 'media', 'caption')
    if caption:
        post.content = caption
    else:
        log.warn('No caption for %r from %r', post, data)

    image = utils.nestedget(data, 'entry_data', 'DesktopPPage', 0, 'media', 'display_src')
    if image:
        post.post_image = image
        post.content = ' '.join([post.content or '', image])
    else:
        log.warn('No image for %r from %r', post, data)

    log.info('Scraped content %r image %r', post.content, post.post_image)
    post.save()

@baker.command
def submit_scrape_instagram_post_caption_tasks():
    posts = models.Posts.objects.filter(platform__platform_name='Instagram',
                                        post_image__isnull=True)
    for post in posts:
        scrape_instagram_post_caption.apply_async([post.id], queue='platform_data_postprocessing')

@task(name='platformdatafetcher.scrapingfetcher.scrape_pin_source', ignore_result=True)
@baker.command
def scrape_pin_source(post_id):
    post = models.Posts.objects.get(id=int(post_id))
    r = requests.get(post.url, headers=utils.browser_headers())
    tree = lxml.html.fromstring(r.text)
    anchor_els = tree.xpath('//div[@class="sourceFlagWrapper"]/a')
    if not anchor_els:
        log.warn('No anchor els')
        return
    href = anchor_els[0].attrib.get('href')
    if not href:
        log.warn('No href')
        return
    post.pin_source = utils.remove_fragment(href)
    post.save()
    log.info('Saved pin source %r', post.pin_source)

@baker.command
def submit_scrape_pin_source_tasks():
    posts = models.Posts.objects.filter(platform__platform_name='Pinterest',
                                        pin_source__isnull=True)
    for post in posts:
        scrape_pin_source.apply_async([post.id], queue='platform_data_postprocessing')


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
