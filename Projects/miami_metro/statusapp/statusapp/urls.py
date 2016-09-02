from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    url(r'^theshelf-status/', 'statustasks.views.status_table'),
    url(r'^platform-stats/', 'statustasks.views.platform_stats'),
    url(r'^fetcherdata-stats/', 'statustasks.views.fetcherdata_stats'),
    url(r'^shelf-stats/', 'statustasks.views.shelf_stats'),
    url(r'^pmsm-images-stats/', 'statustasks.views.pmsm_images_stats'),
    url(r'^influencer-stats/', 'statustasks.views.influencer_stats'),
    url(r'^execute-sql/', 'statustasks.views.execute_sql'),
    #url(r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    url(r'^accounts/login/$', 'statustasks.views.my_login'),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}),

    # Examples:
    # url(r'^$', 'statusapp.views.home', name='home'),
    # url(r'^statusapp/', include('statusapp.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
)
