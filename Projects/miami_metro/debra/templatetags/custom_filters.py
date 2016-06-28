import datetime
import re
import pdb
import json

from django import template
from django.utils.safestring import mark_safe

from debra import constants
from debra.models import LotteryTask, Platform, UserProfileBrandPrivilages
from debra.forms import ModifyShelfForm

register = template.Library()


@register.filter
def number_0(value):
    return "{:,}".format(value)


@register.filter
def underscore_capitalize(word):
    return " ".join([part.capitalize() for part in word.split('_')])


@register.filter
def comma_separated_list(lst):
    return ', '.join(map(str, lst))


@register.filter
def unescape(string):
    from debra.serializers import unescape
    return unescape(string)


@register.filter
def common_date_format(dt, visitor=None):
    if not dt:
        return None

    now = datetime.datetime.now()

    short_format = "%b. %d"
    long_format = "%b. %d %Y"

    if dt.year == now.year:
        format = short_format
    else:
        format = long_format

    if visitor and visitor["user"]:
        tz = visitor["user"].get_setting('timezone')
    else:
        tz = None
        format += " UTC"

    if tz:
        dt += datetime.timedelta(hours=int(tz))
    return dt.strftime(format)


@register.filter
def tablify(obj):
    if type(obj) == dict:
        out = ["<table>"]
        for k, v in obj.iteritems():
            out.append("<tr>")
            out.append("<td>")
            out.append(tablify(k))
            out.append("</td><td><pre>")
            out.append(tablify(v))
            out.append("</pre></td></tr>")
        out.append("</table>")
        return mark_safe(u"".join(out))
    elif type(obj) in (list, tuple):
        return mark_safe(u", ".join([tablify(x) for x in obj]))
    else:
        return mark_safe(unicode(obj))


@register.simple_tag
def run_time():
    import random
    return "%08.x" % random.randint(0, 0xffffffff)

@register.filter
def invited_to(mapping, to_job):
    for job in mapping.jobs.all():
        if job.job.id == to_job.id:
            return job
    return None

@register.filter
def get_setting(obj, key):
    return obj.get_setting(key, True)

@register.filter
def get_setting_default_false(obj, key):
    return obj.get_setting(key, False)


@register.filter
def get_setting_outreach(obj, brand_id):
    return obj.get_setting("outreach_brand_%s" % str(brand_id), True)

# stripe filter
@register.filter
def upcoming_invoices(data):
    balance = 0
    out = []
    now = datetime.datetime.now()
    for invoice in data:
        dt = datetime.datetime.fromtimestamp(invoice["period"]["end"])
        dt_str = dt.strftime("%b. %e, %Y")
        total = invoice["amount"]/100.0
        if total > 0 and dt>now:
            out.append({
                'dt': dt_str,
                'total': total
            })
    return out

#####-----< Formatting filters >-----######
@register.filter
def replace_spaces(value):
    """
    :param value: the string to replace spaces in
    :return: the string with all instances of a `` `` replaced with a ``-``
    """
    return str.replace(str(value), ' ', '-')

@register.filter
def user_name_or_email(userprof):
    """
    :param userprof: the :class:`debra.models.UserProfile` instance to choose name or email for
    :return: the ``userprof``'s name if it's set, otherwise their email with everything after the ``@`` sign stripped off.
    """
    strip_email = lambda email: re.sub(r'@\w+\.\w+', "", email)
    return userprof.name if userprof.name else (userprof.influencer.name if userprof.influencer and userprof.influencer.name else strip_email(userprof.user.email))

@register.filter
def blog_name_or_url(userprof):
    """
    :param userprof: the :class:`debra.models.UserProfile` instance to choose blog name or stripped url for
    :return: the ``userprof``'s blog name if it exists, else their blog url with everything up to ``.com`` taken (minus ``http://``).
    """
    strip_url = lambda url: re.sub(r'\.com$', "", (re.sub(r'(http://)?(www\.)?', "", url))) if url else ""
    return userprof.blog_name if userprof.blog_name else (userprof.influencer.blogname if userprof.influencer and userprof.influencer.blogname else strip_url(userprof.blog_page))

@register.filter
def post_title_or_content(post):
    """
    :param post: a filter to intelligently choose the title or content of a :class:`debra.models.Posts` instance
    :return: the ``post`` title if it exists, else its content
    """
    return post.title if post.title else post.content

@register.filter
def remove_dot_com(name):
    """
    :param name: the string to remove ``.com`` from
    :return: the passed ``name`` with ``.com`` removed
    """
    return re.sub(r'\.com/?$', "", name)

@register.filter
def date_format(date, date_format):
    """
    :param date: the :class:`date` instance to format according to the given ``date_format``
    :param date_format: the date_format string to apply to the passed date
    :return: a date string formatted according to ``date_format``
    """
    return date.strftime(date_format)

