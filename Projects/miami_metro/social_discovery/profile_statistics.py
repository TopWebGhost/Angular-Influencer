from django.db.models.query import QuerySet
from social_discovery.models import SocialProfileOp, InstagramProfile
from django.conf import settings
from datetime import date, timedelta

from celery.decorators import task

from mailsnake import MailSnake
mailsnake_client = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')

STATISTICS_TO_EMAILS = [
    {'email': 'atul@theshelf.com', 'type': 'to'},
    {'email': 'mukhin.vladimir@googlemail.com', 'type': 'to'},
]


def profiles_statistics_summary(queryset=None):

    """
    Statistics data on upgrade of SEA, Canada and Australia profiles. This will return string with data, so we
    could use it for sending daily email.

    Eventually we could rearrange that to some dictionary with data.

    Unfortunately, .annotate(latest_entry=Max('socialprofileop__create_date')) produces an error for models with
    PGJsonfield, so this approach was not successful.

    DatabaseError: could not identify an equality operator for type json
    LINE 1: ...ial_discovery_instagramprofile"."last_post_time", "social_di...

    :param queryset: queryset with profiles to describe with statistics
    :return: dict with statistical data like:
             {
                 "total_given": 2017,
                 "KeywordClassifier": {
                     "blogger": 517,
                     "brand": 200,
                     "undecided": 1500
                 }
                 ...
             }
             where top keys are names of pipeline modules and inner keys are SocialProfileOp descriptions.
             previously: string of statistics.
    """

    if not isinstance(queryset, QuerySet):
        return

    def processor_region_data(the_region='SEA', tags=('LOCATION', 'HASHTAG', 'LANGUAGE')):
        response = dict()

        # This is complicated, ProcessorSEA can issue several tags at once
        upper_region = the_region.upper()

        # Exceptions:
        if the_region == 'MenFashion':
            upper_region = 'FASHIONMEN'

        processed_total = SocialProfileOp.objects.filter(
            profile_id__in=queryset.values_list('id', flat=True)
        ).filter(
            module_classname='Processor%s' % the_region,
            description__in=['%s_LOCATION' % upper_region, 'UNSUITABLE_%s_LOCATION' % upper_region,
                             '%s_HASHTAG' % upper_region, 'UNSUITABLE_%s_HASHTAG' % upper_region,
                             '%s_LANGUAGE' % upper_region, 'UNSUITABLE_%s_LANGUAGE' % upper_region,
                             ]
        ).order_by('profile__id', '-date_created').distinct('profile__id')
        response['Processor%s' % the_region] = {}
        response['Processor%s' % the_region]['total'] = processed_total.count()

        passed_set = set([])

        # print('REGION: %s' % upper_region)

        for tag in tags:
            recent_processed_location = SocialProfileOp.objects.filter(
                profile_id__in=queryset.values_list('id', flat=True)
            ).filter(
                module_classname='Processor%s' % the_region, description__in=['%s_%s' % (upper_region, tag),
                                                                              'UNSUITABLE_%s_%s' % (upper_region, tag)]
            ).order_by('profile__id', '-date_created').distinct('profile__id')
            processor_location_passed = recent_processed_location.filter(description='%s_%s' % (upper_region, tag))
            processor_location_failed = recent_processed_location.filter(description='UNSUITABLE_%s_%s' % (upper_region,
                                                                                                           tag))
            response['Processor%s' % the_region]['%s_%s' % (upper_region, tag)] = processor_location_passed.count()
            response['Processor%s' % the_region]['UNSUITABLE_%s_%s' % (upper_region,
                                                                       tag)] = processor_location_failed.count()

            passed_set = passed_set | set(processor_location_passed.values_list('profile_id', flat=True))

            # print('PASSED list: %s' % processor_location_passed.values_list('profile_id', flat=True))
            # print('PASSED COMMON SET: %s' % passed_set)

        response['Processor%s' % the_region]['total_passed'] = len(passed_set)

        return response

    result = dict()

    # Total profiles given to perform
    result['total_given'] = queryset.count()

    # KeywordClassifier fields
    recent_keyword_classified = SocialProfileOp.objects.filter(
        profile_id__in=queryset.values_list('id', flat=True)
    ).filter(
        module_classname='KeywordClassifier'
    ).order_by(
        'profile__id', '-date_created'
    ).distinct('profile__id')

    keyword_classifier_blogger_qty = recent_keyword_classified.filter(description='blogger')
    keyword_classifier_brand_qty = recent_keyword_classified.filter(description='brand')
    keyword_classifier_undecided_qty = recent_keyword_classified.filter(description='undecided')

    result['KeywordClassifier'] = {}
    result['KeywordClassifier']['given'] = recent_keyword_classified.count()
    result['KeywordClassifier']['blogger'] = keyword_classifier_blogger_qty.count()
    result['KeywordClassifier']['brand'] = keyword_classifier_brand_qty.count()
    result['KeywordClassifier']['undecided'] = keyword_classifier_undecided_qty.count()

    # DescriptionLengthClassifier fields
    recent_dl_classified = SocialProfileOp.objects.filter(
        profile_id__in=queryset.values_list('id', flat=True)
    ).filter(
        module_classname='DescriptionLengthClassifier'
    ).order_by(
        'profile__id', '-date_created'
    ).distinct('profile__id')

    dl_classifier_short = recent_dl_classified.filter(description='SHORT_BIO_50')
    dl_classifier_long = recent_dl_classified.filter(description='LONG_BIO_50')

    result['DescriptionLengthClassifier'] = {}
    result['DescriptionLengthClassifier']['given'] = recent_dl_classified.count()
    result['DescriptionLengthClassifier']['SHORT_BIO_50'] = dl_classifier_short.count()
    result['DescriptionLengthClassifier']['LONG_BIO_50'] = dl_classifier_long.count()

    # ProcessorSEA, ProcessorCanada, ProcessorAustralia, etc...
    for region in ('SEA', 'Canada', 'Australia'):
        data = processor_region_data(region, ('LOCATION', 'HASHTAG', 'LANGUAGE'))
        result.update(data)

    # # Travel hashtags
    # data = processor_region_data('Travel', ('HASHTAG', ))
    # result.update(data)

    # Processors with Hashtags only (Travel, Fashion, etc...)
    for hashtags_name in ('Travel', 'Fashion', 'Decor', 'MenFashion', 'Food', 'Mommy'):
        data = processor_region_data(hashtags_name, ('HASHTAG', ))
        result.update(data)

    # OnlyBloggersProcessor (pre-upgrader)
    recent_obp_classified = SocialProfileOp.objects.filter(
        profile_id__in=queryset.values_list('id', flat=True)
    ).filter(
        module_classname='OnlyBloggersProcessor'
    ).order_by(
        'profile__id', '-date_created'
    ).distinct('profile__id')

    ob_processor_valid = recent_obp_classified.filter(description='VALID')
    ob_processor_invalid = recent_obp_classified.filter(description='INVALID')

    result['OnlyBloggersProcessor'] = {}
    result['OnlyBloggersProcessor']['VALID'] = ob_processor_valid.count()
    result['OnlyBloggersProcessor']['INVALID'] = ob_processor_invalid.count()

    # Upgrader
    upgrades_qs = SocialProfileOp.objects.filter(
        profile_id__in=queryset.values_list('id', flat=True)
    ).filter(
        module_classname='Upgrader'
    ).order_by(
        'profile__id', '-date_created'
    ).distinct('profile__id')  # .values_list('id', flat=True)

    upgrader_upgraded = upgrades_qs.filter(description='UPGRADED')
    upgrader_skipped = upgrades_qs.filter(description='SKIPPED_PROBLEM')
    upgrader_already_upgraded = upgrades_qs.filter(description='ALREADY_UPGRADED')
    upgrader_already_has_inf = upgrades_qs.filter(description='ALREADY_HAS_INFLUENCER')

    result['Upgrader'] = {}
    result['Upgrader']['given'] = len(upgrades_qs)
    result['Upgrader']['UPGRADED'] = upgrader_upgraded.count()
    result['Upgrader']['SKIPPED_PROBLEM'] = upgrader_skipped.count()
    result['Upgrader']['ALREADY_UPGRADED'] = upgrader_already_upgraded.count()
    result['Upgrader']['ALREADY_HAS_INFLUENCER'] = upgrader_already_has_inf.count()

    # ExtraDataUpgrader
    edu_qs = SocialProfileOp.objects.filter(
        profile_id__in=queryset.values_list('id', flat=True)
    ).filter(
        module_classname='ExtraDataUpgrader'
    ).order_by(
        'profile__id', '-date_created'
    ).distinct('profile__id')

    edu_issued = edu_qs.filter(description='DATA_FETCH_ISSUED')
    edu_fetched = edu_qs.filter(description='DATA_FETCHED')
    edu_no_influencer = edu_qs.filter(description='NO_INFLUENCER')

    result['ExtraDataUpgrader'] = {}
    result['ExtraDataUpgrader']['given'] = edu_qs.count()
    result['ExtraDataUpgrader']['DATA_FETCH_ISSUED'] = edu_issued.count()
    result['ExtraDataUpgrader']['DATA_FETCHED'] = edu_fetched.count()
    result['ExtraDataUpgrader']['NO_INFLUENCER'] = edu_no_influencer.count()

    return result


