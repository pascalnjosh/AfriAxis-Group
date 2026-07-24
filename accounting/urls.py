from django.urls import path

from .views import trial_balance

urlpatterns = [
    path(
        "trial-balance/",
        trial_balance,
        name="trial_balance",
    ),
]
