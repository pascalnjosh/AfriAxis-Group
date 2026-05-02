from datetime import datetime
from django.core.management.base import BaseCommand
from tenants.models import Tenant
from payments.models import Rent


class Command(BaseCommand):
    help = "Generate monthly rent for all active tenants"

    def handle(self, *args, **kwargs):
        current_month = datetime.now().strftime("%B")
        current_year = datetime.now().year

        tenants = Tenant.objects.filter(is_active=True)

        created_count = 0
        skipped_count = 0

        for tenant in tenants:
            if not tenant.unit:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(f"Skipped {tenant.full_name}: no unit assigned")
                )
                continue

            rent_amount = tenant.unit.rent_amount

            rent_obj, created = Rent.objects.get_or_create(
                tenant=tenant,
                month=current_month,
                year=current_year,
                defaults={
                    "amount": rent_amount,
                    "amount_paid": 0,
                    "balance": rent_amount,
                    "status": "UNPAID",
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created rent for {tenant.full_name} - {current_month} {current_year}"
                    )
                )
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped existing rent for {tenant.full_name} - {current_month} {current_year}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Done. Created: {created_count}"))
        self.stdout.write(self.style.WARNING(f"Skipped: {skipped_count}"))
