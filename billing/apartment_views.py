from django.shortcuts import render, get_object_or_404
from django.db.models import Sum

from rentals.models import Apartment
from billing.models import Invoice


def apartment_statement(request, apartment_id):

    apartment = get_object_or_404(
        Apartment,
        id=apartment_id
    )

    invoices = Invoice.objects.filter(
        apartment=apartment
    ).select_related(
        "tenant"
    ).order_by(
        "tenant__name",
        "-created_at"
    )

    total_billed = invoices.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    total_paid = invoices.aggregate(
        total=Sum("amount_paid")
    )["total"] or 0

    total_balance = total_billed - total_paid

    return render(
        request,
        "billing/apartment_statement.html",
        {
            "apartment": apartment,
            "invoices": invoices,
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_balance": total_balance,
        }
    )
