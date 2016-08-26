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

class rei(BaseSpider):
    name = "rei"
    allowed_domains = ["rei.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.rei.com"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(rei, self).__init__(*a, **kw)
            self.start_urls.append("http://www.rei.com")
            #self.start_urls.append("http://www.rei.com/category/1/q/Gadget+Gifts")       
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls=[]
        
        if (len(hxs.select('.//body[contains(@class,"reiHome index")]')) > 0) or ("/outlet" in url) or ("/category/" in url):
            
            self.add_links(response, new_urls)
        
        elif ("/product/" in url):
            self.get_product_details(response);
        
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if len(hxs.select('.//body[contains(@class,"reiHome index")]')) > 0 or len(hxs.select('.//body[@id="outletHp"]//ul[contains(@id,"hunt")]')) > 0:
            if self.newArrivals:
                navs_path = hxs.select('.//div[@id="headerWrapper"]//ul[contains(@id,"hunt")]/li//a[contains(text(), "New Arrivals")]/@href').extract() #a[contains(text(), "New Arrivals")]/@href                
            else:
                navs_path = hxs.select('.//div[@id="headerWrapper"]//ul[contains(@id,"hunt")]/li//a/@href').extract()
        elif len(hxs.select('.//div[@id="results"]')) > 0:
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
        while(pagination):
            try:
                navs_path = driver.find_elements_by_xpath('.//*[@id="results"]/ul/li[1]/a')
                
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
                if len(driver.find_elements_by_xpath('.//div[@id="results"]')) > 0:
                    nextbtns = driver.find_elements_by_xpath('.//div[@id="sortShowTop"]/ul[@class="show"]/li//a/div[@class="nextButton"]')
                    if len(nextbtns) > 0:
                        driver.find_element_by_xpath('.//div[@id="sortShowTop"]/ul[@class="show"]/li//a/div[@class="nextButton"]').click()
                        try:
                            WebDriverWait(driver, 3).until(lambda s: driver.find_elements_by_xpath('.//*[@id="results"]/ul/li[1]/a').is_displayed())
                        except:
                            pass
                        pagination = True
                    else:
                        pagination = False
                else:
                    pagination = False

        driver.close()
        display.stop()
            
    def get_product_details(self,response):
        hxs = HtmlXPathSelector(response)
        item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
        item_name = item_name.encode("utf-8")
       # print item_name+"\n"
        if (hxs.select('.//div[@id="itemDescrip"]')) > 0:
            itemsku = hxs.select('.//*[contains(@class,"productSKU")]/text()')[0].extract().split("#")
        else:
            itemsku = hxs.select('.//div[@id="itemDescrip"]//span[@class="itemNum"]/text()')[0].extract().split("#")
        item_id = itemsku[1].strip()
        item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
        print item_img_url+"\n"
        if len(hxs.select('.//*[contains(@class,"salePrice")]/text()').extract()) > 0:
            item_price = hxs.select('.//*[contains(@class,"salePrice")]/text()')[0].extract()
            #print item_price+"\n"
        elif len(hxs.select('.//*[contains(@class,"price")]/span[@itemprop="highPrice"]/text()').extract()) > 0:
            
            item_price = hxs.select('.//*[contains(@class,"price")]/span[@itemprop="highPrice"]/text()')[0].extract()
        else:
            item_price = hxs.select('.//*[contains(@class,"price")]/text()')[0].extract()
        #print item_price+"\n"
                
        self.count_scraped += 1
        content = "\nPRODUCT URL:" + str(response.url) + "\n\t TITLE: " + str(item_name) +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+item_price +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
        logging.critical(content)
        self.writelog(content)
                    
    def writelog(self,content):
        if not self.newArrivals:
            with open("../../../Results/Scrapy/rei_scrapy_Result", "a") as myfile:
                myfile.write(content)
        else:
            with open("../../../Results/Scrapy/rei_scrapy_New_Arrivals_Result", "a") as myfile:
                myfile.write(content)
  