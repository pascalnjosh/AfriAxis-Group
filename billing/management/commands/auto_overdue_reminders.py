from django.core.management.base import BaseCommand
from billing.models import Invoice


class Command(BaseCommand):

    help = "Prepare automatic overdue invoice reminders"

    def handle(self, *args, **kwargs):

        invoices = Invoice.objects.exclude(
            status="PAID"
        ).select_related(
            "tenant",
            "apartment"
        ).order_by(
            "created_at"
        )

        count = 0

        for invoice in invoices:

            balance = invoice.balance()

            if balance <= 0:
                continue

            phone = invoice.tenant.phone or "NO PHONE"

            message = (
                f"Dear {invoice.tenant.name}, "
                f"your AfriAxis invoice {invoice.invoice_number} "
                f"has an outstanding balance of KES {balance}. "
                f"Kindly clear your balance. Thank you."
            )

            self.stdout.write("")
            self.stdout.write(f"Invoice: {invoice.invoice_number}")
            self.stdout.write(f"Tenant: {invoice.tenant.name}")
            self.stdout.write(f"Phone: {phone}")
            self.stdout.write(f"Message: {message}")

            count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Overdue reminders prepared: {count}"
            )
        )
