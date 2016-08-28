import datetime
import io
import logging

import baker
from django.db.models import Q

from debra.models import Platform, Influencer, BrandJobPost
from platformdatafetcher.squarespacefetcher import check_if_squarespace_url
from social_discovery.blog_discovery import queryset_iterator
from xpathscraper import utils

log = logging.getLogger('platformdatafetcher.scripts')


@baker.command
def try_to_fix_invalid_urls():
    suspects = Platform.objects.filter(num_followers__isnull=True, influencer__show_on_search=True, platform_name__in=('Pinterest', 'Instagram', 'Twitter')).exclude(url_not_found=True)

    # empty urls
    suspects.filter(url='').update(url_not_found=True)

    # leading whitespace
    for suspect in suspects.filter(url__startswith=' '):
        suspect.url = suspect.url.strip()
        suspect.save()

    # no schema
    for suspect in suspects.exclude(Q(url__icontains='http://')|Q(url__icontains='https://')):
        if suspect.url.startswith('//'):
            suspect.url = 'http:' + suspect.url
        else:
            suspect.url = 'http://' + suspect.url
        suspect.save()

    for suspect in suspects.filter(platform_name='Twitter').exclude(url__icontains='twitter.com'):
        log.info('Invalid platform url for Twitter ("{0}", platform id {1})'.format(suspect.url, suspect.id))

    for suspect in suspects.filter(platform_name='Pinterest').exclude(url__icontains='pinterest.com'):
        log.info('Invalid platform url for Pinterest ("{0}", platform id {1})'.format(suspect.url, suspect.id))

    for suspect in suspects.filter(platform_name='Instagram').exclude(url__icontains='instagram.com'):
        log.info('Invalid platform url for Instagram ("{0}", platform id {1})'.format(suspect.url, suspect.id))


def find_squarespace_platforms(inf_ids=None):
    """
    Trying to find potential influencers with squarespace (currently just few for test)
    :param limit:
    :return:
    """

    plats = Platform.objects.filter(
        platform_name='Custom'
    ).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    )

    if isinstance(inf_ids, list):
        plats = plats.filter(
            influencer_id__in=inf_ids
        )

    print('Found %s potential platforms to check' % plats.count())

    ctr = 0
    bad_result = []
    unreachable = []

    csvfile = io.open('squarespace_detection_report__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')

    csvfile.write(u'Platform id\tPlatform1 url\tPlatform initial name\tPlatform detected name\tError\n')

    for plat in queryset_iterator(plats):

        if plat.posts_set.filter(inserted_datetime__gte=datetime.datetime(2016, 03, 01)).count() > 0:
            continue

        initial_pn = plat.platform_name
        error = u''
        try:
            is_squarespace = check_if_squarespace_url(plat.url)
            if is_squarespace is True:
                plat.platform_name = 'Squarespace'
                plat.save()
            elif is_squarespace is None:
                unreachable.append(plat.id)
                error = 'Unreachable'
            else:
                print('Plat %s is NOT Squarespace' % plat.id)
        except:
            bad_result.append(plat.id)
            error = 'Got Exception'

        final_pn = plat.platform_name

        ctr += 1
        if ctr % 1000 == 0:
            print('Performed %s platforms' % ctr)

        csvfile.write(u'%s\t%s\t%s\t%s\t%s\n' % (
            plat.id,
            plat.url,
            initial_pn,
            final_pn,
            error
        ))

    csvfile.close()

    return bad_result, unreachable

####### SCRIPT PACK FOR UPDATING FACEBOOK OUTER URLS ######

from platformdatafetcher.socialfetcher import FacebookFetcher
class UpdatingFacebookFetcher(FacebookFetcher):

    def get_skipped_posts_threshold(self):
        """
        The maximum number of existing posts while fetching.
        If we hit that number, we assume we have fetched all the new posts already and stop fetching.
        The default value is 3, but fetchers can override it, if needed.

        P.S.: It is set to 125 because we are performing now only 5 pages of Facebook
        posts by 25 posts per page from API. This number might be increased

        """
        return 5 * 25


def update_facebook_urls_for_campaigns(campaign_ids=None):
    """
    This script updates posts for Facebook platforms for influencers involved in campaigns (all or specified)
    :param campaign_ids:
    :return:
    """

    from platformdatafetcher.pbfetcher import IndepthPolicy

    if campaign_ids is None:
        brand_job_posts = BrandJobPost.objects.all()
    elif type(campaign_ids) is int:
        brand_job_posts = BrandJobPost.objects.filter(id=campaign_ids)
    else:
        brand_job_posts = BrandJobPost.objects.filter(id__in=campaign_ids)

    # getting ids of all influencers in campaigns
    inf_ids = set()

    log.info('Collecting influencers to perform...')
    for bjp in queryset_iterator(brand_job_posts):

        # Initial data
        bjp_inf_ids = list(bjp.candidates.filter(campaign_stage__gte=3).values_list('mailbox__influencer__id', flat=True))
        for iid in bjp_inf_ids:
            if iid is not None:
                inf_ids.add(iid)

    log.info('Found %s distinct influencers, performing them' % len(inf_ids))

    # policy to perform
    policy = IndepthPolicy()

    for inf_id in inf_ids:
        try:

            inf = Influencer.objects.get(id=inf_id)
            log.info('Performing influencer %s (%s)' % (inf.id, inf.blogname))
            fb_platforms = inf.platform_set.filter(platform_name='Facebook').exclude(url_not_found=True)

            log.info('This influencer has %s Facebook platforms without url_not_found=True')

            for plat in fb_platforms:
                log.info('Performing posts for platform %s (%s)' % (plat.id, plat.url))

                pf = UpdatingFacebookFetcher(plat, policy)
                posts = pf.fetch_posts(max_pages=5)

                log.info('5 pages of platform %s were performed' % plat.id)

        except Influencer.DoesNotExist:
            log.error('Influencer %s was not found' % inf_id)


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
