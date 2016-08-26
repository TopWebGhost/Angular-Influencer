import re, datetime, logging, commands, hashlib, os, errno, urllib

from scrapy.spider import BaseSpider
from scrapy.contrib.spiders import CrawlSpider, Rule
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from scrapy.selector import HtmlXPathSelector
from scrapy.item import Item
from scrapy.http import Request
from scrapy.exceptions import CloseSpider
from scrapy.utils.response import get_base_url
from harry.dexter.items import Category, ProductItem, ColorSizeItem, CategoryItem, StoreCategoryItem
from debra.models import Brands, ProductModel, Items, PromoRawText, Promoinfo, StoreSpecificItemCategory
from laguerta import popmail
from time import sleep
from django.utils.encoding import smart_str, smart_unicode
from django.core.exceptions import ObjectDoesNotExist

# For parsing text from website
import HTMLParser
from BeautifulSoup import BeautifulSoup

logger = logging.getLogger('miami_metro')

def calculate_digest(store, gender, age_group, category_name):
    val_str = smart_unicode(store) + smart_unicode(gender) + smart_unicode(age_group) + smart_unicode(category_name)
    m = hashlib.md5()
    m.update(smart_str(val_str))
    return m.hexdigest()        


class PromoFetchWebsiteSpider(CrawlSpider):
    name = "categoryfetch"
    start_urls = []
    
    def __init__(self, *a, **kw):
        super(PromoFetchWebsiteSpider, self).__init__(*a, **kw)
        self._initialize_start_urls()

    def _initialize_start_urls(self):
        brands = Brands.objects.all()
        for brand in brands:
            brand_name = brand.name
            brand_domain_name = brand.domain_name
            #if brand_domain_name != "Nil" and (brand_name == 'Express' or brand_name == 'Abercrombie & Fitch' or\
            #                                   brand_name == 'J.Crew' or self._gap_family_brand(brand_name) or\
            #                                   brand_name == 'New York & Company'):                           
            #if brand_domain_name != "Nil" and (brand_name == 'New York & Company' or self._gap_family_brand(brand_name)):
            if brand_domain_name != "Nil" and (brand_name == 'Abercrombie & Fitch'):
                if self._gap_family_brand(brand_name):
                    if brand_domain_name == 'gap':
                        url = "http://www." + brand_domain_name + ".com/"
                    else:
                        url = "http://" + brand_domain_name + ".gap.com/"
                else:
                    url = "http://www." + brand_domain_name + ".com/"
                
                logger.info(" Adding " + url + " to crawl...")
                self.start_urls.append(url)
                
    def _gap_family_brand(self, brand_name):
        if brand_name == 'Banana Republic' or brand_name == 'Gap' or \
            brand_name == 'Old Navy' or brand_name == 'Athleta' or brand_name == 'Piperlime':
            return True
        else:
            return False
    
    # checks if tok is present in sub
    def _contains(self, sub, tok):
        index = sub.find(tok)
        if index >= 0:
            return True
        else:
            return False
    
    '''
        Underlying logic:
        - find all top-level divisions
        - follow each, and find the categories listed on the left-side
        - follow link to each category, and find subcategories listed
        - populate database with this information
    '''
    def parse(self, response):
        url = response.url
        print "\n----Parse URL: " + str(url) + " Size of response: " + str(len(str(response.body)))
        
        soup = BeautifulSoup(response.body_as_unicode())
        
        if self._contains(str(url), 'www.gap.com'):
            return self._process_gap(response, soup)
        elif 'oldnavy' in url:
            return self._process_oldnavy(response, soup)
        elif 'bananarepublic' in url:
            return self._process_br(response, soup)
        elif 'athleta' in url:
            return self._process_athleta(response, soup)
        elif 'piperlime' in url:
            return self._process_piperlime(response, soup)
        elif 'nyandcompany' in url:
            return self._process_nyandcompany(response, soup)
        elif 'jcrew' in url:
            return self._process_jcrew(response, soup)
        elif 'express' in url:
            return self._process_express(response, soup)
        elif 'abercrombie' in url:
            return self._process_abercrombie(response, soup)
            
        return
        
    def _process_abercrombie(self, response, soup):
        store_name = "Abercrombie & Fitch"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)
    
    def _process_express(self, response, soup):
        store_name = "Express"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)
    
    def _process_jcrew(self, response, soup):
        store_name = "J.Crew"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)
    
    def _process_gap(self, response, soup):
        store_name = "Gap"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)
    
    def _process_br(self, response, soup):
        store_name = "Banana Republic"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)
        
    def _process_oldnavy(self, response, soup):
        store_name = "Old Navy"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)
    
    def _process_athleta(self, response, soup):
        store_name = "Athleta"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)

    def _process_piperlime(self, response, soup):
        store_name = "Piperlime"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)

    def _process_nyandcompany(self, response, soup):
        store_name = "New York & Company"
        base_url = get_base_url(response)
        return self._get_divisions(response, soup, store_name, base_url)
    
        
    def _get_divisions(self, response, soup, store_name, base_url):
        print "Inside get_divisions"
        
        if store_name == 'Piperlime':
            all_division_info = soup.findAll("a", { "class": "notSelected" })
            for division_info in all_division_info:
                try:
                    follow_url = base_url + division_info['href']
                    main_division = division_info.text.lower()
                except AttributeError:
                    print "AttributeError", division_info
                else:
                    gender_val, age_group_val = self._follow_division_urls(main_division, store_name)
                    if gender_val and age_group_val:
                        yield Request(follow_url, self.handle_category_list, 
                                      meta={'store': store_name, 'gender': gender_val, 'age_group': age_group_val, 'baseurl': base_url})
        
        elif store_name == 'Abercrombie & Fitch':
            all_division_info = soup.find("div", { "id": "primary-nav" }).find('ul').findAll('li')
            base_url = base_url.split('StoreView')[0]
            for division_info in all_division_info:
                try:
                    follow_url = base_url + division_info.a['href']
                    main_division = division_info.a.text.lower()
                except AttributeError:
                    print "AttributeError", division_info
                except TypeError:
                    print "TypeError", division_info
                else:
                    print main_division, follow_url
                    gender_val, age_group_val = self._follow_division_urls(main_division, store_name)
                    if gender_val and age_group_val:
                        yield Request(follow_url, self.handle_category_list, 
                                      meta={'store': store_name, 'gender': gender_val, 'age_group': age_group_val, 'baseurl': base_url})
            
        elif store_name == 'Express':
            all_division_info = soup.findAll("span", { "class": "glo-header-tab-span for-her-img" })
            all_division_info += soup.findAll('span', {'class': 'glo-header-tab-span for-him-img'})
            #print all_division_info
            base_url = base_url.split('/home.jsp')[0]
            for division_info in all_division_info:
                try:
                    follow_url = base_url + division_info.a['href']
                    main_division = division_info.a.text.lower()
                except AttributeError:
                    print "AttributeError", division_info
                else:
                    print follow_url, main_division
                    gender_val, age_group_val = self._follow_division_urls(main_division, store_name)
                    if gender_val and age_group_val:
                        yield Request(follow_url, self.handle_category_list, 
                                      meta={'store': store_name, 'gender': gender_val, 'age_group': age_group_val, 'baseurl': base_url})
                    
        
        elif store_name == 'New York & Company':
            all_division_info = soup.find("table", { "id": "topnav" }).findAll('a')
            base_url = base_url.split('/nyco/')[0]
            for division_info in all_division_info:
                try:
                    follow_url = base_url + division_info['href']
                    main_division = division_info.text.lower()
                except AttributeError:
                    print "AttributeError", division_info
                else:
                    gender_val, age_group_val = 'women', 'adult'
                    if gender_val and age_group_val:
                        yield Request(follow_url, self.handle_category_list, 
                                      meta={'store': store_name, 'gender': gender_val, 'age_group': age_group_val, 'baseurl': base_url})
        elif store_name == "J.Crew":
            all_division_info = soup.find("ul", { "id": "globalnav" }).findAll('li')
            for division_info in all_division_info:
                try:
                    follow_url = division_info.a['href']
                    main_division = division_info.a.text.lower()
                except AttributeError:
                    print "AttributeError", division_info
                else:
                    print follow_url, main_division
                    gender_val, age_group_val = self._follow_division_urls(main_division, store_name)
                    if gender_val and age_group_val:
                        yield Request(follow_url, self.handle_category_list, 
                                      meta={'store': store_name, 'gender': gender_val, 'age_group': age_group_val, 'baseurl': base_url})
                    
        else:
            all_division_info = soup.findAll("li", { "class": "division" })
            for division_info in all_division_info:
                try:
                    follow_url = base_url + division_info.a['href']
                    main_division = division_info.img['alt'].lower()
                except AttributeError:
                    print "AttributeError", division_info
                except TypeError:
                    print "TypeError", division_info, store_name
                else:    
                    gender_val, age_group_val = self._follow_division_urls(main_division, store_name)
                    if gender_val and age_group_val:
                        yield Request(follow_url, self.handle_category_list, 
                                      meta={'store': store_name, 'gender': gender_val, 'age_group': age_group_val, 'baseurl': base_url})
        
        yield
        
    def _follow_division_urls(self, main_division, store_name):
        print main_division, store_name
        gender_val = None
        age_group_val = None
        if (store_name == 'Athleta'):
            gender_val = 'women'
            age_group_val = 'adult'
        elif (store_name == 'Piperlime'):
            if 'women' in main_division or main_division == 'apparel' or main_division == 'shoes & accessories':
                gender_val = 'women'
                age_group_val = 'adult'
            elif main_division == "men":
                gender_val = 'men'
                age_group_val = 'adult'
        elif (store_name == 'J.Crew') or (store_name == 'Express') or (store_name == 'Abercrombie & Fitch'):
            if 'women' in main_division:
                gender_val = 'women'
                age_group_val = 'adult'
            elif main_division == "men" or main_division == "mens":
                gender_val = 'men'
                age_group_val = 'adult'
        else:
            if 'women' in main_division or main_division == 'body' or main_division == 'maternity':
                gender_val = 'women'
                age_group_val = 'adult'
            elif main_division == 'girls':
                gender_val = 'women'
                age_group_val = 'child'
            elif 'toddler girl' in main_division or 'infant girl' in main_division: 
                gender_val = 'women'
                age_group_val = 'baby'
            elif main_division == "men" or main_division == "men's big & tall":
                gender_val = 'men'
                age_group_val = 'adult'
            elif main_division == 'boys':
                gender_val = 'men'
                age_group_val = 'child'
            elif 'toddler boy' in main_division or 'infant boy' in main_division: 
                gender_val = 'men'
                age_group_val = 'baby'
        
        return gender_val, age_group_val
        
    
    def handle_category_list(self, response):
        soup = BeautifulSoup(response.body_as_unicode())
        html_parser = HTMLParser.HTMLParser()
        store_val = smart_unicode(response.meta['store'])
        gender_val = smart_unicode(response.meta['gender'])
        age_group_val = smart_unicode(response.meta['age_group'])
        baseurl_val = smart_unicode(response.meta['baseurl'])
        if store_val == "New York & Company":
            all_categories = soup.find("ul", { "id": "leftnav" }).findAll('li')
        elif store_val == "Abercrombie & Fitch":
            all_categories = soup.find("div", { "id": "category-nav" }).find('ul').findAll('li')
            baseurl_val = smart_unicode(response.meta['baseurl']).split('/webapp')[0]
        elif store_val == "Express":
            all_categories = soup.find("div", {"id": "glo-leftnav-container"}).findAll('span')
        elif store_val == "J.Crew":
            all_categories = soup.findAll("p", { "class": "leftNavCat" })
        else:
            all_categories = soup.findAll("li", { "class": "category" })    
        
        if store_val == "Piperlime":
            all_categories += soup.findAll("li", { "class": "category search" })
            all_categories += soup.findAll("li", { "class": "category search sale" })
            
        all_categories_href = []
        for category in all_categories:
            try:
                if store_val == "New York & Company":
                    category_name_val = smart_unicode(html_parser.unescape(category.a.span.text))
                elif (store_val == "Abercrombie & Fitch"): 
                    category_name_val = smart_unicode(html_parser.unescape(category.a.text))
                    if "A&F" in category_name_val:
                        category_name_val = category_name_val.replace(';', '')
                else:
                    category_name_val = smart_unicode(html_parser.unescape(category.a.text))
                
                if store_val == "J.Crew" or store_val == "Express":
                    follow_url = category.a['href']
                else:
                    follow_url = baseurl_val + category.a['href']
                
            except AttributeError:
               print "AttributeError", category
               continue
            else:
                print smart_str(category_name_val), follow_url
                idx = calculate_digest(store_val, gender_val, age_group_val, category_name_val)
                try:
                    existing_item = StoreSpecificItemCategory.objects.get(hash_val = idx)
                except ObjectDoesNotExist:
                    print "CAT: ", smart_str(category_name_val)
                    brand_obj = Brands.objects.get(name = store_val)
                    item = StoreCategoryItem(brand = brand_obj, 
                                             gender = gender_val, 
                                             age_group = age_group_val,
                                             categoryName = category_name_val,
                                             hash_val = idx)
                    item.save()
                    yield item
                 
                all_categories_href.append(follow_url)
                
                
        # NY&Company does not have sub-categories
        if not store_val == "New York & Company":
            for href in all_categories_href:
                #print baseurl_val, href
                yield Request(href, self.handle_subcategory_list, 
                              meta={'store': store_val, 'gender': gender_val, 'age_group': age_group_val})
        
    
    def handle_subcategory_list(self, response):
        soup = BeautifulSoup(response.body_as_unicode())
        html_parser = HTMLParser.HTMLParser()
        store_val = smart_unicode(response.meta['store'])
        gender_val = smart_unicode(response.meta['gender'])
        age_group_val = smart_unicode(response.meta['age_group'])
        if (store_val == "Piperlime"):
            all_subcategories = soup.findAll("li", { "class": "subcategory" })
            all_subcategories += soup.findAll("li", { "class": "subcategory search" })
            all_subcategories += soup.findAll("li", { "class": "subcategory search sale" })
        elif (store_val == "J.Crew"):
            all_subcategories = soup.findAll("h2", { "class": "header2" })
        elif (store_val == "Express"):
            all_subcategories = soup.find("ul", { "class": "sublink" }).findAll('li')
        elif (store_val == "Abercrombie & Fitch"):
            all_subcategories = soup.find("ul", { "class": "secondary" }).findAll('li')
        else:
            all_subcategories = soup.findAll("li", { "class": "subCategory" })
        #print "SUBC: ", response.url, store_val, gender_val, age_group_val
        for category in all_subcategories:
            try:
                category_name_val = smart_unicode(html_parser.unescape(category.a.text))
                if (store_val == "Abercrombie & Fitch") and "A&F" in category_name_val:
                    category_name_val = category_name_val.replace(';', '')
                
            except AttributeError:
               print "AttributeError", category
               continue
            else:
                print 'SUBC: ', category_name_val
                idx = calculate_digest(store_val, gender_val, age_group_val, category_name_val)
                try:
                    existing_item = StoreSpecificItemCategory.objects.get(hash_val = idx)
                except ObjectDoesNotExist:
                    #print smart_str(category_name_val)
                    brand_obj = Brands.objects.get(name = store_val)
                    item = StoreCategoryItem(brand = brand_obj, 
                                             gender = gender_val, 
                                             age_group = age_group_val,
                                             categoryName = category_name_val,
                                             hash_val = idx)
                    item.save()
                    yield item
        