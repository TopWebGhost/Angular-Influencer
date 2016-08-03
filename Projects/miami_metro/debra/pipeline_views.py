from collections import defaultdict

from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404

from debra.models import *
from debra import constants
from debra import serializers
from debra.helpers import PageSectionSwitcher, name_to_underscore, update_model
from debra.base_views import BaseView, BaseTableViewMixin
from debra.pipeline_section_switchers import (
    ApproveStatusSwitcherWrapper, PublicApproveStatusSwitcherWrapper,
    CampaignStageSwitcherWrapper,)
from debra.pipeline_mixins import *

# should go after from debra.models import *
from aggregate_if import Count, Max


'''
    BrandJobPost.stages() -- all stages
    BrandJobPost.pipeline_stages() - only pipeline stages

    There are 4 main pages:
        * Load Influencers Page
        * Private Approval Page
        * Public Approval Page
        * Campaign Pipeline Pages (one page for each stage)
    
'''


class LoadInfluencersView(PipelineViewMixin, CampaignSetupViewMixin,
        CampaignViewMixin, BaseView):
    
    def get(self, request, *args, **kwargs):
        self.set_params(request, *args, **kwargs)
        return render(
            request,
            'pages/job_posts/campaign_load_influencers.html',
            self.context
        )

    def post(self, request, *args, **kwargs):
        self.set_params(request, *args, **kwargs)
        data = json.loads(request.body)
        if request.GET.get('add_to_approval_report'):
            self.campaign.influencer_collection.merge_influencers(
                [data.get('inf_id')], celery=True)
        elif request.GET.get('add_tag_to_approval_report'):
            tag = InfluencersGroup.objects.get(id=data.get('tag_id'))
            InfluencerAnalyticsCollection.objects.from_tag(
                tag, self.campaign.influencer_collection)
        elif request.GET.get('add_to_approval_report_bulk'):
            tag_ids = [
                tag['id'] for tag in data.get('tags', [])
                if tag.get('selected')
            ]
            post_collection_ids = [
                pc['id'] for pc in data.get('post_collections', [])
                if pc.get('selected')
            ]
            tags = InfluencersGroup.objects.filter(id__in=tag_ids)
            post_collections = PostAnalyticsCollection.objects.filter(
                id__in=post_collection_ids)

            for tag in tags:
                InfluencerAnalyticsCollection.objects.from_tag(
                    tag,
                    self.campaign.influencer_collection,
                    campaign=self.campaign,
                    approved=not self.pre_outreach_enabled,
                )
            for pc in post_collections:
                InfluencerAnalyticsCollection.objects.from_post_collection(
                    pc,
                    self.campaign.influencer_collection,
                    campaign=self.campaign,
                    approved=not self.pre_outreach_enabled,
                )
        return HttpResponse()

    @cached_property
    def campaign_stage(self):
        return IJM.CAMPAIGN_STAGE_LOAD_INFLUENCERS

    @cached_property
    def context(self):
        context = super(LoadInfluencersView, self).context
        context.update({
            'tags_list': self.brand.get_visible_tags_list(),
            'post_collections_list': self.brand.get_visible_post_collections_list(
                with_counts=True),
            'success_redirect_url': reverse(
                'debra.job_posts_views.campaign_approval',
                args=(self.campaign.id,)
            ) if self.pre_outreach_enabled else reverse(
                'debra.job_posts_views.campaign_setup',
                args=(self.campaign.id,)
            ) + '?campaign_stage=0',
        })
        return context


class BloggerApprovalView(BloggerApprovalViewMixin, PipelineTableViewMixin,
        PipelineViewMixin, CampaignSetupViewMixin, CampaignViewMixin,
        BloggerNotesViewMixin, BloggersTableViewMixin, BaseTableViewMixin,
        BaseView):

    def get(self, request, *args, **kwargs):
        self.set_params(request, *args, **kwargs)

        if not self.pre_outreach_enabled:
            raise Http404()

        return render(
            request,
            'pages/job_posts/campaign_approval.html',
            self.context
        )

    def post(self, request, *args, **kwargs):
        if request.GET.get('delete_pending'):
            self.influencer_collection.influenceranalytics_set.filter(
                approve_status=IA.APPROVE_STATUS_PENDING
            ).delete()
        return HttpResponse()

    @cached_property
    def approval_switcher(self):
        return self.section_switchers.get(
            'section_switcher'
        ).wrapper.child_switchers.get(
            'approve_status_switcher'
        )
    
    @cached_property
    def campaign_stage(self):
        return IJM.CAMPAIGN_STAGE_APPROVAL

    @cached_property
    def context(self):
        context = super(BloggerApprovalView, self).context
        return context

    @cached_property
    def hidden_fields(self):
        _hidden_fields = []
        _selected_value = self.section_switchers.get(
            'section_switcher'
        ).wrapper.child_switchers.get(
            'approve_status_switcher'
        ).wrapper.selected_section_value
        if _selected_value not in [IA.APPROVE_STATUS_PENDING, IA.APPROVE_STATUS_ARCHIVED]:
            _hidden_fields.append('remove_info')
        return _hidden_fields


