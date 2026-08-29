from django.shortcuts import render, get_object_or_404

from accounts.decorators import (
    audit_required,
    get_user_company_ids,
)
from rentals.models import Tenant

from .models import TenantLedger


@audit_required
def tenant_statement(request, tenant_id):

    tenants = (
        Tenant.objects
        .select_related(
            "apartment",
            "apartment__company",
        )
    )

    # ---------------------------------------------------------
    # COMPANY ISOLATION
    #
    # Superusers may access tenants from any company.
    #
    # Normal users may access only tenants whose Apartment
    # belongs to one of their active CompanyAssignments.
    # ---------------------------------------------------------

    if not request.user.is_superuser:

        company_ids = get_user_company_ids(
            request.user
        )

        tenants = tenants.filter(
            apartment__company_id__in=company_ids
        )

    tenant = get_object_or_404(
        tenants,
        id=tenant_id,
    )

    entries = (
        TenantLedger.objects
        .filter(
            tenant=tenant
        )
        .order_by(
            "entry_date",
            "id",
        )
    )

    balance = 0

    for entry in entries:
        balance += entry.debit
        balance -= entry.credit
        entry.running_balance = balance

    return render(
        request,
        "ledger/tenant_statement.html",
        {
            "tenant": tenant,
            "entries": entries,
            "balance": balance,
        },
    )
