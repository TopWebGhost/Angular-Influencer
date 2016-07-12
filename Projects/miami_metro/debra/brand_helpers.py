import time
import datetime
import requests
import traceback
from urlparse import urlparse, parse_qs

from django.contrib.auth.models import User
from django.conf import settings
from django.db.models import Q

from celery.decorators import task
from celery import chord
from celery.utils.log import get_task_logger

from debra.constants import SHELF_BRAND_USER, SHELF_BRAND_PASSWORD
from xpathscraper import xbrowser
from mailsnake import MailSnake
mailsnake_client = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')

logger = get_task_logger(__name__)


def create_profile_for_brand(brand):
    from debra.models import UserProfile

    existing_user = User.objects.filter(username=SHELF_BRAND_USER(brand.domain_name))
    if existing_user.count() == 1:
        return
    else:
        brand_user_virtual = User()
        brand_user_virtual.username = SHELF_BRAND_USER(brand.domain_name)
        brand_user_virtual.email = SHELF_BRAND_USER(brand.domain_name)
        brand_user_virtual.is_active = True
        brand_user_virtual.set_password(SHELF_BRAND_PASSWORD)
        brand_user_virtual.save()
        brand_user_prof_virtual = UserProfile()
        brand_user_prof_virtual.user = brand_user_virtual
        brand_user_prof_virtual.name = brand.name
        brand_user_prof_virtual.brand = brand
        brand_user_prof_virtual.create_brand_img()
        brand_user_prof_virtual.save()


def connect_user_to_brand(brand, user_profile):
    from debra.models import UserProfileBrandPrivilages
    privilages = UserProfileBrandPrivilages()
    privilages.user_profile = user_profile
    privilages.brand = brand
    if UserProfileBrandPrivilages.objects.filter(brand=brand, permissions=UserProfileBrandPrivilages.PRIVILAGE_OWNER).exists():
        privilages.permissions = UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR_UNCONFIRMED
        #@todo send email to brand owner
    else:
        privilages.permissions = UserProfileBrandPrivilages.PRIVILAGE_OWNER
    privilages.save()
    user_profile.update_intercom()
    # make sure brand is not blacklisted
    if brand.blacklisted:
        brand.blacklisted = False
        brand.save()
    if brand.is_agency:
        for managed_brand in brand.get_managed_brands():
            bp = UserProfileBrandPrivilages()
            bp.brand = managed_brand
            bp.user_profile = user_profile
            bp.permissions = UserProfileBrandPrivilages.PRIVILAGE_AGENCY
            bp.save()


def sanity_checks(brand):
    email = SHELF_BRAND_USER(brand.domain_name)
    try:
        brand.userprofile
    except:
        print "Brand", brand, "had no user profile"
        create_profile_for_brand(brand)
    try:
        brand.userprofile.user
    except:
        print "Brand", brand, "had no user???"
        brand_user_virtual = User()
        brand_user_virtual.username = SHELF_BRAND_USER(brand.domain_name)
        brand_user_virtual.email = email
        brand_user_virtual.is_active = True
        brand_user_virtual.set_password(SHELF_BRAND_PASSWORD)
        brand_user_virtual.save()
        brand.userprofile.user = brand_user_virtual
        brand.userprofile.save()


def find_post_by_url(url, single, **kwargs):
    from debra.models import Posts
    from debra import helpers

    t = time.time()
    url = url.strip()
    platform = kwargs.get('platform')

    # kwargs['content__isnull'] = False

    # Instagram, Pinterest, TwitterFetcherr, Blog
    fields = ['url']
    if platform:
        urls = helpers.get_canonical_urls(url, platform.platform_name)
        # urls = [url, url.split('?')[0]]
    else:
        urls = [url]
    funcs = [lambda u: u.split('#')[0], lambda u: u, lambda u: u.split('?')[0], lambda u: u.lower(), lambda u: u.upper()]

    if platform and platform.platform_name in ['Facebook']:
        fbid = helpers.extract_fbid(url)
        if fbid:
            print '* have FBID for Facebook post, using it...'
            fields = ['url__contains']
            urls = [fbid]
            funcs = [lambda u: u]
        else:
            urls = [url]

    def make_q_list(urls):
        q_list = []
        for u in urls:
            for field in fields:
                q_list.append(Q(**{field: u}))
        return q_list

    def qs_generator(funcs):
        for f in funcs:
            q_list = make_q_list(map(f, urls))
            qs = Posts.objects.filter(
                reduce(lambda a, b: a | b, q_list), **kwargs).extra(select={
                    'has_content': 'content IS NOT NULL',
                }).order_by('has_content')
            yield qs if qs.exists() else None

    for qs in qs_generator(funcs):
        if qs is None:
            continue
        break

    if qs is None:
        print "Got no posts, took %s" % (time.time() - t,)
    else:
        if single:
            post = qs[0]
            print "Got post: %r, took %s" % (post, time.time() - t,)
            return post
        else:
            posts = list(qs)
            print "Got posts: %s, took %s" % (len(posts), time.time() - t,)
            return posts


