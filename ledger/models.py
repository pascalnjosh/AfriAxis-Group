from django.db import models
from django.utils import timezone

from rentals.models import Tenant
from rentals.models import Rent


class TenantLedger(models.Model):

    ENTRY_TYPES = [
        ("rent", "Rent"),
        ("payment", "Payment"),
        ("adjustment", "Adjustment"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )

    rent = models.ForeignKey(
        Rent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    entry_type = models.CharField(
        max_length=20,
        choices=ENTRY_TYPES,
    )

    description = models.CharField(max_length=255)

    debit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    entry_date = models.DateField(
        default=timezone.now,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["entry_date", "id"]

    def __str__(self):
        return f"{self.tenant.name} - {self.entry_type}"