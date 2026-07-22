from django.db import models


class EtimsConfiguration(models.Model):
    ENVIRONMENT_CHOICES = (
        ("SANDBOX", "Sandbox"),
        ("PRODUCTION", "Production"),
    )

    company_name = models.CharField(
        max_length=200,
        default="AfriAxis Group",
    )

    kra_pin = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    branch_id = models.CharField(
        max_length=20,
        blank=True,
        default="00",
    )

    device_serial_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default="SANDBOX",
    )

    api_base_url = models.URLField(
        blank=True,
        default="",
    )

    client_id = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    client_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.company_name} - {self.environment}"
