# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting model 'PricingTaskToWishlistItemLink'
        db.delete_table('debra_pricingtasktowishlistitemlink')

        # Deleting model 'TaskToPromoLink'
        db.delete_table('debra_tasktopromolink')

        # Deleting model 'StoreItemCombinationResults'
        db.delete_table('debra_storeitemcombinationresults')

        # Deleting model 'StoreCeleryTasks'
        db.delete_table('debra_storecelerytasks')

        # Adding model 'PricingTasks'
        db.create_table('debra_pricingtasks', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default='11', to=orm['debra.UserIdMap'])),
            ('combination_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('task_id', self.gf('django.db.models.fields.CharField')(default='Nil', unique=True, max_length=200)),
            ('user_notify', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('proc_done', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('enqueue_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('start_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('finish_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('num_items', self.gf('django.db.models.fields.IntegerField')(default='1')),
            ('price', self.gf('django.db.models.fields.FloatField')(default='-11.0', max_length=10)),
            ('saleprice', self.gf('django.db.models.fields.FloatField')(default='-11.0', max_length=10)),
            ('free_shipping', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('debra', ['PricingTasks'])

        # Adding model 'CombinationOfUserOps'
        db.create_table('debra_combinationofuserops', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.UserIdMap'])),
            ('combination_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('user_selection', self.gf('django.db.models.fields.related.ForeignKey')(default='2', to=orm['debra.UserOperations'], null=True, blank=True)),
            ('item_out_of_stock', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('how_many_out_of_stock', self.gf('django.db.models.fields.IntegerField')(default='0')),
            ('tracking_enabled', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('task_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
        ))
        db.send_create_signal('debra', ['CombinationOfUserOps'])

        # Adding model 'PromotionApplied'
        db.create_table('debra_promotionapplied', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('promo', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.Promoinfo'], null=True, blank=True)),
            ('task', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.PricingTasks'], null=True, blank=True)),
            ('savings', self.gf('django.db.models.fields.FloatField')(default='0.0', max_length=10)),
        ))
        db.send_create_signal('debra', ['PromotionApplied'])


    def backwards(self, orm):
        
        # Adding model 'PricingTaskToWishlistItemLink'
        db.create_table('debra_pricingtasktowishlistitemlink', (
            ('user_selection', self.gf('django.db.models.fields.related.ForeignKey')(default='2', to=orm['debra.UserOperations'], null=True, blank=True)),
            ('item_out_of_stock', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.UserIdMap'])),
            ('how_many_out_of_stock', self.gf('django.db.models.fields.IntegerField')(default='0')),
            ('combination_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('tracking_enabled', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('debra', ['PricingTaskToWishlistItemLink'])

        # Adding model 'TaskToPromoLink'
        db.create_table('debra_tasktopromolink', (
            ('promo', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.Promoinfo'], null=True, blank=True)),
            ('savings', self.gf('django.db.models.fields.FloatField')(default='0.0', max_length=10)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('task', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.StoreCeleryTasks'], null=True, blank=True)),
        ))
        db.send_create_signal('debra', ['TaskToPromoLink'])

        # Adding model 'StoreItemCombinationResults'
        db.create_table('debra_storeitemcombinationresults', (
            ('free_shipping', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('combination_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('price', self.gf('django.db.models.fields.FloatField')(default='-11.0', max_length=10)),
            ('completion_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2012, 2, 14, 16, 15, 5, 166332))),
            ('saleprice', self.gf('django.db.models.fields.FloatField')(default='-11.0', max_length=10)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('debra', ['StoreItemCombinationResults'])

        # Adding model 'StoreCeleryTasks'
        db.create_table('debra_storecelerytasks', (
            ('user_notify', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('start_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('proc_done', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('num_items', self.gf('django.db.models.fields.IntegerField')(default='1')),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default='11', to=orm['debra.UserIdMap'])),
            ('task_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200, unique=True)),
            ('finish_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('combination_id', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=200)),
            ('enqueue_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
        ))
        db.send_create_signal('debra', ['StoreCeleryTasks'])

        # Deleting model 'PricingTasks'
        db.delete_table('debra_pricingtasks')

        # Deleting model 'CombinationOfUserOps'
        db.delete_table('debra_combinationofuserops')

        # Deleting model 'PromotionApplied'
        db.delete_table('debra_promotionapplied')


    models = {
        'debra.brands': {
            'Meta': {'object_name': 'Brands'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'})
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
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '50'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']"}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '50'})
        },
        'debra.combinationofuserops': {
            'Meta': {'object_name': 'CombinationOfUserOps'},
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'how_many_out_of_stock': ('django.db.models.fields.IntegerField', [], {'default': "'0'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item_out_of_stock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'tracking_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.UserIdMap']"}),
            'user_selection': ('django.db.models.fields.related.ForeignKey', [], {'default': "'2'", 'to': "orm['debra.UserOperations']", 'null': 'True', 'blank': 'True'})
        },
        'debra.items': {
            'Meta': {'object_name': 'Items'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'cat1': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'cat2': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'cat3': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'cat4': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'cat5': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '6'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url_lg': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'img_url_md': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'img_url_sm': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'pr_colors': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '600'}),
            'pr_currency': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
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
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': "'11'", 'to': "orm['debra.UserIdMap']"}),
            'user_notify': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'debra.productmodel': {
            'Meta': {'object_name': 'ProductModel'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'description': ('django.db.models.fields.TextField', [], {'default': "'Nil'"}),
            'err_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '6'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idx': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '200'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'prod_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '200'}),
            'promo_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'})
        },
        'debra.promoinfo': {
            'Meta': {'unique_together': "(('store', 'd', 'promo_type', 'promo_disc_perc', 'promo_disc_amount', 'promo_disc_lower_bound', 'sex_category', 'item_category'),)", 'object_name': 'Promoinfo'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'd': ('django.db.models.fields.DateField', [], {}),
            'free_shipping_lower_bound': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item_category': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'promo_disc_amount': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'promo_disc_lower_bound': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'promo_disc_perc': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'promo_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sex_category': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'store': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'validity': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'where_avail': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        'debra.promotionapplied': {
            'Meta': {'object_name': 'PromotionApplied'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'promo': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'savings': ('django.db.models.fields.FloatField', [], {'default': "'0.0'", 'max_length': '10'}),
            'task': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.PricingTasks']", 'null': 'True', 'blank': 'True'})
        },
        'debra.ssitemstats': {
            'Meta': {'object_name': 'SSItemStats'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': "'1'", 'to': "orm['debra.Brands']"}),
            'category': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '10'}),
            'gender': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '6'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-111.00'", 'max_length': '10'}),
            'price_selection_metric': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sale_cnt': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-111.00'", 'max_length': '10'}),
            'tdate': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2012, 2, 15, 21, 28, 8, 84637)'}),
            'total_cnt': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'})
        },
        'debra.useridmap': {
            'Meta': {'object_name': 'UserIdMap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addr': ('django.db.models.fields.CharField', [], {'default': "'-11.11.11.11'", 'max_length': '50'}),
            'user_id': ('django.db.models.fields.IntegerField', [], {'default': "'-1111'", 'unique': 'True', 'max_length': '50'})
        },
        'debra.useroperations': {
            'Meta': {'object_name': 'UserOperations'},
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'datetime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']", 'null': 'True', 'blank': 'True'}),
            'operator_type': ('django.db.models.fields.IntegerField', [], {'default': '4'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': "'-1'", 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.UserIdMap']"})
        },
        'debra.wishlistitem': {
            'Meta': {'object_name': 'WishlistItem'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.UserIdMap']"}),
            'user_selection': ('django.db.models.fields.related.ForeignKey', [], {'default': "'2'", 'to': "orm['debra.UserOperations']", 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['debra']
