# encoding: utf-8
import itertools
from requests.exceptions import Timeout, ConnectionError
from lxml.html import document_fromstring, fromstring
import re
import time
import requests

__author__ = 'atulsingh'

import logging

from debra.models import Posts, PostLengthCheck
from xpathscraper import xbrowser
from django.conf import settings
from datetime import datetime

'''
This is used only for blogs for which feed fetcher only got a summary content.

The idea here is to use the manually--identified--pattern in class names and ids to discover the main content of the post.
Rest of the post data (date, title) is correctly fetched from the feeds, so we should be good there.
'''


log = logging.getLogger('platformdatafetcher.fetch_blog_posts_manually')

requests_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:40.0) Gecko/20100101 Firefox/40.0'}

# these (main, post_body) xpath tuples were manually created by looking at posts
path_lists = [("//article[contains(@id, 'post-')]", "//div[contains(@class, 'entry-content')]"),
              ("//article[contains(@id, 'post-')]", "//div[contains(@class, 'post_content')]"),
              ("//article[contains(@class, 'post-')]", "//div[contains(@class, 'entry-')]"),
              ("//div[contains(@class, 'content-area')]", "//div[contains(@class, 'entry-content')]"),
              ("//div[@id='post-area']", "//div[@id='content-area']"),
              ("//div[@id='main']/article[contains(@id, 'post-')]", "//div[@class='post-entry']"),
              ("//div[@id='main']//article[contains(@class, 'post-')]", '//section[@class="entry"]'),
              ("//div[contains(@id, 'post-')]", "//div[contains(@class, 'post-entry')]"),
              ("//div[contains(@class, 'post-')]", "//p[contains(@class, 'post-info')]"),
              ("//div[contains(@class, 'blog-post')]", ""),
              ("//div[contains(@class, 'post-list')]", "//article[contains(@class, 'item-post')]")
    ]

# Here are paths for comments in blogs:
# first goes path to container, second is a path for comments
COMMENTS_PATHS = [

    # Masks
    ("//div[contains(@id, 'comments')]", "//div[starts-with(@id, 'post')]"),

    ("//div[contains(@id, 'comments')]", "//li[(contains(@id, 'comment') and contains(@class, 'comment'))]"),
    ("//div[contains(@id, 'comments')]", "//div[(contains(@id, 'comment') and not(contains(@id, 'comments')) and contains(@class, 'comment') and not(contains(@class, 'comments')))]"),

    ("//div[contains(lower-case(@id), 'comments')]", "//li[contains(lower-case(@class), 'comment')]"),


    ("//div[contains(lower-case(@class), 'comments')]", "//li[contains(lower-case(@class), 'comment')]"),
    ("//div[contains(@class, 'Comments')]", "//li[contains(@class, 'Comment')]"),

    ("//div[contains(@id, 'comments')]", "//div[(contains(@id, 'wc-comm') and contains(@class, 'wc-comment'))]"),

    ("//div[contains(@id, 'comments')]", "//div[(contains(@id, 'comment') and not(contains(@id, 'form)))]"),

    ("//div[contains(@id, 'comments')]", "//div[contains(@id, 'post')]"),

    ("//div[contains(@id, 'commentArea')]", "//div[contains(@class, 'blogCommentWrap')]"),

    ("//section[contains(@id, 'conversation')]", "//li[(contains(@id, 'post') and contains(@class, 'post'))]"),  # Discuss comments?

    ("//section[contains(@id, 'comments')]", "//div[(contains(@id, 'comment') and contains(@class, 'comment'))]"),

    ("//div[contains(lower-case(@class), 'comments')]", "//div[contains(lower-case(@class), 'comment')]"),

    ("//ol[contains(@id, 'comments')]", "//li[(contains(@id, 'comment') and contains(@class, 'comment'))]"),

    ("//*[contains(lower-case(@class), 'comments')]", "//*[contains(lower-case(@class), 'comment')]"),

    ("//div[contains(@id, 'comments')]", "//div[contains(@class, 'comment-block')]"),

    ("//div[contains(@class, 'comments')]", "//div[contains(@class, 'comment')]"),

    ("//div[contains(@id, 'comments')]", "//table[contains(@class, 'comment')]"),  # tanyaburr.co.uk uses this

]


# regexp to fetch occurencies with number in front, like '123 Comments:'
comments_num_pre_regex = re.compile(
    "(?i)(?:(?:(?:(?:\d{1,3},?)*\d{3}?)|(?:\d+))[^\d\w]{0,5}(?:com{1,2}ent|kom{1,2}entar|pensamient|thought|response|antwort|(?:&nbsp)+)[^\n\r\t\s\d]*)"
)

# regexp to fetch occurencies with number at the end, like 'Comments (123):'
comments_num_post_regex = re.compile(
    "(?i)(?:(?:com{1,2}ent|kom{1,2}entar|pensamient|response|antwort|(?:&nbsp)+)[^\n\r\t\s\d]*[^\d\w]{0,5}\s+(?:(?:(?:\d{1,3},?)*\d{3}?)|(?:\d+)))"
)

# regexp to fetch occurencies with no comments, like 'No comments'
comments_no_regex = re.compile(
    "(?i)(?:(?:no)[^\n\r\t\s\d]*[^\d\w]{0,5}(?:com{1,2}ent|kom{1,2}entar|pensamient|response|antwort|(?:&nbsp)+)[^\n\r\t\s\d]*)"
)


class FetchBlogPostsManually(object):
    main_div_xpath = None
    post_content_xpath = None

    def __init__(self, post, main_div_xpath, post_content_xpath):
        self.main_div_xpath = main_div_xpath
        self.post_content_xpath = post_content_xpath
        self.post = post

    def fetch_content(self, to_save=False):
        """
        here, we use lxml to fetch the content and use the xpaths to check if we found full post content.
        """
        with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
            xb.load_url(self.post.url)
            content_div = xb.els_by_xpath(self.main_div_xpath + self.post_content_xpath)

            if content_div:
                log.info("Awesome, we got content")
                if len(content_div) > 1:
                    log.info("Hmmm, more than one elements found---shouldn't happen")
                content = content_div[0]
                html = content.get_attribute('innerHTML')
                log.info("Got content with %d length " % len(html))
                if to_save:
                    self.post.content = html
                    self.post.save()
                return True
        log.info("No content was received for %s usign [%s,%s]" % (self.post.url, self.main_div_xpath, self.post_content_xpath))
        return False


# these are classes, that are surely in classes of comment nodes
COMMENT_NODES_CLASSES = [
    "commenttable",
]

valid_node_tags = [
    'li',
    'div',
    'table',
    'p',
    # 'span',
    'dt',
    'dd']

    # def __init__(self, xb):
    #     self.xb = xb #rowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY)
    #     self.xb.driver.set_page_load_timeout(20)
    #     self.xb.driver.set_script_timeout(20)
    #     self.xb.driver.implicitly_wait(10)
    #
    #     # Compiled regexps were moved to init because on production it hanged on them
    #     # regexp to fetch occurencies with number in front, like '123 Comments:'
    #     self.comments_num_pre_regex = re.compile(
    #         # "(?i)((((\d{1,3},?)*\d{3}?)|(\d+))[^\d\w]{0,5}(com{1,2}ent|kom{1,2}entar|pensamient|response|antwort|(&nbsp)+)[^\n\r\t\s\d]*)"
    #         "(?i)(?:(?:(?:(?:\d{1,3},?)*\d{3}?)|(?:\d+))[^\d\w]{0,5}(?:com{1,2}ent|kom{1,2}entar|pensamient|response|antwort|(?:&nbsp)+)[^\n\r\t\s\d]*)"
    #     )
    #
    #     # regexp to fetch occurencies with number at the end, like 'Comments (123):'
    #     self.comments_num_post_regex = re.compile(
    #         # "(?i)((com{1,2}ent|kom{1,2}entar|pensamient|response|antwort|(&nbsp)+)[^\n\r\t\s\d]*[^\d\w]{0,5}(((\d{1,3},?)*\d{3}?)|(\d+)))"
    #         "(?i)(?:(?:com{1,2}ent|kom{1,2}entar|pensamient|response|antwort|(?:&nbsp)+)[^\n\r\t\s\d]*[^\d\w]{0,5}(?:(?:(?:\d{1,3},?)*\d{3}?)|(?:\d+)))"
    #     )
    #
    #     # regexp to fetch occurencies with no comments, like 'No comments'
    #     self.comments_no_regex = re.compile(
    #         # "(?i)((no)[^\n\r\t\s\d]*[^\d\w]{0,5}(com{1,2}ent|kom{1,2}entar|pensamient|response|antwort|(&nbsp)+)[^\n\r\t\s\d]*)"
    #         "(?i)(?:(?:no)[^\n\r\t\s\d]*[^\d\w]{0,5}(?:com{1,2}ent|kom{1,2}entar|pensamient|response|antwort|(?:&nbsp)+)[^\n\r\t\s\d]*)"
    #     )

