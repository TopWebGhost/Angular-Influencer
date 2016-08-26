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

class NYCSpider(CrawlSpider):
    name = "nyco"

    store_name = "New York & Company"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    count_scraped = 0
    urls_scraped = set()
    items_to_scrape = []
    items_scraped = []
    count = 0
    insert_date = datetime.datetime.now()

    handle_httpstatus_list = [302]
    already_added_urls = []
    start_urls = []
    allowed_domains = ['www.nyandcompany.com',]

    #fixing the error in the way we were finding out the prod_id
    #replacing old prod.c_idx by the correct idex
    correction_id_process = False

    new_arrivals = 0

    def __init__(self, *a, **kw):
        super(NYCSpider, self).__init__(*a, **kw)
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))
        self.base_url = kw.get('start_url')
        self.store_name = kw.get('store_name')
        print self.new_arrivals
        if not self.correction_id_process:
            self.start_urls.append(self.base_url)
        else:
            #find all prod objects and crawl only those URLs
            all_prods = ProductModel.objects.filter(brand__name = self.store_name)
            self.start_urls = [prod.prod_url for prod in all_prods]
            print "Found %d number of items " % (len(self.start_urls))

    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        new_urls = []
        # for home page.
        if not self.correction_id_process:
            print "Primary Navigation URL " + str(url)
            self.add_primary_nav_links(response, new_urls)

        # these contain category pages. they have links to other category pages and links to product pages
        if '/cat/' in url:
            self.add_category_links(response, new_urls)
            self.add_product_links(response, new_urls)

        # these are product pages
        if 'prod' in url:
            valid_prod, product = self.parse_nyc(response)

        self.count += 1

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
        primary_navs_path = hxs.select('//table[@id="topnav"]/tr/td/a/@href').extract()
        base_link = "http://www.nyandcompany.com"

        for p in primary_navs_path:
            url_to_follow = base_link + p
            if not (url_to_follow in self.already_added_urls):
                if self.new_arrivals == 0 or 'New-Arrivals' in url_to_follow:
                    print "Category URL: " + str(base_link + p)
                    new_urls.append(base_link + p)

    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)
        base_link = "http://www.nyandcompany.com"
        category_nav_path_1 = hxs.select('//div[@id="leftnav_wrapper"]/ul/li/a/@href').extract()
        category_nav_path_2 = hxs.select('//ul[@id="leftnav"]/li/ul/li/a/@href').extract()

        category_nav_path = category_nav_path_1 + category_nav_path_2

        for p in category_nav_path:
            url_to_follow = base_link + p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)


    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        base_link = "http://www.nyandcompany.com"

        product_path_1 = hxs.select('//div[@class="items_wrapper"]/ul/li/a/@href').extract()

        product_path_2 = hxs.select('//div[contains (@class,"pagination")]/div/a/@href').extract()

        product_path_3 = hxs.select('//div[@class="items_wrapper"]/p[contains (@class, "view-all")]/a/@href').extract()

        product_path = product_path_1 + product_path_2 + product_path_3

        for p in product_path:
            url_to_follow = base_link + p
            if not (url_to_follow in self.already_added_urls):
                print "Product URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)




    def parse_nyc(self, response):
        hxs = HtmlXPathSelector(response)
        # find name of item
        item_name_path = hxs.select('//h1/text()')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            return (False, None)
        item_name = item_name_path.extract()
        logging.critical("Name: " + str(item_name))

        self.count_scraped += 1

        '''
        PLAYING NICE: sleeping for 1min after crawling every 100 pages
        '''
        if self.count_scraped % 100 == 0:
            sleep(0) # sleep for 1 mins for express

        can_url_path = hxs.select('//link[@rel="canonical"]/@href')
        if len(can_url_path) > 0:
            prod_url = can_url_path.extract()[0]
        else:
            prod_url = response.url
        logging.critical("PRODUCT URL:" + str(prod_url) + " TITLE " + str(item_name) + " TOTAL SO FAR " + str(self.count_scraped))

        # find gender
        gender = 'F'
        logging.critical("Gender: " + gender)


        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs, prod_url)

        if item_id_ in self.all_items_scraped:
            print "RETURNING since we have already scraped " + str(item_id_)

        self.all_items_scraped.add(item_id_)

        logging.critical("ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))

        # extract image URL
        img_str = re.findall('strLarge = ["\w\d\/:_\$.?]+', str(response.body))
        prod_img_url = ""
        if len(img_str) > 0:
            img_str_ = img_str[0]
            img_str_parts = img_str_.split()
            if len(img_str_parts) > 2:
                prod_img_url = img_str_parts[2].strip('"')
        if prod_img_url == "":
            logging.critical("PROBLEM with Image URL for " + str(response.url))
        logging.critical("Image URL: " + str(prod_img_url))


        # find description and keywords: these will be useful in categorization
        desc = hxs.select('//p[@class="itemstyle_pdp"]/span[@class="details"]/text()').extract()
        logging.critical("Description: ")
        logging.critical(desc)
        prod_desc = desc

        # promo text
        promo_str = ""

        product, created_new = self._create_product_item(response.url, item_name[0], item_id_, str(prod_url), price_, \
                                            sale_price_, gender, str(prod_img_url), promo_str, prod_desc)

        if product == None:
            logging.critical("PROBLEM: product is None for URL " + str(response.url))

        if created_new:
            new_cat = simple_product_categorization(product)
            product.cat1 = new_cat["cat1"]
            product.cat2 = new_cat["cat2"]
            product.cat3 = new_cat["cat3"]
            product.save()

        logging.critical("Total unique items: " + str(len(self.all_items_scraped)) + " we have scraped so far: " +\
                          str(self.count_scraped) + " Unique URLs scraped: " + str(len(self.urls_scraped)))

        return (True, product)




    def avoid_redirection(self, request):
        request.meta.update(dont_redirect=True)
        #request.meta.update(dont_filter=True)
        return request


    def _create_product_item(self, orig_url, name, prod_id, prod_url, price, saleprice, gender, img_url, promo_text, prod_desc):
        from django.core.exceptions import ObjectDoesNotExist

        b = Brands.objects.get(name = self.store_name)

        existing_item = ProductModel.objects.filter(brand = b, c_idx = prod_id)
        print existing_item
        if len(existing_item) > 0:
            print "Item " + str(existing_item[0]) + " EXISTS. Not creating new one. We got " + str(len(existing_item)) + " number of copies"

            #correct the c_idx
            for e in existing_item:
                if e.prod_url != orig_url:
                    print "Correcting url: cur_url: " + str(e.prod_url) + " prod_url: " + str(prod_url)
                    e.c_idx = prod_id
                    e.prod_url = prod_url
                    e.save()
            #existing_item[0].insert_date = self.insert_date
            #existing_item[0].save()
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
        price = 0
        sale_price = 0
        item_id = '-1'
        item_id_path = hxs.select('//input[@name="editedProdid"]/@value').extract()
        if len(item_id_path) > 0:
            item_id = item_id_path[0]
        '''
        style_txt_array = hxs.select('//p[@class="itemstyle_pdp"]/text()').extract()
        if len(style_txt_array) > 0:
            style = style_txt_array[0]
            vals = style.split()
            if len(vals) > 1:
                item_id = int(vals[1].strip('.'))
        '''
        if item_id == '-1':
            print "ITEM_ID NOT FOUND for url: " + str(url)
        return (item_id, price, sale_price)




