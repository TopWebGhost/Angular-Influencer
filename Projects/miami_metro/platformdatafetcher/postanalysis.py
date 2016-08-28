import logging
import baker
import re

from celery.decorators import task
from django.db.models import F
import django.db

from xpathscraper import utils
from xpathscraper import xutils
from . import platformutils
from . import contentfiltering
from debra import models
import xps.models
from xps import extractor


log = logging.getLogger('platformdatafetcher.postanalysis')


_RE_HASHTAG = re.compile(r'[\s,.!:;]#(\w+)')
_RE_MENTION = re.compile(r'[\s,.!:;]@(\w+)')


def clean_content_for_keyword_search(content):
    if xutils.is_html(content):
        cleaned_content = xutils.strip_html_tags(content)
    else:
        cleaned_content = content

    # Remove urls from content - doesn't work because regexps don't handle fragments (#)
    #urls = contentfiltering.find_all_urls(cleaned_content, False)
    # for u in urls:
    #    cleaned_content = cleaned_content.replace(u, '')

    # let the space be the first character so the regexps can match the first word
    cleaned_content = ' ' + cleaned_content

    log.debug('Cleaned content: %s', cleaned_content)
    return cleaned_content


def _process_links(post, content):
    """
    This function's goal is to find linkages between posts.
    Say post p1 content contains url pointing to another post p2.

    And if p2 has brand_tags and BrandInPost, then we are going to copy them to p1 as well.

    Assumption: this only works if the p1 is a social platform post (e.g., Facebook post, Pin, Instagram, Tweet)
    If it is a blog post and it points to another blog point, it doesn't work.
    """
    if post.platform.platform_name_is_blog is True:
        return

    all_urls = contentfiltering.find_all_urls(content)
    for url in all_urls:
        url = utils.remove_query_params(url)
        ref_q = models.Posts.objects.filter(url=url)
        for ref in ref_q:
            log.info('Found reference to post %r with brand tags %r', ref, ref.brand_tags)

            # Create LinkFromPost
            models.LinkFromPost.objects.get_or_create(source_post=post, dest_post=ref)

            # Copy brand tags
            if ref.brand_tags:
                post.brand_tags = utils.add_to_comma_separated(post.brand_tags, ref.brand_tags.split(' ,'))
                post.save()

            # Copy BrandInPosts
            for bip in ref.brandinpost_set.all():
                models.BrandInPost.objects.get_or_create(brand=bip.brand, post=post)


def _domains_from_urls_to_exclude(influencer):
    plats = influencer.platform_set.exclude(platform_name__in=models.Platform.SOCIAL_PLATFORMS)
    return [plat.url for plat in plats]


def _resolve_pin_source(pin_source):
    from hanna import import_from_blog_post

    domain = utils.domain_from_url(pin_source)
    if models.Brands.objects.filter(domain_name=domain, supported=True).exists():
        return pin_source
    if domain in import_from_blog_post.exclude_domains_set:
        return pin_source
    if 'blogspot.' in domain or 'wordpress.' in domain or 'tumblr.' in domain:
        return pin_source
    pin_source_resolved = xutils.resolve_redirect_using_xbrowser(pin_source)
    return pin_source_resolved


