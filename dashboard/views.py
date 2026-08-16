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


def md_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "GM"]:
        return redirect("/accounts/home/")

    today = timezone.now().date()

    unpaid_rents = Rent.objects.filter(
        paid=False
    ).select_related(
        "tenant",
        "house",
        "house__apartment"
    ).order_by("due_date")

    total_unpaid = Decimal("0")

    for rent in unpaid_rents:
        total_unpaid += rent.balance or Decimal("0.00")

        if rent.due_date:
            rent.days_overdue = (today - rent.due_date).days
        else:
            rent.days_overdue = 0

    total_houses = House.objects.count()
    occupied_houses = House.objects.filter(occupied=True).count()
    vacant_houses = House.objects.filter(occupied=False).count()

    if total_houses > 0:
        occupancy_rate = round((occupied_houses / total_houses) * 100, 2)
    else:
        occupancy_rate = 0

    revenue_potential = House.objects.aggregate(
        total=Sum("rent_amount")
    )["total"] or 0

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

    cash_balance = total_money_in - total_money_out

    water_total = WaterBill.objects.aggregate(
        total=Sum("amount")
    )["total"] or 0

    water_paid = WaterBill.objects.aggregate(
        total=Sum("amount_paid")
    )["total"] or 0

    water_balance = WaterBill.objects.aggregate(
        total=Sum("balance")
    )["total"] or 0

    deposits_held = Deposit.objects.filter(
        status="held"
    ).aggregate(
        total=Sum("amount")
    )["total"] or 0

    sms_drafts = SMSReminder.objects.filter(status="draft").count()
    sms_sent = SMSReminder.objects.filter(status="sent").count()
    sms_failed = SMSReminder.objects.filter(status="failed").count()

    context = {
        "total_payments": Payment.objects.count(),
        "successful": Payment.objects.filter(status="SUCCESS").count(),
        "pending": Payment.objects.filter(status="PENDING").count(),
        "failed": Payment.objects.filter(status="FAILED").count(),

        "rent_arrears": unpaid_rents.count(),
        "unpaid_rents": unpaid_rents,
        "total_unpaid": total_unpaid,

        "today": today,
        "total_houses": total_houses,
        "occupied_houses": occupied_houses,
        "vacant_houses": vacant_houses,
        "occupancy_rate": occupancy_rate,
        "revenue_potential": revenue_potential,

        "total_money_in": total_money_in,
        "total_money_out": total_money_out,
        "cash_balance": cash_balance,

        "water_total": water_total,
        "water_paid": water_paid,
        "water_balance": water_balance,

        "deposits_held": deposits_held,

        "sms_drafts": sms_drafts,
        "sms_sent": sms_sent,
        "sms_failed": sms_failed,

        "apartment_performance": apartment_performance(),
    }

    return render(request, "dashboard/md.html", context)


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

@login_required
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












