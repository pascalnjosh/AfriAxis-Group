from django.shortcuts import render
from .models import Rent
from django.db import models

def dashboard(request):
    unpaid_rents = Rent.objects.filter(status="unpaid").order_by('-amount')[:50]

    rent_revenue = Rent.objects.filter(status="paid").aggregate(total=models.Sum('amount'))['total'] or 0
    unpaid_total = Rent.objects.filter(status="unpaid").aggregate(total=models.Sum('amount'))['total'] or 0
    unpaid_rent_count = Rent.objects.filter(status="unpaid").count()

    return render(request, "dashboard.html", {
        "unpaid_rents": unpaid_rents,
        "rent_revenue": rent_revenue,
        "unpaid_total": unpaid_total,
        "unpaid_rent_count": unpaid_rent_count
    })