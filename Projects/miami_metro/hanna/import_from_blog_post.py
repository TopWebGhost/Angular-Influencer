"""
ImportProductFromBlogPost: This class is responsible for importing products from a given Posts object.
    Uses the ProductInfoFromUrlExtractor class to handle each url.

ProductInfoFromUrlExtractor: This class is responsible for
    Basic algo is simple:
    --- fetch that prod url using selenium
    --- once the selenium call returns, check if the driver.current_url's domain = prod url's domain
    --- if no => original prod url is the 'affiliate link' & final prod url is the prod url link
    --- run 'price, name, img url' fetch for the prod url using PageDetailExtractor code
"""
from celery.decorators import task
from debra.models import (Posts, Shelf, ProductModelShelfMap, Brands, ProductModel, ProductsInPosts,
                          ProductPrice, ColorSizeModel, Platform, User, LinkFromPost)
from xps import extractor
from xpathscraper import utils, xbrowser
import datetime
from django.conf import settings
from debra.bookmarklet_views import postprocess_new_item
from masuka import image_manipulator
from xps import models as xps_models
from platformdatafetcher import sponsorshipfetcher
from platformdatafetcher import platformutils
from platformdatafetcher import contentfiltering
from platformdatafetcher import postanalysis
from platformdatafetcher import producturlsextractor
from platformdatafetcher import categorization
import logging
from debra import db_util


log = logging.getLogger('hanna.import_from_blog_post')

exclude_domains = ['http://pinterest.com', 'http://lookbook.nu', 'http://facebook.com', 'http://retailmenot.com',
                   'http://luckymag.com', 'http://shareaholic.com', 'http://ebates.com', 'http://blogspot.com',
                   'http://instagram.com', 'http://twitter.com', 'http://flickr.com', 'http://google.com', 'http://yahoo.com',
                   'http://linkwithin.com', 'http://feedburner.com', 'http://currentlyobsessed.com', 'http://linkytools.com',
                   'http://photobucket.com', 'http://followgram.me', 'http://wordpress.com', 'http://www.bloglovin.com',
                   'http://wikipedia.com', 'http://tumblr.com', 'http://pose.com', 'http://polyvore.com', 'http://youtube.com',
                   'http://platform.twitter.com', 'http://d.adroll.com/', 'http://web.stagram.com/', 'http://typepad.com',
                   'http://accounts.google.com', 'http://en.wikipedia.org']

exclude_domains_set = {utils.domain_from_url(url) for url in exclude_domains}


HEADLESS_DISPLAY = settings.AUTOCREATE_HEADLESS_DISPLAY
MIN_IMG_SIZE = 200 * 200


