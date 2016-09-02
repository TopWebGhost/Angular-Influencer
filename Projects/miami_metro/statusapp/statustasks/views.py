import logging
import datetime
from collections import OrderedDict, defaultdict
from pprint import pprint, pformat
import math
import subprocess
import os.path

from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt


from . import models
from . import tasks
from .tasks import _cursor


log = logging.getLogger('statustasks.views')



def _get_queue_data():
    r = tasks.rabbitmq_get('api/queues/?sort=name')
    #pprint.pprint(r.json())
    return r.json()

def _get_shelf_stats(hours_ago, max_image_size):
    conn = tasks._create_prod_db_connection()
    cur = _cursor(conn)
    cur.execute("""select *,
        exists(
            select 1 from xps_scrapingresult sr
            join xps_scrapingresultsize ssize on ssize.scraping_result_id = sr.id
            where sr.product_model_id = pmsm.product_model_id
            and ssize.size <= %s
        ) as small_image_exists
        from debra_productmodelshelfmap pmsm
        where added_datetime > current_timestamp - '%s hours'::interval
        and added_datetime < current_timestamp + '24 hours'::interval
        order by added_datetime desc""", [max_image_size, hours_ago])
    by_dayhour = OrderedDict()
    def key_from_dt(dt):
        return (dt.date(), dt.hour)
    for row in cur:
        if key_from_dt(row['added_datetime']) not in by_dayhour:
            by_dayhour[key_from_dt(row['added_datetime'])] = {'items': 0, 'img_url__isnull': 0,
                                                              'img_url_shelf_view__isnull': 0,
                                                              'small_image_exists': 0}
        d = by_dayhour[key_from_dt(row['added_datetime'])]
        d['items'] += 1
        if row['img_url'] is None:
            d['img_url__isnull'] += 1
        if row['img_url_shelf_view'] is None:
            d['img_url_shelf_view__isnull'] += 1
        if row['small_image_exists']:
            d['small_image_exists'] += 1
    cur.close()
    log.info('shelf stats: %s', pformat(by_dayhour))
    return by_dayhour

def _get_pmsms_with_small_images(hours_ago, max_image_size):
    conn = tasks._create_prod_db_connection()
    cur = _cursor(conn)
    cur.execute("""select * from
        debra_productmodelshelfmap pmsm,
        debra_productmodel pm,
        xps_scrapingresult sr,
        xps_scrapingresultsize ssize
        where pmsm.product_model_id = pm.id
        and sr.product_model_id = pm.id
        and sr.tag = 'img'
        and ssize.scraping_result_id = sr.id
        and ssize.size <= %s
        and pmsm.added_datetime > current_timestamp - '%s hours'::interval
        order by pmsm.added_datetime desc
        limit 1000""", [max_image_size, hours_ago])
    return list(cur)

