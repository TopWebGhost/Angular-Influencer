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

class JcrewSpider(CrawlSpider):
    name = "jcrew"

    store_name = "J.Crew"
    HOME = "/Users/atulsingh/Documents/workspace2/"
    # stats
    all_items_scraped = set()
    invalid_links = 0

    count_scraped = 0
    urls_scraped = set()
    items_to_scrape = []
    items_scraped = []
    count = 0


    insert_date = datetime.date.today()

    handle_httpstatus_list = [302]
    already_added_urls = []
    # prod url -> ss link url
    start_urls = []
    allowed_domains = ['jcrew.com',]

    new_arrivals = 0

    def __init__(self, *a, **kw):
        super(JcrewSpider, self).__init__(*a, **kw)

        self.start_urls.append("http://www.jcrew.com/index.jsp")
        #self.start_urls.append("http:///womens_category/suiting.jsp")
        if kw.get('new_arrivals'):
            self.new_arrivals = int(kw.get('new_arrivals'))

        #self.start_urls.append('http://www.jcrew.com/sale.jsp')
        #self.start_urls.append('http://www.jcrew.com/womens_category/outerwear/wool.jsp?navLoc=left_nav')


    def parse(self, response):
        url = response.url
        print "\n----Parse:: " + str(self.count) + " URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        new_urls = []
        # for home page. StoreView for Abercrombie & Gillihicks, HomePage for Hollister
        if 'index.jsp' in url:
            print "USEFUL URL " + str(url)
            self.add_primary_nav_links(response, new_urls)

        # these contain category pages. they have links to other category pages and links to product pages
        #if response.request.meta.get('redirect_urls'):
        #    print "Redirected from " + str(response.request.meta.get('redirect_urls')[0])
        self.add_category_links(response, new_urls)
        self.add_product_links(response, new_urls)
        if 'navLoc=left_nav' in url:
            u = url.replace('navLoc=left_nav', 'iNextCategory=-1')
            new_urls.append(u)
            #print "\n---SCRAPING PAGE---\n"

        # these are product pages
        if 'PRDOVR' in url:
            valid_prod, product = self.parse_jcrew(response)

        self.count += 1

        sleep(1)
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
        primary_navs_path = hxs.select('//ul[@id="globalnav"]/li/a/@href').extract()

        for p in primary_navs_path:
            url_to_follow =  p
            if not (url_to_follow in self.already_added_urls):
                print "Category URL: " + str(url_to_follow)
                new_urls.append(url_to_follow)

    def add_category_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        category_nav_path_1 = hxs.select('//p[@class="leftNavCat"]/a/@href').extract()

        category_nav_path_2 = hxs.select('//a[@name="saleLeftNav"]/@href').extract()

        category_nav_path_3 = hxs.select('//td[@class="searchCategoriesFound"]/h2/a/@href').extract()

        category_nav_path_4 = hxs.select('//ul[@class="leftnav_sub_sub"]/li/h2/a/@href').extract()

        category_nav_path = category_nav_path_1 + category_nav_path_2 + category_nav_path_3 + category_nav_path_4


        for p in category_nav_path:
            url_to_follow = p
            if not (url_to_follow in self.already_added_urls):
                if self.new_arrivals == 0 or 'NewArrivals' in url_to_follow:

                    print "Category URL: " + str(url_to_follow)
                    new_urls.append(url_to_follow)
                    print "Category URL: " + str(url_to_follow + '?iNextCategory=-1')
                    new_urls.append(url_to_follow  + '?iNextCategory=-1')

    def get_id_from_url(self, url):

        import re

        pattern = 'PRDOVR~[\d]+'
        pattern_comp = re.compile(pattern)
        results = pattern_comp.findall(url)
        vals = []

        if len(results) > 0:
            for res in results:
                vals.append(res.strip('PRDOVR~'))

        return vals

    def add_product_links(self, response, new_urls):
        hxs = HtmlXPathSelector(response)

        product_path_1 = hxs.select('//td[@class="arrayImg"]/a/@href').extract()

        product_path = product_path_1

        for p in product_path:
            url_to_follow = p
            print "Product URL: Checking: " + str(url_to_follow)
            if not (url_to_follow in self.already_added_urls):
                if self.new_arrivals == 0 or 'NewArrivals' in url_to_follow:

                    print "Product URL: : Not yet visited: " + str(url_to_follow)
                    prod_ids = self.get_id_from_url(url_to_follow)
                    print "Length of result: " + str(len(prod_ids)) + " ProdID: " + str(prod_ids)
                    #assert len(prod_ids) < 2
                    if len(prod_ids) == 1:
                        pid = prod_ids[0]
                        prod = ProductModel.objects.filter(brand__name = self.store_name, c_idx = pid)
                        if len(prod) > 0:
                            print "EXISTS. We found " + str(len(prod)) + " first: " + str(prod[0])
                        else:
                            print "IS A NEW ITEM. ID " + str(pid)
                            new_urls.append(url_to_follow)
                    else:
                        print "ADDING. ID GOT: " + str(prod_ids)  + " URL: " + str(url_to_follow)
                        new_urls.append(url_to_follow)



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
        if len(desc) > 0:
            desc_content = desc.extract()[0]
        else:
            desc_content = ''
        logging.critical("Description: " + str(desc_content.encode('utf-8')))


        keywords = hxs.select('//meta[@name="keywords"]/@content').extract()
        keywords_content = keywords[0]
        logging.critical("Keywords: ")
        logging.critical(keywords_content)

        prod_desc = desc_content + "\n" + keywords_content
        print "Length of prod_desc " + str(len(prod_desc))

        promo_str = ''

        product, created_new = self._create_product_item(item_name, item_id_, str(prod_url), price_, \
                                            sale_price_, gender, str(prod_img_url[0]), promo_str, prod_desc)
        print "gender " + str(product.gender)
        if created_new:
            new_cat = simple_product_categorization(product)
            product.cat1 = new_cat["cat1"]
            product.cat2 = new_cat["cat2"]
            product.cat3 = new_cat["cat3"]
            product.save()


        error = hxs.select('//span[@class="select-error"]/text()')
        if len(error) > 0:
            logging.critical("Error: " + (error.extract()[0]).encode('utf-8'))
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

        b = Brands.objects.get(name = self.store_name)

        existing_item = ProductModel.objects.filter(brand = b).filter(c_idx = prod_id)
        print existing_item
        if len(existing_item) > 0:
            print "Item " + str(existing_item[0]) + " EXISTS. Not creating new one. Returning...."
            #existing_item[0].insert_date = self.insert_date
            #existing_item[0].save()
            return (existing_item[0], False)

        logging.critical("CREATE_PRODUCT OBJ: foreign key " + str(b))
        item = ProductModel(brand = b,
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


    def _find_price(self, hxs):
        price = 0
        sale_price = 0
        item_id = -1



        item_id_path = hxs.select('//span[@class="itemid-single"]/text()').extract()
        if len(item_id_path) > 0:
            item_id_data = item_id_path[0]
            if len(item_id_data) > 1:
                item_id = item_id_data.split()[1]


        return (item_id, price, sale_price)




