from social_discovery.blog_discovery import queryset_iterator
from social_discovery.models import InstagramProfile
import datetime
import io

import logging
from social_discovery.pipelines import SEAPipeline, CanadaPipeline, AustraliaPipeline, TravelPipeline
from django.db.models.query_utils import Q
import urlparse

log = logging.getLogger('social_discovery.scripts')


def reissue_upgraded_without_influencer(do_real=False):
    """
    This script finds all InstagramProfiles without discovered_influencer but with 'UPGRADED' tag.
    Then it removes their 'UPGRADED' tag and reissue them to their corresponding pipelines according to
    their existing tags (for example, if it has SEA_HASHTAG, then it should be reissued to SEAPipeline, and so on.)
    :param do_real: -- set to True to save changes and to issue tasks.
    :return:
    """

    ips_without_influencers = InstagramProfile.objects.filter(discovered_influencer__isnull=True)
    ips_upgraded = ips_without_influencers.filter(tags__contains='UPGRADED')

    ips_upgraded_ids = list(ips_upgraded.values_list('id', flat=True))

    log.info('Profiles without influencer but with "UPGRADED" tag: %s' % ips_upgraded.count())

    # lists for profiles to reissue for particular pipelines
    reissue_sea = []
    reissue_canada = []
    reissue_australia = []
    reissue_travel = []

    for profile in ips_upgraded:

        # Removing 'UPGRADED' tag
        tags = profile.tags.split()
        tags.remove(u'UPGRADED')
        profile.tags = " ".join(tags)
        log.info('Profile %s tags: %s' % (profile.id, tags))
        if do_real:
            profile.save()

        if any([t in tags for t in ['SEA_LOCATION', 'SEA_LANGUAGE', 'SEA_HASHTAG']]):
            reissue_sea.append(profile.id)

        if any([t in tags for t in ['CANADA_LOCATION', 'CANADA_LANGUAGE', 'CANADA_HASHTAG']]):
            reissue_canada.append(profile.id)

        if any([t in tags for t in ['AUSTRALIA_LOCATION', 'AUSTRALIA_LANGUAGE', 'AUSTRALIA_HASHTAG']]):
            reissue_australia.append(profile.id)

        if any([t in tags for t in ['TRAVEL_LOCATION', 'TRAVEL_LANGUAGE', 'TRAVEL_HASHTAG', 'travel_hashtags']]):
            reissue_travel.append(profile.id)

    log.info('Summary for reissuing:')
    log.info('SEA profiles to reissue: %s' % len(reissue_sea))
    log.info('Canada profiles to reissue: %s' % len(reissue_canada))
    log.info('Australia profiles to reissue: %s' % len(reissue_australia))
    log.info('Travel profiles to reissue: %s' % len(reissue_travel))
    log.info('Total profiles to reissue: %s' % (len(reissue_travel) + len(reissue_australia)
                                                + len(reissue_canada) + len(reissue_sea)))

    unissued_ids = [pid for pid in ips_upgraded_ids if
                    pid not in reissue_sea and
                    pid not in reissue_canada and
                    pid not in reissue_australia and
                    pid not in reissue_travel]
    if len(unissued_ids) > 0:
        log.info('Unissued profile ids: %s' % unissued_ids)

    # reissuing sorted profiles
    if do_real:
        sea_pipeline = SEAPipeline()
        sea_pipeline.run_pipeline(reissue_sea)

        can_pipeline = CanadaPipeline()
        can_pipeline.run_pipeline(reissue_canada)

        aus_pipeline = AustraliaPipeline()
        aus_pipeline.run_pipeline(reissue_australia)

        tra_pipeline = TravelPipeline()
        tra_pipeline.run_pipeline(reissue_travel)

        log.info('Pipeline tasks were reissued successfully.')


def generate_report_social_urls_have_youtube():
    """
    Creates a csv report for collected social_urls in new_mommy_hashtags colelctions.

    :return:
    """
    initial_profiles = InstagramProfile.objects.filter(
        tags__contains="have_youtube",
        friends_count__gte=5000).filter(
        Q(social_urls_detected__isnull=False) | Q(non_social_urls_detected__isnull=False)
    )

    log.info('Found %s InstagramProfiles' % initial_profiles.count())

    csvfile = io.open('social_urls_detected__have_youtube__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'InstagramProfile id\turl\tDescription\tExternal url\tsocial_urls_detected\tnon_social_urls_detected\tPlatforms found\tFirst 10 platform ids\t\n'
    )

    for profile in queryset_iterator(initial_profiles):
        desc = profile.get_description_from_api()
        if desc is not None:
            desc = desc.replace(u'\t', u'').replace(u'\n', u'')
        found_plat_ids = profile.get_platform_ids_detected()
        csvfile.write(
            u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t\n' % (
                profile.id,
                profile.get_url(),
                desc,
                profile.get_url_from_api(),
                profile.social_urls_detected,
                profile.non_social_urls_detected,
                len(found_plat_ids),
                '' if len(found_plat_ids) == 0 else found_plat_ids[:10]
            )
        )

    csvfile.close()


