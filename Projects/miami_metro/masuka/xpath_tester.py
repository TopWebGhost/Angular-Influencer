'''
GUI-based testing of x-paths built by our new algorithm in https://github.com/atuls/PageDetailExtractor

Essentially, we provide a web-page for our internal users where they can go through each product in their WishlistItem
and check if the results found by our algorithm are correct.

Users see three things on this page:
--- left part is the url loaded in the iframe (so that users can easily check the ground truth)
--- middle part are the results given by our algorithm [name, image, price]
--- right part has a correct, error button
    --- if error, user needs to provide the correct result

'''
import sys
from debra.models import ProductModelShelfMap, User
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.conf import settings
import urlparse
from django.http import HttpResponse

from xps import extractor
from xps import models as xpath_models


def save_xpath_test_result(request):
    '''
    Save the results provided by the human tester in the CorrectValue
    '''
    parsed = urlparse.urlparse(request.build_absolute_uri())
    params = urlparse.parse_qs(parsed.query)

    wid = int(params['wid'][0])
    val = params['new_value'][0]
    is_correct = int(params['correct'][0])
    tag = params['tag'][0]
    print "values: [%s] [%s] [%s]" % (wid, val, tag)
    item = ProductModelShelfMap.objects.get(id = wid)
    prod = xpath_models.Product.objects.get(url = item.product_model.prod_url)


    correct_value, created = xpath_models.CorrectValue.objects.get_or_create(product=prod, tag=tag, value=val)
    return HttpResponse(status=200)

def xpath_tester(request):
    '''
    Provide an easy way for a user to test if the output of xps is correct
    '''
    parsed = urlparse.urlparse(request.build_absolute_uri())
    params = urlparse.parse_qs(parsed.query)
    newid = 0
    if 'curid' in params.keys():
        newid = int(params['curid'][0]) + 1
    print "newid %d"% newid

    #make sure to check only those WishlistItems that have not been verified yet
    while True:
        item = ProductModelShelfMap.objects.using('default').all().order_by('-added_datetime')[newid]
        if not xpath_models.CorrectValue.objects.filter(product__url=item.product_model.prod_url).exists():
            break
        newid += 1

    print item.product_model.prod_url

    try:
        name = xpath_models.FoundValue.objects.get(product__url = item.product_model.prod_url, tag="name")
        name = name.value
    except:
        name = None
        print "[Name] Got an exception: prod: %s : %s " % (item.product_model.prod_url, str(sys.exc_info()))
        pass

    try:
        img = xpath_models.FoundValue.objects.get(product__url = item.product_model.prod_url, tag="img")
        img = img.value.strip('[').strip(']').lstrip('u').strip("'")
    except:
        img = None
        print "[Image] Got an exception: prod: %s : %s " % (item.product_model.prod_url, str(sys.exc_info()))
        pass

    try:
        price = xpath_models.FoundValue.objects.get(product__url = item.product_model.prod_url, tag="price")
        price = price.value
    except:
        price = None
        print "[Price] Got an exception: prod: %s : %s " % (item.product_model.prod_url, str(sys.exc_info()))
        pass

    return render_to_response('pages/xpath_tester.html',
                            {'item': item,
                            'name': name,
                            'img': img,
                            'price': price,
                            'curid': newid,
                            },
                            context_instance=RequestContext(request))


def run_xps_script(headless_display=False):
    '''
    for each wishlist item product, we run the xps extractor and store the results in xps FoundValue table
    '''
    e = extractor.Extractor(headless_display=headless_display)

    for i, item in enumerate(ProductModelShelfMap.objects.using('default').select_related('product_model').all().order_by('-added_datetime')[:1000]):
        print "Starting %s %s " % (i, item.product_model.prod_url)
        prod, created = xpath_models.Product.objects.get_or_create(url=item.product_model.prod_url)
        try:
            res = e.extract_from_url(item.product_model.prod_url)
            print "res: %s" % res
            name = res['name']
            img = res['img']
            prices = res['price']

            name_val, created = xpath_models.FoundValue.objects.get_or_create(product=prod, tag='name', value=str(name))
            img_val, created = xpath_models.FoundValue.objects.get_or_create(product=prod, tag='img', value=str(img))
            price_val, created = xpath_models.FoundValue.objects.get_or_create(product=prod, tag='price', value=str(prices))

        except:
            print "Got an exception: prod: %s : %s " % (item.product_model.prod_url, str(sys.exc_info()))
            ### we're also storing the exception
            name_val, created = xpath_models.FoundValue.objects.get_or_create(product=prod, tag='name', value=str(sys.exc_info()))
            pass
