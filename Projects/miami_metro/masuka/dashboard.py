from debra.models import User, WishlistItem, Brands
from debra.models import UserOperations, UserProfile

import datetime


from mailsnake import MailSnake
from mailsnake.exceptions import *

'''
	Per User stats we care about:
		1. Total items
			- Shelved from feed
			- Shelved from outside
			- Shelved from supported store
			- Shelved from unsupported store

		2. Price alerts set

		3. Price alert emails
			- Opened 
			- Clicked

		4. Clicked on Buy Button

		5. Clicked on Invite Friends

		6. Frequency of usage
			- Use everyday
			- Use every week
'''

def stats_by_user(start):
	users = User.objects.filter(date_joined__gte = start)

	for user in users:
		items_shelved = WishlistItem.objects.select_related('user_selection', 
							'user_selection__item',
							'user_selection__item__brand').filter(user_id = user)

		items_shelved_unsupported = items_shelved.filter(user_selection__item__brand__supported = False)

		items_with_price_alerts_set = items_shelved.filter(notify_lower_bound__gte = 1.0)

		stores_shelved = items_shelved.distinct('user_selection__item__brand__name')

		stores = [item.user_selection.item.brand for item in stores_shelved]
		all_stores = set()
		supported_stores = set()
		for s in stores:
			all_stores.add(s.name)
			if s.supported:
				supported_stores.add(s.name)



		#print "stores %s " % all_stores
		#print "Supported stores %s " % supported_stores

		user_ops = UserOperations.objects.filter(user_id = user, operator_type = 0)

		from_feed = items_shelved.exclude(affiliate_source_wishlist_id = '-1')
		try:
			prof = user.get_profile()
			if prof:
				prof.num_items_from_supported_stores = len(items_shelved) - len(items_shelved_unsupported)
				prof.num_items_added_internally = len(from_feed)
				prof.num_supported_stores = len(supported_stores)
				prof.num_unsupported_stores = len(all_stores) - len(supported_stores)
				prof.num_price_alerts_set = len(items_with_price_alerts_set)
				prof.num_days_since_joined = 0
				prof.num_price_alert_emails_received = 0
				prof.num_price_alert_emails_opened = 0
				prof.num_price_alert_emails_clicked = 0
				prof.save()
		except:
			print "User %s %s has no profile " % (user, user.email)
			pass
		if len(user_ops) > 30:
			print "[%s] ITEMS: %d unsupported: %d  From Feed: %d Price Alerts: %d  Stores: %d Supported Stores: %d" % (user.email, len(user_ops), len(items_shelved_unsupported),
										len(from_feed), len(items_with_price_alerts_set), len(all_stores), len(supported_stores))


def stats_by_store(start):
	items_shelved = WishlistItem.objects.select_related('user_selection', 
							'user_selection__item',
							'user_selection__item__brand').filter(user_id__date_joined__gte = start)
	
	

	stores = Brands.objects.all().order_by('-num_items_shelved')

	for s in stores:
		items = items_shelved.filter(user_selection__item__brand = s)
		prices = [item.user_selection.item.price for item in items]
		prices.sort()
		total = 0.0
		avg_price = 0.0
		median_price = 0.0
		seventyfive_percentile_price = 0.0
		if prices:
			for p in prices:
				total += p
			avg_price = total / len(prices)
			median_price = prices[len(prices)/2]
			seventyfive_percentile = 3 * len(prices) / 4
			seventyfive_percentile_price = prices[seventyfive_percentile]
		else:
			print "store %s has no prices, items %s " % (s, len(items))
		items_with_alert = items.filter(notify_lower_bound__gte = 1.0)
		s.num_items_shelved = len(items)
		s.num_items_have_price_alerts = len(items_with_alert)
		s.save()
		print "%s,%d,%d,%.2f,%.2f,%.2f" % (s.name, s.num_items_shelved, s.num_items_have_price_alerts, avg_price, median_price, seventyfive_percentile_price)
	


def stats_ordered_by_day(start):
	users = User.objects.filter(date_joined__gte = start)


	one_day = datetime.timedelta(days=1)

	today = datetime.date.today()

	start_date = start

	while start_date <= today:

		users_joined = User.objects.filter(date_joined__contains = start_date)

		items_shelved = WishlistItem.objects.select_related('user_selection', 
							'user_selection__item',
							'user_selection__item__brand').filter(user_id__date_joined__contains = start_date)

		items_shelved_unsupported = items_shelved.filter(user_selection__item__brand__supported = False)


		items_with_price_alerts_set = items_shelved.filter(notify_lower_bound__gte = 1.0)


		print "[%s] %d %d %d %d" % (start_date, len(users_joined), len(items_shelved), len(items_shelved_unsupported), len(items_with_price_alerts_set))
		start_date += one_day

'''
	Per Store stats we care about
		1. Total Items Shelved

		2. How many times Shelved

		3. Price alerts set



'''



'''
	Price Data
		1. How many total price alerts set

		2. Distribution of prices of items Shelved

		3. Distribution of price alerts
			- By store


'''


if __name__ == "__main__":
	# First release on the blog
	start_date = datetime.date(2013, 1, 24)
	stats_by_user(start_date)
	#stats_by_store(start_date)