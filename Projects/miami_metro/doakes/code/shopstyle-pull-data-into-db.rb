# -*- coding: utf-8 -*-
require 'rubygems'  
require 'nokogiri'
require 'open-uri'
require 'net/http'
require 'active_record'  

# Pseudo-code
# 1. Accept cmd-line arguments: brand/store
# 2. Call shopstyle URL with info, and process received arguments
# 3. Write output to db

def process_pernode_info(pernode, gender_val, time, brandinfo_arr)

  pr_id = pernode.xpath('//Product/Id')
  pr_name = pernode.xpath('//Product/Name')
  pr_br_name = pernode.xpath('//Product/BrandName')
  pr_currency = pernode.xpath('//Product/Currency')
  pr_price = pernode.xpath('//Product/Price')
  pr_instock = pernode.xpath('//Product/InStock')
  pr_retailer = pernode.xpath('//Product/Retailer')
  pr_category = pernode.xpath('//Product/Category')
  pr_saleprice = pernode.xpath('//Product/SalePrice') 
  pr_image = pernode.xpath('//Product/Image/Url') 
  pr_color = pernode.xpath('//Product/Color/Name') 
  pr_size = pernode.xpath('//Product/Size/Name') 
  pr_url = pernode.xpath('//Product/Url') 
  
  # Get brand_id
  br_id = ""
  brandinfo_arr.each do |l|
    if (pr_br_name.text.strip.casecmp(l.name.strip) == 0)
      #print "Match: " + l.name.strip + " with " + pr_br_name.text + "\n"
      #print "Match: ID = " + l.id.to_s + "\n"
      br_id = l.id.to_s
      break
    end
  end
  
  # TODO: if br_id is nill, input new brand name and match with that ID

  # Get gender
  p_gender = gender_val

  # Get product categories (up to five supported right now)
  i = 0
  p_cat = ['Empty', 'Empty', 'Empty', 'Empty', 'Empty']
  pr_category.each do |l|
    p_cat[i] = l.text
    i += 1
    break if (i > 4)
  end  

  # Get saleprice
  if ((pr_saleprice.nil? == false) and (pr_saleprice.text.empty? == false))
    p_saleprice = pr_saleprice.text
  else 
    p_saleprice = pr_price.text
  end

  # Get image urls (for small, medium and large sizes)
  i = 0
  p_img = ['Empty', 'Empty', 'Empty']
  pr_image.each do |l|
    p_img[i] = l.text
    i += 1
    break if (i > 2)
  end  
  
  # Get available sizes
  p_size = []
  pr_size.each do |l|
    #print "[" + l.text.to_s.strip + "], "
    p_size << "[" + l.text.downcase.strip + "], "
  end
  p_size << "[], " if p_size.length == 0
  #print p_size.join + "\n"

  # Get available colors
  p_color = []
  pr_color.each do |l|
    #print "[" + l.text.to_s.strip + "], "
    p_color << "[" + l.text.downcase.strip + "], "
  end
  p_color << "[], " if p_color.length == 0
  #print p_color.join + "\n"
  #print pr_name.text + "\n"

  tmp_array = [br_id, pr_name.text, p_gender, p_cat[0], p_cat[1], p_cat[2], p_cat[3], p_cat[4], pr_price.text, p_saleprice, p_img[0], p_img[1], p_img[2], pr_url.text, p_size.join, p_color.join, pr_instock.text, pr_retailer.text, pr_currency.text]
  
  return tmp_array

end

def talk_to_db(dbname)  

  brand_arr = []
  item_cl_name_str = ""
  brand_cl_name_str = ""

  print "Connecting with database: " + dbname + " \n"

  # Establish connection to database
  ActiveRecord::Base.establish_connection(:adapter => 'postgresql',
                                          :host => '69.120.105.217',
                                          :port => '5432',
                                          :username => 'django_user',
                                          :password => 'mypassword',
                                          :database => dbname);

  # Determine table name and create corresponding Class  
  # In table names, find one that includes "items" substring and capitalize!
  table_a = ActiveRecord::Base.connection.tables
  table_a.each do |l|
    if (l.index('_items') != nil) 
      item_cl_name_str = l.capitalize!
    end
    if (l.index('_brands') != nil) 
      brand_cl_name_str = l.capitalize!
    end
  end
  print "Inserting into table: " + item_cl_name_str + " with info from " + brand_cl_name_str + "\n"
  item_cl_name = Object.const_set(item_cl_name_str, Class.new(ActiveRecord::Base))
  brand_cl_name = Object.const_set(brand_cl_name_str, Class.new(ActiveRecord::Base))
  brand_arr[0] = brand_cl_name.find_by_name("Express")
  brand_arr[1] = brand_cl_name.find_by_name("J.Crew")
  brand_arr[2] = brand_cl_name.find_by_name("Banana Republic")
  return item_cl_name, brand_arr
