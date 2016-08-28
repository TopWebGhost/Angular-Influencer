from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from datetime import datetime
from functools import wraps


log = logging.getLogger('platformdatafetcher.activity_levels')


def recalculate_activity_level(action):
    """
    Recalculate platform activity level after fetching posts.

    Decorate fetcher classes' fetch_posts methods.
    """
    @wraps(action)
    def wrapper(self, *args, **kwargs):
        try:
            return action(self, *args, **kwargs)
        finally:
            platform = self.platform
            try:
                platform.calculate_activity_level()
                platform.last_fetched = datetime.utcnow()
                platform.save()
            except:
                log.exception('Calculating activity level for platform {} failed.'.format(platform.pk))
                # log.exception('Calculating activity level for platform failed.',
                #               extra={'platform_id': platform.pk})

            try:
                influencer = platform.influencer
                influencer.calculate_activity_level()
                influencer.save()
            except:
                log.exception('Calculating activity level for influencer {} failed.'.format(influencer.pk))
                # log.exception('Calculating activity level for influencer failed.',
                #               extra={'influencer_id': influencer.pk if 'influencer' in locals() else None})
    return wrapper
