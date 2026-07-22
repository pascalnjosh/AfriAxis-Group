from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from enterprise.models import Branch, Company, Currency
from inventory.models import StorageLocation, Warehouse
from sales.models import Product


class Supplier(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="suppliers",
    )

    supplier_code = models.CharField(max_length=30)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    kra_pin = models.CharField(max_length=30, blank=True, default="")
    address = models.TextField(blank=True, default="")

    credit_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "supplier_code"],
                name="unique_supplier_code_per_company",
            ),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.supplier_code} - {self.name}"


class PurchaseRequest(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CONVERTED", "Converted to Purchase Order"),
        ("CANCELLED", "Cancelled"),
    )

    request_number = models.CharField(
        max_length=60,
        unique=True,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="purchase_requests",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="purchase_requests",
        null=True,
        blank=True,
    )

    request_date = models.DateField(
        default=timezone.localdate,
    )

    required_date = models.DateField(
        null=True,
        blank=True,
    )

    reason = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_purchase_requests",
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_purchase_requests",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.request_number


class PurchaseRequestLine(models.Model):
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="purchase_request_lines",
    )

    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    estimated_unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    notes = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    @property
    def estimated_total(self):
        return self.quantity * self.estimated_unit_cost

    def __str__(self):
        return (
            f"{self.purchase_request.request_number} - "
            f"{self.product.product_code}"
        )


class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("SENT", "Sent to Supplier"),
        ("PARTIALLY_RECEIVED", "Partially Received"),
        ("RECEIVED", "Fully Received"),
        ("CANCELLED", "Cancelled"),
    )

    order_number = models.CharField(
        max_length=60,
        unique=True,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="purchase_orders",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
        null=True,
        blank=True,
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
        null=True,
        blank=True,
    )

    order_date = models.DateField(
        default=timezone.localdate,
    )

    expected_delivery_date = models.DateField(
        null=True,
        blank=True,
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    notes = models.TextField(blank=True, default="")
    terms = models.TextField(blank=True, default="")

    subtotal = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    tax_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_purchase_orders",
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_purchase_orders",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def calculate_totals(self):
        subtotal = Decimal("0.00")
        tax = Decimal("0.00")

        for line in self.lines.all():
            subtotal += line.line_subtotal
            tax += line.tax_amount

        self.subtotal = subtotal
        self.tax_amount = tax
        self.total_amount = subtotal + tax

        self.save(
            update_fields=[
                "subtotal",
                "tax_amount",
                "total_amount",
            ]
        )

    def __str__(self):
        return self.order_number


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
    )

    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    quantity_received = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    @property
    def line_subtotal(self):
        return self.quantity * self.unit_cost

    @property
    def tax_amount(self):
        return self.line_subtotal * self.tax_rate / Decimal("100")

    @property
    def line_total(self):
        return self.line_subtotal + self.tax_amount

    @property
    def quantity_outstanding(self):
        return self.quantity - self.quantity_received

    def __str__(self):
        return (
            f"{self.purchase_order.order_number} - "
            f"{self.product.product_code}"
        )


class GoodsReceipt(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("POSTED", "Posted"),
        ("CANCELLED", "Cancelled"),
    )

    receipt_number = models.CharField(
        max_length=60,
        unique=True,
    )

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )

    receipt_date = models.DateField(
        default=timezone.localdate,
    )

    supplier_delivery_note = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    notes = models.TextField(blank=True, default="")

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="received_goods_receipts",
        null=True,
        blank=True,
    )

    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.receipt_number


class GoodsReceiptLine(models.Model):
    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        related_name="goods_receipt_lines",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="goods_receipt_lines",
    )

    location = models.ForeignKey(
        StorageLocation,
        on_delete=models.PROTECT,
        related_name="goods_receipt_lines",
    )

    quantity_received = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    batch_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.goods_receipt.receipt_number} - "
            f"{self.product.product_code}"
        )


class SupplierInvoice(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PENDING", "Pending"),
        ("PARTIAL", "Partially Paid"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    )

    invoice_number = models.CharField(
        max_length=100,
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
    )

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        related_name="supplier_invoices",
        null=True,
        blank=True,
    )

    invoice_date = models.DateField(
        default=timezone.localdate,
    )

    due_date = models.DateField(null=True, blank=True)

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
    )

    subtotal = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    tax_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    amount_paid = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "invoice_number"],
                name="unique_supplier_invoice_number",
            ),
        ]

    @property
    def balance(self):
        return self.total_amount - self.amount_paid

    def __str__(self):
        return (
            f"{self.supplier.name} - "
            f"{self.invoice_number}"
        )
