from decimal import Decimal

from .models import Account


def get_general_ledger(
    *,
    account,
    date_from=None,
    date_to=None,
):
    lines = (
        account.journal_lines
        .select_related("journal_entry")
        .order_by(
            "journal_entry__entry_date",
            "journal_entry__journal_number",
            "id",
        )
    )

    if date_from:
        lines = lines.filter(
            journal_entry__entry_date__gte=date_from,
        )

    if date_to:
        lines = lines.filter(
            journal_entry__entry_date__lte=date_to,
        )

    balance = Decimal("0.00")
    rows = []

    for line in lines:

        if account.account_type.normal_balance == "DEBIT":
            balance += line.debit
            balance -= line.credit
        else:
            balance += line.credit
            balance -= line.debit

        rows.append(
            {
                "date": line.journal_entry.entry_date,
                "journal": line.journal_entry.journal_number,
                "reference": line.journal_entry.reference,
                "description": line.description,
                "debit": line.debit,
                "credit": line.credit,
                "balance": balance,
            }
        )

    return rows
