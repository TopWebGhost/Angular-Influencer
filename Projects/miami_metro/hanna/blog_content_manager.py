'''
    Blog Content manager class

    Trigger Events:
    a) when a new blogger signs up
    b) periodic crawls
    c) when we automatically add a blogger

    For the given blog url,
    a) fetch the posts via the `fetcher`
    b) find product urls in each post
    c) store the product url and the corresponding meta data in the default shelf
'''
from celery.decorators import task
import platformdatafetcher
from platformdatafetcher.fetcher import fetcher_for_platform, try_detect_platform_name
from platformdatafetcher.platformextractor import extract_platforms_from_platform
from debra.models import Platform, Influencer, Posts, User, Brands, ProductModel, Shelf
from debra.models import PostInteractions, ProductsInPosts
from import_from_blog_post import ImportProductFromBlogPost, SaveProductInfoInWishlist
from django.core.mail import send_mail
from . import standardize

class BlogContentManager(object):

    def __init__(self, url, user=None, shelf_name="Products from my Blog"):
        '''
        url : url of the blog (shouldn't be a bloglovin url)
        '''
        assert (not 'bloglovin' in url)

        self.url = url
        self.user = user
        self.shelf = None
        self.shelf_name = shelf_name

        self.platform = self._set_platform()

        try:
            self.fetcher = fetcher_for_platform(self.platform)
        except:
            self.fetcher = None
            pass

        self.posts = []
        self.error_urls = []

    def _set_platform(self):
        platform, created = Platform.objects.get_or_create(url=self.url)
        #set platform name
        platform_name, corrected_url = try_detect_platform_name(self.url)
        print "Got platform_name %s corrected_url %s " % (platform_name, corrected_url)
        if platform_name:
            platform.platform_name = platform_name
            platform.save()
        return platform

    def clean_content(self):
        print "Cleaning posts for %s" % self.platform
        posts = Posts.objects.filter(platform=self.platform)
        interactions = PostInteractions.objects.filter(post__platform=self.platform)
        interactions.delete()
        posts.delete()

    def get_all_posts_in_db(self):
        posts = Posts.objects.filter(platform=self.platform)
        return posts

    def fetch_social_handlers(self):
        '''
        Gets all social network profile URLs of this blogger, e.g., their facebook, pinterest, twitter, instagram
        '''
        return extract_platforms_from_platform(self.platform.id, to_save=True)

    def crawl_blog_posts(self, max_pages=None):
        '''
        Get blog posts & post interactions for the platform
        if max_pages is not specified, we try to fetch all
        else, we fetch only max_pages worth of posts
        '''
        if not self.fetcher:
            print "Fetcher not found, so returning None"
            return (None, None)
        self.posts = self.fetcher.fetch_posts(max_pages=max_pages)
        return

    def fetch_products_from_recently_crawled_posts(self, howmany_posts=10):
        '''
        import products from most recently `howmany` number of posts
        '''
        ordered_posts = Posts.objects.filter(platform=self.platform,
                                             products_import_completed__isnull=True).order_by('-create_date')
        print "Got %d number of ordered posts " % len(ordered_posts)
        if len(ordered_posts) > howmany_posts:
            ordered_posts = ordered_posts[:howmany_posts]

        for post in ordered_posts:
            self._fetch_products_from_post(post)

    def fetch_products_from_given_posts(self, post_ids):
        for pid in post_ids:
            post = Posts.objects.get(id=pid)
            self._fetch_products_from_post(post)
            post.products_import_completed = True
            post.save()

    def _fetch_products_from_post(self, post):
        '''
        Private method:
        '''
        importer = ImportProductFromBlogPost(post)
        results = importer.get_product_info_all()
        print "Post: %s, Product results: %s" % (post.url, results)
        return results

    def save_products_from_given_posts(self, post_ids):
        if self.user:
            self.shelf, created = Shelf.objects.get_or_create(user_id=self.user, name=self.shelf_name)
            self.shelf.user_created_cat = True
            self.shelf.save()
        else:
            print "no user given, so not sure which shelf to save these items in."
            return

        for pid in post_ids:
            post = Posts.objects.get(id=pid)
            print "Post %s" % post
            self._save_products_in_shelf(post)

    def _save_products_in_shelf(self, post):
        '''
        For the given post and the associated products, save it in the default shelf.
        '''

        products_in_post = ProductsInPosts.objects.filter(post=post, is_valid_product=True)
        print "Found %d valid products." % len(products_in_post)
        for prod in products_in_post:
            print "Trying to save prod: %s %s %s" % (prod.prod.id, prod.is_affiliate_link, prod.orig_url)
            print "Using create date of the post: %s" % post.create_date
            save_obj = SaveProductInfoInWishlist(self.shelf, prod, post.create_date)
            save_obj.save_in_shelf()

    def get_error_urls(self):
        '''
        return urls that we had trouble fetching info from
        '''
        return self.error_urls

    ### TO DO IN A BIT
    def crawl_facebook_posts(self):

        return

    def crawl_pinterest_posts(self):

        return

    def crawl_instagram_posts(self):
        return

    def crawl_twitter_posts(self):
        return


##### This task fetches new posts
##### If max_pages_to_crawl is None, this fetches all posts.
##### TODO: need to implement an interface to fetch only new posts
@task(name="hanna.blog_content_manager.update_blogger_content", ignore_result=True)
def update_blogger_content(influencer, max_pages_to_crawl=None):
    try:
        print "Starting update_blogger_content for %s for %s pages " % (influencer.blog_url, max_pages_to_crawl)
        manager = BlogContentManager(influencer.blog_url)
        manager.crawl_blog_posts(max_pages=max_pages_to_crawl)
    except Exception, exc:
        raise update_blogger_content.retry(exc=exc)






def save_products_from_posts(influencer, user, shelf_name, post_ids):
    bb = BlogContentManager(influencer.blog_url, user, shelf_name)
    bb.save_products_from_given_posts(post_ids)

@task(name="hanna.blog_content_manager.start_tracking_blog", ignore_result=True)
def start_tracking_blog(blog_url):
    '''
    1. First, standardize the blog_url (this will create a influencer+platform obj or fetch corresponding
        to the standardized url)
    2. Then create a crawler manager for this blog
    3. Start crawling the entire blog
    '''

    influencer = standardize.get_influencer(blog_url)
    platform = standardize.get_blog_platform(blog_url)
    print "Got influencer (%s, %s) for blog_url %s" % (influencer, influencer.blog_url, blog_url)
    manager = BlogContentManager(influencer.blog_url)
    print "manager.platform.id: %s platform.id: %s" % (manager.platform.id, platform.id)
    assert manager.platform.id == platform.id

    if Posts.objects.filter(platform=platform).exists():
        print "We should save items that have been imported corresponding to the posts that have already been crawled"
        #posts = Posts.objects.filter(platform=platform)
        #post_ids = [post.id for post in posts]
        #import_products_from_posts(influencer, user, post_ids)
        manager.fetch_social_handlers()
    else:
        print "We should start crawling at least the social handlers and few posts"
        manager.crawl_blog_posts()

    return







