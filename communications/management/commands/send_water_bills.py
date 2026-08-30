from django.core.management.base import BaseCommand

from communications.billing import send_water_bill_sms
from services.models import WaterBill


class Command(BaseCommand):

    help = "Send/record SMS for unpaid water bills."

    def handle(self, *args, **options):

        qs = (
            WaterBill.objects
            .select_related(
                "tenant",
                "tenant__apartment",
            )
            .filter(
                paid=False,
                tenant__active=True,
            )
        )

        success = 0
        failed = 0

        for bill in qs:

            if not bill.tenant.phone:
                failed += 1
                continue

            try:
                sms = send_water_bill_sms(bill)

                success += 1

                self.stdout.write(
                    f"{sms.status} | "
                    f"{sms.phone_number} | "
                    f"WATER-{bill.pk}"
                )

            except Exception as exc:
                failed += 1
                self.stderr.write(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"COMPLETE success={success} failed={failed}"
            )
        )
