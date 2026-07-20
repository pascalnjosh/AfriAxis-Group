from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.water_dashboard,
        name="water_dashboard",
    ),
]
