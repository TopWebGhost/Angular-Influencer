import pytest
from datetime import datetime

from datetime import timedelta
from mock import patch, call

from social_discovery.models import InstagramProfile
from social_discovery.tasks import (
    _create_profiles_from_instagram_hashtags, reprocess_instagram_profiles,
)
from social_discovery.tests import factories


@pytest.mark.unittest
@patch(
    'social_discovery.tasks.CreatorByInstagramHashtags.create_new_profiles'
)
@patch(
    'social_discovery.tasks.bd_hashtags',
    {
        'fashion_tags': ['style', 'makeup', ],
        'food_tags': ['food', 'cooking', 'seafood', ],
    }
)
class TestCreateProfilesFromInstagramHashtags:
    def test_default_params(self, create_new_profiles):
        _create_profiles_from_instagram_hashtags()
        assert not create_new_profiles.called

    def test_set_hashkeys(self, create_new_profiles):
        _create_profiles_from_instagram_hashtags(hashtags_keys=('food_tags',))
        assert not create_new_profiles.called

    def test_set_class(self, create_new_profiles):
        _create_profiles_from_instagram_hashtags(
            pipeline_class_name='TestPipeline'
        )
        assert not create_new_profiles.called

    def test_non_existent_tag(self, create_new_profiles):
        _create_profiles_from_instagram_hashtags(
            hashtags_keys=('extra_tags',),
            pipeline_class_name='TestPipeline'
        )
        assert not create_new_profiles.called

    @pytest.mark.parametrize(
        'tags_keys,expected_tags',
        [
            (
                ['food_tags', ],
                {'food_tags': ['food', 'cooking', 'seafood', ], },
            ),
            (
                ['food_tags', 'fashion_tags', ],
                {
                    'food_tags': ['food', 'cooking', 'seafood', ],
                    'fashion_tags': ['style', 'makeup', ],
                },
            ),
            (
                ['food_tags', 'extra_tags', ],
                {
                    'food_tags': ['food', 'cooking', 'seafood', ],
                },
            ),
        ]
    )
    def test_hashtags(self, create_new_profiles, tags_keys, expected_tags):
        _create_profiles_from_instagram_hashtags(
            hashtags_keys=tags_keys,
            pipeline_class_name='TestPipeline'
        )
        assert create_new_profiles.called
        assert create_new_profiles.call_args == call(
            pipeline_class='TestPipeline',
            hashtags=expected_tags,
            submission_tracker=None, num_pages_to_load=20
        )

    def test_custom_settings(self, create_new_profiles):
        _create_profiles_from_instagram_hashtags(
            hashtags_keys=('food_tags',),
            pipeline_class_name='TestPipeline',
            submission_tracker='123',
            num_pages_to_load=10,
        )
        assert create_new_profiles.called
        assert create_new_profiles.call_args == call(
            pipeline_class='TestPipeline',
            hashtags={'food_tags': ['food', 'cooking', 'seafood', ], },
            submission_tracker='123', num_pages_to_load=10
        )


@pytest.mark.unittest
@pytest.mark.django_db
@patch('social_discovery.tasks.MAX_INSTAGRAM_REFETCH_RETRY_COUNT', 3)
@patch('social_discovery.pipelines.crawler_task.apply_async')
class TestReprocessInstagramProfiles:
    @pytest.mark.parametrize(
        'profile_config,was_processed',
        [
            (
                {
                    'friends_count': 30,
                    'tags': 'blog',
                    'reprocess_tries_count': 0,
                }, False
            ),
            (
                {
                    'friends_count': 100000,
                    'tags': 'undecided SHORT',
                    'reprocess_tries_count': 1,
                }, True
            ),
            (
                {
                    'friends_count': 100000,
                    'tags': 'undecided',
                    'reprocess_tries_count': 2,
                }, True
            ),
            (
                {
                    'friends_count': 100000,
                    'tags': 'lifestyle undecided',
                    'reprocess_tries_count': 2,
                }, True
            ),
            (
                {
                    'friends_count': 50000,
                    'tags': 'lifestyle undecided',
                    'reprocess_tries_count': 2,
                }, True
            ),
            (
                {
                    'friends_count': 50000,
                    'tags': 'lifestyle undecided',
                    'reprocess_tries_count': 3,
                }, False
            ),
            (
                {
                    'friends_count': 49999,
                    'tags': 'lifestyle undecided',
                    'reprocess_tries_count': 2,
                }, False
            ),
            (
                {
                    'friends_count': 52000,
                    'tags': 'lifestyle blog',
                    'reprocess_tries_count': 2,
                }, False
            ),
        ]
    )
    def test_undecided_profiles(
        self, crawler_task_mock, profile_config, was_processed
    ):
        profile = factories.InstagramProfileFactory(**profile_config)
        reprocess_instagram_profiles(friends_lower_bound=50000, period_weeks=0)
        assert crawler_task_mock.called is was_processed
        assert InstagramProfile.objects.get(
            id=profile.id
        ).reprocess_tries_count == profile.reprocess_tries_count + int(
            was_processed
        )

    @pytest.mark.parametrize(
        'date_created,was_processed',
        [
            (datetime.now() - timedelta(days=30), True),
            (datetime.now() - timedelta(days=15), True),
            (datetime.now() - timedelta(days=14), True),
            (datetime.now() - timedelta(days=13), False),
            (datetime.now() - timedelta(days=1), False),
        ]
    )
    def test_newly_created_profiles(
        self, crawler_task_mock, date_created, was_processed
    ):
        profile = factories.InstagramProfileFactory(
            friends_count=50000,
            tags='lifestyle undecided',
            reprocess_tries_count=2,
        )
        profile.date_created = date_created
        profile.save()
        reprocess_instagram_profiles(friends_lower_bound=50000, period_weeks=2)
        assert crawler_task_mock.called is was_processed
        assert InstagramProfile.objects.get(
            id=profile.id
        ).reprocess_tries_count == profile.reprocess_tries_count + int(
            was_processed
        )
