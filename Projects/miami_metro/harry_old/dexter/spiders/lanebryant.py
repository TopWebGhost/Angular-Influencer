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

class lanebryant(BaseSpider):
    name = "lanebryant"
    allowed_domains = ["lanebryant.com"]
    start_urls = []
    already_added_urls = []
    count = 0
    base_url = "http://www.lanebryant.com"
    count_scraped = 0
    newArrivals = True
    
    def __init__(self, *a, **kw):
            super(lanebryant, self).__init__(*a, **kw)
            self.start_urls.append("http://www.lanebryant.com")
            #self.start_urls.append("http://www.lanebryant.com/cowl-neck-peplum-top/p158556/index.pro?selectedColor=Gardenia&selectedSize=None%20selected")
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count += 1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls = []
               
        if (len(hxs.select('//body[@id="home"]')) > 0) or (len(hxs.select('//body[@id="thumbnail"]')) > 0):
            self.add_links(response, new_urls)
       
        elif len(hxs.select('//body[@id="product"]')) > 0:
            self.get_product_details(response);
        
        for url_to_follow in new_urls:            
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self, response, urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if len(hxs.select('//body[@id="home"]')) > 0:
           
            if self.newArrivals:
                navs_path = hxs.select('.//ul[@id="cssdropdown"]//li//a[contains(text(),"new arrivals")]/@href').extract()          
            else:
                navs_path = hxs.select('.//ul[@id="cssdropdown"]//li//a/@href').extract() 
               # print navs_path
            
        elif len(hxs.select('//body[@id="thumbnail"]')) > 0 :
            navs_path = hxs.select('.//div[contains(@class,"current-product")]//a[1]/@href').extract()
            self.handlePagination(response, urls)
        
            
        for path in navs_path:
            url_to_follow = ""
            if "http://" not in path:
                url_to_follow = self.base_url + path
            else:
                url_to_follow = path
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)
                           
    def handlePagination(self, response, urls):
        hxs = HtmlXPathSelector(response)
        pagination1 = hxs.select('.//div[@class="top-pagination-container"]//div[contains(@class,"next")]/a/@href').extract()
        
        if len(pagination1) > 0:
            pagination_url = pagination1[0]
        else:
            return False
        
        url = response.url.split("?")
        if len(pagination1) > 0:
            url_to_follow = ""
            if "http://" not in pagination_url:
                url_to_follow = self.base_url + pagination_url
            else:
                url_to_follow = path
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)
            
    def get_product_details(self, response):
        hxs = HtmlXPathSelector(response)
        item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
        item_name = item_name.encode("utf-8")
       # print item_name+"\n"
        item_id = hxs.select('.//input[@name="productId"]/@value')[0].extract()
       # print item_id+"\n"
        item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
        item_url = urllib.unquote(hxs.select('//meta[@property="og:url"]/@content')[0].extract())
        
        #print item_img_url+"\n"
        if len(hxs.select('.//div[@class="description-container"]//span[@class="catalog-display-price-text"]//span[@class="regPrice"]/text()').extract()) > 0:
            item_price_arr = hxs.select('.//div[@class="description-container"]//span[@class="catalog-display-price-text"]//span[@class="regPrice"]/text()')[0].extract().split(" ")
            print "item_price_arr %s " % item_price_arr
            if len(item_price_arr) >0:
                item_price = str(self.price_string_to_float(item_price_arr[len(item_price_arr)-1]))
            
        elif len(hxs.select('.//div[@class="description-container"]/ span[@class="catalog-display-price-text"]//span[@class="price"]/text()').extract()) > 0:
            item_price_arr = hxs.select('.//div[@class="description-container"]/ span[@class="catalog-display-price-text"]//span[@class="price"]/text()')[0].extract()
            print "item_price_arry %s " % item_price_arr
            if len(item_price_arr) >0:
                item_price = str(self.price_string_to_float(item_price_arr))
        else:
            item_price = "product price not found"
        #print item_price+"\n"
        
        self.count_scraped += 1
        content = "\n"+str(self.count_scraped) + ". PRODUCT URL:" + item_url + "\n\t TITLE: " + item_name.decode("utf-8","ignore") + "\n\t ITEM ID: " + str(item_id) + "\n\t ITEM PRICE:" + str(item_price) + "\n\t IMAGE URL:" + item_img_url + "\n\t TOTAL SO FAR: " + str(self.count_scraped)
        logging.critical(content)
        self.writelog(content, item_url, item_name, item_id, item_price, item_img_url)
                    
    def writelog(self, content, url, name, prod_id, price_str, image):
        
        price_str2 = price_str.replace(',', '')
        exp = '[\d\.]+'
        res = re.findall(exp, price_str2)
        price = 0
        if len(res) > 0:
            price = float(res[0])
        
        print "SAVING :: ITEM:: [%s] [%s] [%s] [%.2f] [%s]"% (url, name, prod_id, price, image)
        save_item("Lane Bryant", name, url, prod_id, price, image) 

    def price_string_to_float(self, price):

        '''

            Converts input like $129.00 to 129.00

            Or $1,299.00 to 1299.00

            Or ($20.00) to 20.00

        '''
        print "input string to price_string_to_float function: %s " % price
        valueArr = price.split("-")
        if len(valueArr) > 1:
            return 0
        else:
            if float(re.sub(r'[^\d.]+', '', valueArr[0])):
                print "valueArr %s: output %s " % (valueArr, re.sub(r'[^\d.]+', '', valueArr[0]))
                return float(re.sub(r'[^\d.]+', '', valueArr[0]))
            else:
                return 0