def connect_post_analytics_to_contract(pa, to_save=True):
    from debra.models import InfluencerJobMapping

    # assert pa.contract is None, 'PA already has a contract associated'
    # assert pa.collection and pa.post.influencer, 'Must have collection and influencer associated'

    try:
        if pa.contract or not pa.collection or not pa.post.influencer:
            return
    except AttributeError:
        return

    try:
        ijm = InfluencerJobMapping.objects.filter(
            contract__isnull=False,
            job__post_collection=pa.collection,
            mailbox__influencer=pa.post.influencer
        )[0]
    except IndexError:
        print 'No matching contract can be found.'
    else:
        pa.contract = ijm.contract
        if to_save:
            pa.save()
        return ijm.contract


@task(bind=True, name="debra.brand_helpers.connect_url_to_post")
def connect_url_to_post(self, url, post_analytics_id, influencer_id=None):
    """
    High level goal: Given a url, we ultimately need to add that post and Influencer in our database.
        So, first we check if we have a post for that url.
            => Yes, then we can find the influencer as well associated with that post.
            => No
                => First, we need to see if there already exists an Influencer for this blog domain
                    => If yes, then use that influencer
                    => Else, create an influencer with source='import_from_post_analytics'
                => Now, that we have an influencer for this url but we dont have that post fetched. So,
                   we need to run our crawler to get that url.
                   QUESTION: do we have a method to fetch a given url?
    """
    from debra.models import Posts, PostAnalytics, Platform, Influencer
    from debra import helpers
    from platformdatafetcher import (
        pbfetcher, fetcher, postprocessing, feeds, socialfetcher)
    from xpathscraper import utils
    from platformdatafetcher.fetch_blog_posts_manually import get_all_comments_number
    from platformdatafetcher.fetch_blog_posts_date import fetch_blog_posts_date
    from platformdatafetcher import pbfetcher
    from masuka.image_manipulator import upload_post_image

    def create_post(url):
        blog_url = utils.post_to_blog_url(url)
        inf = helpers.create_influencer_and_blog_platform(blog_url, 'import_from_post_analytics', True, True)

        if inf:
            platform = inf.blog_platform
            print("Inf.validated_on: %r" % inf.validated_on)
            if not inf.validated_on or not 'info' in inf.validated_on:
                # it's not QA-ed yet, so let's process this sequentially
                postprocessing.process_new_influencer_sequentially(inf.id, True)
            # at this point, we should have data for the influencer
            # now, let's check if got the post

            # post = Posts.objects.filter(platform=platform, url__iexact=url)
            # print("Got post: %r" % post)
            # if post.exists():
            #     return post[0]

            post = find_post_by_url(url, True, platform=platform)

            if post is None:
                # here we just create a quick post artifically (ideally we should have fetched this post)
                post = Posts.objects.create(
                    platform=platform,
                    influencer=inf,
                    show_on_search=inf.show_on_search,
                    url=url
                )
            return post

        print("No valid influencer found")
        helpers.send_admin_email_via_mailsnake("Post Analytics: No valid influencer found %r" % url, "During our post analytics, we didn't find an influencer for this Post.url=%r" % (url))
        return None

    def pick_the_best_post(posts):
        """
        we may get multiple posts for the same url
        1. If there is only one, return it
        2. Else, if the influencer is show_on_search >> validated_on >> others
        """
        print("pick_the_best_post: for %r" % posts)
        blog_posts = posts.filter(platform__platform_name__in=Platform.BLOG_PLATFORMS)
        if len(blog_posts) > 0:
            posts = blog_posts
        if len(posts) == 1:
            print("\tCase 1: Only one post found, so returning it")
            return posts[0]

        # first pick the best influencer
        influencers = list(posts.values_list('influencer', flat=True))
        if len(set(influencers)) == 1:
            influencer = influencers[0]
        else:
            influencer_id = influencers[0]
            influencer_objects = Influencer.objects.filter(id__in=influencers)
            influencer_object = Influencer.objects.get(id=influencer_id)
            influencer_object = influencer_object._select_influencer_to_stay(influencer_objects)
            influencer = influencer_object.id
        print("selected influencer= %r" % influencer)
        posts = posts.filter(influencer=influencer)
        # Case 2: return post belonging to the best influencer
        if len(posts) == 1:
            print("\tCase 2: returning post belonging to the best influencer")
            return posts[0]
        # Case 3: return post belonging to the non url_not_found platform from the best influencer
        posts_without_url_not_found = posts.exclude(
            platform__url_not_found=True).extra(select={
                'has_content': 'content IS NOT NULL',
            }).order_by('has_content')
        if len(posts_without_url_not_found) >= 1:
            print("\tCase 3: returning post belonging to the platform that is not url_not_found")
            return posts_without_url_not_found[0]
        # Case 4: just use any post
        print("\tInfluencer for this post are neither show_on_search nor validated, so returning with arbitrary one")
        return posts[0]

    def get_resolved_url(pa):
        # use the url that we found after resolving the link
        # so the postanalytics.url will be what the user added and
        # the associated post will use the resolved link
        print '* Handling URL redirection for PA={}'.format(pa.id)
        try:
            redirected_url = utils.resolve_http_redirect(pa.post_url)
            if pa.post_url != redirected_url:
                PostAnalytics.objects.handle_redirect(pa, redirected_url)
            url = redirected_url
            print '* Resolved URL={}'.format(redirected_url)
        except:
            url = pa.post_url
        print '* Original URL={}'.format(pa.post_url)
        print '* Resulting URL={}'.format(url)
        return url

    def get_social_post(pa, influencer):
        was_created = False
        if pa.post is not None:
            post = pa.post
        else:
            # not sure if we need this
            url = get_resolved_url(pa)
            plats = influencer.platforms().filter(platform_name=pa.post_type)
            if plats.count() > 1:
                plats = plats.exclude(url_not_found=True)
            # @TODO: add IndexError exception handling
            try:
                plat = plats[0]
            except Exception:
                post = None
            else:
                post = find_post_by_url(url, True, platform=plat)
                if post is None:
                    pass
                    # # create a new post
                    # print '* Creating a new post'
                    # post = Posts.objects.create(
                    #     platform=plat,
                    #     influencer=influencer,
                    #     show_on_search=influencer.show_on_search,
                    #     url=url
                    # )
                    # print '* created. id={}'.format(post.id)
                    # was_created = True
        return post, was_created

    def get_post(pa):
        post, was_created = None, False
        if pa.post is not None:
            post = pa.post
        else:
            url = get_resolved_url(pa)
            posts = find_post_by_url(url, False)
            if posts and len(posts) >= 1:
                post_ids = [p.id for p in posts]
                posts_qs = Posts.objects.filter(id__in=post_ids)
                post = pick_the_best_post(posts_qs)
            else:
                # create a blog post only for Blog
                post = create_post(url)
                was_created = True
        return post, was_created

    def extract_post_comments(post, analytics_for_url):
        num_comments = -1
        method = None
        try:
            num_comments, method = get_all_comments_number(post.url)
            if num_comments == -1 and method == 'captcha_squarespace':

                # helpers.send_admin_email_via_mailsnake(
                #     "Comment fetcher: Captcah required (Squarespace) for %r" % post.url,
                #     "Please check out this Post.id=%r Post.url=%r" % (post.id, post.url))

                logger.error('Captcha (Squarespace) required for comment fetcher. Post ID and url provided.',
                             exc_info=1,
                             extra={'post_id': post.id,
                                    'post_url': post.url})
        except Exception as e:
            num_comments = -1

            if self.request.retries >= 5:

                logger.error('Comment fetcher constantly crashed for %s retries.' % self.request.retries,
                             exc_info=1,
                             extra={'post_id': post.id,
                                    'post_url': post.url,
                                    'exception': e})

                # helpers.send_admin_email_via_mailsnake(
                #     "Comment fetcher crashed for %r and was retried %s times." % (post.url, self.request.retries),
                #     "Please check out this Post.id=%r Post.url=%r\n Exception: %s" % (post.id, post.url, e))
            else:
                # Retrying the method in 1 minute when we get an exception from comment fetcher.
                logger.warning('Retrying task due to comment fetcher crash...',
                               exc_info=1,
                               extra={'post_id': post.id,
                                      'post_url': post.url,
                                      'exception': e,
                                      'retry_number': self.request.retries,
                                      'task_id': self.request.id})

                # logger.error('Retrying task %s attempt %s due to comment fetcher crash for post: %s ' % (self.request.id,
                #                                                                                          self.request.retries,
                #                                                                                          post.url))

                raise self.retry(countdown=60 * 1, max_retries=5)

        # Retrying the method in 1 minute when we get a connection error result.
        if num_comments == -1 and method == 'connection_error':

            if self.request.retries < 3:
                # logger.error('Retrying task %s attempt %s due to connection_error for post: %s ' % (self.request.id,
                #                                                                                     self.request.retries,
                #                                                                                     post.url))
                logger.warning('Retrying task due to connection_error result in comment_fetcher',
                               exc_info=1,
                               extra={'post_id': post.id,
                                      'post_url': post.url,
                                      'retry_number': self.request.retries,
                                      'task_id': self.request.id})

                raise self.retry(countdown=60 * 1, max_retries=3)

        # num_comments = max(
        #     num_comments, max(map(
        #         lambda x: x.post_comments, analytics_for_url)
        #     )
        # )

        post.engagement_media_numcomments = num_comments
        post.ext_num_comments = num_comments

    def extract_post_date(post):
        if not post.create_date:
            try:
                post_data_result = fetch_blog_posts_date(post.url)
                if post_data_result['date_published'] is not None:
                    post.create_date = post_data_result['date_published']
                if post_data_result['title'] is not None:
                    post.title = post_data_result['title']
            except Exception as e:
                # helpers.send_admin_email_via_mailsnake(
                #     "Date fetcher crashed for %r" % post.url,
                #     "Please check out this Post.id=%r Post.url=%r\n Exception: %s" % (post.id, post.url, e)
                # )
                logger.error('Date fetcher has crashed. Post ID and url provided.' % self.request.retries,
                             exc_info=1,
                             extra={'post_id': post.id,
                                    'post_url': post.url,
                                    'exception': e})

    origin_analytics = PostAnalytics.objects.get(id=post_analytics_id)
    if influencer_id is not None:
        influencer = Influencer.objects.get(id=influencer_id)
    else:
        influencer = None
    collection_id = origin_analytics.collection_id

    if influencer is not None and origin_analytics.post_type not in [None, 'Blog']:
        post, was_created = get_social_post(origin_analytics, influencer)
    else:
        post, was_created = get_post(origin_analytics)

    if not post:
        helpers.send_admin_email_via_mailsnake("Post Analytics: No valid post found %r" % url, "During our post analytics, we didn't find a post for this url=%r" % (url))
        print("No post was found for %r, so returning." % origin_analytics.post_url)
        return
    print("Using post: %r for URL: %r" % (post, origin_analytics.post_url))

    post_exists = PostAnalytics.objects.filter(
        collection_id=collection_id, post=post
    ).exclude(post_url=origin_analytics.post_url).exists()
    if post_exists:
        print '* PA with post={} and another post_url exists, removing current one.'.format(post.id)
        origin_analytics.delete()
        return

    origin_analytics.post = post
    origin_analytics.save()

    # BE CAREFUL IF YOU MODIFY ANY OF THE POST ANALYTICS FROM THIS LIST !!!
    if post.platform:
        analytics_for_url = PostAnalytics.objects.filter(post=post)
        post_type = post.platform.platform_name
        if post_type in Platform.BLOG_PLATFORMS:
            post_type = 'Blog'
        analytics_for_url.update(post_type=post_type)
        origin_analytics = PostAnalytics.objects.get(id=origin_analytics.id)
    else:
        analytics_for_url = PostAnalytics.objects.filter(
            post_url__iexact=origin_analytics.post_url)
    analytics_for_url = list(analytics_for_url)

    if post.post_image is None:
        # upload_post_image_task.apply_async([post.id], queue='celery')
        upload_post_image(post)
        post = Posts.objects.get(id=post.id)

    if origin_analytics.post_type in ['Blog', None]:
        extract_post_comments(post, analytics_for_url)
        extract_post_date(post)
        post.save()
    else:
        try:
            print '* Start fetching post interactions.'
            f = fetcher.fetcher_for_platform(post.platform)
            f.fetch_post_interactions([post])
        except Exception:
            helpers.send_admin_email_via_mailsnake(
                "'connect_url_to_post' exception during post interactions fetching (Post={})".format(post.id),
                '<br />'.join(traceback.format_exc().splitlines())
            )

    def get_number_of_shares(pa):
        if pa.post_type == 'Facebook':
            return pa.post.engagement_media_numfbshares
        elif pa.post_type == 'Twitter':
            return pa.post.engagement_media_numretweets
        elif pa.post_type == 'Pinterest':
            return pa.post.engagement_media_numrepins
        else:
            return sum([
                pa.count_tweets or 0,
                pa.count_fb_shares or 0,
                pa.count_fb_likes or 0,
                pa.count_fb_comments or 0,
                pa.count_gplus_plusone or 0,
                pa.count_pins or 0,
            ])

    origin_analytics.count_video_impressions = post.impressions;
    origin_analytics.count_likes = post.engagement_media_numlikes
    origin_analytics.post_comments = post.ext_num_comments
    origin_analytics.count_shares = get_number_of_shares(origin_analytics)
    origin_analytics.save()

    contract = connect_post_analytics_to_contract(origin_analytics, False)

    for analytics in analytics_for_url:
        if analytics.post is None:
            analytics.post = post
            analytics.post_found = True
        # if analytics.post_comments is None:
        #     analytics.post_comments = post.engagement_media_numcomments
        if contract and analytics.contract_id is None and analytics.collection_id == collection_id:
            analytics.contract_id = contract.id
        analytics.save()

    print("Collection_id=%r" % collection_id)
    # send_post_analytics_report(collection_id)
    # send_post_analytics_report_to_admins(collection_id)


