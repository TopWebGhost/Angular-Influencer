import os
import sha
import uuid
import datetime
import copy
import base64
import json
import re
import itertools
from StringIO import StringIO
from collections import defaultdict, OrderedDict

import pydocusign

from django.core.urlresolvers import reverse, reverse_lazy
from django.conf import settings
from django.utils.text import Truncator

from debra.constants import *
from debra.helpers import update_json


class CustomDocuSignClient(pydocusign.DocuSignClient):

    def _create_envelope_from_document_request(self, envelope):
        if not self.account_url:
            self.login_information()
        url = '{account}/envelopes'.format(account=self.account_url)
        data = envelope.to_dict()
        bodies = []
        for document in envelope.documents:
            document_data = document.data
            document_data.seek(0)
            file_content = document_data.read()
            bodies.append(
                "--myboundary\r\n"
                "Content-Type:application/pdf\r\n"
                "Content-Disposition: file; "
                "filename=\"document.pdf\"; "
                "documentid={document_id} \r\n"
                "\r\n"
                "{file_data}\r\n".format(
                    document_id=document.documentId,
                    file_data=file_content)
            )

        body = str(
            "\r\n"
            "\r\n"
            "--myboundary\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n"
            "Content-Disposition: form-data\r\n"
            "\r\n"
            "{json_data}\r\n"
            "{file_bodies}"
            "--myboundary--\r\n"
            "\r\n".format(
                json_data=json.dumps(data), file_bodies="".join(bodies))
        )
        headers = self.base_headers()
        headers['Content-Type'] = "multipart/form-data; boundary=myboundary"
        headers['Content-Length'] = len(body)
        return {
            'url': url,
            'headers': headers,
            'body': body,
        }

    def post_sender_view(self, authenticationMethod=None,
                            clientUserId='', email='', envelopeId='',
                            returnUrl='', userId='', userName=''):
        """POST to {account}/envelopes/{envelopeId}/views/recipient.
        This is the method to start embedded signing for recipient.
        Return JSON from DocuSign response.
        """
        if not self.account_url:
            self.login_information()
        url = '/accounts/{accountId}/envelopes/{envelopeId}/views/sender' \
              .format(accountId=self.account_id,
                      envelopeId=envelopeId)
        if authenticationMethod is None:
            authenticationMethod = 'none'
        data = {
            'authenticationMethod': authenticationMethod,
            'clientUserId': clientUserId,
            'email': email,
            'envelopeId': envelopeId,
            'returnUrl': returnUrl,
            'userId': userId,
            'userName': userName,
        }
        return self.post(url, data=data, expected_status_code=201)


class ArbitraryTab(pydocusign.models.PositionnedTab):
    """PositionnedTab with arbitrary parameters."""

    def __init__(self, documentId=None, pageNumber=1, xPosition=0,
                 yPosition=0, recipientId=None, **kwargs):
        super(ArbitraryTab, self).__init__(
            documentId, pageNumber, xPosition, yPosition, recipientId)

        #: Arbitrary parameters
        for param, value in kwargs.items():
            if param in self.attributes:
                setattr(self, param, value)


def make_tab_class(class_name, base_class, tabs_name, *params):
    attributes = copy.copy(base_class.attributes)
    for param in params:
        if param not in attributes:
            attributes.append(param)
    params_dict = {
        'tabs_name': tabs_name,
        'attributes': attributes,
    }
    return type(class_name, (base_class,), params_dict)


ExtendedTab = make_tab_class(
    'ExtendedTab', ArbitraryTab, None, 'locked', 'value', 'name', 'fontSize',
    'font', 'height',)

DateTab = make_tab_class('DateTab', ExtendedTab, 'dateTabs')
NumberTab = make_tab_class('NumberTab', ExtendedTab, 'numberTabs')
TextTab = make_tab_class('TextTab', ExtendedTab, 'textTabs')
EditTextTab = make_tab_class('TextTab', ExtendedTab, 'textTabs', 'width')
DateSignedTab = make_tab_class('DateSignedTab', ExtendedTab, 'dateSignedTabs')


client = CustomDocuSignClient(
    root_url=DOCUSIGN_ROOT_URL,
    username=DOCUSIGN_USERNAME,
    password=DOCUSIGN_PASSWORD,
    integrator_key=DOCUSIGN_INTEGRATOR_KEY,
)

demo_client = CustomDocuSignClient(
    root_url=DOCUSIGN_TEST_ROOT_URL,
    username=DOCUSIGN_TEST_USERNAME,
    password=DOCUSIGN_TEST_PASSWORD,
    integrator_key=DOCUSIGN_TEST_INTEGRATOR_KEY,
)


