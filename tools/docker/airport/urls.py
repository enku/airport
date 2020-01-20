from django.conf.urls import include, url
from django.contrib.auth import views as auth_views

urlpatterns = [
    url(r'^', include('airport.urls')),
    url(r'^accounts/login/$', auth_views.login),
    url(r'^accounts/logout/$', auth_views.logout, {'next_page': '/'}, name='logout',),
]
