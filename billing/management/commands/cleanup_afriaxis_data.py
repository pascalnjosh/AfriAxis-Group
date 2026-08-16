from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from billing.models import Invoice
from rentals.models import House, Rent


class Command(BaseCommand):
    help = (
        "Safely repair stale house occupancy and remove exact duplicate "
        "rental invoices. Runs as a dry-run unless --apply is supplied."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the changes. Without this flag, no data is changed.",
        )

        parser.add_argument(
            "--skip-occupancy",
            action="store_true",
            help="Do not repair house occupancy.",
        )

        parser.add_argument(
            "--skip-invoices",
            action="store_true",
            help="Do not inspect or remove duplicate invoices.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        skip_occupancy = options["skip_occupancy"]
        skip_invoices = options["skip_invoices"]

        mode = "APPLY" if apply_changes else "DRY RUN"

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"AfriAxis data cleanup mode: {mode}"
            )
        )
        self.stdout.write("")

        occupancy_ids = []
        duplicate_invoice_ids = []

        if not skip_occupancy:
            occupancy_ids = self.find_stale_occupied_houses()

        if not skip_invoices:
            duplicate_invoice_ids = self.find_duplicate_invoices()

        self.stdout.write("")
        self.stdout.write("Cleanup summary")
        self.stdout.write("-" * 50)
        self.stdout.write(
            f"Houses to mark vacant: {len(occupancy_ids)}"
        )
        self.stdout.write(
            f"Duplicate invoices to delete: "
            f"{len(duplicate_invoice_ids)}"
        )

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. No database records were changed."
                )
            )
            self.stdout.write(
                "Run again with --apply after reviewing the results."
            )
            return

        with transaction.atomic():
            if occupancy_ids:
                updated = House.objects.filter(
                    id__in=occupancy_ids,
                ).update(
                    occupied=False,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Marked {updated} houses as vacant."
                    )
                )

            if duplicate_invoice_ids:
                invoices = Invoice.objects.filter(
                    id__in=duplicate_invoice_ids,
                )

                protected = invoices.annotate(
                    payment_count=Count("invoicepayment")
                ).filter(
                    payment_count__gt=0,
                )

                if protected.exists():
                    protected_numbers = list(
                        protected.values_list(
                            "invoice_number",
                            flat=True,
                        )
                    )

                    raise RuntimeError(
                        "Cleanup stopped because invoices selected for "
                        f"deletion have payments: {protected_numbers}"
                    )

                deleted_count = invoices.count()
                invoices.delete()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deleted {deleted_count} exact duplicate invoices."
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "AfriAxis data cleanup completed successfully."
            )
        )

    def find_stale_occupied_houses(self):
        open_rent_house_ids = set(
            Rent.objects.filter(
                closed=False,
            ).values_list(
                "house_id",
                flat=True,
            )
        )

        candidates = House.objects.filter(
            occupied=True,
            tenant__isnull=True,
        ).select_related(
            "apartment",
        ).order_by(
            "apartment__name",
            "house_number",
        )

        stale_houses = [
            house
            for house in candidates
            if house.id not in open_rent_house_ids
        ]

        self.stdout.write("Occupancy repair")
        self.stdout.write("-" * 50)

        for house in stale_houses:
            apartment_name = (
                house.apartment.name
                if house.apartment
                else "No apartment"
            )

            self.stdout.write(
                f"VACANT: ID {house.id} | "
                f"{apartment_name} | {house.house_number}"
            )

        return [house.id for house in stale_houses]

    def find_duplicate_invoices(self):
        rental_invoices = (
            Invoice.objects
            .filter(
                invoice_type="RENTAL",
                tenant__isnull=False,
            )
            .annotate(
                payment_count=Count("invoicepayment"),
            )
            .order_by(
                "tenant_id",
                "invoice_date",
                "created_at",
                "id",
            )
        )

        grouped = defaultdict(list)

        for invoice in rental_invoices:
            signature = (
                invoice.tenant_id,
                invoice.invoice_date,
                invoice.invoice_type,
                Decimal(invoice.rent_amount),
                Decimal(invoice.wifi_amount),
                Decimal(invoice.water_amount),
                Decimal(invoice.discount_amount),
                Decimal(invoice.tax_amount),
                Decimal(invoice.total_amount),
            )

            grouped[signature].append(invoice)

        delete_ids = []

        self.stdout.write("")
        self.stdout.write("Exact duplicate invoice review")
        self.stdout.write("-" * 50)

        for signature, invoices in grouped.items():
            if len(invoices) <= 1:
                continue

            invoices_with_payments = [
                invoice
                for invoice in invoices
                if invoice.payment_count > 0
                or Decimal(invoice.amount_paid) > 0
            ]

            if invoices_with_payments:
                keeper = sorted(
                    invoices_with_payments,
                    key=lambda item: (
                        item.created_at,
                        item.id,
                    ),
                )[0]
            else:
                keeper = sorted(
                    invoices,
                    key=lambda item: (
                        item.created_at,
                        item.id,
                    ),
                )[0]

            removable = [
                invoice
                for invoice in invoices
                if invoice.id != keeper.id
                and invoice.payment_count == 0
                and Decimal(invoice.amount_paid) == 0
            ]

            if not removable:
                continue

            tenant_id = signature[0]
            invoice_date = signature[1]
            amount = signature[-1]

            self.stdout.write(
                f"GROUP: Tenant {tenant_id} | "
                f"{invoice_date} | KES {amount:,.2f}"
            )

            self.stdout.write(
                f"  KEEP: {keeper.id} - "
                f"{keeper.invoice_number} - "
                f"paid KES {keeper.amount_paid:,.2f}"
            )

            for invoice in removable:
                self.stdout.write(
                    f"  DELETE: {invoice.id} - "
                    f"{invoice.invoice_number} - "
                    f"paid KES {invoice.amount_paid:,.2f}"
                )

                delete_ids.append(invoice.id)

        return delete_ids
