from retrying import retry

from debra import clickmeter

clickmeter_api = clickmeter.ClickMeterApi()


def test_tracking_groups_exist():
	from debra.models import BrandJobPost

	groups = list(BrandJobPost.objects.filter(
		periodic_tracking=True
	).values_list('tracking_group', flat=True))
	non_empty_groups = [group for group in groups if group]

	total_count = len(groups)
	non_empty_count = len(non_empty_groups)

	print '* total: {}'.format(total_count)
	print '* non empty: {}'.format(non_empty_count)

	results = []
	for n, group in enumerate(non_empty_groups, start=1):
		results.append(test_tracking_group_exists(group))
		print '** {}/{}'.format(n, non_empty_count)

	positive_count = results.count(True)
	negative_count = results.count(False)

	print '* positives: {}'.format(positive_count)
	print '* negatives: {}'.format(negative_count)


@retry(stop_max_attempt_number=3, stop_max_delay=10000, wait_fixed=3000)
def test_tracking_group_exists(tracking_group):
	result = clickmeter.ClickMeterListResult(
		clickmeter_api,
		'/aggregated/summary/groups', {
			'timeframe': 'beginning',
			'status': 'active',
		}
	)

	try:
		entity = result.find_entity(tracking_group)
	except clickmeter.ClickMeterException as e:
		return False
	else:
		return entity is not None



# @task(name='debra.account_helpers.influencer_tracking_verification', ignore_result=True)
# def influencer_tracking_verification(pa_id, attempts=3, delay=30):
# 	'''
# 	checks whether post has been updated with tracking links and pixels
# 	'''
#     from urllib2 import unquote
#     from debra.models import Contract, PostAnalytics
#     from debra.helpers import send_admin_email_via_mailsnake
#     from xpathscraper import xbrowser

#     # contract = get_object_or_404(Contract, id=contract_id)
#     pa = get_object_or_404(PostAnalytics, id=pa_id)
#     contract = pa.contract

#     pa.tracking_status = pa.TRACKING_STATUS_VERIFYING
#     pa.save()

#     def visit_page(page_url):
#         log.info('* Opening {} with Selenium...'.format(page_url))
#         with xbrowser.XBrowser(headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY) as xb:
#             xb.driver.set_page_load_timeout(60)
#             xb.driver.set_script_timeout(60)
#             xb.driver.implicitly_wait(10)
#             try:
#                 xb.load_url(page_url)
#             except:  
#                 send_admin_email_via_mailsnake(
#                     "'influencer_tracking_verification' Selenium exception for PostAnalytics={} (url={})".format(pa.id, page_url),
#                     '<br />'.join(traceback.format_exc().splitlines())
#                 )

#     def check_visit(datapoint, url):
#         log.info('* Attempt id={}, #{}'.format(pa.id, n + 1))
#         log.info('* Sleeping for {} secs... id={}, #{}'.format(
#             delay, pa.id, n + 1))

#         time.sleep(delay)
#         try:
#             log.info('* Getting /clickstream... id={}, #{}'.format(
#                 pa.id, n + 1))

#             resp = requests.get(
#                 constants.CLICKMETER_BASE_URL + '/clickstream',
#                 headers=headers,
#                 params={'datapoint': datapoint})
#             try:
#                 urls = [
#                     unquote(x.get('realDestinationUrl', '')).strip().strip('/')
#                     for x in resp.json()['rows']][:constants.CLICKMETER_EVENTS_VERIFICATION_NUMBER]
#             except KeyError:
#                 urls = []

#             log.info('* Urls found={} for id={}, #{}'.format(
#                 len(urls), pa.id, n + 1))

#             if url.strip().strip('/') in urls:
#                 log.info('* Post URL is found... id={}, #{}'.format(
#                     pa.id, n + 1))

#                 return True
#         except:
#             log.info('* Exception, sending email to admins... id={}, #{}'.format(
#                 pa.id, n + 1))

#             send_admin_email_via_mailsnake(
#                 "'influencer_tracking_verification' exception for PostAnalytics={}".format(pa.id),
#                 '<br />'.join(traceback.format_exc().splitlines())
#             )

#     if pa.post_type not in ['Blog']:
#         response = requests.get(pa.post_url)
#         if response.status_code == 200:
#             pa.tracking_status = pa.TRACKING_STATUS_VERIFIED
#         else:
#             pa.tracking_status = pa.TRACKING_STATUS_VERIFICATION_PROBLEM
#         pa.save()
#         return

#     log.info('* Exctracting tracking data...')

