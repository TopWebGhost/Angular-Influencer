import csv
import datetime
import re
import copy
import os
import logging
import urllib
import time
import pprint
import baker
import string
import urlparse
import collections
import json
import quopri
import chardet
import random

from operator import itemgetter
from celery.decorators import task
from mailsnake import MailSnake
from json2html import json2html
from dateutil.parser import parser as dateutil_parser

from django.core.urlresolvers import reverse
from django.conf import settings
from django.db.models import Q, get_model
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import mail_admins
from django.core.cache import get_cache

from debra.models import (
    ProductModel, Influencer, UserProfile, PlatformDataOp, InfluencersGroup)
from debra import models
from debra import mongo_utils
from debra.constants import *
from xpathscraper import utils
from debra.decorators import cached_property


mailsnake_client = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')
mailsnake_admin_client = MailSnake(settings.MANDRILL_ADMIN_EMAIL_API_KEY, api='mandrill')
mc_cache = get_cache('memcached')
redis_cache = get_cache('redis')

log = logging.getLogger('debra.helpers')


def get_random_date(start_date=None, end_date=None):
    if start_date or end_date:
        start_date = start_date or datetime.datetime(1970, 1, 1, 0, 0, 0)
        end_date = end_date or datetime.datetime.now()
        return start_date + datetime.timedelta(
            seconds=random.randint(0, int((end_date - start_date).total_seconds())))
    else:
        year = datetime.date.today().year
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        h = random.randint(0, 23)
        m = random.randint(0, 59)
        s = random.randint(0, 59)
        return datetime.datetime(year, month, day, h, m, s)


def get_model_instance(value, model_class):
    if isinstance(value, model_class):
        return value
    if isinstance(value, basestring):
        try:
            value = int(value)
        except ValueError:
            value = None
    if isinstance(value, int):
        return model_class.objects.get(id=value)


def guess_encoding(encoded_text):
    encoding = 'utf-8'
    try:
        payload_dec = quopri.decodestring(encoded_text)
        chdet = chardet.detect(payload_dec)
        if chdet["encoding"] and chdet["confidence"] > 0.9:
            encoding = chdet['encoding']
            decoded_text = unicode(payload_dec, chdet["encoding"], 'ignore')
        else:
            decoded_text = unicode(payload_dec, 'utf-8', 'ignore')
    except Exception as e:
        print e
    return encoding, decoded_text


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i+n]


def multikeysort(items, columns, functions={}, getter=itemgetter):
    """Sort a list of dictionary objects or objects by multiple keys bidirectionally.

    Keyword Arguments:
    items -- A list of dictionary objects or objects
    columns -- A list of column names to sort by. Use -column to sort in descending order
    functions -- A Dictionary of Column Name -> Functions to normalize or process each column value
    getter -- Default "getter" if column function does not exist
              operator.itemgetter for Dictionaries
              operator.attrgetter for Objects
    """
    comparers = []
    for col in columns:
        column = col[1:] if col.startswith('-') else col
        if not column in functions:
            functions[column] = getter(column)
        comparers.append((functions[column], 1 if column == col else -1))

    def comparer(left, right):
        for func, polarity in comparers:
            if func(left) is None and func(right) is None:
                return 0
            if func(left) is None:
                return -1
            if func(right) is None:
                return 1
            result = cmp(func(left), func(right))
            if result:
                return polarity * result
        else:
            return 0
    return sorted(items, cmp=comparer)
 

def compose(inner_func, *outer_funcs):
     """Compose multiple unary functions together into a single unary function"""
     if not outer_funcs:
         return inner_func
     outer_func = compose(*outer_funcs)
     return lambda *args, **kwargs: outer_func(inner_func(*args, **kwargs))


class BetterPaginator(Paginator):
    def __init__(self, *args, **kwargs):
        count = kwargs.pop('count')
        super(BetterPaginator, self).__init__(*args, **kwargs)
        self._count = count


class OrderedDefaultdict(collections.OrderedDict):
    def __init__(self, *args, **kwargs):
        if not args:
            self.default_factory = None
        else:
            if not (args[0] is None or callable(args[0])):
                raise TypeError('first argument must be callable or None')
            self.default_factory = args[0]
            args = args[1:]
        super(OrderedDefaultdict, self).__init__(*args, **kwargs)

    def __missing__ (self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = default = self.default_factory()
        return default

    def __reduce__(self):  # optional, for pickle support
        args = (self.default_factory,) if self.default_factory else ()
        return self.__class__, args, None, None, self.iteritems()


def get_server_info(request):
    '''
    This internal function gets the server info to dynamically populate the
    absolute URL in the 'My Shelf' and 'Shelf It' bookmarklets.
    '''
    if 'SERVER_NAME' in request.META and request.META['SERVER_NAME'] and (request.META['SERVER_NAME'] == 'localhost.herokuapp.com'):
        sname = request.META['SERVER_NAME']
        sport = request.META['SERVER_PORT']
        sname = sname + ":" + sport
    elif 'HTTP_HOST' in request.META and 'HTTP_X_FORWARDED_PORT' in request.META:
        sname = request.META['HTTP_HOST']
        sport = request.META['HTTP_X_FORWARDED_PORT']
        sname = sname + ":" + sport
    elif 'HTTP_HOST' in request.META:
        sname = request.META['HTTP_HOST']

    return sname


def get_js_shelfit_code(sname):
    '''
    This internal function auto-populates the home view with
    javascript code. Auto-population is needed for the absolute
    URL (localhost vs jawan vs myshelf).
    '''
    from debra.bookmarklet_views import get_bookmarklet_href
    return get_bookmarklet_href()

def read_csv_file(filename, delimiter=',', dict_keys=[]):
    """
    read a csv file into a list of dictionaries whose keys are specified by dict_keys (ORDER MATTERS!). i.e. if dict_keys = ['a', 'b']
    and csv has values for a row of 1, 2 the result will be [{'a': 1, 'b': 2}]
    @return list of dictionaries, each entry is a row in the csv file
    """
    result = []
    file_path = '{base}/csvs/{name}'.format(base=os.path.dirname(os.path.realpath(__file__)), name=filename)
    with open(file_path, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=delimiter, quotechar='|')
        for row in reader:
            row_dict = {}
            for i in range(0, min(len(row), len(dict_keys))):
                row_dict[dict_keys[i]] = row[i]

            result.append(row_dict)

    return result

def write_csv_file(filename, data, is_3d=False, delimiter='='):
    '''
    A function to write a csv file
    @param filename - the name of the csv file to create
    @param data - a 2-dimensional array containing the data to write
    @param is_3d - if true, the passed data is actually 3 dimensional (array containing array of rows which contains an array of cols)
    '''
    with open(filename, 'wb') as csvfile:
        writer = csv.writer(csvfile, delimiter=delimiter, quotechar='|', quoting=csv.QUOTE_MINIMAL)

        if is_3d:
            for page in data:
                for row in page:
                    removed_unicode_row = [dat.encode('ascii', 'ignore') if not isinstance(dat, int) else dat for dat in row]
                    writer.writerow(removed_unicode_row)
        else:
            for row in data:
                removed_unicode_row = [dat.encode('ascii', 'ignore') if not isinstance(dat, int) else dat for dat in row]
                writer.writerow(removed_unicode_row)




#####-----< View Helpers >-----#####
def request_user(request):
    return request.user.userprofile if request.user.is_authenticated() else 1

def parse_prev_param(prev):
    '''
    parse the 'prev' GET parameter, which we use for breadcrumbs
    @param prev - the value of the 'prev' GET param. This should be a string of form '<page>,<uid>(optional)'
    '''
    urls_map = {
        'trendsetters': lambda u: reverse('debra.explore_views.trendsetters'),
        'followers': lambda u: reverse('debra.shelf_views.followers', args=(u,)),
        'following': lambda u: reverse('debra.shelf_views.following', args=(u,))
    }
    page,u_id = prev.split(',')
    return {
        'page': "your {page}".format(page=page) if page == 'followers' or page == 'following' else page,
        'url': urls_map[page](u_id)
    }

def blank_page(request):

    return render(request, 'pages/blank_page.html', {})

def serve_download(download_url, filename, content_type='image/png'):
    file = urllib.urlopen(download_url)
    response = HttpResponse(file.read(), content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename={filename}'.format(filename=filename)

    return response
#####-----</ View Helpers >-----#####


#####-----< Generic Helpers >-----#####
def domain_of_email(email):
    """
    get the domain portion of a given email
    """
    return re.sub(r'.*@', "", email)

def domain_of_url(url):
    """
    get the domain portion of a given url
    """
    return re.sub(r'(http://)?(www\.)?', "", url)

def email_matches_domain(email, url):
    ''''
    check if a given email has the same domain (after @) as a given url (amazon.com matches bobby@amazon.com)
    @param email - the email to match
    @param url - the url to match
    @return True if they match, false o/w
    '''
    return email and url and domain_of_email(email) == utils.domain_from_url(url)

def is_valid_hostname(hostname):
    if len(hostname) > 127:
        return False
    if '.' not in hostname:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1] # strip exactly one dot from the right, if present
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))

