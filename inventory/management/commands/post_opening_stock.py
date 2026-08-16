from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import (
    InventoryBatch,
    StorageLocation,
    Warehouse,
)
from inventory.services import post_stock_movement
from sales.models import Product


class Command(BaseCommand):
    help = "Post controlled opening inventory using the stock movement engine."

    def add_arguments(self, parser):
        parser.add_argument(
            "--product",
            required=True,
            help="Product code, for example AGRI-001.",
        )
        parser.add_argument(
            "--warehouse",
            required=True,
            help="Warehouse code.",
        )
        parser.add_argument(
            "--location",
            required=True,
            help="Storage location code.",
        )
        parser.add_argument(
            "--quantity",
            required=True,
            help="Opening stock quantity.",
        )
        parser.add_argument(
            "--unit-cost",
            required=True,
            help="Opening stock unit cost.",
        )
        parser.add_argument(
            "--batch",
            default="",
            help="Optional batch number.",
        )
        parser.add_argument(
            "--manufacturing-date",
            default="",
            help="Optional date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--expiry-date",
            default="",
            help="Optional date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--reference",
            default="OPENING-STOCK",
        )
        parser.add_argument(
            "--remarks",
            default="Opening inventory balance",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and show the posting without changing data.",
        )

    def parse_decimal(self, value, field_name):
        try:
            amount = Decimal(str(value))
        except InvalidOperation as exc:
            raise CommandError(
                f"{field_name} must be a valid number."
            ) from exc

        if amount <= 0:
            raise CommandError(
                f"{field_name} must be greater than zero."
            )

        return amount

    def parse_date(self, value, field_name):
        if not value:
            return None

        try:
            return datetime.strptime(
                value,
                "%Y-%m-%d",
            ).date()
        except ValueError as exc:
            raise CommandError(
                f"{field_name} must use YYYY-MM-DD format."
            ) from exc

    def handle(self, *args, **options):
        product_code = options["product"].strip()
        warehouse_code = options["warehouse"].strip()
        location_code = options["location"].strip()
        batch_number = options["batch"].strip()

        quantity = self.parse_decimal(
            options["quantity"],
            "Quantity",
        )

        unit_cost = self.parse_decimal(
            options["unit_cost"],
            "Unit cost",
        )

        manufacturing_date = self.parse_date(
            options["manufacturing_date"],
            "Manufacturing date",
        )

        expiry_date = self.parse_date(
            options["expiry_date"],
            "Expiry date",
        )

        if (
            manufacturing_date
            and expiry_date
            and expiry_date < manufacturing_date
        ):
            raise CommandError(
                "Expiry date cannot be before manufacturing date."
            )

        try:
            product = Product.objects.get(
                product_code=product_code,
                active=True,
            )
        except Product.DoesNotExist as exc:
            raise CommandError(
                f"Active product '{product_code}' was not found."
            ) from exc
        except Product.MultipleObjectsReturned as exc:
            raise CommandError(
                "More than one active product uses this code. "
                "Specify a unique product code."
            ) from exc

        try:
            warehouse = Warehouse.objects.get(
                code=warehouse_code,
                active=True,
                company=product.company,
            )
        except Warehouse.DoesNotExist as exc:
            raise CommandError(
                f"Active warehouse '{warehouse_code}' was not found "
                "for the product company."
            ) from exc

        try:
            location = StorageLocation.objects.get(
                warehouse=warehouse,
                code=location_code,
                active=True,
            )
        except StorageLocation.DoesNotExist as exc:
            raise CommandError(
                f"Active location '{location_code}' was not found "
                f"in warehouse '{warehouse_code}'."
            ) from exc

        batch = None

        if batch_number:
            batch_defaults = {
                "manufacturing_date": manufacturing_date,
                "expiry_date": expiry_date,
                "quantity_received": Decimal("0.000"),
                "quantity_available": Decimal("0.000"),
                "cost_price": unit_cost,
                "active": True,
            }

            batch, created = InventoryBatch.objects.get_or_create(
                product=product,
                batch_number=batch_number,
                defaults=batch_defaults,
            )

            if not created:
                if (
                    manufacturing_date
                    and batch.manufacturing_date
                    and batch.manufacturing_date != manufacturing_date
                ):
                    raise CommandError(
                        "Existing batch has a different "
                        "manufacturing date."
                    )

                if (
                    expiry_date
                    and batch.expiry_date
                    and batch.expiry_date != expiry_date
                ):
                    raise CommandError(
                        "Existing batch has a different expiry date."
                    )

        duplicate_exists = product.stock_movements.filter(
            movement_type="OPENING",
            warehouse=warehouse,
            location=location,
            batch=batch,
            reference=options["reference"].strip(),
        ).exists()

        if duplicate_exists:
            raise CommandError(
                "An opening movement with the same product, warehouse, "
                "location, batch, and reference already exists."
            )

        total_value = quantity * unit_cost

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Opening Stock Posting"
            )
        )
        self.stdout.write("-" * 50)
        self.stdout.write(f"Product: {product}")
        self.stdout.write(f"Warehouse: {warehouse}")
        self.stdout.write(f"Location: {location}")
        self.stdout.write(f"Batch: {batch or '-'}")
        self.stdout.write(f"Quantity: {quantity:,.3f}")
        self.stdout.write(f"Unit cost: KES {unit_cost:,.2f}")
        self.stdout.write(f"Total value: KES {total_value:,.2f}")
        self.stdout.write(
            f"Reference: {options['reference'].strip()}"
        )

        if options["dry_run"]:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. No stock was posted."
                )
            )
            return

        with transaction.atomic():
            movement, balance = post_stock_movement(
                movement_type="OPENING",
                product=product,
                warehouse=warehouse,
                location=location,
                quantity=quantity,
                unit_cost=unit_cost,
                batch=batch,
                reference=options["reference"],
                remarks=options["remarks"],
            )

            if batch:
                batch.quantity_received += quantity
                batch.cost_price = unit_cost

                if manufacturing_date:
                    batch.manufacturing_date = manufacturing_date

                if expiry_date:
                    batch.expiry_date = expiry_date

                batch.save(
                    update_fields=[
                        "quantity_received",
                        "quantity_available",
                        "cost_price",
                        "manufacturing_date",
                        "expiry_date",
                    ]
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Opening stock posted successfully: "
                f"{movement.movement_number}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"New balance: {balance.quantity:,.3f} units"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Average cost: KES {balance.average_cost:,.2f}"
            )
        )
