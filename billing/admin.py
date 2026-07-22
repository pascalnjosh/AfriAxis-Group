from django.contrib import admin, messages

from etims.services import EtimsService

from .models import Invoice, InvoiceLine, InvoicePayment


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0

    fields = (
        "item_code",
        "description",
        "quantity",
        "unit",
        "unit_price",
        "discount_rate",
        "tax_rate",
        "line_subtotal",
        "discount_amount",
        "tax_amount",
        "line_total",
    )

    readonly_fields = (
        "line_subtotal",
        "discount_amount",
        "tax_amount",
        "line_total",
    )


@admin.action(
    description="Submit selected invoices to eTIMS sandbox"
)
def submit_invoices_to_etims(
    modeladmin,
    request,
    queryset,
):
    submitted = 0
    failed = 0

    try:
        service = EtimsService()
    except RuntimeError as exc:
        modeladmin.message_user(
            request,
            str(exc),
            level=messages.ERROR,
        )
        return

    for invoice in queryset:
        try:
            result = service.submit_invoice(invoice)

            if result.get("success"):
                submitted += 1
            else:
                failed += 1

        except Exception as exc:
            failed += 1

            invoice.etims_status = "FAILED"
            invoice.save(
                update_fields=[
                    "etims_status",
                    "updated_at",
                ]
            )

            modeladmin.message_user(
                request,
                f"{invoice.invoice_number}: {exc}",
                level=messages.ERROR,
            )

    if submitted:
        modeladmin.message_user(
            request,
            (
                f"{submitted} invoice(s) submitted "
                "to the eTIMS sandbox."
            ),
            level=messages.SUCCESS,
        )

    if failed:
        modeladmin.message_user(
            request,
            f"{failed} invoice(s) failed.",
            level=messages.WARNING,
        )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "invoice_type",
        "customer_name",
        "tenant",
        "apartment",
        "total_amount",
        "amount_paid",
        "status",
        "etims_status",
        "invoice_date",
    )

    search_fields = (
        "invoice_number",
        "customer_name",
        "customer_phone",
        "customer_kra_pin",
        "tenant__name",
        "apartment__name",
        "etims_receipt_number",
    )

    list_filter = (
        "invoice_type",
        "status",
        "etims_status",
        "apartment",
        "invoice_date",
        "created_at",
    )

    readonly_fields = (
        "subtotal",
        "discount_amount",
        "tax_amount",
        "total_amount",
        "amount_paid",
        "created_at",
        "updated_at",
        "etims_submitted_at",
    )

    fieldsets = (
        (
            "Invoice",
            {
                "fields": (
                    "invoice_number",
                    "invoice_type",
                    "invoice_date",
                    "due_date",
                    "currency",
                    "status",
                )
            },
        ),
        (
            "Rental Link",
            {
                "fields": (
                    "tenant",
                    "apartment",
                )
            },
        ),
        (
            "Customer Snapshot",
            {
                "fields": (
                    "customer_name",
                    "customer_phone",
                    "customer_email",
                    "customer_address",
                    "customer_kra_pin",
                )
            },
        ),
        (
            "Legacy Rental Charges",
            {
                "fields": (
                    "rent_amount",
                    "water_amount",
                    "wifi_amount",
                )
            },
        ),
        (
            "Totals",
            {
                "fields": (
                    "subtotal",
                    "discount_amount",
                    "tax_amount",
                    "total_amount",
                    "amount_paid",
                )
            },
        ),
        (
            "eTIMS",
            {
                "fields": (
                    "etims_status",
                    "etims_control_unit_number",
                    "etims_receipt_number",
                    "etims_internal_data",
                    "etims_signature",
                    "etims_qr_code_url",
                    "etims_submitted_at",
                )
            },
        ),
        (
            "Notes",
            {
                "fields": (
                    "notes",
                    "terms",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    inlines = (InvoiceLineInline,)

    actions = (
        submit_invoices_to_etims,
    )


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "description",
        "quantity",
        "unit",
        "unit_price",
        "tax_rate",
        "line_total",
    )

    search_fields = (
        "invoice__invoice_number",
        "description",
        "item_code",
    )

    list_filter = (
        "unit",
        "tax_rate",
        "created_at",
    )

    readonly_fields = (
        "line_subtotal",
        "discount_amount",
        "tax_amount",
        "line_total",
        "created_at",
    )


@admin.register(InvoicePayment)
class InvoicePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "amount",
        "phone_number",
        "mpesa_receipt",
        "paid_at",
    )

    search_fields = (
        "invoice__invoice_number",
        "phone_number",
        "mpesa_receipt",
    )

    list_filter = (
        "paid_at",
    )