def dynamic_filter(qs, filter_field, filter_op, filter_val):
    '''
    a method to apply a dynamic filter to a queryset
    @param qs - the queryset to apply the filter to
    @param filter_field - a string representing the field to filter
    @param filter_op - the operation of the filter to apply i.e. eq, gt, etc.
    @param filter_val - the val to look for in the qs
    @return the filtered queryset
    '''
    filter_format = '{field}__{op}'.format(field=filter_field, op=filter_op) if filter_op != 'eq' else filter_field
    kwargs = {
        filter_format: filter_val
    }

    return qs.filter(**kwargs)

def yesterday():
    return datetime.datetime.now() - datetime.timedelta(days=1)

def user_is_logged_in_user(request, page_user_prof):
    """
    this method checks if the user in the request is the same user as the given user
    @param request - the HttpRequest
    @param page_user_prof - the user to check against the user in the request
    """
    return request.user.is_authenticated() and request.user.userprofile.id == page_user_prof.id

def render_data(fun):
    """
    Renders execution time and data returned by calling ``fun()`` as a plain text http response
    """
    start = time.time()
    data = fun()
    end = time.time()
    return HttpResponse('Computed in %.3fs, data:\n\n%s' % (end-start, pprint.pformat(data)),
                        content_type='text/plain')

#####-----</ Generic Helpers >-----#####


#####-----< Intercomm >-----#####
class IntercomCustomData:
    def custom_data(self, user):
        """ Required method, same name and only accepts one attribute (django User model) """
        user_prof = user.userprofile

        return INTERCOM_CUSTOM_DATA(user_prof)
#####-----</ Intercomm >-----#####


#####-----< Email Helpers >-----#####
#####-----< STATIC EMAIL MAPPINGS >-----#####
EMAIL_SUBJECTS = {
    'product_errors_report': 'Daily ProductModel Error Report Fun',
    'multiple_brand_error': 'User Signup Attempt for Multiple Brands With A URL',
    'image_error': 'User Image Upload Failure'
}

EMAIL_TPL_VARS = {
    'product_errors_report': {
        'products': ProductModel.objects.filter(insert_date__gte=yesterday(), problems__isnull=False)
    }
}

EMAIL_TO = {
    'product_errors_report': [{
        'email': ATUL_EMAILS['admin_email'],
        'name': 'Artur'
    }],
    'multiple_brand_error': [
        {
            'email': ATUL_EMAILS['admin_email'],
            'name': "Atul"
        },
        {
            'email': ATUL_EMAILS['admin_email'],
            'name': 'Atul'
        }
    ],
    'image_error': [
        {
            'email': ATUL_EMAILS['admin_email'],
            'name': "Atul"
        },
        {
            'email': ATUL_EMAILS['admin_email'],
            'name': 'Atul'
        }
    ],
}

EMAIL_FROM = {
    'product_errors_report': {
        'email': ATUL_EMAILS['admin_email'],
        'name': 'ATUL'
    },
    'multiple_brand_error': {
        'email': SUPPORT_EMAIL,
        'name': 'support'
    },
    'image_error': {
        'email': SUPPORT_EMAIL,
        'name': 'support'
    },
}

def send_mandrill_email(to=None, _from=None, subject=None, message_type='internal', message_name='product_errors_report', tpl_vars={}):
    '''
    generic method for sending an email using mandrill to the provided users
    @param to - list of name,email dicts the message is to
    @param _from - dict containing the sender email and name (keys: name, email)
    @param subject - the subject of the email
    @param message_type - the type of message being sent (maps to the folders in mailchimp_templates)
    @param message_name - the name of the message being sent
    @param tpl_vars - template variables
    '''
    tpl_vars.update(EMAIL_TPL_VARS.get(message_name, {}))
    to = to or EMAIL_TO[message_name]
    _from = _from or EMAIL_FROM[message_name]
    subject = subject if subject else EMAIL_SUBJECTS[message_name]

    rendered_message = render_to_string('mailchimp_templates/{type}/{message}.html'.format(type=message_type, message=message_name),
                                        tpl_vars)

    mailsnake = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')
    mailsnake.messages.send(message={
        'html': rendered_message,
        'subject': subject,
        'from_email': _from['email'],
        'from_name': _from['name'],
        'to': to
    })
