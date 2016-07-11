"""
Contains standard way to generate reports for brands and their competitors.

So, for each 

"""
from debra import elastic_search_helpers

# RALPH LAUREN & COMPETITIVE BRANDS KEYWORDS
ralph_lauren = ['ralphlauren', 'ralph lauren', 'ralphlauren.com']
rebecca_minkoff = ['rebecca minkoff', 'rebeccaminkoff', 'rebeccaminkoff.com']
jcrew = ['jcrew', 'j.crew', 'j crew', 'j. crew', 'jcrew.com']
michael_kors = ['michael kors', 'michaelkors', 'michaelkors.com']


# REVOLVE CLOTHING & COMPETITIVE BRANDS KEYWORDS
revolve_clothing = ['revolve clothing', 'revolveclothing', 'revolveme', 'revolveclothing.com']
netaporter = ['net-a-porter', 'netaporter', 'net a porter', 'netaporter.com']
asos = ['asos', 'asos.com']
shopbop = ['shopbop', 'shop bop', 'shopbop.com']
nastygal = ['nastygal', 'nasty gal', 'nastygals', 'nasty gals', 'nastygal.com']
moda_operandi = ['moda operandi', 'modaoperandi', 'modaoperandi.com']
farfetch = ['farfetch', 'farfetch.com']
the_outnet = ['theoutnet', 'the outnet', 'theoutnet.com']
free_people = ['freepeople', 'free people', 'freepeople.com']
zappos = ['zappos', 'zapposcouture', 'zappos couture', 'zappos.com']
lord_and_taylor = ['lordandtaylor', 'lord and taylor', 'lordandtaylor.com']
barneys = ['barneys', 'barneys.com']
bergdorf = ['bergdorf', 'bergdorfs', 'bergdorfgoodman', 'bergdorf goodman', 'bergdorfgoodman.com']
saks = ['saks', 'saksfifthavenue', 'saks fifth avenue', 'saksfifthavenue.com']
bluefly = ['bluefly', 'blue fly', 'bluefly.com']
ann_taylor = ['anntaylor', 'ann taylor', 'anntaylor.com']


chloe_and_isabel = ['chloe and isabel', 'chloe & isabel', 'chloeandisabel', 'chloeandisabel.com']
stellab_and_dot = ['stella and dot', 'stella & dot', 'stelladot', 'stelladot.com']


required_matching_posts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 30, 35, 40, 45, 50]

def convert_keywords(kw):
	result = []
	for r in kw:
		b = ['post_content', r]
		result.append(b)
	print("Input: %s  Output: %s" % (kw, result))
	return result

def print_distribution(total, distribution):
	count = 0
	count_pct = 0.0
	for s in distribution:
		if type(distribution) == type(list()):
			print("%r;%d;%.2f" % (s[0], s[1], s[1]*100.0/total))
			count += s[1]
			count_pct += s[1]*100.0/total
		if type(distribution) == type({}):
			print("%r;%d;%.2f" % (s, distribution[s], distribution[s]*100/total))
			count += distribution[s]
			count_pct += distribution[s] * 100.0/total
		if count_pct > 99.9:
			print("Others;%d;%.2f" % (total-count), (total-count)*100/total)
			return


def influencer_and_post_reports(brand_name, searchable_kws, limit=len(required_matching_posts), group_concatenator='or'):
	"""
	This dumps two things for a given set of keywords (it could be a single brand or multiple brand keywords)
	a) Total posts and posts per post_per_platform
	b) Total influencers and then varies # of mentions
	"""
	
	# 1st report is about influencer stats based on minimum posts matching
	result = {}
	
	total_post, post_per_platform = elastic_search_helpers.helper_post_platform_stats(condition=searchable_kws, group_concatenator=group_concatenator)
	for m in required_matching_posts[:limit]:
		total, _ = elastic_search_helpers.helper_influencer_stats(condition=searchable_kws, min_satisfying_posts=m, group_concatenator=group_concatenator)
		result[m] = total

	heading = 'Brand;' + ';'.join([str(i) for i in required_matching_posts])

	result_str = brand_name +';' + ';'.join([str(i) for i in result.values()]) 
	
	print heading
	print result_str
	print("Total Posts: %d" % total_post)
	print_distribution(total_post, post_per_platform)
	print("-----------")

def all_brands_mentioned_by_influencers(brand_name, searchable_kws, group_concatenator='or'):
	"""
	This first find all influencers for these keywords and then find ALL products mentioned by these
	influencers. And then dumps the distribution for:
	a) brand distribution
	b) affiliate distribution
	c) category distribution
	"""
	
	total, total_products, total_with_affiliates, sorted_brand_domains, affiliate_links, categories = elastic_search_helpers.helper_productshelfmap_info(searchable_kws, group_concatenator=group_concatenator)

	print("Total Products;%d;Total Affiliate;%d" % (total_products, total_with_affiliates))

	print("Brands Mentioned by Influencers of %s" % brand_name)
	print_distribution(total_products, sorted_brand_domains)
	print("Affiliate Links used by Influencers of %s" % brand_name)
	print_distribution(total_products, affiliate_links)
	print("Category distribution of %s" % brand_name)
	print_distribution(total_products, categories)


def product_information_for_a_single_brand_or_retailer(brand_name=None, domain_name=None, designer_name=None, product_name=None):

	total_products, total_with_affiliates, sorted_brand_domains, affiliate_links, categories = elastic_search_helpers.find_product_info_for_brand(brand_name=brand_name,
		domain_name=domain_name,
		designer_name=designer_name,
		product_name=product_name)

	print("Product information for %s" % brand_name)
	print("Total Products;%d" % total_products)
	print("Total Affiliates;%d" % total_with_affiliates)
	print_distribution(total_products, sorted_brand_domains)
	print_distribution(total_products, affiliate_links)
	print_distribution(total_products, categories)

