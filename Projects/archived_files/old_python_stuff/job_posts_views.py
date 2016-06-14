# @brand_view
# def list_messages(request, brand, base_brand, **kwargs):
#     # return redirect('debra.job_posts_views.unlinked_messages')
#     section = kwargs.get('section')
#     if section is not None and section not in ['direct', 'campaigns', 'collections']:
#         raise Http404()
#     only_partial = bool(request.GET.get('only_partial', False))
#     section_id = kwargs.get('section_id')

#     if section in ['collections']:
#         associated_collections = list(brand.influencer_groups.filter(
#             creator_brand=base_brand
#         ).exclude(
#             archived=True
#         ).order_by('id').only('id', 'archived', 'name'))
#     else:
#         associated_collections = None

#     search_query = request.GET.get('q')

#     headers = []
#     columns_visible = request.GET.get('columns_visible', [])

#     def add_headers(new_headers, visible=True, extra=False):
#         for n, header in enumerate(new_headers, start=len(headers) + 1):
#             headers.append({
#                 'text': header,
#                 'value': n,
#                 'visible': visible,
#                 'extra': extra,
#                 'sortable': True
#             })

#     add_headers([
#         'Influencer', 'Stage', 'Subject', 'Opened count', 'Messages count',
#         'Last reply'
#     ])

#     if request.user.userprofile.flag_can_edit_contracts:
#         add_headers([
#             'Starting Price', 'Negotiated Price', 'Deliverables',
#             'Extra Details', 'Address', 'Project Timeframe',
#         ], visible=False, extra=True)
#         add_headers([
#             'Edit Contract Details', 'Product URL', 'Send Contract',
#             'Send Email to Add Posts', 'PayPal Info',
#         ])

#     try:
#         for column in columns_visible:
#             headers[int(column) - 1]['visible'] = True
#     except (ValueError, IndexError):
#         pass

#     headers_dict = OrderedDict()
#     for h in headers:
#         headers_dict['_'.join([x.lower() for x in h['text'].split()])] = h

#     non_sortable_columns = ['subject']
#     for column in non_sortable_columns:
#         headers_dict[column]['sortable'] = False

#     for c in request.visitor["user"].flag_messages_columns_visible:
#         headers_dict[c]['visible'] = True

#     sort_by = int(request.GET.get('sort_by', 0))
#     sort_direction = int(request.GET.get('sort_direction', 0))

#     partial = bake_list_messages_partial(
#         brand=brand,
#         base_brand=base_brand,
#         show_all=section is None,
#         show_direct=section is not None and section in ['direct'],
#         page=request.GET.get('page', 1),
#         paginate_by=request.GET.get('paginate_by', 10),
#         sort_by=sort_by,
#         sort_direction=sort_direction,
#         campaign_id=section_id or 0 if section in ['campaigns'] else None,
#         campaigns=request.visitor["campaigns"] if section in ['campaigns'] else [],
#         collection_id=section_id or 0 if section in ['collections'] else None,
#         collections=associated_collections,
#         stage_selected=int(request.GET.get('stage', -1)),
#         search_query=search_query,
#         headers=headers_dict,
#         request=request)

#     if only_partial:
#         return HttpResponse(partial)

#     context = {
#         'selected_tab': 'outreach',
#         'sub_page': 'messages',
#         'partial_content': partial,
#         'hide_sidenav': True,
#         'stages_list': [{'value': k, 'text': v} for k, v in MailProxy.STAGE],
#         'headers': headers_dict,
#         'search_query': search_query,
#         'sort_direction': sort_direction,
#         'sort_by': sort_by,
#     }

#     return render_to_response(
#         'pages/job_posts/messages_list.html',
#         context,
#         context_instance=RequestContext(request)
#     )


@brand_view
def list_jobs(request, brand, base_brand):
    from aggregate_if import Count
    posts = BrandJobPost.objects.exclude(archived=True)

    posts = posts.filter(
        creator=brand, oryg_creator=base_brand
    )
    # ).extra(
    #     select={
    #         "invited_count_sql": """
    #             SELECT DISTINCT COUNT(*)
    #             FROM 
    #             (SELECT influencer_id
    #             FROM debra_influencerjobmapping as ijm 
    #                 JOIN debra_mailproxy as mp
    #             ON ijm.mailbox_id=mp.id
    #             WHERE ijm.job_id=debra_brandjobpost.id
    #                 AND ijm.status IN (2, 3, 4)) AS F
    #         """,
    #         "applied_count_sql": """
    #             SELECT DISTINCT COUNT(*)
    #             FROM
    #             (SELECT influencer_id
    #             FROM debra_influencerjobmapping as ijm 
    #                 JOIN debra_mailproxy as mp
    #             ON ijm.mailbox_id=mp.id
    #             WHERE ijm.job_id=debra_brandjobpost.id
    #                 AND ijm.status=5
    #             UNION
    #             SELECT influencer_id
    #             FROM debra_mailproxy as mp
    #                 JOIN debra_mailproxymessage as mpm
    #                     ON mpm.thread_id=mp.id
    #                 JOIN debra_influencerjobmapping as ijm
    #                     ON ijm.mailbox_id=mp.id
    #             WHERE ijm.job_id=debra_brandjobpost.id
    #                 AND mpm.type=1
    #                 AND mpm.direction=2
    #             ) as S
    #         """
    #     }
    # )