end

def parse_product_info(filename, gender_arr, brand, time, dbname)

  item_cl_name, brand_arr = talk_to_db(dbname)
  i = 0
  fp = []
  filename.each do |l|
    puts "Parsing file: ", l
    fp = File.open(l)  
    reader = Nokogiri::XML::Reader.from_io(fp)
    reader.each do |node|
      if node.name == 'Product' and node.node_type == Nokogiri::XML::Reader::TYPE_ELEMENT
        doc = Nokogiri::XML(node.outer_xml)
        filedata_arr = process_pernode_info(doc, gender_arr[i], time, brand_arr)
        item_cl_name.create(:brand_id => filedata_arr[0], 
                            :name => filedata_arr[1], 
                            :gender => filedata_arr[2], 
                            :cat1 => filedata_arr[3], 
                            :cat2 => filedata_arr[4], 
                            :cat3 => filedata_arr[5], 
                            :cat4 => filedata_arr[6], 
                            :cat5 => filedata_arr[7], 
                            :price => filedata_arr[8], 
                            :saleprice => filedata_arr[9], 
                            :insert_date => time.strftime("%Y-%m-%d %H:%M:%S"), 
                            :img_url_sm => filedata_arr[10], 
                            :img_url_md => filedata_arr[11], 
                            :img_url_lg => filedata_arr[12], 
                            :pr_url => filedata_arr[13],
                            :pr_sizes => filedata_arr[14],
                            :pr_colors => filedata_arr[15],
                            :pr_instock => filedata_arr[16],
                            :pr_retailer => filedata_arr[17],
                            :pr_currency => filedata_arr[18]
                            )
      end
    end
    fp.close
    i += 1
  end  
end

# Read line-by-line and write to file
def fetch_xml_into_file(url_str, fname)
  fp = File.open(fname, 'w')
  @doc = Nokogiri::XML(open(url_str))
  fp.puts(@doc)
  fp.close
end

=begin
 The following two functions just construct and return shopstyle.com urls 
 that allow us to fetch relevant information.
 
 We first use the apiGetCategoryHistogram method to fetch info on
 primary categories and counts.
 
 Total products per brand = sum(primary_category_cnt);  
=end
def construct_ss_cathist_url(brand)
  if (brand.casecmp("jcrew") == 0)
    url_str = "http://api.shopstyle.com/action/apiGetCategoryHistogram?pid=uid289-3680017-16&fl=b284"
  elsif (brand.casecmp("express") == 0)
    url_str = "http://api.shopstyle.com/action/apiGetCategoryHistogram?pid=uid289-3680017-16&fl=b13342"
  elsif (brand.casecmp("bananarepublic") == 0)
    url_str = "http://api.shopstyle.com/action/apiGetCategoryHistogram?pid=uid289-3680017-16&fl=b2683"
  end
end

def construct_ss_apisearch_url(brand, category, min_idx, rec_cnt)
  if (brand.casecmp("jcrew") == 0)
    url_str = "http://api.shopstyle.com/action/apiSearch?pid=uid289-3680017-16&cat="+category.text+"&fl=b284"+"&min="+min_idx.to_s+"&count="+rec_cnt.to_s
  elsif (brand.casecmp("express") == 0)
    url_str = "http://api.shopstyle.com/action/apiSearch?pid=uid289-3680017-16&cat="+category.text+"&fl=b13342"+"&min="+min_idx.to_s+"&count="+rec_cnt.to_s
  elsif (brand.casecmp("bananarepublic") == 0)
    url_str = "http://api.shopstyle.com/action/apiSearch?pid=uid289-3680017-16&cat="+category.text+"&fl=b2683"+"&min="+min_idx.to_s+"&count="+rec_cnt.to_s
  end
end

=begin
 This function gets info on the primary categories, and the product 'count'.
 This information is used later when we pull all the information for each brand by 
 pulling 'count' products for each 'primary category' 
