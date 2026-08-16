from django.urls import path

from .views import (
    add_bom_component,
    delete_bom_component,
    activate_bom,
    bom_detail,
    deactivate_bom,
    bom_list,
    complete_production_order_view,
    manufacturing_dashboard,
    production_order_detail,
    production_order_list,
    release_production_order,
    start_production_order,
)

app_name = "manufacturing"

urlpatterns = [
    path(
        "boms/<int:pk>/components/add/",
        add_bom_component,
        name="add_bom_component",
    ),
    path(
        "boms/<int:pk>/components/<int:line_id>/delete/",
        delete_bom_component,
        name="delete_bom_component",
    ),
    path(
        "boms/<int:pk>/",
        bom_detail,
        name="bom_detail",
    ),
    path(
        "boms/<int:pk>/activate/",
        activate_bom,
        name="activate_bom",
    ),
    path(
        "boms/<int:pk>/deactivate/",
        deactivate_bom,
        name="deactivate_bom",
    ),
    path(
        "boms/",
        bom_list,
        name="bom_list",
    ),
    path(
        "",
        manufacturing_dashboard,
        name="dashboard",
    ),
    path(
        "production-orders/",
        production_order_list,
        name="production_order_list",
    ),
    path(
        "production-orders/<int:pk>/",
        production_order_detail,
        name="production_order_detail",
    ),
    path(
        "production-orders/<int:pk>/release/",
        release_production_order,
        name="release_production_order",
    ),
    path(
        "production-orders/<int:pk>/start/",
        start_production_order,
        name="start_production_order",
    ),
    path(
        "production-orders/<int:pk>/complete/",
        complete_production_order_view,
        name="complete_production_order",
    ),
]



