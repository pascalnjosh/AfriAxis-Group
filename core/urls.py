from accounts.views import role_home
from django.contrib import admin
from django.urls import include, path

from core.pwa import service_worker

from dashboard.views import (
    charts_page,
    finance_dashboard,
    md_dashboard,
    rent_report_page,
    tenants_page,
    vacant_houses_page,
)

urlpatterns = [
    path("service-worker.js", service_worker, name="service_worker"),
    path("dashboard/", include("dashboard.ceo_urls")),
    # Django Admin
    path("admin/", admin.site.urls),

    # Home
    path("", role_home, name="erp_home"),

    # Dashboard
    path("dashboard/", md_dashboard, name="dashboard_page"),
    path(
        "dashboard/finance/",
        finance_dashboard,
        name="finance_dashboard",
    ),
    path(
        "dashboard/rent-report/",
        rent_report_page,
        name="rent_report_page",
    ),
    path(
        "dashboard/vacant-houses/",
        vacant_houses_page,
        name="vacant_houses_page",
    ),
    path(
        "dashboard/tenants/",
        tenants_page,
        name="tenants_page",
    ),
    path(
        "dashboard/charts/",
        charts_page,
        name="charts_page",
    ),

    # Authentication
    path(
        "auth/",
        include("django.contrib.auth.urls"),
    ),

    # ERP Modules
    path("payments/", include("payments.urls")),
    path("services/", include("services.urls")),
    path("rentals/", include("rentals.urls")),
    path("banking/", include("banking.urls")),
    path("ledger/", include("ledger.urls")),
    path("billing/", include("billing.urls")),
    path("accounting/", include("accounting.urls")),
    path("inventory/", include("inventory.urls")),
    path("manufacturing/", include("manufacturing.urls")),
    path("purchasing/", include("purchasing.urls")),
    path("sales/", include("sales.urls")),

    # Accounts
    path("accounts/", include("accounts.urls")),
    path("tenant/", include("accounts.tenant_urls")),
]