def _do_analyze_post_content(post, additional_brands):
    from hanna import import_from_blog_post

    brands = set(additional_brands)

    content = platformutils.iterate_resolve_shortened_urls(post.content)
    log.debug('Content after resolving: %s', content[:1000])

    # extract Brands from urls
    exclude_domains_from_urls = import_from_blog_post.exclude_domains + \
        _domains_from_urls_to_exclude(post.influencer)
    brand_urls_candidates = contentfiltering.find_important_urls(content,
                                                                 exclude_domains_from_urls=exclude_domains_from_urls,
                                                                 exclude_root_links=False)
    # add text urls for non-blog platforms
    if not post.platform.platform_name_is_blog:
        brand_urls_candidates.update(contentfiltering.filter_urls(
            contentfiltering.find_all_urls(content),
            exclude_domains_from_urls))
    # add potential product link from pin_source
    if post.pin_source:
        pin_source_resolved = _resolve_pin_source(post.pin_source)
        log.debug('pin_source_resolved: %r', pin_source_resolved)
        brand_urls_candidates.update(contentfiltering.filter_urls(
            [pin_source_resolved],
            exclude_domains_from_urls))

    brand_urls_candidates = [extractor.normalize_product_url(url) for url in brand_urls_candidates]
    brand_urls_candidates = utils.unique_sameorder(brand_urls_candidates)
    log.info('brand_urls_candidates: %r', brand_urls_candidates)
    for b_url in brand_urls_candidates:
        brands.add(xps.models.get_or_create_brand(b_url))

    broken_brands = [b for b in brands if b is None]
    if len(broken_brands) > 0:
        log.error('Broken (None) brand detected when analyzing post: {}, brands: {}'.format(post.id, brands))

    log.info('Brands including blacklisted: %r', brands)
    #brands = {b for b in brands if not b.blacklisted}
    #log.info('Brands without blacklisted: %r', brands)

    # Create post.brand_tags from Brands
    if brands:
        brand_tags = [b.name for b in brands]
        post.brand_tags = utils.add_to_comma_separated(post.brand_tags, brand_tags)
        post.save()

    # Create BrandMentions from Brands
    for brand in brands:
        bm, created = models.BrandMentions.objects.get_or_create(influencer=post.influencer, brand=brand)
        bm.count_notsponsored = F('count_notsponsored') + 1 if not created else 1
        if post.is_sponsored:
            bm.count_sponsored = F('count_sponsored') + 1 if not created else 1
        log.info('Saving BrandMentions: %r', bm)
        bm.save()

    # Process hashtags # and mentions @
    cleaned_content = clean_content_for_keyword_search(content)

    hashtags = _RE_HASHTAG.findall(cleaned_content)
    hashtags = [x.lower() for x in hashtags]
    hashtags = utils.unique_sameorder(hashtags)
    log.debug('Found hashtags: %r', hashtags)

    mentions = _RE_MENTION.findall(cleaned_content)
    mentions = [x.lower() for x in mentions]
    mentions = utils.unique_sameorder(mentions)
    log.debug('Found mentions: %r', mentions)

    post.hashtags = utils.add_to_comma_separated(post.hashtags, hashtags)
    post.mentions = utils.add_to_comma_separated(post.mentions, mentions)
    post.save()

    # Insert data to *InPost models
    insert_brands_in_post(post, brands)
    insert_hashtags_in_post(post, hashtags)
    insert_mentions_in_post(post, mentions)

    _process_links(post, content)
    if post.pin_source:
        _process_links(post, pin_source_resolved)


def insert_to_in_post_table(model_cls, val_field, post, values, defaults={}):
    filter_kwargs = {'post': post, '%s__in' % val_field: values}
    existing = model_cls.objects.filter(**filter_kwargs).select_related(val_field)
    existing_vals = set(getattr(e, val_field) for e in existing)
    to_insert = [v for v in values if v not in existing_vals]
    log.info('%r to insert: %r', val_field, to_insert)
    try:
        model_params = []
        for v in to_insert:
            model_values = defaults.copy()
            model_values.update({'post': post, val_field: v})
            model_params.append(model_values)

        model_cls.objects.bulk_create([model_cls(**params) for params in model_params])
    except django.db.DatabaseError:
        log.exception('While insert_to_in_post_table')


def insert_brands_in_post(post, brands):
    return insert_to_in_post_table(models.BrandInPost, 'brand', post, brands)


def insert_hashtags_in_post(post, hashtags):
    return insert_to_in_post_table(models.HashtagInPost, 'hashtag', post, hashtags)


def insert_mentions_in_post(post, mentions):
    return insert_to_in_post_table(
        models.MentionInPost,
        'mention',
        post,
        mentions,
        defaults=dict(
            platform=post.platform,
            influencer=post.influencer,
            platform_name=post.platform.platform_name
        )
    )


@task(name='platformdatafetcher.postanalysis.analyze_post_content', ignore_result=True)
@baker.command
def analyze_post_content(post_id, additional_brands=[]):
    post = models.Posts.objects.get(id=int(post_id))
    with platformutils.OpRecorder('analyze_post_content', post=post):
        _do_analyze_post_content(post, additional_brands)
        log.info('Analyzed post content for %r', post)


@baker.command
def run_analyze_post_content(platform_name):
    infs = models.Influencer.objects.filter(show_on_search=True)
    plats = models.Platform.objects.filter(influencer__in=infs, platform_name=platform_name,
                                           url_not_found=False)
    posts = models.Posts.objects.filter(platform__in=plats).order_by('-create_date')
    for post in posts.iterator():
        try:
            analyze_post_content.apply_async([post.id], queue='indepth_fetching.%s' % platform_name)
        except:
            log.exception('For %r', post)


@baker.command
def run_analyze_post_content_for_social_platforms():
    for platform_name in ['Instagram', 'Twitter', 'Facebook', 'Pinterest']:
        run_analyze_post_content(platform_name)

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()



