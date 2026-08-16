from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from .models import Account


def get_account_totals(account, date_from=None, date_to=None):
    lines = account.journal_lines.filter(
        journal_entry__status="POSTED",
    )

    if date_from:
        lines = lines.filter(
            journal_entry__entry_date__gte=date_from,
        )

    if date_to:
        lines = lines.filter(
            journal_entry__entry_date__lte=date_to,
        )

    return lines.aggregate(
        debit=Coalesce(
            Sum("debit"),
            Decimal("0.00"),
        ),
        credit=Coalesce(
            Sum("credit"),
            Decimal("0.00"),
        ),
    )


def get_trial_balance(*, company, date_from=None, date_to=None):
    accounts = Account.objects.filter(
        company=company,
        active=True,
    ).select_related(
        "account_type",
    ).order_by("code")

    rows = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for account in accounts:
        totals = get_account_totals(
            account,
            date_from=date_from,
            date_to=date_to,
        )

        debit = totals["debit"]
        credit = totals["credit"]

        if account.account_type.normal_balance == "DEBIT":
            balance = debit - credit
        else:
            balance = credit - debit

        rows.append(
            {
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.account_type.name,
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )

        total_debit += debit
        total_credit += credit

    return {
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": total_debit - total_credit,
        "is_balanced": total_debit == total_credit,
    }


def get_profit_and_loss(*, company, date_from=None, date_to=None):
    accounts = Account.objects.filter(
        company=company,
        active=True,
        account_type__category__in=[
            "REVENUE",
            "COST_OF_SALES",
            "EXPENSE",
        ],
    ).select_related(
        "account_type",
    ).order_by("code")

    revenue_rows = []
    cost_of_sales_rows = []
    expense_rows = []

    total_revenue = Decimal("0.00")
    total_cost_of_sales = Decimal("0.00")
    total_expenses = Decimal("0.00")

    for account in accounts:
        totals = get_account_totals(
            account,
            date_from=date_from,
            date_to=date_to,
        )

        debit = totals["debit"]
        credit = totals["credit"]
        category = account.account_type.category

        if category == "REVENUE":
            balance = credit - debit
            total_revenue += balance
            revenue_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": balance,
                }
            )

        elif category == "COST_OF_SALES":
            balance = debit - credit
            total_cost_of_sales += balance
            cost_of_sales_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": balance,
                }
            )

        elif category == "EXPENSE":
            balance = debit - credit
            total_expenses += balance
            expense_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": balance,
                }
            )

    gross_profit = total_revenue - total_cost_of_sales
    net_profit = gross_profit - total_expenses

    return {
        "revenue_rows": revenue_rows,
        "cost_of_sales_rows": cost_of_sales_rows,
        "expense_rows": expense_rows,
        "total_revenue": total_revenue,
        "total_cost_of_sales": total_cost_of_sales,
        "gross_profit": gross_profit,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
    }


def get_balance_sheet(*, company, as_of=None):
    accounts = Account.objects.filter(
        company=company,
        active=True,
        account_type__category__in=[
            "ASSET",
            "LIABILITY",
            "EQUITY",
        ],
    ).select_related(
        "account_type",
    ).order_by("code")

    asset_rows = []
    liability_rows = []
    equity_rows = []

    total_assets = Decimal("0.00")
    total_liabilities = Decimal("0.00")
    total_equity = Decimal("0.00")

    for account in accounts:
        totals = get_account_totals(
            account,
            date_to=as_of,
        )

        debit = totals["debit"]
        credit = totals["credit"]
        category = account.account_type.category

        if category == "ASSET":
            balance = debit - credit
            total_assets += balance
            asset_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": balance,
                }
            )

        elif category == "LIABILITY":
            balance = credit - debit
            total_liabilities += balance
            liability_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": balance,
                }
            )

        elif category == "EQUITY":
            balance = credit - debit
            total_equity += balance
            equity_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": balance,
                }
            )

    profit_and_loss = get_profit_and_loss(
        company=company,
        date_to=as_of,
    )

    current_earnings = profit_and_loss["net_profit"]
    total_equity_with_earnings = total_equity + current_earnings
    total_liabilities_and_equity = (
        total_liabilities + total_equity_with_earnings
    )

    difference = total_assets - total_liabilities_and_equity

    return {
        "asset_rows": asset_rows,
        "liability_rows": liability_rows,
        "equity_rows": equity_rows,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "current_earnings": current_earnings,
        "total_equity_with_earnings": total_equity_with_earnings,
        "total_liabilities_and_equity": total_liabilities_and_equity,
        "difference": difference,
        "is_balanced": difference == Decimal("0.00"),
    }


def get_cash_flow(*, company, as_of=None):
    """
    Indirect-method cash-flow statement.

    This version uses the current AfriAxis chart structure:
    - Cash and bank accounts are identified by code 1000 or names
      containing 'cash' or 'bank'.
    - Other asset balances are treated as operating working-capital
      movements.
    - Liability balances are treated as operating working-capital
      movements.
    - Equity postings are treated as financing activities.
    """

    profit_and_loss = get_profit_and_loss(
        company=company,
        date_to=as_of,
    )

    net_profit = profit_and_loss["net_profit"]

    accounts = Account.objects.filter(
        company=company,
        active=True,
    ).select_related(
        "account_type",
    ).order_by("code")

    operating_rows = []
    financing_rows = []
    investing_rows = []

    total_operating_adjustments = Decimal("0.00")
    total_financing_cash = Decimal("0.00")
    total_investing_cash = Decimal("0.00")
    closing_cash_balance = Decimal("0.00")

    for account in accounts:
        totals = get_account_totals(
            account,
            date_to=as_of,
        )

        debit = totals["debit"]
        credit = totals["credit"]
        category = account.account_type.category

        account_name = account.name.lower()

        is_cash_account = (
            account.code == "1000"
            or "cash" in account_name
            or "bank" in account_name
        )

        if is_cash_account:
            cash_balance = debit - credit
            closing_cash_balance += cash_balance
            continue

        if category == "ASSET":
            balance = debit - credit

            adjustment = -balance

            total_operating_adjustments += adjustment

            operating_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": adjustment,
                }
            )

        elif category == "LIABILITY":
            balance = credit - debit

            adjustment = balance

            total_operating_adjustments += adjustment

            operating_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": adjustment,
                }
            )

        elif category == "EQUITY":
            balance = credit - debit

            total_financing_cash += balance

            financing_rows.append(
                {
                    "code": account.code,
                    "name": account.name,
                    "amount": balance,
                }
            )

    net_cash_from_operations = (
        net_profit + total_operating_adjustments
    )

    net_change_in_cash = (
        net_cash_from_operations
        + total_investing_cash
        + total_financing_cash
    )

    opening_cash_balance = (
        closing_cash_balance - net_change_in_cash
    )

    difference = (
        closing_cash_balance
        - opening_cash_balance
        - net_change_in_cash
    )

    return {
        "net_profit": net_profit,
        "operating_rows": operating_rows,
        "investing_rows": investing_rows,
        "financing_rows": financing_rows,
        "total_operating_adjustments": total_operating_adjustments,
        "net_cash_from_operations": net_cash_from_operations,
        "net_cash_from_investing": total_investing_cash,
        "net_cash_from_financing": total_financing_cash,
        "net_change_in_cash": net_change_in_cash,
        "opening_cash_balance": opening_cash_balance,
        "closing_cash_balance": closing_cash_balance,
        "difference": difference,
        "is_reconciled": difference == Decimal("0.00"),
    }
