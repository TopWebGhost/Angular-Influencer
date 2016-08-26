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
import copy
import urllib
from debra.view_shelf import simple_product_categorization

#logging.basicConfig(format='%(message)s', level=logging.CRITICAL)

class ModClothSpider(CrawlSpider):
    name = "modcloth"

    store_name = "ModCloth"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    count_scraped = 0
    urls_scraped = set()
    items_to_scrape = []
    items_scraped = []
    count = 0
    insert_date = datetime.datetime.now()


    handle_httpstatus_list = [302]
    already_added_urls = []
    start_urls = []
    allowed_domains = ['modcloth.com',]

    new_arrivals = 0

    base_link = "http://www.modcloth.com"


    def __init__(self, *a, **kw):
        super(ModClothSpider, self).__init__(*a, **kw)
        # start with the home page

        self.brand = Brands.objects.get(name = self.store_name)
        print self.brand

#        self.start_urls.append("http://www.childrensplace.com/webapp/wcs/stores/servlet/product_10001_10001_-1_941788_617077_177878|27812_accessories|accessories_accessories")
#        self.start_urls.append("http://www.childrensplace.com/webapp/wcs/stores/servlet/product_10001_10001_-1_941119_678404_25851_babygirl_25851|72470")
        #self.start_urls.append('http://www.express.com/view-all-pants-704/control/show/80/index.cat')
        #self.start_urls.append('http://www.express.com/accessories-34/index.cat')

        self.start_urls.append("http://www.modcloth.com/")
        self.new_arrivals = int(kw.get('new_arrivals'))
        print self.new_arrivals
        self.prod_re = re.compile(self.base_link+'/shop/[a-zA-Z0-9_-]+/([a-zA-Z0-9_-]+)')
        self.cat_re = re.compile(self.base_link+'/shop/[a-zA-Z0-9_-]+')
        self.cat2_re = re.compile(self.base_link+'/[a-zA-Z0-9_-]+')


    def parse(self, response):
        self.count += 1


        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))

        if 'TCPSearch' in url:
            return

#        print "prod %s %s" % (self.prod_re.match(url), url)
#        print "cat %s %s" % (self.cat_re.match(url), url)
#        print "cat2 %s %s" % (self.cat2_re.match(url), url)

        #print str(response.body)
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister
        if url == 'http://www.modcloth.com/':
            print "USEFUL URL " + str(url)
            self.add_primary_nav_links(response, new_urls)
        elif self.prod_re.match(url):
            self.parse_product(response)
        elif self.cat_re.match(url) or self.cat2_re.match(url):
            self.add_product_links(response, new_urls)
#            self.add_category_links(response, new_urls) # this can all be done from the first section


        print "Total pages scraped " + str(self.count_scraped) + " Total URLS " + str(self.count) + \
              " Total invalid links " + str(self.invalid_links)

        for url_to_follow in new_urls:
            if not (url_to_follow in self.already_added_urls):
                prod = ProductModel.objects.filter(prod_url = url_to_follow)
                if len(prod) == 0:
                    self.already_added_urls.append(url_to_follow)
                    yield Request(url_to_follow, callback=self.parse)


    def add_primary_nav_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        print self.new_arrivals
        if self.new_arrivals == 0:
            primary_navs_path = hxs.select('//div[@id="header"]/ul[@id="top-nav"]/li[contains (@class, "top-nav-container")]/div[@class="top-nav-dropdown"]/div[@class="dropdown-categories"]/ul/li[@class="parent"]/a/@href').extract()
        else:
            primary_navs_path = hxs.select('//div[@id="header"]/ul[@id="top-nav"]/li[contains (@class, "new-arrivals")]/div[@class="top-nav-dropdown"]/div[@class="dropdown-categories"]/ul[not(@class="shop-by-column")]/li[@class="parent"]/a/@href').extract()

        for p in primary_navs_path:
            url_to_follow = self.base_link+p+'?per_page=300'
            if not (url_to_follow in self.already_added_urls):
                print "Category URLa: " + str(url_to_follow)
                new_urls.append(url_to_follow)

        if self.new_arrivals == 0:
            primary_navs_path = hxs.select('//div[@id="header"]/ul[@id="top-nav"]/li[contains (@class, "top-nav-container")]/div[@class="top-nav-dropdown"]/div[@class="dropdown-categories"]/ul/li[@class="parent"]/ul/li/a/@href').extract()

            for p in primary_navs_path:
                url_to_follow = self.base_link+p+'?per_page=300'
                if not (url_to_follow in self.already_added_urls):
                    print "Category URLb: " + str(url_to_follow)
                    new_urls.append(url_to_follow)

    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        category_nav_path = hxs.select('//div[@id="section_nav"]//h3/a/@href').extract()
        for p in category_nav_path:
            url_to_follow = self.base_link+p
            if not (url_to_follow in self.already_added_urls):
                print "Category URLb: " + str(url_to_follow)
                new_urls.append(url_to_follow)

        category_nav_path = hxs.select('//div[@id="section_nav"]//ul[@class="outfits_nav"]/li/a/@href').extract()
        for p in category_nav_path:
            if 'javascript' in p:
                # javascript:refine('4294967273');
                continue

            url_to_follow = self.base_link+p
            if not (url_to_follow in self.already_added_urls):
                print "Category URLc: " + str(url_to_follow)
                new_urls.append(url_to_follow)


    # product_10001_10001_-1_935936_672321_27151|
    def get_id_from_url(self, url):
        results = self.prod_re.findall(url)

        if len(results) > 0:
            result = results[0]
            if result[-1] == "_":
                return result[:-1]
            return result

        return None

    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        product_path = hxs.select('//div[@id="main_content"]/div[@id="product_category_container"]/ul[@class="product_list"]/li/a[@href]/@href').extract()
