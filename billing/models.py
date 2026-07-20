from decimal import Decimal

from django.db import models
from django.utils import timezone


class Invoice(models.Model):
    INVOICE_TYPES = (
        ("RENTAL", "Rental Invoice"),
        ("COMMERCIAL", "Commercial Invoice"),
        ("SERVICE", "Service Invoice"),
    )

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PENDING", "Pending"),
        ("PARTIAL", "Partially Paid"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    )

    ETIMS_STATUS_CHOICES = (
        ("NOT_SUBMITTED", "Not Submitted"),
        ("PENDING", "Pending Submission"),
        ("SUBMITTED", "Submitted"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    )

    tenant = models.ForeignKey(
        "rentals.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    apartment = models.ForeignKey(
        "rentals.Apartment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
    )

    invoice_type = models.CharField(
        max_length=20,
        choices=INVOICE_TYPES,
        default="RENTAL",
    )

    customer_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    customer_phone = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    customer_email = models.EmailField(
        blank=True,
        default="",
    )

    customer_address = models.TextField(
        blank=True,
        default="",
    )

    customer_kra_pin = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    invoice_date = models.DateField(
        default=timezone.now,
    )

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    currency = models.CharField(
        max_length=10,
        default="KES",
    )

    rent_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    wifi_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    water_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    amount_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    terms = models.TextField(
        blank=True,
        default="",
    )

    etims_status = models.CharField(
        max_length=20,
        choices=ETIMS_STATUS_CHOICES,
        default="NOT_SUBMITTED",
    )

    etims_control_unit_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    etims_receipt_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    etims_internal_data = models.TextField(
        blank=True,
        default="",
    )

    etims_signature = models.TextField(
        blank=True,
        default="",
    )

    etims_qr_code_url = models.URLField(
        blank=True,
        default="",
    )

    etims_submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def balance(self):
        return self.total_amount - self.amount_paid

    def calculate_totals(self, save=True):
        lines = self.lines.all()

        if lines.exists():
            subtotal = sum(
                (line.line_subtotal for line in lines),
                Decimal("0.00"),
            )

            discount = sum(
                (line.discount_amount for line in lines),
                Decimal("0.00"),
            )

            tax = sum(
                (line.tax_amount for line in lines),
                Decimal("0.00"),
            )

            self.subtotal = subtotal
            self.discount_amount = discount
            self.tax_amount = tax
            self.total_amount = subtotal - discount + tax

        else:
            self.subtotal = (
                self.rent_amount
                + self.wifi_amount
                + self.water_amount
            )

            self.total_amount = (
                self.subtotal
                - self.discount_amount
                + self.tax_amount
            )

        if save:
            self.save(
                update_fields=[
                    "subtotal",
                    "discount_amount",
                    "tax_amount",
                    "total_amount",
                    "updated_at",
                ]
            )

        return self.total_amount

    def recalculate_status(self):
        payments_total = self.invoicepayment_set.aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

        self.amount_paid = payments_total

        if self.status == "CANCELLED":
            pass
        elif self.amount_paid >= self.total_amount:
            self.status = "PAID"
        elif self.amount_paid > 0:
            self.status = "PARTIAL"
        else:
            self.status = "PENDING"

        self.save(
            update_fields=[
                "amount_paid",
                "status",
                "updated_at",
            ]
        )

    def save(self, *args, **kwargs):
        if self.tenant:
            if not self.customer_name:
                self.customer_name = self.tenant.name

            if not self.customer_phone:
                self.customer_phone = self.tenant.phone

        super().save(*args, **kwargs)

    def __str__(self):
        customer = self.customer_name

        if not customer and self.tenant:
            customer = self.tenant.name

        return f"{self.invoice_number} - {customer or 'Customer'}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    item_code = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    description = models.CharField(
        max_length=255,
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=1,
    )

    unit = models.CharField(
        max_length=30,
        default="EA",
    )

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    discount_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    line_subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def calculate(self):
        quantity = Decimal(self.quantity)
        unit_price = Decimal(self.unit_price)
        discount_rate = Decimal(self.discount_rate)
        tax_rate = Decimal(self.tax_rate)

        self.line_subtotal = quantity * unit_price

        self.discount_amount = (
            self.line_subtotal
            * discount_rate
            / Decimal("100")
        )

        taxable_amount = (
            self.line_subtotal
            - self.discount_amount
        )

        self.tax_amount = (
            taxable_amount
            * tax_rate
            / Decimal("100")
        )

        self.line_total = (
            taxable_amount
            + self.tax_amount
        )

    def save(self, *args, **kwargs):
        self.calculate()
        super().save(*args, **kwargs)
        self.invoice.calculate_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.calculate_totals()

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description}"


class InvoicePayment(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    phone_number = models.CharField(
        max_length=20,
    )

    mpesa_receipt = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    paid_at = models.DateTimeField(
        default=timezone.now,
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
