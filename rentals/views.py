from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .models import Apartment, Tenant, House, Rent


def move_out_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)

    house = House.objects.filter(
        tenant=tenant,
        occupied=True,
    ).first()

    if house:
        house.occupied = False
        house.tenant = None
        house.save()

    tenant.delete()

    return redirect("/dashboard/tenants/")


def assign_tenant(request, house_id):
    house = get_object_or_404(House, id=house_id)

    if request.method == "POST":
        name = request.POST.get("name")
        phone = request.POST.get("phone")

        tenant = Tenant.objects.create(
            name=name,
            phone=phone,
            apartment=house.apartment,
        )

        house.tenant = tenant
        house.occupied = True
        house.save()

        Rent.objects.create(
            tenant=tenant,
            house=house,
            amount=house.rent_amount,
            amount_paid=0,
            balance=house.rent_amount,
            paid=False,
            due_date=timezone.now().date(),
            billing_month=date.today().replace(day=1),
        )

        return redirect("/dashboard/tenants/")

    return render(request, "rentals/assign_tenant.html", {"house": house})


def rent_balance_report(request):
    apartments = Apartment.objects.all().order_by("name")

    latest_rent = Rent.objects.order_by("-billing_month").first()

    if latest_rent:
        default_month = latest_rent.billing_month.month
        default_year = latest_rent.billing_month.year
    else:
        today = date.today()
        default_month = today.month
        default_year = today.year

    apartment_id = request.GET.get("apartment")
    month = request.GET.get("month", str(default_month))
    year = request.GET.get("year", str(default_year))

    rents = Rent.objects.select_related(
        "tenant",
        "house",
        "house__apartment",
    )

    if apartment_id:
        rents = rents.filter(house__apartment_id=apartment_id)

    if month:
        rents = rents.filter(billing_month__month=month)

    if year:
        rents = rents.filter(billing_month__year=year)

    rents = rents.order_by(
        "house__apartment__name",
        "house__house_number",
    )

    total_rent = sum(r.amount for r in rents)
    total_paid = sum(r.amount_paid for r in rents)
    total_balance = sum(r.balance for r in rents)

    return render(
        request,
        "rentals/rent_balance_report.html",
        {
            "rents": rents,
            "apartments": apartments,
            "selected_apartment": apartment_id,
            "selected_month": month,
            "selected_year": year,
            "months": range(1, 13),
            "years": [2026, 2027, 2028],
            "total_rent": total_rent,
            "total_paid": total_paid,
            "total_balance": total_balance,
        },
    )