import copy
from uuid import uuid4
import time
import csv
from collections import defaultdict
import itertools
import datetime

from django.conf import settings
from django.db.models import Q

from registration.models import RegistrationProfile

from debra.decorators import cached_property
from debra import constants


class SimilarWebDataFixer(object):

    def find_non_monthly_visits(self, inf_ids=None):
        from debra.models import SimilarWebVisits

        years = [2014, 2015, 2016]
        months = range(1, 13)
        days = [1]
        monthly_dates = [datetime.date(*d)
            for d in itertools.product(years, months, days)
            if d != (2016, 9, 1)]
        non_monthly_visits = SimilarWebVisits.objects.exclude(
            begins__in=monthly_dates)
        if inf_ids:
            non_monthly_visits = non_monthly_visits.filter(
                influencer_id__in=inf_ids)
        return non_monthly_visits

    def fix_monthly_visits(self, inf_ids=None):
        from debra.models import mc_cache

        non_monthly_visits = self.find_non_monthly_visits(inf_ids=inf_ids)
        non_monthly_visits.delete()
        mc_cache.clear()


class CustomBloggersLoader():

    INFLUENCER_FIELDS = {
        # 'Name': 'name',
        # 'Occupation': 'InfluencerBrandMapping.occupation',
        # 'Category Tags': 'InfluencerBrandMapping.categories',
        'Instagram Handle': None,
        # 'Site/Blog': 'blog_url',
        # 'YouTube Channel': 'youtube_url',
        'Instagram Following': None,
        # 'Snapchat Name': 'snapchat_username',
        # 'Sex': 'InfluencerBrandMapping.sex',
        # 'Age': 'InfluencerBrandMapping.age',
        # 'Ethnicity': 'InfluencerBrandMapping.ethnicity',
        # 'Country': 'Influencer.DemographicsLocality.country',
        # 'Language': 'InfluencerBrandMapping.language',
        # 'Representation': 'InfluencerBrandMapping.representation',
        # 'Mailing Address': 'InfluencerBrandMapping.mailing_address',
        # 'City': 'Influencer.DemographicsLocality.city',
        # 'State (only use for USA)': 'Influencer.DemographicsLocality.state',
        # 'ZipCode': 'InfluencerBrandMapping.zip_code',
        # 'Direct Email Address': None,
        # 'Direct Cell': 'InfluencerBrandMapping.cell',
        # 'Rep Email Address': 'InfluencerBrandMapping.rep_email_address',
        # 'Rep Phone': 'InfluencerBrandMapping.rep_phone',
         #'Notes': 'InfluencerBrandMapping.notes',
    }

    def __init__(self, brand_id=None, filename=None, file_format=None, limit=None):
        self.filename = filename
        self.file_format = file_format or 'csv'
        self.brand_id = brand_id
        self.limit = limit

    def read_from_file(self):
        data = []
        with open(self.filename, 'rb') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return data

    def load(self, to_save=False):
        from debra.models import (InfluencersGroup,
            DemographicsLocality, Influencer, InfluencerBrandMapping,)

        fields_data = self.get_fields_data()
        if self.limit:
            fields_data = fields_data[:self.limit]

        infs = []

        if to_save:
            tag = InfluencersGroup.objects.get(
                id=constants.R29_CUSTOM_DATA_TAG_ID)

            for data in fields_data:
                inf = Influencer(**data['influencer'])

                demographics_locality = DemographicsLocality.objects.get_or_create(
                    **data['demographics'])[0]
                inf.demographics_locality = demographics_locality
                inf.save(bypass_checks=True)

                tag.add_influencer(inf)

                brand_mapping = InfluencerBrandMapping(**data['brand_mapping'])
                brand_mapping.influencer = inf
                brand_mapping.save()

                infs.append(inf)

        return infs

    def fix_blog_urls(self, to_save=False):
        from debra.models import Influencer

        infs = Influencer.objects.filter(source='r29_customer_import')
        infs = infs.exclude(blog_url__isnull=True)
        infs = infs.exclude(blog_url__icontains='http')
        infs = infs.exclude(blog_url__icontains='.co')
        infs = infs.exclude(blog_url__icontains='www')
        infs = infs.exclude(blog_url__icontains='youtu.be')
        infs = infs.exclude(blog_url__icontains='bit.ly')
        infs = infs.exclude(blog_url='n/a')
        infs = infs.exclude(blog_url__icontains='.se')

        # fields_data = self.get_fields_data()
        # blog_url_2_inf = {inf['influencer']['blog_url']:inf for inf in fields_data}

        new_urls = {}

        for inf in infs:
            # new_blog_url = blog_url_2_inf.get(inf.blog_url, {}).get()
            new_blog_url = 'http://' + ''.join(inf.blog_url.replace(
                '&', 'and').replace("'", "").lower().split(' ')) + '.com'
            if to_save:
                inf.blog_url = new_blog_url
                inf.save(bypass_checks=True)
            print '* {} ==> {}'.format(inf.blog_url, new_blog_url)
            new_urls[new_blog_url] = inf
        return new_urls

    def fix_blog_urls_v2(self, to_save=False):
        from openpyxl import load_workbook
        from debra.models import Influencer

        wb = load_workbook(filename='/home/walrus/Documents/custom_bloggers.xlsx')
        ws = wb['Talent Tracker as of 8.5.16']
        rows = list(ws.rows)

        urls = [
            'http://minniemuse.com',
            'http://charissafay.com',
            'http://trotter.com',
            'http://letasobierajski.com',
            'http://troprouge.com',
            'http://thelifestyled.com',
            'http://mariavannguyen.com',
            'http://nanysklozet.com',
            'http://saraphotographs.com',
            'http://15minutebeauty.com',
            'http://fancytreehouse.com',
            'http://greaseandglamour.com',
            'http://kenziepoo.com',
            'http://keatonrow.com',
            'http://evagoicochea.com',
            'http://colormecourtney.com',
            'http://sassykitchen.com',
            'http://fashionbananas.com',
            'http://chloedigital.com',
            'http://kristenglam.com',
            'http://thefashionphilosophy.com',
            'http://fashionedchic.com',
            'http://hellosandwich.com',
            'http://heyprettything.com',
            'http://honestlyjamie.com',
            'http://fitbabefiles.com',
            'http://leoht.com',
            'http://fireonthehead.com',
            'http://juniperandfir.com',
            'http://theobjectenthusiast.com',
            'http://apartment34.com',
            'http://beauty101blog.com',
            'http://beautyandsomebeef.com',
            'http://beautybets.com',
            'http://brightandbeautiful.com',
            'http://stylewithinreach.com',
            'http://caitlinmoran.com',
            'http://afashionloveaffair.com',
            'http://carleybarton.com',
            'http://carmynjoy.com',
            'http://wearwherewell.com',
            'http://forsling.com',
            'http://chantalanderson.com',
            'http://lyst.com',
            'http://momofukumilkbar.com',
            'http://christinemcconnell.com',
            'http://delune.com',
            'http://claudiacomte.com',
            'http://coco+kelly.com',
            'http://cocorosa.com',
            'http://moehfashion.com',
            'http://inspirat.io/spielkkind.com',
            'http://stylelustpages.com',
            'http://crystalinmarie.com',
            'http://openhaus.com',
            'http://dawnrichard.com',
            'http://dchaussee.com',
            'http://eggcanvas.com',
            'http://eleanorfriedberger.com',
            'http://keatonrow.com',
            'http://modwedding.com',
            'http://ouropenroad.com',
            'http://emthegem.com',
            'http://esteestanley.com',
            'http://evashawmusic.com',
            'http://evannclingan.com',
            'http://everythingcurvyandchic.com',
            'http://thisthatbeauty.com',
            'http://sugarhillcountryclub.com',
            'http://misswhoeveryouare.com',
            'http://studdedknives.com',
            'http://gypsetgoddess.com',
            'http://haim.com',
            'http://halliedaily.com',
            'http://soulectionpage.com',
            'http://happilygrey.com',
            'http://thehousethatlarsbuilt.com',
            'http://houseofharper.com',
            'http://ifyouseekstyle.com',
            'http://shannonbarkerr.com',
            'http://nomia.com',
            'http://nycpretty.com',
            'http://juliapott.com',
            'http://kateryan.com',
            'http://kateyoung.com',
            'http://smallspells.com',
            'http://ondiyoga.com',
            'http://capturefashion.com',
            'http://naja.com',
            'http://willbryantstudio.com',
            'http://urbanbushbabes.com',
            'http://pickthebrain.com',
            'http://gonzaleswithans.com',
            'http://styleonwine.com',
            'http://cleowade.com',
            'http://esraroise.com',
            'http://peelingin.com',
            'http://flashesofstyle.com',
            'http://flowergirlnyc.com',
            'http://foodiecrush.com',
            'http://garnerstyle.com',
            'http://stilettobeats.com',
            'http://good,bad,andfab..com',
            'http://hbfit.com',
            'http://thedaydreamings.com',
            'http://fashionhotbox.com',
            'http://viennawedekind.com',
            'http://viewfrom5ft2.com',
            'http://takeaim.com',
            'http://virginiaelwoodtattoo.com',
            'http://eye4style.com',
            'http://justdanablair.com',
            'http://baby2baby.com',
            'http://kittycowell.com',
            'http://profreshstyle.com',
            'http://caitlincawley.com',
            'http://sacramentostreet.com',
            'http://bakeyourday.com',
            'http://monbraee.com',
            'http://mystylepill.com',
            'http://melrodstyle.com',
            'http://fivestory.com',
            'http://iwantyoutoknow.com',
            'http://kendieveryday.com',
            'http://itssuperfashion.com',
            'http://vsf.com',
            'http://miannscanlan.com',
            'http://brynenotice.com',
            'http://ohsoglam.com',
            'http://soko.com',
            'http://sophielopez.com',
            'http://thistimetomorrow.com',
            'http://leefromamerica.com',
            'http://pennyweight.com',
            'http://pinkhorrorshow.com',
            'http://lindseylouie.com',
            'http://styleslicker.com',
            'http://ambitiouskitchen.com',
            'http://calivintage.com',
            'http://carolynhsu.com',
            'http://christinaemilie.com',
            'http://jetsetfarryn.com',
            'http://poemstore.com',
            'http://shinythoughts.com',
            'http://papillion.com',
            'http://courtneyscott.com',
            'http://dallasshaw.com',
            'http://fashionmegreen.com',
            'http://dianebirch.com',
            'http://emmajanekepley.com',
            'http://chloeroth.com',
            'http://ericacorsano.com',
            'http://thespicystiletto.com',
            'http://djunabel.com',
            'http://perrinparis.com',
            'http://saraluxe.com',
            'http://jeanstories.com',
            'http://citybrewed.com',
            'http://goldwireblog.com',
            'http://dylanasuarez.com',
            'http://doobop.com',
            'http://scoutsixteen.com',
            'http://tellloveandchocolate.com',
            'http://styleandpepper.com',
            'http://inspirafashion.com',
            'http://locksandtrinkets.com',
            'http://retroflame.com',
            'http://lombardandfifth.com',
            'http://brittandwhit.com'
        ]

        mapping = {}
        for row in rows:
            blog_url = row[4].value or ''
            new_blog_url = 'http://' + ''.join(blog_url.replace(
                '&', 'and').replace("'", "").lower().split(' ')) + '.com'
            if new_blog_url in urls:
                mapping[new_blog_url] = (blog_url,
                    row[4].hyperlink.target if row[4].hyperlink else None)

        infs = Influencer.objects.filter(
            source='r29_customer_import',
            blog_url__in=urls
        ).exclude(blog_url__isnull=True)

        # [3033384, 3032166, 3034086, 3033125, 3034135, 3034047, 3033296, 3033485,
        # 3033762, 3031729, 3032463, 3033666, 3032994, 3032972, 3032445, 3032245,
        # 3033788, 3032309, 3032191, 3033032, 3032428, 3032468, 3032642, 3032661,
        # 3032755, 3033087, 3033119, 3033714, 3033325, 3034058, 3031895, 3031962,
        # 3031963, 3031965, 3032036, 3032084, 3032085, 3032108, 3032111, 3032122,
        # 3032133, 3032135, 3032163, 3032198, 3032204, 3032205, 3032218, 3032224,
        # 3032238, 3032241, 3032243, 3033888, 3032249, 3032255, 3032262, 3032297,
        # 3032299, 3032359, 3032365, 3032368, 3032379, 3032398, 3032420, 3032436,
        # 3032447, 3032446, 3032450, 3032480, 3032479, 3033409, 3033911, 3032600,
        # 3032606, 3032607, 3032615, 3032621, 3032681, 3032682, 3032710, 3033814,
        # 3033560, 3033572, 3032912, 3032956, 3032958, 3033853, 3033594, 3031745,
        # 3034146, 3034207, 3032212, 3033097, 3034121, 3032128, 3032230, 3032433,
        # 3032484, 3032501, 3032508, 3032510, 3032538, 3033906, 3032579, 3032612,
        # 3034017, 3034025, 3034170, 3034171, 3033371, 3034175, 3032329, 3032918,
        # 3032983, 3033019, 3033665, 3032080, 3032083, 3032143, 3033428, 3033473,
        # 3033354, 3032215, 3032700, 3032987, 3033304, 3034096, 3033361, 3033571,
        # 3033583, 3033866, 3033882, 3033040, 3033107, 3033628, 3033642, 3033152,
        # 3033924, 3031829, 3032089, 3032130, 3032203, 3032866, 3032903, 3033826,
        # 3033608, 3032251, 3032270, 3032594, 3032325, 3032412, 3034010, 3032427,
        # 3034073, 3032336, 3033633, 3031724, 3032504, 3032213, 3032281, 3032354,
        # 3032880, 3032923, 3033976, 3033914, 3032961, 3033397, 3033708, 3033196,
        # 3032042]


        print list(infs.values_list('id', flat=True))

        res = []
        for inf in infs:
            correct_blog_url = mapping.get(inf.blog_url)
            try:
                correct_blog_url = mapping[inf.blog_url][1]
            except KeyError:
                pass
            else:
                # print inf.blog_url, '==>', correct_blog_url
                res.append((inf, correct_blog_url))
                if to_save:
                    inf.blog_url = correct_blog_url
                    inf.save(bypass_checks=True)
        return res



    def find_busted_by_qa_bloggers_v1(self):
        from debra.models import Influencer, InfluencerEditHistory

        fields_data = self.get_fields_data()

        infs = Influencer.objects.filter(source='r29_customer_import')
        touched_infs = Influencer.objects.filter(
            id__in=list(InfluencerEditHistory.objects.filter(
                influencer__in=infs
            ).distinct('influencer').values_list(
                'influencer', flat=True))
        )

        name_2_inf = {inf['influencer']['name']:inf for inf in fields_data}
        snapchat_2_inf = {inf['influencer']['snapchat_username']:inf for inf in fields_data}
        blog_url_2_inf = {inf['influencer']['blog_url']:inf for inf in fields_data}

        found_infs = []
        found_infs.extend([(inf, name_2_inf.get(inf.name)) for inf in touched_infs])
        found_infs.extend([(inf, snapchat_2_inf.get(inf.snapchat_username)) for inf in touched_infs])
        found_infs.extend([(inf, blog_url_2_inf.get(inf.blog_url)) for inf in touched_infs])

        return dict(found_infs)

    def fix_busted_by_qa_bloggers_v1(self, inf_ids=None):
        '''
        So, go through all of those R29's influencers from the spreadsheet
        a) reset all of their social *_url fields to none 
        b) set all of their platform objects with url_not_found=True
        c) then save the url fields from their spreadsheet
        d) save their name, location fields as well.. (custom data is fine, don't touch it)
        '''
        from debra.models import Influencer
        from platformdatafetcher import geocoding

        infs_data = self.find_busted_by_qa_bloggers_v1()
        if inf_ids:
            infs_data = {inf:data for inf, data in infs_data.items() if inf.id in inf_ids}
        total = len(infs_data)

        for n, (inf, fields_data) in enumerate(infs_data.items(), start=1):
            # (a)
            for field in Influencer.SOCIAL_PLATFORM_FIELDS:
                setattr(inf, field, None)
            inf.save(bypass_checks=True)
            # (b)
            inf.platform_set.update(url_not_found=True)
            # (c)
            for field in ['youtube_url', 'snapchat_username', 'insta_url']:
                setattr(inf, field, fields_data['influencer'][field])
            # (d)
            for field in ['name']:
                setattr(inf, field, fields_data['influencer'][field])

            inf.demographics_location = u', '.join(
                filter(None, [fields_data['demographics'][unit]
                    for unit in ['city', 'state', 'country']]))
            inf.save(bypass_checks=True)
            geocoding.normalize_location(inf.id)
            # .apply_async((inf.id,),
            #     queue='blogger_approval_report')
            print '* {}/{}'.format(n, total)

    def update_locations(self):
        from debra.models import Influencer
        from platformdatafetcher import geocoding
        infs = Influencer.objects.filter(source='r29_customer_import')
        infs = infs.select_related('demographics_locality')
        total = infs.count()
        for n, inf in enumerate(infs, start=1):
            location = unicode(inf.demographics_locality)
            inf.demographics_location = location
            inf.save()
            geocoding.normalize_location.apply_async((inf.id,),
                queue='blogger_approval_report')
            print '{}/{}'.format(n, total)

    def update_ethnicity(self):
        from debra.models import (
            Influencer, InfluencerBrandMapping,)

        fields_data = self.get_fields_data()
        mapping = {inf['influencer']['insta_url']:inf for inf in fields_data}

        brand_mappings = InfluencerBrandMapping.objects.filter(
            influencer__source='r29_customer_import'
        ).select_related('influencer')  

        total = brand_mappings.count()
        for n, brand_mapping in enumerate(brand_mappings, start=1):
            brand_mapping.ethnicity = mapping[brand_mapping.influencer.insta_url]['brand_mapping']['ethnicity']
            brand_mapping.save()
            print '* {}/{}'.format(n, total)

    def prepare_fields_data(self, inf_data):
        from debra.models import (
            Influencer, DemographicsLocality,
            InfluencerBrandMapping,)

        influencer_fields = {
            'name': inf_data['Name'].strip() or None,
            'blog_url': inf_data['Site/Blog'].strip() or None,
            'email': inf_data['Direct Email Address'].strip() or None,
            'youtube_url': inf_data['YouTube Channel'].strip() or None,
            'snapchat_username': inf_data['Snapchat Name'].strip() or None,
            'insta_url': 'https://www.instagram.com/{}/'.format(
                inf_data['Instagram Handle'].strip('@')) if inf_data['Instagram Handle'] else None,
            'source': 'r29_customer_import',

            'show_on_search': False, # just for now
            'old_show_on_search': False, # just for now
        }

        instagram_platform_fields = {
            'insta_url': influencer_fields['insta_url'] or None,
            'num_followers': inf_data['Instagram Following'] or None,
            'platform_name': 'Instagram',
        }

        demographics_fields = {
            'country': inf_data['Country'].strip() or None,
            'city': inf_data['City'].strip() or None,
            'state': inf_data['State (only use for USA)'].strip() or None,
        }

        brand_mapping_fields = {
            'brand_id': self.brand_id,
            'influencer_id': None,
            'cell_phone': inf_data['Direct Cell'].strip() or None,
            'representation': inf_data['Representation'].strip() or None,
            'rep_email_address': inf_data['Rep Email Address'].strip() or None,
            'rep_phone': inf_data['Rep Phone'].strip() or None,
            'language': [x.strip() for x in inf_data['Language'].split(',')] if inf_data['Language'] else None,
            'zip_code': inf_data['ZipCode'].strip() or None,
            'mailing_address': inf_data['Mailing Address'].strip() or None,
            'categories': [x.strip()
                for x in inf_data['Category Tags'].split(',')] if inf_data['Category Tags'] else None,
            'occupation': [x.strip()
                for x in inf_data['Occupation'].split(',')] if inf_data['Occupation'] else None,
            # 'sex': dict([
            #     (v, k) for k, v in InfluencerBrandMapping.SEX
            # ])[inf_data['Sex'].strip()],
            'sex': [x.strip() for x in inf_data['Sex'].split('/')] if inf_data['Sex'] else None,
            'age': int(inf_data['Age'].strip()) if inf_data['Age'].strip() else None,
            'ethnicity': [x.strip() for x in inf_data['Ethnicity'].split(',' if ',' in inf_data['Ethnicity'] else '/')],
            'notes': inf_data['Notes'].strip() if inf_data['Notes'] else None,
        }

        return {
            'influencer': influencer_fields,
            'demographics': demographics_fields,
            'brand_mapping': brand_mapping_fields,
            'instagram_platform': instagram_platform_fields,
        }

    def get_fields_data(self):
        infs_data = self.read_from_file()
        return [
            self.prepare_fields_data(inf_data)
            for inf_data in infs_data
        ]


