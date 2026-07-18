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