import itertools
import datetime
import random
from collections import defaultdict

from django.db.models import Count, Sum
from django.core.cache import get_cache

from debra.helpers import get_model_instance
from debra.decorators import (cached_property, timeit,)
from debra import models
from debra import feeds_helpers
from social_discovery.blog_discovery import queryset_iterator


mc_cache = get_cache('memcached')
redis_cache = get_cache('redis')


PLATFORMS = ['Blog', 'Instagram', 'Facebook',
	'Twitter', 'Pinterest',]


class CampaignReportDataHelper(object):

	def __init__(self, campaign):
		self.campaign = get_model_instance(campaign,
			models.BrandJobPost)

	def _get_required_number_of_posts_for_each_platform(self, per_influencer=True):
		if per_influencer:
			res = defaultdict(int)

			contract_ids = list(self.campaign.participating_post_analytics.exclude(
				contract__isnull=True
			).distinct('contract').values_list('contract', flat=True))
			contracts_queryset = models.Contract.objects.filter(
				id__in=contract_ids)

			contracts_iterator = queryset_iterator(contracts_queryset)
			for contract in contracts_iterator:
				d = contract.deliverables_json
				for pl in PLATFORMS:
					res[pl] += d.get(pl.lower(), {}).get('value', 0) or 0
			return res
		else:
			d = self.campaign.deliverables_json
			return {
				pl: d.get(pl.lower(), {}).get('value', 0) * self.influencers_count
				for pl in PLATFORMS
			}

	def _get_random_influencers_for_each_platform(self, INFS_PER_PLATFORM=5):
		infs_qs = self.post_analytics_queryset.values(
			'post__platform__platform_name',
			'post__influencer',
			'post__influencer__name',
		).distinct(
			'post__influencer', 'post__platform__platform_name'
		).order_by('post__influencer')

		def _processed_inf(inf):
			pl = inf['post__platform__platform_name']
			pl = 'Blog' if pl in models.Platform.BLOG_PLATFORMS else pl
			inf_id = inf['post__influencer']
			return pl, {
				'id': inf['post__influencer'],
				'name': inf['post__influencer__name'],
				'pic': None,
			}

		def _collected_infs():
			collected_infs = defaultdict(list)
			for inf in infs_qs:
				pl, data  = _processed_inf(inf)
				if len(collected_infs[pl]) >= INFS_PER_PLATFORM:
					continue
				collected_infs[pl].append(data)
			inf_ids = itertools.chain(*[[inf['id'] for inf in pl_infs]
				for pl_infs in collected_infs.values()])
			profile_pics = models.Influencer.objects.get_profile_pics(
				inf_ids)
			for pl, infs in collected_infs.items():
				for inf in infs:
					inf['pic'] = profile_pics.get(inf['id'])
			return collected_infs

		return _collected_infs()

	def _get_post_counts_for_each_platform(self):
		qs = self.post_analytics_queryset
		counts = {
			item['post__platform__platform_name']: item['count'] or 0
			for item in qs.values('post__platform__platform_name').annotate(
				count=Count('post', distinct=True))
		}
		counts['Blog'] = sum(cnt for pl, cnt in counts.items()
		if pl in models.Platform.BLOG_PLATFORMS)
		for pl, _ in counts.items():
			if pl in models.Platform.BLOG_PLATFORMS:
				del counts[pl]
		total = sum(counts.values())
		return counts, total

	def _get_post_samples_for_platform(self, platform_name=None, limit=5):

		post_ids = [
			x['post']
			for x in self.post_analytics_queryset.filter_platforms(
				platform_name
			).with_campaign_counters(
				selected_counters=['agr_post_total_count']
			).values(
				'post__influencer',
				'post',
				'agr_post_total_count',
			).order_by(
				'post__influencer',
				'-agr_post_total_count',
			).distinct(
				'post__influencer'
			)
		]

		# @todo: sort by score
		ordered_post_ids = post_ids

		# ordered_post_ids = list(models.Posts.objects.filter(
		# 	id__in=post_ids
		# ).with_campaign_counters(
		# 	selected_counters=['agr_post_total_count']
		# ).order_by(
		# 	'-agr_post_total_count'
		# ).values_list('id', flat=True))

		feed_json = feeds_helpers.get_feed_handler()
		data = feed_json(
			request=None,
			no_cache=True,
			with_post_ids=ordered_post_ids,
			preserve_order=True,
			include_products=False,
			limit_size=limit
		).get('results', [])
		for item in data:
			dims = item.get('post_image_dims')
			if dims and len(dims) == 2:
				width, height = dims
				post_image_dims = {
					'width': width,
					'height': height,
				}
			else:
				post_image_dims = None
			item['post_image_dims'] = post_image_dims
		return data

	def _get_total_engagements_for_platform(self, platform_name):
		return self.post_analytics_queryset.filter_platforms(
			platform_name).total_engagement()

	def _get_total_impressions_for_platform(self, platform_name):
		return self.post_analytics_queryset.filter_platforms(
			platform_name).total_impressions()

	def _get_top_posts_for_platform(self, platform_name=None, desc=True, limit=3):
		qs = self.post_analytics_queryset.filter_platforms(
			platform_name
		).exclude(
			post__post_image__isnull=True,
		).with_campaign_counters(
			selected_counters=['agr_post_total_count']
		).order_by(
			'{}agr_post_total_count'.format('-' if desc else ''),
		).values(
			'post__post_image',
			'post',
			'post__url',
			'post__title',
			'agr_post_total_count',
		)

		qs = qs[:limit]
		return [{
			'pic': item['post__post_image'],
			'post_id': item['post'],
			'url': item['post__url'],
			'title': item['post__title'],
		} for item in qs]

	@cached_property
	def post_analytics_queryset(self):
		return self.campaign.participating_post_analytics.exclude(
			post__platform__platform_name='Instagram',
			post__post_image__isnull=True,
		).exclude(
			post__platform__isnull=True,
		)

	@cached_property
	def influencers_count(self):
		return self.campaign.participating_influencers_count

	@cached_property
	def post_counts_for_each_platform(self):
		return self._get_post_counts_for_each_platform()

	@cached_property
	def required_number_of_posts_for_each_platform(self):
		return self._get_required_number_of_posts_for_each_platform()

	@cached_property
	def random_influencers_for_each_platforms(self):
		return self._get_random_influencers_for_each_platform()


