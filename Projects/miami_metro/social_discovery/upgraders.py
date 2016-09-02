import logging
import string
from urlparse import urlparse

import requests
from celery import task
from requests.exceptions import (
    Timeout, HTTPError, ConnectionError, TooManyRedirects,
)
from requests.packages.urllib3.exceptions import LocationParseError

from debra.models import Influencer, Platform, InfluencersGroup
from platformdatafetcher.pbfetcher import policy_for_platform
from social_discovery.crawler_task import crawler_task
from social_discovery.create_influencers import (
    get_influencers_email_name_location_for_profile,
    create_influencer_from_instagram,
)
from social_discovery.instagram_crawl import (
    connect_profiles_to_influencer, discover_blogs,
)
from social_discovery.models import InstagramProfile, SocialProfileOp
from social_discovery.pipeline_constants import get_queue_name_by_pipeline_step

"""
This file contains all Upgrader and derived modules for InstagramProfile pipeline.
"""

log = logging.getLogger('social_discovery.upgraders')


class Upgrader(object):
    """
    Intended to connect profiles to their corresponding influencers.
    ~ create_influencers_from_crawled_profiles() from create_influencer.py
    """

    def find_uncertain_prev(self, influencer_ids=None):
        """
        This function is used to find the most suitable existing influencer among the provided.

        Algorithm:
        1. Getting blog urls of all profiles with provided ids
        2. If there is a mix of artificical and non-artificial urls, stripping artificial ones.
        3. Checking remaining urls for duplicates. If all remaining urls are considered duplicates of
            each other, then returning one of them.
        4. Checking if domain names differ only by extension. If that happens, returning just the first id of them.
        5. Almost as the (3) but for final redirected urls

        """

        if type(influencer_ids) != list or len(influencer_ids) == 0:
            log.info('Incorrect influencer_ids parameter')
            return None, None

        # TODO: temporary skipping large amounts of urls (> 50)
        if len(influencer_ids) > 50:
            log.info('Too many influencer ids (%s), please check that manually.' % len(influencer_ids))
            return -1, 'Too many influencer ids (%s), please check that manually.' % len(influencer_ids)

        influencers = Influencer.objects.filter(id__in=influencer_ids)
        if influencers.count() == 0:
            # influencers do not exist
            log.info('influencer_ids parameter is empty')
            return None, None
        elif influencers.count() == 1:
            log.info('Incorrect influencer_ids parameter has only one value')
            return influencers[0].id, 0

        # Premeditation (list of data in format of a dict)
        pre_data = {}
        data = {}
        found_non_generic_urls = False
        for inf in influencers:
            if inf.blog_url is None or inf.blog_url == '':
                continue

            is_generic = True if 'theshelf.com/artificial' in inf.blog_url else False

            if not is_generic:
                found_non_generic_urls = True

                try:
                    u = requests.get(
                        inf.blog_url if inf.blog_url.startswith('http') else 'http://%s' % inf.blog_url,
                        timeout=10
                    )
                except (Timeout, HTTPError, ConnectionError, TooManyRedirects):
                    u = None
                except LocationParseError:
                    continue

            pre_data[inf.id] = {
                'blog_url': inf.blog_url,
                'redirect_url': inf.blog_url if is_generic or u is None else u.url,  # url after all redirects
                'is_generic': is_generic
            }

            # Checking if we have generic urls and normal, removing generic ones if normal are found
            if found_non_generic_urls:
                for k, v in pre_data.items():
                    if v['is_generic'] is False:
                        data[k] = v

        if len(data) == 1:
            log.info('Only one id left after premeditation phase...')
            return data.keys()[0], 0

        # checking if all of them are generic
        all_artificial = True
        for k, v in data.items():
            if not v['is_generic']:
                all_artificial = False
                break
        if all_artificial:
            log.info('All influencers are artificial, returning one of them...')
            return data.keys()[0], 0

        # Step 3. Checking if they are all duplicates one of each other by their blog_url
        url = data.items()[0][1]['blog_url']
        log.info('Finding duplicates for url %s ...' % url)
        duplicates = Influencer.find_duplicates(blog_url=url)

        duplicates_counter = 0
        for duplicate in duplicates:
            if duplicate.id in data:
                duplicates_counter += 1

        if len(data) == duplicates_counter:
            log.info('Seems influencers are duplicates, deciding who stays...')
            return influencers[0]._select_influencer_to_stay(duplicates).id, 1

        log.info('Seems influencers with ids %s are not duplicates, moving on...' % data.keys())

        # Step 4. Checking for domain names differ only by extension
        core = None
        are_same = True
        for i, inf in data.items():

            parsed_url = urlparse(inf['blog_url'])
            if parsed_url.path not in ['', '/']:
                log.info('url non-empty path found, comparing by domains impossible...')
                are_same = False
                break

            domain = parsed_url.netloc
            chunks = domain.split(':')[0]
            chunks = chunks.split('.')
            if len(chunks) > 1:
                chunks = chunks[:-1]
            domain = ".".join([part for part in chunks if part != 'www'])
            if core is None:
                core = domain
            else:
                if domain != core:
                    are_same = False
                    break

        if are_same:
            log.info('Seems these influencers are the same by blog netlocs, returning result...')
            return data.keys()[0], 2

        log.info('Seems influencers with ids %s are not the same by blog netlocs, moving on...' % data.keys())

        # Step 5. Checking if redirects are the same
        same_redirects = True
        core = None
        for inf in data.values():
            if core is None:
                core = inf['redirect_url']
            elif core != inf['redirect_url']:
                same_redirects = False
                break

        if same_redirects is True:
            log.info('Seems influencers are duplicates according to final redirects of their blog_urls...')
            return data.keys()[0], 3

        # Step 6. Checking if they are of the same blog by pattern with path of /yyyy/mm/title_chunk/
        same_posts_of_one = True
        blog_domain = None
        for inf in data.values():
            parsed_url = urlparse(inf['blog_url'])
            path_chunks = parsed_url.path.split('/')
            path_chunks = filter(None, path_chunks)

            # checking if path follows the logic of /yyyy/mm/<title of the post>
            if len(path_chunks) < 3:
                same_posts_of_one = False
                break

            # checking year (4 digits) and month (2 digits) and possibly day
            year_found = False
            for a in path_chunks[:2]:
                if len(a) == 4 and a.isdigit() and 1990 <= int(a) <= 2100:  # :-)

                    if not year_found:
                        # year found
                        year_found = True
                    else:
                        # second year found? No way...
                        same_posts_of_one = False
                        break
                elif len(a) == 2 and a.isdigit() and 1 <= int(a) <= 31:
                    # day or month
                    pass
                else:
                    # not a year or month
                    same_posts_of_one = False
                    break

            # rare case if month and day are before year
            if not year_found:
                a = path_chunks[2]
                if not (len(a) == 4 and a.isdigit() and  1990 <= int(a) <= 2100):
                    # No year detected, our pattern is not applied
                    same_posts_of_one = False
                    break

            if blog_domain is None:
                blog_domain = parsed_url.netloc
            elif blog_domain != parsed_url.netloc:
                same_posts_of_one = False
                break

        if same_posts_of_one:
            log.info('Seems influencers have blog_urls that are post urls of the same blog...')
            return data.keys()[0], 4

        log.info('Could not determine the staying influencer, exiting...')
        return -1, -1

    def find_uncertain(self, data=None):
        """
        Input format:
        [(2703057, 'http://www.theshelf.com/artificial_blog/1936528-84df6d92-f1a4-4a03-8d53-270ae6619914.html'), (2456449, 'http://wholesaleclothingkorea.com/')]
        [(2758024, 'http://smokykohl.com'), (2415803, 'http://smokykohl.com/')]


        So, we're working only on data of id/blog_url pairs, without calling DB.

        1. Iterate over list of urls.
            If there are only artificial urls, return the lowest id.
            If there are artificial urls and normal urls, then strip all elements with artificial urls from input data.
            * Example: [(2703057, 'http://www.theshelf.com/artificial_blog/1936528-84df6d92-f1a4-4a03-8d53-270ae6619914.html'), (2456449, 'http://wholesaleclothingkorea.com/')]

        2. If there is only one element left, return it.
            * Example: [(2703057, 'http://www.theshelf.com/artificial_blog/1936528-84df6d92-f1a4-4a03-8d53-270ae6619914.html'), (2456449, 'http://wholesaleclothingkorea.com/')]

        3. If there are several elements with non-artificial urls, trying to bring that urls to a identical form (stripping 'www' in (LOWERCASED!) netloc, ignoring schemas, trailing slashes if path is only '/'.
           If all netlocs+paths are the same, return (which?) id.
            * Example: [(2758024, 'http://smokykohl.com'), (2415803, 'http://smokykohl.com/')]
            * Example: [(2758075, 'http://FUSS.CO.IN'), (748797, 'http://fuss.co.in/')]

        4. If all urls have no path part and are different only by domain suffix, then PROBABLY they are the same influencer. Return one of them (preferrably, .com may be?).
            * Example: [(748604, 'http://www.fashionata.be'), (2758279, 'http://www.fashionata.com')]
            * Example: [(2758073, 'http://xiaxue.blogspot.com'), (892887, 'http://xiaxue.blogspot.de')]

            * What to do with these ones? [(2758537, 'http://ohpageboys.blogspot.com'), (19547, 'http://ohpageboys.blogspot.co.uk')]
                                          [(2770040, 'http://inalathifahs.blogspot.co.id'), (1279631, http://inalathifahs.blogspot.com)]

        5. If all urls have THE SAME netloc of certain domains (usually 3-part: username.blogspot.com/ ), we could try to check that's username with netloc 'core' to find corellation:
            * Example: [(1054628, 'http://www.indianshringar.com/'), (982460, 'http://indianshringar.blogspot.com/')]

        6. If path's mask has some number parts before like /YYYY/MM/post-header/ or /MM/DD/YYYY/post-header/ or some alike pattern AND the same netloc, then it is definitely the same blog:
            * Example: [(2762275, 'http://myfunfoodiary.com'), (2587259, 'http://myfunfoodiary.com/2015/08/new-post-nasi-campur-kencana-fresh-market-pik-cabang-itc-mangga-dua/#sthash.l9iy7ksr.dpbs')]

        7. If netloc is the same, and path has only one part and it looks like a slug or empty, then it seems that these are also the same influencer:
            * Example: [(2640281, 'http://www.nadnut.com/singapore-staycations-marriott-hotel/'), (2599730, 'http://www.nadnut.com/teppei-japanese-restaurant-quality-omakase-at-an-affordable-price/'), (2374871, http://www.nadnut.com)]

        <<< SOME MORE STEPS? >>>

        ?. If none matched, then return -1, so it should be checked manually.
        """
        blog_platforms = [
            'blogspot.com',
            'wordpress.com',
            # insert more here!
        ]

        # Step 0. Premeditation check
        if not isinstance(data, list):
            log.info('Step 0: Data is not a list, exiting...')
            return None, 0
        if len(data) == 0:
            log.info('Step 0: Data is an empty list, exiting...')
            return None, 0
        elif len(data) == 1:
            log.info('Step 0: Data has only one value, returning its id...')
            return data[0][0], 0

        # Step 1. Artificial urls check
        urls = []

        # check if artificial urls present
        for entry in data:
            if 'theshelf.com/artificial' not in entry[1]:
                try:
                    parsed_url = entry[1].split('#')[0].strip('/')
                    parsed_url = urlparse(parsed_url)
                    if parsed_url.netloc:
                        urls.append([entry[0], parsed_url])
                except:
                    # something has happened while
                    log.error('Step 1: Can not urlparse given url: %s , skipping it...' % entry[1])
                    pass

        # TODO: Here we also could check quantity of remaining urls

        # Step 2. Checking non-artificial urls
        if len(urls) == 0:
            # all urls are artificial, return first (?)
            log.info('Step 1: All urls are artificial, returning just first of them...')
            return data[0][0], 1
        elif len(urls) == 1:
            # got 1 good url, returning it
            log.info('Step 2: One good url remains, returning its id...')
            return urls[0][0], 2

        # Step 3. Bringing urls to the same form (stripping starting www. , removing '/' netloc), checking similarity
        netloc_path = None
        similar = True
        for entry in urls:
            # performing netloc
            netloc = entry[1].netloc
            netloc = netloc.lower()
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            if entry[1].netloc != netloc:
                entry[1] = entry[1]._replace(netloc=netloc)

            # performing path
            path = entry[1].path
            if path == '/':
                entry[1] = entry[1]._replace(path='')

            # performing a check
            if netloc_path is None:
                log.info("Step 3: Netloc path set: %s%s" % (entry[1].netloc, entry[1].path))
                netloc_path = "%s%s" % (entry[1].netloc, entry[1].path)
            elif netloc_path != "%s%s" % (entry[1].netloc, entry[1].path):
                similar = False
                # log.info("Step 3: Netloc path differs for: %s%s , going to next step..." % (entry[1].netloc, entry[1].path))
                # break

        if similar:
            best_id = Influencer.objects.get(id=urls[0][0])._select_influencer_to_stay(Influencer.objects.filter(id__in=[u[0] for i, u in enumerate(urls) if i > 0])).id
            log.info("Step 3: Similarity detected, returning most suitable id: %s" % best_id)
            return best_id, 3

        # Step 3.5: checking redirections. Removing queries ('?param1=val1&param2=val2' part)
        if len(urls) < 50:
            for entry in urls:
                try:
                    url = entry[1].geturl()
                    req = requests.get(url, timeout=10)
                    url = req.url
                    url = url.split('#')[0].strip('/')
                    url = urlparse(url)
                    if url.netloc.startswith('www.'):
                        url = url._replace(netloc=url.netloc[4:])

                    url = url._replace(query='')
                    url = url._replace(path=url.path.strip('/'))

                    entry[1] = url
                    # log.info(entry[1])
                except Exception as e:
                    # log.error(e)
                    pass
            log.info('Fetched %s redirected urls' % len(urls))
        else:
            log.info('There are %s urls to check redirects, better to check that manually.')

        # Step 4. No path part and differece is only in domain suffix.
        empty_path = True
        com_id = None
        netloc_chunk = None
        similar = True
        for entry in urls:
            # checking empty path
            if entry[1].path != '':
                empty_path = False
                break

            # checking domain
            chunks = entry[1].netloc.split(':')[0].split('.')
            if chunks[-1] == 'com' and com_id is None:
                com_id = entry[0]
            if netloc_chunk is None:
                netloc_chunk = '.'.join(chunks[:-1])
            elif netloc_chunk != '.'.join(chunks[:-1]):
                # TODO: FIX for these suffixes:  .com  VS .co.uk
                similar = False
                break

        if similar and empty_path:
            log.info("Step 4: Domain similarity without suffix detected, returning id: %s" % com_id if com_id is not None else urls[0][0])
            return com_id if com_id is not None else urls[0][0], 4

        # Step 5. Checking blog platform usernames and 2-nd level domains.
        # Netlocs with blog platforms should start with username,
        # netlocks without them must contain only that username and suffix.

        similar = True
        username_chunk = None
        best_id = None
        fewest_chunks = None

        # phase 1. Detecting username chunk...
        for entry in urls:
            failed = False
            for platform in blog_platforms:
                if entry[1].netloc.endswith(platform):

                    chunks = entry[1].netloc[:-len(platform)]  # .strip('.').split('.')
                    username = chunks.strip('.')  # '.'.join([w for w in chunks if w])

                    if username_chunk is None:
                        # setting username_chunk
                        username_chunk = username
                        log.info("Step 5: Username_chunk set: %s" % username)
                    elif username_chunk != username:
                        similar = False
                        failed = True
                        log.info("Step 5: Different usernames detected for platforms, going to the next step...")
                        break
                    if best_id is None:
                        best_id = entry[0]
                        # fewest_chunks = entry[1].netloc.split('.')

            if failed:
                break

        # phase 2. Comparing non-platform domains with username_chunk
        if similar:
            for entry in urls:
                # for platform in blog_platforms:
                if not any([entry[1].netloc.endswith(pl) for pl in blog_platforms]):

                    # TODO: may be we could check any appearence of username_chunk in netloc here? Although, false positives possible.
                    chunks = entry[1].netloc.split(username_chunk)
                    if len(chunks) == 1:
                        # no appearence of username_chunk in netloc
                        log.info("Step 5: netloc %s does not contain username %s, proceeding to the next step..." % (entry[1].netloc, username_chunk))
                        similar = False
                        break
                    elif len(chunks) == 2 and chunks[0] == '' and len(chunks[1].strip('.').split('.')) == 1:
                        # good match
                        log.info('Step 5: username found as 2-nd level domain')
                        # if entry[0] < best_id:  # and entry[1].netloc.split('.') < fewest_chunks:  # lowest id
                        best_id = entry[0]
                            # fewest_chunks = entry[1].netloc.split('.')
                    else:
                        # something strange
                        log.info("Step 5: Weird result for netloc %s containing username %s, proceeding to the next step..." % (entry[1].netloc, username_chunk))
                        similar = False
                        break

        if similar:
            # TODO: Which id should we return in this case?
            log.info("Step 5: Domain similarity with username detected, returning id: %s" % best_id)
            return best_id, 5

        # Step 6. Checking pattern for year/month (/day)
        netloc_chunk = None
        similar_dateformat = True
        digit_pattern = []
        best_id = None

        for entry in urls:

            # checking netloc
            netloc = entry[1].netloc
            if netloc_chunk is None:
                log.info("Step 6: Netloc path set: %s" % netloc)
                netloc_chunk = netloc
            elif netloc_chunk != netloc:
                similar_dateformat = False
                log.info("Step 6: Netloc differs for: %s , going to next step..." % netloc)
                break

            # checking path
            path = entry[1].path
            if path != '':  # empty path is fine
                log.info("Step 6: path not empty...")

                if best_id is None:
                    best_id = entry[0]

                chunks = path.strip('/').split('/')

                # now we need to check possible combinations: 1 4-digit (1990...2100), 0..2 2-digit (01..31)
                if len(digit_pattern) == 0:   # digit_pattern is None:
                    log.info('Digit pattern initialization...')
                    # maximum 3 first chunks could be numeric
                    failed = False
                    for chunk in chunks[:3]:
                        # log.info('Checking chunk: %s' % chunk)
                        if chunk.isdigit():

                            l = len(chunk)
                            # year check
                            if l == 4 and l not in digit_pattern and 1990 <= int(chunk) <= 2100:
                                # log.info('Seems we have found a year...')
                                digit_pattern.append(l)
                            elif l == 2 and 01 <= int(chunk) <= 31:
                                # log.info('Seems we have found a day or month...')
                                digit_pattern.append(l)
                            else:
                                failed = True
                                break
                        else:
                            # part is not digital, finishing application
                            # log.info('Chunk is not digit, finishing processing chunks')
                            break

                    if failed:
                        break

                else:
                    log.info('Checking path for date pattern. chunks: %s   digit_pattern: %s' % (chunks, digit_pattern))
                    if len(digit_pattern) == 0 or len(chunks) < len(digit_pattern):
                        log.info('Bad date pattern format...')
                        similar_dateformat = False
                        break

                    # checking similarity for dates
                    for ii, digit in enumerate(digit_pattern):
                        if len(chunks[ii]) != digit:
                            log.info('Length of %s is not %s, checking failed' % (chunks[ii], digit))
                            similar_dateformat = False
                            break

            else:
                best_id = entry[0]
                log.info("Step 6: best id detected: %s" % best_id)

        if similar_dateformat and len(digit_pattern) > 0:
            log.info("Step 6: Seems the urls are of the same blog with date path, returning id: %s" % best_id)
            return best_id, 6

        # Step 7. Checking for same netloc and single-elemented sluggified path
        netloc_chunk = None
        similar = True
        best_id = None

        slug_symbols = set(string.ascii_lowercase + '-')

        for entry in urls:
            # checking netloc
            netloc = entry[1].netloc
            if netloc_chunk is None:
                log.info("Step 7: Netloc path set: %s" % netloc)
                netloc_chunk = netloc
            elif netloc_chunk != netloc:
                similar = False
                log.info("Step 7: Netloc differs for: %s , going to next step..." % netloc)
                break

            # checking path
            path_chunks = entry[1].path.split('/')

            if len(path_chunks) == 1 and path_chunks[0] == '':
                # empty path, good netloc
                best_id = entry[0]
            elif len(path_chunks) == 2 and path_chunks[0] == '':
                # path is slugyfied?
                if set(path_chunks[1]) <= slug_symbols:
                    # yes
                    pass
                else:
                    # no
                    similar = False
                    break
            else:
                similar = False
                break

        if similar:
            log.info("Step 7: Seems the urls are of the same blog with post slugs, returning id: %s" % best_id)
            return best_id, 7

        log.info("Unfortunately, corellation was not found, returning -1...")
        return -1, -1

    def upgrade_profile(self, profile=None):
        """
        This method upgrades given profile. Will not upgrade profile if it already has tag 'UPGRADED' or has not empty
        value of discovered_influencer. Checking this profile with connect_profiles_to_influencer(qset) method.
        If no influencer returned: Create influencer and connect it. Tag profile as 'UPGRADED'.
        If 1 influencer returned: Connect it to profile. Tag profile as 'UPGRADED'.
        """

        if profile is None:
            log.info('Profile to upgrade is None')
            return None
        elif isinstance(profile.discovered_influencer, Influencer):
            log.info('Profile already has an influencer')
            return 'ALREADY_HAS_INFLUENCER'

        # checking for required tags
        tags = profile.tags.split()
        if 'UPGRADED' in tags:
            log.info('Profile was already upgraded')
            return 'ALREADY_UPGRADED'

        # upgrading this guy:
        # Here we fetch all possible influencer for this profile and act depending on what did we find:
        # 1 influencer, no influencers or several influencers.
        queryset = InstagramProfile.objects.filter(id=profile.id)
        result = connect_profiles_to_influencer(queryset)

        good = result.get('good', [])
        if len(good) > 0:
            # got a good result
            log.info('Found 1 influencer - good result, connecting it to profile...')
            candidate = good[0].values()[0].pop()
            log.info('Candidate: %s' % candidate)
            profile.discovered_influencer = candidate
            profile.append_mutual_exclusive_tag('UPGRADED', ['UPGRADED', 'SKIPPED'])
            profile.save()
            return 'UPGRADED'

        none = result.get('none', [])
        if len(none) > 0:
            # got a none result
            log.info('Found no influencers - creating new one and connecting it to profile...')

            # Old code:
            # _, inf = create_influencer_from_instagram(profile_id=profile.id, to_save=True)
            # profile.discovered_influencer = inf
            # profile.append_mutual_exclusive_tag('UPGRADED', ['UPGRADED', 'SKIPPED'])
            # profile.save()

            # New code:
            response = discover_blogs(profile_id=profile.id, category=None, to_save=True)

            # This function can return following responses:
            # EXISTING_BLOG -- blog_url of real blog
            # ARTIFICIAL_BLOG -- blog_url is artificial, no real blog url is found
            # INFLUENCER_CREATION_ERROR_MULTIPLE_BLOGS -- several blog urls detected, influencer is not created
            # INFLUENCER_CREATION_ERROR_ALL_BLACKLISTED -- influencer is blacklisted
            # INFLUENCER_CREATION_ERROR_MULTIPLE_INSTA_PROFILES -- multiple Instagram profiles detected
            if response in ['EXISTING_BLOG', 'ARTIFICIAL_BLOG']:
                # denormalizing it
                try:
                    this_profile = InstagramProfile.objects.get(id=profile.id)
                    inf = this_profile.discovered_influencer
                    if inf is not None:
                        inf.denormalize_fast()
                except InstagramProfile.DoesNotExist:
                    log.error('Could not get InstagramProfile %s for influencer denormalization.' % profile.id)

                # Re-acquiring profile with updated data and adding 'UPGRADED' tag.
                # It is necessary for not to overwrite existing data.
                try:
                    profile = InstagramProfile.objects.get(id=profile.id)
                    profile.append_mutual_exclusive_tag('UPGRADED', ['UPGRADED', 'SKIPPED'])
                except InstagramProfile.DoesNotExist:
                    log.error('Could not get InstagramProfile %s to add "UPGRADED" tag.' % profile.id)

                return 'UPGRADED'
            return response

        problem = result.get('problem', [])
        if len(problem) > 0:
            # got the worst case
            # TODO: skipping for now, add code for getting correct influencer id when we're happy with it.
            log.info('Found possible %s matching problematic influencers - skipping for now...' % len(problem[0].values()))
            profile.append_mutual_exclusive_tag('SKIPPED', ['UPGRADED', 'SKIPPED'])
            return 'SKIPPED_PROBLEM'

        return 'UPGRADED'

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        Pipeline method for upgrading single profile and deciding if it will go further by pipeline's route.
        """

        log.info('Started %s.pipeline(profile_id=%s, route=%s)' % (type(self).__name__, profile_id, route))
        # Fetching data from kwargs
        try:
            profile = InstagramProfile.objects.get(id=profile_id)
            result = self.upgrade_profile(profile)

            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile.id,
                description=result,
                module_classname=type(self).__name__,
                data={}
            )

            log.info('result=%s' % result)

            # proceeding with pipeline route if result is suitable
            if type(route) is list and len(route) > 1 and result in ['UPGRADED',
                                                                     'ALREADY_HAS_INFLUENCER',
                                                                     'ALREADY_UPGRADED']:
                log.info('Proceeding to the next step: %s' % route[1])
                crawler_task.apply_async(
                    kwargs={
                        'klass_name': route[1],
                        'task_type': 'pipeline',
                        'profile_id': profile.id,
                        'route': route[1:],
                    },
                    queue=get_queue_name_by_pipeline_step(route[1])
                )
            else:
                log.info('Route finished or terminating route because of result.')

        except InstagramProfile.DoesNotExist:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)


@task(name="social_discovery.upgraders.fetch_extra_data_task", ignore_result=True)
def fetch_extra_data_task(profile_id=None):
    """
    Task to fetch additional info for freshly created influencer
    :param profile_id: id of profile to perform
    :return:
    """
    if profile_id is None:
        return

    try:
        # getting profile, influencer, platforms that are not artificial
        profile = InstagramProfile.objects.get(id=profile_id)
        influencer = profile.discovered_influencer
        if influencer is not None:
            # fetching all non-artificial platforms and gathering info from them
            platforms = influencer.platform_set.exclude(url__contains='theshelf.com/artificial')
            log_data = {'plats': []}
            for platform in platforms:
                policy = policy_for_platform(platform)

                # TODO:
                # # if there is a platform with url_not_found=True, setting it to False for rediscovery purposes
                # # otherwise it will not work good this step
                # if platform.url_not_found is True:
                #     platform.url_not_found = False
                #     platform.save()

                log_data['plats'].append(platform.id)

            get_influencers_email_name_location_for_profile(profile_id, to_save=True)

            # fetching profile pic for this updated influencer
            try:
                inf = Influencer.objects.get(id=influencer.id)
                inf.set_profile_pic()
            except Influencer.DoesNotExist:
                log.error('Influencer with id=%s not found when tried to set profile image.')

            # Appending tag
            profile.append_tag('DATA_FETCHED')

            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile.id,
                description='DATA_FETCHED',
                module_classname='ExtraDataUpgrader',
                data=log_data
            )
        else:
            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile.id,
                description='NO_INFLUENCER',
                module_classname='ExtraDataUpgrader',
                data={}
            )

    except InstagramProfile.DoesNotExist:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)


class ExtraDataUpgrader(object):
    """
    This module is intended to get additional data to freshly-created influencer.

    """

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        Pipeline method for getting extra data for freshly-created influencer and deciding
        if it will go further by pipeline's route.
        """

        log.info('Started %s.pipeline(profile_id=%s, route=%s)' % (type(self).__name__, profile_id, route))

        try:
            # getting profile
            profile = InstagramProfile.objects.get(id=profile_id)

            # Technically, we just issue task here and that's all. We do not wait untill it will be complete.
            fetch_extra_data_task.apply_async(
                kwargs={
                    'profile_id': profile.id,
                },
                queue='fetch_extra_data_for_influencer'  # queue for tasks to get extra data
            )

            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile.id,
                description='DATA_FETCH_ISSUED',
                module_classname=type(self).__name__,
                data={}
            )

            # proceeding with pipeline route if result is suitable
            if type(route) is list and len(route) > 1:
                log.info('Proceeding to the next step: %s' % route[1])
                crawler_task.apply_async(
                    kwargs={
                        'klass_name': route[1],
                        'task_type': 'pipeline',
                        'profile_id': profile.id,
                        'route': route[1:],
                    },
                    queue=get_queue_name_by_pipeline_step(route[1])
                )
            else:
                log.info('Route finished or terminating route because of result.')

        except InstagramProfile.DoesNotExist:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)