# def get_comments_number_precise(url):
#     """
#     This helper function returns a number of comments from page by the following algorithm:
#     It fetches data from the function get_all_comments_number up to max_attempts times. If it gets 'regexp_match'
#     it returns result immediately. Otherwise it gets largest value returned from that three times
#     :param url:
#     :return: number of comments, method to obtain this number
#     """
#     max_attempts = 3
#     current_attempt = 0
#     results = []
#
#     while current_attempt < max_attempts:
#
#         xb.driver.set_page_load_timeout(10*(current_attempt+1))
#
#         num_comments, method = get_all_comments_number(url)
#         if method in ['regexp_match', 'href_#comments']:
#             xb.driver.set_page_load_timeout(20)
#             return num_comments, method
#         else:
#             results.append((num_comments, method))
#
#         current_attempt += 1
#
#     top_number_of_comments = -2
#     top_method = None
#     for num_comments, method in results:
#         if num_comments > top_number_of_comments:
#             top_number_of_comments = num_comments
#             top_method = method
#
#     xb.driver.set_page_load_timeout(20)
#     return top_number_of_comments, top_method



def get_all_comments_number(url, describe=False):
    """
    Calculates the number of comments for the particular url. Iterates over iframes too.
    :param url - url of the blog where to calculate comment number
    :param describe: - flag to print debug info
    :return: number of detected comments
    """
    COMMENTS_LIST_XPATH = """
        //div[
            (
                contains(translate(@id, 'ACEINORSTV', 'aceinorstv'), 'conversation')
            or
                contains(translate(@class, 'ACEINORSTV', 'aceinorstv'), 'conversation')
            or
                contains(translate(@class, 'CEMNOST', 'cemnost'), 'comments')
            or
                contains(translate(@id, 'CEMNOST', 'cemnost'), 'comments')
            or
                (
                    contains(translate(@class, 'CMO', 'cmo'), 'comm')
                and
                    contains(translate(@class, 'ILST', 'ILST'), 'list')
                )
            or
                (
                    contains(translate(@id, 'CMO', 'cmo'), 'comm')
                and
                    contains(translate(@id, 'ILST', 'ILST'), 'list')
                )
            )
        ]
        |
        //section[
            (
                contains(translate(@id, 'ACEINORSTV', 'aceinorstv'), 'conversation')
            or
                contains(translate(@class, 'ACEINORSTV', 'aceinorstv'), 'conversation')
            or
                contains(translate(@class, 'CEMNOST', 'cemnost'), 'comments')
            or
                contains(translate(@id, 'CEMNOST', 'cemnost'), 'comments')
            or
                (
                    contains(translate(@class, 'CMO', 'cmo'), 'comm')
                and
                    contains(translate(@class, 'ILST', 'ILST'), 'list')
                )
            or
                (
                    contains(translate(@id, 'CMO', 'cmo'), 'comm')
                and
                    contains(translate(@id, 'ILST', 'ILST'), 'list')
                )
            )
        ]
        |
        //ol[
            (
                contains(translate(@id, 'ACEINORSTV', 'aceinorstv'), 'conversation')
            or
                contains(translate(@class, 'ACEINORSTV', 'aceinorstv'), 'conversation')
            or
                contains(translate(@class, 'CEMNOST', 'cemnost'), 'comments')
            or
                contains(translate(@id, 'CEMNOST', 'cemnost'), 'comments')
            or
                (
                    contains(translate(@class, 'CMO', 'cmo'), 'comm')
                and
                    contains(translate(@class, 'ILST', 'ILST'), 'list')
                )
            or
                (
                    contains(translate(@id, 'CMO', 'cmo'), 'comm')
                and
                    contains(translate(@id, 'ILST', 'ILST'), 'list')
                )
            )
        ]
        |
        //ul[
            (
                contains(translate(@id, 'ACEINORSTV', 'aceinorstv'), 'conversation')
            or
                contains(translate(@class, 'ACEINORSTV', 'aceinorstv'), 'conversation')
            or
                contains(translate(@class, 'CEMNOST', 'cemnost'), 'comments')
            or
                contains(translate(@id, 'CEMNOST', 'cemnost'), 'comments')
            or
                (
                    contains(translate(@class, 'CMO', 'cmo'), 'comm')
                and
                    contains(translate(@class, 'ILST', 'ILST'), 'list')
                )
            or
                (
                    contains(translate(@id, 'CMO', 'cmo'), 'comm')
                and
                    contains(translate(@id, 'ILST', 'ILST'), 'list')
                )
            )
        ]

    """

    num_comments = 0

    # before we do anything, we check the url for accessibility
    try:
        response = requests.get(url, timeout=10, headers=requests_headers)
        if response.status_code in [400, 404] or response.status_code >= 500:
            return -1, 'status_%s' % response.status_code
        if response.status_code == 403:
            # checking out 'squarespace captcha page'
            if 'recaptcha' in response.content and 'squarespace' in response.content:
                return -1, 'captcha_squarespace'
    except Timeout:
        return -1, 'status_timeout'
    except ConnectionError:
        return -1, 'connection_error'

    # First, we try to find comments number by regular expression within the page and all iframes.
    # We store result, iframe and tag info (if results are found) to return number for result with
    # the greatest font size because it can be taken from some ad.
    try:
        with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                               disable_cleanup=False,
                               load_no_images=True) as xb:

            xb.driver.set_page_load_timeout(60)
            xb.driver.set_script_timeout(60)
            xb.driver.implicitly_wait(10)

            try:
                # print('* Loading url...')
                # xb.load_url(url)
                xb.driver.get(url)
            except Exception as e:
                print('Exception while loading page and performing scripts: %s' % e)

            # print('* Url loaded...')

            # sending script to stop loading
            # xb.driver.execute_script("window.stop();")

            # wait until scripts perform
            time.sleep(2)
            try:
                # print('* Getting page source...')
                ps = xb.driver.page_source
                # print('* Got page source...')
                initial_page = fromstring(ps)
                # print('* Got lxml tree...')
            except ValueError:
                return -1, 'valueerror_getting_page'

            # checking for <a href="posturl/#comments">num</a> on page for a number of comments
            page = initial_page
            nodes = page.xpath("//a[@href='%s#comments']/text()" % url)
            if nodes:
                for node in nodes:
                    num_comments = re.findall(r'[\d,]+', node)
                    if len(num_comments) > 0:
                        return num_comments[0].replace(',', ''), 'href_#comments'

            # Trying just to fetch something like "Comments (%d)" on a page with regexps
            have_got_results = False

            # flag showing that this value of max_font_size has been already met while checking
            is_doubled = False

            # maximum font size found for positive match
            max_font_size = 0.0

            # maximum quantity of comments
            max_qty = 0

            nodes = fetch_qty_by_regexp(xb)
            for node in nodes:
                have_got_results = True
                if node.get('font_size', 0.0) == max_font_size and max_qty != node.get('comments', 0):
                    is_doubled = True
                elif node.get('font_size', 0.0) > max_font_size:
                    is_doubled = False
                    max_qty = node.get('comments', 0)
                    max_font_size = node.get('font_size')

            iframes = xb.driver.find_elements_by_tag_name('iframe')
            if len(iframes) > 0:
                for iframe in iframes:
                    # performing iframe
                    # try:
                    nodes = fetch_qty_by_regexp(xb, iframe)
                    for node in nodes:
                        have_got_results = True
                        if node.get('font_size', 0.0) == max_font_size and max_qty != node.get('comments', 0):
                            is_doubled = True
                        elif node.get('font_size', 0.0) > max_font_size:
                            is_doubled = False
                            max_qty = node.get('comments', 0)
                            max_font_size = node.get('font_size')

                    # except Exception as e:
                    #     print('Skipping this iframe due to exception: %s' % e)

            # print('Has results: %s   is_doubled: %s' % (have_got_results, is_doubled))

            if have_got_results and not is_doubled:
                return max_qty, 'regexp_match'

            # checking for rss feed for comments
            # If it has <item></item> tags and their quantity is less than 10, then state it as the number of comments
            try:
                response = requests.get("%s%sfeed" % (url, '' if url.endswith('/') else '/'),
                                        timeout=5,
                                        headers=requests_headers)
                if response.status_code == 200:
                    page = fromstring(response.content)
                    nodes = page.xpath('.//item')
                    if len(nodes) < 10:
                        return len(nodes), 'comments_feed'
                    else:
                        return -1, 'comments_feed'
            except Timeout:
                pass

            # checking for blogspot
            blogspot_urls = initial_page.xpath("//link[re:test(@href, 'feeds\/\d+\/comments\/default')]/@href",
                                               namespaces={'re': 'http://exslt.org/regular-expressions'})
            # print('blogspot urls: %s' % blogspot_urls)
            if blogspot_urls:
                try:
                    response = requests.get(blogspot_urls[0], timeout=5, headers=requests_headers)
                    if response.status_code == 200:
                        pg = document_fromstring(response.content)
                        nodes = pg.xpath('//totalresults/text()')
                        if nodes:
                            return nodes[0], 'comments_opensearch'
                except Timeout:
                    pass

            return -1, 'none_matched'

            # TODO: Now we are not interested in probability part, so return -1 if not found by previous steps
            # print('Regex did not get results, performing by probability...')

            xb.driver.switch_to_default_content()

            # html page
            ps = xb.driver.page_source
            page = document_fromstring(ps)

            comments_nodes = page.xpath(COMMENTS_LIST_XPATH)

            if describe:
                print('Got %s comments nodes' % len(comments_nodes))

            for node in comments_nodes:
                num_comments += get_node_comments_number(node, page, describe=describe)
                if num_comments != 0:
                    return num_comments, 'probability'

            if num_comments == 0:  #  True:  # len(comments_nodes) == 0:  # do not look in iframes for comments if we have them in base doc?
                iframes = xb.driver.find_elements_by_tag_name('iframe')
                if len(iframes) > 0:
                    # print('Comments not yet found but we have %s iframes here, let\'s check them...' % len(iframes))

                    for iframe in iframes:

                        # switching to iframe
                        try:
                            xb.driver.switch_to_default_content()
                            xb.driver.switch_to_frame(iframe)

                            page_source = xb.driver.page_source
                            page = document_fromstring(page_source)

                            comments_nodes += page.xpath(COMMENTS_LIST_XPATH)

                            for node in comments_nodes:
                                num_comments += get_node_comments_number(node, page, describe=describe)

                                if num_comments != 0:
                                    return num_comments, 'probability'
                        except Exception as e:
                            print('Skipping this iframe due to exception: %s' % e)

    except Exception as e:
        log.exception(e, extra={'url': url})

    return num_comments, 'probability'

