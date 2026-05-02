from django.contrib import admin
from .models import Payment, MpesaCallbackLog, Rent


@admin.register(Rent)
class RentAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant_name", "amount", "paid", "mpesa_receipt")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "rent", "amount", "phone_number", "status", "transaction_code", "verified", "payment_date")
    list_filter = ("status", "verified")


@admin.register(MpesaCallbackLog)
class MpesaCallbackLogAdmin(admin.ModelAdmin):
    list_display = ("id", "payment", "checkout_request_id", "result_code", "receipt_number", "received_at")
