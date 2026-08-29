from accounts.decorators import (
    audit_required,
    finance_required,
    get_user_company_ids,
)
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Sum

from accounting.models import Account, JournalEntry, JournalEntryLine
from .models import (
    BankAccount,
    BankStatementUpload,
)
from accounting.posting import create_journal_entry, reverse_journal_entry
from django.shortcuts import get_object_or_404, redirect, render

from payments.models import Payment
from rentals.models import Rent
from rentals.services import (
    apply_rent_bank_advance,
    post_rent_bank_advance,
)

from .forms import BankStatementUploadForm
from .models import BankTransaction
from .utils import process_bank_statement


def _bank_accounts_for_user(user):
    """
    Return active bank accounts available to the user.
    """

    queryset = (
        BankAccount.objects
        .filter(active=True)
        .select_related(
            "company",
            "apartment",
        )
    )

    company_ids = get_user_company_ids(
        user
    )

    if company_ids is None:
        return queryset

    return queryset.filter(
        company_id__in=company_ids,
    )


def _bank_transactions_for_user(user):
    """
    Restrict bank transactions to permitted bank accounts.
    """

    return BankTransaction.objects.filter(
        bank_account__in=_bank_accounts_for_user(
            user
        )
    )


def _statement_uploads_for_user(user):
    """
    Restrict statement uploads to permitted bank accounts.
    """

    return BankStatementUpload.objects.filter(
        bank_account__in=_bank_accounts_for_user(
            user
        )
    )


@audit_required
def reconciliation_dashboard(request):
    transactions = (
        _bank_transactions_for_user(
            request.user
        )
        .select_related(
            "bank_account",
            "matched_tenant",
            "matched_house",
            "matched_house__apartment",
            "matched_sales_receipt",
            "matched_supplier_payment",
        )
        .order_by("-transaction_date", "-id")
    )

    latest_upload = (
        _statement_uploads_for_user(
            request.user
        )
        .filter(processed=True)
        .select_related("bank_account")
        .order_by("-uploaded_at", "-id")
        .first()
    )

    statement_closing_balance = Decimal("0.00")
    gl_cash_balance = Decimal("0.00")
    reconciliation_difference = Decimal("0.00")
    reconciliation_status = "NO STATEMENT"
    statement_date = None
    bank_account = None

    statement_transactions = BankTransaction.objects.none()

    if latest_upload:
        bank_account = latest_upload.bank_account

        statement_transactions = (
            BankTransaction.objects
            .filter(statement_upload=latest_upload)
            .order_by("transaction_date", "id")
        )

        last_statement_transaction = (
            statement_transactions.last()
        )

        if last_statement_transaction:
            statement_date = (
                last_statement_transaction.transaction_date
            )

            statement_closing_balance = Decimal(
                str(last_statement_transaction.balance)
            )

            cash_account = (
                Account.objects
                .filter(
                    company=bank_account.company,
                    code="1000",
                    active=True,
                )
                .first()
            )

            if cash_account:
                cash_lines = (
                    JournalEntryLine.objects
                    .filter(
                        account=cash_account,
                        journal_entry__status="POSTED",
                        journal_entry__entry_date__lte=statement_date,
                    )
                )

                gl_cash_balance = sum(
                    (
                        Decimal(str(line.debit))
                        - Decimal(str(line.credit))
                        for line in cash_lines
                    ),
                    Decimal("0.00"),
                )

            reconciliation_difference = (
                statement_closing_balance
                - gl_cash_balance
            )

            if (
                reconciliation_difference
                == Decimal("0.00")
            ):
                reconciliation_status = "BALANCED"
            else:
                reconciliation_status = (
                    "OUT OF BALANCE"
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
            transactions.aggregate(
                total=Sum("money_in")
            )["total"]
            or Decimal("0.00")
        ),

        "total_money_out": (
            transactions.aggregate(
                total=Sum("money_out")
            )["total"]
            or Decimal("0.00")
        ),

        "bank_account": bank_account,
        "latest_upload": latest_upload,
        "statement_date": statement_date,

        "statement_closing_balance": (
            statement_closing_balance
        ),

        "gl_cash_balance": gl_cash_balance,

        "reconciliation_difference": (
            reconciliation_difference
        ),

        "reconciliation_status": (
            reconciliation_status
        ),

        "statement_transactions": (
            statement_transactions.count()
        ),

        "statement_approved": (
            statement_transactions.filter(
                match_status="approved",
            ).count()
        ),

        "statement_pending": (
            statement_transactions.filter(
                match_status="pending",
            ).count()
        ),

        "statement_rejected": (
            statement_transactions.filter(
                match_status="rejected",
            ).count()
        ),

        "unallocated_receipts": (
            statement_transactions
            .filter(
                money_in__gt=0,
            )
            .exclude(
                match_status="approved",
            )
            .count()
        ),

        "bank_charge_rows": (
            statement_transactions.filter(
                money_out__gt=0,
            ).count()
        ),
    }

    return render(
        request,
        "banking/reconciliation.html",
        context,
    )

