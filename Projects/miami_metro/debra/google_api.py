import os
import logging
import httplib2

from django.conf import settings

from oauth2client.service_account import ServiceAccountCredentials
from apiclient.discovery import build

from debra import constants

KEYFILE_LOCATION = os.path.join(
    settings.PROJECT_PATH, 'debra/jsons/google_api/keyfile.json')
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    # 'https://www.googleapis.com/auth/drive.file',
]

from oauth2client.service_account import ServiceAccountCredentials


def get_credentials():
    return ServiceAccountCredentials.from_json_keyfile_name(
        KEYFILE_LOCATION, scopes=SCOPES)


def build_service(credentials=None):
    if credentials is None:
        credentials = get_credentials()
    http_auth = credentials.authorize(httplib2.Http(
        disable_ssl_certificate_validation=True))
    return build('drive', 'v2', http=http_auth)
