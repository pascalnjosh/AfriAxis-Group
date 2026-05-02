from django.urls import path
from .views import wifi_packages_page, wifi_payment_page, wifi_status, wifi_stk_push, wifi_callback

urlpatterns = [
    path("wifi/", wifi_packages_page, name="wifi_packages_page"),
    path("wifi/<int:customer_id>/", wifi_payment_page, name="wifi_payment_page"),
    path("wifi/<int:customer_id>/status/", wifi_status, name="wifi_status"),
    path("wifi/<int:customer_id>/stk-push/", wifi_stk_push, name="wifi_stk_push"),
    path("wifi/callback/", wifi_callback, name="wifi_callback"),
]
