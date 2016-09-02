import logging
from django.db.models.query import QuerySet
import json

from social_discovery.models import InstagramProfile
from social_discovery.pipelines import SEAPipeline, AustraliaPipeline, CanadaPipeline
from social_discovery.upgraders import Upgrader, ExtraDataUpgrader

log = logging.getLogger('social_discovery.crawler_draft')


def test_problematic_ones_prev():
    """
    For testing purposes of Upgrader. Can be removed later.
    :return:
    """
    log.info('Downloading data...')

    cases = []

    with open('/tmp/problem_profiles.txt', 'r') as f:
        for line in f:
            chunks = line.split(', ')
            # id_list = []
            data = {'profile_url': None, 'ids': []}
            for i, chunk in enumerate(chunks):
                if i == 0:
                    data['profile_url'] = chunk
                elif i % 2 == 1:
                    data['ids'].append(chunk)

            cases.append(data)

    log.info('Loaded data (%s strings)...' % len(cases))
    log.info('First one: %s' % cases[0])

    upgrader = Upgrader()

    with open('trying_resolving_problem.txt', 'a+') as f:
        for data in cases:
            result, method = upgrader.find_uncertain_prev(data['ids'])
            f.write('%s --> %s by method %s\n' % (data['profile_url'], result, method))


def test_problematic_ones():
    """
    For testing purposes of Upgrader. Can be removed later.
    :return:
    """
    log.info('Downloading data...')

    cases = []

    with open('/tmp/problem_profiles.txt', 'r') as f:
        for line in f:
            chunks = line.replace('\n', '').split(', ')
            # id_list = []
            data = {'profile_url': None, 'ids': []}

            data['profile_url'] = chunks.pop(0)

            ids = []
            while len(chunks) > 0:
                ids.append((chunks.pop(0), chunks.pop(0)))
            data['ids'] = ids

            cases.append(data)

    log.info('Loaded data (%s strings)...' % len(cases))
    log.info('First one: %s' % cases[0])

    # print(json.dumps(cases[:30], sort_keys=True, indent=4, separators=(',', ': ')))
    # return

    upgrader = Upgrader()

    with open('trying_resolving_problem.txt', 'a+') as f:
        distribution = {}
        for data in cases:
            result, method = upgrader.find_uncertain(data['ids'])
            if method in distribution:
                distribution[method] += 1
            else:
                distribution[method] = 1
            f.write('%s --> %s by method %s\n' % (data['profile_url'], result, method))
        f.write('Distribution: ')
        f.write(json.dumps(distribution, sort_keys=True, indent=4, separators=(',', ': ')))



def upgrade_sea_profiles(qty=None):
    """
    Upgrade SEA profiles:

    1. From all instagram profiles with > 1000 friends_count
    2. Run the SEA pipeline on this set. (need to make sure this doesn't go out of memory)
    3, Run the DescriptionLengthClassifier on undecided
    4. Now, pick relevant profiles to upgrade:
         => Classifier (have either Blogger or (SHORT_LEN_50 & Undecided tag))
         => Processor (has one of these SEA_LOCATION, SEA_LANGUAGE, SEA_HASHTAGS) but not the UNDECIDED ones
    5. Run upgrader on them (how many are these?)
       a) first check if there already exists an influencer => if only one, good, connect, and mark 'upgraded'
       b) if more than, mark problematic (as we discused today)
       c) if 0, then create one and mark 'upgraded'
    :return:
    """

    if isinstance(qty, QuerySet):
        profiles = qty
    else:
        # Getting all profiles with > 1000 friends_count and without existing discovered_influencer
        profiles = InstagramProfile.objects.filter(friends_count__gte=1000).exclude(discovered_influencer__isnull=False)
        if qty is not None:
            # limiting queryset if qty param defined
            profile_ids = profiles.values_list('id', flat=True)[:qty]
            profiles = profiles.filter(id__in=profile_ids)

    log.info('Initial profiles count: %s' % profiles.count())

    # Running SEA pipeline for this set
    # Since pipeline is working with a single id, just running it for each of them
    log.info('Pipeline starting...')
    pipeline = SEAPipeline()
    pipeline.run_pipeline(profiles)
    log.info('Pipeline performance completed (SEA).')


