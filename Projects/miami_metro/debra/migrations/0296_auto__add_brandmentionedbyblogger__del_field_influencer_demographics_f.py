# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'BrandMentionedByBlogger'
        db.create_table('debra_brandmentionedbyblogger', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('platform', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.Platform'], null=True, blank=True)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['debra.Brands'], null=True, blank=True)),
            ('count_sponsored', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True)),
            ('count_notsponsored', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True)),
            ('snapshot_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now, db_index=True)),
        ))
        db.send_create_signal('debra', ['BrandMentionedByBlogger'])

        # Deleting field 'Influencer.demographics_fbpic'
        db.delete_column('debra_influencer', 'demographics_fbpic')

        # Deleting field 'Influencer.demographics_first_name'
        db.delete_column('debra_influencer', 'demographics_first_name')

        # Deleting field 'Influencer.brands_liked'
        db.delete_column('debra_influencer', 'brands_liked')

        # Deleting field 'Influencer.demographics_last_name'
        db.delete_column('debra_influencer', 'demographics_last_name')

        # Deleting field 'Influencer.ranking_monetization_score'
        db.delete_column('debra_influencer', 'ranking_monetization_score')

        # Deleting field 'Influencer.ranking_overallengagement_mediascore'
        db.delete_column('debra_influencer', 'ranking_overallengagement_mediascore')

        # Deleting field 'Influencer.followers_overalldemographics_percentbloggers'
        db.delete_column('debra_influencer', 'followers_overalldemographics_percentbloggers')

        # Deleting field 'Influencer.followers_overalldemographics_averageage'
        db.delete_column('debra_influencer', 'followers_overalldemographics_averageage')

        # Deleting field 'Influencer.ranking_posting_rate_score'
        db.delete_column('debra_influencer', 'ranking_posting_rate_score')

        # Deleting field 'Influencer.ranking_overallengagement_recurringscore'
        db.delete_column('debra_influencer', 'ranking_overallengagement_recurringscore')

        # Deleting field 'Influencer.demographics_fbid'
        db.delete_column('debra_influencer', 'demographics_fbid')

        # Deleting field 'Influencer.ranking_overallseo_score'
        db.delete_column('debra_influencer', 'ranking_overallseo_score')

        # Deleting field 'Influencer.ranking_blogger_quality_score'
        db.delete_column('debra_influencer', 'ranking_blogger_quality_score')

        # Deleting field 'Influencer.followers_overalldemographics_topcountry'
        db.delete_column('debra_influencer', 'followers_overalldemographics_topcountry')

        # Deleting field 'Influencer.ranking_blogger_follower_score'
        db.delete_column('debra_influencer', 'ranking_blogger_follower_score')

        # Deleting field 'Influencer.top_followers'
        db.delete_column('debra_influencer', 'top_followers')

        # Deleting field 'Influencer.followers_overalldemographics_percentmale'
        db.delete_column('debra_influencer', 'followers_overalldemographics_percentmale')

        # Adding field 'Influencer.score_engagement_overall'
        db.add_column('debra_influencer', 'score_engagement_overall', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.score_popularity_overall'
        db.add_column('debra_influencer', 'score_popularity_overall', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Deleting field 'Platform.monetization_revenueestimate'
        db.delete_column('debra_platform', 'monetization_revenueestimate')

        # Deleting field 'Platform.monetization_percentsponsored'
        db.delete_column('debra_platform', 'monetization_percentsponsored')

        # Deleting field 'Platform.brandfit_matrix'
        db.delete_column('debra_platform', 'brandfit_matrix')

        # Deleting field 'Platform.bloggers_linked'
        db.delete_column('debra_platform', 'bloggers_linked')

        # Deleting field 'Platform.reference_score'
        db.delete_column('debra_platform', 'reference_score')

        # Deleting field 'Platform.engagement_platform_recurringscore'
        db.delete_column('debra_platform', 'engagement_platform_recurringscore')

        # Deleting field 'Platform.has_frame'
        db.delete_column('debra_platform', 'has_frame')

        # Deleting field 'Platform.social_handle'
        db.delete_column('debra_platform', 'social_handle')

        # Deleting field 'Platform.growth_category'
        db.delete_column('debra_platform', 'growth_category')

        # Deleting field 'Platform.monetization_numads'
        db.delete_column('debra_platform', 'monetization_numads')

        # Adding field 'Platform.locale'
        db.add_column('debra_platform', 'locale', self.gf('django.db.models.fields.CharField')(default=None, max_length=32, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.numsponsoredposts'
        db.add_column('debra_platform', 'numsponsoredposts', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numlikes_overall'
        db.add_column('debra_platform', 'avg_numlikes_overall', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numcomments_overall'
        db.add_column('debra_platform', 'avg_numcomments_overall', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numshares_overall'
        db.add_column('debra_platform', 'avg_numshares_overall', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numlikes_sponsored'
        db.add_column('debra_platform', 'avg_numlikes_sponsored', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numcomments_sponsored'
        db.add_column('debra_platform', 'avg_numcomments_sponsored', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numshares_sponsored'
        db.add_column('debra_platform', 'avg_numshares_sponsored', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numlikes_non_sponsored'
        db.add_column('debra_platform', 'avg_numlikes_non_sponsored', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numcomments_non_sponsored'
        db.add_column('debra_platform', 'avg_numcomments_non_sponsored', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.avg_numshares_non_sponsored'
        db.add_column('debra_platform', 'avg_numshares_non_sponsored', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.score_engagement_overall'
        db.add_column('debra_platform', 'score_engagement_overall', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.score_popularity_overall'
        db.add_column('debra_platform', 'score_popularity_overall', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.score_engagement_sponsored'
        db.add_column('debra_platform', 'score_engagement_sponsored', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.score_engagement_non_sponsored'
        db.add_column('debra_platform', 'score_engagement_non_sponsored', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Deleting field 'Posts.prize_money'
        db.delete_column('debra_posts', 'prize_money')

        # Deleting field 'Posts.num_prizes'
        db.delete_column('debra_posts', 'num_prizes')

        # Deleting field 'Posts.content_numvideos'
        db.delete_column('debra_posts', 'content_numvideos')

        # Deleting field 'Posts.maxmediasize'
        db.delete_column('debra_posts', 'maxmediasize')

        # Deleting field 'Posts.content_numpics'
        db.delete_column('debra_posts', 'content_numpics')

        # Deleting field 'Posts.final_product_urls'
        db.delete_column('debra_posts', 'final_product_urls')


    def backwards(self, orm):
        
        # Deleting model 'BrandMentionedByBlogger'
        db.delete_table('debra_brandmentionedbyblogger')

        # Adding field 'Influencer.demographics_fbpic'
        db.add_column('debra_influencer', 'demographics_fbpic', self.gf('django.db.models.fields.URLField')(default=None, max_length=1000, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.demographics_first_name'
        db.add_column('debra_influencer', 'demographics_first_name', self.gf('django.db.models.fields.CharField')(default=None, max_length=1000, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.brands_liked'
        db.add_column('debra_influencer', 'brands_liked', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.demographics_last_name'
        db.add_column('debra_influencer', 'demographics_last_name', self.gf('django.db.models.fields.CharField')(default=None, max_length=1000, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.ranking_monetization_score'
        db.add_column('debra_influencer', 'ranking_monetization_score', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.ranking_overallengagement_mediascore'
        db.add_column('debra_influencer', 'ranking_overallengagement_mediascore', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.followers_overalldemographics_percentbloggers'
        db.add_column('debra_influencer', 'followers_overalldemographics_percentbloggers', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.followers_overalldemographics_averageage'
        db.add_column('debra_influencer', 'followers_overalldemographics_averageage', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.ranking_posting_rate_score'
        db.add_column('debra_influencer', 'ranking_posting_rate_score', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.ranking_overallengagement_recurringscore'
        db.add_column('debra_influencer', 'ranking_overallengagement_recurringscore', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.demographics_fbid'
        db.add_column('debra_influencer', 'demographics_fbid', self.gf('django.db.models.fields.CharField')(default=None, max_length=100, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.ranking_overallseo_score'
        db.add_column('debra_influencer', 'ranking_overallseo_score', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.ranking_blogger_quality_score'
        db.add_column('debra_influencer', 'ranking_blogger_quality_score', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.followers_overalldemographics_topcountry'
        db.add_column('debra_influencer', 'followers_overalldemographics_topcountry', self.gf('django.db.models.fields.CharField')(default=None, max_length=50, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.ranking_blogger_follower_score'
        db.add_column('debra_influencer', 'ranking_blogger_follower_score', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.top_followers'
        db.add_column('debra_influencer', 'top_followers', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Influencer.followers_overalldemographics_percentmale'
        db.add_column('debra_influencer', 'followers_overalldemographics_percentmale', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Deleting field 'Influencer.score_engagement_overall'
        db.delete_column('debra_influencer', 'score_engagement_overall')

        # Deleting field 'Influencer.score_popularity_overall'
        db.delete_column('debra_influencer', 'score_popularity_overall')

        # Adding field 'Platform.monetization_revenueestimate'
        db.add_column('debra_platform', 'monetization_revenueestimate', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.monetization_percentsponsored'
        db.add_column('debra_platform', 'monetization_percentsponsored', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.brandfit_matrix'
        db.add_column('debra_platform', 'brandfit_matrix', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.bloggers_linked'
        db.add_column('debra_platform', 'bloggers_linked', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.reference_score'
        db.add_column('debra_platform', 'reference_score', self.gf('django.db.models.fields.FloatField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.engagement_platform_recurringscore'
        db.add_column('debra_platform', 'engagement_platform_recurringscore', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.has_frame'
        db.add_column('debra_platform', 'has_frame', self.gf('django.db.models.fields.NullBooleanField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.social_handle'
        db.add_column('debra_platform', 'social_handle', self.gf('django.db.models.fields.CharField')(default=None, max_length=1000, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.growth_category'
        db.add_column('debra_platform', 'growth_category', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Platform.monetization_numads'
        db.add_column('debra_platform', 'monetization_numads', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Deleting field 'Platform.locale'
        db.delete_column('debra_platform', 'locale')

        # Deleting field 'Platform.numsponsoredposts'
        db.delete_column('debra_platform', 'numsponsoredposts')

        # Deleting field 'Platform.avg_numlikes_overall'
        db.delete_column('debra_platform', 'avg_numlikes_overall')

        # Deleting field 'Platform.avg_numcomments_overall'
        db.delete_column('debra_platform', 'avg_numcomments_overall')

        # Deleting field 'Platform.avg_numshares_overall'
        db.delete_column('debra_platform', 'avg_numshares_overall')

        # Deleting field 'Platform.avg_numlikes_sponsored'
        db.delete_column('debra_platform', 'avg_numlikes_sponsored')

        # Deleting field 'Platform.avg_numcomments_sponsored'
        db.delete_column('debra_platform', 'avg_numcomments_sponsored')

        # Deleting field 'Platform.avg_numshares_sponsored'
        db.delete_column('debra_platform', 'avg_numshares_sponsored')

        # Deleting field 'Platform.avg_numlikes_non_sponsored'
        db.delete_column('debra_platform', 'avg_numlikes_non_sponsored')

        # Deleting field 'Platform.avg_numcomments_non_sponsored'
        db.delete_column('debra_platform', 'avg_numcomments_non_sponsored')

        # Deleting field 'Platform.avg_numshares_non_sponsored'
        db.delete_column('debra_platform', 'avg_numshares_non_sponsored')

        # Deleting field 'Platform.score_engagement_overall'
        db.delete_column('debra_platform', 'score_engagement_overall')

        # Deleting field 'Platform.score_popularity_overall'
        db.delete_column('debra_platform', 'score_popularity_overall')

        # Deleting field 'Platform.score_engagement_sponsored'
        db.delete_column('debra_platform', 'score_engagement_sponsored')

        # Deleting field 'Platform.score_engagement_non_sponsored'
        db.delete_column('debra_platform', 'score_engagement_non_sponsored')

        # Adding field 'Posts.prize_money'
        db.add_column('debra_posts', 'prize_money', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Posts.num_prizes'
        db.add_column('debra_posts', 'num_prizes', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Posts.content_numvideos'
        db.add_column('debra_posts', 'content_numvideos', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Posts.maxmediasize'
        db.add_column('debra_posts', 'maxmediasize', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Posts.content_numpics'
        db.add_column('debra_posts', 'content_numpics', self.gf('django.db.models.fields.IntegerField')(default=None, null=True, blank=True), keep_default=False)

        # Adding field 'Posts.final_product_urls'
        db.add_column('debra_posts', 'final_product_urls', self.gf('django.db.models.fields.TextField')(default=None, null=True, blank=True), keep_default=False)


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
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2014, 2, 7, 2, 18, 51, 16067)'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2014, 2, 7, 2, 18, 51, 15971)'}),
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
        'debra.brandmentionedbyblogger': {
            'Meta': {'object_name': 'BrandMentionedByBlogger'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Brands']", 'null': 'True', 'blank': 'True'}),
            'count_notsponsored': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'count_sponsored': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'platform': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Platform']", 'null': 'True', 'blank': 'True'}),
            'snapshot_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'db_index': 'True'})
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
        'debra.color': {
            'Meta': {'object_name': 'Color'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '500', 'null': 'True'}),
            'product_img': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '500', 'null': 'True'}),
            'swatch_img': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '500', 'null': 'True'})
        },
        'debra.colorsizemodel': {
            'Meta': {'object_name': 'ColorSizeModel'},
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '500'}),
            'color_data': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Color']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'product': ('django.db.models.fields.related.ForeignKey', [], {'default': "'0'", 'to': "orm['debra.ProductModel']"}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '500'}),
            'size_inseam': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '500', 'null': 'True'}),
            'size_sizetype': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '500', 'null': 'True'}),
            'size_standard': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '500', 'null': 'True'})
        },
        'debra.embeddable': {
            'Meta': {'object_name': 'Embeddable'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.UserProfile']"}),
            'html': ('django.db.models.fields.TextField', [], {'max_length': '5000'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lottery': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Lottery']", 'null': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'default': "'collage_widget'", 'max_length': '50'})
        },
        'debra.fetcherapidataassignment': {
            'Meta': {'unique_together': "(('spec', 'server_ip'),)", 'object_name': 'FetcherApiDataAssignment'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'server_ip': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'spec': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.FetcherApiDataSpec']"}),
            'value_m': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.FetcherApiDataValue']"})
        },
        'debra.fetcherapidataspec': {
            'Meta': {'object_name': 'FetcherApiDataSpec'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'platform_name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'policy_name': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'debra.fetcherapidatavalue': {
            'Meta': {'object_name': 'FetcherApiDataValue'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_usage': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'spec': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.FetcherApiDataSpec']"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '10000'}),
            'value_index': ('django.db.models.fields.IntegerField', [], {})
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
            'demographics_bloggerage': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'demographics_gender': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'demographics_location': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'default': 'None', 'max_length': '75', 'null': 'True', 'blank': 'True'}),
            'fb_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'insta_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "'Blogger name'", 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'pin_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'relevant_to_fashion': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'score_engagement_overall': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'score_popularity_overall': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'shelf_user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'tw_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        'debra.linkfromplatform': {
            'Meta': {'object_name': 'LinkFromPlatform'},
            'dest_platform': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'destlink_set'", 'null': 'True', 'to': "orm['debra.Platform']"}),
            'dest_url': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_platform': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'sourcelink_set'", 'to': "orm['debra.Platform']"})
        },
        'debra.lottery': {
            'Meta': {'object_name': 'Lottery'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.UserProfile']"}),
            'end_date': ('django.db.models.fields.DateField', [], {}),
            'end_datetime': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'in_test_mode': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'show_winners': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'start_date': ('django.db.models.fields.DateField', [], {}),
            'start_datetime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'terms': ('django.db.models.fields.TextField', [], {'max_length': '5000', 'null': 'True', 'blank': 'True'}),
            'theme': ('django.db.models.fields.CharField', [], {'default': "'theme_pink'", 'max_length': '20'}),
            'timezone': ('django.db.models.fields.CharField', [], {'default': "'-5'", 'max_length': '100'})
        },
        'debra.lotteryentry': {
            'Meta': {'object_name': 'LotteryEntry'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_winner': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lottery': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Lottery']"}),
            'touch_datetime': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.UserProfile']"})
        },
        'debra.lotteryentrycompletedtask': {
            'Meta': {'object_name': 'LotteryEntryCompletedTask'},
            'custom_task_response': ('django.db.models.fields.CharField', [], {'max_length': '300', 'null': 'True', 'blank': 'True'}),
            'entry': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.LotteryEntry']"}),
            'entry_validation': ('django.db.models.fields.CharField', [], {'max_length': '300', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_winner': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
            'mandatory': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'point_value': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'requirement_text': ('django.db.models.fields.CharField', [], {'max_length': '300', 'null': 'True', 'blank': 'True'}),
            'requirement_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'step_id': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
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
        'debra.operationstatus': {
            'Meta': {'unique_together': "(('object_type', 'object_spec', 'op', 'op_status', 'op_msg', 'op_date', 'op_hour'),)", 'object_name': 'OperationStatus'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_spec': ('django.db.models.fields.CharField', [], {'max_length': '10000', 'db_index': 'True'}),
            'object_type': ('django.db.models.fields.CharField', [], {'max_length': '1000'}),
            'op': ('django.db.models.fields.CharField', [], {'max_length': '1000'}),
            'op_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'op_date': ('django.db.models.fields.DateField', [], {}),
            'op_hour': ('django.db.models.fields.IntegerField', [], {}),
            'op_msg': ('django.db.models.fields.CharField', [], {'max_length': '50000', 'null': 'True'}),
            'op_status': ('django.db.models.fields.CharField', [], {'max_length': '10000', 'null': 'True'})
        },
        'debra.platform': {
            'Meta': {'object_name': 'Platform'},
            'about': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'api_calls': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'avg_numcomments_non_sponsored': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'avg_numcomments_overall': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'avg_numcomments_sponsored': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'avg_numlikes_non_sponsored': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'avg_numlikes_overall': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'avg_numlikes_sponsored': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'avg_numshares_non_sponsored': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'avg_numshares_overall': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'avg_numshares_sponsored': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'blogname': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'cover_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'create_date': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'indepth_processed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'influencer': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Influencer']", 'null': 'True', 'blank': 'True'}),
            'last_api_call': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'locale': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'num_followers': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'num_following': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'numposts': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'numsponsoredposts': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'platform_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'posting_rate': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'profile_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'score_engagement_non_sponsored': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'score_engagement_overall': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'score_engagement_sponsored': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'score_popularity_overall': ('django.db.models.fields.FloatField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'total_numcomments': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'total_numlikes': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'total_numshares': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'db_index': 'True', 'blank': 'True'}),
            'url_not_found': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'})
        },
        'debra.platformapicalls': {
            'Meta': {'unique_together': "(('platform_name', 'calls_date', 'calls_hour', 'status_code', 'status_msg'),)", 'object_name': 'PlatformApiCalls'},
            'calls_date': ('django.db.models.fields.DateField', [], {}),
            'calls_hour': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'num_calls': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'platform_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'status_code': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'status_msg': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'})
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
            'added_datetime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'db_index': 'True'}),
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
            'admin_categorized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'api_id': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'brand_tags': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'content': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'create_date': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numcomments': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numfbshares': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numlikes': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numrepins': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numretweets': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'engagement_media_numshares': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'influencer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Influencer']"}),
            'inserted_datetime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'is_sponsored': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'location': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'platform': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Platform']", 'null': 'True', 'blank': 'True'}),
            'problems': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'products_import_completed': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'show_on_feed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'title': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'})
        },
        'debra.postshelfmap': {
            'Meta': {'object_name': 'PostShelfMap'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'post': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Posts']"}),
            'shelf': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Shelf']"}),
            'user_prof': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.UserProfile']"})
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
            'problems': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'prod_url': ('django.db.models.fields.URLField', [], {'default': "'Nil'", 'max_length': '2000', 'db_index': 'True'}),
            'promo_text': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '200'}),
            'saleprice': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'})
        },
        'debra.productmodelshelfmap': {
            'Meta': {'object_name': 'ProductModelShelfMap'},
            'added_datetime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'db_index': 'True'}),
            'admin_categorized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'affiliate_prod_link': ('django.db.models.fields.URLField', [], {'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'affiliate_source_wishlist_id': ('django.db.models.fields.IntegerField', [], {'default': "'-1'", 'max_length': '100'}),
            'avail_sizes': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'bought': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'calculated_price': ('django.db.models.fields.FloatField', [], {'default': "'-11.0'", 'max_length': '10'}),
            'color': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'current_product_price': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.ProductPrice']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_feed_compressed': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_feed_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_original': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_panel_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_shelf_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'img_url_thumbnail_view': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'imported_from_blog': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'item_out_of_stock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'notify_lower_bound': ('django.db.models.fields.FloatField', [], {'default': "'-1'", 'max_length': '10'}),
            'post': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Posts']", 'null': 'True', 'blank': 'True'}),
            'product_model': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.ProductModel']"}),
            'promo_applied': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'savings': ('django.db.models.fields.FloatField', [], {'default': "'0'", 'max_length': '10'}),
            'shelf': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Shelf']", 'null': 'True', 'blank': 'True'}),
            'shipping_cost': ('django.db.models.fields.FloatField', [], {'default': "'-1'", 'max_length': '10'}),
            'show_on_feed': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'size': ('django.db.models.fields.CharField', [], {'default': "'Nil'", 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'snooze': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'time_notified_last': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'time_price_calculated_last': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user_prof': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.UserProfile']", 'null': 'True', 'blank': 'True'})
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
            'create_time': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2014, 2, 7, 2, 18, 50, 559248)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'promo_info': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Promoinfo']", 'null': 'True', 'blank': 'True'}),
            'promo_raw': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.PromoRawText']", 'null': 'True', 'blank': 'True'}),
            'promo_updated_text': ('django.db.models.fields.TextField', [], {}),
            'updated_time': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2014, 2, 7, 2, 18, 50, 559272)'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'debra.promoinfo': {
            'Meta': {'object_name': 'Promoinfo'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'd': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime(2014, 2, 7, 2, 18, 50, 558013)'}),
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
        'debra.shelf': {
            'Meta': {'object_name': 'Shelf'},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Brands']", 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imported_from_blog': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'num_items': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'num_likes': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'shelf_img': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'user_created_cat': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'user_id': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'shelves'", 'null': 'True', 'blank': 'True', 'to': "orm['auth.User']"})
        },
        'debra.sponsorshipinfo': {
            'Meta': {'object_name': 'SponsorshipInfo'},
            'added_datetime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'db_index': 'True'}),
            'content': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '10000', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_running': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'max_entry_value': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'post': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['debra.Posts']"}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True'}),
            'total_entries': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'widget_type': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True'})
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
            'admin_action': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'admin_categorized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'admin_classification_tags': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'admin_comments': ('django.db.models.fields.TextField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'age': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'blog_name': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'blog_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'blog_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'bloglovin_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'brand': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['debra.Brands']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'can_set_affiliate_links': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'collage_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'connector_tag': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
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
            'friendly_tag': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
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
            'influencer': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['debra.Influencer']", 'null': 'True', 'blank': 'True'}),
            'instagram_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'is_female': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_trendsetter': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
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
            'popularity_rank': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'price_alerts_notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'privilege_level': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'profile_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'quality_tag': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'raw_data': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'show_autocategorized': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'social_interaction_notification': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'store_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'style_bio': ('django.db.models.fields.TextField', [], {'default': 'None', 'max_length': '2000', 'null': 'True', 'blank': 'True'}),
            'style_tags': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '1000', 'null': 'True'}),
            'temp_img_url': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '1000', 'null': 'True', 'blank': 'True'}),
            'twitter_page': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'unclaimed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
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
