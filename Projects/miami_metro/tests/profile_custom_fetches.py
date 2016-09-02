from __future__ import absolute_import, division, print_function, unicode_literals
import cProfile
from platformdatafetcher import fetchertasks


test_platforms = [
    872183,
    2096438,
    1847260,
    1958384,
    871659,
    921707,
    1284950,
    873012,
    899156,
    2485718,
]


def test_one():
    fetchertasks.fetch_platform_data(test_platforms[0])


def profile_one():
    cProfile.run('from tests.profile_custom_fetches import *; test_one()',
                 'tmp/profile_one')


def test_all():
    for platform_id in test_platforms:
        fetchertasks.fetch_platform_data(platform_id)


def profile_all():
    cProfile.run('from tests.profile_custom_fetches import *; test_all()',
                 'tmp/profile_all_no_init_parse')
