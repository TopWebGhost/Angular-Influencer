__author__ = 'atulsingh'

import datetime
import json
import logging
import re
import sys
import traceback
import urlparse
from collections import defaultdict, OrderedDict, Counter
from time import time

import baker
import django.db
import requests
from celery.decorators import task
from django.conf import settings

from debra import constants
from debra import models
from xpathscraper import utils
from . import contentfiltering

log = logging.getLogger('platformdatafetcher.platformutils')

BLACKLISTED_USERNAMES = ['profile.php', 'pages', 'blog', 'en', 'sharer.php']
STRIPPED_POSTFIXES = ['/boards', '/pins']

URL_SHORTENERS_DOMAINS = ['tinyurl.com', 'bit.ly', 'goo.gl', 't.co']
DEFAULT_SHORTENED_URLS_TO_RESOLVE = 30

PLATFORM_NAME_DEFAULT = 'blog'

PDO_LATEST_EXCLUDED_PREFIXES = [
    'fieldchange',
]


def _domain_to_regex(domain):
    return re.compile(r'(^|(.*\.)){}$'.format(re.escape(domain)))


class PLATFORM_DOMAIN_REGEX:
    BLOGLOVIN = _domain_to_regex('bloglovin.com')
    FACEBOOK = _domain_to_regex('facebook.com')
    FASHIOLISTA = _domain_to_regex('fashiolista.com')
    GPLUS = _domain_to_regex('plus.google.com')
    INSTAGRAM = _domain_to_regex('instagram.com')
    LOOKBOOK = _domain_to_regex('lookbook.nu')
    PINTEREST = _domain_to_regex('pinterest.com')
    TUMBLR = _domain_to_regex('tumblr.com')
    TWITTER = _domain_to_regex('twitter.com')
    YOUTUBE = _domain_to_regex('youtube.com')

    SOCIAL_DOMAINS = (
        BLOGLOVIN,
        FACEBOOK,
        FASHIOLISTA,
        GPLUS,
        INSTAGRAM,
        LOOKBOOK,
        PINTEREST,
        TUMBLR,
        TWITTER,
        YOUTUBE,
    )
    NON_SOCIAL_DOMAINS = ()
    ALL = SOCIAL_DOMAINS + NON_SOCIAL_DOMAINS


# A list of tuples (platform name, regexp for profile url, regexps for invalid urls)
PLATFORM_PROFILE_REGEXPS = [
    # We shouldn't confuse Blogspot blogs with blogspot profiles
    #('Blogspot', r'.*/blogger.com/profile/.*', [
    #]),
    ('Pinterest', r'.*pinterest.com/.*', [
        r'.*/pin/.*',
    ]),
    ('Twitter', r'.*twitter.com/.*', [
        r'.*/share\?.*',
        r'.*/intent/.*',
        r'.*/favorite/.*',
        r'.*/search?.*',
        r'.*/statuses/.*',
        r'.*/status/',
        r'.*support.twitter.com.*',
        r'.*/forums/.*',
        r'.*dev.twitter.com.*',
        r'.*/signup/?$',
        r'.*/signup\?',

    ]),
    ('Instagram', r'(?:.*instagram.com/.*|.*statigr.am/.*|.*followgram.me/.*)', [
        r'.*/p/.*',
    ]),
    ('Facebook', r'.*facebook.com/.*', [
        r'.*/login.php.*',
        r'.*/l.php.*',
        r'.*/media/.*',
        r'.*/help/.*',
        r'.*/sharer.php/.*',
        r'.*/sharer.php.*',
        r'.*/photos/.*',
        r'.*/photo.php.*',
        r'.*/story.php.*',
    ]),
    ('Bloglovin', r'.*bloglovin.com.*/.*', [
    ]),
    ('Tumblr', r'.*tumblr.com(/.*|$)', [
        r'.*tumblr.com/login.*',
        r'.*tumblr.com/share\?.*',

    ]),
    ('Youtube', r'.*youtube.com/.*', [
    # ('Youtube', r'(?:.*youtube.com/.*|.*youtu.be/.*|.*y2u.be/.*)' , [ # Two last are for vids only, do not post to channels/pages
        r'.*youtube.com/profile.*',
        r'.*youtube.com/watch\?.*',
    ]),
    ('Lookbook', r'.*lookbook.nu/.*', [
        r'.*/widget/.*',
        r'.*/look/.*',
        r'.*lookswidget.*',
        r'.*fanswidget.*',
    ]),
    ('Fashiolista', r'.*fashiolista.com/.*', [
    ]),
    ('Gplus', r'.*plus\.google\.com/.*', [
    ]),
]


