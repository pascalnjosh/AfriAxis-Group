from django.db import models
from django.contrib.auth.models import User


class MoneyIn(models.Model):
    SOURCE_CHOICES = [
        ("rent", "Rent"),
        ("water", "Water"),
        ("wifi", "Wi-Fi"),
        ("rent_deposit", "Rent Deposit"),
        ("water_deposit", "Water Deposit"),
        ("other", "Other"),
    ]

    source = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    received_from = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=100, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    date_received = models.DateField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.source} - {self.amount}"


class MoneyOut(models.Model):
    CATEGORY_CHOICES = [
        ("repairs", "Repairs"),
        ("maintenance", "Maintenance"),
        ("salary", "Salary"),
        ("water_payment", "Water Payment"),
        ("electricity", "Electricity"),
        ("office", "Office Expense"),
        ("other", "Other"),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_to = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=100, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    date_paid = models.DateField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.category} - {self.amount}"