@register.filter
def zero_if_none(val):
    """
    :param val: the value to return 0 for if it is None
    :return: the value if it is not None, else 0
    """
    return 0 if val is None else val
#####-----</ Formatting filters >-----######

#####-----< Pic filters >-----######
@register.filter
def best_pic_for_profile(userprof):
    """
    :param userprof: The :class:`debra.models.UserProfile` to get the best profile picture for
    :return: the path to the best profile picture for the passed user

    a filter to get the best picture for a user's profile. Preference - in order - is:

    * profile_img_url
    * image2
    * /mymedia/site_folder/images/global/avatar.png
    """
    return userprof.profile_img_url or (userprof.influencer.profile_pic_url if userprof.influencer and userprof.influencer.profile_pic_url else '/mymedia/site_folder/images/global/avatar.png')

@register.filter
def best_square_pic_for_profile(userprof):
    """
    :param userprof: The :class:`debra.models.UserProfile` to get the best square picture for the profile
    :return: the passed user's profile image (in square form) if it exists, otherwise the global square avatar.

    a filter to get the best SQUARE pic for a users profile (this is the same as best pic for profile with the
    exception that we cant use image2)
    """
    return '{im}.small.jpg'.format(im=userprof.profile_img_url) if userprof.profile_img_url \
        else userprof.influencer.profile_pic_url if userprof.influencer and userprof.influencer.profile_pic_url else '/mymedia/site_folder/images/global/avatar.png'

@register.filter
def best_pic_for_shelf(shelf):
    """
    :param shelf: the :class:`debra.models.Shelf` instance to get the best picture for
    :return: the ``shelf``'s image if it exists, otherwise the ``missing_image`` avatar
    """
    return shelf.shelf_img or '/mymedia/site_folder/images/global/missing_image.jpg'

@register.filter
def best_pic_for_product(pmsm):
    """
    :param pmsm: :class:`debra.models.ProductModelShelfMap` instance
    :return: the ``pmsm``'s best image (first try  the img_url_feed_view, then img_url if that doesnt exist)
    """
    return pmsm.img_url_feed_view or pmsm.img_url

@register.filter
def small_pic(pic):
    """
    :param pic: the source of the original image
    :return: the small version of the given ``pic``
    """
    return '{pic}.small.jpg'.format(pic=pic)

@register.filter
def post_pic(post):
    """
    :param post: the :class:`debra.models.Posts` instance to get the picture for
    :return: the first ``img_url`` for the post if it exists. Else the missing image global avatar.
    """
    post_image = '/mymedia/site_folder/images/global/missing_image.jpg'
    try:
        post_image = post.img_urls.pop() if post.img_urls else post_image
    except ValueError:
        pass
    return post_image

@register.filter
def fb_pic(platforms, pic_type):
    """
    :param platforms: a list or Queryset of :class:`debra.models.Platform`
    :param pic_type: one of ``profile`` or ``cover``
    :return: the facebook profile img if it exists, otherwise try and get the twitter profile image..if that also doesn't exist return ``None``

    given a list of platforms, get the Facebook platform and choose either cover or profile image based on passed pic_type
    we give prefernce to facebook because their images have better resolution
    """
    if not platforms:
        return None
    return platforms[0].influencer.cover_pic

#####-----</ Pic filters >-----######

#####Truthy Filters
#------------------
@register.filter
def is_followed_by(user, potential_follower):
    """
    :param user: the :class:`debra.models.UserProfile` instance to check if being followed
    :param potential_follower: the :class:`debra.models.UserProfile` instance to check if following the ``user``
    :return: True if ``potential_follower`` is following ``user``, False otherwise.
    """
    return potential_follower.is_following(user)

@register.filter
def has_posts_for_platform(user_prof, platform_name):
    """
    :param user_prof: the :class:`debra.models.UserProfile` instance to check for having posts for the given ``platform_name``
    :param platform_name: a string representing a platform (i.e. Facebook, Twitter, etc.) of the ``user_prof``'s to check for posts
    :return: True if the ``user_prof`` has posts on the given ``platform_name``. False otherwise.
    """
    return user_prof.has_posts(platform_name)
#####-----</ Truthy filters >-----######

