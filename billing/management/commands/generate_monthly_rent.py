from django.core.management.base import BaseCommand
from rentals.models import Tenant, House, Rent


class Command(BaseCommand):
    help = "Generate monthly rent records for tenants"

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for tenant in Tenant.objects.all():
            house = House.objects.filter(apartment=tenant.apartment, occupied=True).first()

            if not house:
                skipped += 1
                continue

            exists = Rent.objects.filter(
                tenant=tenant,
                house=house,
                paid=False
            ).exists()

            if exists:
                skipped += 1
                continue

            Rent.objects.create(
                tenant=tenant,
                house=house,
                amount=house.rent_amount,
                paid=False
            )

            created += 1

        self.stdout.write(self.style.SUCCESS(f"Rent created: {created}, Skipped: {skipped}"))