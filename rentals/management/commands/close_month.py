from django.core.management.base import BaseCommand
from rentals.models import Rent
from datetime import date


class Command(BaseCommand):
    help = "Close a rent month"

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--month", type=int, required=True)

    def handle(self, *args, **options):
        year = options["year"]
        month = options["month"]

        rents = Rent.objects.filter(
            billing_month__year=year,
            billing_month__month=month,
        )

        count = rents.update(closed=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Closed {count} rent records."
            )
        )