class HaveYoutubeUpgrader(Upgrader):
    """
    Upgrader for task for instagram profiles with youtube
    """

    def upgrade_profile(self, profile=None):
        """
        This method upgrades given profile with new rules:

        1. get_username(InstagramProfile.url)
        2. check if we have a Platform object of Instagram that has the same validated_handle..
        3. If yes
           3.a) if at least one of the found platforms has url_not_found = False =>
                    -- if more than one ? Issue 'multiple_platforms_found' tag.
                    --connect InstagramProfile with this platform's influencer, Issue 'UPGRADED' tag

        a) no platform that has the validated_handle == username is found => we should create a new influencer, Issue 'UPGRADED' tag.
        b) only one platform with url_not_found = False, then connect. Issue 'UPGRADED' tag
        c) else, tag this InstgramProfile with 'multiple_platforms_found'


        Notes:
        (1) validated_handle -- appears to be a numeric id, but not a username
        (2) remember Youtube url! If we create a new influencer or do not find influencer by its instagram data,
        we need to check an existing Youtube url to make search for this also.
        (3) chain detection thing to use here?

        """

        # if profile is None:
        #     log.info('Profile to upgrade is None')
        #     return None
        # elif isinstance(profile.discovered_influencer, Influencer):
        #     log.info('Profile already has an influencer')
        #     return 'ALREADY_HAS_INFLUENCER'
        #
        # # checking for required tags
        # tags = profile.tags.split()
        # if 'UPGRADED' in tags:
        #     log.info('Profile was already upgraded')
        #     return 'ALREADY_UPGRADED'

        # from platformdatafetcher.platformutils import username_from_platform_url
        #
        # detecting validated_handle
        # insta_url = profile.get_url()
        # user_name = username_from_platform_url(insta_url)

        # this_validated_handle = utils.nestedget(self._data, 'entry_data', 'ProfilePage', 0, 'user', 'id')

        # TODO: elaborate the method of fetching appropriate platform/influencer except this_validated_handle
        this_validated_handle = profile.api_data.get('id') if profile.api_data is not None else None

        log.info('This InstagramProfile\'s validated_handle: %s' % this_validated_handle)

        # checking if we already have a Platform object of Instagram that has the same validated_handle
        if this_validated_handle is not None and len(this_validated_handle) > 0:
            existing_plats = Platform.objects.filter(platform_name='Instagram',
                                                     validated_handle=this_validated_handle)
            if existing_plats.count() == 1:
                # Yay! we found our platform and influencer
                log.info('Good! We found a single platform for this InstagramProfile: %s' % profile.platform)
                profile.platform = existing_plats[0]
                profile.discovered_influencer = existing_plats[0].influencer
                profile.append_mutual_exclusive_tag('UPGRADED', ['UPGRADED', 'SKIPPED', 'multiple_platforms_found'])
                profile.save()
                return 'UPGRADED'
            elif existing_plats.count() == 0:
                # No existing platform detected -- creating a new influencer here.
                log.info('Ok, we found no platform for this InstagramProfile\'s '
                         'validated_handle, so creating a new influencer here')
                _, inf = create_influencer_from_instagram(
                    profile_id=profile.id, to_save=True
                )
                profile.discovered_influencer = inf
                profile.append_mutual_exclusive_tag('UPGRADED', ['UPGRADED', 'SKIPPED'])
                profile.save()
                return 'UPGRADED'

            else:
                # Hmmm.... Found more than 1 platform. Difficult case, checking if there
                # is only one with 'url_not_found=False'
                log.info('Found more than 1 platform for this InstagramProfile\'s '
                         'validated_handle, investigating those with url_not_found!=True...')
                unf_existing_plats = existing_plats.exclude(url_not_found=True)

                if unf_existing_plats.count() == 1:
                    # Ok, looks like this is one active platform, so it will the one we seek...
                    log.info('Good! We found a single platform for this '
                             'InstagramProfile with url_not_found!=True: %s' % profile.platform)
                    profile.platform = unf_existing_plats[0]
                    profile.discovered_influencer = unf_existing_plats[0].influencer
                    profile.append_mutual_exclusive_tag(
                        'UPGRADED', ['UPGRADED', 'SKIPPED', 'multiple_platforms_found']
                    )
                    profile.save()
                    return 'UPGRADED'
                elif unf_existing_plats.count() == 0:
                    # Weird, no platforms with url_not_found=False
                    log.info('No platform for this InstagramProfile '
                             ' with url_not_found!=True ... what should we do here... for now, tagging it'
                             ' with multiple_platforms_found tag')
                    # TODO: ??? This case is weird
                    profile.append_mutual_exclusive_tag(
                        'multiple_platforms_found', ['UPGRADED', 'SKIPPED', 'multiple_platforms_found']
                    )
                    profile.save()
                    return 'multiple_platforms_found'
                else:
                    # Another murky case - several of them with url_not_found=False ...
                    log.info('Found more than 1 platform for this InstagramProfile\'s '
                             ' with url_not_found!=True, setting multiple_platforms_found tag, weird case.')
                    profile.append_mutual_exclusive_tag(
                        'multiple_platforms_found', ['UPGRADED', 'SKIPPED', 'multiple_platforms_found']
                    )
                    profile.save()
                    return 'multiple_platforms_found'
        else:
            log.error('Validated handle is None or its length is 0. Skipping...')
            profile.append_mutual_exclusive_tag('SKIPPED', ['UPGRADED', 'SKIPPED', 'multiple_platforms_found'])
            profile.save()
            return 'SKIPPED'


