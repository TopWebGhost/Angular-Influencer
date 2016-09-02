# encoding: utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from platformdatafetcher import contentfiltering, contentclassification, platformutils
from xpathscraper import utils
from xpathscraper.xbrowser import redirect_using_xbrowser
import requests
from django.utils import encoding
from django.db.models.query import ValuesQuerySet
from debra import models as dmodels
import gc

social_url_domains = ['youtube', 'facebook', 'twitter', 'snapchat', 'youtu.be', 'pinterest', 'instagram']

domains_to_skip = ['dayre.me', 'ask.fm', 'liketk.it', 'liketoknow.it', 'line.me', 'chictopia.com', 'bitly.com',
                   'bit.ly', 'flickr.com', '500px.com', 'opensky.com', 'etsy.com', 'cbs46.com',
                   'beauty.hotpepper.js', 'behance.net', 'blog.naver.com', 'naver.com', 'cargocollective.com',
                   'cnn.com', 'ellie.com', 'flickr.com', 'glp.tv', 'gofundme.com', 'itun.es', '//l.co', 'line.me',
                   'linked.com', 'lookbook.nu', 'models.com', 'snapchat.com', 'styleseat.com', 'telegram.me',
                   'trendycandy.com', 'vimeo.com', 'vine.co', 'wattpad.com', 'wanderlust.com', 'weibo.com',
                   'amazon.com', 'behance.net', 'bigcartel.com', 'bocao.com', 'bridestory.com', 'cntraveler.com',
                   'ebay.com', 'elle.de', 'etsy.com', 'hautelook.com', 'huffingtonpost.com',  'huffingtonpost.ca',
                   'imdb.com', 'imdb.me', 'ipsy.com', 'lookbooker.com', 'medium.com', 'modelmayhem.com',
                   'nouw.com', 'poshmark.com', 'ravelry.com', 'sprezzabox.com', 'styleseat', 'thiscrush.com',
                   'vogue.', 'zalora.com', 'ask.fm', '500px.com', 'dayre.me', 'about.me', 'docs.google.com',
                   'soundcloud.com', 'suicidegirls.com', 'vk.com', 'birchbox.com', 'change.org', 'eventbrite.com',
                   'google.com', 'kickstarter.com', 'weebly.com', 'ameblo.jp', 'rantapallo.fi', 'elle.my',
                   'www.exclusively.com', 'itunes.apple.com', 'theshop.jp', 'dropbox.com', 'shop-online.jp',
                   'wechat.com', 'nylon.jp', 'styletribute.com', 'login.live.com', 'ndtv.com', 'paypal.com',
                   'ebay.co', 'yahoo.com', 'avon.com', 'my.avon.', 'eonline.com', 'zomato.com', 'whatwelike.co',
                   'myspace.com', 'twitch.com', 'mail.ru', 'gmail.com', 'shopify.com', ]


# We'll periodically crawl these instagram handles to fetch their posts and then we'll use our new pipelines
# to fetch new instagram handles
brand_handles_to_scrape_on_instagram = ['https://www.instagram.com/ritzcarlton/',
                                        'https://www.instagram.com/ergobaby/',
                                        'https://www.instagram.com/honest/',
                                        'https://www.instagram.com/revolve/',
                                        'https://www.instagram.com/oldnavy/',
                                        'https://www.instagram.com/modcloth/',
                                        'https://www.instagram.com/keds/',
                                        'https://www.instagram.com/americanapparelusa/',
                                        'https://www.instagram.com/tjmaxx/',
                                        'https://www.instagram.com/bananarepublic/',
                                        'https://www.instagram.com/urbanoutfitters/',
                                        'https://www.instagram.com/theloftfashion/',
                                        'https://www.instagram.com/lillypulitzer/',
                                        'https://www.instagram.com/aldo_shoes/',
                                        'https://www.instagram.com/stitchfix/',]

def get_description_decoded(description):
    """
    return ascii coded string so that simple text analysis doesn't fail. We also don't save it as this because
    front-end needs to be untouched.
    """
    if description:
        description = encoding.smart_str(description, encoding='ascii', errors='ignore')
    return description


def is_blog(url):
    return contentclassification.classify(url) == 'blog'


def is_social_link(url):
    lurl = url.lower()

    for dom in social_url_domains:
        if dom in lurl:
            return True
    return False


def find_blogs(description, category):
    non_social_links = extract_non_social_links(description)
    blog_links = [link for link in non_social_links
                  if is_blog(link)]
    return set(blog_links)


def extract_links(description):
    links = contentfiltering.find_all_urls(description)
    res = set()
    for link in links:
        try:
            # # Previous implementation: could not deal with something like 'http://t.co/SAMTfJlIeg'
            # r = requests.get(link, timeout=20, headers=utils.browser_headers())
            # if (r.status_code == 200 or 'squarespace' in r.content) and len(r.url) >= 15:
            #     # res.add(r.url.lower())
            #     res.add(r.url)
            # else:
            #     if r.status_code is not 200:
            #         print("Not adding %s because status code is %d" % (link, r.status_code))
            #     if len(r.url) < 15:
            #         print("Not adding %s because length is %d" % (link, len(r.url)))

            # Implementing selenium-based method for receiving urls after redirections
            final_url = redirect_using_xbrowser(link, timeout=20)
            if final_url is not None and len(final_url) > 0:
                res.add(final_url)
        except Exception as e:
            # whatever the error, ignore and move on
            print("Error %s with %s" % (e, link))
            continue
    return list(res)


def skip_network_links(link, declare_good=list()):
    """
    Here, we look at a given link and check if exists in our list of suspicious url domains that belong to
    magazines, stores, or other local networks.

    if we provide declare_good list of urls, we consider not to skip that url even if it is in domains_do_skip list.
    """
    domains = domains_to_skip
    for d in domains:
        if d in link.lower() and d not in declare_good:
            return True
    return False

def extract_non_social_links(profile_description):
    """
    This is a helper method to check if the profile has any non-social link. These are
    likely to be brands. Profiles that don't have such a a link are likely to be influencers.
    """
    links = extract_links(profile_description)
    non_social_links = []

    for link in links:
        # no need to strip the url path for these
        if skip_network_links(link):
            ll = None
        else:
            ll = utils.post_to_blog_url(link)
        if not ll or dmodels.Platform.is_social_platform(ll):
            continue
        non_social_links.append(ll)
    return non_social_links


def extract_all_social_links(profile_description):
    """
    Extracts all urls that are social links
    """
    links = extract_links(profile_description)
    social_links = []

    for link in links:
        if dmodels.Platform.is_social_platform(link):
            social_links.append(link)
    return social_links


def extract_blog_link_from_ltkt(link):
    # this didn't work with lxml, may need to use selenium
    # TODO later
    import lxml.html

    try:
        r = requests.get(link, timeout=20, headers=utils.browser_headers())
        print("r.status %d" % r.status_code)
        tree = lxml.html.fromstring(r.content)

        username_links = tree.xpath('//div[@class="usr_head"]//a')
        print("Found %d username links" % len(username_links))
        username = None
        for position, ll in enumerate(username_links):
            print("position: %d" % position)
            href = ll.attrib.get('href')
            print("href=%r" % href)
            if not href:
                continue
            else:
                username = href
                print("Got username %r" % username)
                break

        u = 'http://liketoknow.it/'+ username
        r = requests.get(u, timeout=20, headers=utils.browser_headers())
        tree = lxml.html.fromstring(r.content)
        blog_url_path = tree.xpath('//a[@class="blog_url"]')
        if len(blog_url_path) == 0:
            print("no blog url found")
            return None
        blog_url = blog_url_path[0].attrib.get('href')
        print("Found blog url: %r" % blog_url)
        return blog_url
    except Exception as e:
        print("Error %s with %s" % (e, link))

    return None


def find_profiles_with_non_branded_links(qset):
    ids = set()
    for q in qset:
        r = extract_non_social_links(q.profile_description)
        if r == []:
            ids.add(q.id)

    return qset.filter(id__in=ids)

