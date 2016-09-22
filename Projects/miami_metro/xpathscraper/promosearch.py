import subprocess
import logging
import uuid
import tempfile
import os
import os.path
from pprint import pformat
import csv
import time
import codecs

from boto.s3.connection import S3Connection
import requests
import baker
from django.conf import settings
from debra import db_util
from celery.decorators import task

from . import xbrowser
from . import utils
from . import xutils
from . import textutils
import debra.models


log = logging.getLogger('xpathscraper.promosearch')

MIN_IMG_SIZE = 200 * 200
PRODUCTS_FOR_LINK_SEARCH = 5

S3_PROMO_IMGS_BUCKET = 'promo-images-candidates'
S3_PROMO_IMGS_EXPIRES = 86400 * 7

@utils.memoize
def _run_tesseract(img_url):
    name = uuid.uuid4().get_hex()
    base_filename = os.path.join(tempfile.gettempdir(), name)
    img_filename = base_filename + os.path.splitext(img_url)[1]
    txt_filename = base_filename + '.txt'

    r = requests.get(img_url)
    r.raise_for_status()
    text = None
    try:
        with open(img_filename, 'w') as f:
            f.write(r.content)
        subprocess.check_output(['tesseract', img_filename, base_filename])
        with open(txt_filename) as f:
            text = f.read()
    finally:
        try:
            os.unlink(img_filename)
        except OSError:
            pass
        try:
            os.unlink(txt_filename)
        except OSError:
            pass
    # omit first line, which is a banner
    #text = text.split('\n', 2)[-1]
    return text


class PromoSearch(object):

    def __init__(self, xbrowser, brands_domain=None):
        self.xbrowser = xbrowser
        self.xbrowser.add_js_file('promo.js')
        if brands_domain:
            brands_model = debra.models.Brands.objects.get(domain_name=brands_domain)
            product_models = brands_model.productmodel_set.all().\
                order_by('-id')\
                [:PRODUCTS_FOR_LINK_SEARCH]
            self.product_urls = [p.prod_url for p in product_models]
            log.info('Product urls to load in search for promo links for domain %s: %s',
                     brands_domain, self.product_urls)

    def _contains_promo_text(self, text):
        text = text.lower()
        words = textutils.split_en_words(text)
        return any(w in xbrowser.jsonData['promo_words'] for w in words)

    def find_images_on_common_pages(self):
        common_links = xutils.find_common_links(self.xbrowser, self.product_urls)
        log.warn('common links, searching for promo images here: (%s) %s', len(common_links),
                 common_links)
        return self._find_on_pages(common_links)

    def find_images_on_crawled_pages(self, depth=1, max_per_page=100):
        res = []
        def when_loaded(url):
            res.extend(self._parse_promotions_from_images())
        for url in self.product_urls:
            xutils.crawl_indepth(self.xbrowser, url, when_loaded, depth, max_per_page)
        return res

    def find_images_and_texts_on_crawled_pages(self, depth=1, max_per_page=5):
        img_res = []
        text_res = []
        def when_loaded(url):
            log.info('Parsing promotions from url %r', url)

            #img_data = self._parse_promotions_from_images()
            #log.info('Parsed promotions from images from url %r: %s', url, pformat(img_data))
            #img_res.extend([(url,) + d for d in img_data])

            text_data = self._find_texts_on_page()
            log.info('Parsed promotions from texts from url %r: %s', url, pformat(text_data))
            text_res.extend([(url,) + d for d in text_data])

        visited = set()
        for url in self.product_urls:
            xutils.crawl_indepth(self.xbrowser, url, when_loaded, depth, max_per_page, visited)

        return img_res, text_res

    def find_on_single_page(self, url):
        self.xbrowser.load_url(url)
        img_res = self._parse_promotions_from_images()
        text_res = self._find_texts_on_page()
        log.info('img_res: %s', img_res)
        log.info('text_res: %s', text_res)
        return img_res + text_res

    def _find_on_pages(self, links):
        imgs = []
        texts = []
        for link in links:
            self.xbrowser.load_url(link)

            img_page_res = self._parse_promotions_from_images()
            log.info('Images found on %s: %s', link, img_page_res)
            imgs += img_page_res

            text_page_res = self._find_texts_on_page()
            texts += text_page_res

        return imgs

    def _parse_promotions_from_images(self):
        imgs = self.xbrowser.driver.find_elements_by_tag_name('img')
        log.info('images on page: %s', len(imgs))
        imgs_sizes = [(el, self.xbrowser.el_size(el)) for el in imgs]
        imgs_sizes = [(el, s) for (el, s) in imgs_sizes if s >= MIN_IMG_SIZE]
        res = []
        for el, s in imgs_sizes:
            src = el.get_attribute('src')
            if not src:
                continue
            text = None
            try:
                text = _run_tesseract(src)
            except:
                log.exception('While running tessaract')
            if not text:
                continue
            is_promo = self._contains_promo_text(text)
            log.info('img: %r, text: %r, promo: %r', src, text, is_promo)
            if is_promo:
                res.append((src, text))
        return res

    def _find_texts_on_page_from_promo_fragments(self):
        promo_xpath_attrs = self.xbrowser.execute_jsfun('_XP.findPromoXPathCandidates')
        log.info('promo_xpath_attrs: %s', promo_xpath_attrs)
        clusters, not_clustered = self.xbrowser.execute_jsfun('_XP.clusterPromoTexts', promo_xpath_attrs)
        log.info('promo clusters, not_clustered: %s %s', clusters, not_clustered)
        texts = []
        for cluster in clusters:
            texts.append(([xa[0] for xa in cluster], ' '.join(xa[1]['attrs']['text'] for xa in cluster)))
        for xa in not_clustered:
            texts.append((xa[0], xa[1]['attrs']['text']))
        log.info('promo texts: %s', texts)
        return texts

    def _find_texts_on_page(self):
        clusters, not_clustered = self.xbrowser.execute_jsfun('_XP.findPromoClusteredCandidates')
        #log.info('promo clusters, not_clustered: %s %s', clusters, not_clustered)
        texts = []
        for cluster in clusters:
            texts.append(([xa[0] for xa in cluster], ' '.join(xa[1]['attrs']['text'] for xa in cluster)))
        for xa in not_clustered:
            texts.append(([xa[0]], xa[1]['attrs']['text']))

        valid_texts = [t for t in texts if any(textutils.contains_en_word(t[1], w) for w in \
                                               xbrowser.jsonData['promo_words'])]
        log.info('promo texts: %s', valid_texts)

        return valid_texts

