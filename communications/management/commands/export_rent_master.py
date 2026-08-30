import csv

from django.core.management.base import BaseCommand

from rentals.models import House


class Command(BaseCommand):

    help = (
        "Export the AfriAxis clean operational rent master "
        "without historical payment data."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--output",
            default="AFRIAXIS_V7_RENT_MASTER.csv",
        )

    def handle(self, *args, **options):

        output = options["output"]

        houses = (
            House.objects
            .select_related(
                "apartment",
                "tenant",
            )
            .order_by(
                "apartment__name",
                "house_number",
            )
        )

        with open(
            output,
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as handle:

            writer = csv.writer(handle)

            writer.writerow(
                [
                    "PROPERTY",
                    "HOUSE",
                    "TENANT",
                    "PHONE",
                    "EXPECTED_MONTHLY_RENT",
                    "OCCUPIED",
                ]
            )

            for house in houses:

                tenant = getattr(
                    house,
                    "tenant",
                    None,
                )

                writer.writerow(
                    [
                        house.apartment.name,
                        house.house_number,
                        (
                            tenant.name
                            if tenant
                            else ""
                        ),
                        (
                            tenant.phone
                            if tenant
                            else ""
                        ),
                        house.rent_amount,
                        house.occupied,
                    ]
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {output}"
            )
        )
