from django.shortcuts import render
from django.db import models
from .models import Rent


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