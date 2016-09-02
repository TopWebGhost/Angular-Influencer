from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
import copy
from debra import models
import calendar
from platformdatafetcher.blogfetcher import TumblrFetcher


class TestTumblrPostData(unittest.TestCase):
    def test_full_post_data(self):
        post = models.Posts()
        TumblrFetcher.read_post_data(post, text_post_data)
        self.assertEqual('post title', post.title)
        self.assertEqual('body text', post.content)
        self.assertEqual('http://dapprly.com/post/my-blog-post', post.url)
        self.assertEqual('104194253038', post.api_id)
        self.assertEqual(1417562117, calendar.timegm(post.create_date.utctimetuple()))

    def test_no_body_uses_caption(self):
        post = models.Posts()
        no_photo_data = copy.deepcopy(photo_post_data)
        del no_photo_data['photos']

        TumblrFetcher.read_post_data(post, photo_post_data)
        self.assertEqual('', post.title)
        self.assertIn(photo_post_data['caption'], post.content)

    def test_photos_rendered_in_body(self):
        post = models.Posts()
        TumblrFetcher.read_post_data(post, photo_post_data)

        self.assertIn('http://40.media.tumblr.com/original_size.jpg', post.content)
        self.assertIn(photo_post_data['caption'], post.content)


text_post_data = {
    'blog_name': 'dapprly',
    'body': 'body text',
    'date': '2014-12-02 23:15:17 GMT',
    'format': 'html',
    'highlighted': [],
    'id': 104194253038,
    'note_count': 11,
    'post_url': 'http://dapprly.com/post/my-blog-post',
    'reblog_key': 'ZZ7ZwqRv',
    'short_url': 'http://tmblr.co/ZqUpvv1X2TY3k',
    'slug': 'designer-ditches-corporate-fashion-for-denim',
    'state': 'published',
    'tags': [
        'dapprly',
        'denim',
        'kent denim',
        'startup',
        'fashion',
        'menswear',
        'accessories',
        'street style',
        'streetstyle fashion',
        'mens fashion',
        'stylish',
        'stylish men',
        'style hunt',
        'style gur'
    ],
    'timestamp': 1417562117,
    'title': 'post title',
    'type': 'text'
}

photo_post_data = {
    'blog_name': 'dapprly',
    'caption': '<p>So sad to lose this guy to #la. It&#8217;s been fun in #nyc, #sxsw, and everywhere in between. @bahjournalist @kionsanders @stanmichaelbash @neiki2u  (at Bo&#8217;s Kitchen &amp; Bar Room)</p>',
    'date': '2014-12-05 02:33:58 GMT',
    'format': 'html',
    'highlighted': [],
    'id': 104376529477,
    'image_permalink': 'http://dapprly.com/image/104376529477',
    'link_url': 'http://instagram.com/p/wNVuxoQGOI/',
    'note_count': 3,
    'photos': [
        {'alt_sizes': [
            {'height': 75,
             'url': 'http://40.media.tumblr.com/575a2dea587a5540af808b51e990a13c/tumblr_ng38gm6mN21rpmxc4o1_75sq.jpg',
             'width': 75}
        ],
            'caption': '',
            'original_size': {
                'height': 640,
                'url': 'http://40.media.tumblr.com/original_size.jpg',
                'width': 640
            }
        }
    ],
    'post_url': 'http://dapprly.com/post/104376529477/so-sad-to-lose-this-guy-to-la-its-been-fun-in',
    'reblog_key': 'BXS7J8wX',
    'short_url': 'http://tmblr.co/ZqUpvv1XDKt95',
    'slug': 'so-sad-to-lose-this-guy-to-la-its-been-fun-in',
    'state': 'published',
    'tags': ['nyc', 'sxsw', 'la'],
    'timestamp': 1417746838,
    'type': 'photo'
}