def upload_images_to_s3(images):
    s3conn = S3Connection(settings.AWS_KEY, settings.AWS_PRIV_KEY)
    bucket = s3conn.create_bucket(S3_PROMO_IMGS_BUCKET)
    bucket.set_acl('public-read')
    s3_urls = []
    for src in images:
        image_data = requests.get(src).content
        key_name = src
        log.info('S3 key_name: %s, bytes: %s', key_name, len(image_data))
        key = bucket.get_key(key_name)
        if key:
            log.info('S3 key already exists, not uploading')
        else:
            log.info('Creating new S3 key')
            key = bucket.new_key(key_name)
            key.set_contents_from_string(image_data)
        s3_urls.append(key.generate_url(S3_PROMO_IMGS_EXPIRES))
    return s3_urls

def most_popular_brands(how_many):
    connection = db_util.connection_for_reading()
    cur = connection.cursor()
    cur.execute("""select pm.brand_id, count(*) as brand_popularity
        from debra_productmodelshelfmap pmsm
        join debra_productmodel pm on pm.id=pmsm.product_model_id
        group by pm.brand_id
        order by brand_popularity desc
        limit %s""", [how_many])
    brands_ids = [row[0] for row in cur]
    cur.close()
    brands_objects = [debra.models.Brands.objects.get(id=b_id) for b_id in brands_ids]
    return brands_objects

@task(name='xpathscraper.promosearch.process_brand')
@baker.command
def process_brand(brand_id):
    brand = debra.models.Brands.objects.get(id=brand_id)
    with xbrowser.XBrowser(disable_cleanup=settings.DEBUG, headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
        ps = PromoSearch(xb, brand.domain_name)
        img_res, text_res = ps.find_images_and_texts_on_crawled_pages()
        #with codecs.open('/tmp/img.%s.%s.csv' % (brand.domain_name, int(time.time())), 'w', 'utf-8') as f:
        #    w = csv.writer(f, delimiter='\t')
        #    for d in img_res:
        #        w.writerow([d[0], d[1], repr(d[2])])
        with codecs.open('/tmp/txt.%s.%s.csv' % (brand.domain_name, int(time.time())), 'w', 'utf-8') as f:
            w = csv.writer(f, delimiter='\t')
            for d in text_res:
                w.writerow([repr(d[0]), u' '.join(repr(x) for x in d[1]), repr(d[2])])

@baker.command
def submit_promo_search_tasks(num_brands):
    brands = most_popular_brands(num_brands)
    log.info('Submitting promo search tasks for brands: %r', brands)
    for brand in brands:
        process_brand.apply_async([brand.id])

@baker.command
def tesseract(url):
    print _run_tesseract(url)

def _upload_from_res(res):
    log.info('uploading images')
    s3_urls = upload_images_to_s3(x[0] for x in res)
    print s3_urls

@baker.command
def images_common(brands_domain, do_upload='0'):
    #utils.log_to_stderr(['__main__', 'xpathscraper', 'requests'])
    xb = xbrowser.XBrowser(disable_cleanup=True)
    ps = PromoSearch(xb, brands_domain)
    res = ps.find_images_on_common_pages()
    print res
    if int(do_upload):
        _upload_from_res(res)

@baker.command
def images_crawled(brands_domain, do_upload='0'):
    #utils.log_to_stderr(['__main__', 'xpathscraper', 'requests'])
    xb = xbrowser.XBrowser(disable_cleanup=True)
    ps = PromoSearch(xb, brands_domain)
    res = ps.find_images_on_crawled_pages()
    print res
    if int(do_upload):
        _upload_from_res(res)

@baker.command
def images_single(url):
    #utils.log_to_stderr(['__main__', 'xpathscraper', 'requests'])
    xb = xbrowser.XBrowser(disable_cleanup=True)
    ps = PromoSearch(xb)
    res = ps.find_on_single_page(url)
    print res

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

