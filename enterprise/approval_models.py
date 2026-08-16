from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .models import Company


class ApprovalWorkflow(models.Model):
    DOCUMENT_TYPES = (
        ("PURCHASE_ORDER", "Purchase Order"),
        ("SUPPLIER_INVOICE", "Supplier Invoice"),
        ("SUPPLIER_PAYMENT", "Supplier Payment"),
        ("SALES_ORDER", "Sales Order"),
        ("DELIVERY_NOTE", "Delivery Note"),
        ("CUSTOMER_INVOICE", "Customer Invoice"),
        ("INVENTORY_ADJUSTMENT", "Inventory Adjustment"),
        ("JOURNAL_ENTRY", "Journal Entry"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="approval_workflows",
    )

    name = models.CharField(
        max_length=150,
    )

    document_type = models.CharField(
        max_length=40,
        choices=DOCUMENT_TYPES,
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
                fields=["company", "document_type"],
                name="unique_approval_workflow_per_document_type",
            ),
        ]
        ordering = ["company", "document_type"]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class ApprovalStep(models.Model):
    workflow = models.ForeignKey(
        ApprovalWorkflow,
        on_delete=models.CASCADE,
        related_name="steps",
    )

    name = models.CharField(
        max_length=150,
    )

    sequence = models.PositiveIntegerField()

    required_permission = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text=(
            "Optional Django permission codename required to approve "
            "this step."
        ),
    )

    minimum_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )

    maximum_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )

    active = models.BooleanField(
        default=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workflow", "sequence"],
                name="unique_approval_step_sequence",
            ),
        ]
        ordering = ["sequence"]

    def clean(self):
        if (
            self.minimum_amount is not None
            and self.maximum_amount is not None
            and self.minimum_amount > self.maximum_amount
        ):
            raise ValidationError(
                "Minimum amount cannot be greater than maximum amount."
            )

    def __str__(self):
        return (
            f"{self.workflow.name} - "
            f"{self.sequence}. {self.name}"
        )


class ApprovalRequest(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="approval_requests",
    )

    workflow = models.ForeignKey(
        ApprovalWorkflow,
        on_delete=models.PROTECT,
        related_name="approval_requests",
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )

    object_id = models.PositiveBigIntegerField()

    content_object = GenericForeignKey(
        "content_type",
        "object_id",
    )

    current_step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.SET_NULL,
        related_name="current_requests",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="submitted_approval_requests",
        null=True,
        blank=True,
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "workflow",
                    "content_type",
                    "object_id",
                ],
                condition=models.Q(status="PENDING"),
                name="unique_pending_approval_request",
            ),
        ]
        ordering = ["-requested_at"]

    def clean(self):
        if self.workflow.company_id != self.company_id:
            raise ValidationError(
                "The workflow belongs to another company."
            )

        if (
            self.current_step
            and self.current_step.workflow_id != self.workflow_id
        ):
            raise ValidationError(
                "The current approval step belongs to another workflow."
            )

    def mark_completed(self, status):
        if status not in {"APPROVED", "REJECTED", "CANCELLED"}:
            raise ValidationError(
                "Invalid completed approval status."
            )

        self.status = status
        self.completed_at = timezone.now()

        self.save(
            update_fields=[
                "status",
                "completed_at",
            ]
        )

    def __str__(self):
        return (
            f"{self.workflow.name} - "
            f"{self.content_type} #{self.object_id}"
        )


class ApprovalAction(models.Model):
    ACTION_CHOICES = (
        ("SUBMITTED", "Submitted"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    )

    approval_request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.CASCADE,
        related_name="actions",
    )

    step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.SET_NULL,
        related_name="actions",
        null=True,
        blank=True,
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
    )

    action_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approval_actions",
        null=True,
        blank=True,
    )

    comments = models.TextField(
        blank=True,
        default="",
    )

    action_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["action_at"]

    def __str__(self):
        return (
            f"{self.approval_request_id} - "
            f"{self.action}"
        )
