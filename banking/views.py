from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from payments.models import Payment
from rentals.models import Rent

from .forms import BankStatementUploadForm
from .models import BankTransaction
from .utils import process_bank_statement


@login_required
def reconciliation_dashboard(request):
    transactions = (
        BankTransaction.objects
        .select_related(
            "matched_tenant",
            "matched_house",
            "matched_house__apartment",
        )
        .order_by("-transaction_date", "-id")
    )

    context = {
        "transactions": transactions[:200],
        "total_transactions": transactions.count(),
        "approved": transactions.filter(
            match_status="approved",
        ).count(),
        "pending": transactions.filter(
            match_status="pending",
        ).count(),
        "rejected": transactions.filter(
            match_status="rejected",
        ).count(),
        "unknown": transactions.filter(
            suggested_category="unknown",
        ).count(),
        "total_money_in": (
            transactions.aggregate(total=Sum("money_in"))["total"]
            or Decimal("0")
        ),
        "total_money_out": (
            transactions.aggregate(total=Sum("money_out"))["total"]
            or Decimal("0")
        ),
    }

    return render(
        request,
        "banking/reconciliation.html",
        context,
    )


@login_required
def upload_statement(request):
    if request.method == "POST":
        form = BankStatementUploadForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            upload = form.save(commit=False)
            upload.uploaded_by = request.user
            upload.save()

            try:
                process_bank_statement(upload)
                messages.success(
                    request,
                    "Bank statement uploaded and processed.",
                )
            except Exception as exc:
                messages.error(
                    request,
                    f"Processing failed: {exc}",
                )

            return redirect("bank_reconciliation")
    else:
        form = BankStatementUploadForm()

    return render(
        request,
        "banking/upload_statement.html",
        {"form": form},
    )


def _payment_queryset(transaction):
    return Payment.objects.filter(
        payment_method="BANK",
        transaction_desc=transaction.description,
    )


@db_transaction.atomic
def _post_bank_transaction(transaction):
    """
    Post one bank transaction to the matched tenant and house.

    Returns:
        posted: bool
        message: str
    """
    if transaction.match_status == "approved":
        return False, "Transaction is already approved."

    if not transaction.matched_tenant_id:
        return False, "Cannot approve: no matched tenant."

    if not transaction.matched_house_id:
        return False, "Cannot approve: no matched house."

    if transaction.money_in <= 0:
        return False, "Cannot approve: transaction has no money in."

    existing_payments = _payment_queryset(transaction)

    # If linked payment rows already exist, do not post twice.
    if existing_payments.filter(
        rental_rent__isnull=False,
    ).exists():
        transaction.match_status = "approved"
        transaction.save(update_fields=["match_status"])

        return False, "This transaction was already posted."

    # Remove old orphan rows created by the previous broken approval code.
    existing_payments.filter(
        rental_rent__isnull=True,
    ).delete()

    rents = (
        Rent.objects
        .select_for_update()
        .filter(
            tenant=transaction.matched_tenant,
            house=transaction.matched_house,
            paid=False,
            closed=False,
        )
        .order_by("billing_month", "due_date", "id")
    )

    if not rents.exists():
        return False, (
            "No open rent record exists for the matched tenant and house."
        )

    remaining = Decimal(transaction.money_in)
    total_applied = Decimal("0")

    for rent in rents:
        outstanding = Decimal(rent.amount) - Decimal(rent.amount_paid)

        if outstanding <= 0:
            continue

        applied = min(remaining, outstanding)

        rent.amount_paid = Decimal(rent.amount_paid) + applied
        rent.save()

        Payment.objects.create(
            rental_rent=rent,
            amount=applied,
            phone_number="",
            account_reference="BANK",
            transaction_desc=transaction.description,
            mpesa_receipt_number=transaction.reference,
            payment_method="BANK",
            status="SUCCESS",
        )

        total_applied += applied
        remaining -= applied

        if remaining <= 0:
            break

    if total_applied <= 0:
        return False, "No outstanding rent balance was available."

    # Preserve excess funds as an unallocated tenant advance.
    if remaining > 0:
        Payment.objects.create(
            rental_rent=None,
            amount=remaining,
            phone_number="",
            account_reference="BANK-ADVANCE",
            transaction_desc=transaction.description,
            mpesa_receipt_number=transaction.reference,
            payment_method="BANK",
            status="SUCCESS",
        )

    transaction.match_status = "approved"
    transaction.suggested_category = "rent"
    transaction.save(
        update_fields=[
            "match_status",
            "suggested_category",
        ]
    )

    if remaining > 0:
        return True, (
            f"Transaction approved. KES {total_applied:,.2f} applied "
            f"to rent and KES {remaining:,.2f} recorded as an advance."
        )

    return True, (
        f"Transaction approved. KES {total_applied:,.2f} applied to rent."
    )


