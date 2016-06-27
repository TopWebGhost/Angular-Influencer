# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'UserProfile.name'
        db.add_column('debra_userprofile', 'name', self.gf('django.db.models.fields.CharField')(default='Your name?', max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile.blog_name'
        db.add_column('debra_userprofile', 'blog_name', self.gf('django.db.models.fields.CharField')(default="Your blog's name?", max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'Bloggers.facebook_url'
        db.add_column('debra_bloggers', 'facebook_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'Bloggers.pinterest_url'
        db.add_column('debra_bloggers', 'pinterest_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'Bloggers.bloglovin_url'
        db.add_column('debra_bloggers', 'bloglovin_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'Bloggers.twitter_url'
        db.add_column('debra_bloggers', 'twitter_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'Bloggers.fb_followers'
        db.add_column('debra_bloggers', 'fb_followers', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'Bloggers.twitter_followers'
        db.add_column('debra_bloggers', 'twitter_followers', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'Bloggers.pinterest_followers'
        db.add_column('debra_bloggers', 'pinterest_followers', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'Bloggers.bloglovin_followers'
        db.add_column('debra_bloggers', 'bloglovin_followers', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Changing field 'Bloggers.blog_url'
        db.alter_column('debra_bloggers', 'blog_url', self.gf('django.db.models.fields.URLField')(max_length=1000, null=True))


    def backwards(self, orm):
        
        # Deleting field 'UserProfile.name'
        db.delete_column('debra_userprofile', 'name')

        # Deleting field 'UserProfile.blog_name'
        db.delete_column('debra_userprofile', 'blog_name')

        # Deleting field 'Bloggers.facebook_url'
        db.delete_column('debra_bloggers', 'facebook_url')

        # Deleting field 'Bloggers.pinterest_url'
        db.delete_column('debra_bloggers', 'pinterest_url')

        # Deleting field 'Bloggers.bloglovin_url'
        db.delete_column('debra_bloggers', 'bloglovin_url')

        # Deleting field 'Bloggers.twitter_url'
        db.delete_column('debra_bloggers', 'twitter_url')

        # Deleting field 'Bloggers.fb_followers'
        db.delete_column('debra_bloggers', 'fb_followers')

        # Deleting field 'Bloggers.twitter_followers'
        db.delete_column('debra_bloggers', 'twitter_followers')

        # Deleting field 'Bloggers.pinterest_followers'
        db.delete_column('debra_bloggers', 'pinterest_followers')

        # Deleting field 'Bloggers.bloglovin_followers'
        db.delete_column('debra_bloggers', 'bloglovin_followers')

        # Changing field 'Bloggers.blog_url'
        db.alter_column('debra_bloggers', 'blog_url', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000))


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
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'debra.addpopupchange': {
            'Meta': {'object_name': 'AddPopupChange'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Brands']"}),
            'color_new': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'color_orig': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'create_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_new': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'img_orig': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'name_new': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'name_orig': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'price_new': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'price_orig': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.ProductModel']"}),
            'size_new': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'size_orig': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'debra.bloggers': {
            'Meta': {'object_name': 'Bloggers'},
            'account_created': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'blog_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'blogger_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'bloglovin_followers': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'bloglovin_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'created_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email_addr': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'facebook_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'fb_followers': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'intro_email_sent_date': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'intro_response_date': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'pinterest_followers': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'pinterest_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'profile_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000'}),
            'twitter_followers': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'twitter_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'upgraded_to_blogger': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'})
        },
        'debra.brands': {
            'Meta': {'object_name': 'Brands'},
            'crawler_name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '50'}),
            'disable_tracking_temporarily': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'domain_name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'icon_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '50'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logo_blueimg_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'logo_img_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'num_items_have_price_alerts': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_items_shelved': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'partially_supported': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'promo_discovery_support': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'shopstyle_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'start_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'supported': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'debra.categories': {
            'Meta': {'object_name': 'Categories'},
            'brand': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['debra.Brands']", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'})
        },
        'debra.categorymodel': {
            'Meta': {'object_name': 'CategoryModel'},
            'categoryId': ('django.db.models.fields.IntegerField', [], {'default': "'-111'", 'max_length': '50'}),
            'categoryName': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']"})
        },
        'debra.colorsizemodel': {
            'Meta': {'object_name': 'ColorSizeModel'},
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '500'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']"}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '500'})
        },
        'debra.combinationofuserops': {
            'Meta': {'object_name': 'CombinationOfUserOps'},
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'how_many_out_of_stock': ('django.db.models.fields.IntegerField', [], {'default': "'0'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item_out_of_stock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'tracking_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'user_selection': ('django.db.models.fields.related.ForeignKey', [], {'default': "'2'", 'to': "orm['debra.UserOperations']", 'null': 'True', 'blank': 'True'})
        },
        'debra.emailfromteaserpage': {
            'Meta': {'object_name': 'EmailFromTeaserPage'},
            'email_addr': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'time_registered': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'})
        },
        'debra.items': {
            'Meta': {'object_name': 'Items'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'cat1': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'cat2': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'cat3': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'cat4': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'cat5': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url_lg': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'img_url_md': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'img_url_sm': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'pr_colors': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '600'}),
            'pr_currency': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'pr_id': ('django.db.models.fields.IntegerField', [], {'default': '-1', 'max_length': '100'}),
            'pr_instock': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '10'}),
            'pr_retailer': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'pr_sizes': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '600'}),
            'pr_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'20.00'", 'max_length': '10'}),
            'product_model_key': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['debra.ProductModel']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'10.00'", 'max_length': '10'})
        },
        'debra.preferredbrands': {
            'Meta': {'object_name': 'PreferredBrands'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.pricingtasks': {
            'Meta': {'object_name': 'PricingTasks'},
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'enqueue_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'finish_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'free_shipping': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'num_items': ('django.db.models.fields.IntegerField', [], {'default': "'1'"}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'proc_done': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'task_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'unique': 'True', 'max_length': '200'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'user_notify': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
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
            'cat1': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat10': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat2': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat3': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat4': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat5': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat6': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat7': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat8': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat9': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'description': ('django.db.models.fields.TextField', [], {'default': "'Nil'"}),
            'designer_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'err_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idx': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '2000'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'num_fb_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_pins': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_twitter_mentions': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'prod_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '2000'}),
            'promo_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'track_last_finish_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'null': 'True', 'blank': 'True'}),
            'track_last_start_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'null': 'True', 'blank': 'True'})
        },
        'debra.productprice': {
            'Meta': {'object_name': 'ProductPrice'},
            'finish_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        'debra.promodashboardunit': {
            'Meta': {'object_name': 'PromoDashboardUnit'},
            'checked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'create_time': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 4, 26, 0, 52, 12, 323832)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'promo_info': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'promo_raw': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.PromoRawText']", 'null': 'True', 'blank': 'True'}),
            'promo_updated_text': ('django.db.models.fields.TextField', [], {}),
            'updated_time': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 4, 26, 0, 52, 12, 323858)'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.promoinfo': {
            'Meta': {'object_name': 'Promoinfo'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'd': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 4, 26, 0, 52, 12, 322938)'}),
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
            'raw_text': ('django.db.models.fields.TextField', [], {}),
            'store': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"})
        },
        'debra.promotionapplied': {
            'Meta': {'object_name': 'PromotionApplied'},
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'promo': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'savings': ('django.db.models.fields.FloatField', [], {'default': "'0.0'", 'max_length': '10'}),
            'task': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.PricingTasks']", 'null': 'True', 'blank': 'True'})
        },
        'debra.shelf': {
            'Meta': {'object_name': 'Shelf'},
            'brand': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_inspiration': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'We should have a name'", 'max_length': '100'}),
            'num_dislikes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_views': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'public_sharing_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'public_sharing_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'system_cat': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_created_cat': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.shelfcomments': {
            'Meta': {'object_name': 'ShelfComments'},
            'comment': ('django.db.models.fields.TextField', [], {}),
            'comment_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'profile_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'shelf': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Shelf']", 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'default': "'Guest User'", 'max_length': '100'})
        },
        'debra.ssitemstats': {
            'Meta': {'object_name': 'SSItemStats'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'category': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '10'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-111.00'", 'max_length': '10'}),
            'price_selection_metric': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sale_cnt': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-111.00'", 'max_length': '10'}),
            'tdate': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 4, 26, 0, 52, 12, 329312)'}),
            'total_cnt': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'})
        },
        'debra.storepreferencesfromteaserpage': {
            'Meta': {'object_name': 'StorePreferencesFromTeaserPage'},
            'aber': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'aerie': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'agnus': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'aldo': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'american_eagle': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ann_taylor': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'anthro': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'armani': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'associated_email_addr': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.EmailFromTeaserPage']", 'null': 'True', 'blank': 'True'}),
            'bebe': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'betsy': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'books_brothers': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'br': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'burberry': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'coach': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'diesel': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'dkny': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'donna': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'exp': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'extra': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'forever': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'fossil': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'french_connection': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'gap': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'guess': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'h_and_m': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'hollister': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jcrew': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'kate_spade': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lacoste': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lane_bryant': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'levis': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'limited': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lucky': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'miss_sixty': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nicole_miller': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nike': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nine_west': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ny_co': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'old_navy': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ralph_lauren': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'steve_madden': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'thomas_pink': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'top_shop': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'true_religion': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'united_colors': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'urban_outfitters': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'victoria': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'white_house_black_market': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'zara': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'debra.storespecificitemcategory': {
            'Meta': {'object_name': 'StoreSpecificItemCategory'},
            'age_group': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '10'}),
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'categoryName': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '10'}),
            'hash_val': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '33'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'debra.taskdailystats': {
            'Meta': {'object_name': 'TaskDailyStats'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Brands']"}),
            'finish_time': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'num_active_items': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_became_avail': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_became_unavail': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_dups': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_prices_decr': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_prices_incr': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_prices_unchg': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_tasks_started': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_tested_avail': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'num_tested_price': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'}),
            'prices_changed_25': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'prices_changed_50': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'prices_changed_75': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'prices_changed_more': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'time_taken_for_tasks': ('django.db.models.fields.IntegerField', [], {'default': "'0'", 'max_length': '50'})
        },
        'debra.userassignedcategory': {
            'Meta': {'object_name': 'UserAssignedCategory'},
            'categoryIcon': ('django.db.models.fields.files.ImageField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'categoryName': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.useridmap': {
            'Meta': {'object_name': 'UserIdMap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addr': ('django.db.models.fields.CharField', [], {'default': "'-11.11.11.11'", 'max_length': '50'}),
            'user_id': ('django.db.models.fields.IntegerField', [], {'default': "'-1111'", 'unique': 'True', 'max_length': '50'})
        },
        'debra.useroperations': {
            'Meta': {'object_name': 'UserOperations'},
            'calculated_price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'datetime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'how_many_out_of_stock': ('django.db.models.fields.IntegerField', [], {'default': "'0'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']", 'null': 'True', 'blank': 'True'}),
            'item_out_of_stock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'operator_type': ('django.db.models.fields.IntegerField', [], {'default': '4'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': "'-1'", 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
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
            'access_token': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'blog_name': ('django.db.models.fields.CharField', [], {'default': '"Your blog\'s name?"', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'blog_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'date_of_birth': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'default_shelves_created': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'facebook_id': ('django.db.models.fields.BigIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'facebook_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'facebook_open_graph': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'facebook_profile_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '1', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.files.ImageField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'image1': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image10': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image2': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image3': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image4': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image5': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image6': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image7': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image8': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'image9': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Your name?'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'newsletter_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'num_buy_link_clicks': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_days_since_joined': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
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
            'raw_data': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'}),
            'website_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        'debra.usershelfiterrors': {
            'Meta': {'object_name': 'UserShelfitErrors'},
            'extra_info': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'problematic_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.usertutorialstatus': {
            'Meta': {'object_name': 'UserTutorialStatus'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'page_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000'}),
            'tutorial_status': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.wishlistitem': {
            'Meta': {'object_name': 'WishlistItem'},
            'affiliate_prod_link': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'affiliate_source_wishlist_id': ('django.db.models.fields.IntegerField', [], {'default': "'-1'", 'max_length': '100'}),
            'avail_sizes': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'bought': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'calculated_price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'cat1': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat2': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat3': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'compare_flag': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'how_many_out_of_stock': ('django.db.models.fields.IntegerField', [], {'default': "'0'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url_feed_view': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_panel_view': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_shelf_view': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'in_buylist': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'item_out_of_stock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'notify_lower_bound': ('django.db.models.fields.FloatField', [], {'default': "'-1'", 'max_length': '10'}),
            'promo_applied': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'savings': ('django.db.models.fields.FloatField', [], {'default': "'0'", 'max_length': '10'}),
            'shipping_cost': ('django.db.models.fields.FloatField', [], {'default': "'-1'", 'max_length': '10'}),
            'snooze': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'time_notified_last': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'time_price_calculated_last': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user_assigned_cat': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.UserAssignedCategory']", 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'user_selection': ('django.db.models.fields.related.ForeignKey', [], {'default': "'2'", 'to': "orm['debra.UserOperations']", 'null': 'True', 'blank': 'True'})
        },
        'debra.wishlistitemshelfmap': {
            'Meta': {'object_name': 'WishlistItemShelfMap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'num_dislikes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'shelf': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Shelf']", 'null': 'True', 'blank': 'True'}),
            'wishlist_item': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.WishlistItem']", 'null': 'True', 'blank': 'True'})
        },
        'debra.wishlistuacategorymap': {
            'Meta': {'object_name': 'WishlistUACategoryMap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'shelf': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.UserAssignedCategory']", 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'wishlist_item': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.WishlistItem']", 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['debra']
