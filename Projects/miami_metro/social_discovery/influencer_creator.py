from debra.models import Platform, InfluencersGroup, Influencer

from urlparse import urlparse
import logging

from debra.helpers import create_influencer_and_blog_platform

import requests
from platformdatafetcher.platformextractor import collect_any_social_urls
from xpathscraper import xbrowser as xbrowsermod
from xpathscraper.utils import browser_headers
from platformdatafetcher.contentclassification import Classifier

import time
from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings

log = logging.getLogger('social_discovery.influencer_creator')


class InfluencerCreator(object):
    """
    This class performs operations to find influencer / create new one for this profile according to diagram.
    """

    # mutual-exclusive tags of the result
    TAGS = [
        'IC_one_inf_found',       # one platform is found, its influencer taken and connected to
                                  # profile, it is not artificial
        'IC_many_plats_found',    # many platforms found, not easy to detect influencer
        'IC_one_artificial_inf_found',  # we found existing influencer and it is artificial, we connected it
        'IC_many_nonsocial_found',  # found > 1 non-social urls
        'IC_nothing_found',  # non-social urls found, not found a blog

        'IC_artificial_inf_created',  # created new artificial influencer
        'IC_new_blog_new_inf',  # we did not find non-social blog platform, so created new blog platform
                                # and new influencer

        'IC_one_from_several',   # among several influencers we found one which is not blacklisted
                                 # and old_show_on_search=True
        'IC_dups_from_several',   # among several influencers we found some which are not blacklisted
                                  # and old_show_on_search=True
        'IC_best_from_several',  # we did not find old_show_on_search=True, so we picked teh best to stay

        'IC_possible_brand',  # possible a brand
    ]

    obsolete_tags = [
        'IC_not_found_nonsocial',  # obsolete tag, will be removed if encountered
        'IC_new_blog_new_inf_liketoknowit',  # No non-social blog platform, created new blog platform and
                                             # new influencer with liketoknow.it blog platform
    ]

    def __init__(self, profile=None, save=False):
        """

        :param profile: -- given InstagramProfile
        :return:
        """
        if profile is not None:
            self.profile = profile

        self.report_data = dict()
        self.url_classifier = Classifier()
        self.save = save  # if true, all changes are permanent

    def detect_influencer(self):
        """
        Detects influencer according to the diagram

        :return: Influencer Id
        """
        self.report_data = dict()

        # checking if this profile has been performed before (if it has any IC_* actual tags)
        tags = self.profile.tags.split()
        if any(t in self.TAGS for t in tags):
            # looks like this profile was already performed, skipping it
            return 'already_preformed'

        # removing existing discovered_influencer if any presents
        present_influencer = self.profile.discovered_influencer
        if present_influencer is not None:
            self.profile.discovered_influencer = None
            if self.save is True:
                self.profile.save()

        # Getting profile's discovered platform ids
        existing_platform_ids = self.profile.get_platform_ids_detected()
        non_social_urls = self.profile.get_non_social_urls_detected()

        log.info('Detecting influencer for InstagramProfile %s ...' % self.profile.id)

        self.report_data['profile_id'] = self.profile.id
        self.report_data['existing_platform_ids_qty'] = len(existing_platform_ids)
        self.report_data['non_social_urls_qty'] = len(non_social_urls)

        if len(existing_platform_ids) >= 1:
            log.info('Found %s platform ids' % len(existing_platform_ids))
            # There are at least 1 discovered existing platform for this Profile
            # fetching all platforms except those with url_not_found=True
            # UPDATE: and then detecting influencers of these platforms. If there is only one influencer - using it

            active_plats = Platform.objects.filter(id__in=existing_platform_ids).exclude(url_not_found=True)
            active_influencers_ids = set()
            for p in active_plats:
                if p.influencer is not None:
                    active_influencers_ids.add(p.influencer.id)

            active_influencers_ids = list(active_influencers_ids)

            self.report_data['active_influencers_ids'] = active_influencers_ids

            log.info('Found %s existing platforms with %s distinctive influencers' % (
                len(existing_platform_ids),
                len(active_influencers_ids)
            ))

            if len(active_influencers_ids) == 1:
                # Great! Only platforms with one distinctive influencers found, working with it: adding this
                # influencer to collection, connecting it to InstagramProfile

                log.info('Found 1 influencer (%s), setting IC_one_inf_found tag, setting '
                         'influencer to InstagramProfile' % active_influencers_ids[0])

                candidate_influencer = Influencer.objects.get(id=active_influencers_ids[0])

                if candidate_influencer.blog_url is not None and candidate_influencer.blog_url.startswith(
                        'http://www.theshelf.com/artificial_blog/'
                ):
                    inf = Influencer.objects.get(id=active_influencers_ids[0])

                    # TODO: connecting existing artificial influencer?
                    self.profile.discovered_influencer = candidate_influencer
                    if self.save is True:
                        self.profile.save()

                        self.add_influencer_to_discovered_collection(candidate_influencer)

                        self.profile.append_mutual_exclusive_tag('IC_one_artificial_inf_found',
                                                                 self.TAGS + self.obsolete_tags)

                    self.report_data['result'] = 'One existing influencer found (artificial/osos): %s (osos: %s / sos: %s)' % (
                        active_influencers_ids[0],
                        inf.old_show_on_search,
                        inf.show_on_search,
                    )
                    return 'IC_one_artificial_inf_found'
                else:
                    self.profile.discovered_influencer = candidate_influencer
                    if self.save is True:
                        self.profile.save()

                        self.add_influencer_to_discovered_collection(candidate_influencer)

                        self.profile.append_mutual_exclusive_tag('IC_one_inf_found', self.TAGS + self.obsolete_tags)

                    self.report_data['result'] = 'One existing influencer found and set to ' \
                                                 'profile (non-artificial, non-osos): %s (osos: %s / sos: %s)' % (
                        active_influencers_ids[0],
                        candidate_influencer.old_show_on_search,
                        candidate_influencer.show_on_search,
                    )
                    return 'IC_one_inf_found'

            elif len(active_influencers_ids) > 1:
                # We discovered more than one active platforms with more than one distinctive influencers.

                log.info('Found more than 1 platform with more than 1 distinctive '
                         'Influencers, setting tag IC_many_plats_found')

                # self.profile.append_mutual_exclusive_tag('IC_many_infs_found', self.TAGS)

                infs = Influencer.objects.filter(id__in=active_influencers_ids,
                                                 old_show_on_search=True).exclude(blacklisted=True)

                if infs.count() == 0:
                    # None found, we pick the best _select_influencer_to_stay(),
                    # connect to the profile and add to the collection

                    active_infs = Influencer.objects.filter(id__in=active_influencers_ids)
                    best_one = active_infs[0]._select_influencer_to_stay(list(active_infs))

                    self.profile.discovered_influencer = best_one
                    if self.save is True:
                        self.profile.save()
                        # self.add_influencer_to_discovered_collection(best_one)
                        self.profile.append_mutual_exclusive_tag('IC_best_from_several', self.TAGS + self.obsolete_tags)

                    several_infs = [
                        "%s  (osos: %s / sos: %s)" % (inf.id,
                                                      inf.old_show_on_search,
                                                      inf.show_on_search) for inf in active_infs
                    ]
                    self.report_data['result'] = 'Several existing influencers found (no osos=True): %s , ' \
                                                 'taken best of them: %s  (osos: %s / sos: %s)' % (
                        several_infs,
                        best_one.id,
                        best_one.old_show_on_search,
                        best_one.show_on_search
                    )

                    return 'IC_best_from_several'

                elif infs.count() == 1:
                    # One Influencer with old_show_on_search=True found, using it
                    candidate_influencer = infs[0]
                    self.profile.discovered_influencer = candidate_influencer
                    if self.save is True:
                        self.profile.save()
                        # self.add_influencer_to_discovered_collection(candidate_influencer)
                        self.profile.append_mutual_exclusive_tag('IC_one_from_several', self.TAGS + self.obsolete_tags)

                    several_infs =[
                        "%s  (osos: %s / sos: %s)" % (inf.id,
                                                      inf.old_show_on_search,
                                                      inf.show_on_search) for inf in infs
                    ]
                    self.report_data['result'] = 'Several existing influencers found: %s , taken ' \
                                                 'one of them with osos=True: %s  (osos: %s / sos: %s)' % (
                        several_infs,
                        candidate_influencer.id,
                        candidate_influencer.old_show_on_search,
                        candidate_influencer.show_on_search,
                    )

                    return 'IC_one_from_several'

                else:
                    # Multiple found - adding these to collection of duplicates
                    if self.save is True:
                        self.add_influencers_to_duplicates_collection(influencers=infs)

                        self.profile.append_mutual_exclusive_tag('IC_many_infs_found', self.TAGS + self.obsolete_tags)

                    self.report_data['result'] = 'Several existing influencers found: %s, taken those with osos=True ' \
                                                 'and putting them to duplicates collection.' % [
                        "%s  (osos: %s / sos: %s)" % (inf.id,
                                                      inf.old_show_on_search,
                                                      inf.show_on_search) for inf in infs
                    ]

                return 'IC_many_infs_found'

        # There are 0 discovered platforms, checking with non-social urls
        if len(non_social_urls) == 0:
            # Creating influencer with artificial url, adding it to collection, connecting it to the profile

            log.info('No non-social urls found, creating artificial Influencer and adding it to the profile')

            count_str = '%s' % (int(time.time()))
            blog_url = 'http://www.theshelf.com/artificial_blog/%s.html' % count_str
            inf = create_influencer_and_blog_platform(blog_url,
                                                      influencer_source='discovered_via_instagram',
                                                      to_save=True,
                                                      platform_name_fallback=True)

            self.profile.discovered_influencer = inf
            if self.save is True:
                self.profile.save()
                # TODO: Should we create here an instagram platform too?
                self.add_influencer_to_discovered_collection(inf)
                self.profile.append_mutual_exclusive_tag('IC_artificial_inf_created', self.TAGS + self.obsolete_tags)

            log.info('Adding IC_artificial_inf_created tag')

            self.report_data['result'] = 'No social/non-social platforms found - creating ' \
                                         'artificial Influencer: %s (osos: %s / sos: %s).' % (inf.id,
                                                                                              inf.old_show_on_search,
                                                                                              inf.show_on_search)

            return 'IC_artificial_inf_created'

        else:
            # There are some non-social urls -- checking if there are unique non-social urls

            # Special shortcut: if non-social urls contain liketoknow.it url. If this url is found, then using it as a
            # blog url for this future influencer

            from platformdatafetcher.producturlsextractor import get_blog_url_from_liketoknowit

            # NEW logic to check for bloggy urls
            log.info('%s non-social urls found: %s, trying to find unique root domains' % (
                len(non_social_urls), non_social_urls
            ))

            blog_urls_found = []

            from platformdatafetcher.platformextractor import collect_social_urls_from_blog_url, \
                substitute_instagram_post_urls

            # detecting if any of non-social urls are blogs
            with xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                                      load_no_images=True, disable_cleanup=False, timeout=60) as xb:

                # social urls chunks, we need to prepare social urls into detectable chunks like 'www-less domain/path'
                social_chunks = []
                for url in self.profile.get_social_urls_detected():
                    parsed = urlparse(url)
                    chunk = '%s%s' % (
                        parsed.netloc[4:] if parsed.netloc.startswith('www.') else parsed.netloc, parsed.path
                    )
                    chunk = chunk.strip('/')
                    if chunk not in social_chunks:
                        social_chunks.append(chunk)

                log.info('Social url fragments for searching: %s' % social_chunks)

                # detecting if any found socials in there
                non_social_urls = self.profile.get_non_social_urls_detected()
                unique_root_domains = self.get_unique_root_domains(non_social_urls)
                for k in unique_root_domains.keys():
                    non_social_url_start = unique_root_domains[k][0]

                    # checking if this url is a good liketoknow.it url and blog url can be retrieved:
                    parsed = urlparse(non_social_url_start)
                    # checking if domain is liketoknow.it
                    if parsed.netloc.lower().strip().replace('www.', '', 1) == 'liketoknow.it' and \
                            parsed.path.lower().strip('/').strip() not in ['', 'login']:

                        log.info('Liketoknow.it url detected: %r , trying to get its blog url' % non_social_url_start)

                        # looks like it is a good liketoknow.it url, getting blog url
                        blog_url = get_blog_url_from_liketoknowit(non_social_url_start, xb)
                        if blog_url is not None:
                            log.info('Blog url detected successfully: %r , considering it a good blog url' % blog_url)
                            # adding it to blog_urls detected
                            if blog_url not in blog_urls_found:
                                blog_urls_found.append(blog_url)
                            else:
                                log.info('Blog url %r is already detected' % blog_url)
                        else:
                            log.info('Blog url was not detected')

                    else:
                        is_blog_url, non_social_url = self.is_url_a_blog(non_social_url_start, self.profile)
                        log.info('Checking if %r is a blog:' % non_social_url)
                        if is_blog_url is True and non_social_url is not None:
                            log.info('Perfect, %r is a blog' % non_social_url)
                            socials_detected = []
                            found_soc_urls = defaultdict(list)
                            collect_social_urls_from_blog_url(xb=xb,
                                                              by_pname=found_soc_urls,
                                                              platform=None,
                                                              non_social_url=non_social_url)

                            substitute_instagram_post_urls(found_soc_urls)

                            log.info('SOCIAL URLS COLLECTED: %s' % found_soc_urls)

                            # if no social urls were collected, we're checking if this non-social url has
                            # social urls in any form with regexps by its content and iframes.
                            if len(found_soc_urls) == 0:
                                scraped_social_urls = collect_any_social_urls(
                                    xb=xb,
                                    non_social_url=non_social_url
                                )
                                log.info('Thorough search found %s candidate social urls '
                                         'to check' % len(scraped_social_urls))
                                found_soc_urls['Bruteforce'] = scraped_social_urls

                            # found_socials is in format {'Instagram': ['url1', 'url2',...], 'Facebook': [...], ...}
                            for social_url_lst in found_soc_urls.values():
                                for social_url in social_url_lst:
                                    if any([sc.lower() in social_url.lower() for sc in social_chunks]):
                                        # we found one of social chunks in detected social url
                                        if social_url not in socials_detected:
                                            socials_detected.append(social_url)

                            log.info('Positively matched social urls: %s' % socials_detected)

                            # if we found some matching social urls - then it is a blog url, TA-DAAAA!
                            if len(socials_detected) > 0:
                                if non_social_url not in blog_urls_found:
                                    # TODO: should we use here self.is_url_a_blog(url, self.profile) for extra blog check?
                                    blog_urls_found.append(non_social_url)
                                    log.info('Considering url %r to be a blog url for this profile' % non_social_url)

                        else:
                            log.info('Url %r considered as non-blog url or is unreachable' % non_social_url_start)

            if len(blog_urls_found) == 1:
                # we found 1 blog url
                log.info('Looks like it is a new single blog url!')
                self.report_data['unique_root_domain_is_blog'] = True

                # Here we have found 0 existing platforms, but we detected that a single non-social url
                # is a BLOG. So we create a blog platform with this url, creating an influencer, connecting
                # this blog platform to this influencer and connecting the influencer to the profile.

                # creating new blog platform
                inf = create_influencer_and_blog_platform(blog_url=blog_urls_found[0],
                                                          influencer_source='ic_from_insta_profile',
                                                          to_save=self.save,
                                                          platform_name_fallback=True)
                self.profile.discovered_influencer = inf
                log.info('A new influencer has been created: %s' % inf)
                if self.save is True:
                    self.profile.save()
                    self.add_influencer_to_discovered_collection(inf)
                    self.profile.append_mutual_exclusive_tag('IC_new_blog_new_inf', self.TAGS + self.obsolete_tags)

                self.report_data['result'] = 'New influencer %s (osos: %s / sos: %s) created by single ' \
                                             'non-social blog platform' % (inf.id,
                                                                           inf.old_show_on_search,
                                                                           inf.show_on_search)

                return 'IC_new_blog_new_inf'

            elif len(blog_urls_found) == 0:
                # if none found to be a blog
                #   => check if the length of the url > 20 chars (typically identifies as a
                #           product) => then this profile needs to be fetched again later
                #     => create a new field "date_to_fetch_later" in InstagramProfile and update this field
                #           with today+10 days later
                #     => need to create a celery task that checks if today is the day when they should be
                #           re-fetched and then clears up this date_to_fetch_later to None
                #     => after fetching the profile, compare the old url and description with new one, check
                #           if it's different, then pass it to the same pipeline as it was originally part of

                log.info('No blog urls were detected within non_social_urls')

                # TODO: what should we do if this already has date_to_fetch_later != None ?
                long_url = False
                for non_social_url in non_social_urls:
                    if len(non_social_url) > 20:
                        self.profile.date_to_fetch_later = datetime.now() + timedelta(days=10)
                        if self.save is True:
                            self.profile.save()
                        long_url = True
                        break

                if long_url is True:

                    self.report_data['result'] = 'No blog urls were found, retrying in 10 days'
                    return '10_days_later'
                else:
                    # TODO: What should we do here, should we create an artificial url?

                    if self.save is True:
                        self.profile.append_mutual_exclusive_tag('IC_possible_brand', self.TAGS + self.obsolete_tags)

                    self.report_data['result'] = 'Profile considered to be possibly a brand.'
                    return 'IC_possible_brand'

            else:
                # TODO: Skipping for now...

                log.info('We found many non-social blog domains, setting IC_many_nonsocial_found tag:' % blog_urls_found)

                if self.save is True:
                    self.profile.append_mutual_exclusive_tag('IC_many_nonsocial_found', self.TAGS + self.obsolete_tags)

                self.report_data['result'] = 'Multiple unique root domains found, skipped for now'
                return 'IC_many_nonsocial_found'



    def add_influencer_to_discovered_collection(self, influencer=None):
        """
        Adds discovered influencer to the appropriate collection
        :param influencer:
        :return:
        """
        if influencer is not None and influencer.old_show_on_search is not True:
            coll = InfluencersGroup.objects.filter(name='discovered_from_instagram')
            if len(coll) > 0:
                coll = coll[0]
                coll.add_influencer(influencer)

    def add_influencers_to_duplicates_collection(self, influencers=None):
        """
        Adds discovered influencer to the appropriate collection
        :param influencer:
        :return:
        """
        if influencers is not None:
            coll = InfluencersGroup.objects.filter(name='duplicates_from_instagram')
            if len(coll) > 0:
                coll = coll[0]
                for inf in influencers:
                    if inf.old_show_on_search is not True:
                        coll.add_influencer(inf)

    def get_unique_root_domains(self, urls):
        """
        counts unique root domains of provided urls
        :param urls:
        :return:
        """
        log.info('Counting unique root domains for urls %s' % urls)
        if type(urls) == list:

            urls_by_domains = dict()

            for u in urls:

                # looks like this url is OK
                url_parsed = urlparse(u)
                dmn = url_parsed.netloc

                # normalizing domain for blogspot
                if 'blogspot.com' in dmn:
                    dmn = '%s.blogspot.com' % dmn.split('.blogspot.com')[0]

                if dmn.endswith('.blogspot.com') or dmn.endswith('.wordpress.com'):
                    # If we found some blogspot or wordpress url at this moment - considering it best hit
                    u = url_parsed._replace(netloc=dmn).geturl()

                if dmn in urls_by_domains:
                    urls_by_domains[dmn].append(u)
                else:
                    urls_by_domains[dmn] = [u, ]

            return urls_by_domains  # list(unique_domains)
        else:
            return {}

    def is_url_a_blog(self, url=None, profile=None):
        """
        Checks if url is a blog
        :param url:
        :return:
        """
        log.info('Checking if url is blog: %s' % url)

        # checking if these urls are real and working
        try:
            resp = requests.get(url=url, headers=browser_headers(), timeout=15, verify=False)

            if resp.status_code < 400:
                # looks like this url is OK
                url_parsed = urlparse(resp.url)
                dmn = url_parsed.netloc

                if dmn.lower().endswith('.livejournal.com'):
                    # looks like we found a LiveJournal blog
                    return True, resp.url

                # normalizing domain for blogspot
                if 'blogspot.com' in dmn:
                    dmn = '%s.blogspot.com' % dmn.split('.blogspot.com')[0]

                if dmn.endswith('.blogspot.com') or dmn.endswith('.wordpress.com'):
                    # If we found some blogspot or wordpress url at this moment - considering it best hit
                    return True, url_parsed._replace(netloc=dmn).geturl()

                if '<!-- This is Squarespace. -->' in resp.content:
                    # looks like we found a Squarespace blog
                    return True, resp.url

                # checking if 'blog' is in root domain (2nd level domain)
                root_domain = dmn.split('.')[-2] if len(dmn.split('.')) >= 2 else None
                if root_domain is not None and 'blog' in root_domain:
                    # high chances that this is a blog
                    return True, resp.url

                if profile is not None:

                    # if liketoknow hashtag appears in the profile's description, then it's a blogger for sure
                    desc = profile.get_description_from_api()
                    if '#liketoknow' in desc.lower():
                        return True, resp.url

                    classification = self.url_classifier.classify(url=resp.url)
                    if classification == 'blog':
                        # looks like our Classifier defined it as blog
                        return True, resp.url

                # TODO: Unreliable? May be use here some regexp */*blog*/* in the path (not for now)?
                # if 'blog' in dmn or '/blog/' in url_parsed.path:
                #     # Looks like it is some blog?
                #     best_result = url_parsed.geturl()
                #     result.add(dmn)
                #     break

                return None, None

            else:
                # removing urls going to domain not found
                log.info('url %s returned %s code, skipping it' % (url, resp.status_code))
                return None, None

        except Exception as e:
            log.exception(e)
            return None, None

    def get_report_data(self):
        """
        returns dict with report data
        :return:
        """
        return self.report_data
