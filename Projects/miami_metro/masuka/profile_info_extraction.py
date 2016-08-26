__author__ = 'atulsingh'

from celery.decorators import task
import requests
from debra.models import UserProfile, Influencer, Platform
from masuka import image_manipulator
from debra.constants import *

API_KEYS = ['2cc0091740f91360']
FULL_CONTACT_PERSON_URL = 'https://api.fullcontact.com/v2/person.json'

class FullContactWrapper():
    '''
    A class that wraps the calls to FullContact service to fetch info about users
    '''
    def __init__(self):
        self.api_key = API_KEYS[0]

    def _call_api(self, email):
        response = requests.get('%s?apiKey=%s&email=%s&style=%s' % (FULL_CONTACT_PERSON_URL, self.api_key, email, 'dictionary'))
        if response.status_code != 200:
            return response.status_code, None, None, None, None, None, None, None, None, None, None, None
        response_json = response.json()
        status = response_json['status']
        img_url = None
        platform_name = None
        full_name = None
        gender = None
        age = None
        age_range = None
        location = None
        facebook_profile = None
        pinterest_profile = None
        twitter_profile = None
        instagram_profile = None
        if status == 200:
            for k in response_json.keys():
                print k, response_json[k]
            # first get the profile pictures
            photos = response_json['photos'] if 'photos' in response_json.keys() else {}
            for k in photos.keys():
                if photos[k][0]['isPrimary']:
                    img_url = photos[k][0]['url']
                    platform_name = photos[k][0]['typeName']
                    break
            # now get the social handles
            socialProfiles = response_json['socialProfiles'] if 'socialProfiles' in response_json.keys() else {}
            for k in socialProfiles.keys():
                prof_url = socialProfiles[k][0]['url']
                if k == 'facebook':
                    facebook_profile = prof_url
                if k == 'twitter':
                    twitter_profile = prof_url
                if k == 'pinterest':
                    pinterest_profile = prof_url
                if k == 'instagram':
                    instagram_profile = prof_url

            contactinfo = response_json['contactInfo'] if 'contactInfo' in response_json.keys() else None
            demographics = response_json['demographics'] if 'demographics' in response_json.keys() else None
            full_name = contactinfo['fullName'] if contactinfo and 'fullName' in contactinfo.keys() else None
            gender = demographics['gender'] if demographics and 'gender' in demographics.keys() else None
            age = demographics['age'] if demographics and 'age' in demographics.keys() else None
            age_range = demographics['ageRange'] if demographics and 'ageRange' in demographics.keys() else None
            location = demographics['locationGeneral'] if demographics and 'locationRange' in demographics.keys() else None

        print status, img_url, platform_name, full_name, gender, age, age_range, location, facebook_profile, \
               pinterest_profile, twitter_profile, instagram_profile
        return status, img_url, platform_name, full_name, gender, age, age_range, location, facebook_profile, \
               pinterest_profile, twitter_profile, instagram_profile

    def fetch_person_info(self, user_profile):
        email = user_profile.user.email
        status, img_url, platform_name, full_name, gender, age, age_range, location, fb, pin, tw, insta = self._call_api(email)
        if status is not 200:
            print "Ooops, FullContact API returned {status}".format(status=status)
            return
        image_updated = False
        if img_url and user_profile.profile_img_url is None:
            user_profile.profile_img_url = img_url
            image_updated = True

        user_profile.is_female = True if (gender and gender == "Female") else False
        user_profile.location = location if location and user_profile.location is None else user_profile.location
        #user_profile.name = full_name if full_name and (not user_profile.name) or \
        #                                 (user_profile.name and user_profile.name is not full_name) else user_profile.name
        user_profile.facebook_page = fb if fb and user_profile.facebook_page is None else user_profile.facebook_page
        user_profile.twitter_page = tw if tw and user_profile.twitter_page is None and tw else user_profile.twitter_page
        user_profile.pinterest_page = pin if pin and user_profile.pinterest_page is None else user_profile.pinterest_page
        user_profile.instagram_page = insta if insta and user_profile.instagram_page is None else user_profile.instagram_page
        user_profile.age = int(age) if age else 0
        user_profile.save()

        if image_updated:
            image_manipulator.save_external_profile_image_to_s3(user_profile)

        # this method will now set the influencer object for this user profile and set the platforms
        # user_profile.enable_data_crawling()

    def fetch_influencer_info(self, influencer):
        '''
        Fetch the info for a given influencer & then create Platform objects for each
        '''
        email = influencer.email
        status, img_url, platform_name, full_name, gender, age, age_range, location, fb, pin, tw, insta = self._call_api(email)
        if status is not 200:
            print "Ooops, FullContact API returned {status}".format(status=status)
            return

        if full_name and influencer.name is None:
            influencer.name = full_name

        if location and influencer.demographics_location is None:
            influencer.demographics_location = location

        if age and influencer.demographics_bloggerage is None:
            influencer.demographics_bloggerage = age

        # No such field in Influencer
        #if img_url and influencer.demographics_fbpic is None:
        #    influencer.demographics_fbpic = img_url

        influencer.demographics_gender = gender

        url_vals = {'fb': fb, 'pin': pin, 'tw': tw, 'insta': insta}
        appended = False
        for name, url in url_vals.items():
            if not url:
                continue
            field = '%s_url' % name
            if not influencer.contains_url(field, url):
                influencer.append_url(field, url)
                appended = True

        if appended:
            influencer.remove_from_validated_on(ADMIN_TABLE_INFLUENCER_INFORMATIONS)

        influencer.save()

@task(name="masuka.profile_info_extraction.initialize_profile_info", ignore_result=True)
def initialize_profile_info(obj):
    print "Initializing profile for {obj}".format(obj=obj)
    fc = FullContactWrapper()
    if isinstance(obj, UserProfile):
        fc.fetch_person_info(obj)
