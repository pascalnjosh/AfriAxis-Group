from django.core.management.base import BaseCommand

from accounting.models import Account
from manufacturing.models import (
    BillOfMaterial,
    ProductionOrder,
)


class Command(BaseCommand):

    help = (
        "AfriAxis manufacturing closeout control report. "
        "Does not modify inventory GL policy."
    )

    def handle(self, *args, **options):

        self.stdout.write("")
        self.stdout.write(
            "=== MANUFACTURING CONTROL ==="
        )

        self.stdout.write(
            f"BOMs                     "
            f"{BillOfMaterial.objects.count()}"
        )

        self.stdout.write(
            f"Production Orders        "
            f"{ProductionOrder.objects.count()}"
        )

        self.stdout.write("")
        self.stdout.write(
            "INVENTORY GL ACCOUNTS"
        )

        for code in [
            "1200",
            "1210",
            "1220",
        ]:

            qs = Account.objects.filter(
                code=code
            )

            if qs.exists():

                for account in qs:

                    self.stdout.write(
                        f"{account.code} | "
                        f"{account.name}"
                    )

            else:

                self.stdout.write(
                    f"{code} | NOT FOUND"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "No GL remapping performed. "
                "1200/1210 remains an explicit "
                "accounting-policy decision."
            )
        )
