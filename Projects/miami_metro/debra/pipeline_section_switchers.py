from collections import defaultdict

from django.core.urlresolvers import reverse

from debra.helpers import name_to_underscore
from debra.models import *
from debra.section_switchers import SectionSwitcherWrapper

# should go after from debra.models import *
from aggregate_if import Count, Max


class ApproveStatusSwitcherWrapper(SectionSwitcherWrapper):

    # DISABLED_SECTIONS = [IA.APPROVE_STATUS_MAYBE,]
    DISABLED_SECTIONS = [IA.APPROVE_STATUS_ARCHIVED,]

    @cached_property
    def queryset(self):
        queryset = super(ApproveStatusSwitcherWrapper, self).queryset
        queryset = queryset.exclude(approve_status__in=self.DISABLED_SECTIONS)
        return queryset

    @cached_property
    def sections(self):
        return [s for s in IA.APPROVE_STATUS
            if s[0] not in self.DISABLED_SECTIONS]

    @cached_property
    def counts(self):
        _qs = self.queryset.values('approve_status').annotate(
            Count('approve_status')
        )
        return {
            x['approve_status']: x['approve_status__count']
            for x in _qs
        }

    @cached_property
    def hidden(self):
        _hidden = []
        for i in [IA.APPROVE_STATUS_NOT_SENT,
                IA.APPROVE_STATUS_PENDING]:
            if self.counts.get(i, 0) == 0:
                _hidden.append(i)
        return _hidden

    @cached_property
    def urls(self):
        _urls = []
        for n, _ in self.sections:
            params = dict(approve_status=n)
            if self._context.get('preview'):
                params.update({
                    'preview': 1,
                })
            _urls.append('?' + '&'.join([
                '{}={}'.format(k, v) for k, v in params.items()]))
        return _urls

    @cached_property
    def extra(self):
        _extra = {}
        _extra.update({
            'class': {
                k:'{}_approval'.format(name_to_underscore(v))
                for k, v in self.sections
            },
        })
        return _extra
    

class PublicApproveStatusSwitcherWrapper(ApproveStatusSwitcherWrapper):

    DISABLED_SECTIONS = ApproveStatusSwitcherWrapper.DISABLED_SECTIONS + [
        IA.APPROVE_STATUS_ARCHIVED,
    ]


class CampaignStageSwitcherWrapper(SectionSwitcherWrapper):

    @cached_property
    def first_stage_with_unread_messages(self):
        return self._switcher.get_first_section_matching_criteria(
            lambda s: s.key >= 0 and s.extra.get('unread_count', 0) > 0)

    @cached_property
    def default_selected_section_value(self):
        if self._context['view'].search_query:
            return IJM.CAMPAIGN_STAGE_ALL
        if self.first_stage_with_unread_messages:
            val = self.first_stage_with_unread_messages.key
        else:
            val = super(CampaignStageSwitcherWrapper,
                self).default_selected_section_value
        if val in IJM.SANDBOX_STAGES:
            val = IJM.CAMPAIGN_STAGE_FINALIZING_DETAILS
        return val
    
    @cached_property
    def sections(self):
        return BrandJobPost.stages()

    @cached_property
    def urls(self):
        _urls = {
            n: '{}?campaign_stage={}'.format(reverse(
                'debra.job_posts_views.campaign_setup',
                args=(self._context['view'].campaign.id,)
            ), n) for n, _ in BrandJobPost.stages()
        }
        _urls.update({
            IJM.CAMPAIGN_STAGE_APPROVAL: reverse(
                'debra.job_posts_views.campaign_approval',
                args=(self._context['view'].campaign.id,)
            ),
            IJM.CAMPAIGN_STAGE_LOAD_INFLUENCERS: reverse(
                'debra.job_posts_views.campaign_load_influencers',
                args=(self._context['view'].campaign.id,)
            )
        })
        return _urls

    @cached_property
    def hidden(self):
        _hidden = []
        if not self._context['view'].pre_outreach_enabled:
            _hidden.append(IJM.CAMPAIGN_STAGE_APPROVAL)
        if not self._context['view'].campaign.info_json.get('signing_contract_on'):
            _hidden.append(IJM.CAMPAIGN_STAGE_CONTRACTS)
        if not self._context['view'].campaign.info_json.get('sending_product_on'):
            _hidden.append(IJM.CAMPAIGN_STAGE_LOGISTICS)

        for stage, name in BrandJobPost.stages():
            stage_settings = self._context['view'].campaign.info_json.get(
                'stage_settings', {}).get(str(stage), {})
            if stage_settings.get('send_contract') and stage < IJM.CAMPAIGN_STAGE_CONTRACTS:
                _hidden.append(IJM.CAMPAIGN_STAGE_CONTRACTS)
            if '{}_stage_disabled'.format(stage) in self._context['view'].campaign.tags_list:
                _hidden.append(stage)
        return _hidden

    @cached_property
    def extra(self):
        return {
            'unread_count': self.unread_counts,
            'class': {k:name_to_underscore(v) for k, v in BrandJobPost.stages()},
        }

    @cached_property
    def _counts(self):
        _qs = self.queryset.values(
            'campaign_stage'
        ).annotate(
            Count('campaign_stage'),
            unread_count=Count('campaign_stage', only=(
                Q(mailbox__has_been_read_by_brand=False))
            )
        )
        _counts = defaultdict(int)
        _unread_counts = defaultdict(int)
        for stage_data in _qs:
            key = min(IJM.SANDBOX_STAGES) if\
                stage_data['campaign_stage'] in\
                IJM.SANDBOX_STAGES else\
                stage_data['campaign_stage']
            _counts[key] += stage_data['campaign_stage__count']
            _unread_counts[key] += stage_data['unread_count']
        _counts.update({
            IJM.CAMPAIGN_STAGE_ALL: sum(_counts.values()),
            # IJM.CAMPAIGN_STAGE_APPROVAL: self._context.get(
            #     'view').pre_outreach_bloggers_count,
            IJM.CAMPAIGN_STAGE_APPROVAL: self.child_switchers.get(
                'approve_status_switcher'
            ).wrapper.counts.get(IA.APPROVE_STATUS_PENDING, 0),
            IJM.CAMPAIGN_STAGE_LOAD_INFLUENCERS: -1,
        })
        _unread_counts.update({
            IJM.CAMPAIGN_STAGE_ALL: sum(_unread_counts.values()),
        })
        return {
            'counts': _counts,
            'unread_counts': _unread_counts,
        }

    @cached_property
    def counts(self):
        return self._counts['counts']

    @cached_property
    def unread_counts(self):
        return self._counts['unread_counts']