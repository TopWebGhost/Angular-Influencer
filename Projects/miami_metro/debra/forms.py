import logging
import re
import socket
import urlparse
from datetime import datetime, time

from django import forms
from django.conf import settings
from django.forms import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse

from phonenumber_field.formfields import PhoneNumberField
from captcha.fields import CaptchaField
from registration.models import RegistrationProfile

from xpathscraper import utils

from debra.models import (
    UserProfile, StyleTag, Shelf, Lottery, LotteryPrize, LotteryTask, Brands,
    BrandJobPost, ProductModelShelfMap, Influencer, Platform)
from debra import constants

logger = logging.getLogger('miami_metro')


attrs_dict = {'class': 'required'}


#####-----< Custom Form Fields >-----#####
class TwitterHandleField(forms.CharField):
    '''
    this form field validates a twitter handle (something like @steiny) and - as part of its clean method - converts
    the handle to a url (@steiny would become http://www.twitter.com/steiny)
    '''
    def clean(self, value):
        try:
            return "http://www.twitter.com/{handle}/".format(handle=value.lstrip('@')) if value and '@' in value else value
        except:
            raise ValidationError
#####-----</ Custom Form Fields >-----#####


class UploadImageForm(forms.Form):
    x1 = forms.FloatField(required=True)
    y1 = forms.FloatField(required=True)
    x2 = forms.FloatField(required=True)
    y2 = forms.FloatField(required=True)
    image_file = forms.FileField(required=True)
    scaling_factor = forms.FloatField(required=False)

#####-----< Admin Forms >-----#####
class ModifyBrandForm(forms.ModelForm):
    class Meta:
        model = Brands
        fields = ['icon_id', 'is_active']

class ModifyUserForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['popularity_rank', 'connector_tag', 'quality_tag', 'friendly_tag', 'privilege_level',
                  'is_trendsetter', 'admin_comments', 'admin_action', 'admin_classification_tags']

class ModifyInfluencerForm(forms.ModelForm):
    twitter = forms.CharField(required=False)
    facebook = forms.CharField(required=False)
    pinterest = forms.CharField(required=False)
    instagram = forms.CharField(required=False)
    blog_name = forms.CharField(required=False)
    blog_url = forms.CharField(required=False)

    widget_access = forms.BooleanField(required=False)
    trendsetter = forms.BooleanField(required=False)

    class Meta:
        model = Influencer
        fields = ['relevant_to_fashion', 'show_on_search', 'remove_tag',
                  'demographics_location', 'name', 'email',
                  'fb_crawler_problem', 'fb_couldnt_find', 'fb_blogger_mistake',
                  'tw_crawler_problem', 'tw_couldnt_find', 'tw_blogger_mistake',
                  'in_crawler_problem', 'in_couldnt_find', 'in_blogger_mistake',
                  'pn_crawler_problem', 'pn_couldnt_find', 'pn_blogger_mistake',]

class InfluencerImportForm(forms.ModelForm):
    blog_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'req'}))
    blog_url = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'req blog_url'}))
    blog_platform = forms.ChoiceField(choices=Platform.blog_platforms_for_select())
    twitter = forms.CharField(required=False)
    extra_twitter = forms.CharField(required=False)
    facebook = forms.CharField(required=False)
    pinterest = forms.CharField(required=False)
    bloglovin = forms.CharField(required=False)
    instagram = forms.CharField(required=False)
    extra_instagram = forms.CharField(required=False)
    blog_aboutme = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    class Meta:
        model = Influencer
        fields = ['name', 'email', 'demographics_gender', 'source', 'demographics_location']
        widgets = {
            'source': forms.Select(choices=Influencer.SOURCE_TYPES),
            'demographics_gender': forms.Select(choices=(('male', 'male'), ('female', 'female')))
        }

class ModifyProductForm(forms.Form):
    show_on_feed = forms.BooleanField(required=False)
#####-----</ Admin Forms >-----#####

#####-----< Shelf Model Forms >-----#####
class ModifyShelfForm(forms.ModelForm):
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'typical_form'}))
    shelf_img = forms.CharField(max_length=400, widget=forms.HiddenInput(attrs={'class': 'shelf_img_input'}), required=False)

    class Meta:
        model = Shelf
        fields = ['name',]

class CreateShelfForm(forms.ModelForm):
    name = forms.CharField(max_length=300)

    class Meta:
        model = Shelf
        fields = ['name',]
