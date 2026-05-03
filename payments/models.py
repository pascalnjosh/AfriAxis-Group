from django.db import models

# ======================
# MPESA PAYMENTS
# ======================

class Payment(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    transaction_code = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.phone_number} - {self.amount}"


class MpesaCallbackLog(models.Model):
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


# ======================
# RENT SYSTEM
# ======================

class Rent(models.Model):
    tenant_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, default="PENDING")

    def __str__(self):
        return self.tenant_name