def build_stat_mail_text(statistics_data=None, is_html=False):
    """
    This function builds text for statistics data
    :param statistics_data: dict with statistics data
    :param is_html: if True, then lines are ended with <br />, else with /n
    :return:
    """
    if not isinstance(statistics_data, dict):
        return None

    result = ""

    result += "Total profiles to perform: %s\r\n" % statistics_data.get('total_given')
    result += "KeywordClassifier (received %s profiles)\r\n" % statistics_data.get('KeywordClassifier', {}).get('given')
    result += "    set tag 'blogger' to profiles: %s\r\n" % statistics_data.get('KeywordClassifier', {}).get('blogger')
    result += "    set tag 'brand' to profiles: %s\r\n" % statistics_data.get('KeywordClassifier', {}).get('brand')
    result += "    set tag 'undecided' to profiles: %s\r\n" % statistics_data.get('KeywordClassifier',
                                                                                {}).get('undecided')
    result += "    finally, out of %s profiles: %s passed to next module, %s profiles did not.\r\n" % (
        statistics_data.get('KeywordClassifier', {}).get('blogger', 0) +
        statistics_data.get('KeywordClassifier', {}).get('brand', 0) +
        statistics_data.get('KeywordClassifier', {}).get('undecided', 0),
        statistics_data.get('KeywordClassifier', {}).get('blogger', 0) +
        statistics_data.get('KeywordClassifier', {}).get('undecided', 0),
        statistics_data.get('KeywordClassifier', {}).get('brand', 0)
    )

    result += "\r\n"
    result += "DescriptionLengthClassifier (received %s profiles)\r\n" % \
              statistics_data.get('DescriptionLengthClassifier', {}).get('given')
    result += "    set tag 'SHORT_BIO_50' to profiles: %s\r\n" % \
              statistics_data.get('DescriptionLengthClassifier', {}).get('SHORT_BIO_50')
    result += "    set tag 'LONG_BIO_50' to profiles: %s\r\n" % \
              statistics_data.get('DescriptionLengthClassifier', {}).get('LONG_BIO_50')
    result += "    finally, out of %s profiles: %s passed to next module, %s profiles did not.\r\n" % (
              statistics_data.get('DescriptionLengthClassifier', {}).get('SHORT_BIO_50') +
              statistics_data.get('DescriptionLengthClassifier', {}).get('LONG_BIO_50'),
              statistics_data.get('DescriptionLengthClassifier', {}).get('SHORT_BIO_50'),
              statistics_data.get('DescriptionLengthClassifier', {}).get('LONG_BIO_50')
    )

    for key, value in statistics_data.items():
        if key.startswith('Processor'):
            result += "\r\n"
            result += "%s (received %s profiles)\r\n" % (key, value.get('total'))

            passed = 0
            for k, v in value.items():
                if k not in ['total', 'total_passed']:
                    if k.startswith('UNSUITABLE'):
                        result += "    NOT set tag '%s' to profiles: %s\r\n" % (k.replace('UNSUITABLE_', ''), v)
                    else:
                        result += "    set tag '%s' to profiles: %s\r\n" % (k, v)
                        passed += v

            result += "    finally, out of %s profiles: %s passed to next module, %s profiles did not.\r\n" % (
                value.get('total'),
                value.get('total_passed'),
                value.get('total', 0) - value.get('total_passed', 0)
            )

    result += "\r\n"
    result += "OnlyBloggersProcessor (pre-upgrader, received %s profiles)\r\n" % \
              (statistics_data.get('OnlyBloggersProcessor', {}).get('VALID', 0) +
               statistics_data.get('OnlyBloggersProcessor', {}).get('INVALID', 0))
    result += "    profiles with tags 'blogger' or ('undecided' & SHORT_BIO_50): %s\r\n" % \
              statistics_data.get('OnlyBloggersProcessor', {}).get('VALID', 0)
    result += "    profiles without tags 'blogger' and ('undecided' & SHORT_BIO_50): %s\r\n" % \
              statistics_data.get('OnlyBloggersProcessor', {}).get('INVALID', 0)
    result += "    finally, out of %s profiles: %s passed to next module, %s profiles did not.\r\n" % (
        statistics_data.get('OnlyBloggersProcessor', {}).get('VALID', 0) +
        statistics_data.get('OnlyBloggersProcessor', {}).get('INVALID', 0),
        statistics_data.get('OnlyBloggersProcessor', {}).get('VALID', 0),
        statistics_data.get('OnlyBloggersProcessor', {}).get('INVALID', 0)
    )

    result += "\r\n"
    result += "Upgrader (received %s profiles)\r\n" % statistics_data.get('Upgrader', {}).get('given')
    result += "    set tag 'UPGRADED' (upgraded profiles) to profiles: %s\r\n" % \
              statistics_data.get('Upgrader', {}).get('UPGRADED')
    result += "    set tag 'SKIPPED' (did not upgrade due to multiple possible influencers) to profiles: %s\r\n" % \
              statistics_data.get('Upgrader', {}).get('SKIPPED_PROBLEM')
    result += "    were skipped due to being already upgraded: %s\r\n" % \
              statistics_data.get('Upgrader', {}).get('ALREADY_UPGRADED')
    result += "    were skipped due to already having influencer: %s\r\n" % \
              statistics_data.get('Upgrader', {}).get('ALREADY_HAS_INFLUENCER')
    result += "    finally, out of %s profiles: %s were successfully upgraded, %s profiles were not.\r\n" % (
        statistics_data.get('Upgrader', {}).get('given'),
        statistics_data.get('Upgrader', {}).get('UPGRADED'),
        statistics_data.get('Upgrader', {}).get('given', 0) - statistics_data.get('Upgrader', {}).get('UPGRADED', 0)
    )

    result += "\r\n"
    result += "ExtraDataUpgrader (received %s profiles)\r\n" % statistics_data.get('ExtraDataUpgrader', {}).get('given')
    result += "    set tag 'DATA_FETCH_ISSUED' (issued to getting data, may be not yet performed) to profiles: %s\r\n" % \
              statistics_data.get('ExtraDataUpgrader', {}).get('DATA_FETCH_ISSUED')
    result += "    set tag 'DATA_FETCHED' (already performed and received data) to profiles: %s\r\n" % \
              statistics_data.get('Upgrader', {}).get('DATA_FETCHED')
    result += "    were skipped due to having no influencer (already performed): %s\r\n" % \
              statistics_data.get('Upgrader', {}).get('NO_INFLUENCER')

    result += "    finally, out of %s profiles: %s were successfully updated with extra data.\r\n" % (
        statistics_data.get('ExtraDataUpgrader', {}).get('given'),
        statistics_data.get('ExtraDataUpgrader', {}).get('DATA_FETCHED')
    )

    if is_html:
        result = "<p>" + result.replace('\r\n', '</p><p>') + "</p>"

    return result


@task(name="social_discovery.profile_statistics.send_statistics_email", ignore_result=True)
def send_statistics_email():
    """
    Task to send statistics email for previous day.
    :return:
    """
    yesterday = date.today() - timedelta(days=1)
    yesterday_str = yesterday.isoformat()

    profiles = InstagramProfile.objects.filter(date_created__contains=yesterday_str)
    report_data = profiles_statistics_summary(profiles)
    report = build_stat_mail_text(report_data, is_html=True)

    mailsnake_client.messages.send(message={
        'html': 'Report for InstagramProfiles performed on %s\n\n%s' % (yesterday_str, report),
        'subject': 'Report for InstagramProfiles performed, %s' % yesterday_str,
        'from_email': 'atul@theshelf.com',
        'from_name': 'InstagramProfile Pipeline',
        'to': STATISTICS_TO_EMAILS}
    )

