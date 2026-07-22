from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.models import InventoryBatch
from inventory.services import post_stock_movement

from .models import GoodsReceipt, PurchaseOrder


@transaction.atomic
def post_goods_receipt(goods_receipt, user=None):
    receipt = (
        GoodsReceipt.objects
        .select_for_update()
        .select_related(
            "purchase_order",
            "warehouse",
        )
        .get(pk=goods_receipt.pk)
    )

    if receipt.status == "POSTED":
        raise ValidationError(
            "This goods receipt has already been posted."
        )

    if receipt.status == "CANCELLED":
        raise ValidationError(
            "A cancelled goods receipt cannot be posted."
        )

    if receipt.purchase_order.status == "CANCELLED":
        raise ValidationError(
            "The related purchase order is cancelled."
        )

    lines = list(
        receipt.lines
        .select_for_update()
        .select_related(
            "purchase_order_line",
            "product",
            "location",
        )
    )

    if not lines:
        raise ValidationError(
            "The goods receipt has no lines."
        )

    for line in lines:
        po_line = line.purchase_order_line

        if po_line.purchase_order_id != receipt.purchase_order_id:
            raise ValidationError(
                f"{line.product} does not belong to this purchase order."
            )

        if line.product_id != po_line.product_id:
            raise ValidationError(
                f"Product mismatch on receipt line {line.pk}."
            )

        if line.location.warehouse_id != receipt.warehouse_id:
            raise ValidationError(
                f"Location {line.location} does not belong to the warehouse."
            )

        outstanding = (
            po_line.quantity
            - po_line.quantity_received
        )

        if line.quantity_received <= Decimal("0.000"):
            raise ValidationError(
                f"Received quantity for {line.product} must be greater than zero."
            )

        if line.quantity_received > outstanding:
            raise ValidationError(
                f"Received quantity for {line.product} exceeds "
                f"the outstanding quantity of {outstanding}."
            )

        batch = None

        if line.batch_number:
            batch, _ = InventoryBatch.objects.get_or_create(
                product=line.product,
                warehouse=receipt.warehouse,
                location=line.location,
                batch_number=line.batch_number,
                defaults={
                    "manufacturing_date": line.manufacturing_date,
                    "expiry_date": line.expiry_date,
                },
            )

        post_stock_movement(
            movement_type="PURCHASE",
            product=line.product,
            warehouse=receipt.warehouse,
            location=line.location,
            quantity=line.quantity_received,
            unit_cost=line.unit_cost,
            batch=batch,
            reference=receipt.receipt_number,
            remarks=(
                f"Goods receipt against purchase order "
                f"{receipt.purchase_order.order_number}"
            ),
            created_by=user,
        )

        po_line.quantity_received += line.quantity_received
        po_line.save(
            update_fields=["quantity_received"]
        )

    purchase_order = (
        PurchaseOrder.objects
        .select_for_update()
        .get(pk=receipt.purchase_order_id)
    )

    total_ordered = sum(
        (
            line.quantity
            for line in purchase_order.lines.all()
        ),
        Decimal("0.000"),
    )

    total_received = sum(
        (
            line.quantity_received
            for line in purchase_order.lines.all()
        ),
        Decimal("0.000"),
    )

    if total_received >= total_ordered:
        purchase_order.status = "RECEIVED"
    elif total_received > Decimal("0.000"):
        purchase_order.status = "PARTIALLY_RECEIVED"

    purchase_order.save(
        update_fields=["status"]
    )

    receipt.status = "POSTED"
    receipt.posted_at = timezone.now()

    if user is not None:
        receipt.received_by = user

    receipt.save(
        update_fields=[
            "status",
            "posted_at",
            "received_by",
        ]
    )

    return receipt
