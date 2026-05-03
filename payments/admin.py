from django.contrib import admin
from .models import Payment, Rent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "amount", "payment_method", "status", "created_at")
    list_filter = ("payment_method", "status", "created_at")
    search_fields = ("phone_number", "account_reference", "mpesa_receipt_number")


@admin.register(Rent)
class RentAdmin(admin.ModelAdmin):
    list_display = ("tenant_name", "amount", "paid", "due_date")
    list_filter = ("paid", "due_date")
    search_fields = ("tenant_name",)
