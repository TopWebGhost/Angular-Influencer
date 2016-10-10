from debra import models
from xpathscraper import utils
from django.db.models import Sum, Q
import logging
utils.log_to_stderr()
log = logging.getLogger('main')

inf = models.Platform.objects.get(id=125095).influencer

log.info('Computing total_popularity')
total_popularity = models.Platform.objects.filter(influencer__show_on_search=True).aggregate(num_followers_total=Sum('num_followers'))['num_followers_total']

log.info('Computing total_engagement')
total_engagement = models.Platform.objects.filter(influencer__show_on_search=True).aggregate(engagement_overall=Sum('score_engagement_overall'))['engagement_overall']

log.info('Running denormalization')

inf.denormalize(total_popularity, total_engagement)

log.info('Done')
