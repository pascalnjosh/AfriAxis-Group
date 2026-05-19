from django.contrib import admin
from .models import Apartment, Tenant, House, Rent


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "total_units",
        "location",
        "active",
    )

    search_fields = (
        "name",
        "location",
    )

    list_filter = (
        "active",
    )


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "phone",
        "apartment",
    )

    search_fields = (
        "name",
        "phone",
    )

    list_filter = (
        "apartment",
    )


@admin.register(House)
class HouseAdmin(admin.ModelAdmin):

    list_display = (
        "house_number",
        "apartment",
        "rent_amount",
        "occupied",
    )

    search_fields = (
        "house_number",
    )

    list_filter = (
        "occupied",
        "apartment",
    )


@admin.register(Rent)
class RentAdmin(admin.ModelAdmin):

    list_display = (
        "tenant",
        "house",
        "amount",
        "paid",
        "due_date",
    )

    search_fields = (
        "tenant__name",
        "house__house_number",
    )

    list_filter = (
        "paid",
        "due_date",
        "house__apartment",
    )
