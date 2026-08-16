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
    SalesInvoice,
    SalesInvoiceLine,
    SalesOrder,
    SalesOrderLine,
    UnitOfMeasure,
)
from .services import post_delivery_note, post_sales_invoice


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


class SalesInvoiceLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 1


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "customer",
        "sales_order",
        "invoice_date",
        "due_date",
        "currency",
        "total_amount",
        "amount_paid",
        "balance_display",
        "status",
    )

    list_filter = (
        "status",
        "invoice_date",
        "due_date",
        "company",
        "branch",
        "currency",
    )

    search_fields = (
        "invoice_number",
        "customer__name",
        "customer__customer_code",
        "sales_order__order_number",
        "customer_reference",
    )

    readonly_fields = (
        "subtotal",
        "discount_amount",
        "tax_amount",
        "total_amount",
        "amount_paid",
        "balance_display",
        "posted_by",
        "posted_at",
        "created_at",
        "updated_at",
    )

    inlines = [SalesInvoiceLineInline]

    actions = ["post_selected_sales_invoices"]

    @admin.display(description="Balance")
    def balance_display(self, obj):
        if obj.pk:
            return obj.balance
        return "0.00"

    def save_related(self, request, form, formsets, change):
        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        if form.instance.status == "DRAFT":
            form.instance.calculate_totals()

    @admin.action(
        description="Post selected sales invoices"
    )
    def post_selected_sales_invoices(
        self,
        request,
        queryset,
    ):
        posted = 0
        already_posted = 0
        failed = 0

        for invoice in queryset:
            try:
                original_status = invoice.status

                post_sales_invoice(
                    sales_invoice=invoice,
                    user=request.user,
                )

                if original_status == "POSTED":
                    already_posted += 1
                else:
                    posted += 1

            except ValidationError as exc:
                failed += 1

                reference = (
                    invoice.invoice_number
                    or f"Invoice ID {invoice.pk}"
                )

                self.message_user(
                    request,
                    (
                        f"{reference}: "
                        f"{'; '.join(exc.messages)}"
                    ),
                    level=messages.ERROR,
                )

            except Exception as exc:
                failed += 1

                reference = (
                    invoice.invoice_number
                    or f"Invoice ID {invoice.pk}"
                )

                self.message_user(
                    request,
                    f"{reference}: {exc}",
                    level=messages.ERROR,
                )

        if posted:
            self.message_user(
                request,
                f"{posted} sales invoice(s) posted successfully.",
                level=messages.SUCCESS,
            )

        if already_posted:
            self.message_user(
                request,
                (
                    f"{already_posted} sales invoice(s) "
                    "were already posted."
                ),
                level=messages.INFO,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} sales invoice(s) failed.",
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
