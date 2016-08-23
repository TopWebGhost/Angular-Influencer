import sys
import os
import urllib2
from datetime import datetime
from django.utils.encoding import smart_str
from BeautifulSoup import BeautifulStoneSoup
from celery.decorators import task
from debra.models import Items, Brands

'''
   Process information from within each XML Product node 
'''
def process_pernode_info(prod, gender_val, log_fp):
  pr_br_name = prod.find('brandname')
  pr_id = prod.find('id')
  pr_name = prod.find('name')
  pr_currency = prod.find('currency')
  pr_price = prod.find('price')
  pr_saleprice = prod.find('saleprice')
  pr_instock = prod.find('instock')
  pr_retailer = prod.find('retailer')
  pr_category = prod.findAll('category')
  pr_image = prod.findAll('image')
  pr_color = prod.findAll('color')
  pr_size = prod.findAll('size')
  pr_url = prod.find('url')
  
  pr_brand_id = prod.find('brandid')
  #print pr_br_name, pr_id, pr_name, pr_currency, pr_price, pr_saleprice,\
  #    pr_instock, pr_retailer, pr_category, pr_image_url, pr_color_names, pr_size_vals, pr_url
  
  brand_obj = None
  for brand in Brands.objects.all():
      if brand.name.lower().strip() == pr_br_name.text.lower().strip():
          brand_obj = brand
          break

  if brand_obj == None:
      print "Checking for b" + str(pr_brand_id.text.lower())
      brand_obj = Brands.objects.get(shopstyle_id = 'b' + str(pr_brand_id.text.lower()))
  
  #if not brand_id:
  #    Brands.objects.create(name=pr_br_name.text.strip())
  p_gender = gender_val
  
  # Get product categories (up to five supported right now)
  i = 0
  p_cat = [u'Empty', u'Empty', u'Empty', u'Empty', u'Empty']
  for cat in pr_category:
      p_cat.append(cat.text)
      i += 1
      if (i > 4):
          break

  # Get saleprice
  if pr_saleprice:
      p_saleprice = pr_saleprice.text
  else: 
      p_saleprice = pr_price.text

  # Get image urls (for small, medium and large sizes)
  i = 0
  p_img = [u'Empty', u'Empty', u'Empty']
  for img in pr_image:
      img_url = img.url
      p_img.append(img_url.text)
      i += 1
      if i>2:
          break
  
  # Get available sizes
  p_size = []
  for size in pr_size:
      size_val = size.find('name').text
      p_size.append('[' + size_val.lower().strip() + '], ')
  if not len(p_size):
      p_size.append('[], ') 

  #print brand_id, pr_name.text, p_gender, p_cat, pr_price.text, p_saleprice, p_img, p_size
  
  # Get available colors
  p_color = []
  for color in pr_color:
      color_val = color.find('name').text
      p_color.append('[' + color_val.lower().strip() + '], ')
  if not len(p_color): 
      p_color.append('[], ')

  tmp_array = [brand_obj, pr_name.text, p_gender, p_cat[0], p_cat[1], p_cat[2], p_cat[3], p_cat[4],\
               pr_price.text, p_saleprice, p_img[0], p_img[1], p_img[2], pr_url.text, ''.join(p_size),\
               ''.join(p_color), pr_instock.text, pr_retailer.text, pr_currency.text, pr_id.text]
  
  tmp_array_dbg = [brand_obj.name, pr_name.text, p_gender, p_cat[0], p_cat[1], p_cat[2], p_cat[3], p_cat[4],\
                   pr_price.text, p_saleprice, p_img[0], p_img[1], p_img[2], pr_url.text, ''.join(p_size),\
                   ''.join(p_color), pr_instock.text, pr_retailer.text, pr_currency.text, pr_id.text]
  
  log_fp.write('DB info: ' + smart_str(len(tmp_array)) + ' [' + smart_str(', '.join(tmp_array_dbg)) + ']\n')
  return tmp_array

