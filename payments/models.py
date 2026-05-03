from django.db import models
from django.utils import timezone


class Rent(models.Model):
    tenant_name = models.CharField(max_length=150, default="Unknown")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)
    due_date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.tenant_name} - {self.amount}"


class Payment(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    ]

    rent = models.ForeignKey(Rent, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    account_reference = models.CharField(max_length=100, blank=True, null=True)
    transaction_desc = models.CharField(max_length=255, blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=50, default="MPESA")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.phone_number or 'Payment'} - {self.amount} - {self.status}"
