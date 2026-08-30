from django.conf import settings
from django.db import models


class SmsMessage(models.Model):

    class BillType(models.TextChoices):
        RENT = "RENT", "Rent"
        WATER = "WATER", "Water"
        WIFI = "WIFI", "Wi-Fi"
        RECEIPT = "RECEIPT", "Receipt"
        GENERAL = "GENERAL", "General"

    class Status(models.TextChoices):
        TEST = "TEST", "Test"
        QUEUED = "QUEUED", "Queued"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        DELIVERED = "DELIVERED", "Delivered"

    phone_number = models.CharField(
        max_length=20,
        db_index=True,
    )

    recipient_name = models.CharField(
        max_length=200,
        blank=True,
    )

    bill_type = models.CharField(
        max_length=20,
        choices=BillType.choices,
        default=BillType.GENERAL,
        db_index=True,
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )

    provider = models.CharField(
        max_length=50,
        blank=True,
    )

    provider_message_id = models.CharField(
        max_length=200,
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
    )

    reference = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
    )

    tenant = models.ForeignKey(
        "rentals.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_messages",
    )

    rent = models.ForeignKey(
        "rentals.Rent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_messages",
    )

    water_bill = models.ForeignKey(
        "services.WaterBill",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_messages",
    )

    wifi_customer = models.ForeignKey(
        "services.WifiCustomer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_messages",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sms_messages",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.bill_type} | {self.phone_number} | {self.status}"
