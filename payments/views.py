from decimal import Decimal, InvalidOperation

from accounts.decorators import (
    audit_required,
    finance_required,
    get_user_company_ids,
)

from django.db import models, transaction
from django.shortcuts import render, get_object_or_404, redirect

from .models import Payment
from rentals.models import Rent


def _allowed_company_ids(request):
    """
    Return company IDs accessible to the current user.

    None means unrestricted access for a superuser.
    """
    return get_user_company_ids(request.user)


def _rents_for_user(request):
    qs = Rent.objects.select_related(
        "tenant",
        "house",
        "house__apartment",
    )

    company_ids = _allowed_company_ids(request)

    if company_ids is not None:
        qs = qs.filter(
            house__apartment__company_id__in=company_ids
        )

    return qs


def _payments_for_user(request):
    """
    Current rent payments are scoped through rental_rent.

    Legacy Payment rows without rental_rent are intentionally not
    exposed through this company-scoped ERP dashboard because they
    have no reliable company relationship.
    """
    qs = Payment.objects.select_related(
        "rental_rent",
        "rental_rent__tenant",
        "rental_rent__house",
        "rental_rent__house__apartment",
    )

    company_ids = _allowed_company_ids(request)

    if company_ids is not None:
        qs = qs.filter(
            rental_rent__house__apartment__company_id__in=company_ids
        )

    return qs


@audit_required
def dashboard(request):
    rents = (
        _rents_for_user(request)
        .order_by("due_date")
    )

    unpaid = rents.filter(
        paid=False,
        closed=False,
    )

    paid = (
        rents
        .filter(paid=True)
        .order_by("due_date")
    )

    payment_qs = _payments_for_user(request)

    payments = (
        payment_qs
        .order_by("-created_at")[:50]
    )

    collected_total = (
        payment_qs
        .filter(status="SUCCESS")
        .aggregate(
            total=models.Sum("amount")
        )["total"]
        or Decimal("0.00")
    )

    outstanding_total = (
        unpaid
        .aggregate(
            total=models.Sum("balance")
        )["total"]
        or Decimal("0.00")
    )

    context = {
        "greeting": "AfriAxis Payments Dashboard",
        "total_rents": rents.count(),
        "total_revenue": collected_total,
        "rent_due": outstanding_total,
        "net_outstanding": outstanding_total,

        "successful_payments": (
            payment_qs
            .filter(status="SUCCESS")
            .count()
        ),

        "pending_payments": (
            payment_qs
            .filter(status="PENDING")
            .count()
        ),

        "failed_payments": (
            payment_qs
            .filter(status="FAILED")
            .count()
        ),

        "unpaid_rents": unpaid,
        "paid_rents": paid,
        "payments": payments,
    }

    return render(
        request,
        "payments/dashboard.html",
        context,
    )


@finance_required
def rent_payment_page(request, rent_id):
    rent = get_object_or_404(
        _rents_for_user(request),
        id=rent_id,
    )

    message = None
    error = None

    if request.method == "POST":
        payment_method = (
            request.POST.get(
                "payment_method",
                "BANK",
            )
            .strip()
            .upper()
        )

        # M-Pesa is intentionally excluded.
        # AfriAxis M-Pesa is reserved for Wi-Fi services only.
        allowed_methods = {
            "BANK",
            "CASH",
            "CHEQUE",
        }

        if payment_method not in allowed_methods:
            error = (
                "Invalid payment method. "
                "M-Pesa is available only for Wi-Fi services."
            )

        try:
            amount = Decimal(
                request.POST.get("amount") or "0"
            )
        except (
            InvalidOperation,
            TypeError,
        ):
            amount = Decimal("0.00")

        reference = (
            request.POST.get(
                "reference",
                "",
            )
            .strip()
        )

        description = (
            request.POST.get(
                "description",
                "",
            )
            .strip()
        )

        current_balance = (
            rent.balance
            or Decimal("0.00")
        )

        if not error and amount <= 0:
            error = (
                "Payment amount must be greater than zero."
            )

        if (
            not error
            and current_balance > 0
            and amount > current_balance
        ):
            error = (
                f"Payment cannot exceed outstanding balance "
                f"of KES {current_balance}."
            )

        if not error:
            with transaction.atomic():
                payment = Payment.objects.create(
                    rental_rent=rent,
                    amount=amount,
                    account_reference=(
                        reference
                        or f"RENT-{rent.id}"
                    ),
                    transaction_desc=(
                        description
                        or (
                            f"Rent payment for "
                            f"{rent.tenant.name}"
                        )
                    ),
                    payment_method=payment_method,
                    status="SUCCESS",
                )

                rent.amount_paid = (
                    rent.amount_paid
                    or Decimal("0.00")
                ) + amount

                rent.balance = max(
                    Decimal("0.00"),
                    (
                        rent.amount
                        or Decimal("0.00")
                    ) - rent.amount_paid,
                )

                rent.paid = (
                    rent.balance
                    == Decimal("0.00")
                )

                rent.save(
                    update_fields=[
                        "amount_paid",
                        "balance",
                        "paid",
                    ]
                )

            return redirect(
                "payment_receipt",
                payment_id=payment.id,
            )

    return render(
        request,
        "rent_payment.html",
        {
            "rent": rent,
            "message": message,
            "error": error,
        },
    )


@audit_required
def payment_receipt(request, payment_id):
    payment = get_object_or_404(
        _payments_for_user(request),
        id=payment_id,
    )

    return render(
        request,
        "payments/receipt.html",
        {
            "payment": payment,
        },
    )
