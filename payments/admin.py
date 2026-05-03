from django.contrib import admin
from .models import Payment, MpesaCallbackLog, Rent

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "phone_number", "amount", "status", "transaction_code", "created_at")


@admin.register(MpesaCallbackLog)
class MpesaCallbackLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")


@admin.register(Rent)
class RentAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant_name", "amount", "due_date", "status")
