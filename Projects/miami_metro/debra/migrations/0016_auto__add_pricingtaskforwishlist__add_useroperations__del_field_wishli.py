# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'PricingTaskforWishlist'
        db.create_table('debra_pricingtaskforwishlist', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.UserIdMap'])),
            ('item', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.UserOperations'], null=True, blank=True)),
            ('task_time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
        ))
        db.send_create_signal('debra', ['PricingTaskforWishlist'])

        # Adding model 'UserOperations'
        db.create_table('debra_useroperations', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_id', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.UserIdMap'])),
            ('color', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100, null=True, blank=True)),
            ('size', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100, null=True, blank=True)),
            ('quantity', self.gf('django.db.models.fields.IntegerField')(default='-1', max_length=50, null=True, blank=True)),
            ('img_url', self.gf('django.db.models.fields.URLField')(default='Nil', max_length=1000)),
            ('operator_type', self.gf('django.db.models.fields.IntegerField')(default=4)),
            ('item', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.ProductModel'], null=True, blank=True)),
            ('time', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
        ))
        db.send_create_signal('debra', ['UserOperations'])

        # Deleting field 'WishlistI.item'
        db.delete_column('debra_wishlisti', 'item_id')

        # Deleting field 'WishlistI.color'
        db.delete_column('debra_wishlisti', 'color')

        # Deleting field 'WishlistI.size'
        db.delete_column('debra_wishlisti', 'size')

        # Deleting field 'WishlistI.img_url'
        db.delete_column('debra_wishlisti', 'img_url')

        # Deleting field 'WishlistI.quantity'
        db.delete_column('debra_wishlisti', 'quantity')

        # Adding field 'WishlistI.base_item'
        db.add_column('debra_wishlisti', 'base_item', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['debra.UserOperations'], null=True, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting model 'PricingTaskforWishlist'
        db.delete_table('debra_pricingtaskforwishlist')

        # Deleting model 'UserOperations'
        db.delete_table('debra_useroperations')

        # Adding field 'WishlistI.item'
        db.add_column('debra_wishlisti', 'item', self.gf('django.db.models.fields.related.ForeignKey')(default='0', to=orm['debra.ProductModel'], null=True, blank=True), keep_default=False)

        # Adding field 'WishlistI.color'
        db.add_column('debra_wishlisti', 'color', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'WishlistI.size'
        db.add_column('debra_wishlisti', 'size', self.gf('django.db.models.fields.CharField')(default='Nil', max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'WishlistI.img_url'
        db.add_column('debra_wishlisti', 'img_url', self.gf('django.db.models.fields.URLField')(default='Nil', max_length=1000), keep_default=False)

        # Adding field 'WishlistI.quantity'
        db.add_column('debra_wishlisti', 'quantity', self.gf('django.db.models.fields.IntegerField')(default='-1', max_length=50, null=True, blank=True), keep_default=False)

        # Deleting field 'WishlistI.base_item'
        db.delete_column('debra_wishlisti', 'base_item_id')


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
        'debra.pricingtaskforwishlist': {
            'Meta': {'object_name': 'PricingTaskforWishlist'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.UserOperations']", 'null': 'True', 'blank': 'True'}),
            'task_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.UserIdMap']"})
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
            'tdate': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2012, 2, 11, 19, 41, 32, 488445)'}),
            'total_cnt': ('django.db.models.fields.IntegerField', [], {'default': "'-11'", 'max_length': '10'})
        },
        'debra.storecelerytasks': {
            'Meta': {'object_name': 'StoreCeleryTasks'},
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'enqueue_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'finish_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'num_items': ('django.db.models.fields.IntegerField', [], {'default': "'1'"}),
            'proc_done': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'task_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'unique': 'True', 'max_length': '200'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': "'11'", 'to': "orm['debra.UserIdMap']"}),
            'user_notify': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'debra.storeitemcombinationresults': {
            'Meta': {'object_name': 'StoreItemCombinationResults'},
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'free_shipping': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'})
        },
        'debra.tasktoitemlink': {
            'Meta': {'object_name': 'TaskToItemLink'},
            'combination_id': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']", 'null': 'True', 'blank': 'True'}),
            'item_missing': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'debra.tasktopromolink': {
            'Meta': {'object_name': 'TaskToPromoLink'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'promo': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'savings': ('django.db.models.fields.FloatField', [], {'default': "'0.0'", 'max_length': '10'}),
            'task': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.StoreCeleryTasks']", 'null': 'True', 'blank': 'True'})
        },
        'debra.useridmap': {
            'Meta': {'object_name': 'UserIdMap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addr': ('django.db.models.fields.CharField', [], {'default': "'-11.11.11.11'", 'max_length': '50'}),
            'user_id': ('django.db.models.fields.IntegerField', [], {'default': "'-1111'", 'max_length': '50'})
        },
        'debra.useroperations': {
            'Meta': {'object_name': 'UserOperations'},
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '1000'}),
            'item': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']", 'null': 'True', 'blank': 'True'}),
            'operator_type': ('django.db.models.fields.IntegerField', [], {'default': '4'}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': "'-1'", 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.UserIdMap']"})
        },
        'debra.wishlisti': {
            'Meta': {'object_name': 'WishlistI'},
            'base_item': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.UserOperations']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.UserIdMap']"})
        }
    }

    complete_apps = ['debra']
