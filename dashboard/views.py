from accounts.decorators import (
    management_required,
    finance_required,
)
from django.contrib.auth.decorators import login_required
from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render, redirect
from django.utils import timezone

from payments.models import Payment
from rentals.models import Apartment, House, Rent, Tenant
from accounting.models import Account, JournalEntryLine
from water.models import WaterBill
from deposits.models import Deposit
from sms.models import SMSReminder


def user_role(request):
    profile = getattr(request.user, "userprofile", None)

    if profile:
        return profile.role

    return None


@management_required
def md_dashboard(request):
    from decimal import Decimal

    from django.db.models import Sum

    from enterprise.models import Company

    from sales.models import (
        Customer,
        SalesOrder,
        SalesInvoice,
        DeliveryNote,
    )

    from inventory.models import (
        Warehouse,
        StockBalance,
        StockMovement,
    )

    from manufacturing.models import (
        BillOfMaterial,
        ProductionOrder,
    )

    from purchasing.models import (
        Supplier,
        PurchaseOrder,
        GoodsReceipt,
        SupplierInvoice,
        SupplierPayment,
    )

    from accounting.models import (
        JournalEntry,
        JournalEntryLine,
        Account,
    )

    from banking.models import (
        BankAccount,
        BankTransaction,
    )

    from services.models import (
        WifiCustomer,
        WifiPackage,
        WifiPayment,
    )

    today = timezone.now().date()

    # ====================================================
    # COMPANIES
    # ====================================================

    companies = Company.objects.filter(
        active=True
    ).order_by("id")

    fas = Company.objects.filter(
        name__icontains="FAIRLANE",
        active=True,
    ).first()

    africore = Company.objects.filter(
        name__icontains="AFRICORE",
        active=True,
    ).first()


    # ====================================================
    # FAS SALES
    # ====================================================

    fas_customers = Customer.objects.none()
    fas_orders = SalesOrder.objects.none()
    fas_invoices = SalesInvoice.objects.none()
    fas_deliveries = DeliveryNote.objects.none()

    if fas:
        fas_customers = Customer.objects.filter(
            company=fas
        )

        fas_orders = SalesOrder.objects.filter(
            company=fas
        ).select_related(
            "customer"
        )

        fas_invoices = SalesInvoice.objects.filter(
            company=fas
        ).select_related(
            "customer",
            "sales_order",
        )

        fas_deliveries = DeliveryNote.objects.filter(
            sales_order__company=fas
        ).select_related(
            "customer",
            "sales_order",
            "warehouse",
        )

    fas_sales_total = fas_invoices.aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    fas_sales_paid = fas_invoices.aggregate(
        total=Sum("amount_paid")
    )["total"] or Decimal("0.00")

    fas_receivables = (
        fas_sales_total - fas_sales_paid
    )


    # ====================================================
    # FAS INVENTORY
    # ====================================================

    fas_warehouses = Warehouse.objects.none()
    fas_stock = StockBalance.objects.none()
    fas_movements = StockMovement.objects.none()

    if fas:
        fas_warehouses = Warehouse.objects.filter(
            company=fas
        )

        fas_stock = StockBalance.objects.filter(
            warehouse__company=fas
        ).select_related(
            "product",
            "warehouse",
            "location",
            "batch",
        )

        fas_movements = StockMovement.objects.filter(
            warehouse__company=fas
        ).select_related(
            "product",
            "warehouse",
            "location",
            "batch",
        ).order_by(
            "-created_at"
        )

    inventory_value = Decimal("0.00")

    for row in fas_stock:
        inventory_value += (
            (row.quantity or Decimal("0.00"))
            *
            (row.average_cost or Decimal("0.00"))
        )


    # ====================================================
    # FAS MANUFACTURING
    # ====================================================

    fas_boms = BillOfMaterial.objects.none()
    fas_production = ProductionOrder.objects.none()

    if fas:
        fas_boms = BillOfMaterial.objects.filter(
            company=fas
        ).select_related(
            "finished_product",
            "warehouse",
        )

        fas_production = ProductionOrder.objects.filter(
            company=fas
        ).select_related(
            "bom",
            "warehouse",
        ).order_by(
            "-created_at"
        )

    active_boms = fas_boms.filter(
        status="ACTIVE"
    ).count()

    production_in_progress = fas_production.filter(
        status__in=[
            "RELEASED",
            "IN_PROGRESS",
        ]
    ).count()


    # ====================================================
    # FAS PURCHASING
    # ====================================================

    fas_suppliers = Supplier.objects.none()
    fas_purchase_orders = PurchaseOrder.objects.none()
    fas_grns = GoodsReceipt.objects.none()
    fas_supplier_invoices = SupplierInvoice.objects.none()
    fas_supplier_payments = SupplierPayment.objects.none()

    if fas:
        fas_suppliers = Supplier.objects.filter(
            company=fas
        )

        fas_purchase_orders = PurchaseOrder.objects.filter(
            company=fas
        ).select_related(
            "supplier"
        ).order_by(
            "-created_at"
        )

        fas_grns = GoodsReceipt.objects.filter(
            purchase_order__company=fas
        ).select_related(
            "purchase_order",
            "supplier",
        )

        fas_supplier_invoices = SupplierInvoice.objects.filter(
            purchase_order__company=fas
        ).select_related(
            "supplier",
            "purchase_order",
        )

        fas_supplier_payments = SupplierPayment.objects.filter(
            supplier_invoice__purchase_order__company=fas
        ).select_related(
            "supplier",
            "supplier_invoice",
        )

    supplier_invoice_total = fas_supplier_invoices.aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    supplier_invoice_paid = fas_supplier_invoices.aggregate(
        total=Sum("amount_paid")
    )["total"] or Decimal("0.00")

    fas_payables = (
        supplier_invoice_total
        -
        supplier_invoice_paid
    )


    # ====================================================
    # AFRICORE PROPERTY / RENT
    # ====================================================

    apartments = Apartment.objects.none()
    houses = House.objects.none()
    tenants = Tenant.objects.none()
    rents = Rent.objects.none()

    if africore:
        apartments = Apartment.objects.filter(
            company=africore
        )

        houses = House.objects.filter(
            apartment__company=africore
        )

        tenants = Tenant.objects.filter(
            apartment__company=africore
        )

        rents = Rent.objects.filter(
            house__apartment__company=africore
        ).select_related(
            "tenant",
            "house",
            "house__apartment",
        )

    unpaid_rents = rents.filter(
        paid=False
    ).order_by(
        "due_date"
    )

    total_unpaid = Decimal("0.00")

    for rent in unpaid_rents:
        total_unpaid += (
            rent.balance
            or Decimal("0.00")
        )

        if rent.due_date:
            rent.days_overdue = (
                today - rent.due_date
            ).days
        else:
            rent.days_overdue = 0

    total_houses = houses.count()

    occupied_houses = houses.filter(
        occupied=True
    ).count()

    vacant_houses = houses.filter(
        occupied=False
    ).count()

    if total_houses:
        occupancy_rate = round(
            (
                occupied_houses
                /
                total_houses
            ) * 100,
            1,
        )
    else:
        occupancy_rate = 0

    rent_billed = rents.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    rent_collected = rents.aggregate(
        total=Sum("amount_paid")
    )["total"] or Decimal("0.00")


    # ====================================================
    # ACCOUNTING
    # ====================================================

    posted_journals = JournalEntry.objects.filter(
        status="POSTED"
    )

    recent_journals = posted_journals.select_related(
        "company"
    ).order_by(
        "-entry_date",
        "-id",
    )[:8]

    cash_account = Account.objects.filter(
        code="1000"
    ).first()

    total_money_in = Decimal("0.00")
    total_money_out = Decimal("0.00")

    if cash_account:
        cash_totals = JournalEntryLine.objects.filter(
            journal_entry__status="POSTED",
            account=cash_account,
        ).aggregate(
            money_in=Sum("debit"),
            money_out=Sum("credit"),
        )

        total_money_in = (
            cash_totals["money_in"]
            or Decimal("0.00")
        )

        total_money_out = (
            cash_totals["money_out"]
            or Decimal("0.00")
        )

    cash_balance = (
        total_money_in
        -
        total_money_out
    )


    # ====================================================
    # BANKING
    # ====================================================

    bank_accounts = BankAccount.objects.filter(
        active=True
    ).select_related(
        "company"
    )

    pending_bank_transactions = BankTransaction.objects.filter(
        match_status="pending"
    ).count()

    approved_bank_transactions = BankTransaction.objects.filter(
        match_status="approved"
    ).count()


    # ====================================================
    # WIFI
    # ====================================================

    wifi_customers = WifiCustomer.objects.all()
    wifi_packages = WifiPackage.objects.all()
    wifi_payments = WifiPayment.objects.all()

    wifi_active = wifi_customers.filter(
        active=True
    ).count()

    wifi_success = wifi_payments.filter(
        status="SUCCESS"
    ).count()

    wifi_pending = wifi_payments.filter(
        status="PENDING"
    ).count()


    # ====================================================
    # LEGACY PROPERTY SUPPORT
    # ====================================================

    water_total = WaterBill.objects.aggregate(
        total=Sum("amount")
    )["total"] or 0

    water_paid = WaterBill.objects.aggregate(
        total=Sum("amount_paid")
    )["total"] or 0

    deposits_held = Deposit.objects.filter(
        status="held"
    ).aggregate(
        total=Sum("amount")
    )["total"] or 0


    # ====================================================
    # CONTEXT
    # ====================================================

    context = {

        # group
        "companies": companies,
        "company_count": companies.count(),

        # FAS
        "fas": fas,
        "fas_customers": fas_customers.count(),
        "fas_orders": fas_orders.count(),
        "fas_invoices": fas_invoices.count(),
        "fas_deliveries": fas_deliveries.count(),
        "fas_sales_total": fas_sales_total,
        "fas_sales_paid": fas_sales_paid,
        "fas_receivables": fas_receivables,

        # inventory
        "fas_warehouses": fas_warehouses.count(),
        "fas_stock_count": fas_stock.count(),
        "fas_movement_count": fas_movements.count(),
        "inventory_value": inventory_value,
        "stock_rows": fas_stock.order_by(
            "product__name"
        )[:8],
        "recent_movements": fas_movements[:8],

        # manufacturing
        "fas_bom_count": fas_boms.count(),
        "active_boms": active_boms,
        "production_count": fas_production.count(),
        "production_in_progress": production_in_progress,
        "bom_rows": fas_boms.order_by(
            "code"
        )[:6],

        # purchasing
        "supplier_count": fas_suppliers.count(),
        "purchase_order_count": fas_purchase_orders.count(),
        "grn_count": fas_grns.count(),
        "supplier_invoice_count": fas_supplier_invoices.count(),
        "supplier_payment_count": fas_supplier_payments.count(),
        "fas_payables": fas_payables,

        # property
        "apartment_count": apartments.count(),
        "tenant_count": tenants.count(),
        "total_houses": total_houses,
        "occupied_houses": occupied_houses,
        "vacant_houses": vacant_houses,
        "occupancy_rate": occupancy_rate,
        "rent_billed": rent_billed,
        "rent_collected": rent_collected,
        "rent_arrears": unpaid_rents.count(),
        "total_unpaid": total_unpaid,
        "unpaid_rents": unpaid_rents[:10],

        # accounting
        "journal_count": JournalEntry.objects.count(),
        "posted_journal_count": posted_journals.count(),
        "recent_journals": recent_journals,
        "total_money_in": total_money_in,
        "total_money_out": total_money_out,
        "cash_balance": cash_balance,

        # banking
        "bank_account_count": bank_accounts.count(),
        "bank_transaction_count": BankTransaction.objects.count(),
        "pending_bank_transactions": pending_bank_transactions,
        "approved_bank_transactions": approved_bank_transactions,

        # wifi
        "wifi_customer_count": wifi_customers.count(),
        "wifi_active": wifi_active,
        "wifi_package_count": wifi_packages.count(),
        "wifi_payment_count": wifi_payments.count(),
        "wifi_success": wifi_success,
        "wifi_pending": wifi_pending,

        # legacy operational values
        "water_total": water_total,
        "water_paid": water_paid,
        "deposits_held": deposits_held,

        # real recent business documents
        "recent_sales_orders": fas_orders.order_by(
            "-order_date",
            "-id",
        )[:5],

        "recent_sales_invoices": fas_invoices.order_by(
            "-invoice_date",
            "-id",
        )[:5],

        "recent_deliveries": fas_deliveries.order_by(
            "-delivery_date",
            "-id",
        )[:5],

        "today": today,
    }

    return render(
        request,
        "dashboard/md.html",
        context,
    )


