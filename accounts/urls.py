from django.urls import path

from .views import (
    erp_home,
    profile,
    role_home,
)


urlpatterns = [
    path("", erp_home, name="erp_home"),
    path("home/", role_home, name="role_home"),
    path("profile/", profile, name="profile"),
]