#
#        product_path_2 = hxs.select('//div[contains (@class, "cat-thu-row")]/div/div/a/@href').extract()
#
#        product_path_3 = hxs.select('//div[@id="cat-ens-prod-item"]/a/@href').extract()
#
#        product_path_4 = hxs.select('//div[contains (@class, "cat-thu-product")]/div/a/@href').extract()
#
#        # search for view-all links on the category pages
#        product_path_5 = hxs.select('//td[contains (@class, "cat-thu-but-view-all")]/a/@href').extract()

#        product_path = product_path_1 + product_path_2 + product_path_3 + product_path_4 + product_path_5

        for p in product_path:
            url_to_follow = self.base_link + p
#            print "Product URL: Checking: " + str(url_to_follow)
            if not (url_to_follow in self.already_added_urls):
                print "Product URL: Not yet visited: " + str(url_to_follow),
                prod_id = self.get_id_from_url(url_to_follow)
                print "ProdID: " + str(prod_id)
                #assert len(prod_ids) < 2

                if prod_id:
                    prod = ProductModel.objects.filter(brand__name = self.store_name, c_idx = prod_id)
                    if len(prod) > 0:
                        print "EXISTS. We found " + str(len(prod)) + " first: " + str(prod[0])
                    else:
#                        print "IS A NEW ITEM. ID " + str(prod_id)
                        new_urls.append(url_to_follow)
#
#                else:
#                    new_urls.append(url_to_follow)


    def parse_product(self, response):
        print "parse_product %s" % response

        #self.check_shelfit_validity(response)
        #return
        hxs = HtmlXPathSelector(response)

        # find name of item
        item_name_path = hxs.select('//div[contains(@class,"product-detail-page")]/div[@id="product-info-container"]/h1[@id="product-name"]/text()')
        if len(item_name_path) == 0:
            self.invalid_links += 1
            return (False, None)
        item_name = item_name_path.extract()
        logging.critical("Name: " + str(item_name))

        self.count_scraped += 1


        '''
        PLAYING NICE: sleeping for 1min after crawling every 100 pages
        '''
#        if self.count_scraped % 100 == 0:
#            sleep(60) # sleep for 1 mins for express


        prod_url = response.url
        logging.critical("PRODUCT URL:" + str(prod_url) + " TITLE " + str(item_name) + " TOTAL SO FAR " + str(self.count_scraped))

        # find gender
        gender = 'Nil'
#        logging.critical("Gender: " + gender)

        '''
        TODO: if same page has multiple items, our logic will not work.
        So, leaving it for future.
        '''
#        if len(item_name) == 0:
#            logging.critical("DIDN'T FIND TITLE AT NORMAL PLACE, MUST BE SUIT. RETURNING." + str(prod_url))
#            print item_name_path
#            print "Size of response " + str(len(str(response)))
#            print str(response)
#            return (False, None)

        # find price and sale price
        item_id_, price_, sale_price_ = self._find_price(hxs, prod_url)

#        print item_id_
#        return

        if item_id_ in self.all_items_scraped:
            print "RETURNING since we have already scraped " + str(item_id_)

        self.all_items_scraped.add(item_id_)

        logging.critical("ITEM_ID " + str(item_id_) + " PRICE " + str(price_) + " SALE PRICE " + str(sale_price_))

        # extract image URL
        # <meta content="http://www.childrensplace.com/www/b/TCP/images/cloudzoom/p/136532_p.jpg" property="og:image">
        prod_img_path = hxs.select('//div[@id="product_main_image"]/a[@id="zoomable"]/img[@id="big_image"]/@src')
        prod_img_url = str(prod_img_path.extract()[0])
#        prod_img_url = prod_img_str[28: len(prod_img_str) - 2]
        logging.critical("Image URL: " + str(prod_img_url))


        # find description and keywords: these will be useful in categorization
#        <div id="tab-content">
#          <dl class="tabs">
#            <dt id="tab_description" class="tab_here tab_here" width="91" style="display: block; left: 0px;">Description</dt>
#            <dd style="display: block;">
#              <p>Rev up his look with this cute style!</p>

