from __future__ import absolute_import, division, print_function, unicode_literals

import unittest
from platformdatafetcher import platformutils


class TestNormalization(unittest.TestCase):
    def test_normalized(self):
        normal = 'https://plus.google.com/109264603825317751107'
        normalized = platformutils.normalize_social_url(normal)
        self.assertEqual(normal, normalized)

    def test_subpages_suffix(self):
        normal = 'https://plus.google.com/109264603825317751107'

        self.assertEqual(normal, platformutils.normalize_social_url(normal + '/posts'))
        self.assertEqual(normal, platformutils.normalize_social_url(normal + '/about'))
        self.assertEqual(normal, platformutils.normalize_social_url(normal + '/posts/1234/blahblah'))

    def test_u0_prefix(self):
        normal = 'https://plus.google.com/109264603825317751107'

        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/0/109264603825317751107'))

    def test_u0_b_prefix(self):
        normal = 'https://plus.google.com/109264603825317751107'

        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/0/b/109264603825317751107'))
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/0/z/109264603825317751107'))

    def test_u1_prefix(self):
        normal = 'https://plus.google.com/109264603825317751107'

        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/1/109264603825317751107'))
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/1/b/109264603825317751107'))

    def test_plus_prefixed_username(self):
        normal = 'https://plus.google.com/+CarliBel55'
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/+CarliBel55/posts'))

    def test_uX_prefix_plus_username(self):
        normal = 'https://plus.google.com/+AnnDrake'
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/0/+AnnDrake/posts'))
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/1/+AnnDrake/posts'))

    def test_duplicate_id(self):
        normal = 'https://plus.google.com/117308936952117063631'
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/117308936952117063631/117308936952117063631/posts'))
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/b/117308936952117063631/117308936952117063631/posts'))
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/0/b/117308936952117063631/117308936952117063631/posts'))

    def test_querystring_params(self):
        normal = 'https://plus.google.com/+LauraDavidson-posts'
        self.assertEqual(normal, platformutils.normalize_social_url(
            'https://plus.google.com/u/0/+LauraDavidson-posts?rel=author'))
