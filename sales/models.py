from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from enterprise.models import Branch, Company, Currency


class Customer(models.Model):
    CUSTOMER_TYPES = (
        ("INDIVIDUAL", "Individual"),
        ("BUSINESS", "Business"),
        ("GOVERNMENT", "Government"),
        ("NGO", "NGO"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="sales_customers",
    )

    customer_code = models.CharField(max_length=30)

    customer_type = models.CharField(
        max_length=20,
        choices=CUSTOMER_TYPES,
        default="BUSINESS",
    )

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

    current_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "customer_code"],
                name="unique_customer_code_per_company",
            ),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.customer_code} - {self.name}"


class ProductCategory(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="product_categories",
    )

    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_product_category_code",
            ),
        ]
        verbose_name_plural = "Product categories"

    def __str__(self):
        return self.name


class UnitOfMeasure(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="units_of_measure",
    )

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_unit_code_per_company",
            ),
        ]
        verbose_name_plural = "Units of measure"

    def __str__(self):
        return self.code


class Product(models.Model):
    PRODUCT_TYPES = (
        ("STOCK", "Stock Item"),
        ("SERVICE", "Service"),
        ("CONSUMABLE", "Consumable"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="products",
    )

    product_code = models.CharField(max_length=50)
    barcode = models.CharField(max_length=100, blank=True, default="")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")

    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPES,
        default="STOCK",
    )

    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        related_name="products",
    )

    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name="products",
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="products",
    )

    cost_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    selling_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    etims_item_code = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    track_inventory = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "product_code"],
                name="unique_product_code_per_company",
            ),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.product_code} - {self.name}"


class PriceList(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="price_lists",
    )

    name = models.CharField(max_length=100)

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="price_lists",
    )

    is_default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_price_list_per_company",
            ),
        ]

    def __str__(self):
        return self.name


class PriceListItem(models.Model):
    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="price_list_items",
    )

    price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    minimum_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "price_list",
                    "product",
                    "minimum_quantity",
                ],
                name="unique_product_price_tier",
            ),
        ]

    def __str__(self):
        return f"{self.price_list.name} - {self.product.name}"



class SalesOrder(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("CONFIRMED", "Confirmed"),
        ("PARTIALLY_DELIVERED", "Partially Delivered"),
        ("DELIVERED", "Delivered"),
        ("INVOICED", "Invoiced"),
        ("CANCELLED", "Cancelled"),
    )

    order_number = models.CharField(
        max_length=60,
        unique=True,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="sales_orders",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="sales_orders",
        null=True,
        blank=True,
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )

    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.SET_NULL,
        related_name="sales_orders",
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
        related_name="sales_orders",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    customer_reference = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    delivery_address = models.TextField(
        blank=True,
        default="",
    )

    notes = models.TextField(blank=True, default="")
    terms = models.TextField(blank=True, default="")

    subtotal = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    discount_amount = models.DecimalField(
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
        related_name="created_sales_orders",
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_sales_orders",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_totals(self):
        subtotal = Decimal("0.00")
        discount = Decimal("0.00")
        tax = Decimal("0.00")

        for line in self.lines.all():
            subtotal += line.line_subtotal
            discount += line.discount_amount
            tax += line.tax_amount

        self.subtotal = subtotal
        self.discount_amount = discount
        self.tax_amount = tax
        self.total_amount = subtotal - discount + tax

        self.save(
            update_fields=[
                "subtotal",
                "discount_amount",
                "tax_amount",
                "total_amount",
                "updated_at",
            ]
        )

    def __str__(self):
        return self.order_number


class SalesOrderLine(models.Model):
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sales_order_lines",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    quantity_delivered = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
    )

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    discount_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    @property
    def line_subtotal(self):
        return self.quantity * self.unit_price

    @property
    def discount_amount(self):
        return (
            self.line_subtotal
            * self.discount_rate
            / Decimal("100")
        )

    @property
    def taxable_amount(self):
        return self.line_subtotal - self.discount_amount

    @property
    def tax_amount(self):
        return (
            self.taxable_amount
            * self.tax_rate
            / Decimal("100")
        )

    @property
    def line_total(self):
        return self.taxable_amount + self.tax_amount

    @property
    def quantity_outstanding(self):
        return self.quantity - self.quantity_delivered

    def save(self, *args, **kwargs):
        if not self.description:
            self.description = self.product.name

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.sales_order.order_number} - "
            f"{self.product.product_code}"
        )


class DeliveryNote(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("POSTED", "Posted"),
        ("CANCELLED", "Cancelled"),
    )

    delivery_number = models.CharField(
        max_length=60,
        unique=True,
    )

    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name="delivery_notes",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="delivery_notes",
    )

    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="delivery_notes",
    )

    delivery_date = models.DateField(
        default=timezone.localdate,
    )

    delivery_address = models.TextField(
        blank=True,
        default="",
    )

    vehicle_number = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    driver_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    received_by_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    notes = models.TextField(blank=True, default="")

    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="dispatched_delivery_notes",
        null=True,
        blank=True,
    )

    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.delivery_number


class DeliveryNoteLine(models.Model):
    delivery_note = models.ForeignKey(
        DeliveryNote,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    sales_order_line = models.ForeignKey(
        SalesOrderLine,
        on_delete=models.PROTECT,
        related_name="delivery_lines",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="delivery_note_lines",
    )

    location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.PROTECT,
        related_name="delivery_note_lines",
    )

    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    batch_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    def __str__(self):
        return (
            f"{self.delivery_note.delivery_number} - "
            f"{self.product.product_code}"
        )


