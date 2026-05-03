import openpyxl
from django.core.management.base import BaseCommand
from payments.models import Rent
from datetime import date


class Command(BaseCommand):
    help = "Import house rents from Excel files"

    def handle(self, *args, **kwargs):
        files = [
            ("MUTHAIGA", "MUTHAIGA UNITS.xlsx"),
            ("GULF", "GULF UNITS.xlsx"),
            ("EASTWARD", "EASTWARD UNITS.xlsx"),
            ("BLUEVALLEY", "BLUEVALLEY UNITS.xlsx"),
        ]

        today = date.today()
        due_date = date(today.year, today.month, 1)
        total_created = 0
        total_skipped = 0

        for property_name, file in files:
            wb = openpyxl.load_workbook(file, data_only=True)
            ws = wb.active

            for row in ws.iter_rows(min_row=2, values_only=True):
                house_no = row[0]
                house_type = row[1]
                amount = row[2]

                if not house_no or not amount:
                    total_skipped += 1
                    continue

                tenant_name = f"{property_name} House {house_no} - {house_type}"

                rent, created = Rent.objects.get_or_create(
                    tenant_name=tenant_name,
                    due_date=due_date,
                    defaults={
                        "amount": amount,
                        "status": "PENDING",
                    }
                )

                if created:
                    total_created += 1
                    self.stdout.write(f"Added: {tenant_name} - {amount}")
                else:
                    total_skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Created: {total_created}, Skipped: {total_skipped}"))
