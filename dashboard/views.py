from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render, redirect
from django.utils import timezone

from payments.models import Payment
from rentals.models import Apartment, House, Rent, Tenant


def user_role(request):

    profile = getattr(
        request.user,
        "userprofile",
        None
    )

    if profile:
        return profile.role

    return None


def md_dashboard(request):

    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM"]:
        return redirect("/accounts/home/")

    today = timezone.now().date()

    unpaid_rents = Rent.objects.filter(
        paid=False
    ).select_related(
        "tenant",
        "house",
        "house__apartment"
    ).order_by("due_date")

    total_unpaid = Decimal("0")

    for rent in unpaid_rents:
        total_unpaid += rent.amount
        rent.days_overdue = (
            today - rent.due_date
        ).days

    total_houses = House.objects.count()

    occupied_houses = House.objects.filter(
        occupied=True
    ).count()

    vacant_houses = House.objects.filter(
        occupied=False
    ).count()

    if total_houses > 0:

        occupancy_rate = round(
            (occupied_houses / total_houses) * 100,
            2
        )

    else:
        occupancy_rate = 0

    revenue_potential = House.objects.aggregate(
        total=Sum("rent_amount")
    )["total"] or 0

    context = {

        "total_payments": Payment.objects.count(),

        "successful": Payment.objects.filter(
            status="SUCCESS"
        ).count(),

        "pending": Payment.objects.filter(
            status="PENDING"
        ).count(),

        "failed": Payment.objects.filter(
            status="FAILED"
        ).count(),

        "rent_arrears": unpaid_rents.count(),

        "unpaid_rents": unpaid_rents,

        "total_unpaid": total_unpaid,

        "today": today,

        "total_houses": total_houses,

        "occupied_houses": occupied_houses,

        "vacant_houses": vacant_houses,
        "apartment_performance": apartment_performance(),

        "occupancy_rate": occupancy_rate,

        "revenue_potential": revenue_potential,
    }

    return render(
        request,
        "dashboard/md.html",
        context
    )


def rent_report_page(request):

    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "ACCOUNTS"]:
        return redirect("/accounts/home/")

    apartments = Apartment.objects.all().order_by("name")

    rows = []

    grand_total = 0
    grand_paid = 0
    grand_unpaid = 0

    for apartment in apartments:

        rents = Rent.objects.filter(
            house__apartment=apartment
        )

        total = rents.aggregate(
            total=Sum("amount")
        )["total"] or 0

        paid = rents.filter(
            paid=True
        ).aggregate(
            total=Sum("amount")
        )["total"] or 0

        unpaid = rents.filter(
            paid=False
        ).aggregate(
            total=Sum("amount")
        )["total"] or 0

        rows.append({
            "apartment": apartment.name,
            "total": total,
            "paid": paid,
            "unpaid": unpaid,
        })

        grand_total += total
        grand_paid += paid
        grand_unpaid += unpaid

    return render(
        request,
        "dashboard/rent_report.html",
        {
            "rows": rows,
            "grand_total": grand_total,
            "grand_paid": grand_paid,
            "grand_unpaid": grand_unpaid,
        }
    )


def vacant_houses_page(request):

    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM"]:
        return redirect("/accounts/home/")

    vacant_houses = House.objects.filter(
        occupied=False
    ).select_related(
        "apartment"
    ).order_by(
        "apartment__name",
        "house_number"
    )

    return render(
        request,
        "dashboard/vacant_houses.html",
        {
            "vacant_houses": vacant_houses,
        "apartment_performance": apartment_performance(),
            "vacant_count": vacant_houses.count(),
        }
    )


def tenants_page(request):

    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM"]:
        return redirect("/accounts/home/")

    tenants = Tenant.objects.select_related(
        "apartment"
    ).order_by(
        "apartment__name",
        "name"
    )

    return render(
        request,
        "dashboard/tenants.html",
        {
            "tenants": tenants,
            "tenant_count": tenants.count(),
        }
    )


def charts_page(request):

    total_rent = Rent.objects.aggregate(
        total=Sum("amount")
    )["total"] or 0

    unpaid_rent = Rent.objects.filter(
        paid=False
    ).aggregate(
        total=Sum("amount")
    )["total"] or 0

    paid_rent = Rent.objects.filter(
        paid=True
    ).aggregate(
        total=Sum("amount")
    )["total"] or 0

    total_houses = House.objects.count()

    occupied_houses = House.objects.filter(
        occupied=True
    ).count()

    vacant_houses = House.objects.filter(
        occupied=False
    ).count()

    return render(
        request,
        "dashboard/charts.html",
        {
            "total_rent": total_rent,
            "paid_rent": paid_rent,
            "unpaid_rent": unpaid_rent,
            "total_houses": total_houses,
            "occupied_houses": occupied_houses,
            "vacant_houses": vacant_houses,
        "apartment_performance": apartment_performance(),
        }
    )

from django.db.models import Count


def apartment_performance():

    apartments = Apartment.objects.all()

    performance = []

    for apartment in apartments:

        houses = House.objects.filter(
            apartment=apartment
        )

        total_houses = houses.count()

        occupied = houses.filter(
            occupied=True
        ).count()

        vacant = houses.filter(
            occupied=False
        ).count()

        revenue = Rent.objects.filter(
            house__apartment=apartment
        ).aggregate(
            total=Sum("amount")
        )["total"] or 0

        unpaid = Rent.objects.filter(
            house__apartment=apartment,
            paid=False
        ).aggregate(
            total=Sum("amount")
        )["total"] or 0

        if total_houses > 0:
            occupancy = round(
                (occupied / total_houses) * 100,
                2
            )
        else:
            occupancy = 0

        performance.append({
            "name": apartment.name,
            "revenue": revenue,
            "unpaid": unpaid,
            "occupancy": occupancy,
            "vacant": vacant,
        })

    return sorted(
        performance,
        key=lambda x: x["revenue"],
        reverse=True
    )


