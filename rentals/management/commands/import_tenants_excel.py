import openpyxl

from django.core.management.base import BaseCommand

from rentals.models import Apartment, House, Tenant, Rent


class Command(BaseCommand):

    help = "Import tenants, phone numbers, houses, and rent from Excel"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            type=str
        )

    def handle(self, *args, **kwargs):

        file_path = kwargs["file_path"]

        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active

        created_tenants = 0
        updated_tenants = 0
        created_houses = 0
        created_rents = 0
        skipped = 0

        for row in sheet.iter_rows(min_row=2, values_only=True):

            apartment_name = row[0]
            house_number = row[1]
            tenant_name = row[2]
            phone = row[3]
            rent_amount = row[4]

            if not apartment_name or not house_number or not tenant_name:
                skipped += 1
                continue

            apartment, _ = Apartment.objects.get_or_create(
                name=str(apartment_name).strip(),
                defaults={
                    "total_units": 0,
                    "active": True,
                }
            )

            house, house_created = House.objects.get_or_create(
                apartment=apartment,
                house_number=str(house_number).strip(),
                defaults={
                    "rent_amount": rent_amount or 0,
                    "occupied": True,
                }
            )

            if house_created:
                created_houses += 1

            house.rent_amount = rent_amount or house.rent_amount
            house.occupied = True
            house.save()

            tenant, tenant_created = Tenant.objects.get_or_create(
                name=str(tenant_name).strip(),
                apartment=apartment,
                defaults={
                    "phone": str(phone).strip() if phone else "",
                }
            )

            tenant.phone = str(phone).strip() if phone else tenant.phone
            tenant.save()

            if tenant_created:
                created_tenants += 1
            else:
                updated_tenants += 1

            rent_exists = Rent.objects.filter(
                tenant=tenant,
                house=house,
                paid=False
            ).exists()

            if not rent_exists:
                Rent.objects.create(
                    tenant=tenant,
                    house=house,
                    amount=rent_amount or house.rent_amount,
                    paid=False,
                )

                created_rents += 1

        self.stdout.write("")
        self.stdout.write("EXCEL TENANT IMPORT COMPLETE")
        self.stdout.write("--------------------------------")
        self.stdout.write(f"Tenants Created: {created_tenants}")
        self.stdout.write(f"Tenants Updated: {updated_tenants}")
        self.stdout.write(f"Houses Created: {created_houses}")
        self.stdout.write(f"Rents Created: {created_rents}")
        self.stdout.write(f"Skipped Rows: {skipped}")
