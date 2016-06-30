import json
import dateutil
import datetime
import time
import itertools
import random
from collections import defaultdict

from django.shortcuts import get_object_or_404
from django.http import Http404
from django.db.models import F
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.conf import settings
from django.core.cache import get_cache

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.decorators import action, link
from rest_framework import status


from djangorestframework_camel_case.render import CamelCaseJSONRenderer
from djangorestframework_camel_case.parser import CamelCaseJSONParser
from aggregate_if import Count

from debra.models import (
    Posts, BrandJobPost, SiteConfiguration, Contract, MailProxyMessage,
    Brands, BrandTaxonomy, IA, IJM, IAC, InfluencerBrandMapping,
    ROIPredictionReport, User, InfluencersGroup, InfluencerBrandUserMapping,
    Platform, Influencer,)
from debra.serializers import (
    PostSerializer, CampaignSerializer, SiteConfigurationSerializer,
    ContractSerializer, ConversationSerializer, BrandSerializer,
    BrandTaxonomySerializer, InfluencerBrandMappingSerializer,
    CustomDataInfluencerSerializer,)
from debra import constants
from debra import feeds_helpers as fh
from debra.decorators import cached_property
from campaigns.helpers import CampaignReportDataWrapper
from campaigns.decorators import campaign_report_endpoint


redis_cache = get_cache('redis')


class PostDetails(APIView):

    def get(self, request, pk, format=None):
        post = get_object_or_404(Posts, pk=pk)
        serializer = PostSerializer(post)
        return Response(serializer.data)


class PostSearch(APIView):

    def get(self, request, format=None):
        url = request.QUERY_PARAMS.get('url')
        if not url:
            return Response()
        if not url.startswith('http'):
            url = 'http://' + url
        posts = Posts.objects.filter(url=url)
        try:
            post = posts[0]
        except IndexError:
            raise Http404
        else:
            serializer = PostSerializer(post)
            return Response(serializer.data)


class MailProxyMessageViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = MailProxyMessage.objects.all()
    serializer_class = ConversationSerializer

    @link()
    def content_part(self, request, id):
        m = self.get_object()
        cid = request.GET.get('cid')

        orig_msg = ConversationSerializer.get_original_message(m.msg)
        parts = ConversationSerializer.get_message_parts(orig_msg)

        data = {}
        try:
            content_type, content = parts['inline_images'][cid]
        except KeyError:
            data.update({
                'status': 'error',
            })
        else:
            data.update({
                'status': 'success',
                'data': {
                    # 'content_type': content_type,
                    # 'content': content,
                    'content': 'data:{};base64, {}'.format(
                        content_type, content)
                }
            })
        return Response(data)


class CampaignViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = BrandJobPost.objects.all()
    serializer_class = CampaignSerializer

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)

    @action(methods=['post'])
    def submit_public_approval_report(self, request, id):
        from debra import mail_proxy

        data = json.loads(request.body)

        brand_id = data.get('brand_id')
        report_id = data.get('report_id')
        user_id = data.get('user_id')

        report = ROIPredictionReport.objects.get(id=report_id)
        user = User.objects.get(id=user_id)
        hash_key = report.get_public_hash(user)

        # public_link = report.get_public_url(user)
        # inner_link = "{}{}".format(constants.MAIN_DOMAIN, reverse(
        #     'debra.search_views.blogger_approval_report',
        #     args=(report_id,))
        # )

        # subject = "{}. Client approval report submitted".format(inner_link)
        # body = "".join([
        #     "<p>Public link: {}</p>",
        #     "<p>Inner link: {}</p>",
        # ]).format(public_link, inner_link)

        # helpers.send_admin_email_via_mailsnake(
        #     subject,
        #     body,
        #     ["michael@theshelf.com", "desirae@theshelf.com", "lauren@theshelf.com"]
        # )

        rendered_message = render_to_string(
            'mailchimp_templates/approval_report_submitted_email.txt', {
                'user': user.userprofile,
                'campaign': report.campaign,
                'blog_domain': constants.BLOG_DOMAIN,
                'main_domain': constants.MAIN_DOMAIN,
            }
        ).encode('utf-8')

        mandrill_message = {
            'html': rendered_message,
            'subject': "The Influencer Approval Form for {} has been submitted.".format(report.campaign.title),
            'from_email': 'lauren@theshelf.com',
            'from_name': 'Lauren',
            'to': [{
                'email': user.email,
                'name': user.userprofile.name if user.userprofile else user.email
            }],
        }

        print mandrill_message

        mail_proxy.mailsnake_send(mandrill_message)

        report.influencer_collection.approval_status = IAC.APPROVAL_STATUS_SUBMITTED
        report.influencer_collection.save()

        if report.campaign:
            report.campaign.influencer_collection.influenceranalytics_set.filter(
                tmp_approve_status__isnull=True
            ).update(
                tmp_approve_status=IA.APPROVE_STATUS_PENDING
            )
            report.campaign.influencer_collection.influenceranalytics_set.update(
                approve_status=F('tmp_approve_status'))
            report.campaign.merge_approved_candidates(celery=True)

        return Response({
            'redirect_url': reverse('debra.search_views.blogger_approval_report_public',
                args=(brand_id, report_id, user_id, hash_key,)),
        })

    @action(methods=['post'])
    def move_all_bloggers_to_another_stage(self, request, id):
        '''
            Example of POST params:
            {
                from_stage: <number>,
                to_stage: <number>,
            }
        '''
        data = json.loads(request.body)

        from_stage = data.get('from_stage')
        to_stage = data.get('to_stage')

        ijms = IJM.objects.filter(job_id=id, campaign_stage=from_stage)
        ijms.update(campaign_stage=to_stage)

        return Response({
            'redirect_url': reverse('debra.job_posts_views.campaign_setup',
                args=(id,)) + '?campaign_stage={}'.format(to_stage),
        })

    @action(methods=['post'])
    def archive_influencer(self, request, id):
        '''
            Example of POST params:
            {
                stage_type: 'pre_outreach' / 'outreach',
                influencer_id: <pk>,
                mapping_id: <pk>,
            }
        '''
        data = json.loads(request.body)
        stage_type = data.get('stage_type', 'outreach')

        if stage_type == 'pre_outreach':
            ia = IA.objects.get(id=data.get('mapping_id'))
            ia.archived = not ia.archived
            ia.save()
        elif stage_type == 'outreach':
            IJM.objects.filter(id=data.get('mapping_id')).update(
                campaign_stage=IJM.CAMPAIGN_STAGE_ARCHIVED)

        return Response()

    @action(methods=['get'])
    def approval_report_selection_counts(self, request, id):
        from aggregate_if import Count

        campaign = self.get_object()
        collection = campaign.influencer_collection

        _counts_qs = collection.influenceranalytics_set.exclude(
            archived=True
        ).values(
            'tmp_approve_status'
        ).annotate(Count('tmp_approve_status'))

        _statuses = [
            IA.APPROVE_STATUS_YES,
            IA.APPROVE_STATUS_NO,
            IA.APPROVE_STATUS_MAYBE,
            IA.APPROVE_STATUS_PENDING,
        ]

        _counts = {
            x['tmp_approve_status']: x['tmp_approve_status__count']
            for x in _counts_qs
            if x['tmp_approve_status'] in _statuses
        }

        data = {
            'list': [{
                'text': "{}'s".format(dict(IA.APPROVE_STATUS).get(status)),
                'count': _counts.get(status, 0),
            } for status in _statuses],
            'pending_count': _counts.get(IA.APPROVE_STATUS_PENDING, 0),
        }
        return Response(data)

    @action(methods=['get'])
    def total_blog_impressions(self, request, id):
        campaign = self.get_object()
        data = {
            'title': 'Total Blog Impressions',
            'count': campaign.get_total_impressions(blog_only=True),
            'order': 1,
        }
        return Response(data)

    @action(methods=['get'])
    def total_potential_social_impressions(self, request, id):
        campaign = self.get_object()
        data = {
            'title': 'Total Potential Social Impressions',
            'count': campaign.get_total_impressions(social_only=True),
            'order': 2,
        }
        return Response(data)

    @action(methods=['get'])
    def total_potential_unique_social_impressions(self, request, id):
        campaign = self.get_object()
        data = {
            'title': 'Total Potential Unique Social Impressions',
            'count': campaign.get_unique_impressions(social_only=True),
            'order': 3,
        }
        return Response(data)

    @action(methods=['get'])
    def all_impressions(self, request, id):
        campaign = self.get_object()
        data = {
            'title': 'All Impressions',
            'count': campaign.get_total_impressions(),
            'order': 4,
        }
        return Response(data)


class SiteConfigurationViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = SiteConfiguration.objects.all()
    serializer_class = SiteConfigurationSerializer

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)

    @action(methods=['get'])
    def blogger_custom_metadata(self, request, id):
        data = self.get_object().blogger_custom_data_json
        return Response(data)

    @action(methods=['get'])
    def locations(self, request, id):
        query = request.GET.get('q')
        locs = redis_cache.get('longlocs')
        if query:
            data = [loc for loc in locs
                if loc.get('title') and query.lower() in loc.get('title').lower()]
        else:
            data = locs[:200]
        for item in data:
            item['value'] = item['title']
        data = [item for item in data
            if item['title'] and item['title'] != 'None']
        total = len(data)
        print '* got {} locations'.format(total)
        data = data[:250]
        return Response(data)


class BrandTaxonomyViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = BrandTaxonomy.objects.all()
    serializer_class = BrandTaxonomySerializer

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)

    @action()
    def update_es_counts(self, request, id):
        taxonomy = self.get_object()
        taxonomy.update_es_counts()
        return Response(self.serializer_class(taxonomy).data)


class ContractViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)

    # if contract.tracking_hash_key != hash_key:
    #     raise Http404()

    @action()
    def add_blogger_post(self, request, id):
        from debra.models import PostAnalyticsCollection, PostAnalytics

        contract = self.get_object()
        data = json.loads(request.body)

        if not contract.campaign.bloggers_post_collection:
            print '* no post collection, creating one...'
            contract.campaign.bloggers_post_collection =\
                PostAnalyticsCollection.objects.create(
                    name="Campaign: {}, Blogger: {}".format(
                        contract.campaign.title, contract.blogger.id),
                    creator_brand=contract.brand,
                    system_collection=True,
                )
            contract.campaign.save()

        item = PostAnalytics.objects.from_source(
            post_url=data.get('url'), refresh=True)
        item.post_date = dateutil.parser.parse(data.get('date', ''))
        item.post_title = data.get('title')
        item.post_type = data.get('type')
        item.contract = contract
        item.save()
        contract.campaign.bloggers_post_collection.add(item)
        return Response({'data': item.blogger_post})

    @action()
    def remove_blogger_posts(self, request, id):
        contract = self.get_object()

        data = json.loads(request.body)
        if contract.campaign.bloggers_post_collection is not None:
            contract.campaign.bloggers_post_collection.remove(
                pa_ids=data.get('ids'))
        return Response(data)

    @action()
    def mark_blogger_posts_done(self, request, id):
        contract = self.get_object()

        contract.posts_adding_status = contract.POSTS_ADDING_STATUS_DONE
        contract.save()

        return Response()

    @action()
    def verify_blogger_post(self, request, id):
        from debra.account_helpers import influencer_tracking_verification
        from debra.models import PostAnalytics

        data = json.loads(request.body)

        pa = PostAnalytics.objects.get(id=int(data.get('id')))

        influencer_tracking_verification.apply_async(
            [pa.id], queue="influencer_tracking_verification")
        pa.tracking_status = PostAnalytics.TRACKING_STATUS_SENT
        pa.save()

        return Response({'data': pa.blogger_post})

    @action()
    def generate_google_doc(self, request, id):
        contract = self.get_object()
        contract.generate_google_doc()
        return Response({
            'data': {
                'googleDocEmbedUrl': contract.google_doc_embed_url,
            }
        })


class BrandViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = Brands.objects.all()
    serializer_class = BrandSerializer

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)

    @action(methods=['post'])
    def flags(self, request, id):
        brand = self.get_object()
        data = json.loads(request.body)
        for flag, value in data.items():
            attr_name = 'flag_{}'.format(flag)
            try:
                getattr(brand, attr_name)
            except AttributeError:
                pass
            else:
                setattr(brand, attr_name, value)
        brand.save()
        return Response()

    @action(methods=['get'])
    def outreach_templates(self, request, id):
        obj = self.get_object()
        data = self.serializer_class().get_outreach_templates(obj)
        return Response({'data': data})

    @action(methods=['get'])
    def campaigns(self, request, id):
        obj = self.get_object()
        data = self.serializer_class().get_campaigns(obj)
        return Response(data)

    @action(methods=['get'])
    def saved_searches(self, request, id):
        obj = self.get_object()
        data = self.serializer_class().get_saved_searches(obj)
        return Response(data)

    @action(methods=['get'])
    def tags(self, request, id):
        obj = self.get_object()
        data = self.serializer_class().get_tags(obj)
        return Response(data)

    @action(methods=['get', 'post'])
    def blogger_custom_data(self, request, id):
        from djangorestframework_camel_case.util import underscoreize
        if request.method == 'GET':
            try:
                inf_id = int(request.GET.get('influencer_id'))
            except (TypeError, ValueError):
                inf_id = None
            if inf_id:
                mapping, _ = InfluencerBrandMapping.objects.get_or_create(
                    influencer_id=inf_id, brand_id=id)
                data = InfluencerBrandMappingSerializer(mapping).data
            else:
                obj = self.get_object()
                data = InfluencerBrandMappingSerializer(
                    obj.influencerbrandmapping_set.all(), many=True).data
            return Response(data)
        else:
            data = underscoreize(json.loads(request.body))

            print data.get('influencer_id')

            mapping, _ = InfluencerBrandMapping.objects.get_or_create(
                influencer_id=data.get('influencer_id'),
                brand_id=id)

            mapping_data = data['fields']
            influencer_data = data['fields']['influencer_data']
            location_data = data['fields']['location_data']

            def save_mapping():
                serializer = InfluencerBrandMappingSerializer(mapping,
                    data=mapping_data, partial=True)
                if serializer.is_valid():
                    serializer.save()

            def save_influencer():
                serializer = CustomDataInfluencerSerializer(mapping.influencer,
                    data=influencer_data, partial=True)
                if serializer.is_valid():
                    serializer.save()

            def save_location():
                edited = False
                if location_data['location'] != mapping.influencer.demographics_location_normalized:
                    mapping.influencer.demographics_location_normalized = location_data['location']
                    edited = True
                if location_data['location'] != mapping.influencer.demographics_location:
                    mapping.influencer.demographics_location = location_data['location']
                    edited = True
                if edited:
                    mapping.influencer.save()
                    from platformdatafetcher import geocoding
                    geocoding.normalize_location.apply_async(
                        (mapping.influencer.id,), queue='blogger_approval_report')

                # save directly to 'demographics_locality'
                # serializer = CustomDataLocationSerializer(
                #     mapping.influencer.demographics_locality,
                #     data=location_data, partial=True)
                # if serializer.is_valid():
                #     serializer.save()

            save_mapping()
            save_influencer()
            save_location()

            return Response()


class InfluencerBrandMappingViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = InfluencerBrandMapping.objects.all()
    serializer_class = InfluencerBrandMappingSerializer

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)


