from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounting.models import JournalEntry
from accounting.posting import create_journal_entry
from enterprise.models import Company


@transaction.atomic
def post_rent_bank_advance(bank_transaction, user=None):
    from banking.models import BankTransaction

    bank_item = (
        BankTransaction.objects
        .select_for_update()
        .select_related(
            "bank_account",
            "matched_tenant",
            "matched_house",
        )
        .get(pk=bank_transaction.pk)
    )

    if bank_item.match_status != "approved":
        raise ValidationError(
            "Only approved bank transactions can be posted."
        )

    if bank_item.suggested_category != "rent":
        raise ValidationError(
            "Bank transaction is not an approved rent receipt."
        )

    if bank_item.money_in <= Decimal("0.00"):
        raise ValidationError(
            "Rent receipt must have money in."
        )

    if not bank_item.matched_tenant_id:
        raise ValidationError(
            "Rent receipt has no matched tenant."
        )

    if not bank_item.matched_house_id:
        raise ValidationError(
            "Rent receipt has no matched house."
        )

    company = Company.objects.get(
        name="AfriAxis Group"
    )

    reference = (
        f"RENTADV-BANK-{bank_item.id}"
    )

    existing = JournalEntry.objects.filter(
        company=company,
        reference=reference,
    ).first()

    if existing:
        return existing

    amount = Decimal(str(bank_item.money_in))

    journal = create_journal_entry(
        company=company,
        entry_date=bank_item.transaction_date,
        reference=reference,
        description=(
            f"Tenant advance received from "
            f"{bank_item.matched_tenant} "
            f"for {bank_item.matched_house}"
        ),
        lines=[
            {
                "account_code": "1000",
                "debit": amount,
                "description": (
                    f"Bank rent receipt - "
                    f"{bank_item.matched_tenant}"
                ),
            },
            {
                "account_code": "2200",
                "credit": amount,
                "description": (
                    f"Tenant advance - "
                    f"{bank_item.matched_tenant}"
                ),
            },
        ],
        user=user,
        auto_post=True,
    )

    return journal


@transaction.atomic
def post_rent_bill(rent, user=None):
    from rentals.models import Rent

    rent = (
        Rent.objects
        .select_for_update()
        .select_related(
            "tenant",
            "house",
            "house__apartment",
        )
        .get(pk=rent.pk)
    )

    company = Company.objects.get(
        name="AfriAxis Group"
    )

    amount = Decimal(str(rent.amount))

    if amount <= Decimal("0.00"):
        raise ValidationError(
            "Rent amount must be greater than zero."
        )

    reference = f"RENTBILL-{rent.id}"

    existing = JournalEntry.objects.filter(
        company=company,
        reference=reference,
    ).first()

    if existing:
        return existing

    journal = create_journal_entry(
        company=company,
        entry_date=rent.billing_month,
        reference=reference,
        description=(
            f"Rent billing for {rent.tenant} - "
            f"{rent.house} - "
            f"{rent.billing_month:%B %Y}"
        ),
        lines=[
            {
                "account_code": "1100",
                "debit": amount,
                "description": (
                    f"Rent receivable - "
                    f"{rent.tenant}"
                ),
            },
            {
                "account_code": "4100",
                "credit": amount,
                "description": (
                    f"Rental revenue - "
                    f"{rent.tenant}"
                ),
            },
        ],
        user=user,
        auto_post=True,
    )

    return journal


@transaction.atomic
def apply_rent_bank_advance(bank_transaction, user=None):
    from banking.models import BankTransaction
    from payments.models import Payment

    bank_item = (
        BankTransaction.objects
        .select_for_update()
        .select_related(
            "matched_tenant",
            "matched_house",
        )
        .get(pk=bank_transaction.pk)
    )

    if bank_item.match_status != "approved":
        raise ValidationError(
            "Only approved bank transactions can be applied."
        )

    if bank_item.suggested_category != "rent":
        raise ValidationError(
            "Bank transaction is not a rent transaction."
        )

    payments = list(
        Payment.objects
        .filter(
            status="SUCCESS",
            payment_method="BANK",
            rental_rent__isnull=False,
            transaction_desc=bank_item.description,
        )
        .select_related(
            "rental_rent",
            "rental_rent__tenant",
        )
        .order_by("id")
    )

    if not payments:
        raise ValidationError(
            "No linked rental payment allocations were found."
        )

    total_applied = sum(
        (
            Decimal(str(payment.amount))
            for payment in payments
        ),
        Decimal("0.00"),
    )

    bank_amount = Decimal(str(bank_item.money_in))

    if total_applied != bank_amount:
        raise ValidationError(
            f"Rental payment allocations total "
            f"{total_applied}, but bank receipt is "
            f"{bank_amount}."
        )

    company = Company.objects.get(
        name="AfriAxis Group"
    )

    reference = (
        f"RENTAPPLY-BANK-{bank_item.id}"
    )

    existing = JournalEntry.objects.filter(
        company=company,
        reference=reference,
    ).first()

    if existing:
        return existing

    descriptions = ", ".join(
        (
            f"Rent {payment.rental_rent_id} "
            f"{payment.rental_rent.tenant}"
            for payment in payments
        )
    )

    journal = create_journal_entry(
        company=company,
        entry_date=min(
            payment.rental_rent.billing_month
            for payment in payments
        ),
        reference=reference,
        description=(
            f"Apply tenant advance from bank transaction "
            f"{bank_item.id}: {descriptions}"
        ),
        lines=[
            {
                "account_code": "2200",
                "debit": total_applied,
                "description": (
                    f"Tenant advance applied - "
                    f"{bank_item.matched_tenant}"
                ),
            },
            {
                "account_code": "1100",
                "credit": total_applied,
                "description": (
                    f"Rent receivable settled - "
                    f"{bank_item.matched_tenant}"
                ),
            },
        ],
        user=user,
        auto_post=True,
    )

    return journal
