from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Apartment, Tenant, House, Rent

admin.site.register(Apartment)
admin.site.register(Tenant)
admin.site.register(House)
admin.site.register(Rent)