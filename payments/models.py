from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Rent(models.Model):
    tenant_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    mpesa_receipt = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.tenant_name} - {self.amount}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    rent = models.ForeignKey(Rent, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1.00"))],
    )
    phone_number = models.CharField(max_length=15)
    transaction_code = models.CharField(max_length=50, blank=True, null=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    verified = models.BooleanField(default=False)
    payment_date = models.DateTimeField(default=timezone.now)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment #{self.id} - Rent {self.rent_id} - {self.amount}"


class MpesaCallbackLog(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    result_code = models.IntegerField()
    result_desc = models.TextField()
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.checkout_request_id or f"callback-{self.id}"
