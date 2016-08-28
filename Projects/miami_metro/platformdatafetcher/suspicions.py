from __future__ import division
import logging
import baker

from debra import models
from debra import constants
from debra import db_util
from django.db.models import Q
from hanna import import_from_blog_post

from platformdatafetcher import platformutils
from xpathscraper import utils
from xpathscraper import textutils


log = logging.getLogger('platformdatafetcher.invariants')


BLACKLISTED_MAINSTREAM_HANDLES = {platformutils.url_to_handle(u)
                                  for u in import_from_blog_post.exclude_domains}


def append_social_urls_to_blacklist_handles():
    """
    Here, we extend the list of bad urls by creating fake urls, such as "twitter.com/pinterest". This is an invalid
    url and should be caught. So, here, we create such fake urls for each platform that we crawl.
    """
    social_platform_names = models.Platform.SOCIAL_PLATFORMS_CRAWLED
    new_blacklist = []
    for s1 in social_platform_names:
        u = s1.lower() + '.com'
        for s2 in social_platform_names:
            if s1 == s2:
                continue
            u2 = u + "/" + s2.lower()
            #print(u)
            new_blacklist.append(u2)
    print '\n'.join(new_blacklist)
    BLACKLISTED_MAINSTREAM_HANDLES.union(set(new_blacklist))

append_social_urls_to_blacklist_handles()

def is_blacklisted(url):
    if '#!' in url:
        return False
    return platformutils.url_to_handle(url) in BLACKLISTED_MAINSTREAM_HANDLES


HIGH_VARIATION_FACTOR = 0.5
HIGH_VARIATION_MIN_VALUE = 50


def high_variation(nums):
    if len(nums) < 3:
        return False
    for prev, curr in utils.window(nums, 2):
        if prev < HIGH_VARIATION_MIN_VALUE and curr < HIGH_VARIATION_MIN_VALUE:
            continue
        diff = abs(prev - curr)
        base = max(prev, curr)
        diff_factor = diff / base
        if diff_factor > HIGH_VARIATION_FACTOR:
            log.debug('Large difference between numbers: %s %s', prev, curr)
            return True
    return False


class InfluencerSuspicion(object):

    def report(self, influencer):
        """Should insert ``InfluencerCheck`` if an influencer is suspected.
        """
        raise NotImplementedError()

    def __repr__(self):
        return self.__class__.__name__


class GlobalSuspicion(object):

    def report_all(self):
        """Should insert ``InfluencerChecks`` for all suspected influencers
        """

    def __repr__(self):
        return self.__class__.__name__


class SuspiciousURLs(InfluencerSuspicion):

    def report(self, influencer):
        fields = []
        if not utils.url_is_valid(influencer.blog_url):
            fields.append('blog_url')
        for url_field in models.Influencer.platform_name_to_field.values():
            url_str = getattr(influencer, url_field, '') or ''
            urls = url_str.split()
            for url in urls:
                if url and (not utils.url_is_valid(url) or not utils.can_get_url(url)):
                    if url_field not in fields:
                        fields.append(url_field)
        if fields:
            log.info('Inserting url suspicion, fields %s inf %r', fields, influencer)
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_NON_EXISTING_URL, fields)
        else:
            log.info('No url suspicion for %r', influencer)


