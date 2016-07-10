from celery.decorators import task

import json
import logging
from collections import defaultdict
import decimal
import pdb

from django.shortcuts import render_to_response, render, redirect
from django.http import HttpResponse
from django.contrib import auth
from django.conf import settings

from xps import models
from xpathscraper import xbrowser, scrapingresults, resultsenrichment, utils, textutils
from angel import price_tracker
import debra.models
from debra.models import Shelf, ProductModelShelfMap
from debra import logical_categories
from debra.widgets import ShelvesFeed
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from xps import extractor
from django.db.models import Avg, Max, Min, Count, F
import datetime
from django.utils.encoding import smart_str, smart_unicode
from django.utils.http import urlquote
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
import re
import inflect
import urlparse
import urllib
import HTMLParser
from masuka import image_manipulator
from debra.constants import LIKED_SHELF, DELETED_SHELF
from debra.forms import AddAffiliateLinkForm


_htmlparser = HTMLParser.HTMLParser()
unescape = _htmlparser.unescape

log = logging.getLogger('miami_metro')

TAGS_SENT_TO_BOOKMARKLET = ['name', 'img']
TAGS_SENT_TO_BOOKMARKLET_DEBUG = TAGS_SENT_TO_BOOKMARKLET + ['price', 'size', 'color', 'sizetype', 'inseam', 'colordata', 'checkoutbutton']

_BASE_URL = 'http://localhost:8000' if settings.DEBUG else 'https://app.theshelf.com'

PRICE_BOOKMARKLET_HREF_TEMPLATE = """javascript:(function() {
    if (typeof(_PBM_INIT) === 'undefined') {
        var head = document.head || document.getElementsByTagName('head')[0];
        var elem = document.createElement('script');
        elem.setAttribute('src', '%(base_url)s/mymedia/site_folder/js/shelfit_getshelf.js?%(query)sr='+Math.random()*99999999);
        elem.setAttribute('async', false); elem.setAttribute('defer', false); head.insertBefore(elem, head.firstChild);
    } else {
        _PBM.bookmarkClicked();
    }
}());"""

BLACKLISTED_IMG_DOMAINS = [
    'googleadservices',
    'fastclick',
    'invitemedia',
    'adnxs.com',
    'marinsm.com',
    'advertising.com',
    'amgdgt.com',
    'searchmarketing.com',
    'doubleclick.net',
]


def _render_bookmarklet_href(base_url, query):
    tpl = re.sub(r'\s+', ' ', PRICE_BOOKMARKLET_HREF_TEMPLATE.replace('\n', ' '))
    return tpl % dict(base_url=base_url, query=query)

def get_bookmarklet_href():
    return _render_bookmarklet_href(_BASE_URL, '')

def get_bookmarklet_debug_href():
    return _render_bookmarklet_href(_BASE_URL, 'd=1&')

def _jsonpresp(fun, obj):
    return HttpResponse('{fun}({json_data});'.format(fun=fun, json_data=json.dumps(obj)),
            'text/javascript')

def _scraping_result_is_good_enough(sr):
    if sr.tag == 'img':
        for xpe in sr.fetch_xpath_exprs():
            if xpe.expr == '//body/img[1]':
                return False
        if sr.value_json:
            url = json.loads(sr.value_json)
            domain = utils.domain_from_url(url)
            if any(bdomain in domain for bdomain in BLACKLISTED_IMG_DOMAINS):
                return False
    return True

def _scraping_results_resp(wid, scraping_results):
    fun = '_PBM.receivedXPathsForUrl'

    scraping_results = filter(_scraping_result_is_good_enough, scraping_results)

    if len(scraping_results) == 0:
        return _jsonpresp(fun, {'status': 'nodata',
            'msg': 'No xpaths in set'})

    xpath_expr_dict = defaultdict(list)
    for sr in scraping_results:
        for xpe in sr.fetch_xpath_exprs():
            xpath_expr_dict[sr.tag].append(xpe.expr)
    for lst in xpath_expr_dict.values():
        lst.sort(key=len)

    value_dict = defaultdict(list)
    for sr in scraping_results:
        if sr.value_json is not None:
            value_dict[sr.tag].append(sr.value_json)

    log.info('Returning xpath_expr_dict: %s', xpath_expr_dict)
    log.info('Returning value_dict: %s', value_dict)

    final_result = []
    final_result.append(xpath_expr_dict)
    final_result.append(wid)
    final_result.append(value_dict)

    return _jsonpresp(fun, {'status': 'ok', 'data': final_result})