class SaveProductInfoInWishlist(object):

    """
    Adds the info from ProductInfoFromUrlExtractor to the given Shelf by first creating the
    a) brand if it doesn't exist
    b) the product if it doesn't exist
    c) the ProductModelShelfMap
    """

    def __init__(self, shelf, product_in_post_model, create_date, post=None, imported_from_blog=False):
        self.user = shelf.user_id
        self.shelf = shelf
        self.prod = product_in_post_model
        self.create_date = create_date
        self.imported_from_blog = imported_from_blog
        # this contains the list of PMSMs created for this imported url
        self.pmsms = []
        self.post = post

    def check_if_prod_is_valid(self):
        """
        check to see if the product obtained after pdextractor is valid:
            -- at least we got a name and image
        """
        return self.prod.is_valid_product

    def _get_product(self):
        if isinstance(self.prod, ProductsInPosts):
                brand = SaveProductInfoInWishlist._get_brand(self.prod.prod.prod_url)
                prod_model = self.prod.prod
        if isinstance(self.prod, ProductInfoFromUrlExtractor):
            brand = SaveProductInfoInWishlist._get_brand(
                self.prod.redirected_prod_url if self.prod.is_affiliate_link else self.prod.url)
            prod_model = self.prod.prod

        prod_model.brand = brand
        prod_model.save()

        return prod_model

    def save_in_shelf(self):
        #assert self.check_if_prod_is_valid()

        prod_model = self._get_product()

        log.debug("Found prod_model: %s" % prod_model)
        pmsm = None

        # check if a ProductModelShelfMap already exists for the same prod_model and that it was imported
        if ProductModelShelfMap.objects.filter(product_model=prod_model,
                                               user_prof=self.user.userprofile if self.user else None,
                                               shelf=self.shelf,
                                               post=self.post if self.post else None).exists():
            log.debug("ProductModelShelfMap already exists for product: %s" % prod_model)
            pmsm = ProductModelShelfMap.objects.select_related('product_model__brand').get(product_model=prod_model,
                                                                                           user_prof=self.user.userprofile if self.user else None,
                                                                                           post=self.post if self.post else None,
                                                                                           shelf=self.shelf)
            if not pmsm.img_url_thumbnail_view:
                image_manipulator.create_images_for_wishlist_item(pmsm)
        if pmsm is None:
            pmsm = ProductModelShelfMap.objects.create(user_prof=self.user.userprofile if self.user else None,
                                                       product_model=prod_model,
                                                       imported_from_blog=True,
                                                       added_datetime=self.create_date,
                                                       shelf=self.shelf,
                                                       post=self.post if self.post else None,
                                                       influencer=self.post.influencer if self.post else None)
            postprocess_new_item(pmsm.id)
            # refetch the model so that we don't over-write with bad content
            pmsm = ProductModelShelfMap.objects.select_related('product_model__brand').get(id=pmsm.id)

        color_size_model = ColorSizeModel(product=prod_model)
        color_size_model.save()
        product_price = ProductPrice(product=color_size_model, price=prod_model.price, orig_price=prod_model.price)
        product_price.save()

        if prod_model.price > 0.0:
            pmsm.calculated_price = prod_model.price

        # set `savings` if we have a sale price
        if prod_model.saleprice > 0.0 and prod_model.saleprice < prod_model.price:
            pmsm.savings = prod_model.price - prod_model.saleprice
            pmsm.calculated_price = prod_model.saleprice
            product_price.price = prod_model.saleprice
            product_price.save()

        pmsm.current_product_price = product_price
        pmsm.show_on_feed = False

        # set `affiliate_prod_link` if it is
        if self.prod.is_affiliate_link:
            pmsm.affiliate_prod_link = self.prod.url

        pmsm.imported_from_blog = True
        pmsm.save()
        self.pmsms.append(pmsm)


        log.debug("Created ProductModelShelfMap (%s, %s, %s) in Shelf %s " %
                  (pmsm.id, pmsm.calculated_price, pmsm, self.shelf))
        return {'img_url_thumbnail_view': pmsm.img_url_thumbnail_view,
                'name': pmsm.product_model.name,
                'pmsm_id': pmsm.id}

    @staticmethod
    def _get_brand(prod_url):
        log.debug("_get_brand for %s" % prod_url)
        domain = utils.domain_from_url(prod_url)
        brand, created = Brands.objects.get_or_create(domain_name=domain)
        if brand.name == 'Nil':
            brand.name = domain.replace('www.', '').replace('.com', '').replace('/', '')
            brand.save()
        log.debug("Created: %s Brand: %s Domain: %s" % (created, brand, domain))
        return brand


