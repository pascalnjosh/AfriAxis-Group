from accounts.decorators import operations_required
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from inventory.models import StockBalance

from .models import BillOfMaterial, ProductionOrder
from .services import complete_production_order


@operations_required
def manufacturing_dashboard(request):
    boms = BillOfMaterial.objects.select_related(
        "finished_product",
        "warehouse",
        "company",
    )

    orders = ProductionOrder.objects.select_related(
        "bom",
        "bom__finished_product",
        "warehouse",
        "company",
    )

    active_boms = boms.filter(status="ACTIVE").count()
    total_boms = boms.count()

    released_orders = orders.filter(status="RELEASED").count()
    in_progress_orders = orders.filter(status="IN_PROGRESS").count()
    completed_orders = orders.filter(status="COMPLETED").count()

    inventory_value = Decimal("0.00")

    for stock in StockBalance.objects.select_related(
        "location",
        "product",
    ):
        inventory_value += (
            Decimal(str(stock.quantity))
            * Decimal(str(stock.average_cost))
        )

    recent_orders = orders.order_by("-created_at")[:10]

    context = {
        "total_boms": total_boms,
        "active_boms": active_boms,
        "released_orders": released_orders,
        "in_progress_orders": in_progress_orders,
        "completed_orders": completed_orders,
        "inventory_value": inventory_value,
        "recent_orders": recent_orders,
    }

    return render(
        request,
        "manufacturing/dashboard.html",
        context,
    )


