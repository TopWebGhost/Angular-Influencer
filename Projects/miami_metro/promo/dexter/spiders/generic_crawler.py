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

class factory_jcrew(BaseSpider):
    name = "gen_crawler"
    start_urls = []
    already_added_urls = []
    count = 0
    count_scraped = 0
    newArrivals = False
#------------------------------------------- Globals for Katespade --------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://katespade.com"
    allowed_domains = ["katespade.com"]
    storeName = "Katespade"
    base_url = "http://katespade.com/"
    HomePageDiv = './/*[@id="home-content"]'
    ListingPageDIv = './/*[contains(@id,"category-level")]'
    CategoryPageDiv = './/*[contains(@id,"category-level")]'
    ProductPageDiv ='.//*[@id="product-content"]'
    #Links to check for products
    Navigation_Links = './/*[@id="navigation"]/ul/li//a/@href'
    new_arrivals_links = './/*[@id="navigation"]/ul/li[1]//a/@href'
    Product_Listing_Links = './/*[@id="search-result-items"]/li//a[@class="thumb-link"]/@href'
    Category_Navigation_Links ='.//*[contains(@id,"category-level")]//a[contains(@class,"refinement-link")]/@href'
    # Product Page Details
    standered_price_element ='.//*[@id="product-content"]//span[@class="price-standard"]/text()'
    sale_price_element = './/*[@id="product-content"]//span[@class="price-sales"]/text()'
    name_element ='.//*[@id="product-content"]/h1[@class="product-name"]/text()'
    product_image_element ='.//meta[@property="og:image"]/@content'
    item_id_element='.//*[@id="pid"]/@value' '''
# ---------------------------------------------Globals for net-a-porter -----------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://www.net-a-porter.com/"
    allowed_domains = ["net-a-porter.com"]
    storeName = "Net A Porter"
    base_url = "http://www.net-a-porter.com"
    HomePageDiv = './/*[@class="primary"]'
    ListingPageDIv = './/*[@id="sub-navigation-contents"]/ul'
    CategoryPageDiv = './/*[@id="sub-navigation-contents"]/ul'
    ProductPageDiv ='.//*[@id="product-info"]'
    #Links to check for products
    Navigation_Links = './/*[@id="top-nav-btn-links"]//a/@href'
    new_arrivals_links = './/*[@id="top-nav-btn-links"]/li[contains(@class,"whatsNew")]//a/@href'
    Product_Listing_Links = './/*[@id="product-list"]/div[contains(@class,"product-image")]//a/@href'
    Category_Navigation_Links ='.//*[@id="sub-navigation-contents"]/ul//a/@href'
    # Product Page Details
    standered_price_element ='.//*[@id="price"]/text()'
    sale_price_element = './/*[@id="price"]/text()'
    name_element ='.//*[@id="product-details"]/h2/text()'
    product_image_element ='.//img[@id="medium-image"]/@src'
    item_id_element='.//input[@id="productId"]/@value' '''
# ---------------------------------------------Globals for toryburch -----------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://www.toryburch.com/"
    allowed_domains = ["toryburch.com"]
    storeName = "Toryburch"
    base_url = "http://www.toryburch.com"
    HomePageDiv = './/*[@class="homepage"]'
    ListingPageDIv = './/*[contains(@class,"productsearchresult")]'
    CategoryPageDiv = './/*[contains(@class,"productsearchresult")]'
    ProductPageDiv ='.//*[@id="pdpMain"]'
    #Links to check for products
    Navigation_Links = './/*[@id="navigation"]//ul//li//a/@href'
    new_arrivals_links = './/*[@id="navigation"]//ul//li//a[contains(text(),"New Arrivals")]/@href'
    Product_Listing_Links = './/*[@id="search"]//div[contains(@class,"product")]/div[contains(@class,"name")]/a/@href'
    Category_Navigation_Links ='.//*[contains(@id,"category")]//a/@href'
    # Product Page Details
    standered_price_element ='.//*[contains(@id,"price")]/*[contains(@class,"standardprice")]/text()'
    sale_price_element = './/*[contains(@id,"price")]/*[contains(@class,"salesprice")]/text()'
    name_element ='.//*[contains(@class,"productname")]/text()'
    product_image_element ='.//meta[@property="og:image"]/@property'
    item_id_element='.//*[@id="masterProduct"]/@value' '''
    
# ---------------------------------------------Globals for bcbg -----------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://www.bcbg.com/"
    allowed_domains = ["bcbg.com"]
    storeName = "BCBG"
    base_url = "http://www.bcbg.com"
    HomePageDiv = './/*[@id="homepage-slider"]'
    ListingPageDIv = './/*[@id="secondary"]'
    CategoryPageDiv = './/*[@id="secondary"]'
    ProductPageDiv ='.//*[@id="pdpMain"]'
    #Links to check for products
    Navigation_Links = './/*[@id="navigation"]//a/@href'
    new_arrivals_links = './/*[@id="navigation"]//a[contains(text(),"NEW ARRIVALS")]/@href'
    Product_Listing_Links = './/*[@id="search-result-items"]/li//div[contains(@class,"product-name")]//a/@href'
    Category_Navigation_Links ='.//*[contains(@id,"category-level")]//a/@href'
    # Product Page Details
    standered_price_element ='.//*[@id="product-content"]//span[@class="original-price"]/text()'
    sale_price_element = './/*[@id="product-content"]//span[@class="price-standard"]/text()'
    name_element ='.//*[@id="pdpMain"]//h1[@class="product-name"]/text()'
    product_image_element ='.//*[@id="pdpMain"]//img[@class="primary-image"]/@src'
    item_id_element='.//*[@id="pid"]/@value' '''
    
