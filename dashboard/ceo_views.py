from calendar import month_abbr
from datetime import date
from decimal import Decimal

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
)
from django.shortcuts import render
from django.utils import timezone


ZERO = Decimal("0.00")


def get_model(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def get_current_company(request):
    user = request.user

    possible_profiles = [
        getattr(user, "userprofile", None),
        getattr(user, "profile", None),
        getattr(user, "employee_profile", None),
    ]

    for profile in possible_profiles:
        if profile and getattr(profile, "company_id", None):
            return profile.company

        if profile and getattr(profile, "branch_id", None):
            branch = profile.branch

            if getattr(branch, "company_id", None):
                return branch.company

    Company = get_model("enterprise", "Company")

    if Company is None:
        return None

    queryset = Company.objects.all()
    fields = {
        field.name
        for field in Company._meta.get_fields()
    }

    if "active" in fields:
        queryset = queryset.filter(active=True)

    return queryset.order_by("id").first()


def company_queryset(model, company):
    if model is None:
        return None

    queryset = model.objects.all()

    if company is None:
        return queryset.none()

    field_names = {
        field.name
        for field in model._meta.get_fields()
    }

    if "company" in field_names:
        return queryset.filter(company=company)

    if "branch" in field_names:
        return queryset.filter(branch__company=company)

    if "purchase_order" in field_names:
        return queryset.filter(
            purchase_order__company=company
        )

    if "supplier_invoice" in field_names:
        return queryset.filter(
            supplier_invoice__purchase_order__company=company
        )

    if "invoice" in field_names:
        invoice_field = model._meta.get_field("invoice")
        invoice_model = getattr(
            invoice_field,
            "related_model",
            None,
        )

        if invoice_model:
            invoice_fields = {
                field.name
                for field in invoice_model._meta.get_fields()
            }

            if "company" in invoice_fields:
                return queryset.filter(invoice__company=company)

    if "warehouse" in field_names:
        warehouse_field = model._meta.get_field("warehouse")
        warehouse_model = getattr(
            warehouse_field,
            "related_model",
            None,
        )

        if warehouse_model:
            warehouse_fields = {
                field.name
                for field in warehouse_model._meta.get_fields()
            }

            if "company" in warehouse_fields:
                return queryset.filter(
                    warehouse__company=company
                )

            if "branch" in warehouse_fields:
                return queryset.filter(
                    warehouse__branch__company=company
                )

    return queryset.none()


def decimal_sum(queryset, field_name):
    if queryset is None:
        return ZERO

    fields = {
        field.name
        for field in queryset.model._meta.get_fields()
    }

    if field_name not in fields:
        return ZERO

    return (
        queryset.aggregate(total=Sum(field_name))["total"]
        or ZERO
    )


def net_debit(queryset):
    if queryset is None:
        return ZERO

    result = queryset.aggregate(
        debit_total=Sum("debit"),
        credit_total=Sum("credit"),
    )

    return (
        (result["debit_total"] or ZERO)
        - (result["credit_total"] or ZERO)
    )


def net_credit(queryset):
    if queryset is None:
        return ZERO

    result = queryset.aggregate(
        debit_total=Sum("debit"),
        credit_total=Sum("credit"),
    )

    return (
        (result["credit_total"] or ZERO)
        - (result["debit_total"] or ZERO)
    )


def invoice_balance(queryset):
    if queryset is None:
        return ZERO

    fields = {
        field.name
        for field in queryset.model._meta.get_fields()
    }

    if "balance" in fields:
        return decimal_sum(queryset, "balance")

    if "total_amount" in fields and "amount_paid" in fields:
        expression = ExpressionWrapper(
            F("total_amount") - F("amount_paid"),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        )

        return (
            queryset.aggregate(total=Sum(expression))["total"]
            or ZERO
        )

    return ZERO


def month_start_shift(value, months):
    year = value.year
    month = value.month + months

    while month <= 0:
        month += 12
        year -= 1

    while month > 12:
        month -= 12
        year += 1

    return date(year, month, 1)


def build_monthly_analytics(lines, today):
    rows = []

    for offset in range(-5, 1):
        start = month_start_shift(today.replace(day=1), offset)
        end = month_start_shift(start, 1)

        month_lines = lines.filter(
            journal_entry__entry_date__gte=start,
            journal_entry__entry_date__lt=end,
        )

        revenue_lines = month_lines.filter(
            Q(account__account_type__category__icontains="revenue")
            | Q(account__account_type__category__icontains="income")
            | Q(account__account_type__name__icontains="revenue")
            | Q(account__account_type__name__icontains="income")
            | Q(account__name__icontains="sales revenue")
        )

        cogs_lines = month_lines.filter(
            Q(account__name__icontains="cost of goods sold")
            | Q(account__name__icontains="cogs")
            | Q(account__account_type__category__icontains="cost of sales")
        )

        expense_lines = month_lines.filter(
            Q(account__account_type__category__icontains="expense")
            | Q(account__account_type__name__icontains="expense")
            | Q(account__code__startswith="6")
        ).exclude(
            Q(account__name__icontains="cost of goods sold")
            | Q(account__name__icontains="cogs")
        )

        revenue = max(net_credit(revenue_lines), ZERO)
        cogs = max(net_debit(cogs_lines), ZERO)
        expenses = max(net_debit(expense_lines), ZERO)
        profit = revenue - cogs - expenses

        rows.append(
            {
                "label": f"{month_abbr[start.month]} {start.year}",
                "revenue": revenue,
                "expenses": cogs + expenses,
                "profit": profit,
            }
        )

    maximum = max(
        [
            abs(value)
            for row in rows
            for value in (
                row["revenue"],
                row["expenses"],
                row["profit"],
            )
        ]
        + [Decimal("1.00")]
    )

    for row in rows:
        row["revenue_width"] = float(
            abs(row["revenue"]) / maximum * 100
        )
        row["expense_width"] = float(
            abs(row["expenses"]) / maximum * 100
        )
        row["profit_width"] = float(
            abs(row["profit"]) / maximum * 100
        )

    return rows


@login_required
def ceo_dashboard(request):
    company = get_current_company(request)
    today = timezone.localdate()
    month_start = today.replace(day=1)

    JournalEntry = get_model("accounting", "JournalEntry")
    JournalEntryLine = get_model(
        "accounting",
        "JournalEntryLine",
    )
    StockBalance = get_model("inventory", "StockBalance")
    StockMovement = get_model("inventory", "StockMovement")
    CustomerInvoice = get_model("billing", "Invoice")
    SupplierInvoice = get_model(
        "purchasing",
        "SupplierInvoice",
    )
    GoodsReceipt = get_model("purchasing", "GoodsReceipt")
    PurchaseOrder = get_model("purchasing", "PurchaseOrder")
    SupplierPayment = get_model(
        "purchasing",
        "SupplierPayment",
    )
    BankAccount = get_model("banking", "BankAccount")

    journals = company_queryset(JournalEntry, company)
    stock_balances = company_queryset(
        StockBalance,
        company,
    )
    stock_movements = company_queryset(
        StockMovement,
        company,
    )
    customer_invoices = company_queryset(
        CustomerInvoice,
        company,
    )
    supplier_invoices = company_queryset(
        SupplierInvoice,
        company,
    )
    goods_receipts = company_queryset(
        GoodsReceipt,
        company,
    )
    purchase_orders = company_queryset(
        PurchaseOrder,
        company,
    )
    supplier_payments = company_queryset(
        SupplierPayment,
        company,
    )
    bank_accounts = company_queryset(
        BankAccount,
        company,
    )

    if journals is not None:
        posted_journals = journals.filter(
            status="POSTED",
            entry_date__lte=today,
        )
        future_journals = journals.filter(
            status="POSTED",
            entry_date__gt=today,
        )
    else:
        posted_journals = None
        future_journals = None

    if posted_journals is not None:
        monthly_journals = posted_journals.filter(
            entry_date__gte=month_start,
            entry_date__lte=today,
        )
    else:
        monthly_journals = None

    if JournalEntryLine is not None and company is not None:
        ledger_lines = JournalEntryLine.objects.filter(
            journal_entry__company=company,
            journal_entry__status="POSTED",
            journal_entry__entry_date__lte=today,
        ).select_related(
            "journal_entry",
            "account",
            "account__account_type",
        )
    else:
        ledger_lines = None

    if ledger_lines is not None:
        revenue_lines = ledger_lines.filter(
            Q(account__account_type__category__icontains="revenue")
            | Q(account__account_type__category__icontains="income")
            | Q(account__account_type__name__icontains="revenue")
            | Q(account__account_type__name__icontains="income")
            | Q(account__name__icontains="sales revenue")
            | Q(account__code__startswith="4")
        )

        cogs_lines = ledger_lines.filter(
            Q(account__name__icontains="cost of goods sold")
            | Q(account__name__icontains="cogs")
            | Q(account__account_type__category__icontains="cost of sales")
            | Q(account__code__startswith="5")
        )

        operating_expense_lines = ledger_lines.filter(
            Q(account__account_type__category__icontains="expense")
            | Q(account__account_type__name__icontains="expense")
            | Q(account__code__startswith="6")
        ).exclude(
            Q(account__name__icontains="cost of goods sold")
            | Q(account__name__icontains="cogs")
        )

        cash_lines = ledger_lines.filter(
            Q(account__name__icontains="cash")
            | Q(account__name__icontains="bank")
            | Q(account__code="1000")
        )

        receivable_lines = ledger_lines.filter(
            Q(account__name__icontains="accounts receivable")
            | Q(account__name__icontains="trade receivable")
            | Q(account__code="1100")
        )

        payable_lines = ledger_lines.filter(
            Q(account__name__icontains="accounts payable")
            | Q(account__name__icontains="trade payable")
            | Q(account__code="2000")
        )

        ledger_revenue = max(
            net_credit(revenue_lines),
            ZERO,
        )
        cost_of_goods_sold = max(
            net_debit(cogs_lines),
            ZERO,
        )
        operating_expenses = max(
            net_debit(operating_expense_lines),
            ZERO,
        )
        ledger_cash = net_debit(cash_lines)
        ledger_receivables = net_debit(receivable_lines)
        ledger_payables = net_credit(payable_lines)

        monthly_analytics = build_monthly_analytics(
            ledger_lines,
            today,
        )
    else:
        ledger_revenue = ZERO
        cost_of_goods_sold = ZERO
        operating_expenses = ZERO
        ledger_cash = ZERO
        ledger_receivables = ZERO
        ledger_payables = ZERO
        monthly_analytics = []

    gross_profit = ledger_revenue - cost_of_goods_sold
    net_profit = gross_profit - operating_expenses

    inventory_value = ZERO

    if stock_balances is not None:
        balance_fields = {
            field.name
            for field in StockBalance._meta.get_fields()
        }

        if "quantity" in balance_fields:
            cost_field = None

            if "average_cost" in balance_fields:
                cost_field = "average_cost"
            elif "unit_cost" in balance_fields:
                cost_field = "unit_cost"

            if cost_field:
                expression = ExpressionWrapper(
                    F("quantity") * F(cost_field),
                    output_field=DecimalField(
                        max_digits=20,
                        decimal_places=2,
                    ),
                )

                inventory_value = (
                    stock_balances.aggregate(
                        total=Sum(expression)
                    )["total"]
                    or ZERO
                )

    bank_balance = ledger_cash

    if bank_balance == ZERO and bank_accounts is not None:
        bank_fields = {
            field.name
            for field in BankAccount._meta.get_fields()
        }

        for field_name in [
            "current_balance",
            "balance",
            "book_balance",
        ]:
            if field_name in bank_fields:
                bank_balance = decimal_sum(
                    bank_accounts,
                    field_name,
                )
                break

    receivables = ledger_receivables

    if receivables == ZERO:
        receivables = invoice_balance(customer_invoices)

    payables = ledger_payables

    if payables == ZERO:
        payables = invoice_balance(supplier_invoices)

    low_stock_items = []

    if stock_balances is not None:
        balance_fields = {
            field.name
            for field in StockBalance._meta.get_fields()
        }

        if "quantity" in balance_fields:
            low_stock_items = list(
                stock_balances
                .select_related("product", "warehouse")
                .filter(quantity__lte=5)
                .order_by("quantity")[:10]
            )

    recent_journals = []

    if posted_journals is not None:
        recent_journals = list(
            posted_journals.order_by(
                "-entry_date",
                "-created_at",
                "-id",
            )[:8]
        )

    context = {
        "company": company,
        "today": today,
        "bank_balance": bank_balance,
        "inventory_value": inventory_value,
        "receivables": receivables,
        "payables": payables,
        "ledger_revenue": ledger_revenue,
        "cost_of_goods_sold": cost_of_goods_sold,
        "gross_profit": gross_profit,
        "operating_expenses": operating_expenses,
        "net_profit": net_profit,
        "monthly_analytics": monthly_analytics,
        "future_journal_count": (
            future_journals.count()
            if future_journals is not None
            else 0
        ),
        "journal_count": (
            posted_journals.count()
            if posted_journals is not None
            else 0
        ),
        "monthly_journal_count": (
            monthly_journals.count()
            if monthly_journals is not None
            else 0
        ),
        "invoice_count": (
            customer_invoices.count()
            if customer_invoices is not None
            else 0
        ),
        "supplier_invoice_count": (
            supplier_invoices.count()
            if supplier_invoices is not None
            else 0
        ),
        "stock_movement_count": (
            stock_movements.count()
            if stock_movements is not None
            else 0
        ),
        "goods_receipt_count": (
            goods_receipts.count()
            if goods_receipts is not None
            else 0
        ),
        "purchase_order_count": (
            purchase_orders.count()
            if purchase_orders is not None
            else 0
        ),
        "supplier_payment_count": (
            supplier_payments.count()
            if supplier_payments is not None
            else 0
        ),
        "low_stock_items": low_stock_items,
        "recent_journals": recent_journals,
    }

    return render(
        request,
        "dashboard/ceo_dashboard.html",
        context,
    )