#####-----</ Email Helpers >-----#####

#####-----< Model Helpers >-----#####

def select_valid_influencer(infs):
    if not infs:
        return None
    for inf in infs:
        if not inf.blacklisted and inf.source:
            return inf
    return None

def all_blacklisted(infs):
    if not infs:
        return False
    return all(inf.blacklisted for inf in infs)

def get_first_or_create(manager, kwargs):
    existing = list(manager.filter(**kwargs)[:1])
    if existing:
        return existing[0]
    return manager.create(**kwargs)


def get_or_create_influencer(blog_url, influencer_source, to_save):
    """
    This function either gets an existing influencer for a blog url or creates a new one.
    Even if one that exists is blacklisted, it is returned.
    The source is appended.
    """
    created = False
    # find all influencers with that blog url
    dup_infs = models.Influencer.find_duplicates(blog_url, exclude_blacklisted=False)
    if len(dup_infs) > 1:
        # if more than one found, pick the best one
        inf = dup_infs[0]
        inf = inf._select_influencer_to_stay(dup_infs)
        log.warn('Existing inf found: %r', inf)
    elif len(dup_infs) == 1:
        inf = dup_infs[0]
        log.warn('Existing inf found: %r', inf)
    else:
        # if none found, create a new one
        inf = models.Influencer(blog_url=blog_url, source=influencer_source, date_created=datetime.datetime.now())
        log.info('Created new influencer %r', inf)
        created = True
    #####if all_blacklisted(dup_infs):
    #####    return None, False
    #####if dup_infs:
    #####    inf = select_valid_influencer(dup_infs)
    #####    log.warn('Existing inf found: %r', inf)
    #####    return inf, False

    inf.append_source(influencer_source)
    if to_save:
        inf.save()
    return inf, created

def create_influencer_and_blog_platform(blog_url, influencer_source, to_save=True, platform_name_fallback=False):
    """Returns Influencer.
    """
    from platformdatafetcher import fetcher

    inf, inf_created = get_or_create_influencer(blog_url, influencer_source, to_save)
    log.info('Influencer was freshly created: %s' % inf_created)
    if not inf:
        # this should never happen
        return None
    if not inf_created:
        return inf
    pls = fetcher.create_platforms_from_urls([blog_url], use_api=True, platform_name_fallback=platform_name_fallback)
    if not pls:
        log.warn('Could not create a platform from %r', blog_url)
        return inf
    pl = pls[0]
    pl.influencer = inf
    if not pl.platform_name:
        pl.platform_name = 'Custom'
    log.info('Created platform %r from url %r', pl, blog_url)
    if to_save:
        # This will handle duplicates
        pl.save()
    return inf

def get_influencer_even_if_blacklisted(blog_url, source, disable_blacklist=False):
    infs = Influencer.find_duplicates(blog_url, exclude_blacklisted=False)
    if len(infs) >= 1:
        inf = infs[0]
        best_scored_influencer = inf._select_influencer_to_stay(infs)

        if disable_blacklist and best_scored_influencer.blacklisted:
            # track this info of who we're un-blacklisting to review later if needed
            _, _ = PlatformDataOp.objects.get_or_create(influencer=best_scored_influencer, operation='unmarking_blacklisted')
            best_scored_influencer.blacklisted = False
        best_scored_influencer.append_source(source)
        best_scored_influencer.save()
        return best_scored_influencer
    return None

@task(name="debra.helpers.create_influencer_and_blog_platform_bunch", ignore_result=True)
def create_influencer_and_blog_platform_bunch(urls, source, category, to_save=True, tags=None):
    """
    method to create a bunch of influencers from a given list of urls
    urls: list of urls
    source: where they are received from
    category: what category we should assign them right away (this can be used for checking our automatic categorization)
    """
    infs = set()
    log.info("create_influencer_and_blog_platform_bunch: we're given %d urls" % len(urls))
    for i,link in enumerate(urls):
        print "Checking %r" % link
        inf = create_influencer_and_blog_platform(link, source, to_save=to_save, platform_name_fallback=True)

        if inf.blacklisted:
            log.info("Selected influencer is blacklisted %s" % inf)

        inf.append_source(source)
        if tags:
            inf.add_tags(tags, to_save=False)
        if category and not (inf.blogger_type and category in inf.blogger_type):
            inf.blogger_type = inf.blogger_type + ":" + category if inf.blogger_type else category
        if to_save:
            inf.save()
        print "%s %s %s %s %s" % (inf, inf.source, inf.blogger_type, source, category)
        infs.add(inf)
        print "Created %d influencers so far" % len(infs)

        ##### if they are all blacklisted, that's not good.
        #####if dup_infs and all_blacklisted(dup_infs) and to_save:
        #####    # save this info in backend so that we can go back and double check our blog detection algorithm
        #####    _,_ = models.PlatformDataOp.objects.get_or_create(influencer=dup_infs[0], operation='unmarking_blacklisted')
        #####    models.Influencer.objects.filter(id=dup_infs[0].id).update(blacklisted=False)

        #####inf = create_influencer_and_blog_platform(link, source, to_save=to_save, platform_name_fallback=True)
        #####if inf:
        #####    # avoid storing multiple copies of source and category
        #####    inf.append_source(source)
        #####    if category and not (inf.blogger_type and category in inf.blogger_type):
        #####        inf.blogger_type = inf.blogger_type + ":" + category if inf.blogger_type else category
        #####    if to_save:
        #####        inf.save()
        #####    print "%s %s %s %s %s" % (inf, inf.source, inf.blogger_type, source, category)
        #####    infs.add(inf)
    return infs


def create_blog_platform_for_blog_url(influencer):
    from platformdatafetcher import fetcher

    if not influencer.blog_url:
        log.warn('blog_url not set for %r', influencer)
        return None
    blog_plats = influencer.platform_set.exclude(url_not_found=True).filter(platform_name__in=models.Platform.BLOG_PLATFORMS)
    if blog_plats.exists():
        log.warn('Blog platform already exists for influencer %r: %r', influencer, list(blog_plats))
        return None
    new_plat = fetcher.create_single_platform_from_url(influencer.blog_url, use_api=True, platform_name_fallback=True)
    new_plat.influencer = influencer
    if not new_plat.platform_name:
        new_plat.plaform_name = 'Custom'
    new_plat.save()
    log.info('Created: %r', new_plat)
    return new_plat

