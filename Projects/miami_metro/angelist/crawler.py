__author__ = 'atulsingh'

from xpathscraper import xbrowser as xbrowsermod
from django.conf import settings
from time import sleep
import requests
from debra.models import AngelListProfile, AngelListCompanyUserRelationship
from selenium.webdriver.common.keys import Keys

ANGEL_LIST_INVESTOR_HOME = 'https://angel.co/people/investors/'

list_of_investor_profile_urls = set()

LOCATIONS = ["San Francisco", "Seattle", "New York", "Los Angeles", "Boston", "Austin", "Menlo Park", "Washington, DC",
             "Philadelphia", "Denver", "San Diego", "Chicago", "Paris", "London", "Berlin", "Portland", "Houston",
             "Charlotte", "Canada", ]


def get_handle(prof):
    # https://angel.co/kapil-agrawal?utm_source=news => expected output: "kapil-agrawal"
    i0 = prof.find('?')
    i1 = prof.find('angel.co/')
    return prof[i1+len('angel.co/'):i0] if i0 > 0 else prof[i1+len('angel.co/'):]


def get_investments_and_advisees(startup_roles):
    # input is a list of entries
    investment = []
    advisee = []

    for role in startup_roles:
        print "\n--\nrole: %s" % role
        #print "type: %s get(startup): %s" % (type(role), role.get('startup', None))
        if type(role) is unicode or not role.get('startup', None):
            continue
        startup_name = role['startup']['angellist_url']
        company_url = role['startup']['company_url']
        if company_url is None:
            company_url = ''
        print '%s %s' % (startup_name, role['role'])
        if role['role'] == 'past_investor':
            investment.append(startup_name + "|||" + company_url)
        else:
            advisee.append(startup_name + "|||" + company_url)
        print "\n------\n"
    #print "investments: %s" % investment
    #print "advisees: %s" % advisee
    return investment, advisee

def fetch_profile_details(prof, only_basic=False):
    print prof.url
    handle = get_handle(prof.url)
    url = 'https://api.angel.co/1/users/search?slug=' + handle
    rep = requests.get(url)
    result = rep.json()
    print result
    print "\n+++++++++++\n"
    name = result.get('name', None)
    twitter_url = result.get('twitter_url', None)
    linkedin_url = result.get('linkedin_url', None)
    facebook_url = result.get('facebook_url', None)
    online_bio_url = result.get('online_bio_url', None)
    resume_url = result.get('resume_url', None)
    angel_id = result.get('id', None)
    roles = result.get('roles', None)
    bio = result.get('bio', None)
    all_roles = ''

    if roles:
        for r in roles:
            all_roles += (', ' + r.get('display_name', ''))
    print "%r, %r, %r, %r, %r, %r, %r, %r" % (name, twitter_url, linkedin_url, facebook_url, resume_url,
                                            online_bio_url, angel_id, all_roles)

    if not angel_id:
        return
    print "\n+++++++++\n"
    assert angel_id is not None
    prof.name = name
    prof.twitter_url = twitter_url
    prof.linkedin_url = linkedin_url
    prof.facebook_url = facebook_url
    prof.resume_url = resume_url
    prof.online_bio_url = online_bio_url
    prof.roles = all_roles
    prof.angel_id = angel_id
    prof.bio = bio
    prof.save()

    # markets and location
    other_meta_info = 'https://api.angel.co/1/users/' + str(angel_id) + "/?include_details=investor"
    print "Fetching URL: %s" % other_meta_info
    other_meta_response = requests.get(other_meta_info)
    other_meta_val = other_meta_response.json()
    print other_meta_val
    details = other_meta_val['investor_details']
    markets = details['markets']
    market_vals = ''
    for m in markets:
        market_vals = market_vals + "," + m['display_name']
    print "===>"
    print market_vals
    print "\n+++++++++\n"

    location_vals = ''
    locations = other_meta_val['locations']
    for l in locations:
        location_vals = location_vals + ',' + l['display_name']

    print location_vals
    print "\n+++++++\n"

    is_accredited = details['accreditation'] == 'Yes'
    print "Investor accredited: %d" % is_accredited
    prof.is_accredited = is_accredited
    prof.locations_interested = location_vals
    prof.markets_interested = market_vals
    prof.save()

    if only_basic:
        return

    # investments & advisory roles & founding
    roles_url = 'https://api.angel.co/1/users/' + str(angel_id) + "/roles"
    print "Fetching URL: %s" % roles_url
    roles = requests.get(roles_url)
    roles = roles.json()
    print roles
    print "\n+++++++++\n"
    investments = None
    advisees = None
    if roles:
        print "We got %d roles " % len(roles['startup_roles'])
        # we will need to do pagination for finding all values
        total_pages = roles['last_page']
        cur_page = roles['page']
        investments, advisees = get_investments_and_advisees(roles['startup_roles'])
        while cur_page <= total_pages:
            cur_page += 1
            roles_url = 'https://api.angel.co/1/users/' + str(angel_id) + "/roles?page="+str(cur_page)
            print "Fetching URL: %r" % roles_url
            roles = requests.get(roles_url)
            roles = roles.json()
            new_investments, new_advisees = get_investments_and_advisees(roles['startup_roles'])
            investments += new_investments
            advisees += new_advisees

    print "%r, %r, %r, %r, %r, %r, %r, %r" % (name, twitter_url, linkedin_url, facebook_url, resume_url,
                                            online_bio_url, angel_id, all_roles)

    print "++++++++++ Investments +++++++++"
    for i in investments:
        print "%r" % i
        angel_url = i.split('|||')[0]
        company_url = i.split('|||')[1]
        AngelListCompanyUserRelationship.objects.get_or_create(user=prof,
                                                               company_url=company_url if company_url else None,
                                                               angellist_url=angel_url,
                                                               relationship='Investor')


    print "++++++++++ Advising    +++++++++"
    for i in advisees:
        print "%r" % i
        angel_url = i.split('|||')[0]
        company_url = i.split('|||')[1]
        AngelListCompanyUserRelationship.objects.get_or_create(user=prof,
                                                               company_url=company_url if company_url else None,
                                                               angellist_url=angel_url,
                                                               relationship='Advisor')

    # investment thesis
    # seed

