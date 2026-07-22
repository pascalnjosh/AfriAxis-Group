from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from enterprise.models import Company, Currency


class AccountType(models.Model):
    CATEGORY_CHOICES = (
        ("ASSET", "Asset"),
        ("LIABILITY", "Liability"),
        ("EQUITY", "Equity"),
        ("REVENUE", "Revenue"),
        ("COST_OF_SALES", "Cost of Sales"),
        ("EXPENSE", "Expense"),
    )

    name = models.CharField(max_length=100)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
    )
    normal_balance = models.CharField(
        max_length=10,
        choices=(
            ("DEBIT", "Debit"),
            ("CREDIT", "Credit"),
        ),
    )

    def __str__(self):
        return self.name


class Account(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    account_type = models.ForeignKey(
        AccountType,
        on_delete=models.PROTECT,
        related_name="accounts",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)
    allow_posting = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_account_code_per_company",
            ),
        ]
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("POSTED", "Posted"),
        ("REVERSED", "Reversed"),
    )

    journal_number = models.CharField(
        max_length=60,
        unique=True,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="journal_entries",
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    entry_date = models.DateField(
        default=timezone.localdate,
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    description = models.TextField(
        blank=True,
        default="",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_journal_entries",
        null=True,
        blank=True,
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="posted_journal_entries",
        null=True,
        blank=True,
    )
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    @property
    def total_debit(self):
        return sum(
            (
                line.debit
                for line in self.lines.all()
            ),
            Decimal("0.00"),
        )

    @property
    def total_credit(self):
        return sum(
            (
                line.credit
                for line in self.lines.all()
            ),
            Decimal("0.00"),
        )

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit

    def clean(self):
        if self.status == "POSTED" and not self.is_balanced:
            raise ValidationError(
                "A journal entry must balance before posting."
            )

    def __str__(self):
        return self.journal_number


class JournalEntryLine(models.Model):
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    debit = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    credit = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError(
                "A journal line cannot contain both debit and credit."
            )

        if self.debit == 0 and self.credit == 0:
            raise ValidationError(
                "A journal line must contain a debit or credit amount."
            )

        if not self.account.allow_posting:
            raise ValidationError(
                "This account does not allow direct posting."
            )

    def __str__(self):
        return (
            f"{self.journal_entry.journal_number} - "
            f"{self.account.code}"
        )
