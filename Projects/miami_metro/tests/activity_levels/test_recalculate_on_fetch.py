from __future__ import absolute_import, division, print_function, unicode_literals
from datetime import datetime, timedelta
import unittest
from mock import Mock
from debra import models
from platformdatafetcher.fetcherbase import Fetcher
from platformdatafetcher.activity_levels import recalculate_activity_level


class NormalFetcher(Fetcher):
    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):
        self.posts_fetched = True
        return True


class CrashingFetcher(Fetcher):
    @recalculate_activity_level
    def fetch_posts(self, max_pages=None):
        raise ValueError("Oops!")


class RecalculateTest(unittest.TestCase):
    def setUp(self):
        self.influencer = models.Influencer()
        self.influencer.calculate_activity_level = Mock()
        self.influencer.save = Mock()

        self.platform = models.Platform()
        self.platform.influencer = self.influencer

    def test_recalculate_decorator(self):
        self.platform.insert_date = datetime.today() - timedelta(days=40)
        self.platform.get_last_post_date = Mock()
        self.platform.get_last_post_date.return_value = datetime.today()
        self.platform.save = Mock()
        self.assertIsNone(self.platform.activity_level)
        self.assertIsNone(self.platform.last_fetched)

        f = NormalFetcher(self.platform, None)
        result = f.fetch_posts()

        self.assertTrue(result)
        self.assertTrue(f.posts_fetched)
        self.platform.save.assert_any_call()
        self.assertEqual(models.ActivityLevel.ACTIVE_LAST_DAY, self.platform.activity_level)
        self.assertLess(10, (datetime.utcnow() - self.platform.last_fetched).total_seconds)

        self.influencer.save.assert_any_call()
        self.influencer.calculate_activity_level.assert_any_call()

    def test_exception_midprocess_still_recalculates_level(self):
        self.platform.insert_date = datetime.today() - timedelta(days=40)
        self.platform.get_last_post_date = Mock()
        self.platform.get_last_post_date.return_value = datetime.today()
        self.platform.save = Mock()
        self.assertIsNone(self.platform.activity_level)

        f = CrashingFetcher(self.platform, None)

        with self.assertRaises(ValueError):
            f.fetch_posts()

        self.platform.save.assert_any_call()
        self.assertEqual(models.ActivityLevel.ACTIVE_LAST_DAY, self.platform.activity_level)
        self.assertLess(10, (datetime.utcnow() - self.platform.last_fetched).total_seconds)
