"""
update a Platform object for each of the supplied blogs
@param blogs - a list of dictionaries representing blogs and having format:
[{
  'blog_url': '<url>',
  'blog_name': '<name>',
  'post_title': '<xpath>',
  'post_content': '<xpath>',
  'post_date': '<xpath>',
  'post_urls': '<xpath>',
  'post_comments': '<xpath>',
  'next_page': '<xpath>',
}]
@param start_index - the starting point for iterating over blogs. We include this so that if we hit an error,
we can restart from that blog rather then the beginning.
@param end_index - the end point for iterating over blogs. We use this so we can distribute blog processing
over multiple machines.
@param max_posts - the maximum number of posts to fetch per page, if not provided fetch all
@param max_pages - the maximimum number of pages to fetch per blog, if not provided fetch all
@return number of platforms updated if operation completed sucessfully, None if an error occurred

Note: Bad ones: http://amandaberg.webblogg.se/,  http://crystalinmarie.com/
"""

import logging
from pprint import pformat
import os
from collections import defaultdict, OrderedDict
import json

from celery.decorators import task
from iso8601 import ParseError, parse_date
import parsedatetime
import baker
import datetime
from django.conf import settings
from django import db

from xpathscraper import xbrowser
from xpathscraper import utils
from debra import helpers
from debra import models


log = logging.getLogger('platformdatafetcher.customblogs')

def _read_blogs():
    blogs = helpers.read_csv_file('blog_xpaths.tsv', delimiter='\t',
                            dict_keys=['blog_name', 'blog_url', 'post_urls', 'post_title', 'post_content', 'post_date',
                                       'post_comments', 'next_page', ''])
    return blogs

@baker.command
def submit_custom_blog_tasks(start_index, end_index, nocelery='0'):
    start_index = int(start_index)
    end_index = int(end_index)
    blogs = _read_blogs()
    log.info('Processing blogs: %s', pformat(blogs[start_index:end_index]))
    for blog in blogs[start_index:end_index]:
        if int(nocelery):
            handle_blog(blog)
        else:
            handle_blog.apply_async(args=[blog], queue='update_blog_from_xpath')

@baker.command
def submit_blog_task_by_url(url):
    blogs = _read_blogs()
    matching = [b for b in blogs if utils.domain_from_url(url) == utils.domain_from_url(b['blog_url'])]
    log.info('Found matching blogs: %r', matching)
    if not matching:
        return
    handle_blog(matching[0])

def _find_platform(blog_url):
    blog_domain = utils.domain_from_url(blog_url)
    pl_candidates = models.Platform.objects.filter(url__contains=blog_domain)
    for pl in pl_candidates:
        if utils.domain_from_url(pl.url) == blog_domain:
            return pl
    return None

@task(name='platformdatafetcher.customblogs.handle_blog', ignore_result=True)
def handle_blog(blog):
    platform = _find_platform(blog['blog_url'])
    if platform is None:
        models.OperationStatus.inc('custom_blog', blog['blog_url'], 'init_platform', 'notfound', None)
        return
    ft = models.FetcherTask.objects.create(
        platform=platform,
        started=datetime.datetime.now(),
        server_ip=utils.get_ip_address(),
        process_pid=str(os.getpid()),
        policy_name='custom_blog',
    )
    xb = None
    counts = {}
    try:
        xb = xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, width=1200, height=800)
        log.info('Processing blog %r', blog)
        counts = _do_handle_blog(blog, xb)
    except Exception as e:
        log.exception('While processing %r', blog)
        try:
            db.close_connection()
        except:
            log.exception('While resetting connection')
        models.OperationStatus.inc('custom_blog', blog.get('blog_url'), 'processing', 'exception',
                                   e.__class__.__name__)
        pass
    finally:
        if xb is not None:
            try:
                xb.cleanup()
            except:
                log.exception('While xb.cleanup(), ignoring')
    ft.duration = (datetime.datetime.now() - ft.started).total_seconds()
    ft.posts_saved = counts.get('posts_saved')
    ft.pis_saved = counts.get('pis_saved')
    ft.save()


