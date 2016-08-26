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

class zappos(BaseSpider):
    name = "zappos"
    allowed_domains = ["zappos.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.zappos.com"
    count_scraped =0
    newArrivals = True
    
    def __init__(self,*a, **kw):
            super(zappos, self).__init__(*a, **kw)
            self.start_urls.append("http://www.zappos.com")
            #self.start_urls.append("http://www.zappos.com/product/8070215/color/393374")
    
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        url = response.url
        print "\n\n\n\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls=[]
        
        if (len(hxs.select('.//div[@id="wrap"]//div[contains(@class,"pageHomepage")]')) > 0) or (len(hxs.select('.//div[@id="resultWrap"]')) > 0) or (len(hxs.select('.//div[@id="resultWrap"]/div[@id="searchResults"]')) > 0):
            self.add_links(response, new_urls)
       
        elif len(hxs.select('.//div[@id="wrap"]//div[contains(@class,"productPage")]')) > 0:
            self.get_product_details(response)
        
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):            
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)


    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []  
        sleep(2)      
        if (len(hxs.select('.//div[@id="wrap"]//div[contains(@class,"pageHomepage")]')) > 0):
            if self.newArrivals:
                navs_path = hxs.select('.//div[@id="hpTopLeft"]//h4[@class="loneHeading"]/a[contains(text(), "New Arrivals")]/@href').extract()                
            else:
                navs_path = hxs.select('.//div[contains(@class,"catNav")]//a/@href').extract()
        elif len(hxs.select('.//div[@id="resultWrap"]')) > 0 or len(hxs.select('.//div[@id="resultWrap"]/div[@id="searchResults"]')) > 0:
            navs_path = hxs.select('.//div[@id="searchResults"]/a/@href').extract()

            if len(hxs.select('.//div[@class="pagination"]//span[@class="last"]').extract())>0:
                self.handlePagination(response, urls)
        else:
            navs_path = hxs.select('.//div[contains(@class,"catNav")]//a/@href').extract()    
        
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
        #print "under pagination"
        #pagination1 = hxs.select('.//div[@id="resultWrap"]//div[contains(@class,"top")]//div[@class="pagination"]/a[contains(text(),"»")]/@href')
        pagination1 = hxs.select('.//div[@id="resultWrap"]//div[contains(@class,"top")]//div[@class="pagination"]/a[3][contains(@class,"arrow")]/@href').extract()
        pagination2 = hxs.select('.//div[@id="resultWrap"]//div[contains(@class,"top")]//div[@class="pagination"]/a[4][contains(@class,"arrow")]/@href').extract()
        
        if len(pagination1) > 0:
            pagination_url = pagination1[0]
        elif len(pagination2) > 0:
            pagination_url = pagination2[0]       
        else:
            return False

        #print pagination_url

        if pagination_url !="" :
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
                
        if (len(hxs.select('.//div[@id="wrap"]//div[contains(@class,"productPage")]')) > 0):
            #item_name = hxs.select('.//div[@id="productStage"]//a[contains(@class,"link")]/text()')[0].extract()
            item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
            #item_name.decode("windows-1252")
            item = hxs.select('.//div[@id="theater"]/span[@id="sku"]/text()')[0].extract()
            item_id =""
            if len(item.split(" ")) >0:
                item_id = item.split(" ")[1]
                print "item Id :"+item_id.decode("windows-1252")
            else:
                item_id = item
                print "item Id :"+item_id.decode("windows-1252")
                
          
            item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
            
            if len(hxs.select('.//div[@id="priceSlot"]/span[contains(@class,"salePrice")]/text()').extract()):
                item_price = hxs.select('.//div[@id="priceSlot"]/span[contains(@class,"salePrice")]/text()')[0].extract()
            else:
                item_price = hxs.select('.//div[@id="priceSlot"]/span[contains(@class,"nowPrice")]/text()')[0].extract()
            
            prod_url = ""
            meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
            if len(meta_tag_url) > 0:
                prod_url = urllib.unquote(meta_tag_url.extract()[0])
            else:
                prod_url = response.url
            self.count_scraped += 1
            content =""
            try:
                content =("\nPRODUCT URL:" + str(prod_url) + "\n\t TITLE: " + str(item_name) +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+item_price +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped))
                content.encode('ascii', 'ignore')
            except TypeError:
                content = "\nPRODUCT URL:" + str(prod_url) + "\n\t TITLE: " + str(item_name) +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+item_price +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
            
            finally:
                logging.critical(content)
                self.writelog(content, prod_url, item_name, item_id, item_price, item_img_url)
        else:
            return False
                    
                    
    def writelog(self, content, url, name, prod_id, price_str, image):
        
        price_str2 = price_str.replace(',', '')
        exp = '[\d\.]+'
        res = re.findall(exp, price_str2)
        price = 0
        if len(res) > 0:
            price = float(res[0])
        
        print "SAVING :: ITEM:: [%s] [%s] [%s] [%.2f] [%s]"% (url, name.decode("utf-8","ignore"), prod_id, price, image)
        save_item("Zappos", name, url, prod_id, price, image) 