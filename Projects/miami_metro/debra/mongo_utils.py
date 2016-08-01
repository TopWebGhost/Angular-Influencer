import time
import logging
import pymongo
import datetime
from django.conf import settings
from debra.constants import INTERCOM_CUSTOM_DATA
from celery.decorators import task

log = logging.getLogger('mongo utils')

# share client in thread
try:
    client = pymongo.MongoClient(settings.MONGO_CONNECTION_STRING, socketTimeoutMS=20000, connectTimeoutMS=20000)
except:
    client = None


def get_db():
    """
    returns tracking database or None if error
    """
    if client:
        return client.app5524706
    else:
        return None


def get_query_tracking_col():
    """
    return queries tracking collection or None if error
    """
    db = get_db()
    if db:
        return db.track_queries
    else:
        return None


def get_visitor_tracking_col():
    """
    return queries tracking collection or None if error
    """
    db = get_db()
    if db:
        return db.track_visitors
    else:
        return None


def get_influencer_counters_col():
    """
    return queries tracking collection or None if error
    """
    db = get_db()
    if db:
        return db.influencer_counters
    else:
        return None


def get_brands_stats_col():
    """
    return brands statistics collection or None if error
    """
    db = get_db()
    if db:
        return db.brands_stats
    else:
        return None

def get_brands_counters_col():
    """
    return brands statistics collection or None if error
    """
    db = get_db()
    if db:
        return db.brands_counters
    else:
        return None


def get_influencer_edit_history_col():
    """
    return brands statistics collection or None if error
    """
    db = get_db()
    if db:
        return db.influencer_edits
    else:
        return None


def get_notifications_col():
    """
    return collection of notifications
    """
    db = get_db()
    if db:
        return db.notifications
    else:
        return None

def get_brand_throttle_track_col():
    """
    return collection of throttle tracking for brand
    """
    db = get_db()
    if db:
        return db.brand_throttle_track
    else:
        return None

@task(name='debra.mongo_utils.track_query_task', ignore_result=True)
def track_query_task(query_type, data, meta):
    """
    takes query type, data and metadata and saves into db
    """
    collection = get_query_tracking_col()
    if not collection:
        log.error("No collection to track query")
        return
    output_data = {
        'query_type': query_type,
        'data': data,
        'meta': meta,
        'ts': time.time()
    }
    collection.insert(output_data)


@task(name='debra.mongo_utils.track_visit_task', ignore_result=True)
def track_visit_task(re_usr_id):
    """
    takes request.visitor instance and saves visit fact
    """
    from debra import models
    from debra import account_helpers

    collection = get_visitor_tracking_col()
    if not collection:
        log.error("No collection to track visit")
        return
    user_id = "anonymous"
    user_email = "anonymous"
    user = None
    brand = None
    if re_usr_id:
        user = models.User.objects.get(id=re_usr_id)
        user_id = re_usr_id
        user_email = user.email
        brand = account_helpers.get_associated_brand(user)

    key_data = {
        'user_id': user_id,
    }
    output_data = {
        '$set': {
            'email': user_email,
            'meta': user and INTERCOM_CUSTOM_DATA(user.userprofile) or None,
            'brand_meta': brand and brand.get_intercom_company_data() or None,
            'last_visit': time.time(),
        },
        '$inc': {'visits': 1}
    }
    collection.update(key_data, output_data, upsert=True)


@task(name='debra.mongo_utils.influencers_appeared_on_search_task', ignore_result=True)
def influencers_appeared_on_search_task(influencer_id_list):
    """
    takes list of ids of influencers who appeared on search
    """
    collection = get_influencer_counters_col()
    if not collection:
        log.error("No collection to track counter change")
        return
    bulk = collection.initialize_ordered_bulk_op()
    for i in influencer_id_list:
        key_data = {
            'influencer_id': i,
        }
        output_data = {
            '$inc': {'appeared_on_search': 1}
        }
        bulk.find(key_data).upsert().update(output_data)
    bulk.execute()


@task(name='debra.mongo_utils.influencer_profile_viewed_task', ignore_result=True)
def influencer_profile_viewed_task(influencer_id):
    """
    tracks fact that influencer profile was viewed
    """
    collection = get_influencer_counters_col()
    if not collection:
        log.error("No collection to track counter change")
        return
    key_data = {
        'influencer_id': int(influencer_id),
    }
    output_data = {
        '$inc': {'profile_views': 1}
    }
    collection.update(key_data, output_data, upsert=True)


