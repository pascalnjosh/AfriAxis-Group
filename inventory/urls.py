from django.urls import path

from .views import (
    inventory_dashboard,
    movement_history,
    stock_balances,
    stock_ledger,
)

urlpatterns = [
    path(
        "",
        inventory_dashboard,
        name="inventory_dashboard",
    ),
    path(
        "balances/",
        stock_balances,
        name="stock_balances",
    ),
    path(
        "movements/",
        movement_history,
        name="movement_history",
    ),
    path(
        "stock-ledger/",
        stock_ledger,
        name="stock_ledger",
    ),
]
