'''
This file is for unit testing segments of the
application
'''
from django.test import TestCase, LiveServerTestCase
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from debra.models import Bloggers, Brands, UserProfile, Shelf, WishlistItem, ProductModel, WishlistItemShelfMap
from debra.tests.selenium_wrapper import Selenium
import random
import pdb

#####-----#####-----#####-----< Model Tests >-----#####-----#####-----#####





class TestUserModel(TestCase):
    '''
    Tests for our UserProfile model
    '''
    def setUp(self):
        self.fresh_user = User.objects.create_user(username="Tester@Test.com", email="Tester@Test.com", password="test").userprofile

        self.trendsetter_user = User.objects.create_user(username="TrendyTester@Test.com", email="TrendyTester@Test.com", password="test").userprofile
        self.trendsetter_user.can_set_affiliate_links = True
        self.trendsetter_user.is_trendsetter = True
        self.trendsetter_user.save()

    def tearDown(self):
        self.fresh_user.delete()
        self.fresh_user.user.delete()
        self.trendsetter_user.delete()
        self.trendsetter_user.user.delete()

    def test_default_user_configs(self):
        '''
        test that the user configurations for a fresh user are what they should be
        '''
        self.assertEqual(self.fresh_user.num_items_in_shelves, 0)
        self.assertEqual(self.fresh_user.num_items_from_supported_stores, 0)
        self.assertEqual(self.fresh_user.num_items_added_internally, 0)
        self.assertEqual(self.fresh_user.num_followers, 0)
        self.assertEqual(self.fresh_user.num_following, 0)
        self.assertEqual(self.fresh_user.num_shelves, 5) #the default shelves for a user
        self.assertEqual(self.fresh_user.user.username, self.fresh_user.user.email)

    def test_get_trendsetters(self):
        '''
        test the get trendsetters method
        '''
        self.assertIn(self.trendsetter_user, UserProfile.get_trendsetters())
        self.assertNotIn(self.fresh_user, UserProfile.get_trendsetters())




    #####-----< User Status Tests >-----#####
    def test_is_blogger(self):
        self.assertTrue(self.trendsetter_user.is_blogger)
        self.assertFalse(self.fresh_user.is_blogger)

    def test_has_social_links(self):
        '''
        test the has_social_links method
        '''
        self.assertFalse(self.fresh_user.has_social_links)

        #add a social link
        self.fresh_user.facebook_page = "http://www.facebook.com/testmeplz"
        self.fresh_user.save()

        self.assertTrue(self.fresh_user.has_social_links)

    def test_has_story(self):
        self.assertFalse(self.fresh_user.has_story)

        #add story
        self.fresh_user.aboutme = "blahblah"
        self.fresh_user.save()
        self.assertTrue(self.fresh_user.has_story)

        #remove story
        self.fresh_user.aboutme = None
        self.fresh_user.save()
        self.assertFalse(self.fresh_user.has_story)

    def test_has_style(self):
        self.assertFalse(self.fresh_user.has_style)

        #add style
        self.fresh_user.style_tags = "tag,tag2"
        self.fresh_user.save()
        self.assertTrue(self.fresh_user.has_style)

        #remove style
        self.fresh_user.style_tags = None
        self.fresh_user.save()
        self.assertFalse(self.fresh_user.has_style)

    def test_has_collage(self):
        self.assertFalse(self.fresh_user.has_collage)
        #add collage
        self.fresh_user.image1 = "http://image.jpg"
        self.fresh_user.save()
        self.assertTrue(self.fresh_user.has_collage)
        #remove collage
        self.fresh_user.image1 = None
        self.fresh_user.save()
        self.assertFalse(self.fresh_user.has_collage)
    #####-----</ User Status Tests >-----#####

    #####-----< External Model Queries Test >-----#####
    def test_non_deleted_category_shelves(self):
        test_shelf = Shelf.objects.create(name="test", user_id=self.fresh_user.user)
        self.assertIn(test_shelf, self.fresh_user.non_deleted_category_shelves)
        test_shelf.delete()

    def test_recently_shelved_items(self):
        test_product = ProductModel.objects.create()
        test_item = WishlistItem.objects.create(product_model=test_product, user_id=self.fresh_user.user)
        self.assertIn(test_item, self.fresh_user.recently_shelved_items)
        test_item.delete()
        test_product.delete()
    #####-----</ External Model Queries Test >-----#####

    #####-----< User Calculated Fields Tests >-----#####
    def test_profile_url(self):
        self.assertEqual(self.fresh_user.profile_url, "/%d/shelf/" % self.fresh_user.id)
    def test_stripped_email(self):
        self.assertEqual(self.fresh_user.stripped_email, "Tester")
        self.assertEqual(self.trendsetter_user.stripped_email, "TrendyTester")
    #####-----</ User Calculated Fields Tests >-----#####

    #####-----< Follower/Following Tests >-----#####
    def test_start_following(self):
        self.fresh_user.start_following(self.trendsetter_user)

        #num followers / num_following assertions
        self.assertEqual(self.fresh_user.num_following, 1)
        self.assertEqual(self.trendsetter_user.num_followers, 1)
        #is following assertions
        self.assertTrue(self.fresh_user.is_following(self.trendsetter_user))
        self.assertFalse(self.trendsetter_user.is_following(self.fresh_user))
        #get_following / get_followers assertions
        self.assertIn(self.fresh_user, [mapping.user for mapping in self.trendsetter_user.get_followers])
        self.assertIn(self.trendsetter_user, [mapping.following for mapping in self.fresh_user.get_following])

    def test_add_follower(self):
        self.trendsetter_user.add_follower(self.fresh_user)

        ###these assertions are the same as test_start_following as we've performed an converse operation to the start_following
        #num followers / num_following assertions
        self.assertEqual(self.fresh_user.num_following, 1)
        self.assertEqual(self.trendsetter_user.num_followers, 1)
        #is following assertions
        self.assertTrue(self.fresh_user.is_following(self.trendsetter_user))
        self.assertFalse(self.trendsetter_user.is_following(self.fresh_user))
        #get_following / get_followers assertions
        self.assertIn(self.fresh_user, [mapping.user for mapping in self.trendsetter_user.get_followers])
        self.assertIn(self.trendsetter_user, [mapping.following for mapping in self.fresh_user.get_following])

    def test_stop_following(self):
        self.fresh_user.start_following(self.trendsetter_user)
        self.fresh_user.stop_following(self.trendsetter_user)

        #num followers / num_following assertions
        self.assertEqual(self.fresh_user.num_following, 0)
        self.assertEqual(self.trendsetter_user.num_followers, 0)
        #is following assertions
        self.assertFalse(self.fresh_user.is_following(self.trendsetter_user))
        #get_following / get_followers assertions
        self.assertIn(self.fresh_user, [mapping.user for mapping in self.trendsetter_user.get_followers])
        self.assertIn(self.trendsetter_user, [mapping.following for mapping in self.fresh_user.get_following])

    #####-----</ Follower/Following Tests >-----#####


