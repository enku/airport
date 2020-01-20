from django.conf.urls import include, patterns, url

urlpatterns = patterns(
    '',
    (r'^', include('airport.urls')),
    url(r'^accounts/login/$', 'django.contrib.auth.views.login'),
    url(
        r'^accounts/logout/$',
        'django.contrib.auth.views.logout',
        {'next_page': '/'},
        name='logout',
    ),
)