class PublicBloggerApprovalView(BloggerApprovalViewMixin, CampaignViewMixin,
        BloggerNotesViewMixin, BloggersTableViewMixin, BaseTableViewMixin, BaseView):

    def set_params(self, request, *args, **kwargs):
        campaign = BrandJobPost.objects.select_related(
            'report', 'influencer_analytics_collection',
        ).filter(
            report_id=kwargs.get('report_id'),
            creator_id=kwargs.get('brand_id'),
        )[0]
        user = User.objects.get(id=kwargs['user_id'])
        if kwargs['hash_key'] != campaign.report.get_public_hash(user):
            raise Http404()
        kwargs.update({
            'campaign': campaign
        })
        super(PublicBloggerApprovalView, self).set_params(
            request, *args, **kwargs)
        self.user = user
        self.brand_id = kwargs.get('brand_id')
        self.preview = self.request.GET.get('preview')

    def get(self, request, *args, **kwargs):
        self.set_params(request, *args, **kwargs)

        if not self.pre_outreach_enabled:
            raise Http404()

        print 'USER:', self.user.is_authenticated()

        return render(
            request,
            'pages/job_posts/campaign_approval_public.html',
            self.context
        )

    @cached_property
    def queryset(self):
        return self.campaign.influencer_collection.influenceranalytics_set.exclude(
            archived=True)

    @cached_property
    def approval_switcher(self):
        return self.section_switchers.get(
            'approve_status_switcher')

    @cached_property
    def serializer_class_level_context(self):
        context = super(PublicBloggerApprovalView,
            self).serializer_class_level_context
        context.update({
            'user': self.user,
        })
        return context

    @cached_property
    def context(self):
        print '** PublicBloggerApprovalView'
        context = super(PublicBloggerApprovalView, self).context
        context.update({
            'public_approval_page': True,
            'preview': self.preview,
            'report': self.campaign.report,
            'brand_id': self.brand_id,
            'user_id': self.user.id,
            # 'user': self.user,
            'collection': self.campaign.influencer_collection,
            'landing_page': not self.request.user.is_authenticated(),
            'search_page': True,
            'reportOwner': self.user.userprofile,
            'approve_statuses': [
                {'value': IA.APPROVE_STATUS_YES, 'text': 'Yes'},
                {'value': IA.APPROVE_STATUS_NO, 'text': 'No'},
                {'value': IA.APPROVE_STATUS_MAYBE, 'text': 'Maybe'},
            ]
        })
        return context
    
    def get_section_switchers(self):
        return {
            'approve_status_switcher': PublicApproveStatusSwitcherWrapper(
                queryset=self.campaign.influencer_collection.influenceranalytics_set.exclude(
                    archived=True),
                selected_section_value=self._approve_status,
                context={'preview': self.preview}).switcher,
        }

    @cached_property
    def serializer_class(self):
        return serializers.PublicInfluencerApprovalReportTableSerializer


