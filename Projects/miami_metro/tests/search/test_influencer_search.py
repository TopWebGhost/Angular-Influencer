from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
from debra import search_helpers


zappos_query = {
    'keyword': 'Zappos',
    'type': 'all',
    'page': 1,
    'filters': {
        'engagement': [],
        'brand': [],
        'popularity': [],
        'priceranges': [],
        'gender': []
    }
}


class TestInfluencerSearch(unittest.TestCase):
    def test_search_results(self):
        result = search_helpers.search_influencers(zappos_query, 60)
