from django.db import models
from django.contrib.auth.models import User

from enterprise.models import Company, Branch, Department


class UserProfile(models.Model):

    ROLE_CHOICES = [
        ("MD", "Managing Director"),
        ("CEO", "Chief Executive Officer"),
        ("GM", "General Manager"),
        ("MANAGER", "Manager"),
        ("SUPERVISOR", "Supervisor"),
        ("FINANCE", "Finance"),
        ("ACCOUNTS", "Accounts"),
        ("AUDITOR", "Auditor"),
        ("WIFI_TECHNICIAN", "Wi-Fi Technician"),
    ]

    EMPLOYMENT_STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("PROBATION", "Probation"),
        ("LEAVE", "On Leave"),
        ("SUSPENDED", "Suspended"),
        ("INACTIVE", "Inactive"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
    )

    employee_id = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )

    job_title = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="staff_profiles",
        null=True,
        blank=True,
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="staff_profiles",
        null=True,
        blank=True,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="staff_profiles",
        null=True,
        blank=True,
    )

    profile_photo = models.ImageField(
        upload_to="accounts/profile_photos/",
        null=True,
        blank=True,
    )

    signature = models.ImageField(
        upload_to="accounts/signatures/",
        null=True,
        blank=True,
    )

    bio = models.TextField(
        blank=True,
        default="",
    )

    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default="ACTIVE",
    )

    employment_date = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class CompanyAssignment(models.Model):

    ROLE_CHOICES = [
        ("MD", "Managing Director"),
        ("CEO", "Chief Executive Officer"),
        ("GM", "General Manager"),
        ("MANAGER", "Manager"),
        ("SUPERVISOR", "Supervisor"),
        ("FINANCE", "Finance"),
        ("ACCOUNTS", "Accounts"),
        ("AUDITOR", "Auditor"),
        ("WIFI_TECHNICIAN", "Wi-Fi Technician"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="company_assignments",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="executive_assignments",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_assignments",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_assignments",
    )

    job_title = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"],
                name="unique_user_company_assignment",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.get_role_display()} - "
            f"{self.company.name}"
        )