hashtags = {
    'fashion_hashtags': ['ontheblog', 'liketkit', 'fashionblogger', 'styleblogger', 'fashionblog', 'styleblog',
                         'mensfashion',
                         'manstyle', 'makeupartist', 'makeupaddict', 'menstyle', 'menwithstyle',
                         'outfitideas', 'trendspotter', 'yougotitright', 'streetstyleluxe', 'whatiworetoday',
                         'streetstyled', 'outfitpost', 'vscostyle', 'fashionpost', 'fashionkiller', 'currentlywearing',
                         'stilkolik', 'stylediaries', 'stylemacarons', 'bloggerdiaries', 'outfitshare',
                         'realoutfitgram', 'stylegram', 'stylehunters', 'lookoftheday', 'aboutalook',
                         'flashesofdelight', 'bloggerfashion', 'fashionlivesonootd', 'fashiondaily', 'ootdwatch',
                         'theblogissue', 'outfitdetails', 'aboutalook', 'todayslook', 'momentsofchic', 'ootdmagazine',
                         'ilovefashionbloggers', 'modeblogger', 'mystyle', 'dailylook', 'lotd', 'ltkstyletip',
                         'winterstyle', 'fblogger', 'winterfashion', 'denimondenim', 'ldnfashion', 'todayiamwearing',
                         'asseenonme', 'outfitgrid', 'realoutfitgram', 'todayimwearing', 'f21xme', 'aeostyle',
                         'outfitideas4you', 'outfitdetails'],
                        # 'ootd',
                        #'instablog', 'manstyle', 'getthelook', 'instafashion', 'whatimwearing', 'outfittoday', 'looktoday',
                        #'fwis', 'danielwellington', 'wiw', 'vancityvogue', 'ootdfash', 'aboutalook', 'styleoftheday',
                        #'styleblogger',  'lookoftheday',
                        #'stylexstyle', 'stelladotstyle', 'outfitinspo', 'mensstreetstyle', 'fashiondiary', 'charmingcharlie'],
                        #'streetstyle', 'mystyle','outfit', 'clothes', 'whatiwore', 'whatiworetoday', 'mylook'],
    'food_hashtags': [# 'foodporn',  'food', 'bbq', 'cooking', 'paleo', 'seafood', 'foodie',
                      #    'instafood', 'chef', 'foodshoot', 'nomnomnom', 'nomnom', 'recipe', 'cuisine', 'foodpics',
                      'foodblog', 'foodblogger', 'veganlove', 'goodcarbs', 'whatveganseat', 'plantbased',
                      'veganfoodshare', 'healthyfoodshare', 'govegan', 'gesundundlecker', 'highcarbvegan',
                      'glutenfree', 'glutenfritt', 'simplefood', 'simplecooking', 'seasonalfood', 'veganfoodlovers',
                      'foodenvy', 'quinoa', 'veganofig', ],

    'lifestyle_hashtags': ['justgoshoot', 'thislifetoday', 'darlingmovement', 'thatsdarling', 'postthepeople',
                           'makeyousmilestyle', 'inspocafe', 'ontheblog', 'bespoke', 'flatlays',
                           'makeitblissful', 'todayslovely', 'gatheredstyle', 'fwis', 'lotd',
                           'pursuepretty', 'urlaub'],

    'healthfitness_hashtags': ['fabletics', 'fitnessblogger'],

    'travel_hashtags': [#'vacation', 'trip', 'getaway', 'wanderlust', 'vacaciones', 'minivacation', 'travel',
                        #     'travelbug', 'bucketlist', 'backpacking', 
                        'instatravel', 'travelgram', 'travelblog', 'travelblogger', 'travelinspo', 'worldtraveler', 'instapassport',
                        'travelinstyle', 'nomadlife', 'expatliving', 'travelista', 'oftd', 'travelwriter', 'travelgirl', 'travelstyle',
                        'traveltheworld', 'womentravel', 'traveldiary', 'worldtraveler', 'traveladdict', 'travelogue', 'travelingram',
                        'mytravelgram'],
    'mom_hashtags': ["mommyblogger" , "momblogger" , "cookingblog" , "cookingblogger" , "mommystyle" , "momstyle" ,
                     "mommyblog" , "mommylife" , "familytravel" , "fashionkidsmoms" , "mumlife" , "harlowhandmade" ,
                     "toddlerlife" , "littleandbrave" , "candidchildhood" , "heaventhrumylens" , "clickinmoms" ,
                     "momtogs" , "momswithcameras" , "simplychildren" , "creative_kid_edits" , "throughachildseyes" ,
                     "ourchildrenphoto" , "kids_circle" , "mom_hub" , "tinytrendz" , "spectacularkidz" , "cmglimpse" ,
                     "childhoodunplugged" , "candidchildhood" , "kidsootd" , "mumlife" , "babystyleguide" , "travelingwithkids" ,
                     "motherhood" , "kidsfashionforall" , "babysfirstchristmas" , "firstchristmas" , "momswithboys" ,
                     "bestofmom" , "momlife" , "motherandson" , "toddler" , "babiesofinstagram" , "babywearing" , "cameramama" ,
                     "childofig" , "childrenofinstagram" , "childrenphoto" , "childrenphotography" , "cute_baby_photo" ,
                     "cutekidsfashion" , "dailyparenting" , "documentyourdays" , "ig_baby" , "ig_beautiful_kids" , "ig_kids" ,
                     "ig_motherhood" , "igkiddies" , "joyfulmamas" , "kids_of_our_world" , "kidsgeneration" , "kidsofinstagram" ,
                     "kidsstylezz" , "kidzfashion" , "lblogger" , "letthembelittle" , "littlestoriesofmylife" ,
                     "livethelittlethings" , "loves_children" , "mamarazzi" , "minibeautiesandgents" , "ministylekids" ,
                     "momsofinstagram" , "momtog" , "motherhoodrising" , "motherhoodthroughinstagram" , "motherhoodunplugged" ,
                     "mumswithcameras" , "mytinymoments" , "ohheymama" , "our_everyday_moments" , "petitejoys" , "prettylittlething" ,
                     "thechildrenoftheworld" , "thehappynow" , "tinybeansmoment" , "trendykiddies" , "umh_kids" , "uniteinmotherhood" , "vscokids" ,],
    'decor_hashtags': ['homedecorblog', 'lifestyleblog', 'lifestyleblogger', 'decorblog', 'decorblogger', 'westelm',
                       'the_real_houses_of_ig', 'completehappyhome', 'homeproject', 'decorblog',
                       'inspire_me_home_decor', 'instahomedecor', 'makehomeyours', 'mypotterybarn', 'completehappyhome',
                       'wainscoting', 'remodel', 'housetohome', 'farmhousedecor', 'cottagestyle', 'cottagedecor',
                       'farmhousestyle', ],
    'video_hashtags': ['vlogger', 'youtuber'],
    'beauty_hashtags': ['beautyblog', 'beautyblogger', 'makeupblog', 'makeupblogger'],
    'menfashion_hashtags': ['dollarshaveclub', 'baxterofcalifornia', 'JackThreads', 'mensgrooming', 'pompadour',
                            'fashionstork', 'menwithclass', 'fashionformen', 'menwithstreetstyle', 'mrporter',
                            'menwithclass', 'gqstyle', 'simplydapper', 'dapperman', 'mentrend', 'menstyleguide',
                            'suitlife', 'estilohombre', 'estilomasculino', 'ootdmen', 'guystyle', 'sprezzatura',
                            'sartorial', 'cordovan', 'gqstylehunt', 'nudiejeans', 'suitup',
                            'suitandtie', 'tailored', 'meninsuits', 'pocketsquare'],

    'singapore': ['clozetteambassador', 'clozettedaily', 'clozette', 'clozetteid', 'stylexstyle', 'dressedinfayth', 'welovecleo',
                  'projecttrendit', 'afstreetstyle', 'oo7d', 'ofes', 'theinfluencernetwork', 'vauntstyle', 'styyli', 'ootdasean',
                  'asianfashion', 'uljjangfashion', 'uljjangstyle', 'ulzzangfashion', 'ulzzangstyle', 'fasyen', 'ootdsg', 'sgootd',
                  'lookbooksg', 'sglookbook', 'sgblogger', 'bloggersg', 'fashionsg', 'sgfashion', 'stylesg', 'sgstyle', 'beautysg',
                  'sgbeauty', 'sgigstyle', 'igsgstyle', 'vscosg', 'sgvsco', 'vscocamsg', 'exploresg', 'exploresingapore', 'wiwtsg',
                  'innershinesg', 'outfitsg', 'igersingapore', 'gf_singapore', 'sgfashionweekly', 'zalorasg', 'blogshopsg', 'sg50',
                  'sgigfashion', 'singaporefashion', 'sgmodel', 'singaporeblogger', 'sgstreetstyleawards', 'iluvsg', 'sgdaily',
                  'CebuFashionBloggers', 'pilipinasootd', 'bloggersph', 'ootdpinoy', 'ootdpinas', 'pinayfashionista', 'lookbookph',
                  'vscophilippines', 'indonesianstyle', 'jakartafashion', 'indofashionpeople', 'lookhitz', 'ootdindomen',
                  'lookbookindonesia', 'ootdyk', 'ootdjogja', 'lookbookyk', 'indonesiafashionlook', 'idfashionlook', 'koreanstyle',
                  'koreanlook', 'koreanfashion', 'kstyle', 'kfashion', 'seoulfashionweek'],

    'hongkong': ['hkootd', 'hkfashion', 'hkbeautyblogger', 'hkfoodblogger', 'hkig',],
    'india': ['indianfashion', 'indianstyle', 'indianfoodblogger', 'indiafashion'],
    'fashion_brands': ['modcloth', 'nordstrom', 'katespade', 'ralphlauren', 'bonobos', 'warbyparker', 'herschel',
                       'zara', 'forever21', 'anntaylor', 'anthropologie', 'revolveme', 'toryburch',
                       'drmartens', 'revolveclothing', 'nastygal', 'shoptobi', 'nordstromrack', 'stuartweitzman',
                       'nordstrom', 'baublebar', 'chloeandisabel', 'stellaanddot', 'fcmember', 'americanapparel',
                       'dollskills', 'mvmt', 'birchbox', 'ltkunder100', 'ltkunder50', 'f21xme', 'charmingcharlies',
                       'seedheritage', 'jcrewfactory', 'thekooples', 'allsaints', 'hoorsenbuhs', 'anthropologie',
                       'barneysnewyork', ],
    'delivery_brands': ['blueapron', 'instacart', 'doordash',],
    'canada': ['vancouverblogger', 'ootdcanada', 'fashioncanadians', 'canadianblogger', 'montrealblogger',
               'canadianstreetstyle',
               'canadianfashion', 'vancouverfashion', 'montrealfashion', 'yegfashion', 'fashioncanada', 'torontostyle',
               'torontofashionblogger', 'torontostreetstyle', 'torontofashion', 'vancouverstyle', 'canadianyogi',
               'topshopcanada',
               'vancouverstyleblogger', 'vancitybuzz', 'viaawesome', 'vancouverbc', 'beautifulbc', 'downtownvancouver',
               'explorebc', 'explorecanada', 'igersvancouver', 'igersvancouver', 'canadianbloggers', 'igerscanada',
               'vancouverlife', 'vancouverlife', 'britishcolumbia', 'yvr',
               'canadianstyle', 'canadianfashion', 'fashioncanada', 'wearcanada', 'ootdcanada', 'fashioncanadians',
               'torontofashion', 'torontostyle', 'fashiontoronto', 'torontoblogger', 'bloggertoronto',
               'vancouvershopping', 'vancouvermodel', 'vancouverfashion', 'vancouverstyle', 'vancouverblogger',
               'calgaryfashion', 'calgaryblogger', 'calgaryshopping', 'yycfashion', 'yycblogger', 'yycstyle', 'yycblog',
               'calgarystyle', 'ottawafashion', 'ottawastylist', 'ottawastyle', 'ottowashopping', 'ottawabeauty',
               'ottawablogger', 'ootdottawa', 'montrealfashion', 'montrealshopping', 'quebecblogger', ],

    'south_america': ['perufashion', 'brazilfashion', 'cachosbrasil', ],
    'germany': ['german_blogger', 'blogger_de', 'fashionberlin', 'germanblogger', 'fashionblogger_muc',
                'fashionblogger_de', 'beautyblogger_de',],
    # ASIAN HASHTAGS
    'australian': [u'Australianfashion',
                    u'Australianstyle', u'Australianlifestyle', u'fashionAustralian', u'styleAustralian',
                    u'lifestyleAustralianblog', u'Australianblogs', u'Australianblogger', u'Australianbloggers',
                    u'blogAustralian', u'ootdAustralian', u'Australianootd', u'Australianclozette', u'Australianmodel',
                    u'Australianshop', u'Australianblogshop', u'Australiangirls', u'Australianwiw', u'wiwAustralian',
                    u'vscoAustralian', u'Australianoutfit', u'Australianvsco', u'igAustralian', u'Australianig',
                    u'Australia', u'Australiafashion', u'Australiastyle', u'Australialifestyle', u'fashionAustralia',
                    u'styleAustralia', u'lifestyleAustralia', u'Australiablog', u'Australiablogs', u'Australiablogger',
                    u'Australiabloggers', u'blogAustralia', u'ootdAustralia', u'Australiaootd', u'Australiaclozette',
                    u'Australiamodel', u'Australiashop', u'Australiablogshop', u'Australiagirls', u'Australiawiw',
                    u'wiwAustralia', u'vscoAustralia', u'Australiaoutfit', u'Australiavsco', u'igAustralia',
                    u'Australiaig', 'canonaustralia', 'melbournestyle', 'melbournefashion'],

    'only_sea' : ['singaporedance', 'universalstudiossingapore', 'malaysiaairlines', 'thaigirls', 'Indonesiabloggers',
                  'newmalaysiatrending', 'sg50again', 'igermalaysia', 'wow_malaysia', 'gildanmalaysia', 'singaporemodel',
                  'thaifood', 'sgselltrade', 'sghmanicmonday', 'malaysiaborneo', 'malaysianmade', 'japanfashion', 'thailandmodel',
                  'malaysiablogger', 'indianblogger', 'igsellermalaysia', 'stylesingapore', 'lvphilippines', 'hmphilippines',
                  'sgbridal', 'malaysianoutfit', 'sgbakeryhalal', 'sgfleamarket', 'celebrityfitnessmalaysia', 'fashionkorea',
                  'cittabellamalaysia', 'casiothailand', 'clozettedaily', 'malaysiablogs', 'lifestyleindochina', 'Indonesiablogs',
                  'malaysiaonlineshopping', 'fitnesssg', 'nutritiondepot_sg', 'sweaterkpopmalaysia', 'sginsideout',
                  'chanelperfumesmalaysia', 'igerssingapore', 'kidsgram_phils', 'sgfoodie', 'asianguy', 'skysg', 'malaysianblogs',
                  'malaysianonlineshop', 'befitmalaysia', 'japanclozette', 'flannelmalaysia', 'sghopeful', 'japanblogshop',
                  'vscoindochina', 'igersmalaysia', 'thailandphotography', 'happybirthdaysingapore', 'malaysiadestination',
                  'spotlightmalaysia', 'sgfoodies', 'indiabloggers', 'herbalifemalaysia', 'forever21philippines', 'koreanboy',
                  'japaneseblogshop', 'blogindochina', 'shakleemalaysia', 'malaysianphotographer', 'uljjangboy', 'fashionthai',
                  'pakaianimport', 'bazaarmalaysia', 'zalorasg', 'perfumemalaysia', 'malaysianarts', 'japanese', 'malaysianboy',
                  'hkbloggers', 'sweatermalaysiamurah', 'sjcammalaysia', 'japanig', 'yoursingapore', 'blogthailand', 'malaysiapublicholiday',
                  'thailandclozette', 'indochina', 'sgfleas', 'malaysiabrand', 'BloggerIndonesia', 'dubsmash_malaysia',
                  'nailpolishmalaysia', 'naturactophilippines', 'singapore2014', 'japanesegirls', 'lifeisdeliciousinsingapore',
                  'sglookbook', 'philippinesblogshop', 'malaysiaprettybabe', 'fashionhongkong', 'sglifestyle', 'bw_singapore',
                  'malaysianlifestyle', 'tiffanyhwang', 'starlivemalaysia', 'wonderfulmalaysia', 'fashionkidsmalaysia_raya',
                  'thailandstyle', 'calvinkleinmalaysia', 'thailandlovers', 'mumbaibloger', 'lifestylehongkong', 'nuffnangau',
                  'bangkok', 'hkshop', 'philippinesootd', 'singaporeflyer', 'dressmalaysia', 'pickatsg', 'wakdoyok', 'sgigstyle',
                  'ig_thailandia', 'singaporeig', 'ootdthai', 'koreanmakeuptutorial', 'foodsg', 'nuffnang', 'tudungmurahmalaysia',
                  'stylebloggerph', 'prayformalaysia', 'sglatinas', 'malaysianchinese', 'malaysianfood', 'lookingforsg',
                  'singaporeinsiders', 'hongkongblogshop', 'japaneseblogs', 'igmalaysiashop', 'tiensmalaysia', 'thaiootd',
                  '88lovelifemalaysia', 'indochinashop', 'stylexstyle', 'faythlabel', 'printingbajumalaysia', 'thailandlifestyle',
                  'canonmalaysia', 'coachsingapore', 'singaporetrip', 'stylethailand', 'blogthai', 'studentmalaysia', 'hermesthailand',
                  'vscojapan', 'malaysiaclozette', 'udmalaysia', 'landscapestylesgf', 'huntgrammalaysia', 'japanesevsco', 'cfmalaysia',
                  'asianmodel', 'ig_philippines', 'chihiro', 'bw_malaysia', 'tclootd', 'ootdIndonesia', 'malaysiavsco',
                  'malaysian_igers', 'ig_malaysia', 'vscomalaysia', 'malaysiadistrofiesta2014', 'malaysianbloggers', 'basicphilippines',
                  'indochinastyle', 'jasseries_sg', 'malaysiaweddingphotographer', 'ootdthailand', 'singaporeonlineshopping', 'ellesingapore',
                  'maxidressmalaysia', 'malaysiatrend', 'reviewigshopmalaysia', 'beautyboundasia', 'ootdjapanese', 'ig_minimalaysia',
                  'singaporebakes', '4malaysian', 'vscoindia', 'indiafashion', 'sgcarshoot', 'sukanmalaysia', 'sgdeals', 'igshopmalaysia',
                  'indiablogshop', 'charlesandkiethphilippines', 'mumbaiblogger', 'weddingmalaysia', 'fujifilmxcommunity_malaysia',
                  'ighongkong', 'thailandcuteboy', 'lifestylehk', 'vscosingapore', 'weddingmalaysiaphotographer', 'philippineslifestyle',
                  'malaysiaonlineshop', 'sgblogshops', 'vscocammalaysia', 'wow_thailand', 'indochinaig', 'plussizemalaysia',
                  'philippineonlineshop', 'krabithailand', 'igers_malaysia', 'alhamdulillahmalaysiamasihaman', 'gopromalaysia_official',
                  'asiangirl', 'lifestylemalaysia', 'chinesemalaysian', 'singaporestyle', 'indiablogger', 'kasutmalaysia', 'sgbakes',
                  'ulzzang', 'nikemalaysia', 'wiwmalaysian', 'singaporepackage', 'necklacemalaysia', 'malaysianwedding', 'vscopinas',
                  'gaymalaysia', 'michaelkorsmalaysia', 'bisnesonlinemalaysia', 'hkfoodie', 'koreanmalaysia', 'malaysiancafe', 'kimtan',
                  'hkblog', 'sukarelawanmalaysia', 'afasg15', 'igjapan', 'brownieconnoisseursg', 'eyesofphilippines', 'tuullathelabel',
                  'vsvomalaysia', 'uniqlomalaysia', 'kaftanmalaysia', 'lehnga', 'ootdhongkong', 'prelovedmalaysia', 'hkmodel',
                  'begmalaysiamurah', 'Indonesialifestyle', 'sgfamily', 'singaporeblogs', 'malaysiaig', 'vascomalaysia', 'thaiblogs',
                  'fashionsg', 'boudoirsingapore', 'loveramalaysia', 'travel_the_philippines', 'aafsg', 'koreanfashionmalaysia',
                  'singaporeclozette', 'begmalaysia', 'malaysiatanahairk,', 'weddingphotographermalaysia', 'redcupthailand', 'thailandootd',
                  'thailandbloggers', 'indochinafashion', 'indiaootd', 'philippinesneakerhead', 'choicerish', 'ootdsg', 'ootdsingapore',
                  'butikmalaysia', 'instavscomalaysia', 'dressedinfayth', 'bboyworldmalaysia', 'philippinesvsco', 'igthailand', 'hkfashion',
                  'fashionindia', 'vscocamsg', 'magicjellysingapore', 'dontjudgechallengeindonesia', 'montblancsg', 'igersphilippines',
                  'hkigers', 'malaysianvsco', 'singaporean', 'pilipinasootdbasics', 'jahitpukalmalaysia', 'nationalgallerysg', 'jakartafashionweek',
                  'fashionthailand', 'koreanmakeup', 'indochinaclozette', 'hongkonggirls', 'wiwindia', 'tokyofashionweek', 'singaporepreweddingphotographer',
                  'bazaarphilippines', 'singaporecreatives', 'bazarmalaysia', 'louisvuittonphilippines', 'malaysiastyle', 'lifestylesingapore',
                  'indiashop', 'gf_philippines', 'japanesemodel', 'blogphilippines', 'vapemalaysia', 'Indonesiaoutfit', 'lifestylethai',
                  'gopromalaysiaofficial', 'ig_japan', 'beautysg', 'afasg2015', 'backpackingmalaysia', 'sgaccessories', 'instagramalaysia',
                  'fashionjapanese', 'malaysialifestyle', 'noisesingapore', 'al_hongkongsingapore2015', 'philippineswiw', 'blogmalaysia',
                  'gf_malaysia', 'singaporegirls', 'singaporecity', 'sgshop', 'apalagimalaysiamah,', 'malaysiawonderface', 'lofficielhommesthailand',
                  'furlamalaysia', 'bollywood', 'katespadephilippines', 'versaceperfumemalaysia', 'ilovemalaysia', 'idolgroup', 'malaysiangp',
                  'huntgramphilippines', 'wiwthailand', 'bapesg', 'delhiblogger', 'makeupartistmalaysia', 'stylemalaysian', 'gucciperfumesmalaysia',
                  'thaivsco', 'thailand_allshots', 'ootdhk', 'thailandshop', 'malaysiadistro', 'thaifashion', 'thaicuteboy', 'flipkart', 'posmalaysia',
                  'malaysianselfie', 'singaporethroughmycam', 'ilovesingapore', 'philippinesshop', 'indikah', 'chocoolatesg', 'instashopmalaysia',
                  'malaysiaboutique', 'indiaclozette', 'marcjacobsmalaysia', 'instamumbai', 'koreanbeautybloger', 'sgfashion', 'philippinesblogs',
                  'dubsmashmalaysian_', 'Indonesiablogshop', 'browniesg', 'singaporenight', 'walletmurahmalaysia', 'guccimalaysia',
                  'lifestylemalaysian', 'malaysiafoodie', 'fashionindochina', 'trustedsellermalaysia', 'thaishop', 'muaythaifamily', 'myootdphilippines',
                  'sgonlineshopping', 'japanwiw', 'malaysiamy', 'malaysianootd', 'missphilippines', 'sayajualrantaimalaysia',
                  'fashionphilippines', 'makeupthailand', 'cuticutimalaysia', 'malaysianproduct', 'theisland_philippines', 'igersthailand',
                  'preweddingsingapore', 'stylehongkong', 'michaelkorsthailand', 'jerseywarehousemalaysia', 'stylevietnam', 'vsco_malaysia',
                  'colorkillthailand', 'ootdmalaysian', 'philippinesmodel', 'loves_united_thailand', 'vscophilippines_', 'malaysiarepresent',
                  'igboutiquemalaysia', 'thailandlife', 'lovebonito', 'uljjangstyle', 'hkgirls', 'monarchsg', 'indiaig', 'instaid',
                  'fashionsingapore', 'lokalmalaysia', 'lifestylethailand', 'singaporelifestyle', 'muaythailife', 'lolascafesg', 'tokyofashion',
                  'singaporeinternationaljamboree', 'malaysianmakeupartist', 'bajukoreamalaysia', 'blogindia', 'ig_malaysia_', 'dunhillperfumemalaysia',
                  'wiwhongkong', 'thailandblogger', 'bajukorea', 'ootdphilippines_', 'amazingthailand', 'sghaze', 'japaneseig', 'thisissingapore',
                  'stylejapan', 'bestofsingapore', 'malaysiagirls', 'ig_singapore', 'malaysianshop', 'fashionmalaysia', 'Indonesiamodel',
                  'jomkurus1malaysia', 'sgfitness', 'singaporefashion', 'hkwiw', 'thailandfashion', 'bassguitar', 'hkvsco', 'singaporecakes',
                  'sgwedding', 'themalaysia_ig', 'hennamalaysia', 'japaneseshop', 'tshirtmalaysia', 'bundlemalaysia', 'sg', 'mdsootd',
                  'ulzzanggirl', 'lifestylejapan', 'vscohongkong', 'malaysianartist', 'montblancperfumemalaysia', 'thai', '30daysleftinthailand',
                  'instasg', 'thailandig', 'photographermalaysia', 'hongkongblogger', 'Indonesiablogger', 'halalsg', 'hkblogger', 'gottomovesg',
                  'visitmyigmalaysia', 'universalstudiosingapore', 'styleindochina', 'welovesingapore', 'wiwjapanese', 'thailandoutfit',
                  'bns_philippines', 'singaporephotographer', 'wovenlabelmalaysia', 'chroniclesindonesia', 'pelukismalaysia', 'sweaterhoodiemalaysia',
                  'cosmeticsthailand', 'MaxFactorIndonesia', 'vscocamphilippines', 'topdressmalaysia', 'supportlocalsg', 'instamalaysia',
                  'ig_malaysiabest', 'stylemalaysia', 'styleindonesia', 'clozetteambassador', 'sgbeauty', 'f21philipines', 'thefacethailand',
                  'wow_singapore', 'sginstashop', 'icu_malaysia', 'hongkongclozette', 'japanvsco', 'thailandmarket', 'goprophilippines',
                  'siamthai_ig', 'hkfood', 'explorethailand2015', 'ootdph', 'sgflea', 'thailand2015', 'peninsularmalaysiatrip', 'blogshopsg',
                  'fashionIndonesia', 'jubahmurahmalaysia', 'nightclub_singapore', 'singaporehijab', 'japanshop', 'skystylesgf', 'adayinthailand',
                  'overrunsphilippines', 'thaigirl', 'muamalaysia', 'onlyinmalaysia', 'kasutkoreamalaysia', 'sgselfie', 'wiwIndonesia',
                  'thailandvsco', 'igphilippined', 'shoppingsg', 'exploresingapore', 'hongkongoutfit', 'missmalaysiaworld2014', 'blogjapanese',
                  'pacorabannemalaysia', 'igshopmalaysiamurah', 'igphilippines', 'japaneseblogger', 'coffeemalaysia', 'simisaialsosg50',
                  'skatemalaysia', 'socialitysingapore', 'sgvsco', 'tv3malaysia', 'malaysiankraf', 'hkootd', 'singaporetraveldiariesbyhimani',
                  'singaporeblogshop', 'borongmalaysia', 'malaysianweddingphotographer', 'cdgphilippines', 'hermesmalaysia', 'pumamalaysia',
                  'iluvsg', 'japanlifestyle', 'malaysiangirls', 'versaceperfumemurahmalaysia', 'stylejapanese', 'fhmthailand',
                  'mystorysg', 'dontjudgechallengeasian', 'taiwanfashion', 'vietnammodel', 'gppmalaysia', 'japanblog', 'gshockmalaysia',
                  'fitnessmalaysia', 'catthailand', 'tokyostore', 'shoponlinephilippines', 'igsgfashion', 'hongkongig', 'clozetteph',
                  'muasingapore', 'matjoezmeetsg', 'babymalaysia', 'vscojapanese', 'stylehk', 'global_malaysia', 'inimalaysiakita', 'stylethai',
                  'jakartafashionweek2015', 'onlinesellerphilippines', 'quiksilvermalaysia', 'projectphotosg', 'singaporeonlineshop',
                  'makeupartistjakarta', 'sgloots', 'indikahasia', 'thaibloggers', 'folksingapore', 'fashionvietnam', 'sghalafoods', 'malaysianblogshop',
                  'presweetsingapore', 'tshirtmurahmalaysia', 'gopromalaysia', 'twinsmalaysia', 'japaneselifestyle', 'muaythaigirl', 'fashiontaiwan',
                  'vietnamstyle', 'sgfitnessmotivation', 'pencarianremaja', 'hkgirl', 'malaysian', 'styleIndonesia', 'taiwanstyle', 'japanoutfit',
                  'sg_le', 'japanesefashion', 'vscoshotphilippines', 'lamontetalesgoode', 'carousellsg', 'sgsocialenterprise', 'jammalaysia',
                  'sgsportshub', 'indialifestyle', 'malaysianclozette', 'ulzzangmakeup', 'singaporeairlines', 'jakartafashionweek2016',
                  'instashopmalaysiamurah', 'malaysiaboleh', 'iphonesamsungmurahmalaysia', 'mtnmalaysia', 'indiastyle', 'oicsingapore',
                  'navratriisgujarati', 'dubsmashmalaysia', 'indochinabloggers', 'hongkongstyle', 'sginstocks', 'thaiblogshop', 'lifestyleIndonesia',
                  'bloghk', 'sgstyle', 'singaporeblog', 'majalahremajaootd', 'sginstababes', 'hongkonglifestyle', 'bodycondressmalaysia', 'chokermalaysia',
                  'sghtattootuesday', 'vapesquadmalaysia', 'japanesestyle', 'thaiblogger', 'exsgcafes', 'streetsg', 'Indonesiagirls', 'ulzzangfashion',
                  'jualmurahmalaysia', 'hairclipmalaysia', 'igreviewmalaysia', 'fashionhk', 'kedaionlinemalaysia', 'philippinesgirls', 'instasingapore',
                  'malaysiablog', 'malaysianwiw', 'bagsphilippines', 'welovecleo', 'sgblogger', 'teamvccmalaysia', 'sgfood', 'choosephilippines',
                  'begmurahmalaysia', 'igers_singapore', 'thailandblogs', 'Indonesiaootd', 'muaythaifighter', 'singaporeblogger', 'icu_thailand',
                  'vapormalaysia', 'instagramsg', 'indochinaootd', 'Indonesiafashion', 'japanesewiw', 'backpackersmalaysia', 'hkoutfit',
                  'breadstreetkitchensg', 'indochinablogshop', 'cafehoppingsg', 'malaysiak,', 'onlineshopmalaysia', 'clozette', 'singaporedesigners',
                  'indodubsgram', 'fashionjapan', 'innershinesg', 'pacorabbaneperfumesmalaysia', 'gfmalaysia', 'malaysiaoutfit', 'malaysiandancer',
                  'beautifulmalaysia', 'sgbakery', 'hongkongootd', 'neocrewsmalaysia', 'igersmalaysian', 'designservicemalaysia', 'malaysiacypher',
                  'dressmurahmalaysia', 'kawaii', 'photographymalaysia', 'koreaastylee', 'philippinemade', 'Indonesiastyle', 'malaysiahottestbloggers',
                  'foodhuntmalaysia', 'wiwphilippines', 'commedesgarcon', 'thaiclozette', 'onlineshopphilippines', 'ocbcmalaysia', 'ipadphilippines',
                  'newbrandmalaysia', 'koreanfashion', 'tokyostyle', 'cafehopmalaysia', 'foodinkmalaysia', 'fossilmalaysia', 'singaporeoutfit',
                  'lookbooksg', 'malaysianblogger', 'japaneseoutfit', 'cafehoppingmalaysia', 'japanesebloggers', 'zaramalaysia', 'sharephilippines',
                  'philippinesbloggers', 'wow_philippines', 'fashionindonesia', 'hklifestyle', 'goproheromalaysia', 'koreastyle', 'bloghongkong', 'sgmodel',
                  'sgdaily', 'igindia', 'philippinesclozette', 'muaythai_sp', 'ihayogasingapore', 'instasg50', 'sexydressmalaysia', 'wms_philippines',
                  'discoversingapore', 'bagpackmalaysia', 'singaporewiw', 'ankara_sg', 'onlinestorephilippines', 'wiwindochina', 'itsmorefuninthephilippines',
                  'kasutmurahmalaysia', 'preweddingtripsingapore', 'ootdpinas', 'gujunpyo', 'eventsg', 'talui_sg2015', 'sayajualnecklacemalaysia',
                  'hijabistamalaysia', 'sgigers', 'hongkongbloggers', 'sg50', 'sgig', 'singaporeskyline', 'thaistyle', 'thailandgirls', 'gf_singapore',
                  'instaiklanmalaysia', 'sgheartmap', 'graphicdesignmalaysia', 'majalahremaja', 'victoriasecretmalaysia', 'malaysiablogshop',
                  'coachmalaysia', 'instashoot_malaysia', 'universitimalaysiaterenggan,', 'VSCOTaiwan', 'indochinagirls', 'vscophilippines',
                  'japaneseclozette', 'igersjp', 'thaiwiw', 'philippinesblogger', 'singaporeillustrators', 'shawlmurahmalaysia', 'loves_singapore',
                  'beautyproductmalaysia', 'malaysiasuperleague', 'malaysianfashion', 'kaneztokyo', 'uniqloginza', 'samsungcamerasg', 'igersmalaysiabest',
                  'philippinesfashion', 'skymalaysia', 'cosmeticthailand', 'singaporeootd', 'vietnamfashion', 'singaporelife', 'preorderthailand',
                  'wiwmalaysia', 'sglong', 'wiwtsg', 'philippinefashion', 'indochinaoutfit', 'asianmalegod', 'vscoIndonesia', 'Indonesiablog',
                  'styletaiwan', 'madeinmalaysia', 'sgphysiques', 'malaysiawiw', 'nikethailand', 'indochinalifestyle', 'jimmychooperfumemalaysia',
                  'sgmanicmonday', 'lookingforphilippines', 'indiawiw', 'blogjapan', 'igmalaysian', 'artmarketmalaysia', 'indochinamodel',
                  'malaysianig', 'igmalaysia_best', 'japanblogs', 'shoppingon9malaysia', 'thailandblogshop', 'thaiblog', 'belleinvietnam', 'blogIndonesia',
                  'atticasg', 'hongkongmodel', 'instagram_sg', 'malaysiabloggers', 'etudethailand', 'hkig', 'ulzzangstyle', 'freepostagemalaysia', 'yogasg',
                  'tissotmalaysia', 'fossilthailand', 'missmalaysia', 'catsmalaysia', 'instababe_malaysia', 'wearsg', 'ootdjapan', 'ootdindochina',
                  'love_malaysia', 'japangirls', 'sggirls', 'hmmalaysia', 'mdscollections', 'philippinesstyle', 'malaysiahijab', 'igersingapore',
                  'nuffnangsg', 'coachthailand', 'accessoriessg', 'audisg', 'ini_malaysian', 'ootdpilipinas', 'malaysianblog', 'indonesian', 'wiwsingapore',
                  'thaimodel', 'peeloffnailpolishmalaysia', 'ulzzangwannabe', 'CebuFashionBloggers', 'hongkongfashion', 'delhi', 'nailsg', 'styleindia',
                  'malaysianrapper', 'bagmalaysia', 'malaysiamodel', 'malaysiachristianyouthassosiation', 'indochinawiw', 'ighk', 'sgsales', 'styleph',
                  'japaneseblog', 'stylephilippines', 'sgfacades', 'inmalaysia', 'morefuninthephilippines', 'singaporeshop', 'malaysiashop', 'exploresg',
                  'preordermalaysia', 'tourismmalaysia', 'lifestylejapanese', 'sg_50', 'lifestyleindia', 'onlineshoppingmalaysia', 'delhifashionblogger',
                  'indiablog', 'hongkongwiw', 'sunsetsg', 'ootdphilippines', 'fashionmalaysian', 'hikingmalaysia', 'ootdindo', 'malaysia', 'streetstylesgf',
                  'kaftansingapore', 'thaishopping', 'instaeatmalaysia', 'igindochina', 'basicerphilippines', 'lookbookphilippines', 'wiwhk', 'singaporebrownies',
                  'katespademalaysia', 'selamatpagimalaysia', 'insta_thailand', 'malaysiafashion', 'modelindonesia', 'shoesphilippines', 'uljjangfashion',
                  'thaipeople', 'cebublogger', 'japanmodel', 'vscohk', 'cakesg', 'philippinesoutfit', 'hkblogs', 'indochinablogger', 'capturesingapore', 'hkclozette',
                  'indochinavsco', 'sgbased', 'malaysiatrulyasia', 'dressesphilippines', 'muajakarta', 'popupsg', 'igersmanila', 'matamatasg', 'hongkongblog',
                  'koreanmodel', 'boyfriendshirtmalaysia', 'tokyofashionweek2015', 'thailandwiw', 'ulzzangindonesia', 'igsg', 'sgfashionista', 'thailand',
                  'indiavsco', 'sgmalaybridal', 'sgsale', 'japaneseootd', 'blogmalaysian', 'instashootmalaysia', 'japanootd', 'topmanmalaysia',
                  'dubsmashmalaysian', 'htcmalaysia', 'sgbazaar', 'instantlyagelessmalaysia', 'thatsothailand', 'ootdmalaysia', 'djcdubsindo', 'clarkequaysg',
                  'styletokyo', 'sgselling', 'hongkongblogs', 'sgbabes', 'sgcakes', 'instamalaysian', 'lifestylephilippinesblog', 'craftclassmalaysia',
                  'singaporefood', 'hkstyle', 'sgkids', 'ilovephilippines', 'mymalaysia', 'eyesofthephilippines', 'msumalaysia', 'japanblogger', 'avonthailand',
                  'blackmarketmalaysia', 'missmalaysia2015', 'malaysianstyle', 'indiamodel', 'tdmsingapore', 'handbagmalaysia', 'instaphilippines', 'sgshopping',
                  'koreanstyle', 'ootdindia', 'prestigesg', 'hongkongvsco', 'koreanblogger', 'topmurahmalaysia', 'sweatshirtmalaysia', 'travel_philippines',
                  'igmalaysiabest', 'malaysian_ig', 'blousecantikmalaysia', 'coffeescrubmalaysia', 'singaporepreweddingpromo', 'WeAreCFB', 'muaythaigirls',
                  'wu_philippines', 'Phillippines', 'Indonesiawiw', 'gramminginsingapore', 'blogsingapore', 'vscomalaysian', 'learnthaiboxing', 'sweatermalaysiashop',
                  'jamtanganmalaysia', 'wovenlabelsingapore', 'malaysiaootd', 'singaporevsco', 'prewedjakarta', 'snsd', 'kasutreadystockmalaysia',
                  'igshopmurahmalaysia', 'peninsularmalaysia', 'indiaoutfit', 'indochinablogs', 'japanstyle', 'vscosg', 'selllovebonito', 'indiagirls',
                  'hkblogshop', 'louisvuittonthailand', 'instagrammalaysia', 'igbizmalaysia', 'shaandaar', 'fitmalaysia', 'Indonesiavsco', 'thailandblog',
                  'igmalaysia', 'igminimalaysia', 'vanelasg', 'malaysianmodel', 'hermessingapore', 'singaporewedding', 'loves_malaysia', 'graphicdesignermalaysia',
                  'pilipinasootd', 'igjapanese', 'browniebarphilippines', 'sgonlineshops', 'canonsg', 'anarchysg', 'thailifestyle', 'malaysianterbaik',
                  'ver22thailand', 'koreamodel', 'malaysiaphotographer', 'Indonesiaig', 'ulzzanggirls', 'japanesegirl', 'malaysiancafes', 'koreafashion',
                  'qsmalaysia', 'uljjang', 'sgootd', 'exploremalaysia', 'japanbloggers', 'sgblogshop', 'sportshoesmalaysia', 'mukapalaakongthai',
                  'vscothailand', 'pomademalaysia', 'matjoezinsg', 'sgevents', 'amalaysianphoto', 'malaysiaigers', 'Indonesiaclozette', 'shop_ootdsg',
                  'MalaysianGirl', 'topshopthailand', 'ulzzangindo', 'missworldmalaysia2014', 'hongkongshop', 'indochinablog', 'singaporebloggers', 'stylekorea',
                  'iger_malaysia', 'utusanmalaysia', 'singaporeshops', 'gaysingapore', 'exploresingaporecafes', 'gyarugirl', 'indiablogs', 'Indonesiashop',
                  'igIndonesia', 'fotografijalananmalaysia', 'igsingapore', 'fashiontokyo', 'backpack_singapore', 'sglocallife', 'malaysianmodels',
                  'cafemalaysia', 'indianfashionblogger',
                  'philippinesig', 'walletsphilippines', 'sgbesties', 'asianboy', 'makeupforeversg', 'wiwjapan', 'sgjewellery'],

    'asia_common': [u'philippinesfashion', u'philippinesstyle', u'philippineslifestyle',
                    u'fashionphilippines', u'stylephilippines', u'lifestylephilippinesblog', u'philippinesblogs',
                    u'philippinesblogger', u'philippinesbloggers', u'blogphilippines', u'ootdphilippines',
                    u'philippinesootd', u'philippinesclozette', u'philippinesmodel', u'philippinesshop',
                    u'philippinesblogshop', u'philippinesgirls', u'philippineswiw', u'wiwphilippines',
                    u'vscophilippines', u'philippinesoutfit', u'philippinesvsco', u'igphilippines', u'philippinesig',

                    u'singaporefashion', u'singaporestyle', u'singaporelifestyle', u'fashionsingapore',
                    u'stylesingapore', u'lifestylesingapore', u'singaporeblog', u'singaporeblogs', u'singaporeblogger',
                    u'singaporebloggers', u'blogsingapore', u'ootdsingapore', u'singaporeootd', u'singaporeclozette',
                    u'singaporemodel', u'SG',
                    u'singaporeshop', u'singaporeblogshop', u'singaporegirls', u'singaporewiw', u'wiwsingapore',
                    u'vscosingapore', u'singaporeoutfit', u'singaporevsco', u'igsingapore', u'singaporeig',
                    u'hongkongfashion', u'hongkongstyle', u'hongkonglifestyle', u'fashionhongkong', u'stylehongkong',
                    u'lifestylehongkong', u'hongkongblog', u'hongkongblogs', u'hongkongblogger', u'hongkongbloggers',
                    u'bloghongkong', u'ootdhongkong', u'hongkongootd', u'hongkongclozette', u'hongkongmodel',
                    u'hongkongshop', u'hongkongblogshop', u'hongkonggirls', u'hongkongwiw', u'wiwhongkong',
                    u'vscohongkong', u'hongkongoutfit', u'hongkongvsco', u'ighongkong', u'hongkongig',
                    u'japanfashion', u'japanstyle', u'japanlifestyle', u'fashionjapan', u'stylejapan',
                    u'lifestylejapan', u'japanblog', u'japanblogs', u'japanblogger', u'japanbloggers', u'blogjapan',
                    u'ootdjapan',
                    u'japanootd', u'japanclozette', u'japanmodel', u'japanshop', u'japanblogshop', u'japangirls',
                    u'japanwiw', u'wiwjapan', u'vscojapan', u'japanoutfit', u'japanvsco', u'igjapan', u'japanig',
                    u'japanesefashion', u'japanesestyle', u'japaneselifestyle', u'fashionjapanese',
                    u'stylejapanese', u'lifestylejapanese', u'japaneseblog', u'japaneseblogs', u'japaneseblogger',
                    u'japanesebloggers', u'blogjapanese', u'ootdjapanese', u'japaneseootd', u'japaneseclozette',
                    u'japanesemodel', u'japaneseshop', u'japaneseblogshop', u'japanesegirls', u'japanesewiw',
                    u'wiwjapanese', u'vscojapanese', u'japaneseoutfit', u'japanesevsco', u'igjapanese', u'japaneseig',
                    u'indiafashion', u'indiastyle', u'indialifestyle', u'fashionindia', u'styleindia',
                    u'lifestyleindia', u'indiablog', u'indiablogs', u'indiablogger', u'indiabloggers', u'blogindia',
                    u'ootdindia', u'indiaootd', u'indiaclozette', u'indiamodel', u'indiashop', u'indiablogshop',
                    u'indiagirls', u'indiawiw', u'wiwindia', u'vscoindia', u'indiaoutfit', u'indiavsco', u'igindia',
                    u'indiaig', u'desifashion', u'desistyle', u'desilifestyle', u'fashiondesi', u'styledesi',
                    u'lifestyledesi', u'desiblog', u'desiblogs', u'desiblogger', u'desibloggers', u'blogdesi',
                    u'ootddesi', u'desiootd', u'desiclozette', u'desimodel', u'desishop', u'desiblogshop', u'desigirls',
                    u'desiwiw', u'wiw', u'vsco', u'Indonesiaoutfit', u'Indonesiavsco', u'vscoIndonesia', u'igIndonesia',
                    u'Indonesiaig', u'Indonesiafashion', u'Indonesiastyle', u'Indonesialifestyle', u'fashionIndonesia',
                    u'styleIndonesia', u'lifestyleIndonesia', u'Indonesiablog', u'Indonesiablogs', u'Indonesiablogger',
                    u'Indonesiabloggers', u'blogIndonesia', u'ootdIndonesia', u'Indonesiaootd', u'Indonesiaclozette',
                    u'Indonesiamodel', u'Indonesiashop', u'Indonesiablogshop', u'Indonesiagirls', u'Indonesiawiw',
                    u'wiwIndonesia', u'indochina', u'indochinafashion', u'indochinastyle', u'indochinalifestyle',
                    u'fashionindochina', u'styleindochina', u'lifestyleindochina', u'indochinablog', u'indochinablogs',
                    u'indochinablogger', u'indochinabloggers', u'blogindochina', u'ootdindochina', u'indochinaootd',
                    u'indochinaclozette', u'indochinamodel', u'indochinashop', u'indochinablogshop', u'indochinagirls',
                    u'indochinawiw', u'wiwindochina', u'vscoindochina', u'indochinaoutfit', u'indochinavsco',
                    u'igindochina', u'indochinaig', u'malaysiafashion', u'malaysiastyle',
                    u'malaysialifestyle', u'fashionmalaysia', u'stylemalaysia', u'lifestylemalaysia', u'malaysiablog',
                    u'malaysiablogs', u'malaysiablogger', u'malaysiabloggers', u'blogmalaysia', u'ootdmalaysia',
                    u'malaysiaootd', u'malaysiaclozette', u'malaysiamodel', u'malaysiashop', u'malaysiablogshop',
                    u'malaysiagirls', u'malaysiawiw', u'wiwmalaysia', u'vscomalaysia', u'malaysiaoutfit',
                    u'malaysiavsco', u'igmalaysia', u'malaysiaig', u'malaysianfashion', u'malaysianstyle',
                    u'malaysianlifestyle', u'fashionmalaysian', u'stylemalaysian', u'lifestylemalaysian',
                    u'malaysianblog', u'malaysianblogs', u'malaysianblogger', u'malaysianbloggers', u'blogmalaysian',
                    u'ootdmalaysian', u'malaysianootd', u'malaysianclozette', u'malaysianmodel', u'malaysianshop',
                    u'malaysianblogshop', u'malaysiangirls', u'malaysianwiw', u'wiwmalaysian', u'vscomalaysian',
                    u'malaysianoutfit', u'malaysianvsco', u'igmalaysian', u'malaysianig', u'thaifashion',
                    u'thaistyle', u'thailifestyle', u'fashionthai', u'stylethai', u'lifestylethai', u'thaiblog',
                    u'thaiblogs', u'thaiblogger', u'thaibloggers', u'blogthai', u'ootdthai', u'thaiootd',
                    u'thaiclozette', u'thaimodel', u'thaishop', u'thaiblogshop', u'thaigirls', u'thaiwiw',
                    u'thailandoutfit',
                    u'thailandvsco', u'vscothailand', u'igthailand', u'thailandig', u'thailandfashion',
                    u'thailandstyle', u'thailandlifestyle', u'fashionthailand', u'stylethailand', u'lifestylethailand',
                    u'thailandblog',
                    u'thailandblogs', u'thailandblogger', u'thailandbloggers', u'blogthailand', u'ootdthailand',
                    u'thailandootd', u'thailandclozette', u'thailandmodel', u'thailandshop', u'thailandblogshop',
                    u'thailandgirls', u'thailandwiw', u'wiwthailand', u'Chinafashion', u'Chinastyle', u'Chinalifestyle', u'fashionChina',
                    u'styleChina', u'lifestyleChina', u'Chinablog', u'Chinablogs', u'Chinablogger', u'Chinabloggers',
                    u'blogChina', u'ootdChina', u'Chinaootd', u'Chinaclozette', u'Chinamodel', u'Chinashop',
                    u'Chinablogshop', u'Chinagirls', u'Chinawiw', u'wiwChina', u'vscoChina', u'Chinaoutfit',
                    u'Chinavsco', u'igChina', u'Chinaig', u'chinese', u'chinesefashion', u'chinesestyle',
                    u'chineselifestyle',
                    u'fashionchinese', u'stylechinese', u'lifestylechinese', u'chineseblog', u'chineseblogs',
                    u'chineseblogger', u'chinesebloggers', u'blogchinese', u'ootdchinese', u'chineseootd',
                    u'chineseclozette', u'chinesemodel', u'chineseshop', u'chineseblogshop', u'chinesegirls',
                    u'chinesewiw', u'wiwchinese', u'vscochinese', u'chineseoutfit', u'chinesevsco', u'igchinese',
                    u'chineseig', u'Tokyofashion', u'Tokyostyle', u'Tokyolifestyle', u'fashionTokyo',
                    u'styleTokyo', u'lifestyleTokyo', u'Tokyoblog', u'Tokyoblogs', u'Tokyoblogger', u'Tokyobloggers',
                    u'blogTokyo', u'ootdTokyo', u'Tokyoootd', u'Tokyoclozette', u'Tokyomodel', u'Tokyoshop',
                    u'Tokyoblogshop', u'Tokyogirls', u'Tokyowiw', u'wiwTokyo', u'vscoTokyo', u'Tokyooutfit',
                    u'Tokyovsco', u'igTokyo', u'Tokyoig', u'Asiafashion', u'Asiastyle', u'Asialifestyle',
                    u'fashionAsia',
                    u'styleAsia', u'lifestyleAsia', u'Asiablog', u'Asiablogs', u'Asiablogger', u'Asiabloggers',
                    u'blogAsia', u'ootdAsia', u'Asiaootd', u'Asiaclozette', u'Asiamodel', u'Asiashop', u'Asiablogshop',
                    u'Asiagirls', u'Asiawiw', u'Asianoutfit', u'Asianvsco', u'vscoAsian', u'igAsian', u'Asianig',
                    u'Asianfashion', u'Asianstyle', u'Asianlifestyle', u'fashionAsian', u'styleAsian',
                    u'lifestyleAsian', u'Asianblog', u'Asianblogs', u'Asianblogger', u'Asianbloggers', u'blogAsian',
                    u'ootdAsian',
                    u'Asianootd', u'Asianclozette', u'Asianmodel', u'Asianshop', u'Asianblogshop', u'Asiangirls',
                    u'Asianwiw', u'wiwAsian',  u'koreanfashion', u'koreanstyle', u'koreanlifestyle',
                    u'fashionkorean', u'stylekorean', u'lifestylekorean', u'koreanblog', u'koreanblogs',
                    u'koreanblogger', u'koreanbloggers', u'blogkorean', u'ootdkorean', u'koreanootd', u'koreanclozette',
                    u'koreanmodel',
                    u'koreanshop', u'koreanblogshop', u'koreangirls', u'koreanwiw', u'wiwkorean', u'vscokorean',
                    u'koreanoutfit', u'koreanvsco', u'igkorean', u'koreanig', u'southkorean', u'southkoreanfashion',
                    u'southkoreanstyle', u'southkoreanlifestyle', u'fashionsouthkorean', u'stylesouthkorean',
                    u'lifestylesouthkoreanblog', u'southkoreanblogs', u'southkoreanblogger', u'southkoreanbloggers',
                    u'blogsouthkorean', u'ootdsouthkorean', u'southkoreanootd', u'southkoreanclozette',
                    u'southkoreanmodel', u'southkoreanshop', u'southkoreanblogshop', u'southkoreangirls',
                    u'southkoreanwiw', u'wiwsouthkorean', u'vscosouthkorean', u'southkoreanoutfit', u'southkoreanvsco',
                    u'igsouthkorean', u'southkoreanig', u'koreafashion', u'koreastyle', u'korealifestyle',
                    u'fashionkorea', u'stylekorea', u'lifestylekorea', u'koreablog', u'koreablogs', u'koreablogger',
                    u'koreabloggers', u'blogkorea', u'ootdkorea', u'koreaootd', u'koreaclozette', u'koreamodel',
                    u'koreashop', u'koreablogshop', u'koreagirls', u'koreawiw', u'wiwkorea', u'vscokorea',
                    u'koreaoutfit', u'koreavsco', u'igkorea', u'koreaig', u'southkorea', u'southkoreafashion',
                    u'southkoreastyle',
                    u'southkorealifestyle', u'fashionsouthkorea', u'stylesouthkorea', u'lifestylesouthkoreablog',
                    u'southkoreablogs', u'southkoreablogger', u'southkoreabloggers', u'blogsouthkorea',
                    u'ootdsouthkorea', u'southkoreaootd', u'southkoreaclozette', u'southkoreamodel', u'southkoreashop',
                    u'southkoreablogshop', u'southkoreagirls', u'southkoreawiw', u'wiwsouthkorea', u'vscosouthkorea',
                    u'southkoreaoutfit', u'southkoreavsco', u'igsouthkorea', u'southkoreaig',
                    u'Bangkokfashion', u'Bangkokstyle', u'Bangkoklifestyle', u'fashionBangkok', u'styleBangkok',
                    u'lifestyleBangkok', u'Bangkokblog', u'Bangkokblogs', u'Bangkokblogger', u'Bangkokbloggers',
                    u'blogBangkok', u'ootdBangkok', u'Bangkokootd', u'Bangkokclozette', u'Bangkokmodel', u'Bangkokshop',
                    u'Bangkokblogshop', u'Bangkokgirls', u'Bangkokwiw', u'wiwBangkok', u'vscoBangkok', u'Bangkokoutfit',
                    u'Bangkokvsco', u'igBangkok', u'Bangkokig', u'manilafashion', u'manilastyle',
                    u'manilalifestyle', u'fashionmanila', u'stylemanila', u'lifestylemanila', u'manilablog',
                    u'manilablogs', u'manilablogger', u'manilabloggers', u'blogmanila', u'ootdmanila', u'manilaootd',
                    u'manilaclozette', u'manilamodel', u'manilashop', u'manilablogshop', u'manilagirls', u'manilawiw',
                    u'wiwmanila', u'vscomanila', u'manilaoutfit', u'manilavsco', u'igmanila', u'manilaig',
                    u'jakartafashion', u'jakartastyle', u'jakartalifestyle', u'fashionjakarta', u'stylejakarta',
                    u'lifestylejakarta', u'jakartablog', u'jakartablogs', u'jakartablogger', u'jakartabloggers',
                    u'blogjakarta', u'ootdjakarta', u'jakartaootd', u'jakartaclozette', u'jakartamodel', u'jakartashop',
                    u'jakartablogshop', u'jakartagirls', u'jakartawiw', u'wiwjakarta', u'vscojakarta', u'jakartaoutfit',
                    u'jakartavsco', u'igjakarta', u'jakartaig', u'hochiminh', u'hochiminhfashion', u'hochiminhstyle',
                    u'hochiminhlifestyle', u'fashionhochiminh', u'stylehochiminh', u'lifestylehochiminh',
                    u'hochiminhblog', u'hochiminhblogs', u'hochiminhblogger', u'hochiminhbloggers', u'bloghochiminh',
                    u'ootdhochiminh', u'hochiminhootd', u'hochiminhclozette', u'hochiminhmodel', u'hochiminhshop',
                    u'hochiminhblogshop', u'hochiminhgirls', u'hochiminhwiw', u'wiwhochiminh', u'vscohochiminh',
                    u'hochiminhoutfit', u'hochiminhvsco', u'ighochiminh', u'hochiminhig', u'hanoifashion',
                    u'hanoistyle', u'hanoilifestyle', u'fashionhanoi', u'stylehanoi', u'lifestylehanoi', u'hanoiblog',
                    u'hanoiblogs', u'hanoiblogger', u'hanoibloggers', u'bloghanoi', u'ootdhanoi', u'hanoiootd',
                    u'hanoiclozette', u'hanoimodel', u'hanoishop', u'hanoiblogshop', u'hanoigirls', u'hanoiwiw',
                    u'wiwhanoi', u'vscohanoi', u'hanoioutfit', u'hanoivsco', u'ighanoi', u'hanoiig', u'makatioutfit',
                    u'makativsco', u'vscomakati', u'igmakati', u'makatiig', u'makatifashion', u'makatistyle',
                    u'makatilifestyle', u'fashionmakati', u'stylemakati', u'lifestylemakati', u'makatiblog',
                    u'makatiblogs', u'makatiblogger', u'makatibloggers', u'blogmakati', u'ootdmakati', u'makatiootd',
                    u'makaticlozette', u'makatimodel', u'makatishop', u'makatiblogshop', u'makatigirls', u'makatiwiw',
                    u'wiwmakati', u'danangfashion', u'danangstyle', u'dananglifestyle', u'fashiondanang',
                    u'styledanang', u'lifestyledanang', u'danangblog', u'danangblogs', u'danangblogger',
                    u'danangbloggers', u'blogdanang', u'ootddanang', u'danangootd', u'danangclozette', u'danangmodel',
                    u'danangshop', u'danangblogshop', u'dananggirls', u'danangwiw', u'wiwdanang', u'vscodanang',
                    u'danangoutfit', u'danangvsco', u'igdanang', u'danangig', u'malaccafashion',
                    u'malaccastyle', u'malaccalifestyle', u'fashionmalacca', u'stylemalacca', u'lifestylemalacca',
                    u'malaccablog', u'malaccablogs', u'malaccablogger', u'malaccabloggers', u'blogmalacca',
                    u'ootdmalacca', u'malaccaootd', u'malaccaclozette', u'malaccamodel', u'malaccashop',
                    u'malaccablogshop', u'malaccagirls', u'malaccawiw', u'wiwmalacca', u'vscomalacca', u'malaccaoutfit',
                    u'malaccavsco', u'igmalacca', u'malaccaig', u'hkfashion', u'hkstyle', u'hklifestyle',
                    u'fashionhk', u'stylehk', u'lifestylehk', u'hkblog', u'hkblogs', u'hkblogger', u'hkbloggers',
                    u'bloghk', u'ootdhk', u'hkootd', u'hkclozette', u'hkmodel', u'hkshop', u'hkblogshop', u'hkgirls',
                    u'hkwiw', u'wiwhk', u'vscohk', u'hkoutfit', u'hkvsco', u'ighk', u'hkig', u'sgfashion', u'sgstyle',
                    u'sglifestyle', u'fashionsg', u'stylesg', u'lifestylesg', u'sgblog', u'sgblogs', u'sgblogger',
                    u'sgbloggers', u'blogsg', u'ootdsg', u'sgootd', u'sgclozette', u'sgmodel', u'sgshop', u'sgblogshop',
                    u'sggirls', u'sgwiw', u'wiwsg', u'vscosg', u'sgoutfit', u'sgvsco', u'igsg', u'sgig', u'jpfashion',
                    u'jpstyle', u'jplifestyle', u'fashionjp', u'stylejp', u'lifestylejp', u'jpblog', u'jpblogs',
                    u'jpblogger', u'jpbloggers', u'blogjp', u'ootdjp', u'jpootd', u'jpclozette', u'jpmodel', u'jpshop',
                    u'jpblogshop', u'jpgirls', u'jpwiw', u'wiwjp', u'vscojp', u'jpoutfit', u'jpvscovscojpigjpjpig',
                    'ronherman',],

    'asia_singapore': [u'sgmodel', u'wiwtsg', u'innershinesg', u'singaporeblogger', u'sgigstyle', u'vscocamsg',
                       u'zalorasg', u'blogshopsg', u'fashionsg', u'igsgfashion', u'lookingforsg', u'ootdsg', u'sg50',
                       u'sgblogger', u'sgfashion', u'sgflea', u'sgfleamarket', u'sgig', u'sgigstyle', u'sginstashop',
                       u'sgootd', u'sgsales', u'sgselling', u'sgshop', u'sgstyle', u'singaporedesigners',
                       u'singaporeshops', u'wearsg', u'sgselling', u'sgsales', u'sglookbook', u'lookbooksg', ],

    'asia_philipines': [u'styleph', u'pilipinasootd', u'stylebloggerph', u'pilipinasootd', u'cebublogger',
                        u'stylebloggerph', u'pilipinasootd', u'pilipinasootd', u'ootdpilipinas',
                        u'pilipinasootdbasics', u'igersmanila', u'ootdph', u'ootdpinas', u'vscopinas',
                        u'vscophilippines', ],

    'asia_vietnam': [u'belleinvietnam', u'vietnamfashion', u'vietnamstyle', u'fashionvietnam', u'stylevietnam',
                     u'vietnammodel', ],

    'asia_md': [u'mdsootd', u'mdscollections', ],

    'asia_brands': [u'clozetteambassador', u'clozette', u'clozettedaily', u'faythlabel', u'lovebonito',
                    u'selllovebonito', u'stylexstyle', u'tuullathelabel', u'welovecleo', u'faythlabel',
                    u'dressedinfayth', u'wakdoyok', u'clozetteph', u'kaneztokyo', ],

    'asia_misc': [u'asiangirl', u'tclootd', u'snsd', u'ulzzang', u'gyarugirl', u'bajukorea',  u'idolgroup',
                  u'ulzzangfashion', u'ulzzanggirls', u'uljjangfashion', u'uljjang', u'uljjangboy', u'uljjangstyle',
                  u'ulzzangstyle', u'ulzzangwannabe', u'ulzzangindonesia', u'ulzzangindo', u'indikah', ],

    'asia_indonesia': [u'MaxFactorIndonesia', u'BloggerIndonesia', u'styleindonesia', u'fashionindonesia',
                       u'pakaianimport', u'ootdindo', u'indikahasia', ],

    'asia_korea': [u'koreanfashion', u'koreanstyle', u'stylekorea', u'fashionkorea', u'koreastyle', u'koreafashion',
                   u'koreanmodel', u'koreamodel', u'stylekorea', u'koreaastylee', u'koreanboy', ],

    'asia_malaysia': [u'MalaysianGirl', u'malaysian', u'chinesemalaysian', u'malaysianchinese', u'fashionmalaysia',
                      ],

    'asia_thailand': [u'fashionthailand', u'stylethailand', u'thailandfashion', u'thailandstyle', ],

    'asia_hongkong': [u'fashionhongkong',  u'stylehongkong', u'hongkongfashion', u'hongkongstyle',
                      u'hongkongblogger', u'hongkongblog', ],

    'asia_taiwan': [u'VSCOTaiwan', u'taiwanstyle', u'taiwanfashion', u'styletaiwan', u'fashiontaiwan', ],

    'asia_japan': [u'tokyofashion', u'tokyofashionweek2015', u'tokyostyle', u'japanesegirl',
                   u'tokyofashionweek', u'tokyostore', u'bangkok', u'styletokyo', u'fashiontokyo',
                   u'stylejapan', u'fashionjapan', u'japanstyle', u'japanfashion', u'japanesefashion',
                   u'japanesestyle', ],

}

