from datetime import date

from accounts.decorators import (
    audit_required,
    finance_required,
    get_user_company_ids,
)

from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .models import Apartment, Tenant, House, Rent


def _allowed_company_ids(request):
    """
    Return the active company IDs accessible to the current user.

    None means unrestricted access for a superuser.
    """
    return get_user_company_ids(request.user)


def _apartments_for_user(request):
    qs = Apartment.objects.all()

    company_ids = _allowed_company_ids(request)

    if company_ids is not None:
        qs = qs.filter(company_id__in=company_ids)

    return qs


def _tenants_for_user(request):
    qs = Tenant.objects.select_related("apartment")

    company_ids = _allowed_company_ids(request)

    if company_ids is not None:
        qs = qs.filter(apartment__company_id__in=company_ids)

    return qs


def _houses_for_user(request):
    qs = House.objects.select_related(
        "apartment",
        "tenant",
    )

    company_ids = _allowed_company_ids(request)

    if company_ids is not None:
        qs = qs.filter(apartment__company_id__in=company_ids)

    return qs


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


@finance_required
def move_out_tenant(request, tenant_id):
    tenant = get_object_or_404(
        _tenants_for_user(request),
        id=tenant_id,
    )

    house = (
        _houses_for_user(request)
        .filter(
            tenant=tenant,
            occupied=True,
        )
        .first()
    )

    if house:
        house.occupied = False
        house.tenant = None
        house.save(
            update_fields=[
                "occupied",
                "tenant",
            ]
        )

    tenant.delete()

    return redirect("/dashboard/tenants/")


@finance_required
def assign_tenant(request, house_id):
    house = get_object_or_404(
        _houses_for_user(request),
        id=house_id,
    )

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()

        if name:
            tenant = Tenant.objects.create(
                name=name,
                phone=phone,
                apartment=house.apartment,
            )

            house.tenant = tenant
            house.occupied = True
            house.save(
                update_fields=[
                    "tenant",
                    "occupied",
                ]
            )

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

    return render(
        request,
        "rentals/assign_tenant.html",
        {
            "house": house,
        },
    )


@audit_required
def rent_balance_report(request):
    apartments = (
        _apartments_for_user(request)
        .order_by("name")
    )

    base_rents = _rents_for_user(request)

    latest_rent = (
        base_rents
        .order_by("-billing_month")
        .first()
    )

    if latest_rent:
        default_month = latest_rent.billing_month.month
        default_year = latest_rent.billing_month.year
    else:
        today = date.today()
        default_month = today.month
        default_year = today.year

    apartment_id = request.GET.get("apartment")
    month = request.GET.get(
        "month",
        str(default_month),
    )
    year = request.GET.get(
        "year",
        str(default_year),
    )

    rents = base_rents

    if apartment_id:
        rents = rents.filter(
            house__apartment_id=apartment_id
        )

    if month:
        rents = rents.filter(
            billing_month__month=month
        )

    if year:
        rents = rents.filter(
            billing_month__year=year
        )

    rents = (
        rents
        .annotate(
            house_number_numeric=Cast(
                "house__house_number",
                IntegerField(),
            )
        )
        .order_by(
            "house__apartment__name",
            "house_number_numeric",
            "house__house_number",
        )
    )

    total_rent = sum(
        r.amount for r in rents
    )

    total_paid = sum(
        r.amount_paid for r in rents
    )

    total_balance = sum(
        r.balance for r in rents
    )

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
