from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import (
    Supplier,
    PurchaseRequest,
    PurchaseOrder,
    GoodsReceipt,
    SupplierInvoice,
    SupplierPayment,
)


@login_required
def purchasing_dashboard(request):
    suppliers = Supplier.objects.filter(active=True).order_by("name")

    purchase_requests = (
        PurchaseRequest.objects
        .select_related("company", "branch")
        .order_by("-request_date", "-id")[:10]
    )

    purchase_orders = (
        PurchaseOrder.objects
        .select_related("supplier", "company", "branch")
        .order_by("-order_date", "-id")[:10]
    )

    goods_receipts = (
        GoodsReceipt.objects
        .select_related("supplier", "purchase_order", "warehouse")
        .order_by("-receipt_date", "-id")[:10]
    )

    supplier_invoices = (
        SupplierInvoice.objects
        .select_related("supplier", "purchase_order")
        .order_by("-invoice_date", "-id")[:10]
    )

    supplier_payments = (
        SupplierPayment.objects
        .select_related("supplier", "supplier_invoice", "bank_account")
        .order_by("-payment_date", "-id")[:10]
    )

    context = {
        "supplier_count": Supplier.objects.count(),
        "active_supplier_count": Supplier.objects.filter(active=True).count(),
        "purchase_request_count": PurchaseRequest.objects.count(),
        "purchase_order_count": PurchaseOrder.objects.count(),
        "goods_receipt_count": GoodsReceipt.objects.count(),
        "supplier_invoice_count": SupplierInvoice.objects.count(),
        "supplier_payment_count": SupplierPayment.objects.count(),

        "suppliers": suppliers,
        "purchase_requests": purchase_requests,
        "purchase_orders": purchase_orders,
        "goods_receipts": goods_receipts,
        "supplier_invoices": supplier_invoices,
        "supplier_payments": supplier_payments,
    }

    return render(
        request,
        "purchasing/dashboard.html",
        context,
    )