#####-----</ Shelf Model Forms >-----#####


#####-----< Lottery Forms >-----#####
class CreateLotteryForm(forms.ModelForm):
    exists_id = forms.CharField(widget=forms.HiddenInput(), required=False) #if a lottery instance has already been created, this is populated
    start_date = forms.DateField(widget=forms.DateInput(format='%m-%d-%Y'), input_formats=['%m-%d-%Y'])
    end_date = forms.DateField(widget=forms.DateInput(format='%m-%d-%Y'), input_formats=['%m-%d-%Y'])
    start_time = forms.TimeField(required=False)
    end_time = forms.TimeField(required=False)


    class Meta:
        model = Lottery
        fields = ['theme', 'name', 'terms', 'start_date', 'end_date', 'timezone']
        widgets = {
            'theme': forms.HiddenInput()
        }

    def clean(self):
        cleaned_data = super(CreateLotteryForm, self).clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        cleaned_data['start_datetime'] = datetime.combine(cleaned_data.get('start_date'), start_time if start_time and start_time != '' else time(0, 0))
        cleaned_data['end_datetime'] = datetime.combine(cleaned_data.get('end_date'), end_time if end_time and end_time != '' else time(0, 0))

        return cleaned_data


class LotteryPrizeForm(forms.ModelForm):
    exists_id = forms.CharField(widget=forms.HiddenInput(), required=False) #if this is for a prize that has been created

    class Meta:
        model = LotteryPrize
        fields = ['description', 'quantity', 'brand']

class LotteryTaskForm(forms.ModelForm):
    exists_id = forms.CharField(widget=forms.HiddenInput(), required=False) #if this is for a prize that has been created
    task = forms.CharField(widget=forms.HiddenInput())
    custom_option = forms.ChoiceField(choices=LotteryTask.CUSTOM_RULE_OPTIONS, widget=forms.RadioSelect, initial=LotteryTask.CUSTOM_TEXT_FIELD[0], required=False)
    step_id = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = LotteryTask
        fields = ['task', 'point_value', 'requirement_text', 'requirement_url', 'url_target_name', 'mandatory', 'validation_required', 'custom_option', 'step_id']
        widgets = {
            'point_value': forms.HiddenInput,
            'requirement_text': forms.Textarea
        }

    def clean(self):
        cleaned_data = super(LotteryTaskForm, self).clean()
        requirement_text = cleaned_data.get('requirement_text')
        requirement_url = cleaned_data.get('requirement_url')
        if (requirement_text is not None and requirement_text == ''):
            if (requirement_url is not None and requirement_url == ''):
                raise forms.ValidationError(_(u'A value is required'))

        return cleaned_data

class EnterLotteryForm(forms.Form):
    validation_url = forms.CharField(max_length=200, required=False)
    custom_task_response = forms.CharField(max_length=300, required=False)
#####-----</ Lottery Forms >-----#####

#####-----< WishlistItem Forms >-----#####
class AddItemToShelvesForm(forms.Form):
    shelves = forms.CharField(max_length=600, widget=forms.HiddenInput(attrs={'class': 'shelves'}), required=False)

class AddAffiliateLinkForm(forms.ModelForm):
    affiliate_prod_link = forms.CharField(error_messages={'invalid': 'Please enter a valid url'})
    class Meta:
        model = ProductModelShelfMap
        fields = ['affiliate_prod_link',]
#####-----</ WishlistItem Forms >-----#####

#####-----< Account Forms >-----#####
class ShelfAccountForm(forms.ModelForm):
    style_tags = forms.CharField(required=False)
    twitter_page = TwitterHandleField(required=False)

    class Meta:
        model = UserProfile
        fields = ['location', 'name', 'blog_name', 'aboutme', 'style_bio', 'style_tags', 'is_female',
                  'facebook_page', 'pinterest_page', 'twitter_page', 'instagram_page', 'etsy_page', 'store_page', 'bloglovin_page',
                  'web_page', 'blog_page', 'youtube_page', 'account_management_notification', 'opportunity_notification', 'price_alerts_notification',
                  'deal_roundup_notification', 'social_interaction_notification']
        widgets = {
            'location': forms.TextInput,
            'aboutme': forms.Textarea,
            'style_bio': forms.Textarea
        }


    def clean_style_tags(self):
        '''
        we must separately clean this so we can split the style tag string and save the resulting tags
        in our database
        '''
        tags = self.cleaned_data['style_tags'].split(",")

        for tag in tags:
            new_tag,created = StyleTag.objects.get_or_create(name=tag)


        return self.cleaned_data['style_tags']


class ChangeEmailForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email',]

    def clean_email(self):
        """
        Validate that the supplied email address is unique for the
        site.
        """
        if User.objects.filter(email__iexact=self.cleaned_data['email']):
            raise forms.ValidationError(_(u'This email address is already in use. Please supply a different email address.'))
        return self.cleaned_data['email']


class ChangePasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput)


class ShelfLoginForm(forms.Form):
    '''
    this form is responsible ONLY for logging in a user
    '''
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(attrs_dict, maxlength=75)))
    password = forms.CharField(widget=forms.PasswordInput(attrs=attrs_dict, render_value=False))

    def clean(self):
        cleaned_data = super(ShelfLoginForm, self).clean()
        cleaned_data["email"] = cleaned_data["email"].lower()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        does_not_exist_msg = _(u'That email does not exist in our system, please try again.')

        try:
            u = User.objects.get(username__iexact=email)
            user_prof = u.userprofile

            resend_url = reverse('debra.account_views.resend_activation_key')+"?email=%s" % email
            activation_msg = _(u'Please verify your email before logging in.  If you didn\'t receive your activation email, then click <a href="%s">here</a> to resend it.'%resend_url)

            if not u.is_active:
                if u.influencer_set.exists() and all(u.influencer_set.values_list('blacklisted', flat=True)):
                    raise forms.ValidationError(does_not_exist_msg)
                raise forms.ValidationError(activation_msg)
        except User.DoesNotExist:
            raise forms.ValidationError(does_not_exist_msg)

        valid_user = authenticate(username=email, password=password)
        if valid_user is None:
            raise forms.ValidationError(_(u'The password is incorrect, please try again.'))

        return cleaned_data


class ShopperRegistrationForm(forms.Form):
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(attrs_dict, maxlength=75)))
    password = forms.CharField(widget=forms.PasswordInput(attrs=attrs_dict, render_value=False))

    def clean(self):
        cleaned_data = super(ShopperRegistrationForm, self).clean()
        cleaned_data["email"] = cleaned_data["email"].lower()
        email = cleaned_data.get("email")

        # make sure another user with the given email doesnt already exist
        try:
            User.objects.get(username__iexact=email)
            raise forms.ValidationError(_(u'Another user with the given email already exists'))
        except User.DoesNotExist:
            pass

        return cleaned_data

    def save(self):
        """
        Taken whole-sale from django-registration
        """
        site = Site.objects.get(id=settings.SITE_ID)
        new_user = RegistrationProfile.objects.create_inactive_user(username=self.cleaned_data['email'],
                                                                    password=self.cleaned_data['password'],
                                                                    email=self.cleaned_data['email'],
                                                                    site=site)
        new_user_prof = UserProfile.user_created_callback(new_user)
        return new_user_prof


