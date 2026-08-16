from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from billing.models import Invoice, InvoiceLine
from enterprise.services import get_invoice_reference


def _to_decimal(value, field_name):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(
            f"{field_name} must be a valid number."
        ) from exc


@transaction.atomic
def create_commercial_invoice(
    *,
    customer_name,
    items,
    customer_phone="",
    customer_email="",
    customer_address="",
    customer_kra_pin="",
    invoice_type="COMMERCIAL",
    due_date=None,
    currency="KES",
    notes="",
    terms="",
):
    customer_name = str(customer_name).strip()

    if not customer_name:
        raise ValueError("Customer name is required.")

    if invoice_type not in {"COMMERCIAL", "SERVICE"}:
        raise ValueError(
            "Invoice type must be COMMERCIAL or SERVICE."
        )

    if not items:
        raise ValueError(
            "At least one invoice item is required."
        )

    invoice_number = get_invoice_reference()

    invoice = Invoice.objects.create(
        invoice_number=invoice_number,
        invoice_type=invoice_type,
        customer_name=customer_name,
        customer_phone=str(customer_phone).strip(),
        customer_email=str(customer_email).strip(),
        customer_address=str(customer_address).strip(),
        customer_kra_pin=str(customer_kra_pin).strip(),
        invoice_date=timezone.localdate(),
        due_date=due_date,
        currency=currency,
        subtotal=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("0.00"),
        amount_paid=Decimal("0.00"),
        status="DRAFT",
        notes=notes,
        terms=terms,
    )

    for position, item in enumerate(items, start=1):
        description = str(
            item.get("description", "")
        ).strip()

        if not description:
            raise ValueError(
                f"Item {position} requires a description."
            )

        quantity = _to_decimal(
            item.get("quantity", 1),
            f"Item {position} quantity",
        )

        unit_price = _to_decimal(
            item.get("unit_price", 0),
            f"Item {position} unit price",
        )

        discount_rate = _to_decimal(
            item.get("discount_rate", 0),
            f"Item {position} discount rate",
        )

        tax_rate = _to_decimal(
            item.get("tax_rate", 0),
            f"Item {position} tax rate",
        )

        if quantity <= 0:
            raise ValueError(
                f"Item {position} quantity must be greater than zero."
            )

        if unit_price < 0:
            raise ValueError(
                f"Item {position} unit price cannot be negative."
            )

        if not Decimal("0") <= discount_rate <= Decimal("100"):
            raise ValueError(
                f"Item {position} discount rate must be between 0 and 100."
            )

        if not Decimal("0") <= tax_rate <= Decimal("100"):
            raise ValueError(
                f"Item {position} tax rate must be between 0 and 100."
            )

        InvoiceLine.objects.create(
            invoice=invoice,
            item_code=str(
                item.get("item_code", "")
            ).strip(),
            description=description,
            quantity=quantity,
            unit=str(
                item.get("unit", "EA")
            ).strip() or "EA",
            unit_price=unit_price,
            discount_rate=discount_rate,
            tax_rate=tax_rate,
        )

    invoice.refresh_from_db()
    invoice.calculate_totals()
    invoice.refresh_from_db()

    return invoice


@transaction.atomic
def _invoice_company(invoice):
    """
    Resolve the company that owns an invoice.

    AfriAxis currently operates as a single-company ERP, but this helper
    first attempts to derive the company from the invoice relationships.
    """
    from enterprise.models import Company

    if invoice.apartment_id:
        apartment = invoice.apartment

        if hasattr(apartment, "company_id") and apartment.company_id:
            return apartment.company

    if invoice.tenant_id:
        tenant = invoice.tenant

        if (
            hasattr(tenant, "apartment")
            and tenant.apartment
            and hasattr(tenant.apartment, "company_id")
            and tenant.apartment.company_id
        ):
            return tenant.apartment.company

    company = Company.objects.first()

    if company is None:
        raise ValidationError(
            "No company has been configured."
        )

    return company


