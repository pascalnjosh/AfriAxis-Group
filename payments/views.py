from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from .models import Rent, Payment


def dashboard(request):
    rents = Rent.objects.all()

    unpaid = rents.filter(paid=False)
    paid = rents.filter(paid=True)

    context = {
        "paid_total": paid.aggregate(total=models.Sum("amount"))["total"] or 0,
        "unpaid_total": unpaid.aggregate(total=models.Sum("amount"))["total"] or 0,
        "unpaid_count": unpaid.count(),
        "unpaid_rents": unpaid.order_by("-amount")[:50],
    }

    return render(request, "payments/dashboard.html", context)


def rent_payment_page(request, rent_id):
    rent = get_object_or_404(Rent, id=rent_id)

    if request.method == "POST":
        Payment.objects.create(
            amount=rent.amount,
            phone_number=request.POST.get("phone_number"),
            account_reference=f"RENT-{rent.id}",
            transaction_desc=f"Rent payment for {rent.tenant_name}",
            status="SUCCESS",
        )

        rent.paid = True
        rent.save()

        return redirect("payments_dashboard")

    return render(request, "rent_payment.html", {"rent": rent})