import random

from factory import DjangoModelFactory, Faker

from debra.models import Platform


class InfluencerFactory(DjangoModelFactory):
    class Meta:
        model = 'debra.Influencer'

    name = Faker('name')


class PlatformFactory(DjangoModelFactory):
    class Meta:
        model = 'debra.Platform'

    platform_name = random.choice(Platform.ALL_PLATFORMS)
