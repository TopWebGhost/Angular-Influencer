# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'ScrapingResult'
        db.create_table('xps_scrapingresult', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('product_model', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.ProductModel'], null=True, blank=True)),
            ('flag', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('tag', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('xps', ['ScrapingResult'])

        # Adding model 'XPathExpr'
        db.create_table('xps_xpathexpr', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('scraping_result', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['xps.ScrapingResult'])),
            ('list_index', self.gf('django.db.models.fields.IntegerField')()),
            ('expr', self.gf('django.db.models.fields.CharField')(max_length=4096)),
        ))
        db.send_create_signal('xps', ['XPathExpr'])

        # Adding model 'ScrapingResultSet'
        db.create_table('xps_scrapingresultset', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['debra.Brands'])),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=1024)),
        ))
        db.send_create_signal('xps', ['ScrapingResultSet'])

        # Adding model 'ScrapingResultSetEntry'
        db.create_table('xps_scrapingresultsetentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('scraping_result_set', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['xps.ScrapingResultSet'])),
            ('scraping_result', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['xps.ScrapingResult'])),
        ))
        db.send_create_signal('xps', ['ScrapingResultSetEntry'])

        # Adding model 'CorrectValue'
        db.create_table('xps_correctvalue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('product_model', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['debra.ProductModel'])),
            ('tag', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=1024)),
        ))
        db.send_create_signal('xps', ['CorrectValue'])

        # Adding model 'FoundValue'
        db.create_table('xps_foundvalue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('product_model', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['debra.ProductModel'])),
            ('tag', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=1024)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('xps', ['FoundValue'])


    def backwards(self, orm):
        
        # Deleting model 'ScrapingResult'
        db.delete_table('xps_scrapingresult')

        # Deleting model 'XPathExpr'
        db.delete_table('xps_xpathexpr')

        # Deleting model 'ScrapingResultSet'
        db.delete_table('xps_scrapingresultset')

        # Deleting model 'ScrapingResultSetEntry'
        db.delete_table('xps_scrapingresultsetentry')

        # Deleting model 'CorrectValue'
        db.delete_table('xps_correctvalue')

        # Deleting model 'FoundValue'
        db.delete_table('xps_foundvalue')


    models = {
        'debra.brands': {
            'Meta': {'object_name': 'Brands'},
            'crawler_name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '50'}),
            'disable_tracking_temporarily': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'domain_name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
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
            'incomplete_flag': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
        'xps.correctvalue': {
            'Meta': {'object_name': 'CorrectValue'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product_model': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.ProductModel']"}),
            'tag': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        'xps.foundvalue': {
            'Meta': {'object_name': 'FoundValue'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product_model': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.ProductModel']"}),
            'tag': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
        },
        'xps.scrapingresult': {
            'Meta': {'object_name': 'ScrapingResult'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'flag': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product_model': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.ProductModel']", 'null': 'True', 'blank': 'True'}),
            'tag': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'xps.scrapingresultset': {
            'Meta': {'object_name': 'ScrapingResultSet'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Brands']"}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'xps.scrapingresultsetentry': {
            'Meta': {'object_name': 'ScrapingResultSetEntry'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'scraping_result': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['xps.ScrapingResult']"}),
            'scraping_result_set': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['xps.ScrapingResultSet']"})
        },
        'xps.xpathexpr': {
            'Meta': {'object_name': 'XPathExpr'},
            'expr': ('django.db.models.fields.CharField', [], {'max_length': '4096'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'list_index': ('django.db.models.fields.IntegerField', [], {}),
            'scraping_result': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['xps.ScrapingResult']"})
        }
    }

    complete_apps = ['xps']
