from __future__ import division
import logging
import baker
import itertools
import pprint
import datetime
from collections import defaultdict
import urlparse

from celery.decorators import task
from debra import models
from debra import constants
from debra import db_util
from django.db.models import Q
from django.db.models import query
from hanna import import_from_blog_post

from platformdatafetcher import platformutils
from xpathscraper import utils
from xpathscraper import textutils


RES_LIMIT = 50


def from_ids(cursor, mclass):
    ids = [row[0] for row in itertools.islice(cursor, 0, RES_LIMIT)]
    q = mclass.objects.filter(id__in=ids).order_by('-id')
    return list(q)

def fetch_count_and_objects(sql, mclass, id_alias='pl.id'):
    """A sql should contain '{what}' in a place of columns selection.
    This function returns a tuple of
    - 'count(*)'
    - a list of ``mclass`` model class objects
    """
    connection = db_util.connection_for_reading()
    cur = connection.cursor()

    cur.execute(sql.format(what='count(*)'))
    count = cur.fetchone()[0]

    cur.execute('%s limit %s' % (sql.format(what=id_alias), RES_LIMIT))
    objects = from_ids(cur, mclass)

    return count, objects

def insert_warnings(q, invariant_instance, mclass, id_alias='pl.id'):
    if isinstance(q, (str, unicode)):
        # sql
        connection = db_util.connection_for_reading()
        cur = connection.cursor()
        cur.execute(q.format(what=id_alias))
        r_ids = (row[0] for row in cur)
    elif isinstance(q, query.QuerySet):
        r_ids = (m.id for m in q.iterator())
    elif isinstance(q, list):
        r_ids = (m.id for m in q)
    else:
        assert False, 'Unknown type of q: %r' % type(q)
    cause = getattr(invariant_instance, 'cause', None)
    if not cause:
        log.error('cause not specified in %r', invariant_instance)
        return
    fields = getattr(invariant_instance, 'fields', None)
    if not fields:
        fields = []
    for r_id in r_ids:
        if mclass == models.Platform:
            platform = models.Platform.objects.get(id=r_id)
            influencer = platform.influencer
        elif mclass == models.Influencer:
            influencer = models.Influencer.objects.get(id=r_id)
            platform = None
        else:
            assert False, 'Unknown model class %r' % mclass
        if not models.InfluencerCheck.objects.filter(influencer=influencer, platform=platform,
                 cause=cause, fields=fields, status=models.InfluencerCheck.STATUS_NEW).exists():
            models.InfluencerCheck.report(influencer, platform, cause, fields)



class Invariant(object):

    def check(self):
        """Inserts objects not fulfilling the invariant into PlatformDataWarning table.
        """
        raise NotImplementedError()

    def __repr__(self):
        return self.__class__.__name__


class FewFetchErrors(Invariant):

    def __init__(self, max_errors_pct=5.0, hours=8):
        self.max_errors_pct = max_errors_pct
        self.hours = hours

    def check(self):
        connection = db_util.connection_for_reading()
        cur = connection.cursor()
        cur.execute("""
        select
        count(case when error_msg is not null and error_msg <> 'old_version' then 1 else null end) as errors,
        count(*) as all
        from debra_platformdataop pdo
        join debra_platform pl on pl.id=pdo.platform_id
        join debra_influencer inf on inf.id=pl.influencer_id
        where pdo.operation='fetch_data'
        and inf.show_on_search = true
        and not (pl.url_not_found = true)
        and pdo.started > current_timestamp - '{hours} hours'::interval""".format(hours=self.hours))
        errors, all = cur.fetchone()
        if all == 0:
            errors_pct = 0
        else:
            errors_pct = (errors * 100) / all
        print 'Errors in the last %s hours: %.2f%%' % (self.hours, errors_pct)


class PostsButNoFollowers(Invariant):

    def check(self):
        q = """select {what} from debra_platform pl
            join debra_influencer inf on inf.id=pl.influencer_id
            where (pl.num_followers is null or pl.num_followers=0)
            and inf.show_on_search = true
            and not (pl.url_not_found = true)
            and exists(select * from debra_posts po where po.platform_id=pl.id)
            """
        insert_warnings(q, self, models.Platform)


class NoPosts(Invariant):

    def check(self):
        q = """select {what} from debra_platform pl
            join debra_influencer inf on inf.id=pl.influencer_id
            where url_not_found=false and validated_handle is not null
            and not exists(select * from debra_posts po where po.platform_id=pl.id)
            """
        insert_warnings(q, self, models.Platform)


class PostsLastMonthButNoPostsThisMonth(Invariant):

    def check(self):
        q = """select {what} from debra_platform pl
        join debra_influencer inf on inf.id=pl.influencer_id
        where exists(select * from debra_posts po
            where po.platform_id=pl.id and po.create_date
            between current_timestamp - '2 months'::interval and current_timestamp - '1 months'::interval)
        and not exists(select * from debra_posts po
            where po.platform_id=pl.id and po.create_date > current_timestamp - '1 month'::interval)
        and inf.show_on_search = true
        and not (pl.url_not_found = true)
        """
        insert_warnings(q, self, models.Platform)


