from django.contrib import admin
from .models import WaterBill


@admin.register(WaterBill)
class WaterBillAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "house",
        "billing_month",
        "units_used",
        "rate_per_unit",
        "amount",
        "amount_paid",
        "balance",
        "status",
        "created_at",
    )
    list_filter = ("status", "billing_month", "created_at")
    search_fields = ("tenant__name", "house__house_number", "billing_month")