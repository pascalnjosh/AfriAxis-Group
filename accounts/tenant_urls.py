from django.urls import path

from .tenant_auth_views import (
    tenant_login,
    tenant_logout,
    tenant_dashboard,
)

urlpatterns = [

    path(
        "login/",
        tenant_login,
        name="tenant_login"
    ),

    path(
        "dashboard/",
        tenant_dashboard,
        name="tenant_dashboard"
    ),

    path(
        "logout/",
        tenant_logout,
        name="tenant_logout"
    ),
]
