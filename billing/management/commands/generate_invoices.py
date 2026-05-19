from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Invoice
from rentals.models import Rent
from services.models import WaterBill


class Command(BaseCommand):
    help = "Generate monthly invoices from unpaid rent and water bills"

    def handle(self, *args, **kwargs):

        today = timezone.now().date()

        created = 0
        skipped = 0

        rents = Rent.objects.filter(
            paid=False
        ).select_related(
            "tenant",
            "house",
            "house__apartment"
        )

        for rent in rents:

            water_total = 0

            water_bills = WaterBill.objects.filter(
                tenant=rent.tenant,
                paid=False
            )

            for bill in water_bills:
                water_total += bill.total_amount

            invoice_number = f"INV-{today.year}{today.month:02d}-{rent.id}"

            exists = Invoice.objects.filter(
                invoice_number=invoice_number
            ).exists()

            if exists:
                skipped += 1
                continue

            total_amount = rent.amount + water_total

            Invoice.objects.create(
                tenant=rent.tenant,
                apartment=rent.house.apartment,
                invoice_number=invoice_number,
                rent_amount=rent.amount,
                wifi_amount=0,
                water_amount=water_total,
                total_amount=total_amount,
                amount_paid=0,
                status="PENDING",
            )

            created += 1

        self.stdout.write(
            f"Monthly invoices generated. Created: {created}, Skipped: {skipped}"
        )
