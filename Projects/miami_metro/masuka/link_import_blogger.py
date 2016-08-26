from celery.decorators import task
from selenium import webdriver
from debra.models import ProductModel, WishlistItem, User, Brands, WishlistItemShelfMap


from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support.ui import WebDriverWait

import datetime
from time import sleep
from django.utils.http import urlquote
from pyvirtualdisplay import Display
from django.core.mail import send_mail

# what about viglinks and skimlinks that re-write links on the fly
affiliate_networks = ['rstyle', 'shopstyle', 'linksynergy']

generic_urls = ['pinterest', 'facebook', 'retailmenot', 'luckymag', 'shareaholic', 'ebates', 'blog', 'instagram', 'twitter', 'flickr', 'google', 'yahoo', 'linkwithin', 'feedburner', 'none', 'currentlyobsessed', 'linky', 'photobucket', 'followgram', 'theshelf','wordpress','wikipedia']

def setup_driver():
	display = Display(visible=0, size=(800, 600))
	display.start()
	profile = FirefoxProfile()

	profile.set_preference("dom.max_script_run_time", 600)

	profile.set_preference("dom.max_chrome_script_run_time", 600)

	#profile.set_preference('permissions.default.image', 2)  # disable images

	profile.set_preference('plugin.scan.plid.all', False)  # disable plugin loading crap

	profile.set_preference('dom.disable_open_during_load', True)  # disable popups

	profile.set_preference('browser.popups.showPopupBlocker', False)

	driver = webdriver.Firefox(profile)

	return (driver, display)

def authenticate(driver, server, email, pwd):
	driver.get(server)

	login_form_btns = driver.find_elements_by_xpath('//a[@id="login_btn"]')
	#pick the one that is visible
	login_form_btn = None
	for btn in login_form_btns:
		if btn.is_displayed():
			login_form_btn = btn
			break
	print "Found login btn"
	login_form_btn.click()
	print "Clicked on login_btn"

	sleep(5)

	# now let's find the email and password form and the submit button

	email_form = driver.find_element_by_xpath('.//form[contains(@action,"our_login")]//input[@id="email"]')
	print "Found email %s " % email_form
	email_form.send_keys(email)
	sleep(5)


	pwd_form = driver.find_element_by_xpath('.//form[contains(@action,"our_login")]//input[@id="password"][@name="login_password_visible"]')
	print "Found pwd_form %s, entering password %s " % (pwd_form, pwd)
	pwd_form.send_keys('')
	pwd_form = driver.find_element_by_xpath('.//form[contains(@action,"our_login")]//input[@id="password"][@name="login_password"]')
	pwd_form.send_keys(pwd)
	sleep(5)

	submit_form = driver.find_element_by_xpath('.//form[contains(@action,"our_login")]//input[@value="Submit!"]')
	print "Found submit_form %s " % submit_form

	submit_form.click()
	sleep(15)

def common_prefix(a,b):
  i = 0
  for i, (x, y) in enumerate(zip(a,b)):
    if x!=y: break
  return a[:i]

