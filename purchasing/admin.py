from django.contrib import admin, messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    Supplier,
    SupplierInvoice,
    SupplierPayment,
)
from enterprise.approval_services import (
    approve_request,
    reject_request,
    submit_for_approval,
)
from enterprise.models import ApprovalRequest

from .services import post_goods_receipt, post_supplier_payment


class PurchaseRequestLineInline(admin.TabularInline):
    model = PurchaseRequestLine
    extra = 1


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number",
        "company",
        "branch",
        "request_date",
        "required_date",
        "status",
    )

    list_filter = (
        "status",
        "request_date",
        "company",
        "branch",
    )

    search_fields = (
        "request_number",
        "reason",
    )

    inlines = [PurchaseRequestLineInline]


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "supplier",
        "order_date",
        "status",
        "currency",
        "total_amount",
    )

    list_filter = (
        "status",
        "order_date",
        "company",
        "branch",
    )

    search_fields = (
        "order_number",
        "supplier__name",
        "supplier__supplier_code",
    )

    readonly_fields = (
        "subtotal",
        "tax_amount",
        "total_amount",
        "created_at",
        "approved_by",
        "approved_at",
    )

    inlines = [PurchaseOrderLineInline]

    actions = (
        "submit_selected_purchase_orders",
        "approve_selected_purchase_orders",
        "reject_selected_purchase_orders",
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        form.instance.calculate_totals()

    def _pending_approval_request(self, purchase_order):
        content_type = ContentType.objects.get_for_model(
            purchase_order,
            for_concrete_model=False,
        )

        return (
            ApprovalRequest.objects
            .filter(
                company=purchase_order.company,
                content_type=content_type,
                object_id=purchase_order.pk,
                status="PENDING",
            )
            .select_related(
                "workflow",
                "current_step",
            )
            .first()
        )

    @admin.action(
        description="Submit selected purchase orders for approval"
    )
    def submit_selected_purchase_orders(self, request, queryset):
        submitted = 0
        failed = 0

        for purchase_order in queryset:
            try:
                if purchase_order.status != "DRAFT":
                    raise ValidationError(
                        "Only draft purchase orders can be submitted."
                    )

                purchase_order.calculate_totals()

                if not purchase_order.lines.exists():
                    raise ValidationError(
                        "The purchase order has no lines."
                    )

                if purchase_order.total_amount <= 0:
                    raise ValidationError(
                        "The purchase order total must be greater than zero."
                    )

                submit_for_approval(
                    document=purchase_order,
                    document_type="PURCHASE_ORDER",
                    user=request.user,
                    notes=(
                        "Purchase order submitted through "
                        "the administration portal."
                    ),
                )

                purchase_order.status = "PENDING"

                purchase_order.save(
                    update_fields=["status"]
                )

                submitted += 1

            except (ValidationError, ValueError) as exc:
                failed += 1

                message = (
                    "; ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )

                self.message_user(
                    request,
                    f"{purchase_order.order_number}: {message}",
                    level=messages.ERROR,
                )

        if submitted:
            self.message_user(
                request,
                f"{submitted} purchase order(s) submitted for approval.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} purchase order submission(s) failed.",
                level=messages.WARNING,
            )

    @admin.action(
        description="Approve selected purchase orders"
    )
    def approve_selected_purchase_orders(self, request, queryset):
        approved = 0
        advanced = 0
        failed = 0

        for purchase_order in queryset:
            try:
                if purchase_order.status != "PENDING":
                    raise ValidationError(
                        "Only pending purchase orders can be approved."
                    )

                approval_request = self._pending_approval_request(
                    purchase_order
                )

                if approval_request is None:
                    raise ValidationError(
                        "No pending approval request was found."
                    )

                approval_request = approve_request(
                    approval_request=approval_request,
                    user=request.user,
                    comments=(
                        "Approved through the Purchase Order "
                        "administration portal."
                    ),
                )

                if approval_request.status == "APPROVED":
                    purchase_order.status = "APPROVED"
                    purchase_order.approved_by = request.user
                    purchase_order.approved_at = timezone.now()

                    purchase_order.save(
                        update_fields=[
                            "status",
                            "approved_by",
                            "approved_at",
                        ]
                    )

                    approved += 1

                else:
                    advanced += 1

            except (ValidationError, ValueError) as exc:
                failed += 1

                message = (
                    "; ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )

                self.message_user(
                    request,
                    f"{purchase_order.order_number}: {message}",
                    level=messages.ERROR,
                )

        if approved:
            self.message_user(
                request,
                f"{approved} purchase order(s) fully approved.",
                level=messages.SUCCESS,
            )

        if advanced:
            self.message_user(
                request,
                (
                    f"{advanced} purchase order(s) advanced "
                    "to the next approval step."
                ),
                level=messages.INFO,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} purchase order approval(s) failed.",
                level=messages.WARNING,
            )

    @admin.action(
        description="Reject selected purchase orders"
    )
    def reject_selected_purchase_orders(self, request, queryset):
        rejected = 0
        failed = 0

        for purchase_order in queryset:
            try:
                if purchase_order.status != "PENDING":
                    raise ValidationError(
                        "Only pending purchase orders can be rejected."
                    )

                approval_request = self._pending_approval_request(
                    purchase_order
                )

                if approval_request is None:
                    raise ValidationError(
                        "No pending approval request was found."
                    )

                reject_request(
                    approval_request=approval_request,
                    user=request.user,
                    comments=(
                        "Rejected through the Purchase Order "
                        "administration portal."
                    ),
                )

                purchase_order.status = "REJECTED"
                purchase_order.approved_by = None
                purchase_order.approved_at = None

                purchase_order.save(
                    update_fields=[
                        "status",
                        "approved_by",
                        "approved_at",
                    ]
                )

                rejected += 1

            except (ValidationError, ValueError) as exc:
                failed += 1

                message = (
                    "; ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )

                self.message_user(
                    request,
                    f"{purchase_order.order_number}: {message}",
                    level=messages.ERROR,
                )

        if rejected:
            self.message_user(
                request,
                f"{rejected} purchase order(s) rejected.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} purchase order rejection(s) failed.",
                level=messages.WARNING,
            )

class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 1


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "purchase_order",
        "supplier",
        "warehouse",
        "receipt_date",
        "status",
    )

    list_filter = (
        "status",
        "receipt_date",
        "warehouse",
    )

    search_fields = (
        "receipt_number",
        "purchase_order__order_number",
        "supplier__name",
        "supplier_delivery_note",
    )

    readonly_fields = (
        "posted_at",
        "created_at",
    )

    inlines = [GoodsReceiptLineInline]

    actions = ["post_selected_goods_receipts"]

    @admin.action(
        description="Post selected goods receipts"
    )
    def post_selected_goods_receipts(self, request, queryset):
        posted = 0
        failed = 0

        for receipt in queryset:
            try:
                post_goods_receipt(
                    goods_receipt=receipt,
                    user=request.user,
                )
                posted += 1

            except (ValidationError, ValueError) as exc:
                failed += 1

                message = (
                    "; ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )

                self.message_user(
                    request,
                    f"{receipt.receipt_number}: {message}",
                    level=messages.ERROR,
                )

        if posted:
            self.message_user(
                request,
                f"{posted} goods receipt(s) posted successfully.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} goods receipt(s) failed.",
                level=messages.WARNING,
            )


for model in (
    Supplier,
    SupplierInvoice,
    ):
    if not admin.site.is_registered(model):
        admin.site.register(model)


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "supplier",
        "supplier_invoice",
        "payment_date",
        "amount",
        "payment_method",
        "bank_account",
        "posted",
    )

    list_filter = (
        "posted",
        "payment_method",
        "payment_date",
        "supplier",
        "bank_account",
    )

    search_fields = (
        "reference",
        "supplier__name",
        "supplier__supplier_code",
        "supplier_invoice__invoice_number",
    )

    readonly_fields = (
        "posted",
        "posted_at",
        "created_at",
    )

    actions = ["post_selected_supplier_payments"]

    @admin.action(
        description="Post selected supplier payments"
    )
    def post_selected_supplier_payments(self, request, queryset):
        posted_count = 0
        failed_count = 0

        for payment in queryset:
            try:
                post_supplier_payment(
                    payment=payment,
                    user=request.user,
                )
                posted_count += 1

            except (ValidationError, ValueError) as exc:
                failed_count += 1

                message = (
                    "; ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )

                self.message_user(
                    request,
                    f"{payment.reference}: {message}",
                    level=messages.ERROR,
                )

        if posted_count:
            self.message_user(
                request,
                f"{posted_count} supplier payment(s) posted.",
                level=messages.SUCCESS,
            )

        if failed_count:
            self.message_user(
                request,
                f"{failed_count} supplier payment(s) failed.",
                level=messages.WARNING,
            )




