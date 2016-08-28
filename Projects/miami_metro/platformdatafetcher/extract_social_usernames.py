#!/usr/bin/env python
"""
Module target is to extract social platform usernames or urls from profile
description

E.g. given the description:
    'Twitter: @annadellorusso Snap: annadellorusso'
We need to get usernames per platform:
    {
        'twitter': {'annadellorusso'},
        'snapchat': {'annadellorusso'},
    }
This should work for complex cases with platforms as unicode icons or user
having same username for several platforms:
    'Hi all, my Twitter/FB/Snap is welc0m4'
    ->
    {
        'twitter': {'welc0m4'},
        'facebook': {'welc0m4'},
        'snapchat': {'welc0m4'},
    }
"""

import re


class SOCIAL_PLATFORMS:
    FACEBOOK = 'facebook'
    INSTAGRAM = 'instagram'
    PINTEREST = 'pinterest'
    SNAPCHAT = 'snapchat'
    TUMBLR = 'tumblr'
    TWITTER = 'twitter'
    LOOKBOOK = 'lookbook'
    VINE = 'vine'
    YOUTUBE = 'youtube'

    ALL = (
        FACEBOOK,
        INSTAGRAM,
        PINTEREST,
        SNAPCHAT,
        TUMBLR,
        TWITTER,
        LOOKBOOK,
        VINE,
        YOUTUBE,
    )


SOCIAL_PLATFORMS_URLS = {
    SOCIAL_PLATFORMS.FACEBOOK: 'https://www.facebook.com/{}',
    SOCIAL_PLATFORMS.INSTAGRAM: 'https://www.instagram.com/{}/',
    SOCIAL_PLATFORMS.PINTEREST: 'https://www.pinterest.com/{}/',
    SOCIAL_PLATFORMS.TUMBLR: 'http://{}.tumblr.com/',
    SOCIAL_PLATFORMS.TWITTER: 'https://twitter.com/{}',
    SOCIAL_PLATFORMS.LOOKBOOK: 'http://lookbook.nu/{}',
    SOCIAL_PLATFORMS.VINE: 'https://vine.co/{}',
    SOCIAL_PLATFORMS.YOUTUBE: 'https://www.youtube.com/user/{}',
}
# Text that users usually put in their profile before the username
# e.g. 'My fb is annadeloru; youtube: andelor'
SOCIAL_MARKERS = {
    SOCIAL_PLATFORMS.FACEBOOK: ('facebook', 'fb', 'fbook',),
    SOCIAL_PLATFORMS.INSTAGRAM: ('instagram', 'insta', 'ig',),
    SOCIAL_PLATFORMS.PINTEREST: ('pinterest', 'pt',),
    SOCIAL_PLATFORMS.SNAPCHAT: ('snapchat', 'sc', 'snap', 'schat',),
    SOCIAL_PLATFORMS.TUMBLR: ('tumblr', 'tb',),
    SOCIAL_PLATFORMS.TWITTER: ('twitter', 'tweet', 'tw',),
    SOCIAL_PLATFORMS.LOOKBOOK: ('lookbook', 'lb',),
    SOCIAL_PLATFORMS.VINE: ('vine',),
    SOCIAL_PLATFORMS.YOUTUBE: ('youtube', 'utube', 'yt',),
}

# People may use icons instead of platform name (more common for twitter)
SOCIAL_PLATFORMS_ICONS = {
    '@': SOCIAL_PLATFORMS.TWITTER,
    u'\U0001f3ac': SOCIAL_PLATFORMS.YOUTUBE,  # clapperboard
    u'\U0001f426': SOCIAL_PLATFORMS.TWITTER,  # bird
    u'\U0001f47b': SOCIAL_PLATFORMS.SNAPCHAT,  # ghost
}

# Some special words to skip from processing, e.g.:
# 'Hey, my youtube CHANNEL is reloK4des'
WORDS_TO_SKIP = {
    'blog', 'blogs', 'blogger', 'bloggers',
    'channel', 'channels' 'chat',
    'editor', 'email',
    'gmail', 'gmail.com',
    'join',
    'mail',
    'periscope', 'pscope',
    'subscribe',
    'tutorial', 'tutorials',
    'user', 'username',
    'video', 'videos', 'view', 'views',
    'watch', 'with',
    'youtuber',
}

USERNAME_PATTERN = '[a-z_]+[\w\-.]*\w+'
MIN_USERNAME_LENGTH = 4


def to_unicode(text=''):
    if not isinstance(text, unicode):
        return text.decode('utf-8')
    return text


def _get_regex_block_from_social_markers(platform_name):
    regex_blocks = []
    if not platform_name or platform_name not in SOCIAL_MARKERS:
        return
    for marker in SOCIAL_MARKERS[platform_name]:
        regex_blocks.append('(?<=\s{})'.format(marker))
    return regex_blocks