class SuspiciousEmails(InfluencerSuspicion):
    """
    Here we evaluate if either of the emails entered for this Influencer is problematic.

    We should follow this logic:

    0. If we already have InfluencerCheck for this influencer with SUCCESS, return

    1. Look at both fields (email_for_advertising_or_collaborations and email_all_other), one after another
        - Find value of the field
        - If None or 'null' or '':
            => replace the value of the field to None
            => continue (i.e., go the next field)
        - Else:
            => split value into an array of emails (as we assume that emails should be space separated)
            => for each email
                ==> if utils.email_is_valid() method fails: (to check for syntactical errors)
                    ===> save this email and the field. This is problematic.
                ==> if passes: (still can be semantic errors)
                    ===> if KICKBOX API gives an error:
                        ====> save this email and the field and reason.
                    ===> SUCCESS, this email is good
                        ====> save this Influencer with success as reason

    (at this point, our Influencercheck will have influencers that have an erroneous email in one of the fields)
    2. Now, find all influencers that don't have any email in their fields as well as
        - infs = Influencer.objects.filter(show_on_search=True).filter(email_for_advertising_or_collaborations__isnull=True, email_all_other__isnull=True)
        - these should have a contact form
        - if no contact form or broken contact form:
            => create an InfluencerCheck with "No contact form"
        - else:
            => SUCCESS, we found a valid contact form page.

    """

    def check_contact_form_url(self, influencer, field, to_save=True):
        val = getattr(influencer, field)
        ## nothing in contact form field
        if not val:
            return
        # if we already have an InfluencerCheck and its status is either VALID or NEW, return
        if models.InfluencerCheck.already_exists(influencer, models.InfluencerCheck.CAUSE_NON_EXISTING_URL, field):
            return
        if not utils.can_get_url(val):
            print "Ooops, URL is invalid %s " % val
            if to_save:
                models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_NON_EXISTING_URL, [field])
        else:
            print "Awesome, contact form URL is Valid %s " % val
            if to_save:
                # find all existing InfluencerCheck for this field and with this cause, mark all of them as VALID
                existing_checks = models.InfluencerCheck.objects.filter(influencer=influencer,
                                                                        cause=models.InfluencerCheck.CAUSE_NON_EXISTING_URL,
                                                                        fields=field)
                # update the state of all InfluencerCheck for this email to STATUS_VALID
                if existing_checks.exists():
                    existing_checks.update(status=models.InfluencerCheck.STATUS_VALID)
                else:
                    # Create a new InfluencerCheck and then change the status to STATUS_VALID
                    c = models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_NON_EXISTING_URL, [field])
                    if c:
                        c.status=models.InfluencerCheck.STATUS_VALID
                        c.save()

    def report(self, influencer, to_save=True):
        self.check_contact_form_url(influencer, 'contact_form_if_no_email', to_save)
        for field in ['email_for_advertising_or_collaborations', 'email_all_other']:
            email_str = getattr(influencer, field)
            if not email_str:
                continue
            emails = email_str.split()
            for email in emails:
                # if we alredy found to be suspect but not fixed yet or if it's mark validated => continue
                if models.InfluencerCheck.already_exists(influencer, models.InfluencerCheck.CAUSE_SUSPECT_EMAIL, field):
                    continue
                if models.InfluencerCheck.already_exists(influencer, models.InfluencerCheck.CAUSE_SUSPECT_EMAIL_KICKBOX, field):
                    continue

                # for all other cases, continue with testing
                if not utils.email_is_valid(email):
                    print 'Invalid email %s because it failed syntactic tests ' % email
                    if to_save:
                        models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_EMAIL, [field])
                else:
                    print 'KICKBOX semantic checking of email %s: ' % email,
                    if not utils.email_is_accepted(email):
                        print "FAILURE"
                        if to_save:
                            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_EMAIL_KICKBOX, [field])
                    else:
                        print "SUCCESS"
                        existing_checks = models.InfluencerCheck.objects.filter(influencer=influencer,
                                                                                cause__in=[models.InfluencerCheck.CAUSE_SUSPECT_EMAIL,
                                                                                           models.InfluencerCheck.CAUSE_SUSPECT_EMAIL_KICKBOX
                                                                                ],
                                                                                field=field)
                        # update the state of all InfluencerCheck for this email to STATUS_VALID
                        if existing_checks.exists():
                            existing_checks.update(status=models.InfluencerCheck.STATUS_VALID)
                        else:
                            # we'll create a new InfluencerCheck object and mark it as STATUS_VALID
                            if to_save:
                                c = models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_EMAIL, [field])
                                c.update(status=models.InfluencerCheck.STATUS_VALID)


        ## if all of [email_for_advertising_or_collaborations, email_all_other, contact_form_if_no_email] are empty
        ## then this should also be an error

        if not influencer.email_for_advertising_or_collaborations and not influencer.email_all_other and not influencer.contact_form_if_no_email:
            log.info('No emails or contact forms for %r', influencer)
            models.InfluencerCheck.report_new(influencer,
                                              None,
                                              models.InfluencerCheck.CAUSE_SUSPECT_NO_CONTENT,
                                              ['email_for_advertising_or_collaborations', 'email_all_other', 'contact_form_if_no_email'])


# class SuspiciousEmailsKickbox(InfluencerSuspicion):
#     def report(self, influencer):
#         for field in ['email_for_advertising_or_collaborations', 'email_all_other']:
#             email_str = getattr(influencer, field) or ''
#             emails = email_str.split()
#             for email in emails:
#                 if False:
#                     continue



class BlognameBloggernameSimilarities(InfluencerSuspicion):
    def report(self, influencer):
        if not influencer.blogname:
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_NAME_BLOGNAME, ['blogname'])
        if not influencer.name:
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_NAME_BLOGNAME, ['name'])
        if not influencer.blogname or not influencer.name:
            return
        if influencer.blogname.lower() == influencer.name.lower():
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_NAME_BLOGNAME, ['name', 'blogname'])
        else:
            if len(influencer.name) > 18:
                models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_NAME_BLOGNAME, ['name'])
            if len(influencer.blogname) > 25:
                models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_NAME_BLOGNAME, ['blogname'])
            words = textutils.tokenize_to_alpha_words(influencer.blogname)
            if len(words) <= 1:
                models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_BLOGNAME, ['blogname'])
            if any(textutils.is_emoji_char(c) for c in influencer.blogname):
                models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_BLOGNAME, ['blogname'], 'Emoji characters')



