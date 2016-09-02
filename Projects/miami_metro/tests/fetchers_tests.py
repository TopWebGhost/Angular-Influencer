# -*- coding: utf-8 -*-
import unittest
from django.contrib.sites.models import Site
from django.conf import settings
from debra.models import Platform, Influencer


class FetcherTestCase(unittest.TestCase):
    def setUp(self):
        print settings.DATABASES['default']['HOST']
        if not settings.DATABASES['default']['HOST'] in ('127.0.0.1', 'localhost', ''):
            raise RuntimeError('This test case shouldn\'t be run on production database.')

        Site.objects.get_or_create(id=settings.SITE_ID)


class FacebookFetcherTestCase(FetcherTestCase):
    def test(self):
        from platformdatafetcher.fetchertasks import fetch_platform_data
        from platformdatafetcher.postprocessing import FetchAllPolicy

        # platform = Platform.objects.create(
        #     platform_name='Facebook',
        #     influencer=Influencer.objects.create(),
        #     url=u'https://www.facebook.com/lina.paramita.18'
        # )
        # fetch_platform_data(platform.id, policy_instance=FetchAllPolicy())

        # platform = Platform.objects.create(
        #     platform_name='Facebook',
        #     influencer=Influencer.objects.create(),
        #     url=u'https://www.facebook.com/BananaRepublic'
        # )
        # fetch_platform_data(platform.id, policy_instance=FetchAllPolicy())

        platform = Platform.objects.create(
            platform_name='Facebook',
            influencer=Influencer.objects.create(),
            url=u'https://www.facebook.com/LeopardandLillies'
        )
        fetch_platform_data(platform.id, policy_instance=FetchAllPolicy())


class InstagramFetcherTestCase(FetcherTestCase):
    def test(self):
        from platformdatafetcher.fetchertasks import fetch_platform_data
        from platformdatafetcher.postprocessing import FetchAllPolicy

        platform = Platform.objects.create(
            platform_name='Instagram',
            influencer=Influencer.objects.create(),
            url=u'http://instagram.com/courtsieannb'
        )
        fetch_platform_data(platform.id, policy_instance=FetchAllPolicy())


class YoutubeFetcherTestCase(FetcherTestCase):
    def test(self):
        from platformdatafetcher.postprocessing import FetchAllPolicy
        from platformdatafetcher.videohostingfetcher import YoutubeFetcher

        platform = Platform.objects.create(
            platform_name='Youtube',
            influencer=Influencer.objects.create(),
            url=u'https://www.youtube.com/user/babs80'
        )
        fetcher = YoutubeFetcher(platform, FetchAllPolicy())
        self.assertEquals(fetcher.platform.num_following, 119)

        platform = Platform.objects.create(
            platform_name='Youtube',
            influencer=Influencer.objects.create(),
            url=u'https://www.youtube.com/user/Ezechiel2012'
        )
        fetcher = YoutubeFetcher(platform, FetchAllPolicy())
        self.assertEquals(fetcher.platform.num_following, 8)
        self.assertEquals(fetcher.platform.url, 'https://www.youtube.com/user/Ezechiel2012')
        self.assertEquals(fetcher.platform.profile_img_url, '//i.ytimg.com/i/_VrftHgnXOByJdtTwQMA9A/mq1.jpg?v=bc675c')
        self.assertEquals(fetcher.platform.blogname, 'Kanaal van Ezechiel2012')
        posts = fetcher.fetch_posts()
        self.assertEquals(len(posts), 67)
        post_urls = [post.url for post in posts]
        self.assertTrue('https://youtube.com/watch?v=Mb5QWt_EyM4' in post_urls)
        post_titles = [post.title for post in posts]
        self.assertTrue('Aura - New Circuitry' in post_titles)
        post_impressions = [post.impressions for post in posts]
        # self.assertTrue(1013 in post_impressions)
        post_num_comments = [post.ext_num_comments for post in posts]
        # self.assertTrue(18 in post_titles)

        