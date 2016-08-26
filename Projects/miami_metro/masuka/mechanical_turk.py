from debra.constants import HOUDINI_API_KEY, HOUDINI_URL, HOUDINI_PROMO_IMAGE_TASK, HOUDINI_PROMO_EMAIL_TASK
from debra.models import MechanicalTurkTask
from generic_email_ops import GenericPromoGmailOps
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.http import HttpResponse
import pdb
import requests
import json


class MechanicalTurk():
    '''
    a class for encapsulating mechanical turk logic
    '''
    def __init__(self):
        self.gmail_handle = GenericPromoGmailOps()
        
    #####-----< Private Methods >-----#####
    def _send_houdini_task(self, task, input):
        '''
        abstract method for sending a task to houdini
        @return the newly created mechanical turk task
        '''
        params = { 'api_key': HOUDINI_API_KEY,
                   'environment': 'sandbox',
                   'postback_url': "http://alpha-getshelf.herokuapp.com%s" % reverse('masuka.mechanical_turk.process_response'),
                   'blueprint': task,
                   'input': input }        
        response = requests.post('%s/tasks.json' % HOUDINI_URL, data=json.dumps(params))
        pdb.set_trace()
        #save the task info into our database
        response_json = response.json()
        
        return MechanicalTurkTask.objects.create(task_type=task, task_id=response_json['id'], status=response_json['status'])
    
    def _promo_emails_since_yesterday(self):
        '''
        method to get all promotional emails sent since yesterday
        @return a list of the email message bodie's
        '''
        emails = self.gmail_handle.emails_since_yesterday()
        return [self.gmail_handle.email_message_body(email) for email in emails]
    #####-----</ Private Methods >-----#####

    #####-----< Public Methods >-----#####    
    def send_images(self, img_paths):
        '''
        a function to send mechanical turk the promo images for processing
        NOTE: not mapped by urls.py, should be called explicitly from a shell or other function
        '''
        paths = img_paths.split(',')
        
        for path in paths:
            self._send_houdini_task(HOUDINI_PROMO_IMAGE_TASK, {'image_url': path})                        
        
    def send_emails(self, emails):
        '''
        a function to send mechanical turk a list of emails for processing of promotions
        NOTE: not mapped by urls.py, should be called explicitly from a shell or other function
        @param emails - email messages (body only) to send to mechanical turk for processing
        '''
        NUM_EMAILS_PER_PAGE = 1
        pages = []        
        
        print "creating pages of emails.."
        #create "pages" of emails
        for i in range(0, len(emails) / NUM_EMAILS_PER_PAGE): 
            lower_slice, upper_slice = (i * NUM_EMAILS_PER_PAGE, (i + 1) * NUM_EMAILS_PER_PAGE)
            pages.append(emails[lower_slice:upper_slice])

        #for each of the pages, send the page - in string form - to mechanical turk for processing
        print "sending pages to houdini.."
        page_delimiter = "<br /><br /><br /><br />++++++++++++++++++++$$$$$$$$$$$$$$$$$$+++++++++++++++++++<br /><br /><br /><br />"
        for page in pages:
            page_as_string = page_delimiter.join(page)
            self._send_houdini_task(HOUDINI_PROMO_EMAIL_TASK, {'emails': page_as_string}) 
    
    def check_status(self):
        '''
        a function to check the status of mechanical turk pending processes
        NOTE: not mapped by urls.py, should be called explicitly from a shell or other function
        '''
        processing_tasks = MechanicalTurkTask.objects.exclude(status="complete")
        for task in processing_tasks:
            r = requests.get('%s/tasks/%s.json?api_key=%s' % (HOUDINI_URL, task.task_id, HOUDINI_API_KEY))
            #later we can do more with this
            print 'Input: %s // Status: %s // Output: %s' % (r['input'], r['status'], r['output'])
    #####-----</ Public Methods >-----#####
            
            
def process_response(request):
    '''
    a function to process the postback response from mechanical turk
    '''
    send_mail("Mechanical Turk Done" , "Mechanical turk finished processing", "atul@theshelf.com", ['atul@theshelf.com'], fail_silently=False)
    
    #update the mechanical turk task in our db
    try:
        task = MechanicalTurkTask.objects.get(task_id=request.POST.get('id'))
        task.status = request.POST.get('status')
        task.save()
    except ObjectDoesNotExist:
        pass
    
    return HttpResponse(status=200)