def group_brand_reports():
	searchable_kws = convert_keywords(revolve_clothing)
	influencer_and_post_reports('revolve', [searchable_kws])

	searchable_kws = convert_keywords(netaporter)
	influencer_and_post_reports('netaporter', searchable_kws)

	searchable_kws = convert_keywords(asos)
	influencer_and_post_reports('asos', searchable_kws)
	
	searchable_kws = convert_keywords(shopbop)
	influencer_and_post_reports('shopbop', searchable_kws)
	
	searchable_kws = convert_keywords(nastygal)
	influencer_and_post_reports('nastygal', searchable_kws)

	searchable_kws = convert_keywords(moda_operandi)
	influencer_and_post_reports('moda operandi', searchable_kws)

	searchable_kws = convert_keywords(farfetch)
	influencer_and_post_reports('farfetch', searchable_kws)
	
	searchable_kws = convert_keywords(the_outnet)
	influencer_and_post_reports('the_outnet', searchable_kws)

	searchable_kws = convert_keywords(free_people)
	influencer_and_post_reports('free_people', searchable_kws)

	searchable_kws = convert_keywords(zappos)
	influencer_and_post_reports('zappos', searchable_kws)

	searchable_kws = convert_keywords(lord_and_taylor)
	influencer_and_post_reports('lord_and_taylor', searchable_kws)

	searchable_kws = convert_keywords(barneys)
	influencer_and_post_reports('barneys', searchable_kws)

	searchable_kws = convert_keywords(bergdorf)
	influencer_and_post_reports('bergdorf', searchable_kws)

	searchable_kws = convert_keywords(saks)
	influencer_and_post_reports('saks', searchable_kws)

	searchable_kws = convert_keywords(bluefly)
	influencer_and_post_reports('bluefly',  searchable_kws)

	searchable_kws = convert_keywords(ann_taylor)
	influencer_and_post_reports('ann taylor', searchable_kws)


def basic_info(brand_name, keywords):
	searchable_kws = convert_keywords(keywords)
	influencer_and_post_reports(brand_name, [searchable_kws])
	all_brands_mentioned_by_influencers(brand_name, [searchable_kws])

def get_revolve_info():
	searchable_kws = convert_keywords(revolve_clothing)
	basic_info('revolve', revolve_clothing)
	#product_information_for_a_single_brand_or_retailer(brand_name='revolve clothing', domain_name='revolveclothing.com', designer_name='revolve clothing')

	# other brands we want to compare with
	# asos, shopbop, zappos, bluefly, ann_taylor
	searchable_kws_asos = convert_keywords(asos)
	searchable_kws_shopbop = convert_keywords(shopbop)
	searchable_kws_zappos = convert_keywords(zappos)
	searchable_kws_bluefly = convert_keywords(bluefly)
	searchable_kws_anntaylor = convert_keywords(ann_taylor)

	influencer_and_post_reports('revolve_asos', [searchable_kws, searchable_kws_asos], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('revolve_shopbop', [searchable_kws, searchable_kws_shopbop], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('revolve_zappos', [searchable_kws, searchable_kws_zappos], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('revolve_bluefly', [searchable_kws, searchable_kws_bluefly], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('revolve_anntaylor', [searchable_kws, searchable_kws_anntaylor], group_concatenator='and_same', limit=1)


def get_bluefly_info():
	searchable_kws = convert_keywords(bluefly)
	basic_info('bluefly', bluefly)
	#product_information_for_a_single_brand_or_retailer(brand_name='bluefly', domain_name='bluefly.com', designer_name='Bluefly')

	# other brands we want to compare with
	# asos, shopbop, zappos, bluefly, ann_taylor
	searchable_kws_netaporter = convert_keywords(netaporter)
	searchable_kws_asos = convert_keywords(asos)
	searchable_kws_shopbop = convert_keywords(shopbop)
	searchable_kws_zappos = convert_keywords(zappos)
	searchable_kws_bergdorf = convert_keywords(bergdorf)
	searchable_kws_barneys = convert_keywords(barneys)
	searchable_kws_anntaylor = convert_keywords(ann_taylor)

	influencer_and_post_reports('bluefly_netaporter', [searchable_kws, searchable_kws_netaporter], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('bluefly_shopbop', [searchable_kws, searchable_kws_shopbop], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('bluefly_zappos', [searchable_kws, searchable_kws_zappos], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('bluefly_asos', [searchable_kws, searchable_kws_asos], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('bluefly_anntaylor', [searchable_kws, searchable_kws_anntaylor], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('bluefly_bergdorf', [searchable_kws, searchable_kws_bergdorf], group_concatenator='and_same', limit=1)
	influencer_and_post_reports('bluefly_barneys', [searchable_kws, searchable_kws_barneys], group_concatenator='and_same', limit=1)


def get_zappos_info():
	pass


def get_chloe_and_isabel_info():
	pass
if __name__ == '__main__':
	#group_brand_reports()
	#get_revolve_info()
	#get_bluefly_info()
	product_information_for_a_single_brand_or_retailer(brand_name='revolve clothing', domain_name='revolveclothing.com', designer_name='revolve clothing')
	product_information_for_a_single_brand_or_retailer(brand_name='bluefly', domain_name='bluefly.com', designer_name='Bluefly')







