from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    Account,
    AccountType,
    JournalEntry,
    JournalEntryLine,
)
from .services import post_journal_entry


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "normal_balance",
    )

    list_filter = (
        "category",
        "normal_balance",
    )

    search_fields = (
        "name",
    )


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "company",
        "account_type",
        "allow_posting",
        "active",
    )

    list_filter = (
        "company",
        "account_type",
        "allow_posting",
        "active",
    )

    search_fields = (
        "code",
        "name",
    )


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = (
        "journal_number",
        "company",
        "entry_date",
        "reference",
        "status",
        "total_debit",
        "total_credit",
    )

    list_filter = (
        "status",
        "entry_date",
        "company",
        "currency",
    )

    search_fields = (
        "journal_number",
        "reference",
        "description",
    )

    readonly_fields = (
        "posted_at",
        "created_at",
        "total_debit",
        "total_credit",
        "is_balanced",
    )

    inlines = [JournalEntryLineInline]

    actions = ["post_selected_journals"]

    @admin.action(
        description="Post selected journal entries"
    )
    def post_selected_journals(self, request, queryset):
        posted = 0
        failed = 0

        for journal in queryset:
            try:
                post_journal_entry(
                    journal_entry=journal,
                    user=request.user,
                )
                posted += 1

            except ValidationError as exc:
                failed += 1

                self.message_user(
                    request,
                    (
                        f"{journal.journal_number}: "
                        f"{'; '.join(exc.messages)}"
                    ),
                    level=messages.ERROR,
                )

        if posted:
            self.message_user(
                request,
                f"{posted} journal entry or entries posted.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} journal entry or entries failed.",
                level=messages.WARNING,
            )