@task(name='debra.mongo_utils.influencer_inc_dec_collection_task', ignore_result=True)
def influencer_inc_dec_collection_task(influencer_id, delta):
    """
    tracks fact that influencer profile was viewed
    """
    collection = get_influencer_counters_col()
    if not collection:
        log.error("No collection to track counter change")
        return
    key_data = {
        'influencer_id': int(influencer_id),
    }
    output_data = {
        '$inc': {'in_collections': delta}
    }
    collection.update(key_data, output_data, upsert=True)


@task(name='debra.mongo_utils.influencer_log_edits_task', ignore_result=True)
def influencer_log_edits_task(influencer_id, edits):
    """
    tracks edits of influencer profile
    """
    collection = get_influencer_edit_history_col()
    if not collection:
        log.error("No collection to track influencer edits")
        return
    bulk = collection.initialize_ordered_bulk_op()
    for data in edits:
        data["ts"] = int(datetime.datetime.now().strftime("%s"))

        key_data = {
            'influencer_id': int(influencer_id),
        }

        output_data = {
            '$push': {
                'edits': data
            }
        }
        bulk.find(key_data).upsert().update(output_data)
    bulk.execute()


def track_query(query_type, data, meta):
    track_query_task.apply_async([query_type, data, meta], queue="celery")
    #track_query_task(query_type, data, meta)


def track_visit(request):
    rq_usr_id = request.user.is_authenticated() and request.user.id or None
    track_visit_task.apply_async([rq_usr_id], queue="celery")
    #track_visit_task(rq_usr_id)


def influencers_appeared_on_search(influencer_id_list):
    if influencer_id_list:
        influencers_appeared_on_search_task.apply_async([influencer_id_list], queue="celery")
    #influencers_appeared_on_search_task(influencer_id_list)


def influencer_profile_viewed(influencer_id):
    influencer_profile_viewed_task.apply_async([influencer_id], queue="celery")
    #influencer_profile_viewed_task(influencer_id)


def influencer_inc_dec_collection(influencer_id, delta):
    influencer_inc_dec_collection_task.apply_async([influencer_id, delta], queue="celery")
    #influencer_inc_dec_collection_task(influencer_id, delta)


def influencer_log_edits(influencer_id, edits):
    #influencer_log_edits_task.apply_async([influencer_id, edits], queue="celery")
    influencer_log_edits_task(influencer_id, edits)


def notify_user(user_id, type, message):
    col = get_notifications_col()
    message["type"] = type
    col.update({"user_id": user_id}, {"$inc": {type: 1}, "$push": {"messages": message}}, upsert=True)


def notify_brand(brand_id, type, message):
    from debra.models import Brands, UserProfileBrandPrivilages
    brand = Brands.objects.get(id=brand_id)
    col = get_notifications_col()
    message["type"] = type
    notify_privilages = (
        UserProfileBrandPrivilages.PRIVILAGE_OWNER,
        UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR,
        UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR_UNCONFIRMED,
    )
    profiles = brand.related_user_profiles.filter(permissions__in=notify_privilages)
    output_data = {
        "$inc": {type: 1},
        "$push": {"messages": message}
    }
    bulk = col.initialize_ordered_bulk_op()
    for profile in profiles:
        user = profile.user_profile.user
        key_data = {
            'user_id': user.id,
        }
        bulk.find(key_data).upsert().update(output_data)
    bulk.execute()


def remove_notification(user_id, type=None):
    col = get_notifications_col()
    if type is None:
        col.remove({"user_id": user_id})
    else:
        col.update({"user_id": user_id}, {"$set": {type: 0}, "$pull": {"messages": {"type": type}}}, upsert=True)


def mark_notification_seen(user_id, text):
    col = get_notifications_col()
    col.update({"user_id": user_id, "messages": {"text": text}}, {"$set": {"messages.$.seen": True}})


def mark_thread_seen(user_id, thread_id):
    col = get_notifications_col()
    doc = col.find_one({"user_id": user_id, "messages.thread": thread_id})
    if not doc:
        return
    for message in doc["messages"]:
        if message["thread"] == thread_id:
            message["seen"] = True
    col.update({"user_id": user_id}, {"$pull": {"messages": {}}})
    col.update({"user_id": user_id}, {"$pushAll": {"messages": doc["messages"]}})


