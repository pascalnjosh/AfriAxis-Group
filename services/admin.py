from django.contrib import admin
from .models import (
    WifiPackage,
    WifiCustomer,
    WifiPayment,
    WifiCallbackLog,
    WaterMeter,
    WaterReading,
    WaterBill,
)

admin.site.register(WifiPackage)
admin.site.register(WifiCustomer)
admin.site.register(WifiPayment)
admin.site.register(WifiCallbackLog)
admin.site.register(WaterMeter)
admin.site.register(WaterReading)
admin.site.register(WaterBill)