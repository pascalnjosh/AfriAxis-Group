import base64
import json
from datetime import datetime, timedelta

import requests

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import (
    WifiPackage,
    WifiCustomer,
    WifiPayment,
    WifiCallbackLog,
)


def wifi_packages_page(request):
    packages = WifiPackage.objects.all().order_by("price")

    return render(
        request,
        "services/wifi_packages.html",
        {"packages": packages},
    )


def wifi_payment_page(request, customer_id):
    customer = get_object_or_404(
        WifiCustomer,
        id=customer_id,
    )

    packages = WifiPackage.objects.all().order_by("price")

    return render(
        request,
        "services/wifi_payment.html",
        {
            "customer": customer,
            "packages": packages,
        },
    )


def wifi_status(request, customer_id):
    customer = get_object_or_404(
        WifiCustomer,
        id=customer_id,
    )

    customer.refresh_status()

    latest_payment = (
        WifiPayment.objects
        .filter(customer=customer)
        .order_by("-created_at")
        .first()
    )

    if request.headers.get("Accept") == "application/json":
        return JsonResponse({
            "customer_id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "active": customer.active,
            "package": (
                customer.package.name
                if customer.package
                else None
            ),
            "start_date": customer.start_date,
            "expiry_date": customer.expiry_date,
            "expired": customer.is_overdue,
            "payment_status": (
                latest_payment.status
                if latest_payment
                else None
            ),
        })

    return render(
        request,
        "services/wifi_status.html",
        {
            "name": customer.name,
            "active": customer.active,
            "package": (
                customer.package.name
                if customer.package
                else None
            ),
            "expiry_date": customer.expiry_date,
            "latest_payment": latest_payment,
        },
    )


def normalize_phone_number(phone):
    phone = str(phone or "").strip()
    phone = phone.replace(" ", "").replace("-", "")

    if phone.startswith("+254"):
        return "254" + phone[4:]

    if phone.startswith("0"):
        return "254" + phone[1:]

    if phone.startswith("254"):
        return phone

    return phone


def get_mpesa_access_token():
    url = (
        f"{settings.MPESA_BASE_URL}"
        "/oauth/v1/generate"
        "?grant_type=client_credentials"
    )

    response = requests.get(
        url,
        auth=(
            settings.MPESA_CONSUMER_KEY,
            settings.MPESA_CONSUMER_SECRET,
        ),
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data["access_token"]


@csrf_exempt
def wifi_stk_push(request, customer_id):
    customer = get_object_or_404(
        WifiCustomer,
        id=customer_id,
    )

    try:
        data = json.loads(
            request.body.decode("utf-8")
        )
    except Exception:
        data = request.POST

    package_id = data.get("package_id")

    package = get_object_or_404(
        WifiPackage,
        id=package_id,
    )

    phone_number = normalize_phone_number(
        data.get("phone_number")
        or data.get("phone")
        or customer.phone
    )

    if not phone_number.startswith("254"):
        return JsonResponse(
            {
                "error": "Invalid Kenyan phone number."
            },
            status=400,
        )

    payment = WifiPayment.objects.create(
        customer=customer,
        package=package,
        amount=package.price,
        phone_number=phone_number,
        status="PENDING",
        verified=False,
    )

    try:
        token = get_mpesa_access_token()

        timestamp = datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )

        password_raw = (
            f"{settings.MPESA_SHORTCODE}"
            f"{settings.MPESA_PASSKEY}"
            f"{timestamp}"
        )

        password = base64.b64encode(
            password_raw.encode()
        ).decode()

        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(package.price),
            "PartyA": phone_number,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": f"WIFI-{payment.id}",
            "TransactionDesc": (
                f"WiFi payment - {package.name}"
            ),
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        url = (
            f"{settings.MPESA_BASE_URL}"
            "/mpesa/stkpush/v1/processrequest"
        )

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        mpesa_response = response.json()

        payment.merchant_request_id = (
            mpesa_response.get(
                "MerchantRequestID"
            )
        )

        payment.checkout_request_id = (
            mpesa_response.get(
                "CheckoutRequestID"
            )
        )

        if mpesa_response.get("ResponseCode") != "0":
            payment.status = "FAILED"

        payment.save(
            update_fields=[
                "merchant_request_id",
                "checkout_request_id",
                "status",
            ]
        )

        return JsonResponse({
            "message": (
                "M-Pesa STK Push sent."
            ),
            "payment_id": payment.id,
            "customer": customer.name,
            "package": package.name,
            "amount": str(package.price),
            "phone_number": phone_number,
            "status": payment.status,
            "checkout_request_id": (
                payment.checkout_request_id
            ),
        })

    except requests.RequestException as exc:
        payment.status = "FAILED"

        payment.save(
            update_fields=["status"]
        )

        return JsonResponse(
            {
                "error": "M-Pesa request failed.",
                "details": str(exc),
                "payment_id": payment.id,
            },
            status=502,
        )

    except Exception as exc:
        payment.status = "FAILED"

        payment.save(
            update_fields=["status"]
        )

        return JsonResponse(
            {
                "error": "Unable to initiate M-Pesa payment.",
                "details": str(exc),
                "payment_id": payment.id,
            },
            status=500,
        )


@csrf_exempt
def wifi_callback(request):
    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )
    except Exception:
        return JsonResponse(
            {"error": "Invalid JSON"},
            status=400,
        )

    WifiCallbackLog.objects.create(
        data=payload
    )

    callback = (
        payload
        .get("Body", {})
        .get("stkCallback", {})
    )

    checkout_request_id = callback.get(
        "CheckoutRequestID"
    )

    result_code = callback.get(
        "ResultCode"
    )

    payment = (
        WifiPayment.objects
        .filter(
            checkout_request_id=checkout_request_id
        )
        .first()
    )

    if not payment:
        return JsonResponse(
            {
                "ResultCode": 0,
                "ResultDesc": (
                    "Callback received but payment "
                    "was not found."
                ),
            }
        )

    if result_code == 0:
        receipt = None
        amount = None
        phone_number = None

        items = (
            callback
            .get("CallbackMetadata", {})
            .get("Item", [])
        )

        for item in items:
            name = item.get("Name")
            value = item.get("Value")

            if name == "MpesaReceiptNumber":
                receipt = value

            elif name == "Amount":
                amount = value

            elif name == "PhoneNumber":
                phone_number = value

        payment.transaction_code = receipt
        payment.status = "SUCCESS"
        payment.verified = True

        payment.save(
            update_fields=[
                "transaction_code",
                "status",
                "verified",
            ]
        )

        customer = payment.customer
        package = payment.package
        now = timezone.now()

        customer.package = package
        customer.active = True
        customer.start_date = now

        if (
            package
            and package.duration_minutes
            and package.duration_minutes > 0
        ):
            customer.expiry_date = (
                now
                + timedelta(
                    minutes=package.duration_minutes
                )
            )

        elif (
            package
            and package.duration_days
            and package.duration_days > 0
        ):
            customer.expiry_date = (
                now
                + timedelta(
                    days=package.duration_days
                )
            )

        else:
            customer.expiry_date = (
                now + timedelta(days=30)
            )

        customer.save(
            update_fields=[
                "package",
                "active",
                "start_date",
                "expiry_date",
            ]
        )

    else:
        payment.status = "FAILED"
        payment.verified = False

        payment.save(
            update_fields=[
                "status",
                "verified",
            ]
        )

    return JsonResponse({
        "ResultCode": 0,
        "ResultDesc": "Accepted",
    })
