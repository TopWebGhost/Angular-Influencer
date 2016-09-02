from __future__ import (
    absolute_import, division, print_function, unicode_literals,
)

import logging
import urlparse
from datetime import datetime

from django.db import models
from django_pgjson.fields import JsonField as PGJsonField

from debra import models as debra_models

log = logging.getLogger('social_discovery.models')


class TwitterProfile(models.Model):
    platform = models.ForeignKey(debra_models.Platform, related_name='twitter_profile', null=True)
    discovered_influencer = models.ForeignKey(debra_models.Influencer, related_name='twitter_profile', null=True)
    screen_name = models.TextField(null=False, blank=False, db_index=True, unique=True)
    friends = models.ManyToManyField('TwitterProfile', through='TwitterFollow', related_name='friends+')
    profile_description = models.TextField(null=True, blank=True)
    friends_updated = models.DateTimeField(null=True, blank=True)
    post_count = models.IntegerField(null=True, blank=True)
    friends_count = models.IntegerField(null=True, blank=True)
    followers_count = models.IntegerField(null=True, blank=True)
    last_post_time = models.DateTimeField(null=True, blank=True)
    api_data = PGJsonField(null=True, blank=True)
    valid_influencer = models.NullBooleanField(default=None, db_index=True)
    update_pending = models.BooleanField(default=False, db_index=True)

    def __unicode__(self):
        return 'TwitterProfile(%s)' % self.screen_name


class TwitterFollow(models.Model):
    follower = models.ForeignKey(TwitterProfile, null=False, blank=False, db_index=True, related_name='folowers')
    followed = models.ForeignKey(TwitterProfile, null=False, blank=False, db_index=True, related_name='followed')


