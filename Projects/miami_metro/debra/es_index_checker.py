from debra.models import Influencer, Posts
import time
import json
import logging
from datetime import datetime, timedelta

from debra.constants import ELASTICSEARCH_URL, ELASTICSEARCH_INDEX

from debra.elastic_search_helpers import make_es_get_request

# logger = logging.getLogger('debra.es_index_checker')

logger = logging.getLogger('comparing')
hdlr = logging.FileHandler('es_index_checker_%s.log' % datetime.now().strftime("%Y%m%d_%H%M%S"))
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)


# an hour when indexing occurs, in (0..23) interval
INDEXING_HOUR = 2

# URL for post index
POST_INDEX_URL = "%s/%s/post/" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)

# This is a value of maximum posts allowed to be unindexed for an influencer to skip him.
SAFE_MARGIN = 0


def index_unindexed_posts(since=0, to=1000, to_save=False):
    """
    This function finds delta of unindexed posts between total indexed posts of influencer in ES and DB and
    sets their last_modified to corresponding date, so they will be indexed at the nearest time.

    :return:
    """

    # Marking a time of start
    start_time = time.time()

    # Counters
    ctr_total_infs_performed = 0
    ctr_inf_fully_indexed = 0  # number of already synchronized
    ctr_bad_http_status = 0  # bad http status
    ctr_inf_to_reindex = 0

    ctr_posts_to_reindex = 0

    # Determining datetime earlier of which we're inspecting posts
    margin_date = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    es_margin_date = margin_date.strftime("%Y-%m-%dT%H:%M:%S.000000")

    # Fetching influencers' ids that should be checked
    # inf_ids_to_check = Influencer.objects.filter(show_on_search=True)\
    #     .exclude(blacklisted=True).order_by('id').values_list('id', flat=True)[since:to]

    # We're trying to perform top 5000 most popular influencers
    inf_ids_to_check = Influencer.objects.filter(show_on_search=True, score_popularity_overall__isnull=False).exclude(blacklisted=True).order_by('-score_popularity_overall').values_list('id', flat=True)[since:to]

    ctr_total_infs_to_check = len(inf_ids_to_check)
    logger.info('Total influencers to check: %s' % ctr_total_infs_to_check)

    # performing all influencers
    for inf_id in inf_ids_to_check:
        t = time.time()
        logger.info('Performing influencer %s' % inf_id)
        # TODO: Do we need to confirm if this influencer is already indexed?

        # getting DB Posts count for this influencer
        # TODO: We're fetching only posts whose platform does not have set platform__url_not_found=True
        db_count = Posts.objects.filter(influencer_id=inf_id,
                                        last_modified__lt=margin_date).exclude(platform__url_not_found=True).count()

        # getting ES Posts count
        es_count = None
        es_query = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {
                                "nested": {
                                    "path": "influencer",
                                    "filter": {
                                        "term": {
                                            "influencer.influencer_id": inf_id
                                        }
                                    }
                                }
                            },
                            {
                                "range": {
                                    "last_modified": {
                                        "lt": es_margin_date
                                    }
                                }
                            }
                        ]
                    },
                    "query": {
                        "match_all": {}
                    }
                }
            }
        }

        rq = make_es_get_request(
            es_url="%s/_count" % POST_INDEX_URL,
            es_query_string=json.dumps(es_query)
        )

        if rq.status_code == 200:
            resp = rq.json()
            es_count = resp.get("count", None)

            # if es_count is lower than db_count, we're fetching all indexed post ids
            if db_count > es_count:
                logger.info('Influencer %s has %s posts, with: %s indexed, %s not indexed.' % (inf_id,
                                                                                               db_count,
                                                                                               es_count,
                                                                                               db_count-es_count))

                indexed_post_ids = []
                if es_count > 0:
                    for part in range(0, (es_count / 1000 + 1)):

                        # Getting post ids
                        es_query = {
                            "sort": [
                                "_id"
                            ],
                            "fields": [],
                            "from": part*1000,
                            "query": {
                                "filtered": {
                                    "filter": {
                                        "and": [
                                            {
                                                "nested": {
                                                    "path": "influencer",
                                                    "filter": {
                                                        "term": {
                                                            "influencer.influencer_id": inf_id
                                                        }
                                                    }
                                                }
                                            },
                                            {
                                                "range": {
                                                    "last_modified": {
                                                        "lt": es_margin_date
                                                    }
                                                }
                                            }
                                        ]
                                    },
                                    "query": {
                                        "match_all": {}
                                    }
                                }
                            },
                            "size": 1000
                        }

                        rq = make_es_get_request(
                            es_url="%s/_search" % POST_INDEX_URL,
                            es_query_string=json.dumps(es_query),
                        )

                        if rq.status_code == 200:
                            resp = rq.json()

                            # list of posts' ids existing in ES
                            for entry in resp.get("hits", {}).get("hits", []):
                                if entry.get('_id') is not None:
                                    indexed_post_ids.append(entry.get('_id'))

                logger.info("Total posts ids fetched from ES: %s" % len(indexed_post_ids))

                # updating last_modified of the remaining posts that are unindexed
                unindexed_posts = Posts.objects.filter(
                    influencer_id=inf_id,
                    last_modified__lt=margin_date
                ).exclude(platform__url_not_found=True).exclude(id__in=indexed_post_ids)
                # for p in unindexed_posts:
                #     print(' * id: %s  date: %s' % (p.id, p.last_modified))

                logger.info('Unindexed posts fetched: %s' % unindexed_posts.count())

                if to_save:
                    # UPDATING last_modified of posts
                    updated = unindexed_posts.update(last_modified=datetime.now())
                    logger.info('Scheduled %s posts for indexing' % updated)
                    ctr_posts_to_reindex += updated

                    # UPDATING last_modified of the influencer
                    i = Influencer.objects.get(id=inf_id)
                    i.last_modified = datetime.now()
                    i.save()

                # ctr_posts_to_reindex += updated

                ctr_inf_to_reindex += 1

            elif db_count == es_count:

                if db_count == es_count:
                    logger.info('Influencer %s has %s posts, with: all %s are indexed.' % (inf_id,
                                                                                           db_count,
                                                                                           es_count))
                    ctr_inf_fully_indexed += 1

            else:

                logger.info('Influencer %s has %s posts, with: %s are indexed and some will be reindexed.' % (inf_id,
                                                                                                              db_count,
                                                                                                              es_count))
                ctr_inf_fully_indexed += 1

        else:
            logger.error('Influencer %s has %s posts, with: %s indexed. Received HTTP status: %s' % (inf_id,
                                                                                                     db_count,
                                                                                                     es_count,
                                                                                                     rq.status_code))

            ctr_bad_http_status += 1

        ctr_total_infs_performed += 1

        logger.info('Influencer has been performed for %s sec' % int(time.time() - t))

    end_time = time.time()

    logger.info('Finished. Took %s seconds.' % int(end_time - start_time))
    logger.info('Total influencers fetched: %s' % ctr_total_infs_to_check)
    logger.info('Total influencers performed: %s' % ctr_total_infs_performed)
    logger.info('Influencers totally indexed: %s' % ctr_inf_fully_indexed)
    logger.info('Influencers with remaining posts set to indexing: %s' % ctr_inf_to_reindex)
    logger.info('Posts set to indexing: %s' % ctr_posts_to_reindex)
    logger.info('Influencers with bad http status: %s' % ctr_bad_http_status)