def update_blog_url(influencer, new_url):
    plats = influencer.platform_set.filter(url=influencer.blog_url)
    matching_plats = plats.count()
    log.info('Updating %d platform urls matching old blog url %r', matching_plats, influencer.blog_url)
    plats.update(url=new_url)
    influencer.blog_url = new_url
    influencer.save()
    return matching_plats

def update_platform_url(platform, new_url):
    from platformdatafetcher import platformutils

    if platformutils.url_to_handle(platform.url) == \
       platformutils.url_to_handle(platform.influencer.blog_url):
        platform.influencer.blog_url = new_url
        platform.influencer.save()
        platform.influencer.handle_duplicates()

    platform.url = new_url
    platform.save()
    platform.handle_duplicates()

#####-----</ Model Helpers >-----#####


def run_email_extraction(influencer, linked_task=None, user_prof_id=None):
    """Submits extract_emails_from_platform task for the given influencer's blog platform
    and (if ``not linked_task is None``) runs a celery task ``linked_task`` after it, that
    should take an Influencer's id as an argument.
    """
    from platformdatafetcher import emailextractor

    pl = influencer.blog_platform
    if not pl:
        mail_admins("run_email_extraction error: no blog platform for influencer", "Influencer: %s, User_prof_id: %s" % (str(influencer), user_prof_id))
        return
    if linked_task:
        emailextractor.extract_emails_from_platform.apply_async(args=[pl.id],
               queue='email_extraction_high_priority',
               link=linked_task.subtask(args=[influencer.id, user_prof_id],
                                   immutable=True,
                                   queue='email_extraction_high_priority'))
    else:
        emailextractor.extract_emails_from_platform.apply_async(args=[pl.id],
               queue='email_extraction_high_priority')

    #email = UserProfile.objects.get(id=user_prof_id).user.email
    #send_mail('Please wait until we process your blog', 'You are being verified now', 'lauren@theshelf.com',[email], fail_silently=True)



def check_if_email_matches_domain(email, domain):
    """
    checks if email is from the same domain as the given domain
    e.g., atul@theshelf.com and theshelf.com should return True
    """
    log.info("checking if email is from a given domain: email(%s) domain(%s)", email, domain)
    if not '@' in email:
        return False
    email_domain = email.split('@')[1]
    return True if email_domain.lower() in domain.lower() else False


def set_userprof_influencer_mapping(inf, user_prof):
    inf.append_email_if_not_present(user_prof.user.email)
    inf.shelf_user = user_prof.user
    inf.save()
    user_prof.influencer = inf
    user_prof.blog_verified = True
    user_prof.save()


@task(name="debra.helpers.post_email_extraction_blogger_influencer_callback", ignore_result=True)
def post_email_extraction_blogger_influencer_callback(inf_id, user_prof_id):
    """
    This is called after email extraction has completed.
    We now check if we found an email for this influencer. If yes, then the userprof and influencer are connected.
    """
    log.info("post_email_extraction_blogger_influencer_callback: inf_id %s user_prof_id %s", inf_id, user_prof_id)
    inf = Influencer.objects.get(id=inf_id)
    user_prof = UserProfile.objects.get(id=user_prof_id)
    log.info("post_email_extraction_blogger_influencer_callback: found inf: %s", inf)
    log.info("post_email_extraction_blogger_influencer_callback: found user_prof: %s", user_prof)
    if inf.email and user_prof.user.email in inf.email:
        log.info("Email (%s) belongs to influencer's found email (%s), setting mapping between user_prof and influencer", user_prof.user.email, inf.email)
        set_userprof_influencer_mapping(inf, user_prof)


def collect_brand_stats(verbose=False, calc_overall=True, selected_date=None, brands=None):
    def pis_data(date_range, platform_name):
        q = models.PostInteractions.objects.filter(
            post__create_date__range=date_range,
            post__platform__platform_name=platform_name)
        return q
    def comments_data(date_range, platform_name):
        return pis_data(date_range, platform_name).filter(if_commented=True).count()
    def likes_data(date_range, platform_name):
        return pis_data(date_range, platform_name).filter(if_liked=True).count()
    def shares_data(date_range, platform_name):
        return pis_data(date_range, platform_name).filter(if_shared=True).count()

    metrics = [
    {
        "name": "likes",
        "get": likes_data,
    },
    {
        "name": "comments",
        "get": comments_data,
    },
    {
        "name": "shares",
        "get": shares_data,
    },
    ]

    #brands = models.Brands.objects.filter(blacklisted=False)
    #brands = models.Brands.objects.filter(blacklisted=False, brandmentions__count_notsponsored__gte=700).distinct()
    #brands = models.Brands.objects.filter(Q(as_competitor__isnull=False)|Q(competitors__isnull=False)).distinct()
    if not brands:
        brands = models.Brands.objects.filter(domain_name='zappos.com')
    cnt = brands.count()
    last_week = datetime.datetime.today() - datetime.timedelta(days=7)
    collection = mongo_utils.get_brands_stats_col()
    if not collection:
        print "Cant get collection"
        return True

    platforms = ['Twitter', 'Facebook', 'Instagram', 'Pinterest', 'Wordpress', 'Blogspot', 'Custom']

    if verbose:
        print "We have", cnt, "brands"

    global_ts = int(selected_date.strftime("%s"))

    dt_range = utils.datetime_range_from_date(selected_date)

    if calc_overall:
        posts_original = models.Posts.objects.filter(create_date__range=dt_range)
        for pname in platforms:
            posts = posts_original.filter(platform_name=pname)
            key_data = {
                "metric": "count",
                "type": pname,
                "brand_id": None,
            }
            pull_data = {
                "$pull": {
                    "samples": {
                        "ts": global_ts,
                    }
                }
            }
            push_data = {
                "$push": {
                    "samples": {
                        "v": posts.count(),
                        "ts": global_ts,
                    }
                }
            }
            collection.update(key_data, pull_data, upsert=True, multi=True)
            collection.update(key_data, push_data, upsert=True)
            for metric in metrics:
                key_data = {
                    "metric": metric["name"],
                    "type": pname,
                    "brand_id": None,
                }
                pull_data = {
                    "$pull": {
                        "samples": {
                            "ts": global_ts,
                        }
                    }
                }
                push_data = {
                    "$push": {
                        "samples": {
                            "v": metric["get"](dt_range, pname),
                            "ts": global_ts,
                        }
                    }
                }
                collection.update(key_data, pull_data, upsert=True, multi=True)
                collection.update(key_data, push_data, upsert=True)
        products = models.ProductModelShelfMap.objects.filter(
            post__influencer__isnull=False,
            img_url_feed_view__isnull=False,
            post__create_date__range=dt_range
        )
        key_data = {
            "metric": "count",
            "type": "Products",
            "brand_id": None,
        }
        pull_data = {
            "$pull": {
                "samples": {
                    "ts": global_ts,
                }
            }
        }
        push_data = {
            "$push": {
                "samples": {
                    "v": products.count(),
                    "ts": global_ts,
                }
            }
        }
        collection.update(key_data, pull_data, upsert=True, multi=True)
        collection.update(key_data, push_data, upsert=True)

    posts_original = models.Posts.objects.filter(create_date__range=dt_range)
    products_all = models.ProductModelShelfMap.objects.filter(post__isnull=False, img_url_feed_view__isnull=False,
                                                              post__create_date__range=dt_range)
    for n, brand in enumerate(brands):
        if verbose:
            print 1+n, "/", cnt
        brand_name = brand.name
        brand_domain_name = brand.domain_name.replace('www.', '').replace('.com', '')
        posts_brands = posts_original.filter(Q(brand_tags__icontains=brand_name) |
                                             Q(brand_tags__icontains=brand_domain_name) |
                                             Q(mentions__icontains=brand_name) |
                                             Q(mentions__icontains=brand_domain_name) |
                                             Q(hashtags__icontains=brand_name) |
                                             Q(hashtags__icontains=brand_domain_name))
        for pname in platforms:
            posts = posts_brands.filter(platform_name=pname)
            key_data = {
                "metric": "count",
                "type": pname,
                "brand_id": brand.id,
            }
            pull_data = {
                "$pull": {
                    "samples": {
                        "ts": global_ts,
                    }
                }
            }
            push_data = {
                "$push": {
                    "samples": {
                        "v": posts.count(),
                        "ts": global_ts,
                    }
                }
            }
            collection.update(key_data, pull_data, upsert=True, multi=True)
            collection.update(key_data, push_data, upsert=True)
            for metric in metrics:
                key_data = {
                    "metric": metric["name"],
                    "type": pname,
                    "brand_id": brand.id,
                }
                pull_data = {
                    "$pull": {
                        "samples": {
                            "ts": global_ts,
                        }
                    }
                }
                push_data = {
                    "$push": {
                        "samples": {
                            "v": metric["get"](dt_range, pname),
                            "ts": global_ts,
                        }
                    }
                }
                collection.update(key_data, pull_data, upsert=True, multi=True)
                collection.update(key_data, push_data, upsert=True)
        products = products_all.filter(product_model__brand=brand)
        key_data = {
            "metric": "count",
            "type": "Products",
            "brand_id": brand.id,
        }
        pull_data = {
            "$pull": {
                "samples": {
                    "ts": global_ts,
                }
            }
        }
        push_data = {
            "$push": {
                "samples": {
                    "v": products.count(),
                    "ts": global_ts,
                }
            }
        }
        collection.update(key_data, pull_data, upsert=True, multi=True)
        collection.update(key_data, push_data, upsert=True)

