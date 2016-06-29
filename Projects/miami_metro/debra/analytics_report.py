__author__ = 'atulsingh'

from celery.decorators import task
import datetime

from debra.models import Posts, Brands, BrandSavedCompetitors, ProductModelShelfMap
from . import feeds_helpers
from . import mongo_utils

def fill_posts_count(platform_name, brand, start_date):
    from . import feeds_helpers
    all_ids = feeds_helpers.post_ids_for_brand(platform_name, brand, max_pages=1000)
    all_posts = Posts.objects.filter(id__in=all_ids)

    return all_posts.filter(create_date__gte=start_date).count()



@task(name='debra.analytics_report.generate_report', ignore_result=True)
def generate_report(brand):


    start_week = datetime.date(2014, 6, 23)
    start_month = datetime.date(2014, 6, 1)
    start_year = datetime.date(2014, 1, 1)

    # dictionary to store one for [this week, this month, this year]
    blog_posts_count = {}
    pin_posts_count = {}
    insta_posts_count = {}
    twitter_posts_count = {}
    fb_posts_count = {}
    prod_count = {}


    blog_post_urls = {}
    pin_urls = {}
    insta_urls = {}
    twitter_urls = {}
    fb_urls = {}
    prod_pic_urls = {}

    ## blog posts
    all_blogpost_ids = feeds_helpers.post_ids_for_brand('Blogspot', brand, max_pages=1000)
    all_wp_ids = feeds_helpers.post_ids_for_brand('Wordpress', brand, max_pages=1000)
    all_tumblr_ids = feeds_helpers.post_ids_for_brand('Tumblr', brand, max_pages=1000)
    all_custom_ids = feeds_helpers.post_ids_for_brand('Custom', brand, max_pages=1000)

    all_blog_ids = all_blogpost_ids + all_wp_ids + all_tumblr_ids + all_custom_ids
    all_blog_posts = Posts.objects.filter(id__in=all_blog_ids)

    blog_posts_count['week'] = all_blog_posts.filter(create_date__gte=start_week).count()
    blog_posts_count['month'] = all_blog_posts.filter(create_date__gte=start_month).count()
    blog_posts_count['year'] = all_blog_posts.filter(create_date__gte=start_year).count()

    print "Total Blog Posts: %s" % blog_posts_count

    pin_posts_count['week'] = fill_posts_count('Pinterest', brand, start_week)
    pin_posts_count['month'] = fill_posts_count('Pinterest', brand, start_month)
    pin_posts_count['year'] = fill_posts_count('Pinterest', brand, start_year)

    print "Total Pin Posts: %s" % pin_posts_count

    insta_posts_count['week'] = fill_posts_count('Instagram', brand, start_week)
    insta_posts_count['month'] = fill_posts_count('Instagram', brand, start_month)
    insta_posts_count['year'] = fill_posts_count('Instagram', brand, start_year)

    print "Total Insta Posts: %s" % insta_posts_count


    twitter_posts_count['week'] = fill_posts_count('Twitter', brand, start_week)
    twitter_posts_count['month'] = fill_posts_count('Twitter', brand, start_month)
    twitter_posts_count['year'] = fill_posts_count('Twitter', brand, start_year)

    print "Total Tweets Posts: %s" % twitter_posts_count


    fb_posts_count['week'] = fill_posts_count('Facebook', brand, start_week)
    fb_posts_count['month'] = fill_posts_count('Facebook', brand, start_month)
    fb_posts_count['year'] = fill_posts_count('Facebook', brand, start_year)

    print "Total FB Posts: %s" % pin_posts_count

    total_products = ProductModelShelfMap.objects.filter(post__influencer__show_on_search=True,
                                                         product_model__brand=brand).distinct('product_model__img_url')
    prod_count['week'] = total_products.filter(added_datetime__gte=start_week).count()
    prod_count['month'] = total_products.filter(added_datetime__gte=start_month).count()
    prod_count['year'] = total_products.filter(added_datetime__gte=start_year).count()

    print "Total Products: %d" % total_products.count()
    report_data = {
        "brand_id": brand.id,
        "dates": {
            "start_week": int(start_week.strftime("%s")),
            "start_month": int(start_month.strftime("%s")),
            "start_year": int(start_year.strftime("%s")),
            "today": int(datetime.date.today().strftime("%s")),
        },
        "statistics_counts": {
            "blog": blog_posts_count,
            "instagram": insta_posts_count,
            "pinterest": pin_posts_count,
            "twitter": twitter_posts_count,
            "facebook": fb_posts_count,
            "products": prod_count,
        }
    }

    key_data = {
        'brand_id': brand.id,
    }

    value_data = {
        '$set': report_data
    }

    collection = mongo_utils.get_brands_counters_col()
    collection.update(key_data, value_data, upsert=True)


@task(name='debra.analytics_report.generate_complete_report', ignore_result=True)
def generate_complete_report():
    """
    for each brand, we want to get the following info:

    SUMMARY
    ======
    Total Blog Posts: (this week) / (this month) / (this year)
    Total Pinterest:
    Total Instagram:
    Total Facebook :
    Total Twitter  :
    Total Products :


    TOP 5 ITEMS:
    ===========
    Blog Posts: Pic 1, Pic 2, Pic 3, Pic 4, Pic 5
    Pinterest: Pic 1, Pic 2, Pic 3, Pic 4, Pic 5
    Instagram:
    Twitter  :
    Facebook :
    Products :


    STATS FROM YOUR COMPETITION
    ===========================
                    COMPETITION 1       COMPETITION 2   COMPETITION 3
    Blog Posts:
    Giveaways:
    Pinterest:
    Instagram:
    Twitter:
    Facebook:
    Products:


    """
    #brand = Brands.objects.filter(domain_name='zappos.com')[0]
    brands_supported = Brands.objects.filter(supported=True)
    brands_enterprise = Brands.objects.filter(stripe_plan='Enterprise')
    brands_pro = Brands.objects.filter(stripe_plan='Startup')
    brands = brands_supported | brands_enterprise | brands_pro

    competitors = BrandSavedCompetitors.objects.all()
    ids = set()
    for c in competitors:
        ids.add(c.brand.id)
        ids.add(c.competitor.id)

    brands_competitors = Brands.objects.filter(id__in=ids)
    brands = brands | brands_competitors
    brands = brands.distinct()
    for brand in brands:
        generate_report(brand)