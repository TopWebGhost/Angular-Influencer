import pytest

from debra.models import Platform


@pytest.mark.unittest
class TestPlatfrom:
    @pytest.mark.parametrize(
        'url,is_social',
        (
            ('', None,),
            (None, None,),
            # bloglovin
            ('https://www.bloglovin.com/', True,),
            ('https://bloglovin.com/', True,),
            ('http://bloglovin.com/', True,),
            ('//bloglovin.com/', True,),
            ('bloglovin.com', True,),
            ('http://frame.bloglovin.com/?post=5101820213', True,),
            ('http://mybloglovin.com/', False,),
            ('http://bloglovingcom', False,),
            ('http://bloglovin.ru', False,),
            # facebook
            ('https://www.facebook.com', True,),
            ('http://www.facebook.com/', True,),
            ('https://www.facebook.com/events/886698974767653/', True,),
            ('https://www.facebook.com/aikikode', True,),
            ('https://facebook/facebook.com/', False,),
            # fashiolista
            ('http://www.fashiolista.com/#!/', True,),
            # google plus
            ('https://plus.google.com/', True,),
            ('https://plus.google.com/u/0/18187086772494274593/posts', True,),
            ('https://gplus.com/', False,),
            # instagram
            ('https://www.instagram.com/karting.drive/', True,),
            ('http://instagram.com', True,),
            ('http://ainstagram.com', False,),
            # lookbook
            ('http://lookbook.nu/', True,),
            ('http://lookbook.nu/themysteriousgirl', True,),
            ('http://lookbook.ru/', False,),
            # pinterest
            ('https://pinterest.com', True,),
            ('https://ru.pinterest.com/', True,),
            ('https://pinterest.ru/', False,),
            # tumblr
            ('https://www.tumblr.com/', True,),
            ('http://allways-lovingyou.tumblr.com/post/14910/donteens', True,),
            # twitter
            ('https://twitter.com', True,),
            ('https://twitter.com/JimCarrey', True,),
            ('twitter.gov', False,),
            # youtube
            ('http://youtube.com', True,),
            ('https://www.youtube.com/ch/UCDsO-0Yo5zpJk575nKXgMVA', True,),
            ('https://ssyoutube.com/watch?=5zpJk575nKXgMVA', False,),
        )
    )
    def test_is_social_platform(self, url, is_social):
        assert Platform.is_social_platform(url) is is_social
