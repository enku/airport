from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('airport.views',
    url(r'^info$', 'info', name='info'),
    url(r'^$', 'home', name='home'),
    url(r'^games/info$', 'games_info', name='games_info'),
    url(r'^games/stats$', 'games_stats'),
    url(r'^games/create/(\d+)?$', 'games_create', name='games_create'),
    url(r'^games/join/(\d+)?$', 'games_join', name='games_join'),
    url(r'^games/$', 'games_home', name='games'),
    url(r'^crash$', 'crash'),
    url(r'^accounts/register/$', 'register', name='register'),
    url(r'^about$', 'about')
)