from django.urls import path
from . import views

urlpatterns = [
    path(
        "tenant/<int:tenant_id>/",
        views.tenant_statement,
        name="tenant_statement",
    ),
]