from decimal import Decimal

from billing.models import Invoice, InvoicePayment


def apply_mpesa_to_invoice(
    phone_number,
    amount,
    receipt,
    invoice=None,
):
    amount = Decimal(str(amount))

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    if invoice is None:
        invoice = (
            Invoice.objects
            .filter(tenant__phone=phone_number)
            .exclude(status="PAID")
            .order_by("created_at", "id")
            .first()
        )

    if not invoice:
        return None

    payment = InvoicePayment.objects.create(
        invoice=invoice,
        amount=amount,
        phone_number=phone_number,
        mpesa_receipt=receipt,
    )

    return payment
