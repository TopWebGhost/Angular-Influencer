from scrapy.spider import BaseSpider
from scrapy.contrib.spiders import CrawlSpider, Rule
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from scrapy.selector import HtmlXPathSelector
from scrapy.item import Item
from scrapy.http import Request
import re
from scrapy.exceptions import CloseSpider
import datetime
import logging
import commands
from harry.dexter.items import Category, ProductItem, ColorSizeItem, CategoryItem
from debra.models import Brands, ProductModel, Items
import os, errno
from time import sleep
import copy
import urllib
from debra.view_shelf import simple_product_categorization

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)

class AnnFamilySpider(CrawlSpider):
    name = "ann_family"

    store_name = "Ann Taylor"
    #store_name = "Loft"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    count_scraped = 0
    urls_scraped = set()
    items_to_scrape = []
    items_scraped = []
    count = 0

    insert_date = datetime.date.today()

    handle_httpstatus_list = [302]
    already_added_urls = []
    # prod url -> ss link url
    start_urls = []
    allowed_domains = ['anntaylor.com','loft.com']

    new_arrivals = 0

    def __init__(self, *a, **kw):
        super(AnnFamilySpider, self).__init__(*a, **kw)
        print "Kwargs: %s " % kw
        self.store_name = kw.get('store_name')
        self.base_url = kw.get('start_url')
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))
        self.start_urls.append(self.base_url)
        # start with the home page
        #if self.store_name == "Ann Taylor":
        #    self.start_urls.append("http://www.anntaylor.com/")
        #if self.store_name == "Loft":
        #    self.start_urls.append("http://www.loft.com/")


    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister
        print "USEFUL URL " + str(url)
        self.add_primary_nav_links(response, new_urls)
        self.add_category_links(response, new_urls)
        # these contain category pages. they have links to other category pages and links to product pages
        if 'department' in url or '/cat/' in url or 'category' in url:
            #if response.request.meta.get('redirect_urls'):
            #    print "Redirected from " + str(response.request.meta.get('redirect_urls')[0])
            self.add_category_links(response, new_urls)
            self.add_product_links(response, new_urls)
            #print "\n---SCRAPING PAGE---\n"

        # these are product pages
        if 'product' in url:
            valid_prod, product = self.parse_ann_family(response)

        self.count += 1

        sleep(1)
        print "Total pages scraped " + str(self.count_scraped) + " Total URLS " + str(self.count) + \
              " Total invalid links " + str(self.invalid_links)

        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                prod = ProductModel.objects.filter(prod_url = url_to_follow)
                if len(prod) == 0:
                    self.already_added_urls.append(url_to_follow)
                    yield Request(url_to_follow, callback=self.parse)


    def add_primary_nav_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)
        primary_navs_path = hxs.select('//div[@id="nav-site"]/ul/li/div/a/@href').extract()

        for p in primary_navs_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "Primary NAV URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        category_nav_path = hxs.select('//div[@id="nav-site"]/ul/li/div/ul/li/a')

        for p in category_nav_path:
            style = p.select('./@style').extract()[0]
            if self.new_arrivals == 0 or 'newarr' in style:
                url_to_follow = self.base_url + p.select('./@href').extract()[0]
                if not (url_to_follow in self.already_added_urls):
                    print "Category URL: " + str(url_to_follow)
                    new_urls.append(url_to_follow)



    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)



        product_path_1 = hxs.select('//div[contains (@class, "products")]/div/div/div/div/a[@class="clickthrough"]/@href').extract()

        # VIEW ALL link on the category page
        product_path_2 = hxs.select('//ol[@class="pages"]/li/a[contains (text(), "VIEW")]/@href').extract()


        product_path = product_path_1 + product_path_2

        for p in product_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "Product URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)




    def parse_ann_family(self, response):
        hxs = HtmlXPathSelector(response)

        # find name of item
        item_name_path = hxs.select('//div[@class="hd-info"]//h1/text()')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            print "Invalid link:  " + str(response.url)
            return (False, None)
        item_name = item_name_path.extract()[0]
        logging.critical("Name: " + str(item_name))

        self.count_scraped += 1


        meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')

        prod_url = meta_tag_url.extract()[0]
        logging.critical("PRODUCT URL:" + str(prod_url) + " ITEM_NAME " + str(item_name) + " TOTAL SO FAR " + str(self.count_scraped))

        # Ann Taylor is for women only
        gender = 'F'

        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs, prod_url)

        if item_id_ in self.items_scraped:
            logging.critical("ITEM ALREADY SCRAPED " + str(item_id_))
            return (False, None)
        else:
            self.items_scraped.append(item_id_)

        logging.critical("ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))
        if price_ > sale_price_:
            logging.critical("SALE on ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))


        # extract image URL
        prod_img_path = hxs.select('//img[@id="productImage"]/@src')
        prod_img_url = str(prod_img_path.extract()[0])
        logging.critical("Image URL: " + str(prod_img_url))


        # find description and keywords: these will be useful in categorization
        desc = hxs.select('//div[@class="gu gu-first description"]/p/text()').extract()
        prod_desc = ''.join(desc)
        logging.critical("Description: " + prod_desc)

        # promo text
        # DIDN'T FIND ANY
        #promo_path = hxs.select('//span[@class="cat-pro-promo-text"]//font/text()').extract()
        #promo_str = str(promo_path)
        #logging.critical("Promotion: ")
        #logging.critical(promo_str)
        promo_str = ""



        product, created_new = self._create_product_item(item_name, item_id_, str(prod_url), price_, \
                                                         sale_price_, gender, str(prod_img_url), promo_str, prod_desc)

        if created_new:
            new_cat = simple_product_categorization(product)
            product.cat1 = new_cat["cat1"]
            product.cat2 = new_cat["cat2"]
            product.cat3 = new_cat["cat3"]
            product.save()


        #self._store_in_file(response, item_id_)
        #raise CloseSpider('Blah')
        logging.critical("Total unique items: " + str(len(self.all_items_scraped)) + " we have scraped so far: " +\
                          str(self.count_scraped) + " Unique URLs scraped: " + str(len(self.urls_scraped)))
        #raise SystemExit

        return (True, product)


    def process_links_none(self, links):
        print "Links from BVReviews: " + str(links)
        return set()

    def process_links_sub(self, links):
        return links



    def avoid_redirection(self, request):
        request.meta.update(dont_redirect=True)
        #request.meta.update(dont_filter=True)
        return request


    def _create_product_item(self, name, prod_id, prod_url, price, saleprice, gender, img_url, promo_text, prod_desc):
        from django.core.exceptions import ObjectDoesNotExist

        b = Brands.objects.get(name = self.store_name)

        existing_item = ProductModel.objects.filter(brand = b).filter(c_idx = prod_id)
        print existing_item
        if len(existing_item) > 0:
            print "Item " + str(existing_item[0]) + " EXISTS. Not creating new one. Returning...."
            return (existing_item[0], False)

        logging.critical("CREATE_PRODUCT OBJ: foreign key " + str(b))
        item = ProductModel(brand = b,
                            c_idx = prod_id,
                            name = name,
                            prod_url = prod_url,
                            price = price,
                            saleprice = saleprice,
                            promo_text = promo_text,
                            gender = gender,
                            img_url = img_url,
                            description = prod_desc,
                            insert_date = self.insert_date,)

        #print item
        item.save()
        print "CREATING NEW PRODUCT MODEL OBJ"
        #return (item.save(), True)
        return (item, True)


    def _find_price(self, hxs, url):
        #item_id_elem = hxs.select('//div[@class="details"]/p/text()')
        #item_id_full = item_id_elem.extract()[0] #self.find_itemid_in_url(url)
        # item_id_full has the following content: Style #258734
        #item_id = item_id_full[7:]
        #print "ITEM_ID " + str(item_id)
        item_id = ''
        id2_path = hxs.select('//input[@name="productId"]/@value').extract()
        if len(id2_path) > 0:
            item_id = id2_path[0]
        return (item_id, 0, 0)