@transaction.atomic
def post_customer_invoice(invoice, user=None):
    from decimal import Decimal

    from accounting.models import JournalEntry
    from accounting.posting import create_journal_entry
    from enterprise.models import Currency

    invoice = (
        invoice.__class__.objects
        .select_for_update()
        .select_related(
            "tenant",
            "apartment",
        )
        .get(pk=invoice.pk)
    )

    if invoice.status == "DRAFT":
        raise ValidationError(
            "A draft invoice cannot be posted to the General Ledger."
        )

    if invoice.status == "CANCELLED":
        raise ValidationError(
            "A cancelled invoice cannot be posted."
        )

    if invoice.total_amount <= Decimal("0.00"):
        raise ValidationError(
            "Invoice total must be greater than zero."
        )

    reference = f"INV-{invoice.invoice_number}"
    company = _invoice_company(invoice)

    existing = JournalEntry.objects.filter(
        company=company,
        reference=reference,
    ).first()

    if existing:
        return existing

    receivable = Decimal(str(invoice.total_amount))
    vat = Decimal(str(invoice.tax_amount))
    revenue = Decimal(str(invoice.subtotal))
    discount = Decimal(str(invoice.discount_amount))

    # Revenue should equal the taxable/net sales amount.
    net_revenue = revenue - discount

    if net_revenue <= Decimal("0.00"):
        net_revenue = receivable - vat

    if receivable != net_revenue + vat:
        raise ValidationError(
            "Invoice accounting values do not balance: "
            f"receivable {receivable}, "
            f"revenue {net_revenue}, VAT {vat}."
        )

    try:
        currency = Currency.objects.get(
            code=invoice.currency,
        )
    except Currency.DoesNotExist as exc:
        raise ValidationError(
            f"Currency {invoice.currency} has not been configured."
        ) from exc

    lines = [
        {
            "account_code": "1100",
            "debit": receivable,
            "description": (
                f"Customer invoice {invoice.invoice_number}"
            ),
        },
        {
            "account_code": "4000",
            "credit": net_revenue,
            "description": (
                f"Sales revenue - {invoice.customer_name}"
            ),
        },
    ]

    if vat > Decimal("0.00"):
        lines.append(
            {
                "account_code": "2100",
                "credit": vat,
                "description": (
                    f"Output VAT - {invoice.invoice_number}"
                ),
            }
        )

    return create_journal_entry(
        company=company,
        currency=currency,
        entry_date=invoice.invoice_date,
        reference=reference,
        description=(
            f"Customer invoice {invoice.invoice_number}"
        ),
        lines=lines,
        user=user,
        auto_post=True,
    )


@transaction.atomic
def post_customer_payment(payment, user=None):
    from decimal import Decimal

    from accounting.models import JournalEntry
    from accounting.posting import create_journal_entry
    from enterprise.models import Currency

    payment = (
        payment.__class__.objects
        .select_for_update()
        .select_related(
            "invoice",
            "invoice__tenant",
            "invoice__apartment",
        )
        .get(pk=payment.pk)
    )

    invoice = payment.invoice
    payment_amount = Decimal(str(payment.amount))

    if payment_amount <= Decimal("0.00"):
        raise ValidationError(
            "Payment amount must be greater than zero."
        )

    # The payment record already exists and InvoicePayment.save()
    # recalculates amount_paid. Check the invoice total against all
    # recorded payments instead of adding the payment again.
    total_recorded = (
        invoice.invoicepayment_set.aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )

    if total_recorded > Decimal(str(invoice.total_amount)):
        raise ValidationError(
            "Recorded payments exceed the invoice total."
        )

    reference_value = (
        payment.mpesa_receipt
        or f"PAY-{payment.pk}"
    )

    reference = f"RCPT-{reference_value}"
    company = _invoice_company(invoice)

    existing = JournalEntry.objects.filter(
        company=company,
        reference=reference,
    ).first()

    if existing:
        return existing

    try:
        currency = Currency.objects.get(
            code=invoice.currency,
        )
    except Currency.DoesNotExist as exc:
        raise ValidationError(
            f"Currency {invoice.currency} has not been configured."
        ) from exc

    journal = create_journal_entry(
        company=company,
        currency=currency,
        entry_date=payment.paid_at.date(),
        reference=reference,
        description=(
            f"Customer payment for invoice "
            f"{invoice.invoice_number}"
        ),
        lines=[
            {
                "account_code": "1000",
                "debit": payment_amount,
                "description": (
                    f"Customer receipt {reference_value}"
                ),
            },
            {
                "account_code": "1100",
                "credit": payment_amount,
                "description": (
                    f"Settlement of invoice "
                    f"{invoice.invoice_number}"
                ),
            },
        ],
        user=user,
        auto_post=True,
    )

    # Use the model's aggregate-based status calculation.
    invoice.recalculate_status()

    return journal
