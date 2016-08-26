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

class AEagleFamilySpider(CrawlSpider):
    name = "aeagle"

    #store_name = "Banana Republic"
    store_name = "Aerie"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    base_url = 'http://www.ae.com'
    count_scraped = 0
    urls_scraped = set()
    items_to_scrape = []
    items_scraped = []
    count = 0
    insert_date = datetime.datetime.now()


    handle_httpstatus_list = [301, 302]
    already_added_urls = []
    # prod url -> ss link url
    start_urls = []
    allowed_domains = ['ae.com',]

    new_arrivals = 0

    def __init__(self, *a, **kw):
        super(AEagleFamilySpider, self).__init__(*a, **kw)
        # start with the home page
        #self.start_urls.append("http://www.bananarepublic.gap.com/")
        #self.start_urls.append(self.base_url)
        #print "Hello"
        self.store_name = kw.get('store_name')
        self.base_url = kw.get('start_url')
        self.start_urls.append(self.base_url)
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))
        print self.new_arrivals
        print self.base_url
        print self.store_name

    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister

        print "NAVIGATION URL " + str(url)
        if 'index.jsp' in url:
            self.add_primary_nav_links(response, new_urls)

        # these contain category pages. they have links to other category pages and links to product pages
        if 'category' in url or 'catId' in url:
            self.add_category_links(response, new_urls)
            self.add_product_links(response, new_urls)

        # these are product pages
        if 'product' in url:
            valid_prod, product = self.parse_aeaglefamily(response)

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


    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        if self.new_arrivals == 0:
            primary_navs_path_1 = hxs.select('//div[@class="catNav"]/ul/li/ul/li/a/@href').extract()
            primary_navs_path_2 = hxs.select('//div[@class="catNav"]/ul/li/ul/li/ul/li/a/@href').extract()
        else:
            primary_navs_path_1 = hxs.select('//div[@class="catNav"]/ul/li/ul/li/a/span[contains (text(), "New Arrivals")]/../@href').extract()
            primary_navs_path_2 = hxs.select('//div[@class="catNav"]/ul/li/ul/li/a/span[contains (text(), "New Arrivals")]/../../ul/li/a/@href').extract()

        primary_navs_path = primary_navs_path_1 + primary_navs_path_2

        for p in primary_navs_path:
            url_to_follow = p
            if not (url_to_follow in self.already_added_urls):
                print "CATEGORY NAV URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        cat_navs_path = hxs.select('//div[@class="sProd"]/a/@href').extract()

        for p in cat_navs_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "PRODUCT URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)


    def add_primary_nav_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        primary_navs_path = hxs.select('//div[@id="topNav"]/div/ul/li/a/@href').extract()

        for p in primary_navs_path:
            url_to_follow = p
            if not (url_to_follow in self.already_added_urls):
                print "PRIMARY NAV URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def parse_aeaglefamily(self, response):
        #self.check_shelfit_validity(response)
        #return (False, None)
        hxs = HtmlXPathSelector(response)

        # find name of item
        item_name_path = hxs.select('//h1[@class="pName"]/text()')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            print "Invalid link:  " + str(response.url)
            return (False, None)
        item_name = item_name_path.extract()[0]
        logging.critical("Name: " + item_name.encode('utf-8'))

        self.count_scraped += 1

        meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
        if len(meta_tag_url) > 0:
            prod_url = meta_tag_url.extract()[0]
        else:
            prod_url = response.url

        logging.critical("PRODUCT URL:" + str(prod_url) + " ITEM_NAME " + item_name.encode('utf-8') + " TOTAL SO FAR " + str(self.count_scraped))

        gender = 'F'

        logging.critical("GENDER: " + gender)
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
        meta_tag_url = hxs.select('//meta[@property="og:image"]/@content')
        if len(meta_tag_url) > 0:
            prod_img_url = meta_tag_url.extract()[0]
        else:
            prod_img_url = ""


        # find description and keywords: these will be useful in categorization
        prod_desc = ''
        logging.critical("Description: " + prod_desc)

        # promo text
        promo_str = ""



        product, created_new = self._create_product_item(item_name, item_id_, str(prod_url), price_, \
                                                         sale_price_, gender, str(prod_img_url), promo_str, prod_desc)

        if product == None:
            logging.critical("Product is None----SHOULDN'T HAPPEN!!!!!******************")
            #import sys
            #sys.exit(1)

        ### HANDLE CATEGORIZATION
        if created_new:
            new_cat = simple_product_categorization(product)
            product.cat1 = new_cat["cat1"]
            product.cat2 = new_cat["cat2"]
            product.cat3 = new_cat["cat3"]
            product.save()

        logging.critical("Total unique items: " + str(len(self.all_items_scraped)) + " we have scraped so far: " +\
                          str(self.count_scraped) + " Unique URLs scraped: " + str(len(self.urls_scraped)))

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
            existing_item[0].insert_date = self.insert_date
            existing_item[0].save()
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
        #http://www.ae.com/web/browse/product.jsp?productId=2153_8490_126&catId=cat10025
        end_index = url.find('productId=')
        #url_t => http://www.anthropologie.com/anthro/product/shopsale-freshcuts/24084030
        url_t = url[end_index + len('productId='):]
        # start = last /
        start = url_t.rfind('&')
        if start >= 0:
            item_id = url_t[:start]
        else:
            item_id = url_t

        print "ITEM_ID " + str(item_id)


        price = -1

        # Don't care about sale price since we're going to do that calculation soon
        return (item_id, price, price)

