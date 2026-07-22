from django.db import models
from django.utils import timezone


class Currency(models.Model):
    code = models.CharField(
        max_length=3,
        unique=True,
    )

    name = models.CharField(
        max_length=100,
    )

    symbol = models.CharField(
        max_length=10,
        blank=True,
        default="",
    )

    decimal_places = models.PositiveSmallIntegerField(
        default=2,
    )

    active = models.BooleanField(
        default=True,
    )

    def __str__(self):
        return f"{self.code} - {self.name}"


class Company(models.Model):
    name = models.CharField(
        max_length=200,
        unique=True,
    )

    legal_name = models.CharField(
        max_length=250,
        blank=True,
        default="",
    )

    registration_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    kra_pin = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    email = models.EmailField(
        blank=True,
        default="",
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    website = models.URLField(
        blank=True,
        default="",
    )

    address = models.TextField(
        blank=True,
        default="",
    )

    country = models.CharField(
        max_length=100,
        default="Kenya",
    )

    base_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="companies",
        null=True,
        blank=True,
    )

    logo = models.ImageField(
        upload_to="enterprise/company_logos/",
        null=True,
        blank=True,
    )

    active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name


class Branch(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="branches",
    )

    code = models.CharField(
        max_length=20,
    )

    name = models.CharField(
        max_length=150,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    email = models.EmailField(
        blank=True,
        default="",
    )

    address = models.TextField(
        blank=True,
        default="",
    )

    is_head_office = models.BooleanField(
        default=False,
    )

    active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_branch_code_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class Department(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="departments",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="departments",
        null=True,
        blank=True,
    )

    code = models.CharField(
        max_length=20,
    )

    name = models.CharField(
        max_length=150,
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    active = models.BooleanField(
        default=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_department_code_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class FiscalYear(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="fiscal_years",
    )

    name = models.CharField(
        max_length=50,
    )

    start_date = models.DateField()

    end_date = models.DateField()

    is_current = models.BooleanField(
        default=False,
    )

    closed = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_fiscal_year_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class DocumentSequence(models.Model):
    DOCUMENT_TYPES = (
        ("INVOICE", "Invoice"),
        ("RECEIPT", "Receipt"),
        ("QUOTATION", "Quotation"),
        ("PURCHASE_ORDER", "Purchase Order"),
        ("DELIVERY_NOTE", "Delivery Note"),
        ("CREDIT_NOTE", "Credit Note"),
        ("DEBIT_NOTE", "Debit Note"),
        ("PAYMENT", "Payment"),
        ("JOURNAL", "Journal"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="document_sequences",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="document_sequences",
        null=True,
        blank=True,
    )

    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPES,
    )

    prefix = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    next_number = models.PositiveBigIntegerField(
        default=1,
    )

    padding = models.PositiveSmallIntegerField(
        default=6,
    )

    reset_yearly = models.BooleanField(
        default=True,
    )

    last_reset_year = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "branch",
                    "document_type",
                ],
                name="unique_document_sequence",
            ),
        ]

    def next_reference(self):
        from django.db import transaction

        current_year = timezone.localdate().year

        with transaction.atomic():
            sequence = (
                DocumentSequence.objects
                .select_for_update()
                .get(pk=self.pk)
            )

            if (
                sequence.reset_yearly
                and sequence.last_reset_year != current_year
            ):
                sequence.next_number = 1
                sequence.last_reset_year = current_year

            number = str(sequence.next_number).zfill(
                sequence.padding
            )

            parts = [
                sequence.prefix,
                str(current_year),
                number,
            ]

            reference = "-".join(
                part for part in parts if part
            )

            sequence.next_number += 1

            sequence.save(
                update_fields=[
                    "next_number",
                    "last_reset_year",
                    "updated_at",
                ]
            )

            self.next_number = sequence.next_number
            self.last_reset_year = sequence.last_reset_year

        return reference

    def __str__(self):
        return (
            f"{self.company.name} - "
            f"{self.get_document_type_display()}"
        )

