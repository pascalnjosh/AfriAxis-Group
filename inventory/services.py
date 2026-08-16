from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction

from accounting.models import JournalEntry
from accounting.posting import create_journal_entry

from .models import (
    StockAdjustment,
    StockBalance,
    StockMovement,
)


INWARD_MOVEMENTS = {
    "OPENING",
    "PURCHASE",
    "RECEIPT",
    "TRANSFER_IN",
    "ADJUSTMENT_IN",
    "CUSTOMER_RETURN",
}

OUTWARD_MOVEMENTS = {
    "SALE",
    "ISSUE",
    "TRANSFER_OUT",
    "ADJUSTMENT_OUT",
    "SUPPLIER_RETURN",
}


def _movement_number():
    return f"STK-{uuid4().hex[:12].upper()}"


@transaction.atomic
def post_stock_movement(
    *,
    movement_type,
    product,
    warehouse,
    location,
    quantity,
    unit_cost=Decimal("0.00"),
    batch=None,
    reference="",
    remarks="",
    created_by=None,
):
    quantity = Decimal(str(quantity))
    unit_cost = Decimal(str(unit_cost))

    if movement_type not in INWARD_MOVEMENTS | OUTWARD_MOVEMENTS:
        raise ValueError("Invalid stock movement type.")

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    if location.warehouse_id != warehouse.id:
        raise ValueError(
            "Storage location does not belong to the selected warehouse."
        )

    if batch and batch.product_id != product.id:
        raise ValueError(
            "Selected batch does not belong to the selected product."
        )

    balance, _ = (
        StockBalance.objects
        .select_for_update()
        .get_or_create(
            warehouse=warehouse,
            location=location,
            product=product,
            batch=batch,
            defaults={
                "quantity": Decimal("0.000"),
                "average_cost": Decimal("0.00"),
            },
        )
    )

    if movement_type in INWARD_MOVEMENTS:
        old_quantity = balance.quantity
        new_quantity = old_quantity + quantity

        if new_quantity > 0:
            old_value = old_quantity * balance.average_cost
            incoming_value = quantity * unit_cost

            balance.average_cost = (
                old_value + incoming_value
            ) / new_quantity

        balance.quantity = new_quantity

    else:
        if balance.quantity < quantity:
            raise ValueError(
                (
                    f"Insufficient stock for {product.product_code}. "
                    f"Available: {balance.quantity}, "
                    f"Required: {quantity}."
                )
            )

        unit_cost = balance.average_cost
        balance.quantity -= quantity

    balance.save(
        update_fields=[
            "quantity",
            "average_cost",
            "updated_at",
        ]
    )

    movement = StockMovement.objects.create(
        movement_number=_movement_number(),
        movement_type=movement_type,
        product=product,
        warehouse=warehouse,
        location=location,
        batch=batch,
        quantity=quantity,
        unit_cost=unit_cost,
        reference=str(reference).strip(),
        remarks=str(remarks).strip(),
        created_by=created_by,
    )

    if batch:
        batch.quantity_available = sum(
            stock.quantity
            for stock in batch.stock_balances.all()
        )

        batch.save(
            update_fields=[
                "quantity_available",
            ]
        )

    return movement, balance

@transaction.atomic
def post_stock_adjustment(adjustment, user=None):
    adjustment = (
        StockAdjustment.objects
        .select_for_update()
        .prefetch_related("lines")
        .get(pk=adjustment.pk)
    )

    if adjustment.status == "POSTED":
        raise ValidationError(
            "This stock adjustment has already been posted."
        )

    if adjustment.status != "APPROVED":
        raise ValidationError(
            "Only approved stock adjustments can be posted."
        )

    reference = f"STKADJ-{adjustment.adjustment_number}"

    if JournalEntry.objects.filter(
        company=adjustment.warehouse.company,
        reference=reference,
        status="POSTED",
    ).exists():
        raise ValidationError(
            "A journal already exists for this adjustment."
        )

    total_loss = Decimal("0.00")
    total_gain = Decimal("0.00")

    adjustment_lines = list(
        adjustment.lines.select_related(
            "location",
            "product",
            "batch",
        )
    )

    if not adjustment_lines:
        raise ValidationError(
            "The stock adjustment contains no lines."
        )

    for line in adjustment_lines:
        variance = Decimal(str(line.variance))

        if variance == Decimal("0.000"):
            continue

        if line.location.warehouse_id != adjustment.warehouse_id:
            raise ValidationError(
                (
                    f"Location {line.location} does not belong "
                    f"to warehouse {adjustment.warehouse}."
                )
            )

        if variance > 0:
            movement, balance = post_stock_movement(
                movement_type="ADJUSTMENT_IN",
                product=line.product,
                warehouse=adjustment.warehouse,
                location=line.location,
                quantity=variance,
                unit_cost=line.unit_cost,
                batch=line.batch,
                reference=adjustment.adjustment_number,
                remarks=adjustment.reason,
                created_by=user,
            )

            total_gain += movement.quantity * movement.unit_cost

        else:
            movement, balance = post_stock_movement(
                movement_type="ADJUSTMENT_OUT",
                product=line.product,
                warehouse=adjustment.warehouse,
                location=line.location,
                quantity=abs(variance),
                unit_cost=line.unit_cost,
                batch=line.batch,
                reference=adjustment.adjustment_number,
                remarks=adjustment.reason,
                created_by=user,
            )

            total_loss += movement.quantity * movement.unit_cost

    if total_gain > Decimal("0.00"):
        raise ValidationError(
            (
                "Positive stock adjustments require an Inventory "
                "Adjustment Gain account. Create that account before "
                "posting inventory gains."
            )
        )

    if total_loss == Decimal("0.00"):
        raise ValidationError(
            "This adjustment has no non-zero stock variances."
        )

    create_journal_entry(
        company=adjustment.warehouse.company,
        reference=reference,
        description=(
            f"Stock adjustment {adjustment.adjustment_number}: "
            f"{adjustment.reason}"
        ),
        user=user,
        auto_post=True,
        lines=[
            {
                "account_code": "6000",
                "debit": total_loss,
                "credit": Decimal("0.00"),
                "description": "Inventory adjustment loss",
            },
            {
                "account_code": "1200",
                "debit": Decimal("0.00"),
                "credit": total_loss,
                "description": "Inventory reduction",
            },
        ],
    )

    adjustment.status = "POSTED"
    adjustment.save(
        update_fields=[
            "status",
        ]
    )

    return adjustment
