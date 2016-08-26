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
from debra.modify_shelf import simple_product_categorization

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)

class AberSpider(CrawlSpider):
    name = "aber"
    #store_name = "Abercrombie & Fitch"
    #store_name = "Hollister"
    store_name = "Gilly Hicks"
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
    allowed_domains = ['abercrombie.com', 'hollisterco.com', 'gillyhicks.com']

    base_url = ''
    new_arrivals = 0

    def __init__(self, *a, **kw):
        super(AberSpider, self).__init__(*a, **kw)
        self.store_name = kw.get('store_name')
        self.base_url = kw.get('start_url')
        self.start_urls.append(self.base_url)
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))
        print self.new_arrivals
        print self.base_url
        print self.store_name

        #if self.store_name == "Abercrombie & Fitch":
        #    self.start_urls.append("http://www.abercrombie.com/")
        #if self.store_name == "Hollister":
        #    self.start_urls.append("http://www.hollisterco.com/")
        #if self.store_name == "Gilly Hicks":
        #    self.start_urls.append("http://www.gillyhicks.com/")



    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister
        if 'StoreView' in url or 'HomePage' in url:
            print "USEFUL URL " + str(url)
            self.add_primary_nav_links(response, new_urls)

        # these contain category pages. they have links to other category pages and links to product pages
        if 'CategoryDisplay' in url:
            self.add_category_links(response, new_urls)
            self.add_product_links(response, new_urls)

        # these are product pages
        if 'ProductDisplay' in url:
            valid_prod, product = self.parse_aber(response)

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
        primary_navs_path = hxs.select('//div[@id="primary-nav"]/ul/li/a/@href').extract()
        base_link = self.base_url + "webapp/wcs/stores/servlet/"

        for p in primary_navs_path:
            url_to_follow = base_link + p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(base_link + p)
                new_urls.append(base_link + p)

    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)
        if self.new_arrivals:
            category_nav_path = hxs.select('//div[@id="category-nav"]/ul/li/a[text()="New Arrivals"]/@href').extract()
        else:
            category_nav_path = hxs.select('//div[@id="category-nav"]/ul/li/a/@href').extract()

        for p in category_nav_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(self.base_url + p)
                new_urls.append(self.base_url + p)

    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)
        base_link = self.base_url + "webapp/wcs/stores/servlet/"

        product_path = hxs.select('//li[contains (@class, "product-wrap")]/div/div/a/@href').extract()

        for p in product_path:
            url_to_follow = base_link + p
            if not (url_to_follow in self.already_added_urls):
                print "Product URL: " + str(base_link + p)
                new_urls.append(base_link + p)



    def parse_aber(self, response):
        #self.check_shelfit_validity(response)
        #return
        hxs = HtmlXPathSelector(response)

        # find name of item
        item_name_path = hxs.select('//meta[@property="og:title"]/@content').extract()
        if len(item_name_path) == 0:
            self.invalid_links += 1
            return (False, None)
        item_name = item_name_path[0]
        logging.critical("Name: " + str(item_name))

        self.count_scraped += 1

        prod_url = response.url
        logging.critical("PRODUCT URL:" + str(prod_url) + " TITLE " + str(item_name) + " TOTAL SO FAR " + str(self.count_scraped))

        # find gender
        gender = 'F'
        gender_path = hxs.select('//div[@id="primary-nav"]/ul/li[contains (@class, "current")]/a/text()').extract()
        if len(gender_path) > 0:
            gender_tmp = gender_path[0]
            if 'M' == gender_tmp[0]:
                gender = 'M'
        logging.critical("Gender: " + gender)


        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs, prod_url)

        if item_id_ in self.all_items_scraped:
            print "RETURNING since we have already scraped " + str(item_id_)

        self.all_items_scraped.add(item_id_)

        logging.critical("ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))

        # extract image URL
        prod_img_url = ""
        img_path = hxs.select('//img[@class="prod-img"]/@src').extract()
        if len(img_path) > 0:
            prod_img_url = img_path[0]
        if prod_img_url == "":
            logging.critical("PROBLEM with Image URL for " + str(response.url))
        logging.critical("Image URL: " + str(prod_img_url))


        # find description and keywords: these will be useful in categorization
        desc = hxs.select('//meta[@property="og:description"]/@content').extract()[0]
        logging.critical(desc)
        prod_desc = desc

        # promo text
        promo_str = ""



        product, created_new = self._create_product_item(item_name[0], item_id_, str(prod_url), price_, \
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
        #raise SystemExit

        return (True, product)




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
        item_id_path = hxs.select('//input[@name="productId"]/@value')
        if len(item_id_path) > 0:
            tmp = item_id_path.extract()
            item_id = tmp[0]

        item_price_path = hxs.select('//input[@name="price"]/@value')
        if len(item_price_path) > 0:
            tmp = item_price_path.extract()
            price = float(tmp[0].strip('$'))




        print "ITEM_ID %s PRICE %f" % (item_id, price)
        return (item_id, price, sale_price)




