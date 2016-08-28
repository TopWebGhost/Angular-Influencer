from platformdatafetcher.emailextractor import extract_emails_from_text

__author__ = 'atulsingh'

import logging
from debra.models import Influencer
from debra.constants import *
from django.db.models import Q
from debra import admin_helpers

log = logging.getLogger('platformdatafetcher.influencerattributeselector')

"""
Our goal here is to automatically pre-fill fields of Influencer so that our manual QA team doesn't have to spend time
going through them manually.


Basic idea is to go through the values from each platform's detected_influencer_attributes field and pick the
one that is most likely to be the correct value.
"""


class AutomaticAttributeSelector(object):
    def __init__(self, influencer, to_save=False):
        self.influencer = influencer
        self.platforms = influencer.platforms().exclude(url_not_found=True)
        self.to_save = to_save

        self.select_blogname()
        self.select_name()
        self.select_location()
        self.select_email()

    def _set_attribute_and_autodetectfield(self, attribute_name, attribute_value):
        """
        save value in Influencer
        """
        log.info("_set_attribute_and_autodetectfield [%s] : [%s] = [%s]" % (self.influencer.blog_url, attribute_name, attribute_value))
        if not attribute_value:
            return

        self.influencer.autodetect_attribute(attribute_name, attribute_value)

        if self.to_save:
            setattr(self.influencer, attribute_name, attribute_value)
            self.influencer.save()

    def _only_set_attribute(self, attribute_name, attribute_value):
        """
        save value in Influencer but not in the auto detected
        """
        log.info("_set_attribute [%s] : [%s] = [%s]" % (self.influencer.blog_url, attribute_name, attribute_value))
        if not attribute_value:
            return

        setattr(self.influencer, attribute_name, attribute_value)
        if self.to_save:
            self.influencer.save()

    @staticmethod
    def get_discovered_attribute_from_platform(attribute_name, plat):
        """
        Get discovered value from platform for a given attribute_name
        """
        if attribute_name in plat.influencer_attributes.keys():
            attribute_value = plat.influencer_attributes[attribute_name]
            log.info("Found attribute value %s for %s from %s" % (attribute_value, attribute_name, plat.url))
            return attribute_value
        return None

    def select_name(self):
        """
         We go through platforms in order: Gplus => Bloglovin => Twitter => Pinerest => Instagram
         For each potential candidate, we make sure to only pick it if
         a) it doesn't match theblog name
         b) it doesn't match the domain of the blog
         c) it doesn't match typical words like 'blogger'
        """
        def is_suspicious(n, inf):
            if not n:
                return True
            if n.strip().lower() == 'blogger':
                return True
            if ' by ' in n.lower() or ' of ' in n.lower() or ' from ' in n.lower():
                return True
            # more than 3 words in the name doesn't make sense
            if len(n.split()) > 3:
                return True

            # These below ones are causing false negatives
            # if name exists in the blog url, it's not a good sign
            #name_without_spaces = n.replace(' ', '').lower()
            #if name_without_spaces in inf.blog_url.lower():
            #    return True
            #if inf.blogname:
            #    # if name is a substring of the blogname or vice-versa, it's probably a bad value
            #    if n.lower() in inf.blogname.lower() or inf.blogname.lower() in n.lower():
            #        return True
            return False

        platnames_to_consider = ['Instagram', 'Gplus', 'Bloglovin', 'Twitter', 'Pinterest']
        for platname in platnames_to_consider:
            plat = self.platforms.filter(platform_name=platname)
            if len(plat) >= 1:
                plat = plat[0]
                name = AutomaticAttributeSelector.get_discovered_attribute_from_platform('name', plat)
                # don't use this name if it matches substring of the blogname
                log.info('AutomaticAttributeSelector: Name fetched: %s' % name)
                if not is_suspicious(name, self.influencer):
                    self._only_set_attribute('name', name)
                    return
        return

    def select_blogname(self):
        """
        Give bloglovin first priority. And then the blog platform.
        """
        bloglovin = self.platforms.filter(platform_name='Bloglovin')
        if len(bloglovin) >= 1:
            bloglovin = bloglovin[0]
            blogname = AutomaticAttributeSelector.get_discovered_attribute_from_platform('blogname', bloglovin)
            self._set_attribute_and_autodetectfield('blogname', blogname)
            return
        if self.influencer.blog_platform:
            blogname = self.influencer.blog_platform.blogname
            self._set_attribute_and_autodetectfield('blogname', blogname)
        return

    def select_email(self):
        """
        First give priority to Google+
        """
        gplus = self.platforms.filter(platform_name='Gplus')
        if len(gplus) >= 1:
            gplus = gplus[0]
            email_list = AutomaticAttributeSelector.get_discovered_attribute_from_platform('emails', gplus)
            if email_list and len(email_list) > 0:
                emails = ' '.join(email_list)
                self._set_attribute_and_autodetectfield('email_for_advertising_or_collaborations', emails)
        else:
            # iterating over platforms and fetching emails from them
            for pl in self.platforms:
                emails = extract_emails_from_text(pl.description)
                if len(emails) > 0:
                    # getting maximum 2 emails
                    emails = ' '.join(emails[:2])
                    self._set_attribute_and_autodetectfield('email_for_advertising_or_collaborations', emails)
        return

    def select_location(self):
        """
        Give Facebook.location first priority.
        If not available, then we should check if other platforms have any value provided.

        Our high level logic is the following:
            a) find all found values from each of the platform.detected_demographics_location
            b) find common ones
            c) remove the entries that have weird entries
            d) rest of them, enter the different set of values separated by //
        """
        fb = self.platforms.filter(platform_name='Facebook')
        if len(fb) >= 1:
            fb = fb[0]
            location = AutomaticAttributeSelector.get_discovered_attribute_from_platform('location', fb)
            self._set_attribute_and_autodetectfield('demographics_location', location)
            return

        ## helper method to remove candidates that look suspicious
        def remove_suspicious(candidates):
            suspicious = ['!', '-', '\\x', '+', '(', ')', '&', '.com', '@', '/', 'the', 'where', 'world', 'but',
                         'space', 'of', 'land', 'midtown', ' from ', ' to ']
            to_remove = set()
            for c in candidates:
                for s in suspicious:
                    if s in c:
                        to_remove.add(c)
                if len(c) > 25:
                    to_remove.add(c)
                    continue
                # split this in words
                ww = c.split(' ')
                if len(ww) > 5:
                    to_remove.add(c)

            to_remove = list(to_remove)
            for t in to_remove:
                candidates.remove(t)
            return candidates
        ## now let's check if we have other options
        plats_with_loc = self.platforms.filter(detected_demographics_location__isnull=False).exclude(platform_name='Facebook')
        if len(plats_with_loc) > 0:
            locs = [p.detected_demographics_location.lower() for p in plats_with_loc]
            locs = set(locs)
            # avoid values that contain "!" or common english words like "but" "where" "the"
            final_candidates = remove_suspicious(list(locs))
            log.info("Location candiates %s" % final_candidates)
            if len(final_candidates) > 0 and len(final_candidates) <= 5:
                if len(final_candidates) == 1:
                    final_candidates = final_candidates[0]
                else:
                    final_candidates = "//".join(final_candidates)
                self._only_set_attribute('demographics_location', final_candidates)
        return


