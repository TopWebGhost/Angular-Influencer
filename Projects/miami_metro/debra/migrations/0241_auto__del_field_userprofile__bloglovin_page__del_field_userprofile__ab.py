# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting field 'UserProfile._bloglovin_page'
        db.delete_column('debra_userprofile', '_bloglovin_page')

        # Deleting field 'UserProfile._aboutme'
        db.delete_column('debra_userprofile', '_aboutme')

        # Deleting field 'UserProfile.num_price_alerts_set'
        db.delete_column('debra_userprofile', 'num_price_alerts_set')

        # Deleting field 'UserProfile.num_supported_stores'
        db.delete_column('debra_userprofile', 'num_supported_stores')

        # Deleting field 'UserProfile._can_create_inspiration_shelf'
        db.delete_column('debra_userprofile', '_can_create_inspiration_shelf')

        # Deleting field 'UserProfile._username'
        db.delete_column('debra_userprofile', '_username')

        # Deleting field 'UserProfile.num_price_alert_emails_opened'
        db.delete_column('debra_userprofile', 'num_price_alert_emails_opened')

        # Deleting field 'UserProfile._picture_page'
        db.delete_column('debra_userprofile', '_picture_page')

        # Deleting field 'UserProfile.num_items_added_internally'
        db.delete_column('debra_userprofile', 'num_items_added_internally')

        # Deleting field 'UserProfile.num_items_from_supported_stores'
        db.delete_column('debra_userprofile', 'num_items_from_supported_stores')

        # Deleting field 'UserProfile._is_female'
        db.delete_column('debra_userprofile', '_is_female')

        # Deleting field 'UserProfile._can_set_affiliate_links'
        db.delete_column('debra_userprofile', '_can_set_affiliate_links')

        # Deleting field 'UserProfile._web_page3'
        db.delete_column('debra_userprofile', '_web_page3')

        # Deleting field 'UserProfile._web_page2'
        db.delete_column('debra_userprofile', '_web_page2')

        # Deleting field 'UserProfile._giveaway_emails'
        db.delete_column('debra_userprofile', '_giveaway_emails')

        # Deleting field 'UserProfile._pinterest_page'
        db.delete_column('debra_userprofile', '_pinterest_page')

        # Deleting field 'UserProfile._publish_on_facebook_timeline'
        db.delete_column('debra_userprofile', '_publish_on_facebook_timeline')

        # Deleting field 'UserProfile.num_price_alert_emails_clicked'
        db.delete_column('debra_userprofile', 'num_price_alert_emails_clicked')

        # Deleting field 'UserProfile._comment_on_shelf'
        db.delete_column('debra_userprofile', '_comment_on_shelf')

        # Deleting field 'UserProfile._notification'
        db.delete_column('debra_userprofile', '_notification')

        # Deleting field 'UserProfile.num_unsupported_stores'
        db.delete_column('debra_userprofile', 'num_unsupported_stores')

        # Deleting field 'UserProfile.num_price_alert_emails_received'
        db.delete_column('debra_userprofile', 'num_price_alert_emails_received')

        # Deleting field 'UserProfile.chloe_isable_page'
        db.delete_column('debra_userprofile', 'chloe_isable_page')

        # Deleting field 'UserProfile._invite_to_shelf'
        db.delete_column('debra_userprofile', '_invite_to_shelf')

        # Deleting field 'UserProfile.username'
        db.delete_column('debra_userprofile', 'username')

        # Deleting field 'UserProfile._twitter_page'
        db.delete_column('debra_userprofile', '_twitter_page')

        # Deleting field 'UserProfile.num_buy_link_clicks'
        db.delete_column('debra_userprofile', 'num_buy_link_clicks')

        # Deleting field 'UserProfile.num_shelves_created'
        db.delete_column('debra_userprofile', 'num_shelves_created')

        # Deleting field 'UserProfile._location'
        db.delete_column('debra_userprofile', '_location')

        # Deleting field 'UserProfile._facebook_page'
        db.delete_column('debra_userprofile', '_facebook_page')

        # Deleting field 'UserProfile._is_a_shelfalista'
        db.delete_column('debra_userprofile', '_is_a_shelfalista')

        # Deleting field 'UserProfile.num_invites_sent'
        db.delete_column('debra_userprofile', 'num_invites_sent')

        # Deleting field 'UserProfile.num_days_since_joined'
        db.delete_column('debra_userprofile', 'num_days_since_joined')

        # Deleting field 'UserProfile._profile_img_url'
        db.delete_column('debra_userprofile', '_profile_img_url')

        # Deleting field 'UserProfile._web_page'
        db.delete_column('debra_userprofile', '_web_page')


    def backwards(self, orm):
        
        # Adding field 'UserProfile._bloglovin_page'
        db.add_column('debra_userprofile', '_bloglovin_page', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._aboutme'
        db.add_column('debra_userprofile', '_aboutme', self.gf('django.db.models.fields.TextField')(default=None, max_length=2000, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile.num_price_alerts_set'
        db.add_column('debra_userprofile', 'num_price_alerts_set', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile.num_supported_stores'
        db.add_column('debra_userprofile', 'num_supported_stores', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile._can_create_inspiration_shelf'
        db.add_column('debra_userprofile', '_can_create_inspiration_shelf', self.gf('django.db.models.fields.BooleanField')(default=False), keep_default=False)

        # Adding field 'UserProfile._username'
        db.add_column('debra_userprofile', '_username', self.gf('django.db.models.fields.CharField')(default=None, max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile.num_price_alert_emails_opened'
        db.add_column('debra_userprofile', 'num_price_alert_emails_opened', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile._picture_page'
        db.add_column('debra_userprofile', '_picture_page', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile.num_items_added_internally'
        db.add_column('debra_userprofile', 'num_items_added_internally', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile.num_items_from_supported_stores'
        db.add_column('debra_userprofile', 'num_items_from_supported_stores', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile._is_female'
        db.add_column('debra_userprofile', '_is_female', self.gf('django.db.models.fields.BooleanField')(default=True), keep_default=False)

        # Adding field 'UserProfile._can_set_affiliate_links'
        db.add_column('debra_userprofile', '_can_set_affiliate_links', self.gf('django.db.models.fields.BooleanField')(default=False), keep_default=False)

        # Adding field 'UserProfile._web_page3'
        db.add_column('debra_userprofile', '_web_page3', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._web_page2'
        db.add_column('debra_userprofile', '_web_page2', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._giveaway_emails'
        db.add_column('debra_userprofile', '_giveaway_emails', self.gf('django.db.models.fields.BooleanField')(default=True), keep_default=False)

        # Adding field 'UserProfile._pinterest_page'
        db.add_column('debra_userprofile', '_pinterest_page', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._publish_on_facebook_timeline'
        db.add_column('debra_userprofile', '_publish_on_facebook_timeline', self.gf('django.db.models.fields.BooleanField')(default=True), keep_default=False)

        # Adding field 'UserProfile.num_price_alert_emails_clicked'
        db.add_column('debra_userprofile', 'num_price_alert_emails_clicked', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile._comment_on_shelf'
        db.add_column('debra_userprofile', '_comment_on_shelf', self.gf('django.db.models.fields.BooleanField')(default=True), keep_default=False)

        # Adding field 'UserProfile._notification'
        db.add_column('debra_userprofile', '_notification', self.gf('django.db.models.fields.BooleanField')(default=True), keep_default=False)

        # Adding field 'UserProfile.num_unsupported_stores'
        db.add_column('debra_userprofile', 'num_unsupported_stores', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile.num_price_alert_emails_received'
        db.add_column('debra_userprofile', 'num_price_alert_emails_received', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile.chloe_isable_page'
        db.add_column('debra_userprofile', 'chloe_isable_page', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._invite_to_shelf'
        db.add_column('debra_userprofile', '_invite_to_shelf', self.gf('django.db.models.fields.BooleanField')(default=True), keep_default=False)

        # Adding field 'UserProfile.username'
        db.add_column('debra_userprofile', 'username', self.gf('django.db.models.fields.CharField')(default=None, max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._twitter_page'
        db.add_column('debra_userprofile', '_twitter_page', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile.num_buy_link_clicks'
        db.add_column('debra_userprofile', 'num_buy_link_clicks', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile.num_shelves_created'
        db.add_column('debra_userprofile', 'num_shelves_created', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile._location'
        db.add_column('debra_userprofile', '_location', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._facebook_page'
        db.add_column('debra_userprofile', '_facebook_page', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._is_a_shelfalista'
        db.add_column('debra_userprofile', '_is_a_shelfalista', self.gf('django.db.models.fields.BooleanField')(default=False), keep_default=False)

        # Adding field 'UserProfile.num_invites_sent'
        db.add_column('debra_userprofile', 'num_invites_sent', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile.num_days_since_joined'
        db.add_column('debra_userprofile', 'num_days_since_joined', self.gf('django.db.models.fields.IntegerField')(default=0), keep_default=False)

        # Adding field 'UserProfile._profile_img_url'
        db.add_column('debra_userprofile', '_profile_img_url', self.gf('django.db.models.fields.CharField')(default=None, max_length=1000, null=True, blank=True), keep_default=False)

        # Adding field 'UserProfile._web_page'
        db.add_column('debra_userprofile', '_web_page', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True), keep_default=False)


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
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2013, 12, 18, 3, 12, 48, 45151)'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2013, 12, 18, 3, 12, 48, 45054)'}),
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
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '2000'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'num_fb_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_pins': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_twitter_mentions': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'prod_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '2000', 'db_index': 'True'}),
            'promo_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'})
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
            'create_time': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 12, 18, 3, 12, 47, 586068)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'promo_info': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'promo_raw': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.PromoRawText']", 'null': 'True', 'blank': 'True'}),
            'promo_updated_text': ('django.db.models.fields.TextField', [], {}),
            'updated_time': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 12, 18, 3, 12, 47, 586092)'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.promoinfo': {
            'Meta': {'object_name': 'Promoinfo'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'd': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2013, 12, 18, 3, 12, 47, 584690)'}),
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
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'num_items': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'shelf_img': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'user_created_cat': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'shelves'", 'null': 'True', 'blank': 'True', 'to': "orm['auth.User']"})
        },
        'debra.styletag': {
            'Meta': {'object_name': 'StyleTag'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'debra.userfollowmap': {
            'Meta': {'unique_together': "(('user', 'following'),)", 'object_name': 'UserFollowMap'},
            'following': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'follows'", 'to': "orm['debra.UserProfile']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'users'", 'to': "orm['debra.UserProfile']"})
        },
        'debra.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
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
            'num_followers': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_following': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_items_in_shelves': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_shelves': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
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
            'current_product_price': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.ProductPrice']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_feed_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_original': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_panel_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_shelf_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_thumbnail_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'imported_from_blog': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'wishlist_items'", 'null': 'True', 'blank': 'True', 'to': "orm['auth.User']"})
        },
        'debra.wishlistitemshelfmap': {
            'Meta': {'object_name': 'WishlistItemShelfMap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'shelf': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Shelf']", 'null': 'True', 'blank': 'True'}),
            'wishlist_item': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.WishlistItem']", 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['debra']
