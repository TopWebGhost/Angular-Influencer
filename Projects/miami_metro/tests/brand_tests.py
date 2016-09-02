# -*- coding: utf-8 -*-
import unittest
import time
from xpathscraper.xbrowser import XBrowser
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from debra.models import User, Brands
import helpers


class RegisterBrand(unittest.TestCase):
    def setUp(self):
        self.base_url = "http://localhost:8000"
        self.server = helpers.ServerRunner()
        self.server.mock_fn('debra.models.intercom')
        self.server.mock_fn('intercom.Intercom')
        self.server.mock_fn('intercom.User')
        self.server.mock_fn('intercom.Tag')
        self.server.mock_fn('mixpanel.Mixpanel')
        self.server.mock_fn('debra.account_helpers.send_mail')
        self.server.mock_fn('registration.models.RegistrationProfile.send_activation_email')
        self.server.mock_fn('platformdatafetcher.fetcher.create_platforms_from_urls')
        self.server.mock_fn('debra.account_helpers.intercom_track_event')
        self.server.mock_fn('django-intercom.intercom')
        self.server.run()

        try:
            User.objects.get(email="contact@taigh.eu").delete()
        except:
            pass
        try:
            User.objects.get(username="theshelf@taigh.eu.toggle").delete()
        except:
            pass
        try:
            Brands.objects.get(domain_name="taigh.eu").delete()
        except:
            pass
        self.wait_timeout = 300
        self.xb = XBrowser()#headless_display=True)
        self.driver = self.xb.driver

    def _wait_and_click_xpath(self, xpath):
        driver = self.driver
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        driver.find_element_by_xpath(xpath).click()

    def _wait_and_click_css(self, css):
        driver = self.driver
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
        driver.find_element_by_css_selector(css).click()

    def _wait_and_click_id(self, id):
        driver = self.driver
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.ID, id))
        )
        driver.find_element_by_id(id).click()


    def _posts_loaded(self):
        driver = self.driver
        WebDriverWait(driver, self.wait_timeout).until_not(
            EC.presence_of_element_located((By.XPATH, '//*[@id="bloggers_root"]/div[3]/div[4]/div/span/div[2]/ul'))
        )
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".dashboard_block"))
        )
        self.assertTrue(driver.execute_script('return $(".dashboard_block").length')>0)


    def _bloggers_loaded(self):
        driver = self.driver
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".blogger_box.search_item"))
        )
        self.assertTrue(driver.execute_script('return $(".blogger_box.search_item").length')>0)


    def logout(self):
        driver = self.driver
        driver.get("%s/logout/" % (self.base_url,))

    def login(self):
        driver = self.driver
        driver.get(self.base_url)
        WebDriverWait(driver, self.wait_timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".log_sign_corner > a:nth-child(2)"))
        )
        driver.find_element_by_css_selector(".log_sign_corner > a:nth-child(2)").click()
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".login_title"))
        )
        driver.find_element_by_id("login_form_id_1").clear()
        driver.find_element_by_id("login_form_id_1").send_keys("contact@taigh.eu")
        driver.find_element_by_id("login_form_id_2").clear()
        driver.find_element_by_id("login_form_id_2").send_keys("test")
        driver.find_element_by_xpath("(//input[@value='Submit!'])[2]").click()

    def do_register(self):
        driver = self.driver
        driver.get(self.base_url)
        WebDriverWait(driver, self.wait_timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".log_sign_corner > a:nth-child(1)"))
        )
        driver.find_element_by_css_selector(".log_sign_corner > a:nth-child(1)").click()
        WebDriverWait(driver, self.wait_timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//div[2]/div/div/div/div/div/div[2]"))
        )
        driver.find_element_by_xpath("//div[2]/div/div/div/div/div/div[2]").click()
        driver.find_element_by_id("brand_signup_id_1").clear()
        driver.find_element_by_id("brand_signup_id_1").send_keys("taigh")
        driver.find_element_by_id("brand_signup_id_2").clear()
        driver.find_element_by_id("brand_signup_id_2").send_keys("contact@taigh.eu")
        driver.find_element_by_id("brand_signup_id_3").clear()
        driver.find_element_by_id("brand_signup_id_3").send_keys("test")
        driver.find_element_by_id("brand_signup_id_4").clear()
        driver.find_element_by_id("brand_signup_id_4").send_keys("taigh")
        driver.find_element_by_id("brand_signup_id_5").clear()
        driver.find_element_by_id("brand_signup_id_5").send_keys("taigh.eu")
        driver.find_element_by_xpath("(//input[@value='Submit!'])[2]").click()

        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body > div.lightbox.dynamic.bl_bg_lb.w_logo"))
        )
        self.assertEqual("Wonderful! We just sent you an email.", driver.find_element_by_css_selector(".lb_title").text)

        #mock checks
        self.assertTrue(self.server.mock_called('registration.models.RegistrationProfile.send_activation_email'))

        #post register db checks
        self.assertTrue(User.objects.filter(email="contact@taigh.eu").count() == 1)
        user = User.objects.get(email="contact@taigh.eu")
        user_profile = user.userprofile
        self.assertFalse(user_profile is None)
        activation_key = user.registrationprofile_set.all()[0].activation_key

        #email activation
        driver.get("%s/accounts/activate/%s/" % (self.base_url, activation_key))
        time.sleep(10)
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[3]/div[2]/div/div/div"))
        )
        self.assertEqual("Awesome, we'll message you shortly to set up a demo time! If you're wanting a quicker response, you can contact us here.", driver.find_element_by_css_selector("div.subti.gray").text)

        self.assertTrue(Brands.objects.filter(domain_name="taigh.eu").count() == 1)
        brand = Brands.objects.get(domain_name="taigh.eu")
        self.assertEqual(brand.flag_locked, True)
        self.assertEqual(brand.flag_availiable_plan, None)

    def do_payment(self):
        driver = self.driver
        driver.get(self.base_url)
        time.sleep(10)
        self._wait_and_click_xpath("//div[2]/div/div/div/div[2]")
        self._wait_and_click_xpath("//input[@value='Go to checkout']")
        driver.find_element_by_xpath("(//input[@type='text'])[2]").clear()
        driver.find_element_by_xpath("(//input[@type='text'])[2]").send_keys("4242 4242 4242 4242")
        driver.find_element_by_xpath("//div[2]/div/div/div/div/div/form/div[2]/fieldset/div").click()
        self._wait_and_click_xpath("/html/body/span/div[11]/div[1]/div/div/div[2]/div/div/div/div/div/form/div[2]/fieldset[1]/div/ul/li[3]/a")
        driver.find_element_by_xpath("//div[2]/div/div/div/div/div/form/div[2]/fieldset[2]/div").click()
        self._wait_and_click_xpath("/html/body/span/div[11]/div[1]/div/div/div[2]/div/div/div/div/div/form/div[2]/fieldset[2]/div/ul/li[3]/a")
        driver.find_element_by_xpath("(//input[@type='text'])[3]").clear()
        driver.find_element_by_xpath("(//input[@type='text'])[3]").send_keys("123")
        driver.find_element_by_xpath("//input[@value='Submit']").click()

    def do_brand_enterprise_noagency(self):
        #base of some other tests
        driver = self.driver

        self.do_register()

        brand = Brands.objects.get(domain_name="taigh.eu")
        brand.flag_locked = False
        brand.flag_availiable_plan = 'enterprise'
        brand.save()

        #payment
        self.do_payment()

        #agency wizard
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/span/div/div/div/div[2]/div/div/div/div/div/h1"))
        )
        self.assertEqual("Are you an Agency?", driver.find_element_by_xpath("/html/body/span/div/div/div/div[2]/div/div/div/div/div/h1").text)
        self._wait_and_click_xpath("/html/body/span/div/div/div/div[2]/div/div/div/div/div/a[2]")

        time.sleep(60)
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.blogger_search_page"))
        )

    def do_test_filter_panel_bloggers(self):
        driver = self.driver
        eng_min = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[2]/div[2]/fieldset[1]/input')
        eng_max = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[2]/div[2]/fieldset[2]/input')
        eng_min.clear()
        eng_min.send_keys("5")
        eng_max.clear()
        eng_max.send_keys("100")
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[3]/div[2]/span[2]/label/span')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[4]/div[2]/span[2]/label/span[1]')
        time.sleep(0.5)
        fol_min = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[4]/div[3]/fieldset[1]/input')
        fol_max = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[4]/div[3]/fieldset[2]/input')
        fol_min.clear()
        fol_min.send_keys("40")
        fol_max.clear()
        fol_max.send_keys("1000")
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[3]/div/div[1]/span[2]/label/span[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[3]/div/div[1]/span[8]/label/span[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[4]')
        time.sleep(0.5)
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[3]/div/div[1]/span[121]/label/span[1]')
        cat_filter = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[2]/div/input')
        cat_filter.clear()
        cat_filter.send_keys("sandal")
        time.sleep(0.5)
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[3]/div/div[1]/span/label/span[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[6]/div[2]/span[3]/label/span')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[7]/div[2]/span[1]/label/span')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[8]/div[3]/div[1]/div[1]/span[6]/label/span[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[9]/div[3]/div[1]/div[1]/span[1]/label/span[1]')
        time.sleep(0.5)
        #we have succesfully selected all 11 filters
        self.assertEqual(driver.execute_script('return $(".applied_filters .filter").length'), 11)
        time.sleep(4)

    def do_test_filter_panel_bloggers(self):
        driver = self.driver
        eng_min = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[2]/div[2]/fieldset[1]/input')
        eng_max = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[2]/div[2]/fieldset[2]/input')
        eng_min.clear()
        eng_min.send_keys("5")
        eng_max.clear()
        eng_max.send_keys("100")
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[3]/div[2]/span[2]/label/span')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[4]/div[2]/span[2]/label/span[1]')
        time.sleep(0.5)
        fol_min = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[4]/div[3]/fieldset[1]/input')
        fol_max = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[4]/div[3]/fieldset[2]/input')
        fol_min.clear()
        fol_min.send_keys("40")
        fol_max.clear()
        fol_max.send_keys("1000")
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[3]/div/div[1]/span[2]/label/span[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[3]/div/div[1]/span[8]/label/span[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[4]')
        time.sleep(0.5)
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[3]/div/div[1]/span[121]/label/span[1]')
        cat_filter = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[2]/div/input')
        cat_filter.clear()
        cat_filter.send_keys("sandal")
        time.sleep(0.5)
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[5]/div[3]/div/div[1]/span/label/span[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[6]/div[2]/span[3]/label/span')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[7]/div[2]/span[1]/label/span')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[8]/div[3]/div[1]/div[1]/span[6]/label/span[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[9]/div[3]/div[1]/div[1]/span[1]/label/span[1]')
        time.sleep(0.5)
        #we have succesfully selected all 11 filters
        self.assertEqual(driver.execute_script('return $(".applied_filters .filter").length'), 11)
        time.sleep(4)


    def do_test_text_filters(self, wait_fn):
        driver = self.driver
        #filter bar - all
        filter_bar = driver.find_element_by_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/input')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div/ul/li[1]/a')
        filter_bar.clear()
        filter_bar.send_keys("fashion")
        time.sleep(4)
        wait_fn()

        #filter bar - keyword
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div/ul/li[2]/a')
        filter_bar.clear()
        filter_bar.send_keys("fashion")
        time.sleep(4)
        wait_fn()

        #filter bar - brand url
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div/ul/li[3]/a')
        filter_bar.clear()
        filter_bar.send_keys("jcrew.com")
        time.sleep(4)
        wait_fn()

        #filter bar - blogger's name
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div/ul/li[4]/a')
        filter_bar.clear()
        filter_bar.send_keys("judy")
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[2]/div/div/div[1]/div')
        time.sleep(4)
        wait_fn()

        #filter bar - blog name
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div/ul/li[5]/a')
        filter_bar.clear()
        filter_bar.send_keys("penny")
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[2]/div/div/div[3]/div')
        time.sleep(4)
        wait_fn()

        #filter bar - blog url
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[1]/ul/li[6]/a')
        filter_bar.clear()
        filter_bar.send_keys("penny")
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[2]/div/div/div/div')
        time.sleep(4)

        #filter bar - location
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div/ul/li[7]/a')
        filter_bar.clear()
        filter_bar.send_keys("london")
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[1]/span/div[2]/div/div/div[1]/div')
        time.sleep(4)
        wait_fn()


    def do_test_filters(self):
        driver = self.driver
        self._bloggers_loaded()
        self.do_test_filter_panel_bloggers()
        self._bloggers_loaded()

        #filters with bloggers are ok now, checking posts

        #clear filters
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[1]/div[1]/p/span')

        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[2]/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[2]/div[1]/ul/li[2]/a')

        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[2]/div[1]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[2]/fieldset[2]/div[1]/ul/li[1]/a')
        self.do_test_text_filters(self._bloggers_loaded)

    def do_test_competitors(self):
        driver = self.driver
        if not driver.execute_script('return $("body > span > span.ng-scope > div > div.nano.has-scrollbar > div.content.nano-content.side_bar_content > div.primary_nav > a:nth-child(4)").hasClass("selected")'):
            self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/a[3]')
            time.sleep(2)
        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element_by_css_selector('body'))
        actions.perform()
        time.sleep(2)
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/a[2]')
        time.sleep(2)
        self._wait_and_click_xpath('/html/body/span/span[2]/div[3]/div/div/div/div/a')

        time.sleep(2)
        competitor_url = driver.find_element_by_xpath('/html/body/span/span[2]/div[1]/div/div/div[2]/div/div/div/div/div/div/fieldset/input')
        competitor_url.clear()
        time.sleep(2)
        competitor_url.send_keys('zappos.com')
        time.sleep(15)

        for i in range(60):
            try:
                elm = driver.find_element_by_xpath("//li[%i]" % i)
                if "zappos.com" == elm.text: break
            except:
                pass
        elm.click()

        time.sleep(5)
        self._wait_and_click_xpath('/html/body/span/span[2]/div[1]/div/div/div[2]/div/div/div/div/div/input')
        time.sleep(5)

        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/span/div/fieldset/div')
        time.sleep(5)
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/span/div/fieldset/div/ul/li/a')
        time.sleep(5)
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/a[2]')
        time.sleep(5)
        self._bloggers_loaded()
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/a[3]')
        self._posts_loaded()
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/a[5]')
        self._posts_loaded()
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/a[6]')
        self._posts_loaded()
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/a[7]')
        self._posts_loaded()
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/div[2]/a[8]')
        self._posts_loaded()


    def do_test_outreach(self):
        driver = self.driver
        if not driver.execute_script('return $(".primary_nav>:nth-child(6)").hasClass("selected")'):
            self._wait_and_click_css('.primary_nav>:nth-child(6)')
            time.sleep(1)
        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element_by_css_selector('body'))
        actions.perform()
        self._wait_and_click_css('.primary_nav>:nth-child(7)>a:nth-child(1)')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.blogger_search_page.the_collections"))
        )
        while driver.execute_script('return $(".collection_outer_wrapper").length')>0:
            self._wait_and_click_css('.collection_outer_wrapper > div > div.icon-misc_files_trash4.delete_collection')
            self._wait_and_click_xpath('/html/body/span/span[2]/span/div[3]/div/div/div[2]/div/div/div/div/div/div/button[1]')
            time.sleep(1)

        self._wait_and_click_xpath('/html/body/span/span[2]/span/div[5]/div')
        self._wait_and_click_xpath('/html/body/span/span[2]/span/div[1]/div/div/div[2]/div/div/div/div/div/fieldset/div/input')
        collection_name = driver.find_element_by_xpath('/html/body/span/span[2]/span/div[1]/div/div/div[2]/div/div/div/div/div/fieldset/div/input')
        collection_name.clear()
        time.sleep(1)
        collection_name.send_keys(u'test collection with special characters 123!@#łąść')
        time.sleep(1)
        self._wait_and_click_xpath(u'/html/body/span/span[2]/span/div[1]/div/div/div[2]/div/div/div/div/div/input')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collection_outer_wrapper"))
        )
        self.assertTrue(driver.execute_script('return $(".collection_outer_wrapper").length') == 1)
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/a[1]')
        time.sleep(10)
        self._bloggers_loaded()
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[3]/div/span/div[1]/div[1]/div[1]/div[1]/div[2]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[2]/div/div[1]/div[2]/div[1]/div')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[3]')
        time.sleep(30)
        if not driver.execute_script('return $(".primary_nav>:nth-child(6)").hasClass("selected")'):
            self._wait_and_click_css('.primary_nav>:nth-child(6)')
            time.sleep(1)
        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element_by_css_selector('body'))
        actions.perform()
        self._wait_and_click_css('.primary_nav>:nth-child(7)>a:nth-child(1)')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collection_outer_wrapper"))
        )
        self.assertEqual("1", driver.find_element_by_css_selector("span.info").text)
        self._wait_and_click_xpath('/html/body/span/span[2]/span/div[5]/div[2]/a')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/span/span[2]/div[6]/div/table/tbody"))
        )
        self.assertTrue(driver.execute_script('return $(".favorited").length') == 1)

        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/a[1]')
        time.sleep(10)
        self._bloggers_loaded()
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[3]/div/span/div[1]/div[2]/div[1]/div[1]/div[2]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[2]/div/div[1]/div[2]/div[1]/div')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[3]')
        time.sleep(30)
        if not driver.execute_script('return $(".primary_nav>:nth-child(6)").hasClass("selected")'):
            self._wait_and_click_css('.primary_nav>:nth-child(6)')
            time.sleep(1)
        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element_by_css_selector('body'))
        actions.perform()
        self._wait_and_click_css('.primary_nav>:nth-child(7)>a:nth-child(1)')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collection_outer_wrapper"))
        )
        self.assertEqual("2", driver.find_element_by_css_selector("span.info").text)
        self._wait_and_click_xpath('/html/body/span/span[2]/span/div[5]/div[2]/a')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/span/span[2]/div[6]/div/table/tbody"))
        )
        self.assertTrue(driver.execute_script('return $(".favorited").length') == 2)

        if not driver.execute_script('return $(".primary_nav>:nth-child(6)").hasClass("selected")'):
            self._wait_and_click_css('.primary_nav>:nth-child(6)')
            time.sleep(1)
        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element_by_css_selector('body'))
        actions.perform()
        self._wait_and_click_css('.primary_nav>:nth-child(7)>a:nth-child(2)')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".campaign_boxes"))
        )
        while driver.execute_script('return $(".collection_outer_wrapper").length')>0:
            self._wait_and_click_css('div.icon-misc_files_trash4')
            self._wait_and_click_css('div.delete_collection.bs_tooltip.ng-isolate-scope > span > div > div > div.lightbox.dynamic > div > div > div > div > div > div > button.square_bt.teal_bt.sm.confirm_selection')
            time.sleep(1)
        self._wait_and_click_xpath('/html/body/span/span[2]/div[3]/div/div')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body > span > span.dashboard_content > div.campaign_setup"))
        )
        collection_name = driver.find_element_by_xpath('/html/body/span/span[2]/div[3]/form/div[2]/div[3]/fieldset[1]/input')
        collection_name.clear()
        time.sleep(1)
        collection_name.send_keys(u'test campaigns #$@#$łóąść')
        time.sleep(1)
        self._wait_and_click_xpath('/html/body/span/span[2]/div[3]/form/div[2]/div[20]/input')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body > span > span.dashboard_content > div.page_title_section > div.campaign_extras"))
        )
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/a[2]')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body > span > span.dashboard_content.camp_no_nav > div.public_post > div.centered_content > div > div > div.campaign_sect_left > div.section_title"))
        )
        if not driver.execute_script('return $(".primary_nav>:nth-child(6)").hasClass("selected")'):
            self._wait_and_click_css('.primary_nav>:nth-child(6)')
            time.sleep(1)
        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element_by_css_selector('body'))
        actions.perform()
        self._wait_and_click_css('.primary_nav>:nth-child(7)>a:nth-child(2)')

        self._wait_and_click_xpath('/html/body/span/span[2]/div[3]/div/div')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body > span > span.dashboard_content > div.campaign_setup"))
        )
        collection_name = driver.find_element_by_xpath('/html/body/span/span[2]/div[3]/form/div[2]/div[3]/fieldset[1]/input')
        collection_name.clear()
        time.sleep(1)
        collection_name.send_keys(u'campaign no collection')
        self._wait_and_click_xpath('/html/body/span/span[2]/div[3]/form/div[2]/div[20]/input')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body > span > span.dashboard_content > div.page_title_section > div.campaign_extras"))
        )
        self._wait_and_click_xpath('/html/body/span/span[1]/div/div[4]/div[1]/div[2]/a[1]')
        time.sleep(10)
        self._bloggers_loaded()

        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[3]/div/span/div[1]/div[1]/div[2]/div[1]/div[2]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[2]/div/div[1]/div[2]/div[2]/div')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[3]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[3]/div/span/div[1]/div[2]/div[2]/div[1]/div[2]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[2]/div/div[1]/div[2]/div[2]/div')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[3]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[3]/div[3]/div/span/div[1]/div[1]/div[3]/div[1]/div[2]')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[2]/div/div[1]/div[2]/div[2]/div')
        self._wait_and_click_xpath('//*[@id="bloggers_root"]/div[1]/div/div/div/div[2]/div/div/div/div/div[3]')
        time.sleep(30)
        if not driver.execute_script('return $(".primary_nav>:nth-child(6)").hasClass("selected")'):
            self._wait_and_click_css('.primary_nav>:nth-child(6)')
            time.sleep(1)
        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element_by_css_selector('body'))
        actions.perform()
        self._wait_and_click_css('.primary_nav>:nth-child(7)>a:nth-child(2)')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collection_outer_wrapper"))
        )
        self._wait_and_click_xpath('/html/body/span/span[2]/div[3]/div[2]/a')
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="bloggers_root"]/div[2]/div[2]/table/tbody'))
        )
        self.assertTrue(driver.execute_script('return $(".favorited").length') == 3)


    def test_e2e_brand_enterprise_noagency(self):
        driver = self.driver
        self.do_brand_enterprise_noagency()
        #self.do_test_filters()

        # you can skip cleaning up models in setup but you have to login then
        #self.login()
        #time.sleep(30)
        #self._bloggers_loaded()
        #self.do_test_competitors()
        self.do_test_outreach()

    def tearDown(self):
        self.xb.cleanup()
