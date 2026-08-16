from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    BillOfMaterial,
    BillOfMaterialLine,
    ProductionOrder,
    ProductionOrderMaterial,
)
from .services import complete_production_order


class BillOfMaterialLineInline(admin.TabularInline):
    model = BillOfMaterialLine
    extra = 1


class ProductionOrderMaterialInline(admin.TabularInline):
    model = ProductionOrderMaterial
    extra = 1

    readonly_fields = (
        "consumed_quantity",
        "total_cost",
    )


@admin.register(BillOfMaterial)
class BillOfMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "company",
        "finished_product",
        "warehouse",
        "output_quantity",
        "version",
        "status",
        "created_at",
    )

    search_fields = (
        "code",
        "finished_product__product_code",
        "finished_product__name",
        "version",
    )

    list_filter = (
        "company",
        "warehouse",
        "status",
        "created_at",
    )

    readonly_fields = (
        "created_at",
    )

    inlines = (
        BillOfMaterialLineInline,
    )


@admin.register(BillOfMaterialLine)
class BillOfMaterialLineAdmin(admin.ModelAdmin):
    list_display = (
        "bom",
        "component",
        "quantity",
        "wastage_percent",
    )

    search_fields = (
        "bom__code",
        "component__product_code",
        "component__name",
    )

    list_filter = (
        "bom",
        "component",
    )


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "company",
        "bom",
        "warehouse",
        "planned_quantity",
        "produced_quantity",
        "status",
        "planned_start_date",
        "planned_end_date",
        "created_by",
        "created_at",
    )

    search_fields = (
        "order_number",
        "bom__code",
        "bom__finished_product__product_code",
        "bom__finished_product__name",
    )

    list_filter = (
        "company",
        "warehouse",
        "status",
        "planned_start_date",
        "planned_end_date",
        "created_at",
    )

    readonly_fields = (
        "produced_quantity",
        "actual_start_at",
        "completed_at",
        "created_at",
    )

    inlines = (
        ProductionOrderMaterialInline,
    )

    actions = (
        "complete_selected_production_orders",
    )

    @admin.action(
        description="Complete selected production orders"
    )
    def complete_selected_production_orders(
        self,
        request,
        queryset,
    ):
        completed_count = 0
        failed_count = 0

        for production_order in queryset:
            try:
                complete_production_order(
                    production_order,
                    user=request.user,
                )

                completed_count += 1

            except (ValidationError, ValueError) as exc:
                failed_count += 1

                error_message = (
                    "; ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )

                self.message_user(
                    request,
                    (
                        f"{production_order.order_number}: "
                        f"{error_message}"
                    ),
                    level=messages.ERROR,
                )

            except Exception as exc:
                failed_count += 1

                self.message_user(
                    request,
                    (
                        f"{production_order.order_number}: "
                        f"Unexpected completion error - {exc}"
                    ),
                    level=messages.ERROR,
                )

        if completed_count:
            self.message_user(
                request,
                (
                    f"Successfully completed {completed_count} "
                    f"production order(s)."
                ),
                level=messages.SUCCESS,
            )

        if failed_count:
            self.message_user(
                request,
                (
                    f"{failed_count} production order(s) "
                    f"were not completed."
                ),
                level=messages.WARNING,
            )


@admin.register(ProductionOrderMaterial)
class ProductionOrderMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "production_order",
        "component",
        "required_quantity",
        "consumed_quantity",
        "unit_cost",
        "total_cost",
    )

    search_fields = (
        "production_order__order_number",
        "component__product_code",
        "component__name",
    )

    list_filter = (
        "production_order",
        "component",
    )

    readonly_fields = (
        "consumed_quantity",
        "total_cost",
    )
