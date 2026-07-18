from django.contrib import admin
from .models import Deposit


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "house",
        "deposit_type",
        "amount",
        "status",
        "date_received",
        "recorded_by",
    )
    list_filter = ("deposit_type", "status", "date_received")
    search_fields = ("tenant__name", "house__house_number", "reference", "notes")