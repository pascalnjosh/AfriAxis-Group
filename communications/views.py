from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import audit_required, finance_required

from rentals.models import Rent
from services.models import WaterBill, WifiCustomer

from .billing import (
    send_rent_bill_sms,
    send_water_bill_sms,
    send_wifi_bill_sms,
)
from .models import SmsMessage


@audit_required
def sms_dashboard(request):

    rows = SmsMessage.objects.select_related(
        "tenant",
        "rent",
        "water_bill",
        "wifi_customer",
    )[:250]

    context = {
        "rows": rows,
        "total": SmsMessage.objects.count(),
        "queued": SmsMessage.objects.filter(
            status=SmsMessage.Status.QUEUED
        ).count(),
        "test": SmsMessage.objects.filter(
            status=SmsMessage.Status.TEST
        ).count(),
        "sent": SmsMessage.objects.filter(
            status=SmsMessage.Status.SENT
        ).count(),
        "failed": SmsMessage.objects.filter(
            status=SmsMessage.Status.FAILED
        ).count(),
    }

    return render(
        request,
        "communications/dashboard.html",
        context,
    )


@finance_required
@require_POST
def send_rent_sms(request, rent_id):

    rent = get_object_or_404(
        Rent.objects.select_related(
            "tenant",
            "house",
            "tenant__apartment",
        ),
        pk=rent_id,
    )

    try:
        sms = send_rent_bill_sms(
            rent,
            user=request.user,
        )

        messages.success(
            request,
            f"Rent SMS {sms.status}: {sms.phone_number}",
        )

    except Exception as exc:
        messages.error(
            request,
            f"Rent SMS failed: {exc}",
        )

    return redirect("sms_dashboard")


@finance_required
@require_POST
def send_water_sms(request, bill_id):

    bill = get_object_or_404(
        WaterBill.objects.select_related(
            "tenant",
            "tenant__apartment",
        ),
        pk=bill_id,
    )

    try:
        sms = send_water_bill_sms(
            bill,
            user=request.user,
        )

        messages.success(
            request,
            f"Water SMS {sms.status}: {sms.phone_number}",
        )

    except Exception as exc:
        messages.error(
            request,
            f"Water SMS failed: {exc}",
        )

    return redirect("sms_dashboard")


@finance_required
@require_POST
def send_wifi_sms(request, customer_id):

    customer = get_object_or_404(
        WifiCustomer.objects.select_related(
            "package",
        ),
        pk=customer_id,
    )

    try:
        sms = send_wifi_bill_sms(
            customer,
            user=request.user,
        )

        messages.success(
            request,
            f"Wi-Fi SMS {sms.status}: {sms.phone_number}",
        )

    except Exception as exc:
        messages.error(
            request,
            f"Wi-Fi SMS failed: {exc}",
        )

    return redirect("sms_dashboard")
