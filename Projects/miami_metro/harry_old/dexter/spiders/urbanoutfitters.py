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

class urbanoutfitters(BaseSpider):
    name = "urbanoutfitters"
    allowed_domains = ["urbanoutfitters.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.urbanoutfitters.com"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(urbanoutfitters, self).__init__(*a, **kw)
            self.start_urls.append("http://www.urbanoutfitters.com")
            #self.start_urls.append("http://www.urbanoutfitters.com/urban/catalog/productdetail.jsp?id=25748567&parentid=W_APP_DRESSES")
            #print sys.argv[3]
            #self.newArrivals = sys.argv[2]
        
    def parse(self, response):
        self.count+=1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls=[]
        if ("index.jsp" in url) or ("category.jsp" in url):
            self.add_links(response, new_urls)
       
        elif "productdetail.jsp" in url:
                self.get_product_details(response);
        
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):            
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        if "index.jsp" in response.url:
            if self.newArrivals:
                navs_path = hxs.select('//div[@id="header-subnav-wrapper"]/div[@class="subnavTwoColList"]/div[@class="subnavTwoCol-column"]/a[contains(text(), "New Arrivals")]/@href').extract()                
            else:
                navs_path = hxs.select('//div[@id="header-subnav-wrapper"]/div[@class="subnavTwoColList"]/div[@class="subnavTwoCol-column"]/a/@href').extract()
                print navs_path
            
        elif "category.jsp" in response.url:
            navs_path = hxs.select('//div[@id="category-products"]/div[@class="category-product"]/div[@class="category-product-media"]/p[@class="category-product-image"]/a/@href').extract()
            self.handlePagination(response, urls)
            
        for path in navs_path:
            url_to_follow = self.base_url + path
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)
                           
    def handlePagination(self,response,urls):
        hxs = HtmlXPathSelector(response)
        pagination1 = hxs.select('.//*[@id="category-content"]/div[2]/p[2]/span[2]/a[2]/@href')
        pagination2 = hxs.select('.//*[@id="category-content"]/div[2]/p[2]/span[2]/a/@href')
        if len(pagination1) > 0:
            pagination_url = hxs.select('.//*[@id="category-content"]/div[2]/p[2]/span[2]/a[2]/@href')[0].extract()
        elif len(pagination2) > 0:
            pagination_url = hxs.select('.//*[@id="category-content"]/div[2]/p[2]/span[2]/a/@href')[0].extract()
        else:
            return False
        
        url = response.url.split("?")
        if len(pagination1) > 0 or len(pagination2) > 0:
            url_to_follow = url[0]+ pagination_url
            urls.append(url_to_follow)           
           # print "\n\n\n Pagination URL: "+url_to_follow
            
    def get_product_details(self,response):
        hxs = HtmlXPathSelector(response)
        item_name_path = hxs.select('//div[@id="prodOptions"]/h2[@id="prodTitle"]/text()')
        item_name=""
        if len(item_name_path) == 0:
            self.invalid_links += 1
            return (False, None)
        else:
            item_name = item_name_path[0].extract()
            item_id =""
            item_price =""
            item_img_url = ""
            if len(hxs.select('//meta[@name="productid"]')) >0: 
                item_id = hxs.select('//meta[@name="productid"]/@content')[0].extract()
               
            if len(hxs.select(".//*[@id='prodOptions']/h2[2]/span[1]")) > 0:
                item_price = hxs.select(".//*[@id='prodOptions']/h2[2]/span[1]/text()")[0].extract()
            if len(hxs.select(".//img[@id='prodMainImg']")) > 0:
                item_img_url= hxs.select(".//img[@id='prodMainImg']/@src")[0].extract()
        prod_url = ""
        meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
        if len(meta_tag_url) > 0:
            prod_url = urllib.unquote(meta_tag_url.extract()[0])
        else:
            prod_url = response.url
        self.count_scraped += 1
        content = "\nPRODUCT URL:" + str(prod_url) + "\n\t TITLE: " + str(item_name) +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+item_price +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
        logging.critical(content)
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
            save_item("urbanoutfitters.com/", name, url, prod_id, price, image)                
  