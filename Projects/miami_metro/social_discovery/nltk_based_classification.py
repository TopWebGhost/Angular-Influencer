__author__ = 'atulsingh'

"""
    Here, we are going to use nltk and classification to find qualifying features for different set of things.

    For example, brands vs. bloggers based on their profile descriptions.
    Or between asian and non-asian profiles based on their description.
"""


from textblob.classifiers import NaiveBayesClassifier
from social_discovery.models import InstagramProfile
from debra.models import Platform, Influencer, Posts
from django.db.models import Q
import time
import re

training_dataset = []
test_dataset = []


def get_description(q):
    """
    Get description from the appropriate field of the model.
    """
    if q.__class__ == InstagramProfile:
        return q.get_description_from_api()
    if q.__class__ == Platform:
        return q.description


def fill_dataset(type='training', qset=None, profile_description=True, tag=None):
    """
    Here, we fill testdata with the profiles from qset and mark them with the tag
    """
    if not tag:
        print("You need to specify the tag")
        return
    if not qset:
        print("Need to provide a qset")
        return

    if type == 'training':
        dataset = training_dataset
    else:
        dataset = test_dataset

    for q in qset:
        if profile_description:
            description = get_description(q)
            if description:
                dataset.append((description, tag))

    print("Created %d elements in the %s dataset" % (len(dataset), type))


def find_influencers_by_location(country=None):
    infs = Influencer.objects.filter(demographics_locality__country=country)
    return infs.filter(old_show_on_search=True)


def asian_vs_non_asian(limit=None):
    min_num_followers = 1000
    max_num_followers = 50000
    american_infs = find_influencers_by_location('United States')

    instagrams_of_american_infs = Platform.objects.filter(influencer__in=american_infs).exclude(url_not_found=True)
    instagrams_of_american_infs = instagrams_of_american_infs.filter(platform_name='Instagram')

    # pick the chunk
    instagrams_of_american_infs = instagrams_of_american_infs.filter(num_followers__gte=min_num_followers)
    instagrams_of_american_infs = instagrams_of_american_infs.exclude(num_followers__lte=max_num_followers)

    if limit:
        instagrams_of_american_infs = instagrams_of_american_infs[:limit]

    print("Total instagram profiles checking for american: %d" % len(instagrams_of_american_infs))
    fill_dataset('training', instagrams_of_american_infs, True, 'american')

    singapore_infs = find_influencers_by_location('Singapore')
    malaysia = find_influencers_by_location('Malaysia')
    philippines = find_influencers_by_location('Philippines')
    indonesia = find_influencers_by_location('Indonesia')

    asian_infs = singapore_infs | malaysia | philippines | indonesia

    instagrams_of_asian_infs = Platform.objects.filter(influencer__in=asian_infs).exclude(url_not_found=True)
    instagrams_of_asian_infs = instagrams_of_asian_infs.filter(platform_name='Instagram')
    # pick the chunk
    instagrams_of_asian_infs = instagrams_of_asian_infs.filter(num_followers__gte=min_num_followers)
    instagrams_of_asian_infs = instagrams_of_asian_infs.exclude(num_followers__lte=max_num_followers)

    if limit:
        instagrams_of_asian_infs = instagrams_of_asian_infs[:limit]

    print("Total instagram profiles checking for asian: %d" % len(instagrams_of_asian_infs))

    fill_dataset('training', instagrams_of_asian_infs, True, 'asian')

    cl = NaiveBayesClassifier(training_dataset)

    cl.show_informative_features(5)
    return cl



class InstagramProfileClassifier(object):

    def __init__(self, initial_train=[]):
        self.classifier = NaiveBayesClassifier(initial_train)

    def update(self, sure_post_content_list):
        self.classifier.update(sure_post_content_list)

    def classify(self, post_content):
        return self.classifier.classify(post_content)

    def prob_dist(self, post_content):
        return self.classifier.prob_classify(post_content)

    def accuracy(self, post_content):
        # TODO: does not work as written in manual
        return self.classifier.accuracy(post_content if type(post_content) == list else [post_content, ])

    def show_informative_features(self, param):
        self.classifier.show_informative_features(param)


