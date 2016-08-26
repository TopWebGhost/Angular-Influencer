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
from harry.dexter.items import Category, ColorSizeItem, CategoryItem
from debra.models import Brands, ProductModel, Items
import os, errno
from time import sleep
import copy
import urllib
from django.utils.encoding import smart_str, smart_unicode
from debra.modify_shelf import store_spec_product_categorization

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)

class GapFamilySpider(CrawlSpider):
    
    name = "ssgapfamily"
    #store_name = "Banana Republic"
    #store_name = "Gap"
    #store_name = "Old Navy"
    store_name = "Athleta"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    count_scraped = 0
    urls_scraped = set()
    items_to_scrape = []
    items_scraped = []
    count = 0
    date = datetime.datetime.now()
    
    
    #date_ = datetime.date.today() #(2012, 1, 31)
    date_ = datetime.date(2012, 6, 27)
    start_night = datetime.time(0)
    mid_night = datetime.time(23, 59, 59)
    #day = datetime.timedelta(hours=23, minutes=59, seconds=59)
    d_start = datetime.datetime.combine(date_, start_night)
    d_end = datetime.datetime.combine(date_, mid_night)

    insert_date = date_ #datetime.date(2000, 1, 11)
    
    handle_httpstatus_list = [302]
    
    # prod url -> ss link url
    prod_link_to_ss_link_map = {}
    
    start_urls = []

    def __init__(self, *a, **kw):
        super(GapFamilySpider, self).__init__(*a, **kw)
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
        #items_on_date = Items.objects.filter(insert_date__range = (self.d_start, self.d_end))
        items_on_date = Items.objects.all()
        b = Brands.objects.get(name = self.store_name)
        print b
        items_of_brand = items_on_date.filter(brand = b)
        print "Items in Brands DB: " + str(len(items_of_brand))
        print items_of_brand[0].pr_url
        #print items_of_brand[0].name
        #self.start_urls.append(items_of_brand[0].pr_url)
        #self.start_urls.append(items_of_brand[1].pr_url)
        #self.start_urls.append(items_of_brand[2].pr_url)

        for item in items_of_brand:
            self.start_urls.append(item.pr_url)

    
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
        
        
        
    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        
        if self._contains(str(url), '/browse/product'):# or self._contains(str(url), '/loft/catalog'):
            print "USEFUL URL " + str(url) 
            #if response.request.meta.get('redirect_urls'):
            #    print "Redirected from " + str(response.request.meta.get('redirect_urls')[0])
            print "\n---SCRAPING PAGE---\n"
            valid_prod, product = self.parse_gapfamily(response)
            print "\n---SCRAPING DONE---\n"
            if valid_prod:
                print "\n---VALID PRODUCT---\n"
            else:
                print "\n---NO, IT's NOT A VALID PRODUCT---\n"
        self.count += 1
        print "Total pages scraped " + str(self.count_scraped) + " Total URLS " + str(self.count) + \
              " Total invalid links " + str(self.invalid_links)
        valid, url_to_follow = self.follow_forward_link(response)
        if valid:
            #print "Following " + str(url_to_follow) + " \nCrawled: " + str (url)
            self.prod_link_to_ss_link_map[urllib.unquote(url_to_follow)] = url
            #print self.prod_link_to_ss_link_map
            yield Request(url_to_follow, callback=self.parse)
                
        #return []

    def follow_forward_link(self, response):
        #print "Response.body: " + response.body
        #start_ind = urls_to_follow[0].find('url=')
        #url_start = urls_to_follow[0][start_ind+4:]
        start_ind = response.body.rfind('redirect=')
        if start_ind >= 0:
            print "Found index for 'redirect'"
            url_start = response.body[start_ind+9:]
        else:
            print "No, didn't find redirect, now looking for 'url'"
            start_ind = response.body.rfind('url=')
            print "Start index " + str(start_ind)
            if start_ind >= 0:
                url_start = response.body[start_ind+4:]
        if start_ind < 0:
            return (False, None)
        end_ind_1 = url_start.find(" ")
        end_ind_2 = url_start.find("'")
        if end_ind_1 > end_ind_2:
            end_ind = end_ind_2
        else:
            end_ind = end_ind_1
        url_ = url_start[:end_ind]
        url__ = urllib.unquote(url_)#url_.decode('utf-8')
        print "Url_ : " + url_ + " Url__: " + url__
        #print "FORWARDED URL: " + str(url_)
        if self._contains(url__, 'http://'):
            print "FORWARDED URL: " + str(url__)
        
            return (True, url__)
        else:
            return (False, url__)
   
    def _helper_check(self, hxs, tag, tag_value):
        cmd_string = '//' + tag + '="' + tag_value + '"'
        result = hxs.select(cmd_string).extract()
        if result == 'False':
            print "\t Problem with " + tag + " " + tag_value
        return result
    
    def check_shelfit_validity(self, response):
        hxs = HtmlXPathSelector(response)
        print response.url

        # Size
        #d.getElementById("SelectSize_0");
        self._helper_check(hxs, "@id", "SelectSize_0")
        
        # Color
        #d.getElementById("color-picker");
        # grand kids must have <a...
        self._helper_check(hxs, "@id", "color-picker")
        
        # Img url
        #getElementById('productImage').src
        self._helper_check(hxs, "@id", "productImage")

        # quantity
        #d.getElementById('quantity').value;
        self._helper_check(hxs, "@id", "quantity")
        
        # product id
        #d.getElementById('productId').value;
        self._helper_check(hxs, "@id", "productId")
        
        # d.getElementsByTagName('meta');
        # URL
        # meta: og-url
        self._helper_check(hxs, "@property", "og:url")
        # meta: og-title
        # prod name
        self._helper_check(hxs, "@property", "og:title")

   
    def parse_gapfamily(self, response):
        #self.check_shelfit_validity(response)
        #return (False, None)
        hxs = HtmlXPathSelector(response)
        
        # find name of item
        item_name_path = hxs.select('//title/text()')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            print "Invalid link:  " + str(response.url)
            return (False, None)
        item_name = smart_unicode(item_name_path.extract()[0])
        if '|' in item_name:
            index = item_name.find('|')
            item_name = item_name[0:index]
        logging.critical("Name: " + item_name)
                
        self.count_scraped += 1
        
        ''' 
        PLAYING NICE: sleeping for 1min after crawling every 100 pages
        '''
        if self.count_scraped % 100 == 0:
            print "Sleeping for 60 secs..."
            sleep(60) # sleep for 1 mins for express
            
        can_url_path = hxs.select('//link[@rel="canonical"]/@href')
        if len(can_url_path) > 0:
            prod_url = can_url_path.extract()[0]
        else:
            prod_url = response.url
        logging.critical("PRODUCT URL:" + str(prod_url) + " ITEM_NAME " + smart_unicode(item_name) + " TOTAL SO FAR " + str(self.count_scraped))

        gender = 'F'
        if "www.bananarepublic.com" in prod_url or 'www.gap.com' in prod_url:
            gender_path = hxs.select('//a/img[contains (@class, "_selected")]/@alt')
            if len(gender_path) > 0:
                gender__ = gender_path.extract()[0]
                if 'men' in gender__ or 'boy' in gender__:
                    gender = 'M'
                
        logging.critical("GENDER: " + gender)
        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs, prod_url)
        
        if item_id_ in self.items_scraped:
            logging.critical("ITEM ALREADY SCRAPED " + str(item_id_))
            return (False, None)
        else:
            self.items_scraped.append(item_id_)
            
        logging.critical("ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))
        if price_ > sale_price_:
            logging.critical("SALE on ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))
        
        
        # extract image URL
        prod_img_path = hxs.select('//img[@id="productImage"]/@src')
        if len(prod_img_path) > 0:
            prod_img_url = str(prod_img_path.extract()[0])
            logging.critical("Image URL: " + str(prod_img_url))
        else:
            prod_img_url = ""

        # find description and keywords: these will be useful in categorization
        prod_desc = ''
        logging.critical("Description: " + prod_desc)
        
        # promo text
        # DIDN'T FIND ANY 
        #promo_path = hxs.select('//span[@class="cat-pro-promo-text"]//font/text()').extract()
        #promo_str = str(promo_path)
        #logging.critical("Promotion: ")
        #logging.critical(promo_str)
        promo_str = ""

        

        product, created_new = self._create_product_item(item_name, int(item_id_), str(prod_url), price_, \
                                                         sale_price_, gender, str(prod_img_url), promo_str, prod_desc)
        
        if product == None:
            logging.critical("Product is None----SHOULDN'T HAPPEN!!!!!******************")
            #import sys
            #sys.exit(1)
            product = ProductModel.objects.get(idx = int(item_id_))
            
        if self.store_name == "Piperlime":
            cat_path = hxs.select('//a[contains (@class, "category selected")]/text()').extract()
            subcat_path = hxs.select('//a[contains (@class, "subcategory selected")]/text()').extract()
        else:
            cat_path = hxs.select('//a[contains (@class, "categorySelected")]/text()').extract()
            subcat_path = hxs.select('//a[contains (@class, "subCategorySelected")]/text()').extract()
        cat1 = "Nil"
        cat2 = "Nil"
        cat3 = "Nil"
        
        if len(cat_path) > 0:
            cat1 = cat_path[0]
        if len(subcat_path) > 0:
            cat2 = subcat_path[0]
        print cat1
        print cat2 
        store_spec_product_categorization(product, cat1, cat2, cat3)
        logging.critical("Cat1 " + str(product.cat1) + " Cat2 " + str(product.cat2) + " Cat 3" + str(product.cat3))
        
        #self._store_in_file(response, item_id_)
        #raise CloseSpider('Blah')
        logging.critical("Total unique items: " + str(len(self.all_items_scraped)) + " we have scraped so far: " +\
                          str(self.count_scraped) + " Unique URLs scraped: " + str(len(self.urls_scraped)))
        #raise SystemExit
        
        return (True, product)
        
        
    def process_links_none(self, links):
        print "Links from BVReviews: " + str(links)
        return set()
    
    def process_links_sub(self, links):
        return links
        
    def find_itemid_in_url(self, url_str):
        start = url_str.index('prodId=')
        size = len('prodId=')
        itemid = url_str[start+size:]
        
        print "ItemID found: " + str(itemid)
        #raise SystemExit
        return itemid


  
    def avoid_redirection(self, request):
        request.meta.update(dont_redirect=True)
        #request.meta.update(dont_filter=True)
        return request
    
    def _get_color_size_array(self, response):
        colorToSizeArray = re.findall('colorToSize[\w\d\[\]\\\',=\s]+;', str(response.body))
        #print colorToSizeArray
        total = len(colorToSizeArray)
        colorSizeMapping = {}
        
        for i in range(0, total):
            mapping_var = colorToSizeArray[i]
            #print mapping_var
            '''
            mapping_var is a string, e.g.: colorToSize42466Array['ENSIGN'] = ['X Small', 'Small', 'Large'];
            '''
            square_brk_left = mapping_var.find('[')
            square_brk_right = mapping_var.find(']')
            #print "Square_left " + str(square_brk_left) + " Square_right " + str(square_brk_right)
            color = mapping_var[square_brk_left+2: square_brk_right-1]
            #print color
            
            sizes_str = mapping_var[square_brk_right+5: len(mapping_var)]
            #print sizes_str
            
            num_sizes = sizes_str.count(',') + 1
            #print "Num sizes " + str(num_sizes)
            size = []
            for j in range(0, num_sizes):
                single_quote_left = sizes_str.find("\'")
                #print "Quoteleft " + str(single_quote_left)
                remaining_sizes_str = sizes_str[single_quote_left+1: len(sizes_str)]
                #print "Remaining " + remaining_sizes_str
                single_quote_right = remaining_sizes_str.find("\'")
                #print "QuoteRight " + str(single_quote_right)
                size_elem = remaining_sizes_str[0: single_quote_right]
                #print "Size_elem " + size_elem
                size.append(size_elem)
                sizes_str = sizes_str[single_quote_right+ single_quote_left + 3: len(sizes_str)]
            #print size
            colorSizeMapping[color] = copy.deepcopy(size)
    
        return colorSizeMapping
    
    def _create_product_item(self, name, prod_id, prod_url, price, saleprice, gender, img_url, promo_text, prod_desc):
        from django.core.exceptions import ObjectDoesNotExist
        if 'www.bananarepublic.com' in prod_url:
            store = "Banana Republic"
        if 'www.gap.com' in prod_url:
            store = "Gap"
        if 'oldnavy' in prod_url:
            store = "Old Navy"
        if 'athleta' in prod_url:
            store = "Athleta"
        b = Brands.objects.get(name = store)

        try:
            existing_item = ProductModel.objects.filter(brand = b).get(idx = prod_id)
            result = existing_item
            if result.gender != gender:
                result.gender = gender
                result.save()
            logging.critical("Item " + str(result) + " EXISTS. Not creating new one. Returning....gender " + result.gender)
            return (result, False)
        except ObjectDoesNotExist:
            
            print "Prod id " + str(prod_id) + " url " + str(prod_url) + " img " + str(img_url) + " gender " + gender \
                    + " price " + str(price) 
            item = ProductModel(brand = b, 
                                idx = prod_id,
                                name = name,
                                prod_url = prod_url,
                                price = price,
                                saleprice = saleprice,
                                promo_text = promo_text,
                                gender = gender,
                                img_url = img_url,
                                description = prod_desc,
                                insert_date = self.insert_date,)
             
            logging.critical("CREATE_PRODUCT OBJ: foreign key " + str(b))
            logging.critical("Prod id " + str(prod_id) + " url " + str(prod_url) + " img " + str(img_url) + " gender " + gender)
            
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

    def _find_price(self, hxs, url):
        ind_of_slash = url.rfind('/')
        # /P492952.jsp => 492952
        item_id = url[ind_of_slash+2: len(url)-4]
        print "ITEM_ID " + str(item_id)

        price_path = hxs.select('//span[@id="priceText"]/text()')
        
        if len(price_path) > 0:
            price_temp = price_path.extract()[0]
            price = float(price_temp.replace('$', ''))

        else:
            print "PRICE NOT FOUND"
            price = -1
            
        # Don't care about sale price since we're going to do that calculation soon
        return (item_id, price, price)
        
        
        
        
