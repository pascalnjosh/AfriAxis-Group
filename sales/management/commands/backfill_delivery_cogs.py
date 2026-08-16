from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounting.models import JournalEntry
from accounting.posting import create_journal_entry
from inventory.models import StockBalance, StockMovement
from sales.models import DeliveryNote


class Command(BaseCommand):
    help = (
        "Backfill unit cost and COGS journal for a previously posted "
        "delivery note without changing stock quantity."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delivery",
            required=True,
            help="Delivery note number, for example DN-000001.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        delivery_number = options["delivery"].strip()
        dry_run = options["dry_run"]

        try:
            delivery = (
                DeliveryNote.objects
                .select_for_update()
                .select_related(
                    "sales_order",
                    "sales_order__company",
                    "sales_order__currency",
                    "warehouse",
                )
                .get(delivery_number=delivery_number)
            )
        except DeliveryNote.DoesNotExist as exc:
            raise CommandError(
                f"Delivery note {delivery_number} was not found."
            ) from exc

        if delivery.status != "POSTED":
            raise CommandError(
                "Only previously posted delivery notes can be backfilled."
            )

        journal_reference = f"DELIVERY-{delivery.delivery_number}"

        if JournalEntry.objects.filter(
            company=delivery.sales_order.company,
            reference=journal_reference,
        ).exists():
            raise CommandError(
                "A COGS journal already exists for this delivery note."
            )

        movements = list(
            StockMovement.objects
            .select_for_update()
            .select_related(
                "product",
                "warehouse",
                "location",
                "batch",
            )
            .filter(
                movement_type="SALE",
                reference=delivery.delivery_number,
            )
            .order_by("id")
        )

        if not movements:
            raise CommandError(
                "No SALE stock movements were found for this delivery note."
            )

        total_cost = Decimal("0.00")
        movement_updates = []

        for movement in movements:
            if movement.unit_cost > Decimal("0.00"):
                unit_cost = movement.unit_cost
            else:
                balance = (
                    StockBalance.objects
                    .filter(
                        product=movement.product,
                        warehouse=movement.warehouse,
                        location=movement.location,
                        batch=movement.batch,
                    )
                    .first()
                )

                if balance is None:
                    raise CommandError(
                        "No stock balance was found for "
                        f"{movement.product.product_code} at "
                        f"{movement.location}."
                    )

                if balance.average_cost <= Decimal("0.00"):
                    raise CommandError(
                        "The stock balance has no valid average cost for "
                        f"{movement.product.product_code}."
                    )

                unit_cost = balance.average_cost

            movement_cost = movement.quantity * unit_cost
            total_cost += movement_cost

            movement_updates.append(
                {
                    "movement": movement,
                    "unit_cost": unit_cost,
                    "movement_cost": movement_cost,
                }
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"Backfill delivery: {delivery.delivery_number}"
            )
        )

        for row in movement_updates:
            self.stdout.write(
                f"{row['movement'].product.product_code}: "
                f"{row['movement'].quantity:,.3f} × "
                f"KES {row['unit_cost']:,.2f} = "
                f"KES {row['movement_cost']:,.2f}"
            )

        self.stdout.write(
            f"Total COGS: KES {total_cost:,.2f}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. No records were changed."
                )
            )
            transaction.set_rollback(True)
            return

        for row in movement_updates:
            movement = row["movement"]
            movement.unit_cost = row["unit_cost"]
            movement.save(update_fields=["unit_cost"])

        create_journal_entry(
            company=delivery.sales_order.company,
            currency=delivery.sales_order.currency,
            entry_date=delivery.delivery_date,
            reference=journal_reference,
            description=(
                f"Backfilled cost of goods sold for "
                f"{delivery.delivery_number}"
            ),
            lines=[
                {
                    "account_code": "5000",
                    "debit": total_cost,
                    "description": (
                        f"COGS for delivery "
                        f"{delivery.delivery_number}"
                    ),
                },
                {
                    "account_code": "1200",
                    "credit": total_cost,
                    "description": (
                        f"Inventory issued on delivery "
                        f"{delivery.delivery_number}"
                    ),
                },
            ],
            auto_post=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Historical delivery cost and COGS journal "
                "backfilled successfully."
            )
        )