old_influencer_keywords = ['snapchat', 'collabora', 'sponsorship', 'advertise', 'youtube',
                       'youtu.be', 'blogger', 'vlogger', 'blogging', 'my blog', 'blog:', 'mommy', 'stylist',
                       'artist', 'blogspot', "i'm ", 'i like', 'enthusiast', 'traveler', 'traveller',
                       'foodie', 'dreamer', 'photographer', 'student', 'designer ', 'designer.', 'designer/', 'dayre.me', 'liketk.it', 'liketoknow', 'rstyle',
                       'youtubeuse', 'bloggeuse', 'instagrameuse', 'influencer', 'adventurer', 'blogging', 'model', 'ambassador',
                       'singer', 'actress ', 'actress.', 'actress ', 'actress/', 'actor ', ' actor', 'actor.', 'actor/', 'musician', 'freelancer', 'rapper', 'cosplayer', 'gamer',
                       'hairstylist', 'entrepreneur', 'wanderluster', 'writer', 'author', 'illustrator', 'sculptor',
                       'wife', 'cofonder', 'co-founder', 'founder', 'adventure', 'presenter', ' mama', 'singing',
                       'New outfit post', 'New on the blog', 'on the blog today', 'fashion blogger', 'lifestyle blogger',
                        'beauty blogger', 'on my blog', 'music, food, beauty', 'fashion, beauty, lifestyle',
                        'fashion, lifestyle, travel', 'fashion, travel, lifestyle', 'fashion, food, travel',
                        'music food beauty', 'fashion beauty lifestyle', 'fashion lifestyle travel', 'fashion travel lifestyle',
                        'fashion food travel', 'My youtube channel', 'Wechat', "hi i'm", 'hi i am', 'Hi, I am',
                        "Hi, I'm", 'living in', 'my style', 'represented by', "I'm a", 'I am a', 'mom of', 'my family',
                        'my hubs', 'my dog', 'my cat', 'my kids', 'my daughter', 'my son', 'my daughters', 'my sons',
                        'Canon 700D', 'Taurus', 'Gemini', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn',
                        'Aquarius', 'Pisces', 'Entrepreneur', 'cofounder', 'Videographer', 'STORYTELLER', 'are mine',
                        'Outfit Of The Day', 'Streetstyle', 'tumblr', 'married', 'trainer', 'sponsorship', 'periscope',
                        'canon 700D']

