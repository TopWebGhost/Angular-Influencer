import pdb

from django.conf import settings
from django.contrib import admin
from django.conf.urls.defaults import patterns, include, url
from django.db.models.loading import cache as model_cache
from django.views.generic import TemplateView

from registration.views import activate
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework import routers


from debra import api
from debra.admin import modify_admin_site
from debra.suspect_admin import suspect_admin_site
from debra.constants import SCROLLABLE_COLLAGE, GRID_COLLAGE
from debra.models import Embeddable
from debra.sitemaps import (
    UserSitemap, BrandSitemap, ProductSitemap, StaticViewSitemap)

if not model_cache.loaded:
    model_cache.get_models()


router = routers.SimpleRouter(trailing_slash=False)
router.register(r'campaigns', api.CampaignViewSet)
router.register(r'configurations', api.SiteConfigurationViewSet)
router.register(r'contracts', api.ContractViewSet)
router.register(r'messages', api.MailProxyMessageViewSet)
router.register(r'brands', api.BrandViewSet)
router.register(r'brand_taxonomies', api.BrandTaxonomyViewSet)
router.register(r'influencer_brand_mappings', api.InfluencerBrandMappingViewSet)
router.register(r'tags', api.TagViewSet, base_name='Tag')
router.register(r'campaign_reports', api.CampaignReportViewSet)
router.register(r'influencers', api.InfluencerViewSet)


urlpatterns = patterns('',
    (r'^api/v1/', include(router.urls)),
)


# Uncomment the next two lines to enable the admin:
admin.autodiscover()

handler404 = 'debra.account_views.my_custom_404_view'
handler403 = 'debra.errors_views.error403'