def has_thread_unread(user_id, thread_id):
    col = get_notifications_col()
    return col.find({"user_id": user_id, "messages": {"$elemMatch": {"thread": thread_id, "seen": {"$ne": True}}}}).count() != 0


def get_fetched_platforms_col():
    """
    return queries fetched platforms or None if error
    """
    db = get_db()
    if db:
        return db.fetched_platforms
    else:
        return None


def clear_performed_platform():
    col = get_fetched_platforms_col()
    col.remove()


def mongo_mark_issued_platform(plat_id, influencer_id=None, show_on_search=None,
                               old_show_on_search=None, url_not_found=None, platform_name=None):
    """
    Helper to mark issued platform -- for task to detect platforms that are not being performed.
    :return:
    """
    from debra.models import Platform

    try:
        today = datetime.date.today().isoformat().replace('-', '')
        col = get_fetched_platforms_col()

        doc = col.find_one({"_id": today})
        if not doc:
            fp = {
                "_id": today,
                "fetched": [],
                "issued": [],
                "issued_count": 0,
                "issued_osos_count": 0,
                "issued_sos_count": 0,
                "fetched_count": 0,
                "fetched_osos_count": 0,
                "fetched_sos_count": 0
            }
            col.insert(fp)

        osos = None  # flag of platform.influencer.old_show_on_search
        sos = None   # flag of platform.influencer.show_on_search
        inf_id = None
        if influencer_id is None or show_on_search is None or old_show_on_search is None \
                or url_not_found is None or platform_name is None:
            try:
                plat = Platform.objects.get(id=plat_id)
                platform_name = plat.platform_name
                url_not_found = plat.url_not_found
                inf_id = plat.influencer.id
                osos = plat.influencer.old_show_on_search
                sos = plat.influencer.show_on_search
            except:
                pass
        else:
            inf_id = influencer_id
            osos = show_on_search
            sos = old_show_on_search

        col.update(
            {
                "_id": today
            },
            {
                "$push": {
                    "issued": {
                        "platform_id": plat_id,
                        "influencer_id": inf_id,
                        "unf": url_not_found,
                        "pn": platform_name,
                        "osos": osos,
                        "sos": sos,
                        "dt": datetime.datetime.now().isoformat()
                    }
                },
                "$inc": {
                    "issued_count": 1,
                    "issued_osos_count": 1 if osos is True else 0,
                    "issued_sos_count": 1 if sos is True else 0
                }
            }
        )
    except:
        pass

@task(name='debra.mongo_utils.mongo_mark_performed_platform', ignore_result=True)
def mongo_mark_performed_platform(plat_id, influencer_id=None, show_on_search=None,
                                  old_show_on_search=None, url_not_found=None, platform_name=None):
    """
    Helper to mark performed platform -- for task to detect platforms that are not being performed.
    :return:
    """
    from debra.models import Platform

    try:

        today = datetime.date.today().isoformat().replace('-', '')
        col = get_fetched_platforms_col()

        doc = col.find_one({"_id": today})
        if not doc:
            fp = {
                "_id": today,
                "fetched": [],
                "issued": [],
                "issued_count": 0,
                "issued_osos_count": 0,
                "issued_sos_count": 0,
                "fetched_count": 0,
                "fetched_osos_count": 0,
                "fetched_sos_count": 0
            }
            col.insert(fp)

        osos = None  # flag of platform.influencer.old_show_on_search
        sos = None   # flag of platform.influencer.show_on_search
        inf_id = None
        if influencer_id is None or show_on_search is None or old_show_on_search is None \
                or url_not_found is None or platform_name is None:
            try:
                plat = Platform.objects.get(id=plat_id)
                platform_name = plat.platform_name
                url_not_found = plat.url_not_found
                inf_id = plat.influencer.id
                osos = plat.influencer.old_show_on_search
                sos = plat.influencer.show_on_search
            except:
                pass
        else:
            inf_id = influencer_id
            osos = show_on_search
            sos = old_show_on_search

        col.update(
            {
                "_id": today
            },
            {
                "$push": {
                    "fetched": {
                        "platform_id": plat_id,
                        "unf": url_not_found,
                        "pn": platform_name,
                        "influencer_id": inf_id,
                        "osos": osos,
                        "sos": sos,
                        "dt": datetime.datetime.now().isoformat()
                    }
                },
                "$inc": {
                    "fetched_count": 1,
                    "fetched_osos_count": 1 if osos is True else 0,
                    "fetched_sos_count": 1 if sos is True else 0
                }
            }
        )

    except:
        pass


