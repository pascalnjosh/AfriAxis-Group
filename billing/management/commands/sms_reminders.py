from django.core.management.base import BaseCommand
from billing.models import Invoice


class Command(BaseCommand):
    help = "Show SMS reminders for unpaid invoices"

    def handle(self, *args, **kwargs):

        invoices = Invoice.objects.filter(
            status="PENDING"
        ).select_related(
            "tenant",
            "apartment"
        )

        count = 0

        for invoice in invoices:

            phone = invoice.tenant.phone or "NO PHONE"

            message = (
                f"Dear {invoice.tenant.name}, "
                f"your AfriAxis invoice {invoice.invoice_number} "
                f"balance is KES {invoice.balance()}. "
                f"Please pay promptly. Thank you."
            )

            self.stdout.write("")
            self.stdout.write(f"Phone: {phone}")
            self.stdout.write(f"Message: {message}")

            count += 1

        self.stdout.write("")
        self.stdout.write(f"SMS reminders prepared: {count}")