=end
def get_cathist_info_from_file(xml_filename_ch)
  fp_ch = File.open(xml_filename_ch, 'r')
  primary_cats = []
  primary_cats_cnt = []
  reader = Nokogiri::XML::Reader.from_io(fp_ch)
  reader.each do |node|
    if node.name == 'Category' and node.node_type == Nokogiri::XML::Reader::TYPE_ELEMENT 
      doc = Nokogiri::XML(node.outer_xml)
      cat_id = doc.xpath('//Category/Id')
      parent_cat_id = doc.xpath('//Category/ParentId')
      cat_count = doc.xpath('//Category/Count')
      if ((not parent_cat_id.text.empty?) and (parent_cat_id.text == "clothes-shoes-and-jewelry"))
        primary_cats << cat_id
        primary_cats_cnt << cat_count
      end
    end
  end
  return primary_cats, primary_cats_cnt
end

=begin
 In this function, we use the shopstyle.com apiGetCategoryHistogram method to 
 get info on the primary categories and their counts. We store this category histogram 
 information in a file for later reference (if needed). 
=end
def get_cathist_info(brand, time, xmlfilepath)
  init_url = construct_ss_cathist_url(brand)
  @doc = Nokogiri::XML(open(init_url))
  xml_filename_ch = "%s%s%s%s%4d%s%02d%s%02d%s%02d%s%02d%s%02d%s%s" % 
    [xmlfilepath, "/", brand.downcase, "-ss-", time.year, "-", time.month, "-", time.day, "-", time.hour, "-", time.min, "-", time.sec, "-categoryHist", ".xml"]
  puts xml_filename_ch
  fp_ch = File.open(xml_filename_ch, 'w')
  fp_ch.puts(@doc)
  fp_ch.close
  return get_cathist_info_from_file(xml_filename_ch) 
end

def get_xml_data(brand, time, xmlfilepath)
  
  # First, we get the main categories per store
  primary_cats, primary_cats_cnt = get_cathist_info(brand, time, xmlfilepath)
  print "Primary categories: " + primary_cats.join(" ") + ", Counts: " + primary_cats_cnt.join(" ") + "\n"
  
  # Second, we get the number of items in the category, i.e. product_cnt
  xml_filename = []
  gender_info = []
  for i in 0..primary_cats_cnt.length-1

    product_cnt = primary_cats_cnt[i].text.to_i
    print "Total product count: " + product_cnt.to_s + "\n"
    
    # Next, we fetch item info 250 items at a time (max. allowed pull number by shopstyle API)
    max_allowed_records = 250 # dictated by shopstyle.com API
    num_iter = product_cnt / max_allowed_records
    num_last_cnt = product_cnt % max_allowed_records
    print "Num iterations: "+num_iter.to_s+" "+num_last_cnt.to_s+"\n"
    min_cnt = 0  

    # Create file(s) and store XML data
    k = xml_filename.length
    for j in 0..num_iter
      url_str = construct_ss_apisearch_url(brand, primary_cats[i], min_cnt, max_allowed_records)
      l_fname = "%s%s%s%s%4d%s%02d%s%02d%s%02d%s%02d%s%02d%s%02d%s" % 
        [xmlfilepath, "/", brand.downcase, "-ss-", time.year, "-", time.month, "-", time.day, "-", time.hour, "-", time.min, "-", time.sec, "-", j+k, ".xml"]
      print j.to_s + ": " + url_str + " " + l_fname + "\n" 
      xml_filename << l_fname
      if primary_cats[i].text.include? "women"
        gender_info << 'F'
      elsif primary_cats[i].text.include? "mens"
        gender_info << 'M'
      else
        gender_info << 'O'
      end
      #fetch_xml_into_file(url_str, l_fname)    
      min_cnt += 250      
    end
  end
  return xml_filename, gender_info
end

if __FILE__ == $0

  if ARGV.length < 3
    puts "Usage    : ruby $0 brand /path/to/xml name_of_pg_db"
    puts "Example  : ruby $0 express /home/kishore/workspace/miami_metro/doakes/xml-data devel_db"
    exit
  end

  store_name = ARGV[0]
  xmlfilepath = ARGV[1]
  dbname = ARGV[2]

  puts "Brand: " + store_name + ", xmlfilepath: " + xmlfilepath + ", dbname: " + dbname

  time = Time.new
  xml_fname, gender_arr = get_xml_data(store_name, time, xmlfilepath)  
  i = 0
  xml_fname.each do |l|
    print l + " " + gender_arr[i] + "\n"
    i += 1
  end
  parse_product_info(xml_fname, gender_arr, store_name, time, dbname)  
end

