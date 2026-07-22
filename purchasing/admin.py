from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    Supplier,
    SupplierInvoice,
)
from .services import post_goods_receipt


class PurchaseRequestLineInline(admin.TabularInline):
    model = PurchaseRequestLine
    extra = 1


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number",
        "company",
        "branch",
        "request_date",
        "required_date",
        "status",
    )

    list_filter = (
        "status",
        "request_date",
        "company",
        "branch",
    )

    search_fields = (
        "request_number",
        "reason",
    )

    inlines = [PurchaseRequestLineInline]


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "supplier",
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
        "supplier__name",
        "supplier__supplier_code",
    )

    readonly_fields = (
        "subtotal",
        "tax_amount",
        "total_amount",
        "created_at",
        "approved_at",
    )

    inlines = [PurchaseOrderLineInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        form.instance.calculate_totals()


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 1


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "purchase_order",
        "supplier",
        "warehouse",
        "receipt_date",
        "status",
    )

    list_filter = (
        "status",
        "receipt_date",
        "warehouse",
    )

    search_fields = (
        "receipt_number",
        "purchase_order__order_number",
        "supplier__name",
        "supplier_delivery_note",
    )

    readonly_fields = (
        "posted_at",
        "created_at",
    )

    inlines = [GoodsReceiptLineInline]

    actions = ["post_selected_goods_receipts"]

    @admin.action(
        description="Post selected goods receipts"
    )
    def post_selected_goods_receipts(self, request, queryset):
        posted = 0
        failed = 0

        for receipt in queryset:
            try:
                post_goods_receipt(
                    goods_receipt=receipt,
                    user=request.user,
                )
                posted += 1

            except (ValidationError, ValueError) as exc:
                failed += 1

                message = (
                    "; ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )

                self.message_user(
                    request,
                    f"{receipt.receipt_number}: {message}",
                    level=messages.ERROR,
                )

        if posted:
            self.message_user(
                request,
                f"{posted} goods receipt(s) posted successfully.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} goods receipt(s) failed.",
                level=messages.WARNING,
            )


for model in (
    Supplier,
    SupplierInvoice,
):
    if not admin.site.is_registered(model):
        admin.site.register(model)
