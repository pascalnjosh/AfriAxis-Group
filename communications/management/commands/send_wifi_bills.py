from django.core.management.base import BaseCommand

from communications.billing import send_wifi_bill_sms
from services.models import WifiCustomer


class Command(BaseCommand):

    help = "Send/record Wi-Fi billing SMS."

    def handle(self, *args, **options):

        qs = (
            WifiCustomer.objects
            .select_related("package")
            .filter(
                package__isnull=False,
            )
        )

        success = 0
        failed = 0

        for customer in qs:

            if not customer.phone:
                failed += 1
                continue

            try:
                sms = send_wifi_bill_sms(customer)

                success += 1

                self.stdout.write(
                    f"{sms.status} | "
                    f"{sms.phone_number} | "
                    f"WIFI-{customer.pk}"
                )

            except Exception as exc:
                failed += 1
                self.stderr.write(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"COMPLETE success={success} failed={failed}"
            )
        )
