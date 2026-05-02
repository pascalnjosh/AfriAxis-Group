from django.shortcuts import render
from django.db.models import Sum

from payments.models import Payment
from rentals.models import Apartment, Rent
from services.models import WifiCustomer, WifiPayment, WaterBill
from billing.models import Invoice


def dashboard(request):
    # PAYMENTS
    rent_payments = Payment.objects.filter(status="SUCCESS")
    wifi_payments = WifiPayment.objects.filter(status="SUCCESS")

    total_rent_revenue = rent_payments.aggregate(total=Sum("amount"))["total"] or 0
    total_wifi_revenue = wifi_payments.aggregate(total=Sum("amount"))["total"] or 0

    # WATER
    water_bills = WaterBill.objects.all()
    total_water_revenue = water_bills.filter(paid=True).aggregate(total=Sum("total_amount"))["total"] or 0

    # RENT STATUS
    total_rents = Rent.objects.count()
    paid_rents = Rent.objects.filter(paid=True).count()
    unpaid_rents = Rent.objects.filter(paid=False).count()

    # WIFI STATUS
    active_wifi = WifiCustomer.objects.filter(active=True).count()
    inactive_wifi = WifiCustomer.objects.filter(active=False).count()

    # WATER STATUS
    paid_water = water_bills.filter(paid=True).count()
    unpaid_water = water_bills.filter(paid=False).count()

    # INVOICES
    invoices = Invoice.objects.all()
    invoice_total = sum(i.total_amount for i in invoices)
    invoice_paid = sum(i.amount_paid for i in invoices)
    invoice_balance = invoice_total - invoice_paid

    # APARTMENTS
    apartments = []
    for apt in Apartment.objects.all():
        houses = apt.houses.all()
        rents = Rent.objects.filter(house__in=houses)

        apartments.append({
            "name": apt.name,
            "units": apt.total_units,
            "houses": houses.count(),
            "tenants": apt.tenants.count(),
            "paid_rent": rents.filter(paid=True).count(),
            "unpaid_rent": rents.filter(paid=False).count(),
        })

    context = {
        "company_name": "AfriAxis Group",

        "total_rent_revenue": total_rent_revenue,
        "total_wifi_revenue": total_wifi_revenue,
        "total_water_revenue": total_water_revenue,
        "grand_total": total_rent_revenue + total_wifi_revenue + total_water_revenue,

        "total_rents": total_rents,
        "paid_rents": paid_rents,
        "unpaid_rents": unpaid_rents,

        "active_wifi": active_wifi,
        "inactive_wifi": inactive_wifi,

        "paid_water": paid_water,
        "unpaid_water": unpaid_water,

        "invoice_total": invoice_total,
        "invoice_paid": invoice_paid,
        "invoice_balance": invoice_balance,

        "apartments": apartments,
    }

    return render(request, "dashboard.html", context)