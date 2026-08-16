from django.urls import path

from .views import (
    dashboard,
    rent_payment_page,
    payment_receipt,
)

urlpatterns = [
    path(
        "",
        dashboard,
        name="payments_dashboard",
    ),
    path(
        "rent/<int:rent_id>/pay/",
        rent_payment_page,
        name="rent_payment_page",
    ),
    path(
        "receipt/<int:payment_id>/",
        payment_receipt,
        name="payment_receipt",
    ),
]
