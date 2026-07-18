from django.core.management.base import BaseCommand
from rentals.models import Rent


class Command(BaseCommand):
    help = "Remove placeholder duplicate rent records"

    def handle(self, *args, **options):
        deleted = 0

        for rent in Rent.objects.select_related("tenant", "house"):
            tenant_name = rent.tenant.name if rent.tenant else ""
            house_text = rent.house.house_number if rent.house else ""

            is_placeholder = (
                "House" in tenant_name
                or "BLUEVALLEY" in tenant_name
                or "EASTWARD" in tenant_name
                or "GULF" in tenant_name
                or "MUTHAIGA" in tenant_name
            )

            has_payment = rent.amount_paid > 0 or rent.paid

            if is_placeholder and not has_payment:
                rent.delete()
                deleted += 1

        self.stdout.write(
            self.style.SUCCESS(f"Deleted placeholder rents: {deleted}")
        )