#     check_data = [
#         (pa.post_url, contract.tracking_pixel, True),
#         (contract.product_url, contract.tracking_link, contract.campaign.product_sending_status not in ['no_product_sending', 'no_product_page']),
#         (contract.campaign.client_url, contract.tracking_brand_link, True),
#     ]

#     headers = {
#         'Accept': 'application/json',
#         'Content-Type': 'application/json',
#         'X-Clickmeter-Authkey': constants.CLICKMETER_API_KEY,
#     }

#     for url, datapoint, to_check in check_data:
#         if not to_check:
#             continue
#         success = False
#         visit_page(url)
#         for n in xrange(attempts):
#             success = success or check_visit(datapoint, url)
#         if not success:
#             log.info('* Nothing is found. id={}, #{}, url={}'.format(pa.id, n + 1, url))

#             pa.tracking_status = pa.TRACKING_STATUS_VERIFICATION_PROBLEM
#             pa.save()

#             log.info("* PostAnalytics updated with 'Verification Problem' status. id={}, #{}".format(
#                 pa.id, n + 1))
#             log.info('* Sending email to admins about failure. id={}, #{}'.format(
#                 pa.id, n + 1))

#             send_admin_email_via_mailsnake(
#                 'Verification problem on PostAnalytics={}'.format(pa.id),
#                 '''
#                 # of attempts = {}, delay = {} secs<br />
#                 searched for url={}
#                 '''.format(attempts, delay, url)
#             )
#             return

#     pa.tracking_status = pa.TRACKING_STATUS_VERIFIED
#     pa.save()

#     log.info("* PostAnalytics updated with 'Verified' status. id={}, #{}".format(
#         pa.id, n + 1))


# @task(name='debra.account_helpers.update_campaign_tracking_stats', ignore_result=True)
# def update_campaign_tracking_stats(campaign_id):
# 	'''
# 	updates aggregates stats for the whole campaign
# 	'''
#     from debra.models import (
#         BrandJobPost, PostAnalyticsCollectionTimeSeries)
#     from debra.helpers import send_admin_email_via_mailsnake

#     campaign = get_object_or_404(
#         BrandJobPost, id=campaign_id)

#     result = ClickMeterListResult(
#         clickmeter_api,
#         '/aggregated/summary/groups', {
#             'timeframe': 'beginning',
#             'status': 'active',
#         }
#     )

#     try:
#         entity = result.find_entity(campaign.tracking_group)
#     except ClickMeterException as e:
#         send_admin_email_via_mailsnake(
#             'ClickMeterException for Campaign={}'.format(campaign_id),
#             e.error_html
#         )
#     else:
#         if not entity:
#             # TODO: commented it out because of spamming out emails
#             # send_admin_email_via_mailsnake(
#             #     'Cannot find ClickMeter EntityId={} for Campaign={}'.format(
#             #         campaign.tracking_group, campaign_id),
#             #     'Cannot find ClickMeter EntityId={} for Campaign={}'.format(
#             #         campaign.tracking_group, campaign_id),
#             # )
#             pass
#         time_series = PostAnalyticsCollectionTimeSeries.objects.create(
#             collection=campaign.post_collection,
#             count_clicks=entity.get('totalClicks', 0),
#             count_unique_clicks=entity.get('uniqueClicks', 0),
#             count_views=entity.get('totalViews', 0),
#             count_unique_views=entity.get('uniqueViews', 0),
#             snapshot_date=datetime.datetime.now()
#         )


# @task(name='debra.account_helpers.bulk_update_contract_tracking_stats', ignore_result=True)
# def bulk_update_contract_tracking_stats(campaign_id, pa_ids=None, connect_to_url_call=True):
# 	'''
# 	updates stats for each particular post in a campaign
# 	'''
#     from copy import copy
#     from debra.models import BrandJobPost, PostAnalytics, Platform
#     from debra.helpers import send_admin_email_via_mailsnake
#     from debra.brand_helpers import connect_url_to_post

#     campaign = get_object_or_404(BrandJobPost, id=campaign_id)
#     post_collection = campaign.post_collection

#     log.info('* Getting Post Analytics from DB...')

#     if pa_ids is None:
#         # qs = post_collection.get_unique_post_analytics()
#         qs = PostAnalytics.objects.filter(
#             id__in=list(
#                 campaign.participating_post_analytics.values_list(
#                     'id', flat=True))
#         )
#     else:
#         qs = PostAnalytics.objects.filter(id__in=pa_ids)

#     qs = qs.exclude(
#         post__platform__isnull=True
#     ).prefetch_related('post__platform', 'contract')