def add_instagram_post_comment_hashtags():
    """
    https://app.asana.com/0/42664940909123/64544792261628



    :return:
    """

    from debra.models import Posts, PostInteractions
    from time import time
    t = time()
    insta_posts = Posts.objects.filter(influencer__old_show_on_search=True,
                                       platform__platform_name="Instagram").exclude(platform__url_not_found=True)

    # limiting posts for test
    insta_posts = insta_posts.filter(id=107085632)

    for post in insta_posts:
        print('Performing post %s for influencer %s' % (post.id, post.influencer_id))
        self_post_interactions = PostInteractions.objects.filter(post=post)
        # self_post_interactions = PostInteractions.objects.filter(post=post, follower__influencer_id=post.influencer_id)

        print('Got %s post_interactions of the poster for it...' % self_post_interactions.count())
        for spi in self_post_interactions:
            print('   * interaction %s : influencer: %s' % (spi.id, spi.follower.influencer_id))

    print('Done for %s sec' % int(time() - t))


def check_hashtagers_names():
    """
    https://app.asana.com/0/42664940909123/64544792261628

    checking corellation between usernames of post writers and first followers' names

    :return:
    """
    from debra.models import Influencer, Posts, PostInteractions, Platform
    top_influencers = Influencer.objects.filter(old_show_on_search=True).order_by('-score_popularity_overall')[:1000]

    for inf in top_influencers:
        # print('Influencer: %s  Username: %s' % (inf.id, inf.name))

        insta_platforms = Platform.objects.filter(influencer_id=inf.id, platform_name='Instagram').exclude(url_not_found=True)
        for insta_platform in insta_platforms:
            # print('    Platform: %s  Detected name: %s' % (insta_platform.id, insta_platform.detected_name))

            posts_with_interactions = Posts.objects.filter(platform_id=insta_platform.id, postinteractions__isnull=False)[:3]
            for post in posts_with_interactions:
                # print('        Post: %s' % post.id)

                interactions = PostInteractions.objects.filter(post_id=post.id).order_by('id')
                if interactions.count() > 0:
                    print('Influencer: %s  Username: %s' % (inf.id, inf.name))
                    print('    Platform: %s  Detected name: %s' % (insta_platform.id, insta_platform.detected_name))
                    print('        Post: %s  url: %s' % (post.id, post.url))
                    print('            Post interaction: %s, firstname: %s' % (interactions[0].id, interactions[0].follower.firstname))



def perform_singaporean_interactions():

    from debra.models import InfluencersGroup
    from platformdatafetcher.pbfetcher import policy_for_platform
    from platformdatafetcher.socialfetcher import InstagramScrapingFetcher

    coll = InfluencersGroup.objects.get(name='Singapore Keywords')
    for inf in coll.influencers:
        insta = inf.platform_set.filter(platform_name='Instagram').exclude(url_not_found=True)
        insta_ids = insta.values_list('id', flat=True)
        print("Got %d instagram platforms to issue tasks" % len(insta_ids))
        for iid in insta_ids:
            fetch_post_interactions_for_platform_task.apply_async([iid], queue='fetch_instagram_post_interactions')


@task(name='platformdatafetcher.postanalysis.fetch_post_interactions_for_platform_task', ignore_result=True)
def fetch_post_interactions_for_platform_task(platform_id):
    """
    Function for celery task to fetch post interactions for platform_id
    :param platform_id:
    :return:
    """

    from debra.models import Platform
    from platformdatafetcher.pbfetcher import policy_for_platform
    from platformdatafetcher.socialfetcher import InstagramScrapingFetcher
    import datetime
    try:
        # Getting the instagram platform
        insta_platform = Platform.objects.get(id=platform_id, platform_name='Instagram')

        isf = InstagramScrapingFetcher(insta_platform, policy_for_platform(insta_platform))

        posts = insta_platform.posts_set.all().order_by('id')

        # Performing posts in chunks by 500
        total = posts.count()
        print("Got total %d posts" % total)
        chunk_size = 500
        start = 0

        while start < total:
            posts_to_perform = posts[start:start+chunk_size]
            start += chunk_size
            isf.fetch_post_interactions(list(posts_to_perform), None, None)

        # updating last_modified so that they are indexed the next day
        posts.update(last_modified=datetime.datetime.now())
    except Platform.DoesNotExist:
        pass


def check_inexisting_post_interactions():
    """
    This helper method just prints a list of platforms without connected PostInteractions objects for
    influencers belonging to InfluencerGroup 'Singapore Keywords'
    :return:
    """
    from debra.models import InfluencersGroup, PostInteractions

    missing = []

    coll = InfluencersGroup.objects.get(name='Singapore Keywords')
    coll_influencers = coll.influencers
    print('Total number of influencers: %s' % len(coll_influencers))
    c = 0
    for inf in coll_influencers:
        if c % 1000 == 0:
            print('Performed %s influencers...' % c)

        insta = inf.platform_set.filter(platform_name='Instagram').exclude(url_not_found=True)
        insta_ids = insta.values_list('id', flat=True)
        for iid in insta_ids:
            cntr = PostInteractions.objects.filter(platform_id=iid).count()
            if cntr == 0:
                missing.append({'inf_id': inf.id, 'platform_id': iid})

        c += 1

    print('missing:')
    print(missing)