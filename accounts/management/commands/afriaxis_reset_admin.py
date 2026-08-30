import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "One-time guarded AfriAxis production administrator recovery"

    def handle(self, *args, **options):

        username = os.environ.get(
            "AFRIAXIS_RESET_USERNAME",
            ""
        ).strip()

        password = os.environ.get(
            "AFRIAXIS_RESET_PASSWORD",
            ""
        )

        if not username or not password:
            self.stdout.write(
                "AfriAxis admin recovery: not configured - skipped."
            )
            return

        User = get_user_model()

        try:
            user = User.objects.get(
                username=username
            )
        except User.DoesNotExist:
            self.stderr.write(
                "AfriAxis admin recovery: user does not exist."
            )
            return

        user.set_password(password)
        user.is_active = True

        user.save(
            update_fields=[
                "password",
                "is_active",
            ]
        )

        self.stdout.write(
            self.style.SUCCESS(
                "AfriAxis production administrator password reset successfully."
            )
        )
