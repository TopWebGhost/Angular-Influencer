from debra.constants import GMAIL_PROMOS_IMAPSERVER, GMAIL_PROMOS_USERNAME, GMAIL_PROMOS_PASSWORD
import imaplib
import datetime
import email

class GenericPromoGmailOps():
    '''
    a class for generic operations on our promo gmail account.
    credit for many of the functions here to http://yuji.wordpress.com/2011/06/22/python-imaplib-imap-example-with-gmail/
    '''
    def __init__(self):
        self._gmail_login()
        
    def _gmail_login(self):
        '''
        a function to log us into our gmail account for promotions and set this instances handle for the accound
        '''
        handle = imaplib.IMAP4_SSL(GMAIL_PROMOS_IMAPSERVER)
        handle.login('%s@gmail.com' % GMAIL_PROMOS_USERNAME, GMAIL_PROMOS_PASSWORD)
        handle.select("inbox")
        self.handle = handle

    #####-----< Private Methods >-----#####    
    def _raw_email_to_message(self, raw_email):
        '''
        a method to get the python EmailMessage for the raw data of a given email
        @param raw_email - the raw data to get the EmailMessage for
        @return an EmailMessage representation of the raw data
        '''
        return email.message_from_string(raw_email) if raw_email else None

    def _get_raw_email(self, id):
        '''
        a method to get the raw_data for an email given the email id
        @param id - the id of the email to get the raw data for
        @return email raw_data
        '''
        print "getting raw data for id ", id
        result, data = self.handle.fetch(id, "(RFC822)")        
        return data[0][1] if data[0] else None
    #####-----</ Private Methods >-----#####  
      
    #####-----< Public Methods >-----#####  
    def email_message_body(self, email_message):
        '''
        a method to get the body of an EmailMessage
        @param email_message - the EmailMessage to get the body of
        @return string representing the body of the email message
        '''
        if email_message is None:
            return ''
        elif isinstance(email_message, str):
            return email_message
        elif email_message.get_content_maintype() == "text":
            return email_message.get_payload()
        else:
            parts = email_message.get_payload()
            combined_parts = ''
            for part in parts:
                combined_parts += self.email_message_body(part.get_payload())
        
            return combined_parts
                
    
    def emails_since_yesterday(self):
        '''
        a method to get all emails in our inbox since yesterday
        @return EmailMessages for all emails since yesterday        
        '''
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")
        result, data = self.handle.uid('search', None, '(SENTSINCE {date})'.format(date=yesterday))
        email_ids = data[0].split()
        return [self._raw_email_to_message(self._get_raw_email(id)) for id in email_ids]
        
    #####-----</ Public Methods >-----#####
        
        
    
