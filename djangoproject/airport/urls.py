from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^info$', views.info, name='info'),
    url(r'^$', views.main, name='main'),
    url(r'^messages/$', views.messages, name='messages'),
    url(r'^games_info/$', views.games_info, name='games_info'),
    url(r'^games_stats/$', views.games_stats),
    url(r'^games_create/$', views.games_create, name='games_create'),
    url(r'^games_join/$', views.games_join, name='games_join'),
    url(r'^games_pause/$', views.pause_game, name='pause_game'),
    url(r'^games_quit/$', views.rage_quit, name='rage_quit'),
    url(r'^games_start/$', views.games_start, name='start_game'),
    url(r'^game_summary/$', views.game_summary, name='game_summary'),
    url(r'^city_image/$', views.city_image, name='city_image'),
    url(r'^city_image/(.*)/$', views.city_image),
    url(r'^crash/$', views.crash),
    url(r'^register/$', views.register, name='register'),
    url(r'^about/$', views.about),
]
