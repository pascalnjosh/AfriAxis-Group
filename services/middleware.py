from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone


class WifiExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from services.models import WifiCustomer

            WifiCustomer.objects.filter(
                expiry_date__lt=timezone.now(),
                active=True
            ).update(active=False)

        except (OperationalError, ProgrammingError):
            pass

        return self.get_response(request)