def generate_report_social_urls_new_mommy():
    """
    Creates a csv report for collected social_urls in new_mommy_hashtags colelctions.

    :return:
    """
    initial_profiles = InstagramProfile.objects.filter(
        tags__contains="new_mommy_hashtags",
        friends_count__gte=5000
    ).filter(
        Q(social_urls_detected__isnull=False) | Q(non_social_urls_detected__isnull=False)
    ).order_by('id')

    log.info('Found %s InstagramProfiles' % initial_profiles.count())

    csvfile = io.open('social_urls_detected__mommy__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')
    csvfile.write(
        u'InstagramProfile id\turl\tDescription\tExternal url\tsocial_urls_detected\tnon_social_urls_detected\tPlatforms found\tFirst 10 platform ids\tIC TAG\tDiscovered Influencer Id\tBlog Url\t\n'
    )

    for profile in queryset_iterator(initial_profiles):
        desc = profile.get_description_from_api()
        if desc is not None:
            desc = desc.replace(u'\t', u'').replace(u'\n', u'')
        found_plat_ids = profile.get_platform_ids_detected()

        ic_tags = profile.tags.split() if profile.tags is not None else []
        ic_tags = [ t for t in ic_tags if t.startswith('IC_') ]

        csvfile.write(
            u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t\n' % (
                profile.id,
                profile.get_url(),
                desc,
                profile.get_url_from_api(),
                profile.social_urls_detected,
                profile.non_social_urls_detected,
                len(found_plat_ids),
                '' if len(found_plat_ids) == 0 else found_plat_ids[:10],
                ic_tags,
                profile.discovered_influencer.id if profile.discovered_influencer is not None else None,
                profile.discovered_influencer.blog_url if profile.discovered_influencer is not None else None,
            )
        )

    csvfile.close()


def test_new_upgrader(tag_to_check='mom', tag_to_exclude=None, friends_count_threshold=5000, include_undecided=False):
    """
    Testing new upgrader (detection of platforms and creating of influencers)
    :return:
    """
    from debra.models import Influencer
    from social_discovery.influencer_creator import InfluencerCreator

    initial_profiles = InstagramProfile.objects.filter(
        tags__contains=tag_to_check,
        friends_count__gte=friends_count_threshold,
    ).order_by(
        'id'
    )

    if tag_to_exclude:
        initial_profiles = initial_profiles.exclude(tags__contains=tag_to_exclude)

    blogs = initial_profiles.filter(tags__contains='blogger')
    undecided = initial_profiles.filter(tags__contains='undecided')

    if include_undecided:
        final_profiles = blogs | undecided
    else:
        final_profiles = blogs

    initial_profiles = final_profiles  # .values_list(
    #     "id",
    #     flat=True
    # )

    csvfile = io.open('test_new_upgrader__mommy__extra__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')

    csvfile.write(
        u'InstagramProfile id\turl\tDescription\tExternal url\tsocial_urls_detected\tnon_social_urls_detected\tPlatforms found\tFirst 10 platform ids\t'
        u'DELIMITER\t'
        u'Existing influencer Id\t'
        u'profile_id\t'
        u'existing_platform_ids_qty\t'
        u'non_social_urls_qty\t'
        u'Influencers found by platform_ids\t'
        u'Unique non-social root domains\t'
        u'Unique non-social root domains count\t'
        u'If only 1: is blog?\t'
        u'Blog platforms found:\t'
        u'IC tag:\t'
        u'Report: RESULT\n'
    )

    log.info('Total profiles: %s' % initial_profiles.count())

    for profile in initial_profiles:
        log.info('Performing profile # %s' % profile.id)

        try:

            ic = InfluencerCreator(profile=profile)
            res = ic.detect_influencer()
            log.info('Result: %s' % res)
            report_data = ic.get_report_data()

            desc = profile.get_description_from_api()
            if desc is not None:
                desc = desc.replace(u'\t', u'').replace(u'\n', u'')
            found_plat_ids = profile.get_platform_ids_detected()

            ic_tags = profile.tags.split() if profile.tags is not None else []
            ic_tags = [ t for t in ic_tags if t.startswith('IC_') ]

            inf_ids_found = report_data.get('active_influencers_ids', [])
            if len(inf_ids_found) > 0:
                infs_found = Influencer.objects.filter(id__in=inf_ids_found)
            else:
                infs_found = None

            if (infs_found is not None and infs_found.count() == 1 and infs_found[0].old_show_on_search is not True) \
                or (infs_found is None and report_data.get('non_social_urls_qty', 0) == 1):

                csvfile.write(
                    u'%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t\n' % (
                        profile.id,
                        profile.get_url(),
                        desc,
                        profile.get_url_from_api(),
                        profile.social_urls_detected,
                        profile.non_social_urls_detected,
                        len(found_plat_ids),
                        '' if len(found_plat_ids) == 0 else found_plat_ids[:10],

                        '*',

                        None if profile.discovered_influencer is None else profile.discovered_influencer.id,

                        report_data.get('profile_id', ''),
                        report_data.get('existing_platform_ids_qty', ''),
                        report_data.get('non_social_urls_qty', ''),
                        report_data.get('active_influencers_ids', ''),
                        report_data.get('unique_root_domains', ''),
                        len(report_data.get('unique_root_domains', [])),
                        report_data.get('unique_root_domain_is_blog', ''),
                        report_data.get('blog_platforms_found', ''),
                        ic_tags,
                        report_data.get('result', ''),
                    )
                )
        except:
            pass

    csvfile.close()