@baker.command
def insert_brand_data():
    utils.force_db_indexes_usage()

    start_date = datetime.date(2014, 3, 1)
    end_date = datetime.date.today()
    one = datetime.timedelta(days=1)

    domains = ['zappos.com', 'express.com', 'topshop.com', 'shopbop.com', 'thelimited.com',
               'neimanmarcus.com', 'nordstrom.com', 'target.com', 'piperlime.com']
    brands = models.Brands.objects.filter(domain_name__in=domains)

    while start_date <= end_date:
        collect_brand_stats(verbose=True, calc_overall=True, selected_date=start_date, brands=brands)
        start_date += one


def upgrade_brand_to_enterprise(brand):
    customer = stripe.Customer.retrieve(brand.stripe_id)
    plan_sub = None
    for sub in customer.subscriptions.data:
        if sub.plan.id in STRIPE_SUBSCRIPTIONS_PLANS:
            plan_sub = sub
    if plan_sub:
        plan_sub.plan = STRIPE_PLAN_ENTERPRISE
        plan_sub.save()
        brand.refresh_stripe_data()
    else:
        print "Brand was not subscribed"


def create_email_of_list_of_collections(brand):
    inf_groups = models.InfluencerGroupMapping.objects.filter(group__owner_brand=brand)
    print "Got %d influencers" % inf_groups.count()

    infs = set()
    for i in inf_groups:
        infs.add(i.influencer)

    for i in infs:
        print "Blog URL: ", i.blog_url, "\t Blog Name: ", i.blogname, "\t Name: ", i.name, "\t Email: ",
        if i.email_for_advertising_or_collaborations:
            print i.email_for_advertising_or_collaborations
        elif i.email_all_other:
            print i.email_all_other
        else:
            print i.contact_form_if_no_email


def paginate(qs, page=1, paginate_by=10, count=None):
    paginator = BetterPaginator(qs, paginate_by, count=count)
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def extract_attachments(data):
    attachments = data.get('attachments')
    if attachments:
        attachments = [x for x in attachments if type(x) is dict]
        attachments = [(a['filename'], a['path']) for a in attachments]
    return attachments


def render_and_send_message(**kw):
    from debra.mail_proxy import send_test_email
    from debra.account_helpers import get_bleached_template

    data = kw.get('data')

    context = {
        'brand': kw.get('brand'),
        'influencer': kw.get('influencer'),
        "job_mapping": kw.get('job_mapping'),
        'contract': kw.get('contract'),
        'job': kw.get('job'),
        'note': get_bleached_template(data.get('template')) if data.get('bleach', True) else data.get('template'),
        'test_send': kw.get('send_mode', 'normal') in ['test', 'dev_test'],
        'user': kw.get('user'),
        'mp': kw.get('mp'),
        'data': data,
    }

    rendered_message = render_to_string(
        kw.get('template_name'), context).encode('utf-8')

    subject = data.get('subject', kw.get('default_subject')).encode('utf-8')
    if kw.get('send_mode') in ['test', 'dev_test']:
        subject = "({}) {}".format(kw.get('send_mode').upper(), subject)

    attachments = extract_attachments(data)

    params = {
        'sender': kw.get('sender'),
        'subject': subject,
        'body': rendered_message,
        'attachments': attachments
    }

    if kw.get('send_mode', 'normal') in ['test', 'dev_test']:
        resp = send_test_email(brand=kw.get('brand'), **params)
    else:
        resp = kw.get('mp').send_email_as_brand(**params)

    return resp


