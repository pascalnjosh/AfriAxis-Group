from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import JournalEntry
from accounting.posting import create_journal_entry
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
            "purchase_order__company",
            "purchase_order__currency",
            "warehouse",
            "supplier",
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

    journal_reference = f"GRN-{receipt.receipt_number}"

    if JournalEntry.objects.filter(
        company=receipt.purchase_order.company,
        reference=journal_reference,
    ).exists():
        raise ValidationError(
            "A GRNI journal already exists for this goods receipt."
        )

    total_receipt_value = Decimal("0.00")

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
                f"Location {line.location} does not belong "
                "to the selected warehouse."
            )

        outstanding = (
            po_line.quantity
            - po_line.quantity_received
        )

        if line.quantity_received <= Decimal("0.000"):
            raise ValidationError(
                f"Received quantity for {line.product} "
                "must be greater than zero."
            )

        if line.quantity_received > outstanding:
            raise ValidationError(
                f"Received quantity for {line.product} exceeds "
                f"the outstanding quantity of {outstanding}."
            )

        batch = None

        if line.batch_number:
            batch, created = InventoryBatch.objects.get_or_create(
                product=line.product,
                batch_number=line.batch_number,
                defaults={
                    "manufacturing_date": line.manufacturing_date,
                    "expiry_date": line.expiry_date,
                    "quantity_received": Decimal("0.000"),
                    "quantity_available": Decimal("0.000"),
                    "cost_price": line.unit_cost,
                    "active": True,
                },
            )

            if not created:
                if (
                    line.manufacturing_date
                    and batch.manufacturing_date
                    and batch.manufacturing_date
                    != line.manufacturing_date
                ):
                    raise ValidationError(
                        f"Batch {line.batch_number} has a different "
                        "manufacturing date."
                    )

                if (
                    line.expiry_date
                    and batch.expiry_date
                    and batch.expiry_date != line.expiry_date
                ):
                    raise ValidationError(
                        f"Batch {line.batch_number} has a different "
                        "expiry date."
                    )

        movement, _balance = post_stock_movement(
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

        line_value = movement.total_cost
        total_receipt_value += line_value

        if batch:
            batch.quantity_received += line.quantity_received
            batch.cost_price = line.unit_cost

            if line.manufacturing_date:
                batch.manufacturing_date = line.manufacturing_date

            if line.expiry_date:
                batch.expiry_date = line.expiry_date

            batch.save(
                update_fields=[
                    "quantity_received",
                    "quantity_available",
                    "cost_price",
                    "manufacturing_date",
                    "expiry_date",
                ]
            )

        po_line.quantity_received += line.quantity_received
        po_line.save(
            update_fields=["quantity_received"]
        )

    if total_receipt_value <= Decimal("0.00"):
        raise ValidationError(
            "The goods receipt has no accounting value."
        )

    create_journal_entry(
        company=receipt.purchase_order.company,
        currency=receipt.purchase_order.currency,
        entry_date=receipt.receipt_date,
        reference=journal_reference,
        description=(
            f"Goods receipt {receipt.receipt_number} "
            f"from {receipt.supplier.name}"
        ),
        lines=[
            {
                "account_code": "1210",
                "debit": total_receipt_value,
                "description": (
                    f"Inventory received under "
                    f"{receipt.receipt_number}"
                ),
            },
            {
                "account_code": "2050",
                "credit": total_receipt_value,
                "description": (
                    f"GRNI liability for "
                    f"{receipt.receipt_number}"
                ),
            },
        ],
        user=user,
        auto_post=True,
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


@transaction.atomic
def post_supplier_invoice(supplier_invoice, user=None):
    invoice = (
        supplier_invoice.__class__.objects
        .select_for_update()
        .select_related(
            "supplier",
            "purchase_order",
            "purchase_order__company",
            "currency",
        )
        .get(pk=supplier_invoice.pk)
    )

    if invoice.status == "CANCELLED":
        raise ValidationError(
            "A cancelled supplier invoice cannot be posted."
        )

    if invoice.total_amount <= Decimal("0.00"):
        raise ValidationError(
            "Supplier invoice total must be greater than zero."
        )

    if invoice.purchase_order is None:
        raise ValidationError(
            "Supplier invoice must be linked to a purchase order."
        )

    reference = f"SUPINV-{invoice.invoice_number}"

    existing = JournalEntry.objects.filter(
        company=invoice.purchase_order.company,
        reference=reference,
    ).first()

    if existing:
        return existing

    net_amount = Decimal(str(invoice.subtotal))
    tax_amount = Decimal(str(invoice.tax_amount))
    total_amount = Decimal(str(invoice.total_amount))

    if total_amount != net_amount + tax_amount:
        raise ValidationError(
            "Supplier invoice does not balance: "
            f"net {net_amount}, VAT {tax_amount}, "
            f"total {total_amount}."
        )

    lines = []

    if net_amount > Decimal("0.00"):
        lines.append(
            {
                "account_code": "2050",
                "debit": net_amount,
                "description": (
                    f"Clear GRNI for supplier invoice "
                    f"{invoice.invoice_number}"
                ),
            }
        )

    if tax_amount > Decimal("0.00"):
        lines.append(
            {
                "account_code": "1300",
                "debit": tax_amount,
                "description": (
                    f"Input VAT on supplier invoice "
                    f"{invoice.invoice_number}"
                ),
            }
        )

    lines.append(
        {
            "account_code": "2000",
            "credit": total_amount,
            "description": (
                f"Accounts payable - {invoice.supplier.name}"
            ),
        }
    )

    journal = create_journal_entry(
        company=invoice.purchase_order.company,
        currency=invoice.currency,
        entry_date=invoice.invoice_date,
        reference=reference,
        description=(
            f"Supplier invoice {invoice.invoice_number}"
        ),
        lines=lines,
        user=user,
        auto_post=True,
    )

    if invoice.status == "DRAFT":
        invoice.status = "PENDING"
        invoice.save(update_fields=["status"])

    return journal

@transaction.atomic
def post_supplier_payment(payment, user=None):
    from decimal import Decimal

    from accounting.models import JournalEntry
    from accounting.posting import create_journal_entry

    payment = (
        payment.__class__.objects
        .select_for_update()
        .select_related(
            "supplier_invoice",
            "supplier_invoice__purchase_order",
            "supplier_invoice__purchase_order__company",
            "supplier_invoice__currency",
            "supplier",
            "bank_account",
        )
        .get(pk=payment.pk)
    )

    invoice = payment.supplier_invoice
    amount = Decimal(str(payment.amount))

    if payment.posted:
        reference = f"SUPPAY-{payment.reference}"

        existing = JournalEntry.objects.filter(
            reference=reference,
        ).first()

        if existing:
            return existing

        raise ValidationError(
            "This supplier payment is marked posted but has no journal."
        )

    if invoice.status == "CANCELLED":
        raise ValidationError(
            "A cancelled supplier invoice cannot be paid."
        )

    if payment.supplier_id != invoice.supplier_id:
        raise ValidationError(
            "Payment supplier does not match the supplier invoice."
        )

    if amount <= Decimal("0.00"):
        raise ValidationError(
            "Payment amount must be greater than zero."
        )

    outstanding = (
        Decimal(str(invoice.total_amount))
        - Decimal(str(invoice.amount_paid))
    )

    if amount > outstanding:
        raise ValidationError(
            f"Payment exceeds outstanding balance of {outstanding}."
        )

    if invoice.purchase_order is None:
        raise ValidationError(
            "Supplier invoice has no linked purchase order."
        )

    company = invoice.purchase_order.company
    reference = f"SUPPAY-{payment.reference}"

    existing = JournalEntry.objects.filter(
        company=company,
        reference=reference,
    ).first()

    if existing:
        payment.posted = True
        payment.posted_at = timezone.now()
        payment.save(
            update_fields=[
                "posted",
                "posted_at",
            ]
        )
        return existing

    journal = create_journal_entry(
        company=company,
        currency=invoice.currency,
        entry_date=payment.payment_date,
        reference=reference,
        description=(
            f"Supplier payment {payment.reference} "
            f"for invoice {invoice.invoice_number}"
        ),
        lines=[
            {
                "account_code": "2000",
                "debit": amount,
                "description": (
                    f"Settlement of supplier invoice "
                    f"{invoice.invoice_number}"
                ),
            },
            {
                "account_code": "1000",
                "credit": amount,
                "description": (
                    f"Payment from {payment.bank_account}"
                ),
            },
        ],
        user=user,
        auto_post=True,
    )

    invoice.amount_paid += amount

    if invoice.amount_paid >= invoice.total_amount:
        invoice.status = "PAID"
    elif invoice.amount_paid > Decimal("0.00"):
        invoice.status = "PARTIAL"
    else:
        invoice.status = "PENDING"

    invoice.save(
        update_fields=[
            "amount_paid",
            "status",
        ]
    )

    payment.posted = True
    payment.posted_at = timezone.now()
    payment.save(
        update_fields=[
            "posted",
            "posted_at",
        ]
    )

    return journal

