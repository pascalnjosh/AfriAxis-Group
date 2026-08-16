from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from enterprise.models import Company
from inventory.models import Warehouse
from sales.models import Product


class BillOfMaterial(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("OBSOLETE", "Obsolete"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="bills_of_material",
    )

    code = models.CharField(max_length=50)

    finished_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="bom_finished_products",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="bills_of_material",
    )

    output_quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("1.000"),
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    version = models.CharField(
        max_length=30,
        default="1.0",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_bom_code_per_company",
            )
        ]

    def __str__(self):
        return self.code


class BillOfMaterialLine(models.Model):
    bom = models.ForeignKey(
        BillOfMaterial,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    component = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="bom_components",
    )

    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    wastage_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.component} ({self.quantity})"


class ProductionOrder(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("RELEASED", "Released"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="production_orders",
    )

    order_number = models.CharField(max_length=50)

    bom = models.ForeignKey(
        BillOfMaterial,
        on_delete=models.PROTECT,
        related_name="production_orders",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="production_orders",
    )

    raw_material_location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.PROTECT,
        related_name="production_material_orders",
    )

    finished_goods_location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.PROTECT,
        related_name="production_output_orders",
    )

    planned_quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    produced_quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    planned_start_date = models.DateField(
        null=True,
        blank=True,
    )

    planned_end_date = models.DateField(
        null=True,
        blank=True,
    )

    actual_start_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        related_name="created_production_orders",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "order_number"],
                name="unique_production_order_per_company",
            )
        ]

    def __str__(self):
        return self.order_number


class ProductionOrderMaterial(models.Model):
    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="materials",
    )

    component = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="production_material_lines",
    )

    required_quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    consumed_quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["id"]

        constraints = [
            models.UniqueConstraint(
                fields=["production_order", "component"],
                name="unique_component_per_production_order",
            )
        ]

    @property
    def total_cost(self):
        return self.consumed_quantity * self.unit_cost

    def __str__(self):
        return (
            f"{self.production_order.order_number} - "
            f"{self.component}"
        )