def get_node_comments_number(container_node, page, describe=False):
    """
    Gets a number of comments nodes from particular 'container' node.
    :param container_node:  - node, which is considered to be a container, or root for comments.
    :param page: - node of the whole parent page
    :param describe: - flag to print debug info
    :return: number of detected comments
    """

    ctr = 0
    num_comments = 0

    if describe:
        print('**************************************')
        print('Performing a Container Node:')
        print('Tag: %s' % container_node.tag)
        print('Type: %s' % type(container_node))
        print('Id: %s' % container_node.get('id'))
        print('Class: %s' % container_node.get('class'))
        print('Has parent: %s' % container_node.getparent().tag)
        print('Has children: %s' % len(container_node.getchildren()))
        print('Depth: %s' % depth(container_node))
        print('**************************************')

    # manually check if Discuss
    if container_node.tag == 'section' and container_node.get('id') == 'conversation':
        return len(container_node.xpath("..//li[(@class='post' and contains(@id, 'post'))]"))

    # iterating child nodes to find similar ones
    # Looking over their classes (similar classes values can point us to comments)

    # I. First, getting data about nodes disposition
    disposition = {}
    perform_node(container_node, disposition, describe=describe)

    if describe:
        print(disposition)

    # II. Searching for nodes that can be determinated as nodes of comments
    # trying the most simple way for experiment: count the highest quantity of tags

    variants = {}
    nodes_for_better_probabilities = {}
    top_probability = 50

    for node_tag in valid_node_tags:
        node_disposition = disposition.get(node_tag, None)

        if describe:
            print('* * * TAG: %s * * *' % node_tag)

        if node_disposition:
            top_qty_for_tag = 0

            for level, class_list in sorted(node_disposition.items()):

                if describe:
                    print('------------------------')
                    print('Level: %s, has %s class groups' % (level, len(class_list)))
                for class_group in class_list:
                    if describe:
                        print('  * class group: %s, tags on this level: %s, probability: %s' % (
                            class_group['class'],
                            class_group['qty'],
                            class_group['prob']))
                    if class_group['qty'] in variants:
                        variants[class_group['qty']] += 1
                    else:
                        variants[class_group['qty']] = 1

                    if class_group['prob'] > 50:
                        if class_group['class']:
                            if class_group['prob'] not in nodes_for_better_probabilities:
                                nodes_for_better_probabilities[class_group['prob']] = []
                            nodes_for_better_probabilities[class_group['prob']].append({'tag': node_tag,
                                                                                        'class': class_group['class']})
                            if class_group['prob'] > top_probability:
                                top_probability = class_group['prob']

    if nodes_for_better_probabilities:
        # print('nodes of top probabilities: %s' % nodes_for_better_probabilities)

        nodes = nodes_for_better_probabilities[top_probability]

        xpath_expression = " | ".join(["//%s[contains(@class, '%s')]" % (node['tag'], node['class']) for node in nodes])
        comment_nodes = page.xpath(xpath_expression)

        if describe:
            print('Return by probabilities...')

        return len(comment_nodes)

    # III. Counting variants
    # if describe:
    #     print('Variants: %s' % variants)
    #
    # top_key, top_value = 0, 0
    # for key, value in variants.items():
    #     if value > top_value and key != top_key and key != 1:
    #         top_key, top_value = key, value
    #         num_comments = top_key

    # return comment_node
    return num_comments

def perform_node(node, result, is_child=False, describe=False):
    """
    Processes given node and updates result dictionary in the form of:

    {'div': {5: [{'class': 'comment', 'qty': 1}], ...}, 'li': {7: [{'class': 'comment2', 'qty': 5}], ... }

    Here, 'div' is the tag, encountered in the node, is a key for a dict of levels,
    each of them contains information about divs of the 'class' classes, encountered 'qty' times.

    Also probability is calculated for each node. Some conditions increase that probability, some of them decrease.
    """

    node_tag = node.tag
    node_depth = depth(node)
    node_class = node.get('class')

    perform_children = True

    # This flag shows that this node is the most upper with a single avatar tag inside his children
    # Improved predictability of nodes for comments: looking for avatar or Reply button in tags
    # TODO: look on similarity of tag classes
    # is_upper_with_existing_avatar = False

    # put valid tags info to result
    if node_tag in valid_node_tags and node_class is not None:

        # "prob" -- probability of being a node for comment, default is 50
        # increase or decrease it with certain checks
        prob = 50

        has_avatar, is_top_tag_for_avatar = check_node_for_avatar(node)

        has_reply, is_top_tag_for_reply = check_node_for_reply(node)

        has_inputs = check_node_for_inputs(node)

        has_text = check_node_for_text(node)

        if has_avatar:
            prob += 20
        if is_top_tag_for_avatar:
            prob += 30

        if has_reply:
            prob += 10
        if is_top_tag_for_reply:
            prob += 15

        # Li tag with text is definitely a comment
        if node_tag == 'li' and is_child and has_text:  # Todo: find that this li is above of others of them all
            prob = 150

        # Not reliable
        # if 'comment' in node_class or 'comment' in node.get('id', ""):
        #     prob += 5

        # these are classes, that are surely in classes of comment nodes
        if any([cnc in node_class for cnc in COMMENT_NODES_CLASSES]) and 'comments' not in node_class:
            prob += 5

        # Comments have text
        if describe:
            print('<%s class="%s"> has text: %s' % (node_tag, node_class, has_text))
        if not has_text:
            prob -= 100

        # Comments do not have inputs
        if has_inputs:
            prob -= 125

        # The most top node, container of comments can not be comment itself.
        if not is_child:
            prob = -150

        # Distinctive JS plugin divs lowering prob (Masonry, for example), they are NOT comments
        if node.tag == 'div' and 'masonry' in node_class.split():
            prob = -150
            perform_children = False

        # Distinctive classes ('pingback', ...), that are not counted for comments
        if 'pingback' in node_class.split():
            prob = -150
            perform_children = False

        if node_tag in result and node_depth in result[node_tag] and prob >= 50:
            similar_tags = result[node_tag][node_depth]

            # checking tags for similarity or is it a new tag
            is_new = True
            for similar_tag in similar_tags:

                if describe:
                    print('Node_class %s  VS  similar_tag_class %s  Similarity: %s' % (node_class,
                                                                                       similar_tag['class'],
                                                                                       0))

                # if similar, then increase qty
                if similar_tag['class'] == node_class:
                    similar_tag['qty'] += 1
                    is_new = False

                    # check if probability changed
                    if prob > similar_tag['prob']:
                        similar_tag['prob'] = prob

                    break

            # appending if it is new one
            if is_new and node_class is not None:
                result[node_tag][node_depth].append({'class': node_class, 'qty': 1, 'match': 'full', 'prob': prob})

        else:
            if node_tag not in result:
                result[node_tag] = {}
            if node_depth not in result[node_tag]:
                result[node_tag][node_depth] = []
            result[node_tag][node_depth].append({'class': node_class, 'qty': 1, 'match': 'full', 'prob': prob})

    if perform_children:
        children = node.getchildren()

        for child_node in children:
            perform_node(child_node, result, is_child=True, describe=False)


