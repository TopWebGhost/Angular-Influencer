from debra.helpers import PageSectionSwitcher
from debra.models import *
from debra import constants
from debra import serializers
from debra.pipeline_section_switchers import *


class BloggerNotesViewMixin(object):

    def pre_serialize_processor(self):
        super(BloggerNotesViewMixin, self).pre_serialize_processor()
        brand_user_mapping = {
            x.influencer_id:x
            for x in InfluencerBrandUserMapping.objects.filter(
                influencer__in=[p.influencer for p in self.paginated_queryset],
                user=self.user
            )
        }
        for p in self.paginated_queryset:
            p.agr_brand_user_mapping = brand_user_mapping.get(
                p.influencer.id) if p.influencer else None
            if p.agr_brand_user_mapping:
                p.agr_notes = p.agr_brand_user_mapping.notes
            else:
                p.agr_notes = None


class BloggersTableViewMixin(object):

    def pre_serialize_processor(self):
        super(BloggersTableViewMixin, self).pre_serialize_processor()
        _t0 = time.time()
        platforms_data = redis_cache.get_many([
            'plsd_{}'.format(p.influencer.id)
            for p in self.paginated_queryset if p.influencer
        ])
        print '* platforms data fetched ({} bytes), took {}'.format(
            sys.getsizeof(platforms_data), time.time() - _t0)
        _t0 = time.time()
        profile_pics = redis_cache.get_many([
            'pp_{}'.format(p.influencer.id)
            for p in self.paginated_queryset if p.influencer
        ])
        print '* profile pics fetched, took {}'.format(time.time() - _t0)

        # brand_user_mapping = {
        #     x.influencer_id:x
        #     for x in InfluencerBrandUserMapping.objects.filter(
        #         influencer__in=[p.influencer for p in self.paginated_queryset],
        #         user=self.request.user
        #     )
        # }
        for p in self.paginated_queryset:
            # p.agr_brand_user_mapping = brand_user_mapping.get(
            #     p.influencer.id) if p.influencer else None
            # if p.agr_brand_user_mapping:
            #     p.agr_notes = p.agr_brand_user_mapping.notes
            # else:
            #     p.agr_notes = None
            # p._campaign = self.campaign
            if p.influencer is not None:
                p.influencer._serialized_platforms = platforms_data.get(
                    'plsd_{}'.format(p.influencer.id))
                p.influencer._profile_pic = profile_pics.get('pp_{}'.format(
                    p.influencer.id))

    @cached_property
    def default_order_params(self):
        return [('id', 1),]


class CampaignViewMixin(object):

    def set_params(self, request, *args, **kwargs):
        super(CampaignViewMixin, self).set_params(request, *args, **kwargs)

        if kwargs.get('campaign'):
            self.campaign = kwargs.get('campaign')
        else:
            self.campaign = BrandJobPost.objects.select_related(
                'creator',
                'post_collection',
                'report__influencer_analytics_collection',
            ).get(id=kwargs.get('campaign_id'))
        self.pre_outreach_enabled = self.campaign.info_json.get(
            'approval_report_enabled', False)

    @property
    def context(self):
        print '** CampaignViewMixin'
        context = super(CampaignViewMixin, self).context
        context.update({
            'campaign': self.campaign,
            'InfluencerJobMapping': IJM,
            'IJM': IJM,
            'selected_tab': 'campaign',
        })
        return context

    def pre_serialize_processor(self):
        super(CampaignViewMixin, self).pre_serialize_processor()
        for p in self.paginated_queryset:
            p._campaign = self.campaign


class CampaignSetupViewMixin(object):

    @cached_property
    def brand(self):
        # @TODO: probably we should replace it with
        # self.campaign.creator
        return self.request.visitor['base_brand']
    
    def get_section_switchers(self):
        switchers = super(CampaignSetupViewMixin,self).get_section_switchers()
        switchers.update({
            'campaign_switcher': PageSectionSwitcher(
                constants.CAMPAIGN_SECTIONS, 'campaign_setup',
                url_args=(self.campaign.id,),
                extra_url_args={
                    'influencer_approval': (self.campaign.roi_report.id,)
                },
                # hidden=[] if pre_outreach_enabled else ['influencer_approval'],
            )
        })
        return switchers


