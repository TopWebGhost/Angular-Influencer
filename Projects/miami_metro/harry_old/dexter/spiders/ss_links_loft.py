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

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)

class AnnTaylorSpider(CrawlSpider):
    """
        Differences with Ann Taylor: 
            1. the price field sometimes has an additional <strong> </strong> 
    """
    
    name = "loft"
    store_name = "Loft"
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
        super(AnnTaylorSpider, self).__init__(*a, **kw)
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
        items_on_date = Items.objects.filter(insert_date__range = (self.d_start, self.d_end))
        b = Brands.objects.get(name = self.store_name)
        print b
        items_of_brand = items_on_date.filter(brand = b)
        print "Items in Brands DB: " + str(len(items_of_brand))
        #print items_of_brand[0].pr_url
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
        
        if self._contains(str(url), '/loft/catalog/'):# or self._contains(str(url), '/loft/catalog'):
            print "USEFUL URL " + str(url) 
            #if response.request.meta.get('redirect_urls'):
            #    print "Redirected from " + str(response.request.meta.get('redirect_urls')[0])
            print "\n---SCRAPING PAGE---\n"
            valid_prod, product = self.parse_anntaylor(response)
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
        end_ind = url_start.find("'")
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

   
    def parse_anntaylor(self, response):
        self.check_shelfit_validity(response)
        return (False, None)
        hxs = HtmlXPathSelector(response)
        
        # find name of item
        item_name_path = hxs.select('//div[@class="hd-info"]//h1/text()')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            print "Invalid link:  " + str(response.url)
            return (False, None)
        item_name = smart_unicode(item_name_path.extract()[0])
        logging.critical("Name: " + item_name)
                
        self.count_scraped += 1
        
        ''' 
        PLAYING NICE: sleeping for 1min after crawling every 100 pages
        '''
        if self.count_scraped % 100 == 0:
            print "Sleeping for 60 secs..."
            sleep(60) # sleep for 1 mins for express
            
        meta_tag_url = hxs.select('//meta[@property="og:url"]/@content')
        
        prod_url = meta_tag_url.extract()[0]
        logging.critical("PRODUCT URL:" + str(prod_url) + " ITEM_NAME " + smart_unicode(item_name) + " TOTAL SO FAR " + str(self.count_scraped))

        # Ann Taylor is for women only
        gender = 'F'
        
        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs, prod_url)
        
        if item_id_ in self.items_scraped:
            logging.critical("ITEM ALREADY SCRAPED " + str(item_id_))
            # store the category for this itemid
            print "Appending categories for product " + str(item_id_)
            categories_path = hxs.select('//div[@id="cat-pro-pagnation"]//a/text()').extract()
            num_categories = len(categories_path)
            categories = []
            for i in range(0, num_categories):
                category = str(categories_path[i]).strip('\n').strip()
                categories.append(category)
                logging.critical("Categories: " + category)
            product = ProductModel.objects.filter(idx = item_id_).filter(insert_date = insert_date)
            self._create_category(product, categories)
            return (False, None)
        else:
            self.items_scraped.append(item_id_)
            
        logging.critical("ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))
        if price_ > sale_price_:
            logging.critical("SALE on ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))
        
        
        # extract image URL
        prod_img_path = hxs.select('//img[@id="productImage"]/@src')
        prod_img_url = str(prod_img_path.extract()[0])
        logging.critical("Image URL: " + str(prod_img_url))


        # find description and keywords: these will be useful in categorization
        desc = hxs.select('//div[@class="gu gu-first description"]/p/text()').extract()
        prod_desc = ''.join(desc)
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
        
        product = None
        
        
        
        
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
                            promo_text = promo_text,
                            gender = gender,
                            img_url = img_url,
                            description = prod_desc,
                            insert_date = self.insert_date,)
         
        logging.critical("CREATE_PRODUCT OBJ: foreign key " + str(b))
        print "Prod id " + str(prod_id) + " url " + str(prod_url) + " img " + str(img_url)
        '''item['brand'] = b
        item['idx'] = prod_id
        item['name'] = name
        item['prod_url'] = prod_url
        item['price'] = price
        item['saleprice'] = saleprice
        item['promo_text'] = promo_text
        item['err_text'] = "None"
        item['gender'] = gender
        item['img_url'] = img_url
        item['description'] = prod_desc
        item['insert_date'] = self.insert_date
        '''
        #print item
        print "CREATING NEW PRODUCT MODEL OBJ"
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
        item_id_elem = hxs.select('//div[@class="details"]/p/text()')
        item_id_full = item_id_elem.extract()[0] #self.find_itemid_in_url(url)
        # item_id_full has the following content: Style #258734
        item_id = item_id_full[7:]
        print "ITEM_ID " + str(item_id)

        cur_price_dollars_elem = hxs.select('//div[@class="price"]/p[@class="sale"]/text()')
        cur_price_cents_elem = hxs.select('//div[@class="price"]/p[@class="sale"]/sup[@class="cents"]/text()')
        
        if len(cur_price_dollars_elem.extract()) > 1:
            cur_price_dollars = cur_price_dollars_elem.extract()[1]
            print "CURRENT DOLLAR AMOUNT:" + cur_price_dollars
            if len(cur_price_cents_elem) > 0:
                cents = cur_price_cents_elem.extract()[0]
                print "CURRENT DOLLAR AMOUNT: CENTS: " + cents
                cur_price_dollars += cents
                print "CURRENT DOLLAR AMOUNT: OVERALL: " + cur_price_dollars
        else:
            cur_price_dollars_elem = hxs.select('//div[@class="price"]/p[@class="sale"]/strong/sup')
            ## [u'<sup class="dollars">$</sup>34', u'<sup class="cents">.88</sup>']
            if (cur_price_dollars_elem.extract() > 0):
                foo = cur_price_dollars_elem.extract()[0]
                print "Foo: " + foo
                index_ = foo.rindex('>')
                print "Index: " + str(index_)
                dollar_ = foo[index_+1:len(foo)]
                cur_price_dollars = dollar_
                print "Cur_price: " + cur_price_dollars
            cur_price_cents_elem = hxs.select('//div[@class="price"]/p[@class="sale"]/strong/sup/text()')
            if len(cur_price_cents_elem.extract()) > 1:
                cents = cur_price_cents_elem.extract()[1]
                cur_price_dollars += cents
                print "CURRENT DOLLAR AMOUNT: OVERALL: " + cur_price_dollars
        cur_price = float(cur_price_dollars)
        
        old_price_elem_dollar = hxs.select('//div[@class="price"]/p[@class="was"]/text()')
        old_price_dollar = cur_price
        if len(old_price_elem_dollar) > 0:
            old_price_dollar = old_price_elem_dollar.extract()[1]
            cents_elem = hxs.select('//div[@class="price"]/p[@class="was"]/sup[@class="cents"]/text()')
            if cents_elem.extract() > 0:
                cents = cents_elem.extract()[0]
                old_price_dollar += cents
            sale_price = cur_price
            price = old_price_dollar
        else:
            price = cur_price
            sale_price = price
    
        return (item_id, price, sale_price)
        
        
        
        
