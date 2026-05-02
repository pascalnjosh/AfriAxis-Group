from django.urls import path
from .views import tenant_status, pay_invoice

urlpatterns = [
    path("tenant/<int:tenant_id>/status/", tenant_status, name="tenant_status"),
    path("invoice/<int:invoice_id>/pay/", pay_invoice, name="pay_invoice"),
]