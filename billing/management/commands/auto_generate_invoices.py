from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Invoice
from rentals.models import Tenant, Rent
from services.models import WaterBill, WifiCustomer


class Command(BaseCommand):

    help = "Automatically generate monthly ERP invoices"

    def handle(self, *args, **kwargs):

        today = timezone.now().date()
        month_code = today.strftime("%Y%m")

        created = 0
        skipped = 0

        tenants = Tenant.objects.select_related(
            "apartment"
        )

        for tenant in tenants:

            invoice_number = f"AFX-{month_code}-{tenant.id}"

            exists = Invoice.objects.filter(
                invoice_number=invoice_number
            ).exists()

            if exists:
                skipped += 1
                continue

            rent = (
                Rent.objects
                .filter(
                    tenant=tenant,
                    paid=False
                )
                .order_by("-due_date")
                .first()
            )

            rent_amount = (
                rent.amount
                if rent
                else Decimal("0.00")
            )

            wifi_customer = WifiCustomer.objects.filter(
                phone=tenant.phone
            ).select_related(
                "package"
            ).first()

            wifi_amount = Decimal("0.00")

            if (
                wifi_customer and
                wifi_customer.package
            ):
                wifi_amount = wifi_customer.package.price

            water_total = Decimal("0.00")

            water_bills = WaterBill.objects.filter(
                tenant=tenant,
                paid=False
            )

            for bill in water_bills:
                water_total += bill.total_amount

            total_amount = (
                rent_amount +
                wifi_amount +
                water_total
            )

            Invoice.objects.create(
                tenant=tenant,
                apartment=tenant.apartment,
                invoice_number=invoice_number,
                rent_amount=rent_amount,
                wifi_amount=wifi_amount,
                water_amount=water_total,
                total_amount=total_amount,
                amount_paid=Decimal("0.00"),
                status="PENDING",
            )

            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"ERP invoice automation complete. Created: {created}, Skipped: {skipped}"
            )
        )
