from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.models import InventoryBatch
from inventory.services import post_stock_movement

from .models import DeliveryNote, SalesOrder


@transaction.atomic
def post_delivery_note(delivery_note, user=None):
    delivery_note = (
        DeliveryNote.objects
        .select_for_update()
        .select_related(
            "sales_order",
            "warehouse",
        )
        .get(pk=delivery_note.pk)
    )

    if delivery_note.status == "POSTED":
        raise ValidationError(
            "This delivery note has already been posted."
        )

    if delivery_note.status == "CANCELLED":
        raise ValidationError(
            "A cancelled delivery note cannot be posted."
        )

    if delivery_note.sales_order.status == "CANCELLED":
        raise ValidationError(
            "The related sales order is cancelled."
        )

    lines = list(
        delivery_note.lines
        .select_related(
            "sales_order_line",
            "product",
            "location",
        )
        .select_for_update()
    )

    if not lines:
        raise ValidationError(
            "The delivery note has no lines."
        )

    for line in lines:
        order_line = line.sales_order_line

        if order_line.sales_order_id != delivery_note.sales_order_id:
            raise ValidationError(
                f"Product {line.product} does not belong "
                "to this sales order."
            )

        if line.product_id != order_line.product_id:
            raise ValidationError(
                f"Product mismatch on delivery line {line.pk}."
            )

        if line.location.warehouse_id != delivery_note.warehouse_id:
            raise ValidationError(
                f"Location {line.location} does not belong "
                "to the selected warehouse."
            )

        outstanding = (
            order_line.quantity
            - order_line.quantity_delivered
        )

        if line.quantity <= Decimal("0.000"):
            raise ValidationError(
                f"Delivery quantity for {line.product} "
                "must be greater than zero."
            )

        if line.quantity > outstanding:
            raise ValidationError(
                f"Delivery quantity for {line.product} exceeds "
                f"the outstanding quantity of {outstanding}."
            )

        batch = None

        if line.batch_number:
            batch = (
                InventoryBatch.objects
                .select_for_update()
                .filter(
                    product=line.product,
                    warehouse=delivery_note.warehouse,
                    location=line.location,
                    batch_number=line.batch_number,
                )
                .first()
            )

            if batch is None:
                raise ValidationError(
                    f"Batch {line.batch_number} was not found "
                    f"for {line.product}."
                )

        post_stock_movement(
            product=line.product,
            warehouse=delivery_note.warehouse,
            location=line.location,
            movement_type="SALE",
            quantity=line.quantity,
            reference=delivery_note.delivery_number,
            batch=batch,
            created_by=user,
            remarks=(
                f"Delivery against sales order "
                f"{delivery_note.sales_order.order_number}"
            ),
        )

        order_line.quantity_delivered += line.quantity
        order_line.save(
            update_fields=["quantity_delivered"]
        )

    order = (
        SalesOrder.objects
        .select_for_update()
        .get(pk=delivery_note.sales_order_id)
    )

    total_ordered = sum(
        (
            line.quantity
            for line in order.lines.all()
        ),
        Decimal("0.000"),
    )

    total_delivered = sum(
        (
            line.quantity_delivered
            for line in order.lines.all()
        ),
        Decimal("0.000"),
    )

    if total_delivered >= total_ordered:
        order.status = "DELIVERED"
    elif total_delivered > Decimal("0.000"):
        order.status = "PARTIALLY_DELIVERED"

    order.save(update_fields=["status"])

    delivery_note.status = "POSTED"
    delivery_note.posted_at = timezone.now()

    if user is not None:
        delivery_note.dispatched_by = user

    delivery_note.save(
        update_fields=[
            "status",
            "posted_at",
            "dispatched_by",
        ]
    )

    return delivery_note




