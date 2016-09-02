import pytest
from mock import patch

from social_discovery import pipelines
from social_discovery.classifiers import *  # to make eval() work
from social_discovery.processors import *  # to make eval() work
from social_discovery.tests import factories
from social_discovery.upgraders import LightUpgrader, LightExtraDataUpgrader


@pytest.mark.unittest
@pytest.mark.django_db
@patch('social_discovery.pipelines.crawler_task.apply_async')
@patch(
    'social_discovery.pipelines.get_queue_name_by_pipeline_step',
    return_value='test_queue_name'
)
class TestPipeline:
    @pytest.fixture()
    def pipeline(self):
        pipeline = pipelines.Pipeline()
        pipeline.PIPELINE_ROUTE = [
            KeywordClassifier.__name__,
            DescriptionLengthClassifier.__name__,
            OnlyBloggersProcessor.__name__,
        ]
        return pipeline

    def test_no_pipeline(self, _, crawler_task_mock, pipeline):
        pipeline.PIPELINE_ROUTE = None
        instagram_profile = factories.InstagramProfileFactory()
        pipeline.run_pipeline(data=instagram_profile.id)
        pipeline.run_pipeline()
        assert not crawler_task_mock.called

    @pytest.mark.parametrize('input_type', (int, str,))
    def test_id_as_data(self, _, crawler_task_mock, pipeline, input_type):
        instagram_profile = factories.InstagramProfileFactory()
        pipeline.run_pipeline(data=input_type(instagram_profile.id))
        assert crawler_task_mock.call_count == 1
        assert crawler_task_mock.call_args[1] == {
            'queue': 'test_queue_name',
            'kwargs': {
                'klass_name': 'KeywordClassifier',
                'profile_id': instagram_profile.id,
                'task_type': 'pipeline',
                'route': [
                    'KeywordClassifier',
                    'DescriptionLengthClassifier',
                    'OnlyBloggersProcessor',
                ]
            }
        }

    def test_ids_list_as_data(self, _, crawler_task_mock, pipeline):
        profiles_count = 4
        instagram_profiles = factories.InstagramProfileFactory.create_batch(
            profiles_count
        )
        pipeline.run_pipeline(
            data=[profile.id for profile in instagram_profiles]
        )
        assert crawler_task_mock.call_count == profiles_count
        for run in range(profiles_count):
            crawler_task_mock.assert_any_call(
                queue='test_queue_name',
                kwargs={
                    'klass_name': 'KeywordClassifier',
                    'profile_id': instagram_profiles[run].id,
                    'task_type': 'pipeline',
                    'route': [
                        'KeywordClassifier',
                        'DescriptionLengthClassifier',
                        'OnlyBloggersProcessor',
                    ]
                }
            )

    def test_queryset_as_data(self, _, crawler_task_mock, pipeline):
        profiles_count = 4
        instagram_profiles = factories.InstagramProfileFactory.create_batch(
            profiles_count
        )
        profile_ids_to_call = (
            instagram_profiles[0].id, instagram_profiles[1].id,
        )
        pipeline.run_pipeline(
            data=InstagramProfile.objects.filter(id__in=profile_ids_to_call)
        )
        assert len(profile_ids_to_call) < profiles_count
        assert crawler_task_mock.call_count == len(profile_ids_to_call)
        for run in range(len(profile_ids_to_call)):
            crawler_task_mock.assert_any_call(
                queue='test_queue_name',
                kwargs={
                    'klass_name': 'KeywordClassifier',
                    'profile_id': instagram_profiles[run].id,
                    'task_type': 'pipeline',
                    'route': [
                        'KeywordClassifier',
                        'DescriptionLengthClassifier',
                        'OnlyBloggersProcessor',
                    ]
                }
            )

    def test_no_data_no_profiles(self, _, crawler_task_mock, pipeline):
        pipeline.run_pipeline()
        assert not crawler_task_mock.called

    def test_no_data_no_friends(self, _, crawler_task_mock, pipeline):
        factories.InstagramProfileFactory.create_batch(4)
        pipeline.run_pipeline()
        assert not crawler_task_mock.called

    def test_no_data(self, _, crawler_task_mock, pipeline):
        factories.InstagramProfileFactory()
        factories.InstagramProfileFactory(
            friends_count=pipeline.DEFAULT_MINIMUM_FRIENDS_COUNT - 1
        )
        profiles_to_use = [
            factories.InstagramProfileFactory(
                friends_count=pipeline.DEFAULT_MINIMUM_FRIENDS_COUNT
            ),
            factories.InstagramProfileFactory(
                friends_count=pipeline.DEFAULT_MINIMUM_FRIENDS_COUNT + 1
            ),
        ]
        pipeline.run_pipeline()
        assert crawler_task_mock.call_count == len(profiles_to_use)
        for run in range(len(profiles_to_use)):
            crawler_task_mock.assert_any_call(
                queue='test_queue_name',
                kwargs={
                    'klass_name': 'KeywordClassifier',
                    'profile_id': profiles_to_use[run].id,
                    'task_type': 'pipeline',
                    'route': [
                        'KeywordClassifier',
                        'DescriptionLengthClassifier',
                        'OnlyBloggersProcessor',
                    ]
                }
            )


@pytest.mark.unittest
@pytest.mark.parametrize(
    'pipeline,expected_elements_types',
    [
        (
            pipelines.SEAPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorSEA,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.AustraliaPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorAustralia,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.CanadaPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorCanada,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.GermanyPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorGermany,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.TravelPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorTravel,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.FashionPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorFashion,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.DecorPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorDecor,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.MenFashionPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorMenFashion,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.FoodPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorFood,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.MommyPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorMommy,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.HaveYoutubePipeline,
            [
                HaveYoutubeUrlClassifier,
                HaveYoutubeUrlProcessor,
            ],
        ),
        (
            pipelines.HaveYoutubeDiscoverUrlsPipeline,
            [
                HaveYoutubeDetectSocialUrlsProcessor,
            ],
        ),
        (
            pipelines.HaveYoutubeDiscoverPlatformsPipeline,
            [
                HaveYoutubeDetectExistingPlatformsProcessor,
            ],
        ),
        (
            pipelines.ConnectInstagramProfilesToInfluencersPipeline,
            [
                DetectSocialUrlsProcessor,
                DetectExistingPlatformsProcessor,
                LightUpgrader,
                LightExtraDataUpgrader,
            ],
        ),
        (
            pipelines.BasicClassifierPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.LifestylePipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorLifestyle,
                OnlyBloggersProcessor,
            ],
        ),
        (
            pipelines.HealthFitnessPipeline,
            [
                KeywordClassifier,
                DescriptionLengthClassifier,
                ProcessorHealthFitness,
                OnlyBloggersProcessor,
            ],
        ),
    ]
)
def test_pipelines(pipeline, expected_elements_types):
    assert [
        type(eval(pipeline_element)()) for pipeline_element in
        pipeline.PIPELINE_ROUTE
    ] == expected_elements_types
