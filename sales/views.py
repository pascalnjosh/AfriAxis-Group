from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import (
    Customer,
    SalesOrder,
    DeliveryNote,
    SalesInvoice,
    SalesReceipt,
)


@login_required
def sales_dashboard(request):
    customers = (
        Customer.objects
        .filter(active=True)
        .order_by("name")
    )

    sales_orders = (
        SalesOrder.objects
        .select_related(
            "customer",
            "company",
            "branch",
        )
        .order_by(
            "-order_date",
            "-id",
        )[:10]
    )

    delivery_notes = (
        DeliveryNote.objects
        .select_related(
            "customer",
            "sales_order",
            "warehouse",
        )
        .order_by(
            "-delivery_date",
            "-id",
        )[:10]
    )

    sales_invoices = (
        SalesInvoice.objects
        .select_related(
            "customer",
            "sales_order",
            "delivery_note",
        )
        .order_by(
            "-invoice_date",
            "-id",
        )[:10]
    )

    sales_receipts = (
        SalesReceipt.objects
        .select_related(
            "customer",
            "sales_invoice",
            "bank_account",
        )
        .order_by(
            "-receipt_date",
            "-id",
        )[:10]
    )

    context = {
        "customer_count": Customer.objects.count(),
        "active_customer_count": Customer.objects.filter(
            active=True
        ).count(),
        "sales_order_count": SalesOrder.objects.count(),
        "delivery_note_count": DeliveryNote.objects.count(),
        "sales_invoice_count": SalesInvoice.objects.count(),
        "sales_receipt_count": SalesReceipt.objects.count(),

        "customers": customers,
        "sales_orders": sales_orders,
        "delivery_notes": delivery_notes,
        "sales_invoices": sales_invoices,
        "sales_receipts": sales_receipts,
    }

    return render(
        request,
        "sales/dashboard.html",
        context,
    )
