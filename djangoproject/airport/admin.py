"""ModelAdmin registration"""

from django.contrib import admin

from models import Airport, City, Flight


admin.site.register(Airport)
admin.site.register(City)
admin.site.register(Flight)
