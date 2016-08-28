"""Verifying influencer's fields algorithmically. This should take work from QA by using some
sure sources that can be checked automatically (currently Bloglovin is used). The verified fields are
written to :attr:`debra.models.Influencer.autoverified_fields`.
"""

import logging
import json

import baker
import requests
import lxml.html

from xpathscraper import utils
from xpathscraper import textutils
from celery.decorators import task
from platformdatafetcher import platformutils
from debra import models


log = logging.getLogger('platformdatafetcher.influencerverification')


class Verifier(object):

    def verify(self, influencer):
        """Must return None or a list of influencer's fields that are verified
        """
        raise NotImplementedError()


class BloglovinVerifier(Verifier):

    def verify(self, influencer):
        if not influencer.bloglovin_url:
            log.warn('No bloglogin_url')
            return []
        bloglovin_url = influencer.bloglovin_url.split()[0]
        r = requests.get(bloglovin_url)
        tree = lxml.html.fromstring(r.text)

        name_el = tree.xpath('//div[@class="blog-info"]/h1[@class="name"]')[0]
        name = name_el.text
        log.info('Blogger name from bloglovin: %r', name)

        url_el = tree.xpath('//div[@class="blog-info"]/div[@class="url"]/a')[0]
        url = url_el.text
        if not url.startswith('http'):
            url = 'http://%s' % url
        log.info('Blog url: %r', url)

        if platformutils.url_to_handle(url) == platformutils.url_to_handle(influencer.blog_url):
            log.info('Urls match')
            if textutils.same_word_sets(name, influencer.name):
                return ['name']
        else:
            log.warn('Urls do not match')


VERIFIERS = [
    BloglovinVerifier(),
]

@task(name='platformdatafetcher.influencerverification.verify', ignore_result=True)
@baker.command
def verify(influencer_id):
    influencer = models.Influencer.objects.get(id=int(influencer_id))
    with platformutils.OpRecorder(operation='verify', influencer=influencer) as opr:
        log.info('Verifying %r', influencer)
        fields = []
        info = {}
        for verifier in VERIFIERS:
            try:
                res = verifier.verify(influencer)
            except:
                log.exception('While running verifier %r', verifier)
                continue
            log.info('Result: %s', res)
            if res:
                fields.extend(res)
                info[verifier.__class__.__name__] = res
        log.info('Verified fields: %s', fields)
        log.info('Verification debug info: %s', info)
        old = json.loads(influencer.autoverified_fields or '[]')
        new = utils.unique_sameorder(old + fields)
        if old == new:
            log.info('Verification process did not add new fields, old value: %s', old)
        else:
            log.info('New autoverified_fields: %s', new)
            influencer.autoverified_fields = json.dumps(new)
            influencer.save()
        opr.data = {'fields': fields, 'info': info}

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
