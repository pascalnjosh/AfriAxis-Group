from datetime import date

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Compatibility alias for generate_monthly_invoices. "
        "Uses the protected invoice generator."
    )

    def add_arguments(self, parser):
        today = date.today()

        parser.add_argument(
            "--year",
            type=int,
            default=today.year,
        )
        parser.add_argument(
            "--month",
            type=int,
            default=today.month,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "generate_invoices is deprecated. "
                "Running generate_monthly_invoices."
            )
        )

        call_command(
            "generate_monthly_invoices",
            year=options["year"],
            month=options["month"],
            dry_run=options["dry_run"],
        )