class InstagramProfile(models.Model):
    platform = models.ForeignKey(debra_models.Platform, related_name='instagram_profile', null=True)
    discovered_influencer = models.ForeignKey(debra_models.Influencer, related_name='instagram_profile', null=True)
    username = models.TextField(null=False, blank=False, db_index=True, unique=True)
    profile_description = models.TextField(null=True, blank=True)
    friends_updated = models.DateTimeField(null=True, blank=True)
    post_count = models.IntegerField(null=True, blank=True)
    friends_count = models.IntegerField(null=True, blank=True)
    followers_count = models.IntegerField(null=True, blank=True)
    last_post_time = models.DateTimeField(null=True, blank=True)
    api_data = PGJsonField(null=True, blank=True)
    api_data_history = PGJsonField(null=False, blank=True, default=[])
    valid_influencer = models.NullBooleanField(default=None, db_index=True)
    update_pending = models.BooleanField(default=False, db_index=True)
    tags = models.TextField(default=None, null=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True)
    social_urls_detected = models.TextField(default=None, null=True)
    non_social_urls_detected = models.TextField(default=None, null=True)
    date_to_fetch_later = models.DateTimeField(null=True, blank=True)

    # this is a list of ids of platforms that we detect according to content of fields:
    # * social_urls_detected
    # * non_social_urls_detected
    platform_ids_detected = models.TextField(default=None, null=True)

    # How many times we tried to reprocess this profile to classify it other
    # than undecided
    reprocess_tries_count = models.PositiveIntegerField(
        default=0, null=False, blank=False
    )

    def __unicode__(self):
        return 'InstagramProfile(%s)' % self.username

    def get_url(self):
        return 'https://instagram.com/%s' % self.username

    def get_description_from_api(self):
        api = self.api_data
        if not api:
            return
        return api.get('biography') or api.get('bio')

    def _get_data_from_api_history(self, keys=None):
        api_history = self.api_data_history
        description_set = set()
        if not api_history or not keys:
            return description_set
        for api_data in api_history:
            for api_data_value in api_data.values():
                for key in keys:
                    biography = api_data_value.get(key)
                    if biography:
                        description_set.add(biography)
                        break
        return description_set

    def get_description_from_api_history(self):
        bio = self._get_data_from_api_history(keys=('biography', 'bio',))
        return ' '.join(bio)

    def get_url_from_api(self):
        api = self.api_data
        if not api:
            return
        return api.get('external_url') or api.get('website')

    def get_urls_from_api_history(self):
        return self._get_data_from_api_history(
            keys=('external_url', 'website',)
        )

    def combine_description_and_external_url(self):
        """
        Combine api_data['biography'] and api_data['external_url] into one
        """
        description = self.get_description_from_api() or ''
        external_url = self.get_external_url()
        if external_url:
            description += ' ' + external_url
        return description

    def get_nodes_from_api(self):
        api = self.api_data
        if 'media' in api.keys() and api.get('media') and 'nodes' in api['media'].keys():
            nodes = api.get('media').get('nodes', None)
            return nodes
        return None

    def get_commentors(self):
        data = self.profile_description
        if not data:
            return []
        units = data.split()
        commentors = [u[3:].lower() for u in units if u.startswith('!*_')]
        return commentors

    def get_mentions(self):
        data = self.profile_description
        if not data:
            return []
        units = data.split()
        mentions = [u.strip('@').lower() for u in units if u.startswith('@')]
        return mentions

    def get_hashtags(self):
        data = self.profile_description
        if not data:
            return []
        units = data.split()
        hashtags = [u.lower() for u in units if not '@' in u]
        hashtags = [u.lower() for u in hashtags if not '!*_' in u]
        return hashtags

    def append_tag(self, tag):
        if tag is not None:
            tags = self.tags
            if tags:
                if tag not in tags:
                    tags += ' ' + tag
            else:
                tags = tag
            self.tags = tags
        self.save()

    def append_mutual_exclusive_tag(self, tag, exclusive_tags):
        """
        This function is used to append mutual exclusive tags, for example 'brand' tag can not be together with
        'blogger' or 'undecided' tags, so when we place 'brand', we need to ensure that there are no 'blogger'
        or 'unecided' tag.
        :param tag: tag to be set, 'blogger' for example.
        :param exclusive_tags: list of mutually exclusive tags, as ['blogger', 'brand', 'undecided']
        """
        tags = self.tags

        # checking and removing existing tag
        if len(exclusive_tags) > 0 and tags is not None and any([t in tags for t in exclusive_tags if t is not None]):
            tags_list = tags.split()
            # filters out only tags that not in a list of mutual exclusive tags
            self.tags = ' '.join([t for t in tags_list if t not in exclusive_tags])

        self.append_tag(tag)

    def get_posts(self):
        nodes = self.get_nodes_from_api()
        if not nodes:
            return []
        posts = []
        for n in nodes:
            code = n.get('code', None)
            if code:
                posts.append('https://instagram.com/p/'+code)
        return posts

    def get_external_url(self):
        api = self.api_data
        if 'external_url' in api.keys():
            return api.get('external_url', None)
        return None

    def get_all_urls(self):
        from platformdatafetcher.contentfiltering import find_all_urls
        external_url = self.get_external_url()
        api = self.api_data
        urls = []
        if api and 'biography' in api.keys() and api.get('biography'):
            biography = api.get('biography')
            urls = find_all_urls(biography)
            if len(urls) > 0:
                if external_url:
                    urls.append(external_url)
        if external_url:
            urls.append(external_url)
        return urls

    def update_description(self, tag):
        """
        This function was moved here from instagram_crawl.create_pending_profile function
        :param tag: some tag to append to description
        :return:
        """
        if self.profile_description is None and tag:
            self.profile_description = tag
            if self.id is not None:
                self.save()
        if self.profile_description and len(self.profile_description) > 2000:
            # profile description already too long, returning
            return
        if self.profile_description and tag and tag not in self.profile_description.lower():
            self.profile_description += " " + tag
            if self.id is not None:
                self.save()

    def check_if_dead(self, to_save=True):
        """
        This function marks a profile as DEAD if url raises an exception
        :param to_save: whether to save or not
        :return:
        """
        from xpathscraper.utils import can_get_url
        url = 'http://instagram.com/' + self.username
        res = can_get_url(url)
        if not res:
            print("%s is dead" % url)
            if to_save:
                self.append_tag('DEAD')
            return True
        return False

    def get_social_urls_detected(self):
        if self.social_urls_detected is None:
            return []
        else:
            return self.social_urls_detected.split(' ')

    def set_social_urls_detected(self, urls_list=None):
        try:
            self.social_urls_detected = None if not urls_list else u' '.join(
                urls_list
            )
            self.save()
        except TypeError:
            pass

    def get_non_social_urls_detected(self):
        if self.non_social_urls_detected is None:
            return []
        else:
            return self.non_social_urls_detected.split(' ')

    def set_non_social_urls_detected(self, urls_list=None):
        """
        We go through the urls and skip the ones with blacklisted domains and
        then save the remaining ones.
        P.S.: considering liketoknow.it urls as good because we can retrieve
        blog urls from them.
        """
        from . import blog_discovery

        if not urls_list:
            self.non_social_urls_detected = None
            self.save()
            return

        if type(urls_list) is list and len(urls_list) > 0:
            new_list = []
            for url in urls_list:
                if blog_discovery.skip_network_links(
                    url, declare_good=['liketoknow.it', ]
                ):
                    continue
                new_list.append(url)
            if len(new_list) > 0:
                self.non_social_urls_detected = u' '.join(new_list)
                self.save()

    def get_platform_ids_detected(self):
        if self.platform_ids_detected is None:
            return []
        else:
            return [int(pid) for pid in self.platform_ids_detected.split(' ') if pid.isdigit()]

    def set_platform_ids_detected(self, platform_ids_list=None):
        if type(platform_ids_list) is list and len(platform_ids_list) > 0:
            self.platform_ids_detected = u' '.join([str(pid) for pid in platform_ids_list])
            self.save()
        elif platform_ids_list is None or (type(platform_ids_list) is list and len(platform_ids_list) == 0):
            self.platform_ids_detected = None
            self.save()

    def find_existing_platform_ids(self):
        """
        Searches for existing platforms in DB according to platform_names and usernames for social_urls_detected
        """

        from platformdatafetcher.platformutils import social_platform_name_from_url, username_from_platform_url
        from . import blog_discovery
        import requests

        log.info('Detecting social platforms for Profile %s' % self.id)

        social_urls = self.get_social_urls_detected()
        non_social_urls = self.get_non_social_urls_detected()

        detected_platform_ids = []

        log.info('Detecting social platforms according to %s social urls...' % len(social_urls))
        for url in social_urls:
            log.info('Searching for platform with url: %s' % url)
            username = username_from_platform_url(url)
            log.info('Username: %s' % username)
            if not username:
                log.info("Skipping url %r because username is None" % url)
                continue
            platform_name = social_platform_name_from_url(None, url)
            log.info('Platform_name: %s' % platform_name)

            plats_ids = debra_models.Platform.objects.filter(username=username, influencer__show_on_search=True,
                                                             platform_name=platform_name).values_list('id', flat=True)

            if plats_ids.count() > 0:
                log.info('For %r Found %s existing platforms, ids: %s' % (url, len(plats_ids), plats_ids))
                for p in plats_ids:
                    if p not in detected_platform_ids:
                        detected_platform_ids.append(p)

        log.info('Detecting non-social platforms according to %s non-social urls...' % len(non_social_urls))
        if non_social_urls and len(non_social_urls) > 0:
            found_domains = set()
            for url in non_social_urls:
                log.info('Searching for non-social url: %s' % url)

                # TODO: currently we search only for blogspot and wordpress non-social urls. We can search for any (contains=domain), but it will take a lot of time
                try:
                    # if url is one of the blacklisted, we skip it
                    if blog_discovery.skip_network_links(url):
                        log.info('Skipping %r because it"s blacklisted' % url)
                        continue
                    # now check if the url is not reachable, this should cause an exception if the url is invalid or
                    # unreachable
                    _ = requests.get(url, verify=False)
                    domain = urlparse.urlparse(url).netloc.lower()
                    found_domains.add(domain)

                    # now add non-www based domain also
                    if 'www.' in domain:
                        found_domains.add(domain.strip('www.'))
                    if not 'www.' in domain:
                        found_domains.add('www.'+ domain)
                except Exception as e:
                    log.exception(e)
            log.info("Found domains: %r" % found_domains)
            for domain in found_domains:
                # checking if it is a wordpress or blogspot
                # if '.wordpress.' in domain or '.blogspot.' in domain:
                log.info("CHECKING Domain: %r" % domain)
                # Step 1: getting candidates
                plats_data = debra_models.Platform.objects.exclude(
                    platform_name__in=debra_models.Platform.SOCIAL_PLATFORMS
                ).filter(
                    url__contains=domain, influencer__show_on_search=True
                ).values('id', 'url')

                log.info(plats_data)

                if plats_data.count() > 0:
                    log.info('For domain %r Found %s CANDIDATE platforms' % (domain, len(plats_data)))
                    # Step 2: checking domain
                    for pdata in plats_data:
                        purl = pdata['url']
                        pid = pdata['id']
                        log.info("PID: [%r] Purl: [%r]" % (pid, purl))
                        try:
                            candidate_domain = urlparse.urlparse(purl).netloc.lower()
                            log.info("Candidate_domain: [%r] Domain: [%r]" % (candidate_domain, domain))
                            if candidate_domain == domain and pid not in detected_platform_ids:
                                detected_platform_ids.append(pid)
                        except AttributeError:
                            pass

        # now make sure to only check for non-duplicate ids
        unique_detected_platform_ids = detected_platform_ids
        if len(detected_platform_ids) > 0:
            unique_detected_platform_ids = list(set(detected_platform_ids))
            self.set_platform_ids_detected(unique_detected_platform_ids)
            log.info('Saved %s existing platform ids to Profile %s: %s' % (len(unique_detected_platform_ids),
                                                                           self.id,
                                                                           unique_detected_platform_ids))
        else:
            log.info('No existing platforms detected, no platform ids saved to Profile %s' % self.id)

        return unique_detected_platform_ids

    def update_from_web_data(self, web_data):
        """
        Update corresponding profile fields with data obtained using web
        crawler
        :param web_data: result of instagram_crawl.scrape_profile_details()
        :type details: dict
        :return: None
        """
        self.update_pending = False

        if web_data:
            if 'following' in web_data:
                self.friends_count = web_data['following']
            if 'followers' in web_data:
                self.followers_count = web_data['followers']
            if 'posts' in web_data:
                self.post_count = web_data['posts']
            if 'last_post_time' in web_data:
                self.last_post_time = web_data['last_post_time']
            if 'api_data' in web_data:
                self.api_data = web_data['api_data']
                self.api_data_history.append({
                    datetime.now().strftime('%Y-%m-%d'): self.api_data,
                })
        else:
            log.info('No blogs discovered for profile %s', self)
            self.valid_influencer = False

        self.save()