class PipelineViewMixin(object):

    def set_params(self, request, *args, **kwargs):
        super(PipelineViewMixin, self).set_params(request, *args, **kwargs)
        
        try:
            self._campaign_stage = int(request.GET.get('campaign_stage'))
        except TypeError:
            self._campaign_stage = None

    def get_section_switchers(self):
        switchers = super(PipelineViewMixin, self).get_section_switchers()
        switchers.update({
            'section_switcher': CampaignStageSwitcherWrapper(
                queryset=self.campaign.candidates.all(),
                selected_section_value=self.campaign_stage,
                context=dict(view=self),    
                child_switchers={
                    'approve_status_switcher': ApproveStatusSwitcherWrapper(
                        queryset=self.campaign.influencer_collection.influenceranalytics_set.all(),
                        selected_section_value=getattr(
                            self, '_approve_status', None)
                        ).switcher
                }
            ).switcher,
        })
        return switchers

    @cached_property
    def campaign_stage(self):
        return self._campaign_stage

    @cached_property
    def pre_outreach_bloggers_count(self):
        try:
            sw = self.section_switchers.get(
                'section_switcher'
            ).wrapper.child_switchers['approve_status_switcher']
        except KeyError:
            print '* pre_outreach_bloggers_count: calculate'
            return self.campaign.influencer_collection.influenceranalytics_set.filter(
                approve_status=IA.APPROVE_STATUS_PENDING
            ).count(),
        else:
            print '* pre_outreach_bloggers_count: pre-defined'
            return sw.wrapper.counts.get(IA.APPROVE_STATUS_PENDING, 0)

    @cached_property
    def outreach_bloggers_count(self):
        sw = self.section_switchers.get('section_switcher').wrapper
        return sw.counts.get(IJM.CAMPAIGN_STAGE_ALL, 0)

    @cached_property
    def counts(self):
        _wrapper = self.section_switchers.get(
            'section_switcher').wrapper
        return {
            'total': _wrapper.counts.get(IJM.CAMPAIGN_STAGE_ALL),
            'current': #self.filtered_queryset.count()#\
                #if self.search_query else 
                _wrapper.counts.get(_wrapper.selected_section_value),
        }

    @property
    def context(self):
        print '** PipelineViewMixin'
        context = super(PipelineViewMixin, self).context
        # context.update(self.section_switchers)
        context.update({
            'influencers_count': self.counts['total'],
            'can_move_to_next_stage': self.section_switchers.get(
                'section_switcher').selected in [
                    IJM.CAMPAIGN_STAGE_PRE_OUTREACH,
                    IJM.CAMPAIGN_STAGE_WAITING_ON_RESPONSE,
                    IJM.CAMPAIGN_STAGE_NEGOTIATION,
                ] and self.request.visitor["base_brand"] and\
                    self.request.visitor["base_brand"].flag_skipping_stages_enabled,
        })
        return context