def _get_social_platform_username_regex(platform_name):
    regex_blocks = _get_regex_block_from_social_markers(platform_name)
    if not regex_blocks:
        return
    return re.compile(
        '(?:(?:{}) )({})'.format(
            '|'.join(regex_blocks), USERNAME_PATTERN
        ), flags=re.IGNORECASE
    )


def _icons_to_social_handles(text):
    for platform_icon, platform_name in SOCIAL_PLATFORMS_ICONS.iteritems():
        text = to_unicode(text).replace(
            platform_icon, ' {} '.format(platform_name)
        )
    return collapse_spaces(text)


def extract_ascii(text):
    return re.sub(r'[^\w\-.]+', ' ', text)


def collapse_spaces(text):
    return (re.sub(r'\s+', ' ', text)).strip()


def remove_short_words(text, min_length=MIN_USERNAME_LENGTH, exceptions=None):
    result_words = []
    exceptions = exceptions or []
    for word in text.split():
        if len(word) >= min_length or word in exceptions:
            result_words.append(word)
    return ' '.join(result_words)


def remove_invalid_words(text):
    # that have @ not at the start or start with a number, dot or dash
    return collapse_spaces(
        re.sub(
            r'(?<=\s)(([\w\-.]+@+[@\w\-.]*)|([0-9.\-]+\w*))(\s|\Z)', ' ',
            u' {}'.format(to_unicode(text))
        )
    )


def _clean_text(text, platform_name):
    platform_social_markers = SOCIAL_MARKERS.get(platform_name, [])
    text = remove_words(
        remove_short_words(
            extract_ascii(
                _icons_to_social_handles(
                    remove_invalid_words(text)
                )
            ).lower(), exceptions=platform_social_markers
        ),
        _get_words_blacklist(platform_name)
    )
    # Collapse several same social platform handlers to one:
    # 'twitter twitter hello tw twitter' -> 'twitter hello twitter'
    if platform_social_markers:
        # First rename all social markers to 'main' marker:
        # 'twitter tw hello tweet' -> 'twitter twitter hello twitter'
        # And then collapse same markers in a row
        # 'twitter twitter hello twitter' -> 'twitter hello twitter'
        main_platrom_marker = platform_social_markers[0]
        text = re.sub(
            r'\b({}(\Z|\s))+'.format(main_platrom_marker),
            '{} '.format(main_platrom_marker),
            re.sub(
                r'\b({})\b'.format('|'.join(platform_social_markers)),
                main_platrom_marker,
                text
            )
        )
    # Prepend space before the text to allow lookahead space expressions
    return u' {}'.format(to_unicode(text))


def remove_words(text, words_to_remove):
    return collapse_spaces(
        re.sub(
            r'(?<=\s)({})(\s|\Z)'.format('|'.join(words_to_remove)), ' ',
            u' {}'.format(to_unicode(text))
        )
    )


def _get_words_blacklist(platform_name):
    markers = []
    for platform in SOCIAL_MARKERS:
        if platform == platform_name:
            continue
        markers.extend(SOCIAL_MARKERS[platform])
    return list(set(markers) | WORDS_TO_SKIP)


def get_url_for_username(username, platform_name):
    url_template = SOCIAL_PLATFORMS_URLS.get(platform_name)
    if not url_template:
        return
    return url_template.format(username)


def find_platform_usernames(text, platform_name):
    """
    Get set of usernames for the specified platform found in text
    :param text:
    :param platform_name:
    :return:  set of platform usernames
    """
    return set(
        _get_social_platform_username_regex(platform_name).findall(
            _clean_text(text, platform_name),
        )
    )


def find_usernames_per_platform(text):
    """
    Get dict of found platforms usernames
    :param text:  profile description
    :return:  dictionary of found platform names and set of usernames for each
    """
    social_usernames = {}
    for platform_name in SOCIAL_PLATFORMS.ALL:
        usernames = find_platform_usernames(
            text, platform_name
        )
        if usernames:
            social_usernames[platform_name] = usernames
    return social_usernames


def find_all_usernames(text):
    """
    Extract usernames for all platforms from given text
    :param text:
    :return: set of usernames extracted
    """
    social_usernames = set()
    for platform_name in SOCIAL_PLATFORMS.ALL:
        social_usernames |= find_platform_usernames(
            text, platform_name
        )
    return social_usernames


def get_profile_urls_from_usernames(text):
    """
    Get a set of profile URLs created from usernames found in text
    :param text:  profile description
    :return:  set of URLs
    """
    social_urls = []
    for platform_name in SOCIAL_PLATFORMS.ALL:
        usernames = find_platform_usernames(
            text, platform_name
        )
        if not usernames:
            continue
        urls = filter(
            lambda u: u,
            [
                get_url_for_username(
                    username, platform_name
                ) for username in usernames
            ]
        )
        if not urls:
            continue
        social_urls.extend(urls)
    return set(social_urls)


if __name__ == '__main__':
    import sys
    print find_usernames_per_platform(sys.argv[1])
