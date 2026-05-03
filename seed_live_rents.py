import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from payments.models import Rent

data = [
    ("Oasis Business Center Tenant 2", 450000),
    ("Oasis Business Center Tenant 1", 155000),
    ("EASTWARD House 12 - BEDSITTER", 8000),
    ("GULF House 9 - ONE BEDROOM", 7500),
    ("MUTHAIGA House 1 - ONE BEDROOM", 7000),
]

for name, amount in data:
    Rent.objects.get_or_create(
        tenant_name=name,
        amount=amount,
        paid=False,
    )

print("Seeded successfully")