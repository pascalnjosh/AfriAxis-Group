import re

from django.core.management.base import BaseCommand

from banking.models import BankAccount
from rentals.models import Tenant


def normalize_phone(value):

    digits = re.sub(
        r"\D",
        "",
        str(value or ""),
    )

    if digits.startswith("254") and len(digits) == 12:
        return "+" + digits

    if digits.startswith("0") and len(digits) == 10:
        return "+254" + digits[1:]

    if len(digits) == 9:
        return "+254" + digits

    return str(value or "").strip()


class Command(BaseCommand):

    help = (
        "Verify readiness for bank statement / bank SMS "
        "tenant matching."
    )

    def handle(self, *args, **options):

        self.stdout.write("")
        self.stdout.write(
            "=== AFRIAXIS PAYMENT MATCHING READINESS ==="
        )

        accounts = BankAccount.objects.filter(
            active=True
        ).order_by(
            "purpose",
            "bank_name",
        )

        self.stdout.write("")
        self.stdout.write("BANK ACCOUNTS")

        for account in accounts:

            self.stdout.write(
                f"{account.purpose:8} | "
                f"{account.bank_name:15} | "
                f"{account.account_number}"
            )

        self.stdout.write("")
        self.stdout.write("TENANT PHONES")

        tenants = Tenant.objects.filter(
            active=True
        )

        missing = 0
        valid = 0

        for tenant in tenants:

            normalized = normalize_phone(
                tenant.phone
            )

            if normalized.startswith("+254"):
                valid += 1
            else:
                missing += 1

        self.stdout.write(
            f"Active tenants             {tenants.count()}"
        )

        self.stdout.write(
            f"Usable Kenyan phones       {valid}"
        )

        self.stdout.write(
            f"Missing/invalid phones     {missing}"
        )

        purposes = set(
            accounts.values_list(
                "purpose",
                flat=True,
            )
        )

        for required in [
            "RENT",
            "WATER",
            "WIFI",
        ]:

            status = (
                "PASS"
                if required in purposes
                else "MISSING"
            )

            self.stdout.write(
                f"{required:8} account purpose     {status}"
            )
