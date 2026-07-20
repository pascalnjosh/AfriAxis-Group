from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from .models import WaterBill


@login_required
def water_dashboard(request):
    month = request.GET.get("month", "").strip()
    status = request.GET.get("status", "").strip()
    search = request.GET.get("search", "").strip()

    bills = (
        WaterBill.objects
        .select_related(
            "tenant",
            "house",
            "house__apartment",
        )
        .order_by("-created_at", "tenant__name")
    )

    if month:
        bills = bills.filter(billing_month__icontains=month)

    if status:
        bills = bills.filter(status=status)

    if search:
        bills = bills.filter(
            tenant__name__icontains=search
        ) | bills.filter(
            house__house_number__icontains=search
        )

    totals = bills.aggregate(
        total_amount=Sum("amount"),
        total_paid=Sum("amount_paid"),
        total_balance=Sum("balance"),
    )

    context = {
        "bills": bills[:300],
        "selected_month": month,
        "selected_status": status,
        "search": search,
        "total_bills": bills.count(),
        "total_amount": totals["total_amount"] or Decimal("0"),
        "total_paid": totals["total_paid"] or Decimal("0"),
        "total_balance": totals["total_balance"] or Decimal("0"),
        "unpaid_count": bills.filter(status="unpaid").count(),
        "partial_count": bills.filter(status="partial").count(),
        "paid_count": bills.filter(status="paid").count(),
    }

    return render(
        request,
        "water/dashboard.html",
        context,
    )
