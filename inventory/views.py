from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render

from sales.models import Product

from .models import (
    InventoryBatch,
    StockAdjustment,
    StockBalance,
    StockMovement,
    StorageLocation,
    Warehouse,
)


@login_required
def inventory_dashboard(request):
    stock_value_expression = ExpressionWrapper(
        F("quantity") * F("average_cost"),
        output_field=DecimalField(
            max_digits=20,
            decimal_places=2,
        ),
    )

    total_inventory_value = (
        StockBalance.objects.aggregate(
            total=Coalesce(
                Sum(stock_value_expression),
                Decimal("0.00"),
            )
        )["total"]
    )

    negative_stock_count = StockBalance.objects.filter(
        quantity__lt=0,
    ).count()

    zero_stock_count = StockBalance.objects.filter(
        quantity=0,
    ).count()

    positive_stock_count = StockBalance.objects.filter(
        quantity__gt=0,
    ).count()

    low_stock_rows = (
        StockBalance.objects
        .filter(
            quantity__gt=0,
            quantity__lte=5,
        )
        .select_related(
            "product",
            "warehouse",
            "location",
            "batch",
        )
        .order_by(
            "quantity",
            "product__name",
        )[:10]
    )

    recent_movements = (
        StockMovement.objects
        .select_related(
            "product",
            "warehouse",
            "location",
            "batch",
            "created_by",
        )
        .order_by(
            "-created_at",
            "-id",
        )[:10]
    )

    recent_adjustments = (
        StockAdjustment.objects
        .select_related(
            "warehouse",
            "created_by",
            "approved_by",
        )
        .order_by(
            "-created_at",
            "-id",
        )[:10]
    )

    context = {
        "product_count": Product.objects.filter(
            active=True,
        ).count(),
        "warehouse_count": Warehouse.objects.filter(
            active=True,
        ).count(),
        "location_count": StorageLocation.objects.filter(
            active=True,
        ).count(),
        "batch_count": InventoryBatch.objects.filter(
            active=True,
        ).count(),
        "movement_count": StockMovement.objects.count(),
        "adjustment_count": StockAdjustment.objects.count(),
        "total_inventory_value": total_inventory_value,
        "negative_stock_count": negative_stock_count,
        "zero_stock_count": zero_stock_count,
        "positive_stock_count": positive_stock_count,
        "low_stock_rows": low_stock_rows,
        "recent_movements": recent_movements,
        "recent_adjustments": recent_adjustments,
    }

    return render(
        request,
        "inventory/dashboard.html",
        context,
    )


@login_required
def stock_balances(request):
    warehouse_id = request.GET.get("warehouse")
    product_id = request.GET.get("product")
    search = request.GET.get("q", "").strip()

    balances = (
        StockBalance.objects
        .select_related(
            "warehouse",
            "location",
            "product",
            "batch",
        )
        .order_by(
            "warehouse__name",
            "location__code",
            "product__name",
        )
    )

    if warehouse_id:
        balances = balances.filter(
            warehouse_id=warehouse_id,
        )

    if product_id:
        balances = balances.filter(
            product_id=product_id,
        )

    if search:
        balances = balances.filter(
            Q(product__product_code__icontains=search)
            | Q(product__name__icontains=search)
            | Q(batch__batch_number__icontains=search)
            | Q(location__code__icontains=search)
        )

    stock_value_expression = ExpressionWrapper(
        F("quantity") * F("average_cost"),
        output_field=DecimalField(
            max_digits=20,
            decimal_places=2,
        ),
    )

    totals = balances.aggregate(
        total_quantity=Coalesce(
            Sum("quantity"),
            Decimal("0.000"),
        ),
        total_value=Coalesce(
            Sum(stock_value_expression),
            Decimal("0.00"),
        ),
    )

    return render(
        request,
        "inventory/stock_balances.html",
        {
            "balances": balances,
            "warehouses": Warehouse.objects.filter(
                active=True,
            ).order_by("name"),
            "products": Product.objects.filter(
                active=True,
            ).order_by("name"),
            "selected_warehouse": warehouse_id,
            "selected_product": product_id,
            "search": search,
            "total_quantity": totals["total_quantity"],
            "total_value": totals["total_value"],
        },
    )