influencer_keywords = ['influencer', 'blogger', 'Wechat', 'Videographer', 'STORYTELLER', 'Streetstyle', 'married',
                       'trainer', 'Sponsorship', 'singing', 'wife', 'Taurus', 'Gemini', 'Virgo', 'Libra', 'Scorpio',
                       'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces', 'photographer', 'singer', 'actress',
                       'musician', 'freelancer', 'rapper', 'singer', 'cosplayer', 'Hairstylist', 'Entrepreneur',
                       'student', 'wanderluster', 'writer', 'author', 'illustrator', 'sculptor', 'cofounder',
                       'co-founder', 'founder', 'presenter', 'Gymnast', 'Decorator', 'Entrepreneur',
                       'traveler', 'artist', 'model', 'actor', 'gamer', 'adventurer', 'stylist', 'specialist',
                       'consultant', 'Editor', 'traveller', 'teacher', 'eater', 'doer', 'enthusiast', 'addict',
                       'aholic', 'Humanitarian', 'Advocate', 'mom', 'mum', 'mama', 'housemate', 'instructor',
                       'vlogger', 'blogging', 'my blog', 'blog:', 'mommy', 'foodie', 'dreamer', 'youtuber',
                       'liketk.it', 'liketoknow', 'rstyle', 'phototaker', 'styler', 'hubby', 'my', 'lover', 'creator']