def depth(node):
    """
    Returns depth of the node in the context of the page.
    :param node: node to perform
    :return: level of depth
    """
    d = 0
    while node is not None:
        d += 1
        node = node.getparent()
    return d


def check_node_for_avatar(node):
    """
    This method checks if this tag is the most top tag in tree which has a single avatar sibling inside.
    has_avatar_in_children -- this is a flag showing that ONE avatar node presents inside the children xpath
    is_top_tag_for_avatar -- this is a flag showing that this tag is the top one having underlying avatars in it
        (it is not a container tag for comments)
    """
    # print('Searching avatar children for <%s class="%s">' % (node.tag, node.get('class')))
    has_avatar_in_children, is_top_tag_for_avatar = False, False
    children_avatar_nodes = node.xpath(".//img[(contains(@class, 'ava') or contains(@src, 'ava') or contains(@id, 'ava') or contains(@alt, 'ava'))] | .//div[(contains(@class, 'avatar') or contains(@id, 'avatar'))]")
    # print('children_avatar_nodes : %s' % children_avatar_nodes)
    if len(children_avatar_nodes) == 1:
        has_avatar_in_children = True
    if has_avatar_in_children and len(node.getparent().xpath(".//img[(contains(@class, 'ava') or contains(@src, 'ava') or contains(@id, 'ava') or contains(@alt, 'ava'))] | .//div[(contains(@class, 'avatar') or contains(@id, 'avatar'))]")) > 1:
        is_top_tag_for_avatar = True
    return has_avatar_in_children, is_top_tag_for_avatar


def check_node_for_reply(node):
    """
    This method checks if this tag is the most top tag in tree which has a single avatar sibling inside.
    has_reply_in_children -- this is a flag showing that ONE reply button node presents inside the children xpath
    is_top_tag_for_reply -- this is a flag showing that this tag is the top one having underlying reply buttons in it
        (it is not a container tag for comments)
    """
    # print('Searching reply children for <%s class="%s">' % (node.tag, node.get('class')))
    has_reply_in_children, is_top_tag_for_reply = False, False
    children_reply_nodes = node.xpath(".//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reply')]")
    # print('children_reply_nodes : %s' % children_reply_nodes)
    if len(children_reply_nodes) == 1:
        has_reply_in_children = True
    if has_reply_in_children and len(node.getparent().xpath(".//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reply')]")) > 1:
        is_top_tag_for_reply = True
    return has_reply_in_children, is_top_tag_for_reply


def check_node_for_inputs(node):
    """
    This method checks if this node has inputs or textareas for entering text/comments in its children.
    has_forms -- this is a flag showing that there are input or textarea tags in this node's children
    """
    # print('Searching input or textarea in children for <%s class="%s">' % (node.tag, node.get('class')))
    has_inputs = False
    children_inputs = node.xpath(".//input | .//textarea")
    # print('children_inputs_nodes : %s' % children_inputs)
    if len(children_inputs) > 0:
        has_inputs = True
    return has_inputs


def check_node_for_text(node):
    """
    This method checks if this node has text in its TODO:deepest children.
        MUST: Except text in hrefs.

    It is a trait of commentaries that there is some text in a node.
    has_text -- this is a flag showing that there is a text in the deepest nodes.
    """
    # print('Searching input or textarea in children for <%s class="%s">' % (node.tag, node.get('class')))
    has_text = False

    if len(node.text_content().split()) > 0:
        has_text = True
    return has_text


