from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    Customer,
    DeliveryNote,
    DeliveryNoteLine,
    PriceList,
    PriceListItem,
    Product,
    ProductCategory,
    SalesOrder,
    SalesOrderLine,
    UnitOfMeasure,
)
from .services import post_delivery_note


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer",
        "order_date",
        "status",
        "currency",
        "total_amount",
    )

    list_filter = (
        "status",
        "order_date",
        "company",
        "branch",
    )

    search_fields = (
        "order_number",
        "customer__name",
        "customer_reference",
    )

    readonly_fields = (
        "subtotal",
        "discount_amount",
        "tax_amount",
        "total_amount",
        "created_at",
        "updated_at",
        "approved_at",
    )

    inlines = [SalesOrderLineInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        form.instance.calculate_totals()


class DeliveryNoteLineInline(admin.TabularInline):
    model = DeliveryNoteLine
    extra = 1


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(admin.ModelAdmin):
    list_display = (
        "delivery_number",
        "sales_order",
        "customer",
        "warehouse",
        "delivery_date",
        "status",
    )

    list_filter = (
        "status",
        "delivery_date",
        "warehouse",
    )

    search_fields = (
        "delivery_number",
        "sales_order__order_number",
        "customer__name",
        "vehicle_number",
        "driver_name",
    )

    readonly_fields = (
        "posted_at",
        "created_at",
    )

    inlines = [DeliveryNoteLineInline]

    actions = ["post_selected_delivery_notes"]

    @admin.action(
        description="Post selected delivery notes"
    )
    def post_selected_delivery_notes(self, request, queryset):
        posted = 0
        failed = 0

        for delivery_note in queryset:
            try:
                post_delivery_note(
                    delivery_note=delivery_note,
                    user=request.user,
                )
                posted += 1

            except ValidationError as exc:
                failed += 1

                self.message_user(
                    request,
                    (
                        f"{delivery_note.delivery_number}: "
                        f"{'; '.join(exc.messages)}"
                    ),
                    level=messages.ERROR,
                )

        if posted:
            self.message_user(
                request,
                f"{posted} delivery note(s) posted successfully.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} delivery note(s) failed.",
                level=messages.WARNING,
            )


for model in (
    Customer,
    Product,
    ProductCategory,
    UnitOfMeasure,
    PriceList,
    PriceListItem,
):
    if not admin.site.is_registered(model):
        admin.site.register(model)