def fetch_urls(driver, server_add, blog_page_url, shelf_names):

	driver.get(blog_page_url)


	found_urls = []

	for network in affiliate_networks:

		found_urls_elems = driver.find_elements_by_xpath('//a[contains(@href, "' + network + '")]')
		for f in found_urls_elems:
			has_sidebar = f.find_elements_by_xpath('./ancestor::*[contains(@class, "sidebar")] | ./ancestor::*[contains(@id, "sidebar")] | ./ancestor::*[contains(@id, "comment")] | ./ancestor::*[contains(@id, "right")]')
			f_url = f.get_attribute('href')
			if len(has_sidebar) > 0:
				print "%s is in sidebar, so skipping it" % f_url
				continue
			found_generic = False
			for ff in generic_urls:
				if ff in f_url:
					found_generic = True
					break
			if found_generic:
				print "%s is a generic url, so skipping it " % f_url
				continue
			if f_url.endswith('.com') or f_url.endswith('.com/'):
				print "this url %s seems to be the domain url and not a product, so skipping it" % f_url
				continue
			print "Good, this url %s is not in side bar " % f_url
			f_url = f.get_attribute('href')
			found_urls.append(f_url)
		#found_urls += [f.get_attribute('href') for f in found_urls_elems]
	num_affiliate_urls = len(found_urls)
	# now find all non-affiliate links that
	all_urls =  driver.find_elements_by_xpath('//a')
	for f in all_urls:
		has_sidebar = f.find_elements_by_xpath('./ancestor::*[contains(@class, "sidebar")] | ./ancestor::*[contains(@id, "sidebar")] | ./ancestor::*[contains(@id, "comment")] | ./ancestor::*[contains(@id, "right")]')
		if len(has_sidebar) > 0:
			print "%s is in sidebar, so skipping it" % f
			continue
		f_url = f.get_attribute('href')
		if not f_url:
			continue
		#skip url's that go to other bloggers
		found_generic = False
		for ff in generic_urls:
			if ff in f_url:
				found_generic = True
				break
		if found_generic:
			print "%s is a generic url, so skipping it " % f_url
			continue

		if f_url.endswith('.com') or f_url.endswith('.com/'):
			print "this url %s seems to be the domain url and not a product, so skipping it" % f_url
			continue
		print "Checking if [%s] and [%s] have some common prefix " % (f_url, blog_page_url)
		#skip url's that point to other blog entires
		common = common_prefix(f_url, blog_page_url)
		if common == "http" or common == "http://" or common == "http://www" or common == "http://www.":
			found_urls.append(f_url)
		else:
			print "URL %s belongs to the same blogger, so not fetching it " % f_url
			continue

	unique_urls = set(found_urls)
	print "OK, found %s URLs for us to add to the shelf " % len(unique_urls)

	for f_url in unique_urls:
		print "URL %s " % f_url
	count = 0
	num_successful = 0
	failed_urls = set()
	#server_add = 'http://app.theshelf.com/'
	for f_url in unique_urls:
		count += 1
		print "Found URL %s " % f_url


		try:
			driver.execute_script('window.onbeforeunload = function() {}')
		except:
			print "no worries, moving on"
			pass
		driver.get(f_url)
		sleep(60)



		try:
			driver.execute_script('window.onbeforeunload = function() {}')
		except:
			print "no worries, moving on"
			pass


		final_prod_url = driver.current_url
		print "Got prod_url %s " % final_prod_url
		found_generic = False
		for ff in generic_urls:
			if ff in final_prod_url:
				found_generic = True
				break
		if found_generic:
			print "%s %s is a generic url, so skipping  %s" % (f_url, final_prod_url, found_generic)
			continue

		# first check if we have already shelved this URL
		url_already_shelved = False
		separted_shelves = shelf_names.split('^^')
		for sep_shelf in separted_shelves:
			ww = WishlistItemShelfMap.objects.filter(shelf__name__iexact = sep_shelf, wishlist_item__affiliate_prod_link = f_url)
			if len(ww) > 0:
				print "Found Affiliate URL %s already in shelf %s, so not doing anything " % (f_url, sep_shelf)
				url_already_shelved = True
				break
			else:
				ww = WishlistItemShelfMap.objects.filter(shelf__name__iexact = sep_shelf, wishlist_item__user_selection__item__prod_url = final_prod_url)
				if len(ww) > 0:
					print "Found URL %s already in shelf %s, so not doing anything " % (final_prod_url, sep_shelf)
					url_already_shelved = True
					break

		if url_already_shelved:
			continue
		#brands = [site for site in Brands.objects.all() if site.domain_name in final_prod_url]
		#print "Found %s matching brands " % brands
		#for b in brands:
		#	print "b.name=[%s] b.domain_name=[%s]" % (b.name, b.domain_name)

		cmd = """javascript:void((function(){var shelf_svr='%s';var e=document.createElement('script');e.setAttribute('type','text/javascript');e.setAttribute('charset','UTF-8');e.setAttribute('src',shelf_svr+'mymedia/site_folder/js/shelfit_getshelf.js?r='+Math.random()*99999999);document.body.appendChild(e)})());""" % server_add
		print "Cmd %s " % cmd
		driver.execute_script(cmd)
		#driver.execute_script("javascript:void((function(){shelf_svr='%s';var e=document.createElement('script');e.setAttribute('type','text/javascript');e.setAttribute('charset','UTF-8');e.setAttribute('src',shelf_svr+'mymedia/site_folder/js/additem/shelfit_getshelf.js?r='+Math.random()*99999999);document.body.appendChild(e)})());" % server_add)
		sleep(60)
		try:
			print "waiting for jquery to wrap up"
			WebDriverWait(driver, 60, poll_frequency=0.05).until(lambda d : d.execute_script("return jQuery.active == 0") == True)
		except:
			print "waiting for jquery loading to finish failed, so waiting another 60 secs"
			pass

		#cmd = """$('#shelf_content_container').attr('combid');"""
		#print "Cmd %s " % cmd
		try:
			driver.save_screenshot("../"+str(count)+".jpg")
		except:
			pass
		try:
			fname = driver.find_elements_by_xpath('//iframe[@id="shelfit_panel"]')
			if len(fname) > 0:
				print "Success---shelfit worked: at least the iframe showed up!"
				fname = fname[0]
				driver.switch_to_frame(fname)
				num_successful += 1
			else:
				print "moving on to next item since we didn't find the shelfit_panel frame"
				failed_urls.add(f_url)
				continue
		except:
			print "Didn't find shelfit panel, moving on"
			pass
		try:
			elem = driver.find_elements_by_xpath('.//*[@id="shelf_content_container"]')
			if len(elem) > 0:
				elem = elem[0]
				combid = elem.get_attribute('combid')
				print "got combid %s " % combid
			else:
				print "Didn't find the element with combid as an attribute"
				driver.switch_to_default_content()
				failed_urls.add(f_url)
				continue
		except:
			print "Exception happened when looking for the shelf_content_container"
			failed_urls.add(f_url)
			pass
			continue
		driver.switch_to_default_content()
		shelves = shelf_names.split('^^')
		print "got shelves %s shelf_names %s " % (shelves, shelf_names)
		num_shelves = len(shelves)
		print "Got %d number of shelves " % num_shelves
		cmd = server_add + 'categorize_item/?combid='+str(combid)+'&numcat='+str(num_shelves)+'&catval=' + shelf_names
		if f_url != final_prod_url:
			cmd = cmd + '&affiliate_link=' + urlquote(f_url)
		print "fetching %s " % cmd
		driver.get(cmd)



	return (num_successful, failed_urls)

