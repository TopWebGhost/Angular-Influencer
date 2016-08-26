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


class NeimanMarcus(BaseSpider):
    name = "neimanmarcus"
    allowed_domains = ["neimanmarcus.com"]
    start_urls = []
    already_added_urls = []
    count = 0
    base_url = "http://www.neimanmarcus.com"
    count_scraped = 0
    newArrivals = False
    
    def __init__(self, *a, **kw):
            super(NeimanMarcus, self).__init__(*a, **kw)
            self.start_urls.append("http://www.neimanmarcus.com")
            #self.start_urls.append("http://www.neimanmarcus.com/p/Blumarine-Sequined-Short-Sleeve-Cocktail-Dress-Lime-Blumarine/prod152940046_cat12210734__/?icid=&searchType=EndecaDrivenCat&rte=%252Fcategory.jsp%253FitemId%253Dcat12210734%2526pageSize%253D30%2526No%253D0%2526refinements%253D&eItemId=prod152940046&cmCat=product")
            # ------- Test Product Url -------------------
            #self.start_urls.append("http://www.neimanmarcus.com/p/Valentino-Glam-Lock-Small-Flap-Bag-Poudre-Pop-Apple-Spectrum-Spanning-Shoes-Bags/prod152450219_cat45630740__/?icid=&searchType=EndecaDrivenCat&rte=%252Fcategory.jsp%253FitemId%253Dcat45630740%2526pageSize%253D30%2526No%253D0%2526refinements%253D&eItemId=prod152450219&cmCat=product")
            # ------------ Test Category URL ----------------------
            # self.start_urls.append("http://www.neimanmarcus.com/category.jsp?itemId=cat12110766&parentId=cat10170731&masterId=cat17740742")
            #self.start_urls.append("http://www.neimanmarcus.com/etemplate/saleSiloE.jsp?itemId=cat980731&parentId=&siloId=cat980731&navid=topNavSale")
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count += 1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        
        new_urls = []
        
        if len(hxs.select('//body[contains(@class,"productPage")]')) > 0:
            self.get_product_details(response);
            
        elif len(hxs.select('//body[contains(@class,"home")]')) > 0 or "category.jsp" in response.url or "etemplate" in response.url:
            self.add_links(response, new_urls)
       
        
        
        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self, response, urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        
        if "category.jsp" in response.url or "etemplate" in response.url:
            if len(hxs.select('.//div[@id="filterContainer"]')) > 0 or len(hxs.select(".//div[@id='searchcontent']/div[@class='dimensionSorts']")) >0:
                navs_path = hxs.select('.//div[contains(@class,"product")]/div[@class="productImageContainer"]/a[@class="prodImgLink"]/@href').extract()
                
                if len(hxs.select('.//div[@id="toppagination"]/div[@class="pagingnext"]/a/@href').extract()) >0:
                   
                    self.handlePagination(response, urls)
                else:
                    self.scrape_using_selenium(response, urls)
                    
            elif len(hxs.select('.//div[@class="categoryTreeList"]/ul/li/a/@href')) >0:
                    navs_path = hxs.select('.//div[@class="categoryTreeList"]/ul/li/a/@href').extract()
            else:
                navs_path = hxs.select('.//div[@id="contentbody"]//div[@class="catalognav"]/ul/li//a/@href').extract()
                
        elif len(hxs.select('//body[contains(@class,"home")]')) > 0:
                
            if self.newArrivals:
                navs_path = hxs.select('.//div[@id="siloheader"]//a[contains(text(), "New Arrivals")]/@href').extract() #a[contains(text(), "New Arrivals")]/@href                
            else:
                navs_path = hxs.select('.//div[@id="siloheader"]//a/@href').extract() 
                #print navs_path
            
                
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
        pagination1 = hxs.select('.//div[@id="toppagination"]/div[@class="pagingnext"]/a/@href').extract()
        pagination_url = ""
        
        if len(pagination1) > 0:
            pagination_url = pagination1[0]
        else:
            return False
        
        if len(pagination1) > 0:
            url_to_follow = ""
            if "http://" not in pagination_url:
                url_to_follow = self.base_url + pagination_url
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
                navs_path = driver.find_elements_by_xpath('.//div[contains(@class,"product")]/div[@class="productImageContainer"]/a[@class="prodImgLink"]') 
                print len(navs_path)
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
                if len(driver.find_elements_by_xpath('.//div[@id="sortPagingContainer"]//div[@id="epaging"]//div[contains(@class,"pagingSlide")]/div[@class="pagingNav"]')) > 0:
                    nextbtns = driver.find_elements_by_xpath('.//div[@id="sortPagingContainer"]//div[@id="epaging"]//div[contains(@class,"pagingSlide")]')
                    nxtbtnfound = False
                    for btn in nextbtns:
                        if btn.find_element_by_xpath('./div[@class="pagingNav"]').text.strip() == "NEXT": 
                            btn.click()
                            WebDriverWait(driver, 10).until(lambda s: not s.find_elements_by_id('searchShield'))
                            #WebDriverWait(self.selenium, 10).until(lambda s: len(s.find_elements(By.CSS_SELECTOR, 'list-item')) == 0)
                            #WebDriverWait(self.driver, 5, poll_frequency=0.05).until(lambda d : not self.driver.find_element_by_xpath('.//*[@id="searchShield"]').is_displayed())
                            #sleep(5)
                            print "wait end"
                            pagination = True
                        else:
                            pagination = False
                else:
                    pagination = False
         
         
        driver.close()
        display.stop()
            
    def get_product_details(self, response):
        #print "under ge product details"
        hxs = HtmlXPathSelector(response)
        if len(hxs.select(".//form[@id='lineItemsForm']//div[@class='lineItem']")) <2 and len(hxs.select(".//form[@id='lineItemsForm']//div[@class='lineItem']")) >0:
            item_name = hxs.select('//meta[@property="og:title"]/@content')[0].extract()
            print item_name + "\n"
            print len(hxs.select('//div[@class="lineItemInfo"]/p[@class="GRAY10N"]/text()'))
            item_id = hxs.select('//div[@class="lineItemInfo"]/p[@class="GRAY10N"]/text()')[0].extract()
            item_id = item_id.strip()
            print item_id + "\n"
            item_img_url = hxs.select('//meta[@property="og:image"]/@content')[0].extract()
            print item_img_url + "\n"
            if len(hxs.select('//div[@class="lineItemInfo"]//div[@class="adornmentPriceElement"]//div[@class="price pos2"]/text()').extract()) > 0:
                item_price = hxs.select('//div[@class="lineItemInfo"]//div[@class="adornmentPriceElement"]//div[@class="price pos2"]/text()')[0].extract()
               
            elif len(hxs.select('//div[@class="lineItemInfo"]/span/text()')) > 0:
                item_price = hxs.select('//div[@class="lineItemInfo"]/span/text()')[0].extract()
            else:
                item_price = "0"
            print item_price + "\n"
            prod_url = response.url
            
            prod_url_link = hxs.select('//link[@rel="canonical"]/@href')
            if len(prod_url_link) > 0:
                prod_url = prod_url_link[0].extract()

            self.count_scraped += 1
            content = "\nPRODUCT URL:" + str(prod_url) + "\n\t TITLE: " + str(item_name) + "\n\t ITEM ID: " + item_id + "\n\t ITEM PRICE:" + item_price + "\n\t IMAGE URL:" + item_img_url + "\n\t TOTAL SO FAR: " + str(self.count_scraped)+"\n\n\n"
            logging.critical(content)
            self.writelog(content, prod_url, item_name, item_id, item_price, item_img_url)
                    
    def writelog(self, content, url, name, prod_id, price_str, image):
        '''
        if not self.newArrivals:
            with open("neimanmarcus_scrapy_result", "a") as myfile:
                myfile.write(content)
        else:
            with open("neimanmarcus_scrapy_New_Arrivals_Results", "a") as myfile:
                myfile.write(content)
        '''
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
            save_item("Neiman Marcus", name, url, prod_id, price, image)
  
