# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'UserProfile.newsletter_enabled'
        db.add_column('debra_userprofile', 'newsletter_enabled', self.gf('django.db.models.fields.BooleanField')(default=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'UserProfile.newsletter_enabled'
        db.delete_column('debra_userprofile', 'newsletter_enabled')


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
        'debra.brands': {
            'Meta': {'object_name': 'Brands'},
            'domain_name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'logo_blueimg_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'logo_img_url': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'shopstyle_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
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
            'err_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idx': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '200'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'prod_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '300'}),
            'promo_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'})
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
        'debra.promoinfo': {
            'Meta': {'object_name': 'Promoinfo'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'd': ('django.db.models.fields.DateField', [], {}),
            'exclude_category': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'free_shipping_lower_bound': ('django.db.models.fields.FloatField', [], {'default': '10000'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item_category': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'promo_disc_amount': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'promo_disc_lower_bound': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'promo_disc_perc': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'promo_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sex_category': ('django.db.models.fields.IntegerField', [], {'default': '2'}),
            'store': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'validity': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'where_avail': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        'debra.promorawtext': {
            'Meta': {'object_name': 'PromoRawText'},
            'data_source': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'insert_date': ('django.db.models.fields.DateField', [], {}),
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
            'tdate': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2012, 9, 21, 5, 19, 42, 623534)'}),
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
            'finish_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
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
            'prices_changed_more': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'})
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
            'about_me': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'access_token': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'blog_url': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'date_of_birth': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'facebook_id': ('django.db.models.fields.BigIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'facebook_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'facebook_profile_url': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '1', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.files.ImageField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'newsletter_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'raw_data': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'}),
            'website_url': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'debra.usershelfiterrors': {
            'Meta': {'object_name': 'UserShelfitErrors'},
            'extra_info': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'problematic_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.wishlistitem': {
            'Meta': {'object_name': 'WishlistItem'},
            'calculated_price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'cat1': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat2': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'cat3': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '25'}),
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'compare_flag': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'how_many_out_of_stock': ('django.db.models.fields.IntegerField', [], {'default': "'0'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_buylist': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
        }
    }

    complete_apps = ['debra']