def daterange(start_date, end_date):
    for n in range(int ((end_date - start_date).days)):
        yield start_date + datetime.timedelta(n)

def get_mongo_report_value(since_date, to_date, val=None):

    from debra.models import Platform
    from collections import defaultdict, Counter

    # getting datakeys
    later = max(since_date, to_date)
    earlier = min(since_date, to_date)
    list_of_keys = [dt.isoformat().replace('-', '') for dt in daterange(earlier, later)]

    col = get_fetched_platforms_col()

    # calculating values
    int_result = 0
    dict_result = defaultdict()
    for k in list_of_keys:
        mongo_data = col.find_one({"_id": k})
        if mongo_data:
            # counting total by platform names
            if val == 'platforms':
                for i in mongo_data.get('fetched', []):
                    pn = i.get('pn', None)
                    unf = i.get('unf', None)
                    if unf is not True:
                        if pn is not None and pn in dict_result:
                            dict_result[pn] += 1
                        elif pn is not None and pn not in dict_result:
                            dict_result[pn] = 1

            # influencers with N platforms:
            # (1) forming a list of all infs ids for performed platform entries
            # (2) counting counts of these ids
            if val == 'infs_by_plats':
                # (1)
                tpd = defaultdict()
                for i in mongo_data.get('fetched', []):
                    inf_id = i.get('influencer_id', None)
                    plat_id = i.get('platform_id', None)
                    unf = i.get('unf', None)
                    if inf_id is not None and plat_id is not None and unf is not True:
                        if inf_id in tpd:
                            if plat_id not in tpd[inf_id]:
                                tpd[inf_id].append(plat_id)
                        else:
                            tpd[inf_id] = [plat_id, ]

                        # tpl.append(inf_id)
                tpl = []
                for x, y in tpd.items():
                    tpl.extend([x, ] * len(y))

                # (2)
                c = Counter(tpl)
                for v in c.values():
                    if v in dict_result:
                        dict_result[v] += 1
                    else:
                        dict_result[v] = 1

            if val == 'all_validated':
                for i in mongo_data.get('fetched', []):
                    if i.get('unf', 'missing') not in ['missing', True]:
                        int_result += 1

            if val == 'blog_plats_crawled':
                for i in mongo_data.get('fetched', []):
                    pn = i.get('pn', None)
                    unf = i.get('unf', None)
                    if pn in Platform.BLOG_PLATFORMS and unf is not True:
                        int_result += 1

    # returning results
    if val in ['all_validated', 'blog_plats_crawled']:
        return int_result
    else:
        return dict_result


def get_mongo_report_inf_by_plats(since_date, to_date):

    from collections import defaultdict, Counter

    too_much_ctr = 0
    too_much_ids = []

    # getting datakeys
    later = max(since_date, to_date)
    earlier = min(since_date, to_date)
    list_of_keys = [dt.isoformat().replace('-', '') for dt in daterange(earlier, later)]

    col = get_fetched_platforms_col()

    # calculating values
    dict_result = defaultdict()
    for k in list_of_keys:
        mongo_data = col.find_one({"_id": k})
        if mongo_data:
            # influencers with N platforms:
            # (1) forming a list of all infs ids for performed platform entries
            # (2) counting counts of these ids
            tpd = defaultdict()
            for i in mongo_data.get('fetched', []):
                inf_id = i.get('influencer_id', None)
                plat_id = i.get('platform_id', None)
                unf = i.get('unf', None)
                if inf_id is not None and plat_id is not None and unf is not True:
                    if inf_id in tpd:
                        if plat_id not in tpd[inf_id]:
                            tpd[inf_id].append(plat_id)
                    else:
                        tpd[inf_id] = [plat_id, ]

                    # tpl.append(inf_id)
            tpl = []
            for x, y in tpd.items():
                tpl.extend([x, ] * len(y))

            # (2)
            c = Counter(tpl)
            for iid, v in c.items():
                if v < 7:
                    if v in dict_result:
                        dict_result[v] += 1
                    else:
                        dict_result[v] = 1
                else:
                    too_much_ctr += 1
                    if iid not in too_much_ids:
                        too_much_ids.append(iid)

    return dict_result, too_much_ctr, too_much_ids


