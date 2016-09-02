from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
from platformdatafetcher.categorization import CategoryMatch, CategoryMatcher, PostInfo


class PostInfoTest(unittest.TestCase):
    def test_tokenization(self):
        p = PostInfo('http://google.com', 'the quick brown fox')
        self.assertEqual(['the', 'quick', 'brown', 'fox'], p.words)
        self.assertEqual('http://google.com', p.post_url)

    def test_no_content(self):
        p = PostInfo('http://google.com', None)
        self.assertEqual([], p.words)


class SingleCategoryMatchTest(unittest.TestCase):
    def _post(self, content):
        return PostInfo('http://google.com', content)

    def setUp(self):
        self.matcher = CategoryMatcher(category_id=1,
                                       category_name='numbers',
                                       keywords=['one', 'two', 'three'],
                                       match_threshold=2)

    def test_below_threshold(self):
        self.assertEqual(CategoryMatch(False, ['one'], 1, 'numbers'),
                         self.matcher.matches(self._post('one bottle of beer')))

    def test_gte_threshold(self):
        self.assertEqual(CategoryMatch(True, ['one', 'two'], 1, 'numbers'),
                         self.matcher.matches(self._post('one bottle or two')))

    def test_count_multiple_occurrences(self):
        self.assertEqual(CategoryMatch(True, ['one', 'one'], 1, 'numbers'),
                         self.matcher.matches(self._post('one bottle or one')))


    def test_case_insensitive_match(self):
        self.assertEqual(CategoryMatch(True, ['one', 'two'], 1, 'numbers'),
                         self.matcher.matches(self._post('One boTtle Or twO')))

    def test_doesnt_match_without_threshold(self):
        matcher = CategoryMatcher(category_id=1, category_name='numbers',
                                  keywords=['one', 'two', 'three'],
                                  match_threshold=None)
        self.assertFalse(matcher.matches(self._post('one bottle or two')).success)