#     # social_posts = post_analytics.exclude(Q(post_type='Blog') | Q(post_type__isnull=True))
#     # post_analytics = post_analytics.filter(Q(post_type='Blog') | Q(post_type__isnull=True))
#     social_posts = qs.filter(
#         post__platform__platform_name__in=Platform.SOCIAL_PLATFORMS
#     )
#     post_analytics = qs.filter(
#         post__platform__platform_name__in=Platform.BLOG_PLATFORMS
#     )

#     social_posts = list(social_posts)
#     post_analytics = list(post_analytics)

#     log.info('* Got {} blog posts, {} social posts.'.format(
#         len(post_analytics), len(social_posts)))

#     log.info('* Getting data from ClickMeter...')

#     if pa_ids:
#         date_range = (
#             min(p.created for p in post_analytics) - datetime.timedelta(hours=2),
#             max(p.created for p in post_analytics) + datetime.timedelta(hours=2),
#         )
#     else:
#         date_range = None

#     clicks_result = ClickMeterListResult(
#         clickmeter_api,
#         '/aggregated/summary/datapoints', {
#             'timeframe': 'custom' if date_range else 'beginning',
#             'fromDay': date_range[0].strftime('%Y%m%d%H%M') if date_range else None,
#             'toDay': date_range[1].strftime('%Y%m%d%H%M') if date_range else None,
#             'type': 'tl',
#         }
#     )

#     views_result = ClickMeterListResult(
#         clickmeter_api,
#         '/aggregated/summary/datapoints', {
#             'timeframe': 'custom' if date_range else 'beginning',
#             'fromDay': date_range[0].strftime('%Y%m%d%H%M') if date_range else None,
#             'toDay': date_range[1].strftime('%Y%m%d%H%M') if date_range else None,
#             'type': 'tp',
#         }
#     )

#     log.info('* Creating mappings...')

#     def get_new_pas(pas):
#         if pa_ids:
#             return pas
#         new_pas = []
#         for pa in pas:
#             new_pa = PostAnalytics.objects.from_source(
#                 post_url=pa.post_url, refresh=True)
#             new_pa.post = pa.post
#             new_pa.collection = pa.collection
#             new_pa.contract = pa.contract
#             new_pa.post_found = pa.post_found
#             # new_pa = pa
#             # new_pa.pk = None
#             try:
#                 if pa.post.platform.platform_name in Platform.BLOG_PLATFORMS:
#                     new_pa.count_clickthroughs = 0
#                     new_pa.count_unique_clickthroughs = 0
#                     new_pa.count_impressions = 0
#                     new_pa.count_unique_impressions = 0
#             except AttributeError:
#                 pass
#             new_pas.append(new_pa)
#         return new_pas

#     new_post_analytics = get_new_pas(post_analytics)
#     new_social_post_analytics = get_new_pas(social_posts)

#     def get_mapping(field):
#         d = defaultdict(list)
#         for p in new_post_analytics:
#             if p.contract is not None:
#                 field_value = getattr(p.contract, field)
#                 if isinstance(field_value, list):
#                     field_values = field_value
#                 else:
#                     field_values = [field_value]
#                 for field_value in field_values:
#                     d[field_value].append(p)
#         return d

#     mappings = {
#         # 'tracking_link': get_mapping('tracking_link'),
#         'product_tracking_links': get_mapping('product_tracking_links'),
#         'campaign_product_tracking_links': get_mapping(
#             'campaign_product_tracking_links'),
#         'tracking_brand_link': get_mapping('tracking_brand_link'),
#         'tracking_pixel': get_mapping('tracking_pixel'),
#     }

#     def find_by_field(field, value):
#         return mappings[field][value]

#     log.info('* Updating views counts...')

#     for page in views_result:
#         for entity in page['result']:
#             for pa in find_by_field('tracking_pixel', entity.get('entityId')):
#                 log.info('* Tracking Pixel {} updating...'.format(
#                     entity.get('entityId')))
#                 pa.count_impressions = entity.get('totalViews', 0)
#                 pa.count_unique_impressions = entity.get('uniqueViews', 0)

#     log.info('* Updating counts views...')

#     use_campaign_links = campaign.info_json.get('same_product_url')