def get_report_data():
    """
    Getting data grouped by platforms for last two weeks
    :return:
    """

    from collections import defaultdict

    data = dict()

    # starting day
    today = datetime.date.today()

    # 1st week
    end_date = today
    start_date = today - datetime.timedelta(days=28)

    col = get_fetched_platforms_col()

    for i, dt in enumerate(daterange(start_date, end_date)):

        log.info('%s Getting mongo data for %s' % (i, dt))

        mongo_data = col.find_one({"_id": dt.isoformat().replace('-', '')})

        if mongo_data:
            # tpd = defaultdict()
            for f in mongo_data.get('fetched', []):
                plat_id = f.get('platform_id', None)
                unf = f.get('unf', None)
                osos = f.get('osos', None)
                plat_name = f.get('pn', None)

                if osos is True and unf is not True:

                    if plat_name not in data:
                        data[plat_name] = {}

                    if i == 27:
                        if 'today' not in data[plat_name]:
                            data[plat_name]['today'] = defaultdict()
                        data[plat_name]['today'][plat_id] = 1

                    if i == 26:
                        if 'yesterday' not in data[plat_name]:
                            data[plat_name]['yesterday'] = defaultdict()
                        data[plat_name]['yesterday'][plat_id] = 1

                    if i >= 21:
                        if 'week1' not in data[plat_name]:
                            data[plat_name]['week1'] = defaultdict()
                        data[plat_name]['week1'][plat_id] = 1

                    if i >= 14:
                        if 'week2' not in data[plat_name]:
                            data[plat_name]['week2'] = defaultdict()
                        data[plat_name]['week2'][plat_id] = 1

                    if i >= 7:
                        if 'week3' not in data[plat_name]:
                            data[plat_name]['week3'] = defaultdict()
                        data[plat_name]['week3'][plat_id] = 1

                    if i >= 0:
                        if 'week4' not in data[plat_name]:
                            data[plat_name]['week4'] = defaultdict()
                        data[plat_name]['week4'][plat_id] = 1

    result = dict()
    for plat_name, plat_data in data.items():

        if plat_name not in result:
            result[plat_name] = {}

        for period, ids_dict in plat_data.items():
            result[plat_name][period] = len(ids_dict)

    return result




