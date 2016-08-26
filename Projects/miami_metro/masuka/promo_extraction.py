from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from debra.models import Brands
#!/usr/bin/python

# Usage: recognize.py <input file> <output file> [-language <Language>] [-pdf|-txt|-rtf|-docx|-xml]

import argparse
import base64
import getopt
import MultipartPostHandler
import os
import re
import sys
import time
import urllib2
import urllib
import xml.dom.minidom
from time import sleep
from pyvirtualdisplay import Display

profile = FirefoxProfile()
profile.set_preference("dom.max_script_run_time",600)
profile.set_preference("dom.max_chrome_script_run_time",600)
#profile.set_preference('permissions.default.image', 2) # disable images
profile.set_preference('plugin.scan.plid.all', False) # disable plugin loading crap
profile.set_preference('dom.disable_open_during_load',True) # disable popups
profile.set_preference('browser.popups.showPopupBlocker',False)

potential_promo_list = []
urls_to_follow = []
imginfo = {}

class PotentialPromoUnit:
	img_url = None
	text = ""
	file_index = 0
	def __eq__(self, other):
		if isinstance(other, PotentialPromoUnit):
			return self.img_url == other.img_url and self.text == other.text

class ImgInfo:
	img_url = None
	height = None
	width = None
	area = None
	count = 0

class ProcessingSettings:
	Language = "English"
	OutputFormat = "txt"


class Task:
	Status = "Unknown"
	Id = None
	DownloadUrl = None
	def IsActive( self ):
		if self.Status == "InProgress" or self.Status == "Queued":
			return True
		else:
			return False

class AbbyyOnlineSdk:
	ServerUrl = "http://cloud.ocrsdk.com/"
	ApplicationId = "ShelfOCR"
	Password = "59b85l/YV2ezm5Z6Q+zyNoel"
	Proxy = None
	enableDebugging = 0

	def ProcessImage( self, filePath, settings ):
		urlParams = urllib.urlencode({
			"language" : settings.Language,
			"exportFormat" : settings.OutputFormat
			})
		requestUrl = self.ServerUrl + "processImage?" + urlParams

		bodyParams = { "file" : open( filePath, "rb" )  }
		request = urllib2.Request( requestUrl, None, self.buildAuthInfo() )
		response = self.getOpener().open(request, bodyParams).read()
		if response.find( '<Error>' ) != -1 :
			return None
		# Any response other than HTTP 200 means error - in this case exception will be thrown

		# parse response xml and extract task ID
		task = self.DecodeResponse( response )
		return task

	def GetTaskStatus( self, task ):
		urlParams = urllib.urlencode( { "taskId" : task.Id } )
		statusUrl = self.ServerUrl + "getTaskStatus?" + urlParams
		request = urllib2.Request( statusUrl, None, self.buildAuthInfo() )
		response = self.getOpener().open( request ).read()
		task = self.DecodeResponse( response )
		return task

	def DownloadResult( self, task, outputPath ):
		getResultParams = urllib.urlencode( { "taskId" : task.Id } )
		getResultUrl = self.ServerUrl + "getResult?" + getResultParams
		request = urllib2.Request( getResultUrl, None, self.buildAuthInfo() )
		fileResponse = self.getOpener().open( request ).read()
		resultFile = open( outputPath, "wb" )
		resultFile.write( fileResponse )


	def DecodeResponse( self, xmlResponse ):
		""" Decode xml response of the server. Return Task object """
		dom = xml.dom.minidom.parseString( xmlResponse )
		taskNode = dom.getElementsByTagName( "task" )[0]
		task = Task()
		task.Id = taskNode.getAttribute( "id" )
		task.Status = taskNode.getAttribute( "status" )
		if task.Status == "Completed":
			task.DownloadUrl = taskNode.getAttribute( "resultUrl" )
		return task


	def buildAuthInfo( self ):
		return { "Authorization" : "Basic %s" % base64.encodestring( "%s:%s" % (self.ApplicationId, self.Password) ) }

	def getOpener( self ):
		if self.Proxy == None:
			self.opener = urllib2.build_opener( MultipartPostHandler.MultipartPostHandler,
			urllib2.HTTPHandler(debuglevel=self.enableDebugging))
		else:
			self.opener = urllib2.build_opener( 
				self.Proxy, 
				MultipartPostHandler.MultipartPostHandler,
				urllib2.HTTPHandler(debuglevel=self.enableDebugging))
		return self.opener