influencer_phrases = ['New outfit post', 'New on the blog', 'on the blog today', 'fashion blogger', 'lifestyle blogger',
                      'beauty blogger', 'on my blog', 'music, food, beauty', 'fashion, beauty, lifestyle',
                      'fashion, lifestyle, travel', 'fashion, travel, lifestyle', 'fashion, food, travel',
                      'music food beauty', 'fashion beauty lifestyle', 'fashion lifestyle travel', 'fashion travel lifestyle',
                      'fashion food travel', 'My youtube channel', 'Youtube Channal', 'are mine', 'Outfit Of The Day',
                      'Canon 700D', "hi i'm", 'hi i am', 'Hi, I am',
                      "Hi, I'm", 'living in', 'my style', 'represented by', "I'm a", 'I am a', 'mom of', 'my family',
                      'my hubs', 'my dog', 'my cat', 'my kids', 'my daughter', 'my son', 'my daughters', 'my sons',
                      'makeup artist', 'make-up artist', 'make up artist', 'my family', 'I write', 'I make', 'I draw',
                      'I photo', 'I love', 'I like', 'I travel', 'I blog', 'I want', 'was born', 'I was not',
                      'born in', 'visual diary', 'fashion diary', 'beauty diary', 'makeup diary', 'make-up diary',
                      'food, fashion &', 'fashion, food', 'fashion, lifestyle', 'fashion, beauty', 'lifestyle, travel',
                      'lifestyle, fashion', 'current location', 'food & fashion', 'fashion & food', 'travel & fashion',
                      'fashion & travel', 'fashion & lifestyle', 'lifestyle & fashion', 'raised in', 'email me',
                      'blogspot', 'rstyle', 'broadcaster', 'contact me', 'by me', 'for me']


