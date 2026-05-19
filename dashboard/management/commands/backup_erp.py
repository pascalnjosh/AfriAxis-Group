import csv
import os
from django.core.management.base import BaseCommand
from django.utils import timezone

from rentals.models import Apartment, House, Tenant, Rent
from billing.models import Invoice


class Command(BaseCommand):
    help = "Export ERP data to CSV backup files"

    def handle(self, *args, **kwargs):

        today = timezone.now().strftime("%Y%m%d_%H%M%S")

        folder = f"backups/afriaxis_backup_{today}"

        os.makedirs(folder, exist_ok=True)

        with open(f"{folder}/apartments.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Name", "Total Units", "Location", "Active"])

            for item in Apartment.objects.all():
                writer.writerow([item.id, item.name, item.total_units, item.location, item.active])

        with open(f"{folder}/houses.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Apartment", "House Number", "Rent Amount", "Occupied"])

            for item in House.objects.select_related("apartment"):
                writer.writerow([item.id, item.apartment.name if item.apartment else "", item.house_number, item.rent_amount, item.occupied])

        with open(f"{folder}/tenants.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Name", "Phone", "Apartment"])

            for item in Tenant.objects.select_related("apartment"):
                writer.writerow([item.id, item.name, item.phone, item.apartment.name if item.apartment else ""])

        with open(f"{folder}/rents.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Tenant", "House", "Amount", "Paid", "Due Date"])

            for item in Rent.objects.select_related("tenant", "house"):
                writer.writerow([item.id, item.tenant.name, item.house.house_number, item.amount, item.paid, item.due_date])

        with open(f"{folder}/invoices.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Invoice Number", "Tenant", "Apartment", "Total", "Paid", "Status", "Created"])

            for item in Invoice.objects.select_related("tenant", "apartment"):
                writer.writerow([item.id, item.invoice_number, item.tenant.name, item.apartment.name if item.apartment else "", item.total_amount, item.amount_paid, item.status, item.created_at])

        self.stdout.write(f"Backup created successfully: {folder}")