class CampaignReportEndpointsManager(object):

	def __init__(self, campaign):
		self.campaign = get_model_instance(campaign,
			models.BrandJobPost)
		self.helper = CampaignReportDataHelper(campaign)

	@timeit
	def _calc_platform_counts(self, pl_name):
		if pl_name is None:
			raise NotImplementedError
		posts = self.helper.post_analytics_queryset.filter_platforms(pl_name)
		counts, _ = self.helper.post_counts_for_each_platform
		totals_required = self.helper.required_number_of_posts_for_each_platform

		aggr_data = posts.aggregate(
			pins_count=Sum('count_pins'),
			tweets_count=Sum('count_tweets'),
			gplus_count=Sum('count_gplus_plusone'),
		)

		repins_count = aggr_data.get('pins_count', 0) or 0
		tweets_count = aggr_data.get('tweets_count', 0) or 0
		gplus_count = aggr_data.get('gplus_count', 0) or 0

		return {
			'platform_name': pl_name,
			'total_posts_required': max(
				totals_required.get(pl_name, 0), counts.get(pl_name, 0)),
			'total_posts_gone': counts.get(pl_name, 0),
			'total_clicks': posts.total_clicks(),
			'total_impressions': posts.total_impressions(),
			'total_engagements': posts.total_engagement(),
			'comments_count': posts.total_comments(),
			'likes_count': posts.total_likes(),
			'shares_count': posts.total_shares(),
			'audience': posts.audience(),
			'total_video_impressions': posts.total_video_impressions(),

			'facebook_count': posts.total_facebook_engagement(),
			'repins_count': repins_count,
			'tweets_count': tweets_count,
			'gplus_count': gplus_count,
		}

	@timeit
	def _calc_random_influencers(self, pl_name):
		if pl_name is None:
			raise NotImplementedError
		infs = self.helper.random_influencers_for_each_platforms.get(pl_name, [])
		return {
			'influencers': infs,
		}

	@timeit
	def _calc_top_posts(self, pl_name=None):
		return {
			'top_posts': self.helper._get_top_posts_for_platform(
				pl_name, desc=True),
			'lower_posts': self.helper._get_top_posts_for_platform(
				pl_name, desc=False),
		}

	@timeit
	def _calc_top_influencers_by_share_counts(self, pl_name='Blog', limit=3):
		if pl_name is not 'Blog':
			raise NotImplementedError

		blog_posts = self.helper.post_analytics_queryset.filter_platforms(
			'Blog')

		def get_infs(count_field):
			qs = blog_posts.exclude(post__influencer__isnull=True)
			if count_field == 'agr_fb_count':
				qs = qs.with_campaign_counters(selected_counters=['agr_fb_count'])

			annotation_field = '{}_sum'.format(count_field)

			def get_extra_fields():
				return ['agr_fb_count'] if count_field == 'agr_fb_count' else []

			qs = qs.values(
				'post__influencer',
				'post__influencer__name',
				*get_extra_fields())
			qs = qs.annotate(**{
				annotation_field: Sum(count_field)
			}).order_by(
				'-{}'.format(annotation_field)
			)[:limit]

			profile_pics = models.Influencer.objects.get_profile_pics(
				[x['post__influencer'] for x in qs])
			return [{
				'name': item['post__influencer__name'],
				'id': item['post__influencer'],
				'pic': profile_pics.get(item['post__influencer']),
				'count': item[annotation_field] or 0,
			} for item in qs]

		return {
			'influencers': {
				'Pinterest': get_infs('count_pins'),
				# 'Facebook': get_infs('agr_fb_count'),
				'Gplus': get_infs('count_gplus_plusone'),
				'Twitter': get_infs('count_tweets'),
			},
		}

	@timeit
	def _calc_posting_time_series(self, pl_name=None):

		def get_time_series():
			qs = self.helper.post_analytics_queryset.filter_platforms(
				pl_name)
			qs = qs.exclude(
				post__create_date__isnull=True,
			).values(
				'post',
				'post__create_date',
				'post__platform_name',
				'post__influencer__name',
			).order_by('post__create_date')
			time_series = list(qs)
			return [{
				'post_id': post_data['post'],
				'influencer_name': post_data['post__influencer__name'],
				'post_date': post_data['post__create_date'],
				'platform_name': 'Blog' if post_data['post__platform_name'] in\
					models.Platform.BLOG_PLATFORMS else post_data['post__platform_name'],
			} for post_data in time_series]

		return {
			'time_series': get_time_series(),
		}

	@timeit
	def _calc_post_counts_time_series(self, pl_name=None):
		posts = self.helper.post_analytics_queryset.filter_platforms(
			pl_name).exclude(post__create_date__isnull=True).posts()

		date_field = 'create_date'
		time_series = posts.extra(select={
			'year': "EXTRACT(year FROM {})".format(date_field),
            'month': "EXTRACT(month FROM {})".format(date_field),
            'day': "EXTRACT(day FROM {})".format(date_field),
		}).values(
			'year', 'month', 'day',
		).order_by(
			'year', 'month', 'day'
		).annotate(date_count=Count('id'))

		return {
			'time_series': [{
				'date': datetime.date(
					year=int(serie['year']),
					month=int(serie['month']),
					day=int(serie['day']),
				),
				'count': serie['date_count'],
			} for serie in time_series],
		}

	@timeit
	def _calc_influencer_performance(self, pl_name=None):
		posts = self.helper.post_analytics_queryset.filter_platforms(pl_name)
		infs_data = posts.exclude(
			post__influencer__isnull=True
		).with_campaign_counters(
			selected_counters=['agr_post_total_count']
		).order_by(
			'post__influencer',
			'-agr_post_total_count',
		).distinct(
			'post__influencer'
		).values(
			'post__influencer',
			'post__influencer__name',
			'agr_post_total_count',
		)

		return {
			'influencers': [{
				'name': inf['post__influencer__name'],
				'score': inf['agr_post_total_count'] or 0,
				'id': inf['post__influencer'],
			} for inf in infs_data]
		}

	@timeit
	def _calc_engagement_time_series(self, pl_name=None,\
		engagement_type=None):

		engagement_types = ('likes', 'comments', 'shares', 'video_impressions',)
		if engagement_type not in (None,) + engagement_types:
			raise Exception("engagement_type={} can't be found in {}".format(
				engagement_type, engagement_types))

		def get_fake_data():
			data, cumulative_data = _FakeEngagementTimeSeries(self).\
				generate()
			return {
				'time_series': {k: v.dicts() for k, v in data.items()},
				'cumulative_time_series': {k: v.dicts()
					for k, v in cumulative_data.items()},
			}

		def get_real_data():
			pass

		return get_fake_data()

	@timeit
	def _calc_clickthroughs_time_series(self, pl_name=None, cumulative=False):
		if pl_name not in [None, 'Blog']:
			raise NotImplementedError
		blog_posts_history = self.campaign.post_collection.postanalytics_set.\
			all().filter_platforms(pl_name)
		blog_posts = self.helper.post_analytics_queryset.filter_platforms(
			pl_name)

		return {
			'total_clicks': blog_posts.total_clicks(),
			'time_series': blog_posts_history.time_series('count_clickthroughs',
				cumulative=cumulative),
		}

	@timeit
	def _calc_cumulative_clickthroughs_time_series(self, pl_name=None):
		return self._calc_clickthroughs_time_series(pl_name, cumulative=True)

	@timeit
	def _calc_impressions_time_series(self, pl_name=None, cumulative=False):

		def _social_time_series():
			pl = pl_name if pl_name in models.Platform.SOCIAL_PLATFORMS else 'Social'
			social_posts = self.helper.post_analytics_queryset.\
				filter_platforms(pl).\
				posts()
			return social_posts.time_series('platform__num_followers',
				date_field='create_date', date_field_full='debra_posts.create_date',
				cumulative=cumulative)

		def _blog_time_series():
			blog_posts_history = self.campaign.post_collection.postanalytics_set.\
				all().filter_platforms('Blog')
			return blog_posts_history.time_series('count_impressions',
				cumulative=cumulative)

		def _mixed_time_series():
			if pl_name is None:
				return (TimeSeries(_blog_time_series()) +\
					TimeSeries(_social_time_series())).to_cumulative().dicts()
			elif pl_name in models.Platform.SOCIAL_PLATFORMS:
				return _social_time_series()
			else:
				return _blog_time_series()

		return {
			'total_impressions': self.helper.post_analytics_queryset.\
				filter_platforms(pl_name).\
				total_impressions(),
			'time_series': _mixed_time_series(),
		}

	@timeit
	def _calc_cumulative_impressions_time_series(self, pl_name=None):
		return self._calc_impressions_time_series(pl_name, cumulative=True)

	@timeit
	def _calc_post_samples(self, pl_name=None):
		if pl_name is None:
			raise NotImplementedError
		return {
			'posts': self.helper._get_post_samples_for_platform(pl_name),
		}

	@timeit
	def _calc_instagram_photos(self):
		posts = self.helper.post_analytics_queryset.\
			filter_platforms('Instagram').\
			with_campaign_counters(selected_counters=['agr_post_total_count']).\
			values('post__url', 'post__post_image', 'agr_post_total_count').\
			order_by('-agr_post_total_count')[:30]
		return {
			'instagram_photos': [{
				'url': post['post__url'],
				'img': post['post__post_image'],
			} for post in posts]
		}

	@timeit
	def _calc_influencer_locations(self):
		infs = self.helper.post_analytics_queryset.\
			influencers().\
			select_related('demographics_locality').\
			exclude(demographics_location_lat__isnull=True).\
			exclude(demographics_location_lon__isnull=True)

		for inf in infs:
			pass


