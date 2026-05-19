from payments.models import Rent as PaymentRent
from rentals.models import Apartment, House, Tenant, Rent as RentalRent

created = 0

for old in PaymentRent.objects.all():

    name = old.tenant_name

    if "House" in name:

        parts = name.split(" House ")

        property_name = parts[0]

        house_number = "House " + parts[1]

    elif "Tenant" in name:

        property_name = "Oasis Business Center"

        house_number = name

    else:

        property_name = "General"

        house_number = name

    apartment, _ = Apartment.objects.get_or_create(
        name=property_name,
        defaults={
            "total_units": 0,
            "location": "",
            "active": True,
        }
    )

    house, _ = House.objects.get_or_create(
        apartment=apartment,
        house_number=house_number,
        defaults={
            "rent_amount": old.amount,
            "occupied": True,
        }
    )

    tenant, _ = Tenant.objects.get_or_create(
        name=name,
        defaults={
            "phone": "",
            "apartment": apartment,
        }
    )

    RentalRent.objects.get_or_create(
        tenant=tenant,
        house=house,
        amount=old.amount,
        due_date=old.due_date,
        defaults={
            "paid": old.paid,
        }
    )

    created += 1

print("Copied records:", created)
print("Apartments:", Apartment.objects.count())
print("Houses:", House.objects.count())
print("Tenants:", Tenant.objects.count())
print("Rental rents:", RentalRent.objects.count())
