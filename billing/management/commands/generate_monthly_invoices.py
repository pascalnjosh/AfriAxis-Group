from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import Invoice, InvoiceLine
from rentals.models import Rent, Tenant
from services.models import WifiCustomer
from water.models import WaterBill


class Command(BaseCommand):
    help = "Safely generate itemized monthly invoices without duplicates."

    def add_arguments(self, parser):
        today = date.today()

        parser.add_argument(
            "--year",
            type=int,
            default=today.year,
        )
        parser.add_argument(
            "--month",
            type=int,
            default=today.month,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without creating invoices.",
        )

    def handle(self, *args, **options):
        year = options["year"]
        month = options["month"]
        dry_run = options["dry_run"]

        if month < 1 or month > 12:
            raise CommandError("Month must be between 1 and 12.")

        billing_date = date(year, month, 1)
        month_code = billing_date.strftime("%Y%m")
        month_label = billing_date.strftime("%B %Y")

        created = 0
        existing = 0
        empty = 0

        tenants = (
            Tenant.objects
            .filter(
                houses__occupied=True,
                houses__tenant__isnull=False,
            )
            .select_related("apartment")
            .distinct()
            .order_by("name", "id")
        )

        self.stdout.write(
            self.style.WARNING(
                f"Billing period: {month_label}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no invoices will be created."
                )
            )

        for tenant in tenants:
            invoice_number = (
                f"AFX-{month_code}-{tenant.id}"
            )

            duplicate_exists = Invoice.objects.filter(
                invoice_number=invoice_number,
            ).exists()

            if not duplicate_exists:
                duplicate_exists = Invoice.objects.filter(
                    tenant=tenant,
                    invoice_type="RENTAL",
                    invoice_date__year=year,
                    invoice_date__month=month,
                ).exists()

            if duplicate_exists:
                existing += 1
                self.stdout.write(
                    f"SKIP EXISTING: {tenant.name} "
                    f"({invoice_number})"
                )
                continue

            rent = (
                Rent.objects
                .filter(
                    tenant=tenant,
                    billing_month__year=year,
                    billing_month__month=month,
                )
                .order_by(
                    "-billing_month",
                    "-created_at",
                    "-id",
                )
                .first()
            )

            rent_amount = Decimal("0.00")

            if rent and rent.balance > 0:
                rent_amount = Decimal(rent.balance)

            wifi_customer = (
                WifiCustomer.objects
                .select_related("package")
                .filter(phone=tenant.phone)
                .first()
            )

            wifi_amount = Decimal("0.00")

            if (
                wifi_customer
                and wifi_customer.package
            ):
                wifi_amount = Decimal(
                    wifi_customer.package.price
                )

            water_bill = (
                WaterBill.objects
                .filter(
                    tenant=tenant,
                    billing_month__iexact=month_label,
                )
                .exclude(status="paid")
                .order_by("-created_at", "-id")
                .first()
            )

            water_amount = Decimal("0.00")

            if water_bill and water_bill.balance > 0:
                water_amount = Decimal(
                    water_bill.balance
                )

            if (
                rent_amount <= 0
                and wifi_amount <= 0
                and water_amount <= 0
            ):
                empty += 1
                self.stdout.write(
                    f"SKIP EMPTY: {tenant.name}"
                )
                continue

            expected_total = (
                rent_amount
                + wifi_amount
                + water_amount
            )

            if dry_run:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"WOULD CREATE: {invoice_number} | "
                        f"{tenant.name} | "
                        f"KES {expected_total:,.2f}"
                    )
                )
                continue

            with transaction.atomic():
                invoice = Invoice.objects.create(
                    tenant=tenant,
                    apartment=tenant.apartment,
                    invoice_number=invoice_number,
                    invoice_type="RENTAL",
                    customer_name=tenant.name,
                    customer_phone=tenant.phone,
                    invoice_date=billing_date,
                    due_date=(
                        rent.due_date
                        if rent
                        else billing_date
                    ),
                    currency="KES",
                    rent_amount=rent_amount,
                    wifi_amount=wifi_amount,
                    water_amount=water_amount,
                    subtotal=Decimal("0.00"),
                    total_amount=Decimal("0.00"),
                    amount_paid=Decimal("0.00"),
                    status="PENDING",
                    notes=(
                        f"Monthly rental invoice for "
                        f"{month_label}"
                    ),
                )

                if rent_amount > 0:
                    InvoiceLine.objects.create(
                        invoice=invoice,
                        item_code="RENT",
                        description=(
                            f"Monthly Rent - {month_label}"
                        ),
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
                        description=(
                            f"Water Bill - {month_label}"
                        ),
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
                        description=(
                            f"Wi-Fi Subscription - "
                            f"{month_label}"
                        ),
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
                    f"CREATED: {invoice_number} | "
                    f"{tenant.name} | "
                    f"KES {invoice.total_amount:,.2f}"
                )
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed. Created: {created}, "
                f"Existing: {existing}, "
                f"Empty: {empty}"
            )
        )
