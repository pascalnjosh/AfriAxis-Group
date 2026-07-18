from django.core.management.base import BaseCommand
from rentals.models import Rent


class Command(BaseCommand):
    help = "Close all fully paid rent records"

    def handle(self, *args, **kwargs):
        rents = Rent.objects.filter(
            paid=True,
            closed=False,
        )

        count = rents.update(closed=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Closed {count} rent records."
            )
        )