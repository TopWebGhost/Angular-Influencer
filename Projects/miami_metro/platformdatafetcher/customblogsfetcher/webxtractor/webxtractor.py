#!/usr/bin/env python
# -*- coding: utf-8 -*-
# webxtractor lib
#
####################################################################################################

"""
~~~ webXtractor 0.1.0 ~~~

The web-content extraction lib.

>>> from webxtractor import BlogXtractor, PostXtractor
>>> blogxtractor = BlogXtractor()
>>> blog = blogxtractor.extract(url='http://example.com')
>>> print blog.current_page_number
1
>>> print blog.current_page_url
http://example.com
>>> print blog.next_page_url
http://example.com/page/2
>>> blog = blogxtractor.extract(
    url=blog.next_page_url,
    prev_page_url=blog.current_page_url,
    prev_page_number=blog.current_page_number,
    )
>>> print blog.current_page_url
http://example.com/page/2
>>> print len(blog.posts)
10
>>> print blog.posts[0].url
http://example.com/post
>>> postxtractor =  PostXtractor()
>>> post = postxtractor.extract(url=blog.posts[0].url)
>>> print post.title
-TITLE-
>>> print post.publish_date
2014-01-01 00:00:00
>>> print post.text
Blah-blah-blah[...]
>>> print post.html
<p id="content">Blah-blah-blah[...]
>>> print len(post.images)
5
>>> print post.images[0].url
http://example.com/image.jpeg
>>> print post.images[0].width
1600
>>> print post.images[0].alt
big-image
>>> print len(post.comments)
10
>>> print post.comments[5].url
http://example.com/post#comment-6
>>> print post.comments[5].author_name
Bob Smith
>>> print post.comments[5].author_url
http://bob.com
>>> print post.comments[5].text
hi dude!
>>> print post.comments[5].html
<p id="comment-6">hi dude![...]
>>> print post.comments[5].publish_date
2014-01-02 05:20:00

"""

####################################################################################################


import os
import sys
import re
import copy
import itertools
import urllib2
import codecs
import encodings
import struct
import datetime
import logging
import threading
from Queue import Queue
from urlparse import urlparse
from time import time
from collections import deque
from difflib import SequenceMatcher
from dateutil import parser as date_parser
try:
    from htmlentitydefs import name2codepoint
except ImportError:
    from html.entities import name2codepoint
try:
    from lxml import etree
    from lxml.etree import XPath
    from lxml.html import tostring, document_fromstring, HtmlElement
    from lxml.html.clean import Cleaner
except ImportError:
    raise ImportError("lxml lib is required")
try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        raise ImportError("json lib is required")


####################################################################################################


# Setup logging
logging.basicConfig(level=logging.INFO)
xLogger = logging.getLogger('webXtractor')


####################################################################################################


# HTTP headers
USER_AGENT = 'Mozilla/5.0 (X11; Linux i686; rv:28.0) Gecko/20100101 Firefox/28.0'

# The minimum actual image size
# Images with the actual size less than this settings will not be processed
_MIN_IMAGE_WIDTH = 400 # ?
_MIN_IMAGE_HEIGHT = 350 # ?

# Image formats for processing
# This setting is used to minimize the number of network requests
_IMAGE_FORMATS = ('jpeg', 'jpg', 'png')

# Punctuation characters
_PUNCTUATION = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'

# The title delimiters
_TITLE_DELIMITERS = (' | ', ' - ', ' :: ', ' / ', ' > ', ' ~ ', ': ', u' » ', u' « ', u' — ')

# Positive smileys
POSITIVE_EMOTIONS = [
    ':-)', ':)', '(:', ';)', '(;', ':o)', ':]', ';]', ':3', ':>', '=]', '8)', '8-)', '=)', ':}',
    ':^)', ':-D', ':D', '))', '8-D', '8D', 'x-D', 'xD', 'X-D', 'XD', '=-D', '=D', '=-3', '=3',
    'B^D', ':-))', ":'-)", ":')", '>:O', ':-O', ':O', '8-0', ':*', ':^*', ';-)', '*-)', '*)', ';-]',
    ';D', ';^)', ':-,' '>:P', ':-P', ':P', ':-p', ':p', '=p', ':-b', ':b', 'O:-)', '0:-3', '0:3',
    '0:-)', '0:)', '0;^)', '>:)', '>;)', '>:-)', '}:-)', '}:)', '3:-)', '3:)', 'o/\\o', '^5',
    '>_>^', '^<_<', '|;-)', '%)', '\\o/', '*\\0/*', '<3', '^_^', '^^', '^ ^', '^.^', '^o^', '^O^',
    '^-^', 'O_O', 'OO', 'o_o', 'oo', '/:-)', ':D<3',
    ]

# Negative smileys
NEGATIVE_EMOTIONS = [
    '>:[', ':-(', ':(', '):', ';(', ':-c', ':c', ':-<', ':<', ':-[', ':[', ':{', '((', ';(', ':-||',
    ':@', '>:(', ":'-(", ":'(", 'D:<', 'D:', 'D8', 'D;', 'D=', 'DX', 'v.v', "D-':", '>:\\', '>:/',
    ':-/', ':-.', ':/', ':\\', '=/', '=\\', ':L', '=L', ':S', '>.<', ':|', ':-|', ':$', '<:-|',
    '</3', '(>_<)', '(^_^;)', '(-_-;)', '(~_~;)', '(=_=)', '(~o~)', '(~_~)', ':C', ':-C', 'O_o',
    'Oo', 'oO', 'o_O', '<_<',
    ]

# ASCII letters
_U = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
_L = 'abcdefghijklmnopqrstuvwxyz'

# Months
_MONTHS = [
    'january', 'jan', 'february', 'feb', 'march', 'mar', 'april', 'apr', 'may',
    'june', 'jun', 'july', 'jul', 'august', 'aug', 'september', 'sep', 'october', 'oct',
    'november', 'nov', 'december', 'dec'
    ]

# Tags
_HEADINGS_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
_COMMENT_TAGS = ['tr', 'li', 'dl']
_LIST_TAGS = ['dl', 'ol', 'menu', 'dd', 'li', 'ul', 'dt']
_FORM_TAGS = [
    'textarea', 'fieldset', 'option', 'form', 'button',
    'label', 'optgroup', 'input', 'legend', 'select',
    ]
_TABLE_TAGS = ['colgroup', 'tr', 'tbody', 'caption', 'tfoot', 'th', 'table','td', 'col', 'thead']
_TEXT_CONTENT_TAGS = [
    'p', 'span', 'b', 'i', 'big', 'tt', 'small', 's', 'u', 'strike', 'strong', 'address', 'cite',
    'blockquote', 'em', 'code', 'acronym', 'kbd', 'ins', 'dfn', 'del', 'abbr', 'strong', 'var',
    ]
_NOT_CONTENT_TAGS = _FORM_TAGS + ['dl', 'dt', 'dd', 'iframe', 'aside', 'table', 'nav']
_CONTENT_BLOCK_TAGS = ['div','article','section']

# Regular expressions
_RE_HEADER_ENCODING = re.compile(r'charset=([\w-]+)', re.I)
_RE_TEMPLATE = r'''%s\s*=\s*["']?\s*%s\s*["']?'''
_RE_HTTPEQUIV = _RE_TEMPLATE % ('http-equiv', 'Content-Type')
_RE_CONTENT = _RE_TEMPLATE % ('content', r'(?P<mime>[^;]+);\s*charset=(?P<charset>[\w-]+)')
_RE_CONTENT2 = _RE_TEMPLATE % ('charset', r'(?P<charset2>[\w-]+)')
_RE_XML_ENCODING = _RE_TEMPLATE % ('encoding', r'(?P<xmlcharset>[\w-]+)')
_RE_BODY_ENCODING_PATTERN = (
    r'<\s*(?:meta(?:(?:\s+%s|\s+%s){2}|\s+%s)|\?xml\s[^>]+%s|body)' %
    (_RE_HTTPEQUIV, _RE_CONTENT, _RE_CONTENT2, _RE_XML_ENCODING)
    )
_RE_BODY_ENCODING_STR = re.compile(_RE_BODY_ENCODING_PATTERN, re.I)
_RE_BODY_ENCODING_BYTES = re.compile(_RE_BODY_ENCODING_PATTERN.encode('ascii'), re.I)
_RE_DIGIT = re.compile(r'\d')
_RE_2DIGITS = re.compile(r'(\d){2,}')
_RE_2CHR = re.compile(r'[a-zA-Z]{2,}')
_RE_DOMAIN = re.compile(r'[\w-]{4,}')
_RE_PAGE_NUM = r'\D%s(?!\d)'
_RE_YEAR = re.compile(r'^201\d$')
_RE_ENTITY = re.compile(r'(&[a-z]+;)')
_RE_NUM_ENTITY = re.compile(r'(&#\d+;)')
_RE_NS = {'re': 'http://exslt.org/regular-expressions'}

# XPath expressions
_xp_tags = lambda tags: ' or '.join(['self::%s' % _ for _ in tags])
_xp_names = lambda names: ' or '.join(['name()="%s"' % _ for _ in names])
_xp_translate = lambda obj: 'translate({},"{}","{}")'.format(obj, _U, _L)
_xp_images = ' or '.join(['contains(@src, ".%s")' % _ for _ in _IMAGE_FORMATS])
_XPATH_TEXT_BLOCKS = XPath('.//text()')
_XPATH_LANG = XPath('@lang', smart_strings=False)
_XPATH_META_LANG1 = XPath('.//meta[@http-equiv="content-language"]/@content', smart_strings=False)
_XPATH_META_LANG2 = XPath('.//meta[@name="lang"]/@content', smart_strings=False)
_XPATH_META_AUTHOR = XPath('.//meta[@name="author"]/@content', smart_strings=False)
_XPATH_META_DESCRIPTION = XPath('.//meta[@name="description"]/@content', smart_strings=False)
_XPATH_META_KEYWORDS = XPath('.//meta[@name="keywords"]/@content', smart_strings=False)
_XPATH_META_OG_TITLE = XPath('.//meta[@property="og:title"]/@content', smart_strings=False)
_XPATH_META_OG_TYPE = XPath('.//meta[@property="og:type"]/@content', smart_strings=False)
_XPATH_META_OG_DESCRIPTION = XPath(
    './/meta[@property="og:description"]/@content', smart_strings=False
    )
_XPATH_HEAD_TITLE = XPath('.//title/text()', smart_strings=False)
_XPATH_TIME_TAG = XPath('.//time')
_XPATH_DATE_ATTR = XPath(
    './/*[@*[contains({},"date") and not({})]]'
    .format(_xp_translate('.'), _xp_names(['src','href']))
    )
_XPATH_PUBLISHED_ATTR = XPath(
    './/*[@*[contains({},"published") and not({})]]'
    .format(_xp_translate('.'), _xp_names(['src','href']))
    )
_XPATH_DATE_IN_ANCHOR = XPath(
    './/a[re:test(@title,"\d{2,}") and re:test(text(),"\d")]',
    namespaces=_RE_NS
    )
_XPATH_DATE_CANDIDATES = XPath(
    './/*[re:test(text(),"\d{2,}") and string-length(text())>4]',
    namespaces=_RE_NS
    )
_XPATH_AUTHOR_ATTR = XPath(
    ('.//*[@*[(contains({},"author") or contains({},"name") or contains({},"contributor") or '
    'contains({},"user")) and not({})] and not(self::img)]')
    .format(
        _xp_translate('.'), _xp_translate('.'), _xp_translate('.'), _xp_translate('.'),
        _xp_names(['src'])
        )
    )
_XPATH_ARTICLE_TAG = XPath('.//article')
_XPATH_CONTENT_BLOCKS = XPath('.//div[contains({},"content")]'.format(_xp_translate('@class')))
_XPATH_HEADER_TAG = XPath('.//header')
_XPATH_HEADINGS_TAGS = XPath('.//*[({}) and not(ancestor::aside)]'.format(_xp_tags(_HEADINGS_TAGS)))
_XPATH_COMMENT_META_AUTHOR = XPath(
    './/div[contains(@class, "meta")]//a[@href and string-length(text())>2]'
    )