def send_admin_email_via_mailsnake(subject, body, extra_emails=None):
    """
    Our custom mailing system to use mailsnake because google cloud doesn't allow us to send emails from workers
    """
    from_email = 'atul@theshelf.com'
    from_name = 'Atul'

    admin_emails = settings.ADMINS 
    to_emails = [{'email': email[1], 'type': 'to'} for email in admin_emails]

    if extra_emails:
        to_emails.extend([{'email': x, 'type': 'to'} for x in extra_emails])

    mailsnake_admin_client.messages.send(message={'html': body,
                                            'subject': subject,
                                            'from_email': from_email,
                                            'from_name': from_name,
                                            'to': to_emails})


@task(name="debra.helpers.add_influencers_to_tag", ignore_result=True)
def add_influencers_to_group(group_id, influencer_ids):
    influencers = models.Influencer.objects.filter(id__in=influencer_ids)
    group = models.InfluencersGroup.objects.get(id=group_id)

    for inf in influencers:
        group.add_influencer(inf)


def create_post_collection_copy_for_brand(collection_id, brand_id):
    brand = models.Brands.objects.get(id=brand_id)
    collection = models.PostAnalyticsCollection.objects.get(id=collection_id)

    new_collection = models.PostAnalyticsCollection.objects.get(id=collection_id)
    new_collection.pk = None
    new_collection.creator_brand = brand
    new_collection.user = brand.userprofile and brand.userprofile.user or None
    new_collection.save()

    # for pa in collection.postanalytics_set.all():
    #     pa.pk = None
    #     pa.collection = new_collection
    #     pa.save()

    new_analytics = []
    for pa in collection.postanalytics_set.all():
        pa.pk = None
        pa.collection = new_collection
        new_analytics.append(pa)
    models.PostAnalytics.objects.bulk_create(new_analytics)

    return new_collection


def create_tag_copy_for_brand(collection_id, brand_id):
    brand = models.Brands.objects.get(id=brand_id)
    collection = models.InfluencersGroup.objects.get(id=collection_id)

    new_collection = models.InfluencersGroup.objects.get(id=collection_id)
    new_collection.pk = None
    new_collection.creator_brand = brand
    new_collection.owner_brand = brand
    new_collection.creator_userprofile = brand.userprofile
    new_collection.save()

    inf_ids = models.InfluencerGroupMapping.objects.filter(
        group=collection
    ).values_list('influencer', flat=True)

    # for mapping in mappings:
    #     new_mapping = models.InfluencerGroupMapping.objects.create(
    #         group=new_collection,
    #         influencer_id=mapping.influencer_id)

    # new_mappings = []
    # for mapping in mappings:
    #     new_mapping = models.InfluencerGroupMapping(
    #         group=new_collection,
    #         influencer=mapping.influencer)
    #     new_mappings.append(new_mapping)
    # models.InfluencerGroupMapping.objects.bulk_create(new_mappings)

    if settings.DEBUG:
        add_influencers_to_group(new_collection.id, inf_ids)
    else:
        add_influencers_to_group.apply_async(
            [new_collection.id, inf_ids], queue="celery")

    return new_collection


def create_report_copy_for_brand(report_id, brand_id):
    brand = models.Brands.objects.get(id=brand_id)
    report = models.ROIPredictionReport.objects.get(id=report_id)

    new_report = models.ROIPredictionReport.objects.get(id=report_id)
    new_report.pk = None
    new_report.creator_brand = brand
    new_report.user = brand.userprofile and brand.userprofile.user or None

    new_collection = create_post_collection_copy_for_brand(
        report.post_collection_id, brand_id)

    new_report.post_collection = new_collection
    new_report.save()

    return new_report


def create_tag_from_post_collection_for_brand(collection_id, brand_id, tag_id=None, new_tag_name=None):
    brand = models.Brands.objects.get(id=brand_id)
    collection = models.PostAnalyticsCollection.objects.get(id=collection_id)

    if new_tag_name is None:
        new_tag_name = "Influencers from '{}' collection".format(
            collection.name)

    inf_ids = list(collection.postanalytics_set.exclude(
        post__influencer__isnull=True
    ).values_list(
        'post__influencer', flat=True).distinct())

    if tag_id is not None:
        tag = models.InfluencersGroup.objects.get(id=tag_id)
        tag.influencers_count += len(inf_ids)
    else:
        tag = models.InfluencersGroup(
            name=new_tag_name,
            creator_brand=brand,
            owner_brand=brand,
            influencers_count=len(inf_ids),
            creator_userprofile=brand.userprofile)
    tag.save()

    if settings.DEBUG:
        add_influencers_to_group(tag.id, inf_ids)
    else:
        add_influencers_to_group.apply_async(
            [tag.id, inf_ids], queue="celery")

    # for inf in infs:
    #     new_mapping = models.InfluencerGroupMapping.objects.create(
    #         group=tag,
    #         influencer=inf)

    # infs = models.Influencer.objects.filter(id__on=infs)

    # new_mappings = []
    # for inf in infs:
    #     new_mapping = models.InfluencerGroupMapping(
    #         group=tag,
    #         influencer=inf)
    #     new_mappings.append(new_mapping)
    # models.InfluencerGroupMapping.objects.bulk_create(new_mappings)

    return tag


def create_tag_from_report_for_brand(report_id, brand_id, tag_id=None):
    report = models.ROIPredictionReport.objects.get(id=report_id)

    if tag_id is None:
        new_tag_name = "Influencers from '{}' report".format(report.name)
    else:
        new_tag_name = None

    return create_tag_from_post_collection_for_brand(
        report.post_collection_id, brand_id, tag_id, new_tag_name=new_tag_name)


def create_post_collection_from_tag(tag_id, brand_id=None):
    # hack
    tag = models.InfluencersGroup.objects.get(id=tag_id)
    if brand_id is None:
        brand_id = tag.creator_brand_id
    inf_ids = tag.influencers_mapping.exclude(
        status=models.InfluencerGroupMapping.STATUS_REMOVED
    ).values_list('influencer', flat=True)

    infs = models.Influencer.objects.filter(id__in=inf_ids)

    post_collection = models.PostAnalyticsCollection.objects.create(
        name=tag.name,
        creator_brand_id=brand_id,
        tag_id=tag_id)

    for inf in infs:
        try:
            post = inf.posts_set.all()[0]
        except IndexError:
            print '* failed to find post for inf={}'.format(inf.id)
            continue
        post_analytics = models.PostAnalytics.objects.create(
            post=post,
            post_url=post.url,
            post_found=True,
            collection=post_collection)
        print '* post analytics post_id={}, inf_id={} created'.format(
            post.id, inf.id)

    return post_collection