def social_platform_name_from_url(blog_url, url, allow_insta_posts=False):
    """Discover a *social* platform name from blog_url (this method
    does not work for blogs.
    :param allow_insta_posts -- if True then it will count instagram posts as instagram
            platform url with current implementation
    """
    assert url

    if blog_url and not blog_url.endswith('/'):
        blog_url += '/'

    domain = utils.domain_from_url(url)
    if 'blogspot.com' in domain or 'wordpress.com' in domain:
        return PLATFORM_NAME_DEFAULT

    if blog_url and blog_url in url:
        return PLATFORM_NAME_DEFAULT

    if url.startswith(('javascript', 'about')):
        return PLATFORM_NAME_DEFAULT

    if ' ' in url.strip():
        return PLATFORM_NAME_DEFAULT

    if url.lower().endswith(('.jpg', '.jpeg', '.png', 'gif',)):
        return PLATFORM_NAME_DEFAULT

    for name, regexp, n_regexps in PLATFORM_PROFILE_REGEXPS:
        if re.match(regexp, url):
            if allow_insta_posts is True and name == 'Instagram':
                return name
            if not any(re.match(n_r, url) for n_r in n_regexps):
                return name
    return PLATFORM_NAME_DEFAULT


def meaningful_domain_fragment(url):
    url = url.lower()
    if social_platform_name_from_url(None, url) != PLATFORM_NAME_DEFAULT:
        return None
    domain = utils.domain_from_url(url)
    domain = utils.strip_last_domain_component(domain)
    parts = domain.split('.')
    parts = [p for p in parts if p not in ['blogspot', 'wordpress']]
    return ''.join(parts) or None


def url_to_handle(url, new_blogspot_duplicate_detection_logic=False):
    """Normalizes a url by removing protocol, www., international blogspot domains
    to become suitable for saving in validated_handle.
    """
    # url = url.lower()
    if not url.startswith('http'):
        url = 'http://' + url
    parsed = urlparse.urlsplit(url)
    netloc = utils.remove_prefix(parsed.netloc, 'www.')
    netloc = netloc.lower()
    path = parsed.path.rstrip('/')
    param = ''
    if 'blogspot.' in netloc:
        if not netloc.endswith('.com'):
            if new_blogspot_duplicate_detection_logic:
                # created this on June 22nd 2015, not yet using this
                # the question really is that if a user buys www.blah.blogspot.com can a different user buy
                # www.blah.blogspot.co.uk? If so, we can't automatically mark them as duplicates
                # for a url candidate like this http://atlantic-pacific.blogspot.co.il, the above one will create
                # http://atlantic-pacific.blogspot.co.com which is wrong.
                # what we want is http://atlantic-pacific.blogspot.com to see if it's identical to the other urls we have.
                netloc = netloc[:netloc.find('blogspot.') + len('blogspot.')] + 'com'
            else:
                netloc = utils.strip_last_domain_component(netloc) + '.com'

    if netloc.endswith('facebook.com'):
        # Facebook is special: id or profile prams should be added
        parsed_qs = urlparse.parse_qs(parsed.query, keep_blank_values=True)
        if 'id' in parsed_qs:
            param = '?id=%s' % parsed_qs['id'][0]
    return netloc + path + param


_normalize_gplus_uid_matcher = re.compile(r'(/u/[0-9](/[^0-9][^/]*)?)?(?P<uid>/[0-9]{6,})', re.IGNORECASE)
_normalize_gplus_username_matcher = re.compile(r'(/u/[0-9](/[^0-9][^/]*)?)?/\+(?P<username>[^/]+)', re.IGNORECASE)