def create_fake_user_for_influencer(influencer_id):
    from debra.models import Influencer, User, UserProfile

    test_email = 'our.newsletter.list@gmail.com'

    inf = Influencer.objects.get(id=influencer_id)

    inf.email = test_email
    inf.email_for_advertising_or_collaborations = test_email
    inf.email_all_other = None
    inf.ready_to_invite = True
    inf.show_on_search = False
    inf.save()

    UserProfile.objects.filter(influencer=inf).update(influencer=None)

    user = User.objects.create_user(
        username='delete_{}'.format(uuid4()),
        email=test_email,
        password='1234',
    )
    user.is_active = True
    user.save()

    user_prof = UserProfile.user_created_callback(user)
    user_prof.name = inf.name
    user_prof.blog_name = inf.blogname
    user_prof.blog_page = inf.blog_url
    user_prof.blog_verified = True
    user_prof.influencer = inf
    user_prof.save()

    inf.shelf_user = user
    inf.save()

    return user


def create_fake_copy_of_influencer(source_influencer_id, destination_influencer_id=None):
    from debra.models import Influencer

    source_influencer = Influencer.objects.get(id=source_influencer_id)

    if destination_influencer_id:
        destination_influencer = Influencer.objects.get(
            id=destination_influencer_id)
        destination_influencer.average_num_comments_per_post = source_influencer.average_num_comments_per_post
        destination_influencer.average_num_posts = source_influencer.average_num_posts
        destination_influencer.save()
    else:
        destination_influencer = source_influencer
        destination_influencer.pk = None
        destination_influencer.save()

    for pl in source_influencer.platforms():
        new_pl = pl
        new_pl.pk = None
        new_pl.influencer = destination_influencer
        new_pl.save(bypass_checks=True)