class ProductInfoFromUrlExtractor(object):

    """
    Fetches the product info from a given  url
    """

    def __init__(self, url):
        self.url = url
        self.is_affiliate_link = False
        self.redirected_prod_url = url
        self.name = None
        self.img = None
        self.original_price = None
        self.sale_price = None
        self.headless_display = HEADLESS_DISPLAY
        self.is_valid_product = False
        self.prod = None
        self.brand = None

    def get_product_name(self):
        if self.name:
            return self.name.product_name
        return None

    def get_designer_name(self):
        if self.name:
            return self.name.brand_name
        return None

    def get_original_price_value(self):
        if self.original_price:
            return float(self.original_price.value)
        return None

    def get_sale_price_value(self):
        if self.sale_price:
            return float(self.sale_price.value)
        return None

    def get_img_url(self):
        return self.img

    def extract_product_info(self, e):
        # first check if this is a special case url (from *.affiliatetechnology.com)
        self.redirected_prod_url = extractor.normalize_product_url(self.url)
        if self.redirected_prod_url == self.url:
            # check if the url is redirecting to another one first (before we create a product object)
            self.redirected_prod_url = xbrowser.redirect_using_xbrowser(self.url)
            log.debug('redirected prod url: %r' % self.redirected_prod_url)

        # Set FOR AFFILIATE LINK
        if utils.domain_from_url(self.url) != utils.domain_from_url(self.redirected_prod_url):
            self.is_affiliate_link = True

        # Now GET PRODUCT INFO

        try:
            brand = xps_models.get_or_create_brand(self.redirected_prod_url)
            self.brand = brand
            # now return if this url doesn't refer to a product page (as it ends in a .com or similar)
            if ProductInfoFromUrlExtractor._is_not_product_page(self.redirected_prod_url):
                return

            self.prod = extractor.get_or_create_product(self.redirected_prod_url)
            log.debug("product %s product.id %s brand %s" % (self.prod, self.prod.id, brand))
            self.prod.brand = brand
            self.prod.save()

            res = e.extract_using_computed_xpaths(self.prod, quit_driver=False)
            log.debug("res %s" % res)
            log.debug("prod %s" % self.prod)

            # continue if the product page contains the add-to-cart button or out-of-stock keywords
            if res.valid_product_page or res.not_found_page:
                if 'name' in res.keys() and len(res['name']) > 0:
                    self.name = res['name'][0]
                    self.prod.name = self.get_product_name()
                if 'img' in res.keys() and len(res['img']) > 0 and res['img'][0].size >= MIN_IMG_SIZE:
                    self.img = res['img'][0].src
                    self.prod.img_url = self.img
                else:
                    print 'No image or too small'
                if 'price' in res.keys() and len(res['price']) > 0:
                    price = res['price'][0]
                    # print "Got price %s" % price
                    self.original_price = price.get_orig_price()
                    self.sale_price = price.get_sale_price()
                    # print "Orig: %s Sale: %s" % (self.get_original_price_value(), self.get_sale_price_value())
                    if self.original_price is not None:
                        self.prod.price = self.get_original_price_value()
                    if self.sale_price is not None:
                        self.prod.saleprice = self.get_sale_price_value()
                self.prod.save()
                # print "Found product %s %s name %s img %s" % (prod, prod.id, self.name, self.img)
                if self.name and self.img:
                    self.is_valid_product = True
                    log.debug("Product page is valid")
                else:
                    log.debug("Product page is invalid")
                if res.not_found_page:
                    log.debug("Product page %s is out of stock" % self.redirected_prod_url)
        except:
            log.exception('Could not extract product info from: {}'.format(self.url))


    def get_product_info(self):
        log.debug("Checking url: %s " % self.url)

        e = extractor.Extractor(
            headless_display=self.headless_display,
            reuse_xbrowser=False,
            sleep_after_load=5
        )
        try:
            self.extract_product_info(e)
        finally:
            e.cleanup_xresources()

    @staticmethod
    def _is_not_product_page(url):
        if url.endswith('.com') or url.endswith('com/') or url.endswith('index.html'):
            log.debug("%s is a home home" % url)
            return True

        if 'error' in url:
            log.debug("%s is an error page" % url)
            return True

        return False

    def __repr__(self):
        return "[%s] [Name: %s] [Img: %s] [Base price: %s] [Sale price: %s] [is_affiliate %s] [orig url: %s] \ " \
               "[redirected %s]" % (self.url, self.name, self.img, self.original_price, self.sale_price,
                                    self.is_affiliate_link, self.url, self.redirected_prod_url)


class ImportProductFromBlogPost(object):

    """
    Fetches the product infos of all product urls from a given post
    """

    def __init__(self, post):
        self.post = post
        self.create_date = post.create_date
        self.product_urls = post.product_urls(exclude_domains)

    def get_product_info_all(self):
        results = []
        for url in self.product_urls:
            res = ProductInfoFromUrlExtractor(url)
            res.get_product_info()
            # storing result in ProductInPosts
            results.append(res)
            prod = None
            if res.is_valid_product:
                prod = ProductModel.objects.get(id=res.prod.id)
            _, _ = ProductsInPosts.objects.get_or_create(post=self.post,
                                                         prod=prod,
                                                         is_affiliate_link=res.is_affiliate_link,
                                                         orig_url=url,
                                                         is_valid_product=res.is_valid_product)
        if self.post:
            self.post.products_import_completed = True
            self.post.save()
        return results