def normalize_social_url(url):
    """Converts a social link to a normalized form,
    returns the original url if it is not social or can't be normalized.
    """
    parsed = urlparse.urlsplit(url)
    if 'twitter.com' in parsed.netloc:
        if parsed.path and parsed.path.startswith('/intent/follow') and parsed.query:
            params = urlparse.parse_qs(parsed.query)
            if 'screen_name' in params:
                screen_name = params['screen_name'][0]
                return settings.TWITTER_USER_URL_TEMPLATE.format(screen_name=screen_name)
    if 'stagram.com' in parsed.netloc:
        if parsed.path and parsed.path.startswith('/n/'):
            last_part = parsed.path.rstrip('/').split('/')[-1]
            if last_part and len(last_part) > 2:
                return 'https://instagram.com/%s' % last_part

    if 'plus.google.com' in parsed.netloc and parsed.path:
        uid_match = _normalize_gplus_uid_matcher.search(parsed.path)
        if uid_match:
            return 'https://plus.google.com%s' % uid_match.group('uid')
        username_match = _normalize_gplus_username_matcher.search(parsed.path)
        if username_match:
            return 'https://plus.google.com/+%s' % username_match.group('username')
    return url


def influencer_platforms_from_url_fields(influencer):
    res = []
    for platform_name, field_name in models.Influencer.platform_name_to_field.items():
        url_str = getattr(influencer, field_name)
        if not url_str:
            continue
        for url in url_str.split():
            pl = models.Platform(influencer=influencer, platform_name=platform_name, url=url)
            res.append(pl)
    return res


@task(name="platformdatafetcher.platformutils.save_platforms_from_url_fields", ignore_result=True)
@baker.command
def save_platforms_from_url_fields(influencer_id, to_save=False):
    from platformdatafetcher import platformextractor

    influencer = models.Influencer.objects.get(id=int(influencer_id))
    with OpRecorder(operation='save_platforms_from_url_fields', influencer=influencer) as opr:
        log.debug('Saving platforms to_save=%r inf=%r', to_save, influencer)
        blog_platform_q = models.Platform.objects.filter(url=influencer.blog_url)
        if not blog_platform_q.exists():
            log.debug('Blog platform does not exist')
            return [], []
        blog_platform = blog_platform_q[0]

        platforms_from_fields = influencer_platforms_from_url_fields(influencer)
        validated, not_validated = platformextractor.convert_or_save_platforms(
            blog_platform, platforms_from_fields, to_save)

        log.debug('Validated: (%d) %s', len(validated), validated)
        log.debug('Not validated: (%d) %s', len(not_validated), not_validated)

        data_validated = [(x[0].url, x[1]) for x in validated]
        data_not_validated = [pl.url for pl in not_validated]
        opr.data = dict(validated=data_validated, not_validated=data_not_validated)

        return validated, not_validated


class OpRecorder(object):

    """Creates :class:`debra.models.PlatformDataOp` and creates or updates
    :class:`debra.models.PdoLatest` model that records execution time and
    potential errors encountered during execution of an operation within a ``with`` block.

    When a ``with`` block is not used, then :meth:`OpRecorder.register_exception` or
    :meth:`OpRecorder.register_success` should be called manually.

    :attr:`OpRecorder.data` attribute can be used to store additional data serialized to JSON.

    :param propagate: tells if exceptions should be propagated when raised from a
        ``with`` block (default is ``True``).
    """

    def __init__(self, operation=None, platform=None, influencer=None, product_model=None, post=None,
                 follower=None, post_interaction=None, brand=None, spec_custom=None, propagate=True,
                 _pdo=None):
        if _pdo is not None:
            self.pdo = _pdo
        else:
            self.pdo = models.PlatformDataOp.objects.create(operation=operation,
                                                            platform=platform,
                                                            influencer=influencer,
                                                            product_model=product_model,
                                                            post=post,
                                                            follower=follower,
                                                            post_interaction=post_interaction,
                                                            brand=brand,
                                                            spec_custom=spec_custom)

            # Do not save PdoLatest entries for excluded operations and
            # post/post_interaction tasks
            if (not any(operation.startswith(prefix) for prefix in PDO_LATEST_EXCLUDED_PREFIXES) and
                    not post
                    and not post_interaction):
                models.PdoLatest.save_latest(operation=operation, started_dt=self.pdo.started,
                                             platform=platform,
                                             influencer=influencer,
                                             product_model=product_model,
                                             follower=follower,
                                             brand=brand)
        self.propagate = propagate

    @property
    def data(self):
        if self.pdo.data_json is None:
            return None
        return json.loads(self.pdo.data_json)

    @data.setter
    def data(self, data):
        self.pdo.data_json = json.dumps(data)
        self._save_pdo()

    def register_exception(self):
        error_msg, error_tb = self._format_error(*sys.exc_info())
        self._register_exception_from_args(error_msg, error_tb)

    def is_exception_registered(self):
        return self.pdo.error_msg is not None

    def _save_pdo(self):
        try:
            self.pdo.save()
        except django.db.DatabaseError:
            log.exception('DatabaseError while saving PlatformDataOp, retrying with short data')
            self.pdo.data_json = json.dumps('toolong')
            try:
                self.pdo.save()
            except:
                log.exception('Exception while retrying saving PlatformDataOp with short data')
                if self.propagate:
                    raise

    def register_success(self):
        self.pdo.error_msg = None
        self.pdo.finished = datetime.datetime.now()
        self._save_pdo()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        error_msg, error_tb = self._format_error(exc_type, exc_value, tb)
        self._register_exception_from_args(error_msg, error_tb)

        if error_msg:
            log.error(error_msg + '\n' + error_tb)

        return not self.propagate

    def _format_error(self, exc_type, exc_value, tb):
        error_msg, error_tb = None, None
        if exc_type is not None:
            error_msg = u'%r %r %r' % (exc_type, exc_value, getattr(exc_value, 'message', None))
            error_tb = '\n'.join(traceback.format_tb(tb)) if tb else None
        return (error_msg, error_tb)

    def _register_exception_from_args(self, error_msg, error_tb):
        self.pdo.error_msg = error_msg
        self.pdo.error_tb = error_tb
        self.pdo.finished = datetime.datetime.now()
        self._save_pdo()