def detect_influencer_attributes(influencers):
    for influencer in influencers:
        AutomaticAttributeSelector(influencer, to_save=False)
        influencer.save()


def run_on_new_infs():
    """
    This should be called every day so that new influencers are analyzed before QA can work on them.
    """
    query = Influencer.objects.filter(source__isnull=False, blog_url__isnull=False, blacklisted=False)
    query = query.filter(source__icontains='manual_')
    query = query.exclude(show_on_search=True)
    query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
    # this makes sure we have run the platform extraction
    with_social = query.filter(Q(gplus_url__isnull=False) |
                               Q(fb_url__isnull=False) |
                               Q(tw_url__isnull=False) |
                               Q(pin_url__isnull=False) |
                               Q(insta_url__isnull=False) |
                               Q(youtube_url__isnull=False) |
                               Q(bloglovin_url__isnull=False))

    for i in with_social:
        # first ensure that only valid social handles are left
        admin_helpers.handle_social_handle_updates(i, 'tw_url', i.tw_url)
        admin_helpers.handle_social_handle_updates(i, 'fb_url', i.fb_url)
        admin_helpers.handle_social_handle_updates(i, 'pin_url', i.pin_url)
        admin_helpers.handle_social_handle_updates(i, 'insta_url', i.insta_url)
        admin_helpers.handle_social_handle_updates(i, 'bloglovin_url', i.bloglovin_url)
        admin_helpers.handle_social_handle_updates(i, 'gplus_url', i.gplus_url)
        detect_influencer_attributes(i)