class BloggerRegistrationForm(forms.Form):
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(attrs_dict, maxlength=75)))
    password = forms.CharField(widget=forms.PasswordInput(attrs=attrs_dict, render_value=False), required=False)
    name = forms.CharField(required=True)
    blog_name = forms.CharField(required=True)
    blog_url = forms.CharField(required=True)
    influenity_signup = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super(BloggerRegistrationForm, self).clean()
        cleaned_data["email"] = cleaned_data["email"].lower()
        email = cleaned_data.get("email")
        entered_blog_url = cleaned_data["blog_url"].lower()
        if not entered_blog_url.startswith("http://") and not entered_blog_url.startswith("https://"):
            cleaned_data["blog_url"] = "http://" + cleaned_data["blog_url"]

        def is_valid_url(url):
            s = socket.socket()
            try:
                s.connect((url, 80))
            except Exception:
                print "Bad url", cleaned_data["blog_url"]
                return False
            else:
                return True

        domains = [
            utils.domain_from_url(cleaned_data["blog_url"], preserve_www=False),
            utils.domain_from_url(cleaned_data["blog_url"], preserve_www=True)
        ]

        if not any(map(is_valid_url, domains)):
            raise forms.ValidationError(
                _(u'Your blog url seems to be invalid. Please double check it.'))

        # make sure another user with the given email doesnt already exist
        try:
            user = User.objects.get(username__iexact=email)
            if cleaned_data['influenity_signup']:
                pass
                # if not user.check_password(cleaned_data['password']):
                #     raise forms.ValidationError(_(u'Wrong password'))
            else:
                raise forms.ValidationError(_(u'Another user with the given email already exists'))
        except User.DoesNotExist:
            pass

        return cleaned_data

    def save(self):
        """
        Taken whole-sale from django-registration
        """
        from debra.account_helpers import send_msg_to_slack

        site = Site.objects.get(id=settings.SITE_ID)

        new_password = None

        try:
            new_user = User.objects.get(
                username__iexact=self.cleaned_data['email'])
        except User.DoesNotExist:
            if self.cleaned_data['influenity_signup']:
                new_password = 'TMP_PASSWORD_{}'.format(
                    self.cleaned_data['email'])
            else:
                new_password = self.cleaned_data['password']

            new_user = RegistrationProfile.objects.create_inactive_user(
                username=self.cleaned_data['email'],
                password=new_password,
                email=self.cleaned_data['email'],
                site=site, send_email=False
            )
        try:
            new_user_prof = new_user.userprofile
        except UserProfile.DoesNotExist:
            new_user_prof = UserProfile.user_created_callback(new_user)

        if self.cleaned_data['influenity_signup']:
            new_user.is_active = True
            new_user.save()
            new_user_prof.set_setting('influenity_signup', True)
            new_user_prof.set_setting('influenity_tag_id', 1647)
            new_user_prof.save()

        send_msg_to_slack(
            'blogger-signups',
            '''
            ******************************************
            NEW BLOGGER SIGNUP
            New User? - {is_new_user}
            User = {user}
            Date Joined = {date_joined}
            UserProfile = {userprofile}

            Email = {email}
            Password = {password}
            Name = {name}
            Blog name = {blog_name}
            Blog URL = {blog_url}
            Influenity? - {influenity}
            Influenity Tag ID = {influenity_tag_id}
            '''.format(
                is_new_user=new_password is not None,
                user=new_user.id,
                date_joined=new_user.date_joined,
                userprofile=new_user.userprofile,
                email=self.cleaned_data['email'],
                password=new_password,
                name=self.cleaned_data['name'],
                blog_name=self.cleaned_data['blog_name'],
                blog_url=self.cleaned_data['blog_url'],
                influenity=new_user_prof.get_setting('influenity_signup', False),
                influenity_tag_id=new_user_prof.get_setting('influenity_tag_id'),
            )
        )

        return new_user_prof


# class InfluenityRegistrationForm(BloggerRegistrationForm):


