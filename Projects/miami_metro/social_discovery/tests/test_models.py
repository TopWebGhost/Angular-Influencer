from datetime import datetime

import pytest
from mock import patch

from social_discovery.tests import factories

NOW = datetime(2016, 8, 24, 6, 45)


@pytest.mark.unittest
@pytest.mark.django_db
class TestInstagramProfile:
    @pytest.fixture()
    def instagram_profile(self):
        return factories.InstagramProfileFactory(
            username='hello',
            friends_count=51,
            followers_count=924,
            post_count=38,
            last_post_time=datetime(2016, 3, 2, 18, 43),
            api_data={
                u'biography': u"I don't know what to write",
                u'full_name': u'Anonymous',
            },
            api_data_history=[
                {
                    '2015-10-01':
                        {
                            u'biography': u"I don't know what to write",
                            u'full_name': u'Anonymous',
                        },
                },
            ]
        )

    def test_default_api_data_history(self):
        instagram_profile = factories.InstagramProfileFactory()
        assert instagram_profile.api_data_history == []

    def test_update_from_web_data_no_data(self, instagram_profile):
        assert instagram_profile.valid_influencer is None
        instagram_profile.update_from_web_data(web_data={})
        assert instagram_profile.valid_influencer is False
        assert instagram_profile.friends_count == 51
        assert instagram_profile.followers_count == 924
        assert instagram_profile.post_count == 38
        assert instagram_profile.api_data == {
            u'biography': u"I don't know what to write",
            u'full_name': u'Anonymous',
        }
        assert instagram_profile.api_data_history == [
            {
                '2015-10-01':
                    {
                        u'biography': u"I don't know what to write",
                        u'full_name': u'Anonymous',
                    },
            },
        ]

    @pytest.mark.parametrize(
        'web_data,expected_friends_count,expected_followers_count,'
        'expected_post_count,expected_last_post_time,expected_api_data,'
        'expected_api_data_history',
        [
            (
                {
                    'following': 1027,
                    'followers': 969,
                    'posts': 142,
                    'last_post_time': datetime(2016, 8, 24, 9, 10),
                    'api_data': {
                        u'biography': u'Welcome to my Instagram',
                        u'full_name': u'Allen',
                    },
                },
                1027, 969, 142, datetime(2016, 8, 24, 9, 10),
                {
                    u'biography': u'Welcome to my Instagram',
                    u'full_name': u'Allen',
                },
                [
                    {
                        '2015-10-01':
                            {
                                u'biography': u"I don't know what to write",
                                u'full_name': u'Anonymous',
                            },
                    },
                    {
                        NOW.strftime('%Y-%m-%d'):
                            {
                                u'biography': u'Welcome to my Instagram',
                                u'full_name': u'Allen',
                            },
                    },
                ],
            ),
            (
                {
                    'external_url': 'https://google.com',
                },
                51, 924, 38, datetime(2016, 3, 2, 18, 43),
                {
                    u'biography': u"I don't know what to write",
                    u'full_name': u'Anonymous',
                },
                [
                    {
                        '2015-10-01':
                            {
                                u'biography': u"I don't know what to write",
                                u'full_name': u'Anonymous',
                            },
                    },
                ],
            ),
            (
                {
                    'posts': 465,
                    'external_url': 'https://google.com',
                },
                51, 924, 465, datetime(2016, 3, 2, 18, 43),
                {
                    u'biography': u"I don't know what to write",
                    u'full_name': u'Anonymous',
                },
                [
                    {
                        '2015-10-01':
                            {
                                u'biography': u"I don't know what to write",
                                u'full_name': u'Anonymous',
                            },
                    },
                ],
            ),
        ]
    )
    def test_update_from_web_data_first_time(
        self, instagram_profile, web_data, expected_friends_count,
        expected_followers_count, expected_post_count, expected_last_post_time,
        expected_api_data, expected_api_data_history
    ):
        with patch('social_discovery.models.datetime') as datetime_mock:
            datetime_mock.now.return_value = NOW
            instagram_profile.update_from_web_data(
                web_data=web_data
            )
        assert instagram_profile.valid_influencer is None
        assert instagram_profile.friends_count == expected_friends_count
        assert instagram_profile.followers_count == expected_followers_count
        assert instagram_profile.post_count == expected_post_count
        assert instagram_profile.last_post_time == expected_last_post_time
        assert instagram_profile.api_data == expected_api_data
        assert instagram_profile.api_data_history == expected_api_data_history

    @pytest.mark.parametrize(
        'api_data,expected_description',
        (
            (
                {
                    u'biography': u"I don't know what to write",
                    u'full_name': u'Anonymous',
                    u'external_url': u'http://google.com',
                },
                "I don't know what to write",
            ),
            (
                {
                    u'full_name': u'Anonymous',
                    u'external_url': u'http://google.com',
                },
                None,
            ),
            (
                {
                    u'bio': u'hello',
                    u'full_name': u'Anonymous',
                    u'external_url': u'http://google.com',
                },
                'hello',
            ),
        )
    )
    def test_get_description_from_api(self, api_data, expected_description):
        instagram_profile = factories.InstagramProfileFactory(
            api_data=api_data
        )
        assert instagram_profile.get_description_from_api() == (
            expected_description
        )

    @pytest.mark.parametrize(
        'api_data,expected_url',
        (
            (
                {
                    u'biography': u"I don't know what to write",
                    u'full_name': u'Anonymous',
                    u'external_url': u'http://google.com',
                },
                u'http://google.com',
            ),
            (
                {
                    u'biography': u"I don't know what to write",
                    u'full_name': u'Anonymous',
                },
                None,
            ),
            (
                {
                    u'bio': u'hello',
                    u'full_name': u'Anonymous',
                    u'website': u'http://google.com',
                },
                u'http://google.com',
            ),
        )
    )
    def test_get_url_from_api(self, api_data, expected_url):
        instagram_profile = factories.InstagramProfileFactory(
            api_data=api_data
        )
        assert instagram_profile.get_url_from_api() == (
            expected_url
        )

    @pytest.mark.parametrize(
        'api_data_history,keys,expected_data',
        (
            (
                [
                    {
                        '2015-01-01': {
                            u'biography': u"I don't know what to write",
                            u'full_name': u'Anonymous',
                            u'website': u'http://example.com',
                        },
                    },
                    {
                        '2016-01-01': {
                            u'biography': u"I don't know what to write",
                            u'full_name': u'Anonymous',
                            u'external_url': u'http://google.com',
                        },
                    }
                ],
                ('external_url', 'website',),
                {'http://google.com', 'http://example.com', },
            ),
            (
                [],
                ('external_url', 'website',),
                set(),
            ),
            (
                [
                    {
                        '2015-01-01': {
                            u'biography': u"I don't know what to write",
                            u'full_name': u'Anonymous',
                            u'website': u'http://example.com',
                        },
                    },
                    {
                        '2016-01-01': {
                            u'biography': u"I don't know what to write",
                            u'full_name': u'Anonymous',
                            u'external_url': u'http://google.com',
                        },
                    }
                ],
                ('full_name', ),
                {'Anonymous', },
            ),
            (
                [
                    {
                        '2015-01-01': {
                            u'biography': u"I don't know what to write",
                            u'full_name': u'Anonymous',
                            u'website': u'http://example.com',
                        },
                    },
                    {
                        '2016-01-01': {
                            u'biography': u"I don't know what to write",
                            u'full_name': u'Anonymous',
                            u'external_url': u'http://google.com',
                        },
                    }
                ],
                ('unknown_key', ),
                set(),
            ),
        )
    )
    def test_get_data_from_api_history(
        self, api_data_history, keys, expected_data
    ):
        instagram_profile = factories.InstagramProfileFactory(
            api_data_history=api_data_history
        )
        assert instagram_profile._get_data_from_api_history(
            keys=keys
        ) == expected_data

