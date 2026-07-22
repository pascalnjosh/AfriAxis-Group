from django.contrib import admin

from .models import (
    Customer,
    PriceList,
    PriceListItem,
    Product,
    ProductCategory,
    UnitOfMeasure,
)


class PriceListItemInline(admin.TabularInline):
    model = PriceListItem
    extra = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "customer_code",
        "name",
        "customer_type",
        "phone",
        "kra_pin",
        "credit_limit",
        "current_balance",
        "active",
    )

    search_fields = (
        "customer_code",
        "name",
        "phone",
        "email",
        "kra_pin",
    )

    list_filter = (
        "company",
        "customer_type",
        "active",
    )


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "company",
        "active",
    )

    search_fields = (
        "code",
        "name",
    )

    list_filter = (
        "company",
        "active",
    )


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "company",
        "active",
    )

    search_fields = (
        "code",
        "name",
    )

    list_filter = (
        "company",
        "active",
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_code",
        "name",
        "product_type",
        "category",
        "unit",
        "selling_price",
        "tax_rate",
        "track_inventory",
        "active",
    )

    search_fields = (
        "product_code",
        "barcode",
        "name",
        "etims_item_code",
    )

    list_filter = (
        "company",
        "product_type",
        "category",
        "unit",
        "track_inventory",
        "active",
    )


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "currency",
        "is_default",
        "active",
    )

    list_filter = (
        "company",
        "currency",
        "is_default",
        "active",
    )

    inlines = (
        PriceListItemInline,
    )


@admin.register(PriceListItem)
class PriceListItemAdmin(admin.ModelAdmin):
    list_display = (
        "price_list",
        "product",
        "minimum_quantity",
        "price",
        "active",
    )

    search_fields = (
        "price_list__name",
        "product__product_code",
        "product__name",
    )

    list_filter = (
        "price_list",
        "active",
    )