#     for page in clicks_result:
#         for entity in page['result']:
#             if use_campaign_links:
#                 for pa in find_by_field('campaign_product_tracking_links', entity.get('entityId')):
#                     log.info('* Tracking Link {} updating...'.format(
#                         entity.get('entityId')))
#                     pa.count_clickthroughs += entity.get('totalClicks', 0)
#                     pa.count_unique_clickthroughs += entity.get('uniqueClicks', 0)
#             else:
#                 for pa in find_by_field('product_tracking_links', entity.get('entityId')):
#                     log.info('* Tracking Link {} updating...'.format(
#                         entity.get('entityId')))
#                     pa.count_clickthroughs += entity.get('totalClicks', 0)
#                     pa.count_unique_clickthroughs += entity.get('uniqueClicks', 0)
#             for pa in find_by_field('tracking_brand_link', entity.get('entityId')):
#                 log.info('* Tracking Brand Link {} updating...'.format(
#                     entity.get('entityId')))
#                 pa.count_clickthroughs += entity.get('totalClicks', 0)
#                 pa.count_unique_clickthroughs += entity.get('uniqueClicks', 0)

#     log.info('* Saving newly created Post Analytics...')

#     for pa in itertools.chain(new_post_analytics, new_social_post_analytics):
#         pa.save()
#         if connect_to_url_call:
#             try:
#                 connect_url_to_post(pa.post_url, pa.id)
#             except:
#                 send_msg_to_slack(
#                     'connect-url-to-post',
#                     "{asterisks}\n"
#                     "Post Analytics = {pa_id}\n"
#                     "{asterisks}\n"
#                     "{traceback}\n"
#                     "{delimiter}"
#                     "\n".format(
#                         pa_id=pa.id,
#                         asterisks="*" * 120,
#                         delimiter="=" * 120,
#                         traceback=traceback.format_exc(),
#                     )
#                 )

#     log.info('* Done.')


# @task(name='debra.account_helpers.bulk_update_campaigns_tracking_stats', ignore_result=True)
# def bulk_update_campaigns_tracking_stats(campaign_ids=None):
#     from debra.models import BrandJobPost

#     if campaign_ids:
#         trackable_campaigns = BrandJobPost.objects.filter(id__in=campaign_ids)
#     else:
#         trackable_campaigns = BrandJobPost.objects.filter(
#             periodic_tracking=True)

#     for campaign in trackable_campaigns:
#         update_campaign_tracking_stats.apply_async(
#             [campaign.id], queue='update_campaign_tracking_stats')
#         bulk_update_contract_tracking_stats.apply_async(
#             [campaign.id], queue='bulk_update_contract_tracking_stats')




#   # # NOT USED!!!!!




# @task(name='debra.account_helpers.update_contract_tracking_stats', ignore_result=True)
# def update_contract_tracking_stats(contract_id):
#     from debra.models import Contract, PostAnalytics
#     from debra.helpers import send_admin_email_via_mailsnake

#     contract = get_object_or_404(Contract, id=contract_id)

#     clicks_result = ClickMeterListResult(
#         clickmeter_api,
#         '/aggregated/summary/datapoints', {
#             'timeframe': 'beginning',
#             'type': 'tl',
#         }
#     )

#     views_result = ClickMeterListResult(
#         clickmeter_api,
#         '/aggregated/summary/datapoints', {
#             'timeframe': 'beginning',
#             'type': 'tp',
#         }
#     )

#     def get_datapoint_entity(result, datapoint_id):
#         try:
#             entity = result.find_entity(datapoint_id)
#         except ClickMeterException as e:
#             send_admin_email_via_mailsnake(
#                 'ClickMeterException for Contract={}'.format(contract_id),
#                 e.error_html
#             )
#         else:
#             if not entity:
#                 # send_admin_email_via_mailsnake(
#                 #     'Cannot find ClickMeter EntityId={} for Contract={}'.format(
#                 #         datapoint_id, campaign_id),
#                 #     'Cannot find ClickMeter EntityId={} for Contract={}'.format(
#                 #         datapoint_id, campaign_id),
#                 # )
#                 return
#             return entity

#     link_entity = get_datapoint_entity(clicks_result, contract.tracking_link)
#     brand_link_entity = get_datapoint_entity(
#         clicks_result, contract.tracking_brand_link)
#     pixel_entity = get_datapoint_entity(views, contract.tracking_pixel)

#     post_collection = contract.campaign.post_collection
#     post_analytics = post_collection.filter(
#         contract=contract).get_unique_post_analytics()
#     for pa in post_analytics:
#         new_pa = pa
#         new_pa.pk = None
#         new_pa.count_clickthroughs = link_entity.get('totalClicks', 0) + brand_link_entity.get('totalClicks', 0)
#         new_pa.count_unique_clickthroughs = link_entity.get('uniqueClicks', 0) + brand_link_entity.get('uniqueClicks', 0)
#         new_pa.count_impressions = pixel_entity.get('totalViews', 0)
#         new_pa.count_unique_impressions = pixel_entity.get('uniqueViews', 0)
#         new_pa.save()