def test_run_classification():
    training_blogger_names = ['thebeautysisterss', 'shoaib_khan_official', 'nishajha7370', 'lexieblush',
                              'undercover_mother_downunder', 'celinajaitlyofficial', 'numakeup', 'diychicfrappe',
                              'michelleghunder', 'coolshades.x', 'alexandracharles86', 'cassie_matthews_', 'brunouni',
                              'yanasamsudin', 'jonthearchitect', 'kimlow717', 'panama69', 'ashyaelizabeth',
                              'mr_stholloway', 'rachng_', 'thefashionhunger', 'sydney_aviation_photography',
                              'dreamya.t', 'chloe_hwl', 'minted_interiors', 'hokzeen', 'littlewigsfitness', 'jitshu89',
                              'acceology', 'deoteras', 'aimee_dow', 'carlystephan', 'bethanyymoore', 'suburbanburgs',
                              'itsdylansworld', 'happyharmonymay', 'linda_mua', 'gaia_wellness', 'supersamzero',
                              'kile_anna', 'misspopsasa', 'poojapadhariya', 'reina_aoi_twins', 'thebestnest',
                              'raw_styling', 'senaybostancioglu', 'slens_', 'orangina555', 'chloed88',
                              'katiemckinnon_art', 'atanasiusss', 'chloehmq', 'bunnysdesigns', 'vanessaxlim',
                              'moniqueteruelle', 'makeupbyannalee', 'iamchiharumuto', 'wonko92', 'shuanabeauty',
                              'danhilburn', 'britni_nicolee', 'masakipaula', 'sandranosekai', 'beccagilmartin',
                              'miyavimelody', 'ardaisy_', 'royalebrat', 'martinham2xq', 'hamadragon',
                              'tornevelkphotography', 'cravingyellow', 'canizares1987', 'sherrielicious',
                              'gracefullnailpolish', 'larosequotidien', 'maximsap', 'hakimbolism', 'wwmakeup',
                              'voguepursuit', 'juliabernard.pl', 'tsrhasborth', 'dotheinstathinghy', 'felipousky',
                              'itsgaldh', 'jazzdbell', 'verawaty_', 'inyonkjack', 'revelationtheory', 'erubinz',
                              'jordanrif', 'joleneguillumscott', 'daysizepeda_xx', 'yoga__h', 'theleaux',
                              '_mylifestyle._', 'natoosya', 'cshivali', 'patakutv', 'nathaliatj', 'linlinsstyle',
                              'ecoglamourgirl', 'reemark_photographica', 'endflyer', 'deniseelnajjar', '__traceykaye__',
                              'oz_hong', 'foxingtonphoto', 'jacobejercito', 'makeupbyprernakhullar', 'jippika',
                              'llpookkall', 'ms_edgeley', 'yoghanugraha.photography', 'miqinddawoon', 'rasgullareddy',
                              'ladyrebeccam', 'the_mumbaigirl', 'sweetbell77', 'feelgraphy', 'birenfan', 'jeezybelle',
                              'joycesayshello', 'maulidacita', 'vera_rhuhay', 'blogdtup', 'phoodiegram', 'theivez',
                              'j.lau.78', 'sunday_collector', 'rosannafaraci', 'rubylightfoot', 'owenichols',
                              'camigenna', 'bun__ny', 'msjsracing', 'fashionalities', 'arsyanaf21', 'shona_vertue',
                              'ismaelprata', 'charlottejcho', 'mikimiller_', 'oizep88ers', 'retratoart', 'threadnz',
                              'k1mbumseok', 'jcchris', 'thebargaindiaries', 'molliemiles', 'brewsker', 'lucindazhou',
                              'theycallmefafi', 'creationsbykassy', 'itsdannicadylan', 'yasmin_walter',
                              '__selinababy__', 'imatsofficial', 'graffitiface_mua', 'ra_sketches', 'penelopetentakles',
                              'dianaiswara', 'mybungza', 'shinoharakaori', 'her_littlestories', 'chic.byshabina',
                              'vishnubala', 'lowwie', 'tokyodame', 'blogfit', 'surfing_ewen', 'stylishevents',
                              'yuri_ebihara', 'chillimangoemily', 'mrwilkinsons', 'tracywongphoto', 'haikalshuib',
                              'carlsevert', 'nyatadesigns', 'irdammakeup', 'oneclickwonders', 'shad0wsoflove',
                              'kolkatafoodie', 'sahraruddell', 'zeecrnls', 'amy.mclean', 'misspopsasa', 'martinham2xq',
                              '2aussietravellers', 'martinham2xq',

                              # added for more precision after false opposite positives
                              '_jademadden', 'youngadultbookaddict',


                              ]

    training_brand_names = ['theshopperscloset', 'snack.fever', 'kinnapparel', 'tiphonybeauty', 'griffithuniversity',
                            'repulsebayvisualart', 'clecollections', 'delhibags', 'miishu_boutique', 'kimlow717',
                            'mizled_boutique', 'dragonberryboutiques', 'fattomelbourne', 'nourish_au', 'tadahclothing',
                            'runwaydreamofficial', 'kawaiigyarushop', 'percyhandmade', 'sithastore', 'nakedvice',
                            'friedaandgus', 'shivangigosavicouture', 'stylehub_fashion', 'rubenabird',
                            'bridalfashionweekaustralia', 'sunescapetan', 'sistersecretsph', 'sunnylifeaustralia',
                            'lnmcostore', 'mooralavoro', 'playwithbatik', 'freepeopleaustralia', 'alphabasics',
                            'azorias', 'styliaa_studio2', 'davidkind', 'lebeauties', 'fellowplectrums',
                            'yhoophiipalembang', 'australiascoralcoast', 'bbystar_on', 'aveneindia', 'topsishopp',
                            'jewel_sby', 'oldbangalowroad', 'shopvivianlly', 'topmanau', '21_olshop', 'venroy_sydney',
                            'garudaindonesiasg', 'diamondmojitto', 'sebachi_clothing', 'reidcycles',
                            'closetkingscollective', 'mommasclothed_id', 'glowbybeca', 'delmarbody', 'zenutrients',
                            'the_bling_stores', 'line_32', 'theluxeproject', 'hmcdowall', 'shopeurumme',
                            'labelsandlove43', 'gwynnies', 'shoplustre', 'bagtash', 'purplepeachshop', 'chameeandpalak',
                            'jardanfurniture', 'san_makeup', 'soonmaternity', 'inthesaclinen', 'twocents_coffee',
                            'avene_au', 'my_dirlaknshoes', 'industrylocshair', 'funktrunkph', 'buddhawear',
                            'ballettonet', 'annabelsouls', 'whiteclosetoffical', 'theboathousepb', 'emporiumbarber',
                            'tmf.cosmetics', 'emergeaustralia', 'the_raydale_man', 'outwithaudrey', 'outfix_new',
                            'mecquestore', 'ooakconceptboutiquesh', 'tokosabrina', 'rollmo_aus', 'topazette',
                            'frelynshop', 'sickysworld', 'dearfriend_childrensboutique', 'deptfinery', 'adamistmen',
                            'lovestruckcollective', 'pipmagazineau', 'topshop_au', 'artclub_concept', 'misseyewear',
                            'itsmeayela', 'beyondtheboxph', 'fox_maiden', 'keyselenaa', 'binustv',
                            'dreamcatchercandles', 'auliashouse', 'kardashiankids', 'evocature', 'brandmeup06',
                            'sofrockinggood', 'kisforkanithelabel', 'exquisepatisserie', 'shopglo', 'zahanachennai',
                            'body_blendz', 'essieaustralia', 'callmethebreezesa', 'itsfriday_bao', 'thailandfantastic',
                            'ladymignonne', 'wearesavages_au', 'badlandssupplyco', 'lorealparismy',
                            'flawlessmethailand', 'nisamakeupshop', 'glancez', 'bongky_footwear', 'blackberet_',
                            'snaapfashion', 'remetea_matcha', 'doughnut_time', 'janiceclair', 'bebedesignsau',
                            'birdsnestonline', 'thedresscollective', 'dduckshop', 'letitiagreenstudio',
                            'blossomandglowmaternity', 'ebeautyna', 'justmetea', 'jshop_id', 'svntian', 'happilyyours',
                            'honeycombers', 'm.pravadali_thelabel', 'peppermayo', 'divine_events', 'clementinism',
                            'dubsmashmalaysian_', 'venstoree', 'belancestore', 'notbooknotbuk', '_sabaii_',
                            'onyxintimates', 'lolaroselabel', 'nrlproject', 'sjlingerie', 'basicstore.eyewear',
                            'atpiecelabel', 'khamodabridal', 'the9thmuse_hk', 'almachains', 'elbalqis_kaos3d',
                            'medusahairco', 'fashi0n.bug', 'bunnys_bowtique', 'mybagshopofficial', 'multipalstore',
                            'robbyahmad', 'hermomy', 'bloheartsasia', 'makeupstoreaustralia', 'mon_purse',
                            'passionforthesun', 'bcwylie77', 'viviensmodelmgmt', 'herworldbrides', 'sickysworld',
                            'deptfinery', 'adamistmen', 'callmethebreezesa',

                            # added for more precision after false opposite positives
                            'eatclever.sg', 'ardeuirattire', 'thelentoselectshop', 'famousfootwear_aus', 'beautelash',
                            'kiwiexperience', 'mewali_lifestyle', 'amy11729', 'ninofranco.ph', 'believeestore',
                            'thenakedco_', 'topshopindonesia', 'maude_studio', 'powderperfect', 'indochine_natural',
                            'monday_blooms', 'sunflowerseedvintage', 'coconutrevolution', 'saint_bowery', 'seenit.in',
                            'minkara.life',
                            ]


    bloggernames = ['thebeautysisterss', 'shoaib_khan_official', 'nishajha7370', 'lexieblush', 'hiriemusic',
                    'undercover_mother_downunder', 'celinajaitlyofficial', 'numakeup', 'diychicfrappe',
                    'michelleghunder', 'patricia_ann_p_manzano', 'coolshades.x', 'passionforthesun',
                    'alexandracharles86', 'cassie_matthews_', 'brunouni', 'yanasamsudin', 'jonthearchitect',
                    'kimlow717', 'panama69', 'ashyaelizabeth', 'bcwylie77', 'mr_stholloway', 'rachng_',
                    'thefashionhunger', 'viviensmodelmgmt', 'sydney_aviation_photography', 'dreamya.t', 'chloe_hwl',
                    'minted_interiors', 'hokzeen', 'littlewigsfitness', 'jitshu89', 'acceology', 'deoteras',
                    'aimee_dow', 'carlystephan', 'bethanyymoore', 'suburbanburgs', 'body.tantrums', 'itsdylansworld',
                    'happyharmonymay', 'linda_mua', 'gaia_wellness', 'supersamzero', 'kile_anna', 'misspopsasa',
                    'poojapadhariya', 'reina_aoi_twins', 'thebestnest', 'lorena_g_salazar', 'raw_styling',
                    'senaybostancioglu', 'slens_', 'orangina555', 'perthfoodengineers', 'chuito_pr', 'chloed88',
                    'katiemckinnon_art', 'atanasiusss', 'chloehmq', 'bunnysdesigns', 'vanessaxlim', 'moniqueteruelle',
                    'makeupbyannalee', 'iamchiharumuto', 'wonko92', 'shuanabeauty', 'danhilburn', 'britni_nicolee',
                    'masakipaula', 'sandranosekai', 'beccagilmartin', 'miyavimelody', 'ardaisy_', 'royalebrat',
                    'martinham2xq', 'hamadragon', 'tornevelkphotography', 'cravingyellow', 'canizares1987',
                    'sherrielicious', 'gracefullnailpolish', 'larosequotidien', 'maximsap', 'herworldbrides',
                    'gibsonguitarsg', 'hakimbolism', 'wwmakeup', 'voguepursuit', 'juliabernard.pl', 'tsrhasborth',
                    'dotheinstathinghy', 'felipousky', 'itsgaldh', 'jazzdbell', 'verawaty_', 'inyonkjack',
                    'revelationtheory', 'nj_wedges', 'erubinz', 'jordanrif', 'joleneguillumscott', 'daysizepeda_xx',
                    'yoga__h', 'theleaux', '_mylifestyle._', 'natoosya', 'cshivali', 'patakutv', 'nathaliatj',
                    'linlinsstyle', 'ecoglamourgirl', 'reemark_photographica', 'endflyer', 'angelagiakas',
                    'deniseelnajjar', '__traceykaye__', 'oz_hong', 'foxingtonphoto', 'jacobejercito',
                    'makeupbyprernakhullar', 'jippika', 'llpookkall', 'ms_edgeley', 'yoghanugraha.photography',
                    'miqinddawoon', 'rasgullareddy', 'ladyrebeccam', 'the_mumbaigirl', 'sweetbell77', 'feelgraphy',
                    'birenfan', 'jeezybelle', 'joycesayshello', 'maulidacita', 'vera_rhuhay', 'blogdtup', 'phoodiegram',
                    'theivez', 'j.lau.78', 'sunday_collector', 'rosannafaraci', 'rubylightfoot', 'owenichols',
                    'camigenna', 'bun__ny', 'msjsracing', 'fashionalities', 'arsyanaf21', 'shona_vertue', 'ismaelprata',
                    'charlottejcho', 'mikimiller_', 'amirruddinrahim.co', 'oizep88ers', 'retratoart', 'threadnz',
                    'sickysworld', 'k1mbumseok', 'deptfinery', 'jcchris', 'adamistmen', 'thebargaindiaries',
                    'molliemiles', 'brewsker', 'lucindazhou', 'theycallmefafi', 'creationsbykassy', 'eshaamiinlabel',
                    'itsdannicadylan', 'yasmin_walter', '__selinababy__', 'imatsofficial', 'graffitiface_mua',
                    'ra_sketches', 'penelopetentakles', 'dianaiswara', 'mybungza', 'shinoharakaori',
                    'her_littlestories', 'chic.byshabina', 'vishnubala', 'lowwie', 'tokyodame', 'blogfit',
                    'surfing_ewen', 'stylishevents', 'yuri_ebihara', 'chillimangoemily', 'mrwilkinsons',
                    'tracywongphoto', 'haikalshuib', 'carlsevert', 'nyatadesigns', 'irdammakeup', 'callmethebreezesa',
                    'oneclickwonders', 'shad0wsoflove', 'vishblessedwesh', 'cassieeos', 'i_am_yashsinhasan',
                    'therealdisastr', 'facesbysarah', 'unlimitedgraphicphotography', 'shahilaamzah', 'amitnamdev',
                    'issacritz', 'howdyitssaikat', 'jake_od', 'cameronbyrnespt', 'helloinfinite', 'samoliverl',
                    'girly_machine', 'featherhorse_', 'idabaharum', 'hernacartriene', 'ricasuma', 'portmanteau_press',
                    'huntermodelmanagement', 'fanlaxy_', 'likeandlove', 'jelitaanggun1', 'connorsurdi', 'aafra.khan',
                    'photographybyprincess', 'kitkityan', 'aum_bellezza', 'wakame_kami', 'hnakarimafauzi',
                    'theshimmergirl', 'tokyobangbang', 'professionalstyletherapist', 'tahliademeye', 'sylphsia',
                    'valentina1121li', 'mariealessandra', 'witawanita', 'britnyellen', 'heykarenwoo', 'shotbyash',
                    'james_downing26', 'jazzbrowartist', 'lisa_berney_fitness', 'my.many.loves', 'andie_makkawaru',
                    'superpandaj5', 'bellesorelleeyebrowstylists', 'lumiopusart', 'sharonpetito', 'whenwordsfail_',
                    'theolliesavage', 'thechrishowson', 'nabilabellai_', 's624537', 'phangvictor', 'bellaformakeup',
                    'bychelseawilliamson', 'joshtwk_', 'zin19791126', 'melissabeauty.x', 'piratetb', 'saraeshu',
                    'keithpngtl', 'anmol.saxena.1013', 'tatianasandberg', 'certified.insta.beauties', '_katejarman_',
                    'thehanihanii', 'mika_haru', 'carliestatsky', 'fooderati', 'nessyrobinson', 'ranni_prmtsr',
                    'taiki_jp', 'shareroll', 'fundamentally_flawed', 'laviebohemejewelry', 'desisanti',
                    'martinagranolic', 'nondslr_guy', 'stylecircusbydivya', 'ankhkoji', 'pajezzy', 'stellar_balcony',
                    'donnaunidad', 'thisway_', 'backstreetbyindia', 'katehannah', 'danadecena', 'alanamevissen',
                    'michlbrnt', 'iamyoustudio', 'agamzone', 'shittadi', 'luxuryweddingsblogger', 'licktga',
                    'sahraruddell', 'win_sweet', 'farahsobey', 'jamesbillingphotography', 'dominiqueletoullec',
                    'yennitanoyo', 'horishoutattoo', 'colour_me_creative', 'santosh.chhantyal', 'taratats',
                    'fazabdulgaffa', 'alluringalisha', 'whoisvjm', 'indianary__', 'biendelarosajr',
                    'erinshanley.hairdressing', 'andanythingwhite', 'kimbalikes', 'mumfitness', 'jagsharathore',
                    'thejamlab', 'wilfredhomme', 'adamxshah', 'clara.egaa', 'georgemakeup', 'allegra_stone',
                    'brisbane.photographer', 'chloelecareux', 'formebydee', 'thepaperclipescapeartist', 'missmoli_',
                    'psimonmyway', 'annaspiro', 'jaineil84', 'jasonroars', 'superbarry', 'lillypiri', 'eddieseye',
                    'kaylabombardier', 'nancynielsenphotography', 'heytherehotshot', 'the_blog_of_ruchi',
                    'deviishaleekaoctavia', 'ayurysky', 'suzies_home_education_ideas', 'angelalimaq', 'thisisweiyi',
                    'amyota', 'kinustuff', 'techichikoreashoe', 'archangelachelsea', 'anna_en', 'white.lily_',
                    'justincywong', 'huffyeudaimonia', 'suzieming', 'kirstenandco', 'ozgegyru', 'eunice.arbis',
                    'devereuxxo', 'lauraerp', 'artyshanti', 'polkadotzlens', 'kazueeee', 'sebastianoserafini',
                    'ryanstuart1', 'os_peninggi_termurah', 'questterrarium', 'keiyamazaki', 'melmerizing_official',
                    'iamdallasjlogan', 'gabriellabjersland', 'parichoudhary_', 'cathhalim', 'charlynngwee', 'sasivadee',
                    'ritu_rajput', 'kaneyan0927', 'mrizkiprasetio', 'keisukesyoda', 'vinquilop', 'mart_photographer',
                    'romeoalfanta', 'scocoeco', 'doubletapbynima', 'wazari', 'adrianna_bloomsandscents',
                    'stuartnharrison', 'xxbrittersblog', 'iamjoewy', 'colorsnglitters', 'imliz99',
                    'photographybyhayqal', 'randolph_tan', 'moda_obsede', 'deaugustines', 'thealimentalsage',
                    'bobbybense', 'djleonyanggaddicitive', 'xoxomubashira', 'dev.ie', 'sonyathaniya', 'indianblog',
                    'jimmythebutt', 'mpvdave', 'paulsmollenphotography', 'tarapearce', 'top.korea', 'kei.kun',
                    'dominikcalak', 'evan14', 'shiokspot', 'sullestrade', 'alodiaalmira', 'oftravelsandtales',
                    'oliviashienny', 'fashionablefit', 'rebeccamadisonx', 'erwinmoron', 'rickyliu8', 'thelostnomadph',
                    'ahandfulofashley', 'kopithewestie', 'elpluswr', 'kristina_childs', 'emilymakeupartist',
                    'kimdaoblog', 'ketopower', 'danso_yue', 'toby_scott', 'duhbomb21_gf', 'rosiesdessertspot',
                    'littlero0', 'amieeats', 'littleclosetdiaries', 'yoni_hanan', 'zar_browexpert', 'deanraphael',
                    'nindyparasadyharsono', 'georgiakatee', 'verasalon', 'sofiahills', 'feliciajanesmakeupartistry',
                    'xpastel', 'makeupbygiorgiaskye', 'sophiefishtw', 'onetinytribe', 'natashaanicole',
                    'xlivlovesmakeup', 'mrneoluxe', 'facciataphotography', 'santiyoona', 'timothymccartneyy',
                    'eisha_megan_acton', 'teresitasporleder', 'aishadayo', 'claudiachayy', 'jdolls', 'nobiesahid',
                    'winceeee', 'jordnmcfall', 'actorleeminho.iranian.fan', 'tesseljay', 'christinasandrra',
                    'floralmagic_', 'nerdunit', 'styjp', 'flossyflamingos', 'p22_art', 'emilyfreemanphotography',
                    'henna_aj', 'rubysupergirl', 'vinu_ep', '_cebulka_', 'glitterglossbydia', 'mawis_vintage',
                    'thejoenp', 'croissantqueen', 'drama_korean_', 'lisacohenphoto', 'themakeupmummy',
                    'shutterismstudio', 'limin2204', 'sheliatan', 'mediumlady_liberty', 'moodidennaoui', 'vixquizite',
                    'timsais', 'melonrouge', 'madeleinegracemua', 'neesot', 'mybeautyconfession', 'sajidanain',
                    'emma_the_westie', 'theluxurycat', 'dianandariskia', 'nonihana_', '__benkelly__', 'chandra_wirawan',
                    'kourtzxx__xo', 'ecebutikcookies', 'thebookofkels', 'taipei20', 'imarina20', 'suzanneooi',
                    'jmoconfidential', 'surface85com', 'torihaschka', 'djsixfigures', 'chandrikaravi', 'lisaxbeauty_',
                    'leenabasu', 'woonin_lifestyle', '_healthyessence_', 'lilissudyani', 'silverorchid_henna_',
                    'nicolemammonemua', 'stoned_nair', 'ryancooperthompson', 'bellelueurbeauty', 'threadfolk',
                    'chinahookah', 'bonarchibald', 'houseofskye', 'almeidakezia', 'chinesewill', 'bli_sizeniner',
                    'ankitajain13', 'powdah', 'rjcam', 'rookthelabradoodle', 'lyndelmiller_foodstylist',
                    'kevinmurphy_guy', 'jajankulinersurabaya', 'lisamadigan', 'timothybrisbane', 'lasskaa',
                    'koolvictory', 'koota7', 'gilangnumerouno', 'aa.living', 'thesketch_', 'wrappedndiamonds',
                    'animacreatives', 'xcellmusic', 'katschultz', 'eloiseproustmua', 'scunci_hair',
                    'ashima_colorsnglitters', 'cakesbycliff', 'mizubunnie', 'apocketwifi', 'carly.gordon',
                    'thejapanesecuisine', 'rylan_kindness', 'yeungyatka', 'lafujimama', 'jenhawkins_', 'gemkwatts',
                    'fattylovelove', 'lifestylebyfeliz', 'adisurantha', 'gideon__a', 'hopefulsunflower', 'jsh_ho',
                    'ky2_lovers', 'anneprettyness', 'vivalablonde', 'theartofnight', 'ping_makeup', 'shopunk',
                    'jaiceyzhao_vaping', 'the_style_makers', 'adelaidenunes', 'misherue', '_jademadden',
                    'allana_makeupartist', 'luminousdreamsphotoworks', 'ryancornishmusic', 'thegabmag', 'divyanidutt',
                    'andreafonseka', '4dsk', 'dearestanddashing', 'itsmejerel', 'themadkitty', 'sydneyfine',
                    'satin_and_tat_collage', 'cynthiaditya', 'farahmagi', 'hollyreedmanstylist', 'cobythecorgi',
                    'yuudai0121o', 'kendraalexandra', 'bangdehampower', 'rowan_daly', 'saltmelbourne', 'taylahnilsson',
                    'eemmaa.c', 'meicamakeup', 'melissatanlh', 'youngadultbookaddict', 'cleaneatfreaks', 'mr__kee',
                    'letsnomnom', 'nitanurul', '365days2play', 'nikykim', 'littlemissluluos', 'opiumrose',
                    'aaronhandajani', 'lottaliinalove', 'keshies', 'makeupby_monmoussa', 'rifkimegasaputra',
                    'ayushii_sharma', 'theredmoustachesblog', 'viewzfinder', 'kellyexeter', 'designaquastudio',
                    'beautybykirangill', 'elizabethmbutner', 'issacdang', 'nikimehra', 'gossipsuicide', 'ejlphgphy',
                    'adorepinup', 'thais_stacruz', 'ericksaujana', 'adrielwrites', 'dave_swatt', 'delhibhukkad',
                    'gurpreetcing', 'crystalcourt', 'hungrycaramella', 'angelina_myle', 'eatdrinkandbekerry',
                    'understatedleather', 'maicoroii', 'ladyteex', 'anggaaapalinggii', 'bclsinclair', 'mommymundo',
                    'veemuhamad', 'joycelinefoxy', 'engnatalie', 'mananmehta176', 'natejhill', 'sivan_miller',
                    'kymjohnson5678', 'sashajairam', 'captureofcthulhu', 'hiiiii4945', 'ga_photo', 'russellfleming',
                    'isabellaschimidmakeup', 'daniellekatesimpson', 'inalathifahs_', 'anthonyselemidis',
                    'dannierielfanclub', 'fabiograngeon', 'ourawesomeplanet', 'milkgame', 'foodirectory', 'adamravie',
                    'adelaide90', 'benmurphy', 'bigredbusimports', 'fameisfab', 'philipskwok', 'kbexperience',
                    'style_of_my_sons', 'skye815', 'd.rodruean', 'rahul003', 'rhizaoyos', 'jade_beauty_',
                    'brookeelizabeth.photography', 'stevengoh_photography', 'taikora', 'ashaslittlesecret',
                    'thesnobjournal', 'korbin4332', 'amandanb11', 'tyler_cha', 'boy_tokyo', 'yungandrew',
                    'ieatrealfood.recipes', 'lucagri', 'munkeat', 'lovemiihuang', 'oeymaher', 'tylerphilliprecher',
                    'ameyewear', 'la_joie_des_petites_choses', 'iskachan27', 'aishwaryaraix', 'itsaaronmac',
                    'songhyekyozone', 'sarahmamavee', 'heemin1112', 'marcelglaser_', 'carolynehallumsart',
                    'nurulanisahafsirjd', 'hayzbon', 'blachford', 'fishaberry', 'sheis_sarahjane', 'sub.culture',
                    'keint_bar_rouge_shanghai', 'winifredfred', 'kenji_shigehara_yktattoo', 'musingsofashopaholicmama',
                    'artiste_feritta', 'janicehojj', 'englishhair', 'theperfect_color', 'shabirmusic', 'sydneylove23',
                    'indianaadams', 'photobytj', 'benjaminehrenberg', 'hermaz_may', 'ggofthewest', 'glennchesnaught',
                    'thesoulguide', 'gmdavis', 'mangothesheltie', 'itan', 'mamikivi', 'bebby_fey', 'lepommz',
                    'rubiiellinger', 'beebeesxthree', 'amyeshipp', 'candiceelizabethmodel', 'lateciat', 'saritatheresa',
                    'janxlsm', 'riskieforever', 'organisedlucy', 'aboynamedaaron', 'keitaxyzz', 'shijoon',
                    'saint_bowery', 'aijah_alexis', 'sevenandstitch', 'eza_zylgy', 'anoushkalila',
                    'nanuk_takahashi.buri', 'mimconcepts', 'ikuko_themirrors', 'thecrazyindianfoodie',
                    'anggaprasetyoofficial', 'carissa_mcholme', 'dom_tunny', 'missnewbeauty_', 'melindaint',
                    'nicolewilliamsphotography_', 'babydonkie', 'laurendilena', 'hunnithefrenchbulldog', 'hasszone',
                    'photo_sheep', 'thomasueda', 'fauzi_zulkifli', 'gemagrafi', 'k11hk', 'ameamay', 'sydneybrown_xo',
                    'nickyarthur2', 'skindzmakeup', 'athomebarista', 'maialiakos', 'megan_morton', 'charlie.4.daze',
                    'karolpokojowczyk', 'demelzabuckley', 'morganrubyeliza', 'rossdixonturpin', 'labelsandlove',
                    'whisperelephant3', 'beela_xo', 'awalkwithaisha', 'dorkyanil', 'jordanmcshanewebster', 'jivaapoha',
                    'newglowlashes', 'blugrid', 'luvjemma', 'ninjabharucha', 'missminxette', 'simplicitynails',
                    'brisbaneteacherstyle', 'owendippie', 'faizanpatelphotography', 'priyamukherji', 'startupcreative',
                    'randreventrentals', 'claudiacramer_', 'micah_marquez', 'kokaind', 'laiqa', 'tha_aninhablog',
                    'the_tiah', 'vic_phan', 'luicheukfung', 'yuliieta', 'amin_izzat01', 'thehungrymumbaikar',
                    'shiggashay', 'funkifizzle', 'cutiefive', 'evan__su', 'nyuqi', 'yukays411', 'joshpatil', 'meliumpr',
                    'mohnishpanjabi', 'tyanfumi', 'elainekohst', 'aodnttattoo', 'cg_lifestyled', 'andrianaliazas',
                    'hayamihannah', 'amanikins', 'prisceliachan', 'atriesangel', 'emilysears', 'colbybrittain',
                    'beautificedk', 'hypotato', 'zabillasoeprapto', 'wonderandawe_weddings', 'tucunj', 'lara_mulcahy',
                    'earl_of_anime', 'theurbanelion', 'santaanacloset', 'photographybydustin', 'crazypoplock',
                    'yumyumyummier', 'doyankuliner', 'officialmervynsharma', 'sukkisingapora', 'vin.lee.77',
                    'therealgabtan', 'jessicalea_fitnessbabes', 'cricket_studio', 'apop09', 'theinsanedoll', 'tcrossau',
                    'tickledhoney', 'yugie_potret', 'vincentcogliandro', 'brianna_cabana', 'abhijitsaiprem',
                    'helvanolshop', 'nzfashionwk', 'amaan_punkstar', 'hxhpxins', 'thejollyeater', 'thalitamatsura',
                    'stylewylde', 'asakuraskate', 'shevkellymua', 'viennarr', 'statelibrarynsw', 'jeyshatripathi',
                    'theengineereats', 'ailimusic', 'ikko_life', 'bienjrdelarosa', 'jessiead_beauty', 'perthkidz',
                    'ebonykaymakeupartist', 'priscillasmodels', 'joshuapestka', 'alyshiajoness', 'delhi_youtuber',
                    'photographybyharry', 'hartleylove', 'jadehunter56', 'chadingraham', 'yasminsuteja', 'abhitidudeja',
                    'greymagnolia', 'sleepycocoa', 'xinyicyndisoh', 'ardi_ey', 'popor_sapsiree', 'celia__b',
                    'petapachara', 'shizunan', 'faruqsuhaimi', 'chrystinang', 'meguruyamaguchi', 'heyyyyitskim18',
                    'mericatesalp', 'papillondelamode_dia', 'nfy.hijab', 'chels.randall', 'karennjoyce',
                    'leanandmeadow', 'anitanaoko', 'brittyjones', 'cjd_makeupartistry', 'indiafashionblogger',
                    'alextthomas', 'brittersbeautyaus', 'missfazura', 'somevely', 'radhikayoga', 'danielle_vella',
                    'julzjohan', 'erinvholland', 'nikenicula', 'strictlybabbzy', 'jhelocristobal', 'caturpalinggi',
                    'amenokitarou', 'zadahair', 'n.passmann', 'rayarouge', 'beverliecalopez', 'harry_elite',
                    'saintclairmusic', 'thatigambine', 'nailsbyleah', 'awayandabroad', 'makeupbyebru',
                    'stephcarrington', 'sydneyayles', 'ayanasato1', 'sarahhildebrand', 'tardaskambunawan',
                    'delhiteblogger', 'cosmic.tiger', 'beixin', 'bull8', 'meirinshop', 'digitalneverages',
                    'reeming_karisa', 'littlemisselisa', 'bieucu', 'seouleats', 'whippedcakeco', 'hannour',
                    'musingmutley', 'emitiger', 'beauhaan', 'priyankaaa25', 'crazyshredz', 'nongchat', 'emwhitham',
                    'gorav.ji', 'rita_fant', 'caleen', 'whatiwore', 'schatzlovesoriano', 'jen_hayden', 'pastelpegasus',
                    'candicecutrer', 'theestellestore', 'iamkieranc', 'shinedivas', 'thevogueamigo', 'clynemodels',
                    'thekyliebabii', 'honestlynourished', 'cookinacurry', 'gezzaseyes', 'whiskawish', 'mutzine',
                    'georgiagrav', 'weepinggoh', 'windyaprln', 'newbreedracing', 'chery0131', 'arongmama',
                    'runcintarun', 'talesofwhatever', 'anikabasics', 'zoejoez', 'i_am_laagan', 'lynette_phillips',
                    'frenchczechlevalenalouis_86', 'megankgale', 'garymehigan', 'madsfrancis', 'makeupby_rach',
                    'charlotteinwhite', 'themakeupgrub', 'kakigatel', 'brunagadelha', 'ifbkseoul', 'ijasonkeni',
                    'friskardita', 'chacha_risa', 'itssuperdave', 'anniechuasg', 'shark_model', 'chihaya_314',
                    'staceyclarkstylist', ]

    brandnames = ['theshopperscloset', 'snack.fever', 'kinnapparel', 'tiphonybeauty', 'griffithuniversity',
                  'repulsebayvisualart', 'clecollections', 'delhibags', 'miishu_boutique', 'kimlow717',
                  'mizled_boutique', 'dragonberryboutiques', 'fattomelbourne', 'nourish_au', 'tadahclothing',
                  'runwaydreamofficial', 'kawaiigyarushop', 'percyhandmade', 'sithastore', 'nakedvice', 'friedaandgus',
                  'shivangigosavicouture', 'stylehub_fashion', 'rubenabird', 'misspopsasa', 'littlemomentsapp',
                  'bridalfashionweekaustralia', 'sunescapetan', 'sistersecretsph', 'sunnylifeaustralia', 'lnmcostore',
                  'emporiummelbourne', 'mooralavoro', 'playwithbatik', 'freepeopleaustralia', 'alphabasics',
                  'lifeslittlecelebrations', 'azorias', 'amy.mclean', 'styliaa_studio2', 'davidkind', 'lebeauties',
                  'fellowplectrums', 'martinham2xq', 'yhoophiipalembang', 'australiascoralcoast', 'bbystar_on',
                  'aveneindia', 'topsishopp', 'jewel_sby', 'oldbangalowroad', 'shopvivianlly', 'topmanau', '21_olshop',
                  'venroy_sydney', 'garudaindonesiasg', 'diamondmojitto', 'sebachi_clothing', 'reidcycles',
                  'groundedpleasures', 'closetkingscollective', 'mommasclothed_id', 'glowbybeca', 'delmarbody',
                  'zenutrients', 'the_bling_stores', 'line_32', 'theluxeproject', 'hmcdowall', 'shopeurumme',
                  'shogo_yanagi', 'labelsandlove43', 'gwynnies', 'shoplustre', 'bagtash', 'purplepeachshop',
                  'chameeandpalak', 'jardanfurniture', 'san_makeup', '2aussietravellers', 'soonmaternity',
                  'inthesaclinen', 'twocents_coffee', 'avene_au', 'my_dirlaknshoes', 'industrylocshair', 'funktrunkph',
                  'buddhawear', 'autogespot_singapore', 'ballettonet', 'annabelsouls', 'whiteclosetoffical',
                  'theboathousepb', 'emporiumbarber', 'tmf.cosmetics', 'emergeaustralia', 'the_raydale_man',
                  'outwithaudrey', 'outfix_new', 'mecquestore', 'ooakconceptboutiquesh', 'tokosabrina', 'rollmo_aus',
                  'topazette', 'frelynshop', 'sickysworld', 'dearfriend_childrensboutique', 'deptfinery', 'adamistmen',
                  'lovestruckcollective', 'pipmagazineau', 'thebargaindiaries', 'topshop_au', 'artclub_concept',
                  'misseyewear', 'itsmeayela', 'beyondtheboxph', 'fox_maiden', 'keyselenaa', 'zeecrnls', 'binustv',
                  'dreamcatchercandles', 'auliashouse', 'kardashiankids', 'evocature', 'brandmeup06', 'sofrockinggood',
                  'kisforkanithelabel', 'monique_song', 'exquisepatisserie', 'shopglo', 'zahanachennai', 'body_blendz',
                  'essieaustralia', 'fatfoodiesworld', 'callmethebreezesa', 'itsfriday_bao', 'thailandfantastic',
                  'ladymignonne', 'wearesavages_au', 'badlandssupplyco', 'myfoodbag', 'lorealparismy',
                  'flawlessmethailand', 'nisamakeupshop', 'glancez', 'bongky_footwear', 'blackberet_', 'snaapfashion',
                  'remetea_matcha', 'doughnut_time', 'janiceclair', 'bebedesignsau', 'birdsnestonline',
                  'thedresscollective', 'dduckshop', 'letitiagreenstudio', 'thebombaygourmet',
                  'blossomandglowmaternity', 'ebeautyna', 'justmetea', 'jshop_id', 'svntian', 'happilyyours',
                  'honeycombers', 'm.pravadali_thelabel', 'peppermayo', 'divine_events', 'clementinism',
                  'dubsmashmalaysian_', 'venstoree', 'belancestore', 'notbooknotbuk', '_sabaii_', 'onyxintimates',
                  'lolaroselabel', 'nrlproject', 'sjlingerie', 'basicstore.eyewear', 'ladyteera', 'atpiecelabel',
                  'khamodabridal', 'the9thmuse_hk', 'almachains', 'elbalqis_kaos3d', 'medusahairco', 'fashi0n.bug',
                  'bunnys_bowtique', 'mybagshopofficial', 'multipalstore', 'robbyahmad', 'hermomy', 'bloheartsasia',
                  'makeupstoreaustralia', 'kolkatafoodie', 'sahraruddell', 'mon_purse', 'queenslandbrides',
                  'fadjuice_official', 'thedairy', 'taratats', 'mo_hkg', 'yscutebeautyshop', 'jet_set_beauty',
                  'lao_boo', 'etiquette_indonesia', 'alternativebrewing', 'koreahallyu', 'blessedwithjoolz_boutique',
                  'terramadreorganics', 'wasphair_australia', 'karmmehq', 'formebydee', 'qhhala', 'psimonmyway',
                  'svnster', 'hkoceanpark', 'wearmadeline', 'brow_architect', 'chesterstreetbakery', 'meenaclothing',
                  'shandisoshnik', 'kinustuff', 'lucky44_', 'nailpolishdirect', 'artifashion_butik',
                  'mademoisellewardrobe', 'qualtyshop', 'superdryglobal', 'konoabyrini', 'holographicdaisies',
                  'saturdaythelabel', 'qboutique_', 'macgrawlove', 'lafemme.id', 'topshop_ph', 'galerinadika',
                  'enchanted.aura', 'jontedesignerhire', 'kimberley.ph', 'sasafebbia', 'adoranne.fashion',
                  'augustthefourth', 'nat_ilyashoneyjewellery', 'littlebitoflina', 'pinkmanila', 'borongdropship',
                  'lennyclothing', 'roseinluv_official', 'ikaashieraa_shop', 'uggaustralia', 'lackofcoloraus',
                  '_myminime_', 'versavice_clothing', 'inbloomflowerco', 'simplyhairuk', 'lovinglaneigeph',
                  'platformmurah', 'twist_hk', 'ausoutbacknt', 'joelle_accessories', 'hazelnutbaby_', 'jenniferkateau',
                  '80s__vintage', 'thealimentalsage', 'sister_studios', 'hellopollyhome', 'igersindy', 'indiatrend',
                  'trendphile', 'theonlydress_store', 'craftgue', 'benefitcosmeticssg', 'huntrlabel', 'sweet_atstyle',
                  'feistheist', 'artserieshotelgroup', 'ayalamuseum', 'annukkabyronbay', 'mermaid_life_online',
                  'shophobnob', 'baggiesetc', 'cuckoocallay_cafe', 'cloth_inc', 'maverickslaces', 'unholy_clothing',
                  'littlero0', 'seafollyaustralia', 'baublelove.in', 'ohhenryvintage', '13thcase', 'theimagecode',
                  'cutiebaby_id', 'creatiebeadys', 'thegroundsfloralsbysilva', 'picturemeetsbeauty', 'onetinytribe',
                  'glitterati_store', 'thesleevelesssociety', 'thebodyshopindo', 'dokteralami', 'gingersforgentlemen',
                  'romeoandmadden', 'burdmanlawanda', 'iaclothingco', 'mossmanclothing', 'pinkishijab',
                  'barefootgypsyhomewares', 'silksupply', 'flossyflamingos', 'firstbornknits', 'mrshop_fashion',
                  'meowchic', 'minxempire', 'lovera_collections', 'naturerepublicph', 'aandjshop', 'moroccantan',
                  'banggood', 'boyshop_ragil', 'thecommonwanderer', 'jadewood_design', 'ilovemrmittens',
                  'shanghaisuzylipsticks', 'shutterismstudio', 'vidalocaindia', 'bossastore', 'fashion.lounge',
                  'sexyplus_foryou', 'mode_collective', 'luxuryshop02', 'elldesigns', 'svntal', 'novumcrafts',
                  'shangrilasub', 'urbbana', 'elfcosmeticsph', 'confetticards_', 'charmedforces', 'theluxurycat',
                  'em_vintagestones', 'roxyjaveri', 'shonajoy2026', 'lookbox_living', 'shillathelabel',
                  'sarijanehomeaccents', 'youngblood_aus', 'politixmenswear', 'the_selectiv', 'amore_tokyo',
                  'davine_os', 'sundaemuse', 'tv3malaysia', 'suechangg', 'hobbaprahran', 'beautifulchaosconcepts',
                  'lookbookindonesia', 'australia', 'lasskaa', 'jungkook.bts1', 'imrickjamesbricks', 'oleaforganic',
                  'cutthroatsupplyco', '4fingersmedan', 'threadtheory', 'japansoftlens', 'bestias_xx', 'queenetude',
                  'nicholasthelabel', 'kiehlshk', 'shopmaccs', 'mr.fashionss', 'shopunk', 'mdreamsmelissa',
                  'happysocksavenue', 'thegirlnextd00r', 'lilypadlacquer', 'quarter_surf', 'artedomus',
                  'antikasneakers', 'popflats', 'rtwonsale', 'kkochipida', 'foreverbtqfashion', 'hoyweapstore',
                  'zmgrosirkaosdistro01', 'zmgrosirkaosdistro02', 'domanishoes', 'beachbraves', 'christie_nicole',
                  'rizclothes', 'idecorateshop', 'delhi_foodie', 'originalfook', 'mommyanindya', 'tanckscorner',
                  'littlemissluluos', 'shana_ph', 'fitplusmenswholesale', 'renskincare', 'lubhnafashionparadise',
                  'eatclever.sg', 'beautybarph', 'labelist_', 'lockdownliberated', 'femaleous', 'bargainmum',
                  'ardeuirattire', 'thelentoselectshop', 'famousfootwear_aus', 'yosushi', 'beautelash',
                  'suckeredapparel', '_thecurators', 'fbifashioncollege', 'understatedleather', 'cooperst_clothing',
                  'indianbride', 'supermixme', 'kiwiexperience', 'imonnimelbourne', 'gingerenpepper', 'daisyblvd',
                  'kruenglang_palang_hin', 'the_final_scene', 'bagtrader', 'mytinywardrobesydney', 'fab.hk',
                  'morebymorello', 'mewali_lifestyle', 'stunnerboutique', 'delphinethelabel', 'theclutterbugshop',
                  'mermaiddreamsmy', 'amy11729', 'rizra_rh24', 'bembiibloopshoes', 'ninofranco.ph', 'kwanzagamingchair',
                  'gwynethboutique', 'shopsassydream', 'ildeswimwear', 'believeestore', 'thefaceshopid', 'thenakedco_',
                  'fameisfab', 'francescism', 'unclecurb', 'smartdetoxstore', 'elfs_shop', 'rosenicoleboutique',
                  'titans_wardrobe', 'svnteer', 'topshopindonesia', 'jjthreads', 'shop_rashi', 'maude_studio',
                  'antiquecandleworks', 'wynshops_', 'bata.india', 'ladychatterleysaffair', 'candywholesale',
                  'raheeel_rfs', 'powderperfect', 'bunga_butik', 'citynomads', 'indochine_natural', 'silklaundry',
                  'xenia_boutique', 'missbikinilover', 'tasmania', 'wantedshoes', 'bynorra', 'monday_blooms',
                  'bagaholics_australia', 'cvpshop', 'airnz', 'apairlstore', 'inthesoulshine', 'drumanddry',
                  'sunflowerseedvintage', 'mollinishoes', 'cupcakecentral', 'the_weekend_shop', 'indearweddings',
                  'mosmann_au', 'daisophilippines', 'onetribeapparel', 'modesportif', 'thinteadetoxtea',
                  'leonyevelyn_clothing', 'koleksikikie', 'firstcopyindoree', 'rockyrafaela', '_pastelpixie',
                  'carlaswimwear', 'alittle_pocket', 'lux_anne', 'mothercaresg', 'lipenholic', 'bangkok_stuffs',
                  'thelittlemarketbunch', 'eatsleepshopmy', 'coconutrevolution', 'cetusbiarritz', 'theassemblystore',
                  'd_voguefactory', 'originalfinch', 'aboynamedaaron', 'saint_bowery', 'foodmaniacindia', 'kliptalk',
                  'bucketsandspades', 'malaysiaairlines', 'seenit.in', 'etc.eventstyling', 'grace_1312',
                  'thecrazyindianfoodie', 'mishkahfashion', 'samplestore', 'totallyjewel', 'sweet_littledreams',
                  'hunnithefrenchbulldog', 'crinitis', 'stylehuntercollective', 'townsvillenorthqueensland',
                  'schminkhaus', 'karen_millen_aus', 'wedding.com.my', 'anjalimahtanicouture', 'frankie4footwear',
                  'micarejewels', 'sesenails', 'palmeraapparel', 'holsterfashion', 'minkara.life', 'lazadaph',
                  'healthlab', 'pigtailsandpirates', 'discountbeautyboutique', 'the_shas', 'dollybabyyyy',
                  'mickyinthevan', 'silkastuff', 'hypechamber', 'thehomeaus', 'helloflowerssg', 'zaliahinsta',
                  'thearomatherapycompany', 'micah_marquez', 'wallpaperfactory', 'kokaind', 'grandmafunk_', 'matckc',
                  'humburgermelb', 'folkandbear', 'carrislabelle', 'prestigefashion_', 'yuliieta', 'carterjayjnr',
                  'pdcollectionshop', 'trendthreads', 'petcare.com.au', 'spatulaandwhisk', 'merciperci', 'shopthirteen',
                  'smt_sheismusetia', 'misshollyxox', 'hollyryan_', 'madisonsquareclothing', 'mint_empire',
                  'dvnt_clothing', 'mark_tuckey', 'hijabsbyhanami', 'ensogoph', 'mybeardedpigeon', 'fashioncloset06',
                  'ballpensandetc', 'littleshops_', 'sports_lab_by_atmos', 'santaanacloset', 'stylistaaaaa', 'poplin_',
                  'kmartaus', 'sasuboutique', 'glamourfairy_australia', 'amethystbyrahulpopli', 'bensaholic',
                  'wrightselkarin', 'ehashimoto', 'iam_sumi', 'ethniccrush', 'cewekbelanja', 'pafrenz', 'mochasalt',
                  'joannathangiah', 'lyla_and_bo', 'visitindiana', 'thepipingbag', 'millie_brandedstore',
                  'silverspoonco', 'anboutiqueofficial', 'summurco', 'kowtowclothing', 'cocoliberace', 'indianacolony',
                  'yuppiepalace', 'cocoluxuryofficial', 'parvezo', 'moonchildhk', 'chromatic_fashion',
                  'darling_mockingbird', 'hvncaustralia', 'dnamagazine', 'little.renegade.company_', 'by.mynt',
                  'belowcepekdotcom', '31chapellane', 'localsupply', 'virginemamapapa', 'littlemisselisa',
                  'paintnaillacquer', 'nabila_chic', 'shemademe', 'suboostyle', 'urbandepot', 'sarahschembri_ceramics',
                  'phenixist', 'kookai_australia', 'tishasaksenaofficial', 'gorav.ji', 'aussiebombshell',
                  'wanderingwillos', 'midas_shoes', 'mamabodytea', 'madeinindia_surrey', 'sachishoes',
                  'eastendflowermarket', 'beautymnl', 'zoee_thelabel', 'sainttokyo', 'whiskawish', 'dientb',
                  'novivitalia', 'rosemanclub', 'mminsider', 'dfordelhi', 'foacosmetics', 'goddessbynature',
                  'chasquidoman', 'thebrittwd', 'herempireboutique', 'purecocobella', 'felice_babynkids',
                  'canonsingapore', 'doota_stylish', 'astalift_indonesia', 'empirefitnesscentre', 'femme_elegante',
                  'poppyrosebrisbane', 'greenolastyle', 'primness', 'pureteaaus', 'franjoskitchen',
                  'dazzlingdecorations', 'saul_id', 'zooomberg', 'calithepug', 'grosiraccesories', 'k_shoes13',
                  'toco_blackdiamond', 'japanbuybuy', 'binajewelry', 'ohohbilzy', 'lanstylish', 'chammakkl', 'salsuli',
                  'infiorebeauty', 'topshop_sg', 'thevelvetdolls', 'parca_equipped', 'thecleansekitchen', 'amoreosh',
                  'stfrock', 'zaidah_hijab', 'porsche_woman', 'cloakroom', 'slimsecrets', 'sugarsweet_hk',
                  'sun_photocontest', 'nathhshopp', 'prerto', 'bryan_divohairconnection', 'sandookcouture',
                  'maxtanstudio', 'yoore.official', 'shirtoria', 'pacamara_sg', 'cita9official', 'dddboutique',
                  'lovetodreamaustralia', 'cathydollmalaysia', 'minielegance', 'ettusais_sg', 'tinypeopleshop',
                  'foreveryoung_id', 'pelle_studio', 'aboutlifenm', 'misterwoodies', 'sushimastertessa', 'kiwabi',
                  'chasyahouse', 'sizeableau', 'jfwofficial', 'kozaofficial', 'irieph', 'blubelle_official',
                  'tradesecret_aus', 'thesea_andme', 'shoesforgood_id', 'moogooskincare', 'bohemian.traders',
                  'ancon_indonesia', 'thravistore', 'lemuriansea', 'muffincan', 'ohhappyfry', 'gauriandnainika',
                  'dazzleglaze', 'sams_smokes', 'byoudesigns', 'pensgaloreph', 'lucky.mie', 'catvas', 'jessicablackk',
                  'republicofashion', 'carolynunwin', 'twosixmag', 'headsupfortails', 'lalunaland', 'canonaustralia',
                  'sancia_thelabel', 'popcloudstore', 'maziicollection', 'softlenskoreajapan', 'chocoholicsavenue',
                  'shopohmyoreo', 'peekmybook', 'ama.zin', 'shopbluebelle', 'maharashtra_ig', 'sephora_india',
                  'bondisands', 'veronikamaine_design', 'debipirdashop', 'ootdcolletta', 'rubyandlilli', 'skechersph',
                  'su3_yung', 'nina_valero', 'du_chocolat', 'belindagrey', 'status_anxiety', 'remyishak',
                  'youngblood.apparel', 'septemberstoryhk', 'sckbysofiakapiris', 'shophella', 'myscrubau',
                  'afiyshya.closet', 'linneacase', 'tachkent_bags', 'ayuapparels', 'thebbcreamgirl', 'sukinskincare',
                  'ivoryandchain', 'daiso_usa', 'pranachai', 'rfyola', 'allaboutheidi', 'acquanail', 'girlzfashionshop',
                  'raw_loves_you', 'kirstenandco', 'mombasarose', 'theallnaturalcompany', 'fiorinajewellery',
                  'indobeautygram', 'vipplazaid', 'edenthecollection', 'daisyandmoose', 'henleys_wholefoods',
                  'herbeatshop', 'tintila_australia', 'belif_singapore', 'makeoverjuice', 'glampolish_', '_elone',
                  'karolinacouturelingerie', 'aloysiusnoo', 'taraashleighswimwear', 'rebela_diet', 'piasuperid',
                  'backstageclothing', 'thelittlewears', 'dealshop21', 'suvipashoes', 'gypsyjewelsaustralia',
                  'hanabunni', 'soulmade.korea', 'taffetedesigns', 'villainssf', '__2littlebirds__', 'avana_australia',
                  'vassefelixwines', 'honokaupugwyn', 'nonlastyle', 'eden_homeware', 'benefitbeautyph',
                  'projectxplanner', 'tesselaarflowers', 'grizziestore', 'dearcharme', 'travelflash', 'puppy_tales',
                  'magalipascal', 'wholesaleclothingkorea', 'doktergigi_', 'ivalice_fashionshop', 'thefashionworkshop',
                  'destination_nsw', 'cocokittenshop', 'jamesshawshankclothing', 'mystylebar_ade', 'allaboutcats9',
                  'kiitta.designs', 'fellasboutique', 'snugipops', 'felomenasimpher', 'thepowderkeg', 'ne_sense',
                  'thelaborganics', 'memybodyand_i', 'peainapodmaternity', 'pollypocketworld', 'vivahcollection',
                  'nourishedlife', 'keyshopindonesia', 'elegani.closet', 'safinahinstitute', 'wencooo',
                  'everbilenaofficial', 'jamfactorysouthyarra', 'brauerbirds_bisqueinteriors', 'malaysiakini',
                  'handsom', 'handi_borrison', 'sissaechic', 'cottonshope', 'shopdeca', 'seduceclothing',
                  'foreverandforava', 'waroengmee', 'jaunty_adam', 'frontrowshop', 'le.sarees', 'cliniquethailand',
                  'splendidblooms', 'bandung_market', 'flutternewburgh', 'bluedoornewcastle', 'vergegirl', 'tomatoph',
                  'esye_official', 'nuffnangsg', 'inglotph', 'koffeeclothing', 'geelongvintagemarket', 'sakura_station',
                  'jouldas', 'shakuhachi', 'cmdbymirna', 'pawpawcafe', 'elke_jewellery', 'washitapeaustralia',
                  'shagmelbourne', 'sgfashionistas', 'havmore.id', 'doggy_thingz', 'versatile_boutique',
                  'mavievdesigns', 'project_tbear', 'bettsshoes', 'merlocoffee', 'thais_stacruz', 'twin_olshop',
                  'bakedowncakery', 'stylespot_', 'gayy_commeplay', 'habbot', 'mossandspy', 'gwendolynne',
                  'ayinatinsta', 'finaltouchbrows', 'thewildcollectiveau', 'birdieonjames', 'vintagepip', 'thepulsehk',
                  'cncshope', 'pasdecalaisofficial', 'malongzesupershirt', 'alishaarts', 'vintage1988instagram',
                  'zoieboutique', 'strandarcade', 'inkandspindle_', 'matsumototsukasa', 'emy_gh', 'smartdetoxofficial',
                  'vanillakidshop', 'jerrijones_thelabel', 'creyons_', 'beesheekhairandmakeup', 'love_honor',
                  'jamtangan.rasyid', 'acupofchic', 'discoverqueensland', 'lovefromvenus', 'zier_insta',
                  'weifongdaniel', 'xhysteria', 'memyselfandtea', 'demoda_infashion', 'chinasouthernairlines_eu',
                  'ghelo18', 'pip_sneakers', 'thefreedomstateonline', 'jessicabearcandles', 'bigwaustralia',
                  'kickdenim', 'americaneagleid', 'envogue2', 'kiku.fashion', 'fevale_clothingstore',
                  'allthingslittle_', 'runwayscout', 'bohemian_island', 'mybebeleger', 'yupita_shop', 'larkstore',
                  'natura.lova', 'gerai_minasyari', 'shopkq', 'breslinhouse', 'mango_mojito', 'mrandmrswhite_',
                  'diaraval_shop', 'itspersonail', 'oh_my_donut_melbourne', 'entrecotemelbourne', 'kayleykate',
                  'oneteaspoon_', 'madeit', 'edetalsg', 'icecreamcookieco', 'elstarade', 'butterscotchcafe',
                  'kaayabynitusihota', 'karysfashionboutique', 'yelpindy', 'fabandglam_collections', 'wheelsnmeals',
                  'sephora_onlineshop', 'kepris', 'thehealthfoodguys', 'avierley_boutique', '30.24.shop', 'ifeofficial',
                  'yabuph', 'palanquine', 'pembekalbajumuslimah', 'chloeclothing.id', 'bluemuseboutique', 'chuanwatch',
                  'thecottonpear', 'best_bag999', 'dulla_shoes', 'svnteal', 'thebirdcageboutique', 'lizzy718',
                  'viktoriaandwoods', 'fashionableonly', 'tresind_dubai', 'burqq', 'haircandyextensions',
                  'passiontreevelvet', 'lechicorner', 'posysupplyco', 'lazyqueensvintage', 'moomoosignatures',
                  'littlepartydress', ]

    initial_train = []

    print('Initiating IPC...')

    max_qty_captions = 2

    print('Preparing to add train data for %s bloggers and %s brands '
          'with additionally %s available captions for each' % (len(training_blogger_names),
                                                                len(training_brand_names),
                                                                max_qty_captions))
    # ipc = InstagramProfileClassifier(initial_train)

    t = time.time()
    bloggers = InstagramProfile.objects.filter(username__in=training_blogger_names).values_list('api_data', flat=True)
    for api_data in bloggers:
        bio = api_data['biography']
        initial_train.append((bio, 'blogger'))
        # ipc.update([(bio, 'blogger'),])
        # also adding captions of 5 posts
        for node in api_data.get('media', {}).get('nodes', [])[:max_qty_captions]:
            caption = node.get('caption')
            if caption is not None:
                initial_train.append((caption, 'blogger'))
                # ipc.update([(bio, 'blogger'),])
    print('Collected bloggers data for %s seconds, total %s entries' % (int(time.time() - t), len(initial_train)))

    # print('Creating IPC...')
    # t = time.time()
    # ipc = InstagramProfileClassifier(initial_train)
    # print('Creation of IPC took %s seconds' % int(time.time() - t))
    # initial_train = []
    print('Added bloggers data')

    additional_train = []

    t = time.time()
    brands = InstagramProfile.objects.filter(username__in=training_brand_names).values_list('api_data', flat=True)
    for api_data in brands:
        bio = api_data['biography']
        initial_train.append((bio, 'brand'))
        # ipc.update([(bio, 'brand'),])
        # also adding captions of 5 posts
        for node in api_data.get('media', {}).get('nodes', [])[:max_qty_captions]:
            caption = node.get('caption')
            if caption is not None:
                initial_train.append((caption, 'brand'))
                # ipc.update([(bio, 'brand'),])
    print('Collected brands data for %s seconds, total %s entries' % (int(time.time() - t), len(initial_train)))

    print('Creating IPC...')
    t = time.time()
    ipc = InstagramProfileClassifier(initial_train)
    print('Creation of IPC took %s seconds' % int(time.time() - t))

    # print('Updating IPC...')
    # t = time.time()
    # ipc.update(additional_train)
    # print('Updating IPC took %s seconds' % int(time.time() - t))
    # additional_train = []
    print('Added brands data')



    print('IPC created')

    # ipc.check()
    test_blogger_names = ['lyz__official', 'bogatova_polina', 'gontrancherrier', 'deannixon1', 'emilia_elena_r',
                           'aldenrichards02', 'ohohbilzy', 'taekomccarroll', 'apocketfullofsweetness', 'mabuhaymilesss',
                           'lululuvsbklyn', 'sweetandco_', 'showntoscale', 'stellasheaa', 'piyama_co', 'ssdesignstudio',
                           'paulsboutiqueltd', 'emadkek', 'cadudasa', 'carabbrave_dancer', ]

    test_blogger_names = bloggernames[400:600]

    print('Trying to classify %s bloggers:' % len(test_blogger_names))
    for name in test_blogger_names:
        text = InstagramProfile.objects.filter(username=name).values_list('api_data', flat=True)[0]['biography']
        # result = ipc.classify(text)
        result = ipc.prob_dist(text)
        print('    %s classified as: %s (%s) %s' % (name,
                                                    result.max(),
                                                    '(bl/br : %.2f/%.2f)' % (result.prob('blogger'), result.prob('brand')),
                                                    ' <-- FALSE' if result.max() != 'blogger' else ''))

    # print('Whole bloggers test set accuracy: %s' % ipc.accuracy(test_blogger_names))

    test_brand_names = ['cherrychup', 'thecupcakequeens', 'wishxoxo', 'antoniecarey', 'bambiandtramp', 'streetonsale',
                         'remedyserum.official', 'pureplanetau', 'aahongkong', 'thedarkhorsejewellery', 'innitbangkok',
                         'blackswallowboutique', 'kravenchi', 'adelin_store', 'liefjegram', 'the_seventh_rabbit',
                         'r.s.f.g', '_houseofgypsy', 'loveizzishop', 'styletread', ]

    test_brand_names = brandnames[400:600]

    print('Trying to classify %s brands:' % len(test_brand_names))
    for name in test_brand_names:
        text = InstagramProfile.objects.filter(username=name).values_list('api_data', flat=True)[0]['biography']
        # result = ipc.classify(text)
        result = ipc.prob_dist(text)
        print('    %s classified as: %s (%s) %s' % (name,
                                                    result.max(),
                                                    '(bl/br : %.2f/%.2f)' % (result.prob('blogger'), result.prob('brand')),
                                                    ' <-- FALSE' if result.max() != 'brand' else ''))
    # print('Whole brands test set accuracy: %s' % ipc.accuracy(test_brand_names))

    ipc.show_informative_features(30)

    return ipc