@login_required
def approve_transaction(request, transaction_id):
    transaction = get_object_or_404(
        BankTransaction,
        id=transaction_id,
    )

    posted, message = _post_bank_transaction(transaction)

    if posted:
        messages.success(request, message)
    else:
        messages.warning(request, message)

    return redirect("bank_reconciliation")


@login_required
def approve_all_high_confidence(request):
    transactions = (
        BankTransaction.objects
        .filter(
            match_status="pending",
            auto_matched=True,
            confidence__gte=95,
            money_in__gt=0,
            matched_tenant__isnull=False,
            matched_house__isnull=False,
        )
        .order_by("transaction_date", "id")
    )

    approved_count = 0
    skipped_count = 0

    for bank_item in transactions:
        posted, _message = _post_bank_transaction(bank_item)

        if posted:
            approved_count += 1
        else:
            skipped_count += 1

    messages.success(
        request,
        (
            f"Bulk approval complete. Approved: {approved_count}, "
            f"Skipped: {skipped_count}."
        ),
    )

    return redirect("bank_reconciliation")


@login_required
@db_transaction.atomic
def undo_transaction(request, transaction_id):
    bank_item = get_object_or_404(
        BankTransaction,
        id=transaction_id,
    )

    if bank_item.match_status != "approved":
        messages.warning(
            request,
            "Transaction is not approved.",
        )
        return redirect("bank_reconciliation")

    payments = list(
        _payment_queryset(bank_item)
        .select_related("rental_rent")
    )

    if not payments:
        bank_item.match_status = "pending"
        bank_item.save(update_fields=["match_status"])

        messages.warning(
            request,
            "No linked payment rows were found. Transaction returned to pending.",
        )
        return redirect("bank_reconciliation")

    reversed_total = Decimal("0")

    for payment in payments:
        rent = payment.rental_rent

        if rent:
            rent = (
                Rent.objects
                .select_for_update()
                .get(id=rent.id)
            )

            rent.amount_paid = max(
                Decimal("0"),
                Decimal(rent.amount_paid) - Decimal(payment.amount),
            )
            rent.save()

        reversed_total += Decimal(payment.amount)
        payment.delete()

    bank_item.match_status = "pending"
    bank_item.save(update_fields=["match_status"])

    messages.success(
        request,
        (
            f"Transaction reversed. KES {reversed_total:,.2f} removed "
            "from payments."
        ),
    )

    return redirect("bank_reconciliation")


@login_required
def reject_transaction(request, transaction_id):
    bank_item = get_object_or_404(
        BankTransaction,
        id=transaction_id,
    )

    if bank_item.match_status == "approved":
        messages.error(
            request,
            "Undo the approved transaction before rejecting it.",
        )
        return redirect("bank_reconciliation")

    bank_item.match_status = "rejected"
    bank_item.save(update_fields=["match_status"])

    messages.success(
        request,
        "Transaction rejected.",
    )

    return redirect("bank_reconciliation")
