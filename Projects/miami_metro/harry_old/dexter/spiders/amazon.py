# -*- coding: utf-8 -*-
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

class amazon(BaseSpider):
    name = "amazon"
    allowed_domains = ["amazon.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.amazon.com"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(amazon, self).__init__(*a, **kw)
            #self.start_urls.append("http://www.amazon.com")
            self.start_urls.append("http://www.amazon.com/clothing-accessories-men-women-kids/b/ref=sa_menu_apr13?ie=UTF8&node=1036592")
            #self.start_urls.append("http://www.amazon.com/Plus-Size-Petite-Capri-Chocolate/dp/B009CVHYM0/ref=sr_1_75?s=apparel&ie=UTF8&qid=1354768400&sr=1-75")
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        url = response.url
        print "\n\n\n\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls=[]
        
        if (len(hxs.select('.//div[@id="pagn"]/span[@class="pagnRA"]')) > 0 or len(hxs.select('.//div[@id="leftNav"]')) > 0):
            self.add_links(response, new_urls)
        elif len(hxs.select('.//form[@id="handleBuy"]')) > 0:
            self.get_product_details(response)

        elif (len(hxs.select('.//div[@id="content"]/div[@id="centerA"]')) > 0):
            self.scrape_using_selenium(response, new_urls)
        
        '''elif len(hxs.select('.//div[@id="main"]/div[@id="searchTemplate"]//div[@id="center"]')) > 0:
            self.add_links(response, new_urls)'''
        
        
        
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):            
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)


    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []  
        
        #listing page.
        print len(hxs.select('.//div[@id="pagn"]/span[@class="pagnRA"]'))     
        if len(hxs.select('.//*[@id="pagn"]').extract())>0:
                navs_path = hxs.select('.//*[contains(@id,"result_")]//div[@class="image"]/a/@href').extract()
                print len(navs_path)
                print "product listing"
                
                if len(hxs.select('.//div[@id="pagn"]/span[@class="pagnRA"]/a[@id="pagnNextLink"]').extract())>0 or (len(hxs.select('.//*[@id="pagn"]').extract())>0):
                    self.handlePagination(response, urls)

        elif (len(hxs.select('.//div[@id="content"]/div[@id="centerA"]')) > 0):
            print hxs.select('.//div[@id="content"]/div[@id="centerA"]')
            if self.newArrivals:
                navs_path = hxs.select('.//div[@id="hpTopLeft"]//h4[@class="loneHeading"]/a[contains(text(), "New Arrivals")]/@href').extract()                
            else:
                
                navs_path = hxs.select('.//*[@id="nav_subcats"]').extract()
                print navs_path
        #left nav
        elif len(hxs.select('.//div[@id="leftNav"]')) > 0:
            print "left nav"
            navs_path = hxs.select('.//div[@id="leftNav"]//ul/li/a/@href').extract()
            print len(navs_path)
            sleep(2)
        
            
        
        for path in navs_path:
            url_to_follow = ""
            if "http://" not in path:
                url_to_follow = self.base_url + path
            else:
                url_to_follow = path
            if not (url_to_follow in self.already_added_urls):
               urls.append(url_to_follow)

    def handlePagination(self,response,urls):
        hxs = HtmlXPathSelector(response)
        pagination_url = ""
        print "under pagination"
        
        pagination1 = hxs.select('.//div[@id="pagn"]/span[@class="pagnRA"]/a[@id="pagnNextLink"]/@href').extract()
        
        if len(pagination1) > 0:
            pagination_url = pagination1[0]
        else:
            return False

        print pagination_url

        if pagination_url !="" :
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
        if len(driver.find_elements_by_xpath('.//div[@id="content"]/div[@id="centerA"]')) > 0:
            navs_path = driver.find_elements_by_xpath('.//*[@id="nav_subcats"]//ul/li/a')
        print len(navs_path)
        
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

    def get_product_details(self,response):
        reload(sys)
        sys.setdefaultencoding('utf-8')
        hxs = HtmlXPathSelector(response)
                
        item_name = hxs.select('.//span[@id="btAsinTitle"]/text()')[0].extract()
        item_name = item_name.encode("utf-8")
        
        item_id = 0
        '''item = hxs.select('.//div[@id="theater"]/span[@id="sku"]/text()')[0].extract()
        item_id =""
        if len(item.split(" ")) >0:
            item_id = item.split(" ")[1]
            print "item Id :"+item_id.decode("windows-1252")
        else:
            item_id = item
            print "item Id :"+item_id.decode("windows-1252")'''
            
        if len(hxs.select('.//div[@id="prodImageOuter"]/div[@id="prodImageCell"]')) > 0:
            item_img_url = hxs.select('.//div[@id="prodImageOuter"]//img/@src')[0].extract()
        elif len(hxs.select('.//img[@id="main-image"]')) > 0:
            item_img_url = hxs.select('.//img[@id="main-image"]/@src')[0].extract()
        elif len(hxs.select('.//*[@class="productImageGrid"]//div[@id="kib-container"]')) > 0:
            item_img_url = hxs.select('.//*[@class="productImageGrid"]//div[@id="kib-container"]//div[@class="centerslate"]//img/@src')[0].extract()    
        else:
            item_img_url = hxs.select('.//*[@id="prodImage"]/@src')[0].extract()
        
        if len(hxs.select('.//*[@class="listprice"]/text()').extract())>0:
            item_price = hxs.select('.//*[@class="listprice"]/text()')[0].extract()
        elif len(hxs.select('.//*[@class="priceLarge"]/text()').extract()) >0:
            item_price = hxs.select('.//*[@class="priceLarge"]/text()')[0].extract()
        else:
            item_price = "0"
        prod_url = response.url

        self.count_scraped += 1
        content =""
        
        content =("\nPRODUCT URL:" + str(prod_url) + "\n\t TITLE: " + item_name.decode("utf-8","ignore") + "\n\t ITEM PRICE:"+item_price +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped))
        
        logging.critical(content)
        self.writelog(content)
                    
    def writelog(self,content):
        if not self.newArrivals:
            with open("../../../Results/Scrapy/amazon_scrapy_Result", "a") as myfile:
               myfile.write(''.join(content))
        else:
            with open("../../../Results/Scrapy/amazon_scrapy_New_Arrivals_Result", "a") as myfile:
                myfile.write(''.join(content))