def _get_platform_stats():
    conn = tasks._create_prod_db_connection()
    cur = _cursor(conn)
    res = {}

    cur.execute("""select count(*) from debra_influencer""")
    res['influencer_count'] = cur.fetchone()[0]

    cur.execute("""select count(*) from debra_influencer where demographics_location is not null""")
    res['influencer_with_location_count'] = cur.fetchone()[0]

    res['datakeys'] = [
        'influencer_cnt',
        #'influencer_cnt_pct',
        'platform_cnt',
        'platform_with_post_cnt',
        'platform_with_pi_cnt',
        'platform_with_num_followers',
        'platform_with_num_following',
        'platform_with_about',
        'platform_with_description',
    ]

    res['by_platform'] = []

    res['by_platform'].append(('all', _compute_by_platform(res, cur, [
        """select pl.platform_name, count(distinct in_.id) as influencer_cnt,
            count(distinct pl.id) as platform_cnt
            from debra_platform pl, debra_influencer in_
            where pl.influencer_id = in_.id
            group by pl.platform_name
            order by influencer_cnt desc""",

        """select pl.platform_name, count(*) as platform_with_post_cnt
            from debra_platform pl
            where exists (select * from debra_posts po where po.platform_id = pl.id)
            group by pl.platform_name
            order by platform_with_post_cnt desc""",

        """select pl.platform_name, count(distinct pl.id) as platform_with_pi_cnt
            from debra_platform pl, debra_posts po
            where po.platform_id = pl.id
            and exists (select * from debra_postinteractions pi where pi.post_id = po.id)
            group by pl.platform_name
            order by platform_with_pi_cnt desc""",

        """select pl.platform_name, count(*) as platform_with_num_followers
            from debra_platform pl
            where num_followers is not null
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_num_following
            from debra_platform pl
            where num_following is not null
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_about
            from debra_platform pl
            where about is not null
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_description
            from debra_platform pl
            where description is not null
            group by pl.platform_name""",
    ])))

    res['by_platform'].append(('trendsetters', _compute_by_platform(res, cur, [
        """select pl.platform_name, count(distinct in_.id) as influencer_cnt,
            count(distinct pl.id) as platform_cnt
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = true
            group by pl.platform_name
            order by influencer_cnt desc""",

        """select pl.platform_name, count(*) as platform_with_post_cnt
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where exists (select * from debra_posts po where po.platform_id = pl.id)
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = true
            group by pl.platform_name
            order by platform_with_post_cnt desc""",

        """select pl.platform_name, count(distinct pl.id) as platform_with_pi_cnt
            from debra_platform pl, debra_posts po, debra_influencer in_, debra_userprofile up
            where po.platform_id = pl.id
            and exists (select * from debra_postinteractions pi where pi.post_id = po.id)
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = true
            group by pl.platform_name
            order by platform_with_pi_cnt desc""",

        """select pl.platform_name, count(*) as platform_with_num_followers
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where (pl.num_followers is not null or pl.total_numlikes is not null)
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = true
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_num_following
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where pl.num_following is not null
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = true
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_about
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where pl.about is not null
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = true
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_description
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where pl.description is not null
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = true
            group by pl.platform_name""",
    ])))

    res['by_platform'].append(('shelf_users_non_trendsetters', _compute_by_platform(res, cur, [
        """select pl.platform_name, count(distinct in_.id) as influencer_cnt,
            count(distinct pl.id) as platform_cnt
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = false
            group by pl.platform_name
            order by influencer_cnt desc""",

        """select pl.platform_name, count(*) as platform_with_post_cnt
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where exists (select * from debra_posts po where po.platform_id = pl.id)
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = false
            group by pl.platform_name
            order by platform_with_post_cnt desc""",

        """select pl.platform_name, count(distinct pl.id) as platform_with_pi_cnt
            from debra_platform pl, debra_posts po, debra_influencer in_, debra_userprofile up
            where po.platform_id = pl.id
            and exists (select * from debra_postinteractions pi where pi.post_id = po.id)
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = false
            group by pl.platform_name
            order by platform_with_pi_cnt desc""",

        """select pl.platform_name, count(*) as platform_with_num_followers
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where (pl.num_followers is not null or pl.total_numlikes is not null)
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = false
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_num_following
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where pl.num_following is not null
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = false
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_about
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where pl.about is not null
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = false
            group by pl.platform_name""",

        """select pl.platform_name, count(*) as platform_with_description
            from debra_platform pl, debra_influencer in_, debra_userprofile up
            where pl.description is not null
            and pl.influencer_id = in_.id
            and in_.shelf_user_id = up.user_id
            and up.is_trendsetter = false
            group by pl.platform_name""",
    ])))

    cur.execute("""select distinct source from debra_influencer where source is not null
                   and source<>''
                """)
    sources = [r[0] for r in cur.fetchall()]
    log.info('influencer sources: %r', sources)

    for source in sources:
        res['by_platform'].append((source, _compute_by_platform(res, cur, [
            """select pl.platform_name, count(distinct in_.id) as influencer_cnt,
                count(distinct pl.id) as platform_cnt
                from debra_platform pl, debra_influencer in_
                where pl.influencer_id = in_.id
                and in_.source=%s
                group by pl.platform_name
                order by influencer_cnt desc""",

            """select pl.platform_name, count(*) as platform_with_post_cnt
                from debra_platform pl, debra_influencer in_
                where exists (select * from debra_posts po where po.platform_id = pl.id)
                and pl.influencer_id = in_.id
                and in_.source=%s
                group by pl.platform_name
                order by platform_with_post_cnt desc""",

            """select pl.platform_name, count(distinct pl.id) as platform_with_pi_cnt
                from debra_platform pl, debra_posts po, debra_influencer in_
                where po.platform_id = pl.id
                and pl.influencer_id = in_.id
                and in_.source=%s
                and exists (select * from debra_postinteractions pi where pi.post_id = po.id)
                group by pl.platform_name
                order by platform_with_pi_cnt desc""",

            """select pl.platform_name, count(*) as platform_with_num_followers
                from debra_platform pl, debra_influencer in_
                where num_followers is not null
                and pl.influencer_id = in_.id
                and in_.source=%s
                group by pl.platform_name""",

            """select pl.platform_name, count(*) as platform_with_num_following
                from debra_platform pl, debra_influencer in_
                where num_following is not null
                and pl.influencer_id = in_.id
                and in_.source=%s
                group by pl.platform_name""",

            """select pl.platform_name, count(*) as platform_with_about
                from debra_platform pl, debra_influencer in_
                where about is not null
                and pl.influencer_id = in_.id
                and in_.source=%s
                group by pl.platform_name""",

            """select pl.platform_name, count(*) as platform_with_description
                from debra_platform pl, debra_influencer in_
                where description is not null
                and pl.influencer_id = in_.id
                and in_.source=%s
                group by pl.platform_name""",
        ], [source])))

    res['totals'] = {}

    cur.execute("""select count(*) from debra_influencer""")
    res['totals']['all'] = cur.fetchone()[0]

    cur.execute("""select count(distinct in_.id)
            from debra_influencer in_, debra_userprofile up
            where in_.shelf_user_id = up.user_id
            and up.is_trendsetter = true""")
    res['totals']['trendsetters'] = cur.fetchone()[0]

    cur.execute("""select count(distinct in_.id)
            from debra_influencer in_, debra_userprofile up
            where in_.shelf_user_id = up.user_id
            and up.is_trendsetter = false""")
    res['totals']['shelf_users_non_trendsetters'] = cur.fetchone()[0]

    for source in sources:
        cur.execute("""select count(*) from debra_influencer where source=%s""", [source])
        res['totals'][source] = cur.fetchone()[0]

    #for name, by_platform in res['by_platform']:
    #    res['totals'][name] = sum(d['influencer_cnt'] for d in by_platform.values())

    res['pcts'] = dict.fromkeys(res['datakeys'])

    return res

