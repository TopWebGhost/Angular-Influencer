'''
    Promotion & item matching
    =========================

    Suppose your selected item is a jean:
    1. Item specific promotion that requires more than one item
    
        B1G1 on jeans
    
    
    2. Generic promotion that applies to the item
    
        Free shipping for $X
        $25 off $100
        30% off on jeans
    
    
    3. Other promotions from the store that do not apply to the item
    
        30% off on sweaters 
'''

from debra.view_promo import get_time_bound_promotion_text
from django.contrib.auth.models import User
from django.utils.encoding import smart_str, smart_unicode
from debra.models import WishlistItem
from debra.models import Brands
from debra.models import ProductModel
from debra.models import Promoinfo
import inflect
import datetime
import logging

logger = logging.getLogger('miami_metro')

def check_singular(phrase):
    inflecter = inflect.engine()
    phrase_singular = inflecter.singular_noun(phrase)
    if not phrase_singular: 
        return phrase
    else: 
        return phrase_singular
        
def find_matching_category_items_in_list(cat, wishlist, store_name):
    item_list = []
    #return [wishlist[0].user_selection.item]

    cat_arr = [cat]
    if '&' in cat:
        tmp_cat_arr = cat.split('&')
        cat_arr.append(tmp_cat_arr[0].strip())
        cat_arr.append(tmp_cat_arr[1].strip())
    cat_arr_singular = map(check_singular, cat_arr)
    logger.debug("CAT_ARR_SINGULAR: " + smart_str(cat_arr_singular))
    
    #prod_list = [wi.user_selection.item for wi in wishlist if wi.user_selection.item.brand.name == store_name]
    prod_list = [wi.user_selection for wi in wishlist if wi.user_selection.item.brand.name == store_name]
    for prod in prod_list:
        for prodcat in prod.item.cat1, prod.item.cat2, prod.item.cat3:
            if prodcat != 'Nil':
                prodcat_singular = check_singular(prodcat)
                for cat_singular in cat_arr_singular:
                    #logger.info("Checking cat: " + str(cat_singular) + " with item's category " + str(prodcat_singular))
                    if prodcat_singular == cat_singular:
                        logger.debug("MATCH FOUND! cat: " + str(cat_singular) + " with item's category " + str(prodcat_singular))
                        item_list.append(prod)
    
    return set(item_list)

def find_matching_category_items(cat, store_name, user_obj, wishlist_item):
    '''
        Currently, we are looking at items only from your shelf.
        and if nothing found, we'll look at all shelves.
        
        ****  TODO: we'll look at items from other shelves (e.g., your friends)
              then finally we'll go scrape the website of the brand.
    '''
    

    #brand = Brands.objects.get(name = store_name)
    user_wishlist = WishlistItem.objects.select_related('user_selection',
                                                        'user_selection__item',
                                                        'user_selection__item__brand').filter(user_id = user_obj)
    
    item_list = find_matching_category_items_in_list(cat, user_wishlist, store_name)
    
    logger.debug("Found list " + str(item_list) + " len " + str(len(item_list)) + " for WishlistItem idx: " + str(wishlist_item.user_selection.item.idx))
    if wishlist_item.user_selection in item_list:
        item_list.remove(wishlist_item.user_selection)
    logger.debug("Pruned list " + str(item_list) + " len " + str(len(item_list)) + " for WishlistItem idx: " + str(wishlist_item.user_selection.item.idx))
    

    ''' if couldn't find other similar category items in our wishlist, 
        expand search to include all wishlists
    '''
    if len(item_list) == 0:
        logger.info("Didn't find any matching items in our wishlist, now let's search in all ")
        all_wishlists = WishlistItem.objects.select_related('user_selection',
                                                            'user_selection__item',
                                                            'user_selection__item__brand').all()
        item_list = find_matching_category_items_in_list(cat, all_wishlists, store_name)
        logger.info("Found list " + str(item_list) + " len " + str(len(item_list)) + " for WishlistItem idx: " + str(wishlist_item.user_selection.item.idx))
        if wishlist_item.user_selection in item_list:
            item_list.remove(wishlist_item.user_selection)
        logger.info("Pruned list " + str(item_list) + " len " + str(len(item_list)) + " for WishlistItem idx: " + str(wishlist_item.user_selection.item.idx))
    
    return item_list