class PipelineTableViewMixin(object):

    @cached_property
    def serializer_mapping(self):
        return {
            IJM.CAMPAIGN_STAGE_APPROVAL: serializers.InfluencerApprovalReportTableSerializer,
            IJM.CAMPAIGN_STAGE_ALL: serializers.CampaignSetupAllTableSerializer,
            # -1: serializers.CampaignSetupArchivedTableSerializer,
            IJM.CAMPAIGN_STAGE_PRE_OUTREACH: serializers.CampaignSetupPreOutreachTableSerializer,
            IJM.CAMPAIGN_STAGE_WAITING_ON_RESPONSE: serializers.CampaignSetupWaitingOnResponseTableSerializer,
            IJM.CAMPAIGN_STAGE_NEGOTIATION: serializers.CampaignSetupNegotiationTableSerializer,
            IJM.CAMPAIGN_STAGE_FINALIZING_DETAILS: serializers.CampaignSetupSandboxTableSerializer,
            IJM.CAMPAIGN_STAGE_CONTRACTS: serializers.CampaignSetupSandboxTableSerializer,
            IJM.CAMPAIGN_STAGE_LOGISTICS: serializers.CampaignSetupSandboxTableSerializer,
            # IJM.CAMPAIGN_STAGE_FINALIZING_DETAILS: serializers.CampaignSetupFinalizingDetailsTableSerializer,
            # IJM.CAMPAIGN_STAGE_CONTRACTS: serializers.CampaignSetupContractTableSerializer,
            # IJM.CAMPAIGN_STAGE_LOGISTICS: serializers.CampaignSetupLogisticsTableSerializer,
            IJM.CAMPAIGN_STAGE_UNDERWAY: serializers.CampaignSetupUnderwayTableSerializer,
            IJM.CAMPAIGN_STAGE_COMPLETE: serializers.CampaignSetupCompleteTableSerializer,
            IJM.CAMPAIGN_STAGE_ARCHIVED: serializers.CampaignSetupArchivedTableSerializer,
        }

    @cached_property
    def serializer_class(self):
        _wrapper = self.section_switchers.get(
            'section_switcher').wrapper
        return self.serializer_mapping.get(
            _wrapper.selected_section_value)

    @property
    def context(self):
        print '** PipelineTableViewMixin'
        _wrapper = self.section_switchers.get('section_switcher').wrapper
        context = super(PipelineTableViewMixin, self).context
        context.update({
            'table_id': 'campaign_pipeline_table',
            'table_classes': ' '.join([
                'messages-table',
                'pipeline_{}'.format(
                    name_to_underscore(
                        dict(BrandJobPost.stages()).get(
                            _wrapper.selected_section_value, 'all')
                    )
                )
            ]),
            'show_conversations': _wrapper.selected_section_value == IJM.CAMPAIGN_STAGE_ALL or\
                _wrapper.selected_section_value > IJM.CAMPAIGN_STAGE_PRE_OUTREACH,
            'all_headers': serializers.CampaignSetupTableSerializer.get_headers(
                visible_columns=[x[0]
                for x in self.serializer_class.get_visible_fields()]
            ),
        })
        return context


class BloggerApprovalViewMixin(object):

    def set_params(self, request, *args, **kwargs):
        super(BloggerApprovalViewMixin, self).set_params(request, *args, **kwargs)

        try:
            self._approve_status = int(request.GET.get('approve_status'))
        except TypeError:
            self._approve_status = None

    @property
    def approval_switcher(self):
        raise NotImplementedError

    @cached_property
    def context(self):
        context = super(BloggerApprovalViewMixin, self).context
        context.update({
            'approval_switcher': self.approval_switcher,
            'IA': InfluencerAnalytics,
            'public_link': self.campaign.roi_report.get_public_url(self.user),
        })
        return context

    @property
    def queryset(self):
        return self.campaign.influencer_collection.influenceranalytics_set.all()

    @property
    def filtered_queryset(self):
        qs = super(BloggerApprovalViewMixin, self).filtered_queryset

        _selected_value = self.approval_switcher.wrapper.selected_section_value
        if _selected_value is not None:
            qs = qs.filter(approve_status=_selected_value)
        return qs

    @property
    def annotated_queryset(self):
        qs = super(BloggerApprovalViewMixin, self).annotated_queryset
        return qs.select_related(
            'influencer__demographics_locality',
            # 'influencer__platform_set',
            # 'influencer__shelf_user__userprofile',
        )

    @cached_property
    def counts(self):
        return {
            'total': sum(self.approval_switcher.wrapper.counts.values()),
            'current': self.approval_switcher.wrapper.counts.get(
                self.approval_switcher.wrapper.selected_section_value, 0),
        }