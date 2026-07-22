from decimal import Decimal, InvalidOperation

from django.db import transaction
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
