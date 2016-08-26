
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

class bloomingdales(BaseSpider):
    name = "bloomingdales"
    allowed_domains = ["bloomingdales.com"]
    start_urls = []
    already_added_urls=[]
    count =0
    base_url= "http://www.bloomingdales.com"
    count_scraped =0
    newArrivals = False
    
    def __init__(self,*a, **kw):
            super(bloomingdales, self).__init__(*a, **kw)
            self.start_urls.append("http://www.bloomingdales.com")
            #self.start_urls.append("http://www1.bloomingdales.com/shop/product/joie-top-exclusive-capetown-color-block?ID=656413&CategoryID=23671&LinkType=#fn%3Dspp%3D20")
            #self.start_urls.append("http://www1.bloomingdales.com/shop/womens-apparel/new-arrivals?id=1000659")
            #self.start_urls.append("http://www1.bloomingdales.com/shop/product/theory-dress-jiya-color-block-cashmere-sweater?ID=649900&CategoryID=21683#fn=spp%3D1%26ppp%3D96%26sp%3D1%26rid%3D37")
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count+=1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls=[]
        
        if (len(hxs.select('.//div[@id="gn_left_nav_container"]//div[@class="gn_left_nav_section"]')) > 0) or (len(hxs.select('.//div[@id="filters"]')) > 0) or (len(hxs.select('.//div[@id="hp_template_pool1"]')) > 0):
            
            self.add_links(response, new_urls)
       
        elif len(hxs.select('.//div[@class="pdp_container"]')) > 0:
            self.get_product_details(response);


        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self,response,urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if len(hxs.select('.//div[@id="gn_left_nav_container"]//div[@class="gn_left_nav_section"]')) > 0:
            if self.newArrivals:
                
                navs_path = hxs.select('.//div[@id="gn_left_nav_container"]/div[@class="gn_left_nav_section"]//a[contains(text(), "New Arrivals")]/@href').extract()                

            else:
                navs_path = hxs.select('.//div[@id="gn_left_nav_container"]/div[@class="gn_left_nav_section"]//a/@href').extract()
        
        elif len(hxs.select('.//div[@id="hp_template_pool1"]')) > 0:
            navs_path = hxs.select('.//div[@id="bl_nav_top_menu"]/div/a/@href').extract() 
        
        elif len(hxs.select('.//div[@id="filters"]')) > 0 :
            if len(hxs.select('.//ul[@id="topPages"]/li[@id="topRightArrow"]//a')) >0:
                self.scrape_using_selenium(response, urls)
            else:
                navs_path = hxs.select('.//div[@id="thumbnails"]//div[contains(@class,"productThumbnail")]//a[contains(@class,"productThumbnailLink")]/@href').extract()
                    
        for path in navs_path:
            url_to_follow = ""
            if "http://" not in path:
                url_to_follow = self.base_url + path
            else:
                url_to_follow = path
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)
                           
    '''def handlePagination(self,response,urls):
        hxs = HtmlXPathSelector(response)
        print "under pagination"
       
       
        pagination1 = hxs.select('.//div[@id="filters"]//ul/li[@id="topRightArrow"]//a/@href').extract()
        
        if len(pagination1) > 0:
            pagination_url = pagination1[0]
        else:
            return False
        print pagination_url
        sys.exit()
        url = response.url.split("?")
        if len(pagination1) > 0:
            url_to_follow = ""
            if "http://" not in pagination_url:
                url_to_follow = self.base_url + pagination_url
            else:
                url_to_follow = pagination_url
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)'''

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
                navs_path = driver.find_elements_by_xpath('.//div[@id="thumbnails"]//div[contains(@class,"productThumbnail")]//a[contains(@class,"productThumbnailLink")]') 
                #print len(navs_path)
                for path in navs_path:
                    url_to_follow = ""
                    if "http://" not in path.get_attribute("href"):
                        url_to_follow = self.base_url + path.get_attribute("href")
                    else:
                        url_to_follow = path.get_attribute("href")
                    if not (url_to_follow in self.already_added_urls):
                        new_urls.append(url_to_follow) 
                         
            except:
                raise
            finally:
                
                if len(driver.find_elements_by_xpath('.//ul[@id="topPages"]/li[@id="topRightArrow"]//a')) > 0:
                    driver.find_element_by_xpath('.//ul[@id="topPages"]/li[@id="topRightArrow"]/div/a').click()
                    #print "clicked next button"
                    #print len(driver.find_elements_by_xpath('.//ul[@id="topPages"]/li[@id="topRightArrow"]//a'))
                    #WebDriverWait(driver, 10).until(lambda s: s.find_element_by_xpath('.//div[@id="thumbnails"]//div[contains(@class,"productThumbnail")]').is_displayed())
                    #WebDriverWait(driver, 10).until(lambda s: s.execute_script("return jQuery.active == 0"))
                    sleep(5)
                    #print "wait end"
                    pagination = True
                        
                else:
                    pagination = False
                
        driver.close()
        display.stop()

            
    def get_product_details(self,response):
        hxs = HtmlXPathSelector(response)
        item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
        item_name = item_name.encode("utf-8")
        #print item_name+"\n"
        item_id = hxs.select('.//div[@class="cmio_PDPZ1 yui-skin-sam"]/input[@id="cmio_productId"]/@value')[0].extract()
        # print item_id+"\n"
        item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
        #print item_img_url+"\n"
        if len(hxs.select('.//div[@id="pdp_main"]//div[@class="pdp_right"]//div[@class="displayNone"]')) == 0:

            if len(hxs.select('.//div[@class="priceSale"]//span[@class="priceBig"]').extract()) > 0:
                item_p = hxs.select('.//div[@class="priceSale"]//span[@class="priceBig"]/text()')[0].extract()
                item_price_arr = item_p.split(" ")
                item_price = self.price_string_to_float(item_price_arr[0])
            else:
                item_p = hxs.select('.//div[@id="pdp_main"]//div[@class="pdp_right"]//div[@class="priceSale"]/div[@class="singleTierPrice"]/span[@class="priceBig"]/text()')[0].extract()
                item_price_arr = item_p.split(" ")
                item_price = self.price_string_to_float(item_price_arr[0])

            
            
            prod_url = ""
            meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
            if len(meta_tag_url) > 0:
                prod_url = urllib.unquote(meta_tag_url.extract()[0])
            else:
                prod_url = response.url
            self.count_scraped += 1

            self.count_scraped += 1
            content = "\nPRODUCT URL:" + str(prod_url) + "\n\t TITLE: " + item_name.decode("utf-8","ignore") +"\n\t ITEM ID: "+item_id+ "\n\t ITEM PRICE:"+str(item_price) +"\n\t IMAGE URL:"+item_img_url+"\n\t TOTAL SO FAR: " + str(self.count_scraped)
            #content.decode("utf-8","ignore").encode('utf-8','ignore')
            logging.critical(content)
            self.writelog(content, prod_url, item_name, item_id, item_price, item_img_url)
        else:
            print "Price not found"
        #print item_price+"\n"
        
                    
    def price_string_to_float(self, price):
        valueArr = price.split("-")
        if len(valueArr) > 1:
            return 0
        else:
            if float(re.sub(r'[^\d.]+', '', valueArr[0])):
                return float(re.sub(r'[^\d.]+', '', valueArr[0]))
            else:
                return 0
                    
    def writelog(self, content, url, name, prod_id, price, image):
        
        print "SAVING :: ITEM:: [%s] [%s] [%s] [%.2f] [%s]"% (url, name.decode("utf-8","ignore"), prod_id, price, image)
        save_item("Bloomingdales", name, url, prod_id, price, image) 
                        
  