def parse_product_info(filename_arr, gender_arr, time, log_fp):
  i = 0
  total_items = 0
  new_items = 0
  existing_items = 0
  for filename in filename_arr:
      log_fp.write('Parsing XML Product file: ' + filename + '\n')
      fp = open(filename, 'r')
      xml_str = fp.read() 
      fp.close()
      soup = BeautifulStoneSoup(xml_str)
      for prod in soup.findAll('product'):    
          filedata_arr = process_pernode_info(prod, gender_arr[i], log_fp)
          # It item exists in DB, update, else insert
          item = Items.objects.filter(pr_id=filedata_arr[19])
          total_items += 1
          if item:
              log_fp.write('Item exists, updating\n')
              existing_items += 1
              item.brand = filedata_arr[0] 
              item.name = filedata_arr[1]
              item.gender = filedata_arr[2] 
              item.cat1 = filedata_arr[3] 
              item.cat2 = filedata_arr[4] 
              item.cat3 = filedata_arr[5] 
              item.cat4 = filedata_arr[6] 
              item.cat5 = filedata_arr[7]
              item.price = filedata_arr[8]
              item.saleprice = filedata_arr[9]
              item.insert_date = time.strftime("%Y-%m-%d %H:%M:%S")
              item.img_url_sm = filedata_arr[10]
              item.img_url_md = filedata_arr[11] 
              item.img_url_lg = filedata_arr[12]
              item.pr_url = filedata_arr[13]
              item.pr_sizes = filedata_arr[14]
              item.pr_colors = filedata_arr[15]
              item.pr_instock = filedata_arr[16],
              item.pr_retailer = filedata_arr[17]
              item.pr_currency = filedata_arr[18]
          else:
              log_fp.write('Item does not exist, creating a new one \n' + str(filedata_arr))
              new_items += 1
              Items.objects.create(brand = filedata_arr[0], 
                                   name = filedata_arr[1], 
                                   gender = filedata_arr[2], 
                                   cat1 = filedata_arr[3], 
                                   cat2 = filedata_arr[4], 
                                   cat3 = filedata_arr[5], 
                                   cat4 = filedata_arr[6], 
                                   cat5 = filedata_arr[7], 
                                   price = filedata_arr[8], 
                                   saleprice = filedata_arr[9], 
                                   insert_date = time.strftime("%Y-%m-%d %H:%M:%S"), 
                                   img_url_sm = filedata_arr[10], 
                                   img_url_md = filedata_arr[11], 
                                   img_url_lg = filedata_arr[12], 
                                   pr_url = filedata_arr[13],
                                   pr_sizes = filedata_arr[14],
                                   #pr_colors = filedata_arr[15],
                                   pr_instock = filedata_arr[16],
                                   pr_retailer = filedata_arr[17],
                                   pr_currency = filedata_arr[18],
                                   pr_id = filedata_arr[19])
      i += 1  
  
  return (total_items, existing_items, new_items)
      
'''
 The following two functions just construct and return shopstyle.com urls 
 that allow us to fetch relevant information.
 
 We first use the apiGetCategoryHistogram method to fetch info on
 primary categories and counts.
 
 Total products per brand = sum(primary_category_cnt);  
'''
def construct_ss_cathist_url(brand, log_fp):
    try:
        br_obj = Brands.objects.get(name=brand)
    except ObjectDoesNotExist:
        print 'Invalid Brand Name: ' + brand
        exit
    url_str = 'http://api.shopstyle.com/action/apiGetCategoryHistogram?pid=uid289-3680017-16&fl='+str(br_obj.shopstyle_id)
    log_fp.write(str(br_obj.name) + ' ' + url_str + '\n')
    return url_str
  

def construct_ss_apisearch_url(brand, category, min_idx, rec_cnt, log_fp):
    try:
        br_obj = Brands.objects.get(name=brand)
    except ObjectDoesNotExist:
        print 'Invalid Brand Name: ' + brand
        exit
    url_str = 'http://api.shopstyle.com/action/apiSearch?pid=uid289-3680017-16&cat='+category+'&fl='\
                +str(br_obj.shopstyle_id)+'&min='+str(min_idx)+'&count='+str(rec_cnt)
    log_fp.write(str(br_obj.name) + ' ' + url_str + '\n')
    return url_str


'''
    This function gets info on the primary categories, and the product 'count'. 
    This information is used later when we pull all the information for each brand by 
    pulling 'count' products for each 'primary category' 
'''
def get_cathist_info_from_file(xml_filename_ch):
    fp_ch = open(xml_filename_ch, 'r')
    primary_cats = []
    primary_cats_cnt = []
    xml_str = fp_ch.read()
    soup = BeautifulStoneSoup(xml_str)
    for cat in soup.findAll('category'):
        cat_id = cat.find('id')
        cat_parentid = cat.find('parentid')
        cat_count = cat.find('count')
        if cat_parentid and cat_parentid.text == 'clothes-shoes-and-jewelry':
            #print cat_parentid.text, cat_id.text, cat_count.text
            primary_cats.append(cat_id.text)
            primary_cats_cnt.append(cat_count.text)
    fp_ch.close()
    return primary_cats, primary_cats_cnt
    
def get_cathist_info(brand, time, xmlfilepath, log_fp):
    init_url = construct_ss_cathist_url(brand, log_fp)
    brand_without_space = brand.replace(' ', '_')
    xml_filename_ch = "%s%s%s%s%4d%s%02d%s%02d%s%02d%s%02d%s%02d%s%s" %\
                        (xmlfilepath, "/", brand_without_space.lower(), "-ss-", time.year, "-",\
                         time.month, "-", time.day, "-", time.hour, "-", time.minute, "-",\
                         time.second, "-categoryHist", ".xml")
    log_fp.write('Category Histogram XML filename: ' + xml_filename_ch + '\n')
    print init_url
    fetch_xml_into_file(init_url, xml_filename_ch)
    return get_cathist_info_from_file(xml_filename_ch)
    
