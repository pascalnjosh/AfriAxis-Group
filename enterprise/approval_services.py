from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalWorkflow,
)


def _get_document_amount(document):
    amount = getattr(document, "total_amount", Decimal("0.00"))

    if amount is None:
        return Decimal("0.00")

    return Decimal(str(amount))


def _step_applies(step, amount):
    if (
        step.minimum_amount is not None
        and amount < step.minimum_amount
    ):
        return False

    if (
        step.maximum_amount is not None
        and amount > step.maximum_amount
    ):
        return False

    return True


def _get_applicable_steps(workflow, document):
    amount = _get_document_amount(document)

    return [
        step
        for step in workflow.steps.filter(active=True).order_by("sequence")
        if _step_applies(step, amount)
    ]


def _validate_approver(step, user):
    if user is None or not user.is_authenticated:
        raise ValidationError(
            "An authenticated user is required."
        )

    if user.is_superuser:
        return

    permission = step.required_permission.strip()

    if permission and not user.has_perm(permission):
        raise ValidationError(
            f"You do not have permission to approve step: {step.name}."
        )


@transaction.atomic
def submit_for_approval(
    document,
    document_type,
    user=None,
    notes="",
):
    company = getattr(document, "company", None)

    if company is None:
        raise ValidationError(
            "The document must belong to a company."
        )

    workflow = (
        ApprovalWorkflow.objects
        .select_for_update()
        .filter(
            company=company,
            document_type=document_type,
            active=True,
        )
        .first()
    )

    if workflow is None:
        raise ValidationError(
            f"No active approval workflow exists for {document_type}."
        )

    steps = _get_applicable_steps(
        workflow=workflow,
        document=document,
    )

    if not steps:
        raise ValidationError(
            "The approval workflow has no applicable active steps."
        )

    content_type = ContentType.objects.get_for_model(
        document,
        for_concrete_model=False,
    )

    existing_request = (
        ApprovalRequest.objects
        .filter(
            workflow=workflow,
            content_type=content_type,
            object_id=document.pk,
            status="PENDING",
        )
        .first()
    )

    if existing_request:
        raise ValidationError(
            "This document already has a pending approval request."
        )

    approval_request = ApprovalRequest.objects.create(
        company=company,
        workflow=workflow,
        content_type=content_type,
        object_id=document.pk,
        current_step=steps[0],
        status="PENDING",
        requested_by=user,
        notes=notes,
    )

    ApprovalAction.objects.create(
        approval_request=approval_request,
        step=steps[0],
        action="SUBMITTED",
        action_by=user,
        comments=notes,
    )

    return approval_request


@transaction.atomic
def approve_request(
    approval_request,
    user,
    comments="",
):
    request = (
        ApprovalRequest.objects
        .select_for_update()
        .select_related(
            "workflow",
            "current_step",
        )
        .get(pk=approval_request.pk)
    )

    if request.status != "PENDING":
        raise ValidationError(
            "Only pending requests can be approved."
        )

    if request.current_step is None:
        raise ValidationError(
            "The approval request has no current approval step."
        )

    _validate_approver(
        step=request.current_step,
        user=user,
    )

    ApprovalAction.objects.create(
        approval_request=request,
        step=request.current_step,
        action="APPROVED",
        action_by=user,
        comments=comments,
    )

    document = request.content_object

    if document is None:
        raise ValidationError(
            "The document linked to this approval request no longer exists."
        )

    applicable_steps = _get_applicable_steps(
        workflow=request.workflow,
        document=document,
    )

    next_step = next(
        (
            step
            for step in applicable_steps
            if step.sequence > request.current_step.sequence
        ),
        None,
    )

    if next_step is not None:
        request.current_step = next_step

        request.save(
            update_fields=[
                "current_step",
            ]
        )

        return request

    request.status = "APPROVED"
    request.current_step = None
    request.completed_at = timezone.now()

    request.save(
        update_fields=[
            "status",
            "current_step",
            "completed_at",
        ]
    )

    return request


@transaction.atomic
def reject_request(
    approval_request,
    user,
    comments="",
):
    request = (
        ApprovalRequest.objects
        .select_for_update()
        .select_related(
            "current_step",
        )
        .get(pk=approval_request.pk)
    )

    if request.status != "PENDING":
        raise ValidationError(
            "Only pending requests can be rejected."
        )

    if request.current_step is None:
        raise ValidationError(
            "The approval request has no current approval step."
        )

    _validate_approver(
        step=request.current_step,
        user=user,
    )

    if not comments.strip():
        raise ValidationError(
            "A rejection reason is required."
        )

    ApprovalAction.objects.create(
        approval_request=request,
        step=request.current_step,
        action="REJECTED",
        action_by=user,
        comments=comments,
    )

    request.status = "REJECTED"
    request.current_step = None
    request.completed_at = timezone.now()

    request.save(
        update_fields=[
            "status",
            "current_step",
            "completed_at",
        ]
    )

    return request


@transaction.atomic
def cancel_request(
    approval_request,
    user=None,
    comments="",
):
    request = (
        ApprovalRequest.objects
        .select_for_update()
        .get(pk=approval_request.pk)
    )

    if request.status != "PENDING":
        raise ValidationError(
            "Only pending requests can be cancelled."
        )

    ApprovalAction.objects.create(
        approval_request=request,
        step=request.current_step,
        action="CANCELLED",
        action_by=user,
        comments=comments,
    )

    request.status = "CANCELLED"
    request.current_step = None
    request.completed_at = timezone.now()

    request.save(
        update_fields=[
            "status",
            "current_step",
            "completed_at",
        ]
    )

    return request
