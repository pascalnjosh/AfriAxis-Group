from django.core.management.base import BaseCommand
from django.db.models import Sum
from rentals.models import Apartment, Rent


class Command(BaseCommand):
    help = "Show monthly rent summary by apartment"

    def handle(self, *args, **kwargs):
        apartments = Apartment.objects.all().order_by("name")

        self.stdout.write("")
        self.stdout.write("AFRIAXIS MONTHLY RENT REPORT")
        self.stdout.write("--------------------------------")

        grand_total = 0
        grand_unpaid = 0
        grand_paid = 0

        for apartment in apartments:
            rents = Rent.objects.filter(
                house__apartment=apartment
            )

            total = rents.aggregate(
                total=Sum("amount")
            )["total"] or 0

            unpaid = rents.filter(
                paid=False
            ).aggregate(
                total=Sum("amount")
            )["total"] or 0

            paid = rents.filter(
                paid=True
            ).aggregate(
                total=Sum("amount")
            )["total"] or 0

            grand_total += total
            grand_unpaid += unpaid
            grand_paid += paid

            self.stdout.write("")
            self.stdout.write(f"Apartment: {apartment.name}")
            self.stdout.write(f"Total Rent: KES {total}")
            self.stdout.write(f"Paid: KES {paid}")
            self.stdout.write(f"Unpaid: KES {unpaid}")

        self.stdout.write("")
        self.stdout.write("--------------------------------")
        self.stdout.write(f"GRAND TOTAL: KES {grand_total}")
        self.stdout.write(f"TOTAL PAID: KES {grand_paid}")
        self.stdout.write(f"TOTAL UNPAID: KES {grand_unpaid}")