class CampaignReportDataWrapper(object):

	CACHABLE_ENDPOINTS = [
		('platform_counts', PLATFORMS),
		('random_influencers', PLATFORMS),
		('top_posts', [None] + PLATFORMS),
		('top_influencers_by_share_counts', ['Blog']),
		('posting_time_series', [None] + PLATFORMS),
		('post_counts_time_series', [None] + PLATFORMS),
		('influencer_performance', [None] + PLATFORMS),
		# ('engagement_time_series', [None]),
		('clickthroughs_time_series', [None] + ['Blog']),
		('cumulative_clickthroughs_time_series', [None] + ['Blog']),
		('impressions_time_series', [None] + ['Blog']),
		('cumulative_impressions_time_series', [None] + ['Blog']),
		('post_samples', PLATFORMS),
	]

	def __init__(self, campaign):
		self.campaign = get_model_instance(campaign,
			models.BrandJobPost)
		self.endpoints_manager = CampaignReportEndpointsManager(
			self.campaign)

	@timeit
	def to_dict(self):
		
		def _for_all_platforms(endpoint, pls):
			return [('{}_{}'.format(endpoint, pl),
				getattr(self.endpoints_manager,'_calc_{}'.format(endpoint))(pl))
			for pl in pls]

		res = dict(itertools.chain(*[_for_all_platforms(endpoint, pls)
			for endpoint, pls in self.CACHABLE_ENDPOINTS]))

		eng_time_series = self.endpoints_manager.\
			_calc_engagement_time_series()
		time_series = eng_time_series['time_series']
		cum_time_series = eng_time_series['cumulative_time_series']
		for (node, ts), (_, cum_ts) in zip(time_series.items(), cum_time_series.items()):
			res.update({
				'engagement_time_series_{}_{}'.format(*node): ts,
				'cumulative_engagement_time_series_{}_{}'.format(*node): cum_ts,
			})

		return res

	@timeit
	def save_to_cache(self, cache=None):
		if cache is None:
			cache = redis_cache
		data = self.to_dict()
		for endpoint, _data in data.items():
			cache.set('crep_{}_{}'.format(self.campaign.id, endpoint),
				_data, timeout=0)

	def retrieve_from_cache(self, endpoint, cache=None):
		if cache is None:
			cache = redis_cache
		data = cache.get('crep_{}_{}'.format(self.campaign.id, endpoint))
		return data

	def get_endpoint_data(self, endpoint, pl_name=None):
		if endpoint in [e for e, _ in self.CACHABLE_ENDPOINTS]:
			key = '{}_{}'.format(endpoint, pl_name)
			data = self.retrieve_from_cache(key)
		else:
			data = getattr(self.endpoints_manager,
				'_calc_{}'.format(endpoint))(pl_name)
		return data