def test_consistency_of_url_detection():
    """
    Here, we check if the urls are correctly obtained from the profiles.
    We check if a profile has an external url and then check if it exists in the
    social_urls_detected or non_social_urls_detected
    """
    initial_profiles = InstagramProfile.objects.filter(
        tags__contains="new_mommy_hashtags",
        friends_count__gte=5000
    ).order_by(
        'id'
    )

    inconsistent = set()

    for i in initial_profiles:
        ext = i.get_external_url()
        if ext:
            soc = i.social_urls_detected
            non_soc = i.non_social_urls_detected
            if (soc and ext.lower() in soc.lower()) or (non_soc and ext.lower() in non_soc.lower()):
                print "good: %r [soc %r] [non_soc %r]" % (ext, soc, non_soc)
            else:
                inconsistent.add(i)
                print "total inconsistencies: %r" % len(inconsistent)


def clean_detector_collections(tag='mommy'):
    """
    Cleans collections for detected/duplicates
    :param tag:
    :return:
    """

    from debra.models import InfluencersGroup

    log.info('Deleting influencers from collection %s_discovered_from_instagram' % tag)
    coll = InfluencersGroup.objects.filter(name='%s_discovered_from_instagram' % tag.lower())
    if len(coll) > 0:
        coll = coll[0]
        infs = coll.influencers
        for inf in infs:
            coll.remove_influencer(inf)

    log.info('Deleting influencers from collection %s_duplicates_from_instagram' % tag)
    coll = InfluencersGroup.objects.filter(name='%s_duplicates_from_instagram' % tag.lower())
    if len(coll) > 0:
        coll = coll[0]
        infs = coll.influencers
        for inf in infs:
            coll.remove_influencer(inf)