class TrackingLinksVerificator(object):

    def __init__(self, campaign_ids=None):
        self.campaign_ids = campaign_ids
        self.errors = defaultdict(list)

    @staticmethod
    def is_correct(urls, datapoints):
        if not urls or urls == ['']:
            return any([
                not datapoints,
            ])
        else:
            if not datapoints:
                return False
            if len(filter(None, urls)) != len(datapoints):
                return False
            pairs = zip(filter(None, urls), datapoints)
            try:
                return all(map(
                    lambda x: x[0] and x[0] != 'None' and x[1] and int(x[1]),
                    pairs
                ))
            except ValueError:
                return False

    @classmethod
    def is_campaign_links_correct(cls, campaign, contract):
        return cls.is_correct(
            campaign.product_urls, contract.campaign_product_tracking_links)

    @classmethod
    def is_contract_links_correct(cls, campaign, contract):
        return cls.is_correct(
            contract.product_urls, contract.product_tracking_links)

    @property
    def campaigns(self):
        from debra.models import BrandJobPost
        if self.campaign_ids:
            campaigns = BrandJobPost.objects.filter(
                candidates__isnull=False,
                id__in=self.campaign_ids
            ).exclude(info='').distinct()
        else:
            campaigns = BrandJobPost.objects.filter(
                candidates__isnull=False).exclude(info='').distinct()
        return campaigns

    @property
    def errors_data(self):
        if not self.errors:
            return

        def _get_contracts_data():
            from debra.models import Contract
            ids = self.errors.keys()
            associated_campaigns = dict(
                Contract.objects.filter(
                    id__in=ids
                ).values_list(
                    'id', 'influencerjobmapping__job'
                )
            )
            return {
                'ids': ids,
                'associated_campaigns': associated_campaigns,
                'with_errors_in_contract': [
                    k for k, v in self.errors.items() if 'contract' in v],
                'with_errors_in_campaign': [
                    k for k, v in self.errors.items() if 'campaign' in v],
            }

        def _get_campaigns_data(contracts_data):
            mapping = contracts_data['associated_campaigns']
            campaign_ids = list(set(mapping.values()))
            return {
                'ids': campaign_ids,
                'with_errors_in_contract': list(set([
                    mapping[k]
                    for k in contracts_data['with_errors_in_contract']
                ])),
                'with_errors_in_campaign': list(set([
                    mapping[k]
                    for k in contracts_data['with_errors_in_campaign']
                ])),
            }

        contracts_data = _get_contracts_data()
        campaigns_data = _get_campaigns_data(contracts_data)

        return {
            'counts': {},
            'values': {
                'contracts': contracts_data,
                'campaigns': campaigns_data,
            }
        }

    def run_check(self, both=False):
        total_campaigns = self.campaigns.count()
        for n, campaign in enumerate(self.campaigns, start=1):
            candidates = campaign.candidates.exclude(contract__isnull=True)
            print '\t{}/{}: id = {}, contracts number = {}'.format(
                n, total_campaigns, campaign.id, candidates.count())
            t0, errors_found = time.time(), len(self.errors)
            candidates = candidates.prefetch_related('contract')
            for ijm in candidates:
                if both or campaign.info_json.get('same_product_url'):
                    if not self.is_campaign_links_correct(campaign, ijm.contract):
                        self.errors[ijm.contract_id].append('campaign')
                if both or not campaign.info_json.get('same_product_url'):
                    if not self.is_contract_links_correct(campaign, ijm.contract):
                        self.errors[ijm.contract_id].append('contract')
            print '\t\t* errors found: {}'.format(len(self.errors) - errors_found)
            print '\t\t* time: {}'.format(time.time() - t0)

    def run_simple_fix(self, which=None, to_save=False):
        from debra.models import Contract
        if not which:
            which = ['contract', 'campaign']
        total_contracts = len(self.errors)
        print '\ttotal busted contracts: {}'.format(total_contracts)
        for n, (contract_id, errors) in enumerate(self.errors.items()):
            c = Contract.objects.prefetch_related(
                'influencerjobmapping__job').get(id=contract_id)
            print '\t\t{}/{}: id = {}, campaign = {}, errors = {}'.format(
                n, total_contracts, contract_id, c.campaign.id, errors)
            if 'contract' in errors and 'contract' in which:
                print '\t\t\tContract fixes:'
                print '\t\t\t\t* product urls: {}'.format(c.product_urls)
                print '\t\t\t\t* old tracking links: {}'.format(
                    c.product_tracking_links)
                if to_save:
                    product_urls = copy.copy(c.product_urls)
                    c.product_urls = []
                    c._ignore_old = True
                    c.save()
                    # just in case they have not been removed
                    c.product_tracking_links = []
                    c.product_urls = product_urls
                    c.save()
                    print '\t\t\t\t* done'
            elif 'campaign' in errors and 'campaign' in which:
                print '\t\t\tCampaign fixes'
                print '\t\t\t\t* product urls: {}'.format(
                    c.campaign.product_urls)
                print '\t\t\t\t* old tracking links: {}'.format(
                    c.campaign_product_tracking_links)
                if to_save:
                    c._newly_created = True
                    c.campaign_product_tracking_links = []
                    c.save()
                    print '\t\t\t\t* done'