class TagViewSet(viewsets.ViewSet):
    # lookup_field = 'id'
    # queryset = InfluencersGroup.objects.all()
    # serializer_class = InfluencersGroupSerializer

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)

    def _get_tag_ids(self, brand_id, inf_id=None):
        pipe = settings.REDIS_CLIENT.pipeline()
        pipe.hget('brectags', brand_id)
        if isinstance(inf_id, int):
            pipe.get('bnotes_{}_{}'.format(brand_id, inf_id))
            pipe.sdiff('btags_{}'.format(brand_id), 'systags')
            pipe.sdiff(
                'itags_{}'.format(inf_id), 'systags')
            pipe_data = pipe.execute()
            try:
                recent_tag = int(pipe_data.pop(0))
            except:
                recent_tag = None
            try:
                note = pipe_data.pop(0)
            except:
                note = None
            btag_ids, itag_ids = pipe_data
            btag_ids = map(int, filter(lambda x: x and x != 'None', btag_ids))
            itag_ids = map(int, filter(lambda x: x and x != 'None', itag_ids))
        elif isinstance(inf_id, list):
            note = None
            pipe.sdiff('btags_{}'.format(brand_id), 'systags')
            for inf in inf_id:
                pipe.sdiff('itags_{}'.format(inf), 'systags')
            results = pipe.execute()
            try:
                recent_tag = int(results.pop(0))
            except:
                recent_tag = None
            btag_ids, itag_ids = (map(int, filter(lambda x: x and x != 'None', results[1])),
                dict(zip(inf_id, map(int, filter(lambda x: x and x != 'None', results[1:])))))
        else:
            note = None
            pipe.sdiff('btags_{}'.format(brand_id), 'systags')
            results = pipe.execute()
            recent_tag, btag_ids = results
            try:
                recent_tag = int(recent_tag)
            except:
                recent_tag = None
            # btag_ids = map(int, settings.REDIS_CLIENT.sdiff(
            #     'btags_{}'.format(brand_id), 'systags'))
            btag_ids = map(int, filter(lambda x: x and x != 'None', btag_ids))
            itag_ids = None
        return note, recent_tag, btag_ids, itag_ids

    def _get_tag_pics(self, tag_ids):
        pipe = settings.REDIS_CLIENT.pipeline()
        for tag_id in tag_ids:
            pipe.hget('tpics', tag_id)
        pics = pipe.execute()
        return dict(zip(tag_ids, pics))

    def _get_rand_infs_from_tags(self, tag_ids):
        pipe = settings.REDIS_CLIENT.pipeline()
        for tag_id in tag_ids:
            pipe.srandmember('tinfs_{}'.format(tag_id))
        random_infs = map(int, pipe.execute())
        return dict(zip(random_infs, tag_ids))

    def list(self, request):
        try:
            inf_id = int(request.GET.get('influencer_id'))
        except (ValueError, TypeError):
            inf_id = None

        _t0 = time.time()
        brand = request.visitor["base_brand"]
        print 'getting brand took {}'.format(time.time() - _t0)

        _t0 = time.time()

        note, recent_tag, btag_ids, itag_ids = self._get_tag_ids(brand.id, inf_id)

        tag_pics = self._get_tag_pics(btag_ids)

        redis_cache_keys = list(itertools.chain(
            ['ig_{}'.format(tag_id) for tag_id in btag_ids],
            ['pp_{}'.format(inf_id)],
        ))
        redis_cache_data = redis_cache.get_many(redis_cache_keys)

        # @todo: we don't really need to do it, we can get
        # pic from the front-end, it's already there
        curr_img_url = redis_cache_data.pop('pp_{}'.format(inf_id), None)

        names = {
            int(tag_id.strip('ig_')): name
            for tag_id, name in redis_cache_data.items()
        }

        print 'redis took {}'.format(time.time() - _t0)

        if note is None and inf_id is not None:
            _t0 = time.time()
            try:
                note = InfluencerBrandUserMapping.objects.filter(
                    user_id=request.user.id, influencer_id=inf_id
                ).values_list('notes', flat=True)[0]
            except IndexError:
                note = None
            print 'notes db call took {}'.format(time.time() - _t0)

        data = {
            'groups': sorted(({
                'id': tag_id,
                'name': name or '',
                'selected': itag_ids and tag_id in itag_ids,
                'type': 'collection',
                'img': tag_pics.get(tag_id) or constants.DEFAULT_PROFILE_PIC,
            } for tag_id, name in names.items()), key=lambda x: x['name'].lower()),
            'img_url': curr_img_url,
            'note': note,
        }

        if recent_tag:
            data.update({
                'recent_tag': recent_tag,
            })

        return Response(data)

    def create(self, request):
        # from debra.brand_helpers import bookmarking_task
        from debra import account_helpers, mongo_utils

        mongo_utils.track_visit(request)

        brand = request.visitor['base_brand']
        data = json.loads(request.body)

        # check if group with such name exists
        note, recent_tag, brand_tag_ids, _ = self._get_tag_ids(brand.id)
        tag_names = redis_cache.get_many([
            'ig_{}'.format(tag_id) for tag_id in brand_tag_ids
        ]).values()

        if data.get('name') in tag_names:
            return Response({
                'status': 'error',
                'content': 'Collection with such name already exists',
            }, status=status.HTTP_400_BAD_REQUEST)

        tag = InfluencersGroup.objects.create(
            name=data.get('name'),
            owner_brand=brand,
            creator_brand=brand,
            creator_userprofile=request.visitor['user'],
        )
        settings.REDIS_CLIENT.sadd('btags_{}'.format(brand.id), tag.id)
        # settings.REDIS_CLIENT.hset('brectags', brand.id, tag.id)

        # track
        mongo_utils.track_query("brand-create-collection", {
            'collection_name': tag.name,
        }, {"user_id": request.visitor["auth_user"].id})

        account_helpers.intercom_track_event(request, "brand-create-collection", {
            'collection_name': tag.name,
        })

        return Response({
            'id': tag.id,
            'name': tag.name,
            'selected': True,
            'type': 'tag',
        })

    @action(methods=['post'])
    def bookmark_influencer(self, request, pk=None):
        data = json.loads(request.body)
        # brand = request.visitor['base_brand']

        try:
            brand = int(data.get('brand'))
        except:
            brand = None

        influencer = data.get('influencer')
        if isinstance(influencer, list):
            try:
                influencers = map(int, influencer)
            except:
                influencers = None
        else:
            try:
                influencer = int(influencer)
            except:
                influencers = None
            else:
                influencers = [influencer]

        if not influencers:
            influencers = filter(None, [influencer])

        if not influencers or not brand:
            return Response({
                'status': 'error',
                'content': 'No influencers and/or brand provided',
            }, status=status.HTTP_400_BAD_REQUEST)

        tags = data.get('groups', [])

        # btag_ids, itag_ids = self._get_tag_ids(brand.id, influencers)

        tags = [tag for tag in tags if tag.get('id') is not None]
        selected_tags = map(int, [tag.get('id') for tag in tags if tag.get('selected')])
        non_selected_tags = map(int, [tag.get('id') for tag in tags if not tag.get('selected')])

        InfluencersGroup.objects.add_influencer_fast(selected_tags, influencers,
            mark_as_recent=True, brand_id=brand)
        InfluencersGroup.objects.remove_influencer_fast(non_selected_tags, influencers)

        return Response({})

    @action(methods=['post'])
    def save_notes(self, request, pk=None):
        data = json.loads(request.body)
        # brand = request.visitor['base_brand']

        try:
            influencer = int(data.get('influencer'))
        except:
            influencer = None

        try:
            brand = int(data.get('brand'))
        except:
            brand = None

        if influencer is None or brand is None:
            return Response({
                'status': 'error',
                'content': 'No influencer and/or brand provided',
            }, status=status.HTTP_400_BAD_REQUEST)

        use_db = data.get('use_db', True)
        use_redis = data.get('use_redis', True)

        if use_db:
            _t0 = time.time()
            mapping, _ = InfluencerBrandUserMapping.objects.get_or_create(
                influencer_id=influencer, user=request.user)
            mapping.notes = data.get('note')
            mapping.save()
            print '* save to db took {}'.format(time.time() - _t0)
        if use_redis:
            _t0 = time.time()
            pipe = settings.REDIS_CLIENT.pipeline()
            pipe.setex('bnotes_{}_{}'.format(brand, influencer),
                data.get('note'), 60 * 60 * 36)
            pipe.execute()
            print '* save to redis took {}'.format(time.time() - _t0)

        return Response({})


class CampaignReportViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = BrandJobPost.objects.all()
    serializer_class = CampaignSerializer

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)

    PLATFORMS = ['Blog', 'Instagram', 'Facebook',
        'Twitter', 'Pinterest',]


    # <SHIT>

    MOCK_DATA = {
        'influencer_names': ['Ben Cerny', 'Pavel Sukhanov',
            'Atul Singh', 'Lauren Jung', 'Sabrina Fenster', 'John Lennon',
            'Paul McCartney', 'Ringo Starr', 'George Harrison',
            'Jimmy Page', 'Robert Plant', 'John Bonham', 'John Paul Jones'
        ],
    }

    @classmethod
    def get_n_profile_pics(cls, n):
        j = BrandJobPost.objects.get(id=355)
        inf_ids = list(j.candidates.values_list('mailbox__influencer',
            flat=True))
        pics = filter(None,
            redis_cache.get_many(['pp_{}'.format(inf_id) for inf_id in inf_ids]).values())
        n = min(n, len(pics))
        return pics[:n]

    @classmethod
    def n_random_asc_ints_generator(cls, n, values_range):
        values = sorted(random.sample(values_range, n))
        for value in values:
            yield value

    @classmethod
    def n_random_asc_dates_generator(cls, n, start_date=None, end_date=None):
        from debra.helpers import get_random_date
        values = sorted(
            get_random_date(start_date, end_date) for _ in xrange(n))
        for value in values:
            yield value

    def get_post_analyics_queryset(self):
        campaign = self.get_object()
        # @todo: not all of the platforms are displayed on the front-end,
        # 'Tumblr', for example. so not sure if we should exclude them
        return campaign.participating_post_analytics.exclude(
            post__platform__platform_name='Instagram',
            post__post_image__isnull=True
        ).exclude(
            post__platform__isnull=True
        )

    @cached_property
    def post_analytics_queryset(self):
        return self.get_post_analyics_queryset()

    def get_platform_counts(self):
        _t0 = time.time()
        qs = self.post_analytics_queryset
        counts = {
            item['post__platform__platform_name']: item['count']
            for item in qs.values('post__platform__platform_name').annotate(
                count=Count('post'))
        }
        counts['Blog'] = sum(cnt for pl, cnt in counts.items()
            if pl in Platform.BLOG_PLATFORMS)
        for pl, _ in counts.items():
            if pl in Platform.BLOG_PLATFORMS:
                del counts[pl]
        total = sum(counts.values())
        print '* get_platform_counts took {}'.format(time.time() - _t0)
        return counts, total

    def get_influencers(self, INFS_PER_PLATFORM=5):
        qs = self.post_analytics_queryset
        pairs = list(qs.values_list(
            'post__platform__platform_name', 'post__influencer'
        ).distinct(
            'post__influencer', 'post__platform__platform_name'
        ).order_by('post__influencer'))
        infs = defaultdict(list)
        for pl, inf in pairs:
            pl = 'Blog' if pl in Platform.BLOG_PLATFORMS else pl
            if len(infs[pl]) >= INFS_PER_PLATFORM:
                continue
            infs[pl].append(inf)
        profile_pics = Influencer.objects.get_profile_pics(
            itertools.chain(*infs.values()))
        return {
            pl: [{
                'id': inf,
                'name': None,
                'pic': profile_pics.get(inf),
            } for inf in infs_list] for pl, infs_list in infs.items()
        }

    # </SHIT>


    @action(methods=['get'])
    @campaign_report_endpoint
    def platform_counts(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def random_influencers(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def top_posts(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def post_samples(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def top_influencers_by_share_counts(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def posting_time_series(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def post_counts_time_series(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def influencer_performance(self, request, id):
        pass

    @action(methods=['get'])
    def engagement_time_series(self, request, id):
        endpoint, pl_name = ('engagement_time_series',
            request.GET.get('platform_name'))
        eng_type = request.GET.get('engagement_type')
        w = CampaignReportDataWrapper(id)
        data = w.retrieve_from_cache('{}_{}_{}'.format(
            endpoint, pl_name, eng_type))
        return Response(data)

    @action(methods=['get'])
    def cumulative_engagement_time_series(self, request, id):
        endpoint, pl_name = ('cumulative_engagement_time_series',
            request.GET.get('platform_name'))
        eng_type = request.GET.get('engagement_type')
        w = CampaignReportDataWrapper(id)
        data = w.retrieve_from_cache('{}_{}_{}'.format(
            endpoint, pl_name, eng_type))
        return Response(data)

    @action(methods=['get'])
    @campaign_report_endpoint
    def clickthroughs_time_series(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def cumulative_clickthroughs_time_series(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def impressions_time_series(self, request, id):
        pass

    @action(methods=['get'])
    @campaign_report_endpoint
    def cumulative_impressions_time_series(self, request, id):
        pass


class InfluencerViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'
    queryset = Influencer.objects.all()
    serializer_class = None

    renderer_classes = (
        CamelCaseJSONRenderer, BrowsableAPIRenderer,)
    parser_classes = (CamelCaseJSONParser,)

    @action(methods=['get'])
    def posts_section_count(self, request, id):
        influencer = self.get_object()

        section = fh.normalize_feed_key(
            request.GET.get('section', 'blog_posts'))
        brand = request.GET.get('brand_domain_name')

        def get_url():
            url_section = {
                fh.BLOG_FEED_FILTER_KEY: 'posts',
                fh.PRODUCT_FEED_FILTER_KEY: 'items',
                fh.INSTAGRAM_FEED_FILTER_KEY: 'photos',
                fh.TWITTER_FEED_FILTER_KEY: 'tweets',
                fh.PINTEREST_FEED_FILTER_KEY: 'pins',
                fh.FACEBOOK_FEED_FILTER_KEY: 'facebook',
                fh.YOUTUBE_FEED_FILTER_KEY: 'videos',
            }.get(section, section)

            params = dict(section=url_section, influencer_id=influencer.id)
            if brand:
                params.update(dict(brand_domain=brand))
            return reverse('debra.blogger_views.blogger_generic_posts',
                kwargs=params)

        def get_title(count):
            title = {
                fh.ALL_FEED_FILTER_KEY: 'All',
                fh.BLOG_FEED_FILTER_KEY: 'Post',
                fh.PRODUCT_FEED_FILTER_KEY: 'Product',
                fh.INSTAGRAM_FEED_FILTER_KEY: 'Photo',
                fh.TWITTER_FEED_FILTER_KEY: 'Tweet',
                fh.PINTEREST_FEED_FILTER_KEY: 'Pin',
                fh.FACEBOOK_FEED_FILTER_KEY: 'Facebook Post',
                fh.YOUTUBE_FEED_FILTER_KEY: 'Video',
            }.get(section)
            return '{}{}'.format(title,
                's' if count > 1 and section != fh.ALL_FEED_FILTER_KEY else '')

        count = influencer.get_posts_section_count(
            section, brand=brand)

        data = {
            'count': count,
            'url': get_url(),
            'title': get_title(count),
        }
        return Response(data)