_XPATH_COMMENT_REPLY = XPath('.//*[{}="reply"]'.format(_xp_translate('text()')))
_XPATH_COMMENT_BODY = XPath('.//*[contains({},"body")]'.format(_xp_translate('@class')))
_XPATH_COMMENT_GARBAGE = XPath(
    './/*[{}="reply" or {}="like" or {}="share" or {}="quote"]'
    .format(
        _xp_translate('text()'), _xp_translate('text()'),
        _xp_translate('text()'), _xp_translate('text()')
        )
    )
_XPATH_COMMENT_CONTENT_NODES = XPath('.//*[self::div or self::p]')
# _XPATH_COMMENT_DATE = XPath(
#     './/*[@*[contains({},"ago") and not({})]]'
#    .format(_xp_translate('.'), _xp_names(['src','href']))
#    )
_XPATH_COMMENT_ID_ALL = XPath(
    './/*[(contains({},"comment") or contains({},"comment")) and re:test(@id,"{}") and ({})]'
    .format(_xp_translate('@id'), _xp_translate('@class'), "\d{3,}", _xp_tags(_COMMENT_TAGS)),
    namespaces=_RE_NS
    )
_XPATH_COMMENT_ID_DIV = XPath(
    './/div[(contains({},"comment") or contains({},"comment")) and re:test(@id,"{}")]'
    .format(_xp_translate('@id'), _xp_translate('@class'), "\d{3,}"),
    namespaces=_RE_NS
    )
_XPATH_COMMENT_ATTR = XPath(
    './/div[@*[contains({},"comment") or {}="replies"]]'
    .format(_xp_translate('.'), _xp_translate('.'))
    )
_XPATH_NAV_TAG = XPath('.//nav')
_XPATH_NAV_BY_DATE = (
    ('%s//a[re:test(@href,"{}") and contains(@href,"?") and '
    'contains(@href, "%s") and (@*[contains({},"old")] or '
    '@*[contains({},"next")] or contains({},"older"))]')
    .format("\d{2,}", _xp_translate('.'), _xp_translate('.'), _xp_translate('text()'))
    )
_XPATH_NAV_PAGINATION = (
    '%s//a[re:test(text(),"^\d+$") and contains(@href, "%s") and contains(@href, text())]'
    .format(_xp_translate('.'))
    )
_XPATH_NAV_PAGINATION_CURRENT = ('%s//*[not(self::a) and text()="%s"]')
_XPATH_NAV_NEXT_PREV_PAGE = (
    ('%s//*[@*[contains({},"next") and not({})] and contains({},"next")]')
    .format(_xp_translate('.'), _xp_names(['src','href']), _xp_translate('text()'))
    )
_XPATH_NAV_PAGE = (
    '%s//a[contains(@href, "%s") and re:test(@href,"(index|(page(s|d)?))(\?|/|-|=)?%s(?!\d)")]'
    )
# _XPATH_IMAGES = XPath('.//img[({}) and not(ancestor::aside)]'.format(_xp_images))
_XPATH_IMAGES = XPath(
    './/img[not(ancestor::aside or contains({}, ".gif"))]'.format(_xp_translate('@src'))
    )
_XPATH_NOT_DIV_TEXT = XPath('.//*[not(self::div)]/text()')
_XPATH_DIV = XPath('.//div')
_XPATH_ANCHOR = XPath('.//a[@href]')
_XPATH_INTERNAL_ANCHOR = './/a[contains(@href,"%s")]'
_XPATH_ANCHOR_ANCESTOR = XPath('.//ancestor::a[@href]')
_XPATH_INTERNAL_ANCHOR_ANCESTOR = './/ancestor::a[contains(@href,"%s")]'
_XPATH_POSSIBLE_CONTENT_NODES = lambda tags: XPath(
    './/*[({}) and not(ancestor::aside or ancestor::nav)]'.format(_xp_tags(tags))
    )
_XPATH_NOT_CONTENT_NODES = XPath(
    './/*[@*[contains({},"sidebar") or contains({},"widget") or contains({},"slider") or '
    'contains({},"navbar") or contains({},"menu") or contains({},"popup") or '
    'contains({},"related") or contains({},"thumbies")] or ({})]'
    .format(
        _xp_translate('.'), _xp_translate('.'), _xp_translate('.'), _xp_translate('.'),
        _xp_translate('.'), _xp_translate('.'), _xp_translate('.'), _xp_translate('.'),
        _xp_tags(_NOT_CONTENT_TAGS)
        )
    )
_XPATH_RELATED = XPath('.//*[@*[contains({},"related")]]'.format(_xp_translate('.')))
_XPATH_SIDEBAR_DIV = XPath('.//div[{}="sidebar"]'.format(_xp_translate('@id')))
_XPATH_ENTRY_CHILD = XPath(
    './/ancestor::div[@*[contains({},"entry") and not(contains({},"related"))]]'
    .format(_xp_translate('.'), _xp_translate('.'))
    )
_XPATH_SIDEBAR_CHILD = XPath('.//ancestor::div[@*[contains({},"sidebar")]]'.format(_xp_translate('.')))

# BOM (byte order mark)
_BOM_TABLE = [
    (codecs.BOM_UTF32_BE, 'utf-32-be'),
    (codecs.BOM_UTF32_LE, 'utf-32-le'),
    (codecs.BOM_UTF16_BE, 'utf-16-be'),
    (codecs.BOM_UTF16_LE, 'utf-16-le'),
    (codecs.BOM_UTF8, 'utf-8'),
]

# Default encoding translation
_DEFAULT_ENCODING_TRANSLATION = {
    'ascii': 'cp1252',
    'euc_kr': 'cp949',
    'gb2312': 'gb18030',
    'gb_2312_80': 'gb18030',
    'gbk': 'gb18030',
    'iso8859_11': 'cp874',
    'iso8859_9': 'cp1254',
    'latin_1': 'cp1252',
    'macintosh': 'mac_roman',
    'shift_jis': 'cp932',
    'tis_620': 'cp874',
    'win_1251': 'cp1251',
    'windows_31j': 'cp932',
    'win_31j': 'cp932',
    'windows_874': 'cp874',
    'win_874': 'cp874',
    'x_sjis': 'cp932',
    'zh_cn': 'gb18030',
}

# The encoding error handling scheme
codecs.register_error('enc_xtractor_replace', lambda exc: (u'\ufffd', exc.start + 1))

# API endpoints
_TWITTER_API_ENDPOINT = 'http://urls.api.twitter.com/1/urls/count.json?url='
_FACEBOOK_API_ENDPOINT = 'http://api.facebook.com/restserver.php?method=links.getStats&urls='

# webxtractor directory
_DIR = os.path.dirname(os.path.abspath(__file__))


####################################################################################################


def readlines(filename, directory=None, encoding='utf-8'):
    """Read lines from file and return a list of non-empty lines.

    :param filename: the file name
    :param directory: the directory that contains a file
    :param encoding: the file encoding

    """
    if directory is not None:
        filename = os.path.join(directory, filename)
    if not directory.startswith('/'):
        path = os.path.join(_DIR, filename)
    with codecs.open(path, encoding=encoding) as f:
        lines = [line.strip() for line in f]
    return filter(None, lines)


####################################################################################################


# Stop-words
_STOPWORDS_EN = readlines('stopwords-en.txt', 'text_data')
_STOPWORDS_ES = readlines('stopwords-es.txt', 'text_data')
_STOPWORDS_FR = readlines('stopwords-fr.txt', 'text_data')
_STOPWORDS_IT = readlines('stopwords-it.txt', 'text_data')
_STOPWORDS_RU = readlines('stopwords-ru.txt', 'text_data')
_STOPWORDS = {
    'en': _STOPWORDS_EN,
    'es': _STOPWORDS_ES,
    'fr': _STOPWORDS_FR,
    'it': _STOPWORDS_IT,
    'ru': _STOPWORDS_RU,
}


####################################################################################################


__all__ = ['USER_AGENT']

def public(obj):
    """The decorator that adds class/function to the public API."""
    all = sys.modules[obj.__module__].__dict__.setdefault('__all__', [])
    if obj.__name__ not in all:
        all.append(obj.__name__)
    return obj


####################################################################################################


def safe_wrapper(func):
    """The safe wrapper for those methods, that can raise expected exceptions.
    Return ``None`` if something goes wrong.
    """
    def wrapper(*arg, **kw):
        try:
            return func(*arg, **kw)
        except WebXtractorError as e:
            xLogger.warning(str(e))
            return None
    return wrapper


####################################################################################################


@public
class WebXtractorError(Exception):
    """webxtractor::WebXtractorError

    All exceptions in this module are instances of this class.

    """


####################################################################################################


# TODO: meta; __doc__
class BaseContainer(object):
    """webxtractor::BaseContainer

    :method json: Serialize the container to a JSON string and return it,
    otherwise return ``None`` if body is not serializable

    """
    def __str__(self):
        return self.json()

    def json(self):
        try:
            return json.dumps(
                self.__dict__,
                default=lambda obj: obj.__dict__ if hasattr(obj, '__dict__') else str(obj)
                )
        except TypeError:
            return None


class CommentContainer(BaseContainer):
    """webxtractor::BaseContainer::CommentContainer

    :param publish_date: the comment publish date
    :param text: the comment text
    :param html: the HTML code of the comment content
    :param author_name: the comment author name
    :param author_url: the comment author URL
    :param like_count: the number of "likes"
    :param share_count: the number of "shares"
    :param replies: a list of replies (``CommentContainer`` instances)
    :param url: the comment URL

    """
    def __init__(self,
        publish_date=None,
        text=None,
        html=None,
        author_name=None,
        author_url=None,
        like_count=None,
        share_count=None,
        replies=None,
        url=None,
        ):
        self.publish_date = publish_date
        self.text = text
        self.html = html
        self.author_name = author_name
        self.author_url = author_url
        self.like_count = like_count
        self.share_count = share_count
        self.replies = replies if replies is not None else []
        self.url = url


class ImageContainer(BaseContainer):
    """webxtractor::BaseContainer::ImageContainer

    :param url: the image URL
    :param name: the image file name (with an extension)
    :param format: the image format ('jpeg', 'png', 'gif')
    :param width: the real width of the image (in pixels)
    :param height: the real height of the image (in pixels)
    :param alt: an alternate text for the image ('@alt' attribute)

    """
    def __init__(self,
        url=None,
        name=None,
        format=None,
        width=None,
        height=None,
        alt=None,
        ):
        self.url = url
        self.name = name
        self.format = format
        self.width = width
        self.height = height
        self.alt = alt


class VideoContainer(BaseContainer):
    """webxtractor::BaseContainer::VideoContainer"""


@public
class BlogContainer(BaseContainer):
    """webxtractor::BaseContainer::BlogContainer

    :param posts: a list of all posts on the page (``PostContainer`` instances)
    :param current_page_url: the current page URL
    :param current_page_number: the current page number
    :param next_page_url: the next page URL (if found, else ``None``)
    :param charset: the encoding
    :param debug_info: the useful debug information

    """
    def __init__(self,
        name=None,
        posts=None,
        current_page_url=None,
        current_page_number=None,
        next_page_url=None,
        charset=None,
        debug_info=None,
        ):
        self.posts = posts if posts is not None else []
        self.current_page_url = current_page_url
        self.current_page_number= current_page_number
        self.next_page_url = next_page_url
        self.charset = charset
        self.debug_info = debug_info