class DataChecker(object):
    pass


class CampaignStagesChecker(DataChecker):

    def __init__(self):
        self._wrong_ids = []

    @cached_property
    def checkers(self):
        from debra.models import InfluencerJobMapping

        def pre_outreach(ijm):
            return ijm['agr_messages_count'] == 0

        def waiting_on_response(ijm):
            return ijm['agr_messages_count'] > 0 and\
                ijm['agr_blogger_messages_count'] == 0

        def negotiation(ijm):
            return ijm['agr_blogger_messages_count'] > 0

        return {
            InfluencerJobMapping.CAMPAIGN_STAGE_PRE_OUTREACH: pre_outreach,
            InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE: waiting_on_response,
            InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION: negotiation,
        }

    def check_instance(self, instance):
        return self.checkers[instance['campaign_stage']](instance)

    def run(self, campaign_ids=None):
        from aggregate_if import Count
        from debra.models import (
            BrandJobPost, InfluencerJobMapping, MailProxyMessage)
        if campaign_ids:
            campaigns = BrandJobPost.objects.filter(id__in=campaign_ids)
        else:
            campaigns = BrandJobPost.objects.exclude(archived=True)
        total_campaigns = campaigns.count()
        for n, campaign in enumerate(campaigns, start=1):
            print '* {}/{} campaign (id={}) processing'.format(
                n, total_campaigns, campaign.id)
            ijms = list(campaign.candidates.filter(campaign_stage__in=[
                InfluencerJobMapping.CAMPAIGN_STAGE_PRE_OUTREACH,
                InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE,
                InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION,
            ]).annotate(
                agr_messages_count=Count('mailbox__threads', only=(
                    Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL)
                )),
                agr_blogger_messages_count=Count('mailbox__threads', only=(
                    Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL) &
                    Q(mailbox__threads__direction=\
                        MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND)
                ))
            ).values('id', 'agr_messages_count', 'agr_blogger_messages_count',
                'campaign_stage'))

            _wrong_count = 0
            for ijm in ijms:
                if not self.check_instance(ijm):
                    self._wrong_ids.append(ijm['id'])
                    _wrong_count += 1

            print '** {} out of {} ids are wrong'.format(_wrong_count,
                len(ijms))
        print 'Total: {} wrong ids'.format(len(self._wrong_ids))

    def fix(self):
        from debra.models import InfluencerJobMapping, MailProxyMessage
        ijms = InfluencerJobMapping.objects.filter(id__in=self._wrong_ids)

        ijms.filter(
            Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_PRE_OUTREACH) &
            Q(mailbox__threads__isnull=False)
        ).update(
            campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE
        )

        ijms.filter(
            Q(campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE) &
            Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
            Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL) &
            Q(mailbox__threads__direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND)
        ).update(
            campaign_stage=InfluencerJobMapping.CAMPAIGN_STAGE_NEGOTIATION
        )


def hide_reporting_tab_for_new_brands(signup_threshold=None, count_only=False):
    from debra.models import Brands, User
    from social_discovery.blog_discovery import queryset_iterator

    signup_threshold = signup_threshold or datetime.date(2016, 2, 1)
    
    brands = Brands.objects.filter(is_subscribed=True)
    total = brands.count()

    brands_to_disable = []
    for n, brand in enumerate(queryset_iterator(brands), start=1):
        has_old_users = brand.related_user_profiles.filter(
            user_profile__user__date_joined__lt=signup_threshold
        ).count() > 0
        if not has_old_users:
            if not count_only:
                brand.flag_post_reporting_on = False
                brand.flag_report_roi_prediction = False
                brand.save()
            brands_to_disable.append(brand)
        print '* {}/{}, number of brands with hidden tab so far: {}'.format(
            n, total, len(brands_to_disable))
    return brands_to_disable