class TestShelfModel(TestCase):
    '''
    Tests for our Shelf model
    '''
    def setUp(self):
        self.fresh_user = User.objects.create_user(username="Tester@Test.com", email="Tester@Test.com", password="test").userprofile
        self.shelf = Shelf.objects.create(user_id=self.fresh_user.user, name="Bleh")
        self.brand = Brands.objects.create()
        self.product = ProductModel.objects.create(brand=self.brand)
        self.item = WishlistItem.objects.create(product_model=self.product, user_id=self.fresh_user.user)

    def tearDown(self):
        self.fresh_user.delete()
        self.fresh_user.user.delete()
        self.shelf.delete()
        self.item.delete()
        self.product.delete()
        self.brand.delete()

    #####-----< Default Configuration Tests >-----#####
    def test_defaults(self):
        self.assertTrue(self.shelf.is_public)
        self.assertFalse(self.shelf.is_deleted)
    #####-----</ Default Configuration Tests >-----#####

    #####-----< Calculated Property Tests >-----#####
    def test_items_in_shelf(self):
        self.assertTrue(len(self.shelf.items_in_shelf) == 0)
        #add an item to the shelf and retest
        mapping = WishlistItemShelfMap.objects.create(shelf=self.shelf, wishlist_item=self.item)
        self.assertIn(self.item, self.shelf.items_in_shelf)

        #simulate row delete and repeat assertion
        mapping.is_deleted = True
        mapping.save()

        self.assertNotIn(self.item, self.shelf.items_in_shelf)
        mapping.delete()
    #####-----</ Calculated Property Tests >-----#####

    #####-----< Query Tests >-----#####
    #####-----</ Query Tests >-----#####

    #####-----< Methods Tests >-----#####
    def test_add_item_to_self(self):
        IMG_URL = "http://asdlkjf/asdlkf.jpg"
        #give the wishlist item an img_url_thumbnail_view so we can test the automatic creation of shelf_img
        self.item.img_url_thumbnail_view = IMG_URL
        self.item.save()
        self.shelf.add_item_to_self(self.item)

        self.assertIn(self.item, self.shelf.items_in_shelf)
        self.assertEqual(self.shelf.shelf_img, IMG_URL)

    def test_remove_item_from_self(self):
        self.shelf.add_item_to_self(self.item)
        self.shelf.remove_item_from_self(self.item)

        self.assertNotIn(self.item, self.shelf.items_in_shelf)
    #####-----</ Methods Tests >-----#####





