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

class topshop(BaseSpider):
    name = "topshop"
    allowed_domains = ["topshop.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.topshop.com/webapp/wcs/stores/servlet/"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(topshop, self).__init__(*a, **kw)
            self.start_urls.append("http://www.topshop.com")
            #self.start_urls.append("http://www.topshop.com/webapp/wcs/stores/servlet/CatalogNavigationSearchResultCmd?catalogId=33057&storeId=12556&langId=-1&viewAllFlag=false&sort_field=Relevance&categoryId=208523&parent_categoryId=203984&beginIndex=1&pageSize=20&geoip=noredirect")      
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body))) + "\n\n\n\n"
        new_urls=[]
        
        if (len(hxs.select('.//*[@id="cmd_topcategoriesdisplay"]')) > 0) or (len(hxs.select('.//*[@id="cmd_catalognavigationsearchresultcmd"]')) > 0):
            self.add_links(response, new_urls)
        elif len(hxs.select('//*[@id="cmd_productdisplay"]')) > 0:
            self.get_product_details(response)
        
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
    
    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if len(hxs.select('.//body[@id="cmd_topcategoriesdisplay"]')) > 0:
            if self.newArrivals:
                navs_path = hxs.select('.//*[@id="nav_catalog_menu"]//a[contains(text(), "New Arrivals")]/@href').extract() #a[contains(text(), "New Arrivals")]/@href                
            else:
                navs_path = hxs.select('.//*[@id="nav_catalog_menu"]//a/@href').extract()
            
        elif len(hxs.select('.//div[@id="top_pagination_list"]')) > 0:
            navs_path = hxs.select('.//div[contains(@class,"wrapper_product_list")]//ul/li[@class="product_image"]/a/@href').extract()
            self.handlePagination(response, urls)
        
        for path in navs_path:
            url_to_follow = ""
            if "http://" not in path:
                url_to_follow = self.base_url + path+"&geoip=noredirect"
            else:
                url_to_follow = path+"&geoip=noredirect"
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)
             
    def handlePagination(self,response,urls):
        pagination_url = ""
        pagination1 = []
        hxs = HtmlXPathSelector(response)
        pagination1 = hxs.select('.//div[@id="wrapper_page_content"]/div[@id="top_pagination_list"]//li[@class="show_next"]/a/@href').extract()
        if len(pagination1)>0:
            pagination_url = pagination1[0]
        #print pagination_url
        #print len(pagination1)
        if len(pagination1) > 0:
            url_to_follow = ""
            if "http://" not in pagination_url:
                url_to_follow = self.base_url + pagination_url +"&geoip=noredirect"
            else:
                url_to_follow = pagination_url+"&geoip=noredirect"
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow) 
   
    def price_string_to_float(self, price):
        valueArr = price.split("-")
        if len(valueArr) > 1:
            return 0
        else:
            if float(re.sub(r'[^\d.]+', '', valueArr[0])):
                return float(re.sub(r'[^\d.]+', '', valueArr[0]))
            else:
                return 0    
            
    def get_product_details(self,response):
        hxs = HtmlXPathSelector(response)
        if len(hxs.select('//meta[@property="og:title"]/@content')) > 0:
            item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
        else:
            item_name = hxs.select('.//*[contains(@id,"product_tab")]/h1/text()')[0].extract()
        item_name = item_name.encode("utf-8")
        item_id = hxs.select('.//*[@class="product_summary"]/li[@class="product_code"]/span/text()')[0].extract().strip()
        if len(hxs.select('.//meta[@property="og:image"]/@content')) > 0:
            item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
        else:
            item_img_url = hxs.select('.//*[@id="product_view_full"]/img/@src')[0].extract()
        if len(hxs.select('.//*[@class="product_summary"]/li[@class="was_price product_price"]')) > 0:
            item_price = self.price_string_to_float(hxs.select('.//*[@class="product_summary"]/li[@class="now_price product_price"]/span/text()')[0].extract())
            #print item_price+"\n"
        else:
            item_price = self.price_string_to_float(hxs.select('.//*[@class="product_summary"]/li[@class="product_price"]/span/text()')[0].extract())
        self.count_scraped += 1
        content = "\nPRODUCT URL:" + str(response.url) + "\n\t TITLE: " + item_name.decode("utf-8","ignore") +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+str(item_price) +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
        logging.critical(content)
        self.writelog(content)
                    
    def writelog(self,content):
        if not self.newArrivals:
            with codecs.open("../../../Results/Scrapy/topshop_scrapy_Result", "a","utf-8") as myfile:
               myfile.write(''.join(content))
        else:
            with codecs.open("../../../Results/Scrapy/topshop_scrapy_New_Arrivals_Result", "a","utf-8") as myfile:
                myfile.write(''.join(content))
  