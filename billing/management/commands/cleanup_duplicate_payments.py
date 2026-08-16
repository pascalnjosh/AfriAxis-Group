from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import InvoicePayment


class Command(BaseCommand):
    help = (
        "Remove duplicate invoice-payment rows while retaining one "
        "payment per M-Pesa receipt. Dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply cleanup. Without this flag, no records change.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        apply_changes = options["apply"]

        payments = (
            InvoicePayment.objects
            .exclude(mpesa_receipt__isnull=True)
            .exclude(mpesa_receipt="")
            .select_related("invoice")
            .order_by(
                "mpesa_receipt",
                "paid_at",
                "id",
            )
        )

        groups = defaultdict(list)

        for payment in payments:
            groups[payment.mpesa_receipt].append(payment)

        delete_ids = []
        affected_invoice_ids = set()

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Invoice payment duplicate cleanup"
            )
        )
        self.stdout.write("-" * 60)

        for receipt, rows in groups.items():
            if len(rows) <= 1:
                continue

            # Keep the earliest payment record.
            keeper = rows[0]
            duplicates = rows[1:]

            self.stdout.write(
                f"Receipt: {receipt}"
            )
            self.stdout.write(
                f"  KEEP: ID {keeper.id} | "
                f"{keeper.invoice.invoice_number} | "
                f"KES {keeper.amount:,.2f} | "
                f"{keeper.paid_at}"
            )

            for duplicate in duplicates:
                self.stdout.write(
                    f"  DELETE: ID {duplicate.id} | "
                    f"{duplicate.invoice.invoice_number} | "
                    f"KES {duplicate.amount:,.2f} | "
                    f"{duplicate.paid_at}"
                )

                delete_ids.append(duplicate.id)
                affected_invoice_ids.add(
                    duplicate.invoice_id
                )

            affected_invoice_ids.add(
                keeper.invoice_id
            )

        self.stdout.write("")
        self.stdout.write(
            f"Duplicate payment rows to delete: "
            f"{len(delete_ids)}"
        )

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. No records were changed."
                )
            )
            transaction.set_rollback(True)
            return

        deleted = 0

        if delete_ids:
            deleted = InvoicePayment.objects.filter(
                id__in=delete_ids,
            ).count()

            InvoicePayment.objects.filter(
                id__in=delete_ids,
            ).delete()

        # Recalculate each affected invoice from the remaining
        # payment records.
        from billing.models import Invoice

        for invoice in Invoice.objects.filter(
            id__in=affected_invoice_ids,
        ):
            invoice.recalculate_status()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} duplicate payment rows."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Recalculated "
                f"{len(affected_invoice_ids)} invoice(s)."
            )
        )