class SocialProfileOp(models.Model):
    """
    Model for logging actions and statistics of InstagramProfile models
    """
    profile = models.ForeignKey(InstagramProfile, null=False)
    date_created = models.DateTimeField(auto_now_add=True, null=True)

    # event description
    description = models.TextField(null=True, blank=True)

    # classname of the module
    module_classname = models.CharField(max_length=256, blank=True, null=True, default=None)

    # dates of event start/finish
    date_started = models.DateTimeField(null=True)
    date_finished = models.DateTimeField(null=True)

    # flag field if this operation finished with error
    has_error = models.BooleanField(default=False)

    # field has json-formed content with additional data (exception messages, results, time, etc)
    data = PGJsonField(null=True, blank=True)

    def __unicode__(self):
        return 'SocialProfileOp id=%s profile_id=%s description=%s date_created=%s module_classname=%s' % (
            self.id,
            self.profile_id if self.profile is not None else None,
            self.description,
            self.date_created,
            self.module_classname
        )


class PlatformLatestPostProcessed(models.Model):
    """
    For each brand platform we store the latest post processed to start
    new influencers search each time from the post we finished at
    """
    platform = models.ForeignKey(
        debra_models.Platform, null=False, blank=False, unique=True,
        db_index=True, related_name='latest_post'
    )
    # 0 means no posts were processed for this platform
    latest_post_id_processed = models.IntegerField(
        null=False, blank=False, default=0
    )
