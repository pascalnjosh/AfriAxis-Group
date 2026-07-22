from django.contrib import admin

from .models import (
    Branch,
    Company,
    Currency,
    Department,
    DocumentSequence,
    FiscalYear,
)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "symbol",
        "decimal_places",
        "active",
    )

    search_fields = (
        "code",
        "name",
    )


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "country",
        "kra_pin",
        "base_currency",
        "active",
    )

    search_fields = (
        "name",
        "kra_pin",
    )


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "code",
        "name",
        "is_head_office",
        "active",
    )

    list_filter = (
        "company",
        "active",
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "branch",
        "code",
        "name",
        "active",
    )

    list_filter = (
        "company",
        "branch",
    )


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "name",
        "start_date",
        "end_date",
        "is_current",
        "closed",
    )


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "branch",
        "document_type",
        "prefix",
        "next_number",
        "active",
    )

    list_filter = (
        "company",
        "document_type",
    )
