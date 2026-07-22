from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from enterprise.models import Branch, Company


class Warehouse(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="warehouses",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="warehouses",
        null=True,
        blank=True,
    )

    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True, default="")

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="managed_warehouses",
        null=True,
        blank=True,
    )

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_warehouse_code_per_company",
            ),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class StorageLocation(models.Model):
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="locations",
    )

    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "code"],
                name="unique_location_code_per_warehouse",
            ),
        ]
        ordering = ["warehouse", "code"]

    def __str__(self):
        return f"{self.warehouse.code} - {self.code}"


class InventoryBatch(models.Model):
    product = models.ForeignKey(
        "sales.Product",
        on_delete=models.PROTECT,
        related_name="inventory_batches",
    )

    batch_number = models.CharField(max_length=100)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    quantity_received = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )

    quantity_available = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )

    cost_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "batch_number"],
                name="unique_batch_number_per_product",
            ),
        ]
        ordering = ["expiry_date", "batch_number"]

    def __str__(self):
        return f"{self.product.product_code} - {self.batch_number}"


class StockBalance(models.Model):
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="stock_balances",
    )

    location = models.ForeignKey(
        StorageLocation,
        on_delete=models.CASCADE,
        related_name="stock_balances",
    )

    product = models.ForeignKey(
        "sales.Product",
        on_delete=models.PROTECT,
        related_name="stock_balances",
    )

    batch = models.ForeignKey(
        InventoryBatch,
        on_delete=models.PROTECT,
        related_name="stock_balances",
        null=True,
        blank=True,
    )

    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("0.000"),
    )

    average_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "warehouse",
                    "location",
                    "product",
                    "batch",
                ],
                name="unique_stock_balance",
            ),
        ]
        ordering = ["warehouse", "location", "product"]

    @property
    def stock_value(self):
        return self.quantity * self.average_cost

    def __str__(self):
        return (
            f"{self.product.product_code} - "
            f"{self.warehouse.code} - "
            f"{self.quantity}"
        )


class StockMovement(models.Model):
    MOVEMENT_TYPES = (
        ("OPENING", "Opening Balance"),
        ("PURCHASE", "Purchase Receipt"),
        ("RECEIPT", "General Receipt"),
        ("SALE", "Sale"),
        ("ISSUE", "General Issue"),
        ("TRANSFER_IN", "Transfer In"),
        ("TRANSFER_OUT", "Transfer Out"),
        ("ADJUSTMENT_IN", "Adjustment Increase"),
        ("ADJUSTMENT_OUT", "Adjustment Decrease"),
        ("CUSTOMER_RETURN", "Customer Return"),
        ("SUPPLIER_RETURN", "Supplier Return"),
    )

    movement_number = models.CharField(
        max_length=60,
        unique=True,
    )

    movement_type = models.CharField(
        max_length=30,
        choices=MOVEMENT_TYPES,
    )

    product = models.ForeignKey(
        "sales.Product",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    location = models.ForeignKey(
        StorageLocation,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    batch = models.ForeignKey(
        InventoryBatch,
        on_delete=models.PROTECT,
        related_name="stock_movements",
        null=True,
        blank=True,
    )

    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    reference = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    remarks = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_stock_movements",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost

    def __str__(self):
        return self.movement_number


class StockAdjustment(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("POSTED", "Posted"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    )

    adjustment_number = models.CharField(
        max_length=60,
        unique=True,
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="stock_adjustments",
    )

    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_stock_adjustments",
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_stock_adjustments",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.adjustment_number


class StockAdjustmentLine(models.Model):
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    location = models.ForeignKey(
        StorageLocation,
        on_delete=models.PROTECT,
        related_name="adjustment_lines",
    )

    product = models.ForeignKey(
        "sales.Product",
        on_delete=models.PROTECT,
        related_name="adjustment_lines",
    )

    batch = models.ForeignKey(
        InventoryBatch,
        on_delete=models.PROTECT,
        related_name="adjustment_lines",
        null=True,
        blank=True,
    )

    system_quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("0.000"),
    )

    counted_quantity = models.DecimalField(
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

    @property
    def variance(self):
        return self.counted_quantity - self.system_quantity

    def __str__(self):
        return (
            f"{self.adjustment.adjustment_number} - "
            f"{self.product.product_code}"
        )


