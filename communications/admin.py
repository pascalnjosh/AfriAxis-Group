from django.contrib import admin

from .models import SmsMessage


@admin.register(SmsMessage)
class SmsMessageAdmin(admin.ModelAdmin):

    list_display = (
        "created_at",
        "bill_type",
        "recipient_name",
        "phone_number",
        "status",
        "reference",
    )

    list_filter = (
        "bill_type",
        "status",
        "created_at",
    )

    search_fields = (
        "recipient_name",
        "phone_number",
        "reference",
        "message",
    )

    readonly_fields = (
        "created_at",
        "sent_at",
        "delivered_at",
    )
