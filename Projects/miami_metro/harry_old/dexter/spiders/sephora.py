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
import os, errno
from time import sleep
import copy
import urllib
import urlparse
import sys
import codecs


def save_item(store_name, item_name, item_url, item_id, item_price, item_image_url):
    print "SAVING: %s %s %s %s %.2f %s" % (store_name, item_name, item_url, item_id, item_price, item_image_url)
    from debra.models import Brands, ProductModel
    b = Brands.objects.get(name=store_name)
    existing_item = ProductModel.objects.filter(brand = b, c_idx = item_id)
    print existing_item
    if len(existing_item) > 0:
        print "Item " + str(existing_item[0]) + " EXISTS. Not creating new one. Returning...."
        return (existing_item[0], False)
    tod = datetime.date.today()
    logging.critical("CREATE_PRODUCT OBJ: foreign key " + str(b))
    item = ProductModel.objects.create(brand = b, 
                                        c_idx = item_id,
                                        name = item_name,
                                        prod_url = item_url,
                                        price = item_price,
                                        saleprice = item_price,
                                        promo_text = '',
                                        gender = '',
                                        img_url = item_image_url,
                                        description = '',
                                        insert_date = tod,)

    
    return (item, True)


class sephora(BaseSpider):
    name = "sephora"
    allowed_domains = ["sephora.com"]
    start_urls = []
    already_added_urls = []
    count = 0
    base_url = "http://www.sephora.com"
    count_scraped = 0
    newArrivals = False
    
    def __init__(self, *a, **kw):
            super(sephora, self).__init__(*a, **kw)
            self.start_urls.append("http://www.sephora.com")
            #self.start_urls.append("http://www.sephora.com/le-male-bath-body-collection-P371801?skuId=3517")
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count += 1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls = []
               
        if (len(hxs.select('.//body[@id="home"]')) > 0) or (len(hxs.select('.//body[@id="search"]')) > 0):
            self.add_links(response, new_urls)
       
        elif len(hxs.select('.//body[@id="product"]')) > 0:
            self.get_product_details(response);
        
        for url_to_follow in new_urls:            
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self, response, urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if len(hxs.select('.//body[@id="home"]')) > 0:
           
            if self.newArrivals:
                navs_path = hxs.select('.//ul[@id="cssdropdown"]//li//a[contains(text(),"new arrivals")]/@href').extract()          
            else:
                navs_path = hxs.select('.//ul[@id="navigation"]//a/@href').extract() 
                # print navs_path
        elif len(hxs.select('.//body[@id="search"]')) > 0 or len(hxs.select('.//div[contains(@class,"category")]')) > 0:
            print "under category"
            #navs_path = hxs.select('.//*[@id="search"]//div[contains(@class,"sidenav")]/ul/li/a')
            #print navs_path
            self.scrape_using_selenium(response, urls)
            
            
        for path in navs_path:
            url_to_follow = ""
            if "http://" not in path:
                url_to_follow = self.base_url + path
            else:
                url_to_follow = path
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)
                           
    
    def scrape_using_selenium(self, response, new_urls):
           
        '''
            We will use selenium
        '''
        #print "under selenium"
        
        from selenium import webdriver
        from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
        from selenium.webdriver.support.ui import WebDriverWait
        
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
        pagination = True
        print "under scraping"
        driver.get(response.url)
        #WebDriverWait(driver, 5, poll_frequency=0.05).until(lambda d : driver.find_element_by_xpath('.//div[contains(@class,"product-grid")]').is_displayed()) #sleep(2)
        #print "out of while"
        while(pagination):
            
            try:
                #print "info23".//div[contains(@class,"category")]//div[contains(@class,"search-navigation")]//ul/li/a
                if len(driver.find_elements_by_xpath('.//div[contains(@class,"category")]')) > 0:
                    navs_path = driver.find_elements_by_xpath('.//div[contains(@class,"category")]//div[contains(@class,"search-navigation")]//ul/li/a')
                else:
                    WebDriverWait(driver, 5, poll_frequency=0.05).until(lambda d : driver.find_element_by_xpath('.//div[contains(@class,"product-grid")]').is_displayed())
                    navs_path = driver.find_elements_by_xpath('.//div[@class="product-item"]/a[@class="product-image"]')
                    print len(navs_path)
                #print len(navs_path)
                for path in navs_path:
                    url_to_follow = ""
                    if "http://" not in path.get_attribute("href"):
                        url_to_follow = self.base_url + path.get_attribute("href")
                    else:
                        url_to_follow = path.get_attribute("href")
                    if not (url_to_follow in self.already_added_urls):
                        new_urls.append(url_to_follow) 
                         
            except:
                pass
            finally:
                if len(driver.find_elements_by_xpath('.//div[contains(@class,"top container")]/div[@class="page-numbers"]/ul/li[@class="next"]')) > 0:
                    nextbtns = driver.find_elements_by_xpath('.//div[contains(@class,"top container")]/div[@class="page-numbers"]/ul/li[@class="next"]/a')
                    nxtbtnfound = False
                    for btn in nextbtns:
                        btn.click()
                        WebDriverWait(driver, 5, poll_frequency=0.05).until(lambda d : driver.find_element_by_xpath('.//div[contains(@class,"product-grid")]').is_displayed()) #sleep(2)
                        #WebDriverWait(self.selenium, 10).until(lambda s: len(s.find_elements(By.CSS_SELECTOR, 'list-item')) == 0)
                        #WebDriverWait(self.driver, 5, poll_frequency=0.05).until(lambda d : not self.driver.find_element_by_xpath('.//*[@id="searchShield"]').is_displayed())
                        sleep(5)
                        #print "wait end"
                        pagination = True
                        
                else:
                    pagination = False

        driver.close()
        display.stop()

    def get_product_details(self, response):
        hxs = HtmlXPathSelector(response)
        print "under product details"
        if len(hxs.select('.//div[@id="primarySkuInfoArea"]'))>0:
            item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
            item_name = item_name.encode("utf-8")
            #print item_name+"\n"
            item_id = hxs.select('.//*[@id="addToMyListSkuId"]/@value')[0].extract()
            #print item_id+"\n"
            item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
            #item_url = urllib.unquote(hxs.select('//meta[@property="og:url"]/@content')[0].extract())
            
            #print item_img_url+"\n"
            if len(hxs.select('.//div[@id="primarySkuInfoArea"]//span[contains(@class,"sku-price sale")]//span[@class="sale-price"]').extract()) > 0:
                item_price = hxs.select('.//div[@id="primarySkuInfoArea"]//span[contains(@class,"sku-price sale")]//span[@class="sale-price"]/span[@class="price"]/text()')[0].extract()
            else:
                item_price = hxs.select('.//div[@id="primarySkuInfoArea"]//span[@class="list-price"]/span[@class="price"]/text()')[0].extract()
    
           
            prod_url = ""
            meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
            if len(meta_tag_url) > 0:
                prod_url = urllib.unquote(meta_tag_url.extract()[0])
            else:
                prod_url = response.url
            self.count_scraped += 1
            content = "\n"+str(self.count_scraped) + ". PRODUCT URL:" + prod_url + "\n\t TITLE: " + item_name.decode("utf-8","ignore") + "\n\t ITEM ID: " + str(item_id) + "\n\t ITEM PRICE:" + str(item_price) + "\n\t IMAGE URL:" + item_img_url + "\n\t TOTAL SO FAR: " + str(self.count_scraped)
            logging.critical(content)
            self.writelog(content, prod_url, item_name, item_id, item_price, item_img_url)
                    
    def writelog(self, content, url, name, prod_id, price_str, image):
        
        price_str2 = price_str.replace(',', '')
        exp = '[\d\.]+'
        res = re.findall(exp, price_str2)
        price = 0
        if len(res) > 0:
            price = float(res[0])
        save_item("Sephora", name, url, prod_id, price, image) 
  
    def price_string_to_float(self, price):

        '''

            Converts input like $129.00 to 129.00

            Or $1,299.00 to 1299.00

            Or ($20.00) to 20.00

        '''

        valueArr = price.split("-")
        if len(valueArr) > 1:
            return 0
        else:
            if float(re.sub(r'[^\d.]+', '', valueArr[0])):
                return float(re.sub(r'[^\d.]+', '', valueArr[0]))
            else:
                return 0