# ---------------------------------------------Globals for 6PM -----------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://www.6pm.com/"
    allowed_domains = ["6pm.com"]
    storeName = "6 PM"
    base_url = "http://www.6pm.com"
    HomePageDiv = './/*[contains(@class,"HomepageSixpm")]'
    ListingPageDIv = './/*[contains(@class,"searchPage")]'
    CategoryPageDiv = './/*[contains(@class,"layoutThreeColumnSixpm")]'
    ProductPageDiv ='.//*[@id="theater"]'
    #Links to check for products
    Navigation_Links = './/*[@id="nav"]//a[not(@href="/")]/@href'
    new_arrivals_links = './/*[@id="navigation"]//a[contains(text(),"NEW ARRIVALS")]/@href' # no new arrivals.
    Product_Listing_Links = './/*[@id="searchResults"]/a/@href'
    Category_Navigation_Links ='.//*[@id="tcSideCol"]/a/@href'
    # Product Page Details
    standered_price_element ='.//*[@id="priceSlot"]/span[@class="oldPrice"]/text()'
    sale_price_element = './/*[@id="priceSlot"]/span[@class="oldPrice"]/text()'
    name_element ='.//*[@id="productStage"]/h1[@class="title"]/a[contains(@class,"link")]/text()'
    product_image_element ='.//*[@id="detailImage"]/img/@src'
    item_id_element='.//*[@name="productId"]/@value' '''

# ---------------------------------------------Globals for Club Monaco -----------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://www.clubmonaco.com/"
    allowed_domains = ["clubmonaco.com"]
    storeName = "Club Monaco"
    base_url = "http://www.clubmonaco.com"
    HomePageDiv = './/*[contains(@id,"home")]'
    ListingPageDIv = './/*[@id="products"]'
    CategoryPageDiv = './/*[contains(@id,"topcat")]'
    ProductPageDiv ='.//*[@id="product-content"]'
    #Links to check for products
    Navigation_Links = './/*[@id="header_menus"]//a/@href'
    new_arrivals_links = './/*[@id="navigation"]//a[contains(text(),"NEW ARRIVALS")]/@href' # no new arrivals.
    Product_Listing_Links = './/*[@id="products"]/li[contains(@class,"product")]/div[@class="product-photo"]/a/@href'
    Category_Navigation_Links ='.//*[@id="side-nav"]/ul[contains(@class,"leftnav")]/li/a/@href'
    # Product Page Details
    standered_price_element ='.//*[@id="product-information"]/div[@class="money"]/span[@class="base-price"]/text()'
    sale_price_element = './/*[@id="product-information"]/div[@class="money"]/span/text()'
    name_element ='.//*[@id="product-information"]/h4[contains(@class,"product-title")]/text()'
    product_image_element ='.//meta[@property="og:image"]/@content'
    item_id_element='.//*[@id = "productId"]/@value' '''

