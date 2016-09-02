from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
from debra import models
from datetime import datetime, timedelta


level = models.ActivityLevel


class TransitionsTest(unittest.TestCase):
    class TestPlatform(models.PlatformActivityLevelMixin):
        def __init__(self):
            self.insert_date = None

        def get_last_post_date(self):
            return self.last_post_date

    def test_last_day(self):
        self.assertEqual(self.level_for_last_post(days_ago=0), level.ACTIVE_LAST_DAY)

    def test_last_week(self):
        self.assertEqual(self.level_for_last_post(days_ago=2), level.ACTIVE_LAST_WEEK)

    def test_last_month(self):
        self.assertEqual(self.level_for_last_post(days_ago=10), level.ACTIVE_LAST_MONTH)

    def test_last_3_months(self):
        self.assertEqual(self.level_for_last_post(days_ago=40), level.ACTIVE_LAST_3_MONTHS)

    def test_last_6_months(self):
        self.assertEqual(self.level_for_last_post(days_ago=150), level.ACTIVE_LAST_6_MONTHS)

    def test_last_year(self):
        self.assertEqual(self.level_for_last_post(days_ago=250), level.ACTIVE_LAST_12_MONTHS)

    def test_more_than_a_year(self):
        self.assertEqual(self.level_for_last_post(days_ago=400), level.ACTIVE_LONG_TIME_AGO)

    def test_no_posts(self):
        platform = self.TestPlatform()
        platform.last_post_date = None
        platform.calculate_activity_level()

        self.assertEqual(platform.activity_level, level.ACTIVE_UNKNOWN)

    def test_new(self):
        platform = models.Platform()
        platform = self.TestPlatform()
        platform.last_post_date = datetime.today() - timedelta(days=5)
        platform.insert_date = datetime.today() - timedelta(days=1)
        platform.calculate_activity_level()

        self.assertEqual(models.ActivityLevel.ACTIVE_NEW, platform.activity_level)

    def level_for_last_post(self, days_ago):
        post_date = datetime.today() - timedelta(days=days_ago)
        platform = self.TestPlatform()
        platform.last_post_date = post_date
        platform.calculate_activity_level()
        return platform.activity_level
