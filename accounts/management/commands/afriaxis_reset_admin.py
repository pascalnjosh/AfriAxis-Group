import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "One-time AfriAxis production admin password reset."

    def handle(self, *args, **options):
        username = os.environ.get("AFRIAXIS_RESET_USERNAME", "").strip()
        password = os.environ.get("AFRIAXIS_RESET_PASSWORD", "")

        if not username or not password:
            self.stdout.write(
                "Admin reset skipped: environment variables not configured."
            )
            return

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(
                f"User {username!r} does not exist in production."
            )

        user.set_password(password)
        user.is_active = True
        user.save(update_fields=["password", "is_active"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Password reset completed for {username}."
            )
        )
