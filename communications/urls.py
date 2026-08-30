from django.urls import path

from . import views


urlpatterns = [

    path(
        "",
        views.sms_dashboard,
        name="sms_dashboard",
    ),

    path(
        "rent/<int:rent_id>/send/",
        views.send_rent_sms,
        name="send_rent_sms",
    ),

    path(
        "water/<int:bill_id>/send/",
        views.send_water_sms,
        name="send_water_sms",
    ),

    path(
        "wifi/<int:customer_id>/send/",
        views.send_wifi_sms,
        name="send_wifi_sms",
    ),
]