brand_keywords = ['broadcast station', 'premier designers', '100% import', 'Paid Promote Line',
                  'Pop-Up Shop', 'Customer care', 'PLEASE READ SHOPS', 'please read policies', 'PLACING AN ORDER', 'PAYPAL ONLY',
                  'OPEN 24/7', 'Worldwide Shipping', 'world wide shipping', 'All orders', 'shipped Express', 'Shop our Insta',
                  'Weekend Slow Respond', 'reseller', 'BOUTIQUE SUPPLIER', 'BEST PRICE', 'Manufactured with love',
                  'based boutique', 'amazing prices', 'best price', 'discounted price', 'discount variety', 'shipped worldwide',
                  'shipped world wide', 'Shop online', 'Retail store', 'A Local Brand', 'Jakarta Women', "Jakarta Women's",
                  'price :', 'ready-to-wear', 'menswear boutique', 'made by select', 'FIRSTHAND', 'online shopping', 'onlineshopping',
                  'Regist :', 'shopping site', 'to show us your style',

                  'BBM: ', 'SMS:', 'BBM :', 'SMS :', '(GROSIR)', '(ECER)',
                  'BB pin : ', 'bb pin:', 'Sold=delete', 'LINE ORDER', 'Line Owner', 'WA : ', 'JAKARTA FAST ', 'RESPON ORDER',
                  'first pay', 'NO REFUND', 'refund', 'JNE from ', 'only WA', 'WEEKEND OFF', 'makeupbranded', 'READY STOCK',
                  'ORIGINAL JAKARTA', 'dropship', '100% ORIGINAL', 'International shipments', '& cod', 'and cod', 'paypal', 'Jrs: ',
                  '2days reservation', 'reservation only', '1st HAND SUPPLIER ', 'Invite BBM', 'ORDER VIA',  'WORLDWIDE ONLINE',
                  'Pin bb',

                  'READY STOCK', 'Shop Indonesia', 'shop india', 'shop singapore', 'shop thailand', 'shop taiwan',
                  'shop philippines', 'shop japan', 'online store', 'same day', 'that carries ', 'topshop', 'shop@',

                  'itunes.apple',
                  'sale!', 'ship worldwide', 'ships worldwide', 'ship world wide', 'ships world wide', 'ship internationally',
                  'ships internationally', 'worldwide delivery', 'shipping', 'order:', 'order by', 'bigcartel.com', 'showroom',
                  'community', 'order online', 'orderform', 'order form', 'in-store', 'in store', '10% off', '20% off', '25% off',
                  '10%off', '20%off', '25%off', 'buy online', 'use hashtag', 'share your', 'limited time', 'limitedtime', 'cloud-based',
                  'web development', 'wholesale',


                  'sold = delete','Airlines','tourism','designers','designer brand',
                  'Phone Orders','shop our profile','shop our link','shop the link','shop the profile','7am - 3pm','a chance to win',
                  'affordable prices','available now','available online','beauty retailer','Boutique Shop','Clinique','delivery',"Don't forget to #",
                  'email us','Emporium','fashion event','fashion house','Fashion Labels','feature your look','Flagship Store',
                  'footwear brand','free samples','instashop','international brands','Kardashian','like2b.uy','limited edition',
                  'Limited Edition','Limited Edition Collection','Log on now','low prices','lowest prices','luxury fashion label',
                  'Made in','Megamall','Monday - Fri ','new. arrivals', 'new arrivals', 'offices in','Open for all-day','Please call','purchase online',
                  'reservations',' road ','shop at','Shop Beauty Online','shop below','shop from Insta','shop insta','shop it','shop now',
                  'Shop now','shop our feed','Shop Our Insta','shop the collection','shop the page','skincare brand','social network',
                  'stockist','Store locations','straight from our feed','Sun-Weds','Tag photos','to be featured','to get featured','tourism',
                  'tweet us','visit us at','7 days','Available in over','avenue','fashion retailer','gives you','grab them','insta shop',
                  'kmart','shoe brand','Shop Instagram','Tag videos','Th-Sat','All shops', 'sold = delete', 'fashion label',
                  '24 Hours', 'send from', 'Authentic Product', 'from Factory', '2-3 weeks', 'Shopping Mall', 'shoe retailer',
                  'cosmetics retailer', 'cosmetic retailer', 'best value', 'order through', 'open all day', 'CUSTOM ORDERS',
                  '(HABIS) = DELETE', 'Habis = delete', 'habis=delete', 'shipping internationally',
                  ' ships', 'supermarket', 'shop@']