def get_xpaths_for_url(request):
    fun = '_PBM.receivedXPathsForUrl'
    should_redirect = request.GET.get('redirect')

    url = request.GET.get('url')
    if not url:
        return _jsonpresp(fun, {'status': 'error', 'msg': 'No url given'})

    debug_mode = int(request.GET.get('d', '0'))
    tags = TAGS_SENT_TO_BOOKMARKLET if not debug_mode else TAGS_SENT_TO_BOOKMARKLET_DEBUG

    # Add this item to user's wishlist
    log.info("user %s is is_authenticated() %s" % (request.user, request.user.is_authenticated()))
    wid = add_item_from_bookmarklet(url, auth.get_user(request) if request.user.is_authenticated() else None)

    product_model = debra.models.ProductModel.objects.filter(prod_url=url)[0]

    # Try to fetch data directly for a product
    product_q = models.ScrapingResult.objects.filter(product_model=product_model)\
            .filter(tag__in=tags)\
            .order_by('id')\
            .select_related()

    ##############
    # ARTUR: when this is uncommented, if you click on the bookmarklet, then shelve the item, then close the bookmarklet,
    # then click the bookmarklet again, you get an alert message saying that the product url has not been seen please check
    # shelf in 10 minutes
    ##############
    if product_q.exists() and not should_redirect:
        log.info('Returning exprs for this specific product')
        return _scraping_results_resp(wid, list(product_q))

    # Try to fetch data from sets from store
    domain = utils.domain_from_url(url)
    brands = debra.models.Brands.objects.filter(domain_name=domain)
    if not brands.exists():
        return _jsonpresp(fun, {'status': 'nodata', 'msg': 'No brand for url %s' % url})
    brand = brands[0]

    sr_sets = models.ScrapingResultSet.objects.filter(brand=brand, description='__included__').\
            select_related()
    if not sr_sets.exists():
        return _jsonpresp(fun, {'status': 'nodata', 'msg': 'No set for domain %s' % brand.domain_name})
    sr_set = sr_sets[0]
    log.info('Using ScrapingResultSet with id %s', sr_set.id)

    entries = sr_set.scrapingresultsetentry_set.all()\
                .filter(scraping_result__tag__in=TAGS_SENT_TO_BOOKMARKLET)\
                .order_by('-entry_count', 'scraping_result__id')\
                .select_related()
    scraping_results = [e.scraping_result for e in entries]

    scraped = _scraping_results_resp(wid, scraping_results)
    #redirect is in the GET parameters if we're coming from a login/signup
    return scraped if not request.GET.get('redirect') else redirect('{base_url}?item_id={wid}&img={image}&name={name}'.format(base_url=reverse('debra.bookmarklet_views.render_bookmarklet'), wid=wid, image=request.GET.get('img'), name=request.GET.get('name')))


def _handle_data_not_found(request):
    logging.getLogger('mail_admins').error('Elements not found by the bookmarklet')


def add_item_from_bookmarklet(url, user_obj):
    log.info('add_item_from_bookmarklet: %s to user: %s', url, user_obj)
    product = extractor.get_or_create_product(url)
    brand = models.get_or_create_brand(url)
    log.info("product %s product.id %s brand %s", product, product.id, brand)
    product.brand = brand
    product.save()
    log.info("product %s product.id %s brand %s", product, product.id, brand)
    log.info("product.brand %s", product.brand)

    w = None
    if user_obj is not None:
        ## search if the product model exists in our LIKED_SHELF
        if ProductModelShelfMap.objects.filter(user_prof=user_obj.get_profile(),
                product_model=product, shelf__name=LIKED_SHELF).exists():
            log.info('User already has this item')
            w = ProductModelShelfMap.objects.filter(user_prof=user_obj.get_profile(),
                    product_model=product, shelf__name=LIKED_SHELF)[0]
        else:
            product.num_pins = F('num_pins') + 1
            product.save()
            log.info('product %s', product)
            like_shelf = Shelf.objects.get_or_create(user_id=user_obj, name=LIKED_SHELF)[0]
            w = ProductModelShelfMap.objects.create(user_prof=user_obj.get_profile(),
                    product_model=product, snooze=True, shelf=like_shelf)
            # Handling of product.name, product.price, product.img_url is done in the price tracker
            # img_url handled in postprocess function
            log.info("got w %s w.id %s product %s ", w, w.id, product)

        # Run sequentially two tasks
        price_tracker.update_product_price.apply_async([product.id],
                                                       link=postprocess_new_item.subtask([w.id], immutable=True),
                                                       queue="celery")
    return w.id if w else 0