# Read from url and write to file
def fetch_xml_into_file(url_str, fname):
    xmlpage = urllib2.urlopen(url_str)
    soup = BeautifulStoneSoup(xmlpage)
    fp = open(fname, 'w')
    fp.write(soup.prettify())
    fp.close()
    return

def get_xml_data(brand, timestamp, xmlfilepath, log_fp):
    # First, we get the main categories per store
    primary_cats, primary_cats_cnt = get_cathist_info(brand, timestamp, xmlfilepath, log_fp)
    log_fp.write('Primary categories: ' + ' '.join(primary_cats) + ', Counts: ' + ' '.join(primary_cats_cnt) + '\n')
    
    # Second, we get the number of items in the category, i.e. product_cnt
    xml_filename = []
    gender_info = []
    brand_without_space = brand.replace(' ', '_')
    for i in range(0, len(primary_cats_cnt)):
        product_cnt = int(primary_cats_cnt[i])
        log_fp.write('Total product count: ' + smart_str(product_cnt) + '\n')
    
        # Next, we fetch item info 250 items at a time (max. allowed pull number by shopstyle API)
        max_allowed_records = 250 # dictated by shopstyle.com API
        num_iter = product_cnt / max_allowed_records
        num_last_cnt = product_cnt % max_allowed_records
        log_fp.write('Num iterations: ' + smart_str(num_iter) + ' ' + smart_str(num_last_cnt) + '\n')
        min_cnt = 0  

        # Create file(s) and store XML data
        k = len(xml_filename)
        for j in range(0, num_iter+1):
            url_str = construct_ss_apisearch_url(brand, primary_cats[i], min_cnt, max_allowed_records, log_fp)
            l_fname = "%s%s%s%s%4d%s%02d%s%02d%s%02d%s%02d%s%02d%s%02d%s" %\
                        (xmlfilepath, "/", brand_without_space.lower(), "-ss-", timestamp.year, "-",\
                         timestamp.month, "-", timestamp.day, "-", timestamp.hour, "-",\
                         timestamp.minute, "-", timestamp.second, "-", j+k, ".xml")
            log_fp.write(smart_str(j) + ': ' + url_str + ' ' + l_fname + '\n') 
            xml_filename.append(l_fname)
            if 'women' in primary_cats[i]:
                gender_info.append('F')
            elif 'mens' in primary_cats[i]:
                gender_info.append('M')
            else:
                gender_info.append('O')
            
            fetch_xml_into_file(url_str, l_fname)    
            min_cnt += 250      

    return xml_filename, gender_info

@task(name="doakes.shopstyle.pull_shopstyle_data")
def pull_shopstyle_data(brand):
    timestamp = datetime.now()
    xmlfilepath = '/tmp/xml-data'
    print 'Working on: ' + brand + ', with XML filepath: ' + xmlfilepath + ', at Time: ' + str(timestamp)
    brand_without_space = brand.replace(' ', '_')
    log_fname = "%s%s%s%s%4d%s%02d%s%02d%s%02d%s%02d%s%02d%s" %\
                          (xmlfilepath, "/", brand_without_space.lower(), "-ss-", timestamp.year, "-",\
                           timestamp.month, "-", timestamp.day, "-", timestamp.hour, "-",\
                           timestamp.minute, "-", timestamp.second, ".dbglog")
    print 'Logfile: ' + log_fname
    log_fp = open(log_fname, 'w')
    xml_fname, gender_arr = get_xml_data(brand, timestamp, xmlfilepath, log_fp)  
    log_fp.write('Number of Product XML files: ' + smart_str(len(xml_fname)) + ', Length of gender array: ' + smart_str(len(gender_arr)) + '\n')
    total_items, existing_items, new_items = parse_product_info(xml_fname, gender_arr, timestamp, log_fp)
    print brand + ', time: ' + str(timestamp) + ', total items: ' + str(total_items) + ', existing items: ' + str(existing_items) + ', new items: ' + str(new_items)
    log_fp.write(str(total_items) + ' ' + str(existing_items) + ' ' + str(new_items) + '\n')
    log_fp.close()
    return (total_items, existing_items, new_items)

if __name__ == "__main__":
    
    if len(sys.argv) < 2:
        print 'Usage    : python $0 brand'
        print 'Example  : python $0 express'
        exit
    
    brand = sys.argv[1]
    total, existing, new = pull_shopstyle_data(brand)
    print total, existing, new
