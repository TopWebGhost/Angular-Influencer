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
from django.utils.encoding import smart_str, smart_unicode

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)

class DSWSpider(CrawlSpider):
    name = "dsw"

    store_name = "DSW"
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
    allowed_domains = ['dsw.com',]

    base_url = 'http://www.dsw.com'

    new_arrivals = 0

    def __init__(self, *a, **kw):
        super(DSWSpider, self).__init__(*a, **kw)
        self.start_urls.append(self.base_url)
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))

    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister

        print "USEFUL URL " + str(url)
        self.add_primary_nav_links(response, new_urls)

        # these contain category pages. they have links to other category pages and links to product pages
        self.add_category_links(response, new_urls)
        if 'collection' in url:
            self.add_product_links(response, new_urls)

        # these are product pages
        if 'prodId' in url:
            self.parse_dsw(response)

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
        primary_navs_path = hxs.select('//div[@id="primaryNav"]/div/a/@href').extract()

        for p in primary_navs_path:
            url_to_follow =  self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        if self.new_arrivals == 0:
            category_nav_path_1 = hxs.select('//div[@id="leftNavZone"]/ul/li/a/@href').extract()
            category_nav_path_2 = hxs.select('//div[@id="leftNavZone"]/ul/li/ul/li/a/@href').extract()
        else:
            category_nav_path_1 = hxs.select('//div[@id="leftNavZone"]/ul/li/a[contains (text(), "New Arrivals")]/@href').extract()
            category_nav_path_2 = []

        category_nav_path = category_nav_path_1 + category_nav_path_2


        for p in category_nav_path:
            p = p.replace('page-1', 'page-1?view=all')
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def get_id_from_url(self, url):

        import re

        pattern = 'PRDOVR~[\d]+'
        pattern_comp = re.compile(pattern)
        results = pattern_comp.findall(url)
        vals = []

        if len(results) > 0:
            for res in results:
                vals.append(res.strip('PRDOVR~'))

        return vals

    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        product_path_1 = hxs.select('//div[@id="productZone"]/div/div/div/a/@href').extract()

        product_path = product_path_1

        for p in product_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "Product URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)



    def parse_dsw(self, response):
        hxs = HtmlXPathSelector(response)

        meta_tag_item_name = hxs.select('//meta[@property="og:title"]/@content')
        if len(meta_tag_item_name) > 0:
            item_name = meta_tag_item_name.extract()[0]
        else:
            item_name_path = hxs.select('//title/text()')
            if len(item_name_path) > 0:
                item_name = item_name_path.extract()[0]
            else:
                logging.error("Not a product page: " + response.url)
                return (False, None)
        logging.critical(smart_str(item_name))

        self.count_scraped += 1


        meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
        if len(meta_tag_url) > 0:
            prod_url = meta_tag_url.extract()[0]
        else:
            prod_url = response.url

        logging.critical("PRODUCT URL:" + smart_str(prod_url) + " TITLE " + smart_str(item_name) + \
                         " TOTAL SO FAR " + str(self.count_scraped))


        # find gender
        gender = 'M'
        if prod_url.lower().find('women') >= 0 or prod_url.lower().find('girl') >= 0:
            gender = 'F'
        logging.critical("Gender: " + gender)


        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs)

        if item_id_ in self.items_scraped:
            logging.critical("ITEM ALREADY SCRAPED " + smart_str(item_id_) + ". RETURNING.")
            return  (True, None)
        else:
            self.items_scraped.append(item_id_)

        logging.critical("ITEM_ID " + item_id_ + " PRICE " + smart_str(price_) + " SALE PRICE " + smart_str(sale_price_))
        if price_ > sale_price_:
            logging.critical("SALE on ITEM_ID " + smart_str(item_id_) + " PRICE " + smart_str(price_) +\
                             " SALE PRICE " + smart_str(sale_price_))


        meta_img_url = hxs.select('//meta[@property="og:image"]/@content')
        if len(meta_img_url) > 0:
            prod_img_url = meta_img_url.extract()[0]
        else:
            prod_img_url = ""
        logging.critical("Image URL: " + smart_str(prod_img_url))


        # find description and keywords: these will be useful in categorization
        desc = hxs.select('//meta[@property="og:description"]/@content')
        if len(desc) > 0:
            desc_content = desc.extract()[0]
        else:
            desc_content = ''
        logging.critical("Description: " + str(desc_content.encode('utf-8')))
        prod_desc = desc_content

        promo_str = ''

        product, created_new = self._create_product_item(item_name, item_id_, str(prod_url), price_, \
                                            sale_price_, gender, prod_img_url, promo_str, prod_desc)


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




    def _create_product_item(self, name, prod_id, prod_url, price, saleprice, gender, img_url, promo_text, prod_desc):
        from django.core.exceptions import ObjectDoesNotExist

        b = Brands.objects.get(name = self.store_name)

        existing_item = ProductModel.objects.filter(brand = b).filter(c_idx = prod_id)
        print existing_item
        if len(existing_item) > 0:
            print "Item " + smart_str(existing_item[0]) + " EXISTS. Not creating new one. Returning...."
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


    def _find_price(self, hxs):
        price = 0
        sale_price = 0
        item_id = -1



        item_id_path = hxs.select('//input[@id="prodId"]/@value')
        if len(item_id_path) > 0:
            tmp = item_id_path.extract()
            item_id = tmp[0]

        price_path = hxs.select('//div[@id="priceSelected"]/text()')

        if len(price_path) > 0:
            tmp = price_path.extract()[0]
            if '$' in tmp:
                price = tmp.strip('$')

        return (item_id, price, sale_price)