class PostContainer(BaseContainer):
    """webxtractor::BaseContainer::PostContainer

    :param meta_description: <meta> description
    :param meta_keywords: <meta> keywords (a list)
    :param meta_author: <meta> author name
    :param meta_og_type: <meta> Open Graph type
    :param meta_og_title: <meta> Open Graph title
    :param meta_og_description: <meta> Open Graph description
    :param lang: the page language
    :param head_title: the <head><title>[...]</title></head> content
    :param title: the post title (the most appropriate result)
    :param publish_date: the post publish date
    :param text: the post text
    :param html: the HTML code of the post body
    :param author_name: the post author name
    :param author_url: the post author URL
    :param comments: a list of comments (`CommentContainer` instances)
    :param images: a list of images (`ImageContainer` instances)
    :param videos: a list of videos (`VideoContainer` instances)
    :param tags: a dict of tags `{"tag1_name": "tag1_url", "tag2_name": "tag2_url", etc.}`
    :param social_metrics: a dict of social metrics `{"facebook": ..., "twitter": ...}`
    :param url: the post URL
    :param charset: the post encoding
    :param debug_info: the useful debug information

    """
    def __init__(self,
        meta_description=None,
        meta_keywords=None,
        meta_author=None,
        meta_og_type=None,
        meta_og_title=None,
        meta_og_description=None,
        lang=None,
        head_title=None,
        title=None,
        publish_date=None,
        text=None,
        html=None,
        author_name=None,
        author_url=None,
        comments=None,
        images=None,
        videos=None,
        tags=None,
        social_metrics=None,
        url=None,
        charset=None,
        debug_info=None,
        ):
        self.meta_description = meta_description
        self.meta_keywords = meta_keywords
        self.meta_author = meta_author
        self.meta_og_type = meta_og_type
        self.meta_og_title = meta_og_title
        self.meta_og_description = meta_og_description
        self.lang = lang
        self.head_title = head_title
        self.title = title
        self.publish_date = publish_date
        self.text = text
        self.html = html
        self.author_name = author_name
        self.author_url = author_url
        self.comments = comments if comments is not None else []
        self.images = images if images is not None else []
        self.videos = videos if videos is not None else []
        self.tags = tags if tags is not None else {}
        self.social_metrics = social_metrics
        self.url = url
        self.charset = charset
        self.debug_info = debug_info


class CacheContainer(object):
    """webxtractor::CacheContainer"""
    def __init__(self, data=None):
        self.data = data


####################################################################################################


