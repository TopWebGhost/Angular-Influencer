import unittest
import time
from xpathscraper.xbrowser import XBrowser
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from debra.models import User, Influencer
import helpers


class RegisterBlogger(unittest.TestCase):
    def setUp(self):
        self.base_url = "http://localhost:8000"
        self.server = helpers.ServerRunner()
        self.server.mock_fn('debra.account_helpers.send_mail')
        self.server.mock_fn('registration.models.RegistrationProfile.send_activation_email')
        self.server.mock_fn('platformdatafetcher.fetcher.create_platforms_from_urls')
        self.server.run()

        try:
            User.objects.get(email="john@taigh.eu").delete()
        except:
            pass
        try:
            Influencer.objects.get(blog_url__icontains="taigh.eu").delete()
        except:
            pass

        self.wait_timeout = 120
        self.xb = XBrowser()
        self.driver = self.xb.driver

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
        driver.find_element_by_id("login_form_id_1").send_keys("john@taigh.eu")
        driver.find_element_by_id("login_form_id_2").clear()
        driver.find_element_by_id("login_form_id_2").send_keys("test")
        driver.find_element_by_xpath("(//input[@value='Submit!'])[2]").click()

    def do_fill_register_form(self):
        driver = self.driver
        driver.get(self.base_url)
        WebDriverWait(driver, self.wait_timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".log_sign_corner > a:nth-child(1)"))
        )
        driver.find_element_by_css_selector(".log_sign_corner > a:nth-child(1)").click()
        WebDriverWait(driver, self.wait_timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.user_title"))
        )
        driver.find_element_by_css_selector("div.user_title").click()
        driver.find_element_by_id("blogger_signup_id_1").clear()
        driver.find_element_by_id("blogger_signup_id_1").send_keys("taigh")
        driver.find_element_by_id("blogger_signup_id_2").clear()
        driver.find_element_by_id("blogger_signup_id_2").send_keys("john@taigh.eu")
        driver.find_element_by_id("blogger_signup_id_3").clear()
        driver.find_element_by_id("blogger_signup_id_3").send_keys("test")
        driver.find_element_by_id("blogger_signup_id_4").clear()
        driver.find_element_by_id("blogger_signup_id_4").send_keys("taigh")
        driver.find_element_by_id("blogger_signup_id_5").clear()
        driver.find_element_by_id("blogger_signup_id_5").send_keys("taigh.eu")
        driver.find_element_by_xpath("(//input[@value='Submit!'])[2]").click()
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body > div.lightbox.dynamic.bl_bg_lb.w_logo"))
        )
        self.assertEqual("Wonderful! We just sent you an email.", driver.find_element_by_css_selector(".lb_title").text)

        #mock checks
        self.assertTrue(self.server.mock_called('registration.models.RegistrationProfile.send_activation_email'))

        #post register db checks
        self.assertTrue(User.objects.filter(email="john@taigh.eu").count() == 1)
        user = User.objects.get(email="john@taigh.eu")
        user_profile = user.userprofile
        self.assertFalse(user_profile is None)

    def do_email_activation(self):
        driver = self.driver
        user = User.objects.get(email="john@taigh.eu")
        activation_key = user.registrationprofile_set.all()[0].activation_key

        #email activation
        driver.get("%s/accounts/activate/%s/" % (self.base_url, activation_key))
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body div.content_area .page_lb_title"))
        )
        self.assertEqual("Last Step!", driver.find_element_by_css_selector(".page_lb_title").text)

    def do_blog_verification(self):
        #blogger verification
        driver = self.driver
        driver.find_element_by_css_selector("div.badge:nth-child(2)").click()
        driver.find_element_by_xpath("//input[@value=\"Done, it's up!\"]").click()
        for i in range(self.wait_timeout):
            try:
                if "Request sent, we will email you in few minutes." == driver.find_element_by_css_selector("h1.lb_title.lg").text:
                    break
            except:
                pass
            time.sleep(1)
        else:
            self.fail("time out")

        #mock assertions
        self.assertTrue(self.server.mock_called('debra.account_helpers.send_mail'))
        self.assertTrue(self.server.mock_called('platformdatafetcher.fetcher.create_platforms_from_urls'))

        #post verification db checks
        user = User.objects.get(email="john@taigh.eu")
        user_profile = user.userprofile
        self.assertTrue(Influencer.objects.filter(blog_url__icontains="taigh.eu").count() == 1)
        influencer = Influencer.objects.get(blog_url__icontains="taigh.eu")
        self.assertEqual(influencer, user_profile.influencer)
        self.assertEqual(influencer.shelf_user, user)
        self.assertTrue(user_profile.blog_verified)

        self.logout()
        self.login()
        #verified blogger screen
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body > div.lightbox.dynamic.bl_bg_lb.w_logo"))
        )
        self.assertEqual("Awesome!", driver.find_element_by_css_selector(".lb_title").text)

        #logout
        self.logout()

    def do_blogger_profile_check(self):
        #testing ready to invite
        driver = self.driver
        influencer = Influencer.objects.get(blog_url__icontains="taigh.eu")
        influencer.ready_to_invite = True
        influencer.save()

        self.login()
        time.sleep(30)
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/span/span/span/div[1]/div/div[1]/div[2]/h1[1]/span[1]"))
        )
        self.assertEqual("taigh", driver.find_element_by_xpath("/html/body/span/span/span/div[1]/div/div[1]/div[2]/h1[1]/span[1]").text)


        #edit page test
        driver.find_element_by_css_selector(".prof_block .simple_follow_btn").click()
        driver.implicitly_wait(5)
        driver.find_element_by_name("blogname").clear()
        driver.find_element_by_name("blogname").send_keys("taigh test")
        driver.find_element_by_name("emails").clear()
        driver.find_element_by_name("emails").send_keys("someemail@domain.com")
        driver.find_element_by_id("location").clear()
        driver.find_element_by_id("location").send_keys("lublin")
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.pac-item:nth-child(1)"))
        )
        driver.find_element_by_css_selector("div.pac-item:nth-child(1)").click()
        driver.find_element_by_name("bio").clear()
        driver.find_element_by_name("bio").send_keys("bio")
        driver.execute_script('$(window).scrollTop($("div.checkbox_col:nth-child(1) > div:nth-child(1)").position().top)')
        driver.find_element_by_css_selector("span.graphic.plus_btn").click()
        driver.find_element_by_xpath("//div[3]/div/div[4]/label/span").click()
        driver.find_element_by_xpath("//div[4]/div/div[9]/label/span").click()
        driver.find_element_by_xpath("//div[10]/label/span").click()
        driver.find_element_by_xpath("//div[2]/div[2]/div/div[3]/label/span").click()
        driver.find_element_by_xpath("//div[2]/div[3]/div/div[7]/label/span").click()
        driver.find_element_by_xpath("//div[2]/div[3]/div/div[2]/label/span").click()
        driver.find_element_by_xpath("//div[2]/div[2]/div/div[10]/label/span").click()
        driver.execute_script('$(window).scrollTop($("div.account_title:nth-child(13)").position().top)')
        driver.find_element_by_css_selector("span.ng-scope > label.floater.ng-binding > span.graphic.plus_btn").click()
        driver.find_element_by_xpath("//span[6]/label/span").click()
        driver.find_element_by_xpath("//span[2]/label/span").click()
        driver.find_element_by_xpath("//span[7]/label/span").click()
        driver.find_element_by_xpath("(//input[@name='range_min'])[2]").clear()
        driver.find_element_by_xpath("(//input[@name='range_min'])[2]").send_keys("25")
        driver.find_element_by_xpath("(//input[@name='range_max'])[3]").clear()
        driver.find_element_by_xpath("(//input[@name='range_max'])[3]").send_keys("50")
        driver.find_element_by_xpath("(//input[@name='range_min'])[4]").clear()
        driver.find_element_by_xpath("(//input[@name='range_min'])[4]").send_keys("23")
        driver.find_element_by_xpath("(//input[@name='range_max'])[4]").clear()
        driver.find_element_by_xpath("(//input[@name='range_max'])[4]").send_keys("100")
        driver.find_element_by_xpath("(//input[@name='name'])[2]").clear()
        driver.find_element_by_xpath("(//input[@name='name'])[2]").send_keys("test")
        driver.find_element_by_xpath("(//input[@name='name'])[3]").clear()
        driver.find_element_by_xpath("(//input[@name='name'])[3]").send_keys("test")
        driver.execute_script('$(window).scrollTop($("fieldset.clearit:nth-child(3) > div:nth-child(1)").position().top)')
        driver.find_element_by_name("collaboration_types").clear()
        driver.find_element_by_name("collaboration_types").send_keys("something about me")
        driver.find_element_by_name("how_you_work").clear()
        driver.find_element_by_name("how_you_work").send_keys("details")
        driver.execute_script('$(window).scrollTop($("div.account_title:nth-child(17)").position().top)')
        driver.find_element_by_id("id_brandname").clear()
        driver.find_element_by_id("id_brandname").send_keys("test")
        driver.find_element_by_name("brandurl").clear()
        driver.find_element_by_name("brandurl").send_keys("test.com")
        driver.find_element_by_name("posturl").clear()
        driver.find_element_by_name("posturl").send_keys("test.com")
        driver.find_element_by_id("campaign_date").click();
        WebDriverWait(driver, self.wait_timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".datepicker-days > table:nth-child(1) > tbody:nth-child(2) > tr:nth-child(5) > td:nth-child(7)"))
        )
        driver.find_element_by_css_selector(".datepicker-days > table:nth-child(1) > tbody:nth-child(2) > tr:nth-child(5) > td:nth-child(7)").click()
        driver.find_element_by_name("details").clear()
        driver.find_element_by_name("details").send_keys("ok")
        driver.find_element_by_xpath("/html/body/span/span/div/div/form/div/fieldset[4]/div").click()
        WebDriverWait(driver, self.wait_timeout).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/span/span/div/div/form/div/fieldset[4]/div/ul/li[2]/a"))
        )
        driver.find_element_by_xpath("/html/body/span/span/div/div/form/div/fieldset[4]/div/ul/li[2]/a").click()
        driver.find_element_by_css_selector("button.square_bt:nth-child(2)").click()
        driver.find_element_by_xpath("//div[20]/button").click()
        #waiting to back to profile page
        WebDriverWait(driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/span/span/span/div[1]/div/div[1]/div[2]/h1[1]/span[1]"))
        )
        # post mortem checks here


    def test_e2e_blogger(self):
        self.do_fill_register_form()
        self.do_email_activation()
        self.do_blog_verification()
        self.do_blogger_profile_check()

    def tearDown(self):
        self.xb.cleanup()