@finance_required
def upload_statement(request):
    allowed_accounts = _bank_accounts_for_user(
        request.user
    )

    if request.method == "POST":
        form = BankStatementUploadForm(
            request.POST,
            request.FILES,
        )

        form.fields[
            "bank_account"
        ].queryset = allowed_accounts

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

        form.fields[
            "bank_account"
        ].queryset = allowed_accounts

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
def _post_bank_transaction(transaction, user=None):
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

    # If linked rent payment rows already exist, keep the operation
    # idempotent but also ensure the accounting journals are active.
    if existing_payments.filter(
        rental_rent__isnull=False,
    ).exists():
        transaction.match_status = "approved"
        transaction.suggested_category = "rent"
        transaction.save(
            update_fields=[
                "match_status",
                "suggested_category",
            ]
        )

        post_rent_bank_advance(
            transaction,
            user=user,
        )

        apply_rent_bank_advance(
            transaction,
            user=user,
        )

        return False, (
            "This transaction was already posted; "
            "rent accounting was verified."
        )

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
        # Valid matched tenant/house with no open rent remaining.
        # Preserve the complete bank receipt as a tenant advance.
        Payment.objects.create(
            rental_rent=None,
            amount=Decimal(transaction.money_in),
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

        post_rent_bank_advance(
            transaction,
            user=user,
        )

        return True, (
            f"Transaction approved. KES "
            f"{Decimal(transaction.money_in):,.2f} "
            "recorded as a tenant advance."
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

    # Accounting: record the full bank receipt as tenant advance,
    # then apply only the amount allocated to rent.
    post_rent_bank_advance(
        transaction,
        user=user,
    )

    apply_rent_bank_advance(
        transaction,
        user=user,
    )

    if remaining > 0:
        return True, (
            f"Transaction approved. KES {total_applied:,.2f} applied "
            f"to rent and KES {remaining:,.2f} recorded as an advance."
        )

    return True, (
        f"Transaction approved. KES {total_applied:,.2f} applied to rent."
    )


def _post_bank_charge_transaction(transaction, user=None):
    if transaction.match_status == "approved":
        return False, "Transaction is already approved."

    if transaction.money_out <= 0:
        return False, "Cannot approve: transaction has no money out."

    bank_account = transaction.bank_account
    company = getattr(bank_account, "company", None)

    if company is None:
        return False, "Cannot approve: bank account has no company."

    reference = f"BANKCHG-{transaction.id}"

    description = (
        transaction.description
        or "Bank charge"
    )

    create_journal_entry(
        company=company,
        reference=reference,
        description=description,
        entry_date=transaction.transaction_date,
        user=user,
        auto_post=True,
        lines=[
            {
                "account_code": "6100",
                "debit": transaction.money_out,
                "credit": "0.00",
                "description": description,
            },
            {
                "account_code": "1000",
                "debit": "0.00",
                "credit": transaction.money_out,
                "description": description,
            },
        ],
    )

    transaction.match_status = "approved"
    transaction.suggested_category = "bank_charge"
    transaction.match_notes = (
        "Posted to 6100 Bank Charges "
        "against 1000 Cash and Bank."
    )

    transaction.save(
        update_fields=[
            "match_status",
            "suggested_category",
            "match_notes",
        ]
    )

    return True, "Bank charge posted and approved."


@finance_required
def approve_transaction(request, transaction_id):
    transaction = get_object_or_404(
        _bank_transactions_for_user(
            request.user
        ),
        id=transaction_id,
    )

    if (
        transaction.matched_sales_receipt_id
        or transaction.matched_supplier_payment_id
    ):
        posted, message = _approve_erp_bank_transaction(
            transaction
        )

    elif transaction.money_out > 0:
        description = str(
            transaction.description or ""
        ).upper()

        bank_charge_markers = (
            "EXCISE DUTY",
            "ACCOUNT STATEMENT CHARGE",
            "TRANSACTION + SMS CHARGE",
            "SMS CHARGE",
            "BANK CHARGE",
            "TRANSFER CHARGE",
            "LEDGER FEE",
            "SERVICE CHARGE",
            "COMMISSION",
        )

        is_bank_charge = any(
            marker in description
            for marker in bank_charge_markers
        )

        if is_bank_charge:
            posted, message = _post_bank_charge_transaction(
                transaction,
                user=request.user,
            )
        else:
            posted = False
            message = (
                "Money-out transaction requires Finance review. "
                "It was not posted as a bank charge."
            )

    else:
        posted, message = _post_bank_transaction(
            transaction,
            user=request.user,
        )

    if posted:
        messages.success(request, message)
    else:
        messages.warning(request, message)

    return redirect("bank_reconciliation")


@finance_required
def approve_all_high_confidence(request):
    transactions = (
        _bank_transactions_for_user(
            request.user
        )
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
        posted, _message = _post_bank_transaction(
            bank_item,
            user=request.user,
        )

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


@finance_required
@db_transaction.atomic
def undo_transaction(request, transaction_id):
    bank_item = get_object_or_404(
        _bank_transactions_for_user(
            request.user
        ).select_for_update(),
        id=transaction_id,
    )

    if bank_item.match_status != "approved":
        messages.warning(
            request,
            "Transaction is not approved.",
        )
        return redirect("bank_reconciliation")

    if bank_item.suggested_category == "bank_charge":
        reference = f"BANKCHG-{bank_item.id}"

        journal = (
            JournalEntry.objects
            .filter(
                company=bank_item.bank_account.company,
                reference=reference,
                status="POSTED",
            )
            .order_by("-id")
            .first()
        )

        if journal is None:
            messages.error(
                request,
                (
                    "Cannot undo bank charge: "
                    f"journal {reference} was not found."
                ),
            )
            return redirect("bank_reconciliation")

        reverse_journal_entry(
            journal_entry=journal,
            user=request.user,
            reason=(
                f"Undo bank transaction {bank_item.id}"
            ),
        )

        bank_item.match_status = "pending"
        bank_item.suggested_category = "bank_charge"
        bank_item.match_notes = (
            f"Bank charge journal {reference} reversed. "
            "Transaction returned to pending Finance review."
        )
        bank_item.save(
            update_fields=[
                "match_status",
                "suggested_category",
                "match_notes",
            ]
        )

        messages.success(
            request,
            (
                "Bank charge reversed and transaction "
                "returned to pending."
            ),
        )
        return redirect("bank_reconciliation")

    if bank_item.suggested_category == "rent":
        advance_reference = f"RENTADV-BANK-{bank_item.id}"
        apply_reference = f"RENTAPPLY-BANK-{bank_item.id}"

        company = (
            bank_item.matched_house.apartment.company
            if bank_item.matched_house_id
            else bank_item.bank_account.company
        )

        # Locate the latest active posted accounting entries.
        # Historical cycles remain in the ledger for audit purposes.
        advance_journal = None

        for candidate in (
            JournalEntry.objects
            .filter(
                company=company,
                reference__startswith=advance_reference,
                status="POSTED",
            )
            .order_by("-id")
        ):
            reversal_exists = JournalEntry.objects.filter(
                company=company,
                reference=f"REV-{candidate.journal_number}",
                status="POSTED",
            ).exists()

            if not reversal_exists:
                advance_journal = candidate
                break

        apply_journal = None

        for candidate in (
            JournalEntry.objects
            .filter(
                company=company,
                reference__startswith=apply_reference,
                status="POSTED",
            )
            .order_by("-id")
        ):
            reversal_exists = JournalEntry.objects.filter(
                company=company,
                reference=f"REV-{candidate.journal_number}",
                status="POSTED",
            ).exists()

            if not reversal_exists:
                apply_journal = candidate
                break

        if advance_journal is None:
            messages.error(
                request,
                (
                    "Cannot undo rent receipt: "
                    f"journal {advance_reference} was not found."
                ),
            )
            return redirect("bank_reconciliation")

        payments = list(
            _payment_queryset(bank_item)
            .select_for_update()
            .select_related("rental_rent")
            .order_by("id")
        )

        rental_payments = [
            payment
            for payment in payments
            if payment.rental_rent_id is not None
        ]

        allocated_total = sum(
            (
                Decimal(payment.amount)
                for payment in rental_payments
            ),
            Decimal("0.00"),
        )

        # If money was allocated to rent, the application journal
        # must exist before we alter operational balances.
        if allocated_total > 0 and apply_journal is None:
            messages.error(
                request,
                (
                    "Cannot undo rent receipt: "
                    f"journal {apply_reference} was not found."
                ),
            )
            return redirect("bank_reconciliation")

        # Reverse the allocation first:
        # Dr Accounts Receivable / Cr Tenant Advances.
        if apply_journal is not None:
            reverse_journal_entry(
                journal_entry=apply_journal,
                user=request.user,
                reason=(
                    f"Undo rent allocation for bank "
                    f"transaction {bank_item.id}"
                ),
            )

        # Reverse the original bank receipt:
        # Dr Tenant Advances / Cr Cash and Bank.
        reverse_journal_entry(
            journal_entry=advance_journal,
            user=request.user,
            reason=(
                f"Undo rent bank receipt "
                f"{bank_item.id}"
            ),
        )

        # Restore each affected rent obligation.
        for payment in rental_payments:
            rent = (
                Rent.objects
                .select_for_update()
                .get(id=payment.rental_rent_id)
            )

            restored_paid = (
                Decimal(rent.amount_paid)
                - Decimal(payment.amount)
            )

            if restored_paid < 0:
                raise ValueError(
                    f"Cannot undo bank transaction "
                    f"{bank_item.id}: rent {rent.id} "
                    "would have negative amount_paid."
                )

            rent.amount_paid = restored_paid
            rent.save()

        # Remove both allocated BANK payments and any
        # unallocated BANK-ADVANCE payment for this receipt.
        for payment in payments:
            payment.delete()

        bank_item.match_status = "pending"
        bank_item.suggested_category = "rent"
        bank_item.match_notes = (
            "Rent receipt accounting reversed. "
            "Payment allocations removed and transaction "
            "returned to pending Finance review."
        )
        bank_item.save(
            update_fields=[
                "match_status",
                "suggested_category",
                "match_notes",
            ]
        )

        messages.success(
            request,
            (
                "Rent receipt reversed, rent balances restored, "
                "and transaction returned to pending."
            ),
        )
        return redirect("bank_reconciliation")


@finance_required
def reject_transaction(request, transaction_id):
    bank_item = get_object_or_404(
        _bank_transactions_for_user(
            request.user
        ),
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


@db_transaction.atomic
def _approve_erp_bank_transaction(bank_item):
    bank_item = (
        BankTransaction.objects
        .select_for_update()
        .select_related(
            "bank_account",
            "matched_sales_receipt",
            "matched_sales_receipt__bank_account",
            "matched_supplier_payment",
            "matched_supplier_payment__bank_account",
        )
        .get(pk=bank_item.pk)
    )

    if bank_item.match_status == "approved":
        return False, "Transaction is already approved."

    if bank_item.matched_sales_receipt_id:
        receipt = bank_item.matched_sales_receipt

        if receipt.status != "POSTED":
            return False, (
                "Matched customer receipt is not posted."
            )

        if receipt.bank_account_id != bank_item.bank_account_id:
            return False, (
                "Customer receipt bank account does not match "
                "the statement transaction."
            )

        if Decimal(str(bank_item.money_in)) != Decimal(str(receipt.amount)):
            return False, (
                "Bank money-in amount does not match "
                "the customer receipt."
            )

        duplicate = (
            BankTransaction.objects
            .filter(
                matched_sales_receipt=receipt,
                match_status="approved",
            )
            .exclude(pk=bank_item.pk)
            .exists()
        )

        if duplicate:
            return False, (
                "This customer receipt is already reconciled "
                "to another bank transaction."
            )

        bank_item.match_status = "approved"
        bank_item.suggested_category = "customer_receipt"
        bank_item.match_notes = (
            f"Reconciled to customer receipt "
            f"{receipt.receipt_number}"
        )

        bank_item.save(
            update_fields=[
                "match_status",
                "suggested_category",
                "match_notes",
            ]
        )

        return True, (
            f"Bank transaction reconciled to "
            f"{receipt.receipt_number}."
        )

    if bank_item.matched_supplier_payment_id:
        payment = bank_item.matched_supplier_payment

        if not payment.posted:
            return False, (
                "Matched supplier payment is not posted."
            )

        if payment.bank_account_id != bank_item.bank_account_id:
            return False, (
                "Supplier payment bank account does not match "
                "the statement transaction."
            )

        if Decimal(str(bank_item.money_out)) != Decimal(str(payment.amount)):
            return False, (
                "Bank money-out amount does not match "
                "the supplier payment."
            )

        duplicate = (
            BankTransaction.objects
            .filter(
                matched_supplier_payment=payment,
                match_status="approved",
            )
            .exclude(pk=bank_item.pk)
            .exists()
        )

        if duplicate:
            return False, (
                "This supplier payment is already reconciled "
                "to another bank transaction."
            )

        bank_item.match_status = "approved"
        bank_item.suggested_category = "supplier_payment"
        bank_item.match_notes = (
            f"Reconciled to supplier payment "
            f"{payment.reference}"
        )

        bank_item.save(
            update_fields=[
                "match_status",
                "suggested_category",
                "match_notes",
            ]
        )

        return True, (
            f"Bank transaction reconciled to "
            f"{payment.reference}."
        )

    return False, "No ERP transaction is matched."















@finance_required
def delete_statement(request, upload_id):
    upload = get_object_or_404(
        _statement_uploads_for_user(
            request.user
        ).select_related(
            "bank_account",
            "bank_account__company",
            "bank_account__apartment",
        ),
        id=upload_id,
    )

    if request.method != "POST":
        messages.error(
            request,
            "Bank statements can only be deleted using the Delete button.",
        )
        return redirect("bank_reconciliation")

    account = upload.bank_account
    apartment = account.apartment

    transaction_count = BankTransaction.objects.filter(
        statement_upload=upload
    ).count()

    BankTransaction.objects.filter(
        statement_upload=upload
    ).delete()

    file_name = upload.file.name if upload.file else ""

    upload.delete()

    messages.success(
        request,
        (
            f"Wrong bank statement deleted successfully. "
            f"{transaction_count} imported transaction(s) removed. "
            f"Apartment: {apartment.name if apartment else 'N/A'}. "
            f"File: {file_name}."
        ),
    )

    return redirect("bank_reconciliation")




