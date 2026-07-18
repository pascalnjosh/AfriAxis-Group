from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render, redirect
from django.utils import timezone

from payments.models import Payment
from rentals.models import Apartment, House, Rent, Tenant
from finance.models import MoneyIn, MoneyOut
from water.models import WaterBill
from deposits.models import Deposit
from sms.models import SMSReminder


def user_role(request):
    profile = getattr(request.user, "userprofile", None)

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

        if rent.due_date:
            rent.days_overdue = (today - rent.due_date).days
        else:
            rent.days_overdue = 0

    total_houses = House.objects.count()
    occupied_houses = House.objects.filter(occupied=True).count()
    vacant_houses = House.objects.filter(occupied=False).count()

    if total_houses > 0:
        occupancy_rate = round((occupied_houses / total_houses) * 100, 2)
    else:
        occupancy_rate = 0

    revenue_potential = House.objects.aggregate(
        total=Sum("rent_amount")
    )["total"] or 0

    total_money_in = MoneyIn.objects.aggregate(
        total=Sum("amount")
    )["total"] or 0

    total_money_out = MoneyOut.objects.aggregate(
        total=Sum("amount")
    )["total"] or 0

    cash_balance = total_money_in - total_money_out

    water_total = WaterBill.objects.aggregate(
        total=Sum("amount")
    )["total"] or 0

    water_paid = WaterBill.objects.aggregate(
        total=Sum("amount_paid")
    )["total"] or 0

    water_balance = WaterBill.objects.aggregate(
        total=Sum("balance")
    )["total"] or 0

    deposits_held = Deposit.objects.filter(
        status="held"
    ).aggregate(
        total=Sum("amount")
    )["total"] or 0

    sms_drafts = SMSReminder.objects.filter(status="draft").count()
    sms_sent = SMSReminder.objects.filter(status="sent").count()
    sms_failed = SMSReminder.objects.filter(status="failed").count()

    context = {
        "total_payments": Payment.objects.count(),
        "successful": Payment.objects.filter(status="SUCCESS").count(),
        "pending": Payment.objects.filter(status="PENDING").count(),
        "failed": Payment.objects.filter(status="FAILED").count(),

        "rent_arrears": unpaid_rents.count(),
        "unpaid_rents": unpaid_rents,
        "total_unpaid": total_unpaid,

        "today": today,
        "total_houses": total_houses,
        "occupied_houses": occupied_houses,
        "vacant_houses": vacant_houses,
        "occupancy_rate": occupancy_rate,
        "revenue_potential": revenue_potential,

        "total_money_in": total_money_in,
        "total_money_out": total_money_out,
        "cash_balance": cash_balance,

        "water_total": water_total,
        "water_paid": water_paid,
        "water_balance": water_balance,

        "deposits_held": deposits_held,

        "sms_drafts": sms_drafts,
        "sms_sent": sms_sent,
        "sms_failed": sms_failed,

        "apartment_performance": apartment_performance(),
    }

    return render(request, "dashboard/md.html", context)


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
        rents = Rent.objects.filter(house__apartment=apartment)

        total = rents.aggregate(total=Sum("amount"))["total"] or 0
        paid = rents.filter(paid=True).aggregate(total=Sum("amount"))["total"] or 0
        unpaid = rents.filter(paid=False).aggregate(total=Sum("amount"))["total"] or 0

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
            "vacant_count": vacant_houses.count(),
            "apartment_performance": apartment_performance(),
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
    total_rent = Rent.objects.aggregate(total=Sum("amount"))["total"] or 0
    unpaid_rent = Rent.objects.filter(paid=False).aggregate(total=Sum("amount"))["total"] or 0
    paid_rent = Rent.objects.filter(paid=True).aggregate(total=Sum("amount"))["total"] or 0

    total_houses = House.objects.count()
    occupied_houses = House.objects.filter(occupied=True).count()
    vacant_houses = House.objects.filter(occupied=False).count()

    total_money_in = MoneyIn.objects.aggregate(total=Sum("amount"))["total"] or 0
    total_money_out = MoneyOut.objects.aggregate(total=Sum("amount"))["total"] or 0
    water_balance = WaterBill.objects.aggregate(total=Sum("balance"))["total"] or 0
    deposits_held = Deposit.objects.filter(status="held").aggregate(total=Sum("amount"))["total"] or 0

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
            "total_money_in": total_money_in,
            "total_money_out": total_money_out,
            "water_balance": water_balance,
            "deposits_held": deposits_held,
            "apartment_performance": apartment_performance(),
        }
    )


def apartment_performance():
    apartments = Apartment.objects.all()
    performance = []

    for apartment in apartments:
        houses = House.objects.filter(apartment=apartment)

        total_houses = houses.count()
        occupied = houses.filter(occupied=True).count()
        vacant = houses.filter(occupied=False).count()

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
            occupancy = round((occupied / total_houses) * 100, 2)
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