from django.utils import timezone
from services.models import WifiCustomer


class WifiExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        WifiCustomer.objects.filter(
            expiry_date__lt=timezone.now(),
            active=True
        ).update(active=False)

        response = self.get_response(request)
        return response
