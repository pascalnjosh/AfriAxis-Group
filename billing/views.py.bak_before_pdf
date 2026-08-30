from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse

from billing.models import Invoice
from billing.utils import apply_mpesa_to_invoice
from rentals.models import Tenant


def invoice_list(request):

    invoices = Invoice.objects.select_related(
        "tenant",
        "apartment"
    ).order_by("-created_at")

    return render(
        request,
        "billing/invoice_list.html",
        {
            "invoices": invoices,
        }
    )


def invoice_detail(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    return render(
        request,
        "billing/invoice_detail.html",
        {
            "invoice": invoice,
        }
    )


def tenant_status(request, tenant_id):

    tenant = get_object_or_404(
        Tenant,
        id=tenant_id
    )

    invoices = tenant.invoice_set.all().order_by(
        "-created_at"
    )

    return render(
        request,
        "tenant_status.html",
        {
            "tenant": tenant,
            "invoices": invoices,
        }
    )


def pay_invoice(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if request.method == "POST":

        amount = request.POST.get("amount")
        phone = request.POST.get("phone")

        apply_mpesa_to_invoice(
            phone_number=phone,
            amount=amount,
            receipt=f"MANUAL-{invoice.invoice_number}",
            invoice=invoice,
        )

        return redirect(
            "tenant_status",
            tenant_id=invoice.tenant.id
        )

    return render(
        request,
        "pay_invoice.html",
        {
            "invoice": invoice,
        }
    )


def invoice_pdf(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    content = f"""
AFRIAXIS ERP INVOICE
--------------------------------

Invoice Number:
{invoice.invoice_number}

Tenant:
{invoice.tenant.name}

Apartment:
{invoice.apartment.name}

Rent:
KES {invoice.rent_amount}

Water:
KES {invoice.water_amount}

WiFi:
KES {invoice.wifi_amount}

TOTAL:
KES {invoice.total_amount}

PAID:
KES {invoice.amount_paid}

BALANCE:
KES {invoice.balance()}

STATUS:
{invoice.status}

Thank you for using AfriAxis ERP
"""

    response = HttpResponse(
        content,
        content_type="text/plain"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{invoice.invoice_number}.txt"'
    )

    return response


def tenant_portal(request, tenant_id):

    tenant = get_object_or_404(
        Tenant,
        id=tenant_id
    )

    invoices = Invoice.objects.filter(
        tenant=tenant
    ).order_by(
        "-created_at"
    )

    total_billed = 0
    total_paid = 0
    total_balance = 0

    for invoice in invoices:
        total_billed += invoice.total_amount
        total_paid += invoice.amount_paid
        total_balance += invoice.balance()

    return render(
        request,
        "billing/tenant_portal.html",
        {
            "tenant": tenant,
            "invoices": invoices,
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_balance": total_balance,
        }
    )


def receipt_detail(request, payment_id):

    from billing.models import InvoicePayment

    payment = get_object_or_404(
        InvoicePayment,
        id=payment_id
    )

    return render(
        request,
        "billing/receipt_detail.html",
        {
            "payment": payment,
            "invoice": payment.invoice,
        }
    )

