from django.contrib.sitemaps import Sitemap
from django.core.urlresolvers import reverse
from debra.models import UserProfile, ProductModelShelfMap

class UserSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7

    def items(self):
        return UserProfile.objects.filter(brand__isnull=True).all()

    def lastmod(self, obj):
        return obj.last_modified

class BrandSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return UserProfile.objects.filter(brand__isnull=False).all()

    def lastmod(self, obj):
        return obj.last_modified

class ProductSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.6

    def items(self):
        return ProductModelShelfMap.objects.filter(img_url_panel_view__isnull=False).all()

    def lastmod(self, obj):
        return obj.time_price_calculated_last


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'daily'

    def items(self):
        account = lambda v: 'debra.account_views.{view}'.format(view=v)
        company = lambda v: 'debra.company_views.{view}'.format(view=v)
        explore = lambda v: 'debra.explore_views.{view}'.format(view=v)
        return [account('home'), explore('inspiration'), explore('trendsetters'), explore('trending_brands'),
                company('contact'), company('hiring'), company('press_kit'), company('about_us'),
                company('bloggers'), company('privacy'), company('support'), company('get_shelfit_button')]

    def location(self, item):
        return reverse(item)