class PostInteractionsLastMonthButNoPostInteractionsThisMonth(Invariant):

    def check(self):
        q = """select {what} from debra_platform pl
        join debra_influencer inf on inf.id=pl.influencer_id
        where   exists(select 1 from debra_postinteractions pis join debra_posts po on (pis.post_id=po.id and po.platform_id=pl.id and pis.create_date between current_timestamp - '2 months'::interval and current_timestamp - '1 months'::interval))
        and not exists(select 1 from debra_postinteractions pis join debra_posts po on (pis.post_id=po.id and po.platform_id=pl.id and pis.create_date > current_timestamp - '1 month'::interval))
        and inf.show_on_search = true
        and not (pl.url_not_found = true)
        """
        insert_warnings(q, self, models.Platform)


class ManyFollowersFewPostInteractions(Invariant):

    def check(self):
        plats = models.Platform.objects.filter(influencer__show_on_search=True,
                                               avg_numcomments_overall__lt=10,
                                               num_followers__gt=10000).\
                                        exclude(platform_name='Twitter').\
                                        exclude(url_not_found=True)
        insert_warnings(plats, self, models.Platform)


class NumFollowersVariations(Invariant):

    def check(self):
        ptss = models.PopularityTimeSeries.objects.filter(influencer__show_on_search=True,
                        snapshot_date__gte=datetime.datetime.today() - datetime.timedelta(days=30),
                        num_followers__isnull=False).\
                    exclude(platform__url_not_found=True).\
                    order_by('platform__id').iterator()
        res = []
        for pl, group in itertools.groupby(ptss, lambda pts: pts.platform):
            lst = list(group)
            lst.sort(key=lambda x: x.snapshot_date)
            nums = [x.num_followers for x in lst]
            if high_variation(nums):
                log.info('High varations for platform %r and num_followers %r', pl, nums)
                res.append(pl)
            else:
                #log.debug('Nums are ok: %r', nums)
                pass

        insert_warnings(res, self, models.Platform)


class NotDenormalizedLastWeek(Invariant):

    def check(self):
        q = """
        select {what}
        from debra_influencer inf
        where inf.show_on_search = true
        and not exists(select * from debra_platformdataop pdo where pdo.influencer_id = inf.id and pdo.operation='denormalize_influencer'
                       and pdo.finished > current_timestamp - '1 week'::interval and pdo.error_msg is null)
        """
        insert_warnings(q, self, models.Influencer, 'inf.id')


class OutlierPlatform(Invariant):
    cause = models.InfluencerCheck.CAUSE_SUSPECT_SOCIAL_PLATFORM_OUTLIER_FOLLOWERS

    def check(self):
        infs = models.Influencer.objects.filter(show_on_search=True)[:10]
        res = []
        for inf in infs:
            plats = inf.platform_set.exclude(url_not_found=True)
            nums = [plat.num_followers for plat in plats]
            nums = [x for x in nums if x > 0]
            if len(nums) <= 1:
                continue
            log.debug('outlier nums: %r', nums)
            avg = utils.avg(*nums)
            for x in nums:
                if not 0.3*avg <= x <= 3.0*avg:
                    log.debug('invalid num: %r', x)
                    res.append(inf)
        insert_warnings(res, self, models.Influencer)


class MinPostsImported(Invariant):

    def check(self):
        q = """
        select pl.id
        from debra_influencer inf
        join debra_platform pl on pl.influencer_id=inf.id
        where inf.show_on_search = true
        and pl.platform_name in ('Blogspot', 'Wordpress', 'Custom')
        and (select count(*) from debra_platformdataop pdo where pdo.post_id in (select po.id from debra_posts po where po.platform_id=pl.id) and operation='fetch_products_from_post') < 5
        """
        insert_warnings(q, self, models.Platform)


class AtLeastOnePostFromTheLastWeek(Invariant):

    def check(self):
        q = """
        select pl.id
        from debra_influencer inf
        join debra_platform pl on pl.influencer_id=inf.id
        where inf.show_on_search = true
        and pl.platform_name in ('Blogspot', 'Wordpress', 'Custom')
        and exists (select * from debra_posts po where po.platform_id = pl.id and po.create_date between current_timestamp - '7 days'::interval and current_timestamp - '1 day'::interval)
        and not exists (select * from debra_platformdataop pdo where pdo.post_id in (select po.id from debra_posts po where po.platform_id=pl.id) and operation='fetch_products_from_post' and pdo.error_msg is null and pdo.finished >= current_timestamp - '7 days'::interval)
        """
        insert_warnings(q, self, models.Platform)


INVARIANTS = [
    #FewFetchErrors(max_errors_pct=5.0, hours=24),
    PostsButNoFollowers(),
    NoPosts(),
    PostsLastMonthButNoPostsThisMonth(),
    PostInteractionsLastMonthButNoPostInteractionsThisMonth(),
    ManyFollowersFewPostInteractions(),
    NumFollowersVariations(),
    NotDenormalizedLastWeek(),
    OutlierPlatform(),
    AtLeastOnePostFromTheLastWeek(),
]


@task(name='platformdatafetcher.invariants.check_invariants', ignore_result=True)
@baker.command
def check_invariants():
    for inv in INVARIANTS:
        log.info('Checking invariant %r', inv)
        try:
            inv.check()
        except:
            log.exception('While checking invariant %r', inv)
            continue

@baker.command
def check_single_invariant(cls_name):
    inv = next(invariant for invariant in INVARIANTS if invariant.__class__.__name__ == cls_name)
    log.info('Checking invariant %r', inv)
    inv.check()