@finance_required
def rent_report_page(request):
    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM", "ACCOUNTS"]:
        return redirect("/accounts/home/")

    apartments = Apartment.objects.all().order_by("name")
    rows = []

    grand_total = 0
    grand_paid = 0
    grand_unpaid = 0

    for apartment in apartments:
        rents = Rent.objects.filter(house__apartment=apartment)

        total = rents.aggregate(total=Sum("amount"))["total"] or 0
        paid = rents.aggregate(total=Sum("amount_paid"))["total"] or 0
        unpaid = rents.aggregate(total=Sum("balance"))["total"] or 0

        rows.append({
            "apartment": apartment.name,
            "total": total,
            "paid": paid,
            "unpaid": unpaid,
        })

        grand_total += total
        grand_paid += paid
        grand_unpaid += unpaid

    return render(
        request,
        "dashboard/rent_report.html",
        {
            "rows": rows,
            "grand_total": grand_total,
            "grand_paid": grand_paid,
            "grand_unpaid": grand_unpaid,
        }
    )


@management_required
def vacant_houses_page(request):
    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM"]:
        return redirect("/accounts/home/")

    vacant_houses = House.objects.filter(
        occupied=False
    ).select_related(
        "apartment"
    ).order_by(
        "apartment__name",
        "house_number"
    )

    return render(
        request,
        "dashboard/vacant_houses.html",
        {
            "vacant_houses": vacant_houses,
            "vacant_count": vacant_houses.count(),
            "apartment_performance": apartment_performance(),
        }
    )