def fetch_qty_by_regexp(xb, iframe=None):
    """
    Returns a list of comment numbers and their text size
    :param iframe -- identifier of iframe being performed or None for main HTML
    :return:
    """

    # print('* Start executing method...')

    # nodes with discriptors, containing data and qty
    # Example: [{'tag': 'div', 'id': 'comments-ctr', 'class': 'comments-num', 'qty': 10}, ... ]
    nodes = []

    # Setting context to the iframe we perform
    iframe_location = {'x': 0, 'y': 0}
    if iframe:
        try:
            iframe_location = iframe.location
        except Exception:
            pass
        xb.driver.switch_to_frame(iframe)

    # print('* Location calculated and Iframe switched to...')

    ps = xb.driver.page_source
    page = fromstring(ps)

    # print('* Page fetched from document...')

    # excluding scripts and head tags
    exclude = page.xpath('//*[self::head or self::script or self::style]')
    for exc in exclude:
        parent = exc.getparent()
        if parent is not None:
            parent.remove(exc)

    # print('* <script> and <head> tags are removed...')

    # excluding HTML comments from page
    exclude = page.xpath('//comment()')
    for exc in exclude:
        parent = exc.getparent()
        if parent is not None:
            parent.remove(exc)

    # print('* Commented out html text is removed...')

    page_raw_text = get_page_raw_text(page)

    # print('* Raw text from page before cleaning urls...')
    # print(page_raw_text)

    # cleaning raw text of occasionally href="..." and src="..."
    chunks = page_raw_text.split()
    page_raw_text = ''
    for chunk in chunks:
        if chunk.lower().startswith('src='):
            page_raw_text = page_raw_text + ' ' + 'src="#"'
        elif chunk.lower().startswith('href='):
            page_raw_text = page_raw_text + ' ' + 'href="#"'
        else:
            page_raw_text = page_raw_text + ' ' + chunk

    # print('* Raw text from page is fetched...')
    # print(page_raw_text)

    comments_qty_pre_texts = re.finditer(comments_num_pre_regex, page_raw_text)
    # print('* 1st iterator obtained...')
    comments_qty_post_texts = re.finditer(comments_num_post_regex, page_raw_text)
    # print('* 2nd iterator obtained...')
    comments_qty_no_texts = re.finditer(comments_no_regex, page_raw_text)
    # print('* 3rd iterator obtained...')

    distinct_text_matches = []
    for cqt in itertools.chain(comments_qty_pre_texts, comments_qty_post_texts, comments_qty_no_texts):
        if cqt.group(0) not in distinct_text_matches:
            distinct_text_matches.append(cqt.group(0))
    # print('* Distinct text matches found...')

    for dtm in distinct_text_matches:
        # print('* Searching for group: %s' % dtm)

        nodes_with_text = page.xpath('.//*[contains(text(), "%s")]' % dtm.split('"')[0])
        # print('* Found %s nodes with this text: %s' % (len(nodes_with_text), dtm))

        # checking if the text of number and comments is in one node or in different
        if len(nodes_with_text) > 0:
            # print('All right, found them!')
            for node_with_text in nodes_with_text:
                # print('  <%s id="%s" class="%s">' % (node_with_text.tag,
                #                                      node_with_text.get('id'),
                #                                      node_with_text.get('class')))

                qty_text = None
                for regex in [comments_num_pre_regex, comments_num_post_regex, comments_no_regex]:
                    qty_text = re.search(
                        regex,
                        get_page_raw_text(node_with_text)
                    )
                    if qty_text is not None:
                        break

                if qty_text is not None:
                    # print('qty_text: %s' % qty_text.group(0))
                    num_comments_txt = re.findall(r'[\d,]+', qty_text.group(0))
                    # print('  * NUM COMMENTS TXT: %s' % num_comments_txt)
                    if num_comments_txt:
                        num_comments = int(num_comments_txt[0].replace(',', ''))
                    else:
                        num_comments = 0
                    # print('  * NUM COMMENTS: %s' % num_comments)

                    # print('css-selector: %s' % css_selector)
                    font_size = 0.0

                    chunks = qty_text.group(0).split('"')
                    contains_text_chain_xpath = ' and '.join(['contains(text(), "%s")' % chunk for chunk in chunks])
                    node_xpath = '[%s%s%s]' % (
                        contains_text_chain_xpath,
                        ' and (@id="%s")' % node_with_text.get('id') if node_with_text.get('id') is not None else '',
                        ' and (@class="%s")' % node_with_text.get('class') if node_with_text.get('class') is not None else '',
                    )
                    # print('  node_xpath : %s' % node_xpath)

                    element_xpath = './/%s%s' % (node_with_text.tag, node_xpath)
                    # print('FETCH XPATH: %s' % element_xpath)
                    selenium_element = xb.driver.find_element_by_xpath(element_xpath)
                    location = selenium_element.location
                    # print('Element location: %s  Iframe location offset: %s' % (location, iframe_location))
                    if location['y'] + iframe_location['y'] >= 250:
                        font_size_txt = selenium_element.value_of_css_property("font-size")
                        if font_size_txt:
                            font_size = float(font_size_txt.replace('px', ''))

                            # print('Font size: %s' % font_size)

                        nodes.append({
                            'tag': node_with_text.tag,
                            'id': node_with_text.get('id'),
                            'class': node_with_text.get('class'),
                            'comments': num_comments,
                            'font_size': font_size
                        })

        # seems it is in different nodes
        else:
            # print('* Seems it is across several tags...')
            # In this case we find all nodes that contain the number part and check for
            # comment-word part in the vicinity of it

            # getting number part and comment part
            num_part = re.findall(r'(?i)([\d,]+|(no)[^\n\r\t\s\d]*)', dtm)[0][0]
            # print("* cqt_group: '%s'" % dtm)
            # print("* num_part: '%s'" % num_part)

            cmt_part = dtm.replace(num_part, '').strip()
            # this flag shows if num part is at the beginning or end
            begins_with = dtm.startswith(num_part)

            # print("Splitted: num: '%s' cmnt: '%s', begins_with: %s" % (num_part, cmt_part, begins_with))

            # Now finding all tags containing that number expressions
            regexpNS = 'http://exslt.org/regular-expressions'
            num_nodes = page.xpath('.//*[re:test(text(), "^(%s)$")]' % num_part, namespaces={'re': regexpNS})
            # print ('have found num nodes: %s' % len(num_nodes))

            # checking each of them for a comment node in a vicinity
            positive_nodes = []
            for num_node in num_nodes:

                if begins_with:
                    parent = num_node.getparent()

                    prev_was_num = False
                    for node_text in parent.itertext():
                        # print(' --> checking: "%s"  , prev_was_num: "%s"' % (node_text.strip(), prev_was_num))
                        if prev_was_num:
                            if cmt_part in node_text:
                                # Got it!
                                # print('FOUND!: %s precedes %s' % (num_part, cmt_part))
                                positive_nodes.append(num_node)
                                break
                        if node_text.strip().startswith(num_part):
                            prev_was_num = True
                        else:
                            prev_was_num = False

                    # additional check of text in node, following the number node if it does not have text after it
                    # example:
                    # <span class="comment-count">31</span>
                    # <span class="comment-title">Comments</span>
                    if (num_node and num_node.tail is None) or (num_node is not None and num_node.tail is not None and len(num_node.tail.strip()) == 0):
                        next_sibling = num_node.getnext()
                        if next_sibling and next_sibling.text is not None and next_sibling.text.strip().startswith(cmt_part):
                            # print('FOUND!: "%s" precedes "%s" in two separate tags' % (num_part, cmt_part))
                            positive_nodes.append(num_node)
                else:
                    parent = num_node.getparent()

                    prev_was_cmt = False
                    for node_text in parent.itertext():
                        # print(' --> checking: "%s"  , prev_was_cmt: "%s"' % (node_text.strip(), prev_was_cmt))
                        if prev_was_cmt:
                            if num_part in node_text:
                                # Got it!
                                # print('FOUND!: "%s" follows "%s"' % (num_part, cmt_part))
                                positive_nodes.append(num_node)
                                break
                        if node_text.strip().startswith(cmt_part):
                            prev_was_cmt = True
                        else:
                            prev_was_cmt = False

                    # additional check of text in node, preceeding the number node if it does not have text after it
                    # example:
                    # <span class="comment-title">Comments:</span>
                    # <span class="comment-count">31</span>
                    prev_sibling = num_node.getprevious()
                    if (prev_sibling is not None and prev_sibling.tail is None) or (num_node is not None and num_node.tail is not None and len(num_node.tail.strip()) == 0):
                        if prev_sibling.text is not None and prev_sibling.text.strip().endswith(cmt_part):
                            # print('FOUND!: %s follows %s in two separate tags' % (num_part, cmt_part))
                            positive_nodes.append(num_node)

            if len(positive_nodes) > 0:
                for positive_node in positive_nodes:
                    node_xpath = './/%s[starts-with(text(), "%s")%s%s]' % (
                        positive_node.tag,
                        num_part,
                        ' and (@id="%s")' % positive_node.get(
                            'id') if positive_node.get('id') is not None else '',
                        ' and (@class="%s")' % positive_node.get(
                            'class') if positive_node.get('class') is not None else '',
                    )

                    font_size = 0.0
                    selenium_element = xb.driver.find_element_by_xpath(
                        node_xpath
                    )

                    location = selenium_element.location
                    # print('Element location: %s  Iframe location offset: %s' % (location, iframe_location))
                    if location['y'] + iframe_location['y'] >= 250:
                        font_size_txt = selenium_element.value_of_css_property("font-size")
                        if font_size_txt:
                            font_size = float(font_size_txt.replace('px', ''))
                            # print('FONT SIZE: %s' % font_size)

                        try:
                            num_comments = int(num_part.replace(',', ''))
                        except ValueError:
                            num_comments = 0

                        nodes.append({
                            'tag': positive_node.tag,
                            'id': positive_node.get('id'),
                            'class': positive_node.get('class'),
                            'comments': num_comments,
                            'font_size': font_size
                        })

    # returning context back from iframe
    if iframe:
        xb.driver.switch_to_default_content()

    # print('* NODES: %s' % nodes)

    return nodes


def check_nodes_for_plain_structure(comment_nodes):
    """
    This method checks if this node is plain (not tree-structured), and if it is plainstructured like:

        <div class="comments">
            <div class="comment-head>User 1 wrote:</div>
            <div class="comment-body>Comment1</div>
            <div class="comment-head>User 2 wrote:</div>
            <div class="comment-body>Comment2</div>
            ...
        </div>

    The quantity of nodes must be the same.
    """
    # TODO: not complete method
    is_plain, is_common_for_all = False, False

    # checking the quantity of nodes if it is equal for all
    classes = {}
    for node in comment_nodes:
        if node.get('class') in classes:
            classes[node.get('class')] += 1
        else:
            classes[node.get('class')] = 1

    qty = -1
    for key, val in classes.items():
        if val != qty and qty < 0:
            qty = val
        if val != qty:
            return is_plain, is_common_for_all

    return is_plain, is_common_for_all


def get_page_raw_text(page):
    """
    This method gets text from page's nodes and joins it with SPACES between the text.
    It is needed because lxml's method .text_content() concatenates the text without spaces and we get stuff
    like '7 CommentsSortBy' instead of '7 Comments Sort By' when the text is in different tags.
    """
    text_chunks = get_node_text(page)
    text = ' '.join([' '.join(tc.split()) for tc in text_chunks])
    return text


def get_node_text(node):
    chunks = []

    # first, append node's own text
    if node.text:
        chunks.append(node.text)

    # then perform its children and their tails
    for child in node.iterchildren():
        chunks = chunks + get_node_text(child)

    if node.tail:
        chunks.append(node.tail)

    return chunks


def get_element_depth(node):

    if node.parent:
        return get_element_depth(node.parent) + 1
    else:
        return 0



def get_comments_number(url):

    result = None

    # Using Selenium Webdriver to get content
    with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
        xb.load_url(url)

        # iterating over xpath list of masks to get nodes with comments
        for path in COMMENTS_PATHS:
            comment_nodes_qty = len(xb.els_by_xpath(path[0] + path[1]))
            if comment_nodes_qty > 0:
                return comment_nodes_qty
    return result


def fetch_content(post, to_save=False):
    log.info("Fetching content for %s" % post)
    for p in path_lists:
        f = FetchBlogPostsManually(post, p[0], p[1])
        if f.fetch_content(to_save):
            break

