# -*- coding: utf-8 -*-
import pytest

from platformdatafetcher.extract_social_usernames import (
    find_usernames_per_platform,
)


@pytest.mark.unittest
class TestExtractSocialUsernames:
    @pytest.mark.parametrize(
        'text,extracted_usernames',
        (
            ('Join my twitter alikt', {'twitter': {'alikt', }, },),
            ('Hi contact me at @johnk', {'twitter': {'johnk', }, },),
            ('Hi contact me at twitter @johnk', {'twitter': {'johnk', }, },),
            ('@kkkk at twitter @johnk', {'twitter': {'johnk', 'kkkk', }, },),
            (
                "Pigeons & Planes. @cakebox. tonight.",
                {'twitter': {'cakebox', }, },
            ),
            (
                (
                    "MUA•Hairdresser•For tiarni@live.com.au tweet me: "
                    "@_tiarn_ snapchat: tiarnstaples MUA"
                ),
                {'twitter': {'_tiarn_', }, 'snapchat': {'tiarnstaples', }, }
            ),
            (
                (
                    'Pictures on my phone Recording artist @ PC Music '
                    '& Photographer info@hannahdia.com'
                ),
                {'twitter': {'music', }, }
            ),
            (
                'join @555ttt & youtube polkiju',
                {'youtube': {'polkiju', }, }
            ),
            (
                'join @.rrr555ttt & sc polkiju',
                {'snapchat': {'polkiju', }, }
            ),
            (
                'my youtube channel/snapchat & twitter and instagram polkiju',
                {
                    'instagram': {'polkiju', },
                    'twitter': {'polkiju', },
                    'snapchat': {'polkiju', },
                    'youtube': {'polkiju', },
                }
            ),
            (
                'my youtube videos are at polkiju',
                {'youtube': {'polkiju', }, }
            )
        )
    )
    def test_find_usernames_per_platform(self, text, extracted_usernames):
        assert find_usernames_per_platform(text) == extracted_usernames