@management_required
def tenants_page(request):
    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM"]:
        return redirect("/accounts/home/")

    tenants = Tenant.objects.select_related(
        "apartment"
    ).order_by(
        "apartment__name",
        "name"
    )

    return render(
        request,
        "dashboard/tenants.html",
        {
            "tenants": tenants,
            "tenant_count": tenants.count(),
        }
    )


@management_required
def charts_page(request):
    total_rent = Rent.objects.aggregate(total=Sum("amount"))["total"] or 0
    unpaid_rent = Rent.objects.aggregate(total=Sum("balance"))["total"] or 0
    paid_rent = Rent.objects.aggregate(total=Sum("amount_paid"))["total"] or 0

    total_houses = House.objects.count()
    occupied_houses = House.objects.filter(occupied=True).count()
    vacant_houses = House.objects.filter(occupied=False).count()

    cash_account = Account.objects.filter(code="1000").first()

    total_money_in = Decimal("0.00")
    total_money_out = Decimal("0.00")

    if cash_account:
        cash_totals = JournalEntryLine.objects.filter(
            journal_entry__status="POSTED",
            account=cash_account,
        ).aggregate(
            money_in=Sum("debit"),
            money_out=Sum("credit"),
        )

        total_money_in = cash_totals["money_in"] or Decimal("0.00")
        total_money_out = cash_totals["money_out"] or Decimal("0.00")
    water_balance = WaterBill.objects.aggregate(total=Sum("balance"))["total"] or 0
    deposits_held = Deposit.objects.filter(status="held").aggregate(total=Sum("amount"))["total"] or 0

    return render(
        request,
        "dashboard/charts.html",
        {
            "total_rent": total_rent,
            "paid_rent": paid_rent,
            "unpaid_rent": unpaid_rent,
            "total_houses": total_houses,
            "occupied_houses": occupied_houses,
            "vacant_houses": vacant_houses,
            "total_money_in": total_money_in,
            "total_money_out": total_money_out,
            "water_balance": water_balance,
            "deposits_held": deposits_held,
            "apartment_performance": apartment_performance(),
        }
    )