# TODO: meta; __doc__
@public
class BaseXtractor(object):
    """webxtractor::BaseXtractor

    :param network_caching: Enable/disable the network caching system
    :method extract: Extract the content from the HTML document or from the URL

    """
    def __init__(self, network_caching=False):

        self.network_caching = network_caching
        # The network cache with URL binding `{"url": ("response_body", {http_headers}), etc.}`
        self._network_cache = CacheContainer({})

        # A place for the extracted content (the independent copy)
        self.content = None

        self._default_date = None
        self.lang = None

        # The HTML Cleaner
        self._html_cleaner = Cleaner(
            # remove any <script> tags
            scripts=True,
            # remove any Javascript, like an ``onclick`` attribute
            javascript=False,
            # remove any comments
            comments=True,
            # remove any style tags or attributes
            style=True,
            # remove any <link> tags
            links=True,
            # remove any <meta> tags
            meta=False,
            # remove structural parts of a page: <head>, <html>, <title>
            page_structure=False,
            # remove any processing instructions
            processing_instructions=False,
            # remove any embedded objects (flash, iframes)
            embedded=False,
            # remove any frame-related tags
            frames=False,
            # remove any form tags
            forms=False,
            # remove <blink> and <marquee>
            annoying_tags=False,
            # remove any tags that aren't standard parts of HTML
            remove_unknown_tags=False,
            # if true, only include 'safe' attributes
            safe_attrs_only=False,
            # if true, then any <a> tags will have ``rel="nofollow"`` added to them
            add_nofollow=False,
            # a list of the allowed hosts for embedded content
            host_whitelist=(),
            )


    def extract(self):
        """Extract the content from the HTML document or from the URL"""


    def _parse_head(self, head_elem, container):
        """Parse the <head> element of the HTML document.

        :param head_elem: the <head> element (`lxml::html::HtmlElement`)
        :param container: the container that is used to save the results

        """
        # meta: description
        container.meta_description = self._xpath(head_elem, _XPATH_META_DESCRIPTION)
        # meta: keywords
        meta_keywords = self._xpath(head_elem, _XPATH_META_KEYWORDS)
        if meta_keywords:
            container.meta_keywords = [e.strip() for e in meta_keywords.split(',')]
        # meta: author
        container.meta_author = self._xpath(head_elem, _XPATH_META_AUTHOR)
        # meta: Open Graph Type
        container.meta_og_type = self._xpath(head_elem, _XPATH_META_OG_TYPE)
        # meta: Open Graph Title
        container.meta_og_title = self._xpath(head_elem, _XPATH_META_OG_TITLE)
        # meta: Open Graph Description
        container.meta_og_description = self._xpath(head_elem, _XPATH_META_OG_DESCRIPTION)
        # the <head><title>...</title></head> content
        head_titles = _XPATH_HEAD_TITLE(head_elem)
        if head_titles:
            # sometimes web-masters by mistake put a few <title> tags in the <head>
            # let's process this case
            if len(head_titles) > 1:
                head_title = max(head_titles, key=lambda k: len(k)).strip()
            else:
                head_title = head_titles[0].strip()
            # parse the title
            container.head_title = self._parse_title(head_title, container.meta_og_title)
        # The page language
        container.lang = self._xpath(head_elem, _XPATH_LANG)
        if not container.lang:
            container.lang = self._xpath(head_elem, _XPATH_META_LANG1)
            if not container.lang:
                container.lang = self._xpath(head_elem, _XPATH_META_LANG2)
        # TODO: parse language
        self.lang = container.lang


    def _parse_title(self, title, pattern):
        """Parse the raw title and try to extract the real title text.
        Can handle such titles: "TITLE | BLOG", "BLOG: TITLE" etc.
        Return the best title possible.

        :param title: the full title text (string)
        :param pattern: a pattern of the title (string), for example extracted from the <meta>

        """
        if pattern is None: return title
        if pattern.lower() in title.lower(): return pattern
        canditates = set()
        for delimiter in _TITLE_DELIMITERS:
            title_parts = title.split(delimiter)
            if len(title_parts) > 1:
                for part in title_parts:
                    canditates.add(part.strip())
        if not canditates: return title
        return max(
            map(
                lambda c: (self._compare_strings(c.lower(), pattern.lower()), c),
                canditates
                ),
            key=lambda k: (k[0], len(k[1]))
        )[1]


    def _get_content_node(self, html_document, images=None, content_block_tags=_CONTENT_BLOCK_TAGS):
        """Find and return the content node (`lxml::html::HtmlElement`) and its images/videos.

        :param html_document: the HTML document (lxml Element `html`)
        :param images: a list of big images on the page (`lxml::html::HtmlElement` instances)
        :param content_block_tags: tags that are used for the content structuring on the web-page

        """
        images = images if images is not None else []
        content_images = []
        content_winner = None
        content_candidates = []
        content_nodes = []
        not_content_nodes = set(_XPATH_NOT_CONTENT_NODES(html_document))
        possible_content_nodes = set(
            _XPATH_POSSIBLE_CONTENT_NODES(content_block_tags)(html_document)
            ).difference(not_content_nodes)
        for node in possible_content_nodes:
            related_posts = _XPATH_RELATED(node)
            for post in related_posts:
                if post.getparent() is not None:
                    post.drop_tree()
            score, node_images = self._rate_content_node(
                node,
                images,
                content_block_tags,
                not_content_nodes
                )
            if _XPATH_ENTRY_CHILD(node) and score > 175:
                score += 100
            # if score > 100:
            #     print node.tag, node.attrib, score
            if score > 500:
                content_nodes.append(node)
                content_images.extend(node_images)
            elif score > 275:
                content_candidates.append((node, score, node_images))
        if content_candidates:
            max_score = max(content_candidates, key=lambda k: k[1])[1]
            too_close_candidates = filter(
                lambda c: c[1] > (max_score * 0.85),
                content_candidates
                )
            content_winner = self._get_parent_node(
                html_document, [c[0] for c in too_close_candidates]
                )
            content_images.extend(itertools.chain(*[c[2] for c in too_close_candidates]))
        if content_nodes:
            if content_winner is not None:
                content_nodes.append(content_winner)
            content_winner = self._get_parent_node(html_document, content_nodes)
        return content_winner, content_images


    def _rate_content_node(self, node, images, stop_tags, not_content_nodes):
        """Rate the given content node.
        The more it's similar to the post body, the higher the score.
        Based on stochastic text models, commonly used patterns and the links density.
        Return the total score for the given node and its images/videos.

        :param node: the top-level node for crawler (`lxml::html::HtmlElement` instance)
        :param images: a list of big images on the page (`lxml::html::HtmlElement` instances)
        :param stop_tags: a list of tags that have to be processed and rated separately (or ignore)
        :param not_content_nodes: a list of nodes that do not contain the post content

        """
        score = 0.0
        node_images = []
        if len(images) == 1:
            image_score = 450
        else:
            image_score = 200
        text_blocks = self._get_text_blocks(node)
        link_density = self._get_link_density(node, stop_tags)
        # links = 0
        queue_tree = deque(node)
        while queue_tree:
            node = queue_tree.popleft()
            if node.tag in stop_tags:
                continue
            elif node.tag in _FORM_TAGS:
                score -= 50
                continue
            elif node.tag in _LIST_TAGS:
                score -= 15
            # elif node.tag == 'a':
            #     links += 1
            elif node in images:
                node_images.append(node)
                score += image_score
            elif node.tag in _TEXT_CONTENT_TAGS:
                text_blocks.extend(self._get_text_blocks(node))
            score -= len(node) ** 0.5
            queue_tree.extend(
                filter(lambda n: n not in not_content_nodes, node)
                )
        if text_blocks:
            score += self._rate_text(text_blocks)
        if link_density > 0.15:
            score *= 1.15 - (link_density / (len(node_images) + 1))
        return score, node_images


    def _rate_text(self, text, lang='en', punctuation='!,-.:;?'):
        """Rate the text content and return the score.

        :param text: the text content given as a string, list, set or tuple
        :param lang: the language of the text

        """
        if isinstance(text, basestring):
            text = [text]
        elif not isinstance(text, (list,set,tuple)):
            raise WebXtractorError(
                "Argument `text` has to be given as a string, list, set or tuple."
                )
        if lang in _STOPWORDS:
            stopwords = _STOPWORDS[lang]
        else:
            stopwords = []
        text_atoms = []
        for text_block in text:
            text_block = self._remove_newline_chars(text_block)
            text_atoms.extend(
                [atom.strip() for atom in text_block.split()]
                )
        text_atoms = filter(lambda a: len(a) > 1 and _RE_2CHR.search(a), text_atoms)
        text_atoms_number = len(text_atoms)
        if not text_atoms_number: return 0
        score = 0.0
        total_len = 0
        for atom in text_atoms:
            if atom[-1] in punctuation:
                score += 2
                atom = atom.rstrip(atom[-1])
            if atom.isalpha():
                score += 1
                if atom.istitle():
                    score += 1
                if atom.lower() in stopwords:
                    score += 2
                total_len += len(atom)
        score *= (len(set(text_atoms)) / float(text_atoms_number)) ** 0.5
        score *= (total_len / float(text_atoms_number)) ** 0.1
        if text_atoms_number > 75:
            score **= 1.5
        elif text_atoms_number > 60:
            score **= 1.4
        return score


    @staticmethod
    def _get_link_density(node, stop_tags):
        """Return link density of the node.

        :param node: the node given as a `lxml::html::HtmlElement` instance
        :param stop_tags: a list of tags that have to be skipped

        """
        node = copy.deepcopy(node)
        for stop_node in node.xpath('.//*[{}]'.format(_xp_tags(stop_tags))):
            stop_node.drop_tree()
        node_text_len = len(node.text_content().strip())
        if not node_text_len: return 0
        anchors_text_len = sum(
            [len(anchor.text_content().strip()) for anchor in _XPATH_ANCHOR(node)]
            )
        return anchors_text_len / float(node_text_len)


    @staticmethod
    def _get_text_blocks(node):
        """Return a list of text blocks of the node.

        :param node: the node given as a `lxml::html::HtmlElement` instance

        """
        text_blocks = [child.tail.strip() for child in node if child.tail]
        if node.text: text_blocks.insert(0, node.text.strip())
        return filter(None, text_blocks)


    def _extract_images(self, html_document):
        """Extract images from the page, that satisfy these conditions:

        (1) The minimum actual image size:
        * width: `_MIN_IMAGE_WIDTH`
        * height: `_MIN_IMAGE_HEIGHT`

        (2) Image formats: `_IMAGE_FORMATS`

        Return a list of images [(`lxml::html::HtmlElement` node, `ImageContainer` instance), etc.]

        :param html_document: the HTML document (lxml Element `html`)

        """
        big_images = []
        queue = Queue()
        images = _XPATH_IMAGES(html_document)
        images_src = set()
        threads = []
        for img in images:
            img_src = img.get('src')
            if not img_src: continue
            if 'http' in img_src and img_src not in images_src:
                images_src.add(img_src)
                thread = threading.Thread(target=self._process_image, args=(queue, img))
                thread.start()
                threads.append(thread)
        for thread in threads:
            thread.join()
        while not queue.empty():
            img, img_size = queue.get_nowait()
            img_src = img.get('src')
            img_name = img_src.split('/')[-1]
            img_format = img_name.split('.')[-1]
            if img_format == 'jpg': img_format = 'jpeg'
            img_alt = img.get('alt')
            img_width, img_height = img_size
            big_images.append(
                (
                    img,
                    ImageContainer(
                        url=img_src,
                        name=img_name,
                        format=img_format,
                        width=img_width,
                        height=img_height,
                        alt=img.get('alt')
                    )
                )
            )
        return big_images


    def _process_image(self, queue, img):
        """Image processing in multithreading mode.

        :param queue: the queue (`Queue::Queue`)
        :param img: the image node (`lxml::html::HtmlElement`)

        """
        image_size = self._get_image_size_from_url(img.get('src'))
        if image_size:
            img_width, img_height = image_size
            if (img_width > _MIN_IMAGE_WIDTH and
                img_height > _MIN_IMAGE_HEIGHT):
                queue.put((img, image_size))


    def _get_clean_html(self, html=None, url=None, encoding=None, http_headers=None):
        """Download the HTML document (if `url` is provided and `html` is not).
        Detect the HTML document charset and clean it for the subsequent data extraction.
        Return a tuple ``(clean_html_unicode, encoding)``

        :param html: the HTML document given as a string or unicode
        :param url: the web-page URL
        :param encoding: the encoding
        :param http_headers: HTTP headers given as a dict

        """
        if encoding:
            encoding = self._resolve_encoding(encoding)

        if isinstance(http_headers, dict):
            http_headers = dict(map(lambda i: (i[0].lower(), i[1]), http_headers.items()))
        elif http_headers is not None:
            raise WebXtractorError("HTTP headers have to be given as a dict.")

        if not html and url:
            html, http_headers = self._get(url)
        elif html:
            if isinstance(html, str):
                if not http_headers and not encoding and url:
                    _, http_headers = self._get(url, only_headers=True)
            elif not isinstance(html, unicode):
                raise WebXtractorError("The HTML document has to be given as a string or unicode.")
        else:
            raise WebXtractorError("No HTML document or URL provided.")

        if not isinstance(html, unicode) and not encoding:
            encoding = self._detect_charset(html, http_headers.get('content-type'))
            try:
                html = html.decode(encoding)
            except UnicodeDecodeError:
                try:
                    html = html.decode('utf-8')
                except UnicodeDecodeError:
                    xLogger.error('Cannot decode the HTML page. URL: {}'.format(url))
            #html = self._decode_entities(html)
        elif isinstance(html, unicode) and not encoding:
            encoding = 'utf-8'
        # elif isinstance(html, unicode):
        #     if encoding:
        #         html = html.encode(encoding)
        #     else:
        #         try:
        #             html = html.encode('utf-8')
        #             encoding = 'utf-8'
        #         except UnicodeEncodeError:
        #             raise WebXtractorError("'utf-8' codec can't encode the HTML document.")

        # html = self._remove_newline_chars(html)
        html = html.replace('\t',' ')
        # is it a good idea to replace the non breaking space (&nbsp;)?
        # well, it makes the result more clean
        html = html.replace('&nbsp;', ' ')
        html = self._html_cleaner.clean_html(html)

        return html, encoding


    # TODO: process http_redirect
    def _get(self, url, cache=False, only_headers=False):
        """Send the HTTP GET request and return the response body and HTTP headers.
        Cache the last request (more precisely the response body) if ``network_caching`` is enabled.
        If ``cache`` == ``True`` and the response body for the given URL can be found
        in ``_network_cache``, then return the response body from ``_network_cache``,
        otherwise make the new request.

        :param url: the web-resource URL
        :param cache: enable/disable interacting with ``_network_cache``
        :param only_headers: read only HTTP headers and return `(None, HTTP_headers)`

        """
        if cache and self.network_caching and self._network_cache.data.get(url):
            return self._network_cache.data[url]
        request = urllib2.Request(url)
        request.add_header('User-agent', USER_AGENT)
        try:
            response = urllib2.urlopen(request, timeout=60)
        except Exception as e:
            raise WebXtractorError(
                "The connection with the web-resource cannot be established. URL: {}. {}."
                .format(url, str(e))
                )
        if response.getcode() != 200:
            raise WebXtractorError(
                "The server returns [{}] HTTP status code. URL: {}."
                .format(response.getcode(), url)
                )
        headers = response.headers.dict
        if not only_headers:
            try:
                response_body = response.read()
            except Exception as e:
                raise WebXtractorError(
                    "Cannot read the response. URL: {}."
                    .format(url, str(e))
                    )
        else:
            response_body = None
        if self.network_caching:
            self._network_cache.data[url] = (response_body, headers)
        return response_body, headers


    @safe_wrapper
    def _get_twitter_metrics(self, page_url):
        """Get the web-page metrics from the Twitter API.
        Return a dict with the ``share_count`` key.

        :param page_url: the web-page URL

        """
        url = _TWITTER_API_ENDPOINT + page_url
        try:
            response_body, _ = self._get(url)
            jsondoc = json.loads(response_body)
            return {'share_count': int(jsondoc['count'])}
        except Exception as e:
            raise WebXtractorError(
                "Can't get social metrics from the Twitter API. {}".format(str(e))
                )


    @safe_wrapper
    def _get_facebook_metrics(self, page_url):
        """Get the web-page metrics from the Facebook API.
        Return a dict with `share_count`, `like_count` and `comment_count` keys.

        :param page_url: the web-page URL

        """
        url = _FACEBOOK_API_ENDPOINT + page_url
        try:
            response_body, _ = self._get(url)
            tree = etree.fromstring(response_body)
            xmlns = tree.nsmap.get(None)
            ns = '{%s}' % xmlns if xmlns else ''
            fb_metrics = {}
            fb_metrics['share_count'] = tree.find('.//{}share_count'.format(ns))
            fb_metrics['like_count'] = tree.find('.//{}like_count'.format(ns))
            fb_metrics['comment_count'] = tree.find('.//{}comment_count'.format(ns))
            for m, v in fb_metrics.items():
                if v.text.isdigit():
                    fb_metrics[m] = int(v.text)
            return fb_metrics
        except Exception as e:
            raise WebXtractorError(
                "Can't get social metrics from the Facebook API. {}".format(str(e))
                )


    @safe_wrapper
    def _get_image_size_from_url(self, img_url):
        """Retrieve the image size from the image URL.
        Download only the first bytes necessary to get the size.
        Supported image formats: GIF, JPEG and PNG.
        Return the image size in the tuple ``(width, height)``.

        :param img_url: the image URL

        """
        width, height = None, None
        request = urllib2.Request(img_url)
        request.add_header('User-agent', USER_AGENT)
        try:
            img = urllib2.urlopen(request)
        except Exception as e:
            raise WebXtractorError(
                "The connection cannot be established. The Image URL: {}. {}"
                .format(img_url, str(e))
                )

        if img.getcode() != 200: # or img.geturl() != img_url:
            raise WebXtractorError(
                "The server returns [{}] HTTP status code. The Image URL: {}"
                .format(img.getcode(), img_url)
                )

        content_length = img.headers.get('content-length')
        if content_length and content_length.isdigit():
            img_size = int(content_length)
            if img_size < 150:
                raise WebXtractorError(
                    "The image size is less than 150 bytes. The Image URL: {}".format(img_url)
                    )
        else:
            raise WebXtractorError(
                "Cannot retrieve the 'Content-Length' HTTP header. The Image URL: {}"
                .format(img_url)
                )

        content_type = img.headers.get('content-type')
        if not content_type:
            raise WebXtractorError(
                "No 'Content-Type' HTTP header: {}. The Image URL: {}"
                .format(content_type, img_url)
                )
        if 'image/gif' in content_type:
            img_format = 'gif'
        elif 'image/jpeg' in content_type:
            img_format = 'jpeg'
        elif 'image/png' in content_type:
            img_format = 'png'
        else:
            raise WebXtractorError(
                "The unsupported 'Content-Type' HTTP header: {}. The Image URL: {}"
                .format(content_type, img_url)
                )

        if img_format == 'jpeg':
            img_data = img.read(2)
        else:
            img_data = img.read(25)

        try:
            # GIF
            if img_format == 'gif' and img_data[:6] in ('GIF87a', 'GIF89a'):
                width, height = [int(e) for e in struct.unpack('<HH', img_data[6:10])]
            # PNG
            elif img_format == 'png' and img_data.startswith('\211PNG\r\n\032\n'):
                if img_data[12:16] == 'IHDR':
                    width, height = [int(e) for e in struct.unpack('>LL', img_data[16:24])]
                else:
                    width, height = [int(e) for e in struct.unpack('>LL', img_data[8:16])]
            # JPEG
            elif img_data.startswith('\377\330'):
                byte = img.read(1)
                while byte and ord(byte) != 0xDA:
                    while ord(byte) != 0xFF: byte = img.read(1)
                    while ord(byte) == 0xFF: byte = img.read(1)
                    if ord(byte) >= 0xC0 and ord(byte) <= 0xC3:
                        height, width = [int(e) for e in struct.unpack(">HH", img.read(7)[-4:])]
                        break
                    else:
                        img.read(int(struct.unpack(">H", img.read(2))[0])-2)
                    byte = img.read(1)
            else:
                raise WebXtractorError(
                    "The unknown type of the image. The Image URL: {}".format(img_url)
                    )
        except Exception:
            raise WebXtractorError(
                "Cannot extract the image size from the image body. The Image URL: {}"
                .format(img_url)
                )

        if width and height: return width, height


    def _detect_charset(self, html, content_type_header=None):
        """Return the HTML document charset.

        Try to detect the encoding from:
        1 - HTTP 'Content-Type' header
        2 - BOM (byte-order mark)
        3 - meta or xml tag declarations

        :param html: the HTML document given as a string
        :param content_type_header: HTTP 'Content-Type' header given as a string

        """
        charset = None
        if content_type_header:
            match = _RE_HEADER_ENCODING.search(content_type_header)
            if match:
                charset = self._resolve_encoding(match.group(1))
        bom_enc, bom = None, None
        for _bom, _enc in _BOM_TABLE:
            if html.startswith(_bom):
                bom_enc, bom = _enc, _bom
                break
        if charset is not None:
            if charset == 'utf-16' or charset == 'utf-32':
                if bom_enc is not None and bom_enc.startswith(charset):
                    charset = bom_enc
                else:
                    charset += '-be'
            return charset
        if bom_enc is not None:
            return bom_enc

        chunk = html[:4096]
        if isinstance(chunk, bytes):
            match = _RE_BODY_ENCODING_BYTES.search(chunk)
        else:
            match = _RE_BODY_ENCODING_STR.search(chunk)
        if match:
            enc_ = match.group('charset') or match.group('charset2') or match.group('xmlcharset')
            if enc_:
                charset = self._resolve_encoding(enc_)
        charset = 'utf-8' if not charset else charset
        return charset


    def _remove_newline_chars(self, text, newline_chars='\n\r'):
        """Remove all newline characters from the text.

        :param text: the text given as a string or unicode
        :param newline_chars: a list of all newline characters to remove

        """
        return self._translate(text, newline_chars)


    @staticmethod
    def _translate(text, deletechars=_PUNCTUATION):
        """Remove ``deletechars`` characters from the text.

        :param text: the text given as a string or unicode
        :param deletechars: a list of all characters to remove

        """
        if isinstance(text, str):
            return text.translate(None, deletechars)
        elif isinstance(text, unicode):
            return text.translate(dict([(ord(chr_), None) for chr_ in deletechars]))


    @staticmethod
    def _str_to_unicode(str_, encoding='utf-8'):
        """Convert a str object to unicode using the encoding given.
        Characters that cannot be converted will be converted to the unicode replacement character.

        :param str_: the string
        :param encoding: the string encoding

        """
        if isinstance(str_, str):
            return str_.decode(encoding, 'enc_xtractor_replace')
        elif isinstance(str_, unicode):
            return str_


    @staticmethod
    def _resolve_encoding(encoding):
        """Return the encoding that `encoding` maps to,
        or ``None`` if the encoding cannot be interpreted.

        :param encoding: the encoding given as a string

        """
        nr = encodings.normalize_encoding(encoding).lower()
        c18n_encoding =  encodings.aliases.aliases.get(nr, nr)
        translated = _DEFAULT_ENCODING_TRANSLATION.get(c18n_encoding, c18n_encoding)
        try:
            return codecs.lookup(translated).name
        except LookupError:
            return None


    @staticmethod
    def _xpath(elem, xpath, namespaces=None):
        """Evaluate the xpath expression using the element as a context node.
        Return the first value found, otherwise return ``None``.

        :param elem: the element of the HTML tree (`lxml::html::HtmlElement`)
        :param xpath: the xpath expression given as a string or `lxml::etree::XPath` instance
        :param namespaces: the namespace mapping given as a dict

        """
        if namespaces is not None and not isinstance(namespaces, dict):
            raise WebXtractorError("Argument ``namespaces`` must be a dict")
        if isinstance(xpath, basestring):
            result = elem.xpath(xpath, namespaces=namespaces)
        elif isinstance(xpath, XPath):
            result = xpath(elem, namespaces=namespaces)
        else:
            raise WebXtractorError(
                "Argument ``xpath`` must be a string, unicode or ``lxml::etree::XPath`` instance"
                )
        if result:
            if isinstance(result, list):
                return result[0]
            else:
                return result
        else:
            return None


    @staticmethod
    def _get_xpath_depth(xpath):
        """Return the xpath depth of the node.
        For example, for the xpath like "/html/body/div[9]/div[2]" it returns: 4

        :param xpath: the absolute xpath given as a string

        """
        if not isinstance(xpath, str):
            raise WebXtractorError("Argument ``xpath`` has to be given as a string.")
        if not xpath.startswith('/') or '//' in xpath:
            raise WebXtractorError(
                "Argument ``xpath`` contains a reletive path, not an absolute path."
                )
        if xpath.endswith('/'): xpath = xpath[:-1]
        depth = xpath.count('/')
        return depth


    @staticmethod
    def _get_parent_node_xpath(xpath_list):
        """Return xpath of the parent node of all nodes
        represented by their paths in ``xpath_list``.

        :param xpath_list: a list of paths

        """
        if not xpath_list: return None
        if not all([isinstance(path, str) for path in xpath_list]):
            raise WebXtractorError("All paths have to be given as a strings.")
        elif len(xpath_list) == 1:
            return xpath_list[0]
        parent_node = []
        paths = [e.split('/') for e in xpath_list]
        for i, p in enumerate(min(paths, key=lambda x: len(x))):
            if all([e[i] == p for e in paths]):
                parent_node.append(p)
            else:
                break
        return '/'.join(parent_node)


    def _get_parent_node(self, html_document, nodes):
        """Return the parent node of all ``nodes``.

        :param html_document: the HTML document (lxml Element `html`)
        :param nodes: a list of nodes (`lxml::html::HtmlElement` instances)

        """
        html_etree = html_document.getroottree()
        paths = [html_etree.getpath(node) for node in nodes]
        parent_node_xpath = self._get_parent_node_xpath(paths)
        parent_node = self._xpath(html_document, parent_node_xpath)
        return parent_node


    @staticmethod
    def _cut_xpath(xpath, depth):
        """Cut the given `xpath` to `depth` levels.

        :param xpath: the absolute xpath given as a string
        :param depth: the depth given as an integer

        """
        if not isinstance(depth, int):
            raise WebXtractorError("Argument `depth` has to be given as an integer.")
        if not isinstance(xpath, str):
            raise WebXtractorError("Argument `xpath` has to be given as a string.")
        if not xpath.startswith('/') or '//' in xpath:
            raise WebXtractorError(
                "Argument `xpath` contains a reletive path, not an absolute path."
                )
        if xpath.endswith('/'): xpath = xpath[:-1]
        xpath_nodes = xpath.split('/')[1:]
        return '/' + '/'.join(xpath_nodes[:depth])


    @staticmethod
    def _are_siblings(xpath_list):
        """Detect whether or not all elements are located
        at the same level of the HTML tree (are siblings).
        Return ``True`` if all elements are siblings, otherwise return ``False``.

        :param xpath_list: a list of paths

        """
        if len(set([p[:p.rfind('/')] for p in xpath_list])) == 1:
            return True
        return False


    def _parse_date(self, timestr, fuzzy=False):
        """Extract `datetime` format out of a string and return it, otherwise return ``None``.

        :param timestr: the string representation of the date
        :param fuzzy: skip unknown elements in the string representation of the date
         (in this case ``None`` is never returned)

        """
        if not isinstance(timestr, basestring):
            raise WebXtractorError("Argument ``timestr`` has to be given as a string or unicode.")
        if len(_RE_DIGIT.findall(timestr)) < 5 and not _RE_2CHR.search(timestr):
            return None
        if ' by' in timestr:
            timestr = timestr.partition('by')[0]
        timestr = (
            self._translate(timestr, '|@;')
            .lower()
            .replace('posted','')
            .replace('published','')
            .replace(' on','')
            .replace('/',' ')
            .replace('\\',' ')
            .strip()
            )
        try:
            datetime_ = date_parser.parse(timestr, default=self._default_date, fuzzy=fuzzy)
        except Exception:
            return None
        return datetime_.replace(tzinfo=None)


    @staticmethod
    def _compare_strings(str1, str2):
        """Compute the diff between two strings.
        Return the ratio of the "similarity" of the strings (float in [0,1]).

        :param str1: the first string
        :param str2: the second string

        """
        if not all([isinstance(s, basestring) for s in (str1, str2)]):
            raise WebXtractorError("Both strings have to be given as a `string` or `unicode`.")
        str1_len = len(str1)
        str2_len = len(str2)
        sm = SequenceMatcher(lambda e: e == " ", str1, str2)
        longest_match = sm.find_longest_match(0, str1_len, 0, str2_len).size
        if not longest_match: return 0.0
        match_ratio = float(longest_match) / min(str1_len, str2_len)
        if match_ratio < 0.3: return 0.0
        return round(sm.ratio(), 2)


    @staticmethod
    def _get_matching_substring(str1, str2):
        """Return the matching substring (with max length possible).

        :param str1: the first string
        :param str2: the second string

        """
        if not all([isinstance(s, basestring) for s in (str1, str2)]):
            raise WebXtractorError("Both strings have to be given as a `string` or `unicode`.")
        matching_blocks = SequenceMatcher(lambda s: s == " ", str1, str2).get_matching_blocks()
        start, _, size = max(matching_blocks, key=lambda k: k[2])
        return str1[start:start+size]


    @staticmethod
    def _document_from_string(html, recover=True, remove_blank_text=True,
        remove_comments=True, encoding=None):
        """Return the document (lxml Element `html`) from the given string.

        :param html: the HTML document given as a string
        :param recover: try hard to parse through broken HTML
        :param remove_blank_text: remove empty text nodes that are ignorable
        :param remove_comments: discard comments
        :param encoding: override the document encoding

        """
        html_parser = etree.HTMLParser(
            recover=recover,
            remove_blank_text=remove_blank_text,
            remove_comments=remove_comments,
            encoding=encoding)
        html_document = etree.fromstring(html, html_parser)
        if html_document is None:
            raise WebXtractorError("The HTML document is empty")
        return html_document


    @staticmethod
    def _normalize_urls(html_document):
        """Remove trailing slash.

        :param html_document: the HTML document (lxml Element `html`)

        """
        for anchor in _XPATH_ANCHOR(html_document):
            url = anchor.get('href')
            if url.endswith('/'): url = url[:-1]
            anchor.attrib['href'] = url


    def _remove_external_urls(self, html_document, domain):
        """Remove external links from the HTML document.

        :param html_document: the HTML document (lxml Element `html`)
        :param domain: the domain of the website

        """
        for anchor in _XPATH_ANCHOR(html_document):
            if not self._is_internal_url(anchor.get('href'), domain):
                anchor.drop_tree()


    # TODO: regexp
    @staticmethod
    def _is_internal_url(url, domain):
        """Check if the given URL is internal.

        :param url: the URL
        :param domain: the domain of the website

        """
        url_domain = '.'.join(_RE_DOMAIN.findall(urlparse(url).netloc))
        if url_domain == domain: return True


    @staticmethod
    def _decode_entities(html):
        """Convert all HTML entities into their unicode representations.
         * &XXX;
         * &#XXX;

        :param html: the html document given as a string

        """
        def _process_entity(match):
            entity = match.group(1)
            name = entity[1:-1]
            if name in name2codepoint:
                return unichr(name2codepoint[name])
            else:
                return entity

        def _process_num_entity(match):
            entity = match.group(1)
            num = entity[2:-1]
            try:
                return unichr(int(num))
            except ValueError:
                return entity

        html = _RE_NUM_ENTITY.sub(_process_num_entity, html)
        html = _RE_ENTITY.sub(_process_entity, html)
        return html


