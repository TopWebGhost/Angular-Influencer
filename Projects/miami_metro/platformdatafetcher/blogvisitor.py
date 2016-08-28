"""Generates traffic to an influencer's blog by fully simulating
a web browser visit (using Selenium and a mouse click).
"""

import logging
import time
import random
import json
import baker
from celery.decorators import task
from django.conf import settings

from platformdatafetcher import platformutils
from xpathscraper import xbrowser
from xpathscraper import utils
from debra import models


log = logging.getLogger('platformdatafetcher.blogvisitor')


@baker.command
def visit_url(url):
    xb = None
    try:
        xb = xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY)
        xb.load_url('http://app.theshelf.com/internal/')
        xb.driver.execute_script("""var a = document.createElement('a');
                                    a.href='%s';
                                    a.id = 'blogvisitor_to_click';
                                    a.innerHTML = 'I will click this';
                                    document.body.appendChild(a);""" % url.replace("'", "\\'"))
        a = xb.driver.find_element_by_id('blogvisitor_to_click')
        a.click()
        xb.driver.back()
    except:
        log.exception('visit_url(url={}) got an exception'.format(url), extra={'url': url})
    finally:
        try:
            if xb:
                xb.cleanup()
        except:
            log.exception('visit_url(url={}) got an exception while xb.cleanup()'.format(url))


@task(name='platformdatafetcher.blogvisitor.visit_platform', ignore_result=True)
@baker.command
def visit_platform(platform_id):
    plat = models.Platform.objects.get(id=int(platform_id))
    with platformutils.OpRecorder('visit_platform', platform=plat):
        visit_url(plat.url)


@task(name='platformdatafetcher.blogvisitor.visit_influencer', ignore_result=True, rate_limit='2/m')
def visit_influencer(influencer_id, pdo_id):
    influencer = models.Influencer.objects.get(id=influencer_id)
    pdo = models.PlatformDataOp.objects.get(id=pdo_id)
    log.info('visit_influencer for %r', influencer)
    opr = platformutils.OpRecorder(_pdo=pdo)
    try:
        visit_url(influencer.blog_url)
    except:
        opr.register_exception()
    else:
        opr.register_success()


@baker.command
def submit_visit_influencer_tasks(submission_tracker):
    infs = models.Influencer.objects.filter(show_on_search=True,
                                            #shelf_user_id__isnull=True,
                                            average_num_comments_per_post__gte=5).exclude(blacklisted=True)
    infs = infs.exclude(blog_url__contains='theshelf.com/artificial')
    log.info('%d influencers to be hit', infs.count())
    infs_to_hit = []
    hits_by_inf = {}
    for inf in infs:
        hits = random.randrange(int(inf.average_num_comments_per_post / 2 + 1))
        log.info('%r will be hit %d times', inf, hits)
        infs_to_hit += [inf] * hits
        hits_by_inf[inf] = hits
    log.info('Total hits: %d', len(infs_to_hit))
    random.shuffle(infs_to_hit)
    pdo_by_inf = {}
    for inf in infs_to_hit:
        if inf in pdo_by_inf:
            pdo = pdo_by_inf[inf]
            log.debug('Reusing pdo for %d', inf.id)
        else:
            pdo = models.PlatformDataOp(operation='visit_influencer', influencer=inf)
            pdo.data_json = json.dumps({'hits': hits_by_inf[inf]})
            pdo.save()
            pdo_by_inf[inf] = pdo
            log.debug('Created new pdo for %d', inf.id)

        submission_tracker.count_task('visit_influencer')
        visit_influencer.apply_async([inf.id, pdo.id], queue='blog_visit')


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