def run():
    profiles = set()
    for location in LOCATIONS:
        xb = xbrowsermod.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY, disable_cleanup=False)
        xb.load_url(ANGEL_LIST_INVESTOR_HOME)
        # now find the button to enter location
        print "now trying location %s" % location
        try:
            loc = xb.el_by_xpath('//input[@placeholder="Add Location"]')
            loc.send_keys(location)
            sleep(5)
            loc.send_keys(Keys.RETURN)
            sleep(5)
        except:
            print "oops, error"
            raise

        count = 0
        while count < 50:
            try:
                profile_links = xb.els_by_xpath('//a[@class="profile-link"]')
                print "Got %d links " % len(profile_links)
                for p in profile_links:
                    u = p.get_attribute('href')
                    v = AngelListProfile.objects.get_or_create(url=u)[0]
                    profiles.add(v)
                    print "We have now %d AngelListProfiles" % AngelListProfile.objects.count()

                more_link = xb.els_by_xpath('//div[@id="more_pagination_button_people_items"]/div[@class="wrapper"]')
                print "Got %d more links" % len(more_link)
                if len(more_link) > 0:
                    more_link = more_link[0]
                    more_link.click()
                    print "clicking on the more link"

                count += 1
                sleep(10)
            except:
                break
                pass
        try:
            xb.cleanup()
        except:
            pass



    for prof in profiles:
        # we're going to use the API to find this information
        fetch_profile_details(prof)
        # now sleep enough to make sure we're < 1000 API calls/hour
        sleep(10)


def print_angel_info():
    saved_angels = AngelListProfile.objects.filter(roles__icontains='Angel').exclude(roles__icontains='VC').exclude(roles__icontains='seed').order_by('-id')
    q1 = saved_angels.filter(markets_interested__icontains='social')
    q2 = saved_angels.filter(markets_interested__icontains='advertising')
    q3 = saved_angels.filter(markets_interested__icontains='blog')
    q4 = saved_angels.filter(markets_interested__icontains='influencer')
    q5 = saved_angels.filter(markets_interested__icontains='market')

    print "Angels with focus on social %d " % q1.count()
    print "Angels with focus on adversiting %d " % q2.count()
    print "Angels with focus on blog %d " % q3.count()
    print "Angels with focus on influencer %d " % q4.count()
    print "Angels with focus on marketing or marketplaces %d " % q5.count()

    final_angel_list = q1 | q2 | q3 | q4 | q5

    saved_angels = final_angel_list.distinct()

    print "Final, we have %d angels " % saved_angels.count()

    competition = ['piqora', 'curalate', 'offerpop', 'olapic', 'sverve']

    not_competitive_ids = set()

    for s in saved_angels:
        is_competitive = False
        for c in competition:
            if not is_competitive and AngelListCompanyUserRelationship.objects.filter(user=s, company_url__icontains=c):
                is_competitive = True
            if not is_competitive and AngelListCompanyUserRelationship.objects.filter(user=s, angellist_url__icontains=c):
                is_competitive = True
        if not is_competitive:
            not_competitive_ids.add(s.id)


    not_competitive_angels = saved_angels.filter(id__in=not_competitive_ids)
    print "Got %d angels that are not competitive " % len(not_competitive_angels)

    for n in not_competitive_angels:
        roles = AngelListCompanyUserRelationship.objects.filter(user=n)
        investments = ''
        advisees = ''
        for r in roles.filter(relationship='Investor'):
            investments += (':' + r.company_url if r.company_url else '')
        for r in roles.exclude(relationship='Investor'):
            advisees += (':' + r.company_url if r.company_url else '')

        print "%r\t%r\t%r\t%r\t%r\t%r" % (n.url, n.name, n.linkedin_url, n.markets_interested, investments, advisees)

if __name__ == '__main__':
    #run()
    print_angel_info()
