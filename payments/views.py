from decimal import Decimal, InvalidOperation

from django.db import models, transaction
from django.shortcuts import render, get_object_or_404, redirect

from .models import Payment
from rentals.models import Rent


def user_role(request):
    profile = getattr(
        request.user,
        "userprofile",
        None
    )

    if profile:
        return profile.role

    return None


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM", "ACCOUNTS"]:
        return redirect("/accounts/home/")

    rents = Rent.objects.all().order_by("due_date")

    unpaid = rents.filter(
        paid=False,
        closed=False
    )

    paid = rents.filter(
        paid=True
    ).order_by("due_date")

    payments = Payment.objects.all().order_by(
        "-created_at"
    )[:50]

    collected_total = Payment.objects.filter(
        status="SUCCESS"
    ).aggregate(
        total=models.Sum("amount")
    )["total"] or Decimal("0.00")

    outstanding_total = unpaid.aggregate(
        total=models.Sum("balance")
    )["total"] or Decimal("0.00")

    context = {
        "greeting": "AfriAxis Payments Dashboard",
        "total_rents": rents.count(),
        "total_revenue": collected_total,
        "rent_due": outstanding_total,
        "net_outstanding": outstanding_total,
        "successful_payments": Payment.objects.filter(
            status="SUCCESS"
        ).count(),
        "pending_payments": Payment.objects.filter(
            status="PENDING"
        ).count(),
        "failed_payments": Payment.objects.filter(
            status="FAILED"
        ).count(),
        "unpaid_rents": unpaid,
        "paid_rents": paid,
        "payments": payments,
    }

    return render(
        request,
        "payments/dashboard.html",
        context
    )


def rent_payment_page(request, rent_id):
    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM", "ACCOUNTS"]:
        return redirect("/accounts/home/")

    rent = get_object_or_404(
        Rent,
        id=rent_id
    )

    message = None
    error = None

    if request.method == "POST":
        payment_method = (
            request.POST.get("payment_method", "BANK")
            .strip()
            .upper()
        )

        allowed_methods = {
            "BANK",
            "CASH",
            "CHEQUE",
        }

        if payment_method not in allowed_methods:
            error = "Invalid payment method."

        try:
            amount = Decimal(
                request.POST.get("amount") or "0"
            )
        except (InvalidOperation, TypeError):
            amount = Decimal("0.00")

        reference = (
            request.POST.get("reference", "")
            .strip()
        )

        description = (
            request.POST.get("description", "")
            .strip()
        )

        current_balance = rent.balance or Decimal("0.00")

        if not error and amount <= 0:
            error = "Payment amount must be greater than zero."

        if not error and current_balance > 0 and amount > current_balance:
            error = (
                f"Payment cannot exceed outstanding balance "
                f"of KES {current_balance}."
            )

        if not error:
            with transaction.atomic():
                payment = Payment.objects.create(
                    rental_rent=rent,
                    amount=amount,
                    account_reference=reference or f"RENT-{rent.id}",
                    transaction_desc=(
                        description
                        or f"Rent payment for {rent.tenant.name}"
                    ),
                    payment_method=payment_method,
                    status="SUCCESS",
                )

                rent.amount_paid = (
                    rent.amount_paid or Decimal("0.00")
                ) + amount

                rent.balance = max(
                    Decimal("0.00"),
                    (rent.amount or Decimal("0.00"))
                    - rent.amount_paid
                )

                rent.paid = rent.balance == Decimal("0.00")

                rent.save(
                    update_fields=[
                        "amount_paid",
                        "balance",
                        "paid",
                    ]
                )

            return redirect(
                "payment_receipt",
                payment_id=payment.id
            )

    return render(
        request,
        "rent_payment.html",
        {
            "rent": rent,
            "message": message,
            "error": error,
        }
    )


def payment_receipt(request, payment_id):
    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM", "ACCOUNTS"]:
        return redirect("/accounts/home/")

    payment = get_object_or_404(
        Payment,
        id=payment_id
    )

    return render(
        request,
        "payments/receipt.html",
        {
            "payment": payment
        }
    )

