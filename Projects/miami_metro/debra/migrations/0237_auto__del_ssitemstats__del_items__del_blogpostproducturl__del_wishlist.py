# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting model 'SSItemStats'
        db.delete_table('debra_ssitemstats')

        # Deleting model 'Items'
        db.delete_table('debra_items')

        # Deleting model 'BlogPostProductUrl'
        db.delete_table('debra_blogpostproducturl')

        # Deleting model 'WishlistUACategoryMap'
        db.delete_table('debra_wishlistuacategorymap')

        # Deleting model 'AddPopupChange'
        db.delete_table('debra_addpopupchange')

        # Deleting model 'BloggerFollowersTimeSeries'
        db.delete_table('debra_bloggerfollowerstimeseries')

        # Deleting model 'CategoryModel'
        db.delete_table('debra_categorymodel')

        # Deleting model 'BlogPost'
        db.delete_table('debra_blogpost')

        # Deleting model 'socialprofiles'
        db.delete_table('debra_socialprofiles')

        # Deleting model 'UserTutorialStatus'
        db.delete_table('debra_usertutorialstatus')

        # Deleting model 'UserShelfitErrors'
        db.delete_table('debra_usershelfiterrors')

        # Deleting model 'ShelfBloggerWidgetImages'
        db.delete_table('debra_shelfbloggerwidgetimages')

        # Deleting model 'StoreSpecificItemCategory'
        db.delete_table('debra_storespecificitemcategory')

        # Deleting model 'BloggerBloglovinProfiles'
        db.delete_table('debra_bloggerbloglovinprofiles')

        # Deleting model 'BlogPostComment'
        db.delete_table('debra_blogpostcomment')

        # Deleting model 'SponsoredBlogPostContent'
        db.delete_table('debra_sponsoredblogpostcontent')

        # Deleting model 'BloggerContactTemplateEmails'
        db.delete_table('debra_bloggercontacttemplateemails')

        # Deleting model 'PreferredBrands'
        db.delete_table('debra_preferredbrands')

        # Deleting model 'ShelfComments'
        db.delete_table('debra_shelfcomments')

        # Deleting model 'PricingTasks'
        db.delete_table('debra_pricingtasks')

        # Deleting model 'EmailFromTeaserPage'
        db.delete_table('debra_emailfromteaserpage')

        # Deleting model 'TaskDailyStats'
        db.delete_table('debra_taskdailystats')

        # Deleting model 'StorePreferencesFromTeaserPage'
        db.delete_table('debra_storepreferencesfromteaserpage')

        # Deleting model 'Bloggers'
        db.delete_table('debra_bloggers')

        # Deleting model 'UserIdMap'
        db.delete_table('debra_useridmap')

        # Deleting model 'BlogAdUnit'
        db.delete_table('debra_blogadunit')

        # Deleting model 'Categories'
        db.delete_table('debra_categories')

        # Removing M2M table for field brand on 'Categories'
        db.delete_table('debra_categories_brand')

        # Deleting model 'CombinationOfUserOps'
        db.delete_table('debra_combinationofuserops')

        # Deleting field 'PromotionApplied.task'
        db.delete_column('debra_promotionapplied', 'task_id')


    def backwards(self, orm):
        
        # Adding model 'SSItemStats'
        db.create_table('debra_ssitemstats', (
            ('total_cnt', self.gf('django.db.models.fields.IntegerField')(default='-11', max_length=10)),
            ('price_selection_metric', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(default='1', to=orm['debra.Brands'])),
            ('saleprice', self.gf('django.db.models.fields.FloatField')(default='-111.00', max_length=10)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('category', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=10)),
            ('gender', self.gf('django.db.models.fields.CharField')(default='A', max_length=10)),
            ('tdate', self.gf('django.db.models.fields.DateField')(default=datetime.datetime(2013, 12, 15, 8, 17, 20, 944570))),
            ('sale_cnt', self.gf('django.db.models.fields.IntegerField')(default='-11', max_length=10)),
            ('price', self.gf('django.db.models.fields.FloatField')(default='-111.00', max_length=10)),
        ))
        db.send_create_signal('debra', ['SSItemStats'])

        # Adding model 'Items'
        db.create_table('debra_items', (
            ('pr_currency', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('insert_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('pr_url', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('pr_instock', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=10)),
            ('img_url_md', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('cat1', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100)),
            ('cat3', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100)),
            ('price', self.gf('django.db.models.fields.FloatField')(default='20.00', max_length=10)),
            ('product_model_key', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['debra.ProductModel'], unique=True, null=True, blank=True)),
            ('pr_retailer', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(default='1', to=orm['debra.Brands'])),
            ('img_url_sm', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('saleprice', self.gf('django.db.models.fields.FloatField')(default='10.00', max_length=10)),
            ('img_url_lg', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('name', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('pr_id', self.gf('django.db.models.fields.IntegerField')(default=-1, max_length=100)),
            ('gender', self.gf('django.db.models.fields.CharField')(default='A', max_length=10)),
            ('pr_colors', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=600)),
            ('pr_sizes', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=600)),
            ('cat2', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100)),
            ('cat4', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100)),
            ('cat5', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100)),
        ))
        db.send_create_signal('debra', ['Items'])

        # Adding model 'BlogPostProductUrl'
        db.create_table('debra_blogpostproducturl', (
            ('blog_post', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.BlogPost'], null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('prod_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
        ))
        db.send_create_signal('debra', ['BlogPostProductUrl'])

        # Adding model 'WishlistUACategoryMap'
        db.create_table('debra_wishlistuacategorymap', (
            ('wishlist_item', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.WishlistItem'], null=True, blank=True)),
            ('shelf', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.UserAssignedCategory'], null=True, blank=True)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['WishlistUACategoryMap'])

        # Adding model 'AddPopupChange'
        db.create_table('debra_addpopupchange', (
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('product', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['debra.ProductModel'])),
            ('img_orig', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('size_new', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('size_orig', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['debra.Brands'])),
            ('price_orig', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('img_new', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('name_orig', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('create_time', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('price_new', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('color_orig', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('color_new', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name_new', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
        ))
        db.send_create_signal('debra', ['AddPopupChange'])

        # Adding model 'BloggerFollowersTimeSeries'
        db.create_table('debra_bloggerfollowerstimeseries', (
            ('fb_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('twitter_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('pinterest_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('sampling_date', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True, blank=True)),
            ('blogger', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('bloglovin_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['BloggerFollowersTimeSeries'])

        # Adding model 'CategoryModel'
        db.create_table('debra_categorymodel', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('product', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.ProductModel'])),
            ('categoryId', self.gf('django.db.models.fields.IntegerField')(default='-111', max_length=50)),
            ('categoryName', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100)),
        ))
        db.send_create_signal('debra', ['CategoryModel'])

        # Adding model 'BlogPost'
        db.create_table('debra_blogpost', (
            ('issue_date', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True, blank=True)),
            ('title', self.gf('django.db.models.fields.CharField')(default=None, max_length=1000, null=True, blank=True)),
            ('blogger', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('bloglovin_blogger', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.BloggerBloglovinProfiles'], null=True, blank=True)),
            ('is_sponsored', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['BlogPost'])

        # Adding model 'socialprofiles'
        db.create_table('debra_socialprofiles', (
            ('sampling_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now, null=True, blank=True)),
            ('bloglovin_profile', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.BloggerBloglovinProfiles'], null=True, blank=True)),
            ('bloglovin_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('twitter_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('facebook_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['socialprofiles'])

        # Adding model 'UserTutorialStatus'
        db.create_table('debra_usertutorialstatus', (
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('tutorial_status', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('page_url', self.gf('django.db.models.fields.URLField')(default='Nil', max_length=1000)),
        ))
        db.send_create_signal('debra', ['UserTutorialStatus'])

        # Adding model 'UserShelfitErrors'
        db.create_table('debra_usershelfiterrors', (
            ('problematic_url', self.gf('django.db.models.fields.URLField')(default='Nil', max_length=1000)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('extra_info', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=1000, null=True, blank=True)),
        ))
        db.send_create_signal('debra', ['UserShelfitErrors'])

        # Adding model 'ShelfBloggerWidgetImages'
        db.create_table('debra_shelfbloggerwidgetimages', (
            ('num_rows', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('widget_id_str', self.gf('django.db.models.fields.CharField')(default=None, max_length=1000, null=True, blank=True)),
            ('num_elems', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('img_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('wishlist_shelf_map', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.WishlistItemShelfMap'], null=True, blank=True)),
            ('widget_id', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('debra', ['ShelfBloggerWidgetImages'])

        # Adding model 'StoreSpecificItemCategory'
        db.create_table('debra_storespecificitemcategory', (
            ('hash_val', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=33)),
            ('categoryName', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100)),
            ('gender', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=10)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(default='1', to=orm['debra.Brands'])),
            ('age_group', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=10)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['StoreSpecificItemCategory'])

        # Adding model 'BloggerBloglovinProfiles'
        db.create_table('debra_bloggerbloglovinprofiles', (
            ('email', self.gf('django.db.models.fields.EmailField')(default=None, max_length=75, null=True, blank=True)),
            ('twitter_handle', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('blog_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=10000, null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('facebook_handle', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('bloglovin_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=10000, null=True, blank=True)),
            ('blog_name', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
        ))
        db.send_create_signal('debra', ['BloggerBloglovinProfiles'])

        # Adding model 'BlogPostComment'
        db.create_table('debra_blogpostcomment', (
            ('blog_post', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.BlogPost'], null=True, blank=True)),
            ('comment', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('issue_date', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True, blank=True)),
            ('comment_poster', self.gf('django.db.models.fields.CharField')(default=None, max_length=1000, null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['BlogPostComment'])

        # Adding model 'SponsoredBlogPostContent'
        db.create_table('debra_sponsoredblogpostcontent', (
            ('blog_post', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.BlogPost'], null=True, blank=True)),
            ('sponsored_stuff', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.Brands'], null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['SponsoredBlogPostContent'])

        # Adding model 'BloggerContactTemplateEmails'
        db.create_table('debra_bloggercontacttemplateemails', (
            ('template_body', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('template_name', self.gf('django.db.models.fields.CharField')(default='Default template', max_length=1000)),
            ('template_subj', self.gf('django.db.models.fields.CharField')(default='Hi there', max_length=1000)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['BloggerContactTemplateEmails'])

        # Adding model 'PreferredBrands'
        db.create_table('debra_preferredbrands', (
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(default='1', to=orm['debra.Brands'])),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['PreferredBrands'])

        # Adding model 'ShelfComments'
        db.create_table('debra_shelfcomments', (
            ('comment', self.gf('django.db.models.fields.TextField')()),
            ('comment_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('profile_img_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=2000, null=True, blank=True)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('shelf', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.Shelf'], null=True, blank=True)),
            ('username', self.gf('django.db.models.fields.CharField')(default='Guest User', max_length=100)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['ShelfComments'])

        # Adding model 'PricingTasks'
        db.create_table('debra_pricingtasks', (
            ('num_items', self.gf('django.db.models.fields.IntegerField')(default='1')),
            ('price', self.gf('django.db.models.fields.FloatField')(default='-11.0', max_length=10)),
            ('proc_done', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('saleprice', self.gf('django.db.models.fields.FloatField')(default='-11.0', max_length=10)),
            ('user_notify', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('free_shipping', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('task_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200, unique=True)),
            ('finish_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('combination_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('enqueue_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('start_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
        ))
        db.send_create_signal('debra', ['PricingTasks'])

        # Adding model 'EmailFromTeaserPage'
        db.create_table('debra_emailfromteaserpage', (
            ('ip_addr', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('email_addr', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('time_registered', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
        ))
        db.send_create_signal('debra', ['EmailFromTeaserPage'])

        # Adding model 'TaskDailyStats'
        db.create_table('debra_taskdailystats', (
            ('num_became_unavail', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('num_tasks_started', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('num_became_avail', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('finish_time', self.gf('django.db.models.fields.DateField')()),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['debra.Brands'])),
            ('num_prices_unchg', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('num_tested_avail', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('time_taken_for_tasks', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('prices_changed_50', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('num_tested_price', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('num_active_items', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('num_dups', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('prices_changed_75', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('prices_changed_25', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('num_prices_decr', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('prices_changed_more', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('num_prices_incr', self.gf('django.db.models.fields.IntegerField')(default='0', max_length=50)),
        ))
        db.send_create_signal('debra', ['TaskDailyStats'])

        # Adding model 'StorePreferencesFromTeaserPage'
        db.create_table('debra_storepreferencesfromteaserpage', (
            ('limited', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('coach', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('aber', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('extra', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('h_and_m', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('american_eagle', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('aldo', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('guess', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('lacoste', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('anthro', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('jcrew', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('betsy', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ralph_lauren', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('urban_outfitters', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('lucky', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('gap', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('nicole_miller', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('bebe', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('top_shop', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('nine_west', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('armani', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('levis', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('donna', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('zara', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('white_house_black_market', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('aerie', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('kate_spade', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('burberry', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ann_taylor', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('united_colors', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('french_connection', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('nike', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('diesel', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('lane_bryant', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('fossil', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('steve_madden', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('thomas_pink', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('dkny', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('associated_email_addr', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['debra.EmailFromTeaserPage'], null=True, blank=True)),
            ('miss_sixty', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('agnus', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('br', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('hollister', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('victoria', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('old_navy', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('forever', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('books_brothers', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('exp', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ny_co', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('true_religion', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('debra', ['StorePreferencesFromTeaserPage'])

        # Adding model 'Bloggers'
        db.create_table('debra_bloggers', (
            ('comment', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True)),
            ('pinterest_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('blogger_type', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('email_addr', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('intro_email_sent_date', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True, blank=True)),
            ('blog_name', self.gf('django.db.models.fields.CharField')(default='Blog name', max_length=1000, null=True, blank=True)),
            ('intro_response_date', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True, blank=True)),
            ('bloglovin_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('profile_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('contact_initiator', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('twitter_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('facebook_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('bloglovin_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('fb_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('twitter_followers', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('pinterest_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(default='Blogger name', max_length=100, null=True, blank=True)),
            ('upgraded_to_blogger', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True, blank=True)),
            ('blog_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('created_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('account_created', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True, blank=True)),
        ))
        db.send_create_signal('debra', ['Bloggers'])

        # Adding model 'UserIdMap'
        db.create_table('debra_useridmap', (
            ('user_id', self.gf('django.db.models.fields.IntegerField')(default='-1111', max_length=50, unique=True)),
            ('ip_addr', self.gf('django.db.models.fields.CharField')(default='-11.11.11.11', max_length=50)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['UserIdMap'])

        # Adding model 'BlogAdUnit'
        db.create_table('debra_blogadunit', (
            ('ad_img_height', self.gf('django.db.models.fields.FloatField')(default=0.0)),
            ('ad_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('sampling_date', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True, blank=True)),
            ('ad_img_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True)),
            ('blogger', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('ad_img_width', self.gf('django.db.models.fields.FloatField')(default=0.0)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['BlogAdUnit'])

        # Adding model 'Categories'
        db.create_table('debra_categories', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100)),
        ))
        db.send_create_signal('debra', ['Categories'])

        # Adding M2M table for field brand on 'Categories'
        db.create_table('debra_categories_brand', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('categories', models.ForeignKey(orm['debra.categories'], null=False)),
            ('brands', models.ForeignKey(orm['debra.brands'], null=False))
        ))
        db.create_unique('debra_categories_brand', ['categories_id', 'brands_id'])

        # Adding model 'CombinationOfUserOps'
        db.create_table('debra_combinationofuserops', (
            ('item_out_of_stock', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['auth.User'], null=True, blank=True)),
            ('how_many_out_of_stock', self.gf('django.db.models.fields.IntegerField')(default='0')),
            ('task_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('combination_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('tracking_enabled', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('debra', ['CombinationOfUserOps'])

        # Adding field 'PromotionApplied.task'
        db.add_column('debra_promotionapplied', 'task', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.PricingTasks'], null=True, blank=True), keep_default=False)


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2013, 12, 18, 1, 56, 51, 470523)'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2013, 12, 18, 1, 56, 51, 470424)'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'debra.alexarankinginfo': {
            'Meta': {'object_name': 'AlexaRankingInfo'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keywords': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'links_in_count': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'page_views': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'platform': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Platform']", 'null': 'True', 'blank': 'True'}),
            'rank': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'rank_by_city': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'rank_by_country': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'reach': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'seo_loadtime': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'sites_linking_in': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'snapshot_date': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'})
        },
        'debra.betabrandrequests': {
            'Meta': {'object_name': 'BetaBrandRequests'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100'}),
            'signup_user': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200'}),
            'signup_user_email': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200'}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'debra.brands': {
            'Meta': {'object_name': 'Brands'},
            'crawler_name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '50'}),
            'disable_tracking_temporarily': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'domain_name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200', 'db_index': 'True'}),
            'icon_id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'logo_blueimg_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'logo_img_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'num_items_have_price_alerts': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_items_shelved': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_shelfers': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'partially_supported': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'product_img_xpath': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'product_name_xpath': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'product_price_xpath': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'promo_discovery_support': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'shopstyle_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'start_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'supported': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'debra.colorsizemodel': {
            'Meta': {'object_name': 'ColorSizeModel'},
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '500'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']"}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '500'})
        },
        'debra.embeddable': {
            'Meta': {'object_name': 'Embeddable'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.UserProfile']"}),
            'html': ('django.db.models.fields.TextField', [], {'max_length': '5000'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lottery': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Lottery']", 'null': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'default': "'collage_widget'", 'max_length': '50'})
        },
        'debra.follower': {
            'Meta': {'object_name': 'Follower'},
            'demographics_age': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'demographics_fbid': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'demographics_fbpic': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'demographics_gender': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'default': 'None', 'max_length': '75', 'null': 'True', 'blank': 'True'}),
            'firstname': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'follower_recurringscore': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_blogger': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'lastname': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'location': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'num_interactions': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'shelf_user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'})
        },
        'debra.influencer': {
            'Meta': {'object_name': 'Influencer'},
            'blog_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'bloglovin_followers': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'bloglovin_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'brands_liked': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'demographics_bloggerage': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'demographics_fbid': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'demographics_fbpic': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'demographics_first_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'demographics_gender': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'demographics_last_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'demographics_location': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'default': 'None', 'max_length': '75', 'null': 'True', 'blank': 'True'}),
            'fb_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'followers_overalldemographics_averageage': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'followers_overalldemographics_percentbloggers': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'followers_overalldemographics_percentmale': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'followers_overalldemographics_topcountry': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'insta_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Blogger name'", 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'pin_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'ranking_blogger_follower_score': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'ranking_blogger_quality_score': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'ranking_monetization_score': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'ranking_overallengagement_mediascore': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'ranking_overallengagement_recurringscore': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'ranking_overallseo_score': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'ranking_posting_rate_score': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'shelf_user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'top_followers': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'tw_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        'debra.lottery': {
            'Meta': {'object_name': 'Lottery'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.UserProfile']"}),
            'end_date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'start_date': ('django.db.models.fields.DateField', [], {}),
            'terms': ('django.db.models.fields.TextField', [], {'max_length': '5000', 'null': 'True', 'blank': 'True'}),
            'theme': ('django.db.models.fields.CharField', [], {'default': "'theme_pink'", 'max_length': '20'})
        },
        'debra.lotteryentry': {
            'Meta': {'object_name': 'LotteryEntry'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_winner': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lottery': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Lottery']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.UserProfile']"})
        },
        'debra.lotteryentrycompletedtask': {
            'Meta': {'object_name': 'LotteryEntryCompletedTask'},
            'custom_task_response': ('django.db.models.fields.CharField', [], {'max_length': '300', 'null': 'True', 'blank': 'True'}),
            'entry': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.LotteryEntry']"}),
            'entry_validation_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'task': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.LotteryTask']"}),
            'touch_datetime': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        'debra.lotterypartner': {
            'Meta': {'object_name': 'LotteryPartner'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lottery': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Lottery']"}),
            'partner': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.UserProfile']"})
        },
        'debra.lotteryprize': {
            'Meta': {'object_name': 'LotteryPrize'},
            'brand': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lottery': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Lottery']"}),
            'quantity': ('django.db.models.fields.IntegerField', [], {})
        },
        'debra.lotterytask': {
            'Meta': {'object_name': 'LotteryTask'},
            'custom_option': ('django.db.models.fields.CharField', [], {'default': "('text_field', 'include a text field')", 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lottery': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Lottery']"}),
            'mandatory': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'point_value': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'requirement_text': ('django.db.models.fields.CharField', [], {'max_length': '300', 'null': 'True', 'blank': 'True'}),
            'requirement_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'step_id': ('django.db.models.fields.IntegerField', [], {'default': '-1'}),
            'task': ('django.db.models.fields.CharField', [], {'default': "'twitter_follow'", 'max_length': '200'}),
            'url_target_name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'url_to_visit': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'validation_required': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'debra.mechanicalturktask': {
            'Meta': {'object_name': 'MechanicalTurkTask'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'task_id': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'task_type': ('django.db.models.fields.CharField', [], {'default': "'emails_promo_info'", 'max_length': '100'})
        },
        'debra.platform': {
            'Meta': {'object_name': 'Platform'},
            'about': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'bloggers_linked': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'blogname': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'brandfit_matrix': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'cover_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'create_date': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_platform_recurringscore': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'growth_category': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'has_frame': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'influencer': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Influencer']", 'null': 'True', 'blank': 'True'}),
            'monetization_numads': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'monetization_percentsponsored': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'monetization_revenueestimate': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'num_followers': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'num_following': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'numposts': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'platform_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'posting_rate': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'profile_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'reference_score': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'social_handle': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'total_numcomments': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'total_numlikes': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'total_numshares': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'db_index': 'True', 'blank': 'True'})
        },
        'debra.popularitytimeseries': {
            'Meta': {'object_name': 'PopularityTimeSeries'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'influencer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Influencer']"}),
            'num_followers': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'num_following': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'platform': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Platform']"}),
            'snapshot_date': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'})
        },
        'debra.postinteractions': {
            'Meta': {'object_name': 'PostInteractions'},
            'api_id': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'content': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '10000', 'null': 'True', 'blank': 'True'}),
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            'follower': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Follower']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'if_commented': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'if_liked': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'if_shared': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'numlikes': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'post': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Posts']"})
        },
        'debra.posts': {
            'Meta': {'object_name': 'Posts'},
            'api_id': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'content': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'content_numpics': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'content_numvideos': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'create_date': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numcomments': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numfbshares': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numlikes': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numrepins': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numretweets': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numshares': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'final_product_urls': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'influencer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Influencer']"}),
            'is_sponsored': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'location': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'maxmediasize': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'num_prizes': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'platform': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Platform']", 'null': 'True', 'blank': 'True'}),
            'prize_money': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'products_import_completed': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'})
        },
        'debra.productavailability': {
            'Meta': {'object_name': 'ProductAvailability'},
            'avail': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'finish_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.ColorSizeModel']"})
        },
        'debra.productmodel': {
            'Meta': {'object_name': 'ProductModel'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'c_idx': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '300', 'blank': 'True'}),
            'cat1': ('django.db.models.fields.CharField', [], {'max_length': '25', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': "'Nil'"}),
            'designer_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'err_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idx': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '2000'}),
            'incomplete_flag': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'num_fb_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_pins': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_twitter_mentions': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'prod_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '2000', 'db_index': 'True'}),
            'promo_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'track_last_finish_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'null': 'True', 'blank': 'True'}),
            'track_last_start_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'null': 'True', 'blank': 'True'})
        },
        'debra.productprice': {
            'Meta': {'object_name': 'ProductPrice'},
            'finish_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'orig_price': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.ColorSizeModel']"}),
            'shipping_cost': ('django.db.models.fields.FloatField', [], {'default': "'-1.0'", 'max_length': '10'})
        },
        'debra.productpromotion': {
            'Meta': {'object_name': 'ProductPromotion'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductPrice']", 'null': 'True', 'blank': 'True'}),
            'promo': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'savings': ('django.db.models.fields.FloatField', [], {'default': "'0.0'", 'max_length': '10'})
        },
        'debra.productsinposts': {
            'Meta': {'object_name': 'ProductsInPosts'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_affiliate_link': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_valid_product': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'orig_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'post': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Posts']"}),
            'prod': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.ProductModel']", 'null': 'True', 'blank': 'True'})
        },
        'debra.promodashboardunit': {
            'Meta': {'object_name': 'PromoDashboardUnit'},
            'checked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'create_time': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 12, 18, 1, 56, 50, 915465)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'promo_info': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'promo_raw': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.PromoRawText']", 'null': 'True', 'blank': 'True'}),
            'promo_updated_text': ('django.db.models.fields.TextField', [], {}),
            'updated_time': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 12, 18, 1, 56, 50, 915491)'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.promoinfo': {
            'Meta': {'object_name': 'Promoinfo'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'd': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 12, 18, 1, 56, 50, 914197)'}),
            'end_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'exclude_category': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'free_shipping_lower_bound': ('django.db.models.fields.FloatField', [], {'default': '10000'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item_category': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'promo_disc_amount': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'promo_disc_lower_bound': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'promo_disc_perc': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'promo_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sex_category': ('django.db.models.fields.IntegerField', [], {'default': '2'}),
            'start_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'store': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'validity': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'where_avail': ('django.db.models.fields.IntegerField', [], {'default': '2'})
        },
        'debra.promorawtext': {
            'Meta': {'object_name': 'PromoRawText'},
            'data_source': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'initial_type': ('django.db.models.fields.CharField', [], {'default': "'storewide'", 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'insert_date': ('django.db.models.fields.DateField', [], {}),
            'processed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'raw_text': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'store': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"})
        },
        'debra.promotionapplied': {
            'Meta': {'object_name': 'PromotionApplied'},
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'promo': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'savings': ('django.db.models.fields.FloatField', [], {'default': "'0.0'", 'max_length': '10'})
        },
        'debra.shelf': {
            'Meta': {'object_name': 'Shelf'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Brands']", 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_inspiration': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'num_dislikes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_items': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_views': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'public_sharing_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'public_sharing_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'shelf_img': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'user_created_cat': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'shelves'", 'null': 'True', 'blank': 'True', 'to': "orm['auth.User']"})
        },
        'debra.styletag': {
            'Meta': {'object_name': 'StyleTag'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'debra.userassignedcategory': {
            'Meta': {'object_name': 'UserAssignedCategory'},
            'categoryIcon': ('django.db.models.fields.files.ImageField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'categoryName': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.userfollowmap': {
            'Meta': {'unique_together': "(('user', 'following'),)", 'object_name': 'UserFollowMap'},
            'following': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'follows'", 'to': "orm['debra.UserProfile']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'users'", 'to': "orm['debra.UserProfile']"})
        },
        'debra.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            '_aboutme': ('django.db.models.fields.TextField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            '_bloglovin_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            '_can_create_inspiration_shelf': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            '_can_set_affiliate_links': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            '_comment_on_shelf': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            '_facebook_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            '_giveaway_emails': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            '_invite_to_shelf': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            '_is_a_shelfalista': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            '_is_female': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            '_location': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            '_notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            '_picture_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            '_pinterest_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            '_profile_img_url': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            '_publish_on_facebook_timeline': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            '_twitter_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            '_username': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            '_web_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            '_web_page2': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            '_web_page3': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'about_me': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'aboutme': ('django.db.models.fields.TextField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'access_token': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'account_management_notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'blog_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'blog_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'blog_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'bloglovin_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'brand': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['debra.Brands']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'can_set_affiliate_links': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'chloe_isable_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'cover_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'date_of_birth': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'deal_roundup_notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'default_shelves_created': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'etsy_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'facebook_id': ('django.db.models.fields.BigIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'facebook_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'facebook_open_graph': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'facebook_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'facebook_profile_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '1', 'null': 'True', 'blank': 'True'}),
            'gravatar_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.files.ImageField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'image1': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image10': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image2': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image3': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image4': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image5': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image6': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image7': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image8': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'image9': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'instagram_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'is_female': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_trendsetter': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'location': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'newsletter_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'num_buy_link_clicks': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_days_since_joined': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_followers': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_following': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_invites_sent': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_items_added_internally': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_items_from_supported_stores': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_items_in_shelves': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_price_alert_emails_clicked': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_price_alert_emails_opened': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_price_alert_emails_received': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_price_alerts_set': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_shelves': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_shelves_created': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_supported_stores': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_unsupported_stores': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'opportunity_notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'pinterest_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'price_alerts_notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'privilege_level': ('django.db.models.fields.CharField', [], {'default': "(0, 'Default')", 'max_length': '50'}),
            'profile_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'raw_data': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'social_interaction_notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'store_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'style_bio': ('django.db.models.fields.TextField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'style_tags': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '1000', 'null': 'True'}),
            'twitter_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'web_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'website_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'youtube_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        'debra.wishlistitem': {
            'Meta': {'object_name': 'WishlistItem'},
            'added_datetime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'db_index': 'True'}),
            'affiliate_prod_link': ('django.db.models.fields.URLField', [], {'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'affiliate_source_wishlist_id': ('django.db.models.fields.IntegerField', [], {'default': "'-1'", 'max_length': '100'}),
            'avail_sizes': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'bought': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'calculated_price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'compare_flag': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'current_product_price': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.ProductPrice']", 'null': 'True'}),
            'how_many_out_of_stock': ('django.db.models.fields.IntegerField', [], {'default': "'0'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_feed_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_original': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_panel_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_shelf_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_thumbnail_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'imported_from_blog': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'in_buylist': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'item_out_of_stock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'notify_lower_bound': ('django.db.models.fields.FloatField', [], {'default': "'-1'", 'max_length': '10'}),
            'product_model': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.ProductModel']"}),
            'promo_applied': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'savings': ('django.db.models.fields.FloatField', [], {'default': "'0'", 'max_length': '10'}),
            'shipping_cost': ('django.db.models.fields.FloatField', [], {'default': "'-1'", 'max_length': '10'}),
            'show_on_feed': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'snooze': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'time_notified_last': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'time_price_calculated_last': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user_assigned_cat': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.UserAssignedCategory']", 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'wishlist_items'", 'null': 'True', 'blank': 'True', 'to': "orm['auth.User']"})
        },
        'debra.wishlistitemshelfmap': {
            'Meta': {'object_name': 'WishlistItemShelfMap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'num_dislikes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'shelf': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Shelf']", 'null': 'True', 'blank': 'True'}),
            'wishlist_item': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.WishlistItem']", 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['debra']
