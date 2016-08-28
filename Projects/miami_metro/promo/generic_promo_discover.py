from selenium import webdriver
from debra.models import Brands
import lxml.html
from lxml.html import etree
from htmlops import *

class DomElements:
	def __init__(self, height, width, alt_val, title_val, href_val, area, inner_text):
		self.height = height
		self.width = width
		self.alt = alt_val
		self.title = title_val
		self.href = href_val
		self.area = area
		self.text = inner_text

def analyze_home_page(brand):

	driver = webdriver.Firefox()
	url = brand.start_url

	print "Fetching the start url %s for brand %s " % (url, brand.name)

	driver.get(url)
	src = driver.page_source
	tree = lxml.html.fromstring(src)
	etree1 = etree.ElementTree(tree)
	root = etree1.getroot()

	analyze_page(driver)

	# after this, we should find all category pages
	# then crawl these category pages and fine the content of the sub-navigation
	# visit each one of these and call analyze_page() on all of them

	# TODO 1: handle iframes
	# TODO 2: handle text that contains keywords

	driver.quit()


# using each leaf's attributes
#>>> for i in img_leaves:
#...       keys = i.keys()
#...       for k in keys:
#...          print "%s %s" % (k, i.get(k)),
#...       print "\n\n"

# finding the leaves
#for c in root.iter():
#...    chh = [ch for ch in c.iterchildren()]
#...    if len(chh) == 0:
#...       leaves.append(c)

#root = etree1.getroot()
#

def analyze_page(driver):
	# Steps
	# 1. Find all images
	# 2. Filter out those are small (<200px in area)
	# 3. For each image
	#    -- Obtain their metadata
	# 	 ----- title, val, text, url, alt
	# 4. Find those images that have keywords ["promo", "sale", "discount", "save", "buy"] in their metadata

	step1 = driver.find_elements_by_xpath('.//img')
	step2 = []
	for img in step1:
		width = img.size['width']
		height = img.size['height']
		alt = img.get_attribute('alt')
		title = img.get_attribute('title')
		href = img.get_attribute('src')
		text = img.text
		area = width * height
		print "Image has area %d " % area
		if area > 100:
			elem = DomElements(height, width, alt, title, href, area, text)
			step2.append(elem)

	img_urls = set()

	for img in step2:
		print "Alt=[%s] Title=[%s] Href=[%s] Area=[%d] Height=[%d] Width=[%d]" % (img.alt, img.title, img.href, img.area, img.height, img.width)