class CampaignPipelineView(PipelineTableViewMixin, PipelineViewMixin,
        CampaignSetupViewMixin, CampaignViewMixin, BloggerNotesViewMixin,
        BloggersTableViewMixin, BaseTableViewMixin, BaseView):

    def set_params(self, request, *args, **kwargs):
        super(CampaignPipelineView, self).set_params(request, *args, **kwargs)
        self.search_query = request.GET.get('q')

    def get(self, request, *args, **kwargs):
        self.set_params(request, *args, **kwargs)
        if request.is_ajax():
            return HttpResponse()
        else:
            '''
            Redirection logic:

            1) if we have selected a campaign stage manually - just go to that stage
            2) otherwise:
                a) if there are any bloggers on any of the post-approval stages
                (including the archived bloggers):
                    - if there are any unread messages - go to the first stage
                        which has unread messages in it;
                    - otherwise, just go to the first non-empty stage;
                b) otherwise (if there are no bloggers on any of the post-approval stages):
                    - if approval form is turned on and there are pending bloggers on the
                        approval stage - just go there (to the pending bloggers)
                    - otherwise, go to the 'load influencers' page
            '''
            if self.campaign_stage is None:
                if self.outreach_bloggers_count:
                    pass
                else:
                    if self.pre_outreach_enabled and self.pre_outreach_bloggers_count > 0:
                        return redirect(reverse(
                            'debra.job_posts_views.campaign_approval', args=(self.campaign.id,)))
                    else:
                        return redirect(reverse(
                            'debra.job_posts_views.campaign_load_influencers', args=(self.campaign.id,)))
            return render(
                request,
                'pages/job_posts/campaign_setup_details.html',
                self.context
            )

    def post(self, request, *args, **kwargs):
        self.set_params(request, *args, **kwargs)
        data = json.loads(request.body)
        if request.GET.get('set_visible_columns'):
            update_model({
                'modelName': 'BrandJobPost',
                'id': self.campaign.id,
                'json_fields': {
                    'info': {
                        'visible_columns': {
                            str(self.section_switchers.get(
                                'section_switcher').wrapper.selected_section_value): data['columns'],
                        }
                    }
                }
            })
        return HttpResponse()

    @cached_property
    def default_order_params(self):
        _selected_value = self.section_switchers.get(
            'section_switcher').wrapper.selected_section_value
        if _selected_value == IJM.CAMPAIGN_STAGE_PRE_OUTREACH:
            return super(CampaignPipelineView, self).default_order_params
        return [('mailbox__has_been_read_by_brand', 0), ('agr_last_message', 1)]

    @cached_property
    def serializer_context(self):
        data = super(CampaignPipelineView, self).serializer_context
        if self.section_switchers.get(
                'section_switcher').wrapper.selected_section_value in [
                    IJM.CAMPAIGN_STAGE_FINALIZING_DETAILS,
                    IJM.CAMPAIGN_STAGE_COMPLETE]:
            posts_list = list(
                self.campaign.participating_post_analytics.exclude(
                    post__platform__platform_name='Instagram',
                    post__post_image__isnull=True
                ).values_list(
                    'post__url',
                    'post__title',
                    'post__platform__platform_name',
                    'post__influencer'
                ).order_by('post__platform__platform_name')
            )
            data.update({
                'posts': posts_list,
            })
        return data

    @cached_property
    def queryset(self):
        return self.campaign.candidates.all()

    @cached_property
    def filtered_queryset(self):
        qs = super(CampaignPipelineView, self).filtered_queryset
        _selected_value = self.section_switchers.get(
            'section_switcher').wrapper.selected_section_value
        if _selected_value > IJM.CAMPAIGN_STAGE_ALL:
            if _selected_value in IJM.SANDBOX_STAGES:
                qs = qs.filter(
                    campaign_stage__in=IJM.SANDBOX_STAGES)
            else:
                qs = qs.filter(campaign_stage=_selected_value)
        if self.search_query:
            qs = qs.filter(
                Q(influencer_analytics__influencer__name__icontains=self.search_query) |
                Q(influencer_analytics__influencer__blogname__icontains=self.search_query) |
                Q(influencer_analytics__influencer__blog_url__icontains=self.search_query) |
                Q(mailbox__influencer__name__icontains=self.search_query) |
                Q(mailbox__influencer__blogname__icontains=self.search_query) |
                Q(mailbox__influencer__blog_url__icontains=self.search_query)
            )
        return qs

    @cached_property
    def annotated_queryset(self):
        qs = super(CampaignPipelineView, self).annotated_queryset
        if self.section_switchers.get(
                'section_switcher').wrapper.selected_section_value not in [
                    IJM.CAMPAIGN_STAGE_PRE_OUTREACH, IJM.CAMPAIGN_STAGE_APPROVAL]:
            qs = qs.annotate(
                agr_opened_count=Count(
                    'mailbox__threads',
                    only=(
                        Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
                        (
                            Q(mailbox__threads__type=MailProxyMessage.TYPE_OPEN) |
                            Q(mailbox__threads__type=MailProxyMessage.TYPE_CLICK)
                        )
                    )
                ),
                agr_emails_count=Count(
                    'mailbox__threads',
                    only=(
                        # Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
                        Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL)
                    )
                ),
                agr_last_message=Max(
                    'mailbox__threads__ts',
                    only=(
                        # Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
                        Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL)
                    )
                ),
                agr_last_sent=Max(
                    'mailbox__threads__ts',
                    only=(
                        # Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
                        Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL) &
                        Q(mailbox__threads__direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER)
                    )
                ),
                agr_last_reply=Max(
                    'mailbox__threads__ts',
                    only=(
                        # Q(mailbox__threads__mandrill_id__regex=r'.(.)+') &
                        Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL) &
                        Q(mailbox__threads__direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND)
                    )
                ),
            )
        qs = qs.select_related(
            'contract',
            'influencer_analytics',
        )
        prefetch_related = [
            # 'mailbox__influencer__shelf_user__userprofile'
            'mailbox__influencer__demographics_locality',
        ]
        # if settings.DEBUG and not settings.USE_PRODUCTION_MEMCACHED:
        #     prefetch_related.append('mailbox__influencer__platform_set')
        qs = qs.prefetch_related(*prefetch_related)
        # qs = qs.prefetch_related(
        #     # 'mailbox__influencer__platform_set',
        #     'mailbox__influencer__shelf_user__userprofile',
        #     # 'job',
        #     # 'contract',
        #     # 'influencer_analytics__influencer__shelf_user__userprofile',
        #     # 'influencer_analytics__influencer__platform_set',
        # )
        return qs

    @cached_property
    def hidden_fields(self):
        hidden_fields = []
        if not self.campaign.info_json.get('blogger_additional_info_on') or not self.campaign.info_json.get('sending_product_on'):
            hidden_fields.append('product_details')
        if not self.campaign.info_json.get('product_links_on') or not self.campaign.info_json.get('sending_product_on'):
            hidden_fields.append('product_url')
        if self.campaign.info_json.get('same_product_url') or not self.campaign.info_json.get('do_select_url') or not self.campaign.info_json.get('sending_product_on'):
            hidden_fields.append('restrictions')
        if not self.campaign.date_requirements_on:
            hidden_fields.append('date_requirements')
        if not self.campaign.info_json.get('sending_product_on'):
            hidden_fields.append('product_info')
            hidden_fields.append('shipping_details')
        if not self.campaign.info_json.get('tracking_codes_on'):
            hidden_fields.append('tracking_code_details')
        # if not self.campaign.creator.flag_post_approval_enabled:
        #     hidden_fields.append('post_approval_details')
        # if not self.campaign.info_json.get('signing_contract_on'):
        #     hidden_fields.append('contract_details')
        #     hidden_fields.append('contract_actions')
        if not self.campaign.payment_details_on:
            hidden_fields.append('paypal')

        if '{}_stage_disabled'.format(IJM.CAMPAIGN_STAGE_NEGOTIATION) in self.campaign.tags_list:
            hidden_fields.append('final_rate')

        _selected_value = self.section_switchers.get(
            'section_switcher').wrapper.selected_section_value
        if _selected_value == IJM.CAMPAIGN_STAGE_FINALIZING_DETAILS:
            if self.campaign.first_stage == _selected_value:
                hidden_fields.extend([
                    'subject',
                ])
            else:
                hidden_fields.extend([
                    'blog_info',
                    'instagram_info',
                    'pinterest_info',
                    'facebook_info',
                    'twitter_info',
                    'youtube_info',
                ])

        return hidden_fields

    def pre_serialize_processor(self):
        super(CampaignPipelineView, self).pre_serialize_processor()
        if self.section_switchers.get(
                'section_switcher').wrapper.selected_section_value not in [
                    IJM.CAMPAIGN_STAGE_PRE_OUTREACH]:
            _t0 = time.time()
            mp_subjects = redis_cache.get_many([
                'sb_{}'.format(p.mailbox.id) for p in self.paginated_queryset
                if p.mailbox
            ])
            print '* fetching thread subjects took {}'.format(
                time.time() - _t0)
            for p in self.paginated_queryset:
                if p.mailbox is not None:
                    p.agr_mailbox_subject = mp_subjects.get('sb_{}'.format(
                        p.mailbox.id))

        for p in self.paginated_queryset:
            if p.contract is not None:
                p.contract.IJM = p
            if p.contract is not None:
                p.contract.agr_campaign = self.campaign