def find_promoinfo_for_item(brand, user_obj, wishlist_item, **kwargs):
    
    '''
        For debugging purposes, "date=your_date" can be passed so that we can get richer
        promotions from a specific day (if today's promotion is not that good).
    '''
    if kwargs:
        try:
            date = kwargs['date']
        except KeyError:
            logger.info('KeyError: should not happen. kwargs: '+smart_unicode(kwargs))
            date = datetime.date.today()
    else:
        date = datetime.date.today()
        
    #brand = Brands.objects.get(name = store_name)
    store_spec_promoinfo = Promoinfo.objects.filter(store = brand).filter(d__contains = date) #order_by('d').reverse()[:2]

    #logger.debug("Brand: " + str(brand.name) + " promo info " + str(store_spec_promoinfo))

    prod = wishlist_item.user_selection.item

    #logger.debug(" Product for the wishlist " + str(prod) + " brand for this product: " + str(prod.brand.name))

    ''' from all the promotions running for this store, find promotions at all levels:
        Level 1. ) B1G1, 30%: specifically for this item category
        Level 2. ) Apply to all items, thus also apply to this item
        Level 3. ) Apply to other items, not to this item. E.g., if 
                   item is a jean and discount is 30% on shirts
                   
        We also want to give recommendations for Level 1 promotions.
    '''
    level_one_promos = []
    level_two_promos = []
    level_three_promos = []
    
    level_one_rec = []

    if prod.brand.name == brand.name:
        # 'w' is the wishlist item
        #logger.info("****Product cat: " + str(prod.cat1))

        for promo in store_spec_promoinfo:
            #logger.info('\n\n*****')
            #logger.info("Promo: " + str(promo))
            if promo.promo_type == 0:
                if prod.cat1 in promo.item_category.lower(): # STORE-WIDE
                    #logger.info("\tLEVEL 2: STORE-WIDE: " + str(promo))
                    level_two_promos.append(promo)
                else:
                    '''  
                        if promo.item_category is "Sale" or "Clearance", then this is level 2
                        else, if it has specific category, and that doesn't match this item,
                              then it should be level 3
                    '''
                    if "sale" in promo.item_category.lower() or "clearance" in promo.item_category.lower():
                        #logger.info("\tLEVEL 2: STORE-WIDE: " + str(promo))
                        level_two_promos.append(promo)                        
                    else:
                        #logger.info("\tLEVEL 3: STORE-WIDE: " + str(promo))
                        level_three_promos.append(promo)
                    
            if promo.promo_type == 1: # AGGREGATE
                #logger.info("\tLEVEL 2: AGGREGATE: " + str(promo))
                level_two_promos.append(promo)
                
            if promo.promo_type == 2: # ADDITIONAL
                #logger.info("\tLEVEL 2: ADDITIONAL: " + str(promo))
                level_two_promos.append(promo)
                
            if promo.promo_type == 3:
                
                if prod.cat1 in promo.item_category.lower() or\
                    ('&' in prod.cat1 and prod.cat2 in promo.item_category.lower()) or\
                    ('&' in prod.cat1 and prod.cat3 in promo.item_category.lower()): # B1G1
                    #print "\tLEVEL 1: B1G1: " + str(promo)
                    #logger.info("\tLEVEL 1: B1G1: " + str(promo))
                    #potential_items = find_matching_category_items(prod.cat1, brand.name, user_obj, wishlist_item)
                    #logger.info("\t\tPotential items of the same category: " + str(potential_items))
                    level_one_promos.append(promo)
                    #level_one_rec += potential_items

                else:
                    #logger.info("\tLEVEL 3: B1G1: " + str(promo))                    
                    level_three_promos.append(promo)
    #logger.info("OK, we're here")        
    logger.info(" LEVEL 1: " + str(len(level_one_promos)) + " LEVEL 2: " + str(len(level_two_promos)) + 
                " LEVEL 3: " + str(len(level_three_promos)))
    
    return (level_one_promos, level_two_promos, level_three_promos, level_one_rec)