@task(name="debra.brand_helpers.fetch_post_analytics_instances")
def fetch_post_analytics_instances(urls, collection_id=None, brand_id=None, refresh=False, post_ids=None):
    from debra.models import PostAnalytics, PostAnalyticsCollection, Brands

    collection = PostAnalyticsCollection.objects.get(id=collection_id)

    genereate_new_report_notification(collection_id)

    pa_ids = []

    if post_ids is None:
        post_ids = [None] * len(urls)

    for i, (url, post_id) in enumerate(zip(urls, post_ids), start=1):
        post_analytics = PostAnalytics.objects.from_source(
            post_url=url, refresh=refresh)
        if post_id:
            post_analytics.post_id = post_id
            post_analytics.save()

        pa_ids.append(post_analytics.id)

        collection.add(post_analytics)

        # for backwards compatibility
        if brand_id is not None:
            brand = Brands.objects.get(id=brand_id)
            post_analytics.brands.add(brand)
        print 'saved: #{} - {}'.format(i, url)

    collection.is_updating = False
    collection.save()

    for i, (pa_id, url) in enumerate(zip(pa_ids, urls), start=1):
        print 'now issuing connect_url_to_post task: #{} - {}'.format(i, url)
        connect_url_to_post.apply_async(
            # [url, pa_id], queue='post_campaign_analytics')
            [url, pa_id], queue='post_campaign_analytics2')
        # connect_url_to_post(url, pa_id)