def render_bookmarklet(request):
    item_id = request.GET.get('item_id')
    name = request.GET.get('name', '')
    img = request.GET.get('img', '')

    item = ProductModelShelfMap.objects.get(id=item_id) if item_id and int(item_id) > 0 else None
    user = request.user.userprofile if request.user.is_authenticated() else None
    shelves_feed = ShelvesFeed(request, None, user=user, view_file="bookmarklet_shelves.html").\
                        generate_item_shelves(item, extra_context={'all_shelves': user.user_created_shelves.order_by("name")}) if user else None


    log.info('item=%s, item.product_model=%s', item, item.product_model if item else None)
    log.info('item_id=%s', item_id)
    log.info('name=%s', name)
    log.info('img=%s', img)

    if not name or not img:
        _handle_data_not_found(request)

    resp_obj = render_to_response("pages/bookmarklet.html", {
                    'next': urlquote('{base_url}?redirect=1&url={page_url}&img={image}&name={name}'.format(base_url=reverse('debra.bookmarklet_views.get_xpaths_for_url'),
                                                                                                           page_url=request.GET.get('url', ''),
                                                                                                           image=img,
                                                                                                           name=name.encode('utf-8', 'ignore'))),
                    'item': item,
                    'shelves': shelves_feed.render() if shelves_feed else None,
                    'img': img,
                    'add_affiliate_link_form': AddAffiliateLinkForm(instance=item)
                },
                context_instance=RequestContext(request))

    return resp_obj

def _is_price_text_valid(price_text):
    if not textutils.contains_digit(price_text):
        return False

    if not any(cs in price_text for cs in xbrowser.jsonData['currency_symbols']):
        return False

    try:
        price_fragment = scrapingresults._extract_first_price_text(price_text)
        price_value = resultsenrichment._price_as_decimal(price_fragment)
    except (decimal.InvalidOperation, ValueError):
        return False

    return True

def check_evaluated_texts(request):
    """This view function expects the 'texts' GET parameter
    that will contain JSON-encoded dictionary with tags (price/name etc.) as
    keys and lists of pairs (xpath, evaluated_text) as values.

    It returns a dictionary which is a subset of the input dictionary
    that contains valid values only.
    """
    fun = '_PBM.receivedCheckEvaluatedTextsResult'

    texts_by_tag_str = request.GET.get('texts')
    if not texts_by_tag_str:
        return _jsonpresp(fun, {'status': 'error', 'msg': 'No texts sent'})
    texts_by_tag = json.loads(texts_by_tag_str)
    log.info('Recevied texts: %r', texts_by_tag_str)

    good_xpaths = texts_by_tag.copy()

    for i, (xpath, price_text) in enumerate(texts_by_tag.get('price', [])):
        if not _is_price_text_valid(price_text):
            del good_xpaths['price'][i]

    # Regard other (non-price) as good for now

    log.info('Returning good_xpaths: %s', good_xpaths)
    return _jsonpresp(fun, {'status': 'ok', 'data': good_xpaths})