def _pct_val(num, tot):
    return (float(num)*100.0)/float(tot)

def _compute_by_platform(res, cur, sqls, *args, **kwargs):
    assert len(sqls) > 1

    log.info('Executing: %s', sqls[0])
    cur.execute(sqls[0], *args, **kwargs)
    log.info('Done')
    by_platform = { x['platform_name']: dict(x) for x in cur }

    if 'influencer_cnt' in by_platform.values()[0] and 'influencer_count' in res:
        for d in by_platform.values():
            d['influencer_cnt_pct'] = int(round((d['influencer_cnt'] * 100 / res['influencer_count'])))

    for sql in sqls[1:]:
        log.info('Executing: %s', sql)
        cur.execute(sql, *args, **kwargs)
        log.info('Done')
        for r in cur:
            if r['platform_name'] in by_platform:
                by_platform[r['platform_name']].update(r)

    by_platform.pop(None, None)
    return by_platform

def _get_fetcherdata_stats(hours, for_search):
    conn = tasks._create_prod_db_connection()
    cur = _cursor(conn)
    res = {}
    res['datakeys'] = [
        'posts_cnt',
        'pis_cnt',
        'sponsorships_cnt',
        'pmsm_cnt',
    ]
    if for_search:
        inf_cond = """and pl.influencer_id in (select id from debra_influencer inf where inf.source is not null
                and inf.blog_url is not null
                and exists(select 1 from debra_platform pl where pl.influencer_id=inf.id and pl.platform_name in ('Facebook', 'Twitter'))
                and exists(select 1 from debra_platform pl where pl.influencer_id=inf.id and pl.profile_img_url is not null)
                and inf.average_num_posts >= 5)
        """
    else:
        inf_cond = ''
    res['by_platform'] = _compute_by_platform(res, cur, [
        """select pl.platform_name, count(*) as posts_cnt
            from debra_posts po, debra_platform pl
            where po.platform_id = pl.id
            {inf_cond}
            and po.inserted_datetime > current_timestamp - '{h} hours'::interval
            group by pl.platform_name""".format(inf_cond=inf_cond, h=hours),
        """select pl.platform_name, count(*) as pis_cnt
            from debra_postinteractions pi, debra_posts po, debra_platform pl
            where po.platform_id = pl.id
            {inf_cond}
            and pi.post_id = po.id
            and pi.added_datetime > current_timestamp - '{h} hours'::interval
            group by pl.platform_name""".format(inf_cond=inf_cond, h=hours),
        """select pl.platform_name, count(*) as sponsorships_cnt
            from debra_sponsorshipinfo si, debra_posts po, debra_platform pl
            where po.platform_id = pl.id
            {inf_cond}
            and si.post_id = po.id
            and si.added_datetime > current_timestamp - '{h} hours'::interval
            group by pl.platform_name""".format(inf_cond=inf_cond, h=hours),
        """select pl.platform_name, count(*) as pmsm_cnt
            from debra_productmodelshelfmap pmsm, debra_posts po, debra_platform pl
            where po.platform_id = pl.id
            {inf_cond}
            and pmsm.post_id = po.id
            and pmsm.added_datetime > current_timestamp - '{h} hours'::interval
            group by pl.platform_name""".format(inf_cond=inf_cond, h=hours),
    ])
    return res