class TimeSeries(object):

	def __init__(self, points=[]):
		self.points = self._merge(points or [])

	@staticmethod
	def _unify(point):
		if isinstance(point, dict):
			return point['date'], point['count']
		return point

	@classmethod
	def _merge(cls, *points):
		d = defaultdict(int)
		for p_date, count in map(cls._unify, itertools.chain(*points)):
			d[p_date] += count or 0
		return sorted(d.items(), key=lambda item: item[0])

	def __add__(self, other):
		return TimeSeries(self._merge(self.points, other.points))

	def __radd__(self, other):
		return TimeSeries(self._merge(self.points, other))

	def pairs(self):
		return self.points

	def dicts(self):
		return [{
			'date': p_date,
			'count': count,
		} for p_date, count in self.points]

	def to_cumulative(self):
		cumulative_points, curr_sum = [], 0
		for p_date, count in self.points:
			curr_sum += count
			cumulative_points.append((p_date, curr_sum))
		return TimeSeries(cumulative_points)


class _FakeEngagementTimeSeries(object):

	ENGAGEMENT_TYPE_2_FIELD_MAPPING = {
		None: 'agr_post_total_count',
		'likes': 'agr_post_likes_count',
		'comments': 'agr_post_comments_count',
		'shares': 'agr_post_shares_count',
		'video_impressions': 'post__impressions',
	}

	ENGAGEMENT_TYPES = ('likes', 'comments', 'shares', 'video_impressions',)

	def __init__(self, endpoints_manager, platform_name=None, engagement_type=None):
		self.em = endpoints_manager

	@staticmethod
	def _calc_impact(p_date, total_eng):

		def _gen_random_distribution():
			_distribution = [50, 30, 20]
			total = 0
			for n, p in enumerate(_distribution):
				val = p + random.randint(0, p / 5) * random.choice([-1, 1])
				day = p_date + datetime.timedelta(n)
				if total + val > 100:
					if total < 100:
						yield day, 100 - total
					break
				total += val
				yield day, val

		for day, eng_percentage in _gen_random_distribution():
			yield day, int((float(eng_percentage) / 100) * total_eng)

	def _max_daily_engagement(self, pl, eng_type):
		posts = self.em.helper.post_analytics_queryset.\
			exclude(post__create_date__isnull=True).\
			filter_platforms(pl).\
			select_related('post').\
			order_by('post__create_date').\
			with_campaign_counters()
		pairs = list(posts.values_list('post__create_date',
			self.ENGAGEMENT_TYPE_2_FIELD_MAPPING[eng_type]))
		return TimeSeries([(p_date.date(), count)
			for p_date, count in pairs])

	def get_time_series(self, pl, eng_type):

		def _pairs():
			for p_date, count  in self._max_daily_engagement(pl, eng_type).pairs():
				for day, impact in self._calc_impact(p_date, count):
					yield day, impact

		return TimeSeries(_pairs())

	def generate(self):
		_visited = dict()

		def _nodes():
			for pl in [None] + PLATFORMS:
				for eng_type in (None,) + self.ENGAGEMENT_TYPES:
					yield pl, eng_type

		def _partial_sum(pl, eng_type):
			if pl is not None and eng_type is not None:
				return self.get_time_series(pl, eng_type)
			else:
				if pl is None:
					nodes = [(pl, eng_type) for pl in PLATFORMS]
				elif eng_type is None:
					nodes = [(pl, eng_type)
						for eng_type in self.ENGAGEMENT_TYPES]
				return sum((_visited[node] for node in nodes), TimeSeries())

		for i in xrange(2, -1, -1):
			for node in _nodes():
				if len(filter(None, node)) == i and node not in _visited:
					_visited[node] = _partial_sum(*node)

		_cumulative_visited = {
			k: v.to_cumulative()
			for k, v in _visited.items()
		}

		return _visited, _cumulative_visited
