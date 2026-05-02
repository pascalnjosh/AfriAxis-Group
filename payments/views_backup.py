import json
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from services.models import WifiCustomer
from .models import Payment, Rent, MpesaCallbackLog


@require_GET
def dashboard(request):
    # --- PAYMENT STATS ---
    total_payments = Payment.objects.count()
    successful_payments = Payment.objects.filter(status=Payment.Status.SUCCESS).count()
    pending_payments = Payment.objects.filter(status=Payment.Status.PENDING).count()
    failed_payments = Payment.objects.filter(status=Payment.Status.FAILED).count()

    # --- RENT ANALYSIS ---
    unpaid_rents = Rent.objects.filter(paid=False).order_by("id")
    paid_rents = Rent.objects.filter(paid=True).order_by("-id")[:5]

    total_unpaid_amount = sum((rent.amount for rent in unpaid_rents), Decimal("0.00"))

    # --- WIFI ANALYSIS ---
    wifi_customers = WifiCustomer.objects.all()

    active_wifi = wifi_customers.filter(active=True)
    inactive_wifi = wifi_customers.filter(active=False)

    expired_wifi = [c for c in wifi_customers if c.is_overdue]

    # --- FINANCIAL ---
    total_revenue = sum(
        (p.amount for p in Payment.objects.filter(status=Payment.Status.SUCCESS)),
        Decimal("0.00")
    )

    # --- CONTEXT ---
    context = {
        "greeting": "System Control Panel",

        # MONEY
        "total_revenue": f"Ksh {total_revenue}",
        "rent_due": f"Ksh {total_unpaid_amount}",

        # PAYMENTS
        "total_payments": total_payments,
        "successful_payments": successful_payments,
        "pending_payments": pending_payments,
        "failed_payments": failed_payments,

        # RENT
        "unpaid_rents": unpaid_rents,
        "paid_rents": paid_rents,

        # WIFI
        "wifi_customers": wifi_customers[:5],
        "active_wifi_count": active_wifi.count(),
        "inactive_wifi_count": inactive_wifi.count(),
        "expired_wifi_count": len(expired_wifi),
    }

    return render(request, "payments/dashboard.html", context)


@require_GET
def rent_payment_page(request, rent_id):
    rent = get_object_or_404(Rent, id=rent_id)
    latest_payment = Payment.objects.filter(rent=rent).order_by("-id").first()

    context = {
        "rent": rent,
        "latest_payment": latest_payment,
    }
    return render(request, "payments/rent_pay.html", context)


@require_GET
def rent_status(request, rent_id):
    rent = get_object_or_404(Rent, id=rent_id)
    latest_payment = Payment.objects.filter(rent=rent).order_by("-id").first()

    data = {
        "rent_id": rent.id,
        "tenant_name": rent.tenant_name,
        "amount": str(rent.amount),
        "paid": rent.paid,
        "mpesa_receipt": rent.mpesa_receipt,
        "latest_payment": None,
    }

    if latest_payment:
        data["latest_payment"] = {
            "id": latest_payment.id,
            "amount": str(latest_payment.amount),
            "phone_number": latest_payment.phone_number,
            "status": latest_payment.status,
            "transaction_code": latest_payment.transaction_code,
            "verified": latest_payment.verified,
            "checkout_request_id": latest_payment.checkout_request_id,
        }

    return JsonResponse(data)


@csrf_exempt
@require_POST
def stk_push_for_rent(request, rent_id):
    rent = get_object_or_404(Rent, id=rent_id)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    phone_number = str(body.get("phone_number", "")).strip()
    amount = body.get("amount", rent.amount)

    if not phone_number:
        return JsonResponse({"error": "phone_number is required"}, status=400)

    payment = Payment.objects.create(
        rent=rent,
        amount=Decimal(str(amount)),
        phone_number=phone_number,
        merchant_request_id=f"test-merchant-{rent.id}",
        checkout_request_id=f"test-checkout-{rent.id}",
        status=Payment.Status.PENDING,
        verified=False,
    )

    return JsonResponse({
        "message": "Test payment created",
        "payment_id": payment.id,
        "checkout_request_id": payment.checkout_request_id,
        "rent_id": rent.id,
        "tenant_name": rent.tenant_name,
        "amount": str(payment.amount),
        "phone_number": payment.phone_number,
        "status": payment.status,
    })


@csrf_exempt
def mpesa_callback(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    stk_callback = payload.get("Body", {}).get("stkCallback", {})
    merchant_request_id = stk_callback.get("MerchantRequestID")
    checkout_request_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc")

    items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
    values = {item.get("Name"): item.get("Value") for item in items if "Name" in item}
    receipt = values.get("MpesaReceiptNumber")

    payment = Payment.objects.filter(checkout_request_id=checkout_request_id).first()

    MpesaCallbackLog.objects.create(
        payment=payment,
        merchant_request_id=merchant_request_id,
        checkout_request_id=checkout_request_id,
        result_code=result_code,
        result_desc=result_desc,
        receipt_number=receipt,
    )

    if payment:
        payment.merchant_request_id = merchant_request_id
        payment.checkout_request_id = checkout_request_id

        if receipt:
            payment.transaction_code = str(receipt)

        if result_code == 0:
            payment.status = Payment.Status.SUCCESS
            payment.verified = True
        else:
            payment.status = Payment.Status.FAILED
            payment.verified = False

        payment.save()

        if result_code == 0:
            rent = payment.rent
            rent.paid = True
            rent.mpesa_receipt = str(receipt) if receipt else rent.mpesa_receipt
            rent.save()

    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})