def get_context(node, brand_url):
	"""
		If node is image, then we use the anchor tag of the parent node as well as the text for the parent.
		If node is a text block, then we use the parent node's anchor tag 
	"""
	parent = node.find_element_by_xpath('..')
	#atag = parent.find_elements_by_xpath('./a')
	urls = None
	url = parent.get_attribute('href')
	if url:
		urls = []
		if 'window.open' in url:
			# this is probably for a pop-up, let's extract the URL
			l0 = len('window.open(')
			i0 = url.find('window.open(')
			s0 = url[i0+l0+1:]
			i1 = s0.find(',')
			s1 = s0[:i1-1]
			print "s1 %s brand_url %s " % (s1, brand_url)
			urls.append(brand_url + s1)
		else:
			urls.append(url)
	#if len(atag) > 0:
	#	urls = []
	#	for a in atag:
	#		urls.append(a.get_attribute('href'))
	#images = parent.find_elements_by_xpath('./*[contains (@src, "gif") or contains (@src, "jpg") or contains (@src, "png") or contains (@src, "jpeg")]')
	images = None
	return parent.text, urls, images


def get_images_info(url, brand_url):
    
    
	#firefoxProfile.addExtension("firebug-1.8.1.xpi")
	#firefoxProfile.setPreference("extensions.firebug.currentVersion", "1.8.1")



	new_urls = []
	print "get_images_info():: Trying: " + url
	driver.get(url)
	

	#images = driver.find_elements_by_xpath('//img')
	images = driver.find_elements_by_xpath('//*[contains (@src, "gif") or contains (@src, "jpg") or contains (@src, "png") or contains (@src, "jpeg")]')
	for img in images:
		ii = ImgInfo()
		h = img.get_attribute('height')
		w = img.get_attribute('width')
		ii.img_url = img.get_attribute('src')
		ii.height = int(h)
		ii.width = int(w)
		ii.area = ii.height * ii.width
		if not ii.area in imginfo.keys():
			imginfos = []
			imginfos.append(ii)
			imginfo[ii.area] = imginfos
		else:
			imginfos = imginfo[ii.area]
			imginfos.append(ii)



	for img in images:
		#print "Dealing with img %s " % img
		src = img.get_attribute('src')
		#print "Got src %s " % src
		alt = img.get_attribute('alt')
		#print "Got alt %s " % alt
		context, parent_url, _ = get_context(img, brand_url)
		if parent_url:
			new_urls.append(parent_url[0])
		#print "Got ctxt %s " % context
		height = int(img.get_attribute('height'))
		width = int(img.get_attribute('width'))
		area = height * width
		#print "Height %d Width %d Area %d" % (height, width, area)
		same_area_images = imginfo[area]
		count_same_area = len(same_area_images)
		#print "count_same_area %d " % count_same_area
		#return
		map_id = img.get_attribute('usemap')
		#print "Got map_id %s " % map_id
		if src and len(src) > 0 and count_same_area < 10:	
			potential_promo = PotentialPromoUnit()
			potential_promo.img_url = src
			potential_promo.text = alt
			if context:
				potential_promo.text += " " + context
			if not potential_promo in potential_promo_list:
				potential_promo_list.append(potential_promo)
		if map_id and len(map_id) > 0:
			id_ = map_id.strip('#')
			print "Ok, real id is %s " % id_
			map_elems = driver.find_elements_by_xpath('//*[@id="'+id_+'"]/area')
			print "Ok, found map_elems %s " % map_elems
			for elem in map_elems:
				n_url = elem.get_attribute('href')
				new_urls.append(n_url)

	print "OK, now we're trying the iframes"
	#now, we also need to try the iframes
	frames = driver.find_elements_by_xpath('//iframe')
	map_ids = []
	for frame in frames:
		print "Switching to next frame  %s " % frame.get_attribute('src')
		driver.switch_to_frame(frame)
		images = driver.find_elements_by_xpath('//*[contains (@src, "gif") or contains (@src, "jpg") or contains (@src, "png") or contains (@src, "jpeg")]')
		for img in images:
			src = img.get_attribute('src')
			alt = img.get_attribute('alt')
			context, parent_url, _ = get_context(img, brand_url)
			if parent_url:
				new_urls.append(parent_url[0])
			map_id = img.get_attribute('usemap')
			if src and len(src) > 0:
				potential_promo = PotentialPromoUnit()
				potential_promo.img_url = src
				potential_promo.text = alt
				if context:
					potential_promo.text += " " + context
				if not potential_promo in potential_promo_list:
					potential_promo_list.append(potential_promo)
				print "Got img_src %s img_alt %s context %s " % (src, alt, context)
			if map_id and len(map_id) > 0:
				id_ = map_id.strip('#')
				print "Ok, real id is %s " % id_
				map_elems = driver.find_elements_by_xpath('//*[@id="'+id_+'"]/area')
				print "Ok, found map_elems %s " % map_elems
				if len(map_elems) ==0:
					map_elems = driver.find_elements_by_xpath('//*[@name="'+id_+'"]/area')
				for elem in map_elems:
					n_url = elem.get_attribute('href')
					new_urls.append(n_url)
				#it's possible that the map with the given id is in the original HTML (and not in this frame)
				if len(map_elems) == 0:
					map_ids.append(id_)
		driver.switch_to_default_content()

	driver.switch_to_default_content()
	#checking for the map_ids in the original DOM
	for id_ in map_ids:
		map_elems = driver.find_elements_by_xpath('//*[@id="'+id_+'"]/area')
		if len(map_elems) ==0:
			map_elems = driver.find_elements_by_xpath('//*[@name="'+id_+'"]/area')
		print "Ok, found map_elems %s " % map_elems
		for elem in map_elems:
			n_url = elem.get_attribute('href')
			new_urls.append(n_url)
	return new_urls

