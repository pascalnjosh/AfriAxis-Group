from accounts.decorators import finance_required
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from enterprise.models import Company

from .ledger_reports import get_general_ledger
from .models import Account
from .reports import (
    get_balance_sheet,
    get_profit_and_loss,
    get_trial_balance,
)


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None


def get_company():
    company = Company.objects.first()

    if company is None:
        raise Http404(
            "No company has been configured."
        )

    return company


@finance_required
def trial_balance(request):
    company = get_company()

    date_from = parse_date(
        request.GET.get("date_from")
    )
    date_to = parse_date(
        request.GET.get("date_to")
    )

    report = get_trial_balance(
        company=company,
        date_from=date_from,
        date_to=date_to,
    )

    return render(
        request,
        "accounting/trial_balance.html",
        {
            "company": company,
            "report": report,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@finance_required
def general_ledger(request):
    company = get_company()

    account = None
    rows = []

    date_from = parse_date(
        request.GET.get("date_from")
    )
    date_to = parse_date(
        request.GET.get("date_to")
    )

    account_id = request.GET.get("account")

    accounts = Account.objects.filter(
        company=company,
        active=True,
    ).order_by("code")

    if account_id:
        account = get_object_or_404(
            accounts,
            pk=account_id,
        )

        rows = get_general_ledger(
            account=account,
            date_from=date_from,
            date_to=date_to,
        )

    return render(
        request,
        "accounting/general_ledger.html",
        {
            "company": company,
            "accounts": accounts,
            "selected_account": account,
            "rows": rows,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@finance_required
def profit_and_loss(request):
    company = get_company()

    date_from = parse_date(
        request.GET.get("date_from")
    )
    date_to = parse_date(
        request.GET.get("date_to")
    )

    report = get_profit_and_loss(
        company=company,
        date_from=date_from,
        date_to=date_to,
    )

    return render(
        request,
        "accounting/profit_and_loss.html",
        {
            "company": company,
            "report": report,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@finance_required
def balance_sheet(request):
    company = get_company()

    as_of = parse_date(
        request.GET.get("as_of")
    )

    report = get_balance_sheet(
        company=company,
        as_of=as_of,
    )

    return render(
        request,
        "accounting/balance_sheet.html",
        {
            "company": company,
            "report": report,
            "as_of": as_of,
        },
    )


@finance_required
def cash_flow(request):
    from .reports import get_cash_flow

    company = get_company()

    as_of = parse_date(
        request.GET.get("as_of")
    )

    report = get_cash_flow(
        company=company,
        as_of=as_of,
    )

    return render(
        request,
        "accounting/cash_flow.html",
        {
            "company": company,
            "report": report,
            "as_of": as_of,
        },
    )

from decimal import Decimal

from django.utils import timezone

from sales.models import Customer, SalesInvoice, SalesReceipt
from purchasing.models import Supplier, SupplierInvoice, SupplierPayment


def _aging_bucket(days_overdue):
    if days_overdue <= 0:
        return "current"

    if days_overdue <= 30:
        return "days_1_30"

    if days_overdue <= 60:
        return "days_31_60"

    if days_overdue <= 90:
        return "days_61_90"

    return "days_over_90"


def _empty_aging_totals():
    return {
        "current": Decimal("0.00"),
        "days_1_30": Decimal("0.00"),
        "days_31_60": Decimal("0.00"),
        "days_61_90": Decimal("0.00"),
        "days_over_90": Decimal("0.00"),
        "total": Decimal("0.00"),
    }


@finance_required
def aged_receivables(request):
    as_of = parse_date(
        request.GET.get("as_of")
    ) or timezone.localdate()

    invoices = (
        SalesInvoice.objects
        .exclude(status__in=["DRAFT", "CANCELLED", "PAID"])
        .order_by(
            "due_date",
            "invoice_number",
        )
    )

    rows = []
    totals = _empty_aging_totals()

    for invoice in invoices:
        balance = (
            Decimal(str(invoice.total_amount))
            - Decimal(str(invoice.amount_paid))
        )

        if balance <= Decimal("0.00"):
            continue

        due_date = invoice.due_date or invoice.invoice_date
        days_overdue = (as_of - due_date).days
        bucket = _aging_bucket(days_overdue)

        row = {
            "invoice": invoice,
            "customer": invoice.customer,
            "due_date": due_date,
            "days_overdue": max(days_overdue, 0),
            "balance": balance,
            "current": Decimal("0.00"),
            "days_1_30": Decimal("0.00"),
            "days_31_60": Decimal("0.00"),
            "days_61_90": Decimal("0.00"),
            "days_over_90": Decimal("0.00"),
        }

        row[bucket] = balance
        totals[bucket] += balance
        totals["total"] += balance
        rows.append(row)

    return render(
        request,
        "accounting/aged_receivables.html",
        {
            "rows": rows,
            "totals": totals,
            "as_of": as_of,
        },
    )


@finance_required
def aged_payables(request):
    as_of = parse_date(
        request.GET.get("as_of")
    ) or timezone.localdate()

    invoices = (
        SupplierInvoice.objects
        .exclude(status__in=["DRAFT", "CANCELLED", "PAID"])
        .select_related(
            "supplier",
            "currency",
        )
        .order_by(
            "due_date",
            "invoice_number",
        )
    )

    rows = []
    totals = _empty_aging_totals()

    for invoice in invoices:
        balance = (
            Decimal(str(invoice.total_amount))
            - Decimal(str(invoice.amount_paid))
        )

        if balance <= Decimal("0.00"):
            continue

        due_date = invoice.due_date or invoice.invoice_date
        days_overdue = (as_of - due_date).days
        bucket = _aging_bucket(days_overdue)

        row = {
            "invoice": invoice,
            "supplier": invoice.supplier,
            "due_date": due_date,
            "days_overdue": max(days_overdue, 0),
            "balance": balance,
            "current": Decimal("0.00"),
            "days_1_30": Decimal("0.00"),
            "days_31_60": Decimal("0.00"),
            "days_61_90": Decimal("0.00"),
            "days_over_90": Decimal("0.00"),
        }

        row[bucket] = balance
        totals[bucket] += balance
        totals["total"] += balance
        rows.append(row)

    return render(
        request,
        "accounting/aged_payables.html",
        {
            "rows": rows,
            "totals": totals,
            "as_of": as_of,
        },
    )


@finance_required
def customer_statement(request):
    customer_id = request.GET.get("customer", "").strip()

    date_from = parse_date(
        request.GET.get("date_from")
    )
    date_to = parse_date(
        request.GET.get("date_to")
    )

    customers = (
        Customer.objects
        .filter(active=True)
        .order_by(
            "customer_code",
            "name",
        )
    )

    transactions = []
    opening_balance = Decimal("0.00")
    running_balance = Decimal("0.00")
    customer_invoices = SalesInvoice.objects.none()

    if customer_id:
        customer = get_object_or_404(
            customers,
            pk=customer_id,
        )

        customer_invoices = SalesInvoice.objects.filter(
            customer=customer,
        ).exclude(
            status__in=["DRAFT", "CANCELLED"],
        )

        if date_from:
            opening_invoices = customer_invoices.filter(
                invoice_date__lt=date_from,
            )

            opening_charges = sum(
                (
                    invoice.total_amount
                    for invoice in opening_invoices
                ),
                Decimal("0.00"),
            )

            opening_payments = sum(
                (
                    payment.amount
                    for payment in SalesReceipt.objects.filter(
                        customer=customer,
                        receipt_date__lt=date_from,
                        status="POSTED",
                    )
                ),
                Decimal("0.00"),
            )

            opening_balance = (
                opening_charges - opening_payments
            )

        invoice_queryset = customer_invoices

        if date_from:
            invoice_queryset = invoice_queryset.filter(
                invoice_date__gte=date_from,
            )

        if date_to:
            invoice_queryset = invoice_queryset.filter(
                invoice_date__lte=date_to,
            )

        for invoice in invoice_queryset:
            transactions.append(
                {
                    "date": invoice.invoice_date,
                    "type": "Invoice",
                    "reference": invoice.invoice_number,
                    "description": (
                        invoice.get_invoice_type_display()
                        if hasattr(
                            invoice,
                            "get_invoice_type_display",
                        )
                        else "Customer Invoice"
                    ),
                    "charge": invoice.total_amount,
                    "payment": Decimal("0.00"),
                    "sort_order": 1,
                }
            )

        payment_queryset = SalesReceipt.objects.filter(
            customer=customer,
            status="POSTED",
        ).select_related("sales_invoice")

        if date_from:
            payment_queryset = payment_queryset.filter(
                receipt_date__gte=date_from,
            )

        if date_to:
            payment_queryset = payment_queryset.filter(
                receipt_date__lte=date_to,
            )

        for payment in payment_queryset:
            transactions.append(
                {
                    "date": payment.receipt_date,
                    "type": "Payment",
                    "reference": (
                        payment.receipt_number
                    ),
                    "description": (
                        f"Payment for "
                        f"{payment.sales_invoice.invoice_number}"
                    ),
                    "charge": Decimal("0.00"),
                    "payment": payment.amount,
                    "sort_order": 2,
                }
            )

        transactions.sort(
            key=lambda item: (
                item["date"],
                item["sort_order"],
                item["reference"],
            )
        )

        running_balance = opening_balance

        for transaction in transactions:
            running_balance += transaction["charge"]
            running_balance -= transaction["payment"]
            transaction["balance"] = running_balance

    total_charges = sum(
        (
            transaction["charge"]
            for transaction in transactions
        ),
        Decimal("0.00"),
    )

    total_payments = sum(
        (
            transaction["payment"]
            for transaction in transactions
        ),
        Decimal("0.00"),
    )

    return render(
        request,
        "accounting/customer_statement.html",
        {
            "customers": customers,
            "selected_customer": customer if customer_id else None,
            "transactions": transactions,
            "opening_balance": opening_balance,
            "total_charges": total_charges,
            "total_payments": total_payments,
            "closing_balance": running_balance,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@finance_required
def supplier_statement(request):
    supplier_id = request.GET.get("supplier")

    date_from = parse_date(
        request.GET.get("date_from")
    )
    date_to = parse_date(
        request.GET.get("date_to")
    )

    suppliers = Supplier.objects.filter(
        active=True,
    ).order_by(
        "supplier_code",
        "name",
    )

    supplier = None
    transactions = []
    opening_balance = Decimal("0.00")
    running_balance = Decimal("0.00")

    if supplier_id:
        supplier = get_object_or_404(
            suppliers,
            pk=supplier_id,
        )

        supplier_invoices = SupplierInvoice.objects.filter(
            supplier=supplier,
        ).exclude(
            status__in=["DRAFT", "CANCELLED"],
        )

        if date_from:
            opening_invoices = supplier_invoices.filter(
                invoice_date__lt=date_from,
            )

            opening_bills = sum(
                (
                    invoice.total_amount
                    for invoice in opening_invoices
                ),
                Decimal("0.00"),
            )

            opening_payments = sum(
                (
                    payment.amount
                    for payment in SupplierPayment.objects.filter(
                        supplier=supplier,
                        payment_date__lt=date_from,
                    )
                ),
                Decimal("0.00"),
            )

            opening_balance = (
                opening_bills - opening_payments
            )

        invoice_queryset = supplier_invoices

        if date_from:
            invoice_queryset = invoice_queryset.filter(
                invoice_date__gte=date_from,
            )

        if date_to:
            invoice_queryset = invoice_queryset.filter(
                invoice_date__lte=date_to,
            )

        for invoice in invoice_queryset:
            transactions.append(
                {
                    "date": invoice.invoice_date,
                    "type": "Supplier Invoice",
                    "reference": invoice.invoice_number,
                    "description": "Supplier invoice",
                    "bill": invoice.total_amount,
                    "payment": Decimal("0.00"),
                    "sort_order": 1,
                }
            )

        payment_queryset = SupplierPayment.objects.filter(
            supplier=supplier,
        ).select_related(
            "supplier_invoice",
        )

        if date_from:
            payment_queryset = payment_queryset.filter(
                payment_date__gte=date_from,
            )

        if date_to:
            payment_queryset = payment_queryset.filter(
                payment_date__lte=date_to,
            )

        for payment in payment_queryset:
            invoice_number = ""

            if payment.supplier_invoice:
                invoice_number = (
                    payment.supplier_invoice.invoice_number
                )

            description = "Supplier payment"

            if invoice_number:
                description = (
                    f"Payment for {invoice_number}"
                )

            transactions.append(
                {
                    "date": payment.payment_date,
                    "type": "Payment",
                    "reference": (
                        payment.reference
                        or f"PAY-{payment.pk}"
                    ),
                    "description": description,
                    "bill": Decimal("0.00"),
                    "payment": payment.amount,
                    "sort_order": 2,
                }
            )

        transactions.sort(
            key=lambda item: (
                item["date"],
                item["sort_order"],
                item["reference"],
            )
        )

        running_balance = opening_balance

        for transaction in transactions:
            running_balance += transaction["bill"]
            running_balance -= transaction["payment"]
            transaction["balance"] = running_balance

    total_bills = sum(
        (
            transaction["bill"]
            for transaction in transactions
        ),
        Decimal("0.00"),
    )

    total_payments = sum(
        (
            transaction["payment"]
            for transaction in transactions
        ),
        Decimal("0.00"),
    )

    return render(
        request,
        "accounting/supplier_statement.html",
        {
            "suppliers": suppliers,
            "selected_supplier": supplier,
            "transactions": transactions,
            "opening_balance": opening_balance,
            "total_bills": total_bills,
            "total_payments": total_payments,
            "closing_balance": running_balance,
            "date_from": date_from,
            "date_to": date_to,
        },
    )










