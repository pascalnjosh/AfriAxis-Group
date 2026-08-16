from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import JournalEntry
from accounting.posting import create_journal_entry
from inventory.models import InventoryBatch, StockBalance
from inventory.services import post_stock_movement

from .models import ProductionOrder


@transaction.atomic
def complete_production_order(production_order, user=None):
    order = (
        ProductionOrder.objects
        .select_for_update()
        .select_related(
            "company",
            "bom",
            "bom__finished_product",
            "warehouse",
            "raw_material_location",
            "finished_goods_location",
        )
        .prefetch_related(
            "materials",
            "materials__component",
        )
        .get(pk=production_order.pk)
    )

    if order.status == "COMPLETED":
        raise ValidationError(
            "This production order has already been completed."
        )

    if order.status == "CANCELLED":
        raise ValidationError(
            "A cancelled production order cannot be completed."
        )

    if order.status not in (
        "RELEASED",
        "IN_PROGRESS",
    ):
        raise ValidationError(
            "Only released or in-progress production orders "
            "can be completed."
        )

    if order.bom.status != "ACTIVE":
        raise ValidationError(
            "The selected bill of materials is not active."
        )

    if order.bom.company_id != order.company_id:
        raise ValidationError(
            "The BOM belongs to another company."
        )

    if order.warehouse.company_id != order.company_id:
        raise ValidationError(
            "The warehouse belongs to another company."
        )

    if (
        order.raw_material_location.warehouse_id
        != order.warehouse_id
    ):
        raise ValidationError(
            "The raw material location does not belong "
            "to the production warehouse."
        )

    if (
        order.finished_goods_location.warehouse_id
        != order.warehouse_id
    ):
        raise ValidationError(
            "The finished goods location does not belong "
            "to the production warehouse."
        )

    planned_quantity = Decimal(
        str(order.planned_quantity)
    )

    if planned_quantity <= Decimal("0.000"):
        raise ValidationError(
            "Planned production quantity must be greater than zero."
        )

    materials = list(
        order.materials
        .select_related("component")
        .select_for_update()
    )

    if not materials:
        raise ValidationError(
            "The production order has no material lines."
        )

    reference = f"PROD-{order.order_number}"

    existing_journal = JournalEntry.objects.filter(
        company=order.company,
        reference=reference,
    ).first()

    if existing_journal:
        raise ValidationError(
            "A manufacturing journal already exists "
            "for this production order."
        )

    total_material_cost = Decimal("0.00")

    for material in materials:
        required_quantity = Decimal(
            str(material.required_quantity)
        )

        if required_quantity <= Decimal("0.000"):
            raise ValidationError(
                f"Required quantity for "
                f"{material.component} must be greater than zero."
            )

        available_balances = (
            StockBalance.objects
            .select_related("batch")
            .filter(
                product=material.component,
                warehouse=order.warehouse,
                location=order.raw_material_location,
                quantity__gt=Decimal("0.000"),
            )
            .order_by(
                "batch__manufacturing_date",
                "batch__created_at",
                "id",
            )
        )

        total_available = sum(
            (
                Decimal(str(stock.quantity))
                for stock in available_balances
            ),
            Decimal("0.000"),
        )

        if total_available < required_quantity:
            raise ValidationError(
                (
                    f"Insufficient stock for "
                    f"{material.component.product_code}. "
                    f"Available: {total_available}, "
                    f"Required: {required_quantity}."
                )
            )

        remaining_quantity = required_quantity
        material_total_cost = Decimal("0.00")
        material_consumed = Decimal("0.000")

        for stock in available_balances:
            if remaining_quantity <= Decimal("0.000"):
                break

            stock_quantity = Decimal(
                str(stock.quantity)
            )

            issue_quantity = min(
                stock_quantity,
                remaining_quantity,
            )

            movement, _balance = post_stock_movement(
                movement_type="ISSUE",
                product=material.component,
                warehouse=order.warehouse,
                location=order.raw_material_location,
                quantity=issue_quantity,
                batch=stock.batch,
                reference=order.order_number,
                remarks=(
                    f"Raw material consumption for production "
                    f"order {order.order_number}"
                ),
                created_by=user,
            )

            movement_cost = (
                Decimal(str(movement.quantity))
                * Decimal(str(movement.unit_cost))
            )

            material_total_cost += movement_cost
            material_consumed += Decimal(
                str(movement.quantity)
            )
            remaining_quantity -= Decimal(
                str(movement.quantity)
            )

        if material_consumed != required_quantity:
            raise ValidationError(
                (
                    f"Material issue mismatch for "
                    f"{material.component.product_code}. "
                    f"Required: {required_quantity}, "
                    f"Issued: {material_consumed}."
                )
            )

        material.consumed_quantity = material_consumed
        material.unit_cost = (
            material_total_cost / material_consumed
        )

        material.save(
            update_fields=[
                "consumed_quantity",
                "unit_cost",
            ]
        )

        total_material_cost += material_total_cost

    if total_material_cost <= Decimal("0.00"):
        raise ValidationError(
            "The production order has no material cost."
        )

    finished_unit_cost = (
        total_material_cost / planned_quantity
    )

    product_prefix = (
        order.bom.finished_product.product_code
        .split("-")[0]
        .upper()
    )

    order_suffix = (
        order.order_number
        .split("-")[-1]
        .upper()
    )

    batch_number = (
        f"{product_prefix}-PO-{order_suffix}"
    )

    finished_batch, batch_created = (
        InventoryBatch.objects.get_or_create(
            product=order.bom.finished_product,
            batch_number=batch_number,
            defaults={
                "manufacturing_date": timezone.localdate(),
                "quantity_received": planned_quantity,
                "quantity_available": Decimal("0.000"),
                "cost_price": finished_unit_cost,
                "active": True,
            },
        )
    )

    if not batch_created:
        raise ValidationError(
            f"Production batch {batch_number} already exists."
        )

    post_stock_movement(
        movement_type="RECEIPT",
        product=order.bom.finished_product,
        warehouse=order.warehouse,
        location=order.finished_goods_location,
        quantity=planned_quantity,
        unit_cost=finished_unit_cost,
        batch=finished_batch,
        reference=order.order_number,
        remarks=(
            f"Finished goods receipt for production "
            f"order {order.order_number}"
        ),
        created_by=user,
    )

    create_journal_entry(
        company=order.company,
        currency=order.bom.finished_product.currency,
        entry_date=timezone.localdate(),
        reference=reference,
        description=(
            f"Manufacturing completion for "
            f"{order.order_number}"
        ),
        lines=[
            {
                "account_code": "1220",
                "debit": total_material_cost,
                "description": (
                    f"Finished goods produced under "
                    f"{order.order_number}"
                ),
            },
            {
                "account_code": "1210",
                "credit": total_material_cost,
                "description": (
                    f"Raw materials consumed under "
                    f"{order.order_number}"
                ),
            },
        ],
        user=user,
        auto_post=True,
    )

    order.produced_quantity = planned_quantity
    order.status = "COMPLETED"
    order.completed_at = timezone.now()

    if order.actual_start_at is None:
        order.actual_start_at = timezone.now()

    order.save(
        update_fields=[
            "produced_quantity",
            "status",
            "actual_start_at",
            "completed_at",
        ]
    )

    return order