@task(name="debra.brand_helpers.send_post_analytics_report")
def send_post_analytics_report(collection_id):
    from debra.models import PostAnalyticsCollection
    from constants import PRODUCTION
    #print("kwargs = %r" % kwargs)
    #collection_id = kwargs.get('collection_id')
    print ("Got collection_id = %r" % collection_id)
    collection = PostAnalyticsCollection.objects.get(id=collection_id)

    if collection.user is not None and collection.updated:
        body ='Hi there,<p>Your collection `%r` is ready (you can view it or export it). Click <a href=%r target="_blank">here to view it</a>.</p>Thanks,<br>The Shelf Team.' % (collection.name, PRODUCTION + collection.page_url,)
        subject = 'Campaign Post Analytics Ready for %r' % collection.name
        from_email = 'atul@theshelf.com'
        from_name = 'Atul'
        to_emails = [
            {'email': 'atul@theshelf.com', 'type': 'cc'},
            {'email': 'pavel@theshelf.com', 'type': 'cc'},
            {'email': collection.user.email, 'type': 'to'},
        ]

        mailsnake_client.messages.send(message={'html': body,
                                                'subject': subject,
                                                'from_email': from_email,
                                                'from_name': from_name,
                                                'to': to_emails})
        
        collection.last_report_sent = datetime.datetime.now()
        collection.save()