####################################################################################################


@public
class PostXtractor(BaseXtractor):
    """webxtractor::BaseXtractor::PostXtractor"""

    def extract(self, url, html=None, encoding=None, http_headers=None,
        extract_comments=True, extract_metrics=False, **data):
        """Extract the post content (and comments) from the HTML document or from the URL.
        Return `PostContainer` instance.

        :param url: the post URL
        :param html: the HTML document given as a string or unicode
        :param encoding: the encoding
        :param http_headers: HTTP headers given as a dict
        :param extract_comments: enable/disable the extraction of comments
        :param extract_metrics: enable/disable the extraction of social metrics (Facebook & Twitter)
        :params data: the information related to this post that has been extracted before
         (for example, the post title from the main page)

        """
        if not isinstance(url, basestring) or not '.' in url:
            raise WebXtractorError('Bad URL: %s' % url)

        # the timestamp for the time tracking
        _timestamp = time()

        self.url = url.split('#')[0]

        # prepare the HTML document + detect the charset
        html, encoding = self._get_clean_html(html, url, encoding, http_headers)

        # create a container for the content
        post_container = PostContainer(
            url=url,
            charset=encoding,
            debug_info={},
            )

        # fill a container with the already extracted data
        if data.get('title'):
            post_container.title = data['title']

        # build the HTML document (lxml)
        html_document = document_fromstring(html)
        # build the HTML document tree (lxml)
        html_etree = html_document.getroottree()

        # make all links absolute
        html_document.make_links_absolute(url)

        # drop sidebar
        sidebar = self._xpath(html_document, _XPATH_SIDEBAR_DIV)
        if sidebar is not None:
            sidebar.drop_tree()

        # META
        # parse the <head> of the HTML document and save the results in the container
        self._parse_head(html_document, post_container)

        # THE PUBLISH DATE IN URL
        # let's try to extract the publish date from the url
        # later this pattern will help us
        self._default_date = None
        publish_date_in_url = filter(lambda e: e.isdigit(), url.split('/'))
        if len(publish_date_in_url) in range(2,4):
            self._default_date = self._parse_date(' '.join(publish_date_in_url))

        # COMMENTS
        # extract comments
        if extract_comments:
            post_container.comments = self._extract_comments(html_document)
        # remove comments from the page
        for node in _XPATH_COMMENT_ATTR(html_document):
            node.drop_tree()

        # # remove widgets / sidebar / navbar
        # for node in _XPATH_NOT_CONTENT_NODES(html_document.body):
        #     node.drop_tree()

        # TAGS
        # extract tags
        tags = html_document.find_rel_links('tag')
        for tag in tags:
            post_container.tags[tag.text_content()] = tag.get('href')
            # tag.drop_tree()

            # # the <header> tag specifies a header for the document or section (HTML5)
            # header = self._xpath(html_document, _XPATH_HEADER_TAG)
            # # find all headings <h1>...<h6>
            # headings = []
            # if header is not None:
            #     headings = _XPATH_HEADINGS_TAGS(header)
            # if not headings:
            #     headings = _XPATH_HEADINGS_TAGS(html_document)

        # find all headings <h1>...<h6>
        headings = _XPATH_HEADINGS_TAGS(html_document)

        # THE POST TITLE
        # ...
        title_node = None
        title_pattern = (
            post_container.title
            or post_container.meta_og_title
            or post_container.head_title
            )
        # if we have headings on the page
        if headings:
            # if we have the post title extracted before (from the main page or <head> section)
            # then we can use this title to rate candidates
            if title_pattern:
                title_candidates = {}
                for heading in headings:
                    title_candidates[heading] = self._compare_strings(
                        heading.text_content().strip().lower(),
                        title_pattern.lower()
                        )
                max_score = max(title_candidates.items(), key=lambda k: k[1])[1]
                final_title_candidates = filter(
                    lambda c: c[1] > 0.2 and c[1] > max_score * 0.8,
                    title_candidates.items()
                    )
                if final_title_candidates:
                    title_node = max(
                        final_title_candidates,
                        key=lambda k: -int(k[0].tag[-1])
                        )[0]
            else:
                # the biggest and longest title
                title_node = max(
                    filter(lambda h: not self._parse_date(h.text_content()), headings),
                    key=lambda k: (-int(k.tag[-1]), len(k.text_content()))
                    )
        # ...
        # choose the most appropriate post title (the final result)
        if title_node is not None:
            headings.remove(title_node)
            post_container.title = title_node.text_content().strip()
            # remove header-image
            for node in html_document.body.iter('img', title_node.tag):
                if node.tag == 'img':
                    node.drop_tree()
                elif node is title_node:
                    break
            # ...
            title_node.drop_tree()
        # ...
        elif title_pattern and not post_container.title:
            post_container.title = title_pattern.strip()

        # THE PUBLISH DATE
        # in most cases the publish date is located near the post title
        # or in the bottom of the post content ***
        # ...
        # but first of all, let's process the another case
        # sometimes the publish date is wrapped by a heading
        date_candidates = []
        for heading in headings[:]:
            publish_date = self._parse_date(heading.text_content())
            if publish_date:
                # headings.remove(heading)
                heading.drop_tree()
                date_candidates.append(publish_date)
        if date_candidates:
            if self._default_date:
                # min timedelta
                date = min(date_candidates, key=lambda k: self._default_date - k)
            else:
                date = max(date_candidates)
            post_container.publish_date = date

        # ...
        # the deep search of the publish date
        if not post_container.publish_date:
            date_node, date = self._find_date_in_node(html_document.body)
            if date:
                post_container.publish_date = date
                if not len(date_node):
                    date_node.drop_tree()
        # ...
        if not post_container.publish_date:
            post_container.publish_date = self._default_date

        # the recommended practice is the <article> tag for the post content (HTML5)
        # let's check if we have such section on the page
        # article_sections = _XPATH_ARTICLE_TAG(html_document)
        # if len(article_sections) == 1:
        #     html_document = article_sections[0]

        # THE POST CONTENT
        # - big images & text are located in the post content
        # - the link density in the post content is less than in the sidebar / menu
        # ...
        # first of all, let's find all big images on the page
        extracted_images = self._extract_images(html_document)
        image_nodes = [img[0] for img in extracted_images]
        # now we can rate all <div> & <article> sections on the page and get the content node
        content_node, content_images = self._get_content_node(html_document, image_nodes)
        # save the post content
        if content_node is not None:
            # content_node.tag = 'article'
            # content_node.attrib.clear()
            # # remove empty wrappers
            # div_wrappers = []
            # for node in content_node.iter('div'):
            #     if not node.text and not node.tail:
            #         div_wrappers.append(node)
            # for node in div_wrappers:
            #     node.drop_tag()
            post_container.images = [
                img[1] for img in filter(lambda img: img[0] in content_images, extracted_images)
                ]
            text_blocks = _XPATH_TEXT_BLOCKS(content_node)
            text_blocks = filter(None, [text.strip() for text in text_blocks])
            post_container.text = ' '.join(text_blocks)
            post_container.html = tostring(content_node, encoding=unicode, with_tail=False)
            content_node.drop_tree()

        # AUTHOR
        post_container.author_name = post_container.meta_author

        # get social metrics from the Facebook and the Twitter
        if extract_metrics:
            post_container.social_metrics = {}
            post_container.social_metrics['twitter'] = self._get_twitter_metrics(url)
            post_container.social_metrics['facebook'] = self._get_facebook_metrics(url)

        # update the debug information
        post_container.debug_info['processing_time'] = round(time() - _timestamp, 2)

        # make a deep copy of the content
        self.content = copy.deepcopy(post_container)

        return post_container


    def _extract_comments(self, html_document):
        """Extract comments from the HTML document.
        Return a list of `CommentContainer` instances.

        :param html_document: the HTML document (lxml Element `html`)

        """
        # COMMENTS
        # - any comment can contain a subtree of replies
        # - all comments are siblings (in the lxml tree) and their replies are siblings too
        # - all top-level comments and their replies have the one common node
        # - in most cases the comment block contains "reply"-elements
        # - often '@id' or '@class' attribute of comments contains a "comment" substring
        # - more often it's a "comment-xxx"-like pattern (where "x" - digit)
        # - we process only those comments that have no replies (TODO: fix)
        # - we process only those pages that have more than one comment
        # - we believe that the xpath depth for replies is more than for the top-level comments

        html_etree = html_document.getroottree()

        extracted_comments = []

        # 1. COMMENTS WITH "REPLY"-ELEMENT
        # ...
        # let's find all tags with a "reply" word in the text content
        comments_candidates = _XPATH_COMMENT_REPLY(html_document.body)
        # we do not process this case
        if len(comments_candidates) == 1:
            comments_candidates = None
        # ...
        # some types of comments do not contain "reply"-element
        # let's try another way
        if not comments_candidates:
            # ...
            # 2. COMMENTS WITH A "COMMENT-XXX"-LIKE PATTERN IN `@ID` OR `@CLASS` ATTRIBUTE
            # ...
            # find all elements that have such pattern
            # tags: 'tr', 'li', 'dl'
            comments_candidates = _XPATH_COMMENT_ID_ALL(html_document.body)
            if not comments_candidates:
                # tag: 'div'
                comments_candidates = _XPATH_COMMENT_ID_DIV(html_document.body)

        if comments_candidates:
            # we are ready to extract comments from the HTML document
            # build the tree of comments
            comments_tree = self._build_comments_tree(comments_candidates, html_document, html_etree)
            # ...
            # parse the tree of comments and extract all comments
            extracted_comments = self._parse_comments_tree(comments_tree, html_document, html_etree)

        return extracted_comments


    def _build_comments_tree(self, comments_nodes, html_document, html_etree):
        """Return the structured tree of comments.

        :param comments_nodes: a list of nodes (`lxml::html::HtmlElement`)
        :param html_document: the HTML document (lxml Element `html`)
        :param html_etree: the HTML document tree (lxml `ElementTree`)

        """
        comments_tree = []
        comments_coffins = []

        # get all xpaths
        comments_paths = [html_etree.getpath(c) for c in comments_nodes]

        # find the parent node that contains all comments
        parent_path = self._get_parent_node_xpath(comments_paths)

        # get the xpath depth of the parent node
        parent_path_depth = self._get_xpath_depth(parent_path)

        # get the xpath depth of each element
        depth_paths = [self._get_xpath_depth(p) for p in comments_paths]

        # get the top level depth (top-level comments)
        top_level_depth = min(depth_paths)

        # get the top level comments for this level
        for d, path in filter(
            lambda d: d[0] == top_level_depth,
            zip(depth_paths, comments_paths)
            ):
            # the correct xpath
            comment_path = self._cut_xpath(path, parent_path_depth + 1)
            # the comment node
            comment_node = self._xpath(html_document, comment_path)
            # remove xpath from list
            comments_paths.remove(path)
            # let's find replies
            replies = filter(lambda p: comment_path in p, comments_paths)
            # if len(replies) > 1:
                # comments_tree[comment_node], cf = self._build_comments_tree(
                # replies,
                # html_document
                # )
            if replies:
                comments_coffins.append(comment_node)
            else:
                comments_tree.append(comment_node)

        for node in comments_coffins:
            node.drop_tree()

        return comments_tree


    def _parse_comments_tree(self, comments_tree, html_document, html_etree):
        """Parse all comments in the tree of comments.

        :param comments_tree: the structured tree of comments
        :param html_document: the HTML document (lxml Element `html`)
        :param html_etree: the HTML document tree (lxml `ElementTree`)

        """
        extracted_comments = []
        for comment_node in comments_tree:
            # if comment_node is None: continue
            # lost node?
            # if not html_etree.getpath(comment_node).startswith('/html'):
            #     continue
            comment_container = CommentContainer()
            # if replies:
            #     comment_container.replies = self._parse_comments_tree(
            #         replies,
            #         html_document,
            #         html_etree
            #         )
            self._parse_comment(comment_node, comment_container, html_document, html_etree)
            if comment_container.html is not None:
                extracted_comments.append(comment_container)
        return extracted_comments


    def _get_comment_url(self, comment_node):
        """Find and return the comment url.

        :param comment_node: the comment node that possibly contains the URL

        """
        if self.url is None: return None
        anchors = comment_node.xpath(_XPATH_INTERNAL_ANCHOR % self.url)
        if not anchors:
            anchors = comment_node.xpath(_XPATH_INTERNAL_ANCHOR_ANCESTOR % self.url)
        if anchors:
            comment_url_candidates = [anchor.get('href') for anchor in anchors]
        else:
            return None
        for candidate in comment_url_candidates:
            if (
                    '?' not in candidate and
                    '#' in candidate and
                    'comment' in candidate.split('#')[1] and
                    _RE_2DIGITS.search(candidate.split('#')[1])
                ):
                return candidate


    @safe_wrapper
    def _parse_comment(self, comment_node, comment_container, html_document, html_etree):
        """Extract the content from the comment node and save it in the comment container.

        :param comment_node: the comment node (`lxml::html::HtmlElement`)
        :param comment_container: `CommentContainer` obj
        :param html_document: the HTML document (lxml Element `html`)
        :param html_etree: the HTML document tree (lxml `ElementTree`)

        """
        # first of all, let's clean this node (delete stuff like "share", "reply", "like" etc.)
        for node in _XPATH_COMMENT_GARBAGE(comment_node):
            node.drop_tree()

        # remove 'by' text
        for text_block in _XPATH_TEXT_BLOCKS(comment_node):
            text_block_parent = text_block.getparent()
            if (
                text_block_parent.text and
                text_block_parent.text.strip().lower() == text_block.strip().lower() == 'by'
                ):
                text_block_parent.text = None

        # THE COMMENT URL
        comment_container.url = self._get_comment_url(comment_node)

        # THE PUBLISH DATE
        date_node, date = self._find_date_in_node(comment_node)
        comment_container.publish_date = date
        if date:
            if not comment_container.url:
                date_anchor = None
                if date_node.tag == 'a':
                    date_anchor = date_node
                else:
                    date_anchor = self._xpath(date_node, _XPATH_ANCHOR)
                    if date_anchor is None:
                        date_anchor = self._xpath(date_node, _XPATH_ANCHOR_ANCESTOR)
                if date_anchor is not None:
                    comment_container.url = date_anchor.get('href')
            if not len(date_node):
                date_node.drop_tree()

        # THE AUTHOR 1
        # "author"/"user"/"name" substring in any attribute
        author_candidates = filter(
            lambda n: len(n.text_content().strip()) > 1,
            _XPATH_AUTHOR_ATTR(comment_node)
        )
        author_anchor = None
        if author_candidates:
            if len(author_candidates) == 1:
                node = author_candidates[0]
            else:
                anchors = filter(
                    lambda c: c.tag == 'a' and len(c.text_content().strip()) > 1,
                    author_candidates
                    )
                if anchors:
                    author_anchor = max(anchors, key=lambda k: len(k.text_content()))
                if author_anchor is None:
                    node = self._get_parent_node(html_document, author_candidates)
            if author_anchor is None:
                if node.tag == 'a':
                    author_anchor = node
                else:
                    author_anchor = self._xpath(node, _XPATH_ANCHOR)
                    if author_anchor is None:
                        author_anchor = self._xpath(node, _XPATH_ANCHOR_ANCESTOR)
            if author_anchor is not None:
                comment_container.author_url = author_anchor.get('href')
                comment_container.author_name = author_anchor.text_content().strip()
            else:
                text_blocks = filter(
                    lambda text: all([t.isalpha() for t in text.split()]),
                    [text.strip() for text in _XPATH_TEXT_BLOCKS(node) if text.strip()]
                    )
                if text_blocks:
                    comment_container.author_name = max(text_blocks, key=lambda k: len(k))
        # ...
        for node in author_candidates:
            if node.getparent() is not None:
                node.drop_tree()

        # THE AUTHOR 2
        # div@meta//a
        if not comment_container.author_name:
            best_candidate = None
            meta_author_anchors = _XPATH_COMMENT_META_AUTHOR(comment_node)
            for anchor in meta_author_anchors:
                if anchor.text.strip().istitle():
                    best_candidate = anchor
                    break
                elif all([t.isalpha() for t in anchor.text.strip().split()]):
                    best_candidate = anchor
            if best_candidate is not None:
                comment_container.author_name = best_candidate.text.strip()
                comment_container.author_url = best_candidate.get('href')
                best_candidate.drop_tree()

        # THE CONTENT
        # find all <div> and <p> nodes that looks like the comment body
        possible_body_nodes = _XPATH_COMMENT_BODY(comment_node)
        if len(possible_body_nodes) == 1:
            body_node = possible_body_nodes[0]
        else:
            body_node = comment_node
        content_blocks = filter(
            lambda n: n.tag == 'p' or (len(''.join([t.strip() for t in n.xpath('./text()')])) > 4),
            _XPATH_COMMENT_CONTENT_NODES(body_node)
            )
        if content_blocks:
            if len(content_blocks) == 1:
                node = content_blocks[0]
            else:
                node = HtmlElement()
                node.extend(content_blocks)
            text_blocks = filter(None, [text.strip() for text in _XPATH_TEXT_BLOCKS(node)])
            comment_container.text = ' '.join(text_blocks)
            comment_container.html = tostring(node, encoding=unicode, with_tail=False)
            if node is not comment_node and node.getparent() is not None:
                node.drop_tree()

        # THE AUTHOR 3
        # ...
        if comment_container.author_name is None:
            best_candidate = None
            for candidate in _XPATH_TEXT_BLOCKS(comment_node):
                content = candidate.strip()
                if len(content) < 3: continue
                if content.istitle():
                    best_candidate = candidate
                    break
                elif all([c.isalpha() for c in content.split()]) and best_candidate is None:
                    best_candidate = candidate
            if best_candidate is not None:
                comment_container.author_name = best_candidate.strip()
                node = best_candidate.getparent()
                if node.tag == 'a':
                    comment_container.author_url = node.get('href')

        # remove the node from the HTML document
        comment_node.drop_tree()


    def _find_date_in_node(self, node, process_text_nodes=True):
        """Find the publish date in the given node.
        Return a tuple with the date node (`lxml::html::HtmlElement` instance) that contains
        the publish date and its `datetime` obj, otherwise return ``None``.

        :param node: the node that possibly contains the publish date (`lxml::html::HtmlElement`)
        :param process_text_nodes: check the children nodes for the publish date in the text

        """
        date = None
        date_node = None
        date_candidates = []

        # 1. <time> tag
        date_candidates.extend(
            self._process_date_candidates(
                _XPATH_TIME_TAG(node)
                )
            )
        # 2. in the @title attr of the anchor
        date_candidates.extend(
            self._process_date_candidates(
                _XPATH_DATE_IN_ANCHOR(node)
                )
            )
        # 3. "published" substring in any attribute (except 'src','href')
        date_candidates.extend(
            self._process_date_candidates(
                _XPATH_PUBLISHED_ATTR(node)
                )
            )
        # 4. "date" substring in any attribute (except 'src','href')
        date_candidates.extend(
            self._process_date_candidates(
                _XPATH_DATE_ATTR(node)
                )
            )
        # 5. iterate over the children nodes and check them for the publish date in the text
        if not date_candidates and process_text_nodes:
            possibly_date_nodes = filter(
                lambda b: len(b.strip()) in range(5,32) and _RE_2DIGITS.search(b),
                _XPATH_TEXT_BLOCKS(node)
                )
            for candidate in possibly_date_nodes:
                date = self._parse_date(candidate.strip())
                if date:
                    # date_candidates.append((None, date))
                    date_candidates.append((candidate.getparent(), date))

        if date_candidates:
            if self._default_date:
                # min timedelta
                date_node, date = min(date_candidates, key=lambda k: self._default_date - k[1])
            else:
                date_node, date = max(date_candidates, key=lambda k: k[1])

        return date_node, date


    def _process_date_candidates(self, date_candidates):
        """Return a list of nodes that contain the publish date [(date_node1, `datetime` obj), etc.]

        :param date_candidates: a list of nodes that possibly contain the publish date

        """
        date_nodes = []
        for node in date_candidates:
            date = None
            if node.get('datetime'):
                date = self._parse_date(node.get('datetime'))
            if not date and node.get('title'):
                date = self._parse_date(node.get('title'))
            if not date:
                text_blocks = _XPATH_TEXT_BLOCKS(node)
                for text in text_blocks:
                    date = self._parse_date(text)
                    if date: break
            if date:
                date_nodes.append((node, date))
        return date_nodes


