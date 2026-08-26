from django.db import models
from django.contrib.auth.models import User

from enterprise.models import Company
from rentals.models import Apartment, Tenant, House


class BankAccount(models.Model):

    PURPOSE_CHOICES = [
        ("RENT", "Rent"),
        ("WATER", "Water"),
        ("WIFI", "Wi-Fi"),
        ("OTHER", "Other"),
    ]
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
        null=True,
        blank=True,
    )

    apartment = models.ForeignKey(
        Apartment,
        on_delete=models.SET_NULL,
        related_name="bank_accounts",
        null=True,
        blank=True,
    )

    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default="OTHER",
    )

    bank_name = models.CharField(
        max_length=100,
    )

    account_name = models.CharField(
        max_length=150,
    )

    account_number = models.CharField(
        max_length=50,
    )

    currency = models.CharField(
        max_length=10,
        default="KES",
    )

    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    active = models.BooleanField(
        default=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "account_number"],
                name="unique_bank_account_number_per_company",
            ),
        ]

    def __str__(self):
        if self.apartment:
            return (
                f"{self.company.name} - "
                f"{self.apartment.name} - "
                f"{self.bank_name} - "
                f"{self.account_number}"
            )

        return (
            f"{self.company.name} - "
            f"{self.bank_name} - "
            f"{self.account_number}"
        )


class BankStatementTemplate(models.Model):
    bank_name = models.CharField(max_length=100)
    date_column = models.CharField(max_length=100, default="Date")
    description_column = models.CharField(max_length=100, default="Description")
    reference_column = models.CharField(max_length=100, default="Reference")
    money_in_column = models.CharField(max_length=100, default="Money In")
    money_out_column = models.CharField(max_length=100, default="Money Out")
    balance_column = models.CharField(max_length=100, default="Balance")
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.bank_name} Statement Template"


class BankStatementUpload(models.Model):
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="statement_uploads",
    )

    template = models.ForeignKey(
        BankStatementTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    file = models.FileField(
        upload_to="bank_statements/",
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    processed = models.BooleanField(
        default=False,
    )

    def __str__(self):
        return f"{self.bank_account} - {self.uploaded_at}"


class BankTransaction(models.Model):

    TRANSACTION_TYPE_CHOICES = [
        ("money_in", "Money In"),
        ("money_out", "Money Out"),
        ("unknown", "Unknown"),
    ]

    MATCH_STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    SUGGESTED_CATEGORY_CHOICES = [
        ("rent", "Rent"),
        ("water", "Water"),
        ("wifi", "Wi-Fi"),
        ("rent_deposit", "Rent Deposit"),
        ("water_deposit", "Water Deposit"),
        ("expense", "Expense"),
        ("other_income", "Other Income"),
        ("customer_receipt", "Customer Receipt"),
        ("supplier_payment", "Supplier Payment"),
        ("unknown", "Unknown"),
    ]

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    statement_upload = models.ForeignKey(
        BankStatementUpload,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    matched_tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_transactions",
    )

    matched_house = models.ForeignKey(
        House,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_transactions",
    )

    matched_sales_receipt = models.ForeignKey(
        "sales.SalesReceipt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_transactions",
    )

    matched_supplier_payment = models.ForeignKey(
        "purchasing.SupplierPayment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_transactions",
    )

    auto_matched = models.BooleanField(
        default=False,
    )

    match_notes = models.TextField(
        blank=True,
    )

    transaction_date = models.DateField()

    description = models.TextField()

    reference = models.CharField(
        max_length=150,
        blank=True,
    )

    money_in = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    money_out = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        default="unknown",
    )

    suggested_category = models.CharField(
        max_length=30,
        choices=SUGGESTED_CATEGORY_CHOICES,
        default="unknown",
    )

    confidence = models.IntegerField(
        default=0,
    )

    match_status = models.CharField(
        max_length=20,
        choices=MATCH_STATUS_CHOICES,
        default="pending",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.transaction_date} - {self.description[:40]}"