def check_xpaths_exists_in_url(url):
    """
    Used by contentclassification.py to check if the url is a blog
    We check for well known xpaths to make sure the blog is correctly detected
    """
    import requests
    from xpathscraper import utils
    import lxml

    try:
        r = requests.get(url, headers=utils.browser_headers())
        tree = lxml.html.fromstring(r.content)
    except:
        return False

    for p in path_lists:
        try:
            main = p[0]
            div = p[1]
            path = main + div
            print("Checking path %s" % path)
            el = tree.xpath(path)
            if len(el) > 0:
                print("found %d elements, success!" % len(el))
                return True
        except:
            pass
    print("Sorry, no xpath found, Failed!")
    return False


def test_urls():
    urls = ("http://littlefrenchworld.com/concours-musestyle-x-topshop",
    "http://fashiioncarpet.com/wordpress/deutsche-fashionblogger-kopierte-styles-verlorene-individualitaet/",
    "http://www.stylingo.co.uk/battle-of-the-primers-smashbox-vs-maxfactor/",
    "http://anythingforthecrown.com/winter-wanderlust-ojai/#more-1095",
    "http://zoejoyxoxo.com/dressing-keira-knightley-for-the-oscars/",
    "http://refunkmyjunk.com/paint-bar-monthly-market/",
    "http://www.inhershoesblog.com/5-essential-gadgets-need-life-right-now",
    "http://anywayitsus.com/2014/11/25/maxidress-me/",
    "http://www.glitterglossgarbage.com/gel-alternatives-opi-infinite-shine-vs-fingerpaints-endless-wear/",
    "http://kimkaylan.com/those-days/",
    "http://www.mrfoxtrot.com/look-61-2/",
    "http://simple-et-chic.de/todays-outfit/backpack-chic/",
    "http://bestfriendsforfrosting.com/2015/02/perfect-valentines-day-manicure-julep/",
    "http://www.frenchweddingstyle.com/",
    "http://www.sassymomsinthecity.com/",
    "http://www.eclectic-magazine.com/shadows-lydia-ainsworth/",
    )
    for u in urls:
        post = Posts.objects.filter(url=u)
        if post.count() >= 1:
            post = post[0]
            fetch_content(post)


from debra.elastic_search_helpers import es_influencer_query_runner_v2

def test_first_hundred_posts_count():

    # getting X top influencers ids
    _, influencers_ids, total = es_influencer_query_runner_v2({}, 450, 0)
    print('Influencers\' ids: %s' % influencers_ids)

    # Get one post for each
    ctr = 0
    for influencer_id in influencers_ids:

        try:
            post = Posts.objects.filter(influencer__id=influencer_id,
                                        platform__platform_name__in=['Blogspot', 'Wordpress', 'Custom'])[0]
            print('%s' % post.url)
            # print('Post url: %s  platform: %s' % (post.url, post.platform.platform_name))
            print('Seems it has %s, %s comments' % get_all_comments_number(post.url))
            # print('Seems it has %s comments' % cf.get_all_comments_number(post.url))
            print('--------------------------')
            ctr += 1
            if ctr >= 200:
                break
        except Exception as e:
            print('No blog posts found for Blogspot, Wordpress or Custom platforms.')
            print(e)
            print('--------------------------')


def test_10_times():

    counter = 0
    while counter < 10:
        test_get_top()
        time.sleep(120)
        counter += 1


