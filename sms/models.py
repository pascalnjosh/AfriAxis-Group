from django.db import models
from django.contrib.auth.models import User
from rentals.models import Tenant


class SMSReminder(models.Model):
    REMINDER_TYPE_CHOICES = [
        ("rent", "Rent Reminder"),
        ("water", "Water Reminder"),
        ("general", "General Reminder"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="sms_reminders")
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE_CHOICES)
    phone_number = models.CharField(max_length=30)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tenant} - {self.reminder_type} - {self.status}"