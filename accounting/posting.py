from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from enterprise.models import Currency

from .models import Account, JournalEntry, JournalEntryLine
from .services import post_journal_entry


@transaction.atomic
def create_journal_entry(
    *,
    company,
    reference,
    description,
    lines,
    currency=None,
    entry_date=None,
    user=None,
    auto_post=True,
):
    if not lines or len(lines) < 2:
        raise ValidationError(
            "A journal entry requires at least two lines."
        )

    if currency is None:
        currency = Currency.objects.first()

    if currency is None:
        raise ValidationError(
            "No currency is configured."
        )

    journal_number = (
        f"JV-{timezone.now():%Y%m%d}-"
        f"{uuid4().hex[:8].upper()}"
    )

    entry = JournalEntry.objects.create(
        journal_number=journal_number,
        company=company,
        currency=currency,
        entry_date=entry_date or timezone.localdate(),
        reference=reference,
        description=description,
        created_by=user,
    )

    for item in lines:
        account_code = item["account_code"]
        debit = Decimal(str(item.get("debit", "0.00")))
        credit = Decimal(str(item.get("credit", "0.00")))
        line_description = item.get("description", "")

        try:
            account = Account.objects.get(
                company=company,
                code=account_code,
                active=True,
            )
        except Account.DoesNotExist as exc:
            raise ValidationError(
                f"Active account {account_code} was not found."
            ) from exc

        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=account,
            description=line_description,
            debit=debit,
            credit=credit,
        )

    if auto_post:
        post_journal_entry(
            journal_entry=entry,
            user=user,
        )

    return entry
