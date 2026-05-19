from django.urls import path

from .views import (
    invoice_list,
    invoice_detail,
    tenant_status,
    pay_invoice,
    invoice_pdf,
    tenant_portal,
    receipt_detail,
)

urlpatterns = [

    path(
        "invoices/",
        invoice_list,
        name="invoice_list"
    ),

    path(
        "invoices/<int:invoice_id>/",
        invoice_detail,
        name="invoice_detail"
    ),

    path(
        "tenant/<int:tenant_id>/",
        tenant_status,
        name="tenant_status"
    ),

    path(
        "tenant-portal/<int:tenant_id>/",
        tenant_portal,
        name="tenant_portal"
    ),

    path(
        "invoice/<int:invoice_id>/pay/",
        pay_invoice,
        name="pay_invoice"
    ),

    path(
        "invoice/<int:invoice_id>/pdf/",
        invoice_pdf,
        name="invoice_pdf"
    ),

    path(
        "receipt/<int:payment_id>/",
        receipt_detail,
        name="receipt_detail"
    ),
]
