from django.http import JsonResponse

from enterprise.models import Company
from rentals.models import Apartment, House, Tenant
from banking.models import BankAccount, BankStatementUpload, BankTransaction
from accounts.models import CompanyAssignment


def live_africore_diagnostic(request):
    c = Company.objects.filter(name="AFRICORE HEIGHTS").first()

    if not c:
        return JsonResponse({
            "company": None,
            "message": "AFRICORE HEIGHTS NOT FOUND",
        })

    apartments = []

    for a in Apartment.objects.filter(company=c).order_by("id"):
        apartments.append({
            "name": a.name,
            "units": a.total_units,
            "houses": House.objects.filter(apartment=a).count(),
            "tenants": Tenant.objects.filter(apartment=a).count(),
        })

    return JsonResponse({
        "company_id": c.id,
        "apartments": apartments,
        "total_houses": House.objects.filter(
            apartment__company=c
        ).count(),
        "bank_accounts": BankAccount.objects.filter(
            company=c
        ).count(),
        "statements": BankStatementUpload.objects.filter(
            bank_account__company=c
        ).count(),
        "transactions": BankTransaction.objects.filter(
            bank_account__company=c
        ).count(),
        "assignments": CompanyAssignment.objects.filter(
            company=c
        ).count(),
    })
