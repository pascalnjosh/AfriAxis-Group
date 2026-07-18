from django.contrib import admin
from django.urls import path, include

from dashboard.views import (
    md_dashboard,
    rent_report_page,
    vacant_houses_page,
    tenants_page,
    charts_page,
)

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # Home
    path("", md_dashboard, name="erp_home"),

    # Dashboard
    path("dashboard/", md_dashboard, name="dashboard_page"),
    path("dashboard/rent-report/", rent_report_page, name="rent_report_page"),
    path("dashboard/vacant-houses/", vacant_houses_page, name="vacant_houses_page"),
    path("dashboard/tenants/", tenants_page, name="tenants_page"),
    path("dashboard/charts/", charts_page, name="charts_page"),

    # Authentication (Django built-in)
    path("auth/", include("django.contrib.auth.urls")),

    # ERP Modules
    path("payments/", include("payments.urls")),
    path("services/", include("services.urls")),
    path("rentals/", include("rentals.urls")),
    path("banking/", include("banking.urls")),
    path("ledger/", include("ledger.urls")),
    path("billing/", include("billing.urls")),

    # Accounts
    path("accounts/", include("accounts.urls")),
    path("tenant/", include("accounts.tenant_urls")),
]