import pytest

from platformdatafetcher import platformutils


@pytest.mark.unittest
@pytest.mark.parametrize(
    'url,username',
    (
        ('http://pinterest.com/chasingdavies/','chasingdavies',),
        ('http://pinterest.com/chasingdavies', 'chasingdavies',),
        ('http://www.facebook.com/ASpoonfulOfStyle', 'aspoonfulofstyle',),
        ('https://www.facebook.com/ChasingDavies?ref=hl', 'chasingdavies',),
        (
            'https://www.facebook.com/pages/Flourish-Boutique-Gallery',  # noqa
            'flourish-boutique-gallery',
        ),
        (
            'https://www.facebook.com/pages/Fawn-Over-Baby?ref=hl',  # noqa
            'fawn-over-baby',
        ),
        (
            'http://www.bloglovin.com/blog/10218643/the-modern-tulip',
            'the-modern-tulip',
        ),
        ('http://www.bloglovin.com/en/blog/2676832', '2676832',),
        ('http://www.bloglovin.com/en/blog/2676832/', '2676832',),
        ('http://www.bloglovin.com/lovesparklepretty', 'lovesparklepretty',),
        ('http://www.instagram.com/@inesjunqueira', 'inesjunqueira',),
        (
            'https://www.facebook.com/profile.php?id=100001409395843',
            '100001409395843',
        ),
        ('http://instagram.com/shannasaidso/#', 'shannasaidso',),
        ('http://instagram.com/shannasaidso#', 'shannasaidso',),
        ('http://instagram.com/#!/shannasaidso', 'shannasaidso',),
        ('http://instagram.com/#!/shannasaidso#', 'shannasaidso',),
        ('http://twitter.com/#!/BoltClock', 'boltclock',),
        (
            'http://www.facebook.com/example.profile#!/pages/Another-Page/123456789012345',  # noqa
            'another-page',
        ),
        ('http://www.pinterest.com/a123/boards/', 'a123',),
        ('http://pinterest.com/', None,),
        (
            'https://plus.google.com/109796464680653194827',
            '109796464680653194827',
        ),
        ('https://plus.google.com/+CarliBel55', 'carlibel55',),
        (
            'https://plus.google.com/share?url=http%3A%2F%2Fwww.parajunkee.net%2Fcontact%2F&t=Contact',  # noqa
            None,
        ),
        ('https://plus.google.com/communities/114406777175383049862', None,),
        ('//plus.google.com/111829613489253728023', '111829613489253728023',),
        (
            'https://www.youtube.com/channel/UCzT17-Lvc5L_gIT10JQsjSA',
            'UCzT17-Lvc5L_gIT10JQsjSA'
        ),
        ('https://www.youtube.com/user/C0OK1EMONSTER', 'c0ok1emonster'),
        ('https://www.youtube.com/c/C0OK1EMONSTER', 'c0ok1emonster'),
    )
)
def test_username_from_platform_url(url, username):
    assert platformutils.username_from_platform_url(url) == username
