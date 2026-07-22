from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from enterprise.models import Company, Currency


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
