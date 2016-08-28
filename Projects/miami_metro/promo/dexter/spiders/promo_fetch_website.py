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
from promo.dexter.items import Category, ProductItem, ColorSizeItem, CategoryItem
from debra.models import Brands, ProductModel, Items, PromoRawText, Promoinfo
from laguerta import popmail
import os, errno
from time import sleep
import urllib
from django.utils.encoding import smart_str, smart_unicode

# For parsing promo text
import HTMLParser
from BeautifulSoup import BeautifulSoup

'''
    Signal handling
'''
from scrapy.xlib.pydispatch import dispatcher
from scrapy import signals


logger = logging.getLogger('miami_metro')


class PromoFetchWebsiteSpider(CrawlSpider):
    name = "promofetchwebsite"
    #HOME = "/Users/atulsingh/Documents/workspace2/"
    HOME = "/home/ubuntu/"
    # stats
    
    time = datetime.datetime.now()
    
    handle_httpstatus_list = [302]
   
    today = datetime.date.today() #(2012, 1, 31)
    
    start_urls = []
    
    def __init__(self, *a, **kw):
        super(PromoFetchWebsiteSpider, self).__init__(*a, **kw)
        brands = Brands.objects.filter(promo_discovery_support=True)
        for brand in brands:
            self.start_urls.append(brand.start_url)
        
            
        self.start_urls.append('http://www.express.com/deals-steals-306/control/show/80/index.cat')
        self.start_urls.append('http://www.express.com/deals-steals-252/control/show/12/index.cat')
        
        #special URLs
        #Not using them right now. Reasons:
        #  - 1. BR didn't update the promos until mid-afternoon.
        #  - 2. Need to understand the syntax. Get the date out to figure out how long they are valid.
        #  - 3. Much easier to just look at the email
        self.start_urls.append("http://www.gap-coupons.com/")
        self.start_urls.append("http://www.banana-republic-coupons.com/")
        self.start_urls.append("http://www.old-navy-coupons.com/")
        self.start_urls.append("http://www.piperlime-coupons.com/")
        self.start_urls.append("http://www.athleta-coupons.com/")
    

        self.start_urls.append("http://www.amazon.com/clothing-accessories-men-women-kids/b/ref=sa_menu_apr?ie=UTF8&node=1036592")
        self.start_urls.append("http://www.amazon.com/shoes-men-women-kids-baby/b/ref=sa_menu_shoe?ie=UTF8&node=672123011")
        self.start_urls.append("http://www.amazon.com/Handbags-Accessories-Clothing/b/ref=sa_menu_bags?ie=UTF8&node=15743631")
        self.start_urls.append("http://www.amazon.com/Handbags-Designer-Sunglasses-iPod-Case/b/ref=sa_menu_cla?ie=UTF8&node=1036700")
        self.start_urls.append("http://www.amazon.com/jewelry-watches-engagement-rings-diamonds/b/ref=sa_menu_jewelry?ie=UTF8&node=3367581")
        self.start_urls.append("http://www.amazon.com/Watches-Mens-Womens-Kids-Accessories/b/ref=sa_menu_watches?ie=UTF8&node=377110011")

    def parse(self, response):

        url = response.url
        print "\n----Parse URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        #print str(response.body)
        
        '''if 'bananarepublic' in url or 'banana-republic-coupons' in url:
            self._process_br(response)

        if 'www.gap.com' in url or 'gap-coupons' in url:
            self._process_gap(response)
            
        if 'oldnavy' in url or 'old-navy-coupons' in url:
            self._process_old_navy(response)
        
        if 'athleta' in url or 'athleta-coupons' in url:
            self._process_athleta(response)
        
        if 'piperlime' in url or 'piperlime-coupons' in url:
            self._process_piperlime(response)
        
        if 'abercrombie' in url:
            self._extract_promo_text_from_homepage(response, 'Abercrombie & Fitch')
        if 'hollister' in url:
            self._extract_promo_text_from_homepage(response, 'Hollister')
        if 'gillyhicks' in url:
            self._extract_promo_text_from_homepage(response, 'Gilly Hicks')
        
        if 'anntaylor' in url:
            print "Got ann taylor"
            self._extract_promo_text_from_homepage(response, 'Ann Taylor')
        if 'loft' in url:
            self._extract_promo_text_from_homepage(response, 'Loft')
        if 'express' in url:
            self._process_express(response)
        '''
        
        if 'jcrew' in url:
            self._process_jcrew(response)
        
        
            
        
        if 'ae.com' in url:
            store_name =  "American Eagle Outfitters"
            st = Brands.objects.get(name = store_name)
            self._extract_promo_text_from_homepage(response, store_name)
            hxs = HtmlXPathSelector(response)
            promo_body = hxs.select('//div[@class="staticPromoBody"]/div/div[@class="mainMessage"]/text()').extract()
            promo_sub_msg = hxs.select('//div[@class="staticPromoBody"]/div/div[@class="subMessage"]/text()').extract()
            raw_text = ''
            if len(promo_body) > 0:
                for p in promo_body:
                    popmail._common_work(store_name, self.today, self.time, 'ae.com', ['code ',], smart_str(p).lower())

                raw_text = ''.join(promo_body)
            if len(promo_sub_msg) > 0:
                for p in promo_sub_msg:
                    popmail._common_work(store_name, self.today, self.time, 'ae.com', ['code ',], smart_str(p).lower())

                raw_text += ''.join(promo_body)

            if len(raw_text) > 1:
                
                pro = PromoRawText.objects.get_or_create(store = st, insert_date = self.today, raw_text = raw_text)
                print pro

            fs_threshold = hxs.select('//span[@class="fsThreshold"]/span/text()').extract()
            raw_txt = ''

            if len(fs_threshold) > 0:
                raw_text = ''.join(fs_threshold)
                pro = PromoRawText.objects.get_or_create(store = st, insert_date = self.today, raw_text = raw_text)
                print pro

        
        all_brands = Brands.objects.filter(promo_discovery_support = True)
        store_name = None
        for b in all_brands:
            if b.start_url in url:
                print "Found domain %s in url %s " % (b.start_url, url)
                store_name = b.name
                break
        if store_name:
            self._extract_promo_text_from_homepage(response, store_name)

    def _common_promo_code_work(self, store_name, sender, code, promo_path):
        target_strings = []
        target_strings.append(code)
        for promo_text in promo_path:
            logger.info(smart_str(promo_text))
            popmail._common_work(store_name, self.today, self.time, sender, target_strings, smart_str(promo_text).lower())
    
    def common_promo_text_work(self, store_name, promo_text_arr):
        #return
        date = self.time
        for promo_text in set(promo_text_arr):
            print "Promo_text: %s" % smart_str(promo_text)
            #continue
            brand = Brands.objects.get(name = store_name)
            logger.info('Inserting in DB: ' + smart_str(brand.name))
            promo = PromoRawText.objects.filter(store = brand).filter(insert_date = date).filter(raw_text = promo_text)
            print smart_str(promo)
            if len(promo) > 0:
                logger.info('Inserting in DB: ' + "Promo exists, not adding a duplicate.")
                continue
            logger.info('Inserting in DB: ' + "Creating new promo.")
            promo = PromoRawText()
            promo.store = brand
            promo.insert_date = date
            promo.raw_text = promo_text
            promo.data_source = 'Website'
            promo.save()
            print smart_str(promo)
        
    def _extract_gap_promo_text_from_homepage(self, store_name, response, html_parser):
        hxs = HtmlXPathSelector(response)
        promo_arr = []
        search_tag1 = '//div[@id="globalBannerText"]/a'
        promo_path = hxs.select(search_tag1).extract()
        if len(promo_path) > 0:
            promo_path_res = ''.join(promo_path)
            promo_arr.append(promo_path_res)
        return promo_arr

    '''
        JCrew-specific function to scrape promo text from homepage
    '''
    def _extract_jcrew_promo_text_from_homepage(self, store_name, response, html_parser):
        hxs = HtmlXPathSelector(response)
        promo_arr = []
        search_tag1 = '//span[@id="globalpromo_text"]/text()'
        promo_path = hxs.select(search_tag1).extract()
        if len(promo_path) > 0:
            promo_path_res = ''.join(promo_path)
            promo_arr.append(promo_path_res)
        search_tag2 = '//div[@id="hdr-freeshipping"]/text()'
        promo_path = hxs.select(search_tag2).extract()
        if len(promo_path) > 0:
            promo_path_res = ''.join(promo_path)
            promo_arr.append(promo_path_res)
        

        promo_path = hxs.select('//div[@id="globalpromo"]/span/a/text()').extract()
        if len(promo_path) > 0:
            promo_path_res = ''.join(promo_path)
            print "HOLA: %s " % promo_path_res
            promo_arr.append(promo_path_res)

        if promo_arr:
            logger.info(' PROMO Text (' + search_tag1 + '/' + search_tag2 + ') for ' + store_name + ': ' + smart_str(promo_arr))
        
        return promo_arr
    
    def _extract_aber_promo_text_from_homepage(self, store_name, response, html_parser):
        hxs = HtmlXPathSelector(response)
        promo_arr = []
        search_tag1 = '//div[@id="shortPromo"]/text()'
        promo_path = hxs.select(search_tag1).extract()
        if len(promo_path) > 0:
            promo_path_res = ''.join(promo_path)
            promo_arr.append(promo_path_res)

        if promo_arr:
            logger.info(' PROMO Text (' + search_tag1 + ') for ' + store_name + ': ' + smart_str(promo_arr))
        
        return promo_arr

    '''
        For some stores, we need to look for store-specific HTML tags 
        or go to store-specific webpages where promo-info is available 
        in addition to the homepage. 
        
        This function is a wrapper around such store-specific functions. 
    '''
    def _extract_store_specific_promo_text_from_homepage(self, store_name, response, html_parser):
        if store_name == 'J.Crew':
            return self._extract_jcrew_promo_text_from_homepage(store_name, response, html_parser)
        if store_name == "Abercrombie & Fitch" or store_name == "Hollister" or store_name == "Gilly Hicks":
            return self._extract_aber_promo_text_from_homepage(store_name, response, html_parser)
        if store_name == "Gap":
            return self._extract_gap_promo_text_from_homepage(store_name, response, html_parser)
            
        return []
    
    '''
        Underlying logic here is:
            find all HTML lines corresponding to the argument 'tag'
            for each HTML line, 
                if one of the keywords exists in the text corresponding to the 'alt' attribute
                    identify this line as potential promo text
                    filter out lines that do not contain money-saving promotions
                    filter out exact match duplicates using 'set' function 
    '''
    def _extract_tag_info_from_homepage(self, store_name, tag, soup, html_parser, response):
        hxs = HtmlXPathSelector(response)
        promo_arr = []
        #all_tag_info = soup.findAll(tag)
        search_str = "//%s/@alt" % tag
        all_tag_info = hxs.select(search_str).extract()
        print "Tag " + tag
        for tag_info in all_tag_info:
            try:
                alt_info = smart_unicode(tag_info)#smart_unicode(html_parser.unescape(tag_info['alt']))
                print '%s' % smart_str(alt_info)
            except KeyError:
                print "Problem in decoding...."
                pass
            else:
                if alt_info: 
                    alt_info_lower = alt_info.lower()
                    print "alt_info_lower %s " % smart_str(alt_info_lower)
                    if 'sale' in alt_info_lower or 'off' in alt_info_lower or 'free' in alt_info_lower or 'for $' in alt_info_lower:
                        potential_promo_text = alt_info_lower
                        print "potential_promo_text %s " % smart_str(potential_promo_text)
                        ''' This function filters out lines that are not directly money-saving-promo-related '''
                        if '$' in potential_promo_text or '%' in potential_promo_text or \
                            'free shipping' in potential_promo_text:
                            promo_arr.append(potential_promo_text)
        
        if promo_arr:
            logger.info(' PROMO Text (' + tag + ') for ' + store_name + ': ' + smart_str(promo_arr))
    
        return promo_arr
    
    '''
        This wrapper function extracts textual information from 
        store homepages (if and when available)
    '''
    def _extract_promo_text_from_homepage(self, response, store_name):
        soup = BeautifulSoup(response.body_as_unicode())
        hxs = HtmlXPathSelector(response)
        html_parser = HTMLParser.HTMLParser()
        promo_text_arr = []
        ''' First look for image 'alt' text '''
        promo_text_set = self._extract_tag_info_from_homepage(store_name, 'img', soup, html_parser, response)
        for promo_text in promo_text_set:
            promo_text_arr.append(promo_text)
        ''' Next look for area 'alt' text '''
        promo_text_set = self._extract_tag_info_from_homepage(store_name, 'area', soup, html_parser, response)
        for promo_text in promo_text_set:
            promo_text_arr.append(promo_text)
        ''' Finally look for info on a store-specific basis ''' 
        promo_text_set = self._extract_store_specific_promo_text_from_homepage(store_name, response, html_parser)
        for promo_text in promo_text_set:
            promo_text_arr.append(promo_text)
        
        ''' For express, we also look at "Deals & Steals" page'''
        promo_text_set = self._get_deals_and_steals_text(store_name, response)
        for promo_text in promo_text_set:
            promo_text_arr.append(promo_text)

        elems = hxs.select('//a/text()').extract()
        for el in elems:
            if 'off' in el.lower() or 'b1g1' in el.lower():
                promo_text_arr.append(el.lower())
        
        if promo_text_arr:
            logger.info(' Final PROMO Text for ' + store_name + ': ' + smart_str(set(promo_text_arr)))
            self.common_promo_text_work(store_name, promo_text_arr)

    def _get_deals_and_steals_text(self, store_name, response):
        hxs = HtmlXPathSelector(response)

        deals = hxs.select('//div[@id="glo-leftnav-container"]/ul/li/a/@title').extract()

        result = []
        if len(deals) > 0:
            if "deals-steals-306/control/show/80/index.cat" in response.url:
                gender = "women"
            else:
                gender = "men"
            for promo_text in deals:
                if "BOGO" in promo_text:
                    newer_promo = promo_text.replace('BOGO For', 'BUY 1, GET 1')
                    promo_text = newer_promo
                    newer_promo = promo_text.replace('BOGO for', 'BUY 1, GET 1')
                    promo_text = newer_promo
                    newer_promo = promo_text.replace('BOGO', 'BUY 1, GET 1')
                    promo_text = newer_promo
                    
                result.append(promo_text + " " + gender)
            logger.info("Deals found: ")

        return result
    
    def _store_promo_code_in_db(self, store_name, code, date):
        # store promo code if it exists
        brand = Brands.objects.get(name = store_name)
        logger.info(" Found promo code " + code.lower() + " for store " + store_name)
        promo = Promoinfo.objects.filter(store = brand).filter(code = code.lower()).filter(d = date)
        print promo
        if len(promo) > 0:
            print "Promo exists, not adding a duplicate."
            return
        
        logger.info(" Creating new Promoinfo entry for code " + code.lower())
        promo = Promoinfo()
        promo.store = brand
        promo.code = code.lower()
        promo.d = date
        promo.save()
        print promo

    
    
    '''
        This function extracts information from the coupon page 
        for stores in the Gap family. 
    '''
    def _extract_promo_text_from_couponpage(self, store_name, response):
        promo_text_arr = []
        promo_codes = []
        hxs = HtmlXPathSelector(response)
        posts = hxs.select('//div[@class="entry-content"]/p')
        if len(posts) > 0:
            #pick the top one only since it is the most recent
            p = posts[0]
            p_text_all_path = p.select('./text()').extract()
            if len(p_text_all_path) > 0:
                p_text_all = ''.join(p_text_all_path)
                #date_ = date_comp.findall(p_text_all)
                promo_text_arr.append(p_text_all)
                
                
        
        if promo_text_arr:
            logger.info(' Final PROMO Text: num %d Text: %s ' % ( len(promo_text_arr), smart_str(set(promo_text_arr))))
            self.common_promo_text_work(store_name, promo_text_arr)
            #self._common_promo_code_work(store_name, store_name, 'code ', promo_text_arr)
        
    def _process_br(self, response):
        store_name = "Banana Republic"
        if 'coupon' in response.url:
            self._extract_promo_text_from_couponpage(store_name, response)
        else:
            self._extract_promo_text_from_homepage(response, store_name)
            
    
    def _process_gap(self, response):
        store_name = "Gap"
        if 'coupon' in response.url:
            self._extract_promo_text_from_couponpage(store_name, response)
        else:
            self._extract_promo_text_from_homepage(response, store_name)
        
        
    def _process_old_navy(self, response):
        store_name = "Old Navy"
        if 'coupon' in response.url:
            self._extract_promo_text_from_couponpage(store_name, response)
        else:
            self._extract_promo_text_from_homepage(response, store_name)
        
    def _process_jcrew(self, response):
        hxs = HtmlXPathSelector(response)
        promo_path = hxs.select('//div[@id="globalpromo"]/span').extract()
        print promo_path
        if 'factory.jcrew.com' in response.url:
            store_name = "J.Crew Factory"
        else:
            store_name = "J.Crew"
        sender = store_name
        code = "code "
        self._common_promo_code_work(store_name, sender, code, promo_path)
        self._extract_promo_text_from_homepage(response, store_name)
        
    def _process_express(self, response):
        store_name = "Express"
        self._extract_promo_text_from_homepage(response, store_name)
        
    def _process_athleta(self, response):
        store_name = "Athleta"
        if 'coupon' in response.url:
            self._extract_promo_text_from_couponpage(store_name, response)
        else:
            self._extract_promo_text_from_homepage(response, store_name)
    
    def _process_piperlime(self, response):
        store_name = "Piperlime"
        if 'coupon' in response.url:
            self._extract_promo_text_from_couponpage(store_name, response)
        else:
            self._extract_promo_text_from_homepage(response, store_name)
        
