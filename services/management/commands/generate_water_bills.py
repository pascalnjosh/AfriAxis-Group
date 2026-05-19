from decimal import Decimal

from django.core.management.base import BaseCommand

from rentals.models import Tenant
from services.models import WaterMeter, WaterReading, WaterBill


class Command(BaseCommand):
    help = "Generate water bills from latest meter readings"

    def handle(self, *args, **kwargs):

        created = 0
        skipped = 0

        meters = WaterMeter.objects.select_related(
            "house",
            "house__apartment"
        )

        for meter in meters:

            readings = WaterReading.objects.filter(
                meter=meter
            ).order_by("-date")

            if readings.count() < 2:
                skipped += 1
                continue

            latest = readings[0]
            previous = readings[1]

            units_used = latest.reading - previous.reading

            if units_used <= 0:
                skipped += 1
                continue

            tenant = Tenant.objects.filter(
                apartment=meter.house.apartment,
                name__icontains=meter.house.house_number
            ).first()

            if not tenant:
                skipped += 1
                continue

            exists = WaterBill.objects.filter(
                tenant=tenant,
                reading=latest
            ).exists()

            if exists:
                skipped += 1
                continue

            cost_per_unit = Decimal("50")

            total_amount = units_used * cost_per_unit

            WaterBill.objects.create(
                tenant=tenant,
                reading=latest,
                units_used=units_used,
                cost_per_unit=cost_per_unit,
                total_amount=total_amount,
                paid=False,
            )

            created += 1

        self.stdout.write(
            f"Water billing complete. Created: {created}, Skipped: {skipped}"
        )
