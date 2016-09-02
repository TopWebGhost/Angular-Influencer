import pytest

from social_discovery import processors
from social_discovery.tests import factories


@pytest.mark.unittest
@pytest.mark.django_db
class TestProcessorGermany:
    @pytest.fixture()
    def processor(self):
        return processors.ProcessorGermany()

    def test_tag(self, processor):
        assert processor.PROCESSOR_TAG == 'GERMANY'

    def test_profile_does_not_exist(self, processor):
        assert processor.proceed(1) is False

    @pytest.mark.parametrize(
        'tags,expected_result',
        [
            ('', False),
            ('some other tags', False),
            (
                '{}_HASHTAG'.format(
                    processors.ProcessorGermany.PROCESSOR_TAG
                ), True
            ),
            (
                'some {}_HASHTAG other tags'.format(
                    processors.ProcessorGermany.PROCESSOR_TAG
                ),
                True
            ),
        ]
    )
    def test_profile_has_no_tags(self, processor, tags, expected_result):
        profile = factories.InstagramProfileFactory(tags=tags)
        assert processor.proceed(profile.id) is expected_result


@pytest.mark.unittest
@pytest.mark.django_db
class TestProcessorLifestyle:
    @pytest.fixture()
    def processor(self):
        return processors.ProcessorLifestyle()

    def test_tag(self, processor):
        assert processor.PROCESSOR_TAG == 'LIFESTYLE'

    def test_profile_does_not_exist(self, processor):
        assert processor.proceed(1) is False

    @pytest.mark.parametrize(
        'tags,expected_result',
        [
            ('', False),
            ('some other tags', False),
            (
                '{}_HASHTAG'.format(
                    processors.ProcessorLifestyle.PROCESSOR_TAG
                ), True
            ),
            (
                'some {}_HASHTAG other tags'.format(
                    processors.ProcessorLifestyle.PROCESSOR_TAG
                ),
                True
            ),
        ]
    )
    def test_profile_has_no_tags(self, processor, tags, expected_result):
        profile = factories.InstagramProfileFactory(tags=tags)
        assert processor.proceed(profile.id) is expected_result


@pytest.mark.unittest
@pytest.mark.django_db
class TestProcessorHealthFitness:
    @pytest.fixture()
    def processor(self):
        return processors.ProcessorHealthFitness()

    def test_tag(self, processor):
        assert processor.PROCESSOR_TAG == 'HEALTHFITNESS'

    def test_profile_does_not_exist(self, processor):
        assert processor.proceed(1) is False

    @pytest.mark.parametrize(
        'tags,expected_result',
        [
            ('', False),
            ('some other tags', False),
            (
                '{}_HASHTAG'.format(
                    processors.ProcessorHealthFitness.PROCESSOR_TAG
                ), True
            ),
            (
                'some {}_HASHTAG other tags'.format(
                    processors.ProcessorHealthFitness.PROCESSOR_TAG
                ),
                True
            ),
        ]
    )
    def test_profile_has_no_tags(self, processor, tags, expected_result):
        profile = factories.InstagramProfileFactory(tags=tags)
        assert processor.proceed(profile.id) is expected_result
