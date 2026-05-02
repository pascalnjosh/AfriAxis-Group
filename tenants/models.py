from django.db import models
from units.models import Unit


class Tenant(models.Model):
    full_name = models.CharField(max_length=150)
    id_number = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)

    unit = models.OneToOneField(Unit, on_delete=models.SET_NULL, null=True, blank=True)
    move_in_date = models.DateField(null=True, blank=True)
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.full_name