class TaskSubmissionTracker(object):
    class OperationContext(object):
        def __init__(self, name, owner):
            self.name = name
            self.owner = owner
            self.children = []
            self.elapsed_time = 0.0

        def __enter__(self):
            self.parent_context = self.owner.context
            if self.parent_context:
                self.parent_context.add_child(self)
            self.owner.context = self
            self.start = time()

            return self

        def __exit__(self, exc_type, exc_value, tb):
            self.owner.context = self.parent_context
            self.end = time()
            self.elapsed_time = self.end - self.start
            return False

        def add_child(self, child):
            self.children.append(child)

        def get_report_lines(self, depth=0):
            yield '{depth_prefix}{name}: {elapsed_time:.2f} s'.format(
                depth_prefix=depth * '-' if depth > 0 else '',
                name=self.name,
                elapsed_time=self.elapsed_time,
            )

            for child in self.children:
                for line in child.get_report_lines(depth=depth + 1):
                    yield line

    def __init__(self):
        self.context = None
        self.counter = Counter()

    def operation(self, name):
        return self.OperationContext(name, self)

    def total(self):
        self.root_context = self.OperationContext("Total", self)
        return self.root_context

    def count_task(self, name):
        self.counter[name] += 1

    def get_task_count_lines(self):
        for task_name, count in sorted(self.counter.items(), key=lambda item: item[0]):
            yield '{}: {}'.format(task_name, count)

    def generate_report(self):
        operation_lines = '\n'.join(list(self.root_context.get_report_lines(depth=0)))
        count_lines = '\n'.join(list(self.get_task_count_lines()))

        return '''
OPERATIONS:
{operation_lines}

TASK COUNTS:
{count_lines}
'''.strip().format(operation_lines=operation_lines, count_lines=count_lines)


def record_simple_op(**pdo_kwargs):
    assert 'operation' in pdo_kwargs
    pdo = models.PlatformDataOp(**pdo_kwargs)
    pdo.save()
    if not pdo.finished:
        pdo.finished = pdo.started
        pdo.save()
    return pdo


def record_field_change(cause, field_name, old_value, new_value, **pdo_kwargs):
    operation = 'fieldchange_%s' % field_name
    try:
        data_json = json.dumps(OrderedDict([
            ('cause', cause),
            ('field', field_name),
            ('old', old_value),
            ('new', new_value),
        ]))
    except (ValueError, TypeError):
        data_json = json.dumps({'error': 'invalid_json_data'})
    pdo = record_simple_op(operation=operation, data_json=data_json, **pdo_kwargs)
    return pdo


def set_url_not_found(message, platform, to_save=True):
    '''
    Mark platform URL as invalid due to request errors or other problems.

    Also sets the activity level to ACTIVE_UNKNOWN since we will not be fetching that platform anymore.
    '''
    if not platform.url_not_found:
        record_field_change(message, 'url_not_found', platform.url_not_found, True, platform=platform)
        platform.activity_level = models.ActivityLevel.ACTIVE_UNKNOWN
        platform.url_not_found = True
    # this ensures that we can correctly create this platform for the right influencer
    # as we don't allow more than one platform to have the same validated handle
    platform.validated_handle = None
    if to_save:
        platform.save()
    # this is to ensure that we remove the posts from the ES index
    platform.influencer.date_edited = datetime.datetime.now()
    if to_save:
        platform.influencer.save()


