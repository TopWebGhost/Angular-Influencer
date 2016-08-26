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

class aeropostale(BaseSpider):
    name = "aeropostale"
    allowed_domains = ["aeropostale.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.aeropostale.com"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(aeropostale, self).__init__(*a, **kw)
            self.start_urls.append("http://www.aeropostale.com")
            #self.start_urls.append("http://www.aeropostale.com/category/index.jsp?categoryId=3534626")      
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body))) #printed urls with count
        new_urls=[]
        
        # if condition for categories the url links and product details page
        if (len(hxs.select('.//*[@id="shopPage"]')) > 0) or (len(hxs.select('.//*[@id="categoryPage"]')) > 0) or (len(hxs.select('.//*[@id="familyPage"]')) > 0):
            self.add_links(response, new_urls)
            #redirect to add_links def for append urls
        elif len(hxs.select('//*[@id="productPage"]')) > 0:
            self.get_product_details(response)
            #redirect to product_detail def for get product details
            
        #for loop to append all urls from new_urls
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
    
    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if len(hxs.select('.//*[@id="shopPage"]')) > 0:
            navs_path = hxs.select('.//*[@id="nav-categories"]//ul/li/a/@href').extract()
        elif len(hxs.select('.//body[@id="categoryPage"]')) > 0:
            if self.newArrivals:
                navs_path = hxs.select('.//div[@id="sidebar-left"]//a[contains(text(), "New Arrivals")]/@href').extract() #a[contains(text(), "New Arrivals")]/@href                
            else:
                navs_path = hxs.select('.//div[@id="sidebar-left"]//a/@href').extract()
            
        elif len(hxs.select('.//*[@id="familyPage"]')) > 0:
            if len(hxs.select('.//li[@class="viewAll"]/a')) > 0:
                self.scrape_using_selenium(response, urls)
            else:
                navs_path = hxs.select('.//div[@id="products"]//div[@class="details"]/a/@href').extract()
        # getting paths from homepage menus and listing pages/left navigations and concatinating with base url
        #print len(navs_path)
        #exit()
        for path in navs_path:
            url_to_follow = ""
            if "http://" not in path:
                url_to_follow = self.base_url + path
            else:
                url_to_follow = path
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)
    #getting all products url from the listing page if having more then 1 pages on listing page 
    def handlePagination(self,response,urls):
        pagination_url = ""
        pagination1 = []
        hxs = HtmlXPathSelector(response)
        pagination1 = hxs.select('.//div[@id="wrapper_page_content"]/div[@id="top_pagination_list"]//li[@class="show_next"]/a/@href').extract()
        if len(pagination1)>0:
            pagination_url = pagination1[0]
        if len(pagination1) > 0:
            url_to_follow = ""
            if "http://" not in pagination_url:
                url_to_follow = self.base_url + pagination_url
            else:
                url_to_follow = pagination_url
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow) 
    
    def scrape_using_selenium(self, response, new_urls):
        
        '''
            We will use selenium
        '''
        
        from selenium import webdriver
        from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
        from selenium.webdriver.support.ui import WebDriverWait
        
        profile = FirefoxProfile()
        profile.set_preference("dom.max_script_run_time",600)
        profile.set_preference("dom.max_chrome_script_run_time",600)
        #profile.set_preference('permissions.default.image', 2) # disable images
        profile.set_preference('plugin.scan.plid.all', False) # disable plugin loading crap
        profile.set_preference('dom.disable_open_during_load',True) # disable popups
        profile.set_preference('browser.popups.showPopupBlocker',False)
        
        from pyvirtualdisplay import Display
        
        display = Display(visible=0, size=(800, 600))
        display.start()
        driver = webdriver.Firefox(profile)
        pagination = True
        driver.get(response.url)
        driver.find_element_by_xpath('.//li[@class="viewAll"]/a').click()
        WebDriverWait(driver, 3).until(lambda s: driver.find_element_by_xpath('.//div[@id="products"]//div[@class="details"]/a').is_displayed())
        navs_path = driver.find_elements_by_xpath('.//div[@id="products"]//div[@class="details"]/a')
        
        for path in navs_path:
            url_to_follow = ""
            if "http://" not in path.get_attribute("href"):
                url_to_follow = self.base_url + path.get_attribute("href")
            else:
                url_to_follow = path.get_attribute("href")
            if not (url_to_follow in self.already_added_urls):
                new_urls.append(url_to_follow)
        driver.close()
        display.stop()
    
    # converting price as string to float eg. INR-200.00 TO 200.00
    def price_string_to_float(self, price):
        valueArr = price.split("-")
        if len(valueArr) > 1:
            return 0
        else:
            if float(re.sub(r'[^\d.]+', '', valueArr[0])):
                return float(re.sub(r'[^\d.]+', '', valueArr[0]))
            else:
                return 0    
    #getting product detiails to write log in a file
    def get_product_details(self,response):
        hxs = HtmlXPathSelector(response)
        item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
        item_name = item_name.encode("utf-8") # encoding the item name avoid to get decode error
        
        item_ids = hxs.select('//meta[@property="og:url"]/@content')[0].extract().split("=")
        
        item_id = item_ids[1].strip() 
        
        item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
        
        if len(hxs.select('.//*[@class="price"]/li[@class="now"]')) > 0:
            item_price = self.price_string_to_float(hxs.select('.//*[@class="price"]/li[@class="now"]/text()')[0].extract())
        else:
            item_price = self.price_string_to_float(hxs.select('.//*[@class="price"]/li/text()')[0].extract())
        self.count_scraped += 1
        content = "\nPRODUCT URL:" + str(response.url) + "\n\t TITLE: " + item_name.decode("utf-8","ignore") +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+str(item_price) +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
        logging.critical(content)
        self.writelog(content)
    
    # writing log result in a file
    def writelog(self,content):
        if not self.newArrivals:
            with codecs.open("../../../Results/Scrapy/aeropostale_scrapy_Result", "a","utf-8") as myfile:
               myfile.write(''.join(content))
        else:
            with codecs.open("../../../Results/Scrapy/aeropostale_scrapy_New_Arrivals_Result", "a","utf-8") as myfile:
                myfile.write(''.join(content))
  