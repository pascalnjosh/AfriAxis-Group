from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render


EXECUTIVE_ROLES = {
    "MD", "CEO", "GM", "FINANCE",
    "ACCOUNTS", "AUDITOR",
}


def _assignments(user):
    try:
        model = apps.get_model("accounts", "CompanyAssignment")
        return list(
            model.objects
            .filter(user=user, active=True)
            .select_related("company")
        )
    except Exception:
        return []


def _role_codes(user):
    if getattr(user, "is_superuser", False):
        return {"SUPERUSER"}

    return {
        str(x.role).upper()
        for x in _assignments(user)
        if getattr(x, "role", None)
    }


def _allowed(user, roles):
    if getattr(user, "is_superuser", False):
        return True

    return bool(_role_codes(user) & set(roles))


def _model(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _count(model):
    if model is None:
        return 0

    try:
        return model.objects.count()
    except Exception:
        return 0


def _field_names(model):
    if model is None:
        return set()

    return {
        field.name
        for field in model._meta.get_fields()
    }


def _recent(model, limit=10):
    if model is None:
        return []

    try:
        fields = _field_names(model)

        for candidate in (
            "created_at",
            "updated_at",
            "posted_at",
            "date",
            "entry_date",
            "id",
        ):
            if candidate in fields:
                return list(
                    model.objects
                    .all()
                    .order_by("-" + candidate)[:limit]
                )

        return list(model.objects.all()[:limit])

    except Exception:
        return []


def _sum_field(model, field_name):
    if model is None:
        return 0

    if field_name not in _field_names(model):
        return 0

    try:
        value = model.objects.aggregate(
            total=Sum(field_name)
        )["total"]

        return value or 0
    except Exception:
        return 0


@login_required
def accounts_workspace(request):
    if not _allowed(
        request.user,
        EXECUTIVE_ROLES,
    ):
        return render(
            request,
            "controls/access_denied.html",
            {
                "area": "Accounts & Finance",
            },
            status=403,
        )

    Account = _model("accounting", "Account")
    JournalEntry = _model(
        "accounting",
        "JournalEntry",
    )
    JournalLine = (
        _model("accounting", "JournalEntryLine")
        or
        _model("accounting", "JournalLine")
    )

    BankAccount = _model(
        "banking",
        "BankAccount",
    )
    BankTransaction = _model(
        "banking",
        "BankTransaction",
    )

    Invoice = (
        _model("billing", "Invoice")
        or
        _model("sales", "SalesInvoice")
    )

    SupplierInvoice = _model(
        "purchasing",
        "SupplierInvoice",
    )

    companies = [
        x.company
        for x in _assignments(request.user)
        if getattr(x, "company", None)
    ]

    context = {
        "companies": companies,

        "account_count":
            _count(Account),

        "journal_count":
            _count(JournalEntry),

        "journal_line_count":
            _count(JournalLine),

        "bank_account_count":
            _count(BankAccount),

        "bank_transaction_count":
            _count(BankTransaction),

        "invoice_count":
            _count(Invoice),

        "supplier_invoice_count":
            _count(SupplierInvoice),

        "recent_journals":
            _recent(JournalEntry, 12),

        "recent_bank_transactions":
            _recent(BankTransaction, 12),

        "recent_invoices":
            _recent(Invoice, 12),
    }

    return render(
        request,
        "controls/accounts_workspace.html",
        context,
    )


@login_required
def audit_workspace(request):
    if not _allowed(
        request.user,
        {
            "MD",
            "CEO",
            "GM",
            "AUDITOR",
        },
    ):
        return render(
            request,
            "controls/access_denied.html",
            {
                "area": "Audit & Controls",
            },
            status=403,
        )

    JournalEntry = _model(
        "accounting",
        "JournalEntry",
    )

    BankTransaction = _model(
        "banking",
        "BankTransaction",
    )

    StockMovement = _model(
        "inventory",
        "StockMovement",
    )

    ProductionOrder = _model(
        "manufacturing",
        "ProductionOrder",
    )

    SalesInvoice = _model(
        "sales",
        "SalesInvoice",
    )

    SalesReceipt = _model(
        "sales",
        "SalesReceipt",
    )

    SmsMessage = _model(
        "communications",
        "SmsMessage",
    )

    CompanyAssignment = _model(
        "accounts",
        "CompanyAssignment",
    )

    User = apps.get_model(
        "auth",
        "User",
    )

    context = {
        "user_count":
            _count(User),

        "assignment_count":
            _count(CompanyAssignment),

        "journal_count":
            _count(JournalEntry),

        "bank_transaction_count":
            _count(BankTransaction),

        "stock_movement_count":
            _count(StockMovement),

        "production_order_count":
            _count(ProductionOrder),

        "sales_invoice_count":
            _count(SalesInvoice),

        "sales_receipt_count":
            _count(SalesReceipt),

        "sms_count":
            _count(SmsMessage),

        "recent_journals":
            _recent(JournalEntry, 15),

        "recent_bank_transactions":
            _recent(BankTransaction, 15),

        "recent_stock_movements":
            _recent(StockMovement, 15),

        "recent_production_orders":
            _recent(ProductionOrder, 10),
    }

    return render(
        request,
        "controls/audit_workspace.html",
        context,
    )

@login_required
def fairlane_management(request):
    """
    Fairlane executive/management structure.

    This screen displays existing assignments only.
    It does not manufacture users or passwords.
    """

    if not _allowed(
        request.user,
        {
            "MD",
            "CEO",
            "GM",
            "MANAGER",
        },
    ):
        return render(
            request,
            "controls/access_denied.html",
            {
                "area": "Fairlane Management",
            },
            status=403,
        )

    CompanyAssignment = _model(
        "accounts",
        "CompanyAssignment",
    )

    assignments = []

    if CompanyAssignment is not None:
        assignments = list(
            CompanyAssignment.objects
            .filter(
                active=True,
                company__name__icontains="FAIRLANE",
                role__in=[
                    "MD",
                    "CEO",
                    "GM",
                    "MANAGER",
                ],
            )
            .select_related(
                "user",
                "company",
            )
            .order_by(
                "role",
                "user__username",
            )
        )

    by_role = {}

    for item in assignments:
        by_role.setdefault(
            item.role,
            [],
        ).append(item)

    management_slots = [
        {
            "code": "MD",
            "name": "Managing Director",
            "people": by_role.get("MD", []),
        },
        {
            "code": "CEO",
            "name": "Chief Executive Officer",
            "people": by_role.get("CEO", []),
        },
        {
            "code": "GM",
            "name": "General Manager",
            "people": by_role.get("GM", []),
        },
        {
            "code": "MANAGER",
            "name": "Manager",
            "people": by_role.get("MANAGER", []),
        },
    ]

    return render(
        request,
        "controls/fairlane_management.html",
        {
            "management_slots":
                management_slots,

            "assignment_count":
                len(assignments),
        },
    )