def genereate_new_report_notification(collection_id):
    from debra.models import PostAnalyticsCollection
    from debra import account_helpers
    from debra import helpers

    collection = PostAnalyticsCollection.objects.get(id=collection_id)

    now = datetime.datetime.strftime(datetime.datetime.now(), '%c')

    body = '''Started to generate a new report at {}:
                collection_id = {},
                collection_name = {},
                user = {}
            '''.format(
                    now,
                    collection.id,
                    collection.name,
                    collection.user or 'No user'
                )
    subject = 'New report for collection_id={}, {}'.format(collection.id, now)

    helpers.send_admin_email_via_mailsnake(subject, body)

    account_helpers.intercom_track_event(None, "generate-report-requested", {
        'collection_name': collection.name,
        'collection_id': collection.id,
    }, user=collection.user)


def send_post_analytics_report_to_admins(collection_id):
    from debra.models import PostAnalyticsCollection
    from debra import helpers

    collection = PostAnalyticsCollection.objects.get(id=collection_id)

    if not collection.updated:
        return

    qs = collection.get_unique_post_analytics().prefetch_related(
        'post'
    )
    qs = list(qs)

    stats = [
        len(filter(lambda x: x.post.title is None, qs)),
        len(filter(lambda x: x.post.create_date is None, qs)),
        len(filter(lambda x: x.post_num_comments in [-1, None], qs)),
        collection.creator_brand.name if collection.creator_brand else None,
        collection.user.id if collection.user else None,
        '{} ({})'.format(collection.user.userprofile.name\
            if collection.user and\
                collection.user.userprofile and\
                collection.user.userprofile.name is not None
            else 'No name',
            collection.user.email if collection.user else 'No email'
        )
    ]

    subject = 'Report for PostAnalyticsCollection.id={} is ready'.format(
        collection.id)
    body = '<br />'.join([
            'Number of missing titles: {}',
            'Number of missing dates: {}',
            'Number of missing comment counts: {}',
            'Brand name: {}',
            'User ID: {}',
            'Username: {}',
            ]).format(*stats)

    helpers.send_admin_email_via_mailsnake(subject, body)


