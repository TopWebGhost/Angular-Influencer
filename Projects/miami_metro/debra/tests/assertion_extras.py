'''
this class holds custom logic that extends the capabilities of unittest Assertions
'''


def equal_with_threshold(value, expected, threshold=3, case_sensitive=False):
    '''
    this method tests whether two strings are equal with an allowance of characters that can be different. 
    @param value - string to test
    @param expected - string we expect
    @param threshold - amount of characters we are willing to "forgive"
    @param case_sensitive - should the comparison be case sensitive
    @return boolean indicating whether the two strings are equal within the threshold
    '''
    #if the given value isn't a string, do a normal equality comparison
    print "VALUE IS", value
    print "EXPECTED IS", expected
    if not isinstance(value, str) or not isinstance(expected, str):
        return value == expected
    else:
        value_chars = list(value)
        expected_chars = list(expected)    
        
        for i in range(0, len(value_chars)):            
            value_letter = value_chars[i].lower() if not case_sensitive else value_chars[i]
            expected_letter = expected_chars[i].lower() if not case_sensitive else expected_chars[i]
            
            #if this letter is the same in both strings, go to the next iteration
            if value_letter == expected_letter:
                continue
            elif threshold > 0:
                threshold -= 1
            else:
                return False
            
        return True
            
    
                
        
        