def interesting(text_input):
	text = text_input.lower()
	if 'sale' in text or 'free' in text or 'discount' in text or 'b1g1' in text or ' off' in text or 'detail' in text or '%' in text:
		return True

	return False


def get_txt_info(url, brand_url):
	"""
	Find all leaf nodes and check their inner text
	"""
	print "get_txt_info():: Trying: " + url
	driver.get(url)

	leaf_nodes = driver.find_elements_by_xpath('//*[not(child::*)]')

	interesting_leaves = []
	new_urls = []
	for node in leaf_nodes:
		if interesting(node.text.lower()):
			interesting_leaves.append(node)

	#sometimes the relevant text is present in siblings
	#<span class="promotion">Free Shipping</span>
	#&
	#<span class="promotion">Free Returns</span>
	#* on orders of $200 or more with code:
	#<b>SFAWINTER</b>

	# so we look at one level up and then all the siblings
	text_result = set()
	for node in interesting_leaves:
		ctxt, urls, images = get_context(node, brand_url)
		if urls:
			for u in urls:
				new_urls.append(u)
		print "node.text %s ctxt %s " % (node.text, ctxt)
		potential_promo = PotentialPromoUnit()
		if ctxt and len(ctxt) > len(node.text):
			potential_promo.text = ctxt.lower()
		else:
			potential_promo.text = node.text.lower()
		count_same_area = 0
		area = 0
		if images and len(images) > 0:
			print "Got image in the context"
			for img in images:
				print "img.src %s " % img.get_attribute('src')
			potential_promo.img_url = images[0].get_attribute('src')
			height = int(images[0].get_attribute('height'))
			width = int(images[0].get_attribute('width'))
			area = height * width
			same_area_images = imginfo[area]
			count_same_area = len(same_area_images)
			print "Height %d Width %d Area %d count_same_area %d " % (height, width, area, count_same_area)
		if count_same_area < 10:
			#don't add the same text again and again
			if area == 0:
				if potential_promo.text in text_result:
					continue
			text_result.add(potential_promo.text) 
			if not potential_promo in potential_promo_list:
				print "Adding %s in the promo list count_same_area %d " % (node.text, count_same_area)
				potential_promo_list.append(potential_promo)
	return new_urls