@task(name="masuka.link_import_blogger.task_fetch_urls")
def task_fetch_urls(user, blog_page_url, shelves_to_use, server_add):
	print "Awesome, user [%s] blog [%s] shelves [%s] server_add [%s]" % (user.email, blog_page_url, shelves_to_use, server_add)
	user_id = user.id
	key = "5Xh_48[dghal55sq2g$"
	driver, display = setup_driver()
	if not 'http://' in server_add:
		server_add = 'http://' + server_add
	serv_len = len(server_add)
	if server_add[serv_len -1] != '/':
		server_add = server_add + '/'

	auth_url = server_add+'fetch_urls/?user_id='+str(user_id)+'&key='+key
	print "Auth_url %s " % auth_url
	driver.get(auth_url)
	#at this point, this browser session should be authenticated with the blogger's credentials
	#sleep(30)
	print "OK, we're now authenticated"
	num_successful, failed_urls = fetch_urls(driver, server_add, blog_page_url, shelves_to_use)
	if num_successful > 0:
		send_mail('TheShelf.com: Items successfully imported', 'We were able to successfuly import %d items from your blog %s.\n However, these product URLS failed: %s\n\nVisit shelf now at http://theshelf.com' % (num_successful, blog_page_url, failed_urls),
                  'lauren@theshelf.com',
                  ['hello@theshelf.com', 'atul@theshelf.com', 'morgan@theshelf.com',], fail_silently=False)
	else:
		send_mail('TheShelf.com: Item import failed', 'We could not successfuly import %d items from your blog %s.\nVisit shelf now at http://theshelf.com' % (num_successful, blog_page_url),
                  'lauren@theshelf.com',
                  ['atul.singh@gmail.com'], fail_silently=False)
	display.stop()
	driver.quit()

if __name__ == "__main__":
	#src_url = 'http://www.thepinkpeonies.com/2013/03/giveaway.html'
	src_url = 'http://www.pennypincherfashion.com/2013/03/spotted-in-leather.html'

	driver = setup_driver()
	server = 'http://127.0.0.1:8000/'

	email = 'abcd@gmail.com'
	pwd = '1234'

	#authenticate(driver, server, email, pwd)



