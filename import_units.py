import os
import django
import pandas as pd
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from rentals.models import Apartment, House

FILES = [
    ("BLUEVALLEY UNITS.xlsx", "Blue Valley"),
    ("GULF UNITS.xlsx", "Gulf"),
    ("EASTWARD UNITS.xlsx", "Eastwards"),
    ("MUTHAIGA UNITS.xlsx", "Muthaiga"),
]

UNIT_COLUMNS = ["Unit", "UNIT", "House", "HOUSE", "House Number", "Unit Number", "Room", "ROOM"]
RENT_COLUMNS = ["Rent", "RENT", "Amount", "AMOUNT", "Rent Amount", "rent_amount"]

for file_name, apartment_name in FILES:
    if not os.path.exists(file_name):
        print(f"Missing file: {file_name}")
        continue

    apartment = Apartment.objects.filter(name=apartment_name).first()
    if not apartment:
        print(f"Missing apartment: {apartment_name}")
        continue

    df = pd.read_excel(file_name)
    print(f"\nProcessing {file_name}")
    print("Columns:", list(df.columns))

    created = 0
    skipped = 0

    for _, row in df.iterrows():
        unit = None
        rent = Decimal("8000.00")

        for col in UNIT_COLUMNS:
            if col in df.columns and pd.notna(row.get(col)):
                unit = str(row.get(col)).strip()
                break

        if not unit:
            first_value = str(row.iloc[0]).strip()
            if first_value and first_value.lower() != "nan":
                unit = first_value

        for col in RENT_COLUMNS:
            if col in df.columns and pd.notna(row.get(col)):
                rent = Decimal(str(row.get(col)))
                break

        if not unit or unit.lower() in ["nan", "none", "unit", "house"]:
            skipped += 1
            continue

        house, was_created = House.objects.get_or_create(
            apartment=apartment,
            house_number=unit,
            defaults={
                "rent_amount": rent,
                "occupied": False,
            }
        )

        if was_created:
            created += 1
        else:
            skipped += 1

    print(f"{apartment_name}: created={created}, skipped={skipped}")

print("\nDONE")
