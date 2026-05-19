from django.urls import path
from .views import role_home, erp_home

urlpatterns = [
    path("", erp_home, name="erp_home"),
    path("home/", role_home, name="role_home"),
]
