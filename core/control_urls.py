from django.urls import path
from core.control_views import (
    accounts_workspace,
    audit_workspace,
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
        name="v7_audit_workspace",
    ),
]
