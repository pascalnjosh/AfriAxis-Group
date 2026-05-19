import base64
import json
from datetime import datetime

import requests

from django.conf import settings
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from .models import Payment
from rentals.models import Rent
from billing.utils import apply_mpesa_to_invoice


def user_role(request):

    profile = getattr(
        request.user,
        "userprofile",
        None
    )

    if profile:
        return profile.role

    return None


def dashboard(request):

    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "ACCOUNTS"]:
        return redirect("/accounts/home/")

    rents = Rent.objects.all().order_by("due_date")

    unpaid = rents.filter(paid=False)

    paid = rents.filter(
        paid=True
    ).order_by("due_date")

    payments = Payment.objects.all().order_by(
        "-created_at"
    )[:50]

    collected_total = Payment.objects.filter(
        status="SUCCESS"
    ).aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    unpaid_total = unpaid.aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    net_outstanding = unpaid_total - collected_total

    context = {
        "greeting": "AfriAxis Payments Dashboard",
        "total_rents": rents.count(),
        "total_revenue": collected_total,
        "rent_due": unpaid_total,
        "net_outstanding": net_outstanding,
        "successful_payments": Payment.objects.filter(status="SUCCESS").count(),
        "pending_payments": Payment.objects.filter(status="PENDING").count(),
        "failed_payments": Payment.objects.filter(status="FAILED").count(),
        "unpaid_rents": unpaid,
        "paid_rents": paid,
        "payments": payments,
    }

    return render(
        request,
        "payments/dashboard.html",
        context
    )


def get_mpesa_access_token():

    url = f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"

    auth = (
        settings.MPESA_CONSUMER_KEY,
        settings.MPESA_CONSUMER_SECRET
    )

    response = requests.get(
        url,
        auth=auth,
        timeout=30
    )

    response.raise_for_status()

    return response.json()["access_token"]


def rent_payment_page(request, rent_id):

    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "ACCOUNTS"]:
        return redirect("/accounts/home/")

    rent = get_object_or_404(
        Rent,
        id=rent_id
    )

    if request.method == "POST":

        phone = request.POST.get("phone_number")

        amount = int(
            float(
                request.POST.get("amount") or rent.amount
            )
        )

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

        callback_url = (
            "https://afriaxis-group-1.onrender.com/"
            "payments/mpesa/callback/"
        )

        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": f"RENT-{rent.id}",
            "TransactionDesc": (
                f"Rent payment for {rent.tenant.name}"
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
            timeout=30
        )

        data = response.json()

        Payment.objects.create(
            rental_rent=rent,
            amount=amount,
            phone_number=phone,
            account_reference=f"RENT-{rent.id}",
            transaction_desc=(
                f"Rent payment for {rent.tenant.name}"
            ),
            checkout_request_id=data.get("CheckoutRequestID"),
            merchant_request_id=data.get("MerchantRequestID"),
            status="PENDING",
        )

        return render(
            request,
            "rent_payment.html",
            {
                "rent": rent,
                "message": "STK push sent. Complete payment on phone.",
                "mpesa_response": data,
            }
        )

    return render(
        request,
        "rent_payment.html",
        {"rent": rent}
    )


@csrf_exempt
def rent_mpesa_callback(request):

    data = json.loads(
        request.body.decode("utf-8") or "{}"
    )

    callback = data.get("Body", {}).get("stkCallback", {})

    checkout_id = callback.get("CheckoutRequestID")

    result_code = callback.get("ResultCode")

    payment = Payment.objects.filter(
        checkout_request_id=checkout_id
    ).first()

    if payment:

        if result_code == 0:

            receipt = None

            items = callback.get(
                "CallbackMetadata",
                {}
            ).get(
                "Item",
                []
            )

            for item in items:

                if item.get("Name") == "MpesaReceiptNumber":
                    receipt = item.get("Value")

            payment.status = "SUCCESS"`r`n            payment.mpesa_receipt_number = receipt`r`n            payment.save()`r`n`r`n            apply_mpesa_to_invoice(`r`n                phone_number=payment.phone_number,`r`n                amount=payment.amount,`r`n                receipt=receipt`r`n            )`r`n`r`n            if payment.rental_rent:`r`n                payment.rental_rent.paid = True`r`n                payment.rental_rent.save()

        else:
            payment.status = "FAILED"
            payment.save()

    return JsonResponse({
        "ResultCode": 0,
        "ResultDesc": "Accepted"
    })


def payment_receipt(request, payment_id):

    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    role = user_role(request)

    if role not in ["MD", "ACCOUNTS"]:
        return redirect("/accounts/home/")

    payment = get_object_or_404(
        Payment,
        id=payment_id
    )

    return render(
        request,
        "payments/receipt.html",
        {
            "payment": payment
        }
    )



