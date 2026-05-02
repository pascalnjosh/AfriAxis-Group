from django.shortcuts import render
from payments.models import Payment
from rentals.models import Rent
from services.models import Subscription
from agri.models import Booking


def md_dashboard(request):
    context = {
        "total_payments": Payment.objects.count(),
        "successful": Payment.objects.filter(verified=True).count(),
        "pending": Payment.objects.filter(verified=False).count(),
        "rent_arrears": Rent.objects.filter(paid=False).count(),
        "wifi_active": Subscription.objects.filter(active=True).count(),
        "agri_bookings": Booking.objects.count(),
    }
    return render(request, "dashboard/md.html", context)
