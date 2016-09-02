# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'TwitterProfile.friends_count'
        db.add_column('social_discovery_twitterprofile', 'friends_count', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True), keep_default=False)

        # Adding field 'TwitterProfile.followers_count'
        db.add_column('social_discovery_twitterprofile', 'followers_count', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'TwitterProfile.friends_count'
        db.delete_column('social_discovery_twitterprofile', 'friends_count')

        # Deleting field 'TwitterProfile.followers_count'
        db.delete_column('social_discovery_twitterprofile', 'followers_count')


    models = {
        'social_discovery.twitterfollow': {
            'Meta': {'object_name': 'TwitterFollow'},
            'followed': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'followed'", 'to': "orm['social_discovery.TwitterProfile']"}),
            'follower': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'folowers'", 'to': "orm['social_discovery.TwitterProfile']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'social_discovery.twitterprofile': {
            'Meta': {'object_name': 'TwitterProfile'},
            'followers_count': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'friends': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "u'friends+'", 'symmetrical': 'False', 'through': "orm['social_discovery.TwitterFollow']", 'to': "orm['social_discovery.TwitterProfile']"}),
            'friends_count': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'friends_updated': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'post_count': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'profile_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'screen_name': ('django.db.models.fields.TextField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['social_discovery']