def report_maker():
    """
    Version 1

    creates a report for the given date in a form:

        <In the last week >
           12,000 influencers were crawled at least one platform
           9,000 influencers at least 2 platforms were crawled
           6,000 influencers at least 3 platforms were crawled
           4,000 influencers all validated platform were crawled
           8,000 influencer's blog platforms were crawled
           5,000 influencers' pinterest were crawled
        <In the last 2 weeks>
            20,000 influencers were crawled

    :param date:
    :return:
    """

    log.info('Started generating report')

    # starting day
    today = datetime.date.today()

    # 1st week
    since = today
    to = today - datetime.timedelta(days=7)
    # total by platforms names, dict
    w1_plats = get_mongo_report_value(since, to, "platforms")
    # influencers by plat, dict
    # w1_infs_by_plats = get_mongo_report_value(since, to, "infs_by_plats")
    w1_infs_by_plats, too_much_ctr, too_much_ids = get_mongo_report_inf_by_plats(since, to)
    # all_validated, total
    w1_all_validated = get_mongo_report_value(since, to, "all_validated")
    # blog_plats_crawled, total
    w1_blog_plats_total = get_mongo_report_value(since, to, "blog_plats_crawled")
    report = '<table border="0">'
    report += "<tr><td><span style='padding: 0 10px'>In the last week:</span></tr></td>"
    for k, v in w1_infs_by_plats.items():
        report += "<tr><td><span style='padding: 0 50px'>%s influencers were crawled " \
                  "with %s platform (distinct)</span></tr></td>" % (
        v, k)
    if too_much_ctr > 0:
        report += "<tr><td><span style='padding: 0 50px'>\t%s influencers were crawled " \
                  "with more than 7 platforms (distinct)</span></tr></td>" % too_much_ctr
        report += "<tr><td><span style='padding: 0 75px'>\tInfluencer Ids: %s</span></tr></td>" % ", ".join(
            [str(i) for i in too_much_ids])

    report += "<tr><td><span style='padding: 0 50px'>\t%s influencers all validated " \
              "platform were crawled</span></tr></td>" % w1_all_validated
    report += "<tr><td><span style='padding: 0 50px'>\t%s influencer's blog " \
              "platforms were crawled</span></tr></td>" % w1_blog_plats_total

    for k, v in w1_plats.items():
        report += "<tr><td><span style='padding: 0 50px'>\t%s %s platforms were crawled</span></tr></td>" % (v, k)

    log.info('1st week calculated')

    # 2 weeks
    since = today
    to = today - datetime.timedelta(days=14)
    # total by platforms names, dict
    w1_plats = get_mongo_report_value(since, to, "platforms")
    # influencers by plat, dict
    # w1_infs_by_plats = get_mongo_report_value(since, to, "infs_by_plats")
    w1_infs_by_plats, too_much_ctr, too_much_ids = get_mongo_report_inf_by_plats(since, to)
    # all_validated, total
    w1_all_validated = get_mongo_report_value(since, to, "all_validated")
    # blog_plats_crawled, total
    w1_blog_plats_total = get_mongo_report_value(since, to, "blog_plats_crawled")
    report += "<tr><td><span style='padding: 0 10px'>In the last 2 weeks:</span></tr></td>"
    for k, v in w1_infs_by_plats.items():
        report += "<tr><td><span style='padding: 0 50px'>\t%s influencers " \
                  "were crawled with %s platform (distinct)</span></tr></td>" % (
        v, k)
    if too_much_ctr > 0:
        report += "<tr><td><span style='padding: 0 50px'>\t%s influencers " \
                  "were crawled with more than 7 platforms (distinct)</span></tr></td>" % too_much_ctr
        report += "<tr><td><span style='padding: 0 75px'>\tInfluencer Ids: %s</span></tr></td>" % ", ".join(
            [str(i) for i in too_much_ids])

    report += "<tr><td><span style='padding: 0 50px'>%s influencers all validated platform " \
              "were crawled</span></tr></td>" % w1_all_validated
    report += "<tr><td><span style='padding: 0 50px'>%s influencer's blog platforms " \
              "were crawled</span></tr></td>" % w1_blog_plats_total

    for k, v in w1_plats.items():
        report += "<tr><td><span style='padding: 0 50px'>%s %s platforms were crawled</span></tr></td>" % (v, k)

    log.info('2nd week calculated')

    # 3 weeks
    since = today
    to = today - datetime.timedelta(days=21)
    # total by platforms names, dict
    w1_plats = get_mongo_report_value(since, to, "platforms")
    # influencers by plat, dict
    # w1_infs_by_plats = get_mongo_report_value(since, to, "infs_by_plats")
    w1_infs_by_plats, too_much_ctr, too_much_ids = get_mongo_report_inf_by_plats(since, to)
    # all_validated, total
    w1_all_validated = get_mongo_report_value(since, to, "all_validated")
    # blog_plats_crawled, total
    w1_blog_plats_total = get_mongo_report_value(since, to, "blog_plats_crawled")
    report += "<tr><td><span style='padding: 0 10px'>In the last 3 weeks:</span></tr></td>"
    for k, v in w1_infs_by_plats.items():
        report += "<tr><td><span style='padding: 0 50px'>\t%s influencers " \
                  "were crawled with %s platform (distinct)</span></tr></td>" % (
        v, k)
    if too_much_ctr > 0:
        report += "<tr><td><span style='padding: 0 50px'>\t%s influencers " \
                  "were crawled with more than 7 platforms (distinct)</span></tr></td>" % too_much_ctr
        report += "<tr><td><span style='padding: 0 75px'>\tInfluencer Ids: %s</span></tr></td>" % ", ".join(
            [str(i) for i in too_much_ids])

    report += "<tr><td><span style='padding: 0 50px'>\t%s influencers all validated platform " \
              "were crawled</span></tr></td>" % w1_all_validated
    report += "<tr><td><span style='padding: 0 50px'>\t%s influencer's blog platforms " \
              "were crawled</span></tr></td>" % w1_blog_plats_total

    for k, v in w1_plats.items():
        report += "<tr><td><span style='padding: 0 50px'>\t%s %s platforms were crawled</span></tr></td>" % (v, k)

    log.info('3rd week calculated')

    # 4 weeks
    since = today
    to = today - datetime.timedelta(days=21)
    # total by platforms names, dict
    # w1_infs_by_plats = get_mongo_report_value(since, to, "infs_by_plats")
    w1_plats = get_mongo_report_value(since, to, "platforms")
    # influencers by plat, dict
    w1_infs_by_plats, too_much_ctr, too_much_ids = get_mongo_report_inf_by_plats(since, to)
    # all_validated, total
    w1_all_validated = get_mongo_report_value(since, to, "all_validated")
    # blog_plats_crawled, total
    w1_blog_plats_total = get_mongo_report_value(since, to, "blog_plats_crawled")
    report += "<tr><td><span style='padding: 0 10px'>In the last 4 weeks:</span></tr></td>"
    for k, v in w1_infs_by_plats.items():
        report += "<tr><td><span style='padding: 0 50px'>\t%s influencers " \
                  "were crawled with %s platform (distinct)</span></tr></td>" % (
        v, k)
    if too_much_ctr > 0:
        report += "<tr><td><span style='padding: 0 50px'>\t%s influencers " \
                  "were crawled with more than 7 platforms (distinct)</span></tr></td>" % too_much_ctr
        report += "<tr><td><span style='padding: 0 75px'>\tInfluencer Ids: %s</span></tr></td>" % ", ".join(
            [str(i) for i in too_much_ids])

    report += "<tr><td><span style='padding: 0 50px'>\t%s influencers all validated platform " \
              "were crawled</span></tr></td>" % w1_all_validated
    report += "<tr><td><span style='padding: 0 50px'>\t%s influencer's blog platforms " \
              "were crawled</span></tr></td>" % w1_blog_plats_total

    for k, v in w1_plats.items():
        report += "<tr><td><span style='padding: 0 50px'>\t%s %s platforms were crawled</span></tr></td>" % (v, k)

    log.info('4th week calculated')

    report += "</table>"
    return report