def test_get_top():

    # with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
    #                        disable_cleanup=False,
    #                        load_no_images=True) as xb:
    #     cf = CommentsFetcher(xb)

    urls = [
        # "http://www.theskinnyfork.com/blog/stubbs-giveaway?rq=Stubb%27s",
        # "http://newhope360.com/what-stock/unboxed-13-new-natural-meal-starters-convenience-foods#slide-0-field_images-1249511",
        # "http://insidetailgating.com/blog/2015/08/21/stubbs-bbq-chicken-dip/",
        # "https://justkeeplivin.com/index.php/blog/best-bbq.html",
        # "http://grillgirl.com/2015/08/sriracha-skirt-steak-empanadas/",

        # "http://www.theskinnyfork.com/blog/stubbs-giveaway?rq=Stubb%27s",
        # "http://www.theskinnyfork.com/blog/cheesy-spinach-verde-enchiladas?rq=Stubb%27s",
        # "http://www.kitchen-concoctions.com/2015/08/grilled-steak-with-corn-and-green-chile.html",
        # "http://www.theskinnyfork.com/blog/sriracha-meatballs?rq=Stubb%27s",

        # "http://www.theskinnyfork.com/blog/cheesy-spinach-verde-enchiladas?rq=Stubb%27s",
        # "http://www.theskinnyfork.com/blog/sriracha-meatballs?rq=Stubb%27s",
        # "http://unorthodoxepicure.com/2015/08/20/rv-chronicles-ive-done-salted-my-peanuts-with-my-tv-watching/",


        # 'https://www.thrillist.com/eat/austin/the-11-best-burgers-in-austin',
        # 'http://tastyquery.com/recipe/701222/the-best-bbq-chicken',
        # 'http://pelletsmokercooking.blogspot.ru/2015/08/smoked-chicken-with-butter-beans.html',
        # 'http://asunshinyday.com/step-by-steps-on-making-a-kick-a-pulled-pork-on-the-smoker/',
        # 'http://www.theskinnyfork.com/blog/stubbs-giveaway?rq=Stubb%27s',
        # 'http://www.realsimple.com/food-recipes/shopping-storing/condiments-you-need',
        # 'http://unorthodoxepicure.com/2015/08/20/rv-chronicles-ive-done-salted-my-peanuts-with-my-tv-watching/',
        # 'http://www.bigflavorstinykitchen.com/2015/08/spice-rubbed-smoked-country-style-ribs-with-farm-fresh-veggie-saute.html',
        # 'http://www.peanutbutterandpeppers.com/2015/08/19/the-best-bbq-chicken/',
        # 'http://insidetailgating.com/blog/2015/08/21/stubbs-bbq-chicken-dip/',
        # 'http://goodtaste.tv/2015/08/kickin-sides-for-bbq/',
        # 'http://www.aspiringsmalltowngirl.com/2015/08/crockpot-ginger-ale-pulled-pork/',
        # 'http://www.kitchen-concoctions.com/2015/08/grilled-steak-with-corn-and-green-chile.html',
        # 'http://smokinstevesblog.com/2015/08/11/stubbs-charcoal-briquettes/',
        # 'http://workplacegourmet.blogspot.ru/2015/08/nutritional-introspection.html',
        # 'https://cupcakesandsequins.wordpress.com/2015/08/11/homemade-bbq-chicken-pizza/',
        # 'https://jensdish.wordpress.com/2015/08/14/pizza-on-the-porch/',
        # 'http://newhope360.com/what-stock/unboxed-13-new-natural-meal-starters-convenience-foods#slide-0-field_images-1249511',
        # 'http://thefitfork.com/recipe/hatch-salmon-cakes-recipe-green-chile-fish-dinners/',
        # 'http://www.wgy.com/onair/real-newsmen-wear-aprons-56511/cooking-sauce-13902886',
        # 'http://www.theskinnyfork.com/blog/cheesy-spinach-verde-enchiladas?rq=Stubb%27s',
        # 'https://wedishnutrition.wordpress.com/2015/08/10/healthy-bbq-gluten-free/',
        # 'http://www.havingfunsaving.com/2015/08/how-to-smoke-great-ribs.html',
        # 'http://www.ohio.com/lifestyle/food/new-in-food-stubb-s-sauces-for-marinating-basting-dipping-1.613303?localLinksEnabled=false',
        # 'https://justkeeplivin.com/index.php/blog/best-bbq.html',
        # 'http://www.sweetandsavoryfood.com/2015/08/5-crock-pot-meals-x-2-10-dinners.html',
        # 'http://www.skinnymom.com/skinny-hawaiian-chicken-cups/',
        # 'http://gothicgranola.com/2015/08/hippie-dippy-lentil-loaf/',
        # 'http://tasteologie.notcot.org/post/76036/New-Fashioned-Cowboy-Beans-Ribs-Hopalong-Cassidy-would-/',
        # 'http://tasteologie.notcot.org/post/77685/Cheesy-Texas-Sriracha-Hatch-Poppers-Is-it-an-appetizer-/',
        # 'http://verygoodrecipes.com/meatball',
        # 'http://unorthodoxepicure.com/2015/08/09/the-rv-chronicles-tighter-than-an-elephant-in-a-suitcase/',
        # 'http://www.theskinnyfork.com/blog/sriracha-meatballs?rq=Stubb%27s',
        # 'http://unorthodoxepicure.com/2015/08/24/the-rv-chronicles-missing-my-rock/',
        # 'http://www.dixiechikcooks.com/bacon-wrapped-mini-jalapeno-corn-muffins/',
        # 'http://www.nola.com/healthy-eating/2015/08/3-day_diet_healthy_to_help_she.html',
        # 'http://www.austinchronicle.com/daily/food/2015-08-12/hatch-chiles-are-here-again/',
        # 'http://www.sweetandsavoryfood.com/2015/08/sweet-thai-chili-meatballs-stubbs-bar-b.html',
        # 'http://www.cookingmaiway.com/2015/08/02/this-was-our-fourth-of-july/',
        # 'http://www.playboy.com/articles/grilling-season-bbq-sauces',
        # 'http://grillgirl.com/2015/08/sriracha-skirt-steak-empanadas/',
        # 'http://www.nibblemethis.com/2015/08/high-low-beef-filet-with-marsala.html',
        # 'http://www.emilybites.com/2015/08/bacon-bbq-cheeseburger-quesadillas.html',
        # 'http://www.tmbbq.com/a-few-more-influential-pitmasters/',
        # 'http://www.makandhercheese.com/bbq-shrimp-and-grits/',


        # 'http://www.onthebrightstyle.com/2014/12/7-holiday-gift-ideas.html',
        # 'http://jenniferslifee.blogspot.com/2014/12/my-daniel-wellington.html',
        # 'http://xannsplace.com/2014/12/27/all-i-got-for-christmas/',
        # 'http://www.styletraces.com/2014/12/orange-fur.html',
        # 'http://www.thestylefever.com/2014/12/outfit-beige-marrone-pantaloni-neri.html',
        # 'http://www.naag-notanaverageguy.com/2014/12/tik-tak.html',
        # 'http://www.mattgstyle.com/2014/12/dark-formality.html',
        # 'http://www.thestylefever.com/2014/12/orologio-daniel-wellington.html',
        # 'http://www.styletraces.com/2014/12/daniel-wellington-christmas.html',
        # 'http://itsmypassions.dk/sidste-chance-inden-jul/',
        # 'http://www.brunettebraid.com/2014/12/getting-ready-for-christmas.html',
        # 'http://nicoletothenines.blogspot.com/2014/12/black-white-and-red.html',
        # 'http://www.lifesetsail.com/2014/12/daniel-wellington-discount-theres-still.html',
        # 'http://annawii.blogg.se/2014/december/boho-details-2.html',
        # 'http://www.becauseshannasaidso.com/2014/12/leopard-plaid-print-mixing-fall-outfit-idea.html',
        # 'http://lifealwaysgoes.blogspot.com/2014/12/mypiecesatdialetu-daniel-weelington.html',
        # 'http://www.heidipetite.com/2014/12/portobello-blues.html',
        # 'http://www.brettrobson.com/2014/12/daniel-wellington-watch-discount-code.html',
        # 'http://catchmylook.blogspot.com/2014/12/daniel-wellington-iii.html',
        # 'http://www.apreppystateofmind.com/2014/12/gifts-for-him.html',
        # 'http://www.itspinkpot.com/2014/12/a-luxe-holiday-gift-guide-women.html',
        # 'http://www.artbymt.dk/my-faves-2/',
        # 'http://www.aniab.net/2014/12/holiday-gift-guide-2014.html',
        # 'http://paigearminta.com/2014/12/12/glamour-gels-giveaway/',
        # 'http://www.onthebrightstyle.com/2014/12/7-holiday-gift-ideas.html',
        # 'http://www.zatrzymujacczas.pl/porzadek-w-ubraniach-to-porzadek-w-zyciu/',
        # 'http://www.onthebrightstyle.com/2014/12/7-holiday-gift-ideas.html',
        # 'http://www.iamafashioneer.com/2014/12/neutrals.html',
        # 'http://catchmylook.blogspot.com/2014/12/daniel-wellington-iii.html',
        # 'http://paigearminta.com/2014/12/12/glamour-gels-giveaway/',
        # 'http://crystalinmarie.com/80-degree-temps-some-site-updates/',
        # 'http://emilysalomon.dk/2015/10/06/all-black/',
        # 'http://www.alterationsneeded.com/2015/10/pop-some-turquoise-in-your-burgundy.html',
        # 'http://www.miss-kindergarten.com/2015/10/rocksbox-jewelry.html',
        # 'http://happilyaudrey.com/2015/10/07/date-night-on-south-beach/',
        # 'http://lifestylebyjoules.com/fashion/outfits/pleated-knit-skirt',
        # 'http://www.preppyandposh.com/2015/10/moto-jeans-utility-vest.html',
        # 'http://www.pinoyguyguide.com/2015/09/happy-socks-colorful-socks-and-mens-printed-underwear.html',
        # 'http://www.mightytravels.com/2015/10/jetblue-deals-for-halloween-travel-31-one-way-amazing-sale-today-only/',
        # 'http://onemileatatime.boardingarea.com/2015/10/01/cheap-jetblue-fares/',
        # 'http://www.fashionrella.com/jetblue/',
        # 'http://levitate-style.tumblr.com/post/130474181778/levitate-style-one-year-anniversary-giveaway',
        # 'http://ny.racked.com/2015/10/2/9442065/the-tie-bar-pop-up-shop-nyc-fall-2015',
        # 'http://www.jessandjill.com/2015/09/the-tie-bar-love.html',
        # 'http://www.goldendivineblog.com/2015/09/my-favorite-fall-capes-under-100.html',
        # 'http://grechenscloset.com/outfit-alternative-organic/',
        # 'http://thriftylittles.com/2015/10/olivia-for-gymboree.html',
        # 'http://www.angiewagg.com/2015/10/honest-tea-giveaway.html',
        # 'http://fivelittlewords.net/2015/09/21/part-of-my-family-honest-tea-honest-kids-organic-drinks/',
        # 'http://www.smalltownrunner.com/2015/10/swiftwater-50k-race-recap-my-2nd.html',
        # 'http://ronisweigh.com/2015/09/what-i-ate-wednesday-was-what-he-cooked.html',
        # # "http://www.bestbeefjerky.org/2015/09/golden-island-jerky-sriracha-barbecue.html",


        # "http://www.onthebrightstyle.com/2014/12/7-holiday-gift-ideas.html",
        # "http://jenniferslifee.blogspot.com/2014/12/my-daniel-wellington.html",
        # "http://xannsplace.com/2014/12/27/all-i-got-for-christmas/",
        # "http://www.styletraces.com/2014/12/orange-fur.html",
        # "http://www.thestylefever.com/2014/12/outfit-beige-marrone-pantaloni-neri.html",
        # "http://www.naag-notanaverageguy.com/2014/12/tik-tak.html",
        # "http://www.mattgstyle.com/2014/12/dark-formality.html",
        # "http://www.thestylefever.com/2014/12/orologio-daniel-wellington.html",
        # "http://www.styletraces.com/2014/12/daniel-wellington-christmas.html",
        # "http://itsmypassions.dk/sidste-chance-inden-jul/",
        # "http://www.brunettebraid.com/2014/12/getting-ready-for-christmas.html",
        # "http://nicoletothenines.blogspot.com/2014/12/black-white-and-red.html",
        # "http://www.lifesetsail.com/2014/12/daniel-wellington-discount-theres-still.html",
        # "http://annawii.blogg.se/2014/december/boho-details-2.html",
        # "http://www.becauseshannasaidso.com/2014/12/leopard-plaid-print-mixing-fall-outfit-idea.html",
        # "http://lifealwaysgoes.blogspot.com/2014/12/mypiecesatdialetu-daniel-weelington.html",
        # "http://www.heidipetite.com/2014/12/portobello-blues.html",
        # "http://www.brettrobson.com/2014/12/daniel-wellington-watch-discount-code.html",
        # "http://catchmylook.blogspot.com/2014/12/daniel-wellington-iii.html",
        # "http://www.apreppystateofmind.com/2014/12/gifts-for-him.html",
        # "http://www.itspinkpot.com/2014/12/a-luxe-holiday-gift-guide-women.html",
        # "http://www.artbymt.dk/my-faves-2/",
        # "http://www.aniab.net/2014/12/holiday-gift-guide-2014.html",
        # "http://paigearminta.com/2014/12/12/glamour-gels-giveaway/",
        # "http://www.onthebrightstyle.com/2014/12/7-holiday-gift-ideas.html",
        # "http://www.zatrzymujacczas.pl/porzadek-w-ubraniach-to-porzadek-w-zyciu/",
        # "http://www.onthebrightstyle.com/2014/12/7-holiday-gift-ideas.html",
        # "http://www.iamafashioneer.com/2014/12/neutrals.html",
        # "http://catchmylook.blogspot.com/2014/12/daniel-wellington-iii.html",
        # "http://paigearminta.com/2014/12/12/glamour-gels-giveaway/",
        # "http://crystalinmarie.com/80-degree-temps-some-site-updates/",
        # "http://emilysalomon.dk/2015/10/06/all-black/",
        # "http://www.alterationsneeded.com/2015/10/pop-some-turquoise-in-your-burgundy.html",
        # "http://www.miss-kindergarten.com/2015/10/rocksbox-jewelry.html",
        # "http://happilyaudrey.com/2015/10/07/date-night-on-south-beach/",
        # "http://lifestylebyjoules.com/fashion/outfits/pleated-knit-skirt",
        # "http://www.preppyandposh.com/2015/10/moto-jeans-utility-vest.html",
        # "http://www.pinoyguyguide.com/2015/09/happy-socks-colorful-socks-and-mens-printed-underwear.html",
        # "http://www.mightytravels.com/2015/10/jetblue-deals-for-halloween-travel-31-one-way-amazing-sale-today-only/",
        # "http://onemileatatime.boardingarea.com/2015/10/01/cheap-jetblue-fares/",
        # "http://www.fashionrella.com/jetblue/",
        # "http://levitate-style.tumblr.com/post/130474181778/levitate-style-one-year-anniversary-giveaway",
        # "http://ny.racked.com/2015/10/2/9442065/the-tie-bar-pop-up-shop-nyc-fall-2015",
        # "http://www.jessandjill.com/2015/09/the-tie-bar-love.html",
        # "http://www.goldendivineblog.com/2015/09/my-favorite-fall-capes-under-100.html",
        # "http://grechenscloset.com/outfit-alternative-organic/",
        # "http://thriftylittles.com/2015/10/olivia-for-gymboree.html",
        # "http://www.angiewagg.com/2015/10/honest-tea-giveaway.html",
        # "http://fivelittlewords.net/2015/09/21/part-of-my-family-honest-tea-honest-kids-organic-drinks/",
        # "http://www.smalltownrunner.com/2015/10/swiftwater-50k-race-recap-my-2nd.html",
        # "http://ronisweigh.com/2015/09/what-i-ate-wednesday-was-what-he-cooked.html",
        # "http://www.modwedding.com/2015/10/31/charming-california-wedding-at-garre-winery/",
        # "http://www.sabragilbert.com/2015/10/sometimes-adulting-is-hard-photo-albums.html",
        # "http://www.inspiredbythis.com/dwell/copper-jewel-tone-thanksgiving/",
        # "http://jojotastic.com/2015/11/02/a-fall-fete-mulled-wine-old-fashioned/",
        # "http://pizzazzerie.com/courtney/9-ways-to-get-in-the-thanksgiving-spirit/",
        # "http://www.stylemepretty.com/living/2015/11/03/festive-fall-sangria/",
        # "http://inspiredbycharm.com/2015/11/diy-color-wrapped-wheat.html",
        # "http://www.abeautifulmess.com/2015/11/design-style-101-southwestern.html",
        # "http://centsationalgirl.com/2015/11/fireplace-makeover-tile-giveaway/",
        # "http://www.decoist.com/shower-curtain-trends/",
        #
        # "http://www.crazyfooddude.com/2015/10/review-vans-blissfully-berry-gluten.html",
        # "http://theglutenfreeawards.com/thanks-for-the-gluten-free-award-vote/",
        # "http://www.positivelysplendid.com/2015/11/poinsettia-ribbon-christmas-tree.html",

        # "http://www.islowcooker.com/pulled-pork-recipe/",
        # "http://ct.moreover.com/?a=25864939294&p=18b&v=1&x=nZ9M4me-baTp2hCwHt5O0A",
        # "http://ct.moreover.com/?a=25858809022&p=18b&v=1&x=_hc2-er6_y7u1OMrk3Le-Q",

        "http://ct.moreover.com/?a=25665293343&p=18b&v=1&x=-W2U7QUuYd5D1eicc34FtA",

    ]

    for url in urls:
        # num_comments, method = cf.get_all_comments_number(url, False)
        num_comments, method = get_all_comments_number(url)
        print('Url %s has (%s, %s) comments.' % (url, num_comments, method))



