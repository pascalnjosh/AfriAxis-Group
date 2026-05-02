from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Invoice, InvoicePayment

admin.site.register(Invoice)
admin.site.register(InvoicePayment)