def _do_handle_blog(blog, xb, max_posts=1000, max_pages=1000):
    counts = defaultdict(int)
    url, name = blog.get('blog_url'), blog.get('blog_name')
    # xpaths
    p_urls_x = blog.get('post_urls')
    p_title_x, p_content_x = blog.get('post_title'), blog.get('post_content')
    p_date_x, p_comments_x = blog.get('post_date'), blog.get('post_comments')
    next_page_x = blog.get('next_page')
    log.info('got xpaths: urls: {urls} -- title: {title} -- date: {date} -- '
                 'comments: {comments} -- page: {page}'.format(urls=p_urls_x, title=p_title_x, date=p_date_x,
                                                               comments=p_comments_x, page=next_page_x))

    platform = _find_platform(url)
    if platform is None:
        log.error('no platform found for url {url} and name {name}'.format(url=url, name=name))
        models.OperationStatus.inc('custom_blog', url, 'get_platform', 'notfound', None)
        return counts
    platform.platform_name = 'Custom'
    platform.blogname = name
    platform.save()
    log.info('using platform %r', platform)
    influencer = platform.influencer
    log.info('got platform {platform} and with influencer {inf}'.format(platform=platform.platform_name, inf=influencer.id))

    log.info('going to blog url {url}'.format(url=url))
    xb.load_url(url)

    cur_page = 1
    next_page_el = xb.el_by_xpath(next_page_x) if next_page_x else None
    next_page = next_page_el.get_attribute('href') if next_page_el else None
    log.info('got to url and just got the next page {next}'.format(next=next_page))
    while True:
        # get a list of all post urls to visit for this blog
        post_urls = [a.get_attribute("href") for a in xb.els_by_xpath(p_urls_x)]
        post_urls = [u for u in post_urls if u]
        log.info('got {urls} post urls from page no {cur_page}: {lst}'.format(
            urls=len(post_urls), cur_page=cur_page, lst=post_urls))
        if not post_urls:
            log.error('No post_urls for platform %r', platform)
            models.OperationStatus.inc('custom_blog', url, 'eval_post_urls', 'empty',
                                       json.dumps({'cur_page': cur_page}))
        # for each post url, load that url and start scraping that page
        for p_url in post_urls[:max_posts]:
            try:
                xb.load_url(p_url)
            except:
                #we werent able to load the url for whatever reason, go to the next post
                log.exception('while loading post_url %s for platform %s', p_url, platform)
                continue
            log.info('just loaded url {url}'.format(url=p_url))

            title_el = xb.el_by_xpath(p_title_x) if p_title_x else None
            if not title_el:
                log.error('No title element for platform %r', platform)
                models.OperationStatus.inc('custom_blog', url, 'find_title_el', 'notfound',
                                           json.dumps({'cur_page': cur_page, 'p_url': p_url}))
            content_el = xb.el_by_xpath(p_content_x) if p_content_x else None
            if not content_el:
                log.error('No content el for platform %r', platform)
                models.OperationStatus.inc('custom_blog', url, 'find_content_el', 'notfound',
                                           json.dumps({'cur_page': cur_page, 'p_url': p_url}))
            date_el = xb.el_by_xpath(p_date_x) if p_date_x else None
            if not date_el:
                log.error('No date el for platform %r', platform)
                models.OperationStatus.inc('custom_blog', url, 'find_date_el', 'notfound',
                                           json.dumps({'cur_page': cur_page, 'p_url': p_url}))

            p_title = title_el.text if title_el else None
            p_content = xb.el_source(content_el) if content_el else None
            p_date = date_el.text if date_el else None
            if not p_title:
                log.error('No title value for platform %r', platform)
                models.OperationStatus.inc('custom_blog', url, 'eval_title_el', 'empty',
                                           json.dumps({'cur_page': cur_page, 'p_url': p_url}))
            if not p_content:
                log.error('No content value for platform %r', platform)
                models.OperationStatus.inc('custom_blog', url, 'eval_content_el', 'empty',
                                           json.dumps({'cur_page': cur_page, 'p_url': p_url}))
            if not p_date:
                log.error('No date value for platform %r', platform)
                models.OperationStatus.inc('custom_blog', url, 'eval_date_el', 'empty',
                                           json.dumps({'cur_page': cur_page, 'p_url': p_url}))
                p_date = datetime.datetime.now()
            else:
                # first try to get the date using the parse_date method of iso8601, if that doesnt work try with
                # parsedatetime, if *that* doesnt work, then just give up on getting the date
                try:
                    p_date = parse_date(p_date)
                except ParseError:
                    cal = parsedatetime.Calendar()
                    try:
                        cal_tup = cal.parse(p_date)
                        p_date = datetime.datetime(*cal_tup[0][:7]) #the 0th el of the tuple is a datetime tuple, pull only the first *7* of those numbers
                    except:
                        p_date = datetime.datetime.now()

            post, post_created = models.Posts.objects.get_or_create(influencer=influencer, platform=platform, url=p_url)
            if not post_created:
                log.warn('post %s already exists', post)
            if p_title:
                post.title = unicode(p_title)
            if p_content:
                post.content = unicode(p_content)
            if p_date:
                post.create_date = p_date
            post.show_on_search = influencer.show_on_search
            post.save()
            log.info('just created a post %r', post)
            counts['posts_saved'] += 1

            comments = xb.els_by_xpath(p_comments_x) if p_comments_x else []
            log.info('now going to iterate over {num_comments} comments'.format(num_comments=len(comments)))
            if comments and not post_created:
                log.info('Deleting %s old comments' % post.postinteractions_set.all().count())
                post.postinteractions_set.all().delete()
            # for each comment in this post, create an appropriate PostInteraction instance
            for comment_el in comments:
                pi = models.PostInteractions.objects.create(
                    post=post,
                    platform_id=post.platform_id,
                    content=unicode(comment_el.text),
                    create_date=post.create_date,
                    if_commented=True
                )
                log.info('created comment %r', pi)
                counts['pis_saved'] += 1
            log.info('done with comments, now going to the next post')


        # once we're done with all the posts, go to the next page and run the scraper over the posts on that page
        if next_page and cur_page <= max_pages:
            try:
                xb.load_url(next_page)
                log.info('going to page {page} now\n\n\n'.format(page=str(cur_page + 1)))
                cur_page += 1

                next_page_el = xb.el_by_xpath(next_page_x)
                if not next_page_el:
                    log.error('No next_page_el')
                    models.OperationStatus.inc('custom_blog', url, 'find_next_page_el', 'notfound',
                                               json.dumps({'cur_page': cur_page, 'p_url': p_url}))
                next_page = next_page_el.get_attribute('href') if next_page_el else None
            except:
                log.exception('while loading next_page, not loading more pages')
                return counts
        else:
            log.info('finished processing after %s pages, platform %r', cur_page, platform)
            return counts


@baker.command
def customblogs_error_report(min_operationstatus_id=1):
    statuses = models.OperationStatus.objects.filter(object_type='custom_blog',
        id__gte=int(min_operationstatus_id)).\
        order_by('object_spec').\
        order_by('op').\
        order_by('op_status')
    by_url = defaultdict(list)
    for st in statuses:
        if st.op_msg and 'p_url' in st.op_msg:
            p_url = json.loads(st.op_msg)['p_url']
        else:
            p_url = ''
        by_url[st.object_spec].append((st.op, p_url))

    for url in by_url:
        print 'BLOG_URL %r' % url
        for op, p_url in by_url[url]:
            print '%s failed, post_url: %r' % (op, p_url)
        print '\n\n'

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

