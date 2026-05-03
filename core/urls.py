from django.contrib import admin
from django.urls import path, include
from payments.views import dashboard

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard, name="dashboard"),
    path("payments/", include("payments.urls")),
    path("services/", include("services.urls")),
]