# kept here for now so that we can test how many are found with these only
questionable_brand_keywords = ['customade', 'custom made', 'made by', 'accessories', 'premium', 'sales', 'we are',
                               'restaurant', 'management', 'boutique', 'handmade', 'store', 'ships', 'handcraft', 'shop', 'discount', 'itunes.apple',
                  'submit', 'follow us', 'sale!', 'ship worldwide', 'ship internationally', 'made in',
                  'worldwide delivery', 'ship world wide', 'shipping', 'order:', 'sell', 'order by', 'bigcartel.com',
                  'showroom', 'community', 'order online', 'orderform', 'order form', 'in-store', 'in store',
                  '10% off', '20% off', '25% off', '10%off', '20%off', '25%off', 'buy online', 'we are', 'use hashtag',
                  'restaurant', 'share your', 'limited time', 'platform', 'cloud-based',
                  'web development', 'wholesale',]

# The phrases may match as a sub-phrase of something longer but it's ok because these are very strong indicators.
locations_phrases = {
    'singapore': ['singapore', 'toa payoh', 'Ang Mo Kio', 'Choa Chu Kang',  'Tampines',  'bukit batok',
                  'lim chu kang',
                  'paya lebar', 'pasir ris',  ],
    'thailand': ['thailand', 'bangkok', 'Nonthaburi', 'Nakhon Ratchasima', ' Thai', 'thai '],
    'malaysia': ['malaysia', 'Malaysian', 'kaula lumpur', 'kaulalumpur', 'kaula lumpar', 'Johor Bahru', 'Shah Alam',
                 'Petaling Jaya', 'Kota Bharu', 'Kota Kinabalu', 'Kuala Terengganu', 'Malacca City',
                 'Seberang Perai', 'Subang Jaya', 'Shah Alam', 'Petaling Jaya',
                 'Johor Bahru Tengah', 'Johor Bahru', 'Malacca City',   'Ampang Jaya', 'Kota Kinabalu',
                 'Sungai Petani',  'Alor Setar', 'Kuala Terengganu', 'Kota Bharu',
                  'Kuala Langat', 'Kubang Pasu',
                 'Batu Pahat',  'Kuala Selangor', 'Lahad Datu', 'Hulu Selangor',
                 'Kinabatangan', 'Pasir Mas', 'Alor Gajah',  'Kuching North',
                 'Kuching South'],
    'indonesia': ['indonesia', 'jakarta', 'Surabaya', 'Bandung', 'Bekasi', 'Tangerang', 'Semarang', 'Palembang', 'Makassar', 'indonesian'],
    'philippines': ['philippines', 'philippine', 'phillipines', 'manila', 'Quezon City', 'Caloocan', 'Davao City', 'Cebu', 'Zamboanga', 'Filipino', 'filipina', 'pilipina', 'MNLA PHIL'],
    'vietnam': ['vietnam', 'ho chi minh', 'ho chi minh city', 'hochiminh', 'hochiminhcity', 'vietnamese'],
    'cambodia': ['cambodia', 'phnom penh', 'Battambang', 'cambodian'],
    'taiwan': ['taiwan', 'taipei', 'taiwanese'],
    'hong kong': ['hongkong', 'hong kong'],
    'china': ['china', 'beijing', 'shanghai', 'Chongqing', 'Guangdong', 'Guizhou', 'chinese'],
    'japan': ['japan', 'tokyo', 'kyoto', 'japanese', 'Yokohama', 'Nagoya', 'Fukuoka', 'japanese'],
    'korea': ['korea', 'seol', 'korean', 'Busan', 'Incheon', 'Daejeon', 'Gwangju', 'Ulsan'],
    'india': ['india', 'delhi', 'bombay', 'mumbai', 'jaipur', 'madras', 'pune', 'chennai', 'bangalore', 'calcutta', 'kolkata', 'Hyderabad', 'Ahmedabad'],
    'australia': ['australia', 'sydney', 'melbourne', 'brisbane', 'adelaide', 'australian'],
    'new zealand': ['new zealand', 'newzealand', ],
    'canada': ['canada', 'vancouver', 'british columbia', 'ontario', 'alberta', 'nova scotia', 'quebec', 'toronto', 'montreal',
              'Saskatchewan', 'Newfoundland', 'Norfolk County', 'canadian', ]
}