# ---------------------------------------------Globals for Lulemon -----------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://shop.lululemon.com"
    allowed_domains = ["lululemon.com"]
    storeName = "Lululemon"
    base_url = "http://shop.lululemon.com"
    HomePageDiv = './/*[@class="home"]'
    ListingPageDIv = './/*[@class="cdp"]'
    CategoryPageDiv = './/*[@class="cdp"]'
    ProductPageDiv ='.//*[@class="pdp"]'
    #Links to check for products
    Navigation_Links = './/*[@id="NAV"]/ul/li//a/@href'
    new_arrivals_links = './/*[@id="NAV"]/ul/li//a[contains(text(),"what\'s new")]/@href'
    Product_Listing_Links = './/*[@class="productList"]//div[@class="product"]/a[1]/@href'
    Category_Navigation_Links ='.//*[@id="pageContent"]//a/@href'
    # Product Page Details
    standered_price_element ='.//*[@id="price"]/span[@class="amount"]/text()'
    sale_price_element = './/*[@id="price"]/i/text()'
    name_element ='.//*[@id="pageContent"]//h1/div[@class="OneLinkNoTx"]/text()'
    product_image_element ='.//*[@id="productImageContainer"]//img/@src'
    item_id_element='.//*[@id="pageLoadSku"]/@value' '''

# ---------------------------------------------Globals for Bodenusa -----------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://www.bodenusa.com"
    allowed_domains = ["bodenusa.com"]
    storeName = "Bodenusa"
    base_url = "http://www.bodenusa.com"
    HomePageDiv = './/*[@class="homeModelArea"]'
    ListingPageDIv = './/*[contains(@class,"leftNav")]'
    CategoryPageDiv = './/*[contains(@class,"leftNav")]'
    ProductPageDiv ='.//*[@id="mainProductGroup"]'
    #Links to check for products
    Navigation_Links = './/*[@class="topBarNav"]//a/@href'
    new_arrivals_links = './/*[@id="NAV"]/ul/li//a[contains(text(),"what\'s new")]/@href' # No new arrival Links
    Product_Listing_Links = './/*[@id="productList"]/li/a/@href'
    Category_Navigation_Links ='.//*[@class="main"]/li/a/@href'
    # Product Page Details
    standered_price_element ='.//*[@class="titleBlock"]//span[@class="NowPrice"]/text()'
    sale_price_element = './/*[@class="titleBlock"]//span[@class="WasPrice"][contains(text(),"$")]/text()'
    name_element ='.//*[@class="titleBlock"]//span[@class="tier1Description"]/text()'
    product_image_element ='.//*[@id="ProductMain"]/@src'
    item_id_element='.//*[@class="titleBlock"]/span[contains(@class,"productCode")]/text()' '''
    
# ---------------------------------------------Globals for Revolveclothing -----------------------------------------
    '''# Checking on which page is the crawler.
    url = "http://www.revolveclothing.com"
    allowed_domains = ["revolveclothing.com"]
    storeName = "Revolve Clothing"
    base_url = "http://www.revolveclothing.com"
    HomePageDiv = './/*[@class="main_slideshow"]'
    ListingPageDIv = './/*[@id="product_index"]'
    CategoryPageDiv = './/*[@id="product_index"]'
    ProductPageDiv ='.//*[@id="detail_index"]'
    #Links to check for products
    Navigation_Links = './/*[@id="mainnav"]//a/@href'
    new_arrivals_links = './/*[@id="mainnav"]/li[1]/a/@href' # No new arrival Links
    Product_Listing_Links = './/*[@id="product_load_outer"]//div[contains(@id,"prod_list_image")]/a/@href'
    Category_Navigation_Links ='.//*[@id="hmain_feature_sub"]//a/@href'
    # Product Page Details
    standered_price_element ='.//*[@id="priceLabel1"]/text()'
    sale_price_element = './/*[@id="priceLabel1"]/text()'
    name_element ='.//*[@class="detail_shop_header"]/h2/text()'
    product_image_element ='.//*[@id="detail_img_main_img"]/@src'
    item_id_element='.//input[@name="code"]/@value' '''

