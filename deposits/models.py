from django.db import models
from django.contrib.auth.models import User
from rentals.models import Tenant, House


class Deposit(models.Model):
    DEPOSIT_TYPE_CHOICES = [
        ("rent_deposit", "Rent Deposit"),
        ("water_deposit", "Water Deposit"),
    ]

    STATUS_CHOICES = [
        ("held", "Held"),
        ("refunded", "Refunded"),
        ("deducted", "Deducted"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="deposits")
    house = models.ForeignKey(House, on_delete=models.SET_NULL, null=True, blank=True)
    deposit_type = models.CharField(max_length=30, choices=DEPOSIT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="held")
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    date_received = models.DateField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tenant} - {self.deposit_type} - {self.amount}"