@operations_required
def production_order_list(request):
    orders = (
        ProductionOrder.objects
        .select_related(
            "bom",
            "bom__finished_product",
            "warehouse",
            "company",
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "manufacturing/production_order_list.html",
        {
            "orders": orders,
        },
    )


@operations_required
def production_order_detail(request, pk):
    order = get_object_or_404(
        ProductionOrder.objects.select_related(
            "bom",
            "bom__finished_product",
            "warehouse",
            "raw_material_location",
            "finished_goods_location",
        ).prefetch_related(
            "materials",
            "materials__component",
        ),
        pk=pk,
    )

    return render(
        request,
        "manufacturing/production_order_detail.html",
        {
            "order": order,
        },
    )


def _validate_production_order_setup(order):
    errors = []

    if order.bom.status != "ACTIVE":
        errors.append(
            "The selected BOM must be ACTIVE."
        )

    if not order.bom.lines.exists():
        errors.append(
            "The BOM has no component lines."
        )

    if not order.materials.exists():
        errors.append(
            "The production order has no material lines."
        )

    if (
        order.raw_material_location.warehouse_id
        != order.warehouse_id
    ):
        errors.append(
            "Raw material location is outside the selected warehouse."
        )

    if (
        order.finished_goods_location.warehouse_id
        != order.warehouse_id
    ):
        errors.append(
            "Finished goods location is outside the selected warehouse."
        )

    if (
        order.finished_goods_location.code.upper()
        != "FINISHED"
    ):
        errors.append(
            "Finished goods location must be FINISHED."
        )

    for material in order.materials.all():
        if material.component_id == order.bom.finished_product_id:
            errors.append(
                (
                    f"{material.component.product_code} cannot "
                    f"be both finished product and raw material."
                )
            )

        if material.required_quantity <= 0:
            errors.append(
                (
                    f"Required quantity for "
                    f"{material.component.product_code} "
                    f"must be greater than zero."
                )
            )

    return errors


@operations_required
def release_production_order(request, pk):
    if request.method != "POST":
        return redirect(
            "manufacturing:production_order_detail",
            pk=pk,
        )

    order = get_object_or_404(
        ProductionOrder.objects.prefetch_related(
            "materials",
            "materials__component",
            "bom__lines",
        ),
        pk=pk,
    )

    if order.status != "DRAFT":
        messages.error(
            request,
            "Only draft production orders can be released.",
        )

        return redirect(
            "manufacturing:production_order_detail",
            pk=pk,
        )

    errors = _validate_production_order_setup(order)

    if errors:
        for error in errors:
            messages.error(request, error)

        return redirect(
            "manufacturing:production_order_detail",
            pk=pk,
        )

    order.status = "RELEASED"

    order.save(
        update_fields=[
            "status",
        ]
    )

    messages.success(
        request,
        f"{order.order_number} released successfully.",
    )

    return redirect(
        "manufacturing:production_order_detail",
        pk=pk,
    )


@operations_required
def start_production_order(request, pk):
    if request.method != "POST":
        return redirect(
            "manufacturing:production_order_detail",
            pk=pk,
        )

    order = get_object_or_404(
        ProductionOrder.objects.prefetch_related(
            "materials",
            "materials__component",
            "bom__lines",
        ),
        pk=pk,
    )

    if order.status != "RELEASED":
        messages.error(
            request,
            "Only released production orders can be started.",
        )

        return redirect(
            "manufacturing:production_order_detail",
            pk=pk,
        )

    errors = _validate_production_order_setup(order)

    if errors:
        for error in errors:
            messages.error(request, error)

        return redirect(
            "manufacturing:production_order_detail",
            pk=pk,
        )

    order.status = "IN_PROGRESS"

    if order.actual_start_at is None:
        order.actual_start_at = timezone.now()

    order.save(
        update_fields=[
            "status",
            "actual_start_at",
        ]
    )

    messages.success(
        request,
        f"{order.order_number} started successfully.",
    )

    return redirect(
        "manufacturing:production_order_detail",
        pk=pk,
    )


@operations_required
def complete_production_order_view(request, pk):
    if request.method != "POST":
        return redirect(
            "manufacturing:production_order_detail",
            pk=pk,
        )

    order = get_object_or_404(
        ProductionOrder.objects.prefetch_related(
            "materials",
            "materials__component",
            "bom__lines",
        ),
        pk=pk,
    )

    errors = _validate_production_order_setup(order)

    if errors:
        for error in errors:
            messages.error(request, error)

        return redirect(
            "manufacturing:production_order_detail",
            pk=pk,
        )

    try:
        complete_production_order(
            order,
            user=request.user,
        )

        messages.success(
            request,
            f"{order.order_number} completed successfully.",
        )

    except (ValidationError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            error_message = "; ".join(exc.messages)
        else:
            error_message = str(exc)

        messages.error(
            request,
            error_message,
        )

    except Exception as exc:
        messages.error(
            request,
            f"Production completion failed: {exc}",
        )

    return redirect(
        "manufacturing:production_order_detail",
        pk=pk,
    )


@operations_required
def bom_list(request):
    boms = (
        BillOfMaterial.objects
        .select_related(
            "finished_product",
            "warehouse",
            "company",
        )
        .prefetch_related(
            "lines",
        )
        .order_by("code")
    )

    return render(
        request,
        "manufacturing/bom_list.html",
        {
            "boms": boms,
        },
    )


@operations_required
def bom_detail(request, pk):
    from sales.models import Product

    bom = get_object_or_404(
        BillOfMaterial.objects.select_related(
            "finished_product",
            "warehouse",
            "company",
        ).prefetch_related(
            "lines",
            "lines__component",
        ),
        pk=pk,
    )

    products = (
        Product.objects
        .filter(
            company=bom.company,
            active=True,
            product_type__in=[
                "STOCK",
                "CONSUMABLE",
            ],
        )
        .exclude(
            pk=bom.finished_product_id,
        )
        .order_by("name")
    )

    return render(
        request,
        "manufacturing/bom_detail.html",
        {
            "bom": bom,
            "products": products,
        },
    )


@operations_required
def activate_bom(request, pk):
    if request.method != "POST":
        return redirect(
            "manufacturing:bom_detail",
            pk=pk,
        )

    bom = get_object_or_404(
        BillOfMaterial.objects.prefetch_related(
            "lines",
            "lines__component",
        ),
        pk=pk,
    )

    errors = []

    if not bom.lines.exists():
        errors.append(
            "This BOM has no component lines."
        )

    for line in bom.lines.all():
        if line.component_id == bom.finished_product_id:
            errors.append(
                (
                    f"{line.component.product_code} cannot be "
                    f"both finished product and component."
                )
            )

        if line.quantity <= 0:
            errors.append(
                (
                    f"Quantity for "
                    f"{line.component.product_code} "
                    f"must be greater than zero."
                )
            )

    if errors:
        for error in errors:
            messages.error(request, error)

    else:
        bom.status = "ACTIVE"
        bom.save(update_fields=["status"])

        messages.success(
            request,
            f"{bom.code} activated successfully.",
        )

    return redirect(
        "manufacturing:bom_detail",
        pk=pk,
    )


@operations_required
def deactivate_bom(request, pk):
    if request.method != "POST":
        return redirect(
            "manufacturing:bom_detail",
            pk=pk,
        )

    bom = get_object_or_404(
        BillOfMaterial,
        pk=pk,
    )

    bom.status = "DRAFT"
    bom.save(update_fields=["status"])

    messages.success(
        request,
        f"{bom.code} returned to draft.",
    )

    return redirect(
        "manufacturing:bom_detail",
        pk=pk,
    )


@operations_required
def add_bom_component(request, pk):
    bom = get_object_or_404(
        BillOfMaterial,
        pk=pk,
    )

    if request.method != "POST":
        return redirect(
            "manufacturing:bom_detail",
            pk=pk,
        )

    from sales.models import Product
    from .models import BillOfMaterialLine

    component_id = request.POST.get("component")
    quantity = request.POST.get("quantity")
    wastage_percent = request.POST.get(
        "wastage_percent",
        "0",
    )

    try:
        component = Product.objects.get(
            pk=component_id,
            company=bom.company,
        )

        quantity = Decimal(str(quantity))
        wastage_percent = Decimal(
            str(wastage_percent)
        )

        if component.id == bom.finished_product_id:
            messages.error(
                request,
                "Finished product cannot be used as its own component.",
            )

        elif quantity <= 0:
            messages.error(
                request,
                "Component quantity must be greater than zero.",
            )

        elif wastage_percent < 0:
            messages.error(
                request,
                "Wastage percentage cannot be negative.",
            )

        elif BillOfMaterialLine.objects.filter(
            bom=bom,
            component=component,
        ).exists():
            messages.error(
                request,
                (
                    f"{component.product_code} is already "
                    f"on this BOM."
                ),
            )

        else:
            BillOfMaterialLine.objects.create(
                bom=bom,
                component=component,
                quantity=quantity,
                wastage_percent=wastage_percent,
            )

            messages.success(
                request,
                (
                    f"{component.product_code} added "
                    f"to {bom.code}."
                ),
            )

    except Product.DoesNotExist:
        messages.error(
            request,
            "Selected component does not exist.",
        )

    except Exception as exc:
        messages.error(
            request,
            f"Unable to add component: {exc}",
        )

    return redirect(
        "manufacturing:bom_detail",
        pk=pk,
    )


@operations_required
def delete_bom_component(request, pk, line_id):
    if request.method != "POST":
        return redirect(
            "manufacturing:bom_detail",
            pk=pk,
        )

    from .models import BillOfMaterialLine

    bom = get_object_or_404(
        BillOfMaterial,
        pk=pk,
    )

    line = get_object_or_404(
        BillOfMaterialLine,
        pk=line_id,
        bom=bom,
    )

    component_code = line.component.product_code

    if bom.status == "ACTIVE":
        messages.error(
            request,
            "Return the BOM to draft before removing components.",
        )

    else:
        line.delete()

        messages.success(
            request,
            f"{component_code} removed from {bom.code}.",
        )

    return redirect(
        "manufacturing:bom_detail",
        pk=pk,
    )


