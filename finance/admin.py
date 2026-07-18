from django.contrib import admin
from .models import MoneyIn, MoneyOut


@admin.register(MoneyIn)
class MoneyInAdmin(admin.ModelAdmin):
    list_display = ("source", "amount", "received_from", "payment_method", "date_received", "recorded_by")
    list_filter = ("source", "payment_method", "date_received")
    search_fields = ("received_from", "reference", "notes")


@admin.register(MoneyOut)
class MoneyOutAdmin(admin.ModelAdmin):
    list_display = ("category", "amount", "paid_to", "payment_method", "date_paid", "recorded_by")
    list_filter = ("category", "payment_method", "date_paid")
    search_fields = ("paid_to", "reference", "notes")