import pytest
from mock import patch

from debra.models import Influencer
from debra.tests import factories as debra_factories
from social_discovery.create_influencers import (
    create_influencer_from_instagram,
)
from social_discovery.tests import factories


@pytest.mark.unittest
@pytest.mark.django_db
@patch('social_discovery.create_influencers.get_influencers_email_name_location_for_profile')  # noqa
@patch('social_discovery.create_influencers.platformextractor.do_further_validation_using_validated_platforms')  # noqa
@patch('social_discovery.create_influencers.admin_helpers.handle_social_handle_updates')  # noqa
@patch('social_discovery.create_influencers.create_platform_for_influencer')  # noqa
@patch('social_discovery.create_influencers.helpers.create_influencer_and_blog_platform')  # noqa
@patch(
    'social_discovery.create_influencers.find_matching_influencers_for_profile'
)
class TestCreateInfluencerFromInstagram:
    def test_matching_influencers(self, find_influencers_mock, *args):
        url = 'http://google.com'
        existing_influencers = {
            url: debra_factories.InfluencerFactory()
        }
        find_influencers_mock.return_value = existing_influencers, (url,)
        instagram_profile = factories.InstagramProfileFactory()
        assert create_influencer_from_instagram(
            instagram_profile.id, False
        ) == (False, existing_influencers,)

    def test_create_influencer(
        self, find_influencers_mock, create_influencer_platform_mock,
        create_platform_for_influencer_mock, *args
    ):
        valid_url = 'https://twitter.com/JimCarrey'
        find_influencers_mock.return_value = dict(), (valid_url,)

        def fake_create_influencer_platform(url, *args, **kwargs):
            influencer = debra_factories.InfluencerFactory()
            debra_factories.PlatformFactory(influencer=influencer, url=url)
            return influencer
        create_influencer_platform_mock.side_effect = (
            fake_create_influencer_platform
        )

        def fake_create_platform_for_influencer(url, inf, *args, **kwargs):
            return debra_factories.PlatformFactory(url=url, influencer=inf)
        create_platform_for_influencer_mock.side_effect = (
            fake_create_platform_for_influencer
        )

        instagram_profile = factories.InstagramProfileFactory()
        result = create_influencer_from_instagram(instagram_profile.id, False)
        assert Influencer.objects.count() == 1
        assert result == (True, Influencer.objects.all()[0])