login_information = client.login_information()


class ContractDocument(object):

    def __init__(self, input_buffer, labels=None, page_offsets=None, tabs=None):
        from reportlab.lib.styles import getSampleStyleSheet
        self.styles = getSampleStyleSheet()
        self.input_buffer = input_buffer
        self.output_buffer = None
        self.original_tabs = tabs
        if labels is None:
            labels = self._extract_labels_from_tabs(tabs)
        self.labels = labels
        self.tabs = [tab for tab in tabs if tab.tabs_name in DOCUSIGN_ALLOWED_TABS]

        paginated_labels = defaultdict(list)
        for label in self.labels:
            paginated_labels[int(label['pageNumber'])].append(label)

        self.labels = labels
        self.paginated_labels = paginated_labels
        self.pages_number = max(paginated_labels.keys() or [0])
        self.page_offsets = page_offsets or [(0, 0)] * self.pages_number

        self._put_text_fields()

    @staticmethod
    def _extract_labels_from_tabs(tabs):
        labels = []
        for tab in tabs:
            tab_dict = tab.to_dict()
            if not tab_dict.get('locked') or not tab_dict.get('value'):
                continue
            labels.append(tab_dict)
        return labels

    def _put_text_fields(self):
        from pyPdf import PdfFileWriter, PdfFileReader
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph

        packet = StringIO()
        can = canvas.Canvas(packet, pagesize=letter, bottomup=0)
        width, height = letter

        # for page_num, labels in self.paginated_labels.items():
        for page_num in xrange(self.pages_number):
            labels = self.paginated_labels.get(page_num + 1, [])
            for label in labels:
                font_size = int(re.findall('\d+', label['fontSize'])[0])
                print '* fontSize:', font_size
                can.setFont('Helvetica', font_size)
                if label['tabLabel'] == 'paragraph':
                    style = self.styles['BodyText']
                    p = Paragraph(
                        unicode(label['value'].strip().replace('\n','<br />\n')),
                        style=style
                    )

                    w, h = p.wrapOn(can, int(label['width']), height)
                    p.drawOn(
                        can,
                        int(label['xPosition']),
                        int(label['yPosition']) - h + 20,
                    )
                else:
                    can.drawString(
                        int(label['xPosition']) + self.page_offsets[page_num][0],
                        int(label['yPosition']) + self.page_offsets[page_num][1],
                        unicode(label['value'].strip())
                    )
            can.showPage()

        can.save()

        packet.seek(0)
        new_pdf = PdfFileReader(packet)
        existing_pdf = PdfFileReader(self.input_buffer)
        output = PdfFileWriter()
        
        self.output_buffer = StringIO()

        for page_num in xrange(existing_pdf.getNumPages()):
            page = existing_pdf.getPage(page_num)
            try:
                page.mergePage(new_pdf.getPage(page_num))
            except IndexError:
                pass
            output.addPage(page)

        output.write(self.output_buffer)


