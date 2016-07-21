from debra import helpers as h
from debra.models import ProductModel, Influencer
from debra.constants import *
from debra.forms import ContactUsForm
from debra import helpers as h
from django.http import HttpResponse
import logging


logger = logging.getLogger('miami_metro')



#####-----< EMAIL VIEWS >-----#####
def lottery_winner(request, user=0, lottery=0):
    '''atuls code here'''
    pass

def brand_email_influencer(request, influencer=0):
    '''
    this view is for when a brand wants to email an influencer about an opportunity
    @param influencer - the influencer to email
    request has:
    -request.user.userprofile.brand: the brand doing the emailing
    '''
    inf = Influencer.objects.get(id=influencer)
    b = request.user.userprofile.brand

    contact_form = ContactUsForm(data=request.POST)
    if contact_form.is_valid():
        name, email = contact_form.cleaned_data.get('name'), contact_form.cleaned_data.get('email')
        subject, message= contact_form.cleaned_data.get('subject'), contact_form.cleaned_data.get('message')
        recipients = [{'name': 'Atul', 'email': ATUL_EMAILS['admin_email']},
                      {'name': 'Lauren', 'email': LAUREN_EMAILS['admin_email']}]

        h.send_mandrill_email(to=recipients, _from={'name': name, 'email': email},
                            subject=subject, message_type='brand', message_name='blogger_contact',
                            tpl_vars={
                                'message': message,
                                'influencer': inf,
                                'brand': b,
                                'email': email
                            })
        return HttpResponse(status=200)

