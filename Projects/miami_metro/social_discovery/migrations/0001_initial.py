# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'TwitterProfile'
        db.create_table('social_discovery_twitterprofile', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('screen_name', self.gf('django.db.models.fields.TextField')(db_index=True)),
            ('profile_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('friends_updated', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('social_discovery', ['TwitterProfile'])

        # Adding model 'TwitterFollow'
        db.create_table('social_discovery_twitterfollow', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('follower', self.gf('django.db.models.fields.related.ForeignKey')(related_name=u'folowers', to=orm['social_discovery.TwitterProfile'])),
            ('followed', self.gf('django.db.models.fields.related.ForeignKey')(related_name=u'followed', to=orm['social_discovery.TwitterProfile'])),
        ))
        db.send_create_signal('social_discovery', ['TwitterFollow'])


    def backwards(self, orm):
        
        # Deleting model 'TwitterProfile'
        db.delete_table('social_discovery_twitterprofile')

        # Deleting model 'TwitterFollow'
        db.delete_table('social_discovery_twitterfollow')


    models = {
        'social_discovery.twitterfollow': {
            'Meta': {'object_name': 'TwitterFollow'},
            'followed': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'followed'", 'to': "orm['social_discovery.TwitterProfile']"}),
            'follower': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'folowers'", 'to': "orm['social_discovery.TwitterProfile']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'social_discovery.twitterprofile': {
            'Meta': {'object_name': 'TwitterProfile'},
            'friends': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "u'friends+'", 'symmetrical': 'False', 'through': "orm['social_discovery.TwitterFollow']", 'to': "orm['social_discovery.TwitterProfile']"}),
            'friends_updated': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'profile_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'screen_name': ('django.db.models.fields.TextField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['social_discovery']
