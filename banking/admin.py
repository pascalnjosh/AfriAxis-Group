from django.contrib import admin, messages
from .models import BankAccount, BankStatementTemplate, BankStatementUpload, BankTransaction
from .utils import process_bank_statement


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("bank_name", "account_name", "account_number", "currency", "opening_balance", "active")
    list_filter = ("bank_name", "currency", "active")
    search_fields = ("bank_name", "account_name", "account_number")


@admin.register(BankStatementTemplate)
class BankStatementTemplateAdmin(admin.ModelAdmin):
    list_display = ("bank_name", "date_column", "description_column", "money_in_column", "money_out_column", "balance_column", "active")
    list_filter = ("bank_name", "active")
    search_fields = ("bank_name",)


@admin.register(BankStatementUpload)
class BankStatementUploadAdmin(admin.ModelAdmin):
    list_display = ("bank_account", "template", "file", "uploaded_at", "uploaded_by", "processed")
    list_filter = ("processed", "uploaded_at", "bank_account", "template")
    actions = ["process_selected_statements"]

    def process_selected_statements(self, request, queryset):
        for statement in queryset:
            if not statement.processed:
                process_bank_statement(statement)

        self.message_user(request, "Selected bank statements processed successfully.", messages.SUCCESS)

    process_selected_statements.short_description = "Process selected bank statements"


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "description",
        "money_in",
        "money_out",
        "balance",
        "transaction_type",
        "suggested_category",
        "confidence",
        "match_status",
    )
    list_filter = ("transaction_type", "suggested_category", "match_status", "transaction_date")
    search_fields = ("description", "reference", "notes")