def _get_influencer_stats():
    conn = tasks._create_prod_db_connection()
    cur = _cursor(conn)
    cur.execute("""select
    count(*) as total_infs,
    count(case when inf.source is not null then 1 else null end) as source_not_null,
    count(case when inf.blog_url is not null then 1 else null end) as blog_url_not_null,
    count(case when inf.relevant_to_fashion=true then 1 else null end) as relevant_to_fashion
    from debra_influencer inf""")
    return cur.fetchone()

@login_required
def status_table(request):
    hours_ago = float(request.GET.get('hours', '24'))
    recent_results = models.TaskResult.objects.filter(executed__gte=datetime.datetime.now() - \
                                                      datetime.timedelta(hours=hours_ago)).\
        order_by('-id')
    recent_by_task = OrderedDict([(task_name, []) for task_name in tasks.TASK_BY_NAME])
    for tr in recent_results:
        if tr.task in recent_by_task:
            recent_by_task[tr.task].append(tr)

    try:
        queue_data = _get_queue_data()
        queue_data = [qd for qd in queue_data if not qd.get('name', '').startswith('celeryev') and not \
                      qd.get('name', '').endswith('pidbox')]
    except:
        log.exception('While getting queue_data')
        queue_data = []

    return render(request, 'status_table.html', dict(
        hours_ago=hours_ago,
        recent_by_task=recent_by_task,
        queue_data=queue_data,
        shelf_stats=shelf_stats,
    ))

def _pcts_for_data_lst(data, user_spec, data_lst):
    tot = data['totals'][user_spec]
    return [_pct_val(v, tot) for v in data_lst]

