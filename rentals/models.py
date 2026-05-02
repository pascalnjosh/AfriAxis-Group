from django.db import models


# ✅ 1. Apartment FIRST (must be defined before use)
class Apartment(models.Model):
    name = models.CharField(max_length=100, unique=True)
    total_units = models.PositiveIntegerField(default=0)
    location = models.CharField(max_length=150, blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.total_units} units)"


# ✅ 2. Tenant
class Tenant(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)

    apartment = models.ForeignKey(
        Apartment,
        on_delete=models.CASCADE,
        related_name="tenants",
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name


# ✅ 3. House (linked to Apartment)
class House(models.Model):
    apartment = models.ForeignKey(
        Apartment,
        on_delete=models.CASCADE,
        related_name="houses",
        null=True,
        blank=True
    )

    house_number = models.CharField(max_length=20)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.house_number} ({self.apartment})"


# ✅ 4. Rent
class Rent(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    house = models.ForeignKey(House, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tenant} - {self.amount}"