def migrate_blogger_approval_report(report_id):
    # migrate from using PostAnalytics to InfluencerAnalytics
    report = models.ROIPredictionReport.objects.get(id=report_id)
    post_collection = report.post_collection

    pa_data = post_collection.postanalytics_set.filter(
        Q(approve_status__isnull=False) | Q(notes__isnull=False)
    ).values(
        'post__influencer', 'approve_status', 'notes')

    influencer_collection = models.InfluencerAnalyticsCollection.objects.from_post_collection(
        post_collection)

    inf_data = {}
    for pa in pa_data:
        inf_data[pa['post__influencer']] = {
            'approve_status': pa['approve_status'],
            'notes': pa['notes']
        }

    count = influencer_collection.influenceranalytics_set.count()
        
    for n, inf in enumerate(influencer_collection.influenceranalytics_set.all()):
        inf.__dict__.update(inf_data[inf.influencer_id])
        inf.save()
        print '* {}/{}: {} migrated'.format(n, count, inf.influencer_id)

    report.influencer_analytics_collection = influencer_collection
    report.save()

    return influencer_collection.id


def create_report_from_tag(tag_id, brand_id=None):
    post_collection = create_post_collection_from_tag(tag_id, brand_id)
    report = models.ROIPredictionReport.objects.create(
        creator_brand_id=post_collection.creator_brand_id,
        name=post_collection.name,
        post_collection=post_collection)
    return report


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

def convert_camel_case_to_underscore(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def name_to_underscore(name):
    return name.replace(' ', '_').replace('-', '').lower()


def format_filename(s):
    """Take a string and return a valid filename constructed from the string.
    Uses a whitelist approach: any characters not present in valid_chars are
    removed. Also spaces are replaced with underscores.
    """
    if s is None:
        return None
    s = s.replace('http://', '').replace('https://', '').replace('www.', '')
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in s if c in valid_chars)
    filename = filename.replace(' ','_') # I don't like spaces in filenames.
    filename = filename.replace('.', '_')
    return filename


def update_json(original_json, new_json, extend_list=False):
    """a recursive function that will traverse object down
    to the lowest level and update only those keys that exist in the
    input params
    """
    if type(new_json) == list:
        if not extend_list:
            del original_json[:]
        original_json.extend(new_json)
    elif type(new_json) == dict:
        for k, v in new_json.items():
            if k not in original_json or type(original_json[k]) not in [dict, list]:
                if isinstance(v, basestring):
                    v = v.strip()
                    if not v:
                        v = None
                original_json[k] = v
            else:
                update_json(original_json[k], new_json[k], extend_list)


def get_canonical_urls(url, platform_name):
    if platform_name not in ['Facebook', 'Youtube']:
        url = url.split('?')[0]
    parse_result = urlparse.urlparse(url)
    prefix = '://'.join([parse_result.scheme, parse_result.hostname])
    canonical_prefixes = {
        'Instagram': ['http://instagram.com', 'https://instagram.com'],
        'Facebook': ['https://www.facebook.com'],
        'Twitter': ['https://twitter.com'],
        'Pinterest': ['https://www.pinterest.com', 'http://www.pinterest.com'],
    }.get(platform_name)
    if canonical_prefixes and prefix not in canonical_prefixes:
        url.replace(prefix, canonical_prefixes[0])

    if canonical_prefixes:
        return [url.replace(prefix, p) for p in canonical_prefixes]
    return [url]


def extract_fbid(url):
    # for Facebook posts only
    # not sure if we should take an account on permalink urls, like
    # https://www.facebook.com/permalink.php?story_fbid=489971664439163&id=237086113061054
    parse_result = urlparse.urlparse(url)
    params = urlparse.parse_qs(parse_result.query)
    try:
        fbid = params['fbid'][0]
    except (KeyError, IndexError):
        try:
            fbid = parse_result.path.split('/')[-1]
        except IndexError:
            fbid = None
    if fbid and len(fbid) == 15:
        return fbid


class PageSectionSwitcher(object):

    def __init__(self, sections, selected_section=None,
            url_args=None, counts=None, extra_url_args=None,
            hidden=None, urls=None, extra=None,
            wrapper=None):
        # assert type(sections) in [list, dict, OrderedDict] and len(sections) > 0
        assert type(sections) in [list, dict, OrderedDict]

        self._url_args = url_args
        self._urls = urls
        self._extra_url_args = extra_url_args or {} 
        self._counts = counts
        self._hidden = hidden
        self._extra = extra

        self.wrapper = wrapper

        print 'Hidden:', hidden

        if type(sections) == list:
            if sections and type(sections[0]) == tuple:
                if type(sections[0][1]) != dict:
                    sections = [(k, {'text': v}) for k, v in sections]
            else:
                sections = [(s['value'], s) for s in sections]
        else:
            sections = [(k, v) for k, v in sections.items()]

        self._sections = OrderedDict(
            [(k, self.PageSection(self, k, **v)) for k, v in sections])

        if self._urls:
            if type(self._urls) == list:
                for u, s in zip(self._urls, self._sections.values()):
                    s.url = u
            elif type(self._urls) == dict:
                for k, s in self._sections.items():
                    s.url = self._urls[k]
        if self._extra:
            for k, data in self._extra.items():
                for s, d in data.items():
                    if self._sections.get(s):
                        self._sections[s].extra[k] = d

        if len(self._sections) > 0:
            self.switch(selected_section)

    def to_dict(self):
        return [s.to_dict() for s in self._sections.values()]

    def switch(self, selected_section):
        if selected_section not in self._sections:
            self.selected = None
        elif selected_section is None:
            self.selected = self._sections.keys()[0]
        else:
            self.selected = selected_section

    @property
    def selected_section(self):
        return self._sections.get(self.selected)

    @property
    def sections(self):
        return self._sections.items()

    def get_first_section_matching_criteria(self, predicate):
        try:
            return [
                s for s in self._sections.values() if predicate(s)
            ][0]
        except IndexError:
            pass

    @cached_property
    def first_non_empty_section(self):
        return self.get_first_section_matching_criteria(
            lambda s: s.key >= 0 and s.visible and (s.count is None or s.count > 0))

    @cached_property
    def first_visible_section(self):
        return self.get_first_section_matching_criteria(
            lambda s: s.key >= 0 and s.visible)

    class PageSection(object):

        def __init__(self, switcher, key, text=None, url=None, **kwargs):
            self.switcher = switcher
            self.key = key
            self.text = text
            self.visible = not (
                self.switcher._hidden and self.key in self.switcher._hidden)
            if not callable(url):
                self.url = url
            else:
                args = self.switcher._extra_url_args.get(
                    self.key, self.switcher._url_args)
                if args:
                    self.url = url(args)
            if self.switcher._counts:
                self.count = self.switcher._counts.get(self.key, 0)
            else:
                self.count = None
            self.extra = {}

        def to_dict(self):
            return {
                'key': self.key,
                'text': self.text,
                'visible': self.visible,
                'selected': self.selected,
                'url': self.url,
                'count': self.count or 0,
                'extra': self.extra,
            }

        @property
        def selected(self):
            return self.switcher.selected == self.key


