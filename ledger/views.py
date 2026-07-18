from django.shortcuts import render, get_object_or_404

from rentals.models import Tenant
from .models import TenantLedger


def tenant_statement(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)

    entries = (
        TenantLedger.objects
        .filter(tenant=tenant)
        .order_by("entry_date", "id")
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