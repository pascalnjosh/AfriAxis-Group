from django.urls import path

from .ceo_views import ceo_dashboard


urlpatterns = [
    path(
        "ceo/",
        ceo_dashboard,
        name="ceo_dashboard",
    ),
]