#####-----< Lottery filters >-----######
@register.filter
def url_for_task(userprof, task):
    """
    :param userprof: the :class:`debra.models.UserProfile` instance to get appropriate social media URLs for
    :param task: A dict representing a :class:`debra.models.LotteryTask` instance
    :return: the appropriate social handle for the given ``userprof`` based on the type of ``task``.

    this is used by the lottery widget to choose which social media url for a user to show (in the creation phase)
    based on the task their currently creating.
    """
    if task == LotteryTask.TWITTER_FOLLOW:
        return userprof.twitter_page
    elif task == LotteryTask.FACEBOOK_FOLLOW:
        return userprof.facebook_page
    elif task == LotteryTask.INSTAGRAM_FOLLOW:
        return userprof.instagram_page
    elif task == LotteryTask.BLOGLOVIN_FOLLOW:
        return userprof.bloglovin_page
    elif task == LotteryTask.BLOG_COMMENT:
        return userprof.blog_page
    elif task == LotteryTask.PINTEREST_FOLLOW:
        return userprof.pinterest_page
    else:
        return ""

@register.filter
def task_rendered_value(task):
    """
    :param task: one of a dict representing a :class:`debra.models.LotteryTask` or a :class:`debra.models.LotteryTask` instance.
    :return: a string representing the value of the passed ``task``

    this filter calls the lambda functon for the given task that is responsible for dynamically generating the value
    for the task (what is shown as the task header) using the value of ``task.url_target_name``
    """
    if isinstance(task, dict):
        return task['value']("")
    else:
        target_name = task.url_target_name if task.task_dict != task.CUSTOM else task.requirement_text
        return task.task_dict['value'](target_name) if task.task_dict != task.CUSTOM else task.task_dict['meta']['instructions'](target_name)

@register.filter
def boolean_for_javascript(task):
    """
    :param task: a :class:`debra.models.LotteryTask` instance
    :return: 1 if the task is mandatory, 0 otherwise

    Because javascript booleans are lowercase (true,false) and python has uppercase (True, False), we have a conversion
    problem.
    """
    return 1 if task.mandatory else 0
#####-----</ Lottery filters >-----######


#####-----< Influencer filters >-----######
@register.filter
def get_platform_url(influencer, platform_name):
    """
    :param influencer: An instance of a :class:`debra.models.Influencer`
    :param platform_name: the name of the platform (Facebook, Twitter, etc.) to fetch the url for the given ``influencer``
    :return: the url of the given ``influencer``'s given ``platform_name`` if it exists, otherwise ``''``
    """
    platform = influencer.platforms().filter(platform_name=platform_name)
    return platform[0].url if platform.exists() else ''

@register.filter
def get_blog_platform(platforms, field):
    """
    :param platforms: list or QuerySet of :class:`debra.models.Platform` instances
    :param field: the field (one of ``url`` or ``name``) to get from the blog platform
    :returns: either the url or the name of the ``blog_platform``, filtered from the list of ``platforms``, depending
    on whether ``name`` or ``url`` is passed as the value of ``field``.
    """
    blog_platforms = [p for p in platforms if not p.is_social]
    plat = blog_platforms[0] if blog_platforms else None

    if plat:
        if field == 'name':
            return plat.blogname
        else:
            return plat.url
    return None

@register.filter
def get_missing_social_platforms(platforms):
    """
    :param platforms: list or Queryset of :class:`debra.models.Platform` instances.
    :return: a list of strings containing the names of all the social platforms NOT contained in the passed ``platforms``
    list.
    """
    social_platforms = Platform.SOCIAL_PLATFORMS
    platform_names = [plat.platform_name for plat in platforms]

    return [p for p in social_platforms if p not in platform_names]

#####-----</ Influencer filters >-----######

#####-----< Shelf filters >-----######
@register.filter
def is_like_shelf(shelf):
    return shelf.name == constants.LIKED_SHELF
#####-----</ Shelf filters >-----######


#####-----< Brands filters >-----######
@register.filter
def get_brand_privilages(user):
    return UserProfileBrandPrivilages.objects.filter(user_profile=user).distinct('brand')
#####-----</ Brands filters >-----######

# verbatim
class VerbatimNode(template.Node):

    def __init__(self, text):
        self.text = text

    def render(self, context):
        return self.text


@register.tag
def verbatim(parser, token):
    text = []
    while 1:
        token = parser.tokens.pop(0)
        if token.contents == 'endverbatim':
            break
        if token.token_type == template.TOKEN_VAR:
            text.append('{{')
        elif token.token_type == template.TOKEN_BLOCK:
            text.append('{%')
        text.append(token.contents)
        if token.token_type == template.TOKEN_VAR:
            text.append('}}')
        elif token.token_type == template.TOKEN_BLOCK:
            text.append('%}')
    return VerbatimNode(''.join(text))

# htmlmin
class HtmlminNode(template.Node):

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        from htmlmin import minify
        value = self.nodelist.render(context)
        return minify(value)

@register.tag
def htmlmin(parser, token):
    nodelist = parser.parse(('endhtmlmin',))
    parser.delete_first_token()
    return HtmlminNode(nodelist)

@register.filter
def jsonify(data):
    try:
        return json.dumps(data)
    except:
        return data