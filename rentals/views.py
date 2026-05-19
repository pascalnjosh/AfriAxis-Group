from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .models import Tenant, House, Rent


def move_out_tenant(request, tenant_id):

    tenant = get_object_or_404(
        Tenant,
        id=tenant_id
    )

    house = House.objects.filter(
        apartment=tenant.apartment,
        occupied=True
    ).first()

    if house:
        house.occupied = False
        house.save()

    tenant.delete()

    return redirect("/dashboard/tenants/")


def assign_tenant(request, house_id):

    house = get_object_or_404(
        House,
        id=house_id
    )

    if request.method == "POST":

        name = request.POST.get("name")
        phone = request.POST.get("phone")

        tenant = Tenant.objects.create(
            name=name,
            phone=phone,
            apartment=house.apartment
        )

        house.occupied = True
        house.save()

        Rent.objects.create(
            tenant=tenant,
            house=house,
            amount=house.rent_amount,
            paid=False,
            due_date=timezone.now().date()
        )

        return redirect("/dashboard/tenants/")

    return render(
        request,
        "rentals/assign_tenant.html",
        {
            "house": house
        }
    )
