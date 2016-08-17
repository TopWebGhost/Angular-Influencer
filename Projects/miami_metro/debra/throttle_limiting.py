import time
import logging
from mongo_utils import get_brand_throttle_track_col

log = logging.getLogger('throttle limiting')


TIMESPAN_DAY = 60*60*24
TIMESPAN_WEEK = TIMESPAN_DAY*7
TIMESPAN_MONTH = TIMESPAN_DAY*30

TIMESPANS = (
    TIMESPAN_DAY,
    TIMESPAN_WEEK,
    TIMESPAN_MONTH
)

QUERY_TYPE_SEARCH_BLOGGERS_JSON = 0

ACTION_NONE = 'none'
ACTION_EMAIL = 'email'
ACTION_LOCK = 'lock'

#lower = more important
ACTION_PRIORITIES = {
    ACTION_LOCK: 0,
    ACTION_EMAIL: 1,
}


def throttle_track(brand, query_type, timestamp=None):
    """
    Args:
        brand (Brands): requesting brand
        query_type (int): int from enumeration of all possible query types
        timestamp (int): if set it will overwrite default value which is time of making this call
    Returns:
        None

    It saves that data into mongo collection 'brand_throttle_track' as json document

    {
        'brand': brand.id as int,
        'queries': [
            {
            'ts': time unix timestamp as int,
            'type': query_type as int
            }, ...
        ]
    }

    """

    if not timestamp:
        timestamp = time.time()

    collection = get_brand_throttle_track_col()
    if not collection:
        log.error("No collection to track brand query limits")
        return

    key_data = {
        'brand': int(brand.id),
    }

    output_data = {
        '$push': {
            'queries': {
                'ts': int(timestamp),
                'type': int(query_type)
            }
        }
    }
    collection.update(key_data, output_data, upsert=True)


def throttle_check(brand, query_type, timespan):
    """
    Args:
        brand (Brands): requesting brand
        query_type (int): int from enumeration of all possible query types
        timespan (int): time span as number of seconds from time of this call
    Returns:
        integer: queries count
    It checks how many queries of given type were made during given time span for given brand.
    It makes query for count of nested documents matching check arguments
    """

    collection = get_brand_throttle_track_col()
    if not collection:
        log.error("No collection to track brand query limits")
        return

    ts_limit = int(time.time() - timespan)

    result = collection.aggregate([
        {'$match': {
                'brand': int(brand.id)
            }
        },
        {'$unwind': '$queries'},
        {'$match':
            {
                'queries.type': int(query_type),
                'queries.ts': {'$gt': ts_limit}
            }
        },
        {'$group':
            {
                '_id': None,
                'count': {'$sum': 1}
            }
        }
    ])

    if len(result["result"]) == 0:
        return 0
    else:
        return result["result"][0]["count"]


def throttle_brand_query(brand, query_type, log=True):
    """
    Args:
        brand (Brands): requesting brand
        query_type (int): int from enumeration of all possible query types
        log (bool): should it log current query type call also?
    Returns:
        string: highest priority action to take, one of actions enumeration
    It checks query throttle for given brand of given query type and returns
    action which should be made. By default it also logs given query_type call,
    to prevent it use keyword argument log=False
    """

    if log:
        try:
            throttle_track(brand, query_type)
        except:
            pass

    #limits are hardcoded now
    checks = [
        {
        "query": QUERY_TYPE_SEARCH_BLOGGERS_JSON,
        "timespan": TIMESPAN_DAY,
        "limit": 200,
        "action": "email"
        },
        {
        "query": QUERY_TYPE_SEARCH_BLOGGERS_JSON,
        "timespan": TIMESPAN_WEEK,
        "limit": 1000,
        "action": "email"
        },
        {
        "query": QUERY_TYPE_SEARCH_BLOGGERS_JSON,
        "timespan": TIMESPAN_MONTH,
        "limit": 2000,
        "action": "email"
        },
        {
        "query": QUERY_TYPE_SEARCH_BLOGGERS_JSON,
        "timespan": TIMESPAN_DAY,
        "limit": 400,
        "action": "lock"
        },
        {
        "query": QUERY_TYPE_SEARCH_BLOGGERS_JSON,
        "timespan": TIMESPAN_WEEK,
        "limit": 2000,
        "action": "lock"
        },
        {
        "query": QUERY_TYPE_SEARCH_BLOGGERS_JSON,
        "timespan": TIMESPAN_MONTH,
        "limit": 4000,
        "action": "lock"
        }
    ]

    action = ACTION_NONE
    c_priority = 999999

    calls = {}
    for span in TIMESPANS:
        try:
            calls[span] = throttle_check(brand, query_type, span)
        except:
            calls[span] = 0

    for check in checks:
        if check["query"] == query_type:
            if calls[check["timespan"]] > check["limit"]:
                if ACTION_PRIORITIES[check["action"]] < c_priority:
                    action = check["action"]
    return action
