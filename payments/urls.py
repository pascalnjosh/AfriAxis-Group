from django.urls import path
from .views import dashboard, rent_payment_page, rent_callback

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("rent/<int:rent_id>/pay/", rent_payment_page, name="rent_payment_page"),
    path("rent/callback/", rent_callback, name="rent_callback"),
]
