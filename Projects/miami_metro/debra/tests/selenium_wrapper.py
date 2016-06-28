from selenium.webdriver import Firefox
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait

class Selenium():
    '''
    encapsulation of selenium methods and properties used during testing
    '''
    def __init__(self):
        self.driver = None

    #####-----< Setup / Teardown >-----#####
    def go_to_url(self, url):
        '''
        a method to go to this ProductPage's url with the selenium driver
        @return - the selenium driver
        '''
        #get selenium driver
        self.driver = self.driver if self.driver else Firefox()
        self.driver.get(url)
        
    def maximize_window(self):
        '''
        maximize the window
        '''
        self.driver.maximize_window()
        
    def current_url(self):
        '''
        a method to return the current url
        @return - the current url of this driver
        '''
        return self.driver.current_url

    def close_driver(self):
        '''
        close this ProductPage's driver if it exists
        '''
        self.driver.quit() if self.driver else None
    #####-----</ Setup / Teardown >-----#####

    #####-----< Find Elements >-----#####
    def find_by_name(self, name):
        '''
        find elements on the page by name
        @return the found element
        '''
        return self.driver.find_element_by_name(name)
        
    def find_by_id(self, id):
        '''
        find elements on the page by their id
        @return the found element
        '''
        return self.driver.find_element_by_id(id)

    def find_by_link_text(self, text):
        '''
        find links on the page by their text
        @return the found element
        '''
        return self.driver.find_element_by_link_text(text)
        
    def find_by_class(self, css_class):
        '''
        find links on the page by their text
        @return the found element
        '''
        return self.driver.find_element_by_class_name(css_class)

    def find_by_xpath(self, xpath):
        '''
        find links on the page by their xpath
        @return the found element
        '''
        return self.driver.find_elements_by_xpath(xpath)
        #####-----</ Find Elements >-----#####
    
    #####-----< Synchronization >-----#####
    def wait(self, time):
        self.driver.implicitly_wait(time)
    
    def wait_until(self, time, condition_check):
        WebDriverWait(self.driver, 30).until(condition_check)
