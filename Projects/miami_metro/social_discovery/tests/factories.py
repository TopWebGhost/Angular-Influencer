from factory import DjangoModelFactory, Faker


class InstagramProfileFactory(DjangoModelFactory):
    class Meta:
        model = 'social_discovery.InstagramProfile'

    username = Faker('user_name')
