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
    print "SAVING: %s %s %s %s %.2f %s" % (store_name, item_name.decode("utf-8","ignore"), item_url, item_id, item_price, item_image_url)
    from debra.models import Brands, ProductModel
    b = Brands.objects.get(name=store_name)
    existing_item = ProductModel.objects.filter(brand = b, c_idx = item_id)
    print existing_item
    if len(existing_item) > 0:
        print "Item " + str(existing_item[0]) + " EXISTS. Not creating new one. Returning...."
        for ii in existing_item:
            if ii.price < item_price:
                print "Updating item price from %.2f to %.2f for %s " % (ii.price, item_price, ii)
                ii.price = item_price
                ii.save()
                print "Updating item price from %.2f to %.2f for %s " % (ii.price, item_price, ii)
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

class nordstrom(BaseSpider):
    name = "nordstrom"
    allowed_domains = ["nordstrom.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://shop.nordstrom.com"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(nordstrom, self).__init__(*a, **kw)
            self.start_urls.append("http://shop.nordstrom.com")
            #self.start_urls.append("http://shop.nordstrom.com/s/xscape-ruched-stretch-satin-sheath-dress/3404113")       
    
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        url = response.url
        print "\n\n\n\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls=[]
        
        if (len(hxs.select('//div[@id="centerZone"]')) > 0) or (len(hxs.select('//div[@id="dynamicFilter"]')) > 0) or (len(hxs.select('.//div[contains(@class,"fashion-results")]')) > 0):
            self.add_links(response, new_urls)
       
        elif len(hxs.select('//div[@class="product-main"]')) > 0:
            self.get_product_details(response)
        
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):            
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)

    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []        
        if (len(hxs.select('//div[@id="centerZone"]')) > 0):
            if self.newArrivals:
                navs_path = hxs.select('.//ul[@id="menu"]/li[@id="women"]//ul/li/a[contains(text(), "New Arrivals")]/@href').extract()                
            else:
                navs_path = hxs.select('.//ul[@id="menu"]/li[@id="women"]//ul/li/a/@href').extract()
        
        elif len(hxs.select('//div[@id="dynamicFilter"]')) > 0 or len(hxs.select('.//div[contains(@class,"fashion-results")]')) > 0:
            
            navs_path = hxs.select('.//div[@class="fashion-results"]//div[contains(@class,"row")]//a[contains(@href,"/")]/@href').extract()
            
            if len(hxs.select('.//div[contains(@class,"fashion-item")]/div[contains(@class,"fashion-photo")]/a/@href').extract())>0:
              
              navs_path = hxs.select('.//div[contains(@class,"fashion-item")]/div[contains(@class,"fashion-photo")]/a/@href').extract()
              
            if len(hxs.select('.//div[@class="fashion-results"]/a/@href').extract())>0:
                navs_path += hxs.select('.//div[@class="fashion-results"]/a/@href').extract()
            
            
            if len(hxs.select('//div[contains(@class,"fashion-results-pager")]/ul[@class="arrows"]/li[@class="next"]/a/@href').extract())>0 or len(hxs.select('//div[@class="fashion-results"]/a[@class="link"]').extract())>0:
                self.handlePagination(response, urls)
            
                
        for path in navs_path:
            url_to_follow = ""
            if "http://" not in path:
                url_to_follow = self.base_url + path
            else:
                url_to_follow = path
            if not (url_to_follow in self.already_added_urls):
               urls.append(url_to_follow)
    
    def handlePagination(self,response,urls):
        pagination_url = ""
        pagination1 = []
        hxs = HtmlXPathSelector(response)
        if len(hxs.select('//div[contains(@class,"fashion-results-pager")]/ul[@class="arrows"]/li[@class="next"]/a/@href').extract())>0:
            pagination1 = hxs.select('//div[contains(@class,"fashion-results-pager")]/ul[@class="arrows"]/li[@class="next"]/a/@href').extract()
        else:
            pagination1 = hxs.select('//div[@class="fashion-results"]/a[@class="link"]').extract()
            print pagination1
        #print pagination1
        if len(pagination1) > 0:
            pagination_url = pagination1[0]
        else:
            return False
               
        if len(pagination1) > 0:
            url_to_follow = ""
            if "http://" not in pagination_url:
                url_to_follow = self.base_url + pagination_url
            else:
                url_to_follow = pagination_url
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)  
                
    def get_product_details(self,response):
        reload(sys)
        sys.setdefaultencoding('utf-8')
        hxs = HtmlXPathSelector(response)
                
        if len(hxs.select('.//div[contains(@class,"product-content")]//div[@class="rightcol"]/table')) < 1:
            print "under simple product"
            item_name = hxs.select('.//div[contains(@class,"product-content")]//div[@class="rightcol"]/h1/text()')[0].extract()
            item_name = item_name.encode("utf-8")
            items = hxs.select('.//div[@class="rightcol"]/div[@id="itemNumberPrice"]/ul[contains(@class,"itemNumberPriceRow")]/li[contains(@class,"itemNumber")]/span/text()').extract()
            item_img_url = hxs.select('.//div[@id="advancedImageViewer"]//div[contains(@class,"fashion-photo")]//div[contains(@class,"fashion-photo-wrapper")]/img/@src')[0].extract()
            item_price = self.price_string_to_float(hxs.select('.//div[@class="rightcol"]/div[@id="itemNumberPrice"]/ul[contains(@class,"itemNumberPriceRow")]/li[contains(@class,"price")]/span[contains(@class,"regular")]/text()')[0].extract())
            prod_url = ""
            meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
            if len(meta_tag_url) > 0:
                prod_url = urllib.unquote(meta_tag_url.extract()[0])
            else:
                prod_url = response.url
            self.count_scraped += 1
            content =""
            for item in items:
                if len(item.split("#")) >0:
                    item_id = item.split("#")[1]
                else:
                    item_id = item
                content +="\nPRODUCT URL:" + str(prod_url) + "\n\t TITLE: " + item_name.decode("utf-8","ignore") +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+str(item_price) +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
                print "SAVING :: ITEM:: [%s] [%s] [%s] [%.2f] [%s]"% (prod_url, item_name, item_id, item_price, item_img_url)
                self.writelog(content, prod_url, item_name, item_id, item_price, item_img_url)
            #self.writelog(content)
            
        else:
            return False
                    
    def writelog(self, content, url, name, prod_id, price_str, image):
        
        
        
        print "SAVING :: ITEM:: [%s] [%s] [%s] [%.2f] [%s]"% (url, name.decode("utf-8","ignore"), prod_id, price_str, image)
        save_item("Nordstrom", name.decode("utf-8","ignore"), url, prod_id, price_str, image) 
       
        
    def price_string_to_float(self, price):
        valueArr = price.split("-")
        if len(valueArr) > 1:
            return 0
        else:
            if float(re.sub(r'[^\d.]+', '', valueArr[0])):
                return float(re.sub(r'[^\d.]+', '', valueArr[0]))
            else:
                return 0            
    