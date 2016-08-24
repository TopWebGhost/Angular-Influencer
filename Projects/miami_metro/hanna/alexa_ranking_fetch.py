"""
Uses the awis api object implemeted by @muhuk https://github.com/muhuk
to find the blog url's alexa ranking and other relevant info
"""
import awis
from debra.models import Platform, AlexaRankingInfo, AlexaMetricByCountry, UserProfile, Platform
from xpathscraper import utils
from platformdatafetcher.platformutils import OpRecorder
from celery.decorators import task
from django.conf import settings
from django.db.models import Q
import datetime
import lxml.etree
import logging

log = logging.getLogger('hanna.alexa_ranking_fetch')

class AlexaAPIWapper(object):
    def __init__(self, platform):
        self.platform = platform
        self.ri = AlexaRankingInfo(platform=platform, snapshot_date=datetime.datetime.now())
        self.api = awis.AwisApi(settings.AWS_KEY, settings.AWS_PRIV_KEY)

    def fetch(self):
        self.tree = self._get_tree()

        self.ri.links_in_count = self._val('//aws:LinksInCount', int)
        self.ri.rank = self._val('//aws:TrafficData/aws:Rank', float)

        # We use the first matching UsageStatistic - for the longest period of time (3m)
        self.ri.reach = self._val('//aws:UsageStatistic/aws:Reach/aws:Rank/aws:Value', float)
        self.ri.page_views_per_1m = self._val('//aws:UsageStatistic/aws:PageViews/aws:PerMillion/aws:Value', float)
        self.ri.page_views_rank = self._val('//aws:UsageStatistic/aws:PageViews/aws:Rank/aws:Value', int)
        self.ri.page_views_per_user = self._val('//aws:UsageStatistic/aws:PageViews/aws:PerUser/aws:Value', float)
        self.ri.save()

        country_data = self._findall('//aws:RankByCountry/aws:Country')
        for cd in country_data:
            cd_m = AlexaMetricByCountry(alexa_ranking_info=self.ri)
            cd_m.country_code = cd.attrib.get('Code')
            rank_els = self._findall('aws:Rank', cd)
            if not rank_els:
                log.warn('No Rank el')
            elif not rank_els[0].text:
                log.warn('No Rank value')
            else:
                cd_m.rank = int(rank_els[0].text)
            c_els = self._findall('aws:Contribution', cd)
            if not c_els:
                log.warn('No Contribution el')
            else:
                cd_m.contribution_page_views_pct = self._val('aws:PageViews', utils.parse_percents,
                                                             c_els[0])
                cd_m.contribution_users_pct = self._val('aws:Users', utils.parse_percents,
                                                             c_els[0])
            cd_m.save()


        return self.ri

    #make the request which is a simple GET request with parameters
    #returns an ElementTree object
    def _get_tree(self):
        url = self.platform.url
        tree = self.api.url_info(url, "Rank", "LinksInCount", "RankByCountry", "Speed", "UsageStats", "Keywords", "SiteData")
        print "tree %s " % lxml.etree.tostring(tree)
        elem = tree.find("//{%s}StatusCode" % self.api.NS_PREFIXES["alexa"])
        print "Require elem.text %s = Success " % elem.text
        assert elem.text == "Success"
        return tree

    def _findall(self, expr, el=None):
        # expr should contain 'aws:' namespace prefixes, which will be replaced
        # by proper namespaces
        expr = expr.replace('aws:', '{http://awis.amazonaws.com/doc/2005-07-11}')
        if el is None:
            el = self.tree
        return el.findall(expr)

    def _val(self, expr, conv_fun=None, el=None):
        els = self._findall(expr, el)
        if not els or els[0] is None:
            return None
        res = els[0].text
        if conv_fun:
            try:
                res = conv_fun(res)
            except ValueError:
                return None
        return res

    # returns the text value for the given field in the ElementTree
    def get_field(self, field_str):
        print "Searching for : //{%s}%s" % (self.api.NS_PREFIXES["awis"], field_str)
        elem = self.tree.find("//{%s}%s" % (self.api.NS_PREFIXES["awis"], field_str))
        if elem is not None:
            return elem.text
        return None


@task(name='hanna.alexa_ranking_fetch.fetch_alexa_data', ignore_result=True)
def fetch_alexa_data(pl_id):
    pl = Platform.objects.get(id=pl_id)
    log.info('Fetching alexa data for platform %r', pl)
    with OpRecorder('fetch_alexa_data', platform=pl) as opr:
        alexa = AlexaAPIWapper(pl)
        alexa.fetch()

if __name__ == "__main__":

    #### find all blogger specific platforms
    #platform = Platform.objects.filter(Q(platform_name = "Blogspot") | Q(platform_name = "Wordpress") \
    #    | Q(platform_name = "Tumblr"))
    trendsetters = UserProfile.get_trendsetters().filter(influencer__isnull=False)
    platform = [t.influencer.blog_platform for t in trendsetters]

    for p in platform:
        #p = platform[0]
        alexa_p = AlexaAPIWapper(p)
        alexa_p.fetch()
        #alexa_p.print_all()
        snapshot_date = datetime.datetime.today()
        new_alexa_data, created = AlexaRankingInfo.objects.get_or_create(platform=p, snapshot_date = snapshot_date)

        print alexa_p.get_field('LinksInCount')
        print alexa_p.get_field('Rank')
        print alexa_p.get_field('Speed')
        print alexa_p.get_field('UsageStatistics')
        print alexa_p.get_field('Keywords')
        print alexa_p.get_field('SiteData')
        print alexa_p.get_field('PageViews')
        print alexa_p.get_field('Reach')
        print alexa_p.get_field('MedianLoadTime')
        print alexa_p.get_field('Percentile')

        if alexa_p.get_field('LinksInCount') is not None:
            new_alexa_data.links_in_count = alexa_p.get_field('LinksInCount')

        if alexa_p.get_field('Rank') is not None:
            new_alexa_data.rank = alexa_p.get_field('Rank')

        if alexa_p.get_field('MedianLoadTime') is not None:
            new_alexa_data.seo_loadtime = alexa_p.get_field('MedianLoadTime')

        new_alexa_data.save()

        #seo_loadtime = models.FloatField(null=True,blank=True,default=None) # FloatField correct? what args?
        #links_in_count = models.IntegerField(null=True,blank=True,default=None)
        #sites_linking_in = models.TextField(null=True,blank=True,default=None)

        #rank = models.FloatField(null=True,blank=True,default=None)
        #rank_by_country = models.FloatField(null=True,blank=True,default=None)
        #rank_by_city = models.FloatField(null=True,blank=True,default=None)

        #reach = models.FloatField(null=True,blank=True,default=None)
        #page_views = models.FloatField(null=True,blank=True,default=None)

        #keywords = models.FloatField(null=True,blank=True,default=None)
