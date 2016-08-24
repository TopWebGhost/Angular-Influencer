__author__ = 'atulsingh'

#This class ensures that for a
# a) given blog url, we only have one influencer and one corresponding platform
# b) given facebook user, we have only one platform (finds and remove duplicates)
# c) same for other platforms

from collections import defaultdict
import pprint

import baker

from debra.models import Influencer, Platform, Posts, PostInteractions, UserProfile
from xpathscraper import utils
from platformdatafetcher.fetcher import try_detect_platform_name
from platformdatafetcher import platformextractor


class InfluencerObject(object):
    def __init__(self, blog_url):
        self.platform_name = None
        self.blog_url = blog_url
        self.make_blog_url_correct()
        self.inf = self.get_or_create_inf()
        self.blog_platform = self.get_or_create_blog_platform()

    def make_blog_url_correct(self):
        # check with the Wordpress and Blogger API's to see if some variation
        # of the blog url exists
        # if yes, use that. else, keep it unchanged
        platform_name, corrected_url = try_detect_platform_name(self.blog_url)
        if platform_name:
            self.blog_url = corrected_url
            self.platform_name = platform_name

    def get_or_create_inf(self):
        # there can be only one Influencer per blog url
        inf = UserProfile.get_influencers(self.blog_url)
        if inf and len(inf) == 1:
            return inf[0]
        elif inf and len(inf) > 1:
            inf = InfluencerObject.remove_duplicate_influencers(inf)
            return inf
        else:
            inf = Influencer.objects.create(blog_url=self.blog_url)
            return inf

    @staticmethod
    def remove_duplicate_influencers(infs):
        assert len(infs) > 1
        print "Removing duplicate influencers for %s" % infs[0].blog_url
        to_keep = infs[0]
        for i in infs[1:]:
            i.delete()
        return to_keep

    @staticmethod
    def remove_duplicate_platforms(plats):
        assert len(plats) > 1
        print "Removing duplicate platforms for %s" % plats[0].url
        to_keep = plats[0]
        for i in plats[1:]:
            posts = Posts.objects.filter(platform=i)
            post_interactions = PostInteractions.objects.filter(post__platform=i)
            post_interactions.delete()
            posts.delete()
            i.delete()
        return to_keep

    def get_or_create_blog_platform(self):
        platforms = Platform.objects.filter(url=self.blog_url)
        if len(platforms) == 1:
            platform = platforms[0]
        elif len(platforms) > 1:
            platform = InfluencerObject.remove_duplicate_platforms(platforms)
        else:
            platform = Platform.objects.create(influencer=self.inf, url=self.blog_url)

        platform.influencer = self.inf
        if self.platform_name:
            platform.platform_name = self.platform_name
        platform.save()
        return platform

    @staticmethod
    def set_user_obj(influencer):
        """
        For the influencer, sets the corresponding shelf_user
            - find the UserProfile that has the matching blog_page as influencer.blog_url
        """
        if not influencer.blog_url:
            return False
        blog_url = influencer.blog_url.strip('http://').strip('www.').rstrip('/')
        prof = UserProfile.objects.filter(blog_page__icontains=blog_url)
        if prof.exists():
            print "Influencer %s has a user %s blog %s" % (influencer.blog_url, prof, prof[0].blog_page)
            influencer.shelf_user = prof[0].user
            influencer.save()
            return True
        return False

def get_influencer(blog_url):
    inf_obj = InfluencerObject(blog_url)
    return inf_obj.inf

def get_blog_platform(blog_url):
    inf_obj = InfluencerObject(blog_url)
    return inf_obj.blog_platform

#def set_platforms_for_shelf_users():

def _create_by_username_platform():
    pls = Platform.objects.filter(platform_name__in=Platform.SOCIAL_PLATFORMS, url__isnull=False)
    ds = list(pls.values('id', 'url', 'platform_name'))
    by_username_platform = defaultdict(list)
    for i, d in enumerate(ds):
        username = platformextractor.username_from_platform_url(d['url'])
        if not username:
            username = ''
        by_username_platform[(username, d['platform_name'])].append(d)
    return by_username_platform

@baker.command
def print_social_platform_duplicates():
    by_username_platform = _create_by_username_platform()
    duplicates = [(k, v) for k, v in by_username_platform.iteritems() if len(v) > 1]
    duplicates.sort(key=lambda (k, v): len(v), reverse=True)
    for (username, platform), dups in duplicates:
        print 'USERNAME <%s> PLATFORM <%s>' % (username, platform)
        pprint.pprint(dups)
        print

@baker.command
def delete_social_platform_duplicates(remaining_platform_id, delete_remaining_also='0'):
    pl = Platform.objects.get(id=remaining_platform_id)
    username = platformextractor.username_from_platform_url(pl.url)
    print 'Will find duplicates for USERNAME <%s>' % username
    by_username_platform = _create_by_username_platform()
    dup_ids = [d['id'] for d in by_username_platform[(username, pl.platform_name)] \
               if d['id'] != pl.id]
    print 'Deleting %s dups: %s' % (len(dup_ids), dup_ids)
    dup_pls = Platform.objects.filter(id__in=dup_ids)
    print 'Deleting and migrating these platforms: %r' % dup_pls
    pl.delete_and_migrate_dups(dup_pls)

    if int(delete_remaining_also):
        print 'Deleting remaining platform %r' % pl
        pl.delete()

def _create_by_url_for_blogs():
    pls = Platform.objects.filter(platform_name__in=Platform.BLOG_PLATFORMS, url__isnull=False)
    ds = list(pls.values('id', 'url', 'platform_name'))
    by_url = defaultdict(list)
    for d in ds:
        canonical_url = utils.strip_url_of_default_info(d['url'], strip_domain=False)
        by_url[canonical_url].append(d)
    return by_url

@baker.command
def print_blog_platform_duplicates():
    by_url = _create_by_url_for_blogs()
    duplicates = [(k, v) for k, v in by_url.iteritems() if len(v) > 1]
    duplicates.sort(key=lambda (k, v): len(v), reverse=True)
    for url, dups in duplicates:
        print 'URL <%s>' % (url)
        pprint.pprint(dups)
        print

def _create_influencer_by_blog_url():
    infs = Influencer.objects.filter(blog_url__isnull=False)
    ds = list(infs.values('id', 'blog_url', 'name'))
    by_url = defaultdict(list)
    for d in ds:
        canonical_url = utils.strip_url_of_default_info(d['blog_url'], strip_domain=False)
        by_url[canonical_url].append(d)
    return by_url

def _create_influencer_by_name():
    infs = Influencer.objects.filter(blog_url__isnull=False)
    ds = list(infs.values('id', 'blog_url', 'name'))
    by_name = defaultdict(list)
    for d in ds:
        canonical_name = d['name'].strip().lower()
        by_name[canonical_name].append(d)
    return by_name

@baker.command
def print_influencer_by_blog_url_duplicates():
    by_blog_url = _create_influencer_by_blog_url()
    duplicates = [(k, v) for k, v in by_blog_url.iteritems() if len(v) > 1]
    duplicates.sort(key=lambda (k, v): len(v), reverse=True)
    for url, dups in duplicates:
        print 'BLOG_URL <%s>' % (url)
        pprint.pprint(dups)
        print

@baker.command
def print_influencer_by_name_duplicates():
    by_name = _create_influencer_by_name()
    duplicates = [(k, v) for k, v in by_name.iteritems() if len(v) > 1]
    duplicates.sort(key=lambda (k, v): len(v), reverse=True)
    for name, dups in duplicates:
        print 'NAME <%s>' % name
        pprint.pprint(dups)
        print

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()

