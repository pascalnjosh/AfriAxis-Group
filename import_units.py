import pandas as pd
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from payments.models import Rent
from django.utils import timezone

def import_excel(file_path):
    df = pd.read_excel(file_path)

    for _, row in df.iterrows():
        Rent.objects.create(
            tenant_name=str(row.get("Tenant Name", "Unknown")),
            amount=float(row.get("Rent Amount", 0)),
            paid=False,
            due_date=timezone.now()
        )

    print(f"Imported: {file_path}")

# FILES
files = [
    "MUTHAIGA UNITS(3).xlsx",
    "GULF UNITS(3).xlsx",
    "EASTWARD UNITS(2).xlsx",
    "BLUEVALLEY UNITS(2).xlsx"
]

for f in files:
    if os.path.exists(f):
        import_excel(f)