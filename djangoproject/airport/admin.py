"""ModelAdmin registration"""

from django.contrib import admin

from models import (Airport, City, Flight, UserProfile)


admin.site.register(Airport)
admin.site.register(City)
admin.site.register(Flight)
admin.site.register(UserProfile)
