from django.shortcuts import render, get_object_or_404, redirect
from billing.models import Invoice
from billing.utils import apply_mpesa_to_invoice
from rentals.models import Tenant


def tenant_status(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    invoices = tenant.invoices.all().order_by("-created_at")

    return render(request, "tenant_status.html", {
        "tenant": tenant,
        "invoices": invoices,
    })


def pay_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)

    if request.method == "POST":
        amount = request.POST.get("amount")
        phone = request.POST.get("phone")

        apply_mpesa_to_invoice(
            phone_number=phone,
            amount=amount,
            receipt=f"MANUAL-{invoice.invoice_number}"
        )

        return redirect("tenant_status", tenant_id=invoice.tenant.id)

    return render(request, "pay_invoice.html", {
        "invoice": invoice,
    })