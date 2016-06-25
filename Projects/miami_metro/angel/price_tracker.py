import logging
import datetime

from django.conf import settings
from celery.decorators import task
from celery.exceptions import SoftTimeLimitExceeded

from debra import models
import debra.tasks
from xpathscraper import utils
from xps import extractor
from masuka import image_manipulator


log = logging.getLogger(__name__)

MIN_IMG_SIZE = 200*200
ITEM_MAX_AGE = datetime.timedelta(days=90)
PRICE_UPDATES_LIMIT = 100000
HEADLESS_DISPLAY = settings.AUTOCREATE_HEADLESS_DISPLAY

DOMAINS_SEPARATELY_QUEUED = ['abercrombie']


@task(name='angel.price_tracker.run_price_updates', ignore_result=True)
def run_price_updates(max_items_to_pick=None, separate_queues=False):
    fresh_items = models.ProductModelShelfMap.objects.\
            filter(added_datetime__gte=datetime.datetime.now() - ITEM_MAX_AGE).\
            order_by('-added_datetime')
    fresh_product_ids = utils.unique_sameorder(item.product_model_id for item in fresh_items)
    log.info('Processing %s fresh products', len(fresh_product_ids))
    if max_items_to_pick:
        fresh_product_ids = fresh_product_ids[:max_items_to_pick]
    else:
        fresh_product_ids = fresh_product_ids[:PRICE_UPDATES_LIMIT]
    for id in fresh_product_ids:
        if separate_queues:
            prod_model = models.ProductModel.objects.get(id=id)
            prod_domain = utils.domain_from_url(prod_model.prod_url)
            if prod_domain in DOMAINS_SEPARATELY_QUEUED:
                update_product_price.apply_async([id], queue='update_product_price.%s' % prod_domain)
                continue
        update_product_price.apply_async([id])
    log.info('Submited all update_product_price tasks')
    return len(fresh_product_ids)

@task(name='angel.price_tracker.update_product_price', ignore_result=True,
        bind=True, soft_time_limit=1800, time_limit=1830, max_retries=5, default_retry_delay=1800)
def update_product_price(self, product_model_id):
    e = None
    try:
        e = extractor.Extractor(headless_display=HEADLESS_DISPLAY)
        _do_update_product_price(self, product_model_id, _extractor=e)
    except SoftTimeLimitExceeded as exc:
        self.retry(exc=exc)
    finally:
        if e is not None:
            e.cleanup_xresources()

def _do_update_product_price(self, product_model_id, _extractor):
    log.info('Processing update_product_price task id=%s', update_product_price.request.id)
    product = models.ProductModel.objects.get(pk=product_model_id)
    log.info('Processing product_id %s url %s', product.id, product.prod_url)

    screenshot_filename = '/tmp/screenshot-%s.png' % update_product_price.request.id
    try:
        res = _extractor.extract_using_computed_xpaths(product, tag_list=extractor.TAG_LIST_ALL,
                quit_driver=False)
    except:
        log.error('Exception during extraction', exc_info=True,
                extra={'data': {
                    'product_model_id': product_model_id,
                    'url': product.prod_url,
                    'screenshot': screenshot_filename,
        }})
        if _extractor.scraper is not None and _extractor.scraper.driver is not None:
            _extractor.scraper.driver.save_screenshot(screenshot_filename)
        raise

    # Together with price extraction we update xpaths for a store (brand),
    # if a page is a valid product page
    if res.valid_product_page:
        log.info('Valid product page, saving xpaths to db')
        extractor.include_xpaths_for_store(product)
    else:
        log.warn('Invalid product page, not saving xpaths to db')

    log.info('Parsing result: %s', res)

    name = res.get('name')
    log.info('name: %s', name)
    if name:
        name = name[0]
        product.name = name.product_name
        designer_name = name.brand_name
        if designer_name:
            product.designer_name = designer_name
        log.info('prod_name %s, desiger name %s', name.product_name, name.brand_name)

    if res.clicking_results:
        log.info('Creating ProductPrices from clicking results')
        product_prices = res.create_product_prices_for_clicking_results(product)
    else:
        log.info('Creating ProductPrices from static page results')
        product_prices = res.create_product_prices_for_static_page(product)

    imgs = res.get('img')
    log.info('Productmodel.img_url: %s, got imgs %s', product.img_url, imgs)
    if imgs and imgs[0].size >= MIN_IMG_SIZE:
        product.img_url = imgs[0].src
        log.info('Saved img_url %s', imgs[0].src)

    product.save()

    # FIXME: select proper product price for wishlist items
    if not product_prices:
        log.warn('No product_prices, not updating wishlist items')
        return

    product_price = max(product_prices, key=lambda pp: pp.price)
    log.info('ProductPrice with highest price: %s', product_price)

    log.info('product.price %s', product.price)
    # Update product model's price
    if product_price.price is not None and (product.price < product_price.price or \
            product.price is None):
        product.price = product_price.price
        log.info('Saved productmodel.price %d', product.price)


    product.save()

    # Update wishlist items for this product
    items = models.ProductModelShelfMap.objects.filter(product_model=product).\
            select_related('current_product_price')
    log.info('Updating %s items', len(items))
    for item in items:
        item.img_url = product.img_url
        item.current_product_price = product_price
        item.save()
        if item.current_product_price is None:
            log.info('Setting price for the first time')
        elif item.current_product_price and (item.current_product_price.price != product_price.price or \
                item.current_product_price.orig_price != product_price.orig_price):
            log.info('Product price changed')
        else:
            log.info('Product price not changed')
        if not item.img_url_shelf_view:
            log.info('ProductModelShelfMap %s has no img_url_shelf_view, so calling image_manipulator', item.id)
            image_manipulator.create_images_for_wishlist_item(item)

    log.info('Finished processing')

@task(name='angel.price_tracker.update_xpaths_for_url', ignore_result=False)
def update_xpaths_for_url(url):
    product = extractor.get_or_create_product(url)
    e = extractor.Extractor(headless_display=HEADLESS_DISPLAY)
    res = e.extract_using_computed_xpaths(product,
            ['name', 'img', 'price', 'size', 'color'])
    extractor.include_xpaths_for_store(product)
    log.info('update_product_price task completed, extracted data: %s', res)

