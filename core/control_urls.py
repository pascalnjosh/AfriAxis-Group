from django.urls import path
from core.control_views import (
    accounts_workspace,
    audit_workspace,
    fairlane_management,
)

urlpatterns = [
    path(
        "accounts-finance/",
        accounts_workspace,
        name="v7_accounts_workspace",
    ),
    path(
        "audit-controls/",
        audit_workspace,
    fairlane_management,
        name="v7_audit_workspace",
    ),

    path(
        "fairlane-management/",
        fairlane_management,
        name="v7_fairlane_management",
    ),
]
