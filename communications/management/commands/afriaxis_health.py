from decimal import Decimal

from django.apps import apps
from django.core.management.base import BaseCommand

from accounting.models import JournalEntry
from banking.models import (
    BankAccount,
    BankStatementUpload,
    BankTransaction,
)
from communications.models import SmsMessage


class Command(BaseCommand):

    help = "AfriAxis V7 final non-destructive health report."

    def handle(self, *args, **options):

        self.stdout.write("")
        self.stdout.write("=" * 65)
        self.stdout.write(" AFRIAXIS V7 - SYSTEM HEALTH")
        self.stdout.write("=" * 65)

        checks = [
            ("rentals", "Apartment"),
            ("rentals", "House"),
            ("rentals", "Tenant"),
            ("rentals", "Rent"),
            ("services", "WaterMeter"),
            ("services", "WaterReading"),
            ("services", "WaterBill"),
            ("services", "WifiPackage"),
            ("services", "WifiCustomer"),
            ("services", "WifiPayment"),
            ("sales", "SalesOrder"),
            ("sales", "SalesInvoice"),
            ("manufacturing", "BillOfMaterial"),
            ("manufacturing", "ProductionOrder"),
            ("inventory", "StockBalance"),
        ]

        for app_label, model_name in checks:

            try:

                model = apps.get_model(
                    app_label,
                    model_name,
                )

                self.stdout.write(
                    f"{model_name:24} "
                    f"{model.objects.count()}"
                )

            except Exception as exc:

                self.stdout.write(
                    f"{model_name:24} ERROR {exc}"
                )

        self.stdout.write("")
        self.stdout.write("BANKING")

        self.stdout.write(
            f"Bank accounts             "
            f"{BankAccount.objects.count()}"
        )

        self.stdout.write(
            f"Statement uploads         "
            f"{BankStatementUpload.objects.count()}"
        )

        self.stdout.write(
            f"Bank transactions         "
            f"{BankTransaction.objects.count()}"
        )

        self.stdout.write("")
        self.stdout.write("COMMUNICATIONS")

        self.stdout.write(
            f"SMS messages              "
            f"{SmsMessage.objects.count()}"
        )

        for status in [
            "TEST",
            "QUEUED",
            "SENT",
            "FAILED",
            "DELIVERED",
        ]:

            self.stdout.write(
                f"SMS {status:18} "
                f"{SmsMessage.objects.filter(status=status).count()}"
            )

        self.stdout.write("")
        self.stdout.write("ACCOUNTING")

        journals = JournalEntry.objects.all()

        self.stdout.write(
            f"Journal entries           {journals.count()}"
        )

        unbalanced = []

        for journal in journals:

            lines = journal.lines.all()

            debit = sum(
                (
                    Decimal(str(line.debit or 0))
                    for line in lines
                ),
                Decimal("0"),
            )

            credit = sum(
                (
                    Decimal(str(line.credit or 0))
                    for line in lines
                ),
                Decimal("0"),
            )

            if debit != credit:

                unbalanced.append(
                    (
                        journal.pk,
                        debit,
                        credit,
                    )
                )

        self.stdout.write(
            f"Unbalanced journals       {len(unbalanced)}"
        )

        if unbalanced:

            raise RuntimeError(
                f"ACCOUNTING CONTROL FAILED: {unbalanced[:10]}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "ACCOUNTING CONTROL: PASS"
            )
        )
