from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import JournalEntry


@transaction.atomic
def post_journal_entry(journal_entry, user=None):
    entry = (
        JournalEntry.objects
        .select_for_update()
        .prefetch_related(
            "lines",
            "lines__account",
        )
        .get(pk=journal_entry.pk)
    )

    if entry.status == "POSTED":
        raise ValidationError(
            "This journal entry has already been posted."
        )

    if entry.status == "REVERSED":
        raise ValidationError(
            "A reversed journal entry cannot be posted."
        )

    lines = list(entry.lines.all())

    if len(lines) < 2:
        raise ValidationError(
            "A journal entry must contain at least two lines."
        )

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for line in lines:
        line.full_clean()

        if line.account.company_id != entry.company_id:
            raise ValidationError(
                f"Account {line.account} belongs to another company."
            )

        if not line.account.active:
            raise ValidationError(
                f"Account {line.account} is inactive."
            )

        total_debit += line.debit
        total_credit += line.credit

    if total_debit <= Decimal("0.00"):
        raise ValidationError(
            "Journal debit total must be greater than zero."
        )

    if total_credit <= Decimal("0.00"):
        raise ValidationError(
            "Journal credit total must be greater than zero."
        )

    if total_debit != total_credit:
        raise ValidationError(
            f"Journal entry is not balanced. "
            f"Debit: {total_debit}, Credit: {total_credit}."
        )

    entry.status = "POSTED"
    entry.posted_at = timezone.now()

    if user is not None:
        entry.posted_by = user

    entry.save(
        update_fields=[
            "status",
            "posted_at",
            "posted_by",
        ]
    )

    return entry
