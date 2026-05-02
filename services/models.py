from django.db import models
from django.utils import timezone


class WifiPackage(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=0)
    duration_minutes = models.IntegerField(default=0)
    speed = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name


class WifiCustomer(models.Model):
    def refresh_status(self):
        now = timezone.now()

        if self.expiry_date and self.expiry_date < now:
            self.active = False
        elif self.start_date and self.expiry_date and self.start_date <= now <= self.expiry_date:
            self.active = True

        self.save(update_fields=["active"])

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    package = models.ForeignKey(WifiPackage, on_delete=models.SET_NULL, null=True, blank=True)
    active = models.BooleanField(default=False)
    start_date = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateTimeField(null=True, blank=True)

    @property
    def is_overdue(self):
        if not self.expiry_date:
            return False
        return timezone.now() > self.expiry_date

    def __str__(self):
        return self.name


class WifiPayment(models.Model):
    customer = models.ForeignKey(WifiCustomer, on_delete=models.CASCADE)
    package = models.ForeignKey(WifiPackage, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    transaction_code = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default="PENDING")
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer} - {self.amount}"


class WifiCallbackLog(models.Model):
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

# 💧 WATER SYSTEM

class WaterMeter(models.Model):
    house = models.OneToOneField("rentals.House", on_delete=models.CASCADE)
    meter_number = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.house} - {self.meter_number}"


class WaterReading(models.Model):
    meter = models.ForeignKey(WaterMeter, on_delete=models.CASCADE)
    reading = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.meter} - {self.reading}"


class WaterBill(models.Model):
    tenant = models.ForeignKey("rentals.Tenant", on_delete=models.CASCADE)
    reading = models.ForeignKey(WaterReading, on_delete=models.CASCADE)

    units_used = models.DecimalField(max_digits=10, decimal_places=2)
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=50)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tenant} - Water {self.total_amount}"
