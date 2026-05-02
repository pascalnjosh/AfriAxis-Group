from django.db import models

class Apartment(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=150)

    def __str__(self):
        return self.name


class Unit(models.Model):
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE)
    unit_number = models.CharField(max_length=20)
    floor = models.CharField(max_length=20, blank=True, null=True)
    unit_type = models.CharField(max_length=50)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.apartment.name} - {self.unit_number}"