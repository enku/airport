from __future__ import unicode_literals

from django.conf.urls import patterns, url

urlpatterns = patterns(
    'airport.views',
    url(r'^info$', 'info', name='info'),
    url(r'^$', 'home', name='home'),
    url(r'^messages/$', 'messages', name='messages'),
    url(r'^games_info/$', 'games_info', name='games_info'),
    url(r'^games_stats/$', 'games_stats'),
    url(r'^games_create/$', 'games_create', name='games_create'),
    url(r'^games_join/$', 'games_join', name='games_join'),
    url(r'^games_pause/$', 'pause_game', name='pause_game'),
    url(r'^games_quit/$', 'rage_quit', name='rage_quit'),
    url(r'^game_summary/$', 'game_summary', name='game_summary'),
    url(r'^games/$', 'games_home', name='games'),
    url(r'^city_image/$', 'city_image', name='city_image'),
    url(r'^city_image/(.*)/$', 'city_image'),
    url(r'^crash/$', 'crash'),
    url(r'^register/$', 'register', name='register'),
    url(r'^about/$', 'about')
)
