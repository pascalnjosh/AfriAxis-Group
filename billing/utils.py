from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from billing.models import Invoice
from rentals.models import Tenant, Rent
from services.models import WifiCustomer, WaterBill


class Command(BaseCommand):
    help = "Generate monthly invoices for all tenants"

    def handle(self, *args, **options):
        today = timezone.now().date()
        month_code = today.strftime("%Y%m")

        created = 0
        skipped = 0

        for tenant in Tenant.objects.all():
            invoice_number = f"AFX-{month_code}-{tenant.id}"

            if Invoice.objects.filter(invoice_number=invoice_number).exists():
                skipped += 1
                continue

            rent = Rent.objects.filter(tenant=tenant, paid=False).order_by("-date").first()
            rent_amount = rent.amount if rent else Decimal("0.00")

            wifi = WifiCustomer.objects.filter(phone=tenant.phone).first()
            wifi_amount = wifi.package.price if wifi and wifi.package else Decimal("0.00")

            water_bill = WaterBill.objects.filter(tenant=tenant, paid=False).order_by("-created_at").first()
            water_amount = water_bill.total_amount if water_bill else Decimal("0.00")

            total = rent_amount + wifi_amount + water_amount

            Invoice.objects.create(
                tenant=tenant,
                apartment=tenant.apartment,
                invoice_number=invoice_number,
                rent_amount=rent_amount,
                wifi_amount=wifi_amount,
                water_amount=water_amount,
                total_amount=total,
                due_date=today.replace(day=10) if hasattr(Invoice, "due_date") else None,
            )

            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created: {created}, Skipped: {skipped}"))
from billing.models import Invoice, InvoicePayment


def apply_mpesa_to_invoice(phone_number, amount, receipt):
    invoice = (
        Invoice.objects
        .filter(tenant__phone=phone_number)
        .exclude(status="PAID")
        .order_by("created_at")
        .first()
    )

    if not invoice:
        return None

    payment = InvoicePayment.objects.create(
        invoice=invoice,
        amount=amount,
        phone_number=phone_number,
        mpesa_receipt=receipt,
    )

    return payment