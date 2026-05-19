from django.core.management.base import BaseCommand

from billing.models import Invoice


class Command(BaseCommand):

    help = "Simulate enterprise SMS reminders"

    def handle(self, *args, **kwargs):

        invoices = (
            Invoice.objects
            .exclude(status="PAID")
            .select_related("tenant")
        )

        sent = 0

        for invoice in invoices:

            phone = invoice.tenant.phone

            if not phone:
                continue

            balance = invoice.balance()

            message = (
                f"AFRIAXIS ERP: Dear {invoice.tenant.name}, "
                f"invoice {invoice.invoice_number} balance is "
                f"KES {balance}. Please pay promptly."
            )

            self.stdout.write("")
            self.stdout.write(f"TO: {phone}")
            self.stdout.write(f"SMS: {message}")

            sent += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"SMS simulation complete. Messages prepared: {sent}"
            )
        )
