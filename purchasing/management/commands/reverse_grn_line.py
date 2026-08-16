from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounting.models import JournalEntry
from accounting.posting import create_journal_entry
from inventory.models import InventoryBatch, StockMovement
from inventory.services import post_stock_movement
from purchasing.models import GoodsReceipt, GoodsReceiptLine


class Command(BaseCommand):
    help = (
        "Reverse one incorrect line from an already-posted goods receipt "
        "without deleting the historical GRN line."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--grn",
            required=True,
            help="Goods receipt number, for example 001.",
        )
        parser.add_argument(
            "--line-id",
            required=True,
            type=int,
            help="Incorrect GoodsReceiptLine database ID.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the correction without changing records.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        grn_number = options["grn"].strip()
        line_id = options["line_id"]
        dry_run = options["dry_run"]

        try:
            receipt = (
                GoodsReceipt.objects
                .select_for_update()
                .select_related(
                    "purchase_order",
                    "purchase_order__company",
                    "purchase_order__currency",
                    "warehouse",
                    "supplier",
                )
                .get(receipt_number=grn_number)
            )
        except GoodsReceipt.DoesNotExist as exc:
            raise CommandError(
                f"Goods receipt {grn_number} was not found."
            ) from exc

        if receipt.status != "POSTED":
            raise CommandError(
                "Only a posted goods receipt can be repaired."
            )

        try:
            line = (
                GoodsReceiptLine.objects
                .select_for_update()
                .select_related(
                    "product",
                    "location",
                    "purchase_order_line",
                )
                .get(
                    pk=line_id,
                    goods_receipt=receipt,
                )
            )
        except GoodsReceiptLine.DoesNotExist as exc:
            raise CommandError(
                f"Line {line_id} does not belong to GRN {grn_number}."
            ) from exc

        if not line.batch_number:
            raise CommandError(
                "The incorrect receipt line has no batch number."
            )

        try:
            batch = (
                InventoryBatch.objects
                .select_for_update()
                .get(
                    product=line.product,
                    batch_number=line.batch_number,
                )
            )
        except InventoryBatch.DoesNotExist as exc:
            raise CommandError(
                f"Batch {line.batch_number} was not found."
            ) from exc

        quantity = Decimal(str(line.quantity_received))
        unit_cost = Decimal(str(line.unit_cost))
        reversal_value = quantity * unit_cost

        movement_reference = (
            f"REV-GRN-{receipt.receipt_number}-LINE-{line.id}"
        )
        journal_reference = (
            f"REV-GRN-{receipt.receipt_number}-LINE-{line.id}"
        )

        existing_movement = StockMovement.objects.filter(
            reference=movement_reference,
            movement_type="ADJUSTMENT_OUT",
        ).first()

        existing_journal = JournalEntry.objects.filter(
            company=receipt.purchase_order.company,
            reference=journal_reference,
        ).first()

        if existing_movement or existing_journal:
            raise CommandError(
                "This GRN line has already been reversed."
            )

        purchase_movements = StockMovement.objects.filter(
            movement_type="PURCHASE",
            reference=receipt.receipt_number,
            product=line.product,
            warehouse=receipt.warehouse,
            location=line.location,
            batch=batch,
            quantity=quantity,
            unit_cost=unit_cost,
        )

        if purchase_movements.count() != 1:
            raise CommandError(
                "Expected exactly one matching PURCHASE movement for "
                f"GRN line {line.id}, but found "
                f"{purchase_movements.count()}."
            )

        balance = batch.stock_balances.filter(
            warehouse=receipt.warehouse,
            location=line.location,
            product=line.product,
        ).first()

        if balance is None:
            raise CommandError(
                "No stock balance exists for the incorrect batch."
            )

        if balance.quantity < quantity:
            raise CommandError(
                f"Cannot reverse {quantity} units. "
                f"Only {balance.quantity} units remain in the batch."
            )

        if batch.quantity_received < quantity:
            raise CommandError(
                "Batch quantity received is lower than the reversal quantity."
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"GRN repair: {receipt.receipt_number}"
            )
        )
        self.stdout.write("-" * 60)
        self.stdout.write(f"Incorrect line ID: {line.id}")
        self.stdout.write(f"Product: {line.product}")
        self.stdout.write(f"Batch: {batch.batch_number}")
        self.stdout.write(f"Location: {line.location}")
        self.stdout.write(f"Quantity to reverse: {quantity:,.3f}")
        self.stdout.write(f"Unit cost: KES {unit_cost:,.2f}")
        self.stdout.write(
            f"Inventory value to reverse: KES {reversal_value:,.2f}"
        )

        if dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. No records were changed."
                )
            )
            transaction.set_rollback(True)
            return

        movement, updated_balance = post_stock_movement(
            movement_type="ADJUSTMENT_OUT",
            product=line.product,
            warehouse=receipt.warehouse,
            location=line.location,
            quantity=quantity,
            batch=batch,
            reference=movement_reference,
            remarks=(
                f"Reverse incorrect GRN {receipt.receipt_number} "
                f"line {line.id}"
            ),
        )

        # The movement service recalculates quantity_available.
        batch.refresh_from_db()
        batch.quantity_received -= quantity

        if batch.quantity_received <= Decimal("0.000"):
            batch.quantity_received = Decimal("0.000")
            batch.active = False

        batch.save(
            update_fields=[
                "quantity_received",
                "active",
            ]
        )

        journal = create_journal_entry(
            company=receipt.purchase_order.company,
            currency=receipt.purchase_order.currency,
            entry_date=receipt.receipt_date,
            reference=journal_reference,
            description=(
                f"Reverse incorrect GRN {receipt.receipt_number} "
                f"line {line.id}"
            ),
            lines=[
                {
                    "account_code": "2050",
                    "debit": reversal_value,
                    "description": (
                        f"Reverse excess GRNI from "
                        f"GRN {receipt.receipt_number}"
                    ),
                },
                {
                    "account_code": "1200",
                    "credit": reversal_value,
                    "description": (
                        f"Reverse excess inventory from "
                        f"GRN {receipt.receipt_number}"
                    ),
                },
            ],
            auto_post=True,
        )

        audit_note = (
            f"\nCorrection: GRN line {line.id}, batch "
            f"{line.batch_number}, quantity {quantity}, "
            f"value KES {reversal_value} was reversed through "
            f"{movement.movement_number} and {journal.journal_number}."
        )

        receipt.notes = (
            f"{receipt.notes or ''}{audit_note}"
        ).strip()

        receipt.save(
            update_fields=["notes"]
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Reversal movement: {movement.movement_number}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Reversal journal: {journal.journal_number}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Remaining incorrect-batch stock: "
                f"{updated_balance.quantity:,.3f}"
            )
        )