####################################################################################################


@public
class BlogXtractor(BaseXtractor):
    """webxtractor::BaseXtractor::BlogXtractor"""

    def extract(self, url, html=None, encoding=None, http_headers=None,
        prev_page_url=None, prev_page_number=None, **data):
        """Extract the blog page content (urls of posts and the next page url)
        from the HTML document or from the URL.
        If both `html`and `url` are provided, then `url` is used only to find the pagination.
        Return `BlogContainer` instance.

        :param url: the blog URL
        :param html: the HTML document given as a string
        :param encoding: the encoding
        :param http_headers: HTTP headers given as a dict
        :params prev_page_url: the previous page url
        :param prev_page_number: the previous page number given as an integer
        :params data: the information that has been extracted before
         (for example, a list of titles/urls from the previous page)

        """
        if not isinstance(url, basestring) or not '.' in url:
            raise WebXtractorError('Bad URL: %s' % url)

        # the timestamp for the time tracking
        _timestamp = time()

        # set "zero" page
        if prev_page_number is None:
            prev_page_number = 0

        # prepare the HTML document + detect the charset
        html, encoding = self._get_clean_html(html, url, encoding, http_headers)

        blog_domain = '.'.join(_RE_DOMAIN.findall(urlparse(url).netloc))

        # create a container for the blog
        blog_container = BlogContainer(
            current_page_url=url,
            current_page_number=prev_page_number+1,
            charset=encoding,
            debug_info={},
            )

        # build the HTML document (lxml)
        html_document = document_fromstring(html)
        # build the HTML document tree (lxml)
        html_etree = html_document.getroottree()

        # drop sidebar
        sidebar = self._xpath(html_document, _XPATH_SIDEBAR_DIV)
        if sidebar is not None:
            sidebar.drop_tree()

        # make all links absolute
        html_document.make_links_absolute(url)
        # remove external links
        self._remove_external_urls(html_document, blog_domain)
        # remove trailing slash from urls
        self._normalize_urls(html_document)

        # the next page number
        next_page_number = prev_page_number + 2
        _re_next_page_number = re.compile(_RE_PAGE_NUM % next_page_number)

        # a place for winner
        next_page_winner = None

        # # !!!note: this trick does not work with the traditional pagination
        # # if we know the xpath of the "next page" anchor, then we can get it without any magic
        # if xpaths is not None and 'next_page_xpath' in xpaths:
        #     next_page_winner = self._xpath(html_document, xpaths['next_page_xpath'])

        # if we know the previous page url and its number
        # then we can try to find the next page url by this pattern
        if (
            next_page_winner is None
            and prev_page_number and prev_page_url and
            re.search(_RE_PAGE_NUM % prev_page_number, prev_page_url)
            ):
            next_page_url_pattern = (
                './/a[re:test(@href,"{}") and re:test(@href,"{}")]'
                .format(
                    prev_page_url.replace(str(prev_page_number),'\d+'),
                    _RE_PAGE_NUM % next_page_number
                    )
                )
            # let's check this pattern
            next_page_candidates = html_document.xpath(next_page_url_pattern, namespaces=_RE_NS)
            if next_page_candidates:
                winner = (0, None)
                # let's rate candidates
                for candidate in next_page_candidates:
                    if prev_page_url in candidate.get('href'): continue
                    ratio_ = self._compare_strings(candidate.get('href'), prev_page_url)
                    # ratio_ *= len(_re_next_page_number.findall(candidate.get('href'))) ** 0.5
                    if ratio_ > winner[0]:
                        winner = ratio_, candidate
                # and choose the winner
                if winner[0] > 0.90:
                    next_page_winner = winner[1]

        # remove links to the previous page from the HTML document
        if prev_page_url:
            prev_page_anchors = html_document.xpath('.//a[@href="{}"]'.format(prev_page_url))
            for anchor in prev_page_anchors:
                anchor.drop_tree()

        # in most cases this block will be processed only on the first two pages
        # (if we are going to crawl the blog in one run)
        if next_page_winner is None:

            # if we know the previous page url
            # then we can extract the pattern from it (it'll help us later)
            # in most cases such links differ only by digits in them
            # let's normalize the previous page url
            nav_url_pattern = self._translate(prev_page_url, '0123456789') if prev_page_url else None

            # NAVIGATION
            # - all navigation links have the blog's domain in the url
            # - all navigation links have at least one digit in the url
            # ...
            # let's find all <nav> tags to simplify the task
            # nav_tags = _XPATH_NAV_TAG(html_document)
            # if nav_tags:
            #     nav = './/nav'
            # else:
            #     nav = '.'
            nav = '.'
            # ...
            # 1. THE “PAGE”-LIKE NAVIGATION.
            # this case is similar to the traditional pagination (urls are similar)
            # but we have no [1] [2] .. [9] etc. elements on the page
            # we process only internal links to find such patterns:
            # (page(s|d)|index)/N
            # (page(s|d)|index)-N
            # (page(s|d)|index)=N
            # (page(s|d)|index)N
            # (page(s|d)|index)?N
            #...
            # let's find the anchor that satisfy these conditions
            nav_page_anchor = self._xpath(
                html_document,
                _XPATH_NAV_PAGE % (nav, blog_domain, next_page_number),
                namespaces=_RE_NS
                )
            if nav_page_anchor is not None:
                next_page_winner = nav_page_anchor
            #...
            if next_page_winner is None:
                # 2. THE TRADITIONAL PAGINATION.
                # the common practice in pagination: [1] [2] [3] ... [8] [9] [10]
                # in this case we try to find all anchors that have one common pattern:
                # all such anchors have the text and the part of the 'href' attribute
                # represented by the same digit
                # for example: <a class="page" href="http://www.example.com/page/2/">2</a>
                # the current page is represented by another tag with the digit in it
                # ...
                # let's find all anchors that satisfy these conditions
                nav_pagination_nodes = html_document.xpath(
                    _XPATH_NAV_PAGINATION % (nav, blog_domain),
                    namespaces=_RE_NS
                    )
                if nav_pagination_nodes:
                    # sometimes we have pagination in the top and in the bottom of the page
                    # let's try to detect what kind of pagination it is
                    pag_links = set()
                    for anchor in nav_pagination_nodes[:]:
                        # if we know the next page number
                        # then we can use this information to quickly find the next page number
                        if anchor.text == str(next_page_number):
                            next_page_winner = anchor
                            break
                        if anchor.get('href') not in pag_links:
                            pag_links.add(anchor.get('href'))
                        else:
                            # pagination in the top and in the bottom of the page
                            # convert to the simple pagination
                            nav_pagination_nodes.remove(anchor)
                    # ...
                    if next_page_winner is None:
                        # find the parent node
                        paths = [html_etree.getpath(anchor) for anchor in nav_pagination_nodes]
                        parent_path = self._get_parent_node_xpath(paths)
                        parent_node = self._xpath(html_document, parent_path)
                        # find the current page in pagination
                        nav_current_node = self._xpath(
                            parent_node,
                            _XPATH_NAV_PAGINATION_CURRENT % (nav, blog_container.current_page_number),
                            namespaces=_RE_NS
                            )
                        if nav_current_node is not None:
                            nav_current_path = html_etree.getpath(nav_current_node)
                            paths += [nav_current_path]
                            if self._are_siblings(paths):
                                # find the next page in pagination if elements are siblings
                                # (are located at the same level of the HTML tree)
                                for sibling in nav_current_node.itersiblings():
                                    if sibling in nav_pagination_nodes:
                                        next_page_winner = sibling
                                        break
                            else:
                                # find the next page in pagination if elements are not siblings
                                top_path_depth = self._get_xpath_depth(parent_path) + 1
                                nav_current_path = self._cut_xpath(nav_current_path, top_path_depth)
                                nav_current_node = self._xpath(parent_node, nav_current_path)
                                for sibling in nav_current_node.itersiblings():
                                    anchor = self._xpath(sibling, _XPATH_ANCHOR)
                                    if anchor in nav_pagination_nodes:
                                        next_page_winner = anchor
                                        break
            # ...
            if next_page_winner is None:
                # 3. THE NAVIGATION BY DATE-FILTER QUERIES.
                # this type of navigation is most used on blogspot-like platforms
                # in this case we have one/two elements on the page, something like:
                # [newer posts] and [older posts]
                # such links have "?" char ("?query" with the date-filter) and at least two digits
                # we are interested in the link with "old" or "next" substring in one of attributes
                # ("older-page", "next-page" etc.)
                # ...
                # let's find all anchors that have such pattern in the "@href" attribute
                nav_by_date_anchor = self._xpath(
                    html_document,
                    _XPATH_NAV_BY_DATE % (nav, blog_domain),
                    namespaces=_RE_NS
                    )
                if nav_by_date_anchor is not None:
                    next_page_winner = nav_by_date_anchor
            # ...
            if next_page_winner is None:
                # 4. THE “PREVIOUS – NEXT”:PAGE NAVIGATION.
                # in this case we have two anchors with "next"/"prev" substring in one of attributes
                # or the text content of this anchors has such substring
                # we believe that the "next page" is what we need (older page)
                # sometimes such anchors have no text content (they are present as an images)
                # ...
                # let's find all elements that have a "next" substring in one of attributes
                # and all elements that have a "next" substring in the text content
                nav_next_prev_nodes = html_document.xpath(_XPATH_NAV_NEXT_PREV_PAGE % nav)
                # let's filter all elements by presence of <a> tag
                nav_candidates = []
                for node in nav_next_prev_nodes:
                    anchor = None
                    if node.tag == 'a' and node.get('href'):
                        anchor = node
                    else:
                        # descendants
                        anchor = self._xpath(node, _XPATH_ANCHOR)
                        if anchor is None:
                            # ancestors
                            anchor = self._xpath(node, _XPATH_ANCHOR_ANCESTOR)
                    if (anchor is not None and
                        blog_domain in anchor.get('href') and
                        _re_next_page_number.search(anchor.get('href'))
                        ):
                        nav_candidates.append(anchor)
                # ...
                if len(nav_candidates) == 1:
                    # if we have the only one candidate, then it seems to be what we are looking for
                    next_page_winner = nav_candidates.pop()
                elif nav_candidates:
                    if nav_url_pattern:
                        # let's compare all candidates with the url pattern
                        winner = (0, None)
                        for candidate in nav_candidates:
                            ratio_ = self._compare_strings(
                                self._translate(candidate.get('href'), '0123456789'),
                                nav_url_pattern
                                )
                        if ratio_ > winner[0]:
                            winner = ratio_, candidate
                        if winner[0] > 0.9:
                            next_page_winner = winner[1]
                    else:
                        # in most cases this anchor is located in the right bottom corner
                        next_page_winner = nav_candidates[-1]
        # ...
        # save the next page url and its xpath
        if next_page_winner is not None:
            blog_container.next_page_url = next_page_winner.get('href')
            next_page_xpath = html_etree.getpath(next_page_winner)
            blog_container.debug_info['xpaths'] = {'next_page_xpath': next_page_xpath}

        # THE POST URL/TITLE
        # - the common practice: the post title in <h1>...<h6> tags
        # - the post url contains the blog's domain
        # - often the post url contains a few parts that are represented by digits
        #   for example: http://www.example.com/2014/04/post
        # ...
        if 'processed_posts' in data:
            processed_posts_urls = [
                post.url.rstrip('/') for post in data['processed_posts'] if post
                ]
        else:
            processed_posts_urls = []
        # ...
        post_winners = []
        #...
        # find all <h1>, <h2>, <h3>, <h4>, <h5>, <h6> tags
        headings = _XPATH_HEADINGS_TAGS(html_document)
        post_candidates = {}
        # select all headings with <a> tag
        for heading in headings:
            # descendants
            anchor = self._xpath(heading, _XPATH_INTERNAL_ANCHOR % blog_domain)
            if anchor is None:
                # ancestors
                anchor = self._xpath(
                    heading,
                    _XPATH_INTERNAL_ANCHOR_ANCESTOR % blog_domain
                    )
            if anchor is not None:
                anchor_text = anchor.text_content().strip()
                if (
                    anchor.get('href') not in processed_posts_urls and
                    anchor_text.lower() not in _MONTHS and not _RE_YEAR.match(anchor_text)
                    ):
                    post_candidates.setdefault(heading.tag, {'anchors': []})['anchors'].append(anchor)
        # ...
        if post_candidates:
        # let's rate all candidates by the URL structure and <h[weight]>
            for heading in post_candidates.keys():
                post_candidates[heading]['score'] = 0.0
                anchors_with_date = set()
                for anchor in post_candidates[heading]['anchors']:
                    url_parts = anchor.get('href').split('/')
                    possible_date_parts = filter(lambda e: e.isdigit() and len(e) > 1, url_parts)
                    if len(possible_date_parts) > 1:
                        anchors_with_date.add(anchor)
                        post_candidates[heading]['score'] += (8 - int(heading[-1])) ** 1.5
                    else:
                        post_candidates[heading]['score'] += (8 - int(heading[-1])) ** 0.75
                anchors_with_date_count = float(len(anchors_with_date))
                if anchors_with_date_count == len(post_candidates[heading]['anchors']):
                    post_candidates[heading]['score'] *= anchors_with_date_count ** 0.5
                elif anchors_with_date_count:
                    ratio_ = anchors_with_date_count / len(post_candidates[heading]['anchors'])
                    if ratio_ > 0.7:
                        post_candidates[heading]['score'] *= anchors_with_date_count ** 0.35
                        post_candidates[heading]['anchors'] = anchors_with_date
            # let's choose winners
            post_winners = max(post_candidates.values(), key=lambda k: k['score'])['anchors']
        # ...
        else:
            # if we can't locate headings with anchors inside, then:
            # 1 - the blog is empty
            # 2 - the blog has the HTML structure without headings
            # let's try to process the second case
            # ...
            # extract urls from images
            image_nodes = [img[0] for img in self._extract_images(html_document)]
            for node in image_nodes:
                anchor = self._xpath(node, _XPATH_INTERNAL_ANCHOR_ANCESTOR % blog_domain)
                if anchor is not None and self._is_internal_url(anchor.get('href'), blog_domain):
                    post_winners.append(anchor)
            # ...
            if not post_winners:
                # in this case we use the same rules:
                # - the post url contains the blog's domain
                # - the post url contains a few parts in the path that are represented by digits
                # find all anchors that satisfy these conditions
                post_candidates = html_document.xpath(_XPATH_INTERNAL_ANCHOR % blog_domain)
                for anchor in post_candidates:
                    anchor_text = anchor.text_content().strip()
                    if (anchor_text.lower() not in _MONTHS and not _RE_YEAR.match(anchor_text)):
                        url_parts = anchor.get('href').split('/')
                        possible_date_parts = filter(lambda e: e.isdigit() and len(e) > 1, url_parts)
                        if len(possible_date_parts) > 1:
                            post_winners.append(anchor)
            # ...
            post_winners = filter(lambda a: a.get('href') not in processed_posts_urls, post_winners)
        # ...
        # let's save all posts (urls & titles)
        if post_winners:
            # often the post url represented by anchor with the post title in the text content
            # but sometimes we have the duplicate url with the publish date in the text content
            # or we have the duplicate url with the text like "read more"
            # let's process this case
            posts = {}
            for post in post_winners:
                url = post.get('href')
                if url.endswith(blog_domain): continue
                title = post.text_content().strip()
                digits_count = len(_RE_DIGIT.findall(title))
                if digits_count > 4 or 'read ' in title.lower():
                    title = None
                    title_score = 0
                else:
                    title_score = len(title)
                if (url in posts and title_score > posts[url]['title_score']) or url not in posts:
                    posts.setdefault(url, {})
                    posts[url]['title_score'] = title_score
                    posts[url]['title'] = title
            blog_container.posts = []
            for url in posts:
                blog_container.posts.append(
                    PostContainer(
                        url=url,
                        title=posts[url]['title'],
                        charset=encoding,
                        )
                    )

        # update the debug information
        blog_container.debug_info['processing_time'] = round(time() - _timestamp, 2)

        # make a deep copy of the content
        self.content = copy.deepcopy(blog_container)

        return blog_container


####################################################################################################










