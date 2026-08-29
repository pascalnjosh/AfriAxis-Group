from django.urls import path

from .views import (
    create_sales_documents,
    delivery_post,
    delivery_print,
    fas_customer_create,
    invoice_post,
    invoice_print,
    new_sale,
    sales_dashboard,
    sales_order_detail,
)


urlpatterns = [
    path(
        "",
        sales_dashboard,
        name="sales_dashboard",
    ),

    path(
        "new/",
        new_sale,
        name="new_sale",
    ),

    path(
        "customers/new/",
        fas_customer_create,
        name="fas_customer_create",
    ),

    path(
        "orders/<int:pk>/",
        sales_order_detail,
        name="sales_order_detail",
    ),

    path(
        "orders/<int:pk>/documents/",
        create_sales_documents,
        name="create_sales_documents",
    ),

    path(
        "invoices/<int:pk>/print/",
        invoice_print,
        name="invoice_print",
    ),

    path(
        "invoices/<int:pk>/post/",
        invoice_post,
        name="invoice_post",
    ),

    path(
        "deliveries/<int:pk>/print/",
        delivery_print,
        name="delivery_print",
    ),

    path(
        "deliveries/<int:pk>/post/",
        delivery_post,
        name="delivery_post",
    ),
]