@task(name="debra.bookmarklet_views.postprocess_new_item")
def postprocess_new_item(item_id):
    print "postprocess_new_item called with id %s " % item_id
    item = ProductModelShelfMap.objects.select_related('user_prof', 'product_model').get(id=item_id)

    all_category_names = set(logical_categories.categories_list)

    ''' Find what shelf this item will be placed under by our auto-categorization'''
    if not (item.product_model.cat1 in all_category_names):
        new_cat = simple_product_categorization(item.product_model)
        item.product_model.cat1 = new_cat["cat1"]
        item.product_model.cat2 = new_cat["cat2"]
        item.product_model.cat3 = new_cat["cat3"]
        item.product_model.save()

    prod = item.product_model
    item.img_url = prod.img_url
    item.save()
    item = ProductModelShelfMap.objects.get(id=item_id)
    image_manipulator.create_images_for_wishlist_item(item)

    # check if this PMSM has user_prof (may not always have as this function is called by import_from_blog,
    # where it's not always true that the user exists for the influencer)
    if item.user_prof:
        item.user_prof.num_items_in_shelves = F('num_items_in_shelves') + 1
        item.user_prof.save()

def map_input_to_logical_category(input_str):

    '''
    V2: March 2014
    cat1 => highest
    cat2 => mid
    cat3 => lowest

    e.g., pants : cat1=> apparel cat2 => pants cat3 => pant
    e.g., scarf : cat1=> accessories cat2=>scarves
    '''
    inflecter = inflect.engine()
    #print "Input: %s" % input_str

    for key in logical_categories.logical_categories_reverse_mapping.keys():
        #print key, logical_categories.logical_categories_reverse_mapping[key]
        cat = logical_categories.logical_categories_reverse_mapping[key]
        if len(cat) == 1:
            cat = {"cat1": cat[0], "cat2": "", "cat3": ""}
        elif len(cat) == 2:
            cat = {"cat1": cat[1], "cat2": cat[0], "cat3": ""}
        elif len(cat) == 3:
            cat = {"cat1": cat[2], "cat2": cat[1], "cat3": cat[0]}


        key_singular = inflecter.singular_noun(key)
        key_plural = key

        if not key_singular:
            #this means that key is already singular
            key_singular = key
            key_plural = inflecter.plural(key)


        #print 'key_sing %s key_plu %s cat %s' % (key_singular, key_plural, cat)
        input_split = input_str.lower().split()
        num_words = len(input_split)
        if num_words > 0 and (key_singular == input_split[num_words-1] or key_plural == input_split[num_words-1]):
            print "Result: Input %s belongs to %s category as it contained (%s or %s)" % (smart_str(input_str), cat, key_singular, key_plural)
            return cat

    for key in logical_categories.logical_categories_reverse_mapping.keys():
        #print key, logical_categories.logical_categories_reverse_mapping[key]
        cat = logical_categories.logical_categories_reverse_mapping[key]
        if len(cat) == 1:
            cat = {"cat1": cat[0], "cat2": "", "cat3": ""}
        elif len(cat) == 2:
            cat = {"cat1": cat[1], "cat2": cat[0], "cat3": ""}
        elif len(cat) == 3:
            cat = {"cat1": cat[2], "cat2": cat[1], "cat3": cat[0]}

        key_singular = inflecter.singular_noun(key)
        key_plural = key

        if not key_singular:
            #this means that key is already singular
            key_singular = key
            key_plural = inflecter.plural(key)


        #print 'key_sing %s key_plu %s cat %s' % (key_singular, key_plural, cat)
        #input_split = input_str.lower().split()

        if key_singular in input_str.lower() or key_plural in input_str.lower():
            print "Result: Input %s belongs to %s category as it contained (%s or %s)" % (smart_str(input_str), cat, key_singular, key_plural)
            return cat

    return None

def simple_product_categorization(product):

    if product.brand.name == "Pottery Barn":
        return {"cat1": "home", "cat2": "", "cat3": ""}
    if product.brand.name == "The Children's Place":
        return {"cat1": "kids", "cat2": "", "cat3": ""}
    cat = map_input_to_logical_category(product.name)
    #print cat

    if not cat:
        #need to look for the category in the URL
        #trip the prefix upto the domain name
        domain_name = product.brand.domain_name
        cat = map_input_to_logical_category(product.prod_url[len(domain_name):])
        #print cat
        if not cat:
            cat = {"cat1": "uncategorized", "cat2": "uncategorized", "cat3": "uncategorized"}

    print "Product %s is categorized as %s. Existing %s" % (smart_str(product.prod_url), cat, smart_str(product.cat1))
    return cat