def unset_url_not_found(message, platform):
    '''
    Mark platform URL as invalid to False.
    '''
    if platform.url_not_found:
        record_field_change(message, 'url_not_found', platform.url_not_found, False, platform=platform)
        platform.url_not_found = False
        platform.save()


def fetch_social_url(url, timeout=10):
    kwargs = {'url': url, 'timeout': timeout, 'verify': False}

    # TODO: these two lines were commented out before
    if social_platform_name_from_url(None, url) != 'Facebook':
        kwargs['headers'] = utils.browser_headers()

    r = requests.get(**kwargs)
    return r


_URL_SHORTENER_CACHE = {}
_URL_SHORTENER_MAX_SIZE = 10000


def resolve_shortened_urls(content, to_resolve=DEFAULT_SHORTENED_URLS_TO_RESOLVE, url_fetch_timeout=10):
    urls = contentfiltering.re_find_urls(content)
    urls = [u for u in urls if utils.domain_from_url(u).lower() in URL_SHORTENERS_DOMAINS]
    urls = urls[:to_resolve]
    log.debug('Resolving shortened urls: %r', urls)
    for u in urls:
        try:
            if u not in _URL_SHORTENER_CACHE:
                if len(_URL_SHORTENER_CACHE) >= _URL_SHORTENER_MAX_SIZE:
                    log.warn('Clearing url shortener cache')
                    _URL_SHORTENER_CACHE.clear()
                _URL_SHORTENER_CACHE[u] = utils.resolve_http_redirect(u, url_fetch_timeout)
            resolved = _URL_SHORTENER_CACHE[u]
        except:
            log.exception('While resolving %r', u)
            continue
        content = content.replace(u, resolved)
    return content


def iterate_resolve_shortened_urls(content, iterations=2):
    for i in xrange(iterations):
        content = resolve_shortened_urls(content)
    return content


def exclude_influencers_disabled_for_automated_edits(query):
    query = query.exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    query = query.exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
    return query


