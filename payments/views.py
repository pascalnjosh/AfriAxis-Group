import base64
import json
from datetime import datetime
import requests

from django.conf import settings
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Rent, Payment
from django.db import models
from .models import Rent

def dashboard(request):
    rents = Rent.objects.all()

    unpaid = rents.filter(paid=False)
    paid = rents.filter(paid=True)

    context = {
        "greeting": "AfriAxis Dashboard",
        "total_revenue": paid.aggregate(total=models.Sum("amount"))["total"] or 0,
        "rent_due": unpaid.aggregate(total=models.Sum("amount"))["total"] or 0,
        "total_payments": rents.count(),
        "successful_payments": paid.count(),
        "pending_payments": 0,
        "failed_payments": 0,
        "unpaid_rents": unpaid,
    }

    return render(request, "payments/dashboard.html", context)

def get_mpesa_access_token():
    url = f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    auth = (settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET)
    response = requests.get(url, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def rent_payment_page(request, rent_id):
    rent = get_object_or_404(Rent, id=rent_id)

    if request.method == "POST":
        phone = request.POST.get("phone_number")
        amount = int(float(request.POST.get("amount") or rent.amount))

        token = get_mpesa_access_token()

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
        password = base64.b64encode(password_raw.encode()).decode()

        callback_url = f"https://afriaxis-group-1.onrender.com/payments/mpesa/callback/"

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
            "TransactionDesc": f"Rent payment for {rent.tenant_name}",
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        url = f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest"
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()

        checkout_id = data.get("CheckoutRequestID")
        merchant_id = data.get("MerchantRequestID")

        Payment.objects.create(
            rent=rent,
            amount=amount,
            phone_number=phone,
            account_reference=f"RENT-{rent.id}",
            transaction_desc=f"Rent payment for {rent.tenant_name}",
            checkout_request_id=checkout_id,
            merchant_request_id=merchant_id,
            status="PENDING",
        )

        return render(request, "rent_payment.html", {
            "rent": rent,
            "message": "STK push sent. Complete payment on phone.",
            "mpesa_response": data,
        })

    return render(request, "rent_payment.html", {"rent": rent})


@csrf_exempt
def rent_mpesa_callback(request):
    data = json.loads(request.body.decode("utf-8") or "{}")

    callback = data.get("Body", {}).get("stkCallback", {})
    checkout_id = callback.get("CheckoutRequestID")
    result_code = callback.get("ResultCode")

    payment = Payment.objects.filter(checkout_request_id=checkout_id).first()

    if payment:
        if result_code == 0:
            receipt = None
            items = callback.get("CallbackMetadata", {}).get("Item", [])

            for item in items:
                if item.get("Name") == "MpesaReceiptNumber":
                    receipt = item.get("Value")

            payment.status = "SUCCESS"
            payment.mpesa_receipt_number = receipt
            payment.save()

            if payment.rent:
                payment.rent.paid = True
                payment.rent.save()
        else:
            payment.status = "FAILED"
            payment.save()

    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
