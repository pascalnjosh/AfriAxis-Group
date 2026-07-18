import pandas as pd

from django.core.management.base import BaseCommand
from rentals.models import Apartment, House, Tenant, Rent


FILES = [
    ("BLUEVALLEY.xlsx", "BLUEVALLEY"),
    ("EASTWARD.xlsx", "EASTWARD"),
    ("GULF.xlsx", "GULF"),
    ("MUTHAIGA.xlsx", "MUTHAIGA"),
]


class Command(BaseCommand):
    help = "Import real tenants from apartment Excel files"

    def handle(self, *args, **options):
        total_updated = 0

        for filename, apartment_name in FILES:
            self.stdout.write(f"\nReading {filename}...")

            apartment = Apartment.objects.filter(name__icontains=apartment_name).first()
            if not apartment:
                self.stdout.write(self.style.ERROR(f"Apartment not found: {apartment_name}"))
                continue

            df = pd.read_excel(filename, header=1)
            for _, row in df.iterrows():

                raw_house_no = row.get("HOUSE NO", "")
                try:
                    house_no = str(int(float(raw_house_no)))
                except Exception:
                    house_no = str(raw_house_no).strip()

                tenant_name = str(row.get("TENANT NAME", "")).strip()

                phone = str(
                    row.get("PHONE NO", row.get("PHONE  NO", ""))
                ).strip()

                rent_amount = row.get("PAYMENT AMOUNT", 0)

                if not house_no or tenant_name.lower() == "nan":
                    continue

                house = House.objects.filter(
                    apartment=apartment,
                    house_number__icontains=f"House {house_no}"
                ).first()

                if not house:
                    self.stdout.write(f"House not found: {apartment_name} {house_no}")
                    continue

                tenant = Tenant.objects.filter(
                    apartment=apartment,
                    name__icontains=tenant_name
                ).first()

                if not tenant:
                    tenant = Tenant.objects.create(
                        apartment=apartment,
                        name=tenant_name,
                        phone="" if phone.lower() == "nan" else phone,
                    )
                else:
                    tenant.name = tenant_name
                    tenant.phone = "" if phone.lower() == "nan" else phone
                    tenant.save()

                house.occupied = True

                try:
                    if pd.notna(rent_amount):
                        house.rent_amount = rent_amount
                except Exception:
                    pass

                house.save()

                total_updated += 1
           