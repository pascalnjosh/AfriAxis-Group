from decimal import Decimal

from .models import BankTransaction
from .pdf_utils import extract_pdf_text
from .parsers.sidian import parse_sidian_transactions


def clean_amount(value):
    if value in [None, ""]:
        return Decimal("0")

    value = str(value).replace(",", "").replace("KES", "").replace("-", "").strip()

    try:
        return Decimal(value)
    except Exception:
        return Decimal("0")


def create_transaction(statement_upload, data):
    return BankTransaction.objects.create(
        bank_account=statement_upload.bank_account,
        statement_upload=statement_upload,
        transaction_date=data["date"],
        description=data["description"],
        reference=data.get("reference", ""),
        money_in=clean_amount(data.get("money_in", 0)),
        money_out=clean_amount(data.get("money_out", 0)),
        balance=clean_amount(data.get("balance", 0)),
    )


def process_pdf_statement(statement_upload):
    text = extract_pdf_text(statement_upload.file.path)
    bank_name = statement_upload.bank_account.bank_name.upper()

    if "SIDIAN" in bank_name:
        transactions = parse_sidian_transactions(text)

        for item in transactions:
            create_transaction(statement_upload, item)

        statement_upload.processed = True
        statement_upload.save()

        return len(transactions)

    raise ValueError("PDF parser for this bank is not ready yet.")


def process_bank_statement(statement_upload):
    filename = statement_upload.file.name.lower()

    if filename.endswith(".pdf"):
        return process_pdf_statement(statement_upload)

    raise ValueError("Only PDF processing is active right now.")

def match_erp_bank_transaction(bank_transaction):
    from datetime import timedelta

    from purchasing.models import SupplierPayment
    from sales.models import SalesReceipt

    transaction = bank_transaction

    transaction.matched_sales_receipt = None
    transaction.matched_supplier_payment = None

    if transaction.money_in > Decimal("0.00"):
        date_from = transaction.transaction_date - timedelta(days=3)
        date_to = transaction.transaction_date + timedelta(days=3)

        receipts = (
            SalesReceipt.objects
            .filter(
                bank_account=transaction.bank_account,
                status="POSTED",
                amount=transaction.money_in,
                receipt_date__range=(
                    date_from,
                    date_to,
                ),
            )
            .exclude(
                bank_transactions__match_status="approved",
            )
            .order_by(
                "receipt_date",
                "id",
            )
        )

        exact_reference = receipts.filter(
            reference__iexact=transaction.reference,
        ).first()

        match = exact_reference or receipts.first()

        if match:
            transaction.matched_sales_receipt = match
            transaction.suggested_category = "customer_receipt"
            transaction.auto_matched = True
            transaction.confidence = (
                100
                if exact_reference
                else 90
            )
            transaction.match_notes = (
                f"Matched customer receipt "
                f"{match.receipt_number}"
            )

            transaction.save(
                update_fields=[
                    "matched_sales_receipt",
                    "matched_supplier_payment",
                    "suggested_category",
                    "auto_matched",
                    "confidence",
                    "match_notes",
                ]
            )

            return transaction

    if transaction.money_out > Decimal("0.00"):
        date_from = transaction.transaction_date - timedelta(days=3)
        date_to = transaction.transaction_date + timedelta(days=3)

        payments = (
            SupplierPayment.objects
            .filter(
                bank_account=transaction.bank_account,
                posted=True,
                amount=transaction.money_out,
                payment_date__range=(
                    date_from,
                    date_to,
                ),
            )
            .exclude(
                bank_transactions__match_status="approved",
            )
            .order_by(
                "payment_date",
                "id",
            )
        )

        exact_reference = payments.filter(
            reference__iexact=transaction.reference,
        ).first()

        match = exact_reference or payments.first()

        if match:
            transaction.matched_supplier_payment = match
            transaction.suggested_category = "supplier_payment"
            transaction.auto_matched = True
            transaction.confidence = (
                100
                if exact_reference
                else 90
            )
            transaction.match_notes = (
                f"Matched supplier payment "
                f"{match.reference}"
            )

            transaction.save(
                update_fields=[
                    "matched_sales_receipt",
                    "matched_supplier_payment",
                    "suggested_category",
                    "auto_matched",
                    "confidence",
                    "match_notes",
                ]
            )

            return transaction

    transaction.auto_matched = False
    transaction.confidence = 0

    transaction.save(
        update_fields=[
            "matched_sales_receipt",
            "matched_supplier_payment",
            "auto_matched",
            "confidence",
        ]
    )

    return transaction
