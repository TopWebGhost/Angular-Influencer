import json
import threading
import time
import operator
from htmlmin import minify

from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.core.cache import get_cache
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import FieldError


def bake_list_details_jobpost_partial(job_id, show_candidates=True, show_applicants=False, page=1, request=None):
    from debra.models import MailProxyMessage, BrandJobPost, InfluencerJobMapping, InfluencerGroupMapping, Influencer, InfluencersGroup
    import datetime
    from aggregate_if import Count, Sum, Min, Max
    from email import message_from_string
    from debra.helpers import paginate
    from debra.serializers import influencer_info

    jobs = BrandJobPost.objects
    job = jobs.extra(
        select={
            "invited_count_sql": """
                SELECT DISTINCT COUNT(*)
                FROM 
                (SELECT influencer_id
                FROM debra_influencerjobmapping as ijm 
                    JOIN debra_mailproxy as mp
                ON ijm.mailbox_id=mp.id
                WHERE ijm.job_id=debra_brandjobpost.id
                    AND ijm.status IN (2, 3, 4)) AS F
            """,
            #     UNION
            #     SELECT influencer_id
            #     FROM debra_influencerjobmapping as ijm 
            #         JOIN debra_influencergroupmapping as igm
            #     ON ijm.mapping_id=igm.id
            #     WHERE ijm.job_id=debra_brandjobpost.id
            #         AND ijm.status IN (2, 3, 4)) as F
            # """,
            "applied_count_sql": """
                SELECT DISTINCT COUNT(*)
                FROM
                (SELECT influencer_id
                FROM debra_influencerjobmapping as ijm 
                    JOIN debra_mailproxy as mp
                ON ijm.mailbox_id=mp.id
                WHERE ijm.job_id=debra_brandjobpost.id
                    AND ijm.status=5
                UNION
                SELECT influencer_id
                FROM debra_mailproxy as mp
                    JOIN debra_mailproxymessage as mpm
                        ON mpm.thread_id=mp.id
                    JOIN debra_influencerjobmapping as ijm
                        ON ijm.mailbox_id=mp.id
                WHERE ijm.job_id=debra_brandjobpost.id
                    AND mpm.type=1
                    AND mpm.direction=2
                ) as S
                """
                # UNION
                # SELECT influencer_id
                # FROM debra_influencerjobmapping as ijm 
                #     JOIN debra_influencergroupmapping as igm
                # ON ijm.mapping_id=igm.id
                # WHERE ijm.job_id=debra_brandjobpost.id
                #     AND ijm.status=5
        }
    ).get(id=job_id)
    brand = job.creator
    base_brand = job.oryg_creator

    if not show_candidates and not show_applicants:
        show_candidates = True
    elif show_applicants and show_candidates:
        show_applicants = False

    candidates = []
    applicants = []

    if job:
        candidates_qs = InfluencerJobMapping.objects
        candidates_qs = candidates_qs.prefetch_related(
            # 'mailbox__threads',
            'mailbox',
            'mailbox__influencer__platform_set',
            'mailbox__influencer__shelf_user__userprofile',
            # 'mapping__mailbox__threads',
            'mapping__mailbox',
            'mapping__influencer__shelf_user__userprofile',
            # 'mapping__influencer__shelf_user',
            'mapping__influencer__platform_set',
            # 'mapping__influencer',
            'mapping',
        ).extra(
            select={
                "first_message": """
                    SELECT mpm.msg
                    FROM debra_mailproxymessage as mpm
                    WHERE thread_id=debra_influencerjobmapping.mailbox_id
                        AND mpm.type=1
                    ORDER BY mpm.ts
                    LIMIT 1
                """
            }
        ).annotate(
            emails_count_agr=Count('mailbox__threads', only=(Q(mailbox__threads__mandrill_id__regex=r'.(.)+') & Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL))),
            opened_count_agr=Count('mailbox__threads', only=(Q(mailbox__threads__mandrill_id__regex=r'.(.)+') & (Q(mailbox__threads__type=MailProxyMessage.TYPE_OPEN) | Q(mailbox__threads__type=MailProxyMessage.TYPE_CLICK)))),
            post_stamp_agr=Min('mailbox__threads__ts', only=(Q(mailbox__threads__mandrill_id__regex=r'.(.)+') & Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL))),
            reply_stamp_agr=Max('mailbox__threads__ts', only=(Q(mailbox__threads__mandrill_id__regex=r'.(.)+') & Q(mailbox__threads__type=MailProxyMessage.TYPE_EMAIL))),
            applied_agr=Count('mailbox__threads', only=(Q(mailbox__threads__mandrill_id__regex=r'.(.)+') & Q(mailbox__threads__direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND)))
        ).order_by('-reply_stamp_agr').exclude(reply_stamp_agr__isnull=True)

        get_subject = lambda msg: message_from_string(msg.encode('utf-8'))['subject']

        candidates_qs = candidates_qs.filter(job=job).exclude(status=InfluencerJobMapping.STATUS_REMOVED)

        applicants_qs = candidates_qs.filter(
            Q(applied_agr__gt=0) | Q(status=InfluencerJobMapping.STATUS_ACCEPTED)
        )

        qs = paginate(candidates_qs if show_candidates else applicants_qs,
            page=page, count=job.invited_count_sql if show_candidates \
            else job.applied_count_sql)
        
        for mapping in qs:
            mapping.__dict__.update(influencer_info(
                mapping.influencer, request=request))
            mapping.email_subject_agr = get_subject(mapping.first_message)
            mapping.applied_flag = mapping.applied_agr > 0 or \
                mapping.status == InfluencerJobMapping.STATUS_ACCEPTED

    context = {
        'selected_tab': 'outreach',
        'sub_page': 'job_posts',
        'show_candidates': show_candidates,
        'show_applicants': show_applicants,
        'candidates': qs if show_candidates else [],
        'applicants':  qs if show_applicants else [],
        'items': qs,
        'job': job,
        'request': request,
        'status_choices': InfluencerGroupMapping.STATUS,
        'visitor': {
            'brand': brand,
            'base_brand': base_brand,
            'user': base_brand.get_owner_user_profile()
        }
    }

    if request:
        context["visitor"]["user"] = request.visitor["user"]

    partial = render_to_string('pages/job_posts/job_candidates_list_partial.html', context)
    # cache = get_cache('long')
    # cache.set("partial_list_details_jobpost_%s" % job_id, partial)
    return partial