def handle_post_analytics_urls(urls, collection_id=None, brand_id=None, refresh=False, collection=None, post_ids=None):
    from debra.models import PostAnalytics, PostAnalyticsCollection

    assert collection_id is not None or (collection and\
        isinstance(collection, PostAnalyticsCollection))

    if collection is None:
        collection = PostAnalyticsCollection.objects.get(id=collection_id)
    elif collection_id is None:
        collection_id = collection.id

    collection.is_updating = True
    collection.save()

    #sending = send_post_analytics_report.subtask(
    #    kwargs={'collection_id': collection_id})
    #connecting = chord(connect_url_to_post.s(url) for url in urls)(sending)

    if settings.DEBUG:
        fetch_post_analytics_instances(
            urls, collection_id, brand_id, refresh, post_ids)
    else:
        fetch_post_analytics_instances.apply_async(
            [urls, collection_id, brand_id, refresh, post_ids],
            # queue='post_campaign_analytics'
            queue='post_campaign_analytics2'
        )

    print("handle_post_analytics_urls returning")


@task(name="debra.brand_helpers.add_influencers_to_blogger_approval_report")
def add_influencers_to_blogger_approval_report(inf_ids, inf_collection_id=None, extra=None, campaign_id=None, approved=False):
    from debra.models import InfluencerAnalyticsCollection, BrandJobPost

    assert inf_collection_id is not None or campaign_id is not None

    print 'Campaign = {}'.format(campaign_id)
    print 'Influencer Collection = {}'.format(inf_collection_id)

    if campaign_id:
        campaign = BrandJobPost.objects.get(id=campaign_id)
        inf_collection = campaign.influencer_collection
    else:
        inf_collection = InfluencerAnalyticsCollection.objects.get(
            id=inf_collection_id)
        campaign = None

    inf_collection.save_influencers(inf_ids, extra)
    if campaign and approved:
        campaign.merge_approved_candidates(
            celery=False, inf_ids=inf_ids)


