from django.urls import path
from .views import move_out_tenant, assign_tenant

urlpatterns = [
    path(
        "move-out/<int:tenant_id>/",
        move_out_tenant,
        name="move_out_tenant"
    ),

    path(
        "assign/<int:house_id>/",
        assign_tenant,
        name="assign_tenant"
    ),
]
