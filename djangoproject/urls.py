from django.conf.urls.defaults import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^info$', 'airport.views.info', name='info'),
    url(r'^$', 'airport.views.home', name='home'),
    url(r'^games/info$', 'airport.views.games_info', name='games_info'),
    url(r'^games/create/(\d+)?$', 'airport.views.games_create', name='games_create'),
    url(r'^games/join/(\d+)?$', 'airport.views.games_join', name='games_join'),
    url(r'^games/', 'airport.views.games_home', name='games'),
    url(r'^crash$', 'airport.views.crash'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/register/$', 'airport.views.register', name='register'),
    url(r'^accounts/login/$', 'django.contrib.auth.views.login'),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout',
        {'next_page': '/'}, name='logout'),
    url(r'^about$', 'airport.views.about')
)
