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

class AnthroFamilySpider(CrawlSpider):
    name = "anthro"

    #store_name = "Banana Republic"
    store_name = "Anthropologie"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    base_url = 'http://www.anthropologie.com'
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
    allowed_domains = ['anthropologie.com',]

    new_arrivals = 0

    def __init__(self, *a, **kw):
        super(AnthroFamilySpider, self).__init__(*a, **kw)
        # start with the home page
        self.start_urls.append(self.base_url)
        print "Kwargs: %s " % kw
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))
        print self.new_arrivals

    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister

        print "NAVIGATION URL " + str(url)
        if 'index.jsp' in url:
            self.add_primary_nav_links(response, new_urls)
            self.add_category_links(response, new_urls)
        # these contain category pages. they have links to other category pages and links to product pages
        if 'category' in url:

            self.add_product_links(response, new_urls)

        # these are product pages
        if 'product' in url:
            valid_prod, product = self.parse_anthrofamily(response)

        self.count += 1

        sleep(1)
        print "Total pages scraped " + str(self.count_scraped) + " Total URLS " + str(self.count) + \
              " Total invalid links " + str(self.invalid_links)

        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                if self.new_arrivals == 0 or 'shopnew' in url_to_follow.lower():
                    #only if product doesn't already exist
                    prod = ProductModel.objects.filter(prod_url = url_to_follow)
                    if len(prod) == 0:
                        self.already_added_urls.append(url_to_follow)
                        yield Request(url_to_follow, callback=self.parse)



    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)
        from selenium import webdriver
        from selenium.webdriver.firefox.firefox_profile import FirefoxProfile

        profile = FirefoxProfile()
        profile.set_preference("dom.max_script_run_time",600)
        profile.set_preference("dom.max_chrome_script_run_time",600)
        profile.set_preference('permissions.default.image', 2) # disable images
        profile.set_preference('plugin.scan.plid.all', False) # disable plugin loading crap
        profile.set_preference('dom.disable_open_during_load',True) # disable popups
        profile.set_preference('browser.popups.showPopupBlocker',False)

    #   firefoxProfile.addExtension("firebug-1.8.1.xpi")
    #   firefoxProfile.setPreference("extensions.firebug.currentVersion", "1.8.1")
        from pyvirtualdisplay import Display

        display = Display(visible=0, size=(800, 600))
        display.start()
        driver = webdriver.Firefox(profile)

        try:
            driver.get(self.base_url)
            category_links = driver.find_elements_by_xpath('//div[@class="flyout_category_column"]/a')
            if len(category_links) > 0:
                for e in category_links:
                    cat_url = e.get_attribute('href')
                    print "Checking Category_URL: " + cat_url

                    if not (cat_url in self.already_added_urls):
                        print "Adding Category URL: " + str(cat_url)
                        new_urls.append(cat_url)
        except:
            pass
            driver.quit()
            display.stop()
            display = Display(visible=0, size=(800, 600))
            display.start()
            driver = webdriver.Firefox(profile)
        driver.quit()
        display.stop()




    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        cat_navs_path = hxs.select('//div[@class="category-item"]/div/a/@href').extract()

        for p in cat_navs_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "PRODUCT URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

        next_link = hxs.select('//a[@class="rightarrow arrow next"]/@href').extract()
        for p in next_link:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "NEXT PAGE URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)



    def add_primary_nav_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        primary_navs_path = hxs.select('//div[@id="main-nav"]/ul/li/a/@href').extract()

        for p in primary_navs_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "PRIMARY NAV URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def parse_anthrofamily(self, response):
        #self.check_shelfit_validity(response)
        #return (False, None)
        hxs = HtmlXPathSelector(response)

        # find name of item
        item_name_path = hxs.select('//meta[@property="og:title"]/@content')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            print "Invalid link:  " + str(response.url)
            return (False, None)
        item_name = item_name_path.extract()[0]
        logging.critical("Name: " + item_name.encode('utf-8'))

        self.count_scraped += 1
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
        prod_img_path = hxs.select('//meta[@property="og:image"]/@content')
        if len(prod_img_path) > 0:
            prod_img_url = str(prod_img_path.extract()[0])
            logging.critical("Image URL: " + str(prod_img_url))
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
        item_id_path = hxs.select('//input[@name="product"]/@value').extract()
        if len(item_id_path) > 0:
            item_id = item_id_path[0]
        else:
            #http://www.anthropologie.com/anthro/product/shopsale-freshcuts/24084030.jsp
            end_index = url.find('.jsp')
            #url_t => http://www.anthropologie.com/anthro/product/shopsale-freshcuts/24084030
            url_t = url[:end_index]
            # start = last /
            start = url_t.rfind('/')
            item_id = url_t[start+1:]


        print "ITEM_ID " + str(item_id)


        price = -1
        old_price_path = hxs.select('//div[contains (@class,"prodprice")]/div[contains (@class,"prodwasprice")]/text()')
        if len(old_price_path) > 0:
            old_price_val = old_price_path.extract()[0]
        else:
            old_price_path = hxs.select('//div[contains (@class,"prodprice")]/text()')
            if len(old_price_path) > 0:
                old_price_val = old_price_path.extract()[0]
        #was $74.00
        pp = '[\d\.]+'
        pp_c = re.compile(pp)
        vals = re.findall(pp_c, old_price_val)
        if len(vals) > 0:
            price = vals[0]

        # Don't care about sale price since we're going to do that calculation soon
        return (item_id, price, price)