def bake_list_details_jobpost_partial_async(*args, **kwargs):
    threading.Thread(
        target=bake_list_details_jobpost_partial,
        args=args,
        kwargs=kwargs
    ).start()


def bake_list_details_partial(group_id, page=1, request=None, for_admin=False):
    from debra.models import (
        BrandJobPost, InfluencerJobMapping, InfluencerGroupMapping, Influencer,
        InfluencersGroup, MailProxy)
    from debra.helpers import paginate
    from debra.serializers import influencer_info
    ig = InfluencersGroup.objects.prefetch_related(
        'owner_brand',
        'creator_brand'
    )
    group_id = int(group_id)

    group = ig.get(id=group_id)
    brand = group.owner_brand
    base_brand = group.creator_brand

    influencers_qs = Influencer.objects.filter(
        group_mapping__group_id=group_id
    ).prefetch_related(
        'platform_set',
        'group_mapping__group',
        'group_mapping__jobs__mailbox',
        'group_mapping__jobs__job',
        'mails__candidate_mapping__job',
        'shelf_user__userprofile'
    ).extra(
        select={
            "status": """
                SELECT igm.status
                FROM debra_influencergroupmapping as igm
                    JOIN debra_influencersgroup as ig
                ON igm.group_id=ig.id
                WHERE igm.influencer_id=debra_influencer.id
                LIMIT 1
            """
        },
        where=["""status IS NOT NULL AND status <> 1"""]
    ).distinct()

    influencers = paginate(influencers_qs, page=page, paginate_by=50)

    brand_groups = filter(
        lambda x: not x.archived and x.creator_brand_id == base_brand.id,
        brand.influencer_groups.all()
    )

    brand_groups.sort(key=lambda x: x.name)

    all_groups_global = [{'id': g.id, 'name': g.name} for g in brand_groups]

    for influencer in influencers:
        status = influencer.status
        groups_in = map(lambda x: x.group,\
            filter(lambda x: x.status != InfluencerGroupMapping.STATUS_REMOVED,\
                influencer.group_mapping.all()
            )
        )
        groups_in = filter(
            lambda x: x and not x.archived and x.owner_brand_id == brand.id,
            set(groups_in)
        )

        other_groups = filter(lambda x: x.id != group_id, groups_in)

        all_groups = []
        all_jobs = []
        job_ids = []
        jobs = []
        for brand_group in brand_groups:
            all_groups.append({
                'id': brand_group.id,
                'name': brand_group.name,
                'selected': brand_group in groups_in,
                'type': 'collection',
                'toggled': False
            })
        for mapping in influencer.group_mapping.all():
            for job_mapping in mapping.jobs.all():
                jobs.append(job_mapping.job)
        for mail in influencer.mails.all():
            for candidate in mail.candidate_mapping.all():
                jobs.append(candidate.job)
        jobs = filter(lambda x: x and not x.archived and \
            x.creator_id == brand.id and \
            x.oryg_creator_id == base_brand.id, jobs
        )
        jobs = set(jobs)
        for job in jobs:
            all_jobs.append((job.id, job.title,))
            job_ids.append(job.id)
        influencer.__dict__.update(influencer_info(influencer, status=status,\
            all_jobs_list=all_jobs, job_ids_list=job_ids,\
            other_groups_list=other_groups,
            all_groups_json=json.dumps(all_groups))
        )

    context = {
        'sub_page': 'favorited',
        'selected_tab': 'outreach',
        'influencers': influencers,
        'groups_list': json.dumps(all_groups_global),
        'group': group,
        'status_choices': InfluencerGroupMapping.STATUS,
        'request': request,
        'visitor': {
            'brand': brand,
            'base_brand': base_brand,
            'user': base_brand.get_owner_user_profile()
        }
    }

    if request:
        context["visitor"]["user"] = request.visitor["user"]

    tmpl_name = "pages/job_posts/"\
                "bloggers_favorited_table{}_partial.html".format(
                    '_for_admin' if for_admin else '')

    partial = render_to_string(tmpl_name, context)
    # cache = get_cache('long')
    # cache.set("partial_list_details_%s" % group_id, partial)
    return partial