class SuspectDescription(InfluencerSuspicion):

    def _valid_description(self, desc):
        if not desc:
            return False
        if len(desc) < 50:
            return False
        if 'http:' in desc or 'www.' in desc:
            return False
        if any(textutils.is_emoji_char(c) for c in desc):
            return False
        return True

    def report(self, influencer):
        if not self._valid_description(influencer.description):
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_DESCRIPTION, ['description'])


class SuspectLocation(InfluencerSuspicion):
    """
    Problematic cases:
    a) http or .com in demographics_location
    b) '//' in demographics_location
    c) empty value
    """

    def report(self, influencer):
        if influencer.demographics_location is None:
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_LOCATION, ['demographics_location'])

        if influencer.demographics_location and not influencer.demographics_location_normalized and \
                influencer.platformdataop_set.filter(operation='normalize_location', error_msg=None).exists():
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_LOCATION, ['demographics_location'])



class SuspectOutlierPlatform(InfluencerSuspicion):

    def report(self, inf):
        plats = inf.platform_set.exclude(url_not_found=True)
        nums = [plat.num_followers for plat in plats]
        nums = [x for x in nums if x > 0]
        if len(nums) <= 1:
            return
        log.debug('outlier nums: %r', nums)
        avg = utils.avg(*nums)
        for x in nums:
            if x >= 50000:# and (not 0.3 * avg <= x <= 3.0 * avg):
                log.debug('invalid num: %r', x)
                of_plat = next(plat for plat in plats if plat.num_followers == x)
                models.InfluencerCheck.report_new(inf, of_plat, models.InfluencerCheck.CAUSE_SUSPECT_SOCIAL_PLATFORM_OUTLIER_FOLLOWERS, [])


class SuspectNotEnoughSocialUrls(InfluencerSuspicion):

    def report(self, influencer):
        valid_social_plats = [plat for plat in influencer.platform_set.all()
                              if plat.url_not_found is not True and plat.platform_name_is_social]
        num_social_plats = len(valid_social_plats)
        if num_social_plats <=1:
            log.info('One or less social platforms! Reporting.')
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_HIGH_COMMENTS_LOW_SOCIAL_URLS, [])
            return

class SuspectBigPublication(InfluencerSuspicion):

    def report(self, influencer):
        blog_platform = influencer.blog_platform
        if blog_platform and blog_platform.calculate_posting_rate > 50:
            log.info('One or less social platforms! Reporting.')
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_BIG_PUBLICATION, [])
            return


class SuspectHighFollowersLowSocialUrls(InfluencerSuspicion):

    def report(self, influencer):
        valid_social_plats = [plat for plat in influencer.platform_set.all()
                              if plat.url_not_found is not True and plat.platform_name_is_social]
        if not valid_social_plats:
            return
        if len(valid_social_plats) >= 3:
            # Enough platforms to be safe from this suspicion
            return
        social_followers = sum(plat.num_followers or 0 for plat in valid_social_plats)
        social_followers_per_platform = social_followers / len(valid_social_plats)
        if social_followers_per_platform >= 10000:
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_HIGH_FOLLOWERS_LOW_SOCIAL_URLS, [])


class SuspectBrokenMainstreamSocialLink(InfluencerSuspicion):

    def report(self, influencer):
        fields = []
        if is_blacklisted(influencer.blog_url):
            fields.append('blog_url')
        for url_field in models.Influencer.platform_name_to_field.values():
            url_str = getattr(influencer, url_field, '') or ''
            urls = url_str.split()
            for url in urls:
                if is_blacklisted(url):
                    if url_field not in fields:
                        fields.append(url_field)
        if fields:
            models.InfluencerCheck.report_new(influencer, None, models.InfluencerCheck.CAUSE_SUSPECT_BROKEN_SOCIAL, fields)




class SuspectSocialHandles(InfluencerSuspicion):
    def report(self, influencer):
        valid_social_plats = [plat for plat in influencer.platform_set.all()
                              if plat.url_not_found is not True and plat.platform_name in ('Facebook', 'Twitter', 'Instagram', 'Pinterest')]
        for plat in valid_social_plats:
            if not plat.autovalidated:
                models.InfluencerCheck.report_new(influencer, plat, models.InfluencerCheck.CAUSE_SUSPECT_SOCIAL_HANDLES, [])


