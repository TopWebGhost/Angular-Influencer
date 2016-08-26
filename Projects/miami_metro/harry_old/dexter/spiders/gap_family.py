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
from masuka import pricing_aggregate_stats
import urlparse

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)

class GapFamilySpider(CrawlSpider):
    name = "gapfamily"

    #store_name = "Banana Republic"
    #store_name = "Gap"
    #store_name = "Old Navy"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    #base_url = 'http://bananarepublic.gap.com'
    #base_url = 'http://www.gap.com'
    base_url = 'http://oldnavy.gap.com'

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
    allowed_domains = ['bananarepublic.com', 'bananarepublic.gap.com', 'gap.com',
                       'oldnavy.com', 'oldnavy.gap.com', 'athleta.com', 'athleta.gap.com',
                       'piperlime.com', 'piperlime.gap.com',]

    new_arrivals = 0
    canonicalize_idx = False

    def __init__(self, *a, **kw):
        super(GapFamilySpider, self).__init__(*a, **kw)
        # start with the home page
        #self.start_urls.append("http://www.bananarepublic.gap.com/")
        #self.start_urls.append(self.base_url)
        #print "Hello"
        print "Kwargs: %s " % kw
        self.store_name = kw.get('store_name')
        self.base_url = kw.get('start_url')
        if self.canonicalize_idx:
            # bug fixing starts
            all_products = pricing_aggregate_stats.get_active_products(self.store_name)
            for prod in all_products:
                self.start_urls.append(prod.prod_url)
            return
        # bug fixing stops
        self.start_urls.append(self.base_url)
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))
        print self.new_arrivals


    def canonicalize_c_idx(self, response):
        #there is a discrepency in which we are getting prod_id in the shelfit code
        #and the prod_id we get in the crawler here


        #so we are going to cleanse our DB
        #
        #1. fetch all products we have in the DB
        #2. get it's new c_idx
        #3. check if we have a duplicate for that c_idx
        #4. if yes: (we can only have one of these two, so we need to throw out one)
        #           (but before that, we need to correct all WishlistItem and CSMs)
        hxs = HtmlXPathSelector(response)
        canonical_url_path = hxs.select('//link[@rel="canonical"]/@href').extract()
        canonical_url = ''
        if len(canonical_url_path) > 0:
            canonical_url = canonical_url_path[0]

        if canonical_url == '':
            print "There is a problem, we should have found canonical URL here for this URL %s " % response.url

            return

        parsed = urlparse.urlparse(canonical_url)

        item_id_canonical = re.match('/products/P(\d+)\.jsp', parsed.path).group(1)

        parsed = urlparse.urlparse(response.url)
        params = urlparse.parse_qs(parsed.query)
        if 'pid' in params:
            item_id=params['pid'][0]
            prod = ProductModel.objects.filter(c_idx = item_id)
            if item_id_canonical != '':
                for p in prod:
                    print "Updating c_idx from %s to %s for prod %s " % (p.c_idx, item_id_canonical, p.prod_url)
                    p.c_idx = item_id_canonical
                    p.save()




    def parse(self, response):
        if self.canonicalize_idx:
            #bug fixing starts
            url = response.url
            print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
            self.canonicalize_c_idx(response)
            self.count += 1
            return


        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #bug fixing stops
        #print str(response.body)
        selenium_urls = []
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister

        print "NAVIGATION URL " + str(url)
        self.add_primary_nav_links(response, new_urls)

        # these contain category pages. they have links to other category pages and links to product pages
        if 'division.do' in url or 'subDivision.do' in url:
            self.add_category_links(response, selenium_urls)
            try:
                self.scrape_using_selenium(selenium_urls, new_urls)
            except:
                print "Scrapy crashed while visiting URL: %s" % (url)
                pass

        # these are product pages
        if 'browse/product.do' in url:
            valid_prod, product = self.parse_gapfamily(response)

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
        if 'piperlime' in self.base_url:
            primary_navs_path = hxs.select('//div[contains (@id, "TopNavLayout")]/div/ul/li/a/@href').extract()
        elif 'athleta' in self.base_url:
            primary_navs_path = hxs.select('//div[contains (@id, "topNav_")]/div/div/ul/li/a/@href').extract()
        else:
            primary_navs_path = hxs.select('//div[contains (@class,"topNavBottomRow")]/div/ul/li/a/@href').extract()

        for p in primary_navs_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "PRIMARY NAV URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        if 'piperlime' in self.base_url:
            if self.new_arrivals == 0:
                cat_navs_path = hxs.select('//ul[@id="sideNavCategoryHeaders"]/li/ul/li/a/@href').extract()
            else:
                cat_navs_path = hxs.select('//ul[@id="sideNavCategoryHeaders"]/li/ul/li/a[contains (text(), "rrivals")]/@href').extract()
        else:
            if self.new_arrivals == 0:
                cat_navs_path = hxs.select('//div[@id="sideNavCategories"]/ul/li/a/@href').extract()
            else:
                #Gap: New Arrivals, BR: new arrivals, Athleta: New arrivals ===> common: "rrivals"
                cat_navs_path = hxs.select('//div[@id="sideNavCategories"]/ul/li/a[contains (text(), "rrivals")]/@href').extract()


        for p in cat_navs_path:
            url_to_follow = self.base_url + p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)


    def scrape_using_selenium(self, category_urls, new_urls):

        '''
            We will use selenium
        '''
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
        for url in category_urls:
            print "Trying: " + url
            try:
                driver.get(url)
                count_of_items = driver.find_elements_by_xpath('//div[@id="totalItemCountDiv"]/text()')
                print 'count_of_items ' % count_of_items

                prod_elems = driver.find_elements_by_xpath('//div[contains (@id, "categoryProductItem")]/a')
                if len(prod_elems) > 0:
                    for e in prod_elems:
                        prod_url = e.get_attribute('href')
                        print "Checking Product_URL: " + prod_url

                        if not (prod_url in self.already_added_urls):
                            print "Adding Product URL: " + str(prod_url)
                            new_urls.append(prod_url)

            except:
                pass

                driver.quit()
                display.stop()
                display = Display(visible=0, size=(800, 600))
                display.start()
                driver = webdriver.Firefox(profile)

        driver.quit()
        display.stop()

    def parse_gapfamily(self, response):
        #self.check_shelfit_validity(response)
        #return (False, None)
        hxs = HtmlXPathSelector(response)

        # find name of item
        item_name_path = hxs.select('//title/text()')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            print "Invalid link:  " + str(response.url)
            return (False, None)
        item_name = item_name_path.extract()[0]
        if '|' in item_name:
            index = item_name.find('|')
            item_name = item_name[0:index]
        logging.critical("Name: " + item_name.encode('utf-8'))

        self.count_scraped += 1



        prod_url = response.url
        logging.critical("PRODUCT URL:" + str(prod_url) + " ITEM_NAME " + item_name.encode('utf-8') + " TOTAL SO FAR " + str(self.count_scraped))

        gender = 'F'
        if "www.bananarepublic.com" in prod_url or 'www.gap.com' in prod_url:
            gender_path = hxs.select('//a/img[contains (@class, "_selected")]/@alt')
            if len(gender_path) > 0:
                gender__ = gender_path.extract()[0]
                if 'men' in gender__ or 'boy' in gender__:
                    gender = 'M'

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
        prod_img_path = hxs.select('//img[@id="productImage"]/@src')
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



    #def avoid_redirection(self, request):
    #    request.meta.update(dont_redirect=True)
    #    #request.meta.update(dont_filter=True)
    #    return request


    def _create_product_item(self, name, prod_id, prod_url, price, saleprice, gender, img_url, promo_text, prod_desc):
        from django.core.exceptions import ObjectDoesNotExist
        store_name = "-1"
        if 'bananarepublic' in prod_url:
            store_name = "Banana Republic"
        elif 'oldnavy' in prod_url:
            store_name = 'Old Navy'
        elif 'athleta' in prod_url:
            store_name = 'Athleta'
        elif 'piperlime' in prod_url:
            store_name = "Piperlime"
        elif 'www.gap.com' in prod_url:
            store_name = "Gap"
        else:
            return (None, False)

        b = Brands.objects.get(name = store_name)

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

        canonical_url_path = hxs.select('//link[@rel="canonical"]/@href').extract()
        canonical_url = ''
        if len(canonical_url_path) > 0:
            canonical_url = canonical_url_path[0]
        parsed = urlparse.urlparse(canonical_url)
        params = urlparse.parse_qs(parsed.query)
        #if 'pid' in params:
        #    item_id=params['pid'][0]
        #elif '.jsp' in parsed.path:
        item_id = re.match('/products/P(\d+)\.jsp', parsed.path).group(1)

#        pid = url.rfind('&pid=')
#        scid = url.rfind('&scid=')
#        # /P492952.jsp => 492952
#        item_id = url[pid+5: scid]
        print "ITEM_ID " + str(item_id)

        price_path = hxs.select('//span[@id="priceText"]/text()')

        if len(price_path) > 0:
            price_temp = price_path.extract()[0]
            price = float(price_temp.replace('$', ''))

        else:
            print "PRICE NOT FOUND"
            price = -1

        # Don't care about sale price since we're going to do that calculation soon
        return (item_id, price, price)

