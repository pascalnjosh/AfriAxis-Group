from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from billing.models import Invoice, InvoiceLine
from rentals.models import Rent, Tenant
from services.models import WifiCustomer
from water.models import WaterBill


class Command(BaseCommand):
    help = "Generate itemized monthly invoices for all tenants"

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        month_code = today.strftime("%Y%m")
        billing_month_label = today.strftime("%B %Y")

        created = 0
        skipped = 0
        empty = 0

        tenants = (
            Tenant.objects
            .select_related("apartment")
            .order_by("name")
        )

        for tenant in tenants:
            invoice_number = f"AFX-{month_code}-{tenant.id}"

            if Invoice.objects.filter(
                invoice_number=invoice_number
            ).exists():
                skipped += 1
                continue

            rent = (
                Rent.objects
                .filter(
                    tenant=tenant,
                    billing_month__year=today.year,
                    billing_month__month=today.month,
                )
                .order_by("-billing_month", "-created_at")
                .first()
            )

            rent_amount = (
                Decimal(rent.balance)
                if rent and rent.balance > 0
                else Decimal("0.00")
            )

            wifi_customer = (
                WifiCustomer.objects
                .select_related("package")
                .filter(phone=tenant.phone)
                .first()
            )

            wifi_amount = (
                Decimal(wifi_customer.package.price)
                if wifi_customer and wifi_customer.package
                else Decimal("0.00")
            )

            water_bill = (
                WaterBill.objects
                .filter(
                    tenant=tenant,
                    billing_month__iexact=billing_month_label,
                )
                .exclude(status="paid")
                .order_by("-created_at")
                .first()
            )

            water_amount = (
                Decimal(water_bill.balance)
                if water_bill and water_bill.balance > 0
                else Decimal("0.00")
            )

            if (
                rent_amount <= 0
                and wifi_amount <= 0
                and water_amount <= 0
            ):
                empty += 1
                continue

            invoice = Invoice.objects.create(
                tenant=tenant,
                apartment=tenant.apartment,
                invoice_number=invoice_number,
                invoice_type="RENTAL",
                customer_name=tenant.name,
                customer_phone=tenant.phone,
                invoice_date=today,
                due_date=rent.due_date if rent else None,
                currency="KES",
                rent_amount=rent_amount,
                wifi_amount=wifi_amount,
                water_amount=water_amount,
                subtotal=Decimal("0.00"),
                total_amount=Decimal("0.00"),
                amount_paid=Decimal("0.00"),
                status="PENDING",
                notes=f"Monthly rental invoice for {billing_month_label}",
            )

            if rent_amount > 0:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    item_code="RENT",
                    description=f"Monthly Rent - {billing_month_label}",
                    quantity=Decimal("1.00"),
                    unit="MONTH",
                    unit_price=rent_amount,
                    discount_rate=Decimal("0.00"),
                    tax_rate=Decimal("0.00"),
                )

            if water_amount > 0:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    item_code="WATER",
                    description=f"Water Bill - {billing_month_label}",
                    quantity=Decimal("1.00"),
                    unit="BILL",
                    unit_price=water_amount,
                    discount_rate=Decimal("0.00"),
                    tax_rate=Decimal("0.00"),
                )

            if wifi_amount > 0:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    item_code="WIFI",
                    description=f"Wi-Fi Subscription - {billing_month_label}",
                    quantity=Decimal("1.00"),
                    unit="MONTH",
                    unit_price=wifi_amount,
                    discount_rate=Decimal("0.00"),
                    tax_rate=Decimal("0.00"),
                )

            invoice.calculate_totals()
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created: {created}, "
                f"Skipped existing: {skipped}, "
                f"Skipped without charges: {empty}"
            )
        )