@task(name="hanna.import_from_blog_post.fetch_products_from_post", ignore_result=True)
def fetch_products_from_post(post_id, shelf_user_id):
    """
    1. We first figure out if this post is a sponsored post or not (using simple keyword matching)
    2. Next, we search for any widgets that the blogger has. If yes, we search for products inside them (sponsorshipfetcher.get_product_urls)
    3. Next, we search for product urls in the post content
    4. Now we iterate over all these product urls

    """
    log.debug("Fetching products from post_id %s" % post_id)
    post = Posts.objects.select_related('influencer', 'influencer__shelf_user', 'platform').get(id=post_id)
    with platformutils.OpRecorder('fetch_products_from_post', post=post):
        _do_fetch_products_from_post(post, shelf_user_id)


def _get_product_urls(post):
    product_urls_in_post = post.product_urls(exclude_domains)

    # add urls from text links for non-blog platforms
    if not post.platform.platform_name_is_blog:
        content = platformutils.iterate_resolve_shortened_urls(post.content)
        product_urls_in_post.update(
            contentfiltering.filter_urls(
                contentfiltering.find_all_urls(content),
                exclude_domains
            )
        )

    log.debug("We have %d product urls in the post content: %s" % (len(product_urls_in_post), product_urls_in_post))
    post.test_and_set_sponsored_flag()

    product_urls_in_widgets = sponsorshipfetcher.get_product_urls(post.id)
    log.debug("Products in widgets: %s" % product_urls_in_widgets)
    log.debug("We have %d product urls in the widget " % len(product_urls_in_widgets))

    additional_product_url_candidates = []
    if post.pin_source:
        additional_product_url_candidates.append(post.pin_source)

    influencer_blog_platforms = post.influencer.platform_set.filter(
        platform_name__in=Platform.BLOG_PLATFORMS
    )
    additional_product_urls = contentfiltering.filter_urls(
        additional_product_url_candidates,
        exclude_domains + [plat.url for plat in influencer_blog_platforms]
    )

    product_urls = product_urls_in_post.union(product_urls_in_widgets).union(additional_product_urls)

    # extract product urls from embedded urls
    urls_for_urls_extraction = [u for u in product_urls if utils.domain_from_url(u) in
                                producturlsextractor.ALL_SUPPORTED_DOMAINS]
    products_urls_extracted = []
    for url in urls_for_urls_extraction:
        products_urls_extracted += producturlsextractor.do_extract_product_urls(url)
    log.info('All products_urls_extracted: %r', products_urls_extracted)
    product_urls.update(products_urls_extracted)

    return product_urls


def _get_user_shelf(shelf_user_id):
    user = User.objects.get(id=shelf_user_id) if shelf_user_id else None
    if user:
        shelf = Shelf.objects.get_or_create(user_id=user, name="Products from my Blog", imported_from_blog=True)[0]
    else:
        shelves = Shelf.objects.filter(user_id=user, name="Products from my Blog", imported_from_blog=True)
        if shelves.exists():
            shelf = shelves[0]
        else:
            shelf = Shelf.objects.create(user_id=user, name="Products from my Blog", imported_from_blog=True)
    return shelf


