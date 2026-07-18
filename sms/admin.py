from django.contrib import admin
from .models import SMSReminder


@admin.register(SMSReminder)
class SMSReminderAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "reminder_type",
        "phone_number",
        "status",
        "created_at",
        "sent_at",
        "recorded_by",
    )
    list_filter = ("reminder_type", "status", "created_at")
    search_fields = ("tenant__name", "phone_number", "message")