@task(name="debra.brand_helpers.send_approval_report_to_client")
def send_approval_report_to_client(campaign_id):
    from debra.models import (
        InfluencerAnalyticsCollection, BrandJobPost, InfluencerAnalytics)

    campaign = BrandJobPost.objects.get(id=campaign_id)
    collection = campaign.influencer_collection
    collection.influenceranalytics_set.filter(
        approve_status=InfluencerAnalytics.APPROVE_STATUS_NOT_SENT
    ).update(
        approve_status=InfluencerAnalytics.APPROVE_STATUS_PENDING
    )
    collection.approval_status = InfluencerAnalyticsCollection.APPROVAL_STATUS_SENT
    collection.save()


@task(name="debra.brand_helpers.add_approved_influencers_to_pipeline")
def add_approved_influencers_to_pipeline(campaign_id, inf_ids=None):
    from debra.models import (
        BrandJobPost, InfluencerAnalytics, InfluencerJobMapping,
        Contract, Influencer, MailProxy
    )
    campaign = BrandJobPost.objects.get(id=campaign_id)

    params = dict(approve_status=InfluencerAnalytics.APPROVE_STATUS_YES)
    if inf_ids is not None:
        params['influencer_id__in'] = inf_ids
    ia_ids = campaign.influencer_collection.influenceranalytics_set.filter(
        **params).values_list('id', 'influencer')

    candidates = list(campaign.candidates.values_list(
        'mailbox__influencer', 'influencer_analytics__influencer'))
    inf_set = set()
    for inf1, inf2 in candidates:
        inf_set.add(inf1)
        inf_set.add(inf2)

    to_merge = []
    for ia_id, inf_id in ia_ids:
        if inf_id not in inf_set:
            to_merge.append((ia_id, inf_id))

    print '* Merging {} new influencers'.format(len(to_merge))

    infs = {
        inf.id:inf
        for inf in Influencer.objects.filter(id__in=[x[1] for x in to_merge])
    }

    for ia_id, inf_id in to_merge:
        print '* Creating IJM for {}'.format(ia_id)
        ijm = InfluencerJobMapping.objects.create(
            influencer_analytics_id=ia_id,
            job=campaign,
            campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_PRE_OUTREACH,
            mailbox=MailProxy.create_box(campaign.creator, infs.get(inf_id))
        )
        contract = Contract()
        contract._ignore_old = True
        contract.save()
        ijm.contract = contract
        ijm.save()

        # call the tracking stuff
        contract = Contract.objects.get(id=contract.id)
        contract._newly_created = True
        contract.save()


@task(name='debra.brand_helpers.influencer_fetch_post_analytics_instances', ignore_result=True)
def influencer_fetch_post_analytics_instances(pa_ids, inf_ids=None):
    from debra.models import PostAnalytics
    from debra.helpers import send_admin_email_via_mailsnake

    if inf_ids is None:
        inf_ids = [None] * len(pa_ids)

    pa_values = PostAnalytics.objects.filter(id__in=pa_ids).values_list(
        'id', 'post_url')

    for inf_id, (pa_id, post_url) in zip(inf_ids, pa_values):
        connect_url_to_post(post_url, pa_id, inf_id)

    pas = PostAnalytics.objects.filter(id__in=pa_ids).prefetch_related('post')

    for pa in pas:
        if not pa.post:
            continue
        if pa.post.title != pa.post_title or (pa.post.create_date and pa.post.create_date.date() != pa.post_date):
            send_admin_email_via_mailsnake(
                'PostAnalytics={} and Post={} data mismatch'.format(
                    pa.id, pa.post.id),
                'Titles: "{}", "{}" <br />Dates: "{}, "{}"'.format(
                    pa.post_title, pa.post.title, pa.post_date, pa.post.create_date.date())
                )