# The keywords should match exactly. So, make sure to use only those keywords that we know for sure will match and
# wouldn't match in a sub-string.
locations_keywords = {
    'singapore': ['changi', 'Bedok', 'jurong', 'clementi', 'novena', 'tekong', 'pulau', 'geylang', 'sembawang',
                  'yishun', 'kallang', 'seletar', 'mandai', 'sg'],
    'thailand': [],
    'malaysia': ['Kajang', 'Klang', 'Ipoh',  'Muar', 'Kuantan', 'Tawau', 'Sandakan', 'Seremban', 'Kulim', 'Padawan',
                 'Taiping', 'Miri', 'Kulai', 'Kangar', 'Bintulu', 'Manjung', 'Penampang', 'Sepang', 'Nilai', 'Keningau',
                 'Kluang', 'Kemaman', 'Selayang', 'Sibu'],
    'indonesia': [],
    'philippines': [],
    'vietnam': [],
    'cambodia': [],
    'taiwan': [],
    'hong kong': ['hk'],
    'china': [],
    'japan': [],
    'korea': [],
    'india': [],
    'australia': ['perth'],
    'new zealand': ['auckland',],
    'canada': ['Edmonton', 'Mississauga', 'Winnipeg', 'Brampton', 'Surrey', 'Laval', 'calgary', 'ottawa', 'halifax', 'waterloo',  ]
}

domain_extensions = {
    'singapore': ['.sg'],
    'philippines': ['.ph'],
    'hong kong': ['.hk'],
    'australia': ['.au'],
    'india': ['.in'],
    'japan': ['.jp'],
    'canada': ['.ca'],
    'blogger_domains': ['dayre.me', 'weibo.com']
}


keywords_in_different_languages = {
    #          fashion  blogger fashion blogger lifestyle influencer beauty I
    'china' : [u'時尚', u'博客', u'時尚博主', u'生活方式', u'影響', u'美女', u'我'],
    #'vietnam': [u'thời trang', u'blogger thời trang', u'lối sống', u'ảnh hưởng', u'vẻ đẹp', u'tôi'],
    'snapchat': ['\xf0\x9f\x91\xbb'],
}


# https://djangosnippets.org/snippets/1949/
def queryset_iterator(queryset, chunksize=1000):
    """
    Iterate over a Django Queryset ordered by the primary key

    This method loads a maximum of chunksize (default: 1000) rows in it's
    memory at the same time while django normally would load all rows in it's
    memory. Using the iterator() method only causes it to not preload all the
    classes.

    Note that the implementation of the iterator does not support ordered query sets.
    """
    pk = 0
    try:
        last_pk = queryset.order_by('-pk')[0].pk
        queryset = queryset.order_by('pk')
        while pk < last_pk:
            for row in queryset.filter(pk__gt=pk)[:chunksize]:
                pk = row.pk
                yield row
            gc.collect()
    except IndexError:
        gc.collect()


def better_queryset_iterator(queryset, chunksize=1000, prefetch=None,
      select_related=None, many=False):

    if isinstance(queryset, ValuesQuerySet):
        _pk_getter = lambda x: x['id']
    else:
        _pk_getter = lambda x: x.pk

    pk = 0
    try:
        last_pk = _pk_getter(queryset.order_by('-pk')[0])
        queryset = queryset.order_by('pk')
        while pk < last_pk:
            _queryset = queryset.filter(pk__gt=pk)
            if select_related:
                _queryset = _queryset.select_related(*select_related)
            if prefetch:
                _queryset = _queryset.prefetch_related(*prefetch)
            _lst = []
            for row in _queryset[:chunksize]:
                pk = _pk_getter(row)
                if many:
                    _lst.append(row)
                else:
                    yield row
            if many:
              yield _lst
            gc.collect()
    except IndexError:
        gc.collect()


def create_platform_and_influencer_for_branded_urls(urls=None):
    """
    Here, we create Influencer and Platform for crawling branded instagram platforms so that we can crawl their posts
    and also have an easier way to identifying them for crawling by just checking their 'source' field

    Call this method whenever a new branded instagram url is needed to be crawled and is added to
    brand_handles_to_scrape_on_instagram array on the top of this file
    """

    if not urls:
        urls = brand_handles_to_scrape_on_instagram

    def get_or_create_branded_influencer(username):
        inf_url = 'http://theshelf.com/artificial/instagram_username_%s.html' % username
        infs = dmodels.Influencer.objects.filter(blog_url=inf_url)
        if infs.exists():
            i = infs[0]
            i.add_tags(['brands_for_discovering_new_inf'])
            i.save()
            return i
        else:
            i = dmodels.Influencer.objects.create(blog_url=inf_url, source='retailers_to_crawl')
            i.add_tags(['brands_for_discovering_new_inf'])
            i.save()
            p = dmodels.Platform.objects.create(url='https://instagram.com/%s' % username,
                                                influencer=i,
                                                platform_name='Instagram')
            return i


    usernames = set()
    for u in urls:
        d = platformutils.username_from_platform_url(u)
        usernames.add(d)
        print("Perfect, for URL=[%r] we got username=[%r]" % (u, d))
        i = get_or_create_branded_influencer(d)
        print("OK, got this influencer: %r" % i)
        print("It's platforms: %r" % i.platforms().exclude(url_not_found=True))