def test_five_thousands():

    influencer_ids = []
    page = 1
    size = 1000
    while page < 6:
        _, ids, total = es_influencer_query_runner_v2({}, size, page)
        influencer_ids += ids
        page += 1

    filename = 'comment_numbers_%s.csv' % datetime.strftime(datetime.now(), '%Y-%m-%d_%H%M%S')
    csvfile = open(filename, 'a+')
    csvfile.write('Influencer_Id;Post_Id;Post_URL;Number_of_comments\n')
    csvfile.close()

    for i,influencer_id in enumerate(influencer_ids):
        print i
        try:
            post = Posts.objects.filter(influencer__id=influencer_id,
                                        platform__platform_name__in=['Blogspot', 'Wordpress', 'Custom'])
            if post.count() == 0:
                continue
            post = post[0]
            # num_comments = cf.get_comments_number(post.url)
            num_comments, method = get_all_comments_number(post.url)
            print('Comment: %r Post url: %s  platform: %s' % (num_comments, post.url, post.platform.platform_name))
            csvfile = open(filename, 'a+')
            csvfile.write('%s;%s;%s;%s;%s\n' % (influencer_id, post.id, post.url, method, num_comments))
        except IndexError:
            csvfile = open(filename, 'a+')
            csvfile.write('%s;%s;%s;%s;%s\n' % (influencer_id, '---', '---', '---', 'No Blogspot, Wordpress, Custom'))
        except Exception as e:
            csvfile = open(filename, 'a+')
            csvfile.write('%s;%s;%s;%s;%s\n' % (influencer_id, '---', '---', '---', 'Exception: %s' % e))
        finally:
            csvfile.close()


def test_short_posts():
    """
    Fetcher for https://app.asana.com/0/38788253712150/60681497924019

    :return:
    """

    from debra.models import Influencer, Posts, Platform
    import codecs

    filename = 'short_posts_%s.csv' % datetime.strftime(datetime.now(), '%Y-%m-%d_%H%M%S')
    # csvfile = open(filename, 'a+')
    csvfile = codecs.open(filename, 'a+', "utf-8")
    csvfile.write(u"%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
        'N', 'Post Id', 'Post url', 'Platform', 'DB content length', 'Content', 'Influencer Id', 'Xpath'))

    ctr = 1

    # first 100 most popular influencers
    inf_ids = Influencer.objects\
        .filter(old_show_on_search=True, score_popularity_overall__isnull=False)\
        .exclude(blacklisted=True)\
        .order_by('-score_popularity_overall')\
        .values_list('id', flat=True)[:500]

    for inf_id in inf_ids:
        print('%s Performing influencer %s...' % (ctr, inf_id))

        plat_ids = Platform.objects.filter(influencer_id=inf_id,
                                           platform_name__in=['Blogspot', 'Wordpress', 'Custom']).values_list('id', flat=True)

        for plat_id in plat_ids:
            print('    Performing platform %s...' % plat_id)
            posts_count = Posts.objects.filter(platform_id=plat_id).count()
            short_posts_count = Posts.objects.filter(platform_id=plat_id).extra(where=["CHAR_LENGTH(content) <= 100"]).count()
            print('        Posts: %s  Short posts: %s' % (posts_count, short_posts_count))
            if posts_count > 0 and short_posts_count == posts_count:
                # Our client!
                post = Posts.objects.filter(platform_id=plat_id)[0]

                # print('=====================================')
                # print('Post %s  Platform: %s  url: %s' % (post.id, post.platform.platform_name, post.url))
                # print('Content length in DB: %s' % len(post.content))
                # print(post.content)
                # resp = requests.get(post.url)
                # if resp.status_code >= 400:
                #     print('Url status code: %s' % resp.status_code)
                # else:

                csvfile.write(u"%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
                    ctr,
                    post.id,
                    post.url,
                    post.platform.platform_name,
                    len(post.content),
                    post.content.replace('\n', '').replace('\t', ''),
                    post.influencer_id, '')
                )
        ctr += 1

    csvfile.close()


