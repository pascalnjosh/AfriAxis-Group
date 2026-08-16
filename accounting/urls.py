from django.urls import path

from .views import (
    aged_payables,
    aged_receivables,
    balance_sheet,
    customer_statement,
    general_ledger,
    profit_and_loss,
    supplier_statement,
    trial_balance,
)

urlpatterns = [
    path(
        "general-ledger/",
        general_ledger,
        name="general_ledger",
    ),
    path(
        "trial-balance/",
        trial_balance,
        name="trial_balance",
    ),
    path(
        "profit-and-loss/",
        profit_and_loss,
        name="profit_and_loss",
    ),
    path(
        "balance-sheet/",
        balance_sheet,
        name="balance_sheet",
    ),
    path(
        "aged-receivables/",
        aged_receivables,
        name="aged_receivables",
    ),
    path(
        "aged-payables/",
        aged_payables,
        name="aged_payables",
    ),
    path(
        "customer-statement/",
        customer_statement,
        name="customer_statement",
    ),
    path(
        "supplier-statement/",
        supplier_statement,
        name="supplier_statement",
    ),
]
