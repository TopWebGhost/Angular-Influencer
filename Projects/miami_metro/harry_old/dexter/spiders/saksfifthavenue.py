
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

class saksfifthavenue(BaseSpider):
    name = "saksfifthavenue"
    allowed_domains = ["saksfifthavenue.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.saksfifthavenue.com"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(saksfifthavenue, self).__init__(*a, **kw)
            self.start_urls.append("http://www.saksfifthavenue.com")
            #self.start_urls.append("http://www.saksfifthavenue.com/main/ProductDetail.jsp?PRODUCT<>prd_id=845524446171787")

    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls=[]
        
        
        if len(hxs.select('.//body[@id="productDetail"]')) > 0:
            self.get_product_details(response);
            
        elif len(hxs.select('.//div[@id="mhp"]')) > 0 or "Entry.jsp" in response.url or "SectionPage.jsp" in response.url:
            self.add_links(response, new_urls)
        elif len(hxs.select('.//div[@id="pc-top"]')) > 0:
            self.add_links(response, new_urls) 

        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if len(hxs.select('.//div[@id="pc-top"]')) > 0:
            navs_path = hxs.select('.//div[@id="product-container"]//a[contains(@id,"image-url")]/@href').extract()
            
            if len(hxs.select('.//div[@id="pc-top"]//ol/li/a[@class="next"]/@href').extract())>0:
                self.handlePagination(response, urls)
        
        elif len(hxs.select('.//div[@id="saksBody"]//div[@id="pa-content-wrap"]//div[@id="left-nav-content"]')) > 0:
            
            if self.newArrivals:
                
                navs_path = hxs.select('.//div[@id="saksBody"]//div[@id="pa-content-wrap"]//div[@id="left-nav-content"]//ul[@class="guided"]/li/a[contains(text(), "New Arrivals")]/@href').extract()                

            else:
                navs_path = hxs.select('.//div[@id="saksBody"]//div[@id="pa-content-wrap"]//div[@id="left-nav-content"]//ul[@class="guided"]/li/a/@href').extract()
        
        elif len(hxs.select('.//div[@id="saks-nav-categories"]//ul[@id="saks-nav-categories-list"]')) > 0:
            navs_path = hxs.select('.//div[@id="saks-nav-categories"]//ul[@id="saks-nav-categories-list"]//a[@class="nav-link"]/@href').extract() 
        

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
        #print "under pagination"
       
       
        pagination1 = hxs.select('.//div[@id="pc-top"]//ol/li/a[@class="next"]/@href').extract()
        
        if len(pagination1) > 0:
            pagination_url = pagination1[0]
        else:
            return False
        #print pagination_url
        #sys.exit()
        url = response.url.split("?")
        if len(pagination1) > 0:
            url_to_follow = ""
            if "http://" not in pagination_url:
                url_to_follow = self.base_url + pagination_url
            else:
                url_to_follow = pagination_url
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)

            
    def get_product_details(self,response):
        hxs = HtmlXPathSelector(response)
        item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
        item_name = item_name.encode("utf-8")
        #print item_name+"\n"
        if len(hxs.select('.//*[@id="pdSizeColor--MainProductqtyToBuy0"]/select')) > 0:
            item_id = hxs.select('.//*[@id="pdSizeColor--MainProductqtyToBuy0"]/select/@productcode')[0].extract()
        else:
            item_id = hxs.select('.//div[@class="pdp-item-container"]//input[contains(@name,"productCode")]/@value')[0].extract()
       
        item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
       
        '''if len(hxs.select('.//div[@id="saksBody"]//div[@class="pdp-item-container"][1]//span[@class="blackBold11"]/span[@class="product-sale-price"]')) > 0:
            item_price_arr = hxs.select('.//div[@id="saksBody"]//div[@class="pdp-item-container"][1]//span[@class="blackBold11"]/span[@class="product-sale-price"]/text()')[0].extract().split(" ")
            if len(item_price_arr)>1:
                item_price = self.price_string_to_float(item_price_arr[1])
            else:
                item_price = self.price_string_to_float(item_price_arr[0])'''
        
        if len(hxs.select('.//div[@id="saksBody"]//div[@class="pdp-item-container"][1]//table//tr//span[@class="product-price"]/text()')) >0:
            item_price_arr = hxs.select('.//div[@id="saksBody"]//div[@class="pdp-item-container"][1]//table//tr//span[@class="product-price"]/text()')[0].extract().strip().split("$")
            if len(item_price_arr)>1:
                item_price = self.price_string_to_float(item_price_arr[len(item_price_arr)-1].strip())
            else:
                item_price = self.price_string_to_float(item_price_arr[0].strip())
        else:
            item_price = "price not found"
            
        prod_url = ""
        meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
        if len(meta_tag_url) > 0:
            prod_url = urllib.unquote(meta_tag_url.extract()[0])
        else:
            prod_url = response.url
        self.count_scraped += 1
        
        content = "\nPRODUCT URL:" + str(prod_url) + "\n\t TITLE: " + item_name.decode("utf-8","ignore") +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+str(item_price) +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
        
        logging.critical(content)
        self.writelog(content, prod_url, item_name, item_id, item_price, item_img_url)
        
        
                    
    def writelog(self, content, url, name, prod_id, price, image):
        
        
        save_item("Saks Fifth Avenue", name, url, prod_id, price, image) 
    
    def price_string_to_float(self, price):

        '''

            Converts input like $129.00 to 129.00

            Or $1,299.00 to 1299.00

            Or ($20.00) to 20.00

        '''

        valueArr = price.split("-")
        value = valueArr[len(valueArr)-1]
        if float(re.sub(r'[^\d.]+', '', value)):
           return float(re.sub(r'[^\d.]+', '', value))
        else:
           return 0
                    
  