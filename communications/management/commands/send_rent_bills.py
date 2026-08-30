from django.core.management.base import BaseCommand, CommandError

from communications.billing import send_rent_bill_sms
from rentals.models import Rent


class Command(BaseCommand):

    help = (
        "Send/record rent billing SMS. "
        "Bulk mode requires --confirm-bulk."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--limit",
            type=int,
            default=0,
        )

        parser.add_argument(
            "--confirm-bulk",
            action="store_true",
        )

    def handle(self, *args, **options):

        limit = options["limit"]
        confirm_bulk = options["confirm_bulk"]

        if not limit and not confirm_bulk:

            raise CommandError(
                "Bulk rent SMS is blocked. "
                "Use --limit N for testing. "
                "Use --confirm-bulk only after reviewing "
                "the current billing cycle."
            )

        qs = (
            Rent.objects
            .select_related(
                "tenant",
                "house",
                "tenant__apartment",
            )
            .filter(
                paid=False,
                tenant__active=True,
            )
            .order_by(
                "tenant__apartment__name",
                "house__house_number",
                "id",
            )
        )

        if limit:
            qs = qs[:limit]

        success = 0
        failed = 0

        for rent in qs:

            tenant = rent.tenant

            if not tenant.phone:

                failed += 1

                self.stderr.write(
                    f"SKIP RENT-{rent.pk}: missing phone"
                )

                continue

            try:

                sms = send_rent_bill_sms(rent)

                success += 1

                self.stdout.write(
                    f"{sms.status} | "
                    f"{sms.phone_number} | "
                    f"RENT-{rent.pk}"
                )

            except Exception as exc:

                failed += 1

                self.stderr.write(
                    f"FAILED RENT-{rent.pk}: {exc}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"COMPLETE success={success} failed={failed}"
            )
        )