def social_url_extraction_tester():
    """
    Testing teh effectiveness of urls detection in description
    """
    initial_profiles = InstagramProfile.objects.filter(
        tags__contains="new_mommy_hashtags",
        friends_count__gte=5000
    ).order_by(
        'id'
    )[:1000]

    log.info('Performing %s profiles: ' % initial_profiles.count())

    csvfile = io.open('social_urls_extraction__mommy__%s.csv' % datetime.datetime.strftime(
        datetime.datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')

    csvfile.write(
        u'Profile\t'
        u'Description\t'
        u'External url\t'
        u'Discovered SOCIAL urls\t'
        u'Discovered NON-SOCIAL urls\t'
        u'All discovered found?\t'
        u'Extra\n'
    )

    for profile in initial_profiles:
        log.info('Performing profile: %s' % profile.id)
        social = profile.get_social_urls_detected()
        non_social = profile.get_non_social_urls_detected()
        both = social + non_social
        external_url = profile.get_external_url()

        all_found = None

        desc = profile.get_description_from_api()
        if desc is None:
            desc = u""
        else:
            desc = u" ".join(desc.split())

        if external_url is not None:
            full_desc = desc + u' %s' % external_url
        else:
            full_desc = desc

        if len(desc) > 0:
            all_found = True
            for url in both:
                parsed = urlparse.urlparse(url)
                dmn = parsed.netloc[4:] if parsed.netloc.startswith("www.") else "www.%s" % parsed.netloc
                alt_url = parsed._replace(netloc=dmn)
                alt_url = alt_url.geturl()

                if (url.lower().strip('/') not in full_desc.lower()) and (alt_url.lower().strip('/') not in full_desc.lower()):
                    all_found = False
                    break

        csvfile.write(
            u'%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                profile.id,
                desc,
                external_url,
                social,
                non_social,
                all_found,
                u''
            )
        )

    csvfile.close()
    log.info('Done.')


def cleanup_influencers_data():
    """
    This is a one-time task.

    We find all influencers that are not showing up on old_show_on_search=True and do not have date_validated greater than May 2016

    For all of these, we do the following:
    a) find all platforms that are not autovalidated and are SOCIAL_PLATFORM
        => clear out their given fb_url or other fields from Influencer
        => mark them url_not_found=True
    b) find all of their autovalidated=True and are SOCIAL_PLATFORM
        => save their url in the influencer _url field
    c) Save influencer, reset scores, name, blogname, email, and profile_pic
    d) Find all instagram profiles that are connected = InstagramProfile.objects.filter(discovered_influencer=inf)
        => disconnect these

    """

    from debra import models as dmodels
    import datetime

    def update_field(platform, value):
        """
        a helper method to reset the Influencer fields also
        """
        if platform.platform_name in dmodels.Influencer.platform_name_to_field.keys():
            field = dmodels.Influencer.platform_name_to_field[platform.platform_name]
            setattr(platform.influencer, field, value)
            log.info("Setting %r=%r for %r" % (field, value, platform.influencer))
            platform.influencer.save()

    def cleanup(influencer):
        influencer.name = None
        influencer.email_for_advertising_or_collaborations = None
        influencer.profile_pic_url = None
        influencer.email_all_other = None
        influencer.blogname = None
        influencer.score_engagement_overall = None
        influencer.score_popularity_overall = None
        influencer.save()

    def disconnect_profile(iid):
        if iid is not None:
            ips = InstagramProfile.objects.filter(discovered_influencer__id=iid)
            for ip in ips:
                ip.discovered_influencer = None
                ip.save()
                log.info('Disconnected Influencer %s from InstagramProfile %s' % (iid, ip.id))

    infs = dmodels.Influencer.objects.all().exclude(old_show_on_search=True).filter(show_on_search=True)
    infs = infs.exclude(date_validated__gte=datetime.date(2016, 6, 1))
    inf_ids = infs.values_list('id', flat=True)

    infs_count = infs.count()
    log.info("Total influencers = %d" % infs_count)

    plats_all = dmodels.Platform.objects.filter(influencer__in=infs,
                                                platform_name__in=dmodels.Platform.SOCIAL_PLATFORMS_CRAWLED).exclude(url_not_found=True)

    plats_autovalidated_ids = plats_all.filter(autovalidated=True).values_list('id', flat=True)
    plats_not_autovalidated_ids = plats_all.exclude(autovalidated=True).values_list('id', flat=True)


    plats_autovalidated_ids_count = plats_autovalidated_ids.count()
    plats_not_autovalidated_ids_count = plats_not_autovalidated_ids.count()

    log.info("Total autovalidated social plats: %r" % plats_autovalidated_ids_count)
    log.info("Total non-autovalidated social_plats: %r" % plats_not_autovalidated_ids_count)

    for i, pid in enumerate(plats_not_autovalidated_ids):
        plat = dmodels.Platform.objects.get(id=pid)
        plat.url_not_found = True
        plat.save()
        update_field(plat, None)
        if i % 100 == 0:
            log.info("plats_not_autovalidated_ids :: Done with %d/%d" % (i, plats_not_autovalidated_ids_count))

    for i, pid in enumerate(plats_autovalidated_ids):
        plat = dmodels.Platform.objects.get(id=pid)
        update_field(plat, plat.url)
        if i % 100 == 0:
            log.info("plats_autovalidated_ids :: Done with %d/%d" % (i, plats_autovalidated_ids_count))

    for i, iid in enumerate(inf_ids):
        inf = dmodels.Influencer.objects.get(id=iid)
        cleanup(inf)
        disconnect_profile(iid)
        if i % 100 == 0:
            log.info("inf_ids :: Done with %d/%d" % (i, infs_count))


def profile_stats(friends_count=1000):
    """
    Displays stats about profiles with a minimum friends_count
    """

    profiles = InstagramProfile.objects.filter(friends_count__gte=friends_count)

    bloggers = profiles.filter(tags__contains='blogger')
    brand = profiles.filter(tags__contains='brand')
    undecided = profiles.filter(tags__contains='undecided')
    short = undecided.filter(tags__contains='SHORT')

    print("[%d] Total=[%d] Bloggers=[%d] Brand=[%d] Undecided=[%d] Short_Undecided=[%d]" %
          (friends_count, profiles.count(), bloggers.count(), brand.count(), undecided.count(), short.count()))