class BrandRegistrationForm(forms.Form):
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(attrs_dict, maxlength=75)), required=True)
    # password = forms.CharField(widget=forms.PasswordInput(attrs=attrs_dict, render_value=False), required=True)
    # phone_number = PhoneNumberField(required=True)

    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=False)
    brand_name = forms.CharField(required=False)
    brand_url = forms.CharField(required=True)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.referer = kwargs.pop('referer', None)
        super(BrandRegistrationForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(BrandRegistrationForm, self).clean()
        try:
            cleaned_data["email"] = cleaned_data["email"].lower()
        except:
            raise forms.ValidationError('')

        url = cleaned_data.get('brand_url')
        email = cleaned_data.get("email")

        # brand url <=> email matching disabled now
        # # check that the users email matches the brands domain, if not send back error
        # if not helpers.email_matches_domain(email, url):
        #     raise forms.ValidationError(_(u'The provided email must be your brand account email'))

        # make sure we dont have multiple brands with the given domain in our system
        # domain = utils.domain_from_url(url)

        # try:
        #    s = socket.socket()
        #    s.connect((domain, 80))
        # except:
        #    print "Bad url", url
        #    raise forms.ValidationError(_(u'Your brand url seems to be invalid. Please double check it.'))

        # make sure another user with the given email doesnt already exist
        try:
            User.objects.get(username__iexact=email)
            raise forms.ValidationError(_(u'Another user with the given email already exists'))
        except User.DoesNotExist:
            pass

        return cleaned_data

    def save(self):
        """
        Create user-related models and make user active
        """
        username = email = self.cleaned_data['email'].lower()
        # password = self.cleaned_data['password']
        # phone_number = self.cleaned_data['phone_number']
        password = constants.TRIAL_PASSWORD
        new_user = User.objects.create_user(username, email, password)
        new_user.is_active = True
        new_user.save()

        RegistrationProfile.objects.create_profile(new_user)

        up = UserProfile.objects.create(
            user=new_user)
        return up

    @property
    def referer_page(self):
        return urlparse.urlparse(self.referer).path.strip('/').split('/')[0]

    @property
    def referer_tag(self):
        return {
            '': 'home',
            'blogger-outreach': 'newbie',
            'influencer-marketing': 'expert',
            'agencies': 'agency',
            'blogger-campaign-services': 'services',
            'coverage': 'coverage',
            'the-blog': 'blog',
            'blogger-roundups': 'roundups',
        }.get(self.referer_page)


class AddNewUserForm(forms.Form):
    name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    # captcha = CaptchaField()

    def clean_email(self):
        email = self.cleaned_data['email'].lower()

        try:
            User.objects.get(username__iexact=email)
            raise forms.ValidationError(_(u'Another user with the given email already exists'))
        except User.DoesNotExist:
            pass

        return email


class ContactUsForm(forms.Form):
    '''
    allow users to send us questions/comments
    '''
    name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    subject = forms.CharField(required=True)
    message = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': "5", 'cols': "36"}))
    captcha = CaptchaField()
#####-----</ Account Forms >-----#####


class ContactUsDemoForm(forms.Form):
    '''
    demo rq
    '''
    name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    brand = forms.CharField(required=True)
    brandurl = forms.CharField(required=True)
    captcha = CaptchaField()


class JobPostForm(forms.ModelForm):
    title = forms.CharField(max_length=256, required=True)

    def clean_title(self):
        title = self.cleaned_data["title"]

        if title:
            title = title.strip()
        if not title:
            raise forms.ValidationError(_("Title should be a non-empty string."))

        if BrandJobPost.objects.exclude(id=self.instance.id).filter(creator=self.instance.creator, title=title).exists():
            raise forms.ValidationError(_("Brand already has campaign with this title."))
        return title

    def clean_client_name(self):
        client_name = self.cleaned_data['client_name']

        if client_name:
            client_name = client_name.strip()
        return client_name

    def clean_mentions_required(self):
        mentions_required = self.cleaned_data["mentions_required"]

        if mentions_required:
            values_list = [x.strip() for x in mentions_required.split(',')]
            values_list = ['{}{}'.format('' if x.startswith('@') else '@', x) for x in values_list]
            mentions_required = ', '.join(values_list)

        return mentions_required

    def clean_hashtags_required(self):
        hashtags_required = self.cleaned_data["hashtags_required"]

        if hashtags_required:
            values_list = [x.strip() for x in hashtags_required.split(',')]
            values_list = ['{}{}'.format('' if x.startswith('#') else '#', x) for x in values_list]
            hashtags_required = ', '.join(values_list)

        return hashtags_required

    class Meta:
        model = BrandJobPost
        fields = (
            'description',
            'title',
            'who_should_apply',
            'details',
            'collab_type',
            'date_start',
            'date_end',
            'filter_json',
            'collection',
            'cover_img_url',
            'mentions_required',
            'hashtags_required',
            'client_name',
            'utm_source',
            'utm_medium',
            'utm_campaign',
        )


class  PlatformUrlsForm(forms.Form):
    SOURCE_CHOICES = (
        ('Manual_Pinterest', 'Manual_Pinterest'),
        ('Manual_BlogRoll', 'Manual_BlogRoll'),
        ('Manual_Twitter', 'Manual_Twitter'),
        ('Manual_Bloglovin', 'Manual_Bloglovin'),
    )
    CATEGORY_CHOICES = (
        ('Mommy', 'Mommy'),
        ('Travel', 'Travel'),
        ('DIY', 'DIY'),
        ('Food', 'Food'),
        ('Design', 'Design'),
        ('Wedding', 'Wedding'),
    )
    links = forms.CharField(widget=forms.Textarea, required=True)
    source = forms.ChoiceField(choices=SOURCE_CHOICES, initial='Manual', required=True)
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, initial='Mommy', required=True)

    def clean_links(self):
        text = self.cleaned_data["links"]
        # YOU SHOULD USE ", " for comma-sepateated urls, not just "," !!!!
        # otherwise it won't split that two urls separated by comma
        links = set()
        for link in [group[0] for group in constants.GRUBER_URLINTEXT_PAT.findall(text)]:
            links.add(link)
        return list(links)
