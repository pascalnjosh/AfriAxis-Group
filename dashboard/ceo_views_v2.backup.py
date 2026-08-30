from decimal import Decimal

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.shortcuts import render
from django.utils import timezone


ZERO = Decimal("0.00")


def get_model(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def get_current_company(request):
    """
    Resolve the company belonging to the logged-in user.

    The function supports common profile relationships and safely falls back
    to the first active company during development.
    """
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

    fields = {field.name for field in Company._meta.get_fields()}

    queryset = Company.objects.all()

    if "active" in fields:
        queryset = queryset.filter(active=True)

    return queryset.order_by("id").first()


def company_queryset(model, company):
    if model is None:
        return None

    queryset = model.objects.all()
    field_names = {field.name for field in model._meta.get_fields()}

    if company is None:
        return queryset.none()

    if "company" in field_names:
        return queryset.filter(company=company)

    if "branch" in field_names:
        return queryset.filter(branch__company=company)

    if "purchase_order" in field_names:
        return queryset.filter(purchase_order__company=company)

    if "supplier_invoice" in field_names:
        return queryset.filter(
            supplier_invoice__purchase_order__company=company
        )

    if "invoice" in field_names:
        invoice_model = getattr(
            model._meta.get_field("invoice"),
            "related_model",
            None,
        )

        if invoice_model:
            invoice_fields = {
                field.name for field in invoice_model._meta.get_fields()
            }

            if "company" in invoice_fields:
                return queryset.filter(invoice__company=company)

    if "warehouse" in field_names:
        warehouse_model = getattr(
            model._meta.get_field("warehouse"),
            "related_model",
            None,
        )

        if warehouse_model:
            warehouse_fields = {
                field.name for field in warehouse_model._meta.get_fields()
            }

            if "company" in warehouse_fields:
                return queryset.filter(warehouse__company=company)

            if "branch" in warehouse_fields:
                return queryset.filter(
                    warehouse__branch__company=company
                )

    # Do not expose globally unscoped records on a multi-company dashboard.
    return queryset.none()


def decimal_sum(queryset, field_name):
    if queryset is None:
        return ZERO

    model_fields = {
        field.name for field in queryset.model._meta.get_fields()
    }

    if field_name not in model_fields:
        return ZERO

    result = queryset.aggregate(total=Sum(field_name))["total"]

    return result or ZERO


def invoice_balance(queryset):
    if queryset is None:
        return ZERO

    fields = {
        field.name for field in queryset.model._meta.get_fields()
    }

    if "balance" in fields:
        return decimal_sum(queryset, "balance")

    if "total_amount" in fields and "amount_paid" in fields:
        balance_expression = ExpressionWrapper(
            F("total_amount") - F("amount_paid"),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        )

        return (
            queryset.aggregate(total=Sum(balance_expression))["total"]
            or ZERO
        )

    return ZERO


@login_required
def ceo_dashboard(request):
    company = get_current_company(request)
    today = timezone.localdate()
    month_start = today.replace(day=1)

    JournalEntry = get_model("accounting", "JournalEntry")
    StockBalance = get_model("inventory", "StockBalance")
    StockMovement = get_model("inventory", "StockMovement")
    CustomerInvoice = get_model("billing", "Invoice")
    SupplierInvoice = get_model("purchasing", "SupplierInvoice")
    GoodsReceipt = get_model("purchasing", "GoodsReceipt")
    PurchaseOrder = get_model("purchasing", "PurchaseOrder")
    SupplierPayment = get_model("purchasing", "SupplierPayment")
    BankAccount = get_model("banking", "BankAccount")

    journals = company_queryset(JournalEntry, company)
    stock_balances = company_queryset(StockBalance, company)
    stock_movements = company_queryset(StockMovement, company)
    customer_invoices = company_queryset(CustomerInvoice, company)
    supplier_invoices = company_queryset(SupplierInvoice, company)
    goods_receipts = company_queryset(GoodsReceipt, company)
    purchase_orders = company_queryset(PurchaseOrder, company)
    supplier_payments = company_queryset(SupplierPayment, company)
    bank_accounts = company_queryset(BankAccount, company)

    posted_journals = (
        journals.filter(status="POSTED")
        if journals is not None
        else None
    )

    monthly_journals = posted_journals

    if monthly_journals is not None:
        journal_fields = {
            field.name
            for field in JournalEntry._meta.get_fields()
        }

        if "entry_date" in journal_fields:
            monthly_journals = monthly_journals.filter(
                entry_date__gte=month_start,
                entry_date__lte=today,
            )

    inventory_value = ZERO

    if stock_balances is not None:
        balance_fields = {
            field.name
            for field in StockBalance._meta.get_fields()
        }

        if "quantity" in balance_fields:
            if "average_cost" in balance_fields:
                inventory_expression = ExpressionWrapper(
                    F("quantity") * F("average_cost"),
                    output_field=DecimalField(
                        max_digits=20,
                        decimal_places=2,
                    ),
                )

                inventory_value = (
                    stock_balances.aggregate(
                        total=Sum(inventory_expression)
                    )["total"]
                    or ZERO
                )

            elif "unit_cost" in balance_fields:
                inventory_expression = ExpressionWrapper(
                    F("quantity") * F("unit_cost"),
                    output_field=DecimalField(
                        max_digits=20,
                        decimal_places=2,
                    ),
                )

                inventory_value = (
                    stock_balances.aggregate(
                        total=Sum(inventory_expression)
                    )["total"]
                    or ZERO
                )

    bank_balance = ZERO

    if bank_accounts is not None:
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

    if journals is not None:
        recent_journals = list(
            journals.order_by("-created_at", "-id")[:8]
        )

    context = {
        "company": company,
        "today": today,
        "bank_balance": bank_balance,
        "inventory_value": inventory_value,
        "receivables": invoice_balance(customer_invoices),
        "payables": invoice_balance(supplier_invoices),
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