# ---------------------------------------------Globals for Lillypulitzer -----------------------------------------
    # Checking on which page is the crawler.
    url = "http://www.lillypulitzer.com"
    allowed_domains = ["lillypulitzer.com"]
    storeName = "Lillypulitzer"
    base_url = "http://www.lillypulitzer.com"
    HomePageDiv = './/*[@id="homeUnderNav"]'
    ListingPageDIv = './/*[@id="thumbnailPageContent"]'
    CategoryPageDiv = './/*[@id="categoryPageContent"]'
    ProductPageDiv ='.//*[@id="productDetails"]'
    #Links to check for products
    Navigation_Links = './/*[@id="header-nav"]//ul//li//a/@href'
    new_arrivals_links = './/*[@id="mainnav"]/li[1]/a/@href' # No new arrival Links
    Product_Listing_Links = './/*[@id="thumbnailPageContent"]//div[@class="imageDisplay"]//a/@href'
    Category_Navigation_Links ='.//*[@id="categoryPageContent"]//a/@href'
    # Product Page Details
    standered_price_element ='.//*[@class="priceDisplay"]//span[@class="basePrice"]/text()'
    sale_price_element = './/*[@class="priceDisplay"]//span[@class="basePrice"]/text()' #Could not find sale price
    name_element ='.//*[@id="descriptionContainer"]/h1[@class="itemName"]/text()'
    product_image_element ='.//*[@id="mainItemImageZoomConstrainer"]/img/@src'
    item_id_element='.//*[@name="productId"]/@value'
    
    def __init__(self, *a, **kw):
            super(factory_jcrew, self).__init__(*a, **kw)
            self.start_urls.append(self.url)
            #self.start_urls.append("http://factory.jcrew.com/boys-clothing.jsp")
    def parse(self, response):
        hxs = HtmlXPathSelector(response) 
        self.count += 1
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        new_urls = []
        # Check for Product DIV First as its the innermost Page.
        if len(hxs.select(self.ProductPageDiv)) > 0:
            print "got product page div"
            self.get_product_details(response);
        # Check for Home page and other product listing pages.
        elif len(hxs.select(self.HomePageDiv)) >0 or len(hxs.select(self.ListingPageDIv)) > 0 or len(hxs.select(self.CategoryPageDiv)) > 0:
            self.add_links(response, new_urls)
       
        
        for url_to_follow in new_urls:            
            if not (url_to_follow in self.already_added_urls):
                self.already_added_urls.append(url_to_follow)
                yield Request(url_to_follow, callback=self.parse)
                
    def add_links(self, response, urls):
        hxs = HtmlXPathSelector(response) 
        navs_path = []
        if len(hxs.select(self.ListingPageDIv)) > 0 or len(hxs.select(self.CategoryPageDiv)) :
            if len(hxs.select(self.Product_Listing_Links))>0:
                navs_path = hxs.select(self.Product_Listing_Links).extract()
                #print navs_path
            else:
                navs_path = hxs.select(self.Category_Navigation_Links).extract()
        elif len(hxs.select(self.HomePageDiv)) > 0:
            if self.newArrivals:
                navs_path = hxs.select(self.new_arrivals_links).extract()          
            else:
                navs_path = hxs.select(self.Navigation_Links).extract() 
            
        for path in navs_path:
            
            url_to_follow = ""
            if "http://" not in path:
                url_to_follow = self.base_url + path
            else:
                url_to_follow = path
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow)
                           
    # Not Using Pagination as of now, Will check this as we need to switch between selenium and scrapy pagination
    def handlePagination(self,response,urls):
        pagination_url = ""
        hxs = HtmlXPathSelector(response)
        pagination_url = hxs.select('.//*[@class="paginationTop"]//li[@class="pageNext"]/a/@href')[0].extract()
        print "under pagination"
        if pagination_url !="":
            url_to_follow = ""
            if "http://" not in pagination_url:
                url_to_follow = self.base_url + pagination_url
            else:
                url_to_follow = pagination_url
            if not (url_to_follow in self.already_added_urls):
                urls.append(url_to_follow) 
    
    def get_product_details(self, response):
        hxs = HtmlXPathSelector(response)
        print "in product details"
        if len(hxs.select(self.ProductPageDiv))>0:
            item_name = hxs.select(self.name_element)[0].extract().strip()
            item_name = item_name.encode("utf-8")
            item_id = hxs.select(self.item_id_element)[0].extract()
            item_img_url = hxs.select(self.product_image_element)[0].extract()
            item_price=0.0
            print self.standered_price_element
            print self.sale_price_element
            if len(hxs.select(self.sale_price_element))>0:
                item_price = self.price_string_to_float(hxs.select(self.sale_price_element)[0].extract())
            else:
                item_price = self.price_string_to_float(hxs.select(self.standered_price_element)[0].extract())
            '''if len(hxs.select(self.sale_price_element))>0:
                item_price_ele = self.price_string_to_float(self.standered_price_element)
            else:
                item_price_ele = self.price_string_to_float(self.sale_price_element)
                
            item_price_arr = item_price_ele.split(" ")
            if len(item_price_arr) > 1:
                print item_price_arr[1]
                item_price = self.price_string_to_float(item_price_arr[1])
            else:
                item_price = self.price_string_to_float(item_price_arr[0])'''
            
            prod_url = response.url
            self.count_scraped += 1
            content = "\n"+str(self.count_scraped) + ". PRODUCT URL:" + prod_url + "\n\t TITLE: " + item_name.decode("utf-8","ignore") + "\n\t ITEM ID: " + str(item_id) + "\n\t ITEM PRICE:" + str(item_price) + "\n\t IMAGE URL:" + item_img_url + "\n\t TOTAL SO FAR: " + str(self.count_scraped)
            logging.critical(content)
            save_item(self.storeName, item_name, prod_url, item_id, item_price, item_img_url)
        
                    
    def price_string_to_float(self, price):
        #print price
        price = price.replace(" ","")
        price_arr = price.split("$")
        #print price_arr 
        conv_price = 0.00
        for pr in price_arr:
            try:
                #print pr
                conv_price = float(re.sub(r'[^\d.]+', '', pr)) 
                #print conv_price
            except:
                pass
        #print conv_price
        return conv_price
