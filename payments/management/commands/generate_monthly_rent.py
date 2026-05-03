from datetime import date
from django.core.management.base import BaseCommand
from payments.models import Rent


class Command(BaseCommand):
    help = "Generate monthly rent records"

    def handle(self, *args, **options):
        today = date.today()
        due_date = date(today.year, today.month, 1)

        rents = [
            ("Oasis Business Center Tenant 1", 155000),
            ("Oasis Business Center Tenant 2", 450000),
        ]

        created_count = 0

        for tenant_name, amount in rents:
            rent, created = Rent.objects.get_or_create(
                tenant_name=tenant_name,
                due_date=due_date,
                defaults={
                    "amount": amount,
                    "status": "PENDING",
                }
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created rent: {tenant_name} - {amount}"))

        self.stdout.write(self.style.SUCCESS(f"Monthly rent generation complete. Created: {created_count}"))
