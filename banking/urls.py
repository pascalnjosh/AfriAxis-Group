from django.urls import path
from . import views

urlpatterns = [
    path(
        "reconciliation/",
        views.reconciliation_dashboard,
        name="bank_reconciliation",
    ),

    path(
        "upload/",
        views.upload_statement,
        name="upload_statement",
    ),

    path(
        "approve/<int:transaction_id>/",
        views.approve_transaction,
        name="approve_transaction",
    ),

    path(
        "approve-all/",
        views.approve_all_high_confidence,
        name="approve_all_high_confidence",
    ),

    # ADD THIS
    path(
        "reject/<int:transaction_id>/",
        views.reject_transaction,
        name="reject_transaction",
    ),
path("undo/<int:transaction_id>/", views.undo_transaction, name="undo_transaction"),
]