class ContractSender(object):

    def __init__(self, contract):
        from debra.models import Contract

        self.callback_url = ''.join([
            MAIN_DOMAIN, reverse('debra.job_posts_views.docusign_callback',)])
        if type(contract) == int:
            contract = Contract.objects.get(id=contract)
        self.contract = contract
        self.campaign = contract.campaign
        self.brand = contract.brand

        if type(contract) == Contract:
            self.blogger = contract.blogger
        # self.template_id = template_id or DOCUSIGN_TEMPLATE_ID
        self.template_id = self.campaign.docusign_template
        self.document_specific_tabs = defaultdict(OrderedDict)
        self._load_documents_from_template()
        self._create_docusign_documents()

    def _load_documents_from_template(self, start=1, skip=0):
        if self.template_id:
            data = demo_client.get_template(self.template_id)
        else:
            data = {}

        documents = []
        document_mapping = {}
        document_dicts = []
        tabs = []
        signer_tabs = {}
        common_attributes = set([
            'locked', 'value', 'name', 'fontSize', 'font', 'height', 'width',
            'tabLabel', 'required', 'pageNumber'])

        use_default_document = self.campaign.info_json.get(
            'use_default_document', True)

        # default_document_dict = get_default_document(self.contract)
        # if use_default_document:
        #     document_dicts.append(default_document_dict)

        if use_default_document:
            default_data = demo_client.get_template(
                site_configurator.instance.docusign_documents_json.get(
                    'default', {}).get('template_id'))
            document_dicts.extend(default_data['documents'])
            update_json(
                signer_tabs,
                copy.deepcopy(default_data['recipients']['signers'][0]['tabs']),
                extend_list=True
            )
        if data:
            document_dicts.extend(data['documents'][skip:])
            update_json(
                signer_tabs,
                copy.deepcopy(data['recipients']['signers'][0]['tabs']),
                extend_list=True
            )

        for n, document in enumerate(document_dicts, start=start):
            document_mapping[document['documentId']] = n

        # if data:
        #     signer_tabs = copy.copy(data['recipients']['signers'][0]['tabs'])
        #     if use_default_document:
        #         for tab_name, tabs_data in signer_tabs.items():
        #             tabs_data.extend(
        #                 default_document_dict.get('tabs').get(tab_name, []))
        # else:
        #     signer_tabs = copy.copy(default_document_dict.get('tabs'))

        for tab_name, tabs_data in signer_tabs.items():
            all_keys = set(itertools.chain(*[t.keys() for t in tabs_data]))
            class_keys = list(common_attributes.intersection(all_keys))
            tab_class = make_tab_class(
                str(tab_name), ArbitraryTab, tab_name, *class_keys)
            for tab in tabs_data:
                keys_set = set(tab.keys())
                for k in set(class_keys).difference(keys_set):
                    tab[k] = None                    
            for tab_data in tabs_data:
                if tab_data.get('value','').startswith(DOCUSIGN_SHELF_VARIABLE):
                    field_name = tab_data['value'].strip(
                        DOCUSIGN_SHELF_VARIABLE)
                    value = self.contract.get_docusign_field_value(
                        tab_data['documentId'], field_name)
                    self.document_specific_tabs[tab_data['documentId']][field_name] = value
                    tab_data['value'] = value
                document_id = document_mapping[tab_data['documentId']]
                tab_params = dict([
                    (k, v) for k, v in tab_data.items()
                    if k in tab_class.attributes
                ])
                tab_params['documentId'] = document_id
                # tab_params['name'] = str(uuid.uuid4())
                tabs.append(tab_class(**tab_params))

        for n, document in enumerate(document_dicts, start=1):
            try:
                raw_document = document['raw_document']
            except KeyError:
                raw_document = demo_client.get_envelope_document(
                    document['uri'].split('/')[2], document['documentId']).data
            documents.append(
                ContractDocument(
                    input_buffer=StringIO(raw_document),
                    tabs=[tab for tab in tabs if tab.documentId == n],
                    page_offsets=self.contract.get_docusign_page_offsets(
                        document['documentId']),
                )
            )

        # self.tabs = tabs
        # self.allowed_tabs = [
        #     tab for tab in tabs if tab.tabs_name in DOCUSIGN_ALLOWED_TABS]

        self.documents = documents

    def _create_docusign_documents(self):
        docusign_documents = []
        for n, document in enumerate(self.documents, start=1):
            docusign_documents.append(
                pydocusign.Document(
                    name='document_{}.pdf'.format(n),
                    documentId=n,
                    data=document.output_buffer
                )
            )
        self.docusign_documents = docusign_documents

    def create_and_send_envelope(self):
        from debra.models import Contract
        assert type(self.contract) == Contract

        self.contract.status = self.contract.STATUS_NON_SENT
        self.contract.save()

        event_notification = pydocusign.EventNotification(
            url=self.callback_url)

        if self.contract.info_json.get('agent_name'):
            signer_name = self.contract.info_json.get('agent_name')
        else:
            signer_name = self.contract.blogger.name or 'No blogger name'

        signer = pydocusign.Signer(
            email=self.blogger.emails[0],
            name=signer_name,
            recipientId=1,
            clientUserId=str(self.contract.id),
            tabs=self.tabs,
            emailSubject=Truncator(u'{} campaign contract for {}'.format(
                    self.campaign.title, self.blogger.name or 'No blogger name')).chars(50),
            emailBody=Truncator(u'Thanks for participating in the {}.'.format(
                self.campaign.title)).chars(50),
        )

        envelope = pydocusign.Envelope(
            documents=self.docusign_documents,
            emailSubject=Truncator(u'{} campaign contract for {}'.format(
                self.campaign.title, self.blogger.name or 'No blogger name')).chars(50),
            emailBlurb=Truncator(u'Thanks for participating in the {}.'.format(
                self.campaign.title, )).chars(50),
            eventNotification=event_notification,
            status=pydocusign.Envelope.STATUS_SENT,
            recipients=[signer]
        )
        client.create_envelope_from_document(envelope)

        self.contract.envelope = envelope.envelopeId
        self.contract.save()

    @property
    def tabs(self):
        return list(itertools.chain(*[doc.tabs for doc in self.documents]))