def update_model(data):
    model_class = get_model('debra', data.get('modelName'))
    model_id = data.get('id')
    if model_id:
        model_instance = get_object_or_404(model_class, id=model_id)
    else:
        model_instance = model_class()

    if data.get('delete'):
        print '* removing...'
        model_instance.delete()
        return

    values_to_save = {}
    values_to_save.update(data.get('values', {}))
    values_to_save.update(data.get('default_values', {}))

    values = {}
    for k, v in values_to_save.items():
        k = convert_camel_case_to_underscore(k)
        if isinstance(v, basestring):
            v = v.strip()
            if not v:
                v = None
        if model_instance.__dict__[k] != v:
            values[k] = v
    print '* fields updating: {}'.format(values.keys())

    old_values = {k:v for k, v in model_instance.__dict__.items() if k in values}
    model_instance.__dict__.update(values)

    if model_id and data.get('notifyAboutChanges'):
        try:
            old_values_table = json2html.convert(json=old_values)
        except:
            old_values_table = None
        try:
            new_values_table = json2html.convert(json=values)
        except:
            new_values_table = None
        if new_values_table:
            send_admin_email_via_mailsnake(
                '{}={} model changed'.format(data.get('modelName'), model_id),
                '''
                <h1>{title}</h1>
                <h3>Old Values</h3>
                {old_values}
                <h3>New Values</h3>
                {new_values}
                '''.format(
                    title='{}={} model changed'.format(
                        data.get('modelName'), model_id),
                    old_values=old_values_table or 'Empty',
                    new_values=new_values_table or 'Empty',
                )
            )

    print data.get('json_fields')

    print '* json fields updating'

    for k, v in data.get('json_fields', {}).items():
        try:
            original_value = json.loads(getattr(model_instance, k))
        except Exception:
            print '* json loading problem: ', str(k)
            original_value = {}
        print '* {} updating'.format(k)
        update_json(original_value, v)
        print '* modifed: ', original_value
        setattr(model_instance, k, json.dumps(original_value))

    model_instance.save()
    print '* {} saved: {}'.format(model_class, model_instance.id)
    return model_instance


def escape_angular_interpolation(value):
    return re.sub(r'{{\s*(?P<var>(?!\s*getEscaped).*?)\s*}}', r"{{ getEscaped('\g<var>') }}", value)


def escape_angular_interpolation_reverse(value):
    return re.sub(r"{{\s*getEscaped\('(?P<var>.*?)'\)\s*}}", r"{{ \g<var> }}", value)


def eval_or_return(expression):
    try:
        expr = eval(expression)
    except:
        expr = expression
    for date_format in settings.DATETIME_INPUT_FORMATS:
        try:
            expr = datetime.datetime.strptime(expr, date_format)
        except (TypeError, ValueError):
            pass
        else:
            break
    return expr


def get_or_set_cache(cache_key, getter, cache=None):
    if cache is None:
        cache = mc_cache
    cache_data = cache.get(cache_key)
    if cache_data:
        data = cache_data
    else:
        data = getter()
        cache.set(cache_key, data)
    print '** data: ', data
    return data


class CacheQuerySet(object):

    def __init__(self, serializer, cache=None, unpack=True):
        self._serializer = serializer
        self._cache = cache if cache else redis_cache
        self._unpack = unpack

    def set_cache_key(self, key):
        try:
            self._cache_key
        except AttributeError:
            self._cache_key = key
        else:
            raise Exception('CacheQuerySet: cache_key is already set')
        return self

    @cached_property
    def _cached_data(self):
        try:
            _raw_data = self._raw_items
        except AttributeError:
            _raw_data = None
        if _raw_data is None:
            print '* cache call for {}'.format(self._cache_key)
            _raw_data = self._cache.get(self._cache_key)
        if self._unpack:
            return self._serializer.cache_serializer().unpack(_raw_data)
        return _raw_data
        # return self._serializer.cache_serializer().serialize_iterable(
        #     _raw_data, many=True)

    def _build_index(self):
        self._id_2_item = {item['id']:item for item in self._serialized_items}
        self._indexed = True

    def _find_in_index(self, lookup_id):
        return self._id_2_item[lookup_id]

    def raw(self, items):
        new_queryset = copy.deepcopy(self)
        new_queryset._raw_items = items
        return new_queryset

    def raw_self(self, items):
        self._raw_items = items
        return self

    def all(self, items):
        if self._cached_data is None:
            print '*** DB call for {}'.format(self._cache_key)
        self._serialized_items = self._cached_data if self._cached_data is not\
            None else self._serializer(items, many=True).data
        self._indexed = False
        return self

    def filter(self, predicate):
        if self._serialized_items is None:
            raise Exception('Yo!')
        new_queryset = copy.deepcopy(self)
        new_queryset._serialized_items = filter(predicate,
            self._serialized_items)
        return new_queryset

    def prefetch_related(self, querysets):
        new_queryset = copy.deepcopy(self)
        new_queryset._prefetched_querysets = querysets
        return new_queryset

    def related(self, name, lookup_id):
        return self._prefetched_querysets[name].get(lookup_id)

    def get(self, lookup_id=None):
        if lookup_id:
            if not self._indexed:
                self._build_index()
            return self._find_in_index(lookup_id)
        return self._serialized_items

    def safe_get(self, lookup_id=None):
        try:
            return self.get(lookup_id)
        except KeyError:
            pass


class AdminNotificator(object):

    def __init__(self, name, mute=False):
        self._name = name
        self._mute = mute
    
    def notificate(self, *args, **kwargs):
        print 'NOTIFICATION: args={}, kwargs={}'.format(args, kwargs)
        if not self._mute:
            self._do_notificate(*args, **kwargs)

    def _do_notificate(self, *args, **kwargs):
        raise NotImplementedError


class EmailAdminNotificator(AdminNotificator):

    def _do_notificate(self, subject=None, body=None):
        if subject is None:
            subject = '{}'.format(datetime.datetime.now())
        subject = '[{}] {}'.format(self._name, subject)
        body = body or ''
        send_admin_email_via_mailsnake(subject, body)
