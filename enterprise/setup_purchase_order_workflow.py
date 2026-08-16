from django.db import transaction

from enterprise.models import (
    ApprovalStep,
    ApprovalWorkflow,
    Company,
)


@transaction.atomic
def setup_purchase_order_workflows():
    companies = Company.objects.all()

    if not companies.exists():
        print("NO COMPANIES FOUND")
        return

    for company in companies:
        workflow, created = ApprovalWorkflow.objects.get_or_create(
            company=company,
            document_type="PURCHASE_ORDER",
            defaults={
                "name": "Purchase Order Approval",
                "active": True,
            },
        )

        if not created:
            workflow.name = "Purchase Order Approval"
            workflow.active = True
            workflow.save(
                update_fields=[
                    "name",
                    "active",
                ]
            )

        ApprovalStep.objects.update_or_create(
            workflow=workflow,
            sequence=1,
            defaults={
                "name": "Manager Approval",
                "required_permission": "",
                "minimum_amount": None,
                "maximum_amount": None,
                "active": True,
            },
        )

        ApprovalStep.objects.update_or_create(
            workflow=workflow,
            sequence=2,
            defaults={
                "name": "Finance Approval",
                "required_permission": "",
                "minimum_amount": None,
                "maximum_amount": None,
                "active": True,
            },
        )

        print(
            f"READY: {company.name} "
            f"- Manager Approval -> Finance Approval"
        )


setup_purchase_order_workflows()
