from django.urls import path

from .views import purchasing_dashboard

urlpatterns = [
    path(
        "",
        purchasing_dashboard,
        name="purchasing_dashboard",
    ),
]