# TODO: REFACTOR THIS FOR PRODUCTION!!! Do not set url for production.
#MISC URLS
urlpatterns += patterns('',
    # Media-related routing
    (r'^mymedia/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT})
)
urlpatterns += patterns('',
    url(r'html2canvas-proxy/', include('django_html2canvas.urls')),
    (r'^blank-page/$', 'debra.helpers.blank_page')
)


#ADMIN URLS
urlpatterns += patterns('',
    url(r'^admin/upgrade/', include(modify_admin_site.urls)),
    url(r'^admin/suspect/', include(suspect_admin_site.urls)),
    (r'^admin/', include(admin.site.urls)),
)

api_urlpatterns = patterns('',
    url(r'^api/posts/(?P<pk>\d+)/$', api.PostDetails.as_view(), name='post-details'),
    url(r'^api/posts/$', api.PostSearch.as_view(), name='post-search'),
)

api_urlpatterns = format_suffix_patterns(api_urlpatterns)

urlpatterns += api_urlpatterns

blank_pages = [
    (r'^blank{}/$'.format(i), TemplateView.as_view(
        template_name='pages/blank{}.html'.format(i))) for i in xrange(1, 11)]

urlpatterns += patterns('', *blank_pages)


#MAIL PROXY
urlpatterns += patterns('debra.mail_proxy',
    # Make sure you update the  SSLIFY_DISABLE_FOR_REQUEST setting to disable SSL
    # if updating the hook URL
    ('^reply/$', 'mandrill_webhook'),
)


#SHELF NETWORK URLS
urlpatterns += patterns('debra.shelfnetwork_views',
    ('^shelfnetwork/bloggers/$', 'shelfnetwork_bloggers'),
)

#DEBRA ACCOUNT URLS
urlpatterns += patterns('debra.account_views',
    ('favicon.ico', 'favicon'),
    ('robots.txt', 'robots'),
    (r'^the-blog/(?P<post_url>.+)$', 'blog_redirect'),

    ('^$', 'brand_home'),
    (r'^login-open-popup/$', 'brand_home', {'login_popup_auto_open': True, 'blog_redirection': False}),
    (r'^brand-signup-open-popup/$', 'brand_home', {'brand_signup_popup_auto_open': True, 'blog_redirection': False}),
    (r'^blogger-signup-open-popup/$', 'brand_home', {'blogger_signup_popup_auto_open': True, 'blog_redirection': False}),
    (r'^influenity-signup-open-popup/$', 'brand_home', {
        'blogger_signup_popup_auto_open': True,
        'influenity_signup_popup_auto_open': True,
        'blog_redirection': False
    }),

    (r'^slack_test/$', 'slack_test'),

    (r'^brands/$', 'brand_home'),
    (r'^agency/$', 'agency'),
    (r'^selfserve/$', 'selfserve'),
    (r'^brands/mismatched/$', 'brand_email_mismatch'),
    (r'^brands/verify/$', 'trigger_brand_membership_verify'),
    (r'^bloggers/$', 'home'),
    (r'^pricing/foggy/1211/$', 'pricing'),
    (r'^terms/$', 'terms'),
    (r'^privacy/$', 'privacy'),
    (r'^login/$', 'shelf_login'),
    (r'^bloggers-list/$', 'export_list'),
    (r'^bloggers-list-custom/hMCx3WC4zhQiY5KiH7ebV0lWcpzwH3$', 'export_list_custom'),
    (r'^bloggers-list/ongoing$', 'export_ongoing'),
    (r'^shopper-signup/$', 'shopper_signup'),
    (r'^blogger-signup/$', 'blogger_signup'),
    (r'^brand-signup/$', 'brand_signup'),
    (r'^contact-us/$', 'contact_us'),
    (r'^add-new-user/$', 'add_new_user'),
    (r'^logout/$', 'our_logout'),
    (r'^brand/next-steps/$', 'brand_next_steps'),
    (r'^blogger/next-steps/$', 'blogger_next_steps'),
    (r'^upgrade-request/$', 'upgrade_request'),
    (r'^account/getting_started/$', 'getting_started'),
    (r'^account/unregister/$', 'unregister'),
    (r'^account/change-email/$', 'change_email'),
    (r'^account/change-password/$', 'change_password'),
    (r'^account/resend_activation_key/$', 'resend_activation_key'),

    (r'^account/registered/brand$', 'registration_complete_brand'),
    (r'^account/registered/blogger$', 'registration_complete_blogger'),
    (r'^account/verified/brand$', 'email_verified_brand'),
    (r'^account/plan_change/brand/(?P<plan_name>.+)$', 'plan_changed_brand'),

    (r'^buy/$', 'auto_buy'),
    (r'^demo-request/$', 'demo_requested'),

    #tmp views
    (r'^blogger/added/$', 'blogger_blog_ok'),
    (r'^blogger/verify/$', 'blogger_blog_not_ok'),
    (r'^blogger/verify_badge/$', 'trigger_badge_verify'),
    (r'^shopper/$', 'shopper_next_steps'),
    (r'^internal/$', 'internal_blog_visitor'),
)

urlpatterns += patterns('',
    url(r'^accounts/activate/(?P<activation_key>\w+)/$', activate, {'backend': 'debra.custom_backend.ShelfBackend'}, name='registration_activate'),
    (r'accounts/', include('registration.urls')),
    url(r'accounts/password-reset', 'debra.account_views.reset_password'),
)

#DEBRA SHELF URLS
urlpatterns += patterns('debra.shelf_views',
    (r'^you/(?P<user>\d+)/likes/$', 'liked_items'), #testing removal
    (r'^you/(?P<user>\d+)/followers/$', 'followers'), #testing removal
    (r'^you/(?P<user>\d+)/following/$', 'following'), #testing removal
    (r'^you/(?P<user>\d+)/toggle-follow/(?P<target>\d+)/$', 'toggle_follow'),
    (r'^you/(?P<user>\d+)/about/$', 'about_me'),
    (r'^you/(?P<user>\d+)/about/edit/$', 'edit_profile'),
    (r'^you/(?P<user>\d+)/my-shelves/$', 'my_shelves'),
    (r'^you/(?P<user>\d+)/shelf/$', 'shelf_home'),
    (r'^you/(?P<user>\d+)/shelf/create/$', 'create_shelf'),
    (r'^you/(?P<user>\d+)/shelf/create-from-links/$', 'create_shelf_from_links'),
    (r'^you/(?P<user>\d+)/shelf/(?P<shelf>\d+)/modify/$', 'modify_shelf'),
    (r'^you/(?P<user>\d+)/shelf/(?P<filter>.*?)$', 'shelf_home'),
)

#DEBRA WIDGETS URLS
urlpatterns += patterns('debra.widget_views',
    url(r'^widgets/(?P<user>\d+)/home/$', 'widgets_home'),
    url(r'^widgets/(?P<user>\d+)/collage/scrollable/$', 'collage', {'collage_type': SCROLLABLE_COLLAGE}, name="scrollable_collage"),
    url(r'^widgets/(?P<user>\d+)/collage/grid/$', 'collage', {'collage_type': GRID_COLLAGE}, name="grid_collage"),
    url(r'^widgets/(?P<user>\d+)/lottery/new/$', 'new_lottery'),
    url(r'^widgets/(?P<user>\d+)/lottery/view-all/$', 'view_lotterys'),
    url(r'^widgets/(?P<user>\d+)/lottery/create/$', 'create_lottery'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/edit/$', 'edit_lottery'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/preview/$', 'preview_lottery'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/duplicate/$', 'duplicate_lottery'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/analytics/$', 'lottery_analytics'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/winner/$', 'pick_winner'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/winner/(?P<winner>\d+)/delete/$', 'delete_winner'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/show-winners/$', 'show_winners'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/clear-test-entries/$', 'clear_test_entries'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/add-prize/$', 'create_lottery_prize'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/add-task/$', 'create_lottery_task'),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/delete-prize/(?P<item>\d+)/$', 'delete_lottery_modifier', {'modifier': 'prize'}, name="delete_lottery_prize"),
    url(r'^widgets/(?P<user>\d+)/lottery/(?P<lottery>\d+)/delete-task/(?P<item>\d+)/$', 'delete_lottery_modifier', name="delete_lottery_task"),
    #embeddables
    url(r'^widgets/(?P<user>\d+)/embeddable/create-collage/$', 'create_embeddable', name="create_embeddable_collage"),
    url(r'^widgets/(?P<user>\d+)/embeddable/create-lottery/$', 'create_embeddable', {'type': Embeddable.LOTTERY_WIDGET}, name="create_embeddable_lottery"),
    url(r'^widgets/(?P<user>\d+)/embeddable/(?P<embeddable>\d+)/enter-lottery/$', 'enter_lottery_task'),
    url(r'^widgets/(?P<creator>\d+)/render-embeddable/(?P<embeddable>\d+)/$', 'render_embeddable')
    #change the previous to:
    #widgets/<id>/embeddable/<id>/render/
)

#DEBRA BRAND URLS
urlpatterns += patterns('debra.brand_views',
    (r'^brand/(?P<brand_id>\d+)/login/$', 'login_as_brand'),
    (r'^brand/(?P<user>\d+)/home/$', 'brand_home'),
    (r'^brand/(?P<user>\d+)/followers/$', 'followers'),
    (r'^brand/(?P<user>\d+)/about/$', 'about_me'),
    (r'^brand/(?P<user>\d+)/about/edit/$', 'edit_profile'),
)

#DEBRA ITEM URLS
urlpatterns += patterns('debra.item_views',
    url(r'^item/(?P<item>\d+)/seo-product-info/$', 'item_info', {'seo_version': True}),
    url(r'^(?P<user>\d+)/item/(?P<item>\d+)/info/$', 'item_info'),
    url(r'^(?P<user>\d+)/item/(?P<item>\d+)/add-to-shelves/$', 'add_item_to_shelves'),
    url(r'^(?P<user>\d+)/item/(?P<item>\d+)/make-hidden/$', 'hide_from_feed'),
    url(r'^(?P<user>\d+)/item/(?P<item>\d+)/add-affiliate-link/$', 'add_affiliate_link'),
    url(r'^(?P<user>\d+)/item/(?P<item>\d+)/send-analytics/$', 'ga_tracking'),
    url(r'^(?P<user>\d+)/item/(?P<item>\d+)/delete/$', 'remove_item_from_shelf', name="remove_from_shelf"),
    url(r'^(?P<user>\d+)/item/(?P<item>\d+)/delete-all/$', 'remove_item_from_shelf', {'all_shelves': True}, name="remove_from_all_shelves"),
)
#refactor these to have structure item/:item_id/user/:user_id

#DEBRA EXPLORE URLS
urlpatterns += patterns('debra.explore_views',
    (r'^explore/inspiration/json/$', 'inspiration_json'),
    (r'^explore/inspiration/(?P<filter>.*?)$', 'inspiration', {'admin_view': False}),
    (r'^explore/inspiration/$', 'inspiration', {'admin_view': False}),
    (r'^explore/trendsetters/$', 'trendsetters', {'admin_view': False}),
    (r'^explore/brands/$', 'trending_brands', {'admin_view': False}),
    (r'^explore/giveaways/$', 'giveaways'),
)

#DEBRA QUERY URLS (check profperties of specific model object)
urlpatterns += patterns('debra.query_views',
    (r'^query/user/autocomplete/$', 'user_autocomplete'),
    (r'^query/blogger/autocomplete/$', 'blogger_autocomplete'),
    (r'^query/task/$', 'check_task_status'),
)

#DEBRA SEARCH URLS
urlpatterns += patterns('debra.search_views',
    (r'^search/bloggers/$', 'blogger_search'),
    (r'^search/posts/$', 'posts_search'),

    # (r'^search/bloggers/json$', 'blogger_search_json'),
    (r'^search/bloggers/json$', 'blogger_search_json_v3'),

    (r'^search/posts/json$', 'posts_search_json'),

    (r'^search/bloggers/(?P<influencer_id>\d+)/json$', 'blogger_info_json'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/posts$', 'blogger_posts_json'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/items$', 'blogger_items_json'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/stats$', 'blogger_stats_json'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/brand_mentions$', 'blogger_brand_mentions_json'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/monthly_visits$', 'blogger_monthly_visits'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/traffic_shares$', 'blogger_traffic_shares'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/top_country_shares$', 'blogger_top_country_shares'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/post_counts$', 'blogger_post_counts_json'),

    (r'^search/bloggers/(?P<influencer_id>\d+)/json/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_info_json_public'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/posts/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_posts_json_public'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/items/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_items_json_public'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/stats/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_stats_json_public'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/brand_mentions/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_brand_mentions_json_public'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/monthly_visits/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_monthly_visits_public'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/traffic_shares/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_traffic_shares_public'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/top_country_shares/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_top_country_shares_public'),
    (r'^search/bloggers/(?P<influencer_id>\d+)/json/post_counts/(?P<date_created_hash>[a-fA-F\d]{32})/$', 'blogger_post_counts_json_public'),

    (r'^search/brand/json$', 'search_brand_json'),
    (r'^search/autocomplete$', 'autocomplete'),
    (r'^search/autocomplete/with_type$', 'autocomplete_with_type'),
    (r'^search/autocomplete/brand$', 'autocomplete_brand'),
    (r'^search/saved_views/$', 'saved_views_tags'),
    (r'^search/saved_views/tags/$', 'saved_views_tags'),
    (r'^search/saved_views/favorites$', 'saved_views_favorites'),
    (r'^search/saved_views/searches$', 'saved_views_searches'),
    (r'^search/saved_views/posts$', 'saved_views_posts'),
    (r'^search/save_search/$', 'save_search'),
    (r'^search/saved_search/get/(?P<query_id>\d+)/$', 'get_saved_searches'),
    (r'^search/saved_search/get/$', 'get_saved_searches'),
    (r'^search/saved_search/edit/$', 'edit_saved_searches'),
    (r'^search/saved_search/delete/$', 'delete_saved_search'),
    # (r'^search/saved_views/searches/(?P<section>[a-z_]+)/count_only/$', 'saved_search_details', {'count_only': True}),
    (r'^search/saved_views/searches/(?P<section>[a-z_]+)/(?P<query_id>\d+)/$', 'saved_search_details'),
    (r'^search/saved_views/searches/(?P<section>[a-z_]+)/$', 'saved_search_details'),
    (r'^search/saved_views/searches/$', 'saved_search_details'),

    (r'^roi_prediction_reports/(?P<report_id>\d+)/edit$', 'roi_prediction_report_edit'),
    (r'^roi_prediction_reports/create/$', 'roi_prediction_report_create'),
    (r'^roi_prediction_reports/(?P<report_id>\d+)/$', 'roi_prediction_report'),
    (r'^roi_prediction_report_influencer_stats/(?P<report_id>\d+)/$', 'roi_prediction_report_influencer_stats'),
    (r'^roi_prediction_reports/$', 'roi_prediction_reports'),

    (r'^blogger_approval_reports/(?P<report_id>\d+)/$', 'blogger_approval_report'),
    (r'^client_approval_report/(?P<brand_id>\d+)/(?P<report_id>\d+)/(?P<user_id>\d+)/(?P<hash_key>[a-fA-F\d]{32})/$', 'blogger_approval_report_public'),

    (r'^approve_report_update/$', 'approve_report_update'),
    (r'^public_approval_report_submit/$', 'public_approval_report_submit'),
    (r'^client_approval_invite_send/(?P<report_id>\d+)/$', 'client_approval_invite_send'),
    (r'^blogger_approval_status_change/(?P<brand_id>\d+)/(?P<report_id>\d+)/(?P<user_id>\d+)$', 'blogger_approval_status_change'),

    (r'^influencer_posts_info/$', 'influencer_posts_info'),

    (r'^post_analytics_collections/(?P<collection_id>\d+)/edit$', 'post_analytics_collection_edit'),
    (r'^post_analytics_collections/create/$', 'post_analytics_collection_create'),
    (r'^post_analytics_collections/(?P<collection_id>\d+)/$', 'post_analytics_collection'),
    (r'^post_analytics_collections/$', 'post_analytics_collections'),
    (r'^post_analytics/edit/(?P<post_analytics_id>\d+)/$', 'edit_post_analytics'),
    (r'^post_analytics/del/(?P<post_analytics_id>\d+)/$', 'del_post_analytics'),
    (r'^post_analytics_collection/refresh/(?P<collection_id>\d+)/$', 'refresh_post_analytics_collection'),

    (r'^search/main/$', 'main_search'),
)

urlpatterns += patterns('debra.blogger_views',

    (r'^blogger/about/(?P<influencer_id>\d+)/$', 'blogger_about'),
    (r'^blogger/about/(?P<influencer_id>\d+)/edit/$', 'blogger_about_edit'),
    (r'^blogger/edit/(?P<influencer_id>\d+)/$', 'blogger_edit'),

    (r'^blogger/(?P<section>.*?)/(?P<influencer_id>\d+)/$', 'blogger_generic_posts'),
    (r'^blogger/(?P<section>.*?)/(?P<influencer_id>\d+)/brand/(?P<brand_domain>.*?)/$', 'blogger_generic_posts'),

    (r'^blogger/posts/(?P<influencer_id>\d+)/sponsored/$', 'blogger_posts_sponsored'),
    (r'^blogger/posts/(?P<influencer_id>\d+)/$', 'blogger_posts'),
    (r'^blogger/photos/(?P<influencer_id>\d+)/$', 'blogger_photos'),
    (r'^blogger/tweets/(?P<influencer_id>\d+)/$', 'blogger_tweets'),
    (r'^blogger/videos/(?P<influencer_id>\d+)/$', 'blogger_youtube'),
    (r'^blogger/pins/(?P<influencer_id>\d+)/$', 'blogger_pins'),
    (r'^blogger/items/(?P<influencer_id>\d+)/$', 'blogger_items'),

    (r'^blogger/(?P<section>.*?)/(?P<blog_url>.*?)/(?P<influencer_id>\d+)/$', 'blogger_redirection'),
    (r'^blogger/(?P<section>.*?)/(?P<blog_url>.*?)/(?P<influencer_id>\d+)/(?P<sub_section>.*?)/$', 'blogger_redirection'),
)

#DEBRA BRAND PROFILE URLS
urlpatterns += patterns('debra.brand_profile_views',
    (r'^brand/posts/(?P<brand_url>.*?)/(?P<brand_id>\d+)/$', 'brand_posts'),
    (r'^brand/photos/(?P<brand_url>.*?)/(?P<brand_id>\d+)/$', 'brand_photos'),
    (r'^brand/tweets/(?P<brand_url>.*?)/(?P<brand_id>\d+)/$', 'brand_tweets'),
    (r'^brand/pins/(?P<brand_url>.*?)/(?P<brand_id>\d+)/$', 'brand_pins'),
    (r'^brand/items/(?P<brand_url>.*?)/(?P<brand_id>\d+)/$', 'brand_items'),
    (r'^brand/about/(?P<brand_url>.*?)/(?P<brand_id>\d+)/$', 'brand_about'),
    (r'^brand/edit/(?P<brand_url>.*?)/(?P<brand_id>\d+)/$', 'brand_edit'),
)

#DATAEXPORT
urlpatterns += patterns('debra.dataexport_views',
    (r'^export/onetimepaid$', 'export_paid_onetime'),
    (r'^export/list$', 'dataexport_list'),
    (r'^export/template$', 'dataexport_template'),
    (r'^export/template/save$', 'dataexport_save_template'),
    (r'^export/request$', 'export_request'),
    (r'^export/download/(?P<file_type>.*?)/(?P<task_id>.*?)$', 'export_download'),
    (r'^export/post_analytics_collection/(?P<collection_id>\d+)/$',\
        'export_post_analytics_collection_view'),
    (r'^export/campaign_report/(?P<campaign_id>\d+)/$',\
        'export_campaign_report_view'),
    (r'^export/collection/(?P<collection_id>\d+)/$',\
        'export_collection_view'),
)

#JOBS POSTS
urlpatterns += patterns('debra.job_posts_views',
    (r'^campaigns/preview/(?P<id>.*?)$', 'view'),
    (r'^campaigns/edit/(?P<id>.*?)$', 'edit'),
    (r'^campaigns/del/(?P<id>.*?)$', 'delete'),
    (r'^campaigns/add$', 'add'),
    (r'^campaigns/add/upload_attachment$', 'upload_campaign_attachment'),
    (r'^campaigns/$', 'list_jobs'),
    (r'^campaigns/associations/(?P<job_id>.*?)$', 'get_job_collection_associations'),
    (r'^campaigns/as_bloggers$', 'list_as_bloggers'),
    (r'^campaigns/groups/$', 'favorited_bloggers'),
    (r'^campaigns/groups/(?P<group_id>\d+)/(?P<section>[a-z]+)/$', 'list_details'),
    (r'^campaigns/groups/(?P<group_id>\d+)/$', 'list_details'),
    (r'^campaigns/groups/job/(?P<job_id>\d+)/(?P<section>[a-z]+)$', 'list_details_jobpost'),
    (r'^campaigns/groups/job/(?P<job_id>\d+)/', 'list_details_jobpost'),
    (r'^campaigns/groups/get$', 'get_influencer_groups'),
    (r'^campaigns/groups/set$', 'set_influencer_groups'),
    (r'^campaigns/groups/add$', 'add_influencer_groups'),
    (r'^campaigns/groups/edit$', 'edit_influencer_groups'),
    (r'^campaigns/groups/del$', 'delete_influencer_groups'),
    (r'^post_analytics/collections/get/$', 'get_post_analytics_collections'),
    (r'^post_analytics/collections/set/$', 'set_post_analytics_collections'),
    (r'^post_analytics/collections/add/$', 'add_post_analytics_collection'),
    (r'^post_analytics/collections/edit/$', 'edit_post_analytics_collection'),
    (r'^post_analytics/collections/del/$', 'del_post_analytics_collection'),
    (r'^roi_prediction_reports/add/$', 'add_roi_prediction_report'),
    (r'^roi_prediction_reports/edit/$', 'edit_roi_prediction_report'),
    (r'^roi_prediction_reports/del/$', 'del_roi_prediction_report'),
    (r'^campaigns/groups/mapping/edit$', 'edit_influencer_mapping'),
    (r'^campaigns/groups/mapping/delete$', 'remove_influencer_from_groups'),
    (r'^campaigns/groups/job/mapping/delete$', 'remove_candidate_from_campaign'),
    (r'^campaigns/groups/email$', 'send_email_to_influencers'),
    (r'^campaigns/invitation/(?P<map_id>\d+)$', 'invite'),
    (r'^campaigns/invite/$', 'send_invitation'),
    (r'^campaigns/respond/$', 'send_response'),
    (r'^campaigns/invitation/(?P<map_id>\d+)/apply$', 'apply_invitation'),
    (r'^campaigns/invitation/(?P<map_id>\d+)/(?P<thread>[a-z]+)/conversation$', 'get_conversations'),
    (r'^campaigns/messages/(?P<message_id>\d+)/events/$', 'get_message_events'),

    (r'^reassign_campaign_cover/(?P<campaign_id>\d+)/$', 'reassign_campaign_cover'),

    (r'^campaigns/(?P<campaign_id>\d+)/report/(?P<section>[a-z_]+)/(?P<hash_key>[a-fA-F\d]{32})/$', 'campaign_report'),
    (r'^campaigns/(?P<campaign_id>\d+)/report/(?P<section>[a-z_]+)/$', 'campaign_report'),
    (r'^campaigns/(?P<campaign_id>\d+)/report/$', 'campaign_report'),

    (r'^brand_taxonomy/$', 'brand_taxonomy'),

    (r'^campaigns/(?P<campaign_id>\d+)/setup/$', 'campaign_setup'),
    (r'^campaigns/(?P<campaign_id>\d+)/approval/$', 'campaign_approval'),
    (r'^campaigns/(?P<campaign_id>\d+)/load_influencers/$', 'campaign_load_influencers'),
    # (r'^unlinked_messages/$', 'unlinked_messages'),

    (r'^campaigns/(?P<campaign_id>\d+)/edit/$', 'campaign_create'),
    (r'^campaigns/create/$', 'campaign_create'),
    (r'^campaigns/app/edit/$', 'campaign_edit'),

    (r'^messages/(?P<section>[a-z]+)/(?P<section_id>\d+)/$', 'list_messages'),
    (r'^messages/(?P<section>[a-z]+)/$', 'list_messages'),

    (r'^messages/$', 'list_messages'),
    # (r'^messages/$', 'unlinked_messages'),

    (r'^messages/send/$', 'send_message'),
    (r'^messages/upload_attachment/$', 'upload_message_attachment'),
    (r'^messages/(?P<message_id>\d+)/download_attachment/(?P<attachment_name>[\w,\s-]+\.[A-Za-z]{3})/$',
        'download_message_attachment'),

    (r'^messages/set_visible_columns/$', 'set_messages_visible_columns'),

    (r'^bloggers/(?P<contract_id>\d+)/(?P<blogger_hash>[a-fA-F\d]{32})/document_send/$', 'contract_sending_view'),
    (r'^bloggers/(?P<contract_id>\d+)/(?P<blogger_hash>[a-fA-F\d]{32})/document_sign/$', 'contract_signing_view'),
    (r'^bloggers/(?P<contract_id>\d+)/(?P<blogger_hash>[a-fA-F\d]{32})/document_sign/complete$', 'blogger_document_sign_complete'),

    (r'^bloggers/(?P<contract_id>\d+)/(?P<blogger_hash>[a-fA-F\d]{32})/shipment_received/$', 'blogger_shipment_received'),

    (r'^email_template_context/(?P<contract_id>\d+)/$', 'get_email_template_context'),

    (r'^edit_contract/(?P<contract_id>\d+)/$', 'edit_contract'),
    (r'^send_contract/(?P<contract_id>\d+)/$', 'send_contract'),
    (r'^load_document_specific_fields/(?P<contract_id>\d+)/$', 'load_document_specific_fields'),
    (r'^load_document_specific_fields/$', 'load_document_specific_fields'),
    (r'^download_contract_document/(?P<contract_id>\d+)/$', 'download_contract_document'),
    (r'^download_contract_document/(?P<contract_id>\d+)/preview$', 'download_contract_document_preview'),
    (r'^download_campaign_contract_document/(?P<campaign_id>\d+)/preview$', 'download_campaign_contract_document_preview'),
    (r'^docusign_callback/$', 'docusign_callback'),

    (r'^test_document/(?P<contract_id>\d+)/$', 'test_document'),

    (r'^send_tracking_code/(?P<contract_id>\d+)/$', 'send_tracking_code'),
    (r'^send_add_post_link/(?P<contract_id>\d+)/$', 'send_add_post_link'),
    (r'^send_collect_data_link/(?P<contract_id>\d+)/$', 'send_collect_data_link'),
    (r'^send_paypal_info_request/(?P<contract_id>\d+)/$', 'send_paypal_info_request'),
    (r'^send_shipment_notification/(?P<contract_id>\d+)/$', 'send_shipment_notification'),
    (r'^send_followup_message/(?P<contract_id>\d+)/$', 'send_followup_message'),
    (r'^send_posts_adding_notification/(?P<contract_id>\d+)/$', 'send_posts_adding_notification'),
    (r'^mark_payment_complete/(?P<contract_id>\d+)/$', 'mark_payment_complete'),
    
    (r'^campaign_overview_page/(?P<campaign_id>\d+)/$', 'campaign_overview_page'),
    (r'^blogger/tracking_page/(?P<contract_id>\d+)/(?P<hash_key>[a-fA-F\d]{32})/$', 'blogger_tracking_page'),
    (r'^blogger/tracking_link/(?P<contract_id>\d+)/(?P<hash_key>[a-fA-F\d]{32})/$', 'blogger_tracking_link'),
    (r'^blogger/tracking_link/(?P<contract_id>\d+)/(?P<hash_key>[a-fA-F\d]{32})/complete$', 'blogger_tracking_link_complete'),

    (r'^post_analytics_collections/(?P<collection_id>\d+)/stats/$', 'get_post_analytics_collection_stats'),

    (r'^update_model/(?P<model_id>\d+)/$', 'update_model'),
    (r'^update_model/$', 'update_model'),
    (r'^edit_notes/$', 'edit_notes'),
)

from django.views.generic import RedirectView
from debra.job_posts_views import FixRedirectView

# HOT FIX FOR INCORRECT LINKS IN EMAILS
urlpatterns += patterns('debra.job_posts_views',
    # (r'^campaigns/groups/(?P<group_id>\d+)/(?P<origin_url>\d+).*?$', FixRedirectView.as_view()),
    (r'^campaigns/groups/(?P<group_id>\d+)/(?P<origin_url>([\w\.]+)\.([a-z]{2,6}\.?)(\/[\w\.]*)*\/?)$', FixRedirectView.as_view()),
)


#BRAND DASHBOARD
urlpatterns += patterns('debra.brand_dashboard',
    (r'^dashboard/competitor/save$', 'save_competitor'),
    (r'^dashboard/pins/$', 'mentioning_pins'),
    (r'^dashboard/tweets/$', 'mentioning_tweets'),
    (r'^dashboard/posts/$', 'mentioning_posts'),
    (r'^dashboard/collabs/$', 'mentioning_posts_sponsored'),
    (r'^dashboard/products/$', 'mentioning_products'),
    (r'^dashboard/photos/$', 'mentioning_photos'),
    (r'^dashboard/influencers$', 'mentioning_influencers'),
    (r'^dashboard/$', 'dashboard_charts'),
    (r'^dashboard/summary/$', 'summary_page'),
    (r'^dashboard/competitors/pins/$', 'mentioning_competitors_pins'),
    (r'^dashboard/competitors/tweets/$', 'mentioning_competitors_tweets'),
    (r'^dashboard/competitors/posts/$', 'mentioning_competitors_posts'),
    (r'^dashboard/competitors/collabs/$', 'mentioning_competitors_posts_sponsored'),
    (r'^dashboard/competitors/products/$', 'mentioning_competitors_products'),
    (r'^dashboard/competitors/photos/$', 'mentioning_competitors_photos'),
    (r'^dashboard/competitors/influencers$', 'mentioning_competitors_influencers'),
    (r'^dashboard/competitors/$', 'dashboard_competitors_charts'),
    (r'^dashboard/analytics/posts/$', 'posts_analytics'),
)

#BRAND ACCOUNTS
urlpatterns += patterns('debra.brand_account_views',
    (r'^account/$', 'account_landing'),
    (r'^account/notifications$', 'account_notifications'),
    #(r'^account/settings$', 'account_settings'),
    (r'^account/settings/$', 'account_landing'),
    (r'^account/invoice/printable/(?P<invoice_id>.+)$', 'account_invoice_printable'),
    (r'^account/settings/save$', 'save_account_settings'),
    (r'^lookup_timezone$', 'lookup_timezone'),
    (r'^account/email_invoice/$', 'send_latest_invoice_to_email'),
    (r'^account/cc/change/$', 'change_cc'),
    (r'^account/agency/set_as$', 'set_as_agency'),
    (r'^account/agency/add-mark/$', 'mark_add_brand_to_agency'),
    (r'^account/agency/add/$', 'add_brand_to_agency'),
    (r'^account/agency/del/$', 'del_brand_from_agency'),
    (r'^account/agency/set/(?P<id>\d+)$', 'set_agency_main_brand'),
    (r'^account/preferences/$', 'brand_preferences'),
)


#DEBRA PAYMENT URLS
urlpatterns += patterns('debra.payment_views',
    (r'^payment/brand/$', 'brand_payment'),
    (r'^payment/coupon/check$', 'check_coupon'),
    (r'^payment_stripe_webhook/$', 'stripe_webhook'),
    (r'^bloggers/payment_setup_complete/$', 'stripe_callback'),
    (r'^bloggers/payment_authorize/$', 'stripe_auth'),
    (r'^bloggers/(?P<influencer_id>\d+)/payment_page/$', 'blogger_payment_page'),
)

#TEMPORARY BLOGGER DASHBOARD PAGES
urlpatterns += patterns('masuka.blogger_info',
    (r'blogger_info/(?P<bloggerid>\d+)/$', 'blogger_info'),
)

#TEMPORARY VIEW TO TEST OUT NEW XPATH MODULE
urlpatterns += patterns('masuka.xpath_tester',
    (r'xpath_tester/$', 'xpath_tester'),
    (r'save_xpath_test_result/$', 'save_xpath_test_result')
)

#DEBRA EMAIL URLS
urlpatterns += patterns('debra.email_views',
    (r'email/(?P<user>\d+)/lottery/(?P<lottery>\d+)/winner/(\d+)?$', 'lottery_winner'),
    (r'email/(?P<influencer>\d+)/opportunity/(\d+)?$', 'brand_email_influencer'),
)



#DEBRA BOOKMARKLET URLS
urlpatterns += patterns('debra.bookmarklet_views',
    (r'^pricebookmarklet/get-xpaths-for-url$', 'get_xpaths_for_url'),
    (r'^pricebookmarklet/check-evaluated-texts$', 'check_evaluated_texts'),
    (r'^pricebookmarklet/render_bookmarklet$', 'render_bookmarklet'),
)

#DEBRA DYNAMIC FORMS URLS
urlpatterns += patterns('debra.dynamicforms_views',
    (r'^forms/contact_us$', 'contact_us_form'),
    (r'^forms/add_new_user$', 'add_new_user_form'),
)


#MISC DJANGO URLS
urlpatterns += patterns('',
    url(r'^facebook/connect/$', 'django_facebook.views.connect', name='facebook_connect'),
    url(r'^facebook/disconnect/$', 'django_facebook.views.disconnect', name='facebook_disconnect'),
    # For Facebook routing on jawan
    # TODO: REFACTOR THIS FOR PRODUCTION!!!
    (r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.STATIC_ROOT}),
)

#MASUKA URLS
urlpatterns += patterns('masuka',
    (r'^image_upload/$', 'image_manipulator.image_upload'),
    (r'^campaigns/cover/upload/$', 'image_manipulator.upload_campaign_cover'),
    (r'^image/blogger-collage/(?P<user>\d+)/upload/$', 'image_manipulator.create_shelf_share_screenshot'),
    (r'^image/blogger-collage/(?P<user>\d+)/download/$', 'image_manipulator.download_image'),
    (r'^image/style-collage/(?P<user>\d+)/generate/$', 'image_manipulator.create_profile_collage_screenshot'),
    (r'^mechanical-turk/process$', 'mechanical_turk.process_response'),
)

#CAPTCHA URLS
urlpatterns += patterns('',
    url(r'^captcha/', include('captcha.urls')),
)

#DEBUG SQL QUERIES
urlpatterns += patterns('debra.debug_testing',
    (r'^price_tracker/$', 'price_tracker_queries'),
)

#CACHE REFRESHING URLS
urlpatterns += patterns('',
    url(r'^cacherefresh/product-feed-json/$', 'debra.feeds_helpers.product_feed_json_cacherefresh'),
    url(r'^cacherefresh/instagram-feed-json/$', 'debra.feeds_helpers.instagram_feed_json_cacherefresh'),
    url(r'^cacherefresh/blog-feed-json/$', 'debra.feeds_helpers.blog_feed_json_cacherefresh'),
)