#        desc = hxs.select('//div[@id="tab-content"]/dl[@class="tabs"]/dd[0]/p[0]/text()').extract()
        desc = hxs.select('//meta[@property="og:description"]/@content').extract()
        logging.critical("Description: ")
        logging.critical(desc)
        prod_desc = desc[0]

        # promo text
        promo_str = 'Nil'
#        promo_path = hxs.select('//span[@class="cat-pro-promo-text"]//font/text()').extract()
#        promo_str = str(promo_path)
#        logging.critical("Promotion: ")
#        logging.critical(promo_str)



        product, created_new = self._create_product_item(item_name[0], item_id_, str(prod_url), price_, \
                                            sale_price_, gender, str(prod_img_url), promo_str, prod_desc)


        if (not created_new):
            return (False, product)


#    <div id="breadcrumbs">
#        <ul>
#            <li>
#                <a href="http://www.modcloth.com/">ModCloth</a> // 0
#                <span></span>
#            </li>
#            <li>
#                <a href="/shop/clothing">Clothing</a> // 1
#                <span></span>
#            </li>
#            <li>
#                <a href="/shop/outerwear">Outerwear</a> // 2
#                <span></span>
#            </li>
#            <li>
#                <a href="/shop/coats">Coats</a> // 3
#                <span></span>
#            </li>

        if created_new:
            new_cat = simple_product_categorization(product)
            product.cat1 = new_cat["cat1"]
            product.cat2 = new_cat["cat2"]
            product.cat3 = new_cat["cat3"]
            product.save()


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



    def avoid_redirection(self, request):
        request.meta.update(dont_redirect=True)
        #request.meta.update(dont_filter=True)
        return request


    def _create_product_item(self, name, prod_id, prod_url, price, saleprice, gender, img_url, promo_text, prod_desc):
        from django.core.exceptions import ObjectDoesNotExist

        existing_item = ProductModel.objects.filter(brand = self.brand).filter(c_idx = prod_id)
        print existing_item
        if len(existing_item) > 0:
            print "Item " + str(existing_item[0]) + " EXISTS. Not creating new one. Returning...."
            return (existing_item[0], False)

        logging.critical("CREATE_PRODUCT OBJ: foreign key " + str(self.brand))
        item = ProductModel(brand = self.brand,
                            c_idx = prod_id,
                            name = name,
                            prod_url = prod_url,
                            price = price,
                            saleprice = saleprice,
                            promo_text = promo_text,
                            gender = gender,
                            img_url = img_url,
                            description = prod_desc,
                            insert_date = self.insert_date,)

        #print item
        item.save()
        print "CREATING NEW PRODUCT MODEL OBJ"
        #return (item.save(), True)
        return (item, True)


    def _find_price(self, hxs, url):
        print "CALCULATING PRICE: " + str(url)
        #item_id = self.find_itemid_in_url(url)

        item_id = self.get_id_from_url(url)
        '''
        ind1 = hxs.response.body.index('input name="productId"')
        print ind1
        assert ind1 > 0
        res1 = hxs.response.body[ind1:]
        ind2 = res1.index('value=')
        ind3 = res1.index('/>')
        final_str = res1[ind2 + 7: ind3-1]
        print "INDEX2 " + str(ind2) + " INDEX3 " + str(ind3)
        item_id = final_str
        print "ITEM_ID " + str(item_id)
        '''
        price_path = hxs.select('//div[@id="storefront-products-details-transactional-box"]/h3[@id="product-price"]/span[@itemprop="price"]/text()')
        _list = price_path.extract()
        logging.critical(_list)

        '''
        Some items have their prices given in a range: $30-$45. The price can be a function of
        size or style. We currently only store the minimal size.
        '''

        price = 0
        sale_price = 0
        for pr in _list:
            try:
                newPrice = float(re.sub(r'[^\d.]+', '', pr))

                if price == 0:
                    price = newPrice
                else:
                    if newPrice > price:
                        price = newPrice

                if sale_price == 0:
                    sale_price = newPrice
                else:
                    if newPrice < sale_price:
                        salePrice = newPrice

            except:
                pass

#        if '-' in _list[0]:
#            loc = _list[0].find('-')
#            new_ = _list[0][0:loc]
#            price = float(new_.strip('$').replace('\n', '').replace('\t', ''))
#            #print "Price: " + str(price) + " orig " + str(_list[0])
#            #raise SystemExit
#        else:
#            price = float(_list[0].strip('$').replace('\n', '').replace('\t', ''))
#
#        sale_price = price
#        if len(_list) > 1:
#            if '-' in _list[1]:
#                loc = _list[1].find('-')
#                new_ = _list[1][0:loc]
#                sale_price = float(new_.strip('$').replace('\n', '').replace('\t', ''))
#            else:
#                sale_price = float(_list[1].strip('$').replace('\n','').replace('\t', ''))

        return (item_id, price, sale_price)