def apartment_performance():
    apartments = Apartment.objects.all()
    performance = []

    for apartment in apartments:
        houses = House.objects.filter(apartment=apartment)

        total_houses = houses.count()
        occupied = houses.filter(occupied=True).count()
        vacant = houses.filter(occupied=False).count()

        revenue = Rent.objects.filter(
            house__apartment=apartment
        ).aggregate(
            total=Sum("balance")
        )["total"] or 0

        unpaid = Rent.objects.filter(
            house__apartment=apartment,
            paid=False
        ).aggregate(
            total=Sum("balance")
        )["total"] or 0

        if total_houses > 0:
            occupancy = round((occupied / total_houses) * 100, 2)
        else:
            occupancy = 0

        performance.append({
            "name": apartment.name,
            "revenue": revenue,
            "unpaid": unpaid,
            "occupancy": occupancy,
            "vacant": vacant,
        })

    return sorted(
        performance,
        key=lambda x: x["revenue"],
        reverse=True
    )

@finance_required
def finance_dashboard(request):
    from decimal import Decimal

    from django.db.models import Sum

    from accounting.reports import (
        get_balance_sheet,
        get_profit_and_loss,
    )
    from banking.models import BankAccount, BankTransaction
    from billing.models import Invoice
    from enterprise.models import Company
    from rentals.models import House, Rent

    company = Company.objects.first()

    financial_position = {
        "asset_rows": [],
        "liability_rows": [],
        "total_assets": Decimal("0.00"),
        "total_liabilities": Decimal("0.00"),
    }

    profit_and_loss = {
        "total_revenue": Decimal("0.00"),
        "total_expenses": Decimal("0.00"),
        "net_profit": Decimal("0.00"),
    }

    if company:
        financial_position = get_balance_sheet(
            company=company,
        )

        profit_and_loss = get_profit_and_loss(
            company=company,
        )

    def account_amount(rows, code):
        for row in rows:
            if row["code"] == code:
                return row["amount"]

        return Decimal("0.00")

    asset_rows = financial_position.get(
        "asset_rows",
        [],
    )

    liability_rows = financial_position.get(
        "liability_rows",
        [],
    )

    cash_and_bank = account_amount(
        asset_rows,
        "1000",
    )

    accounts_receivable = account_amount(
        asset_rows,
        "1100",
    )

    inventory_value = account_amount(
        asset_rows,
        "1200",
    )

    accounts_payable = account_amount(
        liability_rows,
        "2000",
    )

    rent_totals = Rent.objects.aggregate(
        billed=Sum("amount"),
        collected=Sum("amount_paid"),
        outstanding=Sum("balance"),
    )

    rent_billed = (
        rent_totals["billed"]
        or Decimal("0.00")
    )

    rent_collected = (
        rent_totals["collected"]
        or Decimal("0.00")
    )

    outstanding_rent = (
        rent_totals["outstanding"]
        or Decimal("0.00")
    )

    total_houses = House.objects.count()

    occupied_houses = House.objects.filter(
        occupied=True,
    ).count()

    vacant_houses = total_houses - occupied_houses

    if total_houses:
        occupancy_rate = round(
            occupied_houses / total_houses * 100,
            1,
        )
    else:
        occupancy_rate = 0

    invoice_rows = Invoice.objects.exclude(
        status="CANCELLED",
    ).values(
        "total_amount",
        "amount_paid",
        "status",
    )

    outstanding_invoices = Decimal("0.00")
    unpaid_invoice_count = 0

    for invoice in invoice_rows:
        balance = (
            Decimal(invoice["total_amount"])
            - Decimal(invoice["amount_paid"])
        )

        if balance > 0:
            outstanding_invoices += balance
            unpaid_invoice_count += 1

    pending_bank = BankTransaction.objects.filter(
        match_status="pending",
    ).count()

    approved_bank = BankTransaction.objects.filter(
        match_status="approved",
    ).count()

    rejected_bank = BankTransaction.objects.filter(
        match_status="rejected",
    ).count()

    bank_accounts = BankAccount.objects.filter(
        active=True,
    ).count()

    recent_bank_transactions = (
        BankTransaction.objects
        .select_related(
            "bank_account",
            "matched_tenant",
            "matched_house",
        )
        .order_by(
            "-transaction_date",
            "-id",
        )[:8]
    )

    recent_rents = (
        Rent.objects
        .select_related(
            "tenant",
            "house",
            "house__apartment",
        )
        .order_by(
            "-billing_month",
            "-id",
        )[:8]
    )

    context = {
        "company": company,
        "cash_and_bank": cash_and_bank,
        "accounts_receivable": accounts_receivable,
        "accounts_payable": accounts_payable,
        "inventory_value": inventory_value,
        "total_revenue": profit_and_loss[
            "total_revenue"
        ],
        "total_expenses": profit_and_loss[
            "total_expenses"
        ],
        "net_profit": profit_and_loss[
            "net_profit"
        ],
        "total_assets": financial_position[
            "total_assets"
        ],
        "total_liabilities": financial_position[
            "total_liabilities"
        ],
        "rent_billed": rent_billed,
        "rent_collected": rent_collected,
        "outstanding_rent": outstanding_rent,
        "total_houses": total_houses,
        "occupied_houses": occupied_houses,
        "vacant_houses": vacant_houses,
        "occupancy_rate": occupancy_rate,
        "outstanding_invoices": outstanding_invoices,
        "unpaid_invoice_count": unpaid_invoice_count,
        "pending_bank": pending_bank,
        "approved_bank": approved_bank,
        "rejected_bank": rejected_bank,
        "bank_accounts": bank_accounts,
        "recent_bank_transactions": recent_bank_transactions,
        "recent_rents": recent_rents,
    }

    return render(
        request,
        "dashboard/finance_dashboard.html",
        context,
    )













