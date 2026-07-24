from django.urls import path

from .views import general_ledger, trial_balance

urlpatterns = [
    path("general-ledger/", general_ledger, name="general_ledger"),
    path("general-ledger/", general_ledger, name="general_ledger"),
    path(
        "trial-balance/",
        trial_balance,
        name="trial_balance",
    ),
]