def report_maker2():
    """
    Version 2

    creates a new version of report in a table form:

    First of all, the daily crawling report should contain information like this above:
    <Blogspots> Crawled yesterday: <> Crawled last week: <> Crawled in last 2 week: <> Crawled in last 3 week:<> // Total
    For each platform type.
    Using influencers.old_show_on_search=True influencers and related platforms in counts only.
    :return:
    """
    from debra.models import Platform

    log.info('Started generating report')

    report_data = get_report_data()

    report = '<table border="1">'
    report += "<tr><td>Platform name</td><td>Crawled today</td><td>Crawled yesterday</td><td>Crawled last week</td><td>Crawled last 2 weeks</td><td>Crawled last 3 weeks</td><td>Crawled last 4 weeks</td><td>TOTAL WE HAVE</td></tr>"

    for plat_name, plat_data in report_data.items():

        total_plats = Platform.objects.filter(
            platform_name=plat_name,
            influencer__old_show_on_search=True
        ).exclude(
            url_not_found=True
        ).exclude(
            influencer__blacklisted=True
        ).count()

        report += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            plat_name,
            plat_data.get('today', 0),
            plat_data.get('yesterday', 0),
            plat_data.get('week1', 0),
            plat_data.get('week2', 0),
            plat_data.get('week3', 0),
            plat_data.get('week4', 0),
            total_plats
        )

    report += "</table>"
    return report


def get_platform_data_by_key(key=None):
    """

    :param key:
    :return:
    """
    col = get_fetched_platforms_col()
    if key is None:
        doc = col.find_one()
    else:
        doc = col.find_one({"_id": key})
    return doc


def get_ids_of_performed(since=None, mode='show_on_search'):
    """
    Returns a list of ids of platforms, peformed since given date
    :param since:
    :param mode: mode of getting ids: 'old_show_on_search', 'show_on_search', 'any'
    :return:
    """

    keys = {}

    if since is not None:
        # getting datakeys
        later = datetime.datetime.today()
        earlier = since
        list_of_keys = [dt.isoformat().replace('-', '').split("T")[0] for dt in daterange(earlier, later)]

        col = get_fetched_platforms_col()

        # calculating values
        for k in list_of_keys:
            log.info('performing ids for %s' % k)
            mongo_data = col.find_one({"_id": k})
            if mongo_data is not None:
                log.info('Collecting ids for key %s' % k)

                for i in mongo_data.get('fetched', []):
                    plat_id = i.get('platform_id', None)
                    osos = i.get('osos', None)
                    sos = i.get('sos', None)
                    unf = i.get('unf', None)
                    if (mode == 'show_on_search' and sos is True or
                            mode == 'old_show_on_search' and osos is True or
                            mode == 'any') and unf is not True:
                        keys[plat_id] = 1
            else:
                log.info('Key %s does not have any data, skipping it' % k)

    else:
        log.info('since is None, returning empty')

    return keys.keys()
