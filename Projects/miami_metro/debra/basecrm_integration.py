__author__ = 'shelfops'

"""
    Simple helper methods for interacting with the BASE CRM.
"""

import basecrm
from django.conf import settings
from django.core.mail import mail_admins


def get_client():
    return basecrm.Client(access_token=settings.BASECRM_TOKEN)


def create_lead(first_name, last_name, organization_name, organization_url, email, phone_number=None):
    try:
        client = get_client()
        print("Organization name: %r" % (organization_url + '<:>' + first_name))
        lead = client.leads.create(organization_name=organization_url + '<:>' + first_name)
        print("Created lead")
        lead.website = organization_url
        lead.first_name = first_name
        lead.last_name = "TBD (fix later)"
        lead.email = email
        if phone_number:
            lead.phone = phone_number
        client.leads.update(lead.id, lead)
        print("Success, lead created withid %r" % lead.id)
    except Exception as e:
        # send email to admins about this error
        print("Problem in creating a BASE lead for %r, sending info in an email [%r]" % (email, e))
        mail_admins("Problem in BASE CRM lead %r " % email, "More info:\n[%r] [%r] [%r] [%r] [%r]" % (first_name,
                                                                                                      last_name,
                                                                                                      organization_name,
                                                                                                      organization_url,
                                                                                                      email))
        pass


