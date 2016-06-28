'''
this file contains logger logic. The logger will enable us to better analyze test results without 
having to examine and restart the tests every time an assertion fails
'''

class Logger():
    def __init__(self, test_type):
        self.test_type = test_type
        
        
