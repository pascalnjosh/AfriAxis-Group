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


from django.contrib import messages
from django.core.exceptions import ValidationError

from .adjustment_services import post_adjustment_note
from .models import AdjustmentNote


@admin.register(AdjustmentNote)
class AdjustmentNoteAdmin(admin.ModelAdmin):
    list_display = (
        "note_number",
        "note_type",
        "note_date",
        "party_name",
        "subtotal",
        "tax_amount",
        "total_amount",
        "status",
        "journal_entry",
    )

    list_filter = (
        "note_type",
        "status",
        "note_date",
        "company",
    )

    search_fields = (
        "note_number",
        "customer_name",
        "supplier__name",
        "supplier__supplier_code",
        "reason",
    )

    readonly_fields = (
        "total_amount",
        "journal_entry",
        "posted_by",
        "posted_at",
        "created_at",
        "updated_at",
    )


    actions = (
        "post_selected_adjustment_notes",
    )

    fieldsets = (
        (
            "Note details",
            {
                "fields": (
                    "note_number",
                    "company",
                    "note_type",
                    "note_date",
                    "status",
                    "reason",
                )
            },
        ),
        (
            "Customer or supplier",
            {
                "fields": (
                    "customer_name",
                )
            },
        ),
        (
            "Amounts",
            {
                "fields": (
                    "subtotal",
                    "tax_amount",
                    "total_amount",
                )
            },
        ),
        (
            "Posting information",
            {
                "fields": (
                    "journal_entry",
                    "posted_by",
                    "posted_at",
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def party_name(self, obj):
        if obj.note_type == "CUSTOMER_CREDIT":
            return obj.customer_name

        return str(obj.supplier or "")

    party_name.short_description = "Customer/Supplier"

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.created_by_id:
            obj.created_by = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    @admin.action(
        description="Post selected adjustment notes"
    )
    def post_selected_adjustment_notes(
        self,
        request,
        queryset,
    ):
        posted_count = 0
        failed_count = 0

        for note in queryset:
            try:
                post_adjustment_note(
                    adjustment_note=note,
                    user=request.user,
                )
                posted_count += 1

            except ValidationError as exc:
                failed_count += 1

                self.message_user(
                    request,
                    f"{note.note_number}: {exc}",
                    level=messages.ERROR,
                )

            except Exception as exc:
                failed_count += 1

                self.message_user(
                    request,
                    f"{note.note_number}: {exc}",
                    level=messages.ERROR,
                )

        if posted_count:
            self.message_user(
                request,
                (
                    f"{posted_count} adjustment note(s) "
                    f"posted successfully."
                ),
                level=messages.SUCCESS,
            )

        if failed_count:
            self.message_user(
                request,
                (
                    f"{failed_count} adjustment note(s) "
                    f"could not be posted."
                ),
                level=messages.WARNING,
            )


