from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
from platformdatafetcher.categorization import Categorizer, CategoryMatcher, PostInfo


class CategorizationTest(unittest.TestCase):
    def setUp(self):
        self.categorizer = Categorizer([
            CategoryMatcher(category_id=1, category_name='numbers',
                            keywords=['one', 'two'], match_threshold=2),
            CategoryMatcher(category_id=2, category_name='music',
                            keywords=['michael', 'jackson'], match_threshold=2),
        ])

    def _categories(self, matches):
        return [m.category_name for m in matches]

    def test_single_category(self):
        matches = self.categorizer.match_categories(self._post('one beer, two beers'))
        self.assertEqual(['numbers'], self._categories(matches))

    def test_multiple_categories(self):
        matches = self.categorizer.match_categories(self._post('one michael jackson two'))
        self.assertEqual(['numbers', 'music'], self._categories(matches))

    def _post(self, content):
        return PostInfo('http://google.com', content)
