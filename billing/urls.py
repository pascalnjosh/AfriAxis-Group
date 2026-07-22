from django.urls import path

from .views import (
    invoice_list,
    invoice_detail,
    tenant_status,
    pay_invoice,
    invoice_pdf,
    tenant_portal,
    receipt_detail,
    commercial_invoice_create,
)

from .apartment_views import apartment_statement
from .apartment_pdf_views import apartment_statement_pdf


urlpatterns = [

    path("invoices/", invoice_list, name="invoice_list"),

    path(
        "invoices/create/commercial/",
        commercial_invoice_create,
        name="commercial_invoice_create",
    ),

    path("invoices/<int:invoice_id>/", invoice_detail, name="invoice_detail"),

    path("tenant/<int:tenant_id>/", tenant_status, name="tenant_status"),

    path("tenant-portal/<int:tenant_id>/", tenant_portal, name="tenant_portal"),

    path("invoice/<int:invoice_id>/pay/", pay_invoice, name="pay_invoice"),

    path("invoice/<int:invoice_id>/pdf/", invoice_pdf, name="invoice_pdf"),

    path("receipt/<int:payment_id>/", receipt_detail, name="receipt_detail"),

    path("apartment/<int:apartment_id>/statement/", apartment_statement, name="apartment_statement"),

    path("apartment/<int:apartment_id>/statement/pdf/", apartment_statement_pdf, name="apartment_statement_pdf"),
]


