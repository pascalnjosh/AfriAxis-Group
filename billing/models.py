from django.db import models
from django.utils import timezone


class Invoice(models.Model):
    tenant = models.ForeignKey(
        "rentals.Tenant",
        on_delete=models.CASCADE
    )

    apartment = models.ForeignKey(
        "rentals.Apartment",
        on_delete=models.SET_NULL,
        null=True
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True
    )

    rent_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    wifi_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    water_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    status = models.CharField(
        max_length=20,
        default="PENDING"
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )

    def balance(self):
        return self.total_amount - self.amount_paid

    def recalculate_status(self):

        payments_total = self.invoicepayment_set.aggregate(
            total=models.Sum("amount")
        )["total"] or 0

        self.amount_paid = payments_total

        if self.amount_paid >= self.total_amount:
            self.status = "PAID"

        elif self.amount_paid > 0:
            self.status = "PARTIAL"

        else:
            self.status = "PENDING"

        self.save()

    def __str__(self):
        return f"{self.invoice_number} - {self.tenant}"


class InvoicePayment(models.Model):

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    phone_number = models.CharField(
        max_length=20
    )

    mpesa_receipt = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    paid_at = models.DateTimeField(
        default=timezone.now
    )

    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)

        self.invoice.recalculate_status()

    def delete(self, *args, **kwargs):

        invoice = self.invoice

        super().delete(*args, **kwargs)

        invoice.recalculate_status()

    def __str__(self):
        return f"{self.invoice} - {self.amount}"
