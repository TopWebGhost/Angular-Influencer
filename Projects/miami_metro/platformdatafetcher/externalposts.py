"""An extension of :class:`debra.models.Posts` fetching done normally by fetchers and
fetcher policies. This module uses non-standard sources for acquiring posts.
"""

import logging
import pprint
import urlparse
import random
import time

import baker
from celery.decorators import task
from django.conf import settings
from debra import models

from xpathscraper import utils
from xpathscraper import xbrowser
from platformdatafetcher import platformutils
from platformdatafetcher import socialfetcher


log = logging.getLogger('platformdatafetcher.externalposts')


PINTEREST_ACCOUNTS = [
    ('our.newsletter.list@gmail.com', 'ssssavvy'),
    ('laurensingh.stores@gmail.com', 'windstorm_in_vegas'),
]

def login_to_pinterest(xb, email, password):
    xb.load_url('https://www.pinterest.com/login/')
    email_field = xb.el_by_xpath('//li[@class="loginUsername"]/input')
    email_field.send_keys(email)
    password_field = xb.el_by_xpath('//li[@class="loginPassword"]/input')
    password_field.send_keys(password)
    button = xb.el_by_xpath('//div[@class="formFooterButtons"]/button')
    button.click()
    time.sleep(5)

def login_to_pinterest_using_random_account(xb):
    email, password = random.choice(PINTEREST_ACCOUNTS)
    login_to_pinterest(xb, email, password)


class PinsBySourceFetcher(object):

    def __init__(self, xb, source_influencer):
        assert source_influencer.blog_url
        log.info('Fetching pins from /source/ page for %r', source_influencer)
        self.source_influencer = source_influencer
        self.pin_platform = self.source_influencer.platform_set.filter(platform_name='Pinterest').\
            exclude(url_not_found=True)[0]
        self.xb = xb
        # login_to_pinterest_using_random_account(self.xb)
        source = urlparse.urlparse(source_influencer.blog_url).netloc
        self.xb.load_url('http://www.pinterest.com/source/%s/' % source)

    def fetch(self):
        self.pins = socialfetcher.PinterestFetcher.fetch_pins(self.xb)
        #pprint.pprint(self.pins)
        res = []
        for p in self.pins:
            if models.Posts.objects.filter(url=p['url'], platform=self.pin_platform).exists():
                log.debug('Skipping already saved pin with url %s', p['url'])
                continue
            post = models.Posts()
            post.influencer = self.source_influencer
            post.show_on_search = self.source_influencer.show_on_search
            post.platform = self.pin_platform
            post.api_id = p['id']
            post.url = p['url']
            post.content = p.get('description')
            if p.get('img'):
                if not post.content:
                    post.content = p.get('img')
                else:
                    post.content += ' ' + p.get('img')
            # create_date set in fetch_post_interactions method
            post.engagement_media_numlikes = int(p['likeCount']) if p.get('likeCount') else None
            post.engagement_media_numrepins = int(p['repinCount']) if p.get('repinCount') else None
            post.pinned_by = socialfetcher.PinterestFetcher.convert_pinned_by(p.get('pinnedBy'))
            log.debug('Saving new post %r', post)
            res.append(post)

        for post in res:
            post.save()

        return res


@baker.command
def fetch_pins_by_source(influencer_id):
    influencer = models.Influencer.objects.get(id=int(influencer_id))
    try:
        with platformutils.OpRecorder('fetch_pins_by_source', influencer=influencer):
            f = PinsBySourceFetcher(influencer)
            f.fetch()
    except Exception as e:
        log.exception(e, exc_info=1, extra={'influencer_id': influencer_id})



if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