@login_required
def platform_stats(request):
    data = _get_platform_stats()
    for user_spec, pdata in data['by_platform']:
        for pn in pdata:
            data_lst = [pdata[pn].get(k, 0) for k in data['datakeys']]
            data_pct = _pcts_for_data_lst(data, user_spec, data_lst)
            pdata[pn] = zip(data_lst, data_pct)
    log.info('platform data:\n%s', pformat(data))
    return render(request, 'platform_stats.html', dict(data))

@login_required
def shelf_stats(request):
    hours_ago = float(request.GET.get('hours', '24'))
    max_image_size = float(request.GET.get('max_image_size', '20000'))
    try:
        shelf_stats = _get_shelf_stats(hours_ago, max_image_size).items()
    except:
        log.exception('While getting shelf stats')
        shelf_stats = []
    return render(request, 'shelf_stats.html', dict(
        hours_ago=hours_ago,
        shelf_stats=shelf_stats,
    ))

@login_required
def pmsm_images_stats(request):
    hours_ago = float(request.GET.get('hours', '24'))
    max_image_size = float(request.GET.get('max_image_size', '20000'))
    try:
        pmsm_stats = _get_pmsms_with_small_images(hours_ago, max_image_size)
    except:
        log.exception('While getting pmsm image stats')
        pmsm_stats = []
    return render(request, 'pmsm_image_stats.html', dict(
        hours_ago=hours_ago,
        max_image_size=max_image_size,
        max_image_size_sqrt=math.sqrt(max_image_size),
        pmsm_stats=pmsm_stats,
    ))

@login_required
def fetcherdata_stats(request):
    hours = int(request.GET.get('hours', '24'))
    for_search = int(request.GET.get('for-search', '0'))
    data = _get_fetcherdata_stats(hours, for_search)
    for pn in data['by_platform']:
        data['by_platform'][pn] = [data['by_platform'][pn].get(k, 0) for k in data['datakeys']]
    log.info('fetcherdata:\n%s', pformat(data))
    return render(request, 'fetcherdata_stats.html', dict(data, hours=hours))

@login_required
def influencer_stats(request):
    d = _get_influencer_stats()
    return render(request, 'influencer_stats.html', {'data': d})


SQL_LATEST_POST = """
with latest_post_data as (
    select
    inf.id,
    (select max(po.create_date) from debra_posts po where po.platform_id=pl.id) as latest_post
    from debra_influencer inf
    join debra_platform pl on (pl.influencer_id=inf.id and pl.url=inf.blog_url)
)
select count(*) as influencer_cnt, date_part('day', (current_timestamp - latest_post)) as latest_post_days_ago
from latest_post_data
group by latest_post_days_ago
order by latest_post_days_ago asc
"""

SQL_POSTS_COUNTS = """
with post_count_data as (
    select
    (select count(*) from debra_posts po where po.platform_id=pl.id) as c,
    inf.id as inf_id
    from debra_influencer inf
    join debra_platform pl on pl.influencer_id=inf.id
)
select
count(case when c between 1 and 5 then 1 else null end) as posts_between_1_5,
count(case when c between 6 and 10 then 1 else null end) as posts_between_6_10,
count(case when c between 11 and 50 then 1 else null end) as posts_between_11_50,
count(case when c between 51 and 100 then 1 else null end) as posts_between_51_100,
count(case when c >= 101 then 1 else null end) as posts_gt_101
from post_count_data
;
"""

@login_required
def execute_sql(request):
    sql_name = request.GET.get('sql')
    sql = globals()[sql_name]
    log.info('Executing: %s', sql)
    output = subprocess.check_output([os.path.join(settings.PROJECT_PATH, '../run_sql.sh'), sql])
    log.info('Done')
    return render(request, 'sql_results.html', dict(output=output, sql=sql_name))


@csrf_exempt
def my_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return HttpResponse('ok')
        return HttpResponse('not ok')
    return render(request, 'login.html', {})