def find_promoinfo(store_name, user_obj, **kwargs):
    logger.info(store_name + " " + str(user_obj))
    
    wishlist = WishlistItem.objects.filter(user_id = user_obj)
    
    import datetime
    diff = datetime.timedelta(days=5)
    today = datetime.date.today()
    old = today# - diff
    
    for wi in wishlist:
        print "\n\n[***** ITEM: " + str(wi.user_selection.item) + " ]"
        p1, p2, p3, rec1 = find_promoinfo_for_item(store_name, user_obj, wi, date=old)
        
        if len(p1) > 0:
            print "LEVEL 1: " + str(p1)
            
            print "\t\tRecommendations" + str(rec1)

        if len(p2) > 0:
            print "LEVEL 2: " + str(p2)
        
    
        if len(p3) > 0:
            print "LEVEL 3: " + str(p3)
    
def find_promo_raw_text_item(wishlist_item):
    ''' Filter out promos that are not relevant to the item's category '''
    
    final_promo_list = []
    final_promo_raw_text_list = []
    prod = wishlist_item.user_selection.item
    store_name = prod.brand.name
    store_spec_promolist = get_time_bound_promotion_text(brand_name=store_name)

    for promo in store_spec_promolist[store_name]:
        cat = prod.cat1
        promo_text_lower = promo.raw_text.lower()
        
        #print "ITEM: " + str(prod) + " PROMO: " + str(promo) + " cat " + cat
        if (cat != 'Nil' and (cat in promo_text_lower) and not(promo_text_lower in final_promo_raw_text_list)):
            final_promo_list.append(promo)
            final_promo_raw_text_list.append(promo_text_lower)
            #print "PROMO: " + str(promo) + " LEVEL 1: Category-specific: " + cat
        if (cat != 'Nil' and not (cat in promo.raw_text.lower()) and not(promo_text_lower in final_promo_raw_text_list)):
            final_promo_list.append(promo)
            final_promo_raw_text_list.append(promo_text_lower)
            #print "PROMO: " + str(promo) + " LEVEL 3: Other promotions: (not in our category: " + cat + " )"
        if ('sale' in promo.raw_text.lower() or 'clearance' in promo_text_lower or 'redlines' in promo_text_lower) and \
                    not(promo.raw_text.lower() in final_promo_raw_text_list) :
            final_promo_list.append(promo)
            final_promo_raw_text_list.append(promo_text_lower)
            #print "PROMO: " + str(promo) + " LEVEL 2: Sale/Clearance: "

    return final_promo_list

def find_promo_raw_text(store_name, user_obj):
    logger.info(store_name + " " + str(user_obj))
    wishlist = WishlistItem.objects.filter(user_id = user_obj)
    
    for wi in wishlist:
        if wi.user_selection.item.brand.name == "Express":
            promos = find_promo_raw_text_item(wi)
            print "FOUND PROMOS: " + str(promos)
        
if __name__ == "__main__":
    
    print 'Testing'
    store_name = "Abercrombie & Fitch"
    all_users = User.objects.all()
    #find_promo_raw_text(store_name, all_users[1])
    
    find_promoinfo(store_name, all_users[1])
    
    find_promoinfo(store_name, all_users[2])
    
    #find_promoinfo(store_name, all_users[3])
    
    #find_promoinfo(store_name, all_users[4])
    
    #find_promoinfo(store_name, all_users[5])