def _do_fetch_products_from_post(post, shelf_user_id):
    if post.products_import_completed:
        log.debug("Product import already completed for post %r" % post)
        return

    # first issue the task to get the best image for the post to show in the front end
    image_manipulator.upload_post_image_task.apply_async([post.id], queue='post_image_upload_worker')

    log.debug("Found post: %s %s " % (post.url, post.create_date))

    shelf = _get_user_shelf(shelf_user_id)
    product_urls = _get_product_urls(post)

    log.debug("Overall, we have %d products" % len(product_urls), product_urls)
    brands = set()
    for prod_url in product_urls:
        log.debug("Checking prod_url: %s" % prod_url)
        try:
            res = ProductInfoFromUrlExtractor(prod_url)
            res.get_product_info()
            log.debug("got result: %s" % res)
            brands.add(res.brand)
            save_obj = SaveProductInfoInWishlist(shelf, res, post.create_date, post, True)
            if True: #save_obj.check_if_prod_is_valid():
                save_obj.save_in_shelf()
                pmsms = save_obj.pmsms
                log.debug("Looks like we created %d pmsms " % len(pmsms))
                for p in pmsms:
                    log.debug("PMSM: %s " % p.id)
                    if not p.admin_categorized:
                        p.imported_from_blog = True
                        p.show_on_feed = False
                    # this item has already been categorized
                    p.post = post
                    p.save()
                    brands.add(p.product_model.brand)
        except:
            log.exception('While processing prod_url=%r, post=%r', prod_url, post.id)
            pass

    broken_brands = [b for b in brands if b is None]
    if len(broken_brands) > 0:
        log.error('Broken (None) brand detected for post: {}, brands: {}'.format(post.id, brands))

    postanalysis.analyze_post_content(post.id, brands)

    # Refresh post content modified by analyze_post_content
    post = Posts.objects.get(id=post.id)
    post.products_import_completed = True
    post.save()

    # after we have finished fetching the products, create this list in the post model for showing it in the front-end
    post.get_product_json()

    # and then issue the categorization (categorization depends on get_products_json operation to finish)
    if post.platform.platform_name_is_blog:
        categorization.categorize_post.apply_async([post.id], queue='post_categorization')

    # Reanalyze links from social posts pointing to the analyzed post
    if post.platform.platform_name_is_blog:
        for link in LinkFromPost.objects.filter(dest_post=post):
            log.info('Reanalyzing links for post %r', link.source_post)
            postanalysis.analyze_post_content(link.source_post_id)

    log.info("Done with post %r" % post)


@task(name="hanna.imported_from_blog_post.create_wishlist_for_url_in_shelf", ignore_result=False)
def create_wishlist_for_url_in_shelf(shelf, prod_url, create_date=None):
    '''
    A celery task to create a wishlist item for a given url
    -- Used when a blogger creates a shelf on the fly and adds URLs in text fields
    '''
    try:
        res = ProductInfoFromUrlExtractor(prod_url)
        res.get_product_info()
    except:
        print "exception happened"
        return None
    if not create_date:
        create_date = datetime.datetime.today()
    save_obj = SaveProductInfoInWishlist(shelf, res, create_date)
    print "great, now checking if prod is valid: %d" % save_obj.check_if_prod_is_valid()
    if save_obj.check_if_prod_is_valid():
        return save_obj.save_in_shelf()
    return None


@task(name="hanna.imported_from_blog_post.fetch_prods_from_all_recent_posts", ignore_result=False)
def fetch_prods_from_all_recent_posts(platform_id, start_date):
    platform = Platform.objects.get(id=platform_id)
    posts = Posts.objects.filter(platform=platform, create_date__gte=start_date).exclude(
        products_import_completed__isnull=False)
    print "[Admin Edited] Ok, importing %d posts for %s" % (posts.count(), platform)
    for p in posts:
        fetch_products_from_post(p.id, platform.influencer.shelf_user.id if platform.influencer.shelf_user else None)


def _submit_fetch_prods(post_ids):
    print '%d tasks to submit' % len(post_ids)
    for i, id in enumerate(post_ids):
        post = Posts.objects.get(id=id)
        post.products_import_completed = False
        post.save()
        fetch_products_from_post.apply_async(
            args=[post.id, post.platform.influencer.shelf_user.id if post.platform.influencer.shelf_user else None], queue="import_products_from_post_latest")
        if i % 100 == 0:
            print 'Submitted', i


def fetch_prods_for_posts_with_sponsorships_but_no_products():
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
    select po.id
    from debra_posts po
    where not exists(select * from debra_productmodelshelfmap pmsm where pmsm.post_id=po.id)
    and exists(select * from debra_sponsorshipinfo si where si.post_id=po.id)
    and po.products_import_completed = true
    """)
    post_ids = [row[0] for row in cur]
    _submit_fetch_prods(post_ids)


def fetch_prods_for_posts_with_liketk_but_no_products():
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""
    select po.id
    from debra_posts po
    join debra_platform pl on po.platform_id=pl.id
    where not exists(select * from debra_productmodelshelfmap pmsm where pmsm.post_id=po.id)
    and content ilike '%liketk.it%'
    and po.products_import_completed=true
    and pl.platform_name='Instagram'
    """)
    post_ids = [row[0] for row in cur]
    _submit_fetch_prods(post_ids)
