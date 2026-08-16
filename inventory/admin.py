from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    InventoryBatch,
    StockAdjustment,
    StockAdjustmentLine,
    StockBalance,
    StockMovement,
    StorageLocation,
    Warehouse,
)
from .services import post_stock_adjustment


class StorageLocationInline(admin.TabularInline):
    model = StorageLocation
    extra = 1


class StockAdjustmentLineInline(admin.TabularInline):
    model = StockAdjustmentLine
    extra = 1

    readonly_fields = (
        "variance",
    )


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "company",
        "branch",
        "manager",
        "active",
    )

    search_fields = (
        "code",
        "name",
        "address",
    )

    list_filter = (
        "company",
        "branch",
        "active",
    )

    inlines = (
        StorageLocationInline,
    )


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = (
        "warehouse",
        "code",
        "name",
        "active",
    )

    search_fields = (
        "warehouse__code",
        "warehouse__name",
        "code",
        "name",
    )

    list_filter = (
        "warehouse",
        "active",
    )


@admin.register(InventoryBatch)
class InventoryBatchAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "batch_number",
        "manufacturing_date",
        "expiry_date",
        "quantity_received",
        "quantity_available",
        "cost_price",
        "active",
    )

    search_fields = (
        "product__product_code",
        "product__name",
        "batch_number",
    )

    list_filter = (
        "product",
        "expiry_date",
        "active",
    )


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = (
        "warehouse",
        "location",
        "product",
        "batch",
        "quantity",
        "average_cost",
        "stock_value",
        "updated_at",
    )

    search_fields = (
        "product__product_code",
        "product__name",
        "warehouse__code",
        "location__code",
        "batch__batch_number",
    )

    list_filter = (
        "warehouse",
        "location",
        "product",
    )

    readonly_fields = (
        "stock_value",
        "updated_at",
    )


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "movement_number",
        "movement_type",
        "product",
        "warehouse",
        "location",
        "batch",
        "quantity",
        "unit_cost",
        "total_cost",
        "reference",
        "created_at",
    )

    search_fields = (
        "movement_number",
        "reference",
        "product__product_code",
        "product__name",
        "batch__batch_number",
    )

    list_filter = (
        "movement_type",
        "warehouse",
        "location",
        "product",
        "created_at",
    )

    readonly_fields = (
        "total_cost",
        "created_at",
    )


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        "adjustment_number",
        "warehouse",
        "status",
        "created_by",
        "approved_by",
        "created_at",
        "approved_at",
    )

    search_fields = (
        "adjustment_number",
        "reason",
    )

    list_filter = (
        "warehouse",
        "status",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "approved_at",
    )

    inlines = (
        StockAdjustmentLineInline,
    )

    actions = (
        "post_selected_stock_adjustments",
    )

    @admin.action(
        description="Post selected stock adjustments"
    )
    def post_selected_stock_adjustments(
        self,
        request,
        queryset,
    ):
        posted_count = 0
        failed_count = 0

        for adjustment in queryset:
            try:
                post_stock_adjustment(
                    adjustment,
                    user=request.user,
                )
                posted_count += 1

            except (ValidationError, ValueError) as exc:
                failed_count += 1

                if hasattr(exc, "messages"):
                    error_message = "; ".join(exc.messages)
                else:
                    error_message = str(exc)

                self.message_user(
                    request,
                    (
                        f"{adjustment.adjustment_number}: "
                        f"{error_message}"
                    ),
                    level=messages.ERROR,
                )

            except Exception as exc:
                failed_count += 1

                self.message_user(
                    request,
                    (
                        f"{adjustment.adjustment_number}: "
                        f"Unexpected posting error — {exc}"
                    ),
                    level=messages.ERROR,
                )

        if posted_count:
            self.message_user(
                request,
                (
                    f"Successfully posted {posted_count} "
                    f"stock adjustment(s)."
                ),
                level=messages.SUCCESS,
            )

        if failed_count:
            self.message_user(
                request,
                (
                    f"{failed_count} stock adjustment(s) "
                    f"were not posted."
                ),
                level=messages.WARNING,
            )


@admin.register(StockAdjustmentLine)
class StockAdjustmentLineAdmin(admin.ModelAdmin):
    list_display = (
        "adjustment",
        "location",
        "product",
        "batch",
        "system_quantity",
        "counted_quantity",
        "variance",
        "unit_cost",
    )

    search_fields = (
        "adjustment__adjustment_number",
        "product__product_code",
        "product__name",
        "batch__batch_number",
    )

    list_filter = (
        "adjustment",
        "location",
        "product",
    )

    readonly_fields = (
        "variance",
    )
