from django.contrib import admin
from .models import Invoice, InvoicePayment


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):

    list_display = (
        "invoice_number",
        "tenant",
        "apartment",
        "total_amount",
        "amount_paid",
        "status",
        "created_at",
    )

    search_fields = (
        "invoice_number",
        "tenant__name",
        "apartment__name",
    )

    list_filter = (
        "status",
        "apartment",
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
