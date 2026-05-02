from collections import defaultdict
from django.core.management.base import BaseCommand
from payments.models import Rent
from payments.sms import send_sms


class Command(BaseCommand):
    help = "Send one rent reminder per tenant with total arrears"

    def handle(self, *args, **kwargs):
        rents = Rent.objects.filter(balance__gt=0).select_related('tenant')

        if not rents.exists():
            self.stdout.write(self.style.WARNING("No tenants with arrears found."))
            return

        tenant_totals = defaultdict(lambda: {
            "full_name": "",
            "phone": "",
            "total_balance": 0,
        })

        for rent in rents:
            tenant = rent.tenant
            tenant_totals[tenant.id]["full_name"] = tenant.full_name
            tenant_totals[tenant.id]["phone"] = tenant.phone
            tenant_totals[tenant.id]["total_balance"] += float(rent.balance)

        for tenant_id, data in tenant_totals.items():
            full_name = data["full_name"]
            phone = data["phone"]
            total_balance = data["total_balance"]

            if phone:
                message = f"Hello {full_name}, your total rent arrears are KES {total_balance:.2f}. Please pay."
                send_sms(phone, message)
                self.stdout.write(self.style.SUCCESS(f"Sent ONE to {full_name}"))
            else:
                self.stdout.write(self.style.WARNING(f"No phone for {full_name}"))
