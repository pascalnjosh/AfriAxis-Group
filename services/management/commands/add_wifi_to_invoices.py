from django.core.management.base import BaseCommand

from billing.models import Invoice
from services.models import WifiCustomer


class Command(BaseCommand):
    help = "Add active WiFi package charges to existing tenant invoices"

    def handle(self, *args, **kwargs):

        updated = 0
        skipped = 0

        customers = WifiCustomer.objects.select_related(
            "package"
        )

        for customer in customers:

            if not customer.package:
                skipped += 1
                continue

            invoice = Invoice.objects.filter(
                tenant__name=customer.name,
                status="PENDING"
            ).order_by("-created_at").first()

            if not invoice:
                skipped += 1
                continue

            if invoice.wifi_amount and invoice.wifi_amount > 0:
                skipped += 1
                continue

            invoice.wifi_amount = customer.package.price
            invoice.total_amount = (
                invoice.rent_amount
                + invoice.water_amount
                + invoice.wifi_amount
            )

            invoice.save()

            updated += 1

        self.stdout.write(
            f"WiFi invoice update complete. Updated: {updated}, Skipped: {skipped}"
        )