@login_required
def movement_history(request):
    warehouse_id = request.GET.get("warehouse")
    product_id = request.GET.get("product")
    movement_type = request.GET.get("movement_type")
    search = request.GET.get("q", "").strip()

    movements = (
        StockMovement.objects
        .select_related(
            "product",
            "warehouse",
            "location",
            "batch",
            "created_by",
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )

    if warehouse_id:
        movements = movements.filter(
            warehouse_id=warehouse_id,
        )

    if product_id:
        movements = movements.filter(
            product_id=product_id,
        )

    if movement_type:
        movements = movements.filter(
            movement_type=movement_type,
        )

    if search:
        movements = movements.filter(
            Q(movement_number__icontains=search)
            | Q(reference__icontains=search)
            | Q(product__product_code__icontains=search)
            | Q(product__name__icontains=search)
            | Q(batch__batch_number__icontains=search)
        )

    totals = movements.aggregate(
        total_quantity=Coalesce(
            Sum("quantity"),
            Decimal("0.000"),
        )
    )

    return render(
        request,
        "inventory/movements.html",
        {
            "movements": movements[:500],
            "warehouses": Warehouse.objects.filter(
                active=True,
            ).order_by("name"),
            "products": Product.objects.filter(
                active=True,
            ).order_by("name"),
            "movement_types": StockMovement.MOVEMENT_TYPES,
            "selected_warehouse": warehouse_id,
            "selected_product": product_id,
            "selected_movement_type": movement_type,
            "search": search,
            "total_quantity": totals["total_quantity"],
        },
    )


@login_required
def stock_ledger(request):
    product_id = request.GET.get("product")
    warehouse_id = request.GET.get("warehouse")

    selected_product = None
    rows = []
    running_balance = Decimal("0.000")
    running_value = Decimal("0.00")

    movements = StockMovement.objects.none()

    if product_id:
        selected_product = get_object_or_404(
            Product,
            pk=product_id,
        )

        movements = (
            StockMovement.objects
            .filter(
                product=selected_product,
            )
            .select_related(
                "warehouse",
                "location",
                "batch",
            )
            .order_by(
                "created_at",
                "id",
            )
        )

        if warehouse_id:
            movements = movements.filter(
                warehouse_id=warehouse_id,
            )

        inward_types = {
            "OPENING",
            "PURCHASE",
            "RECEIPT",
            "TRANSFER_IN",
            "ADJUSTMENT_IN",
            "CUSTOMER_RETURN",
        }

        for movement in movements:
            quantity_in = Decimal("0.000")
            quantity_out = Decimal("0.000")

            if movement.movement_type in inward_types:
                quantity_in = movement.quantity
                running_balance += movement.quantity
                running_value += movement.total_cost
            else:
                quantity_out = movement.quantity
                running_balance -= movement.quantity
                running_value -= movement.total_cost

            rows.append(
                {
                    "date": movement.created_at,
                    "movement_number": movement.movement_number,
                    "movement_type": movement.get_movement_type_display(),
                    "reference": movement.reference,
                    "warehouse": movement.warehouse,
                    "location": movement.location,
                    "batch": movement.batch,
                    "quantity_in": quantity_in,
                    "quantity_out": quantity_out,
                    "unit_cost": movement.unit_cost,
                    "running_balance": running_balance,
                    "running_value": running_value,
                }
            )

    return render(
        request,
        "inventory/stock_ledger.html",
        {
            "products": Product.objects.filter(
                active=True,
            ).order_by("name"),
            "warehouses": Warehouse.objects.filter(
                active=True,
            ).order_by("name"),
            "selected_product": selected_product,
            "selected_warehouse": warehouse_id,
            "rows": rows,
            "closing_quantity": running_balance,
            "closing_value": running_value,
        },
    )
