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

class ExpressSpider(CrawlSpider):
    name = "express"

    store_name = "Express"
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
    allowed_domains = ['express.com',]

    new_arrivals = 0
    base_url = 'http://www.express.com'

    fixing_original_prices = False

    def __init__(self, *a, **kw):
        super(ExpressSpider, self).__init__(*a, **kw)
        # start with the home page
        if self.fixing_original_prices:
            prods = ProductModel.objects.filter(brand__name = "Express")
            for p in prods:
                self.start_urls.append(p.prod_url)

        else:
            self.start_urls.append("http://www.express.com/")
            if kw.get('new_arrivals'):
                self.new_arrivals = int(kw.get('new_arrivals'))
            print self.new_arrivals
        #self.start_urls.append('http://www.express.com/view-all-pants-704/control/show/80/index.cat')
        #self.start_urls.append('http://www.express.com/accessories-34/index.cat')

    def update_price(self, response):
        url = response.url
        prods = ProductModel.objects.filter(brand__name = "Express", prod_url = url)
        if len(prods) == 0:
            print "PROBLEM:: shouldn't happen. no prod found for %s " % url
            return
        if len(prods) > 1:
            print "PROBLEM: more than 1 entries found for url %s " % url

        hxs = HtmlXPathSelector(response)


        orig_path = hxs.select('//span[@class="cat-glo-tex-oldP"]/text()').extract()
        if len(orig_path) > 0:
            price_str = orig_path[0]
        else:
            price_path = hxs.select('//li[@class="cat-pro-price"]/strong/text()').extract()
            price_str = price_path[0]
        exp = '[\d\.]+'
        res = re.findall(exp, price_str)
        price = 0
        if len(res) > 0:
            price = float(res[0])

        for prod in prods:
            print "Found price %s for prod %s. Stored price %s " % (price, prod, prod.price)
            if price > 0 and price != prod.price:
                prod.price = price
                prod.save()
                print "Updating price for prod %s " % prod

    def parse(self, response):
        self.count += 1

        if self.fixing_original_prices:
            self.update_price(response)
            return

        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister
        if 'home.jsp' in url:
            print "USEFUL URL " + str(url)
            self.add_primary_nav_links(response, new_urls)

        # these contain category pages. they have links to other category pages and links to product pages
        if 'index.cat' in url or 'index.sec' in url or 'index.ens' in url:
            #if response.request.meta.get('redirect_urls'):
            #    print "Redirected from " + str(response.request.meta.get('redirect_urls')[0])
            self.add_category_links(response, new_urls)
            self.add_product_links(response, new_urls)
            #print "\n---SCRAPING PAGE---\n"

        # these are product pages
        if 'index.pro' in url:
            valid_prod, product = self.parse_express(response)



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
        primary_navs_path = hxs.select('//div[@class="header-top"]/span/a/@href').extract()
        base_link = "http://www.express.com"

        for p in primary_navs_path:
            url_to_follow = base_link + p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(base_link + p)
                new_urls.append(base_link + p)

    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        if self.new_arrivals == 0:
            category_nav_path = hxs.select('//div[@id="glo-leftnav-container"]/span/a/@href').extract()
        else:
            category_nav_path = hxs.select('//div[@id="glo-leftnav-container"]/span/a[contains (text(), "New Arrivals")]/@href').extract()
        for p in category_nav_path:
            url_to_follow = p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

        if self.new_arrivals == 0:
            category_nav_path = hxs.select('//div[@id="glo-leftnav-container"]/ul/li/a/@href').extract()
        else:
            category_nav_path = hxs.select('//div[@id="glo-leftnav-container"]/ul/li/a[contains (text(), "New Arrivals")]/@href').extract()
        for p in category_nav_path:
            url_to_follow = p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

        next = hxs.select('//a[@class="cat-glo-page-action"]/@href').extract()
        for p in next:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def get_id_from_url(self, url):

        import re

        pattern = '-[\d]+-'
        pattern_comp = re.compile(pattern)
        results = pattern_comp.findall(url)
        vals = []

        if len(results) > 0:
            for res in results:
                vals.append(res.strip('-'))

        return vals

    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        base_link = "http://www.express.com"

        product_path_1 = hxs.select('//div[@class="cat-cat-pro-row"]/div/div/a/@href').extract()

        product_path_2 = hxs.select('//div[contains (@class, "cat-thu-row")]/div/div/a/@href').extract()

        product_path_3 = hxs.select('//div[@id="cat-ens-prod-item"]/a/@href').extract()

        product_path_4 = hxs.select('//div[contains (@class, "cat-thu-product")]/div/a/@href').extract()

        # search for view-all links on the category pages
        product_path_5 = hxs.select('//td[contains (@class, "cat-thu-but-view-all")]/a/@href').extract()

        product_path = product_path_1 + product_path_2 + product_path_3 + product_path_4 + product_path_5

        for p in product_path:
            url_to_follow = base_link + p
            print "Product URL: Checking: " + str(url_to_follow)
            if not (url_to_follow in self.already_added_urls):
                print "Product URL: Not yet visited: " + str(url_to_follow),
                prod_ids = self.get_id_from_url(url_to_follow)
                print "Length of result: " + str(len(prod_ids)) + " ProdID: " + str(prod_ids)
                #assert len(prod_ids) < 2
                if len(prod_ids) == 1:
                    pid = prod_ids[0]
                    prod = ProductModel.objects.filter(brand__name = self.store_name, c_idx = pid)
                    if len(prod) > 0:
                        print "EXISTS. We found " + str(len(prod)) + " first: " + str(prod[0])
                    else:
                        print "IS A NEW ITEM. ID " + str(pid)
                        new_urls.append(url_to_follow)

                else:
                    new_urls.append(url_to_follow)


    def parse_express(self, response):
        #self.check_shelfit_validity(response)
        #return
        hxs = HtmlXPathSelector(response)

        # find name of item
        item_name_path = hxs.select('//div[@id="cat-pro-con-detail"]//h1/text()')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            return (False, None)
        item_name = item_name_path.extract()
        logging.critical("Name: " + str(item_name))

        self.count_scraped += 1



        prod_url = response.url
        logging.critical("PRODUCT URL:" + str(prod_url) + " TITLE " + str(item_name) + " TOTAL SO FAR " + str(self.count_scraped))

        # find gender
        gender = 'M'
        if prod_url.lower().find('women') >= 0 or prod_url.lower().find('girl') >= 0:
            gender = 'F'
        logging.critical("Gender: " + gender)

        '''
        TODO: if same page has multiple items, our logic will not work.
        So, leaving it for future.
        '''
        if len(item_name) == 0:
            logging.critical("DIDN'T FIND TITLE AT NORMAL PLACE, MUST BE SUIT. RETURNING." + str(prod_url))
            print item_name_path
            print "Size of response " + str(len(str(response)))
            print str(response)
            return (False, None)

        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs, prod_url)

        if item_id_ in self.all_items_scraped:
            print "RETURNING since we have already scraped " + str(item_id_)

        self.all_items_scraped.add(item_id_)

        logging.critical("ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))

        # extract image URL
        prod_img_path = hxs.select('//link[@rel="image_src"]')
        prod_img_str = str(prod_img_path.extract()[0])
        prod_img_url = prod_img_str[28: len(prod_img_str) - 2]
        logging.critical("Image URL: " + str(prod_img_url))


        # find description and keywords: these will be useful in categorization
        desc = hxs.select('//div[@id="cat-pro-con-detail"]//li[@class="cat-pro-desc"]/text()').extract()
        logging.critical("Description: ")
        logging.critical(desc)
        prod_desc = desc

        # promo text
        promo_path = hxs.select('//span[@class="cat-pro-promo-text"]//font/text()').extract()
        promo_str = str(promo_path)
        logging.critical("Promotion: ")
        logging.critical(promo_str)




        product, created_new = self._create_product_item(item_name[0], int(item_id_), str(prod_url), price_, \
                                            sale_price_, gender, str(prod_img_url), promo_str, prod_desc)


        if (not created_new):
            return (False, product)

        if created_new:
            new_cat = simple_product_categorization(product)
            product.cat1 = new_cat["cat1"]
            product.cat2 = new_cat["cat2"]
            product.cat3 = new_cat["cat3"]
            product.save()
        #self._create_category(product, categories)


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
        print "CALCULATING PRICE: " + str(url)
        #item_id = self.find_itemid_in_url(url)

        item_id_path = hxs.select('//input[@name="productId"]/@value').extract()
        if len(item_id_path) > 0:
            item_id = item_id_path[0]
            print "ITEM_ID " + str(item_id)
        else:
            print "ERROR: couldn't find productId input element"
            return

        orig_path = hxs.select('//span[@class="cat-glo-tex-oldP"]/text()').extract()
        if len(orig_path) > 0:
            price_str = orig_path[0]
        else:
            price_path = hxs.select('//li[@class="cat-pro-price"]/strong/text()').extract()
            price_str = price_path[0]
        exp = '[\d\.]+'
        res = re.findall(exp, price_str)
        price = 0
        if len(res) > 0:
            price = float(res[0])
        sale_price = price

        return (item_id, price, sale_price)