class SuspectNoComments(InfluencerSuspicion):
    def report(self, influencer):
        valid_plats = [plat for plat in influencer.platform_set.all()
                       if not plat.url_not_found]
        if not valid_plats:
            return
        max_followers = max(plat.num_followers or 0 for plat in valid_plats)
        if max_followers >= 500:
            blog_platform = influencer.blog_platform
            if blog_platform and blog_platform.total_numcomments == 0:
                models.InfluencerCheck.report_new(influencer, blog_platform, models.InfluencerCheck.CAUSE_SUSPECT_NO_COMMENTS, [])


class SuspectNoFollowers(InfluencerSuspicion):
    def report(self, influencer):
        valid_social_plats = [plat for plat in influencer.platform_set.all()
                              if plat.url_not_found is not True and plat.platform_name in ('Facebook', 'Twitter', 'Instagram', 'Pinterest')]
        for plat in valid_social_plats:
            if not plat.num_followers:
                models.InfluencerCheck.report_new(influencer, plat, models.InfluencerCheck.CAUSE_SUSPECT_NO_SOCIAL_FOLLOWERS, [])


class SuspectDuplicateSocial(GlobalSuspicion):

    def report_all(self, platform_name):
        """
        Run this for each type of platform
        """
        cause_str = "CAUSE_SUSPECT_DUPLICATE_SOCIAL_%s" % platform_name
        cause = getattr(models.InfluencerCheck, cause_str)
        connection = db_util.connection_for_reading()
        cur = connection.cursor()
        cur.execute("""
        select distinct inf1.id, inf2.id, pl1.id
        from debra_platform pl1, debra_platform pl2, debra_influencer inf1, debra_influencer inf2
        where pl1.url = pl2.url
        and pl1.url <> ''
        and pl1.id < pl2.id
        and pl1.url_not_found=false
        and pl2.url_not_found=false
        and pl1.platform_name = '{platform_name}'
        and pl2.platform_name = pl1.platform_name
        and inf1.id=pl1.influencer_id
        and inf2.id=pl2.influencer_id
        and inf1.blacklisted=false and inf1.source is not null and inf1.validated_on like '%%info%%'
                    and inf1.show_on_search=true
        and inf2.blacklisted=false and inf2.source is not null and inf2.validated_on like '%%info%%'
                    and inf2.show_on_search=true
        """.format(platform_name=platform_name))
        log.info('Fetching %d duplicate pairs', cur.rowcount)
        for inf1_id, inf2_id, pl1_id in cur:
            models.InfluencerCheck.report_new(
                models.Influencer.objects.get(id=inf1_id),
                models.Platform.objects.get(id=pl1_id),
                cause,
                [],
                data={'related': [['Influencer', inf2_id]]},
            )
            models.InfluencerCheck.report_new(
                models.Influencer.objects.get(id=inf2_id),
                models.Platform.objects.get(id=pl1_id),
                cause,
                [],
                data={'related': [['Influencer', inf1_id]]},
            )


SUSPICIONS = [
    SuspiciousURLs(),
    SuspiciousEmails(),
    BlognameBloggernameSimilarities(),
    SuspectDescription(),
    SuspectLocation(),
    SuspectBrokenMainstreamSocialLink(),
    SuspectOutlierPlatform(),
    SuspectNotEnoughSocialUrls(),
    SuspectSocialHandles(),
    SuspectNoComments(),
    SuspectHighFollowersLowSocialUrls(),
    SuspectBigPublication(),
]

SUSPICIONS_GLOBAL_RUN = [
    SuspectDuplicateSocial(),
]


@baker.command
def report_suspicions(susp_list=SUSPICIONS, global_list=SUSPICIONS_GLOBAL_RUN, offset=None, limit=None):
    infs = models.Influencer.objects.filter(blacklisted=False,
        validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS).\
        exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED).\
        select_related('platform')

    if limit:
        infs = infs[offset:(offset + limit)]
    else:
        infs = infs[offset:]

    count = infs.count()

    models.InfluencerCheck.objects.filter(cause=models.InfluencerCheck.CAUSE_SUSPECT_NO_COMMENTS).delete()

    counter = 0

    for inf in infs:
        counter += 1
        print "{}/{}....".format(counter, count)
        for susp in susp_list:
            # log.info('Using %r processing %r', susp, inf)
            try:
                susp.report(inf)
            except KeyboardInterrupt:
                raise
            except:
                log.exception('While checking %r for %r', susp, inf)

    for susp in global_list:
        log.info('Running global suspicion %r', susp)
        susp.report_all()


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
