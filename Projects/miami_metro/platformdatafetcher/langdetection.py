"""Detects a language for a platform (blog) and saves results into
:attr:`debra.models.Platform.content_lang`. It uses Python package
``guess_language``.
"""


import logging
import collections

import baker
from celery.decorators import task

from xpathscraper import utils
from xpathscraper import xutils
from debra import models
from platformdatafetcher import platformutils


log = logging.getLogger('platformdatafetcher.langdetection')

POSTS_TO_CHECK = 10
MIN_DETECTED_FACTOR = 0.5


def detect_language(content):
    # import is inside the function, because it takes noticeable time
    import guess_language

    return guess_language.guessLanguage(content)

@task(name='platformdatafetcher.langdetection.detect_platform_lang', ignore_result=True)
@baker.command
def detect_platform_lang(platform_id):
    platform = models.Platform.objects.get(id=int(platform_id))
    with platformutils.OpRecorder(operation='detect_platform_lang', platform=platform) as opr:
        posts = platform.posts_set.all()[:POSTS_TO_CHECK]
        if len(posts) < MIN_DETECTED_FACTOR * POSTS_TO_CHECK:
            log.warn('Not enough posts to check: %d', len(posts))
            return
        langs = []
        for p in posts:
            if not p.content:
                continue
            text = xutils.strip_html_tags(p.content)
            lang = detect_language(text)
            log.info('Lang %r detected from content %r', lang, text)
            langs.append(lang)
        log.info('All langs: %r', langs)
        valid_langs = [l for l in langs if l != 'UNKNOWN']
        if not valid_langs:
            log.warn('Cannot detect language for any post')
            return
        lang_counter = collections.Counter(valid_langs)
        most_common_lang, most_common_counter = lang_counter.most_common(1)[0]
        log.info('Most common lang: %r, count: %d', most_common_lang, most_common_counter)
        if most_common_counter >= len(posts) * MIN_DETECTED_FACTOR:
            log.info('Count is high enough to set content_lang')
            platform.content_lang = most_common_lang
            platform.save()
        else:
            log.warn('Count IS NOT high enough to set content_lang')


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
