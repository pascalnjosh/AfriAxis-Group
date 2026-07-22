from django.utils import timezone

from etims.models import EtimsConfiguration


class EtimsService:

    def __init__(self):
        self.config = (
            EtimsConfiguration.objects
            .filter(is_active=True)
            .first()
        )

        if not self.config:
            raise RuntimeError(
                "No active eTIMS configuration found."
            )

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def health_check(self):
        return {
            "environment": self.config.environment,
            "company": self.config.company_name,
            "configured": True,
        }

    def submit_invoice(self, invoice):
        payload = {
            "invoice_number": invoice.invoice_number,
            "customer": invoice.customer_name,
            "total": str(invoice.total_amount),
        }

        invoice.etims_status = "SUBMITTED"
        invoice.etims_receipt_number = (
            f"TEST-{invoice.invoice_number}"
        )
        invoice.etims_control_unit_number = "SANDBOX"
        invoice.etims_submitted_at = timezone.now()

        invoice.save(
            update_fields=[
                "etims_status",
                "etims_receipt_number",
                "etims_control_unit_number",
                "etims_submitted_at",
                "updated_at",
            ]
        )

        return {
            "success": True,
            "message": "Sandbox submission successful.",
            "payload": payload,
        }