"""
for store s:
	urls_to_crawl = {home page of s}
	promo_units = {}

	for u in urls_to_crawl:
		promo_units += find_images(u)
		promo_units += find_text(u)
		urls_to_crawl += find_follow_links(u)

	for p in promo_units:
		if p.type = IMAGE:
			perform OCR on p.image

	# wait until OCR is Completed
	now, promo_units contain textual information 

"""

def handle_store(store_name):
	brand = Brands.objects.get(name = store_name)
	brand_url = brand.start_url
	print "brand_url %s " % brand_url
	urls_to_follow.append(brand.start_url)
	total = len(urls_to_follow)
	index = 0
	while index < total:
		cur_url = urls_to_follow[index]
		print "[%d/%d] Dealing with URL %s " % (index, total, cur_url)
		follow_urls1 = get_images_info(cur_url, brand_url)
		print "follow_urls1 %s " % follow_urls1
		follow_urls2 = get_txt_info(cur_url, brand_url)
		print "follow_urls2 %s " % follow_urls2
		follow_urls = follow_urls1 + follow_urls2
		for uu in follow_urls:
			if not uu in urls_to_follow and brand_url in uu:
				print "Need to add %s to the URL list " % uu
				urls_to_follow.append(uu)
		total = len(urls_to_follow)
		index += 1
		
	print "Done collecting, now printing the potential_promo_list"
	for p in potential_promo_list:
		if p.img_url:
			if brand.start_url in p.img_url:
				print "Img URL: [%s] Text: [%s]" % (p.img_url, p.text)
		else:
			print "Img URL: [] Text: [%s]" % (p.text)
	
	index = 0
	abb = AbbyyOnlineSdk()
	settings = ProcessingSettings()
	tasks = {}

	for p in potential_promo_list:
		if p.img_url:
			if brand.start_url in p.img_url:
				print "Img URL: [%s] Text: [%s]" % (p.img_url, p.text)
				#first download the image locally
				print "Dealing with '" + p.img_url + "'"
				u = urllib2.urlopen(p.img_url)
				path = '/Users/atulsingh/Downloads/file'+str(index)+'.html'
				localFile = open(path, 'w')
				localFile.write(u.read())
				localFile.close()
				task = abb.ProcessImage(path, settings)
				tasks[task] = p
				print "Done with '" + p.img_url + "'"
				p.file_index = index
				index += 1
	print "Now checking status after sleeping..."
	#now let's check status
	sleep(60)
	all_done = False
	index = 0
	
	for t in tasks.keys():
		status = abb.GetTaskStatus(t)
		while status.Status != 'Completed':
			#sweet
			sleep(60)
			status = abb.GetTaskStatus(t)
		print "this task " + str(t) + " is done"
		result_path = '/Users/atulsingh/Downloads/result'+str(index)+'.txt'
		abb.DownloadResult(t, result_path)
		ff = open(result_path, 'r')
		print "File content: %s " % ff.read()
		potential_promo = tasks[t]
		print "promo: %s " % potential_promo.text

		index += 1
		

def dump_promo_raw_text(date_):
	from debra.models import PromoRawText
	promos = PromoRawText.objects.filter(insert_date__contains = date_)
	index = 0
	data = set()
	for p in promos:
		#print "%d %s " % (index, p.raw_text)
		
		data.add(p.raw_text)
	for entry in data:
		print str(index) + ' "' + entry + '"'
		print "\n"
		index += 1
if __name__ == "__main__":

	import datetime
	date_ = datetime.date.today()
	#dump_promo_raw_text(date_)
	if len(sys.argv) > 1 and sys.argv[1]:
		display = Display(visible=0, size=(800, 600))
		display.start()
		driver = webdriver.Firefox(profile)

		handle_store(sys.argv[1])

		driver.quit()
		display.stop()
