from decimal import Decimal
from uuid import uuid4

from django.db import transaction

from .models import StockBalance, StockMovement


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