#####-----#####-----#####-----</ Model Tests >-----#####-----#####-----#####





#####-----#####-----#####-----< Selenium Tests >-----#####-----#####-----#####





class TestSelenium(LiveServerTestCase):
    '''
    Tests for bloggers
    '''
    @classmethod
    def setUpClass(cls):
        cls.selenium = Selenium()
        super(TestSelenium, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.selenium.close_driver()
        super(TestSelenium, cls).tearDownClass()

    def setUp(self):
        '''
        create each of the different types of bloggers
        '''
        self.selenium.go_to_url('{base}{url}'.format(base=self.live_server_url, url=reverse('debra.account_views.home')))
        self.selenium.maximize_window()
        self.test_user = User.objects.create_user(username="TrendyTester@Test.com", email="TrendyTester@Test.com", password="test").userprofile

    def tearDown(self):
        self.test_user.delete()
        self.test_user.user.delete()

    #####-----< Helpers >-----#####
    def live_test_url(self, url):
        return '{base}{url}'.format(base=self.live_server_url, url=reverse(url))

    def clear_inputs(self, inputs):
        [input.clear() for input in inputs]

    def xpath_formatter(self, container, inner_selector, use_id=False):
        return "//*[contains(@class, '{container}')]//*[contains({selector_type}, '{inner}')]".\
                format(container=container, selector_type="@id" if use_id else "@class", inner=inner_selector)

    #####-----</ Helpers >-----#####

    #####-----< Home Page Tests >-----#####
    def test_login(self):
        '''
        test the ability of the user to login
        '''
        ##Open dialog
        login_btn = self.selenium.find_by_id("login_btn")
        login_btn.click()

        self.selenium.wait(2)
        ##find username, password, error msg, and submit button fields then type in the various wrong inputs, verify failures
        username = self.selenium.find_by_xpath(self.xpath_formatter('login-popup', 'email'))[0]
        password = self.selenium.find_by_xpath(self.xpath_formatter('login-popup', 'id_password', use_id=True))[0]
        submit = self.selenium.find_by_xpath(self.xpath_formatter('login-popup', 'login_button'))[0]

        ##verify failures
        username.click()
        username.send_keys("blue")
        submit.click()
        email_error_msg = self.selenium.find_by_xpath(self.xpath_formatter('login-popup', 'nod_msg'))[0]
        self.assertTrue(email_error_msg.is_displayed())
        self.assertEqual(email_error_msg.text, "Please type a valid email")

        self.clear_inputs([username, password])
        username.send_keys("blue@sky.com")
        submit.click()
        password_error_msg = self.selenium.find_by_xpath(self.xpath_formatter('login-popup', 'nod_msg'))[0]
        self.assertTrue(password_error_msg.is_displayed())
        self.assertEqual(password_error_msg.text, "Please enter a value")

        self.clear_inputs([username, password])
        username.send_keys("blue@sky.com")
        password.send_keys("charlieday")
        submit.click()
        self.selenium.wait(3)
        validation_box_msg = self.selenium.find_by_xpath(self.xpath_formatter('login-popup', 'validation_box'))[0]
        self.assertTrue(validation_box_msg.is_displayed())
        self.assertEqual(validation_box_msg.text, "Bad email/password combo")

        ##verify correct result
        self.clear_inputs([username, password])
        username.send_keys(self.test_user.user.username)
        password.send_keys(self.test_user.user.password)
        submit.click()
        self.selenium.wait_until(10, lambda d: self.selenium.current_url() == self.live_test_url('debra.explore_views.inspiration'))
        self.assertEqual(self.selenium.current_url(), self.live_test_url('debra.explore_views.inspiration'))


    def test_signup(self):
        '''
        test the ability of a user to signup
        '''
        pass

    def test_brand_signup(self):
        '''
        test the ability of a brand to signup
        '''
        pass

    def test_forgot_password(self):
        '''
        test forgot password functionality
        '''
        pass
    #####-----</ Home Page Tests >-----#####





#####-----#####-----#####-----</ Selenium Tests >-----#####-----#####-----#####
