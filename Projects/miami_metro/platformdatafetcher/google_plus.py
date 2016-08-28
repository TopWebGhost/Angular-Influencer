from __future__ import absolute_import, division, print_function, unicode_literals
import json
import requests
from bs4 import BeautifulSoup
from requests.exceptions import SSLError
from xpathscraper.utils import nestedget, browser_headers


def clean_html(html):
    if html is None:
        return None

    soup = BeautifulSoup(html)
    return soup.get_text()


class GPlusProfile(object):
    def __init__(self, data):
        self._data = data

        # Most of the indexes taken from https://github.com/gyurisc/dotnet.googleplus/blob/master/GooglePlus/GooglePlusService.cs
        # They seem stable and haven't changed for the 4-5 years.
        self.id = self._get_field(1, 0)
        self.first_name = clean_html(self._get_field(1, 2, 4, 1))
        self.last_name = clean_html(self._get_field(1, 2, 4, 2))
        self.full_name = clean_html(self._get_field(1, 2, 4, 3))
        self.other_names = [clean_html(name_info[0]) for name_info in self._get_list(1, 2, 5, 1)]

        self.introduction = clean_html(self._get_field(1, 2, 14, 1))
        self.tagline = clean_html(self._get_field(1, 2, 33, 1))

        self.location = self._get_field(1, 2, 9, 1)

        self.emails = [entry for entry, _ in self._get_list(1, 2, 12, 9)]

        self.gender = self._decode_gender(self._get_field(1, 2, 17, 1))

        profiles1 = [(entry[3], entry[1]) for entry in self._get_list(1, 2, 51, 0)]
        profiles2 = [(entry[3], entry[1]) for entry in self._get_list(1, 2, 72, 0, 0)]
        self.profiles = profiles1 + profiles2

        self.sites = [(entry[3], entry[1]) for entry in self._get_list(1, 2, 52, 0)]
        self.links = [(entry[3], entry[1]) for entry in self._get_list(1, 2, 53, 0)]

        #[(entry[3], entry[1]) for entry in p._get_list(1, 2, 72, 0, 0)]

    def _get_field(self, *indexes):
        return nestedget(self._data, *indexes)

    def _get_list(self, *indexes):
        return self._get_field(*indexes) or []

    def _decode_gender(self, gender_value):
        if not gender_value:
            return None
        elif gender_value == 1:
            return 'Male'
        elif gender_value == 2:
            return 'Female'
        else:
            return unicode(gender_value)


class GPlusService(object):
    profile_url = 'https://plus.google.com/_/profiles/get/{0}'

    def get_profile(self, profile_id):
        if not profile_id.isdigit() and not profile_id.startswith('+'):
            profile_id = '+' + profile_id

        url = self.profile_url.format(profile_id)
        try:
            response = requests.get(url, headers=browser_headers())
        except SSLError:
            # trying to fetch it with verify=True if we encounter SSLError
            response = requests.get(url, headers=browser_headers(), verify=False)
        return self.parse_profile(response.content.decode('utf-8'))

    def parse_profile(self, js_data):
        cleaned = self._clean_up_js(js_data)
        parsed = json.loads(cleaned)

        # throw away parsed[1] -- seems like junk data
        profile = GPlusProfile(parsed[0])
        return profile

    def _clean_up_js(self, js_data):
        '''
        Port of the CleanupGoogleJSON object here:
        https://github.com/gyurisc/dotnet.googleplus/blob/master/GooglePlus/GoogleUtils.cs
        '''
        # Clean up Anti-XSS junk at the beginning
        if len(js_data) > 5:
            js_data = js_data[5:]

        last_char = None
        in_string = False
        in_escape = False

        result = []

        for current_char in js_data:
            if current_char.isspace() and not in_string:
                continue

            if in_string:
                if in_escape:
                    result.append(current_char)
                    in_escape = False
                elif current_char == '\\':
                    result.append(current_char)
                    in_escape = True
                elif current_char == '"':
                    result.append(current_char)
                    in_string = False
                else:
                    result.append(current_char)

                last_char = current_char
                continue

            if current_char == '"':
                result.append(current_char)
                in_string = True
            elif current_char == ',':
                if last_char == ',' or last_char == '[' or last_char == '{':
                    result.append('null')
                result.append(current_char)
            elif current_char == ']' or current_char == '}':
                if last_char == ',':
                    result.append('null')
                result.append(current_char)
            else:
                result.append(current_char)

            last_char = current_char

        return ''.join(result)
