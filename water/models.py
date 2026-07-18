
from django.db import models
from django.contrib.auth.models import User
from rentals.models import Tenant, House


class WaterBill(models.Model):
    STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partial", "Partial"),
        ("paid", "Paid"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="manual_water_bills")
    house = models.ForeignKey(House, on_delete=models.SET_NULL, null=True, blank=True)
    billing_month = models.CharField(max_length=20)
    previous_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    units_used = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rate_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unpaid")
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.units_used = self.current_reading - self.previous_reading
        self.amount = self.units_used * self.rate_per_unit
        self.balance = self.amount - self.amount_paid

        if self.amount_paid <= 0:
            self.status = "unpaid"
        elif self.amount_paid < self.amount:
            self.status = "partial"
        else:
            self.status = "paid"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tenant} - {self.billing_month} - {self.amount}"