class HaveYoutubeExtraDataUpgrader(ExtraDataUpgrader):
    """
    ExtraDataUpgrader for task for instagram profiles with youtube
    """
    pass


class LightUpgrader(Upgrader):
    """
    This upgrader upgrades profiles according their found platforms/platform ids
    """

    def upgrade_profile(self, profile=None):
        """
        This method upgrades given profile with new rules:

        1. InstagramProfile provided
        2. For this profile we detect all interesting social/non-sicial platforms we already have in DB.
            According to found platforms we detect influencers. 3 cases are possible:

            a) NO Platforms found ==> NO Influencers found, GOOD --> we create these platform, create influencer,
                set it as discovered_influencer, getting extra data for p,latforms/influencer.
            b) SOME Platforms found --> ONE common Influencer found for these platforms, AWESOME! --> creating
                missing platforms(if any), attaching them to this influencer, set it as discovered_influencer,
                getting extra data for platforms(if needed)

            c) SOME Platforms found --> SEVERAL common Influencer found for these platforms, DIFFICULT CASE!
               We need to think out a plan what to do here...

        """

        if profile is None:
            log.info('Profile to upgrade is None')
            return None

        log.info('LightUpgrader: performing InstagramProfile %s' % profile.id)
        from social_discovery.influencer_creator import InfluencerCreator
        ic = InfluencerCreator(profile=profile, save=True)
        result = ic.detect_influencer()

        return result

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        Pipeline method for upgrading single profile and deciding if it will go further by pipeline's route.
        """

        log.info('Started %s.pipeline(profile_id=%s, route=%s)' % (type(self).__name__, profile_id, route))
        # Fetching data from kwargs
        try:
            profile = InstagramProfile.objects.get(id=profile_id)
            result = self.upgrade_profile(profile)

            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile.id,
                description=result,
                module_classname=type(self).__name__,
                data={}
            )

            log.info('result=%s' % result)

            # proceeding with pipeline route if result is suitable
            if type(route) is list and len(route) > 1 and result is not None and result not in ['10_days_later',
                                                                                                'IC_possible_brand']:
                log.info('Proceeding to the next step: %s' % route[1])
                crawler_task.apply_async(
                    kwargs={
                        'klass_name': route[1],
                        'task_type': 'pipeline',
                        'profile_id': profile.id,
                        'route': route[1:],
                    },
                    queue=get_queue_name_by_pipeline_step(route[1])
                )
            else:
                log.info('Route finished or terminating route because of result.')

        except InstagramProfile.DoesNotExist:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)


class LightExtraDataUpgrader(object):
    """
    This module is intended to get additional data to freshly-created/connected influencer by LightUpgrader.

    """

    # group names where the influencer will be put
    group_name_processed_non_artificial = 'upgraded_from_instagram_processed_non_artificial_non_qa'
    group_name_processed_artificial = 'upgraded_from_instagram_processed_artificial_non_qa'

    def update_created_influencer(self, profile):
        """
        Once an influencer is created or associated with an instagram profile
        (only for influencers with not old_show_on_search=True):
            a) Run new_influencer processing (so that we extract platforms) (
            check postprocessing.py: process_new_influencer_sequentially()):
                1) We need to make sure that social_urls_extracted are added to these influencers or at least they
                    exist even after this platform extraction
                2) Make sure that we run the algorithm to detect emails and names and other variables from the
                    social profiles (AutomaticAttributeSelector)
                3) Do we need to run denormalization to make sure we have a picture too?
            b) Without artificial urls based influencers
                1) These should be upgraded to show_on_search=True (if they are not already)
                2) Run new_influencer processing ((AutomaticAttributeSelector))
                3) Add these to "upgraded_from_instagram_processed_non_qa"
                    (a) The QA table should pick influencers from this collection
                    (b) Once they are saved, they should be removed from this collection and added to a new
                        collection "upgraded_from_instagram_qaed"
                    (c) Run denormalization
            c) If artificial_url
                1) should be added to a separate collection, "upgraded_from_instagram_artificial_non_qa"
                2) Same as above processing
            d) We should then add social_url_detection, platform-id-detection, and lightinfluencercreator to the
              pipelines so that any future instagram profile is already handled
                1) We should make sure that this processing is not done if a profile already has an
                    Influencer associated, however, we should still tag them because the same
                    influencer could have multiple tags
                2) We should clean up all instagram profiles and their connection with Influencers (except
                    those which are in the mommy_tags)

        UPDATE:  actually, we can still keep the tag group the same, no need to create a unique tag group

        :param profile_id: instagramProfile id
        :return:
        """

        from platformdatafetcher.postprocessing import _do_process_new_influencer_sequentially, FetchAllPolicy
        from platformdatafetcher.influencerattributeselector import AutomaticAttributeSelector
        from platformdatafetcher.platformextractor import _platforms_from_links
        from platformdatafetcher.fetcher import fetcher_for_platform

        # finding out the tag from upgrader
        ic_tag = None
        tags = profile.tags.split() if profile.tags is not None else []
        for t in tags:
            if t.lower().startswith('ic_'):
                ic_tag = t
        log.info('IC tag: %s' % ic_tag)

        if profile.discovered_influencer is None:
            log.info("%r doesn't have an influencer, this shouldn't happen" % profile)
            return False

        # return if the associated influencer is already in one of the collections
        inf = profile.discovered_influencer
        coll_name = self.group_name_processed_artificial if 'theshelf.com/artificial' in inf.blog_url \
            else self.group_name_processed_non_artificial
        coll = InfluencersGroup.objects.get(name=coll_name)

        if inf.id in coll.influencer_ids:
            log.info('Inf %r already in collection %r' % (inf, coll))
            return True

        # When influencer was freshly created:
        if inf.old_show_on_search is not True and \
                ic_tag in [
                    'IC_artificial_inf_created',  # created new artificial influencer
                    'IC_new_blog_new_inf',  # we did not find non-social blog platform, so created new blog platform and new influencer
                    'IC_one_inf_found',
                ]:

            log.info('Influencer was recently created, fetching its data, creating its social platforms if any...')

            # Running new_influencer processing
            _ = _do_process_new_influencer_sequentially(None, inf, assume_blog=True)
            inf = Influencer.objects.get(id=inf.id)
            # We need to make sure that social_urls_extracted are added to this influencer or at least they
            # exist even after this platform extraction
            # If this influiencer has been just created, then create its discovered social platforms
            # here and pull their posts.
            social_urls = profile.get_social_urls_detected()
            if len(social_urls) > 0:
                # If we found any social urls and this influencer was created - that means these social
                # platforms do not exist, we should create them now and fetch their blogs.
                # for social_url in social_urls:
                plats = _platforms_from_links(
                    source_url=None,
                    influencer=inf,
                    links=social_urls,
                    to_save=True
                )

                # setting their url_show_on_search=False and auto_validated=True, because these are freshly fetched
                for plat in plats:
                    plat.autovalidated = True
                    plat.autovalidated_reason = 'discovered_by_instagramprofile_social_urls'
                    plat.url_not_found = False
                    plat.save()

                # Fetching their stats when creating fetcher
                policy = FetchAllPolicy()
                for plat in plats:
                    try:
                        # skip twitter because it can block
                        if 'twitter.com' in plat.url.lower() or plat.platform_name not in Platform.SOCIAL_PLATFORMS_CRAWLED:
                            continue
                        if plat.validated_handle:
                            # that means we already have processed this, so no need to fetch
                            continue
                        pf = fetcher_for_platform(plat, policy)
                    except:
                        pass
                    # no need to fetch posts because it will take a long time
                    # pf.fetch_posts()

            # Make sure that we run the algorithm to detect emails and names and other variables
            # from the social profiles

            # get_influencers_email_name_location_for_profile(profile_id, to_save=True)
            AutomaticAttributeSelector(inf, to_save=True)

            # 3) Do we need to run denormalization to make sure we have a picture too?
            # fetching profile pic for this updated influencer
            try:
                inf = Influencer.objects.get(id=inf.id)
                inf.set_profile_pic()
                inf.denormalize_fast()
                inf.save()
            except Influencer.DoesNotExist:
                log.error('Influencer with id=%s not found when tried to set profile image.')

        # Depending on artificial url or not we're adding influencer to collection
        inf = Influencer.objects.get(id=inf.id)

        # only add the infuencer to the collection if it's not on the production
        if inf.old_show_on_search is not True:
            coll.add_influencer(inf)

        # These should be upgraded to show_on_search=True (if they are not already)
        if inf.show_on_search is not True:
            inf.set_show_on_search(value=True, on_production=False)

        log.info('Appending LEDU_performed tag')
        profile.append_tag('LEDU_performed')

        return True

    def pipeline(self, profile_id=None, route=None, **kwargs):
        """
        Pipeline method for getting extra data for freshly-created influencer by LightUpgrader and deciding
        if it will go further by pipeline's route.

        """

        log.info('Started %s.pipeline(profile_id=%s, route=%s)' % (type(self).__name__, profile_id, route))

        try:
            # getting profile and just perform its updating
            profile = InstagramProfile.objects.get(id=profile_id)

            if 'LEDU_performed' not in profile.tags:
                self.update_created_influencer(profile)

            # creating a SocialProfileOp object for this event
            SocialProfileOp.objects.create(
                profile_id=profile_id,
                description='LEDU_DATA_FETCH_ISSUED',
                module_classname=type(self).__name__,
                data={}
            )

            # proceeding with pipeline route if result is suitable
            if type(route) is list and len(route) > 1:
                log.info('Proceeding to the next step: %s' % route[1])
                crawler_task.apply_async(
                    kwargs={
                        'klass_name': route[1],
                        'task_type': 'pipeline',
                        'profile_id': profile.id,
                        'route': route[1:],
                    },
                    queue=get_queue_name_by_pipeline_step(route[1])
                )
            else:
                log.info('Route finished or terminating route because of result.')

        except InstagramProfile.DoesNotExist:
            log.error('InstagramProfile with id: %s does not exist, exiting.' % profile_id)
