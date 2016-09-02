from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
from debra import models


level = models.ActivityLevel


class InfluencerActivityTest(unittest.TestCase):
    class TestInfluencer(models.InfluencerActivityLevelMixin):
        def __init__(self):
            self.platform_activity_levels = None

        def get_platform_activity_levels(self):
            return self.platform_activity_levels

    def test_no_platform_activity(self):
        self.assertEqual(None, self.level_for_platforms(None))
        self.assertEqual(None, self.level_for_platforms([]))

    def test_single_platform_level_passed_to_influencer(self):
        self.assertEqual(level.ACTIVE_LAST_WEEK, self.level_for_platforms([level.ACTIVE_LAST_WEEK]))

    def test_picking_highest_activity_level(self):
        self.assertEqual(level.ACTIVE_LAST_DAY, self.level_for_platforms([
            level.ACTIVE_LAST_WEEK, level.ACTIVE_LAST_MONTH, level.ACTIVE_LAST_DAY
        ]))

    def test_unknown_level_has_lowest_priority(self):
        self.assertEqual(level.ACTIVE_LONG_TIME_AGO, self.level_for_platforms([
            level.ACTIVE_LONG_TIME_AGO, level.ACTIVE_UNKNOWN
        ]))

    def test_using_none_as_last_resort(self):
        self.assertEqual(level.ACTIVE_LAST_WEEK, self.level_for_platforms([
            level.ACTIVE_LAST_WEEK, None
        ]))

        self.assertEqual(None, self.level_for_platforms([
            None, None, None
        ]))

    def level_for_platforms(self, platform_levels):
        influencer = self.TestInfluencer()
        influencer.platform_activity_levels = platform_levels
        influencer.calculate_activity_level()
        return influencer.activity_level

