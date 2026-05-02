from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
import json

from .models import WifiPackage, WifiCustomer, WifiPayment, WifiCallbackLog


def wifi_packages_page(request):
    packages = WifiPackage.objects.all().order_by("price")
    return render(request, "services/wifi_packages.html", {"packages": packages})


def wifi_payment_page(request, customer_id):
    customer = get_object_or_404(WifiCustomer, id=customer_id)
    packages = WifiPackage.objects.all().order_by("price")

    if request.method == "POST":
        package = get_object_or_404(WifiPackage, id=request.POST.get("package_id"))
        phone = request.POST.get("phone") or customer.phone

        WifiPayment.objects.create(
            customer=customer,
            package=package,
            amount=package.price,
            phone_number=phone,
            status="PENDING",
            verified=False,
        )

        return redirect(f"/services/wifi/{customer.id}/status/")

    return render(request, "services/wifi_payment.html", {
        "customer": customer,
        "packages": packages,
    })


def wifi_status(request, customer_id):
    customer = get_object_or_404(WifiCustomer, id=customer_id)
    customer.refresh_status()

    if request.headers.get("Accept") == "application/json":
        return JsonResponse({
            "customer_id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "active": customer.active,
            "package": customer.package.name if customer.package else None,
            "start_date": customer.start_date,
            "expiry_date": customer.expiry_date,
            "expired": customer.is_overdue,
        })

    return render(request, "services/wifi_status.html", {
        "name": customer.name,
        "active": customer.active,
        "package": customer.package.name if customer.package else None,
        "expiry_date": customer.expiry_date,
    })


@csrf_exempt
def wifi_stk_push(request, customer_id):
    customer = get_object_or_404(WifiCustomer, id=customer_id)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        data = request.POST

    package = get_object_or_404(WifiPackage, id=data.get("package_id"))
    phone_number = str(data.get("phone_number") or data.get("phone") or customer.phone).strip()

    payment = WifiPayment.objects.create(
        customer=customer,
        package=package,
        amount=package.price,
        phone_number=phone_number,
        status="PENDING",
        verified=False,
    )

    return JsonResponse({
        "message": "WiFi payment created",
        "payment_id": payment.id,
        "customer": customer.name,
        "package": package.name,
        "amount": str(package.price),
        "phone_number": phone_number,
        "status": payment.status,
    })


@csrf_exempt
def wifi_callback(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    WifiCallbackLog.objects.create(data=payload)

    payment_id = payload.get("payment_id")
    result_code = int(payload.get("ResultCode", 1))
    receipt = payload.get("MpesaReceiptNumber", "")

    payment = WifiPayment.objects.filter(id=payment_id).first()
    if not payment:
        return JsonResponse({"error": "Payment not found"}, status=404)

    if result_code == 0:
        payment.status = "SUCCESS"
        payment.verified = True
        payment.transaction_code = receipt
        payment.save()

        customer = payment.customer
        package = payment.package
        now = timezone.now()

        customer.package = package
        customer.active = True
        customer.start_date = now

        if package.duration_minutes and package.duration_minutes > 0:
            customer.expiry_date = now + timedelta(minutes=package.duration_minutes)
        elif package.duration_days and package.duration_days > 0:
            customer.expiry_date = now + timedelta(days=package.duration_days)
        else:
            customer.expiry_date = now + timedelta(days=30)

        customer.save()

    else:
        payment.status = "FAILED"
        payment.verified = False
        payment.save()

    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
