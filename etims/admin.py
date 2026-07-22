from django.contrib import admin

from .models import EtimsConfiguration


@admin.register(EtimsConfiguration)
class EtimsConfigurationAdmin(admin.ModelAdmin):

    list_display = (
        "company_name",
        "kra_pin",
        "environment",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "environment",
        "is_active",
    )

    search_fields = (
        "company_name",
        "kra_pin",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Company",
            {
                "fields": (
                    "company_name",
                    "kra_pin",
                    "branch_id",
                    "device_serial_number",
                )
            },
        ),
        (
            "API Configuration",
            {
                "fields": (
                    "environment",
                    "api_base_url",
                    "client_id",
                    "client_secret",
                    "is_active",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
