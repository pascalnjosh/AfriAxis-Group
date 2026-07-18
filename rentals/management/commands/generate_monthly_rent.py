from datetime import date

from django.core.management.base import BaseCommand

from ledger.models import TenantLedger
from rentals.models import House, Rent


class Command(BaseCommand):
    help = "Generate monthly rent for all occupied houses"

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--month", type=int, required=True)

    def handle(self, *args, **options):
        year = options["year"]
        month = options["month"]

        billing_month = date(year, month, 1)
        due_date = billing_month

        created = 0
        skipped = 0

        houses = House.objects.filter(
            occupied=True,
            tenant__isnull=False,
        ).select_related(
            "tenant",
            "apartment",
        )

        for house in houses:

            exists = Rent.objects.filter(
                house=house,
                billing_month=billing_month,
            ).exists()

            if exists:
                skipped += 1
                continue

            rent = Rent.objects.create(
                tenant=house.tenant,
                house=house,
                amount=house.rent_amount,
                amount_paid=0,
                balance=house.rent_amount,
                paid=False,
                billing_month=billing_month,
                due_date=due_date,
            )

            TenantLedger.objects.create(
                tenant=house.tenant,
                rent=rent,
                entry_type="rent",
                description=f"Monthly Rent {billing_month:%B %Y}",
                debit=house.rent_amount,
                credit=0,
                balance=house.rent_amount,
                entry_date=billing_month,
            )

            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Monthly rent generated. Created: {created}, Skipped: {skipped}"
            )
        )