def upgrade_australia_profiles(qty=None):
    """
    Upgrade Australian and New Zealand profiles:

    1. From all instagram profiles with > 1000 friends_count
    2. Run the SEA pipeline on this set. (need to make sure this doesn't go out of memory)
    3, Run the DescriptionLengthClassifier on undecided
    4. Now, pick relevant profiles to upgrade:
         => Classifier (have either Blogger or (SHORT_LEN_50 & Undecided tag))
         => Processor (has one of these AUSTRALIA_LOCATION, AUSTRALIA_LANGUAGE, AUSTRALIA_HASHTAGS) but not the UNDECIDED ones
    5. Run upgrader on them (how many are these?)
       a) first check if there already exists an influencer => if only one, good, connect, and mark 'upgraded'
       b) if more than, mark problematic (as we discused today)
       c) if 0, then create one and mark 'upgraded'
    :return:
    """

    if isinstance(qty, QuerySet):
        profiles = qty
    else:
        # Getting all profiles with > 1000 friends_count and without existing discovered_influencer
        profiles = InstagramProfile.objects.filter(friends_count__gte=1000).exclude(discovered_influencer__isnull=False)
        if qty is not None:
            # limiting queryset if qty param defined
            profile_ids = profiles.values_list('id', flat=True)[:qty]
            profiles = profiles.filter(id__in=profile_ids)

    log.info('Initial profiles count: %s' % profiles.count())

    # Running SEA pipeline for this set
    # Since pipeline is working with a single id, just running it for each of them
    log.info('Pipeline starting...')
    pipeline = AustraliaPipeline()
    pipeline.run_pipeline(profiles)
    log.info('Pipeline performance completed (Australia).')


def upgrade_canada_profiles(qty=None):
    """
    Upgrade Canadian profiles:

    1. From all instagram profiles with > 1000 friends_count
    2. Run the SEA pipeline on this set. (need to make sure this doesn't go out of memory)
    3, Run the DescriptionLengthClassifier on undecided
    4. Now, pick relevant profiles to upgrade:
         => Classifier (have either Blogger or (SHORT_LEN_50 & Undecided tag))
         => Processor (has one of these CANADA_LOCATION, CANADA_LANGUAGE, CANADA_HASHTAGS) but not the UNDECIDED ones
    5. Run upgrader on them (how many are these?)
       a) first check if there already exists an influencer => if only one, good, connect, and mark 'upgraded'
       b) if more than, mark problematic (as we discused today)
       c) if 0, then create one and mark 'upgraded'
    :return:
    """

    if isinstance(qty, QuerySet):
        profiles = qty
    else:
        # Getting all profiles with > 1000 friends_count and without existing discovered_influencer
        profiles = InstagramProfile.objects.filter(friends_count__gte=1000).exclude(discovered_influencer__isnull=False)
        if qty is not None:
            # limiting queryset if qty param defined
            profile_ids = profiles.values_list('id', flat=True)[:qty]
            profiles = profiles.filter(id__in=profile_ids)

    log.info('Initial profiles count: %s' % profiles.count())

    # Running SEA pipeline for this set
    # Since pipeline is working with a single id, just running it for each of them
    log.info('Pipeline starting...')
    pipeline = CanadaPipeline()
    pipeline.run_pipeline(profiles)
    log.info('Pipeline performance completed (Australia).')


def issue_post_upgrade_for_existing():
    """
    one-time helper task, remove it after it is done.
    :return:
    """
    insta = InstagramProfile.objects.filter(friends_count__gte=1000)
    upgraded = insta.filter(tags__contains='UPGRADED')

    upgraded = upgraded.values_list('id', flat=True)

    print('Started issuing profiles...')

    edu = ExtraDataUpgrader()

    ctr = 0
    for profile_id in upgraded:
        edu.pipeline(profile_id)

        ctr += 1
        if ctr % 1000 == 0:
            print('Performed %s profiles...')

    print('Done, total %s profiles' % ctr)
