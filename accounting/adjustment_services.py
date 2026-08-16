from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AdjustmentNote, JournalEntry
from .posting import create_journal_entry


@transaction.atomic
def post_adjustment_note(
    *,
    adjustment_note,
    user=None,
):
    note = (
        AdjustmentNote.objects
        .select_for_update()
        .select_related(
            "company",
            "offset_account",
            "supplier",
            "customer_invoice",
            "supplier_invoice",
            "journal_entry",
        )
        .get(pk=adjustment_note.pk)
    )

    if note.status == "POSTED":
        if note.journal_entry_id:
            return note.journal_entry

        raise ValidationError(
            "This adjustment note is already posted."
        )

    if note.status == "CANCELLED":
        raise ValidationError(
            "A cancelled adjustment note cannot be posted."
        )

    note.full_clean()

    subtotal = Decimal(str(note.subtotal))
    tax_amount = Decimal(str(note.tax_amount))
    total_amount = subtotal + tax_amount

    reference = f"ADJ-{note.note_number}"

    existing = JournalEntry.objects.filter(
        company=note.company,
        reference=reference,
    ).first()

    if existing:
        note.journal_entry = existing
        note.status = "POSTED"
        note.posted_at = (
            existing.posted_at or timezone.now()
        )

        if user is not None:
            note.posted_by = user

        note.save(
            update_fields=[
                "journal_entry",
                "status",
                "posted_at",
                "posted_by",
                "updated_at",
            ]
        )

        return existing

    lines = []

    if note.note_type == "CUSTOMER_CREDIT":
        lines.append(
            {
                "account_code": note.offset_account.code,
                "debit": subtotal,
                "credit": Decimal("0.00"),
                "description": (
                    f"Credit note {note.note_number}: "
                    f"{note.reason}"
                ),
            }
        )

        if tax_amount > Decimal("0.00"):
            lines.append(
                {
                    "account_code": "2100",
                    "debit": tax_amount,
                    "credit": Decimal("0.00"),
                    "description": (
                        f"Output VAT reversal "
                        f"{note.note_number}"
                    ),
                }
            )

        lines.append(
            {
                "account_code": "1100",
                "debit": Decimal("0.00"),
                "credit": total_amount,
                "description": (
                    f"Customer credit: "
                    f"{note.customer_name}"
                ),
            }
        )

        description = (
            f"Customer credit note {note.note_number} "
            f"for {note.customer_name}"
        )

    elif note.note_type == "SUPPLIER_DEBIT":
        lines.append(
            {
                "account_code": "2000",
                "debit": total_amount,
                "credit": Decimal("0.00"),
                "description": (
                    f"Supplier debit note: "
                    f"{note.supplier}"
                ),
            }
        )

        lines.append(
            {
                "account_code": note.offset_account.code,
                "debit": Decimal("0.00"),
                "credit": subtotal,
                "description": (
                    f"Supplier debit note "
                    f"{note.note_number}: "
                    f"{note.reason}"
                ),
            }
        )

        if tax_amount > Decimal("0.00"):
            lines.append(
                {
                    "account_code": "1300",
                    "debit": Decimal("0.00"),
                    "credit": tax_amount,
                    "description": (
                        f"Input VAT reversal "
                        f"{note.note_number}"
                    ),
                }
            )

        description = (
            f"Supplier debit note {note.note_number} "
            f"for {note.supplier}"
        )

    else:
        raise ValidationError(
            "Unsupported adjustment note type."
        )

    journal_entry = create_journal_entry(
        company=note.company,
        reference=reference,
        description=description,
        entry_date=note.note_date,
        lines=lines,
        user=user,
        auto_post=True,
    )

    note.journal_entry = journal_entry
    note.status = "POSTED"
    note.posted_at = timezone.now()

    if user is not None:
        note.posted_by = user

    note.save(
        update_fields=[
            "journal_entry",
            "status",
            "posted_at",
            "posted_by",
            "updated_at",
        ]
    )

    return journal_entry