class HashtagTokenizer(object):
    """
    tokenizer to extract hashtags
    """
    def __init__(self):
        self.regex = re.compile('((?!(#[a-fA-F0-9]{3})(\W|$)|(#[a-fA-F0-9]{6})(\W|$))#[a-zA-Z0-9]*)', re.I)

    def tokenize(self, text):
        return self.regex.findall(text)
hashtag_tokenizer = HashtagTokenizer()


def get_post_hashtags(post):
        # adding hashtags from post's content
        content_hashtags = []
        for h in [m[0].lower() for m in hashtag_tokenizer.tokenize(post.content)]:
            if h and h not in content_hashtags:
                content_hashtags.append(h)

        # adding also hashtags from PostInteractions of the same Post's Influencer
        for post_int in post.postinteractions_set.filter(follower__influencer_id=post.influencer_id):
            if post_int.content is not None:
                for h in [m[0].lower() for m in hashtag_tokenizer.tokenize(post_int.content)]:
                    if h and h not in content_hashtags:
                        content_hashtags.append(h)
        return content_hashtags


def test_by_hashtags_us_sea():
    """
    So, we're taking 100 Influencers with [10000:20000] followers with Instagram platforms from US
    and 1000 Influencers from SEA.
    Then we fetch 10 posts for each and get their hashtags.
    These hashtags will be lowercased and used as a train data for our classifier.

    :return:
    """
    pids = []
    train_data_us = []

    t = time.time()

    # getting US influencers Instagram platforms
    platform_ids = Platform.objects.filter(platform_name='Instagram',
                                           num_followers__gte=10000,
                                           num_followers__lte=20000,
                                           influencer__old_show_on_search=True,
                                           influencer__demographics_location__contains='United States',
                                           ).values_list('id', flat=True)[:100]   # [:1000]

    for platform_id in platform_ids:
        print('Performing platform: %s' % platform_id)
        pids.append(platform_id)
        posts = Posts.objects.filter(platform_id=platform_id).order_by('create_date')[:100]

        ctr = 0
        platform_hashtags = []
        for p in posts:
            hashtags_str = ' '.join(get_post_hashtags(p))

            if len(hashtags_str) > 0:
                # print('Post %s, hashtags: %s' % (p.id, hashtags_str))
                platform_hashtags.append(hashtags_str)
                # train_data.append((hashtags_str, 'US',))
                ctr += 1

            if ctr >= 10:

                break
        if len(platform_hashtags) > 0:
            train_data_us.append((' '.join(platform_hashtags), 'US',))

    print('US train data (took %.0f seconds):' % (time.time() - t))
    print(train_data_us)
    print('Platform IDs:')
    print(pids)

    pids = []
    train_data_esa = []

    t = time.time()
    # getting SEA training data
    profiles = InstagramProfile.objects.filter(Q(discovered_influencer__demographics_location__contains='Singapore') |
                                               Q(discovered_influencer__demographics_location__contains='Malaysia') |
                                               Q(discovered_influencer__demographics_location__contains='Philipines') |
                                               Q(discovered_influencer__demographics_location__contains='Thailand')
                                               ).order_by('-followers_count')[:100]

    for profile in profiles:
        print('Performing profile: %s' % profile.id)
        pids.append(profile.id)
        hashtags_str = ' '.join(profile.get_hashtags())
        if len(hashtags_str) > 0:
            train_data_esa.append((hashtags_str, 'SEA',))

    print('SEA train data (took %.0f seconds):' % (time.time() - t))
    print(train_data_esa)
    print('Profiles IDs:')
    print(pids)

    print('Creating IPC...')
    t = time.time()
    ipc = InstagramProfileClassifier(train_data_us+train_data_esa)
    print('Creation of IPC took %s seconds' % int(time.time() - t))

    return ipc