@task(name='debra.brand_helpers.handle_new_influencers', ignore_result=True)
def handle_new_influencers(urls, tag_id=None, brand_id=None, user_id=None):
    from debra.helpers import create_influencer_and_blog_platform_bunch
    from debra.models import (
        InfluencersGroup, Brands, User, Influencer)
    from debra.helpers import send_admin_email_via_mailsnake
    from platformdatafetcher import postprocessing
    from xpathscraper import utils

    urls = map(utils.post_to_blog_url, urls)

    brand = Brands.objects.get(id=brand_id) if brand_id else None
    user = User.objects.get(id=user_id) if user_id else None
    tag = InfluencersGroup.objects.get(id=tag_id) if tag_id else None

    send_admin_email_via_mailsnake(
        'Influencer import started for {}'.format(brand.name),
        '''
        <p>Influencer import started:</p></br>
        <ul>
        <li>adding {} urls</li>
        <li>collection: {}</li>
        <li>brand: {}</li>
        <li>user: {}</li>
        </ul>
        '''.format(len(urls), tag, brand, user)
    )

    infs = create_influencer_and_blog_platform_bunch(
        urls, 'customer_uploaded', None, tags=['customer_uploaded'])

    send_admin_email_via_mailsnake(
        'Influencer Import: Influencers created now for {} and tag {}'.format(brand.name, tag.name if tag else "No Tag Given"),
        '''
        <p>Created {}<p>'''.format(len(infs))
    )

    infs_added_to_tag = []

    for inf in infs:
        print("Checking influencer %r blog_url %r show_on_search %r" % (inf.id, inf.blog_url, inf.show_on_search))
        if not inf.show_on_search:
            # it's not on search yet, so let's process this sequentially and then it'll show up on an admin table
            postprocessing.process_new_influencer_sequentially(inf.id, True)
        if tag:
            if tag.add_influencer(inf):
                infs_added_to_tag.append(inf)
                print("influencer %r added to the tag group" % inf)

    send_admin_email_via_mailsnake(
        'Influencer import finished for {}'.format(brand.name),
        '''
        <p>Please check new influencers in the <a href={}>admin table</a>. </p>
        <p>Stats:</p></br>
        <ul>
        <li>{} influencers were found/created</li>
        <li>{} urls were passed</li>
        <li>{} new influencers were added to the tag</li>
        <li>{} with show_on_search=True among newly added to the tag influencers</li>
        <li>{} with old_show_on_search=True among newly added to the tag influencers</li>
        <li>{} with show_on_search=True among all passed influencers</li>
        <li>{} with old_show_on_search=True among all passed influencers</li>
        </ul>
        '''.format(
            "https://app.theshelf.com/admin/upgrade/influencer/uploaded_by_customers/",
            len(infs),
            len(urls),
            len(infs_added_to_tag),
            len(filter(lambda inf: inf.show_on_search, infs_added_to_tag)),
            len(filter(lambda inf: inf.old_show_on_search, infs_added_to_tag)),
            len(filter(lambda inf: inf.show_on_search, infs)),
            len(filter(lambda inf: inf.old_show_on_search, infs)),
        ),
        extra_emails = ['desirae@theshelf.com']
    )


@task(name='debra.brand_helpers.bookmarking_task', ignore_result=True)
def bookmarking_task(tag_ids, operation, collection_type, params=None, **kwargs):
    from debra.models import InfluencersGroup

    params = params or {}

    if collection_type == 'tag':
        if operation == 'create_collection':
            tag = InfluencersGroup()
            tag.name = params.get('name')
            tag.owner_brand_id = params.get('brand'),
            tag.creator_brand_id = params.get('brand')
            tag.creator_userprofile_id = params.get('userprofile')
            tag.save()
        else:
            tags = InfluencersGroup.objects.filter(id__in=tag_ids)
            for tag in tags:
                if operation == 'add_influencer':
                    tag.add_influencer(**params)
                elif operation == 'remove_influencer':
                    tag.remove_influencer(**params)


@task(name='debra.brand_helpers.send_missing_emails', ignore_result=True)
def send_missing_emails(inf_id, to_send=True):
    from debra.models import Influencer, MailProxyMessage

    inf = Influencer.objects.get(id=inf_id)

    messages_to_send = []
    for mp in inf.mails.all():
        last_week = datetime.datetime.today() - datetime.timedelta(days=7)
        try:
            last_message = mp.threads.filter(
                ts__gte=last_week,
                direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER,
                type=MailProxyMessage.TYPE_EMAIL,
            ).order_by('-ts')[0]
        except IndexError:
            pass
        else:
            messages_to_send.append(last_message)
    if to_send:
        print '* sending {} messages'.format(len(messages_to_send))
        for message in messages_to_send:
            message.send()
    return messages_to_send

@task(name='debra.brand_helpers.send_missing_emails_report', ignore_result=True)
def send_missing_emails_report():
    from debra import helpers
    from debra.models import Influencer

    mp_data = Influencer.objects.missing_emails_data()
    count = len(mp_data.keys())

    helpers.send_admin_email_via_mailsnake(
        "Missing emails daily report: {} found".format(count),
        "During our daily check we have found {} influencers with missing emails".format(count)
    )
