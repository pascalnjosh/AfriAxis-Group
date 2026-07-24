from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from .models import Account


def get_trial_balance(*, company, date_from=None, date_to=None):
    accounts = Account.objects.filter(
        company=company,
        active=True,
    ).select_related(
        "account_type",
    ).order_by(
        "code",
    )

    rows = []

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for account in accounts:
        lines = account.journal_lines.filter(
            journal_entry__status="POSTED",
        )

        if date_from:
            lines = lines.filter(
                journal_entry__entry_date__gte=date_from,
            )

        if date_to:
            lines = lines.filter(
                journal_entry__entry_date__lte=date_to,
            )

        totals = lines.aggregate(
            debit=Coalesce(
                Sum("debit"),
                Decimal("0.00"),
            ),
            credit=Coalesce(
                Sum("credit"),
                Decimal("0.00"),
            ),
        )

        debit = totals["debit"]
        credit = totals["credit"]

        if account.account_type.normal_balance == "DEBIT":
            balance = debit - credit
        else:
            balance = credit - debit

        rows.append(
            {
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.account_type.name,
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )

        total_debit += debit
        total_credit += credit

    return {
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": total_debit - total_credit,
        "is_balanced": total_debit == total_credit,
    }