def exclude_platforms_disabled_for_automated_edits(query):
    query = query.exclude(influencer__validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    query = query.exclude(influencer__validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
    return query


@baker.command
def test_platform_validation():
    validated_infs = models.Influencer.objects.filter(
        validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    log.info('Total validated_infs: %d', validated_infs.count())
    validated_infs = validated_infs[:100]
    total_validated, total_not_validated = [], []
    reasons = defaultdict(int)
    for inf in validated_infs:
        validated, not_validated = save_platforms_from_url_fields(inf.id)
        total_validated += validated
        total_not_validated += not_validated
        for pl, reason in validated:
            reasons[reason] += 1

        log.info('total_validated: %d, total_not_validated: %d',
                 len(total_validated),
                 len(total_not_validated))
        log.info('reasons: %s', reasons)


# at least 10 digits
_username_gplus_numeric_uid_matcher = re.compile(r'[0-9]{10,}')


def username_from_facebook_url(url):
    '''
    Extract FB username from URL.

    If it fails, it does a HTTP request to that URL, detects redirects and attempts to extract
    the username from the redirected URL.
    '''
    def username_from_url(url):
        path_parts = urlparse.urlparse(url).path.split('/')
        path_parts = [pp for pp in path_parts if pp]
        if len(path_parts) == 0:
            return None
        if len(path_parts) == 1 and not path_parts[0].endswith('.php'):
            return path_parts[0]
        if 'page' in path_parts[0].lower() or 'people' in path_parts[0].lower():
            # Considering this example: https://www.facebook.com/pages/A-TRENDY-LIFE/104747756232737
            # we should return last part of this url's path
            # or https://www.facebook.com/people/Snezana-Petreski/100008418961626

            # return path_parts[1]
            return path_parts[-1]

        if len(path_parts) == 2 and path_parts[-1].lower() in ('info', 'about'):
            return path_parts[0]
        return None

    username = username_from_url(url)
    if not username:
        try:
            response = requests.get(url, verify=False)
            redirected_url = response.url
            if redirected_url != url:
                username = username_from_url(redirected_url)
        except Exception:
            log.exception('Error resolving Facebook redirect for: {}'.format(url))

    return username


def username_from_platform_url(url):
    url = url.rstrip('/')
    if url.endswith('/#'):
        url = url[:-2]
    if '#!/' in url:
        url = url.replace('#!/', '/').replace('//', '/')
    for postfix in STRIPPED_POSTFIXES:
        url = utils.remove_postfix(url, postfix)

    domain = utils.domain_from_url(url)
    # TODO: think if we should lower() the path part of given url?
    # Exceptions (case-dependant): youtube.com/channel/,
    if domain != 'youtube.com' or 'youtube.com/channel/' not in url.lower():
        url = url.lower()

    if domain == 'facebook.com':
        return username_from_facebook_url(url)

    if domain.endswith('tumblr.com'):
        tumblr_name = domain[:-10]
        return tumblr_name if len(tumblr_name) > 0 else None

    path = urlparse.urlsplit(url).path
    if not path:
        return None

    parts = path.split('/')
    parts = [p for p in parts if p.strip()]
    parts = [p for p in parts if p not in BLACKLISTED_USERNAMES]
    if not parts:
        return None

    # Youtube can have urls like:
    # https://www.youtube.com/channel/UCIzI6LQzuudmdbtXhuZpBmA/videos
    # http://www.youtube.com/user/raechelmyers/videos
    # https://www.youtube.com/c/Minimalistbaker
    # https://www.youtube.com/watch?v=Fky6hpTlBZU
    # https://www.youtube.com/results?search_query=some_query
    # First three are good for us
    # https://support.google.com/youtube/answer/6180214?hl=en

    if domain == 'youtube.com':
        # ID-based channel URL
        lowercase_parts = map(lambda s: s.lower(), parts)
        if 'channel' in lowercase_parts:
            username_idx = lowercase_parts.index('channel')
            if username_idx >= 0 and len(parts) >= username_idx + 2:
                return parts[username_idx+1]
        # Legacy username channel URL
        elif 'user' in parts:
            username_idx = parts.index('user')
            if username_idx >= 0 and len(parts) >= username_idx + 2:
                return parts[username_idx+1]
        # Custom channel URL
        elif 'c' in parts:
            username_idx = parts.index('c')
            if username_idx >= 0 and len(parts) >= username_idx + 2:
                return parts[username_idx+1]
        # plain username
        elif len(parts) == 1 and parts[0] not in [
            'create_channel', 'playlist', 'results', 'channels',
            'subscription_manager', 'about', 'testtube',
        ]:
            return parts[0]
        return None

    if domain == 'plus.google.com':
        if len(parts) > 0 and 'communities' in parts[0].lower():
            # Community pages not supported.
            return None

        numeric_ids = [part for part in parts if _username_gplus_numeric_uid_matcher.match(part)]
        if numeric_ids:
            return numeric_ids[0]
        plus_prefixed_usernames = [part for part in parts if part.startswith('+')]
        if plus_prefixed_usernames:
            return plus_prefixed_usernames[0].lstrip('+')
        return None

    def user_part(p):
        if '?' in p:
            p = p.split('?', 1)[0]
        return not p.isdigit()

    maybe_user_parts = filter(user_part, parts)
    if not maybe_user_parts:
        # for bloglovin, url with a number only is a valid handle
        if domain == 'bloglovin.com':
            return parts[-1]
        return None

    username = maybe_user_parts[-1]
    if '?' in username:
        username = username.split('?', 1)[0]
    username = username.replace('@', '').replace('#', '').replace('!', '')
    if any(username.lower() == bu for bu in BLACKLISTED_USERNAMES):
        return None
    return username


def check_fb_platforms():
    from debra.models import Influencer

    infs = Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True).exclude(fb_url__isnull=True)

    ctr = 0
    potential_ctr = 0
    bad_inf_ctr = 0
    good_inf_ctr = 0
    for inf in infs:

        # finding all fb platforms
        fb_plats = inf.platforms().filter(platform_name='Facebook')

        if fb_plats.exclude(url_not_found=True).count() == 0:
            # None of the platforms are valid
            potential_ctr += 1

            # handle_social_handle_updates(inf, 'fb_url', inf.fb_url)
            # fb_plats = inf.platforms().filter(platform_name='Facebook').exclude(url_not_found=True)
            # if fb_plats.count() == 1:
            #     FacebookFetcher(fb_plats[0], policy_for_platform(fb_plats[0]))
            #     good_inf_ctr += 1
            # else:
            #     log.error('Influencer %s has no facebook platforms even after handle_social_handle_updates')
            #     bad_inf_ctr += 1

        ctr += 1
        if ctr % 1000 == 0:
            print('%s Influencers performed' % ctr)

    log.info('Total %s Influencers have been performed' % ctr)
    log.info('%s potential Influencers have passed the fb_plats' % potential_ctr)
    log.info('%s Influencers have been refreshed' % good_inf_ctr)
    log.info('%s Influencers have problems after handle_social_handle_updates' % bad_inf_ctr)


def check_user_id(id_or_url):
    """
    Tester for testing facebook users via facebook graph API
    :param id_or_url: facebook url or id of a user
    :return:
    """
    from django.conf import settings
    import requests
    params = {'access_token': '%s|%s' % (settings.FACEBOOK_APP_ID, settings.FACEBOOK_APP_SECRET)}
    postfix = '/v2.5/%s' % id_or_url
    url = settings.FACEBOOK_BASE_URL + postfix
    print(url)
    resp = requests.get(url, params=params, verify=False)
    userdata = resp.json()
    print(userdata)
    print('user\'s id: %s' % userdata.get('id'))


def get_youtube_channel_for_url(url=None):
    """
    Returns youtube channel url by its video url if it is valid youtube video url.

    Channel urls are like:
    https://www.youtube.com/channel/UCIzI6LQzuudmdbtXhuZpBmA/videos
    http://www.youtube.com/user/raechelmyers/videos
    https://www.youtube.com/c/Minimalistbaker

    Video urls are like:
    https://www.youtube.com/watch?v=Fky6hpTlBZU
    https://youtu.be/Fky6hpTlBZU
    http://y2u.be/Fky6hpTlBZU

    :param url:
    :return:
    """

    good_video_urls_regexp = r'(?:.*youtube.com\/watch\?.+|.*youtu.be\/.+|.*y2u.be\/.+)'
    good_channel_urls_regexp = r'(?:.*youtube.com\/channel\/.+|.*youtube.com\/user\/.+|.*youtube.com\/c\/.+)'

    if url is None:
        return None

    elif re.match(good_channel_urls_regexp, url):
        # it is already a channel url
        return url

    elif re.match(good_video_urls_regexp, url):
        # it is a video url, fetching channel's url with XBrowser
        # it is a video url, fetching channel's url with XBrowser
        import requests
        import lxml.html
        # need headers={...}/verify=False, otherwise it generates SSLError:
        # bad handshake: Error([('SSL routines', 'SSL3_GET_SERVER_CERTIFICATE', 'certificate verify failed')],)
        # and will not return a resultative response.
        r = requests.get(url, headers=utils.browser_headers(), verify=False)
        tree = lxml.html.fromstring(r.content)
        elems = tree.xpath("//div[@class='yt-user-info']/a")
        if elems and len(elems) > 0:
            elem = elems[0]
            v = elem.attrib.get('href')
            if v:
                channel_url = "https://www.youtube.com" + v
                return channel_url
        return None

        # with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
        #                        load_no_images=True, timeout=10) as xb:
        #
        #     # setting timeouts to xb instance
        #     xb.driver.set_script_timeout(5)
        #     xb.driver.implicitly_wait(5)
        #
        #     xb.driver.get(url)
        #     module_time.sleep(2)
        #
        #     channel_node = xb.driver.find_element_by_xpath("//div[@class='yt-user-info']/a")
        #     channel_node.click()
        #     module_time.sleep(2)
        #     channel_url = xb.driver.current_url
        #     return channel_url

    else:
        return None


def get_youtube_user_from_channel(url):
    """
    Move from
    https://www.youtube.com/channel/UC_Dk3tBqRF9Ig9MTOjU6weA
    to
    https://www.youtube.com/user/lufyenzo
    """
    import lxml.html

    if not url or not re.search('youtube.com/c(hannel)?/', url.lower()):
        return
    r = requests.get(url, verify=False)
    tree = lxml.html.fromstring(r.content)
    user_urls = tree.xpath('//meta[@property="og:url"]/@content')
    if not user_urls:
        return
    user_url = user_urls[0]
    if 'youtube.com/user/' in user_url:
        return user_url.lower()


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
