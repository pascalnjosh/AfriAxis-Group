from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import JournalEntry
from accounting.posting import create_journal_entry
from inventory.models import InventoryBatch
from inventory.services import post_stock_movement
from enterprise.services import get_invoice_reference
from .models import SalesInvoice, SalesReceipt
from .models import DeliveryNote, SalesOrder


@transaction.atomic
def post_delivery_note(delivery_note, user=None):
    delivery_note = (
        DeliveryNote.objects
        .select_for_update()
        .select_related(
            "sales_order",
            "sales_order__company",
            "sales_order__currency",
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

    journal_reference = (
        f"DELIVERY-{delivery_note.delivery_number}"
    )

    existing_journal = JournalEntry.objects.filter(
        company=delivery_note.sales_order.company,
        reference=journal_reference,
    ).first()

    if existing_journal:
        raise ValidationError(
            "A COGS journal already exists for this delivery note."
        )

    total_cost = Decimal("0.00")

    for line in lines:
        order_line = line.sales_order_line

        if (
            order_line.sales_order_id
            != delivery_note.sales_order_id
        ):
            raise ValidationError(
                f"Product {line.product} does not belong "
                "to this sales order."
            )

        if line.product_id != order_line.product_id:
            raise ValidationError(
                f"Product mismatch on delivery line {line.pk}."
            )

        if (
            line.location.warehouse_id
            != delivery_note.warehouse_id
        ):
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
                    batch_number=line.batch_number,
                )
                .first()
            )

            if batch is None:
                raise ValidationError(
                    f"Batch {line.batch_number} was not found "
                    f"for {line.product}."
                )

        # Services do not create inventory or COGS movements.
        if (
            line.product.track_inventory
            and line.product.product_type != "SERVICE"
        ):
            movement, _balance = post_stock_movement(
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

            total_cost += movement.total_cost

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

    if total_cost > Decimal("0.00"):
        create_journal_entry(
            company=delivery_note.sales_order.company,
            currency=delivery_note.sales_order.currency,
            entry_date=delivery_note.delivery_date,
            reference=journal_reference,
            description=(
                f"Cost of goods sold for delivery "
                f"{delivery_note.delivery_number}"
            ),
            lines=[
                {
                    "account_code": "5000",
                    "debit": total_cost,
                    "description": (
                        f"COGS for delivery "
                        f"{delivery_note.delivery_number}"
                    ),
                },
                {
                    "account_code": "1220",
                    "credit": total_cost,
                    "description": (
                        f"Finished goods inventory issued on delivery "
                        f"{delivery_note.delivery_number}"
                    ),
                },
            ],
            user=user,
            auto_post=True,
        )

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


@transaction.atomic
def post_sales_invoice(sales_invoice, user=None):
    invoice = (
        SalesInvoice.objects
        .select_for_update()
        .select_related(
            "company",
            "branch",
            "customer",
            "sales_order",
            "sales_order__company",
            "sales_order__branch",
            "sales_order__customer",
            "sales_order__currency",
            "currency",
        )
        .get(pk=sales_invoice.pk)
    )

    order = (
        SalesOrder.objects
        .select_for_update()
        .get(pk=invoice.sales_order_id)
    )

    customer = (
        invoice.customer.__class__.objects
        .select_for_update()
        .get(pk=invoice.customer_id)
    )

    if invoice.status == "CANCELLED":
        raise ValidationError(
            "A cancelled sales invoice cannot be posted."
        )

    journal_reference = None
    existing_journal = None

    if invoice.invoice_number:
        journal_reference = (
            f"SALESINV-{invoice.invoice_number}"
        )

        existing_journal = JournalEntry.objects.filter(
            company=invoice.company,
            reference=journal_reference,
        ).first()

    if invoice.status == "POSTED":
        if existing_journal:
            return existing_journal

        raise ValidationError(
            "This invoice is marked posted but has no journal entry."
        )

    if existing_journal:
        raise ValidationError(
            "A journal entry already exists for this sales invoice."
        )

    if order.status == "CANCELLED":
        raise ValidationError(
            "The related sales order is cancelled."
        )

    if order.status != "DELIVERED":
        raise ValidationError(
            "The sales order must be fully delivered before invoicing."
        )

    if invoice.company_id != order.company_id:
        raise ValidationError(
            "Invoice company does not match the sales order company."
        )

    if invoice.customer_id != order.customer_id:
        raise ValidationError(
            "Invoice customer does not match the sales order customer."
        )

    if invoice.currency_id != order.currency_id:
        raise ValidationError(
            "Invoice currency does not match the sales order currency."
        )

    if invoice.branch_id is None:
        invoice.branch = order.branch

    if invoice.branch_id is None:
        raise ValidationError(
            "A branch is required before generating the invoice number."
        )

    if invoice.branch.company_id != invoice.company_id:
        raise ValidationError(
            "Invoice branch does not belong to the invoice company."
        )

    lines = list(
        invoice.lines
        .select_for_update()
        .select_related(
            "sales_order_line",
            "sales_order_line__sales_order",
            "product",
        )
    )

    if not lines:
        raise ValidationError(
            "The sales invoice has no lines."
        )

    invoiced_order_line_ids = set()

    for line in lines:
        order_line = line.sales_order_line

        if order_line.sales_order_id != order.id:
            raise ValidationError(
                f"Invoice line {line.pk} does not belong "
                "to the selected sales order."
            )

        if line.product_id != order_line.product_id:
            raise ValidationError(
                f"Product mismatch on invoice line {line.pk}."
            )

        if order_line.id in invoiced_order_line_ids:
            raise ValidationError(
                f"Sales order line {order_line.id} appears more than once "
                "on the invoice."
            )

        invoiced_order_line_ids.add(order_line.id)

        if line.quantity <= Decimal("0.000"):
            raise ValidationError(
                f"Invoice quantity for {line.product} "
                "must be greater than zero."
            )

        if line.quantity != order_line.quantity:
            raise ValidationError(
                f"Invoice quantity for {line.product} must equal "
                f"the ordered quantity of {order_line.quantity}."
            )

        if order_line.quantity_delivered < line.quantity:
            raise ValidationError(
                f"Invoice quantity for {line.product} exceeds "
                f"the delivered quantity of "
                f"{order_line.quantity_delivered}."
            )

    order_line_ids = set(
        order.lines.values_list("id", flat=True)
    )

    if invoiced_order_line_ids != order_line_ids:
        raise ValidationError(
            "The invoice must contain every sales order line."
        )

    invoice.calculate_totals()

    net_revenue = (
        Decimal(str(invoice.subtotal))
        - Decimal(str(invoice.discount_amount))
    )

    tax_amount = Decimal(str(invoice.tax_amount))
    total_amount = Decimal(str(invoice.total_amount))

    if net_revenue <= Decimal("0.00"):
        raise ValidationError(
            "Invoice net revenue must be greater than zero."
        )

    if total_amount <= Decimal("0.00"):
        raise ValidationError(
            "Invoice total must be greater than zero."
        )

    expected_total = net_revenue + tax_amount

    if total_amount != expected_total:
        raise ValidationError(
            "Sales invoice does not balance: "
            f"net revenue {net_revenue}, "
            f"VAT {tax_amount}, "
            f"total {total_amount}."
        )

    projected_balance = (
        Decimal(str(customer.current_balance))
        + total_amount
    )

    # A zero credit limit is treated as no configured limit.
    if (
        customer.credit_limit > Decimal("0.00")
        and projected_balance > customer.credit_limit
    ):
        available_credit = (
            customer.credit_limit
            - customer.current_balance
        )

        raise ValidationError(
            f"Customer credit limit exceeded. "
            f"Available credit is {available_credit}."
        )

    if not invoice.invoice_number:
        invoice.invoice_number = get_invoice_reference(
            company_name=invoice.company.name,
            branch_code=invoice.branch.code,
        )

    journal_reference = (
        f"SALESINV-{invoice.invoice_number}"
    )

    if JournalEntry.objects.filter(
        company=invoice.company,
        reference=journal_reference,
    ).exists():
        raise ValidationError(
            "A journal entry already exists for this invoice number."
        )

    journal_lines = [
        {
            "account_code": "1100",
            "debit": total_amount,
            "description": (
                f"Accounts receivable - {customer.name}"
            ),
        },
        {
            "account_code": "4000",
            "credit": net_revenue,
            "description": (
                f"Sales revenue for invoice "
                f"{invoice.invoice_number}"
            ),
        },
    ]

    if tax_amount > Decimal("0.00"):
        journal_lines.append(
            {
                "account_code": "2100",
                "credit": tax_amount,
                "description": (
                    f"Output VAT on invoice "
                    f"{invoice.invoice_number}"
                ),
            }
        )

    journal = create_journal_entry(
        company=invoice.company,
        currency=invoice.currency,
        entry_date=invoice.invoice_date,
        reference=journal_reference,
        description=(
            f"Sales invoice {invoice.invoice_number} "
            f"for {customer.name}"
        ),
        lines=journal_lines,
        user=user,
        auto_post=True,
    )

    customer.current_balance = projected_balance
    customer.save(
        update_fields=[
            "current_balance",
            "updated_at",
        ]
    )

    invoice.status = "POSTED"
    invoice.posted_at = timezone.now()

    update_fields = [
        "invoice_number",
        "branch",
        "status",
        "posted_at",
        "updated_at",
    ]

    if user is not None:
        invoice.posted_by = user
        update_fields.append("posted_by")

    invoice.save(update_fields=update_fields)

    order.status = "INVOICED"
    order.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return journal




@transaction.atomic
def post_sales_receipt(receipt, user=None):
    receipt = (
        SalesReceipt.objects
        .select_for_update()
        .select_related(
            "sales_invoice",
            "sales_invoice__company",
            "sales_invoice__currency",
            "customer",
            "bank_account",
        )
        .get(pk=receipt.pk)
    )

    invoice = (
        SalesInvoice.objects
        .select_for_update()
        .select_related(
            "company",
            "currency",
            "customer",
        )
        .get(pk=receipt.sales_invoice_id)
    )

    customer = (
        invoice.customer.__class__.objects
        .select_for_update()
        .get(pk=invoice.customer_id)
    )

    if receipt.status == "POSTED":
        existing_journal = JournalEntry.objects.filter(
            company=invoice.company,
            reference=receipt.receipt_number,
        ).first()

        if existing_journal:
            return existing_journal

        raise ValidationError(
            "This receipt is marked posted but has no journal entry."
        )

    if receipt.status == "CANCELLED":
        raise ValidationError(
            "A cancelled sales receipt cannot be posted."
        )

    if invoice.status not in (
        "POSTED",
        "PARTIAL",
    ):
        raise ValidationError(
            "Only posted or partially paid invoices can receive payments."
        )

    if receipt.customer_id != invoice.customer_id:
        raise ValidationError(
            "Receipt customer does not match the sales invoice customer."
        )

    payment_amount = Decimal(str(receipt.amount))

    if payment_amount <= Decimal("0.00"):
        raise ValidationError(
            "Receipt amount must be greater than zero."
        )

    outstanding = Decimal(str(invoice.balance))

    if outstanding <= Decimal("0.00"):
        raise ValidationError(
            "This sales invoice has no outstanding balance."
        )

    if payment_amount > outstanding:
        raise ValidationError(
            f"Receipt amount {payment_amount} exceeds "
            f"the outstanding invoice balance of {outstanding}."
        )

    if receipt.payment_method == "BANK":
        if receipt.bank_account_id is None:
            raise ValidationError(
                "A bank account is required for bank receipts."
            )

        if not receipt.bank_account.active:
            raise ValidationError(
                "The selected bank account is inactive."
            )

        bank_currency = (
            str(receipt.bank_account.currency)
            .strip()
            .upper()
        )

        invoice_currency = (
            str(invoice.currency.code)
            .strip()
            .upper()
        )

        if bank_currency != invoice_currency:
            raise ValidationError(
                f"Bank currency {bank_currency} does not match "
                f"invoice currency {invoice_currency}."
            )

    journal_reference = (
        receipt.receipt_number
    )

    if JournalEntry.objects.filter(
        company=invoice.company,
        reference=journal_reference,
    ).exists():
        raise ValidationError(
            "A journal entry already exists for this sales receipt."
        )

    journal = create_journal_entry(
        company=invoice.company,
        currency=invoice.currency,
        entry_date=receipt.receipt_date,
        reference=journal_reference,
        description=(
            f"Customer receipt {receipt.receipt_number} "
            f"for invoice {invoice.invoice_number}"
        ),
        lines=[
            {
                "account_code": "1000",
                "debit": payment_amount,
                "description": (
                    f"Customer payment received - "
                    f"{receipt.receipt_number}"
                ),
            },
            {
                "account_code": "1100",
                "credit": payment_amount,
                "description": (
                    f"Accounts receivable cleared - "
                    f"{invoice.invoice_number}"
                ),
            },
        ],
        user=user,
        auto_post=True,
    )

    invoice.amount_paid = (
        Decimal(str(invoice.amount_paid))
        + payment_amount
    )

    if invoice.amount_paid >= invoice.total_amount:
        invoice.amount_paid = invoice.total_amount
        invoice.status = "PAID"
    else:
        invoice.status = "PARTIAL"

    invoice.save(
        update_fields=[
            "amount_paid",
            "status",
            "updated_at",
        ]
    )

    customer.current_balance = max(
        Decimal("0.00"),
        Decimal(str(customer.current_balance))
        - payment_amount,
    )

    customer.save(
        update_fields=[
            "current_balance",
            "updated_at",
        ]
    )

    receipt.status = "POSTED"
    receipt.posted_at = timezone.now()

    update_fields = [
        "status",
        "posted_at",
    ]

    if user is not None:
        receipt.posted_by = user
        update_fields.append("posted_by")

    receipt.save(
        update_fields=update_fields
    )

    journal.refresh_from_db()

    return journal

