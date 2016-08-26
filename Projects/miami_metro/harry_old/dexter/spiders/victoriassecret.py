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
from debra.modify_shelf import store_spec_product_categorization
from debra.modify_shelf import static_name_cat_mapping, update_category_info_in_prod_model

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)

class VictoriasSecretSpider(CrawlSpider):
    name = "victoriassecret"
    
    store_name = "Victoria's Secret"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    base_url = 'http://www.victoriassecret.com'
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
    allowed_domains = ['victoriassecret.com',]

    new_arrivals = 0

    def __init__(self, *a, **kw):
        super(VictoriasSecretSpider, self).__init__(*a, **kw)
        # start with the home page
        self.base_url = kw.get('start_url')
        self.store_name = kw.get('store_name')        
        #print "Hello"   
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))
        self.start_urls.append(self.base_url)
        
        
    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister
        
        print "NAVIGATION URL " + str(url) 
        self.add_primary_nav_links(response, new_urls)
        
        # these contain category pages. they have links to other category pages and links to product pages
        self.add_category_links(response, new_urls)
        self.add_product_links(response, new_urls)
        
        # these are product pages
        if 'ProductID' in url:
            valid_prod, product = self.parse_vs(response)
        
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
        
        primary_navs_path_1 = hxs.select('//ul[@id="leftnav"]/li/ul/li/a/@href').extract()
        
        primary_navs_path = primary_navs_path_1
        
        for p in primary_navs_path:
            url_to_follow = p
            if not (url_to_follow in self.already_added_urls):

                print "CATEGORY NAV URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)
                new_urls.append(url_to_follow + '?pageAt=all')
                
    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)
        
        cat_navs_path = hxs.select('//ul[@id="collection"]/li/ul/li/a/@href').extract()
            
        for p in cat_navs_path:
            url_to_follow = p
            if not (url_to_follow in self.already_added_urls):
                print "PRODUCT URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)
                
                
    def add_primary_nav_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)
        if self.new_arrivals == 0:
            primary_navs_path = hxs.select('//div[@id="nav"]/div/div/ul/li/a/@href').extract()
        else:
            primary_navs_path = hxs.select('//div[@id="nav"]/div/div/ul/li[@id="whats-new"]/a/@href').extract()
            
        for p in primary_navs_path:
            url_to_follow = p
            if not (url_to_follow in self.already_added_urls):
                print "PRIMARY NAV URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)
        
    def parse_vs(self, response):
        #self.check_shelfit_validity(response)
        #return (False, None)
        hxs = HtmlXPathSelector(response)
        
        # find name of item
        item_name = ''
        meta_name = hxs.select('//meta[@property="og:title"]/@content')
        if len(meta_name) > 0:
            item_name = meta_name.extract()[0]
        if len(meta_name) == 0:
            self.invalid_links += 1
            print "Invalid link:  " + str(response.url)
            return (False, None)
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
                
        
        logging.critical("Total unique items: " + str(len(self.all_items_scraped)) + " we have scraped so far: " +\
                          str(self.count_scraped) + " Unique URLs scraped: " + str(len(self.urls_scraped)))
        
        return (True, product)
        
        
    
        
    def _create_product_item(self, name, prod_id, prod_url, price, saleprice, gender, img_url, promo_text, prod_desc):
        from django.core.exceptions import ObjectDoesNotExist
        
        
        b = Brands.objects.get(name = self.store_name)
        
        existing_item = ProductModel.objects.filter(brand = b).filter(c_idx = prod_id)
        print existing_item
        if len(existing_item) > 0:
            print "Item " + str(existing_item[0]) + " EXISTS. Not creating new one. Returning...."
            #existing_item[0].insert_date = self.insert_date
            #existing_item[0].save()
            return (existing_item[0], False)
             
        logging.critical("CREATE_PRODUCT OBJ: foreign key " + str(b))
        item = ProductModel.objects.create(brand = b, 
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
        id_path = hxs.select('//input[@name="COREMETRICSID"]/@value').extract()
        item_id = ''
        if len(id_path) > 0:
            item_id = id_path[0]
        
        print "ITEM_ID " + str(item_id)

        
        price = -1
            
        # Don't care about sale price since we're going to do that calculation soon
        return (item_id, price, price)
        