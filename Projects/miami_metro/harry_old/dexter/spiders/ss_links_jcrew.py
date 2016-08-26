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
from harry.dexter.items import Category, ProductItem, ColorSizeItem, CategoryItem
from debra.models import Brands, ProductModel, Items
import os, errno
from time import sleep
import urllib
from debra.modify_shelf import store_spec_product_categorization
from django.utils.encoding import smart_str, smart_unicode

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)




class SSJCrewSpider(CrawlSpider):
    name = "ssjcrew"
    store_name = "J.Crew"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    
    count_scraped = 0
    
    invalid_links = 0
    
    urls_scraped = set()
    items_to_scrape = []
    items_scraped = []
    count = 0
    date = datetime.datetime.now()
    
    handle_httpstatus_list = [302]
   
    date_ = datetime.date.today() #(2012, 1, 31)

    start_night = datetime.time(0)
    mid_night = datetime.time(23, 59, 59)
    #day = datetime.timedelta(hours=23, minutes=59, seconds=59)
    d_start = datetime.datetime.combine(date_, start_night)
    d_end = datetime.datetime.combine(date_, mid_night)

    insert_date = date_ #datetime.date(2000, 1, 11)

    # prod url -> ss link url
    prod_link_to_ss_link_map = {} 
    start_urls = []
    
    def __init__(self, *a, **kw):
        super(SSJCrewSpider, self).__init__(*a, **kw)
        try:
            if kw['single_url']:
                self._initialize_spec_urls(a[0], single_url=kw['single_url'])
            else:
                self._initialize_start_urls()
        except KeyError:
            self._initialize_start_urls()

    def _initialize_spec_urls(self, *a, **kw):
        print '==========INITIALIZATION======='
        one_url = kw['single_url']
        if one_url:
            url = a[0]
            self.start_urls.append(url)

    def _initialize_start_urls(self):
        ### for INITIAZATION only
        #items_on_date = ProductModel.objects.filter(brand__name = self.store_name)
        #for item in items_on_date:
        #    print "ITEM: " + str(item.prod_url)
        #    if item.prod_url != 'Nil':
        #        self.start_urls.append(item.prod_url)
        
            
        items_on_date = Items.objects.filter(insert_date__range = (self.d_start, self.d_end))
        b = Brands.objects.get(name = self.store_name)
        print b
        items_of_brand = items_on_date.filter(brand = b)
        print "Items in Brands DB: " + str(len(items_of_brand))
        #print items_of_brand[0].pr_url
        #print items_of_brand[0].name
        self.start_urls.append(items_of_brand[35].pr_url)
        #for item in items_of_brand:
        #    self.start_urls.append(item.pr_url)
        
    
    # checks if tok is present in sub
    def _contains(self, sub, tok):
        index = sub.find(tok)
        if index >= 0:
            return True
        else:
            return False

    # combine the array elements into a single string with 
    # provided delimiters
    def _combine(self, string_array, start_delim, end_delim):
        result = ""
        for i in range(0, len(string_array)):
            result += start_delim
            result += string_array[i]
            result += end_delim
            
        return result
            
            
    def _create_dir(self, fpath):
        print "Creating directory: ", fpath
        
        try:
            os.makedirs(fpath)
        except OSError as exc: # Python >2.5
            if exc.errno == errno.EEXIST:
                pass
            else: raise
            
        
    def _store_in_file(self, response, item_id):
        path_name = self.HOME + "/" + str(self.date.isoformat())
        self._create_dir(path_name)
        path_name += "/" + self.store_name + "/"
        self._create_dir(path_name)
        
        fname = path_name + str(item_id) + ".html"
        FILE = open(fname, 'w')
        FILE.write(str(response.body))
        FILE.close()
        
        
        
    #def parse_sub_sub2(self, response):
    def parse(self, response):

        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        
        if self._contains(str(url), 'PRODUCT') or self._contains(str(url), 'PRDOVR'):
            print "USEFUL URL " + str(url) 
            if response.request.meta.get('redirect_urls'):
                print "Redirected from " + str(response.request.meta.get('redirect_urls')[0])
            print "\n---SCRAPING PAGE---\n"
            valid_prod, product = self.parse_jcrew(response)
            print "\n---SCRAPING DONE---\n"
            
        self.count += 1
        print "Total pages scraped " + str(self.count_scraped) + " Total URLS " + str(self.count) + \
              " Total invalid links " + str(self.invalid_links)
        valid, url_to_follow = self.follow_forward_link(response)
        if valid:
            print "Following " + str(url_to_follow) + " \nCrawled: " + str (url)
            self.prod_link_to_ss_link_map[urllib.unquote(url_to_follow)] = url
            #print self.prod_link_to_ss_link_map
            yield Request(url_to_follow, callback=self.parse)
                
        #return []
            
    def follow_forward_link(self, response):
        #print response.body
        #start_ind = urls_to_follow[0].find('url=')
        #url_start = urls_to_follow[0][start_ind+4:]
        start_ind = response.body.rfind("url=")
        print "Start index " + str(start_ind)
        if start_ind >= 0:
            url_start = response.body[start_ind+4:]
        else:
            return (False, None)
        end_ind_1 = url_start.find("'")
        end_ind_2 = url_start.find(" ")
        if end_ind_1 > end_ind_2:
            end_ind = end_ind_2
        else:
            end_ind = end_ind_1
        url_ = url_start[:end_ind]
        url__ = urllib.unquote(url_)
        if self._contains(url__, 'http'):
            if self._contains(url__, 'http://www.jcrew.com/'):
                # make sure the url ends in .jsp for jcrew URLs
                ind = url__.rfind('.jsp')
                url___ = url__[0:ind + 4]
                url__ = url___
            return (True, url__)
        else:
            return (False, url__)
        #yield Request(url_, callback=self.parse)
        
    def parse_jcrew(self, response):
        
        hxs = HtmlXPathSelector(response)

        meta_tag_item_name = hxs.select('//meta[@property="og:title"]/@content')
        if len(meta_tag_item_name) > 0:
            item_name = meta_tag_item_name.extract()[0]
        else:
            item_name_path = hxs.select('//title/text()')
            if len(item_name_path) > 0:
                item_name = item_name_path.extract()[0]
            else:
                logging.error("Not a product page: " + response.url)
                return (False, None)
        logging.critical(item_name.encode('utf-8'))
                    
        self.count_scraped += 1
        
        ''' 
        PLAYING NICE: sleeping for 3min after crawling every 100 pages
        '''
        if self.count_scraped % 100 == 0:
            sleep(3*60) # sleep for 3 mins
        
        meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
        if len(meta_tag_url) > 0:
            prod_url = meta_tag_url.extract()[0]
        else:
            prod_url = response.url
            
        logging.critical("PRODUCT URL:" + str(prod_url) + " TITLE " + str(item_name.encode('utf-8')) + \
                         " TOTAL SO FAR " + str(self.count_scraped))

        
        # find gender
        gender = 'M'
        if prod_url.lower().find('women') >= 0 or prod_url.lower().find('girl') >= 0:
            gender = 'F'
        logging.critical("Gender: " + gender)
        
        
        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs)
        
        if item_id_ in self.items_scraped:
            logging.critical("ITEM ALREADY SCRAPED " + str(item_id_) + ". RETURNING.")
            return  (True, None)
        else:
            self.items_scraped.append(item_id_)
            
        logging.critical("ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))
        if price_ > sale_price_:
            logging.critical("SALE on ITEM_ID " + str(item_id_) + " PRICE " + str(price_) +\
                             " SALE PRICE " + str(sale_price_))
        
        
        # extract image URL
        prod_img_path = hxs.select('//div[contains (@class, "prod_main_img")]/a/img[contains (@src, "http")]/@src')
        prod_img_url = prod_img_path.extract()
        logging.critical("Image URL: " + str(prod_img_url))

        
        # find description and keywords: these will be useful in categorization
        desc = hxs.select('//meta[@property="og:description"]/@content')
        desc_content = desc.extract()[0]
        logging.critical("Description: " + str(desc_content.encode('utf-8')))
        
        
        keywords = hxs.select('//meta[@name="keywords"]/@content').extract()
        keywords_content = keywords[0]
        logging.critical("Keywords: ")
        logging.critical(keywords_content)

        prod_desc = desc_content + "\n" + keywords_content
        print "Length of prod_desc " + str(len(prod_desc))
        
        product, created_new = self._create_product_item(item_name, int(item_id_), str(prod_url), price_, \
                                            sale_price_, gender, str(prod_img_url[0]), prod_desc)
        print "gender " + str(product.gender)
        cat_path = hxs.select('//ul[@class="leftnav_sub_sub"]')
        subcat_path = cat_path.select('../p/span/a/@id').extract()
        cat1 = "Nil"
        cat2 = "Nil"
        cat3 = "Nil"
        
        if len(subcat_path) > 0:
            cat1 = subcat_path[0]
        
        print cat1
        print cat2 
        store_spec_product_categorization(product, cat1, cat2, cat3)
        print "Cat1 " + str(product.cat1) + " Cat2 " + str(product.cat2) + " Cat 3" + str(product.cat3)
                
                
        error = hxs.select('//span[@class="select-error"]/text()')
        if len(error) > 0:
            logging.critical("Error: " + (error.extract()[0]).encode('utf-8'))
        #self._store_in_file(response, item_id_)
        #raise CloseSpider('Blah')
        logging.critical("Total unique items: " + str(len(self.all_items_scraped)) + " we have scraped so far: " +\
                          str(self.count_scraped) + " Unique URLs scraped: " + str(len(self.urls_scraped)))
        #raise SystemExit
        
        return (True, product)

  
    def _create_product_item(self, name, prod_id, prod_url, price, saleprice, 
                             gender, img_url, prod_desc):
        b = Brands.objects.get(name = self.store_name)

        existing_item = ProductModel.objects.filter(brand = b).filter(idx = prod_id)
        print existing_item
        if len(existing_item) > 0:
            print "Item " + str(existing_item[0]) + " EXISTS. Not creating new one. Returning...."
            return (existing_item[0], False)
        
        item = ProductModel(brand = b, 
                            idx = prod_id,
                            name = name,
                            prod_url = prod_url,
                            price = price,
                            saleprice = saleprice,
                            promo_text = "None",
                            gender = gender,
                            img_url = img_url,
                            description = prod_desc,
                            insert_date = self.insert_date,)
        
         
        logging.critical("CREATE_PRODUCT OBJ: foreign key " + str(b))
        print "Prod id " + str(prod_id) + " url " + str(prod_url) + " img " + str(img_url)
        
        #print item
        
        return (item.save(), True)
        
    
    def _create_color_size(self, product, color_array, size_array):
        c_size = len(color_array)
        s_size = len(size_array)
        # pick the minimum
        min = c_size
        if c_size > s_size:
            min = s_size
        for i in range(0, min):
            colorsize = ColorSizeItem()
            colorsize['product'] = ProductModel.objects.get(pk=product.id)
            colorsize['color'] = color_array[i]
            colorsize['size'] = size_array[i]
            colorsize.save()
        
        
    
    def _create_category(self, product, categories):
        for cat in categories:
            category = CategoryItem()
            category['product'] = ProductModel.objects.get(pk=product.id)
            category['categoryId'] = 0
            category['categoryName'] = cat
            category.save()

    def _find_price(self, hxs):
        price = 0
        sale_price = 0
        item_id = -1
        
        price_path = hxs.select('//span[@class="price-single"]/text()').extract()[0]
        dollar_ind = price_path.find('$')
        if dollar_ind >= 0:
            price = price_path[dollar_ind+1:]
        else:
            price = -1
        
        sale_price_path = hxs.select('//span[@class="select-sale-single"]/text()').extract()
        if len(sale_price_path) > 0:
            dollar_ind = sale_price_path[0].find('$')    
            sale_price = sale_price_path[dollar_ind+1:]
        
        item_id_path = hxs.select('//span[@class="itemid-single"]/text()').extract() 
        if len(item_id_path) > 0:
            item_id_data = item_id_path[0]
            if len(item_id_data) > 1:
                item_id = item_id_data.split()[1]

        
        return (item_id, price, sale_price)
        
        
        
        
