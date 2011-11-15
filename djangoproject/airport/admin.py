from django.contrib import admin

from airport.models import Airport, City


admin.site.register(City)
admin.site.register(Airport)
