from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from enterprise.models import Company

from .reports import get_trial_balance


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None


@login_required
def trial_balance(request):
    company = Company.objects.first()

    if company is None:
        raise Http404(
            "No company has been configured."
        )

    date_from = parse_date(
        request.GET.get("date_from")
    )

    date_to = parse_date(
        request.GET.get("date_to")
    )

    report = get_trial_balance(
        company=company,
        date_from=date_from,
        date_to=date_to,
    )

    return render(
        request,
        "accounting/trial_balance.html",
        {
            "company": company,
            "report": report,
            "date_from": date_from,
            "date_to": date_to,
        },
    )