def bake_list_details_partial_async(*args, **kwargs):
    threading.Thread(
        target=bake_list_details_partial,
        args=args,
        kwargs=kwargs
    ).start()


def bake_list_messages_partial(brand, base_brand, campaign_id=None,
    collection_id=None, campaigns=None, collections=None, page=1,
    sort_by=None, sort_direction=None, show_all=False, show_direct=False,
    request=None, stage_selected=None, search_query=None, headers=None,
    paginate_by=None):
    from debra.models import (
        BrandJobPost, InfluencerJobMapping, InfluencerGroupMapping, Influencer,
        InfluencersGroup, MailProxyMessage, Platform, MailProxy)
    import datetime
    from aggregate_if import Count, Sum, Min, Max
    from email import message_from_string
    from collections import namedtuple, Counter
    from debra.helpers import multikeysort
    from debra.serializers import influencer_info

    NON_SORTABLE_FIELD_NUMBERS = [3]

    if stage_selected not in [x[0] for x in MailProxy.STAGE]:
        stage_selected = None

    t0 = time.time()

    mailboxes_qs = base_brand.mails.exclude(threads__isnull=True)

    mailboxes_qs = mailboxes_qs.annotate(
        emails_count_agr=Count('threads', only=(Q(threads__mandrill_id__regex=r'.(.)+') & Q(threads__type=MailProxyMessage.TYPE_EMAIL))),
        opened_count_agr=Count('threads', only=(Q(threads__mandrill_id__regex=r'.(.)+') & (Q(threads__type=MailProxyMessage.TYPE_OPEN) | Q(threads__type=MailProxyMessage.TYPE_CLICK)))),
        post_stamp_agr=Min('threads__ts', only=(Q(threads__mandrill_id__regex=r'.(.)+') & Q(threads__type=MailProxyMessage.TYPE_EMAIL))),
        reply_stamp_agr=Max('threads__ts', only=(Q(threads__mandrill_id__regex=r'.(.)+') & Q(threads__type=MailProxyMessage.TYPE_EMAIL))),
    )

    mailboxes_qs = mailboxes_qs.exclude(emails_count_agr=0)

    # if type(campaign) == type(1):
    #     mailboxes_qs = mailboxes_qs.filter(candidate_mapping__job_id=campaign)
    select_dict = {
    }

    if campaign_id is not None or show_direct:
        select_dict.update({
            "campaign_id": """
                SELECT bjp.id
                FROM debra_influencerjobmapping as ijm
                    JOIN debra_brandjobpost as bjp
                        ON ijm.job_id=bjp.id
                WHERE ijm.mailbox_id=debra_mailproxy.id
                LIMIT 1
            """
        })

    if collection_id is not None or show_direct:
        select_dict.update({
            "collection_id": """
                SELECT id 
                FROM (
                    (SELECT ig.id, ig.archived, ig.name
                    FROM debra_influencerjobmapping as ijm
                        JOIN debra_influencergroupmapping as igm
                            ON ijm.mapping_id=igm.id
                        JOIN debra_influencersgroup as ig
                            ON igm.group_id=ig.id
                    WHERE ijm.mailbox_id=debra_mailproxy.id
                    LIMIT 1)
                    UNION
                    (SELECT ig.id, ig.archived, ig.name
                    FROM debra_influencergroupmapping as igm
                        JOIN debra_influencersgroup as ig
                            ON igm.group_id=ig.id
                    WHERE igm.mailbox_id=debra_mailproxy.id
                    LIMIT 1)
                ) as SQ
                LIMIT 1
            """
        })

    mailboxes_qs = mailboxes_qs.extra(select=select_dict)

    filtered = None
    if campaign_id is not None:
        campaign_id = int(campaign_id)
        filtered = map(lambda x: x[0], filter(
            lambda x: x[1] is not None and (campaign_id == 0 or x[1] == campaign_id),
            mailboxes_qs.values_list('id', 'campaign_id')
        ))
        mailboxes_qs = mailboxes_qs.filter(id__in=filtered)

    if collection_id is not None:
        collection_id = int(collection_id)
        filtered = map(lambda x: x[0], filter(
            lambda x: x[1] is not None and (collection_id == 0 or x[1] == collection_id),
            mailboxes_qs.values_list('id', 'collection_id')
        ))
        mailboxes_qs = mailboxes_qs.filter(id__in=filtered)

    if show_direct:
        filtered = map(lambda x: x[0], filter(
            lambda x: x[1] is None and x[2] is None,
            mailboxes_qs.values_list('id', 'collection_id', 'campaign_id')
        ))
        mailboxes_qs = mailboxes_qs.filter(id__in=filtered)

    if search_query:
        mailboxes_qs = mailboxes_qs.filter(
            Q(influencer__name__icontains=search_query) |
            Q(influencer__blogname__icontains=search_query) |
            Q(influencer__blog_url__icontains=search_query)
        )

    stage_counts = dict(Counter(mailboxes_qs.values_list('stage', flat=True)))
    stages_list = [
        {'value': k, 'text': v, 'count': stage_counts.get(k, 0)}
        for k, v in MailProxy.STAGE
    ]

    if stage_selected is not None:
        mailboxes_qs = mailboxes_qs.filter(stage=stage_selected)

    mailboxes_qs = mailboxes_qs.prefetch_related(
        'influencer__platform_set', # platform_name, url_not_found, total_numlikes, num_followers
        'influencer__shelf_user__userprofile',
    )

    if request.user.userprofile.flag_can_edit_contracts:
        mailboxes_qs = mailboxes_qs.prefetch_related(
            'candidate_mapping'
        )

    get_subject = lambda msg: message_from_string(msg.encode('utf-8'))['subject']

    number_2_field = {
        1: 'influencer__name',
        2: 'stage',
        3: 'first_message',
        4: 'opened_count_agr',
        5: 'emails_count_agr',
        6: 'reply_stamp_agr',
        7: 'candidate_mapping__contract__starting_price',
        8: 'candidate_mapping__contract__negotiated_price',
        9: 'candidate_mapping__contract__deliverables',
        10: 'candidate_mapping__contract__extra_details',
        11: 'candidate_mapping__contract__blogger_address',
        12: 'candidate_mapping__contract__start_date',
        14: 'candidate_mapping__contract__product_url',
        15: 'candidate_mapping__contract__status',
        16: 'candidate_mapping__contract__posts_adding_status',
    }

    if sort_by in NON_SORTABLE_FIELD_NUMBERS:
        sort_by = 0

    try:
        field = number_2_field[sort_by]
    except KeyError:
        mailboxes_qs = mailboxes_qs.order_by(
            'has_been_read_by_brand', '-reply_stamp_agr')
    else:
        field = "{}{}".format('-' if sort_direction == 1 else '', field)
        # mailboxes_qs = multikeysort(
        #     mailboxes_qs,
        #     [field, 'has_been_read_by_brand'],
        #     {'first_message': lambda x: x.reply_stamp_agr},
        #     getter=operator.attrgetter
        # )
        mailboxes_qs = mailboxes_qs.order_by(
            field, 'has_been_read_by_brand')

    print "PRE", time.time() - t0

    influencers = set()
    mailboxes = []

    t0 = time.time()

    print "QUERY", time.time() - t0

    paginator = Paginator(
        mailboxes_qs, request.visitor['user'].flag_messages_paginate_by)
    try:
        mailboxes = paginator.page(page)
    except PageNotAnInteger:
        mailboxes = paginator.page(1)
    except EmptyPage:
        mailboxes = paginator.page(paginator.num_pages)

    ids = [x.id for x in mailboxes]

    first_messages = MailProxyMessage.objects.filter(
        type=1,
        thread_id__in=ids
    ).order_by(
        'thread', 'ts'
    ).distinct('thread').values_list('thread', 'msg')

    thread_2_message = {t:m for t, m in first_messages}

    t0 = time.time()
    for mailbox in mailboxes:
        mailbox.subject_agr = get_subject(thread_2_message.get(mailbox.id))
        if request.user.userprofile.flag_can_edit_contracts:
            try:
                mailbox.contract = mailbox.candidate_mapping.all()[0].contract
            except IndexError:
                mailbox.contract = None
        influencer = mailbox.influencer
        mailbox.__dict__.update(influencer_info(influencer, request=request))
        classes = []

        from_collection = False
        from_campaign = False
        if campaign_id is not None:
            from_campaign = True
            classes.append("from_campaign")

        if collection_id is not None:
            from_collection = True
            classes.append("from_collection")

        if not from_collection and not from_campaign:
            classes.append("from_generic")

        if mailbox.has_been_read_by_brand == False:
            classes.append("unread-message")

        influencers.add(mailbox.influencer.id)
        mailbox.classes = " ".join(classes)
        mailbox.conversation_classes = " ".join(set(classes) - set(["unread-message"]))
        # mailboxes.append(mailbox)
    print "FINISH", time.time() - t0

    t0 = time.time()

    context = {
        'mailboxes': mailboxes,
        'collections': collections, # (id, archived, name)
        'campaigns': campaigns, # (id, archived, title)
        'influencers': influencers,
        'collection_selected': collection_id,
        'campaign_selected': campaign_id,
        'all_selected': show_all,
        'direct_selected': show_direct,
        'page': paginator.page(page),
        'visitor': {
            'brand': brand,
            'base_brand': base_brand,
            'user': base_brand.get_owner_user_profile()
        },
        'request': request,
        'sort_by': sort_by,
        'sort_direction': sort_direction,
        'headers': headers,
        'NON_SORTABLE_FIELD_NUMBERS': NON_SORTABLE_FIELD_NUMBERS,
        'stages_list': stages_list,
        'stage_selected': stage_selected,
        'total_count': sum(stage_counts.values()),
        'search_query': search_query,
    }
    partial = render_to_string('pages/job_posts/messages_list_partial.html', context)

    print "AFTER FINISH", time.time() - t0
    # cache = get_cache('long')
    # cache.set("partial_messages_%s_%s" % (base_brand.id, brand.id), partial)
    return partial


def bake_list_messages_partial_async(*args, **kwargs):
    threading.Thread(
        target=bake_list_messages_partial,
        args=args,
        kwargs=kwargs
    ).start()
