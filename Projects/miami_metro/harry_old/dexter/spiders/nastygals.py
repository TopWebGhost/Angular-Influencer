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


class nastygal(BaseSpider):
    name = "nastygal"
    allowed_domains = ["nastygal.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.nastygal.com"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(nastygal, self).__init__(*a, **kw)
            self.start_urls.append("http://www.nastygal.com")
                   
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls=[]
        
        if (len(hxs.select('//body[@class="l-home"]')) > 0) or ((len(hxs.select('//body[@class="l-products"]')) > 0) and len(hxs.select('//form[@id="vProduct-quickFind-form-1"]')) > 0 or (len(hxs.select('//body[@class="l-collectionsLookbook"]')) > 0)):
            
            self.add_links(response, new_urls)
       
        elif len(hxs.select('//div[contains(@class,"v-product-detailpagetemplate")]')) > 0:
            self.get_product_details(response);
        
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if len(hxs.select('//body[@class="l-home"]')) > 0:
           
            if self.newArrivals:
                navs_path = hxs.select('.//div[@id="nav-primary"]/ul/li/a[(@title, "What\'s New")]/@href').extract() #a[contains(text(), "New Arrivals")]/@href                
            else:
                navs_path = hxs.select('.//div[@id="nav-primary"]/ul/li/a/@href').extract() 
                print navs_path
            
        elif len(hxs.select('//body[@class="l-products"]')) > 0 and len(hxs.select('//form[@id="vProduct-quickFind-form-1"]')) > 0:
           navs_path = hxs.select('//div[@class="v-product-browsepagetemplate"]//div[contains(@class,"product")]/div[@class="image"]//a[1]/@href').extract()
           self.handlePagination(response, urls)
        elif len(hxs.select('//body[@class="l-collectionsLookbook"]')) > 0:
            navs_path = hxs.select('//div[@id="galleryImages"]/div/a/@href').extract()
            
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
        pagination1 = hxs.select('.//*[contains(@class,"pagination")]//ul/li[@class="next"]/a/@href').extract()
        
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
            
    def get_product_details(self,response):
        hxs = HtmlXPathSelector(response)
        item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
       # print item_name+"\n"
        item_id = hxs.select('//meta[@property="eb:id"]/@content')[0].extract()
       # print item_id+"\n"
        item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
        print item_img_url+"\n"
        if len(hxs.select('//div[@class="v-product-detailinfo"]//div[contains(@class,"price-original")]//del/text()').extract()) > 0:
            item_price = hxs.select('//div[@class="v-product-detailinfo"]//div[contains(@class,"price-original")]//del/text()')[0].extract()
            #print item_price+"\n"
        else:
            item_price = hxs.select('//meta[@property="eb:price"]/@content')[0].extract()
        #print item_price+"\n"
                
        self.count_scraped += 1
        content = "\nPRODUCT URL:" + str(response.url) + "\n\t TITLE: " + str(item_name) +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+item_price +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
        logging.critical(content)
        prod_url = response.url
        self.writelog(content, prod_url, item_name, item_id, item_price, item_img_url)
                    
    def writelog(self, content, url, name, prod_id, price_str, image):
        
        price_str2 = price_str.replace(',', '')
        exp = '[\d\.]+'
        res = re.findall(exp, price_str2)
        price = 0
        if len(res) > 0:
            price = float(res[0])
        if 'e-gift-card' in url:
            print "NOT SAVING :: ITEM:: [%s] [%s] [%s] [%.2f] [%s]"% (url, name, prod_id, price, image)
        else:
            print "SAVING :: ITEM:: [%s] [%s] [%s] [%.2f] [%s]"% (url, name, prod_id, price, image)
            save_item("Nasty Gal", name, url, prod_id, price, image) 
  